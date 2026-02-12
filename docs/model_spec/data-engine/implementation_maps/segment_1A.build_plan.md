# Segment 1A Remediation Build Plan (fix-data-engine track)
_As of 2026-02-12_

## Purpose
Remediate Segment 1A engine implementation plus handwritten policy/config surfaces so output data reaches certified `B` (minimum) and then `B+` (target) realism, using fresh run lineages under `runs/fix-data-engine/...` only.

## Scope
- In scope: Segment 1A states `S0..S9`, policy/config bundles, coefficient exports, validation and statistical certification harness for 1A.
- Out of scope: Editing historical run artifacts, changing downstream segments before 1A gate closure, cosmetic-only metric tuning without causal fixes.

## Authority Anchors
- `packages/engine/AGENTS.md`
- `docs/reports/eda/segment_1A/segment_1A_published_report.md`
- `docs/reports/eda/segment_1A/segment_1A_remediation_report.md`
- `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s0.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s1.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s2.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s3.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s4.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s5.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s6.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s7.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s8.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s9.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/artefact_registry_1A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.1A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml`

## Target Statistical Contract
Hard `B` gates (all mandatory):
1. `P(outlet_count=1) >= 0.25` (fail if `<0.20`).
2. `median(candidate_count) <= 15` (fail if `>18`).
3. `CV(phi) >= 0.05` and `P95/P05(phi) >= 1.25`.
4. Required artifacts present:
   - `s3_integerised_counts`
   - `s3_site_sequence`
   - `sparse_flag`
   - `merchant_abort_log`
   - `hurdle_stationarity_tests`
5. Determinism hash parity for same seed + same policy/coeff hashes.

Grade mapping:
- `B`: all hard gates pass + at least 70% of `B` target-band checks pass.
- `B+`: all hard gates pass + at least 80% of `B+` target-band checks pass.

## Run Isolation Contract
- Baseline comparison remains read-only:
  - `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/...`
- New remediation lineage root:
  - `runs/fix-data-engine/segment_1A/`
- Run wave naming:
  - `wave_0_baseline_replay`
  - `wave_1_structure`
  - `wave_2_geo_legal`
  - `wave_3_dispersion`
  - `wave_4_certification`
- Execution default:
  - `ENGINE_RUNS_ROOT=runs/fix-data-engine/segment_1A`
  - explicit `SEG1A_S*_RUN_ID` when replaying downstream states.

## State-by-State Remediation Blueprint

### S0 Foundations
Objective: keep run sealing and lineage stable while enabling remediation lineage isolation.

Planned actions:
- Verify no implicit writes outside `ENGINE_RUNS_ROOT`.
- Verify sealed input captures updated policy/coefficient paths and hashes for each wave.
- Keep `run_receipt.json` deterministic and authoritative for reruns.

DoD:
- [ ] New runs write only under `runs/fix-data-engine/segment_1A/<run_id>/`.
- [ ] `sealed_inputs_1A.json` includes all changed policy/coeff assets with new hashes.
- [ ] No S0 contract regression in validation bundle.

### S1 Hurdle
Objective: restore realistic single-vs-multi posture and prevent all-multi collapse.

Planned actions:
- Re-author hurdle coefficients/export choice to target realistic multi-site probability.
- Keep deterministic Bernoulli and RNG envelope unchanged.
- Validate channel/MCC conditioning remains active and not saturated.

Primary surfaces:
- `config/layer1/1A/models/hurdle/exports/.../hurdle_coefficients.yaml`
- `packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/runner.py` (only if policy alone cannot satisfy gates)

DoD:
- [ ] Multi-rate supports downstream single-site share target when combined with S8.
- [ ] No S1 schema or RNG accounting regressions.
- [ ] S1 replay checks pass in S9.

### S2 NB Outlets + Dispersion
Objective: eliminate near-constant `phi` and restore merchant-level variance heterogeneity.

Planned actions:
- Re-author `nb_dispersion_coefficients.yaml` to lift `phi` spread (`CV`, quantile ratio).
- Preserve S2 RNG event invariants (`gamma`, `poisson`, `nb_final`) and ordering.
- Keep `n_outlets >= 2` semantics for multi merchants only.

