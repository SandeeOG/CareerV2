"""Evidence → career affinity (deterministic).

Scores how well a Student Evidence Profile's canonical features align with a
career knowledge profile (its industry, tags and opportunity flags). The result
feeds the ranker's additive-bonus hook, so recommendation ranking operates on
structured evidence — never on raw survey answers — and stays fully
deterministic and explainable.
"""

from __future__ import annotations

from .schema import StudentEvidenceProfile

# Industry id → (feature, weight) descriptors.
_INDUSTRY_FEATURES: dict[str, tuple[tuple[str, float], ...]] = {
    "technology-computing": (("technical_interest", 1.0), ("analytical_thinking", 0.4)),
    "business-finance": (("business_interest", 1.0), ("analytical_thinking", 0.3)),
    "healthcare-medicine": (("helping_others", 0.9), ("research_interest", 0.3),
                            ("people_interaction", 0.4)),
    "engineering-manufacturing": (("technical_interest", 0.8), ("hands_on_work", 0.6),
                                  ("problem_solving", 0.4)),
    "science-research": (("research_interest", 1.0), ("curiosity", 0.5),
                         ("analytical_thinking", 0.5)),
    "education-training": (("helping_others", 0.7), ("communication", 0.7),
                           ("people_interaction", 0.5)),
    "law-government": (("communication", 0.6), ("analytical_thinking", 0.5),
                       ("attention_to_detail", 0.4)),
    "arts-design-media": (("artistic_interest", 1.0), ("creativity", 0.7)),
    "communication-marketing": (("communication", 0.8), ("business_interest", 0.4),
                                ("creativity", 0.4), ("people_interaction", 0.5)),
    "agriculture-environment": (("hands_on_work", 0.7), ("research_interest", 0.3),
                                ("helping_others", 0.3)),
    "construction-urban": (("hands_on_work", 0.8), ("technical_interest", 0.5),
                           ("attention_to_detail", 0.3)),
    "hospitality-tourism": (("people_interaction", 0.9), ("helping_others", 0.4),
                            ("international_interest", 0.4)),
    "transport-logistics": (("attention_to_detail", 0.5), ("hands_on_work", 0.5),
                            ("analytical_thinking", 0.4)),
    "sports-wellness": (("hands_on_work", 0.8), ("people_interaction", 0.5)),
    "social-impact": (("helping_others", 1.0), ("people_interaction", 0.5)),
    "defence-security": (("risk_tolerance", 0.6), ("hands_on_work", 0.5),
                         ("leadership", 0.4), ("attention_to_detail", 0.3)),
}

# Career tag → (feature, weight).
_TAG_FEATURES: dict[str, tuple[tuple[str, float], ...]] = {
    "analytical": (("analytical_thinking", 0.6),),
    "mathematics": (("analytical_thinking", 0.6),),
    "numbers": (("analytical_thinking", 0.5),),
    "data": (("analytical_thinking", 0.4), ("technical_interest", 0.4)),
    "detail": (("attention_to_detail", 0.6),),
    "precision": (("attention_to_detail", 0.6),),
    "discipline": (("attention_to_detail", 0.4),),
    "organization": (("attention_to_detail", 0.4), ("leadership", 0.3)),
    "people": (("people_interaction", 0.6),),
    "communication": (("communication", 0.6),),
    "storytelling": (("creativity", 0.4), ("communication", 0.5)),
    "writing": (("communication", 0.5), ("artistic_interest", 0.3)),
    "science": (("research_interest", 0.6),),
    "research": (("research_interest", 0.6), ("curiosity", 0.3)),
    "lab": (("research_interest", 0.5),),
    "curious": (("curiosity", 0.6),),
    "creativity": (("creativity", 0.6),),
    "creative": (("creativity", 0.6), ("artistic_interest", 0.4)),
    "design": (("artistic_interest", 0.5), ("creativity", 0.4)),
    "innovation": (("creativity", 0.4), ("entrepreneurship", 0.3)),
    "leadership": (("leadership", 0.6),),
    "strategy": (("leadership", 0.4), ("business_interest", 0.4)),
    "business": (("business_interest", 0.6),),
    "teaching": (("helping_others", 0.5), ("communication", 0.4)),
    "care": (("helping_others", 0.6),),
    "empathy": (("helping_others", 0.5), ("people_interaction", 0.3)),
    "service": (("helping_others", 0.4),),
    "technology": (("technical_interest", 0.6),),
    "programming": (("technical_interest", 0.7),),
    "systems": (("technical_interest", 0.4), ("analytical_thinking", 0.3)),
    "practical": (("hands_on_work", 0.5),),
    "craft": (("hands_on_work", 0.5), ("artistic_interest", 0.3)),
    "outdoors": (("hands_on_work", 0.5),),
    "sports": (("hands_on_work", 0.5),),
    "energy": (("hands_on_work", 0.4),),
    "courage": (("risk_tolerance", 0.6),),
}

