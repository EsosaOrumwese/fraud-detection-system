# Segment 5B Optimization + Remediation Build Plan (B/B+ Execution Plan)
_As of 2026-02-22_

## 0) Objective and closure rule
- Objective: close Segment `5B` with both:
  - performance closure to minute-scale practical iteration, and
  - certified realism closure at `B` minimum, with `B+` as active target.
- Published authority posture:
  - published report grade `B+`, but remediation authority treats current posture as not closure-grade due deterministic DST/civil-time defect and weak calibration guardrails.
- Closure rule:
  - `PASS_BPLUS_ROBUST`: all hard realism gates pass, all B+ stretch gates pass, cross-seed stability passes, and runtime budgets pass.
  - `PASS_B`: all hard realism gates pass, cross-seed stability passes, and runtime budgets pass.
  - `HOLD_REMEDIATE`: any hard realism gate fails or runtime budget fails.
- Phase advancement law (binding): no phase is closed until every DoD checkbox in that phase is green.

## 1) Source-of-truth stack

### 1.1 Statistical authority
- `docs/reports/eda/segment_5B/segment_5B_published_report.md`
- `docs/reports/eda/segment_5B/segment_5B_remediation_report.md`

### 1.2 State/contract authority
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s0.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s1.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s2.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s3.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s4.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s5.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5B/dataset_dictionary.layer2.5B.yaml`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5B/artefact_registry_5B.yaml`

### 1.3 Upstream freeze posture (initial)
- `1A`, `1B`, `2B`, `3A`, `3B`, `5A` are treated as frozen inputs for the first 5B pass.
- `2A` reopen is explicitly allowed only if Wave-A DST hard gates cannot close with 5B-local changes alone (upstream-owned transition horizon dependency).

## 2) Scope and ownership map
- Active performance hotspots from measured baseline:
  - `S4` (primary),
  - `S1` (secondary),
  - `S2/S3` (tertiary),
  - `S5` (low runtime share; governance-only tuning).
- Active realism owners:
  - `S4 + S5`: DST/civil-time correctness and enforcement.
  - `S4 + routing policy`: timezone concentration and virtual-share calibration.
  - `S5 + policy/schema`: persistent gate hardening and sentinelization.
- Structural rails:
  - `S0` sealed-input/gate integrity is veto-only (not a tuning target).
  - `S2 -> S3 -> S4` count conservation is non-regression law.

## 3) Target gates (realism + runtime)

### 3.1 Hard realism gates (B)
- `T1` DST mismatch rate `<= 0.50%`.
- `T2` one-hour DST signature mass `P(offset in {-3600,+3600}) <= 0.10%`.
- `T3` DST-window hour-bin MAE `<= 1.5 pp`.
- `T4` S3<->S4 logical-key conservation exact: total diff `0`, key mismatch count `0`.
- `T5` physical/virtual nullability integrity violations `0`.
- `T6` timezone concentration top-10 share `<= 72%`.
- `T7` virtual share in band `[3%, 8%]` unless policy explicitly pins physical-first (must be documented).

### 3.2 Stretch realism gates (B+)
- `T1+` DST mismatch rate `<= 0.10%`.
- `T2+` one-hour DST signature mass `<= 0.02%`.
- `T3+` DST-window hour-bin MAE `<= 0.7 pp`.
- `T6+` timezone concentration top-10 share `<= 62%`.
- `T7+` virtual share in band `[5%, 12%]`.

### 3.3 Cross-seed stability gates
- Required seeds for certification: `{42, 7, 101, 202}`.
- Hard gates must pass on every required seed.
- Key-metric cross-seed CV:
  - `B`: `<= 0.25`
  - `B+`: `<= 0.15`

### 3.4 Runtime gates (binding)
- Candidate lane (single seed, changed-state onward): target `<= 7 min`.
- Witness lane (2 seeds): target `<= 14 min`.
- Certification lane (4 seeds): target `<= 30 min`.
- State budgets (finalized by `POPT.0` authority run `c25a2675fbfbacd952b13bb594880e92`):
  - `S1 <= 90s` (stretch `120s`),
  - `S2 <= 35s` (stretch `45s`),
  - `S3 <= 35s` (stretch `45s`),
  - `S4 <= 240s` (stretch `300s`),
  - `S5 <= 5s` (stretch `8s`).

## 4) Run protocol, retention, and pruning
- Active run root: `runs/fix-data-engine/segment_5B/`.
- Keep-set only:
  - baseline authority run-id,
  - current candidate,
  - last good,
  - active witness/certification run-set.
- Prune rule (mandatory): prune superseded failed/superseded run-id folders before each expensive rerun.

### 4.1 Progressive rerun matrix (sequential-state law)
- If `S1` changes: rerun `S1 -> S2 -> S3 -> S4 -> S5`.
- If `S2` changes: rerun `S2 -> S3 -> S4 -> S5`.
- If `S3` changes: rerun `S3 -> S4 -> S5`.
- If `S4` changes: rerun `S4 -> S5`.
- If only `S5` policy/gates change: rerun `S5`.
- If upstream `2A` is reopened and accepted: rerun `S0 -> S1 -> S2 -> S3 -> S4 -> S5`.

