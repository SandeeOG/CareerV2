"""Application ports (404_REPOSITORY_ARCHITECTURE.md, 405_EVENT_BUS, 409_PROVIDER, 403_SERVICE).

Ports are the stable interfaces the application layer depends on; infrastructure
supplies adapters (400 §8/§15/§16). Repositories are aggregate-oriented and
storage-independent (404 §5), return domain objects (REP-05), expose intent-based
methods (404 §13), and contain no business logic (INV-02). Providers isolate
external services (409 §2). The event publisher transports immutable domain
events (405).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.career.career import Career
from ..domain.common.events import DomainEvent
from ..domain.common.identifiers import (
    CareerId,
    ProfileId,
    RecommendationId,
    SkillId,
    StudentId,
)
from ..domain.knowledge_graph.edge import Edge
from ..domain.knowledge_graph.node import Node
from ..domain.memory.memory import Memory
from ..domain.recommendation.recommendation import Recommendation
from ..domain.student.profile import StudentIntelligenceProfile
from ..domain.student.student import Student


class PersistenceError(Exception):
    """Domain-level persistence error (404 §20). Infra exceptions stay internal."""


class ConcurrencyError(PersistenceError):
    """Raised on an optimistic-concurrency version conflict (404 §15)."""


# --------------------------------------------------------------------------
# Aggregate repositories (404 §7)
# --------------------------------------------------------------------------


@runtime_checkable
class StudentRepository(Protocol):
    """Persists the Student aggregate root (31C §5)."""

    def add(self, student: Student) -> None: ...
    def get(self, student_id: StudentId) -> Student | None: ...
    def exists(self, student_id: StudentId) -> bool: ...


@runtime_checkable
class ProfileRepository(Protocol):
    """Persists immutable, versioned Student Intelligence Profiles (23 §14).

    Saving appends a version; ``get_active`` returns the latest.
    """

    def save(self, profile: StudentIntelligenceProfile) -> None: ...
    def get_active(self, student_id: StudentId) -> StudentIntelligenceProfile | None: ...
    def get(self, profile_id: ProfileId) -> StudentIntelligenceProfile | None: ...
    def list_versions(
        self, student_id: StudentId
    ) -> tuple[StudentIntelligenceProfile, ...]: ...


@runtime_checkable
class EvidenceGraphRepository(Protocol):
    """Persists the per-student Evidence Graph (22 §6)."""

    def save(self, student_id: StudentId, graph: object) -> None: ...
    def get(self, student_id: StudentId) -> object | None: ...


@runtime_checkable
class RecommendationRepository(Protocol):
    """Persists immutable Recommendation aggregates (31C §10)."""

    def add(self, recommendation: Recommendation) -> None: ...
    def get(self, recommendation_id: RecommendationId) -> Recommendation | None: ...
    def list_for_student(self, student_id: StudentId) -> tuple[Recommendation, ...]: ...


@runtime_checkable
class MemoryRepository(Protocol):
    """Persists Memory records (31C §14)."""

    def add(self, memory: Memory) -> None: ...
    def list_for_student(self, student_id: StudentId) -> tuple[Memory, ...]: ...


# --------------------------------------------------------------------------
# Read + graph repositories (404 §8, §10)
# --------------------------------------------------------------------------


@runtime_checkable
class CareerCatalogRepository(Protocol):
    """Read-optimized career catalogue (404 §8). Never modifies state."""

    def get(self, career_id: CareerId) -> Career | None: ...
    def list_all(self) -> tuple[Career, ...]: ...
    def find_by_skill(self, skill_id: SkillId) -> tuple[Career, ...]: ...


@runtime_checkable
class KnowledgeGraphRepository(Protocol):
    """Access to the canonical Knowledge Graph (404 §10, 32A §5)."""

    def add_node(self, node: Node) -> None: ...
    def add_edge(self, edge: Edge) -> None: ...
    def list_nodes(self) -> tuple[Node, ...]: ...
    def neighbours(self, node_id: str) -> tuple[Node, ...]: ...


# --------------------------------------------------------------------------
# Event bus (405)
# --------------------------------------------------------------------------


@runtime_checkable
class EventPublisher(Protocol):
    """Publishes domain events after a successful transaction (405 §10)."""

    def publish(self, event: DomainEvent) -> None: ...
    def publish_all(self, events: tuple[DomainEvent, ...]) -> None: ...


# --------------------------------------------------------------------------
# Providers (409) + platform services (403 §7)
# --------------------------------------------------------------------------


@runtime_checkable
class Clock(Protocol):
    """Platform clock service (403 §7)."""

    def now(self) -> object: ...


@runtime_checkable
class IdGenerator(Protocol):
    """Platform id-generation service (403 §7, 30 §7 opaque ids)."""

    def new_id(self, prefix: str) -> str: ...


@runtime_checkable
class ConfigurationService(Protocol):
    """Centralized configuration (410). Business logic never reads env directly."""

    def get(self, key: str, default: str | None = None) -> str | None: ...
