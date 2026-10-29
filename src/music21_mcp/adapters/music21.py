"""Explicit read surface; never resolve client-provided Python attributes."""

from collections.abc import Iterator
from typing import Any

from music21 import (
    base,
    chord,
    clef,
    duration,
    expressions,
    instrument,
    key,
    metadata,
    meter,
    note,
    pitch,
    spanner,
    stream,
    tempo,
    tie,
)

from ..registry import APIError

# Each entry is an independently reviewed set of non-contextual read properties.
FIELDS: dict[type, tuple[str, ...]] = {
    base.Music21Object: (),
    stream.Stream: (),
    stream.Score: (),
    stream.Part: ("partName", "partAbbreviation"),
    stream.Measure: ("number", "numberSuffix"),
    stream.Voice: (),
    note.GeneralNote: ("duration", "quarterLength", "lyrics"),
    note.NotRest: ("tie",),
    note.Note: ("pitch", "nameWithOctave"),
    note.Rest: ("fullMeasure",),
    chord.Chord: ("pitches", "notes"),
    pitch.Pitch: ("name", "nameWithOctave", "step", "octave", "alter", "midi"),
    duration.Duration: ("quarterLength", "type", "dots"),
    note.Lyric: ("text", "number", "syllabic", "identifier"),
    tie.Tie: ("type", "style", "placement"),
    meter.TimeSignature: ("ratioString",),
    key.KeySignature: ("sharps",),
    clef.Clef: ("sign", "line", "octaveChange"),
    instrument.Instrument: ("instrumentName", "partName", "partAbbreviation"),
    metadata.Metadata: ("title", "composer", "movementName"),
    expressions.TextExpression: ("content",),
    tempo.MetronomeMark: ("text", "number"),
    spanner.Spanner: (),
}
TYPES = {cls.__name__: cls for cls in FIELDS}


def fields(obj: object) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            field for cls, names in FIELDS.items() if isinstance(obj, cls) for field in names
        )
    )


def properties(obj: object) -> dict[str, Any]:
    result = {name: getattr(obj, name) for name in fields(obj)}
    if isinstance(obj, spanner.Spanner):
        result["spannedElements"] = obj.getSpannedElements()
    return result


def walk(root: object) -> Iterator[tuple[stream.Stream, base.Music21Object, Any]]:
    """Yield containment edges without touching activeSite; bound graph traversal."""
    if not isinstance(root, stream.Stream):
        return
    stack = [(root, iter(root.elements), frozenset({id(root)}))]
    count = 0
    while stack:
        parent, children, ancestors = stack[-1]
        child = next(children, None)
        if child is None:
            stack.pop()
            continue
        count += 1
        if count > 100_000:
            raise APIError("traversal_limit: Document traversal exceeds 100000 occurrences")
        yield parent, child, parent.elementOffset(child)
        if isinstance(child, stream.Stream) and id(child) not in ancestors:
            if len(stack) >= 128:
                raise APIError("traversal_limit: Document nesting exceeds 128")
            stack.append((child, iter(child.elements), ancestors | {id(child)}))
