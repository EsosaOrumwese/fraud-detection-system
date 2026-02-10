# Segment 5A Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 5A toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness
This section captures the observed statistical weaknesses in Segment 5A, prioritized by impact on realism and downstream propagation.

### 1.1 Primary weaknesses (material for realism)
1. **Channel realism collapse (`channel_group = mixed` only).**  
   The run does not realize CP/CNP channel separation even though policy structure supports it.  
   Evidence from the analytical report shows `class_zone_shape_5A` effectively collapses to `channel_group = mixed`.
   - Why this is material: 5A is the temporal-shape substrate for downstream segments. Without CP/CNP differentiation, downstream systems cannot learn realistic channel-conditioned rhythms (for example late-hour CNP lift and different weekend posture).
2. **Class and country concentration are stronger than policy targets.**  
   The realized composition breaches target posture:
   - `max_class_share = 0.600` (`consumer_daytime`) vs target `0.55`
   - `max_single_country_share_within_class = 0.532` vs target `0.35`
   - macro mix includes `consumer_daytime` around `0.621` share.
   - Why this is material: concentrated class-country mass narrows behavioral diversity and can create a stylized synthetic signature rather than a broad, organic composition.
3. **Tail-zone sparsity produces degenerate timezone behavior.**  
   Tail rows are mostly zero and dominate row count:
   - about `86.9%` of merchant-zone rows have `weekly_volume_expected = 0`
   - tail-zone zero rate is about `98.2%`
   - `262/414` TZIDs have weekly total `<= 1.0`.
   - Why this is material: timezone-level diagnostics become artifact-prone (for example degenerate peak-hour ties), and downstream geo-temporal realism becomes dependent on filtering rather than inherent data quality.
4. **DST residual mismatch remains a structured temporal blemish.**  
   Residual mismatch is concentrated in DST-shifting zones, not random:
   - non-DST zones `frac_mismatch ~0.0003`
   - DST-shift zones `frac_mismatch ~0.0178`
   - positive association between mismatch and DST shift (`rho ~0.62`).
   - Why this is material: this leaves a systematic local-time alignment scar on clock-time features and weakens explainability around transition windows.
5. **Overlay coverage is uneven at country edges.**  
   Country affected-share is mostly stable but not universal:
   - p10 `0.080`, p50 `0.112`, p90 `0.135`
   - some countries have `0%` affected volume while some reach about `0.28`.
   - Why this is material: edge countries can look artificially excluded or over-hit unless this coverage asymmetry is explicitly intended and documented.

### 1.2 Secondary weaknesses (quality constraints, not hard blockers)
1. **Within-class shape diversity is intentionally narrow.**  
   Each class uses a small template family (three variants selected deterministically by tzid).
   - Why this matters: reproducibility is strong, but behavioral heterogeneity can look template-driven rather than naturally varied.
2. **Upper-tail scale factors are very sharp for a small subset.**  
   Scale factors are right-skewed with long tail (for example p99 around `6.34`, max around `26.27`).
   - Why this matters: not necessarily wrong, but requires guardrails so rare extremes remain plausible rather than accidental.

### 1.3 Non-weaknesses (explicitly ruled out)
1. **Cross-surface conservation is strong.**  
   Baseline mass and local<->UTC conversion conserve totals to numerical precision.
2. **Class archetypes are behaviorally coherent.**  
   Day/evening/night and weekend patterns align with intended class semantics.
3. **Overlay amplitudes are bounded and explainable.**  
   Scenario factors remain within configured ranges and do not produce runaway shock behavior.

### 1.4 Section-1 interpretation
1. Segment 5A is internally coherent but statistically stylized.
2. The largest realism blockers are channel-collapse, concentration, tail-zone degeneracy, and DST residual structure.
3. Because 5A feeds downstream timing and geo-temporal structure, these weaknesses have leverage beyond 5A itself.
4. Remediation should therefore target these specific weak points while preserving strong conservation and archetype coherence.

## 2) Expected Statistical Posture (B/B+)
This section defines the target statistical posture for Segment 5A under remediation, with explicit `B` and `B+` acceptance gates.

### 2.1 Posture objective
For 5A, the target is not only plausible aggregate rhythms.  
The target is a diverse, explainable temporal generator that:
1. Preserves existing strengths (mass conservation, class-archetype coherence).
2. Removes stylization artifacts (channel collapse, over-concentration, dormant tail zones, DST residual structure).
3. Produces stable upstream signal quality for 5B/6A/6B.

### 2.2 Non-negotiable `B` gates (hard requirements)
1. **Mass conservation and normalization remain exact.**
   - Local/UTC total conservation error: `MAE <= 1e-9` (practically zero).
   - Shape normalization error per key: `max_abs_diff <= 1e-9`.
2. **No structural regression in class archetypes.**
   - `online_24h` remains materially more night-heavy than `consumer_daytime`.
   - `office_hours` remains materially lower weekend-share than `evening_weekend`.
