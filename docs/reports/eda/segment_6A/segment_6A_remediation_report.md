# Segment 6A Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 6A toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness
This section captures the observed statistical weaknesses in Segment 6A from the analytical report and prioritizes them by realism impact on downstream layers (especially 6B).

### 1.1 Primary weaknesses (material for `B/B+`)
1. **IP realism is the largest mismatch vs policy intent.**  
   Observed IP type mix is heavily residential (`~0.96` observed vs `~0.38` expected), device->IP linkage coverage is sparse (`~14.8%` of devices linked), and linked IP degree is strongly heavy-tailed (up to `1,741` devices per IP).
   - Why this is material: it creates an over-dominant shared-IP signal that can overwhelm other fraud-relevant cues downstream.
2. **Account holding tails violate policy caps (`K_max`) at scale.**  
   The report shows widespread and large cap breaches, not isolated outliers:
   - `RETAIL_CREDIT_CARD_STANDARD`: `K_max=4`, observed max `79`, breach count `25,163`
   - `RETAIL_SAVINGS_INSTANT`: `K_max=4`, observed max `70`, breach count `23,495`
   - `RETAIL_PERSONAL_LOAN_UNSECURED`: `K_max=2`, observed max `23`, breach count `9,434`
   - `BUSINESS_CREDIT_CARD`: `K_max=5`, observed max `135`, breach count `382`
   - Why this is material: tail behavior is structurally outside intended policy bounds, which distorts ownership realism and downstream feature distributions.
3. **Risk propagation along the entity graph is weak.**  
   Risky party roles do not materially propagate into riskier account/device roles, and high-sharing IPs are only weakly enriched for high-risk labels except near far-tail degree.
   - Why this is material: the causal realism chain (`risky owner -> risky assets -> risky network`) is weakened, reducing explainability quality for fraud posture.
4. **Device/IP role vocabularies are simplified relative to priors.**  
   Direct policy-to-observed validation for device/IP role priors is blocked by vocabulary mismatch/simplification.
   - Why this is material: intended risk semantics are not fully auditable, making realism tuning harder and less traceable.

### 1.2 Secondary weaknesses (mainly cap `B+`, not `B`)
1. **Country/segment behavior is highly policy-driven and uniform.**  
   The geography/segment surface is coherent, but mostly deterministic with limited emergent heterogeneity.
2. **Instrument composition is near-target, but totals can be inflated.**  
   Within-account-type composition aligns with priors, yet absolute totals can be lifted by minimum-attachment mechanics.

### 1.3 Net Section-1 interpretation
1. Segment 6A does not have the hard correctness collapse seen in 6B.
2. However, four material realism gaps block a robust move from `B-` to `B/B+`:
   - IP prior divergence
   - `K_max` breach at scale
   - weak risk propagation
   - role-vocabulary traceability gap
3. These are the priority weaknesses Section 2 onward must target with explicit acceptance criteria.

## 2) Expected Statistical Posture (B/B+)
### 2.1 Non-negotiable `B` gates (hard requirements)
1. **Policy-traceable roles must be auditable.**  
   Every runtime `device_role` and `ip_role` must map to a policy role family via an explicit mapping table.
   - Gate: mapping coverage `= 100%`; unmapped role rate `= 0`.
2. **`K_max` semantics must be coherent.**  
   Either:
   - hard-cap mode: over-cap rate `= 0` for all account types, or
   - revised-cap mode: versioned cap policy with observed over-cap rate `<= 0.5%` per type and p99 within revised cap.
   - Gate fails if neither condition is met.
3. **IP prior divergence must be materially reduced.**  
   Gate on absolute share error (`observed - target`) by IP type:
   - `B`: max absolute error `<= 15 pp`
   - `B+`: max absolute error `<= 8 pp`
4. **Device->IP linkage must be non-trivially realistic.**  
   Gate:
   - `B`: device->IP coverage `>= 25%`
   - `B+`: device->IP coverage `>= 35%`
   plus bounded extreme sharing tail.
