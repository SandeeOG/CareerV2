"""Construct, domain and derived feature scores (11_STUDENT_INTELLIGENCE_MODEL.md §9).

These are the processed intelligence quantities held by the SIP. Each carries
confidence and evidence so it remains explainable and reproducible.

Key invariant (11 §13 INV-03): **derived features must always reference
evidence**. A construct or domain score likewise records the evidence that
produced it. Missing data is represented by absence, never fabricated (INV-08).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..common.confidence import Confidence
from ..common.identifiers import EvidenceId
from ..common.provenance import Provenance
from ..common.scores import Score


@dataclass(frozen=True, slots=True)
class ConstructScore:
    """A measured behavioural construct (e.g. analytical reasoning) — 11 §9.

    Construct scores originate from assessment evidence; they are not engineered.
    """

    construct: str
    score: Score
    confidence: Confidence
    evidence: tuple[EvidenceId, ...] = field(default_factory=tuple)
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if not self.construct.strip():
            raise ValueError("ConstructScore.construct must be non-empty")


@dataclass(frozen=True, slots=True)
class DomainScore:
    """A higher-level aggregate over constructs (11 §9 Domain Scores)."""

    domain: str
    score: Score
    confidence: Confidence
    derived_from: tuple[str, ...] = field(default_factory=tuple)  # construct names

    def __post_init__(self) -> None:
        if not self.domain.strip():
            raise ValueError("DomainScore.domain must be non-empty")


@dataclass(frozen=True, slots=True)
class DerivedFeature:
    """An engineered variable (11 §9 Derived Features).

    Derived features never originate directly from questionnaires (11 §9) and
    must reference the evidence behind them (INV-03).
    """

    name: str
    score: Score
    confidence: Confidence
    evidence: tuple[EvidenceId, ...]
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("DerivedFeature.name must be non-empty")
        if not self.evidence:
            raise ValueError(
                "DerivedFeature requires evidence (11_STUDENT_INTELLIGENCE_MODEL.md "
                "§13 INV-03)"
            )
