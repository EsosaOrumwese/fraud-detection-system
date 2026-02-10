# Segment 5B Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 5B toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness
This section captures the observed statistical weaknesses in Segment 5B, prioritized by their effect on realism and downstream model behavior.

### 1.1 Primary weaknesses (material for realism)
1. **Systematic DST local-time defect (main realism weakness).**  
   Observed local-time mismatch rate is about `2.6%` (sample-based checks), with mismatches dominated by exact `-3600s` offsets and a very small `+3600s` tail.  
   Mismatches cluster around DST transition windows, especially the EU transition period.  
   - Why this is material: this is a structured timing bias, not random noise. It distorts hour-of-day feature realism for a meaningful subset of events and weakens explainability around time-sensitive behavior.
2. **High timezone concentration (global world skew).**  
   Timezone concentration is steep: top `5%` of timezones carry about `58.6%` of arrivals, and top `10%` carry about `81.3%`.  
   - Why this is material: global temporal behavior is dominated by a small timezone set. Downstream models can over-learn geography/timezone-specific rhythms rather than broadly realistic patterns.

### 1.2 Secondary weaknesses (constrain realism quality, but not hard blockers)
1. **Virtual routing share is low for rich online-behavior realism.**  
   Virtual arrivals are about `2.25%` of total arrivals.  
   - Why this matters: this is plausible for a physical-first world, but it limits online/CNP-like diversity if the intended synthetic world expects stronger digital behavior representation.
2. **Lean validation posture under-tests civil-time realism by default.**  
   Segment 5B validation uses sampled checks and relaxed civil-time/RNG gates in lean mode.  
   - Why this matters: defects like DST misalignment can still pass operational validation unless they are explicitly checked in statistical analysis.

### 1.3 Non-weaknesses (to avoid false diagnosis)
1. **S2/S3 duplicate-key anatomy is structural, not a bug.**  
   Multiple component rows per logical key are expected in current mechanics. After logical-key aggregation, count conservation is exact.
2. **Mass conservation and macro heavy-tail alignment are strong.**  
   Total S3 counts match total arrivals exactly, and merchant-level arrivals align almost perfectly with S2 intensity.
   - Why this matters: these are statistical strengths and should not be misclassified as remediation targets.

### 1.4 Section-1 interpretation
1. Segment 5B is statistically strong overall and can already support `B/B+` posture on most realism axes.
2. The main remediation priority is DST correctness in local-time rendering.
3. Secondary priorities are timezone concentration calibration (if broader global realism is required) and virtual-share tuning (if richer online behavior is required).
4. Because conservation and macro alignment already pass strongly, remediation should be focused and surgical rather than broad redesign.

## 2) Expected Statistical Posture (B/B+)
This section defines the target statistical posture for Segment `5B` under remediation, with explicit `B` and `B+` acceptance gates.

### 2.1 Non-negotiable `B` gates (hard requirements)
1. **Civil-time correctness with DST applied.**  
   Local-time mismatch (`observed_local - expected_local`) must be tightly bounded and non-systematic.
   - `B`: total mismatch rate `<= 0.20%`, and one-hour shift mismatches (`-3600/+3600`) `<= 0.10%`
   - `B+`: total mismatch rate `<= 0.05%`, one-hour shift mismatches `<= 0.02%`
   - Why this gate exists: removes structured hour-of-day bias from DST windows.
2. **DST-window parity must hold where transitions occur.**  
   For each DST transition window (US, EU, and timezone edge cases), observed local-hour profiles must align with expected-clock reconstruction.
   - `B`: average absolute hour-bin error per window `<= 1.5 pp`
   - `B+`: average absolute hour-bin error per window `<= 0.8 pp`
3. **Logical-key count conservation must remain exact.**  
   After logical-key aggregation, S3 counts and S4 arrivals must match exactly.
   - `B/B+`: mismatch count `= 0`, residual sum `= 0`
4. **Routing field integrity must remain exact.**  
   Physical rows must carry `site_id` and null `edge_id`; virtual rows must carry `edge_id` and null `site_id`.
   - `B/B+`: violation rate `= 0`
