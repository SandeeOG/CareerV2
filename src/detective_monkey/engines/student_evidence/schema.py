"""Student Evidence Engine — canonical schema (STUDENT_EVIDENCE_ENGINE_V1).

The Student Evidence Profile is the single source of truth about a student. It
is assembled from four evidence sources (assessment, academic records, goals,
profile) and holds the canonical extracted features. Every feature carries a
score, a confidence and supporting evidence — nothing is fabricated.

Raw survey responses never leave this package: downstream systems (the
Intelligence Engine, recommendation ranking, the AI coach) consume only the
structured profile.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


# The canonical student feature schema. Extraction (structured scoring, AI,
# academic, goals) may only produce these names; validation rejects others.
FEATURE_NAMES: tuple[str, ...] = (
    "analytical_thinking",
    "creativity",
    "leadership",
    "communication",
    "problem_solving",
    "curiosity",
    "technical_interest",
    "business_interest",
    "artistic_interest",
    "helping_others",
    "entrepreneurship",
    "risk_tolerance",
    "teamwork",
    "independence",
    "research_interest",
    "hands_on_work",
    "people_interaction",
    "attention_to_detail",
    "learning_style",
    "relocation_preference",
    "international_interest",
    "career_confidence",
)


def _unit(value: float, name: str) -> float:
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{name} must be within [0, 1], got {value}")
    return value


@dataclass(frozen=True, slots=True)
class ExtractedFeature:
    """One canonical feature: score + confidence + supporting evidence."""

    score: float
    confidence: float
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        _unit(self.score, "ExtractedFeature.score")
        _unit(self.confidence, "ExtractedFeature.confidence")
        if not self.evidence:
            raise ValueError("ExtractedFeature.evidence must be non-empty")


# -- evidence sources -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StudentProfileInfo:
    """Source 4 — basic student profile. No extra demographics."""

    name: str = ""
    age: int | None = None
    grade: str = ""
    school: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    board: str = ""


@dataclass(frozen=True, slots=True)
class AcademicRecord:
    """Source 2 — one subject line from a school management system import."""

    subject: str
    average_score: float          # 0-100
    trend: str = "stable"         # improving | stable | declining
    grade: str = ""
    academic_year: str = ""

    def __post_init__(self) -> None:
        if not (0.0 <= self.average_score <= 100.0):
            raise ValueError("AcademicRecord.average_score must be within [0, 100]")


@dataclass(frozen=True, slots=True)
class StudentGoalsInfo:
    """Source 3 — declared goals. Guide recommendations, never dominate them."""

    dream_career: str = ""
    preferred_country: str = ""
    preferred_subjects: tuple[str, ...] = field(default_factory=tuple)
    preferred_work_style: str = ""       # remote | office | field | mixed
    sector_preference: str = ""          # government | private | either
    entrepreneurship_interest: str = ""  # yes | maybe | no
    willing_to_relocate: str = ""        # yes | maybe | no

    @property
    def is_empty(self) -> bool:
        return not (self.dream_career or self.preferred_country
                    or self.preferred_subjects or self.preferred_work_style
                    or self.sector_preference or self.entrepreneurship_interest
                    or self.willing_to_relocate)


@dataclass(frozen=True, slots=True)
class OpenResponse:
    """One open-ended answer (Source 1). Processed exactly once by extraction."""

    question_id: str
    prompt: str
    text: str


@dataclass(frozen=True, slots=True)
class AssessmentEvidence:
    """The assessment section of the profile: structured construct scores plus
    the (already-processed) open responses kept for auditability."""

    definition_id: str
    definition_version: int
    structured_answered: int
    structured_total: int
    open_answered: int
    open_total: int
    open_responses: tuple[OpenResponse, ...] = field(default_factory=tuple)

    @property
    def completion(self) -> float:
        total = self.structured_total + self.open_total
        answered = self.structured_answered + self.open_answered
        return answered / total if total else 0.0


@dataclass(frozen=True, slots=True)
class EvidenceMetadata:
    """Provenance + lifecycle of the profile."""

    created_at: str = ""                 # ISO timestamp
    updated_at: str = ""
    sources_used: tuple[str, ...] = ()   # assessment | academic | goals | profile
    extraction_provider: str = ""        # e.g. "ai:gemini", "deterministic"
    validation_status: str = "pending"   # pending | yes | partially | no
    validation_notes: str = ""
    last_pulse_at: str = ""              # ISO timestamp of last Career Pulse
    engine_version: str = "evidence-v1"


@dataclass(frozen=True, slots=True)
class StudentEvidenceProfile:
    """The Student Evidence Profile — one per student, the single source of
    truth consumed by every downstream system."""

    student_id: str
    profile: StudentProfileInfo
    academic: tuple[AcademicRecord, ...]
    assessment: AssessmentEvidence
    goals: StudentGoalsInfo
    extracted_features: tuple[tuple[str, ExtractedFeature], ...]
    metadata: EvidenceMetadata

    def feature(self, name: str) -> ExtractedFeature | None:
        for key, value in self.extracted_features:
            if key == name:
                return value
        return None

    def top_features(self, n: int, *, exclude: tuple[str, ...] = ()) -> tuple[tuple[str, ExtractedFeature], ...]:
        pairs = [(k, v) for k, v in self.extracted_features if k not in exclude]
        pairs.sort(key=lambda p: (-p[1].score, p[0]))
        return tuple(pairs[:n])

    def with_features(self, features: tuple[tuple[str, ExtractedFeature], ...],
                      metadata: EvidenceMetadata | None = None) -> "StudentEvidenceProfile":
        return replace(self, extracted_features=features,
                       metadata=metadata or self.metadata)

    def with_metadata(self, metadata: EvidenceMetadata) -> "StudentEvidenceProfile":
        return replace(self, metadata=metadata)


# -- serialization (transport boundary) --------------------------------------


def feature_to_json(f: ExtractedFeature) -> dict:
    return {"score": round(f.score, 4), "confidence": round(f.confidence, 4),
            "evidence": list(f.evidence)}


def profile_to_json(p: StudentEvidenceProfile) -> dict:
    return {
        "student_id": p.student_id,
        "profile": {
            "name": p.profile.name, "age": p.profile.age, "grade": p.profile.grade,
            "school": p.profile.school, "city": p.profile.city,
            "state": p.profile.state, "country": p.profile.country,
            "board": p.profile.board,
        },
        "academic": [
            {"subject": a.subject, "average_score": a.average_score,
             "trend": a.trend, "grade": a.grade, "academic_year": a.academic_year}
            for a in p.academic
        ],
        "assessment": {
            "definition_id": p.assessment.definition_id,
            "definition_version": p.assessment.definition_version,
            "structured_answered": p.assessment.structured_answered,
            "structured_total": p.assessment.structured_total,
            "open_answered": p.assessment.open_answered,
            "open_total": p.assessment.open_total,
            "completion": round(p.assessment.completion, 4),
            "open_responses": [
                {"question_id": r.question_id, "prompt": r.prompt, "text": r.text}
                for r in p.assessment.open_responses
            ],
        },
        "goals": {
            "dream_career": p.goals.dream_career,
            "preferred_country": p.goals.preferred_country,
            "preferred_subjects": list(p.goals.preferred_subjects),
            "preferred_work_style": p.goals.preferred_work_style,
            "sector_preference": p.goals.sector_preference,
            "entrepreneurship_interest": p.goals.entrepreneurship_interest,
            "willing_to_relocate": p.goals.willing_to_relocate,
        },
        "extracted_features": {k: feature_to_json(v) for k, v in p.extracted_features},
        "metadata": {
            "created_at": p.metadata.created_at,
            "updated_at": p.metadata.updated_at,
            "sources_used": list(p.metadata.sources_used),
            "extraction_provider": p.metadata.extraction_provider,
            "validation_status": p.metadata.validation_status,
            "validation_notes": p.metadata.validation_notes,
            "last_pulse_at": p.metadata.last_pulse_at,
            "engine_version": p.metadata.engine_version,
        },
    }


def profile_from_json(data: dict) -> StudentEvidenceProfile:
    """Inverse of profile_to_json — the durable-persistence round trip."""
    p, a, g, m = (data.get("profile") or {}, data.get("assessment") or {},
                  data.get("goals") or {}, data.get("metadata") or {})
    return StudentEvidenceProfile(
        student_id=data["student_id"],
        profile=StudentProfileInfo(
            name=p.get("name", ""), age=p.get("age"), grade=p.get("grade", ""),
            school=p.get("school", ""), city=p.get("city", ""),
            state=p.get("state", ""), country=p.get("country", ""),
            board=p.get("board", ""),
        ),
        academic=tuple(
            AcademicRecord(
                subject=r["subject"], average_score=float(r["average_score"]),
                trend=r.get("trend", "stable"), grade=r.get("grade", ""),
                academic_year=r.get("academic_year", ""),
            ) for r in data.get("academic", [])
        ),
        assessment=AssessmentEvidence(
            definition_id=a.get("definition_id", ""),
            definition_version=int(a.get("definition_version", 1)),
            structured_answered=int(a.get("structured_answered", 0)),
            structured_total=int(a.get("structured_total", 0)),
            open_answered=int(a.get("open_answered", 0)),
            open_total=int(a.get("open_total", 0)),
            open_responses=tuple(
                OpenResponse(r["question_id"], r.get("prompt", ""), r.get("text", ""))
                for r in a.get("open_responses", [])
            ),
        ),
        goals=StudentGoalsInfo(
            dream_career=g.get("dream_career", ""),
            preferred_country=g.get("preferred_country", ""),
            preferred_subjects=tuple(g.get("preferred_subjects", [])),
            preferred_work_style=g.get("preferred_work_style", ""),
            sector_preference=g.get("sector_preference", ""),
            entrepreneurship_interest=g.get("entrepreneurship_interest", ""),
            willing_to_relocate=g.get("willing_to_relocate", ""),
        ),
        extracted_features=tuple(sorted(
            (name, ExtractedFeature(
                score=float(f["score"]), confidence=float(f["confidence"]),
                evidence=tuple(f["evidence"])))
            for name, f in (data.get("extracted_features") or {}).items()
        )),
        metadata=EvidenceMetadata(
            created_at=m.get("created_at", ""), updated_at=m.get("updated_at", ""),
            sources_used=tuple(m.get("sources_used", [])),
            extraction_provider=m.get("extraction_provider", ""),
            validation_status=m.get("validation_status", "pending"),
            validation_notes=m.get("validation_notes", ""),
            last_pulse_at=m.get("last_pulse_at", ""),
            engine_version=m.get("engine_version", "evidence-v1"),
        ),
    )
