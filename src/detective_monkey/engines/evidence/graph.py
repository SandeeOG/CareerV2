"""Evidence Graph (22_EVIDENCE_ENGINE.md §6, §17).

The canonical bridge between raw observations and deterministic intelligence. It
holds immutable evidence, the relationships between evidence and the entities it
concerns, and any conflicts (which are stored, never discarded — §14).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ...domain.common.evidence import Evidence
from ...domain.common.identifiers import EvidenceId, StudentId


class EvidenceRelationType(str, Enum):
    """How evidence relates to entities/other evidence (22 §17)."""

    SUPPORTS = "supports"
    DEMONSTRATES = "demonstrates"
    CONFIRMS = "confirms"
    CONTRADICTS = "contradicts"


@dataclass(frozen=True, slots=True)
class EvidenceRelation:
    """A typed link from an evidence item to a target subject/entity."""

    source: EvidenceId
    relation: EvidenceRelationType
    target_subject: str


@dataclass(frozen=True, slots=True)
class EvidenceConflict:
    """Conflicting evidence for the same subject (22 §14).

    The Evidence Engine records conflicts and their confidences; the Student
    Intelligence Engine decides how to interpret them.
    """

    subject: str
    evidence_ids: tuple[EvidenceId, ...]
    note: str = ""


@dataclass(frozen=True, slots=True)
class EvidenceGraph:
    """An immutable, per-student graph of canonical evidence."""

    student_id: StudentId
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    relations: tuple[EvidenceRelation, ...] = field(default_factory=tuple)
    conflicts: tuple[EvidenceConflict, ...] = field(default_factory=tuple)

    def for_subject(self, subject: str) -> tuple[Evidence, ...]:
        return tuple(e for e in self.evidence if e.subject == subject)

    def subjects(self) -> set[str]:
        return {e.subject for e in self.evidence}
