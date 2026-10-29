# music21-mcp

Skrivskyddad MCP-server över stdio för att läsa MusicXML och utforska music21:s
objektmodell med stabila objektreferenser. Fas 1 är implementerad; redigering,
export, metodanrop och automatisk introspektion ingår inte.

Kräver Python 3.12 eller senare och [uv](https://docs.astral.sh/uv/).

```sh
uv sync --extra dev
uv run music21-mcp
```

Servern väntar på MCP-meddelanden via stdin. Använd följande konfiguration i
en MCP-klient och byt sökvägen till din lokala checkout:

```json
{
  "mcpServers": {
    "music21": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/music21-mcp", "run", "music21-mcp"]
    }
  }
}
```

Exempel på verktygsflöde:

1. `document_open(path="/absolute/path/score.musicxml")` ger `document_id` och `root`.
2. `object_children(document_id=..., object_id=root)` listar direkta barn.
3. `object_query(document_id=..., type_name="Part")` hittar stämmorna.
4. Sök med en stämmas ID som `object_id` och `type_name="Measure"` för takter.
5. Sök inom en takt med `type_name="Note"`, även om noterna ligger i Voices.
6. `object_get(document_id=..., object_id=...)` läser tonhöjd, längd och position.
7. `object_query(document_id=..., type_name="Note", filters={"nameWithOctave": "C4"})`
   hittar motsvarande noter med samma stabila ID:n.
8. `document_close(document_id=...)` frigör dokumentet.

Ett litet testpartitur finns i [examples/scores/prototype.musicxml](examples/scores/prototype.musicxml).
Servern får läsa uttryckligen angivna lokala MusicXML-filer med processens
filbehörigheter. Kör den därför som en lokal betrodd utvecklingskomponent.
Dokumenten hålls i minnet tills de stängs eller servern avslutas.

```sh
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

Tester täcker Python-API:et och en riktig MCP-klient som startar servern över stdio.
Läs [designbesluten](docs/architecture.md), [API-kontraktet](docs/protocol.md)
och [roadmapen](docs/roadmap.md).
