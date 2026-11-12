"""Parsers voor bankexports.

Ondersteund:
- Van Lanschot (en andere banken) CAMT.053 XML
- American Express NL activity.csv

Elke parser levert een lijst dicts met vaste velden (zie _tx()).
Bedragen zijn in centen (int), negatief = uitgaand.
"""
import csv
import hashlib
import io
import re
import xml.etree.ElementTree as ET
from datetime import datetime


class ImportFout(Exception):
    pass


def _tx(**kw):
    base = {
        "uid": None,            # unieke sleutel voor deduplicatie
        "source": None,         # 'bank' of 'amex'
        "account": None,        # IBAN of Amex-rekeningnummer
        "date": None,           # ISO datum (YYYY-MM-DD)
        "amount": 0,            # centen, negatief = uitgaand
        "counterparty": "",     # naam tegenpartij / winkel
        "counterparty_iban": "",
        "description": "",      # omschrijving / remittance
        "tx_type": "",          # pin, incasso, overboeking, ideal, creditcard, ...
        "creditor_id": "",
        "mandate_id": "",
        "cardholder": "",
        "foreign": "",
        "merchant_key": "",     # genormaliseerde sleutel voor groeperen
        "country": "",          # land (alleen bekend bij Amex)
    }
    base.update(kw)
    return base


def _hash(*parts):
    h = hashlib.sha1("\x1f".join(str(p) for p in parts).encode("utf-8"))
    return h.hexdigest()[:20]


# ---------------------------------------------------------------- normalisatie

_SPLIT2 = re.compile(r"\s{2,}")


def normalize_name(s):
    """Maak een stabiele winkelsleutel: hoofdletters, zonder filiaal- en
    referentienummers ('Albert Heijn 1184' -> 'ALBERT HEIJN',
    'AMZNPRIMENL*3Q8411ZZ5' -> 'AMZNPRIMENL')."""
    if not s:
        return ""
    s = s.upper().replace("*", " ").replace("=", " ")
    out = []
    for tok in s.split():
        tok = tok.strip(".,;:-/#()")
        if not tok:
            continue
        digits = sum(c.isdigit() for c in tok)
        if digits >= 2 or tok.isdigit():
            continue
        out.append(tok)
    return " ".join(out)


def card_merchant(name, rmt):
    """Bij kaartbetalingen zet de bank soms de plaats in het naamveld
    ('GRONINGEN' in plaats van 'KRUIDVAT 6318'). Geeft dan de echte
    winkelnaam uit de omschrijving terug, anders None."""
    if not rmt or not re.search(r"[BG]EA Nr", rmt):
        return None
    chunks = [c.strip() for c in _SPLIT2.split(re.split(r"[BG]EA Nr", rmt)[0].strip()) if c.strip()]
    if len(chunks) < 2:
        return None
    first, city = chunks[0], chunks[1]
    nn = normalize_name(name)
    if nn and nn == normalize_name(city) and normalize_name(first) and normalize_name(first) != nn:
        return first
    return None


def _looks_like_code(name):
    """OVpay e.d. gebruiken een willekeurige code als naam."""
    return bool(re.fullmatch(r"[A-Z0-9]{12,}", (name or "").replace(" ", ""))) and \
        sum(c.isdigit() for c in name) >= 3


# ---------------------------------------------------------------- CAMT.053

# Van Lanschot eigen transactiecodes (BkTxCd/Prtry/Cd), afgeleid uit exports
_VL_CODES = {
    "10": "incasso",
    "4": "ideal",
    "44": "overboeking",
    "101": "pin",
    "111": "pin",
    "120": "pin",
    "121": "online kaart",
    "420": "overboeking",
    "501": "overboeking",
    "540": "overboeking",
    "600": "terugboeking kaart",
}

_DD_RE = re.compile(r"DD:\s*(\d{4}-\d{2}-\d{2})")