3. **DST residuals are bounded and non-dominant.**
   - overall mismatch rate: `<= 0.20%` for `B`, `<= 0.05%` for `B+`
   - DST-zone mismatch rate: `<= 0.50%` for `B`, `<= 0.20%` for `B+`.

### 2.3 B/B+ targets on observed weak axes
1. **Channel realization (CP/CNP realism)**
   - `B`: at least two realized `channel_group` values with non-trivial mass (each `>= 10%` in eligible rows).
   - `B+`: all intended channel groups realized; no collapse to `mixed`.
   - Separation target:
     - `night_share(CNP) - night_share(CP) >= 0.08` (`B`)
     - `night_share(CNP) - night_share(CP) >= 0.12` (`B+`).
2. **Class concentration**
   - `max_class_share <= 0.55` (`B`, consistent with current policy target).
   - `max_class_share <= 0.50` (`B+`, lower stylization).
3. **Country-within-class concentration**
   - `max_single_country_share_within_class <= 0.40` (`B`)
   - `max_single_country_share_within_class <= 0.35` (`B+`).
4. **Tail-zone dormancy reduction**
   - tail-zone zero-rate: `<= 90%` (`B`), `<= 80%` (`B+`)
   - non-trivial TZIDs (`weekly_total > 1.0`):
     - `>= 190` for `B`
     - `>= 230` for `B+`.
5. **Overlay country coverage uniformity**
   - no zero-coverage among top-volume countries.
   - coverage spread control:
     - `p90/p10(country_affected_share) <= 2.0` (`B`)
     - `p90/p10(country_affected_share) <= 1.6` (`B+`).

### 2.4 Strength-preservation constraints
Remediation must preserve:
1. **Heavy-tail realism** in merchant volume (do not flatten macro shape to pass concentration gates).
2. **Overlay boundedness** (calendar amplitudes remain policy-bounded; no synthetic shock inflation).
3. **Flag coherence** (`high_variability_flag` remains aligned with higher CV and higher night/weekend share).

### 2.5 Cross-seed stability expectations
Required seed panel: `{42, 7, 101, 202}`.
1. All hard gates must pass on every seed.
2. Coefficient-of-variation targets on key metrics:
   - `B`: `CV <= 0.25`
   - `B+`: `CV <= 0.15`.

### 2.6 Section-2 interpretation
1. `B` means Segment 5A is no longer dominated by collapse/over-concentration artifacts.
2. `B+` means Segment 5A becomes a robust, diverse upstream temporal generator for downstream fraud realism.
3. Any change that improves weak axes but breaks conservation or archetype coherence is invalid.

## 3) Root-Cause Trace
This section traces each observed weakness to its most probable generating mechanism, maps it to specific 5A states and policy surfaces, and identifies upstream amplifiers.

### 3.1 Causal graph (condensed)
`1A merchant/site topology` + `2A country-timezone sparsity` -> `5A S1 class assignment` -> `5A S2 shape/template assignment` -> `5A S3 baseline intensity scaling` -> `5A S4 overlay + local-time handling` -> observed 5A posture (concentration, tail dormancy, DST residuals, uneven overlay coverage).

### 3.2 Weakness-to-cause mapping
1. **Weakness: Channel realism collapse (`channel_group = mixed` only).**
   - Immediate mechanism:
     - S1 emits class assignments without meaningful realized CP/CNP branch diversity in downstream shape rows.
     - The pipeline effectively behaves as a single-channel generator at the `class_zone_shape_5A` surface.
   - Why this happened:
     - Channel dimension is present structurally but not activated strongly enough by the effective policy path.
     - S2/S3 therefore consume mostly channel-agnostic priors.
   - Primary loci:
     - `packages/engine/src/engine/layers/l2/seg_5A/s1_demand_classification/runner.py`
     - `config/layer2/5A/policy/merchant_class_policy_5A.v1.yaml`
   - Upstream amplifier:
     - None required for failure; this is mainly a local 5A modeling collapse.

2. **Weakness: Class and country concentration above target posture.**
   - Immediate mechanism:
     - S1 class allocation priors and assignment process concentrate mass in dominant classes (notably `consumer_daytime`).
     - S2/S3 preserve this skew rather than diffusing it.
   - Why this happened:
     - Prior/cap setup appears under-regularized for diversity.
     - Deterministic mapping from class-country context to a small shape family limits dilution.
   - Primary loci:
     - `packages/engine/src/engine/layers/l2/seg_5A/s1_demand_classification/runner.py`
     - `config/layer2/5A/policy/merchant_class_policy_5A.v1.yaml`
     - `config/layer2/5A/policy/shape_library_5A.v1.yaml`
   - Upstream amplifier:
     - 1A merchant mass concentration by country/merchant archetype increases the pressure toward class concentration.
     - Relevant upstream surface:
       - `config/layer1/1A/ingress/transaction_schema_merchant_ids.bootstrap.yaml`

