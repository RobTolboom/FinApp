# Regels en categorieën uit de code, met regels-editor

Datum: 2026-11-14
Branch: `feat/regels-in-database`
Status: voorstel, nog niet goedgekeurd
Afhankelijk van: `2026-11-14-instellingen-tabs.md` (de subtab Regels)
Mock: scherm "2. Regels-editor" in
<https://claude.ai/artifact/KtMnNFZqaWZQr9S5hP7jZX>

## Doel

Herkenningsregels en categorieën staan nu als Python-code in
`app/rules.py`. Daardoor:

- kan een gebruiker eigen regels alleen toevoegen door de code te wijzigen;
- belanden persoonlijke patronen (lokale zaken, eigen financiële
  producten) gemakkelijk in de gedeelde code;
- werkt aanpassen op de NAS niet, omdat `app/` daar read-only is gemount.

Na dit plan staan alle regels en categorieën in de eigen database. De app
levert een algemene standaardset mee als data, en `rules.py` bevat alleen
nog de logica om regels te toetsen, te valideren en te testen. Eigen regels
beheer je in een editor in de app.

## Omvang

### Data uit de code

- `app/default_rules.json`: de standaardregels. Elke regel heeft een vaste
  `id`, een `group` (de huidige kopjes zoals "vaste lasten"), `mode`
  (`contains` of `regex`), `pattern`, `category` en optioneel `source`
  (`bank`/`amex`) en `sign` (`in`/`out`).
- `app/default_categories.json`: de standaardcategorieën (naam, soort,
  kleur), `renames` (nu `RENAMES`) en per categorie
  `exclude_from_averages` (nu `EXCLUDE_FROM_AVERAGES`).
- `app/rules.py` houdt alleen logica: de JSON-bestanden laden, een regel
  valideren en compileren, toetsen en testen. `CATEGORIES`, `RENAMES`,
  `EXCLUDE_FROM_AVERAGES` en `RULES` verdwijnen eruit. Een apart
  `rules_personal.py` komt er niet.

### Standaardset opschonen

- Bij het omzetten naar `default_rules.json` wordt elk patroon beoordeeld:
  landelijke ketens, banken, overheid en algemene woorden blijven; lokale
  zaken, eenmalige leveranciers, beroepsgebonden en andere persoonsgebonden
  patronen gaan niet mee.
- De beoordeling per patroon staat in de beschrijving van de pull request,
  zodat de eigenaar ze kan nalopen. Dit planbestand herhaalt de patronen
  bewust niet.

### Database

Additieve schemawijziging (aparte goedkeuring nodig volgens `CLAUDE.md`):

```sql
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin TEXT,          -- 'standard' of 'personal'
    std_id TEXT UNIQUE,   -- id uit default_rules.json, NULL bij eigen regels
    grp TEXT,
    mode TEXT,            -- 'contains' of 'regex'
    pattern TEXT,
    category TEXT,
    source TEXT,          -- '', 'bank' of 'amex'
    sign TEXT,            -- '', 'in' of 'out'
    enabled INTEGER DEFAULT 1,
    sort INTEGER
);
```

- Bij het opstarten werkt de app de standaardregels bij aan de hand van
  `std_id`: nieuwe toevoegen, gewijzigde bijwerken, verdwenen weghalen.
  `enabled` blijft daarbij altijd staan. Eigen regels worden nooit
  aangeraakt.
- Categorieën: de tabel `categories` bestaat al. Ontbrekende
  standaardcategorieën worden, net als nu, aangevuld vanuit
  `default_categories.json`; `renames` werkt zoals `RENAMES` nu.
  `exclude_from_averages` wordt bij het laden uit het JSON-bestand gelezen;
  daar komt geen kolom voor.

### Volgorde van toetsen

1. handmatig per transactie (`tx_overrides`)
2. tegenpartij-regels (`merchant_rules`)
3. eigen rekeningen en namen
4. **eigen regels**, van boven naar beneden
5. standaardregels die aan staan, in de volgorde van het JSON-bestand

De categorisering geeft als reden "eigen regel" bij stap 4. Een
tegenpartij-regel krijgt de reden "tegenpartij-regel"; die heet nu ook
"eigen regel" en zou anders verwarrend zijn.

### Regels-editor (subtab Regels)

- **Eigen regels**: tabel met sleepgreep, volgnummer, patroon met het label
  `bevat` of `regex`, categorie, voorwaarden, het aantal treffers, en de
  knoppen eerste, laatste, bewerken en verwijderen. De volgorde kan met
  slepen worden gewijzigd; de knoppen eerste en laatste werken ook zonder
  muis.
- **Regel toevoegen of bewerken**: een tekstveld, de keuze "bevat deze
  tekst" (standaard) of "reguliere expressie", categorie, richting
  (af/bij/beide) en bron (bank/Amex/beide). De knop Testen toont het aantal
  geraakte transacties en de eerste 10: datum, tegenpartij, bedrag, de
  huidige categorie met reden en de nieuwe categorie. Een transactie met
  een handmatige keuze of tegenpartij-regel is zichtbaar gemarkeerd als
  "gaat voor".
- **Tegenpartij-regels**: een lijst van de bestaande `merchant_rules`
  (tegenpartij, categorie, aantal transacties) met de knoppen verwijderen
  en "omzetten naar eigen regel". Omzetten maakt een eigen regel met
  `mode = contains` op de tegenpartij en verwijdert de tegenpartij-regel.
- **Standaardregels**: alleen-lezen, gegroepeerd per `grp`, met een
  aan/uit-vinkje per regel, een zoekveld, het filter "alleen uitgezette" en
  de knop "kopiëren als eigen regel" om een standaardregel aan te passen.