5. **Timezone concentration must match intended world posture.**  
   If the target world is global synthetic realism (not intentionally Europe-centric), concentration should be reduced.
   - `B`: top-10 timezone share `<= 72%`
   - `B+`: top-10 timezone share `<= 62%`
   - If Europe-heavy is intentional, this must be explicitly versioned as design intent rather than treated as silent drift.

### 2.2 `B` vs `B+` target posture by realism axis
1. **Temporal realism**
   - `B`: no systematic DST hour-shift signature; transition windows materially corrected.
   - `B+`: DST-period local-time behavior statistically close to non-transition periods after conditioning.
2. **Geo-temporal diversity**
   - `B`: concentration remains present but no longer dominates overall temporal behavior.
   - `B+`: broader timezone contribution with stable secondary timezone mass.
3. **Routing realism**
   - `B`: physical-vs-virtual temporal split remains plausible and stable.
   - `B+`: virtual component is strong enough to support richer online-behavior realism without breaking physical-first structure.
4. **Mechanistic coherence**
   - `B/B+`: S2->S3->S4 conservation and dispersion realism remain intact after fixes.

### 2.3 Quantitative acceptance targets
1. **DST offset mass**
   - `B`: `P(offset in {-3600, +3600}) <= 0.10%`
   - `B+`: `P(offset in {-3600, +3600}) <= 0.02%`
2. **Weekend-structure preservation**
   - Metric: `|weekend_share_observed - weekend_share_expected|`
   - `B`: `<= 0.20 pp`
   - `B+`: `<= 0.10 pp`
   - Why this matters: DST corrections must not distort weekly rhythm.
3. **Dispersion preservation (do not over-smooth)**
   - Metric: standard deviation of standardized count residuals
   - `B`: `1.20 to 1.60`
   - `B+`: `1.25 to 1.50`
   - Why this matters: maintain realistic NB2 burstiness while fixing timing.
4. **Virtual-share posture (if richer online realism is intended)**
   - `B`: virtual share `3% to 8%`
   - `B+`: virtual share `5% to 12%`
   - If policy intent remains strict physical-first, current low virtual share can be accepted only with explicit policy declaration.

### 2.4 Cross-seed stability expectations
1. Required seeds: `{42, 7, 101, 202}`.
2. All hard gates must pass on every seed.
3. CV targets for critical metrics (`DST mismatch`, `top-10 timezone share`, `virtual share`, `weekend-share delta`):
   - `B`: `<= 0.25`
   - `B+`: `<= 0.15`

### 2.5 Section-2 interpretation
1. For Segment 5B, `B` is primarily a temporal-correctness and consistency target: fix DST behavior without regressing conservation or routing integrity.
2. `B+` additionally requires controlled geo-temporal broadening and stronger online-behavior representativeness where policy intent calls for it.
3. Because 5B already has strong internal mechanics, remediation should be constrained: fix the specific mismatches while preserving existing strengths.

## 3) Root-Cause Trace
This section traces each material weakness in 5B to its immediate cause, upstream cause, and implementation locus.

### 3.1 Root-cause matrix
| Weakness | Immediate Cause | Upstream Cause | State/Policy/Code locus | Evidence | Confidence |
|---|---|---|---|---|---|
| DST local-time mismatch in `arrival_events_5B` | 5B local timestamp generation uses timezone offsets from cache that does not include 2026 transition boundaries | 2A timezone timetable cache horizon in this run is effectively capped at 2025 | `L2/5B/S4` local-time placement and tz lookup path; upstream `L1/2A` tz cache artifact | One-hour mismatch signature (`-3600s` dominant) concentrated on DST windows; decoded cache shows no transitions >= 2026 for the run artifact | High |
| Civil-time validator semantics mismatch | Local wall time is serialized with UTC marker semantics (`Z`) and then reinterpreted during civil-time checks | Representation contract between producer and validator is ambiguous for local timestamps | `L2/5B/S4` timestamp formatting and `L2/5B/S5` parser/check path | Parser-based check can report high disagreement while wall-clock reconstruction reproduces expected ~2% DST mismatch | High |
| DST defect not blocked by gate | Lean validation path relaxes civil-time failure to warning/continue behavior | Policy intent (`fail_closed`) is not enforced in lean execution branch | `config/layer2/5B/validation_policy_5B.yaml` vs `L2/5B/S5` lean-gating behavior | Defect survives operational gate and is only caught in EDA realism checks | High |
| Timezone concentration too steep | Routing in 5B inherits concentrated upstream timezone/site exposure and lacks balancing control | 5A zone/site concentration and 2B timetable topology feed concentrated support into 5B | `config/layer2/5B/arrival_routing_policy_5B.yaml`, upstream `L2/5A`, `L2/2B` outputs | Top-k timezone share remains high and stable across diagnostics | Medium-High |
| Virtual share lower than target posture | Effective virtual routing depends on eligibility path and hybrid context mass | Upstream merchant/class mix constrains virtual-capable pool | `arrival_routing_policy_5B.yaml` (`p_virtual_hybrid`) + upstream class/channel composition | Realized virtual share remains low despite non-zero virtual routing probability | Medium |
| Duplicate-key pre-aggregation anatomy appears alarming | Multi-component row representation before logical key collapse | None (expected mechanics) | `L2/5B/S2/S3` component generation and `L2/5B/S4` aggregation | Post-aggregation parity returns to exact conservation (`0%` mismatch) | High (non-defect) |

