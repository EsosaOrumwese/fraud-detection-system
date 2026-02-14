# Cluster 7 - Round 1 Answers

## Q1) What is your realism grading model (what "B/B+" means, and what gates are hard vs soft)?

My realism grading model is a **two-layer certification system**:

1. **Hard gates (veto gates):** non-negotiable realism conditions that must all pass.
2. **Soft gates (target-band checks):** a multi-metric scorecard where each metric is evaluated against `B` and `B+` target bands.

If hard gates fail, the segment is not certifiable at `B` no matter how good the averages look.

### 1) What "B" means in this system

`B` means the segment is no longer "statistically plausible on paper only"; it is **operationally defensible** for downstream use.

Concretely, `B` requires:

- **all hard gates = PASS**, and
- **at least 70%** of `B` soft-band checks = PASS.

So `B` is not a loose midpoint grade. It means baseline realism contradictions are materially closed and run-to-run evidence is auditable.

### 2) What "B+" means in this system

`B+` is stricter. It means the segment has moved from "acceptable realism" to "strong realism posture with tighter distribution shape."

Concretely, `B+` requires:

- **all hard gates = PASS** (same veto rule), and
- **at least 80%** of `B+` soft-band checks = PASS,
- plus no major regression on critical concentration surfaces.

This prevents "metric gaming," where a segment might pass many easy checks but drift on structurally important behavior.

### 3) Hard gates vs soft gates (exact distinction)

#### Hard gates (fail-closed)
These are binary, non-compensating gates. For 1A remediation, the hard gates were:

1. **Single-site tier exists materially** (no missing base merchant tier).
2. **Candidate set not near-global by default** (no "everyone can expand everywhere" posture).
3. **Dispersion heterogeneity restored** (not near-constant variance profile).
4. **Required audit artifacts emitted** (realism claims must be verifiable run-over-run).

These gates are "hard" because each one protects against a structural failure mode that can invalidate downstream realism even when other metrics look good.

#### Soft gates (banded realism scorecard)
These are metric bands used for grading once hard gates are green. They cover:

- merchant pyramid and concentration,
- legal/geographic realism,
- candidate-realization coupling,
- stochastic realism,
- identity semantics,
- artifact completeness.

Each metric has two explicit intervals:

- a `B` interval,
- a tighter `B+` interval.

The score is the pass-share across all checks (for 1A: 14 total checks).

### 4) Why this model is robust (and recruiter-relevant)

This model is intentionally designed to block three common failure patterns:

1. **Average-score masking:** hard gates prevent catastrophic defects from being hidden by good averages.
2. **Single-seed luck:** certification includes replay/sensitivity evidence, not one lucky run.
3. **Metric-forging drift:** concentration and topology protections block "optimize one metric, break system realism" behavior.

So the grade is not an opinion; it is an executable decision protocol with explicit vetoes and threshold math.

### 5) Example outcome under this model (1A)

Under this exact framework, the certified 1A result was:

- hard gates: **4/4 pass**,
- soft coverage:
  - `B`: **13/14** (`92.86%`) -> pass,
  - `B+`: **10/14** (`71.43%`) -> below `80%` threshold,
- final decision: **`B` (eligible_B=true, eligible_B_plus=false)**.

That is the key point: this grading model is strict enough to reject an over-claim (`B+`) even after substantial improvement, while still certifying proven progress (`B`) with evidence.

## Q2) Choose one segment you've actually remediated (1A): baseline failure signature (top 3 issues), chosen fixes, what you froze to prevent regression

I will use **Segment 1A** because it is fully remediated through a formal wave process (`P0 -> P5`) with a final certification decision.

### Baseline failure signature (top 3)

At baseline, the segment was not failing because of one bug; it was failing because core realism surfaces contradicted each other.

1. **Population-shape failure (missing base merchant tier).**  
   - Single-site share was effectively `0.0` (`min outlets per merchant = 2`), so the generator had no meaningful single-site base.  
   - This structurally over-weighted chain-like merchants and polluted downstream topology.

