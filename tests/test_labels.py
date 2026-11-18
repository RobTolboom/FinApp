"""Tests voor het beheren van labels. Alle gegevens zijn verzonnen.

Draaien vanuit de hoofdmap:
    python3 -m unittest discover -s tests
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import app  # noqa: E402


class LabelTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.store = app.Store(os.path.join(self.dir.name, "finapp.db"))
        self.a = self.store.label({"action": "add", "name": "Verbouwing"})["id"]
        self.b = self.store.label({"action": "add", "name": "Zakelijk"})["id"]

    def names(self):
        with self.store.conn() as c:
            return {r["id"]: r["name"] for r in c.execute("SELECT id, name FROM labels")}

    def test_rename(self):
        self.store.label({"action": "rename", "id": self.a, "name": "  Keuken  "})
        self.assertEqual(self.names(), {self.a: "Keuken", self.b: "Zakelijk"})

    def test_rename_to_own_name_is_allowed(self):
        self.store.label({"action": "rename", "id": self.a, "name": "Verbouwing"})
        self.assertEqual(self.names()[self.a], "Verbouwing")

    def test_rename_to_existing_name_gives_clear_message(self):
        with self.assertRaises(ValueError) as ctx:
            self.store.label({"action": "rename", "id": self.a, "name": "Zakelijk"})
        self.assertEqual(str(ctx.exception), "Er bestaat al een label met deze naam")
        self.assertEqual(self.names(), {self.a: "Verbouwing", self.b: "Zakelijk"})

    def test_rename_to_empty_name_is_refused(self):
        for name in ("", "   ", None):
            with self.assertRaises(ValueError) as ctx:
                self.store.label({"action": "rename", "id": self.a, "name": name})
            self.assertEqual(str(ctx.exception), "Geef het label een naam")
        self.assertEqual(self.names()[self.a], "Verbouwing")

    def test_add_existing_name_gives_the_same_message(self):
        with self.assertRaises(ValueError) as ctx:
            self.store.label({"action": "add", "name": "Zakelijk"})
        self.assertEqual(str(ctx.exception), "Er bestaat al een label met deze naam")


if __name__ == "__main__":
    unittest.main()