3. **Weakness: Tail-zone dormancy (`weekly_volume_expected = 0` for most tail rows).**
   - Immediate mechanism:
     - S3 baseline intensity multiplies low-share cells by conservative scale terms and then floor/rounding behavior drives many cells to zero.
   - Why this happened:
     - Tail zones begin with very low support.
     - Scale policy does not provide sufficient lower-tail lift for non-dominant zone-country pairs.
   - Primary loci:
     - `packages/engine/src/engine/layers/l2/seg_5A/s3_baseline_intensity/runner.py`
     - `config/layer2/5A/policy/demand_scale_policy_5A.v1.yaml`
     - `config/layer2/5A/policy/shape_time_grid_policy_5A.v1.yaml`
   - Upstream amplifier:
     - 2A timezone allocation sparsity gives S3 a large near-zero starting surface.

4. **Weakness: Structured DST residual mismatch.**
   - Immediate mechanism:
     - S4 local-time conversion and calendar application are mostly correct outside DST but leave a deterministic residual near DST boundaries.
   - Why this happened:
     - Time conversion behavior appears to apply transition handling inconsistently for a subset of DST-observing timezone/date windows.
   - Primary loci:
     - `packages/engine/src/engine/layers/l2/seg_5A/s4_calendar_overlays/runner.py`
     - Timezone conversion/util path invoked by S4
   - Upstream amplifier:
     - 2A timezone mix is Europe-heavy and DST-observing, so even small local conversion defects are visible at scale.

5. **Weakness: Overlay country coverage unevenness (including zero-coverage tails).**
   - Immediate mechanism:
     - S4 overlay target selection is driven by base intensity and scenario policy constraints, so low-volume countries can be skipped while high-volume slices over-represent.
   - Why this happened:
     - Overlay selection logic is not sufficiently stratified by country coverage constraints.
     - Existing constraints optimize boundedness/stability more than cross-country fairness.
   - Primary loci:
     - `config/layer2/5A/scenario/scenario_overlay_policy_5A.v1.yaml`
     - `config/layer2/5A/scenario/scenario_overlay_validation_policy_5A.v1.yaml`
     - `packages/engine/src/engine/layers/l2/seg_5A/s4_calendar_overlays/runner.py`
   - Upstream amplifier:
     - S3 concentration by country/class increases uneven overlay realization.

6. **Weakness: Narrow within-class diversity (few shape variants per class).**
   - Immediate mechanism:
     - S2 selects among a small template pool, with deterministic assignment keyed by timezone/context.
   - Why this happened:
     - Template cardinality is intentionally low and assignment is deterministic for reproducibility.
   - Primary loci:
     - `packages/engine/src/engine/layers/l2/seg_5A/s2_weekly_shape_library/runner.py`
     - `config/layer2/5A/policy/shape_library_5A.v1.yaml`
   - Upstream amplifier:
     - Country/timezone concentration makes low template cardinality appear stronger than it would in a more diffuse topology.

### 3.3 Confidence rating by trace
1. **High confidence**:
   - Channel collapse, class concentration, tail dormancy, and narrow template diversity.
   - Rationale: these are direct reflections of measured outputs and known policy structure.
2. **Medium-high confidence**:
   - DST residual mechanism.
   - Rationale: signature is strongly structured (DST-linked), but exact branch-level code behavior still needs line-level confirmation during fix implementation.
3. **High confidence**:
   - Overlay unevenness as a consequence of base-volume-weighted targeting plus non-stratified country coverage constraints.

### 3.4 Upstream dependency summary
1. 5A issues are not fully local; 1A and 2A materially condition how severe 5A weaknesses appear.
2. Concentration and sparsity are propagated phenomena:
   - upstream skew -> S1 concentration -> S3 zero-heavy tails -> S4 uneven coverage.
3. Therefore, a 5A-only fix can improve posture but may saturate early unless upstream sparsity/concentration is also adjusted.

### 3.5 Section-3 interpretation
1. The dominant failure mode is not random noise; it is a deterministic composition of policy choices.
2. The highest-leverage causes are:
   - channel branch collapse in S1,
   - lower-tail suppression in S3,
   - limited diversity in S2,
   - DST boundary handling in S4.
3. This trace supports targeted remediation in Section 4 rather than broad retuning.

## 4) Remediation Options (Ranked + Tradeoffs)
This section defines remediation options that map directly to Section-3 root causes, ranks them by impact-to-risk, and specifies practical bundles for `B` and `B+` targets.

