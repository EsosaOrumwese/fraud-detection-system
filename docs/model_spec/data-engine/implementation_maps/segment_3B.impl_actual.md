# Segment 3B Implementation Map (Actual)

Append-only implementation planning log for Segment 3B. Each entry documents
the design element, a short summary, and the detailed decision path. Do not
delete or rewrite prior entries.

---

## S0 - Gate & Environment Seal

### Entry: 2026-01-18 13:16

Context read and scope confirmation for 3B.S0.

Files read (expanded specs + contracts):
- `docs/model_spec/data-engine/layer-1/narrative/narrative_1A-to-3B.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s0.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s1.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s2.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s3.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s4.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s5.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3B/dataset_dictionary.layer1.3B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3B/artefact_registry_3B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3B/schemas.3B.yaml`

Key alignment checkpoints:
- 3B.S0 is RNG-free and control-plane only.
- HashGate inputs include 1A/1B/2A/3A validation bundles + _passed.flag.
- Sealed inputs include upstream egress metadata + virtual/CDN policy + external
  refs, including large assets (hrsl_raster, pelias bundle).
- `s0_gate_receipt_3B` requires `upstream_gates`, `sealed_policy_set`, and
  `digests` (fields optional but object required).
- `sealed_inputs_3B` uses row-object schema (same list-of-rows pattern as 3A).

---

### Entry: 2026-01-18 13:17

Decisions for S0 clarifications (anchored to prior segment implementation
choices and to the currently approved 3A/2B bundle laws).

Decision set:
1) **tz_timetable_cache optionality (gate vs warn).**
   - Choice: treat `tz_timetable_cache` as optional in S0.
   - Rationale: 2B.S0 treats caches as optional with WARN, and 3A.S0 uses the
     same optional-input pattern (include if present, warn if missing, fail if
     present but invalid). 3B.S0 should align to avoid blocking runs when a
     cache is not required by downstream 3B states.
   - Mechanics: include `tz_timetable_cache` in `sealed_inputs_3B` only when
     resolved + exists; log `optional_missing` when absent; fail closed if
     present but schema/digest invalid.

2) **Upstream bundle verification laws.**
   - Choice: use per-segment bundle law that matches the current outputs:
     - 1A/1B/2A: `index.json` validated to that segment's bundle index schema,
       then SHA-256 over raw bytes of each `index.path` in ASCII-lex order
       (exclude `_passed.flag`).
     - 3A: use the index-only law from the 3A.S7 implementation: SHA-256 over
       concatenated `members[].sha256_hex` in index order (because the bundle is
       index + `_passed.flag` only).
   - Rationale: 3A's bundle is index-only; hashing raw bytes is invalid and
     will not match `_passed.flag`. The other segments still use index->bytes.
   - Mechanics: implement a 3A gate branch that loads `index.json` and applies
     the index-only digest rule. Keep the 1A/1B/2A branch identical to 3A.S0.

3) **Pelias bundle integrity.**
   - Choice: validate `pelias_cached_bundle.sha256_hex` against the computed
     SHA-256 of `pelias_cached_sqlite`, then seal both artefacts separately.
   - Rationale: the bundle metadata explicitly carries the sqlite digest; this
     is a strong integrity check and matches the "fail closed on digest
     mismatch" posture used in 3A.S0 for concrete registry digests.
   - Mechanics: compute sqlite digest (streaming), parse bundle JSON, compare
     `sha256_hex`, fail if mismatch, then include both in sealed inputs.

4) **`digests` object in `s0_gate_receipt_3B`.**
   - Choice: emit keys for required artefacts only; omit keys for optional
     artefacts when missing.
   - Rationale: schema marks digests fields optional but forbids nulls; omitting
     missing optional digests keeps deterministic receipts and avoids writing
     placeholder values.
   - Mechanics: build `digests` from available artefacts; add a `notes` entry
     in the receipt if optional digests are absent.

5) **`hrsl_raster` hashing strategy.**
   - Choice: compute SHA-256 by streaming bytes of the raster file.
   - Rationale: aligns with 1B S0 handling for population rasters; registry
     digest is placeholder and cannot be trusted. Streaming is deterministic
     and avoids memory spikes.
   - Mechanics: read file in 1 MiB chunks with progress logs (elapsed/rate/ETA).

These decisions keep 3B.S0 behavior consistent with 1B/2A/2B/3A gate patterns,
while respecting the 3A index-only bundle law and the requirement to fail closed
on concrete digest mismatches.

---

### Entry: 2026-01-18 13:18

Pre-implementation plan for 3B.S0 (detailed, stepwise).

Plan:
1) **Load identity + run context.**
   - Resolve `run_receipt.json` (run_id, seed, parameter_hash,
     manifest_fingerprint). Enforce hex64 patterns and path-embed equality.
   - Initialize `RunPaths` and run log handler.

