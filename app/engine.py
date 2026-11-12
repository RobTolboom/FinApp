"""Categorisering en herkenning van vaste lasten."""
import re
import statistics
from collections import defaultdict
from datetime import date

import rules as default_rules
from parsers import _SPLIT2, _split_amex_desc

# Bekende Nederlandse plaatsen: een pinbetaling hier telt nooit als vakantie,
# ook als die plaats zelden in je transacties voorkomt. Daarnaast geldt elke
# plaats die buiten je vakanties in minstens 3 verschillende maanden voorkomt
# als 'thuis' (zie Categorizer.prepare).
NL_CITIES = {
    "AMSTERDAM", "ROTTERDAM", "DEN HAAG", "S-GRAVENHAGE", "UTRECHT", "EINDHOVEN", "GRONINGEN",
    "TILBURG", "ALMERE", "BREDA", "NIJMEGEN", "NYMEGEN", "APELDOORN", "ARNHEM", "HAARLEM",
    "HAARLEMMERMEER", "ENSCHEDE", "AMERSFOORT", "ZAANSTAD", "S-HERTOGENBOSCH", "S-HERTOGENBO",
    "DEN BOSCH", "ZWOLLE", "LEIDEN", "LEEUWARDEN", "MAASTRICHT", "DORDRECHT", "EDE", "ALKMAAR",
    "EMMEN", "DELFT", "VENLO", "DEVENTER", "HELMOND", "OSS", "HILVERSUM", "ASSEN", "HOOGEZAND",
    "DRACHTEN", "HEERENVEEN", "SNEEK", "MEPPEL", "HOOGEVEEN", "WINSCHOTEN", "VEENDAM", "STADSKANAAL",
    "DELFZIJL", "APPINGEDAM", "HAREN", "ZUIDLAREN", "ROLDE", "BEILEN", "ELST", "WIJCHEN", "MALDEN",
    "LENT", "DUIVEN", "WESTERVOORT", "ZUTPHEN", "SCHIPHOL", "UDEN", "VEGHEL", "SCHIJNDEL", "SCHYNDEL",
    "WAGENINGEN", "VALKENBURG", "BAD NIEUWESCH", "TEXEL", "DE COCKSDORP", "SCHIERMONNIKO",
    "ZEVENHUIZEN G", "ADUARD", "EIBERGEN", "BARENDRECHT", "ZUIDWOLDE GN", "VEENINGEN", "HOUTEN",
}


def _city(tx):
    """Plaats uit de omschrijving van een kaartbetaling (hoofdletters)."""
    desc = tx.get("description") or ""
    if tx.get("source") == "amex":
        return _split_amex_desc(desc)[1].upper()
    head = re.split(r"[BG]EA Nr", desc)[0].strip()
    parts = _SPLIT2.split(head)
    return parts[1].strip().upper() if len(parts) >= 2 else ""

# (dagen, label, ondergrens, bovengrens)
PERIODS = [
    (7.0,    "Wekelijks",       5,   9),
    (14.0,   "Tweewekelijks",   12,  17),
    (30.44,  "Maandelijks",     25,  36),
    (61.0,   "Tweemaandelijks", 54,  68),
    (91.3,   "Per kwartaal",    80,  101),
    (182.6,  "Halfjaarlijks",   160, 205),
    (365.25, "Jaarlijks",       330, 400),
]
PERIOD_BY_LABEL = {p[1]: p for p in PERIODS}


def _d(s):
    return date.fromisoformat(s)


# ---------------------------------------------------------------- categorieën

