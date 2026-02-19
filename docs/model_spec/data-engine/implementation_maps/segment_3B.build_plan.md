# Segment 3B Remediation Build Plan (B/B+ Execution Plan)
_As of 2026-02-19_

## 0) Objective and closure rule
- Objective: remediate Segment `3B` to certified realism `B` minimum, with `B+` as the active target where feasible.
- Baseline authority posture from published report: realism grade `D` (borderline `D+`).
- Primary realism surfaces of record:
  - `virtual_classification_3B` (S1 explainability realism)
  - `virtual_settlement_3B` (S1 anchor diversity realism)
  - `edge_catalogue_3B` (S2 heterogeneity + settlement coherence realism)
  - `edge_alias_blob_3B` / `edge_alias_index_3B` (S3 fidelity non-regression)
  - `virtual_validation_contract_3B` (S4 realism-governance coverage)
- Closure rule:
  - `PASS_BPLUS`: all hard gates + stretch gates + tighter stability gates pass across required seeds.
  - `PASS_B`: all hard gates + stability gates pass across required seeds.
  - `FAIL_REALISM`: any hard gate fails on any required seed.
- Phase advancement law (binding): no phase closes until its DoD checklist is fully green.

## 1) Source-of-truth stack

### 1.1 Statistical authority
- `docs/reports/eda/segment_3B/segment_3B_published_report.md`
- `docs/reports/eda/segment_3B/segment_3B_remediation_report.md`

