import json
from enum import Enum, IntEnum
from fractions import Fraction

import pytest
from music21 import articulations, duration, expressions, note, pitch, stream

from music21_mcp.object_api import ObjectAPI
from music21_mcp.registry import APIError, ObjectRegistry
from music21_mcp.serialization import encode, rational
from music21_mcp.sessions import Document, SessionManager


def test_generic_music21_references_and_nested_reading():
    root = stream.Score()
    n = note.Note("C#4", quarterLength=Fraction(1, 3))
    n.articulations.append(articulations.Staccato())
    n.expressions.append(expressions.Fermata())
    root.insert(0, n)
    sessions = SessionManager()
    doc = Document(root, "values")
    sessions._documents[doc.id] = doc
    api = ObjectAPI(sessions)
    props = api.query(
        doc.id,
        select=[
            "pitch.accidental.name",
            "duration.tuplets.numberNotesActual",
            "duration.components.quarterLength",
            "articulations.name",
            "expressions.name",
        ],
    )["items"][0]["properties"]
    assert props["pitch"]["properties"]["accidental"]["properties"]["name"] == "sharp"
    assert (
        props["duration"]["properties"]["tuplets"]["items"][0]["properties"]["numberNotesActual"]
        == 3
    )
    assert props["duration"]["properties"]["components"]["items"][0]["quarterLength"] == rational(
        0.5
    )
    assert props["articulations"]["items"][0]["properties"]["name"] == "staccato"
    assert props["expressions"]["items"][0]["properties"]["name"] == "fermata"
    for obj in (
        pitch.Accidental("sharp"),
        duration.Tuplet(),
        articulations.Accent(),
        expressions.Fermata(),
    ):
        ref = encode(obj, doc.registry)
        assert ref == {"$ref": doc.registry.register(obj)}
        assert api.get(doc.id, ref["$ref"])["properties"]
        assert (
            api.schema(doc.id, ref["$ref"])["type"]
            == f"{type(obj).__module__}.{type(obj).__name__}"
        )


def test_mapping_enums_and_namedtuple_values():
    class Number(IntEnum):
        ONE = 1

    class Text(Enum):
        WORD = "hello"

    registry = ObjectRegistry()
    data = encode({"n": Number.ONE, "text": Text.WORD, "ratio": Fraction(1, 7)}, registry)
    assert data == {
        "entries": {"n": 1, "text": "hello", "ratio": rational(Fraction(1, 7))},
        "total": 3,
        "truncated": False,
    }
    assert encode(duration.DurationTuple("quarter", 0, 1.0), registry) == {
        "type": "quarter",
        "dots": 0,
        "quarterLength": rational(1),
    }
    assert encode({str(i): i for i in range(101)}, registry)["truncated"]
    assert len(encode(list(range(101)), registry)["items"]) == 100
    json.dumps(data, allow_nan=False)


def test_unsupported_nonfinite_and_cyclic_values_are_bounded():
    registry = ObjectRegistry()
    cycle = []
    cycle.append(cycle)
    mapping = {}
    mapping["cycle"] = mapping
    for value in (object(), float("nan"), float("inf"), {1: "key"}, cycle, mapping):
        with pytest.raises(APIError, match="unsupported_value"):
            encode(value, registry)
