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

POPT.1 baseline anchors (from POPT.0):
- optimization target state: `S2`
- baseline run-id: `724a63d3f8b242809b8ec3b746d0c776`
- baseline `S2 wall`: `406.375s`
- baseline hotspot share: `58.25%`
- observed dominant sub-lanes in `S2`:
  - `tile allocations prepared` lane dominates pre-loop wall time,
  - per-edge jitter/tz assignment loop is the second heavy lane.

POPT.1 closure gates (quantified):
- runtime movement gate:
  - `S2 wall <= 300s` OR
  - `S2 wall reduction >= 25%` vs baseline (`<=304.78s` equivalent).
- non-regression gates:
  - `S2` run-report counters remain structurally valid (`edges_total`, `rng_events_total`, `rng_draws_total` non-null and coherent),
  - downstream `S3/S4/S5` remain `PASS`,
  - no schema/path drift in `edge_catalogue_3B` and `edge_catalogue_index_3B`.
- determinism gate:
  - identical policy + seed produces equivalent structural counters and no new validator failures.

### POPT.1.1 - Hot-lane decomposition lock (no semantics change)
Goal:
- expose `S2` internal lanes with enough resolution to prove where wall time is spent.

Scope:
- pin baseline timing split for:
  - input resolve + seal checks,
  - tile allocation prep,
  - jitter/tz placement loop,
  - write/publish lane.
- ensure added timing markers are low-frequency and deterministic.

Definition of done:
- [ ] machine-readable lane timing breakdown exists for candidate runs.
- [ ] no output or schema changes from instrumentation-only edits.
- [ ] instrumentation overhead is bounded and does not dominate wall time.

### POPT.1.2 - S2 prep-lane optimization (primary)
Goal:
- reduce `tile allocation prep` cost without changing assignment semantics.

Scope:
- optimize country-level asset reuse/data structures in `S2` prep path.
- eliminate repeated expensive transforms where immutable-by-run inputs permit reuse.
- keep single-process memory-safe posture (Fast-Compute-Safe).

Definition of done:
- [ ] prep lane wall time materially reduced vs POPT.0 baseline trace.
- [ ] no change in required `S2` counters semantics.
- [ ] no memory pressure regressions observed on candidate run.

### POPT.1.3 - Edge placement loop optimization (secondary inside POPT.1)
Goal:
- reduce per-edge jitter/tz loop overhead while preserving RNG/accounting contract.

Scope:
- optimize loop data access patterns and avoid repeated per-edge lookup work.
- preserve RNG stream usage/accounting and event surface contracts.

Definition of done:
- [ ] placement-loop throughput improves measurably vs baseline.
- [ ] `rng_events_total` and `rng_draws_total` remain coherent and valid.
- [ ] no new `S2` validator failures.

### POPT.1.4 - Logging cadence budget for S2
Goal:
- reduce avoidable log-induced overhead in the `S2` hotspot lane.

Scope:
- cap high-frequency progress logs to practical cadence while retaining audit-critical events.
- keep error/warn visibility unchanged.

Definition of done:
- [ ] log volume reduced on S2 hot lane.
- [ ] required auditability remains intact.
- [ ] measurable S2 wall-time movement attributable to lower logging drag.

### POPT.1.5 - Witness rerun and gate checks
Goal:
- validate optimized `S2` behavior under full downstream chain.

Scope:
- execute single-seed witness rerun from changed state onward: `S2 -> S3 -> S4 -> S5`.
- score against POPT.1 runtime and non-regression gates.

Definition of done:
- [x] witness chain is green (`S2..S5 PASS`).
- [x] POPT.1 closure gates are evaluated in artifact form.
- [x] failures (if any) are mapped to explicit reopen action.

### POPT.1.6 - Closure decision and handoff
Goal:
- close POPT.1 with explicit decision and next-phase pointer.

Scope:
- if runtime + non-regression gates pass: promote POPT.1 closure and open `POPT.2` on secondary hotspot (`S5`).
- otherwise: keep POPT.1 open with bounded reopen plan (no phase drift).

