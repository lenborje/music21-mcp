import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SCORE = Path(__file__).resolve().parents[2] / "examples/scores/prototype.musicxml"


async def test_real_stdio_client():
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "music21_mcp"])
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            tools = await client.list_tools()
            assert {t.name for t in tools.tools} == {
                "document_open",
                "document_list",
                "document_close",
                "object_get",
                "object_children",
                "object_query",
                "object_schema",
            }

            async def call(name, **kwargs):
                result = await client.call_tool(name, kwargs)
                assert not result.isError, result.content
                return result.structuredContent

            doc = await call("document_open", path=str(SCORE))
            did = doc["document_id"]
            parts = await call("object_query", document_id=did, type_name="Part")
            measures = await call(
                "object_query",
                document_id=did,
                object_id=parts["items"][0]["id"],
                type_name="Measure",
            )
            children = await call(
                "object_children", document_id=did, object_id=measures["items"][0]["id"]
            )
            assert children["total"] > 0
            notes = await call(
                "object_query",
                document_id=did,
                object_id=measures["items"][0]["id"],
                type_name="Note",
            )
            first = notes["items"][0]["id"]
            data = await call("object_get", document_id=did, object_id=first)
            assert data["properties"]["nameWithOctave"] == "C4"
            again = await call(
                "object_query", document_id=did, type_name="Note", filters={"nameWithOctave": "C4"}
            )
            assert again["items"][0]["id"] == first
            error = await client.call_tool(
                "object_query",
                {
                    "document_id": did,
                    "filters": {"__class__": "anything"},
                },
            )
            assert error.isError
            assert "invalid_filter" in error.content[0].text
            await call("document_close", document_id=did)
            closed = await client.call_tool("object_get", {"document_id": did, "object_id": first})
            assert closed.isError
