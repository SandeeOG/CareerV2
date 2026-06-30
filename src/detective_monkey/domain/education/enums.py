"""Education enumerations (14_EDUCATION_MODEL.md §6, §8, §9, §14)."""

from __future__ import annotations

from enum import Enum


class EducationLevel(str, Enum):
    """Educational hierarchy (14 §6). Extensible."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    HIGH_SCHOOL = "high_school"
    VOCATIONAL = "vocational"
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"
    DOCTORAL = "doctoral"
    PROFESSIONAL = "professional"
    CONTINUOUS = "continuous"


class PathwayKind(str, Enum):
    """Kinds of structured learning route (14 §4)."""

    BACHELOR_DEGREE = "bachelor_degree"
    MASTER_DEGREE = "master_degree"
    PHD = "phd"
    DIPLOMA = "diploma"
    VOCATIONAL_TRAINING = "vocational_training"
    PROFESSIONAL_CERTIFICATION = "professional_certification"
    ONLINE_COURSE = "online_course"
    BOOTCAMP = "bootcamp"
    APPRENTICESHIP = "apprenticeship"
    INTERNSHIP = "internship"
    RESEARCH_PROGRAM = "research_program"
    SELF_DIRECTED = "self_directed"


class QualificationType(str, Enum):
    """Qualification types (14 §8)."""

    DEGREE = "degree"
    DIPLOMA = "diploma"
    CERTIFICATE = "certificate"
    LICENSE = "license"
    PROFESSIONAL_CREDENTIAL = "professional_credential"
    MICROCREDENTIAL = "microcredential"
    DIGITAL_BADGE = "digital_badge"
    INDUSTRY_CERTIFICATION = "industry_certification"


class InstitutionType(str, Enum):
    """Educational provider types (14 §9)."""

    UNIVERSITY = "university"
    COLLEGE = "college"
    TECHNICAL_INSTITUTE = "technical_institute"
    TRAINING_CENTER = "training_center"
    ONLINE_PLATFORM = "online_platform"
    RESEARCH_INSTITUTE = "research_institute"
    PROFESSIONAL_ASSOCIATION = "professional_association"
    GOVERNMENT_ORGANIZATION = "government_organization"
    PRIVATE_ACADEMY = "private_academy"


class RequirementType(str, Enum):
    """How strongly a career requires an education pathway (14 §14)."""

    MANDATORY = "mandatory"
    RECOMMENDED = "recommended"
    PREFERRED = "preferred"
    OPTIONAL = "optional"
    ALTERNATIVE = "alternative"


class EnrollmentStatus(str, Enum):
    """Status of a student's education record (14 §20)."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