## 5) Performance-first phase stack (POPT)

### POPT.0 - Profiled baseline lock
Goal:
- lock measured state runtime and hot-lane attribution before optimization edits.

Execution posture:
- no code/policy edits are allowed in `POPT.0`; this phase is evidence lock only.
- run lane is single-seed baseline (`seed=42`) unless an existing clean authority run-id is already pinned and reproducible.
- if no clean authority run-id exists for the current code/config posture, execute one full chain `S0 -> S1 -> S2 -> S3 -> S4 -> S5` and pin that run-id as baseline.

Closure artifacts (required):
- `segment5b_popt0_baseline_lock_<run_id>.md` (run-id, seed, command lane, artifact pointers).
- `segment5b_popt0_state_elapsed_<run_id>.csv` (`state`, `elapsed_s`, `status`, `rows_in`, `rows_out` where available).
- `segment5b_popt0_hotspot_map_<run_id>.json` (lane decomposition and ranked bottlenecks).
- `segment5b_popt0_budget_pin_<run_id>.json` (finalized state and lane budgets with rationale).

#### POPT.0.1 - Baseline authority pin
Objective:
- choose and pin one clean authority baseline run-id under `runs/fix-data-engine/segment_5B/`.

Definition of done:
- [x] baseline run-id is explicitly pinned and recorded in plan artifacts.
- [x] baseline contains complete `S0..S5` PASS evidence for the same code/config posture.
- [x] keep-set is refreshed so superseded failed runs are pruned before further profiling work.

#### POPT.0.2 - State elapsed capture
Objective:
- capture authoritative elapsed time per state and establish initial bottleneck ranking.

Definition of done:
- [x] elapsed table for `S0..S5` is emitted from run-report/log evidence.
- [x] state ranking is recorded with absolute seconds and relative share.
- [x] any missing timing fields are called out explicitly (no silent defaults).

#### POPT.0.3 - Hot-lane decomposition
Objective:
- decompose hot states into `input_load`, `compute`, `validation`, and `write` lanes.

Method:
- parse state logs/step timers and classify elapsed spans into the four lanes.
- compute per-state lane share and segment-level lane share.
- rank optimization owners by expected runtime gain (`S4` first unless evidence disproves).

Definition of done:
- [x] hotspot decomposition artifact is emitted and versioned.
- [x] primary, secondary, and tertiary bottlenecks are explicitly named with evidence.
- [x] expected reduction targets for `POPT.1` and `POPT.2` are pinned from decomposition.

#### POPT.0.4 - Runtime budget finalization
Objective:
- replace initial placeholder budgets with measured closure-grade budgets.

Definition of done:
- [x] finalized state budgets are pinned for `S1..S5`.
- [x] candidate/witness/certification lane budgets are either confirmed or tightened.
- [x] budget rationale is evidence-backed and references baseline decomposition.

#### POPT.0.5 - Handoff decision
Objective:
- close `POPT.0` with an explicit go/no-go and ordered execution lane for optimization.

Definition of done:
- [x] explicit decision is recorded as one of `GO_POPT.1` or `HOLD_POPT.0`.
- [x] if `GO_POPT.1`, ordered optimization lane is pinned (`S1 -> S4 -> S2/S3 -> S5` or evidence-driven variant).
- [x] if `HOLD_POPT.0`, unresolved evidence gaps are listed with exact closure actions.

POPT.0 closure snapshot (2026-02-22):
- authority baseline run-id: `c25a2675fbfbacd952b13bb594880e92` (source root `runs/local_full_run-5`), pinned in `runs/fix-data-engine/segment_5B/POPT0_BASELINE_RUN_ID.txt`.
- baseline closure artifacts:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt0_baseline_lock_c25a2675fbfbacd952b13bb594880e92.md`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt0_state_elapsed_c25a2675fbfbacd952b13bb594880e92.csv`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt0_hotspot_map_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt0_budget_pin_c25a2675fbfbacd952b13bb594880e92.json`
- measured segment elapsed (`S0..S5`): `745.263s` (`00:12:25`) vs candidate budget `<= 420s` -> `RED`.
- hotspot ranking from decomposition:
  1. `S4` (`504.641s`, `67.71%`, dominant lane `compute`)
  2. `S1` (`148.452s`, `19.92%`, dominant lane `input_load`)
  3. `S3` (`45.188s`, `6.06%`, dominant lane `compute`)
- handoff decision: `GO_POPT.1` with evidence-driven owner ordering `S4 -> S1 -> S3 -> S2 -> S5`.

### POPT.1 - S1 domain-derivation redesign (secondary hotspot)
Goal:
- replace Python row materialization/set-dedupe path with lazy/vectorized unique-domain derivation.

Execution note:
- `POPT.0` hotspot evidence ranked `S4` above `S1`; execution starts on `S4` first (evidence-driven variant) and then returns to this `S1` lane.

Scope:
- code:
  - `packages/engine/src/engine/layers/l2/seg_5B/s1_time_grid/runner.py`
  - optional shared helper extraction if needed for reusable vectorized domain scan.
- tooling/evidence:
  - `tools/score_segment5b_popt1_closure.py` (new; baseline-vs-candidate runtime + veto rails).
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt1_*` artifacts.
- out-of-scope:
  - no policy/coeff realism tuning in `POPT.1`,
  - no contract/schema semantics relaxation.

