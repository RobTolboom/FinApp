"""Tests voor het woongebied: plaatsen leren, herkennen en beheren. Alle gegevens zijn verzonnen.

Draaien vanuit de hoofdmap:
    python3 -m unittest discover -s tests
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import app  # noqa: E402
import engine  # noqa: E402

CATS = [{"name": n, "kind": k} for n, k in (
    ("Overig", "expense"), ("Reizen & vakantie", "expense"), ("Overige inkomsten", "income"))]
VACATION = [{"name": "Zomer", "start": "2026-07-04", "end": "2026-07-17"}]
_n = [0]


def pin(day, city, name="Zaak Voorbeeld"):
    """Pinbetaling bij de bank; de plaats staat na de naam in de omschrijving."""
    _n[0] += 1
    return {"uid": "p%d" % _n[0], "source": "bank", "tx_type": "pin", "date": day, "amount": -1250,
            "counterparty": name, "counterparty_iban": "", "merchant_key": name.upper(),
            "description": "%s  %s  BEA Nr 1AB234 05.03.26 12.00" % (name, city), "country": ""}


def amex(day, city, country="", name="Zaak Voorbeeld"):
    """Amex-betaling; de winkelnaam staat in een vaste breedte van 23 tekens, daarna de plaats."""
    _n[0] += 1
    return {"uid": "a%d" % _n[0], "source": "amex", "tx_type": "", "date": day, "amount": -1250,
            "counterparty": name, "counterparty_iban": "", "merchant_key": name.upper(),
            "description": "%-23s %s" % (name[:23], city), "country": country}


def months(maker, city, n, **kw):
    """Eén betaling per maand in n maanden buiten de vakantie."""
    return [maker("2026-%02d-10" % m, city, **kw) for m in range(1, n + 1)]


def categorizer(txs, **kw):
    cz = engine.Categorizer(CATS, {}, {}, [], [], VACATION, **kw)
    cz.prepare(txs)
    return cz


class NormalizeTest(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(engine.normalize_place("'s-Gravenhage"), "S-GRAVENHAGE")
        self.assertEqual(engine.normalize_place("’s-Hertogenbosch"), "S-HERTOGENBOSCH")
        self.assertEqual(engine.normalize_place("  den   haag "), "DEN HAAG")
        self.assertEqual(engine.normalize_place(None), "")

    def test_exact(self):
        self.assertTrue(engine.place_matches("TESTSTAD", {"TESTSTAD"}))
        self.assertFalse(engine.place_matches("TESTSTAD", {"TESTDORP"}))
        self.assertFalse(engine.place_matches("", {"TESTSTAD"}))

    def test_truncated_name(self):
        self.assertTrue(engine.place_matches("S-HERTOGENBO", {"S-HERTOGENBOSCH"}))
        self.assertTrue(engine.place_matches("VOORBEEL", {"VOORBEELDDORP"}))          # precies 8 tekens

    def test_truncated_name_shorter_than_eight_is_no_match(self):
        self.assertFalse(engine.place_matches("VOORBEE", {"VOORBEELDDORP"}))
        self.assertFalse(engine.place_matches("TEST", {"TESTSTAD"}))

    def test_addition_after_a_space(self):
        self.assertTrue(engine.place_matches("TESTSTAD ZH", {"TESTSTAD"}))
        self.assertFalse(engine.place_matches("TESTSTADJE", {"TESTSTAD"}))

    def test_longer_name_in_transaction_is_no_match(self):
        # de lijst bevat de afgekapte vorm, de transactie de volledige: dat is een andere plaats
        self.assertFalse(engine.place_matches("VOORBEELDDORP", {"VOORBEEL"}))


class LearnTest(unittest.TestCase):
    def test_three_months_is_learned_two_is_not(self):
        cz = categorizer(months(pin, "TESTSTAD", 3) + months(pin, "TESTDORP", 2))
        self.assertEqual(cz.learned_places, {"TESTSTAD"})
        self.assertEqual(cz.place_months, {"TESTSTAD": 3, "TESTDORP": 2})

    def test_several_payments_in_one_month_count_once(self):
        cz = categorizer([pin("2026-03-%02d" % d, "TESTSTAD") for d in (1, 8, 15, 22)])
        self.assertEqual(cz.place_months, {"TESTSTAD": 1})
        self.assertEqual(cz.learned_places, set())

    def test_payments_during_a_vacation_do_not_count(self):
        txs = months(pin, "TESTSTAD", 2) + [pin("2026-07-10", "TESTSTAD")]
        self.assertEqual(categorizer(txs).learned_places, set())

    def test_only_card_payments_at_the_bank_count(self):
        txs = months(pin, "TESTSTAD", 3)
        for t in txs:
            t["tx_type"] = "ideal"
        self.assertEqual(categorizer(txs).place_months, {})

    def test_online_payments_do_not_count(self):
        txs = months(amex, "TESTSTAD", 3, name="WWW.VOORBEELD.COM")
        self.assertEqual(categorizer(txs).place_months, {})

    def test_amex_abroad_does_not_count(self):
        txs = months(amex, "TESTSTAD", 3, country="IRELAND")
        self.assertEqual(categorizer(txs).place_months, {})

    def test_amex_in_the_netherlands_or_without_country_counts(self):
        txs = months(amex, "TESTSTAD", 3, country="NETHERLANDS") + months(amex, "TESTDORP", 3, country="")
        self.assertEqual(categorizer(txs).learned_places, {"TESTSTAD", "TESTDORP"})

    def test_learning_switched_off(self):
        cz = categorizer(months(pin, "TESTSTAD", 3), home_learn=False, home_places=["Testdorp"])
        self.assertEqual(cz.learned_places, set())
        self.assertEqual(cz.home_cities, {"TESTDORP"})
        self.assertEqual(cz.place_months, {"TESTSTAD": 3})      # wel geteld, voor de suggesties

    def test_never_learn(self):
        cz = categorizer(months(pin, "TESTSTAD", 3) + months(pin, "TESTDORP", 3), never_learn=["teststad"])
        self.assertEqual(cz.learned_places, {"TESTDORP"})

    def test_own_place_is_home_without_payments(self):
        cz = categorizer([], home_places=["'s-Hertogenbosch"])
        self.assertTrue(cz.is_home("S-HERTOGENBO"))
        self.assertFalse(cz.is_home("TESTSTAD"))


class VacationTest(unittest.TestCase):
    def category(self, tx, history=(), **kw):
        return categorizer(list(history) + [tx], **kw).categorize(tx)

    def test_card_payment_elsewhere_during_vacation_is_travel(self):
        self.assertEqual(self.category(pin("2026-07-10", "VERWEGSTAD")), ("Reizen & vakantie", "vakantie: Zomer"))

    def test_card_payment_outside_vacation_is_not_travel(self):
        self.assertEqual(self.category(pin("2026-08-10", "VERWEGSTAD"))[0], "Overig")

    def test_learned_place_is_not_travel(self):
        self.assertEqual(self.category(pin("2026-07-10", "TESTSTAD"), months(pin, "TESTSTAD", 3))[0], "Overig")

    def test_own_place_is_not_travel(self):
        self.assertEqual(self.category(pin("2026-07-10", "TESTSTAD"), home_places=["Teststad"])[0], "Overig")

    def test_truncated_own_place_is_not_travel(self):
        tx = pin("2026-07-10", "S-HERTOGENBO")
        self.assertEqual(self.category(tx, home_places=["'s-Hertogenbosch"])[0], "Overig")

    def test_place_on_never_learn_is_travel(self):
        tx = pin("2026-07-10", "TESTSTAD")
        self.assertEqual(self.category(tx, months(pin, "TESTSTAD", 3), never_learn=["Teststad"])[0],
                         "Reizen & vakantie")

    def test_no_place_list_in_the_code(self):
        # zonder geleerde of eigen plaatsen is geen enkele plaats thuis
        self.assertEqual(categorizer([]).home_cities, set())
        self.assertFalse(hasattr(engine, "NL_CITIES"))


class HomeApiTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.store = app.Store(os.path.join(self.dir.name, "finapp.db"))

    def home(self):
        return self.store.data()["home"]

    def test_defaults(self):
        self.assertEqual(self.home(), {"learn": True, "places": [], "never_learn": [], "seen": []})

    def test_add_and_remove(self):
        self.store.home({"action": "add", "name": " 's-Hertogenbosch "})
        self.store.home({"action": "add", "name": "teststad"})
        self.store.home({"action": "add", "name": "TESTSTAD"})         # dubbel: geen tweede regel
        self.assertEqual(self.home()["places"], ["S-HERTOGENBOSCH", "TESTSTAD"])
        self.store.home({"action": "remove", "name": "Teststad"})
        self.assertEqual(self.home()["places"], ["S-HERTOGENBOSCH"])

    def test_never_learn_and_allow(self):
        self.store.home({"action": "never_learn", "name": "Teststad"})
        self.assertEqual(self.home()["never_learn"], ["TESTSTAD"])
        self.store.home({"action": "allow", "name": "teststad"})
        self.assertEqual(self.home()["never_learn"], [])

    def test_a_place_is_on_one_list_at_most(self):
        self.store.home({"action": "add", "name": "Teststad"})
        self.store.home({"action": "never_learn", "name": "Teststad"})
        self.assertEqual((self.home()["places"], self.home()["never_learn"]), ([], ["TESTSTAD"]))
        self.store.home({"action": "add", "name": "Teststad"})
        self.assertEqual((self.home()["places"], self.home()["never_learn"]), (["TESTSTAD"], []))

    def test_set_learn(self):
        self.store.home({"action": "set_learn", "learn": False})
        self.assertFalse(self.home()["learn"])
        self.store.home({"action": "set_learn", "learn": True})
        self.assertTrue(self.home()["learn"])

    def test_invalid_input(self):
        for body, message in (
                ({"action": "add", "name": "  "}, "Geef een plaatsnaam op"),
                ({"action": "add"}, "Geef een plaatsnaam op"),
                ({"action": "add", "name": "X" * 41}, "Een plaatsnaam is hooguit 40 tekens"),
                ({"action": "onbekend", "name": "Teststad"}, "Onbekende actie")):
            with self.assertRaises(ValueError) as ctx:
                self.store.home(body)
            self.assertEqual(str(ctx.exception), message)
        self.assertEqual(self.home()["places"], [])

    def test_list_is_limited(self):
        with mock_limit(3):
            for i in range(3):
                self.store.home({"action": "add", "name": "Plaats %d" % i})
            with self.assertRaises(ValueError) as ctx:
                self.store.home({"action": "add", "name": "Plaats 3"})
        self.assertEqual(str(ctx.exception), "Een lijst bevat hooguit 3 plaatsen")
        self.assertEqual(len(self.home()["places"]), 3)


def mock_limit(n):
    from unittest import mock
    return mock.patch.object(app, "HOME_LIST_MAX", n)


if __name__ == "__main__":
    unittest.main()
