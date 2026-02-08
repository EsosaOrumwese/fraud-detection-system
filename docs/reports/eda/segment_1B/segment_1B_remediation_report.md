# Segment 1B Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 1B toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness

This section captures the measured realism blockers from `segment_1B_published_report.md` for Segment 1B (`site_locations` realism surface).

### 1.1 Macro concentration is too strong for B/B+
Measured evidence:
1. Country concentration is severe (`Gini = 0.753`).
2. Top-country shares are high:
- top 1% of countries hold `13.66%` of sites
- top 5% hold `39.33%`
- top 10% hold `59.74%`
3. Top-20 ranking is heavily concentrated in a narrow country set.

Why this blocks `B/B+`:
1. A B/B+ synthetic-global posture should still show concentration, but not a dominance regime where a small country subset drives most spatial mass.
2. Current concentration makes downstream behavior overly country-template-driven.

### 1.2 Geographic coverage is imbalanced (Europe-centric, weak global breadth)
Measured evidence:
1. Lat/lon distributions show strong peaks in northern mid-latitudes and Europe/Africa longitudes.
2. Southern hemisphere coverage is visibly thinner.
3. Choropleth and country bars show sparse presence across much of Africa and South America relative to Europe/North America/Australia.

Why this blocks `B/B+`:
1. Even under synthetic policy constraints, global realism needs credible regional breadth.
2. Empty or near-empty continental zones create obvious realism breaks for human reviewers.

### 1.3 Within-country geometry shows synthetic template artifacts
Measured evidence:
1. Small-multiple country panels show narrow latitude bands, corridor-like shapes, and split clusters in several countries.
2. These shapes are too regular in places and look policy-template generated rather than emergent urban spread.

Why this blocks `B/B+`:
1. Country-level geometry should reflect mixed urban cores plus secondary spread, not repeated stripe/corridor motifs.
2. Template artifacts amplify detectability of synthetic generation rules.

### 1.4 Local clustering is plausible but statistically unbalanced
Measured evidence:
1. Nearest-neighbor distance sample shows dense local clustering (`p50 = 0.28 km`, `p90 = 1.86 km`).
2. Tail is heavy (`p99 = 11.16 km`, with very long-distance outliers).

Why this blocks `B/B+`:
1. Dense cores are good, but the current core-plus-long-tail mix suggests uneven placement priors and diffuse sparse placements.
2. The spatial process does not yet look calibrated to a stable urban plus controlled rural tail target.

### 1.5 Upstream policy-expression weakness (distributional, not structural)
Measured evidence:
1. Structural integrity is strong (row parity, no duplicate key issues, coordinate bounds valid).
2. Weaknesses are distributional (where points are placed), not mechanical correctness.

Why this blocks `B/B+`:
1. A structurally perfect pipeline can still fail realism if placement policy is not representative.
2. The current grade bottleneck is policy shape and priors, not data loss or contract failures.

### 1.6 What is not weak (boundary condition)
1. Coordinate validity is clean (no out-of-range lat/lon).
2. Pipeline parity and deterministic lineage are clean.
3. Segment is reliable for reproducibility; realism shortfall is specifically geospatial representativeness.

### 1.7 Section 1 conclusion
Segment 1B currently has a structurally sound but geographically imbalanced posture:
1. mechanics and integrity are strong,
2. country concentration and continental imbalance are too high,
3. within-country placement shapes reveal synthetic template artifacts,
4. these jointly hold 1B below B/B+ until spatial priors and allocation shape are remediated.

## 2) Expected Statistical Posture (B/B+)

This section defines the target statistical shape for Segment 1B after remediation.  
Goal: preserve deterministic, auditable spatial generation while producing geographically credible synthetic site distributions.

### 2.1 Hard `B` gates (fail-closed)
1. Structural integrity remains perfect
- Row parity across key 1B outputs must hold.
- Duplicate key rate on site identity surfaces must be `0`.
- Coordinate validity (lat/lon in legal ranges) must be `100%`.
- Bundle and validation gates must remain PASS.

2. Country concentration must relax from dominance regime
- Country-site concentration Gini must be:
  - `<= 0.68` for `B`
  - `<= 0.60` for `B+`.
- Top-country concentration limits:
  - top 10% country share `<= 50%` for `B`, `<= 42%` for `B+`
  - top 5% country share `<= 33%` for `B`, `<= 27%` for `B+`
  - top 1% country share `<= 10%` for `B`, `<= 8%` for `B+`.

