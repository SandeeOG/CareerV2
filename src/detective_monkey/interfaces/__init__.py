"""Interface layer (401_API_ARCHITECTURE.md).

Transport adapters (REST today; GraphQL/WebSocket/MCP later) that translate
protocols into application-service calls. Interfaces contain no business logic
(401 INV-03) and reuse the same application services regardless of transport
(401 §22).
"""
