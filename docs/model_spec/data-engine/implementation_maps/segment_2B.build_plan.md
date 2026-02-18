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
- [ ] baseline runtime table (`state_elapsed`, `total_elapsed`) is emitted.
- [ ] top bottlenecks are ranked with evidence.
- [ ] optimization budget targets are pinned for later POPT gates.

### POPT.1 - S3/S4 core compute-path optimization
Goal:
- reduce merchant-day-group hot-path cost in `S3` and `S4`.

Scope:
- improve data structures and join/materialization strategy in S3/S4 loops.
- eliminate redundant scans/recomputations while preserving output identity.

Definition of done:
- [ ] measured runtime reduction on S3/S4 versus POPT.0 baseline.
- [ ] deterministic replay check passes on same seed + same inputs.
- [ ] S3/S4 structural validators remain green.

### POPT.2 - S5 assignment-path optimization
Goal:
- reduce per-arrival routing cost and improve roster-processing throughput.

Scope:
- optimize arrival loop, pre-filtering/indexing, and lookup paths used by S5.
- keep assignment semantics unchanged.

Definition of done:
- [ ] S5 elapsed time materially reduced versus POPT.0.
- [ ] assignment parity checks remain non-regressed.
- [ ] run-report counters remain consistent with pre-optimization semantics.

### POPT.3 - I/O and logging budget optimization
Goal:
- lower I/O and log overhead without losing required audit evidence.

Scope:
- cap high-frequency logs to heartbeat/progress cadence.
- reduce unnecessary reads/writes and redundant serialization work.

Definition of done:
- [ ] log volume reduced with required evidence still present.
- [ ] I/O-heavy states show measured elapsed improvement.
- [ ] no missing mandatory audit fields in run reports.

### POPT.4 - Integrated fast-lane performance lock
Goal:
- validate combined optimization stack across full 2B state chain.

Scope:
- run one integrated candidate through required 2B chain.
- verify runtime target movement and zero determinism/contract regressions.

Definition of done:
- [ ] integrated runtime improvement is demonstrated vs POPT.0.
- [ ] deterministic replay witness passes for accepted candidate.
- [ ] structural gate surfaces (`S0/S2/S6/S7/S8`) remain non-regressed.

### POPT.5 - Optimization freeze handoff
Goal:
- freeze accepted optimization posture before entering remediation P0.

Scope:
- lock accepted run-id/policy/code references.
- prune superseded optimization run folders and retain authority artifacts.
- record freeze statement in plan + implementation notes.

Definition of done:
- [ ] POPT lock artifact is written and referenced by this plan.
- [ ] superseded run-id folders are pruned per retention rule.
- [ ] explicit GO decision recorded to enter remediation `P0`.

## 6) Remediation phase plan (data-first with DoDs)

### P0 - Baseline authority and harness lock
Goal:
- establish the baseline realism posture and lock deterministic iteration harness before tuning.

Scope:
- baseline metrics extraction for S1/S3/S4 and current roster posture.
- runtime baseline capture (state-level elapsed budget table).
- run-retention and prune flow activation under `runs/fix-data-engine/segment_2B/`.

Definition of done:
- [ ] baseline authority run-id and lineage tokens are pinned.
- [ ] baseline metric table for all hard-gate axes is emitted.
- [ ] runtime baseline table (state elapsed and total elapsed) is emitted.
- [ ] prune-before-run workflow is active and evidenced.

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
- [ ] `weight_source.mode` moved from uniform to policy-governed mixture path.
- [ ] S1 metrics hit at least B witness movement direction on selected seed(s):
  - residual activation, top1-top2 gap activation, concentration spread activation.
- [ ] S2 alias integrity and decode parity remain non-regressed.
- [ ] accepted P1 lock record is written (policy snapshot + run-id + metric deltas).

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

Definition of done:
- [ ] per-row sigma resolution replaces single global sigma path.
- [ ] provenance fields emitted (`sigma_source`, `sigma_value`, `weekly_amp`).
- [ ] S3 B gates pass on witness seeds without aggregate instability.
- [ ] P1 S1 gains remain non-regressed under P2 candidate.

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
- [ ] regularizer path is policy-governed and deterministic.
- [ ] S4 B gates pass on witness seeds:
  - dominance center/tail, multi-group share, entropy, mass conservation.
- [ ] no synthetic hard-truncation artifacts observed in distribution diagnostics.
- [ ] P1/P2 gains remain non-regressed.

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

### P5 - Freeze, handoff, and closure
Goal:
- freeze accepted 2B authority candidate and close remediation cycle with retained evidence.

Scope:
- lock accepted policy/config snapshots and authority run-id pointers.
- prune superseded run-id folders while preserving certification evidence.
- record closure decision and residual risks.

Definition of done:
- [ ] freeze status recorded (`FROZEN_CERTIFIED_BPLUS` or `FROZEN_CERTIFIED_B` or `FROZEN_BEST_EFFORT_BELOW_B`).
- [ ] retained evidence artifacts are complete and reproducible.
- [ ] implementation notes and logbook carry full decision trail for all phases.