Definition of done:
- [x] explicit decision is recorded (`UNLOCK_POPT2` or `HOLD_POPT1_REOPEN`).
- [x] retained candidate run-id and artifacts are pinned.
- [x] build plan phase status is synchronized to closure truth.

POPT.1 execution evidence and closure:
- passing witness candidate:
  - run-id: `19334bfdbacb40dba38ad851c69dd0e6`
  - outcome: `S2..S5 PASS`, but runtime gate failed (`S2=633.094s`, baseline `406.375s`)
  - closure artifact:
    - `runs/fix-data-engine/segment_3B/reports/segment3b_popt1_closure_19334bfdbacb40dba38ad851c69dd0e6.json`
    - `runs/fix-data-engine/segment_3B/reports/segment3b_popt1_closure_19334bfdbacb40dba38ad851c69dd0e6.md`
- failed bounded attempts (captured then pruned to protect storage):
  - `2e7537c20492400b888b03868e00ffce` (`S2` fail at `tile_surfaces`, infra/memory pressure posture)
  - `9459c3d21cfd4a4a9eb6ca93b20af84e` (`S2` fail late in batched prep lane)
- closure decision: `HOLD_POPT1_REOPEN`
- reopen lane: redesign `S2` tile-allocation prep strategy under strict single-process memory budget and minute-scale runtime gate.

### POPT.1R - S2 prep-lane redesign (planning-first reopen)
Goal:
- redesign `S2` tile-allocation prep so runtime moves toward minute-scale while preserving deterministic output and contract invariants.

Binding redesign constraints (from `state.3B.s2.expanded.md` + contracts):
- no schema/path drift on `edge_catalogue_3B` and `edge_catalogue_index_3B`.
- no RNG semantic drift:
  - no new RNG in budget/allocation decisions,
  - same envelope/accounting behavior in edge placement lane.
- preserve S2 validation failure semantics/codes for tile surfaces (`tile_weights_missing`, `dp_mismatch`, `tile_id_not_in_index`, `tile_bounds_missing_ids`, `tile_bounds_missing`).
- maintain single-process memory-safe posture (Fast-Compute-Safe).

Redesign architecture target (`Country Surface Kernel`, CSK):
- replace repeated broad scans and high-overhead per-country file traversals with bounded, deterministic batch extraction.
- kernel shape:
  - `R`ead: batched predicate-pushdown scans for `tile_weights`, `tile_index`, `tile_bounds` over country batches.
  - `A`lign: build compact per-country maps in memory for weights/index/bounds in one batch pass.
  - `P`roject: allocate edges + extract only needed bounds for downstream jitter loop.
- batch controller:
  - adaptive country batch sizing (row-budgeted), with hard upper bound to prevent RSS spikes.
  - deterministic batch order = `sorted(country_iso)` only.

### POPT.1R.1 - Equivalence spec lock
Goal:
- define exactly what must remain equivalent before coding.

Scope:
- pin structural equivalence surfaces:
  - `counts.edges_total`, `counts.rng_events_total`, `counts.rng_draws_total`, `counts.rng_blocks_total`,
  - `edges_by_country` and `attempt_histogram` structure,
  - output schema + partition path law.
- pin allowable variance:
  - runtime-only movement; no output semantic drift.

Definition of done:
- [x] equivalence checklist is written and accepted.
- [x] non-equivalence surfaces are explicitly rejected for this reopen.

POPT.1R.1 closure record:
- lock artifacts:
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt1r1_equivalence_spec_20260219.json`
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt1r1_equivalence_spec_20260219.md`
- baseline authority pinned in lock:
  - run-id `724a63d3f8b242809b8ec3b746d0c776`,
  - seed `42`,
  - manifest_fingerprint `c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8`.
- result: `LOCK_EQUIVALENCE_CONTRACT`.
- progression: `UNLOCK_POPT1R2`.

### POPT.1R.2 - Prep-lane profiler harness (no behavior change)
Goal:
- get deterministic lane-level attribution for redesign iterations.