class Categorizer:
    def __init__(self, categories, tx_overrides, merchant_rules, own_ibans, own_names, vacations=()):
        self.kind = {c["name"]: c["kind"] for c in categories}
        self.tx_overrides = tx_overrides
        self.merchant_rules = merchant_rules
        self.own_ibans = {i.replace(" ", "").upper() for i in own_ibans if i.strip()}
        self.own_names = [n.strip().upper() for n in own_names if n.strip()]
        self.rules = [(re.compile(p, re.I), cat, opt) for p, cat, opt in default_rules.RULES]
        self.vacations = [(v["start"], v["end"], v["name"]) for v in vacations]
        self.travel_cat = "Reizen & vakantie" if "Reizen & vakantie" in self.kind else None
        self.home_cities = set(NL_CITIES)

    def _in_vacation(self, d):
        for start, end, name in self.vacations:
            if start <= d <= end:
                return name
        return None

    def prepare(self, txs):
        """Leer welke plaatsen 'thuis' zijn: kaartbetalingen buiten vakanties
        in minstens 3 verschillende maanden."""
        months = defaultdict(set)
        for t in txs:
            if t["source"] == "bank" and t["tx_type"] != "pin":
                continue
            if self._in_vacation(t["date"]):
                continue
            c = _city(t)
            if c:
                months[c].add(t["date"][:7])
        self.home_cities |= {c for c, m in months.items() if len(m) >= 3}

    # Categorieën die tijdens een vakantie naar 'Reizen & vakantie' gaan
    # (vaste lasten, abonnementen en overboekingen blijven onaangetast).
    VACATION_CATS = {"Overig", "Horeca & uit eten", "Boodschappen", "Cultuur & uitjes",
                     "Openbaar vervoer", "Auto, laden & parkeren",
                     "Persoonlijke verzorging", "Contant geld", "Sport & wellness"}
    # Webwinkels en online diensten zijn geen uitgaven ter plaatse
    ONLINE = re.compile(r"\.COM\b|\.NL\b|\.IO\b|WWW\.|APPLE\.|AMAZON|PAYPAL", re.I)

    def _vacation(self, tx):
        """Naam van de vakantie als dit een betaling ter plaatse is, anders None."""
        if not self.vacations or not self.travel_cat:
            return None
        name = self._in_vacation(tx["date"])
        if not name:
            return None
        if tx["source"] == "bank":
            if not (tx["tx_type"] == "pin" or "GEA Nr" in (tx["description"] or "")):
                return None
        elif (tx.get("country") or "").upper().startswith("NETHERLANDS"):
            return None
        if self.ONLINE.search(tx["description"] or ""):
            return None
        city = _city(tx)
        if not city or city in self.home_cities:
            return None
        return name

    def categorize(self, tx):
        cat, why = self._categorize(tx)
        if why in ("standaardregel", "geen regel", "terugbetaling") and cat in self.VACATION_CATS:
            v = self._vacation(tx)
            if v:
                return self.travel_cat, "vakantie: " + v
        return cat, why

    def _categorize(self, tx):
        """Geeft (categorie, reden) terug."""
        if tx["uid"] in self.tx_overrides:
            return self.tx_overrides[tx["uid"]], "handmatig"
        if tx["merchant_key"] in self.merchant_rules:
            return self.merchant_rules[tx["merchant_key"]], "eigen regel"

        if tx["source"] == "bank" and tx["tx_type"] in ("overboeking", "ideal", ""):
            ib = (tx["counterparty_iban"] or "").upper()
            nm = (tx["counterparty"] or "").upper()
            if ib and ib in self.own_ibans:
                return "Interne overboeking", "eigen rekening"
            if any(n and n in nm for n in self.own_names):
                return "Interne overboeking", "eigen naam"

        hay = "%s %s" % (tx["counterparty"], tx["description"])
        sign = "in" if tx["amount"] > 0 else "out"
        for rx, cat, opt in self.rules:
            if opt.get("source") and opt["source"] != tx["source"]:
                continue
            if opt.get("sign") and opt["sign"] != sign:
                continue
            if rx.search(hay):
                return cat, "standaardregel"

        if tx["amount"] > 0:
            if tx["source"] == "amex" or tx["tx_type"] == "terugboeking kaart":
                return "Overig", "terugbetaling"
            return "Overige inkomsten", "geen regel"
        if tx["source"] == "bank" and tx["tx_type"] == "overboeking":
            if re.search(r"FACTUUR|INVOICE|ORDER|BESTELLING|KLANTNR|KLANTNUMMER|\bB\.?V\.?\b|GMBH|\bN\.?V\.?\b",
                         "%s %s" % (tx["counterparty"], tx["description"]), re.I):
                return "Overig", "geen regel"
            return "Betalingen aan personen", "geen regel"
        return "Overig", "geen regel"


# ---------------------------------------------------------------- vaste lasten

def _classify_interval(m):
    for p in PERIODS:
        if p[2] <= m <= p[3]:
            return p
    return None


def _cv(vals):
    if len(vals) < 2:
        return 0.0
    mu = statistics.mean(vals)
    return statistics.pstdev(vals) / mu if mu else 1.0