### 3.2 Causal chain for the principal defect (DST)
1. `L1/2A` produces timezone timetable cache with no effective transition support for 2026 windows in this run.
2. `L2/5B/S4` consumes that cache to compute local-time offsets during arrival rendering.
3. When real DST transitions occur in 2026, local-time offsets remain stale, creating systematic one-hour errors.
4. `L2/5B/S5` lean validation does not hard-stop on this condition, so artifacts pass forward.
5. EDA then surfaces the defect as a structured, non-random mismatch in DST windows.

### 3.3 Why this is a root-cause issue, not noise
1. The mismatch is not diffuse; it is tightly concentrated on known DST transition periods.
2. The offset distribution is discrete and structured (`-3600s` dominant), not broad random jitter.
3. The defect aligns with cache horizon evidence and implementation flow, so causality is coherent across state outputs and code path.

### 3.4 Upstream vs local ownership split
1. **Upstream-owned cause**: transition completeness/horizon of timezone timetable artifact (`2A`).
2. **5B-owned cause**: local timestamp serialization semantics and weak lean civil-time enforcement in validation (`S4/S5`).
3. **Cross-segment calibration cause**: concentrated geography/timezone support and low virtual-capable mass from upstream segments/policies.

### 3.5 Non-causes (explicitly ruled out)
1. Count conservation defects were ruled out: S2->S3->S4 conservation remains exact after logical aggregation.
2. Routing nullability integrity defects were ruled out: physical/virtual field assignment rules are internally coherent.
3. Macro volume alignment defects were ruled out: realized totals preserve upstream intensity posture.

### 3.6 Section-3 interpretation
1. The primary realism miss in 5B is a deterministic temporal correctness defect with clear upstream dependency and local enforcement gaps.
2. Secondary realism gaps are calibration problems (concentration and virtual share), not mechanical breakage.
3. Therefore, remediation should prioritize DST correctness and validation strictness first, then calibrate concentration/diversity levers without disturbing conservation mechanics.

## 4) Remediation Options (Ranked + Tradeoffs)
This section defines remediation choices for 5B, ordered by realism impact, causal certainty, and regression risk.

### 4.1 Ranking method
Options are ranked using four criteria:
1. **Realism impact**: expected lift against the `D`-driving weaknesses in Section 1.
2. **Causal confidence**: strength of evidence from Section 3 root-cause trace.
3. **Blast radius**: scope of side effects across 5B and upstream/downstream segments.
4. **Operational risk**: likelihood of run instability or compatibility breaks.

### 4.2 Ranked options summary
| Rank | Option | Primary weakness addressed | Expected realism lift | Cost/Risk profile |
|---|---|---|---|---|
| 1 | Extend/fix timezone transition cache horizon in upstream 2A | DST one-hour local-time error | High | Medium |
| 2 | Correct local timestamp serialization/parse semantics in 5B S4/S5 | Civil-time contract ambiguity and false disagreement | High | Medium |
| 3 | Enforce strict civil-time gate behavior in 5B validation | Defect pass-through in lean mode | Medium-High | Low-Medium |
| 4 | Add timezone concentration balancing controls in routing policy | Over-concentrated tz contribution | Medium | Medium |
| 5 | Recalibrate virtual-routing mass and eligibility path | Underweight virtual realism | Medium | Medium |
| 6 | Add continuous statistical sentinels to validation bundle | Drift detection and regression prevention | Indirect but material | Low |

