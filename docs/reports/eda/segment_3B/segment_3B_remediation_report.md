# Segment 3B Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 3B toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness
This section records the measured weaknesses from `segment_3B_published_report.md` that block a `B/B+` realism claim for Segment 3B.

### 1.1 Critical realism failure: edge catalogue is behaviorally flat
The primary realism surface in 3B (`S2 edge_catalogue_3B`) is statistically collapsed:
1. Every merchant has exactly `500` edges (`min = p50 = p90 = p99 = max = 500`).
2. Every merchant has exactly `117` countries represented (`min = p50 = p90 = p99 = max = 117`).
3. `edge_weight` has one unique value, `0.002 (= 1/500)`.
4. Concentration metrics are constant across merchants:
   - top-1 share `= 0.002`
   - HHI `= 0.002`
   - entropy `= 6.2146` (approximately `ln(500)`, i.e. maximal uniformity)
5. Merchant-country allocation is identical for all merchants (zero cross-merchant variance per country).

Why this is a blocker:
1. Merchant-level heterogeneity is absent, so routing behavior is effectively cloned across the virtual merchant population.
2. The segment can be structurally correct but still fail realism because its core distributional surface has no behavioral diversity.

### 1.2 High-severity coherence failure: settlement anchors do not shape edge geography
Cross-layer settlement-to-edge coherence is weak:
1. Edge-to-settlement distances are very large:
   - median distance approximately `7,929 km`
   - p90 distance approximately `13,874 km`
2. Settlement-country overlap is near baseline:
   - global baseline around `0.51%`
   - most settlement countries near zero overlap
   - only small uplift in a few cases (for example US around `~5%`)

Why this is high severity:
1. Legal settlement anchors exist, but operational geography is not meaningfully pulled toward them.
2. The virtual footprint reads as globally randomized rather than jurisdiction-anchored.

### 1.3 High-severity explainability weakness: virtual classification is opaque despite plausible rate
Classification rate is plausible, but evidence richness is weak:
1. Virtual share is `309 / 10,000 = 3.09%` (plausible in isolation).
2. Decision evidence is unnaturally uniform:
   - `decision_reason = RULE_MATCH` for all rows
   - single `classification_digest` across all merchants
   - `rule_id` and `rule_version` are empty
3. Visual and tabular slices indicate one dominant MCC/channel gate pattern rather than layered policy effects.

Why this matters:
1. The system can say who is virtual, but cannot credibly explain why at policy-slice level.
2. This limits auditability and weakens synthetic realism defensibility.

### 1.4 Medium-high settlement diversity weakness: anchor clustering in micro-hub geographies
Settlement anchors are plausible but concentrated:
1. `309` virtual merchants map to `260` unique settlement coordinates.
2. Shared-coordinate exposure is high enough to be material:
   - `83` merchants (`26.9%`) are on reused coordinates
   - duplicate excess `= 49` (about `15.9%` of virtual merchants)
3. Top settlement tzids are concentrated in a small hub set (for example Monaco, Luxembourg, Zurich, Dublin, Bermuda, Macau).

Why this matters:
1. The issue is not catastrophic coordinate collapse; it is concentration in a narrow legal-anchor set.
2. That concentration can produce an artificial offshore-hub signature.

### 1.5 Medium realism limitation: alias layer is faithful but cannot add diversity
`S3` alias outputs pass integrity, but preserve the flat upstream distribution:
1. `edge_catalogue_index` and `edge_alias_index` counts match catalogue counts.
2. `alias_table_length` is constant (`500`) for all merchants.
3. Decoded alias probabilities match edge weights (high fidelity).

Why this is still a weakness:
1. Correctness is high, but realism does not improve because alias sampling inherits uniform weights.
2. Segment behavior remains homogeneous even with technically correct alias packaging.

### 1.6 Medium governance weakness: validation contract coverage is narrow
`S4 virtual_validation_contract_3B` is minimal:
1. Only two blocking checks are present (`IP_COUNTRY_MIX`, `SETTLEMENT_CUTOFF`).
2. No direct guardrails for edge heterogeneity collapse (edge-count variance, weight-shape variance, merchant-profile divergence, settlement-overlap corridors).

Why this matters:
1. Major realism defects can remain undetected while structural checks pass.
2. The validation surface is insufficient for a `B/B+` realism claim.

### 1.7 Segment-level weakness summary
1. 3B is structurally reproducible, but its primary realism surface is distributionally underpowered.
2. The dominant failure mode is not schema integrity; it is lack of heterogeneity and weak cross-layer geographic coherence.
3. This aligns with the analytical report conclusion that current 3B posture is in the `D` (borderline `D+`) band.

## 2) Expected Statistical Posture (B/B+)
This section defines the target statistical posture for Segment 3B at two acceptance bands:
1. `B` = minimum credible synthetic realism for virtual-overlay behavior.
2. `B+` = stronger realism with tighter heterogeneity, coherence, and stability.

