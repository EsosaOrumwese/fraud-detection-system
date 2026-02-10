# Segment 2A Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 2A toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness
This section records the measured realism blockers from `segment_2A_published_report.md` for Segment 2A.

### 1.1 Core realism failure: country-level timezone support is collapsed
Measured evidence:
1. Country tzid-count support is highly compressed: **54 of 77 countries** have exactly 1 tzid and the remaining countries mostly have 2.
2. Country top-1 tzid dominance is near-monolithic (median top-1 share is near 1.00).
3. Entropy and top1-top2 diagnostics show many countries operating in near-zero diversity mode.

Why this blocks `B/B+`:
1. A stronger synthetic posture should show broader within-country tz support for eligible geographies.
2. The current one-hot-like country->tz assignment is too rigid for realism-grade claims.

### 1.2 High-severity representativeness failure: tzids are often correct for the point, but points are not country-representative
Measured examples highlighted in the analytical report:
1. **NL** sites concentrated around Caribbean coordinates and mapped to `America/Kralendijk`.
2. **NO** sites concentrated at Svalbard latitude and mapped to `Arctic/Longyearbyen`.
3. **US** sites almost entirely mapped to `America/Phoenix`.
4. **CN** and **BR** include border-adjacent/outlier timezone outcomes inconsistent with broad national spread.

Why this matters:
1. 2A mapping logic can remain technically correct while still producing unrealistic national timezone posture.
2. Downstream temporal behavior then inherits this geographic compression.

### 1.3 Upstream-coupled weakness: 2A realism is constrained by 1B site-location collapse
Evidence:
1. 2A structural integrity is clean (1:1 coverage from `site_locations` to `s1_tz_lookup` to `site_timezones`).
2. Override and nudge activity is minimal in this run, so they are not primary distribution drivers.
3. Country spatial spread diagnostics indicate concentrated point clouds in many countries.

Interpretation:
1. Most realism weakness observed in 2A is inherited from upstream spatial generation shape.
2. 2A is surfacing that weakness clearly rather than introducing it.

### 1.4 Secondary governance weakness: S1 ambiguity fallback can hide location-quality defects
Observed implementation posture:
1. Unresolved S1 ambiguity can use nearest same-country polygon fallback instead of hard-failing.
2. This improves run continuity but may mask poor spatial placement if fallback usage grows.

Current run implication:
1. Fallback appears limited in this run, but it remains a risk surface that requires explicit thresholds in validation.

### 1.5 What is not weak (boundary condition)
1. Structural contracts are strong: no PK duplication, no row-loss, legality/caching bundles PASS.
2. Segment weakness is behavioral realism and representativeness, not pipeline mechanics.

### 1.6 Section 1 conclusion
Segment 2A currently sits in a **correct-but-compressed** posture:
1. Assignment mechanics are valid and deterministic.
2. Country-level timezone diversity and representativeness are too narrow for `B/B+`.
3. Primary causal pressure is upstream spatial collapse, with a secondary governance risk from fallback semantics.

## 2) Expected Statistical Posture (B/B+)
This section defines the target statistical posture for Segment 2A after remediation.  
The objective is to preserve deterministic civil-time correctness while eliminating country-level timezone collapse for multi-timezone-eligible geographies.

### 2.1 Hard `B` gates (fail-closed)
If any hard gate below fails, Segment 2A is not certifiable at `B`.

1. **Structural integrity must remain perfect.**
   - PK duplicates in `s1_tz_lookup` and `site_timezones`: `0`.
   - 1:1 row parity: `site_locations == s1_tz_lookup == site_timezones`.
   - Validation surfaces (`tz_timetable_cache`, legality report, bundle gate) remain PASS.

2. **No collapse in multi-timezone-eligible countries.**
   - Define `C_multi`: countries with `tz_world` support for at least 2 tzids and sufficient sample size (for example `site_count >= 100`).
   - In `C_multi`, share of countries with observed `distinct_tzid_count >= 2` must be `>= 70%`.

3. **Country concentration must relax from monolithic posture.**
   - In `C_multi`, median country top-1 tz share must be `<= 0.92`.
   - In `C_multi`, median `(top1_share - top2_share)` must be `<= 0.85`.
   - In `C_multi`, median normalized tz entropy must be `>= 0.20`.

