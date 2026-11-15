# Schemaversie en automatische back-up vóór een migratie

Datum: 2026-11-15
Branch: `feat/schemaversie`
Status: goedgekeurd op 2026-11-15
Issue: #60

## Doel

De database kan nu alleen groeien: nieuwe tabellen en één kolom die bij het
starten wordt toegevoegd als hij ontbreekt. Bestaande gegevens omzetten kan
niet op een nette manier. De app weet niet welke omzettingen al zijn
gedaan, en gaat er iets mis, dan is er geen kopie om op terug te vallen.

Twee geplande wijzigingen hebben dat wel nodig: het transactie-id op de
bankreferentie, en de herkenningsregels in de database (#50).

Na dit plan:

- weet elke database welke versie van het schema hij heeft;
- voert de app bij het starten precies de omzettingen uit die nog
  ontbreken, elk één keer, in vaste volgorde;
- maakt de app vóór de eerste omzetting vanzelf een kopie van de database;
- blijft de database ongewijzigd als een omzetting mislukt;
- weigert de app te starten met een database die nieuwer is dan de code.

Dit plan voegt zelf geen nieuwe gegevens of tabellen toe. Het legt alleen
het mechanisme neer en brengt de twee bestaande omzettingen erin onder.

## Omvang

### Versienummer

- Het versienummer staat in de database zelf, in `PRAGMA user_version`.
  Dat is een getal dat SQLite voor dit doel vrijhoudt; er is geen extra
  tabel nodig. Een database van vóór dit plan heeft vanzelf versie 0.
- In `app/app.py` komt een lijst `MIGRATIONS`: per versie één functie die
  een open verbinding krijgt en de database van de vorige naar die versie
  brengt. De hoogste versie in de lijst is de versie van de code.
- `SCHEMA` blijft de volledige beschrijving van een nieuwe database. De
  kolom `country` verhuist van de losse `ALTER TABLE` naar `SCHEMA`.

### Bij het starten

1. Bestaat de database nog niet of is hij leeg, dan maakt de app hem aan
   met `SCHEMA` en zet het versienummer direct op de versie van de code.
   Geen back-up, geen omzettingen.
2. Is het versienummer hoger dan de versie van de code, dan stopt de app
   met een melding: de database hoort bij een nieuwere versie van FinApp,
   werk de code bij. Dit voorkomt dat oude code op de NAS een al omgezette
   database beschadigt.
3. Is het versienummer lager, dan maakt de app eerst een back-up en voert
   daarna de ontbrekende omzettingen uit.
4. Is het versienummer gelijk, dan gebeurt er niets.

### Back-up

- Gemaakt met `Connection.backup()` uit de standaardbibliotheek. Dat geeft
  een consistente kopie, ook als de database op dat moment in gebruik is.
- Naast de database, met de oude versie en het tijdstip in de naam:
  `finapp.db` wordt `finapp.backup-v0-20261115-203000.db`. Op de NAS komt
  hij dus in dezelfde gekoppelde map `data/` terecht.
- Zelfde bestandsrechten als de database. De naam eindigt op `.db`, zodat
  `.gitignore` en de privacycontrole hem al tegenhouden.
- Eén back-up per start, vóór de eerste omzetting, ook als er meerdere
  omzettingen achter elkaar volgen.
- Lukt de back-up niet (schijf vol, map alleen-lezen), dan stopt de app met
  een melding en wordt er niets omgezet.
- De app ruimt back-ups niet zelf op. Omzettingen komen zelden voor, de
  database is klein, en automatisch bestanden verwijderen is een risico
  dat hier niets oplevert. De melding bij het starten noemt het pad, zodat
  je weet wat je later kunt weggooien.

### Omzettingen uitvoeren

- Elke omzetting draait in één transactie, samen met het ophogen van het
  versienummer. Mislukt ze, dan wordt alles teruggedraaid, blijft het
  versienummer staan en stopt de app met de foutmelding en het pad van de
  back-up.
- Hiervoor opent de app tijdens het omzetten een verbinding met expliciete
  `BEGIN IMMEDIATE` en `COMMIT`. De standaardinstelling van `sqlite3` in
  Python 3.9 begint niet vanzelf een transactie voor `ALTER TABLE`, en
  `executescript` sluit een lopende transactie af; beide zouden de
  terugdraai-garantie ondermijnen.
- De app meldt in de terminal welke omzettingen zijn uitgevoerd.

### Versie 1: de bestaande omzettingen

Versie 1 bevat wat de app nu bij elke start doet:

- de kolom `country` toevoegen als die ontbreekt;
- de plaatsnaam in het naamveld van kaartbetalingen herstellen. Dat loopt
  nu bij elke start langs alle banktransacties. Nieuwe imports krijgen de
  juiste naam al bij het inlezen (`parsers.py`), dus één keer is genoeg.
  Bijkomend voordeel: de start wordt sneller.

Wat bij elke start blijft, omdat het bij `rules.py` hoort en niet bij het
schema: ontbrekende standaardcategorieën toevoegen en `RENAMES` toepassen.
Met #50 verhuizen de regels naar de database; dat plan bepaalt dan wat
hiermee gebeurt.

### Bestanden

- `app/app.py`: `MIGRATIONS`, de controle en de back-up in `Store.__init__`,
  `country` in `SCHEMA`.
- `tests/test_migrations.py`: nieuw, zie "Acceptatiecriteria".
- `CLAUDE.md` en `CONTRIBUTING.md`: de regel "het schema is additief"
  vervangen door de nieuwe werkwijze: een wijziging aan bestaande gegevens
  is een nieuwe genummerde omzetting, een bestaande omzetting wordt nooit
  meer aangepast.
- `README.md`: korte alinea over de automatische back-up en waar die staat.

Buiten de omvang:

- een back-up downloaden of terugzetten vanuit de app (#17). De functie
  die de kopie maakt, is daar wel voor te hergebruiken;
- terugzetten naar een oudere versie. De weg terug is de back-up;
- het transactie-id op de bankreferentie en de regels in de database. Die
  krijgen elk een eigen plan en worden versie 2 en verder;
- back-ups automatisch opruimen.

## Takenlijst

1. `country` in `SCHEMA`; `MIGRATIONS` met versie 1; controle op het
   versienummer in `Store.__init__`.
2. Back-up vóór de eerste omzetting, met melding in de terminal.
3. Omzettingen in een transactie met het versienummer; nette foutmelding.
4. Weigeren bij een database die nieuwer is dan de code.
5. `tests/test_migrations.py`.
6. `CLAUDE.md`, `CONTRIBUTING.md` en `README.md` bijwerken.
7. Handmatige controle met nepdata (zie onder).

## Risico's

- **De overgang zelf raakt elke bestaande database.** Bij de eerste start
  na deze wijziging gaat elke database van versie 0 naar 1. Versie 1 doet
  alleen wat de app nu al bij elke start doet, en er staat een back-up
  naast. Het is ook de eerste echte proef van het mechanisme, met een
  omzetting die weinig kwaad kan.
- **Twee beschrijvingen van het schema.** Een nieuwe database komt uit
  `SCHEMA`, een bestaande uit de omzettingen. Lopen die uiteen, dan
  verschillen databases onderling. Een test vergelijkt daarom de structuur
  van een nieuwe database met die van een omgezette oude.
- **Oude code op de NAS.** `app/` is daar gekoppeld; wordt de code op de
  Mac bijgewerkt en de database heen en weer gekopieerd, dan kan oude code
  een nieuwere database treffen. Die start dan niet, met een duidelijke
  melding. Dat is bedoeld, maar wel nieuw gedrag.
- **Back-ups bevatten persoonlijke gegevens.** Ze staan alleen naast de
  database en gaan nergens heen, maar het zijn extra kopieën. De README
  noemt dit.
- **Samenloop met #50.** Jeroens plan wijzigt het schema ook. Dit plan
  moet eerst gemerged zijn; daarna wordt zijn wijziging versie 2 of 3. Dat
  moet met hem worden afgestemd voordat hij verder bouwt.
- **Niet getest met echte gegevens.** Alleen met nepdata en een nagebouwde
  oude database. De eerste start op de echte database doet de eigenaar
  zelf; de back-up is daar het vangnet.

## Acceptatiecriteria

Geautomatiseerd, in `tests/test_migrations.py`, met verzonnen gegevens:

- een nieuwe database krijgt direct de versie van de code, zonder back-up;
- een database van versie 0 zonder kolom `country` wordt omgezet naar
  versie 1, en er staat een back-up naast met de oude inhoud en versie 0;
- een database van versie 0 die `country` al heeft, wordt ook zonder fout
  omgezet;
- een tweede start doet niets: geen nieuwe back-up, zelfde versie;
- een omzetting die halverwege een fout geeft, laat gegevens en
  versienummer ongewijzigd;
- een database met een hoger versienummer dan de code wordt geweigerd en
  niet aangeraakt;
- mislukt de back-up, dan wordt er niets omgezet;
- de structuur van een nieuwe database is gelijk aan die van een omgezette.

Handmatig:

- de bestaande tests blijven slagen op Python 3.9 en 3.12;
- een database gemaakt met de code van `main` en gevuld met
  `tools/demo_data.py` start na de wijziging zonder fout, toont dezelfde
  transacties en categorieën, en heeft een back-up ernaast;
- de app start en werkt in de browser met een wegwerpdatabase.

## Besluiten

Genomen op 2026-11-15:

- Bij een database die nieuwer is dan de code weigert de app te starten;
  alleen waarschuwen is niet genoeg.
- De app ruimt back-ups nooit zelf op.
- De volgorde ten opzichte van #50 is daar voorgelegd: dit plan eerst,
  daarna wordt de wijziging van #50 een volgende versie.
