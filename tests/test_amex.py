"""Tests voor de American Express CSV-parser. Alle gegevens zijn verzonnen.

Draaien vanuit de hoofdmap:
    python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import parsers  # noqa: E402


def csv_of(rows, ref=True):
    """Een export met de gegeven (datum, bedrag)-regels."""
    out = ["Datum,Omschrijving,Kaartlid,Rekening #,Bedrag,Referentie,Land\n"]
    for i, (date, amount) in enumerate(rows):
        out.append('%s,WINKEL VOORBEELD        UTRECHT,DEMO GEBRUIKER,XXXX-XXXXX0-00000,"%s",%s,NETHERLANDS\n'
                   % (date, amount, "'REF%04d'" % i if ref else ""))
    return "".join(out).encode()


def parse(rows, **kw):
    return parsers.parse_amex_csv(csv_of(rows, **kw))


class Basis(unittest.TestCase):
    def test_gewone_regel(self):
        (t,) = parse([("03/15/2026", "12,50")])
        self.assertEqual(t["amount"], -1250)          # Amex: positief is een uitgave
        self.assertEqual(t["date"], "2026-03-15")
        self.assertEqual(t["source"], "amex")
        self.assertEqual(t["counterparty"], "Winkel Voorbeeld")
        self.assertEqual(t["cardholder"], "Demo Gebruiker")
        self.assertEqual(t["country"], "NETHERLANDS")
        self.assertEqual(t["uid"], "amex:REF0000")

    def test_betaling_is_positief(self):
        (t,) = parse([("03/15/2026", "-100,00")])
        self.assertEqual(t["amount"], 10000)

    def test_zonder_referentie_krijgt_elke_regel_een_uid(self):
        a, b = parse([("03/15/2026", "12,50"), ("03/15/2026", "12,50")], ref=False)
        self.assertNotEqual(a["uid"], b["uid"])

    def test_onbekend_formaat(self):
        with self.assertRaises(parsers.ImportFout):
            parsers.parse_amex_csv(b"a,b,c\n1,2,3\n")

    def test_leeg_bestand(self):
        with self.assertRaises(parsers.ImportFout):
            parsers.parse_amex_csv(b"Datum,Omschrijving,Bedrag\n")


class Bedrag(unittest.TestCase):
    """#31: Nederlandse en Engelse notatie; bij twijfel weigeren."""

    GOED = [
        ("12,50", 1250), ("-12,50", -1250), ("1.234,56", 123456), ("1,234.56", 123456),
        ("1234,56", 123456), ("1234.56", 123456), ("1.234", 123400), ("1,234", 123400),
        ("1.234.567", 123456700), ("1,234,567.89", 123456789), ("1.234.567,8", 123456780),
        ("0,5", 50), ("7", 700), ("€ 12,50", 1250), ("0.99", 99), ("-0,01", -1),
        ("1234", 123400), ("", 0), ("19,99", 1999), ("4.10", 410),
    ]
    FOUT = ["1,2345", "12.3456", "1.234,567", "1,23,45", "1.2.3", "12,34.5,6", "abc", "1,234.567",
            "1..2", ",50", "1.23,45", "1234,567.89", "12,3456.78"]

    def test_leesbare_bedragen(self):
        for text, cents in self.GOED:
            with self.subTest(bedrag=text):
                self.assertEqual(parsers._amount(text), cents)

    def test_onleesbare_bedragen_geweigerd(self):
        for text in self.FOUT:
            with self.subTest(bedrag=text):
                with self.assertRaises(parsers.ImportFout):
                    parsers._amount(text)

    def test_elk_bedrag_in_nederlandse_notatie(self):
        # elk aantal centen heen en terug, zonder afrondingsverschil
        for cents in range(0, 300000, 7):
            text = "%d,%02d" % (cents // 100, cents % 100)
            if parsers._amount(text) != cents:
                self.fail("%s werd %s" % (text, parsers._amount(text)))

    def test_engelse_notatie_in_bestand(self):
        (t,) = parse([("03/15/2026", "1,234.56")])
        self.assertEqual(t["amount"], -123456)

    def test_onleesbaar_bedrag_breekt_import_af(self):
        with self.assertRaises(parsers.ImportFout) as cm:
            parse([("03/15/2026", "1,2345")])
        self.assertIn("1,2345", str(cm.exception))


class Datum(unittest.TestCase):
    """#32: de volgorde van dag en maand volgt uit het hele bestand."""

    def dates(self, rows):
        return [t["date"] for t in parse([(d, "1,00") for d in rows])]

    def test_maand_dag_vastgelegd_door_andere_regel(self):
        self.assertEqual(self.dates(["05/01/2026", "03/15/2026"]), ["2026-05-01", "2026-03-15"])

    def test_dag_maand_vastgelegd_door_andere_regel(self):
        self.assertEqual(self.dates(["05/01/2026", "15/03/2026"]), ["2026-01-05", "2026-03-15"])

    def test_zonder_waarde_boven_twaalf_geldt_maand_dag(self):
        self.assertEqual(self.dates(["05/01/2026", "02/03/2026"]), ["2026-05-01", "2026-02-03"])

    def test_beide_volgordes_door_elkaar_geweigerd(self):
        with self.assertRaises(parsers.ImportFout) as cm:
            self.dates(["15/03/2026", "03/15/2026"])
        self.assertIn("door elkaar", str(cm.exception))

    def test_streepjes_zijn_dag_maand(self):
        self.assertEqual(self.dates(["05-01-2026", "25-12-2025"]), ["2026-01-05", "2025-12-25"])

    def test_onleesbare_datum_geeft_melding(self):
        with self.assertRaises(parsers.ImportFout) as cm:
            self.dates(["2026-01-05"])
        self.assertIn("2026-01-05", str(cm.exception))

    def test_niet_bestaande_datum_geeft_melding(self):
        with self.assertRaises(parsers.ImportFout):
            self.dates(["02/30/2026"])


if __name__ == "__main__":
    unittest.main()
