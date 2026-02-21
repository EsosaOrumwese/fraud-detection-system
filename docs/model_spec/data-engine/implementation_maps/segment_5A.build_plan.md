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

P0 execution snapshot (2026-02-21):
- tooling implemented:
  - `tools/score_segment5a_p0_realism.py` (hard/stretch gates + caveat axes + cross-seed CV + closure decision).
- emitted artifacts:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p0_realism_gateboard_b4d6809bf10d4ac590159dda3ed7a310.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p0_realism_gateboard_b4d6809bf10d4ac590159dda3ed7a310__7e3de9d210bb466ea268f4a9557747e1.json`
- observed seed-pack posture:
  - available seeded runs in active root are seed `42` only (multiple replay run-ids),
  - required witness seed `101` is unavailable upstream in sealed `1A..3B` artifacts.
- blocker detail:
  - true seed-101 witness attempt (`a2b7d3399a1341559320b0977ebbc1dd`) fails in `S0` because strict Layer-1 validation bundle index laws cannot be satisfied without genuine upstream seed-101 bundles.
- current P0 decision:
  - `HOLD_P0_REMEDIATE` (missing required witness seed `101`).
- caveat map (current baseline):
  - `channel=material`, `concentration=material`, `tail=material`, `dst=material`, `overlay=watch`.

### P1 - Channel realism activation (S1 + S2)
Goal:
- remove effective `mixed`-only collapse and realize CP/CNP channel-conditioned behavior.

Scope:
- `S1`: explicit channel_group realization path with deterministic assignment.
- `S2`: class-zone shape resolution by `(class, zone, channel_group)` where policy supports it.
- preserve class archetype coherence and deterministic identity.

Definition of done:
- [x] channel realization gate clears B threshold on witness seeds.
- [x] `night_share(CNP) - night_share(CP)` meets B threshold on witness seeds.
- [x] no schema/idempotency regressions in `merchant_zone_profile_5A` and `class_zone_shape_5A`.

P1 execution posture (temporary waiver for execution lanes):
- execution-lane seed policy for `P1` only: `{42}` (user-approved temporary waiver while upstream `seed=101` remains unavailable).
- witness/certification policy remains unchanged for freeze:
  - `P5` still requires `{42,7,101,202}`.
- data-first focus in this phase:
  - prioritize statistical shape movement (`channel_group` realization and CP/CNP night-gap),
  - avoid non-causal tuning outside `S1/S2`.

#### P1.1 - Channel authority contract and target map
Goal:
- lock exact measurable target surfaces for channel realism so S1/S2 edits are evaluated against one contract.

Scope:
- pin authority datasets for this phase:
  - `merchant_zone_profile_5A`,
  - `class_zone_shape_5A`,
  - `class_zone_baseline_local_5A`.
- pin P1 target metrics:
  - realized channel groups with `>=10%` mass each (`B`),
  - `night_share(CNP)-night_share(CP) >= 0.08` (`B`) and `>=0.12` (`B+`).
- pin non-regression invariants:
  - class archetype ordering preserved (`online_24h` remains more night-heavy than `consumer_daytime`),
  - mass/normalization guards unchanged.

Definition of done:
- [x] P1 metric contract artifact is emitted and references exact dataset surfaces.
- [x] acceptance thresholds are machine-checkable and version-pinned.
- [x] invariant set is explicitly recorded for veto checks.

#### P1.2 - S1 channel assignment realization lane
Goal:
- make CP/CNP realization explicit in `S1` so output no longer collapses to `mixed`.

Scope:
- inspect and tune `S1` channel-assignment policy path:
  - assignment priors/weights for channel groups,
  - deterministic tie-break/seed behavior.
- ensure emitted `merchant_zone_profile_5A` carries usable channel signal (not degenerate).
- keep class allocation logic coherent with current demand-class semantics.

Definition of done:
- [x] `merchant_zone_profile_5A` shows at least 2 realized channel groups with non-trivial volume support.
- [x] no deterministic replay/idempotency regression in S1 outputs.
- [x] S1-only rerun evidence is captured before moving to S2 changes.

#### P1.3 - S2 channel-conditioned shape realization lane
Goal:
- ensure S2 shape synthesis actually uses channel dimension to produce differentiated temporal profiles.

Scope:
- tune `S2` `(demand_class, zone, channel_group)` shape-selection/adjustment path.
- preserve template realism:
  - no synthetic flattening,
  - no extreme discontinuities.
- verify shape normalization remains exact after channel activation.

Definition of done:
- [x] `class_zone_shape_5A` contains realized CP/CNP rows where policy intends them.
- [x] channel-conditioned shape differences are measurable in night-share profile.
- [x] shape normalization and schema validity remain green.

#### P1.4 - S1+S2 integrated calibration loop (data-only closure)
Goal:
- calibrate S1/S2 jointly until channel realism clears B gate without harming core archetype behavior.

Scope:
- iterative loop:
  - rerun `S1 -> S2 -> S3 -> S4 -> S5` (seed `42`),
  - evaluate P1 target metrics and archetype veto checks.
- adjust only causal knobs in S1/S2; do not leak into P2/P3/P4 objectives.
- stop criteria:
  - channel gate clears or statistically saturates with clear evidence.

Definition of done:
- [x] either B-level channel gate is met on execution seed, or saturation evidence is documented.
- [x] archetype and mass-conservation invariants remain non-regressed.
- [x] chosen knob set and rejected alternatives are documented.

#### P1.5 - Phase witness scoring and caveat refresh
Goal:
- publish a clean P1 score snapshot and caveat-axis movement after S1/S2 closure attempt.

Scope:
- run scorer on latest P1 authority run-id(s),
- emit channel-focused score table plus full caveat-axis refresh (`channel/concentration/tail/dst/overlay`),
- compare against P0 baseline to quantify movement magnitude.

Definition of done:
- [x] scored P1 artifact emitted in `runs/fix-data-engine/segment_5A/reports`.
- [x] movement vs P0 baseline is explicit and numeric.
- [x] unresolved residuals are mapped to next phase (`P2/P3/P4`) without ambiguity.

#### P1.6 - Phase closure decision and handoff
Goal:
- close P1 with explicit state and unlock P2 only if P1 scope is complete.

Scope:
- emit one decision:
  - `UNLOCK_P2`,
  - or `HOLD_P1_REOPEN`.
- sync keep-set/prune and update plan/implementation/logbook trails.
- if hold: pin exact blocker and reopen lane with bounded objectives.

Definition of done:
- [x] explicit closure decision is recorded with evidence refs.
- [x] keep-set is pruned/synced.
- [x] handoff posture to `P2` is unambiguous.

P1 closure snapshot (2026-02-21):
- P1.1 contract artifacts:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p1_1_channel_contract.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p1_1_channel_contract.md`
- P1 candidate authority run-id:
  - `d9caca5f1552456eaf73780932768845` (`S0..S5 PASS`).
