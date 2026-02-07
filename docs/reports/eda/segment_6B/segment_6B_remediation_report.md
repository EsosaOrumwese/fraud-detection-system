# Segment 6B Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 6B toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness
This section captures the observed statistical weaknesses in Segment 6B exactly as established in the Segment 6B analytical report. These are the issues remediation must address before 6B can be credibly graded in the `B/B+` band.

### 1.1 Critical blockers (must be fixed first)
1. **Truth-label collapse (critical):** `is_fraud_truth` collapses to a single class (`True`) at full-run scale, with no usable negative class (`LEGIT`) in the training surface.
   - Why this is a blocker: without a negative class, discrimination, calibration, and threshold analysis are structurally invalid.
2. **Bank-view stratification collapse (critical):** bank-view fraud rate is effectively flat (about `0.155`) across class, amount, geography, merchant size, and segment, with near-zero association strength in the report's stratification tests.
   - Why this is a blocker: the bank-view outcome surface behaves like a near-constant allocator, not a risk-sensitive decision surface.
3. **Case-timeline temporal invalidity (critical):** sampled case gaps include non-monotonic and templated values (for example negative and fixed spikes around `-82801`, `0`, `1`, `3599`, `3600`, `82800`) and durations concentrated on fixed values (about `3600s` and `86401s`).
   - Why this is a blocker: case lifecycle timing features become unreliable for realism and downstream model validation.

### 1.2 High-severity realism weaknesses
1. **Amount distribution is over-discretized and near-uniform (high):** flow amounts are concentrated in 8 fixed price points with near-equal shares (~12.5% each), with weak heavy-tail expression relative to policy intent.
   - Impact: spend intensity lacks realistic heterogeneity; amount-based explainability becomes mechanically driven.
2. **Timing surface is over-deterministic (high):** event and flow timestamps are almost perfectly aligned with no meaningful latency surface.
   - Impact: operational timing signals (auth latency, async behavior, delay effects) are largely absent.
3. **Fraud overlay mechanics are narrow (high):** fraud behaves primarily as a bounded amount uplift plus tag assignment, with weak evidence of campaign-specific class/segment/geo targeting richness.
   - Impact: fraud-vs-legit separability can become too shortcut-like (single-feature separation) instead of context-driven.

### 1.3 Medium-severity structural realism limitations
1. **Session realism is thin (medium):** sessionization is close to identity behavior, with many single-arrival / near-zero-duration sessions in the observed posture.
   - Impact: sequence-level behavioral realism is limited.
2. **Attachment/connectivity realism is under-expressive (medium):** entity-linkage surfaces are structurally clean but comparatively under-connected for richer behavior-network realism.
   - Impact: graph-derived behavioral and fraud features are weaker than expected for production-like pattern learning.
3. **Geographic realism is imbalanced (medium):** cross-border is uniformly high while risk outcomes remain largely unstratified by geography.
   - Impact: geography contributes less explanatory signal than expected in realistic fraud ecosystems.

### 1.4 Practical interpretation for remediation
1. Segment 6B is **mechanically consistent** but **statistically non-credible** for supervised fraud modelling in its current state.
2. The highest-impact weaknesses sit in **S4 truth/bank/case outputs**, not in row-count parity mechanics.
3. Remediation should therefore prioritize restoring label validity and risk stratification first, then improving amount/time/campaign behavior depth.

## 2) Expected Statistical Posture (B/B+)
This section defines the target statistical posture for Segment 6B at two acceptance bands:
1. `B` = minimum credible synthetic realism for supervised fraud modeling.
2. `B+` = strengthened realism with stable stratification and reduced template artifacts.

### 2.1 Non-negotiable `B` gates (hard requirements)
1. **Truth surface must be non-degenerate.**
   - `LEGIT` share must be non-zero.
   - `is_fraud_truth_mean` must be within `0.02` to `0.30` for baseline scenario unless an explicitly versioned policy target states otherwise.
2. **Bank-view surface must be risk-stratified.**
   - Cramer’s V(`bank_view_outcome`, `merchant_class`) `>= 0.05`.
   - Cramer’s V(`bank_view_outcome`, `amount_bin`) `>= 0.05`.
   - `max_class_bank_fraud_rate - min_class_bank_fraud_rate >= 0.03`.
