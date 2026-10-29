"""Bounded JSON values and explicit object references."""

import math
from fractions import Fraction
from typing import Any

from music21 import base, duration, note, pitch, tie

from .registry import APIError, ObjectRegistry


def rational(value: float | Fraction) -> dict[str, int]:
    f = Fraction(value)
    return {"numerator": f.numerator, "denominator": f.denominator}


def encode(value: Any, registry: ObjectRegistry, depth: int = 0) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Fraction):
        return rational(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise APIError("unsupported_value: Non-finite number")
        return value
    if isinstance(value, (base.Music21Object, duration.Duration, note.Lyric, pitch.Pitch, tie.Tie)):
        return {"$ref": registry.register(value)}
    if isinstance(value, (tuple, list)) and depth < 4:
        return {
            "items": [encode(v, registry, depth + 1) for v in value[:100]],
            "total": len(value),
            "truncated": len(value) > 100,
        }
    raise APIError("unsupported_value: Value is outside the supported read model")
