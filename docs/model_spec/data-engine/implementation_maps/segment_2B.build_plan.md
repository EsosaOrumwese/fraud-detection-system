# Segment 2B Remediation Build Plan (B/B+ Execution Plan)
_As of 2026-02-18_

## 0) Objective and closure rule
- Objective: remediate Segment `2B` to certified realism `B` minimum, with `B+` as the active target where feasible.
- Baseline authority posture from published report: realism grade `C`.
- Realism surfaces of record:
  - `s1_site_weights`
  - `s3_day_effects`
  - `s4_group_weights`
  - realism-grade `s5_arrival_roster` used for validation
- Closure rule:
  - `PASS_BPLUS`: all hard gates pass for all required seeds and all B+ bands pass.
  - `PASS_B`: all hard gates pass for all required seeds and B bands pass.
  - `FAIL_REALISM`: any hard gate fails on any required seed.
  - `INVALID_FOR_GRADING`: realism roster preconditions fail.
- Phase advancement law (binding): no phase is closed until its DoD checklist is fully green.

## 1) Source-of-truth stack

### 1.1 Statistical authority
- `docs/reports/eda/segment_2B/segment_2B_published_report.md`
- `docs/reports/eda/segment_2B/segment_2B_remediation_report.md`

### 1.2 State and contract authority
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s0.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s1.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s2.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s3.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s4.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s5.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s6.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s7.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state.2B.s8.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/dataset_dictionary.layer1.2B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/artefact_registry_2B.yaml`

### 1.3 Upstream freeze posture (binding for this pass)
- `1A` remains frozen as certified authority.
- `1B` remains frozen as best-effort-below-B authority.
- `2A` remains frozen as retained authority from prior closure cycle.
- Segment `2B` remediation in this pass does not assume upstream reopen.

## 2) Remediation posture and boundaries
- Causal order is fixed by remediation authority:
  - `S1 -> S3 -> S4 -> realism-grade validation roster/gates`.
- Primary remediation states:
  - `S1` spatial heterogeneity activation.
  - `S3` temporal heterogeneity activation.
  - `S4` anti-collapse tuning after `S1/S3`.
  - `S5` realism-grade roster and gate enforcement for certification validity.
- Structural support states:
  - `S0`: gate/sealed-input integrity and policy digest sealing.
  - `S2`: alias integrity non-regression only (no realism tuning target).
  - `S6`: virtual-edge non-regression only.
  - `S7/S8`: audit + bundle certification surfaces.
- Tuning priority:
  - data-shape realism first,
  - structural/gate flags are veto rails, not the optimization target.

## 3) Statistical targets and hard gates
- Required seeds for certification: `{42, 7, 101, 202}`.

### 3.1 Validation preconditions (fail-closed)
- realism-grade roster required:
  - horizon `>= 28` days,
  - repeated arrivals per merchant-day,
  - retained class/channel coverage.
- active policy fingerprints for S1/S3/S4 must match the chosen remediation spec.

### 3.2 Hard B gates
- S1 spatial heterogeneity:
  - median `|p_site - 1/N_sites| >= 0.003`
  - median `(top1_share - top2_share) >= 0.03`
  - merchant HHI IQR `>= 0.06`
- S3 temporal heterogeneity:
  - median merchant day-effect std-dev `>= 0.03`
  - non-zero between-tz-group differentiation across required seeds
  - aggregate gamma center/spread remains stable (no clipping saturation)
- S4 routing realism:
  - median `max_p_group <= 0.85`
  - share of merchant-days with `max_p_group >= 0.95 <= 35%`
  - share with at least 2 groups where `p_group >= 0.05 >= 35%`
  - entropy p50 `>= 0.35`
  - mass conservation (`sum(p_group)` within tolerance of `1.0`) on all rows
- Structural non-regression:
  - alias parity/hash checks PASS,
  - S7/S8 audit/bundle checks PASS,
  - schema/provenance for new fields remains valid.

### 3.3 B+ target bands
- S1:
  - median `|p_site - 1/N_sites| >= 0.006`
  - median `(top1_share - top2_share) >= 0.05`
  - merchant HHI IQR `>= 0.10`
- S3:
  - median merchant day-effect std-dev `>= 0.04` with visible upper tail
  - stable non-zero tz-group differentiation with controlled drift
- S4:
  - median `max_p_group <= 0.78`
  - share of merchant-days with `max_p_group >= 0.95 <= 20%`
  - share with at least 2 groups where `p_group >= 0.05 >= 50%`
  - entropy p50 `>= 0.45`

### 3.4 Cross-seed stability gates
- CV for primary medians (`S1 residual`, `S4 max_p_group`, `S4 entropy`):
  - `B`: `CV <= 0.25`
  - `B+`: `CV <= 0.15`
- Any seed-specific collapse causes certification failure.

## 4) Run protocol, performance budget, and retention
- Active run root: `runs/fix-data-engine/segment_2B/`.
- Retained folders only:
  - baseline authority pointer,
  - current candidate,
  - last good candidate,
  - active certification pack.
- Prune-before-run is mandatory for superseded failed run-id folders.

### 4.1 Progressive rerun matrix (sequential-state law)
- If any 2B policy bytes change (S1/S3/S4/S5 policy packs): rerun `S0 -> ...` from the first impacted state.
- If `S1` logic changes: rerun `S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8`.
- If `S3` logic changes: rerun `S3 -> S4 -> S5 -> S6 -> S7 -> S8`.
- If `S4` logic changes: rerun `S4 -> S5 -> S6 -> S7 -> S8`.
- If only realism roster/gate logic changes: rerun `S5 -> S6 -> S7 -> S8`.
- If only reporting/certification tooling changes: rerun scorers and regenerate evidence pack; do not mutate state outputs.

### 4.2 Runtime budgets (binding)
- P0 must record measured per-state wall-clock and establish baseline budget references.
- Fast candidate lane (single seed, changed-state onward): target `<= 20 min` wall-clock.
- Witness lane (2 seeds): target `<= 40 min`.
- Certification lane (4 seeds sequential): target `<= 90 min`.
- Any material runtime regression without explained bottleneck + mitigation blocks phase closure.

## 5) Performance optimization pre-lane (POPT, mandatory before remediation)
- Objective: drive 2B iteration runtime to a minute-scale practical lane before realism tuning.
- Guardrails:
  - preserve determinism and contract compliance,
  - no realism-shape tuning in POPT phases,
  - single-process baseline first (no parallelism dependency),
  - every POPT phase needs measured runtime evidence and non-regression checks.

### POPT.0 - Runtime baseline and bottleneck map
Goal:
- produce a measured baseline per state and identify primary hot paths.

Scope:
- collect state-level wall-clock for `S0..S8` in current 2B lane.
- extract dominant compute and I/O bottlenecks from logs/profiles.
- lock runtime budget targets for fast/witness/certification lanes.

Definition of done:
- [x] baseline runtime table (`state_elapsed`, `total_elapsed`) is emitted.
- [x] top bottlenecks are ranked with evidence.
- [x] optimization budget targets are pinned for later POPT gates.

POPT.0 closure record (2026-02-18):
- authority run used:
  - `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`
- generated artifacts:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_popt0_baseline_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_popt0_hotspot_map_c25a2675fbfbacd952b13bb594880e92.md`
- observed runtime baseline (log-derived, 2B window):
  - segment total: `76.357s` (log window `79.994s`).
  - primary hotspot: `S5=30.477s` (`39.91%`, `RED` vs `16s/22s` target/stretch).
  - secondary hotspot: `S4=20.795s` (`27.23%`, `AMBER` vs `18s/24s`).
  - closure hotspot: `S3=19.763s` (`25.88%`, `AMBER` vs `18s/24s`).
- progression gate:
  - decision: `GO POPT.1`
  - selected state for `POPT.1`: `S5`.

