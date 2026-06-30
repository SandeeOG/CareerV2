"""StudentSkill — a student's evidence-backed relationship to a skill.

"A student never owns a Skill" (13 §13). Instead a ``StudentSkill`` links a
student to a canonical ``Skill`` and records proficiency, confidence and the
evidence behind it. Every student-skill relationship requires evidence
(13 §11, INV-04). Proficiency and confidence are kept distinct (13 §12, §23).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..common.confidence import Confidence
from ..common.evidence import Evidence
from ..common.identifiers import SkillId, StudentId
from ..common.scores import ProficiencyLevel, UnitInterval


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class StudentSkill:
    """An immutable snapshot of a student's standing in one skill."""

    student_id: StudentId
    skill_id: SkillId
    proficiency: ProficiencyLevel
    confidence: Confidence
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    growth_rate: UnitInterval | None = None
    verified: bool = False
    last_used: datetime | None = None
    recorded_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        # INV-04: a student-skill relationship must be backed by evidence, unless
        # it is the explicit "no evidence" baseline.
        if self.proficiency is not ProficiencyLevel.NO_EVIDENCE and not self.evidence:
            raise ValueError(
                "A StudentSkill with proficiency above NO_EVIDENCE requires evidence "
                "(13_SKILLS_MODEL.md §11, INV-04)"
            )
