# Branch Investigation: Baseline vs Fraud Overlay Contract

## Branch question

The parent behavioural-stream investigation established that `s2_event_stream_baseline_6B` and `s3_event_stream_with_fraud_6B` have the same broad traffic shape, while the post-overlay stream adds fraud fields. This branch asks the contract question more directly:

> Is `s3_event_stream_with_fraud_6B` a new traffic population, or is it an overlay on the baseline event stream?

The short answer is that the with-fraud stream behaves as an overlay on the baseline traffic contract. It does not add event rows, event types, or a new timing universe. It preserves the event grammar and adds two overlay fields, `fraud_flag` and `campaign_id`. For the rows marked fraud, the overlay matches the baseline event key and timestamp, then changes the economic value carried by `amount`.

That contract matters operationally. In the live fraud decisioning platform, the with-fraud stream should be read as the same traffic body after fraud behaviour has been injected, not as a second independent stream of extra transactions. The analytical comparison is therefore not "how many new events did fraud add?" The comparison is "which existing event keys were marked, and how did their attributes change?"

## Evidence used

Primary report:

- [`behavioural_streams_investigation.md`](../behavioural_streams_investigation.md)

Branch script:

- [`analyze_behavioural_baseline_vs_fraud_overlay_contract.py`](../../../../scratch/analyze_behavioural_baseline_vs_fraud_overlay_contract.py)

Branch exports:

- [`stream_contract_profile.csv`](../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/stream_contract_profile.csv)
- [`baseline_with_fraud_contract_delta.csv`](../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/baseline_with_fraud_contract_delta.csv)
- [`schema_overlay_contract.csv`](../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/schema_overlay_contract.csv)
- [`stream_key_fingerprint.csv`](../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/stream_key_fingerprint.csv)
- [`with_fraud_overlay_summary.csv`](../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/with_fraud_overlay_summary.csv)
- [`fraud_rows_vs_baseline.csv`](../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/fraud_rows_vs_baseline.csv)
- [`fraud_flag_by_event_type.csv`](../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/fraud_flag_by_event_type.csv)
- [`fraud_flow_shape.csv`](../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/fraud_flow_shape.csv)
- [`campaign_overlay_summary.csv`](../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/campaign_overlay_summary.csv)
- [`baseline_nulls.csv`](../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/baseline_nulls.csv)
- [`with_fraud_nulls.csv`](../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/with_fraud_nulls.csv)
- [`baseline_vs_fraud_overlay_contract_summary.json`](../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/baseline_vs_fraud_overlay_contract_summary.json)

The branch is built from compact summaries already produced in the behavioural-stream investigation. It does not rerun the full raw-stream comparison. The exact row-level comparison in this branch is limited to the fraud-marked rows joined back to baseline under the single pinned lineage context for this run: `seed = 42`, one `parameter_hash`, one `manifest_fingerprint`, and `scenario_id = baseline_v1` in both streams. For the full non-fraud key universe, the evidence is profile-and-fingerprint evidence: same row count, same approximate flow count, same event-type count, same event-sequence range, same timestamp horizon, and same summed hash fingerprint over `flow_id + event_seq`. That is strong profiling evidence of preservation, but it is not the same thing as a full anti-join proof over every non-fraud event key.

## Schema contract: the overlay adds columns, not a new event grammar

The schema comparison shows that the with-fraud stream keeps the baseline event body and adds two fields:

| Column | In baseline | In with-fraud | Overlay-added |
|---|---:|---:|---:|
| `amount` | yes | yes | no |
| `campaign_id` | no | yes | yes |
| `event_seq` | yes | yes | no |
| `event_type` | yes | yes | no |
| `flow_id` | yes | yes | no |
| `fraud_flag` | no | yes | yes |
| `manifest_fingerprint` | yes | yes | no |
| `parameter_hash` | yes | yes | no |
| `scenario_id` | yes | yes | no |
| `seed` | yes | yes | no |
| `ts_utc` | yes | yes | no |

This is the first contract-level read. The with-fraud stream is not structurally broader in the sense of carrying merchant, session, case, or truth context directly in the stream. It remains the same thin traffic event stream, but with fraud overlay metadata added.

`fraud_flag` is the binary marker that says whether an event row belongs to the fraud overlay. `campaign_id` is the campaign handle for fraud-marked traffic. The null pattern supports this interpretation: `campaign_id` is null for `473,369,124` rows, exactly matching the non-fraud row count. That makes `campaign_id` nullness a semantic state rather than a missing-data problem:

- non-fraud event row -> no campaign ID
- fraud event row -> campaign ID present

So the overlay contract is not "every row gets a campaign." The contract is "only the rows selected into the fraud campaign layer carry a campaign identity."

## Traffic-shape preservation

At the broad stream-contract level, baseline and with-fraud have the same traffic body:

| Metric | Baseline | With-fraud | Delta |
|---|---:|---:|---:|
| Rows | `473,383,388` | `473,383,388` | `0` |
| Approx flows (profiling) | `244,190,267` | `244,190,267` | `0` |
| Event types | `2` | `2` | `0` |
| Minimum event sequence | `0` | `0` | `0` |
| Maximum event sequence | `1` | `1` | `0` |
| Minimum UTC timestamp | `2026-01-01T00:00:00.001940Z` | `2026-01-01T00:00:00.001940Z` | same |
| Maximum UTC timestamp | `2026-04-01T00:01:41.104298Z` | `2026-04-01T00:01:41.104298Z` | same |

The key fingerprint profile also matches:

| Stream | Rows | Approx flows (profiling) | Key hash sum over `flow_id + event_seq` |
|---|---:|---:|---:|
| `baseline` | `473,383,388` | `244,190,267` | `4.365982797643315e+27` |
| `with_fraud` | `473,383,388` | `244,190,267` | `4.365982797643315e+27` |

The correct interpretation is preservation, not expansion. The with-fraud stream does not increase the event-row count and does not add another event side to the grammar. The approximate flow count is a profiling metric, not exact identity evidence; the stronger preservation signal here is the combination of unchanged row count, unchanged grammar, unchanged horizon, and matching key fingerprint. Together, those show that the with-fraud stream preserves the two-event authorization shape and changes selected attributes inside that stream.

There is one evidence caveat. The branch has not performed a full exact anti-join across all `473M` event keys. The exact join evidence is for the fraud-marked subset. For the full stream, we rely on same row count, same grammar, same horizon, and matching hash fingerprint. That is enough to support the branch's analytical posture, but if this were an audit-control proof of full key identity, the next step would be a bounded or distributed exact key anti-join.

## Fraud layer scale

The fraud overlay is extremely sparse at event-row grain:

| Fraud flag | Rows | Row share | Campaigns | Mean amount | Median amount | Max amount |
|---|---:|---:|---:|---:|---:|---:|
| `false` | `473,369,124` | `99.996987%` | `0` | `24.31` | `14.99` | `3,401.78` |
| `true` | `14,264` | `0.003013%` | `6` | `54.76` | `31.75` | `729.73` |

This is an important denominator point. The fraud layer is not a large alternate traffic body. It is a very small subset of the same stream. At row grain, only about `0.003%` of events are fraud-marked. That means most full-stream aggregate metrics will barely move, even when fraud-marked rows themselves differ materially from normal traffic.

That is exactly what the amount-surface deltas show:

| Metric | Baseline | With-fraud | Delta |
|---|---:|---:|---:|
| Total amount | `11,509,248,225.40` | `11,509,685,771.69` | `437,546.30` |
| Mean amount | `24.312742` | `24.313666` | `0.000924` |
| Median amount | `14.991537` | `14.995169` | `0.003632` |
| P95 amount | `99.443375` | `99.712272` | `0.268898` |

The total amount increases by about `437.5K`, but that is only about `0.0038%` of the baseline total amount. The fraud rows are materially higher-value than non-fraud rows, but they are so sparse that the global stream surface barely changes. This is why the fraud story cannot be understood from whole-stream averages alone. We need both views:

- full-stream view: the overlay preserves traffic scale and barely moves global summaries
- fraud-subset view: the marked rows have a different economic profile

## Fraud event grammar is balanced

The fraud rows preserve the request/response grammar:

| Event type | Fraud flag | Rows | Share within event type |
|---|---:|---:|---:|
| `AUTH_REQUEST` | `false` | `236,684,562` | `99.996987%` |
| `AUTH_REQUEST` | `true` | `7,132` | `0.003013%` |
| `AUTH_RESPONSE` | `false` | `236,684,562` | `99.996987%` |
| `AUTH_RESPONSE` | `true` | `7,132` | `0.003013%` |

The exact fraud-flow shape confirms the same point:

| Fraud flows | Minimum events per flow | Median events per flow | Maximum events per flow | Nonstandard flow shapes |
|---:|---:|---:|---:|---:|
| `7,132` | `2` | `2` | `2` | `0` |

This means the overlay is flow-consistent for fraud-marked traffic. A fraud-marked flow has both event sides represented. Fraud is not appearing as a one-sided event artifact where only request rows or only response rows were selected.

That matters for downstream labels and case workflows. If fraud were marked only on one event side, any flow-level analysis would need special reconstruction rules. Here, the fraud overlay is already aligned with the stream grammar: one fraud-marked request row and one fraud-marked response row per fraud flow.

## What changes on fraud-marked rows

The exact comparison back to baseline was performed for the `14,264` fraud-marked rows:

| Check | Rows |
|---|---:|
| Fraud rows | `14,264` |
| Matched baseline rows | `14,264` |
| Missing baseline rows | `0` |
| Same event type rows | `14,264` |
| Same timestamp rows | `14,264` |
| Same amount rows | `0` |

The amount deltas are:

| Delta metric | Amount delta |
|---|---:|
| Mean amount delta | `+30.67` |
| Minimum amount delta | `+0.08` |
| Maximum amount delta | `+497.13` |