def _detect(txs, is_incasso=False, forced=False):
    """txs: gesorteerd op datum, alleen uitgaven. Geeft periode-tuple of None."""
    n = len(txs)
    if n < 2:
        return PERIOD_BY_LABEL["Maandelijks"] if forced else None
    dates = [_d(t["date"]) for t in txs]
    iv = [(b - a).days for a, b in zip(dates, dates[1:])]
    iv_nz = [d for d in iv if d > 0]
    if not iv_nz:
        return PERIOD_BY_LABEL["Maandelijks"] if forced else None
    m = statistics.median(iv_nz)
    p = _classify_interval(m)
    if forced:
        return p or min(PERIODS, key=lambda x: abs(x[0] - m))
    if not p:
        return None
    days, label, lo, hi = p
    if days <= 101 and n < 3:
        return None
    # regelmaat: interval binnen bandbreedte, of een veelvoud (overgeslagen termijn)
    iv = iv_nz
    exact = sum(1 for d in iv if lo <= d <= hi)
    ok = 0
    for d in iv:
        k = max(1, round(d / days))
        if k <= 3 and lo * k <= d <= hi * k:
            ok += 1
    if ok / len(iv) < 0.75 or exact / len(iv) < 0.5:
        return None
    amounts = [-t["amount"] for t in txs[-6:]]
    if _cv(amounts) > (0.6 if is_incasso else 0.35):
        return None
    if days > 101:
        # Halfjaar- en jaarlasten: twee toevallige winkelaankopen met een jaar
        # ertussen zijn geen vaste last. Eis een vrijwel gelijk bedrag, en bij
        # pinbetalingen minstens drie keer.
        if _cv(amounts) > 0.15:
            return None
        card = any(t.get("tx_type") in ("pin", "online kaart") for t in txs)
        if card and n < 3:
            return None
    return p


def _amount_clusters(txs):
    """Splits een groep op bedrag (bijv. meerdere Apple-abonnementen)."""
    srt = sorted(txs, key=lambda t: -t["amount"])
    clusters = []
    for t in srt:
        a = -t["amount"]
        for c in clusters:
            ref = c["ref"]
            if abs(a - ref) <= max(50, ref * 0.04):
                c["txs"].append(t)
                break
        else:
            clusters.append({"ref": a, "txs": [t]})
    return clusters


def find_recurring(txs, cat_of, kind_of, overrides, end_date):
    """
    txs: alle transacties
    cat_of: uid -> categorie
    kind_of: categorie -> soort
    overrides: key -> 'yes' | 'no'
    Retourneert (lijst vaste lasten, dict uid -> groepsleutel)
    """
    by_key = defaultdict(list)
    for t in txs:
        if t["amount"] >= 0:
            continue
        if kind_of.get(cat_of[t["uid"]]) != "expense":
            continue
        by_key[t["merchant_key"]].append(t)

    end = _d(end_date) if end_date else date.today()
    results, member = [], {}

    def add(key, group, period, manual):
        group = sorted(group, key=lambda t: t["date"])
        days, label = period[0], period[1]
        recent = [-t["amount"] for t in group[-3:]]
        amount = int(statistics.median(recent))
        last = group[-1]
        age = (end - _d(last["date"])).days
        active = age <= days * 1.5 + 10
        cats = defaultdict(int)
        for t in group:
            cats[cat_of[t["uid"]]] += 1
        cat = max(cats, key=cats.get)
        results.append({
            "key": key,
            "name": last["counterparty"] or key,
            "category": cat,
            "period": label,
            "period_days": days,
            "amount": amount,
            "monthly": int(round(amount * 30.44 / days)),
            "yearly": int(round(amount * 365.25 / days)),
            "count": len(group),
            "first": group[0]["date"],
            "last": last["date"],
            "active": active,
            "source": last["source"],
            "cardholder": last.get("cardholder", ""),
            "manual": manual,
            "uids": [t["uid"] for t in group],
        })
        for t in group:
            member[t["uid"]] = key

    for key, group in by_key.items():
        group.sort(key=lambda t: t["date"])
        ov = overrides.get(key)
        if ov == "no":
            continue
        is_inc = key.startswith("INC|")
        p = _detect(group, is_inc, forced=(ov == "yes"))
        if p:
            add(key, group, p, ov == "yes")
            continue
        clusters = _amount_clusters(group)
        if len(clusters) < 2:
            continue
        for c in clusters:
            sub = sorted(c["txs"], key=lambda t: t["date"])
            skey = "%s|%.2f" % (key, c["ref"] / 100.0)
            sov = overrides.get(skey)
            if sov == "no":
                continue
            p = _detect(sub, is_inc, forced=(sov == "yes"))
            if p:
                add(skey, sub, p, sov == "yes")

    results.sort(key=lambda r: (not r["active"], r["category"], -r["monthly"]))
    return results, member