### 2.1 Non-negotiable `B` gates (hard fail)
If any gate below fails, Segment 3B cannot be graded `B` regardless of improvements elsewhere.

1. **Edge heterogeneity must exist at merchant level.**
   - `stddev(edges_per_merchant) > 0`
   - `stddev(countries_per_merchant) > 0`
   - `stddev(top1_country_share_per_merchant) > 0`

2. **Classification must be explainable, not opaque.**
   - `% rows with non-null rule_id >= 99%`
   - `% rows with non-null rule_version >= 99%`
   - At least `3` distinct `rule_id` values are active in virtual classification under baseline scenario.

3. **Settlement must have measurable operational influence.**
   - Median settlement-country overlap per merchant `>= 0.03`
   - Median edge-distance-to-settlement `<= 6,000 km`

4. **Validation contract must cover realism, not only integrity.**
   - Contract contains explicit blocking checks for:
     - edge heterogeneity
     - settlement coherence
     - classification explainability
     - alias fidelity

### 2.2 `B` vs `B+` expected posture by realism axis
| Realism axis | `B` target posture | `B+` target posture |
|---|---|---|
| Virtual prevalence | Within policy band (example: `2%-8%` unless versioned policy states otherwise) | Within tighter policy band and seed-stable |
| Classification explainability | `>=3` active `rule_id`; null `rule_id` and `rule_version` each `<=1%` | `>=5` active `rule_id`; nulls each `<=0.2%`; rule-mix stable by seed |
| Settlement coordinate diversity | unique coordinates / virtual merchants `>=0.88`; duplicate exposure `<=20%` | unique ratio `>=0.93`; duplicate exposure `<=10%` |
| Settlement tzid concentration | top-1 settlement tzid share `<=0.25` | top-1 share `<=0.18` |
| Edge-count heterogeneity | `CV(edges_per_merchant) >=0.25` | `CV(edges_per_merchant) >=0.40` |
| Country-footprint heterogeneity | `CV(countries_per_merchant) >=0.20` | `CV(countries_per_merchant) >=0.35` |
| Weight-shape realism | merchant top-1 edge-weight share p50 in `[0.03, 0.20]`; no equal-weight collapse | p50 in `[0.05, 0.30]` with wider merchant spread |
| Merchant-profile separation | median pairwise JS divergence of merchant country vectors `>=0.05` | `>=0.10` |
| Settlement-edge coherence | median overlap `>=0.03`, p75 overlap `>=0.06`, median distance `<=6,000 km` | median overlap `>=0.07`, p75 overlap `>=0.12`, median distance `<=4,500 km` |
| Alias fidelity | max abs(`alias_prob - edge_weight`) `<=1e-6` | `<=1e-9` |
| Validation coverage | `>=8` realism checks across S1/S2/S3/S4 | `>=12` checks with per-country and per-profile slices |

### 2.3 Cross-seed stability requirements
These are required for any `B/B+` realism claim:
1. Evaluate at seeds `{42, 7, 101, 202}`.
2. All hard-gate metrics pass on all seeds.
3. Cross-seed CV for primary metrics (virtual rate, settlement-overlap median, top-1 share median, profile-divergence median):
   - `<=0.25` for `B`
   - `<=0.15` for `B+`
4. No critical realism check may pass by exception, manual override, or WARN-only downgrade.

### 2.4 Interpretation of the target posture
1. This target does not require real-world CDN fidelity; it requires non-degenerate, policy-shaped synthetic behavior.
2. For 3B, `B/B+` means:
   - structural integrity remains strong,
   - merchant-level variability is statistically visible,
   - settlement anchors exert measurable influence on edge geography,
   - alias remains faithful while encoding non-flat distributions,
   - realism checks are enforceable at gate time.

## 3) Root-Cause Trace
This section traces each observed weakness to concrete policy, code-path, and data-flow causes.  
Goal: establish causal accountability before proposing fixes, so Section 4 can focus on interventions that change distributional behavior rather than surface symptoms.