3. **Case timelines must be temporally valid.**
   - Negative case-gap rate `= 0`.
   - Case events are monotonic by `case_event_seq`.
   - Combined fixed-gap spike share (`3600s` + `86400s`) `<= 0.50`.

If any of these fail, Segment 6B cannot be graded `B` regardless of improvement elsewhere.

### 2.2 `B` vs `B+` expected posture by realism axis
| Realism axis | `B` target posture | `B+` target posture |
|---|---|---|
| Truth class balance | Non-collapsed truth labels; non-zero `LEGIT`; baseline fraud rate in target band | Seed-stable class balance; truth-label mix aligns tightly with policy target (`JS <= 0.03`) |
| Bank-view stratification | Measurable class and amount dependence (`V >= 0.05`) and visible class spread | Stronger, stable stratification (`V >= 0.08`) with clear geography/segment conditioning |
| Truth vs bank coherence | Fraud overlays produce materially higher bank-fraud probability than non-fraud | Calibrated conditional coherence by class/amount/geo/campaign with seed stability |
| Case temporal realism | No negative gaps; bounded fixed-spike dependence; valid lifecycle ordering | Broad delay support with reduced template spikes (`<= 0.25`) and realistic lag spread |
| Amount realism | No near-uniform 8-point collapse; meaningful heavy-tail expression | Context-conditioned spend surfaces by class/channel/geo with stable tail behavior |
| Event timing realism | Non-degenerate auth latency surface (median `0.3s` to `8s`, P99 `> 30s`) | Latency stratifies by risk/context and remains temporally coherent |
| Campaign realism | Campaign effects not limited to a single amount-uplift mechanism | Distinct campaign signatures (class/segment/geo/time) without trivial separability |
| Session/attachment realism | Non-trivial multi-arrival session structure appears | Rich but controlled session and linkage heterogeneity supporting sequence-level explainability |

### 2.3 Cross-seed stability expectations for realism claims
1. All critical metrics must pass at seeds `{42, 7, 101, 202}`.
2. Cross-seed coefficient of variation for primary gate metrics should be `<= 0.25` unless near-zero by construction.
3. No `PASS_WITH_RISK` unresolved on truth/bank/case surfaces.

### 2.4 Why this posture is required
1. Segment 6B is the final supervision surface used by the platform; realism defects here dominate downstream training behavior even when upstream segments look plausible.
2. A `B/B+` claim must therefore reflect both:
   - structural correctness (already mostly present), and
   - non-flat, context-sensitive statistical behavior (currently missing in key S4 and S2 surfaces).

## 3) Root-Cause Trace
This section traces each observed weakness to its most likely causal mechanism in code/policy terms, including upstream dependencies where relevant. The purpose is to avoid symptom-fixing and target the smallest set of changes that can unlock the largest realism lift.

### 3.1 Causal spine (high-level)
The observed `D+` posture is not a collection of independent issues. It is a connected cascade:
1. `S4` truth mapping collapses non-campaign flows into non-LEGIT labels.
2. `S4` bank-view logic consumes that collapsed truth surface and becomes weakly discriminative.
3. `S4` case timelines use fixed minimum-delay constants instead of sampled delay distributions, creating template spikes.
4. `S2` baseline flow generation compresses amounts into fixed points and ignores event timing policy offsets.
5. `S1` attachment/session mechanics use fallback pools and fixed bucket sessionization, reducing behavioral richness.
6. `S5` validation treats realism corridor failures as `WARN_ONLY`, so these issues can pass seal.

In effect: structural parity passes, but statistical realism fails in the surfaces that matter most for downstream fraud modelling.