### 4.3 Option 1: timezone cache horizon fix (upstream 2A)
Mechanism:
1. Extend transition-table construction so cache fully covers simulation dates plus margin.
2. Add hard cache completeness checks for high-mass tzids before cache publish.
Why ranked first:
1. This addresses the dominant realism defect with strongest causal evidence.
2. It removes structured one-hour offset errors at the source.
Tradeoffs:
1. Larger cache artifact and slightly broader lookup footprint.
2. Must verify no runtime regression in 5B local-time lookup throughput.

### 4.4 Option 2: local timestamp semantics correction (5B S4/S5)
Mechanism:
1. Stop encoding local wall time using UTC marker semantics.
2. Make local-time contract explicit and consistent between producer and validator.
Why ranked second:
1. Resolves semantic ambiguity that currently undermines civil-time diagnostics.
2. Prevents parser-induced false disagreement from masking real DST behavior.
Tradeoffs:
1. Potential compatibility handling for readers built around current representation.
2. Requires synchronized update of serialization and validation parsing logic.

### 4.5 Option 3: strict civil-time gate enforcement in validation
Mechanism:
1. Keep lean sampling economics, but enforce hard fail/quarantine above civil-time thresholds.
2. Remove silent warning-only pass path for material civil-time violations.
Why ranked third:
1. Converts known realism defects from post-hoc findings into immediate run-stop signals.
2. Raises trust in sealed outputs used downstream.
Tradeoffs:
1. More run failures during remediation phase until upstream fixes land.
2. Requires clear error payloads so failures are actionable rather than noisy.

### 4.6 Option 4: timezone concentration balancing controls
Mechanism:
1. Add routing-level soft caps or reweighting for extreme top-tz dominance.
2. Preserve intended geography while broadening secondary timezone support.
Why ranked fourth:
1. Important for `B+` global realism, but not a hard correctness defect.
Tradeoffs:
1. If Europe-heavy posture is intentional, aggressive balancing can over-correct into artificial flattening.
2. Requires versioned policy intent to distinguish intended concentration from drift.

### 4.7 Option 5: virtual-share recalibration
Mechanism:
1. Tune effective virtual-capable path, not only headline virtual probability parameters.
2. Calibrate by class/channel mix so uplift is realistic rather than uniform.
Why ranked fifth:
1. Needed for richer digital/CNP realism at `B+`, but secondary to DST correctness.
Tradeoffs:
1. Can perturb channel/timezone/cross-border distributions if changed too aggressively.
2. Requires guardrails to preserve physical-first world assumptions where intended.

### 4.8 Option 6: statistical sentinels inside validation bundle
Mechanism:
1. Add explicit metrics and pass/fail thresholds for DST offset mass, DST-window parity, top-k timezone concentration, and virtual share.
2. Emit deterministic validation verdicts with numeric evidence.
Why ranked sixth:
1. Sentinel checks do not fix causes directly, but are essential to stop regression.
Tradeoffs:
1. Higher validation complexity and threshold-governance overhead.
2. Must be stable across seeds to avoid spurious fail noise.

### 4.9 Remediation bundles
Bundle A: correctness-first (minimum recovery path)
1. Option 1 (cache horizon fix)
2. Option 2 (timestamp semantics correction)
3. Option 3 (strict civil-time gate)
Bundle B: B/B+ uplift path
1. Bundle A
2. Option 4 (timezone balancing)
3. Option 5 (virtual-share calibration)
4. Option 6 (sentinelization)

### 4.10 Section-4 interpretation
1. The shortest path out of `D+` is Bundle A because it directly removes deterministic temporal defects and closes gate leakage.
2. Achieving stable `B/B+` additionally needs Bundle B to improve diversity posture and prevent backsliding.
3. Bundle sequencing matters: correctness first, then calibration, then permanent statistical guardrails.

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)
This section locks the remediation package chosen for Segment 5B. It is intentionally explicit so implementation can be audited line-by-line and validated against Section 2 gates.