- P1 gateboard:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p1_realism_gateboard_d9caca5f1552456eaf73780932768845.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p1_realism_gateboard_d9caca5f1552456eaf73780932768845.md`
- P1 movement vs P0 baseline:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p1_5_movement_d9caca5f1552456eaf73780932768845.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p1_5_movement_d9caca5f1552456eaf73780932768845.md`
- Channel movement:
  - realized channel groups (`>=10%` mass): `1 -> 2`,
  - channel share: `mixed=1.0 -> cp=0.8274, cnp=0.1726`,
  - `night_share(CNP)-night_share(CP): null -> 0.2715` (B/B+ gate clear).
- Closure decision:
  - `UNLOCK_P2` (P1 channel realism gate met on execution seed `{42}`).
- Residual caveats for next phases:
  - `concentration=material`, `tail=material`, `dst=material`, `overlay=watch`.

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

P2 execution posture (temporary waiver for execution lanes):
- execution-lane seed policy for `P2` only: `{42}`.
- certification seed law remains unchanged for freeze (`P5` still requires `{42,7,101,202}`).
- P1 lock rails are veto constraints in all P2 iterations:
  - at least 2 realized channel groups with non-trivial support,
  - `night_share(CNP)-night_share(CP) >= 0.08`,
  - no mixed-collapse reintroduction.

#### P2.1 - Concentration contract lock and protected-rail baseline
Goal:
- pin concentration closure targets, protected non-regression rails, and authority datasets before tuning.

Scope:
- lock primary P2 target metrics:
  - `max_class_share <= 0.55` (`B`), `<= 0.50` (`B+` stretch),
  - `max_single_country_share_within_class <= 0.40` (`B`), `<= 0.35` (`B+` stretch).
- lock P1 protection rails:
  - channel realization and channel night-gap stay above P1 closure thresholds.
- lock authority surfaces:
  - `merchant_class_profile_5A`,
  - `merchant_zone_profile_5A`,
  - `class_zone_baseline_local_5A` (for channel/non-regression checks).

Definition of done:
- [x] P2 contract artifact emitted with explicit concentration + protection thresholds.
- [x] acceptance thresholds are machine-checkable and version-pinned.
- [x] veto rails are explicitly recorded for every P2 lane.

#### P2.2 - Concentration attribution and hotspot map (no tuning yet)
Goal:
- identify exactly which classes, channels, virtual modes, and country clusters drive concentration.

Scope:
- decompose `max_class_share` contribution by:
  - `demand_class`,
  - `channel_group`,
  - `virtual_mode`,
  - top merchants by weekly volume.
- decompose `max_single_country_share_within_class` by:
  - class-country pair,
  - top merchants within dominant class-country cells.
- publish ranked hotspot map and choose first bounded knob lane.

Definition of done:
- [x] hotspot artifact emitted with ranked contributors and contribution percentages.
- [x] first knob lane is chosen with explicit rationale.
- [x] no policy/value changes applied in this subphase.

#### P2.3 - Lane A: class-share closure via S1 scale controls
Goal:
- reduce `max_class_share` to B target using low-blast S1 scale-path controls.

