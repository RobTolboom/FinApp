"""Tests voor de schemaversie, de omzettingen en de back-up vooraf. Alle gegevens zijn verzonnen.

Draaien vanuit de hoofdmap:
    python3 -m unittest discover -s tests
"""
import glob
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import app  # noqa: E402

# transacties zoals de tabel was voordat de kolom 'country' bestond
OLD_TRANSACTIONS = """
CREATE TABLE transactions (
    uid TEXT PRIMARY KEY, source TEXT, account TEXT, date TEXT, amount INTEGER,
    counterparty TEXT, counterparty_iban TEXT, description TEXT, tx_type TEXT,
    creditor_id TEXT, mandate_id TEXT, cardholder TEXT, foreign_amt TEXT,
    merchant_key TEXT, import_id INTEGER
);
"""
# kaartbetaling met de plaats in het naamveld; de echte naam staat vooraan in de omschrijving
CARD_ROW = ("u1", "bank", "NL00DEMO0000000001", "2026-03-05", -1250, "VOORBEELDSTAD", "",
            "Winkel Voorbeeld 12  VOORBEELDSTAD  BEA Nr 1AB234 05.03.26 12.00", "", "", "", "", "",
            "VOORBEELDSTAD", 1)
PLAIN_ROW = ("u2", "bank", "NL00DEMO0000000001", "2026-03-06", -990, "Verzekeraar Voorbeeld", "",
             "Premie maart", "", "", "", "", "", "INC|VERZEKERAAR VOORBEELD", 1)


