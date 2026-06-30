"""Engine registry (20_ENGINE_CONTRACTS.md §27, §28).

Engines register with a central registry so orchestration can discover concrete
implementations through interfaces rather than hardcoded references (§28). This
enables a plugin architecture.
"""

from __future__ import annotations

from .engine import BaseEngine, EngineMetadata


class EngineRegistry:
    """A simple in-memory registry keyed by engine name."""

    def __init__(self) -> None:
        self._engines: dict[str, BaseEngine] = {}

    def register(self, engine: BaseEngine) -> None:
        name = engine.metadata().engine_name
        if name in self._engines:
            raise ValueError(f"Engine '{name}' is already registered")
        self._engines[name] = engine

    def get(self, name: str) -> BaseEngine:
        try:
            return self._engines[name]
        except KeyError:
            raise KeyError(f"No engine registered under '{name}'") from None

    def has(self, name: str) -> bool:
        return name in self._engines

    def descriptions(self) -> tuple[EngineMetadata, ...]:
        return tuple(e.metadata() for e in self._engines.values())

    def __len__(self) -> int:
        return len(self._engines)