4. **Large-country representativeness must improve.**
   - Define `C_large`: high-site countries (for example top decile or `site_count >= 500`).
   - In `C_large`, at least `80%` of countries must satisfy `top1_share < 0.95`.

5. **Fallback/override governance must remain controlled.**
   - S1 nearest-polygon fallback rate should remain low (target `<= 0.05%` rows for `B`).
   - Override usage must remain sparse and explainable; no broad override-driven assignment posture unless explicitly policy-approved.

### 2.2 `B` vs `B+` target bands
| Axis | `B` target | `B+` target |
|---|---|---|
| `C_multi` countries with `distinct_tzid_count >= 2` | `>= 70%` | `>= 85%` |
| `C_multi` median top-1 tz share | `<= 0.92` | `<= 0.80` |
| `C_multi` median `(top1-top2)` gap | `<= 0.85` | `<= 0.65` |
| `C_multi` median normalized tz entropy | `>= 0.20` | `>= 0.35` |
| `C_large` share with `top1_share < 0.95` | `>= 80%` | `>= 95%` |
| S1 fallback rate (row-level) | `<= 0.05%` | `<= 0.01%` |
| Structural parity / legality bundle | PASS required | PASS required |

### 2.3 Expected coupling posture with upstream 1B
2A realism should show a positive coupling with spatial diversity after remediation:
1. Countries with broader site spatial spread should generally show broader tzid support.
2. Higher site-count countries should not remain one-tz collapsed unless topology truly supports only one tzid.
3. Territory-like or border-adjacent timezone dominance in high-volume countries should become rare, explicit, and explainable.

### 2.4 Cross-seed stability gates
Required seeds: `{42, 7, 101, 202}`.

1. All hard `B` gates must pass on all required seeds.
2. Cross-seed CV for key medians (top-1 share, entropy, `distinct_tzid_count` coverage):
   - `B`: `<= 0.30`
   - `B+`: `<= 0.20`
3. No seed-specific collapse mode is allowed (for example one seed reverting to one-tz country collapse while others pass).

### 2.5 Interpretation of expected posture
For Segment 2A, `B/B+` means:
1. Civil-time assignment remains deterministic, reproducible, and contract-correct.
2. Country-level timezone assignment no longer behaves as a compressed one-hot map for multi-tz-eligible geographies.
3. Validation evidence is stable across seeds and robust against shallow-run false confidence.

## 3) Root-Cause Trace
This section traces each 2A realism weakness to concrete mechanisms and ownership surfaces, so remediation targets causes rather than symptoms.

### 3.1 Root-cause map (weakness -> mechanism -> locus)
| Weakness | Immediate mechanism | Primary locus | Secondary locus |
|---|---|---|---|
| Country tzid support collapse (many countries at 1 tzid) | Site coordinates within many countries are generated in tight local bands, so deterministic polygon lookup repeatedly resolves to one dominant tzid | **Upstream 1B spatial generation** | 2A propagation |
| Non-representative country->tz outcomes (for example NL->Kralendijk, NO->Longyearbyen) | Legal-country labels and coordinate support are weakly aligned to mainland representativeness; concentrated points land in remote/territory polygons | **Upstream location priors / geometry sampling** | 2A overrides too sparse to correct |
| High top-1 share and low entropy in multi-tz-eligible countries | Low intra-country geographic dispersion yields low timezone dispersion by construction | **Upstream 1B** | 2A has no diversity synthesis stage |
| Governance risk from fallback behavior | Nearest same-country polygon fallback can continue runs where fail-closed would stop | **2A S1 implementation choice** | Validation lacks strict fallback budget gate |

### 3.2 What 2A is doing correctly (not the realism bottleneck)
1. Structural chain is clean: `site_locations -> s1_tz_lookup -> site_timezones` remains 1:1.
2. PK integrity is preserved.
3. Cache, legality report, and validation bundle are PASS.
4. Nudge and override usage are minimal in the observed run.

Interpretation:
1. Mechanical correctness is strong.
2. The main issue is statistical representativeness, not pipeline breakage.

