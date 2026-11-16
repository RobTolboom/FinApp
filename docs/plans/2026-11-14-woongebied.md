# Woongebied in plaats van een vaste plaatsenlijst

Datum: 2026-11-14, herzien op 2026-11-15
Branch: `feat/woongebied`
Status: goedgekeurd op 2026-11-15
Issue: #51
Mock: scherm "3. Woongebied-editor" in
<https://claude.ai/artifact/KtMnNFZqaWZQr9S5hP7jZX> (van vóór de herziening;
de standaardlijst en de tweede schakelaar daarin vervallen)

## Doel

Binnen een opgegeven vakantieperiode gaan pinbetalingen en geldopnames naar
"Reizen & vakantie", behalve in plaatsen die als thuis gelden. Die plaatsen
komen nu uit twee bronnen:

- `NL_CITIES` in `app/engine.py`: een vaste lijst van ongeveer 80 plaatsen,
  naast grote steden ook kleine dorpen en afgekapte namen. Die lijst is op
  eigen transacties gebaseerd en hoort niet in de gedeelde code.
- automatisch leren: een plaats waar buiten vakanties in minstens 3
  verschillende maanden is gepind. Dat gebeurt onzichtbaar en is niet te
  corrigeren.

Na dit plan staat er geen plaatsnaam meer in de code. Het woongebied
bestaat uit de plaatsen die de app leert en de plaatsen die de gebruiker
zelf toevoegt. De gebruiker ziet in een editor welke plaatsen meetellen,
kan plaatsen toevoegen en weghalen, en kan het leren uitzetten.

## Wijzigingen ten opzichte van het eerste voorstel

Besloten op 2026-11-15:

- **Geen meegeleverde lijst van 20 steden.** Thuis is voor iedereen
  anders, en de lijst liet zich niet verifiëren. Daarmee vervallen
  `app/default_places.json`, de herkomst "standaard", de aliassen en de
  knop "Standaardlijst herstellen".
- **Eén schakelaar** (automatisch bijleren). De schakelaar "thuisplaatsen
  uitsluiten" vervalt: uitzetten is hetzelfde als een lege lijst met het
  leren uit.
- **Het leren wordt strenger** (zie "Leren").
- **Plaats toevoegen door te kiezen** uit de plaatsen in de eigen
  transacties.
- **Geautomatiseerde tests.**

## Omvang

### Opslag (geen schemawijziging, geen omzetting)

Drie sleutels in de bestaande tabel `settings`, met `setdefault`:

| Sleutel       | Standaard | Betekenis                                    |
|---------------|-----------|----------------------------------------------|
| `home_learn`  | `true`    | plaatsen automatisch bijleren                |
| `home_places` | `[]`      | zelf toegevoegde plaatsen                    |
| `never_learn` | `[]`      | plaatsen die nooit worden bijgeleerd         |

- Plaatsnamen worden genormaliseerd opgeslagen (zie "Herkennen").
- Geleerde plaatsen worden niet opgeslagen. Ze worden zoals nu bij elke
  berekening afgeleid in `Categorizer.prepare`.
- Een geleerde plaats "vastzetten" voegt hem toe aan `home_places`. Hij
  blijft dan thuis, ook als het leren uit staat of de plaats later onder
  de drempel zakt.
- "Nooit leren" zet een plaats op `never_learn`. Een plaats kan niet
  tegelijk in `home_places` en op `never_learn` staan: toevoegen aan de
  ene lijst haalt hem van de andere.

### Leren

Een plaats is geleerd als er buiten de opgegeven vakanties in minstens 3
verschillende maanden een betaling ter plaatse is gedaan. Dat blijft zo.
Nieuw is welke betalingen meetellen:

- bank: alleen pinbetalingen, zoals nu;
- Amex: niet als het land is ingevuld en niet Nederland is. Is het land
  leeg (transacties van vóór de kolom `country`), dan telt de betaling
  mee, zoals nu;