def structure(path):
    """Tabellen en indexen met per tabel de kolommen (naam, type), los van de schrijfwijze van de SQL."""
    c = sqlite3.connect(path)
    try:
        names = sorted((r[0], r[1]) for r in c.execute(
            "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))
        cols = {n: sorted((r[1], r[2]) for r in c.execute("PRAGMA table_info(%s)" % n))
                for t, n in names if t == "table"}
        return names, cols
    finally:
        c.close()


def version(path):
    c = sqlite3.connect(path)
    try:
        return c.execute("PRAGMA user_version").fetchone()[0]
    finally:
        c.close()


def rows(path, sql="SELECT uid, counterparty, merchant_key FROM transactions ORDER BY uid"):
    c = sqlite3.connect(path)
    try:
        return c.execute(sql).fetchall()
    finally:
        c.close()


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.db = os.path.join(self.dir.name, "finapp.db")

    def backups(self):
        return sorted(glob.glob(os.path.join(self.dir.name, "finapp.backup-*.db")))

    def old_db(self, with_country=False):
        """Een database van voor de schemaversie (versie 0) met twee transacties."""
        c = sqlite3.connect(self.db)
        c.executescript(OLD_TRANSACTIONS)
        if with_country:
            c.execute("ALTER TABLE transactions ADD COLUMN country TEXT DEFAULT ''")
        marks = ",".join("?" * 15)
        cols = "uid, source, account, date, amount, counterparty, counterparty_iban, description, tx_type, " \
               "creditor_id, mandate_id, cardholder, foreign_amt, merchant_key, import_id"
        for row in (CARD_ROW, PLAIN_ROW):
            c.execute("INSERT INTO transactions (%s) VALUES (%s)" % (cols, marks), row)
        c.commit()
        c.close()

    # ------------------------------------------------------------ nieuwe database
    def test_new_database_gets_latest_version_without_backup(self):
        store = app.Store(self.db)
        self.assertEqual(version(self.db), len(app.MIGRATIONS))
        self.assertEqual(self.backups(), [])
        self.assertIsNone(store.migrated_from)
        self.assertIsNone(store.backup_path)

    def test_new_database_has_country_column(self):
        app.Store(self.db)
        self.assertIn(("country", "TEXT"), structure(self.db)[1]["transactions"])

    # ------------------------------------------------------------ bestaande database
    def test_old_database_is_migrated_with_backup(self):
        self.old_db()
        store = app.Store(self.db)
        self.assertEqual(version(self.db), len(app.MIGRATIONS))
        self.assertEqual(store.migrated_from, 0)
        self.assertEqual(self.backups(), [str(store.backup_path)])
        self.assertIn(("country", "TEXT"), structure(self.db)[1]["transactions"])
        # de plaatsnaam is vervangen door de winkelnaam, de andere transactie is ongemoeid
        self.assertEqual(rows(self.db), [("u1", "Winkel Voorbeeld 12", "WINKEL VOORBEELD"),
                                         ("u2", "Verzekeraar Voorbeeld", "INC|VERZEKERAAR VOORBEELD")])

    def test_backup_holds_old_content_and_version(self):
        self.old_db()
        store = app.Store(self.db)
        backup = str(store.backup_path)
        self.assertRegex(os.path.basename(backup), r"^finapp\.backup-v0-\d{8}-\d{6}\.db$")
        self.assertEqual(version(backup), 0)
        self.assertNotIn(("country", "TEXT"), structure(backup)[1]["transactions"])
        self.assertEqual(rows(backup)[0], ("u1", "VOORBEELDSTAD", "VOORBEELDSTAD"))

    def test_backup_has_same_permissions_as_database(self):
        self.old_db()
        os.chmod(self.db, 0o600)
        store = app.Store(self.db)
        self.assertEqual(os.stat(str(store.backup_path)).st_mode & 0o777, 0o600)

    def test_old_database_that_already_has_country(self):
        self.old_db(with_country=True)
        app.Store(self.db)
        self.assertEqual(version(self.db), len(app.MIGRATIONS))
        self.assertEqual(len(self.backups()), 1)

    def test_second_start_does_nothing(self):
        self.old_db()
        app.Store(self.db)
        before = (self.backups(), rows(self.db), version(self.db))
        store = app.Store(self.db)
        self.assertEqual((self.backups(), rows(self.db), version(self.db)), before)
        self.assertIsNone(store.migrated_from)

    def test_new_and_migrated_database_have_the_same_structure(self):
        self.old_db()
        app.Store(self.db)
        fresh = os.path.join(self.dir.name, "nieuw.db")
        app.Store(fresh)
        self.assertEqual(structure(self.db), structure(fresh))

    def test_one_backup_for_several_migrations(self):
        self.old_db()

        def second(c):
            c.execute("UPDATE transactions SET description='omgezet' WHERE uid='u2'")

        with mock.patch.object(app, "MIGRATIONS", app.MIGRATIONS + [second]):
            store = app.Store(self.db)
        self.assertEqual(version(self.db), 2)
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(store.migrated_from, 0)
        self.assertEqual(rows(self.db, "SELECT description FROM transactions WHERE uid='u2'"), [("omgezet",)])

    # ------------------------------------------------------------ fouten
    def test_failing_migration_changes_nothing(self):
        self.old_db()
        app.Store(self.db)                      # naar de huidige versie
        current = version(self.db)
        before = rows(self.db)

        def broken(c):
            c.execute("UPDATE transactions SET counterparty='kapot'")
            c.execute("ALTER TABLE transactions ADD COLUMN tijdelijk TEXT")
            raise RuntimeError("halverwege mis")

        with mock.patch.object(app, "MIGRATIONS", app.MIGRATIONS + [broken]):
            with self.assertRaises(app.DatabaseFout) as ctx:
                app.Store(self.db)
        self.assertIn("halverwege mis", str(ctx.exception))
        self.assertEqual(version(self.db), current)
        self.assertEqual(rows(self.db), before)
        self.assertNotIn(("tijdelijk", "TEXT"), structure(self.db)[1]["transactions"])
        # de back-up van voor de mislukte omzetting staat er en wordt genoemd
        backup = [b for b in self.backups() if "-v%d-" % current in b]
        self.assertEqual(len(backup), 1)
        self.assertIn(backup[0], str(ctx.exception))

    def test_earlier_migrations_stay_when_a_later_one_fails(self):
        self.old_db()

        def broken(c):
            raise RuntimeError("mis")

        with mock.patch.object(app, "MIGRATIONS", app.MIGRATIONS + [broken]):
            with self.assertRaises(app.DatabaseFout):
                app.Store(self.db)
        self.assertEqual(version(self.db), len(app.MIGRATIONS))
        self.assertEqual(rows(self.db)[0], ("u1", "Winkel Voorbeeld 12", "WINKEL VOORBEELD"))

    def test_newer_database_is_refused_and_untouched(self):
        app.Store(self.db)
        c = sqlite3.connect(self.db)
        c.execute("PRAGMA user_version = %d" % (len(app.MIGRATIONS) + 1))
        c.execute("CREATE TABLE van_later (x TEXT)")
        c.commit()
        c.close()
        before = (structure(self.db), os.path.getsize(self.db))
        with self.assertRaises(app.DatabaseFout) as ctx:
            app.Store(self.db)
        self.assertIn("werk de code bij", str(ctx.exception))
        self.assertEqual((structure(self.db), os.path.getsize(self.db)), before)
        self.assertEqual(version(self.db), len(app.MIGRATIONS) + 1)
        self.assertEqual(self.backups(), [])

    def test_no_migration_when_backup_fails(self):
        self.old_db()
        before = (structure(self.db), rows(self.db))
        real = sqlite3.connect

        def connect(path, *a, **kw):
            if ".backup-" in str(path):
                raise sqlite3.OperationalError("unable to open database file")
            return real(path, *a, **kw)

        with mock.patch.object(app.sqlite3, "connect", side_effect=connect):
            with self.assertRaises(app.DatabaseFout) as ctx:
                app.Store(self.db)
        self.assertIn("geen back-up", str(ctx.exception))
        self.assertEqual(version(self.db), 0)
        self.assertEqual((structure(self.db), rows(self.db)), before)
        self.assertEqual(self.backups(), [])


if __name__ == "__main__":
    unittest.main()
