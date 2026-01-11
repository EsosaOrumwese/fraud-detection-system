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
trace using S0’s keyed Philox substreams.
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
