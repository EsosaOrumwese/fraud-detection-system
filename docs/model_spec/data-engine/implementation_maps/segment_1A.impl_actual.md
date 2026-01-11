# segment_1A.impl_actual.md

Append-only implementation planning log for Segment 1A. Each entry documents the
design element, a short summary of the problem, and the detailed plan to resolve
it. Do not delete prior entries.

---

## S0 - Foundations (S0.1 to S0.10)

### Entry: 2026-01-11 00:12

Design element: Contract source switching (model_spec vs contracts root)
Summary: Ensure dev uses docs/model_spec but production can switch to contracts root without code changes.
Plan:
- Introduce a ContractSource abstraction with a `layout` flag that maps to either
  `docs/model_spec/data-engine/...` or `contracts/...` paths.
- Route all dictionary/registry/schema lookups through ContractSource to avoid
  hard-coded paths.
- Make the engine config carry `contracts_root` + `contracts_layout` with a
  default of `model_spec` and allow CLI overrides later.
- Add a focused test that resolves the same dictionary IDs under both layouts
  once the contracts mirror is populated.

Design element: Run isolation and external root resolution
Summary: Reads must prefer run-local staged inputs; writes must stay under runs/<run_id>.
Plan:
- Use a RunPaths helper to locate `runs/<run_id>/{data,logs,tmp,cache,reference}`.
- Resolve any input path by checking `runs/<run_id>/reference/<path>` first, then
  external roots (repo root by default), then fail.
- Do not copy large immutable datasets by default; only read from external roots.
- Support an optional staging mode later that populates run-local reference when
  requested by the operator.

Design element: Merchant universe loading + schema authority
Summary: S0.1 must validate merchant_ids against ingress schema and enforce
home_country, mcc, and channel mappings before any RNG.
Plan:
- Load `transaction_schema_merchant_ids` using the dataset dictionary path,
  resolving the version token (explicit override or latest directory).
- Load schema packs (`schemas.ingress.layer1.yaml`, `schemas.1A.yaml`,
  `schemas.layer1.yaml`) through the contract source.
- Validate the merchant table against `schemas.ingress.layer1.yaml#/merchant_ids`
  using JSON Schema (jsonschema lib).
- Enforce `home_country_iso` membership in ISO list, `mcc` domain [0, 9999], and
  channel mapping (`card_present` -> CP, `card_not_present` -> CNP).
- Compute `merchant_u64` exactly as `LOW64(SHA256(LE64(merchant_id)))` and store
  in the in-memory merchant frame.

Design element: Parameter hash (S0.2.2)
Summary: Compute `parameter_hash` over governed parameter basenames with UER
encoding, streaming digests, and strict basename rules.
Plan:
- Resolve parameter files from config paths specified in the registry/dictionary.
- Enforce ASCII basenames and uniqueness; abort on missing required basenames.
- Include optional policy basenames only when present.
- Hash file bytes with before/after stat race checks; record size + mtime for
  `param_digest_log` later.
- Implement UER encoding (length-prefixed UTF-8) and the tuple-hash algorithm.

Design element: Manifest fingerprint (S0.2.3)
Summary: Compute `manifest_fingerprint` over all opened artifacts plus git commit
and parameter hash, with dependency closure enforced.
Plan:
- Use the artefact registry to resolve dependency closure for every opened
  artifact (including merchant_ids bootstrap policy if declared).
- Hash each artifact by basename + digest using UER; enforce ASCII unique names.
- Derive `git_32` from the repo commit (use raw bytes; pad SHA-1 if needed).
- Append `git_32` and `parameter_hash_bytes` to the tuple-hash and SHA-256 it.
- Record `manifest_fingerprint_resolved` for the validation bundle later.

Design element: run_id (S0.2.4)
Summary: Generate log partition id that never affects RNG or outputs.
Plan:
- Compute `run_id` from UER("run:1A") + manifest_fingerprint + seed + UTC ns.
- If the run_id already exists under RNG log paths, increment ns and retry up to
  2^16 iterations, then abort.
- Use run_id only for log partitioning (rng events/audit/trace).

Design element: RNG anchor + audit + trace (S0.3+)
Summary: Emit the non-consuming S0 RNG anchor event and one trace row immediately
after it; write the audit entry.
Plan:
- Write `rng_event_anchor` with module `1A.s0`, substream `s0.anchor`, blocks=0,
  draws="0", counters unchanged.
- Append a trace row for (module, substream) immediately after the event.
- Write a single audit row with algorithm metadata, build commit, and optional
  platform/hostname fields; keep timestamps in RFC-3339 microseconds.

Design element: sealed_inputs_1A
Summary: Produce the authoritative inventory of assets sealed by S0.
Plan:
- Include external references (merchant_ids, ISO, GDP, GDP buckets) and any
  parameter and schema assets opened in S0.
- Record `asset_id`, `version_tag`, `sha256_hex`, `path` (posix), and `partition`
  mapping; sort by `(asset_id, path)`.
- Ensure output path uses the dictionary entry:
  `data/layer1/1A/sealed_inputs/manifest_fingerprint=.../sealed_inputs_1A.json`.

Design element: s0_gate_receipt_1A
Summary: Emit the S0 gate receipt with lineage and sealed input summaries.
Plan:
- Write `manifest_fingerprint`, `parameter_hash`, `run_id`, and `sealed_inputs`
  entries that contain `id`, `partition` key list, and `schema_ref`.
- Use the dictionary path:
  `data/layer1/1A/s0_gate_receipt/manifest_fingerprint=.../s0_gate_receipt.json`.

