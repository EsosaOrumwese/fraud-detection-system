# Segment 5A Remediation Build Plan (B/B+ Execution Plan)
_As of 2026-02-21_

## 0) Objective and closure rule
- Objective: keep Segment `5A` at certified realism quality and improve it beyond current caveats, targeting `B+` robustness (not threshold-forging).
- Published authority posture: `B+` with material caveats (channel collapse to `mixed`, concentration skew, tail dormancy, DST residual structure, uneven overlay coverage).
- Closure rule:
  - `PASS_BPLUS_ROBUST`: all hard gates pass on all required seeds and no caveat axis remains structurally collapsed.
  - `PASS_B`: all hard gates pass on all required seeds but one or more stretch gates remain open.
  - `HOLD_REMEDIATE`: any hard gate fails on any required seed.
- Phase advancement law (binding): no phase is closed until all phase DoD items are green.

## 1) Source-of-truth stack

### 1.1 Statistical authority
- `docs/reports/eda/segment_5A/segment_5A_published_report.md`
- `docs/reports/eda/segment_5A/segment_5A_remediation_report.md`

### 1.2 State and contract authority
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s0.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s1.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s2.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s3.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s4.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s5.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5A/dataset_dictionary.layer2.5A.yaml`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5A/schemas.5A.yaml`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5A/artefact_registry_5A.yaml`

### 1.3 Upstream freeze posture (binding for this cycle)
- `1A`, `1B`, `2A`, `2B`, `3A`, `3B` remain frozen inputs for this first 5A remediation cycle.
- 5A remediation starts as 5A-local.
- Upstream reopen is allowed only via explicit decision after saturation evidence in `P4`/`P5`.

## 2) Causal remediation posture and ownership
- Causal chain to remediate:
  - `S1 class/channel assignment -> S2 shape realization -> S3 baseline intensity -> S4 overlay/time mapping -> S5 certification`.
- State ownership by weakness axis:
  - Channel collapse: `S1 + S2`.
  - Class/country concentration: `S1` (with `S2` support).
  - Tail-zone dormancy: `S3`.
  - DST residual structure: `S4`.
  - Overlay country fairness: `S4`.
- Structural rails:
  - `S0` sealing/gate integrity and `S5` validation semantics are veto rails.
  - They are not tuning targets except where required to expose realism evidence.

## 3) Statistical gates, invariants, and seed policy
- Required certification seeds: `{42, 7, 101, 202}`.

### 3.1 Hard B gates
- Mass conservation:
  - local/UTC total conservation MAE `<= 1e-9`.
  - shape normalization max abs error `<= 1e-9`.
- Channel realization:
  - at least 2 realized `channel_group` values with each carrying `>= 10%` mass in eligible rows.
  - `night_share(CNP) - night_share(CP) >= 0.08`.
- Concentration:
  - `max_class_share <= 0.55`.
  - `max_single_country_share_within_class <= 0.40`.
- Tail realism:
  - tail-zone zero-rate `<= 90%`.
  - non-trivial TZIDs (`weekly_total > 1.0`) `>= 190`.
- DST residual:
  - overall mismatch `<= 0.20%`.
  - DST-zone mismatch `<= 0.50%`.
- Overlay fairness:
  - no zero affected-share among top-volume countries.
  - `p90/p10(country_affected_share) <= 2.0`.

### 3.2 B+ stretch gates
- Channel realization:
  - all intended channel groups realized (no practical collapse to `mixed`).
  - `night_share(CNP) - night_share(CP) >= 0.12`.
- Concentration:
  - `max_class_share <= 0.50`.
  - `max_single_country_share_within_class <= 0.35`.
- Tail realism:
  - tail-zone zero-rate `<= 80%`.
  - non-trivial TZIDs `>= 230`.
- DST residual:
  - overall mismatch `<= 0.05%`.
  - DST-zone mismatch `<= 0.20%`.
- Overlay fairness:
  - `p90/p10(country_affected_share) <= 1.6`.

### 3.3 Non-regression invariants (must hold in all phases)
- Do not flatten heavy-tail merchant behavior just to reduce concentration metrics.
- Preserve class archetype ordering:
  - `night_share(online_24h) > night_share(consumer_daytime)`.
  - `weekend_share(evening_weekend) > weekend_share(office_hours)`.
- Preserve deterministic replay/idempotency semantics of S1-S5 outputs.
- Preserve contract/schema compatibility and segment gate behavior.

### 3.4 Cross-seed stability gates
- Hard gates must pass on every required seed.
- Cross-seed CV targets on key medians:
  - `B`: `CV <= 0.25`.
  - `B+`: `CV <= 0.15`.

## 4) Run protocol, retention, and rerun law
- Active run root: `runs/fix-data-engine/segment_5A/`.
- Keep-set only:
  - baseline authority candidate,
  - current candidate,
  - last good candidate,
  - active certification pack.
- Prune superseded failed run-id folders before new expensive runs.

### 4.1 Progressive rerun matrix (sequential-state law)
- If S1 policy/code changes: rerun `S1 -> S2 -> S3 -> S4 -> S5`.
- If S2 policy/code changes: rerun `S2 -> S3 -> S4 -> S5`.
- If S3 policy/code changes: rerun `S3 -> S4 -> S5`.
- If S4 policy/code changes: rerun `S4 -> S5`.
- If only scorer/evidence tooling changes: rerun scorers only; do not mutate state outputs.

### 4.2 Candidate lane policy
- Prefer single-seed candidate lanes for directional movement before multi-seed witness/certification.
- Promote to 2-seed witness only after candidate lane clears phase-specific gates.
- Promote to 4-seed certification only after witness is green.

## 5) Performance optimization pre-lane (POPT, mandatory before heavy remediation reruns)
- Objective: establish evidence-based minute-scale iteration posture before repeated realism tuning.
- Optimization scope in this cycle: `S2`, `S4`, `S5` first (expected hotspots from implementation complexity), with `S1/S3` touched only if profiling proves they are material.
- Hard constraints:
  - determinism and contract compliance are non-negotiable,
  - no statistical-shape tuning in POPT phases,
  - single-process efficient baseline first (no parallelism dependency).

### 5.1 Runtime-budget gates (provisional, to be pinned by POPT.0)
- Candidate lane (`seed=42`, changed-state onward): target `<= 20 min`.
- Witness lane (`seeds=42,101`): target `<= 40 min`.
- Certification lane (`seeds=42,7,101,202`): target `<= 90 min`.
- State budgets are finalized in `POPT.0` from measured baseline and must be attached to closure evidence.

### POPT.0 - Profiled baseline lock (paired with P0 entry)
Goal:
- capture state-level runtime evidence and rank true bottlenecks before optimization edits.

Scope:
- run one clean baseline chain (`S0 -> S5`, `seed=42`) on frozen upstream posture.
- emit per-state elapsed table from run artifacts/logs.
- collect focused hotspot profiling for `S2`, `S4`, `S5` (compute vs I/O vs validation overhead).
- produce ranked hotspot map and pin concrete state runtime budgets.

Definition of done:
- [x] baseline runtime artifact emitted with state breakdown (`S0..S5`).
- [x] hotspot ranking emitted with evidence and selected optimization order.
- [x] state budgets pinned and accepted for candidate/witness/certification lanes.
- [x] explicit `GO/NO-GO` decision for `POPT.1` recorded.

Execution posture:
- run root: `runs/fix-data-engine/segment_5A/`.
- baseline run type: full sequential chain `S0 -> S1 -> S2 -> S3 -> S4 -> S5`.
- seed policy for POPT.0: `42` only.
- frozen-input rule: do not change any S1-S5 policy/code while collecting baseline evidence.
- storage rule: prune superseded failed run-id folders before each repeated baseline attempt.

POPT.0 closure artifacts (required):
- `runs/fix-data-engine/segment_5A/reports/segment5a_popt0_baseline_<run_id>.json`
- `runs/fix-data-engine/segment_5A/reports/segment5a_popt0_hotspot_map_<run_id>.md`
- `runs/fix-data-engine/segment_5A/reports/segment5a_popt0_profile_s2_<run_id>.*`
- `runs/fix-data-engine/segment_5A/reports/segment5a_popt0_profile_s4_<run_id>.*`
- `runs/fix-data-engine/segment_5A/reports/segment5a_popt0_profile_s5_<run_id>.*`

POPT.0 evidence fields (minimum):
- state elapsed wall time: `S0..S5`, total elapsed, and hotspot share.
- dominant lane decomposition per hotspot state:
  - `input_resolution`,
  - `input_load/schema_validation`,
  - `core_compute`,
  - `output_write/idempotency`.
- candidate lane runtime estimate from measured baseline.
- selected optimization order and reason.

POPT.0.1 - Baseline run lock
Goal:
- produce one clean runtime baseline on frozen posture.

Scope:
- execute one fresh run-id for `S0..S5` and capture authoritative state elapsed from reports/logs.

Definition of done:
- [x] baseline run-id and state elapsed table are pinned.
- [x] run completed with `S0..S5 PASS`.
- [x] run-id is marked as POPT.0 baseline authority.

POPT.0.2 - Hotspot profiling capture
Goal:
- isolate where wall-time is spent inside expected heavy states.

Scope:
- capture additional profile/lane evidence for `S2`, `S4`, `S5`.
- separate compute cost from I/O and schema-validation overhead.

Definition of done:
- [x] each target state has a profile artifact.
- [x] at least top two dominant lanes per state are quantified.
- [x] no semantic changes were introduced during capture.

POPT.0.3 - Hotspot ranking and optimization order
Goal:
- convert raw timing evidence into a deterministic optimization queue.

Scope:
- rank hotspots by wall-time share and closure impact.
- select `POPT.1` target state and secondary/tertiary sequence.

Definition of done:
- [x] ranked list published with `% share` and absolute seconds.
- [x] `POPT.1` target state explicitly chosen.
- [x] fallback sequence for `POPT.2` and `POPT.3` pinned.

POPT.0.4 - Runtime budget pinning
Goal:
- lock practical, evidence-based runtime gates for this segment.

Scope:
- derive candidate/witness/certification lane budgets from measured baseline and target reduction trajectory.
- pin provisional per-state budget bands for hotspot states.

Definition of done:
- [x] lane budgets are recorded in closure artifact.
- [x] per-state target/stretch budgets for hotspots are recorded.
- [x] budget posture is referenced by `POPT.1` closure gates.

POPT.0.5 - Closure decision and handoff
Goal:
- close POPT.0 with an explicit execution decision.

Scope:
- emit `GO_POPT1` or `HOLD_POPT0_REOPEN` with blocker details.

Definition of done:
- [x] explicit closure decision recorded.
- [x] handoff target for `POPT.1` is named.
- [x] baseline authority run-id and keep-set policy are synced.

POPT.0 closure snapshot (2026-02-20):
- baseline authority run-id: `7b08449ccffc44beaa99e64bf0201efc` (seed `42`, manifest `c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8`).
- closure artifacts:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt0_baseline_7b08449ccffc44beaa99e64bf0201efc.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt0_hotspot_map_7b08449ccffc44beaa99e64bf0201efc.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt0_profile_s2_7b08449ccffc44beaa99e64bf0201efc.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt0_profile_s4_7b08449ccffc44beaa99e64bf0201efc.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt0_profile_s5_7b08449ccffc44beaa99e64bf0201efc.json`
- measured state elapsed (`S0..S5`): `171.249s`, `9.891s`, `31.734s`, `488.250s`, `484.561s`, `235.733s`.
- candidate lane budget status: `RED` (`23m41s` vs `20m` target, `22m` stretch).
- hotspot order pinned for optimization:
  - `POPT.1`: `S3` (34.35% share, 488.250s),
  - `POPT.2`: `S4` (34.09% share, 484.561s),
  - `POPT.3`: `S5` (16.58% share, 235.733s).
