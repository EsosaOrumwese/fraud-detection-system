# Segment 1A Remediation Build Plan (B/B+ Execution Plan)
_As of 2026-02-12_

## 0) Objective and closure rule
- Objective: remediate Segment `1A` so its certified realism posture is at least `B`, with `B+` as the execution target.
- Closure rule:
  - all hard gates pass, and
  - at least 70% of `B` target-band checks pass for `B`, or
  - at least 80% of `B+` target-band checks pass for `B+`.
- Scope: this plan is for implementation and verification of Segment `1A` only. It may include upstream policy/coeff updates if they are direct causes of `1A` statistical failures.

## 1) Source-of-truth stack

### 1.1 Statistical authority
- `docs/reports/eda/segment_1A/segment_1A_published_report.md`
- `docs/reports/eda/segment_1A/segment_1A_remediation_report.md`

### 1.2 State and contract authority
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s0.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s1.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s2.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s3.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s4.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s5.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s6.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s7.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s8.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s9.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/artefact_registry_1A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.1A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.ingress.layer1.yaml`

### 1.3 Non-negotiables
- Execute causally in state order: `S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S9`.
- Do not use `S8`/`S9` as realism rescue layers for upstream defects.
- Keep deterministic replay intact for fixed seed and policy/coefficient hash.
- Treat missing required outputs as certification failure, not documentation debt.

## 2) Baseline freeze and pass criteria (Phase P0)

### 2.1 Purpose
Freeze the current baseline so post-fix movement is causal and auditable.

### 2.2 Baseline capture bundle
- Pin baseline run and hashes.
- Export baseline metrics for:
  - single-site share and outlet-count pyramid,
  - concentration (`top10%` share, Gini),
  - candidate breadth and realization coupling,
  - home vs legal mismatch + size gradient,
  - implied dispersion (`phi` CV, quantile ratio),
  - required artifact presence.
- Store baseline summary under:
  - `docs/reports/eda/segment_1A/` (report tables),
  - run-scoped validation outputs in `runs/fix-data-engine/segment_1A/`.

### 2.3 P0 definition of done
- [x] baseline run is pinned (run id, manifest fingerprint, parameter hash).
- [x] all Section 2 metrics from remediation report are materialized as baseline table.
- [x] hard-gate status is explicitly marked pass/fail before any code or policy change.

## 3) Workstream A: coefficient-first population/count realism (Phase P1)

### 3.1 Why first
`1A` realism drift begins at the count-generating roots (`S1` hurdle + `S2` NB). If these are not corrected first, later states only mask upstream shape errors.

### 3.2 P1 execution mode (strict)
- Run only required upstream chain for P1: `S0 -> S1 -> S2`.
- Do not execute `S3+` while calibrating P1 unless explicitly needed for a targeted diagnostic.
- P1 scoring is data-shape first; RNG analysis is limited to integrity rails (cardinality/branch purity/counter sanity).

### 3.3 P1 target datasets (authoritative scoring surfaces)
- `S1` branch gate:
  - `logs/layer1/1A/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
