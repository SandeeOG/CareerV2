"""REST adapter (401_API_ARCHITECTURE.md §6).

The default external interface. ``envelope`` is a pure, framework-free mapping
from :class:`ServiceResult` to the standardized HTTP response shape and status
code; ``app.create_app`` builds the FastAPI application (an optional dependency).
"""

from .envelope import http_status, to_envelope

__all__ = ["to_envelope", "http_status"]