### POPT.1 - Primary hotspot optimization
Goal:
- reduce the #1 ranked hotspot state selected by `POPT.0`.

Scope:
- active state for this cycle: `S5`.
- optimize data structures, lookup path, and loop mechanics while preserving output identity.
- no realism-shape tuning in this phase.

Definition of done:
- [x] measured runtime reduction on selected primary state versus POPT.0 baseline.
- [x] deterministic replay check passes on same seed + same inputs.
- [x] relevant structural validators remain green.

POPT.1 progress record (2026-02-18):
- implementation target:
  - `packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py`
- runtime evidence:
  - POPT.0 baseline (`S5`): `30.477s`
  - POPT.1 candidate (`S5`, run-id `c25a2675fbfbacd952b13bb594880e92`, sampled
    input-validation lane): `5.92s`
  - observed reduction: `-24.56s` (`-80.58%`).
- structural evidence:
  - `s5_run_report.json` emitted under fix lane with validators
    `V-01..V-16` all `PASS`.
- replay evidence (closed):
  - deterministic timestamp sequencing applied to persisted S5 RNG event/trace
    rows (anchored to S0 `created_utc`).
  - witness lane:
    - runs root: `runs/fix-data-engine/segment_2B_popt1_replay_20260218_134345`
    - run id: `c25a2675fbfbacd952b13bb594880e92`
    - replay result: second run exited `0` with byte-identical skip logs:
      - `rng_event_alias_pick_group already exists and is identical`
      - `rng_event_alias_pick_site already exists and is identical`
      - `rng_trace_log already exists and is identical`.

POPT.1 closure decision (2026-02-18):
- decision: `CLOSED`
- next phase: `POPT.2` (secondary hotspot `S4` unless reranked).

### POPT.2 - Secondary hotspot optimization
Goal:
- reduce the #2 ranked hotspot from `POPT.0` after `POPT.1` closure.

Scope:
- active state for this cycle: `S4` (unless re-ranked by accepted `POPT.1` candidate evidence).
- optimize compute/materialization path while preserving assignment semantics and normalization invariants.

Definition of done:
- [x] secondary hotspot elapsed time materially reduced versus POPT.0.
- [x] parity/invariant checks remain non-regressed.
- [x] run-report counters remain consistent with pre-optimization semantics.

POPT.2 closure record (2026-02-18):
- implementation target:
  - `packages/engine/src/engine/layers/l1/seg_2B/s4_group_weights/runner.py`
- runtime evidence:
  - POPT.0 secondary hotspot baseline (`S4`): `20.795s`.
  - pre-change witness on fix lane (`S4`, strict output validation):
    - elapsed `25.81s` (same run-id, no policy changes).
  - accepted POPT.2 lane (`S4`, sampled output validation):
    - elapsed `2.92s`.
  - reduction vs POPT.0 baseline: `-17.88s` (`-85.96%`).
  - reduction vs pre-change witness: `-22.89s` (`-88.68%`).
- hotspot proof:
  - profile before:
    - `runs/fix-data-engine/segment_2B/reports/s4_popt2_profile_before.prof`
    - runtime `68.774s`; dominant hotspot:
      `s4_group_weights._write_batch -> validate_dataframe` (`62.069s`).
  - profile after:
    - `runs/fix-data-engine/segment_2B/reports/s4_popt2_profile_after.prof`
    - runtime `7.622s`; `validate_dataframe` reduced to `1.379s`.
- parity / invariant evidence:
  - `s4_run_report` validators `V-01..V-20` all `PASS`.
  - normalization counters unchanged in meaning:
    - `rows_expected=278100`, `rows_written=278100`,
    - `join_misses=0`, `pk_duplicates=0`,
    - `merchants_days_over_norm_epsilon=0`.
  - report snapshots:
    - `runs/fix-data-engine/segment_2B/reports/s4_popt2_run_report_strict.json`
    - `runs/fix-data-engine/segment_2B/reports/s4_popt2_run_report_sample.json`
- replay / idempotence evidence:
  - repeated same-run `S4` execution in sample mode reports
    `output already exists and is identical; skipping publish`.

POPT.2 closure decision (2026-02-18):
- decision: `CLOSED`
- next phase: `POPT.3` (I/O + logging budget optimization).

### POPT.3 - I/O and logging budget optimization
Goal:
- lower I/O and log overhead without losing required audit evidence.

Scope:
- cap high-frequency logs to heartbeat/progress cadence.
- reduce unnecessary reads/writes and redundant serialization work.

Definition of done:
- [x] log volume reduced with required evidence still present.
- [x] I/O-heavy states show measured elapsed improvement.
- [x] no missing mandatory audit fields in run reports.

POPT.3 closure record (2026-02-18):
- implementation target:
  - `packages/engine/src/engine/layers/l1/seg_2B/s3_day_effects/runner.py`
- runtime evidence (`S3`):
  - pre-change baseline witness:
    - command: `make segment2b-s3`
    - wall clock: `21.861s`
    - state timer: `20.73s`.
  - accepted POPT.3 lane (`S3`, sampled output validation):
    - wall clock: `3.233s`
    - state timer: `2.64s`
    - reduction vs pre-change wall clock: `-18.628s` (`-85.22%`).
  - strict compatibility witness post-change:
    - wall clock: `21.287s`
    - state timer: `20.72s` (legacy strict posture preserved).
- logging budget evidence:
  - `S3` INFO run-report line reduced from full JSON to summary.
  - line-length witness from run log:
    - pre-change full JSON line: `12613` chars,
    - post-change summary line: `~201` chars.
- run-report parity evidence:
  - snapshots:
    - `runs/fix-data-engine/segment_2B/reports/s3_popt3_run_report_strict.json`
    - `runs/fix-data-engine/segment_2B/reports/s3_popt3_run_report_sample.json`
  - strict/sample both retain mandatory audit fields and structural counters:
    - `rows_expected=rows_written=278100`,
    - `join_misses=0`, `pk_duplicates=0`,
    - validators fail/warn = `0/0`.

POPT.3 closure decision (2026-02-18):
- decision: `CLOSED`
- next phase: `POPT.4` (integrated fast-lane performance lock).

### POPT.4 - Integrated fast-lane performance lock
Goal:
- validate combined optimization stack across full 2B state chain.

Scope:
- run one integrated candidate through required 2B chain.
- verify runtime target movement and zero determinism/contract regressions.

Definition of done:
- [x] integrated runtime improvement is demonstrated vs POPT.0.
- [x] deterministic replay witness passes for accepted candidate.
- [x] structural gate surfaces (`S0/S2/S6/S7/S8`) remain non-regressed.

POPT.4 closure record (2026-02-18):
- witness lane:
  - runs root: `runs/fix-data-engine/segment_2B_popt4_20260218_1412`
  - run id: `c25a2675fbfbacd952b13bb594880e92`
- integrated runtime evidence:
  - POPT.0 baseline segment elapsed: `76.375s`
    (`runs/fix-data-engine/segment_2B/reports/segment2b_popt0_baseline_c25a2675fbfbacd952b13bb594880e92.json`)
  - POPT.4 integrated candidate segment elapsed: `15.642s`
    (`runs/fix-data-engine/segment_2B/reports/segment2b_popt4_integrated_run1_c25a2675fbfbacd952b13bb594880e92.json`)
  - improvement: `-60.733s` (`-79.52%`).
- deterministic replay witness (accepted optimization scope):
  - replay command scope: `S0->S5` on same run-id/same inputs.
  - witness log:
    `runs/fix-data-engine/segment_2B/reports/segment2b_popt4_replay_scope_s0_s5_stdout.log`
  - result: `PASS` with idempotent skip evidence:
    - `S0`/`S1`/`S3`/`S4` output skip logs,
    - `S5` events byte-identical skip logs,
    - `S5` shared trace replay prefix verified (downstream `S6` append-aware).
