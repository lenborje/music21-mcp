# Fas 1: undersökning och designbeslut

## Undersökt objektmodell

Undersökningen gjordes mot installerad music21 10.5.2 och MCP SDK 1.30.0.
Små Python-experiment bekräftade följande före implementationen:

- Score, Part, Measure och Voice är Stream-underklasser. Barn kan också vara
  metadata, instrument, clefs, taktarter och spanners, inte bara noter.
- Samma Note kan placeras i två Streams. `elementOffset(note)` gav 1/3 i den
  ena och 2 i den andra. Position tillhör alltså en relation, inte identiteten.
- Vanlig Stream-iteration ändrar barnens activeSite. `Stream.elements` gör
  inte detta; den kan däremot sortera och fylla interna cacheminnen.
- Note.pitch och Note.duration återger samma objekt vid upprepad läsning.
  Dessa är inte Stream-barn men behöver egna referenser.
- Chord innehåller noter och pitches. Spanner.getSpannedElements() ger
  referenser till redan existerande objekt, inte hierarkiska barn.
- Offsets och quarterLength kan vara Fraction eller float. Inbyggda floats
  kan inte återskapa ursprunglig precision som music21 redan har förlorat.

Primärkällor:
- https://music21.org/music21docs/moduleReference/moduleBase.html
- https://music21.org/music21docs/moduleReference/moduleStreamBase.html
- https://music21.org/music21docs/usersGuide/usersGuide_58_sitesContext.html
- https://github.com/modelcontextprotocol/python-sdk/tree/v1.30.0

## Beslut

1. En serverprocess har en SessionManager med flera dokument. Varje dokument
   äger ett separat register med starka referenser, indexerat med Python-id.
   Handtag är opaka och unika; varken music21.id eller en musikalisk adress
   används som identitet. Stängning frigör hela dokumentet och ogiltigförklarar
   dess handtag. Ingen persistens eller samtidig flerklienthantering ingår.
2. Stream.elements används för traversal utan activeSite-byte. API:et är
   musikaliskt skrivskyddat men lovar inte frånvaro av interna cacheeffekter.
   Ingen flatten/recurse som skapar extra Stream-kontexter används.
3. object_children ger direkta Stream-barn. Varje post har en parent-referens
   och exakt offset i just den föräldern. object_get kräver ingen unik förälder:
   den visar alla direkta Stream-positioner inom dokumentets rotgraf.
   Pitch, Duration, Lyric, Tie och spanner-relationer följs via egenskaper.
4. Sökning går i djupet från vald Stream (eller roten), exkluderar sökroten
   och returnerar förekomster med parent och offset. Samma objekt i olika
   Streams kan förekomma flera gånger med samma handtag. Cykler bryts längs
   aktuell sökväg. Typfilter matchar godkända klassnamn inklusive basklasser.
5. Egenskaper tillåts uttryckligen per klass. Inget dir/getattr från klientens
   sökväg, eval, exec, metodanrop eller automatisk egenskapspublicering.
   Sökfilter är AND av exakta likhetsvillkor på godkända skalära egenskaper;
   för noter ingår nameWithOctave, och quarterLength kan anges rationellt.
   Nästlade sökvägar och relationella frågespråk skjuts upp.
6. Alla musikaliska tidsvärden serialiseras som {numerator, denominator}.
   Fraction bevaras exakt; float konverteras med as_integer_ratio utan
   avrundning. Objektvärden blir {$ref: ...}, aldrig rekursiv expansion.
   Samlingar i egenskaper begränsas till 100 poster med total/truncated.
7. Barn och sökresultat har offset/limit-paginering (max 100). Traversal
   begränsas till 100 000 förekomster och djup 128 och avbryts med ett
   kontrollerat fel i stället för ett tyst ofullständigt resultat.
8. Import accepterar endast en explicit lokal .musicxml/.xml/.mxl-fil,
   inte URL, katalog, corpus eller generell converter-sträng. Filstorlek
   begränsas till 20 MiB; komprimerade MXL till 100 MiB uppackat. MusicXML
   kan innehålla detaljer som music21 tappar; ingen förlustfri rundresa utlovas.
   Export och redigering ingår inte i fas 1.
9. Förväntade fel får stabil kod och kort meddelande; parserundantag och
   interna objektrepresentationer skickas inte till klienten.
10. MCP-lagret binder tunna verktyg till ett separat Python-API. SDK 1.x
    används för dess FastMCP-gränssnitt. Tillåtna läsverktyg annoteras read-only.

## Uppskjutna beslut

Automatisk schema/introspektion hör till fas 2. Resultat från framtida
metodanrop får inte automatiskt bli nya dokument utan ett separat beslut.
Transaktioner kan behöva kopior och en strategi för ogiltiga referenser;
rollback och redigering implementeras inte nu. MusicXML-bevarande behöver
senare testas mot verkliga MuseScore-partitur och export.