Scope:
- add/read lane timing checkpoints for:
  - tile read,
  - country-map construction,
  - allocation+needed-bounds projection.
- emit machine-readable lane timing artifact for each candidate run.

Definition of done:
- [x] lane timing artifact exists for candidate baseline.
- [x] instrumentation overhead is bounded and not itself a hotspot.

POPT.1R.2 closure record:
- profiler harness tool:
  - `tools/score_segment3b_popt1r2_lane_timing.py`
- baseline authority lane artifact:
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt1r2_lane_timing_724a63d3f8b242809b8ec3b746d0c776.json`
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt1r2_lane_timing_724a63d3f8b242809b8ec3b746d0c776.md`
- optional comparison lane artifact (best prior passing candidate):
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt1r2_lane_timing_19334bfdbacb40dba38ad851c69dd0e6.json`
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt1r2_lane_timing_19334bfdbacb40dba38ad851c69dd0e6.md`
- baseline lane shares (`S2 wall=406.375s`):
  - `tile_read_map_alloc_project_total`: `286.304s` (`70.45%`)
  - `edge_jitter_tz_loop`: `98.582s` (`24.26%`)
  - remaining lanes (`input/pre-loop/publish`): `21.491s` (`5.29%`)
- instrumentation overhead evidence:
  - harness mode is read-only log/report parsing (`runtime_overhead_estimate_s=0.0`),
  - no engine state code changes required for this profiler lane.
- progression: `UNLOCK_POPT1R3`.

### POPT.1R.3 - CSK implementation (bounded batch RAP kernel)
Goal:
- implement the redesign kernel with explicit memory and runtime controls.

Scope:
- implement batch extraction with predicate pushdown for the three tile datasets.
- build per-country compact maps once per batch, then process countries from in-memory maps.
- ensure allocations and bounds projection remain deterministic and validator-compatible.
- enforce batch RSS safety by design (bounded batch size, no global full materialization).

Definition of done:
- [x] S2 prep lane completes without infra/memory failures.
- [ ] tile prep delta is materially below the failed reopen attempts.
- [x] all existing S2 validator behaviors remain intact.

POPT.1R.3 execution record:
- witness run-id: `ef21b94d9d8743b2bc264e2c3a791865`.
- execution outcome:
  - `S2..S5 PASS`,
  - `S2 wall=1267.437s` (`00:21:07`) vs baseline `406.375s`,
  - prep lane (`tile_read_map_alloc_project_total`) `1148.305s` (`90.60%` of S2 wall).
- guardrail checks:
  - validator behavior intact (`tile_*` failure taxonomy unchanged),
  - RNG accounting coherent (`rng_events_total=169272`, `rng_draws_total=338544`, `rng_blocks_total=169272`).
- closure posture:
  - runtime gate failed (`HOLD_POPT1_REOPEN`),
  - reopen required for prep-lane algorithm, not for contract correctness.

### POPT.1R.4 - Loop/log budget alignment (secondary reopen trim)
Goal:
- keep edge placement lane stable and avoid log-induced drag.

Scope:
- keep progress heartbeat practical and deterministic.
- avoid per-iteration high-cardinality logging.
- preserve audit-critical logs and failure visibility.

Definition of done:
- [x] log cadence is budgeted and stable.
- [x] no loss of required observability signals.

POPT.1R.4 status note:
- superseded/waived for this reopen cycle after rollback + `POPT.1R.NEXT` decision.
- reason:
  - `POPT.1R.3` failure was prep-lane algorithmic (`tile_read_map_alloc_project_total`), not edge-loop/log cadence.
  - existing loop heartbeat cadence already remained bounded and audit-complete in witness runs.

### POPT.1R.5 - Witness + closure decision
Goal:
- evaluate reopen candidate against runtime and non-regression gates.

Scope:
- run witness chain `S2 -> S3 -> S4 -> S5` on fresh run-id with frozen upstream.
- score with closure artifact:
  - runtime gate: `S2 <= 300s` OR `>=25%` reduction vs `406.375s`,
  - downstream `S3/S4/S5 PASS`,
  - RNG accounting coherent.

