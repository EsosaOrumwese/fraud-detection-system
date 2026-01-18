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

---

### Entry: 2026-01-18 14:26

HRSL acquisition path switched to AWS CLI sync + local VRT layout.

Problem:
- Remote VRT streaming is too slow; user requested that `make hrsl_raster`
  use AWS CLI instead of the HTTP/VRT downloader path.
- The S3 bucket layout places `hrsl_general-latest.vrt` under
  `hrsl-cogs/hrsl_general/`, but the build script only recognized VRTs at the
  local root and looked for tiles under `local_root/v1`.

Decision:
- Make `make hrsl_raster` sync the `hrsl_general/` prefix from S3 into
  `artefacts/rasters/source/hrsl/hrsl_general` before running the build.
- Update the build script to resolve local VRTs either at the root or inside
  `hrsl_general/` and to require local tiles when the caller requests it.

Rationale:
- AWS CLI sync is faster and more reliable than streaming the VRT over HTTP.
- The bucket layout matches `hrsl_general/` and should be treated as the
  canonical local layout after sync.
- Enforcing a local-only run in `make` prevents accidental fallback to
  remote streaming during long builds.

Implementation notes:
- `makefile`:
  - Added `HRSL_S3_BUCKET`, `HRSL_LOCAL_ROOT`, and `HRSL_S3_SYNC_CMD`.
  - `hrsl_raster` target now runs `aws s3 sync --no-sign-request` to fetch the
    VRT + tiles, then calls the Python script with `--local-root` and
    `--require-local`.
- `scripts/build_hrsl_raster_3b.py`:
  - Added `resolve_local_vrt()` to find `hrsl_general-latest.vrt` or
    `hrsl_general.vrt` under `local_root/` or `local_root/hrsl_general/`.
  - Added `--require-local` flag to fail closed if local tiles/VRT are missing.
  - Kept the remote VRT fallback for direct script runs without
    `--require-local`.

Validation plan:
- Run `make hrsl_raster` to ensure AWS sync completes and the build uses the
  local VRT layout.
- Re-run `make segment3b-s0` to confirm `hrsl_raster` sealing succeeds.

---

### Entry: 2026-01-18 16:27

HRSL local VRT selection corrected after tile path mismatch.

Problem:
- `make hrsl_raster` failed with `RasterioIOError` because the VRT referenced
  `v1/cog_*.tif` relative to its own directory, but the build script selected
  `artefacts/rasters/source/hrsl/hrsl_general.vrt` (at the parent root),
  causing GDAL to look for tiles at `artefacts/rasters/source/hrsl/v1/*` even
  though the AWS sync placed tiles under
  `artefacts/rasters/source/hrsl/hrsl_general/v1/*`.

Decision:
- Prefer VRTs that live alongside their `v1/` tile directory and only accept a
  VRT if a sibling `v1/` contains tiles.
- Align the Makefile default local root to the synced `hrsl_general/` directory
  so the VRT and tiles share the same parent path.

Implementation notes:
- `scripts/build_hrsl_raster_3b.py`:
  - `resolve_local_vrt()` now checks `vrt_path.parent/v1` for tiles and
    prioritizes VRTs under `local_root/hrsl_general/`.
- `makefile`:
  - `HRSL_LOCAL_ROOT` default set to
    `artefacts/rasters/source/hrsl/hrsl_general`.
  - `HRSL_S3_SYNC_CMD` now syncs directly into `$(HRSL_LOCAL_ROOT)` (no extra
    `/hrsl_general` suffix).

Validation plan:
- Re-run `make hrsl_raster` to confirm the build resolves
  `hrsl_general-latest.vrt` from the synced directory and reads tiles from the
  same `v1/` subfolder.

---

### Entry: 2026-01-18 18:40

Pelias bundle digest mismatch during S0 gate; rebuild decision.

Problem:
- `make segment3b-s0` failed at `E3B_S0_006_SEALED_INPUT_DIGEST_MISMATCH` for
  `pelias_cached_bundle.json` vs `pelias_cached.sqlite`.
- Current bundle/provenance report `sha256_hex = d0fd...` and bytes `56500224`,
  while the on-disk sqlite hashes to `5fce...` with bytes `56499549`.

Options considered:
1) Patch only `pelias_cached_bundle.json` to match the sqlite hash.
   - Fast, but leaves provenance inconsistent with the actual sqlite bytes.
2) Rebuild the sqlite bundle via the official script to regenerate both the
   sqlite and bundle/provenance in a consistent, auditable way.

Decision:
- Rebuild the pelias cached sqlite bundle using
  `scripts/build_pelias_cached_sqlite_3b.py` (via `make pelias_cached`) so the
  sqlite, bundle manifest, and provenance sidecar are aligned.

Rationale:
- The data-intake guide requires the bundle manifest to carry the sqlite hash
  and the provenance sidecar to record the raw inputs used. Rebuilding produces
  a coherent set and avoids silent inconsistencies.
- Rebuild cost is acceptable (GeoNames dumps are small relative to HRSL).

Plan:
- Run `make pelias_cached` to rebuild and refresh the three artefacts:
  `artefacts/geocode/pelias_cached.sqlite`,
  `artefacts/geocode/pelias_cached_bundle.json`,
  `artefacts/geocode/pelias_cached_bundle.provenance.json`.
- Re-run `make segment3b-s0` to verify the bundle digest check passes.
- Log the outcome in the logbook with hash/byte confirmation.

---

### Entry: 2026-01-18 18:41

S0 receipt schema violation: sealed_policy_set includes `notes`.

