"""Shared value objects used across every domain module.

This package has no dependencies on other domain modules; it sits at the bottom
of the domain layering (10 §5). Everything here is immutable.
"""

from .attributes import Attributes
from .confidence import Confidence, ConfidenceFactor
from .evidence import Evidence
from .events import DomainEvent, EventName
from .identifiers import (
    CareerId,
    CompetencyId,
    EdgeId,
    EducationPathwayId,
    EntityId,
    EvidenceId,
    ExplanationId,
    IndustryId,
    InstitutionId,
    LabourMarketSnapshotId,
    MemoryId,
    NodeId,
    ProfileId,
    QualificationId,
    RecommendationId,
    SkillId,
    StudentId,
    SubjectId,
)
from .measures import (
    CEFRLevel,
    Coordinate,
    DateRange,
    Duration,
    DurationUnit,
    FreshnessScore,
    LanguageProficiency,
    Money,
    Priority,
    QualityScore,
    RiskLevel,
    SalaryPeriod,
    SalaryRange,
)
from .provenance import Provenance, SourceType
from .scores import (
    Importance,
    ProficiencyLevel,
    Score,
    ScoreRange,
    Trend,
    UnitInterval,
)
from .versioning import Timestamped, Version, VersionRef, VersionSet

__all__ = [
    "Attributes",
    "Confidence",
    "ConfidenceFactor",
    "Evidence",
    "DomainEvent",
    "EventName",
    "EntityId",
    "StudentId",
    "ProfileId",
    "CareerId",
    "SkillId",
    "EducationPathwayId",
    "QualificationId",
    "InstitutionId",
    "CompetencyId",
    "SubjectId",
    "IndustryId",
    "RecommendationId",
    "ExplanationId",
    "EvidenceId",
    "NodeId",
    "EdgeId",
    "MemoryId",
    "LabourMarketSnapshotId",
    "Provenance",
    "SourceType",
    "Money",
    "SalaryRange",
    "SalaryPeriod",
    "Duration",
    "DurationUnit",
    "DateRange",
    "Coordinate",
    "LanguageProficiency",
    "CEFRLevel",
    "RiskLevel",
    "Priority",
    "QualityScore",
    "FreshnessScore",
    "Score",
    "ScoreRange",
    "UnitInterval",
    "ProficiencyLevel",
    "Importance",
    "Trend",
    "Version",
    "VersionRef",
    "VersionSet",
    "Timestamped",
]
