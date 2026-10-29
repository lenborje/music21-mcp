"""Shared bounds for compact JSON responses."""

import json
from typing import Any

from .registry import APIError


def json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def validate_bytes(max_bytes: int) -> None:
    if type(max_bytes) is not int or not 1024 <= max_bytes <= 262_144:
        raise APIError("invalid_pagination: max_bytes must be between 1024 and 262144")


def page(items: list[Any], offset: int, limit: int) -> dict[str, Any]:
    if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
        raise APIError("invalid_pagination: offset >= 0 and 1 <= limit <= 100 required")
    end = offset + limit
    return {
        "items": items[offset:end],
        "total": len(items),
        "next_offset": end if end < len(items) else None,
    }