5. **IP-sharing tail must be bounded by policy, not accidental.**  
   Gate:
   - `B`: p99(`devices_per_ip`) `<= 120`, max `<= 600`
   - `B+`: p99(`devices_per_ip`) `<= 80`, max `<= 350`
   unless explicitly versioned as intentional infrastructure simulation.
6. **Risk propagation must be observable.**  
   Risky party roles should increase risky-account and risky-device likelihood.
   - `B`: odds-ratio(risky account | risky party vs clean party) `>= 1.5`; same for risky device `>= 1.5`
   - `B+`: both `>= 2.0`

### 2.2 `B` vs `B+` expected posture by realism axis
| Realism axis | `B` target posture | `B+` target posture |
|---|---|---|
| Policy traceability | Full role mapping and auditable policy->outcome checks | Same, plus automated fail-closed checks on mapping drift |
| Account-holding realism | `K_max` coherent (hard-cap or revised-cap mode), low breach rate | Tight cap compliance with stable tails across seeds |
| IP type realism | Large prior mismatches corrected to moderate error band | Close alignment to priors with small residual errors |
| Device-IP linkage realism | Linkage no longer sparse; meaningful multi-link structure | Stronger but controlled linkage with realistic heterogeneity |
| IP degree tail realism | Heavy tail present but bounded and explainable | Tail calibrated and stable, no dominating outlier regime |
| Risk propagation realism | Directionally correct owner->asset->network risk uplift | Stronger, consistent propagation with clear effect sizes |
| Geography/segment realism | Still policy-led but less uniform where priors expect variation | Controlled heterogeneity by country/segment without instability |
| Cross-layer utility for 6B | Identity graph supports non-flat downstream risk signals | Identity graph provides stable, explainable conditioning for 6B |

### 2.3 Quantitative acceptance targets to support grading
1. **Association/effect-size floor for propagation:**  
   Cramer's V (or equivalent effect-size) for party-role vs account/device risk labels:
   - `B`: `>= 0.05`
   - `B+`: `>= 0.08`
2. **Distribution alignment:**  
   Jensen-Shannon divergence (JSD) between policy target and observed distributions (IP types, role families):
   - `B`: `<= 0.08`
   - `B+`: `<= 0.05`
3. **Concentration controls:**  
   Country concentration can remain top-heavy, but IP concentration must not dominate all risk signals; track Gini/HHI with explicit upper bounds defined from revised policy baseline.

### 2.4 Cross-seed stability expectations
1. Evaluate seeds `{42, 7, 101, 202}`.
2. Critical metrics must pass on every seed.
3. CV across seeds:
   - `B`: `<= 0.25`
   - `B+`: `<= 0.15`

### 2.5 Why this posture is required
1. Segment 6A is the identity and topology substrate for 6B; if 6A remains over-skewed or under-linked, 6B risk behavior remains flat or shortcut-driven.
2. Moving 6A from `B-` to `B/B+` requires fixing the specific bottlenecks already observed: IP mismatch, cap violations, weak propagation, and traceability gaps.
3. These targets preserve synthetic-policy control while restoring enough structural realism for explainable downstream fraud modelling.

## 3) Root-Cause Trace
This section traces each primary weakness to its most likely originating mechanism in `S1-S5`, separates policy vs implementation responsibility, and identifies the minimum cause set that must be fixed for a credible move to `B/B+`.

### 3.1 Causal spine (high level)
1. `S1/S2` priors are applied tightly, so population and product mix look policy-clean.
2. `S2` cap semantics (`K_max`) are not enforced as hard global party-level constraints after allocation/merge, so holdings tails exceed intended limits.
3. `S3` applies a minimum-attachment floor, so low-lambda account types get inflated instrument totals even when composition remains policy-aligned.
4. `S4` IP generation/linkage mechanics diverge from priors, creating sparse device->IP coverage plus extreme shared-IP concentration.
5. `S5` risk roles are assigned with weak cross-entity coupling and simplified vocabularies, so risk propagation across party->account/device/IP is muted.
6. Validation posture is permissive enough for these drifts to pass, so deviations become accepted output rather than fail-closed defects.

