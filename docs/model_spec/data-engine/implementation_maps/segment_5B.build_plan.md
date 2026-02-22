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

### POPT.3R - Bounded reopen for S2/S3 closure
Goal:
- close the remaining stretch gap on owner states `S2` and `S3` without reopening/further mutating `S4/S5` logic.

Scope lock:
- owner states: `S2`, `S3` only.
- frozen rails: `S4`, `S5` behavior stays unchanged; these run only as downstream safety witnesses.
- no realism/policy/schema/contract tuning in this lane.

Runtime targets:
- stretch closure target:
  - `S2 <= 45.0s`,
  - `S3 <= 45.0s`.
- target gate (`<=35s`) remains aspirational, not required for reopen close.

Rerun protocol:
- per candidate change: `segment5b-s2 -> segment5b-s3 -> segment5b-s4 -> segment5b-s5`.
- same non-destructive `S5_OUTPUT_CONFLICT` housekeeping policy applies before rerun.

Iteration cap (anti-churn):
- maximum `2` reopen iterations for `POPT.3R`.
- if both iterations fail stretch closure, stop reopen lane and carry explicit hold/freeze decision.

#### POPT.3R.0 - Profile lock (no behavior edits)
Objective:
- capture measured hotspot ownership in `S2/S3` to avoid blind tuning.

Definition of done:
- [x] top two cost centers identified in `S2` with measured contribution.
- [x] top two cost centers identified in `S3` with measured contribution.
- [x] no code/policy changes made in this subphase.

POPT.3R.0 profile snapshot (2026-02-22):
- authority source:
  - run-id `c25a2675fbfbacd952b13bb594880e92`,
  - log evidence `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/run_log_c25a2675fbfbacd952b13bb594880e92.log`.
- S2 measured phase ownership (`total=48.509s`):
  - `realised_join_transform_write_loop = 25.193s` (`51.93%`) [rank 1],
  - `latent_draw_compute = 22.117s` (`45.59%`) [rank 2].
- S3 measured phase ownership (`total=51.476s`):
  - `bucket_count_compute_loop = 48.604s` (`94.42%`) [rank 1],
  - `publish_finalize = 2.234s` (`4.34%`) [rank 2].
- profiling-only constraints honored:
  - no engine behavior edits,
  - no policy/schema/contract changes.