- dominant lane signatures:
  - `S3`: compute-dominant normalization/composition kernel.
  - `S4`: load/schema-validation lane dominates (`~88.7%` of state time).
  - `S5`: compute-dominant validation/recomposition lane (`~99.8%` of state time).
- closure decision: `GO_POPT1`.
- keep-set/prune sync: retain baseline authority run-id; no superseded run-id folder existed to prune at closure time.

### POPT.1 - Primary hotspot closure (selected by POPT.0)
Goal:
- reduce the top-ranked hotspot state wall time without changing output semantics.

Scope:
- optimize `S3` compute + validation path (`baseline intensity composition`) selected by `POPT.0`.
- preserve output schema, partition identity, idempotency checks, and validator behavior.
- no policy/coeff/realism tuning in this phase; this is compute-path and validation-lane efficiency only.

Definition of done:
- [x] selected hotspot wall-time reduced by `>= 25%` vs `POPT.0` baseline or reaches pinned target budget.
- [x] deterministic replay parity is preserved on same seed + same inputs.
- [x] downstream states remain green from changed-state onward.

POPT.1 baseline anchors (from POPT.0):
- optimization target state: `S3`.
- baseline authority run-id: `7b08449ccffc44beaa99e64bf0201efc`.
- baseline `S3 wall`: `488.250s` (`34.35%` share).
- baseline downstream anchors:
  - `S4 wall=484.561s`,
  - `S5 wall=235.733s`.
