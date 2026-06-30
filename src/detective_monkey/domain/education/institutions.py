"""Institutions (14_EDUCATION_MODEL.md §9).

Institutions are reusable entities kept separate from pathways (INV-07, §25 DO
"Separate institutions from pathways").
"""

from __future__ import annotations

from dataclasses import dataclass

from ..common.identifiers import InstitutionId
from ..common.versioning import Version
from .enums import InstitutionType


@dataclass(frozen=True, slots=True)
class Institution:
    """A reusable educational provider."""

    id: InstitutionId
    name: str
    institution_type: InstitutionType
    version: Version
    country: str = ""
    region: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Institution.name must be non-empty")
