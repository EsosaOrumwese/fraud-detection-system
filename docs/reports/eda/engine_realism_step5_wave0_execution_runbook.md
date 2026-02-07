# Engine Realism - Step 5 Wave-0 Execution Runbook
Date: 2026-02-07  
Baseline reference run: `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`  
Scope: Execute and evaluate `Wave 0` only (`WP-001`, `WP-002`, `WP-003`) from Step 4.  
Status: Execution planning + gate protocol. No fixes are implemented in this document.

---

## 0) Objective
Step 5 operationalizes Step 4 for the first execution slice:
1. Run a controlled Wave-0 experiment that targets only the 6B critical blockers.
2. Produce reproducible gate evidence for pass/fail decisions.
3. Stop for explicit review before any Wave-1 work.

Wave-0 target gaps:
- `1.1` 6B truth-label collapse.
- `1.2` 6B bank-view stratification collapse.
- `1.3` 6B case timeline invalidity.

---

## 1) Why Wave 0 First
These are platform-blocking realism defects in the final truth surface. If Wave 0 fails:
- all downstream model realism claims remain invalid;
- wave-level improvements in 3B/6A/2B/3A will not rescue final label realism;
- statistical grading cannot move to `B/B+`.

---

## 2) Inputs and Authorities
Primary inputs:
- `docs/reports/reports/eda/engine_realism_baseline_gap_ledger.md`
- `docs/reports/reports/eda/engine_realism_step2_root_cause_trace.md`
- `docs/reports/reports/eda/engine_realism_step3_hypothesis_acceptance_plan.md`
- `docs/reports/reports/eda/engine_realism_step4_execution_backlog.md`

Execution/control surfaces:
- `Makefile` targets `segment6b-s0..segment6b-s5`
- 6B policy files under `config/layer3/6B/`
- 6B implementation path `packages/engine/src/engine/layers/l3/seg_6B/`

---

## 3) Wave-0 Work Package Scope Lock
Allowed in Wave 0:
- `WP-001` (`1.1`) truth mapping key semantics.
- `WP-002` (`1.2`) bank-view conditionality.
- `WP-003` (`1.3`) case delay/timeline monotonicity.

Not allowed in Wave 0:
- Any changes to `3B`, `6A`, `2B`, `3A`, `1A`, `1B`, `2A`, `5A`, `5B`.
- Any policy retuning outside 6B truth/bank/case surfaces.

Purpose of lock:
- preserve attribution: if Wave-0 gates move, cause is local to final truth generation.

---

## 4) Baseline Anchor and Repro Seeds
Mandatory seed set for gating:
- `42`, `7`, `101`, `202`

Comparison anchor:
- Seed-42 baseline is frozen at `c25a2675fbfbacd952b13bb594880e92`.

Evidence rule:
- Report per-seed and aggregate summaries.
- A Wave-0 pass requires both:
  - all critical gates pass per seed;
  - no cross-seed instability breach (Section 9.3).

---

## 5) Execution Modes
### 5.1) Fast validation mode (local attribution)
Use when quickly validating logical correctness on the known baseline run.
- rerun `segment6b-s4` and `segment6b-s5` only against an existing run root;
- verify truth/bank/case gate movement before full multi-seed expansion.

### 5.2) Full gate mode (release decision)
Use for wave pass/fail signoff.
- run full upstream chain to produce required 6B inputs for each seed;
- execute `segment6b-s0..s5`;
- compute all Step-3 Wave-0 gates for each seed;
- generate formal gate report.

---

## 6) Command Runbook (PowerShell)
Assumptions:
- repository root is current working directory;
- `make` is available;
- engine runtime uses `Makefile` defaults unless overridden.

### 6.1) Environment bootstrap
```powershell
$env:PYTHONPATH = "packages/engine/src"
$env:ENGINE_RUNS_ROOT = "runs/local_full_run-5"
```

### 6.2) Fast mode (single known run, seed=42)
```powershell
$env:RUN_ID = "c25a2675fbfbacd952b13bb594880e92"
$env:SEED = "42"
make segment6b-s4
make segment6b-s5
```

### 6.3) Full gate mode (all seeds)
```powershell
$seeds = @(42,7,101,202)
foreach ($s in $seeds) {
  $env:SEED = "$s"
  # run full dependency chain needed for 6B correctness
  make segment1a
  make segment1b
  make segment2a
  make segment2b
  make segment3a
  make segment3b
  make segment5a
  make segment5b
  make segment6a
  make segment6b
}
```

