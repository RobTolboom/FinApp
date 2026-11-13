# FinApp — werkafspraken

Eigenaar: Rob Tolboom. De gebruiker heeft het laatste woord; is een regel
onduidelijk, vraag dan in plaats van te gokken.

## 1. Goedkeuring

### Vrij: geen goedkeuring nodig
- Bestanden lezen en doorzoeken, git-geschiedenis, logs en documentatie.
- Alleen-lezen commando's: `git status`, `git log`, `git diff`, bestanden
  tonen, `python3 -m py_compile`.
- Dingen opzoeken op het web.

### Eerst een plan, dan uitvoeren
- Presenteer voor elke wijziging een kort plan: wat verandert, in welke
  bestanden, en welke git-commando's erbij horen. Wacht op akkoord.
- Een goedgekeurd plan mag op een topic-branch worden uitgevoerd zonder
  per bewerking opnieuw te vragen.
- Stop en vraag opnieuw zodra het werk afwijkt van het plan: andere
  bestanden, een andere aanpak, grotere omvang, of een onverwachte fout die
  een ontwerpkeuze vraagt.
- Wijzig een goedgekeurd plan nooit op eigen houtje.

### Altijd apart vragen, elke keer opnieuw
- `git commit`, `git push`, een pull request openen of mergen.
- Bestanden of branches verwijderen, geschiedenis herschrijven,
  force-operaties.
- Een externe dependency toevoegen. FinApp draait bewust op alleen de
  Python-standaardbibliotheek en platte HTML/CSS/JS; dat is een
  ontwerpprincipe, geen toeval.
- Het databaseschema wijzigen (`SCHEMA` in `app/app.py`) of bestaande
  gegevens migreren.
- Repository-instellingen of GitHub-workflows aanpassen.
- Alles buiten deze repository, inclusief de productie-installatie op de
  NAS.

Goedkeuring voor de ene actie geldt niet automatisch voor de volgende.

### Nooit
- Direct op `main` committen.
- Persoonlijke gegevens lezen, tonen of committen: de database in `data/`,
  bankexports (`.xml`, `.csv`), IBAN's, namen van personen of werkgevers.
  Dit geldt ook voor voorbeelden in code, tests en documentatie.
- Persoonsgebonden herkenningsregels in `app/rules.py` zetten. Zie
  "Projectcontext".

## 2. Workflows

Begin van een sessie
1. `git switch main && git pull origin main`

Na een codewijziging
1. `python3 -m py_compile app/*.py`
2. De app starten met een wegwerpdatabase en de wijziging in de browser
   controleren:
   `python3 app/app.py --db /tmp/finapp-test.db --port 8766 --no-browser`
3. Bij wijzigingen in `rules.py`: controleren dat alle patronen compileren
   (`re.compile` met `re.I`) en dat elke categorienaam in `CATEGORIES`
   voorkomt.

Voor een commit
1. `git status` nalopen: staat er niets uit `data/` of een bankexport bij?
2. `git diff --staged` lezen.

Voor een push
1. Controleren dat de branch op `main` gebaseerd is en geen conflicten heeft.

## 3. Branches en commits

- `main` is de uitgangsbasis en is op GitHub beschermd: wijzigingen komen
  alleen binnen via een pull request met één goedkeuring, commits moeten
  gesigneerd zijn en de geschiedenis blijft lineair (squash merge).
  Beheerders kunnen die bescherming omzeilen; niet direct op `main`
  committen blijft daarom ook een afspraak.
- Werk op kortlevende topic-branches: `feat/...`, `fix/...`, `docs/...`,
  `refactor/...`, `chore/...`.
- Conventional Commits met Nederlandse omschrijving: `feat: vakanties per
  jaar tonen`, `fix: Amex-bedragen met komma parsen`.
- Commit in kleine, samenhangende stappen.

## 4. Plannen

- Kleine wijzigingen: het plan in het gesprek is genoeg.
- Features en refactors: een plan met doel, omvang, takenlijst, risico's en
  acceptatiecriteria in `docs/plans/JJJJ-MM-DD-onderwerp.md`.
