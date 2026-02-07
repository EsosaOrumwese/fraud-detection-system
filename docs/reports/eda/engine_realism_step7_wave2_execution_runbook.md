# Engine Realism - Step 7 Wave-2 Upstream Closure Runbook
Date: 2026-02-07  
Baseline reference run: `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`  
Scope: Execute and evaluate `Wave 2` only (`WP-017..WP-026`) after Wave-1 signoff.  
Status: Execution planning + gate protocol. No fixes are implemented in this document.

---

## 0) Objective
Step 7 defines the final upstream-closure execution needed to move engine realism into the B/B+ band without breaking already-recovered downstream truth surfaces:
1. Run Wave-2 work packages in causally coherent bundles.
2. Validate all Wave-2 target gates.
3. Enforce hard regression guards on Wave-0 and Wave-1 gains.
4. Produce deterministic evidence for final Step-8 signoff/regrade.

Wave-2 target gap set:
- `2.1`, `2.2`, `2.3`, `2.4` (1A outlet/candidate/dispersion realism)
- `2.5` (1B geographic concentration realism)
- `2.6`, `2.17` (2A timezone realism and fallback discipline)
- `2.11` (5B DST correctness)
- `2.16` (6B amount/latency realism)
- `2.21` (3B virtual-evidence realism)

---

## 1) Preconditions
Wave 2 is allowed only if all are true:
1. Step-6 status is `PASS` with no unresolved `PASS_WITH_RISK`.
2. Wave-0 and Wave-1 hard gates are green across seeds `{42, 7, 101, 202}`.
3. Wave-0 and Wave-1 evidence artifacts are complete and immutable.
4. No unreviewed edits exist outside Wave-2 scope files.

If any precondition fails, Step 7 is blocked and execution returns to the earlier failing wave.

---

## 2) Inputs and Authorities
Primary planning anchors:
- `docs/reports/eda/engine_realism_step3_hypothesis_acceptance_plan.md`
- `docs/reports/eda/engine_realism_step4_execution_backlog.md`
- `docs/reports/eda/engine_realism_step5_wave0_execution_runbook.md`
- `docs/reports/eda/engine_realism_step6_wave1_execution_runbook.md`

Execution/control anchors:
- `Makefile` segment targets through `segment6b`.
- Wave-2 file targets listed in Step 4 (`WP-017..WP-026`).

---

## 3) Scope Lock
Allowed change set:
- `WP-017..WP-026` only.

Disallowed in Step 7:
1. Any Wave-0 files (`WP-001..WP-003`) except regression investigation branches.
2. Any Wave-1 files (`WP-004..WP-016`) except regression investigation branches.
3. Any unrelated platform/component implementation files.

Purpose:
- preserve attribution for final upstream closure and prevent mixed-wave ambiguity.

---

## 4) Execution Design (Coupled Bundles + Ablations)
Wave 2 is executed as four coupled bundles:
1. `B1_1A`: `WP-017 + WP-018 + WP-019 + WP-020`
2. `B2_1B`: `WP-021`
3. `B3_2A`: `WP-022 + WP-023`
4. `B4_5B_6B_3B`: `WP-024 + WP-025 + WP-026`

Execution sequence:
1. Run bundle `B1` and evaluate bundle gates + Wave-0/1 regression guards.
2. Run bundle `B2` on top of accepted `B1`.
3. Run bundle `B3` on top of accepted `B1+B2`.
4. Run bundle `B4` on top of accepted `B1+B2+B3`.
5. Run a consolidated full Wave-2 pass and compare against baseline + Wave-0 + Wave-1.

Ablation discipline:
1. For each bundle, run one ablation branch removing the highest-touch WP.
2. Use ablation delta to validate causal direction.
3. Do not promote if ablation and full-bundle effects conflict.

---

## 5) Seed Protocol and Run Index
Mandatory seeds:
- `42`, `7`, `101`, `202`

Per-bundle requirement:
1. Execute all seeds for full bundle.
2. Execute at least seeds `42` and `101` for each ablation branch.
3. Record run ids, manifest fingerprints, parameter hashes, and policy digests.

No bundle is accepted on single-seed evidence.

---

## 6) Command Runbook (PowerShell)
Assumptions:
- repository root is current working directory;
- `make` is available;
- run root is `runs/local_full_run-5`.

### 6.1) Environment bootstrap
```powershell
$env:PYTHONPATH = "packages/engine/src"
$env:ENGINE_RUNS_ROOT = "runs/local_full_run-5"
```