### 4.1 Option catalog (cause-linked)
1. **O1: Channel-branch activation in S1/S2 (remove `mixed` collapse).**
   - What changes:
     - Enforce realized CP/CNP branching in class->shape generation, not just structural placeholders.
     - Introduce channel-conditioned priors so channel effects are visible in realized rows.
   - Targets:
     - Primary: channel collapse.
     - Secondary: concentration reduction via extra composition axis.
   - Upside:
     - Large downstream realism gain (5B/6A/6B) because channel-conditioned behavior becomes learnable.
   - Tradeoffs:
     - If over-separated, CP/CNP can become stylized and unrealistic.
     - Must preserve total mass and archetype coherence.

2. **O2: Class-prior deconcentration + explicit cap controls in S1.**
   - What changes:
     - Lower dominant-class prior mass.
     - Tighten share caps and add mild diversity regularization (for example entropy floor or anti-concentration penalty).
   - Targets:
     - Primary: class/country concentration overshoot.
   - Upside:
     - Directly addresses `max_class_share` and country-within-class spikes.
   - Tradeoffs:
     - Too much flattening can erase plausible heavy-tail composition.
     - Needs seeded stability checks to avoid cross-seed drift.

3. **O3: Tail-zone lift in S3 baseline intensity (controlled lower-tail rescue).**
   - What changes:
     - Add bounded lower-tail support so low-support zone-country cells do not collapse to exact zero at extreme rates.
     - Soften floor/rounding interaction for sparse cells while preserving macro totals.
   - Targets:
     - Primary: tail-zone dormancy.
     - Secondary: improves overlay coverage opportunity set.
   - Upside:
     - Strong gain in timezone realism and diagnostics quality.
   - Tradeoffs:
     - Over-lift can synthesize fake tail activity.
     - Must be support-aware and bounded by country/zone evidence.

4. **O4: Shape-library expansion + less deterministic reuse in S2.**
   - What changes:
     - Increase templates per class.
     - Replace strict deterministic tzid-only mapping with seeded constrained stochastic selection.
   - Targets:
     - Primary: within-class diversity limitation.
     - Secondary: reduces template fingerprinting that amplifies concentration artifacts.
   - Upside:
     - Better heterogeneity without losing reproducibility (seed-locked).
   - Tradeoffs:
     - Policy complexity increases.
     - Requires clear explainability of sampling rules.

5. **O5: DST-boundary correction in S4 local-time handling.**
   - What changes:
     - Explicit DST-aware conversion at transition windows and edge-case timezone handling.
   - Targets:
     - Primary: structured DST residual mismatch.
   - Upside:
     - High trust gain; removes deterministic temporal blemish.
   - Tradeoffs:
     - Timezone logic is brittle; patch must be guarded by targeted tests.

6. **O6: Overlay country-stratification controls in S4 scenario policy.**
   - What changes:
     - Add coverage constraints so top-volume countries are never at zero affected-share.
     - Bound country-level affected-share dispersion.
   - Targets:
     - Primary: overlay unevenness at country edges.
   - Upside:
     - Removes edge-country exclusion artifacts while keeping scenario amplitudes bounded.
   - Tradeoffs:
     - Over-constraint can make overlays look engineered rather than organic.

7. **O7: Upstream assist (1A/2A concentration-sparsity tuning).**
   - What changes:
     - Reduce upstream concentration and extreme timezone sparsity entering 5A.
   - Targets:
     - Amplifiers for concentration, dormancy, and overlay unevenness.
   - Upside:
     - Highest long-term durability across downstream segments.
   - Tradeoffs:
     - Largest blast radius and coordination cost.
     - Requires cross-segment re-baselining.

### 4.2 Ranking (impact, risk, dependency)
1. **Rank 1: O1 + O2 (highest near-term lift).**
   - Why first:
     - Directly attacks the biggest realism blockers and most visible B/B+ gate misses.
   - Dependency:
     - Primarily local to 5A.

2. **Rank 2: O3 (required for tail realism).**
   - Why second:
     - Dormant tails are a core statistical artifact, not a cosmetic issue.
   - Dependency:
     - Mostly local; sensitive to upstream sparsity.

3. **Rank 3: O5 (DST defect correction).**
   - Why third:
     - Deterministic defect with clear signature and strong explainability benefit.
   - Dependency:
     - Local S4 timezone path.

4. **Rank 4: O6 (coverage fairness hardening).**
   - Why fourth:
     - Needed for B+ posture on country-level fairness and stability.
   - Dependency:
     - S4 scenario policy + validation path.

5. **Rank 5: O4 (diversity polish for B+).**
   - Why fifth:
     - Important, but less blocking than O1/O2/O3 for immediate grade lift.
   - Dependency:
     - Local S2 policy and selection logic.

6. **Rank 6: O7 (escalation path).**
   - Why sixth:
     - Structural but expensive; trigger only if 5A-local remediation saturates.
   - Dependency:
     - Cross-segment alignment with 1A/2A remediations.

### 4.3 Recommended remediation bundles
1. **Bundle A (target `B`, lower risk).**
   - Include:
     - O1 + O2 + O3 + O5
   - Expected effect:
     - Clears primary blockers (channel collapse, over-concentration, dormancy, DST residuals) with contained scope.

