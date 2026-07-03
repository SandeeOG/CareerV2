"""Graph traversal: the discovery primitive.

Deterministic breadth-first expansion over the Knowledge Graph, with node-type
and relationship-type filters. This is what lets a query about "Python" reach
Data Science, Machine Learning and Bioinformatics without any of those links
being manually curated. Traversal never mutates the graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...application.ports import KnowledgeGraphRepository
from ...domain.knowledge_graph.edge import Edge
from ...domain.knowledge_graph.node import Node
from ...domain.knowledge_graph.ontology import NodeType, RelationshipType
from ..normalizers.text import slugify, tokens


@dataclass(frozen=True, slots=True)
class Subgraph:
    """The result of an expansion: reachable nodes plus the connecting edges."""

    nodes: tuple[Node, ...] = field(default_factory=tuple)
    edges: tuple[Edge, ...] = field(default_factory=tuple)

    def node_names(self) -> tuple[str, ...]:
        return tuple(n.canonical_name for n in self.nodes)


class GraphTraversal:
    """Read-only traversal over the canonical Knowledge Graph."""

    def __init__(self, graph: KnowledgeGraphRepository) -> None:
        self._graph = graph

    def nodes_of_type(self, node_type: NodeType) -> tuple[Node, ...]:
        return tuple(
            sorted(
                (n for n in self._graph.list_nodes() if n.node_type is node_type),
                key=lambda n: n.canonical_name,
            )
        )

    def find_by_name(self, name: str) -> Node | None:
        """Resolve a canonical name or alias to its node."""
        slug = slugify(name)
        for node in self._graph.list_nodes():
            if slugify(node.canonical_name) == slug:
                return node
        for node in self._graph.list_nodes():
            if any(slugify(a) == slug for a in node.aliases):
                return node
        return None

    def search(self, query: str, limit: int = 10) -> tuple[Node, ...]:
        """Rank nodes by token overlap with the query (name, aliases, tags)."""
        query_tokens = tokens(query)
        if not query_tokens:
            return ()
        scored: list[tuple[float, str, Node]] = []
        for node in self._graph.list_nodes():
            text = " ".join((node.canonical_name, *node.aliases, *node.semantic_tags,
                             node.description))
            node_tokens = tokens(text)
            overlap = len(query_tokens & node_tokens)
            if overlap:
                scored.append((overlap / len(query_tokens), node.canonical_name, node))
        scored.sort(key=lambda s: (-s[0], s[1]))
        return tuple(node for _, _, node in scored[:limit])

    def neighbours(
        self,
        node_id: str,
        *,
        node_types: frozenset[NodeType] | None = None,
        relationship_types: frozenset[RelationshipType] | None = None,
    ) -> tuple[Node, ...]:
        out: list[Node] = []
        for edge in self._graph.edges_of(node_id):
            if relationship_types and edge.edge_type not in relationship_types:
                continue
            other_id = edge.target.value if edge.source.value == node_id else edge.source.value
            node = self._graph.get_node(other_id)
            if node is None:
                continue
            if node_types and node.node_type not in node_types:
                continue
            out.append(node)
        out.sort(key=lambda n: n.canonical_name)
        return tuple(out)

    def expand(
        self,
        seed_ids: tuple[str, ...],
        depth: int = 1,
        *,
        node_types: frozenset[NodeType] | None = None,
        relationship_types: frozenset[RelationshipType] | None = None,
        limit: int = 50,
    ) -> Subgraph:
        """Breadth-first expansion from the seeds up to ``depth`` hops."""
        visited: dict[str, Node] = {}
        collected_edges: dict[str, Edge] = {}
        frontier = [s for s in seed_ids if self._graph.get_node(s) is not None]
        for node_id in frontier:
            node = self._graph.get_node(node_id)
            if node is not None:
                visited[node_id] = node

        for _ in range(max(0, depth)):
            next_frontier: list[str] = []
            for node_id in frontier:
                for edge in self._graph.edges_of(node_id):
                    if relationship_types and edge.edge_type not in relationship_types:
                        continue
                    other_id = (
                        edge.target.value
                        if edge.source.value == node_id
                        else edge.source.value
                    )
                    node = self._graph.get_node(other_id)
                    if node is None:
                        continue
                    if node_types and node.node_type not in node_types:
                        continue
                    collected_edges[edge.id.value] = edge
                    if other_id not in visited and len(visited) < limit:
                        visited[other_id] = node
                        next_frontier.append(other_id)
            frontier = next_frontier
            if not frontier or len(visited) >= limit:
                break

        nodes = tuple(sorted(visited.values(), key=lambda n: n.canonical_name))
        edges = tuple(sorted(collected_edges.values(), key=lambda e: e.id.value))
        return Subgraph(nodes=nodes, edges=edges)

    def find_path(self, start_id: str, goal_id: str, max_depth: int = 6) -> tuple[Node, ...]:
        """Shortest path between two nodes (BFS); empty tuple when unreachable."""
        if self._graph.get_node(start_id) is None or self._graph.get_node(goal_id) is None:
            return ()
        parents: dict[str, str | None] = {start_id: None}
        frontier = [start_id]
        for _ in range(max_depth):
            next_frontier: list[str] = []
            for node_id in frontier:
                for edge in self._graph.edges_of(node_id):
                    other = (
                        edge.target.value
                        if edge.source.value == node_id
                        else edge.source.value
                    )
                    if other in parents:
                        continue
                    parents[other] = node_id
                    if other == goal_id:
                        return self._materialize(parents, goal_id)
                    next_frontier.append(other)
            frontier = next_frontier
            if not frontier:
                break
        return ()

    def _materialize(self, parents: dict[str, str | None], goal_id: str) -> tuple[Node, ...]:
        path_ids: list[str] = []
        cursor: str | None = goal_id
        while cursor is not None:
            path_ids.append(cursor)
            cursor = parents[cursor]
        nodes = [self._graph.get_node(i) for i in reversed(path_ids)]
        return tuple(n for n in nodes if n is not None)