### 6.2) Bundle execution skeleton
```powershell
$seeds = @(42,7,101,202)
foreach ($s in $seeds) {
  $env:SEED = "$s"
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

Bundle notes:
1. Reuse the same command chain for each bundle branch.
2. Bundle identity is controlled by policy/code branch content, not command changes.
3. Keep `RUN_ID` unset unless intentionally replaying a fixed-id branch.

---

## 7) Wave-2 Gate Pack (from Step 3)
### 7.1) `B1_1A` gate set (`2.1`, `2.2`, `2.3`, `2.4`)
Required passes:
1. Single-site merchant share in `[0.30, 0.70]`.
2. Home vs legal-country mismatch in policy-consistent band with expected monotone tier behavior.
3. Candidate breadth median in target band and tail not collapsed.
4. Candidate-realization ratio within configured tolerance.
5. Implied `phi` CV `>= 0.20`.
6. Upper-tail / lower-tail `phi` ratio `>= 2.0`.

### 7.2) `B2_1B` gate set (`2.5`)
Required passes:
1. Region-share absolute error <= 5 percentage points for major regions.
2. Country concentration HHI reduced from baseline and within target band.
3. No map-template artifact dominates top-country spread diagnostics.

### 7.3) `B3_2A` gate set (`2.6`, `2.17`)
Required passes:
1. Countries with exactly one tzid <= 60%.
2. Country top-1 tzid share median <= 0.85.
3. Invalid country->tzid fallback rate <= 1%.
4. Out-threshold nearest-fallback usage <= 5%.

### 7.4) `B4_5B_6B_3B` gate set (`2.11`, `2.16`, `2.21`)
Required passes:
1. DST mismatch rate near zero (target <= 0.1%; hard fail > 0.5%).
2. 6B amount profile no longer near-uniform across price points unless explicitly policy-targeted for the scenario.
3. 6B timing/latency distribution has non-degenerate support and preserves timeline monotonicity.
4. 3B virtual evidence shows within-pair variance beyond MCC/channel-only baseline.
5. Virtual classification association lift metrics exceed Step-3 minimum effect-size thresholds.

---

## 8) Regression Guard Pack (Wave-0 and Wave-1)
Wave-2 execution is invalid if either guard pack regresses:
1. Wave-0 guards: truth integrity, bank-view stratification, case timeline validity.
2. Wave-1 guards: edge realism, graph realism, routing/group realism, zone allocation diversity.

Guard evaluation is mandatory for each bundle and consolidated run.

---

## 9) Evidence Artifacts (Mandatory)
Store in:
- `docs/reports/eda/engine_realism_wave_evidence/wave_2/`

Required files:
1. `wave_2_change_set.md`
2. `wave_2_metrics.csv`
3. `wave_2_gate_report.md`
4. `wave_2_seed_stability.csv`
5. `wave_2_regression_guard_report.md`
6. `wave_2_bundle_ablation_report.md`
7. `wave_2_run_index.csv`

Minimum metric row schema:
- `wave`, `bundle`, `seed`, `run_id`, `gap_id`, `metric_name`, `value`, `threshold`, `operator`, `pass_bool`, `regression_guard_bool`, `notes`

---

## 10) Statistical Test Pack
Mandatory tests per bundle:
1. Distribution-shift tests (KS or Wasserstein) for continuous surfaces.
2. Categorical association tests (Chi-square + Cramer’s V) for class/label stratification.
3. Bootstrap confidence intervals (95%) for all headline metrics.
4. Effect-size stability checks across seeds.

Ablation interpretation rule:
1. Full bundle must improve target metrics in expected direction.
2. Ablation branch should weaken at least one primary effect if attribution is valid.
3. If not, mark attribution as ambiguous and hold promotion.

---

## 11) Stop/Go Policy
### 11.1) Bundle-level stop
Stop bundle progression if:
1. any bundle hard gate fails in any seed;
2. any Wave-0/1 regression guard fails.

### 11.2) Wave-level pass
Wave 2 is `PASS` only when:
1. all four bundles pass their gate sets;
2. all Wave-0 and Wave-1 regression guards remain green;
3. cross-seed CV for primary metrics is <= 0.25 unless near-zero by design;
4. ablation checks confirm expected directional attribution.

### 11.3) Hold semantics
Wave 2 is `HOLD` if:
1. hard gates pass but attribution is ambiguous;
2. cross-seed instability exceeds tolerance;
3. upstream improvements trigger downstream guard fragility.

---

## 12) Definition of Done for Step 7
Step 7 is complete when:
1. Wave-2 runbook is finalized and executable.
2. Bundle sequencing, ablation rules, and guard rails are explicit.
3. Evidence artifact contract is fixed.
4. Pass/Hold/Fail policy is fully defined for final Step-8 signoff.

---

## 13) Next Step
If Step-7 execution result is `PASS`:
- proceed to Step 8 for final closure gate, integrated regrade protocol, and remediation completion decision.

If Step-7 execution result is `HOLD` or `FAIL`:
- iterate inside Wave 2 until gates and regression guards are stable.