### 3.1 Root-cause mapping matrix
| Weakness (Section 1) | Immediate cause | Deeper cause | Primary evidence | Statistical effect |
|---|---|---|---|---|
| 1.1 Edge catalogue is behaviorally flat | `edge_scale` is fixed and reused for all merchants; weights are forced to `1/edge_scale` | S2 policy is modeled as one global allocation template instead of merchant-conditioned sampling | `packages/engine/src/engine/layers/l1/seg_3B/s2_edge_catalogue/runner.py`; `config/layer1/3B/virtual/cdn_country_weights.yaml` | `edges_per_merchant`, `countries_per_merchant`, top-1 share, HHI, entropy collapse to near constants |
| 1.2 Settlement anchors do not shape edge geography | Settlement assignment and edge allocation are decoupled | No settlement-conditioned modulation layer between S1 settlement and S2 country edge construction | `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`; S2 runner path above | High median settlement distance, low overlap uplift vs baseline |
| 1.3 Classification explainability is opaque | Decision reason is coarse and lineage fields are null | Rule metadata model lacks durable identity/version capture at emit time | `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`; `config/layer1/3B/virtual/mcc_channel_rules.yaml` | Plausible rate but weak auditability and low policy-trace richness |
| 1.4 Settlement diversity is concentrated | Settlement coordinate universe is narrow for active virtual cohort | Policy prioritizes a compact hub set without anti-concentration controls | S1 outputs in analytical report; settlement assignments derived from static tables | Reused anchors, hub-heavy tzid mix, synthetic offshore signature risk |
| 1.5 Alias layer preserves flatness | Alias index faithfully mirrors S2 probabilities | Alias step is a codec, not a diversity generator | S3 alias outputs and integrity checks in analytical report | High correctness but no realism lift because upstream distribution is degenerate |
| 1.6 Validation contract is narrow | Only two blocking checks in S4 contract | Contract designed for integrity-only gating, not realism control | `packages/engine/src/engine/layers/l1/seg_3B/s4_virtual_contracts/runner.py`; `config/layer1/3B/virtual/virtual_validation.yml` | Segment can pass contract while failing heterogeneity/coherence targets |

### 3.2 Detailed trace: S2 fixed-edge topology drives the largest realism loss
1. `edge_scale` is pulled once from policy (`500`) and applied globally.
2. Country weights are allocated once from the static global vector and reused across merchants.
3. Per-edge weight is deterministic (`1.0 / edge_scale`), which locks `edge_weight=0.002` for all rows.
4. Because count and weights are both fixed, any derived concentration metric is mathematically constrained:
   - top-1 share converges to `1/500`,
   - HHI converges to uniform-weight baseline,
   - entropy converges to `ln(500)`.
5. Result: the strongest realism surfaces in S2 lose merchant-level variance almost entirely.

### 3.3 Detailed trace: settlement coherence fails due to separation of concerns
1. S1 decides virtual status and binds settlement anchors.
2. S2 constructs edge geography from global country priors that do not consume settlement-country proximity as a control signal.
3. Without a coupling term, settlement-country overlap is incidental, not policy-enforced.
4. This creates the observed pattern:
   - low overlap for most settlement countries,
   - only small uplift for a handful of large countries,
   - high edge-to-settlement distance quantiles.
5. Interpretation: legality anchor exists as metadata, but does not materially influence operational geography.

### 3.4 Detailed trace: explainability failure is representational, not rate-based
1. Virtual prevalence is plausible, so the issue is not gross over/under classification rate.
2. Emitted classification evidence is compressed:
   - one coarse `decision_reason`,
   - null `rule_id` and `rule_version`,
   - shared digest-level signature.
3. This prevents reconstruction of policy pathway at row level.
4. Statistical impact is indirect but critical: downstream analysts cannot attribute distributional artifacts to specific rules, which blocks controlled tuning.

### 3.5 Detailed trace: settlement concentration is policy-shaped and unchecked
1. Virtual merchants map to a limited coordinate/tzid hub set.
2. Duplicate coordinate reuse is substantial but not extreme, which indicates controlled concentration rather than accidental collapse.
3. No guardrail enforces top-hub share limits or minimum unique-coordinate ratio.
4. Outcome: repeated hub signatures that look synthetic when combined with flat S2 edges.

### 3.6 Detailed trace: alias layer is correct and therefore propagates upstream weakness
1. S3 alias artifacts pass parity and decode-fidelity checks.
2. Alias tables are fixed length and reconstruct the same probabilities accurately.
3. This confirms an important causal point:
   - S3 is not introducing the weakness,
   - S3 is preserving a weak upstream distribution by design.
4. Therefore remediation must target S1/S2 policy+generation logic, not alias codec mechanics.

### 3.7 Detailed trace: contract undercoverage allows realism defects to pass
1. S4 checks focus on limited business rules (`IP_COUNTRY_MIX`, `SETTLEMENT_CUTOFF`).
2. Missing checks include:
   - edge-count variance,
   - country-footprint variance,
   - merchant-profile divergence,
   - settlement-overlap corridor checks,
   - explainability lineage completeness.
3. Because these are absent, the segment can be technically green while statistically unrealistic.
4. This is a governance gap, not only a data-generation gap.

### 3.8 Upstream dependency caveat
1. Some 3B limits are inherited from upstream geography/timezone sparsity.
2. However, current evidence shows the dominant 3B failures are local:
   - fixed edge cardinality and weight mechanics,
   - weak settlement coupling,
   - shallow validation coverage.
