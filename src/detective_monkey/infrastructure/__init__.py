"""Infrastructure layer (400_BACKEND_ARCHITECTURE.md §8).

Concrete adapters implementing the application ports. Everything here is
in-memory and dependency-free, so the platform runs and is fully testable
without PostgreSQL, Neo4j, a vector DB or an LLM provider. Real adapters
(SQLAlchemy, Neo4j, Anthropic, ...) replace these without touching the domain or
application layers (30 INV-08, 409 INV-01).
"""