Design element: Output placement + logging
Summary: All outputs must be written under runs/<run_id> with continuous logs.
Plan:
- Resolve dictionary paths relative to `runs/<run_id>` for all S0 outputs.
- Emit structured log lines at each major step (input resolution, validation,
  hashing, outputs) and periodic progress logs for long loops.

---

### Entry: 2026-01-11 00:34

Design element: Contract source switching control (approved approach)
Summary: Implemented the approved env-var + CLI override to keep dev on
docs/model_spec and allow production to flip to contracts root without code
changes.
Plan:
- Default `ENGINE_CONTRACTS_LAYOUT=model_spec` and `ENGINE_CONTRACTS_ROOT=<repo>`.
- Add CLI flags `--contracts-layout` and `--contracts-root` that override env
  defaults for every entrypoint.
- Route all contract lookups through ContractSource to keep switching isolated
  to config.

Design element: Run seed source (approved approach)
Summary: Added config-based seed with CLI override; fail fast if missing.
Plan:
- Create `config/layer1/1A/rng/run_seed.yaml` with a default seed value.
- Allow `--seed` to override the config file for operator-driven runs.
- Include the seed file in sealed_inputs + manifest_fingerprint when used.

Design element: Manifest fingerprint naming
Summary: Use file basenames (path.name) as the canonical names for opened
artifacts in the manifest fingerprint hash, while parameter_hash uses the
spec-governed canonical names.
Plan:
- Collect all opened artifact paths (references, params, dependencies, schema
  packs, dictionary/registry, seed config).
- Hash each file and feed the manifest tuple-hash using `path.name` to align
  with the spec's "basename" wording.
- Abort on duplicate basenames to avoid ambiguous lineage hashes.

Design element: Run-local staged input precedence
Summary: Run-local staging cannot be consulted before run_id is computed, so S0
currently resolves inputs from external roots first.
Plan:
- Document this as a temporary limitation and revisit once a precomputed
  run-id/staging workflow is defined.
- If a staging mode is introduced, re-resolve inputs after run_id creation and
  fail on digest mismatches to preserve determinism.

Design element: Ingress schema validation (JSON Schema adapter)
Summary: Replace manual merchant_ids validation with JSON Schema validation
derived from schemas.ingress.layer1.yaml.
Plan:
- Implement a schema adapter that converts the schema pack table definition into
  Draft 2020-12 JSON Schema (row-level).
- Validate every merchant_ids row with jsonschema and fail fast on errors.
- Keep a targeted FK membership check for home_country_iso against ISO list.

Design element: Makefile entrypoint for S0
Summary: Add Make targets to run S0 without poetry while honoring contract
switching flags.
Plan:
- Add `segment1a-s0` and `engine-s0` targets calling `engine.cli.s0_foundations`.
- Add Make vars for `ENGINE_CONTRACTS_LAYOUT`, `ENGINE_CONTRACTS_ROOT`,
  `ENGINE_EXTERNAL_ROOTS`, `SEG1A_S0_SEED`, and `SEG1A_S0_MERCHANT_VERSION`.

Design element: S0 spec crosscheck (initial)
Summary: Quick audit of current S0 implementation vs the expanded S0 spec.
Plan:
- Validate merchant_ids against JSON Schema; keep ISO FK membership check.
- Confirm parameter_hash + manifest_fingerprint inputs match governed basenames
  and dependency closure rules.
- Add an authority audit to reject any non-JSON schema refs (e.g., .avsc).
- Note outstanding gap: run_id collision check against RNG log directories
  (currently run-root only).

### Entry: 2026-01-11 00:52

Design element: run_id collision scope (S0.2.4)
Summary: Align run_id collision checks to RNG log directories per spec.
Plan:
- Derive RNG log directories from the dataset dictionary entries for
  `rng_audit_log`, `rng_trace_log`, and `rng_event_anchor` using the candidate
  `run_id`, `seed`, and `parameter_hash`.
- Treat any existing log directory for that `{seed, parameter_hash, run_id}` as
  a collision, increment `T_ns` by +1, and recompute run_id (bounded to 2^16).
- Keep a run-root existence check as a conservative guard against accidental
  reuse when partial runs left data without logs.

Design element: Pre-run input resolution (run-local staging order)
Summary: Avoid resolving run-local staged inputs before run_id exists.
Plan:
- Add an `allow_run_local` switch to input resolution so pre-run S0 resolution
  can consult shared external roots only.
- Keep the run-local-first resolution order once run_id exists for downstream
  states (or a future staging mode).
- Remove the effective dependency on the placeholder run_id by disabling the
  run-local search during the pre-run phase.

### Entry: 2026-01-11 01:07

Design element: Run log file (operator-facing heartbeat)
Summary: Provide a run-scoped log file under runs/<run_id> to mirror legacy run logs.
Plan:
- Add a file handler in the core logging module that can be attached once per
  path, with the same timestamped format as STDOUT.
- After S0 derives run_id, attach the file handler to
  runs/<run_id>/run_log_<run_id>.log and emit a confirmation log line.
- Accept that pre-run logs (before run_id) remain STDOUT-only; if needed later,
  add a pre-run buffer or temporary log location that is copied into the run
  folder once run_id is known.

## S1 - Hurdle (placeholder)
No entries yet.

## S2 - NB Outlets (placeholder)
No entries yet.

## S3 - Cross-border Universe (placeholder)
No entries yet.

## S4 - ZTP Target (placeholder)
No entries yet.

## S5 - Currency Weights (placeholder)
No entries yet.

## S6 - Foreign Selection (placeholder)
No entries yet.

## S7 - Integer Allocation (placeholder)
No entries yet.

## S8 - Outlet Catalogue (placeholder)
No entries yet.

## S9 - Validation (placeholder)
No entries yet.