- geen betalingen die als online worden herkend (het bestaande patroon
  `ONLINE` in `Categorizer`).

Reden: een abonnement dat via een buitenlandse stad wordt afgerekend,
maakt die stad nu na drie maanden thuis. Een vakantie daar telt dan niet
als vakantie.

Staat `home_learn` uit, dan telt alleen `home_places`. Plaatsen op
`never_learn` worden overgeslagen.

De drempel van 3 maanden blijft vast.

### Herkennen van plaatsnamen

- Normaliseren: hoofdletters, apostrofs weg, dubbele spaties samengevoegd
  (`'s-Gravenhage` wordt `S-GRAVENHAGE`, zoals de bank het schrijft).
- Een plaats in een transactie hoort bij het woongebied als:
  - de naam exact gelijk is aan een plaats in het woongebied; of
  - de naam in de transactie is afgekapt: minstens 8 tekens en het begin
    van een plaats in het woongebied (`S-HERTOGENBO` past bij
    `S-HERTOGENBOSCH`); of
  - de naam in de transactie begint met een plaats in het woongebied plus
    een spatie (een toevoeging zoals een provinciecode).

Geleerde plaatsen hebben de schrijfwijze van de bank al en passen dus
vrijwel altijd exact. De twee ruimere regels zijn er voor getypte namen.

### Woongebied-editor (subtab Woongebied van Instellingen)

- Korte uitleg: wat het woongebied doet en hoe het leren werkt.
- De schakelaar "Plaatsen automatisch bijleren".
- Eén lijst "Mijn woongebied" met per plaats de herkomst (zelf toegevoegd
  of geleerd) en het aantal maanden waarin er is betaald.
  - zelf toegevoegd: verwijderen;
  - geleerd: vastzetten, nooit leren.
- Plaats toevoegen: een tekstveld met suggesties uit de plaatsen die in de
  eigen transacties voorkomen, elk met het aantal maanden. Zelf typen kan
  ook.
- Een blok "Nooit leren" met per plaats "weer toestaan".
- De subtab Vakanties verwijst in de uitleg naar het woongebied.

### API

- `GET /api/data` levert `home`:
  - `learn`: de schakelaar;
  - `places`: de zelf toegevoegde plaatsen;
  - `never_learn`;
  - `seen`: de plaatsen uit de transacties die bij het leren meetellen,
    elk met het aantal maanden en of de plaats nu geleerd is.
- `POST /api/home` met `action`: `set_learn`, `add`, `remove`,
  `never_learn`, `allow`. "Vastzetten" is `add`.
- Controle op invoer: een naam is niet leeg en hooguit 40 tekens; hooguit
  200 plaatsen per lijst.

### Bestanden

- `app/engine.py`: `NL_CITIES` weg; `Categorizer` krijgt de drie
  instellingen mee; `prepare` houdt per plaats het aantal maanden bij en
  past de nieuwe regels voor het leren toe; één functie die bepaalt of een
  plaats bij het woongebied hoort.
- `app/app.py`: de drie instellingen, `home` in `GET /api/data`, de route
  `POST /api/home`.
- `app/static/app.js` en `style.css`: de subtab Woongebied; verwijzing
  vanuit Vakanties.
- `tests/test_home.py`: nieuw.
- `tools/telling.py`: nieuw, zie "De bestaande installatie".
- `CLAUDE.md`: de regel over `engine.py` in de architectuur aanvullen.

Buiten de omvang: een straal rond een plaats, coördinaten, de drempel
instelbaar maken, en een eigen thuisland anders dan Nederland voor Amex.

## Takenlijst

1. `app/engine.py`: normaliseren en herkennen van plaatsnamen, het leren
   met de nieuwe regels, `NL_CITIES` weg.