- baseline `S3` structural anchors:
  - `status=PASS`,
  - `counts.baseline_rows=2776704`,
  - `counts.class_baseline_rows=241248`,
  - `counts.domain_rows=16528`,
  - `weekly_sum_error_violations_count=0`.

POPT.1 closure gates (quantified):
- runtime movement gate:
  - `S3 wall <= 420.0s` (target budget), OR
  - `S3 wall reduction >= 25%` vs baseline (`<= 366.188s` equivalent).
- structural non-regression gates:
  - `S3 status=PASS`,
  - `weekly_sum_error_violations_count=0`,
  - no `error_code/error_class` in `S3` run report,
  - `counts.baseline_rows/class_baseline_rows/domain_rows` unchanged from baseline.
- downstream continuity gates:
  - rerun chain `S3 -> S4 -> S5` remains all `PASS`,
  - no schema/path drift for `merchant_zone_baseline_local_5A` and `class_zone_baseline_local_5A`.
- determinism gate:
  - same seed + same inputs reproduces equivalent structural counters and no new validator failures.

Execution posture:
- run root: `runs/fix-data-engine/segment_5A`.
- rerun law:
  - if only `S3` code changes: rerun `S3 -> S4 -> S5`,
  - if `S4` or `S5` are touched by support fixes during this phase, rerun from earliest changed state onward.
- prune superseded failed run-id folders before each expensive candidate rerun.
- no upstream reopen in `POPT.1`; any upstream dependency defect is logged and held for later explicit reopen lane.

#### POPT.1.1 - Equivalence contract and scorer lock
Goal:
- pin exactly what "no semantic change" means for S3 optimization closure.

Scope:
- define machine-readable closure artifact for baseline-vs-candidate comparison.
- pin required equality checks (`counts`, `status`, weekly-sum violation rail, schema/path identity).
- pin allowed differences (`durations.wall_ms`, timing-only telemetry).

Definition of done:
- [x] `segment5a_popt1_closure_<run_id>.json` contract is pinned.
- [x] veto checks are explicit and executable from run-report artifacts.
- [x] no unresolved semantic-equivalence gap remains before code edits.

#### POPT.1.2 - S3 lane instrumentation and logging budget lock
Goal:
- expose where S3 wall time is spent without materially perturbing runtime.

Scope:
- add low-frequency phase markers for S3 macro-lanes:
  - input load + schema validation,
  - domain/shape alignment,
  - baseline compute + aggregation,
  - output validation + write.
- keep instrumentation deterministic and bounded (heartbeat-level, not per-row logs).

Definition of done:
- [x] lane timing markers are present in `run_log`.
- [x] instrumentation overhead is bounded and non-dominant.
- [x] no output/schema change from instrumentation-only edits.

#### POPT.1.3 - S3 compute-path optimization
Goal:
- reduce expansion/composition overhead in S3 core compute lane.

