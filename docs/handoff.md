# Handoff – 2026-10-29

## Status och avgränsning

Fas 1 och 2 i [roadmapen](roadmap.md) är implementerade: en tillståndsbevarande,
skrivskyddad MCP-server över stdio med generellt urval av nästlade egenskaper,
object_schema, automatisk metadataupptäckt och generell värdeserialisering.
Projektionen verifierades efter användarens tidigare omstart. Fas 2:s nya
schema har verifierats genom en separat riktig stdio-klient i integrationstest;
användarens redan körande MCP-server behöver startas om för det nya schemat.

**Ingen redigering ska implementeras utan ett nytt uppdrag.** Inga setters,
objektskapande verktyg, metodanrop, export eller transaktioner finns.
Fas 2 är klar; fas 3 ska inte påbörjas utan ett nytt uppdrag.
Det finns inget pågående implementationsuppdrag efter denna handoff.

Tidigare implementationer är committade och pushade till origin/main:

- `06ce4a0`: skrivskyddad fas 1 och ursprungliga designbeslut.
- `e95f2a7`: begränsad nästlad projektion, tester och Sonett 18-mätning.

- `0550e9b`: handoff för läget före fas 2.

Denna handoff har därefter uppdaterats med fas 2:s design och verifiering.

## Läs först

- [README](../README.md): installation och start.
- [Arkitektur](architecture.md): music21-undersökning och designbeslut.
- [API-kontrakt](protocol.md): exakt semantik, gränser och offsetkontexter.
- [Mätrapport](sonett18-measurement.md) och [mätdata](measurements/sonett18.json).

## Kodens ansvar

| Fil under src/music21_mcp | Ansvar |
| --- | --- |
| server.py | FastMCP-verktyg, stdio och sanering av oväntade fel |
| sessions.py | Dokumentlivscykel och lokal MusicXML/MXL-import |
| registry.py | Dokumentägda starka referenser och stabila objekt-ID:n |
| adapters/music21.py | Explicit tillåtna typer/egenskaper och Stream-traversal |
| serialization.py | JSON-värden, rationella tider och objektreferenser |
| projection.py | Validering och begränsad expansion av valda egenskaper |
| introspection.py | Passiv metadataupptäckt, docs, typer, signaturer och scheman |
| pagination.py | Gemensamma paginerings- och JSON-storleksregler |
| object_api.py | Läsning, barn, sökning och paginering utan MCP-beroende |

Exponerade verktyg: document_open, document_list, document_close,
object_get, object_children, object_query och object_schema. Python >=3.12,
music21 >=10.5,<11 och officiella MCP-SDK:t >=1.26,<2; uv.lock finns.
Undersökningen utfördes med music21 10.5.2 och MCP 1.30.0.

## Semantik att bevara

- music21 är en graf. Samma Python-objekt får samma handtag inom dokumentet,
  även vid olika Stream-förekomster eller nästlad expansion. Handtag gäller
  inte över stängning, omstart eller olika dokument.
- Stream.elements används för att undvika byte av activeSite. Läsning kan
  ändå sortera och fylla music21:s interna cacheminnen.
- Träffarnas offset gäller alltid den direkta parent-Streamen, inte sökroten.
  Samma objekt kan ha olika offsets i olika Streams. Globala tider kräver
  att klienten väljer och summerar rätt kedja av relationer.
- Offset och quarterLength är rationella JSON-värden. Ingen implicit
  avrundning eller publicering av kontextberoende beat/offset-egenskaper.
- Sökning går genom Stream-innehåll, exkluderar roten och returnerar
  förekomster. Pitch, Duration, Lyrics och spanner-länkar nås som egenskaper.
- Explicit godkända egenskaper gäller på varje nivå. Klientens strängar får
  inte öppna godtycklig getattr, introspektion, eval/exec eller metodanrop.
- Nästlade sökfilter finns inte. Nästlade vägar stöds endast i projektionen.

## Projektion och gränser

object_query accepterar exempelvis:

```json
{
  "document_id": "doc-...",
  "type_name": "GeneralNote",
  "select": ["quarterLength", "pitch.nameWithOctave", "pitches.midi", "lyrics.text"],
  "limit": 100,
  "max_bytes": 262144
}
```

Utan select gäller tidigare svarsform. Med select tillkommer properties;
utökade referenser behåller $ref och får egna properties. Samlingar har
items/total/truncated. Saknade godkända egenskaper utelämnas; null bevaras.
Överlappande sökvägar slås samman. Expansion genom skalärer ger fel.

Gränser: 32 vägar, 4 egenskapsnivåer, 100 poster per egenskapssamling,
4096 projektionsvärden per träff, 100 träffar per sida, 100000 traverserade
förekomster och 128 Stream-nivåer. max_bytes kan sättas till 1024–262144 och
avser kompakt UTF-8-JSON, inte MCP-omslaget eller SDK:ts textdubblering.
Följ alltid next_offset: bytegränsen kan ge kortare sidor än limit.
En ensam för stor träff ger ett kontrollerat fel, ingen tyst trunkering.