- `S2` accepted outlet count:
  - `logs/layer1/1A/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
- `S2` mixture diagnostics (for rejection/dispersion behavior sanity):
  - `logs/layer1/1A/rng/events/gamma_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
  - `logs/layer1/1A/rng/events/poisson_component/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
- Coefficient/input context for calibration:
  - `data/layer1/1A/hurdle_design_matrix/parameter_hash={parameter_hash}/`
  - `data/layer1/1A/hurdle_pi_probs/parameter_hash={parameter_hash}/`

### 3.4 Primary files to touch
- Policies and coeff bundles:
  - `config/layer1/1A/models/hurdle/hurdle_simulation.priors.yaml`
  - `config/layer1/1A/models/hurdle/exports/version=*/**/hurdle_coefficients.yaml`
  - `config/layer1/1A/models/hurdle/exports/version=*/**/nb_dispersion_coefficients.yaml`
  - `config/layer1/1A/policy/channel_policy.1A.yaml`
- Runtime (only if policy/coeff updates are insufficient):
  - `packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1A/s2_nb_outlets/runner.py`

### 3.5 P1 phased approach and DoD

#### P1.1 Run-loop hardening (`S0->S2` only)
- Intent:
  - enforce state-scoped run profile that stops after `S2`;
  - keep failed-run pruning active before each new run id in `runs/fix-data-engine/...`.
- DoD:
  - [x] one repeatable command/profile executes `S0,S1,S2` only.
  - [x] each run emits all four scoring surfaces listed in 3.3.

#### P1.2 Hurdle calibration (`S1`)
- Intent:
  - calibrate `hurdle_coefficients` to restore realistic single-site vs multi-site split by merchant strata;
  - avoid degenerate saturation where most merchants collapse near `pi ~ 0` or `pi ~ 1`.
- Data checks:
  - derive merchant outlet regime from `hurdle_bernoulli` gate + `nb_final`.
- DoD:
  - [x] single-site share reaches at least `B` band (`0.25 to 0.45`), target `B+` (`0.35 to 0.55`).
  - [x] branch purity holds: no `S2` outputs for merchants gated `is_multi=false`.

#### P1.3 NB mean/dispersion calibration (`S2`)
- Intent:
  - calibrate count level via NB mean path and restore dispersion heterogeneity via `beta_phi`;
  - preserve stable tails while removing near-constant `phi`.
- Data checks:
  - outlet-count shape from `nb_final`;
  - dispersion realism from implied `phi` profile by merchant strata.
- DoD:
  - [x] `outlets_per_merchant` median reaches `B` band (`6 to 20`), target `B+` (`8 to 18`).
  - [x] concentration metrics reach `B` bands:
    - top-10% outlet share (`0.35 to 0.55`),
    - Gini (`0.45 to 0.62`).
  - [x] dispersion heterogeneity reaches `B` bands:
    - `CV(phi)` (`0.05 to 0.20`),
    - `P95/P05(phi)` (`1.25 to 2.0`).

#### P1.4 Joint reconciliation + lock
- Intent:
  - reconcile cross-effects between S1 and S2 so gains are not metric-forging artifacts;
  - lock coefficient bundles once realism is stable.
- DoD:
  - [x] two consecutive P1 runs meet all P1 metrics without counter-tuning oscillation.
  - [x] same-seed replay preserves metric posture (no drift beyond tolerance).
  - [x] locked bundle versions are recorded for hurdle + NB dispersion.

### 3.6 P1 explicit non-goals
- No `S8/S9`-level realism patching as a substitute for upstream S1/S2 fixes.
- No deep RNG-forensics work unless integrity rails fail.
- No full-segment (`S0..S9`) run requirement for iterative P1 tuning.

### 3.7 P1 freeze contract (binding for P2+)
- `P1` is accepted as statistically realistic at `B` and is treated as frozen baseline for downstream phases.
- Frozen `1A` surfaces:
  - `S1/S2` behavioral posture from accepted P1 scorecards,
  - locked coefficient bundle:
    - `config/layer1/1A/models/hurdle/exports/version=2026-02-12/20260212T200823Z/hurdle_coefficients.yaml`
    - `config/layer1/1A/models/hurdle/exports/version=2026-02-12/20260212T200823Z/nb_dispersion_coefficients.yaml`
  - accepted S2 sampler remediation in `packages/engine/src/engine/layers/l1/seg_1A/s2_nb_outlets/runner.py`.
- Rule for `P2+` execution:
  - treat `S1/S2` as immutable and remediate downstream states only unless explicitly reopened.
  - reopen of `P1` requires:
    - demonstrated hard contract/causal contradiction, and
    - explicit user approval before any `S1/S2` change.

## 4) Workstream B: cross-border candidate realism and realization coupling (Phase P2)

### 4.1 Why second
Current posture is "open world then suppress." Candidate breadth is near-global while realized foreign membership is weakly coupled.

### 4.1.a P2 precondition
- P1 freeze contract in Section 3.7 is active; `P2` work must not mutate frozen `S1/S2` surfaces.

### 4.1.b P2 execution mode (strict)
- Iterative tuning scope: `S0 -> S6` only.
- Do not execute `S7+` during P2 calibration loops unless a specific diagnostic requires it.
- Use deterministic seeds for scoring and replay (`42`, `43`, `44`).
- Evaluate both global and stratified posture:
  - `channel`,
  - broad MCC groups,
  - GDP bucket tiers.

### 4.2 States in scope
- `S3` cross-border candidate assembly,
- `S4` target sizing (`K_target`) behavior,
- `S6` foreign membership realization.

### 4.3 P2 target datasets (authoritative scoring surfaces)
- `s3_candidate_set`
- `s3_integerised_counts` (required when `policy.s3.integerisation.yaml` has `emit_integerised_counts=true`; otherwise record intentional absence)
- `rng_event_ztp_final`
- `rng_event_ztp_rejection`
- `rng_event_ztp_retry_exhausted` (optional-presence diagnostic; zero-row posture is valid)
- `rng_event_gumbel_key`
- `s6_membership`
- `s4_metrics_log`

### 4.4 Statistical realism definition and formulas
- Merchant-level variables:
  - `C_m` = candidate breadth for merchant `m` (count from `s3_candidate_set`).
  - `R_m` = realized foreign membership for merchant `m` (count from `s6_membership` or equivalent S6 authority).
  - `rho_m` = realization ratio = `R_m / max(C_m, 1)`.
- Core realism checks:
  - candidate breadth level: `median(C_m)` in `B` band (`5 to 15`).
  - coupling realism: `SpearmanCorr(C_m, R_m) >= 0.30`.
  - realization intensity: `median(rho_m) >= 0.10`.
- Pathology hard checks (fail-fast):
  - retry exhaustion share:
    - `share_exhausted = merchants_with_ztp_retry_exhausted / merchants_with_C_m>0`
    - must remain low (`<= 0.02`).
  - high-rejection concentration:
    - `share_high_reject = merchants_with_ztp_rejections_gt16 / merchants_with_C_m>0`
    - must remain low (`<= 0.10`).
- Stratified realism rule:
  - the three core checks above must not pass only in aggregate while materially failing across most strata.

### 4.5 Tunable surfaces and ownership map
- Allowed to tune in P2:
  - `config/layer1/1A/policy/s3.rule_ladder.yaml`
  - `config/layer1/1A/policy/s3.thresholds.yaml`
  - `config/layer1/1A/policy/s3.base_weight.yaml`
  - `config/layer1/1A/policy/s3.integerisation.yaml`
  - `config/layer1/1A/allocation/ccy_smoothing_params.yaml` (only when P2 diagnostics prove S5 support sparsity is the blocking cause for S6 realization)
  - `config/layer1/1A/policy/crossborder_hyperparams.yaml` (including `ztp` block)
  - `config/layer1/1A/policy.s6.selection.yaml`
  - `config/layer1/1A/models/allocation/dirichlet_alpha_policy.yaml` (only if needed after core tuning)
- Prohibited in P2:
  - any `S1/S2` coefficient or sampler logic change unless P1 reopen is explicitly approved.

### 4.6 Primary files to touch
- Policies:
  - `config/layer1/1A/policy/s3.rule_ladder.yaml`
  - `config/layer1/1A/policy/s3.thresholds.yaml`
  - `config/layer1/1A/policy/s3.base_weight.yaml`
  - `config/layer1/1A/policy/s3.integerisation.yaml`
  - `config/layer1/1A/allocation/ccy_smoothing_params.yaml` (conditional: only after explicit blocker confirmation)
  - `config/layer1/1A/policy/crossborder_hyperparams.yaml`
  - `config/layer1/1A/policy.s6.selection.yaml`
  - `config/layer1/1A/models/allocation/dirichlet_alpha_policy.yaml`
- Runtime code:
  - `packages/engine/src/engine/layers/l1/seg_1A/s3_crossborder/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1A/s4_ztp/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_set/runner.py`

### 4.7 Implementation intent
- Replace near-global default admission with profile-conditioned candidate breadth.
- Tie realization probability to candidate quality/opportunity instead of weak independent suppression.
- Ensure `K_target` and selected foreign set remain causally consistent with candidate universe.

### 4.8 P2 phased approach and DoD

#### P2.1 Baseline and scoring harness
- Intent:
  - materialize deterministic P2 scorecard from P2 surfaces before policy edits.
- DoD:
  - [x] one repeatable command/profile runs `S0..S6` and emits all P2 scoring surfaces.
  - [x] baseline P2 scorecard is written with global + stratified metrics.
  - [x] pathology hard checks are computed and visible in scorecard.

#### P2.2 Candidate breadth shaping (`S3` first)
- Intent:
  - move `C_m` from near-global saturation to profile-conditioned realistic breadth.
- DoD:
  - [x] `median(C_m)` reaches `B` band (`5 to 15`) in aggregate.
  - [x] candidate-shape movement is broad (not a single-stratum artifact).
  - [x] pathology checks remain below hard caps while tuning `S3`.

#### P2.3 Realization coupling (`S4/S6`)
- Intent:
  - align `R_m` with candidate opportunity and remove weak independent suppression.
- DoD:
  - [x] `SpearmanCorr(C_m, R_m) >= 0.30`.
  - [x] `median(rho_m) >= 0.10`.
  - [x] retry/rejection pathology remains below hard caps.
- Current blocker note:
  - resolved via targeted S5 support-density remediation plus S3 breadth compression; reference stable runs:
    - `9901b537de3a5a146f79365931bd514c`
    - `d6e04d5dc57b9dc3f41ac59508cafd3f`

#### P2.4 Joint reconciliation and lock
- Intent:
  - confirm the final P2 tuning is stable and replay-consistent before lock.
- DoD:
  - [x] two consecutive P2 runs meet all P2 B checks without counter-tuning oscillation.
  - [x] same-seed replay preserves P2 metric posture (drift within tolerance).
  - [x] locked policy versions and hashes are recorded for S3/S4/S6 knobs.
- Lock record:
  - accepted parameter hash: `6b93f7a971bdaed50765b5964368305467d31ba2b16ca60b83c20dca111591aa`
  - stable run pair:
    - `9901b537de3a5a146f79365931bd514c`
    - `d6e04d5dc57b9dc3f41ac59508cafd3f`
  - locked knobs:
    - `config/layer1/1A/policy/s3.rule_ladder.yaml`
    - `config/layer1/1A/allocation/ccy_smoothing_params.yaml`
    - `config/layer1/1A/policy/crossborder_hyperparams.yaml`
    - `config/layer1/1A/policy.s6.selection.yaml`

### 4.9 Calibration method (mathematical, non-forging)
- Use staged constrained calibration with frozen `P1` baseline:
  - Stage A: tune `S3` knobs to shape `C_m`.
  - Stage B: tune `S4/S6` knobs to shape `Corr(C_m,R_m)` and `rho_m`.
- Optimization form (for ranking candidate configs):
  - `L(theta) = sum_i w_i * d_i(theta) + lambda * pathology_penalty(theta)`.
  - `d_i(theta)` is band-distance:
    - `0` when metric is inside target interval,
    - quadratic penalty outside interval.
- Selection rule:
  - reject any candidate violating pathology hard caps,
  - among valid candidates, pick smallest `L(theta)` with stable replay behavior.

### 4.10 Storage retention during P2
- To prevent run-root growth during iterative tuning:
  - retain only latest successful baseline run-id set,
  - retain only latest successful candidate run-id set,
  - retain scorecards and lock artifacts,
  - prune other run-id folders after each accepted iteration.

## 5) Workstream C: legal-country realism and identity semantics (Phase P3)

### 5.1 Why third
Home/legal mismatch and site identity ambiguity damage interpretability downstream even when count/topology metrics improve.

### 5.2 P3 freeze guardrails (binding)
- `P1/P2` locked surfaces remain immutable by default during `P3`:
  - `S1/S2` posture and coefficient bundles from Section `3.7`,
  - `S3/S4/S6` locked knobs from Section `4.8` lock record,
  - `S5` support-density posture as accepted in `P2` lock runs.
- P3 scoring authority for size gradient:
  - merchant size is `n_outlets` deciles from `rng_event_nb_final` / `raw_nb_outlet_draw`.
- P3 identity contract (fixed choice):
  - `site_id` is merchant-local sequence semantics scoped to `(merchant_id, legal_country_iso)`,
  - `site_id` is **not** a globally unique physical-site identifier.
- Hard veto during `P3`:
  - reject any candidate change that regresses locked P2 global gates below B thresholds.

### 5.3 States and datasets in scope
- Primary state focus:
  - `S8` outlet materialisation semantics and validation handoff.
- Upstream read-only dependency surfaces for P3 scoring:
  - `s3_candidate_set`,
  - `s6_membership`,
  - `rng_event_nb_final`,
  - `s7` integer count handoff / `s3_integerised_counts` (owner-dependent),
  - `outlet_catalogue` (primary P3 scoring surface).

### 5.4 Primary files to touch
- Runtime and validation:
  - `packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1A/s9_validation/runner.py`
- Contract docs:
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml`
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.1A.yaml`
- Conditional reopen surfaces (only if Section 5.8 trigger is met and approval is granted):
  - `config/layer1/1A/policy/merchant_allocation.1A.yaml`
  - `config/layer1/1A/policy/legal_tender_2024Q4.yaml`
  - additional minimal upstream knobs in `S3/S6/S7` as explicitly approved.

### 5.5 P3 statistical targets and definitions
- `home_legal_mismatch_rate`:
  - `mean(home_country_iso != legal_country_iso)` on `outlet_catalogue`,
  - target bands:
    - `B`: `0.10 to 0.25`,
    - `B+`: `0.12 to 0.20`.
- `size_gradient_pp`:
  - mismatch rate in top merchant size decile minus bottom deciles,
  - target bands:
    - `B`: at least `+5pp`,
    - `B+`: at least `+8pp`.
- `identity_semantics_quality`:
  - unexplained duplicate exposure under declared `site_id` contract,
  - target:
    - no unexplained duplicate anomalies.
- uncertainty requirement:
  - compute Wilson/Bootstrap CIs for key rates and gradient before acceptance.

### 5.6 P3 phased approach and DoD

#### P3.1 Baseline and scoring harness
- Intent:
  - materialize deterministic P3 baseline from locked P2 posture before edits.
- DoD:
  - [x] one repeatable command/profile computes P3 scorecard metrics + CIs.
  - [x] scorecard reports global + stratified posture (`channel`, broad `MCC`, GDP bucket).
  - [x] baseline includes duplicate-semantics diagnostics under current `site_id` contract.
- Baseline evidence (2026-02-13):
  - command: `make segment1a-p3 RUNS_ROOT=runs/fix-data-engine/segment_1A`
  - run id: `d94f908cd5715404af1bfb9792735147`
  - scorecard: `runs/fix-data-engine/segment_1A/reports/segment1a_p3_1_baseline_d94f908cd5715404af1bfb9792735147.json`

#### P3.2 Identity semantics hardening
- Intent:
  - remove site-identity ambiguity while preserving declared S8 contract semantics.
- DoD:
  - [x] schema/dictionary language explicitly binds `site_id` to local `(merchant_id, legal_country_iso)` scope.
  - [x] S9 validators fail closed for any duplicate behavior outside declared contract.
  - [x] unexplained duplicate anomalies are zero in baseline + post-change checks.
- Closure evidence (2026-02-13):
  - contract wording tightened in:
    - `schemas.1A.yaml#/egress/outlet_catalogue` (`site_id` scope explicit),
    - `dataset_dictionary.layer1.1A.yaml` (`outlet_catalogue` description scope explicit).
  - S9 fail-closed enforcement hardened in:
    - `packages/engine/src/engine/layers/l1/seg_1A/s9_validation/runner.py` (`duplicate_local_site_id` rejection in local scope).
  - S9 pass on updated contract authority:
    - `make segment1a-s9 ... SEG1A_S9_RUN_ID=59cc9b7ed3a1ef84f3ce69a3511389ee` -> decision `PASS`.

