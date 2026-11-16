"""Tests voor de CAMT.053-parser. Alle gegevens zijn verzonnen.

Draaien vanuit de hoofdmap:
    python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import parsers  # noqa: E402

NS = "urn:iso:std:iso:20022:tech:xsd:camt.053.001.%s"
IBAN = "NL00DEMO0000000001"


def doc(ntrys, version="02"):
    """Een afschrift met de gegeven boekingen."""
    return ('<?xml version="1.0"?><Document xmlns="%s"><BkToCstmrStmt><Stmt>'
            "<Acct><Id><IBAN>%s</IBAN></Id></Acct>%s</Stmt></BkToCstmrStmt></Document>"
            % (NS % version, IBAN, "".join(ntrys))).encode()


def ntry(amount="10.00", ccy="EUR", sts="<Sts>BOOK</Sts>", date="<BookgDt><Dt>2026-03-05</Dt></BookgDt>",
         rmtinf="<RmtInf><Ustrd>Testbetaling</Ustrd></RmtInf>", ind="DBIT", extra="", details=None):
    """Eén boeking. 'details' vervangt de standaard NtryDtls."""
    if details is None:
        details = ("<NtryDtls><TxDtls><Refs><EndToEndId>E1</EndToEndId></Refs>"
                   "<RltdPties><Cdtr><Nm>Winkel Voorbeeld</Nm></Cdtr></RltdPties>%s</TxDtls></NtryDtls>" % rmtinf)
    return ('<Ntry><Amt Ccy="%s">%s</Amt><CdtDbtInd>%s</CdtDbtInd>%s%s%s%s</Ntry>'
            % (ccy, amount, ind, extra, sts, date, details))


def part(name, amount, e2e, form="amtdtls", ccy="EUR", ind=""):
    """Eén onderdeel (TxDtls) van een verzamelboeking."""
    if form == "amtdtls":
        amt = '<AmtDtls><TxAmt><Amt Ccy="%s">%s</Amt></TxAmt></AmtDtls>' % (ccy, amount)
    elif form == "amt":
        amt = '<Amt Ccy="%s">%s</Amt>%s' % (ccy, amount, "<CdtDbtInd>%s</CdtDbtInd>" % ind if ind else "")
    else:
        amt = ""
    return ("<TxDtls><Refs><EndToEndId>%s</EndToEndId></Refs>%s"
            "<RltdPties><Cdtr><Nm>%s</Nm></Cdtr><Dbtr><Nm>%s</Nm></Dbtr></RltdPties>"
            "<RmtInf><Ustrd>Betaling %s</Ustrd></RmtInf></TxDtls>" % (e2e, amt, name, name, name))


def batch(total, parts, ind="DBIT", extra="", separate=False):
    """Een afschrift met één verzamelboeking."""
    if separate:
        details = "".join("<NtryDtls>%s</NtryDtls>" % p for p in parts)
    else:
        details = "<NtryDtls>%s</NtryDtls>" % "".join(parts)
    return doc([ntry(amount=total, ind=ind, extra=extra, details=details)])


def parse(data):
    return parsers.parse_camt053(data)


class Basis(unittest.TestCase):
    def test_gewone_boeking(self):
        (t,) = parse(doc([ntry()]))
        self.assertEqual(t["amount"], -1000)
        self.assertEqual(t["date"], "2026-03-05")
        self.assertEqual(t["account"], IBAN)
        self.assertEqual(t["counterparty"], "Winkel Voorbeeld")
        self.assertEqual(t["description"], "Testbetaling")
        self.assertEqual(t["source"], "bank")

    def test_bijschrijving_is_positief(self):
        (t,) = parse(doc([ntry(ind="CRDT")]))
        self.assertEqual(t["amount"], 1000)

    def test_uid_blijft_gelijk(self):
        # De uid is een hash van rekening, boekdatum, bedrag, naam, omschrijving
        # en kenmerk. Verandert deze waarde, dan ziet de app alle bestaande
        # transacties als nieuw: alleen aanpassen samen met een migratie.
        (t,) = parse(doc([ntry()]))
        self.assertEqual(t["uid"], "bank:" + parsers._hash(IBAN, "2026-03-05", -1000, "Winkel Voorbeeld",
                                                           "Testbetaling", "E1"))

    def test_twee_gelijke_boekingen_krijgen_elk_een_uid(self):
        a, b = parse(doc([ntry(), ntry()]))
        self.assertNotEqual(a["uid"], b["uid"])

    def test_geen_camt(self):
        with self.assertRaises(parsers.ImportFout):
            parse(b'<?xml version="1.0"?><Document xmlns="urn:iets:anders"/>')

    def test_kapotte_xml(self):
        with self.assertRaises(parsers.ImportFout):
            parse(b"<Document")


class Status(unittest.TestCase):
    """#30: de status staat in Sts of, in nieuwere versies, in Sts/Cd."""

    def test_sts_als_tekst(self):
        self.assertEqual(len(parse(doc([ntry()]))), 1)

    def test_sts_cd_book(self):
        self.assertEqual(len(parse(doc([ntry(sts="<Sts><Cd>BOOK</Cd></Sts>")], "08"))), 1)

    def test_sts_cd_reservering_overgeslagen(self):
        r = parse(doc([ntry(), ntry(amount="20.00", sts="<Sts><Cd>PDNG</Cd></Sts>")], "08"))
        self.assertEqual([t["amount"] for t in r], [-1000])

    def test_sts_tekst_reservering_overgeslagen(self):
        r = parse(doc([ntry(), ntry(amount="20.00", sts="<Sts>PDNG</Sts>")]))
        self.assertEqual([t["amount"] for t in r], [-1000])

    def test_alleen_reserveringen(self):
        with self.assertRaises(parsers.ImportFout):
            parse(doc([ntry(sts="<Sts><Cd>PDNG</Cd></Sts>")], "08"))


