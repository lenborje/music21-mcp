import json
from fractions import Fraction

import pytest
from music21 import note, pitch, stream, tie

from music21_mcp.adapters.music21 import TYPES, readable_names
from music21_mcp.introspection import describe, discover, schema
from music21_mcp.object_api import ObjectAPI
from music21_mcp.pagination import json_size
from music21_mcp.registry import APIError
from music21_mcp.sessions import Document, SessionManager


def test_schema_discovers_inherited_properties_docs_slots_and_signatures():
    members = discover(note.Note, note.Note())
    pitch_info = describe(members["pitch"], note.Note)
    assert pitch_info["readable"]
    assert pitch_info["stored_type"] == "music21.pitch.Pitch"
    assert "Pitch" in pitch_info["doc"]["text"]
    length = describe(members["quarterLength"], note.Note)
    assert length["defined_on"] == "music21.base.Music21Object"
    assert length["type_hint"] == "OffsetQL"
    assert length["wire_format"] == "rational"
    transpose = describe(members["transpose"], note.Note)
    assert not transpose["callable"]
    assert transpose["signature"] == "(value, *, inPlace = False)"
    assert transpose["parameters"][1]["kind"] == "KEYWORD_ONLY"
    assert transpose["parameters"][1]["default"] == {"value": False}
    assert transpose["doc"]["text"]
    assert describe(discover(tie.Tie)["type"], tie.Tie)["source"] == "slot"
    # Forward refs survive as strings. No imports/evaluation are needed.
    method = describe(discover(pitch.Pitch)["transpose"], pitch.Pitch)
    assert "IntervalBase" in method["parameters"][0]["type_hint"]
    assert method["return_type"] == "t.Self | None"


def test_discovery_never_runs_getters_dir_methods_or_repr():
    calls = []

    class BadDefault:
        def __repr__(self):
            raise AssertionError("repr executed")

    class PassiveNote(note.Note):
        public_dynamic = "visible metadata"
        hidden_value: "explode()"

        def __dir__(self):
            raise AssertionError("dir executed")

        @property
        def explode(self):
            calls.append("getter")
            raise RuntimeError("private data")

        def method(self, value: "explode()" = BadDefault(), *, flag=False) -> "explode()":
            calls.append("method")

    obj = PassiveNote()
    obj.new_field = 3
    result = schema(PassiveNote, obj, limit=100)
    members = {m["name"]: m for m in result["items"]}
    assert not members["explode"]["readable"]
    assert members["method"]["parameters"][0]["type_hint"] == "explode()"
    assert "value" not in members["method"]["parameters"][0]["default"]
    assert members["new_field"]["stored_type"] == "builtins.int"
    assert members["hidden_value"]["type_hint"] == "explode()"
    assert calls == []
    assert all(not n.startswith("_") for n in members)
    json.dumps(result)


def test_schema_does_not_change_sites_or_register_objects():
    root = stream.Score()
    a, b = stream.Part(), stream.Part()
    n = note.Note("C#4", quarterLength=Fraction(1, 3))
    a.insert(Fraction(1, 3), n)
    b.insert(2, n)
    root.insert(0, a)
    root.insert(4, b)
    sessions = SessionManager()
    doc = Document(root, "shared")
    sessions._documents[doc.id] = doc
    api = ObjectAPI(sessions)
    handle = doc.registry.register(n)
    before = n.activeSite
    identities = dict(doc.registry._identities)
    result = api.schema(doc.id, handle)
    assert result["read_only"]
    assert n.activeSite is before
    assert n.getOffsetBySite(a) == Fraction(1, 3)
    assert n.getOffsetBySite(b) == 2
    assert doc.registry._identities == identities


