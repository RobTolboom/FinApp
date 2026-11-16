"""Tests voor de bedragen per maand en per jaar van vaste lasten. Alle gegevens zijn verzonnen.

Draaien vanuit de hoofdmap:
    python3 -m unittest discover -s tests
"""
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import engine  # noqa: E402

KIND = {"Wonen": "expense"}


def monthly(amount, months, name="Verhuurder Voorbeeld", step=1, start=(2025, 1)):
    """Eén afschrijving per 'step' maanden, steeds op de eerste van de maand."""
    txs = []
    for i in range(months):
        m = start[1] - 1 + i * step
        txs.append({"uid": "%s-%d" % (name, i), "date": "%04d-%02d-01" % (start[0] + m // 12, m % 12 + 1),
                    "amount": -amount, "merchant_key": name.upper(), "counterparty": name,
                    "source": "bank", "account": ""})
    return txs


def every(days, amount, count, name="Verhuurder Voorbeeld"):
    """Eén afschrijving per vast aantal dagen."""
    first = date(2025, 1, 6)
    return [{"uid": "%s-%d" % (name, i), "date": (first + timedelta(days=days * i)).isoformat(),
             "amount": -amount, "merchant_key": name.upper(), "counterparty": name,
             "source": "bank", "account": ""} for i in range(count)]


def recurring(txs):
    cat_of = {t["uid"]: "Wonen" for t in txs}
    results, _ = engine.find_recurring(txs, cat_of, KIND, {}, max(t["date"] for t in txs))
    return results


class BedragenTest(unittest.TestCase):
    def one(self, txs):
        results = recurring(txs)
        self.assertEqual(len(results), 1)
        return results[0]

    def check(self, txs, period, per_month, per_year):
        r = self.one(txs)
        self.assertEqual((r["period"], r["monthly"], r["yearly"]), (period, per_month, per_year))

    def test_maandelijks_is_twaalf_keer_per_jaar(self):
        self.check(monthly(115000, 12), "Maandelijks", 115000, 1380000)
        self.check(monthly(14215, 12), "Maandelijks", 14215, 170580)

    def test_tweemaandelijks(self):
        self.check(monthly(10000, 6, step=2), "Tweemaandelijks", 5000, 60000)

    def test_per_kwartaal(self):
        self.check(monthly(4560, 4, step=3), "Per kwartaal", 1520, 18240)

    def test_halfjaarlijks(self):
        self.check(monthly(10000, 4, step=6), "Halfjaarlijks", 1667, 20000)

    def test_jaarlijks(self):
        self.check(monthly(10000, 3, step=12), "Jaarlijks", 833, 10000)

    def test_wekelijks_en_tweewekelijks_gaan_via_dagen(self):
        # een jaar heeft 52,18 weken: 365,25 / 7
        self.check(every(7, 10000, 20), "Wekelijks", 43482, 521786)
        self.check(every(14, 10000, 12), "Tweewekelijks", 21741, 260893)

    def test_jaarbedrag_is_twaalf_keer_het_maandbedrag_bij_hele_centen(self):
        for amount in (115000, 5950, 1399, 1):
            r = self.one(monthly(amount, 12))
            self.assertEqual(r["yearly"], 12 * r["monthly"])

    def test_bedragen_zijn_hele_centen(self):
        r = self.one(monthly(3333, 4, step=3))
        self.assertIsInstance(r["monthly"], int)
        self.assertIsInstance(r["yearly"], int)
        self.assertEqual((r["monthly"], r["yearly"]), (1111, 13332))


if __name__ == "__main__":
    unittest.main()
