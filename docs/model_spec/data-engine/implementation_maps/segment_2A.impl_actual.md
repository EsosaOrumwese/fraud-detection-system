# segment_2A.impl_actual.md

Append-only implementation planning log for Segment 2A. Each entry documents the
design element, a short summary of the problem, and the detailed plan to resolve
it. Do not delete prior entries.

State-by-state approach: only the active state's planning is recorded here.
Earlier multi-state planning notes were removed per user request; reading across
2A states is treated as context-only and not an implementation plan.

---

## S0 - Gate & Sealed Inputs (S0.*)

### Entry: 2026-01-14 13:18

Design element: Gate 1B PASS and seal 2A inputs for manifest_fingerprint.
Summary: S0 must enforce "No PASS -> No Read" for 1B, seal all required 2A inputs,
derive manifest_fingerprint, and emit the gate receipt + sealed manifest.

Plan (before implementation, detailed):
1) Resolve run identity inputs.
   - Read `run_receipt.json` for `run_id`, `seed`, and `parameter_hash`.
   - Resolve `manifest_fingerprint` from 1B validation bundle paths and enforce
     path-embed equality (dictionary is authority for paths).
   - If run receipt or CLI seed disagrees with 1B bundle identity, abort with a
     clear error that points to the mismatched token.

2) Verify upstream PASS evidence before any 1B read.
   - Resolve `validation_bundle_1B` and `_passed.flag` via the dataset dictionary.
   - Load `index.json` from the bundle and validate against the 1B bundle index
     schema (schemas.1B.yaml reference in registry).
   - Compute the bundle digest using the Layer-1 law: ASCII-lex order of
     `index.path`, hash raw bytes of listed files, exclude `_passed.flag`.
   - Read `_passed.flag` and assert it equals the recomputed digest. If not,
     abort and emit no outputs.

3) Enumerate and seal required inputs (content addressed).
   - Required sealed inputs for 2A:
     - `site_locations` (1B egress, seed + manifest_fingerprint).
     - `tz_world_2025a` (ingress reference).
     - `tzdb_release` (ingress artefact folder + release metadata).
     - `tz_overrides` policy.
     - `tz_nudge` policy.
   - Optional sealed inputs, include only if referenced by downstream 2A states:
     - `iso3166_canonical_2024`
     - `world_countries`
     - `merchant_mcc_map` (only if overrides contain MCC scope).
   - For each sealed asset, compute sha256 by streaming bytes (no full load in
     memory), record size, format, version tag, and license class from the
     registry.
   - For directory style artefacts (tzdb_release), compute a stable digest by
     hashing all files in ASCII-lex relative-path order and recording each
     member in the sealed manifest.

4) Build `sealed_inputs_2A`.
   - Record `asset_id`, `path`, `partition`, `version_tag`, `sha256_hex`,
     `size_bytes`, `license`, and `schema_ref` for each entry.
   - Enforce "no duplicates, no aliases" and ensure basenames are unique.
   - Sort output by the dictionary ordering (asset_kind, basename).

5) Emit `s0_gate_receipt_2A`.
   - Include `manifest_fingerprint`, `parameter_hash`, `verified_at_utc`,
     `validation_bundle_path`, `passed_flag_sha256`, and a summary of sealed
     inputs (ids + partitions).
   - Set `verified_at_utc` once and reuse it downstream (S2/S3/S4 timestamps).
   - Ensure path-embed equality for manifest_fingerprint in receipt path.

6) Publish atomically with immutability guard.
   - Stage to a temp directory, fsync, then atomically move into the target
     manifest_fingerprint partition.
   - If outputs already exist, require byte-identical content or abort.

Decisions recorded before implementation:
- Optional auxiliaries will be sealed only if later 2A states explicitly
  reference them. Current S1-S5 specs do not require iso3166 or world_countries,
  so they will be omitted unless the policy or validation section requires them.
- If `tz_overrides` contains any MCC-scope entries, `merchant_mcc_map` becomes
  required for this run; otherwise, MCC scope overrides are treated as inactive.

Open questions to resolve before coding:
- Confirm where `parameter_hash` is sourced if `run_receipt.json` is absent
  (fallback to CLI, or abort).
- Confirm tzdb release folder content: single archive file vs multi-file layout,
  so we pick the correct deterministic digesting rule in S0.

### Entry: 2026-01-14 13:27

Design element: S0 implementation decisions (post-clarification).
Summary: User approved the S0-only approach and accepted the recommended
deterministic choices. This entry records those decisions before any code change.

Decisions recorded before implementation:
1) **parameter_hash source**: hard-fail if `run_receipt.json` is missing or
   incomplete. No CLI fallback for parameter_hash (keeps identity deterministic).
2) **tzdb_release hashing**: hash the entire release directory using ASCII-lex
   relative paths (no single-file shortcut). Record total bytes across all files.
3) **Optional auxiliaries**: omit `iso3166_canonical_2024` and `world_countries`
   unless a later 2A state explicitly references them. Keep S0 manifest minimal.
4) **manifest_fingerprint source**: use the run receipt + 1B bundle path tokens
   for the manifest_fingerprint; enforce path-embed equality and abort on mismatch.
5) **Sealed-input basenames**: use a deterministic basename derived from the
   catalog path, but if duplicates appear, fall back to `asset_id` to enforce
   uniqueness (spec requires no duplicate basenames).

Implementation plan (refined, S0 only):
1) Resolve `run_receipt.json`, extract `run_id`, `seed`, `parameter_hash`,
   `manifest_fingerprint`; verify run_id matches folder name.
2) Resolve 1B `validation_bundle_1B` and `_passed.flag` by dictionary ID and
   compute bundle hash via index.json (ASCII-lex raw bytes, flag excluded).
3) Enforce 1B PASS by comparing `_passed.flag` to computed hash; abort if mismatch.
4) Resolve and seal required assets (bundle, flag, site_locations, tz_world_2025a,
   tzdb_release folder, tz_overrides, tz_nudge) with full digests and sizes.
5) Build `sealed_inputs_2A` rows including `asset_kind`, `basename`, `catalog_path`,
   `sha256_hex`, `size_bytes`, and `license_class`, then validate schema.
6) Build `s0_gate_receipt_2A` with `sealed_inputs[]` (id + partition + schema_ref),
   `validation_bundle_path`, `flag_sha256_hex`, and `verified_at_utc`.
7) Publish both artifacts atomically under `manifest_fingerprint` partition,
   with immutability checks (byte-identical re-emits only).

### Entry: 2026-01-14 13:46

Design element: S0 validation mechanics and observability wiring (pre-implementation).
Summary: Flesh out the remaining S0 validators, output placement, and logging so
the run tells a clear gate→seal→emit story while matching 2A-S0 error codes.

Plan (before implementation, detailed):
1) tz_world invariants and tzid set.
   - Prefer pyarrow metadata to read CRS + row count without loading geometry.
   - Parse GeoParquet `geo` metadata for CRS; accept EPSG:4326/WGS84/CRS84.
   - Abort if CRS not WGS84 (2A-S0-020) or row count is zero (2A-S0-021).
   - Load the `tzid` column (polars/pyarrow) to build the authoritative tzid set
     for validating overrides; do not touch geometry content.

2) tzdb_release selection + digesting.
   - Resolve release directory by scanning `artefacts/priors/tzdata/*` for exactly
     one folder containing `tzdb_release.json`; abort on none or multiple
     candidates as unpinned (2A-S0-014).
   - Validate `tzdb_release.json` against `schemas.2A.yaml#/ingress/tzdb_release_v1`.
   - Enforce release_tag format and archive_sha256 hex64 (2A-S0-022/023).
   - Hash **all files** in the release directory in ASCII-lex relative order to
     produce the sealed digest and size_bytes.

