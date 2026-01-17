# segment_2B.impl_actual.md

Append-only implementation planning log for Segment 2B. Each entry documents the
design element, a short summary of the problem, and the detailed plan to resolve
it. Do not delete prior entries.

State-by-state approach: only the active state's planning is recorded here.
Reading ahead across 2B states is context-only and not an implementation plan.

---


## S0 - Gate & Environment Seal (S0.*)

### Entry: 2026-01-15 05:21

Design element: 2B.S0 gate and sealed-input inventory for manifest_fingerprint.
Summary: S0 must verify the upstream 1B PASS bundle before any 1B egress read,
seal all required inputs (1B/2A egress + 2B policy packs + optional cache),
emit a deterministic receipt and sealed inventory, and publish write-once
outputs under manifest_fingerprint-only partitions.

Plan (before implementation, detailed):
1) Establish run identity and resolve contract sources.
   - Load engine config and resolve ContractSource layout = model_spec.
   - Load run_receipt.json for run_id, seed, and parameter_hash.
   - Resolve dictionary, registry, and schema packs for 2B + layer1 + 1B/2A
     refs; record dictionary_version and registry_version.
   - Derive manifest_fingerprint from the 1B validation bundle path token and
     enforce path-embed equality on any outputs (manifest_fingerprint in path
     must match the embedded field).

2) Enforce the upstream 1B gate before any 1B egress read.
   - Resolve validation_bundle_1B and validation_passed_flag_1B via the
     dictionary (no literal paths).
   - Read the bundle index.json and validate against
     schemas.layer1.yaml#/validation/validation_bundle/index_schema.
   - Recompute the bundle digest by streaming raw bytes of each index.path
     in ASCII-lex order, excluding _passed.flag, and compare to the flag value.
   - Abort immediately on any mismatch (2B-S0-011/012/013) before reading
     site_locations or any other 1B egress.

3) Resolve and seal the minimum input set (required + optional cache).
   - Required IDs per spec/dictionary:
     - site_locations (seed + manifest_fingerprint)
     - site_timezones (seed + manifest_fingerprint)
     - route_rng_policy_v1, alias_layout_policy_v1, day_effect_policy_v1,
       virtual_edge_policy_v1 (manifest_fingerprint-only)
     - validation_bundle_1B + validation_passed_flag_1B (gate artefacts)
   - Optional cache: tz_timetable_cache (manifest_fingerprint-only). If
     missing, emit WARN (2B-S0-090) and continue.
   - For each resolved asset:
     - Capture catalog path, partition tokens, and schema_ref from dictionary.
     - Capture registry metadata (license/semver/version) for version_tag.
     - Compute sha256_hex if registry digest is a placeholder or missing;
       use deterministic directory hashing for datasets (ASCII-lex file order).
     - Allow duplicate byte sets across IDs (same sha256_hex, different id).

4) Build the receipt and inventory payloads deterministically.
   - Receipt sealed_inputs list contains {id, partition, schema_ref}, where
     partition is a token map (seed/manifest_fingerprint as applicable).
   - Inventory rows contain asset_id, version_tag, sha256_hex, path, partition,
     schema_ref (optional per schema).
   - Sort inventory rows by asset_id, then path. Validate "no duplicate ids"
     and receipt/inventory membership alignment (V-08, V-12).
   - Validate receipt + inventory against schemas.2B.yaml with layer1 defs.

5) Determinism receipt and policy digest capture.
   - Populate determinism_receipt from engine metadata (commit, python_version,
     platform). Populate policy_ids + policy_digests aligned 1:1, sorted by id.
   - Use the same verified_at_utc in the receipt and run-report. If the output
     already exists and is identical, reuse existing verified_at_utc to keep
     deterministic re-emits identical.

6) Emit run-report and publish outputs with write-once semantics.
   - Build the run-report with the spec-required counters, samples, and
     validator statuses; emit as a single JSON document to stdout (logger)
     and also persist under reports/layer1/2B/state=S0/manifest_fingerprint=...
     (non-authoritative diagnostic).
   - Stage outputs in run tmp, then atomic publish to dictionary-resolved
     paths. Enforce write-once and idempotent re-emit: if partition exists,
     compare bytes and only allow identical outputs; otherwise abort.

7) Logging narrative and performance discipline.
   - Story logs: GATE (bundle verification), INPUTS (required/optional counts),
     INVENTORY (row counts + duplicate byte sets), PUBLISH (bytes, targets),
     and VALIDATION events V-01..V-16 with error codes.
   - Progress logs for bundle hashing when the index is large (include elapsed,
     rate, eta). Avoid loading large datasets into memory; stream hashing.

Open confirmations to resolve before coding:
1) version_tag source for sealed_inputs_2B:
   - Plan: mirror 2A.S0 behavior (prefer registry semver; fall back to
     registry version or "unknown" if placeholders). Confirm if you want a
     stricter rule (e.g., abort when version_tag is placeholder).
2) run-report emission:
   - Plan: log the JSON run-report to stdout via logger.info and also persist
     the same JSON file under the run reports path. Confirm if you prefer
     stdout-only or file-only to reduce log volume.

### Entry: 2026-01-15 05:22

Design element: Resolve S0 confirmations and lock emission posture.
Summary: User approved the default version_tag fallback and dual run-report
emission. We will keep gating strict but avoid aborting solely for missing
version metadata.

Decision details (before implementation):
1) version_tag for sealed_inputs_2B:
   - Adopt the 2A.S0 rule: prefer registry semver, else registry version,
     else "unknown" (string). This avoids spurious aborts when upstream
     artefact metadata is incomplete.
   - Emit a WARN in the run-report (and logger) when any asset uses the
     placeholder value, but do not fail the gate.
   - Rationale: S0 is a trust boundary for data identity; missing metadata
     is a visibility problem, not a data-integrity failure, and should not
     block runs.

2) run-report emission posture:
   - Emit the run-report JSON to stdout via logger.info as a single JSON line
     for easy scraping, and also persist the same JSON file under the run
     reports path (diagnostic only, not authoritative).
   - Rationale: the spec requires stdout emission; the persisted file aids
     audits and CI without parsing logs. Single-line logging keeps console
     noise bounded.

### Entry: 2026-01-15 08:31

Design element: Implement 2B.S0 runner + CLI + Makefile wiring.
Summary: Added the S0 gate implementation for 2B, matching the spec's gate law,
sealed-input inventory, and run-report requirements, while keeping deterministic
hashing and write-once publishing.

Implementation steps and rationale (detailed, as executed):
1) New package scaffolding.
   - Created `packages/engine/src/engine/layers/l1/seg_2B/` and
     `seg_2B/s0_gate/` with `__init__.py` to mirror existing segment layout.
   - Added CLI `packages/engine/src/engine/cli/s0_gate_2b.py` patterned after
     2A’s S0 CLI for consistent config/args handling.

2) Implemented `seg_2B/s0_gate/runner.py` from scratch using 2A S0 patterns.
   - Helpers included: `_StepTimer`, `_ProgressTracker`, `_emit_event`,
     `_emit_validation`, `_hash_paths`, `_hash_partition`, `_atomic_publish_*`,
     `_resolve_dataset_path`, `_resolve_version_tag`.
   - Adopted the same staged publish and identical-output re-emit logic as 2A,
     but mapped errors to 2B codes (`2B-S0-080` for non-identical output,
     `2B-S0-082` for atomic publish failures).

3) Gate verification logic (No PASS -> No read).
   - Resolve `validation_bundle_1B` and `_passed.flag` via the Dictionary, then
     validate `index.json` against
     `schemas.layer1.yaml#/validation/validation_bundle/index_schema`.
   - Recompute bundle hash by ASCII-lex order of `index.path` and streaming
     raw bytes, skipping `_passed.flag`, then compare to flag value.
   - Abort on invalid index, flag format, or hash mismatch using `2B-S0-012`,
     `2B-S0-013`, `2B-S0-011` respectively.

4) Sealed inputs inventory generation.
   - Required IDs: gate artefacts, `site_locations`, `site_timezones`, and
     four 2B policy packs. Optional: `tz_timetable_cache` (warn-only).
   - Compute sha256_hex: bundle uses recomputed digest, files use `sha256_file`,
     directories use deterministic `_hash_partition`.
   - Partition enforcement: verify token embedding for assets with partition
     keys (`seed`, `manifest_fingerprint`), and emit `2B-S0-050` on mismatch.
   - Version tag policy: prefer registry `semver`, fall back to `version`, else
     `unknown`; placeholders trigger WARN via `V-09`.

5) Receipt and inventory payloads.
   - Receipt uses token-map partitions (not lists) per schema and includes
     `catalogue_resolution` + `determinism_receipt` (policy IDs/digests).
   - Inventory rows are ordered by `asset_id`, then `path`, and validated
     against `schemas.2B.yaml#/validation/sealed_inputs_2B`.
   - Receipt shape validated against `schemas.2B.yaml#/validation/s0_gate_receipt_v1`
     using `normalize_nullable_schema`.

6) Run-report implementation per spec.
   - Outputs include `gate`, `inputs_summary`, `inventory_summary`, `publish`,
     `validators`, `summary`, `environment`, `sealed_inputs_sample`,
     `gate_index_sample`, `id_map`, `durations_ms`.
   - Emitted to stdout as a single JSON line and persisted to the run reports
     path (diagnostic only), per approved decision.

7) Makefile wiring.
   - Added `SEG2B_S0_RUN_ID`, `SEG2B_S0_ARGS`, `SEG2B_S0_CMD`, `segment2b-s0`
     target, and included it in `.PHONY`.

Notes / open risks to watch during test run:
1) `V-09` uses warn semantics for placeholder version_tag (mapped to `2B-S0-041`
   but downgraded to WARN per approved decision).
2) Optional cache invalidity is treated as "missing" warn; deeper schema
   validation for cache is deferred until required by spec or observed failures.



### Entry: 2026-01-15 09:05

Design element: 2B.S0 PASS flag parsing failure (2B-S0-013) during gate.
Summary: The S0 gate failed while parsing the 1B `_passed.flag` even though the
file is present and appears to carry the expected sha256. This blocks the
gate before any bundle integrity check, so it must be resilient to small
formatting differences in the flag line.

Detailed reasoning and fix plan (in-process):
1) Reproduce and inspect the actual `_passed.flag` content.
   - Locate the 1B validation flag under the run-id path
     `runs/local_full_run-5/<run_id>/data/layer1/1B/validation/.../_passed.flag`.
   - Confirm the raw line string and verify whether it includes:
     - extra whitespace,
     - alternative separators (e.g., `:` instead of `=`),
     - or any leading BOM/encoding artifacts.
   - Even if the visible line is `sha256_hex = <64hex>`, the regex in the
     runner is stricter than it should be (single-space only) and will reject
     benign whitespace variations.

2) Adjust parsing to be tolerant but still strict about the digest value.
   - Update `_FLAG_PATTERN` to accept any whitespace around `=`.
   - Add a fallback search for a 64-hex token anywhere in the line so that
     variants like `sha256_hex: <hash>` or `sha256_hex=<hash>` still pass.
   - Keep the failure mode (2B-S0-013) if no 64-hex token is found, so this
     stays a validation guard rather than silently accepting arbitrary input.

3) Preserve determinism and safety.
   - The gate still validates that the recomputed bundle hash equals the flag
     digest. The relaxed parsing only prevents false negatives on formatting,
     not integrity violations.

Implementation action:
1) Update `seg_2B/s0_gate/runner.py` `_FLAG_PATTERN` and add fallback hex
   extraction when the strict pattern does not match.
2) Re-run `make segment2b-s0` and confirm the gate proceeds past V-01/V-03 to
   bundle hashing and receipt emission.

### Entry: 2026-01-15 09:08

Design element: Bundle index schema validation error handling in 2B.S0.
Summary: `Draft202012Validator` returns `ValidationError` objects; my earlier
raise path constructed `SchemaValidationError` with only a message string,
which violates the error type signature and raises a `TypeError` before the
intended 2B-S0-012 failure can be emitted.

Detailed reasoning and fix plan:
1) Align error construction with other segments (1B/2A).
   - Use the first validation error’s `.message` and pass a list of dicts
     (e.g., `[{ "message": <message> }]`) as the `errors` argument.
   - This preserves a deterministic error surface and keeps the same 2B
     failure code mapping for invalid bundle index content.

2) Confirm the fix by rerunning S0.
   - Expect S0 to proceed to bundle hashing; any actual schema issues will
     emit `2B-S0-012` with clear detail instead of a TypeError.

### Entry: 2026-01-15 09:13

Design element: Validation bundle index schema mismatch (1B bundle vs layer1 index_schema).
Summary: The 1B validation bundle’s `index.json` is a table with
`artifact_id/kind/path/mime/notes`, but the 2B runner validated it against the
layer1 `validation_bundle/index_schema` (path + sha256 only). This triggers
`2B-S0-012` even when the bundle is valid and blocks the gate.

Detailed reasoning and resolution plan:
1) Confirm the actual index schema in 1B contracts.
   - `schemas.1B.yaml` defines `validation_bundle_1B.index_schema` and
     `validation_bundle_index_1B` as a table with artifact_id/kind/path/mime/notes.
   - The 1B bundle index content matches the 1B schema, not the layer1 schema.

2) Align 2B dictionary schema_ref with 1B bundle contracts.
   - Update `dataset_dictionary.layer1.2B.yaml` entry `validation_bundle_1B`
     to reference `schemas.1B.yaml#/validation/validation_bundle_1B`, matching
     the 2A dictionary and the actual bundle shape.

3) Make the runner robust to bundle schema variants.
   - In `seg_2B/s0_gate/runner.py`, select index validation based on the
     dictionary’s `schema_ref`:
       - If it points at the 1B bundle, extract `index_schema` from the bundle
         and validate as a table using `validate_dataframe`.
       - Otherwise, fall back to the layer1 index_schema (path+sha256 array).
   - This preserves spec intent while preventing false failures from schema
     drift between layer1 and 1B bundles.

### Entry: 2026-01-15 09:17

Design element: Dictionary schema_ref lookup bug in 2B.S0.
Summary: While adding schema-ref–aware bundle index validation, I mistakenly
treated `entries["validation_bundle_1B"]` as an Entry wrapper instead of the
raw dictionary payload, causing an AttributeError on `.entry`.

Detailed fix plan:
1) Correct the lookup to use the dict directly (`entries["validation_bundle_1B"].get("schema_ref")`).
2) Re-run S0 to confirm the gate progresses past schema selection and into
   bundle hash verification.

### Entry: 2026-01-15 09:21

Design element: sealed_inputs_2B schema validation type mismatch.
Summary: `sealed_inputs_2B` is defined as a JSON schema array in
`schemas.2B.yaml`, but the runner attempted to validate it as a table via
`validate_dataframe`, which only supports table/stream/geotable/raster types.

Resolution plan:
1) Switch sealed_inputs_2B validation to use Draft202012Validator with the
   JSON schema returned by `_schema_from_pack(schema_2b, "validation/sealed_inputs_2B")`.
2) Preserve the same failure code (`2B-S0-031`) while reporting the first
   validation error string for clarity.
3) Re-run S0 to confirm the inventory validation passes and publishing proceeds.

### Entry: 2026-01-15 09:23

Design element: Semver alignment for 2B policy versions.
Summary: To make policy changes trackable and bumpable, align `policy_version`
and `version_tag` to an explicit semver (e.g., 1.0.0) and enforce semver format
in the 2B policy schemas.

Implementation plan (before edits):
1) Update all four 2B policy JSON files to set:
   - `policy_version: "1.0.0"`
   - `version_tag: "1.0.0"`
   This collapses version signaling to a single value while keeping both fields
   for compatibility.
2) Tighten `schemas.2B.yaml` policy definitions to require a semver pattern for
   `policy_version` (keep `version_tag` as a plain string).
3) Re-run `segment2b-s0` and clean any prior run-local outputs if write-once
   rejects the updated payloads.

### Entry: 2026-01-15 09:24

Design element: Semver enforcement applied to 2B policies.
Summary: Applied semver alignment by setting `policy_version` and `version_tag`
to `1.0.0` in all four 2B policy JSON files and tightened the 2B policy schemas
to require semver format for `policy_version`.

Actions taken:
1) Updated policy JSON files:
   - `config/layer1/2B/policy/route_rng_policy_v1.json`
   - `config/layer1/2B/policy/alias_layout_policy_v1.json`
   - `config/layer1/2B/policy/day_effect_policy_v1.json`
   - `config/layer1/2B/policy/virtual_edge_policy_v1.json`
   (set `policy_version` and `version_tag` to "1.0.0").
2) Updated `schemas.2B.yaml` to enforce a semver regex for `policy_version`
   across all four policy schemas.
3) Prepared to re-run S0 after clearing previous run-local outputs to satisfy
   write-once rules (since version tags changed).

### Entry: 2026-01-15 09:25

Design element: 2B.S0 receipt schema uses external layer1 $defs.
Summary: `s0_gate_receipt_v1` references `schemas.layer1.yaml#/$defs/uint64` and
`rfc3339_micros`. Draft202012Validator cannot resolve these external refs by
default, causing an Unresolvable error even when the payload is correct.

Resolution plan:
1) Inline layer1 $defs into the receipt schema before validation.
   - Add `_inline_external_refs` to replace refs of the form
     `schemas.layer1.yaml#/$defs/<name>` with the concrete def from the
     layer1 schema pack.
2) Use the inlined schema for validation and keep error code `2B-S0-030` for
   genuine receipt schema mismatches.

### Entry: 2026-01-15 09:25

Design element: Re-emit S0 after semver alignment.
Summary: Cleared the prior run-local S0 outputs (write-once guard) and re-ran
`make segment2b-s0`; the gate completed successfully with all validators PASS
and `warn_count=0`.

Run outcome details:
1) V-09 now PASS with version_tag resolved to "1.0.0" for policy assets.
2) Sealed inputs + receipt republished under the manifest_fingerprint path.

### Entry: 2026-01-15 09:31

Design element: 2B.S0 execution status after fixes.
Summary: S0 gate completed successfully with a WARN on version_tag placeholders
for the 2B policy JSON files (expected per decision). Outputs were published
under manifest_fingerprint partitions and run-report emitted.

Run outcome notes:
1) Gate PASS confirmed (bundle hash matched _passed.flag).
2) Inventory + receipt validation passed; outputs written to:
   - `data/layer1/2B/s0_gate_receipt/manifest_fingerprint=<hex>/s0_gate_receipt_2B.json`
   - `data/layer1/2B/sealed_inputs/manifest_fingerprint=<hex>/sealed_inputs_2B.json`
3) V-09 WARN raised for placeholder version_tag on policy assets; no abort.

### Entry: 2026-01-15 09:38

Design element: 2B policy version_tag placeholders (V-09).
Summary: Policy assets used `{policy_version}` in the dictionary/registry but
the policy JSON files only carried `version_tag`, so S0 could not resolve the
template and emitted placeholder warnings.

Resolution plan (per user direction):
1) Add `policy_version` to each 2B policy JSON and keep `version_tag` for
   backward compatibility.
2) Update `schemas.2B.yaml` policy definitions to allow/require
   `policy_version` (additionalProperties=false).
3) Update 2B.S0 runner to read `policy_version` (fallback to `version_tag`)
   from policy JSON and inject it as a token for version template rendering.
4) Re-run S0 to confirm V-09 no longer warns (unless a policy is missing the
   new field).

### Entry: 2026-01-15 09:44

Design element: Write-once re-emit after policy version update.
Summary: After introducing `policy_version`, previously published S0 outputs
for this run-id no longer matched the new sealed_inputs payloads, triggering
the write-once guard (`2B-S0-080`). To re-emit correctly, the old output
directories for this run-id had to be cleared.

Actions taken (deterministic and scoped):
1) Removed the existing run-local outputs under:
   - `runs/local_full_run-5/<run_id>/data/layer1/2B/s0_gate_receipt/manifest_fingerprint=<hex>/`
   - `runs/local_full_run-5/<run_id>/data/layer1/2B/sealed_inputs/manifest_fingerprint=<hex>/`
2) Re-ran `make segment2b-s0`; S0 completed with all validators PASS and
   `warn_count=0` in the run-report.

### Entry: 2026-01-15 13:45

Design element: S0 write-once guard blocks reseal (2B-S0-080).
Summary: Re-running `segment2b-s0` to refresh the sealed policy digest failed
because the prior S0 outputs already exist for this run_id and the byte
content now differs (expected after policy-byte changes).

Resolution plan (pending user confirmation, before any deletion):
1) Remove the run-local outputs for S0 under:
   - `runs/local_full_run-5/<run_id>/data/layer1/2B/s0_gate_receipt/manifest_fingerprint=<hex>/`
   - `runs/local_full_run-5/<run_id>/data/layer1/2B/sealed_inputs/manifest_fingerprint=<hex>/`
2) Re-run `make segment2b-s0` to regenerate receipt + sealed_inputs with the
   current policy digest.
3) Retry `make segment2b-s2` after S0 succeeds.

Note: per the write-once rules, deleting the old outputs is the only way to
allow the new seal to publish. Awaiting approval before removal.

### Entry: 2026-01-15 14:10

Design element: Reduce validation log spam and improve story-style logs for 2B.
Summary: The 2B runs emit many `VALIDATION` INFO lines (one per validator),
which obscures the state narrative. We will keep validator data in run-reports
but reduce INFO-level noise by logging PASS validations at DEBUG.

Detailed plan (before edits):
1) Adjust `_emit_validation` in each 2B runner (S0..S2).
   - Change PASS validations to log at DEBUG while keeping WARN/FAIL at the
     existing levels.
   - Keep the structured validation payload unchanged for WARN/ERROR so
     operators still see failures in the log.

2) Extend `_emit_event` to handle `severity == "DEBUG"`.
   - Map DEBUG severity to `logger.debug(...)` so PASS validation lines only
     appear when explicitly requested.
   - Preserve INFO/WARN/ERROR behavior for all other events.

3) Preserve story logs and run-report evidence.
   - Do not remove existing stage logs (e.g., “published alias index + blob”,
     “run-report written”, progress logs) so the narrative remains readable.
   - All validator results remain in the run-report JSON and error payloads.

Rationale:
- Operators want to scan logs for the state story; PASS validations belong in
  the run-report and should not dominate console output unless debugging.

### Entry: 2026-01-15 14:12

Design element: Implement 2B logging retrofit (S0-S2).
Summary: Updated validation logging across all 2B states so PASS validations
emit at DEBUG while WARN/FAIL remain visible at INFO/WARN/ERROR. This reduces
console noise while preserving full validator evidence in run-reports.

Implementation actions (explicit):
1) Updated `_emit_event` in:
   - `seg_2B/s0_gate/runner.py`
   - `seg_2B/s1_site_weights/runner.py`
   - `seg_2B/s2_alias_tables/runner.py`
   to handle `severity == "DEBUG"` via `logger.debug(...)`.

2) Updated `_emit_validation` in the same runners to:
   - log PASS validations at DEBUG,
   - keep WARN at WARN and FAIL at ERROR,
   preserving structured payloads for non-PASS outcomes.

Expected effect:
- Run logs now highlight the state narrative (gate, weights, alias build) without
  being dominated by PASS validation lines.

---


### Entry: 2026-01-15 20:59

Design element: S0 reseal attempt blocked by write-once publish (2B-S0-080).
Summary: Re-running 2B.S0 for the same run_id failed because the existing
`s0_gate_receipt_2B` output partition already exists and the new receipt bytes
do not match the prior output (expected when policy metadata changed). The
write-once guard correctly refused to overwrite.

Decision points (pending user confirmation):
1) Reseal strategy to unblock S3.
   - Option A: delete the existing run-local 2B S0 outputs for this run_id
     (`data/layer1/2B/s0_gate_receipt/...` and `data/layer1/2B/sealed_inputs/...`)
     and re-run `segment2b-s0` to publish a new sealed_inputs_2B.
   - Option B: start a fresh run_id (rerun 1A/1B/2A or `make all`) so S0 seals
     into a clean run directory, preserving write-once invariants.

2) My recommendation.
   - Prefer Option B in production to preserve audit lineage.
   - In dev mode, Option A is acceptable if you explicitly approve deletion of
     the S0 outputs for this run_id.

3) Next action (blocked until approval).
   - Once approved, perform the selected reseal approach and re-run S3.



### Entry: 2026-01-16 05:31

Design element: Optional sealing of `s5_arrival_roster` in 2B.S0.
Summary: User requested that the run-scoped arrival roster be sealed in S0
when present, so S5 reads only catalogued + sealed inputs for standalone runs.

Decision + plan update (before implementation):
1) Keep the roster optional but seal when present.
   - If `s5_arrival_roster` exists at the run-scoped partition
     `[seed, parameter_hash, run_id]`, add it to `sealed_inputs_2B` and the
     inventory list with its path + sha256_hex.
   - If missing, continue without abort (standalone runs can supply arrivals
     later, or L2 can supply arrivals).

2) S0 validation posture.
   - Treat roster absence as INFO (not WARN) to avoid noise; only enforce
     sealing when the dataset is present.
   - Rationale: the roster is a dev/test convenience but should not block
     runs in production flows where arrivals are streamed from L2.

3) Run-report update.
   - Include `s5_arrival_roster` in `inputs_summary` only when sealed; ensure
     `catalogue_resolution` includes its registry version_tag when present.

4) Logging.
   - Add a narrative log line noting whether the roster was sealed or skipped,
     and its resolved path when present.


## S1 - Per-merchant weight freezing (S1.*)

### Entry: 2026-01-15 09:31

Design element: 2B.S1 deterministic per-merchant weight freezing (s1_site_weights).
Summary: S1 must derive a deterministic probability law per merchant from
site_locations using alias_layout_policy_v1 (floors/caps/normalisation/quantise),
emit a strict schema table (s1_site_weights), and publish a structured run-report
with deterministic samples and counters, all under write-once + atomic publish.

Pre-implementation review (spec + contracts) and observations:
1) State spec (state.2B.s1.expanded.md) requires:
   - RNG-free pipeline, dictionary-only resolution, seed+manifest_fingerprint
     partitioning, path-embed equality, write-once + idempotent re-emit.
   - Output created_utc must echo S0 receipt verified_at_utc.
   - Optional pins (site_timezones + tz_timetable_cache) are all-or-none; if
     mixed, log WARN and ignore both (no effect on weights).
   - Run-report is mandatory to stdout; persisted copy is optional (allowed).
2) Contract bindings:
   - Output schema: schemas.2B.yaml#/plan/s1_site_weights (columns strict).
   - Inputs: schemas.1B.yaml#/egress/site_locations and
     schemas.2B.yaml#/policy/alias_layout_policy_v1.
   - Dictionary entry for alias_layout_policy_v1 uses {policy_version} token;
     2B.S0 now injects policy_version from policy JSON.
3) Policy/schema mismatch identified:
   - alias_layout_policy_v1 schema requires many fields not present in the
     current policy JSON (policy_id, padding_rule, fallback,
     required_s1_provenance, record_layout, checksum, blob_digest,
     required_index_fields).
   - If S1 validates against the policy schema, the current policy file will
     fail. Plan must reconcile this by updating the policy JSON (preferred) or
     relaxing schema (not preferred because schema is shape authority).

