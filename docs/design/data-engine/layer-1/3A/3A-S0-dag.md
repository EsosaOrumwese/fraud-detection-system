```
        LAYER 1 · SEGMENT 3A — STATE S0 (GATE & SEALED INPUTS FOR ZONE ALLOCATION)  [NO RNG]

Authoritative inputs (read-only at S0 entry)
--------------------------------------------
[Schema+Dict · Shape & catalogue authority]
    - schemas.layer1.yaml                 (layer-wide primitives, RNG envelope, bundle index law)
    - schemas.ingress.layer1.yaml         (ingress/common definitions)
    - schemas.1A.yaml, schemas.1B.yaml    (upstream segment schema packs)
    - schemas.2A.yaml, schemas.2B.yaml
    - schemas.3A.yaml                     (shape authority for all 3A artefacts incl. s0_gate_receipt_3A, sealed_inputs_3A)
    - dataset_dictionary.layer1.*.yaml    (Layer-1 dictionary, including 1A/1B/2A/3A entries)
    - artefact_registry_*.yaml            (registry entries for upstream bundles + 3A policies/priors)

[Upstream HashGates · required for 3A.S0]
    - validation_bundle_1A + _passed.flag  @ data/layer1/1A/validation/fingerprint={manifest_fingerprint}/
    - validation_bundle_1B + _passed.flag  @ data/layer1/1B/validation/fingerprint={manifest_fingerprint}/
    - validation_bundle_2A + _passed.flag  @ data/layer1/2A/validation/fingerprint={manifest_fingerprint}/
      · S0 MUST verify all three according to the standard Layer-1 bundle+flag hashing law.
      · 2B’s bundle/flag are explicitly NOT an input dependency for 3A.S0.

[3A policies & priors · part of the parameter set]
    - zone_mixture_policy_3A       (mixture / escalation policy for S1; theta thresholds/buckets)
    - country_zone_alphas_3A      (Dirichlet α-pack per country×tzid for S2)
    - zone_floor_policy_3A        (floor/bump rules for S2/S4 integerisation)
    - day_effect_policy_v1        (2B day-effect policy that 3A treats as governed input)

[Upstream data-plane & reference surfaces to be sealed (not interpreted by S0)]
    - outlet_catalogue            @ seed={seed} / fingerprint={manifest_fingerprint}     (1A egress: merchant×country×site stubs)
    - site_timezones              @ seed={seed} / fingerprint={manifest_fingerprint}     (2A egress: per-site tzid)
    - tz_timetable_cache          @ fingerprint={manifest_fingerprint}                   (2A cache; tz transitions)
    - tz_index_manifest           @ fingerprint={manifest_fingerprint} (if present)      (2A’s STR-tree / tz polygon index digest)
    - iso3166_canonical_2024, world_countries, tz_world_2025a, etc.                      (ingress references; country/tz universes)
    - any other 1A/2A validation summaries 3A states are allowed to read diagnostically

[Numeric, RNG & identity posture]
    - Identity triple: (parameter_hash, manifest_fingerprint, seed)
        · fixed by Layer-1 S0; S0 verifies formats but MUST NOT change them.
    - Numeric:
        · IEEE-754 binary64, round-to-nearest-even; no FMA/FTZ/DAZ on decision paths.
    - RNG:
        · 3A.S0 is **RNG-free**: MUST NOT consume Philox or call any RNG.
        · `verified_at_utc` MUST be derived from deterministic upstream evidence (e.g. upstream bundle metadata), not `now()`.
    - Partitioning:
        · All S0 outputs are fingerprint-scoped only: partition key `[fingerprint]`.
        · Write-once discipline for 3A.S0 outputs.


----------------------------------------------------------------------
DAG — 3A.S0 (Upstream gates → sealed input set 𝕊 → gate receipt)  [NO RNG]

[Schema+Dict],
[Numeric, RNG & identity posture]
                ->  (S0.1) Input identity triple & basic validation
                    - Receive or resolve `(parameter_hash, manifest_fingerprint, seed)` for this run.
                    - Validate:
                        · `parameter_hash`, `manifest_fingerprint` conform to `hex64`,
                        · `seed` conforms to `uint64`.
                    - Record the triple in memory; treat `seed` as metadata only:
                        · S0 MUST NOT branch or alter sealing behaviour based on `seed`.
                    - These values will be embedded into both S0 outputs.

[Schema+Dict]
                ->  (S0.2) Load catalogue artefacts
                    - Via the dataset dictionary and artefact registries (no raw paths), resolve:
                        · all schema packs listed under [Schema+Dict],
                        · dictionary entries and registry entries for:
                            - 1A/1B/2A validation bundles & flags,
                            - 1A/2A egress surfaces 3A may seal (outlet_catalogue, site_timezones, tz_timetable_cache, tz_index_manifest),
                            - 3A policy/prior artefacts.
                    - Validate:
                        · every `schema_ref` points to a valid anchor,
                        · IDs, `path` patterns, `owner_subsegment`, and `version` tags are self-consistent.
                    - Record a `catalogue_versions` snapshot (e.g. dictionary_version, registry_version) for later embedding.

[Schema+Dict],
[Upstream HashGates]
                ->  (S0.3) Resolve upstream bundles & flags via dictionary
                    - For each upstream segment S ∈ {1A,1B,2A}:
                        · use the dictionary and registry to resolve:
                              bundle_path_S   (validation_bundle_S root directory for this fingerprint),
                              flag_path_S     (_passed.flag for this fingerprint),
                              schema_ref_S    (index schema anchor and flag schema anchor).
                        · Load and validate:
                              index.json under bundle_path_S,
                              the flag file under flag_path_S.
                        - Assert index.json:
                             - lists only bundle members (no flags),
                             - each `path` is relative and ASCII-lex-sortable,
                             - no duplicates; all files exist.

[Upstream HashGates],
[Numeric, RNG & identity posture]
                ->  (S0.4) Compute bundle digests & verify flags
                    - For each upstream segment S ∈ {1A,1B,2A}:
                        1. Iterate the `index.json` entries in **ASCII-lex order of `path`**.
                        2. For each entry:
                               - open the referenced file under bundle_path_S,
                               - append its raw bytes to a SHA-256 stream.
                        3. Compute digest D_S = SHA256(concatenated bytes).
                        4. Parse `_passed.flag`:
                               - require exact single-line format `sha256_hex = <64 lowercase hex>`.
                        5. Compare:
                               - if `<64 hex>` ≠ D_S → Abort with `E3A_S0_001_UPSTREAM_GATE_FAILED` (UPSTREAM_GATE).
                    - On success, record for gate receipt:
                        · `upstream_gates.segment_1A/1B/2A.{bundle_path,flag_path,sha256_hex}`.

[Schema+Dict],
[3A policies & priors]
                ->  (S0.5) Resolve 3A policy/prior artefacts by ID
                    - Using the 3A dictionary & registry, resolve IDs:
                        · `zone_mixture_policy_3A`,
                        · `country_zone_alphas_3A`,
                        · `zone_floor_policy_3A`,
                        · `day_effect_policy_v1` (2B policy recognised as part of 3A’s parameter set).
                    - For each artefact:
                        · ensure an entry exists in the dictionary and registry,
                        · resolve to a concrete `path` (no guessing),
                        · confirm `schema_ref` points to a valid anchor in `schemas.3A.yaml` or an upstream pack.
                    - This step defines the governed policy set 𝓟 for this `(parameter_hash, manifest_fingerprint)`.

[3A policies & priors]
                ->  (S0.6) Compute per-policy/prior digests
                    - For each artefact in 𝓟:
                        · read its entire on-disk representation as a byte sequence,
                        · compute `sha256_hex_policy = SHA256(raw bytes)`.
                    - Record for each:
                        · `{logical_id, owner_segment, role, path, schema_ref, sha256_hex_policy}`.
                    - This set will become `sealed_policy_set` in the gate receipt and subset of `sealed_inputs_3A`.

[Schema+Dict],
[Upstream HashGates],
[Upstream data-plane & reference surfaces],
[3A policies & priors]
                ->  (S0.7) Determine sealed input set 𝕊 for `sealed_inputs_3A`
                    - Define 𝕊 as the union of:
                        1. Upstream gate artefacts (for documentation/diagnostics):
                            · `validation_bundle_1A` + `_passed.flag`,
                            · `validation_bundle_1B` + `_passed.flag`,
                            · `validation_bundle_2A` + `_passed.flag`.
                        2. Upstream data-plane surfaces 3A MAY read (even if S0 itself doesn’t interpret them):
                            · `outlet_catalogue@seed={seed}/fingerprint={manifest_fingerprint}`,
                            · `site_timezones@seed={seed}/fingerprint={manifest_fingerprint}`,
                            · `tz_timetable_cache@fingerprint={manifest_fingerprint}`,
                            · `tz_index_manifest@fingerprint={manifest_fingerprint}` (if published).
                        3. Reference data 3A states depend on structurally:
                            · `iso3166_canonical_2024`, `world_countries`, `tz_world_2025a`, etc.
                        4. 3A policies & priors 𝓟:
                            · `zone_mixture_policy_3A`,
                            · `country_zone_alphas_3A`,
                            · `zone_floor_policy_3A`,
                            · `day_effect_policy_v1`.
                    - 3A.S0 MUST ensure:
                        · every artefact later read by 3A.S1–S7 appears in 𝕊,
                        · later 3A states MUST NOT read artefacts absent from `sealed_inputs_3A`.

[Schema+Dict],
𝕊 from (S0.7)
                ->  (S0.8) Resolve each artefact in 𝕊 through the catalogue
                    - For each logical artefact in 𝕊:
                        · resolve its concrete path via the dataset dictionary and registry,
                        · confirm the resolved path’s tokens (e.g. seed, fingerprint) match the intended run,
                        · retrieve the governing `schema_ref`.
                    - S0 MUST NOT:
                        · invent paths,
                        · relax partitioning,
                        · or widen the sealed set beyond the governed universe.

[Numeric, RNG & identity posture],
𝕊 resolved
                ->  (S0.9) Compute SHA-256 digest per sealed input
                    - For each resolved artefact in 𝕊:
                        · read the on-disk content as a byte stream (dataset, policy, bundle, or flag),
                        · compute `sha256_hex = SHA256(raw bytes)`.
                    - Associate:
                        · `logical_id`, `owner_segment`, `artefact_kind`, `path`, `schema_ref`, `sha256_hex`, `role`.
                    - If upstream segments already publish canonical checksums that are part of the manifest,
                      S0 MAY re-use those instead of re-hashing, but the value appearing in `sealed_inputs_3A`
                      MUST still respect the “SHA-256 over bytes as written” law.

[Schema+Dict],
per-artefact rows from (S0.9)
                ->  (S0.10) Construct row set for `sealed_inputs_3A` in deterministic order
                    - Build one row per artefact in 𝕊 with at least:
                        · `manifest_fingerprint`,
                        · `logical_id` (dataset/artefact ID),
                        · `owner_segment`,
                        · `artefact_kind` (dataset, bundle, policy, reference),
                        · `path`,
                        · `schema_ref`,
                        · `sha256_hex`,
                        · `role` (e.g. upstream_gate, zone_prior, zone_mixture_policy, reference_geo, input_egress).
                    - Sorting:
                        · sort rows first by `owner_segment`,
                        · then by `logical_id` (lexicographically),
                        · then by `path` (lexicographically).
                    - Writer sort MUST follow this key so that replay yields byte-identical output.

(rows from S0.10),
[Schema+Dict]
                ->  (S0.11) Write `sealed_inputs_3A` (fingerprint-only, write-once)
                    - Use the dictionary entry for `sealed_inputs_3A`:
                        · path pattern: `data/layer1/3A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3A.parquet`,
                        · partition keys: `[fingerprint]`,
                        · schema_ref: `schemas.3A.yaml#/validation/sealed_inputs_3A`.
                    - Expand the `fingerprint={manifest_fingerprint}` token.
                    - Immutability:
                        · if the target partition is empty → allowed to write,
                        · if a dataset exists:
                              - allowed only if the bytes are **identical** to what S0 would write (idempotent re-run),
                              - otherwise Abort with an `IMMUTABILITY` error code.
                    - Write using staging:
                        · write Parquet to a temporary location,
                        · fsync, then atomically move into the dictionary path,
                        · ensure `manifest_fingerprint` column equals the partition token in every row.

