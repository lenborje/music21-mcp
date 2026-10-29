# Fas 2: generell introspektion

## Undersökning och beslut

Undersökt mot music21 10.5.2 före implementationen. Objektmodellen använder
Python-properties, _DOC_ATTR, klassannotationer, slots och dynamiska
instansattribut. Exempelvis är Note.pitch ett instansattribut dokumenterat i
_DOC_ATTR, medan quarterLength är en ärvd property med annoterad getter.
Tie.type är en slot. DurationTuple är en namedtuple, inte ProtoM21Object.
Pitch, Duration, Lyric, Tuplet, Accidental och Articulation är ProtoM21Object,
men inte Music21Object/Stream-element.

Primärkällor:
- https://music21.org/music21docs/developerReference/documenting.html
- https://docs.python.org/3.12/library/inspect.html

Schema och läspolicy skiljs åt. Statiskt upptäckta publika egenskaper/metoder
blir beskrivbara metadata, men bara explicit granskade läsegenskaper kan läsas
med object_get/projektion. Metoder är aldrig anropbara i fas 2. Privata namn,
moduler, klasser och godtyckliga Python-objekt publiceras inte som värden.

Schemahämtning ska inte köra properties, användardefinierade descriptors,
__dir__ eller metoder,
skapa standardinstanser eller ändra activeSite. Klassernas MRO och namespaces
undersöks statiskt. För befintliga objekt kan instansens lagrade fältnamn
upptäckas via den inbyggda __dict__-descriptorn utan dynamisk attributåtkomst.
Lagrade värden används bara för att ange deras typ, aldrig för att exponera
värdet eller anropa dess repr. Typannotationer visas som text utan
utvärdering; forward references behöver därför inte kunna importeras/upplösas.
Vid Python >=3.14 läses annotationer statiskt ur deklarationernas AST, utan
annotationlib-anrop. En oannoterad funktionskopia med samma argumentlayout
används av inspect.signature; dess kropp anropas aldrig. Ett riktat test visade
att även annotationlib.Format.STRING kunde exekvera uttryck, vilket därför
inte används. Om källkod saknas blir annotationen okänd. Defaultargument beskrivs bara när de är
skalära litteraler; godtycklig repr körs inte.

object_schema kan användas utan mål för typkatalogen, med type_name för en
registrerad typ eller med document_id/object_id för en faktisk instans.
Objektscheman kan även beskriva konkreta underklasser som inte har ett eget
kortnamn i katalogen. Inga typer importeras från klientsträngar. Schemat
redovisar ursprung, docs, annotationer, begränsningar och läs-/anropsbehörighet.
Medlemmar pagineras och svaren storleksbegränsas. Dokumentation trunkeras
uttryckligen; frånvaro av annotation betyder okänd typ, inte Any-behörighet.

Serialisering behåller tidigare referenser, samlingsformat och rationella
tider. ProtoM21Object blir den generella referensgränsen för musikobjekt.
Utvalda ytterligare musikaliska värden publiceras via granskade fält, inte
genom att godtyckligt returnera allt introspektionen hittar. Strängnycklade
mappningar, enumvärden och music21:s DurationTuple får begränsad strukturerad
serialisering. Okända objekt, rekursion eller ogiltiga tal ger kontrollerade fel.


## Mätt täckning

Följande klasscheman mättes utan att skapa instanser, med music21 10.5.2.
Data omfattar både properties och attribut; alla publika Python-metoder som
hittas beskrivs men ingen kan anropas. Siffrorna är versionsberoende.

| Typ | Upptäckta datafält | Metoder | Godkända läsfält | Automatiskt upptäckta läsfält | Läsfält med deklarerad typ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Note | 46 | 29 | 8 | 8 | 4 |
| Pitch | 26 | 21 | 8 | 8 | 7 |
| Duration | 16 | 13 | 5 | 5 | 5 |
| Tie | 7 | 0 | 3 | 3 | 0 |
| Score | 50 | 138 | 0 | 0 | 0 |
| Tuplet | 12 | 5 | 7 | 2 | 2 |

Typkatalogen innehåller 29 granskade typer. För Note, Pitch, Duration och Tie
kan alla godkända fältnamn upptäckas utan en typunik schemabeskrivning. Däremot
behövs fortfarande läspolicyn för att avgöra vad som är säkert att hämta.
Score saknar godkända objektegenskaper; innehållet nås via children/query.

Tuplet konstruerar flera attribut dynamiskt. Klasschemat kan bara namnge fem
av dess godkända fält tack vare läspolicyn (source=adapter), medan instansschemat
hittar dem i lagringen. DurationTuple har egna namedtuple-descriptors och
beskrivs genom adapterfält. Instrument och Articulation har liknande dynamiska
fält. Spanner.spannedElements är en virtuell, granskad relation. Introspektion
kan alltså inte ersätta alla adaptrar utan att exekvera bibliotekskod.

Annotationer är inte tillräckliga för ett komplett starkt typat API. Tie:s
slots saknar exempelvis deklarerade typer. Note.pitch har dokumentation men
ingen getter-/klassannotation; ett instansschema kan ange stored_type=Pitch
utan att köra en getter. Konstruktorargument används inte som returtyper,
eftersom exempelvis Note(pitch="C4") tar en sträng men lagrar ett Pitch-objekt.
Inga standardinstanser skapas för att försöka fylla sådana luckor.

## Verifiering och praktiska gränser

Automatiska tester kontrollerar att schemat kan styra en riktig MCP-klients
läsning: läsbara namn från object_schema används i projektion och jämförs med
object_get. Nya värdeobjekt kan följas och beskrivas med samma handtag.
Tester täcker även ärvning, slots, instansfält, signaturers parameterkategorier,
forward references, farlig repr, kastande getters och uppskjutna annotationer.
Schema får inte byta activeSite eller registrera nya objekt.

Samtliga 28 tester passerade på Python 3.12 och 3.14, inklusive riktig
stdio-transport. Ruff, formatering och mypy passerade.
Python 3.14-testet verifierar statisk läsning av uppskjutna annotationer och
att annotationernas uttryck inte utvärderas. Dokumenterade gränser för
medlemsantal, byte, text, parametrar och containrar verifieras separat.

Ingen garanti ges att alla publika fält kan hittas: dolda/dynamiska descriptors,
namn utan deklaration eller redan lagrad instans och specialiserade metadata-
system kan saknas. Okända annotationer blir null, och docstrings kan saknas.
Generella biblioteksvärden som inte är stödda värden eller ProtoM21Object
nekas fortsatt; nya läsegenskaper behöver granskas även när ett schema finns.
