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

### Entry: 2026-01-11 01:12

Design element: Ingress schema validation (row-level)
Summary: Fix JSON Schema adapter to validate row objects instead of arrays.
Plan:
- Keep the array-shaped JSON Schema output for any whole-table validation use,
  but add a row-level schema builder that includes $defs and table properties.
- Update row validation to use the row schema so merchant rows validate against
  the correct object type and column constraints.
- Preserve strict additionalProperties=false behavior to match ingress contracts.

### Entry: 2026-01-11 01:16

Design element: Run root override (RUN_ROOT alignment)
Summary: Allow S0 to place run folders under a configurable runs root so Makefile RUN_ROOT is honored.
Plan:
- Add `runs_root` to EngineConfig with default `<repo>/runs`.
- Extend RunPaths to accept `runs_root` and resolve run paths as
  `<runs_root>/<run_id>`.
- Add CLI/env support (`--runs-root`, `ENGINE_RUNS_ROOT`) and wire Makefile
  `RUN_ROOT` into S0 via `ENGINE_RUNS_ROOT`.
- Keep run_id partitioning unchanged; only the base runs directory is configurable.

### Entry: 2026-01-11 01:31

Design element: ISO canonical intake alignment (GeoNames source)
Summary: Fix iso3166_canonical_2024 build to match the acquisition guide and restore missing ISO2 entries (e.g., Namibia).
Plan:
- Update `scripts/build_iso_canonical.py` to parse GeoNames `countryInfo.txt` and
  output to `reference/iso/iso3166_canonical/<version>/iso3166.parquet`.
- Enforce guide rules: keep only ISO2 `^[A-Z]{2}$`, exclude `XK` and `UK`,
  cast numeric codes to int16, and sort lexicographically by `country_iso`.
- Emit `iso3166.provenance.json` with required fields (upstream URL, retrieval
  time, sha256s, exclusions, is_exact_vintage), plus a manifest for audit.
- Use the in-repo `source/countryInfo.txt` by default; allow explicit source
  overrides or forced downloads for rebuilds.

### Entry: 2026-01-11 01:37

Design element: Registry path resolution (directory templates)
Summary: Support registry/dictionary paths that point to versioned directories instead of concrete files.
Plan:
- Update registry path resolution to accept directories and deterministically
  select a concrete artifact file.
- If the registry entry name is known, prefer files named
  `<artifact_name>.(parquet|csv|json|yaml|yml|jsonl)`.
- Otherwise, accept a single parquet file in the directory, or a single file
  of any type; error on ambiguous directories to avoid non-determinism.

### Entry: 2026-01-11 01:40

Design element: Polars channel mapping performance
Summary: Replace map_elements with native expression for channel mapping.
Plan:
- Use `replace_strict(CHANNEL_MAP)` for `channel_sym` to avoid row-wise Python
  lambdas and remove PolarsInefficientMapWarning.
- Keep merchant_u64 mapping unchanged (requires custom hash).

### Entry: 2026-01-11 01:43

Design element: Run resume ergonomics (dev mode)
Summary: Add a run receipt and Makefile support to resume by RUN_ID without breaking run-id semantics.
Plan:
- Write `run_receipt.json` into `runs_root/<run_id>/` after run_id is computed,
  containing run_id, seed, parameter_hash, manifest_fingerprint, contract
  source settings, external roots, and creation time.
- Adjust Makefile defaults to separate `RUNS_ROOT` (base) and `RUN_ID`, and
  derive `RUN_ROOT` as `$(RUNS_ROOT)/$(RUN_ID)` when a RUN_ID is provided.
- Keep S0 writing under `RUNS_ROOT/<run_id>`; downstream segments can resume by
  setting `RUN_ID=<id>` without changing seed or contracts.

### Entry: 2026-01-11 01:54

Design element: Log readability + progress timing
Summary: Align log formatting to legacy run logs and add elapsed/delta timing for S0 steps.
Plan:
- Switch the global logging formatter to `%(asctime)s,%(msecs)03d [LEVEL] logger: msg`
  with `YYYY-MM-DD HH:MM:SS` timestamps to match legacy style.
- Add an S0 step timer that logs elapsed and delta seconds for each major phase.
- Keep the structured log content; only change formatting and add timing suffixes.

### Entry: 2026-01-11 02:33

Design element: S0.4 GDP bucket attachment
Summary: Attach GDP per-capita and bucket IDs to each merchant deterministically with hard failure on missing or invalid values.
Plan:
- Load the pinned GDP per-capita table (2025-04-15) and bucket map (2024) as in S0.1.
- For each merchant, look up `g_c` and `b_m` by `home_country_iso`; abort with
  explicit error codes if GDP is missing, non-positive, or bucket is out of 1..5.
- Keep `g_c` and `b_m` in-memory for S0.5; do not emit RNG or write outputs here.
- Log coverage stats (missing GDP/bucket counts) before aborting to aid diagnosis.

Design element: S0.5 design matrices (hurdle + NB)
Summary: Build deterministic design rows with frozen column order and emit the hurdle design matrix under parameter_hash.
Plan:
- Load `hurdle_coefficients.yaml` and `nb_dispersion_coefficients.yaml` to obtain
  `dict_mcc`, `dict_ch`, `dict_dev5` and validate shapes and canonical ordering.
- Build one-hot vectors in frozen order and assert the leakage rule:
  GDP bucket dummies only for hurdle; `ln(g_c)` only for NB dispersion.
- Materialize `hurdle_design_matrix` to
  `data/layer1/1A/hurdle_design_matrix/parameter_hash={parameter_hash}/` as parquet
  (columns: merchant_id, mcc, channel, gdp_bucket_id, intercept=1.0).
- Keep NB design vectors in-memory for later S2 work; add a TODO to materialize
  if/when a schema/dictionary entry is defined.

Design element: S0.6 crossborder eligibility flags
Summary: Apply crossborder policy rules deterministically to emit eligibility flags.
Plan:
- Parse `crossborder_hyperparams.yaml` and validate `eligibility.rule_set_id`,
  `default_decision`, and rule entries (priority, decision, channel, iso, mcc).
- Expand MCC ranges and wildcard rules into a match structure keyed by
  `(channel_sym, home_country_iso)` and MCC intervals.
- For each merchant, select the winning deny/allow rule by
  `(decision, priority, id)` with `deny < allow`; otherwise use default decision.
- Emit `crossborder_eligibility_flags` with embedded `parameter_hash`, optional
  `produced_by_fingerprint`, and `reason` set to rule id or default reason.

Design element: S0.7 hurdle pi diagnostics (optional)
Summary: Optionally emit `hurdle_pi_probs` as a parameter-scoped diagnostics cache.
Plan:
- Reuse the S0.5 hurdle design vectors and `hurdle_coefficients` to compute
  `eta` and `pi` using Neumaier + two-branch logistic (binary64).
- Narrow `logit` and `pi` to float32 with RNE; emit to
  `data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/`.
- Gate emission behind a CLI/env toggle; by default emit to aid validation.

Design element: S0.8 numeric policy self-tests + attestation
Summary: Execute numeric self-tests, record policy/profile digests, and emit numeric_policy_attest.json.
Plan:
- Resolve `numeric_policy_profile` and `math_profile_manifest` from the registry;
  include both in the manifest-fingerprint enumeration.
- Implement Python-based self-tests for rounding mode, subnormal handling,
  FMA absence, Neumaier sum sanity, and totalOrder mapping.
- Record test results, environment flags, and digests into
  `numeric_policy_attest.json`; treat any failed test as an S0.9 abort.
- Include the attestation digest in the manifest enumeration even though the
  file is written after manifest_fingerprint is known (use staged bytes).

Design element: S0.9 failure records
Summary: Standardize abort handling with a failure.json record under the failure bundle path.
Plan:
- Wrap S0 execution in a top-level try/except that maps raised errors to
  `(failure_class, failure_code)` and writes `failure.json` with required
  lineage keys and details.
- Write failure records to
  `data/layer1/1A/validation/failures/seed={seed}/manifest_fingerprint={manifest_fingerprint}/run_id={run_id}/`.