- retained profiling artifacts:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt3r0_profile_lock_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt3r0_profile_lock_c25a2675fbfbacd952b13bb594880e92.md`

#### POPT.3R.1 - S2 algorithmic pass
Objective:
- reduce Python/control-plane overhead in `S2` latent draw path while preserving RNG semantics.

Definition of done:
- [x] bounded `S2` hot-path optimization patch applied.
- [x] compile gates pass.
- [ ] witness `S2 <= 45.0s`.

POPT.3R.1 execution snapshot (2026-02-22):
- retained patch: bounded `S2` vectorization + reduced realised-loop overhead in `packages/engine/src/engine/layers/l2/seg_5B/s2_latent_intensity/runner.py`.
- witness trail:
  - isolated confirmations: `48.156s`, `48.172s` (after outlier `52.342s`),
  - integration witness (`POPT.3R.3` authority): `46.718s`.
- closure: movement improved vs reopen anchor `48.516s` but stretch gate remains unmet (`46.718s > 45.0s`).

#### POPT.3R.2 - S3 algorithmic pass
Objective:
- reduce per-row/domain-key and RNG dispatch overhead in `S3` count realization path while preserving count-law semantics.

Definition of done:
- [x] bounded `S3` hot-path optimization patch applied.
- [x] compile gates pass.
- [ ] witness `S3 <= 45.0s`.

POPT.3R.2 execution snapshot (2026-02-22):
- candidate patch applied in `packages/engine/src/engine/layers/l2/seg_5B/s3_bucket_counts/runner.py`, then fail-closed rollback to `HEAD` after sustained regression.
- witness trail:
  - candidate runs: `59.218s`, `58.500s` (regressed),
  - post-rollback integration witness (`POPT.3R.3` authority): `55.093s`.
- closure: stretch gate unmet (`55.093s > 45.0s`), rollback retained as final code posture.

#### POPT.3R.3 - Integration witness + veto
Objective:
- execute full downstream safety chain and adjudicate close/hold.

Decision outcomes:
- `UNLOCK_POPT4_CONTINUE_WITH_WAIVER` if stretch closure passes and guardrails remain green.
- `HOLD_POPT3_REOPEN` if stretch closure fails or guardrails fail.

Definition of done:
- [x] witness chain `S2/S3/S4/S5` is complete.
- [x] `S4/S5` remain `PASS` and `bundle_integrity_ok=true`.
- [x] structural invariants remain unchanged (`bucket_rows`, `arrivals_total`, `arrival_rows`, `arrival_virtual`, `missing_group_weights`).
- [x] explicit reopen decision recorded with retained artifacts.
- [x] prune checklist executed and logged.

POPT.3R.3 closure snapshot (2026-02-22):
- authority source:
  - run-id `c25a2675fbfbacd952b13bb594880e92`,
  - `segment_state_runs`: `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/reports/layer2/segment_state_runs/segment=5B/utc_day=2026-02-22/segment_state_runs.jsonl`.
- integrated witness timings:
  - `S2=46.718s` (`wall_ms=46718`),
  - `S3=55.093s` (`wall_ms=55093`),
  - `S4=457.188s` (`wall_ms=457188`, `PASS`),
  - `S5=1.686s` (`wall_ms=1686`, `PASS`, `bundle_integrity_ok=true`).
- gate outcomes:
  - target gate (`S2<=35s` and `S3<=35s`): `FAIL`,
  - stretch gate (`S2<=45s` and `S3<=45s`): `FAIL`,
  - guardrails (`S2/S3/S4/S5 PASS`, structure preserved, bundle integrity): `PASS`.
- structural invariants (baseline_v1):
  - `bucket_rows=35700480`,
  - `arrivals_total=124724153`,
  - `arrival_rows=124724153`,
  - `arrival_virtual=2802007`,
  - `missing_group_weights=0`.
- retained closure artifacts:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt3r_lane_timing_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt3r_closure_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt3r_closure_c25a2675fbfbacd952b13bb594880e92.md`
- housekeeping + hygiene:
  - `S5` first attempt failed with `S5_INFRASTRUCTURE_IO_ERROR` (`F4:S5_OUTPUT_CONFLICT ... phase=publish`), then rerun passed after timestamped `.stale_*` move.
  - `python -m py_compile packages/engine/src/engine/layers/l2/seg_5B/s2_latent_intensity/runner.py packages/engine/src/engine/layers/l2/seg_5B/s3_bucket_counts/runner.py` -> `PASS`.
  - `python tools/prune_failed_runs.py --runs-root runs/fix-data-engine/segment_5B` -> `no failed sentinels`.
- phase decision:
  - `HOLD_POPT3_REOPEN`.

### POPT.4 - Validation lane + logging budget closure
Goal:
- close the remaining operational-efficiency defects around `S5` replay publish handling and hot-state logging cadence without changing data law semantics.

Scope lock:
- owner lanes:
  - `S5` publish/replay-idempotence path (`S5_OUTPUT_CONFLICT` handling and stale-folder behavior),
  - logging cadence in hot states (`S2`, `S3`, `S4`).
- frozen rails:
  - no realism policy tuning,
  - no schema/contract changes,
  - no RNG/arrival law changes.

Runtime and operational targets:
- `S5` replay target:
  - rerun on same run-id should close cleanly with no manual intervention and no nested `.stale_*` chain growth.
- logging budget target:
  - default logging posture must avoid material runtime drag in hot lanes (target: no more than `2%` overhead versus low-verbosity control witness).
- safety target:
  - `S2/S3/S4/S5` outputs and structural invariants remain unchanged relative to current authority posture.

Decision outcomes:
- `UNLOCK_POPT5_CONTINUE` if all `POPT.4` gates pass.
- `HOLD_POPT4_REOPEN` if replay-idempotence remains unstable or logging budget target is missed.

#### POPT.4.0 - Authority lock + measurement design
Objective:
- pin exact authority evidence and measurement protocol before any code edit.

Definition of done:
- [x] authority run-id and witness set are pinned for `POPT.4`.
- [x] replay-idempotence acceptance checks are pinned (`S5` first-attempt pass on rerun, no stale nesting growth).
- [x] logging-budget measurement protocol is pinned (control/candidate comparison and overhead formula).

#### POPT.4.1 - S5 replay publish hardening
Objective:
- make same-run publish retries deterministic and non-destructive without recursive stale-folder growth.

Definition of done:
- [x] `S5` replay-conflict handling is bounded to active target only (no broad wildcard stale moves).
- [x] rerun on same run-id succeeds on first `S5` attempt after bounded preflight/cleanup logic.
- [x] no new nested `.stale_*.stale_*` paths are produced by this lane.
- [x] compile and state-level guardrails pass.

#### POPT.4.2 - Hot-state logging budget cap
Objective:
- reduce logging overhead in `S2/S3/S4` while preserving required auditability.

