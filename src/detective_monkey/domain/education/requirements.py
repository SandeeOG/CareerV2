"""Career education requirements and alternative pathways (14_EDUCATION_MODEL.md §14, §15).

A career references educational requirements with a requirement type. Many
careers support multiple alternative routes (14 §15, §25 DO NOT "Assume every
career requires a university degree"), so requirements are grouped into
independent alternatives.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..common.identifiers import CareerId, EducationPathwayId
from .enums import RequirementType


@dataclass(frozen=True, slots=True)
class EducationRequirement:
    """A single education requirement of a career."""

    career_id: CareerId
    pathway_id: EducationPathwayId
    requirement_type: RequirementType


@dataclass(frozen=True, slots=True)
class AlternativePathwayGroup:
    """A set of pathways that independently satisfy the same requirement.

    Satisfying *any* pathway in the group meets the requirement, modelling the
    "OR" routes in 14 §15.
    """

    career_id: CareerId
    pathways: tuple[EducationPathwayId, ...] = field(default_factory=tuple)
    requirement_type: RequirementType = RequirementType.ALTERNATIVE

    def __post_init__(self) -> None:
        if len(self.pathways) < 2:
            raise ValueError("An alternative group needs at least two pathways")