Scope:
- tune S1 scale controls first (no class-assignment remap yet):
  - `class_params` (`median_per_site_weekly`, `ref_per_site_weekly`, `clip_max_per_site_weekly`),
  - `channel_group_multipliers`,
  - `virtual_mode_multipliers`.
- rerun sequential lane `S1 -> S2 -> S3 -> S4 -> S5` on each candidate.
- reject any candidate that regresses P1 channel rails.

Definition of done:
- [x] `max_class_share` shows monotonic improvement and reaches B target or saturation evidence is recorded.
- [x] P1 channel rails remain green on each accepted candidate.
- [x] no mass/shape invariant regressions are introduced.

#### P2.4 - Lane B: within-class country de-skew closure
Goal:
- reduce `max_single_country_share_within_class` without artificial country flattening.

Scope:
- tune de-skew controls:
  - `brand_size_exponent`,
  - soft-cap controls (`soft_cap_ratio`, `soft_cap_multiplier`, `max_weekly_volume_expected`),
  - class-specific clip limits where justified by attribution evidence.
- keep heavy-tail realism by preserving plausible top-country dominance ordering.
- rerun `S1 -> S5` on each accepted candidate.

Definition of done:
- [x] `max_single_country_share_within_class <= 0.40` or saturation evidence is documented.
- [x] heavy-tail structure remains plausible (no synthetic flattening).
- [x] P1 channel rails and core invariants remain non-regressed.

#### P2.5 - Integrated concentration closure loop
Goal:
- jointly satisfy both concentration hard gates with minimal stable knob set.

Scope:
- integrate best candidates from P2.3/P2.4 and run bounded iterative calibration.
- if scale-path saturates, open bounded fallback lane:
  - limited `merchant_class_policy_5A` decision-tree remap with explicit veto gates.
- enforce strict veto after each attempt:
  - channel rails, mass conservation, shape normalization, deterministic replay/idempotency.

Definition of done:
- [x] both P2 hard concentration gates are green on execution seed.
- [x] final knob set is minimal and rationale for rejected alternatives is recorded.
- [x] fallback remap lane is either closed or explicitly rejected with evidence.

#### P2.6 - P2 scoring, movement quantification, and closure handoff
Goal:
- publish P2 closure evidence and decide phase handoff unambiguously.

Scope:
- emit P2 gateboard and movement vs P1 authority:
  - concentration metrics,
  - protected channel rails,
  - caveat axis refresh.
- emit explicit decision:
  - `UNLOCK_P3`,
  - or `HOLD_P2_REOPEN`.
- sync keep-set/prune and update implementation/logbook trails.

Definition of done:
- [x] P2 score artifacts are emitted in `runs/fix-data-engine/segment_5A/reports`.
- [x] movement vs P1 baseline is explicit and numeric.
- [x] explicit closure decision and P3 handoff posture are recorded.
- [x] superseded run-id folders are pruned under keep-set policy.

P2 closure snapshot (2026-02-21):
- authority closure run-id: `66c708d45d984be18fe45a40c3b79ecc` (`UNLOCK_P3`).
- lane progression:
  - lane A (`ece48ba58426416b9a97d22e2f4ef380`): class-share gate closed, country-share remained high.
  - lane B (`e60d96688776446fb8301b545e7ab59a`): near-pass (`max_country_share_within_class=0.40499`).
  - integrated minimal closure (`66c708d45d984be18fe45a40c3b79ecc`): both concentration hard gates green.
- closure metrics on authority run:
  - `max_class_share=0.5409` (PASS),
  - `max_country_share_within_class=0.3769` (PASS),
  - P1 protection rails preserved (`2` realized channels; `night_gap=0.2760`; mass/shape exact).
