"""Telt de transacties per categorie in je eigen database, zonder iets van de inhoud te tonen.

Bedoeld om een wijziging in de categorisering te controleren: tel vóór en na
een update en vergelijk de aantallen.

    python3 tools/telling.py --db /pad/naar/finapp.db --bewaar /tmp/voor.json
    (FinApp bijwerken)
    python3 tools/telling.py --db /pad/naar/finapp.db --vergelijk /tmp/voor.json

Wat het script toont: aantallen per categorie, het aantal transacties dat
door een vakantieperiode naar "Reizen & vakantie" is gegaan en het aantal
plaatsen in het woongebied. Geen namen, bedragen, omschrijvingen of
plaatsnamen. Categorieën die je zelf hebt aangemaakt, staan er genummerd in
("eigen categorie 1"), zodat je de uitvoer kunt delen.

Het script leest een tijdelijke kopie van de database en verwijdert die na
afloop; je database zelf wordt niet gewijzigd. Met --app kies je een andere
versie van de code, bijvoorbeeld een map met de vorige versie.
"""
import argparse
import json
import os
import sqlite3
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))


def count(db, app_dir):
    sys.path.insert(0, app_dir)
    import app
    import rules

    standard = {c[0] for c in rules.CATEGORIES}
    with tempfile.TemporaryDirectory() as tmp:
        copy = os.path.join(tmp, "kopie.db")
        src = sqlite3.connect("file:%s?mode=ro" % os.path.abspath(db), uri=True)
        dst = sqlite3.connect(copy)
        try:
            src.backup(dst)
        finally:
            src.close()
            dst.close()
        data = app.Store(copy).data()

    txs = [t for t in data["transactions"] if not t.get("synthetic")]
    cats = Counter(t["category"] for t in txs)
    own = sorted(c for c in cats if c not in standard)
    alias = {c: "eigen categorie %d" % (i + 1) for i, c in enumerate(own)}
    home = data.get("home")
    return {
        "transacties": len(txs),
        "door een vakantie omgezet": sum(1 for t in txs if str(t.get("reason", "")).startswith("vakantie")),
        "vakantieperiodes": len(data.get("vacations", [])),
        # het woongebied bestaat pas vanaf de versie met de woongebied-editor
        "plaatsen in woongebied (zelf toegevoegd)": len(home["places"]) if home else None,
        "plaatsen in woongebied (geleerd)": sum(1 for p in home["seen"] if p["learned"]) if home else None,
        "per categorie": {alias.get(c, c): n for c, n in sorted(cats.items())},
    }


def show(now, before=None):
    def line(label, a, b):
        if b is None or a == b:
            print("  %-46s %7s" % (label, "-" if a is None else a))
        else:
            diff = "" if a is None or not isinstance(b, int) else "  (%+d)" % (a - b)
            print("  %-46s %7s   was %s%s" % (label, "-" if a is None else a, b, diff))

    old = before or {}
    for key in ("transacties", "door een vakantie omgezet", "vakantieperiodes",
                "plaatsen in woongebied (zelf toegevoegd)", "plaatsen in woongebied (geleerd)"):
        line(key, now[key], old.get(key) if before else None)
    print("\n  Per categorie")
    old_cats = old.get("per categorie", {})
    for c in sorted(set(now["per categorie"]) | set(old_cats)):
        line(c, now["per categorie"].get(c, 0), old_cats.get(c, 0) if before else None)
    if before:
        changed = sum(1 for c in set(now["per categorie"]) | set(old_cats)
                      if now["per categorie"].get(c, 0) != old_cats.get(c, 0))
        print("\n  %d categorie%s met een ander aantal dan in de bewaarde telling."
              % (changed, "" if changed == 1 else "ën"))


def main():
    ap = argparse.ArgumentParser(description="Tel transacties per categorie, zonder inhoud te tonen")
    ap.add_argument("--db", required=True, help="pad naar de database")
    ap.add_argument("--app", default=os.path.join(HERE, "..", "app"), help="map met de code (standaard: deze versie)")
    ap.add_argument("--bewaar", help="de telling opslaan in dit bestand (alleen aantallen)")
    ap.add_argument("--vergelijk", help="vergelijken met een eerder bewaarde telling")
    a = ap.parse_args()
    if not os.path.isfile(a.db):
        sys.exit("Database niet gevonden: %s" % a.db)
    now = count(a.db, os.path.abspath(a.app))
    before = None
    if a.vergelijk:
        with open(a.vergelijk, encoding="utf-8") as f:
            before = json.load(f)
    show(now, before)
    if a.bewaar:
        with open(a.bewaar, "w", encoding="utf-8") as f:
            json.dump(now, f, ensure_ascii=False, indent=1)
        print("\n  Telling bewaard in %s" % a.bewaar)


if __name__ == "__main__":
    main()