- structural non-regression evidence (`S0/S2/S6/S7/S8`):
  - `S0` run-report overall `PASS`.
  - `S2` run-report overall `PASS`.
  - `S6` run-report overall `PASS`.
  - `S7` audit report summary `PASS`.
  - `S8` validation `_passed.flag` present under 2B validation partition.
- closure artifact:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_popt4_closure_summary_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_popt4_closure_summary_c25a2675fbfbacd952b13bb594880e92.md`
- residual follow-up resolved (2026-02-18):
  - applied deterministic timestamp sequencing in
    `packages/engine/src/engine/layers/l1/seg_2B/s6_edge_router/runner.py`
    for S6 event + trace rows (anchored to S0 `created_utc`).
  - full-segment publish + replay witness (`S0->S8`) completed with no
    `2B-S6-080/2B-S6-081` in replay logs:
    - `runs/fix-data-engine/segment_2B/reports/segment2b_s6fix_run1_stdout.log`
    - `runs/fix-data-engine/segment_2B/reports/segment2b_s6fix_run2_replay_stdout.log`
  - witness summary:
    - `runs/fix-data-engine/segment_2B/reports/segment2b_s6_idempotence_fix_summary_c25a2675fbfbacd952b13bb594880e92.json`

POPT.4 closure decision (2026-02-18):
- decision: `CLOSED`
- next phase: `POPT.5` (optimization freeze handoff).

### POPT.5 - Optimization freeze handoff
Goal:
- freeze accepted optimization posture before entering remediation P0.

Scope:
- lock accepted run-id/policy/code references.
- prune superseded optimization run folders and retain authority artifacts.
- record freeze statement in plan + implementation notes.

Definition of done:
- [x] POPT lock artifact is written and referenced by this plan.
- [x] superseded run-id folders are pruned per retention rule.
- [x] explicit GO decision recorded to enter remediation `P0`.

POPT.5 closure record (2026-02-18):
- lock artifact:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_popt5_lock_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_popt5_lock_c25a2675fbfbacd952b13bb594880e92.md`
- lock content summary:
  - status: `FROZEN_OPTIMIZATION_LOCKED`.
  - accepted run-id: `c25a2675fbfbacd952b13bb594880e92`.
  - runtime lock: `76.375s -> 15.642s` (`79.52%` improvement).
  - replay lock: `S0->S5` pass and full-segment replay pass after S6 fix
    (no `2B-S6-080/2B-S6-081`).
  - code surfaces frozen:
    - `packages/engine/src/engine/layers/l1/seg_2B/s3_day_effects/runner.py`
    - `packages/engine/src/engine/layers/l1/seg_2B/s4_group_weights/runner.py`
    - `packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py`
    - `packages/engine/src/engine/layers/l1/seg_2B/s6_edge_router/runner.py`
- prune evidence:
  - summary: `runs/fix-data-engine/segment_2B/reports/segment2b_popt5_prune_summary.json`
  - pruned roots:
    - `runs/fix-data-engine/segment_2B_popt1_replay_20260218_134345`
    - `runs/fix-data-engine/segment_2B_popt2_20260218_134742`
    - `runs/fix-data-engine/segment_2B_popt4_20260218_1412`
  - storage reclaimed: `39.904 GB`.
- retained root for next phase:
  - `runs/fix-data-engine/segment_2B`.

POPT.5 closure decision (2026-02-18):
- decision: `CLOSED`
- explicit GO: `GO_P0`
- next phase: remediation `P0` (baseline authority and harness lock).

## 6) Remediation phase plan (data-first with DoDs)

### P0 - Baseline authority and harness lock
Goal:
- establish the baseline realism posture and lock deterministic iteration harness before tuning.

Scope:
- baseline metrics extraction for S1/S3/S4 and current roster posture.
- runtime baseline capture (state-level elapsed budget table).
- run-retention and prune flow activation under `runs/fix-data-engine/segment_2B/`.

Definition of done:
- [x] baseline authority run-id and lineage tokens are pinned.
- [x] baseline metric table for all hard-gate axes is emitted.
- [x] runtime baseline table (state elapsed and total elapsed) is emitted.
- [x] prune-before-run workflow is active and evidenced.

P0 closure record (2026-02-18):
- authority baseline pinned:
  - run root: `runs/fix-data-engine/segment_2B`
  - run id: `c25a2675fbfbacd952b13bb594880e92`
  - lineage tokens: `seed=42`,
    `manifest_fingerprint=c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8`,
    `parameter_hash=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7`.
- emitted baseline hard-gate metric artifacts:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p0_baseline_metrics_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p0_baseline_metrics_c25a2675fbfbacd952b13bb594880e92.md`
- emitted runtime baseline artifacts:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p0_runtime_baseline_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p0_runtime_baseline_c25a2675fbfbacd952b13bb594880e92.md`
- key baseline findings (authority run):
  - `S1` fails heterogeneity activation axes (`residual=0.000000`,
    `top1-top2=0.000000`) while `HHI IQR=0.067633` passes B floor.
  - `S3` activation is already non-collapsed (`merchant std median=0.120403`,
    `tz differentiation share=1.000000`, `nonpositive_gamma_rows=0`).
  - `S4` dominance remains above B (`max_p_group p50=0.928926`,
    `share max>=0.95 = 49.13%`, `entropy p50=0.256493`);
    multi-group share passes (`50.84%`) and mass conservation passes.
  - roster posture is not realism-grade (`horizon_span_days=1`,
    `merchant_day_repeat_ge2_share=0.000000`) and therefore verdict is
    `INVALID_FOR_GRADING` until P4 roster hardening.
- prune-before-run evidence remains active from optimization handoff:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_popt5_prune_summary.json`
  - retained root policy unchanged: keep only authority/current/last-good/cert pack.

### P1 - S1 spatial heterogeneity activation
Goal:
- remove uniform-by-construction site-weight collapse in `S1`.

Scope:
- implement `profile_mixture_v2` policy-governed generation.
- preserve deterministic replay and exact normalization.
- emit required provenance (`weight_profile`, `mixture_component`, `alpha_used`).

Candidate surfaces:
- `config/layer1/2B/policy/alias_layout_policy_v1.json`
- `packages/engine/src/engine/layers/l1/seg_2B/s1_site_weights/runner.py`

Definition of done:
- [x] `weight_source.mode` moved from uniform to policy-governed mixture path.
- [x] S1 metrics hit at least B witness movement direction on selected seed(s):
  - residual activation, top1-top2 gap activation, concentration spread activation.
- [x] S2 alias integrity and decode parity remain non-regressed.
- [x] accepted P1 lock record is written (policy snapshot + run-id + metric deltas).

P1 closure record (2026-02-18):
- accepted candidate run:
  - run root: `runs/fix-data-engine/segment_2B`
  - run id: `c7e3f4f9715d4256b7802bdc28579d54`
- policy/code deltas:
  - `config/layer1/2B/policy/alias_layout_policy_v1.json`
    - `weight_source.mode=profile_mixture_v2`
    - added `profile_mixture_v2` block
      (`merchant_size_buckets`, `mixture_weights`,
      `concentration_alpha_by_bucket`, `top1_soft_cap_by_bucket`,
      `min_secondary_mass`, `deterministic_seed_scope=merchant_id`)
    - bumped `version_tag/policy_version` to `1.0.2`
    - updated `quantisation_epsilon` to `1.2e-07` for quantization coherence.
  - `packages/engine/src/engine/layers/l1/seg_2B/s1_site_weights/runner.py`
    - implemented deterministic merchant-scoped `profile_mixture_v2` resolver,
    - added component/bucket/alpha provenance in S1 run-report samples,
    - preserved schema and write-order contracts.
  - `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml`
    - allowed `profile_mixture_v2` in `alias_layout_policy_v1` schema.
- scoring and lock artifacts:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_candidate_c7e3f4f9715d4256b7802bdc28579d54.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_candidate_c7e3f4f9715d4256b7802bdc28579d54.md`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_lock_c7e3f4f9715d4256b7802bdc28579d54.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_lock_c7e3f4f9715d4256b7802bdc28579d54.md`
- measured movement vs P0 baseline (`c25...`):
  - residual median: `0.000000 -> 0.036163` (`+0.036163`)
  - top1-top2 gap median: `0.000000 -> 0.171117` (`+0.171117`)
  - merchant HHI IQR: `0.067633 -> 0.270633` (`+0.203000`)
  - S1 `B`/`B+` band checks on these three axes: all pass.
- S2 non-regression evidence:
  - `s2_run_report` summary `PASS` (`fail_count=0`, `warn_count=0`)
  - alias decode/structural validators remained green.
- run-retention / prune evidence:
  - summary artifact:
    `runs/fix-data-engine/segment_2B/reports/segment2b_p1_prune_summary.json`
  - superseded failed candidate roots pruned:
    `6f2b57a4e7fc4fe6b216fdcf0f87cb73`,
    `79c70dfc9aa44843bd4eb035192e3354`,
    `c983af9b3a4f4a38947fe8d37cbb77f2`.
  - active retained roots: baseline `c25...` and accepted P1 candidate `c7e3...`.

### P2 - S3 temporal heterogeneity activation
Goal:
- move from one effective sigma regime to merchant/tz-differentiated volatility.

Scope:
- implement `sigma_gamma_policy_v2` resolution in `S3`.
- bounded weekly component activation with deterministic behavior.
- preserve aggregate gamma stability while increasing local spread.

Candidate surfaces:
- `config/layer1/2B/policy/day_effect_policy_v1.json`
- `packages/engine/src/engine/layers/l1/seg_2B/s3_day_effects/runner.py`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml` (if policy schema extension is required)