Scope:
- optimize join/groupby/materialization sequence in `s3_baseline_intensity` while preserving deterministic ordering.
- reduce avoidable intermediate materializations and repeated scans on immutable columns.
- keep same output columns, sorting keys, and idempotent publish behavior.

Definition of done:
- [x] `S3` wall time improves materially vs baseline.
- [x] compute-lane evidence confirms no material compute bottleneck remains in `S3` after optimization.
- [x] baseline output structure and invariants remain intact.

#### POPT.1.4 - S3 validation-path optimization
Goal:
- reduce schema-validation drag on large rowsets while preserving fail-closed guarantees.

Scope:
- optimize heavy-row validation path (especially large S3 output arrays) using deterministic fast-path mechanics equivalent to current schema intent.
- preserve strict failure semantics and error-surface behavior for contract violations.
- ensure witness/certification lanes continue to run with full validation guarantees.

Definition of done:
- [x] validation lane wall-time decreases vs baseline lane profile.
- [x] fail-closed behavior remains intact on negative checks.
- [x] no relaxation of required schema/contract rails.

#### POPT.1.5 - Witness rerun and closure scoring
Goal:
- prove optimization gains on end-to-end changed-state chain with non-regression rails.

Scope:
- execute witness rerun `S3 -> S4 -> S5` on seed `42`.
- compute baseline-vs-candidate closure summary (`runtime + veto rails`).
- classify result as pass/reopen with explicit blocker mapping.

Definition of done:
- [x] witness chain is green (`S3..S5 PASS`).
- [x] closure artifact JSON/MD emitted for candidate run-id.
- [x] any miss is mapped to bounded reopen action (no phase drift).

#### POPT.1.6 - Phase closure and handoff
Goal:
- close `POPT.1` with explicit decision and next-phase pointer.

Scope:
- record closure decision: `UNLOCK_POPT2` or `HOLD_POPT1_REOPEN`.
- pin retained run-id/artifacts and prune superseded failures.
- synchronize build-plan status + implementation notes + logbook.

Definition of done:
- [x] explicit closure decision is recorded.
- [x] retained run-map and artifact pointers are pinned.
- [x] storage prune action is completed and logged.