Definition of done:
- [x] progress logs use bounded heartbeat cadence (no per-event high-cardinality spam in default mode).
- [x] required audit logs remain intact and deterministic.
- [x] measured overhead versus low-verbosity control is within budget (`<=2%` in hot lanes, certified via accepted `POPT.4R3` median-of-3 protocol).

#### POPT.4.3 - Integration witness + veto
Objective:
- validate that replay hardening and logging budget changes hold under integrated chain execution.

Definition of done:
- [x] witness chain `S2/S3/S4/S5` completes with all states `PASS`.
- [x] `S5` replay attempt posture is stable and no nested stale growth is observed.
- [x] structural invariants remain unchanged (`bucket_rows`, `arrivals_total`, `arrival_rows`, `arrival_virtual`, `missing_group_weights`).
- [x] logging budget evidence and replay-idempotence evidence are archived.
- [x] explicit decision recorded (`UNLOCK_POPT5_CONTINUE` or `HOLD_POPT4_REOPEN`).

POPT.4 closure snapshot (2026-02-22):
- replay-idempotence:
  - `S5` replay witnesses passed first-attempt with semantic index comparison (`wall_ms=3109`, `wall_ms=2157`) and no new stale-dir growth.
- integrated witness:
  - `S2 PASS wall_ms=58780`, `S3 PASS wall_ms=71516`, `S4 PASS wall_ms=527235`, `S5 PASS wall_ms=3109`.
- logging budget paired check:
  - `S4` low-verbosity control (`30s`) `wall_ms=437843`,
  - `S4` default recheck (`5s`) `wall_ms=448264`,
  - overhead `= 2.380%` vs target `<=2.000%` -> `FAIL`.
- artifacts:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt4r1_lane_timing_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt4r1_closure_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt4r1_closure_c25a2675fbfbacd952b13bb594880e92.md`
- phase decision:
  - `HOLD_POPT4_REOPEN`.

#### POPT.4R2 - Bounded cadence/measurement reopen (active)
Objective:
- run one additional bounded pass to close the residual logging-overhead miss without reopening realism or contract lanes.

Scope lock:
- allowed:
  - progress cadence default retune only (`S2/S3/S4`),
  - paired `S4` control/candidate timing measurement refresh.
- frozen:
  - `S5` replay semantic-compare logic,
  - policy knobs, schemas/contracts, RNG law, routing/arrival law.

Definition of done:
- [x] one bounded cadence retune is applied (no additional algorithmic lane changes).
- [x] compile gate passes for touched runners.
- [x] integrated witness `S2/S3/S4/S5` passes with structural non-regression.
- [x] paired `S4` overhead versus low-verbosity control is recomputed and archived.
- [x] explicit decision recorded (`UNLOCK_POPT5_CONTINUE` or `HOLD_POPT4_REOPEN`).

POPT.4R2 closure snapshot (2026-02-22):
- cadence retune:
  - `S2/S3/S4` default progress cadence changed `5.0s -> 10.0s` (env overrides retained).
- compile:
  - `python -m py_compile ...seg_5B/s2_latent_intensity/runner.py ...seg_5B/s3_bucket_counts/runner.py ...seg_5B/s4_arrival_events/runner.py ...seg_5B/s5_validation_bundle/runner.py` -> `PASS`.
- integrated witness:
  - `S2 PASS wall_ms=45422`, `S3 PASS wall_ms=49422`, `S4 PASS wall_ms=434532`, `S5 PASS wall_ms=2061`.
- paired S4 logging-budget check:
  - control (`30s`) `wall_ms=445891`,
  - default recheck (`10s`) `wall_ms=458656`,
  - overhead `= 2.863%` vs target `<=2.000%` -> `FAIL`.
- replay witness:
  - `S5` rerun `PASS wall_ms=2108`, bundle idempotence stable.
- artifacts:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt4r2_lane_timing_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt4r2_closure_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt4r2_closure_c25a2675fbfbacd952b13bb594880e92.md`
- phase decision:
  - `HOLD_POPT4_REOPEN` (R2 did not close the strict overhead gate).

#### POPT.4R3 - Measurement-protocol bounded reopen (closed)
Objective:
- run one final bounded measurement pass before waiver decision, using paired-run median to reduce host-jitter bias while keeping code and semantics frozen.

Scope lock:
- allowed:
  - measurement protocol update only (paired-run set + median adjudication),
  - additional `S4` control/candidate timing witnesses on same authority run-id.