Detailed plan (before implementation, step-by-step):
1) Resolve inputs and gate conditions.
   - Load S0 receipt and sealed_inputs_2B for the manifest_fingerprint.
   - Resolve site_locations and alias_layout_policy_v1 via dictionary IDs only.
   - Enforce that both assets appear in sealed_inputs_2B for this manifest.
   - Optional pins: if both site_timezones + tz_timetable_cache appear in S0
     inventory, record their resolved paths for run-report; if only one is
     present, emit WARN and ignore both.

2) Reconcile alias_layout_policy_v1 schema vs JSON content.
   - Expand policy JSON to satisfy schemas.2B.yaml#/policy/alias_layout_policy_v1
     required fields, using deterministic defaults consistent with current intent:
       * policy_id = "alias_layout_policy_v1"
       * padding_rule.pad_byte_hex = "00" (align with existing padding_value)
       * fallback = { mode: "uniform" } (matches floor_spec.fallback)
       * required_s1_provenance = { weight_source: true, quantised_bits: true,
         floor_applied: true } (explicit policy echo)
       * record_layout.prob_qbits = quantised_bits
       * checksum/blob_digest objects aligned to checksum algorithm in encode_spec
       * required_index_fields header/merchant_row minimal sets aligned to S2
   - If you want a different policy expansion instead of defaults, confirm
     before coding (see open confirmations).

3) Deterministic weight derivation per spec.
   - Compute base weight per row from policy.weight_source:
     * if weight_source.mode == "uniform", set w_i = 1.0 for all sites.
     * else, use the policy-declared column name or transform (strictly
       deterministic; no RNG, no external IO).
   - Validate domain: w_i finite and >= 0; abort on NaN/inf/negative.
   - Apply floor/cap per policy (absolute/relative); track floor_applied flag.
   - Zero-mass fallback: if sum(u_i) <= 0, apply policy fallback (uniform over
     merchant sites) and set floor_applied true for those rows.
   - Normalise per merchant; enforce |sum(p_i) - 1| <= normalisation_epsilon.
     Clamp tiny negatives within tiny_negative_epsilon if policy allows; then
     re-normalise once.

4) Quantisation to integer grid (deterministic ties).
   - Use quantised_bits b => grid size G=2^b.
   - Compute scaled masses m_i = p_i * G; round half-to-even to integers.
   - Adjust deficit/surplus deterministically using fractional remainder and PK
     tie-breaks (per spec). Ensure per-merchant integer mass exact.
   - Ensure per-row |p_hat - p_i| <= quantisation_epsilon; abort if violated.

5) Build output rows and enforce PK ordering.
   - Output columns: merchant_id, legal_country_iso, site_order, p_weight,
     weight_source, quantised_bits, floor_applied, created_utc.
   - created_utc = S0 receipt verified_at_utc.
   - Writer order strictly by PK. If input not already grouped, do deterministic
     sort by PK (external sort if needed; avoid memory blowups).

6) Run-report emission (spec-complete, deterministic).
   - Emit single JSON run-report to stdout (logger.info).
   - Include required top-level fields, counters, deterministic samples, and
     id_map with resolved paths.
   - Persist identical JSON file under reports/layer1/2B/state=S1/... (diagnostic).
   - Deterministic ordering for validators, samples, and lists.

7) Publish with write-once + atomic move.
   - Stage outputs under run tmp, then atomic publish to dictionary path.
   - If partition exists, compare bytes; allow only identical re-emit.
   - Emit validators (V-01..V-20) with PASS/WARN/FAIL mapping.

8) Performance discipline.
   - Stream per-merchant windows to keep memory O(max K).
   - Avoid parallel reductions that change floating order; use stable serial sums.
   - Log progress by merchants processed with elapsed/rate/eta.

Open confirmations to resolve before coding:
1) Policy schema alignment: approve expanding alias_layout_policy_v1 JSON to
   satisfy the current schemas.2B.yaml requirements (recommended), or do you
   want the schema relaxed to match the existing smaller policy?
2) weight_source label to emit:
   - Plan: emit policy.weight_source.id if present, else policy.weight_source.mode,
     else "unknown". Confirm if you want a different label.
3) Optional pins usage:
   - Plan: if both site_timezones + tz_timetable_cache are sealed, only record
     them in run-report/id_map (no effect on weights). If you want them to
     influence weighting or additional validation, confirm the intended logic.

### Entry: 2026-01-15 10:19

Design element: 2B.S1 per-merchant weight freezing (implementation start).
Summary: Proceeding to implement S1 with the updated policy schema, policy-driven
weight selection, deterministic floors/normalisation/quantisation, and spec-
complete run-report emission (stdout + file). Optional pins are treated as
presence-only signals (warn if mixed; no effect on weights).

Decision details (before coding):
1) Policy schema alignment.
   - Accept the expanded `alias_layout_policy_v1` JSON (now includes the required
     structural fields like `layout_version`, `record_layout`, `checksum`, etc.).
   - Rationale: keep schemas authoritative; policy bytes are sealed inputs and
     a stable source of truth.

2) weight_source label + column handling.
   - Emit `weight_source` as `policy.weight_source.id` if present, else
     `policy.weight_source.mode` (string). This matches spec-provenance.
   - Supported modes for weight extraction: `uniform` (no column) and `column`
     (column name required). If mode is unknown or the column is missing, abort
     with 2B-S1-033.
   - Rationale: minimal deterministic support without inventing transform logic.

3) Optional pins (site_timezones + tz_timetable_cache).
   - If both are sealed, record them in run-report/id_map only.
   - If exactly one is sealed, emit 2B-S1-090 WARN and proceed without either.
   - Rationale: S1 weights are independent of TZ; pins are retained for lineage.

4) Tiny-negative clamp threshold.
   - Use `policy.tiny_negative_epsilon` if present; otherwise fall back to
     `normalisation_epsilon`. Clamp only when `-eps <= p_i < 0`; otherwise abort.
   - Rationale: follow the spec’s clamp rule with a policy-tunable threshold.

5) Run-report emission posture.
   - Emit a single JSON run-report to stdout (via `print/json.dumps`) on success,
     and also persist the same JSON file under reports/layer1/2B/state=S1/...
   - Rationale: spec requires stdout JSON; file copy aids audits.

Implementation plan (immediate steps):
1) Implement `run_s1` in `seg_2B/s1_site_weights/runner.py` with:
   - S0 receipt validation, sealed-input verification, optional-pin handling.
   - Policy validation (schema + minima), weight extraction, floors/caps,
     fallback, normalisation, quantisation, PK-ordered emission.
   - Validator event emissions V-01..V-20 and error mapping.
2) Add CLI `engine/cli/s1_site_weights_2b.py` (patterned after 2A S1).
3) Add Makefile wiring (`SEG2B_S1_*` + `segment2b-s1` target).
4) Run `make segment2b-s1`, fix any failures, and log outcomes + fixes here.

### Entry: 2026-01-15 10:46

Design element: Policy schema acceptance for new S1 fields.
Summary: The first S1 run failed with `2B-S1-031` because the policy JSON
contains `cap_spec`, `tiny_negative_epsilon`, and `notes`, but the
`alias_layout_policy_v1` schema disallowed them via `additionalProperties=false`.

Detailed reasoning and resolution (in-process):
1) The runner now consumes `cap_spec` and `tiny_negative_epsilon`, and `notes`
   is a harmless metadata field. These are legitimate policy bytes that we
   intend to seal and validate, so the schema should acknowledge them rather
   than forcing policy changes or ignoring fields.
2) Update `schemas.2B.yaml` to add optional properties:
   - `cap_spec` as an object with `additionalProperties: true` (parallel to
     `floor_spec`).
   - `tiny_negative_epsilon` as a non-negative number.
   - `notes` as a string.
3) Re-run S1 after schema update to confirm policy validation passes and the
   runner proceeds into weight derivation.

### Entry: 2026-01-15 10:47

Design element: Semver regex validation in 2B policy schemas.
Summary: After adding `cap_spec`, S1 failed again because the semver pattern
in `policy_version` used a double-escaped dot (`\\.`) under YAML single quotes,
which made the regex require a literal backslash and reject `1.0.0`.

Detailed fix and rationale:
1) Replace the pattern string with a single-escape form so the regex engine
   sees `\.` and accepts `1.0.0`.
2) Apply the same correction to all 2B policy schema definitions to avoid
   future false failures (alias_layout/day_effect/route_rng/virtual_edge).
3) Re-run S1 to confirm `policy_version` passes validation.

### Entry: 2026-01-15 10:48

Design element: Polars batch writer overflow for uint64 merchant_id.
Summary: S1 failed mid-run when building a `pl.DataFrame` from batch rows;
Polars inferred a signed integer builder from early rows and then overflowed
when a merchant_id exceeded int64 range (id64 is uint64 per schema).

Detailed fix and implementation:
1) Define an explicit output schema for batch construction:
   - `merchant_id` -> `pl.UInt64`
   - `legal_country_iso` -> `pl.Utf8`
   - `site_order` -> `pl.Int64`
   - `p_weight` -> `pl.Float64`
   - `weight_source` -> `pl.Utf8`
   - `quantised_bits` -> `pl.Int64`
   - `floor_applied` -> `pl.Boolean`
   - `created_utc` -> `pl.Utf8`
2) Add `_build_batch_df(rows)` helper and use it for both batch and final
   flush to guarantee consistent dtypes regardless of row order.
3) Re-run S1 to confirm the batch writer handles uint64 ids without overflow.

### Entry: 2026-01-15 10:49

Design element: 2B.S1 green run verification.
Summary: After schema + dtype fixes, `make segment2b-s1` completed successfully.

Run outcome notes:
1) Validators V-01..V-20 PASS; no WARNs.
2) Output published to
   `data/layer1/2B/s1_site_weights/seed=42/manifest_fingerprint=241f.../`
   with write-once verified and atomic publish.
3) Run-report emitted to stdout and persisted under
   `reports/layer1/2B/state=S1/seed=42/manifest_fingerprint=241f.../`.

### Entry: 2026-01-15 13:48

Design element: S1 write-once guard blocks re-emit (2B-S1-080).
Summary: After resealing S0, re-running S1 produced new weights but failed to
publish because the existing `s1_site_weights` partition already exists with
different bytes (write-once guard).

Observed failure:
- `EngineFailure: F4:2B-S1-080` from `_atomic_publish_dir` while attempting to
  publish `data/layer1/2B/s1_site_weights/seed=42/manifest_fingerprint=<hex>/`.

Resolution plan (pending user approval, before deletion):
1) Remove the existing run-local S1 output directory:
   - `runs/local_full_run-5/<run_id>/data/layer1/2B/s1_site_weights/seed=42/manifest_fingerprint=<hex>/`
2) Re-run `make segment2b-s1` to publish the refreshed weights.
3) Proceed to `make segment2b-s2` once S1 is green.

### Entry: 2026-01-15 14:04

Design element: Correct S1 normalisation scope to match per-merchant spec.
Summary: S2 alias decode coherence failures revealed that S1 normalises
probabilities per (merchant_id, legal_country_iso) instead of per merchant_id,
violating the S1 spec requirement that each merchant's total mass sums to 1.
This must be fixed in S1 to keep S2/S3/S4 coherent.

Detailed plan (before edits, recorded for audit):
1) Confirm spec intent and mismatch.
   - Re-read `state.2B.s1.expanded.md` (Sections 2, 7.2, 7.5, 6.2): S1 must
     normalise per merchant, not per country slice.
   - Observed S2 failure showed `sum(p_weight) > 1` for a single merchant with
     multi-country sites, proving the current S1 grouping is too granular.

2) Code changes required in `seg_2B/s1_site_weights/runner.py`.
   - Change grouping from `["merchant_id", "legal_country_iso"]` to
     `["merchant_id"]` so the normalisation mass is per merchant.
   - Update `merchants_total` to be `n_unique(merchant_id)` and keep progress
     tracking per merchant (spec-aligned counters).
   - Keep PK order for output rows; use the per-row `legal_country_iso` value
     when constructing the output rows and PK tuples.
   - Update error payloads to include a small `legal_country_iso` sample/count
     rather than a single value (multiple countries per merchant now).
   - Keep run-report samples per merchant (no legal_country_iso in
     `samples.normalisation`), matching the spec.

3) Re-emit S1 outputs after code change.
   - Remove the existing run-local S1 partition for this run_id
     (`.../data/layer1/2B/s1_site_weights/seed=42/manifest_fingerprint=.../`)
     to satisfy write-once semantics (approved by user).
   - Re-run `make segment2b-s1` and then `make segment2b-s2`, inspect the S2
     run-report for decode coherence and mass checks.

Implementation action taken immediately after logging this plan:
1) Updated S1 runner to group by merchant_id only and adjust error payloads to
   include country samples (per the plan above).
2) Next: remove the run-local S1 output directory and re-run S1 + S2.

### Entry: 2026-01-15 14:06

Design element: Re-emit S1 after per-merchant normalisation fix.
Summary: Removed the run-local S1 output partition for the active run_id and
re-ran `make segment2b-s1`; the run completed green and published corrected
per-merchant weights.

Actions and observations (post-fix):
1) Removed the existing run-local partition:
   `runs/local_full_run-5/a988b06e603fe3aa90ac84a3a7e1cd7c/data/layer1/2B/s1_site_weights/seed=42/manifest_fingerprint=241f.../`
   (required by write-once semantics).
2) Re-ran `make segment2b-s1 RUN_ID=a988b06e603fe3aa90ac84a3a7e1cd7c`.
   - `merchants_total=1280`, `sites_total=34363`.
   - `max_abs_mass_error_pre_quant=4.44e-16` and `merchants_over_epsilon=0`.
   - All validators V-01..V-20 PASS; run-report emitted and persisted.
3) The corrected weights now reflect per-merchant mass = 1 across all sites
   (across legal_country_iso), aligning with the S1 spec.




## S2 - Alias tables (O(1) sampler build) (S2.*)

### Entry: 2026-01-15 11:05

Design element: 2B.S2 alias index + blob construction (policy-governed, RNG-free).
Summary: S2 must take `s1_site_weights` + `alias_layout_policy_v1` and emit a
byte-stable alias blob + index under `[seed, manifest_fingerprint]`, following
the deterministic Walker/Vose encoding and policy-declared layout/endianness/
alignment. The run-report must provide a bounded, deterministic evidence trail.

Pre-implementation review (spec + contracts) and key observations:
1) Inputs are only `s1_site_weights@seed,manifest_fingerprint` plus the
   token-less `alias_layout_policy_v1` (must match the S0-sealed path/digest).
   No 2A pins or other artefacts are allowed; S0 receipt is the gate.
2) Output shapes are `schemas.2B.yaml#/plan/s2_alias_index` (JSON fields-strict)
   and `schemas.2B.yaml#/binary/s2_alias_blob` (layout/endianness/alignment
   echoed from policy).
3) The authoring guide for `alias_layout_policy_v1` is the real layout contract:
   it defines slice headers, prob_q encoding, checksum scope, and decode law
   semantics that S5/S6 will rely on.

Decisions and alignment posture (before coding):
1) Policy alignment with authoring guide.
   - Extend `alias_layout_policy_v1.json` encode/decode fields to match the
     authoring guide (mass_rounding, delta_adjust, deterministic queue order,
     decode-law identifier, record_layout header/prob_qbits/prob_q_encoding,
     alias_index_type).
   - Keep `quantised_bits` at 24 (as used by S1), but set
     `record_layout.prob_qbits = 32` and `decode_law = "walker_vose_q0_32"`
     to follow the guide’s explicit decode semantics.
   - This is a sealed policy change: it will require re-running 2B.S0 and 2B.S1
     for the same run_id so S2’s policy digest echo matches S0 inventory.

2) Deterministic queue convention (V-27).
   - Implement the exact small/large queue rules in §7.4:
     * small = m_i < M, large = m_i >= M, with m_i == M treated as large.
     * queues initialised in PK order and pop from the front.
   - Track any equality-handling deviation; if detected, emit V-27 WARN with a
     small evidence sample, but continue only if decode coherence holds.

3) Decode spot-check scope.
   - Use a deterministic sample of first N merchants in ascending `merchant_id`,
     decode their slices using `decode_law`, and enforce `|p̂ − p| <= ε_q` and
     Σ p̂ = 1 per merchant (2B-S2-055). This bounds cost and matches spec.

Detailed plan (step-by-step, before implementation):
1) Resolve run identity and gate.
   - Load `run_receipt.json` (seed/parameter_hash/manifest_fingerprint).
   - Validate `s0_gate_receipt_2B` and `sealed_inputs_2B` exist for this
     fingerprint; enforce that `alias_layout_policy_v1` is sealed with the
     exact path + sha256 digest.
   - Resolve `s1_site_weights` strictly by Dictionary ID and exact partitions.

2) Policy validation and minima checks.
   - Validate policy against `schemas.2B.yaml#/policy/alias_layout_policy_v1`.
   - Enforce minima: `layout_version`, `endianness`, `alignment_bytes`,
     `quantised_bits`, `quantisation_epsilon`, `encode_spec`, `decode_law`,
     checksum + blob_digest rules, required index fields.
   - Extract record_layout/prob_qbits and encode_spec parameters to drive
     encode + serialisation.

3) Load S1 weights and enforce coherence.
   - Read `s1_site_weights` (PK order), verify `quantised_bits` constant and
     equals policy `b`.
   - Group by merchant_id and process sites in PK order for determinism.

4) Integer grid reconstruction (RNG-free).
   - Compute G = 2^b; for each site, m* = p_weight * G and
     m0 = round_half_to_even(m*).
   - Apply residual-ranked ±1 adjustment to reach Σ m_i = G; tie-break by PK.
   - Abort on negative or overflow masses (2B-S2-052/053).

5) Walker/Vose alias encoding (deterministic).
   - Compute M = G / K in binary64; initialise small/large queues by PK order.
   - Emit prob/alias entries per encode_spec; follow deterministic equality
     handling (m_i == M treated as large).
   - Finish remaining items with self-alias entries.

6) Slice serialisation + blob write.
   - Write per-merchant slice payload with header + prob_q + alias arrays as
     declared in `record_layout` and `encode_spec`; enforce endianness and
     alignment padding between slices.
   - Compute per-slice checksum (sha256 over payload bytes, excluding padding).
   - Track offsets/lengths, ensure alignment and non-overlap.

7) Build index + global digest.
   - Emit header fields (layout_version, endianness, alignment_bytes,
     quantised_bits, created_utc, policy_id, policy_digest).
   - Compute blob_sha256 over raw bytes; set blob_size_bytes and merchants_count.
   - Validate index against schema; enforce ascending merchant_id order.

8) Decode spot-check + metrics.
   - Decode a bounded deterministic sample from blob using decode_law; compute
     max_abs_delta_decode and merchants_mass_exact_after_decode.

9) Publish + run-report.
   - Stage outputs under run tmp; atomic publish both index + blob; write-once
     idempotent re-emit only if bytes identical.
   - Emit run-report JSON to stdout and persist file; include required samples,
     counters, validators, id_map, and durations_ms (resolve/reconstruct/encode/
     serialize/digest/decode_check/publish).

Implementation order:
1) Update `alias_layout_policy_v1.json` to match the authoring guide (with
   semver bump if needed).
2) Add `seg_2B/s2_alias_tables/runner.py` + CLI (`s2_alias_tables_2b.py`).
3) Makefile wiring: `SEG2B_S2_*` args and `segment2b-s2` target.
4) Re-run `segment2b-s0` + `segment2b-s1` (policy digest changed), then
   `segment2b-s2` until green; log each failure + fix here.

### Entry: 2026-01-15 11:17

Design element: 2B.S2 policy alignment (alias_layout_policy_v1) before coding.
Summary: Lock the policy to the authoring guide so S2 emits a binary layout that
S5/S6 can decode deterministically, then proceed to implement the S2 runner.

Decisions and rationale (recorded before code changes):
1) Update alias_layout_policy_v1 to the authoring guide’s concrete layout/encode
   posture (v1 production baseline).
   - Set `layout_version` to a clear layout identifier (`2B.alias.blob.v1`) to
     match the authoring guide’s naming and avoid ambiguous layout labels.
   - Keep `quantised_bits = 24` (already used by S1 and within realism floors).
   - Set `record_layout.prob_qbits = 32` and `decode_law = "walker_vose_q0_32"`
     to match the guide’s required decode semantics; S2 will encode Q0.32
     probabilities and downstream decode will match the Q0.32 law.
   - Replace the ad-hoc byte-size encode_spec fields with the guide’s
     algorithmic encode_spec keys: mass_rounding, delta_adjust, worklist_order,
     treat_within_epsilon_of_one_as_one. Keep padding rules under padding_rule.
   - Expand record_layout to declare slice_header, prob_q_encoding, and
     alias_index_type so the blob layout is fully specified in policy bytes.
   - Update required_index_fields.header to include `merchants` per the guide
     (header fields must fully declare the top-level index structure).

2) Version bump for policy identity.
   - Because policy bytes change, bump `policy_version` and `version_tag` to
     `1.0.1` so the change is traceable and a new digest is sealed by S0.
   - This necessitates re-running 2B.S0 and 2B.S1 for the same run_id to update
     `sealed_inputs_2B` and `s1_site_weights` to the new policy digest.

3) Implementation order remains: policy update → S2 runner/CLI/Makefile → re-run
   S0/S1 to reseal → run S2 until green.

### Entry: 2026-01-15 11:28

Design element: 2B.S2 alias table encoding implementation kickoff.
Summary: Begin coding the S2 runner/CLI/Makefile with deterministic per-merchant
streaming, Walker/Vose alias encoding, Q0.32 probability packing, and write-once
publishing for the index + blob.

Detailed implementation decisions (before code edits):
1) Input loading and grouping posture.
   - Read `s1_site_weights` via polars, projecting only the required columns:
     merchant_id, legal_country_iso, site_order, p_weight, quantised_bits.
   - Enforce PK monotonicity (merchant_id, legal_country_iso, site_order) while
     iterating. If out-of-order, abort with 2B-S2-083 instead of resorting, to
     avoid nondeterministic external sort costs.
   - Group by merchant_id in the existing order (maintain_order=True), and keep
     memory bounded to a single-merchant window.

2) Policy/minima validation and bit-depth coherence.
   - Validate the policy JSON against `schemas.2B.yaml#/policy/alias_layout_policy_v1`.
   - Enforce required minima keys and compatibility: `decode_law` matches
     `record_layout.prob_qbits`, `quantised_bits` is constant in S1 and equals
     the policy value, `alignment_bytes` >= 1, and checksum rules are present.

3) Integer grid reconstruction per merchant.
   - Use round-to-nearest-even (`numpy.rint`) on `p_weight * G` (G = 2^b).
   - Compute deficit `delta = G - sum(m)` and apply residual-ranked +/-1 adjust
     with deterministic tie breaks (residual then PK index). Abort if the sum
     cannot be reconciled or any m_i is negative or > G.

4) Walker/Vose alias encoding (deterministic queues).
   - Compute scaled masses and initialize small/large queues in ascending index
     order. Treat m_i == M as large, and pop/push queues from the front/back to
     preserve deterministic order. Track any equality handling deviations to
     emit V-27 WARN evidence without altering the output.

5) Serialization + checksums.
   - Write each merchant slice as: header (u32 n_sites, u32 prob_qbits, u32 0, u32 0),
     then prob_q uint32 array and alias uint32 array, in the policy endianness.
   - Encode prob_q using Q0.32: floor(prob * 2^32), clamp to [1, 2^32-1].
   - Compute per-slice checksum over payload bytes only; length excludes padding.
   - Insert alignment padding between slices; track offsets and lengths, and
     stream blob sha256 as bytes are written.

6) Index generation and validation.
   - Build the index header with required fields (including merchants array),
     set blob_size_bytes and blob_sha256, and ensure merchants_count matches
     the number of rows.
   - Validate index JSON against `schemas.2B.yaml#/plan/s2_alias_index` with
     Draft202012Validator. Enforce non-overlap and bounds with explicit checks.

7) Publish and run-report emission.
   - Stage index + blob under run tmp; atomic publish both with write-once
     guard. If either exists and bytes differ, abort with 2B-S2-080.
   - Emit run-report JSON to stdout and persist the same JSON file; include
     deterministic samples, validators, id_map, and durations_ms.
### Entry: 2026-01-15 11:55

Design element: 2B.S2 alias table runner implementation (file creation + core algorithm wiring).
Summary: Begin actual coding for S2, ensuring the runner matches the spec’s deterministic Walker/Vose encode, Q0.32 packing, policy echo, write-once publish, and run-report evidence rules.

Implementation posture and concrete choices (recorded before code edits):
1) File/runner layout.
   - Create `packages/engine/src/engine/layers/l1/seg_2B/s2_alias_tables/runner.py` and keep the module name aligned with S2 (“alias tables”).
   - Use the same logging/event helpers as S1/S0 to keep run logs story-like and consistent.
   - Reuse S0 helper functions for path resolution, schema extraction, and external $defs inlining.

2) Input handling + gate evidence.
   - Validate `s0_gate_receipt_2B` and `sealed_inputs_2B` with Draft202012Validator, inlining layer1 $defs into the receipt schema (same approach as S1) to avoid unresolved refs.
   - Enforce that `alias_layout_policy_v1` is present in sealed_inputs, and that its sealed path matches the dictionary-resolved policy path (abort with 2B-S2-070 on mismatch).
   - Validate the policy JSON against `schemas.2B.yaml#/policy/alias_layout_policy_v1`, then enforce minima (layout_version/endianness/alignment/quantised_bits/encode_spec/decode_law/checksum/blob_digest/required_index_fields). Missing or unsupported values abort with 2B-S2-032.

3) Weights loading + PK order enforcement.
   - Load `s1_site_weights` via Polars with only required columns; enforce constant quantised_bits == policy b (2B-S2-058) and verify strict PK ascending order (merchant_id, legal_country_iso, site_order). If ordering breaks, abort with 2B-S2-083 instead of resorting (determinism > implicit reordering).

4) Mass reconstruction and deterministic adjustments.
   - Use binary64 m* = p_weight * G with G = 2^b; round ties-to-even via numpy.rint; residual adjustment by residual ranking + PK index, skipping invalid decrement cases and aborting with 2B-S2-052/053 when reconciliation fails.

5) Alias encode + Q0.32 packing.
   - Implement Walker/Vose with deterministic small/large queues (m_i == M treated as large) and treat-within-epsilon-of-one-as-one using policy.quantisation_epsilon.
   - Encode prob_q with Q0.32 floor/clamp rule and uint32 arrays; pack slice header `u32_n_sites,u32_prob_qbits,u32_reserved0,u32_reserved1` + prob_q + alias arrays in policy endianness.

6) Blob/index serialization + checksums.
   - Stream blob writes to run tmp, align slice offsets to alignment_bytes, pad with policy.pad_byte_hex, and exclude padding from per-slice checksum scope (policy scope = slice_payload_bytes). Track offset/length per merchant and compute blob sha256 as bytes are written.

7) Validation + run-report evidence.
   - Validate index JSON against schema with inlined layer1 $defs, then enforce bounds/non-overlap/alignment, merchants/sites coverage, and policy echo/created_utc coherence.
   - Perform deterministic decode spot-check on first N merchants (N=20), compute p_hat from encoded prob_q + alias, enforce |p_hat - p_weight| <= epsilon_q and sum p_hat ~ 1 (2B-S2-055).
   - Emit run-report (stdout + file) with required top-level fields, samples (index rows, decode rows, boundary checks, alignment), counters, and durations.