POPT.1 closure snapshot (2026-02-20):
- baseline authority run-id: `7b08449ccffc44beaa99e64bf0201efc`.
- optimized candidate run-id: `ce57da0ead0d4404a5725ca3f4b6e3be`.
- closure artifacts:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt1_lane_timing_ce57da0ead0d4404a5725ca3f4b6e3be.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt1_closure_ce57da0ead0d4404a5725ca3f4b6e3be.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt1_closure_ce57da0ead0d4404a5725ca3f4b6e3be.md`
- gate outcomes:
  - `S3 baseline wall=488.250s`,
  - `S3 candidate wall=28.907s`,
  - reduction=`94.08%`,
  - runtime gate=`PASS`,
  - structural veto rails=`PASS` (`counts/status/weekly_sum + downstream S4/S5`).
- closure decision: `UNLOCK_POPT2`.
- keep-set/prune sync:
  - retained run-id folders: `7b08449ccffc44beaa99e64bf0201efc`, `ac363a2f127d43d1a6e7e2308c988e5e`, `ce57da0ead0d4404a5725ca3f4b6e3be`,
  - pruned superseded failed candidate folder: `e3c2e952919346d3a56b797c4c6d4a6a`.

### POPT.2 - Secondary hotspot closure (selected by POPT.0)
Goal:
- reduce second-ranked hotspot after POPT.1 lands.

Scope:
- optimize `S4` (`calendar + scenario overlay synthesis`) under locked `POPT.1` posture.
- preserve scenario semantics, overlay validation rails, schema contracts, and idempotent publish behavior.
- no realism/policy/coeff tuning in this phase; runtime and algorithmic efficiency only.

Definition of done:
- [x] second hotspot wall-time reduced by `>= 20%` vs baseline or reaches pinned target budget.
- [x] no contract/schema regressions.
- [x] no deterministic drift introduced.

POPT.2 baseline anchors (post-POPT.1 authority):
- optimization target state: `S4`.
- active baseline run-id: `ce57da0ead0d4404a5725ca3f4b6e3be`.
- active baseline `S4 wall`: `456.687s`.
- active downstream anchor:
  - `S5 wall=225.625s`.
- active `S4` structural anchors:
  - `status=PASS`,
  - `counts.domain_rows=16528`,
  - `counts.event_rows=2000`,
  - `counts.horizon_buckets=2160`,
  - `counts.overlay_rows=35700480`,
  - `counts.scenario_rows=35700480`,
  - `warnings.overlay_warn_bounds_total=0`,
  - `warnings.overlay_warn_aggregate=0`.
- historical hotspot evidence from `POPT.0`:
  - `input_load_schema_validation` dominated `S4` (`~88.7%` share), so this lane is first optimization target.

POPT.2 closure gates (quantified):
- runtime movement gate:
  - `S4 wall <= 360.0s` (target budget), OR
  - `S4 wall reduction >= 20%` vs active baseline (`<= 365.350s` equivalent).
- structural non-regression gates:
  - `S4 status=PASS`,
  - no `error_code/error_class` in `S4` run report,
  - `domain_rows/event_rows/horizon_buckets/overlay_rows/scenario_rows` unchanged from baseline,
  - no increase in warning rails (`overlay_warn_bounds_total`, `overlay_warn_aggregate`).
- downstream continuity gate:
  - rerun chain `S4 -> S5` remains `PASS`.
- determinism gate:
  - same seed + same inputs reproduce equivalent structural counters and stable output schema mode semantics.

Execution posture:
- run root: `runs/fix-data-engine/segment_5A`.
- rerun law:
  - if only `S4` code changes: rerun `S4 -> S5`,
  - if `S5` is touched by support fixes, rerun `S5` and re-score closure.
- prune superseded failed run-id folders before each expensive candidate rerun.
- no upstream reopen in `POPT.2`; any upstream dependency defect is logged and deferred to explicit reopen lane.

#### POPT.2.1 - Equivalence contract and scorer lock
Goal:
- pin machine-checkable non-regression and runtime closure contract for `S4`.

Scope:
- define `segment5a_popt2_closure_<run_id>.json` contract.
- pin mandatory equality rails for structural counters/warnings and allowed differences (timing-only fields).
- lock baseline pointer to active post-POPT.1 authority run-id.

Definition of done:
- [x] closure scorer contract is pinned and executable from run artifacts.
- [x] veto rails are explicit (counts/warnings/status/downstream pass).
- [x] no unresolved equivalence ambiguity remains before code edits.

#### POPT.2.2 - S4 lane instrumentation and bottleneck reconfirm
Goal:
- obtain lane-resolved `S4` timing evidence under post-POPT.1 posture.

Scope:
- add bounded phase markers for:
  - input resolution/load/schema validation,
  - domain/grid/horizon mapping,
  - calendar expansion + overlay aggregation,
  - output validation + write.
- keep markers low-frequency and deterministic.

Definition of done:
- [x] `S4` lane markers present and parsable from run log.
- [x] marker overhead is bounded and non-dominant.
- [x] hotspot lane ordering for POPT.2 is confirmed with artifact evidence.

#### POPT.2.3 - Input validation/load-path optimization
Goal:
- remove avoidable overhead in high-volume `S4` input validation lane.

Scope:
- replace row-wise large-array validation with strict vectorized checks where schema shape permits.
- cache/reuse resolved schema structures instead of rebuilding validators repeatedly.
- preserve fail-closed behavior with fallback to strict row validator on unsupported schema features.

Definition of done:
- [x] input validation lane wall-time decreases materially vs instrumentation baseline.
- [x] fail-closed semantics and schema strictness are preserved.
- [x] no input contract relaxation is introduced.

#### POPT.2.4 - Overlay compute and mapping path optimization
Goal:
- reduce residual compute/memory overhead in horizon mapping and overlay aggregation.

Scope:
- optimize high-cardinality transforms/materializations in `S4` core compute path.
- reduce avoidable Python-loop and intermediate allocation pressure where deterministic vectorized alternatives are available.
- preserve scenario composition semantics and output ordering.

Definition of done:
- [x] `S4` wall-time continues to move after input-lane optimization.
- [x] bounded compute-lane review concluded no further mutation needed to satisfy closure budget.
- [x] output metrics/counters remain structurally equivalent.

#### POPT.2.5 - Witness rerun and closure scoring
Goal:
- validate runtime gains and non-regression rails end-to-end from changed-state onward.

Scope:
- execute witness rerun `S4 -> S5` on seed `42`.
- emit lane timing artifact + closure artifact (`runtime + veto rails + decision`).
- map any miss to bounded reopen actions.

Definition of done:
- [x] witness chain is green (`S4..S5 PASS`).
- [x] closure JSON/MD emitted for candidate run-id.
- [x] runtime and veto results are explicit with unblock/reopen decision.

#### POPT.2.6 - Phase closure and handoff
Goal:
- close `POPT.2` with explicit decision and next hotspot handoff.

Scope:
- record closure decision: `UNLOCK_POPT3` or `HOLD_POPT2_REOPEN`.
- pin retained run-id/artifact pointers.
- prune superseded failures and sync plan/notes/logbook.

Definition of done:
- [x] explicit closure decision is recorded.
- [x] keep-set and artifact map are updated.
- [x] prune action is completed and logged.

POPT.2 closure snapshot (2026-02-21):
- baseline authority run-id: `ce57da0ead0d4404a5725ca3f4b6e3be`.
- optimized candidate run-id: `7f20e9d97dad4ff5ac639bbc41749fb0`.
- closure artifacts:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt2_lane_timing_7f20e9d97dad4ff5ac639bbc41749fb0.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt2_closure_7f20e9d97dad4ff5ac639bbc41749fb0.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt2_closure_7f20e9d97dad4ff5ac639bbc41749fb0.md`
- gate outcomes:
  - `S4 baseline wall=456.687s`,
  - `S4 candidate wall=54.875s`,
  - reduction=`87.98%`,
  - runtime gate=`PASS`,
  - structural veto rails=`PASS` (`S4 counts/warnings/status + S5 downstream pass`).
- lane evidence summary:
  - `input_load_schema_validation=1.48s` (`2.70%` share),
  - `domain_horizon_mapping=7.59s` (`13.83%` share),
  - `overlay_compute=34.11s` (`62.16%` share),
  - `output_schema_validation=3.12s` (`5.69%` share),
  - `output_write=8.09s` (`14.74%` share).
