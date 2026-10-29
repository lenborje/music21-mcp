# music21-mcp

## 1. Projektidé

Utveckla en generell MCP-server (Model Context Protocol) som ger AI-agenter tillgång till Python-biblioteket **music21** för musikalisk analys, bearbetning och generering av partitur.

Till skillnad från befintliga music21-MCP-servrar, som huvudsakligen erbjuder ett begränsat antal specialiserade operationer, ska denna server exponera music21:s objektmodell på ett generellt och tillståndsbevarande sätt.

En agent ska exempelvis kunna:

- Läsa in ett MusicXML-partitur.
- Utforska dess struktur: partier, stämmor, takter, noter, pauser, ackord, text och andra notationselement.
- Söka efter objekt utifrån typ, position eller egenskaper.
- Läsa och ändra objektens attribut.
- Skapa, kopiera, flytta och ta bort objekt.
- Anropa relevanta metoder i music21.
- Utföra musikalisk analys.
- Exportera det modifierade partituret till MusicXML.

Servern ska vara oberoende av MuseScore, men MusicXML ska göra det möjligt att använda den tillsammans med MuseScore och andra notskriftsprogram.

## 2. Grundläggande designprinciper

### 2.1 Generellt API

MCP-servern ska inte behöva känna till alla tänkbara musikaliska operationer.

I stället ska den erbjuda ett litet antal generella verktyg för att:

1. Hantera dokument och sessioner.
2. Navigera i objektmodellen.
3. Söka och filtrera objekt.
4. Läsa objektens egenskaper.
5. Modifiera objekt.
6. Anropa metoder.
7. Importera och exportera dokument.

Specialiserade musikaliska verktyg kan tillkomma senare, men ska i princip kunna implementeras med hjälp av det generella API:et.

### 2.2 Tillståndsbevarande sessioner

Servern ska hålla inlästa music21-objekt i minnet mellan MCP-anrop.

Varje dokument tilldelas ett unikt ID. Objekt inom dokumentet ska kunna refereras med stabila handtag.

Exempel:

```text
document: score-1
object:   obj-1042
```

En agent ska kunna hämta ett objekt, undersöka dess egenskaper och använda samma objektreferens i efterföljande anrop.

Objektreferenserna behöver inte överleva en omstart av servern.

### 2.3 Ingen godtycklig Python-exekvering

Servern ska inte erbjuda ett generellt `eval` eller `exec`.

Det generella API:et ska i stället bygga på kontrollerad introspektion och metodanrop.

Endast uttryckligen tillåtna objekt, attribut och metoder får exponeras.

Detta är särskilt viktigt eftersom music21:s objektmodell innehåller Python-objekt som kan referera till annan funktionalitet än musikalisk bearbetning.

### 2.4 Separera MCP från music21

Projektet ska ha en tydlig uppdelning mellan:

- MCP-protokoll och transport.
- Sessions- och objekthantering.
- Generell objektmodell och introspektion.
- music21-specifika adaptrar.
- Import och export.

Det ska vara möjligt att testa huvuddelen av funktionaliteten utan att starta en MCP-klient.

### 2.5 Börja med stdio

Den första versionen ska använda MCP över stdio.

HTTP-transport och stöd för flera samtidiga klienter är inte prioriterat.

## 3. Föreslagen arkitektur

```text
AI Agent
   |
   | MCP
   |
   v
+---------------------------+
| MCP Server                |
|                           |
|  Tools / Resources        |
|          |                |
|          v                |
|  Session Manager          |
|          |                |
|          v                |
|  Object Registry          |
|          |                |
|          v                |
|  Object Model API         |
|          |                |
|          v                |
|  music21 Adapter          |
|          |                |
|          v                |
|       music21             |
+---------------------------+
          |
          v
     MusicXML / MIDI
```

### Session Manager

Ansvarar för öppna dokument och deras livscykel.

### Object Registry

Tilldelar stabila objekt-ID:n och håller reda på relationen mellan dessa och Python-objekten.