3) Overrides policy validation and MCC dependency.
   - Validate `tz_overrides.yaml` against `tz_overrides_v1`; abort on schema
     failure (2A-S0-030) or duplicate `(scope, target)` pairs (2A-S0-031).
   - If any override references an unknown tzid (not in tz_world tzid set),
     abort with 2A-S0-032.
   - If any override uses `scope: mcc`, require `merchant_mcc_map` to exist and
     be sealed; otherwise abort as missing required asset (2A-S0-010).

4) Version tags and authority echo.
   - Use dictionary version tokens when resolvable; when `{semver}` is
     unresolved (e.g., empty overrides list), fall back to a digest-derived
     version tag `sha256:<hex>` to keep the version pinned and non-ambiguous.
   - Validate schema_ref anchors, catalog_path matches dictionary, and
     license_class matches registry for every sealed row (2A-S0-052).

5) Determinism receipt + run-report placement.
   - Compute a partition hash over the emitted S0 outputs (receipt + inventory)
     **excluding** the determinism receipt file itself, then write
     `determinism_receipt.json` under the sealed_inputs partition.
   - Emit a run-report to
     `runs/<run_id>/reports/layer1/2A/state=S0/manifest_fingerprint=<fp>/s0_run_report.json`
     with the required fields; missing fields produce 2A-S0-070 warnings.

6) Logging and validation story.
   - Emit structured events for `GATE`, `SEAL`, `HASH`, `EMIT`, `DETERMINISM`,
     and per-validator `VALIDATION` with segment/state/manifest_fingerprint.
   - Add human-readable INFO messages that narrate each step so the run log
     reads as a linear story without consulting the spec.

### Entry: 2026-01-14 14:20

Design element: Deterministic timestamps + manifest digest handling for S0 outputs.
Summary: Ensure S0 outputs are re-runnable without immutability conflicts while still
meeting the run-report and audit requirements.

Decisions recorded before implementation:
1) Use `run_receipt.created_utc` for deterministic timestamps in S0 outputs:
   - `verified_at_utc` in `s0_gate_receipt_2A`.
   - `created_utc` for each row in `sealed_inputs_2A`.
   - `determinism_receipt.computed_at_utc` (if recorded) and run-report `started_utc`.
   This keeps S0 outputs byte-identical on re-runs for the same run_id.
2) Use `asset_id` as `basename` in `sealed_inputs_2A` (dataset stem), which is
   stable, ASCII-safe, and avoids duplicate basenames for partitioned assets.
3) Compute `sealed_inputs.manifest_digest` as SHA-256 over the canonical JSON
   bytes of the `sealed_inputs_2A` payload (sorted by `(asset_kind, basename)`).
   This digest is recorded in the run-report and `HASH` log event only; it is not
   used to overwrite or recompute `manifest_fingerprint`, which remains sourced
   from `run_receipt.json` per the layer-wide identity workflow.
4) Determinism receipt placement:
   - Stored under the `sealed_inputs_2A` manifest_fingerprint partition alongside
     the inventory file as `determinism_receipt.json`.
   - Partition hash is computed over the emitted inventory file **before**
     writing the determinism receipt itself, to avoid self-hash recursion.

### Entry: 2026-01-14 15:07

Design element: S0 gate mechanics refinements after re-reading state.2A.s0 (pre-implementation).
Summary: Align tzdb/override handling and optional inputs with the binding spec and existing engine patterns.

Decisions recorded before implementation:
1) **tzid membership enforcement**: only enforce tzid membership if a sealed tzid index is explicitly provided in the sealed inputs. The current dictionary/registry does not define a tzid index, so overrides will be schema-validated and duplicate-checked; tzid membership is logged as a WARN-only skip (no abort).
2) **tzdb_release metadata source**: treat the dictionary path as a directory and resolve 	zdb_release.json (or .yaml/.yml) inside it; validate against schemas.2A.yaml#/ingress/tzdb_release_v1, enforce release_tag regex, and cross-check rchive_sha256 against the actual archive bytes when present.
3) **Optional ingress references**: keep iso3166_canonical_2024 and world_countries out of the sealed set unless a downstream 2A state explicitly references them or a policy requires them. This preserves the minimal-manifest decision recorded earlier; any later decision to include them must re-run S0 with a new manifest_fingerprint.
4) **MCC overrides**: keep the strict gate: if any override uses scope: mcc and merchant_mcc_map is not sealed, abort S0 (treating the run as misconfigured rather than silently ignoring MCC overrides).

Implementation notes to apply:
- 	z_world checks use GeoParquet metadata for CRS/row count; abort if CRS != WGS84 or row count == 0.
- If 	zdb_release directory contains multiple metadata files or no archive, abort as unpinned/malformed rather than guessing.

### Entry: 2026-01-14 14:58

Design element: S0 gate runner + CLI wiring (implementation pass, post-plan).
Summary: Implemented the S0 gate logic exactly as planned, including the PASS gate,
sealed-inputs construction, and run-report emission, then wired a dedicated CLI and
Makefile target so S0 can be executed without the segment2a multi-state runner.

Implementation actions (detailed, after planning):
1) Added `packages/engine/src/engine/layers/l1/seg_2A/s0_gate/runner.py`.
   - Implemented run receipt resolution via `_resolve_run_receipt` and hard-failed
     if `run_receipt.json` lacks `run_id`, `seed`, `parameter_hash`, or
     `manifest_fingerprint`.
   - Added PASS gate checks for `validation_bundle_1B`:
     - Validated `index.json` against the 1B bundle schema.
     - Recomputed the bundle hash from index entries (ASCII-lex `index.path`,
       raw bytes, `_passed.flag` excluded).
     - Parsed `_passed.flag` and enforced exact hash equality before allowing any
       1B reads.
   - Implemented deterministic sealed-inputs build:
     - Required assets: `validation_bundle_1B`, `validation_passed_flag_1B`,
       `site_locations`, `tz_world_2025a`, `tzdb_release`, `tz_overrides`, `tz_nudge`.
     - Optional `merchant_mcc_map` sealed only when overrides include `scope: mcc`
       (hard-fail if missing in that case).
     - `asset_kind` derived from dictionary + catalog path; `basename` set to
       `asset_id` for deterministic uniqueness.
   - Added tz assets validation:
     - `tz_world_2025a` CRS + non-empty check via GeoParquet metadata.
     - `tzdb_release` resolved as a directory; metadata file (`tzdb_release.*`)
       validated against `schemas.2A.yaml#/ingress/tzdb_release_v1`; archive digest
       checked against actual archive if present; full directory digest computed.
     - `tz_overrides` and `tz_nudge` validated against policy schemas; duplicate
       `(scope,target)` pairs hard-fail; tzid membership logged as WARN-only
       when no tzid index exists in the dictionary.
   - Emitted `sealed_inputs_2A` and `s0_gate_receipt_2A` to the fingerprinted
     partition with `_atomic_publish_dir` immutability guard.
   - Wrote determinism receipt (hash over payloads excluding the receipt itself)
     and `s0_run_report.json` with required fields; missing fields logged with
     `2A-S0-070` warnings.
   - Added structured story logs using `_emit_event` + `_emit_validation` so the
     run log reads as Gate -> Seal -> Hash -> Emit -> Determinism.

2) Added `packages/engine/src/engine/cli/s0_gate_2a.py`.
   - Exposes `--contracts-layout`, `--contracts-root`, `--runs-root`,
     `--external-root`, and `--run-id` flags consistent with existing S0 CLIs.
   - Uses `EngineConfig` + `with_external_roots` to resolve contract layout and
     external roots; logs a final completion line with run identity.

3) Wired Makefile support for the S0 gate runner.
   - Added `SEG2A_S0_RUN_ID` and `SEG2A_S0_ARGS`/`SEG2A_S0_CMD` blocks that mirror
     the Segment 1B S0 invocation pattern.
   - Added `segment2a-s0` target so S0 can be executed without the full segment2a
     runner (state-by-state workflow).