- Ensure only the first failure is recorded; subsequent exceptions re-raise.

Design element: S0.10 validation bundle + gate
Summary: Emit the full validation bundle with manifest logs, index, and _passed flag.
Plan:
- Write `MANIFEST.json`, `parameter_hash_resolved.json`,
  `manifest_fingerprint_resolved.json`, `param_digest_log.jsonl`, and
  `fingerprint_artifacts.jsonl` into the validation bundle directory.
- Include `numeric_policy_attest.json` and optionally lint files.
- Generate `index.json` listing bundle members, compute `_passed.flag` as
  SHA-256 over listed files (excluding `_passed.flag`) in ASCII path order.
- Stage bundle in a `_tmp.{uuid}` directory and atomically rename on success.

### Entry: 2026-01-11 02:47

Design element: Manifest hashing fix + numeric attestation ordering
Summary: Align parameter_hash/manifest_fingerprint hashing to the tuple-hash spec and include numeric_policy_attest in the manifest enumeration by staging attestation bytes before the fingerprint is final.
Plan:
- Replace the current double-hash pattern with the spec-compliant concatenation:
  parameter_hash = SHA256(T1||T2||...); manifest_fingerprint = SHA256(T1||...||Tk||git_32||parameter_hash_bytes).
- Preserve ASCII-unique basename checks and the UER(name)||digest per-artefact tuple hash.
- Run numeric self-tests immediately after parameter_hash (still before any RNG), build the deterministic `numeric_policy_attest.json` payload in memory, and hash those bytes for inclusion in the manifest enumeration.
- Note the ordering deviation (attestation computed before manifest_fingerprint) in the logbook so the digest can be included without post-hoc mutation; write the file after the run_id is established but keep bytes identical to the staged hash.
- Add explicit logs around hash inputs (counts, basenames) to aid auditability.

### Entry: 2026-01-11 03:16

Design element: S0 implementation (hashing, numeric policy, GDP features, eligibility, validation)
Summary: Implemented S0.4–S0.10 outputs with spec-aligned hashing, numeric policy self-tests, atomic writes, failure records, and validation bundle generation.
Plan/Implementation details:
- Hashing: replaced the double-hash path with spec-compliant tuple concatenation for `parameter_hash` and `manifest_fingerprint` (SHA256 over concatenated T(a) bytes, then git_32 + parameter_hash_bytes appended for manifest).
- Numeric policy (S0.8): added `numeric_policy.py` to run RNE/FTZ/FMA/libm/Neumaier/total-order self-tests and produce `numeric_policy_attest.json`. Attestation bytes are serialized deterministically (sort_keys + compact separators) before hashing for manifest enumeration.
- Ordering deviation: to include attestation in the manifest enumeration, S0 now computes numeric tests and attestation bytes before finalizing `manifest_fingerprint`. This is a deliberate ordering deviation noted here for auditability.
- Libm regression check: the manifest does not ship reference bit-patterns; the implementation therefore uses version/function checks (numpy/scipy artifacts listed in `math_profile_manifest.json`) as the regression gate. This is a pragmatic substitution and should be revisited when reference vectors exist.
- GDP attachment (S0.4): enforce `observation_year=2024`, FK coverage, positivity, and bucket range (1..5). Merchants get `gdp_per_capita` and `gdp_bucket_id` columns before design-matrix work.
- Design matrices (S0.5): load hurdle + NB dispersion coefficient bundles, verify dict alignment and shapes, ensure MCC/channel vocab coverage, and persist `hurdle_design_matrix` under `parameter_hash` with atomic partition writes.
- Eligibility (S0.6): parse `crossborder_hyperparams.yaml` rule-set with deterministic matching (deny > allow, priority asc, id asc), emit `crossborder_eligibility_flags` with `parameter_hash` and `produced_by_fingerprint`.
- Hurdle pi diagnostics (S0.7): optional emission of `hurdle_pi_probs` using branch-stable logistic + Neumaier sum, narrowed to float32; gated by CLI/env flag.
- Validation bundle (S0.10): added `validation_bundle.py` to emit `MANIFEST.json`, `{parameter,manifest}_resolved.json`, `param_digest_log.jsonl`, `fingerprint_artifacts.jsonl`, `numeric_policy_attest.json`, `run_environ.json`, `index.json`, and `_passed.flag` with atomic directory swap.
- Schema nuance: `fingerprint_artifacts.jsonl` uses `sha256` (not `sha256_hex`) to match `schemas.layer1.yaml`; this diverges from the textual S0.10 description.
- Failure records (S0.9): added deterministic failure payload writer to `validation/failures/manifest_fingerprint=.../seed=.../run_id=...` with `_FAILED.SENTINEL.json`, and wired run-state telemetry updates on failure.

### Entry: 2026-01-11 03:31

Design element: Reference input version selection (dev guard)
Summary: Ensure S0 uses a coherent merchant snapshot in dev runs when dictionary `version` is `TBD`, without changing the production contract (manifest-driven version pinning).
Plan:
- Detect that `transaction_schema_merchant_ids` has `version: TBD` in the dataset dictionary and that the resolver currently selects the lexicographically last directory, which can pick legacy `vYYYY-MM-DD` snapshots.
- In dev (Makefile orchestration), default `SEG1A_S0_MERCHANT_VERSION` to the bootstrap `MERCHANT_VERSION` (currently `2026-01-03`) so S0 reads the intended snapshot and avoids reference mismatches (e.g., GDP coverage gaps).
- Keep the engine code unchanged so production still relies on explicit manifest/scenario pinning; document this as a dev-only guardrail.

### Entry: 2026-01-11 03:35

Design element: Numeric policy math_profile pinning (S0.8)
Summary: Align the pinned math profile manifest with the active dev runtime so the libm self-test passes while preserving the same function set.
Plan:
- Keep the S0.8 libm self-test strict (fail-closed) and update the pinned math profile reference version instead of relaxing checks.
- Create a new `reference/governance/math_profile/2026-01-11/math_profile_manifest.json` with `numpy-2.3.5` and `scipy-1.15.3` artifacts and their wheel SHA256 digests, retaining the same function list.
- Ensure Makefile uses the project venv interpreter so the runtime matches the pinned manifest; keep production wiring unchanged (registry path uses `{version}` and resolves the latest version).

### Entry: 2026-01-11 03:37

Design element: Registry `{version}` resolution ordering
Summary: Prevent non-date version directories (e.g., `openlibm-v0.8.7`) from shadowing date-stamped governance snapshots in dev runs.
Plan:
- When resolving registry paths that include `{version}`, prefer directories matching `YYYY-MM-DD` if any exist; fall back to lexicographic order otherwise.
- Apply in `_resolve_registry_path` so governance artefacts (numeric policy, math profile, etc.) select the newest date-stamped snapshot by default.
- Keep behavior unchanged for templates without `{version}` or when only non-date versions exist.

### Entry: 2026-01-11 03:39

Design element: Numeric policy self-test tolerance (Neumaier)
Summary: Stabilize the Neumaier self-test across runtime versions by comparing to `math.fsum` with a bounded ULP window.
Plan:
- Replace the Decimal-based reference sum with `math.fsum` to avoid cross-runtime drift in the expected value.
- Accept Neumaier results within 1024 ULP of `math.fsum` for the test sequence; this still guards against gross errors while preventing false failures under Python/ABI changes.

### Entry: 2026-01-11 03:42

Design element: S0.6 eligibility output typing
Summary: Prevent Polars overflow during eligibility frame construction for large `merchant_id` values.
Plan:
- Emit the crossborder eligibility frame with an explicit schema, pinning `merchant_id` to `UInt64` and other columns to their expected types.
- Only include `produced_by_fingerprint` in the schema when supplied to avoid schema mismatch on optional lineage.

### Entry: 2026-01-11 03:43

Design element: S0.7 hurdle_pi_probs typing
Summary: Prevent Polars overflow when materializing optional hurdle diagnostics.
Plan:
- Build `hurdle_pi_probs` with an explicit schema (`merchant_id` as `UInt64`, `logit/pi` as `Float32`, hashes as `Utf8`) to avoid inference issues on large IDs.

