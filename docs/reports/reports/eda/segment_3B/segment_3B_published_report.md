# Segment 3B - Design vs Implementation Observations (Virtual Merchants & CDN Surfaces)
Date: 2026-01-31
Scope: Design intent vs implementation notes for Segment 3B (S0-S5), plus what to look for in 3B datasets before assessment.

---

## 0) Why this report exists
Segment 3B builds the virtual-merchant overlay: it decides who is virtual, assigns a legal settlement anchor, constructs the CDN edge universe with coordinates and weights, packages the alias tables used by routing, and publishes the routing + validation contracts that govern virtual flows. This report captures what the 3B design specifies, what implementation decisions were taken, and what evidence we should look for when we later assess the 3B datasets for realism and correctness.

---

## 1) Design intent (what 3B should do)
High-level intent across states:

1) S0 - Gate & environment seal
   - Enforce upstream PASS gates (1A, 1B, 2A, 3A) and seal the exact set of policies, references and datasets that 3B is allowed to read.
   - Emit `s0_gate_receipt_3B` and `sealed_inputs_3B` as the only authority on the 3B input universe.

2) S1 - Virtual classification & settlement nodes
   - Classify merchants into virtual vs non-virtual using governed MCC/channel rules.
   - Create one settlement node per virtual merchant with deterministic `settlement_site_id`, settlement coordinates and a `tzid_settlement`.
   - Emit `virtual_classification_3B` and `virtual_settlement_3B`.

3) S2 - CDN edge catalogue construction
   - For each virtual merchant, determine an edge budget and allocate edges across countries using governed weights.
   - Sample edge coordinates (HRSL + tile weights + world polygons), assign `tzid_operational`, and compute `edge_weight`.
   - Emit `edge_catalogue_3B` and `edge_catalogue_index_3B` plus RNG evidence logs.

4) S3 - Edge alias tables & universe hash
   - Convert each merchant's edge distribution into an alias table in a versioned binary layout.
   - Emit `edge_alias_blob_3B`, `edge_alias_index_3B`, and `edge_universe_hash_3B` tying policies + S2 catalogue + S3 alias outputs.

5) S4 - Virtual routing semantics & validation contracts
   - Publish `virtual_routing_policy_3B` (settlement vs operational clocks, alias usage, routing semantics).
   - Publish `virtual_validation_contract_3B` describing tests/tolerances used later to validate virtual routing.

6) S5 - Validation bundle + PASS flag
   - Re-audit all 3B artefacts and RNG usage.
   - Emit `validation_bundle_3B`, `validation_bundle_index_3B`, `s5_manifest_3B`, and `_passed.flag`.

---

## 2) Expected datasets & evidence surfaces (contract view)
Core datasets to assess later:

S0 / sealing
- `s0_gate_receipt_3B`
- `sealed_inputs_3B`

S1 / virtual classification + settlement
- `virtual_classification_3B`
- `virtual_settlement_3B`

S2 / edge catalogue
- `edge_catalogue_3B`
- `edge_catalogue_index_3B`
- RNG evidence logs: `rng_event_edge_tile_assign`, `rng_event_edge_jitter`

S3 / alias & universe integrity
- `edge_alias_blob_3B`
- `edge_alias_index_3B`
- `edge_universe_hash_3B`

S4 / routing + validation contracts
- `virtual_routing_policy_3B`
- `virtual_validation_contract_3B`

S5 / validation bundle + PASS gate
- `validation_bundle_3B`
- `validation_bundle_index_3B`
- `s5_manifest_3B`, `s5_structural_summary_3B`, `s5_rng_summary_3B`, `s5_digest_summary_3B`
- `_passed.flag`

---

## 2.1) Priority ranking (by realism impact)
If we rank datasets by their direct impact on realism in the virtual overlay, the order is:

1) `edge_catalogue_3B` - concrete edge geography, weights and tzids; the most visible realism surface.
2) `virtual_settlement_3B` - legal anchors for virtual merchants; determines the home base realism.
3) `virtual_classification_3B` - determines how large the virtual universe is and why; sets overall realism of virtual prevalence.
4) `edge_alias_blob_3B` / `edge_alias_index_3B` - governs how routing samples edges; realism depends on correct weighting and layout.
5) `edge_universe_hash_3B` - integrity surface, critical for correctness but indirect for realism.
6) `virtual_routing_policy_3B` / `virtual_validation_contract_3B` - semantics and governance; critical for correctness but not a visible realism surface by themselves.