### 3.3 Primary cause: upstream spatial collapse drives downstream timezone collapse
Evidence-linked mechanism:
1. Many countries show very small lat/lon spread despite meaningful site counts.
2. 2A assignment is deterministic point-in-polygon.
3. Narrow coordinate support therefore maps to narrow tz support.
4. Low entropy and high top-1 dominance are expected outcomes under this geometry.

Bounded conclusion:
1. 2A cannot create timezone diversity from geographically collapsed inputs.
2. Primary realism remediation must include upstream spatial broadening.

### 3.4 Secondary cause: representativeness gap in country placement priors
Observed pattern:
1. Some high-impact country outputs are dominated by territory-like or border-adjacent tzids.
2. These outputs are geometrically valid for the sampled points but not representative of broad national posture.

Causal implication:
1. This is a placement-prior issue rather than a timezone-mapping algorithm defect.
2. Remediation requires improved country-level sampling priors in upstream generation, plus selective 2A safeguards.

### 3.5 Tertiary cause: continuity-first fallback can hide upstream quality defects
Current S1 posture:
1. Ambiguity can resolve via nearest same-country polygon fallback instead of hard fail.
2. This improves continuity and deterministic completion.

Risk posture:
1. If fallback frequency rises, realism can drift without obvious hard failures.
2. Therefore fallback requires explicit quantitative guardrails in validation.

### 3.6 Responsibility split (to prevent mis-targeted remediation)
1. **Upstream 1B owner surface:**
   - increase intra-country spatial diversity,
   - enforce country-representative location priors,
   - reduce single-band/single-tile concentration artifacts.
2. **2A owner surface:**
   - preserve deterministic assignment correctness,
   - enforce provenance and legality contracts,
   - add fallback governance and targeted override controls for pathological pairings.
3. **Validation owner surface (2A realism gates):**
   - enforce concentration/entropy thresholds on eligible country cohorts,
   - enforce fallback-rate budgets and seed-stability criteria.

### 3.7 Root-cause conclusion
Segment 2A misses `B/B+` mainly due to input-geometry realism deficits, not assignment logic defects:
1. upstream spatial collapse causes timezone support collapse,
2. weak representativeness priors cause implausible country->tz outcomes,
3. fallback semantics add a governance risk if not explicitly budgeted.

This makes remediation direction clear: upstream spatial fixes are primary; 2A should add guardrails and targeted controls rather than synthetic post-hoc diversification.

## 4) Remediation Options (Ranked + Tradeoffs)

This section ranks remediation options by causal power, statistical lift, and operational risk.  
The ranking follows the root-cause trace in Section 3: upstream spatial representativeness is primary; 2A guardrails are secondary but mandatory.

| Rank | Option | What changes | Expected impact on 2A realism | Tradeoffs / risks |
|---|---|---|---|---|
| 1 | Upstream representativeness fix in 1B (primary) | Rework country-level site coordinate generation so multi-timezone countries get geographically representative spread instead of narrow bands and territory-heavy clusters. | Largest lift on `distinct_tzid_count`, top-1 share, and entropy. Directly addresses the primary cause in Section 3. | Highest implementation effort; affects downstream segments and requires re-baselining. |
| 2 | 2A assignment governance gates (fallback/override budgets) | Add strict quantitative caps and fail-closed behavior for fallback and override usage. | Prevents silent realism drift and turns quality regressions into explicit run failures. | Can increase short-term run failures until upstream is fixed. |
| 3 | Country-risk watchlist with deterministic corrective controls | For known pathological country->tz outcomes in high-volume countries, apply deterministic policy constraints or mandatory review path. | Fast reduction of worst anomalies; improves high-impact countries early. | If overused, becomes patchwork and can hide upstream defects. |
| 4 | Eligibility-aware realism scoring in 2A validation | Score realism on eligible cohorts (`C_multi`) and enforce B/B+ thresholds there; keep single-tz countries as a separate cohort. | Improves statistical fairness of acceptance decisions and avoids false pass/fail from mixed cohorts. | Requires strict cohort definitions and stable seed handling. |
| 5 | Post-assignment redistribution layer (temporary only) | Add rebalance after tz assignment to force distributional targets. | Can quickly improve headline metrics. | Weak causal integrity; risks synthetic artifacts and lower explainability. Should be temporary only. |

