"""Explanation domain (10_DOMAIN_MODEL.md §12).

The boundary where the AI layer turns deterministic recommendations into
human-readable understanding, without ever changing the recommendation.
"""

from .explanation import Explanation

__all__ = ["Explanation"]
