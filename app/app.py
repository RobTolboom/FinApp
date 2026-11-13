#!/usr/bin/env python3
"""FinApp: lokaal overzicht van je uitgaven en vaste lasten.

Start:  python3 app.py        (opent automatisch je browser)
Opties: python3 app.py --port 8765 --db /pad/naar/finapp.db --no-browser

Alles draait op je eigen computer. De server luistert alleen op 127.0.0.1
en er wordt niets naar internet verstuurd. Alleen Python 3.9+ (standaard
op macOS) is nodig; er zijn geen extra pakketten.
"""
import argparse
import base64
import hmac
import ipaddress
import json
import re
import os
import sqlite3
import sys
import threading
import unicodedata
import webbrowser
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine  # noqa: E402
import mortgage  # noqa: E402
import parsers  # noqa: E402
import rules as default_rules  # noqa: E402

STATIC = HERE / "static"


def default_db_path():
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "FinApp"
    else:
        base = Path.home() / ".finapp"
    return base / "finapp.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    uid TEXT PRIMARY KEY, source TEXT, account TEXT, date TEXT, amount INTEGER,
    counterparty TEXT, counterparty_iban TEXT, description TEXT, tx_type TEXT,
    creditor_id TEXT, mandate_id TEXT, cardholder TEXT, foreign_amt TEXT,
    merchant_key TEXT, import_id INTEGER
);
CREATE INDEX IF NOT EXISTS ix_tx_date ON transactions(date);
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, source TEXT,
    imported_at TEXT, added INTEGER, duplicates INTEGER, date_from TEXT, date_to TEXT
);
CREATE TABLE IF NOT EXISTS tx_overrides (uid TEXT PRIMARY KEY, category TEXT);
CREATE TABLE IF NOT EXISTS merchant_rules (key TEXT PRIMARY KEY, category TEXT);
CREATE TABLE IF NOT EXISTS recurring_overrides (key TEXT PRIMARY KEY, state TEXT);
CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY, kind TEXT, color TEXT, sort INTEGER);
CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS tx_flags (uid TEXT PRIMARY KEY, exclude INTEGER);
CREATE TABLE IF NOT EXISTS vacations (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, start TEXT, end TEXT);
CREATE TABLE IF NOT EXISTS balances (account TEXT, date TEXT, kind TEXT, amount INTEGER, PRIMARY KEY (account, date, kind));
CREATE TABLE IF NOT EXISTS assets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, side TEXT, sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS valuations (asset_id INTEGER, date TEXT, value INTEGER, PRIMARY KEY (asset_id, date));
CREATE TABLE IF NOT EXISTS labels (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, color TEXT);
CREATE TABLE IF NOT EXISTS tx_labels (uid TEXT, label_id INTEGER, PRIMARY KEY (uid, label_id));
CREATE TABLE IF NOT EXISTS mortgage_parts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, principal INTEGER,
    rate REAL, term_months INTEGER, start TEXT, kind TEXT);
