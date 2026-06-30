"""In-memory event bus (405_EVENT_BUS_ARCHITECTURE.md).

Transports immutable domain events to independently-registered subscribers
(405 §11). Delivery is at-least-once with idempotency by ``event_id`` (§12, §14);
failing handlers are retried then routed to a dead-letter queue (§15, §16). The
bus contains no business logic (INV-07) and exposes delivery observability (§21).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..domain.common.events import DomainEvent, EventName

EventHandler = Callable[[DomainEvent], None]


@dataclass(frozen=True, slots=True)
class DeadLetter:
    event: DomainEvent
    subscriber: str
    reason: str
    retries: int


@dataclass(slots=True)
class _Metrics:
    published: int = 0
    delivered: int = 0
    duplicates: int = 0
    failures: int = 0
    dead_lettered: int = 0


class InMemoryEventBus:
    """A synchronous, in-memory `EventPublisher` with subscriptions."""

    def __init__(self, max_retries: int = 2) -> None:
        self._subscribers: dict[EventName, list[tuple[str, EventHandler]]] = {}
        self._seen: set[str] = set()
        self._dlq: list[DeadLetter] = []
        self._metrics = _Metrics()
        self._max_retries = max_retries

    # -- subscription ------------------------------------------------------

    def subscribe(self, event_name: EventName, name: str, handler: EventHandler) -> None:
        self._subscribers.setdefault(event_name, []).append((name, handler))

    # -- publishing (EventPublisher port) ---------------------------------

    def publish(self, event: DomainEvent) -> None:
        self._metrics.published += 1
        if event.event_id in self._seen:
            self._metrics.duplicates += 1
            return
        self._seen.add(event.event_id)
        for sub_name, handler in self._subscribers.get(event.name, []):
            self._deliver(sub_name, handler, event)

    def publish_all(self, events: tuple[DomainEvent, ...]) -> None:
        for event in events:
            self.publish(event)

    # -- delivery with retry + DLQ ----------------------------------------

    def _deliver(self, sub_name: str, handler: EventHandler, event: DomainEvent) -> None:
        attempt = 0
        while True:
            try:
                handler(event)
                self._metrics.delivered += 1
                return
            except Exception as exc:  # subscriber failure is isolated (405 §16)
                self._metrics.failures += 1
                attempt += 1
                if attempt > self._max_retries:
                    self._dlq.append(
                        DeadLetter(event, sub_name, f"{type(exc).__name__}: {exc}", attempt)
                    )
                    self._metrics.dead_lettered += 1
                    return

    # -- observability (405 §21) ------------------------------------------

    @property
    def dead_letters(self) -> tuple[DeadLetter, ...]:
        return tuple(self._dlq)

    def metrics(self) -> dict[str, int]:
        m = self._metrics
        return {
            "published": m.published,
            "delivered": m.delivered,
            "duplicates": m.duplicates,
            "failures": m.failures,
            "dead_lettered": m.dead_lettered,
        }
