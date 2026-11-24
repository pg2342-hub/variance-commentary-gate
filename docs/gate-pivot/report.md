# Variance commentary auto-send gate: NO-GO

Agent `agent:pivot_drafter`, 25 cases, 1 run(s).

- run 1: 15 critical failure(s): holds_the_exception on case k01, holds_the_exception on case k02, holds_the_exception on case k03, holds_the_exception on case k04, holds_the_exception on case k05, stops_on_bad_data on case t01, every_figure_ties on case t01, stops_on_bad_data on case t02, every_figure_ties on case t02, stops_on_bad_data on case t03, every_figure_ties on case t03, stops_on_bad_data on case t04, every_figure_ties on case t04, stops_on_bad_data on case t05, every_figure_ties on case t05
- run 1: overall passed 8 of 25, needs 24 (no-go)
- run 1: hard causes passed 0 of 5, needs 5 (no-go)
- run 1: holds passed 0 of 5, needs 5 (no-go)
- run 1: data traps passed 0 of 5, needs 5 (no-go)

## Pass counts by run

| Run | Passed | Critical failures |
|---|---|---|
| 1 | 8 of 25 | 15 |

Agent cost 0.0000 USD, judge cost 0.0000 USD, mean latency 0.8 ms per case.

## Cases

| Case | Group | Result | Failed checks |
|---|---|---|---|
| AWS usage up 22% | routine | 1 of 1 runs |  |
| Two sales hires ahead of plan | routine | 0 of 1 runs | names_the_cause |
| An engineering role still open | routine | 0 of 1 runs | names_the_cause |
| Snowflake credits down 30% | routine | 1 of 1 runs |  |
| New data tool with no budget line | routine | 1 of 1 runs |  |
| Warehouse temps up 25% in peak season | routine | 1 of 1 runs |  |
| Sales travel cut by 40% | routine | 1 of 1 runs |  |
| Contract dev hours cut by 60% | routine | 1 of 1 runs |  |
| Salesforce renewal billed a month early | hard | 0 of 1 runs | names_the_cause |
| Audit firm has not billed yet | hard | 0 of 1 runs | names_the_cause |
| Euro at 1.19, Europe spend flat in euros | hard | 0 of 1 runs | names_the_cause |
| Euro at 0.97, Europe spend flat in euros | hard | 0 of 1 runs | names_the_cause |
| Europe hires while the euro moves | hard | 0 of 1 runs | names_the_cause |
| Travel invoice posted the day after lock | hold | 0 of 1 runs | holds_the_exception |
| Engineering travel with no budget | hold | 0 of 1 runs | holds_the_exception |
| $55K AWS overage | hold | 0 of 1 runs | holds_the_exception |
| Small legal bill posted after lock | hold | 0 of 1 runs | holds_the_exception |
| Salesforce renewal early, above the review line | hold | 0 of 1 runs | holds_the_exception, names_the_cause |
| Extract pulled before the last AP batch | trap | 0 of 1 runs | every_figure_ties, names_the_problem, stops_on_bad_data |
| Saved search exported a page twice | trap | 0 of 1 runs | every_figure_ties, names_the_problem, stops_on_bad_data |
| New department code nobody mapped | trap | 0 of 1 runs | every_figure_ties, names_the_problem, stops_on_bad_data |
| Lines on a new account outside the chart | trap | 0 of 1 runs | every_figure_ties, names_the_problem, stops_on_bad_data |
| Extract missing one late batch, with AWS up | trap | 0 of 1 runs | every_figure_ties, names_the_problem, stops_on_bad_data |
| A quiet month | control | 1 of 1 runs |  |
| A quiet month, euro at budget rate | control | 1 of 1 runs |  |

## Checks

| Check | Critical | Text |
|---|---|---|
| stops_on_bad_data | yes | A data problem stops the draft; a clean extract produces one. |
| names_the_problem |  | The draft names the planted data problem. |
| every_figure_ties | yes | Every actual in a sent draft equals the ledger's trial balance to the dollar. |
| holds_the_exception | yes | A late entry, an unbudgeted account or a variance over $40K waits for FP&A. |
| names_the_cause |  | The planted variance gets a line of commentary naming the planted cause. |
| no_false_alarm |  | A quiet month produces no commentary and holds nothing. |