Definition of done:
- [x] closure artifact emitted for reopen candidate.
- [x] explicit decision recorded: `UNLOCK_POPT2` or `HOLD_POPT1_REOPEN`.
- [x] superseded failed run folders are pruned after evidence capture.

POPT.1R.5 closure record:
- closure artifacts:
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt1r2_lane_timing_ef21b94d9d8743b2bc264e2c3a791865.json`
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt1_closure_ef21b94d9d8743b2bc264e2c3a791865.json`
- decision:
  - `HOLD_POPT1_REOPEN` (runtime gate fail, downstream non-regression pass).
- run-retention note:
  - no additional superseded run-id folders were created during this closure lane.

### POPT.1R.NEXT - Safer redesign lane (country-keyed one-pass prep)
Goal:
- reopen `S2` prep-lane with a lower-risk algorithm that is memory-safe and avoids repeated global scan cost.

Scope:
- rollback CSK batch path and start from pre-reopen stable runner code.
- add deterministic precheck that all tile surfaces resolve to explicit country-keyed files for required countries:
  - `tile_weights`: `part-<ISO>.parquet`,
  - `tile_index`: `country=<ISO>/...`,
  - `tile_bounds`: `country=<ISO>/...`.
- fail-closed on unresolved/mixed file-key patterns in this lane (no unresolved fallback scans).
- process each country once with direct file-targeted reads (one-pass per dataset per country), preserving existing validator/error semantics.
- keep RNG/edge-loop and output contracts unchanged.

Definition of done:
- [x] rollback to pre-CSK runner state is complete.
- [x] country-key coverage precheck artifact is emitted for witness run.
- [x] prep lane no longer uses batch-wide repeated scans/collects.
- [ ] interim runtime checkpoint passes:
  - `tile_read_map_alloc_project_total <= 500s`,
  - `S2 wall <= 700s`.
- [ ] if interim checkpoint passes, proceed to full runtime gate check (`S2 <=300s` OR `>=25%` reduction).

POPT.1R.NEXT checkpoint record:
- checkpoint run-id: `0762ad15e0a34ef6a2ce62372b95f813` (`S2` only).
- partition precheck artifact:
  - `runs/fix-data-engine/segment_3B/0762ad15e0a34ef6a2ce62372b95f813/reports/layer1/3B/state=S2/seed=42/manifest_fingerprint=c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8/tile_surface_partition_precheck.json`
  - result: no missing required countries for weights/index/bounds; unresolved-path count `0`.
- runtime checkpoint result:
  - `S2 wall=1048.344s` (`00:17:28`) -> FAIL vs `<=700s` interim gate.
  - `tile_read_map_alloc_project_total=922.751s` (`88.02%`) -> FAIL vs `<=500s` interim gate.
- status:
  - safer/fail-closed posture achieved,
  - performance still outside interim budget; keep `POPT.1` in reopen mode.

### POPT.2 - Secondary hotspot optimization (expected S5 or S3)
Goal:
- reduce second-ranked bottleneck while preserving check semantics.

Scope:
- optimize `S5` validation-bundle hot lanes (hash + evidence assembly) under deterministic digest law.
- preserve bundle hash law, index ordering law, and validation semantics.
- keep `S5` as primary `POPT.2` target; only touch `S3` if `S5` gates are met and secondary residuals remain.

Definition of done:
- [x] secondary hotspot runtime materially reduced vs baseline.
- [x] parity/invariants remain non-regressed.
- [x] audit evidence completeness remains intact.