2) **Load contracts (via ContractSource).**
   - 3B dictionary + registry + schemas, plus upstream schemas/dictionaries for
     1A/1B/2A/3A and layer1/ingress packs.
   - Validate schema_ref anchors for all inputs referenced by 3B.S0.

3) **Upstream gate verification (HashGate).**
   - 1A/1B/2A: validate `index.json` schema, compute bytes digest, compare to
     `_passed.flag`, and record gate status.
   - 3A: load `index.json` (validation bundle index), compute index-only digest
     over `members[].sha256_hex` in order, compare to `_passed.flag`.
   - Abort on any mismatch or missing bundle/flag.

4) **Seal policy set and external refs.**
   - Policies/refs: `mcc_channel_rules`, `virtual_settlement_coords`,
     `cdn_weights_ext_yaml`, `cdn_country_weights`, `cdn_key_digest`,
     `virtual_validation_policy`, `virtual_logging_policy`,
     `route_rng_policy_v1`, `alias_layout_policy_v1`, `day_effect_policy_v1`,
     `hrsl_raster`, `pelias_cached_sqlite`, `pelias_cached_bundle`,
     `transaction_schema_merchant_ids`.
   - Compute sha256 digests (streaming for large files, directory hash for
     partitioned datasets). Validate schema refs where applicable.
   - Validate `pelias_cached_bundle` vs sqlite digest (fail if mismatch).

5) **Seal upstream egress metadata inputs.**
   - Required: `outlet_catalogue`, `site_locations`, `site_timezones`,
     `zone_alloc`, `zone_alloc_universe_hash`.
   - Optional: `tz_timetable_cache` (warn if missing; validate if present).
   - Hash partitioned datasets by streaming file bytes in ASCII-lex relative
     path order; avoid row scans.

6) **Build `sealed_inputs_3B` list + validate.**
   - Emit list-of-rows (object schema validated per row).
   - Sorted by `(owner_segment, artefact_kind, logical_id, path)` as per
     dictionary ordering.

7) **Build `s0_gate_receipt_3B` + validate.**
   - Populate version from registry semver; include identity + gates, and
     `sealed_policy_set` (logical_id/path/schema_ref/sha256/role).
   - Populate `digests` with available required artefact digests; omit missing
     optional digests; add `notes` when optional digests missing.
   - Use deterministic `verified_at_utc` from run_receipt (reuse existing on
     idempotent rerun).

8) **Publish outputs + run-report row.**
   - Atomic publish; if output exists and bytes match -> idempotent PASS.
   - Append `segment_state_runs` row for S0 (status, timing, error_code).

9) **Logging + progress.**
   - Story header: objective, gated inputs, outputs.
   - Gate logs include segment, bundle path, computed digest, PASS status.
   - Hashing logs include elapsed/rate/ETA for long loops (raster and bundles).

Planned tests:
- `make segment3b-s0` after upstream segments run; re-run to confirm immutability.
- Negative: corrupt `_passed.flag` to verify HashGate failure path.

---

### Entry: 2026-01-18 13:43

Implementation decisions while coding 3B.S0 (new items beyond the initial plan).

1) **Resolve `transaction_schema_merchant_ids` version via 1A sealed inputs.**
   - Problem: the 3B dictionary uses `path: reference/layer1/transaction_schema_merchant_ids/{version}/`
     but the run receipt does not carry a `version` token; leaving `{version}`
     unresolved makes path resolution fail.
   - Alternatives considered:
     - Require an explicit CLI arg for version (would change CLI/makefile and
       require manual operator input).
     - Scan the reference directory and pick the latest version (non-deterministic
       if multiple versions exist; violates determinism intent).
     - Read the 1A sealed inputs inventory (already deterministic for the run)
       to extract the version used by the upstream segment.
   - Decision: read `sealed_inputs_1A` (run-root metadata output of 1A.S0) and
     extract `partition.version` for `transaction_schema_merchant_ids`.
   - Rationale: aligns 3B to the exact merchant universe used by 1A; keeps
     determinism; avoids additional CLI parameters; uses upstream sealed metadata
     rather than scanning the filesystem.
   - Mechanics:
     - Load `sealed_inputs_1A` via dictionary_1A entry and validate against
       `schemas.1A.yaml#/validation/sealed_inputs_1A`.
     - Extract `partition.version` for `asset_id=transaction_schema_merchant_ids`.
     - Inject `tokens["version"]` before resolving 3B inputs.
     - Fail closed with `E3B_S0_005_SEALED_INPUT_RESOLUTION_FAILED` if missing.

