# Branch Investigation: Flow Truth Labels and Positive-Class Semantics

## Branch question

The parent truth-products investigation established that `s4_flow_truth_labels_6B` is the authoritative supervised label surface at flow grain. This branch focuses only on that surface and asks:

> What does the flow truth label actually say about the positive class, and how should that shape fraud analytics?

The immediate answer is that the truth surface does not describe the same narrow world as the sparse upstream `fraud_flag`. It defines a much broader positive judgement space dominated by `ABUSE`, with a very small explicitly labelled `FRAUD` class. That distinction is central to whether the current extract is usable for realistic fraud analytics.

## Evidence used

Primary report:

- [`truth_products_investigation.md`](../truth_products_investigation.md)

Branch exports:

- [`flow_truth_label_summary.csv`](../../../../exports/interface_world/truth_products/flow_truth_label_summary.csv)
- [`flow_truth_anchor_reconciliation.csv`](../../../../exports/interface_world/truth_products/flow_truth_anchor_reconciliation.csv)
- [`flow_truth_profile.csv`](../../../../exports/interface_world/truth_products/flow_truth_profile.csv)
- [`flow_truth_nulls.csv`](../../../../exports/interface_world/truth_products/flow_truth_nulls.csv)

Related reports:

- [`behavioural_streams_investigation.md`](../../behavioural_streams/behavioural_streams_investigation.md)
- [`baseline_vs_fraud_overlay_contract.md`](../../behavioural_streams/branches/baseline_vs_fraud_overlay_contract.md)

This branch uses compact exports already produced by the truth-products investigation. It does not rescan the raw `236.7M`-row truth surface.

## What the surface is allowed to answer

`s4_flow_truth_labels_6B` is a flow-grain supervised label surface. Its row count is the flow count:

| Metric | Value |
|---|---:|
| Rows | `236,691,694` |
| Flows | `236,691,694` |
| Truth-positive flows | `5,940,539` |
| Truth-negative flows | `230,751,155` |
| Distinct truth labels | `3` |
| Null `fraud_label` rows | `0` |

So this surface is clean as a label table: one row per flow, no missing flow IDs, no missing truth flags, no missing fraud labels, and one pinned run/scenario lineage. It is the right starting point when the analytical question is supervised ground truth.

It is not the right surface for live decision-time features, campaign membership, or case operations. Those belong to other surfaces. Here we are reading the eventual truth judgement attached to each flow.

## The positive class is broad, but its language is not simple

The truth label distribution is:

| Truth flag | Fraud label | Flows | Flow share |
|---|---|---:|---:|
| `false` | `LEGIT` | `230,751,155` | `97.4902%` |
| `true` | `ABUSE` | `5,938,116` | `2.5088%` |
| `true` | `FRAUD` | `2,423` | `0.0010%` |

At the binary level, the truth-positive rate is about `2.51%`. That is radically different from the sparse upstream fraud overlay, which marked only `7,132` exact fraud flows.

But the positive class is not semantically uniform. Almost every truth-positive flow is labelled `ABUSE`; only `2,423` flows are labelled `FRAUD`. In share terms, `ABUSE` represents more than `99.95%` of truth-positive flows, while explicit `FRAUD` is a tiny part of the positive truth surface.

That means stakeholder language matters. If we report `2.51%` as "fraud rate" without qualification, we would be collapsing abuse and fraud into one business term. If the stakeholder question is broad risk or unwanted behaviour, the binary positive class may be appropriate. If the question is explicit fraud loss, chargeback fraud, or criminal fraud, the `FRAUD` label alone is much smaller.

## Truth is not the same as the upstream fraud overlay

The reconciliation against the post-overlay flow anchor is:

| Truth flag | Anchor `fraud_flag` | Flows | Flow share |
|---|---|---:|---:|
| `false` | `false` | `230,751,155` | `97.4902%` |
| `true` | `false` | `5,933,407` | `2.5068%` |
| `true` | `true` | `7,132` | `0.0030%` |
| `false` | `true` | `0` | `0.0000%` |

This resolves part of the realism concern raised in the behavioural-stream investigation, but not all of it.

It resolves the label-surface question: the final supervised truth world is not only the `7,132` overlay-marked flows. The truth process declares `5,940,539` positive flows. So if our aim is supervised modelling or flow-level truth analytics, the extract is not limited to a `0.003%` positive class.

It does not resolve the fraud-overlay calibration concern. The upstream `fraud_flag` remains extremely sparse and low-impact as a campaign/context marker. The truth surface is telling us that most positive truth judgement exists outside that explicit overlay marker. Therefore, the right conclusion is not "the fraud concern disappears." The right conclusion is:

- `fraud_flag` is not the final label.
- `is_fraud_truth` is the final supervised binary label.
- the semantics of that binary label are dominated by `ABUSE`, not explicit `FRAUD`.

## What `fraud_flag` now means in light of truth

The anchor `fraud_flag` has perfect containment inside truth positives in this extract:

- truth-negative and `fraud_flag = true`: `0` flows
- truth-positive and `fraud_flag = true`: `7,132` flows

So the overlay marker is not producing false positives against the truth surface. Every overlay-marked flow is truth-positive.

But the reverse is not true. The truth surface has `5,933,407` positive flows with `fraud_flag = false`. That means `fraud_flag` is a narrow positive-context marker, not a coverage-complete fraud label.

For analytics, the implication is direct:

1. Use `is_fraud_truth` when calculating supervised positive rate, recall, precision, model target prevalence, or truth-based portfolio metrics.

2. Use `fraud_flag` when the question is about the explicit upstream campaign/overlay mechanism.

3. Do not use `fraud_flag` as a shortcut for truth, because it would miss almost all truth positives.

## Realism read from this branch

This branch changes our provisional fitness read.

Before truth products, the behavioural stream made the fraud world look under-seeded: only `7,132` fraud flows, low median amount, and tiny portfolio amount impact. After reading flow truth, the supervised positive class is no longer sparse in that same way. A `2.51%` flow-level positive rate is substantial enough to support modelling and labelled analytics in count terms.

However, the class semantics remain a concern for stakeholder-facing fraud analytics:

- `ABUSE` dominates the positive class.
- explicit `FRAUD` is only `2,423` flows.
- the upstream campaign overlay is only a tiny subset of truth positives.

So the data may be fit for broad abuse/fraud-risk analytics, but it is not yet proven fit for explicit fraud-loss analytics. Any stakeholder-facing work must decide whether the business question is about all truth-positive unwanted behaviour or only the explicit `FRAUD` label.

## Working conclusion

`s4_flow_truth_labels_6B` is the right flow-grain supervised label authority. It is clean, complete, and broad enough to support positive-class analytics at scale.

But the positive class must be named carefully. The binary `is_fraud_truth` flag mostly means `ABUSE` in this run, not explicit `FRAUD`. The upstream `fraud_flag` is a narrow campaign marker contained inside truth positives, while the truth surface expands the positive class far beyond that marker.

For the wider fitness-for-fraud-analytics question, this branch softens the earlier "fraud is too sparse" concern only if we define the target as broad truth-positive abuse/fraud risk. It does not by itself prove the extract is realistic for fraud-loss, chargeback-fraud, or explicit fraud-only stakeholder conclusions.
