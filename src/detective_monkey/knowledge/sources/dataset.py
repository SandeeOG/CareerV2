"""Structured dataset sources.

`InMemoryDatasetSource` wraps records already in memory (seeds, tests, API
payloads). `DelimitedFileSource` is the generic adapter for downloaded public
datasets; `ONetOccupationSource` and `EscoOccupationSource` are presets over
the actual column layouts of the O*NET "Occupation Data" file and the ESCO
occupations CSV export, so ingesting either taxonomy is configuration, not code.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ...domain.knowledge_graph.ontology import NodeType
from ..models.records import RawKnowledgeRecord, SourceMetadata
from .base import KnowledgeSource


class InMemoryDatasetSource(KnowledgeSource):
    """A source over records constructed elsewhere (seeds, tests, integrations)."""

    def __init__(
        self,
        metadata: SourceMetadata,
        records: tuple[RawKnowledgeRecord, ...],
    ) -> None:
        self._metadata = metadata
        self._records = records

    def metadata(self) -> SourceMetadata:
        return self._metadata

    def fetch(self) -> tuple[RawKnowledgeRecord, ...]:
        return self._records


class DelimitedFileSource(KnowledgeSource):
    """A generic CSV/TSV dataset adapter.

    Column names are mapped in the constructor so one class covers most
    government/statistical exports. Missing files or columns yield zero records
    rather than exceptions — a broken source must never break the platform.
    """

    def __init__(
        self,
        metadata: SourceMetadata,
        path: str | Path,
        entity_type: NodeType,
        *,
        name_column: str,
        description_column: str = "",
        aliases_column: str = "",
        code_column: str = "",
        alias_separator: str = "\n",
        delimiter: str = ",",
        encoding: str = "utf-8",
    ) -> None:
        self._metadata = metadata
        self._path = Path(path)
        self._entity_type = entity_type
        self._name_column = name_column
        self._description_column = description_column
        self._aliases_column = aliases_column
        self._code_column = code_column
        self._alias_separator = alias_separator
        self._delimiter = delimiter
        self._encoding = encoding

    def metadata(self) -> SourceMetadata:
        return self._metadata

    def fetch(self) -> tuple[RawKnowledgeRecord, ...]:
        if not self._path.is_file():
            return ()
        records: list[RawKnowledgeRecord] = []
        with self._path.open(encoding=self._encoding, newline="") as handle:
            reader = csv.DictReader(handle, delimiter=self._delimiter)
            for row in reader:
                name = (row.get(self._name_column) or "").strip()
                if not name:
                    continue
                aliases: tuple[str, ...] = ()
                if self._aliases_column:
                    raw = row.get(self._aliases_column) or ""
                    aliases = tuple(
                        a.strip() for a in raw.split(self._alias_separator) if a.strip()
                    )
                records.append(
                    RawKnowledgeRecord(
                        source_id=self._metadata.source_id,
                        entity_type=self._entity_type,
                        name=name,
                        description=(row.get(self._description_column) or "").strip()
                        if self._description_column
                        else "",
                        aliases=aliases,
                        external_code=(row.get(self._code_column) or "").strip()
                        if self._code_column
                        else "",
                    )
                )
        return tuple(records)


class ONetOccupationSource(DelimitedFileSource):
    """O*NET ``Occupation Data.txt`` (tab-delimited: SOC code, title, description)."""

    def __init__(self, metadata: SourceMetadata, path: str | Path) -> None:
        super().__init__(
            metadata,
            path,
            NodeType.CAREER,
            name_column="Title",
            description_column="Description",
            code_column="O*NET-SOC Code",
            delimiter="\t",
        )


class EscoOccupationSource(DelimitedFileSource):
    """ESCO occupations CSV export (preferredLabel, altLabels, description, conceptUri)."""

    def __init__(self, metadata: SourceMetadata, path: str | Path) -> None:
        super().__init__(
            metadata,
            path,
            NodeType.CAREER,
            name_column="preferredLabel",
            description_column="description",
            aliases_column="altLabels",
            code_column="conceptUri",
            alias_separator="\n",
            delimiter=",",
        )
