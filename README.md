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
image en mount de map `app/` en `data/`.

Vul eerst een wachtwoord in bij `FINAPP_PASSWORD` in `docker-compose.yml`.
Zodra FinApp vanaf het thuisnetwerk bereikbaar is, start het niet zonder
wachtwoord; de melding daarover staat in `docker compose logs`. Wie bewust
zonder wachtwoord wil draaien, zet `FINAPP_NO_PASSWORD=1`. Start daarna:

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
| `FINAPP_PASSWORD`      | Wachtwoord voor inloggen; verplicht op het thuisnetwerk       |
| `FINAPP_NO_PASSWORD`   | `1`: bewust zonder wachtwoord draaien op het thuisnetwerk     |
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

Zie `CONTRIBUTING.md` voor de werkwijze (branches, pull requests,
ontwerpprincipes) en vooral de regel dat er nooit persoonlijke gegevens in de
repository komen. Problemen en ideeën: open een issue.

## Licentie

FinApp is beschikbaar onder de [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)-licentie,
zie `LICENSE`. In het kort:

- Je mag de code lezen, de app installeren, draaien en aanpassen voor
  persoonlijk en ander niet-commercieel gebruik, en de software delen zolang
  deze licentie meegaat.
- Commercieel gebruik door anderen is niet toegestaan: niet verkopen, niet
  als betaalde dienst aanbieden, niet verwerken in een commercieel product.
- De FinApp-ontwikkelaars houden het recht om de software zelf tegen betaling
  of tegen een donatie aan te bieden, bijvoorbeeld als kant-en-klare
  applicatie voor wie niet met code wil werken.

Bijdragen zijn welkom; zie `CONTRIBUTING.md` voor de voorwaarden.
