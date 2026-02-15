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
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4_integrated_9ebdd751ab7b4f9da246cc840ddff306.json`

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