3. Global coverage breadth improves materially
- Minimum active-country coverage:
  - at least `85%` of configured eligible countries must have nonzero sites for `B`
  - at least `92%` for `B+`.
- Regional floor guardrails:
  - no major region (Africa, South America, Oceania, Asia, Europe, North America) should be near-empty when eligible countries exist in that region.
- Southern-hemisphere share floor:
  - site share in southern hemisphere `>= 12%` for `B`
  - `>= 18%` for `B+`, unless scenario policy explicitly constrains this.

4. Within-country representativeness improves
- For high-site countries (`C_large`), enforce:
  - no persistent strip/corridor collapse in coordinate spread diagnostics,
  - multi-cluster support where population and urban priors imply it.
- Proxy thresholds:
  - country-level spatial dispersion (bbox or convex-hull proxy) must increase versus baseline for previously collapsed countries.
  - median nearest-neighbor distance in `C_large` remains in plausible urban range while reducing extreme tail mass.

5. Nearest-neighbor tail is controlled
- Keep dense clustering signal, but reduce extreme sparse artifacts:
  - `p50` NN distance remains low (urban clustering preserved),
  - `p99/p50` ratio must contract versus baseline by at least `20%` for `B`, `35%` for `B+`.

### 2.2 `B` vs `B+` target table
| Axis | `B` target | `B+` target |
|---|---|---|
| Country concentration Gini | `<= 0.68` | `<= 0.60` |
| Top 10% country share | `<= 50%` | `<= 42%` |
| Top 5% country share | `<= 33%` | `<= 27%` |
| Top 1% country share | `<= 10%` | `<= 8%` |
| Eligible countries with nonzero sites | `>= 85%` | `>= 92%` |
| Southern hemisphere site share | `>= 12%` | `>= 18%` |
| NN tail contraction (`p99/p50` vs baseline) | `>= 20%` better | `>= 35%` better |
| Structural parity / validity / bundles | PASS required | PASS required |

### 2.3 Coupling expectations with downstream segments
1. Segment 2A timezone realism should improve.
- As country spatial representativeness improves, country-level timezone diversity in 2A should increase for multi-timezone countries.

2. Segment 3A and 3B temporal realism should stabilize.
- Better timezone geography in 2A should reduce downstream civil-time skew artifacts.

3. Segment 5A, 5B, 6A, and 6B interpretability should improve.
- Reduced spatial bias should reduce geography-induced distortions in allocation, cross-border behavior, and fraud targeting interpretation.

### 2.4 Cross-seed stability gates
Required seeds: `{42, 7, 101, 202}`.

1. All hard `B` gates must pass on all seeds.
2. Cross-seed CV thresholds for core metrics:
- `B`: `<= 0.30`
- `B+`: `<= 0.20`.
3. No seed should revert to dominance-collapse mode (for example Gini or top-share returning near baseline failure posture).

### 2.5 Interpretation of expected posture
For Segment 1B, `B/B+` means:
1. The pipeline remains mechanically perfect and deterministic.
2. Country mass is still realistically concentrated, but no longer dominated by a narrow set of countries.
3. Coverage breadth is credible for a synthetic global narrative.
4. Within-country geometry looks population-aware rather than template-collapsed.
5. Downstream timezone and temporal realism improve for causal reasons, not post-hoc corrections.

## 3) Root-Cause Trace

This section traces each observed 1B realism weakness to concrete mechanisms and ownership surfaces, so remediation addresses causes rather than symptoms.

### 3.1 Root-cause map (weakness -> mechanism -> locus)
| Weakness | Immediate mechanism | Primary locus | Secondary locus |
|---|---|---|---|
| Excessive country concentration (`Gini` and top-k too high) | Country mass allocation priors over-weight a narrow set of countries; weak balancing constraints | **1B country allocation policy** | 1A merchant-country composition |
| Europe-centric profile and weak southern/emerging-region coverage | Regional priors and eligibility mix skew toward Europe-like footprint; insufficient regional floor constraints | **1B regional weighting policy** | Scenario-level mix assumptions |
| Within-country stripe and corridor template artifacts | Coordinate synthesis relies on narrow geometric bands or limited sub-country support points | **1B intra-country placement policy** | Tile granularity and jitter mechanics |
| Heavy nearest-neighbor tail with sparse outliers | Mix of dense clusters plus under-constrained sparse placement in low-density areas | **1B tile-weight and sampling shape** | Jitter magnitude and tail controls |
| Realism shortfall despite structural PASS | Validation emphasizes mechanics (parity and bounds) but underweights representativeness gates | **1B validation contract scope** | Segment-grade rubric |

