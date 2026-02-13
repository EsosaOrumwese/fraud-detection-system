# Segment 1B Remediation Build Plan (B/B+ Execution Plan)
_As of 2026-02-13_

## 0) Objective and closure rule
- Objective: remediate Segment `1B` to certified realism `B` minimum, with `B+` as the active target.
- Realism surface of record: `site_locations`.
- Closure rule:
  - all hard `B` gates pass on all required seeds, and
  - `B+` is claimed only if all `B+` gates pass on all required seeds with stability limits met.
- Execution posture: data-shape first. Structural pass flags remain safety rails, not the tuning target.

## 1) Source-of-truth stack

### 1.1 Statistical authority
- `docs/reports/eda/segment_1B/segment_1B_published_report.md`
- `docs/reports/eda/segment_1B/segment_1B_remediation_report.md`

### 1.2 State/contract authority
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s0.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s1.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s2.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s3.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s4.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s5.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s6.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s7.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s8.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s9.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1B/artefact_registry_1B.yaml`

## 2) Upstream lock and remediation scope
- Upstream lock: Segment `1A` is frozen and treated as immutable input during 1B remediation.
- Active remediation states: `S2`, `S4`, `S6`, `S9`.
- Support states (rerun-only unless breakage): `S0`, `S1`, `S3`, `S5`, `S7`, `S8`.
- This follows the remediation report chosen fix bundle (`S2 + S4 + S6 + S9`) and keeps state-order causality intact.

### 2.1 Progressive rerun matrix (mandatory)
- If `S2` changes: rerun `S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S9`.
- If `S4` changes: rerun `S4 -> S5 -> S6 -> S7 -> S8 -> S9`.
- If `S6` changes: rerun `S6 -> S7 -> S8 -> S9`.
- If `S9` gates only change: rerun `S9`.
- No phase closes on partial state chains that violate upstream/downstream dependencies.

## 3) Realism targets (baseline to B/B+)
- Baseline (published report): `country_gini=0.753`, `top10=59.74%`, `top5=39.33%`, `top1=13.66%`.
- `B` targets:
  - `country_gini <= 0.68`
  - `top10 <= 50%`
  - `top5 <= 33%`
  - `top1 <= 10%`
  - eligible countries with nonzero sites `>= 85%`
  - southern hemisphere share `>= 12%`
  - nearest-neighbor tail ratio (`p99/p50`) improves by `>= 20%` vs baseline
- `B+` targets:
  - `country_gini <= 0.60`
  - `top10 <= 42%`
  - `top5 <= 27%`
  - `top1 <= 8%`
  - eligible countries with nonzero sites `>= 92%`
  - southern hemisphere share `>= 18%`
  - nearest-neighbor tail ratio (`p99/p50`) improves by `>= 35%` vs baseline
- Stability targets across seeds:
  - core-metric CV `<= 0.30` for `B`
  - core-metric CV `<= 0.20` for `B+`

## 4) Heavy-compute iteration protocol
- Run root for remediation: `runs/fix-data-engine/segment_1B/`.
- Baseline authority run stays pinned and read-only.
- Keep only required run-id folders:
  - `baseline_authority`
  - `current_candidate`
  - `last_good`
  - certification pack (only during final promotion wave)
- Before starting a new candidate run, prune superseded failed candidate folders.

### 4.1 Two-lane loop
- Fast lane (tuning):
  - single-seed iterations from the changed state onward using the rerun matrix.
  - evaluate only data realism movement and regression vetoes.
- Certification lane (promotion):
  - full-seed set `{42, 7, 101, 202}` with full required state chain for the promoted candidate.
  - promotion blocked if any seed fails a hard gate.

## 5) Phase plan (data-first with DoDs)

### P0 - Baseline authority and harness lock
Goal:
- create a hard baseline and scoring harness so every later metric movement is attributable and reproducible.

P0.1 Baseline authority pin:
- Baseline run authority: `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`.
- Pin immutable lineage tokens for baseline comparison:
  - `run_id`,
  - `manifest_fingerprint`,
  - `parameter_hash`,
  - `seed`.
- Record frozen upstream statement: Segment `1A` is immutable for all 1B remediation runs.

P0.2 Baseline realism scorecard materialization:
- Build one baseline scorecard artifact with these core metrics:
  - `country_gini`,
  - `top1_share`,
  - `top5_share`,
  - `top10_share`,
  - `eligible_country_nonzero_share`,
  - `southern_hemisphere_share`,
  - nearest-neighbor `p99/p50`.
- Emit companion tables for reproducibility:
  - country-share table (sorted descending),
  - region-share table,
  - nearest-neighbor quantile table.
- Persist outputs under remediation run root (reports-only, no data mutation of baseline run).

P0.3 State-level baseline checkpoints (pre-tuning diagnostics):
- Capture S2 baseline diagnostics:
  - `tile_weights` country/region mass profile,
  - `s2_run_report` policy/diagnostic values.
- Capture S4 baseline diagnostics:
  - `s4_alloc_plan` post-integerization country/region share profile.
- Capture S6/S8 baseline diagnostics:
  - local geometry and nearest-neighbor tail profile from `site_locations`.
- Purpose: establish where distortion appears before any knob movement.

P0.4 Iteration harness and storage discipline lock:
- Establish run folder discipline under `runs/fix-data-engine/segment_1B/`:
  - `baseline_authority`,
  - `current_candidate`,
  - `last_good`.
- Wire mandatory pre-run prune step for superseded failed candidates.
- Lock fast-lane posture:
  - start from changed state using rerun matrix in Section 2.1,
  - single-seed tuning until promotion candidate is selected.
- Lock certification posture:
  - required seed set `{42, 7, 101, 202}`,
  - full chain as required by certification rules.

P0.5 Baseline approval gate:
- No `P1` work starts until baseline scorecard is signed as authority.
- No policy/code tuning starts until pruning and run-retention protocol is active.

Definition of done:
- [x] baseline authority run and lineage tokens are pinned in the plan/work log.
- [x] baseline scorecard artifact and companion tables are generated and stored.
- [x] S2/S4/S6/S8 baseline checkpoint summaries are captured.
- [x] fast-lane and certification-lane run protocol is documented and ready.
- [x] prune-before-run workflow is active for `runs/fix-data-engine/segment_1B/`.
- [x] explicit go/no-go note recorded to enter `P1`.

P0 closure record:
- Date/time: `2026-02-13 12:52` local.
- Baseline authority run:
  - `run_id=c25a2675fbfbacd952b13bb594880e92`
  - `seed=42`
  - `manifest_fingerprint=c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8`
  - `parameter_hash=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7`
- Baseline artifacts:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p0_baseline_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p0_baseline_c25a2675fbfbacd952b13bb594880e92_country_share.csv`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p0_baseline_c25a2675fbfbacd952b13bb594880e92_region_share.csv`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p0_baseline_c25a2675fbfbacd952b13bb594880e92_nn_quantiles.csv`
- Harness/protocol artifacts:
  - `runs/fix-data-engine/segment_1B/iteration_protocol.json`
  - `runs/fix-data-engine/segment_1B/baseline_authority/baseline_pointer.json`
  - `runs/fix-data-engine/segment_1B/last_good/last_good_pointer.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p0_prune_check.txt`