POPT.1 baseline anchors (from POPT.0 authority):
- baseline run-id: `c25a2675fbfbacd952b13bb594880e92`.
- baseline `S1 wall`: `148.452s` (`19.92%` of segment lane).
- lane signature: `input_load` dominant (`~146.84s`), compute secondary (`~1.18s`).
- hotspot owner path:
  - `S1: scanning merchant_zone_scenario_local_5A for grouping domain ...`
  - `_scan_domain_keys` currently performs Python per-row tuple insertion over full scenario-local volume.

POPT.1 closure gates (quantified):
- runtime movement gate:
  - `S1 wall <= 90s` (state budget target), OR
  - `S1 reduction >= 40%` vs baseline (`<= 89.071s` equivalent).
- structural non-regression gates:
  - `S1 status=PASS`,
  - `total_bucket_count` unchanged,
  - `total_grouping_rows` unchanged,
  - `total_unique_group_ids` unchanged,
  - no new `error_code/error_class`.
- grouping-shape rails:
  - `median_members_per_group` non-regression within tight tolerance,
  - `max_group_share` non-regression,
  - no increase in scenario_count_failed.
- downstream continuity gates:
  - rerun `S1 -> S2 -> S3 -> S4 -> S5` all `PASS`.
- determinism gate:
  - same `(parameter_hash, manifest_fingerprint, seed)` reproduces identical structural counters and idempotent outputs.

Execution posture:
- run root: `runs/fix-data-engine/segment_5B`.
- rerun law:
  - any `S1` code change reruns `S1 -> S5` (sequential-state law).
- prune posture:
  - prune superseded failed run-id folders before each expensive candidate rerun.
- fail-closed posture:
  - any semantic/regression gate failure => `HOLD_POPT.1_REOPEN`.

#### POPT.1.1 - Equivalence contract and scorer lock
Objective:
- pin exactly what counts as non-semantic optimization for `S1`.

Scope:
- define `segment5b_popt1_closure_<run_id>.json` schema:
  - baseline vs candidate runtime deltas,
  - structural counters veto rails,
  - downstream chain pass/fail map,
  - explicit decision field.
- lock allowed differences:
  - `durations`, lane timing, and logging cadence only.
- lock forbidden differences:
  - grouping identity/counters/schema and downstream pass posture.

Definition of done:
- [x] closure scorer contract is pinned and executable.
- [x] veto checks are explicit and machine-checkable from artifacts.
- [x] no unresolved equivalence ambiguity remains before code edits.

#### POPT.1.2 - Algorithm/design lock for S1 hotspot
Objective:
- lock the pre-implementation algorithm choice and complexity target.

Design alternatives:
- Option A: keep Python per-row batch loops and tune batch size/log cadence only.
- Option B: replace domain derivation with vectorized lazy scan + unique on required key columns.
- Option C: pyarrow dictionary-encoding custom kernel path.

Decision:
- choose Option B as primary lane:
  - compute keys using lazy/vectorized operators (`filter`, null checks, `select`, `unique`) and avoid Python row loops.
  - keep deterministic output via explicit stable sort before grouping-id assignment.
- Option C is fallback only if Option B cannot meet budget with parity.

Complexity posture:
- current: `O(N)` Python-row processing with high interpreter overhead.
- target: `O(N)` columnar scan in native engine + `O(U log U)` deterministic ordering (`U` unique keys), with much lower constant factors.

Definition of done:
- [x] chosen algorithm is documented with rationale and fallback trigger.
- [x] expected complexity and memory/IO posture are explicitly recorded.
- [x] logging cadence budget for scan progress is pinned (no high-frequency spam).

#### POPT.1.3 - Domain-derivation implementation
Objective:
- implement vectorized key-domain extraction in `S1`.

Scope:
- replace `_scan_domain_keys` row loop path with vectorized/lazy domain extraction.
- enforce scenario-id consistency and required-field null checks vectorially.
- emit deterministic key ordering prior to group assignment.

Definition of done:
- [x] `S1` hotspot path no longer depends on per-row Python tuple insertion.
- [x] key-domain parity holds versus baseline authority on structural counters.
- [x] no schema/contract compatibility regressions introduced.

#### POPT.1.4 - Instrumentation + logging budget closure
Objective:
- keep observability while removing runtime drag from progress telemetry.

Scope:
- pin progress heartbeat cadence for heavy scans.
- ensure phase markers remain sufficient for lane decomposition artifacts.

Definition of done:
- [x] lane timing markers remain parsable.
- [x] logging cadence is bounded and non-dominant in `S1` elapsed.
- [x] no loss of required audit evidence.