2. **Cross-border realism contradiction (near-global candidates, weak realization).**  
   - Candidate breadth was near-saturated (`candidate median ~38` out of max `39`).  
   - Realized membership behavior was weakly coupled (`Spearman(C,R) ~0.1044`, realization ratio median `0.0`).  
   - So the world said "everyone can expand everywhere," while realized behavior said "almost nobody does." That is not a credible baseline.

3. **Stochastic realism collapse (variance almost constant).**  
   - Dispersion heterogeneity was nearly flat (`phi CV ~0.00053`, `P95/P05 ~1.00004`).  
   - That made count variation too regular and reduced realism under stratification.

### Chosen fixes (what I changed and why)

I did not do one broad patch. I executed a **causal wave strategy** so each fix could be attributed and defended.

1. **Wave P1: fix the count-generating roots first (`S1/S2`).**  
   - Recalibrated hurdle and NB coefficient surfaces to restore realistic merchant pyramid and dispersion behavior.  
   - Kept this wave scoped to upstream count mechanics to avoid confounding with downstream layers.  
   - Outcome movement:  
     - single-site share moved to `0.414`,  
     - median outlets to `9`,  
     - `phi CV` to `0.1406`,  
     - `phi P95/P05` to `1.58`.

2. **Wave P2: fix candidate-realization coherence (`S3/S4/S6`).**  
   - Compressed candidate breadth from near-global default to profile-conditioned breadth.  
   - Strengthened realization coupling so `R_m` is causally tied to `C_m` rather than weak suppression logic.  
   - Outcome movement:  
     - candidate median became `8`,  
     - `Spearman(C,R)` became `0.789`,  
     - realization-ratio median became `0.1176`,  
     - pathology caps stayed clean.

3. **Wave P3: fix legal realism + identity semantics.**  
   - Tuned mismatch posture to be realistic and size-stratified rather than broadly inflated.  
   - Explicitly hardened site identity semantics and fail-closed duplicate checks so downstream consumers cannot misread site identity behavior.  
   - Outcome movement:  
     - home-vs-legal mismatch rate moved to `0.1225`,  
     - top-vs-bottom size gradient moved to `+13.08pp`,  
     - unexplained duplicate anomalies were eliminated.

4. **Wave P4: close certifiability gaps (artifact completeness + determinism hardening).**  
   - Emitted all previously missing required outputs so realism claims are auditable, not narrative.  
   - Hardened replay determinism by re-keying stochastic master-material from `parameter_hash` rather than manifest-dependent commit variation.  
   - Result: same-seed replay stability held even under forced manifest drift.

### What I froze to prevent regression

I used explicit freeze contracts, not informal "do not touch" agreements.

1. **Wave freezes by scope.**  
   - After P1 closed, `S1/S2` became frozen unless explicit reopen was approved.  
   - After P2 closed, the accepted cross-border knob set and parameter hash were locked.  
   - After P3 closed, mismatch and identity posture were locked.

2. **Certification freeze with executable grade law.**  
   - All downstream use had to preserve hard gates plus B-eligibility (`eligible_B=true`).  
   - This prevented silent quality erosion while trying to optimize other segments.

3. **Determinism freeze through authority pair.**  
   - I pinned a determinism authority pair with forced manifest drift and verified global equality posture across both runs.  
   - That turned replay from "assumed" into proven behavior.

4. **Downstream reopen veto guard.**  
   - I implemented a freeze-guard scorer so reopened 1A candidates are rejected automatically if they regress frozen B posture.  
   - In practice, at least one candidate was explicitly rejected fail-closed when it violated required-output completeness.

### Net result of this remediation program

Segment 1A moved from a contradictory baseline to a certification-backed state:

- hard gates: `4/4` pass,
- `B` coverage: `13/14` (`92.86%`),
- `B+` coverage: `10/14` (`71.43%`),
- final certified grade: **`B`** (with explicit non-claim on `B+`).

That result matters because it proves the system can improve materially without over-claiming, and that improvements are preserved by freeze/veto controls rather than trust.

