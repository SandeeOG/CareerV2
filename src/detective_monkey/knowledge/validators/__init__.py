"""Validation: the gate between generated/imported knowledge and the database."""

from .checks import Severity, ValidationIssue, check_conflicts
from .pipeline import (
    EntityValidationReport,
    RelationshipValidationReport,
    ValidationPipeline,
)

__all__ = [
    "EntityValidationReport",
    "RelationshipValidationReport",
    "Severity",
    "ValidationIssue",
    "ValidationPipeline",
    "check_conflicts",
]