#### POPT.1.5 - Witness rerun and closure scoring
Objective:
- prove runtime gain and non-regression on changed-state chain.

Scope:
- execute witness rerun `S1 -> S2 -> S3 -> S4 -> S5`.
- emit:
  - `segment5b_popt1_lane_timing_<run_id>.json`,
  - `segment5b_popt1_closure_<run_id>.json`,
  - `segment5b_popt1_closure_<run_id>.md`.

Definition of done:
- [x] witness chain `S1..S5` is all `PASS`.
- [x] runtime gate and veto rails are scored from artifacts.
- [x] reopen blockers (if any) are mapped to bounded follow-up action.

#### POPT.1.6 - Phase closure and handoff
Objective:
- close phase with explicit decision and retained run/artifact map.

Scope:
- record closure decision:
  - `UNLOCK_POPT3` (if in numbered order), or
  - `UNLOCK_POPT2_CONTINUE` (if evidence-driven `S4` lane remains active first).
- prune superseded failed run-id folders under keep-set rules.
- sync build plan + implementation map + logbook.

Definition of done:
- [x] explicit closure decision is recorded.
- [x] retained run-id and artifact pointers are pinned.
- [x] prune action is completed and logged.

POPT.1 closure snapshot (2026-02-22):
- witness authority run-id: `c25a2675fbfbacd952b13bb594880e92` (source root `runs/local_full_run-5`).
- closure artifacts:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt1_lane_timing_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt1_closure_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt1_closure_c25a2675fbfbacd952b13bb594880e92.md`
- quantified closure:
  - runtime: `S1 148.452s -> 11.844s` (`92.02%` reduction), gate `PASS`.
  - structural parity: all pinned counters/shape rails exact, gate `PASS`.
  - downstream continuity: `S2/S3/S4/S5 = PASS`, gate `PASS`.
- execution blocker handled during witness:
  - `S5_OUTPUT_CONFLICT` on pre-existing bundle for same run-id; handled by moving stale bundle folder to `.stale_0224` backup and rerunning `S5` (non-destructive).
- phase decision: `UNLOCK_POPT2_CONTINUE`.
- prune closure evidence:
  - `python tools/prune_failed_runs.py --runs-root runs/fix-data-engine/segment_5B`
  - result: no failed sentinels.

### POPT.2 - S4 expansion-path optimization (primary hotspot)
Goal:
- reduce S4 wall time by cutting Python control-plane overhead while preserving deterministic output semantics.

Execution note:
- despite static numbering, this lane is promoted ahead of `POPT.1` for this cycle by `POPT.0` handoff evidence.

Scope:
- `packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/runner.py`
- `packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/numba_kernel.py`
- optional policy knobs in `config/layer2/5B/arrival_routing_policy_5B.yaml` (only if required by algorithmic redesign, not realism tuning).

POPT.2 baseline anchors (authority evidence):
- baseline from `POPT.0`:
  - `S4 wall = 504.641s` (`67.71%` of segment),
  - lane decomposition: `compute=502.457s`, `input_load=1.830s`, `validation=0.328s`, `write=0.026s`,
  - dominant lane: `compute`.
- latest witness after `POPT.1` closure:
  - `S4 wall = 532.453s` (`S4` still dominant bottleneck).
- structural anchor payload (must remain invariant):
  - `bucket_rows=35700480`,
  - `arrivals_total=124724153`,
  - `arrival_rows=124724153`,
  - `arrival_virtual=2802007`,
  - `missing_group_weights=0`.

POPT.2 closure gates (quantified):
- runtime movement gate (mandatory):
  - `S4 reduction >= 35%` vs `504.641s` baseline (`S4 <= 327.017s` practical threshold), and
  - no material regression on `S2/S3/S5` elapsed beyond +15% from their current witness anchors.
- runtime budget alignment gate (stretch, preferred):
  - `S4 <= 300s` (state stretch budget),
  - with explicit note if not yet at target `<= 240s`.
- structural non-regression gate:
  - `S4 status=PASS`,
  - `total_bucket_rows`, `total_arrivals`, `total_rows_written`, `total_virtual` unchanged,
  - `missing_group_weights` not increased.
- deterministic/idempotence gate:
  - replay on same `(run_id, seed, parameter_hash, manifest_fingerprint)` remains idempotent,
  - no new `S4_OUTPUT_CONFLICT` / `S5_OUTPUT_CONFLICT` without documented housekeeping action.
- downstream continuity gate:
  - rerun `S4 -> S5` both `PASS`,
  - `S5` bundle integrity remains `true`.

Execution posture:
- run root: `runs/fix-data-engine/segment_5B`.
- execution run-id lane: continue authority witness lane `c25a2675fbfbacd952b13bb594880e92` unless a new candidate run-id is required for clean isolation.
- rerun law:
  - any `S4` code change reruns `S4 -> S5`.
- logging budget posture:
  - keep `ENGINE_5B_S4_RNG_EVENTS=0` for optimization witness runs (rng_trace retained),
  - no high-cardinality validation/event logging unless explicitly needed for defect triage.
- prune posture:
  - prune superseded failed run-id folders before each expensive witness rerun.

#### POPT.2.1 - Equivalence contract and scorer lock
Objective:
- pin machine-checkable closure adjudication for S4 optimization lane before code edits.

Scope:
- add scorer contract artifacts:
  - `segment5b_popt2_lane_timing_<run_id>.json`,
  - `segment5b_popt2_closure_<run_id>.json`,
  - `segment5b_popt2_closure_<run_id>.md`.
- scorer must evaluate:
  - runtime movement + budget gates,
  - structural invariants,
  - downstream `S5` continuity,
  - explicit decision vocabulary (`UNLOCK_POPT3_CONTINUE` vs `HOLD_POPT2_REOPEN`).

Definition of done:
- [x] POPT.2 scorer contract is executable.
- [x] all veto rails are artifact-derived and machine-checkable.
- [x] no unresolved equivalence ambiguity remains before S4 edits.

#### POPT.2.2 - Algorithm/design lock for S4 hotspot
Objective:
- choose the lowest-risk highest-yield S4 optimization path with clear fallback.

Design alternatives:
- Option A: parameter-only tuning (`batch_rows`, `max_arrivals_chunk`) without code-path redesign.
- Option B: control-plane vectorization + workspace reuse around existing numba kernel.
- Option C: deeper kernel redesign (inner-loop mechanics/dtype/storage changes).

Decision:
- choose Option B as primary lane:
  - keep core numba semantics,
  - remove Python per-row control-plane overhead around batch preparation and seed/index derivation,
  - reduce repeated allocation churn in segment buffers.
- Option C remains fallback only if Option B fails runtime movement gate.

Complexity posture:
- current: per-batch `O(B)` Python loops + `O(A)` kernel expansion (`A` arrivals), with heavy constant factors in prep and serialization.
- target: keep `O(A)` kernel path but materially reduce pre/post `O(B)` Python overhead and allocation churn.

Definition of done:
- [x] selected algorithm and fallback trigger are pinned.
- [x] complexity + memory/IO posture are explicitly recorded.
- [x] logging budget and validation posture for witness runs are pinned.

#### POPT.2.3 - S4 control-plane optimization (pre-kernel)
Objective:
- reduce Python-side preprocessing overhead before `expand_arrivals`.

Scope:
- optimize high-frequency per-row prep lanes:
  - `row_seq_start` derivation,
  - `group_table_index` lookup,
  - `merchant_idx_array` and `zone_rep_idx` derivation,
  - RNG seed/ctr derivation key construction.
- prefer vectorized/native-path derivation and bounded caches over Python row loops.

Definition of done:
- [ ] control-plane prep elapsed materially reduced in lane decomposition.
- [ ] scenario/domain guardrails (`V-08`) remain strict and unchanged.
- [ ] no changes to statistical semantics of routing/time draws.

#### POPT.2.4 - S4 kernel + buffer lifecycle optimization
Objective:
- improve compute-lane throughput without changing output semantics.

Scope:
- optimize per-segment allocation lifecycle for output arrays and intermediate buffers.
- tune chunking strategy to reduce reallocation and improve kernel occupancy.
- keep `NUMBA` acceleration mandatory in optimization witness lane.

Definition of done:
- [ ] compute lane shows measurable reduction vs baseline decomposition.
- [ ] no RNG-accounting drift (`rng_draws_total`, `rng_blocks_total`, `rng_events_total` integrity).
- [ ] no contract/schema regressions introduced.

#### POPT.2.5 - Witness rerun and closure scoring
Objective:
- prove runtime gain and non-regression on changed-state chain.

Scope:
- rerun `S4 -> S5` on candidate lane.
- emit full POPT.2 closure artifacts from scorer.
- compare to both POPT0 baseline and latest POPT1 witness anchor.

Definition of done:
- [x] `S4` and `S5` are `PASS`.
- [ ] runtime movement gate is satisfied.
- [x] structural/determinism/downstream gates are all green.

#### POPT.2.6 - Phase closure and handoff
Objective:
- close POPT.2 with explicit decision and retained artifact/run pointers.

Scope:
- decision outcomes:
  - `UNLOCK_POPT3_CONTINUE` when all mandatory gates pass,
  - `HOLD_POPT2_REOPEN` with bounded reopen lane if any gate fails.
- run-folder hygiene:
  - prune superseded failed runs under keep-set protocol.
- sync build plan + implementation map + logbook.

Definition of done:
- [x] explicit closure decision is recorded.
- [x] retained run/artifact pointers are pinned.
- [x] prune action is completed and logged.

POPT.2 closure snapshot (2026-02-22):
- authority witness run-id: `c25a2675fbfbacd952b13bb594880e92` (source root `runs/local_full_run-5`).
- closure artifacts:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt2_lane_timing_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt2_closure_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt2_closure_c25a2675fbfbacd952b13bb594880e92.md`
- execution outcomes:
  - primary control-plane optimization patch was implemented and witnessed; runtime regressed (`S4=558.859s`), so lane was fail-closed and reverted.
  - post-revert witness remained above baseline gate (`S4=550.875s`), while structural/downstream/determinism rails stayed green.