Implementation alignment notes:
- The tzid membership check remains WARN-only unless a tzid index is explicitly
  sealed (dictionary currently lacks such an entry).
- Optional iso/world inputs remain unsealed unless a later state or policy
  explicitly demands them; S0 stays minimal as per the approved plan.

### Entry: 2026-01-14 15:05

Design element: tzdb_release path token resolution (hotfix after failed run).
Summary: The S0 run failed because the dictionary path uses `{release_tag}` but
S0 had no token to resolve it, so `resolve_input_path` looked for a literal
`artefacts/priors/tzdata/{release_tag}` folder. This must be resolved
deterministically at runtime.

Observed failure (from run log):
- `InputResolutionError: Input not found ... artefacts/priors/tzdata/{release_tag}`
  while resolving `tzdb_release` in S0.

Plan and decisions (before patching code):
1) Resolve `release_tag` deterministically if missing from tokens.
   - Use the dictionary path template: strip at `{release_tag}` to get the root
     `artefacts/priors/tzdata/`.
   - Scan subdirectories for exactly one candidate that contains
     `tzdb_release.json|yaml|yml`. If zero or multiple candidates, fail with
     `2A-S0-014` to avoid ambiguous pinning.
2) After loading `tzdb_release` metadata, enforce tag consistency.
   - If a `release_tag` was inferred from the directory name, require the
     metadata `release_tag` to match exactly (fail-closed on mismatch).
3) Update tokens with the resolved `release_tag` before rendering catalog paths
   so sealed_inputs and run-report paths are canonical and deterministic.

Implementation actions taken:
- Added `_resolve_release_tag_from_root(...)` helper in
  `packages/engine/src/engine/layers/l1/seg_2A/s0_gate/runner.py` to discover the
  single valid release directory under `artefacts/priors/tzdata/`.
- In `run_s0`, added a pre-resolution step:
  - If the tzdb path contains `{release_tag}` and no token is available, resolve
    the tag via the helper and log `S0: resolved tzdb_release tag=...`.
  - Then resolve `tzdb_release` with the updated tokens.
- Added a strict mismatch check between the inferred path tag and the metadata
  `release_tag` (error `2A-S0-014` on mismatch) and ensured tokens are updated
  to the metadata tag after validation.

### Entry: 2026-01-14 15:06

Design element: tzdb_release schema validation with external $ref (runtime failure).
Summary: The run failed during `tzdb_release_v1` schema validation because the
schema includes `$ref: schemas.layer1.yaml#/$defs/hex64` and Draft202012Validator
attempted to resolve it as a URL. We need a local ref mapping for schema packs.

Observed failure (from run log):
- `_WrappedReferencingError: Unresolvable: schemas.layer1.yaml#/$defs/hex64`
  when validating `tzdb_release_v1`.

Plan and decisions (before patching code):
1) Keep validation strict but resolve external $refs locally.
   - Attach `$defs` from `schemas.layer1.yaml` into the active schema.
   - Rewrite `$ref` strings that start with `schemas.layer1.yaml#` to local
     `#/$defs/...` pointers.
2) Keep the change scoped to this runner and to the tzdb_release validation
   (to avoid altering other validators unexpectedly).

Implementation actions taken:
- Added `_rewrite_external_refs` + `_attach_external_defs` helpers and updated
  `_validate_payload` to accept `ref_packs` for local $ref rewrites.
- Passed `ref_packs={"schemas.layer1.yaml": schema_layer1}` when validating
  `ingress/tzdb_release_v1`.

### Entry: 2026-01-14 15:10

Design element: External $defs scope (recursion failure on validation).
Summary: After adding all layer1 `$defs`, Draft202012Validator hit a recursion
error (deep self-referential defs in the layer1 pack). We only need the specific
def(s) referenced by `tzdb_release_v1`, so we should inline a minimal subset.

Observed failure (from run log):
- `RecursionError: maximum recursion depth exceeded` during `$ref` resolution
  inside tzdb_release validation.

Plan and decisions (before patching code):
1) Collect only the external defs actually referenced by the schema path under
   validation (e.g., `hex64`) and inline just those.
2) Keep `$ref` rewriting in place, but avoid pulling in the entire layer1 `$defs`
   to prevent recursive definition expansion.

Implementation actions taken:
- Added `_collect_external_defs` to gather referenced `$defs` keys for a given
  external prefix (`schemas.layer1.yaml#`).
- Updated `_attach_external_defs` to inline only those needed keys and to fail
  if a referenced key is missing in the external pack.
- Kept `$ref` rewriting scoped to the external prefix so refs resolve locally.

### Entry: 2026-01-14 15:11

Design element: External $ref handling (recursion persists).
Summary: The minimal `$defs` injection still hit recursion in the jsonschema
validator. To avoid any external $ref resolution path entirely, I switched to
inlining external defs directly into the schema node, removing `$ref` usage.

Observed failure (from run log):
- Recursion depth exceeded during `$ref` resolution despite minimal $defs.

Plan and decisions (before patching code):
1) Inline external `$defs` directly at the `$ref` site (replace `$ref` with the
   referenced schema object).
2) Preserve any sibling keys on the `$ref` node (e.g., `nullable`) by merging
   them into the inlined schema.
3) Limit the inlining to the `schemas.layer1.yaml#/$defs/*` prefix only.

Implementation actions taken:
- Added `_inline_external_refs` and updated `_validate_payload` to replace
  external `$ref` nodes with their concrete schema definitions from
  `schemas.layer1.yaml` before validation.
- Removed the previous `$defs` injection + `$ref` rewriting path to avoid
  recursion on draft-2020-12 resolution.

### Entry: 2026-01-14 15:12

Design element: External ref handling for policy schemas.
Summary: After fixing tzdb_release, S0 failed on `tz_nudge_v1` because that
schema still referenced `schemas.layer1.yaml#/$defs/hex64`. The external ref
inline logic must be applied to *all* policy validations, not just tzdb_release.

Observed failure (from run log):
- `Unresolvable: schemas.layer1.yaml#/$defs/hex64` during `tz_nudge_v1` validation.

Implementation actions taken:
- Passed `ref_packs={"schemas.layer1.yaml": schema_layer1}` when validating
  `policy/tz_overrides_v1` and `policy/tz_nudge_v1` so their external $refs are
  inlined before Draft202012 validation.

### Entry: 2026-01-14 15:14

Design element: External refs in sealed_inputs + receipt validation.
Summary: S0 progressed to sealing but failed when validating
`sealed_inputs_2A` and the S0 receipt because those schemas still carry
`schemas.layer1.yaml#/$defs/*` refs. We need to inline those refs before using
`validate_dataframe` or Draft202012 on the receipt.

Observed failure (from run log):
- `Unresolvable: schemas.layer1.yaml#/$defs/hex64` during sealed_inputs validation.

Implementation actions taken:
- Inlined external layer1 refs into the `sealed_inputs_2A` schema pack prior to
  `validate_dataframe`.
- Inlined external layer1 refs into the `validation/s0_gate_receipt_v1`
  row schema before Draft202012 validation.

### Entry: 2026-01-14 15:15

Design element: sealed_inputs validation compatibility with jsonschema_adapter.
Summary: `validate_dataframe` expects `$ref` to remain (it maps table columns by
type); inlining external defs converted `$ref` to `type: integer`, which the
adapter rejects. The fix is to rewrite external refs to *local* `$defs` while
preserving `$ref` form (no inlining) for table validation and receipt validation.

Observed failure (from run log):
- `ContractError: Unsupported column type 'integer'` while building
  sealed_inputs row schema.

Implementation actions taken:
- Added `_rewrite_external_refs_local` to add only the needed layer1 `$defs` and
  rewrite `schemas.layer1.yaml#` refs to local `#/$defs/...` while keeping `$ref`
  intact.