### API

- `GET /api/data` levert `rules` (alle regels met `origin`, `enabled` en het
  aantal treffers) en de tegenpartij-regels als lijst.
- `POST /api/rules` met `action`: `add`, `update`, `delete`, `move`
  (naar positie, eerste of laatste), `toggle` (alleen standaardregels),
  `test` (rekent niets op, geeft treffers terug) en `from_merchant`.

### Veiligheid van patronen

- `contains` wordt intern `re.escape(tekst)`; de gebruiker hoeft geen regex
  te kennen.
- Elk patroon wordt bij opslaan gevalideerd: niet leeg, maximaal 200
  tekens, `re.compile(…, re.I)` moet slagen. Een fout komt als melding
  terug en wordt niet opgeslagen.
- Patronen worden in het scherm altijd met `esc()` getoond.
- Een regex voert geen code uit. Een patroon met extreem veel
  terugzoekwerk kan de app wel traag maken; de lengtegrens, de testknop
  en het feit dat alleen ingelogde gebruikers regels kunnen opslaan,
  beperken dat.

Buiten de omvang: categorieën bewerken of verwijderen in de app, en
`exclude_from_averages` instelbaar maken.

## Takenlijst

- [ ] `app/default_categories.json` en `app/default_rules.json` maken
      vanuit de huidige `rules.py`, met de opschoning hierboven.
- [ ] `app/rules.py` herschrijven tot laad-, validatie- en testlogica.
- [ ] `app/app.py`: tabel `rules` in `SCHEMA`, synchronisatie van de
      standaardregels en categorieën bij het opstarten, `rules` en
      tegenpartij-regels in `GET /api/data`, route `POST /api/rules`.
- [ ] `app/engine.py`: `Categorizer` krijgt de regels uit de database mee
      in plaats van `default_rules.RULES`; nieuwe stap "eigen regel" en de
      reden "tegenpartij-regel".
- [ ] `app/static/app.js` en `style.css`: subtab Regels met de vier
      blokken uit de mock; de uitleg over herkenningsregels verhuist van
      Categorieën naar deze subtab.
- [ ] `CLAUDE.md`, `CONTRIBUTING.md` en `README.md` bijwerken waar ze
      `rules.py` als plek voor regels noemen; de controlestap "patronen
      compileren" geldt voortaan voor `default_rules.json`.
- [ ] Controles na de wijziging: `py_compile`, alle patronen in
      `default_rules.json` compileren met `re.I`, elke categorie in
      `default_rules.json` bestaat in `default_categories.json`.
- [ ] Testen met een wegwerpdatabase en verzonnen transacties: nieuwe
      database; een database die met de huidige versie is gemaakt; regel
      toevoegen, testen, slepen, eerste/laatste, bewerken, verwijderen; een
      standaardregel uit- en weer aanzetten; een ongeldige regex; een
      tegenpartij-regel omzetten.

## Advies voor de bestaande installatie

Er is één bestaande database. Na het opschonen van de standaardset worden
transacties die nu door een persoonlijk patroon worden herkend, anders
gecategoriseerd. Advies aan de eigenaar, uit te voeren na de update en
apart goed te keuren:

1. Voor de update een back-up van de database maken.
2. Na de update de patronen die niet in `default_rules.json` zijn
   meegegaan, als eigen regels toevoegen: via de editor, of eenmalig met
   een klein script dat de oude `RULES` vergelijkt met de nieuwe
   standaardset en de verschillen als `origin = 'personal'` invoegt. Dat
   script wordt niet gecommit en draait alleen op de eigen database.
3. Met de testknop een paar regels steekproefsgewijs nalopen.

## Risico's

- **Gedrag verandert voor de bestaande database.** Zie het advies
  hierboven; zonder die stap verschuiven categorieën.
- **Synchronisatie van standaardregels.** Een fout in de vergelijking op
  `std_id` kan aan-/uitkeuzes laten verdwijnen. Daarom: nooit `enabled`
  overschrijven, en eigen regels nooit raken.
- **Volgorde van de standaardregels** doet ertoe (eerste match wint). Bij
  het omzetten naar JSON moet de volgorde exact gelijk blijven aan de
  huidige `RULES`.
- **Prestaties**: de regels worden één keer per verzoek gecompileerd, zoals
  nu. Een test over alle transacties is een volledige doorloop; bij enkele
  duizenden transacties is dat ruim snel genoeg.
- **Schemawijziging**: additief (`CREATE TABLE IF NOT EXISTS`); een oudere
  versie van de app negeert de nieuwe tabel.

## Acceptatiecriteria

- `app/rules.py` bevat geen patronen of categorieën meer.
- Een nieuwe database krijgt de standaardcategorieën en -regels uit de
  JSON-bestanden.
- Een bestaande database start zonder handwerk; handmatige keuzes en
  tegenpartij-regels blijven werken.
- Eigen regels kunnen worden toegevoegd, bewerkt, verwijderd en
  verplaatst (slepen, eerste, laatste), en gaan voor de standaardregels.
- Een standaardregel kan uit en weer aan; die keuze blijft staan na een
  herstart en na een update van `default_rules.json`.
- De testknop toont het aantal treffers en de eerste 10, zonder iets op te
  slaan.
- Een ongeldig of te lang patroon geeft een duidelijke melding.
- Tegenpartij-regels zijn zichtbaar, te verwijderen en om te zetten naar een
  eigen regel.
- Op de NAS (read-only `app/`) werkt de editor.
- De standaardset bevat geen persoonsgebonden patronen.