Problem:
- `make segment3b-s0` failed after sealing inputs because the receipt payload
  included a `notes` field in each `sealed_policy_set` item.
- `schemas.3B.yaml#/validation/s0_gate_receipt_3B` defines
  `sealed_policy_set` items with `additionalProperties: false` and does not
  permit `notes`.

Decision:
- Remove `notes` from `sealed_policy_set` items; keep required fields only
  (`logical_id`, `path`, `schema_ref`, `sha256_hex`, `role`, optional
  `owner_segment`).

Rationale:
- Preserve strict schema compliance for the receipt output. Versioning evidence
  is already enforced by the policy version checks; including it in the
  receipt is not allowed by contract and should remain in logs if needed.

Plan:
- Update the sealed policy append block in
  `packages/engine/src/engine/layers/l1/seg_3B/s0_gate/runner.py` to omit
  `notes`.
- Re-run `make segment3b-s0` to confirm schema validation passes.

---

### Entry: 2026-01-18 18:42

Pelias rebuild + sealed_policy_set fix applied; S0 green.

Actions taken:
- Ran `make pelias_cached` to rebuild the pelias cached bundle.
  - New sqlite digest: `c81dd6418a1e4d0f464c13955d4bd36bd5fe5467147c9c6c460384dbb3d54e5c`
  - Bytes: `56799232`
  - Bundle/provenance now match the sqlite digest and bytes.
- Removed the `notes` field from `sealed_policy_set` items in
  `packages/engine/src/engine/layers/l1/seg_3B/s0_gate/runner.py`.
- Re-ran `make segment3b-s0`; S0 completed successfully with receipt and
  sealed inputs written.

Outcome:
- 3B.S0 gate passes and output schema validates.

---

### Entry: 2026-01-18 19:47

3B.S1 spec review + implementation plan (virtual classification + settlement nodes).

Scope recap (from spec + contracts):
- Outputs: `virtual_classification_3B`, `virtual_settlement_3B` (parquet, keyed
  by `merchant_id`, partitioned by `{seed, manifest_fingerprint}`).
- Inputs: S0 gate (`s0_gate_receipt_3B`, `sealed_inputs_3B`), merchant universe
  (`transaction_schema_merchant_ids`), policy (`mcc_channel_rules`),
  settlement coords (`virtual_settlement_coords`), and optional upstream egress
  (`outlet_catalogue`, `site_locations`, `site_timezones`, `zone_alloc`).
- RNG-free, deterministic; S1 is sole authority for virtual membership and
  settlement nodes. No HashGate outputs.

Key spec/contract reconciliations to implement:
- `decision_reason` enum in schema is `[RULE_MATCH, OVERRIDE_ACCEPT,
  OVERRIDE_DENY, DEFAULT_GUARD]`. The S1 spec mentions `NO_RULE_MATCH` but
  allows “equivalent enum.” Plan: map no-rule to `DEFAULT_GUARD`.
- `tz_source` enum in schema is `[INGEST, OVERRIDE, DERIVED]` while the spec
  text uses `INGESTED/POLYGON/OVERRIDE`. Plan: use schema values; map
  ingested tzid to `INGEST`, polygon-derived to `DERIVED`, override to
  `OVERRIDE`.
- `virtual_mode` exists in schema but not in the spec text. Plan: set
  `VIRTUAL_ONLY` for `is_virtual=1`, `NON_VIRTUAL` for `is_virtual=0`;
  reserve `HYBRID` for future policies (no v1 signal).

Plan (stepwise; aligned to earlier segment style):
1) **Bootstrap + identity checks**
   - Load run receipt (run_id/seed/manifest_fingerprint/parameter_hash).
   - Load + validate `s0_gate_receipt_3B` and `sealed_inputs_3B` against
     `schemas.3B.yaml#/validation/*`.
   - Assert `segment_id=3B`, `state_id=S0`, same `manifest_fingerprint`, and
     `seed`/`parameter_hash` match current run.
   - Verify `upstream_gates` PASS for 1A/1B/2A/3A.
   - Verify contract triplet compatibility with S0 `catalogue_versions`
     (same pattern as prior states).

2) **Sealed input lookup & preflight**
   - Build `sealed_inputs` map by `logical_id`.
   - Require at least: `transaction_schema_merchant_ids`, `mcc_channel_rules`,
     `virtual_settlement_coords`, `pelias_cached_sqlite`, `pelias_cached_bundle`,
     `cdn_weights_ext_yaml` (present in sealed inputs even if not used directly).
   - For each required entry: confirm path exists and schema_ref resolvable;
     for small assets (policy + coords) recompute digest and compare to
     `sha256_hex`.
   - Capture S0 digests for policy + coords: `virtual_rules_digest`,
     `settlement_coord_digest`. Use these as output provenance fields.

3) **Load merchant universe**
   - Resolve `transaction_schema_merchant_ids` path from sealed_inputs.
     If a directory, locate the single parquet member deterministically
     (sorted glob, fail if 0 or >1).
   - Read with polars; enforce required columns:
     `merchant_id`, `mcc`, `channel`, `home_country_iso` or `legal_country_iso`
     (policy only needs `mcc` + `channel` today, but validate required set).
   - Validate uniqueness of `merchant_id` (fail if duplicates).
   - Sort by `merchant_id` for deterministic output ordering.

4) **Load and validate policy**
   - Load `mcc_channel_rules.yaml` and validate against
     `schemas.3B.yaml#/policy/virtual_rules_policy_v1`.
   - Build rule map keyed by `(mcc, channel)`, enforcing uniqueness.
   - Extract `policy_version` from the policy payload; use S0 registry
     `manifest_key` as `source_policy_id`.

