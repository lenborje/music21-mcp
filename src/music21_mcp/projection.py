"""Bounded selection of approved properties, retaining references during expansion."""

from typing import Any

from .adapters.music21 import FIELDS, properties
from .registry import APIError, ObjectRegistry
from .serialization import encode, rational

MAX_PATHS = 32
MAX_DEPTH = 4
MAX_NODES = 4096


def selection(paths: list[str] | None) -> dict[str, Any] | None:
    if paths is None:
        return None
    if len(paths) > MAX_PATHS:
        raise APIError("invalid_selection: At most 32 property paths are allowed")
    allowed = {name for names in FIELDS.values() for name in names} | {"spannedElements"}
    tree: dict[str, Any] = {}
    for path in paths:
        components = path.split(".")
        if not 1 <= len(components) <= MAX_DEPTH or any(c not in allowed for c in components):
            raise APIError("invalid_selection: Expected 1..4 approved property names per path")
        branch = tree
        for name in components:
            branch = branch.setdefault(name, {})
    return tree


def project(obj: object, tree: dict[str, Any], registry: ObjectRegistry) -> dict[str, Any]:
    remaining = MAX_NODES

    def expand(value: Any, branch: dict[str, Any], name: str) -> Any:
        nonlocal remaining
        remaining -= 1
        if remaining < 0:
            raise APIError("projection_limit: Selection exceeds 4096 values per object")
        if not branch:
            return rational(value) if name == "quarterLength" else encode(value, registry)
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return {
                "items": [expand(v, branch, name) for v in value[:100]],
                "total": len(value),
                "truncated": len(value) > 100,
            }
        reference = encode(value, registry)
        if not isinstance(reference, dict) or "$ref" not in reference:
            raise APIError("invalid_selection: Cannot expand a scalar property")
        return {**reference, "properties": read(value, branch)}

    def read(value: object, branch: dict[str, Any]) -> dict[str, Any]:
        approved = properties(value)
        return {
            name: expand(approved[name], nested, name)
            for name, nested in branch.items()
            if name in approved
        }

    return read(obj, tree)