### 4.1 Recommended path for B/B+ with causal integrity
1. Use `Option 1 + Option 2` as the core bundle.
2. Use `Option 3` only for tightly scoped high-impact anomalies while upstream fixes mature.
3. Keep `Option 4` as the permanent validation architecture.
4. Avoid `Option 5` unless time-boxed as a temporary bridge with explicit retirement criteria.

### 4.2 Why this ranking is statistically defensible
1. Section 3 shows 2A collapse is mostly input-geometry induced; therefore the highest-ranked fix must change input representativeness, not assignment output cosmetics.
2. Governance gates are ranked second because they preserve diagnosis fidelity; without them, runs can continue in degraded statistical posture.
3. Watchlist controls are useful for rapid risk reduction but should never substitute for upstream distribution correction.
4. Cohort-aware scoring prevents grade inflation and ensures improvements are measured on countries where timezone diversity is expected.
5. Forced redistribution is intentionally last because it improves metrics without fully repairing underlying causal structure.

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

For Segment 2A, the chosen fix is a causal bundle with primary lift in upstream 1B and governance hardening in 2A.  
The intent is to improve timezone realism without introducing post-hoc synthetic redistribution artifacts.

### 5.1 Must-do fix bundle
1. Upstream 1B representativeness policy upgrade (primary driver)
- Target files (policy surfaces):
  - `config/layer1/1B/policy/site_location_policy_v*.json` (or equivalent active 1B location policy)
  - Country prior tables consumed by 1B site generation
- Exact deltas:
  - Add per-country representativeness profile fields:
    - `mainland_weight`
    - `territory_weight_cap`
    - `min_spatial_dispersion_km`
    - `max_single_tile_share`
  - Add multi-timezone eligibility guard:
    - For countries in `C_multi`, require support across at least 2 timezone-relevant geographic bands.
  - Keep deterministic replay behavior:
    - deterministic seeded mixture sampling, no non-reproducible random path.
- Statistical role:
  - This is the only fix that can causally widen country tz support without cosmetic redistribution in 2A.

2. 2A fallback governance hardening
- Target files:
  - `packages/engine/src/engine/layers/l1/seg_2A/s1_tz_lookup/runner.py` (or equivalent 2A lookup runner)
  - `config/layer1/2A/policy/tz_lookup_policy_v*.json`
- Exact deltas:
  - Add hard-fail threshold:
    - `fallback_rate_hard_cap` (for example `<= 0.0005` for B, `<= 0.0001` for B+).
  - Add localized budget:
    - `fallback_country_cap` to prevent concentrated degradation.
  - Emit explicit counters:
    - `fallback_count`
    - `fallback_rate`
    - `fallback_by_country`
- Statistical role:
  - Prevents continuity-first fallback from hiding geography or boundary-quality defects.

3. 2A override governance normalization
- Target files:
  - `config/layer1/2A/policy/timezone_overrides_v*.json`
  - Override application logic in 2A S1/S2 stages
- Exact deltas:
  - Add strict override metadata:
    - `reason_code`
    - `owner`
    - `expiry_run_or_date`
  - Add hard cap:
    - `override_rate_hard_cap`
  - Prohibit broad wildcard override patterns unless explicitly approved.
- Statistical role:
  - Keeps overrides surgical and auditable rather than latent distribution-shaping controls.

4. 2A cohort-aware realism scorer
- Target files:
  - `packages/engine/src/engine/layers/l1/seg_2A/validation/runner.py` (or equivalent realism diagnostics stage)
- Exact deltas:
  - Define scoring cohorts:
    - `C_single` (single-tz expected)
    - `C_multi` (multi-tz expected, sample-size eligible)
  - Compute and gate metrics on `C_multi`:
    - share with `distinct_tzid_count >= 2`
    - median top-1 share
    - median `(top1-top2)` gap
    - median normalized entropy
  - Keep structural integrity checks global and mandatory.
- Statistical role:
  - Prevents mixed-cohort grade inflation and makes B/B+ acceptance criteria meaningful.

### 5.2 Supporting fixes (after must-do bundle)
1. Country-risk watchlist constraints
- Add bounded controls for a small set of known high-impact country->tz failure patterns.
- Guardrail: watchlist remains narrow and evidence-backed; no broad rebalancing.

