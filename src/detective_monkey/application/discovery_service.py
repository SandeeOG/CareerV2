"""Application service for the discovery loop (v3 "Close the loop").

Hypothesis → calibrated experiment → reflection → experience evidence →
recalibrated hypotheses. This service orchestrates; the Discovery Engine
designs, the Evidence Engine merges, the Intelligence Engine re-ranks. The
"here's what changed" diff returned by ``complete`` is the heart of the
product: the student watches their map move and can ask why.
"""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace

from ..domain.common.identifiers import StudentId
from ..engines.discovery import (
    ACCEPTED,
    COMPLETED,
    PROPOSED,
    SKIPPED,
    DiscoveryEngine,
    Experiment,
    Reflection,
    evidence_strength,
)
from ..engines.student_evidence import StudentEvidenceEngine
from .dto import ErrorCode, ServiceResult

_HYPOTHESES_TO_TEST = 3     # keep this many live proposals
_SCORE_MOVE_THRESHOLD = 0.5  # points on the 0-100 match scale


def _experiment_json(e: Experiment) -> dict:
    return {
        "id": e.id, "career_id": e.career_id, "career_name": e.career_name,
        "title": e.title, "brief": e.brief, "task": e.task,
        "steps": list(e.steps), "modality": e.modality,
        "tier_label": e.tier_label, "minutes": e.minutes,
        "tests": [t.replace("_", " ").title() for t in e.tests_features],
        "why_this_task": list(e.calibration_reasons),
        "status": e.status, "created_at": e.created_at,
        "completed_at": e.completed_at,
        "score_moves": [
            {"career": c, "before": b, "after": a} for c, b, a in e.score_moves],
        "reflection": (
            {"enjoyment": e.reflection.enjoyment,
             "would_do_again": e.reflection.would_do_again}
            if e.reflection else None),
    }