def parse_camt053(data):
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise ImportFout("XML kon niet worden gelezen: %s" % e)

    m = re.match(r"\{(.*)\}", root.tag)
    ns = {"c": m.group(1)} if m else {"c": ""}
    if "camt.053" not in ns["c"]:
        raise ImportFout("Dit XML-bestand is geen CAMT.053-afschrift.")

    def t(el, path):
        if el is None:
            return ""
        x = el.find(path, ns)
        return (x.text or "").strip() if x is not None and x.text else ""

    txs = []
    seen = {}
    for stmt in root.iter("{%s}Stmt" % ns["c"]):
        iban = t(stmt, "c:Acct/c:Id/c:IBAN")
        for ntry in stmt.findall("c:Ntry", ns):
            if t(ntry, "c:Sts") not in ("", "BOOK"):
                continue
            amt = t(ntry, "c:Amt")
            cents = int(round(float(amt) * 100))
            sign = t(ntry, "c:CdtDbtInd")
            if sign == "DBIT":
                cents = -cents
            if t(ntry, "c:RvslInd") == "true":
                cents = -cents
            bookdate = t(ntry, "c:BookgDt/c:Dt") or t(ntry, "c:ValDt/c:Dt")
            code = t(ntry, "c:BkTxCd/c:Prtry/c:Cd") or t(ntry, "c:BkTxCd/c:Domn/c:Fmly/c:SubFmlyCd")

            det = ntry.find("c:NtryDtls/c:TxDtls", ns)
            e2e = t(det, "c:Refs/c:EndToEndId")
            mndt = t(det, "c:Refs/c:MndtId")
            if cents < 0:
                name = t(det, "c:RltdPties/c:Cdtr/c:Nm")
                cp_iban = t(det, "c:RltdPties/c:CdtrAcct/c:Id/c:IBAN")
                cid = t(det, "c:RltdPties/c:Cdtr/c:Id/c:PrvtId/c:Othr/c:Id") or \
                    t(det, "c:RltdPties/c:Cdtr/c:Id/c:OrgId/c:Othr/c:Id")
            else:
                name = t(det, "c:RltdPties/c:Dbtr/c:Nm") or t(det, "c:RltdPties/c:Cdtr/c:Nm")
                cp_iban = t(det, "c:RltdPties/c:DbtrAcct/c:Id/c:IBAN")
                cid = ""
            rmt = t(det, "c:RmtInf/c:Ustrd") or t(ntry, "c:AddtlNtryInf")

            # Werkelijke transactiedatum bij pinbetalingen
            dd = _DD_RE.search(rmt)
            date = dd.group(1) if dd else bookdate

            tx_type = _VL_CODES.get(code, "")
            if not tx_type:
                if mndt:
                    tx_type = "incasso"
                elif "BEA Nr" in rmt:
                    tx_type = "pin"
                else:
                    tx_type = "overboeking"

            # Winkelsleutel
            if mndt and cid:
                key = "INC|%s|%s" % (cid, mndt)
                display = name
            else:
                nm = card_merchant(name, rmt) or name
                if _looks_like_code(nm) or not normalize_name(nm):
                    # val terug op de omschrijving (bijv. 'www.ovpay.nl')
                    for chunk in _SPLIT2.split(rmt.split("BEA Nr")[0]):
                        if normalize_name(chunk) and not _looks_like_code(chunk):
                            nm = chunk
                            break
                display = nm.strip()
                key = normalize_name(nm) or (cp_iban or "ONBEKEND")

            base = (iban, bookdate, cents, name, rmt, e2e)
            k = _hash(*base)
            seen[k] = seen.get(k, 0) + 1
            uid = "bank:" + (k if seen[k] == 1 else _hash(k, seen[k]))

            txs.append(_tx(
                uid=uid, source="bank", account=iban, date=date, amount=cents,
                counterparty=display, counterparty_iban=cp_iban, description=rmt,
                tx_type=tx_type, creditor_id=cid, mandate_id=mndt, merchant_key=key,
            ))
    if not txs:
        raise ImportFout("Geen geboekte transacties gevonden in dit afschrift.")
    return txs


# ---------------------------------------------------------------- Amex CSV

def _nl_amount(s):
    s = (s or "").strip().replace("€", "").replace(" ", "")
    if not s:
        return 0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return int(round(float(s) * 100))