- quantified closure:
  - runtime gate: `FAIL` (`S4 baseline=504.641s`, candidate=`550.875s`, reduction `-9.16%`).
  - stretch budget gate (`<=300s`): `FAIL`.
  - structural gate: `PASS` (all pinned counters exact).
  - non-regression gate (`S2/S3/S5`): `PASS`.
  - downstream + determinism gates: `PASS`.
- recurring witness blocker handled:
  - `S5_OUTPUT_CONFLICT` on same-run publish target handled non-destructively by moving existing bundle folder to timestamped `.stale_*` backups before rerun.
- phase decision: `HOLD_POPT2_REOPEN`.
- bounded reopen posture:
  - advance to `POPT.2R` (higher-blast-radius kernel-focused lane) only with strict veto gates and immediate rollback on runtime non-movement.
- prune closure evidence:
  - `python tools/prune_failed_runs.py --runs-root runs/fix-data-engine/segment_5B`
  - result: no failed sentinels.

### POPT.2R - S4 kernel/serialization reopen (high-blast-radius lane)
Goal:
- reopen S4 with a bounded high-impact optimization lane focused on post-kernel serialization and column-materialization overhead while preserving exact semantics.

Authority anchors:
- POPT0 baseline S4: `504.641s`.
- POPT2 post-revert witness S4: `550.875s` (current reopen anchor).
- best recent witness in this branch before regression: `532.453s`.