#### P3.3 Legal mismatch realism closure under frozen upstream
- Intent:
  - achieve mismatch level and size-gradient realism without reopening locked upstream surfaces.
- DoD:
  - [x] `home_legal_mismatch_rate` reaches at least `B` band.
  - [x] `size_gradient_pp` reaches at least `B` threshold.
  - [x] no regression of locked P2 global gates.
- Closure evidence (2026-02-13):
  - command: `make segment1a-p3 RUNS_ROOT=runs/fix-data-engine/segment_1A`
  - accepted run id (B+ mismatch retune): `da3e57e73e733b990a5aa3a46705f987`
  - scorecard:
    - `runs/fix-data-engine/segment_1A/reports/segment1a_p3_1_baseline_da3e57e73e733b990a5aa3a46705f987.json`
  - global P3 metrics:
    - `home_legal_mismatch_rate = 0.122534` (B+ pass),
    - `size_gradient_pp = +13.076` (B/B+ pass),
    - `no_unexplained_duplicate_anomalies = true`.
  - P2 regression guard:
    - `runs/fix-data-engine/segment_1A/reports/segment1a_p2_regression_da3e57e73e733b990a5aa3a46705f987.json`
    - global checks remain pass (`median_C`, `Spearman(C,R)`, `median_rho`, pathology caps).