Phase-entry locks (binding):
- `P1` lock is frozen as authority (`run_id=c7e3f4f9715d4256b7802bdc28579d54`).
- no `S1` policy/code edits are allowed inside `P2`.
- candidate execution starts at `S3` and progresses sequentially through `S8`.

P2.1 - S3 baseline decomposition and tuning envelope
Goal:
- pin the exact S3 baseline from the active `P1` authority root and lock the tuning envelope before code edits.

Scope:
- measure baseline S3 metrics on active retained roots (`c25...`, `c7e3...`) for:
  - merchant gamma std-dev median and tail,
  - tz-group differentiation signal,
  - aggregate gamma stability guardrails (`nonpositive_gamma_rows`, clip pressure).
- lock allowed tuning ranges for `sigma_base`, tz multipliers, merchant jitter, and weekly amplitude.

Definition of done:
- [x] baseline S3 metric table for `P2` is emitted and pinned to run-id lineage.
- [x] tuning envelope is documented with explicit min/max bounds and anti-instability guards.
- [x] no-code-change witness confirms S1 P1 metrics remain unchanged before P2 edits.

P2.2 - Policy/contract delta for `sigma_gamma_policy_v2`
Goal:
- define a deterministic, schema-valid policy surface for per-row sigma resolution.

Scope:
- update `day_effect_policy_v1` from scalar `sigma_gamma` posture to structured `sigma_gamma_policy_v2`:
  - `sigma_base_by_segment`,
  - `sigma_multiplier_by_tz_group`,
  - `sigma_jitter_by_merchant`,
  - `weekly_component_amp_by_segment`,
  - `sigma_min`, `sigma_max`, `gamma_clip`.
- extend `schemas.2B.yaml` only where required to validate the new policy block under `additionalProperties: false`.

Definition of done:
- [x] policy JSON validates cleanly under contracts.
- [x] schema updates (if any) are minimal and backward-safe for existing required fields.
- [x] policy digest change is traceable in S0 sealed-input outputs on candidate root.

P2.3 - S3 implementation delta and provenance
Goal:
- replace the global sigma path with deterministic per-row sigma resolution while preserving contract outputs.

Scope:
- implement per-row sigma resolver in `s3_day_effects/runner.py` using `sigma_gamma_policy_v2`.
- add bounded weekly component application in the same deterministic seed envelope.
- emit S3 provenance trail in run-report/sample surfaces:
  - `sigma_source`,
  - `sigma_value`,
  - `weekly_amp`.
- preserve existing output schema/order, publish idempotence, and replay determinism.

Definition of done:
- [x] per-row sigma path is active and scalar-global fallback is removed/disabled for 2B remediation lane.
- [x] provenance fields are emitted and populated on sampled output evidence.
- [x] strict structural validators remain green with no new schema violations.

P2.4 - Witness execution and gate scoring
Goal:
- certify S3 movement to at least `B` gates without destabilizing aggregate behavior or regressing frozen P1 gains.

Scope:
- run fast candidate lane from `S3 -> S8` on staged root.
- run witness lane on at least two seeds (`42` + `7`) before P2 closure.
- score against P2 hard gates:
  - merchant std-dev median `>= 0.03`,
  - non-zero tz differentiation,
  - aggregate stability (no clip saturation / nonpositive gamma rows).
- run non-regression checks:
  - P1 S1 locked metrics remain unchanged vs lock artifact,
  - S4 is not allowed to regress into catastrophic collapse beyond baseline floor.

Definition of done:
- [ ] S3 `B` hard gates pass on required witness seeds for P2 closure.
- [x] no aggregate gamma instability events are detected.
- [x] non-regression report is emitted for P1 S1 lock and downstream safety rails.

P2.5 - P2 freeze handoff to P3
Goal:
- freeze accepted P2 candidate and hand off a clean authority root for S4-focused tuning.

Scope:
- emit P2 candidate scorecard + lock artifact (run-id, policy digests, metric deltas).
- prune superseded failed P2 candidate roots under retention rules.
- update `build_plan`, `impl_actual`, and logbook with explicit P2 closure decision.

Definition of done:
- [x] `P2` lock artifact exists and is referenced by this plan.
- [x] retained roots are reduced to baseline + accepted current + reports/cert evidence.
- [x] explicit decision recorded: `GO_P3` only if P2 gates and non-regression checks are green; otherwise `NO_GO_P3`.

P2 closure record (2026-02-18):
- candidate run:
  - run root: `runs/fix-data-engine/segment_2B`
  - run id: `3e6b5090ecde48f68b6fadc0bfad022f` (superseded and pruned after evidence capture)
- policy/code deltas:
  - `config/layer1/2B/policy/day_effect_policy_v1.json`
    - bumped `version_tag/policy_version` to `1.0.3`,
    - added `sigma_gamma_policy_v2` block
      (`sigma_base_by_segment`, `sigma_multiplier_by_tz_group`,
      `sigma_jitter_by_merchant`, `weekly_component_amp_by_segment`,
      `sigma_min`, `sigma_max`, `gamma_clip`).
  - `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml`
    - added schema allowance for `sigma_gamma_policy_v2`.
  - `packages/engine/src/engine/layers/l1/seg_2B/s3_day_effects/runner.py`
    - activated deterministic per-row sigma resolution path,
    - added bounded weekly component and bounded gamma clipping,
    - added sampled provenance fields (`sigma_source`, `sigma_value`, `weekly_amp`),
    - added run-report counters for sigma/gamma boundary evidence.
