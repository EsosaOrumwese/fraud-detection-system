# Truth Products Investigation

## What these surfaces are

The `s4_*` truth products are the offline judgement layer of the interface world.

The interface pack exposes four truth-product datasets:

- `s4_flow_truth_labels_6B`
- `s4_flow_bank_view_6B`
- `s4_event_labels_6B`
- `s4_case_timeline_6B`

They are not traffic and they are not live decision inputs. They are the surfaces that tell us what became true about the post-overlay flow world after labelling, institutional judgement, and case lifecycle construction.

That distinction matters because the behavioural streams and context surfaces tell us what happened in the operating platform, while the truth products tell us how the platform can later learn from, evaluate, audit, and reconstruct those flows.

## References and evidence

Contract references:

- [`docs/model_spec/data-engine/interface_pack/data_engine_interface.md`](../../../../../../../docs/model_spec/data-engine/interface_pack/data_engine_interface.md)
- [`docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`](../../../../../../../docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml)
- [`docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`](../../../../../../../docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml)
- [`docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`](../../../../../../../docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml)

Pinned data surfaces:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s4_flow_truth_labels_6B`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s4_flow_truth_labels_6B)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s4_flow_bank_view_6B`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s4_flow_bank_view_6B)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s4_event_labels_6B`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s4_event_labels_6B)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s4_case_timeline_6B`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s4_case_timeline_6B)

Support script and exports:

- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/scratch/analyze_truth_products.py`](../../../scratch/analyze_truth_products.py)
- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/interface_world/truth_products`](../../../exports/interface_world/truth_products)

## Contract read before touching the data

The interface contract places all `s4_*` products in the `truth_products` role. The binding posture is:

- truth products are canonical labels/case truth products
- truth products are read for supervision, evaluation, case tooling, and offline analysis
- truth products must not be treated as live traffic
- truth products must never be used for live decisions

The join map is also specific:

- `s4_event_labels_6B` joins to `s3_event_stream_with_fraud_6B` by `seed`, `manifest_fingerprint`, `scenario_id`, `flow_id`, `event_seq`
- `s4_flow_truth_labels_6B` joins to `s3_flow_anchor_with_fraud_6B` by `seed`, `manifest_fingerprint`, `scenario_id`, `flow_id`
- `s4_flow_bank_view_6B` joins to `s3_flow_anchor_with_fraud_6B` by `seed`, `manifest_fingerprint`, `scenario_id`, `flow_id`
- `s4_case_timeline_6B` is case-centric and joins through `case_id`, with `flow_id` present as the flow carried by each case event

This gives us three analytical objects, not one:

- ground truth: what the synthetic truth process says the flow really is
- bank view: what the institution sees or acts on
- case lifecycle: the post-decision operational trail

## Physical shape

The pinned truth-product group has this shape:

| Surface | Rows | Grain | Files |
|---|---:|---|---:|
| `s4_flow_truth_labels_6B` | `236,691,694` | one row per flow | `1,302` |
| `s4_flow_bank_view_6B` | `236,691,694` | one row per flow | `1,302` |
| `s4_event_labels_6B` | `473,383,388` | one row per event | `1` |
| `s4_case_timeline_6B` | `59,775,740` | one row per case event | `1,302` |

The shape is coherent with the earlier stream/context findings:

- there are `236,691,694` flows
- there are `473,383,388` event rows because each flow has two authorization events
- flow truth and bank view both cover the full flow universe
- case timeline is selective, covering only flows that enter a case lifecycle

All four truth surfaces have clean required fields: no nulls in IDs, labels, lineage fields, timestamps where present, or case event fields.

## Flow truth labels

`s4_flow_truth_labels_6B` is the ground-truth surface at flow grain.

Observed label distribution:

| Truth flag | Fraud label | Flows | Flow share |
|---|---|---:|---:|
| `false` | `LEGIT` | `230,751,155` | `97.4902%` |
| `true` | `ABUSE` | `5,938,116` | `2.5088%` |
| `true` | `FRAUD` | `2,423` | `0.0010%` |

So the truth surface is not simply a copy of the explicit fraud-campaign overlay. It declares a much broader positive class than the `7,132` campaign-marked flows we saw in `s3_flow_anchor_with_fraud_6B`.

The reconciliation against the post-overlay anchor is:

| Truth flag | Anchor `fraud_flag` | Flows | Flow share |
|---|---|---:|---:|
| `false` | `false` | `230,751,155` | `97.4902%` |
| `true` | `false` | `5,933,407` | `2.5068%` |
| `true` | `true` | `7,132` | `0.0030%` |
| `false` | `true` | `0` | `0.0000%` |

This is an important investigative finding. `fraud_flag` in the post-overlay anchor is not the same thing as `is_fraud_truth` in the truth product. The anchor flag marks the explicit overlay/campaign surface. The truth product expands the judgement space into `ABUSE` and `FRAUD`, with `ABUSE` being the dominant positive class.

That means downstream analysis should not use `fraud_flag` as the final label. It is an upstream context marker. The final supervised label surface is `s4_flow_truth_labels_6B`.

## Bank view

`s4_flow_bank_view_6B` is the institution-facing classification of each flow.

Observed bank-view distribution:

| Bank-view flag | Bank label | Flows | Flow share |
|---|---|---:|---:|
| `false` | `BANK_CONFIRMED_LEGIT` | `220,401,202` | `93.1174%` |
| `true` | `BANK_CONFIRMED_FRAUD` | `10,503,772` | `4.4377%` |
| `false` | `NO_CASE_OPENED` | `2,424,522` | `1.0243%` |
| `false` | `CUSTOMER_DISPUTE_REJECTED` | `2,220,851` | `0.9383%` |
| `true` | `CHARGEBACK_WRITTEN_OFF` | `1,141,347` | `0.4822%` |

The bank sees more positive flows than the truth surface declares:

- truth-positive flows: `5,940,539`
- bank-positive flows: `11,645,119`

So the bank view is not a clean mirror of ground truth. It is a second judgement layer, which is exactly what we would expect in a fraud platform: an institution can act on suspicious or disputed flows even when the underlying truth label says otherwise, and it can also miss true-positive flows.

## Truth versus bank view

The flow-level truth/bank matrix is:

| Truth | Bank view | Flows | Flow share |
|---|---|---:|---:|
| `false` | `false` | `220,512,654` | `93.1645%` |
| `false` | `true` | `10,238,501` | `4.3257%` |
| `true` | `false` | `4,533,921` | `1.9155%` |
| `true` | `true` | `1,406,618` | `0.5943%` |

This gives us the first full offline evaluation object in the interface world:

- true positives: `1,406,618`
- false positives: `10,238,501`
- false negatives: `4,533,921`
- true negatives: `220,512,654`

The bank view has low agreement with truth positives if read as a classifier:

- precision against truth: about `12.08%`
- recall against truth: about `23.68%`

This should not immediately be read as a defect. At this stage, the bank view is an institutional action surface, not necessarily a model score. The point is that the interface pack preserves the difference between what is true, what the institution acts on, and what later becomes a case. That difference is exactly where supervision, model evaluation, operational review, and stakeholder reporting can begin.

## Event labels

`s4_event_labels_6B` is the event-grain label surface keyed to the post-overlay event stream.

It has:

- rows: `473,383,388`
- flows: `236,691,694`
- event sequence values: `0` and `1`
- truth-positive event rows: `11,881,078`
- bank-positive event rows: `23,290,238`

By event sequence:

| Event sequence | Rows | Truth-positive rows | Bank-positive rows |
|---:|---:|---:|---:|
| `0` | `236,691,694` | `5,940,539` | `11,645,119` |
| `1` | `236,691,694` | `5,940,539` | `11,645,119` |

This is the event-level duplication of the flow-level judgement. Each labelled flow appears on both authorization events. That is why the event-level positive counts are exactly twice the flow-level positive counts.

The key reconciliation is also exact:

| Surface | Rows | Flows | Event sequence values | Event-key hash |
|---|---:|---:|---:|---|
| `s3_event_stream_with_fraud_6B` | `473,383,388` | `236,691,694` | `2` | same |
| `s4_event_labels_6B` | `473,383,388` | `236,691,694` | `2` | same |

So the event label surface is not inventing a new event universe. It labels the same post-overlay event-key universe.

## Case timeline

`s4_case_timeline_6B` is the operational lifecycle surface.

Observed profile:

- rows: `59,775,740`
- cases: `22,752,610`
- represented flows: `22,752,610`
- event types: `6`
- case event sequence range: `0` to `5`
- timeline span: `2026-01-01T00:00:00.694988Z` to `2026-08-13T08:47:09.708142Z`

The case timeline extends far beyond the January-March traffic window. That is not a traffic-window error. It is the case lifecycle continuing after the underlying transaction event. This is another reason the `s4_*` group is offline-only.