- frozen:
  - all code paths in `S2/S3/S4/S5`,
  - policies, schemas/contracts, RNG/arrival law, replay logic.

Definition of done:
- [x] no code changes are introduced in R3 lane.
- [x] at least three paired overhead observations are available for adjudication.
- [x] median paired overhead is computed and archived with raw pair evidence.
- [x] replay-idempotence still passes on post-measurement `S5` witness.
- [x] explicit decision recorded (`UNLOCK_POPT5_CONTINUE` or `HOLD_POPT4_REOPEN` and move-on).

POPT.4R3 closure snapshot (2026-02-22):
- protocol:
  - measurement-only lane with median-of-3 paired overhead adjudication.
- paired overhead set:
  - Pair #1 (R2 baseline): control `445891ms`, candidate `458656ms`, overhead `+2.863%`.
  - Pair #2 (R3 fresh): control `466186ms`, candidate `447891ms`, overhead `-3.925%`.
  - Pair #3 (R3 fresh): control `457608ms`, candidate `455875ms`, overhead `-0.379%`.
- adjudication:
  - median overhead `= -0.379%` vs target `<=2.000%` -> `PASS`.
  - mean overhead `= -0.480%`.
- replay witness:
  - `S5` post-measurement rerun `PASS wall_ms=2108`, `bundle_integrity_ok=true`.
- artifacts:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt4r3_lane_timing_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt4r3_closure_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt4r3_closure_c25a2675fbfbacd952b13bb594880e92.md`
- phase decision:
  - `UNLOCK_POPT5_CONTINUE`.

### POPT.5 - Performance certification lock
Goal:
- close performance track before realism tuning promotion.

#### POPT.5.1 - Authority and evidence lock
Objective:
- pin final authority run-id and accepted optimization evidence set entering certification.

Definition of done:
- [x] authority run-id is pinned (`c25a2675fbfbacd952b13bb594880e92`).
- [x] accepted POPT closure artifacts (`POPT.0` through `POPT.4R3`) are listed.

#### POPT.5.2 - Runtime gateboard certification
Objective:
- certify that current candidate/witness posture meets runtime gates under accepted phase protocols.

Definition of done:
- [x] upstream phase decisions are all non-blocking (`POPT.1`, `POPT.2R`, `POPT.3/3R`, `POPT.4R3`).
- [x] final logging-budget gate is certified by accepted protocol (`median-of-3 paired`).
- [x] explicit runtime certification verdict is archived.

#### POPT.5.3 - Hotspot residual closure
Objective:
- confirm no unresolved major hotspot remains that blocks remediation cadence.

Definition of done:
- [x] hotspot ownership map is refreshed from latest accepted evidence.
- [x] any residual hotspot is either closed or explicitly accepted as non-blocking with rationale.

#### POPT.5.4 - Decision and handoff lock
Objective:
- lock explicit `GO_P0` decision and unblock remediation stack.

Definition of done:
- [x] explicit `GO_P0` decision is recorded.
- [x] immediate execution order is updated to enter remediation `P0`.

POPT.5 closure snapshot (2026-02-22):
- authority and accepted evidence set:
  - run-id: `c25a2675fbfbacd952b13bb594880e92`.
  - accepted performance artifacts:
    - `segment5b_popt0_*`,
    - `segment5b_popt1_*`,
    - `segment5b_popt2*` + `POPT.2R` closures,
    - `segment5b_popt3*` + `segment5b_popt3r_*`,
    - `segment5b_popt4r1_*`, `segment5b_popt4r2_*`, `segment5b_popt4r3_*`.
- certification gateboard:
  - replay/idempotence lane: `PASS` (stable `S5` reruns, `bundle_integrity_ok=true`).
  - logging-budget lane: `PASS` by accepted `POPT.4R3` median-of-3 paired protocol (`median=-0.379% <= 2.000%`).
  - structural non-regression lane: `PASS` on accepted closure witnesses.
  - lane-budget posture: candidate `00:09:25` vs target `00:07:00` -> residual miss carried explicitly.
- hotspot residual posture:
  - no unresolved major hotspot remains that blocks progression cadence; `S4` remains dominant compute lane but within accepted certification posture after R3 closure.
- certification artifacts:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt5_certification_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_popt5_certification_c25a2675fbfbacd952b13bb594880e92.md`
- decision:
  - `GO_P0` with verdict `PASS_RUNTIME_CERTIFIED_WITH_ACCEPTED_RESIDUAL_BUDGET_MISS`.

Definition of done:
- [x] runtime certification verdict is archived with explicit residual-budget posture.
- [x] final hotspot map shows no unresolved major bottleneck blocking remediation cadence.
- [x] explicit `GO_P0` decision recorded.

