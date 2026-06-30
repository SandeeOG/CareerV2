"""Education Model (14_EDUCATION_MODEL.md).

Models education as a reusable, versioned graph of pathways, qualifications,
institutions, competencies and learning outcomes — not a list of degrees.
Canonical educational knowledge is kept separate from individual student records.
"""

from .competencies import Competency, EducationSkill, LearningOutcome
from .enums import (
    EducationLevel,
    EnrollmentStatus,
    InstitutionType,
    PathwayKind,
    QualificationType,
    RequirementType,
)
from .institutions import Institution
from .pathways import (
    EducationPathway,
    FinancialEstimate,
    GeographicContext,
    SubjectComponent,
    TimeEstimate,
)
from .qualifications import Qualification
from .requirements import AlternativePathwayGroup, EducationRequirement
from .student_education import EducationGap, StudentEducation

__all__ = [
    "Competency",
    "EducationSkill",
    "LearningOutcome",
    "EducationLevel",
    "PathwayKind",
    "QualificationType",
    "InstitutionType",
    "RequirementType",
    "EnrollmentStatus",
    "Institution",
    "Qualification",
    "EducationPathway",
    "GeographicContext",
    "FinancialEstimate",
    "TimeEstimate",
    "SubjectComponent",
    "EducationRequirement",
    "AlternativePathwayGroup",
    "StudentEducation",
    "EducationGap",
]