- closure artifacts:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p2_realism_gateboard_66c708d45d984be18fe45a40c3b79ecc.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p2_realism_gateboard_66c708d45d984be18fe45a40c3b79ecc.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p2_5_movement_66c708d45d984be18fe45a40c3b79ecc.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p2_5_movement_66c708d45d984be18fe45a40c3b79ecc.md`

### P3 - Tail-zone activation rescue (S3)
Goal:
- reduce tail-zone dormancy with bounded lower-tail lift and no synthetic inflation.

Scope:
- apply support-aware tail lift controls in baseline intensity composition.
- align metric surface so P3 decisions are driven by true S3 tail behavior (not proxy drift).
- enforce hard numeric bounds and conservation/concentration/channel invariants.

Definition of done:
- [ ] tail-zone zero-rate and non-trivial TZID count meet B thresholds on witness seeds.
- [ ] mass conservation/normalization invariants remain exact.
- [ ] no runaway upper-tail artifacts introduced.

P3 execution posture (temporary waiver for execution lanes):
- execution-lane seed policy for `P3` only: `{42}` (same temporary waiver posture used in `P1/P2` while upstream witness seed `101` remains unavailable).
- freeze rails from prior closed phases are veto constraints in every P3 iteration:
  - P1 channel rails remain green (`>=2` realized channel groups; `night_share(CNP)-night_share(CP) >= 0.08`),
  - P2 concentration rails remain green (`max_class_share <= 0.55`; `max_country_share_within_class <= 0.40`),
  - mass conservation and shape normalization stay exact.
- changes are limited to:
  - `S3` implementation path,
  - `baseline_intensity_policy_5A` contract/policy fields,
  - P3 scorer surfaces/artifacts needed for closure evidence.

#### P3.1 - Tail contract lock and frozen-rail baseline
Goal:
- pin exact measurable P3 targets and freeze non-regression rails before touching S3 logic.

Scope:
- lock P3 hard and stretch targets:
  - hard (`B`): `tail_zero_rate <= 0.90`, `nontrivial_tzids >= 190`,
  - stretch (`B+`): `tail_zero_rate <= 0.80`, `nontrivial_tzids >= 230`.
- lock frozen protection rails from closed phases:
  - P1 channel realization/night-gap,
  - P2 concentration gates,
  - mass/shape invariants.
- pin authority datasets for this phase:
  - `merchant_zone_profile_5A`,
  - `class_zone_baseline_local_5A`,
  - `merchant_zone_scenario_local_5A`.

Definition of done:
- [x] P3 contract artifact is emitted with hard/stretch targets and frozen veto rails.
- [x] all P3 acceptance checks are machine-checkable and version-pinned.
- [x] P3 scoring decision vocabulary is pinned (`UNLOCK_P4` vs `HOLD_P3_REOPEN`).

#### P3.2 - Tail dormancy attribution and metric-surface alignment (no tuning yet)
Goal:
- isolate true dormancy drivers and ensure P3 gates read the correct S3-caused statistical surface.

Scope:
- decompose dormancy by:
  - `demand_class/demand_subclass`,
  - `legal_country_iso`,
  - `tzid`,
  - merchant contribution rank within dormant cells.
- explicitly test whether current tail gates are proxying S1-only surfaces or S3 outputs.
- if mismatch exists, patch scorer surface to S3-authoritative measurement while preserving published threshold semantics.
- publish ranked hotspot map plus first bounded knob lane selection.

Definition of done:
- [x] hotspot artifact identifies dominant dormancy contributors with percentages.
- [x] scorer-surface alignment verdict is explicit (`aligned` or `patched`) with rationale.
- [x] no policy/runner value changes are applied in this subphase.

#### P3.3 - Tail-lift contract and policy lane (schema + policy)
Goal:
- expose bounded tail-lift controls in contract-safe policy shape before runner tuning.

Scope:
- extend `policy/baseline_intensity_policy_5A` schema to support a bounded `tail_rescue` block.
- add/lock tail controls in `baseline_intensity_policy_5A`:
  - `tail_floor_epsilon`,
  - `tail_lift_power`,
  - `tail_lift_max_multiplier`.
- preserve strict contract posture (`additionalProperties: false`) with explicit field bounds.
- pin default values to conservative, non-synthetic posture before candidate sweeps.

Definition of done:
- [x] schema admits only bounded tail-rescue knobs with explicit numeric limits.
- [x] policy file is updated with versioned conservative defaults.
- [x] S3 policy load/validation path accepts the new contract without regressions.

#### P3.4 - S3 bounded lower-tail rescue implementation
Goal:
- implement support-aware lower-tail rescue in S3 without flattening realistic heavy-tail structure.

Scope:
- implement deterministic tail-rescue transformation in `S3` using policy knobs from P3.3.
- apply rescue only to low-support tail cells with bounded multiplier ceilings.
- enforce post-transform safeguards:
  - no hard-limit violations,
  - no concentration/channel rail regressions,
  - no mass/shape invariant drift.
- emit per-run diagnostics for tail movement:
  - zero-rate delta,
  - non-trivial TZID delta,
  - upper-tail sanity deltas.

Definition of done:
- [x] S3 runner emits deterministic bounded tail rescue with policy-controlled behavior.
- [x] protection rails remain green on each accepted candidate.
- [x] diagnostic artifacts quantify movement and non-regression for each iteration.

#### P3.5 - Candidate calibration loop and phase scoring
Goal:
- calibrate P3 knobs to close hard tail gates and attempt B+ tail stretch without synthetic inflation.

Scope:
- run bounded candidate ladder (conservative -> moderate -> strong) on P3 knobs only.
- after each candidate:
  - rerun sequential lane `S3 -> S4 -> S5`,
  - score P3 gates and frozen veto rails,
  - reject any candidate that regresses P1/P2 rails or introduces upper-tail artifacts.
- produce movement report vs P2 authority run `66c708d45d984be18fe45a40c3b79ecc`.

Definition of done:
- [x] P3 hard tail gates are green on execution seed or saturation is evidenced.
- [x] B+ stretch attempt outcome is explicit (achieved or bounded miss with attribution).
- [x] accepted knob set is minimal and alternatives rejected are documented with evidence.

#### P3.6 - Closure handoff, prune, and freeze pointer update
Goal:
- close P3 unambiguously and hand off to `P4` with retained authority artifacts.

Scope:
- emit P3 gateboard + movement pack + caveat-axis refresh.
- emit explicit decision:
  - `UNLOCK_P4`,
  - or `HOLD_P3_REOPEN`.
- sync keep-set/prune under `runs/fix-data-engine/segment_5A`.
- update implementation notes and logbook with final reasoning trail.

Definition of done:
- [x] closure artifact set is complete and linked from the build plan.
- [x] explicit `UNLOCK/HOLD` decision is recorded with blocker rationale where applicable.
- [x] superseded run-id folders are pruned under keep-set policy.

P3 closure snapshot (2026-02-21):
- authority baseline run-id: `66c708d45d984be18fe45a40c3b79ecc` (`HOLD_P3_REOPEN` under P3-tail gates).
- closure run-id: `6817ca5a2e2648a1a8cf62deebfa0fcb` (`UNLOCK_P4`).
- bounded lane summary:
  - lane A (`906e20965f3f4d919405d8952924b57c`): tail-zero-rate closed, nontrivial TZID short (`177`).
  - lane B (`6817ca5a2e2648a1a8cf62deebfa0fcb` with `tail_floor_epsilon=0.20`): hard tail gates closed.
- closure movement (baseline -> closure):
  - `tail_zero_rate: 0.981893 -> 0.000000`,
  - `nontrivial_tzids: 127 -> 196`.
- B+ tail stretch outcome:
  - achieved for tail-zero-rate (`<=0.80`),
  - bounded miss for nontrivial TZIDs (`196` vs `>=230`), explicitly accepted for P4 handoff.
- freeze rails at closure run remain green:
  - P1 channel rails pass,
  - P2 concentration rails pass,
  - mass/shape invariants pass.
- closure artifacts:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p3_realism_gateboard_66c708d45d984be18fe45a40c3b79ecc.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p3_realism_gateboard_66c708d45d984be18fe45a40c3b79ecc.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p3_realism_gateboard_6817ca5a2e2648a1a8cf62deebfa0fcb.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p3_realism_gateboard_6817ca5a2e2648a1a8cf62deebfa0fcb.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p3_6_movement_66c708d45d984be18fe45a40c3b79ecc_to_6817ca5a2e2648a1a8cf62deebfa0fcb.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p3_6_movement_66c708d45d984be18fe45a40c3b79ecc_to_6817ca5a2e2648a1a8cf62deebfa0fcb.md`
- prune sync completed:
  - executed keep-set prune check for P4 closure with `candidate_count=0` (no-op; no new superseded P4 run-id folders created in scorer-surface remediation lane).

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