Primary surfaces:
- `config/layer1/1A/models/hurdle/exports/.../nb_dispersion_coefficients.yaml`
- `packages/engine/src/engine/layers/l1/seg_1A/s2_nb_outlets/runner.py` (only if coefficient-only tuning is insufficient)

DoD:
- [ ] `CV(phi)` and `P95/P05(phi)` pass `B` hard thresholds.
- [ ] S2 component parity and replay checks pass in S9.
- [ ] No overflow/invalid mu-phi failures introduced.

### S3 Crossborder Candidate Set
Objective: remove near-global candidate saturation and support single-site/base-tier realism.

Planned actions:
- Rebuild candidate policy from globally permissive sets to constrained regionalized sets.
- Emit integerisation and site-sequence artifacts (turn on policy flags).
- Expand S3 emission semantics to include deterministic home-only rows for non-multi merchants so candidate statistics reflect full merchant universe.

Primary surfaces:
- `config/layer1/1A/policy/s3.rule_ladder.yaml`
- `config/layer1/1A/policy/s3.thresholds.yaml`
- `config/layer1/1A/policy/s3.base_weight.yaml`
- `config/layer1/1A/policy/s3.integerisation.yaml`
- `packages/engine/src/engine/layers/l1/seg_1A/s3_crossborder/runner.py`

DoD:
- [ ] `median(candidate_count)` passes hard gate (`<=15`) on full merchant universe.
- [ ] Candidate-to-membership coherence metrics improve into `B` corridor.
- [ ] `s3_integerised_counts` and `s3_site_sequence` are emitted and schema-valid.

### S4 ZTP
Objective: keep ZTP causal link valid and non-pathological after S1/S3 changes.

Planned actions:
- Re-check `theta` and exhaustion posture from crossborder policy.
- Tune only if K-target distributions become incompatible with new candidate realism.

Primary surfaces:
- `config/layer1/1A/policy/crossborder_hyperparams.yaml`
- `packages/engine/src/engine/layers/l1/seg_1A/s4_ztp/runner.py` (only if needed)

DoD:
- [ ] No new ZTP gate failures or exhaustion pathologies.
- [ ] S4 outputs remain consistent with S1/S3 gates.

### S5 Currency Weights
Objective: ensure required `sparse_flag` and supporting diagnostics exist and are valid.

Planned actions:
- Verify and enforce `sparse_flag` emission in all remediation runs.
- Preserve S5 pass receipt and deterministic cache behavior.

Primary surfaces:
- `packages/engine/src/engine/layers/l1/seg_1A/s5_currency_weights/runner.py`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml` (only if contract updates are needed)

DoD:
- [ ] `sparse_flag` exists and validates.
- [ ] S5 receipt + `_passed.flag` present and consumable.

### S6 Foreign Set Selection
Objective: reduce home/legal mismatch inflation and restore size-stratified realism.

Planned actions:
- Recalibrate selection policy to avoid broad foreign realization for small merchants.
- Keep deterministic weighted-gumbel selection and event coverage guarantees.
- Preserve degrade semantics while reducing broad mismatch baseline.

Primary surfaces:
- `config/layer1/1A/policy.s6.selection.yaml`
- `packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_set/runner.py` (only if policy is insufficient)

DoD:
- [ ] `home != legal` share enters `B` corridor (`0.10..0.25`).
- [ ] Size-decile mismatch gradient meets minimum `B` requirement.
- [ ] S6 membership parity and event coverage checks pass in S9.

### S7 Integerisation
Objective: preserve conservation and domain integrity while supporting revised realism posture.

Planned actions:
- Validate S7 counts stay domain-consistent after S3/S6 changes.
- Tune lane settings only if integerisation artifacts create new concentration/pathology.

Primary surfaces:
- `config/layer1/1A/allocation/s7_integerisation_policy.yaml`
- `packages/engine/src/engine/layers/l1/seg_1A/s7_integerisation/runner.py` (if needed)

DoD:
- [ ] Sum/count/domain invariants remain green.
- [ ] No S7 parity regressions in S9 replay.

### S8 Outlet Catalogue
Objective: materialize realistic single-site merchants and stabilize identity semantics.

Planned actions:
- Add deterministic home-only egress rows for single merchants (`single_vs_multi_flag=false`, outlet count=1).
- Keep multi-merchant path unchanged except for policy-driven count/distribution improvements.
- Explicitly enforce/document `site_id` semantics as per-merchant sequence identifier.

Primary surfaces:
- `packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.1A.yaml` (if semantics need formalization)
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml` (if semantics note required)