### 3.2 Root-cause matrix by weakness
| Observed weakness | Root cause trace | Evidence | Confidence |
|---|---|---|---|
| Truth-label collapse (`is_fraud_truth` degenerate) | `S4` collapses `direct_pattern_map` rules by `fraud_pattern_type` key only. In policy, `fraud_pattern_type=NONE` appears in more than one rule with different conditions and labels; reduced keying causes overwrite and loss of condition-sensitive branching. Net effect: non-campaign flows are no longer reliably mapped to `LEGIT`. | `packages/engine/src/engine/layers/l3/seg_6B/s4_truth_bank_labels/runner.py` (`_load_truth_maps`, `_map_enum_expr`) and `config/layer3/6B/truth_labelling_policy_6B.yaml` (`RULE_NONE_NO_OVERLAY` vs `RULE_OVERLAY_ANOMALY_NO_CAMPAIGN`). Run aggregates show contradiction: `S3 fraud_true=7,342 / 124,724,153` vs `S4 fraud_true=124,724,153 / 124,724,153`. | Very high |
| Bank-view stratification collapse | Bank-view probabilities are conditioned on truth subtype/label. Once truth is degenerate, downstream bank-view is constrained to a narrow probability manifold, producing near-flat rates across class/amount/geo. | `runner.py` uses `p_detect_by_truth_subtype`, `p_dispute_by_truth_subtype`, `p_chargeback_given_dispute` keyed from `truth_subtype` (`~1225-1228`). | High |
| Case timeline temporal invalidity (fixed spikes, invalid dynamics) | Delay policy is loaded but only `min_seconds` is used; delays are applied as constants. Case lifecycle policy is loaded but unused. Event timeline assembly becomes deterministic fixed offsets around those minima. | `runner.py`: `_load_min_delay_seconds`; fixed `detect/dispute/chargeback/case_close` delay assignment; `case_policy` loaded then discarded (`_ = case_policy`); case event timestamps built from `base_ts + fixed_seconds`. `config/layer3/6B/delay_models_6B.yaml` defines rich distributions not executed. | Very high |
| Amount over-discretization / weak tails | `S2` extracts `price_points_minor` and selects by hash index directly; richer family-level tails and distribution contracts in `amount_model_6B` are not used in current generation path. | `packages/engine/src/engine/layers/l3/seg_6B/s2_baseline_flow/runner.py` (`_extract_price_points`, hash-index `amount_index -> amount_minor`). `config/layer3/6B/amount_model_6B.yaml` includes tail models (`LOGNORMAL`, `TRANSFER`) and realism targets that are bypassed. | High |
| Event timing realism collapse | Timing policy is loaded but not applied. Event stream in lean path emits `AUTH_REQUEST` and `AUTH_RESPONSE` with no modeled offset process, collapsing latency realism. | `runner.py` (`timing_policy` loaded then `_ = timing_policy`), event build path with fixed pair generation and no offset-model invocation. `config/layer3/6B/timing_policy_6B.yaml` specifies rich offset models not executed. | Very high |
| Fraud overlay narrowness | `S3` is implemented as a lean deterministic overlay emphasizing campaign tagging + bounded amount shift. Campaign target semantics and multi-instance richness are compressed. | `packages/engine/src/engine/layers/l3/seg_6B/s3_fraud_overlay/runner.py` (`instances = max(1, min(max_instances, 1))` effectively forcing 1 instance/template; overlay path centered on `campaign_id` assignment and `amount_shift_expr`). | High |
| Session/attachment under-expression | `S1` uses fixed timeout bucket sessionization (ignores hard-break/day-boundary process) and warns that key policy linkage fields are unavailable, falling back to global or reduced candidate pools. | `packages/engine/src/engine/layers/l3/seg_6B/s1_attachment_session/runner.py` warnings for missing `arrival.legal_country_iso` and unavailable merchant-linked device/IP candidates; warning for fixed hard-timeout bucket sessionization. | High |
| Realism issues escape gating | `S5` realism corridor checks are configured as `WARN_ONLY` and seal rules do not fail on warn failures, so statistical defects can pass final gate when structural checks pass. | `config/layer3/6B/segment_validation_policy_6B.yaml`: `fail_on_any_warn_failure: false`; realism checks `WARN_*`; notes explicitly state realism corridors warn by default. | Very high |

### 3.3 Policy-vs-implementation attribution
The dominant failure mode in 6B is not simply "bad handcrafted policy values." The stronger pattern is policy richness not being executed by lean runner paths:
1. Delay, timing, and case policies define stochastic and conditional structures.
2. Implemented runners often load these policies but execute reduced deterministic mechanics.
3. Therefore, the remediation priority should start with policy-faithful execution paths (or explicit simplification policies), then tune parameters.