### 5.1 Chosen package
Chosen package: **Bundle B (correctness-first + calibration + sentinels)**, executed in three waves.
1. `Wave A` (correctness hardening): remove deterministic DST defect and stop pass-through.
2. `Wave B` (distribution calibration): reduce excessive timezone concentration and raise virtual realism toward B/B+ posture.
3. `Wave C` (contract hardening): encode thresholds/semantics in policy + schema so behavior remains stable across runs.

Reason for selection:
1. Wave A addresses the dominant causal chain with highest confidence.
2. Wave B addresses B/B+ uplift requirements without reworking core mechanics.
3. Wave C prevents the same class of drift from silently reappearing.

### 5.2 Wave A: correctness hardening (must land first)
#### A1) Enforce civil-time fail-closed in 5B validation runtime
Files:
1. `packages/engine/src/engine/layers/l2/seg_5B/s5_validation_bundle/runner.py`

Current behavior to remove:
1. Civil-time mismatches are computed but can still pass in lean flow via warning/override path.

Required delta:
1. Remove warning-only override for civil-time mismatch breach.
2. If civil mismatch rate exceeds threshold, mark validation failure and surface deterministic fail payload.
3. Keep sampled validation strategy, but do not soften verdict semantics.

Invariant after change:
1. If civil mismatch exceeds threshold, bundle verdict is not PASS.

#### A2) Fix local-time contract semantics in S4->S5
Files:
1. `packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/runner.py`
2. `packages/engine/src/engine/layers/l2/seg_5B/s5_validation_bundle/runner.py`

Current behavior to remove:
1. Local wall-clock fields serialized using UTC-style marker semantics and re-parsed ambiguously by validator path.

Required delta:
1. Serialize local timestamps as true local wall-clock representation (no misleading UTC marker semantics for local fields).
2. Validator must parse local fields as local wall-clock consistently with producer contract.
3. Keep UTC fields unchanged for canonical ordering/audit.

Invariant after change:
1. Civil-time check compares like-for-like representations (local wall-clock vs reconstructed expected local wall-clock).

#### A3) Increase civil-time sample power in S5
Files:
1. `packages/engine/src/engine/layers/l2/seg_5B/s5_validation_bundle/runner.py`

Current sampling:
1. `min(50000, max(10000, int(n_arrivals_total * 0.001)))`

Required delta:
1. Raise target to: `sample_target = min(200000, max(25000, int(n_arrivals_total * 0.005)))`

Reason:
1. DST mismatch is window-local and sparse; low sample fractions under-detect transition-local defects.

Invariant after change:
1. Civil-time defect rates are estimated with enough power to reliably detect sub-0.2% breaches.

#### A4) Add tz-cache horizon guard before 5B runtime consumption
Files:
1. `packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/runner.py` (or shared tz cache loader used by S4)
2. Upstream cache publish/check path in 2A (where transition tables are emitted)

Required delta:
1. Before run, assert transition coverage for each high-mass tzid intersects full scenario horizon.
2. If coverage is incomplete and tz is not explicitly fixed-offset, raise hard validation error.
3. Emit structured diagnostics listing tzids with missing horizon coverage.

Invariant after change:
1. 5B cannot run with stale transition horizon for active, DST-relevant tzids.

### 5.3 Wave B: calibration for B/B+ uplift
#### B1) Raise effective virtual routing share
Files:
1. `config/layer2/5B/arrival_routing_policy_5B.yaml`

Parameter delta:
1. `hybrid_policy.p_virtual_hybrid: 0.35 -> 0.50`

Expected effect:
1. Realized virtual share rises from ~2.25% toward Section-2 `B` band (`3% to 8%`), depending on eligibility path.

Guardrail:
1. If realized share exceeds `12%`, roll back and re-tune by eligibility filters rather than only probability.

#### B2) Reduce deterministic timezone over-concentration from fallback behavior
Files:
1. `packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/numba_kernel.py`

Current behavior to reduce:
1. Physical routing miss path can fall back to a default table, reinforcing dominant timezone mass.

