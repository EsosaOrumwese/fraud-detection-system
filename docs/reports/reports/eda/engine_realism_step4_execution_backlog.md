# Engine Realism — Step 4 Execution Backlog
Date: 2026-02-07  
Baseline run: `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`  
Scope: Convert Step 3 hypotheses into executable remediation backlog and validation sequence.  
Status: Planning only. No fixes are implemented in this document.

---

## 0) Purpose
This backlog operationalizes Step 3:
1. One work package per Step 2 `Critical/High` gap (`26` total).
2. Explicit file-level edit targets (policy + implementation).
3. Expected metric movement tied to Step 3 acceptance gates.
4. Execution sequence with dependency control and fail-closed run gates.

---

## 1) Execution Protocol
Run protocol per wave:
1. Apply only wave-scoped changes.
2. Generate a sealed run for seed set `{42, 7, 101, 202}`.
3. Compute Step 3 gate metrics.
4. Fail the wave if any critical gate fails or if more than 2 high gates regress.
5. Record results in a wave evidence note before moving to next wave.

Output artifacts per wave:
- `wave_{N}_change_set.md`
- `wave_{N}_metrics.csv`
- `wave_{N}_gate_report.md`

---

## 2) Priority Waves
Wave order is strict:
1. `Wave 0`: `1.1`, `1.2`, `1.3`
2. `Wave 1`: `1.4`, `1.5`, `2.12`, `2.13`, `2.14`, `2.15`, `2.7`, `2.8`, `2.18`, `2.19`, `2.9`, `2.10`, `2.20`
3. `Wave 2`: `2.1`, `2.2`, `2.3`, `2.4`, `2.5`, `2.6`, `2.17`, `2.11`, `2.16`, `2.21`

No downstream wave starts until upstream wave gates pass.

---

## 3) Backlog (One-to-One with Step 2)

### Wave 0 (Critical final-truth blockers)
| WP | Gap | Segment | Primary files to change | Planned change | Expected metric movement | Gate refs |
|---|---|---|---|---|---|---|
| WP-001 | `1.1` | 6B | `config/layer3/6B/truth_labelling_policy_6B.yaml`, `packages/engine/src/engine/layers/l3/seg_6B/s4_truth_bank_labels/runner.py` | Replace one-key truth mapping with composite key `(fraud_pattern_type, overlay_anomaly_any)` and collision-safe loader. | `is_fraud_truth_mean` drops from `1.0` into policy band; `LEGIT` class restored. | Step 3 `1.1` |
| WP-002 | `1.2` | 6B | `config/layer3/6B/truth_labelling_policy_6B.yaml` (bank-view section), `packages/engine/src/engine/layers/l3/seg_6B/s4_truth_bank_labels/runner.py` | Introduce covariate-conditioned bank-view sampling by class/amount/cross-border. | Cramer’s V and class-rate spread move above minimums. | Step 3 `1.2` |
| WP-003 | `1.3` | 6B | `config/layer3/6B/truth_labelling_policy_6B.yaml` (delay models), `packages/engine/src/engine/layers/l3/seg_6B/s4_truth_bank_labels/runner.py` | Shift from fixed-min delays to sampled delays with monotonic timeline enforcement per case. | Negative gap rate to zero; fixed spike share reduced. | Step 3 `1.3` |

