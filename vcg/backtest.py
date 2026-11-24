"""Back-test three closes against what FP&A wrote: the step before any live close.

For each close, take the 20 largest variances and compare the drafter's cause with FP&A's. The answer key
is synthetic. Where something was planted, FP&A's cause is the planted one; elsewhere it is the largest
vendor gap in the ledger, which is the drafter's own rule, so those cells agree by construction. The test that
matters is the planted items. Each close also plants things only FP&A could know from outside the ledger
(an invoice coded to the wrong department, a late invoice caught up), so a data-only draft cannot get every one.
"""

from __future__ import annotations

from collections import defaultdict

from .core import draft
from .data import BUDGET_RATE, EUR_DEPTS, PAYROLL, build

CLOSES = [
    {
        "seed": 31,
        "month": "2026-09",
        "eur_rate": 1.13,
        "changes": [
            {"type": "vendor_change", "dept": "ENG", "account": "6150", "vendor": "AWS", "pct": 0.15},
            {"type": "hires", "dept": "ENG", "n": 1},
            {"type": "vendor_change", "dept": "SAL", "account": "6200", "vendor": "Concur travel", "pct": 0.35},
            {"type": "vendor_change", "dept": "DATA", "account": "6150", "vendor": "Snowflake", "pct": -0.2},
            {"type": "new_vendor", "dept": "OPS-US", "account": "6100", "vendor": "project44", "amount": 6400},
            {"type": "fx"},
        ],
    },
    {
        "seed": 32,
        "month": "2026-10",
        "eur_rate": 1.15,
        "changes": [
            {"type": "vendor_change", "dept": "OPS-US", "account": "6050", "vendor": "Harbor Staffing", "pct": 0.28},
            {"type": "open_roles", "dept": "CS", "n": 1},
            {"type": "timing_late", "dept": "FIN", "vendor": "Audit firm"},
            {"type": "vendor_change", "dept": "SAL", "account": "6250", "vendor": "LinkedIn Ads", "pct": 0.6},
            {"type": "miscoded", "from": "SAL", "to": "CS", "vendor": "Concur travel", "amount": 6200},
            {"type": "fx"},
        ],
    },
    {
        "seed": 33,
        "month": "2026-11",
        "eur_rate": 1.19,
        "changes": [
            {"type": "vendor_change", "dept": "ENG", "account": "6150", "vendor": "AWS", "pct": 0.22},
            {"type": "hires", "dept": "SAL", "n": 2},
            {"type": "timing_early", "dept": "SAL", "vendor": "Salesforce"},
            {"type": "vendor_change", "dept": "OPS-US", "account": "6050", "vendor": "Harbor Staffing", "pct": 0.31},
            {"type": "late_entry", "dept": "CS", "account": "6200", "vendor": "Concur travel", "amount": 4800},
            {"type": "new_vendor", "dept": "DATA", "account": "6100", "vendor": "dbt Labs", "amount": 7200},
            {"type": "catch_up", "dept": "PPL", "vendor": "Rippling"},
            {"type": "fx"},
        ],
    },
]
TOP = 20
KEEP = 18


def fpa_key(close) -> dict:
    """FP&A's cause per department and account, from the planted truth and the ledger."""
    planted = {(p["dept"], p["account"]): p["cause"] for p in close.truth["planted"]}
    key = {}
    act = defaultdict(float)
    for x in close.lines:
        k = (x["department"], x["account"], x["payee"])
        act[k] += x["amount_local"] * (BUDGET_RATE if x["department"] in EUR_DEPTS else 1.0)
    bud = defaultdict(float)
    for b in close.budget:
        if b["month"] == close.month:
            bud[(b["dept"], b["account"], b["vendor"])] += b["amount"]
    cells = {(d, a) for d, a, _ in act} | {(d, a) for d, a, _ in bud}
    for d, a in cells:
        if (d, a) in planted:
            key[(d, a)] = planted[(d, a)]
            continue
        if a == PAYROLL:
            key[(d, a)] = {"type": "fx", "member": "EUR"} if d in EUR_DEPTS else {"type": "pay", "member": d}
            continue
        payees = {p for dd, aa, p in act if (dd, aa) == (d, a)} | {p for dd, aa, p in bud if (dd, aa) == (d, a)}
        gaps = {p: act.get((d, a, p), 0) - bud.get((d, a, p), 0) for p in payees}
        top = max(gaps.items(), key=lambda kv: abs(kv[1]))[0]
        key[(d, a)] = {"type": "fx", "member": "EUR"} if d in EUR_DEPTS else {"type": "vendor", "member": top}
    return key


def same(a: dict, b: dict) -> bool:
    if a["type"] in ("vendor", "new_vendor") and b["type"] in ("vendor", "new_vendor"):
        return a["member"] == b["member"]
    return a["type"] == b["type"] and a["member"] == b["member"]


def run_close(scenario: dict) -> dict:
    close = build(scenario)
    out = draft(close)
    key = fpa_key(close)
    by_cell = {(v["dept"], v["account"]): v for v in out["variances"]}
    from .core import Queries, _budget_cells, explain

    _, bud_v = _budget_cells(close)
    lines = defaultdict(list)
    for x in close.lines:
        lines[(x["department"], x["account"])].append(x)
    top = sorted(by_cell.values(), key=lambda v: -abs(v["variance"]))[:TOP]
    rows = []
    for v in top:
        cause = v.get("cause") or explain(close, v["dept"], v["account"], lines[(v["dept"], v["account"])], bud_v, Queries(close))
        want = key[(v["dept"], v["account"])]
        rows.append(
            {
                "dept": v["dept"],
                "account": v["account"],
                "variance": v["variance"],
                "drafted": cause["type"],
                "drafted_member": cause["member"],
                "fpa": want["type"],
                "fpa_member": want["member"],
                "kept": same(cause, want),
                "text": v.get("text", ""),
                "material": v["material"],
                "holds": v.get("holds", []),
            }
        )
    kept = sum(r["kept"] for r in rows)
    written = [r for r in rows if r["material"]]
    return {
        "month": close.month,
        "kept": kept,
        "top": len(rows),
        "passes": kept >= KEEP,
        "tie_out": out["tie_out"],
        "rows": rows,
        "written": len(written),
        "written_kept": sum(r["kept"] for r in written),
        "held": sum(1 for v in out["variances"] if v.get("holds")),
    }


def backtest() -> list[dict]:
    return [run_close(s) for s in CLOSES]


if __name__ == "__main__":
    for r in backtest():
        print(
            f"{r['month']}: FP&A keeps {r['kept']} of {r['top']} causes ({'meets' if r['passes'] else 'misses'} 18 of 20); "
            f"tie-out {r['tie_out']['figures_checked']} figures, max diff ${r['tie_out']['max_difference']}"
        )
        for x in r["rows"]:
            if not x["kept"]:
                print("   changed:", x["dept"], x["account"], x["drafted"], x["drafted_member"], "->", x["fpa"], x["fpa_member"])
