"""In-memory repository adapters (404_REPOSITORY_ARCHITECTURE.md).

These implement the application repository ports against in-memory stores. They
return domain objects, expose intent-based methods, and hold no business logic
(404 INV-02). Immutable aggregates (SIP, Recommendation) are append-only.
"""

from __future__ import annotations

from ..domain.career.career import Career
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
from ..engines.evidence.graph import EvidenceGraph


class InMemoryStudentRepository:
    def __init__(self) -> None:
        self._students: dict[str, Student] = {}

    def add(self, student: Student) -> None:
        self._students[student.id.value] = student

    def get(self, student_id: StudentId) -> Student | None:
        return self._students.get(student_id.value)

    def exists(self, student_id: StudentId) -> bool:
        return student_id.value in self._students


class InMemoryProfileRepository:
    def __init__(self) -> None:
        self._by_student: dict[str, list[StudentIntelligenceProfile]] = {}
        self._by_id: dict[str, StudentIntelligenceProfile] = {}

    def save(self, profile: StudentIntelligenceProfile) -> None:
        self._by_student.setdefault(profile.student_id.value, []).append(profile)
        self._by_id[profile.id.value] = profile

    def get_active(self, student_id: StudentId) -> StudentIntelligenceProfile | None:
        versions = self._by_student.get(student_id.value)
        if not versions:
            return None
        return max(versions, key=lambda p: p.profile_version.number)

    def get(self, profile_id: ProfileId) -> StudentIntelligenceProfile | None:
        return self._by_id.get(profile_id.value)

    def list_versions(
        self, student_id: StudentId
    ) -> tuple[StudentIntelligenceProfile, ...]:
        versions = self._by_student.get(student_id.value, [])
        return tuple(sorted(versions, key=lambda p: p.profile_version.number))


class InMemoryEvidenceGraphRepository:
    def __init__(self) -> None:
        self._graphs: dict[str, EvidenceGraph] = {}

    def save(self, student_id: StudentId, graph: EvidenceGraph) -> None:
        self._graphs[student_id.value] = graph

    def get(self, student_id: StudentId) -> EvidenceGraph | None:
        return self._graphs.get(student_id.value)


class InMemoryRecommendationRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, Recommendation] = {}
        self._by_student: dict[str, list[str]] = {}

    def add(self, recommendation: Recommendation) -> None:
        self._by_id[recommendation.id.value] = recommendation
        # The recommendation pins the student profile version; derive student
        # ownership from the recommendation id scheme (rec_<student>_...).
        owner = self._owner(recommendation)
        self._by_student.setdefault(owner, []).append(recommendation.id.value)

    def get(self, recommendation_id: RecommendationId) -> Recommendation | None:
        return self._by_id.get(recommendation_id.value)

    def list_for_student(self, student_id: StudentId) -> tuple[Recommendation, ...]:
        ids = self._by_student.get(student_id.value, [])
        return tuple(self._by_id[i] for i in ids)

    @staticmethod
    def _owner(rec: Recommendation) -> str:
        parts = rec.id.value.split("_")
        return parts[1] if len(parts) > 1 else ""


class InMemoryMemoryRepository:
    def __init__(self) -> None:
        self._by_student: dict[str, list[Memory]] = {}

    def add(self, memory: Memory) -> None:
        owner = memory.owner.value if memory.owner else "_platform"
        self._by_student.setdefault(owner, []).append(memory)

    def list_for_student(self, student_id: StudentId) -> tuple[Memory, ...]:
        return tuple(self._by_student.get(student_id.value, []))


class InMemoryCareerCatalogRepository:
    def __init__(self, careers: tuple[Career, ...] = ()) -> None:
        self._careers: dict[str, Career] = {c.id.value: c for c in careers}

    def add(self, career: Career) -> None:
        self._careers[career.id.value] = career

    def get(self, career_id: CareerId) -> Career | None:
        return self._careers.get(career_id.value)

    def list_all(self) -> tuple[Career, ...]:
        return tuple(self._careers.values())

    def find_by_skill(self, skill_id: SkillId) -> tuple[Career, ...]:
        return tuple(
            c for c in self._careers.values()
            if any(cs.skill_id == skill_id for cs in c.skills)
        )


class InMemoryIntelligenceProfileRepository:
    """Stores the interpretation-rich Intelligence Profile per student.

    A separate store from the low-level SIP profiles (different aggregate). Latest
    profile per student wins.
    """

    def __init__(self) -> None:
        self._by_student: dict[str, object] = {}

    def save(self, student_id: StudentId, profile: object) -> None:
        self._by_student[student_id.value] = profile

    def get(self, student_id: StudentId) -> object | None:
        return self._by_student.get(student_id.value)


class InMemoryMentorMemory:
    """Persistent mentor memory (Epic 10): readiness history, goal, saved careers.

    Lets the AI mentor proactively continue with a returning student.
    """

    def __init__(self) -> None:
        self._readiness: dict[str, list[int]] = {}
        self._goal: dict[str, str] = {}
        self._saved: dict[str, list[str]] = {}

    def record_readiness(self, student_id: StudentId, score: int) -> None:
        self._readiness.setdefault(student_id.value, []).append(score)

    def readiness_history(self, student_id: StudentId) -> tuple[int, ...]:
        return tuple(self._readiness.get(student_id.value, []))

    def set_goal(self, student_id: StudentId, goal: str) -> None:
        self._goal[student_id.value] = goal

    def goal(self, student_id: StudentId) -> str | None:
        return self._goal.get(student_id.value)

    def save_career(self, student_id: StudentId, career_id: str) -> None:
        saved = self._saved.setdefault(student_id.value, [])
        if career_id not in saved:
            saved.append(career_id)

    def saved_careers(self, student_id: StudentId) -> tuple[str, ...]:
        return tuple(self._saved.get(student_id.value, []))


class InMemoryKnowledgeGraphRepository:
    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []

    def add_node(self, node: Node) -> None:
        self._nodes[node.id.value] = node

    def add_edge(self, edge: Edge) -> None:
        self._edges.append(edge)

    def list_nodes(self) -> tuple[Node, ...]:
        return tuple(self._nodes.values())

    def neighbours(self, node_id: str) -> tuple[Node, ...]:
        ids: set[str] = set()
        for e in self._edges:
            if e.source.value == node_id:
                ids.add(e.target.value)
            elif e.target.value == node_id:
                ids.add(e.source.value)
        return tuple(self._nodes[i] for i in ids if i in self._nodes)