5) **Classification surface**
   - Normalize `mcc` to zero-padded 4-digit string for rule lookups.
   - Determine `decision` for each merchant:
     * match rule -> `is_virtual = decision=="virtual"`,
       `decision_reason="RULE_MATCH"`.
     * no match -> `is_virtual=0`, `decision_reason="DEFAULT_GUARD"`.
   - Populate columns per schema:
     * `virtual_mode` = `VIRTUAL_ONLY` if virtual else `NON_VIRTUAL`.
     * `rule_id`, `rule_version` = null (v1 policy has no rule IDs).
     * `source_policy_id` = registry `manifest_key` for `mcc_channel_rules`.
     * `source_policy_version` = policy `version`.
     * `classification_digest` = `virtual_rules_digest` from S0 receipt.
     * `notes` left null (no freeform spec requirement).

6) **Settlement nodes**
   - Load `virtual_settlement_coords.csv`; validate against
     `schemas.3B.yaml#/reference/virtual_settlement_coords_v1`.
   - Require unique `merchant_id` in coords. (Fail if duplicates.)
   - Join coords to virtual merchants (`is_virtual=1`); fail if any virtual
     merchant missing coords (unless an explicit partial-coverage flag is
     introduced).
   - Construct `settlement_site_id` per spec §6.7:
     `sha256("3B.SETTLEMENT" + 0x1F + str(merchant_id)) -> low64 -> 16-hex`.
   - `tzid_settlement` from coords; fail if null (v1 coords provide tzid).
   - `tz_source` = `INGEST`.
   - `coord_source_id` = `coord_source` from coords (fallback to logical_id
     if null).
   - `coord_source_version` = `coordinate_batch` from
     `virtual_settlement_coords.provenance.json` (fallback to empty error).
   - `settlement_coord_digest` = S0 `settlement_coord_digest`.
   - `tz_policy_digest` = S0 `tz_index_digest` if present; else
     `tzdata_archive_digest` (requires a decision).

7) **Validate + write outputs**
   - Validate both outputs against `schemas.3B.yaml#/plan/*`.
   - Write to canonical dataset paths from dictionary.
   - Use temp dir + atomic move; if existing outputs found:
     * If byte-identical, treat as no-op.
     * If different, abort with output inconsistency error.

8) **Run report**
   - Emit `s1_run_report_3B` using `schemas.layer1.yaml#/run_report/segment_state_run`
     with counts (merchants total, virtual merchants, settlement rows) and
     input digests used.

9) **Logging + observability**
   - Story header: objective, gated inputs, outputs.
   - Log counts: merchant universe size, rule count, virtual count, coords
     coverage, settlement rows.
   - For any long loops (if not vectorised), log progress with elapsed/rate/ETA.
   - Log path + digest summaries for sealed inputs and outputs.

Open decisions/questions to confirm with user:
- `decision_reason` mapping for “no rule”: use `DEFAULT_GUARD` (schema-compliant)
  vs introduce `NO_RULE_MATCH` (schema change).
- `virtual_mode` mapping: default to `NON_VIRTUAL`/`VIRTUAL_ONLY` only.
- `tz_source` vocabulary mismatch: use schema enums `INGEST/DERIVED/OVERRIDE`.
- `tz_policy_digest` source: prefer S0 `tz_index_digest`; confirm if S1 should
  instead use the tzdata archive digest or the sealed_inputs digest for
  `tz_timetable_cache`.

---

### Entry: 2026-01-18 19:59

S1 decisions confirmed; implementation begins.

Confirmed decisions (per user approval):
- `decision_reason`: use `DEFAULT_GUARD` for no-rule cases (schema-compliant).
- `virtual_mode`: set `VIRTUAL_ONLY` for `is_virtual=1`, `NON_VIRTUAL` for
  `is_virtual=0`; `HYBRID` unused in v1.
- `tz_source`: use schema enum values `INGEST/DERIVED/OVERRIDE` (map ingested
  tzid to `INGEST`).
- `tz_policy_digest`: use `tz_index_digest` from `s0_gate_receipt_3B`
  (fallback to `tzdata_archive_digest` if index digest missing).

Implementation approach chosen:
- Follow 3A.S1 runner pattern: validate S0 receipt + sealed inputs, verify
  required sealed artefacts and digests, then compute classification and
  settlement outputs in a deterministic order using polars and atomic publish.
- Use v1 `mcc_channel_rules` exact match lookup (no overrides/priorities).
- Derive `settlement_site_id` per §6.7 hash law
  (`SHA256("3B.SETTLEMENT" + 0x1F + merchant_id)` -> low64 -> 16-hex).

Next steps:
- Implement `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`.
- Add CLI entrypoint and Makefile target (`segment3b-s1`).
- Run `make segment3b-s1` and fix any failures; log decisions as they arise.

---

### Entry: 2026-01-18 20:22

S1 implementation details (initial build).

Key mechanics implemented:
- Runner at `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`
  mirrors the 3A.S1 structure:
  - Load run receipt, attach run log, load 3B dictionary/registry + schema packs.
  - Validate `s0_gate_receipt_3B` and `sealed_inputs_3B`, enforce upstream PASS.
  - Build `sealed_by_id`, require `transaction_schema_merchant_ids` and parse the
    `{version}` token from its sealed path to resolve dictionary paths.
  - Verify required sealed assets with digest comparisons (policy, coords, merchant
    ids, pelias, cdn weights).
  - Apply `mcc_channel_rules` exact-match table to `merchant_id` universe to
    produce `virtual_classification_3B`.
  - Join `virtual_settlement_coords` to virtual merchants only, enforce tzid
    presence, and construct `settlement_site_id` via the SHA256 low64 law.
  - Validate both outputs against `schemas.3B.yaml#/plan/*`, write parquet to
    temp dirs, then atomic publish with immutability check.
  - Emit `s1_run_report_3B` with counts + digests.

