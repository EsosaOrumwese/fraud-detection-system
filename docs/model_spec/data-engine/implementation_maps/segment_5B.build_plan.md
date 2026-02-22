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
- `packages/engine/src/engine/layers/l2/seg_5B/s1_time_grid/runner.py`.

Definition of done:
- [ ] `S1` wall time reduced materially vs baseline (target `>= 60%` reduction).
- [ ] grouping/domain output parity holds on deterministic checks.
- [ ] schema and downstream non-regression (`S2..S5`) remain green.

### POPT.2 - S4 expansion-path optimization (primary hotspot)
Goal:
- reduce S4 wall time by cutting Python control-plane overhead while preserving deterministic output semantics.

Execution note:
- despite static numbering, this lane is promoted ahead of `POPT.1` for this cycle by `POPT.0` handoff evidence.

Scope:
- `packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/runner.py`
- `packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/numba_kernel.py`
- optional policy knobs in `config/layer2/5B/arrival_routing_policy_5B.yaml` (only if required by algorithmic redesign, not realism tuning).

Definition of done:
- [ ] `S4` wall time reduced materially vs baseline (target `>= 35%` reduction).
- [ ] deterministic replay/idempotence checks pass.
- [ ] count conservation, routing nullability, and schema invariants remain exact.

### POPT.3 - S2/S3 secondary throughput closure
Goal:
- close remaining throughput drag in `S2` and `S3` where runtime remains above budget after POPT.1/POPT.2.

Definition of done:
- [ ] `S2` and `S3` each within pinned state budgets (or explicit waiver with evidence).
- [ ] no RNG-accounting regressions introduced.
- [ ] no realism-shape tuning performed in POPT phases.

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
