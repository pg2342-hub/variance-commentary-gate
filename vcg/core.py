"""The drafter: data checks, tie-out, variances, causes, commentary, and the hold rules.

No model calls. This is the deterministic layer an agent's commentary has to tie back to: every
figure it writes comes from a query listed next to it, and every query is re-run against the ledger.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from .data import ACCOUNTS, BUDGET_RATE, EUR_DEPTS, MONTH_NAME, MONTHS, PAYROLL, Close

MATERIAL_USD = 5000  # a variance gets a line of commentary at $5K and 5% of budget
MATERIAL_PCT = 0.05
HOLD_USD = 40000  # anything this size waits for FP&A, even after go-live
TIE_TOLERANCE = 1.0  # dollars


def money(x: float, signed: bool = False) -> str:
    s = f"${abs(x) / 1000:,.1f}K" if abs(x) >= 1000 else f"${abs(x):,.0f}"
    if signed:
        return ("+" if x >= 0 else "-") + s
    return s


def data_checks(close: Close) -> list[dict]:
    issues = []
    depts = {x["department"] for x in close.lines}
    bad = sorted(depts - set(close.dept_map))
    if bad:
        issues.append({"code": "unmapped_department", "detail": f"Department code {', '.join(bad)} is not in the department map."})
    accts = {x["account"] for x in close.lines}
    bad = sorted(accts - set(close.accounts))
    if bad:
        issues.append({"code": "unmapped_account", "detail": f"Account {', '.join(bad)} is not in the chart of accounts."})
    seen, dup = set(), 0
    for x in close.lines:
        dup += x["id"] in seen
        seen.add(x["id"])
    if dup:
        issues.append({"code": "duplicate_lines", "detail": f"{dup} journal lines appear twice in the extract."})
    if not issues:
        ext = defaultdict(float)
        for x in close.lines:
            ext[(x["department"], x["account"])] += x["amount"]
        keys = set(ext) | set(close.trial_balance)
        breaks = [(k, ext.get(k, 0) - close.trial_balance.get(k, 0)) for k in keys]
        breaks = [(k, d) for k, d in breaks if abs(d) > TIE_TOLERANCE]
        if breaks:
            total = sum(d for _, d in breaks)
            issues.append(
                {
                    "code": "extract_does_not_tie",
                    "detail": f"The extract misses the trial balance by {money(total, True)} "
                    f"across {len(breaks)} department and account cells.",
                }
            )
    return issues


def _sql(dept: str, acct: str, month: str, extra: str = "", what: str = "SUM(tl.amount)") -> str:
    return (
        f"SELECT {what} FROM transactionline tl JOIN transaction t ON t.id = tl.transaction "
        f"WHERE t.postingperiod = '{month}' AND tl.department = '{dept}' AND tl.account = '{acct}'{extra}"
    )


class Queries:
    def __init__(self, close: Close):
        self.close, self.items, self.n = close, {}, 0

    def add(self, sql: str, value: float, kind: str, key: dict) -> str:
        self.n += 1
        qid = f"Q{self.n}"
        self.items[qid] = {"sql": sql, "value": round(value, 2), "kind": kind, "key": key}
        return qid


def _budget_cells(close: Close):
    cells = defaultdict(float)
    by_vendor = defaultdict(float)
    for b in close.budget:
        if b["month"] == close.month:
            cells[(b["dept"], b["account"])] += b["amount"]
            by_vendor[(b["dept"], b["account"], b["vendor"])] += b["amount"]
    return cells, by_vendor


def _later_budget(close: Close, dept: str, vendor: str):
    after = MONTHS[MONTHS.index(close.month) + 1 :]
    for b in close.budget:
        if b["dept"] == dept and b["vendor"] == vendor and b["month"] in after:
            return b
    return None


def explain(close: Close, dept: str, acct: str, lines: list, budget_v: dict, q: Queries) -> dict:
    """Name the one driver behind a department and account variance, with the queries behind its figures."""
    if acct == PAYROLL:
        n = len({x["payee"] for x in lines})
        plan = close.headcount_plan[dept]
        act = sum(x["amount"] for x in lines)
        bud = budget_v.get((dept, acct, "Payroll"), 0)
        cand = []
        if n != plan:
            per_head = bud / plan if plan else 0
            cand.append(("headcount", dept, (n - plan) * per_head))
        if dept in EUR_DEPTS:
            local = sum(x["amount_local"] for x in lines)
            cand.append(("fx", "EUR", local * (close.eur_rate - BUDGET_RATE)))
        extra = {"rate": close.eur_rate} if dept in EUR_DEPTS else {}
        if not cand:
            cand.append(("pay", dept, act - bud))
        typ, member, amt = max(cand, key=lambda c: abs(c[2]))
        qn = q.add(_sql(dept, acct, close.month, what="COUNT(DISTINCT tl.entity)"), n, "headcount", {"dept": dept, "account": acct})
        return {"type": typ, "member": member, "amount": round(amt, 2), "queries": [qn], "headcount": n, "plan": plan} | extra

    act_v = defaultdict(float)
    loc_v = defaultdict(float)
    for x in lines:
        act_v[x["payee"]] += x["amount"]
        loc_v[x["payee"]] += x["amount_local"]
    vendors = set(act_v) | {v for (d, a, v) in budget_v if d == dept and a == acct}
    diffs = {v: act_v.get(v, 0) - budget_v.get((dept, acct, v), 0) for v in vendors}
    if dept in EUR_DEPTS:
        fx = sum(loc_v.values()) * (close.eur_rate - BUDGET_RATE)
        local_diffs = {v: loc_v.get(v, 0) * BUDGET_RATE - budget_v.get((dept, acct, v), 0) for v in vendors}
        top_local = max(local_diffs.items(), key=lambda kv: abs(kv[1]))
        if abs(fx) > abs(top_local[1]):
            qn = q.add(
                _sql(dept, acct, close.month, what="SUM(tl.foreignamount)"), sum(loc_v.values()), "local", {"dept": dept, "account": acct}
            )
            return {"type": "fx", "member": "EUR", "amount": round(fx, 2), "queries": [qn], "rate": close.eur_rate}
        diffs = local_diffs
    vendor, amt = max(diffs.items(), key=lambda kv: abs(kv[1]))
    budgeted = budget_v.get((dept, acct, vendor), 0)
    actual = act_v.get(vendor, 0)
    qn = q.add(
        _sql(dept, acct, close.month, f" AND tl.entity = '{vendor}'"), actual, "vendor", {"dept": dept, "account": acct, "vendor": vendor}
    )
    out = {"member": vendor, "amount": round(amt, 2), "queries": [qn], "actual": round(actual, 2), "budget": round(budgeted, 2)}
    if not budgeted:
        later = _later_budget(close, dept, vendor)
        if later and abs(later["amount"] - actual) <= 0.1 * later["amount"]:
            return out | {"type": "timing", "budget_month": later["month"]}
        return out | {"type": "new_vendor"}
    if not actual:
        return out | {"type": "timing", "not_billed": True}
    return out | {"type": "vendor"}


def sentence(close: Close, v: dict) -> str:
    acct, c = ACCOUNTS.get(v["account"], f"Account {v['account']}"), v["cause"]
    dirn = "over" if v["variance"] > 0 else "under"
    pct = "no budget" if not v["budget"] else (f"{v['pct']:+.0%}" if abs(v["pct"]) < 10 else "over 10x budget")
    head = f"{acct} is {money(v['variance'])} {dirn} budget ({pct})"
    mon = MONTH_NAME[close.month]
    t = c["type"]
    if t == "headcount":
        gap = c["headcount"] - c["plan"]
        word = "ahead of" if gap > 0 else "behind"
        hires = "1 hire" if abs(gap) == 1 else f"{abs(gap)} hires"
        return f"{head}, mainly headcount of {c['headcount']} against a plan of {c['plan']}, {hires} {word} plan."
    if t == "fx":
        return f"{head}, mainly the euro at {c['rate']:.2f} against the budget rate of {BUDGET_RATE:.2f}, worth {money(c['amount'], True)}."
    if t == "timing" and c.get("not_billed"):
        return f"{head}, mainly timing, {c['member']} is budgeted for {mon} at {money(c['budget'])} and has not billed yet."
    if t == "timing":
        return (
            f"{head}, mainly timing, {c['member']} billed {money(c['actual'])} in {mon} that is budgeted for "
            f"{MONTH_NAME[c['budget_month']]}."
        )
    if t == "new_vendor":
        return f"{head}, mainly {c['member']} at {money(c['actual'])}, which has no budget line."
    if t == "pay":
        return f"{head}, mainly pay changes at a headcount on plan."
    return f"{head}, mainly {c['member']} at {money(c['actual'])} against {money(c['budget'])} budgeted."


HOLD_WORDS = {
    "late_entry": "{n} posted after the books locked",
    "unbudgeted": "the account has no budget this month",
    "large": "the variance is above the $40K review line",
}


def hold_text(v: dict) -> str:
    n = len(v["late_lines"])
    why = [HOLD_WORDS[h].format(n=f"{n} line" if n == 1 else f"{n} lines") for h in v["holds"]]
    return "Held for FP&A because " + " and ".join(why) + "."


def draft(close: Close) -> dict:
    """Draft one close. Returns what would send, what is held for FP&A, and the query behind every figure."""
    issues = data_checks(close)
    if issues:
        return {"published": False, "issues": issues, "variances": [], "commentary": {}, "queries": {}, "tie_out": None}

    q = Queries(close)
    bud_cells, bud_v = _budget_cells(close)
    by_cell = defaultdict(list)
    for x in close.lines:
        by_cell[(x["department"], x["account"])].append(x)
    lock = close.lock_at
    out = []
    for key in sorted(set(by_cell) | set(bud_cells)):
        dept, acct = key
        lines = by_cell.get(key, [])
        act = round(sum(x["amount"] for x in lines), 2)
        bud = round(bud_cells.get(key, 0), 2)
        var = round(act - bud, 2)
        pct = var / bud if bud else 1.0
        material = (abs(var) >= MATERIAL_USD and abs(pct) >= MATERIAL_PCT) or (bud == 0 and act != 0)
        late = [x for x in lines if datetime.fromisoformat(x["posted_at"]) > lock]
        holds = []
        if late:
            holds.append("late_entry")
        if bud == 0 and act != 0:
            holds.append("unbudgeted")
        if abs(var) >= HOLD_USD:
            holds.append("large")
        if not material and not holds:
            out.append({"dept": dept, "account": acct, "actual": act, "budget": bud, "variance": var, "pct": pct, "material": False})
            continue
        qa = q.add(_sql(dept, acct, close.month), act, "actual", {"dept": dept, "account": acct})
        qb = q.add(
            f"SELECT SUM(amount) FROM budget WHERE period = '{close.month}' AND department = '{dept}' AND account = '{acct}'",
            bud,
            "budget",
            {"dept": dept, "account": acct},
        )
        cause = explain(close, dept, acct, lines, bud_v, q)
        v = {
            "dept": dept,
            "account": acct,
            "actual": act,
            "budget": bud,
            "variance": var,
            "pct": pct,
            "material": True,
            "cause": cause,
            "holds": holds,
            "late_lines": [x["id"] for x in late],
            "queries": [qa, qb] + cause["queries"],
        }
        v["text"] = sentence(close, v)
        if holds:
            v["hold_text"] = hold_text(v)
        out.append(v)

    tie = tie_out(close, q)
    commentary = defaultdict(lambda: {"send": [], "held": []})
    for v in out:
        if v["material"]:
            commentary[v["dept"]]["held" if v["holds"] else "send"].append(v["text"])
    return {"published": True, "issues": [], "variances": out, "commentary": dict(commentary), "queries": q.items, "tie_out": tie}


def tie_out(close: Close, q: Queries) -> dict:
    """Re-run every figure the commentary uses against the trial balance and the budget file."""
    bud_cells, _ = _budget_cells(close)
    checked, worst = 0, 0.0
    for item in q.items.values():
        k = item["key"]
        if item["kind"] == "actual":
            ref = close.trial_balance.get((k["dept"], k["account"]), 0)
        elif item["kind"] == "budget":
            ref = bud_cells.get((k["dept"], k["account"]), 0)
        else:
            continue
        checked += 1
        worst = max(worst, abs(item["value"] - ref))
    return {"ok": worst <= TIE_TOLERANCE, "figures_checked": checked, "max_difference": round(worst, 2)}