Sidecar provenance decision:
- `coord_source_version` is populated from
  `artefacts/virtual/virtual_settlement_coords.provenance.json` (`coordinate_batch`).
  Treated as a required sidecar for the `virtual_settlement_coords` dataset
  (fail closed if missing), despite not being a separate sealed input row.
  Rationale: schema requires `coord_source_version` and the data-intake guide
  defines it as part of the coordinate artefact bundle.

Immutability handling for paired outputs:
- Added `_atomic_publish_pair()` to ensure both `virtual_classification_3B` and
  `virtual_settlement_3B` are either both published or both rejected when
  existing partitions are present; detects partial outputs and fails closed.

CLI + Makefile wiring:
- `packages/engine/src/engine/cli/s1_virtual_classification_3b.py`
  entrypoint added.
- Makefile updated with `SEG3B_S1_*` args + `segment3b-s1` target.

Pending verification:
- Run `make segment3b-s1` to confirm green and validate outputs.

---

### Entry: 2026-01-18 20:23

S1 fixes after first run attempt.

Issue 1: S0 receipt identity fields.
- Observed: `s0_gate_receipt_3B` does not include `segment_id`/`state_id` fields
  (schema only includes `version`, `manifest_fingerprint`, `seed`,
  `parameter_hash`, `upstream_gates`, `sealed_policy_set`, `digests`).
- Decision: remove the `segment_id/state_id` check from S1. Keep the
  `manifest_fingerprint`, `seed`, and `parameter_hash` checks as authoritative.

Issue 2: EngineFailure attribute mismatch.
- Observed: `EngineFailure` exposes `failure_code`, not `error_code`.
- Decision: use `exc.failure_code` to populate run-report error_code.

Next action:
- Re-run `make segment3b-s1` and address any further issues.

---

### Entry: 2026-01-18 20:26

S1 merchant_id type failure planning.

Problem:
- `make segment3b-s1` fails at merchant_universe with Polars error "conversion from u64 to i64 failed in column merchant_id for 625 values".
- Root cause: S1 casts merchant_id to `pl.Int64`, but the id64 contract is uint64 and the ingress parquet includes values above signed 64-bit range.

Options considered:
1) Keep `Int64` and clamp or modulo values.
   - Rejected: violates the id64 contract and determinism expectations.
2) Coerce merchant_id to string.
   - Rejected: schema requires integer id64 and downstream joins assume numeric keys.
3) Use `UInt64` consistently across the S1 pipeline (merchant ids + settlement coords).
   - Accepted: aligns with schema and existing layer-1 patterns, preserves full range.

Decision:
- Replace the S1 merchant_id cast with `pl.UInt64`.
- After validating `virtual_settlement_coords`, cast its merchant_id to `pl.UInt64` so join keys are aligned.

Planned edits:
- `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`: swap `pl.Int64` -> `pl.UInt64` for merchant_df; add a `pl.UInt64` cast for coords_df before duplicate/join checks.
- Re-run `make segment3b-s1` and record any new failures in the implementation map/logbook.

Invariants to preserve:
- Merchant ids remain unsigned 64-bit (`id64`); schema validation order stays the same.
- No changes to digesting or manifest handling.

Logging:
- Keep existing story/progress logs; only add logging if new error context is needed.

---

### Entry: 2026-01-18 20:30

S1 failure: StepTimer formatting error.

Problem:
- `make segment3b-s1` now fails in `merchant_universe` with `_StepTimer.info() takes 2 positional arguments but 4 were given`.
- Root cause: `_StepTimer.info(message)` only accepts a single formatted message string, but several call sites pass logger-style format args.

Options considered:
1) Expand `_StepTimer.info` signature to accept `*args` and perform formatting.
   - Would change helper API and potentially hide formatting mistakes.
2) Keep `_StepTimer.info` as-is and pre-format strings at each call site.
   - Minimal change; consistent with intent of StepTimer as a simple wrapper.

Decision:
- Update the three call sites to pass a fully formatted string (f-string) into `_StepTimer.info`.

Planned edits:
- `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`: convert `timer.info` calls for merchant universe, classification, and settlement nodes to f-strings.
- Re-run `make segment3b-s1` and log the result.

---

### Entry: 2026-01-18 20:32

S1 classification failure: Polars treating decision constants as column names.

Problem:
- `make segment3b-s1` now fails in `classification` with `error_context.detail="DEFAULT_GUARD"`.
- The only place that literal appears in the classification phase is the `pl.when(...).then(_DECISION_DEFAULT)` expression.
- Polars treats bare strings in expressions as column references in some contexts; missing column "DEFAULT_GUARD" triggers a `ColumnNotFound`-style error, surfaced as detail "DEFAULT_GUARD".

Options considered:
1) Add a column named `DEFAULT_GUARD` (nonsense).
2) Wrap constants in `pl.lit(...)` to force literal values.
   - Aligns with other layer-1 code (explicit `pl.lit` usage).

Decision:
- Wrap `_DECISION_DEFAULT`, `_DECISION_RULE_MATCH`, `_VIRTUAL_MODE_*` in `pl.lit` when used in `pl.when` expressions.