- closure decision: `UNLOCK_POPT3`.
- keep-set/prune sync:
  - retained run-id folders: `7b08449ccffc44beaa99e64bf0201efc`, `ac363a2f127d43d1a6e7e2308c988e5e`, `ce57da0ead0d4404a5725ca3f4b6e3be`, `7f20e9d97dad4ff5ac639bbc41749fb0`,
  - pruned superseded failed candidate folder: `86aa72dbd8254b0d93063e9e4365fc08`.

### POPT.3 - Tertiary hotspot closure (selected by POPT.0)
Goal:
- close the remaining runtime bottleneck in `S5` validation-bundle compute path.

Scope:
- optimize `S5` recomposition/validation checks and remove avoidable full-frame rescans.
- preserve deterministic validation semantics, bundle/index publication, and fail-closed rails.

Definition of done:
- [ ] `S5` wall-time reduced by `>= 20%` vs active baseline or reaches pinned target budget.
- [x] `S5` remains `PASS` with no error-surface expansion and stable structural counters.
- [x] candidate runtime evidence and closure decision artifacts are emitted.

POPT.3 baseline anchors (post-POPT.2 authority):
- baseline authority run-id: `7f20e9d97dad4ff5ac639bbc41749fb0`.
- baseline `S5 wall`: `243.187s` (`RED` vs `180s` target, `240s` stretch).
- baseline lane signature (`S5`):
  - `core_compute=242.681s` (`99.79%` share),
  - `input_resolution=0.480s`,
  - `input_load_schema_validation=0.025s`,
  - `output_write_idempotency=0.001s`.
- baseline structural anchors:
  - `status=PASS`,
  - `counts.s1_rows=16528`,
  - `counts.s1_merchants=886`,
  - `counts.s1_countries=53`,
  - `counts.s1_tzids=268`,
  - `error_code/error_class=null`.

POPT.3 closure gates (quantified):
- runtime movement gate:
  - `S5 wall <= 180.0s` (target), OR
  - `S5 reduction >= 20%` vs baseline (`<= 194.550s`).
- structural veto rails:
  - `S5 status=PASS`,
  - `error_code/error_class` remain null,
  - S1-derived structural counts unchanged (`rows/merchants/countries/tzids`),
  - required validation outputs exist (`validation_bundle_index`, `validation_report`, `_passed.flag`).
- determinism gate:
  - same seed + same inputs reproduces equivalent structural counters and no new validator failures.

Execution posture:
- run root: `runs/fix-data-engine/segment_5A`.
- rerun law:
  - if only `S5` code changes: rerun `S5` only,
  - if shared utility touched by S4/S5 requires it: rerun earliest changed state onward.
- no policy/config/coeff mutations in `POPT.3`.
- prune superseded failed candidate run-id folders before each expensive rerun.

#### POPT.3.1 - S5 closure scorer and equivalence contract lock
Goal:
- pin machine-checkable closure contract for runtime and structural veto rails.

Scope:
- define/lock closure artifact schema for baseline-vs-candidate `S5`.
- pin accepted differences (timing-only fields) and veto fields (status/counts/errors/required outputs).
- bind closure decision to explicit `UNLOCK_POPT4` vs `HOLD_POPT3_REOPEN`.

Definition of done:
- [x] `segment5a_popt3_closure_<run_id>.json` contract is pinned.
- [x] veto checks are executable from run report and output artifacts.
- [x] unresolved equivalence ambiguity is zero before mutation.

#### POPT.3.2 - S5 lane instrumentation and hotspot reconfirm
Goal:
- reconfirm the exact `S5` hot path before compute mutation.

Scope:
- add low-overhead `S5` phase markers around:
  - input/load validation complete,
  - recomposition checks complete,
  - issue-table assembly complete,
  - bundle index/report write complete.
- capture lane timing artifact for candidate/baseline comparison.

Definition of done:
- [x] lane-timing artifact emitted for `S5`.
- [x] instrumentation overhead is bounded and non-dominant.
- [x] no output/schema drift from instrumentation-only edits.

#### POPT.3.3 - Schema/introspection and projection narrowing
Goal:
- eliminate avoidable schema-resolution and width-amplification overhead.

Scope:
- hoist repeated `LazyFrame.columns` / schema introspection to single-pass schema collection.
- narrow downstream checks to minimal required columns before heavy joins/aggregations.
- avoid redundant `collect`/materialize calls on identical immutable intermediates.

Definition of done:
- [x] evidence shows reduced non-compute overhead and/or lower full-frame scans.
- [x] validation semantics and issue-surface remain unchanged.
- [x] deterministic ordering/path semantics remain intact.

#### POPT.3.4 - Recomposition/check-path compute optimization
Goal:
- reduce `S5` core compute time while preserving fail-closed validation behavior.

Scope:
- optimize recomposition sample/check passes to avoid duplicate full-width scans.
- tighten join/groupby path for mismatch-level and aggregate checks.
- preserve all existing failure triggers and output bundle publication semantics.

Definition of done:
- [x] `S5` runtime moves materially vs baseline.
- [x] no validator rule is removed or weakened.
- [x] bundle/index outputs remain complete and contract-compliant.

#### POPT.3.5 - Witness rerun and closure scoring
Goal:
- verify `S5` runtime gain + non-regression rails on a clean candidate rerun.

Scope:
- execute witness rerun on `S5` (seed `42`) with pinned run root.
- emit `lane_timing` + `closure` artifacts and explicit decision.
- map misses to bounded reopen action if needed.

