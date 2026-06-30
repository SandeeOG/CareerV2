"""Phase 2 — Intelligence engines.

Each engine implements the uniform contract from
``detective_monkey.contracts`` (20_ENGINE_CONTRACTS.md) and transforms canonical
domain objects into other canonical domain objects. Engines own no persistence,
no API and no UI; tunable logic (assessment definitions, feature formulas,
aggregation rules, recommendation weights, prompts) is supplied as data or
injected strategies, never hardcoded.

Deterministic engines (assessment, evidence, feature engineering, student
intelligence, recommendation) are reproducible. AI-facing engines (explanation,
retrieval, agent) keep their deterministic core separate and treat any LLM as an
optional, provider-agnostic port.
"""
