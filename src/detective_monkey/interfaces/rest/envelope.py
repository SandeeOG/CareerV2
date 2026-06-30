"""Standardized response envelope (401_API_ARCHITECTURE.md §12, §18).

Pure functions mapping a transport-independent :class:`ServiceResult` to the HTTP
response body and status code. No framework dependency, so this is unit-testable
on its own.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from ...application.dto import ErrorCode, ServiceResult

# Error code -> HTTP status (401 §18).
_STATUS = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INTERNAL_ERROR: 500,
}


def _serialize(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _serialize(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    return value


def to_envelope(result: ServiceResult) -> dict:
    """Map a service result to the canonical envelope (401 §12)."""
    return {
        "success": result.success,
        "data": _serialize(result.data) if result.data is not None else None,
        "metadata": dict(result.metadata),
        "warnings": list(result.warnings),
        "errors": [
            {"code": e.code.value, "message": e.message} for e in result.errors
        ],
    }


def http_status(result: ServiceResult) -> int:
    if result.success:
        return 200
    if result.errors:
        return _STATUS.get(result.errors[0].code, 500)
    return 500