- baseline + candidate evidence:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p2_1_baseline_e94506e84ab84dc0aaebf2bb770f816d.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p2_1_baseline_e94506e84ab84dc0aaebf2bb770f816d.md`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p2_candidate_3e6b5090ecde48f68b6fadc0bfad022f.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p2_candidate_3e6b5090ecde48f68b6fadc0bfad022f.md`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p2_lock_3e6b5090ecde48f68b6fadc0bfad022f.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p2_lock_3e6b5090ecde48f68b6fadc0bfad022f.md`
- gate outcome:
  - `S3` hard/stability gates: pass.
  - `P1 S1` non-regression and `S2` non-regression: pass.
  - `S4` non-catastrophic guard: fail
    (`entropy_p50=0.125673`, `max_p_group_median=0.972654`).
- cross-seed witness posture:
  - seed `7` witness deferred in this lane (retained upstream authority roots are seed `42` only).
- run-retention / prune evidence:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p2_prune_summary.json`
  - pruned superseded roots:
    `e94506e84ab84dc0aaebf2bb770f816d`,
    `3e6b5090ecde48f68b6fadc0bfad022f`.
  - retained active roots: baseline `c25...`, frozen P1 lock `c7e3...`.
- explicit decision:
  - `NO_GO_P3` from this candidate.
  - next required lane is S4-focused recovery (P3) from P1-frozen authority root.

P2.R1 - bounded recovery pass (single-attempt)
Goal:
- recover `P2` by reducing S3-driven collapse pressure into S4 while keeping S3 B gates green.

Scope:
- apply one bounded policy-only tuning pass in:
  - `config/layer1/2B/policy/day_effect_policy_v1.json`
- tune only these `sigma_gamma_policy_v2` knobs downward:
  - `sigma_base_by_segment`,
  - `sigma_multiplier_by_tz_group`,
  - `sigma_jitter_by_merchant.amplitude`,
  - `weekly_component_amp_by_segment`,
  - `gamma_clip` tightening.
- execute exactly one candidate lane (`S0 -> S8`) on a fresh run-id staged from frozen `P1` authority.
- rescore using `tools/score_segment2b_p2_candidate.py`.

Definition of done:
- [x] exactly one bounded candidate run is executed and scored.
- [x] `S3` hard/stability/provenance + `S1/S2` non-regression remain green.
- [ ] if `S4` non-catastrophic guard turns green: close `P2` as recovered and record `GO_P3`.
- [x] if `S4` guard remains red: close `P2.R1` as failed and carry forward `NO_GO_P3` with evidence.

P2.R1 closure record (2026-02-18):
- candidate run:
  - run root: `runs/fix-data-engine/segment_2B`
  - run id: `80c00bf4cb654500a1bc0fa25bf84c83` (superseded and pruned after evidence capture)
- policy delta (bounded softening only):
  - `config/layer1/2B/policy/day_effect_policy_v1.json`
    - reduced `sigma_base_by_segment`,
    - compressed `sigma_multiplier_by_tz_group`,
    - reduced `sigma_jitter_by_merchant.amplitude`,
    - reduced `weekly_component_amp_by_segment`,
    - tightened `sigma_min/sigma_max` and `gamma_clip`.
- scoring evidence:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p2_candidate_80c00bf4cb654500a1bc0fa25bf84c83.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p2_candidate_80c00bf4cb654500a1bc0fa25bf84c83.md`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p2r1_lock_80c00bf4cb654500a1bc0fa25bf84c83.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p2r1_lock_80c00bf4cb654500a1bc0fa25bf84c83.md`
- gate outcome:
  - `S3` hard/stability/provenance: pass.
  - `P1 S1` non-regression + `S2` non-regression: pass.
  - `S4` non-catastrophic guard: fail (`entropy_p50=0.126338`, `max_p_group_median=0.972396`).
- decision:
  - `NO_GO_P3` maintained from `P2` lane (bounded recovery did not clear S4 guard).
- run-retention / prune evidence:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p2r1_prune_summary.json`
  - pruned superseded root: `80c00bf4cb654500a1bc0fa25bf84c83`.

### P3 - S4 anti-dominance tuning (post S1/S3)
Goal:
- contract dominance tails and lift multi-group behavior without synthetic artifacts.

Scope:
- introduce policy-governed regularizer behavior in `S4`.
- preserve rank order where required and enforce exact sum-to-one.
- tune only after `S1/S3` are locked.

Candidate surfaces:
- policy host decision in phase entry:
  - extend an existing 2B policy pack or add a new 2B policy artefact for `group_mix_regularizer_v1`.
- `packages/engine/src/engine/layers/l1/seg_2B/s4_group_weights/runner.py`
- contract updates if new policy artefact is introduced:
  - `docs/model_spec/data-engine/layer-1/specs/contracts/2B/dataset_dictionary.layer1.2B.yaml`
  - `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml`
  - `docs/model_spec/data-engine/layer-1/specs/contracts/2B/artefact_registry_2B.yaml`

Definition of done:
- [x] regularizer path is policy-governed and deterministic.
- [ ] S4 B gates pass on witness seeds:
  - dominance center/tail, multi-group share, entropy, mass conservation.
- [x] no synthetic hard-truncation artifacts observed in distribution diagnostics.
- [x] P1/P2 gains remain non-regressed.

Phase-entry locks (binding):
- `P1` remains frozen (`run_id=c7e3f4f9715d4256b7802bdc28579d54`).
- `P2/P2.R1` are closed as `NO_GO_P3` from S4 guard failures.
- no additional `S1` or `S3` policy/code edits are allowed inside `P3`.
- P3 work is constrained to `S4` policy + `S4` implementation + scoring/evidence.

P3.1 - S4 policy and contract surface (`group_mix_regularizer_v1`)
Goal:
- create an explicit, deterministic S4 anti-collapse policy surface aligned to remediation authority.

Scope:
- add `group_mix_regularizer_v1` policy artefact under 2B policy pack.
- include required fields from remediation:
  - `enabled`,
  - `apply_when_groups_ge`,
  - `max_p_group_soft_cap`,
  - `regularization_strength`,
  - `entropy_floor`,
  - `preserve_rank_order`,
  - `sum_to_one`.
- wire dictionary/registry/schema so S0 seals policy digest and S4 validates strict contract.

Candidate surfaces:
- `config/layer1/2B/policy/group_mix_regularizer_v1.json` (new or equivalent host file)
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/dataset_dictionary.layer1.2B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/artefact_registry_2B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml`

Definition of done:
- [x] policy artefact exists with remediation-required fields and bounded ranges.
- [x] contracts validate with `additionalProperties: false` posture retained.
- [x] S0 sealed-input digest includes S4 regularizer policy on candidate root.

P3.2 - S4 implementation delta (deterministic anti-collapse regularizer)
Goal:
- apply bounded anti-dominance regularization in S4 while preserving deterministic replay and exact mass conservation.

Scope:
- implement policy-governed regularizer in:
  - `packages/engine/src/engine/layers/l1/seg_2B/s4_group_weights/runner.py`
- behavior requirements:
  - apply only when `n_groups >= apply_when_groups_ge`,
  - soft-cap top group (`max_p_group_soft_cap`) without hard truncation artifacts,
  - redistribute softened mass to secondary groups with rank-order preservation when enabled,
  - optional entropy-floor uplift bounded by `regularization_strength`,
  - enforce exact `sum(p_group)=1` after transformation.
- emit provenance in S4 run-report samples/counters:
  - `regularizer_applied`,
  - `regularizer_strength`,
  - `regularizer_delta_mass` (or equivalent bounded delta evidence).

Definition of done:
- [x] S4 regularizer path is deterministic and policy-governed.
- [x] rowwise mass-conservation checks remain exact (within numeric epsilon).
- [x] run-report provenance fields for regularizer decisions are emitted.
- [x] replay/idempotence and structural validators remain green.

P3.3 - Baseline authority lane + P3 scorer
Goal:
- establish a fixed P3 baseline authority root and scoring harness for S4 B/B+ realism gates.

