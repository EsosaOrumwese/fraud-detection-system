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

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

## 6) Validation Tests + Thresholds

## 7) Expected Grade Lift (Local + Downstream Impact)
