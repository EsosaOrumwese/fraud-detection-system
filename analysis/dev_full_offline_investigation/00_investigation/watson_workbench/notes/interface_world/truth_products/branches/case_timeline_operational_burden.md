# Branch Investigation: Case Timeline and Operational Burden

## Branch question

The parent truth-products investigation established that `s4_case_timeline_6B` is the post-decision operational lifecycle surface. This branch asks:

> What kind of case world does the platform expose, and what operational burden does that case world imply?

The immediate answer is that the case timeline is broad, selective, and mostly shallow. It covers about `9.61%` of all flows, produces `59.78M` case events across `22.75M` cases, and mostly consists of two-event open/close lifecycles. But the burden is not evenly distributed across the truth/bank judgement space: bank-positive/truth-negative flows and true-positive aligned flows are fully represented in cases, while only a small share of true-negative aligned flows enter the case world.

## Evidence used

Primary report:

- [`truth_products_investigation.md`](../truth_products_investigation.md)

Branch and parent exports:

- [`case_timeline_profile.csv`](../../../../exports/interface_world/truth_products/case_timeline_profile.csv)
- [`case_event_type_summary.csv`](../../../../exports/interface_world/truth_products/case_event_type_summary.csv)
- [`case_length_summary.csv`](../../../../exports/interface_world/truth_products/case_length_summary.csv)
- [`case_truth_bank_reconciliation.csv`](../../../../exports/interface_world/truth_products/case_truth_bank_reconciliation.csv)
- [`case_timeline_nulls.csv`](../../../../exports/interface_world/truth_products/case_timeline_nulls.csv)
- [`case_coverage_by_truth_bank_cell.csv`](../../../../exports/interface_world/truth_products/branches/case_timeline_operational_burden/case_coverage_by_truth_bank_cell.csv)
- [`case_coverage_by_truth_bank_label_pair.csv`](../../../../exports/interface_world/truth_products/branches/case_timeline_operational_burden/case_coverage_by_truth_bank_label_pair.csv)

Related branch:

- [`truth_vs_bank_view.md`](truth_vs_bank_view.md)

The branch uses compact exports from the truth-products investigation and one derived coverage aggregate, exported in two views, that joins those compact case counts to the label-pair anatomy from `truth_vs_bank_view`. It does not rescan the raw case timeline.

## What the case timeline is allowed to answer

`s4_case_timeline_6B` is not a label table and not a live decision input. It is an offline operational history surface. Its grain is one row per case event:

| Metric | Value |
|---|---:|
| Case timeline rows | `59,775,740` |
| Cases | `22,752,610` |
| Represented flows | `22,752,610` |
| Case event types | `6` |
| Case event sequence range | `0` to `5` |
| Average events per case | `2.63` |
| Share of all flows represented in cases | `9.61%` |

The surface is clean at required-field level. There are no nulls in `case_id`, `case_event_seq`, `flow_id`, `case_event_type`, `ts_utc`, or lineage fields in the compact null profile.

The case timeline therefore answers operational questions: which flows entered case history, what events were attached to them, how deep the lifecycle became, and how much post-decision work exists. It should not be used as a shortcut for ground truth. Case presence means operational representation, not automatic fraud truth.

## Case time extends beyond transaction time

The timeline runs from `2026-01-01T00:00:00.694988Z` to `2026-08-13T08:47:09.708142Z`, a span of about `224.37` days. This is much longer than the January-March operating transaction window we have been using for the interface world.

That is not a defect by itself. Cases are post-decision operational objects. A transaction may occur in January, February, or March, but dispute handling, chargeback initiation, chargeback decision, and closure can extend well after the original authorization event. This is why the case timeline belongs to offline operational analytics rather than live decision-time payloads.

The key caution is reporting-window discipline. If we later calculate case workload by calendar date, we must not mix transaction-window interpretation with case-event-window interpretation. A case event in August does not mean August transaction traffic exists in the interface pack. It means a case lifecycle continued into August.

## Event grammar of the case lifecycle

The event-type distribution is:

| Case event type | Rows | Cases | Case event sequence | Row share | Case share |
|---|---:|---:|---|---:|---:|
| `CASE_OPENED` | `22,752,610` | `22,752,610` | `0` | `38.0633%` | `100.0000%` |
| `CASE_CLOSED` | `22,752,610` | `22,752,610` | `5` | `38.0633%` | `100.0000%` |
| `CUSTOMER_DISPUTE_FILED` | `5,121,378` | `5,121,378` | `2` | `8.5677%` | `22.5090%` |
| `CHARGEBACK_INITIATED` | `3,362,198` | `3,362,198` | `3` | `5.6247%` | `14.7772%` |
| `CHARGEBACK_DECISION` | `3,362,198` | `3,362,198` | `4` | `5.6247%` | `14.7772%` |
| `DETECTION_EVENT_ATTACHED` | `2,424,746` | `2,424,746` | `1` | `4.0564%` | `10.6570%` |

Every represented case has an open and close event. That gives the surface a complete lifecycle frame: cases do not appear as dangling openings without closure in this extract.

The middle events are selective. Only `10.66%` of cases attach a detection event. `22.51%` have a customer dispute filed. `14.78%` progress into chargeback initiation and chargeback decision. So the case timeline is not a uniform six-step workflow for every case. It is a common open/close shell with optional operational stages in the middle.

That matters for burden analysis. A row count of `59.78M` does not mean `59.78M` separate cases. It means `22.75M` case objects generating multiple operational events. The work profile is partly case count and partly lifecycle depth.

## Case depth is broad but mostly shallow

Case length distribution:

| Case events | Cases | Case share |
|---:|---:|---:|
| `2` | `16,666,405` | `73.2505%` |
| `3` | `2,579,827` | `11.3386%` |
| `4` | `144,180` | `0.6337%` |
| `5` | `2,046,459` | `8.9944%` |
| `6` | `1,315,739` | `5.7828%` |

The dominant lifecycle has exactly two events. These are cases with the open/close frame and no additional middle events. That is `73.25%` of all cases.

The deeper case population is smaller but still operationally material. `5`-event and `6`-event cases together represent `3,362,198` cases, or `14.78%` of the case population. That number lines up with the chargeback event counts, which suggests that chargeback progression is the main driver of deeper case lifecycles.

So the case world is not "small but complicated." It is large and mostly shallow, with a meaningful chargeback-depth minority. That distinction matters for project framing: a workload project could focus on volume containment and triage, while a loss/project branch could focus on the smaller but deeper chargeback path.

## Case coverage across truth/bank judgement cells

The case timeline covers `22,752,610` flows out of `236,691,694` total flows. The broad coverage rate is `9.61%`, but the coverage is very different by truth/bank cell:

| Truth/bank cell | Total flows | Case flows | Case coverage |
|---|---:|---:|---:|
| bank-positive/truth-negative | `10,238,501` | `10,238,501` | `100.0000%` |
| true-positive alignment | `1,406,618` | `1,406,618` | `100.0000%` |
| truth-positive/bank-negative | `4,533,921` | `3,115,199` | `68.7087%` |
| true-negative alignment | `220,512,654` | `7,992,292` | `3.6244%` |

This is the key burden finding of the branch. The case world is selective, but it is not uniformly selective. Every bank-positive/truth-negative flow is represented in the case timeline. Every true-positive aligned flow is represented too. Most truth-positive/bank-negative flows are represented, while only a small fraction of true-negative aligned flows enter cases.

That shape gives operational meaning to the truth/bank disagreement from the previous branch. The large over-action cell, `LEGIT / BANK_CONFIRMED_FRAUD`, is not just a label disagreement sitting outside operations; it is fully case-represented. That makes it a real candidate for customer-friction, investigation burden, false-positive review, or bank-action-quality analytics.

The true-positive aligned cell is also fully case-represented, which makes sense operationally: when truth and bank view both agree positively, the case surface carries the handling trail.

The truth-positive/bank-negative cell is more complex. `68.71%` of those flows still appear in case history, even though the bank flag is negative. This is where the labels need careful reading. Bank-negative does not mean operationally invisible. It can include `NO_CASE_OPENED` and `CUSTOMER_DISPUTE_REJECTED`, and those labels are not equivalent to absence from the case timeline.

## Label-pair burden inside cases

