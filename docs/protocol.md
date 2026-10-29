# Fas 1: API-kontrakt

Transport: MCP över stdio, en sessionshanterare per serverprocess. Alla
verktyg returnerar strukturerad JSON. Dokument- och objekt-ID:n är opaka
strängar. Ett object_id gäller endast i sitt dokument och under dess livstid.

| Verktyg | Argument | Resultat |
| --- | --- | --- |
| document_open | path | document_id, name, root |
| document_list | inga | lista av dokumentbeskrivningar |
| document_close | document_id | closed: true |
| object_get | document_id, object_id | id, type, properties, positions |
| object_children | document_id, object_id, offset=0, limit=50 | items, total, next_offset |
| object_query | document_id, object_id=null, type_name=null, filters=null, offset=0, limit=50, select=null, max_bytes=262144 | items, total, next_offset |

`root` är ett objekt-ID som kan användas direkt. Egenskaper som refererar till
objekt kodas som `{"$ref": "obj-..."}`. Läs dem med object_get. Egenskapssamlingar
har `items`, `total` och `truncated` (max 100). Rekursiv expansion sker endast
när klienten uttryckligen väljer nästlade egenskaper med `select`. Tillgängliga egenskaper definieras uttryckligen i adaptern, inklusive
noters pitch/duration/lyrics/tie, ackords pitches/notes och spanners spannedElements.
Andra importerade Music21Object kan inspekteras men ha tomma properties.

Barn och sökträffar har `id`, fullständigt `type`, `parent: {"$ref": ...}` samt
`offset: {"numerator": 1, "denominator": 3}`. Offset gäller i den angivna direkta
föräldern, i fjärdedelsnoter. quarterLength använder samma rationella format.
Ingen ospecificerad activeSite-position exponeras. object_get.positions visar
distinkta direkta Stream-föräldrar inom rotgrafen som `items`, `total`, `truncated`,
med högst 100 poster. Roten och egenskapsobjekt som Pitch har normalt inga positioner.

object_children följer endast Stream-innehåll. För andra objekt blir resultatet
tomt; Pitch och Duration nås i stället via properties. Voices behålls som egna
behållare. Sökning går rekursivt genom Stream-innehåll i djupordning och utesluter
sökroten. Delade objekt ger flera förekomster med samma ID. Spanner-länkar och
objektegenskaper traverseras inte av sökningen.

Typnamn i sökningar är godkända kortnamn från adaptern, exempelvis Part,
Measure, Voice, Note, Rest, Chord, GeneralNote, Stream, Clef och Spanner.
Basklasser matchar underklasser. Ett okänt typnamn ger fel.

`filters` är en JSON-mapp med AND-likhet. Tillåtna namn är nameWithOctave,
quarterLength, number, partName, text, step, octave, type, ratioString,
sharps, content. Egenskapen måste finnas direkt på objektets godkända läsyta;
exempelvis används nameWithOctave för Note, medan step finns på Pitch.
quarterLength accepterar ett tal eller en rationell mapp. Övriga värden är
JSON-skalärer. Okända namn, privata attribut och attributsökvägar ger fel.

Paginering använder offset >= 0 och limit mellan 1 och 100. next_offset är null
vid slutet. total räknas för hela sökområdet; sidstorleken begränsar svar och
registrering men inte tiden att söka. Traversal över 100 000 förekomster eller
128 nivåer ger traversal_limit. object_get söker också rotgrafen efter positioner.

Fel returneras som MCP tool errors med `kod: meddelande`. Koder omfattar
unknown_document, unknown_object, invalid_file, parse_error, invalid_type,
invalid_filter, invalid_pagination, invalid_selection, projection_limit,
result_too_large, traversal_limit, unsupported_value och
internal_error. Felaktiga MCP-argument valideras även av SDK:t.

Import stödjer explicit lokal .xml/.musicxml/.mxl, max 20 MiB på disk och
100 MiB uppackat ZIP-innehåll. Ingen URL/corpus-åtkomst eller generell
converter-sträng erbjuds. Alla referenser upphör vid document_close/omstart.


## Egenskapsurval i object_query

`select` är en valfri lista med punktseparerade egenskapsnamn. Den ändrar inte
sökning, filter eller objektidentitet. Utelämnat/null ger samma träffar och
svarsform som tidigare. `[]` lägger till tomma `properties` per träff.

```json
{
  "document_id": "doc-...",
  "type_name": "GeneralNote",
  "select": [
    "quarterLength",
    "pitch.nameWithOctave",
    "pitch.midi",
    "pitches.nameWithOctave",
    "lyrics.text",
    "duration.type"
  ],
  "limit": 100,
  "max_bytes": 262144
}
```