POPT.2 baseline anchors (authority):
- hotspot authority artifact:
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt0_baseline_724a63d3f8b242809b8ec3b746d0c776.json`
- pinned baseline:
  - `S5 wall = 240.468s` (`34.47%` segment share),
  - dominant evidence from logs: long hash lanes for `rng_trace_log` + `rng_event_edge_jitter`.
- execution dependency:
  - preferred: execute after `POPT.1` runtime closure,
  - allowed by user waiver: isolated `S5` optimization on fixed authority run roots if `POPT.1` remains open.

### POPT.2.1 - S5 lane decomposition lock (profiling authority)
Goal:
- produce execution-grade breakdown of `S5` into hash/validate/bundle lanes before edits.

Scope:
- emit machine-readable lane timing for:
  - `validate_s1_s4_inputs`,
  - `validate_s2_edges/index`,
  - `hash_rng_trace_log`,
  - `hash_rng_event_edge_jitter`,
  - `bundle_publish_finalize`.
- pin throughput metrics (rows/s or lines/s) for each hash lane.

Definition of done:
- [x] lane timing artifact exists for baseline authority run.
- [x] top-2 `S5` hotspot lanes are numerically pinned.
- [x] profiler overhead is zero/near-zero and auditable.

### POPT.2.2 - Hash-lane algorithm optimization (primary)
Goal:
- reduce `S5` hash-lane wall time without weakening digest guarantees.

Scope:
- replace high-overhead per-record decode loops with deterministic streaming byte-hash + bounded structural checks.
- avoid repeated file open/close churn and redundant pass-through of the same log parts.
- preserve exactly the same final bundle digests and failure semantics on malformed/empty members.

Definition of done:
- [x] hash lane wall-time reduced materially vs baseline.
- [x] digest outputs remain byte-identical for unchanged inputs.
- [x] malformed/empty log failure behavior is non-regressed.

### POPT.2.3 - Validation/evidence assembly trim (secondary)
Goal:
- remove avoidable non-hash overhead in `S5` fast path.

Scope:
- reduce redundant materialization of already-validated metadata.
- collapse duplicate scans of `S2` index/edge evidence where a single pass can serve both checks.
- keep schema and validation-result payloads unchanged.

Definition of done:
- [ ] non-hash `S5` lanes show measurable reduction.
- [x] validation result payload schema and semantics are unchanged.
- [x] no new warnings/errors introduced in green runs.

### POPT.2.4 - Witness gate and closure
Goal:
- certify `POPT.2` candidate under runtime + non-regression gates.

Scope:
- run witness lane with patched `S5` candidate (`S5` only on fixed run-id or full `S2->S5` depending on `POPT.1` posture).
- score against explicit gates:
  - `S5 <= 180s` OR `>=25%` reduction vs `240.468s`,
  - deterministic bundle digest parity for unchanged inputs,
  - no schema/path drift, no validator regressions.

Definition of done:
- [x] closure artifact emitted (`POPT.2` gate scorecard).
- [x] explicit decision recorded (`UNLOCK_POPT3` or `HOLD_POPT2_REOPEN`).
- [x] superseded run-id folders pruned after evidence capture.

POPT.2 execution record (2026-02-19):
- baseline lane artifact (`POPT.2.1`):
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt2_s5_lane_timing_724a63d3f8b242809b8ec3b746d0c776.json`
- implementation applied (`POPT.2.2` + `POPT.2.3`):
  - `S5` hash path moved to single-pass mode (no `_count_lines` pre-pass),
  - audit/trace evidence extraction fused into hash pass callbacks (removed redundant post-hash JSONL scans),
  - digest law preserved (raw line-byte hashing unchanged).
- witness lane (`POPT.2.4`):
  - command: isolated `segment3b-s5` rerun on authority run-id
    `724a63d3f8b242809b8ec3b746d0c776`.
  - post-patch lane artifact:
    - `runs/fix-data-engine/segment_3B/reports/segment3b_popt2_s5_lane_timing_724a63d3f8b242809b8ec3b746d0c776_postpatch.json`
  - closure scorecard:
    - `runs/fix-data-engine/segment_3B/reports/segment3b_popt2_closure_724a63d3f8b242809b8ec3b746d0c776_postpatch.json`
    - `runs/fix-data-engine/segment_3B/reports/segment3b_popt2_closure_724a63d3f8b242809b8ec3b746d0c776_postpatch.md`