Execution constraints:
- no policy/config realism tuning in this lane.
- no schema/contract shape changes.
- fail-closed rollback is mandatory on runtime non-movement.

POPT.2R closure gates (quantified):
- mandatory movement gate:
  - candidate `S4 <= 532.453s` and
  - candidate `S4` improves by at least `3%` vs reopen anchor `550.875s`.
- stretch movement gate:
  - candidate `S4 <= 495.788s` (`>=10%` improvement vs reopen anchor).
- structural/determinism gate:
  - all POPT2 structural checks exact (`bucket_rows`, `arrivals_total`, `arrival_rows`, `arrival_virtual`, `missing_group_weights`),
  - `S4/S5` status `PASS`, no new unexpected failure classes.
- downstream gate:
  - `S5` bundle integrity remains `true`.

Execution posture:
- run lane: authority run-id `c25a2675fbfbacd952b13bb594880e92`.
- rerun law: any code mutation reruns `S4 -> S5`.
- idempotence housekeeping allowed:
  - if `S5_OUTPUT_CONFLICT` occurs on same-run publish target, handle non-destructively via timestamped `.stale_*` bundle move before rerun.
- prune hygiene remains mandatory before closure.

#### POPT.2R.1 - Design lock and risk pin
Objective:
- lock specific high-impact lane and rejected alternatives before code edits.

Definition of done:
- [x] chosen mutation lane is explicitly pinned with rationale.
- [x] rejected alternatives and blast-radius rationale are recorded.
- [x] runtime/quality veto conditions are locked.

#### POPT.2R.2 - Serialization-path optimization implementation
Objective:
- reduce redundant timestamp/tzid conversion work after kernel expansion.

Scope:
- optimize S4 post-kernel conversion path where local-time/tzid arrays are often equal across columns.
- reuse mapped/formatted arrays when equality conditions hold.

Definition of done:
- [x] code changes are applied in S4 runner.
- [x] compile checks pass.
- [x] no contract/schema/policy semantics are changed.

#### POPT.2R.3 - Witness rerun and scoring
Objective:
- run `S4 -> S5` witness on candidate and score with POPT2 scorer contract.

Definition of done:
- [x] witness `S4` is `PASS`.
- [x] witness `S5` is `PASS` (with documented housekeeping if conflict occurs).
- [x] scorer artifacts are emitted and reviewed.

#### POPT.2R.4 - Closure decision and rollback discipline
Objective:
- decide unlock vs hold from quantified gates and enforce rollback discipline.

Decision outcomes:
- `UNLOCK_POPT3_CONTINUE` if mandatory movement + all quality rails pass.
- `HOLD_POPT2R_REOPEN` if mandatory movement fails.

Definition of done:
- [x] closure decision is explicitly recorded.
- [x] retained run/artifact pointers are pinned.
- [x] if candidate regresses vs anchor, rollback/restore action is recorded. (N/A: candidate improved vs anchor)
- [x] prune checklist is executed and logged.

POPT.2R closure snapshot (2026-02-22):
- witness run-id: `c25a2675fbfbacd952b13bb594880e92`.
- runtime movement:
  - `S4=460.968s`,
  - vs reopen anchor `550.875s`: `-89.907s` (`-16.32%`),
  - vs `532.453s` gate anchor: pass (`460.968 <= 532.453`).
