# Segment 3A Remediation Build Plan (B/B+ Execution Plan)
_As of 2026-02-18_

## 0) Objective and closure rule
- Objective: remediate Segment `3A` to certified realism `B` minimum, with `B+` as the stretch target.
- Baseline authority posture from published report: realism grade `C` (structurally correct, behaviorally flat).
- Primary realism surfaces of record:
  - `s1_escalation_queue`
  - `s2_country_zone_priors`
  - `s3_zone_shares`
  - `s4_zone_counts`
  - `zone_alloc`
- Closure rule:
  - `PASS_BPLUS`: all hard gates pass on all required seeds and all B+ stretch gates pass.
  - `PASS_B`: all hard gates pass on all required seeds.
  - `FAIL_REALISM`: any hard gate fails on any required seed.
  - `INVALID_FOR_GRADING`: required artifacts or certification seedpack is incomplete.
- Phase advancement law (binding): no phase is closed until every DoD item is green.

## 1) Source-of-truth stack

### 1.1 Statistical authority
- `docs/reports/eda/segment_3A/segment_3A_published_report.md`
- `docs/reports/eda/segment_3A/segment_3A_remediation_report.md`

### 1.2 State and contract authority
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s0.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s1.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s2.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s3.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s4.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s5.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s6.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s7.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3A/dataset_dictionary.layer1.3A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3A/schemas.3A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3A/artefact_registry_3A.yaml`

### 1.3 Upstream freeze posture (binding for this cycle)
- `1A` frozen.
- `1B` frozen.
- `2A` frozen.
- `2B` frozen.
- 3A remediation starts as 3A-local only; any upstream reopen requires explicit decision and separate lane.

## 2) Causal remediation posture
- Data-shape causal order:
  - `S2 priors` -> `S3 sampled dispersion` -> `S4 integerized outcomes` -> `zone_alloc`.
- State ownership for remediation:
  - Primary tuning states: `S2`, `S3`, `S4`.
  - Secondary conditional tuning state: `S1` (escalation smoothing).
  - Contract/gate states (`S0`, `S6`, `S7`) are veto rails, not the optimization target.
- Focus law:
  - optimize for statistical realism movement first,
  - keep structural checks green as hard vetoes.

## 3) Statistical targets and hard gates
- Certification seedpack: `{42, 7, 101, 202}`.

### 3.1 Hard B gates (must pass all seeds)
- S2 priors on multi-TZ countries:
  - median `top1_share <= 0.85`.
  - share with `top1_share >= 0.99 <= 20%`.
- S3 merchant heterogeneity:
  - median within-country `std(share_drawn) >= 0.02`.
- S4 realized multi-zone behavior:
  - escalated pairs with `>1` nonzero zone `>= 35%`.
  - escalated pairs with `>=2` zones above `5%` share `>= 20%`.
  - median `top1_share <= 0.90`.
  - p75 `top1_share <= 0.97`.
- `zone_alloc`:
  - median `top1_share <= 0.90`.
- Structural rails:
  - conservation and schema gates remain PASS (`S6` and bundle path non-regression).

### 3.2 B+ stretch gates
- S2:
  - median `top1_share <= 0.75`.
  - share with `top1_share >= 0.99 <= 10%`.
- S3:
  - median within-country `std(share_drawn) >= 0.04`.
- S4 and `zone_alloc`:
  - median `top1_share <= 0.85`.
  - escalated multi-zone rate `>= 55%`.

### 3.3 Cross-seed stability gates
- CV for primary medians (`S2 top1`, `S3 std`, `S4 top1`, multi-zone rate):
  - `B`: `CV <= 0.25`
  - `B+`: `CV <= 0.15`
- Any hard-gate miss on any seed blocks certification.

## 4) Run protocol, performance budget, and retention
- Active run root: `runs/fix-data-engine/segment_3A`.
- Retention set:
  - baseline authority run,
  - active candidate run,
  - last good run,
  - reports folder.
- Prune-before-expensive-run is mandatory.

### 4.1 Progressive rerun matrix (sequential-state law)
- If `S2` policy/code changes: rerun `S2 -> S3 -> S4 -> S5 -> S6 -> S7`.
- If `S3` policy/code changes: rerun `S3 -> S4 -> S5 -> S6 -> S7`.
- If `S4` policy/code changes: rerun `S4 -> S5 -> S6 -> S7`.
- If `S1` policy/code changes: rerun `S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7`.
- If only scorer/reporting changes: rerun scorers only; no state recomputation.

### 4.2 Runtime-budget law for this plan
- `POPT.0` must publish measured state-level baseline before remediation tuning.
- No phase closes without measured runtime evidence showing non-regression against locked baseline.
- Target posture: minute-scale iteration for single-seed candidate lane under single-process mode.

## 5) Phased remediation plan

### POPT.0 - 3A runtime baseline and bottleneck map
Goal:
- establish state-level runtime baseline and hotspot ranking before any realism tuning.

Scope:
- run one clean `S0 -> S7` chain on fixed seed (`42`) from frozen upstream posture.
- emit state elapsed table and hotspot map.

Definition of done:
- [x] baseline runtime artifact is emitted.
- [x] hotspot ranking is pinned.
- [x] runtime budgets for candidate/witness/certification lanes are pinned.

POPT.0 closure snapshot (2026-02-18):
- clean authority run-id: `06b822558c294a0888e3f8f342e83947`.
- artifacts:
  - `runs/fix-data-engine/segment_3A/reports/segment3a_popt0_baseline_06b822558c294a0888e3f8f342e83947.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_popt0_hotspot_map_06b822558c294a0888e3f8f342e83947.md`
- measured state shares (seed `42`):
  - `S6`: `00:00:18` (`26.45%`)
  - `S7`: `00:00:13` (`19.38%`)
  - `S5`: `00:00:12` (`18.42%`)
  - `S4`: `00:00:08` (`11.90%`)
  - `S3`: `00:00:06` (`9.38%`)
  - `S2`: `00:00:05` (`7.08%`)
  - `S1`: `00:00:04` (`5.45%`)
  - `S0`: `00:00:01` (`1.95%`)
- progression gate: `GO` (`next_state_for_popt1=S6`; primary hotspot budget status=`RED`).
- pinned runtime budgets (seconds):
  - `S0`: target `1.5`, stretch `2.5`
  - `S1`: target `3.0`, stretch `4.5`
  - `S2`: target `4.0`, stretch `6.0`
  - `S3`: target `5.0`, stretch `7.5`
  - `S4`: target `6.0`, stretch `9.0`
  - `S5`: target `8.0`, stretch `12.0`
  - `S6`: target `10.0`, stretch `14.0`
  - `S7`: target `8.0`, stretch `12.0`

### POPT.1 - Hotspot optimization lock
Goal:
- reduce primary runtime bottleneck while preserving deterministic outputs.

Scope:
- optimize only hot states identified by `POPT.0` (`S6` primary; `S7/S5` secondary closure lane).
- no realism-threshold tuning in this phase.
- no policy/config changes in `S1/S2/S3/S4`; this is compute-path only.
- keep `S6` and `S7` as strict veto rails: no schema drift, no gate relaxation, no digest-rule weakening.

Execution posture:
- candidate run root: `runs/fix-data-engine/segment_3A`.
- baseline authority for deltas:
  - run-id: `06b822558c294a0888e3f8f342e83947`
  - artifact: `runs/fix-data-engine/segment_3A/reports/segment3a_popt0_baseline_06b822558c294a0888e3f8f342e83947.json`
- rerun law for this phase:
  - if `S6` code changes: rerun `S6 -> S7`.
  - if `S7` code changes: rerun `S7`.
  - if `S5` code changes: rerun `S5 -> S6 -> S7`.
- prune superseded run-id folders before each expensive candidate pass.
- closure authority:
  - candidate run-id: `81599ab107ba4c8db7fc5850287360fe`
  - closure decision: `UNLOCK_P0`
  - measured deltas vs baseline `06b822558c294a0888e3f8f342e83947`:
    - `S5`: `12.50s -> 4.60s` (`+63.23%`)
    - `S6`: `17.94s -> 2.93s` (`+83.65%`)
    - `S7`: `13.15s -> 2.25s` (`+82.89%`)

#### POPT.1.1 - Baseline guard + closure scorer lock
Goal:
- lock a deterministic runtime-delta scorer and veto-gate evaluator for `POPT.1`.

Scope:
- add closure scorer artifact contract for baseline-vs-candidate comparison.
- capture current baseline timings for `S6/S7/S5` and invariant fields used for non-regression.

Definition of done:
- [x] `segment3a_popt1_closure_<run_id>.json` schema is pinned.
- [x] baseline snapshot for `S6/S7/S5` is pinned as scorer input.
- [x] veto checks are encoded (status, issue counts, digest/index integrity).

#### POPT.1.2 - S6 primary hotspot optimization
Goal:
- reduce `S6` elapsed time while preserving validation semantics and PASS posture.

Scope:
- target `S6` precondition-input load and structural-check execution path.
- optimize data-structure/reuse and IO sequencing only; no rule changes.

Definition of done:
- [x] `S6` elapsed improves vs baseline (`17.94s`) with measured evidence.
- [x] `S6` reaches at least `AMBER` budget (`<= 14.0s`) or shows >=15% reduction if still above.
- [x] `S6` run-report remains `overall_status=PASS`, `issues_error=0`, `issues_total` non-regressed.

#### POPT.1.3 - S7 secondary hotspot optimization
Goal:
- reduce validation-bundle assembly runtime (`S7`) without changing bundle contract semantics.

Scope:
- optimize member hashing/index assembly path (IO/readback/layout efficiency).
- keep index-only bundle posture and required member coverage unchanged.

Definition of done:
- [x] `S7` elapsed improves vs baseline (`13.14s`) with measured evidence.
- [x] `S7` reaches at least `AMBER` budget (`<= 12.0s`) or shows >=10% reduction if still above.
- [x] `index.json` integrity and `_passed.flag` semantics remain unchanged.

#### POPT.1.4 - S5 closure-lane trim (conditional)
Goal:
- reduce `S5` closure-lane drag if `S5` remains above closure budget after `S6/S7` work.

Scope:
- optimize `zone_alloc` write/digest path and invariant reuse.
- no changes to allocation semantics or digest masking rules.

Definition of done:
- [x] if executed, `S5` elapsed improves vs baseline (`12.50s`) with measured evidence.
- [x] `S5` reaches at least `AMBER` budget (`<= 12.0s`) or shows >=8% reduction if still above.
- [x] `pairs_count_conservation_violations=0` and `routing_universe_hash` contract remains valid.

#### POPT.1.5 - Determinism + structural witness
Goal:
- prove that runtime gains do not compromise deterministic contracts or structural rails.

Scope:
- run witness candidate pass(es) on seed `42` and compare required invariants to baseline.
- enforce fail-closed veto if any structural or digest contract drifts unexpectedly.

Definition of done:
- [x] `S6` and `S7` statuses remain PASS across witness pass.
- [x] no schema/index/passed-flag regressions.
- [x] closure scorer reports runtime improvement with no veto violations.

#### POPT.1.6 - Phase closure and lock
Goal:
- close `POPT.1` with explicit verdict and handoff target for next phase.

Scope:
- publish closure summary and lock candidate run-id.
- update plan/notes/logbook with measured deltas and next-phase decision.

Definition of done:
- [x] closure artifacts emitted:
  - `runs/fix-data-engine/segment_3A/reports/segment3a_popt1_closure_<run_id>.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_popt1_closure_<run_id>.md`
- [x] explicit decision recorded: `UNLOCK_P0` or `HOLD_POPT1_REOPEN`.
- [x] retention/prune set is applied to keep storage bounded.

Definition of done:
- [x] hotspot runtime reduced with measured evidence.
- [x] deterministic replay witness is PASS.
- [x] structural non-regression checks remain PASS.

### P0 - Baseline statistical pack and scoring harness
Goal:
- produce 3A baseline metric pack and lock scorer contract for all later phases.

Scope:
- emit baseline metrics from current authority run and calibration plots/JSON needed for gates.
- lock scorer script interfaces and artifact names.

Definition of done:
- [x] baseline metrics JSON/MD emitted.
- [x] hard/stretch gate evaluator is executable on one candidate run.
- [x] baseline-vs-candidate delta report format is pinned.

P0 execution authority:
- baseline run-id: `81599ab107ba4c8db7fc5850287360fe`
- baseline artifacts:
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p0_baseline_metrics_81599ab107ba4c8db7fc5850287360fe.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p0_baseline_metrics_81599ab107ba4c8db7fc5850287360fe.md`
- candidate evaluator witness:
  - candidate run-id: `06b822558c294a0888e3f8f342e83947`
  - delta artifacts:
    - `runs/fix-data-engine/segment_3A/reports/segment3a_p0_candidate_vs_baseline_06b822558c294a0888e3f8f342e83947.json`
    - `runs/fix-data-engine/segment_3A/reports/segment3a_p0_candidate_vs_baseline_06b822558c294a0888e3f8f342e83947.md`
