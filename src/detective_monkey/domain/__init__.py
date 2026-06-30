"""The Detective Monkey domain model (Phase P1).

Layering (00_ARCHITECTURE_PRINCIPLES.md §4, 10_DOMAIN_MODEL.md §5):

    common            -> shared value objects (no domain dependencies)
    knowledge_graph   -> canonical semantic layer (17)
    skills            -> reusable capability nodes (13)
    career            -> career intelligence graph (12)
    education         -> learning pathways (14)
    labour_market     -> external market snapshots (15)
    student           -> Student Intelligence Profile (11)
    recommendation    -> deterministic decision objects (16)
    explanation       -> human-readable layer boundary object (10 §12)
    memory            -> personal, persistent memory (19)

Dependency rule: a module may import only from ``common`` and from modules that
sit *below* it in the domain layering. Reverse dependencies are prohibited
(10_DOMAIN_MODEL.md §16, 18_CORE_INTELLIGENCE_ARCHITECTURE.md §19).
"""
