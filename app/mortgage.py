"""Hypotheekberekening per leningdeel.

Een leningdeel heeft een hoofdsom, rente (% per jaar), looptijd in maanden,
ingangsdatum en aflosvorm (annuitair, lineair of aflossingsvrij).
Renteherzieningen gelden vanaf de maand van hun datum. Een correctie zet de
restschuld op een bekende waarde (bijvoorbeeld uit het jaaroverzicht van de
bank of na een extra aflossing); vanaf daar wordt verder gerekend. Een
correctie in of vóór de maand van de ingangsdatum is de beginstand.

Bedragen in centen. Maand = 'YYYY-MM'. De eerste termijn valt in de maand
na de ingangsdatum.
"""


def _add(key, n):
    y, m = int(key[:4]), int(key[5:7]) + n
    while m > 12:
        y, m = y + 1, m - 12
    while m < 1:
        y, m = y - 1, m + 12
    return "%04d-%02d" % (y, m)


def opening_balance(part, corrections=()):
    """Restschuld bij de ingangsdatum: de hoofdsom, of de laatste correctie
    in of vóór de startmaand."""
    start = part["start"][:7]
    early = [c for c in sorted(corrections, key=lambda c: c["date"]) if c["date"][:7] <= start]
    return int(early[-1]["balance"]) if early else int(part["principal"])


def schedule(part, rates=(), corrections=()):
    """Geeft een lijst maanden met dict(month, interest, repayment, extra,
    balance). 'extra' is wat een correctie in die maand extra van de
    restschuld afhaalt (negatief als de correctie de restschuld verhoogt)."""
    start = part["start"][:7]
    term = int(part["term_months"])
    kind = part["kind"]
    bal = float(opening_balance(part, corrections))
    lin_step = bal / term if term else 0.0
    rate = float(part["rate"])
    rate_by_month = sorted(((r["date"][:7], float(r["rate"])) for r in rates))
    corr_by_month = {}
    for c in sorted(corrections, key=lambda c: c["date"]):
        if c["date"][:7] > start:
            corr_by_month[c["date"][:7]] = float(c["balance"])
    last_corr = max(corr_by_month) if corr_by_month else ""
    out = []
    for n in range(1, term + 1):
        mk = _add(start, n)
        for d, r in rate_by_month:
            if d <= mk:
                rate = r
        i = rate / 100.0 / 12.0
        remaining = term - n + 1
        interest = bal * i
        if kind == "aflossingsvrij" or bal <= 0:
            repay = 0.0
        elif kind == "lineair":
            repay = min(bal, lin_step)
        else:  # annuitair
            pay = bal / remaining if i == 0 else bal * i / (1 - (1 + i) ** -remaining)
            repay = min(bal, pay - interest)
        bal -= repay
        extra = 0.0
        if mk in corr_by_month:
            # correctie: bekende restschuld aan het eind van deze maand
            extra = max(0.0, bal) - corr_by_month[mk]
            bal = corr_by_month[mk]
            if kind == "lineair":
                lin_step = bal / max(1, term - n)
        out.append({"month": mk, "interest": int(round(interest)), "repayment": int(round(repay)),
                    "extra": int(round(extra)), "balance": int(round(max(0.0, bal)))})
        # afgelost: stoppen, tenzij een latere correctie de restschuld weer zet
        if bal <= 0.5 and kind != "aflossingsvrij" and mk >= last_corr:
            break
    # correcties na het einde van de looptijd: alleen de restschuld bijwerken
    end = _add(start, term)
    for mk in sorted(m for m in corr_by_month if m > end):
        extra = max(0.0, bal) - corr_by_month[mk]
        bal = corr_by_month[mk]
        out.append({"month": mk, "interest": 0, "repayment": 0, "extra": int(round(extra)),
                    "balance": int(round(max(0.0, bal)))})
    return out


def balance_at(part, sched, month, corrections=()):
    """Restschuld aan het eind van 'month' (beginstand vóór de eerste termijn)."""
    if month < _add(part["start"][:7], 1):
        return opening_balance(part, corrections) if month >= part["start"][:7] else None
    last = None
    for row in sched:
        if row["month"] <= month:
            last = row["balance"]
        else:
            break
    return last if last is not None else 0
