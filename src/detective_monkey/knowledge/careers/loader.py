"""CareerKnowledgeLoader — the single import path for career knowledge.

Loads every generated career JSON file, validates each against the canonical
schema, enforces the cross-file rules (duplicate careers, relationship
integrity), normalizes relationships, and can ingest the whole set into the
Knowledge Platform as first-class entities and relationships. The application
never depends on manually seeded career dictionaries: this loader plus the
JSON files are the only source of career information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ...domain.common.attributes import Attributes
from ...domain.common.provenance import SourceType
from ...domain.common.scores import UnitInterval
from ...domain.knowledge_graph.ontology import NodeType, RelationshipType
from ..models.records import RawKnowledgeRecord, RawRelationshipHint, SourceMetadata
from ..normalizers.text import slugify
from ..services.platform import KnowledgePlatform
from ..sources.dataset import InMemoryDatasetSource
from .schema import (
    CareerProfile,
    IndustryProfile,
    load_json_file,
    profile_from_json,
    validate_career_json,
)

DATA_DIR = Path(__file__).parent / "data"
SOURCE_ID = "career_knowledge_v1"


@dataclass(frozen=True, slots=True)
class LoadReport:
    """What the loader accepted and why anything was rejected."""

    accepted: int = 0
    rejected: int = 0
    issues: tuple[str, ...] = field(default_factory=tuple)


class CareerKnowledgeLoader:
    """Load → validate → normalize → build repository / ingest into platform."""

    def __init__(self, data_dir: str | Path = DATA_DIR) -> None:
        self._data_dir = Path(data_dir)

    # -- loading ------------------------------------------------------------

    def load(self) -> tuple[tuple[CareerProfile, ...], tuple[IndustryProfile, ...], LoadReport]:
        issues: list[str] = []
        rejected = 0
        industries = self._load_industries(issues)
        industry_ids = {i.id for i in industries}

        raw_profiles: list[dict] = []
        for path in sorted(self._data_dir.glob("*.json")):
            if path.name == "industries.json":
                continue
            data, error = load_json_file(path)
            if error:
                issues.append(f"invalid JSON: {error}")
                rejected += 1
                continue
            problems = validate_career_json(data)
            if problems:
                issues.append(f"{path.name}: {'; '.join(problems)}")
                rejected += 1
                continue
            raw_profiles.append(data)

        # Cross-file: duplicate careers are rejected, first one wins.
        seen: set[str] = set()
        unique: list[dict] = []
        for data in raw_profiles:
            if data["id"] in seen:
                issues.append(f"duplicate career id rejected: {data['id']}")
                rejected += 1
                continue
            seen.add(data["id"])
            unique.append(data)

        # Normalization + relationship integrity: related careers must exist
        # (by name); unknown ones are dropped, and a profile whose relations
        # all vanish is rejected — the graph never links to invented entities.
        names = {data["name"] for data in unique}
        accepted: list[CareerProfile] = []
        for data in unique:
            related = [r for r in data["related_careers"] if r in names and r != data["name"]]
            dropped = set(data["related_careers"]) - set(related)
            if dropped:
                issues.append(f"{data['id']}: dropped unknown related {sorted(dropped)}")
            if not related:
                issues.append(f"{data['id']}: rejected — no valid related careers")
                rejected += 1
                continue
            if data["industry"] not in industry_ids:
                issues.append(f"{data['id']}: rejected — unknown industry {data['industry']}")
                rejected += 1
                continue
            data = {**data, "related_careers": related}
            accepted.append(profile_from_json(data))

        report = LoadReport(
            accepted=len(accepted), rejected=rejected, issues=tuple(issues))
        return tuple(sorted(accepted, key=lambda p: p.name)), industries, report

    def build_repository(self):
        from .repository import CareerKnowledgeRepository

        profiles, industries, report = self.load()
        return CareerKnowledgeRepository(profiles, industries, report)

    def _load_industries(self, issues: list[str]) -> tuple[IndustryProfile, ...]:
        path = self._data_dir / "industries.json"
        data, error = load_json_file(path)
        if error or not isinstance(data, list):
            issues.append(f"industries.json missing or invalid: {error or 'not a list'}")
            return ()
        out = []
        for item in data:
            try:
                out.append(IndustryProfile(
                    id=item["id"], name=item["name"], description=item["description"],
                    icon=item.get("icon", ""),
                    featured_careers=tuple(item.get("featured_careers", ())),
                    trending_careers=tuple(item.get("trending_careers", ())),
                    future_note=item.get("future_note", ""),
                ))
            except (KeyError, TypeError) as exc:
                issues.append(f"industries.json entry invalid: {exc}")
        return tuple(out)

    # -- knowledge platform ingestion ----------------------------------------

    def ingest_into(self, platform: KnowledgePlatform):
        """Register careers/industries/skills as a knowledge source and run
        one generation cycle — career profiles become first-class entities."""
        profiles, industries, _ = self.load()
        records: list[RawKnowledgeRecord] = []

        for industry in industries:
            records.append(RawKnowledgeRecord(
                source_id=SOURCE_ID, entity_type=NodeType.INDUSTRY,
                name=industry.name, description=industry.description,
                tags=("industry",),
            ))

        skills: dict[str, str] = {}
        for profile in profiles:
            for skill in profile.core_skills:
                skills.setdefault(slugify(skill), skill)

        for slug, skill_name in sorted(skills.items()):
            records.append(RawKnowledgeRecord(
                source_id=SOURCE_ID, entity_type=NodeType.SKILL,
                name=skill_name,
                description=f"{skill_name} — a core skill across career paths.",
            ))

        industry_names = {i.id: i.name for i in industries}
        for profile in profiles:
            hints = [RawRelationshipHint(
                RelationshipType.BELONGS_TO, industry_names[profile.industry],
                NodeType.INDUSTRY)]
            hints += [RawRelationshipHint(RelationshipType.RELATED_TO, related,
                                          NodeType.CAREER)
                      for related in profile.related_careers]
            hints += [RawRelationshipHint(RelationshipType.REQUIRES, skill,
                                          NodeType.SKILL, UnitInterval(0.8))
                      for skill in profile.core_skills]
            records.append(RawKnowledgeRecord(
                source_id=SOURCE_ID, entity_type=NodeType.CAREER,
                name=profile.name,
                description=profile.overview,
                tags=profile.tags,
                attributes=Attributes.of(
                    industry=profile.industry,
                    career_family=profile.career_family,
                    salary_entry_lpa=str(profile.salary_entry_lpa),
                    salary_senior_lpa=str(profile.salary_senior_lpa),
                    difficulty=str(profile.difficulty),
                    remote=f"{profile.remote_work:.2f}",
                    demand=f"{profile.future_demand:.2f}",
                    automation_risk=f"{profile.automation_risk:.2f}",
                ),
                relationships=tuple(hints),
            ))

        platform.sources.register(InMemoryDatasetSource(
            SourceMetadata(
                source_id=SOURCE_ID,
                name="Career Knowledge Base v1 (generated, validated)",
                source_type=SourceType.RESEARCH,
                reliability=UnitInterval(0.85),
                dataset_version="1",
            ),
            tuple(records),
        ))
        return platform.generation.ingest(SOURCE_ID)
