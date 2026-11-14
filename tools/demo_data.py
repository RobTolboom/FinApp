"""Maakt een verzonnen dataset om FinApp mee te testen.

Schrijft twee bestanden die je via de importknop in de app inlaadt:
- demo-bank.xml  CAMT.053-afschrift met een betaal- en een spaarrekening
- demo-amex.csv  American Express-export

Alle namen, IBAN's en rekeningnummers zijn verzonnen. De IBAN's hebben
bewust een ongeldig controlegetal (NL00), zodat ze nooit een echte rekening
kunnen zijn. Met dezelfde --seed en --eind is de uitvoer elke keer gelijk.

Gebruik:
    python3 tools/demo_data.py
    python3 tools/demo_data.py --uit /tmp/finapp-demo --maanden 12 --eind 2026-10-31

Schrijf de uitvoer niet in de repository: .xml en .csv horen daar niet.
"""
import argparse
import csv
import os
import random
import xml.etree.ElementTree as ET
from datetime import date, timedelta

NS = "urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"

IBAN_BETAAL = "NL00DEMO0000000001"
IBAN_SPAAR = "NL00DEMO0000000002"
AMEX_REKENING = "XXXX-XXXXX0-00000"
EIGEN_NAAM = "Demo Gebruiker"

THUIS = "UTRECHT"
VAKANTIE_STAD = "LISBOA"
VAKANTIE_LAND = "PORTUGAL"

MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december"]