- De implementatie begint pas na expliciete goedkeuring van het plan.

## 5. Wat een pull request moet bevatten

Controleer dit één keer per pull request, niet per bewerking.
- Een beschrijving van wat er verandert, waarom, en hoe het handmatig is
  getest (er zijn nog geen geautomatiseerde tests).
- `README.md` alleen bijwerken als de tekst daar niet meer klopt.
- Bij schemawijzigingen: het schema is additief (`CREATE TABLE IF NOT
  EXISTS`, `setdefault` voor instellingen, `RENAMES` voor categorieën),
  zodat bestaande databases zonder handwerk blijven werken.

## 6. Rapporteren

- Zeg voor een actie die aparte goedkeuring vraagt in één regel wat je gaat
  doen en waarom.
- Rapporteer resultaten zoals ze zijn: fouten met hun uitvoer,
  overgeslagen stappen als overgeslagen, ongeverifieerde beweringen als
  ongeverifieerd.
- Gesprek, code-commentaar, documentatie, commitberichten en
  gebruikersteksten in het Nederlands. Identifiers (functies, variabelen,
  databasekolommen) in het Engels, zoals nu al het geval is.

## 7. Projectcontext

### Wat het is
Een lokale webapp voor persoonlijke financiën: bankafschriften importeren,
transacties categoriseren, vaste lasten, vermogen en hypotheek volgen.
Draait op de eigen computer of in Docker op een NAS. Niets gaat naar
internet.

### Architectuur
- `app/app.py`: `ThreadingHTTPServer` uit de standaardbibliotheek, het
  SQLite-schema (`SCHEMA`), instellingen (JSON per sleutel in tabel
  `settings`) en alle API-routes onder `/api/...`. `GET /api/data` levert
  de volledige dataset aan de frontend; de frontend rekent verder zelf.
- `app/engine.py`: `Categorizer` (regels, handmatige correcties,
  tegenpartij-regels, eigen rekeningen), herkenning van terugkerende lasten
  en vakanties.
- `app/parsers.py`: CAMT.053 (XML, alle Nederlandse banken) en American
  Express CSV. `detect_and_parse` kiest op basis van bestandsinhoud.
- `app/mortgage.py`: hypotheekdelen, rentewijzigingen, correcties.
- `app/rules.py`: standaardcategorieën en herkenningsregels (regex,
  eerste match wint, van boven naar beneden).
- `app/static/`: één `index.html`, één `app.js` (zonder framework, eigen
  SVG-grafieken) en één `style.css`.
- `docker-compose.yml`: `python:3.12-slim` met `app/` read-only gemount.
  Na een codewijziging op de NAS is `docker compose restart` nodig.

### Valkuilen
- Alle bedragen zijn integers in centen (`_cents` in app.py, `eur` in
  app.js). Nooit floats voor geld.
- Transactie-`uid`s zijn hashes van de inhoud; ze maken dubbele imports
  onschadelijk. Wijzig de hash-invoer in `parsers.py` niet zonder
  migratie, anders worden alle bestaande transacties als nieuw gezien.
- `rules.py` moet algemeen bruikbaar blijven: landelijke ketens, banken,
  overheid. Regels voor een werkgever, familie of eigen adres horen in de
  app als tegenpartij-regel (tabel `merchant_rules`) en staan dan alleen
  in de eigen database. Persoonlijke patronen zijn op 2026-11-12 bewust
  verwijderd.
- Omgevingsvariabelen: `FINAPP_DB`, `FINAPP_HOST`, `FINAPP_PORT`,
  `FINAPP_PASSWORD`, `FINAPP_NO_PASSWORD`, `FINAPP_USER`,
  `FINAPP_ALLOWED_HOSTS`. Standaard luistert de app alleen op
  `127.0.0.1`. In thuisnetwerkmodus start de app niet zonder wachtwoord,
  tenzij `FINAPP_NO_PASSWORD=1` is gezet.
- Python 3.9 is de ondergrens (standaard-macOS); gebruik geen nieuwere
  syntaxis zoals `match` of `X | Y` in type-annotaties.