### Entry: 2026-01-11 03:44

Design element: Validation bundle timestamp helper
Summary: Ensure `created_utc_ns` emission works across Python runtimes.
Plan:
- Use `time.time_ns()` in `utc_now_ns()` instead of `datetime.timestamp_ns()` to avoid missing-method failures under Python 3.12 while still emitting epoch nanoseconds.

### Entry: 2026-01-11 06:37

Design element: Run log labeling (S0/S1)
Summary: Make log prefixes self-descriptive by using the full engine module path instead of terse `engine.s0`/`engine.s1` names.
Plan:
- Update S0 runner + outputs loggers to `engine.layers.l1.seg_1A.s0_foundations.l2.*` so log lines read like the prior `run_log_run-4` format.
- Update S0/S1 CLI logger names to the same namespace for consistency across CLI and runner output.
- Apply the same pattern to S1 hurdle runner so downstream logs remain intuitive.

## S1 - Hurdle (placeholder)

### Entry: 2026-01-11 02:07

Design element: S1 run context + preconditions
Summary: Anchor S1 to the run receipt and verify RNG audit presence before emitting any events.
Plan:
- Require a run_id (CLI or newest run_receipt.json under runs_root) and load
  `runs_root/<run_id>/run_receipt.json` to get `{seed, parameter_hash,
  manifest_fingerprint, runs_root}`.
- Load dataset dictionary, artefact registry, and schema packs via
  ContractSource to keep dev/prod switching intact.
- Resolve `rng_audit_log`, `rng_trace_log`, `rng_event_hurdle_bernoulli`, and
  `hurdle_design_matrix` paths via dictionary templates and the run tokens,
  prefixing with `runs_root/<run_id>`.
- Assert the RNG audit log exists and contains a row for the `{seed,
  parameter_hash, run_id}` triple before any event emission; abort if missing.

Design element: Hurdle inputs + coefficient alignment
Summary: Load the S0.5 design matrix and hurdle coefficients with strict,
order-frozen alignment to x_m.
Plan:
- Load the parameter-scoped `hurdle_design_matrix` dataset and select required
  columns: `merchant_id`, `mcc`, `channel`, `gdp_bucket_id`, `intercept`.
- Enforce presence of the required columns and `intercept == 1.0`; abort on
  missing columns or unexpected intercept values.
- Resolve `hurdle_coefficients.yaml` via the artefact registry template and
  load it atomically; parse `dict_mcc`, `dict_ch`, `dict_dev5`, and `beta`.
- Validate `dict_ch == ["CP","CNP"]`, `dict_dev5 == [1,2,3,4,5]`, and
  `len(beta) == 1 + len(dict_mcc) + len(dict_ch) + len(dict_dev5)`; abort on
  any mismatch to preserve the frozen design order.
- Build index maps for MCC/channel/GDP buckets so the contribution order is
  exactly `[intercept, mcc block, channel block, gdp bucket block]`.

Design element: Logistic probability + RNG event/trace emission
Summary: Compute `eta/pi` with fixed-order Neumaier and emit the hurdle event +
trace using S0's keyed Philox substreams.
Plan:
- Implement UER string encoding (LE32 length + UTF-8) plus LE64 encoding for
  merchant_u64, and derive master material
  `M = SHA256(UER("mlr:1A.master") || manifest_fingerprint_bytes || LE64(seed))`.
- Implement keyed substream derivation per S0.3:
  `msg = UER("mlr:1A") || UER("hurdle_bernoulli") || LE64(merchant_u64)`,
  `H = SHA256(M || msg)`, key = LOW64(H) (LE64 of bytes 24..31), counter =
  `(BE64(H[16:24]), BE64(H[24:32]))`.
- Implement Philox2x64-10 with standard constants and key schedule; map counter
  `(hi,lo)` to a block with low-lane `x0` used for the uniform, and advance the
  counter by 1 for stochastic events.
- Implement `u01` mapping `u = ((x + 1) * 2^-64)` with `u == 1.0` remapped to
  `1 - 2^-53`; ensure `u` is in (0,1).
- For each merchant row: compute `eta` via Neumaier in fixed order, compute
  `pi` with the two-branch logistic (no clamp), mark deterministic if
  `pi ∈ {0.0,1.0}`. If stochastic, draw one uniform and set `is_multi = u < pi`;
  if deterministic, set `u = null` and `is_multi = (pi == 1.0)`.
- Emit JSONL event records with the full RNG envelope + payload; append a
  cumulative `rng_trace_log` row per event with saturating uint64 totals.
- Log progress every N merchants to keep a heartbeat; write to a temp file and
  atomically move into the final log path, aborting if the target path already
  exists.

### Entry: 2026-01-11 07:01

Design element: S1 validator + failure artefacts
Summary: Implemented S1 validation and failure recording to complete S1.6/S1.V coverage.
Plan:
- Added per-run `segment_state_runs` telemetry for S1 with started/failed/completed status updates (same path template as S0).
- Implemented JSON-schema validation for `rng_event_hurdle_bernoulli` and `rng_trace_log` rows using the layer-1 schema pack; schema failures map to `rng_envelope_schema_violation` or `hurdle_payload_violation` (F4).
- Implemented replay checks: recompute `eta/pi` via fixed-order Neumaier + two-branch logistic; validate deterministic branch rules; regenerate `u` from Philox base counter and assert `(u<pi)` matches `is_multi`; enforce `draws/blocks` budget identity and counter deltas (F4).
- Enforced path↔embed equality on `{seed, parameter_hash, run_id}` (F5), uniqueness/cardinality vs design matrix row count (F8), and gated-stream presence checks using dictionary `gating.gated_by == rng_event_hurdle_bernoulli` (F8).
- Added failure record emission to `validation/failures/manifest_fingerprint=.../seed=.../run_id=...` with `_FAILED.SENTINEL.json` via the shared writer.

Deviation note:
- Missing run inputs (e.g., audit log) are wrapped to `wrong_dataset_path` (F5) with the dataset id inferred from the error message; this is logged for future refinement to dedicated S1.6 codes if specified.

### Entry: 2026-01-11 06:44

Design element: S1 completeness check (status + remaining work)
Summary: Core hurdle emission is implemented, but S1 is not complete versus the spec due to missing validation/failure artefacts.
Plan:
- Add S1 failure handling per S1.6/S1.V: emit failure objects with the required keys and `_FAILED` sentinel under the validation bundle path when any S1 predicate fails.
- Implement the S1 validator harness (schema + partition equality + RNG replay + trace reconciliation + gating presence checks) so S1 can produce a PASS/FAIL bundle similar to S0.
- Record run-state telemetry for S1 (started/failed/completed) consistent with the S0 `segment_state_runs` tracking.

### Entry: 2026-01-11 07:24

Design element: S1 runner repair + spec alignment (S1.1–S1.V)
Summary: Rewrote `run_s1` and aligned registry resolution, trace totals, and validation to the hurdle spec.
Plan/Implementation details:
- Replaced the broken `run_s1` control flow with a clean, spec-ordered sequence: load run_receipt, validate gate receipt lineage, verify `rng_audit_log`, and preflight event/trace targets before any emission.
- Enforced design-matrix invariants up front (required columns, intercept == 1.0, unique merchant_id) and built a `design_map` for validator joins.
- Resolved `hurdle_coefficients` using the registry template with date-stamped version preference and artifact-name file selection to avoid lexicographic drift.
- Emitted hurdle events with deterministic vs stochastic branches per `pi`, ensured `u` is open-interval only for stochastic draws, and wrote JSONL to temp files before atomic promotion.
- Adjusted trace totals to saturate at uint64 (per schema) and appended trace rows alongside events using the same envelope counters.
- Extended S1 validation to enforce `manifest_fingerprint` equality in events and to select the final trace row using the schema’s max-(after_hi, after_lo) + ts_utc + totals + part-name rule.
- Preserved failure recording + `segment_state_runs` telemetry so any abort writes a structured failure payload and run-state entry.