2. Validation seed-pack standardization
- Enforce certification seed set: `{42, 7, 101, 202}`.
- Require all hard gates to pass across all seeds before grading at B/B+.

### 5.3 Rejected primary alternative
1. Post-assignment timezone rebalance in 2A is explicitly not chosen as primary remediation.
- Reason:
  - It can improve headline metrics quickly but weakens causal traceability.
  - It increases risk of synthetic artifacts and lowers explainability.
- Allowed only as emergency, time-boxed bridge with explicit retirement criteria.

### 5.4 Implementation order (to avoid false diagnostics)
1. Patch 1B representativeness policy and generation behavior first.
2. Patch 2A fallback and override governance next.
3. Add cohort-aware scoring and hard realism gates.
4. Re-run 1B->2A on multi-seed protocol and evaluate against Section 2 thresholds.

## 6) Validation Tests + Thresholds

This section defines the certification protocol for Segment 2A after remediation.  
The protocol is fail-closed and seed-stable: a single hard-gate failure means no B/B+ certification.

### 6.1 Certification scope
1. Evaluate using required seeds: `{42, 7, 101, 202}`.
2. Use full realism runs, not smoke/plumbing-only runs.
3. Segment is certifiable only when all hard gates pass on all required seeds.

### 6.2 Hard fail gates (`B` minimum)
1. Structural integrity
- `site_locations == s1_tz_lookup == site_timezones` row parity must hold.
- PK duplicates in `s1_tz_lookup` and `site_timezones` must be `0`.
- Legality/cache/validation bundle must remain PASS.
- Fail condition: any violation.

2. Fallback and override governance
- `fallback_rate <= 0.05%` for `B`; `<= 0.01%` for `B+`.
- `override_rate <= 0.20%` for `B`; `<= 0.05%` for `B+`, unless explicit approved exception.
- No single country may exceed `fallback_country_cap`:
  - recommended `<= 0.10%` in-country rows for `B`
  - recommended `<= 0.03%` in-country rows for `B+`.
- Fail condition: any cap breach.

3. Multi-timezone cohort realism (`C_multi`)
- Share of countries with `distinct_tzid_count >= 2`:
  - `>= 70%` for `B`
  - `>= 85%` for `B+`.
- Median top-1 tz share:
  - `<= 0.92` for `B`
  - `<= 0.80` for `B+`.
- Median `(top1_share - top2_share)` gap:
  - `<= 0.85` for `B`
  - `<= 0.65` for `B+`.
- Median normalized tz entropy:
  - `>= 0.20` for `B`
  - `>= 0.35` for `B+`.
- Fail condition: any metric below `B` threshold.

4. Large-country representativeness (`C_large`)
- Share of countries with `top1_share < 0.95`:
  - `>= 80%` for `B`
  - `>= 95%` for `B+`.
- Fail condition: threshold miss.

### 6.3 Required diagnostics (must be reported even if gates pass)
1. Country-level diagnostic table
- Per country report:
  - `site_count`
  - `distinct_tzid_count`
  - `top1_share`
  - `top1_top2_gap`
  - `entropy`
  - `fallback_count/rate`
  - `override_count/rate`.
- Purpose: hotspot tracing and auditability.

2. Country x tzid share matrix (top countries, top tzids, plus `OTHER`)
- Purpose: detect hidden territory-dominant or border-driven assignment artifacts.

3. Cross-seed stability diagnostics
- Compute CV across seeds for:
  - median top-1 share
  - median top1-top2 gap
  - median entropy
  - share with `distinct_tzid_count >= 2`.
- Acceptance:
  - CV `<= 0.30` for `B`
  - CV `<= 0.20` for `B+`.

4. Coupling check with upstream spatial spread
- Compute Spearman correlation between country spatial-dispersion proxy (from 1B) and timezone-diversity proxy (from 2A).
- Expected:
  - `rho > 0.15` for `B`
  - `rho > 0.25` for `B+`.
- Purpose: verify the improvement is causally aligned with upstream spatial realism.

### 6.4 Statistical test protocol (pre vs post remediation)
1. Distribution shift on country concentration metrics
- Apply KS or Wasserstein distance on country-level `top1_share` and entropy distributions.
- Acceptance:
  - directional shift toward target bands with effect size reported (not p-value only).

