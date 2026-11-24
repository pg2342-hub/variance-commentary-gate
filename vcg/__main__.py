"""Draft one close and print what sends, what is held, and the query behind each figure.

python -m vcg                 # the November back-test close
python -m vcg --close 2026-09 --sql
"""

from __future__ import annotations

import argparse

from .backtest import CLOSES
from .core import draft
from .data import DEPARTMENTS, build


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--close", default="2026-11", choices=[c["month"] for c in CLOSES])
    ap.add_argument("--sql", action="store_true", help="print the query behind every figure")
    args = ap.parse_args()
    scen = next(c for c in CLOSES if c["month"] == args.close)
    out = draft(build(scen))
    if not out["published"]:
        for i in out["issues"]:
            print("STOPPED:", i["detail"])
        return
    t = out["tie_out"]
    gap = t["max_difference"]
    print(f"Tie-out: {t['figures_checked']} figures re-run against the trial balance and budget, largest difference ${gap:.2f}\n")
    for v in out["variances"]:
        if not v["material"]:
            continue
        status = "HELD" if v["holds"] else "SEND"
        print(f"[{status}] {DEPARTMENTS[v['dept']]}: {v['text']}")
        if v["holds"]:
            print(f"        {v['hold_text']}")
        if args.sql:
            for qid in v["queries"]:
                q = out["queries"][qid]
                print(f"        {qid} = {q['value']:,.2f}  {q['sql']}")


if __name__ == "__main__":
    main()