- baseline verdict: `FAIL_REALISM` (expected; this is the locked pre-remediation posture).

### P1 - S2 prior geometry remediation (CF-3A-01)
Goal:
- reduce prior over-concentration while preserving country/zone domain integrity.

Scope:
- tune `country_zone_alphas` and `zone_floor_policy` toward mixed-dominance priors.
- keep deterministic, parameter-scoped S2 output contract unchanged.
- keep `S0/S1` frozen in this phase; no escalation-policy edits in `P1`.

Definition of done:
- [x] S2 hard gates move into or toward B bands on witness seed.
- [x] no S2 domain/integrity regressions.
- [x] policy digests + decision trail captured.

P1 authority baseline (from P0):
- run-id: `81599ab107ba4c8db7fc5850287360fe`
- baseline anchors:
  - `S2` multi-TZ top1 median: `0.991523`
  - `S2` multi-TZ share(top1>=0.99): `0.525424`
  - `S3` merchant share-std median: `0.002972`
  - `S4` escalated multi-zone rate: `0.133251`
  - `S4` top1 median/p75: `1.000000 / 1.000000`

Execution posture:
- rerun law for this phase:
  - `country_zone_alphas` or `zone_floor_policy` change -> rerun `S2 -> S3 -> S4 -> S5 -> S6 -> S7`.
