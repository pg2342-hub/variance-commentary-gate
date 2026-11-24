# Variance commentary auto-send gate: GO

Agent `agent:gated_drafter`, 25 cases, 1 run(s).

- every rule held on all 1 run(s), no critical failures

## Pass counts by run

| Run | Passed | Critical failures |
|---|---|---|
| 1 | 25 of 25 | 0 |

Agent cost 0.0000 USD, judge cost 0.0000 USD, mean latency 0.9 ms per case.

## Cases

| Case | Group | Result | Failed checks |
|---|---|---|---|
| AWS usage up 22% | routine | 1 of 1 runs |  |
| Two sales hires ahead of plan | routine | 1 of 1 runs |  |
| An engineering role still open | routine | 1 of 1 runs |  |
| Snowflake credits down 30% | routine | 1 of 1 runs |  |
| New data tool with no budget line | routine | 1 of 1 runs |  |
| Warehouse temps up 25% in peak season | routine | 1 of 1 runs |  |
| Sales travel cut by 40% | routine | 1 of 1 runs |  |
| Contract dev hours cut by 60% | routine | 1 of 1 runs |  |
| Salesforce renewal billed a month early | hard | 1 of 1 runs |  |
| Audit firm has not billed yet | hard | 1 of 1 runs |  |
| Euro at 1.19, Europe spend flat in euros | hard | 1 of 1 runs |  |
| Euro at 0.97, Europe spend flat in euros | hard | 1 of 1 runs |  |
| Europe hires while the euro moves | hard | 1 of 1 runs |  |
| Travel invoice posted the day after lock | hold | 1 of 1 runs |  |
| Engineering travel with no budget | hold | 1 of 1 runs |  |
| $55K AWS overage | hold | 1 of 1 runs |  |
| Small legal bill posted after lock | hold | 1 of 1 runs |  |
| Salesforce renewal early, above the review line | hold | 1 of 1 runs |  |
| Extract pulled before the last AP batch | trap | 1 of 1 runs |  |
| Saved search exported a page twice | trap | 1 of 1 runs |  |
| New department code nobody mapped | trap | 1 of 1 runs |  |
| Lines on a new account outside the chart | trap | 1 of 1 runs |  |
| Extract missing one late batch, with AWS up | trap | 1 of 1 runs |  |
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