def _split_amex_desc(desc):
    """Amex zet de winkelnaam in een vaste breedte van 23 tekens, gevolgd
    door de plaats."""
    d = desc.rstrip()
    if len(d) > 24 and d[23] == " ":
        return d[:23].strip(), d[24:].strip()
    parts = _SPLIT2.split(d, maxsplit=1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")


def parse_amex_csv(data):
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    fields = [f.strip() for f in (reader.fieldnames or [])]
    reader.fieldnames = fields
    need = {"Datum", "Omschrijving", "Bedrag"}
    if not need.issubset(fields):
        raise ImportFout("Onbekend CSV-formaat; verwacht een American Express-export "
                         "met de kolommen Datum, Omschrijving en Bedrag.")
    txs = []
    seen = {}
    for row in reader:
        if not row.get("Datum"):
            continue
        try:
            date = datetime.strptime(row["Datum"].strip(), "%m/%d/%Y").date().isoformat()
        except ValueError:
            date = datetime.strptime(row["Datum"].strip(), "%d-%m-%Y").date().isoformat()
        # Amex: positief = uitgave, negatief = betaling/creditering
        cents = -_nl_amount(row.get("Bedrag"))
        desc = (row.get("Omschrijving") or "").strip()
        merchant, city = _split_amex_desc(desc)
        ref = (row.get("Referentie") or "").strip().strip("'\"")
        extra = (row.get("Aanvullende informatie") or "").strip()
        foreign = ""
        fm = re.search(r"Foreign Spend Amount:\s*([\d.,]+)\s+([A-Za-z ]+?)\s+Commission", extra)
        if fm:
            foreign = "%s %s" % (fm.group(1), fm.group(2).strip())
        if ref:
            uid = "amex:" + ref
        else:
            k = _hash(date, cents, desc, row.get("Kaartlid"))
            seen[k] = seen.get(k, 0) + 1
            uid = "amex:" + (k if seen[k] == 1 else _hash(k, seen[k]))
        txs.append(_tx(
            uid=uid, source="amex", account=(row.get("Rekening #") or "").strip(),
            date=date, amount=cents, counterparty=(normalize_name(merchant) or merchant).title(),
            description=desc,
            tx_type="creditcard", cardholder=(row.get("Kaartlid") or "").strip().title(),
            foreign=foreign, merchant_key=normalize_name(merchant) or "ONBEKEND",
            country=(row.get("Land") or "").strip().upper(),
        ))
    if not txs:
        raise ImportFout("Geen transacties gevonden in dit CSV-bestand.")
    return txs


def camt_balances(data):
    """Openings- en eindsaldi (OPBD/CLBD) uit een CAMT.053-afschrift."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    m = re.match(r"\{(.*)\}", root.tag)
    ns = {"c": m.group(1)} if m else {"c": ""}
    out = []
    for stmt in root.iter("{%s}Stmt" % ns["c"]):
        acct = stmt.find("c:Acct/c:Id/c:IBAN", ns)
        iban = (acct.text or "").strip() if acct is not None else ""
        for bal in stmt.findall("c:Bal", ns):
            code = bal.find("c:Tp/c:CdOrPrtry/c:Cd", ns)
            amt = bal.find("c:Amt", ns)
            sign = bal.find("c:CdtDbtInd", ns)
            dt = bal.find("c:Dt/c:Dt", ns)
            if code is None or amt is None or dt is None:
                continue
            cents = int(round(float(amt.text) * 100))
            if sign is not None and sign.text == "DBIT":
                cents = -cents
            out.append({"account": iban, "date": dt.text.strip(), "kind": code.text.strip(), "amount": cents})
    return out


def detect_and_parse(filename, data):
    name = (filename or "").lower()
    head = data[:600].lstrip()
    if name.endswith(".xml") or head.startswith(b"<?xml") or b"camt.053" in head:
        return parse_camt053(data)
    if name.endswith(".csv") or b"Omschrijving" in head:
        return parse_amex_csv(data)
    raise ImportFout("Bestandstype niet herkend. Gebruik een CAMT.053 (.xml) van de bank "
                     "of een American Express .csv-export.")