- scorer contract:
  - baseline authority:
    - `segment3a_p0_baseline_metrics_81599ab107ba4c8db7fc5850287360fe.json`
  - candidate comparator:
    - `score_segment3a_p0_candidate.py`
- optimize data shape first; structural rails (`S4/zone_alloc` conservation) remain veto gates.

#### P1.1 - Target Envelope + Knob Map
Goal:
- lock quantitative movement targets and the exact knob families to explore for `S2`.

Scope:
- set interim `P1` movement envelope (not final certification):
  - `S2` multi-TZ top1 median: reduce by at least `0.05` absolute from baseline.
  - `S2` share(top1>=0.99, multi-TZ): reduce by at least `0.10` absolute.
  - no increase in `S4`/`zone_alloc` top1 concentration.
- pin candidate knobs:
  - prior flattening strength (dominant-to-tail mass redistribution),
  - floor/bump intensity and caps in `zone_floor_policy`.

Definition of done:
- [x] movement envelope values are pinned in notes before first candidate run.
- [x] knob families and tested ranges are explicitly listed.
- [x] run-sequence and retention policy are pinned (`S2->S7`, prune superseded runs).

#### P1.2 - Prior Geometry Candidate Sweep (`country_zone_alphas`)
Goal:
- identify one alpha-geometry family that reduces S2 degeneracy without breaking downstream structure.

Scope:
- execute bounded candidate sweep on `country_zone_alphas` geometry only.
- score each candidate against the `P0` baseline with `segment3a_p0_candidate_vs_baseline_<run_id>`.
- prioritize candidates with strongest reductions in:
  - `S2` multi-TZ top1 median,
  - `S2` share(top1>=0.99, multi-TZ).

Selection method:
- maximize objective:
  - `J = 0.45 * d_top1 + 0.35 * d_tail + 0.20 * d_multi_zone`
  - where:
    - `d_top1 = baseline_s2_top1_median - candidate_s2_top1_median`
    - `d_tail = baseline_s2_share_ge099 - candidate_s2_share_ge099`
    - `d_multi_zone = candidate_s4_multi_zone_rate - baseline_s4_multi_zone_rate`
- hard veto if conservation rails fail (`S4` or `zone_alloc`).

Definition of done:
- [x] at least one alpha candidate produces positive `d_top1` and `d_tail`.
- [x] candidate ranking table is recorded in decision trail.
- [x] one alpha candidate is promoted to `P1.3` floor co-calibration lane.

#### P1.3 - Floor/Boost Co-Calibration (`zone_floor_policy`)
Goal:
- use floor-policy tuning to preserve tail participation without flattening priors unrealistically.

Scope:
- keep promoted alpha geometry fixed.
- test bounded floor-policy variants (floor intensity/cap) and rerun `S2->S7`.
- reject variants that improve `S2` but regress downstream concentration in `S4/zone_alloc`.

Definition of done:
- [x] selected floor-policy variant improves `S2` concentration metrics vs `P0` baseline.
- [x] `S3` merchant share-std and `S4` escalated multi-zone rate are non-regressed.
- [x] conservation rails remain PASS.

#### P1.4 - Witness Lock + P1 Closeout
Goal:
- lock one `P1` authority candidate and hand off cleanly to `P2`.

Scope:
- rerun winning `P1` candidate once for witness reproducibility.
- emit final `P1` candidate-vs-baseline artifacts and decision summary.
- pin retained run-ids and prune superseded run folders.

Definition of done:
- [x] witness rerun reproduces metrics within deterministic tolerance (exact for deterministic fields).
- [x] final `P1` artifact paths are pinned in build plan + notes.
- [x] explicit `P1` decision recorded:
  - `UNLOCK_P2` or `HOLD_P1_REOPEN`.

P1 closure snapshot (2026-02-19):
- decision: `UNLOCK_P2`.
- promoted alpha authority (`P1.2`): `878cddcd58bf4a36bd88c56de0d18056`.
- selected floor co-calibration candidate (`P1.3`): `3dd2a10fb61b4ab581f9e9251c8d72ab` (`F0`, `floor_scale=1.00`, `threshold_shift=0.00`).
- witness rerun (`P1.4`): `fa527d6a0a4c4eab97516d9e95be8420` (exact metric replay vs selected candidate).
- retained run-id set after prune:
  - `06b822558c294a0888e3f8f342e83947` (`POPT.0` runtime baseline),
  - `81599ab107ba4c8db7fc5850287360fe` (`P0` baseline authority),
  - `878cddcd58bf4a36bd88c56de0d18056` (`P1.2` alpha authority),
  - `3dd2a10fb61b4ab581f9e9251c8d72ab` (`P1.3` selected floor candidate),
  - `fa527d6a0a4c4eab97516d9e95be8420` (`P1.4` witness).
