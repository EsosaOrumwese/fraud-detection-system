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