8) Publish semantics.
   - Write index + blob to staging under run tmp; publish with write-once guard (byte-identity required for re-emit) and sequential atomic renames. If any non-identical existing output is found, abort with 2B-S2-080. If publish fails, abort with 2B-S2-082.

Open risks noted before coding:
- JSON schema refs: must inline `schemas.layer1.yaml#/$defs/*` into index schema to avoid `Unresolvable` errors.
- Writer-order strictness: we are aborting if `s1_site_weights` ordering is not strictly ascending; if you prefer an internal deterministic sort, we should revisit before finalizing.

### Entry: 2026-01-15 12:15

Design element: 2B.S2 implementation resume (replace placeholder runner, wire CLI/Makefile).
Summary: The S2 runner stub currently contains placeholder text; we will replace
it with the full deterministic alias build, add the CLI entry point, and wire
the Makefile target. No algorithmic deviations from the prior S2 plan are
introduced here; this entry logs the exact work sequence before editing code.

Planned actions (before code edits, detailed):
1) Replace `seg_2B/s2_alias_tables/runner.py` placeholder content.
   - Implement the full S2 runner as per the 11:55 posture: policy validation,
     integer-grid reconstruction, Walker/Vose encode, Q0.32 packing, per-slice
     checksum, streaming blob digest, index build + schema validation, decode
     spot-check, and atomic publish with write-once guard.
   - Ensure logs remain story-like and include progress, throughput, and
     timing stats (elapsed/rate/eta) in long loops.

2) Add CLI entry point `engine/cli/s2_alias_tables_2b.py`.
   - Pattern after `s1_site_weights_2b.py` to keep config/args consistent
     (contracts layout/root, runs root, external roots, run-id override).

3) Update Makefile wiring for `segment2b-s2`.
   - Add `SEG2B_S2_RUN_ID`, `SEG2B_S2_ARGS`, `SEG2B_S2_CMD` variables.
   - Add `segment2b-s2` target to `.PHONY` and to the target list near
     `segment2b-s0`/`segment2b-s1` for consistency.

4) After code edits, run `make segment2b-s2` (and re-run S0/S1 if policy digest
   changes) to confirm green. Record any failures and fixes in this log.

### Entry: 2026-01-15 12:22

Design element: Begin S2 coding pass (runner/CLI/Makefile wiring, plus compatibility shim).
Summary: Proceed to replace the placeholder runner with the full deterministic
alias-table build, add the CLI entry point and Makefile target, and optionally
add a thin import shim so older tests importing `seg_2B.s2_alias` continue to
work without changing the state implementation naming.

Detailed pre-edit actions and decisions:
1) Implementation sequencing (before touching code).
   - First, log this in-process entry, then implement the runner, then add CLI
     and Makefile wiring, and only after that run S2.
   - Rationale: capture the exact intended sequence to keep the audit trail
     usable (the user requested brainstorming + decisions be logged before
     code changes).

2) Compatibility shim decision.
   - Decision: add a tiny `seg_2B/s2_alias` module that re-exports the new
     `S2AliasRunner/S2AliasInputs` from `s2_alias_tables`. This preserves older
     import paths used in `tests/engine/test_seg_2b_s2_alias.py` without
     altering the S2 implementation name or spec bindings.
   - Rationale: the shim is non-invasive, avoids test breakage, and does not
     change S2’s outputs or contract behaviour.

3) Logging and run-report intent.
   - Continue story-style logs per spec: explicit stages for RESOLVE, POLICY,
     RECONSTRUCT, ENCODE, SERIALIZE, DIGEST, DECODE_CHECK, and PUBLISH.
   - Ensure long loops (per merchant / per slice) include progress with
     elapsed/rate/eta so operators see real-time progress.

4) Failure-handling posture.
   - Preserve spec abort codes for each validator; the runner should emit the
     matching `V-##` status updates and include them in the run-report even on
     early failure.
   - Abort-class failures must avoid publishing any outputs; attempted run
     report emission should still occur with partial data when safe.

### Entry: 2026-01-15 13:36

Design element: Final S2 runner alignment to spec (run-report, queue performance, policy compatibility).
Summary: Before finishing Makefile wiring and running S2, tighten the runner to
match the S2 spec’s observability and performance requirements: add missing
run-report fields (id_map), fix boundary sample indexing, enforce policy
encode/decode compatibility, and remove O(K^2) queue operations in alias build.

Detailed decisions and changes to apply (before edits):
1) Run-report completeness (spec compliance).
   - Add `id_map` with dictionary-resolved paths for:
     `s1_site_weights`, `alias_layout_policy_v1`, `s2_alias_index`, `s2_alias_blob`.
   - Ensure `samples.boundary_checks` uses the correct offsets from the sorted
     ranges list (not the boundary-candidate index) so gaps are accurate.
   - Keep `targets` order fixed as `[s2_alias_index, s2_alias_blob]` (already
     correct), and keep validators sorted by id.

2) Alias queue performance (avoid O(K^2)).
   - Replace `small.pop(0)` / `large.pop(0)` list-queue operations with
     heap-based worklists (`heapq`) keyed by index. This keeps deterministic
     ascending-index behaviour while ensuring O(K log K) per merchant instead
     of quadratic pops.
   - Still treat `m_i == M` as “large” per the deterministic queue convention.

3) Policy compatibility checks (no silent mismatches).
   - Abort if `encode_spec.mass_rounding` or `encode_spec.delta_adjust` or
     `encode_spec.worklist_order` is not the supported values
     (`round_to_nearest_ties_to_even`, `residual_ranked_plus_minus_one`,
     `ascending_index`).
   - Abort if `record_layout.prob_q_encoding` or `alias_index_type` or
     `slice_header` differs from the supported layout (`Q0.32_floor_clamp...`,
     `u32`, `u32_n_sites,u32_prob_qbits,u32_reserved0,u32_reserved1`).
   - Abort if `decode_law` is not `walker_vose_q0_32` or if `prob_qbits > 32`.
   - Rationale: the implementation is intentionally narrow; any policy drift
     should fail closed rather than silently producing a different layout.

4) Observability during alias build.
   - Add a progress tracker that logs merchants processed (elapsed/rate/eta).
   - Emit a “S2: building alias tables” log with merchant/site counts.

5) Digest timing accuracy.
   - Record digest timing around the blob SHA-256 finalisation, not a zero-cost
     no-op, so `digest_ms` reflects actual work.

Next actions after these edits:
1) Update `seg_2B/s2_alias_tables/runner.py` to implement the changes above.
2) Wire `segment2b-s2` in the Makefile and run `make segment2b-s2` until green,
   recording every failure + fix here and in the logbook.

### Entry: 2026-01-15 13:42

Design element: Applied S2 runner + Makefile changes for spec compliance.
Summary: Implemented the planned S2 runner adjustments and Makefile wiring so
the alias build follows spec-required logging, policy compatibility, and
performance posture before running S2.

Actions executed (detailed):
1) Runner: policy compatibility enforcement.
   - Added `_validate_policy_compat` checks for endianness/alignment, positive
     epsilons, encode_spec fields, record_layout fields, decode_law, and
     checksum/digest settings; aborts on unsupported values with 2B-S2-032.

2) Runner: alias queue performance.
   - Replaced list `pop(0)` + `bisect.insort` with heap-based worklists to keep
     deterministic ascending-index behaviour while avoiding O(K^2) queue costs.

3) Runner: observability and report evidence.
   - Added a progress tracker for merchants with elapsed/rate/eta.
   - Added an explicit “S2: building alias tables” log line with merchant/row
     counts.
   - Fixed boundary sample indexing to reference the correct neighbor ranges.
   - Added `id_map` to the run-report with dictionary-resolved paths for all
     inputs/outputs required by §11.10.

4) Runner: digest timing.
   - Captured `digest_ms` around blob SHA-256 finalisation instead of a no-op
     timer, and wired this value into the run-report.

5) Makefile: S2 wiring.
   - Added `SEG2B_S2_RUN_ID`, S2 args/command, `segment2b-s2` target, and
     `.PHONY` entry so S2 can be run via make consistently with S0/S1.

Next steps:
1) Run `make segment2b-s2` for the active run_id and inspect the log/report.
2) Record any failures + fixes in this file and in the logbook.

### Entry: 2026-01-15 13:44

Design element: S2 abort on policy digest mismatch (2B-S2-022).
Summary: First S2 run after the runner updates failed at the policy digest
check: the sealed digest for `alias_layout_policy_v1` no longer matches the
current policy file bytes for the active run_id.

Observed failure (from run log):
- Validator V-24 failed with `2B-S2-022 policy_digest_mismatch` and showed
  `sealed=b622...f908` vs `computed=8295...8cfe`.

Diagnosis and resolution plan:
1) The sealed_inputs_2B entry was produced by 2B.S0 earlier in the run and
   still carries the old policy digest. Since policy bytes have changed since
   that seal, S2 correctly fails closed.
2) Re-run `make segment2b-s0` for the same run_id to refresh sealed_inputs_2B
   with the current policy digest. (S1 does not depend on this policy, but we
   will re-run S1 if needed to keep the run lineage consistent.)
3) Re-run `make segment2b-s2` and confirm the digest check passes.
4) Record the rerun outputs and any new errors in this log and the logbook.

### Entry: 2026-01-15 13:58

Design element: S2 Polars streaming panic on parquet (engine mismatch).
Summary: `make segment2b-s2` panicked inside Polars' old streaming engine:
`Parquet no longer supported for old streaming engine` during
`scan_parquet(...).collect(streaming=True)`.

Observed failure:
- Panic from `polars-pipe` convert.rs:111 while collecting the lazy frame in
  streaming mode, aborting S2 after the policy resolution step.

Resolution plan (before edit):
1) Remove `streaming=True` and use `pl.read_parquet(..., columns=[...])` to
   load only required columns without invoking the deprecated streaming engine.
2) Re-run `make segment2b-s2` to confirm S2 proceeds past the load step.

Note: this keeps memory bounded by column projection and avoids runtime panics
from Polars' deprecated streaming engine on parquet sources.

### Entry: 2026-01-15 14:07

Design element: S2 green run after corrected S1 weights.
Summary: After re-emitting S1 with per-merchant normalisation, `make segment2b-s2`
completed successfully with all validators PASS and decode coherence restored.

Run outcome notes:
1) S2 processed `merchants_total=1280`, `sites_total=34363` and published both
   `s2_alias_index` and `s2_alias_blob` under the manifest_fingerprint path.
2) Decode check passed for all sampled rows; `merchants_mass_exact_after_decode=1280`
   and `max_abs_delta_decode=5.89e-08` (<= policy quantisation epsilon).
3) Run-report emitted to stdout and persisted under
   `reports/layer1/2B/state=S2/seed=42/manifest_fingerprint=241f.../`.

## Cross-state logging retrofit (S0-S2)



## S3 - Day Effects (S3.*)

### Entry: 2026-01-15 18:06

Design element: 2B.S3 day-effect (gamma) generation with Philox RNG.
Summary: S3 must generate per-merchant, per-UTC-day, per-tz-group gamma factors
under a policy-governed RNG envelope, with strict partitioning, write-once
publishing, and byte-identical replays for identical inputs.

Files reviewed (expanded + contracts):
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s3.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/dataset_dictionary.layer1.2B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/artefact_registry_2B.yaml`

Detailed plan (before implementation, stepwise):
1) Resolve run identity and authorities.
   - Load run_receipt.json for `seed`, `parameter_hash`, `manifest_fingerprint`.
   - Resolve contracts from model_spec (dev mode) and record versions in run-report.
   - Enforce Dictionary-only resolution; no literal paths; no network I/O.

2) Enforce S0 gate evidence and S0-evidence rule.
   - Resolve `s0_gate_receipt_2B` and `sealed_inputs_2B` for the same
     `manifest_fingerprint` and validate schema anchors.
   - Use S0 receipt `verified_at_utc` as canonical `created_utc` for all rows.
   - Confirm `day_effect_policy_v1` appears in S0 sealed inputs and validate
     its digest/path against the sealed inventory (S0-evidence rule).

3) Resolve inputs by Dictionary ID at exact partitions.
   - `s1_site_weights` at `[seed, manifest_fingerprint]`.
   - `site_timezones` at `[seed, manifest_fingerprint]`.
   - `day_effect_policy_v1` by **token-less** S0-sealed path + digest.
   - Abort on partition mismatch or missing input (2B-S3-020/070).

4) Validate policy minima (Abort on missing or invalid).
   - Parse `day_effect_policy_v1` and enforce: rng_engine=philox2x64-10,
     rng_stream_id matches pattern, draws_per_row=1, sigma_gamma>0,
     day_range inclusive and well-formed, record_fields present,
     rng_derivation keys present, created_utc_policy_echo boolean.
   - Decide how to treat record_fields vs fixed schema (see confirmations).

5) Form tz-groups deterministically.
   - Join `s1_site_weights` to `site_timezones` on
     `(merchant_id, legal_country_iso, site_order)` and require 1:1 mapping.
   - Derive `tz_group_id` as the tzid string from site_timezones.
   - For each merchant, compute the distinct tz_group_id set
     (used for coverage grid).

6) Construct the day grid from policy day_range.
   - Build inclusive UTC day list `[start_day..end_day]` (string dates).
   - Validate against 2B-S3-033/090 on malformed ranges.

7) RNG envelope and draws (Philox).
   - Use counter-based Philox per policy `rng_derivation`:
     key basis: manifest_fingerprint_bytes + seed_u64 + rng_stream_id.
   - Counter basis: manifest_fingerprint_bytes + seed_u64 + rng_stream_id,
     then increment per row in writer order (strictly monotone; no reuse).
   - Draw 1 normal per row (log_gamma) with sigma=policy sigma_gamma and
     mean = -0.5*sigma^2 so E[gamma]=1.
   - Record rng_stream_id, counter_hi/lo for each row.
   - Enforce RNG echo checks: engine/stream/draw counts per validators.

8) Emit `s3_day_effects` with strict ordering and write-once semantics.
   - Output columns per `schemas.2B.yaml#/plan/s3_day_effects`.
   - Writer order must be PK order: (merchant_id, utc_day, tz_group_id).
   - Enforce coverage: every merchant × tz_group × day → exactly one row.
   - Validate schema, PK uniqueness, and writer order.
   - Atomic publish to Dictionary path and enforce byte-identical re-emits.

9) Run-report and logging (story aligned).
   - Emit story header: objective + gated inputs + outputs.
   - Progress logs for row generation include elapsed, count/total, rate, ETA.
   - Emit WARN for tz_group_id not in site_timezones set (2B-S3-191) with
     a small sample of tzids.
   - Run-report captures counts, day_range, rng_draws_total, policy digests,
     and validation results; record created_utc provenance from S0 receipt.

Performance notes:
- Avoid full cartesian materialization in memory; stream rows in PK order.
- Use deterministic iteration order: merchants sorted; tz_group_id sorted;
  days sorted. This guarantees PK order and stable RNG counter sequence.

Open confirmations (need user decision before coding):
1) `record_fields` in `day_effect_policy_v1` vs fixed output schema:
   - Plan: treat `record_fields` as a **minimum required set** and abort if it
     omits any required schema fields; always emit the full schema-defined
     columns for stability. Confirm if you want output to be **subsettable**
     based on policy (would require schema change).
2) `created_utc_policy_echo`:
   - Plan: when true, echo policy_id/version_tag/sha256 in the **run-report**
     (not in the data rows) to keep rows minimal and schema-stable. Confirm.
3) tzid validity warning (2B-S3-191):
   - Plan: warn if any tz_group_id in output not present in site_timezones set,
     include a small sample in run-report and log; do not alter outputs.

### Entry: 2026-01-15 19:02

Design element: Lock S3 confirmation decisions + policy alignment before coding.
Summary: User approved the S3 confirmation posture and asked to proceed with
implementation. Before coding, we must reconcile `day_effect_policy_v1.json`
with the schema so S3 validation can pass and remain deterministic.

Decision details (approved, before implementation):
1) `record_fields` handling:
   - Treat `record_fields` as the **minimum required set**. If any required
     schema field is missing from the list, abort with the policy schema
     failure (2B-S3-032). Always emit the full schema columns in the output
     table so downstream readers see a stable shape across runs.
   - Rationale: policy should not shrink the schema; it only declares the
     minimum provenance fields that must be present.

2) `created_utc_policy_echo` handling:
   - When true, echo policy_id/version_tag/sha256 in the **run-report only**.
     Do not inject policy fields into the data rows to keep the table schema
     stable and compact.
   - Rationale: output rows must remain schema-stable; run-report is the right
     place for policy provenance echoes.

3) tzid validity warning (2B-S3-191):
   - Emit WARN with a small sample of offending tz_group_id values in the log
     and run-report, but do not alter outputs. Keep the failure closed in S7
     if inputs_digest/parity checks require it.
   - Rationale: visibility without mutating outputs preserves determinism and
     allows later governance checks to decide what to do.

Policy alignment decision (required before coding):
4) `day_effect_policy_v1.json` is currently **out of schema**:
   - Missing required fields: `policy_id`, `rng_derivation`, `sha256_hex`.
   - `rng_engine` is `philox_4x32_10`, but schema requires `philox2x64-10`.
   - Contains disallowed fields (`rng_key_hi/lo`, `base_counter_*`, `calendar`)
     because additionalProperties=false.
   - Plan: update the JSON to match schema, remove disallowed fields, and add
     `rng_derivation` with the required basis rules. Use a compliant
     `rng_stream_id` (e.g., `2B.day_effects.gamma`) that matches the pattern.

5) `sha256_hex` field in policy file:
   - The schema requires it, but it is ambiguous whether it should equal the
     file digest. To avoid circularity, we will compute `sha256_hex` as the
     SHA-256 of a canonical JSON rendering **with the sha256_hex field
     omitted**, then insert that value into the file. S0 will continue sealing
     the policy by raw file bytes (as required by spec), and S3 will treat
     `sha256_hex` as a provenance echo only (no equality check against the
     sealed digest).
   - This is a pragmatic interpretation for a spec gap; it must be logged so
     the policy digest rule can be tightened later if needed.

Next steps before coding:
1) Update `config/layer1/2B/policy/day_effect_policy_v1.json` to the schema
   shape (policy_id, rng_engine, rng_derivation, sha256_hex; remove old keys).
2) Re-seal S0 for the active run_id (policy digest changes) and re-run S1/S2
   only if the write-once guard requires it.
3) Implement S3 runner + CLI + Makefile wiring per the approved decisions.

### Entry: 2026-01-15 19:24

Design element: Bring `day_effect_policy_v1.json` into authoring-guide compliance.
Summary: The authoring guide for S3 mandates a minimum 365-day range and requires
`created_utc` in `record_fields`. The current policy used a 14-day range and
omitted `created_utc`, which would force S3 to fail the realism/minima checks.
This entry documents the required policy updates before coding S3.

Reasoning (in-flight, detailed):
1) **Day-range realism floor**: The authoring guide (§7.1) requires
   `D >= 365` inclusive days (and <= 1826). A short range undermines the "real
   deal" posture and is explicitly disallowed. We must expand the day range to
   at least one full year before S3 can pass.
2) **Record-fields minima**: The authoring guide (§2, §8) requires
   `created_utc` to appear in `record_fields`. S3 always emits full schema
   columns, but it must still enforce the policy's minimum list. Missing
   `created_utc` would be a policy minima failure.
3) **Version bump**: Because the policy bytes change materially (range + fields),
   bump `version_tag` and `policy_version` to the next patch (`1.0.1`) to keep
   governance traceable.
4) **Digest rule**: The `sha256_hex` field must be recomputed over canonical JSON
   **excluding** the `sha256_hex` field (authoring guide §4). This is consistent
   with the earlier "no circular hash" decision and keeps S0 sealing by raw
   bytes unchanged.

Decisions recorded before applying changes:
- Set `day_range` to **2024-01-01 .. 2024-12-31** (366 days; >=365 and <=1826).
- Add `"created_utc"` to `record_fields`.
- Bump `version_tag` and `policy_version` to `1.0.1`.
- Recompute `sha256_hex` from canonical JSON excluding `sha256_hex`.

Implementation actions (policy file update):
1) Updated `config/layer1/2B/policy/day_effect_policy_v1.json` with the new
   day range and record_fields, and bumped the version tags to `1.0.1`.
2) Recomputed `sha256_hex` as
   `a84875f0237efaefaf2cbb130323659626f5d4a85e74e5a3c18a204925783e4e`
   (canonical JSON excluding the hash field).

Follow-ups required (after policy change):
1) Re-run `segment2b-s0` to reseal the updated policy digest in `sealed_inputs_2B`.
2) Re-run `segment2b-s1` and `segment2b-s2` if write-once guards detect
   the policy change.
3) Proceed with S3 runner implementation using the updated policy values.

### Entry: 2026-01-15 19:35

Design element: Begin 2B.S3 runner/CLI/Makefile implementation (day-effect factors).
Summary: Start implementing S3 to generate deterministic per-merchant/utc-day/tz-group
gamma factors with Philox counters, enforce S0 gate evidence + sealed policy, and emit
the strict run-report + write-once output.

Implementation plan (in-progress, explicit steps before code edits):
1) **Wire contracts + run identity**.
   - Load run_receipt.json (seed, parameter_hash, manifest_fingerprint, run_id).
   - Load dictionary, registry, schema packs: 2B, 2A, 1B, layer1 (needed for refs).
   - Record dictionary_version + registry_version for run-report.
   - Story header log: objective + required inputs (s0_gate_receipt_2B,
     sealed_inputs_2B, s1_site_weights, site_timezones, day_effect_policy_v1)
     and the output (`s3_day_effects`).

2) **S0 gate evidence + sealed-input enforcement**.
   - Resolve `s0_gate_receipt_2B` and validate its schema (inline layer1 $defs).
   - Resolve `sealed_inputs_2B` and validate with Draft202012Validator
     (array schema).
   - Assert `day_effect_policy_v1` and `site_timezones` are present in
     sealed_inputs_2B, with exact path + partition KV matches.
   - Use S0 receipt `verified_at_utc` as `created_utc` for all S3 rows.

3) **Resolve inputs (Dictionary-only)**.
   - Resolve `s1_site_weights@seed,manifest_fingerprint` (read-only).
   - Resolve `site_timezones@seed,manifest_fingerprint` (read-only).
   - Resolve policy path using the **S0-sealed path** (token-less).
   - Record dictionary paths in `id_map` for run-report.

4) **Policy minima + schema alignment**.
   - Validate `day_effect_policy_v1` schema anchor.
   - Enforce minima: rng_engine=philox2x64-10, draws_per_row=1,
     sigma_gamma>0, day_range inclusive, rng_derivation fields present,
     record_fields includes all required output fields.
   - Treat `record_fields` as a minimum list; output table remains full schema.
   - If `created_utc_policy_echo` is true, echo policy id/version/digest
     in run-report only (not in data rows).

5) **Join + tz-group formation (deterministic)**.
   - Load `site_timezones` and `s1_site_weights` (project only join keys + tzid).
   - Enforce 1:1 join on (merchant_id, legal_country_iso, site_order):
     - Missing tzid => abort 2B-S3-040.
     - Multiple tzids for same key => abort 2B-S3-041.
   - For each merchant_id, build a sorted list of distinct tz_group_id (tzid).
   - Track `merchants_total`, `tz_groups_total`, `join_misses`, and
     `pk_duplicates` counters.

6) **Day grid + row enumeration**.
   - Build inclusive day list from policy day_range (ascending ISO date).
   - Total rows expected = sum over merchants of (len(tz_groups) * days_total).
   - Emit progress logs with elapsed/rate/ETA as rows are generated.

7) **RNG derivation + log-normal draw**.
   - Implement policy-derivation: compute SHA256 digest with UER strings and
     {manifest_fingerprint_bytes, seed_u64, rng_stream_id} for key + counter
     (LE64 for key tail, BE64 for counter hi/lo per spec).
   - Counter = base + row_rank (row_rank in PK order).
   - Use philox2x64_10 (from 1A.s1_hurdle.rng), convert to uniform via u01,
     then inverse-normal (Acklam) to obtain z ~ N(0,1).
   - log_gamma = mu + sigma*z, mu = -0.5*sigma^2, gamma = exp(log_gamma).
   - Enforce gamma>0, log_gamma finite; track max_abs_log_gamma.
   - Record rng_stream_id, rng_counter_hi/lo per row and verify strict monotonicity.

8) **Output + validation + publish**.
   - Write rows in PK order to parquet batches (bounded memory).
   - Validate row schema using jsonschema adapter for `s3_day_effects`.
   - Enforce coverage: rows_written == rows_expected.
   - Atomic publish with write-once semantics; abort on non-identical output.

9) **Run-report + samples**.
   - Emit run-report with required sections: policy, inputs_summary,
     rng_accounting, publish, validators, summary, environment, samples,
     counters, durations_ms, id_map.
   - Deterministic sample selection rules (first N by PK order; worst diffs first).

10) **Logging story**.
   - Narrative logs for each stage (GATE → POLICY → GROUPS → RNG DRAWS → PUBLISH).
   - Keep PASS validations at DEBUG, WARN/FAIL visible.

Implementation intention:
1) Add `seg_2B/s3_day_effects/runner.py` using S1/S2 patterns + shared RNG helpers.
2) Add CLI `engine/cli/s3_day_effects_2b.py`.
3) Add Makefile wiring (`SEG2B_S3_RUN_ID`, args/cmd, target, `.PHONY`).


### Entry: 2026-01-15 19:52

Design element: 2B.S3 day-effect generation for per-merchant x UTC-day x tz-group gamma multipliers.
Summary: S3 must deterministically build tz-groups from S1 + 2A site_timezones, draw one
Philox-based log-normal gamma per {merchant, day, tz_group}, and publish a write-once
partition `s3_day_effects` with full RNG provenance and coverage validation.

Plan (before implementation, detailed; captured during design):
1) Resolve authorities and run identity.
   - Contracts source: `model_spec` layout (dev mode); keep CLI flags for
     `--contracts-layout` + `--contracts-root` so production can switch to root
     without code changes.
   - Load run_receipt.json (run_id, seed, parameter_hash, manifest_fingerprint).
   - Load dictionary, registry, and schema packs for 2B + 2A + 1A layer1 defs.
   - Record dictionary_version + registry_version for the run-report.

2) Gate + sealed input discipline.
   - Resolve `s0_gate_receipt_2B` and validate against
     `schemas.2B.yaml#/validation/s0_gate_receipt_v1` (inline layer1 $defs).
   - Extract `created_utc = receipt.verified_at_utc`; this is authoritative
     and must be echoed into every output row (2B-S3-086).
   - Resolve and validate `sealed_inputs_2B` (schema) and assert the S3-required
     assets are sealed: `site_timezones`, `day_effect_policy_v1`,
     and `validation_bundle_1B`/`validation_passed_flag_1B` only for gate
     continuity (note: `s1_site_weights` is within-segment, not sealed).
   - Enforce partition path equality for sealed assets (2B-S3-070).

3) Resolve required inputs by dictionary only (no literal paths).
   - `s1_site_weights` at `seed={seed}/manifest_fingerprint={manifest_fp}`.
   - `site_timezones` at `seed={seed}/manifest_fingerprint={manifest_fp}`.
   - `day_effect_policy_v1` uses the exact sealed path + digest.
   - Reject any missing or mis-resolved dataset (2B-S3-020/070).

