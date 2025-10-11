# S4 ZTP Target Package

This package will host every layer required to implement the State-4 zero-truncated Poisson (ZTP) sampler. During preparation we fix the wiring so kernels and writers can land without re-reading the expanded spec each time.

## Current Status
- `contexts.py` exposes immutable bundles for deterministic inputs (hyperparameters, merchant view, lineage). These are the only concrete types checked into the repo so far.
- L0/L1/L2/L3 packages are placeholders; their READMEs and AGENTS remain minimal until implementation lands.

## Inputs the Runner Must Provide
- **Gates:** `is_multi` from the S1 hurdle stream and `is_eligible` from S3 eligibility flags. If either is `false` the merchant must never reach the sampler.
- **Counts:** `n_outlets` from the S2 `nb_final` non-consuming record (integer ≥ 2) and admissible foreign count `A` derived from the S3 candidate set (excludes the home country).
- **Feature:** Optional bounded scalar `X` in `[0, 1]` with a deterministic default of `0.0` when absent.

## Governed Artefacts (participate in `parameter_hash`)
- ZTP link coefficients `theta0`, `theta1`, `theta2` (see data-intake notes §“S4 link”).
- `MAX_ZTP_ZERO_ATTEMPTS` cap (default 64) and `ztp_exhaustion_policy` (`"abort"` or `"downgrade_domestic"`).
- Eligibility rule bundle already sealed in S0 (required to keep branch purity aligned with S3).

## Failure Vocabulary Mapping
- `NUMERIC_INVALID`: raised when the binary64 `lambda_extra` is NaN/Inf/≤0.
- `BRANCH_PURITY`: any attempt to emit S4 rows for merchants that failed S1/S3 gates.
- `A_ZERO_MISSHANDLED`, `ATTEMPT_GAPS`, `FINAL_MISSING`, `MULTIPLE_FINAL`, `CAP_WITH_FINAL_ABORT`, `TRACE_MISSING`, `REGIME_INVALID`, `RNG_ACCOUNTING`: all scoped per merchant and expected to reuse the existing `S0Error` taxonomy with new codes if required.
- Run-scoped structural failures reuse `E_PARTITION_MISMATCH` and friends to maintain the global ledger.

## Resume & Trace Expectations
- Writers must inspect existing `poisson_component`, `ztp_rejection`, `ztp_retry_exhausted`, and `ztp_final` logs to recover the latest attempt index and Philox counters before resuming.
- Every event append must be followed immediately by a cumulative `rng_trace_log` row for `(module="1A.ztp_sampler", substream_label="poisson_component")`.

These notes capture the preparation work; implementation phases will flesh out subpackages without revisiting the policies documented here.