### 3.2 Root-cause matrix (issue by issue)
| Weakness (from Section 1) | Direct evidence | Most likely root cause | Layer | Confidence |
|---|---|---|---|---|
| IP type mismatch + sparse linkage + heavy IP tail | Residential ~96% vs expected ~38%; device->IP coverage ~14.8%; devices/IP p99 ~172 | `S4` linkage/count rules not honoring IP priors for most device groups; strong reuse regime; likely fallback/defaulting toward residential; no strict gate on prior-divergence | Policy + implementation | High |
| `K_max` breaches at scale | Large exceedances (for example `RETAIL_CREDIT_CARD_STANDARD` max 79 vs cap 4) | `S2` cap applied locally (cell/step) but not globally re-clamped per party-account_type after integerization/merge; semantics drift between target cap and hard cap | Implementation + policy semantics | High |
| Weak risk propagation | Risky party roles only weakly enrich risky account/device outcomes | `S5` role assignment mostly independent by entity type (hash-based), with insufficient conditional dependence on ownership graph; sparse IP linkage further weakens propagation path | Policy + implementation | Medium-High |
| Instrument totals inflated for low-target products | Composition matches priors, but low-lambda types observe ~1.0 instruments/account | Floor rule (at least one bank-rail instrument) overrides low lambda intent; totals inflate while shares still look aligned | Implementation (intentional mechanic) | High |
| Geography/segment over-uniformity | Country segment mixes close to global; region synthetic hashing | Global priors dominate; missing sealed country->region taxonomy replaced by hash mapping; limited country-conditioned modulation | Design/policy choice | High |
| Device/IP role traceability gap | Observed role vocabulary simplified vs richer priors | Runtime role vocabulary collapsed without formal mapping table; policy-to-observed checks become non-auditable | Implementation/design deviation | High |

### 3.3 Attribution split (where failure actually comes from)
1. Policy-authoring causes:
   - Under-specified coupling constraints between entity risk layers.
   - Priors that are globally smooth with weak country/segment conditioning.
   - Ambiguous cap semantics (`K_max` treated as soft target vs hard invariant).
2. Implementation causes:
   - Post-allocation hard-cap enforcement missing or incomplete.
   - IP linkage/type assignment path not conforming to intended priors.
   - Minimum-instrument floor introduces structural count inflation.
   - Vocabulary simplification without mandatory mapping layer.
3. Validation causes:
   - Gates emphasize structural correctness over distributional conformance.
   - Relaxed thresholds allow major realism drift to PASS.

### 3.4 Upstream/downstream dependency trace
1. Upstream (`5A/5B`) is not the primary source of these 6A weaknesses.
2. These 6A weaknesses directly shape `6B` model-facing realism:
   - Weak party->asset risk coupling reduces explainable fraud separation downstream.
   - Shared-IP extreme tails can create shortcut features (or noisy dominance).
   - Inflated holdings/instruments alter exposure surfaces and volume-conditioned behavior.
3. Therefore, 6A fixes are prerequisite for stable 6B lift toward `B/B+`.

### 3.5 Minimal root-cause set to target first
1. Enforce explicit `K_max` semantics globally after allocation.
2. Rebuild `S4` IP prior application and linkage coverage controls.
3. Add conditional risk propagation rules in `S5` (party state must influence account/device/IP risk odds).
4. Introduce mandatory role-mapping table for device/IP vocabulary parity.
5. Convert realism checks from advisory to fail-closed for these four surfaces.

## 4) Remediation Options (Ranked + Tradeoffs)
This section defines candidate remediation paths for the Section 3 causes, ranks them by statistical impact and execution risk, and frames tradeoffs explicitly against the `B/B+` target posture in Section 2.

### 4.1 Ranking framework
Options are ranked on four criteria:
1. Direct impact on the non-negotiable `B` gates in Section 2.
2. Downstream impact on `6B` realism and fraud explainability.
3. Implementation blast radius and regression risk.
4. Auditability and repeatability (how easy it is to validate and keep stable across seeds).