2. **Bundle B (target `B+`, full 5A posture).**
   - Include:
     - Bundle A + O6 + O4
   - Expected effect:
     - Adds country-coverage fairness and within-class diversity needed for robust synthetic realism.

3. **Bundle C (escalation if B+ misses remain).**
   - Include:
     - Bundle B + O7
   - Expected effect:
     - Removes upstream structural amplifiers when local tuning reaches diminishing returns.

### 4.4 Option-level guardrails (must hold during remediation)
1. Do not trade away conservation invariants to improve diversity metrics.
2. Do not flatten class composition so far that heavy-tail behavior disappears.
3. Tail-lift must be bounded by support to avoid fabricated activity in implausible cells.
4. Channel separation must be meaningful but not exaggerated.
5. Overlay fairness controls must preserve scenario semantics and bounded amplitudes.
6. Upstream tuning is escalation, not first-line 5A remediation.

### 4.5 Section-4 interpretation
1. The minimum serious path to `B` is Bundle A.
2. The credible path to `B+` is Bundle B, with Bundle C as structural backup.
3. This ranking keeps changes causal, auditable, and aligned with Section-3 traceability.

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)
This section pins the selected remediation package for 5A and converts it into concrete policy/code deltas with rollout order and non-regression constraints.

### 5.1 Chosen package
1. **Selected package: `Bundle B`**
   - Included options: `O1 + O2 + O3 + O5 + O6 + O4`.
   - Why selected:
     - `Bundle A` is sufficient for a conservative `B` target, but the desired posture is `B/B+` with downstream leverage.
     - `Bundle B` is the minimal package that can plausibly clear B+ gates on channel realism, concentration, tail activity, DST hygiene, overlay fairness, and template diversity.
2. **Escalation rule (`O7` upstream assist)**
   - Activate only if post-remediation run still misses at least two of:
     - `max_class_share <= 0.50`
     - tail-zone zero-rate `<= 80%`
     - DST-zone mismatch `<= 0.20%`
     - no zero-coverage among top-volume countries.

### 5.2 Exact deltas by option
1. **O1: Channel-branch activation (S1/S2)**
   - Policy deltas:
     - File: `config/layer2/5A/policy/merchant_class_policy_5A.v1.yaml`
     - Add explicit per-class CP/CNP priors (initial proposal):
       - `consumer_daytime`: `cp=0.72`, `cnp=0.28`
       - `online_24h`: `cp=0.20`, `cnp=0.80`
       - `online_bursty`: `cp=0.30`, `cnp=0.70`
       - `office_hours`: `cp=0.78`, `cnp=0.22`
       - `fuel_convenience`: `cp=0.90`, `cnp=0.10`
       - `evening_weekend`: `cp=0.55`, `cnp=0.45`
       - `travel_hospitality`: `cp=0.60`, `cnp=0.40`
       - `bills_utilities`: `cp=0.35`, `cnp=0.65`
     - Add realized-mass guardrail:
       - `min_realized_channel_share_per_branch: 0.10` for eligible classes.
   - Code deltas:
     - File: `packages/engine/src/engine/layers/l2/seg_5A/s1_demand_classification/runner.py`
       - Remove effective single-channel fallback in eligible paths.
       - Emit explicit `channel_group` with seeded deterministic assignment.
     - File: `packages/engine/src/engine/layers/l2/seg_5A/s2_weekly_shape_library/runner.py`
       - Resolve templates by `(class, channel_group)` key where available.
       - Keep class-only fallback with audit counter if channel-specific template missing.

2. **O2: Class deconcentration and cap enforcement (S1)**
   - Policy deltas:
     - File: `config/layer2/5A/policy/merchant_class_policy_5A.v1.yaml`
     - Reduce dominant-class prior (`consumer_daytime`) by about 15% relative weight.
     - Reallocate to underweight classes (`online_bursty`, `travel_hospitality`, `evening_weekend`, `bills_utilities`).
     - Add cap controls:
       - `max_class_share_soft: 0.52`
       - `max_class_share_hard: 0.55`
       - `max_country_share_within_class_soft: 0.37`
       - `max_country_share_within_class_hard: 0.40`
   - Code deltas:
     - File: `packages/engine/src/engine/layers/l2/seg_5A/s1_demand_classification/runner.py`
       - Add seeded rebalance pass after initial assignment:
         - shift marginal assignments from classes above soft cap to policy-nearest underweight classes.
       - Emit diagnostics:
         - `max_class_share`, `max_country_share_within_class`, `rebalance_moved_count`.