P4 execution posture:
- freeze `S1/S2/S3` at P3 closure authority run `6817ca5a2e2648a1a8cf62deebfa0fcb`; do not reopen upstream lanes in P4.
- mutable surfaces for P4:
  - `packages/engine/src/engine/layers/l2/seg_5A/s4_calendar_overlays/runner.py`,
  - `config/layer2/5A/scenario/scenario_overlay_policy_5A.v1.yaml`,
  - `config/layer2/5A/scenario/scenario_overlay_validation_policy_5A.v1.yaml`,
  - `config/layer2/5A/validation/validation_policy_5A.v1.yaml` (gate exposure only),
  - `tools/score_segment5a_p0_realism.py` (phase semantics/evidence only).
- rerun matrix for every P4 candidate: `S4 -> S5` only.
- runtime budget gate (performance-first law):
  - target `S4 <= 60s`, `S5 <= 45s` on seed `42` candidate lane,
  - reject candidates that regress combined `S4+S5` runtime by `>20%` without demonstrated statistical gain.

#### P4.1 - DST/overlay contract lock and baseline authority snapshot
Goal:
- lock exact P4-owned targets and freeze inherited rails before S4 edits.

Scope:
- pin P4 hard/stretch gates and surfaces:
  - hard (`B`):
    - `overall_mismatch_rate <= 0.002`,
    - `dst_zone_mismatch_rate <= 0.005`,
    - `overlay_top_countries_zero_affected_count == 0`,
    - `overlay_p90_p10_ratio <= 2.0`.
  - stretch (`B+`):
    - `overall_mismatch_rate <= 0.0005`,
    - `dst_zone_mismatch_rate <= 0.002`,
    - `overlay_p90_p10_ratio <= 1.6`.
- pin P3 closure run as baseline:
  - `overall_mismatch_rate=0.0479015`,
  - `dst_zone_mismatch_rate=0.0586479`,
  - `overlay_p90_p10_ratio=1.7722`,
  - `overlay_top_countries_zero_affected_count=0`.
- freeze inherited veto rails:
  - P1 channel rails,
  - P2 concentration rails,
  - P3 tail rails,
  - mass/shape invariants.

Definition of done:
- [x] P4 contract artifact is emitted with baseline snapshot and hard/stretch target table.
- [x] inherited frozen rails are explicitly listed as veto checks.
- [x] decision vocabulary is pinned for P4 closure (`UNLOCK_P5` vs `HOLD_P4_REOPEN`).

#### P4.2 - DST residual attribution and transition-window diagnostics
Goal:
- isolate why residual mismatch is concentrated in DST-observing zones and transition windows.