Samma Python-objekt ska normalt representeras av samma ID inom en session.

### Object Model API

Implementerar generella operationer för navigation, introspektion, sökning och modifiering.

### music21 Adapter

Ansvarar för music21-specifik semantik, exempelvis:

- `Stream`, `Score`, `Part`, `Measure`
- `Note`, `Rest`, `Chord`
- `Duration`, `Pitch`
- `Lyric`, `Expression`
- `Tie`, `Slur` och andra spanners
- Hierarkiska positioner och offsets
- Import och export

## 4. MCP-verktyg

Det slutliga API:et ska hållas så litet som möjligt.

Följande är en preliminär uppdelning.

### 4.1 Dokumenthantering

| Verktyg | Funktion |
|---|---|
| `document_open` | Läs in MusicXML eller annat format |
| `document_create` | Skapa ett nytt dokument |
| `document_list` | Lista öppna dokument |
| `document_close` | Stäng ett dokument |
| `document_export` | Exportera dokument |

### 4.2 Objektinspektion

| Verktyg | Funktion |
|---|---|
| `object_get` | Hämta ett objekts egenskaper |
| `object_children` | Lista objektets barn |
| `object_parent` | Hämta överordnat objekt |
| `object_query` | Sök efter objekt |
| `object_schema` | Beskriv tillgängliga egenskaper och metoder |

Resultaten ska vara JSON-kompatibla.

Objekt som inte kan representeras direkt som JSON ska returneras som referenser.

Stora samlingar ska stödja paginering.

### 4.3 Objektmodifiering

| Verktyg | Funktion |
|---|---|
| `object_set` | Ändra en egenskap |
| `object_create` | Skapa ett nytt objekt |
| `object_insert` | Infoga objekt i en Stream |
| `object_remove` | Ta bort objekt |
| `object_copy` | Kopiera objekt |
| `object_call` | Anropa en tillåten metod |

`object_call` är särskilt viktigt.

Det ska göra det möjligt att utnyttja music21:s befintliga funktionalitet utan att behöva implementera ett MCP-verktyg för varje metod.

### 4.4 Transaktioner

Det bör finnas stöd för att utföra flera ändringar som en sammanhängande operation.

En första implementation kan erbjuda:

- `transaction_begin`
- `transaction_commit`
- `transaction_rollback`

En transaktion ska antingen genomföras helt eller lämna dokumentet oförändrat.

Den exakta mekanismen för rollback måste utredas. En möjlig implementation är att arbeta med en kopia av dokumentet.

## 5. Objektmodell och serialisering

Detta är sannolikt projektets mest komplicerade del.

music21 innehåller en stor och delvis dynamisk objektmodell.

Vi behöver därför definiera hur Python-objekt representeras i MCP.

### 5.1 Objektbeskrivningar

Ett objekt kan exempelvis representeras så här:

```json
{
  "id": "obj-1042",
  "type": "music21.note.Note",
  "properties": {
    "pitch": {
      "$ref": "obj-1043"
    },
    "quarterLength": 1.0,
    "offset": 2.0
  }
}
```

Referenser ska kunna följas genom nya MCP-anrop.

### 5.2 Introspektion

Servern ska kunna beskriva vilka egenskaper och metoder som finns på en viss objekttyp.

Detta gör det möjligt för en agent att upptäcka funktionalitet dynamiskt.

Vi bör undersöka i vilken utsträckning detta kan genereras automatiskt med:

- `inspect`
- Type hints
- Properties
- Metodsignaturer
- Docstrings

Automatisk introspektion får dock inte innebära att alla upptäckta metoder automatiskt blir tillåtna att anropa.

### 5.3 Objektidentitet

Vi behöver skilja mellan:

- Python-objektets identitet.
- Objektets position i ett partitur.
- Objektets MCP-referens.

Det är särskilt viktigt eftersom ett music21-objekt kan förekomma i olika Stream-kontexter.

### 5.4 Positioner

Musikaliska positioner ska inte representeras enbart med flyttal.

