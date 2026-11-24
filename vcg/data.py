"""A made-up freight forwarder's month: NetSuite-style GL lines, a trial balance, and a vendor-level budget.

Everything here is synthetic. A scenario is a seed, a close month, and a list of planted changes;
`build(scenario)` returns the extract the drafter reads plus the truth the eval grades against.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

BUDGET_RATE = 1.08  # USD per EUR in the budget
MONTHS = [f"2026-{m:02d}" for m in range(1, 13)]
MONTH_NAME = {m: datetime(2026, int(m[5:]), 1).strftime("%B") for m in MONTHS}

# Department codes as they appear in the extract, mapped to reporting departments (the mapping FP&A owns).
DEPARTMENTS = {
    "OPS-US": "Operations",
    "OPS-NL": "Operations Europe",
    "SAL": "Sales",
    "CS": "Customer Success",
    "ENG": "Engineering",
    "DATA": "Data & Analytics",
    "PPL": "People",
    "FIN": "Finance",
}
EUR_DEPTS = {"OPS-NL"}

ACCOUNTS = {
    "6000": "Salaries and wages",
    "6050": "Contractors",
    "6100": "Software subscriptions",
    "6150": "Cloud hosting",
    "6200": "Travel",
    "6250": "Marketing programs",
    "6300": "Professional fees",
    "6350": "Facilities",
    "6400": "Recruiting",
}
PAYROLL = "6000"

# Headcount plan and average monthly pay (in the department's currency).
HEADCOUNT = {
    "OPS-US": (14, 7800),
    "OPS-NL": (8, 6900),
    "SAL": (6, 11500),
    "CS": (5, 8200),
    "ENG": (9, 14500),
    "DATA": (4, 13200),
    "PPL": (3, 9800),
    "FIN": (4, 11000),
}

# Non-payroll budget lines: department, account, vendor, monthly amount, and when it bills.
# "monthly" bills every month; ("annual", m) bills once in month m; ("quarterly", m) in m, m+3, ...
PLAN = [
    ("OPS-US", "6050", "Harbor Staffing", 42000, "monthly"),
    ("OPS-US", "6100", "Descartes", 9500, "monthly"),
    ("OPS-US", "6200", "Concur travel", 14000, "monthly"),
    ("OPS-US", "6350", "Carlsbad lease", 38000, "monthly"),
    ("OPS-NL", "6050", "Randstad", 21000, "monthly"),
    ("OPS-NL", "6200", "Concur travel", 6500, "monthly"),
    ("OPS-NL", "6350", "Schiphol lease", 24000, "monthly"),
    ("SAL", "6100", "Salesforce", 96000, ("annual", 12)),
    ("SAL", "6100", "ZoomInfo", 4200, "monthly"),
    ("SAL", "6200", "Concur travel", 18000, "monthly"),
    ("SAL", "6250", "Trade shows", 22000, ("quarterly", 2)),
    ("SAL", "6250", "LinkedIn Ads", 9000, "monthly"),
    ("CS", "6100", "Zendesk", 3800, "monthly"),
    ("CS", "6200", "Concur travel", 5200, "monthly"),
    ("ENG", "6100", "GitHub", 2600, "monthly"),
    ("ENG", "6100", "Datadog", 7400, "monthly"),
    ("ENG", "6150", "AWS", 61000, "monthly"),
    ("ENG", "6050", "Northbeam Dev", 18000, "monthly"),
    ("DATA", "6150", "Snowflake", 23000, "monthly"),
    ("DATA", "6100", "Fivetran", 3100, "monthly"),
    ("PPL", "6100", "Rippling", 5400, "monthly"),
    ("PPL", "6400", "Greenhouse", 30000, ("annual", 3)),
    ("PPL", "6400", "LinkedIn Recruiter", 6800, "monthly"),
    ("FIN", "6100", "NetSuite", 84000, ("annual", 7)),
    ("FIN", "6300", "Audit firm", 15000, "monthly"),
    ("FIN", "6300", "Outside counsel", 8000, "monthly"),
]


def bills_in(timing, month: str) -> bool:
    m = int(month[5:])
    if timing == "monthly":
        return True
    kind, start = timing
    if kind == "annual":
        return m == start
    return (m - start) % 3 == 0


@dataclass
class Close:
    month: str
    lock_at: datetime
    lines: list  # the extract: what the drafter reads
    trial_balance: dict  # (dept_code, account) -> USD, straight from the ledger
    budget: list  # vendor-level budget lines for the whole year, USD at the budget rate
    headcount_plan: dict
    eur_rate: float
    dept_map: dict = field(default_factory=lambda: dict(DEPARTMENTS))
    accounts: dict = field(default_factory=lambda: dict(ACCOUNTS))
    truth: dict = field(default_factory=dict)


def _lock(month: str) -> datetime:
    y, m = int(month[:4]), int(month[5:])
    nxt = datetime(y + (m == 12), m % 12 + 1, 1)
    days = 0
    d = nxt
    while days < 5:  # books lock on the fifth business day
        if d.weekday() < 5:
            days += 1
        if days < 5:
            d += timedelta(days=1)
    return d.replace(hour=18)


def _posted(rng, month: str, lock: datetime) -> datetime:
    y, m = int(month[:4]), int(month[5:])
    start = datetime(y, m, 3, 9)
    span = (lock - timedelta(hours=30) - start).total_seconds()
    return start + timedelta(seconds=rng.uniform(0, span))


def build(scenario: dict) -> Close:
    rng = random.Random(scenario.get("seed", 7))
    month = scenario.get("month", "2026-11")
    lock = _lock(month)
    eur = scenario.get("eur_rate", BUDGET_RATE)
    changes = scenario.get("changes", [])
    truth = {"planted": [], "issue": None, "holds": []}

    # Budget: vendor lines for the year plus payroll at plan.
    budget = []
    for dept, acct, vendor, amt, timing in PLAN:
        fx = BUDGET_RATE if dept in EUR_DEPTS else 1.0
        for mo in MONTHS:
            if bills_in(timing, mo):
                budget.append({"month": mo, "dept": dept, "account": acct, "vendor": vendor, "amount": round(amt * fx, 2)})
    plan_hc = {d: n for d, (n, _) in HEADCOUNT.items()}
    for dept, (n, pay) in HEADCOUNT.items():
        fx = BUDGET_RATE if dept in EUR_DEPTS else 1.0
        for mo in MONTHS:
            budget.append({"month": mo, "dept": dept, "account": PAYROLL, "vendor": "Payroll", "amount": round(n * pay * fx, 2)})

    # Actual activity, in the department's own currency, before planted changes.
    activity = []  # dicts with dept, account, payee, memo, local amount, kind
    for dept, acct, vendor, amt, timing in PLAN:
        if bills_in(timing, month):
            noise = 1 + rng.gauss(0, 0.012) if timing == "monthly" else 1.0
            activity.append({"dept": dept, "account": acct, "payee": vendor, "memo": f"{vendor} invoice", "local": amt * noise})
    staff = {}
    for dept, (n, pay) in HEADCOUNT.items():
        staff[dept] = [round(pay * (1 + rng.uniform(-0.18, 0.18)), 2) for _ in range(n)]
        # keep total pay on plan so payroll noise stays small
        k = n * pay / sum(staff[dept])
        staff[dept] = [round(p * k, 2) for p in staff[dept]]

    late = []
    for ch in changes:
        t = ch["type"]
        if t in ("vendor_change", "one_off", "new_vendor", "unbudgeted_account"):
            if t == "vendor_change":
                row = next(a for a in activity if a["dept"] == ch["dept"] and a["payee"] == ch["vendor"])
                before = row["local"]
                row["local"] = before * (1 + ch["pct"])
                delta = row["local"] - before
                cause = {"type": "vendor", "member": ch["vendor"]}
            else:
                delta = ch["amount"]
                activity.append(
                    {
                        "dept": ch["dept"],
                        "account": ch["account"],
                        "payee": ch["vendor"],
                        "memo": ch.get("memo", f"{ch['vendor']} invoice"),
                        "local": delta,
                    }
                )
                cause = {"type": "new_vendor" if t != "one_off" else "vendor", "member": ch["vendor"]}
                if t == "one_off" and not any(b["vendor"] == ch["vendor"] and b["dept"] == ch["dept"] for b in budget):
                    cause["type"] = "new_vendor"
            fx = eur if ch["dept"] in EUR_DEPTS else 1.0
            truth["planted"].append({"dept": ch["dept"], "account": ch["account"], "cause": cause, "amount": round(delta * fx, 2)})
            if t == "unbudgeted_account":
                truth["holds"].append({"dept": ch["dept"], "account": ch["account"], "reason": "unbudgeted"})
        elif t == "hires":
            pay = HEADCOUNT[ch["dept"]][1]
            staff[ch["dept"]] += [pay] * ch["n"]
            fx = eur if ch["dept"] in EUR_DEPTS else 1.0
            truth["planted"].append(
                {
                    "dept": ch["dept"],
                    "account": PAYROLL,
                    "cause": {"type": "headcount", "member": ch["dept"]},
                    "amount": round(pay * ch["n"] * fx, 2),
                }
            )
        elif t == "open_roles":
            pay = HEADCOUNT[ch["dept"]][1]
            staff[ch["dept"]] = staff[ch["dept"]][: -ch["n"]]
            fx = eur if ch["dept"] in EUR_DEPTS else 1.0
            truth["planted"].append(
                {
                    "dept": ch["dept"],
                    "account": PAYROLL,
                    "cause": {"type": "headcount", "member": ch["dept"]},
                    "amount": -round(pay * ch["n"] * fx, 2),
                }
            )
        elif t == "timing_early":  # an annual invoice billed this month, budgeted for a later one
            dept, acct, vendor, amt, _ = next(p for p in PLAN if p[0] == ch["dept"] and p[2] == ch["vendor"])
            activity.append({"dept": dept, "account": acct, "payee": vendor, "memo": f"{vendor} annual renewal", "local": amt})
            truth["planted"].append({"dept": dept, "account": acct, "cause": {"type": "timing", "member": vendor}, "amount": amt})
        elif t == "timing_late":  # an invoice budgeted this month that has not arrived
            row = next(a for a in activity if a["dept"] == ch["dept"] and a["payee"] == ch["vendor"])
            activity.remove(row)
            truth["planted"].append(
                {
                    "dept": ch["dept"],
                    "account": row["account"],
                    "cause": {"type": "timing", "member": ch["vendor"]},
                    "amount": -round(row["local"], 2),
                }
            )
        elif t == "late_entry":
            late.append(ch)
            truth["holds"].append({"dept": ch["dept"], "account": ch["account"], "reason": "late_entry"})
        elif t == "large":
            row = next(a for a in activity if a["dept"] == ch["dept"] and a["payee"] == ch["vendor"])
            before = row["local"]
            row["local"] = before + ch["amount"]
            truth["planted"].append(
                {"dept": ch["dept"], "account": row["account"], "cause": {"type": "vendor", "member": ch["vendor"]}, "amount": ch["amount"]}
            )
            truth["holds"].append({"dept": ch["dept"], "account": row["account"], "reason": "large"})
        elif t == "miscoded":  # a Sales invoice coded to another department; only FP&A knows (back-test answer key)
            src = next(a for a in activity if a["dept"] == ch["from"] and a["payee"] == ch["vendor"])
            src["local"] -= ch["amount"]
            activity.append(
                {
                    "dept": ch["to"],
                    "account": src["account"],
                    "payee": ch["vendor"],
                    "memo": f"{ch['vendor']} invoice",
                    "local": ch["amount"],
                }
            )
            for d, sign in ((ch["to"], 1), (ch["from"], -1)):
                truth["planted"].append(
                    {
                        "dept": d,
                        "account": src["account"],
                        "cause": {"type": "miscoded", "member": f"{ch['from']} to {ch['to']}"},
                        "amount": sign * ch["amount"],
                    }
                )
        elif t == "catch_up":  # last month's invoice arrived late and posted with this month's; looks like a price rise
            row = next(a for a in activity if a["dept"] == ch["dept"] and a["payee"] == ch["vendor"])
            budgeted = next(p[3] for p in PLAN if p[0] == ch["dept"] and p[2] == ch["vendor"])
            row["local"] += budgeted
            truth["planted"].append(
                {"dept": ch["dept"], "account": row["account"], "cause": {"type": "timing", "member": ch["vendor"]}, "amount": budgeted}
            )

    if any(c["type"] == "fx" for c in changes):
        planted_fx = sum(sum(staff[d]) + sum(a["local"] for a in activity if a["dept"] == d) for d in EUR_DEPTS)
        truth["fx_effect"] = round(planted_fx * (eur - BUDGET_RATE), 2)
        for c in changes:
            if c["type"] == "fx":
                acct = c.get("account", PAYROLL)
                local = (
                    sum(staff["OPS-NL"])
                    if acct == PAYROLL
                    else sum(a["local"] for a in activity if a["dept"] == "OPS-NL" and a["account"] == acct)
                )
                truth["planted"].append(
                    {
                        "dept": "OPS-NL",
                        "account": acct,
                        "cause": {"type": "fx", "member": "EUR"},
                        "amount": round(local * (eur - BUDGET_RATE), 2),
                    }
                )

    # Post everything as GL lines.
    lines = []
    seq = 0

    def post(dept, acct, payee, memo, local, when):
        nonlocal seq
        seq += 1
        cur = "EUR" if dept in EUR_DEPTS else "USD"
        fx = eur if cur == "EUR" else 1.0
        lines.append(
            {
                "id": f"JL{month[2:4]}{month[5:]}-{seq:05d}",
                "period": month,
                "posted_at": when.isoformat(timespec="minutes"),
                "subsidiary": "Europe B.V." if cur == "EUR" else "US Inc.",
                "department": dept,
                "account": acct,
                "payee": payee,
                "memo": memo,
                "currency": cur,
                "amount_local": round(local, 2),
                "amount": round(local * fx, 2),
            }
        )

    for dept, pays in staff.items():
        for i, p in enumerate(pays):
            post(dept, PAYROLL, f"Employee {dept}-{i + 1:02d}", "Monthly payroll", p, _posted(rng, month, lock))
    for a in activity:
        # big invoices arrive in two or three lines, like real AP
        parts = 1 if a["local"] < 20000 else rng.choice([2, 3])
        cuts = sorted(rng.uniform(0.2, 0.8) for _ in range(parts - 1))
        shares = [b - a_ for a_, b in zip([0] + cuts, cuts + [1])]
        for s in shares:
            post(a["dept"], a["account"], a["payee"], a["memo"], a["local"] * s, _posted(rng, month, lock))
    for ch in late:
        post(
            ch["dept"],
            ch["account"],
            ch["vendor"],
            ch.get("memo", "Late invoice"),
            ch["amount"],
            lock + timedelta(hours=ch.get("hours_after", 20)),
        )
        truth["planted"].append(
            {
                "dept": ch["dept"],
                "account": ch["account"],
                "cause": {
                    "type": "new_vendor" if not any(p[2] == ch["vendor"] and p[0] == ch["dept"] for p in PLAN) else "vendor",
                    "member": ch["vendor"],
                },
                "amount": ch["amount"],
            }
        )

    tb = {}
    for ln in lines:
        k = (ln["department"], ln["account"])
        tb[k] = round(tb.get(k, 0) + ln["amount"], 2)

    # Data problems: the extract stops matching the ledger or the mappings.
    extract = [dict(x) for x in lines]
    dept_map, accounts = dict(DEPARTMENTS), dict(ACCOUNTS)
    for ch in changes:
        t = ch["type"]
        if t == "missing_lines":
            cut = sorted(extract, key=lambda x: x["posted_at"])[-ch.get("n", 25) :]
            ids = {x["id"] for x in cut}
            extract = [x for x in extract if x["id"] not in ids]
            truth["issue"] = "extract_does_not_tie"
        elif t == "duplicate_lines":
            extract = extract + [dict(x) for x in extract[10 : 10 + ch.get("n", 12)]]
            truth["issue"] = "duplicate_lines"
        elif t == "unmapped_department":
            for x in extract:
                if x["department"] == ch["dept"]:
                    x["department"] = ch["code"]
            truth["issue"] = "unmapped_department"
        elif t == "unmapped_account":
            hit = [x for x in extract if x["account"] == ch["account"]][: ch.get("n", 3)]
            for x in hit:
                x["account"] = ch["code"]
            truth["issue"] = "unmapped_account"

    truth["trial_balance"] = {f"{d}|{a}": v for (d, a), v in tb.items()}
    return Close(
        month=month,
        lock_at=lock,
        lines=extract,
        trial_balance=tb,
        budget=budget,
        headcount_plan=plan_hc,
        eur_rate=eur,
        dept_map=dept_map,
        accounts=accounts,
        truth=truth,
    )