The largest case-flow label pairs are:

| Truth label | Bank label | Cell | Total flows | Case flows | Case coverage |
|---|---|---|---:|---:|---:|
| `LEGIT` | `BANK_CONFIRMED_FRAUD` | bank-positive/truth-negative | `10,232,664` | `10,232,664` | `100.0000%` |
| `LEGIT` | `BANK_CONFIRMED_LEGIT` | true-negative alignment | `220,401,202` | `7,880,840` | `3.5757%` |
| `ABUSE` | `CUSTOMER_DISPUTE_REJECTED` | truth-positive/bank-negative | `2,109,342` | `2,109,342` | `100.0000%` |
| `ABUSE` | `CHARGEBACK_WRITTEN_OFF` | true-positive alignment | `1,135,282` | `1,135,282` | `100.0000%` |
| `ABUSE` | `NO_CASE_OPENED` | truth-positive/bank-negative | `2,423,574` | `1,005,731` | `41.4978%` |

This shows that the operational burden is strongly tied to the label-pair anatomy from `truth_vs_bank_view`.

The largest case group is `LEGIT / BANK_CONFIRMED_FRAUD`, with `10.23M` case flows. That is the main over-action burden candidate.

The second-largest group is `LEGIT / BANK_CONFIRMED_LEGIT`, with `7.88M` case flows, even though that is only `3.58%` of all flows in that label pair. This matters because large populations can create large operational counts from low coverage rates. True-negative aligned case flows are not the dominant analytical concern by coverage rate, but they still represent substantial case volume.

The `ABUSE / CUSTOMER_DISPUTE_REJECTED` and `ABUSE / CHARGEBACK_WRITTEN_OFF` groups show that truth-positive abuse risk splits into different operational paths. Some abuse-positive flows are rejected through customer-dispute handling, while others become write-offs. Those are different stakeholder stories.

The `ABUSE / NO_CASE_OPENED` row is a semantic caution. `NO_CASE_OPENED` is a bank label, but `1,005,731` flows with that label still appear in `s4_case_timeline_6B`. Therefore, in this interface world, `NO_CASE_OPENED` must not be interpreted naively as "there is no row in the case timeline." It is a bank-view label, while the case timeline is a separate operational surface.

## Operational reading

The case timeline turns truth/bank disagreement into workload. It does not only tell us that truth and bank view diverge; it tells us which parts of that divergence are carried into operational history.

Three burden lanes now emerge:

1. Over-action burden: `LEGIT / BANK_CONFIRMED_FRAUD` is fully case-represented and carries `10.23M` case flows. This is the strongest candidate for later false-positive, customer-friction, review-load, or bank-action-quality analysis.

2. Abuse handling burden: `ABUSE / CUSTOMER_DISPUTE_REJECTED`, `ABUSE / CHARGEBACK_WRITTEN_OFF`, and `ABUSE / NO_CASE_OPENED` split the truth-positive abuse world across rejected disputes, write-offs, and bank-negative/no-case-labelled handling. This is a candidate for risk operations and abuse-resolution analysis.

3. Baseline case volume: even a low case coverage rate among `LEGIT / BANK_CONFIRMED_LEGIT` flows creates `7.88M` case flows because the underlying legitimate population is huge. This is a denominator warning: operational burden can be large even when coverage is small.

This branch therefore does not just describe the case timeline as a table. It gives us a practical interpretation of where operational work appears to be concentrated.

## Working conclusion

`s4_case_timeline_6B` is the offline operational history surface. It is broad enough to matter, selective enough to require denominator discipline, and structured enough to support later stakeholder-facing operational analytics.

The case world is mostly shallow: most cases have only open and close events. But the volume is large, and the deeper chargeback path is still material. The timeline also extends months beyond the transaction window, so case-event time must be kept separate from transaction-event time.

The strongest analytical lead is operational burden from truth/bank divergence. `LEGIT / BANK_CONFIRMED_FRAUD` is the largest case-flow group and is fully represented in cases. Truth-positive abuse flows split across rejected disputes, write-offs, and no-case-labelled handling. That gives us a defensible path toward later project briefs on false-positive burden, case workload, chargeback/write-off posture, and risk handling quality.