music21 använder bland annat rationella värden för offsets och notlängder.

API:et ska bevara dessa exakt där det är möjligt.

## 6. Säkerhet och robusthet

Servern ska betraktas som en lokal utvecklingskomponent, men ändå ha tydliga säkerhetsgränser.

Krav:

- Ingen godtycklig Python-exekvering.
- Ingen åtkomst till privata attribut som `__dict__`, `__class__` eller liknande via generella verktyg.
- Explicit kontroll av tillåtna metoder.
- Validering av argument och returvärden.
- Begränsning av rekursionsdjup vid serialisering.
- Begränsning av antalet returnerade objekt.
- Kontrollerad hantering av undantag.
- Ingen exponering av interna Python-objekt genom felmeddelanden.

Filåtkomst ska begränsas till uttryckligen tillåtna operationer.

## 7. Föreslagen projektstruktur

```text
music21-mcp/
├── README.md
├── LICENSE
├── pyproject.toml
├── src/
│   └── music21_mcp/
│       ├── __init__.py
│       ├── __main__.py
│       ├── server.py
│       ├── sessions.py
│       ├── registry.py
│       ├── serialization.py
│       ├── introspection.py
│       ├── object_api.py
│       ├── transactions.py
│       └── adapters/
│           ├── __init__.py
│           └── music21.py
├── tests/
│   ├── test_sessions.py
│   ├── test_registry.py
│   ├── test_serialization.py
│   ├── test_introspection.py
│   ├── test_object_api.py
│   └── integration/
├── examples/
│   └── scores/
└── docs/
    ├── architecture.md
    ├── protocol.md
    └── roadmap.md
```

Python 3.12 eller senare föreslås som lägsta version.

Använd:

- `music21`
- Officiella Python-SDK:t för MCP
- `pytest`
- `ruff`
- `mypy` eller `pyright`

Projektet ska använda modern Python-paketering via `pyproject.toml`.

## 8. Utvecklingsplan

### Fas 1 – Teknisk prototyp

**Mål:** Verifiera att grundarkitekturen fungerar.

Implementera:

1. MCP-server över stdio.
2. Inläsning av MusicXML.
3. Sessionshantering.
4. Objektregister.
5. `object_get`.
6. `object_children`.
7. `object_query`.

Verifiera att en agent kan läsa in ett partitur och navigera genom dess struktur.

**Leverans:** En fungerande, skrivskyddad MCP-server.

### Fas 2 – Generell introspektion

**Mål:** Göra objektmodellen självbeskrivande.

Implementera:

1. `object_schema`.
2. Automatisk upptäckt av egenskaper.
3. Metodsignaturer.
4. Docstrings.
5. Typinformation.
6. Generell serialisering av värden och objektreferenser.

Undersök hur stor del av music21:s objektmodell som kan exponeras utan specialkod.

**Leverans:** En agent kan själv upptäcka vilka operationer som är möjliga.

### Fas 3 – Modifiering

**Mål:** Möjliggöra generell redigering.

Implementera:

1. `object_set`.
2. `object_create`.
3. `object_insert`.
4. `object_remove`.
5. `object_copy`.
6. `object_call`.
7. Export till MusicXML.

Börja med en begränsad uppsättning objekt och metoder.

Utöka sedan stödet utifrån faktiska användningsfall.

**Leverans:** En agent kan redigera ett partitur och exportera resultatet.

### Fas 4 – Transaktioner och felhantering

**Mål:** Göra redigeringen robust.

Implementera:

1. Transaktioner.
2. Rollback.
3. Validering av ändringar.
4. Versionshantering av dokument.
5. Hantering av ogiltiga objektreferenser.
6. Förbättrade felmeddelanden.

Undersök även om undo/redo kan implementeras ovanpå transaktionsmekanismen.

**Leverans:** Robust redigering utan risk för partiellt genomförda operationer.

### Fas 5 – Integration med MuseScore

**Mål:** Verifiera användbarheten i ett verkligt arbetsflöde.

