"""Tests voor de hypotheekberekening. Alle gegevens zijn verzonnen.

Draaien vanuit de hoofdmap:
    python3 -m unittest discover -s tests
"""
import itertools
import os
import random
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import mortgage  # noqa: E402


def part(kind="annuitair", principal=20000000, rate=4.0, term=360, start="2024-01-15"):
    return {"principal": principal, "rate": rate, "term_months": term, "start": start, "kind": kind}


def corr(date, balance):
    return {"date": date, "balance": balance}


def row(sched, month):
    return next(r for r in sched if r["month"] == month)


class Schema(unittest.TestCase):
    def test_annuitair(self):
        s = mortgage.schedule(part())
        self.assertEqual(len(s), 360)
        self.assertEqual(s[0]["month"], "2024-02")            # eerste termijn in de maand na de ingangsdatum
        self.assertEqual(s[0]["interest"], 66667)             # 200.000 x 4% / 12
        self.assertEqual(s[-1]["balance"], 0)
        # de termijn (rente plus aflossing) is elke maand 954,83, op een cent
        # afronding na omdat rente en aflossing los worden afgerond
        payments = {r["interest"] + r["repayment"] for r in s}
        self.assertTrue(payments <= {95482, 95483, 95484}, payments)
        self.assertLess(s[0]["repayment"], s[-1]["repayment"])

    def test_lineair(self):
        s = mortgage.schedule(part("lineair", principal=12000000, term=120))
        self.assertEqual(len(s), 120)
        self.assertTrue(all(r["repayment"] == 100000 for r in s))
        self.assertEqual(s[0]["interest"], 40000)
        self.assertEqual(s[-1]["balance"], 0)

    def test_aflossingsvrij(self):
        s = mortgage.schedule(part("aflossingsvrij", principal=5000000, rate=3.0, term=24))
        self.assertEqual(len(s), 24)
        self.assertTrue(all(r["repayment"] == 0 and r["balance"] == 5000000 and r["interest"] == 12500 for r in s))

    def test_renteloos(self):
        s = mortgage.schedule(part(principal=1200000, rate=0.0, term=12))
        self.assertTrue(all(r["repayment"] == 100000 and r["interest"] == 0 for r in s))

    def test_rentewijziging_geldt_vanaf_die_maand(self):
        p = part("aflossingsvrij", principal=12000000, rate=4.0, term=24)
        s = mortgage.schedule(p, [{"date": "2024-07-01", "rate": 2.0}])
        self.assertEqual(row(s, "2024-06")["interest"], 40000)
        self.assertEqual(row(s, "2024-07")["interest"], 20000)

    def test_zonder_correctie_geen_extra(self):
        self.assertTrue(all(r["extra"] == 0 for r in mortgage.schedule(part())))

    def test_restschuld_per_maand(self):
        p = part()
        s = mortgage.schedule(p)
        self.assertIsNone(mortgage.balance_at(p, s, "2023-12"))            # voor de ingangsdatum
        self.assertEqual(mortgage.balance_at(p, s, "2024-01"), 20000000)   # startmaand: de hoofdsom
        self.assertEqual(mortgage.balance_at(p, s, "2024-02"), s[0]["balance"])
        self.assertEqual(mortgage.balance_at(p, s, "2060-01"), 0)          # na de looptijd


