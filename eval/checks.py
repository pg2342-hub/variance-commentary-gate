"""Yes/no checks on each drafted close. Three are critical: one failure blocks automatic sends."""

from golive_gate import NA, CheckSet

checks = CheckSet()


def _cell(out, cell):
    return next((v for v in out["variances"] if [v["dept"], v["account"]] == list(cell)), None)


@checks.check("stops_on_bad_data", text="A data problem stops the draft; a clean extract produces one.", critical=True)
def stops_on_bad_data(case, out):
    return out["published"] == ("issue" not in case.expected)


@checks.check("names_the_problem", text="The draft names the planted data problem.")
def names_the_problem(case, out):
    if "issue" not in case.expected:
        return NA
    return case.expected["issue"] in {i["code"] for i in out["issues"]}


@checks.check("every_figure_ties", text="Every actual in a sent draft equals the ledger's trial balance to the dollar.", critical=True)
def every_figure_ties(case, out):
    if not out["published"]:
        return NA
    tb = out["truth"]["trial_balance"]
    for v in out["variances"]:
        if abs(v["actual"] - tb.get(f"{v['dept']}|{v['account']}", 0)) > 1.0:
            return False
    return True


@checks.check("holds_the_exception", text="A late entry, an unbudgeted account or a variance over $40K waits for FP&A.", critical=True)
def holds_the_exception(case, out):
    want = case.expected.get("hold")
    if not want:
        return NA
    v = _cell(out, case.expected["cell"])
    return bool(v and v.get("material") and want in v.get("holds", []))


@checks.check("names_the_cause", text="The planted variance gets a line of commentary naming the planted cause.")
def names_the_cause(case, out):
    want = case.expected.get("cause")
    if not want:
        return NA
    v = _cell(out, case.expected["cell"])
    if not v or not v.get("material"):
        return False
    c = v["cause"]
    return c["type"] == want["type"] and c["member"] == want["member"]


@checks.check("no_false_alarm", text="A quiet month produces no commentary and holds nothing.")
def no_false_alarm(case, out):
    if case.group != "control":
        return NA
    return not any(v.get("material") for v in out["variances"])