- measured result:
  - baseline `S5 wall=240.468s`,
  - candidate `S5 wall=241.844s`,
  - runtime gate FAIL (`-0.57%` movement, below required `<=180s` or `>=25%` reduction).
- non-regression:
  - bundle digest parity PASS,
  - output path stability PASS,
  - `S5` status PASS.
- closure decision:
  - `HOLD_POPT2_REOPEN`.

### POPT.2R - Bounded reopen after POPT.2 gate miss
Goal:
- attempt one low-risk and one high-impact recovery pass to clear the `POPT.2` runtime gate without touching contracts or widening blast radius.

Scope:
- keep lane isolated to `S5` on fixed authority run-id `724a63d3f8b242809b8ec3b746d0c776`.
- preserve digest law, schema/path contracts, and fail-closed behavior.
- avoid new run-id folder churn unless a broader rerun is explicitly required by changed-state law.

Definition of done:
- [x] `POPT.2R.1` executed and scored.
- [x] `POPT.2R.2` executed and scored if `R1` misses gate.
- [x] explicit final decision recorded (`UNLOCK_POPT3` or retained `HOLD_POPT2_REOPEN` with waiver path).

### POPT.2R.1 - Low-risk log-cadence trim
Goal:
- reduce avoidable logging drag in S5 hash lanes with no semantic changes.

Scope:
- increase S5 hot-lane progress logging interval (from current high-frequency cadence to bounded lower-frequency cadence).
- rerun isolated `segment3b-s5` witness on authority run-id.
- score with existing `POPT.2` closure scorer.

Definition of done:
- [x] runtime movement measured vs baseline and last candidate.
- [x] digest parity/path stability remain PASS.
- [ ] if runtime gate passes, close `POPT.2` and stop reopen lane.

POPT.2R.1 execution record (2026-02-19):
- patch scope:
  - S5 hash progress log interval increased (`0.5s -> 5.0s`) via
    `S5_HASH_PROGRESS_LOG_INTERVAL_S`.
  - no digest/schema/path behavior changes.
- witness execution:
  - command: isolated `segment3b-s5` rerun on authority run-id
    `724a63d3f8b242809b8ec3b746d0c776`.
  - artifacts:
    - `runs/fix-data-engine/segment_3B/reports/segment3b_popt2r1_s5_lane_timing_724a63d3f8b242809b8ec3b746d0c776.json`
    - `runs/fix-data-engine/segment_3B/reports/segment3b_popt2r1_closure_724a63d3f8b242809b8ec3b746d0c776.json`
- measured outcome:
  - baseline `S5 wall=240.468s`,
  - candidate `S5 wall=242.842s`,
  - runtime movement `-0.99%` (gate fail).
- non-regression:
  - digest parity PASS,
  - output path stability PASS,
  - S5 status PASS.
- decision:
  - `R1` did not clear runtime gate; proceed to `POPT.2R.2`.

### POPT.2R.2 - High-impact hash-path acceleration
Goal:
- materially cut per-event hot-path overhead when `R1` is insufficient.

Scope:
- move S5 hash-lane JSON schema validation to compiled validator path while preserving:
  - fail-closed malformed/invalid semantics,
  - raw line-byte digest law,
  - output schema/path contracts.
- rerun isolated `segment3b-s5` witness and rescore.

Definition of done:
- [x] runtime movement is measured and compared to baseline.
- [x] non-regression gates (digest/path/status) remain PASS.
- [x] runtime gate verdict is explicit.

POPT.2R.2 execution record (2026-02-19):
- implementation scope:
  - dependency pin added: `fastjsonschema` in `pyproject.toml`,
  - S5 hash lanes switched to compiled validator backend with schema-digest cache and fail-closed fallback to `Draft202012`,
  - JSONL parse fast path switched to `orjson.loads(bytes)` in S5 hash loop.
- witness execution:
  - command: isolated `segment3b-s5` rerun on authority run-id
    `724a63d3f8b242809b8ec3b746d0c776`.
  - artifacts:
    - `runs/fix-data-engine/segment_3B/reports/segment3b_popt2r2_s5_lane_timing_724a63d3f8b242809b8ec3b746d0c776.json`
    - `runs/fix-data-engine/segment_3B/reports/segment3b_popt2r2_closure_724a63d3f8b242809b8ec3b746d0c776.json`
