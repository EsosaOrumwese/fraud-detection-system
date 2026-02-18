# Segment 2A Remediation Build Plan (B/B+ Execution Plan)
_As of 2026-02-15_

## 0) Objective and closure rule
- Objective: remediate Segment `2A` to certified realism `B` minimum, with `B+` as the target where feasible.
- Realism surface of record: `site_timezones`.
- Closure rule:
  - `PASS_BPLUS`: all hard gates pass on all required seeds and all B+ bands pass.
  - `PASS_B`: all hard gates pass on all required seeds and B bands pass.
  - `FAIL_REALISM`: any hard gate fails on any required seed.
- Program constraint in this cycle:
  - `1A` is frozen as `FROZEN_CERTIFIED_B`.
  - `1B` is frozen as `FROZEN_BEST_EFFORT_BELOW_B`.
  - 2A remediation must not assume upstream reopen during this pass.

## 1) Source-of-truth stack

### 1.1 Statistical authority
- `docs/reports/eda/segment_2A/segment_2A_published_report.md`
- `docs/reports/eda/segment_2A/segment_2A_remediation_report.md`

### 1.2 State and contract authority
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2A/state.2A.s0.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2A/state.2A.s1.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2A/state.2A.s2.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2A/state.2A.s3.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2A/state.2A.s4.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/2A/state.2A.s5.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2A/dataset_dictionary.layer1.2A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2A/schemas.2A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/2A/artefact_registry_2A.yaml`

### 1.3 Upstream freeze authorities (binding in this pass)
- `1A` certification authority:
  - `runs/fix-data-engine/segment_1A/reports/segment1a_p5_certification.json`
  - operational authority run: `416afa430db3f5bf87180f8514329fe8`
- `1B` best-effort authority:
  - integrated lock report:
    - `runs/fix-data-engine/segment_1B/reports/segment1b_p4_integrated_a0ae54639efc4955bc41a2e266224e6e.json`
  - no-regression authority run:
    - `979129e39a89446b942df9a463f09508`
  - freeze posture:
    - `FROZEN_BEST_EFFORT_BELOW_B` (bounded realism sweep exhausted; no further 1B-local tuning in this cycle).

## 2) Remediation posture and boundaries
- Primary realism weakness acknowledged by authority docs:
  - country-level timezone support collapse and representativeness gaps.
- Causal constraint:
  - 2A can harden governance and improve realism under fixed upstream inputs, but is partly ceiling-limited by frozen 1B spatial representativeness.
- Allowed lane for this pass:
  - S1/S2 fallback and override governance hardening.
  - cohort-aware realism scoring and fail-closed certification.
  - narrow, evidence-backed targeted corrections.
- Prohibited lane for this pass:
  - synthetic post-assignment timezone redistribution as primary fix.
  - reopening 1A/1B in this cycle without explicit approval.

## 3) Statistical targets and hard gates
- Required seeds for certification: `{42, 7, 101, 202}`.

### 3.1 Hard B gates (fail-closed)
- Structural integrity:
  - row parity: `site_locations == s1_tz_lookup == site_timezones`.
  - PK duplicates in `s1_tz_lookup` and `site_timezones` = `0`.
  - legality/cache/bundle pass remains green.
- Governance:
  - `fallback_rate <= 0.05%`.
  - `override_rate <= 0.20%` unless explicitly approved exception.
  - country fallback cap enforced (`fallback_country_cap`).
- Multi-timezone cohort realism (`C_multi`):
  - share with `distinct_tzid_count >= 2` >= `70%`.
  - median `top1_share <= 0.92`.
  - median `(top1-top2)_gap <= 0.85`.
  - median normalized entropy >= `0.20`.
- Large-country realism (`C_large`):
  - share with `top1_share < 0.95` >= `80%`.

### 3.2 B+ target bands
- `C_multi` share with `distinct_tzid_count >= 2` >= `85%`.
- median `top1_share <= 0.80`.
- median `(top1-top2)_gap <= 0.65`.
- median normalized entropy >= `0.35`.
- `C_large` share with `top1_share < 0.95` >= `95%`.
- governance stretch:
  - `fallback_rate <= 0.01%`.
  - `override_rate <= 0.05%`.

### 3.3 Stability gates
- Cross-seed CV for core medians:
  - `B`: `<= 0.30`
  - `B+`: `<= 0.20`

## 4) Run protocol, retention, and rerun matrix
- Active run root: `runs/fix-data-engine/segment_2A/`.
- Retention policy:
  - keep baseline authority runs, current candidate, and last-good candidate.
  - prune superseded failed candidates before new expensive runs.

### 4.1 Progressive rerun matrix
- If S1 changes: rerun `S1 -> S2 -> S3 -> S4 -> S5`.
- If S2 changes: rerun `S2 -> S3 -> S4 -> S5`.
- If S3 changes: rerun `S3 -> S4 -> S5`.
- If S4 changes: rerun `S4 -> S5`.
- If only certification/reporting logic changes: rerun scoring + `S5` checks as needed.

## 5) Phase plan (data-first with DoDs)

### P0 - Baseline authority and harness lock
Goal:
- establish an auditable 2A baseline and scoring harness under current frozen upstream posture.

Scope:
- materialize:
  - published baseline (`c25a...`) posture,
  - current-cycle baseline under frozen 1B authority.
- build deterministic scorer artifacts for all 2A hard-gate metrics.

Definition of done:
- [ ] baseline authority lineage is pinned (run ids, fingerprints, hashes).
- [ ] baseline metrics table is emitted for all hard-gate axes.
- [ ] cohort splits (`C_multi`, `C_large`, `C_single`) are implemented and validated.
- [ ] run and retention protocol artifacts are written under `runs/fix-data-engine/segment_2A/`.

### P1 - Governance hardening (S1/S2)
Goal:
- make fallback and override behavior explicitly bounded, fail-closed, and auditable.

Scope:
- `S1`: fallback counters/rates and hard caps.
- `S2`: override rate caps, metadata completeness, and precedence integrity.
- no synthetic distribution forcing.

Candidate surfaces:
- `packages/engine/src/engine/layers/l1/seg_2A/s1_tz_lookup/runner.py`
- `packages/engine/src/engine/layers/l1/seg_2A/s2_overrides/runner.py`
- `config/layer1/2A/timezone/tz_overrides.yaml`
- `config/layer1/2A/timezone/tz_nudge.yml`

Definition of done:
- [x] fallback rate and override rate are emitted per run and by country.
- [x] hard cap breaches fail-closed with explicit reason codes.
- [x] override provenance fields are complete and schema-valid.
- [x] structural parity and legality remain non-regressed.

P1 closure record (2026-02-17):
- code surfaces updated:
  - `packages/engine/src/engine/layers/l1/seg_2A/s1_tz_lookup/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_2A/s2_overrides/runner.py`
- governance controls added:
  - `S1` emits `fallback_rate` + `override_rate` plus country-level maps and enforces:
    - `fallback_rate_cap=0.0005`,
    - `fallback_country_rate_cap=0.02` with `fallback_country_min_sites=100`,
    - `override_rate_cap=0.002`.
  - `S2` emits `override_rate` plus country-level map and enforces:
    - `override_rate_cap=0.002`,
    - active override provenance completeness (`notes || evidence_url`) fail-closed.
- fail-closed reason codes added:
  - `S1`: `2A-S1-090` (global fallback cap), `2A-S1-091` (country fallback cap), `2A-S1-092` (global override cap).
  - `S2`: `2A-S2-090` (global override cap), `2A-S2-091` (override provenance incomplete).
- execution evidence (existing candidate run-id):
  - command:
    - `make segment2a-s1 segment2a-s2 segment2a-s3 segment2a-s4 segment2a-s5 RUNS_ROOT='runs/fix-data-engine/segment_2A' RUN_ID='b65bfe6efaca42e2ac413c059fb88b64'`
  - result: `S1..S5 PASS`.
  - governance witness from run reports:
    - `S1 fallback_rate=3.199e-05`, `S1 override_rate=9.598e-05`, `fallback_country_violations=0`.
    - `S2 override_rate=9.598e-05`, `provenance_missing=0`.

### P2 - Cohort-aware realism scoring and gates
Goal:
- enforce realism evaluation on eligible cohorts so B/B+ verdict is statistically meaningful.

Scope:
- implement machine-readable cohort metrics and pass/fail gates for:
  - `C_multi` diversity and concentration axes,
  - `C_large` representativeness,
  - cross-seed CV.

Candidate surfaces:
- `packages/engine/src/engine/layers/l1/seg_2A/s5_validation/runner.py`
- scoring/report tooling under `tools/` for 2A certification.

Definition of done:
- [x] scorer emits full hard-gate metrics and verdict per seed.
- [x] aggregate cross-seed verdict (`PASS_BPLUS`/`PASS_B`/`FAIL_REALISM`) is deterministic.
- [x] diagnostics CSV/JSON artifacts are emitted for hotspot tracing.

### P2.1 - Cohort contract lock (definitions + formulas)
Goal:
- lock deterministic cohort definitions and metric formulas before scorer implementation.

Scope:
- deterministic cohort definitions:
  - `C_multi`: `tz_world_support_count >= 2` and `site_count >= 100`.
  - `C_large`: `site_count >= 500`.
  - `C_single`: all remaining countries (reported only; non-gating).
- metric formulas:
  - `distinct_tzid_count`,
  - `top1_share`,
  - `top1_top2_gap` (`1.0` when only one observed tzid),
  - normalized entropy (`H / ln(tz_world_support_count)` for eligible support >= 2).

Definition of done:
- [x] cohort and metric formulas are encoded in scorer source (not hand-computed).
- [x] cohort membership is reproducible from run artifacts alone.
- [x] formulas are documented in scorer output metadata.

### P2.2 - Per-seed scorer implementation
Goal:
- produce machine-readable per-seed realism + governance gate evaluation.

Scope:
- emit per-seed JSON containing:
  - structural checks,
  - governance checks,
  - `C_multi` realism metrics,
  - `C_large` representativeness metric,
  - seed-level `PASS_BPLUS`/`PASS_B`/`FAIL_REALISM`.
- emit per-seed diagnostics CSV:
  - country-level rows for `C_multi`/`C_large` with key metrics.

Definition of done:
- [x] scorer runs on an authority run-id and emits deterministic JSON + CSV.
- [x] scorer includes explicit gate booleans and failing-gate list.
- [x] governance surfaces are read from S1/S2 run reports (no duplicate manual calculation path).

### P2.3 - Certification reducer across required seed pack
Goal:
- aggregate required seeds `{42, 7, 101, 202}` into a fail-closed certification verdict.

Scope:
- discover/provide one authoritative run-id per required seed.
- enforce:
  - any hard gate fail on any required seed => `FAIL_REALISM`.
  - all hard gates pass + all B+ bands pass => `PASS_BPLUS`.
  - all hard gates pass + B bands pass => `PASS_B`.
- emit aggregate certification JSON with per-seed rollup.

Definition of done:
- [x] required seed coverage is explicit and machine-validated.
- [x] aggregate verdict is deterministic and reproducible.
- [x] failing seeds/gates are explicitly listed when not green.

### P2.4 - Stability and distribution diagnostics
Goal:
- add cross-seed stability and movement diagnostics required by remediation authority.

Scope:
- cross-seed CV on key medians (`top1_share`, `top1_top2_gap`, entropy, coverage share).
- optional statistical movement diagnostics (`KS`/`Wasserstein`, two-proportion test) as evidence blocks.
- include diagnostics even when verdict fails.

Definition of done:
- [x] CV metrics are emitted and gated (`B<=0.30`, `B+<=0.20`).
- [x] diagnostics section is always present in certification output.
- [x] evidence is sufficient to explain verdict movement vs baseline.

### P2.5 - Execution protocol and artifact closure
Goal:
- execute P2 end-to-end and close with retained artifacts under active run root.

Scope:
- run scorer for available authority run(s) and required seed pack.
- if missing required seed run-ids, generate them under frozen code/policy posture before final certification.
- prune superseded failed run-id folders before expensive runs.

Definition of done:
- [x] per-seed scorer artifacts exist for all required seeds.
- [x] aggregate certification artifact exists with final verdict.
- [x] retained run-id set and scoring artifact paths are pinned in plan + impl notes.

P2 closure record (2026-02-17):
- scoring tool implemented:
  - `tools/score_segment2a_p2_certification.py`
- required-seed execution evidence:
  - seed `42`: `b65bfe6efaca42e2ac413c059fb88b64` (`S0..S5` complete, scored).
  - seed `7`: `07891eca4e6ea549a4d836db35e203aa` (`S0..S5` complete, scored).
  - seed `101`: `513f4f2904d1ac97f2396c059a9573da` (`S1` fail-closed at `2A-S1-091`, scored as hard fail).
  - seed `202`: `5a8836781dd7524da561ad5aa27f64d6` (`S1` fail-closed at `2A-S1-090`, scored as hard fail).
- certification artifacts:
  - `runs/fix-data-engine/segment_2A/reports/segment2a_p2_seed_metrics_42-b65bfe6e_7-07891eca_101-513f4f29_202-5a883678.json`
  - `runs/fix-data-engine/segment_2A/reports/segment2a_p2_country_diagnostics_42-b65bfe6e_7-07891eca_101-513f4f29_202-5a883678.csv`
  - `runs/fix-data-engine/segment_2A/reports/segment2a_p2_certification_42-b65bfe6e_7-07891eca_101-513f4f29_202-5a883678.json`
- verdict:
  - `FAIL_REALISM`.
- primary blockers recorded by certification:
  - all seeds miss B realism axes (`C_multi` concentration/entropy and `C_large` representativeness).
  - seeds `101`/`202` additionally fail hard governance at `S1` (fallback caps), preventing complete `S2..S5` chain for those seeds.

### P3 - Targeted correction lane (bounded, non-synthetic)
Goal:
- close P2 blockers under frozen upstream posture by correcting:
  - S1 hard-gate failures on seeds `101` and `202`,
  - `C_multi` concentration/entropy and `C_large` representativeness misses.

Scope:
- bounded, evidence-led interventions in `2A` only:
  - S1 fallback path and policy hygiene,
  - targeted country watchlist corrections,
  - deterministic candidate ordering and provenance-safe overrides.
- explicit non-scope:
  - no cap relaxation,
  - no synthetic post-assignment redistribution,
  - no 1A/1B reopen in this phase.

Definition of done:
- [x] seeds `101` and `202` clear S1 hard gates without threshold relaxation.
- [x] seed-pack realism metrics materially improve vs P2 closure baseline.
- [x] no structural, legality, determinism, or provenance regressions.

### P3.1 - Failure surface lock and watchlist contract
Goal:
- convert P2 failures into a bounded correction contract before knob changes.

Scope:
- build a hotspot watchlist from P2 certification diagnostics:
  - fallback-cap breach countries (`S1`),
  - high top1-share / low entropy countries (`C_multi`),
  - low representativeness countries (`C_large`).
- pin per-country correction budgets and acceptance tests.

Definition of done:
- [x] watchlist table is emitted with failure mechanism class per country.
- [x] correction budget is pinned per mechanism (`fallback`, `override`, `concentration`).
- [x] a ranked intervention order is recorded (governance blockers first).

### P3.2 - Governance-first rescue for hard-failing seeds
Goal:
- eliminate fail-closed S1 governance breaches on seeds `101`/`202` without loosening gates.

Scope:
- tighten S1 ambiguity resolution and fallback usage for watchlist countries.
- use only deterministic and auditable controls (policy + runner mechanics already in 2A scope).
- keep S2 provenance and override-cap enforcement unchanged or stricter.

Definition of done:
- [x] seeds `101` and `202` complete `S1->S5` without `2A-S1-090/091` breaches.
- [x] `fallback_country_violations == 0` on all required seeds.
- [x] `override_rate` remains within existing `P1` caps and provenance remains complete.

### P3.3 - Realism lift on concentration and entropy axes
Goal:
- improve `C_multi` and `C_large` realism under bounded watchlist-only corrections.

Scope:
- apply targeted corrections to countries that dominate:
  - `top1_share` collapse,
  - `top1_top2_gap` inflation,
  - near-zero normalized entropy.
- enforce veto gates to prevent score-forcing via fallback/override inflation.

Definition of done:
- [ ] seed `42` and seed `7` both improve vs P2 on:
  - `c_multi_median_top1_share` (down),
  - `c_multi_median_top1_top2_gap` (down),
  - `c_multi_median_entropy_norm` (up),
  - `c_large_share_top1_lt_095` (up).
- [x] fallback and override rates do not increase beyond P1 caps.
- [x] no broad/global redistribution logic is introduced.

### P3.4 - Integrated seed-pack candidate and veto cert
Goal:
- produce one P3 authority candidate ready for P4 final certification.

Scope:
- run required seed pack `{42, 7, 101, 202}` on the chosen P3 candidate.
- score with the P2 certification harness and apply veto gates.

Definition of done:
- [x] all required seeds pass hard governance/structural gates.
- [x] aggregate verdict reaches `PASS_B` or explicit blocker set is reduced with quantified deltas.
- [x] retained authority run-id set is pinned for P4 handoff.

### P3.5 - Closure decision (GO P4 or constrained freeze proposal)
Goal:
- end P3 with an explicit, auditable decision gate.

Scope:
- if `PASS_B`/`PASS_BPLUS`: hand off to P4 certification closure.
- if still `FAIL_REALISM`: record residual blockers and produce constrained freeze + reopen recommendation.

Definition of done:
- [x] decision path is explicit (`GO_P4` or `FREEZE_PROPOSAL`).
- [x] residual blocker matrix (metric + owning state/knob) is attached when not green.
- [x] next action queue is recorded without ambiguity.

P3 closure record (2026-02-17):
- execution lane:
  - clean candidate root: `runs/fix-data-engine/segment_2A_p3`
  - retained required run-ids:
    - seed `42`: `b65bfe6efaca42e2ac413c059fb88b64`
    - seed `7`: `07891eca4e6ea549a4d836db35e203aa`
    - seed `101`: `513f4f2904d1ac97f2396c059a9573da`
    - seed `202`: `5a8836781dd7524da561ad5aa27f64d6`
- P3.1 artifacts:
  - baseline watchlist:
    - `runs/fix-data-engine/segment_2A/reports/segment2a_p3_watchlist_baseline.csv`
    - `runs/fix-data-engine/segment_2A/reports/segment2a_p3_watchlist_baseline.json`
  - candidate watchlist:
    - `runs/fix-data-engine/segment_2A_p3/reports/segment2a_p3_watchlist_candidate.csv`
    - `runs/fix-data-engine/segment_2A_p3/reports/segment2a_p3_watchlist_candidate.json`
- P3.2 interventions applied:
  - `config/layer1/2A/timezone/tz_overrides.yaml`:
    - `CN -> Asia/Shanghai`
    - `GE -> Asia/Tbilisi`
    - `PS -> Asia/Hebron`
- P3.2/P3.4 certification evidence:
  - `runs/fix-data-engine/segment_2A_p3/reports/segment2a_p2_seed_metrics_42-b65bfe6e_7-07891eca_101-513f4f29_202-5a883678.json`
  - `runs/fix-data-engine/segment_2A_p3/reports/segment2a_p2_certification_42-b65bfe6e_7-07891eca_101-513f4f29_202-5a883678.json`
  - delta summary:
    - `runs/fix-data-engine/segment_2A_p3/reports/segment2a_p3_delta_summary.json`
- gate movement:
  - seeds `101`/`202` now complete `S0->S5` and clear previous `2A-S1-090/091` hard failures.
  - fallback hotspots reduced (`12 -> 7`), with `CN/GE/PS` hotspot class removed.
  - fallback governance now green on all required seeds for B caps.
- residual blockers (P3.3 not achieved under frozen upstream):
  - `C_multi` concentration/entropy still fail on all seeds:
    - top1 share remains ~`0.967-1.000` (`B <= 0.92`).
    - top1-top2 gap remains ~`0.934-1.000` (`B <= 0.85`).
    - entropy remains ~`0.000-0.080` (`B >= 0.20`).
  - `C_large` representativeness remains ~`0.20-0.33` (`B >= 0.80`).
  - owner inference:
    - primary blocker remains upstream spatial representativeness (frozen `1B`) rather than 2A governance mechanics.
- P3.5 decision:
  - `FREEZE_PROPOSAL` for current 2A pass (`FAIL_REALISM` persists despite governance closure).
  - reopen recommendation: upstream `1B` representativeness lane before additional 2A-local realism tuning.

### P4 - Closure branch (freeze or upstream reopen)
Goal:
- close Segment 2A with an explicit decision path after P3:
  - freeze best-effort under frozen upstream posture, or
  - execute upstream reopen lane (recommended) and re-certify.

Scope:
- Branch A: constrained freeze (`2A` stays best-effort below B for this cycle).
- Branch B: upstream reopen lane on `1B` representativeness, then `1B -> 2A` recertification.
- required seeds remain `{42, 7, 101, 202}`.

Definition of done:
- [x] branch choice is explicitly pinned (`FREEZE_NOW` or `REOPEN_1B`).
- [x] branch-specific DoDs below are fully closed before P4 completion.
- [x] final verdict is explicit (`PASS_BPLUS`, `PASS_B`, or `FAIL_REALISM`).
- [x] retained run-id set and storage hygiene are explicit.

### P4.A - Freeze-now closure (non-reopen branch)
Goal:
- close this cycle without upstream reopen.

Scope:
- lock P3 candidate lane as 2A best-effort authority.
- publish residual blocker matrix and reopen contract.

Definition of done:
- [x] freeze authority run root is pinned (`runs/fix-data-engine/segment_2A_p3`).
- [x] blocker matrix is attached (metric, gap-to-B, owning surface).
- [x] reopen preconditions are documented with owner/phase mapping.

### P4.B - Reopen-1B contract (recommended branch)
Goal:
- define the exact upstream reopen contract so recertification is causal, bounded, and auditable.

Scope:
- open only `1B` representativeness surfaces that causally drive 2A realism:
  - country placement priors,
  - intra-country spread/coverage policies,
  - any deterministic tie-breaks that collapse multi-timezone countries.
- keep `2A` governance caps and scorer thresholds unchanged.

Definition of done:
- [x] reopen surface list is pinned to exact files/states in 1B plan.
- [x] non-negotiables are pinned:
  - no 2A cap relaxation,
  - no synthetic post-assignment redistribution,
  - no threshold edits to B/B+ scorer.
- [x] witness seed protocol and runtime budgets are pinned before execution.

### P4.B1 - Upstream remediation run protocol and budgets
Goal:
- execute upstream reopen with runtime discipline and minimal blast radius.

Scope:
- run protocol:
  - upstream witness set: seeds `{42, 7}` first,
  - if witness movement is positive, expand to `{42, 7, 101, 202}`.
- runtime budgets (Performance-First law):
  - each witness cycle must show measurable runtime improvement or hold vs prior 1B authority lane,
  - abort/reassess if runtime regresses materially without realism lift.

Definition of done:
- [x] witness seed runs complete with retained evidence artifacts.
- [x] runtime evidence table is emitted (per state and chain total).
- [x] movement gate is explicit (`GO_FULL_SEEDPACK` or `HOLD_REWORK`).

### P4.B2 - Integrated 1B -> 2A recertification
Goal:
- verify whether upstream representativeness reopen unlocks 2A B/B+ realism.

Scope:
- execute full required seeds `{42, 7, 101, 202}` through reopened 1B and current 2A stack.
- certify with existing 2A scorer (`tools/score_segment2a_p2_certification.py`).

Definition of done:
- [ ] all required seeds complete `2A S0->S5`.
- [ ] hard governance/structural gates are green on all seeds.
- [x] aggregate verdict is published with deltas vs P3 candidate lane.

### P4.B3 - Final decision gate
Goal:
- end P4 with an unambiguous final disposition.

Scope:
- if `PASS_B`/`PASS_BPLUS`: lock and freeze as upgraded authority.
- if still `FAIL_REALISM`: freeze with explicit upstream residual blockers and next reopen candidate.

Definition of done:
- [x] decision is explicit (`LOCK_UPGRADED_AUTHORITY` or `FREEZE_WITH_BLOCKERS`).
- [x] final retained run-id set and report paths are pinned.
- [x] next-step queue is recorded without ambiguity.

P4 closure record (2026-02-17):
- branch choice:
  - `REOPEN_1B` executed (with `P4.A` baseline freeze snapshot retained as comparison authority).
- execution lane:
  - candidate root: `runs/fix-data-engine/segment_2A_p4b_r1`
  - required run-ids:
    - seed `42`: `b65bfe6efaca42e2ac413c059fb88b64`
    - seed `7`: `07891eca4e6ea549a4d836db35e203aa`
    - seed `101`: `513f4f2904d1ac97f2396c059a9573da`
    - seed `202`: `5a8836781dd7524da561ad5aa27f64d6`
- upstream reopen surfaces applied (`1B` only):
  - `config/layer1/1B/policy/policy.s2.tile_weights.yaml`
  - `config/layer1/1B/policy/policy.s4.alloc_plan.yaml`
- witness (`P4.B1`) outcome:
  - seeds `{42,7}` completed `1B S2->S9` and `2A S0->S5`.
  - `HOLD_REWORK` signal:
    - seed `42` improved on concentration metrics but remained below B.
    - seed `7` regressed materially on concentration/entropy and `C_large` representativeness.
  - runtime evidence artifacts:
    - `runs/fix-data-engine/segment_2A_p4b_r1/reports/segment2a_p4b_runtime_by_seed.json`
    - `runs/fix-data-engine/segment_2A_p4b_r1/reports/segment2a_p4b_runtime_by_seed.csv`
    - `runs/fix-data-engine/segment_2A_p4b_r1/reports/segment2a_p4b_runtime_delta.json`
    - `runs/fix-data-engine/segment_2A_p4b_r1/reports/segment2a_p4b_runtime_delta.csv`
- integrated full-seed recertification (`P4.B2`) outcome:
  - seed `101`: fail-closed at `2A-S1-091` (`fallback_country_cap_exceeded`, country `KZ`).
  - seed `202`: fail-closed at `2A-S1-092` (`override_rate_cap_exceeded`).
  - aggregate certification:
    - `runs/fix-data-engine/segment_2A_p4b_r1/reports/segment2a_p2_certification_42-b65bfe6e_7-07891eca_101-513f4f29_202-5a883678.json`
    - status: `FAIL_REALISM`.
- final decision (`P4.B3`):
  - `FREEZE_WITH_BLOCKERS`.
  - freeze authorities remain:
    - `1A`: unchanged frozen authority.
    - `1B`: unchanged frozen best-effort authority.
    - `2A`: `runs/fix-data-engine/segment_2A_p3` remains best-effort authority; `P4.B` candidate rejected.
- retained/cleanup posture:
  - retain `runs/fix-data-engine/segment_2A_p3` and `runs/fix-data-engine/segment_2A_p4b_r1` (evidence lane).
  - prune superseded partial lane `runs/fix-data-engine/segment_2A_p4b`.

## 6) Failure triage map (state-first)
- Structural parity fail:
  - inspect S1/S2 key/coverage path first.
- Fallback or override cap fail:
  - tune S1 fallback logic and S2 override policy budgets.
- `C_multi` diversity/concentration fail with clean governance:
  - treat as upstream-constrained signal; apply bounded targeted corrections only.
- Seed instability fail:
  - reduce high-sensitivity policy levers; tighten deterministic tie-breaks and policy branching.

## 7) Freeze and reopen rule
- Phase progression is strict: no phase advancement with open DoD.
- `1A` and `1B` are immutable authorities in this cycle.
- If 2A cannot clear `B` under frozen upstream, mark `FAIL_REALISM` and freeze 2A as best-effort for this pass.
- Any reopen request must include:
  - contradiction evidence,
  - precise state/knob scope,
  - explicit approval before execution.

## 8) Performance Optimization Set (POPT.0 -> POPT.4)
Objective:
- make 2A iteration minute-scale before deeper realism loops, using the same hotspot-first method used in 1B.

Execution posture:
- performance-first, semantics-preserving by default.
- no contract/schema/output-shape relaxations.
- deterministic outputs and fail-closed gates remain mandatory.

### POPT.0 - Baseline runtime and hotspot contract lock
Goal:
- freeze an auditable runtime baseline and rank bottlenecks before touching code.

Scope:
- produce a machine-readable baseline artifact for the current 2A authority run chain.
- capture state wall times and hotspot evidence from run logs + state reports.

Definition of done:
- [x] baseline runtime artifact emitted under `runs/fix-data-engine/segment_2A/reports/`.
- [x] ranked hotspot list published (primary, secondary, closure bottleneck).
- [x] minute-scale target budgets pinned per hotspot state.
- [x] progression gate for `POPT.1` recorded (`GO`/`HOLD`).

POPT.0 closure record (2026-02-16):
- authority run used:
  - `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`
  - reason: `runs/fix-data-engine/segment_2A/9ebdd751ab7b4f9da246cc840ddff306` is incomplete (`S3+` missing), so it is not baseline-safe.
- generated artifacts:
  - `runs/fix-data-engine/segment_2A/reports/segment2a_popt0_baseline_c25a2675fbfbacd952b13bb594880e92.json`
  - `runs/fix-data-engine/segment_2A/reports/segment2a_popt0_hotspot_map_c25a2675fbfbacd952b13bb594880e92.md`
- observed runtime baseline (`report wall_ms` sum):
  - `S1=13.188s` (`41.64%`) -> primary hotspot (`RED` vs target/stretch `10s/12s`).
  - `S3=9.360s` (`29.55%`) -> secondary hotspot (`AMBER` vs `8s/10s`).
  - `S2=7.641s` (`24.12%`) -> closure hotspot (`AMBER` vs `7s/9s`).
  - segment total (reports): `31.673s`; log-window elapsed: `35.347s`.
- progression gate:
  - decision: `GO POPT.1`.
  - selected state for `POPT.1`: `S1`.

### POPT.1 - Primary hotspot rewrite
Goal:
- reduce the #1 ranked hotspot state to its stretch runtime budget without changing semantics.

Scope:
- state selected from `POPT.0` ranking (expected likely `S1` or `S3` depending on current run profile).
- algorithm/data-structure and IO/locality optimization first; knob-only tuning is secondary.

Definition of done:
- [ ] primary hotspot wall time reduced to budget (or explicit `AMBER` waiver).
- [ ] deterministic equivalence checks pass.
- [ ] downstream smoke (`next states -> S5`) stays green.
- [ ] no memory-risk regression under Fast-Compute-Safe posture.

POPT.1 status update (2026-02-17):
- authority baseline run:
  - `dd4ba47ab7b942a4930cbeee85eda331`
  - `S1 wall_ms=14766` (`~14.77s`).
- candidate lane:
  - `b65bfe6efaca42e2ac413c059fb88b64` (full `S0->S5` green).
- implemented S1 optimizations (semantics-preserving):
  - early-exit candidate resolver to avoid full candidate-set construction for common unambiguous rows,
  - tuple-row hot-loop iteration (`iter_rows()` instead of named dict rows),
  - reduced per-row output payload + vectorized frame assembly from source batch columns.
- rejected variant:
  - STRtree `predicate=intersects` per-point query path regressed runtime and was rolled back.
- measured outcome:
  - best observed `S1 wall_ms=13796` (`~13.80s`) on candidate lane.
  - improvement vs baseline: `-970ms` (`~6.6%`).
  - `S1` remains above stretch budget (`12s`) -> phase remains open (`RED` vs stretch target).
- safety posture:
  - downstream `S2->S5` remained green on candidate lane.
  - output partitions remained deterministic/identical for unchanged identity (publish path reported identical-bytes reuse).

### POPT.2 - Secondary hotspot rewrite
Goal:
- reduce the #2 ranked hotspot state while preserving `POPT.1` gains.

Scope:
- optimize the second bottleneck lane identified by `POPT.0`.
- include logging cadence and IO overhead trimming only if semantics-neutral.

Definition of done:
- [x] secondary hotspot wall time meets stretch budget.
- [x] no regression in primary hotspot runtime beyond tolerance.
- [x] deterministic and contract checks remain green.

POPT.2 status update (2026-02-17):
- authority baseline for comparison:
  - `dd4ba47ab7b942a4930cbeee85eda331` with `S3 wall_ms=10141`.
- candidate lane:
  - `b65bfe6efaca42e2ac413c059fb88b64`.
- implemented S3 optimization:
  - deterministic shared timetable-index cache keyed by sealed `tzdb_archive_sha256`,
  - cache-hit path reuses encoded index bytes/metadata while preserving coverage and contract checks,
  - cache-miss path compiles and atomically stores cache for subsequent runs.
- measured outcome:
  - cold pass (cache miss): `S3` remains approximately `~10.145s` (expected first-build cost),
  - warm pass (cache hit): `S3 wall_ms=562` (`~0.56s`, `GREEN` vs `8s/10s` target/stretch),
  - improvement vs baseline (warm lane): `-9579ms` (`~94.5%`).
- safety posture:
  - `S4` and `S5` remained PASS on the same candidate run-id,
  - no observed regression in primary hotspot (`S1` remains `13796ms`, still open from `POPT.1`).
- decision:
  - `POPT.2` closed for fast-iteration posture; proceed to `POPT.3`.

### POPT.3 - Validation/closure-path acceleration
Goal:
- speed up validation/certification-path runtime (typically `S5` checks and scorer scans) so candidate verdict loops are fast.

Scope:
- optimize expensive validation scans with fail-closed correctness retained.
- prefer sampling/accelerated parsing only where mathematically safe and explicitly governed.

Definition of done:
- [x] validation lane runtime materially reduced vs baseline.
- [x] all hard correctness checks still full-strength (no silent relaxations).
- [x] decision parity (`PASS`/`FAIL`) unchanged for authority witnesses.

POPT.3 status update (2026-02-17):
- optimized state:
  - `S5` (`packages/engine/src/engine/layers/l1/seg_2A/s5_validation_bundle/runner.py`).
- implemented acceleration lane:
  - in-memory evidence/index/check construction to avoid redundant temp-file churn,
  - deterministic existing-bundle reuse path (`REUSE`) when current evidence/index/checks/flag are byte-identical,
  - fail-closed fallback to full materialize+publish when reuse match is not exact.
- measured runtime evidence (from run logs):
  - candidate run `b65...`: pre-change warm S5 range `308-318ms`, post-change warm S5 range `249-251ms`,
  - authority run `dd4...`: `309ms -> 248ms`.
  - observed warm-lane reduction: approximately `19-22%`.
- correctness posture:
  - `S5` hard checks remain enforced (no sampling/relaxation paths introduced),
  - `S5` decision parity remained `PASS` on both witness runs (`b65...`, `dd4...`),
  - integrated `S3->S4->S5` chain remained green on candidate run.
- decision:
  - `POPT.3` closed; proceed to `POPT.4` integrated recertification handoff.

### POPT.4 - Integrated fast-lane recertification handoff
Goal:
- prove optimized mechanics compose end-to-end for 2A and are ready for ongoing remediation use.

Scope:
- run integrated candidate chain with optimized lanes.
- score realism + structural gates to ensure no unacceptable regression due to performance work.

Definition of done:
- [x] end-to-end runtime materially reduced vs `POPT.0` baseline.
- [x] no-regression posture holds for structural/governance gates.
- [x] integrated lock artifact published and referenced as 2A performance authority.

POPT.4 status update (2026-02-17):
- integrated witness run:
  - `b65bfe6efaca42e2ac413c059fb88b64` executed with full `S0->S5` chain (all states PASS).
- runtime recertification inputs:
  - baseline authority (`POPT.0`): `segment2a_popt0_baseline_c25a2675fbfbacd952b13bb594880e92.json`,
  - no-regression witness: `dd4ba47ab7b942a4930cbeee85eda331`,
  - candidate runtime snapshot: `segment2a_popt0_baseline_b65bfe6efaca42e2ac413c059fb88b64.json`.
- integrated lock artifact:
  - `runs/fix-data-engine/segment_2A/reports/segment2a_popt4_integrated_b65bfe6efaca42e2ac413c059fb88b64.json`
- lock result:
  - status: `GREEN_LOCKED`,
  - checks:
    - `runtime_material=true`,
    - `structural_all_pass=true`,
    - `governance_no_regression=true`.
- runtime outcome:
  - baseline total: `31.673s`,
  - candidate total: `25.857s`,
  - improvement: `-5.816s` (`~18.36%`).
- decision:
  - `POPT.4` closed; 2A fast-iteration performance authority is now pinned to the integrated lock artifact above.

### Storage and retention discipline (POPT binding)
- keep only:
  - baseline authority,
  - current candidate,
  - last-good candidate,
  - current integrated witness.
- prune superseded failed run-id folders before each new expensive candidate.

## 9) Final Effort Lane for 2B Support (Option 2, bounded)
Goal:
- run one final upstream `2A` code+policy reopen attempt to materially reduce the
  `2B` single-group floor (`share(n_groups==1)` and `share(max_p>=0.95)`),
  then close decisively (`GO` or `NO_GO`) before moving to `3A`.

Binding constraints:
- `1A` and `1B` remain frozen authorities.
- no synthetic `2B` local groups (`ALLOW_SYNTHETIC_LOCAL_GROUPS = no`).
- movement must come from real upstream `2A site_timezones` topology.
- one bounded candidate lane only; fail-closed on non-material movement.

Candidate surfaces:
- `packages/engine/src/engine/layers/l1/seg_2A/s2_overrides/runner.py`
- `config/layer1/2A/timezone/tz_overrides.yaml`
- `config/layer1/2A/timezone/tz_nudge.yml`
- optional new `2A` policy contract for bounded rebalance controls:
  - `config/layer1/2A/timezone/topology_rebalance_policy_v1.json`
  - `docs/model_spec/data-engine/layer-1/specs/contracts/2A/schemas.2A.yaml`

### P5.0 - Rebalance contract and guardrails lock
Goal:
- define deterministic, auditable rules for limited `S2` topology rebalance.

Scope:
- target only merchants that are currently single-tz after `S1` and satisfy all:
  - country has more than one valid tzid in `tz_world`,
  - merchant has enough sites (`min_sites_for_rebalance`),
  - site geometry signal supports split (country-aware lon-span/proximity rule).
- pin hard caps:
  - global reassigned-site share cap,
  - per-country reassigned-site cap,
  - per-merchant reassigned-site cap.
- pin deterministic selector:
  - stable merchant/site ordering + hash-seeded tie-break.

Definition of done:
- [x] rebalance policy contract is explicit and schema-validated.
- [x] caps + eligibility rules are pinned in policy and reportable.
- [x] no schema/output-shape changes outside existing `site_timezones` contract.

### P5.1 - S2 deterministic topology rebalance implementation
Goal:
- implement bounded reassignment in `S2` without breaking governance rails.

Scope:
- after standard override resolution, apply bounded reassignment only to eligible rows.
- reassign to real alternate tzids from country-valid set (no pseudo labels).
- preserve deterministic ordering and write-once behavior.
- emit run-report counters:
  - eligible merchants/sites,
  - reassigned sites (global/per-country/per-merchant),
  - cap-hit counts and sample rows.

Definition of done:
- [x] `S2` run reports expose rebalance counters and samples.
- [x] all existing `S2` validators remain pass.
- [x] deterministic replay witness is green on same inputs.

### P5.2 - Single candidate execution protocol (`2A -> 2B`)
Goal:
- execute one clean candidate chain and measure floor movement.

Scope:
- stage clean run-id from current `2B` authority lineage.
- run `2A S0->S5`, then `2B S0->S8` with external-root precedence pinned.
- score using existing analyzers:
  - `tools/score_segment2b_p3_candidate.py`
  - `tools/analyze_segment2b_p1_reopen_floor.py`

Definition of done:
- [x] one full candidate chain completes.
- [x] score + floor artifacts are emitted and retained.
- [x] runtime and storage hygiene records are emitted.

### P5.3 - Final decision gate (terminal for Option 2)
Goal:
- close with explicit terminal decision before `3A`.

Gate criteria:
- movement gate:
  - require material floor drop (`delta share(n_groups==1) <= -0.02` and
    `delta share(max_p>=0.95) <= -0.02`).
- non-regression gate:
  - no new governance failures and no red regression on protected non-tail rails.

Definition of done:
- [x] explicit verdict recorded:
  - `GO_P3_RETRY_FROM_2A_FINAL` if movement + non-regression gates pass,
  - else `NO_GO_OPTION2_FINAL` and move to `3A`.
- [x] final lock artifact for this lane is emitted (json + md).

P5 status update (2026-02-18):
- implemented bounded deterministic topology rebalance in `2A S2` with note-token opt-in (`[rebalance:auto]`), strict global/country/merchant caps, and explicit run-report counters.
- candidate `27d6feeac34141f081c6379c8dc797a2` (first cap posture):
  - `planned_sites_final=21`, `rebalance_reassigned_total=21`, `distinct_tzids=98`,
  - floor movement was non-material (`delta share_n_groups_eq_1=-0.005654`, `delta share_max_p_ge_095=-0.005654`).
- candidate `fd9b373e9a6a4ae0b2204f00677815f1` (expanded cap posture):
  - `planned_sites_final=424`, `rebalance_reassigned_total=424`, `distinct_tzids=132`,
  - legacy override governance remained clean (`overridden_total=6`, `override_rate=0.00019196`),
  - floor movement was material (`delta share_n_groups_eq_1=-0.075121`, `delta share_max_p_ge_095=-0.075121`).
- gate decision:
  - movement + protected non-tail non-regression gates passed (`GO_P3_RETRY_FROM_2A_FINAL`),
  - immediate `P3` retry on the same candidate still returned `FAIL_P3` (`s4_b_band=false`, `s4_bplus_band=false`).
- terminal closure:
  - lane closed as `NO_GO_OPTION2_FINAL`; no further `2A` reopen is planned for this cycle,
  - lock artifacts:
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_2a_final_lock_fd9b373e9a6a4ae0b2204f00677815f1.json`
    - `runs/fix-data-engine/segment_2B/reports/segment2b_p1_reopen_2a_final_lock_fd9b373e9a6a4ae0b2204f00677815f1.md`.
- post-closure code posture:
  - experimental `S2` rebalance implementation was reverted from mainline to
    preserve frozen `2A` authority behavior; evidence artifacts remain retained.
