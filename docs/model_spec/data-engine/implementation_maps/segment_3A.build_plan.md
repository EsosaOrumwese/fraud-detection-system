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
- [ ] S3 dispersion hard gate (`median std >= 0.02`) passes on witness seed.
- [ ] S3 RNG accounting checks remain PASS.
- [ ] no downstream S4 conservation regressions introduced.

### P3 - S4 anti-collapse remediation (CF-3A-05)
Goal:
- prevent integerization collapse that turns escalated pairs monolithic.

Scope:
- tune deterministic floor/bump and rounding safeguards in S4 path.
- preserve strict per-pair count conservation.

Definition of done:
- [ ] S4 multi-zone and top1-share B gates pass on witness seed.
- [ ] conservation and schema checks remain PASS.
- [ ] zone_alloc mirrors S4 with no drift.

### P4 - S1 escalation-shape smoothing (CF-3A-04, conditional)
Goal:
- correct escalation curve coherence if S2/S3/S4 improvements still fail due gate-shape mismatch.

Scope:
- tune `zone_mixture_policy` monotonicity and forced/escalation balance.
- keep S1 as sole escalation authority and preserve domain completeness.

Definition of done:
- [ ] escalation curve monotonicity improves without domain regressions.
- [ ] downstream S4/zone_alloc realism improves or remains non-regressed.
- [ ] policy/version lineage is sealed and recorded.

### P5 - Integrated certification (`B`/`B+`) across seedpack
Goal:
- run full seedpack and determine certified grade.

Scope:
- execute required states per rerun matrix on `{42,7,101,202}`.
- evaluate hard gates, stretch gates, and cross-seed stability.

Definition of done:
- [ ] cross-seed certification artifact is emitted.
- [ ] explicit verdict recorded: `PASS_BPLUS`, `PASS_B`, or `FAIL_REALISM`.
- [ ] freeze candidate and supporting evidence pack are pinned.

### P6 - Freeze and handoff
Goal:
- close 3A remediation cycle and hand off to next segment cleanly.

Scope:
- record final freeze status and retained authority run-id.
- prune superseded failed run folders while preserving evidence.

Definition of done:
- [ ] freeze status recorded (`FROZEN_CERTIFIED_BPLUS`, `FROZEN_CERTIFIED_B`, or `FROZEN_BEST_EFFORT_BELOW_B`).
- [ ] retained evidence paths are complete and reproducible.
- [ ] implementation notes and logbook include full decision trail.