Deviation note:
- InputResolutionError cases still map to `wrong_dataset_path` for failure_code until the spec declares finer-grained codes for missing inputs.

### Entry: 2026-01-11 07:36

Design element: S1 resumability + trace/validation compatibility
Summary: Added resume semantics and compatibility fixes so existing S1 logs validate without re-emission while new runs align to the trace selection rule.
Plan/Implementation details:
- Resumability: detect existing hurdle events + trace rows for the run_id; if both exist, skip emission and run validation only. If only one side exists, abort with a cleanup-required error to avoid mixed outputs.
- Trace emission: track the max `(after_hi, after_lo)` seen during event emission and append a final trace row carrying the full totals with those max counters to satisfy the schema’s final-row selection rule without sorting the full event set.
- Trace validation: keep spec selection by max counter; if totals mismatch and a legacy trace exists, fall back to the row with max totals and log a compatibility message.
- Schema validation fixes: lift `unevaluatedProperties` from `allOf` into the root schema for Draft 2020-12 evaluation, and widen `$defs/id64.maximum` to uint64 for validation to match actual merchant_id ranges observed in ingress.

Deviation note:
- The `id64` widening is a spec deviation; ingress data contains merchant_id values above signed int64, so validation is relaxed to uint64 until contracts are reconciled.

### Entry: 2026-01-11 07:46

Design element: Contract alignment for merchant_id range (id64)
Summary: Promoted the temporary uint64 validation override into the contract so schema authority matches observed merchant_id values.
Plan/Implementation details:
- Updated `schemas.layer1.yaml` `$defs.id64.maximum` to `18446744073709551615` and clarified the description to uint64.
- Removed the runtime override in S1 schema validation so the contract remains the sole authority.
- Revalidate existing S1 hurdle logs under the updated schema to confirm no further special casing is needed.

### Entry: 2026-01-11 07:51

Design element: Remove legacy trace fallback (S1.V strictness)
Summary: The current S1 validator has a compatibility fallback that accepts legacy trace rows with max totals; remove it so only the schema-defined final-row selection is allowed.
Why this exists today:
- Early S1 runs appended trace rows in event order, so the final totals row did not necessarily have the max `(rng_counter_after_hi, rng_counter_after_lo)`.
- The validator therefore used a fallback: if the max-counter row totals did not match event totals, it accepted the max-totals row and logged a compatibility message.
Why it must be removed:
- The S1.V contract is explicit that final-row selection is by max `(after_hi, after_lo)` with tie-breaking rules; accepting a different row undermines auditability and determinism.
- We now emit a final trace row with max counters for new runs, so the fallback is no longer needed for correctness and should not mask contract drift.
Brainstormed options before change:
- Option A: Keep fallback and tolerate legacy traces indefinitely (rejected: violates spec authority and hides broken traces).
- Option B: Remove fallback and force regeneration of S1 traces for legacy runs (chosen: contract purity; aligns with "no PASS, no read").
- Option C: Provide a one-off trace migration tool to append a compliant final row to legacy traces (deferred; can be added if historical runs must be preserved).
Planned changes (before implementation):
- In `packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/runner.py` remove the `trace_totals_row` fallback logic from `_validate_s1_outputs`.
- Keep strict validation: if the max-counter row totals do not match event totals, raise `rng_trace_missing_or_totals_mismatch`.
- Remove the "trace selection fallback used" log line so the run log reflects strict validation.
Operational implications:
- Existing runs with legacy traces will fail S1 validation; resolution is to re-run S1 on a fresh run_id (S0 then S1) or to explicitly migrate the trace file.
Validation plan:
- Re-run `make segment1a-s1` to confirm behavior on current run_id (expected: failure on legacy trace unless a new run is created).
- For a clean run_id, verify that the emitted final trace row passes strict selection with no fallback.

### Entry: 2026-01-11 07:52

Design element: S1 trace validation strictness (implementation)
Summary: Implemented the strict trace-row selection rule by removing the legacy fallback; validator now fails if the max-counter row totals do not match.
What changed and why:
- Removed the `trace_totals_row` selection branch from `_validate_s1_outputs`, so the validator no longer accepts a row selected by max totals when max counters do not match totals.
- The log line "trace selection fallback used (max totals row)" is removed to avoid implying compatibility behavior that is no longer allowed by the contract.
- This makes S1.V validation enforce the schema comment verbatim: final-row selection is based on max `(after_hi, after_lo)` with the tie-break rules, and totals must match the event-derived sums.
Expected operator impact:
- Any legacy run that has trace rows whose max-counter row does not carry final totals will now fail with `rng_trace_missing_or_totals_mismatch`.
- To recover: re-run S1 under a fresh run_id (recommended) or append a compliant final trace row to the legacy trace file using a one-off migration script if historical runs must be preserved.
Review checklist for this change:
- Confirm `_TraceAccumulator.finalize()` is still emitting a compliant final row on new runs (max counters + full totals).
- Confirm there is no remaining code path that selects a non-max-counter row during validation.

### Entry: 2026-01-11 07:52 (pre-implementation)

Design element: Progress logging with timing stats (S0.6/S0.7/S1)
Summary: Add elapsed time, rate, and ETA to loop progress logs so run logs show real-time throughput and remaining time.
Problem observed:
- Current loop logs (S0.6 eligibility, S0.7 hurdle_pi_probs, S1 hurdle emission) report only counts (e.g., 1000/10000) with no timing, making it hard to judge progress or detect stalls.
- AGENTS.md requires continuous heartbeat logs but doesn’t explicitly require rate/ETA; we want to codify this.
Desired behavior:
- Every progress log should include: `elapsed`, `rate` (rows/sec), `eta` (seconds), and current `idx/total`.
- The calculation must be monotonic-time-based to avoid wall-clock jumps.
Brainstormed options:
- Option A: Add a shared progress helper function in each module to compute `elapsed`, `rate`, `eta` (chosen: minimal change, no new dependencies).
- Option B: Add a global progress logger utility in `engine.core.logging` (deferred: more refactor, not required for this change).
- Option C: Use `StepTimer` everywhere (rejected: it measures step deltas, not per-loop throughput).
Plan (before coding):
- `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/eligibility.py`: add `time.monotonic()` start and include elapsed/rate/eta in the progress logs for S0.6.
- `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/runner.py`: add per-loop timing metrics to the S0.7 hurdle_pi_probs progress logs.
- `packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/runner.py`: add timing metrics to the S1 hurdle event emission progress logs; consider adding validation-loop progress if validation-only runs become lengthy.
- `AGENTS.md`: extend logging guidance to require loop progress logs to include elapsed, rate, and ETA.
Validation plan:
- Run S0/S1 and confirm log lines include `elapsed`, `rate`, `eta`.
- Ensure the rate is non-zero once progress starts and ETA decreases as counts approach total.

### Entry: 2026-01-11 07:53

Design element: Progress logging with timing stats (implementation)
Summary: Implemented elapsed/rate/ETA logging for S0.6, S0.7, and S1 emission loops and codified the requirement in AGENTS.md.
What changed and where:
- `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/eligibility.py`: added `start_time = time.monotonic()` and extended the S0.6 progress log to include `elapsed`, `rate`, `eta` for each `idx/total` heartbeat.
- `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/runner.py`: added per-loop timing stats for the S0.7 hurdle_pi_probs emission logs.
- `packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/runner.py`: added per-loop timing stats for hurdle event emission progress logs.
- `AGENTS.md`: added a requirement that all long-running loops include elapsed/rate/ETA in progress logs.
Implementation specifics:
- Timing uses `time.monotonic()` for stability; `rate = idx / elapsed` (guarded for zero), `eta = (total - idx) / rate` (guarded for zero).
- Log format preserves the prior prefix and adds `(elapsed=…, rate=…/s, eta=…)` for scanability in run logs.
Follow-up considerations:
- If validation-only runs become slow, consider adding similar timing logs inside `_validate_s1_outputs` for event/trace scans, but keep log volume bounded.

## S2 - NB Outlets

