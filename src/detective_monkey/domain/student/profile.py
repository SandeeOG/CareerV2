"""Student Intelligence Profile — the canonical representation of a student.

The SIP (11_STUDENT_INTELLIGENCE_MODEL.md §9) is *the single source of truth for
student intelligence*. Every subsystem consumes it; no subsystem recomputes
student intelligence (00 §5, 10 §7).

Invariants enforced here:
    - The SIP is **immutable** for a given version (10 §7, 11 §18 DO). Updates
      create a new version rather than mutating history (INV-02).
    - The SIP contains processed intelligence only. It never contains career
      rankings, AI responses or UI state (11 §9 "The SIP never contains").
    - Every profile records its engine/model versions for reproducibility
      (INV-04, INV-05).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from ..common.identifiers import EvidenceId, ProfileId, StudentId
from ..common.provenance import Provenance
from ..common.versioning import Version, VersionSet
from .reliability import ReliabilityMetrics
from .scores import ConstructScore, DerivedFeature, DomainScore


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProfileStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class IntelligenceCategory(str, Enum):
    """Independent intelligence categories (11 §12)."""

    IDENTITY = "identity"
    BEHAVIOURAL = "behavioural"
    ACADEMIC = "academic"
    TECHNICAL = "technical"
    EXPERIENTIAL = "experiential"
    ASPIRATIONAL = "aspirational"
    PREDICTIVE = "predictive"


@dataclass(frozen=True, slots=True)
class StudentIntelligenceProfile:
    """An immutable, versioned snapshot of everything the platform understands
    about a student's intelligence."""

    id: ProfileId
    student_id: StudentId
    profile_version: Version
    construct_scores: tuple[ConstructScore, ...] = field(default_factory=tuple)
    domain_scores: tuple[DomainScore, ...] = field(default_factory=tuple)
    derived_features: tuple[DerivedFeature, ...] = field(default_factory=tuple)
    reliability: ReliabilityMetrics = field(default_factory=ReliabilityMetrics)
    evidence: tuple[EvidenceId, ...] = field(default_factory=tuple)
    # Pinned input versions for full reproducibility (11 §14, INV-04/05).
    input_versions: VersionSet = field(default_factory=VersionSet)
    provenance: Provenance | None = None
    status: ProfileStatus = ProfileStatus.ACTIVE
    created_at: datetime = field(default_factory=_utcnow)

    def construct(self, name: str) -> ConstructScore | None:
        for cs in self.construct_scores:
            if cs.construct == name:
                return cs
        return None

    def feature(self, name: str) -> DerivedFeature | None:
        for df in self.derived_features:
            if df.name == name:
                return df
        return None