3. Upstream tuning can improve headroom, but 3B cannot reach `B/B+` without local policy/code changes.

### 3.9 Root-cause conclusion
Segment 3B’s realism deficit is caused by a deterministic global-template architecture in S2, weak settlement coupling from S1 to S2, low explainability fidelity in S1 emissions, and narrow S4 realism governance. The failure is primarily causal-design and policy-shape related, not schema integrity related. This causal map is sufficient to move into ranked remediation options in Section 4.

## 4) Remediation Options (Ranked + Tradeoffs)
This section presents ranked remediation options derived from Section 3 causal evidence.  
Ranking is based on expected realism lift per unit implementation effort, while preserving deterministic reproducibility and auditability.

### 4.1 Ranked options matrix
| Rank | Option | What it changes | Weaknesses addressed | Expected realism lift | Tradeoffs / risks |
|---|---|---|---|---|---|
| 1 | S2 profile-conditioned edge generator | Replaces global fixed edge template with merchant-conditioned edge count and weight-shape generation | 1.1, 1.5 | Very high | More policy parameters; requires strict seeded reproducibility controls |
| 2 | Settlement-coupled country weighting | Introduces settlement-proximity and jurisdiction affinity terms into S2 allocation | 1.2, 1.4 | High | Over-coupling risk if proximity term is too strong |
| 3 | Classification lineage enrichment in S1 | Emits non-null `rule_id`, `rule_version`, and richer reason taxonomy | 1.3 | High (audit realism) | Requires rule-schema/version governance |
| 4 | S4 realism contract expansion | Adds blocking checks for heterogeneity, coherence, explainability, and divergence | 1.6 and prevents regression on 1.1-1.5 | High (governance and stability) | More initial gate failures while tuning |
| 5 | Settlement anti-concentration controls | Caps hub share and enforces minimum unique-anchor ratio | 1.4 | Medium to high | Can conflict with legal-hub realism if too strict |
| 6 | Merchant-profile divergence targets | Adds explicit targets for top-1 share spread and inter-merchant JS divergence | 1.1, 1.5 | Medium | Risk of metric overfitting without causal grounding |
| 7 | Upstream diversity assist (2A/2B tuning) | Broadens upstream geo/timezone diversity envelope feeding 3B | 1.2, 1.4 (partial) | Medium (enabling) | Cross-segment coordination and slower payoff |

### 4.2 Option detail and rationale
#### 4.2.1 Option 1: S2 profile-conditioned edge generator (top priority)
1. Replace global `edge_scale=500` with merchant-level `edge_scale_m` drawn from a seeded policy distribution.
2. Build merchant-specific country logits from:
   - global base prior,
   - merchant profile terms (class/size/region),
   - optional weak random effects (seeded, bounded).
3. Allocate edges from each merchant-specific distribution and allow non-uniform weights.
4. Why this is rank 1:
   - Directly resolves the largest statistical collapse (flat cardinality and equal weights),
   - Automatically increases S3 alias realism because alias faithfully mirrors S2.
5. Main risk:
   - If unconstrained, tails can become unstable and hurt cross-seed consistency.

#### 4.2.2 Option 2: Settlement-coupled country weighting
1. Add a settlement-conditioned term to country allocation in S2:
   - distance/proximity kernel,
   - same-jurisdiction affinity boost,
   - bounded blend coefficient against global prior.
2. Enforce floors and caps to avoid near-monoculture routing.
3. Why this is rank 2:
   - It directly addresses high settlement distance and weak overlap uplift, which are current coherence failures.
4. Main risk:
   - Overweighting settlement can create unrealistic local lock-in.

#### 4.2.3 Option 3: Classification lineage enrichment
1. Emit `rule_id`, `rule_version`, and structured decision-reason subclasses for every classified row.
2. Ensure multiple active rules are represented in baseline.
3. Add lineage completeness checks upstream of S4 packaging.
4. Why this is rank 3:
   - Strong audit and explainability lift with low distributional disturbance.
5. Main risk:
   - Requires durable rule identity/version discipline in policy assets.

#### 4.2.4 Option 4: S4 realism contract expansion
1. Extend contract from integrity-only checks to realism checks with blocking thresholds:
   - `CV(edges_per_merchant)`,
   - `CV(countries_per_merchant)`,
   - merchant-profile divergence floor,
   - settlement-overlap corridor,
   - explainability completeness.
2. Add per-profile and per-country slices to prevent aggregate-only masking.
3. Why this is rank 4:
   - Prevents "green but unrealistic" recurrence.
4. Main risk:
   - Early tuning cycles may fail frequently until policy is calibrated.

#### 4.2.5 Option 5: Settlement anti-concentration controls
1. Add policy limits for:
   - top-1 settlement tzid share,
   - minimum unique settlement-coordinate ratio,
   - maximum duplicate-anchor exposure.