Import begränsas till uttryckliga lokala .xml/.musicxml/.mxl-filer, max
20 MiB på disk och 100 MiB deklarerat uppackat ZIP-innehåll. Förlustfri
MusicXML-rundresa är inte utlovad. total kräver fortfarande full traversal;
object_get söker rotgrafen för positioner. Egenskapssamlingar över 100 har
trunkeringsmarkör men ännu ingen egen paginering.

## Verifiering

Senaste fullständiga kontroller efter kodändringarna:

```sh
uv run pytest -q
uv run ruff check src tests examples/query_dump.py
uv run ruff format --check src tests examples/query_dump.py
uv run mypy src
```

Efter fas 2 passerade 28 tester på både Python 3.12 och 3.14, inklusive riktig
stdio-transport. Ruff, formatering och mypy passerade också. Tester för schema,
generell serialisering och metadataupptäckt beskrivs i introspection.md. Integrationstester
startar en riktig server med officiella SDK:ts stdio-klient och jämför
projektioner med individuella object_get, inklusive noter, ackord, pauser,
text, duration, tie, spanners och bytebegränsad paginering. Direkta API-tester
täcker delade objekt, activeSite och expansionsgränser. Testpartituren kräver
inte användarens privata Sonett-fil.

Efter användarens omstart verifierades även den ordinarie MCP-anslutningen:
Sonett 18 gav 559 enskilda Note-objekt; nästlad tonhöjd och text matchade
object_get. Med max_bytes=2048 gav två på varandra följande sidor 4 träffar
vardera, 1812 respektive 1814 byte och next_offset 4 respektive 8, utan överlapp.
Testdokumentet stängdes och anslutningen förblev stabil.

## Sonett 18 och anropsmätning

Lokal indata: `~/Downloads/Sonett18.xml`, inte incheckad. Nils Lindbergs
Shakespeare-sättning för SATB, med omfattande tvåtonig altdelning; 30 takter,
4/4, lento 50. Fullständiga resultat och input-SHA256 finns i mätrapporten.

Den nya körningen använde **13 verktygsanrop**: öppning, 11 object_query-sidor
och stängning. Alla 1025 Stream-förekomster hämtades med valda egenskaper.
Det är **99,38 % färre** än den tidigare fullständiga körningens 2106 anrop.
Samtliga 676 not-/paus-/ackordförekomster matchade tidigare JSON-underlag för
tonhöjder, längder, lokal position, takt och sångtext. All läsning av partituret
gick genom MCP; lokal Python sammanställde JSON, utan att anropa music21.

[examples/query_dump.py](../examples/query_dump.py) är en generell, reproducerbar
MCP-klient med anropsräknare, inte ett specialiserat musikanalysverktyg.
Mätrapporten innehåller det exakta kommandot. Tidigare rådata och diagnostik
låg i /tmp; fortsatt arbete ska inte förutsätta att de filerna finns kvar.

## Tidigare transportavbrott

Vid den första analysen avslutades Codex code-mode-värd under en stor
parallell hämtning. Första felet var `code-mode host closed its stdout`,
följt av förlorat variabellager och `Transport closed` för den anslutna MCP:n.
En full telemetrikö noterades samtidigt. Rotorsaken är **inte fastställd**;
det finns inget belägg för att kalla detta en bevisad serverbugg.

En separat MCP-klient klarade därefter 800 object_get med 80 samtidiga
förfrågningar och levande anslutning efteråt. Den nya projektionen minskar
behovet av stora mängder individuella anrop. Undvik att återskapa den tidigare
anropsstormen i Codex verktygsvärd vid vanlig inspektion. Ingen särskild
transportreparation har implementerats i projektet.

## Nästa steg vid ett nytt uppdrag

Följ användarens nästa prioritering. Fas 2 är implementerad. Läs
[introspection.md](introspection.md) för designval, uppmätt täckning och gränser.
Fas 3 omfattar redigering och är inte beställd. Separat
paginering av egenskapssamlingar och vidare diagnostik av värdavbrottet är
kända förbättringsområden, inte pågående arbete. Behåll generellt API och
skrivskydd tills användaren uttryckligen ändrar avgränsningen.


## Fas 2: nytt API och fortsatta säkerhetsgränser

object_schema() listar den paginerade typkatalogen. type_name="Note" ger
klassmetadata; document_id + object_id ger instansmetadata även för konkreta
underklasser. kind kan filtrera property/attribute/method. Bara katalogtyper
kan väljas med namn; inga godtyckliga importer görs.

Schema upptäcker namn utan getters och utvärderar inte annotationer, inte heller
uppskjutna annotationer i Python 3.14+. Upptäckta namn ger inte läsbehörighet.
readable anger den granskade policyn; writable/callable är alltid false.
Objektregister och activeSite lämnas orörda av schemahämtning. Null-typer och
trunkerade docstrings är avsiktligt markerade, inte implicita behörigheter.

Serialisering använder ProtoM21Object som referensbas. Accidental, Microtone,
Tuplet, Articulation och Expression har granskade läsfält; DurationTuple kodas
som ett direkt värde. Mappningar och enumvärden stöds med storleks-/djupgränser.
Detta är fortsatt ett skrivskyddat API utan metodexekvering.
