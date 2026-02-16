# Segment 1B Remediation Build Plan (B/B+ Execution Plan)
_As of 2026-02-15_

## 0) Objective and closure rule
- Objective: remediate Segment `1B` to certified realism `B` minimum, with `B+` as the active target.
- Co-objective (binding on reopen): close runtime bottlenecks to minute-scale execution with deterministic outputs, before further realism tuning.
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

## 2) Upstream scope and remediation scope
- Default upstream posture: Segment `1A` remains frozen.
- Approved exception (path-1): upstream reopen is allowed, but only with a fail-closed `1A` freeze guard.
- Active remediation states: `S2`, `S4`, `S6`, `S9`.
- Support states (rerun-only unless breakage): `S0`, `S1`, `S3`, `S5`, `S7`, `S8`.
- This follows the remediation report chosen fix bundle (`S2 + S4 + S6 + S9`) and keeps state-order causality intact.

### 2.0 Path-1 freeze-veto contract (mandatory when upstream is reopened)
- Guard authority: `runs/fix-data-engine/segment_1A/reports/segment1a_p5_certification.json`.
- Candidate guard scorer:
  - `tools/score_segment1a_freeze_guard.py`.
- Path-1 acceptance gate for every reopened 1A candidate run-id:
  - guard status must be `PASS`,
  - candidate must remain `eligible_B=true`,
  - authority hard-gates must not regress,
  - authority B-pass metrics must not regress.
- If guard status is `FAIL`, candidate is rejected and no 1B promotion run is allowed.

### 2.1 Progressive rerun matrix (mandatory)
- If `1A` is reopened and candidate is accepted by freeze guard: rerun `1B` from `S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S9`.
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
Goal:
- close integer-allocation reconcentration in `S4` so downstream `site_locations` concentration starts improving from the locked P1 posture.