class Correctie(unittest.TestCase):
    def test_correctie_halverwege(self):
        p = part()
        c = [corr("2026-06-30", 18000000)]
        s = mortgage.schedule(p, (), c)
        self.assertEqual(row(s, "2026-06")["balance"], 18000000)
        self.assertEqual(row(s, "2026-07")["interest"], 60000)             # 180.000 x 4% / 12
        self.assertEqual(s[-1]["balance"], 0)
        self.assertEqual(s[-1]["month"], "2054-01")                        # looptijd blijft gelijk

    def test_in_of_voor_de_startmaand_is_de_beginstand(self):
        """#33"""
        p = part()
        expected = mortgage.schedule(part(principal=19000000))
        for date in ("2024-01-20", "2024-01-01", "2023-11-30"):
            with self.subTest(datum=date):
                c = [corr(date, 19000000)]
                s = mortgage.schedule(p, (), c)
                self.assertEqual(s, expected)
                self.assertEqual(s[0]["interest"], 63333)                  # 190.000 x 4% / 12
                self.assertEqual(mortgage.balance_at(p, s, "2024-01", c), 19000000)

    def test_voor_de_ingangsdatum_nog_geen_restschuld(self):
        self.assertIsNone(mortgage.balance_at(part(), [], "2023-12", [corr("2023-11-30", 19000000)]))

    def test_laatste_vroege_correctie_telt(self):
        c = [corr("2023-10-01", 18000000), corr("2024-01-10", 19500000)]
        self.assertEqual(mortgage.schedule(part(), (), c), mortgage.schedule(part(principal=19500000)))

    def test_lineair_stap_volgt_de_beginstand(self):
        s = mortgage.schedule(part("lineair", term=120), (), [corr("2024-01-20", 12000000)])
        self.assertEqual(s[0]["repayment"], 100000)
        self.assertEqual(len(s), 120)
        self.assertEqual(s[-1]["balance"], 0)

    def test_vroege_en_latere_correctie_samen(self):
        p = part()
        c = [corr("2024-01-20", 19000000), corr("2025-01-31", 18000000)]
        s = mortgage.schedule(p, (), c)
        self.assertEqual(mortgage.balance_at(p, s, "2024-01", c), 19000000)
        self.assertEqual(mortgage.balance_at(p, s, "2025-01", c), 18000000)

    def test_correctie_in_de_startmaand_is_geen_extra_aflossing(self):
        s = mortgage.schedule(part(), (), [corr("2024-01-20", 19000000)])
        self.assertTrue(all(r["extra"] == 0 for r in s))

    def test_na_de_looptijd(self):
        p = part(principal=1200000, rate=0.0, term=12)
        c = [corr("2025-06-30", 500000)]
        s = mortgage.schedule(p, (), c)
        self.assertEqual(mortgage.balance_at(p, s, "2025-05", c), 0)
        self.assertEqual(mortgage.balance_at(p, s, "2025-07", c), 500000)

    def test_na_volledig_aflossen_binnen_de_looptijd(self):
        p = part(principal=1200000, rate=0.0, term=12)
        c = [corr("2024-04-30", 0), corr("2024-08-31", 300000)]
        s = mortgage.schedule(p, (), c)
        self.assertEqual(mortgage.balance_at(p, s, "2024-06", c), 0)
        self.assertEqual(mortgage.balance_at(p, s, "2024-08", c), 300000)
        self.assertEqual((s[-1]["month"], s[-1]["balance"]), ("2025-01", 0))

    def test_afgelost_zonder_latere_correctie_stopt_het_schema(self):
        p = part(principal=1200000, rate=0.0, term=12)
        s = mortgage.schedule(p, (), [corr("2024-04-30", 0)])
        self.assertEqual(s[-1]["month"], "2024-04")

    def test_aflossingsvrij_na_de_looptijd(self):
        p = part("aflossingsvrij", principal=5000000, term=24)
        c = [corr("2027-03-31", 2000000)]
        s = mortgage.schedule(p, (), c)
        self.assertEqual(mortgage.balance_at(p, s, "2027-02", c), 5000000)
        self.assertEqual(mortgage.balance_at(p, s, "2027-04", c), 2000000)


class ExtraAflossing(unittest.TestCase):
    """#34: het verschil door een correctie telt als aflossing in die maand."""

    def setUp(self):
        self.p = part()
        self.basis = mortgage.schedule(self.p)
        self.voor = row(self.basis, "2025-06")["balance"]

    def test_extra_in_de_maand_van_de_correctie(self):
        s = mortgage.schedule(self.p, (), [corr("2025-06-30", self.voor - 1000000)])
        r = row(s, "2025-06")
        self.assertEqual(r["extra"], 1000000)
        self.assertEqual(r["repayment"], row(self.basis, "2025-06")["repayment"])
        self.assertTrue(all(x["extra"] == 0 for x in s if x["month"] != "2025-06"))

    def test_jaartotaal_is_de_daling_van_de_restschuld(self):
        c = [corr("2025-06-30", self.voor - 1000000)]
        s = mortgage.schedule(self.p, (), c)
        total = sum(r["repayment"] + r["extra"] for r in s if r["month"][:4] == "2025")
        drop = mortgage.balance_at(self.p, s, "2024-12", c) - mortgage.balance_at(self.p, s, "2025-12", c)
        self.assertLessEqual(abs(total - drop), 12)            # hoogstens een cent afronding per maand

    def test_correctie_omhoog_is_negatief(self):
        s = mortgage.schedule(self.p, (), [corr("2025-06-30", self.voor + 250000)])
        self.assertEqual(row(s, "2025-06")["extra"], -250000)