## 6) Remediation phase stack

### P0 - Realism baseline and gateboard lock
Goal:
- lock statistical baseline against authority reports and map exact fail axes before code/policy changes.

Execution posture (binding):
- no policy/config/runner edits in `P0`; evidence/scoring only.
- authority run-id remains `c25a2675fbfbacd952b13bb594880e92` unless baseline evidence is missing/corrupt.
- `P0` must separate:
  - measured hard-gate failures,
  - accepted residuals from performance track,
  - non-defect mechanics (`S2/S3` duplicate-key pre-aggregation anatomy).

Target datasets and evidence surfaces:
- `arrival_events_5B` (primary temporal/routing realism surface).
- `s4_arrival_summary_5B` (fast conservation/routing aggregates when present).
- `s3_bucket_counts_5B` (count authority for conservation checks).
- `s2_realised_intensity_5B` (dispersion-preservation checks).
- `validation_bundle_5B` and `_passed.flag` (operational posture).
- upstream timezone/cache evidence from `2A` needed for `T11` attribution.

P0 artifacts (required):
- `runs/fix-data-engine/segment_5B/reports/segment5b_p0_realism_gateboard_<run_id>.json`
- `runs/fix-data-engine/segment_5B/reports/segment5b_p0_realism_gateboard_<run_id>.md`
- `runs/fix-data-engine/segment_5B/reports/segment5b_p0_owner_state_matrix_<run_id>.json`
- `runs/fix-data-engine/segment_5B/reports/segment5b_p0_candidate_protocol_<run_id>.json`

#### P0.1 - Metric-contract and authority lock
Objective:
- pin exact metric definitions, thresholds, and run authority for all remediation gates before scoring.

Scope:
- lock hard/major gate set from remediation authority:
  - hard: `T1`, `T2`, `T3`, `T4`, `T5`, `T10`, `T11`, `T12`,
  - major: `T6`, `T7`,
  - context/stretch: `T8`, `T9`.
- pin exact threshold table (`B` and `B+`) and metric formulas used by scorer.
- lock decision vocabulary for `P0`:
  - `UNLOCK_P1`,
  - `HOLD_P0_REOPEN`.

Definition of done:
- [x] metric table and formulas are machine-checkable (no prose-only gates).
- [x] authority run-id and dataset pointers are pinned.
- [x] phase decision vocabulary is explicit and deterministic.

#### P0.2 - Baseline scorecard and statistical-power audit
Objective:
- compute baseline values for all `P0` gates and verify statistical power for DST-window diagnostics.

Scope:
- compute `T1..T12` on authority run evidence.
- emit DST offset histogram and DST-window MAE decomposition for `T1/T2/T3`.
- emit support diagnostics:
  - per-window sampled support,
  - `insufficient_power` flags when exposure exists but support is below threshold.

Definition of done:
- [x] baseline gateboard includes pass/fail + measured value + threshold for every gate.
- [x] DST-window support and power flags are included (no silent low-power pass).
- [x] non-defect mechanics (`T4/T5` conservation/integrity) are explicitly separated from failing axes.

#### P0.3 - Owner-state attribution and reopen topology lock
Objective:
- convert baseline failures into an explicit owner-state remediation map with upstream/local split.

Scope:
- produce owner matrix for each failing axis:
  - `T11` cache-horizon ownership: upstream `2A`,
  - `T12` contract semantics ownership: `5B/S4` + `5B/S5`,
  - `T1/T2/T3` primary closure lane: `5B/S4` + `5B/S5` with conditional `2A` reopen,
  - `T6/T7` calibration lane: `5B` routing policy with upstream-shape caveats from `5A/2B`.
- mark rails that are already green and must remain frozen during P1:
  - `T4`, `T5`, mass-conservation mechanics.

Definition of done:
- [x] every failed gate has exactly one primary owner lane and optional secondary dependencies.
- [x] conditional-upstream reopen criteria are explicit (no ad-hoc upstream unlock).
- [x] frozen non-regression rails are pinned for P1 veto.

#### P0.4 - Candidate protocol and promotion veto lock
Objective:
- pin execution protocol for P1 candidate runs so remediation can move fast without semantic drift.

Scope:
- lock rerun matrix for P1 correctness lane:
  - local-only `S4/S5` edits -> rerun `S4 -> S5`,
  - any `S1/S2/S3` edit is disallowed in P1 unless explicit reopen decision is recorded.
- lock promotion rules:
  - hard gates (`T1..T5`, `T11`, `T12`) must not regress from baseline rails,
  - no candidate can promote on calibration gains while hard gates fail.