class Valuta(unittest.TestCase):
    """#26: een geboekt bedrag in een andere valuta dan euro wordt geweigerd."""

    def test_dollar_geweigerd_met_melding(self):
        with self.assertRaises(parsers.ImportFout) as cm:
            parse(doc([ntry(ccy="USD", amount="100.00")]))
        self.assertIn("USD", str(cm.exception))
        self.assertIn(IBAN, str(cm.exception))

    def test_reservering_in_dollar_blokkeert_niet(self):
        r = parse(doc([ntry(), ntry(ccy="USD", sts="<Sts>PDNG</Sts>")]))
        self.assertEqual(len(r), 1)

    def test_ontbrekende_valuta_blijft_werken(self):
        r = parse(doc([ntry().replace(' Ccy="EUR"', "")]))
        self.assertEqual(len(r), 1)


class Datum(unittest.TestCase):
    """#27: een boekdatum met tijdstip (DtTm) wordt ook gelezen."""

    def test_dttm(self):
        (t,) = parse(doc([ntry(date="<BookgDt><DtTm>2026-03-05T14:22:10+01:00</DtTm></BookgDt>")]))
        self.assertEqual(t["date"], "2026-03-05")

    def test_dttm_geeft_dezelfde_uid_als_dt(self):
        (a,) = parse(doc([ntry()]))
        (b,) = parse(doc([ntry(date="<BookgDt><DtTm>2026-03-05T14:22:10+01:00</DtTm></BookgDt>")]))
        self.assertEqual(a["uid"], b["uid"])

    def test_valutadatum_als_terugval(self):
        (t,) = parse(doc([ntry(date="<ValDt><DtTm>2026-03-06T00:00:00</DtTm></ValDt>")]))
        self.assertEqual(t["date"], "2026-03-06")

    def test_zonder_datum_geweigerd(self):
        with self.assertRaises(parsers.ImportFout) as cm:
            parse(doc([ntry(date="")]))
        self.assertIn("boekdatum", str(cm.exception))

    def test_onleesbare_datum_geweigerd(self):
        with self.assertRaises(parsers.ImportFout):
            parse(doc([ntry(date="<BookgDt><Dt>5 maart</Dt></BookgDt>")]))


class Betalingskenmerk(unittest.TestCase):
    """#28: een gestructureerd kenmerk komt in de omschrijving, niet in de uid."""

    STRD = "<RmtInf><Strd><CdtrRefInf><Ref>1234567890123456</Ref></CdtrRefInf></Strd></RmtInf>"
    BEIDE = ("<RmtInf><Ustrd>Factuur maart</Ustrd>"
             "<Strd><CdtrRefInf><Ref>RF00539007547034</Ref></CdtrRefInf></Strd></RmtInf>")

    def test_alleen_kenmerk(self):
        (t,) = parse(doc([ntry(rmtinf=self.STRD)]))
        self.assertEqual(t["description"], "Betalingskenmerk 1234567890123456")

    def test_uid_gebruikt_het_kenmerk_niet(self):
        (met,) = parse(doc([ntry(rmtinf=self.STRD)]))
        (zonder,) = parse(doc([ntry(rmtinf="")]))
        self.assertEqual(met["uid"], zonder["uid"])

    def test_omschrijving_en_kenmerk(self):
        (t,) = parse(doc([ntry(rmtinf=self.BEIDE)]))
        self.assertEqual(t["description"], "Factuur maart  Betalingskenmerk RF00539007547034")

    def test_uid_gelijk_met_en_zonder_kenmerk_naast_omschrijving(self):
        (met,) = parse(doc([ntry(rmtinf=self.BEIDE)]))
        (zonder,) = parse(doc([ntry(rmtinf="<RmtInf><Ustrd>Factuur maart</Ustrd></RmtInf>")]))
        self.assertEqual(met["uid"], zonder["uid"])

    def test_kenmerk_niet_dubbel(self):
        rmt = ("<RmtInf><Ustrd>Kenmerk 1234567890123456</Ustrd>"
               "<Strd><CdtrRefInf><Ref>1234567890123456</Ref></CdtrRefInf></Strd></RmtInf>")
        (t,) = parse(doc([ntry(rmtinf=rmt)]))
        self.assertEqual(t["description"], "Kenmerk 1234567890123456")


