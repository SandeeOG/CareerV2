"""Student Evidence Engine V1 — the primary source of information about a student.

Collects evidence (assessment, academics, goals, profile), transforms it into
structured features via deterministic scoring + provider-agnostic AI extraction,
and produces the Student Evidence Profile consumed by the Intelligence Engine,
recommendation ranking and the AI coach.
"""

from .definitions import (
    ASSESSMENT_ID,
    ASSESSMENT_VERSION,
    CAREER_PULSE,
    EVIDENCE_ASSESSMENT,
    PULSE_INTERVAL_DAYS,
    EvidenceAssessment,
    EvidenceQuestion,
    EvidenceSection,
    Option,
    assessment_to_json,
)
from .engine import (
    ENGINE_VERSION,
    EvidenceSubmission,
    StudentEvidenceEngine,
    to_assessment_result,
)
from .extraction import (
    ExtractionValidationError,
    build_extraction_prompt,
    extract_with_ai,
    heuristic_extraction,
    parse_and_validate,
)
from .schema import (
    FEATURE_NAMES,
    AcademicRecord,
    AssessmentEvidence,
    EvidenceMetadata,
    ExtractedFeature,
    OpenResponse,
    StudentEvidenceProfile,
    StudentGoalsInfo,
    StudentProfileInfo,
    profile_to_json,
)
from .scoring import StructuredAnswer, score_structured

__all__ = [
    "ASSESSMENT_ID",
    "ASSESSMENT_VERSION",
    "CAREER_PULSE",
    "EVIDENCE_ASSESSMENT",
    "PULSE_INTERVAL_DAYS",
    "ENGINE_VERSION",
    "FEATURE_NAMES",
    "AcademicRecord",
    "AssessmentEvidence",
    "EvidenceAssessment",
    "EvidenceMetadata",
    "EvidenceQuestion",
    "EvidenceSection",
    "EvidenceSubmission",
    "ExtractedFeature",
    "ExtractionValidationError",
    "OpenResponse",
    "Option",
    "StructuredAnswer",
    "StudentEvidenceEngine",
    "StudentEvidenceProfile",
    "StudentGoalsInfo",
    "StudentProfileInfo",
    "assessment_to_json",
    "build_extraction_prompt",
    "extract_with_ai",
    "heuristic_extraction",
    "parse_and_validate",
    "profile_to_json",
    "score_structured",
    "to_assessment_result",
]
