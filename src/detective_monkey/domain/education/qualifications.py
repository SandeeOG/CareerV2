"""Qualifications (14_EDUCATION_MODEL.md §8).

Each qualification references a recognized issuer (INV-03) and records its level,
recognition and validity.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..common.identifiers import QualificationId
from ..common.scores import UnitInterval
from ..common.versioning import Version
from .enums import EducationLevel, QualificationType


@dataclass(frozen=True, slots=True)
class Qualification:
    """A reusable qualification definition."""

    id: QualificationId
    name: str
    qualification_type: QualificationType
    version: Version
    level: EducationLevel | None = None
    issuer: str = ""
    recognition: UnitInterval | None = None
    country: str = ""
    framework_alignment: str = ""
    validity_years: int | None = None
    renewal_required: bool | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Qualification.name must be non-empty")
        if not self.issuer.strip():
            # INV-03: qualifications reference recognized issuers.
            raise ValueError("Qualification.issuer must be provided (14 INV-03)")
