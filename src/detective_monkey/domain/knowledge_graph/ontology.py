"""The Knowledge Graph ontology (17_KNOWLEDGE_GRAPH.md §5, §6).

The ontology centralizes every canonical node type and relationship type. New
types may be added without changing existing contracts (17 §5 GP / §28 "keep
ontology centralized").
"""

from __future__ import annotations

from enum import Enum


class NodeType(str, Enum):
    """Canonical root node types (17 §5)."""

    STUDENT = "student"  # referenced only; never stored in the graph (17 §13)
    CAREER = "career"
    SKILL = "skill"
    KNOWLEDGE_AREA = "knowledge_area"
    SUBJECT = "subject"
    COMPETENCY = "competency"
    EDUCATION_PATHWAY = "education_pathway"
    QUALIFICATION = "qualification"
    INSTITUTION = "institution"
    INDUSTRY = "industry"
    TECHNOLOGY = "technology"
    TOOL = "tool"
    CERTIFICATION = "certification"
    PROJECT = "project"
    LABOUR_MARKET = "labour_market"
    COUNTRY = "country"
    REGION = "region"
    LANGUAGE = "language"
    COMPANY = "company"
    PROFESSIONAL_ASSOCIATION = "professional_association"
    LEARNING_RESOURCE = "learning_resource"
    SCHOLARSHIP = "scholarship"
    INTERNSHIP = "internship"


class RelationshipType(str, Enum):
    """Canonical edge types (17 §6).

    Every edge must carry an explicit, semantically meaningful type; edges never
    exist without meaning (17 §6, §21 INV-03).
    """

    REQUIRES = "REQUIRES"
    USES = "USES"
    BELONGS_TO = "BELONGS_TO"
    RELATED_TO = "RELATED_TO"
    PART_OF = "PART_OF"
    PRECEDES = "PRECEDES"
    LEADS_TO = "LEADS_TO"
    SPECIALIZES = "SPECIALIZES"
    GENERALIZES = "GENERALIZES"
    ALTERNATIVE_TO = "ALTERNATIVE_TO"
    PREREQUISITE_OF = "PREREQUISITE_OF"
    LOCATED_IN = "LOCATED_IN"
    AVAILABLE_IN = "AVAILABLE_IN"
    CERTIFIED_BY = "CERTIFIED_BY"
    PROVIDED_BY = "PROVIDED_BY"
    EMPLOYED_BY = "EMPLOYED_BY"
    TAUGHT_BY = "TAUGHT_BY"
    ASSESSED_BY = "ASSESSED_BY"
    DEVELOPS = "DEVELOPS"
    SUPPORTS = "SUPPORTS"
    MEASURES = "MEASURES"


class VerificationStatus(str, Enum):
    """Knowledge verification state (17 §8, §11 — unverified knowledge stays
    provisional)."""

    PROVISIONAL = "provisional"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    DEPRECATED = "deprecated"


class NodeStatus(str, Enum):
    """Lifecycle status of a node / canonical entity (13 §18 lifecycle)."""

    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class EdgeDirection(str, Enum):
    """Whether a relationship is directed or symmetric (17 §9, §24 — similarity
    may be asymmetric, 12 §25)."""

    DIRECTED = "directed"
    UNDIRECTED = "undirected"
