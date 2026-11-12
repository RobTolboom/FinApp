"""Hypotheekberekening per leningdeel.

Een leningdeel heeft een hoofdsom, rente (% per jaar), looptijd in maanden,
ingangsdatum en aflosvorm (annuitair, lineair of aflossingsvrij).
Renteherzieningen gelden vanaf de maand van hun datum. Een correctie zet de
restschuld op een bekende waarde (bijvoorbeeld uit het jaaroverzicht van de
bank of na een extra aflossing); vanaf daar wordt verder gerekend.

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


def schedule(part, rates=(), corrections=()):
    """Geeft een lijst maanden met dict(month, interest, repayment, balance)."""
    start = part["start"][:7]
    term = int(part["term_months"])
    kind = part["kind"]
    bal = float(part["principal"])
    lin_step = bal / term if term else 0.0
    rate = float(part["rate"])
    rate_by_month = sorted(((r["date"][:7], float(r["rate"])) for r in rates))
    corr_by_month = {}
    for c in sorted(corrections, key=lambda c: c["date"]):
        corr_by_month[c["date"][:7]] = float(c["balance"])
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
        if mk in corr_by_month:
            # correctie: bekende restschuld aan het eind van deze maand
            bal = corr_by_month[mk]
            if kind == "lineair":
                lin_step = bal / max(1, term - n)
        out.append({"month": mk, "interest": int(round(interest)), "repayment": int(round(repay)),
                    "balance": int(round(max(0.0, bal)))})
        if bal <= 0.5 and kind != "aflossingsvrij":
            break
    # correcties in of voor de startmaand
    return out


def balance_at(part, sched, month):
    """Restschuld aan het eind van 'month' (hoofdsom vóór de eerste termijn)."""
    if month < _add(part["start"][:7], 1):
        return int(part["principal"]) if month >= part["start"][:7] else None
    last = None
    for row in sched:
        if row["month"] <= month:
            last = row["balance"]
        else:
            break
    return last if last is not None else 0