### 4.2 Ranked options
| Rank | Option | What changes | Primary gates impacted | Why it helps | Tradeoffs / risks |
|---|---|---|---|---|---|
| 1 | Global `K_max` enforcement pass in `S2` | Add final per-party, per-account-type cap pass after integerization/merge | `K_max` coherence, tail control | Closes the largest hard mismatch quickly; directly reduces unrealistic account tails | May alter account totals by type; may require minor rebalancing to preserve macro product mix |
| 2 | IP prior-constrained generation in `S4` | Enforce IP type priors, explicit device->IP coverage targets, and bounded IP reuse tail | IP share error, linkage coverage, devices/IP p99/max | Highest realism lift on the weakest surface (IP) | Highest calibration complexity; aggressive tuning can over-correct and mute legitimate shared-IP behavior |
| 3 | Risk propagation coupling in `S5` | Make account/device/IP risk assignment conditional on party risk state and graph context | Propagation odds-ratio and effect-size thresholds | Restores causal realism chain (`risky owner -> risky assets -> risky network`) and downstream explainability | If coupling is too strong, separability becomes unrealistically easy for downstream models |
| 4 | Role vocabulary mapping contract | Introduce explicit runtime-role -> policy-role-family mapping with full coverage checks | Policy traceability gate, auditability gate | Converts currently non-auditable device/IP role surfaces into testable surfaces | Does not fix distributions by itself; must be paired with options 2/3 for substantive realism gain |
| 5 | Instrument floor redesign in `S3` | Replace universal minimum-instrument behavior with account-type-specific floor policy | Instrument totals realism | Eliminates low-lambda inflation while retaining required rails where intended | Can reduce operational completeness if floor policy is over-tightened |
| 6 | Fail-closed realism gates in validation | Promote distribution conformance checks from advisory/relaxed to hard PASS/FAIL | All critical `B` gates | Prevents recurrence of drift and ensures fixes remain durable across reruns | More run failures during tuning wave until thresholds and code paths are stable |
| 7 | Country-conditioned modulation of segment/product priors | Add bounded country-level deltas around global priors | `B+` heterogeneity posture | Reduces over-uniform country behavior and improves synthetic geographic realism | Additional policy complexity and calibration overhead; not required for minimum `B` |
| 8 | Cross-seed robustness hardening | Tune and validate on seeds `{42, 7, 101, 202}` with CV limits | Stability gates | Reduces seed luck risk and improves confidence in grading | Increased runtime and analysis overhead |

### 4.3 Option packages (execution bundles)
1. Package A - minimum viable path to `B`:
   - Includes options `1 + 2 + 3 + 4 + 6`.
   - Rationale: this combination closes all current hard blockers (cap semantics, IP realism, propagation, traceability, fail-closed enforcement).
2. Package B - path to durable `B+`:
   - Includes Package A plus options `5 + 7 + 8`.
   - Rationale: adds heterogeneity realism, removes instrument-floor artifacts, and hardens cross-seed stability.

### 4.4 Tradeoff analysis by realism axis
1. Account-holding realism:
   - Best direct lever: Option 1.
   - Main risk: preserving account-type macro shares after cap enforcement.
2. IP/network realism:
   - Best direct lever: Option 2.
   - Main risk: replacing one unrealistic shape with another through over-correction.
3. Fraud posture explainability:
   - Best direct lever: Option 3.
   - Main risk: synthetic over-separation if conditional uplift is too high.
4. Governance and auditability:
   - Best direct levers: Options 4 and 6.
   - Main risk: temporary friction from stricter PASS/FAIL thresholds during tuning.
5. B+ nuance (not required for baseline B):
   - Best levers: Options 5, 7, and 8.
   - Main risk: increased calibration and runtime overhead.

### 4.5 Recommended ordering
1. Start with options `1, 2, 3` to fix the largest statistical failures.
2. Immediately pair with options `4, 6` so improvements become auditable and fail-closed.
3. Add options `5, 7, 8` only after the `B` gates pass consistently.

### 4.6 Section-4 decision output
1. The preferred strategy for 6A is Package A as the mandatory baseline.
2. Package B is the expansion path once Package A passes all Section 2 `B` gates.
3. Section 5 should therefore specify exact deltas for Package A first, with Package B changes explicitly marked as phase-2 enhancements.

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)
This section converts Section 4 (Package A) into exact, implementation-grade deltas for `6A`. The objective is to pass all `B` gates first, then expand to `B+`.