4) Policy validation (minima + RNG posture).
   - Parse `day_effect_policy_v1` JSON and validate with
     `schemas.2B.yaml#/policy/day_effect_policy_v1`.
   - Abort if minima missing: `rng_engine`, `rng_stream_id`, `draws_per_row`,
     `sigma_gamma`, `day_range`, `rng_derivation`, `record_fields`.
   - Enforce `draws_per_row == 1` and `rng_engine == philox2x64-10`.
   - Validate `day_range` inclusive semantics (start_day <= end_day).
   - Track `sigma_gamma` and `rng_stream_id` for output + run-report.

5) Join + tz-group construction (1:1 join requirement).
   - Read `s1_site_weights` columns: merchant_id, legal_country_iso, site_order.
   - Read `site_timezones` columns: merchant_id, legal_country_iso, site_order, tzid.
   - Detect duplicate tzid per site key (2B-S3-041) and missing tzid (2B-S3-040).
   - Build per-merchant tz-group set using tzid as `tz_group_id`.
   - Sort deterministically: merchants ascending; per-merchant tz_groups sorted
     lexicographically to guarantee writer order.

6) Coverage grid and row order invariants.
   - Construct UTC day list from policy day_range (inclusive).
   - Coverage is exactly: merchants × tz_groups_per_merchant × days.
   - Writer order must be PK order: (merchant_id, utc_day, tz_group_id).
   - Validate no PK duplicates (2B-S3-042) and order monotonicity (2B-S3-083).

7) RNG derivation (Philox2x64-10; counter monotonicity).
   - Use UER encoding and SHA-256 for key/counter derivation per policy:
     - Master: `uer(domain_master) + manifest_fp_bytes + seed_u64`.
     - Stream: `uer(domain_stream) + rng_stream_id`.
     - digest = sha256(master + stream); key = LE64 digest[24:32],
       counter_hi = BE64 digest[16:24], counter_lo = BE64 digest[24:32].
   - Counter increments by 1 per output row in writer order.
   - Record counter_hi/lo for each row and enforce strict monotonicity and
     no wrap (2B-S3-063/064). draw_count must equal rows_expected (2B-S3-062).

8) Distribution and numeric invariants.
   - For each row, draw u in (0,1) from Philox output `x0` and convert to
     z via deterministic normal inverse CDF (Acklam approximation).
   - log_gamma = -0.5 * sigma^2 + sigma * z, gamma = exp(log_gamma).
   - Abort if log_gamma non-finite or gamma <= 0 (2B-S3-057/058).
   - Echo sigma_gamma and rng_stream_id per row; mismatch abort (2B-S3-059/061).

9) Output write, schema validation, and atomic publish.
   - Stage outputs in run tmp dir: `runs/<run_id>/tmp/s3_day_effects_<uuid>/`.
   - Write parquet parts in batches (100k rows) using polars schema that
     matches `schemas.2B.yaml#/plan/s3_day_effects`.
   - Validate via `validate_dataframe` against table schema (inline layer1 defs).
   - Enforce write-once publish: if target exists, compare hashes and allow
     only identical output; otherwise abort (2B-S3-080/081).
   - Publish via atomic rename into dictionary path and remove tmp folder.

10) Run-report + logging story.
   - Emit story header: objective, gated inputs, outputs.
   - Log each phase with narrative, not just counts:
     GATE -> POLICY -> JOIN -> GROUPS -> GENERATE -> VALIDATE -> PUBLISH.
   - Progress logs must include elapsed, processed/total, rate, ETA.
   - Run-report includes: policy details + digest, inputs digest, RNG accounting,
     coverage counts, output stats, validators, samples (rows + tz_groups),
     and environment metadata. Emit JSON to stdout + persist file.

Open confirmations resolved before coding:
1) Failure reporting for ambiguity/override already handled in S1/S2; S3 adopts
   strict abort posture per spec codes above; no relaxations.
2) No new S3 policy source changes; use S0-sealed policy path + digest only.

### Entry: 2026-01-15 20:12

Design element: S3 implementation kickoff (runner/CLI/Makefile) after planning.
Summary: Begin implementing the planned S3 runner, CLI, and makefile wiring.
An earlier attempt to write the runner file failed due to a Windows path-length
issue; we will re-create the file using apply_patch and confirm the file exists
before proceeding with the rest of the wiring.

Decision details (before coding, live):
1) File creation strategy.
   - Use apply_patch Add File for `seg_2B/s3_day_effects/runner.py` to avoid
     PowerShell write errors; verify with `Get-ChildItem` afterward.
   - If apply_patch fails, fall back to a Python writer that targets the same
     path and validates file existence, then proceed with standard edits.

2) Run-report strictness for S3.
   - Follow the spec-required top-level fields and include `samples`, `id_map`,
     and `durations_ms` at top-level (as in other 2B run-reports), while placing
     required counters inside existing objects (`inputs_summary` + `rng_accounting`)
     to keep the report minimal and deterministic.
   - Rationale: satisfies the explicit required fields + sample/counter rules
     without introducing uncontrolled keys.

3) Publish immutability handling.
   - If target partition exists and hashes match, skip publish and mark
     write_once_verified=true; if hashes differ, fail both V-17 and V-18 and
     abort with code 2B-S3-081 (non-idempotent re-emit), recording 2B-S3-080
     on V-17 for traceability.

Next implementation actions:
1) Implement runner with all validators V-01..V-23, strict policy minima,
   join/coverage checks, RNG derivation, and story logs.
2) Add CLI `s3_day_effects_2b.py` and makefile wiring for `segment2b-s3`.
3) Run `make segment2b-s3` and fix any failures, logging each decision/action.

### Entry: 2026-01-15 20:35

Design element: Resume S3 runner/CLI/Makefile implementation and align policy
digest handling with the provenance rule.
Summary: Continue building `s3_day_effects` after confirming that
`day_effect_policy_v1` is schema-aligned (rng_engine, day_range, record_fields)
and that `sha256_hex` is treated as a provenance echo (not the sealed file
digest). This entry captures the exact code steps being taken now.

Implementation steps (before code edits, explicit):
1) Complete the S3 runner in `seg_2B/s3_day_effects/runner.py`.
   - Add RNG derivation helpers (UER encoding + SHA-256) and Philox2x64-10
     kernel, including u01 and deterministic normal ICDF.
   - Implement strict policy minima checks (V-04) and enforce `record_fields`
     as a minimum set while always emitting the full schema columns.
   - Enforce sealed-input checks for `day_effect_policy_v1` + `site_timezones`
     (V-01/V-02/V-03/V-19), using S0 receipt `verified_at_utc` for `created_utc`.
   - Join `s1_site_weights` to `site_timezones` on the 3-key PK; abort on
     missing tzid or duplicate tzid (V-05).
   - Build tz-groups per merchant (sorted) and UTC day grid (inclusive) and
     generate rows in PK order with counters in lockstep (V-06/V-07/V-08/V-12/V-13).
   - Write parquet in bounded batches, validate each batch via JSON-schema
     adapter (V-16), then atomic publish with write-once guard (V-17/V-18).

2) Add the CLI entry point `engine/cli/s3_day_effects_2b.py`.
   - Mirror S1/S2 CLI structure: contracts layout/root flags, external roots,
     run-id selection (latest receipt by default).

3) Wire Makefile target `segment2b-s3`.
   - Add `SEG2B_S3_RUN_ID`, `SEG2B_S3_ARGS`, and `SEG2B_S3_CMD`.
   - Add a `segment2b-s3` target and include it in `.PHONY`.

4) Run and iterate until green.
   - Execute `make segment2b-s3 RUN_ID=<active>` and resolve any runtime errors.
   - Each fix: append a new implementation-map entry + logbook entry with
     reasoning, and re-run until the output is write-once and the run-report
     passes all V-01..V-21 checks.

### Entry: 2026-01-15 20:53

Design element: Record-fields minima interpretation adjustment for S3.
Summary: Align `record_fields` enforcement with the S3 spec (minimum audit
fields only) rather than requiring the full output schema list. This avoids
over-restricting policy configurations while still meeting the binding minima.

Decision details (in-flight):
1) Required minima per spec are:
   - `gamma`, `log_gamma`, `sigma_gamma`, `rng_stream_id`, `rng_counter_lo`,
     `rng_counter_hi`, `created_utc`.
2) The output still emits the full schema-defined columns, but `record_fields`
   only needs to include the minima list above. Any missing minima remains an
   abort under `2B-S3-032` (V-04).
3) Rationale: the policy's `record_fields` is a minimum audit declaration,
   not a schema-level projection list. Requiring merchant_id/utc_day/tz_group_id
   would be stricter than the contract text.

### Entry: 2026-01-15 20:58

Design element: S3 policy digest mismatch (2B-S3-070) during first run attempt.
Summary: Running `segment2b-s3` failed at V-03 because the sealed policy digest
recorded in `sealed_inputs_2B` does not match the current
`day_effect_policy_v1.json` content. This is a process/lineage issue (S0 seal
stale after policy edit), not a runner bug.

Decision details (live, pre-fix):
1) Keep the V-03 digest check strict.
   - The spec expects S3 to trust the S0 seal. Allowing mismatches would break
     lineage and determinism (policy provenance must be frozen at S0).
   - Therefore the correct fix is to re-run 2B.S0 so `sealed_inputs_2B`
     captures the updated policy sha256, then re-run S3.

2) Fix sequence to clear the failure.
   - Run `make segment2b-s0 RUN_ID=<same run_id>` to re-seal inputs using the
     updated `day_effect_policy_v1.json`.
   - Immediately re-run `make segment2b-s3 RUN_ID=<same run_id>` to confirm
     V-03 passes and S3 proceeds to generation/publish.

3) Audit note.
   - Log the policy digest mismatch and reseal decision in the logbook and
     reference this entry for traceability.

### Entry: 2026-01-15 21:07

Design element: De-duplicate S3 RNG helpers and keep implementation log append-only.
Summary: The S3 runner currently embeds its own Philox2x64-10 implementation and
UER/low64 helpers, which duplicates existing helpers in
`engine.layers.l1.seg_1A.s1_hurdle.rng`. We will reuse those shared helpers while
keeping the S3-specific `u = (r + 0.5) * 2^-64` mapping (spec-required). Also,
the implementation log got out-of-order due to an earlier insert mid-file; we
will append all future entries at the end and add a chronology note rather than
rewriting past entries.

Plan (before coding, detailed):
1) RNG helper reuse (no behavior change).
   - Replace local `philox2x64_10`, `_uer_string`, `_ser_u64`, `_low64` with imports
     from `engine.layers.l1.seg_1A.s1_hurdle.rng` (`philox2x64_10`, `uer_string`,
     `ser_u64`, `low64`).
   - Keep the S3-specific `_u01` because the spec mandates `u = (r + 0.5) * 2^-64`
     (the S1 helper uses a different open-interval mapping).
   - Leave constants like `UINT64_MASK` local; they are harmless and avoid dragging
     in extra dependencies. No RNG output should change.

2) Chronology correction (without rewriting history).
   - Do not move existing entries (per “never rewrite prior entries” rule).
   - Add a short note at the end (this entry) that earlier entries were inserted
     out-of-order; all new entries will be appended at the bottom.
   - If you want the file physically re-ordered, get explicit approval first.

3) Re-run plan (after helper swap).
   - You already deleted `runs/<run_id>/data/layer1/2B/`; rerun `segment2b-s0`
     to reseal policy digests, then run `segment2b-s3` on the same run_id.
   - Record each run attempt in the logbook and append any fixes/decisions here.

### Entry: 2026-01-15 21:10

Design element: Applied RNG helper de-dup in S3 runner.
Summary: Swapped local Philox/UER/low64 helpers for the shared implementations
from `seg_1A/s1_hurdle/rng.py` while preserving the S3-specific `(r + 0.5) * 2^-64`
uniform mapping and all RNG derivation logic.

Changes made (actual):
1) Imported `philox2x64_10`, `uer_string`, `ser_u64`, `low64` from
   `engine.layers.l1.seg_1A.s1_hurdle.rng` and removed duplicate local
   implementations in S3.
2) Kept `_u01` in S3 because the spec mandates `(r + 0.5) * 2^-64` (different
   from the S1 helper’s open-interval mapping).
3) Removed unused constants/imports (`UINT64_MAX`, Philox constants, `struct`)
   to avoid confusion and keep the file minimal.

### Entry: 2026-01-15 21:12

Design element: S3 policy schema failure due to rng_stream_id regex escaping.
Summary: S3 failed with `2B-S3-031` because the policy schema’s
`rng_stream_id` pattern is over-escaped in `schemas.2B.yaml`, requiring a
literal backslash before the dot. The authoring guide expects the pattern
`^2B\.[A-Za-z0-9_.-]+$`, which should accept `2B.day_effects.gamma`.

Plan (before code edits):
1) Fix the schema regex to align with the authoring guide.
   - Update `schemas.2B.yaml` `day_effect_policy_v1.properties.rng_stream_id.pattern`
     to `^2B\.[A-Za-z0-9_.-]+$` (single backslash in the YAML single-quoted string).
   - This corrects the schema without changing policy content or data lineage.

2) Re-run S3 only.
   - No reseal needed because the policy bytes are unchanged; only schema
     validation semantics were corrected.
   - Run `make segment2b-s3 RUN_ID=2b22ab5c8c7265882ca6e50375802b26` and
     continue fixing any further issues until green.

### Entry: 2026-01-15 21:13

Design element: Missing run-local `s1_site_weights` after 2B data cleanup.
Summary: S3 failed with `FileNotFoundError` when reading `s1_site_weights`
because the run-local `data/layer1/2B/` directory was deleted to reseal S0,
which removed S1/S2 outputs. This is a run orchestration issue, but S3 should
fail with a clear `2B-S3-020` rather than a raw polars error.

Plan (before fix/run):
1) Add explicit existence checks for `s1_site_weights` and `site_timezones`
   paths after resolution; if missing, abort with `2B-S3-020` (V-02) and
   include dataset_id + path in context.
2) Re-run `segment2b-s1` and `segment2b-s2` for the same run_id to recreate
   the missing outputs, then re-run `segment2b-s3`.

### Entry: 2026-01-15 21:14

Design element: Implemented explicit input existence checks in S3.
Summary: Added pre-read existence checks for `site_timezones` and
`s1_site_weights` to map missing paths to `2B-S3-020` (V-02) instead of a raw
polars `FileNotFoundError`.

Changes made (actual):
1) Inserted `Path.exists()` checks after `_resolve_input` for both inputs.
2) Emitted `input_missing` aborts with `{dataset_id, path}` context.

### Entry: 2026-01-15 21:16

Design element: Schema fix + rerun chain to get S3 green.
Summary: Corrected the `rng_stream_id` pattern in `schemas.2B.yaml`, re-ran the
2B chain to restore missing outputs, and S3 completed green for
run_id `2b22ab5c8c7265882ca6e50375802b26`.

Actions executed (auditable):
1) Schema fix (policy validation):
   - Updated `schemas.2B.yaml` `rng_stream_id` pattern to a single-backslash
     regex `^2B\.[A-Za-z0-9_.-]+$` so `2B.day_effects.gamma` validates.

2) Rerun chain after run-local cleanup:
   - Re-ran `segment2b-s0` to reseal policy digest in the run folder.
   - Re-ran `segment2b-s1` and `segment2b-s2` because their outputs were removed
     when `data/layer1/2B/` was deleted.
   - Re-ran `segment2b-s3` with the same run_id.

3) Outcome:
   - S3 emitted `s3_day_effects` successfully with
     `rows_written=1,129,842`, `tz_groups_total=3,087`, `days_total=366`,
     `write_once_verified=false`, `atomic_publish=true`.
   - Run-report written under
     `runs/local_full_run-5/2b22ab5c8c7265882ca6e50375802b26/reports/layer1/2B/state=S3/seed=42/manifest_fingerprint=e8a05027991ba560d5d334258378e2a607cf0c87b1368dd05fb7ef1a04c0afed/s3_run_report.json`.




## S4 - Zone-group renormalisation (S4.*)

### Entry: 2026-01-15 22:01

Design element: 2B.S4 zone-group renormalisation (s4_group_weights).
Summary: S4 combines deterministic S1 base shares (by tzid) with S3 day effects,
then renormalises per-merchant/per-day to a RNG-free group mix. The output must
be PK-ordered, write-once, and fully validated via the S4 validator set.

Files reviewed (expanded + contracts):
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s4.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/dataset_dictionary.layer1.2B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/artefact_registry_2B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2A/dataset_dictionary.layer1.2A.yaml` (site_timezones ordering)

Pre-implementation plan (detailed, stepwise):
1) Resolve run identity and authorities (no code changes yet).
   - Load run_receipt.json to capture `{seed, manifest_fingerprint, run_id}`.
   - Resolve dictionary, registry, and schema packs from model_spec (dev mode).
   - Record dictionary_version + registry_version for run-report.
   - Enforce dictionary-only resolution (no literal paths, no network I/O).

2) Enforce S0 gate evidence and S0-sealed inputs.
   - Resolve `s0_gate_receipt_2B` for the same manifest_fingerprint and validate
     against `schemas.2B.yaml#/validation/s0_gate_receipt_v1` (row schema).
   - Pull `created_utc` from `verified_at_utc` in the receipt (canonical).
   - Verify `site_timezones` appears in `sealed_inputs_2B` (cross-layer rule).
   - Note: `s1_site_weights` + `s3_day_effects` are within-segment and not sealed
     by S0, but MUST be resolved by exact `{seed, manifest_fingerprint}`.

3) Resolve and validate input partitions (exact selection).
   - Resolve `s1_site_weights`, `site_timezones`, `s3_day_effects` via dictionary.
   - Enforce exact partition tokens; abort on mismatch (2B-S4-070).
   - Verify input paths exist before reading (map missing to 2B-S4-020).
   - Build `id_map` entries for run-report with the resolved paths.

4) Build deterministic day grid from S3 (single authority).
   - Extract distinct `utc_day` values from `s3_day_effects`.
   - Sort ascending (YYYY-MM-DD) for deterministic day order.
   - Use this day grid as the only day set; do not infer or synthesize days.

5) Deterministic join for base shares (1:1 join on site keys).
   - Stream/merge-join `s1_site_weights` and `site_timezones` on
     `(merchant_id, legal_country_iso, site_order)` (both ordered by PK).
   - Abort on missing partner or multiple tzid per key (2B-S4-040/041).
   - For each merchant, aggregate `base_share` per tz_group_id (tzid) using
     stable, serial summation in PK order.
   - Validate per-merchant `sum(base_share)` within epsilon (2B-S4-052).
   - Persist per-merchant tz_group_id list sorted lexicographically for use
     in later normalization and row-ordering checks.

6) Combine base shares with S3 gamma and renormalise (RNG-free).
   - Stream `s3_day_effects` in PK order (merchant_id, utc_day, tz_group_id).
   - For each merchant/day, collect all tz_group rows for that day, compute
     `mass_raw = base_share * gamma` and `denom_raw = sum(mass_raw)`.
   - Require `denom_raw > 0` and a complete gamma row per group/day.
   - Compute `p_group = mass_raw / denom_raw`.
   - Apply tiny-negative guard: if `p_group` is in `(-epsilon, 0)` clamp to 0
     and renormalise once; abort if `p_group < -epsilon` or if the post-pass
     sum exceeds epsilon (2B-S4-051/057).

7) Materialise output rows in PK order and schema-validate.
   - Emit rows in PK order `[merchant_id, utc_day, tz_group_id]`.
   - Columns: `merchant_id, utc_day, tz_group_id, p_group, base_share, gamma,
     created_utc` and (if enabled) `mass_raw, denom_raw`.
   - Validate against `schemas.2B.yaml#/plan/s4_group_weights` with the JSON
     schema adapter (table row schema).

8) Post-publish assertions and write-once publish.
   - Ensure coverage for every `{merchant, tz_group, utc_day}` (2B-S4-050).
   - Validate `sum(p_group)=1` per merchant/day within epsilon (2B-S4-051).
   - Validate `sum(base_share)=1` per merchant within epsilon (2B-S4-052).
   - Enforce write-once + atomic publish (stage/fsync/rename) with byte-identity
     checks on re-emits (2B-S4-080/081/082).

9) Run-report (stdout JSON) + optional persisted copy.
   - Emit single JSON run-report to stdout with spec-required fields:
     inputs_summary, aggregation + normalisation metrics, publish details,
     validators, summary, environment, id_map, counters, durations.
   - Include deterministic samples per spec (rows, normalisation, base_share,
     coverage days; gamma mismatch sample only on V-09 fail).
   - MAY persist the same JSON under reports/layer1/2B/state=S4/... (diagnostic).

10) Logging + performance discipline (story aligned).
   - Emit a story header log: objective + gated inputs + outputs.
   - Progress logs for the row-emission loop with elapsed, processed/total,
     rate, ETA (monotonic time).
   - Keep logs narrative and state-aware (counts describe scope + output stage).
   - Avoid full-table buffering; stream per merchant/day; bounded memory.

Open confirmations to resolve before coding:
1) Normalisation epsilon (î) source:
   - Plan: hard-code a programme constant (proposed `1e-12`) and use the same
     value for the tiny-negative clamp threshold unless you prefer a different
     constant. This avoids introducing a new policy input (S4 may read only the
     three enumerated datasets).
2) Optional audit fields:
   - Plan: include `mass_raw` and `denom_raw` in output rows to support the
     optional audit validators and simplify debugging. Confirm if you want the
     output minimal (omit both) instead.
3) Run-report persistence:
   - Plan: emit to stdout and also persist the same JSON file under the run
     reports path (diagnostic only). Confirm if you prefer stdout-only.

### Entry: 2026-01-15 22:10

Design element: Lock S4 confirmation decisions (epsilon, audit fields, run-report).
Summary: User confirmed the proposed constants and emission posture, so the S4
implementation will use a fixed epsilon, include audit fields, and emit both
stdout and file run-reports.

Decision details (before coding):
1) Normalisation epsilon (î):
   - Use a fixed programme constant `1e-12` for all S4 normalisation and tiny-
     negative guard checks.
   - Rationale: the spec does not permit additional policy inputs in S4; this
     keeps behaviour deterministic and consistent with existing 2B epsilons.

2) Optional audit fields:
   - Always emit `mass_raw` and `denom_raw` in `s4_group_weights` rows.
   - Rationale: supports V-19 audit coherence and simplifies diagnosis without
     altering the schema (fields are nullable/optional).

3) Run-report persistence:
   - Emit the run-report JSON to stdout (single JSON document) and also write
     the same JSON file under the run reports path.
   - Rationale: stdout is required by spec; file persistence aids review and
     traceability without becoming authoritative.

### Entry: 2026-01-15 22:23

Design element: 2B.S4 implementation kickoff (runner/CLI/Makefile wiring).
Summary: Begin coding S4 with deterministic streaming joins and per-merchant/day
renormalisation, write-once publish, and spec-tight run-report emission (stdout + file).

Implementation decisions & stepwise plan (before code changes):
1) Implementation strategy (determinism + performance).
   - Use a streaming Python loop over `s1_site_weights` and `s3_day_effects` to
     preserve strict PK order and stable serial reductions. Avoid parallel/group
     reductions that can change floating order.
   - Build a compact `site_timezones` lookup map keyed by
     (merchant_id, legal_country_iso, site_order) -> tzid to ensure O(1) join
     and to detect multimap keys early (2B-S4-041). Memory is bounded by the
     number of sites and is acceptable for the 2B scale.
   - Aggregate base_share per merchant/tzid in PK order while scanning S1,
     compute per-merchant sum and track max abs error for the run-report.
   - Extract the day grid from `s3_day_effects` (distinct utc_day, sorted), then
     stream S3 rows in PK order to emit S4 rows in the same PK order.

2) Join + coverage enforcement (validator mapping).
   - Missing tzid in the timezones map -> 2B-S4-040 (V-04).
   - Multimap key (same site key -> multiple tzid) -> 2B-S4-041 (V-04).
   - Duplicate PK rows while streaming S3 -> 2B-S4-041A (V-07).
   - Writer order violation in S3 input -> 2B-S4-083 (V-08).
   - Coverage mismatch per merchant/day or rows_written != rows_expected ->
     2B-S4-050 (V-06).
   - Day grid mismatch per merchant (missing or extra day vs global day list) ->
     2B-S4-090 (V-12).

3) Normalisation + domain checks.
   - Compute mass_raw = base_share * gamma and denom_raw = sum(mass_raw) per
     merchant/day. Require denom_raw > 0 (2B-S4-051/V-11).
   - p_group = mass_raw/denom_raw; if p_group < -epsilon -> 2B-S4-057 (V-10).
   - If tiny negatives in (-epsilon, 0), clamp to 0 and renormalise once;
     then enforce |sum(p_group)-1| <= epsilon (2B-S4-051/V-11).
   - Ensure base_share >= 0 and gamma > 0 (2B-S4-057/V-10).
   - Always emit mass_raw/denom_raw (nullable) per approved decision.

4) Output + validation + publish.
   - Emit rows in strict PK order: merchant_id, utc_day, tz_group_id.
   - Validate batches with `validate_dataframe` against
     `schemas.2B.yaml#/plan/s4_group_weights` and inline layer1 $defs.
   - Stage outputs under run-local tmp; atomic publish to dictionary path; on
     re-run, allow only byte-identical output (2B-S4-081/082).

5) Run-report construction (fields-strict, spec-only).
   - Include only the spec-required top-level keys:
     component, manifest_fingerprint, seed, created_utc, catalogue_resolution,
     inputs_summary, aggregation, normalisation, publish, validators, summary,
     environment, samples, counters, durations_ms, id_map.
   - Ensure samples are deterministic (rows by PK order; normalisation/base_share
     sorted by abs_error; coverage by earliest days). Omit gamma_echo unless
     V-09 fails.

6) Logging posture.
   - Story header log with objective + gated inputs + output path.
   - Progress logs for the S3 row stream (elapsed/processed/total/rate/eta).
   - Emit validator PASS at DEBUG; WARN/FAIL at visible levels.

7) Code wiring steps.
   - Create `seg_2B/s4_group_weights/runner.py` (using S3/S2 helper patterns).
   - Add CLI `engine/cli/s4_group_weights_2b.py`.
   - Update Makefile with SEG2B_S4_* args/cmd and `segment2b-s4` target.
   - Log all changes in 2026-01-15 logbook with references to this entry.

### Entry: 2026-01-15 22:51

Design element: S4 execution details for ordering, audit coherence, and sampling.
Summary: Clarify how to preserve PK order without resorting the S3 input, how
to apply tiny-negative clamping while keeping audit coherence within epsilon,
and how to select deterministic samples without storing all merchant/day errors.

Decision details (before coding):
1) S3 input ordering + writer-order validation.
   - Read `s3_day_effects` by enumerating parquet parts in ASCII-lex order and
     iterate rows as-is; do NOT resort the full table.
   - Enforce PK order on the streamed rows (abort `2B-S4-083`) so output order
     is guaranteed PK-ascending without a global sort.
   - Rationale: preserves determinism and avoids an expensive global sort while
     still validating writer order per V-08.

2) Site-timezones multimap handling.
   - Treat any duplicate `(merchant_id, legal_country_iso, site_order)` in
     `site_timezones` as a multimap violation (abort `2B-S4-041`), even if the
     duplicate rows share the same tzid.
   - Rationale: the spec mandates a strict 1:1 join; duplicates break the 1:1
     guarantee even when values are identical.