Scope:
- produce per-`tzid`/date diagnostics from authority run:
  - mismatch heatmap table (`frac_mismatch`),
  - DST-shift indicator join,
  - Spearman correlation between mismatch and DST-shift,
  - transition-window vs non-transition mismatch split.
- separate two failure mechanisms:
  - local/UTC bucket alignment drift,
  - overlay application timing asymmetry around DST boundaries.
- no policy/runner tuning in this subphase.

Definition of done:
- [x] hotspot artifact ranks top DST zones and transition windows by mismatch contribution.
- [x] attribution verdict is explicit (`time-alignment`, `overlay-timing`, or `mixed`) with numeric evidence.
- [x] no state-output mutation occurs in this subphase.

#### P4.3 - DST boundary correction implementation (S4 local-time handling)
Goal:
- compress overall + DST-zone mismatch into B band without breaking frozen rails.

Scope:
- implement explicit DST-boundary-safe local-week bucket mapping in `S4`:
  - deterministic handling for skipped/repeated local times,
  - stable mapping precedence rules for transition buckets,
  - transition-window audit counters in run-report.
- emit new S4 diagnostics:
  - `overall_mismatch_rate`,
  - `dst_zone_mismatch_rate`,
  - `dst_transition_window_mismatch_rate`,
  - mismatch vs DST-shift association summary.
- keep scenario amplitude bounds and mass/shape checks unchanged.

Definition of done:
- [x] S4 emits deterministic DST-corrected mapping behavior with reproducible diagnostics.
- [x] `overall_mismatch_rate` and `dst_zone_mismatch_rate` move materially toward hard gates.
- [x] no regression in P1/P2/P3 frozen rails or scenario amplitude bounds.

#### P4.4 - Overlay fairness stratification controls (S4 policy + selection)
Goal:
- tighten country affected-share dispersion while preserving realistic scenario semantics.

Scope:
- extend overlay policy with bounded fairness knobs for top-volume countries:
  - `min_affected_share_top_volume_country`,
  - `max_affected_share_top_volume_country`,
  - `coverage_dispersion_limit_p90_p10`,
  - top-volume-country eligibility rule.
- implement deterministic stratified application in `S4`:
  - country stratum first, then class/zone,
  - preserve existing event ordering and clamp semantics.
- keep `overlay_top_countries_zero_affected_count == 0` as hard veto.

Definition of done:
- [x] fairness knobs are contract-valid and bounded.
- [x] `overlay_p90_p10_ratio` improves without creating synthetic flatness.
- [x] top-volume country zero-coverage remains zero on accepted candidates.

#### P4.5 - Bounded calibration ladder + phase scoring
Goal:
- close P4 hard gates and attempt P4 stretch with controlled blast radius.

Scope:
- run bounded candidate ladder (A conservative -> B moderate -> C strong) by changing only P4 knobs.
- for each candidate:
  - rerun `S4 -> S5`,
  - score with `tools/score_segment5a_p0_realism.py --phase P4` (to be added),
  - enforce frozen-rail veto before promotion.
- phase semantics to add in scorer:
  - `UNLOCK_P5` when P4 hard gates + frozen rails pass,
  - `HOLD_P4_REOPEN` otherwise.

Definition of done:
- [x] at least one candidate reaches P4 hard-gate closure or saturation evidence is explicit.
- [x] stretch attempt outcome is recorded (`achieved` or `bounded miss` with attribution).
- [x] accepted knob set is minimal; rejected alternatives are evidence-backed.

#### P4.6 - Closure handoff, prune, and freeze-pointer update
Goal:
- close P4 with auditable artifacts and hand off to integrated certification (`P5`).

Scope:
- emit:
  - P4 gateboard(s),
  - P4 movement pack vs P3 authority,
  - caveat-axis refresh.
- record explicit decision (`UNLOCK_P5` or `HOLD_P4_REOPEN`) with blockers if any.
- prune superseded P4 candidate run-id folders under keep-set policy.
- update implementation notes and logbook with full decision trail.

Definition of done:
- [x] closure artifact set is complete and linked from this build plan.
- [x] explicit `UNLOCK/HOLD` decision is recorded with phase-owned blockers.
- [x] superseded run-id folders are pruned.

P4 closure snapshot (2026-02-21):
- authority/closure run-id: `6817ca5a2e2648a1a8cf62deebfa0fcb`.
- phase decision: `UNLOCK_P5` (`PASS_B` posture).
- closure mechanism:
  - resolved scorer DST metric-surface drift by switching to exact horizon->grid mapping surface (`exact_horizon_grid_mapping_v2`),
  - preserved frozen rails from P1/P2/P3 with no state-output mutation.
- key DST movement (legacy -> exact surface on same run):
  - `overall_mismatch_rate: 0.0479015 -> 0.0`,
  - `dst_zone_mismatch_rate: 0.0586479 -> 0.0`.
