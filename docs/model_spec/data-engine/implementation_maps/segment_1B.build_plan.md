# Segment 1B Remediation Build Plan (B/B+ Execution Plan)
_As of 2026-02-13_

## 0) Objective and closure rule
- Objective: remediate Segment `1B` to certified realism `B` minimum, with `B+` as the active target.
- Realism surface of record: `site_locations`.
- Closure rule:
  - all hard `B` gates pass on all required seeds, and
  - `B+` is claimed only if all `B+` gates pass on all required seeds with stability limits met.
- Execution posture: data-shape first. Structural pass flags remain safety rails, not the tuning target.

## 1) Source-of-truth stack

### 1.1 Statistical authority
- `docs/reports/eda/segment_1B/segment_1B_published_report.md`
- `docs/reports/eda/segment_1B/segment_1B_remediation_report.md`

### 1.2 State/contract authority
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s0.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s1.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s2.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s3.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s4.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s5.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s6.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s7.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s8.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s9.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1B/artefact_registry_1B.yaml`

## 2) Upstream lock and remediation scope
- Upstream lock: Segment `1A` is frozen and treated as immutable input during 1B remediation.
- Active remediation states: `S2`, `S4`, `S6`, `S9`.
- Support states (rerun-only unless breakage): `S0`, `S1`, `S3`, `S5`, `S7`, `S8`.
- This follows the remediation report chosen fix bundle (`S2 + S4 + S6 + S9`) and keeps state-order causality intact.

### 2.1 Progressive rerun matrix (mandatory)
- If `S2` changes: rerun `S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S9`.
- If `S4` changes: rerun `S4 -> S5 -> S6 -> S7 -> S8 -> S9`.
- If `S6` changes: rerun `S6 -> S7 -> S8 -> S9`.
- If `S9` gates only change: rerun `S9`.
- No phase closes on partial state chains that violate upstream/downstream dependencies.

## 3) Realism targets (baseline to B/B+)
- Baseline (published report): `country_gini=0.753`, `top10=59.74%`, `top5=39.33%`, `top1=13.66%`.
- `B` targets:
  - `country_gini <= 0.68`
  - `top10 <= 50%`
  - `top5 <= 33%`
  - `top1 <= 10%`
  - eligible countries with nonzero sites `>= 85%`
  - southern hemisphere share `>= 12%`
  - nearest-neighbor tail ratio (`p99/p50`) improves by `>= 20%` vs baseline
- `B+` targets:
  - `country_gini <= 0.60`
  - `top10 <= 42%`
  - `top5 <= 27%`
  - `top1 <= 8%`
  - eligible countries with nonzero sites `>= 92%`
  - southern hemisphere share `>= 18%`
  - nearest-neighbor tail ratio (`p99/p50`) improves by `>= 35%` vs baseline
- Stability targets across seeds:
  - core-metric CV `<= 0.30` for `B`
  - core-metric CV `<= 0.20` for `B+`

## 4) Heavy-compute iteration protocol
- Run root for remediation: `runs/fix-data-engine/segment_1B/`.
- Baseline authority run stays pinned and read-only.
- Keep only required run-id folders:
  - `baseline_authority`
  - `current_candidate`
  - `last_good`
  - certification pack (only during final promotion wave)
- Before starting a new candidate run, prune superseded failed candidate folders.

### 4.1 Two-lane loop
- Fast lane (tuning):
  - single-seed iterations from the changed state onward using the rerun matrix.
  - evaluate only data realism movement and regression vetoes.
- Certification lane (promotion):
  - full-seed set `{42, 7, 101, 202}` with full required state chain for the promoted candidate.
  - promotion blocked if any seed fails a hard gate.

## 5) Phase plan (data-first with DoDs)

### P0 - Baseline authority and harness lock
Focus:
- pin and document baseline metrics/table for Segment 1B.
- lock run/pruning workflow for fast iteration.

Definition of done:
- [ ] baseline metric table is materialized and pinned to one authority run.
- [ ] 1A frozen-input contract for 1B runs is recorded.
- [ ] run-pruning workflow is wired and used before every new candidate.

### P1 - S2 macro-mass reshape (country and region balance priors)
Focus:
- implement `blend_v2` policy and constrained deterministic rebalance in `S2`.

Primary tuning surfaces:
- `policy.s2.tile_weights.yaml` (`basis_mix`, region floors, soft/hard caps, concentration penalty).
- `s2_tile_weights` runner constrained rebalance loop and diagnostics.

Data outputs under evaluation:
- `tile_weights`
- `s2_run_report` diagnostics (`country_share_topk`, `country_gini_proxy`, `region_share_vector`)

Definition of done:
- [ ] `blend_v2` policy path is active with deterministic replay preserved.
- [ ] S2 diagnostics show measurable concentration relaxation without region-floor violations.
- [ ] two consecutive fast-lane runs reproduce the same metric posture for fixed seed/policy hash.
- [ ] P1 lock recorded (S2 policy version + runner commit pinned for downstream phases).

### P2 - S4 anti-collapse integer allocation closure
Focus:
- prevent post-integerization reconcentration from undoing S2 improvements.

Primary tuning surfaces:
- `S4` assignment-time guards (`country_share_soft_guard`, deterministic reroute, bounded residual redistribution).

Data outputs under evaluation:
- `s4_alloc_plan`
- S4 aggregated country/region allocation scorecards

Definition of done:
- [ ] post-S4 concentration/coverage metrics improve versus pre-P2 posture.
- [ ] no reconcentration breach introduced by integerization step.
- [ ] deterministic replay holds for fixed seed/policy hash.
- [ ] P2 lock recorded (S4 guard settings + expected score band).

### P3 - S6 geometry realism closure (within-country shape)
Focus:
- replace rigid uniform-in-cell posture with policy-driven mixture jitter while keeping geographic validity strict.

Primary tuning surfaces:
- `policy.s6.jitter.yaml` (`core_cluster`, `secondary_cluster`, `sparse_tail`, tail clamp).
- `S6` jitter mode selection and mixture parameterization.

Data outputs under evaluation:
- `s6_site_jitter`
- `site_locations` (via downstream `S7/S8` synthesis and egress)

Definition of done:
- [ ] nearest-neighbor tail ratio contracts by at least `20%` vs baseline (`B` floor).
- [ ] top-volume country cohort shows no stripe/corridor collapse sentinel.
- [ ] coordinate validity remains `100%` and point-in-country checks remain intact.
- [ ] P3 lock recorded (S6 jitter profile + expected local-geometry band).

### P4 - Integrated closure run (B target, B+ attempt)
Focus:
- run integrated candidate with locked `P1+P2+P3` settings and verify Segment 1B behaves as one coherent system.

Data outputs under evaluation:
- `tile_weights`
- `s4_alloc_plan`
- `s6_site_jitter`
- `site_locations`

Definition of done:
- [ ] all `B` hard realism gates pass on integrated candidate.
- [ ] no locked upstream phase (`P1/P2/P3`) needs reopening for data-shape contradictions.
- [ ] if near-threshold, execute bounded B+ retune loop without breaking B posture.

### P5 - Certification and freeze
Focus:
- certify promoted candidate across required seed set and freeze Segment 1B authority bundle.

Definition of done:
- [ ] hard `B` gates pass on all required seeds (or `B+` gates if achieved).
- [ ] stability CV limits meet the claimed grade.
- [ ] final lock set is recorded (policy files, runner commits, scorecard artifacts).
- [ ] superseded remediation run-id folders are pruned; retained folders are explicitly listed.

## 6) Failure triage map (state-first diagnosis)
- `Gini/top-k` fail only: retune `S2` caps and concentration penalty first.
- Region-floor fail with acceptable concentration: retune `S4` residual redistribution.
- NN-tail fail with concentration pass: retune `S6` sparse-tail component and clamp.
- Seed instability with mean pass: reduce high-sensitivity knobs and tighten deterministic balancing.
- Structural contract fail at any stage: fix implementation bug before further realism tuning.

## 7) Phase freeze rule
- Once a phase meets DoD and is declared locked, downstream phases must treat it as immutable.
- Reopening a locked phase requires explicit contradiction evidence and user approval.
- This prevents circular retuning and preserves causal attribution of realism movement.