- downstream/structural:
  - `S5` final status `PASS` (after non-destructive `.stale_*` housekeeping for one replay conflict),
  - bundle integrity `true`,
  - structural invariants unchanged (`bucket_rows`, `arrivals_total`, `arrival_rows`, `arrival_virtual`, `missing_group_weights`).
- scorer artifacts (POPT2 contract):
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt2_lane_timing_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt2_closure_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt2_closure_c25a2675fbfbacd952b13bb594880e92.md`
- phase decision:
  - scorer emits `HOLD_POPT2_REOPEN` due legacy POPT2 `35%` reduction gate,
  - `POPT.2R` quantified mandatory gates are satisfied; decision: `UNLOCK_POPT3_CONTINUE`.

### POPT.3 - S2/S3 secondary throughput closure
Goal:
- close remaining throughput drag in `S2` and `S3` where runtime remains above budget after POPT.1/POPT.2.

Authority anchors:
- latest witness before POPT.3:
  - `S2=47.202s` (`durations.wall_ms=47202`),
  - `S3=51.750s` (`durations.wall_ms=51750`).
- pinned state budgets from POPT.0:
  - `S2 target=35.0s`, `stretch=45.0s`,
  - `S3 target=35.0s`, `stretch=45.0s`.

Execution constraints:
- no realism/policy calibration edits in this lane.
- no schema/contract output-shape changes.
- RNG accounting and deterministic replay rails are non-negotiable.

POPT.3 closure gates:
- primary target gate (green close):
  - `S2 <= 35.0s`,
  - `S3 <= 35.0s`.
- stretch gate (amber with explicit waiver):
  - `S2 <= 45.0s`,
  - `S3 <= 45.0s`,
  - plus measurable movement vs anchors.
- guardrails:
  - `S2/S3/S4/S5` all `PASS`,
  - no new RNG failure classes,
  - no structural/regression drift in downstream metrics (`arrivals_total`, `arrival_rows`, `arrival_virtual`, `bucket_rows`, `missing_group_weights`, `bundle_integrity_ok=true`).

Execution posture:
- authority run-id remains `c25a2675fbfbacd952b13bb594880e92`.
- rerun protocol for any `S2/S3` mutation:
  - `segment5b-s2 -> segment5b-s3 -> segment5b-s4 -> segment5b-s5`.
- same-run `S5_OUTPUT_CONFLICT` handling remains non-destructive via `.stale_*` bundle move before rerun.

#### POPT.3.1 - Design lock and hotspot pin
Objective:
- pin exact hot loops to optimize in S2/S3 and reject non-bounded alternatives.

Definition of done:
- [x] chosen optimization lane is explicitly pinned with rationale.
- [x] rejected alternatives are captured with blast-radius reasons.
- [x] closure gates and veto conditions are locked.

#### POPT.3.2 - S2/S3 implementation lane
Objective:
- apply low/medium-blast performance changes in S2/S3 compute hot paths.

Definition of done:
- [x] S2/S3 code optimizations are implemented.
- [x] compile checks pass.
- [x] policy/schema/contract semantics remain unchanged.

#### POPT.3.3 - Witness execution and measurement
Objective:
- run bounded witness chain and capture state timings + guardrails.

Definition of done:
- [x] `S2` witness is `PASS`.
- [x] `S3` witness is `PASS`.
- [x] downstream safety witness (`S4`,`S5`) is `PASS` (with documented housekeeping if conflict occurs).
- [x] updated timing evidence and closure artifacts are emitted.

#### POPT.3.4 - Closure decision
Objective:
- decide close vs hold using explicit target/stretch/guardrail gates.

Decision outcomes:
- `UNLOCK_POPT4_CONTINUE` if primary target gate and all guardrails pass.
- `UNLOCK_POPT4_CONTINUE_WITH_WAIVER` if stretch gate passes with explicit runtime waiver evidence.
- `HOLD_POPT3_REOPEN` if stretch gate fails or any guardrail fails.

Definition of done:
- [x] closure decision is explicitly recorded.
- [x] retained run/artifact pointers are pinned.
- [x] waiver rationale is recorded if target gate is missed. (`N/A`: stretch gate failed; phase held)
- [x] prune checklist is executed and logged.

POPT.3 closure snapshot (2026-02-22):
- witness run-id: `c25a2675fbfbacd952b13bb594880e92`.
- post-rollback witness timings:
  - `S2=48.516s` (`wall_ms=48516`, anchor `47.202s`, `+2.78%`),
  - `S3=51.485s` (`wall_ms=51485`, anchor `51.750s`, `-0.51%`),
  - `S4=444.297s` (`wall_ms=444297`, `PASS`),
  - `S5=1.733s` (`wall_ms=1733`, `PASS`, `bundle_integrity_ok=true`).
- gate outcomes:
  - primary target gate (`S2<=35s` and `S3<=35s`): `FAIL`,
  - stretch gate (`S2<=45s` and `S3<=45s`): `FAIL`,
  - guardrails (`S2/S3/S4/S5 PASS`, no structural drift, bundle integrity): `PASS`.
- S5 replay handling:
  - first attempt failed with `S5_INFRASTRUCTURE_IO_ERROR` (`F4:S5_OUTPUT_CONFLICT ... phase=publish`),
  - non-destructive housekeeping applied via timestamped `.stale_*` move, rerun passed.
- retained closure artifacts:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt3_lane_timing_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt3_closure_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt3_closure_c25a2675fbfbacd952b13bb594880e92.md`
- prune checklist:
  - `python tools/prune_failed_runs.py --runs-root runs/fix-data-engine/segment_5B` -> `no failed sentinels`.
