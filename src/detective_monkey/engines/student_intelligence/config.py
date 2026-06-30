"""Student Intelligence reasoning configuration (23_STUDENT_INTELLIGENCE_ENGINE.md §9).

Construct mapping and domain aggregation rules are configurable and versioned
(INV-... §9 "Aggregation rules are versioned and configurable"; 23 §23 DO NOT
"Hardcode aggregation rules"). The engine reads these; it never embeds them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.common.versioning import Version


@dataclass(frozen=True, slots=True)
class ConstructSource:
    """Maps a construct to the engineered feature that scores it (0..100)."""

    construct: str
    feature_id: str


@dataclass(frozen=True, slots=True)
class AggregationRule:
    """A domain score as a weighted aggregate of constructs (23 §9)."""

    domain: str
    components: tuple[tuple[str, float], ...]  # (construct, weight)

    def __post_init__(self) -> None:
        if not self.components:
            raise ValueError(f"AggregationRule '{self.domain}' needs components")


@dataclass(frozen=True, slots=True)
class DerivedFeatureSpec:
    """A derived indicator surfaced on the SIP, sourced from a feature."""

    name: str
    feature_id: str


@dataclass(frozen=True, slots=True)
class ReasoningConfig:
    """The full, versioned reasoning configuration."""

    version: Version
    construct_sources: tuple[ConstructSource, ...] = field(default_factory=tuple)
    domain_rules: tuple[AggregationRule, ...] = field(default_factory=tuple)
    derived_features: tuple[DerivedFeatureSpec, ...] = field(default_factory=tuple)
