# Layer-2 - Segment 5B - State Overview (S0-S5)

Segment 5B realises arrivals. It gates upstream segments (1A-3B, 5A), fixes the scenario time grid and grouping, draws latent intensities, converts them to bucket counts, expands to the canonical arrival stream, and seals the segment with a PASS bundle. This segment is RNG-bearing in S2-S4; everything else is deterministic.

## Segment role at a glance
- Enforce upstream HashGates and seal 5B inputs/policies before any read.
- Define scenario time grid and grouping over merchantxzonexchannel.
- Realise latent intensities (LGCP-style) on that grid and draw bucket counts.
- Expand counts into `arrival_events_5B` with full routing/tz context.
- Validate and publish `validation_bundle_5B` + `_passed.flag` ("no PASS -> no read" for arrivals).

---

## S0 - Gate & sealed inputs (RNG-free)
**Purpose & scope**  
Verify `_passed.flag_*` from 1A, 1B, 2A, 2B, 3A, 3B, and 5A for the target `manifest_fingerprint`; seal all artefacts/policies 5B may read.

**Preconditions & gates**  
Layer schemas/dictionaries/registries present; upstream bundles/flags match; identities `{seed, parameter_hash, manifest_fingerprint}` fixed; scenario set/config sealed.

**Inputs**  
Upstream gated surfaces: 2A civil time; 2B routing surfaces; 3A `zone_alloc` + hash; 3B virtual routing/edge hash; 5A intensity surfaces (`shape_grid_definition_5A`, baseline/scenario intensities). 5B parameter pack: time grid config, grouping policy, LGCP config, count law, RNG policies, routing semantics.

**Outputs & identity**  
`s0_gate_receipt_5B` at `data/layer2/5B/s0_gate_receipt/fingerprint={manifest_fingerprint}/`; `sealed_inputs_5B` at `data/layer2/5B/sealed_inputs/fingerprint={manifest_fingerprint}/`.

**RNG**  
None.

**Key invariants**  
Only artefacts listed in `sealed_inputs_5B` may be read; sealed digest verified downstream; upstream HashGates enforce "no PASS -> no read".

**Downstream consumers**  
S1-S5 verify the receipt/digest; S5 bundles it.

---

## S1 - Time grid & grouping (RNG-free)
**Purpose & scope**  
Define the scenario time grid and grouping from `(merchant, zone_representation, channel_group)` to `group_id`.

**Preconditions & gates**  
S0 PASS; scenarios and horizons sealed; 5A scenario surfaces present.

**Inputs**  
`merchant_zone_scenario_local_5A`/`_utc_5A` to infer horizon; grouping policy (`arrival_grouping_policy_5B`); 2A civil time if UTC grid used.

**Outputs & identity**  
`s1_time_grid_5B` at `data/layer2/5B/s1_time_grid_5B/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/` with bucket start/end/duration and tags.  
`s1_grouping_5B` at `data/layer2/5B/s1_grouping_5B/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/` mapping domain keys to `group_id` with group features.

**RNG**  
None.

**Key invariants**  
Grid covers the scenario horizon with contiguous, non-overlapping buckets; every domain row has exactly one `group_id`; later states must not re-grid or re-group.

**Downstream consumers**  
S2-S4 operate strictly on this grid/group mapping; S5 validates against it.

---

## S2 - Latent intensity realisation (RNG)
**Purpose & scope**  
Realise latent intensities (e.g., LGCP) on the S1 grid using 5A scenario surfaces as targets.

**Preconditions & gates**  
S0, S1 PASS; 5A intensities available; LGCP config and RNG policy sealed.

**Inputs**  
`s1_time_grid_5B`, `s1_grouping_5B`; 5A scenario intensities aligned to the grid; LGCP parameters (covariance, variance, length scales).

**Outputs & identity**  
`s2_realised_intensity_5B` at `data/layer2/5B/s2_realised_intensity_5B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/` with `lambda_realised`, baseline, and latent components per cell.  
Optional `s2_latent_field_5B` (same partitions) with group-level latent values.

