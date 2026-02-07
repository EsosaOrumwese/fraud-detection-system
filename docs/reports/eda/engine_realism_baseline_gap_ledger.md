# Engine Realism Baseline Ledger (Step 1 Lock)
Date locked: 2026-02-07  
Run baseline: `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`  
Scope: published EDA segment reports (`1A, 1B, 2A, 2B, 3A, 3B, 5A, 5B, 6A, 6B`)

## 1) Frozen Segment Grades
| Segment | Frozen grade | Evidence source |
|---|---|---|
| 1A | B (segment), B- (outlet_catalogue), B- (coeff realism sub-verdict) | `docs/reports/eda/segment_1A/segment_1A_published_report.md` |
| 1B | C+ | `docs/reports/eda/segment_1B/segment_1B_published_report.md` |
| 2A | C | `docs/reports/eda/segment_2A/segment_2A_published_report.md` |
| 2B | C | `docs/reports/eda/segment_2B/segment_2B_published_report.md` |
| 3A | C | `docs/reports/eda/segment_3A/segment_3A_published_report.md` |
| 3B | D (borderline D+) | `docs/reports/eda/segment_3B/segment_3B_published_report.md` |
| 5A | B+ | `docs/reports/eda/segment_5A/segment_5A_published_report.md` |
| 5B | B+ | `docs/reports/eda/segment_5B/segment_5B_published_report.md` |
| 6A | B- | `docs/reports/eda/segment_6A/segment_6A_published_report.md` |
| 6B | D+ | `docs/reports/eda/segment_6B/segment_6B_published_report.md` |

### 1.1) Strict Recalibration (Engine-Impact Weighted)
This recalibration is intentionally stricter than the per-segment report grades. It keeps the original grades frozen for traceability, but adds an engine-level realism lens that weights each segment by:
- statistical severity of defects in its primary realism surfaces;
- propagation impact on downstream segments;
- final-platform relevance (especially `6B` outcomes).

| Segment | Report grade (frozen) | Calibrated grade (strict) | Rationale (engine-impact lens) |
|---|---|---|---|
| 1A | B / B- core | C+ | Strong base shape, but missing single-site tier, broad home/legal mismatch, and near-flat dispersion reduce realism at source. |
| 1B | C+ | C | Structurally clean, but regional imbalance and synthetic placement templates degrade downstream tz realism. |
| 2A | C | C- | Timezone assignment is internally correct but behaviorally unrealistic in multiple countries due to upstream spatial collapse. |
| 2B | C | C- | Routing surfaces are coherent but too flat (uniform weights, one sigma regime, rigid roster), limiting believable variation. |
| 3A | C | C- | Correct joins/conservation, but prior dominance and weak escalation effect suppress multi-zone diversity before virtualization. |
| 3B | D (borderline D+) | D | Uniform edge catalogue and weak settlement coherence are critical realism failures entering layer-2/3 behavior. |
| 5A | B+ | B | Good temporal realism, but channel collapse and tail sparsity keep it below robust synthetic realism. |
| 5B | B+ | B | Arrival realism is strong overall, but DST defect is systematic and materially affects time-feature validity. |
| 6A | B- | C+ | Excellent structural integrity, but IP-prior drift, sparse device-IP linkage, and K_max breaches materially weaken risk realism. |
| 6B | D+ | D | Truth/bank-view/case timeline defects are platform-critical; statistical realism for fraud outcomes remains non-credible. |

**Overall engine realism (strict, platform-weighted): `D+`**  
Interpretation: strong intermediate temporal layers (`5A/5B`) are not sufficient to offset critical realism failures in `3B`, `6A`, and especially `6B`.

## 2) Baseline Gap Ledger (Root-Cause Oriented)
Columns: `symptom`, `metric anchor`, `severity`, `downstream impact`, `suspected source`.