- artifacts:
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p1_2_sweep_summary.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p1_3_sweep_summary.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p1_3_sweep_summary.md`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p1_4_witness_summary.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p1_4_witness_summary.md`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p0_candidate_vs_baseline_3dd2a10fb61b4ab581f9e9251c8d72ab.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p0_candidate_vs_baseline_fa527d6a0a4c4eab97516d9e95be8420.json`

### P2 - S3 merchant dispersion remediation (CF-3A-02)
Goal:
- introduce controlled merchant-level heterogeneity in zone shares.

Scope:
- adjust S3 dispersion controls and RNG-safe deterministic keying.
- preserve RNG accounting and reconciliation invariants.

Definition of done:
- [x] S3 dispersion hard gate (`median std >= 0.02`) passes on witness seed.
- [x] S3 RNG accounting checks remain PASS.
- [x] no downstream S4 conservation regressions introduced.

P2 authority baseline (post-P1 lock):
- selected run-id: `3dd2a10fb61b4ab581f9e9251c8d72ab`.
- witness run-id: `fa527d6a0a4c4eab97516d9e95be8420`.
- current anchors:
  - `S3` merchant share-std median: `0.017801` (gap to B floor: `+0.002199`).
  - `S4` escalated multi-zone rate: `0.917127`.
  - `S4` top1 median: `0.750000`.
  - `zone_alloc` top1 median: `0.750000`.

Execution posture:
- rerun law for this phase:
  - `S3` code/policy change -> rerun `S3 -> S4 -> S5 -> S6 -> S7`.
- scorer contract:
  - baseline authority:
    - `segment3a_p0_baseline_metrics_81599ab107ba4c8db7fc5850287360fe.json`
  - candidate comparator:
    - `score_segment3a_p0_candidate.py`
- `P1`-locked `S2` posture is treated as frozen in `P2`; no `S2` reopen in this phase.

#### P2.1 - Target Envelope + Dispersion Knob Contract
Goal:
- pin quantitative `P2` targets and deterministic knob families before touching `S3`.

Scope:
- target envelope for `P2` candidate selection:
  - primary: `S3 merchant_share_std_median >= 0.020` (`B` hard gate).
  - stretch movement: toward `>= 0.025` without destabilizing downstream shape.
  - guardrails (seed `42`):
    - `S4 escalated_multi_zone_rate >= 0.85`,
    - `S4 top1_share_median <= 0.80`,
    - `zone_alloc top1_share_median <= 0.80`.
- pin dispersion knobs (deterministic, bounded):
  - `alpha_temperature` (compression/flattening on prior concentration),
  - `merchant_dispersion_sigma` (hash-keyed merchant amplitude),
  - `merchant_dispersion_clip` (bounded jitter cap),
  - `alpha_floor` (strictly-positive concentration floor).

Definition of done:
- [x] target envelope + guardrails are pinned in notes.
- [x] candidate knob ranges are explicitly listed.
- [x] run-sequence and prune posture are pinned for `S3->S7` iterations.

#### P2.2 - S3 Knob Surface Wiring (Deterministic + Sealed)
Goal:
- wire bounded dispersion knobs into `S3` without breaking deterministic replay discipline.

Scope:
- implement deterministic merchant-level dispersion transform in
  `packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/runner.py`.
- read `S3` dispersion knobs from sealed `zone_mixture_policy` extension block
  (no new artefact family in this phase), with fail-closed defaults.
- preserve RNG law:
  - unchanged stream identity discipline,
  - unchanged event/trace accounting invariants,
  - no wall-clock or non-sealed randomness.

Definition of done:
- [x] `S3` implements bounded dispersion transform with deterministic keying.
- [x] policy/knob read path is sealed-input compatible and fail-closed.
- [x] compile + static sanity pass is green before first candidate run.

#### P2.3 - Bounded Candidate Sweep + Ranking
Goal:
- find one `S3` dispersion candidate that crosses the hard gate while preserving locked `P1` posture.

Scope:
- run bounded sweep on `S3` dispersion knobs only; rerun `S3->S7` per candidate.
- score candidates against `P0` baseline and `P1` authority anchors.
- rank with objective:
  - `J2 = 0.60*d_s3_std + 0.20*d_s4_multi_zone + 0.10*d_s4_top1_down + 0.10*d_zone_top1_down`
  - where:
    - `d_s3_std = candidate_s3_std - p1_s3_std` (higher is better),
    - `d_s4_multi_zone = candidate_s4_multi_zone - p1_s4_multi_zone` (higher is better),
    - `d_s4_top1_down = p1_s4_top1 - candidate_s4_top1` (higher is better),
    - `d_zone_top1_down = p1_zone_top1 - candidate_zone_top1` (higher is better).
- hard veto:
  - any `S6` FAIL,
  - any conservation regression,
  - any guardrail breach from `P2.1`.

Definition of done:
- [x] at least one candidate reaches `S3 merchant_share_std_median >= 0.020`.
- [x] ranked sweep table + veto reasons are recorded.
- [x] one candidate is promoted to witness lane.

#### P2.4 - Witness Lock + Stability Smoke
Goal:
- prove selected `P2` candidate is deterministic on witness rerun and does not show obvious seed fragility.

Scope:
- rerun selected candidate once on seed `42` and compare deterministic metrics exactly.
- run smoke checks on additional seeds `{7, 101}` for directional stability
  (not full `P5` certification).
- keep structural rails (`S6/S7`) as strict vetoes.

Definition of done:
- [x] witness rerun reproduces deterministic metrics exactly on seed `42`.
- [x] smoke seeds preserve `S3` uplift direction and keep hard rails PASS.
- [x] no new RNG-accounting anomalies are introduced.

#### P2.5 - P2 Closeout and Lock Decision
Goal:
- close `P2` with explicit authority candidate and handoff to `P3`.

Scope:
- publish `P2` summary artifacts (sweep + witness + smoke).
- pin retained run-id set and prune superseded `P2` candidates.
- record explicit phase decision:
  - `UNLOCK_P3` or `HOLD_P2_REOPEN`.

Definition of done:
- [x] closure artifacts are emitted and referenced in build plan + notes.
- [x] retained run set is applied; superseded run folders pruned.
- [x] explicit close decision is recorded (`UNLOCK_P3` / `HOLD_P2_REOPEN`).

P2 execution outcome (2026-02-19):
- rerun-lane note:
  - initial `S3->S7` copy-lane attempt was vetoed by precondition coupling; execution pivoted to full `S0->S7` candidate reruns while varying only `s3_dispersion` knobs.
- selected authority candidate:
  - `C3` (`concentration_scale=0.65`, `alpha_temperature=1.00`, `merchant_jitter=0.00`, `merchant_jitter_clip=0.00`, `alpha_floor=1e-6`).
  - promoted run-id: `3f2e94f2d1504c249e434949659a496f`.
  - witness run-id: `6a3e291aae764c9bbf19b1c39443a68a` (exact metric replay: `PASS`).
  - smoke run-ids: `682c20d2343e4ffaae4d4057d5b23b9e` (`seed=7`), `8d31ca8eaeda4e7d8e1c0c2443cc89c7` (`seed=101`), directional stability: `PASS`.
- closure artifacts:
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p2_3_matrix_runs.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p2_3_sweep_summary.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p2_3_sweep_summary.md`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p2_4_runs.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p2_4_witness_summary.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p2_4_witness_summary.md`
- explicit phase decision:
  - `UNLOCK_P3`.

### P3 - S4 anti-collapse remediation (CF-3A-05)
Goal:
- prevent integerization collapse that turns escalated pairs monolithic.

Scope:
- tune deterministic floor/bump and rounding safeguards in S4 path.
- preserve strict per-pair count conservation.

Definition of done:
- [x] S4 multi-zone and top1-share B gates pass on witness seed.
- [x] conservation and schema checks remain PASS.
- [x] zone_alloc mirrors S4 with no drift.

P3 authority baseline (post-P2 lock):
- selected run-id: `3f2e94f2d1504c249e434949659a496f`.
- witness run-id: `6a3e291aae764c9bbf19b1c39443a68a`.
- smoke run-ids:
  - `682c20d2343e4ffaae4d4057d5b23b9e` (`seed=7`),
  - `8d31ca8eaeda4e7d8e1c0c2443cc89c7` (`seed=101`).
- current anchors:
  - `S4` escalated multi-zone rate: `0.922505`.
  - `S4` top1 median: `0.750000`.
  - `zone_alloc` top1 median: `0.750000`.

Execution posture:
- `P2`-locked `S2/S3` posture remains frozen; `P3` owns `S4` only.
- precheck-first posture:
  - if collapse-risk monitors are already green on witness+smoke, close `P3`
    as no-op lock (`P3_NOOP_LOCK`) to avoid unnecessary blast radius.
  - only open active tuning if monitors fail (`P3_ACTIVE_TUNE`).
- rerun law:
  - `P3.1` (precheck) is report-only (no rerun).
  - if active tuning opens, use full `S0->S7` reruns per candidate (contract-safe
    posture; avoids partial-lane precondition coupling observed in `P2`).

#### P3.1 - Collapse-Risk Fingerprint + Decision Gate
Goal:
- prove whether `CF-3A-05` work is still required after `P2`.

Scope:
- compute witness+smoke collapse-risk panel from current authority run set:
  - `S4 escalated_multi_zone_rate`,
  - `S4 top1_share_median`,
  - `S4 share_pairs_single_zone`,
  - `zone_alloc top1_share_median`.
- decision gate for active tuning:
  - open active lane only if any of:
    - `S4 escalated_multi_zone_rate < 0.90` on witness or `< 0.88` on smoke,
    - `S4 top1_share_median > 0.80` on witness or `> 0.82` on smoke,
    - `zone_alloc top1_share_median > 0.80` on witness or `> 0.82` on smoke,
    - `S4 share_pairs_single_zone > 0.20` on witness or `> 0.22` on smoke.

Definition of done:
- [x] collapse-risk panel is emitted for witness+smoke anchors.
- [x] explicit decision is recorded: `P3_NOOP_LOCK` or `P3_ACTIVE_TUNE`.
- [x] rerun scope for the chosen lane is pinned before execution.

#### P3.2 - Safeguard Knob Contract (Only If Active)
Goal:
- define bounded S4 safeguard knobs before any tuning run.

Scope:
- pin deterministic safeguard families:
  - minimum second-zone floor for escalated pairs above site-count threshold,
  - bounded near-threshold stochastic rounding (seeded; no wall-clock entropy).
- pin deterministic seed namespace and stable keying contract for S4 rounding.
- pin bounded candidate ranges and fail-closed defaults.

Definition of done:
- [x] knob families and ranges are documented (`N/A`, lane not opened under `P3_NOOP_LOCK`).
- [x] deterministic seed/keying contract is explicit (`N/A`, lane not opened under `P3_NOOP_LOCK`).
- [x] veto rails are pinned (`S6/S7`, conservation, `P2` non-regression) (`N/A`, lane not opened under `P3_NOOP_LOCK`).

#### P3.3 - Bounded S4 Safeguard Sweep (Only If Active)
Goal:
- identify one S4 safeguard candidate that improves anti-collapse resilience
  without degrading locked `P2` realism surfaces.

Scope:
- execute bounded candidate matrix (`<= 4` candidates) with full `S0->S7` reruns.
- candidate scoring objective:
  - `J3 = 0.50*d_s4_multi_zone + 0.25*d_s4_top1_down + 0.25*d_zone_top1_down`.
- hard veto:
  - any `S6/S7` FAIL,
  - any conservation/schema regression,
  - any guardrail breach (`S4 multi-zone < 0.85`, `S4 top1 > 0.80`, `zone_alloc top1 > 0.80`).

Definition of done:
- [x] ranked sweep table + veto reasons are emitted (`N/A`, lane not opened under `P3_NOOP_LOCK`).
- [x] one candidate is promoted (or lane is explicitly abandoned as unnecessary).
- [x] runtime evidence is recorded for each candidate run (`N/A`, lane not opened under `P3_NOOP_LOCK`).

#### P3.4 - Witness Lock + Smoke Stability
Goal:
- confirm selected `P3` posture is deterministic and stable.

Scope:
- witness replay on seed `42`.
- smoke seeds `{7,101}` directional checks.
- preserve `P2` locked surfaces:
  - no material regression on `S3 std`,
  - no degradation on S4/zone_alloc hard-gate posture.

Definition of done:
- [x] witness replay confirms deterministic metric stability.
- [x] smoke seeds keep rails PASS and directionally stable.
- [x] no new RNG/accounting anomalies appear in `S6`.

#### P3.5 - Closeout and Handoff
Goal:
- close `P3` with explicit authority posture and hand off cleanly.

Scope:
- publish `P3` summary artifacts (precheck, optional sweep, witness/smoke).
- prune superseded run-ids and retain minimal authority lineage.
- record explicit decision:
  - `UNLOCK_P4`,
  - `SKIP_P4_UNLOCK_P5` (if no escalation smoothing needed),
  - or `HOLD_P3_REOPEN`.

Definition of done:
- [x] closeout artifacts are emitted and referenced.
- [x] retained run set is applied; superseded runs pruned.
- [x] explicit handoff decision is recorded.

P3 execution outcome (2026-02-19):
- precheck decision:
  - `P3_NOOP_LOCK` (collapse-risk triggers not active on witness+smoke anchors).
- active tuning lane:
  - not opened (`P3.2/P3.3` N/A by decision gate).
- authority and stability evidence reused:
  - selected run-id: `3f2e94f2d1504c249e434949659a496f`
  - witness run-id: `6a3e291aae764c9bbf19b1c39443a68a`
  - smoke run-ids:
    - `682c20d2343e4ffaae4d4057d5b23b9e` (`seed=7`)
    - `8d31ca8eaeda4e7d8e1c0c2443cc89c7` (`seed=101`)
- emitted artifacts:
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p3_1_collapse_risk_panel.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p3_1_collapse_risk_panel.md`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p3_closeout_summary.json`
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p3_closeout_summary.md`
- explicit handoff decision:
  - `UNLOCK_P4` (S1 escalation-shape stretch remains open).