3. **O3: Tail-zone lift in S3 (bounded lower-tail rescue)**
   - Policy deltas:
     - File: `config/layer2/5A/policy/demand_scale_policy_5A.v1.yaml`
     - Add tail-rescue controls:
       - `tail_floor_epsilon: 0.015`
       - `tail_lift_power: 0.85`
       - `tail_lift_max_multiplier: 2.5`
       - `min_support_threshold` gate for eligibility.
   - Code deltas:
     - File: `packages/engine/src/engine/layers/l2/seg_5A/s3_baseline_intensity/runner.py`
       - Apply floor-before-rounding for eligible sparse cells.
       - Re-normalize within merchant-week envelope to preserve totals.
       - Emit tail diagnostics:
         - overall zero-rate
         - tail-zone zero-rate
         - count of TZIDs with `weekly_total > 1.0`.

4. **O5: DST boundary correction (S4 local-time handling)**
   - Code deltas:
     - File: `packages/engine/src/engine/layers/l2/seg_5A/s4_calendar_overlays/runner.py`
       - Use timezone-aware local conversion with explicit DST transition handling.
       - Add per-tzid/per-date residual diagnostics table:
         - `frac_mismatch`
         - signed offset histogram
         - transition-window indicator.
   - Validation policy deltas:
     - File: `config/layer2/5A/validation/validation_policy_5A.v1.yaml`
     - Add hard checks:
       - overall mismatch `<= 0.20%` for `B`, `<= 0.05%` for `B+`
       - DST-zone mismatch `<= 0.50%` for `B`, `<= 0.20%` for `B+`.

5. **O6: Overlay country-stratification controls (S4 scenario policy)**
   - Policy deltas:
     - File: `config/layer2/5A/scenario/scenario_overlay_policy_5A.v1.yaml`
     - Add country coverage constraints:
       - `min_affected_share_top_volume_country: 0.05`
       - `max_affected_share_top_volume_country: 0.18`
       - `coverage_dispersion_limit_p90_p10: 2.0` (`B`) / `1.6` (`B+`).
     - Define top-volume country set via share threshold.
   - Code deltas:
     - File: `packages/engine/src/engine/layers/l2/seg_5A/s4_calendar_overlays/runner.py`
       - Add stratified selection:
         - country stratum first, class/zone second.
       - Preserve global scenario amplitude constraints.

6. **O4: Shape-library diversity expansion (S2)**
   - Policy deltas:
     - File: `config/layer2/5A/policy/shape_library_5A.v1.yaml`
     - Raise template cardinality per class from 3 to at least 7.
     - Add channel-conditioned variants where class has mixed channel priors.
     - Add per-class template-usage entropy floor.
   - Code deltas:
     - File: `packages/engine/src/engine/layers/l2/seg_5A/s2_weekly_shape_library/runner.py`
       - Replace strict tzid->single-template mapping with seeded constrained sampling.
       - Deterministic seed key:
         - `(merchant_id, class, channel_group, run_seed)`.

### 5.3 Non-regression invariants (must remain true)
1. Local/UTC total conservation remains exact to numerical tolerance.
2. Class archetype ordering remains intact:
   - `online_24h` night-share > `consumer_daytime` night-share.
   - `office_hours` weekend-share < `evening_weekend` weekend-share.
3. Overlay amplitudes remain within existing scenario bounds.
4. No new key-level parity breaks introduced by channel/template branching.

### 5.4 Rollout sequence (execution order)
1. **Phase A: O5 first**
   - Lowest coupling, clear defect signature, immediate trust gain.
2. **Phase B: O1 + O2 together**
   - Channel and class composition are coupled; patching them together prevents oscillatory tuning.
3. **Phase C: O3**
   - Tail rescue after class/channel posture settles.
4. **Phase D: O6 + O4**
   - Fairness and diversity polish for B+ closure.
5. **Phase E: O7 (conditional)**
   - Trigger only if explicit miss criteria remain after Phase D.

### 5.5 Expected movement after this chosen spec
1. `channel_group` should no longer collapse to `mixed`; CP/CNP should both carry non-trivial realized mass.
2. `max_class_share` should move from `0.600` toward `<=0.55` (`B`) and then `<=0.50` (`B+`).
3. tail-zone zero-rate should decline from current extreme levels toward `<=90%` (`B`) and `<=80%` (`B+`).
4. DST mismatch should compress to B/B+ gates with non-DST and DST windows both stable.
5. Overlay country affected-share spread should narrow, with zero-coverage removed for top-volume countries.

### 5.6 Section-5 interpretation
1. This is a concrete fix spec, not a conceptual recommendation list.
2. The chosen package intentionally balances statistical lift, coupling risk, and downstream propagation impact.
3. The sequence is designed to avoid false attribution during validation by separating low-coupling fixes from composition retuning.

## 6) Validation Tests + Thresholds
This section defines the acceptance protocol for 5A remediation. It specifies hard gates, statistical tests, cross-seed stability rules, and escalation criteria.

### 6.1 Validation scope and run protocol
1. Use the standard seed panel for all claims:
   - `{42, 7, 101, 202}`.
