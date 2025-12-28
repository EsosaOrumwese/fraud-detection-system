# Layer-2 - Segment 5A - State Overview (S0-S5)

Segment 5A builds deterministic intensity surfaces. It gates upstream Layer-1 segments, classifies merchantxzone demand, owns the weekly shape library, composes baseline intensities, applies calendar/scenario overlays, and seals everything with a PASS bundle. All states are RNG-free.

## Segment role at a glance
- Enforce upstream HashGates (1A-3B) and seal the artefacts/policies 5A may read.
- Classify merchantxzone demand classes and base scales.
- Publish the canonical weekly time grid and class/zone shapes (unit-mass).
- Compose baseline per-merchantxzone intensities; overlay calendar/scenario shocks to produce final targets.
- Validate and bundle outputs with `_passed.flag` ("no PASS -> no read" for 5A surfaces).

---

## S0 - Gate & sealed inputs (RNG-free)
**Purpose & scope**  
Verify upstream `_passed.flag_*` for 1A-3B and seal the exact artefacts/policies 5A may touch for a fingerprint.

**Preconditions & gates**  
Layer schemas/dictionaries/registries present; `_passed.flag` + bundles for 1A, 1B, 2A, 2B, 3A, 3B match; identities `{parameter_hash, manifest_fingerprint}` fixed.

**Inputs**  
Upstream gated surfaces (discoverable via catalogues): merchant/outlet, site/timezone, routing surfaces, zone alloc + hash, virtual overlays. Parameter pack: demand class/scale policy, shape library config, scenario/calendar overlays.

**Outputs & identity**  
`s0_gate_receipt_5A` at `data/layer2/5A/s0_gate_receipt/fingerprint={manifest_fingerprint}/`; `sealed_inputs_5A` manifest at `data/layer2/5A/sealed_inputs/fingerprint={manifest_fingerprint}/`. Optional `scenario_manifest_5A` if used to enumerate scenarios (fingerprint-scoped).

**RNG**  
None.

**Key invariants**  
Only artefacts listed in `sealed_inputs_5A` are readable by 5A; sealed inputs digest verified by downstream states; path/embed parity holds.

**Downstream consumers**  
S1-S5 must verify the receipt/digest before reading; S5 bundles it.

---

## S1 - Merchantxzone demand classification (RNG-free)
**Purpose & scope**  
Assign demand class and base scale per `(merchant, legal_country_iso, tzid[, channel])`.

**Preconditions & gates**  
S0 PASS; merchant/zone universe available via sealed inputs; demand class/scale policies sealed.

**Inputs**  
Merchant attributes; zone/domain from `zone_alloc` (and timezones if needed); virtual flags if policy uses them; `demand_class_policy_5A` and `demand_scale_policy_5A`.

**Outputs & identity**  
`merchant_zone_profile_5A` at `data/layer2/5A/merchant_zone_profile_5A/fingerprint={manifest_fingerprint}/` with class id, scale params, flags. Optional `merchant_class_profile_5A` aggregation at the same partition.

**RNG**  
None.

**Key invariants**  
Coverage equals in-scope merchantxzone domain; class/scale decisions are deterministic functions of sealed data/policy; non-negative scales.

**Downstream consumers**  
S2 discovers needed class/zone combos; S3/S4 consume class/scale for intensities.

---

## S2 - Weekly shape library (RNG-free)
**Purpose & scope**  
Define the canonical local-week grid and unit-mass shapes per `(demand_class, zone[, channel])` for each scenario.

**Preconditions & gates**  
S0, S1 PASS; shape config and scenario set sealed.

**Inputs**  
`merchant_zone_profile_5A` (used to know which class/zone combos exist); shape grid config; shape templates/modifiers; scenario metadata.

**Outputs & identity**  
`shape_grid_definition_5A` at `data/layer2/5A/shape_grid_definition_5A/parameter_hash={parameter_hash}/scenario_id={scenario_id}/`.  
`class_zone_shape_5A` at `data/layer2/5A/class_zone_shape_5A/parameter_hash={parameter_hash}/scenario_id={scenario_id}/` with unit-mass vectors per class/zone; optional `class_shape_catalogue_5A` same partitions.