3) Tiny-negative clamp + audit coherence.
   - Compute `p_group = mass_raw / denom_raw` first; if any p < -epsilon, abort
     `2B-S4-057`. For -epsilon <= p < 0, clamp to 0 and renormalise once.
   - Keep `mass_raw` and `denom_raw` unchanged (still the raw values); enforce
     audit coherence with an epsilon tolerance so clamping stays within bounds.
   - Rationale: honours the clamp rule while keeping `p_group` ≈ `mass_raw /
     denom_raw` within epsilon for V-19.

4) Normalisation samples (top-20 without full storage).
   - Maintain a sorted top-20 list of `{merchant_id, utc_day, sum_p_group,
     abs_error}` as we stream; only replace the current worst entry when a new
     candidate is strictly better by the spec’s ordering.
   - Rationale: avoids storing all merchant×day errors while keeping the
     deterministic “largest abs_error, then merchant_id, then utc_day” rule.

### Entry: 2026-01-15 23:01

Design element: S4 wiring + timing fix follow-up.
Summary: Add the S4 CLI + Makefile target, and fix a timing bug that overwrote
the aggregation timing metric after it was computed.

Decision details and in-process actions:
1) Timing metric correction.
   - Issue spotted: `aggregate_ms` was computed correctly after base_share
     aggregation, then overwritten by `join_groups_ms` before publishing.
   - Decision: remove the overwrite so `aggregate_ms` reflects the aggregate
     phase only, and keep `join_groups_ms` unchanged.
   - Rationale: run-report timing fields must remain truthful; overwriting
     breaks performance review and violates the spec’s intent for timing stats.

2) CLI wiring.
   - Added `engine/cli/s4_group_weights_2b.py` using the same contract/run-root
     flags pattern as other 2B CLIs, with a dedicated logger and summary line.
   - Rationale: keeps the CLI surface consistent across 2B states and allows
     targeted S4 runs without invoking the segment driver.

3) Makefile wiring.
   - Added `SEG2B_S4_RUN_ID`, `SEG2B_S4_ARGS`, `SEG2B_S4_CMD`, and
     `segment2b-s4` target; updated `.PHONY` to include the new target.
   - Rationale: match existing per-state targets and make S4 runnable via
     the standard make workflow.

### Entry: 2026-01-15 23:03

Design element: S4 runtime fix (scope capture in nested normalisation).
Summary: Fix the S4 run failure caused by missing nonlocal bindings in the
per-merchant/day normalisation helper.

Decision details and in-process actions:
1) Failure observed.
   - `UnboundLocalError` in `_flush_day` when updating
     `max_abs_mass_error_per_day` and `merchants_days_over_epsilon` during
     the normalisation checks.
   - Root cause: the nested function assigns to those variables without
     declaring them `nonlocal`, so Python treats them as local.

2) Fix.
   - Added `max_abs_mass_error_per_day` and `merchants_days_over_epsilon` to
     the `nonlocal` list at the start of `_flush_day`.
   - Rationale: these counters are state-wide metrics used in run-report
     and validator decisions, so they must update the outer scope.

3) Follow-up.
   - Re-run `make segment2b-s4 RUN_ID=<latest>` after the fix to confirm the
     run completes and produces the S4 output + run-report.

### Entry: 2026-01-15 23:04

Design element: S4 nonlocal syntax correction.
Summary: Fix a syntax error caused by using parenthesized `nonlocal` in Python.

Decision details and in-process actions:
1) Failure observed.
   - `SyntaxError: invalid syntax` at the `nonlocal` statement after the prior
     fix, because Python does not allow parenthesized `nonlocal` lists.

2) Fix.
   - Replaced the parenthesized `nonlocal (...)` with explicit `nonlocal` lines
     for each variable (`rows_written`, `pk_duplicates`, `combine_ms`,
     `normalise_ms`, `write_ms`, `publish_bytes_total`,
     `max_abs_mass_error_per_day`, `merchants_days_over_epsilon`).
   - Rationale: preserve readability while keeping valid Python syntax.

### Entry: 2026-01-15 23:05

Design element: S4 nonlocal scope fix (batch part index).
Summary: Fix a second nonlocal scope error while batching output rows.

Decision details and in-process actions:
1) Failure observed.
   - `UnboundLocalError` raised when updating `part_index` inside `_flush_day`
     while writing batches.
   - Root cause: `_flush_day` increments `part_index` but did not declare it as
     `nonlocal`.

2) Fix.
   - Added `part_index` to the `nonlocal` declarations in `_flush_day`.
   - Rationale: `part_index` is a stateful counter for batch file names and
     must be updated across day flushes.

### Entry: 2026-01-15 23:06

Design element: S4 base_share clamp to satisfy schema bounds.
Summary: Prevent schema validation failures caused by floating-point drift
where `base_share` slightly exceeds 1.0.

Decision details and in-process actions:
1) Failure observed.
   - S4 batch validation failed (`2B-S4-030`) because `base_share` values were
     `1.0000000000000002` for single-group merchants, tripping the schema
     max of 1.0 even though sums were within epsilon.

2) Fix.
   - In `_flush_day`, abort if `base_share_value > 1.0 + EPSILON` (true
     contract violation).
   - If `1.0 < base_share_value <= 1.0 + EPSILON`, clamp to 1.0 before
     computing `mass_raw` and emitting the row.
   - Rationale: preserves deterministic math while tolerating benign float
     drift; keeps emitted rows within schema bounds.

3) Follow-up.
   - Re-run `make segment2b-s4 RUN_ID=<latest>` to confirm the batch validator
     passes and the S4 output + run-report are emitted.

### Entry: 2026-01-15 23:08

Design element: S4 run verification.
Summary: Re-ran S4 after the clamp fix; run completed and run-report is PASS.

Run review notes:
1) Execution status.
   - `make segment2b-s4 RUN_ID=2b22ab5c8c7265882ca6e50375802b26` completed.
   - Run-report summary: PASS (warn_count=0, fail_count=0).

2) Key counters observed (for reference, non-authoritative).
   - merchants_total=1249, tz_groups_total=3087, days_total=366,
     rows_written=1129842 (matches expected).
   - max_abs_mass_error_per_day ~ 4.44e-16, base_share_sigma_max_abs_error
     ~ 5.32e-13 (within epsilon).

3) Outcome.
   - No further code changes needed for S4; proceed to next state once the
     user confirms.




## S5 - Router core (two-stage O(1): group -> site) (S5.*)

### Entry: 2026-01-15 23:27

Design element: S5 contract review + pre-implementation plan.
Summary: Read the S5 expanded spec + contract pack and prepared a detailed,
state-aware implementation plan with open confirmations.

Files reviewed (state + contracts/policies):
- docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s5.expanded.md
- docs/model_spec/data-engine/layer-1/specs/contracts/2B/dataset_dictionary.layer1.2B.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/2B/artefact_registry_2B.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml (RNG envelope + alias_pick_group/site)
- config/layer1/2B/policy/route_rng_policy_v1.json
- config/layer1/2B/policy/alias_layout_policy_v1.json

Key spec anchors and obligations distilled:
1) S5 is a per-arrival router with exactly TWO single-uniform RNG draws
   (alias_pick_group -> alias_pick_site) per arrival, strict event order, and
   cumulative rng_trace_log updates after each event append.
2) S5 reads only catalogued inputs by ID, at exact partitions
   [seed, manifest_fingerprint]; policy files are token-less and MUST be
   selected by S0-sealed path + sha256. No literal paths; no network I/O.
3) S2 alias artefacts are integrity-checked (policy echo + blob_sha256), but
   v1 does NOT decode group slices from the blob; it builds per-group aliases
   from S1 weights filtered by site_timezones.
4) Optional s5_selection_log is allowed ONLY if the Dictionary registers it;
   it must be arrival-ordered and partitioned by
   [seed, parameter_hash, run_id, utc_day], with manifest_fingerprint as a
   column (path ↔ embed equality).
5) Run-report is required to STDOUT (strict fields, created_utc = S0
   verified_at_utc). Persisted copies are non-authoritative but allowed.

Open confirmations to resolve before coding:
1) route_rng_policy_v1 schema mismatch: current JSON lacks required fields
   (policy_id, rng_engine, streams.routing_selection/routing_edge). Proposal:
   update config to match schemas.2B.yaml#/policy/route_rng_policy_v1 and keep
   semver policy_version (1.0.0). Confirm this is acceptable.
2) Selection-log gating: spec says "policy-gated" but only the Dictionary
   registers s5_selection_log. Proposal: add
   route_rng_policy_v1.extensions.selection_log_enabled (boolean) and treat
   selection log as enabled only when BOTH the dictionary entry exists and the
   policy extension is true. Confirm this gating rule.
3) Arrival source for S5 runner: spec defines per-arrival routing but does not
   name a dataset of arrivals in the Dictionary. We need to confirm the
   expected arrival source for the batch runner (e.g., a deterministic driver
   passed via CLI, or a defined arrival roster in the segment). Until this is
   clarified, the runner cannot choose a canonical arrival stream.

Planned implementation approach (after confirmations):
1) Inputs + gate checks (S0-evidence rule).
   - Load s0_gate_receipt_2B + sealed_inputs_2B at
     [manifest_fingerprint], validate schema anchors.
   - Assert route_rng_policy_v1 + alias_layout_policy_v1 appear in sealed
     inputs with exact path + sha256; record their digests for the run-report.
   - Resolve all run-local inputs by Dictionary ID:
     s4_group_weights, s1_site_weights, s2_alias_index, s2_alias_blob,
     site_timezones at [seed, manifest_fingerprint].

2) Preflight integrity (S2 parity + policy echo).
   - Hash s2_alias_blob bytes (SHA-256) and compare to s2_alias_index.blob_sha256.
   - Verify s2_alias_index header fields (layout_version, endianness,
     alignment_bytes, quantised_bits) match alias_layout_policy_v1.
   - Abort on mismatch (2B-S5-041).

3) Data access + mapping setup.
   - Build a site_id -> tz_group_id (tzid) map from site_timezones for
     coherence checks and filtering. Keep it in memory (id64 -> tzid string).
   - Prepare streaming readers for s4_group_weights and s1_site_weights in PK
     order (merchant_id, utc_day, tz_group_id / site_order).

4) Router core (two-stage O(1)).
   - GROUP_ALIAS[m,d]: build from s4_group_weights p_group rows for (m,d,*) in
     PK order; build Walker/Vose alias (deterministic, RNG-free).
   - SITE_ALIAS[m,d,g]: build from s1_site_weights rows for merchant m filtered
     to tz_group_id == g via site_timezones; weights from p_weight; stable
     serial normalization; deterministic alias build.
   - For each arrival (m,t): derive utc_day; draw uniform via Philox
     alias_pick_group; decode group alias to tz_group_id; draw uniform via
     alias_pick_site; decode site alias to site_id; assert mapping coherence
     (site_timezones tzid == chosen tz_group_id). Abort on empty slice or
     mismatch.

5) RNG evidence + log emission (layer envelope).
   - Append alias_pick_group event, then alias_pick_site event for each
     arrival, using schemas.layer1.yaml RNG envelope (module=2B.S5.router).
   - After EACH event append, append one rng_trace_log row with cumulative
     totals (events_total, draws_total, blocks_total).
   - Emit rng_audit_log once per run (routing stream id + policy digest).

6) Optional s5_selection_log (if enabled by policy + dictionary).
   - Write JSONL in arrival order; one file per
     [seed, parameter_hash, run_id, utc_day] partition.
   - Include manifest_fingerprint column; created_utc = S0 verified_at_utc.
   - Publish atomically; idempotent re-emit only if bytes identical.

7) Run-report (STDOUT JSON; strict fields).
   - Emit required fields: component, ids, policy digest/stream id, input paths,
     rng_accounting (events_group, events_site, draws_total), selection_log
     enabled flag, validators, summary. created_utc from S0 verified_at_utc.
   - Persist a copy under reports/layer1/2B/state=S5/... for diagnostics (non-
     authoritative) to stay consistent with other states.

8) Logging (story-style).
   - Story header: objective, gated inputs validated, outputs/logs to be
     produced (rng events, trace, optional selection log).
   - Phase logs: preflight integrity, group alias build, site alias build,
     per-arrival routing, rng event emission, selection log emission.
   - Progress logs for long loops include elapsed, processed/total, rate, ETA.

9) Performance + determinism controls.
   - Cache aliases with LRU-by-bytes; evict SITE_ALIAS first, then GROUP_ALIAS.
   - Stable serial reductions (binary64 ties-to-even); no data-dependent reorder.
   - Avoid scanning s2_alias_blob beyond hash verification; do not parse blob.

10) Validation + test plan.
    - Run `make segment2b-s5 RUN_ID=<latest>` once implemented.
    - Inspect run-report for draws_total == 2*selections and event-order
      invariants; confirm selection_log partitioning if enabled.
    - If failures arise, append entries before fixes per implementation-map
      discipline.

Entry: 2026-01-15 23:53
(S5 contracts + policy alignment — pre-implementation reasoning)
Summary of design problem:
- The S5 spec defines per-arrival routing but does not name a catalogue dataset
  for arrivals. The batch/standalone runner would otherwise be forced to read
  an un-catalogued input, violating the “Dictionary-only resolution” rule.
- The current `route_rng_policy_v1.json` does not match the schema/authoring
  guide (missing policy_id/rng_engine/streams shape). S5/S6 must fail-closed
  if the policy cannot be validated.

Alternatives considered (arrival source):
1) Treat S5 as a pure library invoked only by 5B (no standalone runner input).
   - Pros: avoids adding new datasets; aligns with per-arrival routing in L2.
   - Cons: makes 2B S5 un-runnable in isolation; prevents deterministic batch
     routing tests for L1; contradicts the current CLI runner posture.
2) Allow ad-hoc arrival inputs without dictionary entry (literal path or CLI
   pointer).
   - Rejected: violates catalogue discipline and “no reads beyond inputs
     above”; would be non-auditable and break run reproducibility.
3) Add a catalogued arrival roster dataset for standalone runs.
   - Chosen: preserves contract discipline; keeps S5 deterministic and testable
     without forcing L2 presence; still optional for production use.

Decision:
- Add **optional** dataset `s5_arrival_roster` to 2B contracts (dictionary +
  schema + registry) for standalone/batch runs. S5 uses it only if present and
  only when running in batch/CLI mode; L2 (5B) can still own real-time arrivals.
- Keep S0 sealing unchanged for now (arrival roster is within-segment, run-local
  input, not cross-layer/policy; S5 will still resolve by Dictionary ID only).
  If we later require S0 sealing, we will add a new optional seal step with
  explicit validator IDs.
- Align `route_rng_policy_v1.json` with the schema and authoring guide: include
  policy_id, rng_engine, streams.routing_selection/routing_edge, budgets, and
  a policy_version semver. Add `extensions.selection_log_enabled` to gate
  optional selection logs.

Arrival roster contract shape (proposed):
- Path: `data/layer1/2B/s5_arrival_roster/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/arrival_roster.jsonl`
- Partitioning: `[seed, parameter_hash, run_id]` (run-scoped; utc_day in rows).
- Row schema (new anchor): `schemas.2B.yaml#/trace/s5_arrival_roster_row`
  with `{merchant_id, utc_timestamp, utc_day}` (minimum fields for routing).
- Optional field: `arrival_seq` (only if we need stable ordering when timestamps
  collide; omit unless required by spec or observed collisions).

Implementation steps (to execute next):
1) Update `schemas.2B.yaml` to add `trace/s5_arrival_roster_row` (fields-strict,
   minimal required fields; uses layer defs for id64 + rfc3339_micros + date).
2) Add `s5_arrival_roster` to `dataset_dictionary.layer1.2B.yaml` (status:
   optional; run-scoped partitions; schema_ref to new anchor).
3) Add `s5_arrival_roster` to `artefact_registry_2B.yaml` (category: input or
   diagnostic; notes: optional, run-local for standalone routing).
4) Update `config/layer1/2B/policy/route_rng_policy_v1.json` to match schema +
   authoring guide (policy_id, rng_engine, streams, budgets, key_basis) and add
   `extensions.selection_log_enabled` default false.
5) Add a short S5 spec addendum noting the optional arrival roster for batch
   runs (keeps dictionary-only rule intact).
6) Log each change in logbook with timestamps before code edits.

Entry: 2026-01-16 00:00
(S5 contracts + policy alignment — changes applied)
What changed:
- Added `trace/s5_arrival_roster_row` schema anchor (minimal row: merchant_id,
  utc_timestamp, utc_day) in `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml`.
- Registered optional `s5_arrival_roster` dataset in
  `docs/model_spec/data-engine/layer-1/specs/contracts/2B/dataset_dictionary.layer1.2B.yaml`
  and `docs/model_spec/data-engine/layer-1/specs/contracts/2B/artefact_registry_2B.yaml`.
- Updated `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s5.expanded.md`
  to document the optional run-scoped arrival roster and its partition law.
- Rewrote `config/layer1/2B/policy/route_rng_policy_v1.json` to match the
  schema/authoring guide and added `extensions.selection_log_enabled=false`.

Notes:
- No S0 sealing changes yet; arrival roster remains an optional, run-local input
  resolved by Dictionary ID only (consistent with S5's "Dictionary-only reads").
- If later required, we will add an explicit optional seal step and a new
  validator ID rather than silently changing S0 behaviour.

### Entry: 2026-01-16 05:29

Design element: 2B.S5 router core implementation (Option-A per spec).
Summary: Implement the two-stage router (group -> site), RNG evidence, optional
selection log gating, and strict run-report emission, using Dictionary-only
inputs and S0-sealed policy bytes.

Plan (before implementation, detailed and stepwise):
1) Establish run identity + contract sources.
   - Load run_receipt.json for run_id, seed, parameter_hash, manifest_fingerprint.
   - Resolve ContractSource layout = model_spec (dev mode) and record dictionary/
     registry versions for the run-report.
   - Attach a per-run file logger (state-aware) under the run log path.

2) Enforce S0 evidence and sealed inputs (no read before gate).
   - Resolve `s0_gate_receipt_2B` + `sealed_inputs_2B` at [manifest_fingerprint].
   - Validate both payloads against `schemas.2B.yaml#/validation/*`.
   - Confirm `route_rng_policy_v1` and `alias_layout_policy_v1` appear in the
     sealed_inputs inventory with exact path + sha256_hex (S0-evidence rule).
   - Record S0 `verified_at_utc` as `created_utc` for all logs/run-report rows.

3) Resolve required inputs by Dictionary ID only (exact partitions).
   - `s4_group_weights`, `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`,
     `site_timezones` at [seed, manifest_fingerprint].
   - Optional: `s5_arrival_roster` at [seed, parameter_hash, run_id]. If
     missing, abort in the CLI runner (standalone batch requires a catalogued
     roster) with 2B-S5-020.
   - Enforce path-embed equality for all tokenized paths; abort on mismatch.

4) Preflight S2 alias integrity (parity + blob hash).
   - Read `s2_alias_index` JSON and verify policy echo fields match
     `alias_layout_policy_v1` (layout_version, endianness, alignment_bytes,
     quantised_bits).
   - SHA256 the raw bytes of `s2_alias_blob` and compare to
     `s2_alias_index.blob_sha256`. Abort on mismatch (2B-S5-041).

5) Site identity resolution (spec gap; deterministic decision).
   - Inputs only carry `(merchant_id, legal_country_iso, site_order)`; S5
     requires `site_id` (id64) in selection logs and run-report samples.
   - Decision: derive `site_id` deterministically as
     `uint64(sha256(f"{merchant_id}:{legal_country_iso}:{site_order}"))[:8]`
     (big-endian to uint64). This preserves determinism without adding a new
     input, and can be replicated by downstream systems.
   - Log this derivation decision in the logbook + run-report `notes` section.

6) Router core (two-stage alias, Option-A only).
   - Build GROUP_ALIAS[m, utc_day] from `s4_group_weights` rows (PK order).
   - Build SITE_ALIAS[m, utc_day, tz_group_id] from `s1_site_weights` filtered
     by `site_timezones` where tzid == tz_group_id.
   - For each arrival:
     a) draw uniform via Philox for alias_pick_group -> tz_group_id;
     b) draw uniform via Philox for alias_pick_site -> site_id.
   - Enforce mapping coherence: tz_group_id(site_id) (via site_timezones)
     must equal chosen tz_group_id; abort on mismatch (2B-S5-055).

7) RNG evidence (layer envelope).
   - Append one `rng_event_alias_pick_group` and one
     `rng_event_alias_pick_site` per arrival, in that order.
   - After EACH event append, append one cumulative `rng_trace_log` row.
   - Append `rng_audit_log` once per run with routing stream metadata.
   - Use Philox2x64-10 helper from `seg_1A.s1_hurdle.rng` and the stream/
     budgets from `route_rng_policy_v1`.

8) Optional selection log (policy + dictionary gated).
   - Enable only when Dictionary registers `s5_selection_log` AND
     `route_rng_policy_v1.extensions.selection_log_enabled == true`.
   - Partition by [seed, parameter_hash, run_id, utc_day]; include
     manifest_fingerprint column and created_utc.
   - Writer order = arrival order; publish atomically (write-once).

9) Run-report (STDOUT JSON + file copy).
   - Emit strict JSON to stdout via logger.info and persist under
     reports/layer1/2B/state=S5/seed=.../manifest_fingerprint=.../s5_run_report.json.
   - Include policy ids/digests, dictionary-resolved input paths, RNG accounting
     (events_group/events_site/draws_total), selection_log_enabled, and samples
     of {merchant_id, utc_day, tz_group_id, site_id}.

10) Logging (story-style) + performance controls.
    - Emit a story header with objective + gated inputs + outputs/logs.
    - Progress logs for arrivals include elapsed, processed/total, rate, ETA.
    - Cache alias tables with deterministic LRU-by-bytes; evict SITE_ALIAS first.

11) Test/run plan.
    - Run `make segment2b-s5 RUN_ID=<current>`; fix any schema/path/partition
      errors; append follow-up entries before each fix (per log discipline).
    - Validate run-report invariants: draws_total == 2 * selections_logged and
      event ordering (group then site) is preserved.

Entry: 2026-01-16 05:47
(S5 RNG derivation + alias build decisions before coding)
- Decision: implement routing RNG derivation using the route_rng_policy_v1
  key_basis [seed, parameter_hash, run_id] and a deterministic domain split
  mirroring the 2B.S3 pattern (sha256 -> key + base counter).
  - master_digest = sha256( uer_string("2B.S5.master")
    || parameter_hash_bytes || run_id_bytes || ser_u64(seed) ).
  - stream_digest = sha256( master_digest || uer_string("2B.S5.routing")
    || uer_string(rng_stream_id) ).
  - key = low64(stream_digest); counter_hi/lo = BE64 bytes 16:23 and 24:31.
  - This binds the stream to route_rng_policy_v1.rng_stream_id and the
    key_basis without introducing new policy fields.
- Counter posture: single monotone counter for routing_selection stream; per
  arrival, consume exactly two events in order (group then site), each with
  blocks=1/draws="1" and counter delta +1 (u128). This satisfies V-09
  monotonicity and the “two single-uniform draws per arrival” rule.
- Uniform mapping: use u01() from 1A.S1 RNG helper (open interval, never 0/1)
  to satisfy spec’s open-interval uniform requirement.
- Alias build strategy (deterministic, O(1) picks):
  - Group alias cache: keyed by (merchant_id, utc_day), built from S4 p_group
    with stable sort [merchant_id, utc_day, tz_group_id].
  - Site alias cache: keyed by (merchant_id, tz_group_id), built from S1
    p_weight rows joined to site_timezones and filtered by tzid == tz_group_id,
    with stable sort [merchant_id, tz_group_id, site_order].
  - Per-group weights are renormalized inside each tz_group; any empty slice
    aborts with a spec error (2B-S5-043 equivalent).
- site_id derivation (deterministic): site_id is not present in S1/S2/2A
  outputs, so we will derive id64 as:
  sha256(f"{merchant_id}:{legal_country_iso}:{site_order}") -> take low 64 bits
  (little-endian bytes 24..31) to align with other uint64 derivations.
  This is recorded in run-report + logs for auditability.
- Selection log gating: emit only if dictionary includes s5_selection_log and
  route_rng_policy_v1.extensions.selection_log_enabled == true. Default false.


### Entry: 2026-01-16 06:36

Design element: 2B.S5 router core implementation start (writer + CLI + Makefile).
Summary: Begin coding S5 per the documented plan, wiring the runner/CLI/Makefile and
applying the agreed routing + logging decisions before running the state.

Implementation start plan (detail-first, before code):
1) Runner scaffold and contracts.
   - Create `packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py` and
     mirror the helper structure used in S3/S4 (StepTimer, ProgressTracker, emit_event,
     emit_validation, abort/warn handlers, run-report writer).
   - Load contract packs for 2B + 2A + layer1; inline layer1 defs for schema refs.
   - Validate `s0_gate_receipt_2B` + `sealed_inputs_2B` and record created_utc from
     the receipt for all outputs.

2) Inputs, S0 evidence, and dictionary-only resolution.
   - Resolve required inputs by ID at [seed, manifest_fingerprint]:
     `s4_group_weights`, `s1_site_weights`, `s2_alias_index`, `s2_alias_blob`,
     `site_timezones`.
   - Resolve optional `s5_arrival_roster` at [seed, parameter_hash, run_id]; if missing,
     abort with 2B-S5-020 in the CLI runner (standalone batch requires roster).
   - Enforce S0 evidence by verifying policy entries (route_rng_policy_v1 and
     alias_layout_policy_v1) exist in sealed_inputs with exact path + sha256.

3) Preflight integrity and policy alignment.
   - Hash s2_alias_blob bytes and compare to s2_alias_index.blob_sha256.
   - Verify alias layout policy echo fields in s2_alias_index (layout_version,
     endianness, alignment_bytes, quantised_bits).
   - Validate route_rng_policy_v1 schema and enforce rng_engine == philox2x64-10,
     draws_per_selection == 2, and event_families alias_pick_group/site.

4) Router core (two-stage alias, single-uniform budget).
   - Build group alias tables per (merchant_id, utc_day) using s4_group_weights.
   - Build site alias tables per (merchant_id, utc_day, tz_group_id) using s1_site_weights
     filtered by site_timezones tzid == tz_group_id.
   - Use Philox2x64-10 with counters from route_rng_policy_v1.basis.counter_start and
     derive uniforms via u01(); one uniform per event.
   - Emit alias_pick_group event then alias_pick_site event per arrival, append
     rng_trace_log after each event, and emit a single rng_audit_log per run.

5) Optional selection log and run-report.
   - Emit s5_selection_log only when dictionary registers the dataset AND
     route_rng_policy_v1.extensions.selection_log_enabled == true (default false).
   - Partition selection log by [seed, parameter_hash, run_id, utc_day], include
     manifest_fingerprint and counter snapshots for both events.
   - Emit strict run-report to STDOUT + file; include required keys and deterministic
     samples (up to 20 selections). Keep the samples even though the spec’s
     “fields-strict” wording conflicts (flagged in earlier entry).

6) Logging story and progress.
   - Add S5 story header: objective, gated inputs, outputs/gates being produced.
   - Progress logs for arrivals include elapsed, processed/total, rate, ETA and
     explain what each count represents (arrivals routed). Note phases like
     “building group aliases”, “routing arrivals”, “writing selection log”.

