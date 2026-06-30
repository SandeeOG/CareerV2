"""Career Intelligence Model (12_CAREER_INTELLIGENCE_MODEL.md).

The canonical, global representation of careers as reusable graphs. Career
knowledge never contains student-specific information, and labour-market data is
referenced rather than embedded.
"""

from .career import Career
from .identity import CareerIdentity, ExternalCodes
from .layers import (
    CertificationRef,
    CompetencyRequirement,
    KnowledgeAreaRequirement,
    PersonalityRequirement,
    Responsibility,
    SubjectRequirement,
    TechnologyRef,
    ToolRef,
    WorkStyle,
    WorkValue,
)
from .progression import ProgressionPath, ProgressionStep
from .relationships import CareerRelation, CareerRelationType

__all__ = [
    "Career",
    "CareerIdentity",
    "ExternalCodes",
    "KnowledgeAreaRequirement",
    "SubjectRequirement",
    "PersonalityRequirement",
    "WorkValue",
    "WorkStyle",
    "Responsibility",
    "TechnologyRef",
    "ToolRef",
    "CertificationRef",
    "CompetencyRequirement",
    "ProgressionPath",
    "ProgressionStep",
    "CareerRelation",
    "CareerRelationType",
]