### P4 - S1 escalation-shape smoothing (CF-3A-04, conditional)
Goal:
- correct escalation curve coherence if S2/S3/S4 improvements still fail due gate-shape mismatch.

Scope:
- tune `zone_mixture_policy` monotonicity and forced/escalation balance.
- keep S1 as sole escalation authority and preserve domain completeness.

Definition of done:
- [x] escalation curve monotonicity improves without domain regressions.
- [x] downstream S4/zone_alloc realism improves or remains non-regressed.
- [x] policy/version lineage is sealed and recorded.

P4 authority baseline (post-P3 lock):
- selected run-id: `3f2e94f2d1504c249e434949659a496f`.
- witness run-id: `6a3e291aae764c9bbf19b1c39443a68a`.
- smoke run-ids:
  - `682c20d2343e4ffaae4d4057d5b23b9e` (`seed=7`),
  - `8d31ca8eaeda4e7d8e1c0c2443cc89c7` (`seed=101`).
- open gap owned by `P4`:
  - `S1 zone_count_curve_major_dip_max_abs = 0.501379` (witness/smoke),
  - `S1 zone_count_curve_monotonic_violations = 5` (witness/smoke).

Execution posture:
- `P2/P3` realism surfaces are frozen as non-regression rails:
  - keep `S3 merchant_share_std_median >= 0.020`,
  - keep `S4 multi-zone >= 0.85`, `S4 top1 <= 0.80`, `zone_alloc top1 <= 0.80`,
  - keep conservation + `S6/S7` strict PASS.