- Go/no-go decision to enter `P1`: `GO`.

### P1 - S2 macro-mass reshape (country and region balance priors)
Goal:
- reshape country/region mass at the source (`S2`) so concentration collapse is reduced before integer allocation and jitter stages.

P1 scope boundary:
- Primary state: `S2`.
- Downstream use in P1: only targeted shape checks (`S2 -> S4 -> S8`) to confirm direction-of-movement.
- No `S4` or `S6` tuning in P1; those belong to `P2` and `P3`.

P1 file surfaces:
- Policy/config:
  - `config/layer1/1B/policy/policy.s2.tile_weights.yaml`
- Contract/schema (only as needed to govern new policy keys):
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml`
- Runtime:
  - `packages/engine/src/engine/layers/l1/seg_1B/s2_tile_weights/runner.py`

P1 tunable knobs (S2 only):
- `basis_mix` weights (`uniform`, `area_m2`, `population`)
- `region_floor_share` (region minimum mass floors)
- `country_cap_share_soft`
- `country_cap_share_hard`
- `topk_cap_targets` (`top1`, `top5`, `top10`)
- `concentration_penalty_strength`
- deterministic namespace keying for rebalance loop

P1 work blocks:
- `P1-A` Policy and contract enablement:
  - introduce/activate `blend_v2` policy block with legacy fallback path.
  - ensure policy fields are contract-governed (no hidden runtime knobs).
- `P1-B` Deterministic rebalance implementation in S2:
  - pass A: build raw mixed mass.
  - pass B: enforce floors/caps/penalty with deterministic tie-breaking.
  - preserve replay invariants for fixed `{seed, parameter_hash}`.
- `P1-C` Diagnostics surfaces and score extraction:
  - emit/compute `country_share_topk`, `country_gini_proxy`, `region_share_vector`.
  - compare against P0 baseline scorecard and record deltas.
- `P1-D` Calibration loop:
  - tune one knob group at a time (mix -> floors -> caps -> penalty).
  - keep iteration changes small (max 2-3 related knobs per cycle).
  - run fast-lane from `S2` onward using Section 2.1 rerun matrix.
- `P1-E` P1 lock handoff:
  - pin accepted S2 policy version + runner commit.
  - declare S2 locked for downstream phases unless explicit reopen is approved.

P1 success posture:
- concentration and coverage must move in the right direction versus P0 baseline.
- improvements must be reproducible on repeated same-seed runs.
- no region-floor or deterministic replay regressions.

Definition of done:
- [x] `blend_v2` policy path is active with legacy fallback retained.
- [x] S2 emits governed diagnostics needed for concentration and region-shape scoring.
- [x] at least one accepted P1 candidate shows concentration improvement versus P0 baseline on the authority metrics (`gini`, `top1`, `top5`, `top10`).
- [x] P1 candidate does not introduce new region-floor breaches in S2 diagnostics.
- [x] two consecutive same-seed fast-lane runs reproduce the same S2 score posture.
- [x] P1 lock record is written (policy bundle, commit refs, accepted metric snapshot).

P1 closure record:
- Date/time: `2026-02-13 15:30` local.
- Accepted run:
  - `run_id=335c9a7eec04491a845abc2a049f959f`
  - `seed=42`
  - `manifest_fingerprint=c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8`
  - `parameter_hash=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7`
- Evidence artifacts:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p1_candidate_335c9a7eec04491a845abc2a049f959f.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p1_repro_check_335c9a7eec04491a845abc2a049f959f_8b25602ba5ab48cb9fe459ffece15858.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p1_lock_record.json`
- Lock/pointer updates:
  - `runs/fix-data-engine/segment_1B/current_candidate/current_candidate_pointer.json`
  - `runs/fix-data-engine/segment_1B/last_good/last_good_pointer.json`