2. Keep a controlled allowance for legal hub concentration.
3. Why this is rank 5:
   - Addresses medium-high concentration weakness not fully solved by settlement coupling alone.
4. Main risk:
   - Over-tight caps can erase intended legal-hub patterning.

#### 4.2.6 Option 6: Merchant-profile divergence targets
1. Introduce explicit spread targets for:
   - top-1 share distribution,
   - HHI/entropy distribution,
   - pairwise JS divergence across merchant country vectors.
2. Use these as tuning objectives, not hard-coded direct outputs.
3. Why this is rank 6:
   - Critical for B+ quality after core degeneracy is removed.
4. Main risk:
   - Overfitting to diagnostics if not tied back to policy semantics.

#### 4.2.7 Option 7: Upstream diversity assist
1. Increase upstream spatial/timezone diversity where 3B inherits narrow envelopes.
2. Treat as a support lever, not a substitute for local 3B fixes.
3. Why this is rank 7:
   - Helpful for headroom, but does not fix 3B local root causes.
4. Main risk:
   - Higher coordination overhead and longer delivery time.

### 4.3 Recommended option stack for 3B
#### 4.3.1 Core stack (required for `B`)
1. Option 1 (`S2 profile-conditioned generator`)
2. Option 2 (`Settlement-coupled weighting`)
3. Option 3 (`S1 lineage enrichment`)
4. Option 4 (`S4 realism contract expansion`)

#### 4.3.2 Enhancement stack (targeting `B+`)
1. Option 5 (`Settlement anti-concentration controls`) if hub concentration remains above target after core stack.
2. Option 6 (`Profile divergence targets`) for final calibration and spread shaping.
3. Option 7 (`Upstream assist`) where residual limits are confirmed upstream-bound.

### 4.4 Why this ranking is statistically coherent
1. The top-ranked options directly reverse the strongest measured degeneracies (flat edge topology and weak settlement coupling).
2. Mid-ranked options improve auditability and guardrails, which are required for reproducible realism claims.
3. Lower-ranked options are calibration and dependency levers, valuable but not sufficient without the core stack.

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)
This section selects the concrete implementation package for 3B and defines exact policy/code delta points to execute in a subsequent remediation wave.

### 5.1 Chosen package
Chosen package for baseline remediation (`B` target):
1. `CF-3B-01` S2 merchant-conditioned edge topology generator.
2. `CF-3B-02` S2 settlement-coupled country weighting.
3. `CF-3B-03` S1 classification lineage enrichment.
4. `CF-3B-04` S4 realism contract expansion.

Conditional add-on for concentration cleanup:
1. `CF-3B-05` settlement anti-concentration guardrails (only if post-core metrics still fail concentration bands).

Calibration add-on for `B+`:
1. `CF-3B-06` merchant-profile divergence calibration pack.

### 5.2 Exact policy deltas
#### 5.2.1 File: `config/layer1/3B/virtual/cdn_country_weights.yaml`
Current weakness-driving posture:
1. single global `edge_scale` value,
2. globally shared country weights reused for every merchant,
3. implicit equal edge weights.

Replace with profile-conditioned topology block:
```yaml
edge_topology:
  edge_scale_distribution:
    family: lognormal_trunc
    params:
      median: 500
      sigma: 0.45
      min: 160
      max: 1200
    seed_namespace: "3B_S2_edge_scale"

  merchant_profile_terms:
    by_virtual_class:
      OFFSHORE_HUB: {edge_scale_mult: 1.25, concentration_bias: 0.30}
      HYBRID_FOOTPRINT: {edge_scale_mult: 1.00, concentration_bias: 0.00}
      REGIONAL_COMPACT: {edge_scale_mult: 0.72, concentration_bias: -0.18}
    by_size_bucket:
      SMALL:  {edge_scale_mult: 0.85}
      MEDIUM: {edge_scale_mult: 1.00}
      LARGE:  {edge_scale_mult: 1.20}

  weight_shape:
    family: dirichlet
    concentration_alpha_distribution:
      family: lognormal_trunc
      params: {median: 2.4, sigma: 0.55, min: 0.6, max: 8.0}
    min_country_mass: 1.0e-5
    sparse_tail_floor: 0.0015
```

Add settlement coupling block:
```yaml
settlement_coupling:
  enabled: true
  blend_lambda: 0.38
  proximity_kernel:
    family: exp_distance
    tau_km: 2400
    min_boost: 1.00
    max_boost: 2.10
  same_country_boost: 1.65
  same_region_boost: 1.20
  max_single_country_share: 0.42
  min_effective_country_count: 8
```

Interpretation:
1. `edge_scale` becomes merchant-specific while keeping global median continuity.
2. country weights can vary by profile and settlement geometry.
3. hard caps/floors prevent unstable monoculture or hyper-diffuse tails.

