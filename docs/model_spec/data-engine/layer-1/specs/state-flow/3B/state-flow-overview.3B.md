# Layer-1 - Segment 3B - State Overview (S0-S5)

Segment 3B defines virtual merchants and CDN edges. It gates upstream segments, classifies virtual merchants and their settlement nodes, builds edge catalogues with RNG evidence, packages alias tables plus a virtual-edge universe hash, publishes the routing/validation contracts, and seals the segment with a PASS bundle. Inter-country order stays with 1A `s3_candidate_set`; 3A `zone_alloc` remains the zone authority.

## Segment role at a glance
- Enforce 1A/1B/2A/3A HashGates ("no PASS -> no read") and seal 3B policies before any work.
- Classify merchants as virtual vs physical and create settlement nodes for virtuals.
- Build RNG-bearing edge catalogues for virtual merchants; package alias tables and a virtual-edge universe hash.
- Publish routing and validation contracts for virtual flows.
- Validate and bundle everything into `validation_bundle_3B` + `_passed.flag`.

---

## S0 - Gate & sealed inputs (RNG-free)
**Purpose & scope**  
Verify `_passed.flag` from 1A, 1B, 2A, and 3A for the target `manifest_fingerprint`; seal the artefacts 3B may read.

**Preconditions & gates**  
All upstream bundles/flags must match; otherwise abort ("no PASS -> no read").

**Inputs**  
Upstream gated surfaces: 1B `site_locations`/`outlet_catalogue`; 2A `site_timezones`/`tz_timetable_cache`; 3A `zone_alloc` + `zone_alloc_universe_hash`. Policies: virtual classification, settlement coord source, edge geography/budget policy, alias layout, virtual validation/routing policy, RNG policy.

**Outputs & identity**  
`s0_gate_receipt_3B` at `data/layer1/3B/s0_gate_receipt/fingerprint={manifest_fingerprint}/`; `sealed_inputs_3B` at `data/layer1/3B/sealed_inputs/fingerprint={manifest_fingerprint}/`.

**RNG**  
None.

**Key invariants**  
No 3B reads without all upstream PASS; only artefacts in `sealed_inputs_3B` may be read; path/embed parity holds.

**Downstream consumers**  
All later 3B states rely on the receipt; S5 replays its digests.

---

## S1 - Virtual classification & settlement (deterministic)
**Purpose & scope**  
Classify merchants as virtual vs non-virtual and build one settlement node per virtual merchant.

**Preconditions & gates**  
S0 PASS; classification/settlement policies sealed; merchant universe available via upstream sealed inputs.

**Inputs**  
Merchant attributes (MCC, channel, country) via sealed upstream datasets; virtual classification policy; settlement coordinate/timezone sources.

**Outputs & identity**  
`virtual_classification_3B` at `data/layer1/3B/virtual_classification_3B/seed={seed}/fingerprint={manifest_fingerprint}/` with `is_virtual`, reason codes.  
`virtual_settlement_3B` at `data/layer1/3B/virtual_settlement_3B/seed={seed}/fingerprint={manifest_fingerprint}/` with `settlement_site_id`, lat/lon, `tzid_settlement`, provenance (one row per virtual merchant only).

**RNG**  
None.

**Key invariants**  
Every merchant appears once in classification; settlement rows exist only for virtual merchants; settlement tz/coords follow policy and are deterministic.

**Downstream consumers**  
S2 edge build uses the virtual set and settlements; S4 contracts reference settlement tz semantics.

---

## S2 - Edge catalogue construction (RNG)
**Purpose & scope**  
Build static CDN edge nodes per virtual merchant with governed counts, geography, and RNG jitter/placement.

**Preconditions & gates**  
S0, S1 PASS; edge budget/geography policies sealed; required spatial/tz assets sealed.

**Inputs**  
`virtual_classification_3B`, `virtual_settlement_3B`; upstream spatial assets (tiles/weights, polygons, rasters); tz assets; edge policies.

**Outputs & identity**  
`edge_catalogue_3B` at `data/layer1/3B/edge_catalogue_3B/seed={seed}/fingerprint={manifest_fingerprint}/` with edge coords, country, tzid_operational, weights.  
`edge_catalogue_index_3B` at `data/layer1/3B/edge_catalogue_index_3B/seed={seed}/fingerprint={manifest_fingerprint}/` with counts/digests per merchant and global.  
RNG events for edge placement/jitter under `logs/rng/events/.../seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/`.

