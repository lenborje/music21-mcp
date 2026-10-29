"""A real MCP client discovers the available read surface before using it."""

import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from music21_mcp.pagination import json_size

SCORE = Path(__file__).resolve().parents[2] / "examples/scores/prototype.musicxml"


async def test_discover_and_use_schema_over_stdio():
    async with stdio_client(
        StdioServerParameters(command=sys.executable, args=["-m", "music21_mcp"])
    ) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(tool, **args):
                result = await client.call_tool(tool, args)
                assert not result.isError, result.content
                return result.structuredContent

            tools = {t.name: t for t in (await client.list_tools()).tools}
            assert tools["object_schema"].annotations.readOnlyHint
            assert "object_call" not in tools and "object_set" not in tools
            catalog = await call("object_schema", limit=100)
            assert "Note" in {item["name"] for item in catalog["items"]}
            doc = await call("document_open", path=str(SCORE))
            did = doc["document_id"]
            notes = await call("object_query", document_id=did, type_name="Note")
            first_id = notes["items"][0]["id"]
            schema_items = []
            offset = 0
            while True:
                result = await call(
                    "object_schema",
                    document_id=did,
                    object_id=first_id,
                    offset=offset,
                    limit=100,
                    max_bytes=8192,
                )
                assert result["type"] == "music21.note.Note"
                assert json_size(result) <= 8192
                schema_items.extend(result["items"])
                offset = result["next_offset"]
                if offset is None:
                    break
            assert len(schema_items) == result["total"]
            assert len({m["name"] for m in schema_items}) == len(schema_items)
            assert all(not m["writable"] and not m["callable"] for m in schema_items)
            read_names = [m["name"] for m in schema_items if m["readable"]]
            direct = await call("object_get", document_id=did, object_id=first_id)
            assert set(direct["properties"]) == set(read_names)
            projected = await call(
                "object_query", document_id=did, type_name="Note", limit=1, select=read_names
            )
            assert projected["items"][0]["id"] == first_id
            assert projected["items"][0]["properties"] == direct["properties"]
            pitch_id = direct["properties"]["pitch"]["$ref"]
            pitch_schema = await call(
                "object_schema", document_id=did, object_id=pitch_id, kind="property", limit=100
            )
            assert any(m["name"] == "midi" and m["readable"] for m in pitch_schema["items"])
            methods = await call("object_schema", type_name="Pitch", kind="method", limit=100)
            transpose = next(m for m in methods["items"] if m["name"] == "transpose")
            assert "inPlace" in transpose["signature"]
            assert transpose["parameters"][1]["default"] == {"value": False}
            assert not transpose["callable"]
            # General references support articulation/tuplet/accidental metadata too.
            duration_id = direct["properties"]["duration"]["$ref"]
            duration_data = await call("object_get", document_id=did, object_id=duration_id)
            tuplet_id = duration_data["properties"]["tuplets"]["items"][0]["$ref"]
            tuplet_schema = await call("object_schema", document_id=did, object_id=tuplet_id)
            assert tuplet_schema["type"] == "music21.duration.Tuplet"
            tuplet = await call("object_get", document_id=did, object_id=tuplet_id)
            assert tuplet["properties"]["numberNotesActual"] == 3
            assert tuplet["properties"]["durationActual"]["quarterLength"] == {
                "numerator": 1,
                "denominator": 2,
            }
            for args in (
                {"type_name": "os.system"},
                {"document_id": did, "object_id": first_id, "type_name": "Note"},
            ):
                error = await client.call_tool("object_schema", args)
                assert error.isError
            await call("document_close", document_id=did)
            error = await client.call_tool(
                "object_schema", {"document_id": did, "object_id": first_id}
            )
            assert error.isError
            assert "unknown_document" in error.content[0].text