#### 5.2.2 File: `config/layer1/3B/virtual/mcc_channel_rules.yaml`
Enforce row-level lineage fields on each rule object:
```yaml
- rule_id: "VRULE_MCC5411_ECOM_V3"
  rule_version: "3.0.0"
  mcc: "5411"
  channel: "ECOM"
  decision: "VIRTUAL_TRUE"
  reason_code: "MCC_CHANNEL_POLICY_MATCH"
  priority: 30
```

Schema requirements:
1. `rule_id` non-empty string.
2. `rule_version` semver string.
3. `reason_code` from controlled vocabulary.

#### 5.2.3 File: `config/layer1/3B/virtual/virtual_validation.yml`
Expand realism checks to blocking gates:
```yaml
realism_checks:
  edge_count_cv_min: 0.25
  country_count_cv_min: 0.20
  top1_share_p50_min: 0.03
  top1_share_p50_max: 0.20
  js_divergence_median_min: 0.05
  settlement_overlap_median_min: 0.03
  settlement_overlap_p75_min: 0.06
  settlement_distance_median_max_km: 6000
  rule_id_non_null_rate_min: 0.99
  rule_version_non_null_rate_min: 0.99
  active_rule_id_count_min: 3
```

### 5.3 Exact code deltas
#### 5.3.1 File: `packages/engine/src/engine/layers/l1/seg_3B/s2_edge_catalogue/runner.py`
Required changes:
1. Replace single global `edge_scale` usage with per-merchant `edge_scale_m`.
2. Construct merchant country logits as:
   - base prior term,
   - merchant profile term,
   - settlement coupling term,
   - bounded seeded perturbation term.
3. Normalize logits to merchant-specific country probabilities.
4. Allocate `edges_per_country_m` from merchant-specific probabilities and `edge_scale_m`.
5. Compute non-uniform `edge_weight` from merchant allocation output.
6. Enforce constraints:
   - `max_country_share <= policy.max_single_country_share`,
   - `effective_country_count >= policy.min_effective_country_count`.
7. Emit diagnostics fields for S4 checks:
   - `edge_scale_m`,
   - `merchant_top1_share`,
   - `merchant_hhi`,
   - `merchant_entropy`,
   - `merchant_effective_country_count`.

#### 5.3.2 File: `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`
Required changes:
1. Populate `rule_id` and `rule_version` on every matched rule outcome.
2. Replace single coarse `decision_reason` with controlled subclasses (for example primary/secondary/fallback matches).
3. Preserve deterministic tie-break ordering while exposing selected rule identity.
4. Emit lineage completeness counters for contract checks.

#### 5.3.3 File: `packages/engine/src/engine/layers/l1/seg_3B/s4_virtual_contracts/runner.py`
Required changes:
1. Extend contract payload with realism-check block.
2. Evaluate realism metrics and thresholds as fail-closed for hard gates.
3. Persist measured value + threshold + status per check for audit.

### 5.4 Determinism and reproducibility controls
To avoid non-reproducible realism drift:
1. Use explicit seed namespaces:
   - `3B_S2_edge_scale`,
   - `3B_S2_profile_noise`,
   - `3B_S2_country_alloc`.
2. Hash-stable merchant keying for per-merchant draws.
3. No wall-clock entropy in any draw path.
4. Evaluate fixed seeds `{42, 7, 101, 202}` for acceptance.

### 5.5 Backward-compatibility constraints
1. Preserve existing output schema columns consumed downstream.
2. New columns must be additive.
3. Alias interfaces remain structurally compatible even as internal probabilities gain diversity.
4. Bundle version must be incremented to isolate remediation behavior from prior deterministic bundle.

### 5.6 Execution order inside 3B
1. Land `CF-3B-03` first (lineage enrichment) for immediate audit gain and low risk.
2. Land `CF-3B-01` and `CF-3B-02` together because they are statistically coupled.
3. Land `CF-3B-04` in observe mode for one dry run, then enforce blocking mode.
4. Enable `CF-3B-05` only if concentration metrics remain outside target corridor.
5. Apply `CF-3B-06` during B+ calibration after core B gates are stable.

### 5.7 Expected first-order movement after chosen fix package
Predicted direction after first calibrated pass:
1. `CV(edges_per_merchant)`: `0` to `>= 0.25`.
2. `CV(countries_per_merchant)`: `0` to `>= 0.20`.
3. settlement overlap median: uplift toward `>= 0.03`.
4. settlement distance median: reduction toward `<= 6000 km`.
5. `rule_id` and `rule_version` completeness: from near-null to `>= 99%`.
6. active rule diversity: from effectively one pathway to `>= 3` pathways.

## 6) Validation Tests + Thresholds
This section defines the validation protocol that proves Section 5 remediation changed statistical behavior in the intended direction and at stable quality.

