"""Evidence — the first canonical intelligence object.

Evidence is the ground truth from which all intelligence is derived
(11 §8, 18 §4 Layer 1, 18 §6). Every derived feature, score and recommendation
must be traceable back to evidence (00 §8, 11 §13 INV-03).

Invariant: **Evidence is immutable** (18 §23 INV-01, 13 §11). New observations
create new evidence; existing evidence is never edited.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .attributes import Attributes
from .confidence import Confidence
from .identifiers import EvidenceId
from .provenance import Provenance


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Evidence:
    """An immutable, traceable fact about a subject.

    ``subject`` is an opaque reference to what the evidence concerns (for
    example a skill slug, a construct name, or a career identifier). The domain
    keeps it opaque so evidence can describe anything without coupling to a
    specific entity type.
    """

    id: EvidenceId
    subject: str
    provenance: Provenance
    confidence: Confidence
    summary: str = ""
    observed_at: datetime = field(default_factory=_utcnow)
    metadata: Attributes = field(default_factory=Attributes)

    def __post_init__(self) -> None:
        if not self.subject or not self.subject.strip():
            raise ValueError("Evidence.subject must be a non-empty string")
