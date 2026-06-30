"""Career — the Career Intelligence Graph aggregate (12_CAREER_INTELLIGENCE_MODEL.md §5).

A career is represented as a connected graph of reusable layers, not a flat
record. It exists independently of any user and never contains student data
(INV-04). Labour-market and salary data are deliberately *not* embedded here;
they live in the Labour Market Model and are referenced by ``CareerId``
(15 §26 DO NOT "Store salary inside Career").

The aggregate is immutable (12 §30 "Keep careers immutable"); updates produce a
new ``version`` while historical versions remain reproducible (INV-06, INV-08).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..common.attributes import Attributes
from ..common.identifiers import (
    CareerId,
    EducationPathwayId,
    IndustryId,
)
from ..common.provenance import Provenance
from ..common.scores import UnitInterval
from ..common.versioning import Version
from ..knowledge_graph.ontology import NodeStatus, VerificationStatus
from ..skills.career_skill import CareerSkill
from .identity import CareerIdentity
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
from .progression import ProgressionPath


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Career:
    """An immutable, versioned career intelligence graph.

    Every layer is optional so a career can be described incrementally and grow
    to 100+ attributes (12 §31) without redesign. ``CareerSkill`` requirements
    reference canonical ``Skill`` entities rather than embedding them (13 §14).
    """

    identity: CareerIdentity
    version: Version

    # Capability and knowledge layers
    skills: tuple[CareerSkill, ...] = field(default_factory=tuple)
    knowledge_areas: tuple[KnowledgeAreaRequirement, ...] = field(default_factory=tuple)
    subjects: tuple[SubjectRequirement, ...] = field(default_factory=tuple)
    competencies: tuple[CompetencyRequirement, ...] = field(default_factory=tuple)

    # Behavioural / motivational layers
    personality: tuple[PersonalityRequirement, ...] = field(default_factory=tuple)
    work_values: tuple[WorkValue, ...] = field(default_factory=tuple)
    work_styles: tuple[WorkStyle, ...] = field(default_factory=tuple)
    responsibilities: tuple[Responsibility, ...] = field(default_factory=tuple)

    # Tooling
    technologies: tuple[TechnologyRef, ...] = field(default_factory=tuple)
    tools: tuple[ToolRef, ...] = field(default_factory=tuple)
    certifications: tuple[CertificationRef, ...] = field(default_factory=tuple)

    # References to other canonical entities (by id, never embedded)
    industries: tuple[IndustryId, ...] = field(default_factory=tuple)
    education_pathways: tuple[EducationPathwayId, ...] = field(default_factory=tuple)

    # Progression (alternative paths supported)
    progression: tuple[ProgressionPath, ...] = field(default_factory=tuple)

    # Metadata (12 §22)
    status: NodeStatus = NodeStatus.DRAFT
    verification_status: VerificationStatus = VerificationStatus.PROVISIONAL
    quality_score: UnitInterval | None = None
    coverage_score: UnitInterval | None = None
    provenance: Provenance | None = None
    metadata: Attributes = field(default_factory=Attributes)
    last_updated: datetime = field(default_factory=_utcnow)

    @property
    def id(self) -> CareerId:
        return self.identity.id
