from fractions import Fraction
from pathlib import Path

import pytest
from music21 import chord, note, spanner, stream

from music21_mcp.object_api import ObjectAPI
from music21_mcp.registry import APIError, ObjectRegistry
from music21_mcp.serialization import encode, rational
from music21_mcp.sessions import Document, SessionManager

SCORE = Path(__file__).resolve().parents[1] / "examples/scores/prototype.musicxml"


@pytest.fixture
def opened():
    sessions = SessionManager()
    doc = sessions.open(str(SCORE))
    return sessions, ObjectAPI(sessions), doc


def test_milestone(opened):
    sessions, api, doc = opened
    did = doc["document_id"]
    parts = api.query(did, type_name="Part")["items"]
    assert len(parts) == 1
    measures = api.query(did, parts[0]["id"], "Measure")["items"]
    assert len(measures) == 2
    notes = api.query(did, measures[0]["id"], "Note")["items"]
    first = api.get(did, notes[0]["id"])
    assert first["properties"]["nameWithOctave"] == "C4"
    assert first["properties"]["quarterLength"] == rational(Fraction(1, 3))
    assert notes[1]["offset"] == rational(Fraction(1, 3))
    pitch = api.get(did, first["properties"]["pitch"]["$ref"])
    assert pitch["properties"]["nameWithOctave"] == "C4"
    lyric = first["properties"]["lyrics"]["items"][0]["$ref"]
    assert api.get(did, lyric)["properties"]["text"] == "Hej"
    assert (
        api.query(did, type_name="Note", filters={"nameWithOctave": "C4"})["items"][0]["id"]
        == first["id"]
    )
    assert api.query(did, filters={"quarterLength": rational(Fraction(1, 3))})["total"] == 1
    assert api.children(did, doc["root"])["total"] >= 1
    assert sessions.list() == [doc]
    sessions.close(did)
    with pytest.raises(APIError, match="unknown_document"):
        api.get(did, first["id"])


def test_shared_objects_and_voices(opened):
    sessions, api, _ = opened
    score = stream.Score()
    part = stream.Part()
    m1, m2 = stream.Measure(number=1), stream.Measure(number=2)
    voice = stream.Voice()
    shared = note.Note("F#4")
    voice.insert(Fraction(1, 3), shared)
    m1.insert(0, voice)
    m2.insert(2, shared)
    part.append([m1, m2])
    score.insert(0, part)
    doc = Document(score, "shared")
    sessions._documents[doc.id] = doc
    before = shared.activeSite
    result = api.query(doc.id, type_name="Note")
    assert result["total"] == 2
    assert result["items"][0]["id"] == result["items"][1]["id"]
    assert [x["offset"] for x in result["items"]] == [rational(Fraction(1, 3)), rational(2)]
    assert api.get(doc.id, result["items"][0]["id"])["positions"]["total"] == 2
    assert shared.activeSite is before


def test_pagination_validation_and_isolation(opened):
    sessions, api, doc = opened
    did = doc["document_id"]
    all_notes = api.query(did, type_name="Note")
    pages = [
        api.query(did, type_name="Note", offset=i, limit=1)["items"][0]
        for i in range(all_notes["total"])
    ]
    assert pages == all_notes["items"]
    assert api.query(did, offset=999)["items"] == []
    for kwargs in (
        {"limit": 101},
        {"offset": -1},
        {"type_name": "__class__"},
        {"filters": {"__dict__": 1}},
        {"filters": {"quarterLength": {"numerator": 1, "denominator": 0}}},
    ):
        with pytest.raises(APIError):
            api.query(did, **kwargs)
    other = sessions.open(str(SCORE))
    with pytest.raises(APIError, match="unknown_object"):
        api.get(other["document_id"], all_notes["items"][0]["id"])


def test_registry_and_relation_serialization(opened):
    registry = ObjectRegistry()
    a, b = note.Note("C4"), note.Note("C4")
    assert registry.register(a) == registry.register(a)
    assert registry.register(a) != registry.register(b)
    sessions, api, doc = opened
    document = sessions.get(doc["document_id"])
    slur = spanner.Slur(a, b)
    handle = document.registry.register(slur)
    refs = api.get(document.id, handle)["properties"]["spannedElements"]["items"]
    assert refs[0]["$ref"] == document.registry.register(a)
    c = chord.Chord(["C4", "E4"])
    data = api.get(document.id, document.registry.register(c))
    assert len(data["properties"]["pitches"]["items"]) == 2
    assert encode(list(range(101)), registry)["truncated"] is True
    assert rational(Fraction(1, 7)) == {"numerator": 1, "denominator": 7}


def test_import_errors(tmp_path):
    sessions = SessionManager()
    for path in ("https://example.org/test.xml", str(tmp_path), "missing.musicxml"):
        with pytest.raises(APIError):
            sessions.open(path)
    broken = tmp_path / "broken.xml"
    broken.write_text("<invalid>")
    with pytest.raises(APIError, match="parse_error"):
        sessions.open(str(broken))
    assert sessions.list() == []


def test_children_pagination_and_duration_reference(opened):
    _, api, doc = opened
    did = doc["document_id"]
    first_page = api.children(did, doc["root"], limit=1)
    assert first_page["next_offset"] == 1
    next_page = api.children(did, doc["root"], offset=1, limit=1)
    assert first_page["items"][0]["id"] != next_page["items"][0]["id"]
    first = api.query(did, type_name="Note")["items"][0]["id"]
    duration_id = api.get(did, first)["properties"]["duration"]["$ref"]
    assert api.get(did, duration_id)["properties"]["quarterLength"] == rational(Fraction(1, 3))
    assert api.children(did, duration_id)["items"] == []


def test_compressed_musicxml(tmp_path):
    from zipfile import ZipFile

    path = tmp_path / "score.mxl"
    with ZipFile(path, "w") as archive:
        archive.writestr("score.musicxml", SCORE.read_bytes())
        archive.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container><rootfiles><rootfile full-path="score.musicxml"/></rootfiles></container>""",
        )
    sessions = SessionManager()
    doc = sessions.open(str(path))
    assert ObjectAPI(sessions).query(doc["document_id"], type_name="Note")["total"] == 3


def test_traversal_depth_limit():
    from music21_mcp.adapters.music21 import walk

    root = stream.Stream()
    parent = root
    for _ in range(130):
        child = stream.Stream()
        parent.insert(0, child)
        parent = child
    with pytest.raises(APIError, match="traversal_limit"):
        list(walk(root))


def test_unexpected_errors_are_sanitized():
    from music21_mcp.server import safe

    @safe
    def broken():
        raise RuntimeError("private Python details")

    with pytest.raises(APIError, match="^internal_error: Unable to complete read operation$"):
        broken()