2. Cohort proportion improvement
- Two-proportion z-test on share of `C_multi` countries with `distinct_tzid_count >= 2` (`pre` vs `post`).
- Acceptance:
  - statistically credible increase and practical lift (`>= +10 pp` toward B trajectory).

3. Concentration reduction
- Compute inequality metric (for example Gini) on country top-1 shares.
- Acceptance:
  - reduction versus baseline with no structural regressions.

### 6.5 Required evidence artifacts per run
1. Machine-readable metrics JSON with gate values and pass/fail flags.
2. Country diagnostics CSV for `C_multi`, `C_large`, and flagged exceptions.
3. Fallback/override audit extract with reason codes and owners.
4. Seed comparison summary with CV metrics.
5. One-line certification verdict:
- `PASS_BPLUS`, `PASS_B`, or `FAIL`, with explicit failing gates when applicable.

### 6.6 Fail-closed certification rule
1. If any hard gate fails on any required seed, verdict is `FAIL`.
2. No manual downgrade/waiver to `B` without explicit exception approval and rerun evidence.
3. If structural integrity passes but realism gates fail, verdict is `FAIL_REALISM` (not PASS).

## 7) Expected Grade Lift (Local + Downstream Impact)

### 7.1 Current vs target
1. Current 2A posture is below B due to country-level timezone collapse and representativeness defects, despite strong structural correctness.
2. With the chosen remediation bundle in Sections 4-6, target is:
- minimum: `B`
- expected with stable cross-seed behavior: `B+`.

### 7.2 Local lift expectation for 2A
1. Coverage lift (`C_multi` countries with `distinct_tzid_count >= 2`)
- Expected movement: from compressed regime to `>= 70%` (`B`) and stretch to `>= 85%` (`B+`).

2. Concentration lift (top-1 dominance)
- Median top-1 share expected to relax into `<= 0.92` (`B`) and toward `<= 0.80` (`B+`).
- Top1-top2 gaps expected to contract toward `<= 0.85` (`B`) and `<= 0.65` (`B+`).

3. Entropy lift
- Median normalized entropy expected to rise to `>= 0.20` (`B`) and toward `>= 0.35` (`B+`), especially in large multi-timezone countries.

4. Governance lift
- Fallback and override behavior becomes explicitly bounded and auditable.
- This improves not only grade prospects but also trust in certification outcomes.

### 7.3 Confidence levels by remediation stage
1. After 2A-only governance changes (without 1B representativeness fix):
- Likely ceiling: `C+/B-`.
- Reason: auditability improves but primary compression mechanism remains.

2. After upstream 1B representativeness plus 2A governance bundle:
- Likely result: `B` to `B+`.
- Reason: this is the first stage that changes the causal input geometry driving timezone diversity.

3. After seed-stable evidence across required seed pack:
- Certifiable result: `B+` if all hard and stability gates pass.

### 7.4 Downstream impact (why 2A lift matters beyond 2A)
1. Segment 3A / 3B temporal realism
- Improved country->tz posture improves local hour/day realism and reduces civil-time distortion inherited downstream.

2. Segment 5A / 5B allocation and arrival realism
- More plausible timezone diversity supports more realistic geographic-temporal dispersion in allocation and arrivals.

3. Segment 6A / 6B fraud and case realism
- Cross-border and campaign timing diagnostics become less biased by unrealistic timezone concentration, improving interpretability of fraud-vs-legit temporal signals.

### 7.5 Residual risk after passing B/B+
1. Small countries with low site counts remain noisy and should be interpreted in cohort context.
2. Rare border/territory outcomes may still appear; they should remain sparse and explainable, not dominant.
3. If fallback caps are satisfied only via heavy override use, this is a hidden failure mode and should block B+ certification.

### 7.6 Grade-lift summary statement
1. Segment-local lift: below-B -> `B/B+` is achievable with the chosen causal bundle.
2. Engine-level contribution: 2A remediation removes a key upstream bottleneck affecting temporal and cross-border interpretability in downstream segments.
3. Certification condition: lift claims are valid only when Section 6 hard gates and cross-seed stability gates pass without waivers.