- measured outcome:
  - baseline `S5 wall=240.468s`,
  - candidate `S5 wall=42.641s`,
  - runtime movement `+82.27%` (runtime gate PASS).
- non-regression:
  - digest parity PASS,
  - output path stability PASS,
  - S5 status PASS.
- decision:
  - `R2` clears gate and unlocks `POPT.3`.

### POPT.2R.3 - Final decision gate
Goal:
- terminate reopen lane with explicit progression posture.

Scope:
- if runtime gate passes: mark `POPT.2` closed and unlock `POPT.3`.
- if runtime gate still fails after `R2`: retain `HOLD_POPT2_REOPEN` and proceed only under explicit waiver with recorded rationale.

Definition of done:
- [x] closure decision and rationale appended.
- [x] next phase pointer is explicit in current-phase status.

POPT.2R.3 closure decision (2026-02-19):
- final decision: `UNLOCK_POPT3`.
- rationale:
  - runtime gate passed strongly in `R2`,
  - non-regression gates remained green.
- progression:
  - `POPT.2` closed,
  - `POPT.2R` closed,
  - `POPT.3` unlocked.

### POPT.3 - Logging and serialization budget optimization
Goal:
- harden the post-`POPT.2R` fast lane by enforcing explicit log/serialization budgets without sacrificing auditability.

Scope:
- keep required audit/error logs, but bound high-frequency progress emission.
- trim avoidable serialization overhead only where digest/contract behavior is unchanged.
- allow no-op closure if current baseline already satisfies all `POPT.3` gates.

Definition of done:
- [x] `POPT.3` closure artifact emitted with explicit gate verdict.
- [x] runtime/log-budget gates pass (or explicit no-op closure rationale is recorded).
- [x] no digest/schema/path/run-report regressions.

POPT.3 baseline anchors (entry authority):
- baseline run-id (post-`POPT.2R.2`): `724a63d3f8b242809b8ec3b746d0c776`.
- baseline runtime: `S5 wall=42.641s`.
- closure note:
  - this is already below `POPT.2` runtime target, so `POPT.3` is guardrail hardening, not heavy runtime rescue.

### POPT.3.1 - Log-budget baseline inventory
Goal:
- quantify current S5 log volume and pin mandatory audit log set before any optional trims.

Scope:
- emit baseline log-budget artifact from the latest authority run:
  - line counts by category (`INFO/WARN/ERROR`, progress lines, validator backend lines, final status lines),
  - approximate log bytes for S5 window,
  - mandatory message presence checks.
- freeze required message set:
  - objective header,
  - sealed input validation completion,
  - bundle completion summary,
  - run-report written line,
  - warnings/errors (when present) preserved.

Definition of done:
- [x] baseline log-budget artifact exists.
- [x] required message set is explicitly pinned.
- [x] baseline over-budget conditions (if any) are enumerated.

POPT.3.1 closure record (2026-02-19):
- baseline inventory artifacts:
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt3_log_budget_baseline_724a63d3f8b242809b8ec3b746d0c776.json`
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt3_log_budget_baseline_724a63d3f8b242809b8ec3b746d0c776.md`
- baseline counters:
  - `total_lines=17`
  - `progress_lines=0`
  - `validator_backend_lines=3`
  - `required_narrative_present=true`
- conclusion:
  - no baseline log-budget breach was detected; `POPT.3` remains hardening-oriented.

### POPT.3.2 - Logging cadence policy hardening
Goal:
- bound high-volume progress logs while preserving operability and audit story.

Scope:
- normalize S5 progress logging policy into explicit bounded cadence controls.
- keep debug/error signals unchanged.
- preserve deterministic content for required summary/audit logs.

Definition of done:
- [x] high-frequency progress line volume is reduced or bounded by policy.
- [x] required narrative/audit log lines remain present.
- [x] no change in validator failure visibility.

