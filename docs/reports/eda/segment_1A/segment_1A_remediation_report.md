# Segment 1A Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 1A toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness

For segment `1A`, the observed weaknesses are concentrated in population-shape realism, geographic realism, identity semantics, and stochastic variance realism.

1. Missing single-site merchant base tier (major)
- `outlets_per_merchant` has `min=2`, so no merchant exists at `outlet_count=1`.
- `single_vs_multi_flag` is effectively always `True` in this run.
- Why this is a weakness:
the most common merchant type in normal economies (single-site merchants) is absent, which structurally biases downstream layers toward chain-like behavior.

2. Over-global candidate universe with weak realization coupling (major)
- Candidate breadth is near-saturated (`median ~38` candidates out of `39` countries).
- Actual foreign membership realization is sparse for most merchants (low realization ratio, weak candidate-to-membership coupling).
- Why this is a weakness:
the generator encodes "almost everyone could expand everywhere," while realized behavior says "most do not," producing a policy posture that looks internally inconsistent for baseline realism.

3. Elevated home-vs-legal mismatch across broad merchant sizes (major)
- Share of rows with `home_country_iso != legal_country_iso` is high (about `38.6%` in the assessment run).
- The mismatch is not isolated to very large/global merchants; it appears broadly across size buckets.
- Why this is a weakness:
for baseline synthetic commerce, legal-domicile divergence should be concentrated in specific enterprise strata, not distributed this widely.

4. Site identity semantics create downstream ambiguity (moderate-major)
- Duplicate merchant-site pairs are material (pair-level duplicate exposure is non-trivial; merchant exposure is broad).
- Duplicates are primarily cross-country reuse patterns.
- Why this is a weakness:
if downstream consumers assume site IDs are globally unique physical locations, joins/features can silently encode wrong semantics.

5. NB dispersion block is statistically weak (major; stochastic realism)
- Implied merchant-level `phi` is near-constant around `~12` with extremely low spread (`CV(phi)~0.00053`, `P95/P05~1.00004`).
- Channel/GDP effects in dispersion are effectively flat at merchant level.
- Why this is a weakness:
mean-level heterogeneity exists, but variance-level heterogeneity is almost absent; synthetic counts can look too regular once conditioned on mean.

6. Missing approved outputs reduce auditability and controllability (moderate)
- Expected artifacts such as `s3_integerised_counts`, `s3_site_sequence`, `sparse_flag`, `merchant_abort_log`, and `hurdle_stationarity_tests` are absent in the assessed output set.
- Why this is a weakness:
some realism properties cannot be fully verified or monitored run-over-run, even where data may look plausible.

7. Net observed posture for `1A`
- Strong signal:
heavy-tail outlet concentration is present and directionally plausible.
- Weak signal:
base-tier absence (no single-site), over-global candidate design, high domicile mismatch, and near-constant dispersion dominate realism risk.
- Downstream implication:
these weaknesses propagate into `2A/2B` topology and weighting behavior, then into `3A/3B`, and eventually shape `5A/5B/6A/6B` event realism.

## 2) Expected Statistical Posture (B/B+)

For segment `1A`, a `B/B+` target means the generated merchant/outlet world remains synthetic and policy-driven, but no longer violates core baseline realism in population shape, geographic structure, candidate logic, or variance behavior.

1. Target posture by surface

| Surface | Metric | `B` target | `B+` target | Why it matters |
|---|---|---:|---:|---|
| Merchant pyramid | Single-site merchant share (`outlet_count=1`) | 25% to 45% | 35% to 55% | Restores realistic base tier |
| Merchant pyramid | `outlets_per_merchant` median | 6 to 20 | 8 to 18 | Avoids giant-heavy bias |
| Concentration | Top-10% share of outlets | 35% to 55% | 38% to 50% | Keeps heavy-tail without collapse |
| Concentration | Gini (outlets per merchant) | 0.45 to 0.62 | 0.48 to 0.58 | Plausible inequality range |

| Surface | Metric | `B` target | `B+` target | Why it matters |
|---|---|---:|---:|---|
| Geographic/legal realism | `home != legal` row share | 10% to 25% | 12% to 20% | Current level is too globally/offshore biased |
| Geographic/legal realism | Size gradient in mismatch | Top decile at least +5pp vs bottom deciles | Top decile at least +8pp vs bottom deciles | Legal complexity should be enterprise-skewed |
| Cross-border topology | Merchants with multi-country legal spread | 20% to 45% | 25% to 40% | Keeps international tail, avoids over-global world |