# (termijn, aflossing) per leningdeel; C is aflossingsvrij
A, B, C = (60000, 20000), (40000, 15000), (50000, 0)
TERMS = {"2026-03": [A, B, C]}


def split(payments, terms=TERMS):
    return mortgage.split_repayments(payments, terms)


class Splitsing(unittest.TestCase):
    """#35: elke afschrijving krijgt de aflossing van haar eigen leningdelen."""

    def maart(self, payments, terms=TERMS):
        return split({"2026-03": payments}, terms)["2026-03"]

    def test_een_afschrijving_voor_alle_leningdelen(self):
        self.assertEqual(self.maart([150000]), [35000])

    def test_twee_geldverstrekkers(self):
        self.assertEqual(self.maart([100000, 50000]), [35000, 0])
        self.assertEqual(self.maart([50000, 100000]), [0, 35000])

    def test_drie_losse_afschrijvingen(self):
        self.assertEqual(self.maart([40000, 50000, 60000]), [15000, 0, 20000])

    def test_binnen_de_marge(self):
        self.assertEqual(self.maart([100300, 49800]), [35000, 0])

    def test_eenmalige_betaling_ernaast_krijgt_niets(self):
        self.assertEqual(self.maart([150000, 250000]), [35000, 0])
        self.assertEqual(self.maart([1000000, 150000]), [0, 35000])

    def test_niets_past_een_afschrijving(self):
        self.assertEqual(self.maart([175000]), [35000])

    def test_niets_past_twee_afschrijvingen_naar_rato(self):
        self.assertEqual(self.maart([130000, 75000]), [22195, 12805])

    def test_een_past_de_rest_gaat_naar_de_andere(self):
        self.assertEqual(self.maart([120000, 60000]), [15000, 20000])

    def test_premie_bij_de_ene_geldverstrekker(self):
        self.assertEqual(self.maart([104000, 50000]), [35000, 0])

    def test_premie_en_eenmalige_betaling(self):
        r = self.maart([104000, 50000, 250000])
        self.assertEqual(sum(r), 35000)
        self.assertEqual(r[1], 0)

    def test_aflossing_nooit_hoger_dan_de_afschrijving(self):
        self.assertEqual(self.maart([10000], {"2026-03": [(10000, 30000)]}), [10000])

    def test_maand_zonder_schema(self):
        self.assertEqual(split({"2020-01": [150000]}), {"2020-01": [0]})

    def test_geen_afschrijvingen(self):
        self.assertEqual(split({}), {})

    def test_twee_gelijke_bedragen(self):
        self.assertEqual(sum(self.maart([70000, 70000], {"2026-03": [(70000, 30000), (70000, 0)]})), 30000)

    def test_te_veel_combinaties_valt_terug_op_naar_rato(self):
        veel = {"2026-03": [(10000 + i, 1000) for i in range(12)]}
        self.assertEqual(sum(self.maart([50000] * 6, veel)), 12000)


# één geldverstrekker: termijn van 1.000 euro met oplopende aflossing
EEN = {"2026-%02d" % m: [(100000, 30000 + m * 100)] for m in range(1, 7)}
# twee geldverstrekkers: de tweede is aflossingsvrij
TWEE = {"2026-%02d" % m: [(100000, 30000 + m * 100), (50000, 0)] for m in range(1, 7)}