Planned edits:
- `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`: update the classification `with_columns` block to use `pl.lit` for string constants.
- Re-run `make segment3b-s1` and record results.

---

### Entry: 2026-01-18 20:34

S1 settlement coords CSV parse failure due to int64 inference.

Problem:
- `virtual_settlement_coords.csv` contains merchant_id values above signed 64-bit range.
- `pl.read_csv` infers `i64` and fails parsing (error: could not parse ... as dtype i64).

Options considered:
1) Increase `infer_schema_length` to scan more rows.
   - Does not fix signed-vs-unsigned; still `i64`.
2) Allow parse errors (`ignore_errors=True`) and fill nulls.
   - Masks invalid data; violates spec (merchant_id must be present).
3) Provide explicit schema override for `merchant_id` as `UInt64`.
   - Aligns with id64 contract and avoids parse failure.

Decision:
- Pass `schema_overrides={"merchant_id": pl.UInt64}` to `pl.read_csv` for coords.

Planned edits:
- `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`: update `pl.read_csv(coords_path)` to set `schema_overrides` for `merchant_id`.
- Re-run `make segment3b-s1` and log any follow-up failures.

---

### Entry: 2026-01-18 20:35

S1 settlement coords validation failing on unresolved layer1 defs.

Problem:
- `validate_dataframe` on `reference/virtual_settlement_coords_v1` now errors with `Unresolvable: schemas.layer1.yaml#/$defs/id64`.
- The JSON schema adapter uses `$defs` from the local pack; `schemas.3B.yaml` keeps `id64` as an external ref to `schemas.layer1.yaml`, which is not inlined for table validation.

Options considered:
1) Skip validation for coords.
   - Rejected: would violate spec contract checks.
2) Extend jsonschema_adapter to resolve external packs.
   - Larger change; unnecessary for this state.
3) Inline external layer1 refs into the specific table schema before validation.
   - Matches patterns in other segments (e.g., 2B S1 output validation).

Decision:
- Call `_inline_external_refs(..., schema_layer1, "schemas.layer1.yaml#")` on the coords table pack and on output table packs before `validate_dataframe`.

Planned edits:
- `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`: inline layer1 defs for `reference/virtual_settlement_coords_v1`, `plan/virtual_classification_3B`, and `plan/virtual_settlement_3B`.
- Re-run `make segment3b-s1` and log any follow-on issues.

---

### Entry: 2026-01-18 20:37

S1 unresolved id64 persists after inlining table nodes.

Observation:
- Validation still fails with `Unresolvable: schemas.layer1.yaml#/$defs/id64`.
- The table columns reference `#/$defs/id64`, and the pack's `$defs.id64` is itself a `$ref` to `schemas.layer1.yaml#/$defs/id64`.
- Inlining only the table node does not update the pack `$defs`, so the external ref remains.

Decision:
- Inline external refs on the entire table pack (including `$defs`), not just the table node.

Planned edits:
- `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`: replace `_inline_external_refs(pack[table], ...)` with `_inline_external_refs(pack, ...)` for coords and output packs.
- Re-run `make segment3b-s1`.

---

### Entry: 2026-01-18 20:38

S1 settlement_join failure: coord_source default literal treated as column name.

Problem:
- Failure detail `virtual_settlement_coords` during `settlement_join` after the join succeeded.
- The only place that literal is used in this phase is the `coord_source_id` default:
  `pl.when(...).then("virtual_settlement_coords")...`.
- Polars treats bare strings in expressions as column references; missing column triggers a `ColumnNotFound` error surfaced as the literal name.

Decision:
- Wrap the default string in `pl.lit("virtual_settlement_coords")`.

Planned edits:
- `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`: update `coord_source_id` expression to use `pl.lit`.
- Re-run `make segment3b-s1`.

---

### Entry: 2026-01-18 20:39

S1 execution outcome.

- Re-ran `make segment3b-s1` after the dtype + schema inlining + `pl.lit` fixes.
- S1 now completes successfully and publishes `virtual_classification_3B`, `virtual_settlement_3B`, and `s1_run_report_3B` for run_id `970b0bd6833be3a0f08df8e8abf0364c`.
- Counts observed: `merchants_total=10000`, `virtual_merchants=309`, `settlement_rows=309`.

---

### Entry: 2026-01-18 20:46

3B.S2 spec review + implementation planning (initial).

Problem framing:
- Implement 3B.S2 (CDN edge catalogue construction) per `state.3B.s2.expanded.md`.
- S2 is first RNG-bearing 3B state; must be deterministic, policy-governed, and emit RNG events/logs.
- Must consume S1 outputs + sealed inputs; produce `edge_catalogue_3B` + `edge_catalogue_index_3B` with strict partition/ordering + RNG logs.

Key inputs/contracts (authoritative):
- S0 gate + sealed inputs:
  - `s0_gate_receipt_3B` (`schemas.3B.yaml#/validation/s0_gate_receipt_3B`).
  - `sealed_inputs_3B` (`schemas.3B.yaml#/validation/sealed_inputs_3B`).
- S1 outputs:
  - `virtual_classification_3B`, `virtual_settlement_3B` (`schemas.3B.yaml#/plan/*`).
- Policy/refs for S2:
  - `cdn_country_weights` (`schemas.3B.yaml#/policy/cdn_country_weights_v1`).
  - `cdn_key_digest` (sealed; may be echoed or used for RNG domain separation).
  - `route_rng_policy_v1` (`schemas.2B.yaml#/policy/route_rng_policy_v1`).
  - `hrsl_raster` (ingress). 
  - Spatial/tz assets: `tile_index`, `tile_weights`, possibly `tile_bounds`, `world_countries`, `tz_world_2025a`, `tz_overrides`, `tz_nudge`, `tz_timetable_cache` (per spec). 