CREATE TABLE IF NOT EXISTS mortgage_rates (part_id INTEGER, date TEXT, rate REAL, PRIMARY KEY (part_id, date));
CREATE TABLE IF NOT EXISTS mortgage_corrections (part_id INTEGER, date TEXT, balance INTEGER, PRIMARY KEY (part_id, date));
"""

LABEL_COLORS = ["#3a6fb3", "#c46a24", "#2e8b57", "#8f3f71", "#b8860b", "#56a3a6", "#9d4b4b", "#6b6fb3"]


def _month_end(key):
    y, m = int(key[:4]), int(key[5:7])
    nxt = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return (nxt - timedelta(days=1)).isoformat()


def _months(a, b):
    out, (y, m) = [], (int(a[:4]), int(a[5:7]))
    while "%04d-%02d" % (y, m) <= b:
        out.append("%04d-%02d" % (y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _cents(v):
    s = str(v).strip().replace("\u20ac", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")          # 450.000 = vierhonderdvijftigduizend
    return int(round(float(s) * 100))


EXTRA_COLORS = ["#6c8ebf", "#b85450", "#82b366", "#d6b656", "#9673a6", "#56a3a6", "#c98a4b"]


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        with self.conn() as c:
            c.row_factory = sqlite3.Row
            c.executescript(SCHEMA)
            cols = {r[1] for r in c.execute("PRAGMA table_info(transactions)")}
            if "country" not in cols:
                c.execute("ALTER TABLE transactions ADD COLUMN country TEXT DEFAULT ''")
            # plaatsnaam in het naamveld van kaartbetalingen herstellen
            for r in c.execute("SELECT uid, counterparty, description FROM transactions "
                               "WHERE source='bank' AND merchant_key NOT LIKE 'INC|%'").fetchall():
                fixed = parsers.card_merchant(r["counterparty"], r["description"])
                if fixed:
                    c.execute("UPDATE transactions SET counterparty=?, merchant_key=? WHERE uid=?",
                              (fixed.strip(), parsers.normalize_name(fixed), r["uid"]))
            for old, new in getattr(default_rules, "RENAMES", {}).items():
                if c.execute("SELECT 1 FROM categories WHERE name=?", (old,)).fetchone():
                    c.execute("DELETE FROM categories WHERE name=?", (old,))
                    c.execute("UPDATE tx_overrides SET category=? WHERE category=?", (new, old))
                    c.execute("UPDATE merchant_rules SET category=? WHERE category=?", (new, old))
            have = {r[0] for r in c.execute("SELECT name FROM categories")}
            for i, (name, kind, color) in enumerate(default_rules.CATEGORIES):
                if name not in have:
                    c.execute("INSERT INTO categories VALUES (?,?,?,?)", (name, kind, color, i))

    def conn(self):
        c = sqlite3.connect(str(self.path))
        c.row_factory = sqlite3.Row
        return c

    # ------------------------------------------------------------ lezen
    def settings(self):
        with self.conn() as c:
            s = {r["k"]: json.loads(r["v"]) for r in c.execute("SELECT k, v FROM settings")}
        s.setdefault("own_ibans", [])
        s.setdefault("own_names", [])
        s.setdefault("mortgage_split", True)
        s.setdefault("mortgage_match", "HYPOTHE")
        return s

    def data(self):
        with self.conn() as c:
            cats = [dict(r) for r in c.execute("SELECT * FROM categories ORDER BY sort, name")]
            txs = [dict(r) for r in c.execute("SELECT * FROM transactions ORDER BY date DESC, uid")]
            tx_ov = {r["uid"]: r["category"] for r in c.execute("SELECT * FROM tx_overrides")}
            m_rules = {r["key"]: r["category"] for r in c.execute("SELECT * FROM merchant_rules")}
            rec_ov = {r["key"]: r["state"] for r in c.execute("SELECT * FROM recurring_overrides")}
            imports = [dict(r) for r in c.execute("SELECT * FROM imports ORDER BY id DESC")]
            flags = {r["uid"] for r in c.execute("SELECT uid FROM tx_flags WHERE exclude=1")}
            vacations = [dict(r) for r in c.execute("SELECT * FROM vacations ORDER BY start DESC")]
            labels = [dict(r) for r in c.execute("SELECT * FROM labels ORDER BY name")]
            tx_labels = {}
            for r in c.execute("SELECT uid, label_id FROM tx_labels"):
                tx_labels.setdefault(r["uid"], []).append(r["label_id"])
            balances = [dict(r) for r in c.execute("SELECT * FROM balances ORDER BY date")]
            assets = [dict(r) for r in c.execute("SELECT * FROM assets ORDER BY sort, id")]
            vals = [dict(r) for r in c.execute("SELECT * FROM valuations ORDER BY date")]
            m_parts = [dict(r) for r in c.execute("SELECT * FROM mortgage_parts ORDER BY start, id")]
            m_rates = [dict(r) for r in c.execute("SELECT * FROM mortgage_rates ORDER BY date")]
            m_corr = [dict(r) for r in c.execute("SELECT * FROM mortgage_corrections ORDER BY date")]
        st = self.settings()
        cz = engine.Categorizer(cats, tx_ov, m_rules, st["own_ibans"], st["own_names"], vacations)
        cz.prepare(txs)
        kind_of = {c["name"]: c["kind"] for c in cats}
        cat_of = {}
        for t in txs:
            cat, why = cz.categorize(t)
            if cat not in kind_of:
                cat, why = ("Overige inkomsten" if t["amount"] > 0 else "Overig"), "onbekende categorie"
            t["category"], t["reason"] = cat, why
            t["kind"] = kind_of[cat]
            t["has_merchant_rule"] = t["merchant_key"] in m_rules
            t["excluded_by_category"] = cat in getattr(default_rules, "EXCLUDE_FROM_AVERAGES", set())
            t["excluded"] = t["uid"] in flags or t["excluded_by_category"]
            t["labels"] = tx_labels.get(t["uid"], [])
            cat_of[t["uid"]] = cat
        # Amex-aflossingen uit een periode waarvan geen Amex-transacties zijn
        # geïmporteerd, tellen als ongespecificeerde uitgave (anders ontbreken
        # die creditcarduitgaven helemaal). Een aflossing betaalt het overzicht
        # van de maand ervoor, vandaar 31 dagen speling.
        unspec = "Creditcard Amex (ongespecificeerd)"
        if unspec in kind_of:
            amex_dates = [t["date"] for t in txs if t["source"] == "amex"]
            cutoff = None
            if amex_dates:
                d0 = datetime.fromisoformat(min(amex_dates))
                cutoff = (d0 + timedelta(days=31)).date().isoformat()
            for t in txs:
                if (t["source"] == "bank" and t["category"] == "Creditcard aflossing"
                        and t["reason"] not in ("handmatig", "eigen regel")
                        and (cutoff is None or t["date"] < cutoff)):
                    t["category"], t["reason"] = unspec, "geen Amex-gegevens voor deze periode"
                    t["kind"] = kind_of[unspec]
                    cat_of[t["uid"]] = unspec
        mort = self._mortgage(m_parts, m_rates, m_corr)
        if st.get("mortgage_split") and mort["repay_by_month"] and "Aflossing hypotheek" in kind_of:
            txs = self._split_mortgage(txs, mort, st.get("mortgage_match") or "HYPOTHE", cat_of)
        end_date = txs[0]["date"] if txs else None
        recurring, member = engine.find_recurring(txs, cat_of, kind_of, rec_ov, end_date)
        for t in txs:
            t["group"] = member.get(t["uid"])
        for v in vacations:
            v["count"] = sum(1 for t in txs if t["reason"] == "vakantie: " + v["name"]
                             and v["start"] <= t["date"] <= v["end"])
        for r in recurring:
            r.pop("uids", None)
            r["override"] = rec_ov.get(r["key"])
        # handmatig als 'niet vast' gemarkeerd, zodat je dat kunt terugdraaien
        excluded = [k for k, v in rec_ov.items() if v == "no"]
        sources = {}
        for t in txs:
            if t.get("synthetic"):
                continue
            s = sources.setdefault(t["source"], {"count": 0, "from": t["date"], "to": t["date"]})
            s["count"] += 1
            s["from"] = min(s["from"], t["date"])
            s["to"] = max(s["to"], t["date"])
        return {
            "categories": cats, "settings": st, "transactions": txs,
            "recurring": recurring, "excluded_recurring": excluded,
            "imports": imports, "sources": sources, "end_date": end_date,
            "db_path": str(self.path), "vacations": vacations,
            "labels": labels, "networth": self._networth(txs, balances, assets, vals),
            "mortgage": {"parts": mort["parts"], "monthly_balance": mort["monthly_balance"]},
        }

    # ------------------------------------------------------------ hypotheek
    def _mortgage(self, parts, rates, corrs):
        today = date.today().isoformat()[:7]
        out, repay, interest, bal_total = [], {}, {}, {}
        if not parts:
            return {"parts": [], "repay_by_month": {}, "interest_by_month": {}, "monthly_balance": {}}
        first = min(p["start"][:7] for p in parts)
        months = _months(first, today)
        for p in parts:
            pr = [r for r in rates if r["part_id"] == p["id"]]
            pc = [c for c in corrs if c["part_id"] == p["id"]]
            sched = mortgage.schedule(p, pr, pc)
            for row in sched:
                repay[row["month"]] = repay.get(row["month"], 0) + row["repayment"]
                interest[row["month"]] = interest.get(row["month"], 0) + row["interest"]
            for mk in months:
                b = mortgage.balance_at(p, sched, mk)
                if b is not None:
                    bal_total[mk] = bal_total.get(mk, 0) + b
            cur = next((r for r in sched if r["month"] == today), None)
            yr = today[:4]
            q = dict(p)
            q.update({
                "rates": [{"date": r["date"], "rate": r["rate"]} for r in pr],
                "corrections": [{"date": c["date"], "balance": c["balance"]} for c in pc],
                "balance_now": mortgage.balance_at(p, sched, today),
                "payment_now": (cur["interest"] + cur["repayment"]) if cur else None,
                "interest_now": cur["interest"] if cur else None,
                "repayment_now": cur["repayment"] if cur else None,
                "interest_year": sum(r["interest"] for r in sched if r["month"][:4] == yr),
                "repayment_year": sum(r["repayment"] for r in sched if r["month"][:4] == yr),
                "end_month": sched[-1]["month"] if sched else None,
                "rate_now": ([r["rate"] for r in sorted(pr, key=lambda r: r["date"]) if r["date"][:7] <= today] or [p["rate"]])[-1],
            })
            out.append(q)
        return {"parts": out, "repay_by_month": repay, "interest_by_month": interest, "monthly_balance": bal_total}

    def _split_mortgage(self, txs, mort, pattern, cat_of):
        """Splitst de hypotheektermijn op de bankrekening in rente (blijft een
        uitgave onder Wonen) en aflossing (vermogensopbouw, telt niet mee)."""
        try:
            rx = re.compile(pattern, re.I)
        except re.error:
            rx = re.compile("HYPOTHE", re.I)
        done, out = set(), []
        for t in txs:
            out.append(t)
            mk = t["date"][:7]
            if (t["source"] != "bank" or t["amount"] >= 0 or t["category"] != "Wonen" or mk in done
                    or not rx.search("%s %s" % (t["counterparty"], t["description"]))):
                continue
            rep = min(mort["repay_by_month"].get(mk, 0), -t["amount"])
            if rep <= 0:
                continue
            done.add(mk)
            t["orig_amount"] = t["amount"]
            t["split_repayment"] = rep
            t["amount"] = t["amount"] + rep
            s = dict(t)
            s.update({"uid": t["uid"] + "#aflossing", "amount": -rep, "category": "Aflossing hypotheek",
                      "kind": "transfer", "reason": "aflossing volgens hypotheekschema", "synthetic": True,
                      "labels": [], "excluded": False, "excluded_by_category": False, "split_repayment": None})
            cat_of[s["uid"]] = s["category"]
            out.append(s)
        return out

    def mortgage_action(self, body):
        act = body.get("action")
        with self.lock, self.conn() as c:
            if act in ("add_part", "update_part"):
                name = (body.get("name") or "").strip() or "Leningdeel"
                principal = _cents(body["principal"])
                rate = float(str(body["rate"]).replace(",", ".").replace("%", "").strip())
                years = float(str(body.get("years") or "30").replace(",", "."))
                term = int(round(years * 12))
                start = body.get("start") or ""
                date.fromisoformat(start)
                kind = body.get("kind")
                if kind not in ("annuitair", "lineair", "aflossingsvrij"):
                    raise ValueError("Kies een aflosvorm")
                if principal <= 0 or term <= 0 or not (0 <= rate < 20):
                    raise ValueError("Controleer bedrag, rente en looptijd")
                if act == "add_part":
                    c.execute("INSERT INTO mortgage_parts (name, principal, rate, term_months, start, kind) VALUES (?,?,?,?,?,?)",
                              (name, principal, rate, term, start, kind))
                else:
                    c.execute("UPDATE mortgage_parts SET name=?, principal=?, rate=?, term_months=?, start=?, kind=? WHERE id=?",
                              (name, principal, rate, term, start, kind, int(body["id"])))
            elif act == "delete_part":
                pid = int(body["id"])
                for tbl in ("mortgage_rates", "mortgage_corrections"):
                    c.execute("DELETE FROM %s WHERE part_id=?" % tbl, (pid,))
                c.execute("DELETE FROM mortgage_parts WHERE id=?", (pid,))
            elif act == "add_rate":
                date.fromisoformat(body["date"])
                c.execute("INSERT OR REPLACE INTO mortgage_rates VALUES (?,?,?)",
                          (int(body["id"]), body["date"], float(str(body["rate"]).replace(",", ".").replace("%", ""))))
            elif act == "del_rate":
                c.execute("DELETE FROM mortgage_rates WHERE part_id=? AND date=?", (int(body["id"]), body["date"]))
            elif act == "add_corr":
                date.fromisoformat(body["date"])
                c.execute("INSERT OR REPLACE INTO mortgage_corrections VALUES (?,?,?)",
                          (int(body["id"]), body["date"], _cents(body["balance"])))
            elif act == "del_corr":
                c.execute("DELETE FROM mortgage_corrections WHERE part_id=? AND date=?", (int(body["id"]), body["date"]))
            elif act == "settings":
                c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", ("mortgage_split", json.dumps(bool(body.get("split")))))
                pat = (body.get("match") or "HYPOTHE").strip()
                re.compile(pat)
                c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", ("mortgage_match", json.dumps(pat)))
            else:
                raise ValueError("Onbekende actie")
        return {"ok": True}

    def _networth(self, txs, balances, assets, vals):
        """Maandelijkse eindstanden van de bankrekeningen (teruggerekend vanaf
        het laatste eindsaldo) en de handmatige waarderingen."""
        today = date.today().isoformat()
        accounts = []
        by_acct = {}
        for t in txs:
            if t["source"] == "bank" and t["account"] and not t.get("synthetic"):
                by_acct.setdefault(t["account"], []).append(t)
        for acct, rows in by_acct.items():
            anchors = [b for b in balances if b["account"] == acct and b["kind"] == "CLBD"]
            if not anchors:
                continue
            anchor = max(anchors, key=lambda b: b["date"])
            months = _months(min(t["date"] for t in rows)[:7], today[:7])
            series = {}
            for mk in months:
                end = min(_month_end(mk), today)
                bal = anchor["amount"]
                for t in rows:
                    amt = t.get("orig_amount", t["amount"])
                    if end < t["date"] <= anchor["date"]:
                        bal -= amt
                    elif anchor["date"] < t["date"] <= end:
                        bal += amt
                series[mk] = bal
            accounts.append({"account": acct, "anchor_date": anchor["date"], "anchor": anchor["amount"],
                             "monthly": series})
        for a in assets:
            a["valuations"] = [{"date": v["date"], "value": v["value"]} for v in vals if v["asset_id"] == a["id"]]
        return {"accounts": accounts, "assets": assets}

    # ------------------------------------------------------------ labels
    def label(self, body):
        act = body.get("action")
        with self.lock, self.conn() as c:
            if act == "add":
                name = (body.get("name") or "").strip()
                if not name:
                    raise ValueError("Geef het label een naam")
                n = c.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
                try:
                    cur = c.execute("INSERT INTO labels (name, color) VALUES (?,?)",
                                    (name, LABEL_COLORS[n % len(LABEL_COLORS)]))
                except sqlite3.IntegrityError:
                    raise ValueError("Er bestaat al een label met deze naam")
                return {"ok": True, "id": cur.lastrowid}
            if act == "rename":
                c.execute("UPDATE labels SET name=? WHERE id=?", (body["name"].strip(), int(body["id"])))
            elif act == "delete":
                c.execute("DELETE FROM tx_labels WHERE label_id=?", (int(body["id"]),))
                c.execute("DELETE FROM labels WHERE id=?", (int(body["id"]),))
            else:
                raise ValueError("Onbekende actie")
        return {"ok": True}

    def tx_labels(self, body):
        lid, uids = int(body["label_id"]), list(body.get("uids") or [])
        with self.lock, self.conn() as c:
            if body.get("action") == "remove":
                c.executemany("DELETE FROM tx_labels WHERE uid=? AND label_id=?", [(u, lid) for u in uids])
            else:
                c.executemany("INSERT OR IGNORE INTO tx_labels VALUES (?,?)", [(u, lid) for u in uids])
        return {"ok": True, "count": len(uids)}

    # ------------------------------------------------------------ vermogen
    def asset(self, body):
        act = body.get("action")
        with self.lock, self.conn() as c:
            if act == "add":
                name = (body.get("name") or "").strip()
                side = body.get("side")
                if not name or side not in ("bezit", "schuld"):
                    raise ValueError("Geef een naam en kies bezit of schuld")
                cur = c.execute("INSERT INTO assets (name, side) VALUES (?,?)", (name, side))
                aid = cur.lastrowid
                if body.get("value") not in (None, ""):
                    c.execute("INSERT OR REPLACE INTO valuations VALUES (?,?,?)",
                              (aid, body.get("date") or date.today().isoformat(), _cents(body["value"])))
                return {"ok": True, "id": aid}
            if act == "delete":
                c.execute("DELETE FROM valuations WHERE asset_id=?", (int(body["id"]),))
                c.execute("DELETE FROM assets WHERE id=?", (int(body["id"]),))
            elif act == "value":
                d = body.get("date") or date.today().isoformat()
                date.fromisoformat(d)
                c.execute("INSERT OR REPLACE INTO valuations VALUES (?,?,?)", (int(body["id"]), d, _cents(body["value"])))
            elif act == "delvalue":
                c.execute("DELETE FROM valuations WHERE asset_id=? AND date=?", (int(body["id"]), body["date"]))
            else:
                raise ValueError("Onbekende actie")
        return {"ok": True}

    # ------------------------------------------------------------ schrijven
    def import_file(self, filename, blob):
        filename = os.path.basename(filename)
        txs = parsers.detect_and_parse(filename, blob)
        bals = parsers.camt_balances(blob) if txs and txs[0]["source"] == "bank" else []
        with self.lock, self.conn() as c:
            for b in bals:
                c.execute("INSERT OR REPLACE INTO balances VALUES (?,?,?,?)",
                          (b["account"], b["date"], b["kind"], b["amount"]))
            cur = c.execute(
                "INSERT INTO imports (filename, source, imported_at, added, duplicates, date_from, date_to)"
                " VALUES (?,?,?,?,?,?,?)",
                (filename, txs[0]["source"], datetime.now().isoformat(timespec="seconds"), 0, 0,
                 min(t["date"] for t in txs), max(t["date"] for t in txs)))
            imp_id = cur.lastrowid
            added = dup = 0
            for t in txs:
                try:
                    c.execute(
                        "INSERT INTO transactions (uid, source, account, date, amount, counterparty,"
                        " counterparty_iban, description, tx_type, creditor_id, mandate_id, cardholder,"
                        " foreign_amt, merchant_key, import_id, country)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (t["uid"], t["source"], t["account"], t["date"], t["amount"], t["counterparty"],
                         t["counterparty_iban"], t["description"], t["tx_type"], t["creditor_id"],
                         t["mandate_id"], t["cardholder"], t["foreign"], t["merchant_key"], imp_id,
                         t.get("country", "")))
                    added += 1
                except sqlite3.IntegrityError:
                    dup += 1
            if added:
                c.execute("UPDATE imports SET added=?, duplicates=? WHERE id=?", (added, dup, imp_id))
            else:
                # niets nieuws: geen regel in de importgeschiedenis
                c.execute("DELETE FROM imports WHERE id=?", (imp_id,))
        return {"source": txs[0]["source"], "added": added, "duplicates": dup, "total": len(txs),
                "from": min(t["date"] for t in txs), "to": max(t["date"] for t in txs)}

    def delete_import(self, imp_id):
        with self.lock, self.conn() as c:
            n = c.execute("DELETE FROM transactions WHERE import_id=?", (imp_id,)).rowcount
            c.execute("DELETE FROM imports WHERE id=?", (imp_id,))
        return {"deleted": n}

    def categorize(self, uid, category, scope):
        with self.lock, self.conn() as c:
            if scope == "merchant":
                row = c.execute("SELECT merchant_key FROM transactions WHERE uid=?", (uid,)).fetchone()
                if not row:
                    raise ValueError("Transactie niet gevonden")
                key = row["merchant_key"]
                if category:
                    c.execute("INSERT OR REPLACE INTO merchant_rules VALUES (?,?)", (key, category))
                else:
                    c.execute("DELETE FROM merchant_rules WHERE key=?", (key,))
                # losse uitzondering op deze transactie vervalt
                c.execute("DELETE FROM tx_overrides WHERE uid=?", (uid,))
            else:
                if category:
                    c.execute("INSERT OR REPLACE INTO tx_overrides VALUES (?,?)", (uid, category))
                else:
                    c.execute("DELETE FROM tx_overrides WHERE uid=?", (uid,))
        return {"ok": True}

    def set_exclude(self, uid, exclude):
        with self.lock, self.conn() as c:
            if exclude:
                c.execute("INSERT OR REPLACE INTO tx_flags VALUES (?,1)", (uid,))
            else:
                c.execute("DELETE FROM tx_flags WHERE uid=?", (uid,))
        return {"ok": True}

    def vacation(self, body):
        with self.lock, self.conn() as c:
            if body.get("action") == "delete":
                c.execute("DELETE FROM vacations WHERE id=?", (int(body["id"]),))
            else:
                name = (body.get("name") or "").strip() or "Vakantie"
                start, end = body.get("start") or "", body.get("end") or ""
                try:
                    if datetime.fromisoformat(end) < datetime.fromisoformat(start):
                        raise ValueError
                except ValueError:
                    raise ValueError("Geef een geldige begin- en einddatum op")
                c.execute("INSERT INTO vacations (name, start, end) VALUES (?,?,?)", (name, start, end))
        return {"ok": True}

    def set_recurring(self, key, state):
        with self.lock, self.conn() as c:
            if state in ("yes", "no"):
                c.execute("INSERT OR REPLACE INTO recurring_overrides VALUES (?,?)", (key, state))
            else:
                c.execute("DELETE FROM recurring_overrides WHERE key=?", (key,))
        return {"ok": True}

    def save_settings(self, s):
        clean = {
            "own_ibans": [x.strip().replace(" ", "").upper() for x in s.get("own_ibans", []) if x.strip()],
            "own_names": [x.strip() for x in s.get("own_names", []) if x.strip()],
        }
        with self.lock, self.conn() as c:
            for k, v in clean.items():
                c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (k, json.dumps(v)))
        return {"ok": True}

    def add_category(self, name, kind):
        name = (name or "").strip()
        if not name or kind not in ("expense", "income", "transfer"):
            raise ValueError("Geef een naam en een geldige soort op")
        with self.lock, self.conn() as c:
            n = c.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            c.execute("INSERT OR IGNORE INTO categories VALUES (?,?,?,?)",
                      (name, kind, EXTRA_COLORS[n % len(EXTRA_COLORS)], 100 + n))
        return {"ok": True}


# ---------------------------------------------------------------- HTTP

MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}


LAN_SUFFIXES = (".local", ".lan", ".home", ".home.arpa", ".internal", ".localdomain")


def _is_private_ip(s):
    try:
        ip = ipaddress.ip_address(s)
    except ValueError:
        return False
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return ip.is_private or ip.is_loopback or ip.is_link_local


def _hostname(host_header):
    h = (host_header or "").strip().lower()
    if h.startswith("["):                     # [ipv6]:poort
        return h[1:h.find("]")] if "]" in h else h
    return h.rsplit(":", 1)[0] if h.count(":") == 1 else h


def _cred(text):
    """Inloggegevens als bytes. compare_digest weigert tekst met tekens buiten
    ASCII, waardoor een wachtwoord met bijvoorbeeld é of € nooit zou kloppen.
    Normaliseren voorkomt dat dezelfde letter in twee schrijfwijzen verschilt."""
    return unicodedata.normalize("NFC", text).encode("utf-8")


def make_handler(store, port, lan=False, extra_hosts=(), auth=None):
    """lan=False: alleen bereikbaar op deze computer (127.0.0.1).
    lan=True: ook vanaf het thuisnetwerk. Dan worden alleen verzoeken van
    privé-IP-adressen geaccepteerd, met een Host-header die een privé-IP,
    een lokale naam (.local, .lan, ...) of een expliciet toegestane naam is.
    Dat blokkeert DNS-rebinding en verzoeken van buitenaf.
    auth=(gebruiker, wachtwoord): optionele extra inlog (HTTP Basic)."""
    allowed_hosts = {"127.0.0.1:%d" % port, "localhost:%d" % port}
    extra = {h.strip().lower() for h in extra_hosts if h.strip()}

    def host_ok(header):
        if not lan:
            return header in allowed_hosts
        name = _hostname(header)
        return (name in ("localhost",) or _is_private_ip(name) or name.endswith(LAN_SUFFIXES)
                or name in extra or (header or "").lower() in extra)

    class H(BaseHTTPRequestHandler):
        server_version = "FinApp"

        def log_message(self, fmt, *args):
            pass

        def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:")
            self.end_headers()
            self.wfile.write(body)

        def _guard(self):
            # Bescherming tegen DNS-rebinding en verzoeken vanaf andere websites
            if lan and not _is_private_ip(self.client_address[0]):
                self._send(403, {"error": "Alleen bereikbaar vanaf het thuisnetwerk"})
                return False
            if not host_ok(self.headers.get("Host")):
                self._send(403, {"error": "Ongeldige host"})
                return False
            if auth:
                ok = False
                hdr = self.headers.get("Authorization") or ""
                if hdr.startswith("Basic "):
                    try:
                        user, _, pw = base64.b64decode(hdr[6:]).decode("utf-8").partition(":")
                        ok = (hmac.compare_digest(_cred(user), _cred(auth[0]))
                              & hmac.compare_digest(_cred(pw), _cred(auth[1])))
                    except Exception:
                        ok = False
                if not ok:
                    self._send(401, {"error": "Inloggen vereist"},
                               headers={"WWW-Authenticate": 'Basic realm="FinApp", charset="UTF-8"'})
                    return False
            return True

        def do_GET(self):
            if not self._guard():
                return
            path = urlparse(self.path).path
            if path == "/api/data":
                return self._send(200, store.data())
            if path in ("/", "/index.html"):
                path = "/static/index.html"
            if path.startswith("/static/"):
                f = (STATIC / path[len("/static/"):]).resolve()
                if STATIC in f.parents and f.is_file():
                    return self._send(200, f.read_bytes(), MIME.get(f.suffix, "application/octet-stream"))
            self._send(404, {"error": "Niet gevonden"})

        def do_POST(self):
            if not self._guard():
                return
            if self.headers.get("X-FinApp") != "1":
                return self._send(403, {"error": "Ontbrekende header"})
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            if length > 50 * 1024 * 1024:
                return self._send(413, {"error": "Bestand te groot"})
            raw = self.rfile.read(length)
            try:
                if path == "/api/import":
                    fname = unquote(self.headers.get("X-Filename") or "upload")
                    return self._send(200, store.import_file(fname, raw))
                body = json.loads(raw or b"{}")
                if path == "/api/categorize":
                    return self._send(200, store.categorize(body["uid"], body.get("category"),
                                                            body.get("scope", "tx")))
                if path == "/api/recurring":
                    return self._send(200, store.set_recurring(body["key"], body.get("state")))
                if path == "/api/settings":
                    return self._send(200, store.save_settings(body))
                if path == "/api/categories":
                    return self._send(200, store.add_category(body.get("name"), body.get("kind")))
                if path == "/api/exclude":
                    return self._send(200, store.set_exclude(body["uid"], bool(body.get("exclude"))))
                if path == "/api/vacations":
                    return self._send(200, store.vacation(body))
                if path == "/api/labels":
                    return self._send(200, store.label(body))
                if path == "/api/tx_labels":
                    return self._send(200, store.tx_labels(body))
                if path == "/api/assets":
                    return self._send(200, store.asset(body))
                if path == "/api/mortgage":
                    return self._send(200, store.mortgage_action(body))
                if path == "/api/delete_import":
                    return self._send(200, store.delete_import(int(body["id"])))
                return self._send(404, {"error": "Niet gevonden"})
            except parsers.ImportFout as e:
                return self._send(400, {"error": str(e)})
            except (ValueError, KeyError) as e:
                return self._send(400, {"error": str(e)})
            except Exception as e:  # pragma: no cover
                return self._send(500, {"error": "Interne fout: %s" % e})

    return H


def main():
    ap = argparse.ArgumentParser(description="FinApp, lokaal financieel overzicht")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--db", default=os.environ.get("FINAPP_DB") or str(default_db_path()))
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--host", default=os.environ.get("FINAPP_HOST") or "127.0.0.1",
                    help="0.0.0.0 om ook vanaf het thuisnetwerk bereikbaar te zijn (bijv. op een NAS)")
    a = ap.parse_args()
    lan = a.host not in ("127.0.0.1", "localhost")
    extra_hosts = (os.environ.get("FINAPP_ALLOWED_HOSTS") or "").split(",")
    pw = os.environ.get("FINAPP_PASSWORD") or ""
    auth = ((os.environ.get("FINAPP_USER") or "finapp"), pw) if pw else None

    store = Store(a.db)
    port = int(os.environ.get("FINAPP_PORT") or a.port)
    for attempt in range(1 if lan else 10):
        try:
            srv = ThreadingHTTPServer((a.host, port), make_handler(store, port, lan, extra_hosts, auth))
            break
        except OSError:
            port += 1
    else:
        sys.exit("Poort %d is niet beschikbaar." % port)

    url = "http://%s:%d/" % ("127.0.0.1" if not lan else "<ip-van-dit-apparaat>", port)
    if lan:
        print("Thuisnetwerkmodus: alleen verzoeken van privé-IP-adressen worden geaccepteerd.")
        print("Inlog: %s" % ("aan" if auth else "uit (zet FINAPP_PASSWORD om een wachtwoord te vragen)"))
    print("FinApp draait op %s" % url)
    print("Database: %s" % a.db)
    print("Sluit dit venster of druk op Ctrl+C om te stoppen.")
    if not a.no_browser and not lan:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nGestopt.")


if __name__ == "__main__":
    main()