- Applied this to the sealed_inputs pack before `validate_dataframe` and to the
  receipt row schema before Draft202012 validation.

### Entry: 2026-01-14 15:19

Design element: sealed_inputs/receipt validation recursion from alias `$defs`.
Summary: After rewriting external refs to local `$defs`, Draft202012 validation
still hit recursion because the 2A schema pack `$defs` are alias entries
(`hex64` -> `schemas.layer1.yaml#/$defs/hex64`). Rewriting those alias refs to
local `#/$defs/hex64` makes them self-referential. We need to replace alias
`$defs` with concrete layer1 definitions for the validator inputs.

Plan and decisions (before patching code):
1) Build a sealed_inputs schema pack that uses *only* concrete layer1 `$defs`.
   - Start from the table definition (`manifests/sealed_inputs_2A`) without
     copying the 2A `$defs` alias block.
   - Collect external refs referenced by the table columns.
   - Attach concrete `$defs` from `schemas.layer1.yaml` and rewrite refs to
     local `#/$defs/<name>`.
   - Keep `$ref` form so `validate_dataframe` still works.
2) For the S0 receipt row schema, perform the same transformation.
   - Build row schema, drop alias `$defs`, attach concrete layer1 `$defs`, and
     rewrite external refs to local.
   - Validate receipt rows with Draft202012Validator as before.
3) Remove `_rewrite_external_refs_local` usage in S0 sealing paths to avoid
   alias self-references. Keep external-ref inlining for tzdb and policy
   validations unchanged.

### Entry: 2026-01-14 15:25

Design element: sealed_inputs atomic publish path vs directory staging.
Summary: `_atomic_publish_dir` was called with a *file* path
(`sealed_inputs_2A.json`), but it expects a directory. This caused a
WinError 3 when attempting to rename the temp directory into a file path.

Plan and decisions (before patching code):
1) Treat `sealed_inputs_2A` as a file inside a partition directory.
   - Stage `sealed_inputs_2A.json` + `determinism_receipt.json` inside a temp
     directory.
   - Publish by atomically replacing the *partition directory*
     (`.../sealed_inputs/manifest_fingerprint=<fp>/`) rather than the file path.
2) Align determinism metadata with the directory hash.
   - Record `partition_path` as the partition directory (parent of the file
     path), since the hash is computed over the directory contents.
3) Keep the emitted `sealed_inputs_path` in logs as the file path (matches the
   dictionary and is how operators locate the inventory file).

### Entry: 2026-01-14 15:27

Design element: atomic publish directory parent creation.
Summary: After switching to publish the partition directory, the rename still
failed because the parent directory did not exist (`sealed_inputs/`).

Plan and decisions (before patching code):
1) Ensure `_atomic_publish_dir` creates `final_root.parent` before `replace`.
   - Mirrors `_atomic_publish_file` behavior and avoids WinError 3 on missing
     parent directories.
2) Keep immutability guard unchanged (hash compare when the target exists).

### Entry: 2026-01-14 15:29

Design element: S0 validation + publish fixes (implementation pass).
Summary: Implemented the alias-free schema handling for sealed_inputs/receipt,
added the nullable `notes` field to the receipt payload, fixed directory publish
semantics, and confirmed S0 completes green.

Implementation actions taken (detailed):
1) Added schema helpers in `seg_2A/s0_gate/runner.py`:
   - `_collect_local_defs`, `_resolve_defs`,
     `_prepare_table_pack_with_layer1_defs`, and
     `_prepare_row_schema_with_layer1_defs`.
   - Replaced the sealed_inputs and receipt validation paths to attach **concrete
     layer1 `$defs`** and rewrite external refs to local, avoiding alias self-refs.
2) Added `notes: None` to the S0 gate receipt payload to satisfy the nullable
   but required `notes` column in `validation/s0_gate_receipt_v1`.
3) Fixed sealed_inputs publish staging:
   - Publish the partition directory (`.../sealed_inputs/manifest_fingerprint=...`)
     rather than the file path.
   - Record determinism `partition_path` as the directory, and update the
     determinism log to match.
   - Ensure `_atomic_publish_dir` creates `final_root.parent` before replace.
4) Ran `make segment2a-s0` and confirmed S0 completion with run report and
   pass logs (Gate → Seal → Emit → Determinism) for run_id
   `dbc151d09d5fd3053a74705bca1b673c`.

## S1 - Provisional TZ Lookup (S1.*)

### Entry: 2026-01-14 15:34

Design element: S1 provisional tz lookup (geometry-only, RNG-free).
Summary: Plan the S1 implementation to map each `site_locations` row to exactly
one `tzid_provisional` using the sealed `tz_world` polygons and `tz_nudge`
policy, with strict gate/identity/coverage guarantees.

Plan (before implementation, detailed):
1) Gate + identity verification (No PASS -> No Read).
   - Load `s0_gate_receipt_2A` for the target `manifest_fingerprint` and
     validate against `schemas.2A.yaml#/validation/s0_gate_receipt_v1`.
   - Confirm receipt `manifest_fingerprint` equals the run's fingerprint.
   - Load `sealed_inputs_2A` for the same fingerprint and assert required IDs
     are present: `site_locations`, `tz_world_2025a`, `tz_nudge`.
   - Abort with 2A-S1-001 if receipt missing or invalid; 2A-S1-010 if any input
     cannot be resolved via Dictionary/Registry.

2) Resolve inputs strictly by Dictionary.
   - Resolve `site_locations` partition for the run's `[seed, manifest_fingerprint]`;
     enforce path-embed equality and correct partition (2A-S1-011 on mismatch).
   - Resolve `tz_world_2025a` as the sealed reference path.
   - Resolve `tz_nudge` policy as sealed; validate schema and check
     `epsilon_degrees > 0` (2A-S1-021).

3) Validate tz_world ingress minima (S1-scope).
   - Verify CRS is WGS84 (EPSG:4326) and polygons are non-empty
     (2A-S1-020 on violation). Reuse S0 helpers for CRS/row-count.
   - Load tz_world geometries + `tzid` and precompute `tzid` set for membership
     validation (2A-S1-053 on unknown tzid).

4) Geometry engine and performance strategy.
   - Build a spatial index (prefer `shapely.STRtree`) for tz_world polygons so
     point-in-polygon checks are O(N log M) rather than O(N*M).
   - Use prepared geometries to reduce repeated predicate cost; avoid loading
     all site rows into memory (batch/stream over `site_locations`).
   - Reuse dateline-aware helpers from 1B where appropriate to normalize
     longitudes and avoid antimeridian edge failures.

5) Per-site assignment law (single nudge).
   - For each `site_locations` row, test point-in-polygon membership:
     a) If exactly one polygon matches -> set `tzid_provisional`; `nudge_* = null`.
     b) If zero or multiple matches -> apply a single nudge:
        `(lat', lon') = (lat + epsilon, lon + epsilon)` in degrees.
        - Clamp latitude to [-90, +90].
        - Wrap longitude into (-180, +180] with modular arithmetic.
        - Re-evaluate membership on the nudged point.
     c) If still ambiguous or empty -> abort with 2A-S1-055.
   - Record `nudge_lat_deg` and `nudge_lon_deg` only when the nudge was applied;
     enforce the pair rule (2A-S1-054).

6) Output construction and validation.
   - Emit `s1_tz_lookup` rows with columns:
     `seed`, `manifest_fingerprint`, `merchant_id`, `legal_country_iso`,
     `site_order`, `lat_deg`, `lon_deg`, `tzid_provisional`,
     `nudge_lat_deg`, `nudge_lon_deg`, `created_utc`.
   - Use `run_receipt.created_utc` for deterministic timestamps.
   - Validate output against `schemas.2A.yaml#/plan/s1_tz_lookup`.
   - Enforce PK uniqueness and 1:1 coverage with `site_locations`
     (2A-S1-050 / 2A-S1-051).

