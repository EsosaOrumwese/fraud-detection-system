# Branch Investigation: Truth vs Bank View

## Branch question

The parent truth-products investigation established that `s4_flow_truth_labels_6B` and `s4_flow_bank_view_6B` cover the same flow universe, but they do not answer the same question. This branch asks:

> How does the institution-facing bank view diverge from supervised truth, and what does that divergence mean for fraud analytics?

The immediate answer is that the bank view is not a clean substitute for truth. It marks nearly twice as many flows as positive as the truth surface does, but only a minority of truth-positive flows are also bank-positive. That disagreement is not noise to be ignored; it is one of the main analytical objects exposed by the truth-products layer.

## Evidence used

Primary report:

- [`truth_products_investigation.md`](../truth_products_investigation.md)

Branch and parent exports:

- [`flow_truth_bank_confusion.csv`](../../../../exports/interface_world/truth_products/flow_truth_bank_confusion.csv)
- [`flow_bank_label_summary.csv`](../../../../exports/interface_world/truth_products/flow_bank_label_summary.csv)
- [`flow_bank_profile.csv`](../../../../exports/interface_world/truth_products/flow_bank_profile.csv)
- [`flow_bank_nulls.csv`](../../../../exports/interface_world/truth_products/flow_bank_nulls.csv)
- [`flow_truth_label_summary.csv`](../../../../exports/interface_world/truth_products/flow_truth_label_summary.csv)
- [`flow_truth_profile.csv`](../../../../exports/interface_world/truth_products/flow_truth_profile.csv)

Related branch:

- [`flow_truth_labels_positive_class_semantics.md`](flow_truth_labels_positive_class_semantics.md)

This branch uses compact exports already produced by the truth-products investigation. It does not rescan the raw `236.7M`-row truth or bank-view surfaces.

## What is being compared

At flow grain, the two surfaces line up physically:

| Surface | Rows | Flows | Positive flag | Label column | Null label rows |
|---|---:|---:|---|---|---:|
| `s4_flow_truth_labels_6B` | `236,691,694` | `236,691,694` | `is_fraud_truth` | `fraud_label` | `0` |
| `s4_flow_bank_view_6B` | `236,691,694` | `236,691,694` | `is_fraud_bank_view` | `bank_label` | `0` |

So the comparison is not fighting a grain mismatch. Both surfaces represent one row per flow under the same pinned run/scenario lineage. The disagreement is semantic and operational, not structural.

`is_fraud_truth` is the supervised truth target. It says what the offline truth authority eventually declares about the flow. `is_fraud_bank_view` is the institution-facing action/judgement view. It says what the bank side sees, confirms, writes off, rejects, or leaves without a case.

That distinction matters because the bank view can be useful even when it disagrees with truth. It can represent operational suspicion, customer dispute outcomes, chargeback posture, institutional confirmation, or case handling. But it is not automatically the target label for supervised fraud modelling.

## Bank view has its own label language

The bank-view distribution is:

| Bank-view flag | Bank label | Flows | Flow share |
|---|---|---:|---:|
| `false` | `BANK_CONFIRMED_LEGIT` | `220,401,202` | `93.1174%` |
| `true` | `BANK_CONFIRMED_FRAUD` | `10,503,772` | `4.4377%` |
| `false` | `NO_CASE_OPENED` | `2,424,522` | `1.0243%` |
| `false` | `CUSTOMER_DISPUTE_REJECTED` | `2,220,851` | `0.9383%` |
| `true` | `CHARGEBACK_WRITTEN_OFF` | `1,141,347` | `0.4822%` |

This is already more operational than the truth surface. The truth surface has `LEGIT`, `ABUSE`, and `FRAUD`. The bank surface has labels that read like institutional outcomes: confirmed legitimate, confirmed fraud, no case opened, customer dispute rejected, and chargeback written off.

That means the bank view should not be flattened too quickly into "the bank's version of fraud." The binary flag is useful, but the label vocabulary tells us the surface is carrying action context. `BANK_CONFIRMED_FRAUD` and `CHARGEBACK_WRITTEN_OFF` both map to `is_fraud_bank_view=true`, but they are not operationally identical. One is confirmation language; the other is loss/write-off language.

## The binary disagreement surface

The flow-level truth/bank matrix is:

| Truth | Bank view | Meaning if bank view is read against truth | Flows | Flow share |
|---|---|---|---:|---:|
| `false` | `false` | true negative | `220,512,654` | `93.1645%` |
| `false` | `true` | bank-positive but truth-negative | `10,238,501` | `4.3257%` |
| `true` | `false` | truth-positive but bank-negative | `4,533,921` | `1.9155%` |
| `true` | `true` | true positive | `1,406,618` | `0.5943%` |