### 5.1 Scope and ordering
1. Phase-1 (mandatory for `B`): `S2 cap enforcement`, `S4 IP realism controls`, `S5 propagation coupling`, `role mapping contract`, `fail-closed validation`.
2. Phase-2 (only after Phase-1 passes): `S3 instrument floor refinement`, `country-conditioned modulation`, `cross-seed hardening`.

### 5.2 Delta Set A - `S2` global `K_max` enforcement (mandatory)
1. File to change: `packages/engine/src/engine/layers/l3/seg_6A/s2_accounts/runner.py`.
2. Current behavior to replace:
   - `count_model_id` is validated against supported models.
   - `K_max` is declared in priors, but there is no final hard-cap pass after merge.
   - Warning-only guard exists for total lambda (`max_total_lambda_by_type`) and does not enforce party-level account caps.
3. Required code delta:
   - Add final `enforce_kmax_per_party_account_type(...)` pass after integerization and before artifact writeout.
   - Pull `K_max` by `(party_type, account_type)` from `config/layer3/6A/priors/account_per_party_priors_6A.v1.yaml`.
   - If a party exceeds `K_max` for a type, keep top `K_max` rows by deterministic ranking key; move overflow to a typed redistribution pool.
   - Redistribute overflow within same allocation cell to under-cap parties using residual-weighted sampling; if no legal receiver exists, drop overflow deterministically and record evidence.
   - Add post-pass invariant check: no `(party_id, account_type)` may exceed cap.
4. New runtime evidence counters (required):
   - `kmax_overflow_rows`
   - `kmax_redistributed_rows`
   - `kmax_dropped_rows`
   - `kmax_postcheck_violations`
5. Policy delta:
   - File: `config/layer3/6A/priors/account_per_party_priors_6A.v1.yaml`
   - Add:
     - `constraints.cap_enforcement_mode: hard_global_postmerge`
     - `constraints.max_allowed_kmax_violations: 0`

### 5.3 Delta Set B - `S4` IP prior and linkage realism enforcement (mandatory)
1. File to change: `packages/engine/src/engine/layers/l3/seg_6A/s4_device_graph/runner.py`.
2. Current behavior to replace:
   - Lean mode path ignores richer edge semantics and emits simplified link roles.
   - Missing `region_id` mix currently falls back to first available `ip_type_mix`.
   - Link construction is driven by floor+fractional expansion and can produce sparse coverage with long reuse tails.
3. Required code delta:
   - Remove permissive fallback for missing region mix; fail-closed on `ip_type_mix_missing`.
   - Implement quota-constrained per-region `ip_type` assignment so observed shares track prior targets.
   - Replace unconstrained link expansion with explicit coverage control by device group and bounded reuse control.
   - Add tail clamps with deterministic backoff so `devices_per_ip` stays within target tail envelope.
4. Validation-policy delta:
   - File: `config/layer3/6A/policy/validation_policy_6A.v1.yaml`
   - Change:
     - `linkage_checks.ip_links.max_devices_per_ip: 20000 -> 600`
     - `role_distribution_checks.ip_roles.max_risky_fraction: 0.99 -> 0.25`
   - Add fail-closed realism gates:
     - `distribution_checks.ip_prior_alignment.max_abs_error_pp: 15` (`B`)
     - `distribution_checks.device_ip_coverage.min_fraction: 0.25` (`B`)
     - `distribution_checks.ip_degree_tail.p99_max: 120`
     - `distribution_checks.ip_degree_tail.max_max: 600`

### 5.4 Delta Set C - `S5` risk propagation coupling (mandatory)
1. File to change: `packages/engine/src/engine/layers/l3/seg_6A/s5_fraud_posture/runner.py`.
2. Current behavior to replace:
   - Role assignment is mostly entity-local (hash-based by entity id), so owner-conditioned propagation is weak.
   - Raw-to-runtime role collapsing exists but does not encode strong conditional risk transmission.
