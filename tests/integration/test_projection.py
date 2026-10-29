"""Compare projected MCP responses to independent object_get reference traversal."""

import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from music21 import chord, note, spanner, stream, tie


@pytest.fixture
def score_path(tmp_path):
    score = stream.Score()
    part = stream.Part()
    measure = stream.Measure(number=7)
    voice = stream.Voice()
    first = note.Note("F#4", quarterLength=1 / 3)
    first.addLyric("Héj")
    first.tie = tie.Tie("start")
    second = note.Note("F#4", quarterLength=2 / 3)
    second.tie = tie.Tie("stop")
    voice.insert(0, first)
    voice.insert(1 / 3, second)
    voice.insert(1, chord.Chord(["C4", "E4", "G4"]))
    voice.insert(2, note.Rest(quarterLength=2))
    measure.insert(0, voice)
    part.insert(0, measure)
    part.insert(0, spanner.Slur(first, second))
    score.insert(0, part)
    path = tmp_path / "projection.musicxml"
    score.write("musicxml", fp=path)
    return path


async def test_projection_matches_object_get(score_path):
    async with stdio_client(
        StdioServerParameters(command=sys.executable, args=["-m", "music21_mcp"])
    ) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(tool, **args):
                result = await client.call_tool(tool, args)
                assert not result.isError, result.content
                return result.structuredContent

            doc = await call("document_open", path=str(score_path))
            did = doc["document_id"]

            async def get(object_id):
                return await call("object_get", document_id=did, object_id=object_id)

            async def resolve(value, names):
                # Independently follow only object_get responses, including collection metadata.
                if not names or value is None:
                    return value
                if "items" in value:
                    return {**value, "items": [await resolve(v, names) for v in value["items"]]}
                data = await get(value["$ref"])
                name, *tail = names
                props = data["properties"]
                selected = {name: await resolve(props[name], tail)} if name in props else {}
                return {"$ref": value["$ref"], "properties": selected}

            paths = [
                "quarterLength",
                "pitch.nameWithOctave",
                "duration.quarterLength",
                "lyrics.text",
                "tie.type",
                "pitches.midi",
                "notes.pitch.nameWithOctave",
            ]
            plain = await call("object_query", document_id=did, type_name="GeneralNote")
            combined = await call(
                "object_query", document_id=did, type_name="GeneralNote", select=paths
            )
            assert len(combined["items"]) == 4
            for edge, item in zip(plain["items"], combined["items"], strict=True):
                assert {k: item[k] for k in edge} == edge
                direct = await get(edge["id"])
                expected = {}
                for path in paths:
                    first, *tail = path.split(".")
                    if first in direct["properties"]:
                        expected[first] = await resolve(direct["properties"][first], tail)
                assert item["properties"] == expected
                assert any(
                    p["parent"] == item["parent"] and p["offset"] == item["offset"]
                    for p in direct["positions"]["items"]
                )

            # Direct refs and overlapping paths retain the very same object IDs.
            overlap = await call(
                "object_query",
                document_id=did,
                type_name="Note",
                select=["pitch", "pitch.nameWithOctave", "pitch.midi"],
            )
            for item in overlap["items"]:
                direct = await get(item["id"])
                pitch_id = direct["properties"]["pitch"]["$ref"]
                assert item["properties"]["pitch"]["$ref"] == pitch_id
                pitch_props = (await get(pitch_id))["properties"]
                assert item["properties"]["pitch"]["properties"] == {
                    k: pitch_props[k] for k in ("nameWithOctave", "midi")
                }

            slurs = await call(
                "object_query",
                document_id=did,
                type_name="Spanner",
                select=["spannedElements.pitch.nameWithOctave"],
            )
            for item in slurs["items"]:
                direct = await get(item["id"])
                expected = await resolve(
                    direct["properties"]["spannedElements"], ["pitch", "nameWithOctave"]
                )
                assert item["properties"]["spannedElements"] == expected

            # Page all occurrences; byte-limited pages have no gaps or duplicate IDs.
            items = []
            offset = 0
            while True:
                result = await call(
                    "object_query",
                    document_id=did,
                    type_name="GeneralNote",
                    select=paths,
                    offset=offset,
                    limit=100,
                    max_bytes=1800,
                )
                assert (
                    len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode())
                    <= 1800
                )
                items.extend(result["items"])
                offset = result["next_offset"]
                if offset is None:
                    break
            assert items == combined["items"]
            assert len(items) == result["total"]

            filtered = await call(
                "object_query",
                document_id=did,
                type_name="Note",
                filters={"quarterLength": {"numerator": 1, "denominator": 3}},
                select=["pitch.midi"],
            )
            assert filtered["total"] == 1
            assert filtered["items"][0]["id"] == plain["items"][0]["id"]
            for select in (
                ["__class__"],
                ["pitch.__dict__"],
                ["nameWithOctave.text"],
                ["duration.duration.duration.duration.type"],
                ["pitch"] * 33,
            ):
                error = await client.call_tool(
                    "object_query",
                    {
                        "document_id": did,
                        "type_name": "Note",
                        "select": select,
                    },
                )
                assert error.isError
                assert "invalid_selection" in error.content[0].text
