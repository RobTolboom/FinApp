# Hypotheeksplitsing over meerdere afschrijvingen

Datum: 2026-11-15
Branch: `fix/hypotheek`
Status: goedgekeurd en gebouwd, in review (#56)
Issue: #35

## Doel

De app splitst de hypotheektermijn op de bankrekening in rente (blijft een
uitgave onder Wonen) en aflossing (vermogensopbouw, telt niet mee). Dat
gebeurde per maand op één afschrijving. Bij twee geldverstrekkers of een
verschoven incasso bleef de tweede afschrijving volledig een uitgave.

Na dit plan krijgt elke afschrijving de aflossing van haar eigen
leningdelen, ook als:

- meerdere leningdelen in één bedrag worden afgeschreven;
- meerdere geldverstrekkers elk hun eigen bedrag afschrijven;
- een incasso over de maandgrens verschuift.

## Omvang

- `app/mortgage.py`: nieuwe functie `split_repayments`, die per afschrijving
  bepaalt hoeveel ervan aflossing is.
- `app/app.py`: `_mortgage` levert per maand de termijn en de aflossing per
  leningdeel; `_split_mortgage` gebruikt de nieuwe verdeling.
- Geen wijziging aan `SCHEMA`, de API-routes of de frontend.

Buiten de omvang:

- een eigen herkenningstekst per leningdeel of per geldverstrekker;
- automatisch herkennen van een losse extra aflossing;
- controle van de leningdelen aan de hand van het jaaroverzicht (apart
  idee, zie het issue daarover).

### Werkwijze

De app weet per leningdeel hoeveel rente en aflossing er elke maand in zit.
Welke afschrijving bij welk leningdeel hoort, wordt afgeleid uit de
bedragen:

1. Per maand krijgt elke afschrijving de aflossing van de leningdelen waar
   haar bedrag bij past. Een bedrag past bij een afwijking van hoogstens
   2%, met een ondergrens van 5 euro. Van alle verdelingen die passen wint
   die met de meeste gekoppelde leningdelen en daarna de kleinste afwijking.
2. Een termijn die overblijft, gaat naar een overgebleven afschrijving in
   de volgende of vorige maand als het bedrag daar past.
3. Wat dan nog overblijft, wordt naar rato van de bedragen verdeeld over
   de overgebleven afschrijvingen van dezelfde maand.

Een afschrijving doet alleen mee als zij van de bankrekening komt, in de
categorie Wonen valt en aan het ingestelde patroon voldoet (standaard
`HYPOTHE`). De aflossing is nooit hoger dan de afschrijving zelf.

## Takenlijst

- [x] `split_repayments` met de drie stappen.
- [x] `_mortgage` geeft termijn en aflossing per leningdeel per maand door.
- [x] `_split_mortgage` verdeelt over alle passende afschrijvingen.
- [x] Rekengevallen met verzonnen leningdelen en afschrijvingen.
- [x] Controle via de draaiende app met een wegwerpdatabase.

## Risico's

- **Afschrijving wijkt af van het schema.** Een meegeïncasseerde premie of
  rente per dag in plaats van per maand kan buiten de marge vallen. Dan
  volgt stap 3: het maandtotaal klopt, de verdeling per regel is een
  benadering.
- **Bijna gelijke afschrijvingen.** Twee afschrijvingen binnen elkaars
  marge kunnen worden omgewisseld. Het maandtotaal klopt.
- **Eenmalige betaling met "hypotheek" in de omschrijving.** Een
  adviesfactuur of losse extra aflossing krijgt geen aflossing zolang de
  gewone afschrijving past. Past die ook niet, dan krijgt de eenmalige
  betaling in stap 3 een deel.
- **Tweede geldverstrekker niet herkend.** Een afschrijving zonder
  "hypotheek" in de omschrijving doet pas mee als zij in het patroon staat
  en als Wonen is gecategoriseerd.
- **Veel leningdelen en afschrijvingen in één maand.** Boven 100.000
  mogelijke verdelingen slaat de app stap 1 over en verdeelt naar rato.
- **Geen geautomatiseerde tests.** De rekengevallen zijn handmatig
  gedraaid en staan niet in de repository (zie #42).

## Acceptatiecriteria

- Eén afschrijving voor alle leningdelen geeft dezelfde splitsing als
  voorheen.
- Bij twee geldverstrekkers krijgt elke afschrijving de aflossing van haar
  eigen leningdelen; een afschrijving voor een aflossingsvrij deel wordt
  niet gesplitst.
- Een eenmalige betaling naast een passende afschrijving wordt niet
  gesplitst.
- Bij een verschoven incasso krijgen beide afschrijvingen in dezelfde
  maand elk de aflossing van één termijn, ook als maar één van twee
  geldverstrekkers verschuift.
- De som van de aflossing over alle afschrijvingen is nooit hoger dan de
  aflossing volgens het schema.
- Zonder leningdelen of met de splitsing uitgeschakeld verandert er niets
  aan de transacties.