- bounded execution ladder:
  - start with policy-only smoothing under current S1 rule model,
  - only open S1 code-surface smoothing if policy-only lane cannot meet target.
- rerun law for this phase:
  - full `S0->S7` per candidate (contract-safe lane).

#### P4.1 - Target Envelope + S1 Shape Contract
Goal:
- pin measurable S1-shape targets and non-regression rails before tuning.

Scope:
- primary movement target (phase pass):
  - `S1 major_dip_max_abs <= 0.20` on witness seed,
  - `S1 monotonic_violations <= 2` on witness seed.
- stretch target (align to `3A-S07` trajectory):
  - `S1 major_dip_max_abs <= 0.10`,
  - `S1 major_dip_count_gt_010 = 0`.
- keep escalation-rate corridor to avoid pathological over/under-escalation:
  - witness escalation rate in `[0.55, 0.70]`.

Definition of done:
- [x] quantitative targets and rail thresholds are pinned.
- [x] non-regression rail set is explicit.
- [x] candidate budget and stop criteria are pinned.

#### P4.2 - Policy-Only Knob Contract (Low-Blast Lane)
Goal:
- define bounded policy knobs for S1 shape smoothing without code changes.

Scope:
- tune existing `zone_mixture_policy` controls:
  - `theta_mix`,
  - rule thresholds for `site_count_lt`, `zone_count_country_ge`, `site_count_ge`.
- pin bounded ranges:
  - `theta_mix in {0.20, 0.35, 0.50}`,
  - `site_count_lt in {2, 3, 4}`,
  - `zone_count_country_ge in {3, 4, 5}`,
  - `site_count_ge in {25, 35, 45}`.
- keep rule semantics and policy schema compatible in this lane.

Definition of done:
- [x] bounded knob families and ranges are listed.
- [x] candidate matrix cardinality is capped (`<= 6`).
- [x] veto rails are pinned before first candidate run.

#### P4.3 - Policy-Only Sweep + Ranking
Goal:
- find one policy-only candidate that materially reduces S1 shape incoherence.

Scope:
- execute bounded candidate set (`<= 6`) with full `S0->S7` reruns.
- rank with objective:
  - `J4 = 0.70*d_s1_dip_down + 0.30*d_s1_mono_viol_down`,
  - where:
    - `d_s1_dip_down = p3_major_dip_max_abs - candidate_major_dip_max_abs`,
    - `d_s1_mono_viol_down = p3_monotonic_violations - candidate_monotonic_violations`.
- hard veto:
  - any `S6/S7` FAIL,
  - any conservation/schema regression,
  - any `P2/P3` non-regression breach.