---

## 3) Implementation observations (what is actually done)
Based on `segment_3B.impl_actual.md` and the 3B state-expanded specs.

### 3.1 S0 - Gate & sealed inputs
Observed posture: strict gate enforcement and sealed-input determinism, aligned with the design intent.

Key observations from implementation notes:
- Upstream PASS gates enforced for 1A, 1B, 2A and 3A before any 3B data-plane state runs.
- `tz_timetable_cache` is treated as optional, consistent with the contract; the cache is only sealed and used if present.
- A Pelias bundle digest mismatch was corrected by updating the sealed bundle file, indicating S0 is strict about reference integrity rather than permissive.

Net: S0 is operating as a true closed-world gate that seals the exact inputs and fails on mismatched reference digests, which is the intended posture for reproducibility.

---

### 3.2 S1 - Virtual classification & settlement nodes
Observed posture: no deviations recorded in the implementation notes.

Design expectations remain intact:
- Deterministic classification based on MCC/channel rules.
- One settlement node per virtual merchant with `tzid_settlement` and provenance.

Net: There are no recorded implementation deviations here; we will rely on dataset inspection to confirm classification rates and settlement plausibility.

---

### 3.3 S2 - CDN edge catalogue construction
Observed posture: implementation is consistent with the design, with a notable correction around timezone resolution.

Key implementation notes:
- Timezone resolution failure for country SH (Saint Helena) was addressed by adding a tz_overrides entry, rather than adding special-case logic. This keeps the algorithm deterministic and policy-driven.
- A helper for latest run receipts was added for stability, but does not alter the data plane.

Net: S2 remains policy-driven and deterministic with RNG only for spatial jitter, and the resolution fix indicates attention to geographic edge cases without compromising determinism.

---

### 3.4 S3 - Edge alias tables & universe hash
Observed posture: significant but controlled implementation adjustments to schema references, hashing and index layout.

Key changes recorded:
- Schema reference for alias blob fixed to `edge_alias_blob_header_3B` (previously mismatched).
- Index fields strictly limited to schema-defined columns; policy and `parameter_hash` fields were not added when the schema did not authorize them.
- Universe hash uses minimal schema fields (merchant_id, edge_id, edge_weight), to ensure it is stable and only depends on contract-approved fields.
- Alias index digest computed over raw parquet bytes (not row-level hashing), ensuring reproducibility and avoiding ambiguous serialization.
- `universe_hash` field in the alias index is set to null to avoid circular digest dependencies.
- `gamma_draw_log_3B` exists but is empty, indicating no gamma draws are currently logged in 3B.
- merchant_id overflow fix in alias indices (UInt64) and adjustments to alias blob padding/alignment.

Net: S3 is stable and deterministic, but the hash and index behavior relies on careful adherence to schema constraints. The empty gamma log is a potential gap if future 3B processes are expected to emit gamma-based evidence.

---

### 3.5 S4 - Virtual routing semantics & validation contracts
Observed posture: contract compilation completed; schema adapter expanded to support object columns.

Implementation notes:
- The JSON schema adapter was expanded to support object-typed columns and list items.
- An extra `digests` field was removed from `s4_run_summary_3B` because it was not contract-approved.

Net: S4 is aligned with contract strictness; the implementation is conservative about schema compliance.

---

### 3.6 S5 - Validation bundle + PASS flag
Observed posture: validation bundle law clarified; new evidence surfaces added.

Key decisions recorded:
- Bundle digest law uses evidence file bytes (not an index-only shortcut).
- `s5_manifest_3B` is mandatory and additional summaries are required: `s5_structural_summary_3B`, `s5_rng_summary_3B`, `s5_digest_summary_3B`.
- RNG logs must include internal input fields, though they are not sealed as policy.
- Warnings allowed for missing `edge_tile_assign` events, if `edge_tile_assign` was not used for a run.

Net: S5 is strict and evidence-rich, with explicit digest rules and a more detailed validation trail than earlier segments.

---

## 4) Design vs implementation deltas (summary)
1) S3 hash scope and index layout were narrowed to schema-defined fields, and the hash/index coupling was carefully arranged to avoid circular dependencies. This is consistent with design intent but more conservative than a naive hash-everything approach.
2) `gamma_draw_log_3B` is empty, which is a meaningful deviation if gamma-based randomness was intended for 3B. It may be acceptable if no gamma draws are used, but it should be verified in datasets.
3) S5 digest law uses evidence bytes, which is stricter than an index-only bundle and aligns with the S5 design, but requires downstream tooling to use the correct hashing law.
4) S2 timezone resolution edge case (SH) was solved via policy override rather than ad-hoc code. This is aligned with deterministic, governed inputs.

