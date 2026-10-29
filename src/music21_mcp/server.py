"""MCP stdio bindings for the read-only document API."""

from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .object_api import ObjectAPI
from .registry import APIError
from .sessions import SessionManager

P = ParamSpec("P")
R = TypeVar("R")


def safe(function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return function(*args, **kwargs)
        except APIError:
            raise
        except Exception:
            raise APIError("internal_error: Unable to complete read operation") from None

    return wrapped


def create_server() -> FastMCP:
    mcp = FastMCP("music21-mcp")
    sessions = SessionManager()
    objects = ObjectAPI(sessions)
    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=False, openWorldHint=False))
    @safe
    def document_open(path: str) -> dict[str, str]:
        """Open an explicit local .musicxml/.xml/.mxl file; return document_id and root handle."""
        return sessions.open(path)

    @mcp.tool(annotations=read)
    @safe
    def document_list() -> list[dict[str, str]]:
        """List documents held in memory by this server process."""
        return sessions.list()

    @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, openWorldHint=False))
    @safe
    def document_close(document_id: str) -> dict[str, bool]:
        """Release an in-memory document and invalidate all its object handles."""
        return sessions.close(document_id)

    @mcp.tool(annotations=read)
    @safe
    def object_get(document_id: str, object_id: str) -> dict[str, Any]:
        """Read approved properties and direct Stream positions. Follow $ref via object_get.

        Durations and offsets are exact {numerator, denominator} quarter-note units.
        Collections have items/total/truncated; positions are capped at 100.
        """
        return objects.get(document_id, object_id)

    @mcp.tool(annotations=read)
    @safe
    def object_children(
        document_id: str, object_id: str, offset: int = 0, limit: int = 50
    ) -> dict[str, Any]:
        """Page direct Stream children, including Voice containers and notation objects.

        Each item has id/type/parent/offset. Offset is relative to that parent.
        Use object_query to find notes nested in Voices. limit is 1..100.
        """
        return objects.children(document_id, object_id, offset, limit)

    @mcp.tool(annotations=read)
    @safe
    def object_query(
        document_id: str,
        object_id: str | None = None,
        type_name: str | None = None,
        filters: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Search descendants of object_id (default document root), excluding the root.

        Type names: Music21Object, Stream, Score, Part, Measure, Voice, GeneralNote,
        NotRest, Note, Rest, Chord, TimeSignature, KeySignature, Clef, Instrument,
        Metadata, TextExpression, MetronomeMark, Spanner. Subclasses match too.
        Filters are AND equality on nameWithOctave, quarterLength, number, partName,
        text, step, octave, type, ratioString, sharps, content. Missing fields do not
        match. quarterLength accepts a number or {numerator, denominator}.
        Results are containment occurrences with stable IDs; shared objects may
        appear multiple times. limit is 1..100; next_offset continues pagination.
        """
        return objects.query(document_id, object_id, type_name, filters, offset, limit)

    return mcp


def main() -> None:
    create_server().run(transport="stdio")
