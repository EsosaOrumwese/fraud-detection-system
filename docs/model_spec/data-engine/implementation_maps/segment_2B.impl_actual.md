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
Summary: Added the S0 gate implementation for 2B, matching the spec’s gate law,
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

Design element: Re-emit S0 after semver alignment.
Summary: Cleared the prior run-local S0 outputs (write-once guard) and re-ran
`make segment2b-s0`; the gate completed successfully with all validators PASS
and `warn_count=0`.

Run outcome details:
1) V-09 now PASS with version_tag resolved to "1.0.0" for policy assets.
2) Sealed inputs + receipt republished under the manifest_fingerprint path.

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