### 3.2 What is working correctly (not the bottleneck)
1. Structural pipeline integrity is strong (row parity, deterministic lineage, no key corruption).
2. Coordinate validity is strong (lat/lon ranges are legal).
3. Reproducibility controls are functioning.

Implication:
1. Segment 1B is not failing on mechanics; it is failing on distributional realism.

### 3.3 Primary cause: country allocation priors induce dominance regime
Evidence-linked mechanism:
1. Concentration metrics (Gini and top-k shares) indicate small-country-set dominance.
2. This pattern is consistent with strong allocation priors and weak anti-concentration constraints.
3. Once country counts are fixed this way, downstream intra-country logic cannot recover global balance.

Bounded conclusion:
1. The top realism bottleneck is country-level mass policy, not coordinate jitter or minor mapping details.

### 3.4 Secondary cause: regional balancing guardrails are too weak
Evidence-linked mechanism:
1. Visible continental imbalance (thin southern hemisphere, sparse Africa and South America).
2. This indicates lack of hard regional floor constraints in allocation objectives.
3. Even globally eligible scenarios can collapse into a narrow regional footprint without explicit guardrails.

Bounded conclusion:
1. Regional coverage defects are policy-structural, not random noise.

### 3.5 Tertiary cause: intra-country placement templates are too rigid
Evidence-linked mechanism:
1. Small-multiple plots show recurring narrow-band and split-corridor geometries.
2. That is typical when placement kernels are simplistic (few anchors or bands) relative to country complexity.
3. Resulting shapes look synthetic even when coordinates remain technically valid.

Bounded conclusion:
1. Intra-country representativeness needs richer multi-cluster kernels and stronger dispersion controls.

### 3.6 Quaternary cause: realism validation under-specifies representativeness
Evidence-linked mechanism:
1. Current segment PASS surfaces confirm structural correctness.
2. Realism defects still persisted to published output, so representativeness thresholds were not binding.
3. Without hard concentration and coverage gates, low-realism outputs can pass operational checks.

Bounded conclusion:
1. Validation must include explicit statistical realism gates, not only mechanical checks.

### 3.7 Responsibility split (to avoid mis-targeted fixes)
1. 1B policy owner surface
- Country mass priors
- Regional balancing constraints
- Intra-country placement kernels
- Tail controls for sparse placement

2. 1B implementation owner surface
- Faithful execution of policy shape
- Deterministic seeded sampling and provenance
- Metric emission for realism diagnostics

3. Validation owner surface
- Hard gates for concentration and coverage
- Cross-seed stability criteria
- Explicit fail-closed rules for realism threshold breaches

4. Upstream influence (non-primary)
- 1A merchant-country composition can amplify concentration, but 1B is still responsible for preventing extreme spatial collapse.

### 3.8 Root-cause conclusion
Segment 1B misses `B/B+` mainly because representativeness controls are too weak at the allocation-policy layer:
1. country-level mass is over-concentrated,
2. regional breadth lacks hard balancing floors,
3. intra-country placement kernels generate synthetic-looking geometry motifs,
4. realism thresholds are not yet enforced as hard validation gates.

This establishes remediation direction: strengthen 1B allocation and placement policy first, then harden realism validation so these failures cannot silently recur.

## 4) Remediation Options (Ranked + Tradeoffs)

Below is the ranked option set for 1B, ordered by expected impact on failing realism axes (`country concentration`, `regional breadth`, `within-country geometry`, `nearest-neighbor tail`) and by downstream leverage into `2A+`.

### Rank 1: Rebuild country allocation as a constrained sampler (highest impact)
1. Change:
- Replace raw country priors with a constrained draw that enforces:
- concentration-cap constraints (`Gini`, top-k share ceilings),
- minimum-breadth constraints (active-country floor and region-floor mass).
2. Why it ranks first:
- Most of 1B failure is macro-allocation shape; this directly attacks the largest error source.
3. Expected gain:
- Immediate movement on concentration and global coverage targets.
- Prevents few-country dominance from propagating downstream.
4. Tradeoffs:
- Hard constraints can feel less organic if set too tightly.
- Requires careful seed-stability tuning so runs do not become boundary-brittle.