| Surface | Metric | `B` target | `B+` target | Why it matters |
|---|---|---:|---:|---|
| Candidate realism | Foreign candidate count median | 5 to 15 | 7 to 12 | Prevents "almost everyone can go everywhere" |
| Candidate realism | Candidate->membership correlation | at least 0.30 | at least 0.45 | Makes candidate policy causally meaningful |
| Candidate realism | Realization ratio median | at least 0.10 | at least 0.20 | Avoids zero-realization collapse |

| Surface | Metric | `B` target | `B+` target | Why it matters |
|---|---|---:|---:|---|
| Stochastic realism | Implied `phi` CV | 0.05 to 0.20 | 0.10 to 0.30 | Restores variance heterogeneity |
| Stochastic realism | Implied `phi` P95/P05 | 1.25 to 2.0 | 1.5 to 3.0 | Prevents near-constant dispersion |
| Stochastic realism | Channel/size stratified separation in `phi` | Detectable but moderate | Clearly detectable, still stable | Makes variance profile explainable |

| Surface | Metric | `B` target | `B+` target | Why it matters |
|---|---|---:|---:|---|
| Identity semantics | Merchant-site duplicate ambiguity | Explicit semantics + low unexplained anomalies | Explicit semantics + near-zero unexplained anomalies | Prevents downstream join/feature errors |
| Auditability | Required outputs present (`s3_integerised_counts`, `s3_site_sequence`, `sparse_flag`, `merchant_abort_log`, `hurdle_stationarity_tests`) | all present | all present + monitored | Needed for defendable realism claims |

2. Hard gates for passing `B` at all
1. Single-site tier exists in material volume; no near-zero `outlet_count=1` mass.
2. Candidate set is no longer near-global by default for most merchants.
3. Implied dispersion is not near-constant; `phi` heterogeneity is restored.
4. Missing approved artifacts are emitted so realism can be audited run-over-run.

## 3) Root-Cause Trace

Below is the causality chain for each `1A` weakness, from policy/coeff/config behavior to observed statistical posture, including downstream propagation risk.

1. No single-site merchants (population base-tier missing)
- Likely mechanism:
the outlet-count generation path is effectively constrained to multi-site support, with no explicit mass at `outlet_count=1`.
- Evidence linkage:
observed `min(outlets_per_merchant)=2` and effectively universal `single_vs_multi_flag=True`.
- Root-cause class:
policy/generation constraint, not sampling noise.
- Downstream impact:
biases `2A/2B` topology and all later concentration surfaces toward chain-like behavior.

2. Near-global candidate sets (`median ~38/39`)
- Likely mechanism:
`S3` candidate policy admits almost every country for most merchants, with weak region/size gating.
- Evidence linkage:
candidate breadth near saturation.
- Root-cause class:
policy envelope too permissive in candidate space.
- Downstream impact:
forces later stages to suppress realization, reducing interpretability of cross-border behavior.

3. Weak candidate->membership coupling
- Likely mechanism:
`S6` membership realization is controlled by hurdle/gate logic that is weakly coupled to candidate breadth quality.
- Evidence linkage:
low candidate-to-membership correlation and near-zero median realization ratio.
- Root-cause class:
cross-state coupling weakness between `S3` (can expand) and `S6` (does expand).
- Downstream impact:
cross-border assignment looks disconnected from candidate logic, weakening explainability.

4. Elevated and broad `home != legal` mismatch
- Likely mechanism:
domicile/legal assignment rules are too permissive across all merchant-size strata instead of enterprise-skewed.
- Evidence linkage:
high mismatch share (~38.6%) appears across size buckets, not only large/global merchants.
- Root-cause class:
missing or weak size-stratified policy.
- Downstream impact:
distorts legal-country semantics used in geography-sensitive downstream analytics.

5. Merchant-site duplicate semantics ambiguity
- Likely mechanism:
`site_id` appears reused as a per-merchant index across legal-country records, but this contract is not strongly enforced/documented for consumers.
- Evidence linkage:
material duplicate merchant-site exposure with cross-country reuse patterns.
- Root-cause class:
identity contract ambiguity.
- Downstream impact:
silent join/feature interpretation risk where pipelines assume globally unique physical-site identity.

6. Dispersion realism weakness (implied `phi` near-constant)
- Likely mechanism:
`nb_dispersion_coefficients.yaml` (`beta_phi`) contributes almost no merchant-level heterogeneity:
MCC spread tiny, channel terms near-identical, `ln(GDP)` slope near-zero.
- Evidence linkage:
implied `phi` tightly concentrated around ~12 with very low spread metrics (`CV`, `P95/P05` near-flat).
- Root-cause class:
coefficient authoring/training objective over-weighted toward stability corridor and under-weighted toward heterogeneity realism.
- Downstream impact:
count variance appears over-regular even when mean structure varies.