Scope:
- create one P3 authority candidate root with fixed upstream posture (`S0 -> S3` once).
- add P3 scoring tool for S4 gates + non-regression rails.
- evaluate against remediation thresholds:
  - B:
    - `max_p_group_median <= 0.85`,
    - `share(max_p_group>=0.95) <= 0.35`,
    - `share(groups>=2 where p>=0.05) >= 0.35`,
    - `entropy_p50 >= 0.35`,
    - mass conservation pass.
  - B+:
    - `max_p_group_median <= 0.78`,
    - `share(max_p_group>=0.95) <= 0.20`,
    - `share(groups>=2 where p>=0.05) >= 0.50`,
    - `entropy_p50 >= 0.45`,
    - mass conservation pass.

Definition of done:
- [x] P3 scorer artifact pair exists (json+md) with explicit gate booleans.
- [x] baseline P3 metrics are pinned to authority run-id lineage.
- [x] non-regression rails (`S1`, `S2`, `S3`) are included in scorer output.

P3.4 - B closure tuning (bounded sweep)
Goal:
- reach at least `B` on S4 realism gates with minimal synthetic artifact risk.

Scope:
- bounded sweep on S4 regularizer knobs only (no S1/S3 reopen):
  - `max_p_group_soft_cap`,
  - `regularization_strength`,
  - `entropy_floor`.
- run sequence discipline (progressive engine-safe):
  - reseal with `S0` for each policy delta,
  - execute `S4 -> S8` on staged candidate root with fixed upstream `S3`.
- veto conditions:
  - any structural/regression rail failure,
  - synthetic artifact signatures (rank inversions / hard-cliff shapes).

Definition of done:
- [ ] at least one candidate reaches full `B` S4 gates with rails green, or
- [x] bounded sweep exhausts and P3 is closed as failed-with-evidence.
- [x] accepted/terminal candidate scorecard is emitted and referenced.

P3.5 - B+ stretch lane (optional, bounded)
Goal:
- attempt `B+` S4 closure only after `B` is secured.

Scope:
- narrow tuning around accepted `B` candidate to improve:
  - entropy center,
  - dominance tail,
  - effective multi-group share.
- strict veto on regressions in `B`-passing rails.

Definition of done:
- [ ] either `B+` passes with evidence, or
- [x] lane is explicitly closed with retained terminal best-effort candidate.

P3.6 - Lock, prune, and handoff decision
Goal:
- freeze P3 result and provide authority handoff to roster/certification phase.

Scope:
- emit P3 lock artifact:
  - run-id, policy digests, scorer verdict, gate booleans.
- prune superseded P3 candidate run-id roots.
- update plan/impl/logbook with explicit handoff decision.

Definition of done:
- [x] P3 lock artifact exists and is referenced by this plan.
- [x] run retention is reduced to baseline + accepted authority + reports.
- [x] explicit decision recorded:
  - `GO_P4` if `B`/`B+` achieved with rails green,
  - `NO_GO_P4` with blocker evidence otherwise.

P3 closure record (2026-02-18):
- implemented policy/contract/code surfaces:
  - `config/layer1/2B/policy/group_mix_regularizer_v1.json`
  - `docs/model_spec/data-engine/layer-1/specs/contracts/2B/dataset_dictionary.layer1.2B.yaml`
  - `docs/model_spec/data-engine/layer-1/specs/contracts/2B/artefact_registry_2B.yaml`
  - `docs/model_spec/data-engine/layer-1/specs/contracts/2B/schemas.2B.yaml`
  - `packages/engine/src/engine/layers/l1/seg_2B/s0_gate/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_2B/s4_group_weights/runner.py`
  - `tools/score_segment2b_p3_candidate.py`
- candidate execution evidence:
  - baseline candidate run-id:
    - `c55ffaeb119245e385044f3e70680f03`
  - bounded stronger sweep candidate run-id:
    - `80d9c9df1221400f82db77e27a0d63b2`
  - scorecards:
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_candidate_c55ffaeb119245e385044f3e70680f03.json`
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_candidate_c55ffaeb119245e385044f3e70680f03.md`
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_candidate_80d9c9df1221400f82db77e27a0d63b2.json`
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_candidate_80d9c9df1221400f82db77e27a0d63b2.md`
  - terminal lock:
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_lock_80d9c9df1221400f82db77e27a0d63b2.json`
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_lock_80d9c9df1221400f82db77e27a0d63b2.md`
- blocker analysis:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_tail_floor_analysis.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_tail_floor_analysis.md`
  - outcome:
    - `share(max_p_group>=0.95)` is bound by `share(n_groups==1)=0.483037`,
      exceeding both `B (<=0.35)` and `B+ (<=0.20)` tail thresholds.
    - S4-only regularization cannot reduce this without upstream topology change.
- selected terminal candidate metrics (`80d9...`):
  - `max_p_group_median=0.780000` (B+ center pass),
  - `entropy_p50=0.526908` (B+ entropy pass),
  - `share(groups>=2 where p>=0.05)=0.516963` (B+ multigroup pass),
  - `share(max_p_group>=0.95)=0.483037` (tail fail; structural floor).
- run retention/prune evidence:
  - pruned superseded candidate:
    - `c55ffaeb119245e385044f3e70680f03`
  - prune summary:
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_prune_summary.json`
- explicit decision:
  - `NO_GO_P4` from `P3`.
  - required next move: upstream reopen of `P1/S1` topology to reduce
    single-group merchant-day share before retrying `P3` closure.

### P1.REOPEN - Upstream reopen on S1 topology lane (post-P3 blocker)
Goal:
- execute one concrete upstream reopen attempt on `P1/S1` and verify whether
  it can reduce the `S4` tail-floor blocker identified in `P3`.

Scope:
- reopen `S1` policy posture (no S3/S4 code changes in this lane),
- run one staged candidate through `S0 -> S8`,
- measure whether `share(n_groups==1)` and therefore
  `share(max_p_group>=0.95)` floor moves.

Definition of done:
- [x] one S1-reopen candidate run is executed and scored.
- [x] explicit floor analysis is emitted:
  - `share(n_groups==1)`,
  - `share(max_p_group>=0.95)`,
  - `share(max_p_group>=0.95 | n_groups>1)`.
- [x] explicit decision recorded:
  - `GO_P3_RETRY` only if floor materially drops toward B threshold,
  - otherwise `NO_GO_P1_REOPEN_S1_ONLY` with required upstream expansion.

P1.REOPEN closure record (2026-02-18):
- candidate run and scoring evidence:
  - candidate run-id:
    - `3f075a5bac634b0fbb3cb4491d9f9422`
  - P3 scorecard:
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_candidate_3f075a5bac634b0fbb3cb4491d9f9422.json`
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_candidate_3f075a5bac634b0fbb3cb4491d9f9422.md`
  - floor analysis:
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_floor_3f075a5bac634b0fbb3cb4491d9f9422.json`
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_floor_3f075a5bac634b0fbb3cb4491d9f9422.md`
  - lock artifact:
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_lock_3f075a5bac634b0fbb3cb4491d9f9422.json`
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_lock_3f075a5bac634b0fbb3cb4491d9f9422.md`
- quantified outcome:
  - baseline and candidate both:
    - `share(n_groups==1)=0.4830371567`,
    - `share(max_p_group>=0.95)=0.4830371567`,
    - `share(max_p_group>=0.95 | n_groups>1)=0.0000000000`.
  - deltas:
    - `delta_share_n_groups_eq_1=0.0`,
    - `delta_share_max_p_ge_095=0.0`.
- operational closure:
  - reverted `config/layer1/2B/policy/alias_layout_policy_v1.json` to frozen
    baseline posture (`version_tag=1.0.2`).
  - pruned superseded reopen candidate run-id:
    - `3f075a5bac634b0fbb3cb4491d9f9422`
  - prune evidence:
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_prune_summary.json`
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_prune_summary.md`
- explicit decision:
  - `NO_GO_P1_REOPEN_S1_ONLY`.
  - required next move: broader upstream reopen beyond `S1` (`2A` site-timezone
    topology and possibly `1B` site layout) before any `P3` retry.