3. Required code delta:
   - Add conditional probability layer before final role draw:
     - party-risk -> account-risk uplift
     - party-risk -> device-risk uplift
     - risky-device/high-sharing-IP context -> ip-risk uplift
   - Implement bounded log-odds uplift coefficients with clamp to avoid synthetic over-separability.
4. New policy file:
   - `config/layer3/6A/policy/risk_propagation_coeffs_6A.v1.yaml`
   - Include initial coefficient block tuned for `B`:
     - odds-ratio target for risky account given risky party: `1.6-1.9`
     - odds-ratio target for risky device given risky party: `1.6-1.9`
     - bounded contextual uplift for risky IP from linked risky assets

### 5.5 Delta Set D - role mapping contract (mandatory)
1. Files to change:
   - `config/layer3/6A/taxonomy/fraud_role_taxonomy_6A.v1.yaml`
   - `config/layer3/6A/policy/validation_policy_6A.v1.yaml`
2. Required delta:
   - Introduce explicit `raw_role -> canonical_role_family` mapping table for both device and IP roles.
   - Emit both `raw_role` and `canonical_role_family` in S5 outputs.
   - Add fail-closed mapping checks:
     - `mapping_coverage: 100%`
     - `unmapped_role_rate: 0`
3. Rationale:
   - Converts the current role-vocabulary simplification into an auditable surface; enables policy-vs-observed diagnostics to be meaningful.

### 5.6 Delta Set E - validation hardening (mandatory)
1. File to change: `config/layer3/6A/policy/validation_policy_6A.v1.yaml`.
2. Required delta:
   - Promote critical realism checks to fail-closed:
     - post-merge `K_max` invariants
     - IP prior divergence
     - device->IP linkage coverage
     - IP reuse tail bounds
     - role mapping coverage
   - Keep existing structural checks, but make distribution checks first-class gate criteria.

### 5.7 Phase-2 deltas for `B+` (apply only after Phase-1 pass)
1. `S3` instrument floor refinement:
   - Replace universal floor behavior with account-type-specific floor policy to remove low-lambda inflation artifacts.
2. Country-conditioned modulation:
   - Add bounded country-level deltas around global priors to reduce over-uniform geography.
3. Cross-seed hardening:
   - Require all critical metrics to pass on seeds `{42, 7, 101, 202}` and meet Section 2 CV stability limits.

### 5.8 Chosen spec summary
1. Chosen baseline: `Package A` (Delta Sets A-E) to reach `B`.
2. Chosen extension: Phase-2 deltas to move from `B` toward stable `B+`.
3. No optional deviations are accepted for Phase-1 because each delta closes a current hard blocker identified in Sections 1-3.

## 6) Validation Tests + Thresholds
This section defines the fail-closed validation suite for Segment `6A` after Section 5 fixes are applied. It is the grading gate: if these tests do not pass, `6A` does not qualify for `B`/`B+`.

### 6.1 Validation objective
1. Verify that the chosen fixes in Section 5 close the four material realism gaps:
   - account cap semantics (`K_max`)
   - IP prior/linkage realism
   - owner->asset/network risk propagation
   - role traceability to policy semantics
2. Enforce pass/fail outcomes using explicit thresholds rather than qualitative interpretation.
3. Separate minimum `B` acceptance from tighter `B+` acceptance.

### 6.2 Grade gate logic
1. `B` eligibility:
   - every `B` threshold passes for every required seed.
2. `B+` eligibility:
   - every `B` threshold passes, and every `B+` threshold passes for every required seed.
3. Required seed set:
   - `{42, 7, 101, 202}`
4. Gate policy:
   - any hard-gate failure blocks the corresponding grade.