- Storage discipline:
  - superseded run-id folders pruned after lock (`a7d72773443c4206bb7ab44695274e92`, `8b25602ba5ab48cb9fe459ffece15858`);
  - retained active run-id for P1 handoff: `335c9a7eec04491a845abc2a049f959f`.
- Freeze statement:
  - P1 (`S2`) is now locked; downstream phases (`P2+`) must treat this S2 policy/shape as immutable unless an explicit reopen decision is recorded.

### P2 - S4 anti-collapse integer allocation closure
Focus:
- prevent post-integerization reconcentration from undoing S2 improvements.

Primary tuning surfaces:
- `S4` assignment-time guards (`country_share_soft_guard`, deterministic reroute, bounded residual redistribution).

Data outputs under evaluation:
- `s4_alloc_plan`
- S4 aggregated country/region allocation scorecards

Definition of done:
- [ ] post-S4 concentration/coverage metrics improve versus pre-P2 posture.
- [ ] no reconcentration breach introduced by integerization step.
- [ ] deterministic replay holds for fixed seed/policy hash.
- [ ] P2 lock recorded (S4 guard settings + expected score band).

### P3 - S6 geometry realism closure (within-country shape)
Focus:
- replace rigid uniform-in-cell posture with policy-driven mixture jitter while keeping geographic validity strict.

Primary tuning surfaces:
- `policy.s6.jitter.yaml` (`core_cluster`, `secondary_cluster`, `sparse_tail`, tail clamp).
- `S6` jitter mode selection and mixture parameterization.

Data outputs under evaluation:
- `s6_site_jitter`
- `site_locations` (via downstream `S7/S8` synthesis and egress)

Definition of done:
- [ ] nearest-neighbor tail ratio contracts by at least `20%` vs baseline (`B` floor).
- [ ] top-volume country cohort shows no stripe/corridor collapse sentinel.
- [ ] coordinate validity remains `100%` and point-in-country checks remain intact.
- [ ] P3 lock recorded (S6 jitter profile + expected local-geometry band).

### P4 - Integrated closure run (B target, B+ attempt)
Focus:
- run integrated candidate with locked `P1+P2+P3` settings and verify Segment 1B behaves as one coherent system.

Data outputs under evaluation:
- `tile_weights`
- `s4_alloc_plan`
- `s6_site_jitter`
- `site_locations`

Definition of done:
- [ ] all `B` hard realism gates pass on integrated candidate.
- [ ] no locked upstream phase (`P1/P2/P3`) needs reopening for data-shape contradictions.
- [ ] if near-threshold, execute bounded B+ retune loop without breaking B posture.

### P5 - Certification and freeze
Focus:
- certify promoted candidate across required seed set and freeze Segment 1B authority bundle.

Definition of done:
- [ ] hard `B` gates pass on all required seeds (or `B+` gates if achieved).
- [ ] stability CV limits meet the claimed grade.
- [ ] final lock set is recorded (policy files, runner commits, scorecard artifacts).
- [ ] superseded remediation run-id folders are pruned; retained folders are explicitly listed.

## 6) Failure triage map (state-first diagnosis)
- `Gini/top-k` fail only: retune `S2` caps and concentration penalty first.
- Region-floor fail with acceptable concentration: retune `S4` residual redistribution.
- NN-tail fail with concentration pass: retune `S6` sparse-tail component and clamp.
- Seed instability with mean pass: reduce high-sensitivity knobs and tighten deterministic balancing.
- Structural contract fail at any stage: fix implementation bug before further realism tuning.

## 7) Phase freeze rule
- Once a phase meets DoD and is declared locked, downstream phases must treat it as immutable.
- Reopening a locked phase requires explicit contradiction evidence and user approval.
- This prevents circular retuning and preserves causal attribution of realism movement.
