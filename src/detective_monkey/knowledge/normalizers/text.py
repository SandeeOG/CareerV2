"""Deterministic text normalization utilities.

These are the shared primitives of canonicalization: a stable slug (used to
derive node ids), token extraction, and Jaccard similarity for fuzzy matching
of near-duplicate names. All pure functions — same input, same output, always.
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_name(name: str) -> str:
    """Collapse whitespace; keep the original casing for display."""
    return " ".join(name.split())


def slugify(name: str) -> str:
    """A stable, lowercase, hyphen-separated identifier fragment."""
    return "-".join(_TOKEN_RE.findall(name.lower()))


def tokens(text: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(text.lower()))


def jaccard(a: str, b: str) -> float:
    """Token-set similarity in [0, 1]; 1.0 means identical token sets."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
