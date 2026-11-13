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

## Licentie van je bijdrage

FinApp staat onder de PolyForm Noncommercial 1.0.0-licentie (zie `LICENSE`).
Door een pull request in te dienen ga je akkoord met het volgende:

- Je bijdrage valt onder dezelfde PolyForm Noncommercial-licentie als de rest
  van FinApp.
- Je geeft de FinApp-ontwikkelaars daarnaast een eeuwigdurend, onherroepelijk,
  wereldwijd en royaltyvrij recht om je bijdrage te gebruiken, aan te passen
  en te verspreiden onder elke licentie, ook commercieel. Dit maakt het
  mogelijk om FinApp later als betaalde of donatie-gebaseerde applicatie aan
  te bieden zonder dat elke bijdrager daar opnieuw voor om toestemming moet
  worden gevraagd.
- Je blijft zelf auteursrechthebbende van je bijdrage en mag die elders
  gebruiken zoals je wilt.
- Je verklaart dat je het recht hebt om de bijdrage onder deze voorwaarden te
  leveren: het is je eigen werk, of je hebt toestemming van degene die het
  gemaakt heeft.

Wie structureel meebouwt, kan toetreden tot de FinApp-ontwikkelaars; daarover
maken we onderling afspraken buiten deze repository om.

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
6. Iemand anders kijkt mee en merget. Werk nooit direct op `main`: GitHub
   laat wijzigingen daar alleen toe via een pull request met een
   goedkeuring.

## Commits signeren

`main` accepteert alleen gesigneerde commits. Ongesigneerde commits op je
branch kunnen het mergen van je pull request blokkeren, dus stel signeren
één keer in voordat je begint. Met een SSH-sleutel gaat dat zo:

```bash
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
```

Voeg dezelfde publieke sleutel daarna toe op GitHub onder Settings, "SSH and
GPG keys", met als type "Signing Key". Gebruik je die sleutel al om in te
loggen, dan voeg je hem daar een tweede keer toe als signing key. Staat er
op GitHub "Verified" bij je commit, dan werkt het.

Heb je al ongesigneerde commits op je branch staan? Signeer ze dan alsnog en
push de branch opnieuw:

```bash
git rebase --force-rebase main
git push --force-with-lease
```

## Code

- Comments, documentatie en teksten in de app zijn in het Nederlands.
  Namen van functies, variabelen en databasekolommen in het Engels.
- Houd de bestaande stijl aan: kleine functies, geen frameworks, geen
  buildstap.
- Werk `README.md` alleen bij als de tekst daar niet meer klopt.

## Ideeën en problemen

Open een issue in deze repository en kies een van de formulieren. Beschrijf
bij een bug welk bestandstype je importeerde en wat je verwachtte, zonder
het bestand zelf bij te voegen.

Nieuwe functies bespreken we in issues, één issue per idee:

- Reageer in het issue met je mening en geef een duimpje als je het idee
  graag gebouwd ziet. De issuelijst is op duimpjes te sorteren.
- Het label laat zien waar een idee staat: `bespreken` (meningen gevraagd),
  `akkoord` (gaan we bouwen) of `later` (goed idee, nu geen prioriteit).
- Een idee dat we niet gaan bouwen, sluiten we met een korte uitleg.
- Na akkoord volgt voor grotere wijzigingen een plan in `docs/plans/`. De
  pull request verwijst naar het issue.