7. Missing approved artifacts reduce verifiability
- Likely mechanism:
approved outputs (`s3_integerised_counts`, `s3_site_sequence`, `sparse_flag`, `merchant_abort_log`, `hurdle_stationarity_tests`) are not emitted in assessed output set.
- Evidence linkage:
presence audit in published assessment.
- Root-cause class:
implementation completeness gap in output contract.
- Downstream impact:
realism properties cannot be fully certified run-over-run.

8. Cross-weakness interaction (why posture appears broad but incoherent)
- Candidate space is over-open (`S3`) while realization coupling is weak (`S6`), creating an "open then suppress" generator shape.
- Dispersion is near-constant, so stochastic variation that could mask suppression artifacts is absent.
- Missing single-site tier removes the base population that would anchor realism.
- Result:
operationally coherent output, but statistically over-globalized and under-heterogeneous.

9. Root-cause priority (highest leverage first)
1. Missing single-site mass in count-generation policy.
2. Over-broad candidate policy with weak region/size constraints.
3. Under-heterogeneous NB dispersion coefficient block.
4. Insufficient size-stratified home/legal assignment logic.
5. Site identity semantics ambiguity.
6. Missing approved audit outputs.

## 4) Remediation Options (Ranked + Tradeoffs)

1. Option A (Recommended): Structural realism bundle (`S3 + count-shape + dispersion + identity contract`)
- What changes:
  - Add explicit single-site mass in outlet count generation.
  - Constrain candidate breadth by merchant size and region tiers.
  - Refit/re-author `beta_phi` to add controlled heterogeneity.
  - Enforce and document site identity semantics (`site_id` contract).
  - Add size-stratified home/legal mismatch policy.
- Why ranked #1:
  - It attacks the largest realism defects together and resolves their interactions, rather than patching one symptom at a time.
  - It has the highest probability of moving `1A` into stable `B+`.
- Tradeoffs:
  - Highest design and calibration effort.
  - Requires coordinated policy and coefficient updates.
  - Needs tighter validation to avoid over-correction or instability.

2. Option B: Candidate-first correction (`S3/S6` realignment)
- What changes:
  - Reduce default candidate breadth.
  - Introduce candidate quality weighting tied to geography/economic affinity.
  - Increase coupling between `S3` candidate structure and `S6` realization.
- Why ranked #2:
  - Quickly removes "near-global by default" posture and improves cross-border explainability.
- Tradeoffs:
  - Does not fix missing single-site base tier.
  - Does not fix dispersion heterogeneity weakness.
  - Can still leave segment below `B+`.

3. Option C: Dispersion-only repair (`beta_phi` modernization)
- What changes:
  - Recalibrate NB dispersion coefficients with meaningful MCC/channel/GDP spread and bounded tails.
- Why ranked #3:
  - High leverage on stochastic realism and downstream variance texture.
- Tradeoffs:
  - Structural/geographic realism defects remain.
  - Improves statistical texture but not world-topology realism.

4. Option D: Base-tier correction only (single-site insertion)
- What changes:
  - Add mass at `outlet_count=1` and reshape lower-tail merchant pyramid.
- Why ranked #4:
  - Fast correction of the most visible realism defect.
- Tradeoffs:
  - Candidate breadth, domicile mismatch, and dispersion remain weak.
  - Likely partial uplift only (typically `B` ceiling).

5. Option E: Identity-contract hardening only (`site_id` semantics + dedupe behavior)
- What changes:
  - Explicitly define `site_id` uniqueness semantics and enforce in outputs.
- Why ranked #5:
  - Reduces downstream join/feature ambiguity and interpretation risk.
- Tradeoffs:
  - Mostly correctness and interpretability gain; limited direct statistical grade lift.

6. Option F: Audit-completeness patch only (emit missing approved artifacts)
- What changes:
  - Ensure approved-but-missing outputs are emitted each run.
- Why ranked #6:
  - Required for certifiability and traceability.
- Tradeoffs:
  - Minimal direct effect on realism shape if done alone.

7. Recommended package and sequencing
1. `A1` Count-shape correction plus explicit single-site tier.
2. `A2` Candidate breadth regionalization plus `S6` realization coupling.
3. `A3` Home/legal mismatch stratification by size/global profile.
4. `A4` Dispersion heterogeneity upgrade (`beta_phi`).
5. `A5` Identity contract hardening and audit-artifact completion.

8. Expected grade movement by option
- Option A bundle:
most likely path to stable `B+` if validation bands pass.
- Option B only:
typically low `B` to `B`.
- Option C only:
typically low `B` to `B`.
- Option D only:
typically around `B`.
- Option E/F only:
governance uplift with limited realism-grade movement.

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

## 6) Validation Tests + Thresholds

## 7) Expected Grade Lift (Local + Downstream Impact)
