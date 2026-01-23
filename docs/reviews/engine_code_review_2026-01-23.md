# Engine Code Review Report
Date: 2026-01-23
Scope: packages/engine (static review of runtime determinism, core modules, CLI runners, and contract utilities)
Reviewer: Codex

## Findings (ordered by severity)

### ENG-CR-001 — High — Non-deterministic utc_day partitions for segment_state_runs
**Risk**: Re-running the same run_id on a different day writes status records to a different path, breaking resumability, determinism, and post-run auditing expectations.
**Evidence**:
- packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/runner.py:1074
- packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/runner.py:1062
- packages/engine/src/engine/layers/l1/seg_1A/s2_nb_outlets/runner.py:1231
- packages/engine/src/engine/layers/l1/seg_1A/s3_crossborder/runner.py:1304
- packages/engine/src/engine/layers/l1/seg_1A/s4_ztp/runner.py:670
- packages/engine/src/engine/layers/l1/seg_1A/s5_currency_weights/runner.py:533
- packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_set/runner.py:924
- packages/engine/src/engine/layers/l1/seg_1A/s7_integerisation/runner.py:1063
- packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py:1217
**Recommendation**: derive utc_day from run_receipt.created_utc (or a run-level fixed timestamp stored at S0) and pass it through state runners; avoid wall-clock calls inside state logic for deterministic outputs.

### ENG-CR-002 — High — “latest run_receipt.json by mtime” fallback can select wrong run
**Risk**: touching older run receipts changes mtime and can silently redirect execution to a different run_id, producing outputs under the wrong lineage.
**Evidence**:
- packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/runner.py:107-121 (pattern repeated across multiple states)
**Recommendation**: require explicit run_id for non-interactive runs (e.g., make targets), or gate the fallback behind a `--latest` flag and log a warning when used.

### ENG-CR-003 — Medium — tz_world tzid extraction suppresses failures, disables override membership checks
**Risk**: a corrupted tz_world file or schema drift can silently bypass tzid membership enforcement, weakening gate validation guarantees.
**Evidence**:
- packages/engine/src/engine/layers/l1/seg_2A/s0_gate/runner.py:910-926 (swallows IO/parsing errors and returns empty set)
- packages/engine/src/engine/layers/l1/seg_2A/s0_gate/runner.py:1385 (logs “tzid index unavailable; override membership not enforced”)
**Recommendation**: treat tzid index extraction failure as an error when tz_overrides/tz_nudge are present, or at least escalate to WARN+validation failure for policy-driven runs.

### ENG-CR-004 — Medium/Low — Run reports printed to stdout instead of logger
**Risk**: headless runs or log collection miss the run report output, reducing observability and violating narrative logging expectations.
**Evidence**:
- packages/engine/src/engine/layers/l1/seg_2B/s2_alias_tables/runner.py:1419
- packages/engine/src/engine/layers/l1/seg_2B/s1_site_weights/runner.py:1322
**Recommendation**: emit run-report JSON via logger (INFO) and keep stdout optional behind a flag.

### ENG-CR-005 — Low — Contract YAML loader does not validate object shape
**Risk**: empty or malformed YAML returns None/list and fails later with unclear errors.
**Evidence**:
- packages/engine/src/engine/contracts/loader.py:27-33
**Recommendation**: validate that parsed YAML is a dict and raise ContractError with path context when not.

### ENG-CR-006 — High — Array schema validation drops $defs on list payloads
**Risk**: When validating list payloads, the code wraps the item schema and can drop `$defs`, causing `$ref` resolution to fail (e.g., `PointerToNowhere: /$defs/hex64`). This breaks sealed_inputs validation in 6A/6B and is likely to recur elsewhere.
**Evidence**:
- packages/engine/src/engine/layers/l3/seg_6A/s1_party_base/runner.py (and S2/S3/S4/S5) — `_validate_payload` list wrapping.
- packages/engine/src/engine/layers/l3/seg_6B/s1_attachment_session/runner.py (and S2/S3/S4) — same pattern.
**Recommendation**: centralize array payload validation in a shared helper that preserves `$defs` and add a unit test covering `$id` + `$defs` resolution for list schemas.