Case event types:

| Case event type | Rows | Case event sequence | Row share |
|---|---:|---|---:|
| `CASE_OPENED` | `22,752,610` | `0` | `38.0633%` |
| `CASE_CLOSED` | `22,752,610` | `5` | `38.0633%` |
| `CUSTOMER_DISPUTE_FILED` | `5,121,378` | `2` | `8.5677%` |
| `CHARGEBACK_INITIATED` | `3,362,198` | `3` | `5.6247%` |
| `CHARGEBACK_DECISION` | `3,362,198` | `4` | `5.6247%` |
| `DETECTION_EVENT_ATTACHED` | `2,424,746` | `1` | `4.0564%` |

Case length distribution:

| Case events | Cases | Case share |
|---:|---:|---:|
| `2` | `16,666,405` | `73.2505%` |
| `3` | `2,579,827` | `11.3386%` |
| `4` | `144,180` | `0.6337%` |
| `5` | `2,046,459` | `8.9944%` |
| `6` | `1,315,739` | `5.7828%` |

The case world is therefore broad but mostly shallow. Every represented case has an open and close event, while only subsets go through detection attachment, customer dispute, chargeback initiation, and chargeback decision.

## Case flows versus truth and bank view

The case timeline covers `22,752,610` flows, which is about `9.61%` of all flows.

The largest case-flow groups are:

| Truth | Bank view | Truth label | Bank label | Case flows |
|---|---|---|---|---:|
| `false` | `true` | `LEGIT` | `BANK_CONFIRMED_FRAUD` | `10,232,664` |
| `false` | `false` | `LEGIT` | `BANK_CONFIRMED_LEGIT` | `7,880,840` |
| `true` | `false` | `ABUSE` | `CUSTOMER_DISPUTE_REJECTED` | `2,109,342` |
| `true` | `true` | `ABUSE` | `CHARGEBACK_WRITTEN_OFF` | `1,135,282` |
| `true` | `false` | `ABUSE` | `NO_CASE_OPENED` | `1,005,731` |

This confirms that case creation is not simply "all and only truth-positive flows." Cases include:

- false-positive institutional suspicion
- truth-positive flows missed or rejected by bank view
- true-positive flows that progress into chargeback/write-off outcomes
- legit flows that still enter the case lifecycle

So the case timeline is not just a label table. It is the operational trace of institutional handling.

## Leads exposed by this investigation

1. `s4_flow_truth_labels_6B` is the authoritative supervised label surface at flow grain. It should take precedence over `fraud_flag` when the analytical question is ground truth.

2. `fraud_flag` in the post-overlay anchor is a sparse campaign/context marker, not the full truth label. It marks `7,132` flows, while truth positives cover `5,940,539` flows.

3. The dominant truth-positive class is `ABUSE`, not `FRAUD`. That distinction will matter when we later frame modelling, detection, and stakeholder language.

4. The bank view is a separate institutional judgement surface. Its disagreement with truth is not noise to erase; it is one of the main analytical objects.

5. Event labels duplicate flow labels onto both authorization events. They are useful for event-stream supervision and evaluation, while flow labels remain the cleaner flow-grain target.

6. Case timeline is offline operational history. Its dates extend into August because case handling continues after the January-March transaction window.

7. Case coverage is broad but selective: `22,752,610` case flows out of `236,691,694` total flows.

8. Most cases are shallow two-event lifecycles, but a meaningful minority progress through dispute and chargeback stages.

## Working conclusion

The truth-product group is where the interface world becomes analytically evaluable.

Before this point, we had traffic, context, and fraud-overlay markers. In `s4_*`, the platform exposes the offline judgement layer: what the truth process says, what the bank sees or acts on, how those judgements attach to event rows, and how selected flows move through case handling.

The key posture for later analysis is not to collapse these surfaces into one "fraud label." They answer different questions. `s4_flow_truth_labels_6B` answers ground truth. `s4_flow_bank_view_6B` answers institutional view. `s4_event_labels_6B` attaches those judgements to the event stream. `s4_case_timeline_6B` tells the operational story after a flow becomes case-relevant.

The next work should use these distinctions deliberately. If the question is model supervision, start from flow truth. If the question is bank action quality, compare bank view against truth. If the question is operational burden, use the case timeline. If the question is event-stream labelling, use event labels but remember they are a two-event expansion of the flow-level judgement.
