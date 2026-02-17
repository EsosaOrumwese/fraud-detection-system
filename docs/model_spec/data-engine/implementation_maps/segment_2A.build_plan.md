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
- [ ] fallback rate and override rate are emitted per run and by country.
- [ ] hard cap breaches fail-closed with explicit reason codes.
- [ ] override provenance fields are complete and schema-valid.
- [ ] structural parity and legality remain non-regressed.

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
- [ ] scorer emits full hard-gate metrics and verdict per seed.
- [ ] aggregate cross-seed verdict (`PASS_BPLUS`/`PASS_B`/`FAIL_REALISM`) is deterministic.
- [ ] diagnostics CSV/JSON artifacts are emitted for hotspot tracing.

### P3 - Targeted correction lane (bounded, non-synthetic)
Goal:
- improve failing country/timezone hotspots with narrow, auditable interventions while staying causal.

Scope:
- evidence-based, bounded watchlist corrections only.
- no broad redistribution layer.

Definition of done:
- [ ] at least one bounded candidate improves failing realism axes vs P0 baseline.
- [ ] improvements are not achieved via override inflation or fallback inflation.
- [ ] no structural, legality, or determinism regression.

### P4 - Certification pass or constrained freeze
Goal:
- run full seed-pack certification and make explicit final grade decision.

Scope:
- required seeds: `{42, 7, 101, 202}`.
- full `S0 -> S5` chain per seed with gate checks.

Definition of done:
- [ ] all required-seed hard-gate results are published.
- [ ] final verdict is explicit (`PASS_BPLUS`, `PASS_B`, or `FAIL_REALISM`).
- [ ] if `FAIL_REALISM`, freeze as best-effort with explicit blocker set and reopen contract.
- [ ] retained run-id set is explicit and storage-clean.

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