This matters because parameter tuning without execution-faithfulness cannot recover the intended statistical shape.

### 3.4 Upstream dependency footprint
Some 6B weaknesses are locally generated, others are amplified by upstream data shape:
1. **Locally generated in 6B:** truth collapse, fixed-delay case templating, amount/time compression.
2. **Amplified from upstream topology (5B/6A/S1):** thin session behavior, weak attachment diversity, high cross-border posture with limited risk stratification.
3. **Gate-level amplification:** `S5` allows realism failures to ship as pass, delaying detection of statistical regressions.

### 3.5 Root-cause conclusion for remediation design
For remediation planning, the minimal high-impact root-cause set is:
1. `S4` truth mapping logic defect + over-reduction of truth policy semantics.
2. `S4` delay/timeline execution mismatch with `delay_models` and `case_policy`.
3. `S2` amount/timing policy non-execution.
4. `S5` non-blocking realism gates.

Correcting this set should produce the largest immediate grade lift and unlock meaningful downstream improvements before fine-grained parameter tuning.

## 4) Remediation Options (Ranked + Tradeoffs)
This section converts the root-cause trace into practical remediation options. Ranking is based on:
1. Statistical impact on 6B grade.
2. Causal leverage (whether the option fixes root causes or only symptoms).
3. Risk of unintended regression.
4. Dependency burden on upstream segments.

### 4.1 Ranked options overview
| Rank | Option | Primary objective | Grade-lift potential (6B) | Delivery risk |
|---|---|---|---|---|
| 1 | Execution-faithfulness rescue (`S4+S2+S5 core`) | Restore policy-faithful execution in truth/timeline/timing and enforce realism gates | `D+ -> B-` quickly; `B` feasible with seed stability | Medium |
| 2 | `S4` critical containment fix | Remove truth collapse and fixed-delay templating with minimal scope | `D+ -> C+/B-` | Low to Medium |
| 3 | `S2` amount + timing realism restoration | Replace compressed spend/time surfaces with policy-driven stochastic surfaces | `+0.5 to +1.0` letter after Option 1/2 | Medium |
| 4 | `S3` campaign depth restoration | Move fraud behavior beyond amount uplift into contextual campaign signatures | `+0.3 to +0.7` letter after Option 1 | Medium to High |
| 5 | `S1` attachment/session realism uplift | Increase sequence and connectivity realism | `+0.2 to +0.5` letter | High (upstream dependent) |
| 6 | Policy-only retuning (without code-path fixes) | Tune thresholds/coefficients only | Limited (`D+/C` ceiling) | Low technical, high statistical failure risk |

### 4.2 Option 1 (recommended first): Execution-faithfulness rescue (`S4+S2+S5 core`)
#### 4.2.1 What changes
1. `S4 truth`: replace reduced map-lookup behavior with ordered rule evaluation for `direct_pattern_map` conditions so `fraud_pattern_type=NONE` no longer collapses into a single overwritten outcome.
2. `S4 delays/cases`: sample from configured delay distributions in `delay_models_6B` instead of using only `min_seconds`; execute case lifecycle semantics from `case_policy_6B` rather than fixed event templates.
3. `S2 timing`: apply timing policy offsets (at minimum `AUTH_REQUEST -> AUTH_RESPONSE`) so event-time deltas are not degenerate.
4. `S5 gating`: promote critical realism checks from warning-only behavior to fail-closed behavior for truth degeneracy, timeline validity, and bank-view collapse conditions.

#### 4.2.2 Why this is ranked first
1. It attacks the principal failure chain rather than cosmetic metrics.
2. It restores validity of the supervision surface before model-level concerns.
3. It yields the largest realism gain per unit of engineering effort.

#### 4.2.3 Tradeoffs and risks
1. Multiple key surfaces shift simultaneously, making attribution of post-change movement harder unless validation is staged.
2. Runtime may increase due to distribution sampling and richer event generation.
3. Existing downstream assumptions built around lean deterministic behavior may require adaptation.