DoD:
- [ ] `P(outlet_count=1)` passes hard gate and target band trajectory.
- [ ] `single_vs_multi_flag` aligns with S1 gating semantics.
- [ ] No S8 sequence/overflow regression.

### S9 Validation + Certification Harness
Objective: fail closed on realism gates, not only structural contracts.

Planned actions:
- Extend validation evidence with explicit realism metrics and gate verdicts for 1A remediation.
- Preserve existing structural and replay checks.
- Emit machine-readable baseline-vs-post comparison for sign-off.

Primary surfaces:
- `packages/engine/src/engine/layers/l1/seg_1A/s9_validation/runner.py`
- `config/layer1/1A/policy/validation_policy.yaml`
- `docs/reports/eda/segment_1A/` analysis scripts (for external certification pack)

DoD:
- [ ] Hard gates are computed and recorded in run-scoped evidence.
- [ ] Certification decision (`<B`, `B`, `B+`) is reproducible from artifacts.
- [ ] Determinism proof (same seed/policy hash) is included.

## Phase Execution Plan

### Phase 0 - Baseline Lock (no remediation changes)
Sections:
1. Baseline replay under `runs/fix-data-engine/segment_1A` with current configs.
2. Gate matrix extraction from baseline wave.
3. Artifact completeness inventory.

DoD:
- [ ] Baseline run exists in new lineage root.
- [ ] Baseline gate fail matrix documented.
- [ ] No policy/code changes made in this phase.

### Phase 1 - Structural Realism Recovery
Sections:
1. S1 calibration setup.
2. S3 full-universe candidate semantics + regional candidate policy.
3. S8 single-site materialization.
4. S9 parity checks for new single-site path.

DoD:
- [ ] Single-site hard gate passes.
- [ ] Candidate breadth hard gate passes.
- [ ] Structural replay remains green.

### Phase 2 - Geo/Legal Realism Recovery
Sections:
1. S6 selection policy rebalance.
2. S7/S8 downstream conservation checks.
3. S9 mismatch gradient verification.

DoD:
- [ ] `home != legal` share in `B` corridor.
- [ ] Size gradient gate passes.
- [ ] No conservation/path parity regressions.

### Phase 3 - Dispersion Realism Recovery
Sections:
1. S2 dispersion coefficient remediation.
2. Replay stability and component parity verification.
3. S9 dispersion hard-gate certification.

DoD:
- [ ] `CV(phi)` and `P95/P05(phi)` hard gates pass.
- [ ] No S2 RNG/accounting regressions.

### Phase 4 - Artifact/Governance Closure + Certification
Sections:
1. Required artifact emission closure.
2. Determinism rerun checks.
3. Multi-seed robustness pass and final grade decision.

DoD:
- [ ] All required artifacts present.
- [ ] Determinism pass for same seed + hash.
- [ ] Final grade decision documented with evidence.

## Test and Validation Matrix
Required tests per wave:
1. Structural: schema/PK/FK/path-embed/replay checks.
2. Statistical hard gates: single-site share, candidate median, phi spread, artifact presence.
3. Statistical target bands: concentration, mismatch rate/gradient, candidate-realization coherence.
4. Determinism: identical checksums for repeated same-seed same-hash run.
5. Cross-seed stability: minimum 3-seed sweep for final certification wave.

## Failure and Escalation Rules
- Fail closed on any hard gate failure.
- Do not promote to next phase until current phase DoD is fully green.
- If a change improves one realism surface while violating contract/replay invariants, revert that change and redesign.

## Explicit Assumptions (defaulted)
1. Wave strategy is `B first`, then `B+` uplift.
2. First implementation pass is policy/config-first; code changes are applied where policy alone cannot satisfy hard gates.
3. Existing `runs/local_full_run-5/...` remains immutable baseline evidence only.