Required delta:
1. Replace fixed/default fallback with bounded random fallback across merchant-eligible timezone/site tables.
2. Keep deterministic seed control so replayability is preserved.
3. Do not alter nullability invariants (`site_id` vs `edge_id`) for physical/virtual rows.

Expected effect:
1. Lowers top-k timezone share without flattening into unrealistic uniformity.

#### B3) Add concentration and virtual sentinels into validation bundle payload
Files:
1. `packages/engine/src/engine/layers/l2/seg_5B/s5_validation_bundle/runner.py`
2. `config/layer2/5B/validation_policy_5B.yaml` (threshold definitions)

Required metrics:
1. `top5_tz_share`
2. `top10_tz_share`
3. `virtual_share`
4. `weekend_share_delta_pp` (observed minus expected)

Required thresholds (initial):
1. `top10_tz_share <= 0.72` for B gate.
2. `virtual_share between 0.03 and 0.08` for B band.
3. `|weekend_share_delta_pp| <= 0.20`.

Behavior:
1. Emit metric values always.
2. Gate verdict according to policy mode.

### 5.4 Wave C: contract and schema hardening
#### C1) Make civil-time pass criteria policy-driven and schema-pinned
Files:
1. `config/layer2/5B/validation_policy_5B.yaml`
2. `docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml`

Add policy keys:
1. `max_civil_mismatch_rate`
2. `max_one_hour_shift_rate`
3. `dst_window_hour_bin_mae_pp_max`

Schema requirement:
1. Add keys to schema (currently strict with `additionalProperties: false`) so runtime reads are contract-valid.

#### C2) Document local-time representation contract
Files:
1. 5B contract/spec markdown for field semantics.
2. S4/S5 docstrings where timestamps are serialized/parsed.

Required content:
1. Explicit distinction: UTC canonical timestamp vs local wall-clock timestamp.
2. Prohibit ambiguous reuse of UTC marker semantics for local fields.

### 5.5 Ordered implementation sequence
1. `A1 + A2 + A3 + A4` in one correctness branch.
2. Re-run Segment 5B statistical checks and confirm Section-2 hard gates.
3. Apply `B1 + B2 + B3` for B/B+ uplift.
4. Stabilize with `C1 + C2` so thresholds/contracts are enforceable and versioned.

### 5.6 Non-regression constraints (must hold through all waves)
1. S2->S3->S4 conservation remains exact after logical-key aggregation.
2. Physical/virtual routing nullability remains exact (`site_id` xor `edge_id` as designed).
3. No regression to dispersion realism bounds from 5B baseline.
4. Seeded reproducibility remains intact for deterministic replay.

### 5.7 Expected Section-5 outcome
If executed in order, this chosen fix package should:
1. Eliminate the deterministic DST miss that currently dominates 5B realism downgrade.
2. Lift 5B into B range on correctness gates before calibration.
3. Make B/B+ posture sustainable through explicit sentinels and schema-pinned policy thresholds.

## 6) Validation Tests + Thresholds
This section defines the statistical and structural gates used to validate 5B remediation. The goal is to prove that Wave A fixes correctness defects, Wave B improves realism posture, and neither introduces regressions.

### 6.1 Validation objective
1. Prove civil-time correctness defects are removed (especially DST-local mismatch signatures).
2. Prove concentration/virtual-share calibration moves toward B/B+ posture.
3. Prove conservation, routing integrity, and dispersion realism remain intact.
4. Prove improvements are stable across seeds, not single-run chance.