#### P3.4 Joint reconciliation and lock
- Intent:
  - verify P3 posture is stable and not seed-luck or scorer artifact.
- DoD:
  - [x] two consecutive same-seed P3 runs meet all P3 B checks.
  - [x] replay preserves P3 metric posture within tolerance.
  - [x] lock record captures accepted run ids, parameter hash, and touched knobs/files.
- Closure evidence (2026-02-13):
  - same-seed consecutive runs:
    - `da3e57e73e733b990a5aa3a46705f987`,
    - `a212735023c748a710e4b851046849f8`.
  - both runs show:
    - `seed=42`,
    - `parameter_hash=79d755e7132bdcc9915b5db695a42a0ab5261b14b3d72e84c38ed4c725d874dd`,
    - P3 checks all true (including B+ mismatch and B+ gradient).
  - replay metric drift (`a212... - da3...`):
    - `home_legal_mismatch_rate delta = 0.0`,
    - `size_gradient_pp delta = 0.0`,
    - `top_decile_mismatch_rate delta = 0.0`,
    - `bottom_deciles_mismatch_rate delta = 0.0`.
  - scorecards:
    - `runs/fix-data-engine/segment_1A/reports/segment1a_p3_1_baseline_da3e57e73e733b990a5aa3a46705f987.json`,
    - `runs/fix-data-engine/segment_1A/reports/segment1a_p3_1_baseline_a212735023c748a710e4b851046849f8.json`.
  - P2 non-regression confirmations:
    - `runs/fix-data-engine/segment_1A/reports/segment1a_p2_regression_da3e57e73e733b990a5aa3a46705f987.json`,
    - `runs/fix-data-engine/segment_1A/reports/segment1a_p2_regression_a212735023c748a710e4b851046849f8.json`.
  - lock record:
    - final tuned knob: `config/layer1/1A/allocation/s7_integerisation_policy.yaml` (`home_bias_lane` final tier `max_n_outlets=1000000`, `home_share_min=0.61`),
    - touched runtime from P3 closure track remains:
      - `packages/engine/src/engine/layers/l1/seg_1A/s7_integerisation/runner.py`,
      - `packages/engine/src/engine/layers/l1/seg_1A/s9_validation/runner.py`.