2. Validate every 5A state surface, not just final aggregates:
   - `S1` class/channel assignment outputs
   - `S2` template assignment outputs
   - `S3` baseline intensity outputs
   - `S4` overlay + local-time conversion outputs.
3. Evaluate each run on two layers:
   - deterministic gate pass/fail
   - statistical evidence (distribution tests/effect-size checks).

### 6.2 Core gate matrix (`B` vs `B+`)
1. **G1: Realized channel branches**
   - `B`: at least 2 realized channel branches with non-trivial mass.
   - `B+`: all intended channel branches realized.
2. **G2: Minimum realized branch mass (eligible rows)**
   - `B`: each branch `>= 0.10`.
   - `B+`: each branch `>= 0.12`.
3. **G3: Channel temporal separation**
   - Metric: `night_share(CNP) - night_share(CP)`.
   - `B`: `>= 0.08`.
   - `B+`: `>= 0.12`.
4. **G4: Class concentration**
   - Metric: `max_class_share`.
   - `B`: `<= 0.55`.
   - `B+`: `<= 0.50`.
5. **G5: Country-within-class concentration**
   - Metric: `max_single_country_share_within_class`.
   - `B`: `<= 0.40`.
   - `B+`: `<= 0.35`.
6. **G6: Tail-zone dormancy**
   - Metric: tail-zone zero-rate.
   - `B`: `<= 0.90`.
   - `B+`: `<= 0.80`.
7. **G7: Non-trivial timezone breadth**
   - Metric: count of TZIDs with `weekly_total > 1.0`.
   - `B`: `>= 190`.
   - `B+`: `>= 230`.
8. **G8: DST mismatch overall**
   - `B`: `<= 0.20%`.
   - `B+`: `<= 0.05%`.
9. **G9: DST mismatch in DST-observing zones**
   - `B`: `<= 0.50%`.
   - `B+`: `<= 0.20%`.
10. **G10: Overlay zero-coverage among top-volume countries**
    - `B`: `0`.
    - `B+`: `0`.
11. **G11: Overlay country coverage dispersion**
    - Metric: `p90/p10(country_affected_share)`.
    - `B`: `<= 2.0`.
    - `B+`: `<= 1.6`.
12. **G12: Template diversity (per class effective usage)**
    - `B`: effective templates used `>= 4`.
    - `B+`: effective templates used `>= 5`.

### 6.3 Non-regression invariants (hard fail if broken)
1. Local/UTC mass conservation:
   - `MAE <= 1e-9`.
2. Per-key shape normalization:
   - `max_abs(sum(shape)-1) <= 1e-9`.
3. Archetype ordering remains intact:
   - `night_share(online_24h) > night_share(consumer_daytime)`.
   - `weekend_share(office_hours) < weekend_share(evening_weekend)`.
4. Overlay amplitudes stay inside configured scenario bounds.
5. No new key-level parity break from channel/template expansion.

### 6.4 Statistical evidence tests (beyond threshold clipping)
1. **Class-share fit vs target priors**
   - Test: chi-square goodness-of-fit.
   - Accept if divergence is reduced from baseline and no catastrophic mismatch remains.
2. **CP vs CNP hour-of-day separation**
   - Test: two-sample KS test + effect direction check.
   - Accept if separation is significant and directionally correct (CNP more night-weighted).
3. **DST-structure collapse**
   - Test: Spearman correlation between mismatch rate and DST-shift indicator.
   - Accept if correlation materially drops versus baseline and non-transition windows are near zero mismatch.
4. **Overlay fairness robustness**
   - Test: bootstrap confidence interval for `p90/p10(country_affected_share)`.
   - Accept if CI lies within target threshold band.
5. **Tail activation robustness**
   - Test: bootstrap CI for tail-zone zero-rate and non-trivial TZID count.
   - Accept if pass is CI-supported, not point-estimate-only.

### 6.5 Cross-seed stability requirements
1. All critical gates (`G1` to `G11`) must pass on every seed for claimed grade.
2. Cross-seed stability target:
   - `B`: `CV <= 0.25` on key remediation metrics.
   - `B+`: `CV <= 0.15`.
3. A single-seed pass with multi-seed instability is not accepted as remediation success.

### 6.6 Grade decision policy
1. **`B` pass**
   - all invariants pass
   - all critical gates meet `B` thresholds on all seeds
   - at most one non-critical miss (`G12`) with documented follow-up.
2. **`B+` pass**
   - all invariants pass
   - all critical gates meet `B+` thresholds on all seeds
   - cross-seed CV meets `B+` limits.
3. **Fail**
   - any invariant breach
   - any critical-gate miss on any seed.

### 6.7 Validation wave sequencing (for causality clarity)
1. After `O5` only:
   - validate DST gates (`G8`, `G9`) + invariants.