### 6.2 Authoritative gate matrix
| ID | Test | Metric | B Gate | B+ Gate | Gate Class |
|---|---|---|---|---|---|
| T1 | Civil-time mismatch rate | `P(observed_local != expected_local)` | `<= 0.20%` | `<= 0.05%` | Hard fail |
| T2 | One-hour DST signature mass | `P(offset in {-3600,+3600})` | `<= 0.10%` | `<= 0.02%` | Hard fail |
| T3 | DST-window hour parity | Mean absolute error of hour-bin shares in DST windows (pp) | `<= 1.5 pp` | `<= 0.8 pp` | Hard fail |
| T4 | Logical-key conservation | `sum(S3_by_key) - sum(S4_arrivals)`, key mismatch count | `0` and `0` | `0` and `0` | Hard fail |
| T5 | Routing integrity | Physical/virtual nullability violations (`site_id`, `edge_id`) | `0` | `0` | Hard fail |
| T6 | Timezone concentration | Top-10 timezone share of arrivals | `<= 72%` | `<= 62%` | Major fail |
| T7 | Virtual realism share | `virtual_share` | `3% to 8%` | `5% to 12%` | Major fail |
| T8 | Weekly rhythm preservation | `|weekend_share_observed - weekend_share_expected|` | `<= 0.20 pp` | `<= 0.10 pp` | Major fail |
| T9 | Dispersion preservation | Std-dev of standardized residuals | `1.20 to 1.60` | `1.25 to 1.50` | Major fail |
| T10 | Cross-seed stability | CV of key metrics (`T1,T2,T6,T7,T8`) | `<= 0.25` | `<= 0.15` | Hard fail |
| T11 | TZ-cache horizon completeness | Active tzids covered to scenario horizon | `100%` | `100%` | Hard fail |
| T12 | Local-time contract integrity | Producer/validator local-time parse consistency | `100%` | `100%` | Hard fail |

### 6.3 Metric computation protocol
1. `T1/T2`: reconstruct expected local timestamps from tz rules, compute signed offset distribution.
2. `T3`: for each DST transition window and active timezone, compare observed vs expected local hour-bin shares; aggregate MAE in percentage points.
3. `T4`: collapse S3 component rows to logical keys, compare key-level and total counts to S4.
4. `T5`: assert strict xor/nullability constraints by routing mode.
5. `T6`: compute timezone frequency distribution and top-k shares (top1/top5/top10) plus Lorenz diagnostics.
6. `T8`: derive expected weekend share from scenario calendar and compare against observed arrivals.
7. `T9`: compute standardized residuals `(observed - expected) / sqrt(expected + eps)` and evaluate spread band.
8. `T10`: run multi-seed panel and compute coefficient of variation per gate metric.

### 6.4 Sampling and power rules
1. Civil-time sample size for validation bundle:
   - `sample_target = min(200000, max(25000, int(n_arrivals_total * 0.005)))`
2. DST-window minimum support:
   - Require at least `5000` sampled rows per major DST window when exposure exists.
3. If DST-window support is below threshold and exposure exists, mark as `insufficient_power` and fail gate.
4. If no exposure exists for a zone/window, mark `not_applicable` with explicit evidence.

### 6.5 Gate execution order
1. Execute hard-correctness gates first: `T11`, `T12`, `T1`, `T2`, `T3`, `T4`, `T5`.
2. Only if hard gates pass, evaluate calibration gates: `T6`, `T7`, `T8`, `T9`.
3. Run cross-seed stability last: `T10`.
4. Any hard-gate breach blocks release and grade-lift claims, even if calibration gates pass.

### 6.6 Wave exit criteria
1. **Wave A exit**:
   - `T1` to `T5`, `T11`, and `T12` pass on primary seed and verification seed set.
2. **Wave B exit**:
   - `T6` to `T9` pass without regressions in Wave A gates.
3. **Segment-level acceptance for B/B+**:
   - All gates pass and `T10` stability criterion is satisfied.

### 6.7 Failure attribution map
1. `T1/T2/T3` fail + `T11` fail:
   - root cause is upstream cache horizon/transition completeness.
2. `T1/T2/T3` fail + `T11` pass + `T12` fail:
   - root cause is local-time serialization/parser contract.
3. `T6` fail with hard gates passing:
   - root cause is routing concentration calibration.
4. `T7` fail while `T6` passes:
   - root cause is virtual eligibility/mix, not timezone support.
5. `T9` fails post-calibration:
   - over-correction has distorted dispersion realism.

### 6.8 Required validation artifacts per run
1. `civil_time_validation.json`:
   - mismatch rate, offset histogram, DST-window MAE, sampled support.
2. `routing_integrity_validation.json`:
   - physical/virtual integrity violation counts.
3. `concentration_validation.json`:
   - top-k timezone shares and Lorenz summary.
4. `virtual_share_validation.json`:
   - overall and stratified virtual share.