7) Wiring + run plan.
   - Add CLI `packages/engine/src/engine/cli/s5_router_2b.py` and Makefile target
     `segment2b-s5` with RUN_ID args. Run the state after implementation and log
     every fix as new entries.


### Entry: 2026-01-16 06:43

Design element: 2B.S5 router implementation pass (start of coding).
Summary: Begin coding S5 now that the routing decisions are locked; enforce
the story-style logging and S0-evidence constraints while implementing.

Detailed notes before coding (explicit decisions + mechanics):
- Re-read: state.2B.s5.expanded.md + schemas.2B.yaml + dataset_dictionary.layer1.2B.yaml
  + artefact_registry_2B.yaml + route_rng_policy_v1.json + alias_layout_policy_v1.json.
  Logbook entry references this re-read.
- Implementation posture:
  - Use S3/S4 helper patterns (StepTimer/ProgressTracker, _emit_event/_emit_validation,
    _atomic_publish_dir/_atomic_publish_file, _render_catalog_path/_resolve_dataset_path).
  - Validate JSONL outputs (rng events/trace/audit/selection log) with Draft202012Validator
    against record-level schemas; do NOT use validate_dataframe for non-table records.
  - Validate s5_arrival_roster row-by-row (schemas.2B.yaml#/trace/s5_arrival_roster_row),
    abort on any row invalid to uphold strict input discipline.
- RNG/alias mechanics finalization:
  - Derive Philox key + base counters exactly as S3 (domain_master/domain_stream + rng_stream_id).
  - One uniform per stage (group/site), blocks=1, draws="1", counter increment +1 per event.
  - Build per-merchant/day group alias and per-merchant/group site alias using Vose
    (deterministic ordering). Fail fast on empty slices or non-finite sums.
- Output/logging discipline:
  - Emit story header that names objective + inputs validated + outputs produced.
  - Progress logs include what counts represent (arrivals routed) + rate + ETA.
  - Run-report includes samples (despite spec ambiguity), with created_utc echoed
    from S0 receipt verified_at_utc.

### Entry: 2026-01-16 07:18

Design element: 2B.S5 router implementation continuation (runner/CLI/Makefile + concrete mechanics).
Summary: Proceed with the actual code build for S5, locking the concrete data-flow
and validation mechanics before writing the runner file.

Detailed implementation notes (before code):
1) Site identity derivation (explicit function, now locked).
   - Derive `site_id` deterministically as `low64(sha256(f"{merchant_id}:{legal_country_iso}:{site_order}"))`
     where `low64` uses the same little-endian 64-bit convention as other layer RNG helpers.
   - Build a `(merchant_id, site_id) -> tzid` lookup by computing `site_id` for every
     `site_timezones` row; abort on any duplicate `(merchant_id, site_id)` collisions.
   - Use this mapping for the S5 coherence check (`tz_group_id(site_id)` must equal
     the chosen group) and for the selection log `site_id` field.

2) Alias build inputs and ordering (stable, deterministic).
   - `GROUP_ALIAS[m,d]` is built from S4 `p_group` rows sorted by PK
     `(merchant_id, utc_day, tz_group_id)`. Abort with 2B-S5-040 if the sum of
     `p_group` differs from 1.0 beyond EPS (no hidden renormalization).
   - `SITE_ALIAS[m,d,g]` is built from S1 `p_weight` rows joined to 2A `site_timezones`
     and filtered to tzid == `g`. Sorting uses `(merchant_id, legal_country_iso, site_order)`
     as required; weights are normalized within the filtered slice only.

3) Run-scoped arrivals + per-day selection log files.
   - Require `s5_arrival_roster` at `[seed, parameter_hash, run_id]` for the standalone
     runner; abort with 2B-S5-020 if missing (catalogue-only reads).
   - Selection log gating: emit only when (a) Dictionary registers `s5_selection_log` and
     (b) `route_rng_policy_v1.extensions.selection_log_enabled == true`.
   - Maintain per-`utc_day` JSONL handles so writer order equals arrival order inside each
     day partition; publish by atomic move after close.

4) RNG envelopes + trace/audit (strict budgets).
   - Each arrival emits exactly two events (`alias_pick_group` then `alias_pick_site`),
     each with `blocks=1`, `draws="1"`, counters incremented by +1.
   - After EACH event append, add exactly one `rng_trace_log` row via
     `RngTraceAccumulator.append_event` (cumulative totals).
   - Emit a single `rng_audit_log` row for the run with algorithm, build_commit,
     and platform metadata, partitioned by `[seed, parameter_hash, run_id]`.

5) Wiring steps (files).
   - Create `packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py`
     with the above mechanics + story-style logs.
   - Create CLI `packages/engine/src/engine/cli/s5_router_2b.py`.
   - Update `makefile` with `segment2b-s5` target, add SEG2B_S5 args/command,
     and include it in `.PHONY` and `segment2b` target.

### Entry: 2026-01-16 07:38

Design element: 2B.S5 router spec-alignment fixes (outputs, sealed input gating, run-report shape).
Summary: The initial runner draft must be corrected to follow the S5 expanded spec on
output partitions/paths, sealed arrival roster handling, alias index parity, and the
strict run-report shape; also align rng_audit_log to the layer schema and improve
story-style logging.

Detailed plan before code changes (stepwise + decisions):
1) Outputs & partition alignment (spec-critical).
   - Split RNG event output into TWO partitions:
     `rng_event_alias_pick_group` and `rng_event_alias_pick_site`, each written to
     the dictionary path under `logs/layer1/2B/rng/events/<family>/seed=.../parameter_hash=.../run_id=.../part-00000.jsonl`.
   - Use `run_paths.run_root / rendered_path` for all outputs (events, trace, audit,
     selection log). Remove any path handling that publishes relative to repo root.
   - Validate that rendered output paths contain required tokens
     `[seed, parameter_hash, run_id]` for RNG logs (per S5 §5.2), and abort if not.

2) Arrival roster gating (standalone runner must be catalogue-only).
   - Require `s5_arrival_roster` in `sealed_inputs_2B` (per our earlier decision);
     compare sealed path with the rendered dictionary path and enforce partition
     equality for `[seed, parameter_hash, run_id]`.
   - Remove the incorrect check comparing the rendered path to the raw template
     string (it falsely aborts for templated paths).
   - Validate arrival roster rows against `schemas.2B.yaml#/trace/s5_arrival_roster_row`;
     abort on any invalid row to preserve strict input discipline.

3) Alias artefact parity vs alias_layout_policy_v1.
   - Enforce header parity for `layout_version`, `endianness`, `alignment_bytes`,
     and `quantised_bits` between `s2_alias_index` and `alias_layout_policy_v1`.
   - Keep blob integrity check (`blob_sha256`) and policy digest echo check
     (`index.policy_digest == alias_layout_policy_v1.sha256_hex`).
   - Optionally verify `blob_size_bytes` matches actual blob byte length (warn or
     abort; decide during implementation and document).

4) RNG audit payload alignment.
   - Replace `audit_payload` with schema-valid fields only:
     `ts_utc, run_id, seed, manifest_fingerprint, parameter_hash, algorithm, build_commit`,
     plus optional `code_digest`, `hostname`, `platform`, `notes` (no `python_version`).
   - Compute `build_commit` via local git hash resolution (same helper style as S6).

5) Run-report reformat to spec (fields-strict).
   - Build `component="2B.S5"`, `manifest_fingerprint`, `seed`, `parameter_hash`, `run_id`,
     `created_utc` (S0 verified_at_utc), `catalogue_resolution`.
   - Add `policy` block with id/version_tag/sha256/rng_engine/rng_stream_id/draws_per_selection.
   - Add `inputs_summary` (dictionary-resolved paths for s4/s1/site_timezones/s2 index/blob).
   - Add `rng_accounting` with `events_group`, `events_site`, `events_total`,
     `draws_total`, `first_counter`, `last_counter` (objects `{hi, lo}`).
   - Add `logging` (selection_log_enabled + partition string when enabled),
     `validators`, `summary` (PASS/FAIL + warn_count/fail_count),
     `environment` (engine_commit, python_version, platform, network_io_detected),
     `samples.selections` + `samples.inputs`.
   - Remove non-spec keys from the current draft (e.g., `segment`, `state`, `counts`).

6) Story-style logging (operator-readable).
   - Emit a story header: objective, gated inputs, and outputs being produced.
   - Add phase logs: “validated S0 receipt”, “sealed inputs verified”, “alias
     parity checks”, “routing arrivals”, “writing rng logs”, “selection log
     publish” so the run reads as a coherent narrative.
   - Keep progress logs with elapsed, processed/total, rate, ETA for the routing loop.

7) Wiring.
   - Add CLI `engine.cli.s5_router_2b` with run-id/config args (mirrors other 2B CLIs).
   - Add Makefile `segment2b-s5` target + args, and include S5 in `segment2b`.

### Entry: 2026-01-16 07:56

Design element: 2B.S5 router implementation changes applied (post-plan execution).
Summary: Implemented the spec alignment changes in the S5 runner, added the CLI and
Makefile wiring, and corrected outputs/validation/reporting to match the S5 expanded spec.

Implementation actions taken (chronological, detailed):
1) Output partitioning + atomic publish.
   - Split RNG event outputs into two distinct partitions (group/site) with
     `part-00000.jsonl` filenames to satisfy `dataset_dictionary.layer1.2B.yaml`
     (`rng_event_alias_pick_group` and `rng_event_alias_pick_site`).
   - Switched all output targets to `run_paths.run_root / rendered_path` via a
     shared `_render_output_path()` helper (handles `part-*.jsonl` -> `part-00000.jsonl`).
   - Added output partition token checks for `[seed, parameter_hash, run_id]` on
     event/trace/audit paths before publishing.
   - Replaced directory publishes with `_atomic_publish_file` for event/trace/audit
     logs; selection logs also publish via `_atomic_publish_file`.
   - Added temp cleanup: `shutil.rmtree(tmp_root, ignore_errors=True)` after publish.

2) Arrival roster sealing + path/partition equality.
   - Enforced `s5_arrival_roster` presence in `sealed_inputs_2B` and validated
     sealed path equality against the rendered dictionary path.
   - Enforced partition equality for `[seed, parameter_hash, run_id]` and path-embed
     equality checks on the rendered path string.
   - Added sha256 integrity check of the roster file vs `sealed_inputs_2B`.

3) Alias index parity checks (policy echo + blob size).
   - Added header parity validation between `s2_alias_index` and
     `alias_layout_policy_v1` for `layout_version`, `endianness`,
     `alignment_bytes`, `quantised_bits`.
   - Added `blob_size_bytes` verification against the actual alias blob size.
   - Kept existing `blob_sha256` and `policy_digest` parity checks.

4) RNG policy enforcement + audit schema compliance.
   - Added strict checks for `rng_engine`, `key_basis`, `counter_step_per_event`,
     `counter_wrap_policy`, event family `blocks/draws`, and
     `draws_per_selection == 2`.
   - Implemented `_resolve_git_hash()` (same posture as S6) and removed
     schema-invalid audit fields; `rng_audit_log` now uses only schema-allowed
     fields (`build_commit`, optional `code_digest/hostname/platform/notes`).

5) Run-report format updated to the spec’s fields-strict layout.
   - Replaced the prior ad-hoc structure with `component`, `catalogue_resolution`,
     `policy`, `inputs_summary`, `rng_accounting`, `logging`, `validators`,
     `summary`, `environment`, `samples`.
   - Added deterministic `samples.inputs` + `samples.selections` and
     RNG accounting reconciliation (events_total == draws_total == 2x selections).

6) Story-style logging upgrades.
   - Added explicit narrative logs for: S0 receipt verification, sealed input
     verification, policy+RNG setup, alias index parity, arrival roster load,
     input row counts, and publish completion.
   - Kept progress logs with elapsed/rate/ETA and clarified label to
     “arrivals_routed (group->site selections)”.

7) Wiring.
   - Added CLI `packages/engine/src/engine/cli/s5_router_2b.py`.
   - Added Makefile target + args for `segment2b-s5` and included S5 in `segment2b`.

Notes:
- The S5 runner now uses run-root output paths and spec-aligned filenames,
  preventing accidental writes to repo root and matching the layer RNG log conventions.
### Entry: 2026-01-16 17:11

Problem:
- Running `segment2b-s5` fails with 2B-S5-020 required_asset_missing for
  `s1_site_weights`, even though the dataset exists on disk under the run
  folder. The S0 `sealed_inputs_2B` list does not include run-local outputs
  (S1/S2/S3/S4 outputs), because S0 only seals external inputs/policies.
- The current S5 gating erroneously requires *all* inputs (including run-local
  outputs) to be present in `sealed_inputs_2B`, which is stricter than the spec
  and conflicts with the S0 responsibility split.

Alternatives considered:
1) Force S0 to seal run-local outputs (S1/S2/S3/S4) into `sealed_inputs_2B`.
   - Rejected: S0 cannot know or hash those outputs before they are generated;
     it violates the state ordering and the spec's S0 role.
2) Keep sealed_inputs as the external/policy roster only, and treat run-local
   outputs as required-by-dictionary assets that must exist on disk and pass
   schema validation later in S5.
   - Accepted: preserves the intended S0 sealing boundary while still enforcing
     run-local availability and schema correctness.
3) Drop sealed_inputs checks entirely for S5.
   - Rejected: would weaken provenance guarantees for external inputs/policies
     and the new arrival roster, which should remain sealed.

Decision:
- Split S5 gating into two categories:
  - sealed_required_assets: external inputs and policies that must appear in
    `sealed_inputs_2B` (e.g., route_rng_policy_v1, alias_layout_policy_v1,
    site_timezones, s5_arrival_roster).
  - run_local_required_assets: outputs from prior 2B states (s1_site_weights,
    s2_alias_index, s2_alias_blob, s3_day_effects, s4_group_weights) validated
    by path existence + schema checks but NOT required in sealed_inputs.

Plan to implement (next step):
1) Update `packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py` to
   split `required_assets` into sealed vs run-local lists.
2) Adjust the `2B-S5-020` check to only require sealed assets in
   `sealed_inputs_2B` while keeping dictionary/path checks for run-local outputs.
3) Update the narrative log line to clarify which assets are sealed vs run-local.
4) Rerun `make segment2b-s5` for the same run_id to confirm green.

### Entry: 2026-01-16 17:13

Problem:
- S5 fails with 2B-S5-020 because `s5_arrival_roster` is missing from
  sealed_inputs_2B. The roster is optional, but `make segment2b-s5` runs
  batch/standalone mode and therefore needs a sealed arrival roster to supply
  arrivals.

Decision:
- Generate a deterministic run-scoped roster file so S5 can run green.
- Use *one arrival per merchant_id* derived from `s1_site_weights` so the
  roster is consistent with the run's sealed inputs.
- Use a fixed `utc_day` that exists in `s4_group_weights` for all merchants.
  Observed available days span 2024-01-01..2024-12-31 (366 days); choose
  `utc_day=2024-01-01` and `utc_timestamp=2024-01-01T00:00:00.000000Z` for
  determinism and to avoid day-missing failures.

Plan:
1) Build `arrival_roster.jsonl` at the dictionary path:
   `data/layer1/2B/s5_arrival_roster/seed=42/parameter_hash=.../run_id=.../arrival_roster.jsonl`
   with rows `{merchant_id, utc_timestamp, utc_day}`.
2) Re-run `segment2b-s0` so S0 seals `s5_arrival_roster` into sealed_inputs_2B.
3) Re-run `segment2b-s5` to verify S5 goes green.
4) Log the roster generation details (counts, paths) and keep run report output.

### Entry: 2026-01-16 17:37

Action taken:
- Generated `s5_arrival_roster` JSONL using all unique merchant_id values from
  `s1_site_weights` (1249 rows) with fixed `utc_day=2024-01-01` and
  `utc_timestamp=2024-01-01T00:00:00.000000Z`.
- Wrote to:
  runs/local_full_run-5/2b22ab5c8c7265882ca6e50375802b26/data/layer1/2B/
  s5_arrival_roster/seed=42/parameter_hash=56d451.../run_id=2b22.../arrival_roster.jsonl

Result:
- Re-ran `segment2b-s0` to seal the roster. S0 detected the roster and attempted
  to publish a new receipt, but failed with 2B-S0-080 (atomic publish violation)
  because the existing `s0_gate_receipt_2B` file differs from the newly computed
  receipt (roster inclusion changes the receipt content).

Next step:
- Remove the existing run-local `s0_gate_receipt` and `sealed_inputs` partitions
  for this run/manifest (so S0 can publish the updated receipt and sealed inputs),
  then re-run `segment2b-s0` and `segment2b-s5`.

### Entry: 2026-01-16 17:41

Change in roster generation plan:
- Since the run-local 2B outputs must be cleared before re-running S0–S5,
  we can no longer rely on `s1_site_weights` to build the roster (it would
  be deleted before S0). Instead, derive the roster from the upstream
  `site_locations` input (1B output), which is already sealed and available
  before S0 in 2B.

Reasoning:
- `site_locations` contains stable `merchant_id` coverage for the manifest;
  using it allows roster generation *before* S0 runs, aligning with the
  requirement that S0 seals the roster when present.
- This avoids a circular dependency on S1 outputs and keeps the roster
  generation deterministic and run-scoped.

Updated steps:
1) Clear run-local 2B outputs.
2) Generate `s5_arrival_roster` from `site_locations` (unique merchant_id),
   with fixed `utc_day=2024-01-01` and `utc_timestamp=2024-01-01T00:00:00.000000Z`.
3) Run `segment2b` (S0–S5) so S0 seals the roster and downstream created_utc
   matches the updated receipt.

### Entry: 2026-01-16 17:47

Issue:
- S5 failed during policy validation with `Unresolvable: schemas.layer1.yaml#/$defs/uint64`.
- The current S5 policy validation uses Draft202012Validator on the raw schema
  without inlining external `$ref` definitions, so jsonschema tries to resolve
  `schemas.layer1.yaml` as a remote URI and fails.

Decision:
- Inline external refs for policy schemas (route_rng_policy_v1 and
  alias_layout_policy_v1) using `_inline_external_refs` with the loaded
  `schemas.layer1.yaml` pack prior to Draft202012Validator.

Plan:
1) Update `packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py` to
   call `_inline_external_refs(policy_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")`.
2) Do the same for `alias_policy_schema` before validation.
3) Re-run `segment2b-s5` for the same run_id.

### Entry: 2026-01-16 17:49

Issue:
- S5 policy validation fails because `rng_stream_id` pattern in
  `schemas.2B.yaml` is double-escaped. The parsed pattern contains **two**
  backslashes (`^2B\\.[...]$`), which fails to match `2B.routing` (expects a
  literal backslash before the dot). This is a contract bug, not a policy bug.

Decision:
- Fix the schema pattern to use a single backslash so the regex matches the
  intended `2B.<token>` naming (e.g., `2B.routing`, `2B.routing_edge`).

Plan:
1) Update `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml`
   pattern strings for `rng_stream_id` in routing_selection and routing_edge to
   `'^2B\.[A-Za-z0-9_.-]+$'` **with a single backslash** in YAML (single-quoted).
2) Re-run `segment2b-s5` to confirm validation passes.

### Entry: 2026-01-16 17:50

Issue:
- S5 aborted with `TypeError: _StepTimer.info() takes 2 positional arguments but 4 were given`.
- The new log line uses format args, but `_StepTimer.info` only accepts a
  single message string.

Decision:
- Extend `_StepTimer.info` to accept `*args` and apply `%` formatting when
  provided, then append elapsed/delta as before. This mirrors `logger.info` usage
  while preserving the existing elapsed/delta suffix.

Plan:
1) Update `_StepTimer.info(self, message: str, *args)` and format the message
   when args are passed.
2) Re-run `segment2b-s5`.

### Entry: 2026-01-16 17:52

Issue:
- S5 failed with V-14 created_utc mismatch on `site_timezones`.
- `site_timezones` is an upstream 2A output; its `created_utc` reflects 2A S0
  and is not required to match 2B S0 `verified_at_utc`. The created_utc
  identity law in S5 applies to S5 outputs and 2B-owned outputs (S1/S4), not
  upstream inputs.

Decision:
- Remove the created_utc equality check for `site_timezones` in S5. Retain
  checks for 2B-produced datasets (`s1_site_weights`, `s4_group_weights`) and
  for S5 outputs (selection log rows).

Plan:
1) Drop/relax the `site_timezones` created_utc check in
   `packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py`.
2) Re-run `segment2b-s5` for the same run_id.

### Entry: 2026-01-16 17:55

Issue:
- S5 failed after routing completed with `AttributeError: RunPaths has no reports_root`.
- S5 uses a non-existent `run_paths.reports_root` instead of the standard
  `run_paths.run_root / "reports"` used elsewhere.

Decision:
- Replace `run_paths.reports_root` with `run_paths.run_root / "reports"` for
  S5 run-report output path.

Plan:
1) Update `packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py` to
   build `reports_root = run_paths.run_root / "reports"`.
2) Re-run `segment2b-s5`.

### Entry: 2026-01-16 17:59

Issue:
- S5 failed with 2B-S5-080 (non-identical output exists) when publishing
  rng_event_alias_pick_group. Prior failed attempts left partial RNG logs under
  run-local `logs/layer1/2B/rng/...`.

Decision:
- Remove the run-local 2B RNG logs for the current run_id so S5 can republish
  cleanly. This is safe because RNG logs are S5 outputs and must be regenerated
  with the same sealed inputs.

Plan:
1) Delete `runs/<run_id>/logs/layer1/2B/rng`.
2) Re-run `segment2b-s5`.


## S6 - Virtual-merchant edge routing (S6.*)

### Entry: 2026-01-16 18:09

Design element: 2B.S6 virtual-edge routing branch for is_virtual arrivals.
Summary: S6 must read S0-sealed policy inputs, bypass non-virtual arrivals,
consume exactly one RNG draw per virtual arrival on routing_edge, and emit
run-scoped RNG evidence (and optional s6_edge_log) without touching any
manifest_fingerprint-scoped plan/egress surfaces.

Observations from spec/contract review:
- S6 relies on S0 receipt + sealed_inputs_2B (manifest_fingerprint scoped) and
  does not re-hash upstream bundles.
- Required token-less policies: route_rng_policy_v1 and virtual_edge_policy_v1
  selected by exact S0-sealed path + sha256.
- S6 runtime input comes from S5 per-arrival fields
  {merchant_id, utc_timestamp, utc_day, tz_group_id, site_id, is_virtual};
  S6 must not recompute S5 decisions.
- RNG evidence is run-scoped only (seed, parameter_hash, run_id). One event
  per virtual arrival, and one rng_trace_log row after each event.
- Optional s6_edge_log may be emitted only if registered in the Dictionary.
- Current virtual_edge_policy_v1 JSON does not match schemas.2B.yaml (missing
  policy_id, uses default_edges/merchant_overrides/geo_metadata instead of
  edges[] with ip_country/edge_lat/edge_lon), and the spec expects a per-merchant
  distribution.

Open confirmations before coding (need user decision):
1) Policy shape: should we extend schemas.2B.yaml to allow
   default_edges + merchant_overrides (matching the current policy intent), or
   should we rewrite the policy to the existing edges[] schema and drop
   per-merchant overrides?
   - Recommendation: extend schema to accept default_edges + merchant_overrides
     and update the policy file to include policy_id + ip_country/edge_lat/
     edge_lon so the spec's per-merchant distribution is preserved.
2) Missing per-merchant entries: when a merchant has no override, should S6
   fall back to default_edges (recommended) or abort?
3) Optional s6_edge_log: dictionary already registers s6_edge_log. Should we
   emit it whenever registered, or gate behind a policy flag (e.g.
   extensions.edge_log_enabled) to avoid log bloat?
4) Run-report handling: spec requires a single STDOUT JSON report. Should we
   also persist a copy under reports/layer1/2B/state=S6 (non-authoritative),
   consistent with other 2B states?

Proposed plan (once confirmations are settled):
1) Contracts/policy alignment:
   - Update schemas.2B.yaml virtual_edge_policy_v1 to allow default_edges +
     merchant_overrides (or update policy JSON to edges[] if we choose that).
   - Update config/layer1/2B/policy/virtual_edge_policy_v1.json to include
     policy_id, version_tag, policy_version, and edge attributes
     {edge_id, ip_country, edge_lat, edge_lon, weight or country_weights}.
   - Ensure policy weights per merchant sum to 1 +/- epsilon; log and abort
     on policy minima failure.

2) S6 runner inputs and gating:
   - Verify S0 receipt + sealed_inputs_2B at manifest_fingerprint.
   - Resolve route_rng_policy_v1 + virtual_edge_policy_v1 by S0-sealed
     path + sha256 (no literal paths).
   - Optionally resolve s2_alias_index/blob by [seed, manifest_fingerprint] for
     integrity echo only (no decode).
   - Read S5 arrival stream fields as runtime inputs; do not touch S5 outputs.

3) Algorithm (per arrival):
   - If is_virtual=0: bypass, no RNG draw, no edge selection, no S6 logs.
   - If is_virtual=1:
     - Determine the merchant's edge distribution (override if present,
       otherwise default_edges).
     - Build/lookup per-merchant alias table in canonical edge_id order.
     - Draw exactly one single-uniform from routing_edge stream and decode
       to edge_id.
     - Attach ip_country/edge_lat/edge_lon from policy for that edge_id.
     - Append rng_event_cdn_edge_pick event (run-scoped) and then append
       one rng_trace_log row.
     - If s6_edge_log enabled, append a trace row with required fields and
       manifest_fingerprint embedded (run-scoped, utc_day partition).

4) Logging (story-first):
   - Story header: objective, gated inputs, outputs.
   - Progress logs for virtual arrivals (elapsed, processed/total, rate, eta).
   - Summaries: virtual count, non-virtual count, draws count, edge_log status.

5) Resumability and atomic publish:
   - Stage outputs under run tmp, then atomic publish to run-scoped paths.
   - Enforce write-once and byte-identical re-emits; otherwise require new run_id.

6) Validation/tests:
   - Policy schema validation + minima checks (non-empty edges, weights sum to
     1 +/- epsilon, attributes present).
   - RNG budget: draws == virtual_arrivals, counters monotone, no wrap.
   - Path-embed equality for s6_edge_log if written.
   - Replay sample: deterministic output for a fixed seed/run_id.

### Entry: 2026-01-16 18:12

Decision update (user-approved confirmations):
- Policy shape: proceed with **schema extension** to accept
  `default_edges + merchant_overrides + geo_metadata` while preserving the
  existing `edges[]` form. Then update `virtual_edge_policy_v1.json` to include
  `policy_id`, and normalize edge attributes to `ip_country/edge_lat/edge_lon`.
  Rationale: preserves current intent (per-merchant overrides) without dropping
  virtual routing coverage; keeps token-less policy sealing unchanged.
- Missing overrides: **fallback to default_edges** if a merchant has no override.
  Rationale: avoids hard failures for new virtual merchants; aligns with
  per-merchant override semantics while keeping deterministic routing.
- Optional s6_edge_log: **gate behind policy flag** + dictionary registration,
  default false to avoid log bloat. Rationale: consistent with S5 selection log
  gating; avoids unconditional log growth in production.
- Run-report: emit required STDOUT JSON **and** persist the same JSON under
  `reports/layer1/2B/state=S6/...` (non-authoritative diagnostic).