## Q3) What metrics did you use (and why those metrics matter)?

I used a **layered metric set**. The key design principle was: each metric must either detect a specific realism failure mode or block a known way of gaming the score.

### 1) Population-shape and concentration metrics

These measure whether the merchant world has a credible base and plausible inequality profile.

1. **Single-site share** (`P(outlet_count=1)`)  
   Why it matters: this is the fastest detector of base-tier realism. If it collapses to near zero, the entire world is chain-biased from the root.

2. **Median outlets per merchant**  
   Why it matters: protects against hidden inflation where single-site exists but typical merchant size is still unrealistically large.

3. **Top-10% outlet share**  
   Why it matters: captures concentration of capacity. It blocks false improvements where average counts look fine but mass is over-centralized.

4. **Gini of outlets per merchant**  
   Why it matters: global inequality check complementary to top-10 share; catches tail-shape distortions a single percentile metric can miss.

### 2) Cross-border coherence metrics

These test whether "candidate expansion" and "realized expansion" are causally connected.

1. **Candidate median (`median(C_m)`)**  
   Why it matters: detects over-globalized candidate policy.

2. **Candidate-to-membership coupling (`Spearman(C_m, R_m)`)**  
   Why it matters: proves whether candidate logic actually drives realized membership, not an unrelated suppression layer.

3. **Realization-ratio median (`median(rho_m)` where `rho_m = R_m / max(C_m,1)`)**  
   Why it matters: catches zero-realization collapse even when correlation is numerically high.

4. **Pathology caps** (`share_exhausted`, `share_high_reject`)  
   Why it matters: prevents scoring wins that are achieved by unstable retry/rejection behavior.

### 3) Legal/geographic realism metrics

These enforce interpretable legal structure rather than diffuse mismatch noise.

1. **Home-vs-legal mismatch rate** (`home_country_iso != legal_country_iso`)  
   Why it matters: baseline legal realism level check.

2. **Size gradient (top-decile minus bottom-deciles mismatch, in pp)**  
   Why it matters: enforces that legal complexity is enterprise-skewed, not uniformly spread across all merchant sizes.

3. **Multi-country legal spread**  
   Why it matters: detects over-expanded legal footprint. This was also one of the B+ miss surfaces, so it has real decision impact.

### 4) Stochastic realism metrics

These verify that variance structure is realistic, not near-constant.

1. **`phi` coefficient of variation (`CV(phi)`)**  
   Why it matters: direct heterogeneity signal across merchants.

2. **`phi` quantile spread (`P95/P05`)**  
   Why it matters: robust tail-sensitive check; prevents passing on CV alone when distribution shape is still compressed.

Using both metrics together prevents a common failure where one summary statistic improves while real variance texture remains unrealistic.

### 5) Identity and auditability metrics

These ensure outputs are usable in downstream systems without semantic ambiguity.

1. **No unexplained duplicate identity anomalies**  
   Why it matters: if identity semantics are ambiguous, downstream joins and labels can be wrong even when upstream distributions look good.

2. **Required outputs present (artifact completeness gate)**  
   Required artifacts included:
   - `s3_integerised_counts`,
   - `s3_site_sequence`,
   - `sparse_flag`,
   - `merchant_abort_log`,
   - `hurdle_stationarity_tests`.
   Why it matters: realism claims are not acceptable unless they are auditable run-over-run.

### 6) Why this metric set is decision-grade (not dashboard-grade)

I used the metrics in three decision roles:

1. **Veto role:** hard-gate metrics block certification if structural realism is broken.
2. **Grade role:** soft-band metrics determine `B` vs `B+` by explicit threshold law.
3. **Causality role:** phase-level metrics were tied to wave ownership (`P1`, `P2`, `P3`, `P4`) so improvements could be attributed to specific changes, not run noise.

### 7) Concrete 1A metric outcome snapshot

These are representative certified values from the final scoring artifact:

- single-site share: `0.414`,
- median outlets: `9`,
- top-10 share: `0.3797`,
- gini: `0.5971`,
- candidate median: `8`,
- `Spearman(C,R)`: `0.7891`,
- realization-ratio median: `0.1176`,
- mismatch rate: `0.1225`,
- size gradient: `+13.08pp`,
- `phi CV`: `0.1406`,
- `phi P95/P05`: `1.5804`,
- required outputs present: `true`.

This set is why I could defend the final result rigorously: the metrics are tied to failure modes, bounded by gates, and directly linked to a grade decision.

## Q4) What was the hardest tradeoff (realism vs compute, realism vs stability, realism vs determinism)?

The hardest tradeoff was **realism vs stability under a near-miss B+ posture**.

Specifically: after reaching certified `B`, I had a strong push to close the remaining B+ misses. But the most direct tuning path improved one realism surface while degrading another locked surface, creating a repeated "gain here, regress there" pattern.

### 1) Why this was the hardest tradeoff

By the time I hit P5, I was not fixing obvious defects anymore. I was trying to move from:

- `B` pass (`13/14`)  
to  
- `B+` pass (`>=80%`, but I had `10/14`).

The remaining misses were:

1. `top10_outlet_share` (near miss),
2. `gini_outlets_per_merchant` (material miss),
3. `multi_country_legal_spread`,
4. `realization_ratio_median`.

The first two (`top10`, `gini`) looked reachable via local coefficient tuning, so that became the hardest decision zone.

### 2) The contradiction I had to resolve

I needed to increase B+ realism coverage, but local tuning showed a structural coupling:

- when I improved `gini` toward B+ range, `top10_outlet_share` moved away from its B+ floor,
- when I tried to recover `top10_outlet_share`, inequality shape regressed again.

So the contradiction was:

- **Push for B+ concentration closure**  
vs  
- **Protect already-certified stability and avoid destabilizing P2/P3 closed posture**.

### 3) Options I considered

1. **Aggressive multi-surface retune (S4/S6/S7 and more).**  
   - Pro: higher chance to force B+ closure.  
   - Con: high blast radius; risked regressing closed legal/coupling surfaces and invalidating certification integrity.

2. **Narrow P1 coefficient mini-pass only (bounded local tuning).**  
   - Pro: low blast radius, clean causality, easy rollback.  
   - Con: may not have enough degrees of freedom to satisfy both concentration constraints simultaneously.

3. **Freeze at certified B and stop B+ chase.**  
   - Pro: preserves proven quality and determinism.  
   - Con: leaves known B+ gaps unresolved.

### 4) Decision and why

I chose **Option 2 first** (bounded mini-pass) with an explicit fail-safe:

- run a constrained sweep on `beta_mu` non-intercept scaling,
- accept only if concentration metrics improve jointly without posture regression,
- if no feasible point exists, rollback and keep certified `B`.

I chose this because it preserved engineering truthfulness:

- try a real, testable improvement path,
- but refuse to force a fragile "B+" by destabilizing previously closed surfaces.

### 5) What I implemented during the tradeoff

1. Created experimental coefficient bundles under new timestamps (no overwrite of locked authority bundle).
2. Ran bounded P1 loops across scale variants (`1.0`, `0.9`, `0.8`, `0.7`, `0.6`) plus intercept adjustments.
3. Scored each run against concentration and freeze expectations.
4. Applied rollback rule when joint B+ feasibility was not achieved.

Representative sweep behavior:

- `scale=1.0`: `top10=0.3758`, `gini=0.5932`
- `scale=0.9`: `top10=0.3668`, `gini=0.5842`
- `scale=0.8`: `top10=0.3469`, `gini=0.5635`

This showed exactly the coupling pressure: `gini` improved while `top10` fell below the B+ threshold direction.

### 6) Final tradeoff resolution

I **did not force a B+ claim**.

I rolled back experimental bundle edits and retained the certified `B` posture with freeze-guard discipline.

That was the hard call: choosing durable, reproducible realism over a higher but fragile headline grade.

### 7) Why this is a strong engineering signal

This tradeoff proves I do not optimize for vanity metrics.

