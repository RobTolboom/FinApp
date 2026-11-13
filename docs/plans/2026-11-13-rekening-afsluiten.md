# Rekening afsluiten en melding bij achterlopende gegevens

Datum: 2026-11-13
Branch: `feat/rekening-afsluiten`
Status: goedgekeurd op 2026-11-13

## Doel

Vaste lasten moeten kloppen als niet alle rekeningen even ver zijn
geïmporteerd, en de app moet aansporen om gegevens actueel te houden.

Aanleiding: een last gold als gestopt zodra de laatste boeking te ver voor de
nieuwste transactie over alle rekeningen lag. Een creditcard die een paar
maanden achterliep, leek daardoor al zijn abonnementen te hebben beëindigd.

## Omvang

- Een open rekening wordt beoordeeld tegen zijn eigen laatste boekdatum.
- Een rekening kan worden afgesloten en heropend op het tabblad Instellingen.
  Voor een afgesloten rekening telt de nieuwste datum over alle rekeningen,
  zodat de lasten daarop vanzelf als gestopt gelden.
- Meldingen op Overzicht en Vaste lasten:
  - één als de nieuwste gegevens meer dan 45 dagen oud zijn;
  - één per open rekening die meer dan 45 dagen achterloopt op de nieuwste
    gegevens.
- De keuze staat als sleutel `closed_accounts` in de tabel `settings`.
  `SCHEMA` verandert niet.

Buiten de omvang: de bestaande meldingen over ontbrekende Bank- of
Amex-gegevens, en de opbouw van het vermogen.

## Takenlijst

- [x] `app/engine.py`: `find_recurring` krijgt de afgesloten rekeningen mee en
      bepaalt de einddatum per bron en rekening.
- [x] `app/app.py`: instelling `closed_accounts`, lijst `accounts` in
      `GET /api/data`, route `POST /api/account`.
- [x] `app/static/app.js`: meldingen, paneel "Rekeningen" en de knoppen
      afsluiten en heropenen.
- [x] Testen met verzonnen gegevens.
- [ ] Controle in de browser.

## Risico's

- Wie een opgeheven rekening niet afsluit, houdt de lasten daarop actief. De
  melding per rekening vangt dat op.
- De grens van 45 dagen is een keuze. Het advies is maandelijks importeren en
  een creditcardafschrift kan een maand naijlen.
- Een rekening wordt herkend aan bron en rekeningnummer. Een Amex-export
  zonder rekeningnummer telt als één rekening.

## Acceptatiecriteria

- Een last op een open rekening die achterloopt, blijft actief.
- Een last op een afgesloten rekening geldt als gestopt zodra de laatste
  boeking te ver voor de nieuwste gegevens ligt; na heropenen is hij weer
  actief.
- Een bestaande database zonder `closed_accounts` werkt zonder handwerk.
- De melding verschijnt bij meer dan 45 dagen achterstand en niet voor een
  afgesloten rekening.
- Een rekeningnummer staat nergens voluit in de nieuwe schermteksten; alleen
  de laatste vier tekens.