- Output datasets:
  - `edge_catalogue_3B`, `edge_catalogue_index_3B` (`schemas.3B.yaml#/plan/*`), with ordering in dictionary.
  - RNG logs: `rng_event_edge_tile_assign`, `rng_event_edge_jitter`, `rng_audit_log`, `rng_trace_log` (`schemas.layer1.yaml#/rng/...`).

Observed gaps vs spec:
- Current `sealed_inputs_3B` for the active run does not include `tile_index`, `tile_weights`, `tile_bounds`, `world_countries`, or `tz_world_2025a` (only site_locations/timezones, tz_timetable_cache, hrsl_raster, etc.). S2 spec requires spatial/tz assets to be sealed. This likely needs S0 updates before S2 can run.
- `route_rng_policy_v1` (schema + config) currently defines only `routing_selection` and `routing_edge` streams; no 3B.S2 substreams for `edge_tile_assign` / `edge_jitter` are present. Need a decision on how to source RNG stream IDs and budgets for S2.

Baseline algorithm choice (aligned with spec + existing contracts):
- Use the v1 `cdn_country_weights` policy as the sole edge-budget authority:
  - `edge_scale` -> total edges per merchant (E). No merchant classes/overrides because v1 schema lacks those fields.
  - Country allocation via largest-remainder integerisation (per authoring guide).
- Use 1B tiling surfaces for spatial allocation:
  - For each country, use `tile_weights` (weight_fp + dp) to form per-tile weights `w_tile`, normalised by country.
  - If `tile_bounds` is available, use it for jitter bounds; otherwise compute bounds from `hrsl_raster` + row/col in `tile_index`.
- RNG usage confined to jitter (Phase D). Optional `edge_tile_assign` stream only if we introduce random permutations; otherwise skip tile-assign RNG events and keep allocation deterministic.
- Timezone resolution: reuse 2A-style tz lookup (tz_world + nudge + overrides), but apply to edge coordinates. Use `tz_source` values: `POLYGON` for direct polygon match; `OVERRIDE` when override applied; `NUDGE` for nudge-only resolution if policy requires (schema supports `NUDGE`).
- Edge id law: follow spec 6.7.1 (SHA256 of `"3B.EDGE" + 0x1F + merchant_id + 0x1F + edge_seq_index`, low64 hex). Use deterministic edge ordering to assign `edge_seq_index` (e.g., sort by merchant_id, country_iso, tile_id, jitter_rank).
- Edge digest: compute per-edge digest over canonical row fields (excluding itself) in a documented order; index digest per-merchant/global derived from ordered edge digests per spec.

Implementation plan (stepwise, with decisions + logging):
1) **Contract + gating checks (Phase A)**
   - Load run receipt; resolve seed/parameter_hash/manifest_fingerprint.
   - Validate `s0_gate_receipt_3B` + `sealed_inputs_3B` with schema; verify upstream gate PASS; confirm identity fields.
   - Validate S1 outputs `virtual_classification_3B` + `virtual_settlement_3B`; enforce 1:1 mapping for virtual merchants.
   - Build `V` from `virtual_classification_3B.is_virtual`.
   - Log story header: objective, gated inputs, intended outputs (narrative per AGENTS).

2) **Resolve + validate sealed inputs**
   - Build `sealed_by_id` from `sealed_inputs_3B`.
   - Require `cdn_country_weights`, `cdn_key_digest`, `route_rng_policy_v1`, `hrsl_raster` and spatial/tz assets (tile_index/tile_weights/tile_bounds, world_countries, tz_world_2025a, tz_overrides, tz_nudge). Fail closed if missing.
   - Validate policy YAML via `schemas.3B.yaml#/policy/cdn_country_weights_v1`.
   - Confirm digests match sealed inputs when hardened mode is enabled.

3) **Phase B (RNG-free edge budgets)**
   - Parse `cdn_country_weights` (version, edge_scale, countries list).
   - For each merchant in V:
     - `E_total = edge_scale` (int).
     - Determine `C_m` as all policy countries with weight>0.
     - Compute `T_m(c) = E_total * weight(c)` and integerise with largest remainder (tie-break ISO2 asc).
   - Log counts (total virtual merchants, edges per merchant min/avg/max).

4) **Phase C (RNG-free tile allocation)**
   - Load tile weights for each country; convert `weight_fp` + `dp` -> float weights; normalise per country.
   - Integerise per-country edge counts into tile counts using largest remainder (tie-break by tile_id).
   - Optional: keep a per-merchant in-memory plan, or emit a temporary plan file for resumability.

5) **Phase D (RNG-bearing jitter + RNG logs)**
   - Use Philox to generate `u_lon`, `u_lat` for each edge slot.
   - Jitter inside tile bounds; verify inside country polygon (world_countries). Retry up to `JITTER_MAX_ATTEMPTS` (policy default; will define from spec or config).
   - Emit `rng_event_edge_jitter` for each attempt; include envelope (stream_id, counters, blocks/draws), edge_seq_index, attempt, accepted.
   - If `edge_tile_assign` RNG stream is required, emit events when performing any random permutation; otherwise skip and rely on deterministic ordering.
   - Append/maintain `rng_trace_log` and `rng_audit_log` per existing Layer-1 patterns (reuse 1B S5/S6 utilities).

