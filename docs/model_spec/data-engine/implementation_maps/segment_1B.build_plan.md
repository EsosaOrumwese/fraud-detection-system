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
- [ ] if `AMBER_NEAR_BPLUS`, `P4.3` executes bounded recovery with no B hard-gate regression.
- [ ] accepted integrated candidate has reproducibility witness (`P4.4`) with matching score posture.
- [ ] P4 lock record and pointer updates are written; superseded run-id folders are pruned and retained set is explicit.
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
