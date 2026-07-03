"""SQLite adapters (404 §5 — a pure adapter swap behind existing ports).

A longitudinal discovery product cannot forget its students on restart. These
adapters persist the two aggregates whose history *is* the product — the
Student Evidence Profile and the experiment journal — as JSON documents in
SQLite (stdlib only; no new dependency). Everything derived (intelligence
profiles, affinities, rankings) is deterministic and rebuilt lazily from the
evidence profile, so nothing else needs a database.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..domain.common.identifiers import StudentId
from ..engines.discovery.engine import (
    Experiment,
    experiment_from_json,
    experiment_to_json,
)
from ..engines.student_evidence.schema import (
    StudentEvidenceProfile,
    profile_from_json,
    profile_to_json,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_profiles (
    student_id TEXT PRIMARY KEY,
    body       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_profile_history (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    body       TEXT NOT NULL,
    saved_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiments (
    id         TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    status     TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_experiments_student ON experiments (student_id);
"""


def _connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def initialize(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as con:
        con.executescript(_SCHEMA)


class SqliteEvidenceProfileRepository:
    """EvidenceProfileRepository over SQLite; append-only history preserved."""

    def __init__(self, path: str) -> None:
        self._path = path
        initialize(path)

    def save(self, student_id: StudentId, profile: StudentEvidenceProfile) -> None:
        body = json.dumps(profile_to_json(profile), ensure_ascii=False)
        stamp = profile.metadata.updated_at or profile.metadata.created_at
        with _connect(self._path) as con:
            con.execute(
                "INSERT INTO evidence_profiles (student_id, body, updated_at) "
                "VALUES (?, ?, ?) ON CONFLICT(student_id) DO UPDATE SET "
                "body = excluded.body, updated_at = excluded.updated_at",
                (student_id.value, body, stamp))
            con.execute(
                "INSERT INTO evidence_profile_history (student_id, body, saved_at) "
                "VALUES (?, ?, ?)", (student_id.value, body, stamp))

    def get(self, student_id: StudentId) -> StudentEvidenceProfile | None:
        with _connect(self._path) as con:
            row = con.execute(
                "SELECT body FROM evidence_profiles WHERE student_id = ?",
                (student_id.value,)).fetchone()
        return profile_from_json(json.loads(row[0])) if row else None

    def history(self, student_id: StudentId) -> tuple[StudentEvidenceProfile, ...]:
        with _connect(self._path) as con:
            rows = con.execute(
                "SELECT body FROM evidence_profile_history WHERE student_id = ? "
                "ORDER BY seq", (student_id.value,)).fetchall()
        return tuple(profile_from_json(json.loads(r[0])) for r in rows)

    def student_ids(self) -> tuple[str, ...]:
        with _connect(self._path) as con:
            rows = con.execute("SELECT student_id FROM evidence_profiles").fetchall()
        return tuple(r[0] for r in rows)


class SqliteExperimentRepository:
    """ExperimentRepository over SQLite."""

    def __init__(self, path: str) -> None:
        self._path = path
        initialize(path)

    def save(self, experiment: Experiment) -> None:
        body = json.dumps(experiment_to_json(experiment), ensure_ascii=False)
        with _connect(self._path) as con:
            con.execute(
                "INSERT INTO experiments (id, student_id, status, body, created_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "status = excluded.status, body = excluded.body",
                (experiment.id, experiment.student_id, experiment.status,
                 body, experiment.created_at))

    def get(self, experiment_id: str) -> Experiment | None:
        with _connect(self._path) as con:
            row = con.execute("SELECT body FROM experiments WHERE id = ?",
                              (experiment_id,)).fetchone()
        return experiment_from_json(json.loads(row[0])) if row else None

    def list_for_student(self, student_id: StudentId) -> tuple[Experiment, ...]:
        with _connect(self._path) as con:
            rows = con.execute(
                "SELECT body FROM experiments WHERE student_id = ? "
                "ORDER BY created_at", (student_id.value,)).fetchall()
        return tuple(experiment_from_json(json.loads(r[0])) for r in rows)