class Verzamelboeking(unittest.TestCase):
    """#29: elk onderdeel met een eigen bedrag wordt een eigen transactie."""

    def drie(self, **kw):
        return batch("60.00", [part("Winkel A", "10.00", "E1"), part("Winkel B", "20.00", "E2"),
                               part("Winkel C", "30.00", "E3")], **kw)

    def test_drie_onderdelen(self):
        r = parse(self.drie())
        self.assertEqual([(t["counterparty"], t["amount"]) for t in r],
                         [("Winkel A", -1000), ("Winkel B", -2000), ("Winkel C", -3000)])
        self.assertEqual([t["description"] for t in r],
                         ["Betaling Winkel A", "Betaling Winkel B", "Betaling Winkel C"])
        self.assertEqual(len({t["uid"] for t in r}), 3)

    def test_onderdelen_in_losse_ntrydtls(self):
        self.assertEqual(len(parse(self.drie(separate=True))), 3)

    def test_bijschrijving_met_bedrag_direct_in_txdtls(self):
        r = parse(batch("30.00", [part("Klant A", "10.00", "E1", "amt", ind="CRDT"),
                                  part("Klant B", "20.00", "E2", "amt", ind="CRDT")], ind="CRDT"))
        self.assertEqual([(t["counterparty"], t["amount"]) for t in r], [("Klant A", 1000), ("Klant B", 2000)])

    def test_onderdeel_met_tegengesteld_teken(self):
        r = parse(batch("10.00", [part("Winkel A", "30.00", "E1", "amt", ind="DBIT"),
                                  part("Winkel B", "20.00", "E2", "amt", ind="CRDT")]))
        self.assertEqual([t["amount"] for t in r], [-3000, 2000])

    def test_terugboeking(self):
        r = parse(batch("30.00", [part("Winkel A", "10.00", "E1"), part("Winkel B", "20.00", "E2")],
                        extra="<RvslInd>true</RvslInd>"))
        self.assertEqual([t["amount"] for t in r], [1000, 2000])

    def test_twee_gelijke_onderdelen(self):
        r = parse(batch("10.00", [part("Winkel A", "5.00", "E1"), part("Winkel A", "5.00", "E1")]))
        self.assertEqual(len(r), 2)
        self.assertEqual(len({t["uid"] for t in r}), 2)

    def assert_niet_gesplitst(self, data, total):
        (t,) = parse(data)
        self.assertEqual(t["amount"], total)
        self.assertEqual(t["counterparty"], "Winkel A")

    def test_som_klopt_niet(self):
        self.assert_niet_gesplitst(batch("60.00", [part("Winkel A", "10.00", "E1"),
                                                   part("Winkel B", "20.00", "E2")]), -6000)

    def test_onderdeel_zonder_bedrag(self):
        self.assert_niet_gesplitst(batch("30.00", [part("Winkel A", "10.00", "E1"),
                                                   part("Winkel B", "", "E2", "geen")]), -3000)

    def test_onderdeel_in_vreemde_valuta(self):
        self.assert_niet_gesplitst(batch("30.00", [part("Winkel A", "10.00", "E1"),
                                                   part("Winkel B", "22.00", "E2", ccy="USD")]), -3000)

    def test_een_onderdeel_houdt_de_uid_van_een_gewone_boeking(self):
        (los,) = parse(doc([ntry(rmtinf="<RmtInf><Ustrd>Betaling Winkel A</Ustrd></RmtInf>")
                            .replace("Winkel Voorbeeld", "Winkel A")]))
        (een,) = parse(batch("10.00", [part("Winkel A", "10.00", "E1")]))
        self.assertEqual(los["uid"], een["uid"])


if __name__ == "__main__":
    unittest.main()