_NEUTRAL = 0.5


def career_descriptor_features(career) -> tuple[str, ...]:
    """The canonical features that describe what this career *is* — the
    features an experiment for this career actually tests. Ordered by weight,
    deduplicated."""
    weighted: dict[str, float] = {}
    for name, weight in _INDUSTRY_FEATURES.get(getattr(career, "industry", ""), ()):
        weighted[name] = max(weighted.get(name, 0.0), weight)
    for tag in getattr(career, "tags", ()):
        for name, weight in _TAG_FEATURES.get(tag, ()):
            weighted[name] = max(weighted.get(name, 0.0), weight)
    return tuple(sorted(weighted, key=lambda n: -weighted[n]))


def career_affinity(evidence: StudentEvidenceProfile, career) -> float:
    """Affinity in [0, 1] between the evidence profile and one career
    knowledge profile (duck-typed: industry, tags, entrepreneurship,
    remote_work, government_opportunities)."""
    features = dict(evidence.extracted_features)
    if not features:
        return _NEUTRAL

    acc, total = 0.0, 0.0
    # Industry descriptors define what the career *is*: when the student has
    # no evidence for one, it counts as neutral (low weight) rather than
    # dropping out — otherwise e.g. finance careers would inherit high scores
    # from generic tags alone when business interest was never measured.
    for name, weight in _INDUSTRY_FEATURES.get(getattr(career, "industry", ""), ()):
        feat = features.get(name)
        if feat is None:
            acc += _NEUTRAL * 0.3 * weight
            total += 0.3 * weight
        else:
            acc += feat.score * feat.confidence * weight
            total += feat.confidence * weight
    # Tag descriptors refine the picture; missing evidence simply drops out
    # (the automatic re-normalization the spec requires).
    for tag in getattr(career, "tags", ()):
        for name, weight in _TAG_FEATURES.get(tag, ()):
            feat = features.get(name)
            if feat is None:
                continue
            acc += feat.score * feat.confidence * weight
            total += feat.confidence * weight
    affinity = acc / total if total > 0 else _NEUTRAL

    # Declared goals adjust gently — they guide, never dominate.
    goals = evidence.goals
    entrepreneurship = features.get("entrepreneurship")
    if entrepreneurship is not None and getattr(career, "entrepreneurship", 0) >= 0.7:
        affinity += 0.06 * (entrepreneurship.score - 0.5) * 2
    if goals.preferred_work_style == "remote":
        affinity += 0.05 * (getattr(career, "remote_work", 0.5) - 0.5) * 2
    if goals.sector_preference == "government":
        affinity += 0.05 * (getattr(career, "government_opportunities", 0.5) - 0.5) * 2
    if goals.dream_career:
        dream = goals.dream_career.lower()
        name = getattr(career, "name", "").lower()
        if dream and (dream in name or name in dream):
            affinity += 0.08

    return max(0.0, min(1.0, affinity))


def affinity_map(evidence: StudentEvidenceProfile, careers) -> dict[str, float]:
    """Affinity per career id for the ranker's additive-bonus hook."""
    return {c.id: career_affinity(evidence, c) for c in careers}