| Segment | Symptom | Metric anchor (from report) | Severity | Downstream impact | Suspected source |
|---|---|---|---|---|---|
| 1A | Missing single-site merchant base tier | `min outlets = 2`; `single_vs_multi_flag=True` for all merchants | High | Overstates multi-site behavior in routing and fraud baselines | Policy + implementation semantics |
| 1A | Home/legal mismatch too broad | `~38.6%` rows `home_country_iso != legal_country_iso` | High | Weakens legal-country realism, can distort cross-border and case interpretation | Policy |
| 1A | Candidate universe is over-globalized | candidate countries per merchant: median `38` (of max 39); realization ratio median `0.0` | High | Policy looks incoherent (`can expand anywhere` but rarely does), weak explainability | Policy |
| 1A | Dispersion heterogeneity is collapsed | implied `phi` CV `0.00053`, `P95/P05=1.00004` | High | Suppresses stochastic heterogeneity propagating into later layers | Hand-authored coefficient policy |
| 1B | Global placement imbalance | Europe-heavy concentration, weak southern hemisphere, sparse Africa/South America | High | Timezone diversity and regional behavior realism degrade downstream | Policy distribution design |
| 1B | Spatial templates look synthetic | mixed strip/split geometry; NN tail heavy (`p50=0.28km`, `p99=11.16km`) | Medium | Creates template artifacts in tz allocation and routing | Policy + location generation logic |
| 2A | Timezone support per country is compressed | `54/77` countries have exactly `1` tzid (`~70%`); top-1 tz share median `~1.00` | High | Local-time features lose realism and discriminative value | Upstream 1B + policy assumptions |
| 2A | Non-representative country->tzid outcomes | examples: NL->Caribbean tzid, NO->Svalbard tzid, US->Phoenix-only | High | Civil-time realism and interpretability weaken | Upstream geography collapse + assignment fallback dynamics |
| 2B | Site weights are behaviorally flat | uniformity-driven S1 posture; no meaningful hub dominance | High | Routing lacks realistic merchant/site concentration | Policy (weight-generation) |
| 2B | Excessive single-tz daily dominance | `~50%` merchant-days have `max p_group >= 0.9` | High | Under-diverse daily routing patterns | Policy + allocation behavior |
| 2B | Temporal heterogeneity absent | `sigma_gamma` unique values = `1` (`~0.1206`) | High | Merchants share one volatility regime; weak temporal realism | Policy (global sigma) |
| 2B | Panel/roster realism shallow | full 90-day rectangle; roster is one day, one arrival/merchant | High | Cannot express lifecycle/churn/seasonality realism | Scenario/roster policy |
| 3A | Prior dominance overwhelms diversity | top-1 prior concentration remains high even in multi-tz countries | High | Countries behave effectively single-zone | Policy (S2 priors) |
| 3A | Sampling adds little merchant variance | very low within-country/tz share std (log10 mass strongly negative) | High | Merchant-level allocation signatures are weak | Policy + S3 sampling settings |
| 3A | Escalation intent/outcome mismatch | escalated pairs multi-zone only `~13.3%` | High | Escalation semantics fail to produce intended diversity | Implementation + policy thresholds |
| 3B | Edge catalogue is structurally uniform | each merchant: `500` edges, `117` countries, uniform weights | Critical | Eliminates merchant/geography heterogeneity before 5B/6B | Policy + implementation design choice |
| 3B | Settlement coherence is weak | settlement-country overlap near baseline (`~0.5%`); large anchor distances | Critical | Legal anchor fails to shape operational footprint | Policy weighting design |
| 3B | Classification evidence is flat | one MCC/channel gate dominance; uniform metadata/single digest posture | High | Weak audit explainability of virtual behavior | Policy + implementation simplification |
| 5A | Channel realism not expressed | `channel_group = mixed` only | Medium | CP/CNP temporal/risk differences are unavailable downstream | Policy scope limitation |
| 5A | Tail-zone support mostly empty | `~98%` tail zones have zero volume | Medium | TZ-level analyses can overstate concentration artifacts | Policy sparsity design |
| 5A | Residual DST mismatch remains | DST windows still show small systematic residuals | Medium | Time-based feature purity is slightly degraded | Time conversion implementation detail |
| 5B | DST defect persists in arrivals | mismatch rate `~2.6%` with systematic `+/-3600s` pattern | High | Hour/day features biased in DST windows | Timezone conversion implementation |
| 5B | Geographic concentration is high | top-10 timezones carry `~81%` of arrivals | Medium | "Global" realism claim is weaker unless explicitly intentional | Upstream mix policy |
| 5B | Virtual channel is thin | virtual share `~2.25%` | Medium | Online/CNP-like behavior underpowered | Policy mix |
| 6A | IP type distribution drifts far from priors | residential observed `~96%` vs expected `~38%` | High | Network features dominated by unrealistic IP composition | Policy + implementation mismatch |
| 6A | Sparse device->IP linkage | only `~14.8%` of devices linked to IP | High | Weak entity graph propagation for downstream fraud logic | Policy + generation logic |
| 6A | Account cap semantics violated | widespread `K_max` breaches by account type | High | Tail inflation and policy-audit mismatch in holdings | Implementation enforcement and/or policy mismatch |
| 6A | Fraud-role propagation weak | risky parties do not strongly imply risky accounts/devices | High | Causal fraud graph signal weak before 6B overlay | Policy (risk propagation) |
| 6B | Truth labels are invalid at class-balance level | `is_fraud_truth=True` for `100%` of flows | Critical | Negative class collapse; model evaluation realism impossible | Implementation/policy mapping defect |
| 6B | Bank-view outcomes are almost uniform | bank fraud rate `~0.155` across strata; Cramer's V `~0.001` | Critical | No risk stratification; bank-view realism fails | Policy + implementation calibration defect |
| 6B | Case timelines violate temporal realism | negative gaps; fixed `1h/24h` duration patterns | Critical | Case lifecycle analytics become non-credible | Implementation logic defect |
| 6B | Amount/timing surfaces are mechanical | 8-point near-uniform amounts; no auth latency behavior | High | Synthetic behavior looks rule-flat and weakly lifelike | Policy simplification |

## 3) Severity Stack (Engine-Wide)
### Critical blockers (must fix first)
1. `6B` truth-label collapse (100% fraud truth).
2. `6B` bank-view near-uniformity (no stratification).
3. `6B` case timeline temporal invalidity.
4. `3B` edge-catalogue uniformity + weak settlement coherence.

### High blockers (next wave)
1. `6A` IP realism mismatch and sparse linkage.
2. `2B` uniform routing weights + single global temporal volatility.
3. `3A` prior dominance + escalation not materializing in outputs.
4. `1A` over-global candidate breadth + near-flat dispersion heterogeneity.
5. `5B` DST conversion defect.
6. `2A` compressed timezone support caused by upstream spatial collapse.

### Medium blockers (polish toward B+)
1. `1B` geographic rebalance and template smoothing.
2. `5A` channel-surface realism and tail-zone tuning.
3. `5B` virtual-share calibration for stronger online signal.

## 4) Step-1 Lock Outcome
This document is the frozen baseline for remediation planning.  
Next step (Step 2) should trace each `Critical/High` row to exact policy artifacts and implementation code paths, then attach measurable acceptance thresholds per fix.