def eur(cents):
    """Centen als '1234.56' (CAMT) zonder floats."""
    return "%d.%02d" % (abs(cents) // 100, abs(cents) % 100)


def eur_nl(cents):
    """Centen als '1234,56' of '-1234,56' (Amex-CSV)."""
    return ("-" if cents < 0 else "") + eur(cents).replace(".", ",")


def maand_start(d):
    return d.replace(day=1)


def volgende_maand(d):
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def dag_in_maand(m, dag):
    """Dag 'dag' van maand m, begrensd op de laatste dag van die maand."""
    laatste = volgende_maand(m) - timedelta(days=1)
    return m.replace(day=min(dag, laatste.day))


def werkdag(d):
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


class Generator:
    def __init__(self, rng, start, eind):
        self.rng = rng
        self.start = start
        self.eind = eind
        self.bank = []      # dicts per boeking op de betaalrekening
        self.spaar = []     # boekingen op de spaarrekening
        self.amex = []      # dicts per Amex-regel (bedrag: positief = uitgave)
        self.n = 0
        # vakantie: twee weken vanaf de eerste zaterdag van juli in de periode
        self.vakantie = None
        m = maand_start(start)
        while m <= eind:
            if m.month == 7:
                d = m
                while d.weekday() != 5:
                    d += timedelta(days=1)
                self.vakantie = (d, d + timedelta(days=13))
                break
            m = volgende_maand(m)

    def ref(self):
        self.n += 1
        return "DEMO%08d" % self.n

    def in_vakantie(self, d):
        return bool(self.vakantie) and self.vakantie[0] <= d <= self.vakantie[1]

    # ---------------------------------------------------------- bankboekingen

    def boeking(self, d, cents, naam, omschrijving, code, iban="", mandaat="", crediteur=""):
        if d < self.start or d > self.eind:
            return
        self.bank.append({"date": d, "amount": cents, "name": naam, "rmt": omschrijving,
                          "code": code, "iban": iban, "mandate": mandaat, "creditor": crediteur,
                          "ref": self.ref()})

    def incasso(self, d, cents, naam, crediteur, omschrijving):
        self.boeking(d, -cents, naam, omschrijving, "10",
                     iban="NL00DEMO" + crediteur[-10:], mandaat="MDT-" + crediteur[-6:], crediteur=crediteur)

    def pin(self, d, cents, winkel, stad=THUIS, geldautomaat=False):
        tijd = "%02d.%02d" % (self.rng.randint(8, 20), self.rng.randint(0, 59))
        soort = "GEA" if geldautomaat else "BEA"
        rmt = "%s  %s  %s Nr:%s  %s/%s" % (winkel.upper(), stad, soort, self.ref()[-6:],
                                           d.strftime("%d.%m.%y"), tijd)
        self.boeking(d, -cents, winkel, rmt, "101")

    def bedrag(self, laag, hoog):
        """Willekeurig bedrag in centen tussen laag en hoog (beide in centen)."""
        return self.rng.randint(laag, hoog)

    def maak(self):
        m = maand_start(self.start)
        while m <= self.eind:
            self.maand(m)
            m = volgende_maand(m)
        self.dagelijks()
        self.bank.sort(key=lambda t: (t["date"], t["ref"]))
        self.spaar.sort(key=lambda t: (t["date"], t["ref"]))
        self.amex.sort(key=lambda t: (t["date"], t["ref"]))

    def maand(self, m):
        naam = MAANDEN[m.month - 1]
        r = self.rng

        # inkomsten
        salaris = 325000 + (32500 if m.month == 5 else 0)   # mei: vakantiegeld erbij
        self.boeking(werkdag(dag_in_maand(m, 24)), salaris, "Werkgever Demo BV",
                     "SALARIS %s %d" % (naam.upper(), m.year), "44", iban="NL00DEMO0000000900")

        # wonen en vaste lasten
        self.boeking(dag_in_maand(m, 1), -115000, "Woonstichting Voorbeeld",
                     "HUUR %s %d" % (naam.upper(), m.year), "44", iban="NL00DEMO0000000901")
        self.incasso(dag_in_maand(m, 3), 13500, "Vattenfall Klantenservice", "NL00ZZZ000000000001",
                     "Termijnbedrag energie %s" % naam)
        self.incasso(dag_in_maand(m, 5), 5950, "Ziggo Services BV", "NL00ZZZ000000000002",
                     "Ziggo internet en tv %s" % naam)
        self.incasso(dag_in_maand(m, 1), 14215, "Zilveren Kruis Zorgverzekeringen", "NL00ZZZ000000000003",
                     "Premie zorgverzekering %s" % naam)
        self.incasso(dag_in_maand(m, 12), 1399, "Netflix International BV", "NL00ZZZ000000000004",
                     "Netflix abonnement")
        self.incasso(dag_in_maand(m, 20), 3150, "Centraal Beheer", "NL00ZZZ000000000005",
                     "Inboedel- en aansprakelijkheidsverzekering")
        self.incasso(dag_in_maand(m, 27), 3990, "Basic-Fit Nederland BV", "NL00ZZZ000000000006",
                     "Lidmaatschap Basic-Fit")
        if m.month in (1, 4, 7, 10):
            self.incasso(dag_in_maand(m, 15), 4560, "Vitens NV", "NL00ZZZ000000000007",
                         "Drinkwater kwartaal")
        if m.month in (3, 4):
            self.incasso(dag_in_maand(m, 28), 21400, "Gemeente Voorbeeldstad", "NL00ZZZ000000000008",
                         "Gemeentelijke belastingen termijn")
        self.boeking(dag_in_maand(m, 1), -395, "", "Kosten betaalpakket %s" % naam, "44")

        # sparen
        d = dag_in_maand(m, 25)
        self.boeking(d, -30000, EIGEN_NAAM, "SPAARREKENING maandelijkse inleg", "44", iban=IBAN_SPAAR)
        if self.start <= d <= self.eind:
            self.spaar.append({"date": d, "amount": 30000, "name": EIGEN_NAAM,
                               "rmt": "SPAARREKENING maandelijkse inleg", "code": "44",
                               "iban": IBAN_BETAAL, "mandate": "", "creditor": "", "ref": self.ref()})

        # eenmalig
        if m.month == 4:
            self.boeking(dag_in_maand(m, 18), 41200, "Belastingdienst",
                         "TERUGGAAF INKOMSTENBELASTING %d" % (m.year - 1), "44", iban="NL00DEMO0000000902")
        if m.month == 6 and self.vakantie:
            self.boeking(dag_in_maand(m, 2), -38900, "Transavia",
                         "Boeking vlucht Amsterdam - Lissabon", "4", iban="NL00DEMO0000000903")

        # Amex: abonnementen en online aankopen
        self.amex_regel(dag_in_maand(m, 8), 1199, "SPOTIFY", "STOCKHOLM", "SWEDEN")
        if r.random() < 0.7:
            self.amex_regel(dag_in_maand(m, r.randint(2, 27)), self.bedrag(1500, 8900), "BOL.COM", "UTRECHT")
        if r.random() < 0.4:
            self.amex_regel(dag_in_maand(m, r.randint(2, 27)), self.bedrag(4900, 18900), "COOLBLUE", "ROTTERDAM")
        if r.random() < 0.3:
            self.amex_regel(dag_in_maand(m, r.randint(2, 27)), self.bedrag(2995, 9995), "ZALANDO", "BERLIN", "GERMANY")
        if m.month == 6 and self.vakantie:
            self.amex_regel(dag_in_maand(m, 3), 84000, "BOOKING.COM", "AMSTERDAM")

        # Amex-aflossing van de vorige maand, plus de betaling op de Amex-kaart
        vorige = (m - timedelta(days=1)).replace(day=1)
        totaal = sum(a["amount"] for a in self.amex if vorige <= a["date"] < m)
        if totaal > 0:
            d = dag_in_maand(m, 10)
            self.boeking(d, -totaal, "American Express Europe SA",
                         "Incasso creditcard rekeningoverzicht", "44", iban="NL00DEMO0000000904")
            if self.start <= d <= self.eind:
                self.amex.append({"date": d, "amount": -totaal,
                                  "desc": "HARTELIJK BEDANKT VOOR UW BETALING", "land": "",
                                  "ref": self.ref()})

    def amex_regel(self, d, cents, winkel, stad, land="NETHERLANDS"):
        if d < self.start or d > self.eind:
            return
        desc = "%-23s %s" % (winkel[:23], stad)
        self.amex.append({"date": d, "amount": cents, "desc": desc, "land": land, "ref": self.ref()})

    def dagelijks(self):
        r = self.rng
        boodschappen = ["Albert Heijn 1184", "Jumbo Voorbeeldstraat", "Lidl 0412"]
        horeca = ["Cafe De Hoek", "Restaurant De Molen", "Pizza Napoli", "Starbucks Centraal"]
        winkels = ["HEMA 0231", "Kruidvat 6318", "Action 1720", "Gamma 0544"]
        vakantie_horeca = ["Restaurante O Mar", "Cafe Central", "Pastelaria Belem"]
        d = self.start
        while d <= self.eind:
            if self.in_vakantie(d):
                if r.random() < 0.9:
                    self.pin(d, self.bedrag(1800, 6500), r.choice(vakantie_horeca), VAKANTIE_STAD)
                if r.random() < 0.4:
                    self.pin(d, self.bedrag(800, 3500), "Lidl Alfama", VAKANTIE_STAD)
                if r.random() < 0.5:
                    self.amex_regel(d, self.bedrag(1200, 4800), r.choice(["MUSEU NACIONAL", "TAXI LISBOA",
                                                                           "RESTAURANTE TASCA"]),
                                    VAKANTIE_STAD, VAKANTIE_LAND)
                d += timedelta(days=1)
                continue
            # boodschappen ongeveer drie keer per week
            if r.random() < 0.43:
                self.pin(d, self.bedrag(900, 9500), r.choice(boodschappen))
            if d.weekday() >= 4 and r.random() < 0.3:
                self.pin(d, self.bedrag(1400, 7800), r.choice(horeca))
            if d.weekday() < 5 and r.random() < 0.15:
                self.boeking(d, -self.bedrag(250, 1400), "OVpay", "www.ovpay.nl  OV reis", "121")
            if r.random() < 0.08:
                self.pin(d, self.bedrag(500, 6000), r.choice(winkels))
            if r.random() < 0.05:
                self.pin(d, self.bedrag(4500, 7500), "Shell Voorbeeldweg")
            if r.random() < 0.02:
                self.pin(d, r.choice([2000, 5000, 7000, 10000]), "Geldmaat Stationsplein", geldautomaat=True)
            if r.random() < 0.02:
                self.boeking(d, self.bedrag(1000, 3500), "Vriend Voorbeeld",
                             "Tikkie betaalverzoek etentje", "44", iban="NL00DEMO0000000905")
            d += timedelta(days=1)


# ---------------------------------------------------------------- uitvoer

def _sub(parent, tag, text=None, **attrs):
    el = ET.SubElement(parent, tag, attrs)
    if text is not None:
        el.text = text
    return el


def _saldo(stmt, soort, d, cents):
    bal = _sub(stmt, "Bal")
    _sub(_sub(_sub(bal, "Tp"), "CdOrPrtry"), "Cd", soort)
    _sub(bal, "Amt", eur(cents), Ccy="EUR")
    _sub(bal, "CdtDbtInd", "DBIT" if cents < 0 else "CRDT")
    _sub(_sub(bal, "Dt"), "Dt", d.isoformat())


def _ntry(stmt, t):
    ntry = _sub(stmt, "Ntry")
    _sub(ntry, "Amt", eur(t["amount"]), Ccy="EUR")
    _sub(ntry, "CdtDbtInd", "DBIT" if t["amount"] < 0 else "CRDT")
    _sub(ntry, "Sts", "BOOK")
    _sub(_sub(ntry, "BookgDt"), "Dt", t["date"].isoformat())
    _sub(_sub(ntry, "ValDt"), "Dt", t["date"].isoformat())
    prtry = _sub(_sub(ntry, "BkTxCd"), "Prtry")
    _sub(prtry, "Cd", t["code"])
    _sub(prtry, "Issr", "DEMO")
    det = _sub(_sub(ntry, "NtryDtls"), "TxDtls")
    refs = _sub(det, "Refs")
    _sub(refs, "EndToEndId", t["ref"])
    if t["mandate"]:
        _sub(refs, "MndtId", t["mandate"])
    if t["name"] or t["iban"]:
        pties = _sub(det, "RltdPties")
        rol = "Cdtr" if t["amount"] < 0 else "Dbtr"
        partij = _sub(pties, rol)
        if t["name"]:
            _sub(partij, "Nm", t["name"])
        if t["creditor"]:
            _sub(_sub(_sub(_sub(partij, "Id"), "OrgId"), "Othr"), "Id", t["creditor"])
        if t["iban"]:
            _sub(_sub(_sub(pties, rol + "Acct"), "Id"), "IBAN", t["iban"])
    _sub(_sub(det, "RmtInf"), "Ustrd", t["rmt"])


def schrijf_camt(pad, rekeningen, start, eind):
    """rekeningen: lijst (iban, beginsaldo_centen, boekingen). Eén afschrift per maand."""
    root = ET.Element("Document", xmlns=NS)
    bk = _sub(root, "BkToCstmrStmt")
    hdr = _sub(bk, "GrpHdr")
    _sub(hdr, "MsgId", "DEMO-%s" % eind.isoformat())
    _sub(hdr, "CreDtTm", "%sT12:00:00" % eind.isoformat())
    for iban, saldo, boekingen in rekeningen:
        m = maand_start(start)
        while m <= eind:
            tot = min(volgende_maand(m) - timedelta(days=1), eind)
            van = max(m, start)
            deze = [t for t in boekingen if van <= t["date"] <= tot]
            stmt = _sub(bk, "Stmt")
            _sub(stmt, "Id", "%s-%s" % (iban[-4:], m.strftime("%Y%m")))
            _sub(_sub(_sub(stmt, "Acct"), "Id"), "IBAN", iban)
            _saldo(stmt, "OPBD", van, saldo)
            saldo += sum(t["amount"] for t in deze)
            _saldo(stmt, "CLBD", tot, saldo)
            for t in deze:
                _ntry(stmt, t)
            m = volgende_maand(m)
    tree = ET.ElementTree(root)
    if hasattr(ET, "indent"):
        ET.indent(tree)
    tree.write(pad, encoding="utf-8", xml_declaration=True)


def schrijf_amex(pad, regels):
    velden = ["Datum", "Omschrijving", "Kaartlid", "Rekening #", "Bedrag",
              "Aanvullende informatie", "Land", "Referentie"]
    with open(pad, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(velden)
        for a in sorted(regels, key=lambda a: (a["date"], a["ref"]), reverse=True):
            w.writerow([a["date"].strftime("%m/%d/%Y"), a["desc"], EIGEN_NAAM.upper(), AMEX_REKENING,
                        eur_nl(a["amount"]), "", a["land"], "'%s'" % a["ref"]])


def main():
    vandaag = date.today()
    standaard_eind = vandaag.replace(day=1) - timedelta(days=1)
    ap = argparse.ArgumentParser(description="Maak verzonnen testbestanden voor FinApp")
    ap.add_argument("--uit", default="/tmp/finapp-demo", help="map voor de uitvoer (niet in de repository)")
    ap.add_argument("--maanden", type=int, default=12, help="aantal maanden (standaard 12)")
    ap.add_argument("--eind", default=standaard_eind.isoformat(),
                    help="laatste dag, JJJJ-MM-DD (standaard: einde vorige maand)")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    eind = date.fromisoformat(a.eind)
    start = maand_start(eind)
    for _ in range(a.maanden - 1):
        start = maand_start(start - timedelta(days=1))

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    uit = os.path.abspath(a.uit)
    if uit == repo or uit.startswith(repo + os.sep):
        ap.error("schrijf de uitvoer buiten de repository (bijv. /tmp/finapp-demo)")
    os.makedirs(uit, exist_ok=True)

    g = Generator(random.Random(a.seed), start, eind)
    g.maak()
    bank_pad = os.path.join(uit, "demo-bank.xml")
    amex_pad = os.path.join(uit, "demo-amex.csv")
    schrijf_camt(bank_pad, [(IBAN_BETAAL, 250000, g.bank), (IBAN_SPAAR, 800000, g.spaar)], start, eind)
    schrijf_amex(amex_pad, g.amex)

    print("Periode: %s t/m %s" % (start, eind))
    print("  %s  (%d boekingen betaalrekening, %d spaarrekening)" % (bank_pad, len(g.bank), len(g.spaar)))
    print("  %s  (%d regels)" % (amex_pad, len(g.amex)))
    if g.vakantie:
        print("Vakantie in de data: %s t/m %s (%s). Voeg die in de app toe om de"
              " vakantieherkenning te zien." % (g.vakantie[0], g.vakantie[1], VAKANTIE_STAD.title()))
    print("Importeer beide bestanden via de importknop in de app.")


if __name__ == "__main__":
    main()