### 1.2 State and contract authority
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s0.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s1.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s2.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s3.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s4.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s5.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3B/dataset_dictionary.layer1.3B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3B/schemas.3B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3B/artefact_registry_3B.yaml`

### 1.3 Upstream freeze posture (binding for this pass)
- `1A` remains frozen as certified authority.
- `1B` remains frozen as best-effort frozen authority.
- `2A` remains frozen as retained authority.
- `2B` remains frozen as retained authority.
- `3A` remains frozen as best-effort-below-B authority.
- Segment `3B` remediation in this pass does not assume upstream reopen.

## 2) Remediation posture and boundaries
- Causal remediation order (from report root-cause trace):
  - `S1 lineage -> S2 topology + settlement coupling -> S4 realism governance -> certification`.
- Core change stack for `B`:
  - `CF-3B-03` (`S1` classification lineage enrichment).
  - `CF-3B-01` + `CF-3B-02` (`S2` merchant-conditioned topology + settlement-coupled weighting).
  - `CF-3B-04` (`S4` realism contract expansion, observe then enforce).
- Conditional/add-on stack:
  - `CF-3B-05` settlement anti-concentration guardrail (if concentration remains outside corridor).
  - `CF-3B-06` merchant-profile divergence calibration (B+ lane).
- Structural states:
  - `S0`: gate/sealed-input integrity.
  - `S3`: alias fidelity and universe-hash integrity (codec non-regression target).
  - `S5`: terminal bundle + pass flag + certification evidence.
- Tuning priority:
  - data-shape realism first,
  - structural flags and hash checks are hard veto rails, not optimization targets.

## 3) Statistical targets and hard gates
- Required seeds for certification: `{42, 7, 101, 202}`.

### 3.1 Hard B gates
- `3B-V01`: `CV(edges_per_merchant) >= 0.25`.
- `3B-V02`: `CV(countries_per_merchant) >= 0.20`.
- `3B-V03`: `p50(top1_share) in [0.03, 0.20]`.
- `3B-V04`: median pairwise JS divergence `>= 0.05`.
- `3B-V05`: median settlement-country overlap `>= 0.03`.
- `3B-V06`: p75 settlement-country overlap `>= 0.06`.
- `3B-V07`: median edge-to-settlement distance `<= 6000 km`.
- `3B-V08`: `% non-null rule_id >= 99%`.
- `3B-V09`: `% non-null rule_version >= 99%`.
- `3B-V10`: active `rule_id` count `>= 3`.
- `3B-V11`: `max abs(alias_prob - edge_weight) <= 1e-6`.
- `3B-V12`: S4 realism-check block active + enforced.

### 3.2 B+ target bands
- `3B-S01`: `CV(edges_per_merchant) >= 0.40`.
- `3B-S02`: `CV(countries_per_merchant) >= 0.35`.
- `3B-S03`: `p50(top1_share) in [0.05, 0.30]` with wider spread than B floor.
- `3B-S04`: median pairwise JS divergence `>= 0.10`.
- `3B-S05`: median settlement overlap `>= 0.07`.
- `3B-S06`: p75 settlement overlap `>= 0.12`.
- `3B-S07`: median settlement distance `<= 4500 km`.
- `3B-S08`: `% non-null rule_id` and `% non-null rule_version` each `>= 99.8%`.
- `3B-S09`: active `rule_id` count `>= 5`.
- `3B-S10`: top-1 settlement tzid share `<= 0.18`.

### 3.3 Cross-seed stability gates
- `3B-X01`: cross-seed CV of key medians (`top1_share`, overlap, distance, JS):
  - `B`: `<= 0.25`
  - `B+`: `<= 0.15`
- `3B-X02`: virtual prevalence within policy band on all required seeds.
- `3B-X03`: no hard-gate failures on any required seed.

## 4) Run protocol, performance budget, and retention
- Active run root: `runs/fix-data-engine/segment_3B/`.
- Retained folders only:
  - baseline authority pointer,
  - current candidate,
  - last good candidate,
  - active certification pack.
- Prune-before-run is mandatory for superseded failed run-id folders.

### 4.1 Progressive rerun matrix (sequential-state law)
- If any sealed policy bytes change: rerun `S0 -> S1 -> S2 -> S3 -> S4 -> S5`.
- If `S1` logic/policy changes: rerun `S1 -> S2 -> S3 -> S4 -> S5`.
- If `S2` logic/policy changes: rerun `S2 -> S3 -> S4 -> S5`.
- If `S3` logic/policy changes: rerun `S3 -> S4 -> S5`.
- If `S4` contract/policy changes: rerun `S4 -> S5`.
- If only scorer/report tooling changes: rerun scoring/evidence only; do not mutate state outputs.

### 4.2 Runtime budgets (binding)
- POPT.0 must record per-state wall-clock baseline (`S0..S5`) and bottleneck ranking.
- Fast candidate lane (single seed, changed-state onward): target `<= 15 min`.
- Witness lane (2 seeds): target `<= 30 min`.
- Certification lane (4 seeds sequential): target `<= 75 min`.
- Any material runtime regression without bottleneck closure blocks phase closure.

## 5) Performance optimization pre-lane (POPT, mandatory)
- Objective: establish minute-scale practical iteration before realism tuning.
- Guardrails:
  - preserve determinism and contract compliance,
  - no realism-shape tuning in POPT,
  - single-process efficiency baseline first,
  - each POPT phase requires runtime evidence and non-regression evidence.

### POPT.0 - Runtime baseline and bottleneck map
Goal:
- measure current `S0..S5` runtime and rank bottlenecks.

Scope:
- run one clean baseline chain in fix lane.
- capture state elapsed, dominant I/O paths, dominant compute paths.
- pin per-lane budgets for candidate/witness/certification.

Definition of done:
- [x] baseline runtime table is emitted.
- [x] top bottlenecks are ranked with evidence.
- [x] budget targets are pinned and accepted.

POPT.0 closure record (2026-02-19):
- baseline run:
  - `runs/fix-data-engine/segment_3B/724a63d3f8b242809b8ec3b746d0c776`
- closure artifacts:
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt0_baseline_724a63d3f8b242809b8ec3b746d0c776.json`
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt0_hotspot_map_724a63d3f8b242809b8ec3b746d0c776.md`
- observed runtime:
  - report elapsed sum: `697.64s` (`00:11:38`)
  - log window: `702.666s` (`00:11:43`)
- ranked bottlenecks:
  - primary: `S2` (`406.375s`, `58.25%`)
  - secondary: `S5` (`240.468s`, `34.47%`)
  - closure: `S4` (`38.702s`, `5.55%`)
- lane budgets:
  - fast candidate lane (`<=900s`): `PASS`
  - witness lane target (`<=1800s`): pinned
  - certification lane target (`<=4500s`): pinned
- progression gate:
  - decision: `GO_POPT1`
  - selected primary hotspot for optimization: `S2`

### POPT.1 - Primary hotspot optimization (expected S2)
Goal:
- reduce elapsed for top bottleneck without changing output semantics.

Scope:
- optimize data structures/search/index/join strategy in bottleneck state.
- keep dataset schema and deterministic identity unchanged.

Definition of done:
- [ ] primary hotspot runtime materially reduced vs POPT.0 baseline.
- [ ] deterministic replay parity passes on same seed/input.
- [ ] structural validators remain green.

### POPT.2 - Secondary hotspot optimization (expected S5 or S3)
Goal:
- reduce second-ranked bottleneck while preserving check semantics.

Scope:
- optimize I/O traversal and evidence assembly path.
- preserve bundle hash law and index ordering laws.

Definition of done:
- [ ] secondary hotspot runtime materially reduced vs baseline.
- [ ] parity/invariants remain non-regressed.
- [ ] audit evidence completeness remains intact.

### POPT.3 - Logging and serialization budget optimization
Goal:
- remove avoidable runtime drag from heavy logs/serialization.

Scope:
- keep required audit logs, cap high-frequency progress logging cadence.
- eliminate redundant reads/writes where equivalent digest-checked reuse is possible.

Definition of done:
- [ ] log volume reduced with required auditability preserved.
- [ ] state elapsed improves on I/O-heavy lanes.
- [ ] no required run-report fields are missing.

### POPT.4 - Fast-lane closure and freeze
Goal:
- lock an optimized baseline before remediation.

Scope:
- run witness lane on optimized posture.
- ensure run retention/prune discipline is active and reproducible.

Definition of done:
- [ ] witness lane runtime and determinism are accepted.
- [ ] keep-set + prune workflow is proven.
- [ ] `POPT` is explicitly marked closed.

## 6) Remediation phases (data realism first)

### P0 - Baseline lock and metric scaffolding
Goal:
- lock statistical baseline and scorer contract for 3B.

Scope:
- baseline readout on required metrics (`3B-V*`, `3B-S*`, `3B-X*`).
- emit per-seed and cross-seed metric artifacts.
- pin failure surfaces and initial target deltas.

Definition of done:
- [ ] baseline metric pack exists for required seeds.
- [ ] failing gates are explicitly enumerated by severity.
- [ ] scorer artifact contract is fixed for subsequent phases.

### P1 - S1 lineage enrichment (`CF-3B-03`)
Goal:
- make classification explainability auditable and non-opaque.

Scope:
- enforce non-null `rule_id` and `rule_version`.
- emit controlled reason taxonomy with deterministic tie-break identity.
- preserve virtual prevalence posture unless intentionally policy-adjusted.

Definition of done:
- [ ] `3B-V08` and `3B-V09` pass on witness seeds.
- [ ] active `rule_id` count shows movement toward `3B-V10`.
- [ ] no regressions in S1/S2 join integrity.

### P2 - S2 topology and settlement coupling core (`CF-3B-01 + CF-3B-02`)
Goal:
- remove edge-universe flatness and restore settlement influence.

Scope:
- replace fixed global edge template with merchant-conditioned topology.
- implement settlement-coupled country weighting with bounded guardrails.
- keep deterministic RNG envelope and declared stream namespaces.

Definition of done:
- [ ] hard heterogeneity gates (`3B-V01..V04`) pass on witness seeds.
- [ ] settlement coherence gates (`3B-V05..V07`) pass on witness seeds.
- [ ] S2/S3 integrity and RNG accounting remain PASS.

### P3 - S4 realism governance expansion (`CF-3B-04`)
Goal:
- block green-but-unrealistic runs at contract level.

Scope:
- add realism-check block into `virtual_validation_contract_3B`.
- run one observe-mode pass, then enforce blocking mode.
- persist measured value + threshold + status per realism check.

Definition of done:
- [ ] `3B-V12` passes (realism block active and enforced).
- [ ] contract rows map to all hard-gate surfaces.
- [ ] no schema or registry drift from S4 outputs.

### P4 - Conditional concentration cleanup + B+ calibration (`CF-3B-05/06`)
Goal:
- close residual concentration defects and target `B+` where feasible.

Scope:
- apply settlement anti-concentration controls if hub-share remains out-of-band.
- calibrate merchant-profile divergence/spread for stretch metrics.
- keep hard-gate posture stable while pushing stretch bands.

Definition of done:
- [ ] concentration metrics move toward stretch corridors.
- [ ] no hard-gate regressions introduced by calibration.
- [ ] B+ stretch pass matrix is explicit per seed.

### P5 - Integrated certification and freeze
Goal:
- run full seedpack certification and freeze segment posture.

Scope:
- execute required seeds `{42,7,101,202}` on locked candidate.
- compute hard/stretch/stability verdict.
- emit freeze summary and retained evidence pack.

Definition of done:
- [ ] certification summary artifact is emitted.
- [ ] explicit verdict recorded (`PASS_BPLUS`, `PASS_B`, or `FAIL_REALISM`).
- [ ] freeze status and keep-set are recorded with prune closure.

## 7) Certification artifacts and decision package
- Required artifacts:
  - `3B_validation_metrics_seed_<seed>.json`
  - `3B_validation_cross_seed_summary.json`
  - `3B_validation_failure_trace.md` (if any gate fails)
- Certification decision rule:
  - `B`: all hard + stability gates pass.
  - `B+`: all hard + stretch + tighter stability pass.
  - Any hard-gate fail keeps segment below `B`.

## 8) Current phase status
- `POPT.0`: completed
- `POPT.1`: pending
- `POPT.2`: pending
- `POPT.3`: pending
- `POPT.4`: pending
- `P0`: pending
- `P1`: pending
- `P2`: pending
- `P3`: pending
- `P4`: pending
- `P5`: pending