### 6.1 Validation intent
Validation is split into three layers:
1. `Hard gates (B floor)` that must pass to claim minimum credible realism.
2. `Stretch gates (B+ target)` that must pass to claim stronger realism.
3. `Cross-seed stability gates` that prevent one-seed false confidence.

### 6.2 Execution protocol
1. Run baseline scenario with seeds `{42, 7, 101, 202}`.
2. Compute scalar metrics on full merchant population where feasible.
3. For expensive pairwise metrics (for example JS divergence), use deterministic hash-sample during tuning and confirm once on a full pass for signoff.
4. Compute metrics only from emitted S1/S2/S3/S4 artifacts.
5. Persist per-seed metric bundles and one cross-seed summary bundle.

### 6.3 Hard-gate matrix (`B` minimum)
| Test ID | Surface | Metric | `B` Threshold | Why it matters | Fail action |
|---|---|---|---|---|---|
| `3B-V01` | S2 heterogeneity | `CV(edges_per_merchant)` | `>= 0.25` | Detects fixed-edge collapse | Block |
| `3B-V02` | S2 heterogeneity | `CV(countries_per_merchant)` | `>= 0.20` | Detects fixed-country-footprint collapse | Block |
| `3B-V03` | S2 weight shape | `p50(top1_share)` | in `[0.03, 0.20]` | Avoids equal-weight degeneracy and over-concentration | Block |
| `3B-V04` | S2 profile spread | median pairwise JS divergence | `>= 0.05` | Ensures merchants are not cloned | Block |
| `3B-V05` | S1-S2 coherence | median settlement-country overlap | `>= 0.03` | Settlement must influence routing | Block |
| `3B-V06` | S1-S2 coherence | p75 settlement-country overlap | `>= 0.06` | Prevents aggregate masking | Block |
| `3B-V07` | S1-S2 coherence | median edge-to-settlement distance | `<= 6000 km` | Reduces global-random footprint behavior | Block |
| `3B-V08` | S1 explainability | `% non-null rule_id` | `>= 99%` | Policy traceability | Block |
| `3B-V09` | S1 explainability | `% non-null rule_version` | `>= 99%` | Versioned reproducibility | Block |
| `3B-V10` | S1 explainability | active `rule_id` count | `>= 3` | Avoids single-rule opacity | Block |
| `3B-V11` | S3 alias fidelity | `max abs(alias_prob - edge_weight)` | `<= 1e-6` | Ensures alias is faithful encoder | Block |
| `3B-V12` | S4 governance | realism-check block active + enforced | required checks present | Prevents "green but unrealistic" runs | Block |

### 6.4 Stretch matrix (`B+` target)
| Test ID | Metric | `B+` Threshold |
|---|---|---|
| `3B-S01` | `CV(edges_per_merchant)` | `>= 0.40` |
| `3B-S02` | `CV(countries_per_merchant)` | `>= 0.35` |
| `3B-S03` | `p50(top1_share)` | in `[0.05, 0.30]` with wider spread than B floor |
| `3B-S04` | median pairwise JS divergence | `>= 0.10` |
| `3B-S05` | median settlement overlap | `>= 0.07` |
| `3B-S06` | p75 settlement overlap | `>= 0.12` |
| `3B-S07` | median settlement distance | `<= 4500 km` |
| `3B-S08` | `% non-null rule_id` and `% non-null rule_version` | `>= 99.8%` |
| `3B-S09` | active `rule_id` count | `>= 5` |
| `3B-S10` | top-1 settlement tzid share | `<= 0.18` |

### 6.5 Cross-seed stability gates
| Test ID | Metric family | Threshold |
|---|---|---|
| `3B-X01` | Cross-seed CV of key medians (`top1_share`, overlap, distance, JS) | `<= 0.25` for `B`, `<= 0.15` for `B+` |
| `3B-X02` | Virtual prevalence | within policy band on all seeds |
| `3B-X03` | Hard-gate consistency | no hard-gate failures on any seed |

Interpretation:
1. One successful seed is insufficient.
2. Realism claim is accepted only when the metric envelope is stable under seed perturbation.

### 6.6 Statistical diagnostic add-ons (confidence layer)
1. Two-sample KS diagnostic for `top1_share` distribution across seeds (monitor drift shape).
2. Bootstrap CI for median settlement overlap; lower 95% bound must stay above threshold for confidence.
3. Coupling-effect check: settlement-coupled run should show directional uplift vs uncoupled baseline on overlap and distance.

These diagnostics support interpretation but do not replace hard thresholds.

### 6.7 Acceptance logic
1. `B pass`: all hard gates + stability gates pass.
2. `B+ pass`: all hard gates + stretch gates + tighter stability pass.
3. Any hard-gate fail means no `B` claim.
4. Partial wins (for example coherence pass but heterogeneity fail) are still fail.