#### 4.2.4 Expected statistical effect
1. Truth class balance recovers from degenerate state.
2. Bank-view outcomes regain conditional variation.
3. Case-gap spikes weaken materially as distributional delays replace constants.
4. Segment grade likely moves to `B-` quickly, with `B` possible after seed-stability confirmation.

### 4.3 Option 2: `S4` critical containment fix
#### 4.3.1 What changes
1. Fix truth map collision behavior for `NONE` and other multi-condition rule families.
2. Replace fixed delay constants with sampled delays in S4.
3. Execute minimal case policy ordering and timeline rules.

#### 4.3.2 Why it is still valuable
1. It removes the most severe and obviously invalid statistical artifacts.
2. It can be delivered faster than a broader multi-stage rescue.

#### 4.3.3 Limitation
1. Even with S4 fixed, 6B remains capped by S2 amount/timing compression and S3 campaign narrowness.
2. This option is best treated as containment, not completion.

### 4.4 Option 3: `S2` amount and timing realism restoration
#### 4.4.1 What changes
1. Use policy-defined amount-family behavior rather than fixed-point hash-only assignment.
2. Re-enable timing offset models from timing policy so event transitions produce realistic latency surfaces.
3. Preserve monotonic constraints while allowing non-degenerate spread.

#### 4.4.2 Why it matters
1. Amount/time features are first-class model signals; if they are template-like, explainability and calibration degrade.
2. This option removes major synthetic shortcuts that currently dominate separability.

#### 4.4.3 Tradeoffs
1. Higher computational complexity in generation and validation.
2. Wider stochastic spread can increase run-to-run variability unless guardrails are tuned.

### 4.5 Option 4: `S3` campaign depth restoration
#### 4.5.1 What changes
1. Use true campaign multiplicity (`max_instances_per_seed`) and richer target semantics.
2. Expand effect channels beyond amount uplift to include contextual and temporal signatures.
3. Preserve guardrails while introducing campaign heterogeneity by class/segment/geo/time.

#### 4.5.2 Why it matters
1. Fraud realism should be campaign-structured, not a single scalar uplift overlay.
2. Better campaign differentiation supports more realistic downstream detection logic.

#### 4.5.3 Tradeoffs
1. Calibration becomes harder because campaign heterogeneity can alter class balance unexpectedly.
2. Requires stronger per-campaign validation slices to avoid overfitting one campaign family.

### 4.6 Option 5: `S1` attachment and session realism uplift
#### 4.6.1 What changes
1. Move from fixed timeout bucket sessionization toward boundary-aware session formation.
2. Improve attachment context by reducing fallback/global candidate behavior where feasible.
3. Increase behavioral network heterogeneity while retaining deterministic reproducibility contracts.

#### 4.6.2 Why this is rank 5
1. It is meaningful for realism, but not the dominant blocker for 6B grade.
2. It depends on upstream field/link availability and therefore carries higher dependency risk.

### 4.7 Option 6: policy-only retuning
#### 4.7.1 Why it is explicitly last
1. It cannot repair logic paths that currently bypass policy richness.
2. It risks "metric gaming" where a few summary numbers improve but structural realism defects remain.
3. It should only be used after execution-faithfulness is restored.

### 4.8 Recommended execution sequence for 6B
1. Execute Option 1 first as the primary rescue path.
2. If constrained, use Option 2 as an initial containment pass, then merge into Option 1 scope.
3. Follow immediately with Option 3 to remove amount/time compression.
4. Add Option 4 to deepen fraud realism once truth/bank/time surfaces are stable.
5. Implement Option 5 after upstream dependencies are validated.

### 4.9 Decision framing for Section 5
Section 5 should select one of two practical paths:
1. **Preferred path:** Option 1 + Option 3 as Wave A, Option 4 as Wave B, Option 5 as Wave C.
2. **Constrained path:** Option 2 as immediate containment, then converge to preferred path.

The preferred path is more likely to achieve `B/B+` without hidden residual defects.

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

## 6) Validation Tests + Thresholds

## 7) Expected Grade Lift (Local + Downstream Impact)