### 5.7 Calibration and anti-forging method
- Candidate ranking objective:
  - `L(theta) = sum_i w_i * d_i(theta) + lambda * veto_penalty(theta)`.
- `d_i(theta)`:
  - `0` inside target bands; quadratic penalty outside.
- `veto_penalty(theta)`:
  - hard reject any candidate violating P2 locked gates or contract integrity checks.
- Execution posture:
  - tune one knob family at a time, reconcile jointly only after single-family movement is causal.

### 5.8 Conditional reopen protocol (fail-closed)
- Trigger:
  - if P3.3 cannot meet mismatch-level/gradient targets under frozen upstream.
- Required before reopen:
  - explicit causal evidence that P3-local levers are insufficient, and
  - explicit user approval naming allowed reopen surfaces.
- Minimal reopen order:
  - `S7` count-allocation posture,
  - `S6` legal-membership gating posture,
  - `S3` candidate/legal breadth posture,
  - broader policy/config surfaces only if prior steps fail.
- Reopen DoD:
  - [ ] target movement achieved with smallest approved blast radius.
  - [ ] P1/P2 realism posture remains non-regressed.

## 6) Workstream D: artifact completeness and state auditability (Phase P4)

### 6.1 Why fourth
Certification is impossible while required outputs are absent.

### 6.2 States in scope
- `S3`, `S5`, `S8`, `S9` output surfaces and receipt checks.