### Entry: 2026-01-11 08:16 (pre-implementation)

Design element: S2 contracts review + implementation planning
Summary: Reviewed S2-related contracts (schemas/dictionary/policy) and drafted a concrete, state-by-state implementation plan plus decisions/open issues to resolve before coding.
Contracts reviewed (key S2 bindings):
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml`: confirmed `gamma_component`, `poisson_component`, and `nb_final` schemas; `nb_final` requires non-consuming envelope (`blocks=0`, `draws="0"`), and payload fields `mu`, `dispersion_k`, `n_outlets >= 2`, `nb_rejections >= 0`. `poisson_component.context` supports `nb` and `ztp` (NB context must set `attempt >= 1`).
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml`: S2 streams are `rng_event_gamma_component`, `rng_event_poisson_component`, and `rng_event_nb_final`, gated by `rng_event_hurdle_bernoulli` with predicate `is_multi == true`. Producers are fixed (`1A.nb_and_dirichlet_sampler`, `1A.nb_poisson_component`, `1A.nb_sampler`), and partitions are `{seed, parameter_hash, run_id}`.
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/artefact_registry_1A.yaml`: S2 depends on `hurdle_coefficients` (for `beta_mu`), `nb_dispersion_coefficients` (for `beta_phi`), and `validation_policy` for CUSUM corridor params; RNG event schemas are bound to `schemas.layer1.yaml`.
- `config/layer1/1A/policy/validation_policy.yaml`: currently includes `cusum.reference_k`, `cusum.threshold_h`, plus `cusum.alpha_cap` and a note (see mismatch below).
Contract mismatch / decisions to resolve before coding:
- `validation_policy.yaml` includes `cusum.alpha_cap`, but `schemas.layer1.yaml#/policy/validation_policy` disallows extra fields. This will fail strict schema validation and violates the "fail closed" stance.
  - Decision proposal (pending confirmation): remove `alpha_cap` from the policy file to align with schema; S2 corridor logic will only consume `reference_k` and `threshold_h` as specified.
  - Alternative (if alpha_cap is required): update the schema + spec to include `alpha_cap` and document how it changes corridor math. This is currently out of scope for S2, so default is to align policy file with schema.
Implementation plan (detailed, by substate):
- S2.1 entry gate + inputs:
  - Load S1 hurdle events and build a gate set of `merchant_id` where `is_multi == true`. Enforce branch purity: if `is_multi == false`, skip all S2 outputs for that merchant; if any S2 event is present later for such a merchant, validation must fail.
  - Assemble design vectors using S0/S1 encoders (frozen order) and GDP-per-capita (`world_bank_gdp_per_capita_20250415`) keyed by `home_country_iso`.
  - Load `beta_mu` and `beta_phi` from governed artefacts (`hurdle_coefficients.yaml`, `nb_dispersion_coefficients.yaml`) using `parameter_hash`.
  - Carry lineage fields `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id` into the NB context; do not recompute.
- S2.2 NB link evaluation:
  - Compute `eta_mu = dot64_no_fma(beta_mu, x_mu)` and `eta_phi = dot64_no_fma(beta_phi, x_phi)` using deterministic Neumaier accumulation (S0 numeric policy). No BLAS or vectorized reorder.
  - Exponentiate to `mu`, `phi` in binary64; guard `isfinite` and `> 0`, else `ERR_S2_NUMERIC_INVALID` (merchant-scoped abort; no S2 events emitted for that merchant).
  - Serialize `mu`/`phi` using shortest round-trip decimal for binary64 (use `f64_to_json_shortest` when writing `nb_final`).
- S2.3 Gamma/Poisson attempt (one attempt per loop iteration):
  - Use Philox-based substreams: `gamma_nb` (module `1A.nb_and_dirichlet_sampler`) and `poisson_nb` (module `1A.nb_poisson_component`).
  - Gamma sampler: MT1998 with Box-Muller, no caching; implement per-attempt draw accounting `2*J + A + (phi<1 ? 1 : 0)`.
  - Poisson sampler: S0.3.7 inversion for `lambda < 10`, PTRS for `lambda >= 10`, variable draws; measure consumption with counters.
  - Emit `gamma_component` then `poisson_component` per attempt with full envelope; `context="nb"`, `index=0` for gamma; `attempt` is 1-based in payload but non-authoritative.
  - After each RNG event, append a cumulative `rng_trace_log` row per the S2.6 trace duty.
- S2.4 Rejection loop:
  - Loop attempts until `K >= 2`, counting `r` rejections; no RNG outside the S2.3 attempt step.
  - No hard cap; ensure logs include elapsed/rate/ETA for long runs.
- S2.5 Finalizer:
  - Emit exactly one `nb_final` per merchant with payload `{mu, dispersion_k=phi, n_outlets=N, nb_rejections=r}`.
  - Non-consuming envelope: `rng_counter_before == rng_counter_after`, `blocks=0`, `draws="0"`, module `1A.nb_sampler`, label `nb_final`.
- S2.6 Counter discipline & trace:
  - Ensure counters are monotone and non-overlapping per `(merchant_id, substream_label)`.
  - Maintain per-stream totals in `rng_trace_log` to reconcile `blocks_total` and `draws_total`; no inference of draws from counters.
- S2.7 corridors (validation stage):
  - Add validator logic (likely in S9 validation module) to compute `rho_rej`, `Q0.99`, and CUSUM with policy `reference_k`/`threshold_h`. Fail closed if policy missing.
  - Exclude merchants with invalid `alpha` (non-finite or out of (0,1]) and log `ERR_S2_CORRIDOR_ALPHA_INVALID`.
- S2.8/2.9 structural checks:
  - Validation must enforce coverage (Gamma+Poisson before `nb_final`), composition identity `lambda == (mu/phi) * gamma_value`, and non-consuming `nb_final`.
  - Confirm no Parquet outputs are written for S2; only the three JSONL streams plus trace.
Review checklist before coding:
- Verify existing RNG helpers cover Gamma MT1998 and Poisson S0.3.7 with explicit draw budgets and counter tracking; if not, add minimal primitives.
- Confirm run writer supports `rng_trace_log` updates after each event in S2 (reuse trace accumulator from S1 if available).
- Decide how to resolve `validation_policy.yaml` mismatch (remove `alpha_cap` vs update schema/spec); do this before S2 corridor validation is wired.
Validation plan (for later):
- Run `make segment1a-s2` once S2 is implemented; inspect `gamma_component`, `poisson_component`, `nb_final`, and `rng_trace_log` for coverage, counters, and non-consuming final.
- Add a small deterministic shard to check `nb_final` echoes `mu`/`phi` exactly and `nb_rejections` matches reconstructed attempt index.

### Entry: 2026-01-11 08:21 (pre-implementation)

Design element: CUSUM alpha cap policy for S2 corridors (schema/spec update)
Summary: Expand the validation policy schema and S2.7 spec to support an optional `alpha_cap` so near-1 acceptance probabilities cannot dominate the CUSUM drift metric.
Problem observed:
- The current `validation_policy.yaml` already includes `cusum.alpha_cap`, but the schema rejects extra fields.
- In S2.7, $\alpha_m$ is derived from $(\mu,\phi)$ and can approach 1, which drives $\mathrm{Var}(r_m)$ toward 0; this can inflate the standardized residual $z_m$ and dominate the CUSUM even for a single rejection.
Brainstormed options:
- Option A (chosen): Add `alpha_cap` to the policy schema and update S2.7 spec to cap $\alpha_m$ at `alpha_cap` (default 0.999) before computing $\mathbb{E}[r_m]$ and $\mathrm{Var}(r_m)`. This preserves existing math but prevents extreme $\alpha$ values from dominating.
- Option B: Clip $z_m$ directly to a max magnitude (rejected: adds a new, less interpretable parameter and changes the statistic in an opaque way).
- Option C: Impose a minimum variance floor in the denominator (rejected: hides the same issue without tying it to model probabilities).
Plan (before coding):
- Update `schemas.layer1.yaml#/policy/validation_policy` to allow `cusum.alpha_cap` with domain `(0,1]` and a clear description.
- Update S2.7 spec in `state.1A.s2.expanded.md` to define the capped acceptance probability $\tilde{\alpha}_m=\min(\alpha_m,\texttt{alpha_cap})$ and use $\tilde{\alpha}_m$ in $\mathbb{E}[r_m]$ and $\mathrm{Var}(r_m)$.
- Update `validation_policy_authoring-guide.md` to explain when/why to set `alpha_cap` and document its default.
Validation plan:
- After updating the spec, ensure the current `validation_policy.yaml` validates against the schema with `alpha_cap` present.
- During corridor validation implementation, verify the cap is applied consistently in the $\alpha_m$ computation (and log the cap value in metrics for auditability).

