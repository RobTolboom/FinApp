# Instellingen met tabs

Datum: 2026-11-14
Branch: `feat/instellingen-tabs`
Status: voorstel, nog niet goedgekeurd
Mock: scherm "1. Instellingen met tabs" en "4. Vakanties" in
<https://claude.ai/artifact/KtMnNFZqaWZQr9S5hP7jZX>

## Doel

Het tabblad Instellingen is één lange pagina waarin onderwerpen door elkaar
staan: onder "Vakantieperiodes" staan ook "Categorie toevoegen", "Opslag" en
de uitleg over herkenningsregels. Met eigen tabs per onderwerp blijft het
scherm overzichtelijk en is er plaats voor de regels-editor (plan
`2026-11-14-regels-in-database.md`) en de woongebied-editor (plan
`2026-11-14-woongebied.md`).

## Omvang

- Binnen Instellingen komt een rij subtabs, onder de hoofdtabs. Deze
  plannen leiden samen tot deze volgorde:
  Rekeningen · Vakanties · Woongebied · Categorieën · Regels · Opslag.
- Dit plan maakt alleen de tabs voor bestaande inhoud:
  - **Rekeningen**: de panelen "Eigen rekeningen" en "Rekeningen".
  - **Vakanties**: "Vakantieperiodes", los van al het andere.
  - **Categorieën**: "Categorie toevoegen". Tot plan 2 klaar is, staat de
    uitleg over herkenningsregels hier ook.
  - **Opslag**: het databasepad en de tip over back-ups.
- De tabs Woongebied en Regels komen er met plan 3 en plan 2 bij.
- De gekozen subtab wordt niet onthouden: na het herladen van de pagina
  opent Instellingen op Rekeningen. Binnen een sessie blijft de keuze
  staan als je naar een ander hoofdtab gaat en terugkomt.
- De subtabs vallen op telefoonbreedte netjes over meerdere regels.

Buiten de omvang: nieuwe instellingen, andere teksten in de panelen (ook
de bankspecifieke teksten in `app.js` blijven voorlopig zoals ze zijn).

## Takenlijst

- [ ] `app/static/app.js`: `S.settingsTab` (standaard `"accounts"`),
      `renderSettings()` opsplitsen in een functie per subtab, en een
      klikhandler op een eigen attribuut (`data-settab`).
- [ ] `app/static/style.css`: stijl voor de subtabs (`.subtabs`), op basis
      van de bestaande kleuren en knoppen.
- [ ] Na de wijziging: `python3 -m py_compile app/*.py` en de app starten
      met een wegwerpdatabase
      (`python3 app/app.py --db /tmp/finapp-test.db --port 8766 --no-browser`).
- [ ] In de browser alle subtabs langslopen, elke bestaande knop één keer
      gebruiken (opslaan, vakantie toevoegen en verwijderen, categorie
      toevoegen, rekening afsluiten en heropenen) en de telefoonbreedte
      bekijken.

## Risico's

- `render()` schakelt elementen met de klasse `.tab` en knoppen met
  `data-tab`. Gebruiken de subtabs dezelfde namen, dan raken hoofd- en
  subtabs door elkaar. Daarom eigen namen: `.subtabs` en `data-settab`.
- Knoppen in de panelen werken via event delegation op `data-…`-attributen.
  Na het opsplitsen moeten ze allemaal nog op dezelfde manier werken; de
  handmatige test hierboven controleert elk ervan.
- Een link vanuit een ander tabblad die nu naar `S.tab = "settings"`
  springt, komt altijd op Rekeningen uit. Waar dat onhandig is, kan de
  link ook `S.settingsTab` zetten.

## Acceptatiecriteria

- Instellingen toont de subtabs Rekeningen, Vakanties, Categorieën en
  Opslag; elke subtab toont alleen zijn eigen panelen.
- Elke bestaande functie op het oude instellingenscherm werkt nog.
- Hoofdtabs en subtabs beïnvloeden elkaar niet.
- Na herladen opent Instellingen op Rekeningen.
- Op telefoonbreedte is er geen horizontale scrollbalk.
- Geen wijziging aan `SCHEMA`, de API of de Python-code.