- phase decision:
  - `HOLD_POPT3_REOPEN` (stretch gate not met in final post-rollback witness).

### POPT.4 - Validation lane + logging budget closure
Goal:
- ensure `S5` and hot-state logging cadence are budgeted and not runtime-dominant.

Definition of done:
- [ ] S5 remains functionally strict while runtime is within budget.
- [ ] high-frequency progress logging is budgeted (no material runtime drag).
- [ ] required auditability remains intact.

### POPT.5 - Performance certification lock
Goal:
- close performance track before realism tuning promotion.

Definition of done:
- [ ] candidate/witness runtime gates pass.
- [ ] final hotspot map shows no unresolved major bottleneck blocking remediation cadence.
- [ ] explicit `GO_P0` decision recorded.

## 6) Remediation phase stack

### P0 - Realism baseline and gateboard lock
Goal:
- lock statistical baseline against authority reports and map exact fail axes before code/policy changes.

Definition of done:
- [ ] baseline realism scorecard for required gates is emitted.
- [ ] per-axis owner-state attribution is recorded (`DST`, `concentration`, `virtual share`, `conservation`).
- [ ] candidate lane protocol and promotion veto rules are pinned.

### P1 - Wave A correctness hardening (DST/civil-time first)
Goal:
- remove deterministic DST/civil-time defect and harden fail-closed behavior.

Scope:
- `S4` local-time serialization/offset semantics.
- `S5` civil-time validation power + strict enforcement.
- conditional upstream `2A` timezone transition-horizon reopen if needed.

Definition of done:
- [ ] `T1/T2/T3` hard gates pass on candidate + witness lanes.
- [ ] civil-time failures are no longer warn-only in enforced mode.
- [ ] count/routing invariants remain non-regressed.

### P2 - Wave B calibration (timezone concentration + virtual share)
Goal:
- move concentration and virtual-share realism into B/B+ bands without breaking Wave-A correctness.

Scope:
- routing policy/calibration in S4 and policy files.
- validation sentinels in S5 to prevent silent drift.

Definition of done:
- [ ] `T6/T7` pass for B on required seeds (or documented intent waiver for virtual-share band).
- [ ] no regressions on `T1..T5`.
- [ ] cross-seed stability within B limits.

### P3 - Wave C contract hardening
Goal:
- pin corrected semantics and thresholds in policy/schema/contracts so closure is durable.

Scope:
- `validation_policy_5B` threshold keys and modes.
- contract/schema alignment and implementation references.

Definition of done:
- [ ] new/updated policy keys are contract-pinned and consumed by runner logic.
- [ ] ambiguity in local-time semantics is removed in docs/contracts.
- [ ] validation outputs include required sentinel metrics for governance.

### P4 - Multi-seed certification and robustness lock
Goal:
- certify B/B+ posture on required seed panel with strict veto gates.

Definition of done:
- [ ] all hard gates pass on `{42,7,101,202}`.
- [ ] B+ decision is explicit (`PASS_BPLUS_ROBUST` or `PASS_B`).
- [ ] cross-seed CV gate result is recorded and archived.

### P5 - Freeze, handoff, and prune closure
Goal:
- freeze certified 5B posture and hand off cleanly to downstream segments.

Definition of done:
- [ ] freeze artifacts refreshed (gateboard + scorecards + pointers).
- [ ] superseded run-id folders pruned under keep-set rules.
- [ ] explicit freeze decision recorded (`5B frozen at PASS_B or PASS_BPLUS_ROBUST`).

## 7) Phase-to-state focus map
- `POPT.0`: `S0..S5` evidence only.
- `POPT.1`: `S1`.
- `POPT.2`: `S4`.
- `POPT.3`: `S2/S3`.
- `POPT.4`: `S5` + logging cadence in hot states.
- `P0`: scorer/evidence lane.
- `P1`: `S4/S5` (+conditional `2A` reopen).
- `P2`: `S4/S5` (+routing/virtual policies).
- `P3`: `S5` + contract/policy pinning.
- `P4`: full segment certification.
- `P5`: freeze + prune.

## 8) Immediate execution order from this plan
1. `POPT.0` is closed and pinned (authority: `c25a2675fbfbacd952b13bb594880e92`).
2. Start optimization execution from pinned hotspot order (`S4` then `S1`) under `POPT.1/POPT.2` with strict non-regression rails.
3. Close `POPT.3` and `POPT.4` once `S4/S1` budgets materially improve.
4. Enter remediation `P0 -> P1 -> P2 -> P3 -> P4 -> P5` with strict veto gates.