**RNG**  
None.

**Key invariants**  
Grid covers the local week without overlap; per class/zone vector sums to 1 (tolerance policy); non-negative shape values; scenario_id carried on all outputs.

**Downstream consumers**  
S3 uses grid/shapes to build baselines; S4 overlays reference same grid; 5B/6A adopt this grid (no redefinition).

---

## S3 - Baseline intensities (RNG-free)
**Purpose & scope**  
Compose class/scale (S1) and shapes (S2) into baseline per-merchantxzone intensities per scenario.

**Preconditions & gates**  
S0-S2 PASS; scenario set known; baseline policies sealed.

**Inputs**  
`merchant_zone_profile_5A` (class, scale); `shape_grid_definition_5A`; `class_zone_shape_5A`; scenario metadata; optional adjustments/caps from policy.

**Outputs & identity**  
`merchant_zone_baseline_local_5A` at `data/layer2/5A/merchant_zone_baseline_local_5A/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/` with `lambda_local_base` and decomposition fields. Optional `class_zone_baseline_local_5A` and `merchant_zone_baseline_utc_5A` (same partitions).

**RNG**  
None.

**Key invariants**  
Per `(merchant, zone, scenario)` baseline aligns with S1 scale and S2 shape; non-negative; weekly sum consistent with scale (policy tolerance); any UTC projection must derive deterministically from local baselines + 2A civil-time surfaces.

**Downstream consumers**  
S4 overlays; S5 validation; 5B reads as baseline authority.

---

## S4 - Calendar & scenario overlays (RNG-free)
**Purpose & scope**  
Apply deterministic calendar/scenario effects to produce final target intensities.

**Preconditions & gates**  
S0-S3 PASS; overlay policies and calendars sealed.

**Inputs**  
`merchant_zone_baseline_local_5A`; `shape_grid_definition_5A`; scenario calendars/config; overlay policies (per event type, per merchant/zone/class/channel); optional UTC baselines if producing UTC outputs.

**Outputs & identity**  
`merchant_zone_scenario_local_5A` at `data/layer2/5A/merchant_zone_scenario_local_5A/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/` with `lambda_local_scenario`, optional overlay factors. Optional `merchant_zone_overlay_factors_5A` and `merchant_zone_scenario_utc_5A` (same partitions).

**RNG**  
None.

**Key invariants**  
Non-negative intensities; where no events apply, scenario surface equals baseline; overlay factors bounded per policy; domain matches S3 grid and scenario config; any UTC surface is a deterministic transform of local + 2A civil time.

**Downstream consumers**  
S5 validation; 5B uses scenario/local (and UTC if present) as the sole deterministic target.

---

## S5 - Validation bundle & `_passed.flag`
**Purpose & scope**  
Validate S0-S4 outputs and publish the 5A HashGate.

**Preconditions & gates**  
S0-S4 PASS for the fingerprint; required scenario partitions present; upstream gates still verify.

**Inputs**  
`s0_gate_receipt_5A`, `sealed_inputs_5A`; all modelling outputs (`merchant_zone_profile_5A`, grid/shapes, baselines, overlays), optional catalogues; validation policies/tolerances.

**Outputs & identity**  
`validation_report_5A` and optional `validation_issue_table_5A` at `fingerprint={manifest_fingerprint}`; `validation_bundle_5A` at `data/layer2/5A/validation/fingerprint={manifest_fingerprint}/` with `validation_bundle_index_5A`; `_passed.flag` alongside containing `sha256_hex = <bundle_digest>` over indexed files in ASCII-lex order (flag excluded).

**RNG**  
None.

**Key invariants**  
Schema/partition conformance for all datasets; unit-mass shapes; baseline/overlay consistency; bundle digest matches `_passed.flag`; enforces "no PASS -> no read" for 5A surfaces.

**Downstream consumers**  
5B and 6A must verify `_passed.flag` before reading 5A outputs.
