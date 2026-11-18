"""Categorisering en herkenning van vaste lasten."""
import re
import statistics
from collections import defaultdict
from datetime import date

import rules as default_rules
from parsers import _SPLIT2, _split_amex_desc

HOME_MONTHS = 3     # zo veel verschillende maanden met een betaling maakt een plaats 'thuis'
TRUNCATED_MIN = 8   # een afgekapte plaatsnaam telt pas vanaf deze lengte


def normalize_place(name):
    """Plaatsnaam zoals de bank hem schrijft: hoofdletters, geen apostrofs,
    enkele spaties ('s-Gravenhage wordt S-GRAVENHAGE)."""
    s = re.sub(r"['\u2018\u2019`\u00b4]", "", str(name or ""))
    return " ".join(s.upper().split())


def place_matches(city, places):
    """Hoort de plaats uit een transactie bij een van de opgegeven plaatsen?
    Naast een exacte naam telt een afgekapte naam (S-HERTOGENBO) en een naam
    met een toevoeging na een spatie (zoals een provinciecode)."""
    if not city:
        return False
    if city in places:
        return True
    for p in places:
        if len(city) >= TRUNCATED_MIN and p.startswith(city):
            return True
        if city.startswith(p + " "):
            return True
    return False


def _city(tx):
    """Plaats uit de omschrijving van een kaartbetaling (hoofdletters)."""
    desc = tx.get("description") or ""
    if tx.get("source") == "amex":
        return _split_amex_desc(desc)[1].upper()
    head = re.split(r"[BG]EA Nr", desc)[0].strip()
    parts = _SPLIT2.split(head)
    return parts[1].strip().upper() if len(parts) >= 2 else ""


# (dagen, label, ondergrens, bovengrens, keer per jaar)
# De dagen dienen om de frequentie te herkennen. Het jaarbedrag volgt uit het
# aantal keer per jaar, zodat twaalf maandtermijnen precies een jaar zijn.
PERIODS = [
    (7.0,    "Wekelijks",       5,   9,   365.25 / 7),
    (14.0,   "Tweewekelijks",   12,  17,  365.25 / 14),
    (30.44,  "Maandelijks",     25,  36,  12),
    (61.0,   "Tweemaandelijks", 54,  68,  6),
    (91.3,   "Per kwartaal",    80,  101, 4),
    (182.6,  "Halfjaarlijks",   160, 205, 2),
    (365.25, "Jaarlijks",       330, 400, 1),
]
PERIOD_BY_LABEL = {p[1]: p for p in PERIODS}


def _d(s):
    return date.fromisoformat(s)


# ---------------------------------------------------------------- categorieën

class Categorizer:
    def __init__(self, categories, tx_overrides, merchant_rules, own_ibans, own_names, vacations=(),
                 home_places=(), never_learn=(), home_learn=True):
        self.kind = {c["name"]: c["kind"] for c in categories}
        self.tx_overrides = tx_overrides
        self.merchant_rules = merchant_rules
        self.own_ibans = {i.replace(" ", "").upper() for i in own_ibans if i.strip()}
        self.own_names = [n.strip().upper() for n in own_names if n.strip()]
        self.rules = [(re.compile(p, re.I), cat, opt) for p, cat, opt in default_rules.RULES]
        self.vacations = [(v["start"], v["end"], v["name"]) for v in vacations]
        self.travel_cat = "Reizen & vakantie" if "Reizen & vakantie" in self.kind else None
        # woongebied: zelf toegevoegde plaatsen, aangevuld met wat prepare() leert
        self.own_places = {normalize_place(p) for p in home_places} - {""}
        self.never_learn = {normalize_place(p) for p in never_learn} - {""}
        self.home_learn = bool(home_learn)
        self.place_months = {}          # plaats -> aantal maanden met een betaling buiten vakanties
        self.learned_places = set()
        self.home_cities = set(self.own_places)

    def _in_vacation(self, d):
        for start, end, name in self.vacations:
            if start <= d <= end:
                return name
        return None

    def prepare(self, txs):
        """Leer welke plaatsen 'thuis' zijn: betalingen ter plaatse buiten
        vakanties in minstens HOME_MONTHS verschillende maanden. Online
        betalingen en Amex-betalingen in het buitenland tellen niet mee;
        anders wordt de vestigingsplaats van een abonnement 'thuis'."""
        months = defaultdict(set)
        for t in txs:
            if t["source"] == "bank":
                if t["tx_type"] != "pin":
                    continue
            else:
                country = (t.get("country") or "").strip().upper()
                if country and not country.startswith("NETHERLANDS"):
                    continue
            if self.ONLINE.search(t["description"] or ""):
                continue
            if self._in_vacation(t["date"]):
                continue
            c = normalize_place(_city(t))
            if c:
                months[c].add(t["date"][:7])
        self.place_months = {c: len(m) for c, m in months.items()}
        self.learned_places = set()
        if self.home_learn:
            self.learned_places = {c for c, n in self.place_months.items()
                                   if n >= HOME_MONTHS and not place_matches(c, self.never_learn)}
        self.home_cities = self.own_places | self.learned_places

    def is_home(self, city):
        return place_matches(normalize_place(city), self.home_cities)

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
        if not city or self.is_home(city):
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
    days, label, lo, hi = p[:4]
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


def find_recurring(txs, cat_of, kind_of, overrides, end_date, closed=()):
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
    # Laatste boekdatum per bron en rekening. Een rekening die achterloopt, zoals
    # een creditcard die later wordt geïmporteerd, mag een last niet als gestopt
    # laten tellen. Voor een afgesloten rekening telt de algemene einddatum, zodat
    # de lasten daarop vanzelf als gestopt gelden.
    closed = set(closed)
    last_seen = {}
    for t in txs:
        k = (t.get("source"), t.get("account") or "")
        if t["date"] > last_seen.get(k, ""):
            last_seen[k] = t["date"]

    def end_for(t):
        k = (t.get("source"), t.get("account") or "")
        return end if k in closed or k not in last_seen else _d(last_seen[k])

    results, member = [], {}

    def add(key, group, period, manual):
        group = sorted(group, key=lambda t: t["date"])
        days, label = period[0], period[1]
        recent = [-t["amount"] for t in group[-3:]]
        amount = int(statistics.median(recent))
        last = group[-1]
        age = (end_for(last) - _d(last["date"])).days
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
            "monthly": int(round(amount * period[4] / 12)),
            "yearly": int(round(amount * period[4])),
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
