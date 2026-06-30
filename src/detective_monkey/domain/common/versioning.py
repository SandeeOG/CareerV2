"""Versioning primitives.

"Every domain object is versioned" (10_DOMAIN_MODEL.md §18). Historical states
must remain reproducible (11 §14, 12 §27, 16 §19, 17 §22, 18 §12). These value
objects let any object carry its own version and pin the versions of the inputs
it was derived from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True, order=True)
class Version:
    """A monotonic, integer version with an optional human label.

    Versions are append-only: a new state produces ``number + 1`` rather than
    mutating the previous version (11 §11, 19 §20).
    """

    number: int
    label: str = ""

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError("Version.number must be >= 1")

    def next(self, label: str = "") -> "Version":
        return Version(self.number + 1, label)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"v{self.number}" + (f" ({self.label})" if self.label else "")


# The set of input versions a derived intelligence object was computed from.
# Enables full reproducibility (16 §19, 18 §12 "Version Synchronization").
@dataclass(frozen=True, slots=True)
class VersionRef:
    """A pinned reference to another versioned object."""

    name: str
    version: Version


@dataclass(frozen=True, slots=True)
class VersionSet:
    """An immutable bundle of pinned input versions.

    Example (16 §19): a Recommendation pins the student profile version, career
    version, knowledge version, labour-market version, engine version, weight
    configuration version and explanation version.
    """

    refs: tuple[VersionRef, ...] = field(default_factory=tuple)

    def with_ref(self, name: str, version: Version) -> "VersionSet":
        return VersionSet(self.refs + (VersionRef(name, version),))

    def get(self, name: str) -> Version | None:
        for ref in self.refs:
            if ref.name == name:
                return ref.version
        return None


@dataclass(frozen=True, slots=True)
class Timestamped:
    """Mixin-style value object for objects that record a creation instant.

    Domain objects compose this rather than inherit, keeping them flat and
    serialization-friendly for later phases.
    """

    created_at: datetime = field(default_factory=_utcnow)