### Entry: 2026-01-11 08:27

Design element: CUSUM alpha cap policy for S2 corridors (implementation)
Summary: Updated the schema and S2 spec to accept and define `cusum.alpha_cap`, and documented authoring guidance.
What changed and why:
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml`: added `cusum.alpha_cap` with domain `(0,1]` to accept the policy file and enable explicit caps for near-1 acceptance probabilities.
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s2.expanded.md`: defined capped acceptance probability $\tilde{\alpha}_m = \min(\alpha_m,\texttt{alpha_cap})$ for CUSUM math and clarified optional behavior when `alpha_cap` is absent.
- `docs/model_spec/data-engine/layer-1/specs/data-intake/1A/validation_policy_authoring-guide.md`: added `alpha_cap` to the schema example, semantics, and checklist so policy authors know how to set it.
Notes:
- This is a spec/schema alignment change only; corridor implementation will apply the cap when S2 validation is wired.

### Entry: 2026-01-11 08:32 (pre-implementation)

Design element: S2 RNG substream derivation vs S2.6 formula mismatch
Summary: Decide which keyed mapping to use for S2 substreams; the S2.6 text mentions `ctr:1A` but S0.3.3 defines `mlr:1A` master/material mapping already used in S1.
Observation:
- S0.3.3 defines the authoritative keyed mapping based on `M = SHA256(UER("mlr:1A.master") || manifest_fingerprint_bytes || LE64(seed))` and `H = SHA256(M || UER("mlr:1A") || UER(label) || SER(ids))`.
- S2.6 includes a formula using `SHA256("ctr:1A" || ...)`, which conflicts with S0.3.3 and the existing S1 RNG implementation.
Decision (chosen):
- Use the S0.3.3 mapping (`mlr:1A.master` + `mlr:1A`) to stay consistent with the already-implemented S1 sampler and the core RNG spec; treat the `ctr:1A` occurrence as a spec typo in S2.6.
Implementation plan:
- Reuse the existing Philox helpers (as in S1) to derive substreams from master material and merchant_u64 for labels `gamma_nb`, `poisson_nb`, and `nb_final`.
- Document this decision in the logbook to keep the spec deviation explicit and auditable.

### Entry: 2026-01-11 08:40 (pre-implementation)

Design element: S2 runner behavior (resume, merchant-scoped aborts, and validation scope)
Summary: Define how the S2 runner will handle resuming runs, merchant-scoped numeric aborts, and validation checks before coding.
Decisions:
- Resume logic: if `gamma_component`, `poisson_component`, `nb_final` outputs exist and the trace log already contains S2 substreams (`gamma_nb`, `poisson_nb`, `nb_final`), treat the run as already emitted and only re-validate; partial outputs are treated as a hard error requiring cleanup.
- Merchant-scoped aborts: numeric invalids (`ERR_S2_NUMERIC_INVALID`), missing inputs, or missing hurdle gate for a merchant will skip that merchant with a warning log (no S2 events emitted), rather than aborting the entire run. Structural validation still fails the run when contracts are violated.
- Validation scope in S2 runner: implement schema checks for all S2 streams, counter discipline, coverage/cardinality, composition identity (`lambda == (mu/phi) * gamma_value`), and corridor metrics with `alpha_cap` applied; fail fast on breaches so S2 cannot proceed to S3 unless green.
Implementation notes:
- Use `sealed_inputs_1A.json` to resolve the exact parameter and reference files used in S0 (avoid “latest” drift).
- Keep event ordering deterministic by iterating merchants in ascending `merchant_id`.

### Entry: 2026-01-11 09:15 (pre-implementation)

Design element: S2 runner correctness fixes + CLI/Makefile wiring for execution
Summary: Address two correctness gaps in the S2 runner (ingress schema validation and nb_final substream counters) and add the CLI + Makefile target to run S2 via `make`.
Observations driving the change:
- The S2 runner currently validates merchant rows against the `schemas.1A` pack, not the ingress schema pack (`schemas.ingress.layer1.yaml`). This is the same mismatch that caused the "row is not of type array" failure earlier in S0 and will reject valid merchant rows.
- The `nb_final` event currently uses `poisson_nb` substream counters, which conflates substream lineage and breaks the S2.6 requirement that each substream has its own counters and trace totals.
- There is no S2 CLI or Makefile target yet, so the state cannot be run directly with `make segment1a-s2` (required for the green-run validation loop).
Decisions (before coding):
- Load the ingress schema pack (`ingress.layer1`) alongside `schemas.layer1`, and validate merchant rows with the ingress schema. Remove the unused `schemas.1A` load in S2.
- Derive a dedicated `nb_final` substream per merchant, and use its counter snapshot for the non-consuming `nb_final` event (before == after, blocks=0, draws="0"). Keep `poisson_nb` counters only for the poisson component.
- Add `engine.cli.s2_nb_outlets` mirroring the S1 CLI shape (contracts layout/root, runs root, external roots, optional run_id), and wire a Makefile target (`segment1a-s2`) plus `engine-s2`.
Implementation plan:
- Update `run_s2` to load `ingress.layer1` schema pack and pass it into `_build_merchant_frame`.
- In the emission loop, create `final_stream = derive_substream_state(master_material, SUBSTREAM_FINAL, merchant_id)` and use it only for `nb_final` counters/trace rows.
- Add the new CLI module and Makefile variables (`SEG1A_S2_RUN_ID`, `SEG1A_S2_ARGS`, `SEG1A_S2_CMD`) plus the target lines.
Validation plan:
- Run `python -m py_compile` on the new/updated S2 modules.
- Run `make segment1a-s2` against the current run_id, inspect the run log for validation errors, and iterate fixes until green.

### Entry: 2026-01-11 09:21 (pre-implementation)

Design element: Seal `validation_policy` into S0 sealed_inputs for S2 determinism
Summary: S2 run failed because `sealed_inputs_1A` does not include `validation_policy`; plan is to update S0 to include it in the registry dependency closure and re-run S0/S1 before S2.
Observed failure:
- `make segment1a-s2` failed with `InputResolutionError: sealed_inputs_1A missing required assets: ['validation_policy']`.
- The current S0 sealed_inputs is built from the registry dependency closure of reference + param assets; `validation_policy` is in the registry but is not part of that closure.
Decision (before coding):
- Add `validation_policy` to the `registry_names` set in S0 so it is sealed, hashed into the manifest, and available for S2 validation (no ad-hoc fallback to config files).
- Do not mutate existing run directories; instead, re-run S0 and S1 to produce a new run_id with a corrected sealed_inputs list, then run S2 against that new run.
Implementation plan:
- Update `s0_foundations/runner.py` to include `validation_policy` in the registry names used for dependency closure.
- Re-run `make segment1a-s0` and `make segment1a-s1` to regenerate run outputs with the updated sealed inputs.
- Re-run `make segment1a-s2` and iterate fixes until green.

### Entry: 2026-01-11 09:25 (pre-implementation)

