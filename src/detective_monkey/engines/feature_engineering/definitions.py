"""Feature definitions (24_FEATURE_ENGINEERING_ENGINE.md §7, §8, §9, §12).

Feature definitions are configuration, not engine code (INV-06). Each definition
declares its formula (by id), its inputs (evidence subjects), its dependencies
(other features), normalization and version. Formulas themselves live in the
formula registry, keeping them external to the engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ...domain.common.versioning import Version


class FeatureType(str, Enum):
    """Declared output type of a feature (24 §9)."""

    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    PERCENTAGE = "percentage"
    PROBABILITY = "probability"
    CATEGORICAL = "categorical"


class FeatureCategory(str, Enum):
    """Feature category (24 §8). Extensible."""

    PSYCHOMETRIC = "psychometric"
    ACADEMIC = "academic"
    BEHAVIOURAL = "behavioural"
    TECHNICAL = "technical"
    EDUCATIONAL = "educational"
    SKILL = "skill"
    TEMPORAL = "temporal"
    PORTFOLIO = "portfolio"
    LABOUR = "labour"
    INTERACTION = "interaction"
    COMPOSITE = "composite"


class Normalization(str, Enum):
    """Deterministic normalization rules (24 §12)."""

    NONE = "none"
    MIN_MAX = "min_max"
    CLAMP_UNIT = "clamp_unit"
    PERCENT_TO_UNIT = "percent_to_unit"


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    """A versioned feature definition (24 §7)."""

    id: str
    name: str
    category: FeatureCategory
    output_type: FeatureType
    formula_id: str
    version: Version
    inputs: tuple[str, ...] = field(default_factory=tuple)  # evidence subjects
    dependencies: tuple[str, ...] = field(default_factory=tuple)  # feature ids
    weights: tuple[float, ...] = field(default_factory=tuple)  # for weighted formulas
    normalization: Normalization = Normalization.NONE
    norm_min: float = 0.0
    norm_max: float = 100.0
    owner: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("FeatureDefinition.id must be non-empty")
        if not self.formula_id.strip():
            raise ValueError("FeatureDefinition.formula_id must be non-empty")
