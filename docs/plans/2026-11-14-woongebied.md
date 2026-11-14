# Woongebied in plaats van een vaste plaatsenlijst

Datum: 2026-11-14
Branch: `feat/woongebied`
Status: voorstel, nog niet goedgekeurd
Afhankelijk van: `2026-11-14-instellingen-tabs.md` (de subtab Woongebied)
Mock: scherm "3. Woongebied-editor" in
<https://claude.ai/artifact/KtMnNFZqaWZQr9S5hP7jZX>

## Doel

Binnen een opgegeven vakantieperiode gaan pinbetalingen en geldopnames naar
"Reizen & vakantie", behalve in plaatsen die als thuis gelden. Die plaatsen
komen nu uit twee bronnen:

- `NL_CITIES` in `app/engine.py`: een vaste lijst van ongeveer 80 plaatsen,
  naast grote steden ook kleine dorpen en afgekapte namen. Die lijst is op
  eigen transacties gebaseerd en hoort niet in de gedeelde code.
- automatisch leren: een plaats waar buiten vakanties in minstens 3
  verschillende maanden is gepind. Dat gebeurt onzichtbaar.

Na dit plan levert de app alleen de 20 grootste woonplaatsen van Nederland
mee als data. De gebruiker beheert het woongebied zelf in een editor, ziet
welke plaatsen zijn bijgeleerd en kan het uitsluiten en het leren aan- en
uitzetten.

## Omvang

### Data uit de code

- `app/default_places.json`: de 20 grootste woonplaatsen, elk met een naam
  en optionele aliassen (bijvoorbeeld Den Haag met `'s-Gravenhage`).
- `NL_CITIES` verdwijnt uit `app/engine.py`.
- Een straal rond een plaats valt buiten dit plan, en daarmee ook een
  databestand met coördinaten.

### Opslag (geen schemawijziging)

Vier sleutels in de bestaande tabel `settings`, met `setdefault`:

| Sleutel        | Standaard                       | Betekenis                                  |
|----------------|---------------------------------|--------------------------------------------|
| `home_exclude` | `true`                          | thuisplaatsen uitsluiten bij vakanties     |
| `home_learn`   | `true`                          | plaatsen automatisch bijleren              |
| `home_places`  | de lijst uit `default_places.json` | `[{name, aliases, origin}]`, `origin` is `standard` of `own` |
| `never_learn`  | `[]`                            | plaatsen die nooit worden bijgeleerd       |

- Geleerde plaatsen worden niet opgeslagen. Ze worden zoals nu bij elke
  berekening afgeleid (`Categorizer.prepare`), minus de lijst `never_learn`.
- Een geleerde plaats "vastzetten" voegt hem toe aan `home_places` als
  `own`; "nooit leren" zet hem op `never_learn`.
- "Standaardlijst herstellen" voegt de ontbrekende standaardplaatsen weer
  toe en laat eigen plaatsen staan.

### Herkennen van plaatsnamen

- Vergelijken in hoofdletters, na normaliseren van apostrofs en dubbele
  spaties (`'s-Gravenhage` → `S-GRAVENHAGE`, zoals in de transacties).
- Een plaats in een transactie past bij een woongebied-plaats als:
  - de naam of een alias exact gelijk is; of
  - de transactienaam is afgekapt: minstens 8 tekens, en het begin van de
    naam of alias (`S-HERTOGENBO` past bij `S-HERTOGENBOSCH`); of
  - de transactienaam begint met de naam plus een spatie (een toevoeging
    zoals een provinciecode).

### Woongebied-editor (subtab Woongebied)

- Twee schakelaars: "Plaatsen in mijn woongebied uitsluiten bij vakanties"
  en "Plaatsen automatisch bijleren" (met de uitleg over 3 maanden).
- Eén lijst met alle plaatsen en hun herkomst (standaard, zelf toegevoegd,
  geleerd), het aantal maanden waarin er is gepind, en filters per herkomst.
  - standaard: verwijderen
  - zelf toegevoegd: wijzigen, verwijderen
  - geleerd: vastzetten, nooit leren
- Plaats toevoegen: een tekstveld, met de uitleg over afgekapte namen.
- Een blok "Nooit leren" met de knop "weer toestaan".
- De knop "Standaardlijst herstellen".
- De subtab Vakanties verwijst in de uitleg naar het woongebied.

### API

- `GET /api/data` levert `home`: de schakelaars, `home_places`,
  `never_learn` en de geleerde plaatsen met het aantal maanden.