7) Publish + immutability.
   - Write to temp partition directory, then atomically publish to
     `data/layer1/2A/s1_tz_lookup/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`.
   - If target partition exists, allow only byte-identical re-emit;
     otherwise abort (2A-S1-041).

8) Observability + run-report.
   - Emit structured `GATE`, `INPUTS`, `LOOKUP`, `VALIDATION`, `EMIT` events
     with `seed` + `manifest_fingerprint`.
   - Emit progress logs with counts/rates for large input partitions.
   - Write `s1_run_report.json` with required fields from spec (counts,
     distinct tzids, nudge count, path/inputs, warnings/errors).

Open questions to resolve before coding:
1) Geometry engine choice: ok to standardize on `shapely.STRtree` for
   candidate selection (fast, deterministic) vs `geopandas.sjoin`?
2) Antimeridian handling: should S1 reuse the dateline normalization helpers
   from 1B (as used in `s1_tile_index`/`s6_site_jitter`) to keep longitude
   handling consistent, or treat tz_world as already aligned?
3) Failure reporting: on `2A-S1-055` (ambiguity after nudge), do you want
   the run-report to include a short sample of offending site keys (count-only
   by default per spec), or keep it strictly count-only?

### Entry: 2026-01-14 15:38

Design element: S1 confirmation decisions (pre-implementation).
Summary: Recorded the approved geometry engine, antimeridian posture, and
failure reporting scope before coding.

Decisions recorded before implementation:
1) **Geometry engine:** Use `shapely.STRtree` with prepared geometries for
   candidate selection and deterministic point-in-polygon checks. Avoid
   `geopandas.sjoin` to keep memory lower and enable streaming.
2) **Antimeridian handling:** Reuse the dateline normalization helpers from 1B
   (`s1_tile_index`/`s6_site_jitter`) so longitude handling is consistent across
   segments and edge cases near ±180 are treated uniformly.
3) **Failure reporting:** Keep the run-report count-only for `2A-S1-055`.
   Include a **small capped sample** of offending site keys only in error
   context/logs (no coordinates) to aid debugging without bloating reports or
   leaking location detail.

### Entry: 2026-01-14 15:50

Design element: S1 runner architecture and batch strategy (pre-implementation).
Summary: Pin the data flow, geometry index, IO batching, and validation posture
before coding to keep S1 deterministic and audit-friendly.

Decisions recorded before implementation:
1) **Input streaming + output batches:** Read `site_locations` via Parquet
   batches using pyarrow when available, with a polars fallback. Emit output
   Parquet in batches (default 200k rows) to avoid full materialization.
2) **Schema validation posture:** Validate `s1_tz_lookup` rows per batch using
   `validate_dataframe` with a 2A pack that has concrete layer1 `$defs`. This
   keeps strict schema enforcement without ingesting the entire partition into
   memory.
3) **STRtree candidate matching:** Build an STRtree over split tz_world polygon
   parts. Evaluate candidates with prepared geometries (covers/touches), and
   deduplicate by tzid so multi-part polygons do not cause false ambiguity.
4) **Order + PK checks:** Track writer-order compliance (warn-only on first
   violation) while separately tracking PK duplicates using a set to enforce
   2A-S1-051 even if input ordering is imperfect.
5) **Run-report on failure:** Always emit `s1_run_report.json` with status
   "fail" and canonical error context before re-raising, so the run history is
   preserved even when S1 aborts early.


### Entry: 2026-01-14 16:40

Design element: S1 runner implementation + CLI + Makefile wiring (implementation pass).
Summary: Implemented the full S1 geometry-only tz lookup runner, added the
state-specific CLI, and wired a Makefile target to run S1 independently.

Implementation actions (detailed):
1) Added `packages/engine/src/engine/layers/l1/seg_2A/s1_tz_lookup/runner.py`.
   - Resolved run identity from `run_receipt.json` (seed, manifest_fingerprint,
     parameter_hash) and enforced run_id path consistency before any input reads.
   - Loaded Dictionary, Registry, and schema packs (2A + 1B + ingress + layer1)
     and enforced schema_ref presence/validity with authority conflict checks.
   - Verified the S0 gate receipt for the manifest_fingerprint using the 2A
     schema row validator and logged `GATE` + `VALIDATION` events for V-01.
   - Enforced sealed-input membership: required `site_locations`, `tz_world_2025a`,
     and `tz_nudge` in `sealed_inputs_2A` (abort with 2A-S1-010 on missing).
   - Resolved `site_locations`, `tz_world_2025a`, and `tz_nudge` strictly via
     the Dataset Dictionary and enforced partition token match for
     `(seed, manifest_fingerprint)` (2A-S1-011 on mismatch).
   - Validated tz_world invariants (WGS84 + non-empty) with S0 helpers and
     validated `tz_nudge` against `policy/tz_nudge_v1` with `epsilon_degrees > 0`.
   - Built a STRtree over tz_world polygons, splitting antimeridian geometries
     using the 1B helper so longitude handling is consistent across segments.
   - Streamed `site_locations` in Parquet batches; for each row:
     - Deterministic point-in-polygon lookup for `tzid_provisional`.
     - Single ε-nudge when ambiguous (lat+ε, lon+ε), recorded `nudge_*`.
     - Abort on unresolved ambiguity (2A-S1-055) or nudge-pair violations
       (2A-S1-054).
   - Emitted `s1_tz_lookup` in batch Parquet parts with per-batch schema
     validation (`validate_dataframe` using the 2A pack with layer1 defs).
   - Enforced coverage (2A-S1-050), PK uniqueness (2A-S1-051), null tzid
     (2A-S1-052), unknown tzid (2A-S1-053), and writer-order warn (2A-S1-070).
   - Published the output with write-once semantics via `_atomic_publish_dir`
     (2A-S1-041 on non-identical overwrites).
   - Wrote the run-report `s1_run_report.json` on every run (pass or fail)
     and emitted required `INPUTS`, `LOOKUP`, `VALIDATION`, and `EMIT` events.

2) Added `packages/engine/src/engine/cli/s1_tz_lookup_2a.py`.
   - Mirrors the S0 CLI pattern (contracts layout/root, runs root, external
     roots, run_id) and logs completion with run identity.

3) Updated `makefile` to wire S1.
   - Added `SEG2A_S1_RUN_ID`, `SEG2A_S1_ARGS`, and `SEG2A_S1_CMD`.
   - Added `segment2a-s1` target and `.PHONY` entry.

Notes for next actions:
- Run `make segment2a-s1` (with the current run_id) and inspect the run report
  + logs for any spec compliance gaps or performance issues; record any fixes
  in this implementation log and the logbook.

### Entry: 2026-01-14 16:49

Design element: S1 run attempt + border ambiguity failure (post-implementation).
Summary: The first S1 run aborted with `2A-S1-055 BORDER_AMBIGUITY_UNRESOLVED`.
This is spec-compliant (S1 must hard-fail if a single ε-nudge cannot resolve a
unique tzid), but it blocks a green run until inputs or policy are adjusted.

Observed failure:
- Run: `make segment2a-s1` (run_id `dbc151d09d5fd3053a74705bca1b673c`).
- Error: `S1_ERROR 2A-S1-055` for key `[merchant_id=14376464151614543665, legal_country_iso=MN, site_order=10]`.
- Run-report written to:
  `runs/local_full_run-5/dbc151d09d5fd3053a74705bca1b673c/reports/layer1/2A/state=S1/seed=42/manifest_fingerprint=fa8639df1238943518f72f8e0ed6310ad8521b7427993e1dc67d95ed4549d67b/s1_run_report.json`.

Analysis (recorded for review):
- The S1 algorithm applies the single ε-nudge as specified (`lat+ε, lon+ε`).
- After the nudge, membership remained ambiguous or empty, triggering 2A-S1-055.
- This indicates either a tz_world gap/overlap at that site or ε too small to
  move the point into a unique polygon. The code is following the spec.