### ENG-CR-007 — High — Non-deterministic utc_day partitions for segment_state_runs
**Risk**: Re-running the same run_id on a different day writes status records to a different path, breaking resumability, determinism, and post-run auditing expectations.
**Evidence**:
- packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/runner.py:1074
- packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/runner.py:1062
- packages/engine/src/engine/layers/l1/seg_1A/s2_nb_outlets/runner.py:1231
- packages/engine/src/engine/layers/l1/seg_1A/s3_crossborder/runner.py:1304
- packages/engine/src/engine/layers/l1/seg_1A/s4_ztp/runner.py:670
- packages/engine/src/engine/layers/l1/seg_1A/s5_currency_weights/runner.py:533
- packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_set/runner.py:924
- packages/engine/src/engine/layers/l1/seg_1A/s7_integerisation/runner.py:1063
- packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py:1217
**Recommendation**: derive utc_day from run_receipt.created_utc (or a run-level fixed timestamp stored at S0) and pass it through state runners; avoid wall-clock calls inside state logic for deterministic outputs.

### ENG-CR-008 — High — “latest run_receipt.json by mtime” fallback can select wrong run
**Risk**: touching older run receipts changes mtime and can silently redirect execution to a different run_id, producing outputs under the wrong lineage.
**Evidence**:
- packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/runner.py:107-121 (pattern repeated across multiple states)
**Recommendation**: require explicit run_id for non-interactive runs (e.g., make targets), or gate the fallback behind a `--latest` flag and log a warning when used.

### ENG-CR-009 — Medium — tz_world tzid extraction suppresses failures, disables override membership checks
**Risk**: a corrupted tz_world file or schema drift can silently bypass tzid membership enforcement, weakening gate validation guarantees.
**Evidence**:
- packages/engine/src/engine/layers/l1/seg_2A/s0_gate/runner.py:910-929 (swallows IO/parsing errors and returns empty set)
- packages/engine/src/engine/layers/l1/seg_2A/s0_gate/runner.py:1543-1582 (logs “tzid index unavailable; override membership not enforced”)
**Recommendation**: treat tzid index extraction failure as an error when tz_overrides/tz_nudge are present, or at least escalate to WARN+validation failure for policy-driven runs.

### ENG-CR-010 — Medium — CRS extraction swallows parsing errors
**Risk**: CRS parsing failures are silently ignored; downstream WGS84 checks may be skipped or incorrect, weakening gate enforcement.
**Evidence**:
- packages/engine/src/engine/layers/l1/seg_2A/s0_gate/runner.py:854-872 (`_extract_geo_crs` ignores exceptions)
**Recommendation**: emit a WARN and include the failure context when CRS cannot be read, or fail closed for required assets.

### ENG-CR-011 — Low — Non-atomic JSON writes for run reports / gate outputs
**Risk**: a crash mid-write can leave partial JSON files, causing subsequent reads or validations to fail.
**Evidence**:
- packages/engine/src/engine/layers/l3/seg_6B/s5_validation_gate/runner.py:454-456
- packages/engine/src/engine/layers/l3/seg_6A/s5_fraud_posture/runner.py:715
**Recommendation**: reuse the atomic publish pattern (tmp + replace) for run reports and gate JSON outputs.

### ENG-CR-012 — Low — Contract YAML loader does not validate object shape
**Risk**: empty or malformed YAML returns None/list and fails later with unclear errors.
**Evidence**:
- packages/engine/src/engine/contracts/loader.py:27-31
**Recommendation**: validate that parsed YAML is a dict and raise ContractError with path context when not.

## Open Questions / Assumptions
- Determinism: I assumed run outputs should not depend on wall-clock date. If the spec requires “execution date” partitioning, we should codify that and exclude these files from determinism checks.
- Run selection: I assumed the “latest receipt” fallback is for ad-hoc CLI usage only. If it’s required for operators, consider a dedicated “runs/latest” pointer to avoid mtime ambiguity.

## Testing
- No tests executed (static review only).

## Out of Scope
- Validation of contract correctness vs spec text
- Performance profiling or runtime benchmarking
- Non-engine packages or orchestration scripts