Varje träff behåller `id`, `type`, `parent` och `offset`. De begärda värdena
läggs i `properties`. Exempel för en Note:

```json
{
  "id": "obj-note",
  "type": "music21.note.Note",
  "parent": {"$ref": "obj-measure"},
  "offset": {"numerator": 1, "denominator": 3},
  "properties": {
    "quarterLength": {"numerator": 1, "denominator": 1},
    "pitch": {
      "$ref": "obj-pitch",
      "properties": {"nameWithOctave": "C4", "midi": 60}
    },
    "lyrics": {
      "items": [{"$ref": "obj-lyric", "properties": {"text": "Hej"}}],
      "total": 1,
      "truncated": false
    },
    "duration": {"$ref": "obj-duration", "properties": {"type": "quarter"}}
  }
}
```

Endast adapterns uttryckligen godkända egenskaper får användas på varje nivå.
Privata namn, indexering, jokertecken och metodanrop stöds inte. Ett okänt namn
ger invalid_selection. Godkända egenskaper som saknas på den aktuella klassen
utelämnas: en Rest saknar pitch, en Chord har pitches, och en Note har pitch.
Null behålls (exempelvis tie på en obunden not). Expansion genom ett befintligt
skalärvärde ger invalid_selection. Samma regler gäller för nästlade objekt.

Samlingar expanderas automatiskt över `items` med bevarade `$ref`, `total` och
`truncated`. `notes.pitch.nameWithOctave` följer exempelvis ett ackords noter
till deras tonhöjder. Samlingar behåller gränsen 100 poster; nästlade samlingar
har ingen separat sidmarkör i denna version. Vid behov kan referenser följas
med object_get inom samma begränsade läsmodell. `spannedElements` kan väljas
explicit men ingår inte i söktraversalen. Återkommande/cykliska referenser
behåller samma ID och expanderas bara så långt sökvägen anger.

Överlappande sökvägar slås samman. `pitch` tillsammans med `pitch.midi`
returnerar en utökad referens med midi; utan undersökväg returneras endast
referensen, precis som object_get. Resultatens referenser kan alltid återanvändas
med object_get i samma öppna dokument.

## Paginering och storleksgränser

- Högst 32 sökvägar och 4 egenskapsnivåer per sökväg.
- Högst 100 poster per egenskapssamling och 4096 besökta projektionsvärden
  per matchande objekt. Överskriden expansionsbudget ger projection_limit.
- `limit` är fortfarande 1–100 och `offset` är index bland filtrerade
  förekomster. Den befintliga traverseringsgränsen gäller fortsatt.
- `max_bytes` är 1024–262144 och begränsar hela svarsdokumentets kompakta
  UTF-8-JSON (`ensure_ascii=False`, utan blanksteg). MCP:s omslag och SDK:ts
  eventuella formatering/dubblering till text räknas inte in i den gränsen.
- En sida kan innehålla färre poster än `limit` på grund av bytegränsen.
  Använd alltid `next_offset`; öka inte själv med limit. Träffar hoppas inte över.
- En enskild för stor träff ger result_too_large. Minska urvalet eller öka
  max_bytes inom serverns gräns. Värden skärs inte av tyst för att få plats.
- `total` avser hela sökområdet. Paginering över öppet, skrivskyddat dokument
  är stabil. Urval påverkar inte antalet matchande förekomster.

## Offset i olika Stream-kontexter

Tidsposition är en egenskap hos relationen mellan objekt och Stream. Samma
Note kan ligga vid 1/3 i Stream A och vid 2 i Stream B: två träffar får då samma
`id` och samma projicerade egenskaper, men olika `parent` och `offset`.
`object_get.positions` visar båda direkta föräldrarna inom dokumentets rotgraf.

`offset` i en träff är alltid relativ till dess **direkta förälder**, även när
sökningen startar från Score eller Part. Den är aldrig automatiskt summerad
från sökroten. Om en Measure ligger vid 8 i en Part, en Voice vid 1 i takten
och en Note vid 1/3 i Voice, är notträffens offset fortfarande 1/3. Dess position
relativt Part är 8 + 1 + 1/3 längs just den vägen. För globala positioner behöver
klienten följa och summera rätt kedja av Stream-relationer; en graf kan ha flera.

Urvalet tillåter därför inte `offset`, `beat`, `measureNumber` eller `activeSite`
som objektegenskaper. Nästlade Pitch-, Lyric- och ackordnotreferenser får ingen
påhittad Stream-position. Traversal använder Stream.elements och elementOffset,
inte vanlig iteration eller objektets kontextberoende offset-property, så en
läsning byter inte activeSite. Rationella tidsvärden behålls på samtliga nivåer.