### Wave 1 (High propagation substrate)
| WP | Gap | Segment | Primary files to change | Planned change | Expected metric movement | Gate refs |
|---|---|---|---|---|---|---|
| WP-004 | `1.4` | 3B | `config/layer1/3B/virtual/cdn_country_weights.yaml`, `config/layer1/3B/virtual/cdn_key_digest.yaml`, `packages/engine/src/engine/layers/l1/seg_3B/s2_edge_catalogue/runner.py` | Replace fixed edge cardinality/weights with merchant-conditioned edge count and non-uniform edge weighting. | Edge-count CV, edge-weight Gini increase materially. | Step 3 `1.4` |
| WP-005 | `1.5` | 3B | same as WP-004 | Add explicit settlement-country uplift and distance-aware reweighting. | Settlement overlap uplift and anchor-distance reduction. | Step 3 `1.5` |
| WP-006 | `2.12` | 6A | `config/layer3/6A/priors/ip_count_priors_6A.v1.yaml`, `packages/engine/src/engine/layers/l3/seg_6A/s4_device_graph/runner.py` | Recalibrate IP-type priors and ensure realized sampling respects configured regional shares. | IP-type error vs prior <= threshold. | Step 3 `2.12` |
| WP-007 | `2.13` | 6A | same as WP-006 | Raise linkage propensity (`p_zero`/lambda balance) while preserving realistic sparsity tails. | Device->IP linkage rate increase to target band. | Step 3 `2.13` |
| WP-008 | `2.14` | 6A | `config/layer3/6A/priors/account_per_party_priors_6A.v1.yaml`, `packages/engine/src/engine/layers/l3/seg_6A/s2_accounts/runner.py` | Enforce per-type `K_max` hard/soft constraints with auditable breach logic. | `K_max` breach rate near zero. | Step 3 `2.14` |
| WP-009 | `2.15` | 6A | `packages/engine/src/engine/layers/l3/seg_6A/s5_fraud_posture/runner.py` | Add graph-conditional risk propagation from party to linked entities. | Conditional risk uplifts and MI increase. | Step 3 `2.15` |
| WP-010 | `2.7` | 2B | `config/layer1/2B/policy/alias_layout_policy_v1.json`, `packages/engine/src/engine/layers/l1/seg_2B/s1_site_weights/runner.py` | Replace pure uniform site weighting with policy-driven concentration families by merchant profile. | Top-1 share and entropy variance increase. | Step 3 `2.7` |
| WP-011 | `2.8` | 2B | `config/layer1/2B/policy/day_effect_policy_v1.json`, `packages/engine/src/engine/layers/l1/seg_2B/s3_day_effects/runner.py` | Move from global sigma to merchant-/class-conditioned sigma regimes. | Sigma diversity and temporal CV separation increase. | Step 3 `2.8` |
| WP-012 | `2.18` | 2B | `packages/engine/src/engine/layers/l1/seg_2B/s4_group_weights/runner.py` plus WP-010/011 policies | Tune renormalization and group-mass dynamics to reduce daily top-1 collapse. | `max p_group >=0.9` frequency down to target. | Step 3 `2.18` |
| WP-013 | `2.19` | 2B | scenario roster policy source, `packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py` (input semantics) | Introduce churn/missingness and variable per-day arrival multiplicity in roster generation contract. | Rectangularity breaks; lifecycle variability rises. | Step 3 `2.19` |
| WP-014 | `2.9` | 3A | `config/layer1/3A/allocation/country_zone_alphas.yaml`, `packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/runner.py` | Rebalance extreme alphas and add class/size-conditioned priors for diversity. | Top-1 and entropy metrics move toward targets. | Step 3 `2.9` |
| WP-015 | `2.10` | 3A | `config/layer1/3A/policy/zone_mixture_policy.yaml`, `packages/engine/src/engine/layers/l1/seg_3A/s1_escalation/runner.py` | Retune escalation thresholds and decision criteria using observed site/zone regimes. | Escalation effect on multi-zone support increases. | Step 3 `2.10` |
| WP-016 | `2.20` | 3A | `packages/engine/src/engine/layers/l1/seg_3A/s4_zone_counts/runner.py` | Reduce integerization compression (stochastic rounding or residual-preserving allocation). | Pre->post variance retention above threshold. | Step 3 `2.20` |