Design element: Fix validation_policy semver regex in schema
Summary: S2 validation failed because the semver regex in `schemas.layer1.yaml` is over-escaped, rejecting valid `semver: "1.3.4"` values.
Observed failure:
- `make segment1a-s2` failed during `_load_validation_policy` with SchemaValidationError.
- Manual validation shows semver does not match the pattern `^[0-9]+\\\\.[0-9]+\\\\.[0-9]+$` (schema is escaping the dot twice).
Decision (before coding):
- Update `schemas.layer1.yaml#/validation_policy/semver.pattern` to use a single escaped dot (`^[0-9]+\.[0-9]+\.[0-9]+$`), so standard semver strings like `1.3.4` validate.
- Keep the schema strict otherwise; do not relax additionalProperties or other requirements.
Implementation plan:
- Edit the schema pattern for `validation_policy.semver` and re-run S2 validation.

### Entry: 2026-01-11 09:28

Design element: S2 runner corrections + CLI/Makefile wiring (implementation)
Summary: Implemented the S2 runner fixes and added the S2 CLI/Makefile entry point so S2 can run via `make segment1a-s2`.
What changed:
- `packages/engine/src/engine/layers/l1/seg_1A/s2_nb_outlets/runner.py`: load the ingress schema pack (`ingress.layer1`) and validate merchant rows against it; removed the incorrect use of `schemas.1A` for ingress validation.
- `packages/engine/src/engine/layers/l1/seg_1A/s2_nb_outlets/runner.py`: introduced a dedicated `nb_final` substream (`derive_substream_state(..., SUBSTREAM_FINAL, merchant_id)`) and used its counter snapshot for the non-consuming `nb_final` event envelope.
- `packages/engine/src/engine/cli/s2_nb_outlets.py`: added an S2 CLI (contracts layout/root, runs root, external roots, optional run_id) mirroring the S1 CLI.
- `makefile`: added `SEG1A_S2_RUN_ID`, `SEG1A_S2_ARGS`, and `SEG1A_S2_CMD`, plus `segment1a-s2` and `engine-s2` targets.
Why this resolves the issues:
- Using the ingress schema aligns S2 with the same merchant validation contract as S0, preventing false schema errors from the `schemas.1A` pack.
- The `nb_final` event now has its own substream lineage, satisfying S2.6 counter/trace segregation.

### Entry: 2026-01-11 09:30

Design element: S0 sealed inputs include validation_policy (implementation)
Summary: Updated S0 to seal the validation policy so S2 can load it deterministically.
What changed:
- `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/runner.py`: added `validation_policy` to the registry dependency closure (`registry_names`), so it is recorded in `sealed_inputs_1A` and hashed into the manifest.
Operational impact:
- S0/S1/S2 were re-run to produce a new run_id with the corrected sealed inputs; S2 completed with run_id `396e3a41eadd2e0c5daf44a659ac8876` and manifest_fingerprint `eaf68eec57f5e7bd4dece0793c99a95615522e212a539057989b1cba311e0e14`.

### Entry: 2026-01-11 09:32

Design element: validation_policy semver regex (implementation)
Summary: Fixed the over-escaped semver regex in the schema so `semver: "1.3.4"` validates.
What changed:
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml`: updated `validation_policy.semver.pattern` to use single-escaped dots (`^[0-9]+\.[0-9]+\.[0-9]+$`).

## S3 - Cross-border Universe (placeholder)
### Entry: 2026-01-11 12:40 (pre-implementation)

Design element: S3 contract review (inputs/outputs/policies/dictionary/schema)
Summary: Reviewed the authoritative S3 spec, policy authoring guides, dataset dictionary, schema anchors, and current config policies to identify gating requirements, optional outputs, and schema/policy mismatches before coding.
Sources reviewed (authoritative):
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s3.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml` (S3 dataset IDs/paths/ordering)
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/artefact_registry_1A.yaml` (policy/artefact dependencies)
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml` (policy schemas)
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.1A.yaml` (S3 output schemas)
- `docs/model_spec/data-engine/layer-1/specs/data-intake/1A/policy.s3.rule_ladder_authoring-guide.md`
- `docs/model_spec/data-engine/layer-1/specs/data-intake/1A/policy.s3.base_weight_authoring-guide.md`
- `docs/model_spec/data-engine/layer-1/specs/data-intake/1A/policy.s3.thresholds_authoring-guide.md`
Inputs & outputs per spec:
- Inputs: S1 hurdle (`rng_event_hurdle_bernoulli`), S2 nb_final (`rng_event_nb_final`), merchant ids (ingress), ISO canonical list, rule ladder policy (required), base-weight policy (optional if priors enabled), thresholds policy (optional if bounds enabled), and optional currency-to-country map (only if rule ladder references it).
- Outputs: `s3_candidate_set` is required. `s3_base_weight_priors`, `s3_integerised_counts`, and `s3_site_sequence` are optional but explicitly defined in the dictionary and schemas.
Key invariants:
- No RNG; `candidate_rank(home)=0`; ranks contiguous; reason/tag vocab closed; priors are fixed-dp strings and never used for ordering; integerised counts sum to N; residual_rank persisted; outputs are parameter-scoped with embedded lineage equal to path partition.
Contract mismatches found (must resolve before implementation):
- `policy.s3.rule_ladder.yaml` contains `reason_code_to_rule_id`, but `schemas.layer1.yaml#/policy/s3_rule_ladder` disallows it (`additionalProperties: false`). This is a spec/schema mismatch because S3.3 requires a closed mapping from reason_code to rule_id for ordering-key reconstruction.
- `schemas.layer1.yaml#/policy/s3_base_weight` and `#/policy/s3_thresholds` use an over-escaped semver pattern (same issue fixed earlier for validation_policy), causing valid semver values to fail schema validation.
- `config/layer1/1A/policy/s3.base_weight.yaml` parses `w_max: 1.0e12` as a string under PyYAML, which fails JSON-Schema numeric validation.
Decisions pending (before coding):
- Extend the `s3_rule_ladder` schema to allow `reason_code_to_rule_id` (preferred) so the policy can carry the required mapping; or redesign S3.3 ordering-key reconstruction to avoid the mapping (not recommended because spec requires it).
- Fix semver regex in `schemas.layer1.yaml` for `s3_base_weight.version` and `s3_thresholds.semver` to accept standard semver.
- Normalize `w_max` in `s3.base_weight.yaml` to a numeric literal (e.g., `1000000000000.0`) so schema validation passes deterministically.
Plan for resolution:
- Update schemas to accept the required policy fields and correct semver patterns before implementing S3 validation logic.
- Adjust policy literals to parse as numeric types when required by schema (no quotes for numeric fields).

### Entry: 2026-01-11 12:40 (pre-implementation)

Design element: S3 implementation plan (S3.1–S3.5 pipeline + validation)
Summary: Planned the deterministic S3 pipeline with explicit gating, ordering, optional priors, integerisation, and sequencing, aligned to the contract and current policy files.
S3.1 Rule ladder evaluation (deterministic):
- Load `policy.s3.rule_ladder.yaml` (sealed input), validate against schema (after schema fix), and precompute:
  - `precedence_order` → rank map.
  - closed vocab sets (`reason_codes`, `filter_tags`) for validation.
  - `country_sets` expansion table (ISO2 only).
  - `reason_code_to_rule_id` mapping (must exist and be total).
- For each merchant:
  - Evaluate all rules using the DSL predicates (TRUE, IN_SET, CHANNEL_IN, MCC_IN, N_GE, AND/OR/NOT).
  - Collect `Fired` and compute `rule_trace` order by `(precedence_rank, priority, rule_id)`.
  - Choose exactly one decision source (first decision-bearing rule in `rule_trace`).
- Determine `eligible_crossborder` from precedence logic (DENY overrides ALLOW etc.).
S3.2 Candidate universe (deterministic, no RNG):
- If `eligible_crossborder` false: candidate set is `{home}` only.
- Else compute `ADMITS` and `DENIES` by unioning admit/deny lists from fired rules; remove home from foreigns; final `C = {home} ∪ FOREIGN`.
- Build per-row `reason_codes` and `filter_tags`:
  - Home row always has `filter_tags += ["HOME"]` and includes the decision-source reason code.
  - Foreign rows include admit-bearing rule reason_codes and row_tags; tags and codes are de-duplicated and sorted A–Z.