[Upstream HashGates],
[3A policies & priors],
[Schema+Dict]
                ->  (S0.12) Derive `verified_at_utc` deterministically
                    - S0 MUST derive `verified_at_utc` from deterministic upstream evidence, e.g.:
                        · earliest or latest `created_utc` across upstream validation bundles,
                        · or an explicit timestamp embedded in the Layer-1 manifest.
                    - S0 MUST NOT:
                        · call system clock APIs,
                        · inject non-deterministic timestamps.
                    - For a fixed `(parameter_hash, manifest_fingerprint)`, `verified_at_utc` MUST be identical across reruns.

[Schema+Dict],
identity triple,
upstream gate records,
sealed policy set from (S0.6),
catalogue_versions from (S0.2),
verified_at_utc from (S0.12)
                ->  (S0.13) Assemble `s0_gate_receipt_3A` object
                    - Construct JSON object conforming to `schemas.3A.yaml#/validation/s0_gate_receipt_3A`:
                        · `version` (S0 contract version),
                        · `manifest_fingerprint`, `parameter_hash`, `seed`,
                        · `verified_at_utc`,
                        · `catalogue_versions`,
                        · `upstream_gates` map:
                              - per S ∈ {1A,1B,2A}:
                                    {bundle_path, flag_path, sha256_hex=D_S},
                        · `sealed_policy_set`:
                              - array of `{logical_id, owner_segment, role, sha256_hex, schema_ref}` for policy/prior artefacts,
                        · any optional notes/diagnostics permitted by the schema.
                    - The receipt MUST NOT add new gates or relax the obligations described in this spec.