- `POST /api/home` met `action`: `set` (schakelaars), `add`, `rename`,
  `remove`, `pin` (geleerd → eigen), `never_learn`, `allow`,
  `restore_defaults`.

### De 20 grootste woonplaatsen

Voorlopige lijst, **nog niet geverifieerd**:

Amsterdam, Rotterdam, Den Haag (alias `'s-Gravenhage`), Utrecht, Eindhoven,
Groningen, Tilburg, Almere, Breda, Nijmegen, Apeldoorn, Haarlem, Arnhem,
Enschede, Amersfoort, Zwolle, 's-Hertogenbosch (alias `Den Bosch`), Leiden,
Zoetermeer, Maastricht.

Twijfelgevallen rond plaats 18–22: Dordrecht, Leeuwarden, Zaandam,
Hoofddorp. Let op het verschil tussen woonplaats en gemeente (Zaandam en
Zaanstad, Hoofddorp en Haarlemmermeer). De CBS-tabel "Woonplaatsen in
Nederland" bevat geen inwonertallen. De lijst moet daarom worden getoetst
aan een bron met inwoners per woonplaats, bijvoorbeeld de
BAG-woonplaatsen gecombineerd met CBS-cijfers per buurt.

Buiten de omvang: een straal rond een plaats, coördinaten, plaatsen in het
buitenland, en de drempel van 3 maanden instelbaar maken.

## Takenlijst

- [ ] De lijst van 20 woonplaatsen verifiëren en `app/default_places.json`
      maken.
- [ ] `app/engine.py`: `NL_CITIES` weghalen; `Categorizer` krijgt de
      woongebied-instellingen mee; de herkenningsregels voor plaatsnamen
      hierboven; `prepare` houdt per plaats het aantal maanden bij en slaat
      `never_learn` over; `home_exclude` en `home_learn` respecteren.
- [ ] `app/app.py`: de vier instellingen met `setdefault`, `home` in
      `GET /api/data`, route `POST /api/home`.
- [ ] `app/static/app.js` en `style.css`: subtab Woongebied volgens de
      mock; verwijzing vanuit Vakanties.
- [ ] `CLAUDE.md` bijwerken waar nodig (architectuur, `engine.py`).
- [ ] Controles: `py_compile`; testen met een wegwerpdatabase en
      verzonnen transacties: een vakantie met pinbetalingen in een
      standaardplaats, een geleerde plaats, een eigen plaats, een afgekapte
      naam en een plaats op `never_learn`; beide schakelaars uit en aan;
      standaardlijst herstellen.

## Advies voor de bestaande installatie

Er is één bestaande database. De vaste lijst krimpt van ongeveer 80 naar
20 plaatsen. Plaatsen die daardoor wegvallen en niet worden bijgeleerd,
kunnen oude vakantietransacties anders laten categoriseren.

Advies aan de eigenaar, uit te voeren na de update en apart goed te keuren:
neem de weggevallen plaatsen eenmalig op als "zelf toegevoegd", via de
editor of met een klein script dat niet wordt gecommit. Vergelijk vooraf
en achteraf het aantal transacties in "Reizen & vakantie".

## Risico's

- **Afgekapte namen** kunnen onbedoeld passen: een korte afgekapte naam kan
  het begin van meerdere plaatsen zijn. Daarom de minimumlengte van 8
  tekens; de editor toont welke plaatsen meetellen.
- **Gedrag verandert voor de bestaande database.** Zie het advies
  hierboven.
- **Aliassen** zijn nodig voor plaatsen met twee schrijfwijzen; ontbreekt
  er een, dan wordt die plaats niet herkend.
- **De lijst van 20** is nog niet geverifieerd.

## Acceptatiecriteria

- `app/engine.py` bevat geen plaatsnamen meer.
- Een nieuwe database begint met de 20 woonplaatsen uit
  `default_places.json`; een bestaande database start zonder handwerk.
- Met `home_exclude` uit tellen pinbetalingen in een vakantieperiode
  altijd als vakantie (met de bestaande uitzonderingen: online, Amex in
  Nederland).
- Met `home_learn` uit worden geen plaatsen bijgeleerd.
- Een plaats op `never_learn` wordt niet bijgeleerd; "weer toestaan" draait
  dat terug.
- Vastzetten maakt van een geleerde plaats een eigen plaats.
- Afgekapte namen zoals `S-HERTOGENBO` worden herkend.
- "Standaardlijst herstellen" voegt ontbrekende standaardplaatsen toe en
  laat eigen plaatsen staan.
- Geen wijziging aan `SCHEMA`.