def test_schema_catalog_validation_pagination_and_bounds():
    api = ObjectAPI(SessionManager())
    full = api.schema(limit=100)
    assert {i["name"] for i in full["items"]} == set(TYPES)
    assert api.schema(type_name="music21.note.Note")["type"] == "music21.note.Note"
    parts = []
    offset = 0
    while True:
        result = api.schema(offset=offset, limit=100, max_bytes=1024)
        assert json_size(result) <= 1024
        parts.extend(result["items"])
        offset = result["next_offset"]
        if offset is None:
            break
    assert parts == full["items"]
    all_members = []
    offset = 0
    while True:
        result = api.schema(type_name="Score", offset=offset, max_bytes=8192, limit=100)
        assert json_size(result) <= 8192
        all_members.extend(result["items"])
        offset = result["next_offset"]
        if offset is None:
            break
    assert len(all_members) == result["total"]
    assert len({m["name"] for m in all_members}) == len(all_members)
    assert all(not m["writable"] and not m["callable"] for m in all_members)
    assert api.schema(type_name="Score", offset=999)["items"] == []
    for kwargs in (
        {"object_id": "missing"},
        {"document_id": "missing"},
        {"type_name": "os.system"},
        {"type_name": "__class__"},
        {"kind": "method"},
        {"type_name": "Note", "kind": "private"},
        {"limit": 101},
        {"max_bytes": 100},
    ):
        with pytest.raises(APIError):
            api.schema(**kwargs)


def test_all_reviewed_fields_are_discoverable_and_match_read_policy():
    # No class constructors or getters are needed to discover the declared read surface.
    for cls in TYPES.values():
        members = discover(cls)
        assert set(readable_names(cls)) <= set(members)
        assert {
            name for name, member in members.items() if describe(member, cls)["readable"]
        } == set(readable_names(cls))
        json.dumps(schema(cls))


def test_doc_truncation_and_unannotated_values():
    class Described(note.Note):
        @property
        def long_doc(self):
            raise AssertionError

    Described.long_doc.__doc__ = "A" * 10000
    data = describe(discover(Described)["long_doc"], Described)
    assert len(data["doc"]["text"]) == 1200
    assert data["doc"]["truncated"]
    assert data["type_hint"] is None
    with pytest.raises(APIError, match="result_too_large"):
        schema(Described, max_bytes=1024)


def test_method_parameter_kinds_and_defaults():
    class Signatures:
        @staticmethod
        def static(value: int, /, *args: str, flag=True, **kwargs) -> str:
            raise AssertionError

        @classmethod
        def class_method(cls, value=None):
            raise AssertionError

    methods = discover(Signatures)
    data = describe(methods["static"], Signatures)
    assert [p["kind"] for p in data["parameters"]] == [
        "POSITIONAL_ONLY",
        "VAR_POSITIONAL",
        "KEYWORD_ONLY",
        "VAR_KEYWORD",
    ]
    assert "/" in data["signature"]
    assert data["parameters"][0]["type_hint"] == "int"
    assert [p["name"] for p in describe(methods["class_method"], Signatures)["parameters"]] == [
        "value"
    ]


def test_no_access_granted_to_discovered_fields():
    api = ObjectAPI(SessionManager())
    candidates = {m["name"]: m for m in api.schema(type_name="Note", limit=100)["items"]}
    assert "offset" in candidates and not candidates["offset"]["readable"]
    assert "write" in candidates and not candidates["write"]["callable"]
    from music21_mcp.projection import selection

    with pytest.raises(APIError, match="invalid_selection"):
        selection(["offset"])


def test_non_string_annotations_are_rendered_without_evaluation():
    class Annotated:
        @property
        def values(self) -> list[note.Note] | None:
            raise AssertionError

    data = describe(discover(Annotated)["values"], Annotated)
    assert "list" in data["type_hint"] and "Note" in data["type_hint"]
    assert "None" in data["type_hint"]


def test_deferred_annotation_expressions_are_not_executed_by_schema():
    calls = []

    def evaluate_type():
        calls.append("annotation evaluated")
        return int

    class Deferred:
        field: evaluate_type()

        def method(this, value: evaluate_type()) -> evaluate_type():
            raise AssertionError

    # 3.12 evaluates these at definition time; 3.14 defers them. Neither
    # version may evaluate any of them while building a schema.
    calls.clear()
    members = discover(Deferred)
    data = describe(members["method"], Deferred)
    assert [p["name"] for p in data["parameters"]] == ["value"]
    assert calls == []