Använd MusicXML för att utbyta partitur mellan MuseScore och music21-MCP.

Testa bland annat:

1. Inläsning av ett körpartitur.
2. Identifiering av stämmor.
3. Sökning efter noter på specifika taktslag.
4. Kopiering av sångtext mellan stämmor.
5. Bevarande av textattribut och melismer.
6. Export till MusicXML.
7. Återimport i MuseScore.

Det är viktigt att skilja mellan begränsningar i MCP-servern, music21 och MusicXML-formatet.

**Leverans:** Ett komplett arbetsflöde från MuseScore till music21 och tillbaka.

### Fas 6 – Optimering och utökningar

Först när grundfunktionaliteten fungerar bör vi överväga:

- Batchoperationer.
- Specialiserade musikaliska verktyg.
- MCP Resources.
- HTTP-transport.
- Flera samtidiga sessioner.
- Integration med en MuseScore-MCP.
- Automatiskt genererade verktygsbeskrivningar.
- Mer avancerad frågesemantik.

## 9. Teststrategi

Tester ska i första hand köras direkt mot Python-API:et, utan MCP-transport.

Separata integrationstester ska verifiera att MCP-servern fungerar med en riktig klient.

Särskilt viktiga testfall:

- Objektidentitet vid upprepade sökningar.
- Hierarkiska Stream-strukturer.
- Objekt som förekommer i flera kontexter.
- Exakta musikaliska tidspositioner.
- Kopiering av objekt.
- Hantering av spanners och referenser mellan objekt.
- Import/export utan oavsiktliga förändringar.
- Ogiltiga metodanrop.
- Serialisering av cykliska objektreferenser.
- Stora partitur.
- Transaktioner som misslyckas halvvägs.

Vi bör även ha ett antal MusicXML-filer som regressionstester.

## 10. Viktiga öppna designfrågor

Följande frågor bör undersökas tidigt:

**A. Hur generell ska introspektionen vara?**

Ska vi exponera alla publika music21-egenskaper som standard, eller bara ett uttryckligen godkänt urval?

**B. Hur ska objektidentifiering fungera?**

Ska referenser vara kopplade till Python-objektens identitet eller till deras position i dokumentet?

**C. Hur hanteras objekt som förekommer i flera Streams?**

music21:s modell är inte alltid ett enkelt träd.

**D. Hur hanteras metoder som returnerar nya Streams?**

Ska dessa automatiskt registreras som nya dokument, eller som objekt inom den befintliga sessionen?

**E. Hur ska transaktioner implementeras?**

Djupkopiering av hela partitur är enkel att förstå, men kan bli kostsam och påverka objektidentiteten.

**F. Hur mycket av MusicXML bevaras?**

Vi behöver undersöka vilka notationsdetaljer som music21 inte kan läsa in eller skriva ut utan informationsförlust.

**G. Hur hanteras stora mängder objekt?**

En agent bör inte behöva hämta tusentals noter för att utföra en enkel operation.

**H. Hur uttrycks komplexa sökningar?**

Vi bör överväga ett deklarativt frågespråk som kan uttrycka filtrering på objekttyp, egenskaper, musikalisk position och relationer utan godtycklig Python-kod.

## 11. Definition av första milstolpen

Den första milstolpen ska vara uppnådd när en MCP-klient kan:

1. Starta servern.
2. Öppna en MusicXML-fil.
3. Få tillbaka ett dokument-ID.
4. Lista partiturets stämmor.
5. Lista takterna i en stämma.
6. Lista noterna i en takt.
7. Läsa en nots tonhöjd, längd och position.
8. Söka efter alla noter av en viss typ eller med ett visst attribut.
9. Återanvända tidigare erhållna objektreferenser.

Det ska fungera utan att klienten behöver känna till music21:s interna Python-API.

**Den första milstolpen omfattar ingen redigering.**

Detta ger oss en tydligt avgränsad prototyp som kan användas för att utvärdera arkitekturen innan vi börjar implementera modifieringar.