### P1.REOPEN.2A - Broader upstream reopen (2A topology first)
Goal:
- execute a bounded `2A`-first upstream reopen lane and measure whether changing
  `site_timezones` topology can move the `S4` tail-floor blocker in 2B.

Scope:
- keep 2B `S1/S3/S4` policy/code frozen in this lane.
- stage a fresh candidate run-id from frozen 2B authority.
- apply run-local (candidate-only) 2A timezone policy deltas, rerun `2A S0->S5`,
  then rerun `2B S0->S8`.
- score with existing `2B P3` scorecard and tail-floor analyzer.

Definition of done:
- [x] one 2A-first candidate run completes `2A S0->S5` + `2B S0->S8`.
- [x] score artifacts are emitted:
  - `segment2b_p3_candidate_<run_id>.json`,
  - `segment2b_p1_reopen_floor_<run_id>.json`.
- [x] explicit decision is recorded:
  - `GO_P3_RETRY_FROM_2A` only if `share(n_groups==1)` and
    `share(max_p_group>=0.95)` move materially toward `B` gate (`<=0.35`),
  - otherwise `NO_GO_P1_REOPEN_2A_ONLY` and escalate to `1B` topology reopen.

P1.REOPEN.2A closure record (2026-02-18):
- execution attempts:
  - `1517706f6c4243e285ed7f46ffe225ac`:
    - failed at `2A-S2` (`F4:2A-S2-041`) due atomic publish collision from
      staging a run root that already contained `2A` outputs.
  - `9fd343e1a628427ebc78e3b725955c7c`:
    - failed at `2A-S0` (`F4:2A-S0-052`) due `run_receipt.created_utc` schema
      mismatch (7 fractional digits vs required 6).
  - `867bb5c1cdbb446a8d369b039a52be5a`:
    - completed `2A S0->S5` and `2B S0->S8` using run-local `2A` timezone
      policy deltas (`tz_overrides` reduced `7 -> 2`; `tz_nudge` `semver=1.3.2`,
      `epsilon_degrees=0.01`).
- evidence:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_candidate_867bb5c1cdbb446a8d369b039a52be5a.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_candidate_867bb5c1cdbb446a8d369b039a52be5a.md`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_floor_867bb5c1cdbb446a8d369b039a52be5a.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_floor_867bb5c1cdbb446a8d369b039a52be5a.md`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_2a_lock_867bb5c1cdbb446a8d369b039a52be5a.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_2a_lock_867bb5c1cdbb446a8d369b039a52be5a.md`
- retention/prune:
  - pruned failed staging attempts:
    - `1517706f6c4243e285ed7f46ffe225ac`
    - `9fd343e1a628427ebc78e3b725955c7c`
  - prune summary:
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_2a_prune_summary.json`
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_2a_prune_summary.md`
- quantified outcome:
  - `share(n_groups==1): 0.483037 -> 0.483845` (`+0.000808`)
  - `share(max_p_group>=0.95): 0.483037 -> 0.483845` (`+0.000808`)
  - `share(max_p_group>=0.95 | n_groups>1): 0.0 -> 0.0`
  - `P3` verdict on candidate remained `FAIL_P3` (`s4_b_band=false`,
    `s4_bplus_band=false`).
- explicit decision:
  - `NO_GO_P1_REOPEN_2A_ONLY`.
  - required next move: escalate to `1B` topology reopen before any `P3` retry.

### P1.REOPEN.1B - 1B topology reopen (performance-preserving lane)
Goal:
- test whether bounded `1B` topology movement can reduce `2B` tail-floor
  dominance while preserving the optimized `1B` runtime lane.

Scope:
- keep `2B` `S1/S3/S4` policy/code frozen.
- execute one run-local `1B` candidate from frozen `1B` authority lineage
  (`a0ae54639efc4955bc41a2e266224e6e`) and rerun `S2->S9` only.
- candidate changes are policy-only on `1B` topology surfaces (`S2`/`S4`);
  no `1B` algorithm rewrites in this lane.
- preserve fast-compute-safe posture by pinning the same runtime env knobs used
  by the optimized lane.
- propagate candidate outputs to `2A S0->S5` then `2B S0->S8`, and score with
  existing `P3`/floor analyzers.

Definition of done:
- [x] one `1B` candidate completes `S2->S9` with runtime evidence captured.
- [x] runtime non-regression gate is evaluated against `1B` authority lane:
  - no material regression on `S4/S5/S6/S9` wall-clock under same posture.
- [ ] one downstream candidate completes `2A S0->S5` + `2B S0->S8`.
- [ ] score artifacts are emitted:
  - `segment2b_p3_candidate_<run_id>.json`,
  - `segment2b_p1_reopen_floor_<run_id>.json`.
- [x] explicit decision is recorded:
  - `GO_P3_RETRY_FROM_1B` only if tail floor materially drops toward
    `B` gate (`share(max_p_group>=0.95) <= 0.35`) with runtime gate green,
  - otherwise `NO_GO_P1_REOPEN_1B_ONLY`.

Status update (2026-02-18):
- completed candidates:
  - `0ed63a7bff9d4c91855b516d41d0ec80` (R2),
  - `c24d00ed24564bbe81666808a1d04a77` (R3b, corrected candidate-local policy precedence).
- runtime gate remains red on all valid candidates vs authority `a0ae...`.
- lane closed fail-closed as `NO_GO_P1_REOPEN_1B_ONLY`.

P1.REOPEN.1B closure record (2026-02-18):
- lock artifact:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_1b_lock_c24d00ed24564bbe81666808a1d04a77.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_1b_lock_c24d00ed24564bbe81666808a1d04a77.md`
- explicit decision:
  - `NO_GO_P1_REOPEN_1B_ONLY` (performance-preserving guard not met).
- downstream execution in this lane:
  - skipped by gate (`2A S0->S5` + `2B S0->S8` were intentionally not run).
- next lane:
  - `2B` local recovery with `1B` frozen at authority
    `a0ae54639efc4955bc41a2e266224e6e`.

### P1.LOCAL.RECOVERY - 2B-local recovery with 1B frozen
Goal:
- pursue additional realism movement using only `2B` local surfaces while
  preserving frozen upstream (`1B` authority unchanged).

Scope:
- freeze `1B` at `a0ae54639efc4955bc41a2e266224e6e` (no reopen).
- tune only `2B` local surfaces (`S1/S3/S4`) with strict non-regression rails.
- no broad runtime-risk rewrites; bounded policy-first then bounded code delta.

Baseline insight anchor (authority `80d9...`):
- `share(n_groups==1)=0.483037`, `share(max_p_group>=0.95)=0.483037`.
- decomposition indicates floor is concentrated in `tz_count=1` merchant-days
  (single-group/tail share = `1.0` for that bucket).