### 6.8 Required artifacts per validation cycle
1. `3B_validation_metrics_seed_<seed>.json` with measured values, thresholds, statuses.
2. `3B_validation_cross_seed_summary.json` with pass matrix and CV summary.
3. `3B_validation_failure_trace.md` when any check fails, including likely fault domain (`policy`, `code`, `upstream`).

### 6.9 Sufficiency statement
Section 6 is sufficient for decisioning because it maps directly to:
1. Section 3 root causes (heterogeneity, settlement coupling, explainability, governance).
2. Section 5 chosen fixes (S1/S2/S4 delta package).
3. Segment-grade claims (`B` versus `B+`) with explicit numeric boundaries.

## 7) Expected Grade Lift (Local + Downstream Impact)
This section converts remediation into expected grade movement, both locally for Segment 3B and downstream across dependent segments.

### 7.1 Local grade-lift forecast for 3B
| Scenario | Change package | Expected grade band | Rationale |
|---|---|---|---|
| Current baseline | none | `D` (borderline `D+`) | Flat S2 topology, weak settlement coupling, low explainability lineage, narrow S4 checks |
| Core remediation | `CF-3B-01 + CF-3B-02 + CF-3B-03 + CF-3B-04` | `B-` to `B` | Restores heterogeneity, settlement coherence, policy traceability, and fail-closed realism governance |
| Core + concentration guardrail | core + `CF-3B-05` | `B` (stronger) | Reduces residual hub-cluster signature if still above corridor after core package |
| Full calibration path | core + `CF-3B-05 + CF-3B-06` (plus upstream assist only if needed) | `B` to `B+` | Adds distribution-shape calibration and tighter stability posture |

### 7.2 Metric-level expected movement
| Metric | Current posture | Expected after core package (`B`) | Expected after full package (`B+`) |
|---|---|---|---|
| `CV(edges_per_merchant)` | approximately `0` | `>= 0.25` | `>= 0.40` |
| `CV(countries_per_merchant)` | approximately `0` | `>= 0.20` | `>= 0.35` |
| top-1 edge-share p50 | approximately `0.002` (collapsed) | `[0.03, 0.20]` | `[0.05, 0.30]` with wider spread |
| median settlement overlap | near baseline / weak uplift | `>= 0.03` | `>= 0.07` |
| p75 settlement overlap | weak | `>= 0.06` | `>= 0.12` |
| median settlement distance | approximately `7,929 km` | `<= 6,000 km` | `<= 4,500 km` |
| `% non-null rule_id` / `% non-null rule_version` | near `0%` | `>= 99%` | `>= 99.8%` |
| active `rule_id` count | effectively one dominant pathway | `>= 3` | `>= 5` |
| S4 realism contract coverage | two narrow checks | full hard-gate pack active | full pack + tighter corridors |

Interpretation:
1. The expected uplift is not cosmetic; it is tied to measurable reversals of current degeneracy.
2. The largest local movement is expected on S2 heterogeneity and S1/S2 coherence metrics.
3. Explainability metrics should show step-change improvement immediately once lineage fields are enforced.

### 7.3 Downstream impact forecast
#### 7.3.1 Impact on Segment 5B
Expected impact: medium.
1. More realistic virtual edge diversity reduces cloned geographic signatures feeding later temporal/geo checks.
2. Settlement-coupled behavior should reduce artificial global-random patterns that currently distort realism narratives.

#### 7.3.2 Impact on Segment 6A
Expected impact: low to medium.
1. 6A is not mechanically identical to 3B outputs, but improved virtual-profile realism strengthens coherence surfaces used downstream.
2. Audit lineage improvements also improve cross-segment traceability quality.

#### 7.3.3 Impact on Segment 6B
Expected impact: medium to high.
1. 6B uses surfaces shaped by upstream topology and routing context.
2. Reduced upstream collapse in 3B should ease two major 6B issues:
   - overly uniform cross-border posture,
   - weak profile separation on downstream fraud/behavioral surfaces.
3. 3B remediation alone will not fully resolve 6B, but it removes a meaningful upstream constraint.

### 7.4 Confidence and caveats
1. Confidence to reach `B`: high, if Section 6 hard gates pass on all required seeds.
2. Confidence to reach `B+`: medium, because B+ depends on successful calibration (`CF-3B-06`) and may require limited upstream assist in residual edge cases.
3. Caveat: single-seed success is not accepted as grade evidence; cross-seed stability is mandatory.

### 7.5 Final grading decision rule for 3B
1. Award `B` only if all hard gates (`3B-V*`) and cross-seed stability gates (`3B-X*`) pass.
2. Award `B+` only if hard + stretch (`3B-S*`) + tighter stability thresholds pass.
3. Any hard-gate failure keeps 3B below `B`, regardless of improvements in other segments.