**RNG posture**  
Philox events for tile/cell choice and jitter (blocks/draws per event per spec); trace reconciled; non-RNG steps for budgets and integer allocations.

**Key invariants**  
Edge counts per merchant/country follow policy; coords inside intended country; tzid_operational valid; digests in index match catalogue bytes; RNG budgets match logs/trace.

**Downstream consumers**  
S3 builds alias/universe hash; S4 contracts; 2B virtual routing reads catalogue after 3B PASS.

---

## S3 - Edge alias tables & virtual edge universe hash (deterministic)
**Purpose & scope**  
Transform edge catalogue into alias tables and compute a fingerprint-scoped universe hash tying policies + catalogue + alias bytes.

**Preconditions & gates**  
S0-S2 PASS; alias layout policy sealed.

**Inputs**  
`edge_catalogue_3B`, `edge_catalogue_index_3B`; alias layout policy; sealed policy digests from S0.

**Outputs & identity**  
`edge_alias_blob_3B` and `edge_alias_index_3B` at `data/layer1/3B/edge_alias_{blob,index}_3B/seed={seed}/fingerprint={manifest_fingerprint}/`.  
`edge_universe_hash_3B` at `data/layer1/3B/edge_universe_hash_3B/fingerprint={manifest_fingerprint}/edge_universe_hash_3B.json` capturing component digests and final `edge_universe_hash`.  
`gamma_draw_log_3B` expected empty (proved RNG-free) at `logs/layer1/3B/gamma_draw/seed={seed}/fingerprint={manifest_fingerprint}/gamma_draw_log_3B.jsonl`.

**RNG**  
None (alias build is deterministic; gamma log remains empty unless spec changes).

**Key invariants**  
Alias tables align with catalogue weights; offsets/checksums match bytes; universe hash stable given inputs/policies; gamma log empty.

**Downstream consumers**  
S4 contracts and S5 validation; 2B uses alias/universe hash for virtual routing after PASS.

---

## S4 - Virtual routing semantics & validation contract (RNG-free)
**Purpose & scope**  
Publish binding contracts for virtual routing and validation (dual time zones, routing policy, validation thresholds).

**Preconditions & gates**  
S0-S3 PASS; validation/routing policy pack sealed.

**Inputs**  
`virtual_classification_3B`, `virtual_settlement_3B`; `edge_catalogue_3B`/`edge_catalogue_index_3B`; `edge_alias_blob_3B`/`edge_alias_index_3B`; `edge_universe_hash_3B`; validation/routing policy pack.

**Outputs & identity**  
`virtual_routing_policy_3B` and `virtual_validation_contract_3B` at `data/layer1/3B/{virtual_routing_policy_3B,virtual_validation_contract_3B}/fingerprint={manifest_fingerprint}/`; `s4_run_summary_3B` summarising versions/digests.

**RNG**  
None.

**Key invariants**  
Contracts reference sealed artefacts (catalogue, alias, universe hash); spell out settlement vs operational tz semantics; validation thresholds and metrics are explicit.

**Downstream consumers**  
2B virtual routing and validators consume these contracts after 3B PASS; S5 bundles them.

---

## S5 - Validation bundle & `_passed.flag`
**Purpose & scope**  
Validate S0-S4 outputs and publish the 3B HashGate.

**Preconditions & gates**  
S0-S4 PASS for the fingerprint; upstream gates still verify; required audits/logs present.

**Inputs**  
Gate receipt, sealed inputs; all 3B datasets (`virtual_classification_3B`, `virtual_settlement_3B`, `edge_catalogue_*`, `edge_alias_*`, `edge_universe_hash_3B`, contracts) plus RNG logs from S2; audit/issue summaries (e.g., `s5_manifest_3B` if produced).

**Outputs & identity**  
`validation_bundle_3B` at `data/layer1/3B/validation/fingerprint={manifest_fingerprint}/` with `validation_bundle_index_3B`; `_passed.flag` alongside containing `sha256_hex = <bundle_digest>` over indexed files in ASCII-lex order (flag excluded).

**RNG**  
None.

**Key invariants**  
Bundle index complete; digest matches `_passed.flag`; all required artefacts present and coherent; enforces "no PASS -> no read" for 3B surfaces (catalogue, alias, universe hash, contracts).

**Downstream consumers**  
2B virtual routing and any downstream segment must verify `_passed.flag` before using 3B artefacts.