### 6.3 Test catalog (authoritative)
| Test ID | Metric | Threshold (`B`) | Threshold (`B+`) | Scope | Why it matters |
|---|---|---|---|---|---|
| `T1_KMAX_HARD_INVARIANT` | `max(count_accounts(party_id, account_type) - K_max, 0)` | `= 0` | `= 0` | S2 full output | Proves cap semantics are implemented as hard constraints, not warnings |
| `T2_KMAX_TAIL_SANITY` | per-type `p99_accounts_per_party`, `max_accounts_per_party` vs cap | `p99 <= K_max`, `max <= K_max` | same | S2 full output | Detects hidden tail leakage that can survive partial cap logic |
| `T3_IP_PRIOR_ALIGNMENT` | max absolute error of `pi(ip_type|region)` vs policy target (pp) | `<= 15 pp` | `<= 8 pp` | S4 linked IPs | Directly addresses residential-overdominance and prior drift |
| `T4_DEVICE_IP_COVERAGE` | `linked_devices / total_devices` | `>= 0.25` | `>= 0.35` | S4 | Prevents sparse linkage regime that weakens network realism |
| `T5_IP_REUSE_TAIL_BOUNDS` | `p99(devices_per_ip)`, `max(devices_per_ip)` | `p99 <= 120`, `max <= 600` | `p99 <= 80`, `max <= 350` | S4 | Prevents extreme shared-IP tails from dominating risk signals |
| `T6_ROLE_MAPPING_COVERAGE` | `% mapped runtime roles`, `unmapped_count` | `100%`, `0` | same | S5 role outputs | Restores policy traceability and auditability |
| `T7_RISK_PROPAGATION_EFFECT` | `OR_account`, `OR_device` conditioned on risky party | `>= 1.5` each | `>= 2.0` each | S5 + graph joins | Verifies owner risk actually propagates to asset/network risk |
| `T8_DISTRIBUTION_ALIGNMENT_JSD` | JSD for key distributions (`ip_type`, role families) | `<= 0.08` | `<= 0.05` | S4/S5 | Ensures full-shape alignment, not only point metrics |
| `T9_CROSS_SEED_STABILITY` | CV across seeds on critical metrics | `<= 0.25` | `<= 0.15` | multi-seed aggregate | Protects against seed-luck grading |
| `T10_DOWNSTREAM_COMPAT_6B` | 6B non-regression + realism sensitivity check | must pass | must pass | 6B rerun with remediated 6A | Confirms 6A fixes improve (or at least do not degrade) downstream realism |

### 6.4 Statistical test mechanics
1. For proportion/rate metrics (`T3`, `T4`, `T7`), compute `95%` bootstrap confidence intervals (`>= 1,000` resamples).
2. For propagation odds-ratios (`T7`), require:
   - threshold pass on point estimate
   - lower confidence bound `> 1.0` for directional validity.
3. For JSD checks (`T8`), evaluate both:
   - pooled distribution
   - region-stratified distributions.
4. Sample support rule:
   - if support is insufficient for a metric stratum, mark as `insufficient_evidence` and treat as fail for grade promotion.

### 6.5 Artifact contract (machine-auditable)
1. Per-run detailed artifact:
   - `runs/.../layer3/6A/validation/realism_gate_6A.json`
2. Required fields per test:
   - `test_id`
   - `metric_name`
   - `value`
   - `threshold_B`
   - `threshold_Bplus`
   - `pass_B`
   - `pass_Bplus`
   - `ci_low`
   - `ci_high`
   - `seed`
3. Aggregate decision artifact:
   - `runs/.../layer3/6A/validation/realism_gate_summary_6A.json`
4. Summary must include:
   - `eligible_grade` in `{<C, B, B+}`
   - per-test fail list
   - seed-level stability summary.

### 6.6 Failure triage routing
1. `T1-T2` failures route to `S2` cap enforcement logic.
2. `T3-T5` failures route to `S4` IP prior application and linkage generation controls.
3. `T6-T8` failures route to `S5` role mapping and propagation coefficients.
4. `T9` failures route to robustness retuning (not threshold relaxation by default).
5. `T10` failures route to cross-layer compatibility review before accepting any 6A remediation.

### 6.7 Section-6 acceptance decision
1. Section 5 is considered statistically validated only when `T1-T10` satisfy the `B` gate on all required seeds.
2. `B+` classification is only granted when tighter thresholds also pass with no hard-gate exceptions.
3. Any exception must be explicitly versioned as policy intent and re-baselined, not silently waived.