The biggest cell is agreement on non-positive flows. That is expected because the full population is dominated by `LEGIT` truth labels. But the important part of the matrix is not the high overall agreement produced by the majority class. The important part is the two disagreement cells:

- `10,238,501` flows are bank-positive but truth-negative.
- `4,533,921` flows are truth-positive but bank-negative.

Those two cells describe different business problems. Bank-positive/truth-negative flows are potential over-action, false-positive review, customer-friction, investigation cost, or institutional conservatism. Truth-positive/bank-negative flows are potential missed-risk, under-action, delayed recognition, or truth-positive behaviour that did not convert into bank-positive handling.

## If bank view is read as a classifier, it is weak against truth

If we temporarily read `is_fraud_bank_view` as a binary classifier against `is_fraud_truth`, the operating metrics are:

| Metric | Value |
|---|---:|
| Precision | `12.08%` |
| Recall | `23.68%` |
| Specificity | `95.56%` |
| False positive rate | `4.44%` |
| False negative rate | `76.32%` |
| Accuracy | `93.76%` |
| F1 score | `16.00%` |
| Bank-positive rate | `4.92%` |
| Truth-positive rate | `2.51%` |

The high accuracy is mostly a denominator effect. Because `97.49%` of flows are truth-negative, a surface can look accurate at the all-flow level while still doing a poor job on the positive class. Precision tells us that only about `12.08%` of bank-positive flows are truth-positive. Recall tells us that the bank-positive surface captures only about `23.68%` of truth-positive flows.

That is why this branch should not conclude that the bank view is "bad" in a generic sense. It is weak if treated as a classifier. But the bank view may not be intended to be a pure classifier. In the platform's operating context, it is an institutional action surface. It can still be extremely valuable for studying review posture, friction, chargeback/loss outcomes, operational conservatism, dispute handling, and the gap between supervised truth and what the institution acts on.

## Bank view is broader than truth, but not better aligned with truth

The bank surface marks `11,645,119` flows as positive. The truth surface marks `5,940,539` flows as positive. In count terms, the bank-positive population is about `1.96x` the truth-positive population.

That alone could make the bank view look more aggressive or more conservative depending on the lens. But the confusion matrix shows the real structure: the larger bank-positive population is not just "truth positives plus some extras." It contains `10,238,501` truth-negative flows and only `1,406,618` truth-positive flows. Meanwhile, `4,533,921` truth-positive flows remain bank-negative.

So the bank view is not simply broader coverage of the truth-positive class. It is a different judgement surface. It expands action on one side while missing much of the supervised-positive world on the other. This is precisely the kind of divergence that can become a strong stakeholder-facing analytics project, because it creates concrete questions:

- Where is the bank over-acting relative to truth?
- Where is the bank under-acting relative to truth?
- Are bank-positive/truth-negative flows concentrated by channel, country, amount, merchant, case path, or time?
- Are truth-positive/bank-negative flows mainly `ABUSE`, explicit `FRAUD`, or some operating segment not being escalated?
- Does case lifecycle explain the disagreement?

Those questions are more valuable than asking whether the bank view is "right" or "wrong" in isolation.

## What this means for later analytics

For supervised modelling, `is_fraud_truth` should remain the target unless the project brief explicitly asks for bank-action prediction. The bank view can be a comparison surface, an operational outcome, or a downstream label depending on the analytical question, but it should not silently replace truth.

For stakeholder analytics, the disagreement itself is likely useful. A risk team may care about truth-positive/bank-negative flows because they point to missed or under-handled risk. An operations or customer-experience team may care about bank-positive/truth-negative flows because they point to possible over-escalation or customer friction. A finance/loss team may care about `CHARGEBACK_WRITTEN_OFF` separately because it is closer to realized institutional cost than a generic bank-positive flag.

For realism assessment, this branch does not create the same concern as the sparse upstream `fraud_flag`. The truth/bank disagreement is not inherently unrealistic. Real financial institutions often have disagreement between eventual ground truth, operational action, customer disputes, chargebacks, and case handling. The concern would only arise if later branches show that the disagreement is mechanically patterned in an implausible way, or if the label meanings are too synthetic to support stakeholder claims.

## Working conclusion

`s4_flow_bank_view_6B` is not a substitute for `s4_flow_truth_labels_6B`. It is a separate institutional judgement surface operating over the same flow universe.

Read as a classifier, bank view has low precision and low recall against truth. Read as an operational surface, the same disagreement becomes analytically valuable: it exposes possible over-action, missed truth-positive behaviour, chargeback/write-off posture, and the gap between truth and institutional handling.

For later project briefs, this branch gives us a strong candidate area: truth/bank divergence analysis. The data can support stakeholder-facing questions about operational action quality and risk handling, provided we keep the target definition clear and do not present bank view as ground truth.
