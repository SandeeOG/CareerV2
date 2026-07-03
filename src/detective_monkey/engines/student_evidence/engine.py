"""The Student Evidence Engine (STUDENT_EVIDENCE_ENGINE_V1).

Collect evidence → transform it into structured student features → build the
Student Evidence Profile. Four sources feed Version 1: the career assessment
(structured + open-ended), academic records, student goals and the student
profile. Missing sources are handled gracefully — merging naturally
re-normalizes over whatever evidence exists, and recommendations are never
blocked by missing information.

AI (any provider behind the LLM port) is used only for feature extraction from
open-ended text; all merging, scoring and downstream recommendation logic is
deterministic. Open responses are processed exactly once — the extracted
features are stored on the profile and reused everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from ...domain.common.attributes import Attributes
from ...domain.common.confidence import Confidence
from ...domain.common.evidence import Evidence
from ...domain.common.identifiers import EvidenceId, StudentId
from ...domain.common.provenance import Provenance, SourceType
from ...domain.common.versioning import Version
from ..assessment.responses import AssessmentResult, QualityMetrics
from .definitions import (
    CAREER_PULSE,
    EVIDENCE_ASSESSMENT,
    PULSE_INTERVAL_DAYS,
    EvidenceAssessment,
)
from .extraction import extract_with_ai, heuristic_extraction
from .schema import (
    AcademicRecord,
    AssessmentEvidence,
    EvidenceMetadata,
    ExtractedFeature,
    OpenResponse,
    StudentEvidenceProfile,
    StudentGoalsInfo,
    StudentProfileInfo,
)
from .scoring import StructuredAnswer, answered_structured_count, score_structured

ENGINE_VERSION = "evidence-v1"

# Academic subject-name keywords → the features a strong score supports.
_SUBJECT_FEATURES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("math",), ("analytical_thinking", "problem_solving")),
    (("physics", "chemistry", "biology", "science"), ("research_interest", "analytical_thinking")),
    (("computer", "informatics", "it"), ("technical_interest",)),
    (("art", "music", "design"), ("artistic_interest", "creativity")),
    (("english", "hindi", "language", "literature"), ("communication",)),
    (("business", "economics", "commerce", "accountancy"), ("business_interest",)),
)


@dataclass(frozen=True, slots=True)
class EvidenceSubmission:
    """Everything collected from the student in one assessment session."""

    student_id: StudentId
    profile: StudentProfileInfo = field(default_factory=StudentProfileInfo)
    academic: tuple[AcademicRecord, ...] = ()
    goals: StudentGoalsInfo = field(default_factory=StudentGoalsInfo)
    structured_answers: tuple[StructuredAnswer, ...] = ()
    open_responses: tuple[OpenResponse, ...] = ()


class StudentEvidenceEngine:
    """Builds and maintains the Student Evidence Profile."""

    def __init__(self, assessment: EvidenceAssessment = EVIDENCE_ASSESSMENT,
                 pulse: EvidenceAssessment = CAREER_PULSE) -> None:
        self._assessment = assessment
        self._pulse = pulse

    # -- build --------------------------------------------------------------

    def build(self, submission: EvidenceSubmission, llm: object | None = None,
              now: datetime | None = None) -> StudentEvidenceProfile:
        now = now or datetime.now(timezone.utc)
        sources: list[str] = ["profile"]

        # 1. Structured assessment answers (deterministic scoring).
        structured = score_structured(self._assessment, submission.structured_answers)
        if structured:
            sources.append("assessment")

        # 2. Open-ended responses — AI extraction, validated, with a
        #    deterministic fallback. Processed exactly once, stored forever.
        answered_open = tuple(r for r in submission.open_responses if r.text.strip())
        open_features = extract_with_ai(llm, answered_open)
        provider = "ai"
        if open_features is None:
            open_features = heuristic_extraction(answered_open)
            provider = "deterministic"
        if not answered_open:
            provider = "none"

        # 3 + 4. Academic records and goals → additional feature evidence.
        academic_features = self._academic_features(submission.academic)
        if academic_features:
            sources.append("academic")
        goals_features = self._goals_features(submission.goals, submission.profile)
        if not submission.goals.is_empty:
            sources.append("goals")

        # Merge — sources missing from a feature simply don't participate,
        # which re-normalizes the remaining evidence automatically.
        merged = _merge_feature_sets(structured, open_features,
                                     academic_features, goals_features)

        metadata = EvidenceMetadata(
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            sources_used=tuple(sources),
            extraction_provider=provider,
            validation_status="pending",
            engine_version=ENGINE_VERSION,
        )
        return StudentEvidenceProfile(
            student_id=submission.student_id.value,
            profile=submission.profile,
            academic=submission.academic,
            assessment=AssessmentEvidence(
                definition_id=self._assessment.id,
                definition_version=self._assessment.version,
                structured_answered=answered_structured_count(
                    self._assessment, submission.structured_answers),
                structured_total=len(self._assessment.structured_questions()),
                open_answered=len(answered_open),
                open_total=len(self._assessment.open_questions()),
                open_responses=answered_open,
            ),
            goals=submission.goals,
            extracted_features=tuple(sorted(merged.items())),
            metadata=metadata,
        )

    # -- human-in-the-loop validation ----------------------------------------

    def apply_validation(self, profile: StudentEvidenceProfile, verdict: str,
                         inaccurate: tuple[str, ...] = (),
                         now: datetime | None = None) -> StudentEvidenceProfile:
        """Record the student's verdict ("yes" | "partially" | "no") and soften
        any features they marked as inaccurate."""
        now = now or datetime.now(timezone.utc)
        verdict = verdict if verdict in ("yes", "partially", "no") else "partially"
        adjusted: list[tuple[str, ExtractedFeature]] = []
        for name, feat in profile.extracted_features:
            if name in inaccurate:
                feat = ExtractedFeature(
                    score=round(feat.score * 0.5 + 0.25, 4),  # pull toward neutral
                    confidence=round(feat.confidence * 0.5, 4),
                    evidence=feat.evidence[:2] + ("Student marked this as not accurate.",),
                )
            elif verdict == "yes":
                feat = replace(feat, confidence=round(min(1.0, feat.confidence + 0.15), 4))
            adjusted.append((name, feat))
        metadata = replace(profile.metadata,
                           validation_status=verdict,
                           validation_notes=(
                               f"Marked inaccurate: {', '.join(inaccurate)}" if inaccurate else ""),
                           updated_at=now.isoformat())
        return profile.with_features(tuple(adjusted), metadata)

    # -- experience evidence (the discovery loop) ------------------------------

    def apply_experience(self, profile: StudentEvidenceProfile,
                         features: dict[str, ExtractedFeature],
                         now: datetime | None = None) -> StudentEvidenceProfile:
        """Fold lived-experience evidence into the profile. Experience
        outweighs prior self-report (0.65/0.35 recency-weighted) but a single
        trial never overwrites history — beliefs move, they don't teleport."""
        now = now or datetime.now(timezone.utc)
        max_move = 0.20  # one experiment shifts a belief by at most 20 points
        current = dict(profile.extracted_features)
        for name, new in features.items():
            old = current.get(name)
            if old is None:
                current[name] = new
            else:
                target = 0.65 * new.score + 0.35 * old.score
                moved = old.score + max(-max_move, min(max_move, target - old.score))
                current[name] = ExtractedFeature(
                    score=round(min(1.0, max(0.0, moved)), 4),
                    confidence=round(min(1.0, max(old.confidence, new.confidence) + 0.05), 4),
                    evidence=(new.evidence + old.evidence)[:4],
                )
        sources = profile.metadata.sources_used
        if "experience" not in sources:
            sources = sources + ("experience",)
        metadata = replace(profile.metadata, sources_used=sources,
                           updated_at=now.isoformat())
        return profile.with_features(tuple(sorted(current.items())), metadata)

    # -- Career Pulse ---------------------------------------------------------

    def pulse_due(self, profile: StudentEvidenceProfile,
                  now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        last = profile.metadata.last_pulse_at or profile.metadata.created_at
        try:
            anchor = datetime.fromisoformat(last)
        except ValueError:
            return False
        return now - anchor >= timedelta(days=PULSE_INTERVAL_DAYS)

    def apply_pulse(self, profile: StudentEvidenceProfile,
                    structured_answers: tuple[StructuredAnswer, ...],
                    open_responses: tuple[OpenResponse, ...] = (),
                    llm: object | None = None,
                    now: datetime | None = None) -> StudentEvidenceProfile:
        """Fold a Career Pulse check-in into the profile: fresh answers update
        the touched features (recency-weighted); everything else is preserved."""
        now = now or datetime.now(timezone.utc)
        fresh = score_structured(self._pulse, structured_answers)
        answered_open = tuple(r for r in open_responses if r.text.strip())
        ai = extract_with_ai(llm, answered_open)
        for name, feat in (ai or heuristic_extraction(answered_open)).items():
            fresh[name] = _combine(fresh[name], feat) if name in fresh else feat

        current = dict(profile.extracted_features)
        for name, new in fresh.items():
            old = current.get(name)
            if old is None:
                current[name] = new
            else:
                current[name] = ExtractedFeature(
                    score=round(0.6 * new.score + 0.4 * old.score, 4),
                    confidence=round(min(1.0, max(new.confidence, old.confidence)), 4),
                    evidence=(new.evidence + old.evidence)[:4],
                )

        goals = profile.goals
        dream = next((r.text.strip() for r in answered_open
                      if r.question_id == "pls_open_goal" and r.text.strip()), "")
        if dream:
            goals = replace(goals, dream_career=dream[:80])

        metadata = replace(profile.metadata,
                           last_pulse_at=now.isoformat(),
                           updated_at=now.isoformat())
        return replace(profile, goals=goals,
                       extracted_features=tuple(sorted(current.items())),
                       metadata=metadata)

    # -- source-specific extraction (deterministic) ----------------------------

    @staticmethod
    def _academic_features(records: tuple[AcademicRecord, ...]
                           ) -> dict[str, ExtractedFeature]:
        collected: dict[str, list[tuple[float, str]]] = {}
        for record in records:
            subject = record.subject.lower()
            score01 = record.average_score / 100.0
            if record.trend == "improving":
                score01 = min(1.0, score01 + 0.05)
            elif record.trend == "declining":
                score01 = max(0.0, score01 - 0.05)
            for keywords, features in _SUBJECT_FEATURES:
                if any(k in subject for k in keywords):
                    text = (f"Scored {record.average_score:.0f}% in {record.subject}"
                            + (f" ({record.trend})" if record.trend != "stable" else ""))
                    for feature in features:
                        collected.setdefault(feature, []).append((score01, text))
                    break
        return {
            name: ExtractedFeature(
                score=round(sum(v for v, _ in rows) / len(rows), 4),
                confidence=round(min(0.85, 0.6 + 0.1 * len(rows)), 4),
                evidence=tuple(dict.fromkeys(t for _, t in rows))[:3],
            )
            for name, rows in collected.items()
        }

    @staticmethod
    def _goals_features(goals: StudentGoalsInfo, profile: StudentProfileInfo
                        ) -> dict[str, ExtractedFeature]:
        features: dict[str, ExtractedFeature] = {}
        tri = {"yes": 0.85, "maybe": 0.55, "no": 0.2}
        if goals.entrepreneurship_interest in tri:
            features["entrepreneurship"] = ExtractedFeature(
                tri[goals.entrepreneurship_interest], 0.7,
                (f"Said '{goals.entrepreneurship_interest}' to starting something of their own.",))
        if goals.willing_to_relocate in tri:
            features["relocation_preference"] = ExtractedFeature(
                tri[goals.willing_to_relocate], 0.7,
                (f"Said '{goals.willing_to_relocate}' to relocating for opportunity.",))
        if goals.preferred_country and goals.preferred_country.lower() not in (
                "", profile.country.lower()):
            features["international_interest"] = ExtractedFeature(
                0.8, 0.65, (f"Prefers working in {goals.preferred_country}.",))
        if goals.dream_career:
            features["career_confidence"] = ExtractedFeature(
                0.75, 0.6, (f"Already has a dream career in mind: {goals.dream_career}.",))
        return features


# -- merging -------------------------------------------------------------------


def _combine(a: ExtractedFeature, b: ExtractedFeature) -> ExtractedFeature:
    total = a.confidence + b.confidence
    if total <= 0:
        score = (a.score + b.score) / 2
    else:
        score = (a.score * a.confidence + b.score * b.confidence) / total
    return ExtractedFeature(
        score=round(score, 4),
        confidence=round(min(1.0, max(a.confidence, b.confidence)
                             + 0.1 * min(a.confidence, b.confidence)), 4),
        evidence=tuple(dict.fromkeys(a.evidence + b.evidence))[:4],
    )


def _merge_feature_sets(*sets: dict[str, ExtractedFeature]
                        ) -> dict[str, ExtractedFeature]:
    """Confidence-weighted merge. A feature seen by several independent
    sources gains confidence; features from absent sources simply drop out —
    the automatic re-normalization required by the spec."""
    merged: dict[str, ExtractedFeature] = {}
    for feature_set in sets:
        for name, feat in feature_set.items():
            merged[name] = _combine(merged[name], feat) if name in merged else feat
    return merged


# -- bridge to the Intelligence Engine ------------------------------------------
# The Recommendation flow consumes only the Student Evidence Profile: this
# adapter renders the profile as the construct-observation evidence package the
# deterministic Intelligence Engine already understands. No raw responses pass
# through.

_CONSTRUCT_FROM_FEATURES: tuple[tuple[str, tuple[tuple[str, float], ...]], ...] = (
    ("analytical_thinking", (("analytical_thinking", 0.7), ("problem_solving", 0.3))),
    ("creativity", (("creativity", 0.7), ("artistic_interest", 0.3))),
    ("leadership", (("leadership", 1.0),)),
    ("communication", (("communication", 0.7), ("people_interaction", 0.3))),
    ("curiosity", (("curiosity", 0.6), ("research_interest", 0.4))),
    ("conscientiousness", (("attention_to_detail", 1.0),)),
)


def to_assessment_result(profile: StudentEvidenceProfile) -> AssessmentResult:
    """Render the evidence profile as an AssessmentResult evidence package."""
    student_id = StudentId(profile.student_id)
    version = Version(profile.assessment.definition_version)
    evidence: list[Evidence] = []
    for construct, contributions in _CONSTRUCT_FROM_FEATURES:
        total_w = 0.0
        acc = 0.0
        conf = 0.0
        for feature_name, weight in contributions:
            feat = profile.feature(feature_name)
            if feat is None:
                continue
            acc += feat.score * weight
            conf = max(conf, feat.confidence)
            total_w += weight
        if total_w <= 0:
            continue
        score100 = (acc / total_w) * 100.0
        evidence.append(Evidence(
            id=EvidenceId(f"evidence_{profile.student_id}_{profile.assessment.definition_id}"
                          f"_v{version.number}_{construct}"),
            subject=construct,
            provenance=Provenance(
                SourceType.ASSESSMENT,
                description=f"Student Evidence Profile ({ENGINE_VERSION})",
                references=(profile.assessment.definition_id,),
            ),
            confidence=Confidence.of(max(0.05, conf)),
            summary=f"Evidence-derived construct '{construct}' = {score100:.1f}/100",
            metadata=Attributes.of(value=f"{score100:.4f}", kind="construct_observation"),
        ))
    return AssessmentResult(
        student_id=student_id,
        definition_id=profile.assessment.definition_id,
        definition_version=version,
        evidence=tuple(evidence),
        quality=QualityMetrics(
            completion=profile.assessment.completion,
            straight_lining=0.0,
            speeding=0.0,
        ),
    )