Note:
- if runtime/cost is high, execute in two batches (`42,7` then `101,202`) but keep identical configuration and policy versioning.

---

## 7) Wave-0 Gate Metrics (from Step 3)
### 7.1) Gap `1.1` truth-label integrity gates
Pass criteria:
1. `LEGIT share > 0` and policy-consistent.
2. `0.02 <= is_fraud_truth_mean <= 0.30` (unless policy target explicitly differs).
3. Jensen-Shannon distance between observed truth-label mix and policy target `<= 0.05`.

### 7.2) Gap `1.2` bank-view stratification gates
Pass criteria:
1. Cramer’s V(`bank_view_outcome`, `merchant_class`) `>= 0.05`.
2. Cramer’s V(`bank_view_outcome`, `amount_bin`) `>= 0.05`.
3. `max_class_bank_fraud_rate - min_class_bank_fraud_rate >= 0.03`.

### 7.3) Gap `1.3` case-timeline realism gates
Pass criteria:
1. Negative case-gap rate `= 0`.
2. Combined fixed-gap spike share (`3600` and `86400` seconds) `<= 0.50`.
3. Case-duration support has `>= 10` unique minute-level bins.

---

## 8) Evidence Artifacts (Mandatory)
Store in:
- `docs/reports/reports/eda/engine_realism_wave_evidence/wave_0/`

Required files:
1. `wave_0_change_set.md`
2. `wave_0_metrics.csv`
3. `wave_0_gate_report.md`
4. `wave_0_seed_stability.csv`
5. `wave_0_run_index.csv`

`wave_0_metrics.csv` minimum columns:
- `wave`, `seed`, `run_id`, `gap_id`, `metric_name`, `value`, `threshold`, `operator`, `pass_bool`, `notes`

`wave_0_run_index.csv` minimum columns:
- `seed`, `run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`, `git_commit`, `policy_bundle_digest`

---

## 9) Stop/Go Decision Policy
### 9.1) Hard fail conditions
Wave 0 fails immediately if any is true:
1. Any `Critical` gate fails in any seed.
2. Truth collapse persists (`LEGIT share == 0` or `is_fraud_truth_mean == 1.0`) in any seed.
3. Negative case-gap rate remains non-zero.

### 9.2) Conditional hold
Wave 0 enters hold (no Wave 1 start) if:
1. all hard gates pass but cross-seed drift is unstable;
2. gate pass relies on one seed while another is borderline.

### 9.3) Cross-seed stability guard
For each Wave-0 key metric:
- coefficient of variation across seeds should be `<= 0.25`, unless metric is near-zero by design.
- if violated, mark as `PASS_WITH_RISK` and block Wave 1 pending diagnosis.

---

## 10) Attribution and Rollback Discipline
Attribution rules:
1. Keep Wave-0 edits isolated from non-6B code/policy.
2. Tag each run with exact commit and policy bundle digest.
3. If a gate regresses unexpectedly, revert only the most recent WP bundle and rerun the same seed.

Rollback rule:
- no mixed rollback across waves; only revert within Wave-0 scope until Wave-0 gates are clean.

---

## 11) Statistical Test Pack for Wave 0
Minimum tests to attach to gate report:
1. `JS distance` for truth-label mix vs target mix.
2. `Chi-square` + `Cramer's V` for bank-view stratification tables.
3. `KS test` for case-gap distribution versus baseline fixed-spike shape.
4. Bootstrap confidence intervals (95%) for:
- `is_fraud_truth_mean`
- class-level bank-fraud-rate spread
- fixed-gap spike share

All tests must be reported with:
- sample size,
- statistic,
- p-value (where applicable),
- effect-size interpretation.

---

## 12) Deliverables to Close Step 5
Step 5 is complete when all are present:
1. Wave-0 run evidence artifacts generated for seeds `42,7,101,202`.
2. `wave_0_gate_report.md` declares `PASS`, `HOLD`, or `FAIL` with explicit rationale.
3. Any failed gate has direct root-cause notes and rerun plan.
4. Explicit recommendation is made on whether Wave 1 may start.

---

## 13) Next Step
If Step 5 status is `PASS` and no `PASS_WITH_RISK` holds remain:
- proceed to Step 6: Wave-1 execution runbook and coupled-substrate validation plan.

If Step 5 is `HOLD` or `FAIL`:
- remain in Wave 0 and run targeted ablations until all critical gates clear.
