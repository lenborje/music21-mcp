# music21-mcp

Skrivskyddad MCP-server över stdio för att läsa MusicXML och utforska music21:s
objektmodell med stabila objektreferenser. Fas 1 och 2 är implementerade, inklusive
självbeskrivande scheman och nästlad projektion. Redigering, export och metodanrop
ingår inte.

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


För att hämta värden utan ett object_get per not kan object_query ges exempelvis
`select=["quarterLength", "pitch.nameWithOctave", "pitches.midi", "lyrics.text"]`.
Nästlade referenser behåller sina ID:n. Följ alltid next_offset eftersom även
sidans bytegräns kan begränsa antalet träffar. Se [API-kontraktet](docs/protocol.md).

Ett generellt klientexempel hämtar samtliga objekt med ett valfritt urval genom
riktiga MCP-anrop och redovisar antalet verktygsanrop:

```sh
uv run python examples/query_dump.py ~/Downloads/Sonett18.xml \
  --select partName number quarterLength pitch.nameWithOctave pitches.midi lyrics.text
```

[Mätningen för Sonett 18](docs/sonett18-measurement.md) jämför den nya hämtningen
med de tidigare individuella anropen. Starta om en redan körande MCP-server
för att få det nya verktygsschemat.


Utforska läsmodellen utan att känna till music21:s interna API:

1. `object_schema()` listar typerna som kan beskrivas utan ett öppet dokument.
2. `object_schema(type_name="Note")` beskriver ärvda egenskaper och metoder.
3. `object_schema(document_id=..., object_id=...)` beskriver ett verkligt objekt,
   inklusive publika instansfält som saknar statiska deklarationer.
4. Välj fält märkta `readable: true` i object_query.select eller läs dem via
   object_get. Följ next_offset för hela schemat.

Metoder redovisas med signaturer och dokumentation men `callable: false`.
Upptäckt av ett publikt fält ger inte läsbehörighet automatiskt. Schemahämtning
kör inte getters och utvärderar inte annotationer. Läs [undersökningen av
introspektion](docs/introspection.md) för designval och täckning.