Definition of done:
- [x] ranked sweep table + veto reasons are emitted.
- [x] one candidate is promoted, or lane is explicitly marked insufficient.
- [x] explicit decision recorded: `P4_POLICY_LOCK` or `P4_NEEDS_CODE_SMOOTHING`.

#### P4.4 - Smooth-Band S1 Lane (Only If Needed)
Goal:
- open code+policy smoothing only if policy-only lane cannot meet `P4.1` targets.

Scope:
- add additive smooth-band escalation controls in S1 policy/runner:
  - monotonic `tz_count` escalation band,
  - bounded `site_count` effect (slope + cap).
- preserve deterministic decision logic and sealed-input contract.
- run bounded reruns (`<= 4`) and re-rank with `J4`.

Definition of done:
- [x] additive smooth-band controls are schema-valid and deterministic.
- [x] bounded code-smoothing sweep artifacts are emitted.
- [x] one candidate is promoted or phase is marked reopen-required.

#### P4.5 - Witness Lock + Smoke Stability
Goal:
- prove selected `P4` posture is stable and non-regressive.

Scope:
- witness replay on seed `42`.
- smoke checks on seeds `{7,101}`.
- enforce both S1-shape movement and `P2/P3` non-regression rails.

Definition of done:
- [x] witness run confirms selected S1-shape movement.
- [x] smoke seeds preserve direction and keep hard rails PASS.
- [x] no new anomalies appear in `S6`.

#### P4.6 - Closeout and Handoff
Goal:
- close `P4` with explicit authority posture and route to certification lane.

Scope:
- publish `P4` summary artifacts (sweeps + witness/smoke + decision).
- prune superseded run-ids; retain authority lineage.
- record explicit decision:
  - `UNLOCK_P5`,
  - `UNLOCK_P5_BEST_EFFORT`,
  - or `HOLD_P4_REOPEN`.

Definition of done:
- [x] closeout artifacts are emitted and referenced.
- [x] retained run set is applied; superseded runs pruned.
- [x] explicit handoff decision is recorded.

P4 execution outcome:
- `P4.3` policy-only lane decision:
  - `P4_NEEDS_CODE_SMOOTHING`.
- `P4.4` code-smoothing lane decision:
  - `P4_NEEDS_CODE_SMOOTHING` (strict phase target still unmet under rails),
  - selected rail-safe uplift candidate: `P4K2` / run
    `58df4758c04040d796d38a08c481b555`.
- selected witness/smoke authority set (`P4.5`):
  - witness run (`seed=42`): `6977c4ef82cc4f01ae76549047c08f51`,
  - smoke run (`seed=7`): `b57d89c4bc0741389d4980201eb51ffe`,
  - smoke run (`seed=101`): `d2751ee567fa4935ba572c9644e9e901`.
- measured movement vs anchor (`3f2e94f2d1504c249e434949659a496f`):
  - `S1 major_dip_max_abs`: `0.501379 -> 0.336092` (improved),
  - `S1 monotonic_violations`: `5 -> 5` (no movement),
  - `S4 multi-zone` preserved above non-regression rail across seedpack.
- explicit handoff decision:
  - `UNLOCK_P5_BEST_EFFORT`.
- retained run-id set after `P4.6` prune:
  - `81599ab107ba4c8db7fc5850287360fe`,
  - `3f2e94f2d1504c249e434949659a496f`,
  - `58df4758c04040d796d38a08c481b555`,
  - `6977c4ef82cc4f01ae76549047c08f51`,
  - `b57d89c4bc0741389d4980201eb51ffe`,
  - `d2751ee567fa4935ba572c9644e9e901`.
- artifacts:
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p4_3_sweep_summary.json`,
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p4_4_matrix_runs.json`,
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p4_4_sweep_summary.json`,
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p4_5_runs.json`,
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p4_5_witness_summary.json`,
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p4_closeout_summary.json`.

### P5 - Integrated certification (`B`/`B+`) across seedpack
Goal:
- run full seedpack and determine certified grade.

Scope:
- execute required states per rerun matrix on `{42,7,101,202}`.
- evaluate hard gates, stretch gates, and cross-seed stability.

Definition of done:
- [x] cross-seed certification artifact is emitted.
- [x] explicit verdict recorded: `PASS_BPLUS`, `PASS_B`, or `FAIL_REALISM`.
- [x] freeze candidate and supporting evidence pack are pinned.

P5 authority baseline (post-P4 close):
- `P4` handoff decision: `UNLOCK_P5_BEST_EFFORT`.
- locked candidate posture:
  - variant `P4K2` / run `58df4758c04040d796d38a08c481b555`.
- witness/smoke authority runs:
  - `6977c4ef82cc4f01ae76549047c08f51` (`seed=42`),
  - `b57d89c4bc0741389d4980201eb51ffe` (`seed=7`),
  - `d2751ee567fa4935ba572c9644e9e901` (`seed=101`).
- locked known gap carried into certification:
  - `S1 monotonic_violations` remains above P4 stretch target.

Execution posture:
- no further tuning in `P5`; certification is readout-only on the locked `P4K2`
  posture.
- deterministic rerun requirement per seed:
  - staged run receipt -> full `S0->S7` chain -> baseline/candidate scoring.
- smoke seed input workaround remains bounded and local:
  - if staged run root lacks `1A/outlet_catalogue/seed=<seed>`, alias from
    `seed=42` payload path inside that run root only (bytes unchanged).
- hard rails remain fail-closed in certification:
  - all seeds must keep `S6/S7` PASS and `P2/P3` non-regression rails.

#### P5.1 - Certification Contract Lock
Goal:
- pin exact certification contract before execution.

Scope:
- lock certification seeds to `{42,7,101,202}`.
- lock required lane to full `S0->S7` per seed.
- lock verdict semantics:
  - `PASS_BPLUS`: all hard + stretch gates pass on all seeds.
  - `PASS_B`: all hard gates pass on all seeds, stretch may remain open.
  - `FAIL_REALISM`: any hard gate fail on any seed, or any `S6/S7` fail.

Definition of done:
- [x] seedpack, run lane, and verdict semantics are pinned.
- [x] no open tuning knobs remain in `P5`.
- [x] runtime budget for certification lane is pinned.

#### P5.2 - Seedpack Execution + Scoring
Goal:
- execute the full seedpack on locked posture and score each run.