Resolution options (require user decision before changing inputs):
1) **Adjust tz_nudge ε** (policy): increase ε so the tie-break resolves more
   border cases. This requires re-running S0 to seal a new manifest_fingerprint.
2) **Fix tz_world coverage**: update the tz_world release if polygons are
   missing/overlapping for the affected area, then reseal via S0.
3) **Leave as-is**: keep the fail-closed behaviour and treat this as a data
   quality issue in inputs (spec-compliant but blocks green runs).

No code changes made after the failure; awaiting direction on input/policy changes.

### Entry: 2026-01-14 16:52

Design element: S1 run-report counts on early failure.
Summary: The first S1 run aborted mid-loop, and the run-report showed zeroed
counts because they were populated only after the loop completed. The spec
expects counts to reflect rows read/emitted; even on failure, partial counts are
more informative.

Implementation actions taken:
- Updated `seg_2A/s1_tz_lookup/runner.py` to update `counts` and `checks` during
  processing:
  - `counts.sites_total` updated immediately after each batch read.
  - `counts.border_nudged` updated whenever ε-nudge is applied.
  - `counts.distinct_tzids` updated as tzids are assigned.
  - `counts.rows_emitted` updated after each batch write.
  - `checks.null_tzid` and `checks.unknown_tzid` updated when detected.

Outcome: run-report now preserves partial progress data even if S1 aborts early
with a hard failure (2A-S1-055, 2A-S1-052, etc.).

### Entry: 2026-01-14 17:08

Design element: `tz_nudge` epsilon adjustment after S1 ambiguity (policy update).
Summary: With tz_world already at the latest release, the only spec-compliant
lever to resolve 2A-S1-055 is the sealed `tz_nudge` epsilon. This entry captures
the decision to increase epsilon conservatively and the exact digest derivation
so S0 can reseal a new manifest_fingerprint deterministically.

Decision reasoning (before editing the policy file):
1) **Scope of change:** tz_world is current, so we avoid changing spatial data.
   The spec allows adjusting `tz_nudge` (sealed policy) to change tie-break
   behavior for border ambiguity.
2) **Magnitude choice:** increase epsilon from `0.001` to `0.002` degrees as a
   minimal step. This is small enough to reduce risk of crossing borders
   incorrectly while still addressing a tie-break failure. Larger changes are
   deferred until we confirm whether this resolves the specific ambiguity.
3) **Semver discipline:** bump patch version from `1.3.0` to `1.3.1` to reflect
   the policy change without implying a behavioral overhaul.
4) **Digest computation (binding):** per the authoring guide, compute
   `sha256_digest` from the *effective payload*:
   - material string (UTF-8): `semver=1.3.1\nepsilon_degrees=0.002\n`
   - digest: `530f05cd912afcdd339d835a9fd2025d365e8919c1586162ac7d2074c66471b5`

Planned workflow after policy update:
1) Re-run **2A.S0** to reseal inputs and produce a new `manifest_fingerprint`
   that captures the updated tz_nudge policy.
2) Re-run **2A.S1** for the new manifest_fingerprint to verify the ambiguity
   resolves without violating other checks (coverage, PK, nudge rules).
3) If 2A-S1-055 persists, escalate only to the next conservative epsilon step
   (`0.005`), and repeat the reseal + rerun flow.

### Entry: 2026-01-14 17:10

Design element: S0 reseal failure after `tz_nudge` change (identity law conflict).
Summary: After increasing `tz_nudge` epsilon, re-running 2A.S0 failed with
`2A-S0-062 IMMUTABLE_PARTITION_OVERWRITE` because S0 still targets the existing
`manifest_fingerprint` partition derived from the upstream run receipt (1B),
so the new sealed inputs cannot be published into the old partition.

Observed failure (from `make segment2a-s0 RUN_ID=dbc151d09d5fd3053a74705bca1b673c`):
1) S0 verified 1B PASS and began sealing inputs normally.
2) `s0_gate_receipt_2A` already existed and was byte-identical (skip publish).
3) `_atomic_publish_dir` raised `2A-S0-062` when attempting to publish the new
   `sealed_inputs_2A` partition (bytes differ because tz_nudge digest changed).

Analysis (spec alignment check):
1) The 2A.S0 spec explicitly states **manifest_fingerprint is derived from the
   sealed-inputs manifest**, not borrowed from the upstream run receipt.
2) Current implementation binds `manifest_fingerprint` to the upstream 1B
   fingerprint, so a policy-only change (tz_nudge) cannot create a new
   partition; this is why we hit an immutable overwrite.
3) Fixing this to spec would require **computing a new manifest_fingerprint**
   from the sealed inputs, then writing outputs under that partition.

Open decision needed before code changes:
- **Spec-correct path:** update S0 to derive `manifest_fingerprint` from the
  sealed manifest and use that token for all S0 outputs. This will likely
  require upstream 1B PASS artefacts to exist under the *new* fingerprint, which
  implies re-fingerprinting/re-publishing upstream assets.
- **Deviation path (if approved):** keep `manifest_fingerprint` anchored to the
  upstream 1B fingerprint and treat `sealed_inputs.manifest_digest` as the
  policy-change fingerprint for audit only. This avoids re-running 1A/1B but
  deviates from the explicit 2A.S0 identity law.

No code changes made yet; awaiting direction on which identity posture to take
before proceeding with S0/S1 reruns.

### Entry: 2026-01-14 17:35

Design element: 2A.S0 manifest_fingerprint posture vs upstream identity.
Summary: User confirmed a spec correction direction: **keep upstream
manifest_fingerprint as the 2A.S0 identity**, and update the 2A.S0 spec to
align with other S0 gates (2B/3A/3B). This means 2A.S0 **does not derive**
manifest_fingerprint from the sealed-inputs manifest; instead it binds to the
upstream fingerprint and treats the sealed manifest digest as an audit marker.

Context and evidence:
1) 2A.S0 current spec states manifest_fingerprint is derived from sealed inputs.
2) 2B.S0, 3A.S0, and 3B.S0 explicitly treat manifest_fingerprint as **upstream**
   identity (S0 verifies PASS bundles for the same fingerprint and emits a
   manifest_fingerprint-scoped receipt; no local re-fingerprinting).
3) Current implementation already follows the upstream-identity posture; the
   spec mismatch caused confusion and the `IMMUTABLE_PARTITION_OVERWRITE`
   failure after policy changes (tz_nudge) because the sealed set changed while
   targeting the same upstream partition.

Decision (approved):
- Update 2A.S0 spec to **match upstream identity posture** (like 2B/3A/3B):
  manifest_fingerprint is **input authority** from upstream 1B, not derived
  from the sealed manifest. The sealed-inputs digest stays in the run report as
  an **audit-only** field, not the identity source.

Planned actions before reruns:
1) Edit `docs/model_spec/data-engine/layer-1/specs/state-flow/2A/state.2A.s0.expanded.md`
   to remove/replace all statements that say S0 computes manifest_fingerprint
   from sealed inputs; emphasize upstream fingerprint verification, path↔embed
   equality, and write-once immutability under that upstream identity.
2) Add explicit note that `sealed_inputs.manifest_digest` is recorded for audit
   but does **not** define `manifest_fingerprint` for 2A.
3) Re-run 1A and 1B to produce a **new upstream manifest_fingerprint** for the
   changed tz_nudge, then rerun 2A S0/S1 under that new manifest.

Rationale: Aligns 2A with the layered gate pattern and avoids inventing a new
identity surface that 2B/3A/3B do not use, while preserving determinism via
sealed_inputs digest for auditability.

### Entry: 2026-01-14 17:40

Design element: 2A.S0 spec correction (identity posture).
Summary: Implemented the spec update in
`docs/model_spec/data-engine/layer-1/specs/state-flow/2A/state.2A.s0.expanded.md`
to align with upstream identity binding.