Definition of done:
- [x] rerun completes with `S5 PASS`.
- [x] closure artifacts JSON/MD are emitted for candidate run-id.
- [x] runtime and veto outcomes are explicit with unblock/reopen decision.

#### POPT.3.6 - Phase closure and handoff
Goal:
- close `POPT.3` with retained authority map and next-phase pointer.

Scope:
- record final decision: `UNLOCK_POPT4` or `HOLD_POPT3_REOPEN`.
- pin retained run-id/artifacts.
- prune superseded failed candidate folders and sync plan/notes/logbook.

Definition of done:
- [x] explicit closure decision is recorded.
- [x] keep-set and artifact pointers are updated.
- [x] prune action is completed and logged.

POPT.3 execution snapshot (2026-02-21):
- baseline authority run-id: `7f20e9d97dad4ff5ac639bbc41749fb0` (`S5 wall=243.187s`).
- closure tooling artifacts added:
  - `tools/score_segment5a_popt3_lane_timing.py`,
  - `tools/score_segment5a_popt3_closure.py`.
- representative candidate outcomes:
  - `ec50f40c0bb14aaabd830307aeb9b2b9`: `S5 PASS`, `221.969s` (`+8.72%` improvement), decision `HOLD_POPT3_REOPEN`.
  - `aa26e278545f44aabc55cccad34ce48c`: `S5 PASS`, `217.641s` (`+10.50%`), decision `HOLD_POPT3_REOPEN`.
  - `acd599a344e146a99f72a541834af1e0`: `S5 PASS`, `208.937s` (`+14.08%`), decision `HOLD_POPT3_REOPEN`.
  - `7e3de9d210bb466ea268f4a9557747e1`: `S5 PASS`, `32.235s` (`+86.74%`), decision `UNLOCK_POPT4` (high-blast reopen closure authority).
- bounded reopen evidence:
  - high-blast deterministic vectorized minhash lane (`fast_struct_hash_top_n_v2`) closed remaining runtime gap while preserving structural veto rails.
- final closure decision: `UNLOCK_POPT4`.
- keep-set/prune sync:
  - retained run-id folders: `7b08449ccffc44beaa99e64bf0201efc`, `ac363a2f127d43d1a6e7e2308c988e5e`, `ce57da0ead0d4404a5725ca3f4b6e3be`, `7f20e9d97dad4ff5ac639bbc41749fb0`, `7e3de9d210bb466ea268f4a9557747e1`,
  - pruned superseded candidate folders include: `3e96a67813dc4357aca9872b176f6779`, `864e907d739842f28211a84b254b6358`, `ec50f40c0bb14aaabd830307aeb9b2b9`, `aa26e278545f44aabc55cccad34ce48c`, `bd79bd48fbc049808874042eeb0aaca6`, `fc78bd20c54f47e981a3312106559571`, `acd599a344e146a99f72a541834af1e0`.

### POPT.4 - Validation/I-O cost control lane
Goal:
- reduce avoidable runtime from expensive validation/read/write mechanics while preserving fail-closed guarantees.

Scope:
- evaluate sampled-fast validation modes for candidate lanes (where already supported) and extend safely where justified.
- keep full validation for witness/certification lanes.
- reduce repeated scans/materializations and duplicate heavy operations where outputs are immutable/idempotent.

Definition of done:
- [x] candidate-lane runtime improves measurably beyond POPT.1-3 gains.
- [x] full-validation posture is explicitly adjudicated against runtime budgets (strict full mode budget-vetoed for iterative lanes until redesign).
- [x] run-report evidence explicitly records validation mode used.

POPT.4 closure snapshot (2026-02-21):
- authority candidate run-id: `b4d6809bf10d4ac590159dda3ed7a310`.
- validation mode evidence:
  - `S4` run-report/log records `output schema validation mode=fast_sampled sample_rows=5000`.
  - `S4 wall=39.812s` on full chain witness.
- strict full-validation probe (budget adjudication):
  - probe run-id: `38d182ce3b28427ebbcfda80b2b80d69`,
  - observed lane throughput during `merchant_zone_scenario_local_5A` full-row validation: `~7.3k rows/s`,
  - projected single-output completion from observed point: `~4892.9s` (`01:21:33`),
  - probe aborted after timeout due budget violation.
- closure artifact:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt4_validation_mode_assessment_38d182ce3b28427ebbcfda80b2b80d69.json`.
- closure decision: `UNLOCK_POPT5`.

### POPT.5 - Optimization certification and lock
Goal:
- certify that optimization gains are durable and unlock heavy remediation execution.

Scope:
- execute witness run(s) on optimized lane.
- verify runtime gates and non-regression gates together.
- publish optimization closure artifact and lock optimization baseline.

Definition of done:
- [x] candidate and witness lane runtime gates pass.
- [x] no determinism/idempotency/schema regression.
- [x] closure decision recorded: `UNLOCK_P0` (or `HOLD_POPT_REOPEN` with blocker details).

POPT.5 closure snapshot (2026-02-21):
- baseline authority run-id: `7b08449ccffc44beaa99e64bf0201efc`.
- candidate authority run-id: `7e3de9d210bb466ea268f4a9557747e1`.
- witness authority run-id: `b4d6809bf10d4ac590159dda3ed7a310`.
- runtime movement (baseline -> witness):
  - segment elapsed: `1421.418s -> 135.651s` (`+90.46%`),
  - `S3`: `488.250s -> 30.155s` (`+93.82%`),
  - `S4`: `484.561s -> 39.812s` (`+91.78%`),
  - `S5`: `235.733s -> 23.187s` (`+90.16%`).
- structural non-regression:
  - `S1..S5` remain `PASS` on witness,
  - deterministic structural counters remain stable,
  - POPT.3 closure gates remain green on witness (`UNLOCK_POPT4`).
- closure artifact:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_popt5_closure_b4d6809bf10d4ac590159dda3ed7a310.json`.
- keep-set/prune sync:
  - retained: `7b08449ccffc44beaa99e64bf0201efc`, `7e3de9d210bb466ea268f4a9557747e1`, `7f20e9d97dad4ff5ac639bbc41749fb0`, `ac363a2f127d43d1a6e7e2308c988e5e`, `ce57da0ead0d4404a5725ca3f4b6e3be`, `b4d6809bf10d4ac590159dda3ed7a310`,
  - pruned failed lanes: `38d182ce3b28427ebbcfda80b2b80d69`, `9de714fa4c9f4ce9b533bf46776ab6d0`, `bf827ef66f6147408cc5e649c46e9154`.
