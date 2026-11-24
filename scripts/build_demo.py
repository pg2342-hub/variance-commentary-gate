"""Build the GitHub Pages demo in docs/: both gate reports, the November draft, and the back-test.

python scripts/build_demo.py && python scripts/demo_chrome.py docs/index.html --repo variance-commentary-gate
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402
from golive_gate.cli import main as golive  # noqa: E402

from vcg.backtest import CLOSES, KEEP, TOP, backtest  # noqa: E402
from vcg.core import HOLD_USD, MATERIAL_USD, data_checks, draft  # noqa: E402
from vcg.data import ACCOUNTS, DEPARTMENTS, MONTH_NAME, build  # noqa: E402

DOCS = ROOT / "docs"
REPO = "https://github.com/pg2342-hub/variance-commentary-gate"
E = html.escape
GROUPS = {
    "routine": "Routine",
    "hard": "Timing and currency",
    "hold": "Must wait for FP&A",
    "trap": "Bad extract",
    "control": "Quiet month",
}
CAUSE_WORDS = {
    "vendor": "vendor spend",
    "new_vendor": "vendor with no budget line",
    "headcount": "headcount",
    "timing": "timing",
    "fx": "the euro",
    "pay": "pay",
    "miscoded": "coded to the wrong department",
}


def run_gates():
    out = {}
    for agent, folder in (("agent:gated_drafter", "gate"), ("agent:pivot_drafter", "gate-pivot")):
        golive(["run", str(ROOT / "eval" / "golive.yml"), "--agent", agent, "--out", str(DOCS / folder)])
        out[folder] = json.loads((DOCS / folder / "results.json").read_text())
    return out


def strip(g, who):
    crit_ids = {c["id"] for c in g["checks"] if c["critical"]}
    cells, n_crit = [], 0
    for c in g["cases"]:
        r = c["runs"][0]
        crit = bool(r["error"]) or bool(crit_ids & set(r["failed_checks"]))
        n_crit += crit
        cls = "pass" if r["passed"] else ("crit" if crit else "fail")
        word = "passed" if r["passed"] else ("failed with a critical error" if crit else "failed")
        cells.append(f'<a class="cell {cls}" href="#case-{c["id"]}" data-case="{c["id"]}" aria-label="{who} case {c["id"]} {word}"></a>')
    return "".join(cells), n_crit


def vrow(g, name, sub):
    cells, n_crit = strip(g, name)
    r = g["summary"]["by_run"][0]
    go = g["decision"] == "go"
    crit = f"{n_crit} critical" if n_crit else "no critical errors"
    return (
        f'<div class="vrow"><div class="vwho"><b>{name}</b><span>{sub}</span></div>'
        f'<div class="strip" role="group" aria-label="{name}: every case">{cells}</div>'
        f'<div class="vscore"><b>{r["passed"]}</b><span>of {r["total"]} passed<br>{crit}</span></div>'
        f'<span class="gate {"go" if go else "nogo"}">{"GO" if go else "NO-GO"}</span></div>'
    )


def case_rows(g1, g2):
    cases = {c["id"]: c for c in yaml.safe_load((ROOT / "eval" / "cases.yml").read_text())["cases"]}
    texts = {c["id"]: c["text"] for c in g1["checks"]}
    crit_ids = {c["id"] for c in g1["checks"] if c["critical"]}
    p = {c["id"]: c for c in g2["cases"]}
    rows = []
    for c in g1["cases"]:
        r1, r2 = c["runs"][0], p[c["id"]]["runs"][0]
        exp = cases[c["id"]]["expected"] or {}
        if "issue" in exp:
            want = "Stop the draft and name the problem"
        elif "hold" in exp:
            want = {
                "late_entry": "Hold: a line posted after lock",
                "unbudgeted": "Hold: account with no budget",
                "large": "Hold: over $40K",
            }[exp["hold"]]
            if "cause" in exp:
                want += f", cause is {CAUSE_WORDS[exp['cause']['type']]}"
        elif "cause" in exp:
            m = exp["cause"]["member"]
            m = DEPARTMENTS.get(m, m)
            want = f"Cause: {CAUSE_WORDS[exp['cause']['type']]} ({E(m)})"
        else:
            want = "No commentary, nothing held"

        def verdict(r):
            if r["passed"]:
                return '<td class="v ok">Pass</td>'
            crit = bool(crit_ids & set(r["failed_checks"]))
            why = "; ".join(E(texts[f]) for f in r["failed_checks"][:1])
            return f'<td class="v bad{" crit" if crit else ""}">Fail<div class="why">{why}</div></td>'

        rows.append(
            f'<tr id="case-{c["id"]}" data-tier="{c["group"]}"><td class="n">{c["id"]}</td>'
            f'<td><span class="tag">{GROUPS[c["group"]]}</span></td><td class="tx">{E(c["title"])}</td><td>{want}</td>'
            f"{verdict(r1)}{verdict(r2)}</tr>"
        )
    return "".join(rows)


def queries_html(out, v):
    items = []
    for qid in v["queries"]:
        q = out["queries"][qid]
        items.append(f'<li><span class="qv">${q["value"]:,.2f}</span><code>{E(q["sql"])}</code></li>')
    return '<details><summary>The query behind each figure</summary><ol class="qs">' + "".join(items) + "</ol></details>"


def november(out):
    by_dept = {}
    for v in out["variances"]:
        if v["material"]:
            by_dept.setdefault(v["dept"], []).append(v)
    cards = []
    for dept, vs in by_dept.items():
        lines = []
        for v in vs:
            state = "held" if v["holds"] else "send"
            badge = '<span class="st held">Held for FP&amp;A</span>' if v["holds"] else '<span class="st send">Sends</span>'
            hold = f'<p class="hold">{E(v["hold_text"])}</p>' if v["holds"] else ""
            lines.append(f'<li data-s="{state}">{badge}<p>{E(v["text"])}</p>{hold}{queries_html(out, v)}</li>')
        held = all(v["holds"] for v in vs)
        cards.append(
            f'<article class="dept" data-allheld="{str(held).lower()}"><h3>{E(DEPARTMENTS[dept])}</h3><ul>{"".join(lines)}</ul></article>'
        )
    return "".join(cards)


def backtest_svg(results):
    """Three closes, the 20 largest variances in each, one square per variance: kept or changed by FP&A."""
    size, gap, left, top_pad, row_h = 26, 6, 118, 32, 54
    width = left + TOP * (size + gap) + 96
    height = top_pad + len(results) * row_h
    parts = [f'<svg viewBox="0 0 {width} {height}" class="bt" role="img" aria-label="Back-test: causes FP&amp;A kept in each close">']
    x_gate = left + KEEP * (size + gap) - gap / 2
    parts.append(f'<line class="gl" x1="{x_gate}" x2="{x_gate}" y1="22" y2="{height - 6}"/>')
    parts.append(f'<text class="gt" x="{x_gate}" y="16" text-anchor="middle">{KEEP} of {TOP} needed</text>')
    for i, r in enumerate(results):
        y = top_pad + i * row_h
        parts.append(f'<text class="ml" x="0" y="{y + size * 0.7}">{MONTH_NAME[r["month"]]} close</text>')
        rows = sorted(r["rows"], key=lambda x: not x["kept"])
        for j, x in enumerate(rows):
            cx = left + j * (size + gap)
            cls = "k" if x["kept"] else "c"
            d = DEPARTMENTS[x["dept"]]
            amt = ("-" if x["variance"] < 0 else "") + f"${abs(x['variance']):,.0f}"
            title = f"{d}, {ACCOUNTS[x['account']]}: {amt}. " + (
                "FP&A kept the drafted cause." if x["kept"] else f"FP&A changed the cause to {CAUSE_WORDS[x['fpa']]}."
            )
            parts.append(f'<rect class="{cls}" x="{cx}" y="{y}" width="{size}" height="{size}" rx="5"><title>{E(title)}</title></rect>')
        parts.append(f'<text class="mc" x="{width}" y="{y + size * 0.7}" text-anchor="end">{r["kept"]} of {r["top"]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def changed_list(results):
    items = []
    for r in results:
        for x in r["rows"]:
            if not x["kept"]:
                d = DEPARTMENTS[x["dept"]]
                drafted = CAUSE_WORDS[x["drafted"]]
                if x["fpa"] == "miscoded":
                    real = "a Sales travel invoice coded to Customer Success, which shows on both departments"
                else:
                    real = f"{CAUSE_WORDS[x['fpa']]}, a late invoice from the month before posted with this one"
                    if not x["holds"]:
                        real += ". This line would have sent without a hold"
                items.append(
                    f"<li><b>{MONTH_NAME[r['month']]}, {E(d)}, {E(ACCOUNTS[x['account']])}.</b> Drafted as {drafted} "
                    f"({E(x['drafted_member'])}); FP&amp;A knows it is {real}.</li>"
                )
    return "".join(items)


def traps():
    rows = []
    for change, text in [
        ({"type": "missing_lines", "n": 20}, "Extract pulled before the last AP batch"),
        ({"type": "duplicate_lines", "n": 12}, "Saved search exported a page twice"),
        ({"type": "unmapped_department", "dept": "CS", "code": "CS-EMEA"}, "New department code nobody mapped"),
        ({"type": "unmapped_account", "account": "6100", "code": "6105", "n": 3}, "Lines on an account outside the chart"),
    ]:
        issue = data_checks(build({"seed": 7, "changes": [change]}))[0]
        rows.append(f'<tr><td>{E(text)}</td><td class="say">{E(issue["detail"])}</td><td><span class="st held">Stopped</span></td></tr>')
    return "".join(rows)


def main():
    g = run_gates()
    g1, g2 = g["gate"], g["gate-pivot"]
    nov = draft(build(CLOSES[2]))
    bt = backtest()
    mat = [v for v in nov["variances"] if v["material"]]
    n_send = sum(1 for v in mat if not v["holds"])
    n_held = len(mat) - n_send
    tie = nov["tie_out"]
    p1 = g1["summary"]["by_run"][0]
    p2 = g2["summary"]["by_run"][0]
    kept = ", ".join(f"{r['kept']}" for r in bt)
    written = ", ".join(f"{r['written_kept']} of {r['written']}" for r in bt)
    page = (ROOT / "scripts" / "page.html").read_text()
    subs = {
        "{{VROWS}}": vrow(g1, "Gated drafter", "Data checks, tie-out, one cause per variance, holds")
        + vrow(g2, "Payee pivot", "Department and account pivot, biggest payee gap, sends everything"),
        "{{CASES}}": case_rows(g1, g2),
        "{{NOV}}": november(nov),
        "{{NSEND}}": str(n_send),
        "{{NHELD}}": str(n_held),
        "{{NALL}}": str(len(mat)),
        "{{TIEN}}": str(tie["figures_checked"]),
        "{{TIEMAX}}": f"${tie['max_difference']:,.2f}",
        "{{BTSVG}}": backtest_svg(bt),
        "{{CHANGED}}": changed_list(bt),
        "{{KEPT}}": kept,
        "{{WRITTEN}}": written,
        "{{TRAPS}}": traps(),
        "{{P1}}": f"{p1['passed']} of {p1['total']}",
        "{{P2}}": f"{p2['passed']} of {p2['total']}",
        "{{HOLD}}": f"${HOLD_USD // 1000}K",
        "{{MAT}}": f"${MATERIAL_USD // 1000}K",
        "{{REPO}}": REPO,
    }
    for k, v in subs.items():
        page = page.replace(k, v)
    assert "{{" not in page
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("")
    print("docs/index.html written")


if __name__ == "__main__":
    main()