Edits applied (highlights):
1) **Purpose/objectives/identity language** now states S0 binds the **upstream**
   `manifest_fingerprint` (verified via 1B PASS) and records a sealed-manifest
   **audit digest**; it does **not** derive a new fingerprint locally.
2) **Fingerprint derivation section** replaced with “Identity binding and
   sealed-manifest digest,” and all references to computing manifest_fingerprint
   from sealed inputs were removed or reframed as audit-only.
3) **Immutability rules** now require a **new upstream manifest_fingerprint**
   for any sealed-set change; otherwise the run must abort (no in-place edits).
4) **Run-report/logging/validator text** updated to describe audit digest usage
   and bound manifest_fingerprint (no identity derivation).
5) **Change-control and performance notes** updated to reflect upstream-bound
   identity and audit-digest canonicalisation language.

Next action (per user directive):
- Re-run 1A and 1B to obtain a fresh upstream manifest_fingerprint (note: if
  upstream inputs are unchanged, the fingerprint may remain identical; report
  outcome), then rerun 2A S0/S1 under the new upstream manifest.

### Entry: 2026-01-14 17:52

Design element: Upstream rerun to refresh manifest_fingerprint after 2A.S0 spec change.
Summary: Started the requested upstream rerun sequence to obtain a fresh
manifest_fingerprint for 2A gating under the new spec posture.

Actions and observations:
1) Ran `make segment1a` and completed a new run:
   - run_id: `6ae701ecb522395161651c18ab9b8823`
   - manifest_fingerprint: `241f367ef49d444be4d6da8b3bdd0009c0e1b7c3d99cc27df3a6a48db913044f`
   - observation: fingerprint **unchanged** vs prior runs because 2A policy
     changes (e.g., `tz_nudge`) do not affect 1A inputs.
2) Ran `make segment1b` and it progressed through S2 (`s2_tile_weights`).
   The run completed S2 under the same run_id and manifest_fingerprint:
   - run_id: `6ae701ecb522395161651c18ab9b8823`
   - manifest_fingerprint: `241f367ef49d444be4d6da8b3bdd0009c0e1b7c3d99cc27df3a6a48db913044f`
   The make invocation timed out after S2, so S3–S9 were not rerun yet.

Implication to track:
- If the upstream manifest_fingerprint remains unchanged, 2A.S0 can still
  proceed under a new run_id with the same manifest_fingerprint, but the
  sealed-inputs audit digest will differ due to the `tz_nudge` update. This
  is consistent with the updated spec posture but should be documented in the
  2A run report as an audit-only digest change.

### Entry: 2026-01-14 18:39

Design element: S1 border ambiguity investigation for key
`[merchant_id=14646030219073337247, legal_country_iso=RS, site_order=6]`
from run_id `a988b06e603fe3aa90ac84a3a7e1cd7c`.

Observed failure:
- S1 error `2A-S1-055 border_ambiguity_unresolved` with key
  `[14646030219073337247, "RS", 6]`.

Investigation steps and findings:
1) Located the site in 1B `site_locations` for the run:
   - Path: `runs/local_full_run-5/a988b06e603fe3aa90ac84a3a7e1cd7c/data/layer1/1B/site_locations/seed=42/manifest_fingerprint=241f367ef49d444be4d6da8b3bdd0009c0e1b7c3d99cc27df3a6a48db913044f/part-00000.parquet`
   - Row: `merchant_id=14646030219073337247`, `legal_country_iso=RS`,
     `site_order=6`, `lon_deg=18.951534`, `lat_deg=45.760335`.
2) Queried `reference/spatial/tz_world/2025a/tz_world_2025a.parquet`:
   - The point is **contained** in both `Europe/Belgrade` and `Europe/Zagreb`.
   - `touches=False` for both; this is **overlap**, not a boundary touch.
3) Applied the nudge epsilon (`0.002`) in 8 directions; **still returns both
   tzids** each time. The overlap area is larger than the nudge radius, so the
   ambiguity is not resolvable by the current nudge rule.

Conclusion:
- The point is not malformed; the tz_world polygons **overlap** for this
  location (RS). This is why S1 fails even after nudging.

Potential follow-ups (not yet applied):
1) Add a `tz_overrides` entry to force `Europe/Belgrade` (or the approved tzid)
   for this site key.
2) Fix the tz_world dataset overlap (upstream data correction), then re-seal.
3) If spec allows, implement a deterministic tie-break rule (e.g., by
   `legal_country_iso`), but this would be a spec change.

### Entry: 2026-01-14 19:04

Design element: tz_overrides policy update to resolve RS overlap failures.
Summary: Applied a **country-scope** override for Serbia to force
`Europe/Belgrade`, eliminating repeated ambiguity across seeds.

Decision context:
1) The failure point is in RS and the tz_world polygons **overlap** between
   `Europe/Belgrade` and `Europe/Zagreb`, so nudging cannot resolve it.
2) A **site-scope** override would fix this single key but could recur at other
   RS points; it also increases per-site policy churn.
3) A **country-scope** override is deterministic, stable across seeds, and
   aligns with Serbia having a single canonical tzid.

Action taken:
- Updated `config/layer1/2A/timezone/tz_overrides.yaml` with:
  `scope=country`, `target="RS"`, `tzid="Europe/Belgrade"`, and null expiry.

Planned follow-up:
- Rerun 2A S0 (to reseal inputs including `tz_overrides`) and 2A S1/S2 to
  confirm the ambiguity resolves and `tzid_source="override"` is applied for
  RS sites.

### Entry: 2026-01-14 19:16

Design element: S1 ambiguity fallback via `tz_overrides` (spec + runner alignment).
Summary: S1 currently hard-fails on unresolved ambiguity after a single nudge
(2A-S1-055). The policy decision is to **consult sealed tz_overrides only in
that ambiguity case**, so S1 can continue when an approved override exists
while remaining geometry-first for all unambiguous sites.

Plan and decisions (before code changes, detailed):
1) **Spec update (state.2A.s1.expanded.md).**
   - Replace the current "overrides not consumed in S1" posture with a
     conditional rule: S1 is geometry-only **unless** the single nudge still
     yields 0/2+ candidates, in which case S1 MAY apply a **sealed override**
     to choose `tzid_provisional`.
   - Keep S2 as the **canonical override application** for the final `tzid`;
     S1’s override use is strictly a fallback to resolve ambiguity so the run
     can proceed.
   - Add `tz_overrides` to the S1 input list, with the same **scope precedence**
     as S2: `site » mcc » country`.
   - If overrides include `scope: mcc`, S1 **must** read the sealed
     `merchant_mcc_map` (same as S0/S2 rules) or abort with 2A-S1-010.
   - Update 2A-S1-055 semantics to: ambiguity persists **after nudge and no
     applicable override is active**.

2) **Override activation rule (align to authoring guide).**
   - Treat an override as active iff `expiry_yyyy_mm_dd` is null **or**
     `expiry_yyyy_mm_dd >= date(S0.receipt.verified_at_utc)`.
   - Use the S0 receipt’s `verified_at_utc` as the cutoff date (deterministic,
     no wall-clock dependence). If the receipt lacks a timestamp, fall back to
     the run receipt `created_utc` and document the fallback in logs.

3) **Runner input wiring (S1).**
   - Add `tz_overrides` to `entries` + `registry_entries`, enforce schema_ref
     resolution, and verify presence in `sealed_inputs_2A`.
   - Load `tz_overrides` via `_load_yaml` and validate with
     `schemas.2A.yaml#/policy/tz_overrides_v1` (using layer1 defs).
   - If any override has scope `mcc`, resolve `merchant_mcc_map` by dictionary,
     verify it is sealed, and load a `merchant_id -> mcc` map for lookups.