This is the clearest contract evidence in the branch. For the fraud-marked subset, the overlay does not create new event keys under the pinned single-lineage context, does not alter the event type, and does not alter the timestamp. It selects existing baseline event keys and changes `amount`. In platform language, the fraud overlay changes the economic signal that downstream decisioning, learning, and investigation would see, while preserving the event-bus identity and timing envelope for the marked rows.

This also tells us how not to compare the streams. A naive row-count comparison will say "nothing changed" because the row count is preserved. A naive full-stream mean comparison will also understate the change because fraud rows are rare. The correct comparison is keyed: locate the marked event keys, compare them back to their baseline versions, and inspect which attributes were preserved and which were mutated.

## Campaign IDs are exposed, but not self-explaining

The overlay exposes six campaign IDs. Their row and flow counts are:

| Campaign rank | Rows | Flows | Event types | Mean amount | Time span |
|---:|---:|---:|---:|---:|---|
| 1 | `4,556` | `2,278` | `2` | `54.30` | Jan 1 to Mar 31 |
| 2 | `3,844` | `1,922` | `2` | `54.64` | Jan 1 to Mar 31 |
| 3 | `2,446` | `1,223` | `2` | `55.55` | Jan 1 to Mar 31 |
| 4 | `2,416` | `1,208` | `2` | `54.82` | Jan 1 to Mar 31 |
| 5 | `550` | `275` | `2` | `53.71` | Jan 1 to Mar 31 |
| 6 | `452` | `226` | `2` | `57.27` | Jan 1 to Mar 31 |

Every campaign has two event types, and each campaign's row count is exactly twice its flow count. That preserves the same event grammar inside the campaign layer.

The campaign IDs are not self-explaining. At this stage, we can say how large each campaign footprint is, whether the grammar is preserved, and how the campaign amounts behave. We should not infer campaign semantics from the hashed IDs alone. Their business meaning would need to be read from the campaign catalogue or later truth/case context.

## What this proves and what it does not prove

This branch proves that the with-fraud stream preserves the stream-level event grammar and adds fraud overlay fields. It also proves, for the fraud-marked subset under the pinned single-lineage context, that every fraud row matches a baseline event key, preserves event type, preserves timestamp, and changes amount.

It does not prove full key identity for every non-fraud row through an exact all-stream anti-join. The branch's full-stream preservation claim is based on matching profile and fingerprint evidence. That is acceptable for the current investigative branch, but an audit-grade reconciliation would need an exact full-key comparison using a warehouse/distributed posture.

It also does not explain the meaning of the six campaign IDs. The stream exposes campaign handles, not campaign definitions. The definitions would need to be read from the campaign catalogue or later truth/case context.

## Leads exposed by this branch

1. The with-fraud stream should be analyzed as an overlay on the baseline traffic body, not as an appended fraud population.

2. Fraud is sparse at event-row grain, so full-stream averages will hide most fraud-specific behaviour.

3. Fraud-marked rows preserve event key, event type, and timestamp while changing amount.

4. Fraud marking is flow-consistent: every fraud flow has both request and response rows.

5. `campaign_id` nullness is semantic, not a completeness defect.

6. Campaign IDs require a later semantic bridge; the stream alone gives footprint, not campaign meaning.

7. If a future audit requires full baseline/with-fraud reconciliation, the next step is an exact key anti-join over the full stream, not another profile comparison.

## Working conclusion

The baseline stream is the clean traffic contract. The with-fraud stream is the same traffic contract after a sparse, campaign-tagged fraud overlay has been applied.

The overlay preserves the event-bus shape and changes selected economic values. That makes the with-fraud stream analytically different from baseline, but not because it adds a new traffic population. It is different because a tiny set of existing event keys has been marked, campaign-tagged, and amount-mutated while the surrounding stream remains structurally stable.

## Appendix: visual evidence

### Figure 1. Schema overlay contract

<img src="../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/figures/01_schema_overlay_contract.png" width="900" />

### Figure 2. Contract shape and amount delta

<img src="../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/figures/02_contract_shape_and_amount_delta.png" width="900" />

### Figure 3. Fraud sparsity and amount contrast

<img src="../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/figures/03_fraud_sparsity_and_amount_contrast.png" width="900" />

### Figure 4. Fraud event-side balance

<img src="../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/figures/04_fraud_event_side_balance.png" width="900" />

### Figure 5. Fraud-row preservation and mutation

<img src="../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/figures/05_fraud_row_preservation_and_mutation.png" width="900" />

### Figure 6. Campaign overlay footprint

<img src="../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/figures/06_campaign_overlay_footprint.png" width="900" />

### Figure 7. Campaign ID null semantics

<img src="../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/figures/07_campaign_id_null_semantics.png" width="760" />

### Figure 8. Stream profile preservation evidence

<img src="../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/figures/08_stream_profile_preservation_evidence.png" width="900" />

### Figure 9. Campaign grammar and time span

<img src="../../../../exports/interface_world/behavioural_streams/branches/baseline_vs_fraud_overlay_contract/figures/09_campaign_grammar_and_time_span.png" width="900" />