2) **Upstream gates payload constrained to schema (no `bundle_path`).**
   - Problem: `schemas.3B.yaml#/validation/s0_gate_receipt_3B` defines gate
     objects with `bundle_id`, `flag_path`, `sha256_hex`, and `status` only.
   - Decision: drop `bundle_path` from `upstream_gates` entries (retain in logs).
   - Rationale: schema forbids extra fields; we keep path visibility in logs
     instead of the receipt to stay compliant.

3) **Receipt digest mapping clarified.**
   - Mapping decisions:
     - `virtual_rules_digest` -> `mcc_channel_rules`
     - `settlement_coord_digest` -> `virtual_settlement_coords`
     - `cdn_weights_digest` -> `cdn_country_weights` (the governed weights used
       downstream in 3B.S2/S3 and referenced by `edge_universe_hash_3B`)
     - `hrsl_digest` -> `hrsl_raster`
     - `virtual_validation_digest` -> `virtual_validation_policy`
     - `cdn_key_digest` -> `cdn_key_digest`
     - `tzdata_archive_digest`/`tz_index_digest` -> fields from
       `tz_timetable_cache.json` (only when cache present).
   - Rationale: aligns digest keys to the actual policy/artefacts downstream
     states consume; avoids ambiguity with raw external CDN weights.

4) **Segment-state run log omission.**
   - Problem: 3B dataset dictionary does not define `segment_state_runs`.
   - Decision: do not emit `segment_state_runs` rows for 3B.S0.
   - Rationale: avoid writing out-of-contract artefacts; keep outputs strictly
     to `s0_gate_receipt_3B` and `sealed_inputs_3B`.

---

### Entry: 2026-01-18 13:45

Registry syntax fix required to proceed with S0 execution.

Observation:
- `make segment3b-s0` failed while loading
  `docs/model_spec/data-engine/layer-1/specs/contracts/3B/artefact_registry_3B.yaml`
  due to YAML parse errors (mis-indented `hrsl_raster` block nested under
  `pelias_cached_bundle`).

Decision:
- Correct the indentation of the `hrsl_raster` entry so it is a top-level
  artifact entry alongside the other 3B artifacts.

Rationale:
- The registry must be parseable for `load_artefact_registry` to work.
- The intended structure is clear from the surrounding list items; this is a
  structural formatting fix, not a semantic contract change.

Action:
- Unindented the `# 5 POPULATION RASTER` header and `hrsl_raster` block by two
  spaces to align with other `- name:` entries in the `artifacts:` list.

---

### Entry: 2026-01-18 13:46

Second registry indentation fix (parse error persisted).

Observation:
- YAML parser still failed on `artefact_registry_3B.yaml`, now pointing to the
  `sealed_inputs_3B` entry (mis-indented list item).

Decision:
- Align the `sealed_inputs_3B` entry indentation with other `- name:` entries
  under `artifacts:` (two-space parent + two-space list + two-space item).

Action:
- Re-indented the `sealed_inputs_3B` block to the correct list depth and fixed
  the over-indented `type/category/...` fields.

---

### Entry: 2026-01-18 13:48

HRSL raster build fix to unblock S0 sealing.

Observation:
- `make segment3b-s0` failed because `artefacts/rasters/hrsl_100m.tif` was
  missing.
- `make hrsl_raster` failed: the script downloads the VRT into a temporary
  directory and then attempts to open it after the temp directory is deleted.
- The script's default local root points to
  `artefacts/rasters/source/hrsl_general`, but the repo contains
  `artefacts/rasters/source/hrsl/hrsl_general.vrt`.

Decision:
- Patch `scripts/build_hrsl_raster_3b.py` to keep temp files alive during
  processing and to use the existing local VRT directory by default.

Action:
- Updated `LOCAL_ROOT` default to `artefacts/rasters/source/hrsl`.
- Added a fallback to `hrsl_general.vrt` when `hrsl_general-latest.vrt` is
  missing.
- Reworked the temp-download branch to keep a `TemporaryDirectory` open until
  `rasterio.open` completes.

---

### Entry: 2026-01-18 13:54

HRSL build runtime constraint discovered.

Observation:
- Running `make hrsl_raster` now falls back to remote VRT streaming but is
  multi-hour in wall time (252k blocks; ETA hours). The CLI run timed out
  before completion, leaving only a partial `.tmp.tif`.

Decision:
- Treat `hrsl_raster` as an external large immutable artefact (per run-isolation
  guidance) and request an external-root path or a prebuilt file instead of
  forcing a full build inside the CLI timeout.

Next action (pending user input):
- If the user has `hrsl_100m.tif` elsewhere, add that directory to
  `ENGINE_EXTERNAL_ROOTS` or move the file into `artefacts/rasters/`.
- Otherwise, schedule a long-running offline build outside the CLI timeout
  and re-run `make segment3b-s0` afterward.