2. After `O1 + O2`:
   - validate channel/concentration gates (`G1` to `G5`) + invariants.
3. After `O3`:
   - validate tail gates (`G6`, `G7`) + invariants.
4. After `O6 + O4`:
   - validate overlay/diversity gates (`G10` to `G12`) + full invariants.
5. Final integrated run:
   - full gate matrix + full statistical evidence tests + cross-seed stability panel.

### 6.8 Escalation trigger to upstream remediation (`O7`)
Escalate to upstream (1A/2A) assistance only if, after full Bundle B:
1. at least two critical gates still miss, or
2. one critical gate fails on at least two seeds, or
3. thresholds pass but statistical evidence still shows structural artifacts (for example DST-linked residual coupling or concentration rebound).

### 6.9 Section-6 interpretation
1. This validation framework prevents false wins from threshold-only tuning.
2. It ensures remediation is both numerically compliant and statistically plausible.
3. It also keeps change attribution clean by testing in staged waves before final integrated acceptance.

## 7) Expected Grade Lift (Local + Downstream Impact)
This section estimates the expected realism-grade movement if Section-5 fixes pass the Section-6 acceptance protocol, including likely downstream effects.

### 7.1 Local grade lift expectation (5A)
1. **Current operating posture**
   - Statistically coherent but artifact-heavy on channel collapse, concentration, tail dormancy, and DST residual structure.
2. **After Bundle A (`O1 + O2 + O3 + O5`)**
   - Expected local result: stable `B`.
   - Rationale:
     - Bundle A addresses all primary blockers required for B-gate closure.
3. **After Bundle B (`Bundle A + O6 + O4`)**
   - Expected local result: credible `B+`.
   - Rationale:
     - Adds fairness and diversity controls typically required for stronger synthetic-realism claims.
4. **After Bundle B plus conditional O7 escalation**
   - Expected local result: `B+` with higher robustness under seed and scenario variation.

### 7.2 Expected movement of core 5A metrics
1. **Channel realization**
   - From effective `mixed` collapse to dual realized CP/CNP branches.
   - Expected:
     - both branches non-trivial in eligible rows,
     - measurable night-share separation.
2. **Class concentration**
   - `max_class_share` expected to move from `0.600` toward:
     - about `0.53-0.55` after Bundle A,
     - about `0.48-0.51` after Bundle B.
3. **Country-within-class concentration**
   - `max_single_country_share_within_class` expected to move from `0.532` toward:
     - about `0.38-0.41` after Bundle A,
     - about `0.33-0.37` after Bundle B.
4. **Tail dormancy**
   - tail-zone zero-rate expected to move from current extreme toward:
     - about `88-90%` after Bundle A,
     - about `75-82%` after Bundle B.
5. **DST mismatch**
   - DST-zone mismatch expected to compress into:
     - `B` band after O5,
     - `B+` band with stabilized transition handling.
6. **Overlay coverage fairness**
   - Expected:
     - no zero-coverage in top-volume countries,
     - lower country affected-share dispersion (`p90/p10` tightening).

### 7.3 Downstream impact expectation
1. **Impact on 5B**
   - Expected lift: approximately `+0.3` to `+0.7` grade steps.
   - Why:
     - 5B inherits temporal/geographic posture from 5A; channel and DST cleanup directly reduce artifact transfer.
2. **Impact on 6A**
   - Expected lift: approximately `+0.1` to `+0.4` grade steps.
   - Why:
     - 6A is less directly shaped by 5A than 5B/6B, but improved upstream timing realism still reduces consistency stress.
3. **Impact on 6B**
   - Expected lift: approximately `+0.5` to `+1.0` grade steps if 6B-local fixes are also applied.
   - Why:
     - 5A remediation removes forcing artifacts, but 6B still needs its own fixes on amount/channel/fraud-overlay behavior.

### 7.4 Confidence and dependency statement
1. **High-confidence gains**
   - Channel realization, concentration reduction, and DST residual correction.
2. **Medium-confidence gains**
   - Tail activation and overlay fairness, because they depend on support-aware tuning sensitivity.
3. **Dependency note**
   - 5A improvement is necessary but not sufficient for engine-wide `B/B+`.
   - Final whole-engine claim remains conditional on 5B and 6B closure.

### 7.5 Grade-claim policy for 5A
1. Claim `5A = B` only if:
   - all critical B gates pass on all seeds,
   - all invariants pass.
2. Claim `5A = B+` only if:
   - all critical B+ gates pass on all seeds,
   - cross-seed CV stability gates also pass.
3. Any partial pass is reported as:
   - `improved but not promotable`.

### 7.6 Section-7 interpretation
1. The realistic target path is:
   - Bundle A -> `B`,
   - Bundle B -> `B+`.
2. Expected downstream lift is meaningful but conditional on downstream local remediation completion.
3. This section provides a forecast, not acceptance evidence; Section 6 remains the authority for grade promotion.
