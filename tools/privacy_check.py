"""Controleert dat er geen persoonlijke gegevens in de repository staan.

Faalt als een door git gevolgd bestand:
- een database, bankexport of .env is (.db, .sqlite, .xml, .csv, alles in data/);
- een geldige IBAN bevat. Verzonnen IBAN's met een ongeldig controlegetal,
  zoals NL00DEMO0000000001, zijn toegestaan.

Namen van personen of werkgevers zijn niet automatisch te herkennen; die
blijf je zelf nalopen. De gevonden IBAN wordt niet getoond, alleen de plek.

Gebruik:
    python3 tools/privacy_check.py
"""
import os
import re
import subprocess
import sys

FORBIDDEN_SUFFIXES = (".db", ".db-journal", ".sqlite", ".sqlite3", ".xml", ".csv")
FORBIDDEN_NAMES = (".env",)
ALLOWED_IN_DATA = ("data/.gitkeep",)

# Landcode, controlegetal en 11 tot 30 tekens, aaneen of in groepjes van vier
IBAN_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?(?![A-Za-z0-9])")


def valid_iban(s):
    """True als het controlegetal klopt (mod 97), dus mogelijk een echte IBAN."""
    s = s.replace(" ", "")
    if not 15 <= len(s) <= 34:
        return False
    digits = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    return int(digits) % 97 == 1


def tracked_files(root):
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True, stdout=subprocess.PIPE).stdout
    return [f for f in out.decode("utf-8").split("\0") if f]


def check(root):
    problems = []
    for name in tracked_files(root):
        base = os.path.basename(name)
        if name.startswith("data/") and name not in ALLOWED_IN_DATA:
            problems.append("%s: bestanden in data/ horen niet in de repository" % name)
            continue
        if base.lower().endswith(FORBIDDEN_SUFFIXES) or base in FORBIDDEN_NAMES:
            problems.append("%s: databases, bankexports en .env horen niet in de repository" % name)
            continue
        try:
            with open(os.path.join(root, name), encoding="utf-8") as f:
                lines = f.read().splitlines()
        except (UnicodeDecodeError, OSError):
            continue    # binair of verdwenen bestand
        for n, line in enumerate(lines, 1):
            for m in IBAN_RE.finditer(line):
                if valid_iban(m.group(0)):
                    problems.append("%s:%d: geldige IBAN (%s…); gebruik een verzonnen IBAN die met NL00 begint"
                                    % (name, n, m.group(0)[:4]))
    return problems


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    problems = check(root)
    for p in problems:
        print(p)
    if problems:
        print("\n%d probleem/problemen gevonden. Zie 'De belangrijkste regel' in CONTRIBUTING.md."
              % len(problems))
        return 1
    print("Geen persoonlijke gegevens gevonden in de gevolgde bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
