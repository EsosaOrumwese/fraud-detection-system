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
  - [ ] two consecutive P1 runs meet all P1 metrics without counter-tuning oscillation.
  - [ ] same-seed replay preserves metric posture (no drift beyond tolerance).
  - [ ] locked bundle versions are recorded for hurdle + NB dispersion.

### 3.6 P1 explicit non-goals
- No `S8/S9`-level realism patching as a substitute for upstream S1/S2 fixes.
- No deep RNG-forensics work unless integrity rails fail.
- No full-segment (`S0..S9`) run requirement for iterative P1 tuning.

## 4) Workstream B: cross-border candidate realism and realization coupling (Phase P2)

### 4.1 Why second
Current posture is "open world then suppress." Candidate breadth is near-global while realized foreign membership is weakly coupled.

### 4.2 States in scope
- `S3` cross-border candidate assembly,
- `S4` target sizing (`K_target`) behavior,
- `S6` foreign membership realization.

### 4.3 Primary files to touch
- Policies:
  - `config/layer1/1A/policy/s3.rule_ladder.yaml`
  - `config/layer1/1A/policy/s3.thresholds.yaml`
  - `config/layer1/1A/policy/s3.base_weight.yaml`
  - `config/layer1/1A/policy/crossborder_hyperparams.yaml`
  - `config/layer1/1A/policy.s6.selection.yaml`
- Runtime code:
  - `packages/engine/src/engine/layers/l1/seg_1A/s3_crossborder/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1A/s4_ztp/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_set/runner.py`

### 4.4 Implementation intent
- Replace near-global default admission with profile-conditioned candidate breadth.
- Tie realization probability to candidate quality/opportunity instead of weak independent suppression.
- Ensure `K_target` and selected foreign set remain causally consistent with candidate universe.

### 4.5 P2 definition of done
- [ ] median foreign candidate count reaches at least `B` band (`5 to 15`).
- [ ] candidate-to-membership correlation reaches at least `0.30`.
- [ ] realization ratio median reaches at least `0.10`.
- [ ] no state-level cap/retry pathology dominates selection behavior.

## 5) Workstream C: legal-country realism and identity semantics (Phase P3)

### 5.1 Why third
Home/legal mismatch and site identity ambiguity damage interpretability downstream even when count/topology metrics improve.

### 5.2 States in scope
- legal-country assignment surfaces affecting `S8` projection,
- identity semantics enforcement for emitted outlet rows.

### 5.3 Primary files to touch
- Policies:
  - `config/layer1/1A/policy/merchant_allocation.1A.yaml`
  - `config/layer1/1A/policy/legal_tender_2024Q4.yaml`
- Runtime and outputs:
  - `packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/outputs.py`
- Contract docs (if semantic contract update is required):
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml`
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.1A.yaml`

### 5.4 Implementation intent
- Make home vs legal mismatch explicitly size/profile-conditioned.
- Enforce one clear `site_id` contract:
  - either merchant-local index semantics, or
  - globally unique physical-site semantics.
- Add validator checks so ambiguous duplicate interpretation is impossible.

### 5.5 P3 definition of done
- [ ] `home != legal` share reaches at least `B` band (`0.10 to 0.25`).
- [ ] size gradient is positive and material (top decile at least +5pp vs bottom).
- [ ] duplicate behaviors are fully explained by declared identity contract.

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
