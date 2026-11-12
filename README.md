# FinApp

Lokaal overzicht van je uitgaven, vaste lasten, vermogen en hypotheek. Je
importeert bankafschriften, FinApp categoriseert de transacties en laat zien
waar je geld naartoe gaat. Alles draait op je eigen computer of NAS; er wordt
niets naar internet verstuurd.

## Wat kan het

- Importeren van **CAMT.053-afschriften** (XML, exporteerbaar bij vrijwel elke
  Nederlandse bank) en **American Express CSV-exports**.
- Automatische categorisering via herkenningsregels (`app/rules.py`), met
  handmatige correcties per transactie of per tegenpartij.
- Terugkerende lasten herkennen, vakanties apart zetten, labels toekennen.
- Saldo- en vermogensverloop, hypotheekdelen met rentewijzigingen.

## Snel starten (lokaal)

Alleen Python 3.9 of nieuwer is nodig, zonder extra pakketten.

```bash
python3 app/app.py
```

De browser opent op `http://127.0.0.1:8765`. De database komt standaard in
`~/Library/Application Support/FinApp/` (macOS) of `~/.finapp/` (Linux).

Opties:

```bash
python3 app/app.py --port 8765 --db /pad/naar/finapp.db --no-browser
```

## Draaien in Docker (bijvoorbeeld op een Synology NAS)

De meegeleverde `docker-compose.yml` gebruikt het standaard `python:3.12-slim`
image en mount de map `app/` en `data/`:

```bash
docker compose up -d
```

Open daarna `http://<ip-van-je-nas>:8765`. Zie de toelichting bovenin
`docker-compose.yml` voor de mappenstructuur in Container Manager.

### Omgevingsvariabelen

| Variabele              | Betekenis                                                     |
|------------------------|---------------------------------------------------------------|
| `FINAPP_DB`            | Pad naar de SQLite-database                                   |
| `FINAPP_HOST`          | Adres om op te luisteren (`0.0.0.0` in Docker)                |
| `FINAPP_PORT`          | Poort (standaard 8765)                                        |
| `FINAPP_PASSWORD`      | Zet basis-authenticatie aan                                   |
| `FINAPP_USER`          | Gebruikersnaam bij `FINAPP_PASSWORD` (standaard `finapp`)     |
| `FINAPP_ALLOWED_HOSTS` | Extra toegestane hostnamen, kommagescheiden                   |

## Projectstructuur

```
app/
  app.py        HTTP-server, database-schema en API
  engine.py     categorisering en analyses
  parsers.py    CAMT.053- en Amex-parsers
  mortgage.py   hypotheekberekeningen
  rules.py      standaardcategorieën en herkenningsregels
  static/       frontend (index.html, app.js, style.css)
data/           je database (staat in .gitignore)
docker-compose.yml
```

## Samen ontwikkelen

- Werk nooit direct op `main`. Maak een branch (`git switch -c mijn-wijziging`),
  push die en open een pull request. Een tweede paar ogen kijkt mee voordat het
  wordt samengevoegd.
- Houd pull requests klein en beschrijf wat er verandert en waarom.
- **Commit nooit persoonlijke gegevens**: geen database, geen bankexports, geen
  IBAN's of namen in code of testbestanden. De `.gitignore` vangt de
  bekende bestandstypen af, maar controleer het zelf ook bij `git status`.
- Nieuwe herkenningsregels in `rules.py` moeten algemeen bruikbaar zijn
  (landelijke winkels, banken, overheidsinstanties). Regels voor je eigen
  werkgever, familie of lokale zaken stel je in de app zelf in via
  tegenpartij-regels; die staan in je eigen database.
- Problemen en ideeën: open een issue in deze repository.

## Licentie

MIT, zie `LICENSE`.