Scope:
- for each seed in `{42,7,101,202}`:
  - stage run root under `runs/fix-data-engine/segment_3A`,
  - apply bounded seed-path alias workaround only if required,
  - execute `make segment3a RUNS_ROOT=... RUN_ID=...`,
  - emit baseline metrics + candidate-vs-anchor score artifacts.
- runtime budget gate:
  - target `< 90s` per seed,
  - target `< 8m` total for `P5` seedpack lane.

Definition of done:
- [x] all 4 seed runs complete with emitted score artifacts.
- [x] each seed has explicit `S6/S7` status and rail status captured.
- [x] runtime evidence is recorded vs budget.

#### P5.3 - Integrated Aggregation + Stability Readout
Goal:
- compute single integrated realism view for verdicting.

Scope:
- aggregate per-seed hard/stetch gate outcomes and key realism metrics.
- compute cross-seed dispersion for key surfaces:
  - `S1 major_dip_max_abs`,
  - `S3 merchant_share_std_median`,
  - `S4 escalated_multi_zone_rate`,
  - `S4/zone_alloc top1 median`.
- emit integrated certification artifact:
  - `segment3a_p5_certification_summary.json`,
  - `segment3a_p5_certification_summary.md`.

Definition of done:
- [x] integrated certification summary artifacts are emitted.
- [x] per-seed + aggregate gate matrix is explicit.
- [x] cross-seed stability readout is included in the summary.

#### P5.4 - Verdict + Freeze Candidate Decision
Goal:
- finalize certified grade and freeze posture for `3A`.

Scope:
- apply locked verdict semantics to integrated summary:
  - `PASS_BPLUS`, `PASS_B`, or `FAIL_REALISM`.
- if verdict is pass (`B` or `B+`), pin final freeze candidate run-id.
- if verdict is fail, pin explicit best-effort freeze posture for `P6`.

Definition of done:
- [x] explicit verdict is recorded.
- [x] freeze candidate run-id (or fail rationale) is recorded.
- [x] next handoff decision to `P6` is explicit.

#### P5.5 - Evidence Pack + Retention Handshake
Goal:
- close certification lane with reproducible evidence and bounded storage.

Scope:
- publish retained evidence set (runs + reports + score artifacts).
- prepare explicit keep-set for `P6` freeze/prune.
- ensure implementation notes + logbook capture final `P5` decision trail.

Definition of done:
- [x] evidence pack paths are complete and reproducible.
- [x] keep-set for `P6` is defined.
- [x] decision trail is fully documented.

P5 execution outcome:
- certification runs (`S0->S7`, locked `P4K2` posture):
  - `seed=42` -> `d516f89608ed43ad8ea1018fbb33d9d8`,
  - `seed=7` -> `1b136a61051343c0bc1638397dbb3416`,
  - `seed=101` -> `4029ada5ebd047de991124f372179808`,
  - `seed=202` -> `77f0345ea9d3460c929bd26e99eb522a`.
- aggregate verdict:
  - `FAIL_REALISM`.
- failure cause under locked verdict contract:
  - seed `202` breached hard gate `3A-V04_s3_merchant_share_std_median` while
    `S6/S7` remained PASS on all seeds.
- freeze candidate run-id (best-effort authority witness):
  - `d516f89608ed43ad8ea1018fbb33d9d8` (`seed=42`).
- runtime budget evidence:
  - observed max per-seed runtime: `44.876s` (`<= 90s` target),
  - observed total runtime: `174.727s` (`<= 480s` target).
- explicit handoff decision:
  - `UNLOCK_P6_FREEZE_BEST_EFFORT_BELOW_B`.
- retained evidence pack:
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p5_runs.json`,
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p5_certification_summary.json`,
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p5_certification_summary.md`.
- keep-set prepared for `P6` freeze/prune:
  - `81599ab107ba4c8db7fc5850287360fe`,
  - `3f2e94f2d1504c249e434949659a496f`,
  - `58df4758c04040d796d38a08c481b555`,
  - `6977c4ef82cc4f01ae76549047c08f51`,
  - `b57d89c4bc0741389d4980201eb51ffe`,
  - `d2751ee567fa4935ba572c9644e9e901`,
  - `d516f89608ed43ad8ea1018fbb33d9d8`,
  - `1b136a61051343c0bc1638397dbb3416`,
  - `4029ada5ebd047de991124f372179808`,
  - `77f0345ea9d3460c929bd26e99eb522a`.

### P6 - Freeze and handoff
Goal:
- close 3A remediation cycle and hand off to next segment cleanly.

Scope:
- record final freeze status and retained authority run-id.
- prune superseded failed run folders while preserving evidence.

Definition of done:
- [x] freeze status recorded (`FROZEN_CERTIFIED_BPLUS`, `FROZEN_CERTIFIED_B`, or `FROZEN_BEST_EFFORT_BELOW_B`).
- [x] retained evidence paths are complete and reproducible.
- [x] implementation notes and logbook include full decision trail.

P6 execution outcome:
- freeze status:
  - `FROZEN_BEST_EFFORT_BELOW_B`.
- freeze authority run-id:
  - `d516f89608ed43ad8ea1018fbb33d9d8` (`seed=42` witness).
- prune execution:
  - command: `tools/prune_run_folders_keep_set.py --yes`,
  - result: `candidate_count=0` (no-op; run root already matched keep-set).
- retained run-id set:
  - `81599ab107ba4c8db7fc5850287360fe`,
  - `3f2e94f2d1504c249e434949659a496f`,
  - `58df4758c04040d796d38a08c481b555`,
  - `6977c4ef82cc4f01ae76549047c08f51`,
  - `b57d89c4bc0741389d4980201eb51ffe`,
  - `d2751ee567fa4935ba572c9644e9e901`,
  - `d516f89608ed43ad8ea1018fbb33d9d8`,
  - `1b136a61051343c0bc1638397dbb3416`,
  - `4029ada5ebd047de991124f372179808`,
  - `77f0345ea9d3460c929bd26e99eb522a`.
- retained evidence pack:
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p5_runs.json`,
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p5_certification_summary.json`,
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p5_certification_summary.md`,
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p6_freeze_summary.json`,
  - `runs/fix-data-engine/segment_3A/reports/segment3a_p6_freeze_summary.md`.
- explicit handoff decision:
  - `SEGMENT_3A_FROZEN_MOVE_TO_3B`.
