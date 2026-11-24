from vcg.backtest import backtest
from vcg.baseline import pivot_draft
from vcg.core import data_checks, draft
from vcg.data import build


def test_quiet_month_says_nothing():
    out = draft(build({"seed": 7}))
    assert out["published"]
    assert not any(v["material"] for v in out["variances"])


def test_every_figure_ties_to_the_trial_balance():
    close = build({"seed": 3, "changes": [{"type": "vendor_change", "dept": "ENG", "account": "6150", "vendor": "AWS", "pct": 0.3}]})
    out = draft(close)
    assert out["tie_out"]["ok"] and out["tie_out"]["figures_checked"] >= 2
    for v in out["variances"]:
        assert abs(v["actual"] - close.trial_balance.get((v["dept"], v["account"]), 0)) <= 1


def test_timing_is_not_called_a_price_rise():
    out = draft(build({"seed": 7, "changes": [{"type": "timing_early", "dept": "SAL", "vendor": "Salesforce"}]}))
    v = next(v for v in out["variances"] if (v["dept"], v["account"]) == ("SAL", "6100"))
    assert v["cause"]["type"] == "timing" and "budgeted for December" in v["text"]
    assert "large" in v["holds"]


def test_currency_is_separated_from_spend():
    out = draft(build({"seed": 7, "eur_rate": 1.19, "changes": [{"type": "fx"}]}))
    v = next(v for v in out["variances"] if (v["dept"], v["account"]) == ("OPS-NL", "6000"))
    assert v["cause"]["type"] == "fx"


def test_late_entry_is_held():
    out = draft(
        build({"seed": 7, "changes": [{"type": "late_entry", "dept": "CS", "account": "6200", "vendor": "Concur travel", "amount": 4800}]})
    )
    v = next(v for v in out["variances"] if (v["dept"], v["account"]) == ("CS", "6200"))
    assert v["holds"] == ["late_entry"] and len(v["late_lines"]) == 1


def test_bad_extract_stops_the_draft():
    for change, code in [
        ({"type": "missing_lines", "n": 10}, "extract_does_not_tie"),
        ({"type": "duplicate_lines", "n": 5}, "duplicate_lines"),
        ({"type": "unmapped_department", "dept": "CS", "code": "CS-EMEA"}, "unmapped_department"),
    ]:
        close = build({"seed": 11, "changes": [change]})
        assert [i["code"] for i in data_checks(close)] == [code]
        assert not draft(close)["published"]


def test_pivot_baseline_sends_a_bad_extract():
    assert pivot_draft(build({"seed": 11, "changes": [{"type": "missing_lines", "n": 10}]}))["published"]


def test_backtest_meets_18_of_20_in_every_close():
    results = backtest()
    assert [r["kept"] for r in results] == [20, 18, 19]
    assert all(r["passes"] and r["tie_out"]["ok"] for r in results)
