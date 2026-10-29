"""Bounded JSON values and explicit references to music21's common object base."""

import math
from enum import Enum
from fractions import Fraction
from itertools import islice
from typing import Any

from music21 import duration, prebase

from .registry import APIError, ObjectRegistry

MAX_DEPTH = 4
MAX_ITEMS = 100


def rational(value: float | Fraction) -> dict[str, int]:
    try:
        f = Fraction(value)
    except (TypeError, ValueError, OverflowError):
        raise APIError("unsupported_value: Expected a finite rational value") from None
    return {"numerator": f.numerator, "denominator": f.denominator}


def encode(value: Any, registry: ObjectRegistry, depth: int = 0) -> Any:
    # Enums before str/int: IntEnum and StrEnum otherwise bypass value conversion.
    if isinstance(value, Enum):
        if depth >= MAX_DEPTH:
            raise APIError("unsupported_value: Serialization depth exceeded")
        return encode(value.value, registry, depth + 1)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Fraction):
        return rational(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise APIError("unsupported_value: Non-finite number")
        return value
    if isinstance(value, prebase.ProtoM21Object):
        return {"$ref": registry.register(value)}
    if depth >= MAX_DEPTH:
        raise APIError("unsupported_value: Serialization depth exceeded")
    if isinstance(value, duration.DurationTuple):
        return {
            "type": value.type,
            "dots": value.dots,
            "quarterLength": rational(value.quarterLength),
        }
    if isinstance(value, (tuple, list)):
        return {
            "items": [encode(v, registry, depth + 1) for v in value[:MAX_ITEMS]],
            "total": len(value),
            "truncated": len(value) > MAX_ITEMS,
        }
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise APIError("unsupported_value: Mapping keys must be strings")
        return {
            "entries": {
                k: encode(v, registry, depth + 1) for k, v in islice(value.items(), MAX_ITEMS)
            },
            "total": len(value),
            "truncated": len(value) > MAX_ITEMS,
        }
    raise APIError("unsupported_value: Value is outside the supported read model")
