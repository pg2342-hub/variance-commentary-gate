# variance-commentary-gate

Demo page: https://pranavgudise.dev/variance-commentary-gate/ (the November draft, the three-close back-test, and both gate reports; no install needed)

Draft each department's monthly budget-vs-actual commentary from NetSuite-style ledger lines, tie every figure to the trial balance, and hold the risky lines for FP&A before anything sends on its own.

Monthly variance commentary is the work an FP&A analyst repeats every close: pull actuals by department and account, compare them with the budget, find the cause of each big gap, and write it up for the budget owner. A draft is only useful if FP&A can trust it without redoing it, so this repo puts the controls first and the writing second.

## What it does

1. **Data checks.** Every department code is in the department map, every account is in the chart, no journal line appears twice, and the extract matches the trial balance for every department and account to the dollar. Any failure stops the draft and says why.
2. **Variances.** Actual against budget for every department and account. A line of commentary is written at $5K and 5% off budget, or for spend with no budget.
3. **One cause per variance**, from the lines behind it: a vendor's spend against its budget line, a vendor with no budget line, headcount against plan, timing (an annual invoice billed in a different month than budgeted, or a monthly one not billed yet), or the euro against the budget rate for the European subsidiary.
4. **The query behind every figure.** Each number in a sentence comes from a listed SuiteQL-style query, and every actual and budget figure is re-run against the trial balance and the budget file before anything sends.
5. **Holds.** Even once commentary sends without approval, three kinds of line wait for FP&A: a variance above $40K, an account with no budget, and any entry posted after the books locked.

```
python -m vcg --sql
[HELD] Customer Success: Travel is $4.8K over budget (+92%), mainly Concur travel at $10.0K against $5.2K budgeted.
        Held for FP&A because 1 line posted after the books locked.
[SEND] Engineering: Cloud hosting is $14.6K over budget (+24%), mainly AWS at $75.6K against $61.0K budgeted.
[HELD] Sales: Software subscriptions is $96.0K over budget (over 10x budget), mainly timing, Salesforce billed $96.0K in November that is budgeted for December.
...
```

## The back-test

Before a live close, `python -m vcg.backtest` reruns three closes (September to November) and compares the drafter's cause with FP&A's for the 20 largest variances in each. The bar is 18 of 20 in every close. Result: 20, 18 and 19 of 20. The changed causes are the ones only FP&A could know from outside the ledger, an invoice coded to the wrong department and a late invoice caught up the next month, which is why the first live closes stay on approval.

## The eval

`eval/` holds 25 planted closes on a made-up freight forwarder (8 departments, a US and a European subsidiary), scored with [golive-gate](https://github.com/pg2342-hub/golive-gate):

| Group | Cases | What a correct draft must do |
|---|---|---|
| routine | 8 | Name the one planted cause (vendor spend, headcount, a new vendor) |
| hard | 5 | Call timing and currency what they are, not a price rise |
| hold | 5 | Keep late entries, unbudgeted accounts and variances over $40K for FP&A |
| trap | 5 | Stop on a bad extract and name the problem |
| control | 2 | Write nothing in a quiet month |

The gate: 24 of 25 overall, every hard, hold, trap and control case, and zero critical failures. The three critical checks are sending on a bad extract, sending a figure that does not tie to the trial balance, and sending a line that should wait for FP&A.

```
golive run eval/golive.yml                               # gated drafter: GO, 25 of 25
golive run eval/golive.yml --agent agent:pivot_drafter   # payee pivot: NO-GO, 8 of 25
python scripts/seed_sweep.py                             # the 25 cases on 7 seeds they were not written with: 175 of 175
```

The payee pivot is the spreadsheet version: department and account pivot, the payee with the biggest gap to budget, and send. It names the right vendor in simple months, but it calls a renewal billed early a price rise, names one employee for a headcount change, misses the euro, and sends bad extracts and late entries.

## Run it

```
pip install -e ".[dev]"
pytest -q
golive run eval/golive.yml
python scripts/build_demo.py && python scripts/demo_chrome.py docs/index.html --repo variance-commentary-gate
```

CI runs ruff, the tests, the gate, the seed sweep and the back-test on every push, and fails if the payee pivot ever passes.

## Limits

- All data is synthetic. The company, its departments, budget, headcount and FP&A's answer key are made up. Vendor names are public software and services used as realistic payees; nothing here reflects their real prices.
- The causes are rules, not a model. This is the deterministic layer an agent's commentary should tie back to, and the gate an agent would have to pass before its commentary sends on its own.
- One cause per variance. A variance with two similar-sized drivers gets the larger one; FP&A's review in the approved closes is where a second driver gets added.