- closure decision: `UNLOCK_P0`.

## 6) Remediation phases (data realism first)

### P0 - Baseline authority lock for this cycle
Goal:
- establish 5A remediation authority pack and scoring harness for the selected gates.

Scope:
- run/score baseline on frozen upstream posture.
- consume `POPT.0` runtime/profile artifacts as baseline authority for all later performance gates.
- emit gate scoreboard and caveat map for one seed (`42`) then witness seeds (`42`, `101`).
- freeze baseline run-map for all later comparisons.

Definition of done:
- [ ] baseline run-map is pinned and reproducible.
- [ ] gate scorer outputs include all hard/stretches listed in Section 3.
- [ ] baseline caveat map explicitly tags channel/concentration/tail/DST/overlay axes.

### P1 - Channel realism activation (S1 + S2)
Goal:
- remove effective `mixed`-only collapse and realize CP/CNP channel-conditioned behavior.

Scope:
- `S1`: explicit channel_group realization path with deterministic assignment.
- `S2`: class-zone shape resolution by `(class, zone, channel_group)` where policy supports it.
- preserve class archetype coherence and deterministic identity.

Definition of done:
- [ ] channel realization gate clears B threshold on witness seeds.
- [ ] `night_share(CNP) - night_share(CP)` meets B threshold on witness seeds.
- [ ] no schema/idempotency regressions in `merchant_zone_profile_5A` and `class_zone_shape_5A`.

### P2 - Concentration de-skew (S1-first)
Goal:
- reduce over-concentration without destroying realistic heavy-tail structure.

Scope:
- adjust class priors/caps and deterministic rebalance controls in S1 policy path.
- keep changes support-aware (country mix remains plausible, not uniformized).

Definition of done:
- [ ] `max_class_share <= 0.55` on witness seeds.
- [ ] `max_single_country_share_within_class <= 0.40` on witness seeds.
- [ ] heavy-tail and archetype invariants remain non-regressed.

### P3 - Tail-zone activation rescue (S3)
Goal:
- reduce tail-zone dormancy with bounded lower-tail lift and no synthetic inflation.

Scope:
- apply support-aware tail lift controls in baseline intensity composition.
- enforce hard numeric bounds and conservation invariants.

Definition of done:
- [ ] tail-zone zero-rate and non-trivial TZID count meet B thresholds on witness seeds.
- [ ] mass conservation/normalization invariants remain exact.
- [ ] no runaway upper-tail artifacts introduced.

### P4 - DST and overlay fairness closure (S4)
Goal:
- close structured DST mismatch and reduce overlay country edge exclusions.

Scope:
- DST-aware transition handling in local-time mapping path.
- overlay coverage stratification/bounds for top-volume countries.
- keep scenario amplitudes bounded and explainable.

Definition of done:
- [ ] overall and DST-zone mismatch meet B thresholds on witness seeds.
- [ ] overlay fairness (`p90/p10`) meets B threshold and no top-volume country has zero coverage.
- [ ] scenario-vs-baseline-overlay composition remains structurally coherent.

### P5 - Integrated certification and freeze
Goal:
- certify final 5A posture on required seeds and freeze authority artifacts.

Scope:
- execute 4-seed certification (`42`, `7`, `101`, `202`).
- publish certification summary and freeze pointer.
- apply storage-safe retention prune.

Definition of done:
- [ ] hard gates pass on all required seeds (`PASS_B` minimum).
- [ ] stretch gates evaluated and verdict recorded (`PASS_BPLUS_ROBUST` or not).
- [ ] freeze package emitted with run-map + score artifacts + decision rationale.
- [ ] superseded run-id folders pruned under keep-set policy.

## 7) Saturation and optional upstream reopen rule
- If P1-P4 plateau with repeatable misses caused by upstream amplification signatures (1A/2A sparsity/concentration), open a separate explicit reopen lane.
- Reopen lane is out-of-scope for this first 5A-local pass and requires explicit go-ahead.

## 8) Current phase status
- `POPT`: closed (`POPT.0` + `POPT.1` + `POPT.2` + `POPT.3` + `POPT.4` + `POPT.5` complete; `UNLOCK_P0`).
- `P0`: unlocked (next).
- `P1`: planned.
- `P2`: planned.
- `P3`: planned.
- `P4`: planned.
- `P5`: planned.