**RNG posture**  
Philox streams per RNG policy for latent Gaussian draws; events logged with envelope (`blocks`, `draws`) and reconciled in trace.

**Key invariants**  
`lambda_realised >= 0`, finite; deterministic given `(seed, parameter_hash, manifest_fingerprint, scenario_id)` + config; S3/S4 must treat as fixed.

**Downstream consumers**  
S3 count draws; S5 audits RNG budgets.

---

## S3 - Bucket-level arrival counts (RNG)
**Purpose & scope**  
Draw integer arrival counts per bucket from realised intensities.

**Preconditions & gates**  
S0-S2 PASS; count law and RNG policy sealed.

**Inputs**  
`s2_realised_intensity_5B`; `s1_time_grid_5B` (bucket durations); count-law params.

**Outputs & identity**  
`s3_bucket_counts_5B` at `data/layer2/5B/s3_bucket_counts_5B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/` with `count_N`, parameters, RNG provenance.

**RNG posture**  
Philox events (e.g., `rng_event_bucket_count`) with `blocks=1`, `draws="1"` per draw; budgets logged; trace reconciles totals.

**Key invariants**  
Counts are non-negative integers; consistent with `lambda_realised` and bucket duration under the chosen law; S4 must not alter counts.

**Downstream consumers**  
S4 expands counts; S5 checks count vs arrival parity.

---

## S4 - Arrival skeleton egress (RNG)
**Purpose & scope**  
Expand bucket counts into per-arrival events with timestamps and routing to produce `arrival_events_5B`.

**Preconditions & gates**  
S0-S3 PASS; routing contracts (2B/3A/3B) and civil time surfaces available via sealed inputs.

**Inputs**  
`s3_bucket_counts_5B`; `s1_time_grid_5B`; routing surfaces (2B group weights/alias, 3A zone alloc + hash, 3B virtual routing + edge hash); 2A civil time.

**Outputs & identity**  
`arrival_events_5B` at `data/layer2/5B/arrival_events_5B/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/` with per-arrival identity, UTC/local timestamps, routing context (`site_id` or `edge_id`, `tz_group_id`, hashes), and optional per-event intensity fields.  
Optional summaries: `s4_arrival_summary_5B`, `s4_arrival_anomalies_5B` (same partitions).

**RNG posture**  
Additional draws for intra-bucket timing and routing picks (group/site, edge for virtuals) per configured RNG families; all events logged under `seed/parameter_hash/run_id`.

**Key invariants**  
Rows per cell equal `count_N`; routing consistent with 2B/3A/3B contracts; timestamps within bucket bounds; hashes (`routing_universe_hash`, `edge_universe_hash`) included where applicable.

**Downstream consumers**  
S5 validation; Layer-3/enterprise ingest `arrival_events_5B` only after PASS.

---

## S5 - Validation bundle & `_passed.flag`
**Purpose & scope**  
Validate S0-S4 outputs and publish the 5B HashGate.

**Preconditions & gates**  
S0-S4 PASS for the fingerprint; all seeds/scenarios present; upstream gates still verify.

**Inputs**  
`s0_gate_receipt_5B`, `sealed_inputs_5B`; S1-S4 datasets (grids/grouping, realised intensities, latent field, bucket counts, arrivals, summaries); RNG logs/events/trace; validation policies/tolerances.

**Outputs & identity**  
`validation_report_5B` and optional `validation_issue_table_5B` at `fingerprint={manifest_fingerprint}`; `validation_bundle_5B` at `data/layer2/5B/validation/fingerprint={manifest_fingerprint}/` with `validation_bundle_index_5B`; `_passed.flag` alongside containing `sha256_hex = <bundle_digest>` over indexed files in ASCII-lex order (flag excluded).

**RNG**  
None (validator).

**Key invariants**  
Schema/partition conformance; grid/grouping parity; counts vs intensities vs arrivals match; routing semantics consistent with 2B/3A/3B contracts; RNG accounting closes; bundle digest matches `_passed.flag`; enforces "no PASS -> no read" for 5B artefacts.

**Downstream consumers**  
6A/6B and any external ingestors must verify `_passed.flag` before using `arrival_events_5B` or other 5B outputs.
