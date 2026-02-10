# Engine Realism - Step 6 Wave-1 Coupled Execution Runbook
Date: 2026-02-07  
Baseline reference run: `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`  
Scope: Execute and evaluate `Wave 1` only (`WP-004..WP-016`) after Wave-0 signoff.  
Status: Execution planning + gate protocol. No fixes are implemented in this document.

---

## 0) Objective
Step 6 defines how to execute the high-propagation substrate wave without losing causal attribution:
1. Run `Wave 1` in controlled bundles aligned to coupling in Step 4.
2. Validate Wave-1 target gates and protect Wave-0 critical gains from regression.
3. Produce deterministic evidence required for Step-7/Step-8 statistical signoff and Wave-2 go/no-go.

Wave-1 target gap set:
- `1.4`, `1.5` (3B edge/settlement realism)
- `2.12`, `2.13`, `2.14`, `2.15` (6A graph realism and risk propagation)
- `2.7`, `2.8`, `2.18`, `2.19` (2B routing and temporal realism)
- `2.9`, `2.10`, `2.20` (3A allocation diversity and escalation effectiveness)

---

## 1) Preconditions
Wave 1 is allowed only if all are true:
1. Step-5 status is `PASS` with no unresolved `PASS_WITH_RISK`.
2. Wave-0 critical gates (`1.1`, `1.2`, `1.3`) are green across seeds `{42, 7, 101, 202}`.
3. Wave-0 evidence artifacts are complete and immutable for comparison.
4. No unreviewed policy changes exist outside Wave-1 scope files.

If any precondition fails, Step 6 is blocked and execution returns to Wave-0 stabilization.

---

## 2) Inputs and Authorities
Primary planning anchors:
- `docs/reports/eda/engine_realism_step3_hypothesis_acceptance_plan.md`
- `docs/reports/eda/engine_realism_step4_execution_backlog.md`
- `docs/reports/eda/engine_realism_step5_wave0_execution_runbook.md`

Execution/control anchors:
- `Makefile` segment targets through `segment6b`.
- Wave-1 file targets listed in Step 4 (`WP-004..WP-016`).

---

## 3) Scope Lock
Allowed change set:
- `WP-004..WP-016` only.

Disallowed in Step 6:
1. Any Wave-0 files (`WP-001..WP-003`) except regression investigation branches.
2. Any Wave-2 files (`WP-017..WP-026`).
3. Any unrelated platform/component implementation files.

Purpose:
- keep attribution clean and prevent mixed-wave conclusions.

---

## 4) Execution Design (Coupled Bundles + Ablations)
Wave 1 is executed as four coupled bundles:
1. `B1_3B`: `WP-004 + WP-005`
2. `B2_6A`: `WP-006 + WP-007 + WP-008 + WP-009`
3. `B3_2B`: `WP-010 + WP-011 + WP-012 + WP-013`
4. `B4_3A`: `WP-014 + WP-015 + WP-016`

Execution sequence:
1. Run bundle `B1` and evaluate bundle gates + Wave-0 regression guards.
2. Run bundle `B2` on top of accepted `B1`.
3. Run bundle `B3` on top of accepted `B1+B2`.
4. Run bundle `B4` on top of accepted `B1+B2+B3`.
5. Run a consolidated full Wave-1 pass and compare against baseline + Wave-0.

Ablation discipline:
1. For each bundle, run one ablation branch that removes the largest-policy-touch WP in that bundle.
2. Use ablation delta to confirm effect direction and avoid false attribution.
3. Do not advance if ablation and full-bundle effects contradict expected signs.

---

## 5) Seed Protocol and Run Index
Mandatory seeds:
- `42`, `7`, `101`, `202`

Per-bundle requirement:
1. Execute all seeds for full bundle.
2. Execute at least seed `42` and `101` for each ablation branch.
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
2. Bundle identity is controlled by policy/code branch content, not by command changes.
3. Keep `RUN_ID` unset unless intentionally rerunning a fixed id path.

---

## 7) Wave-1 Gate Pack (from Step 3)
### 7.1) `B1_3B` gate set (`1.4`, `1.5`)
Required passes:
1. Merchant edge-count CV `>= 0.25`.
2. Median edge-weight Gini `>= 0.20`.
3. At least `30%` merchants with top-edge share `>= 0.10`.
4. Median settlement-country edge-share uplift `>= +0.05`.
5. Median settlement anchor-distance reduction `>= 30%` from baseline.
6. Merchants with zero settlement overlap `<= 0.30`.

