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
| object_query | document_id, object_id=null, type_name=null, filters=null, offset=0, limit=50 | items, total, next_offset |

`root` är ett objekt-ID som kan användas direkt. Egenskaper som refererar till
objekt kodas som `{"$ref": "obj-..."}`. Läs dem med object_get. Egenskapssamlingar
har `items`, `total` och `truncated` (max 100). Ingen implicit rekursiv expansion
sker. Tillgängliga egenskaper definieras uttryckligen i adaptern, inklusive
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
invalid_filter, invalid_pagination, traversal_limit, unsupported_value och
internal_error. Felaktiga MCP-argument valideras även av SDK:t.

Import stödjer explicit lokal .xml/.musicxml/.mxl, max 20 MiB på disk och
100 MiB uppackat ZIP-innehåll. Ingen URL/corpus-åtkomst eller generell
converter-sträng erbjuds. Alla referenser upphör vid document_close/omstart.