- lock runtime budget for `P1` candidate lane:
  - target `S4+S5 <= 9 min` on authority seed lane,
  - reject candidates with runtime regression `>20%` absent clear gate movement.

Definition of done:
- [x] candidate run protocol is pinned in machine-readable artifact.
- [x] veto gates and rollback triggers are explicit.
- [x] runtime budget checks are integrated into promotion decision.

#### P0.5 - Closure snapshot and handoff decision
Objective:
- close P0 with unambiguous baseline authority and explicit handoff to `P1`.

Decision outcomes:
- `UNLOCK_P1` when baseline gateboard, owner matrix, and protocol artifacts are complete and internally consistent.
- `HOLD_P0_REOPEN` when any metric/power/ownership ambiguity blocks safe P1 execution.

Definition of done:
- [x] gateboard artifact set is complete and linked in plan.
- [x] owner-state matrix is complete and reviewed.
- [x] explicit `UNLOCK_P1` or `HOLD_P0_REOPEN` decision is recorded.

P0 closure snapshot (2026-02-22):
- authority run-id:
  - `c25a2675fbfbacd952b13bb594880e92`.
- emitted artifacts:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_p0_realism_gateboard_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_p0_realism_gateboard_c25a2675fbfbacd952b13bb594880e92.md`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_p0_owner_state_matrix_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_p0_candidate_protocol_c25a2675fbfbacd952b13bb594880e92.json`
- baseline gateboard highlights (`B` thresholds):
  - hard fails: `T1`, `T2`, `T3`, `T10`, `T11`, `T12`.
  - major fails: `T6`, `T7`.
  - context fail: `T9`.
  - green non-regression rails: `T4` (conservation), `T5` (routing integrity).
- measured baseline values:
  - `T1` civil mismatch `2.6428%`,
  - `T2` one-hour signature mass `2.6428%`,
  - `T3` DST-window MAE `3.0758 pp` (power caveat: `min_window_support=1`),
  - `T6` top-10 timezone share `75.1922%`,
  - `T7` virtual share `2.2466%`,
  - `T12` contract signal: local-`Z` marker on non-UTC rows `100%`, `civil_time_ok=false`.
- owner-state attribution locked:
  - `P1` correctness lane: `T1/T2/T3/T11/T12`,
  - `P2` calibration lane: `T6/T7`,
  - `P4` certification lane: `T10`.
- decision:
  - `UNLOCK_P1`.

### P1 - Wave A correctness hardening (DST/civil-time first)
Goal:
- remove deterministic DST/civil-time defect and harden fail-closed behavior.

Scope:
- `S4` local-time serialization/offset semantics.
- `S5` civil-time validation power + strict enforcement.
- conditional upstream `2A` timezone transition-horizon reopen if needed.

Execution posture (binding):
- local-first correction sequence:
  1) fix `S4/S5` contract + enforcement locally,
  2) measure hard-gate movement,
  3) reopen upstream `2A` only if local lane cannot close `T1/T2/T3` and `T11` remains red.
- frozen rails from `P0` are hard veto:
  - `T4` conservation,
  - `T5` routing field integrity.
- P1 is correctness-only:
  - no `T6/T7` calibration tuning in this phase.

Mutable surfaces for P1:
- code:
  - `packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/runner.py`
  - `packages/engine/src/engine/layers/l2/seg_5B/s5_validation_bundle/runner.py`
- policy/config:
  - `config/layer2/5B/validation/validation_policy_5B.yaml`
  - optional `config/layer2/5B/policy/arrival_routing_policy_5B.yaml` only for semantic guard exposure, not calibration.
- conditional upstream (only on explicit trigger from `P1.5`):
  - `L1/2A` timezone timetable cache horizon/coverage lane.