### Rank 2: Add region-level balancing layer above country priors
1. Change:
- Use two-stage allocation:
- allocate mass by macro-region to target bands,
- then allocate countries within each region.
2. Why it ranks second:
- Fixes Europe-heavy collapse and southern/emerging under-coverage without overfitting country-level knobs.
3. Expected gain:
- Better continental realism and stronger global narrative plausibility.
4. Tradeoffs:
- Slight increase in policy complexity.
- If region bands are too rigid, output can look engineered rather than emergent.

### Rank 3: Replace rigid intra-country templates with mixture-of-kernels
1. Change:
- Move from stripe/corridor-like placement to a mixture:
- dense urban cores,
- secondary city clusters,
- controlled rural/sparse tail.
2. Why it ranks third:
- Directly targets the visible geometric artifacts in country panels.
3. Expected gain:
- Better micro-shape realism and less template repetition.
4. Tradeoffs:
- More parameters to calibrate per country class.
- Added diagnostic burden to prevent overfitting shape controls.

### Rank 4: Tail calibrator for nearest-neighbor distance (anti-pathology control)
1. Change:
- Add post-draw tail calibration guardrails for nearest-neighbor distance:
- cap pathological ultra-sparse tail mass,
- preserve realistic urban clustering.
2. Why it ranks fourth:
- Useful cleanup after macro-allocation and kernel fixes.
3. Expected gain:
- Reduces outlier-heavy sparse behavior that looks synthetic.
4. Tradeoffs:
- If overused, can flatten legitimate heterogeneity.
- Must be monitored so it does not hide upstream sampling defects.

### Rank 5: Upstream coupling control from 1A into 1B (stability option)
1. Change:
- Limit amplification from 1A merchant-country composition into 1B concentration.
- Add coupling limits or a reweighting bridge for stability.
2. Why it ranks fifth:
- Not primary root cause, but can reintroduce concentration drift if untreated.
3. Expected gain:
- Better cross-seed and cross-run stability of 1B realism.
4. Tradeoffs:
- Added coupling logic between segments.
- Requires clear ownership boundaries so 1A and 1B responsibilities do not blur.

### Rank 6: Upgrade validation from PASS mechanics to PASS realism gates
1. Change:
- Promote concentration, coverage, and shape diagnostics to fail-closed realism gates.
2. Why it ranks sixth:
- Does not fix generation directly, but prevents regression and false green states.
3. Expected gain:
- Sustained quality and auditable acceptance criteria.
4. Tradeoffs:
- More failed runs during tuning windows.
- Requires threshold governance and exception discipline.

### Recommended package for `B/B+`
1. Minimum high-confidence package:
- Rank 1 + Rank 2 + Rank 3 + Rank 6.
2. Optional hardening:
- Add Rank 4 for additional tail cleanup.
- Add Rank 5 only if 1A-driven drift remains after first rerun.

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

For Segment 1B, the chosen fix is a coordinated `S2 + S4 + S6 + S9` bundle with contract updates.  
This is the smallest implementation set that can move concentration and geometry realism without breaking deterministic replay.

### 5.1 Policy delta: upgrade S2 from single-basis weighting to constrained blended weighting
File to update:
1. `config/layer1/1B/policy/policy.s2.tile_weights.yaml`

Current posture:
1. Policy only carries `basis`, `dp`, and minimal metadata.
2. Weight construction is under-parameterized for concentration and regional breadth control.

Chosen delta:
1. Keep existing keys for backward compatibility.
2. Add a new policy block `blend_v2` with:
- `enabled: true`
- `basis_mix`:
- `uniform`
- `area_m2`
- `population`
- `region_floor_share` (per macro region)
- `country_cap_share_soft` and `country_cap_share_hard`
- `topk_cap_targets` (`top1`, `top5`, `top10`)
- `concentration_penalty_strength`
- `deterministic_seed_namespace`
3. Add `fallback_mode: legacy_basis_only` when `blend_v2.enabled` is false.

Expected effect:
1. Prevents pure prior-driven collapse into a few dominant countries.
2. Gives explicit policy levers for B/B+ concentration bands.

### 5.2 Runner delta: implement constrained deterministic rebalance in S2
File to update:
1. `packages/engine/src/engine/layers/l1/seg_1B/s2_tile_weights/runner.py`

Current posture:
1. Computes normalized tile weights from one basis stream.
2. No balancing pass for region floors or concentration caps.