### Wave 2 (Upstream shaping + timing + residuals)
| WP | Gap | Segment | Primary files to change | Planned change | Expected metric movement | Gate refs |
|---|---|---|---|---|---|---|
| WP-017 | `2.1` | 1A | `packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py` and relevant 1A policy | Introduce explicit single-site generation path and preserve policy traceability. | Single-site share enters target band. | Step 3 `2.1` |
| WP-018 | `2.2` | 1A | `config/layer1/1A/policy/s3.rule_ladder.yaml`, `packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_set/runner.py` | Constrain legal-country divergence with tiered expansion logic. | Home/legal mismatch reduced and tier-structured. | Step 3 `2.2` |
| WP-019 | `2.3` | 1A | same as WP-018 | Retune candidate breadth caps and admission ladder. | Candidate median/IQR/realization ratios enter bands. | Step 3 `2.3` |
| WP-020 | `2.4` | 1A | `config/layer1/1A/models/hurdle/hurdle_simulation.priors.yaml` and coefficient bundle path | Increase dispersion heterogeneity in hand-authored coefficients and ensure applied variance survives generation. | `phi` CV and tail ratios increase above floor. | Step 3 `2.4` |
| WP-021 | `2.5` | 1B | `config/layer1/1B/policy/policy.s2.tile_weights.yaml` and 1B placement logic | Rebalance global region/country weights and reduce template artifacts. | Region share errors and country HHI improve. | Step 3 `2.5` |
| WP-022 | `2.6` | 2A | `packages/engine/src/engine/layers/l1/seg_2A/s1_tz_lookup/runner.py`, `config/layer1/2A/timezone/tz_nudge.yml`, `config/layer1/2A/timezone/tz_overrides.yaml` | Reduce singleton and nearest-fallback dominance with stronger country/tz plausibility checks. | Singleton share and top-1 tz concentration decline. | Step 3 `2.6` |
| WP-023 | `2.17` | 2A | same as WP-022 | Add explicit invalid-pair rejection/audit and constrained fallback precedence. | Implausible country->tzid rate and out-threshold fallback drop. | Step 3 `2.17` |
| WP-024 | `2.11` | 5B | `packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/numba_kernel.py`, `packages/engine/src/engine/layers/l2/seg_5B/s5_validation_bundle/runner.py` | Correct DST offset handling and strengthen validation from warn-only to gate-aware in realism mode. | DST mismatch reduced to near-zero. | Step 3 `2.11` |
| WP-025 | `2.16` | 6B | `config/layer3/6B/amount_model_6B.yaml`, `packages/engine/src/engine/layers/l3/seg_6B/s2_baseline_flow/runner.py` | Move from uniform hash-point amounts to merchant-conditioned price profiles; introduce auth latency model. | Amount and latency realism metrics enter target bands. | Step 3 `2.16` |
| WP-026 | `2.21` | 3B | `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py` plus classification policy artifact | Expand beyond MCC/channel-only evidence with additional conditioned features. | Within-pair variance and evidence lift increases. | Step 3 `2.21` |

---

## 4) Cross-WP Dependencies
Hard dependencies:
1. `WP-001` must complete before `WP-002` and `WP-003` validation (truth surface foundation).
2. `WP-004` and `WP-005` should be implemented together to avoid false attribution in 3B metrics.
3. `WP-010`, `WP-011`, and `WP-012` should be executed in one experiment branch (coupled dynamics).
4. `WP-014`, `WP-015`, `WP-016` should be executed together (3A prior/escalation/count coupling).
5. `WP-022` and `WP-023` should be delivered together (same fallback system).

Soft dependencies:
1. `WP-021` helps `WP-022/023` but is not a hard blocker.
2. `WP-006/007/008/009` should be evaluated as a bundle for 6A realism signal.

---

## 5) Statistical Validation Backlog
Validation scripts to add (or extend) before implementation wave execution:
1. `validate_step4_wave0.py`:
- truth class balance, JS distance, bank-view stratification, case monotonicity.
2. `validate_step4_wave1.py`:
- edge concentration metrics, settlement uplift, graph risk propagation, routing entropy/dominance.
3. `validate_step4_wave2.py`:
- candidate breadth, dispersion CV/tails, timezone plausibility, DST checks, amount/latency realism.
4. `validate_step4_full_engine.py`:
- aggregate gate pass/fail and weighted segment-grade recalibration.

Each validator must emit:
- `metric_name`, `value`, `threshold`, `pass_bool`, `seed`, `segment`, `wave`.

---

## 6) Risk Register
Execution risks:
1. Over-correction risk: moving from flat to noisy non-explainable outputs.
2. Coupled-change ambiguity: multi-WP waves can hide causal attribution.
3. Performance risk: richer stochastic models may increase runtime significantly.
4. Determinism drift risk: added randomness may break replay assumptions.

Mitigations:
1. Preserve deterministic seed discipline and run all fixed seeds each wave.
2. Use ablation branches inside each wave bundle where feasible.
3. Track runtime and memory deltas as first-class metrics.
4. Require policy-surface documentation for every new stochastic control.

---

## 7) Definition of Done for Step 4
Step 4 is done when:
1. All `26` work packages are explicitly mapped and sequenced.
2. Dependencies and validation scripts are defined.
3. Run-gating protocol is declared for wave execution.
4. No work package remains without target files or measurable acceptance movement.

---

## 8) Next Step
Step 5 should execute `Wave 0` only, produce gate reports, and stop for review before `Wave 1`.