5. `seed_stability_summary.json`:
   - per-metric CV and gate pass/fail matrix.

### 6.9 Section-6 interpretation
1. Section 6 converts remediation intent into measurable release gates.
2. The gates are strict on correctness and controlled on calibration, matching the B/B+ objective.
3. The attribution map prevents ambiguous failures by linking each test breach to a likely causal tier.

## 7) Expected Grade Lift (Local + Downstream Impact)
This section forecasts the expected realism-grade movement from the chosen remediation package and clarifies how much of that lift is local to 5B vs propagated downstream.

### 7.1 Baseline framing
1. Published Segment 5B realism is currently `B+`, but that posture is fragile because a deterministic DST-local-time defect remains.
2. Under the hard-gate remediation rubric in Section 6, current 5B would fail temporal correctness gates until Wave A lands.
3. Therefore, the key lift is not only letter-grade movement; it is movement from non-gated plausibility to gated, defensible realism.

### 7.2 Expected local lift by remediation wave
#### Wave A (correctness hardening)
Expected metric movement:
1. `T1` civil-time mismatch rate: from about `2.6%` toward `<= 0.20%` (`B`) with stretch to `<= 0.05%` (`B+` path).
2. `T2` one-hour DST signature mass: sharp `-3600/+3600` pattern collapses toward gate bounds.
3. `T3` DST-window hour-bin MAE: transition-window mismatch drops into bounded error band.
4. `T4/T5` conservation and routing integrity remain exact (no expected regression).

Expected grade effect:
1. Restores a robust `B` floor under explicit hard-gate compliance.
2. Keeps `B+` attainable if the same pass condition holds across required seeds.

#### Wave B (calibration)
Expected metric movement:
1. `T6` timezone concentration: top-10 share from about `81.3%` toward `<= 72%` for `B`, with stretch to `<= 62%` for `B+`.
2. `T7` virtual share: from about `2.25%` into `3% to 8%` (`B` band), potentially higher under controlled uplift.
3. `T8` weekly-rhythm alignment and `T9` dispersion spread should remain within guardrails if calibration is constrained.

Expected grade effect:
1. Converts corrected `B` posture into durable `B+`.
2. Creates path to `A-` only if concentration and virtual-share targets improve without new distortions.

#### Wave C (schema/contract hardening)
Expected metric movement:
1. Minimal direct distribution change.
2. Strong governance impact: thresholds and semantics become policy/schema enforced.

Expected grade effect:
1. Stabilizes achieved grade across reruns and seeds.
2. Reduces regression risk from implicit behavior drift.

### 7.3 Scenario-based local grade outcomes
1. `Wave A` only: expected `B` to `B+` (high confidence).
2. `Wave A + Wave B`: expected `B+` with `A-` potential (medium confidence).
3. `Wave A + Wave B + Wave C`: expected stable `B+` as the most reliable target; `A-` remains conditional on calibration quality.

### 7.4 Downstream impact forecast (5B -> 6B and later)
What should improve downstream:
1. Local-time features in downstream segments become less biased around DST windows.
2. Geo-temporal signal becomes less over-dominated by a small timezone head.
3. Explanatory diagnostics become cleaner because deterministic hour-shift artifacts are removed.

What will not be fixed by 5B alone:
1. Segment-6B-local realism weaknesses unrelated to routing-time correctness remain (for example amount lattice and label-coupling posture).
2. Upstream concentration sources (for example 5A/2B posture) still cap how far 5B can diversify by itself.

Net downstream expectation:
1. Meaningful but bounded uplift in downstream realism quality.
2. Largest benefit is trust and interpretability, not full downstream grade rescue.

### 7.5 Confidence and uncertainty
1. High confidence in Wave A lift (causal chain is direct and strongly evidenced).
2. Medium confidence in Wave B lift (calibration overshoot/undershoot risk).
3. High confidence in Wave C governance value (regression prevention).

### 7.6 Section-7 interpretation
1. 5B is a high-leverage surgical-remediation segment, not a redesign segment.
2. The chosen package should produce a defensible `B/B+` posture when executed in wave order and validated with Section 6 gates.
3. True `A-` posture is possible but conditional on successful concentration/virtual calibration without harming dispersion realism.