### 6.3 Required outputs to enforce
- `s3_integerised_counts`
- `s3_site_sequence`
- `sparse_flag`
- `merchant_abort_log`
- `hurdle_stationarity_tests`

### 6.4 Primary files to touch
- Runtime:
  - `packages/engine/src/engine/layers/l1/seg_1A/s3_crossborder/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1A/s5_currency_weights/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1A/s9_validation/runner.py`
- Contracts:
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1A/artefact_registry_1A.yaml`
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml`

### 6.5 P4 definition of done
- [ ] all required outputs are emitted in sealed run paths.
- [ ] schema and registry references resolve without manual patching.
- [ ] S9 can certify gates directly from emitted artifacts.

## 7) Certification and grade decision (Phase P5)

### 7.1 Validation matrix
- Hard gates:
  - single-site tier exists materially,
  - candidate breadth not near-global by default,
  - dispersion heterogeneity restored,
  - required outputs present.
- Target bands:
  - use the `B` and `B+` intervals defined in `segment_1A_remediation_report.md`.

### 7.2 Run strategy
1. full certification run (`P0..P4` merged),
2. same-seed replay (determinism),
3. ablation runs by workstream (`P1`, `P2`, `P3`, `P4`) to confirm causal movement,
4. alternate-seed sensitivity run to reject seed-luck wins.

