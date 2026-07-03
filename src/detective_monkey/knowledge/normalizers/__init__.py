"""Normalization: canonical names, aliases and cross-source entity merging."""

from .canonicalizer import AliasTable, Canonicalizer, EntityMerger
from .text import jaccard, normalize_name, slugify, tokens

__all__ = [
    "AliasTable",
    "Canonicalizer",
    "EntityMerger",
    "jaccard",
    "normalize_name",
    "slugify",
    "tokens",
]