Chosen delta:
1. Add a two-pass algorithm:
- Pass A: compute raw tile mass from `basis_mix`.
- Pass B: constrained rebalance loop:
- enforce region floors first,
- enforce country soft/hard caps second,
- apply concentration penalty until convergence or max iterations.
2. Preserve deterministic ordering and seeded behavior so replay remains stable.
3. Emit diagnostics sidecar metrics (for validation consumption):
- `country_share_topk`
- `country_gini_proxy`
- `region_share_vector`.

Expected effect:
1. Changes macro mass shape where current report shows strongest realism failure.
2. Reduces concentration without random instability.

### 5.3 Allocation delta: enforce anti-collapse in S4 assignment step
File to update:
1. `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py`

Current posture:
1. Alloc plan follows requirements and S2 weights but has no explicit anti-collapse controls.
2. Re-concentration can reappear during integer assignment.

Chosen delta:
1. Add assignment-time guardrails:
- `country_share_soft_guard` during running allocation,
- reroute marginal assignments to next eligible tile when guard breached,
- retain deterministic tie-breaking key.
2. Add bounded residual redistribution at end of assignment:
- fill deficits in under-floor regions,
- then normalize remainder by weighted priority.

Expected effect:
1. Keeps S2 realism gains from being undone during discrete allocation.
2. Improves country coverage breadth in final assigned tile counts.

### 5.4 Jitter delta: replace uniform-in-cell synthesis with policy-driven mixture jitter
File to update:
1. `packages/engine/src/engine/layers/l1/seg_1B/s6_site_jitter/runner.py`

Current posture:
1. Predominantly uniform-in-tile jitter.
2. Produces template-like stripe/corridor motifs in some countries.

Chosen delta:
1. Introduce `jitter_policy_v2` mode:
- `core_cluster_component` (urban center pull),
- `secondary_cluster_component`,
- `sparse_tail_component` (bounded probability),
- per-country-class parameter defaults.
2. Keep point-in-country validity checks and deterministic retry order.
3. Add hard clamp to prevent pathological far-tail draws.

Expected effect:
1. Reduces repeated geometric motifs and improves within-country realism.
2. Contracts nearest-neighbor extreme tail while preserving dense cores.

### 5.5 Validation delta: promote realism checks to fail-closed gates in S9
File to update:
1. `packages/engine/src/engine/layers/l1/seg_1B/s9_validation_bundle/runner.py`

Current posture:
1. Strong structural and contract checks.
2. Realism metrics are informative but non-binding.

Chosen delta:
1. Add hard realism gates:
- country concentration (`Gini`, `top1`, `top5`, `top10`),
- active-country coverage floor,
- region-floor compliance,
- southern-hemisphere share floor,
- nearest-neighbor tail ratio ceiling (`p99/p50`).
2. Gate result:
- `PASS` only when structural and realism checks both pass.
3. Emit threshold + observed + breach reason in validation evidence bundle.

Expected effect:
1. Prevents future structurally-correct but statistically-poor outputs from passing.

### 5.6 Contract and schema deltas (required for clean governance)
Files to update:
1. `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`
2. `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml`

Chosen delta:
1. Extend `s2_tile_weights_policy` schema with `blend_v2` and concentration controls.
2. Activate and formalize `jitter_policy` fields (currently reserved) for `S6`.
3. Add realism metric fields expected in S9 validation output contract.
4. Preserve compatibility path:
- new fields optional under legacy mode,
- default behavior remains old path when fields absent.

Expected effect:
1. Makes policy-to-implementation mapping explicit and auditable.
2. Avoids hidden runtime knobs outside contract governance.

### 5.7 Determinism and migration controls
Chosen controls:
1. Keep deterministic seed namespaces per step (`S2`, `S4`, `S6`).
2. Introduce policy version bump (`v2`) and include version hash in artifacts.
3. Maintain a legacy fallback path for comparison runs.
4. Require side-by-side baseline vs v2 replay at identical seeds before promotion.

Why this matters:
1. Remediation is statistical, but provenance and replay guarantees remain non-negotiable.
2. We need clean attribution from policy delta to realism lift.

### 5.8 Initial parameterization for first remediation run (wave-0)
Starting values (to tune in validation loop):
1. `basis_mix`: `uniform=0.20`, `area_m2=0.35`, `population=0.45`.
2. `country_cap_share_soft`: set at baseline minus 10-15 percentage points for dominant countries.
3. `country_cap_share_hard`: soft cap + 3 percentage points.
4. `region_floor_share`: explicit nonzero floors for underrepresented regions.
5. `sparse_tail_component`: low bounded mass to avoid long-distance pathologies.

