"""Immutable attribute bag.

Several domain objects carry open-ended metadata (12 §22, 17 §8). To preserve
immutability of frozen entities, metadata is stored as an :class:`Attributes`
value object backed by a tuple of key/value pairs rather than a mutable ``dict``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Attributes:
    """An immutable, hashable string-keyed attribute map."""

    items: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        keys = [k for k, _ in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("Attributes keys must be unique")

    @classmethod
    def of(cls, **kwargs: str) -> "Attributes":
        return cls(tuple(kwargs.items()))

    def get(self, key: str, default: str | None = None) -> str | None:
        for k, v in self.items:
            if k == key:
                return v
        return default

    def set(self, key: str, value: str) -> "Attributes":
        remaining = tuple((k, v) for k, v in self.items if k != key)
        return Attributes(remaining + ((key, value),))
