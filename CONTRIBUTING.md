# Bijdragen aan FinApp

Fijn dat je meebouwt. FinApp is een klein project van vrienden; deze
afspraken houden het overzichtelijk en voorkomen dat er per ongeluk
persoonlijke financiële gegevens op GitHub belanden.

## De belangrijkste regel: geen persoonlijke gegevens

Commit nooit:
- je database (`data/finapp.db` of een andere `.db`);
- bankexports (`.xml`, `.csv`);
- IBAN's, namen van personen, werkgevers of je adres, ook niet in
  voorbeelden, comments of herkenningsregels.

De `.gitignore` vangt de bekende bestandstypen af, maar kijk zelf ook altijd
even naar `git status` voordat je commit. Wat eenmaal gepusht is, staat voor
altijd in de geschiedenis.

Herkenningsregels in `app/rules.py` moeten voor iedereen bruikbaar zijn:
landelijke winkels, banken, overheidsinstanties. Regels voor je eigen
werkgever, familie of lokale zaken stel je in de app in als
tegenpartij-regel; die staan dan alleen in jouw database.

## Ontwerpprincipes

- **Geen dependencies.** De backend gebruikt alleen de
  Python-standaardbibliotheek (3.9+), de frontend platte HTML, CSS en
  JavaScript. Dat houdt installeren triviaal en de app jarenlang draaiend.
  Wil je toch iets toevoegen, bespreek het eerst in een issue.
- **Niets naar internet.** Geen externe API's, geen CDN's, geen telemetrie.
- **Geld in centen.** Bedragen zijn altijd integers in centen, nooit floats.
- **Bestaande databases blijven werken.** Schemawijzigingen zijn additief
  (`CREATE TABLE IF NOT EXISTS`, nieuwe instellingen via `setdefault`).

## Zo werk je

1. Haal `main` op: `git switch main && git pull`.
2. Maak een branch: `git switch -c feat/korte-omschrijving`. Prefixen:
   `feat/`, `fix/`, `docs/`, `refactor/`, `chore/`.
3. Bouw en test lokaal met een wegwerpdatabase, zodat je eigen gegevens
   buiten schot blijven:
   ```bash
   python3 app/app.py --db /tmp/finapp-test.db --port 8766
   ```
   Je kunt daar een geanonimiseerd testbestand in importeren.
4. Commit in kleine stappen met een duidelijke boodschap:
   `feat: vakanties per jaar tonen`, `fix: Amex-bedragen met komma parsen`.
5. Push je branch en open een pull request. Beschrijf wat er verandert,
   waarom, en hoe je het hebt getest.
6. Iemand anders kijkt mee en merget. Werk nooit direct op `main`; dat is
   een afspraak, want op een gratis privérepository kan GitHub het niet
   afdwingen.

## Code

- Comments, documentatie en teksten in de app zijn in het Nederlands.
  Namen van functies, variabelen en databasekolommen in het Engels.
- Houd de bestaande stijl aan: kleine functies, geen frameworks, geen
  buildstap.
- Werk `README.md` alleen bij als de tekst daar niet meer klopt.

## Ideeën en problemen

Open een issue in deze repository. Beschrijf bij een bug welk bestandstype
je importeerde en wat je verwachtte, zonder het bestand zelf bij te voegen.
