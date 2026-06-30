"""Skill taxonomy and relationship types (13_SKILLS_MODEL.md §5, §9).

"Categories exist only for organization. Relationships define intelligence."
(13 §5)
"""

from __future__ import annotations

from enum import Enum


class SkillCategory(str, Enum):
    """Primary skill category — every skill belongs to exactly one (13 §5)."""

    TECHNICAL = "technical"
    ANALYTICAL = "analytical"
    SCIENTIFIC = "scientific"
    ENGINEERING = "engineering"
    BUSINESS = "business"
    CREATIVE = "creative"
    COMMUNICATION = "communication"
    LEADERSHIP = "leadership"
    RESEARCH = "research"
    HEALTHCARE = "healthcare"
    TEACHING = "teaching"
    LEGAL = "legal"
    LANGUAGE = "language"
    DIGITAL_LITERACY = "digital_literacy"
    INTERPERSONAL = "interpersonal"
    PHYSICAL = "physical"
    DOMAIN_SPECIFIC = "domain_specific"


class SkillRelationType(str, Enum):
    """Edge types between skills (13 §9)."""

    PARENT = "parent"
    CHILD = "child"
    PREREQUISITE = "prerequisite"
    COMPLEMENTARY = "complementary"
    ALTERNATIVE = "alternative"
    REPLACEMENT = "replacement"
    EMERGING = "emerging"
    DEPRECATED = "deprecated"
    FREQUENTLY_COMBINED = "frequently_combined"


class SkillLifecycle(str, Enum):
    """Skill lifecycle states (13 §18)."""

    CREATED = "created"
    VALIDATED = "validated"
    PUBLISHED = "published"
    REFERENCED = "referenced"
    UPDATED = "updated"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