class DiscoveryApplicationService:
    def __init__(
        self,
        engine: DiscoveryEngine,
        experiments,                # ExperimentRepository
        evidence_engine: StudentEvidenceEngine,
        evidence_profiles,          # EvidenceProfileRepository
        evidence_service,           # EvidenceApplicationService (rebuild path)
        intelligence,               # IntelligenceApplicationService (ranking)
        career_knowledge,           # CareerKnowledgeRepository | None
        ids,                        # IdGenerator
    ) -> None:
        self._engine = engine
        self._experiments = experiments
        self._evidence_engine = evidence_engine
        self._profiles = evidence_profiles
        self._evidence = evidence_service
        self._intelligence = intelligence
        self._knowledge = career_knowledge
        self._ids = ids

    # -- overview + proposals --------------------------------------------------

    def overview(self, student_id: StudentId) -> ServiceResult[dict]:
        profile = self._profiles.get(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No evidence profile yet.")
        self._evidence.ensure_ready(student_id)
        self._ensure_proposals(student_id, profile)
        experiments = self._experiments.list_for_student(student_id)
        return ServiceResult.ok({
            "student_id": student_id.value,
            "active": [_experiment_json(e) for e in experiments if e.status == ACCEPTED],
            "proposed": [_experiment_json(e) for e in experiments if e.status == PROPOSED],
            "completed": [_experiment_json(e) for e in reversed(experiments)
                          if e.status == COMPLETED],
            "momentum": self.momentum(student_id),
        })

    def next_experiment(self, student_id: StudentId) -> dict | None:
        """The dashboard's lead card: the active experiment, else the top
        proposal (creating proposals if none exist yet)."""
        profile = self._profiles.get(student_id)
        if profile is None:
            return None
        self._ensure_proposals(student_id, profile)
        experiments = self._experiments.list_for_student(student_id)
        active = [e for e in experiments if e.status == ACCEPTED]
        if active:
            return _experiment_json(active[0])
        proposed = [e for e in experiments if e.status == PROPOSED]
        return _experiment_json(proposed[0]) if proposed else None

    def strength_for(self, student_id: StudentId, profile, career) -> int:
        """Displayed evidence strength for one hypothesis. Feature-level
        evidence transfers between similar careers, but a career the student
        never directly tried is capped — transferred evidence alone should
        never read as 'fully tested'."""
        strength = evidence_strength(profile, career)
        runs = sum(1 for e in self._experiments.list_for_student(student_id)
                   if e.career_id == career.id and e.status == COMPLETED)
        return strength if runs > 0 else min(strength, 50)

    def momentum(self, student_id: StudentId) -> dict:
        """Discovery momentum — the anti-'100% complete'. Counts loop cycles,
        not checklist completion."""
        experiments = self._experiments.list_for_student(student_id)
        completed = [e for e in experiments if e.status == COMPLETED]
        beliefs_moved = sum(1 for e in completed if e.score_moves)
        return {
            "cycles": len(completed),
            "careers_tested": len({e.career_id for e in completed}),
            "beliefs_updated": beliefs_moved,
            "active": sum(1 for e in experiments if e.status == ACCEPTED),
            "proposed": sum(1 for e in experiments if e.status == PROPOSED),
            "last_cycle_at": completed[-1].completed_at if completed else "",
        }

    def hypotheses(self, student_id: StudentId, limit: int = 10) -> ServiceResult[dict]:
        """Ranked hypotheses: fit score × evidence strength × experiments run."""
        profile = self._profiles.get(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No evidence profile yet.")
        self._evidence.ensure_ready(student_id)
        recs = self._intelligence.recommend(student_id)
        if not recs.success or recs.data is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No hypotheses yet.")
        by_career = self._experiments_by_career(student_id)
        rows = []
        for card in recs.data.cards[:limit]:
            known = self._knowledge.get(card.career_id) if self._knowledge else None
            runs = [e for e in by_career.get(card.career_id, ()) if e.status == COMPLETED]
            strength = 0
            if known is not None:
                strength = evidence_strength(profile, known)
                if not runs:
                    strength = min(strength, 50)
            rows.append({
                "career_id": card.career_id, "name": card.name,
                "score": round(card.score),
                "confidence": round(card.confidence * 100),
                "evidence_strength": strength,
                "experiments_run": len(runs),
                "why": list(card.match_explanation[:2]),
            })
        return ServiceResult.ok({"student_id": student_id.value, "hypotheses": rows})

    # -- lifecycle ---------------------------------------------------------------

    def accept(self, student_id: StudentId, experiment_id: str) -> ServiceResult[dict]:
        experiment = self._owned(student_id, experiment_id)
        if experiment is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "Experiment not found.")
        if experiment.status not in (PROPOSED, ACCEPTED):
            return ServiceResult.fail(ErrorCode.CONFLICT, "Experiment already finished.")
        updated = replace(experiment, status=ACCEPTED)
        self._experiments.save(updated)
        return ServiceResult.ok(_experiment_json(updated))

    def skip(self, student_id: StudentId, experiment_id: str) -> ServiceResult[dict]:
        """Skipping rotates to a different task for the same hypothesis —
        a skip is preference evidence about format, not about the career."""
        experiment = self._owned(student_id, experiment_id)
        if experiment is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "Experiment not found.")
        if experiment.status not in (PROPOSED, ACCEPTED):
            return ServiceResult.fail(ErrorCode.CONFLICT, "Experiment already finished.")
        self._experiments.save(replace(experiment, status=SKIPPED))
        replacement = None
        profile = self._profiles.get(student_id)
        career = self._knowledge.get(experiment.career_id) if self._knowledge else None
        if profile is not None and career is not None:
            replacement = self._engine.design(
                profile, career, self._ids.new_id("exp"),
                attempt=experiment.attempt + 1)
            self._experiments.save(replacement)
        return ServiceResult.ok({
            "skipped": experiment_id,
            "replacement": _experiment_json(replacement) if replacement else None,
        })

    def complete(self, student_id: StudentId, experiment_id: str,
                 payload: dict) -> ServiceResult[dict]:
        """Close one discovery cycle: reflection → evidence → recalibration →
        the "here's what changed" diff."""
        experiment = self._owned(student_id, experiment_id)
        if experiment is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "Experiment not found.")
        if experiment.status == COMPLETED:
            return ServiceResult.fail(ErrorCode.CONFLICT, "Already completed.")
        profile = self._profiles.get(student_id)
        if profile is None:
            return ServiceResult.fail(ErrorCode.NOT_FOUND, "No evidence profile yet.")
        try:
            reflection = Reflection(
                enjoyment=float(payload.get("enjoyment", 3)),
                energy=float(payload.get("energy", 3)),
                would_do_again=float(payload.get("would_do_again", 3)),
                text=str(payload.get("text", ""))[:2000],
            )
        except (TypeError, ValueError) as exc:
            return ServiceResult.fail(ErrorCode.VALIDATION_ERROR, f"Bad reflection: {exc}")

        self._evidence.ensure_ready(student_id)
        before_scores = self._scores(student_id)
        before_features = dict(profile.extracted_features)
        career = self._knowledge.get(experiment.career_id) if self._knowledge else None
        strength_before = evidence_strength(profile, career) if career else 0

        # Reflection → experience evidence → merged profile → re-rank.
        features = self._engine.reflection_features(experiment, reflection)
        updated_profile = self._evidence_engine.apply_experience(profile, features)
        self._profiles.save(student_id, updated_profile)
        self._evidence.rebuild(student_id, updated_profile)

        after_scores = self._scores(student_id)
        career_moves = self._career_moves(before_scores, after_scores,
                                          experiment.career_id)
        feature_moves = self._feature_moves(before_features,
                                            dict(updated_profile.extracted_features),
                                            features.keys())
        now = datetime.now(timezone.utc).isoformat()
        done = replace(experiment, status=COMPLETED, completed_at=now,
                       reflection=reflection, score_moves=tuple(career_moves))
        self._experiments.save(done)
        self._ensure_proposals(student_id, updated_profile)

        strength_after = evidence_strength(updated_profile, career) if career else 0
        return ServiceResult.ok({
            "experiment": _experiment_json(done),
            "career_moves": [
                {"career": c, "before": round(b, 1), "after": round(a, 1),
                 "delta": round(a - b, 1)} for c, b, a in career_moves],
            "feature_moves": feature_moves,
            "evidence_strength": {
                "career": experiment.career_name,
                "before": strength_before, "after": strength_after},
            "momentum": self.momentum(student_id),
            "next_experiment": self.next_experiment(student_id),
        })

    # -- internals -----------------------------------------------------------------

    def _owned(self, student_id: StudentId, experiment_id: str) -> Experiment | None:
        experiment = self._experiments.get(experiment_id)
        if experiment is None or experiment.student_id != student_id.value:
            return None
        return experiment

    def _experiments_by_career(self, student_id: StudentId) -> dict[str, list]:
        grouped: dict[str, list] = {}
        for e in self._experiments.list_for_student(student_id):
            grouped.setdefault(e.career_id, []).append(e)
        return grouped

    def _ensure_proposals(self, student_id: StudentId, profile) -> None:
        """Keep one live experiment per top hypothesis (no duplicates)."""
        if self._knowledge is None:
            return
        recs = self._intelligence.recommend(student_id)
        if not recs.success or recs.data is None:
            return
        by_career = self._experiments_by_career(student_id)
        live = sum(1 for exps in by_career.values()
                   if any(e.status in (PROPOSED, ACCEPTED) for e in exps))
        for card in recs.data.cards[:_HYPOTHESES_TO_TEST * 2]:
            if live >= _HYPOTHESES_TO_TEST:
                break
            history = by_career.get(card.career_id, [])
            if any(e.status in (PROPOSED, ACCEPTED) for e in history):
                continue
            career = self._knowledge.get(card.career_id)
            if career is None:
                continue
            # Base attempt on this career's history (skip rotation) plus the
            # number of live proposals created so far, so the three cards on
            # offer use different formats rather than three identical tasks.
            attempt = sum(1 for e in history if e.status in (SKIPPED, COMPLETED)) + live
            experiment = self._engine.design(
                profile, career, self._ids.new_id("exp"), attempt=attempt)
            self._experiments.save(experiment)
            by_career.setdefault(card.career_id, []).append(experiment)
            live += 1

    def _scores(self, student_id: StudentId) -> dict[str, tuple[str, float]]:
        recs = self._intelligence.recommend(student_id)
        if not recs.success or recs.data is None:
            return {}
        return {c.career_id: (c.name, c.score) for c in recs.data.cards}

    @staticmethod
    def _career_moves(before: dict, after: dict, focus_career_id: str
                      ) -> list[tuple[str, float, float]]:
        focus: tuple[str, float, float] | None = None
        moves: list[tuple[str, float, float, float]] = []
        for career_id, (name, after_score) in after.items():
            before_score = before.get(career_id, (name, after_score))[1]
            delta = after_score - before_score
            if career_id == focus_career_id:
                focus = (name, before_score, after_score)
            elif abs(delta) >= _SCORE_MOVE_THRESHOLD:
                moves.append((name, before_score, after_score, abs(delta)))
        moves.sort(key=lambda m: -m[3])
        # The tested career leads the diff, always — it's the hypothesis
        # the student just paid for with their time.
        out = [focus] if focus else []
        out.extend((n, b, a) for n, b, a, _ in moves[: 6 - len(out)])
        return out

    @staticmethod
    def _feature_moves(before: dict, after: dict, touched) -> list[dict]:
        rows = []
        for name in touched:
            b = before.get(name)
            a = after.get(name)
            if a is None:
                continue
            rows.append({
                "feature": name.replace("_", " ").title(),
                "before": round((b.score if b else 0.5) * 100),
                "after": round(a.score * 100),
            })
        rows.sort(key=lambda r: -abs(r["after"] - r["before"]))
        return rows[:6]