Purpose:
1. Move quickly out of current failure regime while preserving enough flexibility for tuning.

## 6) Validation Tests + Thresholds

### 6.1 Validation objective
Validate that the Section 5 fix bundle (`S2+S4+S6+S9`) produces:
1. Structural correctness unchanged.
2. Statistically realistic global spatial posture at `B` minimum.
3. Stable performance across seeds.
4. No hidden regressions passed by aggregate-only metrics.

### 6.2 Run protocol (required)
1. Compare `baseline` vs `v2-remediation` under identical scenario and ingest.
2. Use seed set: `{42, 7, 101, 202}`.
3. Run full 1B chain at minimum: `S2 -> S4 -> S6 -> S8 -> S9`.
4. Store all metrics per seed and pooled aggregate.
5. Validate both per-seed and pooled; pooled PASS is invalid if any seed fails hard gate.

### 6.3 Hard gates (fail-closed, all must pass)
1. Structural integrity:
- row parity and key integrity: PASS
- coordinate bounds validity: `100%` valid
- schema/bundle compliance: PASS

2. Concentration realism:
- country concentration Gini: `<= 0.68` (`B`), `<= 0.60` (`B+`)
- top-10% country share: `<= 50%` (`B`), `<= 42%` (`B+`)
- top-5% country share: `<= 33%` (`B`), `<= 27%` (`B+`)
- top-1% country share: `<= 10%` (`B`), `<= 8%` (`B+`)

3. Coverage realism:
- eligible countries with nonzero sites: `>= 85%` (`B`), `>= 92%` (`B+`)
- southern hemisphere site share: `>= 12%` (`B`), `>= 18%` (`B+`)
- region floor constraints: all configured floors satisfied (no exceptions)

4. Local geometry realism:
- nearest-neighbor `p99/p50` tail ratio improves by:
- `>= 20%` vs baseline for `B`
- `>= 35%` vs baseline for `B+`
- no country in top-volume cohort may show stripe/corridor collapse sentinel = TRUE

### 6.4 Soft diagnostics (non-blocking but tracked)
1. Country-level entropy distribution shift.
2. Within-country multi-cluster evidence score.
3. Bounding-box dispersion sanity by country class.
4. Top-country dominance gap (`top1-top2`) distribution.
5. Country-to-region contribution balance drift.

Soft diagnostics do not fail the run directly, but two consecutive adverse drifts require policy retune before promotion.

### 6.5 Statistical tests (evidence layer)
1. Distribution shift tests:
- KS test for NN distance distribution (`baseline` vs `v2`) per seed.
- Mann-Whitney U for median NN distance shift on top countries.

2. Concentration significance:
- bootstrap CI for Gini and top-k shares (95% CI).
- PASS requires upper CI bound below gate threshold for `B/B+`.

3. Stability significance:
- coefficient of variation across seeds for core metrics:
- `<= 0.30` for `B`
- `<= 0.20` for `B+`

### 6.6 Stage-mapped checks (where to test)
1. `S2` checks:
- basis mix sums to 1
- region floors/caps applied
- country-share preliminary metrics emitted

2. `S4` checks:
- assignment preserves S2 balancing intent
- no post-assignment reconcentration breach

3. `S6` checks:
- jitter mode `v2` active
- kernel mixture proportions respected
- point-in-country validity retained

4. `S8` checks:
- final site location realism metrics computed
- no contract regressions

5. `S9` checks:
- realism gates evaluated fail-closed
- threshold + observed + breach reason written to bundle

### 6.7 Promotion criteria
1. Promote to `B` when all hard gates pass for all seeds and stability criteria meet `B`.
2. Promote to `B+` only when all hard gates meet `B+` thresholds for all seeds and stability criteria meet `B+`.
3. Any single hard-gate fail blocks promotion and triggers retune cycle.

### 6.8 Failure triage map (fast diagnosis)
1. Gini/top-k fail only -> retune `S2` caps and concentration penalty.
2. Region floor fail with good Gini -> retune `S4` redistribution guard.
3. NN tail fail with concentration pass -> retune `S6` sparse-tail component.
4. Seed instability fail with mean pass -> tighten deterministic balancing and reduce high-sensitivity knobs.
5. Structural fail at any stage -> rollback and fix implementation before further realism tuning.

## 7) Expected Grade Lift (Local + Downstream Impact)