---

## 5) What to look for in 3B datasets (realism + correctness)
This checklist is focused on realism: whether the virtual overlay looks believable and sufficiently rich for downstream modeling.

### 5.1 `virtual_classification_3B` (virtual vs physical realism)
Key questions:
- What share of merchants are virtual overall and by MCC/channel?
- Are virtual classifications concentrated in plausible verticals (digital goods, services) rather than randomly scattered?
- Are reason codes balanced and consistent with policy thresholds?

Realism risks:
- Nearly uniform virtual rates across all MCCs/channels would look synthetic and policy-agnostic.
- Over-classification (too many merchants virtual) would distort platform realism by undercutting physical geography.

---

### 5.2 `virtual_settlement_3B` (settlement anchor realism)
Key questions:
- Are settlement coordinates plausible within the merchant's legal country?
- Do settlement timezones align with the settlement coordinates and country boundaries?
- Do settlement nodes repeat unrealistically (one coordinate used for many unrelated merchants)?

Realism risks:
- Settlement anchors collapsing to a few coordinates or incorrect timezones will make virtual flows feel artificial.
- Mismatch between legal country and settlement coordinates undermines trust in virtual semantics.

---

### 5.3 `edge_catalogue_3B` (edge geography and weight realism)
Key questions:
- Edge counts per merchant and per country: do they scale with merchant size and country weight policies?
- Edge coordinates: are they inside country polygons and aligned to populated regions (HRSL)?
- `edge_weight` distribution: do weights create realistic dominance or are they flat/uniform?
- `tzid_operational`: does it match edge coordinates and country expectations?

Realism risks:
- If edges are uniformly distributed across countries or uniformly weighted, routing will be unrealistic and too even.
- If edge coordinates fall outside country polygons or cluster in improbable regions, the geography will be visibly synthetic.

---

### 5.4 `edge_alias_blob_3B` / `edge_alias_index_3B`
Key questions:
- Does index metadata (offsets, counts, checksums) align with the edge counts in `edge_catalogue_3B`?
- Are alias tables sized consistently with weights (more edges -> larger alias segments)?
- Are checksums stable and deterministic for re-runs with the same inputs?

Realism risks:
- If alias tables do not respect the weight distributions, routing will ignore edge realism.
- Misaligned index metadata would indicate representation errors rather than realism issues, but it would block routing correctness.

---

### 5.5 `edge_universe_hash_3B`
Key questions:
- Does the hash change when policies or edge catalogues change?
- Are the component digests traceable back to policy + edge outputs?

Realism risks:
- If the universe hash is insensitive to input changes, the system loses provenance and cannot explain routing behavior.

---

### 5.6 `virtual_routing_policy_3B` & `virtual_validation_contract_3B`
Key questions:
- Do these contracts explicitly bind to S1-S3 outputs and list the exact tests and tolerances?
- Are settlement-vs-operational clock semantics clear and testable?

Realism risks:
- Vague routing semantics or unbound validation contracts will make it hard to interpret whether realism failures are data issues or policy gaps.

---

### 5.7 Validation bundle surfaces
Key questions:
- Is `validation_bundle_3B` present with `_passed.flag` and index digest that matches the digest law?
- Do the S5 summaries align with the actual artefacts (counts, digests, RNG logs)?

Realism risks:
- If validation evidence is inconsistent, we cannot trust any conclusions about realism because the input universe is not fully sealed.

---

## 6) Interpretation guide for realism assessment
If 3B outputs look unrealistic, the likely root causes (by design) are:

1) Overly broad virtual classification rules (S1) -> too many merchants are virtual, draining realism from physical geography.
2) Settlement anchors not aligned with legal countries (S1) -> settlement realism collapses, and dual-time semantics become confusing.
3) Uniform edge weights or evenly distributed edge placement (S2) -> routing will not produce believable edge traffic patterns.
4) Alias tables not reflecting weights (S3) -> even if edges are realistic, routing will sample unrealistically.

During assessment, we should always separate:
- Structural correctness (schema/joins/hashes) from
- Behavioral realism (spatial plausibility, weight diversity, heterogeneity across merchants/countries).

---

(Next: detailed assessment of the actual 3B outputs under the run folder, once we move to data analysis.)