class VerschovenIncasso(unittest.TestCase):
    def test_naar_de_volgende_maand(self):
        r = split({"2026-01": [100000], "2026-03": [100000, 100000], "2026-04": [100000]}, EEN)
        self.assertEqual(r["2026-01"], [30100])
        self.assertEqual(sorted(r["2026-03"]), [30200, 30300])
        self.assertEqual(r["2026-04"], [30400])

    def test_naar_de_vorige_maand(self):
        r = split({"2026-01": [100000], "2026-02": [100000, 100000], "2026-04": [100000]}, EEN)
        self.assertEqual(sorted(r["2026-02"]), [30200, 30300])
        self.assertEqual(r["2026-04"], [30400])

    def test_overgeslagen_maand_zonder_extra_afschrijving(self):
        r = split({"2026-01": [100000], "2026-03": [100000], "2026-04": [100000]}, EEN)
        self.assertEqual(r, {"2026-01": [30100], "2026-03": [30300], "2026-04": [30400]})

    def test_extra_afschrijving_zonder_lege_buurmaand(self):
        r = split({"2026-01": [100000], "2026-02": [100000, 100000], "2026-03": [100000]}, EEN)
        self.assertEqual(sorted(r["2026-02"]), [0, 30200])

    def test_eerste_maand_met_twee_afschrijvingen(self):
        r = split({"2026-02": [100000, 100000]}, EEN)
        self.assertEqual(sorted(r["2026-02"]), [30100, 30200])

    def test_twee_geldverstrekkers_beide_verschoven(self):
        r = split({"2026-01": [100000, 50000], "2026-03": [100000, 50000, 100000, 50000],
                   "2026-04": [50000, 100000]}, TWEE)
        self.assertEqual(sorted(r["2026-03"]), [0, 0, 30200, 30300])
        self.assertEqual(r["2026-04"], [0, 30400])
        self.assertEqual(sum(sum(v) for v in r.values()), 30100 + 30200 + 30300 + 30400)

    def test_twee_geldverstrekkers_een_verschoven(self):
        r = split({"2026-01": [100000, 50000], "2026-02": [50000], "2026-03": [100000, 100000, 50000],
                   "2026-04": [100000, 50000]}, TWEE)
        self.assertEqual(r["2026-02"], [0])
        self.assertEqual(sorted(r["2026-03"]), [0, 30200, 30300])
        self.assertEqual(r["2026-04"], [30400, 0])

    def test_twee_geldverstrekkers_een_vervroegd(self):
        r = split({"2026-01": [100000, 50000], "2026-02": [100000, 100000, 50000], "2026-03": [50000],
                   "2026-04": [100000, 50000]}, TWEE)
        self.assertEqual(r["2026-03"], [0])
        self.assertEqual(sorted(r["2026-02"]), [0, 30200, 30300])


def assign_all(payments, terms):
    """Vergelijkingsmaat voor _assign: rekent elke verdeling door, zonder iets over te slaan."""
    k, n = len(payments), len(terms)
    best, best_score = None, None
    for choice in itertools.product(range(k + 1), repeat=n):
        choice = choice[::-1]          # de eerste termijn wisselt het snelst
        total = [0] * k
        for i, c in enumerate(choice):
            if c < k:
                total[c] += terms[i][0]
        used = set(c for c in choice if c < k)
        if used and all(mortgage._fits(payments[j], total[j]) for j in used):
            score = (len([c for c in choice if c < k]), -sum(abs(payments[j] - total[j]) for j in used))
            if best_score is None or score > best_score:
                best, best_score = choice, score
    return [c if c < k else None for c in best] if best else [None] * n


class Snelheid(unittest.TestCase):
    """De verdeling slaat takken over die niets kunnen opleveren; de uitkomst blijft gelijk."""

    def test_zelfde_uitkomst_als_alles_doorrekenen(self):
        r = random.Random(7)
        for _ in range(1500):
            n, k = r.randrange(1, 7), r.randrange(1, 4)
            terms = [(r.choice([10000, 25000, 25000, 40000, 61000, r.randrange(5000, 90000)]), 1)
                     for _ in range(n)]
            payments = []
            for _ in range(k):
                group = r.sample(terms, r.randrange(0, n + 1))
                payments.append(max(1, sum(t[0] for t in group) + r.choice([0, 0, 300, -300, 7000]))
                                if group else r.randrange(3000, 90000))
            self.assertEqual(mortgage._assign(payments, terms), assign_all(payments, terms), (payments, terms))

    def test_onthouden_uitkomst_is_een_kopie(self):
        memo = {}
        first = mortgage._assign([100000, 50000], [A, B, C], memo)
        first[0] = "gewijzigd"
        self.assertEqual(mortgage._assign([100000, 50000], [A, B, C], memo), [0, 0, 1])

    def test_acht_leningdelen_twintig_jaar(self):
        # twee geldverstrekkers met elk vier leningdelen en een maandelijkse premie
        base = [61000, 47000, 83000, 29000, 55000, 38000, 72000, 44000]
        payments, terms = {}, {}
        for i in range(240):
            month = "%04d-%02d" % (2005 + i // 12, i % 12 + 1)
            terms[month] = [(b, b // 3 + i * 50) for b in base]
            payments[month] = [sum(base[0::2]), sum(base[1::2]), 4500]
        start = time.time()
        r = mortgage.split_repayments(payments, terms)
        self.assertLess(time.time() - start, 2.0)          # was ruim tien seconden
        for month, ts in terms.items():
            self.assertEqual(r[month], [sum(t[1] for t in ts[0::2]), sum(t[1] for t in ts[1::2]), 0])


if __name__ == "__main__":
    unittest.main()
