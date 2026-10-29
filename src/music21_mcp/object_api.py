"""Read-only navigation independent of MCP transport."""

import json
from fractions import Fraction
from typing import Any

from music21 import stream

from .adapters.music21 import TYPES, properties, walk
from .projection import project, selection
from .registry import APIError
from .serialization import encode, rational
from .sessions import Document, SessionManager


def page(items: list[Any], offset: int, limit: int) -> dict[str, Any]:
    if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
        raise APIError("invalid_pagination: offset >= 0 and 1 <= limit <= 100 required")
    end = offset + limit
    return {
        "items": items[offset:end],
        "total": len(items),
        "next_offset": end if end < len(items) else None,
    }


def numeric(value: Any) -> Fraction:
    try:
        if isinstance(value, dict) and set(value) == {"numerator", "denominator"}:
            if any(type(v) is not int for v in value.values()):
                raise ValueError
            return Fraction(value["numerator"], value["denominator"])
        if isinstance(value, bool) or not isinstance(value, (int, float, Fraction)):
            raise ValueError
        return Fraction(value)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError):
        raise APIError("invalid_filter: Expected a finite number or rational value") from None


class ObjectAPI:
    def __init__(self, sessions: SessionManager) -> None:
        self.sessions = sessions

    @staticmethod
    def edge(doc: Document, parent: stream.Stream, child: object, offset: Any) -> dict[str, Any]:
        return {
            "id": doc.registry.register(child),
            "type": f"{type(child).__module__}.{type(child).__name__}",
            "parent": {"$ref": doc.registry.register(parent)},
            "offset": rational(offset),
        }

    def get(self, document_id: str, object_id: str) -> dict[str, Any]:
        doc = self.sessions.get(document_id)
        obj = doc.registry.get(object_id)
        values = properties(obj)
        positions: list[dict[str, Any]] = []
        parents: set[int] = set()
        for parent, child, position in walk(doc.root):
            if child is obj and id(parent) not in parents:
                parents.add(id(parent))
                if len(positions) < 100:
                    positions.append(self.edge(doc, parent, child, position))
        return {
            "id": object_id,
            "type": f"{type(obj).__module__}.{type(obj).__name__}",
            "properties": {
                k: rational(v) if k == "quarterLength" else encode(v, doc.registry)
                for k, v in values.items()
            },
            "positions": {
                "items": positions,
                "total": len(parents),
                "truncated": len(parents) > 100,
            },
        }

    def children(
        self, document_id: str, object_id: str, offset: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        page([], offset, limit)
        doc = self.sessions.get(document_id)
        obj = doc.registry.get(object_id)
        if not isinstance(obj, stream.Stream):
            return page([], offset, limit)
        children = obj.elements
        # Register only the requested page.
        result = [
            self.edge(doc, obj, c, obj.elementOffset(c)) for c in children[offset : offset + limit]
        ]
        return {
            "items": result,
            "total": len(children),
            "next_offset": offset + limit if offset + limit < len(children) else None,
        }

    def query(
        self,
        document_id: str,
        object_id: str | None = None,
        type_name: str | None = None,
        filters: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int = 50,
        select: list[str] | None = None,
        max_bytes: int = 262_144,
    ) -> dict[str, Any]:
        page([], offset, limit)
        tree = selection(select)
        if type(max_bytes) is not int or not 1024 <= max_bytes <= 262_144:
            raise APIError("invalid_pagination: max_bytes must be between 1024 and 262144")
        doc = self.sessions.get(document_id)
        root = doc.root if object_id is None else doc.registry.get(object_id)
        if type_name is not None and type_name not in TYPES:
            raise APIError("invalid_type: Unsupported type name")
        # Scalar filters only. Never evaluate attribute paths or access arbitrary attributes.
        allowed = {
            "nameWithOctave",
            "quarterLength",
            "number",
            "partName",
            "text",
            "step",
            "octave",
            "type",
            "ratioString",
            "sharps",
            "content",
        }
        filters = filters or {}
        if not set(filters) <= allowed:
            raise APIError("invalid_filter: Unsupported property")
        for name, value in filters.items():
            if name == "quarterLength":
                numeric(value)
            elif value is not None and not isinstance(value, (str, int, float, bool)):
                raise APIError("invalid_filter: Expected a scalar value")
        matches: list[dict[str, Any]] = []
        total = 0
        used_bytes = 128  # Reserve the result envelope, total and next_offset.
        full = False
        for parent, child, position in walk(root):
            if type_name is not None and not isinstance(child, TYPES[type_name]):
                continue
            values = properties(child) if filters else {}
            if any(
                name not in values
                or (
                    numeric(values[name]) != numeric(value)
                    if name == "quarterLength"
                    else values[name] != value
                )
                for name, value in filters.items()
            ):
                continue
            if total >= offset and len(matches) < limit and not full:
                item = self.edge(doc, parent, child, position)
                if tree is not None:
                    item["properties"] = project(child, tree, doc.registry)
                size = len(json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode()) + 1
                if used_bytes + size > max_bytes:
                    if not matches:
                        raise APIError(
                            "result_too_large: One result exceeds max_bytes; "
                            "select fewer properties"
                        )
                    full = True
                else:
                    matches.append(item)
                    used_bytes += size
            total += 1
        return {
            "items": matches,
            "total": total,
            "next_offset": offset + len(matches) if offset + len(matches) < total else None,
        }
