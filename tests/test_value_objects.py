"""Tests for the shared value objects (P1 common layer)."""

from __future__ import annotations

import dataclasses

import pytest

from detective_monkey.domain.common import (
    Score,
    ScoreRange,
    UnitInterval,
    Version,
    VersionSet,
)


def test_score_enforces_range() -> None:
    Score(0)
    Score(100)
    with pytest.raises(ValueError):
        Score(-1)
    with pytest.raises(ValueError):
        Score(100.1)


def test_unit_interval_enforces_range() -> None:
    UnitInterval(0.0)
    UnitInterval(1.0)
    with pytest.raises(ValueError):
        UnitInterval(1.5)


def test_score_is_immutable() -> None:
    s = Score(50)
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.value = 60  # type: ignore[misc]


def test_version_is_monotonic() -> None:
    v1 = Version(1)
    v2 = v1.next("recompute")
    assert v2.number == 2
    assert v2 > v1
    with pytest.raises(ValueError):
        Version(0)


def test_version_set_pins_inputs() -> None:
    vs = VersionSet().with_ref("knowledge", Version(3)).with_ref("career", Version(7))
    assert vs.get("knowledge") == Version(3)
    assert vs.get("career") == Version(7)
    assert vs.get("missing") is None


def test_score_range_contains() -> None:
    band = ScoreRange(Score(60), Score(90))
    assert band.contains(Score(75))
    assert not band.contains(Score(40))
    with pytest.raises(ValueError):
        ScoreRange(Score(90), Score(60))
