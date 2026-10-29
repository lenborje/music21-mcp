# Sonett 18: mätning av projektion via MCP

Körd 2026-10-29 mot den lokala Sonett18.xml med samma generella MCP-server.
Indatafingeravtryck, urval, sidstorlekar och råa mätvärden finns i
[measurements/sonett18.json](measurements/sonett18.json). Partituret och de
fullständiga objektsvaren checkas inte in.

## Resultat

| Hämtning | MCP-verktygsanrop |
| --- | ---: |
| Tidigare fullständiga, lyckade analyskörning med individuella object_get | 2 106 |
| Ny körning: document_open | 1 |
| Ny körning: object_query, 100 förekomster per sida | 11 |
| Ny körning: document_close | 1 |
| **Ny körning totalt** | **13** |

**Minskning: 99,38 %.** Målet om minst 90 % är uppnått även jämfört med enbart
den tidigare fullständiga körningen, utan att räkna tidigare avbrutna eller
upprepade försök. Den tidigare samlade analysinsatsen var 4 892 anropsförsök;
jämförelsen här använder den strängare baslinjen 2 106.

Körningen hämtade 1 025 förekomster i 11 sidor. Kompakta JSON-sidor var
11 957–53 801 byte, under gränsen 262 144 byte. Tiden var cirka 0,39 sekunder,
inklusive klientens serverstart/initiering och dokumentstängning. Tiden är en
enskild lokal observation, inte ett representativt prestandatest.

Anropsräknaren i klienten registrerade 13 verktygsanrop. Serverns stderr-logg
bekräftade exakt 13 CallToolRequest. MCP-initiering och SDK:ts listning av
verktyg ingår inte i verktygsanropsmåttet, i överensstämmelse med baslinjen.
Den separata stdio-klienten användes eftersom den tidigare anslutningen i
Codex var bruten och en redan startad server inte får nytt verktygsschema
utan omstart. Inga music21-importer eller direktanrop finns i klienten.

## Reproduktion

Från projektroten, med filen tillgänglig lokalt:

```sh
uv run python examples/query_dump.py ~/Downloads/Sonett18.xml --select \
  partName partAbbreviation title composer movementName number numberSuffix \
  ratioString sharps text content quarterLength nameWithOctave \
  pitch.nameWithOctave pitch.midi pitches.nameWithOctave pitches.midi \
  lyrics.text lyrics.syllabic lyrics.number tie.type duration.type duration.dots \
  > /tmp/sonett18_projected.json 2> /tmp/sonett18_projected.log
```

Exemplet är en generell klient som hämtar valda egenskaper från samtliga
objekttyper. Ingen särskild Sonett- eller musikanalysfunktion har lagts till i
servern. Lokal sammanställning av JSON-svaren beräknar omfång, grupperar text
och jämför fraser. Själva not- och textläsningen sker uteslutande genom MCP.

## Kontroll av analysunderlaget

De 676 not-, paus- och ackordförekomsterna jämfördes lokalt mot JSON-underlaget
från den tidigare körningen. För samtliga stämde objekttyp, tonhöjd/ackordtoner,
längd, taktnummer, lokal offset samt textstavelsers text, nummer och syllabic.
Referenser jämförs inte mellan serverprocesser: deras ID:n är avsiktligt
processlokala. Stabil identitet inom samma dokument kontrolleras i testerna.

| Parti | Enskilda noter | Ackord | Pauser | Omfång |
| --- | ---: | ---: | ---: | --- |
| Sopran | 175 | 0 | 9 | C4–F5 |
| Alt | 74 | 82 | 9 | G♯3–B4 |
| Tenor | 157 | 0 | 9 | E3–D4 |
| Bas | 153 | 0 | 8 | E2–A3 |

Alla fyra partier har 30 takter. Metadata anger Nils Lindberg och William
Shakespeare samt ”Shall I compare thee to a summer's day”. Taktarten är 4/4,
med lento och metronomtal 50. Texten ger avsnitt vid takterna 1–8, 9–16,
17–24 och 25–30. De 82 ackordhändelserna i alten bekräftar det delade partiet.
Inledningen bildar a-moll; slutet har E i basen, B och D♯ i övriga partier,
alltså en klang med kvint och stor septima utan ters. Crescendo anges vid
21 och 24 och ritardando vid 29. Den tidigare musikaliska beskrivningen har
alltså samma faktaunderlag efter den nya hämtningen.

## Automatiska regressionstester

Integrationstestet startar en riktig MCP-server, läser ett separat litet
MusicXML-testpartitur och jämför projektionssvaren med individuella object_get
för noter, pauser, ackord, tonhöjder, duration, text, bindningar och spanners.
Det verifierar även filtrering, överlappande urval och fullständig paginering
under en låg bytegräns. Direkt API-test täcker samma objekt i olika Streams,
activeSite, rationella tidsvärden samt storleks- och expansionsgränser.
Sonett-filen krävs inte för att köra regressionstesterna.
