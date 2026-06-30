"""Application layer (400_BACKEND_ARCHITECTURE.md §6, 403_SERVICE_ARCHITECTURE.md).

Transport-independent use-case orchestration. Application services coordinate
repositories, intelligence engines, providers and the event bus, define
transaction boundaries, and publish domain events after successful commits. They
own no business rules (those live in the domain + engines) and no persistence
(that lives behind repository ports).

This layer depends only on the domain, the engine contracts, and the *ports*
defined here — never on infrastructure implementations (dependency direction
always points inward, 400 §9).
"""