6) **Phase E (tz resolution)**
   - Build tz-world index once (reuse 2A tz lookup utilities) and apply to edge coordinates.
   - Apply nudge + overrides; set `tz_source` accordingly.
   - Fail closed if any edge lacks tzid.

7) **Phase F (edge catalogue + index)**
   - Assemble edge rows with required columns: merchant_id, edge_id, edge_seq_index, country_iso, lat/lon, tzid_operational, tz_source, edge_weight, hrsl_tile_id (tile_id), spatial_surface_id, cdn_policy_id/version, rng_stream_id/event_id, sampling_rank, edge_digest.
   - Sort by dictionary writer_sort (merchant_id, edge_id) before writing parquet.
   - Compute per-merchant and global digests for `edge_catalogue_index_3B` using canonical ordering; write index parquet.
   - Atomic publish both outputs; if outputs exist, compare digests and fail on mismatch.

8) **Validation + invariants**
   - Enforce schema validation on outputs (inline layer1 defs where needed).
   - Check counts: edge_count_total == row count per merchant; global totals match.
   - Verify RNG event counts align with edges placed.
   - Record run report with counts + digests + policy ids/versions.

Performance + memory considerations:
- Use streaming/batched processing per merchant or per country to avoid building full edge arrays in memory.
- For jitter, use chunked loops with progress logs including elapsed/rate/ETA.
- Avoid reading full tile surfaces repeatedly; cache per-country tile arrays with capped LRU (similar to 1B.S6).

Resumability hooks:
- Use temp output dirs + atomic publish; detect existing partitions and skip if identical.
- RNG logs: append trace/audit only if missing for this run_id; skip event emission if already present.

Open questions / decisions to confirm with user before coding:
1) **RNG policy source:** `route_rng_policy_v1` lacks S2 streams. Should we extend it (new stream IDs + budgets), or introduce a 3B-specific RNG policy artefact? If extending, preferred stream_id/substream labels? 
2) **Spatial surfaces:** Should S2 use `tile_bounds` if present, or compute bounds from HRSL raster + row/col? If tile_bounds is not sealed today, should we update S0 to seal it (and tile_index/tile_weights/world_countries/tz_world) before S2?
3) **Edge weights:** Should `edge_weight` be uniform per edge (sum=1 per merchant), or proportional to country/tile weights? (Spec allows both with documented law.)
4) **Edge id ordering:** Confirm `edge_seq_index` ordering key (recommended: country_iso, tile_id, jitter_rank) and 0-based vs 1-based.
5) **TZ resolution:** Should we reuse 2A tz lookup logic directly (including nudge + overrides), and map `tz_source` to `POLYGON/OVERRIDE/NUDGE`? Any simplified mode acceptable?
6) **Edge digest law:** Confirm canonical digest formula for `edge_digest` and `edge_catalogue_index_3B` (per-merchant + global) if a specific law exists beyond the general guidance.

Next action once clarified:
- Update S0 sealing to include missing spatial/tz assets (if required), then implement S2 runner + CLI + Makefile target, and run `make segment3b-s2` until green.

---

### Entry: 2026-01-18 20:48

3B.S2 decisions confirmed (user approved).

Decisions locked:
- **RNG policy source**: Extend `route_rng_policy_v1` to include a 3B.S2 stream for edge jitter (and optional edge_tile_assign). Update `schemas.2B.yaml` + `config/layer1/2B/policy/route_rng_policy_v1.json` accordingly, then validate in S2.
- **Sealed spatial/tz assets**: Update 3B.S0 sealing to require and record `tile_index`, `tile_weights`, `tile_bounds`, `world_countries`, `tz_world_2025a`, `tz_nudge`, and `tz_overrides` so S2 reads only sealed inputs.
- **Edge weights**: Uniform per-edge weights per merchant (sum=1.0 per merchant). No proportional weighting beyond deterministic country/tile allocations.
- **Edge ordering**: `edge_seq_index` is 0-based; ordering by `(merchant_id, country_iso, tile_id, jitter_rank)`; `edge_id` uses SHA256("3B.EDGE" + 0x1F + merchant_id + 0x1F + LE32(edge_seq_index)) -> low64 hex.
- **Timezone resolution**: Reuse 2A-style tz_world + nudge + overrides. For overrides, apply country-level overrides (scope=country); set `tz_source` as POLYGON/NUDGE/OVERRIDE.
- **Digest law**: `edge_digest` = SHA256 of canonical JSON of row fields (excluding edge_digest), per-merchant digest = SHA256 concatenation of edge_digest values in edge_id order, global digest = SHA256 concatenation of per-merchant digests in merchant_id order.

Implementation impacts:
- Contracts update for new route_rng_policy stream schema; config update for policy file.
- 3B dictionary + registry updates to expose upstream tile/tz assets; 3B.S0 required sealed inputs list expanded.
- 3B.S2 runner will implement deterministic Phase A-F algorithm with RNG events + progress logging, and outputs `edge_catalogue_3B` + `edge_catalogue_index_3B`.

---

### Entry: 2026-01-18 21:21

S2 implementation plan refinements before coding.