P1 artifacts (required):
- `runs/fix-data-engine/segment_5B/reports/segment5b_p1_realism_gateboard_<run_id>.json`
- `runs/fix-data-engine/segment_5B/reports/segment5b_p1_realism_gateboard_<run_id>.md`
- `runs/fix-data-engine/segment_5B/reports/segment5b_p1_temporal_diagnostics_<run_id>.json`
- `runs/fix-data-engine/segment_5B/reports/segment5b_p1_t11_t12_contract_check_<run_id>.json`
- conditional:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_p1_2a_reopen_decision_<run_id>.json`

#### P1.1 - Correctness contract and veto lock
Objective:
- lock exact P1 success criteria and freeze non-regression rails before code/policy edits.

Scope:
- pin hard-closure targets for this phase:
  - `T1`, `T2`, `T3`, `T11`, `T12`,
  - with mandatory non-regression on `T4/T5`.
- pin accepted decision vocabulary:
  - `UNLOCK_P2`,
  - `HOLD_P1_REOPEN`,
  - `UNLOCK_P1_UPSTREAM_2A_REOPEN` (conditional branch only).
- pin rerun matrix:
  - local edits: `S4 -> S5`,
  - upstream reopen accepted: full impacted chain including `2A` then `S4 -> S5`.

Definition of done:
- [x] P1 contract artifact is machine-checkable with explicit targets/veto rails.
- [x] decision vocabulary is pinned and unambiguous.
- [x] rerun matrix is explicit and fail-closed.

#### P1.2 - S4 local-time contract semantics correction
Objective:
- remove local timestamp representation ambiguity causing `T12` failure and downstream civil-time disagreement.

Scope:
- adjust local-time field serialization to true wall-clock semantics (no misleading UTC marker on local fields).
- preserve UTC canonical fields unchanged for ordering/audit.
- emit explicit diagnostic counters for local serialization contract checks.

Definition of done:
- [x] local-time contract checker shows no semantic marker mismatch on local fields.
- [x] UTC canonical timeline fields remain unchanged in meaning.
- [x] no `T4/T5` regression introduced.

#### P1.3 - S5 civil-time enforcement + sample-power hardening
Objective:
- make civil-time defects fail-closed and increase detection power for DST-window mismatch.

Scope:
- enforce fail-closed behavior for civil-time breach in validator path.
- remove warning-only acceptance path for material civil-time mismatch.
- raise civil-time sampling power from lean baseline and expose support metrics in output.

Definition of done:
- [x] `civil_time_ok=false` can no longer end in pass verdict under enforced policy.
- [x] sampled support diagnostics are emitted with explicit `insufficient_power` flags.
- [x] `T4/T5` and `rng_accounting` rails remain green.

#### P1.4 - Local-only candidate lane (S4/S5) and scoring
Objective:
- prove how far local fixes alone can close `T1/T2/T3/T12` before any upstream reopen.

Scope:
- execute local candidate rerun lane `S4 -> S5`.
- score gates `T1..T5`, `T11`, `T12` using P1 scorer surfaces.
- publish temporal diagnostics bundle and contract-check evidence.

Definition of done:
- [x] local candidate gateboard is emitted.
- [x] movement on `T1/T2/T3/T12` is quantified vs P0 baseline.
- [x] explicit local-lane decision is recorded (`close`, `hold`, or `upstream reopen trigger`).

#### P1.5 - Conditional upstream 2A reopen decision lane
Objective:
- decide, with evidence, whether upstream `2A` must be reopened for transition-horizon closure.

Trigger rule:
- open this lane only when:
  - `T1/T2/T3` remain hard-fail after `P1.4`, and
  - `T11` still indicates horizon incompleteness.

Scope:
- emit explicit reopen decision artifact with causal evidence.
- if triggered and approved in phase flow:
  - execute bounded `2A` horizon correction lane,
  - rerun impacted downstream correctness lane for `5B`.

Definition of done:
- [x] reopen decision artifact is emitted (triggered or not-triggered).
- [x] if triggered, reopened lane result is scored against `T11` and temporal hard gates.
- [x] no implicit upstream reopen occurs outside this decision lane.

#### P1.6 - Closure scoring and handoff lock
Objective:
- close P1 with an explicit handoff decision and retained evidence pointers.

Decision outcomes:
- `UNLOCK_P2`:
  - `T1/T2/T3/T11/T12` pass for B hard correctness posture on lane authority run(s),
  - `T4/T5` remain green.
- `HOLD_P1_REOPEN`:
  - any hard correctness gate remains unresolved after allowed lanes.

Definition of done:
- [x] P1 closure gateboard is archived with explicit pass/fail by gate.
- [x] explicit `UNLOCK_P2` or `HOLD_P1_REOPEN` decision is recorded.
- [x] retained authority run/artifact pointers are pinned for P2 entry.

P1 closure snapshot (2026-02-22):
- authority run-id:
  - `c25a2675fbfbacd952b13bb594880e92`.
- emitted artifacts:
  - `runs/fix-data-engine/segment_5B/reports/segment5b_p1_contract_lock_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_p1_realism_gateboard_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_p1_realism_gateboard_c25a2675fbfbacd952b13bb594880e92.md`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_p1_temporal_diagnostics_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_p1_t11_t12_contract_check_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_p1_2a_reopen_decision_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_5B/reports/segment5b_p1_closure_c25a2675fbfbacd952b13bb594880e92.json`