### 7.3 Certification outputs
- metric table (baseline vs post-fix),
- hard-gate pass/fail table,
- band-coverage score (`B` and `B+`),
- grade decision with veto notes for any hard-gate failure.

### 7.4 P5 definition of done
- [ ] all hard gates pass.
- [ ] `B` or `B+` band-coverage threshold is met.
- [ ] determinism and ablation evidence are attached.
- [ ] final Segment `1A` grade is recorded with reproducible evidence links.

## 8) Sequencing and stop rules

### 8.1 Phase order
- Execute strictly: `P0 -> P1 -> P2 -> P3 -> P4 -> P5`.
- Do not overlap phases if prior phase DoD is open.
- Within `P1`, execute state progression strictly as `S0 -> S1 -> S2` for each iteration.

### 8.2 Stop rules
- Stop immediately if:
  - determinism breaks,
  - hard-gate metric regresses by more than 10% relative to baseline in the wrong direction,
  - schema/registry drift appears without explicit contract update.
  - P1 run profile unexpectedly emits `S3+` outputs (scope breach).

### 8.3 Rollback rule
- Any failed phase reverts to last sealed passing manifest and re-runs from that boundary.

## 9) Expected downstream effect (for planning, not certification)
- `2A` and `2B`: improved topology realism and lower degenerate weighting pressure.
- `3A` and `3B`: cleaner country/tz behavior because upstream merchant and foreign-set structure is no longer contradictory.
- `5A` to `6B`: better heterogeneity feed into arrivals, flows, and fraud overlays.
- Note: downstream grade lift is not assumed; each segment still requires its own remediation certification.