2. `tests/test_home.py`.
3. `app/app.py`: instellingen, `home` in de data, `POST /api/home`.
4. `app/static/app.js` en `style.css`: de subtab.
5. `tools/telling.py`.
6. `CLAUDE.md` bijwerken.
7. Controles, zie "Acceptatiecriteria".

## De bestaande installatie

Er is één bestaande database. De vaste lijst van ongeveer 80 plaatsen
verdwijnt. Plaatsen waar vaak wordt gepind, worden vanzelf geleerd.
Plaatsen uit de oude lijst waar zelden wordt gepind, vallen weg: een
pinbetaling daar binnen een vakantieperiode telt na de update als
vakantie. Door de strengere regels kunnen ook enkele eerder geleerde
plaatsen wegvallen; dat is de bedoeling.

De eigenaar controleert dit zelf, zonder dat de gegevens de computer
verlaten:

- `tools/telling.py` toont alleen aantallen: het aantal transacties per
  categorie en het aantal dat door een vakantie is omgezet. Geen namen,
  bedragen of omschrijvingen. Draaien vóór en na de update en de twee
  uitkomsten vergelijken.
- Is het aantal vakantietransacties gestegen, dan staan de betrokken
  plaatsen in de editor bij de suggesties en zijn ze met één klik toe te
  voegen.

Het script is algemeen gehouden, zodat het ook bij latere wijzigingen te
gebruiken is (bijvoorbeeld #62).

## Risico's

- **Gedrag verandert voor de bestaande database.** Zie hierboven.
- **Nieuwe gebruiker met weinig gegevens.** Met minder dan drie maanden
  aan transacties is er nog niets geleerd. Dat speelt alleen binnen een
  opgegeven vakantieperiode; de editor laat zien welke plaatsen meetellen
  en toevoegen is één klik.
- **Afgekapte namen** kunnen onbedoeld passen: een afgekapte naam kan het
  begin van meerdere plaatsen zijn. Daarom de minimumlengte van 8 tekens.
- **Vakantiebestemming die als thuis wordt geleerd.** Een plek waar je
  elk jaar komt, in drie verschillende maanden en zonder dat die periodes
  als vakantie zijn opgegeven, wordt geleerd. Dat was al zo; nu is het
  zichtbaar en met "nooit leren" te corrigeren.
- **Samenloop met #50.** Beide wijzigen `Categorizer` en voegen een subtab
  toe. Dit plan gaat eerst.
- **Niet getest met echte gegevens.** Alleen met verzonnen transacties.

## Acceptatiecriteria

Geautomatiseerd, in `tests/test_home.py`, met verzonnen transacties:

- een plaats met betalingen in 3 maanden buiten vakanties is geleerd; met
  2 maanden niet;
- betalingen binnen een vakantieperiode tellen niet mee bij het leren;
- online betalingen en Amex-betalingen met een ander land dan Nederland
  tellen niet mee; Amex zonder land wel;
- met `home_learn` uit wordt niets geleerd en telt alleen `home_places`;
- een plaats op `never_learn` wordt niet geleerd;
- een zelf toegevoegde plaats telt als thuis, ook zonder betalingen;
- een pinbetaling in een vakantieperiode gaat naar "Reizen & vakantie",
  behalve in een plaats van het woongebied;
- normaliseren, afgekapte namen (`S-HERTOGENBO`) en een toevoeging na een
  spatie worden herkend; een afgekapte naam korter dan 8 tekens niet;
- de acties van `POST /api/home`, inclusief de controle op invoer en het
  wisselen tussen de twee lijsten.

Handmatig:

- `app/engine.py` bevat geen plaatsnamen meer;
- een bestaande database start zonder handwerk; geen wijziging aan
  `SCHEMA` of `MIGRATIONS`;
- de subtab werkt met een wegwerpdatabase en de nepdata uit
  `tools/demo_data.py`, inclusief de vakantie die het script noemt;
- `tools/telling.py` toont alleen aantallen.