4) **Ambiguity resolution logic (S1).**
   - Keep the existing geometry flow unchanged for `len(candidates) == 1`.
   - On `len(candidates) != 1` **after nudge**, attempt override selection:
     a) site key override (`"{merchant_id}|{legal_country_iso}|{site_order}"`),
     b) MCC override (if available),
     c) country override (`legal_country_iso`).
   - If an override resolves to a tzid not present in the sealed tz_world set,
     fail with 2A-S1-053 (unknown tzid) to keep membership guarantees.
   - If no active override applies, fail with 2A-S1-055 (unchanged error code).

5) **Observability adjustments.**
   - Add counts for `overrides_applied` and per-scope counts; emit a summary log
     once per run (no per-site spam).
   - Include `tz_overrides` identity (digest/version from sealed_inputs) in the
     S1 run-report inputs so auditors can see which override policy was used.

6) **No schema/output changes.**
   - S1 output shape stays the same; no new columns. Overrides only affect
     `tzid_provisional` for ambiguous sites.
   - Determinism preserved: same inputs + overrides + receipt date produce
     byte-identical outputs.

### Entry: 2026-01-14 19:40

Design element: S1 override fallback implementation (spec + runner changes).
Summary: Implemented the approved S1 posture: consult sealed `tz_overrides` only
when the post-nudge candidate set remains ambiguous, while keeping S2 as the
final override authority. Updated spec text and the runner to match.

Implementation actions (detailed):
1) **Spec update (S1 expanded doc).**
   - Added `tz_overrides` (and conditional `merchant_mcc_map`) to S1 inputs and
     per-input boundaries.
   - Reframed out-of-scope language to permit **post-nudge** override fallback,
     while keeping final override application in S2.
   - Updated run-report inputs and counts to include override identity and
     applied counts; updated structured log expectations.
   - Adjusted determinism statement, state-flow summary, and 2A-S1-055 wording
     to include the override fallback.

2) **Runner updates (`seg_2A/s1_tz_lookup/runner.py`).**
   - Added `tz_overrides` to dictionary/registry resolution, sealed-input checks,
     and INPUTS logs.
   - Loaded and schema-validated `tz_overrides` (policy/tz_overrides_v1) with
     layer1 defs; parsed active overrides using the S0 receipt date.
   - Built active override maps for `site`, `mcc`, and `country` scopes; logged
     when the policy is empty (no fallback).
   - If MCC overrides are active, resolved `merchant_mcc_map` via the sealed
     version tag, validated schema_ref, loaded a `merchant_id -> mcc` lookup,
     and failed closed if missing/empty.
   - Updated the ambiguity path: after the single nudge, apply overrides by
     precedence `site > mcc > country`, fail with 2A-S1-055 if none apply.
   - Enforced tzid membership for overrides (2A-S1-053 on unknown tzid).
   - Added override counters (`overrides_applied/site/mcc/country`) and a
     summary INFO log; surfaced override identity in the run-report inputs.

3) **Output surface unchanged.**
   - No schema or partition changes for `s1_tz_lookup`; only the selection
     logic for ambiguous sites changes.

### Entry: 2026-01-14 20:04

Design element: JSON Schema adapter support for `type: integer` (S1 validation failure).
Summary: S1 failed during JSON Schema adaptation because `schemas.2A.yaml` uses
`type: integer`, but the adapter only recognizes `int32/int64/...`. We need a
minimal, spec-aligned fix so validation can proceed without modifying contracts.

Observed failure:
- `ContractError: Unsupported column type 'integer' for JSON Schema adapter.`
  while adapting `s1_tz_lookup` output tables.

Decision reasoning (before implementation):
1) **Option A: update the adapter** to treat `integer` as a supported column
   type (map to JSON Schema `integer`). This matches JSON Schema semantics and
   keeps the contracts unchanged.
2) **Option B: change schema types** from `integer` to `int32/int64` in the
   2A schema pack. This would alter the spec contract surface and requires
   additional review/coordination because other components may already rely on
   `integer`.
3) **Option C: local hack in S1** to rewrite schemas before validation. This
   would be a one-off deviation and risks divergence across states.

Decision:
- Proceed with **Option A**: update the shared JSON Schema adapter to accept
  `type: integer`. This is a general, low-risk compatibility fix and keeps the
  contract pack authoritative.

Plan (before code changes):
1) Add `"integer": "integer"` to `_TYPE_MAP` in
   `packages/engine/src/engine/contracts/jsonschema_adapter.py`.
2) Ensure both `_column_schema` and `_item_schema` pick up the mapping.
3) Keep other behavior unchanged to avoid widening validation semantics.
4) Re-run `segment2a-s1` to confirm validation passes.

### Entry: 2026-01-14 20:16

Design element: JSON Schema adapter integer support (implementation).
Summary: Implemented `type: integer` support in the shared adapter so 2A S1
output validation can consume schema packs that already use `integer`.

Implementation actions (detailed):
1) Updated `_TYPE_MAP` in `packages/engine/src/engine/contracts/jsonschema_adapter.py`
   to include `integer -> integer`.
2) No changes to schema packs or S1 runner logic; the adapter now accepts
   `integer` wherever column/item types are mapped.

### Entry: 2026-01-14 20:12

Design element: JSON Schema adapter support for `type: number` (S1 validation failure).
Summary: After adding `integer`, S1 failed again because some 2A columns are
declared as `type: number`, which is valid JSON Schema but not supported by the
adapter. We need to expand the adapter mapping.

Observed failure:
- `ContractError: Unsupported column type 'number' for JSON Schema adapter.`
  during `s1_tz_lookup` output validation.

Decision reasoning (before implementation):
1) **Option A: update the adapter** to treat `number` as a supported column
   type (map to JSON Schema `number`). This aligns with JSON Schema itself and
   keeps contracts unchanged.
2) **Option B: change schema types** from `number` to `float32/float64` in the
   2A schema pack. This is a contract edit and may ripple to other uses.
3) **Option C: runner-local schema rewrite**, which would be a one-off
   divergence and risks inconsistent validation behavior across states.

Decision:
- Proceed with **Option A**: update the shared adapter to accept `number`.

Plan (before code changes):
1) Add `"number": "number"` to `_TYPE_MAP` in
   `packages/engine/src/engine/contracts/jsonschema_adapter.py`.
2) Ensure both column and array item mappings accept `number`.
3) Leave all other behavior unchanged.
4) Re-run `segment2a-s1` to confirm validation proceeds.

### Entry: 2026-01-14 20:14

Design element: JSON Schema adapter number support (implementation).
Summary: Implemented `type: number` support in the shared adapter so 2A S1
output validation accepts schema columns typed as `number`.

Implementation actions (detailed):
1) Updated `_TYPE_MAP` in `packages/engine/src/engine/contracts/jsonschema_adapter.py`
   to include `number -> number`.
2) No schema or runner changes; the adapter now recognizes `number` for both
   column and item schemas.

### Entry: 2026-01-14 20:10

Design element: S1 run verification after adapter fixes.
Summary: Re-ran `segment2a-s1` for run_id `a988b06e603fe3aa90ac84a3a7e1cd7c`
after adding adapter support for `integer` and `number`. The make command timed
out in the shell, but the run log shows S1 completed successfully and emitted
outputs.

Observed run evidence (from run log):
1) Output parquet written:
   - `runs/local_full_run-5/a988b06e603fe3aa90ac84a3a7e1cd7c/tmp/s1_tz_lookup_*/part-00000.parquet`
   - rows emitted: `34363`
2) EMIT event logged for
   - `data/layer1/2A/s1_tz_lookup/seed=42/manifest_fingerprint=241f367e.../`
3) Summary and completion line:
   - `S1: overrides applied total=2 (country=2)`
   - `S1 2A complete: run_id=a988... manifest_fingerprint=241f...`

Conclusion:
- S1 is green for run_id `a988b06e603fe3aa90ac84a3a7e1cd7c`.
- No further code changes needed for S1 at this time.
