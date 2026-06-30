"""Infrastructure adapter tests (P3 repositories, P4 event bus)."""

from __future__ import annotations

import pytest

from detective_monkey.domain.common.events import DomainEvent, EventName
from detective_monkey.domain.common.identifiers import ProfileId, StudentId
from detective_monkey.domain.common.versioning import Version
from detective_monkey.domain.student.profile import StudentIntelligenceProfile
from detective_monkey.infrastructure.event_bus import InMemoryEventBus
from detective_monkey.infrastructure.repositories import InMemoryProfileRepository


def test_event_bus_is_idempotent_by_event_id():
    bus = InMemoryEventBus()
    seen: list[str] = []
    bus.subscribe(EventName.GOAL_CREATED, "c", lambda e: seen.append(e.event_id))
    ev = DomainEvent(EventName.GOAL_CREATED, "agg1", event_id="fixed-1")
    bus.publish(ev)
    bus.publish(ev)  # duplicate delivery
    assert len(seen) == 1
    assert bus.metrics()["duplicates"] == 1


def test_event_bus_dead_letters_failing_handler():
    bus = InMemoryEventBus(max_retries=1)

    def boom(_):
        raise RuntimeError("handler down")

    bus.subscribe(EventName.GOAL_CREATED, "flaky", boom)
    bus.publish(DomainEvent(EventName.GOAL_CREATED, "agg2"))
    assert len(bus.dead_letters) == 1
    assert bus.dead_letters[0].subscriber == "flaky"
    assert bus.metrics()["dead_lettered"] == 1


def test_profile_repository_returns_latest_active_version():
    repo = InMemoryProfileRepository()
    sid = StudentId("s1")
    v1 = StudentIntelligenceProfile(ProfileId("p1"), sid, Version(1))
    v2 = StudentIntelligenceProfile(ProfileId("p2"), sid, Version(2))
    repo.save(v1)
    repo.save(v2)
    assert repo.get_active(sid).profile_version == Version(2)
    assert len(repo.list_versions(sid)) == 2
    assert repo.get(ProfileId("p1")) is v1