## 7) Expected Grade Lift (Local + Downstream Impact)
This section estimates expected realism-grade movement after applying Section 5 fixes and validating with Section 6 gates. It is an expected-impact forecast, not a claimed achieved outcome.

### 7.1 Local grade lift forecast for `6A`
1. Current analytical baseline: `B-`.
2. Expected grade after Phase-1 (`Package A`) and full `B`-gate pass (`T1-T10` at `B` thresholds): `B`.
3. Expected grade after Phase-2 enhancements and full `B+`-gate pass: `B+`.
4. Interpretation:
   - Phase-1 closes the current hard realism blockers.
   - Phase-2 improves heterogeneity realism and seed robustness for a credible `B+` posture.

### 7.2 Metric-by-metric lift expectation (local `6A`)
1. `K_max` realism (largest hard-correctness gain):
   - Current: widespread and large cap breaches by account type.
   - Expected post-fix: zero post-merge breaches (`T1`) and tail compliance (`T2`).
   - Grade contribution: removes a direct blocker to `B`.
2. IP realism and linkage:
   - Current: severe residential skew, sparse device->IP coverage, and extreme IP sharing tail.
   - Expected post-fix: bounded share error (`T3`), higher linkage coverage (`T4`), controlled tail (`T5`).
   - Grade contribution: major realism gain on the weakest axis.
3. Risk propagation realism:
   - Current: weak owner->asset/network coupling.
   - Expected post-fix: propagation odds-ratio floors met (`T7`) with directional confidence.
   - Grade contribution: materially improves causal explainability.
4. Traceability and auditability:
   - Current: role simplification without complete policy-to-runtime mapping.
   - Expected post-fix: full mapping coverage and zero unmapped roles (`T6`).
   - Grade contribution: converts ambiguous realism claims into auditable evidence.
5. Distribution-shape quality:
   - Current: some surfaces appear plausible but not close to intended policy shape.
   - Expected post-fix: JSD thresholds met (`T8`) in pooled and stratified views.
   - Grade contribution: prevents passing by point metrics alone.
6. Stability:
   - Current: insufficient robustness assurance.
   - Expected post-fix: cross-seed CV within gate limits (`T9`).
   - Grade contribution: ensures grade is durable, not seed-dependent luck.

### 7.3 Downstream impact forecast on `6B`
1. Why 6A matters to 6B:
   - `6A` defines the identity and network substrate used by 6B; weak 6A realism propagates into weak or shortcut-driven 6B signals.
2. Expected effect of 6A remediation alone:
   - Conservative `6B` lift: `D+ -> C`.
   - If 6B segment-internal remediation is executed in parallel: `D+ -> C+` or `B-`.
3. Why 6A fix alone is not enough for `6B` to reach `B/B+`:
   - 6B retains segment-local weaknesses (for example amount/event mechanics, label/decision dynamics, campaign-expression realism) that must be corrected within 6B itself.
4. Required downstream confirmation:
   - `T10` must show no structural regressions and measurable realism improvement in 6B-facing diagnostics after 6A changes.

### 7.4 Confidence profile and major risks
1. Confidence in achieving local `6A -> B`: High, if `T1-T6` pass on all required seeds.
2. Confidence in achieving local `6A -> B+`: Medium, because Phase-2 introduces calibration complexity and possible over-tuning.
3. Confidence in downstream `6B` lift from 6A alone: Medium (helpful but not sufficient).
4. Main risk to monitor:
   - Over-coupled propagation may make fraud separability unrealistically easy.
5. Risk controls:
   - Use `T7` effect-size thresholds, `T8` shape checks, and `T9` cross-seed stability as hard guardrails against over-correction.

### 7.5 Acceptance statement for this forecast
1. Section 5 should be considered successful for `B` only when:
   - all `B` gates in Section 6 pass on every required seed, and
   - `T10` confirms no downstream regression in 6B.
2. `B+` should be claimed only when:
   - Phase-2 deltas are applied,
   - tighter `B+` thresholds pass on all seeds,
   - and stability metrics remain within `B+` limits.
3. Until those conditions are met, Section 7 remains a forecasted lift, not an achieved grade.