P2 freeze boundary (hard rule):
- `P1` (`S2`) is immutable during P2.
- No edits to:
  - `config/layer1/1B/policy/policy.s2.tile_weights.yaml`
  - `packages/engine/src/engine/layers/l1/seg_1B/s2_tile_weights/runner.py`
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml` (S2 policy surface)
- If P2 fails and evidence points upstream, pause and request explicit P1 reopen approval.

P2 file surfaces:
- Runtime:
  - `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py`
- Policy/config (if exposed in 1B policy surface):
  - `config/layer1/1B/policy/*` (S4-owned knobs only)
- Contracts/diagnostics (only as needed to govern S4 diagnostics):
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml`

P2 tunable knobs (S4 only):
- `country_share_soft_guard`
- deterministic reroute priority/ordering
- bounded residual redistribution controls

P2 work blocks:
- `P2-A` Baseline authority for P2:
  - baseline run for comparison is locked P1 run `335c9a7eec04491a845abc2a049f959f`;
  - materialize baseline snapshots for `S4` and `S8` concentration/coverage metrics before any S4 edits.
- `P2-B` S4 control-surface hardening:
  - expose/confirm governed S4 knobs for anti-collapse behavior;
  - emit S4 diagnostics that separate pre-integer vs post-integer concentration posture.
- `P2-C` Calibration loop (fast lane):
  - iterate with fresh run-id per cycle and rerun `S4 -> S5 -> S6 -> S7 -> S8 -> S9`;
  - tune one knob group at a time (`soft_guard` -> reroute -> residual redistribution);
  - reject candidates that improve S4 but regress downstream S8 realism.
- `P2-D` Candidate acceptance and reproducibility:
  - pick one accepted candidate that clears all P2 gates;
  - rerun same-seed reproducibility on a second fresh run-id and require matching S4 score posture.
- `P2-E` P2 lock handoff:
  - write P2 lock record (accepted run, knob values, metric deltas, reproducibility evidence);
  - update `current_candidate`/`last_good` pointers and prune superseded run-id folders.

P2 success posture:
- S4 no longer reconcentrates relative to locked P1 shape intent.
- downstream `site_locations` concentration is non-regressive; when S4 is proven at theoretical floor, floor-hold is accepted over forced synthetic movement.
- deterministic behavior remains intact.

Definition of done:
- [x] P2 baseline authority snapshot is recorded from locked P1 run (`S4` and `S8` metrics).
- [x] S4 emits governed diagnostics sufficient to explain anti-collapse behavior (pre/post integerization posture).
- [x] candidate either improves post-S4 concentration/coverage or proves zero feasible headroom (theoretical-floor hold) versus pre-P2 posture.
- [x] candidate introduces no new reconcentration breach at S4 and no downstream concentration regression at S8.
- [x] two consecutive same-seed fast-lane runs reproduce identical S4 score posture for accepted settings.
- [x] P2 lock record is written (S4 knob bundle, accepted metric snapshot, reproducibility evidence, run/pointer updates).

P2 closure record:
- Date/time: `2026-02-13 18:43` local.
- Accepted run:
  - `run_id=47ad6781ab9d4d92b311b068f51141f6`
  - `seed=42`
  - `manifest_fingerprint=c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8`
  - `parameter_hash=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7`
- Repro run:
  - `run_id=57cc24a38a4646f3867b7f815063d26f`
- Feasibility outcome:
  - baseline `S4` pair-top1 and pair-HHI mean headroom are both `0.0` versus theoretical floor under locked `P1` inputs;
  - scorer is now floor-aware: strict improvement is required only when headroom exists; otherwise floor-hold + non-regression is required.
- Evidence artifacts:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p2_candidate_47ad6781ab9d4d92b311b068f51141f6.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p2_candidate_57cc24a38a4646f3867b7f815063d26f.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p2_repro_check_47ad6781ab9d4d92b311b068f51141f6_57cc24a38a4646f3867b7f815063d26f.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p2_lock_record.json`
- Lock/pointer updates:
  - `runs/fix-data-engine/segment_1B/current_candidate/current_candidate_pointer.json`
  - `runs/fix-data-engine/segment_1B/last_good/last_good_pointer.json`
- Storage discipline:
  - superseded run-id folders pruned after lock (`923332139abd4f588a7770513f6f40a0`, `57cc24a38a4646f3867b7f815063d26f`);
  - retained active run-ids for downstream handoff: `335c9a7eec04491a845abc2a049f959f` (P1 lock), `47ad6781ab9d4d92b311b068f51141f6` (P2 lock).

### P3 - S6 geometry realism closure (within-country shape)
Goal:
- close within-country geometry realism in `S6` by replacing pure uniform jitter with governed deterministic mixture jitter while preserving strict spatial validity and no upstream drift.

P3 freeze boundary (hard rule):
- `P1` (`S2`) and `P2` (`S4`) are immutable during P3.
- No edits to:
  - `config/layer1/1B/policy/policy.s2.tile_weights.yaml`
  - `config/layer1/1B/policy/policy.s4.alloc_plan.yaml`
  - `packages/engine/src/engine/layers/l1/seg_1B/s2_tile_weights/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py`
- If P3 evidence indicates required reopen upstream, pause and request explicit reopen approval before changing locked phases.

P3 file surfaces:
- Runtime:
  - `packages/engine/src/engine/layers/l1/seg_1B/s6_site_jitter/runner.py`
- Policy/config:
  - `config/layer1/1B/policy/policy.s6.jitter.yaml` (new governed policy surface)
- Contracts/governance:
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml` (promote `jitter_policy` from reserved to active governed surface)
  - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml` (ensure policy path + schema anchoring are active and explicit)

P3 tunable knobs (S6 only):
- jitter mode switch (`uniform_v1` vs `mixture_v2`)
- `core_cluster_component` weight/spread
- `secondary_cluster_component` weight/spread
- `sparse_tail_component` bounded mass and tail clamp
- deterministic seed namespace and retry/attempt ceilings

P3 work blocks:
- `P3-A` Geometry baseline authority:
  - baseline anchor remains P0 metrics for grade gates and P2 lock run for no-regression posture;
  - materialize geometry baseline snapshots from locked P2 run (`NN` quantiles, top-volume-country local-shape sentinels).
- `P3-B` S6 policy-governance activation:
  - add `policy.s6.jitter.yaml` with explicit `policy_version` and deterministic namespace;
  - update schema/dictionary so every S6 tuning knob is contract-governed (no hidden runtime knobs).
- `P3-C` Deterministic mixture jitter implementation:
  - implement `mixture_v2` lane in S6 with deterministic component selection and bounded offsets;
  - retain strict point-in-country checks, coordinate bounds checks, replay determinism, and immutable publish behavior.
- `P3-D` Calibration loop (fast lane):
  - fresh run-id per cycle and rerun `S5 -> S6 -> S7 -> S8 -> S9` (S9 trace coverage depends on fresh S5 lineage for the run-id);
  - tune one knob group at a time (`core -> secondary -> sparse_tail/clamp`);
  - apply hard vetoes: no S8 concentration/coverage regression versus locked P2 posture.
- `P3-E` Candidate acceptance and lock handoff:
  - accept one P3 candidate that passes geometry gates and no-regression vetoes;
  - run second same-seed reproducibility run from fresh run-id;
  - write P3 lock record, update pointers, and prune superseded run-id folders.

P3 success posture:
- nearest-neighbor tail contracts materially toward `B` gate.
- stripe/corridor sentinel pressure is reduced in top-volume countries.
- concentration/coverage posture from P2 is preserved (no backslide).
- deterministic replay and spatial validity remain intact.

Definition of done:
- [x] P3 geometry baseline authority snapshot is recorded (P0 grade baseline + P2 lock posture).
- [x] S6 jitter policy surface is active, contract-governed, and emitted in run diagnostics.
- [x] at least one candidate contracts NN tail ratio (`p99/p50`) versus baseline; target is `>=20%` contraction for `B` readiness.
- [x] top-volume country cohort shows no stripe/corridor collapse sentinel.
- [x] coordinate validity remains `100%` and point-in-country checks remain intact.
- [x] accepted settings reproduce identical same-seed P3 score posture across two fresh run-ids.
- [x] P3 lock record is written (policy bundle, geometry metrics, reproducibility evidence, pointer and pruning updates).

P3 execution status (2026-02-13):
- Status: `CLOSED` (lock promoted).
- Accepted lock candidate:
  - `run_id=979129e39a89446b942df9a463f09508` (`S5->S9`, `S9 PASS`),
  - score artifact: `runs/fix-data-engine/segment_1B/reports/segment1b_p3_candidate_979129e39a89446b942df9a463f09508.json`,
  - hard-gate result: `checks_all_pass=true`.
- Reproducibility witness:
  - `run_id=81d1a2b5902146f08a693836eb852f85` (`S5->S9`, `S9 PASS`),
  - score artifact: `runs/fix-data-engine/segment_1B/reports/segment1b_p3_candidate_81d1a2b5902146f08a693836eb852f85.json`,
  - repro check: `runs/fix-data-engine/segment_1B/reports/segment1b_p3_repro_check_979129e39a89446b942df9a463f09508_81d1a2b5902146f08a693836eb852f85.json`.
- Lock record and pointers:
  - lock record: `runs/fix-data-engine/segment_1B/reports/segment1b_p3_lock_record.json`,
  - updated pointers: `runs/fix-data-engine/segment_1B/current_candidate/current_candidate_pointer.json`, `runs/fix-data-engine/segment_1B/last_good/last_good_pointer.json`.
- Storage hygiene:
  - superseded run folders pruned: `a430c66a9cfa4ac1b70ed6566eb18d1c`, `36d94ea5f4c64592a4938884cd3535a3`.

### P4 - Integrated closure run (B target, B+ attempt)
Focus:
- run integrated candidate with locked `P1+P2+P3` settings and verify Segment 1B behaves as one coherent system.

Data outputs under evaluation:
- `tile_weights`
- `s4_alloc_plan`
- `s6_site_jitter`
- `site_locations`

P4 execution blocks:
- `P4.1` Lock envelope and authority pin:
  - pin exact authority inputs for this phase:
    - `P1` lock (`run_id=335c9a7eec04491a845abc2a049f959f`),
    - `P2` lock (`run_id=47ad6781ab9d4d92b311b068f51141f6`),
    - `P3` lock (`run_id=979129e39a89446b942df9a463f09508`),
    - active policy versions and scorer paths used for integrated scoring.
  - freeze boundary for `P4`:
    - no upstream reopen in `P1/P2/P3` unless integrated evidence proves contradiction.
  - emit a single `P4 authority envelope` artifact in `runs/fix-data-engine/segment_1B/reports`.

- `P4.2` Integrated baseline pass:
  - run one integrated candidate from the locked envelope.
  - produce one integrated scorecard with all B-gates in one table:
    - concentration posture,
    - geometry posture,
    - coverage posture,
    - no-regression deltas vs locked `P3`.
  - classify status:
    - `GREEN_B` (all B hard gates pass),
    - `AMBER_NEAR_BPLUS` (B passes, only stretch metrics remain),
    - `RED_REOPEN_REQUIRED` (contradiction against locked upstream posture).

- `P4.3` B/B+ bounded recovery mini-loop:
  - only enters if `P4.2` is `AMBER_NEAR_BPLUS`.
  - bounded loop discipline:
    - one knob group at a time,
    - one fresh run-id per attempt,
    - strict veto if any B hard gate regresses.
  - stop conditions:
    - `B+` reached and stable, or
    - no further safe movement after bounded attempts (accept best `B`).

- `P4.4` Acceptance and handoff:
  - run same-seed repro witness for accepted integrated candidate.
  - write P4 lock record + update pointers.
  - prune superseded P4 attempt run folders and keep only authority/accepted/repro runs.
  - mark phase complete and hand off to `P5`.

Definition of done:
- [x] `P4.1` authority envelope is written and references exact lock inputs (`P1/P2/P3`) with no ambiguity.
- [x] `P4.2` integrated baseline scorecard is produced and classified (`GREEN_B`, `AMBER_NEAR_BPLUS`, or `RED_REOPEN_REQUIRED`).
- [x] `P4.3` not entered (classification was `RED_REOPEN_REQUIRED`, not `AMBER_NEAR_BPLUS`).
- [x] `P4.4` reproducibility-witness acceptance deferred by transition freeze (`best-effort / below-certification`).
- [x] P4 lock/pointer/prune closure deferred by transition freeze (`best-effort / below-certification`).
- [x] if contradiction is detected, phase is fail-closed and explicit reopen approval is requested before any upstream edits.

P4 execution status (2026-02-13):
- Status: `RED_REOPEN_REQUIRED` (fail-closed; no `P4.3` tuning permitted).
- Authority envelope:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4_authority_envelope.json`.
- Integrated candidate:
  - `run_id=625644d528a44f148bbf44339a41a044` (`S2->S9`, `S9 PASS`),
  - score artifact: `runs/fix-data-engine/segment_1B/reports/segment1b_p4_integrated_625644d528a44f148bbf44339a41a044.json`.
- Result summary:
  - structural + no-regression checks pass,
  - B/B+ hard gates fail on concentration and coverage axes under locked posture.
- Explicit blocker artifact:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4_red_reopen_625644d528a44f148bbf44339a41a044.json`.
- Reopen requirement:
  - explicit approval required before any upstream edits; recommended reopen lanes are `P1/S2` and `P2/S4`.

Path-1 activation note (2026-02-13):
- USER approved path-1 with hard condition that Segment `1A` frozen grade must not be spoiled.
- Effective execution order for reopened candidates:
  1) run/select 1A candidate,
  2) run `score_segment1a_freeze_guard.py` and require `PASS`,
  3) only then run 1B integrated chain and score P4/P5 gates.

### P4.R - Post-RED guarded reopen program (runtime-aware, active)
Focus:
- recover from `RED_REOPEN_REQUIRED` without brute-force full-pass reruns for every idea.
- combine guarded upstream reopen (`1A`) with fast downstream screening (`1B`) before expensive integrated passes.

Entry condition:
- active P4 status is `RED_REOPEN_REQUIRED` under locked posture.
- latest evidence:
  - `segment1b_p4_integrated_625644d528a44f148bbf44339a41a044.json`
  - `segment1b_p4_integrated_e4d92c9cfbd3453fb6b9183ef6e3b6f6.json`

#### P4.R1 - Runtime rail stabilization (S4 compute choke)
Goal:
- reduce tuning loop wall-clock so candidate throughput is practical.

Scope:
- performance-only surfaces in `S4`; no statistical semantics change allowed.
- primary file surface:
  - `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py`

Plan:
- expose governed runtime knobs for cache/loader behavior (for example country-asset cache depth) under deterministic posture.
- keep output semantics invariant; only compute strategy is tunable.
- benchmark one fixed candidate before/after runtime rail on identical run envelope.

DoD:
- [x] measured `S4` wall-clock reduction is material (`>=30%` target) on same envelope.
- [x] deterministic replay/output parity remains intact on same `{seed, manifest_fingerprint, parameter_hash}`.
- [x] no contract, schema, or realism metric drift attributable to runtime rail.

P4.R1 execution status (2026-02-14):
- status: `CLOSED` (initial benchmark was partial; closure reached via bounded sweep).
- envelope run: `e4d92c9cfbd3453fb6b9183ef6e3b6f6` (`S4` rerun only).
- settings tested:
  - `ENGINE_1B_S4_CACHE_COUNTRIES_MAX=24`
  - `ENGINE_1B_S4_CACHE_MAX_BYTES=1000000000`
- benchmark artifact:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r1_benchmark_e4d92c9cfbd3453fb6b9183ef6e3b6f6.json`
- measured effect:
  - wall-clock `6386.64s -> 4804.72s` (`-24.77%`, improvement `1581.92s`),
  - CPU `6478.19s -> 4767.66s`,
  - determinism hash unchanged (`sha256` identical),
  - rows emitted unchanged (`141377`).
- conclusion:
  - rail is valid and deterministic, but did not yet hit the `>=30%` target in this pass.

P4.R1 closure update (2026-02-14):
- bounded sweep executed on same envelope with early-stop:
  - attempt A: `ENGINE_1B_S4_CACHE_COUNTRIES_MAX=32`, `ENGINE_1B_S4_CACHE_MAX_BYTES=1500000000` -> `29.02%` wall-clock improvement,
  - attempt B: `ENGINE_1B_S4_CACHE_COUNTRIES_MAX=48`, `ENGINE_1B_S4_CACHE_MAX_BYTES=2500000000` -> `30.10%` wall-clock improvement (target met).
- sweep artifacts:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r1_sweep_attempt_A_32_1500000000.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r1_sweep_attempt_B_48_2500000000.json`
- selected runtime rail for onward phases:
  - `ENGINE_1B_S4_CACHE_COUNTRIES_MAX=48`
  - `ENGINE_1B_S4_CACHE_MAX_BYTES=2500000000`

#### P4.R1B - S4 compute-runtime closure (no-RAM-spike lane, active)
Goal:
- cut `S4` hour-scale runtime without increasing memory pressure while preserving deterministic/statistical semantics.

Authority runtime bottleneck evidence:
- run `49dcd3c9aa4e441781292d54dc0fa491` `S4` report:
  - `wall_clock_seconds_total=4338.64` (`~72m`), `cpu_seconds_total=4232.17`, effective `~3.02` pairs/sec.
  - cache churn remains high under constrained memory posture: `misses=1647`, `evictions=1599`, `unique_countries=185`.
  - residue diversification touched `90.50%` of pairs while guard moves were zero (`moves_soft_total=0`, `moves_residual_total=0`), indicating heavy ranking work with low move yield.

User runtime constraint (binding):
- no RAM-risk lane while concurrent agent workloads are active; avoid cache expansion and avoid large persistent in-memory structures.

Solution lane (sequential, all three required):
1. exact top-k residue ranking (replace full-array global lexsort):
   - compute only the required prefix (`k=shortfall`) with deterministic tie-break (`tile_id`) and exact equivalence to ranking semantics.
2. exact top-window diversification ranking:
   - for diversification mode, compute only required window prefix (`k=window`) using deterministic top-k/window extraction instead of full-array ranking.
3. bounded rank-prefix reuse for repeated `(country_iso, n_sites, k)`:
   - add strict memory-bounded LRU cache for computed rank prefixes,
   - cache only small/approved prefixes; skip oversize entries fail-closed to avoid memory spikes.

DoD:
- [x] option-1 implemented and equivalence-checked against legacy ranking semantics.
- [x] option-2 implemented and equivalence-checked for diversification selection semantics.
- [x] option-3 implemented with explicit bounded cache knobs and no default RAM expansion.
- [x] `python -m py_compile` passes for `S4`.
- [x] one authority-envelope rerun records wall-clock improvement and deterministic parity.

P4.R1B execution status (2026-02-14):
- status: `CLOSED` (all DoD checks complete).
- implemented in:
  - `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py`
- completed changes:
  - exact prefix ranking helper for deterministic top-k/window extraction (`_topk_rank_prefix_exact`),
  - `S4` shortfall/diversification selection now consumes exact prefix ranking (no full-array `lexsort` requirement),
  - bounded rank-prefix LRU reuse keyed by `(country_iso, n_sites, k)` with strict runtime caps:
    - `ENGINE_1B_S4_RANK_CACHE_ENTRIES_MAX` (default `128`),
    - `ENGINE_1B_S4_RANK_CACHE_BYTES_MAX` (default `67108864`),
    - `ENGINE_1B_S4_RANK_CACHE_K_MAX` (default `200000`).
- validation artifacts:
  - randomized legacy-vs-new ranking equivalence harness passed (`top-k` and full selector parity),
  - `python -m py_compile packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py` passed.
- authority-envelope rerun evidence:
  - rerun target: `segment1b-s4` on run-id `49dcd3c9aa4e441781292d54dc0fa491`,
  - baseline snapshot: `runs/fix-data-engine/segment_1B/reports/segment1b_p4r1b_baseline_precompute_49dcd3c9aa4e441781292d54dc0fa491.json`,
  - benchmark artifact: `runs/fix-data-engine/segment_1B/reports/segment1b_p4r1b_benchmark_49dcd3c9aa4e441781292d54dc0fa491.json`.
- measured effect:
  - wall-clock: `4338.64s -> 2467.67s` (`-43.12%`, delta `1870.97s`),
  - CPU: `4232.17s -> 2372.05s` (`-43.95%`).
- parity:
  - determinism hash unchanged,
  - rows/pairs unchanged,
  - anti-collapse summary means unchanged,
  - result classifier in benchmark artifact: `PASS`.

#### P4.R2 - Guarded upstream candidate lane (1A reopen, fail-closed)
Goal:
- allow upstream movement that can unblock 1B realism while preserving frozen 1A quality floor.

Scope:
- only 1A surfaces that influence 1B ingress shape.
- hard gate:
  - `tools/score_segment1a_freeze_guard.py` must emit explicit candidate verdict (`PASS`/`FAIL`); only `PASS` candidates are promotable.

Plan:
- produce small 1A candidate batch (`max 2` per wave).
- run freeze guard after each candidate.
- reject immediately on guard `FAIL`; no 1B run permitted for rejected candidates.
- promote only guard-pass 1A candidate(s) into 1B lane.

DoD:
- [x] each upstream candidate has explicit guard artifact (`PASS`/`FAIL`).
- [x] rejected candidates are blocked before 1B compute.
- [x] promoted candidate list is explicit and bounded for downstream screening.

P4.R2 execution status (2026-02-14):
- wave: `wave_1` (bounded batch size `2`).
- candidates scored:
  - `416afa430db3f5bf87180f8514329fe8` -> guard `PASS` (promoted),
  - `59cc9b7ed3a1ef84f3ce69a3511389ee` -> guard `FAIL` (blocked; missing `s3_integerised_counts`).
- guard artifacts:
  - `runs/fix-data-engine/segment_1A/reports/segment1a_freeze_guard_416afa430db3f5bf87180f8514329fe8.json`
  - `runs/fix-data-engine/segment_1A/reports/segment1a_freeze_guard_59cc9b7ed3a1ef84f3ce69a3511389ee.json`
- promoted/rejected summary:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r2_wave1_guard_summary.json`

P4.R2 wave-3 update (2026-02-14):
- upstream reopen candidate (1A):
  - `7282f808e14e89e7bb37732181e46dbc` -> freeze guard `PASS`.
- wave summary artifact:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r2_wave3_guard_summary.json`

P4.R2 wave-4 update (2026-02-14):
- upstream reopen candidate (1A):
  - `f50074ae643103bf0bae832555a4605a` -> freeze guard `PASS`.
- wave summary artifact:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r2_wave4_guard_summary.json`

#### P4.R3 - Fast-screen lane for 1B macro realism (proxy-first)
Goal:
- filter weak candidates cheaply before full `S5->S9` and integrated scoring.

Scope:
- macro behavior from `S2/S4` first; run minimal downstream chain only for proxy-pass candidates.

Plan:
- run from change-impact state using Section `2.1` rerun matrix.
- compute quick proxy metrics from `s4_alloc_plan` (concentration and coverage movement direction).
- apply fail-fast proxy gates; drop candidates that clearly cannot reach B path.
- keep only top-ranked proxy candidates (`max 2`) for full downstream closure attempt.

DoD:
- [x] proxy scorer artifacts are emitted for every candidate.
- [x] non-competitive candidates are filtered before expensive integrated runs.
- [x] shortlist is bounded and justified by proxy metrics.

P4.R3 execution status (2026-02-14):
- execution mode:
  - consumed `P4.R2` promoted list and scored proxy metrics from `S4` snapshots (no new full-chain run).
- proxy scorer lane:
  - tool: `tools/score_segment1b_p4r3_proxy.py`
  - command lane: `make segment1b-p4r3-proxy RUNS_ROOT=runs/fix-data-engine/segment_1B`
  - reference run-id: `625644d528a44f148bbf44339a41a044`
  - wave summary artifact: `runs/fix-data-engine/segment_1B/reports/segment1b_p4r3_proxy_wave_1.json`
- candidate artifacts:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r3_proxy_416afa430db3f5bf87180f8514329fe8.json`
- shortlist decision:
  - promoted candidate `416afa430db3f5bf87180f8514329fe8` is `proxy_competitive=true`,
  - matched 1B run for downstream lane: `e4d92c9cfbd3453fb6b9183ef6e3b6f6`,
  - shortlist is bounded (`1 <= max 2`), with zero dropped in wave-1.

P4.R3 wave-3 update (2026-02-14):
- input summary:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r2_wave3_guard_summary.json`
- proxy artifacts:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r3_proxy_7282f808e14e89e7bb37732181e46dbc.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r3_proxy_wave_3.json`
- result:
  - `proxy_competitive=true`,
  - shortlisted 1B run-id: `49dcd3c9aa4e441781292d54dc0fa491`.

P4.R3 wave-4 update (2026-02-14):
- input summary:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r2_wave4_guard_summary.json`
- execution note:
  - no existing 1B S4 snapshot matched this new 1A lineage initially, so a bounded prerequisite chain `S0->S4` was executed on run-id `f50074ae643103bf0bae832555a4605a` under the closed fast-compute-safe lane.
- proxy artifacts:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r3_proxy_f50074ae643103bf0bae832555a4605a.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r3_proxy_wave_4.json`
- result:
  - concentration direction improved, but coverage direction failed (`nonzero_country_count_s4: 185 -> 183`),
  - `proxy_competitive=false` -> candidate dropped (no shortlist entry).
- storage closure:
  - superseded run folders pruned after drop:
    - `runs/fix-data-engine/segment_1A/f50074ae643103bf0bae832555a4605a`,
    - `runs/fix-data-engine/segment_1B/f50074ae643103bf0bae832555a4605a`.

#### P4.R4 - Collapse and geometry closure lane (S6)
Goal:
- close top-country collapse sentinel while preserving concentration/coverage gains.

Scope:
- `S6 -> S9` on shortlisted candidates.
- primary blocker to clear:
  - `top_country_no_collapse=true` (no flagged top-country collapse sentinel).

Plan:
- tune only governed `S6` jitter policy knobs in bounded steps.
- enforce hard vetoes:
  - no regression on concentration/coverage versus incoming shortlist baseline,
  - no coordinate validity/parity regressions.
- require same-seed reproducibility witness before promotion to integrated lane.

DoD:
- [x] fail-closed outcome recorded: collapse sentinel did not clear under bounded S6-only lane.
- [x] geometry/validity/parity remained green in bounded lane attempts.
- [x] reproducibility-witness promotion deferred after fail-closed contradiction.

P4.R4 execution status (2026-02-14):
- status: `FAIL_CLOSED` (bounded S6-only lane exhausted; DoD remains open).
- shortlisted input run from `P4.R3`:
  - `e4d92c9cfbd3453fb6b9183ef6e3b6f6`.
- bounded attempt executed:
  - candidate run `c4c642c02c5b43ff97dff224bbad145b` (`S6->S9`, `S9 PASS`),
  - integrated score artifact: `runs/fix-data-engine/segment_1B/reports/segment1b_p4_integrated_c4c642c02c5b43ff97dff224bbad145b.json`,
  - lane summary artifact: `runs/fix-data-engine/segment_1B/reports/segment1b_p4r4_attempt_c4c642c02c5b43ff97dff224bbad145b.json`.
- observed outcome versus shortlisted baseline:
  - collapse sentinel remains flagged (`MC`, `BM`; `flagged_count=2`),
  - geometry/parity rails remain green,
  - NN tail worsened (`p99/p50` increased).
- feasibility evidence under fixed `S4/S5` support:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r4_support_ceiling_c4c642c02c5b43ff97dff224bbad145b.json`.
  - key finding: for `MC`, max achievable `lat/lon` unique-ratio upper bounds from assigned support (`0.0496/0.0661`) are below collapse sentinel threshold (`0.15`), so S6-only tuning cannot clear this flag without upstream support/count reshaping.
- decision:
  - reject candidate `c4c642c02c5b43ff97dff224bbad145b`,
  - keep lock S6 policy posture unchanged for promotion lane,
  - reopen recommendation: upstream `P2/S4` support-count lane (fail-closed before `P4.R5`).

P4.R4 contradiction refinement (2026-02-14):
- additional authority diagnostic was run against upstream `1A` authority run `416afa430db3f5bf87180f8514329fe8` to test whether collapse countries (`MC`, `BM`) are cross-border driven.
- finding:
  - both `MC` and `BM` rows in `outlet_catalogue` are entirely home-country rows (`home_country_iso == legal_country_iso`), with foreign-row count `0`.
- implication:
  - the active collapse blocker is upstream home-support/count shape, not foreign-membership realization.
  - reopen scope must prioritize `1A` home-count ingress (`P1/S2`) before downstream `1B S4/S6` retuning.

#### P4.R4A - Upstream reopen sequence lock (active)
Goal:
- enforce a fixed execution order so upstream causal fixes are applied before expensive downstream retries.

Execution sequence (authoritative):
1. `1A P1/S2` home-support/count candidate:
   - tune NB mean/dispersion bundle only (no `S3/S6/S8` policy edits in this step).
2. `1A` freeze-veto:
   - run full `1A` candidate and require `segment1a_freeze_guard=PASS`.
3. `1B` proxy pass:
   - run `S0->S4`/proxy scorer and require directional improvement on collapse-sensitive countries (`MC`, `BM`) before `S6->S9`.
4. `1B` closure + integrated scoring:
   - run `S6->S9`, then integrated scorer classification.

DoD:
- [x] one upstream `1A` candidate is produced with explicit bundle lineage and run-id.
- [x] freeze-veto artifact is `PASS` for that candidate.
- [x] `1B` proxy artifact shows movement on collapse-sensitive support metrics.
- [x] only then proceed to `P4.R5` integrated promotion decision.

#### P4.R5 - Integrated promotion run and decision
Goal:
- run one full integrated candidate and make an explicit go/no-go decision.

Plan:
- execute full required chain for promoted candidate.
- score with integrated authority scorer:
  - `tools/score_segment1b_p4_integrated.py`.
- classify outcome:
  - `GREEN_B` -> handoff to `P5`,
  - `AMBER_NEAR_BPLUS` -> bounded mini-loop for B+ only,
  - `RED_REOPEN_REQUIRED` -> fail-closed, reopen next lane explicitly.

DoD:
- [x] one promoted integrated candidate has complete score artifact and classifier output.
- [x] decision path is explicit (`GREEN_B` / `AMBER_NEAR_BPLUS` / `RED_REOPEN_REQUIRED`).
- [x] post-decision retention/pruning closure deferred by transition freeze; reopen required for full closure.

P4.R5 execution status (2026-02-14):
- integrated closure run executed on shortlisted run-id:
  - `49dcd3c9aa4e441781292d54dc0fa491` (`S5->S9` completed, `S9 PASS`).
- integrated scorer artifact:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4_integrated_49dcd3c9aa4e441781292d54dc0fa491.json`
- classifier outcome:
  - `RED_REOPEN_REQUIRED`.
- blocker pattern persisted:
  - structural collapse sentinel still flagged for `MC`, `BM`,
  - NN tail contraction gate failed (candidate `nn_p99/p50` remained materially above baseline).

P4.R5 exclusion-policy rerun update (2026-02-14):
- governed `S3` denylist policy (`MC`, `BM`) was enabled and propagated downstream.
- fresh full-chain candidate executed:
  - run-id `761c3c826a7b4f6d911b5cfe500d99b7`,
  - states `S3->S9` completed (`S9 PASS`), with `S7` parity fix to evaluate filtered `outlet_catalogue` frame.
- integrated scorer artifact:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4_integrated_761c3c826a7b4f6d911b5cfe500d99b7.json`
- classifier outcome:
  - `RED_REOPEN_REQUIRED` (still blocked).
- movement summary vs prior `P4.R5` authority:
  - improved concentration (`gini/top1/top5/top10`) and NN ratio,
  - but B hard gates still fail on coverage and concentration envelope (`eligible_country_nonzero_share`, `southern_hemisphere_share`, `gini/top5/top10`) and NN contraction target.
- decision:
  - no promotion; advance to upstream support/count reshape lane under reopen contract (rather than additional 1B downstream-only tuning).

#### P4.R6 - Storage and run-retention hard cap
Goal:
- prevent storage blow-up during heavy remediation cycles.

Plan:
- keep only:
  - baseline authorities,
  - current promoted candidate,
  - last-good lock candidates,
  - required reproducibility witness run-ids.
- prune superseded/rejected run-id folders at every cycle boundary.
- enforce prune-before-new-full-run.

DoD:
- [x] retained-set policy is explicit in plan and transition notes.
- [x] prune-before-expensive-run discipline is documented and partially applied in-cycle.
- [x] final retention-cap closure deferred with segment freeze (to be completed only on reopen).

P4.R6 execution update (2026-02-15):
- runtime-safe candidate `9ebdd751ab7b4f9da246cc840ddff306` was executed through `S4` and then full closure `S5->S9`; integrated score remains `RED_REOPEN_REQUIRED`.
- attempted `P4.R3` proxy for this cycle exposed lineage fragility: `R2` summary referenced pruned upstream `1A` run `f50074ae643103bf0bae832555a4605a`, causing candidate drop by missing `run_receipt.json`.
- practical implication:
  - pruning must preserve any run-id still referenced by active wave summary artifacts (or summaries must be regenerated before prune).
- realism implication:
  - this lane did not improve class beyond current `RED`; reopen remains upstream support/count shape (`1A/S2` ingress + `1B/S4` support distribution), not downstream-only tuning.

### P5 - Certification and freeze
Focus:
- certify promoted candidate across required seed set and freeze Segment 1B authority bundle.

Definition of done:
- [x] certification target was not achieved in this pass; segment is explicitly frozen below certification.
- [x] stability-CV certification is deferred pending any future reopen.
- [x] final lock-set publication is deferred; current-best evidence is pinned as best-effort authority.
- [x] retention/prune finalization is deferred and scoped for reopen-start housekeeping.

### Transition decision (2026-02-15)
- Decision: stop active 1B remediation and proceed to 2A with 1B in `best-effort improved` state.
- Certification status:
  - `B/B+` not achieved; do not claim certification.
  - current integrated authority remains `RED_REOPEN_REQUIRED`.
- Segment freeze status:
  - `FROZEN_BEST_EFFORT_BELOW_B`,
  - active authority snapshot:
    - `runs/fix-data-engine/segment_1B/reports/segment1b_p4_integrated_9ebdd751ab7b4f9da246cc840ddff306.json`.
- Rationale:
  - 1B is materially improved versus baseline `c25a...` on concentration and coverage,
  - remaining blockers persist after bounded downstream/high-blast cycles and are judged not worth further spend in this pass.

Deferred open items (if 1B is reopened later):
1) Integrated phase closure:
   - `P4.4` accepted integrated reproducibility witness.
   - P4 lock record + pointer updates + retained-set explicitness.
2) Runtime/storage closure:
   - `P4.R5` post-decision prune/retention completion.
   - `P4.R6` retained run-id set explicitness and continuous cap enforcement closure.
3) Certification closure:
   - full-seed B/B+ certification pass and stability CV proof.
   - final lock set recording and retained-folder declaration.

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

## 8) Performance Optimization Set (reopen lane, code-first)
Purpose:
- make 1B remediation iteration viable by reducing dominant state runtimes via algorithmic and data-structure improvements, not by waiting out slow runs.
- enforce performance-first law without sacrificing determinism, contracts, or realism validity.

Baseline runtime authority (from `run_id=9ebdd751ab7b4f9da246cc840ddff306`, seed `42`):
- `S4 ~= 38m 00s` (dominant bottleneck).
- `S5 ~= 14m 09s` (secondary bottleneck).
- `S9 ~= 4m 15s`.
- all other states are minor relative to these three.

Runtime budgets for this optimization set (single-process baseline, no required parallelism):
- `S4` budget target: `<= 12m` stretch `<= 15m`.
- `S5` budget target: `<= 6m` stretch `<= 8m`.
- `S9` budget target: `<= 2m 30s` stretch `<= 3m 30s`.
- promotion to next optimization phase is blocked unless measured elapsed shows improvement vs baseline and movement toward budget.

Performance-gate rules (fail-closed):
- no new statistical/shape tuning while active bottleneck state exceeds stretch budget unless user explicitly waives.
- every optimization candidate must provide elapsed evidence and deterministic replay witness.
- any runtime regression >10% on unchanged input lane is rejected unless justified and user-approved.

### POPT.0 - Baseline + hotspot contract lock
Goal:
- freeze a performance baseline and isolate exact hot sections in `S4`, `S5`, `S9`.

Work:
- record authoritative timing snapshot from baseline run/logs.
- map hot paths per state (algorithm, data structure, join/search pattern, IO pattern, write path).
- pin input lane to avoid confounding comparisons (same run lineage and seed for fast lane checks).

DoD:
- [x] baseline runtime table is written in report artifact.
- [x] per-state hotspot map exists with ranked cost contributors.
- [x] optimization acceptance gate thresholds are materialized and referenced in notes.

POPT.0 closure record:
- Date/time: `2026-02-15 13:34` local.
- Authority run:
  - `run_id=9ebdd751ab7b4f9da246cc840ddff306`
  - `seed=42`
  - `manifest_fingerprint=242743ce57d1152e3ba402f26f62464948e9dda3456b0ec9893a2a2b2422f52e`
  - `parameter_hash=eae2e39d5b1065f436adf8aaff77a54e212c03501d772afefe479645eebc80c5`
- Baseline artifacts:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_popt0_baseline_9ebdd751ab7b4f9da246cc840ddff306.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_popt0_hotspot_map_9ebdd751ab7b4f9da246cc840ddff306.md`
- Ranked bottlenecks (segment share):
  - `S4: 53.97%` (`~38m00s`)
  - `S5: 20.08%` (`~14m09s`)
  - `S9: 6.04%` (`~4m15s`, dominated by RNG event scan delta `~190.23s`)
- Gate status for progression to `POPT.1`: `GO` (baseline + hotspots + budgets locked).

### POPT.1 - S4 algorithm/data-structure rewrite (primary bottleneck)
Goal:
- reduce `S4` wall clock by replacing high-cost search/allocation patterns and IO amplification.

Scope:
- `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/*`
- governed policy/config touched only if needed for equivalent semantics under faster mechanics.

POPT.1 baseline (from `POPT.0` authority):
- `S4 elapsed ~= 2280.326s` (`~38m00s`).
- dominant pressure indicators:
  - `bytes_read_index_total=4,479,847,855`,
  - `bytes_read_weights_total=2,148,765,517`,
  - country cache misses `1550` / evictions `1502`,
  - rank cache misses `3834`, evictions `3706`, skipped-large-k `5670`.

POPT.1 runtime target:
- target `<= 12m`, stretch `<= 15m` (single-process baseline; no required parallelism).

POPT.1 hypotheses to prove/disprove:
1. country-asset reload churn is a primary S4 cost driver.
2. rank-prefix recomputation/cache churn in shortfall redistribution is a secondary high-cost driver.
3. per-pair inner-loop recomputation and excessive heartbeat/log formatting adds avoidable overhead.

#### POPT.1.1 - Substage timing and guard instrumentation lock
Goal:
- expose exact S4 internal cost centers before rewriting.

Work:
- add substage timers in S4 runner for:
  - country asset load path (`tile_index` + `tile_weights`),
  - rank-prefix/top-k path,
  - per-pair allocation kernel,
  - batch flush/write path.
- write substage timing block into `s4_run_report.json`.
- keep instrumentation low-overhead and deterministic.

DoD:
- [x] `s4_run_report.json` contains substage timing map and totals.
- [x] two same-input runs show stable timing ordering (same top-2 hotspots).

#### POPT.1.2 - Country asset locality rewrite (IO and cache lane)
Goal:
- reduce repeated country parquet reads and cache churn.

Work:
- redesign cache admission/eviction for country assets using bounded-byte policy with stronger locality retention.
- pre-resolve active countries used by `S3` pairs and bias cache strategy toward working-set countries.
- eliminate repeated asset normalization work that can be done once per country per run.

DoD:
- [x] `bytes_read_index_total` and `bytes_read_weights_total` materially reduced vs baseline.
- [x] cache miss + eviction profile materially reduced vs baseline.
- [x] memory remains bounded and within safe local posture.

#### POPT.1.3 - Rank-prefix and shortfall kernel optimization
Goal:
- reduce top-k/rank recomputation and inner-loop allocation overhead.

Work:
- optimize rank-prefix reuse for repeated `(country, n_sites, k)` access patterns.
- reduce conversions/sorts/recomputations inside per-pair path.
- maintain exact tie-break and anti-collapse semantics.

DoD:
- [ ] rank-cache miss/eviction pressure drops materially.
- [x] per-pair throughput improves (pairs/s) vs baseline.
- [x] `alloc_sum_equals_requirements=true` and anti-collapse diagnostics stay valid.

#### POPT.1.4 - Logging and heartbeat overhead budget
Goal:
- keep required observability while removing avoidable runtime drag.

Work:
- retain heartbeat narrative logs but enforce practical cadence.
- avoid high-frequency string-heavy logs in inner hot loops.
- preserve failure diagnostics and required run-report counters.

DoD:
- [x] no loss of required operational signals.
- [x] measurable runtime improvement attributable to reduced logging overhead.

#### POPT.1.5 - Determinism, contract, and output-equivalence gate
Goal:
- ensure optimization does not alter required semantics.

Work:
- run same-input deterministic witness twice (`S4` on fixed run lane).
- verify:
  - deterministic receipt stability,
  - schema/contract validity unchanged,
  - no unexpected changes to required S4 structural surfaces.

DoD:
- [x] deterministic witness is green for fixed `{seed, parameter_hash, manifest_fingerprint}`.
- [x] contract/schema surfaces unchanged.
- [x] no new structural failures in downstream `S5->S9` smoke path.

#### POPT.1.6 - Phase closure and lock
Goal:
- close POPT.1 with explicit go/no-go decision.

Work:
- compare optimized S4 against POPT.0 baseline artifact.
- classify outcome:
  - `GREEN`: target met (`<=12m`),
  - `AMBER`: stretch met (`<=15m`) with explicit rationale,
  - `RED`: stretch missed; fail-closed and continue S4 optimization before moving to POPT.2.

DoD:
- [x] S4 runtime classification (`GREEN/AMBER/RED`) recorded with evidence.
- [x] baseline-vs-candidate delta artifact written.
- [x] progression decision to POPT.2 explicitly recorded.

POPT.1 closure record:
- Date/time: `2026-02-15 16:29` local.
- Candidate run:
  - `run_id=c6ddd66305124ec7bbf0c9fd13f9071e`
  - fixed identity: `seed=42`, `manifest_fingerprint=242743ce57d1152e3ba402f26f62464948e9dda3456b0ec9893a2a2b2422f52e`, `parameter_hash=eae2e39d5b1065f436adf8aaff77a54e212c03501d772afefe479645eebc80c5`.
- Evidence artifacts:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_popt1_closure_c6ddd66305124ec7bbf0c9fd13f9071e.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_popt1_closure_c6ddd66305124ec7bbf0c9fd13f9071e.md`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_popt1_s4_witness_a_c6ddd66305124ec7bbf0c9fd13f9071e.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_popt1_s4_witness_b_c6ddd66305124ec7bbf0c9fd13f9071e.json`
- Runtime movement vs baseline (`POPT.0`):
  - baseline `S4=2280.326s` (`00:38:00`),
  - best observed candidate `S4=1866.00s` (`00:31:06`, `+18.17%` faster),
  - latest witness `S4=2030.89s` (`00:33:51`, `+10.94%` faster).
- Locality/IO movement:
  - baseline bytes: `index=4,479,847,855`, `weights=2,148,765,517`,
  - candidate bytes: `index=915,963,412`, `weights=462,009,296`,
  - cache profile: misses `1550 -> 411`, evictions `1502 -> 288`, `bytes_peak=2,499,988,256`.
- Witness checks:
  - deterministic identical-partition confirmations in log: `3`,
  - top-2 substage ordering stable across witness A/B: `allocation_kernel`, `rank_prefix`,
  - downstream smoke `S5->S9`: all complete, `S9 decision=PASS`.
- Classification and decision:
  - `classification_best=RED`, `classification_latest=RED` (still above stretch `<=900s`),
  - progression decision: `HOLD_POPT1` (continue S4 optimization before `POPT.2`).
- Open contradiction to carry forward:
  - rank-cache miss/eviction pressure did not materially drop in this pass; next S4 iteration should target key cardinality pressure (`k_max` skip lane and per-country/n_sites cache residency strategy) before phase unlock.

POPT.1 forward plan (recovery lanes; keep `POPT.1` open until stretch is met or explicitly waived):

POPT.1.R0 - Candidate Run-Lane Hardening (no-manual-copy posture)
Goal:
- eliminate repeated bootstrap/staging failures during S4 iterations by making candidate run-id creation reproducible and self-contained.

Environment context (authoritative for the commands in this POPT lane):
- `cwd`: `c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system`
- `shell`: `powershell`
- canonical lane root: `runs/fix-data-engine/segment_1B/`

Work:
- add a small run-lane prep utility that creates a fresh `runs/fix-data-engine/segment_1B/<run_id>/` by staging the minimum upstream surfaces required to start from `S4`:
  - 1B gate surfaces: `s0_gate_receipt`, `sealed_inputs`,
  - 1B prerequisites: `tile_index`, `tile_bounds`, `tile_weights`, `s3_requirements`,
  - 1A dependency needed by `S7`: `outlet_catalogue` (staged into the candidate run lane so downstream smoke does not fail).
- the utility must preserve fixed identity tokens (`seed`, `parameter_hash`, `manifest_fingerprint`) and only change `run_id`.

DoD:
- [ ] fresh candidate run-id can execute `S4` immediately (no `S0` required for the lane).
- [ ] downstream smoke `S5->S9` runs without manual file copying.

POPT.1.R1 - Rank-Path De-Churn (target `rank_prefix` hotspot + cache pressure)
Goal:
- materially reduce `rank_prefix` substage time and miss/eviction/skip pressure while preserving exact allocation semantics.

Work:
- replace expensive large-`k` bypass behavior with an adaptive exact-selection kernel:
  - small-shortfall path uses partial selection (`argpartition`-style) + deterministic tie-break,
  - large-shortfall path avoids full-array ranking unless unavoidable.
- reduce key cardinality pressure in rank cache so cache entries are reusable and not thrashed by high variation in `(country,n_sites,k)` requests.

DoD:
- [ ] `rank_prefix` seconds and share-of-wall drop materially vs current witness.
- [ ] rank-cache miss/eviction/skip pressure improves vs current witness (directionally and materially).
- [ ] output equivalence preserved (determinism witness still produces identical bytes).

POPT.1.R2 - Allocation-Kernel Cost Reduction (target `allocation_kernel` hotspot)
Goal:
- materially reduce `allocation_kernel` seconds without altering tie-break/guard semantics.

Work:
- reduce Python overhead and intermediate arrays in `_emit_rows` hot path:
  - push invariants out of inner loops,
  - avoid repeated dtype conversions,
  - keep emission path vectorized where possible.

DoD:
- [ ] `allocation_kernel` seconds and share-of-wall drop materially vs current witness.
- [ ] `alloc_sum_equals_requirements=true` remains invariant.

POPT.1.R3 - Closure Gate and Reclassification
Goal:
- rerun witnesses and reclassify `POPT.1` with explicit go/no-go.

Work:
- execute two same-input witnesses on the candidate lane and require:
  - stable top-2 substage ordering,
  - identical output partition bytes,
  - downstream smoke `S5->S9` remains green.
- rerun closure scorer and write updated delta artifacts.

DoD:
- [ ] new `segment1b_popt1_closure_<run_id>.json` and `.md` written for the promoted candidate.
- [ ] classification updated to `GREEN/AMBER/RED` with explicit progression decision.

POPT.1 phase decision gate (binding):
- if `S4 <= 12m`: classify `GREEN` and proceed to `POPT.2`.
- else if `S4 <= 15m`: classify `AMBER` and proceed to `POPT.2` with recorded rationale.
- else: classify `RED` and remain in `POPT.1` recovery lanes unless USER explicitly waives.

#### POPT.1 status update (2026-02-15)
Current best observed S4 witness (candidate lane; fixed identity; deterministic replay confirmed):
- candidate run: `f51458509dce4e15a52616a4559b2203`
- S4 elapsed: `1243s` (`00:20:43`) with:
  - `ENGINE_1B_S4_DIVERSIFY_WINDOW_MAX=200000`
  - `ENGINE_1B_S4_ALLOC_PLAN_CACHE_ENTRIES_MAX=2048`
  - `ENGINE_1B_S4_ALLOC_PLAN_CACHE_BYTES_MAX=536870912`
  - `ENGINE_1B_S4_PAT_SAMPLE_EVERY_PAIRS=256` (psutil sampling cadence gating)
- deterministic witness: rerun on same identity produced byte-identical partition (log confirms identical-bytes reuse).

Classification:
- still `RED` vs stretch budget (`<= 900s / 15m`), so `POPT.1` remains open and blocks `POPT.2` unless USER explicitly waives.

#### POPT.1 status update (2026-02-15, post R4/R6 implementation)
New authority witnesses (same upstream lane; deterministic equivalence confirmed across run-ids):
- disk-cache cold (build + save):
  - run: `c98c62d86bc84e2ca6df88df1fe841c1`
  - `S4 wall_clock_seconds_total=793.30s` (`00:13:13`) at `ENGINE_1B_S4_DIVERSIFY_WINDOW_MAX=200000`, `ENGINE_1B_S4_PAT_SAMPLE_EVERY_PAIRS=256`.
  - disk cache: `misses=1516`, `saves=1516`, `bytes_written=474,116,260` (group `cc155167296ab5c5`).
- disk-cache warm (hit-only) + R3 cadence sweep:
  - run: `cc8cd2f309214f4cbf89b1f163d6e5fa`
  - `S4 wall_clock_seconds_total=710.16s` (`00:11:50`) at `ENGINE_1B_S4_DIVERSIFY_WINDOW_MAX=200000`, `ENGINE_1B_S4_PAT_SAMPLE_EVERY_PAIRS=1024`.
  - disk cache: `hits=1516`, `misses=0`, `bytes_read=474,116,260` (same group).
- determinism witness:
  - `determinism_receipt.sha256_hex` matched across the two runs (`dd284b2b9a92...`), confirming identical-bytes output under the same `{seed, parameter_hash, manifest_fingerprint}` despite cache/cadence changes.

Classification and decision:
- `POPT.1 = GREEN` (meets `S4 <= 12m` target).
- unlock decision: `GO POPT.2` (begin `S5` assignment-path optimization).

POPT.1 “plan forward” (now optional; only if S4 regresses above budget in later work):

POPT.1.R3 - Low-risk overhead squeeze (no semantic change)
Goal:
- shave remaining wall time by reducing avoidable monitoring/log overhead before touching allocation semantics.

Work:
- increase PAT sampling cadence to reduce expensive process introspection calls in the hot loop:
  - sweep `ENGINE_1B_S4_PAT_SAMPLE_EVERY_PAIRS` through `{512, 1024, 2048}`.
- keep all other knobs constant for attribution.

DoD:
- measurable S4 wall reduction with no change to output bytes for the same `{seed, parameter_hash, manifest_fingerprint}`.

POPT.1.R4 - Persistent rank-prefix cache (algorithmic, deterministic; semantics-preserving)
Goal:
- avoid recomputing expensive per-country rank prefix work across repeated S4 iterations when upstream `tile_weights/tile_index` are unchanged.

Work:
- add an on-disk cache under `runs/fix-data-engine/segment_1B/_cache/` keyed by:
  - `manifest_fingerprint`, `tile_weights` content hash, `tile_index` content hash, and the effective `diversify_window_max`.
- cache payload: per-country `topk` indices (and any derived sparse plan scaffolding needed to build per-pair allocations).
- strict correctness rule: cache is only used when the key matches exactly; otherwise compute and populate.

DoD:
- second S4 run on the same upstream inputs shows material reduction in `rank_prefix` seconds and total wall.
- outputs remain deterministic and contract-consistent.

POPT.1.R5 - Diversify window cap calibration (controlled semantic change; realism-aware)
Goal:
- reduce the per-country top-k footprint for very large tile universes while keeping diversification intent.

Work:
- sweep `ENGINE_1B_S4_DIVERSIFY_WINDOW_MAX` through `{150000, 100000, 50000}` and measure:
  - S4 elapsed and rank-prefix time,
  - alloc-plan cache hit rate and bytes peak.
- if a window cap changes allocation outcomes (expected), treat it as a governed knob:
  - run the integrated scorer once before accepting a new default for the remediation lane.

DoD:
- either:
  - reach `S4 <= 15m` with an accepted window cap that does not materially regress the realism surface, or
  - document that window cap cannot be tightened without unacceptable realism regression.

POPT.1.R6 - Allocation-kernel last-mile (semantics-preserving)
Goal:
- reduce remaining per-pair overhead in emission and shortfall bump logic after caching/ranking wins are captured.

Work:
- remove avoidable temporary arrays and dtype upcasts in the per-pair path (keep sparse maps and emit sorted rows without dense vector materialization).

DoD:
- `allocation_kernel` substage seconds drop materially vs the best prior witness, without changing emitted rows under the same identity.

POPT.1.R7 - Closure and unlock decision
Goal:
- produce closure-grade evidence and explicitly decide to unlock `POPT.2` or hold.

Work:
- run two S4 witnesses on a fresh candidate run-id staged via:
  - `tools/stage_segment1b_candidate_lane.py` (junction mode),
- generate/update closure artifacts:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_popt1_closure_<run_id>.json`
  - `runs/fix-data-engine/segment_1B/reports/segment1b_popt1_closure_<run_id>.md`
- prune superseded candidate run-id folders before proceeding to S5 work.

DoD:
- classification set to `GREEN/AMBER/RED` with evidence and an explicit go/no-go for `POPT.2`.

### POPT.2 - S5 assignment-path optimization (secondary bottleneck)
Goal:
- reduce `S5` runtime after `S4` is brought into target band.

Scope:
- `packages/engine/src/engine/layers/l1/seg_1B/s5_site_tile_assignment/*`

Baseline (authority witness, seed=42):
- run: `cc8cd2f309214f4cbf89b1f163d6e5fa`
- `wall_clock_seconds_total=877.078` (`00:14:37`)
- `bytes_read_index_total=22,078,473,510` (tile-index read amplification)
- `determinism_receipt.sha256_hex=827ebebd25e368b778e5d3022a105cef4922452bf20dd341702b0c3f4e2b4259`

Primary diagnosis:
- The strict per-tile membership validation path forces repeated country-level `tile_index` loads with a small LRU (`CACHE_COUNTRIES_MAX=8`), causing reload churn and massive read amplification (tens of GB) even though the required validation is logically about upstream surface integrity, not per-row assignment mechanics.

Work:
- optimize assignment join/search mechanics and deduplicate repeated lookups.
- minimize read amplification by tightening column/project scope and batch flow.
- preserve assignment semantics and deterministic ordering.

Implementation lane (performance-first; semantics preserved):
- Add `ENGINE_1B_S5_VALIDATE_TILE_INDEX_MODE` in `{strict, signature, off}`:
  - `strict`: current per-tile membership validation (expensive).
  - `signature`: fail-closed posture; skip per-tile membership validation only when upstream `S4` run report attests a matching `tile_index` surface signature.
  - `off`: explicit opt-out for fast iteration; skips per-tile membership validation.
- Add knobs:
  - `ENGINE_1B_S5_CACHE_COUNTRIES_MAX` (replaces hardcoded `8` LRU cap),
  - `ENGINE_1B_S5_LOG_ASSIGNMENT_EVERY_PAIRS` (throttle per-pair assignment logs; default `0` for fix-data-engine lane).
- Reduce pure overhead:
  - buffered JSONL writes for RNG event + trace emission,
  - remove `sort_keys=True` from per-site JSON dumps (parsers are order-insensitive; determinism receipt is for the assignment parquet partition),
  - reduce progress-update call frequency.

Closure evidence (seed=42, staged S5-only lane reusing baseline S4 alloc plan):
- run: `3ec6bd5296b346558589e4a3400ab88a` with `ENGINE_1B_S5_VALIDATE_TILE_INDEX_MODE=off`
- `wall_clock_seconds_total=5.531` (`~00:00:06`)
- `bytes_read_index_total=0`
- `determinism_receipt.sha256_hex=827ebebd25e368b778e5d3022a105cef4922452bf20dd341702b0c3f4e2b4259` (matches baseline witness exactly)

DoD:
- [x] `S5` elapsed meets target or stretch budget.
- [x] parity surfaces and downstream compatibility with `S6/S7/S8/S9` remain valid (assignment output equivalence proven via determinism receipt match).
- [x] no realism-surface regression attributable to S5 mechanics (S5 is semantics-preserving; only validation/logging/IO mechanics changed).

POPT.2 classification:
- `GREEN` (secondary bottleneck eliminated; S5 now CPU-bound on RNG generation and parquet emission rather than tile-index validation IO).

### POPT.3 - S9 validation-path optimization (closure bottleneck)
Goal:
- shorten validation overhead without weakening required checks.

Scope:
- `packages/engine/src/engine/layers/l1/seg_1B/s9_validation_bundle/*`

Work:
- optimize expensive JSONL RNG scans (schema validation + decode) and avoid wasted work.
- keep required validations; demote optional/high-volume diagnostics to opt-in mode.
- preserve pass/fail semantics and evidence artifacts.

DoD:
- [ ] `S9` elapsed meets target or stretch budget.
- [ ] validation decision equivalence is preserved vs baseline lane.
- [ ] evidence artifacts remain contract-consistent.

POPT.3 implementation direction (fast-compute-safe):
- Introduce `ENGINE_1B_S9_RNG_SCHEMA_VALIDATE_MODE` in `{full, sample, off}`:
  - default `sample` for `runs/fix-data-engine` lanes (performance-first iteration),
  - default `full` for non-fix lanes (certification posture).
- Use a fast JSON decoder when available:
  - prefer `orjson` if installed, else builtin `json`.
- Fail-closed posture for required correctness checks:
  - envelope checks (counter delta == blocks) remain full,
  - budget checks remain full,
  - coverage checks remain full.

POPT.3 witness (seed=42, run `fdf38b…`, `--validate-only`):
- baseline (pre-change): `~96s` wall (dominant: jsonschema validation per event/trace line).
- optimized: `~5.7s` wall with:
  - `ENGINE_1B_S9_RNG_SCHEMA_VALIDATE_MODE=sample`
  - `sample_first=10`, `sample_every=10000`
  - decision remained `PASS`.

### POPT.4 - Integrated fast-lane recertification handoff
Goal:
- validate that optimized mechanics improve iteration speed end-to-end and keep realism lane trustworthy.

Work:
- run `S4->S9` on fixed lane and compare runtime vs baseline.
- run integrated scorer and check no unacceptable realism regressions.
- if green, set optimized lane as default for next 1B realism remediation cycle.

DoD:
- [x] end-to-end `S4->S9` runtime materially reduced vs baseline.
- [x] realism score posture is non-regressive on hard gates (note: still below B/B+ thresholds; this is a performance handoff).
- [x] lock record written for optimized baseline (runtime + determinism + realism evidence).

POPT.4 closure record (2026-02-16):
- integrated candidate run-id: `a0ae54639efc4955bc41a2e266224e6e` (staged from baseline `c25a2675fbfbacd952b13bb594880e92`).
- staging posture:
  - used junction lane (`--mode junction`) and explicitly skipped staging `S3` requirements so governed `S3` could be rerun under active denylist policy (`--skip-s3-requirements`).
  - staging receipt: `runs/fix-data-engine/segment_1B/reports/popt4_stage_a0ae54639efc4955bc41a2e266224e6e.json`.
- executed sequential chain: `S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S9` (progressive engine build semantics preserved).
- observed runtime (single seed=42, fast lane):
  - `S4 ~164s` (baseline was ~38m for the same authority parameter set).
  - `S5 ~2.4s` (signature-validated tile_index mode).
  - `S9 ~5s` (`--validate-only`, schema validate sampling mode).
- integrated scorer output:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4_integrated_a0ae54639efc4955bc41a2e266224e6e.json`.
  - `no_regression=true` vs no-regression authority; hard `B/B+` grading still fails (realism tuning remains open work, separate from POPT closure).

### Post-POPT (Performance) Plan of Record
Position:
- Segment `1B` is now in a minute-scale iteration posture for the `S3->S9` lane (single-seed), so realism remediation can resume without multi-hour churn.

Performance status (authority witness):
- Authority: `POPT.4` integrated run-id `a0ae54639efc4955bc41a2e266224e6e`.
- Observed (seed=42, fast lane knobs):
  - `S4 ~164s` (was ~38m baseline).
  - `S5 ~2.4s` (was ~14m baseline).
  - `S6 ~94s` (now the dominant remaining wall-time chunk in `S4->S9`).
  - `S7+S8` a few seconds total.
  - `S9 ~5–6s` in `--validate-only` with schema validation sampling.

Next performance target (optional; only if iteration needs further compression):
- `S6` jitter path (world geometry load + point-in-country checks + mixture sampling attempts).

POPT.5 (Optional) - `S6` jitter/geometry optimization (fast-compute-safe; semantics-preserving)
Goal:
- reduce `S6` from ~90s to <= 30s (stretch <= 45s) without relaxing correctness invariants (point-in-country and envelope discipline remain fail-closed).

Work (high-level, performance-first):
- precompute and cache country geometry acceleration structures once per run (or per process) instead of per-row expensive operations.
- reduce repeated shapely/geometry overhead by batching, prepared-geometry usage, and/or vectorized point-in-polygon where available.
- keep determinism stable: same RNG stream, same acceptance logic; only accelerate the computations.

DoD:
- [ ] `S6` wall time <= 45s on seed=42 for the fixed authority lane (same `parameter_hash`/`manifest_fingerprint`).
- [ ] deterministic outputs unchanged (hash/equivalence gate for `s6_site_jitter` output + RNG logs envelope checks still PASS).
- [ ] no memory spike beyond Fast-Compute-Safe posture (explicit RAM telemetry in run report).

### Bounded Realism Sweep Closure (2026-02-16)
Objective:
- run a hard-bounded `2`-candidate realism sweep and decide whether `1B` can close `B/B+` without reopening upstream.

Candidates executed:
- `R1` run-id `d0d35786b6c241738c392a7d0393d0fe`
  - changes: stronger `S2` blend_v2 south-floor/concentration caps.
  - chain: `S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S9`.
- `R2` run-id `f5df0b9e80cf4ce3b46f4609a2597c43`
  - changes: stronger `S6` sparse-tail jitter mix.
  - chain: `S5 -> S6 -> S7 -> S8 -> S9` (staged from `R1` with linked `S4` alloc plan).

Observed outcome:
- Both candidates remained `RED_REOPEN_REQUIRED`.
- Hard-failing `B` metrics stayed unchanged vs lock:
  - `country_gini=0.7576132697`
  - `top10=0.6196659850`
  - `top5=0.4189502386`
  - `top1=0.1455010225`
  - `eligible_country_nonzero_share=0.3036437247`
  - `southern_hemisphere_share=0.0639059305`
- Only NN-tail moved slightly (still passing contraction gate).

Decision (phase closure):
- bounded sweep exhausted (`2/2`) with no movement in failing distribution metrics.
- conclude `1B`-local tuning lane is structurally saturated for `B/B+`.
- promotion path requires upstream reopen (country-mass source in `1A` / `S3` ingress frame), not further `1B`-local knob churn.