(S0.13 receipt),
[Schema+Dict]
                ->  (S0.14) Write `s0_gate_receipt_3A` (fingerprint-only, write-once)
                    - Use dictionary entry for `s0_gate_receipt_3A`:
                        · path: `data/layer1/3A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3A.json`,
                        · partition keys: `[fingerprint]`,
                        · schema_ref: `schemas.3A.yaml#/validation/s0_gate_receipt_3A`.
                    - Expand `fingerprint={manifest_fingerprint}`.
                    - Immutability:
                        · if no file exists → allowed to write,
                        · if file exists:
                              - allowed only if bytes are bit-identical to new JSON (idempotent re-run),
                              - otherwise Abort with `IMMUTABILITY` error.
                    - Write JSON via staging → fsync → atomic move.
                    - After publish:
                        · re-open file and validate against schema anchor,
                        · confirm embedded `manifest_fingerprint` equals partition token.

Downstream touchpoints
----------------------
- **3A.S1–S5 (zone mixture, priors, shares, counts, egress):**
    - MUST treat `s0_gate_receipt_3A` as the authoritative gate for this fingerprint:
        · prove upstream 1A/1B/2A have PASSed,
        · discover which policy/prior artefacts were sealed (and with what digests),
        · discover `catalogue_versions`.
    - MUST treat `sealed_inputs_3A` as the *only* list of upstream data-plane and policy surfaces they may read.
      Any artefact not listed in `sealed_inputs_3A` MUST NOT be accessed by 3A.S1–S5.
- **3A.S6 (validation) & 3A.S7 (bundle & flag):**
    - Use `s0_gate_receipt_3A` as the upstream-gate evidence for 3A,
      and `sealed_inputs_3A` as the supply-chain manifest.
    - MUST NOT weaken S0’s upstream gate or sealed-input obligations.
- **Downstream segments (e.g. 2B, validation tooling):**
    - MUST honour 3A’s own HashGate (built in S7) when consuming `zone_alloc` or any 3A plan surface:
      **No PASS → No read** for Segment 3A outputs.
```