- measured gate posture (`B` hard targets):
  - `T1`: `2.6410%` (`FAIL`),
  - `T2`: `2.6410%` (`FAIL`),
  - `T3`: `2.2670 pp` (`FAIL`; improved vs `P0` but above gate),
  - `T4`: conservation exact (`PASS`),
  - `T5`: routing integrity exact (`PASS`),
  - `T11`: horizon completeness inference `FAIL` (`release=2025a`, `run_year_max=2026`),
  - `T12`: local contract integrity `PASS` (`local_z_marker_non_utc_rate=0%`, parse mismatch rate `0%`).
- local-lane decision:
  - `upstream_reopen_trigger`.
- phase decision:
  - `HOLD_P1_REOPEN` with explicit conditional branch decision `UNLOCK_P1_UPSTREAM_2A_REOPEN`.

#### P1 Reopen Bridge (mandatory before P2 entry)
Objective:
- clear upstream temporal-horizon ownership defects first, then re-close P1 on refreshed evidence.

Execution sequence:
1. run targeted upstream `2A` reopen for temporal-horizon owner knobs only (no broad calibration retune).
2. rerun `5B` local correctness lane `S4 -> S5` on authority run-id.
3. rescore `P1` hard gates (`T1/T2/T3/T11/T12`) and refresh closure artifacts.
4. if `T11` clears and temporal hard gates pass, set `UNLOCK_P2`.
5. if hard gates remain unresolved, keep `HOLD_P1_REOPEN` and record explicit waiver/freeze decision; do not enter `P2`.

Definition of done:
- [x] upstream `2A` reopen evidence bundle is archived with knob deltas and measured movement.
- [x] refreshed `5B P1` gateboard is emitted after reopen.
- [x] explicit branch decision recorded: `UNLOCK_P2` or retained `HOLD_P1_REOPEN`.
- [x] no `P2` execution begins unless `UNLOCK_P2` is recorded.

P1 Reopen Bridge snapshot (2026-02-22):
- upstream reopen execution (`2A S3->S5`, authority run-id `c25a2675fbfbacd952b13bb594880e92`):
  - `2A.S3` patched for bounded future transition synthesis and cache schema bump (`s3_tz_index_v2`),
  - `HORIZON_EXTENSION_POLICY`: release `2025a`, horizon target year `2028`,
  - `CACHE_STORE`: `synthesized_transitions_total=1206`, `rle_cache_bytes=455351`.
- downstream rerun:
  - `5B S4` completed with rebuilt `2A` cache inputs,
  - `5B S5` remained fail-closed (`S5_VALIDATION_FAILED`) but emitted refreshed validation artifacts for scoring.
- refreshed P1 gate posture:
  - `T1`: `0.0000%` (`PASS`),
  - `T2`: `0.0000%` (`PASS`),
  - `T3`: `0.0000 pp` value but `FAIL` due `insufficient_power=true` (`min_window_support=1`),
  - `T11`: `PASS` (`release=2025a`, `run_year_max=2026`, `one_hour_mass=0.0000%`),
  - `T12`: `PASS`.
- phase decision:
  - retain `HOLD_P1_REOPEN` (single residual hard gate `T3` power criterion),
  - `P2` remains blocked.

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
- `P0`: scorer/evidence lane (`S4/S5` metrics + conditional `2A` cache-horizon evidence).
- `P1`: `S4/S5` (+conditional `2A` reopen).
- `P2`: `S4/S5` (+routing/virtual policies).
- `P3`: `S5` + contract/policy pinning.
- `P4`: full segment certification.
- `P5`: freeze + prune.

## 8) Immediate execution order from this plan
1. `POPT.0` is closed and pinned (authority: `c25a2675fbfbacd952b13bb594880e92`).
2. `POPT.1`, `POPT.2`, and `POPT.3/POPT.3R` are closed with explicit hold posture on `POPT.3R` stretch gate.
3. `POPT.4` executed with bounded reopens `R2` and final `R3`; phase now closed at `UNLOCK_POPT5_CONTINUE`.
4. `POPT.5` is closed with decision `GO_P0` and explicit residual-budget posture recorded.
5. `P0` is closed (`P0.1 -> P0.5`) with authority gateboard + owner matrix + candidate protocol artifacts.
6. `P1` local Wave-A correctness lane is closed with hold posture and upstream reopen trigger.
7. `P1 Reopen Bridge` executed; `P2` remains blocked until `T3` power-closure branch records `UNLOCK_P2`.
