"""Dump paginated, projected objects using only an MCP stdio client.

Example: uv run python examples/query_dump.py ~/Downloads/Sonett18.xml \
    --select partName number quarterLength pitch.nameWithOctave lyrics.text

The same generic query can inspect any imported document; no music21 import or
music-specific analysis is performed here. Output includes measured tool calls.
"""

import argparse
import asyncio
import json
import sys
import time
from collections import Counter

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def dump(path: str, select: list[str], limit: int, max_bytes: int) -> dict:
    calls: Counter[str] = Counter()
    started = time.monotonic()
    async with stdio_client(
        StdioServerParameters(command=sys.executable, args=["-m", "music21_mcp"])
    ) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(tool: str, **args):
                calls[tool] += 1
                result = await client.call_tool(tool, args)
                if result.isError:
                    raise RuntimeError(result.content)
                return result.structuredContent

            doc = await call("document_open", path=path)
            items = []
            offset = 0
            sizes = []
            while True:
                page = await call(
                    "object_query",
                    document_id=doc["document_id"],
                    select=select,
                    offset=offset,
                    limit=limit,
                    max_bytes=max_bytes,
                )
                sizes.append(
                    len(json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode())
                )
                items.extend(page["items"])
                offset = page["next_offset"]
                if offset is None:
                    break
            await call("document_close", document_id=doc["document_id"])
    return {
        "document": doc,
        "select": select,
        "items": items,
        "measurement": {
            "tool_calls": dict(calls),
            "total_tool_calls": sum(calls.values()),
            "query_page_bytes": sizes,
            "occurrences": len(items),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--select", nargs="*", default=[])
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max-bytes", type=int, default=262144)
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(dump(args.path, args.select, args.limit, args.max_bytes)),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