Immediate consequences to record before coding:
- `schemas.2B.yaml#/policy/virtual_edge_policy_v1` will be broadened to accept a
  second shape (default_edges/merchant_overrides/geo_metadata), which deviates
  from the authoring guide’s strict edges[]-only posture. This is a spec
  deviation; will note in logbook and preserve the edges[] path for future
  convergence.
- `config/layer1/2B/policy/virtual_edge_policy_v1.json` will be rewritten to
  include `policy_id` and field names aligned with the schema, plus geo_metadata
  entries for edge_lat/edge_lon.
- S6 will treat `is_virtual` as a runtime input: if the arrival record lacks it
  (current s5_arrival_roster schema), S6 will default to `false` and log a
  warning. This keeps S6 non-invasive until upstream provides is_virtual.

### Entry: 2026-01-16 18:26

Additional implementation decisions before coding:
- `s5_arrival_roster_row` schema currently disallows extra fields; to accept
  `is_virtual` when present, I will add `is_virtual` as an **optional** property
  (nullable false) to `schemas.2B.yaml#/trace/s5_arrival_roster_row`. This keeps
  backward compatibility for existing rosters while letting S6 consume the flag
  when available.
- RNG trace log handling: S5 already publishes `rng_trace_log` for the run. S6
  must **append** its trace rows (one per cdn_edge_pick event) to the same
  run-scoped file. I will implement an **append-capable atomic publish** for
  `rng_trace_log` that preserves the existing file bytes as a prefix and then
  appends S6 rows in order. If no new events are produced, S6 will leave the
  trace log unchanged.
- RNG audit log handling: if `rng_audit_log` already exists (from S5), S6 will
  not overwrite it; if missing, S6 will emit a single audit row using the same
  envelope as S5.

### Entry: 2026-01-16 18:34

Additional decision (edge-log context):
- `s6_edge_log` requires `tz_group_id` and `site_id`, but those are not present
  in `s5_arrival_roster_row`. To keep S6 non-invasive, I will **require**
  `s5_selection_log` to exist **only when** `s6_edge_log` is enabled, and join
  on `(merchant_id, utc_timestamp, utc_day)` to obtain `tz_group_id`/`site_id`.
  If `s6_edge_log` is disabled, S6 will not load the selection log and will run
  off the arrival roster alone.

### Entry: 2026-01-16 18:38

Pre-implementation plan (S6 coding steps; do this before edits):
- Implement `packages/engine/src/engine/layers/l1/seg_2B/s6_edge_router/runner.py`
  by adapting S5’s structure and logging conventions:
  - Story header log: objective, gated inputs (S0 receipt + sealed_inputs,
    route_rng_policy_v1, virtual_edge_policy_v1, s5_arrival_roster, optional
    s5_selection_log), and outputs (rng_event_cdn_edge_pick, rng_trace_log,
    rng_audit_log, optional s6_edge_log, run-report).
  - Validate S0 receipt against `validation/s0_gate_receipt_v1` schema (2B) and
    confirm `manifest_fingerprint` matches path token.
  - Build `sealed_by_id` from S0 receipt payload; require the policy + roster
    assets and ensure the sealed paths match dictionary catalog paths.
  - Validate `route_rng_policy_v1` and `virtual_edge_policy_v1` via schema packs
    (inline layer1 refs) and enforce stream semantics:
    * `streams.routing_edge.event_families.cdn_edge_pick` must have blocks=1,
      draws=1, draws_per_virtual=1.
    * `basis.key_basis` must be `[seed, parameter_hash, run_id]`,
      `counter_step_per_event`=1, `counter_wrap_policy`="abort".
  - Normalize virtual edge policy:
    * If `edges[]` present, treat as default edges.
    * Else use `default_edges` + `merchant_overrides` + `geo_metadata`.
    * Enforce weight sum ~=1.0, deterministic ordering by edge_id.
  - Load `s5_arrival_roster` (JSONL) and default `is_virtual=false` if missing,
    logging a single warning so S6 is backward compatible.
  - If `s6_edge_log` is enabled (policy flag + dictionary entry), require
    `s5_selection_log` and join on `(merchant_id, utc_timestamp, utc_day)` to
    fetch `tz_group_id` + `site_id`; abort if missing.
  - Generate RNG: use philox2x64-10 + derived key/counter, one draw per virtual
    arrival (non-virtual arrivals skipped). Emit `rng_event_cdn_edge_pick` and
    append trace rows via `RngTraceAccumulator`.
  - Append trace rows atomically to existing run-scoped `rng_trace_log` while
    leaving prior bytes intact; emit `rng_audit_log` only if missing.
  - Optionally emit `s6_edge_log` partitioned by `utc_day` with edge metadata,
    tz group/site IDs (when enabled).
  - Persist run-report JSON to `reports/layer1/2B/state=S6/...` and also log a
    STDOUT JSON summary.
- Implement `packages/engine/src/engine/cli/s6_edge_router_2b.py` mirroring
  other CLI entrypoints (run_id argument, validate_only optional if in spec).
- Update `makefile` with `segment2b-s6` target and include it in the `segment2b`
  aggregate. Ensure RUN_ID pick-up matches existing pattern.
- After code changes, run `make segment2b-s6 RUN_ID=<current>` and fix any
  failures, logging each decision in both logbook and this implementation map.

### Entry: 2026-01-16 19:10

Design element: 2B.S6 policy decoding details (country-weights) + edge-log join.
Summary: Resolve how to interpret `country_weights` in virtual_edge_policy_v1
without adding new runtime inputs, and confirm the join strategy for optional
s6_edge_log (tz_group_id/site_id provenance) so S6 remains deterministic and
spec-aligned.

Detailed reasoning and decision:
1) `country_weights` semantics in `virtual_edge_policy_v1`.
   - Constraint: S6 inputs are strictly run-scoped arrivals
     `{merchant_id, utc_timestamp, utc_day, is_virtual}` plus (optional)
     `s5_selection_log` for tz_group_id/site_id when the edge log is enabled.
     There is *no* per-arrival legal_country in the roster, and S6 is not
     supposed to read manifest_fingerprint plan tables just to infer it.
   - Spec requirement: policy must define a deterministic probability law over
     edges; either explicit per-edge weights, or a country->edge mapping that
     *induces* such a law.
   - Options considered:
     a) Treat `country_weights` as unsupported (hard-fail if present).
        -> Strict but would break if the policy uses country_weights later.
     b) Add a new input (merchant legal country) by reading S1 tables.
        -> Violates the "S6 does not read plan/egress" intent and adds
           unnecessary I/O.
     c) Interpret `country_weights` deterministically using the *edge's*
        `ip_country` as the key, i.e. weight = country_weights[ip_country]
        (if present), else weight = 0, then renormalize and enforce sum≈1±ε.
        -> Deterministic, uses only policy fields, and still yields a stable
           edge law; does not require extra inputs.
   - Decision: implement (c). If `country_weights` is present and the key
     for the edge's `ip_country` is missing or yields a non-positive total,
     abort with 2B-S6-031 (policy minima missing).

2) s6_edge_log join strategy (tz_group_id + site_id provenance).
   - Constraint: s6_edge_log row schema requires tz_group_id and site_id,
     but s5_arrival_roster does not carry them.
   - Options considered:
     a) Read s5_selection_log only if the edge log is enabled.
     b) Relax the s6_edge_log schema (not desired).
   - Decision: require s5_selection_log when edge logging is enabled; load
     per-day selection log rows into a keyed map by
     (merchant_id, utc_timestamp, utc_day) so S6 can attach tz_group_id and
     site_id deterministically. If a selection record is missing, abort with
     2B-S6-071 to keep the log lineage strict.

3) Implementation steps to reflect the above:
   - Extend `_normalize_edges` usage to accept `country_weights` by mapping
     edge.ip_country -> weight (deterministic rule), then enforce weight sum
     within EPSILON.
   - Add edge-log join cache keyed by utc_day with selection rows from
     s5_selection_log when `edge_log_enabled` and dictionary entry present.
- Log a story-style note once when `is_virtual` is missing in the roster
  (defaulting to False), since this affects bypass behaviour.

### Entry: 2026-01-16 23:24

Design element: Apply the S6 sealed-policy mismatch fix for run_id
`2b22ab5c8c7265882ca6e50375802b26`.
Summary: Execute the approved remediation (delete run-local S0 outputs, reseal,
rerun S6) so the sealed_inputs digest matches the updated policy files.

Detailed reasoning and decision:
1) The error is a sealed digest mismatch for `virtual_edge_policy_v1` in S6,
   which means sealed_inputs_2B still reflects the old policy digest.
2) Spec posture is to trust S0 seals, so the correct fix is to reseal rather
   than bypass validation. We avoid new run IDs to preserve the downstream
   run-local tables already produced in S1-S5.
3) Targeted deletion is safe because only S0 outputs encode sealed inputs:
   - `runs/<run_id>/data/layer1/2B/s0_gate_receipt/manifest_fingerprint=...`
   - `runs/<run_id>/data/layer1/2B/sealed_inputs/manifest_fingerprint=...`
4) After deletion, rerun S0 to rebuild sealed_inputs and then rerun S6; if any
   new validation issues arise, log them and fix incrementally.

### Entry: 2026-01-16 23:27

Design element: S6 rng_audit_log publish collision (2B-S6-080).
Summary: S6 attempted to publish `rng_audit_log` but the run already contains
an audit file from S5. The correct behaviour is to append a new audit record
if missing (or no-op if present), not to re-publish the file.

Detailed reasoning and decision:
1) The run already has `logs/layer1/2B/rng/audit/.../rng_audit_log.jsonl`
   written by S5. S6 calls `_atomic_publish_file` and fails because the file
   exists and differs.
2) Other states (1B S5/S6) use append semantics for rng_audit_log with a
   “present already” check keyed by run_id+seed+parameter_hash+fingerprint.
3) Decision: implement `_ensure_rng_audit` in S6 (and align S5) to:
   - check for an existing audit row matching the current run signature,
     return if found;
   - append the audit row if the file exists but the row is missing;
   - create the file if it does not exist.
4) This preserves resumability and avoids destructive deletes of audit logs.

### Entry: 2026-01-16 23:30

Design element: S6 sealed policy digest mismatch after policy edits.
Summary: S6 failed with 2B-S6-020 because `virtual_edge_policy_v1` sha256
in `sealed_inputs_2B` no longer matches the updated policy file.

Detailed reasoning and decision:
1) Diagnosis: S0 sealed `virtual_edge_policy_v1` earlier (digest A), but the
   policy JSON was later updated (digest B). S6 correctly blocks on mismatch.
2) Spec posture: S6 must trust S0 sealed inventory; therefore the fix is to
   re-run S0 to re-seal the policy (or start a new run if immutable outputs
   must be preserved).
3) Lowest-impact fix: delete only the S0 outputs for this run_id and manifest
   (run-local `s0_gate_receipt` + `sealed_inputs` folders) and re-run S0.
   This keeps the run-local arrival roster and downstream tables intact.
4) Execution plan:
   - Remove:
     `runs/<run_id>/data/layer1/2B/s0_gate_receipt/manifest_fingerprint=...`
     and
     `runs/<run_id>/data/layer1/2B/sealed_inputs/manifest_fingerprint=...`
   - Re-run `make segment2b-s0 RUN_ID=<current>` to reseal policies.
   - Re-run `make segment2b-s6 RUN_ID=<current>` to verify S6 green.

### Entry: 2026-01-16 23:33

Design element: Implement append-style rng_audit_log handling in 2B S5/S6.
Summary: Replaced atomic publish of rng_audit_log in S5/S6 with an
append-or-noop helper to avoid collisions when multiple states write to the
run-scoped audit log.

Detailed reasoning and decision:
1) Implemented `_ensure_rng_audit` in both runners to mirror 1B behaviour:
   - If a matching row already exists (run_id+seed+parameter_hash+fingerprint),
     log and return.
   - If file exists but row missing, append.
   - If file missing, create it.
2) Removed audit tmp file write and `_atomic_publish_file` calls for
   rng_audit_log; kept audit payload validation and structure unchanged.
3) Next step: rerun `make segment2b-s6 RUN_ID=...` to confirm S6 green without
   deleting existing audit logs.

### Entry: 2026-01-16 23:36

Design element: Validate S6 rerun after audit-log append fix.
Summary: Reran S0 to reseal policies and reran S6; S6 completed with
`rng_audit_log already contains audit row` and no publish collision.

Detailed reasoning and decision:
1) S0 reseal confirmed `virtual_edge_policy_v1` digest updated in
   sealed_inputs_2B for the current run_id.
2) S6 completed successfully without deleting the existing audit log, which
   validates the append/no-op behaviour and preserves resumability.

### Entry: 2026-01-16 23:38

Design element: Normalize s5_arrival_roster to include `is_virtual`.
Summary: Add `is_virtual` to the run-scoped arrival roster so downstream S6
can read explicit virtual flags instead of defaulting.

Detailed reasoning and decision:
1) Current roster rows only carry `{merchant_id, utc_timestamp, utc_day}`.
   S6 already accepts missing `is_virtual` but logs a warning and treats
   all rows as non-virtual. For now, we want explicit `is_virtual=false`
   until the upstream 5B owner provides true virtual flags.
2) Since the roster is a run-scoped input sealed by S0, we must edit the
   roster file and then re-run S0 to re-seal its digest (avoid mismatch in S5).
3) Implementation plan:
   - Add a small script to rewrite the JSONL roster in-place, inserting
     `is_virtual` when missing (default false), while preserving existing
     `is_virtual` values if already present.
   - Add a Makefile helper target to run the script for a given RUN_ID,
     reading `seed` + `parameter_hash` from `run_receipt.json`.
   - After normalization, rerun `make segment2b-s0 RUN_ID=<run_id>` to reseal.

### Entry: 2026-01-16 23:40

Design element: Reseal S0 after roster normalization (receipt collision).
Summary: S0 reseal failed due to existing `s0_gate_receipt_2B` and
`sealed_inputs_2B` outputs; remove the run-local partitions and rerun S0.

Detailed reasoning and decision:
1) The roster digest changed, so S0 must emit a new receipt + sealed_inputs.
2) Atomic publish fails if a non-identical receipt already exists (2B-S0-080).
3) Spec posture allows deleting run-local S0 outputs to reseal the same run_id.
4) Plan: remove `data/layer1/2B/s0_gate_receipt/manifest_fingerprint=...` and
   `data/layer1/2B/sealed_inputs/manifest_fingerprint=...`, then rerun S0.

### Entry: 2026-01-16 23:41

Design element: Execute roster normalization + S0 reseal.
Summary: Normalized the run-scoped roster to include `is_virtual=false` and
successfully resealed S0 for the current run_id.

Detailed reasoning and decision:
1) Ran `scripts/normalize_arrival_roster.py` via Makefile to add `is_virtual`
   to all roster rows (default false).
2) Deleted the S0 receipt + sealed_inputs partitions to allow S0 to publish
   updated digests.
3) Reran `make segment2b-s0 RUN_ID=2b22ab5c8c7265882ca6e50375802b26` and
   confirmed S0 PASS with updated roster digest.

### Entry: 2026-01-16 23:48

Design element: Rebuild missing s5_arrival_roster and ensure it carries
`is_virtual`.
Summary: Extend the roster normalizer to generate a roster when missing,
using upstream `site_locations` and a fixed UTC day, and include
`is_virtual=false` in each row.

Detailed reasoning and decision:
1) The run-local roster file was missing, causing S5 to fail with
   2B-S5-020 required_asset_missing even though S0 ran.
2) The spec allows generating a run-scoped roster from upstream sealed inputs
   (site_locations) for standalone/batch runs; this avoids dependencies on
   S1 outputs.
3) Implementation plan:
   - If the roster file is absent, scan `site_locations` parquet (merchant_id
     only), build one row per merchant_id with `utc_day=2024-01-01`,
     `utc_timestamp=2024-01-01T00:00:00.000000Z`, and `is_virtual=false`.
   - Write JSONL to the dictionary path; then rerun S0 to reseal the digest.

### Entry: 2026-01-16 23:49

Design element: Avoid polars streaming panic when scanning site_locations.
Summary: Switch roster generation to non-streaming `read_parquet` to avoid
the deprecated streaming engine failure on Parquet.

Detailed reasoning and decision:
1) `pl.scan_parquet(...).collect(streaming=True)` panics with
   "Parquet no longer supported for old streaming engine" in the current
   Polars version.
2) Dataset size for `site_locations` is manageable for a one-time unique
   merchant_id pass in this run; prefer correctness over streaming.
3) Use `pl.read_parquet(site_paths, columns=["merchant_id"]).unique()` to
   collect merchant_ids deterministically.

### Entry: 2026-01-16 23:55

Design element: Resolve S5 created_utc mismatch after resealing S0.
Summary: Resealing S0 updates `created_utc`, so downstream S1–S4 outputs must
be regenerated to match the new receipt timestamp before S5 can proceed.

Detailed reasoning and decision:
1) S5 validates that upstream run-local outputs share the same `created_utc`
   as the current S0 receipt. After resealing S0, older S1 outputs now fail
   the check (2B-S5-086).
2) Correct fix is to rerun S1-S4 for the same run_id after the new S0 so their
   `created_utc` matches the receipt.
3) Plan: remove run-local `data/layer1/2B/s1_site_weights`, `s2_alias_*`,
   `s3_day_effects`, `s4_group_weights` partitions and rerun S1-S4, then S5.

### Entry: 2026-01-17 00:32

Design element: S0 receipt determinism on re-run (2B-S0-080).
Summary: Re-running `segment2b` failed in S0 because the existing
`s0_gate_receipt_2B.json` differed only by `verified_at_utc`. We need a stable
timestamp so write-once idempotence can pass for the same run_id.

Detailed reasoning and decision:
1) `_atomic_publish_file` correctly rejects non-identical outputs, but the
   receipt payload uses `utc_now_rfc3339_micro()` for `verified_at_utc`, so
   every re-run produces new bytes even when inputs are unchanged.
2) For a fixed run_id, the determinism contract should allow a re-run to
   detect "identical output already exists" and continue, not fail.
3) Use `run_receipt.created_utc` as the receipt’s `verified_at_utc` to keep
   deterministic outputs tied to the run_id. This timestamp is already stable
   and available in `run_receipt.json`, and still satisfies the schema.
4) Fallback: if `created_utc` is missing (unexpected), use the current time to
   avoid crashing, but log a WARN so we know determinism may be lost.
5) After implementing, rerun `make segment2b` to confirm S0 idempotence and
   allow the pipeline to proceed to S5/S6 without resealing errors.

### Entry: 2026-01-17 00:35

Design element: Preserve existing verified_at_utc when receipt already exists.
Summary: The prior S0 receipt was created before the deterministic timestamp
change, so its `verified_at_utc` differs from the new deterministic value.
We will reuse the existing receipt’s timestamp when the file exists to keep
byte-for-byte idempotence without manual cleanup.

Detailed reasoning and decision:
1) The current error persists because the old receipt on disk still has the
   original `verified_at_utc` (from `utc_now`), so the newly generated receipt
   differs even after anchoring to `run_receipt.created_utc`.
2) For resumability, a re-run with the same run_id should treat the existing
   receipt as authoritative if all other fields match. Reusing its timestamp
   is the minimum change that preserves the write-once contract.
3) Plan: resolve `receipt_path` before constructing the payload; if the file
   exists and parses, read `verified_at_utc` and use that value in the new
   payload. Then the identical-output check passes unless other fields changed.
4) If parsing fails, keep the deterministic timestamp and let the mismatch
   surface as an error (corrupted output should not be silently overwritten).

### Entry: 2026-01-17 01:00

Design element: S5 RNG log re-run blocked by non-identical outputs.
Summary: `2B-S5-080` triggered because prior RNG log files already existed for
the same run_id, and the new outputs differed. To preserve the write-once
contract without overwriting, we cleared the run-local log files and re-ran S5.

Detailed reasoning and decision:
1) `_atomic_publish_file` is intentionally strict: it fails if a file already
   exists but its hash differs. This is the right default to protect
   determinism and avoid silent overwrites.
2) The existing RNG log files were produced by an earlier S5 run with different
   inputs (policy/roster revisions). For the same run_id, that makes the new
   outputs non-identical, so the publish correctly aborted.
3) Since the intended behaviour for reruns is to *explicitly* clear outputs
   when inputs changed, the safest fix is to delete the run-local RNG log files
   for `alias_pick_group`, `alias_pick_site`, and `rng_trace_log` and then
   re-run S5. This preserves the write-once contract while allowing a clean
   regeneration.
4) After clearing the logs, re-run `segment2b-s5` and `segment2b-s6`. Both
   states completed successfully, confirming the log cleanup was sufficient.

### Entry: 2026-01-17 06:13

Design element: Deterministic mixed `is_virtual` assignment in arrival roster.
Summary: User requested a deterministic 5–10% virtual mix and asked to lock
the percentage. I will default to 10% virtual and encode it directly into the
arrival roster generation so S6 is exercised without external 5B inputs.

Detailed reasoning and decision:
1) The current roster generator writes `is_virtual=false` for every merchant,
   which yields zero virtual arrivals and makes S6 a no-op.
2) We need a deterministic, repeatable rule to avoid ad-hoc overrides and to
   keep reruns stable for the same seed. Using a hash of `(merchant_id, seed)`
   provides a consistent partition without introducing randomness.
3) Pick a fixed 10% threshold so S6 has enough volume to validate, without
   dominating the sample. This is configurable in code but defaults are locked
   to 10% unless explicitly overridden.
4) Implementation plan: update `scripts/normalize_arrival_roster.py` to compute
   `is_virtual` per row using `sha256(f"{merchant_id}:{seed}") % 100 < 10`,
   and apply the same rule both when generating a new roster and when filling
   missing `is_virtual` fields in an existing roster.
5) After regeneration, rerun S0 to reseal the roster (if needed) and rerun
   S5/S6 to confirm virtual arrivals are routed.

### Entry: 2026-01-17 06:14

Design element: Implement deterministic 10% virtual assignment in roster.
Summary: Updated the arrival roster normalization script to assign `is_virtual`
using a hash of `(merchant_id, seed)` with a fixed 10% threshold.

Detailed reasoning and decision:
1) Implemented `_virtual_bucket` using SHA-256 and `% 100` to ensure stable,
   reproducible bucketing across runs for the same seed.
2) Locked `VIRTUAL_PERCENT = 10` in the script; no CLI override to keep the
   default consistent unless code is changed intentionally.
3) Applied the rule in two paths:
   - When generating a new roster from `site_locations`.
   - When normalizing an existing roster missing `is_virtual`.
4) Kept existing `is_virtual` values untouched to preserve manual overrides
   or upstream-provided flags.

## S7 - Audits & CI gate (S7.*)

### Entry: 2026-01-17 06:20

Design element: S7 audit/CI gate pre-implementation review (contracts + evidence).
Summary: Reviewed the S7 expanded spec and 2B contract surfaces. S7 is RNG-free,
reads only Dictionary-resolved inputs (S2/S3/S4 + sealed policies, and optional
S5/S6 logs + RNG evidence when present), and emits a single authoritative
`s7_audit_report` at `[seed, manifest_fingerprint]` with write-once/atomic
publish and stdout-only run-report.

Detailed reasoning and decisions:
1) Authorities and inputs are explicit. S7 must enforce S0 gate evidence first,
   then read only Dictionary IDs at exact partitions:
   - S2/S3/S4 at `[seed, manifest_fingerprint]`.
   - Policies token-less by S0-sealed `path + sha256_hex`.
   - Optional S5/S6 logs at `[seed, parameter_hash, run_id, utc_day]`, and only
     then read Layer-1 RNG evidence at `[seed, parameter_hash, run_id]`.
2) Output identity is strict: `s7_audit_report` is the only authoritative
   output, partitioned `[seed, manifest_fingerprint]`, with path↔embed equality
   and `created_utc` equal to S0 `verified_at_utc`. Publish is write-once with
   atomic move; re-emit allowed only if byte-identical.
3) Required checks in the spec include:
   - S2 index/blob schema + header/blob digest parity + policy echo.
   - S3/S4 day-grid equality, gamma echo, and per-merchant/day sum(p_group)=1.
   - Optional logs: arrival ordering, partition/lineage checks, and RNG evidence
     reconciliation (S5: 2 events/selection; S6: 1 event/virtual).
4) Deterministic samples are mandated (bounded K=32). Proposed selection is
   lowest-lex merchant_id/utc_day for reproducibility without extra RNG.
5) Open confirmations for the user before coding:
   - Optional logs: treat absence as SKIP (no WARN) vs WARN? Spec calls them
     optional, so default is SKIP unless you want explicit WARNs.
   - Run-report persistence: spec says STDOUT-only; do you want a persisted
     file copy (non-authoritative) or strict stdout-only to reduce I/O?
   - inputs_digest scope: echo only S0-sealed S2/S3/S4 + policies (strict),
     or also include optional logs if present (even though they are not sealed)?
   - RNG evidence: if S5/S6 logs exist but rng_audit_log or rng_trace_log is
     missing, do we hard-fail (spec-leaning) or downgrade to WARN?

### Entry: 2026-01-17 06:22

Design element: S7 confirmation decisions before implementation.
Summary: Locked in the S7 decisions for optional logs, run-report, inputs_digest
scope, and RNG evidence handling so the implementation follows a single path.

Detailed reasoning and decision:
1) Optional logs (S5/S6): treat their absence as SKIP (no WARN), because the
   dictionary marks them optional and the spec does not mandate presence.
   If logs are present, all evidence checks must run; if absent, skip the
   related validators without warning.
2) Run-report emission: STDOUT-only JSON diagnostic (no persisted copy), to
   align with S7's observability section and avoid extra non-authoritative
   artefacts.
3) inputs_digest scope: include only S0-sealed inputs (S2/S3/S4 + policies).
   Optional logs are not sealed; record them in checks/metrics instead of
   digest to avoid mixing sealed and non-sealed evidence.
4) RNG evidence: if S5/S6 logs are present but rng_audit_log or rng_trace_log
   is missing, hard-fail. Reconciliation is required to validate draw budgets
   and counters; passing without evidence would violate the audit gate.

### Entry: 2026-01-17 06:35

Design element: S7 audit/CI gate implementation plan (runner + CLI + Makefile).
Summary: Implement `seg_2B/s7_audit` runner that enforces S7 audit checks and
publishes `s7_audit_report` (stdout-only run-report), then wire CLI + Makefile
target. Preserve deterministic sampling and write-once semantics.

Detailed reasoning and decision (plan before coding):
1) Inputs + authorities (strict):
   - Read S0 receipt at `[manifest_fingerprint]` to anchor `created_utc` and
     validate gate lineage. Use `run_receipt.created_utc` to enforce deterministic
     timestamps. Use S0 `sealed_inputs` to identify sealed assets and their
     digests.
   - Resolve S2/S3/S4 datasets at `[seed, manifest_fingerprint]` using the
     Dictionary + `RunPaths` (no ad-hoc paths). Resolve policies by sealed path +
     sha256 (token-less).
   - Optional logs: `s5_selection_log` and `s6_edge_log` at
     `[seed, parameter_hash, run_id, utc_day]` only if present. If either log
     exists, require RNG evidence logs (`rng_trace_log`, `rng_audit_log`) at
     `[seed, parameter_hash, run_id]` and hard-fail if missing.