Decisions (additional to 20:48 approvals):
- Precompute country edge budgets once (edge_scale is global) and reuse for all virtual merchants to avoid repeating integerisation per merchant.
- Precompute per-country tile allocations once (tile_weights + edges_per_country) and reuse per merchant. This makes the per-merchant loop a deterministic expansion + jitter pass.
- Use tile_bounds as jitter bounds (already sealed) and only treat hrsl_raster as a sealed input/digest reference; no raster reads for jitter in v1.
- Skip `edge_tile_assign` RNG events because tile allocations are deterministic (no random permutation). Only emit `edge_jitter` RNG events (draws=2 per attempt).
- RNG key/counter derivation follows route_rng_policy_v1 basis (seed + parameter_hash + run_id) with domain strings `mlr:3B.edge_catalogue.master` and `mlr:3B.edge_catalogue.stream`.
- Timezone resolution: load tz_world polygons, build STRtree, apply deterministic nudge (tz_nudge epsilon) when polygon match is empty/ambiguous; apply tz_overrides only for scope=country (skip other scopes with a warning) and set tz_source accordingly.

Planned implementation notes:
- Reuse `_split_antimeridian_geometries` for world_countries/tz_world geometries.
- Cache per-country prepared geometries for faster point-in-polygon checks during jitter.
- Edge jitter loop will emit progress logs with elapsed/rate/ETA and track resample counts for run report.
- Edge digest law: compute per-edge digest from canonical JSON (required edge fields only), then per-merchant/global digests by concatenating edge_digest strings in sorted order.

---

### Entry: 2026-01-18 21:54

S2 implementation detail decisions for deterministic IDs, weights, and tz provenance.

Decisions:
- rng_event_id law: set `rng_event_id = sha256(rng_stream_id || "|" || merchant_id || "|" || edge_seq_index)` (hex64).
  - Reasoning: RNG event JSONL has no `rng_event_id` field and includes `ts_utc`, so hashing full event
    payload would make `edge_catalogue_3B` non-deterministic. A synthetic ID anchored to the same
    deterministic inputs as the edge identity keeps outputs stable and still correlates to the jitter
    events via `(merchant_id, edge_seq_index)`.
- edge_weight law: per-merchant uniform weights, `edge_weight = 1.0 / edge_count_total` for all edges
  in `E_m` (sum to 1.0 per merchant). This is simple, deterministic, and contract-compliant.
- tz_source mapping: use `POLYGON` when a unique polygon match is found at the original point,
  `NUDGE` when the deterministic epsilon nudge yields a unique match, and `OVERRIDE` only when a
  country-scoped override is applied. Ignore `site`/`mcc` override scopes in S2 with explicit warnings.
- edge_catalogue_index_3B digests: per-merchant digest is sha256 over concatenated `edge_digest`
  strings in `edge_id` order; global digest is sha256 over concatenated per-merchant digests in
  ascending `merchant_id` order. These orderings align with writer_sort and are deterministic.
- provenance fields: set `cdn_policy_id = "cdn_country_weights"`, `cdn_policy_version` from the
  policy file, `spatial_surface_id = "tile_bounds"`, and `hrsl_tile_id = str(tile_id)`.

Notes:
- `edge_tile_assign` RNG events remain unused (deterministic tile allocation); only `edge_jitter`
  events are emitted. The run report will record `edge_tile_assign` as zero events.

---

### Entry: 2026-01-18 22:24

S2 first run failed due to sealed input digest mismatch for route_rng_policy_v1.

Observation:
- `make segment3b-s2` failed with `E3B_S2_005_SEALED_INPUT_DIGEST_MISMATCH` for
  `route_rng_policy_v1` (computed digest differs from sealed digest in
  `sealed_inputs_3B`).
- This is expected because `config/layer1/2B/policy/route_rng_policy_v1.json`
  was updated to add the `virtual_edge_catalogue` stream after S0 sealed inputs
  were written for the current manifest.

Decision:
- Re-run `3B.S0` to reseal `route_rng_policy_v1` and refresh `sealed_inputs_3B`
  and `s0_gate_receipt_3B` for the current run, then re-run S2.

Rationale:
- S2 is required to enforce sealed input digests; the only correct fix is to
  reseal after changing a governed policy.

---

### Entry: 2026-01-18 22:25

Route RNG policy schema fix to unblock S0 reseal for 3B.

Problem:
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml` defines
  `route_rng_policy_v1.streams.virtual_edge_catalogue.rng_stream_id` with
  `pattern: '^3B\\.[A-Za-z0-9_.-]+$'`, which matches `3B\<char>` (literal
  backslash) and rejects valid IDs like `3B.edge_catalogue`.
- 3B.S0 failed validation for `route_rng_policy_v1` after adding the
  `virtual_edge_catalogue` stream because of this regex.

Decision:
- Fix the regex to `'^3B\.[A-Za-z0-9_.-]+$'` so a literal dot is accepted and
  valid 3B stream IDs pass schema validation.

Rationale:
- Aligns 3B stream IDs with the existing 2B pattern and the policy content.
- Required for S0 to reseal the updated RNG policy.

---

### Entry: 2026-01-18 22:26

S0 reseal blocked by immutability after policy change.

Observation:
- Re-running `make segment3b-s0` now fails with
  `E3B_S0_009_IMMUTABILITY_VIOLATION` because
  `sealed_inputs_3B` already exists for the current
  `manifest_fingerprint` and the new policy digest would change the
  contents.

Implication:
- The RNG policy change requires a new manifest fingerprint (or an explicit
  dev override) before S0 can reseal.

Pending decision (needs user direction):
1) Re-run upstream to generate a new manifest/run_id (strict immutability),
   then run 3B.S0 and 3B.S2 under the new manifest.
2) In dev mode, explicitly remove/relocate the existing `sealed_inputs_3B`
   and `s0_gate_receipt_3B` for this manifest and reseal (violates
   immutability but keeps the current run context).
3) Revert the RNG policy change and keep the existing seal (not preferred).

---