S3.3 Ordering (`candidate_rank` authority):
- Home is always `candidate_rank=0`.
- For each foreign row, reconstruct admit-rule IDs using `reason_code_to_rule_id` and compute the ordering key:
  - `K(r) = (precedence_rank, priority, rule_id)` for each admit rule `r`.
  - `Key1(i) = min_lex K(r)` for the row.
- Sort foreigns by `(Key1, country_iso)` and assign contiguous ranks starting at 1.
S3.4 Base-weight priors (optional, but enabled if policy exists):
- Load `policy.s3.base_weight.yaml`, validate schema.
- Compute `log_w = beta0 + beta_home*I(is_home) + beta_rank*candidate_rank`.
- Clamp log_w and w; quantise to `dp` using deterministic half-even rounding; emit fixed-dp strings in `s3_base_weight_priors`.
S3.5 Integerisation (optional, but enabled if counts are owned by S3):
- Use `N` from S2 and candidate set (ordered).
- If priors enabled: use quantised `w_i^⋄` for shares; else equal weights.
- Apply largest-remainder method with `dp_resid=8`, residual sort descending, tie-break by ISO A–Z.
- If `policy.s3.thresholds.yaml` enabled: compute bounds `L_i,U_i` per spec (bounded Hamilton); fail on infeasible bounds.
- Emit `s3_integerised_counts` with `residual_rank` and ensure `Σ count_i = N`.
S3.5 Sequencing & IDs (optional):
- If S3 owns `s3_site_sequence`, emit `site_order = 1..count_i` per `(merchant_id,country_iso)`; `site_id` optional (decide whether to emit).
Validation & resumability:
- Validate all outputs with schema + deterministic checks (rank contiguity, home presence, ordering-key match, priors dp consistency, counts sum, residual_rank order, bounds feasibility).
- If outputs already exist for the run/parameter_hash, run validation-only; if partial outputs exist, fail fast to avoid append.
Observability:
- Add progress logs with elapsed/rate/ETA during merchant loops (candidate build + integerisation).
Open decisions to confirm before coding:
- Whether S3 owns `s3_base_weight_priors`, `s3_integerised_counts`, and `s3_site_sequence` for 1A (current policies exist and dictionary declares outputs; default plan is to implement all three).
- Whether `site_id` should be emitted or left null (schema allows null).

### Entry: 2026-01-11 13:14 (pre-implementation)

Design element: S3 decision semantics + output ownership (clarification before coding)
Summary: Capture the implementation interpretation for `eligible_crossborder` when no ALLOW/DENY rule fires, and confirm S3 will emit all optional outputs with `site_id` left null.
Decision details:
- `eligible_crossborder` mapping: follow the spec precedence law (DENY then ALLOW); if neither fires, the decision source is the first decision-bearing rule among {CLASS, LEGAL, THRESHOLD, DEFAULT}. In the absence of an explicit allow/deny flag on these rules, interpret **ALLOW only when the decision source precedence is `ALLOW`**; all other precedence classes imply `eligible_crossborder=false`. This keeps default behavior conservative and aligns with the `DEFAULT_DENY` policy pattern.
- Output ownership: S3 will emit `s3_candidate_set` (required) plus the optional `s3_base_weight_priors`, `s3_integerised_counts`, and `s3_site_sequence`, since policies exist and the dictionary defines these datasets.
- `site_id` emission: leave `site_id` null for now (schema allows null), while still emitting deterministic `site_order` and preserving row ordering. A later state can add IDs if needed.

### Entry: 2026-01-11 13:44 (pre-implementation)

Design element: S3 runner structure + gating + output validation approach
Summary: Define the concrete implementation mechanics for S3 (run receipt loading, policy evaluation, candidate build, ordering, priors, integerisation, sequencing, and deterministic validation) before coding.
Decisions and implementation plan:
- Runner structure: implement `engine.layers.l1.seg_1A.s3_crossborder.runner` plus `engine.cli.s3_crossborder` with the same contract/runs-root switches as S1/S2.
- Run context: load run_receipt.json (seed, parameter_hash, manifest_fingerprint, run_id); attach run_log file handler; load dataset dictionary, artefact registry, and schema packs (`schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.1A.yaml`).
- Sealed inputs: resolve policy and reference paths strictly from `sealed_inputs_1A` (rule ladder, base-weight policy, thresholds policy, iso3166 canonical, merchant_ids), and fail if any required asset is missing.
- Gating logic (per spec): process only merchants with `is_multi==true` and an `nb_final` row with `n_outlets >= 2`; treat inconsistent event coverage as a hard failure (e.g., nb_final exists for non-multi, or is_multi but nb_final missing).
- Rule ladder evaluation: evaluate all predicates; build `fired` set; order trace by `(precedence_rank, priority, rule_id)`; select decision source per precedence law; compute `eligible_crossborder` using DENY/ALLOW precedence only.
- Candidate rows: home row always included; home `reason_codes` = union of all fired reason codes (A-Z), `filter_tags` = union of fired tags plus `HOME` (A-Z). Foreign rows use admit-bearing fired rules only: `reason_codes` from admitting rules, `filter_tags` = merchant_tags + row_tags; enforce closed vocab and A-Z sort.
- Ordering authority: compute admission key from `reason_code_to_rule_id` mapping (must be total and one-to-one); order foreigns by `Key1=(precedence_rank, priority, rule_id)` then ISO A-Z; assign `candidate_rank` with home at 0.
- Base-weight priors: implement log-linear policy per authoring guide; clamp log_w and w; quantise with round-to-dp (binary64, half-even) and emit fixed-dp string; fail if sum of quantised weights is zero.
- Integerisation: implement unbounded Hamilton or bounded Hamilton (if thresholds policy enabled) with `dp_resid=8`, residual ordering by residual DESC then ISO A-Z then candidate_rank; assign `residual_rank` for every row and ensure `sum(count)=N`.
- Sequencing: emit `s3_site_sequence` from integerised counts with `site_order=1..count_i`, `site_id=null`.
- Output handling: compute expected outputs deterministically; if all four output datasets already exist for this parameter_hash, validate by comparing to expected DataFrames and skip write; if partial outputs exist, fail and ask for cleanup.
- Validation coverage: rely on internal invariant checks and deterministic comparison rather than the generic JSON-schema adapter for S3 outputs (adapter does not support array-typed columns yet).
- Observability: add step-level timer logs and per-merchant progress logs (elapsed, rate, eta) for the candidate + integerisation loop.

### Entry: 2026-01-11 14:05

Design element: S3 implementation (runner/CLI/Makefile) + schema fix
Summary: Implemented the full S3 cross-border pipeline and wired a CLI/Makefile target; fixed the s3_thresholds semver schema + indentation to unblock policy validation; validated outputs against recomputed results.
What changed and why:
- Added `packages/engine/src/engine/layers/l1/seg_1A/s3_crossborder/runner.py` with the deterministic S3 flow: sealed-input resolution, S1/S2 event validation, rule ladder evaluation, candidate construction, ordering keys, base-weight priors, bounded Hamilton integerisation, and site sequencing.
- Added strict gates for missing/extra hurdle events and nb_final inconsistencies (nb_final for non-multi, multi missing nb_final) so S3 fails on broken upstream coverage rather than silently skipping.
- Enforced policy schema validation for rule ladder, base-weight, and thresholds; added a sanity check that `reason_code_to_rule_id` references actual rule_ids.
- Implemented deterministic output handling: compute expected DataFrames, compare to existing outputs when resuming, error on partial outputs, and use atomic parquet writes to the dictionary-resolved paths.
- Added `packages/engine/src/engine/cli/s3_crossborder.py` and Makefile targets/vars (`SEG1A_S3_*`, `segment1a-s3`, `engine-s3`) to run S3 via `make`.
Fixes during the run:
- Updated `schemas.layer1.yaml` `s3_thresholds.semver` pattern to single-escaped dots and fixed indentation under `properties:` after a YAML parse error.
Validation notes:
- `make segment1a-s3` now completes with outputs emitted under `data/layer1/1A/s3_*` (parameter_hash-scoped), and a subsequent rerun validates existing outputs successfully.

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
