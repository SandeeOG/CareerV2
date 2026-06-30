"""Feature values and the Feature Store (24_FEATURE_ENGINEERING_ENGINE.md §17, §18).

The Feature Store holds computed features only — never raw evidence (§18). It is
the reusable feature layer consumed by the Student Intelligence Engine, the
Recommendation Engine and analytics; no downstream component computes its own
features (§27).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.common.confidence import Confidence
from ...domain.common.identifiers import EvidenceId, StudentId
from ...domain.common.versioning import Version
from .definitions import FeatureType


@dataclass(frozen=True, slots=True)
class FeatureValue:
    """A single computed feature for a student (24 §18)."""

    feature_id: str
    student_id: StudentId
    value: float
    output_type: FeatureType
    confidence: Confidence
    version: Version
    completeness: float = 1.0
    sources: tuple[EvidenceId, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not (0.0 <= self.completeness <= 1.0):
            raise ValueError("FeatureValue.completeness must be within [0, 1]")


@dataclass(frozen=True, slots=True)
class FeatureSet:
    """The set of features produced for one student in one run (24 §6)."""

    student_id: StudentId
    features: tuple[FeatureValue, ...] = field(default_factory=tuple)

    def by_id(self, feature_id: str) -> FeatureValue | None:
        for f in self.features:
            if f.feature_id == feature_id:
                return f
        return None


class FeatureStore:
    """A minimal in-memory Feature Store (24 §17).

    Persistence belongs to later phases; this provides the canonical retrieval
    surface so engines never recompute features.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], FeatureValue] = {}

    def publish(self, feature: FeatureValue) -> None:
        self._store[(feature.student_id.value, feature.feature_id)] = feature

    def publish_set(self, feature_set: FeatureSet) -> None:
        for f in feature_set.features:
            self.publish(f)

    def get(self, student_id: StudentId, feature_id: str) -> FeatureValue | None:
        return self._store.get((student_id.value, feature_id))

    def __len__(self) -> int:
        return len(self._store)