I use controlled experiments, bounded blast radius, explicit rollback criteria, and certification law to make the final call. In production-facing MLOps/Data Engineering, that is the difference between "looks good once" and "can be trusted repeatedly."

## Q5) What was the post-remediation outcome (grade + remaining gaps + your plan)?

### 1) Post-remediation outcome (what was achieved)

For Segment 1A, the remediation program closed with a **certified `B`** outcome, not a narrative claim.

Final certified posture:

- hard gates: **`4/4` pass**,
- soft-band coverage:
  - `B`: **`13/14`** (`92.86%`) -> pass,
  - `B+`: **`10/14`** (`71.43%`) -> below required `80%`,
- grade decision: **`B`** (`eligible_B=true`, `eligible_B_plus=false`).

What this means operationally:

1. baseline contradictions are materially closed,
2. realism is audit-grade (not subjective),
3. deterministic replay and artifact completeness are in place,
4. the segment is safe to consume downstream under freeze-guard controls.

### 2) Remaining gaps (what is still open)

I left explicit non-closure notes instead of inflating the result.

The B+ misses are concentrated in four surfaces:

1. `top10_outlet_share` (near miss),
2. `gini_outlets_per_merchant` (material miss),
3. `multi_country_legal_spread` (large miss),
4. `realization_ratio_median` (below B+ lane even though B lane passes).

Interpretation:

- The segment is good enough for certified `B`.
- It is **not yet** strong enough for `B+` under current coupled constraints.
- Forcing B+ without additional controlled work would risk regression in already-closed surfaces.

### 3) What I proved before accepting the stop point

I validated that "stop at B" was a technical decision, not convenience.

1. Ran bounded coefficient mini-pass experiments targeting the concentration misses.
2. Observed coupling tradeoff (`gini` improves while `top10` deteriorates past B+ floor).
3. Applied rollback rule and restored the locked authority bundle.
4. Kept final claim at certified `B` only.

So the current outcome is an **honest max-stable point** under the chosen blast radius.

### 4) Forward plan (how I move from current B to potential B+ safely)

My forward plan is phased and fail-closed:

1. **Protect current certified B baseline (non-regression first).**  
   - keep hard gates and B-eligibility as mandatory for any reopen candidate,  
   - enforce freeze-guard scorer before downstream promotion.

2. **Run narrow, causal B+ recovery waves (one knob family at a time).**  
   - avoid broad multi-surface retune,  
   - require each wave to show direct metric movement on the targeted miss surface,  
   - reject any wave that regresses locked P2/P3 posture.

3. **Escalate blast radius only if bounded lanes show infeasibility.**  
   - if local coefficient lanes cannot satisfy coupled constraints,  
   - reopen broader surfaces only with explicit causal justification and retained rollback path.

4. **Re-certify, do not re-describe.**  
   - every reopen attempt must re-run hard gates, band coverage, determinism, and artifact completeness before grade change.

### 5) Current status in one line

**Current = certified `B`, stable and guarded; Target = `B+` only through controlled non-regressive waves, not by loosening standards.**

## Q6) Give one causal proof example: how you knew *this fix* moved *that metric* (not noise)

### Causal proof case: P1 dispersion remediation moved `phi` realism from near-flat to realistic heterogeneity

I’ll use one explicit causal claim:

- **Fix:** reworked the `S1/S2` coefficient lane (including NB dispersion coefficients / `beta_phi`) under the P1 wave.
- **Metric moved:** dispersion realism metrics (`phi CV`, `phi P95/P05`) from fail posture to pass posture.

### 1) What the baseline looked like

Before P1 remediation, dispersion realism was effectively collapsed:

- `phi CV ~ 0.00053`
- `phi P95/P05 ~ 1.00004`

That is near-constant variance, which is not realistic for merchant-level heterogeneity.

### 2) Intervention design (how I isolated the cause)

To prove causality, I deliberately constrained the experiment:

1. **State scope isolation:** P1 calibration runs were limited to `S0 -> S1 -> S2` (not full-segment), so downstream states could not confound the result.
2. **Fix-scope isolation:** changed the count/dispersion coefficient lane only; no broad cross-border or legal-policy retune in this step.
3. **Deterministic control posture:** fixed seed and run protocol for comparison and repeated checks.
4. **Consecutive-run requirement:** required repeated pass posture, not a single winning run.

This gives a clean "changed this lane -> observed movement on this metric family" setup.

### 3) Observed movement after the fix

After P1 remediation:

- `phi CV` moved to `0.1406`
- `phi P95/P05` moved to `1.5804`

Both moved from baseline fail values into the defined realism bands used in certification.

### 4) Why this is not noise

The movement is attributable, not random, for four reasons:

1. **Magnitude is structural, not marginal.**  
   - `0.00053 -> 0.1406` for `phi CV` is a two-orders-of-magnitude class change, not seed jitter.

2. **Direction matches mechanism.**  
   - The edited lane was exactly the one that governs dispersion heterogeneity; the moved metrics are the direct readout of that mechanism.

3. **Repetition was required.**  
   - P1 lock required stable posture across consecutive runs; this prevents one-off acceptance.

4. **Certification law consumed the same metrics.**  
   - These metrics were not side diagnostics; they were part of hard/soft gate logic in the grade decision path.

### 5) Additional anti-noise reinforcement

Later, determinism hardening proved same-seed stability even under forced manifest drift, which reinforces that metric movement came from policy/coefficient intervention, not unstable runtime randomness.

### 6) What this proves

This is causal proof in the engineering sense:

- isolate a controllable intervention,
- keep non-target surfaces constrained,
- observe large directional movement in the intended metric family,
- require repeatability before promotion.

That is how I know the fix moved the metric, not luck or observational noise.

## Q7) For an unimplemented segment (e.g., 6B): what is Wave-0 blocker and why must it precede everything else?

For **Segment 6B**, the Wave-0 blocker is:

**Supervision-surface validity is broken at the root (truth labels + bank-view + case time semantics), so downstream realism metrics are not trustworthy until that root is repaired.**

### 1) What exactly is blocked in 6B right now

The current 6B baseline has three critical failures that invalidate normal tuning:

1. **Truth-label collapse:** `is_fraud_truth=True` for effectively `100%` of flows.  
   - This removes the negative class, so discrimination/calibration metrics are structurally meaningless.

2. **Bank-view stratification collapse:** bank-view fraud rate is nearly flat around `~0.155` across strata with near-zero association strength.  
   - So bank-view outcomes are not responding to class/amount/geo risk posture.

3. **Case timeline temporal invalidity:** negative gaps and fixed delay spikes dominate timing behavior.  
   - So timeline realism is templated and non-monotonic in places.

These are not "quality nits." They are validity failures in the final supervision surface.

### 2) Wave-0 blocker definition (formal)

Wave-0 for 6B is not "improve realism." It is:

1. **restore non-degenerate truth mapping,**
2. **restore minimal risk-sensitive bank-view behavior,**
3. **restore temporally valid case sequencing,**
4. **enforce these as fail-closed gates (not warnings).**

Until these four conditions are in place, later improvements can look numerically better while still being statistically invalid.

### 3) Why this must happen before every other wave

Because without Wave-0, all higher-order tuning is built on broken labels.

1. **Campaign tuning before truth repair is misleading.**  
   If truth is collapsed, campaign "improvements" cannot be interpreted as real signal quality.

2. **Amount/timing tuning before case validity is misleading.**  
   Better amount curves do not fix non-monotonic or templated case logic.

3. **Stratification tuning before bank-view repair is misleading.**  
   If bank-view is near-constant, association gains can be artifacts rather than true risk sensitivity.

4. **Any grade claim before fail-closed gating is unsafe.**  
   If critical realism checks remain warn-only, regressions can ship as PASS.

So Wave-0 is precedence-critical because it restores the measurement system itself.

### 4) What Wave-0 includes (minimum executable scope)

Wave-0 should minimally include:

1. **Truth mapping correction:** ordered, condition-aware rule evaluation so non-overlay NONE paths resolve to LEGIT where intended.
2. **Case delay/lifecycle execution correction:** replace fixed minimum-delay templating with policy-driven sampled delays and monotonic sequencing guarantees.
3. **Bank-view conditioning correction:** ensure outcomes are conditional on meaningful risk context, not effectively constant.
4. **Gate hardening:** promote these checks to fail-closed critical gates.

Anything beyond this (campaign depth, richer sessions, geography polish) belongs to later waves.

### 5) Wave-0 exit criteria (what proves blocker is cleared)

Blocker is cleared only when all are true:

1. truth is non-degenerate (LEGIT non-zero, fraud prevalence in bounded range),
2. bank-view shows measurable stratification beyond near-zero effect sizes,
3. negative case gaps are eliminated and timeline order is valid,
4. critical realism checks fail closed on violation.

### 6) Practical sequencing statement

For 6B, **Wave-0 is a validity restoration wave, not an optimization wave**.  
If Wave-0 is not closed first, all subsequent "improvements" are at high risk of being non-causal or non-credible.

## Recruiter hardening pins (for lake-entry conversion)

1. **Final 1A certification artifact + run identity anchor**
   - Certification authority file: `runs/fix-data-engine/segment_1A/reports/segment1a_p5_certification.json`
   - Artifact stamp: `generated_utc=2026-02-13T10:34:00Z`, `wave=P5`
   - Decision encoded in artifact:
     - hard gates `4/4` pass,
     - `B` coverage `13/14`,
     - `B+` coverage `10/14`,
     - final grade `B` (`eligible_B=true`, `eligible_B_plus=false`)
   - Authority run lineage pinned in same artifact:
     - `p2_authority_run=9901b537de3a5a146f79365931bd514c`
     - `p3_authority_run=da3e57e73e733b990a5aa3a46705f987`
     - `p4_authority_run=416afa430db3f5bf87180f8514329fe8`

2. **Freeze-guard scorer path + guard artifact**
   - Freeze scorer executable: `tools/score_segment1a_freeze_guard.py`
   - Candidate guard artifact example:
     - `runs/fix-data-engine/segment_1A/reports/segment1a_freeze_guard_416afa430db3f5bf87180f8514329fe8.json`
   - This guard is the fail-closed reopen control (candidate rejected if hard gates or B-posture regress).

3. **Forced-manifest drift replay pair (determinism proof)**
   - `run_a=29bdb537f5aac75aa48479272fc18161`
   - `run_b=a1753dc8ed8fb1703b336bd4a869f361`
   - Shared control identity:
     - `seed=42` for both
     - `parameter_hash=59ca6719a623f6f024806b79344926c5941841789f2f92264bccad187f710f72` for both
   - Drifted manifest identity (intentional):
     - `manifest_fingerprint` run A: `f5f04c50d1682d9b00a572172fd3a090ff2420a641cb4f9e2dfa0177a612822e`
     - `manifest_fingerprint` run B: `c1230ffabe39afdce8d2300fd1b77aad3e5f2d9a49383fc09fa0b3dfacf3fa09`
   - Evidence artifacts:
     - `runs/fix-data-engine/segment_1A/reports/segment1a_p2_1_baseline_29bdb537f5aac75aa48479272fc18161.json`
     - `runs/fix-data-engine/segment_1A/reports/segment1a_p2_1_baseline_a1753dc8ed8fb1703b336bd4a869f361.json`
     - `segment1a_p5_certification.json` reports determinism verdict `p2_global_equal=true` and `p3_global_equal=true`.

4. **Seed roster used for 1A certification**
   - Certification roster: `{42, 43, 44}`
   - Where used:
     - `p1_4_lock_scorecard.json` includes two-pass replay across seeds `42/43/44`
     - forced-manifest determinism pair uses seed `42`
     - alternate-seed sensitivity evidence uses seed `43` (`alternate_seed_run=651fa96a4dc46cbcf6e3cfee8434180f`)