### 7.2) `B2_6A` gate set (`2.12`..`2.15`)
Required passes:
1. Regional IP-type share error `<= 5 pp`.
2. Devices with `>=1` IP `>= 0.50`.
3. Mean IPs per linked device `>= 1.2`.
4. `K_max` breach rate `<= 0.1%`.
5. Conditional risk uplifts (`party -> device/account`) each `>= 0.15`.
6. Mutual information between linked risk roles `>= 0.02`.

### 7.3) `B3_2B` gate set (`2.7`, `2.8`, `2.18`, `2.19`)
Required passes:
1. Top-1 site-share median `>= 0.20`.
2. Top-1 minus top-2 share median `>= 0.05`.
3. Unique sigma bins `>= 5`.
4. Sigma CV `>= 0.20`.
5. Merchant-days with `max p_group >= 0.9` `<= 25%`.
6. Merchant-days with `max p_group <= 0.7` `>= 30%`.
7. Roster missingness in `5%` to `25%` band.
8. Variance-to-mean ratio > 1 for at least `40%` merchants.

### 7.4) `B4_3A` gate set (`2.9`, `2.10`, `2.20`)
Required passes:
1. Country top-1 share median `<= 0.80`.
2. Merchant-country entropy median `>= 0.25`.
3. Pairs with top-1 `>= 0.95` `<= 0.40`.
4. Escalated pairs multi-zone support `>= 0.30`.
5. Escalation uplift on effective zones `>= +0.5`.
6. S4 variance retention from S3 `>= 60%`.

---

## 8) Wave-0 Regression Guard Pack
Wave-1 run is invalid if any Wave-0 critical metric regresses below pass criteria:
1. `LEGIT share > 0` and fraud-truth mean in target band.
2. Bank-view stratification retains minimum effect-size thresholds.
3. Case negative-gap rate remains zero and fixed-gap spikes remain bounded.

Guard evaluation is mandatory for each bundle and consolidated run.

---

## 9) Evidence Artifacts (Mandatory)
Store in:
- `docs/reports/eda/engine_realism_wave_evidence/wave_1/`

Required files:
1. `wave_1_change_set.md`
2. `wave_1_metrics.csv`
3. `wave_1_gate_report.md`
4. `wave_1_seed_stability.csv`
5. `wave_1_regression_guard_report.md`
6. `wave_1_bundle_ablation_report.md`
7. `wave_1_run_index.csv`

Minimum metric row schema:
- `wave`, `bundle`, `seed`, `run_id`, `gap_id`, `metric_name`, `value`, `threshold`, `operator`, `pass_bool`, `regression_guard_bool`, `notes`

---

## 10) Statistical Test Pack
Mandatory tests per bundle:
1. Distribution shift tests (KS or Wasserstein) for key continuous surfaces.
2. Categorical association tests (Chi-square + Cramer’s V) for stratification targets.
3. Bootstrap confidence intervals (95%) for all bundle headline metrics.
4. Effect-size stability across seeds.

Ablation interpretation rule:
1. Full bundle must improve target metrics in expected direction.
2. Ablation branch should weaken at least one primary effect if attribution is valid.
3. If not, mark attribution as ambiguous and hold promotion.

---

## 11) Stop/Go Policy
### 11.1) Bundle-level stop
Stop bundle progression if:
1. any bundle hard gate fails in any seed;
2. any Wave-0 regression guard fails.

### 11.2) Wave-level pass
Wave 1 is `PASS` only when:
1. all four bundles pass their gate sets;
2. all Wave-0 regression guards remain green;
3. cross-seed CV for primary metrics is `<= 0.25` unless near-zero by design;
4. ablation checks confirm expected directional attribution.

### 11.3) Hold semantics
Wave 1 is `HOLD` if:
1. hard gates pass but attribution is ambiguous;
2. cross-seed instability exceeds tolerance;
3. bundle effects conflict with Step-3 hypothesis direction.

---

## 12) Definition of Done for Step 6
Step 6 is complete when:
1. Wave-1 runbook is finalized and executable.
2. Bundle sequencing, ablation rules, and guard rails are explicit.
3. Evidence artifact contract is fixed.
4. Pass/Hold/Fail policy is fully defined for promotion to Wave 2.

---

## 13) Next Step
If Step-6 execution result is `PASS`:
- proceed to Step 7 for Wave-2 execution runbook and final upstream realism closure.

If Step-6 execution result is `HOLD` or `FAIL`:
- iterate inside Wave 1 until bundle and regression gates are stable.