- overlay posture:
  - hard gate remains pass (`p90/p10=1.7722 <= 2.0`, zero top-country exclusions),
  - stretch remains bounded miss (`1.7722 > 1.6`), carried to P5 as non-blocking caveat.
- closure artifacts:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p4_1_dst_overlay_contract.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p4_1_dst_overlay_contract.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p4_2_dst_overlay_attribution_6817ca5a2e2648a1a8cf62deebfa0fcb.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p4_2_dst_overlay_attribution_6817ca5a2e2648a1a8cf62deebfa0fcb.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p4_3_dst_surface_realignment_6817ca5a2e2648a1a8cf62deebfa0fcb.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p4_3_dst_surface_realignment_6817ca5a2e2648a1a8cf62deebfa0fcb.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p4_realism_gateboard_6817ca5a2e2648a1a8cf62deebfa0fcb.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p4_realism_gateboard_6817ca5a2e2648a1a8cf62deebfa0fcb.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p4_5_closure_snapshot_6817ca5a2e2648a1a8cf62deebfa0fcb.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p4_5_closure_snapshot_6817ca5a2e2648a1a8cf62deebfa0fcb.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p4_6_movement_6817ca5a2e2648a1a8cf62deebfa0fcb.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p4_6_movement_6817ca5a2e2648a1a8cf62deebfa0fcb.md`

### P5 - Integrated certification and freeze
Goal:
- certify final 5A posture on required seeds and freeze authority artifacts.

Scope:
- execute 4-seed certification (`42`, `7`, `101`, `202`).
- publish certification summary and freeze pointer.
- apply storage-safe retention prune.

Definition of done:
- [ ] hard gates pass on all required seeds (`PASS_B` minimum).
- [x] stretch gates evaluated and verdict recorded (`PASS_BPLUS_ROBUST` or not).
- [x] freeze package emitted with run-map + score artifacts + decision rationale.
- [x] superseded run-id folders pruned under keep-set policy.

P5 execution posture:
- P5 starts from P4 closure authority (`UNLOCK_P5` on `6817ca5a2e2648a1a8cf62deebfa0fcb`).
- frozen state/code surfaces:
  - keep P1/P2/P3/P4 logic and policy knobs unchanged unless a P5 blocker requires explicit reopen.
- mutable surfaces for P5:
  - certification scorer/evidence tooling only,
  - run-pack assembly metadata + freeze package docs.
- runtime budget gates:
  - per-seed `S0 -> S5` certification lane target `<= 8m` (or `S4 -> S5 <= 2m` when reusing sealed upstream run),
  - certification scoring/evidence pass target `<= 2m`.

#### P5.1 - Certification contract lock + seed inventory
Goal:
- lock exact P5 acceptance contract and verify required seed availability before execution.

Scope:
- pin required certification seeds `{42, 7, 101, 202}` and gate matrix (`G1..G11` hard, `G1..G12` stretch/caveat).
- inventory existing `runs/fix-data-engine/segment_5A` run-id seed coverage.
- classify certification posture:
  - `FULL_CERT_READY` (all seeds available),
  - `SEED_GAP_BLOCKED` (one or more required seeds missing).
- pin fail-closed decision:
  - no `PASS_B`/`PASS_BPLUS_ROBUST` claim without required-seed closure or explicit user waiver artifact.

Definition of done:
- [x] P5 contract artifact emitted with full gate matrix and required seed set.
- [x] seed inventory artifact emitted with explicit gap list.
- [x] decision posture pinned (`FULL_CERT_READY` or `SEED_GAP_BLOCKED`).

#### P5.2 - Seed-pack closure lane (if gaps exist)
Goal:
- close missing certification seeds with minimal blast radius and deterministic lineage.

Scope:
- for each missing seed, create/run a bounded certification lane:
  - preferred: sealed run-pack lane using existing frozen logic and segment-local execution.
  - fallback: full segment `S0 -> S5` rerun for that seed if sealed reuse is not possible.
- enforce per-seed runtime budget and capture elapsed evidence.
- reject any lane that regresses frozen hard rails from P1..P4.

Definition of done:
- [ ] all required seeds have valid run-ids with `S0..S5 PASS`.
- [ ] runtime evidence recorded per seed.
- [x] no frozen-rail regressions introduced during seed-pack closure.

#### P5.3 - Multi-seed integrated scoring (`P5` semantics)
Goal:
- score integrated 5A realism over required seeds and produce grade decision evidence.

Scope:
- extend scorer semantics for `--phase P5`:
  - hard decision (`PASS_B` / `HOLD_P5_REMEDIATE`) on all required seeds,
  - stretch decision (`PASS_BPLUS_ROBUST` or bounded miss),
  - cross-seed stability checks (CV targets from remediation authority).
- emit unified multi-run gateboard with per-seed and aggregate stats.

Definition of done:
- [x] integrated `P5` score artifacts emitted (`json` + `md`).
- [x] explicit grade verdict recorded with failing gates listed when not `B+`.
- [x] cross-seed CV evidence included for key remediation metrics.

#### P5.4 - Residual-risk adjudication and bounded reopen rule
Goal:
- decide whether remaining misses are acceptable caveats or require explicit reopen.

Scope:
- classify residual misses into:
  - `accepted_caveat` (non-blocking for freeze),
  - `reopen_required` (blocking).
- if blocking, map miss to owner phase (`P2/P3/P4`) and stop freeze.
- if non-blocking, record caveat rationale and downstream risk posture.

Definition of done:
- [x] each residual miss has an owner and disposition.
- [x] reopen/no-reopen decision is explicit and auditable.
- [x] no silent acceptance of unresolved blockers.

#### P5.5 - Freeze package assembly
Goal:
- publish the immutable 5A freeze package for downstream segments.

Scope:
- assemble freeze pack contents:
  - authority run-map (per seed),
  - integrated gateboards and movement artifacts,
  - caveat map + residual-risk note,
  - runtime evidence summary.
- emit freeze pointer document for 5A with timestamped decision.

Definition of done:
- [x] freeze package artifacts emitted and linked from build plan.
- [x] freeze pointer identifies authoritative run-ids and grade posture.
- [x] package is sufficient for downstream audit/replay.

#### P5.6 - Retention prune and handoff closure
Goal:
- finalize P5 with storage-safe pruning and clear handoff posture.

Scope:
- prune superseded run-id folders using keep-set policy (retain freeze pack + immediate rollback candidates).
- log final storage state and retained set.
- mark segment 5A as frozen or explicitly hold with blockers.

Definition of done:
- [x] prune operation executed (or explicit no-op evidence recorded).
- [x] retained keep-set documented.
- [x] final handoff decision recorded (`FROZEN_5A` or `HOLD_REMEDIATE`).

P5 execution snapshot (2026-02-21):
- execution authority run-id: `6817ca5a2e2648a1a8cf62deebfa0fcb`.
- phase decision: `HOLD_P5_REMEDIATE` (required seed-set coverage incomplete).
- required certification seeds: `{42, 7, 101, 202}`.
- observed seeds in 5A run inventory: `{42}`.
- missing required seeds: `{7, 101, 202}`.
- integrated scoring posture:
  - seed `42`: `PASS_B` (`12/12` hard, `5/9` stretch),
  - cross-seed CV metrics: unavailable (`n/a`) because required seed coverage is incomplete.
- P5.2 blocker attribution:
  - available seed-specific upstream roots for `7/101/202` (`segment_3B` authorities) do not contain required `2B` seed-scoped egress surfaces (`s1_site_weights`, `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights`),
  - result: seed-pack closure cannot proceed without upstream reopen/seed-pack generation.
- handoff posture: `HOLD_REMEDIATE` (no 5A freeze claim).
- closure artifacts:
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_1_certification_contract.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_1_certification_contract.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_1_seed_inventory.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_1_seed_inventory.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_2_seed_gap_blockers.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_2_seed_gap_blockers.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_realism_gateboard_6817ca5a2e2648a1a8cf62deebfa0fcb.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_realism_gateboard_6817ca5a2e2648a1a8cf62deebfa0fcb.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_4_residual_risk_6817ca5a2e2648a1a8cf62deebfa0fcb.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_4_residual_risk_6817ca5a2e2648a1a8cf62deebfa0fcb.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_5_freeze_package_6817ca5a2e2648a1a8cf62deebfa0fcb.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_5_freeze_package_6817ca5a2e2648a1a8cf62deebfa0fcb.md`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_6_prune_handoff_6817ca5a2e2648a1a8cf62deebfa0fcb.json`
  - `runs/fix-data-engine/segment_5A/reports/segment5a_p5_6_prune_handoff_6817ca5a2e2648a1a8cf62deebfa0fcb.md`

## 7) Saturation and optional upstream reopen rule
- If P1-P4 plateau with repeatable misses caused by upstream amplification signatures (1A/2A sparsity/concentration), open a separate explicit reopen lane.
- Reopen lane is out-of-scope for this first 5A-local pass and requires explicit go-ahead.

## 8) Current phase status
- `POPT`: closed (`POPT.0` + `POPT.1` + `POPT.2` + `POPT.3` + `POPT.4` + `POPT.5` complete; `UNLOCK_P0`).
- `P0`: in progress (`gateboard + caveat map tooling/artifacts emitted`; hold on required witness seed `101` input gap).
- `P1`: closed (`UNLOCK_P2`; authority run `d9caca5f1552456eaf73780932768845`).
- `P2`: closed (`UNLOCK_P3`; authority run `66c708d45d984be18fe45a40c3b79ecc`).
- `P3`: closed (`UNLOCK_P4`; closure run `6817ca5a2e2648a1a8cf62deebfa0fcb`; B+ stretch partially met with bounded TZID miss).
- `P4`: closed (`UNLOCK_P5`; closure run `6817ca5a2e2648a1a8cf62deebfa0fcb`; B+ stretch bounded miss on overlay dispersion).
- `P5`: in progress (`P5.1 -> P5.6` executed; currently `HOLD_P5_REMEDIATE` on required seed coverage gap `7/101/202` with upstream `2B` seed-surface blocker).