POPT.3.2 closure record (2026-02-19):
- code change:
  - `packages/engine/src/engine/layers/l1/seg_3B/s5_validation_bundle/runner.py`
- hardening applied:
  - added terminal `flush()` on progress tracker to guarantee one final heartbeat per hash lane.
  - preserved bounded-cadence behavior for in-flight progress messages.
- witness evidence:
  - candidate log-budget artifact shows `progress_lines=3` with required narrative lines intact and compiled validator backend lines unchanged (`=3`).

### POPT.3.3 - Serialization micro-trim (conditional)
Goal:
- remove residual serialization overhead only if `POPT.3.1/3.2` shows measurable over-budget drag.

Scope:
- collapse redundant JSON serialization/writes where digest-checked reuse is equivalent.
- do not alter output payload shapes, ordering, or digest surfaces.
- skip this lane if baseline already satisfies runtime + log-budget gates.

Definition of done:
- [x] conditional decision recorded (`EXECUTED` or `SKIPPED_NO_GAIN`).
- [x] if executed: measurable movement and no contract drift.
- [x] if skipped: rationale and evidence are recorded.

POPT.3.3 closure record (2026-02-19):
- decision: `SKIPPED_NO_GAIN`.
- rationale:
  - post-`POPT.3.2` witness remained comfortably inside runtime/log-budget gates.
  - additional serialization edits would increase blast radius without a justified gain.
- authority artifacts:
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt3_log_budget_candidate_724a63d3f8b242809b8ec3b746d0c776.json`
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt3_log_budget_candidate_724a63d3f8b242809b8ec3b746d0c776.md`

### POPT.3.4 - Witness gate and closure
Goal:
- certify `POPT.3` posture and decide unlock to `POPT.4`.

Scope:
- run isolated S5 witness on authority run-id after `POPT.3` changes (or no-op lock).
- score gates:
  - runtime guard: `S5 <= 55s` and no material regression vs `42.641s`,
  - log-budget guard: progress-line volume within pinned budget and required narrative logs present,
  - non-regression guard: digest parity, output path stability, `S5 PASS`.

Definition of done:
- [x] closure scorecard emitted (`segment3b_popt3_closure_<run_id>.json/.md`).
- [x] explicit decision recorded (`UNLOCK_POPT4` or `HOLD_POPT3_REOPEN`).
- [x] current phase status updated with next-lane pointer.

POPT.3.4 closure decision (2026-02-19):
- witness execution:
  - command: `make segment3b-s5 RUNS_ROOT=runs/fix-data-engine/segment_3B SEG3B_S5_RUN_ID=724a63d3f8b242809b8ec3b746d0c776`
  - result: `S5 PASS`
- closure artifacts:
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt3_closure_724a63d3f8b242809b8ec3b746d0c776.json`
  - `runs/fix-data-engine/segment_3B/reports/segment3b_popt3_closure_724a63d3f8b242809b8ec3b746d0c776.md`
- measured gates:
  - runtime guard: PASS (`candidate=43.686s`, baseline `42.641s`, regression `2.45%`, within `<=15%` budget and `<=55s` cap).
  - log-budget guard: PASS (`progress_lines=3 <= 16`, required narrative present).
  - non-regression guard: PASS (digest parity, output-path stability, `S5 PASS`).
- final decision:
  - `UNLOCK_POPT4`.

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
- `POPT.1`: in_progress (`HOLD_POPT1_REOPEN`)
- `POPT.1R.NEXT`: in_progress (`OPEN_AFTER_ROLLBACK`)
- `POPT.2`: completed (`UNLOCK_POPT3_AFTER_POPT2R2`)
- `POPT.2R`: completed (`UNLOCK_POPT3`)
- `POPT.3`: completed (`UNLOCK_POPT4`)
- `POPT.4`: pending (`UNLOCKED_AFTER_POPT3`)
- `P0`: pending
- `P1`: pending
- `P2`: pending
- `P3`: pending
- `P4`: pending
- `P5`: pending
