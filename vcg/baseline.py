"""A spreadsheet-style drafter to compare against: pivot the extract by department and account,
name the payee with the biggest gap to budget, and send. No data checks, no tie-out, no holds."""

from __future__ import annotations

from collections import defaultdict

from .core import MATERIAL_PCT, MATERIAL_USD, _budget_cells, sentence
from .data import Close


def pivot_draft(close: Close) -> dict:
    bud_cells, bud_v = _budget_cells(close)
    cells, by_payee = defaultdict(float), defaultdict(float)
    for x in close.lines:
        cells[(x["department"], x["account"])] += x["amount"]
        by_payee[(x["department"], x["account"], x["payee"])] += x["amount"]
    out = []
    for key in sorted(set(cells) | set(bud_cells)):
        dept, acct = key
        act, bud = round(cells.get(key, 0), 2), round(bud_cells.get(key, 0), 2)
        var = round(act - bud, 2)
        pct = var / bud if bud else 1.0
        material = (abs(var) >= MATERIAL_USD and abs(pct) >= MATERIAL_PCT) or (bud == 0 and act != 0)
        v = {"dept": dept, "account": acct, "actual": act, "budget": bud, "variance": var, "pct": pct, "material": material}
        if material:
            payees = {p for (d, a, p) in by_payee if (d, a) == key} | {p for (d, a, p) in bud_v if (d, a) == key}
            gaps = {p: by_payee.get((dept, acct, p), 0) - bud_v.get((dept, acct, p), 0) for p in payees}
            top = max(gaps.items(), key=lambda kv: abs(kv[1]))
            v["cause"] = {
                "type": "new_vendor" if not bud_v.get((dept, acct, top[0])) and top[1] > 0 else "vendor",
                "member": top[0],
                "amount": round(top[1], 2),
                "actual": by_payee.get((dept, acct, top[0]), 0),
                "budget": bud_v.get((dept, acct, top[0]), 0),
            }
            v["holds"] = []
            v["text"] = sentence(close, v)
        out.append(v)
    return {"published": True, "issues": [], "variances": out, "queries": {}, "tie_out": None}