2) Core checks to implement:
   - S2 alias index + blob:
     a) Validate index JSON schema + header echo vs `alias_layout_policy_v1`
        (layout_version, endianness, alignment_bytes, quantised_bits).
     b) Validate blob digest (sha256) equals header + sealed policy digest.
     c) Validate merchants_count, row checksum hex pattern, and bounds for
        offset+length within blob_size_bytes.
     d) Deterministic sample K<=32 merchants by lowest merchant_id; for each
        sample, read slice header (u32 sites + prob_qbits + reserved) and decode
        alias probabilities. Recompute checksum and compare with row checksum.
        Compute `p_hat` from prob_q + alias and ensure `abs(sum(p_hat)-1.0)`
        <= `quantisation_epsilon`. Record `alias_decode_max_abs_delta` as the
        max `abs(sum(p_hat)-1.0)` across samples. NOTE: Spec mentions
        `max|p_hat - p_enc|`, but `p_enc` is not available at S7 without
        re-deriving original weights; we will log this assumption in the
        run-report and implementation map if needed.
   - S3/S4 coherence:
     a) Ensure day grid equality between S3 and S4 (same merchants, utc_day,
        tz_group_id). Use sorted keys to compare counts and detect drift.
     b) Ensure S4.gamma == S3.gamma per row (exact float match, or with
        epsilon? Use exact match to respect determinism; log count + samples).
     c) For each merchant/day, verify sum(p_group)=1.0 within EPSILON and
        report max_abs_mass_error_s4.
   - Optional logs:
     a) If `s5_selection_log` exists, validate schema, enforce
        manifest_fingerprint + created_utc echo, and ensure per-merchant order
        is non-decreasing by utc_timestamp (no reordering within a day). Count
        selections; expected draws = 2 * selections.
     b) If `s6_edge_log` exists, validate schema, enforce manifest_fingerprint +
        created_utc echo, and ensure timestamps non-decreasing. Count virtual
        arrivals; expected draws = 1 * virtual arrivals.
     c) If RNG evidence logs exist, reconcile event counts vs expected draws and
        ensure RNG trace/audit logs cover the counter space referenced by the
        logs (fail if missing).
3) Output/reporting plan:
   - Emit a narrative story header log at start describing objective, gated
     inputs (S0 receipt, S2/S3/S4, policies, optional logs), and outputs.
   - Emit progress logs for long loops (sample decoding, S3/S4 scans, log
     validation) with elapsed/rate/ETA.
   - Produce `s7_audit_report` JSON at
     `[seed, manifest_fingerprint]` with `created_utc` echoing S0
     `verified_at_utc`, `inputs_digest` containing only sealed assets, and
     `checks/metrics/summary` per spec. Use write-once atomic publish (fail
     if existing non-identical).
   - Emit stdout-only run-report JSON (no persisted run-report file), with
     diagnostics for any skipped optional checks.
4) Wiring plan:
   - Create `packages/engine/src/engine/layers/l1/seg_2B/s7_audit/runner.py`
     and `__init__.py`.
   - Add CLI `packages/engine/src/engine/cli/s7_audit_2b.py`.
   - Update `makefile` to add `segment2b-s7` target and include in `segment2b`.
5) Testing/resumability:
   - Run `make segment2b-s7 RUN_ID=...` and re-run to verify write-once/atomic
     behaviour (idempotent when identical). On failure, log error codes and
     sample keys in S7 run-report (stdout).
   - Verify that optional logs are SKIP (not WARN) when absent and that RNG
     evidence missing triggers a hard fail when logs are present.

### Entry: 2026-01-17 07:00

Design element: Continue S7 implementation after partial file creation.
Summary: The S7 runner file is incomplete (stops after edge-log validation).
I will finish the remaining validations (RNG evidence, site-timezone mapping),
emit the audit report, and wire CLI/Makefile as originally planned.

Detailed reasoning and decision:
1) The current `runner.py` stops immediately after the optional S5/S6 log
   validation block. This leaves out mandatory checks in the S7 expanded spec:
   - RNG evidence reconciliation (V-12/V-13/V-14/V-16/V-17).
   - Site-timezone/edge-policy mapping checks (V-15).
   - Audit report creation and atomic publish (V-18).
2) No change to the earlier decisions. We will finish the runner using the
   exact checks laid out in the 06:35 plan, without changing the scope or
   tolerances.
3) After completing the runner logic, add the CLI wrapper and Makefile target.
   Both are direct wiring steps and do not alter any model behavior.
4) Once wiring is done, run `make segment2b-s7` to validate that the report
   publishes and reruns are idempotent. Any adjustments that arise will be
   logged in new entries, not rewrites.

### Entry: 2026-01-17 07:16

Design element: Finish 2B.S7 audit runner and wire CLI/Makefile.
Summary: Complete the S7 runner logic (RNG evidence reconciliation, mapping
checks, audit report emission) and add CLI + Makefile wiring, keeping the
implementation deterministic and streaming-friendly.

Detailed plan and reasoning (before coding):
1) Evidence source and authority audit.
   - Inputs are strictly Dictionary-resolved: S2/S3/S4 at
     `[seed, manifest_fingerprint]`, policies via sealed S0 path+digest,
     optional S5/S6 logs at `[seed, parameter_hash, run_id, utc_day]`,
     RNG core logs at `[seed, parameter_hash, run_id]`.
   - Shape authorities: 2B pack for S2/S3/S4 + policy + trace rows, Layer-1
     pack for rng_audit_log + rng_trace_log + event families.
   - Decision: do NOT infer any paths; require presence through dictionary
     entries and S0 sealed inventory, and record failures via 2B-S7 codes.

2) Streamed JSONL processing to avoid large in-memory loads.
   - Selection/edge log validation currently uses read_text(). Replace with a
     streaming iterator to reduce memory and improve performance.
   - Ensure progress logs (elapsed, rate, ETA) are emitted through the
     existing ProgressTracker while iterating.

3) RNG evidence checks (V-13/V-14/V-16).
   - If optional logs exist, require rng_audit_log + rng_trace_log + event logs.
   - Validate event log rows against Layer-1 schemas; enforce rng_stream_id
     matches route_rng_policy_v1 for `alias_pick_group`, `alias_pick_site`,
     `cdn_edge_pick`.
   - Counter checks:
     - Per-event: after > before; if after < before => 2B-S7-404 (wrap),
       if after == before or non-monotone vs prior => 2B-S7-403.
     - Per-log monotone: maintain last_after per log to ensure strict increase.
   - Budget checks:
     - S5: group events count == selection count and site events count ==
       selection count (2 events per selection).
     - S6: edge event count == virtual arrivals from s6_edge_log
       (1 event per virtual).
   - Trace reconciliation:
     - Parse rng_trace_log and extract final draws_total/events_total per
       (module, substream_label); verify draws_total == events_total per
       substream.
     - Compute draws_expected = 2*selections + virtuals and compare to the
       sum of per-substream draws_total; fail 2B-S7-402 on mismatch.
   - Rationale: this matches the spec’s “two per selection / one per virtual”
     rule and enforces counter monotonicity without requiring expensive joins.

4) Mapping/attribute checks (V-15).
   - Build a `site_timezones` lookup from 2A (merchant_id, site_id -> tzid).
   - For selection log sample rows, recompute site_id via low64 hash and
     assert tz_group_id matches the 2A tzid (else 2B-S7-410).
   - For edge log sample rows, ensure edge_id exists in virtual_edge_policy_v1
     and record missing attributes as 2B-S7-411.
   - Use a bounded sample (MAX_SAMPLE) to keep runtime predictable while
     still providing coverage.

5) Audit report creation + atomic publish (V-17/V-18).
   - Build `s7_audit_report` with path↔embed equality and created_utc anchored
     to S0 receipt `verified_at_utc`.
   - Include `catalogue_resolution`, `inputs_digest` (S2/S3/S4 + policies),
     `checks[]`, `metrics`, and `summary` per schema.
   - Write to run tmp and atomically publish to
     `data/layer1/2B/s7_audit_report/seed=.../manifest_fingerprint=...`.
   - Idempotent re-run: if bytes are identical, skip; otherwise fail with
     2B-S7-502.

6) Wiring and test steps.
   - Add CLI wrapper `engine.cli.s7_audit_2b` and Makefile target
     `segment2b-s7`, include in `segment2b`.
   - Run `make segment2b-s7 RUN_ID=...` to verify report emission and ensure
     reruns are idempotent; log any failures + fixes in new entries.

Logging intent (story-first):
   - Add a state story header log summarizing objective, gated inputs, and
     outputs.
   - Emit phase logs for S2/S3/S4 validation, RNG evidence checks, mapping
     checks, and report emission so the operator can follow the flow without
     consulting the spec.

### Entry: 2026-01-17 07:29

Design element: Implemented the remaining S7 audit logic + wiring.
Summary: Completed RNG evidence reconciliation, mapping checks, audit report
emission, and CLI/Makefile wiring for 2B.S7. This converts the previously
partial runner into a spec-complete state gate.

Implementation details (what changed and why):
1) Streaming JSONL iteration:
   - Added `_iter_jsonl_rows` and `_resolve_jsonl_paths` helpers to stream
     JSONL logs line-by-line instead of `read_text()`. This avoids loading
     full logs into memory and keeps progress logs responsive.
   - Updated selection/edge log loops to use streaming iteration with
     explicit JSON decode failure handling (2B-S7-400).

2) RNG evidence reconciliation (V-13/V-14/V-16):
   - Added a shared `_scan_event_log` path that validates Layer-1 event log
     schema, enforces stream id + substream_label, and checks counter monotonicity
     and wrap detection (2B-S7-403/404).
   - Required event log counts to match selection/virtual counts (2B-S7-402).
   - Parsed `rng_trace_log` for per-(module,substream) totals, enforced
     draws_total == events_total per substream, and reconciled totals to
     expected draws across S5/S6 (2B-S7-402).
   - Verified `rng_audit_log` presence and schema (evidence-only, RNG-free).

3) Mapping & attribute checks (V-15):
   - Built a `site_timezones` index by recomputing site_id from
     (merchant_id, legal_country_iso, site_order) and compared against
     selection log samples (2B-S7-410).
   - Built an edge_id lookup from `virtual_edge_policy_v1` (edges, defaults,
     merchant_overrides) and asserted edge_id presence for edge log samples
     (2B-S7-411).

4) Audit report (V-17/V-18):
   - Constructed `s7_audit_report` with path↔embed equality, created_utc
     anchored to S0 verified_at_utc, `inputs_digest` from sealed inputs, and
     required metrics/summary fields.
   - Validated report against `schemas.2B.yaml#/validation/s7_audit_report_v1`
     and published atomically with idempotent re-emit handling.

5) Wiring:
   - Added CLI `engine.cli.s7_audit_2b`.
   - Updated Makefile with `SEG2B_S7_CMD`, `segment2b-s7` target, and added
     S7 to `.PHONY` and the `segment2b` chain.

Next verification steps:
   - Run `make segment2b-s7 RUN_ID=...` and confirm report emission.
   - Re-run to validate write-once idempotence and check the run-report JSON.

### Entry: 2026-01-17 07:40

Design element: Rerun 2B end-to-end with resealed inputs after S5 failures.
Summary: S5 failed due to `required_asset_missing` and S7 failed because S2/S3/S4
were not present in `sealed_inputs_2B`. We'll remove run-local 2B outputs and
rerun `make segment2b` so S0 reseals and S1–S6 regenerate under the same
manifest_fingerprint, then re-run S7.

Plan (before execution):
1) Determine the latest run_id under `runs/local_full_run-5` and use that
   run_id for cleanup and rerun unless you specify otherwise.
2) Remove run-local 2B outputs only (leave other segments intact):
   - `runs/<run_id>/data/layer1/2B`
   - `runs/<run_id>/logs/layer1/2B`
   - `runs/<run_id>/reports/layer1/2B`
3) Rerun `make segment2b` to reseal S0 and regenerate S1-S6, then run S7.
4) If any state fails, append a new entry with the error, options considered,
   and the chosen fix before changing code.

### Entry: 2026-01-17 08:19

Design element: Rerun 2B with run-local tmp cleanup to validate BM ambiguity
resolution under a same-run_id reseal.

Summary: User believes stale tmp directories may be causing reuse of old
artifacts and masking a real BM ambiguity issue even after deleting 2B outputs.
We will clear the run-local tmp staging folder for the same run_id, reseal S0,
and rerun `segment2b` end-to-end to confirm whether the BM failure persists.

Plan (before execution):
1) Confirm run_id = `2b22ab5c8c7265882ca6e50375802b26` (user request: same id).
2) Keep run-local 2B outputs already removed; do not touch other segments.
3) Remove run-local staging only:
   - `runs/<run_id>/tmp/*` (delete all staging subfolders).
4) Rerun `make segment2b RUN_ID=<run_id>` to reseal S0 with current
   `tz_overrides` + inputs and regenerate S1-S7.
5) If S1 still fails with 2A-S1-055, treat it as a logic/input issue (not
   stale tmp), capture the failing key, and only then consider code/policy
   changes with a new detailed entry.

### Entry: 2026-01-17 08:24

Design element: Handle `s5_arrival_roster` missing after reseal rerun.

Summary: After clearing run-local tmp and rerunning `make segment2b` with the
same run_id, S5 fails with `2B-S5-020 required_asset_missing` for
`s5_arrival_roster`. S0 logs that the optional arrival roster is missing,
so S5 cannot proceed. This is unrelated to the BM ambiguity; we must generate
the run-scoped roster and reseal S0 so it is included in `sealed_inputs_2B`.

Plan (before execution):
1) Generate/normalize the roster using the existing Make target:
   `make segment2b-arrival-roster RUN_ID=2b22ab5c8c7265882ca6e50375802b26`.
   This uses `scripts/normalize_arrival_roster.py` to emit
   `data/layer1/2B/s5_arrival_roster/seed=42/parameter_hash=.../run_id=.../arrival_roster.jsonl`.
2) Rerun `make segment2b RUN_ID=2b22ab5c8c7265882ca6e50375802b26` so S0 seals
   `s5_arrival_roster` and S5/S6/S7 can proceed.
3) If S5 still fails, capture the exact validator code and add a new entry
   before adjusting code or policy.

### Entry: 2026-01-17 08:25

Design element: Reseal S0 after roster generation without losing the roster.

Summary: After generating `s5_arrival_roster`, rerunning `segment2b` failed in
S0 with `2B-S0-080` (atomic publish violation) because S0 outputs already
exist for this run_id. We need to delete S0/S1-S4 outputs while **preserving**
`s5_arrival_roster`, then rerun S0 so it can seal the roster.

Plan (before execution):
1) Enumerate `runs/<run_id>/data/layer1/2B` and remove all state outputs
   **except** `s5_arrival_roster/` (keep the roster JSONL intact).
2) Also remove `runs/<run_id>/logs/layer1/2B` and
   `runs/<run_id>/reports/layer1/2B` to ensure a clean reseal.
3) Rerun `make segment2b RUN_ID=2b22ab5c8c7265882ca6e50375802b26`.
4) If S0 still fails, inspect `_atomic_publish_file` write-once guard and
   confirm no stale `s0_gate_receipt_2B` / `sealed_inputs_2B` remain.

### Entry: 2026-01-17 08:31

Design element: S7 should not require S2 outputs to be in `sealed_inputs_2B`.

Summary: After resealing with `s5_arrival_roster`, the run reaches S7 but fails
with `2B-S7-020 sealed_asset_missing` for `s2_alias_index`. S2 outputs are
run-local artefacts, not S0-sealed inputs, so S7 should resolve them from the
run-local dataset paths (dictionary + registry) and verify existence/schema
instead of requiring them in `sealed_inputs_2B`.

Plan (before execution):
1) Adjust S7 to treat S2/S3/S4 artefacts as **outputs**, not sealed inputs:
   - Resolve `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`,
     `s4_group_weights` via run-local paths.
   - Validate path existence + schema refs (path↔embed checks) but do not
     require them in `sealed_inputs_2B`.
2) Keep `sealed_inputs_2B` checks for true inputs/policies only (S0 receipt,
   policies, optional routing logs).
3) Re-run `make segment2b-s7 RUN_ID=2b22ab5c8c7265882ca6e50375802b26` and
   confirm the audit report publishes.

### Entry: 2026-01-17 08:32

Implementation update: S7 output resolution fix.

Changes applied:
1) Added `_require_output_asset(...)` in
   `packages/engine/src/engine/layers/l1/seg_2B/s7_audit/runner.py` to resolve
   run-local outputs (S2/S3/S4) without requiring them in `sealed_inputs_2B`.
2) Swapped S2/S3/S4 asset resolution to `_require_output_asset` and kept
   `_require_sealed_asset` for policies only.
3) Removed the `sealed_blob_digest_mismatch` check for alias blob since there
   is no sealed digest for output artefacts; still enforce
   `index_payload.blob_sha256` match.
4) Updated the narrative log to reflect “sealed inputs for policies; outputs for
   S2/S3/S4”.

Next step:
- Re-run `make segment2b-s7 RUN_ID=2b22ab5c8c7265882ca6e50375802b26` to confirm
  the audit report passes with run-local S2/S3/S4 outputs.

### Entry: 2026-01-17 08:34

Design element: Fix S7 schema validation for `plan/s2_alias_index` refs.

Summary: S7 now reaches alias index validation but fails because the schema
references `schemas.layer1.yaml#/$defs/rfc3339_micros` and `_validate_payload`
did not receive the layer-1 ref pack for this schema. We need to pass the same
`ref_packs` mapping used for the S0 receipt validation.

Plan (before execution):
1) Update the `_validate_payload` call for `plan/s2_alias_index` to pass
   `{"schemas.layer1.yaml#/$defs/": schema_layer1}` so Draft202012Validator can
   inline external refs.
2) Re-run `make segment2b-s7 RUN_ID=2b22ab5c8c7265882ca6e50375802b26`.

### Entry: 2026-01-17 08:35

Implementation update: S7 alias-index schema validation refs.

Changes applied:
- Updated `_validate_payload` invocation for `plan/s2_alias_index` to pass
  `{"schemas.layer1.yaml#/$defs/": schema_layer1}` so external refs are
  inlined and Draft202012Validator can resolve `rfc3339_micros`.

Next step:
- Re-run `make segment2b-s7 RUN_ID=2b22ab5c8c7265882ca6e50375802b26`.

### Entry: 2026-01-17 08:36

Design element: Fix indentation error introduced in S7 after ref-pack update.

Summary: The rerun of `segment2b-s7` now fails with an `IndentationError` at
`runner.py` line ~693. The prior change inserted a `_validate_payload(...)`
call after a `try:` but did not indent it, so Python expects an indented block.
We need to correct the indentation so the try/except captures the validation.

Plan (before execution):
1) Open `packages/engine/src/engine/layers/l1/seg_2B/s7_audit/runner.py`
   around the `try:` block near `_validate_payload(plan/s2_alias_index)`.
2) Indent the `_validate_payload` call (and any adjacent statements) so it is
   inside the intended `try:` block.
3) Keep the existing exception handling intact (do not change semantics).
4) Re-run `make segment2b-s7 RUN_ID=2b22ab5c8c7265882ca6e50375802b26`.

### Entry: 2026-01-17 08:37

Design element: Resolve S7 `slice_header_qbits_mismatch` (header=32 vs policy=24).

Summary: S7 now reaches the alias slice checks but fails with
`2B-S7-205 slice_header_qbits_mismatch` for a merchant. The alias index header
quantised bits read from S2 output is 32, while the sealed alias layout policy
declares 24. This means S2 outputs and the sealed policy are out of sync
(likely S2 was generated with a different policy revision or S2 is not honoring
the current `quantised_bits` field).

Plan (before execution):
1) Inspect S2 alias index writer (S2 runner) to see how `quantised_bits` is
   derived and written into the header for each slice.
2) Confirm the sealed alias layout policy for this run_id:
   - policy file path from `sealed_inputs_2B` (S0 receipt),
   - expected `quantised_bits` (currently 24).
3) Determine whether the mismatch is due to stale S2 outputs:
   - If S2 uses the policy value but outputs were generated before policy edits,
     delete run-local S2/S3/S4 outputs and rerun `make segment2b` so S2 rebuilds
     with the current policy (no code change).
   - If S2 is hardcoding or deriving 32 incorrectly, update S2 to use the
     policy value, then rerun S2+.
4) Add a narrative log in S2 when writing the alias header stating which
   `quantised_bits` is used (policy vs override) to make future audits clear.
5) Re-run `make segment2b-s7 RUN_ID=2b22ab5c8c7265882ca6e50375802b26`.

### Entry: 2026-01-17 08:38

Design element: Align S7 slice header qbits check to alias record_layout.prob_qbits.

Summary: Inspection of S2 alias table generation shows the slice header embeds
`prob_qbits` from `policy.record_layout` (default 32), while `quantised_bits`
is the grid size used elsewhere. S7 currently compares `header_qbits` against
`policy.quantised_bits`, which incorrectly flags a mismatch when
`quantised_bits != prob_qbits` (e.g., 24 vs 32). The fix is to compare
`header_qbits` to `record_layout.prob_qbits` and to use `prob_qbits` for
decoding `prob_q` values in the audit sample.

Plan (before execution):
1) In S7, derive `record_layout = alias_policy_payload.get("record_layout", {})`
   and `prob_qbits = int(record_layout.get("prob_qbits") or 0)` with validation.
2) Replace the `header_qbits != policy_quantised_bits` check with
   `header_qbits != prob_qbits` and keep the same error code.
3) Use `prob_qbits` (not `policy_quantised_bits`) for `q_scale` when decoding
   the alias slice probabilities.
4) Re-run `make segment2b-s7 RUN_ID=2b22ab5c8c7265882ca6e50375802b26` and
   confirm the audit report publishes.

### Entry: 2026-01-17 08:39

Design element: Avoid Polars streaming panic when collecting S3/S4 key diffs.

Summary: S7 now progresses to the S3/S4 key reconciliation but panics with
`Parquet no longer supported for old streaming engine` when calling
`collect(streaming=True)`. This appears to be a Polars runtime limitation for
lazy parquet scans in the old streaming engine. We need to collect without
streaming to avoid the crash (the key diff is small enough to fit in memory).

Plan (before execution):
1) Replace `collect(streaming=True)` with plain `.collect()` (or explicit
   `collect(streaming=False)`) for `missing_in_s4` and `missing_in_s3`.
2) Keep the lazy scan and anti-joins unchanged.
3) Re-run `make segment2b-s7 RUN_ID=2b22ab5c8c7265882ca6e50375802b26`.

### Entry: 2026-01-17 08:40

Design element: Remove remaining `collect(streaming=True)` calls in S7.

Summary: After the first streaming fix, S7 still panics when collecting
`gamma_mismatch` and later summary stats, because several other
`collect(streaming=True)` calls remain. We need to remove streaming for all
remaining LazyFrame collects in S7 to avoid the Polars parquet panic.

Plan (before execution):
1) Replace every remaining `collect(streaming=True)` in
   `seg_2B/s7_audit/runner.py` with `.collect()`.
2) Keep the lazy plan structure intact (no change to joins/filters).
3) Re-run `make segment2b-s7 RUN_ID=2b22ab5c8c7265882ca6e50375802b26`.

### Entry: 2026-01-17 08:41

Outcome: S7 audit passes after qbits + Polars collect fixes.

Results:
- `make segment2b-s7 RUN_ID=2b22ab5c8c7265882ca6e50375802b26` now completes with
  `S7_RUN_REPORT` status PASS.
- Alias decode checks, S3/S4 key reconciliation, and mass consistency
  validations all pass after aligning header qbits with `record_layout.prob_qbits`
  and removing streaming collects.

### Entry: 2026-01-17 09:19

Design element: 2B.S8 validation bundle & `_passed.flag`.

Summary: S8 is a deterministic, RNG-free packager. It must verify S0 evidence
and S7 PASS coverage for a deterministic seed set, then assemble a
manifest_fingerprint-scoped validation bundle with canonical `index.json` and
`_passed.flag`. No re-auditing, no network I/O, Dictionary-only resolution.

Sources reviewed:
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s8.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/dataset_dictionary.layer1.2B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/artefact_registry_2B.yaml`

Plan (before implementation):
1) Inputs & authority:
   - Resolve by Dataset Dictionary ID only.
   - Require S0 evidence (`s0_gate_receipt_2B`, `sealed_inputs_2B`) at
     `[manifest_fingerprint]`.
   - Require `s7_audit_report` at `[seed, manifest_fingerprint]` for each seed
     in the discovery set and enforce `summary.overall_status == PASS`.
   - Resolve S2/S3/S4 outputs (`s2_alias_index`, `s2_alias_blob`,
     `s3_day_effects`, `s4_group_weights`) at `[seed, manifest_fingerprint]`
     for seed discovery and optional provenance snapshots (no re-audit).
   - Resolve policies (`alias_layout_policy_v1`, `route_rng_policy_v1`,
     `virtual_edge_policy_v1`) by exact S0-sealed path+sha256 (partition `{}`).
2) Seed discovery:
   - Build seed sets from S2/S3/S4 presence under the manifest_fingerprint.
   - Required seeds = intersection; if empty -> abort.
   - Deterministic ordering: ASCII-lex on decimal seed strings.
3) Audit prerequisite:
   - For every required seed: validate S7 report against
     `schemas.2B.yaml#/validation/s7_audit_report_v1` and require PASS.
   - Path↔embed equality check for `seed`/`manifest_fingerprint` inside each
     report.
4) Bundle layout (deterministic, write-once):
   - Create temp workspace under `runs/<run_id>/tmp/` (run-local).
   - Place S7 reports under `reports/seed={seed}/s7_audit_report.json`.
   - Place S0 evidence under `evidence/s0/` (receipt + sealed_inputs).
   - Optional evidence snapshots: policies and/or S2/S3/S4 digests under
     `evidence/refs/` if we decide to include them.
5) Canonical index + flag:
   - Build `index.json` entries `{path, sha256_hex}` with relative paths only,
     ASCII-lex by path, `_passed.flag` excluded, fields-strict.
   - Compute bundle digest = SHA256(concat(indexed file bytes in path order)).
   - Write `_passed.flag` single line: `sha256_hex = <hex64>`.
6) Publish:
   - Atomic move to
     `data/layer1/2B/validation/manifest_fingerprint={manifest_fingerprint}/`
     (write-once). If existing, allow idempotent re-emit only if byte-identical
     (otherwise abort).
7) Run-report:
   - Emit one JSON to STDOUT only (per spec) with seed coverage, inputs_digest,
     bundle digest proofs, validators + summary.
8) Logging:
   - Story header: objective + gated inputs + outputs.
   - Phase logs for seed discovery, S7 PASS checks, hashing/index, flag, publish.
   - Progress logs for file hashing (elapsed, count/total, rate, ETA).
9) Reuse helpers:
   - Prefer shared bundle helper from 1A.S9 / 1B.S8 for index+flag construction
     if already present to ensure canonical behavior.

Open confirmations (need owner decision before coding):
1) Evidence inclusion: Should the bundle include full S2/S3/S4 files and policy
   snapshots, or only S0 evidence + S7 reports? Spec allows optional evidence
   snapshots but doesn’t mandate them.
2) S7 WARN handling: OK to allow WARN-only S7 reports (PASS required), or
   should WARN be treated as fail in S8?
3) Reuse helper: OK to reuse the existing validation-bundle helper from 1A/1B
   for index/flag creation to guarantee identical bundle law?