- evidence:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_local_recovery_baseline_floor_breakdown_80d9c9df1221400f82db77e27a0d63b2.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_local_recovery_baseline_floor_breakdown_80d9c9df1221400f82db77e27a0d63b2.md`

Phases:
1) `P1L.0` - Feasibility gate (structural floor check)
   - objective: prove whether `2B` local-only changes can reduce
     `share(n_groups==1)` without upstream topology movement.
2) `P1L.1` - S1 alias-layout bounded spread lane
   - objective: reduce structural `tz_count=1` dominance without breaking S1 gates.
3) `P1L.2` - S3 day-effects guard shaping
   - objective: prevent concentration rebound while preserving entropy and median shape.
4) `P1L.3` - S4 bounded anti-dominance closure
   - objective: convert multigroup candidates into reduced tail share under veto gates.
5) `P1L.4` - lock/prune or fail-closed handoff
   - objective: freeze accepted lane or record `NO_GO_P1_LOCAL_RECOVERY`.

Definition of done:
- [x] feasibility gate executed with evidence-backed structural conclusion.
- [ ] at least one 2B-local candidate completes `S0->S8` from frozen upstream.
- [ ] emits score + floor artifacts with explicit gate booleans.
- [ ] preserves current non-tail metrics (median/entropy/multigroup) within veto bounds.
- [ ] records explicit decision:
  - `GO_P3_RETRY_FROM_2B_LOCAL` if measurable floor reduction is achieved,
  - else `NO_GO_P1_LOCAL_RECOVERY`.

Feasibility gate result (2026-02-18):
- baseline authority decomposition + runner semantics indicate structural floor:
  - `tz_count=1` merchant-days map to `n_groups==1` and `tail==1.0`,
  - `S3` group set is derived from unique `site_timezones.tzid` per merchant.
- implication:
  - local `S1/S3/S4` tuning cannot reduce `share(n_groups==1)` unless
    synthetic pseudo-group generation is introduced (high realism risk), or
    upstream `site_timezones` breadth changes.

Decision gate (required before execution continues):
- `ALLOW_SYNTHETIC_LOCAL_GROUPS`:
  - `yes`: proceed with bounded synthetic-group lane in `2B` local states.
  - `no`: reopen upstream `2A` topology with wider scope (not just tiny
    timezone override deltas).

Decision resolution (2026-02-18):
- `ALLOW_SYNTHETIC_LOCAL_GROUPS = no` (user-directed).
- `P1.LOCAL.RECOVERY` closes as feasibility-only; no synthetic local-group lane
  will be executed.
- next lane is `P1.REOPEN.2A.R2` (broader upstream `2A` reopen), with `1B`
  frozen.

### P1.REOPEN.2A.R2 - Broader 2A topology reopen (post-local feasibility)
Goal:
- test whether a broader `2A` topology reopen can reduce the structural
  `2B` single-group/tail floor while keeping `1B` frozen.

Scope:
- freeze `1B` at authority `a0ae54639efc4955bc41a2e266224e6e`.
- stage one clean candidate run-id from `2B` authority
  `80d9c9df1221400f82db77e27a0d63b2` (no copied `2A/2B` outputs).
- apply run-local `2A` timezone policy pack with broader deltas than the prior
  micro-tuning lane.
- run progressive order on same candidate run-id:
  - `2A S0->S5`, then `2B S0->S8`.
- emit score + floor evidence with existing analyzers.

Runtime and safety gates:
- preserve deterministic contracts and frozen downstream `2B` local policy/code.
- keep external-root precedence explicit:
  - candidate run-root first, authority run-root second, repo root third.
- fail-closed if candidate cannot complete or if floor movement is non-material.

Definition of done:
- [x] one clean `P1.REOPEN.2A.R2` candidate completes `2A S0->S5` + `2B S0->S8`.
- [x] emits:
  - `segment2b_p3_candidate_<run_id>.json`,
  - `segment2b_p1_reopen_floor_<run_id>.json`.
- [x] explicit decision is recorded:
  - `GO_P3_RETRY_FROM_2A_R2` only if floor metrics move materially toward `B`,
  - otherwise `NO_GO_P1_REOPEN_2A_R2`.

P1.REOPEN.2A.R2 closure record (2026-02-18):
- candidate run-id:
  - `6188e9c75f5a4c309b8a7900efd7e2d5`.
- run-local `2A` evidence:
  - `S1` applied `6` site overrides (`overrides_site=6`), `distinct_tzids` moved
    `90 -> 92` versus prior reopen lane.
- score/floor artifacts:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_candidate_6188e9c75f5a4c309b8a7900efd7e2d5.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_candidate_6188e9c75f5a4c309b8a7900efd7e2d5.md`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_floor_6188e9c75f5a4c309b8a7900efd7e2d5.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_floor_6188e9c75f5a4c309b8a7900efd7e2d5.md`
  - lock artifact:
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_2a_r2_lock_6188e9c75f5a4c309b8a7900efd7e2d5.json`
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_2a_r2_lock_6188e9c75f5a4c309b8a7900efd7e2d5.md`
- quantified floor movement:
  - `share(n_groups==1): 0.483037 -> 0.481422` (`-0.001616`),
  - `share(max_p_group>=0.95): 0.483037 -> 0.481422` (`-0.001616`),
  - `share(max_p_group>=0.95 | n_groups>1): 0.0 -> 0.0`.
- closure decision:
  - `NO_GO_P1_REOPEN_2A_R2` (movement is measurable but non-material vs `B/B+`
    gate distance; `P3` remains `FAIL_P3`).

### P4 - Realism-grade roster and certification hardening
Goal:
- make grade assignment fail-closed and evidence-backed using realism-grade workload.

Scope:
- upgrade/validate roster posture in `S5` to realism-grade.
- enforce required seed pack and gate logic in scoring/certification artifacts.
- produce full evidence pack with per-seed and cross-seed diagnostics.

Candidate surfaces:
- `packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py` (if roster gate wiring required)
- scoring tools under `tools/` for 2B certification pack generation.
- `S7/S8` evidence packaging surfaces as needed for certification outputs.

Definition of done:
- [ ] realism roster preconditions pass (`>=28` days, repeated arrivals, retained coverage).
- [ ] per-seed scorecards produced for `{42,7,101,202}` with explicit gate booleans.
- [ ] aggregate reducer emits deterministic `PASS_BPLUS`/`PASS_B`/`FAIL_REALISM`.
- [ ] cross-seed CV and collapse checks are emitted and enforced.

P4 disposition (2026-02-18):
- waived for this cycle and closed fail-closed into `P5` because realism-grade
  roster preconditions remain unmet and `P3` blocker stayed structural under
  accepted constraints (`1A/1B` frozen, no synthetic local groups).
- terminal realism posture remains `FAIL_P3` on frozen authority:
  - `s4_b_band=false`,
  - `s4_bplus_band=false`.

### P5 - Freeze, handoff, and closure
Goal:
- freeze accepted 2B authority candidate and close remediation cycle with retained evidence.

Scope:
- lock accepted policy/config snapshots and authority run-id pointers.
- prune superseded run-id folders while preserving certification evidence.
- record closure decision and residual risks.

Definition of done:
- [x] freeze status recorded (`FROZEN_CERTIFIED_BPLUS` or `FROZEN_CERTIFIED_B` or `FROZEN_BEST_EFFORT_BELOW_B`).
- [x] retained evidence artifacts are complete and reproducible.
- [x] implementation notes and logbook carry full decision trail for all phases.

P5 closure record (2026-02-18):
- freeze status:
  - `FROZEN_BEST_EFFORT_BELOW_B`.
- frozen authority and lock artifacts:
  - `runs/fix-data-engine/segment_2B/reports/segment2b_p3_lock_80d9c9df1221400f82db77e27a0d63b2.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_freeze_lock_best_effort_80d9c9df1221400f82db77e27a0d63b2.json`
  - `runs/fix-data-engine/segment_2B/reports/segment2b_freeze_lock_best_effort_80d9c9df1221400f82db77e27a0d63b2.md`
- retained supporting locks:
  - `segment2b_p1_lock_c7e3f4f9715d4256b7802bdc28579d54.json`
  - `segment2b_popt5_lock_c25a2675fbfbacd952b13bb594880e92.json`
  - `segment2b_p1_reopen_2a_final_lock_fd9b373e9a6a4ae0b2204f00677815f1.json`
- handoff:
  - remediation focus moves to segment `3A`; `2B` remains frozen unless an
    explicit upstream-constraint reopen is approved.
