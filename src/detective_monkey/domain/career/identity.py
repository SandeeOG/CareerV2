"""Career identity layer (12_CAREER_INTELLIGENCE_MODEL.md §6).

Stable identity for a career, including multiple external taxonomy codes. A
career has exactly one canonical identity (INV-01).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..common.identifiers import CareerId


@dataclass(frozen=True, slots=True)
class ExternalCodes:
    """External occupation taxonomy identifiers (12 §6).

    Multiple identifiers are supported so the career can align with ISCO, O*NET,
    ESCO and SOC without privileging any one taxonomy.
    """

    isco: str | None = None
    onet: str | None = None
    esco: str | None = None
    soc: str | None = None


@dataclass(frozen=True, slots=True)
class CareerIdentity:
    """Canonical identity of a career."""

    id: CareerId
    canonical_name: str
    slug: str
    description: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    codes: ExternalCodes = field(default_factory=ExternalCodes)

    def __post_init__(self) -> None:
        if not self.canonical_name.strip():
            raise ValueError("CareerIdentity.canonical_name must be non-empty")
        if not self.slug.strip():
            raise ValueError("CareerIdentity.slug must be non-empty")
