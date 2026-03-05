# Dev_Full Road to Production-Ready
_Mission Run + Gates + Evidence Packs for Senior-Defensible Proof_

## 1. Purpose, scope, and non-goals

### 1.1 Purpose

This document defines the **road to production-ready** for the **dev_full** platform. “Production-ready” here means: the dev_full stack can be **deployed into a realistic production-like operating posture** and can complete a **production-grade mission run** that produces **claimable evidence packs** (metrics + artifacts + drills) suitable for defending senior ML Platform and MLOps claims.

This document exists to prevent “green checklist drift.” It makes the goal explicit and forces all work to map to:

* the **mission run** definition,
* the **gates** required to de-risk that mission,
* and the **evidence** required to declare success.

### 1.2 Scope

This road covers everything required to make dev_full production-ready in the operational sense above:

* **Runtime hot path (RTDL + decisioning):** ingestion boundary, streaming backbone, projections/state, decision chain, archive/audit sinks, and case/labels.
* **Learning & evolution loop:** time-causal dataset building, training/evaluation, model tracking/registry, promotion corridor, rollback readiness.
* **Operations & governance:** observability, runbooks and alert posture, audit answerability, promotion governance, and incident/drill evidence.
* **Cost-to-outcome and idle-safe operation:** budget envelopes, unit economics, teardown, and post-run residual scans.

### 1.3 Non-goals

The following are explicitly **not required** to declare *production-ready (dev_full)*:

* Migrating to **prod_target** infrastructure or “best-of-the-best” enterprise stack. dev_full remains the stack; the goal is to prove it can operate production-like.
* Achieving bank-scale throughput if it is outside the declared dev_full operational envelope. Scale claims must match the declared envelope.
* Multi-region disaster recovery, active-active architectures, or full regulatory compliance programs beyond what is needed for auditable operation and controlled change.
* Finding the “best fraud model.” The goal is to prove the **governed lifecycle** (time-causal learning, evaluation, promotion, rollback), not to maximize domain KPIs.
* Building a full case management product UI. Case/labels are included only to the extent needed for truth surfacing, learning realism, and auditability.

### 1.4 Audience

* **Primary:** Codex (implementer) — must use this document as the authoritative guide for what “production-ready dev_full” means and what evidence must be produced.
* **Secondary:** You (designer/owner) — use it to steer work, prevent drift, and generate outward-facing claims from evidence packs.
* **Tertiary:** Reviewers (recruiters/engineers) — evidence packs produced under this road are intended to be defensible and inspectable.

---

## 2. The end goal

### 2.1 The single objective

The single objective is to execute a **Production-Grade Run (Mission Run)** on dev_full. This mission run is the “escape velocity” event: it proves the platform is not a toy by demonstrating that it can operate under realistic pressure, recover safely, remain auditable, and stay within bounded cost — while producing durable evidence.

### 2.2 What success means

Success is not “all phases are green” in isolation. Success means:

* The mission run completes under a **declared operational envelope** (steady/burst/soak + realistic cohorts).
* The platform produces the required **evidence bundles**:

  * runtime scorecard metrics with distributions (p50/p95/p99 where relevant),
  * mandatory drill reports (replay integrity, lag recovery, schema evolution, dependency degrade, rollback, audit drill, cost guardrail),
  * governance and audit artifacts (promotion records, lineage/provenance, decision traceability),
  * cost-to-outcome receipts and idle-safe teardown proofs.
* The final verdict is **PASS only if** `open_blockers = 0` and all required evidence bundles are present and readable.

These outputs are what enable senior-grade claims (platform reliability, governed delivery, replay safety, auditability, cost discipline). If the evidence pack is incomplete, the mission is not considered successful.

### 2.3 What must be true to declare “production-ready dev_full”

Dev_full is production-ready only when:

1. **Wiring is stable:** platform infrastructure, identities, handles, and evidence sinks are correct and do not mask data-plane failures.
2. **Data is understood:** a 7d realism pass has pinned the cohort mix (skew/dupes/out-of-order), join coverage, and time-safe allowlists needed for RTDL, IEG, and learning.
3. **Operational certification is passed:** runtime and ops/gov certification packs are completed under the dev_full operational envelope.
4. **A go-live rehearsal mission succeeds:** the platform runs continuously for a meaningful window, survives at least one controlled incident/drill, performs at least one controlled change (promotion/deploy), and closes with bounded cost and idle-safe teardown — with zero open blockers and a complete evidence pack.

That combination—not “greens” alone—is the definition of production-ready in this document.

---

## 3. Production-Grade Run specification (the mission profile)

This section defines the single deliverable that ends the “road to production-ready”: a **production-grade mission run** on dev_full that generates a complete, claimable evidence pack.

### 3.1 Mission charter

**Mission name:** `DEV_FULL_PROD_GRADE_RUN_v0`
**Mission purpose:** demonstrate dev_full can operate under realistic production-like pressure and produce senior-defensible proofs.
**Mission authority:** the run is considered successful only if the **mission completion rule** (Section 3.8) is satisfied.

**Pinned mission inputs (must be explicit in the run charter artifact):**

* `manifest_fingerprint={manifest_fingerprint}` (world identity)
* `scenario_id` (scenario identity)
* `platform_run_id` and `scenario_run_id` (run identity)
* `runtime_window_start_ts_utc` / `runtime_window_end_ts_utc`
* `as_of_time_utc` (time-causal learning cutoff)
* `label_maturity_lag` (time delay before labels become eligible)
* `injection_path` (one of: `via_IG` or `via_MSK`, must be declared)
* `budget_envelope_usd` for the mission run (and per major lane if applicable)

**Mission run charter output artifact (required):**

* `mission_run_charter.json` (run-scoped, readable, immutable once committed)

---

### 3.2 Data sources and boundaries

This mission enforces a strict boundary model:

**Oracle boundary**

* Oracle Store is the full source-of-truth bundle (external producer-owned).
* Runtime does **not** have carte blanche access to Oracle; it must only consume the **stream_view** materializations for the declared runtime window.
* Learning is forbidden from “future Oracle” access: all learning datasets must be time-causal under `as_of_time_utc` and `label_maturity_lag`.

**Stream-sort boundary (under Oracle)**

* Stream-sort/materialization produces stream-ready views (`stream_view`) for the declared window and emits receipts/parity evidence into run-control.

**Runtime truth boundary**

* IG (when `via_IG`) is the admission truth boundary: admitted/quarantined/receipt surfaces must be produced and used for later truth and learning basis.
* If `via_MSK` is used for hot-path-only certification, the mission charter must explicitly limit which claims are certified (no claiming IG envelope performance).

**Truth products**

* `s4_*` truth products are learning/eval only and must not influence runtime decisions.

---

### 3.3 Load campaign (steady → burst → recovery → soak)

The mission run must include a full load campaign. Numeric values are **not** defined here; they come from the numeric contracts referenced in Section 12. This section defines the **shape** and the required evidence.

**Phases:**

1. **Warmup**

   * Bring the platform to stable operation and confirm observability surfaces are live.
2. **Steady window**

   * Sustained load at `RC2-S.steady_rate` for at least `RC2-S.steady_duration`.
3. **Burst window**

   * Increase to `RC2-S.burst_rate` (or `burst_multiplier × steady`) for at least `RC2-S.burst_duration`.
4. **Recovery window**

   * Return to steady and measure time-to-return-to-stable (lag and latency return under threshold).
5. **Soak window**

   * Sustained operation for at least `RC2-S.soak_duration` to surface memory leaks, backlog creep, sink backpressure, and cost behavior.

**Required outputs:**

* `runtime_scorecard_snapshot.json` at the end of each phase (steady/burst/recovery/soak)
* A single consolidated `mission_scorecard_report.md` summarizing distributions and breaches

---

### 3.4 Cohort realism requirements (must include “production messiness”)

The mission run must include realistic cohorts; otherwise the run is not claimable.

**Cohorts to include (minimum set):**

* **Duplicates cohort:** repeated delivery attempts for some events (tests idempotency and dedupe correctness).
* **Out-of-order cohort:** events arriving out of time order within a flow/key (tests watermark/allowed-lateness posture).
* **Hot-key cohort:** a small set of keys that account for a disproportionate share of traffic (tests skew resilience).
* **Payload extremes cohort:** near-limit payload sizes (tests envelope behavior and serialization/perf).
* **Mixed event types cohort:** representative mix of event types seen in the data realism profile.

**Required outputs:**

* `cohort_manifest.json` describing the cohort composition and injection method
* `cohort_results_summary.json` showing how each cohort impacted lag/latency/errors/quarantine

---

### 3.5 Required runtime outputs (what must be produced end-to-end)

To claim runtime success, the platform must produce durable, readable outputs across all runtime planes within the mission window:

**Ingestion truth surfaces (when `via_IG`):**

* admitted count, quarantined count, duplicate suppression evidence
* receipts summary, quarantine reason distribution, and (declared) offset/position snapshot

**Streaming/RTDL outputs:**

* projections produced and persisted as designed (IEG/OFP outputs and state)
* checkpoint evidence and bounded lag evidence

**Decision chain outputs:**

* decisions committed with version headers and correlation IDs
* action outcomes committed
* audit records committed (append-safe), and/or audit stream landed in S3 via sink

**Case/labels outputs:**

* cases created from decision triggers (if enabled in mission scope)
* labels stored under writer-boundary semantics (even if labels are sparse)

**Required output artifacts:**

* `runtime_outputs_manifest.json` (lists required outputs and their readback proofs)

---

### 3.6 Required learning outputs (time-causal learning loop)

The mission must prove the learning corridor works on real run windows.

**Learning input readiness (time-causal):**

* `as_of_time_utc` enforced for events/features
* `label_maturity_lag` enforced for truth/labels
* leakage guardrails run and published (no future rows)

**OFS dataset output:**

* dataset manifest + fingerprint
* dataset quality summary (row counts, missingness, key coverage, label coverage)
* rollback recipe (dataset-level)

**MF train/eval output:**

* training + evaluation reports
* baseline/champion comparison evidence (even if baseline is “previous champion”)
* full lineage/provenance (code/config/data fingerprint → model artifact)

**MPR output:**

* promotion decision record (or explicit non-promotion record)
* if promotion occurs: ACTIVE resolution evidence and post-promotion observation snapshot
* rollback readiness (at least one rollback drill in the mission, or in the paired ops/gov pack)

**Required output artifacts:**

* `learning_outputs_manifest.json`

---

### 3.7 Mandatory drill events during the mission

The mission run is only production-grade if it proves failure behavior, not just steady behavior.

**Mandatory drills (minimum set):**

1. **Replay/backfill integrity drill**

   * replay a bounded window and prove invariants: no double side effects, consistent aggregates, consistent decision counts.
2. **Lag spike + recovery drill**

   * induce lag/backpressure and prove detect → mitigate → recover within bound.
3. **Schema evolution drill**

   * compatible change passes; incompatible change quarantines/blocks without silent corruption.
4. **Dependency degrade drill**

   * simulate a dependency outage/latency spike and prove degrade mode keeps the system safe and bounded.
5. **Audit drill**

   * answer “what ran for decision X and why” within a bounded time using platform records.
6. **Cost guardrail + idle-safe drill**

   * prove cost envelope enforcement and post-run idle-safe posture.

**Drill outputs (required for each drill):**

* `drill_<id>_report.json` (scenario, expected behavior, observed timeline, recovery bound, integrity checks)
* a link/reference to the runbook used

---

### 3.8 Mission completion rule (PASS/FAIL)

The mission run verdict is **PASS** only if all of the following are true:

1. All mission phases (steady/burst/recovery/soak) completed with required scorecard snapshots present and readable.
2. All mandatory cohorts were included and cohort manifests/results are present.
3. All mandatory drills executed and produced valid drill report bundles with recovery bounds met.
4. Learning corridor outputs exist and are time-causal (no leakage), with dataset manifest/fingerprint and lineage complete.
5. All required runtime outputs are present and readback-verified (outputs manifest satisfied).
6. Cost envelope and idle-safe closure are satisfied (post-teardown residual scan clean, cost receipts published).
7. `open_blockers = 0` in the final blocker register, and the final verdict artifact is published and readback-verified.

If any condition fails, the mission verdict is **FAIL** (or `HOLD_REMEDIATE` if the failure is recoverable without redefining the mission charter), and the rerun boundary rules determine what must be rerun.

---

## 4. Pillars of production-ready (must-haves)

These pillars are the **non-negotiable outcomes** that define “production-ready dev_full.” They exist to prevent checklist drift: you do not get to declare readiness because phases are green; you declare readiness only when these outcomes are proven with evidence.

Each pillar below is written as:

* **What it means**
* **What must be true**
* **How it is proven (minimum evidence)**
* **Common failure modes to watch for**

---

### 4.1 Hot path is SLO-grade within the declared envelope

#### What it means

The platform’s **end-to-end runtime path** (ingest → stream processing/projections → decision → action/logging) operates within declared SLO bounds **under steady, burst, recovery, and soak**. This is not “it ran once”; it is **predictable operation** under defined pressure.

#### What must be true

* The platform can sustain the **RC2-S steady profile** without accumulating unbounded lag/backlog.
* Under the **RC2-S burst profile**, the system either:

  * remains within SLO, or
  * enters a defined degraded posture while remaining safe and bounded.
* Recovery is measurable: after burst or induced lag, the system returns to “stable” within a defined bound.
* Soak shows stability: no memory leaks, no backlog creep, no increasing error rates, no sink-induced collapse.

#### How it is proven (minimum evidence)

* **Scorecard distributions** for the mission run:

  * end-to-end latency p50/p95/p99 (at minimum p95/p99)
  * error/timeout rate
  * consumer lag p95/p99
  * checkpoint success rate and checkpoint duration p95 (if applicable)
  * throughput (measured at the correct boundary for the declared injection path)
* **Recovery evidence**:

  * time-to-return-to-stable after burst and after a lag/restart drill
* **Observability evidence**:

  * trace/correlation coverage sufficient to localize where time is spent

#### Common failure modes to watch for

* “Throughput” measured in one component (e.g., Flink operator rows/s) while IG-admitted rate is far lower (wrong measurement surface).
* Hot-key skew causing one partition to lag massively while global metrics look fine.
* Sink backpressure (archive/audit writes) silently throttling the pipeline.
* Aurora connection pool saturation causing p99 latency spikes and timeouts.
* Degrade mode exists but is never triggered/verified, or is unsafe when triggered.

---

### 4.2 Streaming semantics are correctness-preserving (retries/duplicates/replay/out-of-order)

#### What it means

The platform remains **correct** when the world behaves like production:

* clients retry,
* events duplicate,
* events arrive out of order,
* consumers restart,
* replays/backfills occur,
* schemas evolve.

Correctness is not “no crashes.” Correctness is: **no double side effects, no silent corruption, invariants hold.**

#### What must be true

* **Idempotency**: duplicates do not create duplicate downstream side effects (double decisions, double cases, double audit entries).
* **Replay safety**: replaying a known window produces consistent outcomes under defined invariants.
* **Out-of-order tolerance**: late/out-of-order events are handled by policy (windowing/watermarks, side outputs, or explicit rejection/quarantine), not silently misprocessed.
* **Schema evolution behavior** is explicit:

  * compatible changes are accepted,
  * incompatible changes are blocked/quarantined (fail-closed),
  * no silent parse/field drift.

#### How it is proven (minimum evidence)

* **Cohort injection results**:

  * duplicates cohort results (dedupe hit rate, duplicate-admission rate, side-effect invariants)
  * out-of-order cohort results (late rate, handling policy evidence)
  * hot-key cohort results (skew handling and bounded lag)
* **Replay/backfill drill report**:

  * replay window definition
  * invariants pass (counts, aggregates, no double side effects)
  * time-to-complete bound
* **Schema evolution drill report**:

  * compatible change accepted evidence
  * incompatible change quarantined/blocked evidence
  * quarantine reason distribution
* **Truth boundary evidence**:

  * offset/position snapshot semantics are pinned and understood for the declared ingestion mode

#### Common failure modes to watch for

* Idempotency key collisions (two true events share a key and one is dropped incorrectly).
* “Replay window too small” (proves nothing about correctness).
* Late events silently dropped with no accounting.
* Quarantine exists but reason taxonomy is too vague to diagnose.
* Mixed “proxy offsets” used as if they are Kafka offsets (semantic drift).

---

### 4.3 Learning + promotion corridor is governed and reversible (rollback is real)

#### What it means

You can safely evolve models in production-like operation:

* learning is time-causal (no future leakage),
* training/evaluation is reproducible and traceable,
* promotion is gated and auditable,
* rollback is time-bounded and proven.

This is the core difference between “a model pipeline exists” and “MLOps is production-grade.”

#### What must be true

* **Time-causal learning**:

  * events/features are bounded by `as_of_time`
  * labels/truth are bounded by `as_of_time - maturity_lag`
  * “no future rows” hard checks pass
* **Immutable datasets**:

  * OFS publishes dataset manifest + fingerprint
  * training binds to that fingerprint (no “latest”)
* **Meaningful evaluation**:

  * candidate is evaluated vs baseline/champion
  * thresholds are pinned
* **Promotion governance**:

  * eligibility checks pass before mutation
  * promotion commit has transport proof
  * ACTIVE resolution is deterministic (one active per scope)
* **Rollback**:

  * rollback is executable and time-bounded
  * post-rollback stability verified

#### How it is proven (minimum evidence)

* **Learning input readiness pack**:

  * replay basis receipt + as-of + maturity + leakage guardrail report
* **OFS pack**:

  * dataset manifest + fingerprint + quality summary + rollback recipe
* **MF pack**:

  * train/eval report + baseline comparison + lineage/provenance complete
* **MPR pack**:

  * promotion record + transport proof + ACTIVE snapshot + post-promotion observation
* **Rollback drill report**:

  * observed rollback time vs target
  * verification that last-known-good is restored
* **Audit linkage**:

  * ability to trace a production decision to model version and back to training run

#### Common failure modes to watch for

* Using labels keyed to event time rather than label availability time (leakage).
* “Baseline” not pinned (comparison becomes meaningless).
* Promotion is “write a pointer” without readback/transport proof.
* Rollback exists on paper but isn’t executed as a drill.
* MLflow lineage incomplete (“orphan model” problem).

---

### 4.4 Operations are observable and auditable (fast answerability + diagnosability)

#### What it means

When things go wrong (and they will), the platform can:

* detect issues quickly,
* localize the fault domain,
* recover predictably,
* and answer audit questions with evidence, not guesswork.

This is what separates a toy system from an operated system.

#### What must be true

* **Correlation continuity**: events carry correlation IDs across ingress → stream → decision → archive/case.
* **Actionable alerting**: alerts map to runbooks; false positives are controlled.
* **Fast diagnosability**: you can distinguish data vs model vs pipeline vs infra failures quickly.
* **Audit answerability**: you can answer “what ran, with what model/data/config, and why?” within a bounded time using records.

#### How it is proven (minimum evidence)

* **Observability surfaces exist and are used**:

  * dashboards for lag, latency, error rate, checkpoint health, sink backlog, cost anomalies
* **Alert/runbook linkage**:

  * each critical alert has a runbook reference
* **Incident-style drill evidence**:

  * lag spike + recovery drill with time-to-detect and time-to-recover
* **Audit drill report**:

  * select a decision and trace model/version → promotion record → training run → dataset fingerprint → config
  * measure audit response time and completeness

#### Common failure modes to watch for

* Telemetry exists but lacks correlation, so you can’t localize bottlenecks.
* Alerts exist but aren’t actionable (no runbooks; noisy).
* “Audit logs” exist but are missing key fields (model version, dataset fingerprint, promotion ref).
* Decision explanations aren’t reconstructable (no reason codes or feature-set identity).

---

### 4.5 Spend is bounded and enforced (unit cost + idle-safe)

#### What it means

The platform is economically operable:

* cost is measured and attributable,
* budget envelopes are enforced,
* unit economics are understood,
* and the platform returns to idle-safe state after runs.

This is a senior signal because it shows stewardship, not just engineering.

#### What must be true

* Every mission run has a **budget envelope** declared in advance.
* Cost-to-outcome receipts are produced per run/lane.
* Unit costs are measurable (cost per X events, cost per training run, cost per replay).
* There is a cost anomaly and overrun posture (alert/throttle/stop/teardown policy).
* Teardown leaves no expensive residues (residual scan clean; idle-safe verified).

#### How it is proven (minimum evidence)

* **Pre-run budget envelope artifact**
* **Post-run cost receipts**:

  * total cost and lane-level attribution where possible
  * unit cost calculations tied to counters
* **Cost guardrail drill**:

  * show that a cost threshold triggers the expected enforcement behavior
* **Teardown evidence**:

  * residual scan output
  * idle-safe snapshot

#### Common failure modes to watch for

* Costs cannot be attributed to lanes/components (no visibility → no control).
* “Idle safe” exists but leaves hidden resources running (MSK/Flink apps, endpoints).
* Unit costs are computed from the wrong counters (e.g., processed rows vs admitted events).
* Budget envelopes are declared but never enforced (no action on breach).

---

### 4.6 Pillar-to-mission enforcement (how these pillars prevent drift)

To avoid “green checklist” drift, the mission must:

* include steady/burst/soak + cohorts (Pillars 4.1 & 4.2),
* include learning + promotion + rollback evidence (Pillar 4.3),
* include diagnosability and audit drill (Pillar 4.4),
* include budget envelope + cost receipt + idle-safe teardown (Pillar 4.5).

If any pillar is unproven, the mission verdict cannot be PASS, regardless of how many intermediate phases are “green.”

---

## 5. Proof model and claimability rules (anti-toy, anti-gaming)

This section defines the **rules of truth** for production-ready dev_full. It exists to prevent two common failure modes:

1. “We ran something and it looked green” (but can’t be defended), and
2. “We turned observed values into the standard” (so the standard stops meaning anything).

Everything in the road-to-production program must be evaluated against this proof model.

---

### 5.1 Definitions (what words mean in this program)

**Headline claim (production-ready dev_full):**
A single statement that becomes true only after the Production-Grade Run (mission) passes, producing a complete evidence pack.

**Supporting claim:**
A bounded, testable statement that supports the headline claim. Supporting claims map to the pillars (SLO hot path, replay safety, governed learning/promotion, auditability, cost control).

**Proof points (impact metrics):**
Quantitative measurements that show outcomes (latency p95/p99, lag p95/p99, error rate, MTTR, rollback time, audit response time, unit cost).

**Artifacts:**
Inspectable evidence objects (manifests, receipts, gate summaries, dashboards, drill bundles, lineage records, audit logs, cost receipts).

**Drills:**
Intentional failure-mode exercises that prove behavior under stress (rollback, replay integrity, lag recovery, schema evolution, dependency degrade, audit drill, cost guardrail drill).

**Evidence pack:**
A named bundle of artifacts + metrics outputs that can be referenced and reviewed later (runtime pack, ops/gov pack, data realism pack, mission pack).

**Blocker:**
A failure of a required gate/metric/artifact that prevents claimability. Blockers have codes, severity, a remediation path, and a rerun boundary.

---

### 5.2 Evidence bundle rule (minimum claimability requirement)

No supporting claim is claimable unless it has evidence in three categories:

**Minimum evidence bundle for any claim:**

1. **Metrics:** at least 2 relevant proof metrics
2. **Artifacts:** at least 1 inspectable artifact proving the mechanism
3. **Drills:** at least 1 drill proving behavior under failure or stress

**Recommended “senior-grade” bundle (Tier-0 claims):**

* 3–6 metrics (including at least one distribution metric p95/p99)
* 2–5 artifacts (gate outputs + dashboards + runbooks + lineage/audit records)
* 1–2 drills (one “correctness” drill and one “recovery/rollback” drill)

If a claim lacks any of these, it stays **HOLD_REMEDIATE** even if the system “seems to work.”

---

### 5.3 Claimability levels (L0–L4)

Each Tier-0 supporting claim is graded. This is how you talk honestly about Point X progression without overstating.

* **L0 — Not started:** No mechanism exists.
* **L1 — Implemented:** Mechanism exists but no meaningful evidence.
* **L2 — Tested:** Basic test pass exists; evidence pack partially complete.
* **L3 — Pressure-tested:** Proven under a declared envelope with realistic cohorts; drills executed; metrics reported as distributions.
* **L4 — Production-proven:** Sustained operation with SLO posture, incident learning, and repeatable auditability; error budget mindset (more than one run).

**Production-ready dev_full requirement:**

* Tier-0 runtime and ops/gov claims must be **at least L3**, and the mission run must PASS with **open_blockers=0**.
* L4 is not required for dev_full production-ready, but can be a later improvement.

---

### 5.4 Measurement surface rules (to stop “wrong metric” certification)

Every metric in any contract or scorecard must declare a **measurement surface**. You may not treat a component-internal throughput number as “platform throughput” unless it is explicitly mapped to the boundary.

**Approved measurement surfaces (examples):**

* `IG_ADMITTED_EVENTS_PER_SEC` (truth boundary throughput)
* `MSK_CONSUME_RATE_EVENTS_PER_SEC` (bus consumption rate)
* `FLINK_PROCESSED_EVENTS_PER_SEC` (stream compute rate)
* `DECISION_COMMITTED_PER_SEC` (decision output rate)
* `SINK_WRITTEN_RECORDS_PER_SEC` (archive/audit sink rate)

**Rules:**

1. **End-to-end claims require end-to-end surfaces.**
   If a claim is about “platform hot path SLO,” it must use surfaces that include the relevant boundaries (IG and/or decision commit), not just Flink internal counters.

2. **One metric ≠ one truth.**
   You must reconcile at least two surfaces (e.g., IG admitted vs decision committed) to ensure you’re not measuring a partial lane.

3. **Counters must be defined and reproducible.**
   Each metric must define:

   * numerator, denominator, unit, aggregation window
   * sampling method
   * where it is stored and how it is reproduced

---

### 5.5 Injection path rules (via_IG vs via_MSK)

To prevent accidental bypass certification, every run must declare how load is injected:

* **`via_IG`**: events are produced to the platform through the Ingestion Gate.

  * certifies: IG envelope behavior + idempotency truth + end-to-end hot path.
* **`via_MSK`**: events are injected directly into MSK topics (or downstream of IG).

  * certifies: streaming + RTDL + decision + sinks under load.
  * does **not** certify: IG rate limits, IG auth/envelope, idempotency store scaling.

**Hard rule:** You may only claim what the injection path covers.
If your run uses `via_MSK`, Tier-0 claims about IG throughput/latency must remain HOLD unless separately certified.

---

### 5.6 Anti-gaming rules (what makes runs “production-like”)

These rules stop “pass by cheating” behaviors.

**A) Minimum duration rules**

* Steady, burst, and soak must each meet minimum durations defined in the numeric contract.
* “Steady for 30 seconds” is not steady.
* “Soak for 2 minutes” is not soak.

**B) Minimum sample size rules**

* Each profile must meet minimum processed events (not attempted events).
* Replay window must be large enough to validate invariants (not a handful of events).

**C) Distribution rules**

* For latency and lag, you must report distributions:

  * p50, p95, p99 (minimum: p95 and p99)
* Averages are not acceptable for certification.

**D) Peak slice rule**

* At least one run must include a peak-like slice (from the 7d profile) or equivalent injected skew.

**E) Cohort realism rule**

* Certification runs must include at least:

  * duplicates cohort
  * out-of-order cohort
  * hot-key cohort
* If cohorts are omitted, the run cannot certify replay correctness or skew resilience.

**F) “Observed once” prohibition**

* You may not convert a single observed value into a threshold without:

  * declaring it as a baseline, and
  * declaring a policy target and guardband.

---

### 5.7 Blocker taxonomy (how failure is recorded and acted on)

Every failure to meet a gate produces a blocker record with:

* **Blocker code** (e.g., RC-B4 “profile thresholds not met”)
* **Severity** (mission-blocking vs improvement)
* **What failed** (metric name, threshold, observed value)
* **Measurement surface** (where it was measured)
* **Root cause hypothesis** (initial)
* **Allowed remediation actions** (what changes are permitted)
* **Rerun boundary** (what must be rerun to clear it)
* **Evidence links** (where the proof lives)

**Hard rule:** A blocker is cleared only when the rerun boundary produces evidence with the blocker absent. No “manual closure” without evidence.

---

### 5.8 Rerun boundaries (don’t rerun the world)

When something fails, you rerun only what is necessary, based on failure class:

**A) Wiring/infrastructure failures**

* Rerun only the smallest gate that validates the corrected wiring (IAM, handle, reachability).
* Do not rerun full soak to fix a missing permission.

**B) Throughput/lag failures**

* Rerun the affected load profile (steady/burst/soak) after remediation.
* Compare against the same profile with the same cohort mix.

**C) Correctness failures (replay/duplicates)**

* Rerun the replay/duplicate cohort window with the same inputs.
* Re-validate invariants (no double side effects).

**D) Learning leakage failures**

* Rerun the learning input readiness and dataset build steps.
* Do not proceed to training until leakage report is PASS.

**E) Audit failures**

* Rerun audit drill after fixing missing fields/lineage linkage.

**F) Cost failures**

* Rerun cost guardrail drill or mission teardown closure after fixing attribution/idle-safe behavior.

This keeps your iteration loop fast and avoids burning money.

---

### 5.9 “Status owner” rule (single authoritative truth)

At any moment, there must be one authoritative status source for production-ready dev_full progression (the gate program status file). No competing “it looks green” sources.

**Hard rule:** If a summary disagrees with the status owner, the summary is wrong until reconciled.

---

### 5.10 Final claimability rule (what “production-ready” cannot ignore)

Even if all intermediate gates are green, you do not declare production-ready unless:

* the mission run PASSes,
* all required evidence packs are present and readable,
* all mandatory drills are completed with recovery bounds met,
* and `open_blockers = 0`.

This is the rule that prevents “we’re ready because everything is green” drift.

---

## 6. Traceability matrix (mission → gates → evidence)

This section is the **anti-drift backbone** of the entire document. It ensures we do not “chase greens.” Every activity must map to:

* the **mission requirement**,
* the **pillar it supports**,
* the **gate(s) that prove prerequisites**,
* and the **evidence** (metrics + artifacts + drills) that make it claimable.

If a task cannot be mapped here, it is not on the road to production-ready (dev_full).

---

### 6.1 Mission requirements (canonical list)

The Production-Grade Run (Section 3) has these canonical requirements:

**MR-01** Mission charter pinned (window, as-of, maturity lag, injection path, budget)
**MR-02** Stream-view materialization exists for the mission window (Oracle → stream_view)
**MR-03** Ingestion truth boundary functions under load (if `via_IG`)
**MR-04** Streaming hot path sustains steady→burst→recovery→soak within envelope
**MR-05** Correctness under messiness (duplicates/out-of-order/hot keys) is proven
**MR-06** Replay/backfill integrity is proven (no double side effects, invariants pass)
**MR-07** Decision chain commits are durable and auditable (DF/AL/DLA + archive sink)
**MR-08** Case/labels outputs are written under writer-boundary rules (if in scope)
**MR-09** Learning is time-causal (no future rows) and produces dataset manifest/fingerprint
**MR-10** Training/eval produces lineage-complete candidate + eval vs baseline
**MR-11** Promotion corridor + ACTIVE resolution is governed; rollback is proven
**MR-12** Observability enables fast localization and audit answerability
**MR-13** Cost-to-outcome receipts exist and idle-safe teardown is proven
**MR-14** Final verdict PASS with `open_blockers = 0` and all evidence packs present

---

### 6.2 Mission requirements → Pillar mapping

| Mission Requirement | Pillar(s) Supported                          |
| ------------------- | -------------------------------------------- |
| MR-02, MR-03, MR-04 | 4.1 Hot path SLO-grade                       |
| MR-05, MR-06        | 4.2 Streaming correctness                    |
| MR-09, MR-10, MR-11 | 4.3 Governed learning + reversible promotion |
| MR-07, MR-12        | 4.4 Observable + auditable ops               |
| MR-13               | 4.5 Cost bounded + idle-safe                 |
| MR-14               | All pillars                                  |

---

### 6.3 Pillars → Tier-0 supporting claims (canonical set)

To keep this road minimal, we treat Tier-0 claims as the “spine”:

* **C-T0.1** Governed release corridor + rollback (promotion is reversible)
* **C-T0.2** SLO-grade online decision path (within declared envelope)
* **C-T0.3** Replay-safe streaming correctness (retries/duplicates/replays don’t corrupt truth)
* **C-T0.4** Observability + diagnosability (fast detection/localization)
* **C-T0.5** Audit-grade provenance + decision traceability (fast answerability)
* **C-T0.6** Cost-to-outcome control + idle-safe enforcement

Each mission requirement must map to at least one of these claims.

---

### 6.4 Traceability matrix: mission → gates → evidence (core table)

This table is the “do not drift” reference for Codex.

#### Legend

* **G1** Wiring/control-plane hardening baseline
* **G2** 7d Data realism & semantic readiness
* **G3A** Runtime operational certification pack
* **G3B** Ops/Gov operational certification pack
* **G4** Go-live rehearsal mission (escape velocity)

| Mission Req                                          | Claim(s)               | Gate(s) that must be green first | Required Evidence (metrics + artifacts + drills)                                                                                        |
| ---------------------------------------------------- | ---------------------- | -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| MR-01 Mission charter pinned                         | (Meta)                 | G1                               | mission_run_charter.json + readback proof; budget envelope present                                                                      |
| MR-02 Stream-view materialization exists             | C-T0.3, C-T0.4         | G1, G2                           | stream_sort_receipt + parity/readability; stream_view manifest; schema contract pass                                                    |
| MR-03 Ingestion truth boundary under load (`via_IG`) | C-T0.2, C-T0.3, C-T0.4 | G1, G2, G3A                      | IG admit rate (p95/p99), reject/quarantine rate, DDB hot partition signals; duplicates cohort proof; IG receipts/quarantine reason dist |
| MR-04 Hot path steady→burst→recovery→soak            | C-T0.2, C-T0.4, C-T0.6 | G1, G2, G3A                      | runtime scorecard distributions (latency/lag/errors/checkpoints); recovery time-to-stable; cost per unit for run                        |
| MR-05 Correctness under cohorts                      | C-T0.3                 | G2, G3A                          | cohort_manifest + cohort_results_summary; dedupe hit rate, duplicate-admission rate; late/out-of-order handling evidence                |
| MR-06 Replay/backfill integrity                      | C-T0.3                 | G2, G3A                          | replay drill report bundle; invariants pass (no double side effects); time-to-complete                                                  |
| MR-07 Decision chain durable + auditable             | C-T0.2, C-T0.5         | G1, G3A, G3B                     | decision outputs manifest; audit sink write proof; decision log completeness; append/readback proof                                     |
| MR-08 Case/labels writer-boundary correctness        | C-T0.3, C-T0.5         | G1, G2, G3A                      | writer-boundary probe evidence; reconciliation coverage; duplication safety for cases                                                   |
| MR-09 Time-causal learning inputs                    | C-T0.3, C-T0.5         | G2                               | leakage report PASS; as-of/maturity policy pinned; “no future rows” hard check evidence                                                 |
| MR-10 Train/eval lineage + eval vs baseline          | C-T0.1, C-T0.5         | G2, G3B                          | dataset manifest/fingerprint; MLflow lineage snapshot; eval_vs_baseline report; reproducibility check                                   |
| MR-11 Promotion + ACTIVE + rollback proven           | C-T0.1, C-T0.5         | G3B                              | transport proof (ack+readback hash); ACTIVE resolution snapshot; rollback drill report with bounded restore                             |
| MR-12 Observability and audit answerability          | C-T0.4, C-T0.5         | G3A, G3B                         | trace coverage; TTD/TTDiag; audit drill response time; runbooks linked to alerts                                                        |
| MR-13 Cost bounded + idle-safe                       | C-T0.6                 | G3A, G3B, G4                     | cost receipts; unit cost; guardrail drill; teardown residual scan clean; idle_safe=true                                                 |
| MR-14 Final PASS with open_blockers=0                | All                    | G4                               | final verdict artifact + readback; all evidence bundles present and readable                                                            |

---

### 6.5 Stop-the-line rules derived from traceability

These are the rules that prevent “green checklists” from replacing the mission:

1. **No G3A runtime certification without G2 data realism.**
   If you don’t know skew/dupes/out-of-order/join coverage, you can’t certify runtime correctness or SLO posture.

2. **No promotion/rollback claim without drill proof.**
   A corridor isn’t “governed” until rollback is executed and time-bounded.

3. **No replay-safety claim without a replay drill of meaningful size.**
   Micro replays do not count.

4. **No audit-ready claim without an audit drill.**
   If you can’t answer “what ran and why” from records within bound, the platform is not production-ready.

5. **No PASS verdict with any open blockers.**
   If a blocker exists, the platform is not production-ready, regardless of other green marks.

---

### 6.6 Required evidence pack list (for mission completion)

The mission is only claimable if all of these packs exist:

* **G1 Wiring Baseline Pack** (M1–M13 wiring stress green summary + baseline receipt)
* **G2 Data Realism Pack** (7d profile, join matrix, IEG decisions, monitoring baselines)
* **G3A Runtime Certification Pack** (scorecard run + runtime drills + cost snapshot)
* **G3B Ops/Gov Certification Pack** (promotion corridor + rollback drill + audit drill + runbooks)
* **G4 Mission Run Pack** (final verdict + consolidated evidence index + idle-safe closure)

---

### 6.7 How Codex must use this section (operational rule)

For any work item, Codex must answer in its implementation notes:

* Which **MR-xx** requirement does this advance?
* Which **claim(s)** does it strengthen?
* Which **gate** does it unblock?
* What **evidence artifact(s)** were produced, and where?
* What **blocker code(s)** were closed, and what rerun boundary is required?

If it can’t answer these, it’s likely doing busywork rather than moving toward production-ready.

---

## 7. Gate program overview (the road map)

This section defines the **only allowed path** to declare **production-ready (dev_full)**. It converts the mission specification (Section 3) and the proof model (Section 5) into a **fail-closed gate program**.

**Core rule:** A gate exists only to reduce risk for the Production-Grade Run. Passing gates is not the goal; passing the mission run is the goal.

---

### 7.1 Gate list and intent (G1–G4)

#### G1 — Wiring & control-plane hardening (foundation)

**Intent:** Prove the platform’s infrastructure wiring, identities, handles, evidence sinks, and orchestration are stable enough that failures observed later can be attributed to data-plane behavior rather than hidden wiring defects.
**Outcome:** “Wiring stable baseline” exists and can be referenced as a starting point for all later runs.

#### G2 — Data realism (7d) & semantic readiness

**Intent:** Prove you understand the real data content and can operate time-safely and meaningfully:

* cohort mix (skew/dupes/out-of-order),
* join coverage (what actually joins),
* RTDL allowlist (what is safe at runtime),
* IEG meaningful graph decisions (what is stable enough to store),
* monitoring baselines (what “normal” looks like).
  **Outcome:** A pinned **Data Realism Pack** that becomes the source of truth for runtime load campaigns and learning windows.

#### G3 — Operational certification (alive platform packs)

Split into two certification packs that together prove “alive platform”:

* **G3A Runtime Certification Pack:** SLO hot path + streaming correctness under load and drills.
* **G3B Ops/Gov Certification Pack:** promotion corridor, rollback, auditability, runbooks/alerts, cost governance.
  **Outcome:** Tier-0 claims reach at least L3 (pressure-tested) within the declared dev_full envelope, and evidence packs are complete.

#### G4 — Go-live rehearsal (escape velocity gate)

**Intent:** Prove the platform can complete an end-to-end mission-like operation with controlled change and incident recovery:

* continuous operation,
* at least one controlled deploy/promotion,
* at least one intentional incident/drill and recovery,
* bounded cost and idle-safe closure.
  **Outcome:** A single “mission run” PASS with `open_blockers=0` and a complete evidence pack.

---

### 7.2 Gate entry/exit conditions (fail-closed)

Each gate has strict entry and exit criteria. A gate is **not** considered complete unless its required evidence pack is produced and readable.

#### Entry rule (for any gate)

To begin a gate:

* the previous gate must be marked PASS (or explicit waiver must exist and be mission-safe),
* a run charter for the gate must be pinned (window, injection path, budgets as applicable),
* required observability surfaces must be available (so failures are diagnosable).

#### Exit rule (for any gate)

A gate exits PASS only when:

* all required artifacts for that gate exist and are readable,
* all required thresholds for that gate are satisfied,
* `open_blockers=0` for that gate’s blocker register,
* and the gate’s verdict artifact is published and readback-verified.

If thresholds are not met but the evidence is complete, the gate exits **HOLD_REMEDIATE** with explicit blockers and rerun boundaries.

---

### 7.3 Allowed progression rules (what must be done before next gate)

These are the non-negotiable progression constraints that prevent “greens” from skipping the mission-critical work.

#### Rule P1 — G1 must exist before anything else is trusted

No runtime or learning certification can be treated as meaningful unless a wiring baseline exists. If wiring isn’t stable, bottleneck work becomes guesswork.

#### Rule P2 — G2 must precede runtime certification (G3A)

No operational runtime certification may be declared without data realism:

* you cannot claim replay safety without knowing real duplicate/out-of-order/skew rates,
* you cannot set a credible envelope without observing real cohort distributions.

#### Rule P3 — G3A and G3B are both required before G4

You may not attempt the go-live rehearsal mission if:

* the hot path is not pressure-tested (G3A), or
* rollback/audit/runbooks are not proven (G3B).

#### Rule P4 — Numeric contracts must be activatable, not “observed”

Before G3A/G3B runs are considered certification, the numeric contracts must be:

* policy-driven (targets and ceilings pinned),
* measurement-surface correct,
* anti-gaming enforced,
* and contain no `TBD` fields required for the gate.

#### Rule P5 — No mission PASS with any open blockers

The mission gate (G4) is an absolute closure gate:

* any open blocker implies the platform is not production-ready.

---

### 7.4 Stop-the-line rules (when to halt and not proceed)

These rules protect you from burning time/money on runs that cannot produce claimable evidence.

**S1: Contract not activatable → stop.**
If a required numeric contract section contains `TBD` or missing metrics, do not run certification. Fix the contract or metric emission first.

**S2: Measurement surface ambiguous → stop.**
If throughput/latency metrics don’t specify where they were measured (IG vs MSK vs Flink vs decision commit), do not certify. Emit correct counters first.

**S3: Data realism incomplete → stop.**
If you have not produced join coverage/skew/duplicate/out-of-order profiles, do not perform runtime certification. Produce the Data Realism Pack first.

**S4: Replay/rollback/audit drills missing → stop.**
If you can’t run the drills and produce drill bundles, you can’t claim production-ready.

**S5: Cost/idle-safe not enforceable → stop.**
If teardown leaves residues or cost guardrails cannot be verified, do not proceed to mission runs.

---

### 7.5 Rerun scope discipline (don’t rerun the world)

This program is designed to move fast. When a gate fails:

* Only rerun the minimal boundary required by the blocker code.
* Always re-run with the same declared profile and cohort manifest unless the blocker explicitly requires changing the profile.

**Examples**

* IG throttles too low → rerun only IG steady/burst profile, not full mission.
* Flink checkpoint failures → rerun hot-path profile and checkpoint recovery drill.
* Audit fields missing → rerun audit drill after fixing record emission, not full soak.

This discipline keeps cost controlled and increases the quality of evidence.

---

### 7.6 Global completion rule (production-ready dev_full declaration)

Dev_full is declared **production-ready** only when all of the following are true:

1. **G1 PASS** (wiring baseline established).
2. **G2 PASS** (7d data realism pack established and pinned).
3. **G3A PASS** (runtime operational certification pack complete and thresholds met).
4. **G3B PASS** (ops/gov certification pack complete and thresholds met).
5. **G4 PASS** (go-live rehearsal mission run PASS, `open_blockers=0`, all evidence packs present).

Any other definition is a drift trap.

---

## 8. Gate G1: Wiring & control-plane hardening (foundation)

G1 exists to answer one question only:

> “Is the platform’s wiring stable enough that failures observed later are attributable to data-plane behavior rather than hidden infrastructure defects?”

This gate does **not** certify throughput or “bank-grade scale.” It certifies the **control plane and substrate wiring** so the next gates (data realism and operational cert) are not guesswork.

---

### 8.1 Intent (what G1 proves and what it does not)

#### G1 proves

* The platform can be **provisioned, started, gated, and torn down** using the dev_full substrate without hidden drift.
* The platform’s **truth boundaries and evidence sinks** are operational:

  * Oracle boundary is readable in the intended way
  * IG boundary is reachable and fail-closed
  * MSK topics are reachable with correct identities
  * Stream compute can be activated and produces run-scoped evidence
  * State stores are reachable (Aurora/Redis)
  * Evidence and archive sinks are writable/readable (S3)
* The platform’s **run-control authority** is stable:

  * Step Functions authority surfaces exist
  * run-scoped artifacts are written/read back deterministically
  * no “silent pass” when artifacts are missing

#### G1 does not prove

* Sustained production throughput or SLO-grade behavior under load.
* Replay correctness under large windows.
* Meaningful IEG content derived from real data semantics.
* Model quality or monitoring thresholds derived from data.

Those are explicitly deferred to G2 and G3.

---

### 8.2 Entry conditions (before running G1 validation)

G1 may be entered only if:

* dev_full infrastructure is deployed from IaC (Terraform applied cleanly with no drift),
* the current “authoritative wiring stress status” file exists (single status owner),
* and a baseline run charter (window + run ids + pinned handles) is declared.

---

### 8.3 Required evidence pack: “Wiring Stable Baseline Pack”

G1 is satisfied by producing (or referencing) a single baseline evidence pack containing:

#### A) Substrate and identity readiness

* IaC apply evidence (core + streaming + runtime + data_ml + ops stacks)
* State locking proof (no concurrent drift)
* Identity posture proofs:

  * roles/policies present
  * secrets access path correct (no plaintext)
  * VPC reachability where required

#### B) Oracle boundary readiness (read-only posture)

* Oracle store readability checks for required inputs
* Explicit statement of boundary: runtime is not allowed to “scan the future”

#### C) IG boundary readiness (truth boundary wiring)

* IG health (200/202)
* Auth fail-closed (valid key passes, invalid/missing fails)
* Envelope exists (payload size limit, timeouts, throttles)
* Idempotency store reachable and TTL posture proven
* Receipt/quarantine sinks reachable

#### D) Bus and streaming wiring

* MSK topics reachable by intended identities
* Streaming lane activation succeeds (application RUNNING)
* Basic checkpoint wiring exists (checkpoint path configured)
* Lag counters and consumer group identity visible

#### E) State store connectivity

* Aurora reachable and basic read/write probe passes
* Redis reachable and basic get/set probe passes
* Connection posture (pool limits, timeouts) pinned or at least visible

#### F) Evidence sink wiring (run control and archive)

* S3 evidence bucket writable and readback verified
* Archive sink writable and readback verified
* “No missing required artifact” rule enforced (fail-closed)

#### G) Teardown and idle-safe wiring

* Residual scan runs and is clean (or explicitly waived with reason)
* Idle-safe posture verified (no leftover endpoints or runaway compute)

**Deliverable artifact:**
`g1_wiring_stable_baseline_pack.json` containing:

* baseline run id(s)
* links to each required artifact
* PASS/FAIL per wiring category above
* open_blockers list (must be empty for G1 PASS)

---

### 8.4 “Single baseline run” rule (the anchor you carry forward)

G1 must nominate **one** baseline run (or run set) as the reference for later gates.

This matters because:

* later failures can be compared against a known-good wiring state,
* and you can prove regressions are not due to wiring drift.

**Baseline anchor fields (required):**

* `baseline_platform_run_id`
* `baseline_scenario_run_id`
* `baseline_manifest_fingerprint={manifest_fingerprint}`
* `baseline_handle_set_id` (or equivalent)
* `baseline_evidence_root`

---

### 8.5 Blocker taxonomy for G1 (what counts as “wiring not stable”)

G1 uses a limited blocker set. If any appear, you must remediate before proceeding.

**Examples**

* **G1-B1**: missing required artifact (readback failed)
* **G1-B2**: IAM/permission denial on critical lane
* **G1-B3**: MSK topic unreachable or auth failure
* **G1-B4**: streaming app cannot start or cannot checkpoint
* **G1-B5**: Aurora/Redis unreachable or unstable
* **G1-B6**: teardown leaves residuals / idle-safe not verified
* **G1-B7**: inconsistent run-scoped identity (collision, non-determinism)

Each blocker must specify:

* minimal remediation
* rerun boundary (usually only the failed probe, not the full chain)

---

### 8.6 Exit criteria / DoD (G1 PASS)

G1 is PASS only when:

1. `g1_wiring_stable_baseline_pack.json` exists and is readable.
2. Every wiring category A–G is marked PASS.
3. `open_blockers = 0`.
4. The baseline run anchor is pinned and referenced by subsequent gates.
5. Teardown/idle-safe is verified (or any waiver is explicit, time-bounded, and not mission-critical).

If any condition fails, G1 exits as **HOLD_REMEDIATE**, and you may not proceed to G2/G3 until the blockers are cleared.

---

### 8.7 Notes for implementer behavior (Codex rules for G1)

* G1 is not a performance contest. Do not inflate rates here.
* Do not widen scope: the objective is wiring stability, not data realism.
* Any wiring change after G1 PASS must either:

  * re-run the minimal G1 probes affected, or
  * declare the baseline invalid and establish a new baseline pack.

---

## 9. Gate G2: Data realism (7d) & semantic readiness

G2 is the gate that kills “toy project” vibes for real. It answers the questions your wiring stress **cannot** answer:

* **Can the platform move voluminous data end-to-end without bursting?**
* **Does the platform derive meaningful, time-safe, and stable insights from real content (IEG/OFP/learning), not just schemas?**
* **Can we define a credible operational envelope and cohort mix from observed reality (skew/dupes/out-of-order), instead of guessing?**

G2 produces a single output: the **Data Realism Pack**, which becomes the authoritative input to:

* the **mission run charter** (Section 3),
* the **runtime envelopes** (RC2-S / RC2-L),
* the **cohort manifest** (duplicates/out-of-order/hot keys),
* the **IEG graph choices**, and
* the **monitoring baselines**.

If G2 is incomplete, **G3 cannot be claimed**—because you don’t yet know what you’re certifying against.

---

### 9.1 Intent

G2 exists to transform “we have a dataset schema” into “we understand what’s inside the data well enough to operate and learn safely.”

G2 must:

1. **Measure reality** on a representative 7-day window:

   * volumes, time behavior, key coverage, duplicates, out-of-order, skew, payload distribution
2. **Validate joinability** of the platform’s intended join graph (what actually joins, fanout, missingness)
3. **Pin time-safe runtime inputs** (RTDL allowlist) and forbid future/leaky surfaces
4. **Define meaningful IEG** (what entity relationships are stable enough to store and project)
5. **Define monitoring baselines** (what “normal” looks like for ops + ML signals)
6. **Define a load campaign spec** that reflects reality (not synthetic “clean” cohorts)
7. **Define learning readiness constraints**:

   * time-causal dataset windows
   * label maturity distribution
   * leakage guardrails that will actually hold on real rows

This is not “EDA.” This is **production semantics realization**.

---

### 9.2 Window charter and selection rules (7d)

#### 9.2.1 The window you must pin

G2 must pin a single 7-day charter:

* `manifest_fingerprint={manifest_fingerprint}`
* `scenario_id`
* `window_start_ts_utc`
* `window_end_ts_utc` (window_end = window_start + 7d)
* `as_of_time_utc` (default: `window_end_ts_utc`)
* `label_maturity_lag` (initially TBD; becomes pinned by G2 outputs)
* `data_source_set` (which tables are included)

**Output artifact:** `g2_window_charter.json` (immutable after publication)

#### 9.2.2 Which tables are in scope (by role)

Use the Data Engine interface roles as binding truth:

**Runtime traffic (streamed):**

* behavioural event streams (`s2_event_stream_baseline_6B`, `s3_event_stream_with_fraud_6B`) 

**Runtime join context (RTDL-eligible context):**

* flow anchors (`s2_flow_anchor_baseline_6B`, `s3_flow_anchor_with_fraud_6B`)
* arrival skeleton (`arrival_events_5B`)
* arrival entities (`s1_arrival_entities_6B`) 

**Batch-only (explicitly forbidden in RTDL):**

* `s1_session_index_6B` (contains session_end_utc / arrival_count, i.e., future aggregation) 

**Offline truth products (learning/eval only):**

* `s4_event_labels_6B`, `s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B`, `s4_case_timeline_6B` 

#### 9.2.3 Selection rules (avoid biased weeks)

* The 7-day window must include at least one “busy” slice (peak-ish period) and one “quiet” slice (to capture seasonality and load variation).
* The 7-day window must be repeatable (you will rerun profile computations after remediation).

---

### 9.3 Reality profile (7d): what must be measured per table

For each in-scope table, produce a standard profile. Every metric must include:

* the exact filter used (`window_start_ts_utc`, `window_end_ts_utc`),
* the measurement surface (table name + partitioning used),
* and summary statistics (not raw dumps).

#### 9.3.1 Time behavior (critical for streaming realism)

For tables with `ts_utc`:

* min/max `ts_utc`
* distribution of time gaps (periods with no events)
* outlier density (spikes)
* same-timestamp density (how many rows share the same second)
* required stable tie-break keys (if timestamps collide heavily)

For truth tables without `ts_utc`:

* derive `ts_utc` by joining to live tables (as your data plan describes) and record:

  * derivation join success rate
  * derived-time min/max
  * derived-time skew/outliers 

**Why this matters:** You can’t pretend a stream is “time sorted” if the data has extreme timestamp collisions without deterministic secondary ordering.

#### 9.3.2 Key coverage & stability (drives feasibility)

For each candidate key used by RTDL/IEG/OFS joins (examples: `flow_id`, `merchant_id`, `arrival_seq`, `event_seq`, plus any entity IDs present):

* % present / % null
* distinct count
* churn rate (new IDs/day)
* reuse rate (events per ID)
* collision indicators (same ID maps to too many unrelated flows)

**Why this matters:** A schema key that is missing 30% of the time will create sparse projections and meaningless entity graph edges.

#### 9.3.3 Duplicate and near-duplicate behavior

For each table:

* duplicate rate for the table’s natural key (e.g., `flow_id,event_seq` for event streams; `merchant_id,arrival_seq` for arrival skeleton)
* near-duplicate rate: same natural key but different payload signature (hash mismatch)
* concentration of duplicates by key (do duplicates cluster on hot keys?)

**Why this matters:** replay safety and idempotency claims depend on whether duplicates exist and how they behave in the wild.

#### 9.3.4 Skew / hot key profile (the RTDL killer)

For partition-candidate keys (flow_id, merchant_id, entity IDs):

* top 0.1% keys share of total volume
* max events per key
* Gini-like inequality indicator (even rough)
* key distribution over time (do hot keys stay hot or rotate?)

**Why this matters:** skew drives partition imbalance → lag spikes → missed SLO, even if average EPS looks fine.

#### 9.3.5 Payload size distribution (cost + latency driver)

For traffic/event payloads:

* p50/p95/p99 payload size
* max payload size
* rate of near-limit payloads

**Why this matters:** envelope settings (IG payload limits, timeouts) must match reality; otherwise you’ll quarantine half the world.

**Output artifacts (required):**

* `g2_table_profile_<table>.json` (one per table)
* `g2_profile_rollup.json` (global rollup for quick review)

---

### 9.4 Join coverage matrix: “does the join graph actually work?”

This is non-negotiable. Your interface doc pins the join map; G2 must measure whether it’s healthy in real content. 

#### 9.4.1 Mandatory joins to validate

At minimum, validate:

1. **Event stream ↔ Flow anchor**
   `s3_event_stream_with_fraud_6B` ↔ `s3_flow_anchor_with_fraud_6B`
   Keys: `seed, manifest_fingerprint, scenario_id, flow_id` 

2. **Flow anchor ↔ Arrival skeleton**
   `s3_flow_anchor_with_fraud_6B` ↔ `arrival_events_5B`
   Keys: `seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq` 

3. **Arrival skeleton ↔ Arrival entities**
   `arrival_events_5B` ↔ `s1_arrival_entities_6B`
   Keys: `seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq` 

4. **Truth labels ↔ Event stream** (learning-only)
   `s4_event_labels_6B` ↔ `s3_event_stream_with_fraud_6B`
   Keys: `seed, manifest_fingerprint, scenario_id, flow_id, event_seq` 

#### 9.4.2 Metrics required per join

For each join:

* unmatched rate (left rows without right match)
* fanout distribution (1→many)
* duplicate key rate on each side
* join stability indicators (collisions)
* time alignment sanity (if relevant)

#### 9.4.3 Pass criteria for “joinability”

G2 does **not** require perfect joins. It requires that any weakness is made explicit and closed with a decision:

* If unmatched rate is high:

  * decide whether to drop, quarantine, or compute fallback features
* If fanout is high:

  * decide whether to cap fanout, re-key, or move join offline
* If collisions exist:

  * decide whether to treat as data quality issue (quarantine) or adjust key semantics

**Output artifacts (required):**

* `g2_join_matrix.json` (all joins, metrics, verdicts)
* `g2_join_decisions.md` (human-readable decisions + implications)

---

### 9.5 RTDL allowlist: time-safe runtime surfaces only

This is where you enforce the “no future Oracle access” rule in operational terms: runtime only sees time-safe inputs.

#### 9.5.1 Dataset allowlist/denylist

Produce and pin:

* **Allowed in RTDL:**

  * event streams
  * flow anchors
  * arrival skeleton/entities
* **Forbidden in RTDL:**

  * session_index
  * all `s4_*` truth products
  * any derived aggregate that implies future knowledge

#### 9.5.2 Field-level allowlist

Even within allowed datasets, some fields may encode future aggregation or post-hoc truth. Those must be forbidden at runtime even if the dataset is allowed.

**Output artifacts:**

* `g2_rtdl_allowlist.yaml` (datasets + fields allowed)
* `g2_rtdl_denylist.yaml` (explicitly forbidden datasets/fields)
* `g2_time_causality_rules.md` (the law: event_ts ≤ now, truth delayed)

---

### 9.6 IEG realism decisions (meaningful entity graph, not theoretical)

This is where you answer: “what entity relationship is meaningful to store?”

#### 9.6.1 Candidate entity extraction

From `s1_arrival_entities_6B` (and any other entity-bearing surfaces), enumerate all entity-like identifiers present.

For each candidate entity ID:

* coverage (% events with this ID)
* churn (new IDs/day)
* reuse distribution (events per ID)
* mega-node risk (degree distribution)
* collision signals (same ID appears across too many unrelated flows)

#### 9.6.2 Edge candidates and stability

Define candidate edges based on fields that link IDs (e.g., device→account, IP→device, account→instrument, merchant→terminal). Then measure:

* edge coverage
* edge churn (does mapping flip?)
* component size distribution (connected components)
* whether edge introduces mega-components

#### 9.6.3 Decisions you must pin

G2 must produce:

* **Minimum viable node set**
* **Minimum viable edge set**
* **TTL/state retention policy** for edges and derived projections
* **Skew mitigation policy** for hot keys (salting/capping/side path)

**Output artifacts:**

* `g2_ieg_node_catalog.json`
* `g2_ieg_edge_catalog.json`
* `g2_ieg_graph_decisions.md` (what we will store and why)
* `g2_ieg_state_budget.json` (TTLs, size expectations, anti-blowup rules)

---

### 9.7 Archive/audit routing realism (timely, queryable, non-blocking)

Your platform must be able to persist truth without choking the hot path.

#### 9.7.1 What must be persisted

From a production posture, define which categories must land durably:

* admitted traffic (or a minimally sufficient subset)
* decisions + actions
* audit trail events
* minimal projection outputs required for replay/audit

#### 9.7.2 Storage layout decisions

Pin:

* partitioning scheme (event_date/hour)
* target file sizes (avoid tiny files)
* sink flush/rotation posture (if using connectors)
* failure posture (DLQ/quarantine behavior for sink failures)

#### 9.7.3 Backpressure risk assessment

Use the 7d profile to estimate:

* bytes/day
* peak bytes/hour
* sink throughput requirements

**Output artifacts:**

* `g2_archive_layout_spec.md`
* `g2_sink_backpressure_risk.json`
* `g2_audit_fields_required.yaml` (the minimum for audit drill)

---

### 9.8 Learning realism inputs (label maturity, availability, and time-causal feasibility)

This makes learning “real” instead of schema-driven.

#### 9.8.1 Label availability and maturity distribution

For truth tables (`s4_*`), compute:

* % of events with labels
* label latency distribution (how long after event time labels become “knowable”)
* maturity lag candidates (p50/p90/p95)

Then decide:

* initial `label_maturity_lag` for dev_full production-ready runs
* whether learning uses only an earlier slice of the 7 days (common and fine)

#### 9.8.2 Time-causal feasibility checks

Prove:

* events/features are bounded by `as_of_time`
* truth is bounded by `as_of_time - maturity_lag`
* “no future rows” checks are executable and will fail-closed

**Output artifacts:**

* `g2_label_maturity_report.json`
* `g2_learning_window_spec.json` (as_of + maturity + eligible slice)
* `g2_leakage_policy.md` (what is forbidden, how checked)

---

### 9.9 Outputs: the Data Realism Pack (required artifacts + acceptance)

G2 PASS requires publishing a complete, readable pack:

#### 9.9.1 Required artifacts

1. `g2_window_charter.json`
2. Per-table profiles: `g2_table_profile_*.json`
3. `g2_profile_rollup.json`
4. `g2_join_matrix.json` + `g2_join_decisions.md`
5. `g2_rtdl_allowlist.yaml` + `g2_rtdl_denylist.yaml`
6. IEG decisions: catalogs + graph decisions + state budget
7. Archive/audit specs: layout + backpressure risk + required audit fields
8. Learning realism: label maturity report + learning window spec + leakage policy
9. `g2_monitoring_baselines.json` (derived “normal” ranges for key signals)
10. `g2_load_campaign_seed.json` (steady/burst/soak proposal + cohort mix derived from reality)

#### 9.9.2 Acceptance rules (G2 PASS)

G2 is PASS only when:

* all required artifacts exist and are readable
* join matrix exists and every mandatory join has a verdict and a decision (no “unknown”)
* RTDL allowlist/denylist is pinned (time-safe runtime surfaces)
* IEG decisions are explicit (nodes, edges, TTL/state budget, skew policy)
* label maturity and learning window are pinned (no future access enforceable)
* monitoring baselines exist (so G3 alerts aren’t guessed)
* any discovered risk is either:

  * mitigated with a pinned design decision, or
  * recorded as a blocker with a remediation path and rerun boundary

---

### 9.10 Exit criteria / DoD (G2 PASS vs HOLD)

**G2 PASS** when:

* Data Realism Pack is complete and readable
* `open_blockers = 0`
* every “unknown” has been converted into a pinned decision or an explicit blocker that is resolved
* and the outputs are referenced by G3 charter generation (runtime envelope + cohort manifest + learning window spec)

**G2 HOLD_REMEDIATE** when:

* key joins are unusable and no mitigation decision exists
* skew/hot keys are extreme and no mitigation policy exists
* label maturity makes learning impossible and no window adjustment is defined
* monitoring baselines are missing (forcing guessed thresholds)
* any artifact is missing/unreadable (fail-closed rule)

---

### Practical note: why G2 is the unlock

After G2, you stop guessing:

* your load campaign becomes reality-derived
* your IEG becomes defensible (not arbitrary)
* your learning corridor becomes truly time-causal
* your monitoring thresholds become baseline-derived
* and your operational certification becomes meaningful

---

## 10A. Runtime operational certification pack (G3A)

G3A is where dev_full becomes **alive** in a production-shaped way. It proves Tier-0 runtime claims under a declared envelope using:

* a scorecard run (steady → burst → recovery → soak),
* realistic cohorts (dupes/out-of-order/hot keys),
* mandatory runtime drills,
* and deterministic evidence bundles.

**Hard rule:** G3A is not allowed to run (as certification) unless G2 PASS is complete, because the runtime envelope and cohorts must be reality-derived.

---

### 10A.1 Intent and scope (what G3A certifies)

G3A certifies the runtime-facing Tier-0 claims:

* **T0.2 SLO-grade online decision path** within the declared `RC2-S` envelope
* **T0.3 Replay-safe streaming correctness** under realistic cohorts and replay drills
* **T0.4 Runtime observability & diagnosability** (runtime slice)
* **T0.6 Runtime cost control** (unit cost + cost guardrail + idle-safe closure)

G3A does not claim:

* business KPI improvements (fraud capture)
* multi-region HA
* “bank-scale EPS” unless explicitly declared in the envelope

---

### 10A.2 Entry conditions (G3A may start only if)

1. **G1 PASS** baseline exists (wiring stable baseline pack pinned).
2. **G2 PASS** data realism pack exists and is referenced by this run charter:

   * load campaign seed (steady/burst/soak proposal)
   * cohort definitions (dupes/out-of-order/hot keys)
   * monitoring baselines
   * learning window spec (as-of/maturity) if learning is included in the same run
3. Runtime numeric contract section **RC2-S is activatable**:

   * no required `TBD` thresholds
   * measurement surfaces declared per metric
4. Observability surfaces exist:

   * correlation propagation is enabled
   * dashboards/queries needed for scorecard metrics are available

If any condition fails, G3A must exit `HOLD_REMEDIATE` without burning money.

---

### 10A.3 RC2-S vs RC2-L envelopes (how envelopes are used)

#### RC2-S (required envelope)

* This is the dev_full **operational envelope** you must meet to call dev_full production-ready.
* It is calibrated from G2 reality and recent stable runs.
* It must include: steady, burst, recovery, soak, replay window sizes, sample minima, cohort mix.

#### RC2-L (stretch envelope)

* This is an aspirational envelope.
* It must not block G3A PASS unless explicitly stated.
* It is allowed to remain partially TBD while you achieve production-ready in RC2-S.

**Rule:** The scorecard run must explicitly state which envelope it is claiming (RC2-S required).

---

### 10A.4 Scorecard run spec (steady → burst → recovery → soak)

G3A requires a single “canonical scorecard run” whose structure is fixed and repeatable.

#### Phase 0: Preflight

* Verify key dependencies are reachable:

  * IG (if via_IG), MSK, Flink apps, Aurora, Redis, sink paths, evidence store
* Confirm correlation propagation is on.
* Confirm cost budget envelope is declared.

**Output:** `g3a_preflight_snapshot.json`

#### Phase 1: Steady

* Inject load at `RC2-S.steady_rate` for `RC2-S.steady_duration`.
* Require minimum processed event count (not attempted count).

**Outputs:**

* `g3a_scorecard_steady.json`
* `g3a_component_health_steady.json`

#### Phase 2: Burst

* Increase load to `RC2-S.burst_rate` (or multiplier) for `RC2-S.burst_duration`.
* Record backpressure behavior, lag growth, and error rates.

**Outputs:**

* `g3a_scorecard_burst.json`
* `g3a_component_health_burst.json`

#### Phase 3: Recovery

* Return to steady (or reduced) load.
* Measure time-to-return-to-stable for:

  * lag back under threshold
  * p95/p99 latency stabilized
  * error rates normalized

**Outputs:**

* `g3a_scorecard_recovery.json`
* `g3a_recovery_bound_report.json`

#### Phase 4: Soak

* Maintain operation for `RC2-S.soak_duration`.
* Detect leaks/backlog creep/sink backpressure/cost drift.

**Outputs:**

* `g3a_scorecard_soak.json`
* `g3a_soak_drift_report.json`

#### Consolidated scorecard

* Produce a single human-readable summary:

  * distributions p50/p95/p99
  * thresholds and PASS/FAIL
  * component attribution

**Output:** `g3a_scorecard_report.md`

---

### 10A.5 Cohort realism requirements (mandatory for G3A)

G3A must include cohorts defined by G2:

* **Duplicates cohort** (retry-like behavior)
* **Out-of-order cohort** (late events / ordering uncertainty)
* **Hot-key cohort** (skew pressure)
* **Payload extremes cohort** (near-limit sizes)
* **Mixed event type cohort** (representative mix)

Each cohort must be described and measured.

**Outputs:**

* `g3a_cohort_manifest.json`
* `g3a_cohort_results.json`
* cohort-specific deltas (lag/latency/errors/quarantine)

**Hard rule:** No cohort → no replay/correctness claimability.

---

### 10A.6 Required runtime metrics (what must be measured, and where)

Every metric row must declare:

* **measurement surface** (IG-admitted, MSK-consumed, Flink-processed, decision-committed, sink-written)
* **distribution requirement** (p50/p95/p99 where applicable)
* **threshold** from the numeric contract

#### Minimum Tier-0 runtime metrics families

**Hot path (T0.2)**

* end-to-end decision latency p95/p99 (boundary defined)
* error/timeout rate
* availability posture during run (if tracked)
* recovery-to-stable time

**Streaming correctness & health (T0.3)**

* consumer lag p95/p99
* checkpoint success rate + checkpoint duration p95
* dedupe hit rate + duplicate-admission rate
* quarantine rate + top reasons distribution

**Observability (T0.4 runtime slice)**

* correlation/trace coverage %
* time-to-detect / time-to-diagnose for induced incidents (from drills)

**Cost (T0.6 runtime slice)**

* cost per unit (cost per N events processed) for the run
* budget adherence for the run
* idle burn post-run (verified in closure)

**Hard rule:** If a required metric is missing, the run fails closed with a blocker (no “PASS by omission”).

---

### 10A.7 Mandatory runtime drills (must be executed and bundled)

G3A requires runtime-level failure-mode drills. Each drill must produce:

* scenario definition
* expected behavior
* observed timeline and outcomes
* recovery bound results
* integrity checks
* artifact links

#### Required drills

1. **Replay/backfill integrity drill**

   * Replay a bounded window sized by contract
   * Prove invariants:

     * no double side effects (decisions/cases/audit)
     * consistent counts/aggregates
       **Output:** `g3a_drill_replay_integrity.json`

2. **Lag spike + recovery drill**

   * Induce lag/backpressure (controlled)
   * Prove:

     * detection + localization
     * recovery within bound
       **Output:** `g3a_drill_lag_recovery.json`

3. **Schema evolution drill**

   * Compatible change accepted
   * Incompatible change blocked/quarantined
     **Output:** `g3a_drill_schema_evolution.json`

4. **Dependency degrade drill**

   * Simulate a dependency failure/latency spike (Aurora/Redis/feature retrieval if applicable)
   * Prove degrade mode keeps safe bounded operation
     **Output:** `g3a_drill_dependency_degrade.json`

5. **Cost guardrail + idle-safe drill**

   * Verify cost thresholds and post-run teardown/idle-safe posture
     **Output:** `g3a_drill_cost_guardrail.json`

**Rule:** Drill reports must include the measured TTD/TTDiag and recovery bound.

---

### 10A.8 Evidence bundle schema + naming + deterministic paths

To make evidence reusable for CV/portfolio claims, G3A must publish a deterministic bundle.

#### Required bundle root

* `evidence/dev_full/production_ready/g3a_runtime/<platform_run_id>/`

#### Required index

* `g3a_runtime_evidence_index.json` containing:

  * run charter reference
  * scorecard artifacts list
  * drill artifacts list
  * cohort artifacts list
  * metric extraction queries/definitions references
  * final PASS/FAIL verdict fields
  * open blockers list

#### Required final verdict

* `g3a_runtime_verdict.json` with:

  * `overall_pass` boolean
  * `verdict` (`PASS` or `HOLD_REMEDIATE`)
  * `open_blockers` count and list
  * `next_gate` suggestion (G3B or remediation)

**Hard rule:** If the index is missing or unreadable, the run cannot be considered certification.

---

### 10A.9 Exit criteria / DoD (G3A PASS)

G3A is PASS only if:

1. Scorecard run completed (steady/burst/recovery/soak) with required durations and sample minima.
2. All required metrics are present, measured on correct surfaces, and satisfy RC2-S thresholds.
3. All mandatory cohorts were included and cohort results are published.
4. All mandatory drills executed and their recovery bounds/integrity checks pass.
5. Cost envelope adherence is proven and idle-safe closure is verified.
6. `open_blockers = 0` in `g3a_runtime_verdict.json`.
7. Evidence bundle index exists and references all required artifacts.

If any condition fails, G3A exits `HOLD_REMEDIATE` with explicit blockers and rerun boundaries.

---

### 10A.10 Common “waste time” traps (explicitly forbidden)

* Re-running full soak when the blocker is a missing metric emission.
* Using Flink internal throughput as “platform EPS” when injection path is via_IG.
* Certifying without cohorts because it “looks stable.”
* Treating tiny replay windows as replay certification.
* Adjusting thresholds to match observed values without explicit policy justification.

---

## 10B. Ops/Gov operational certification pack (G3B)

G3B proves the platform is **operable and governable** under production-like expectations. This is the part that prevents Codex (or anyone) from claiming “production-ready” just because the hot path can process data.

G3B certifies Tier-0 ops/governance claims:

* **T0.1** Governed release/promotion corridor + rollback (reversible change)
* **T0.5** Audit-grade provenance + decision traceability (fast answerability)
* **T0.4** Observability governance slice (alerts/runbooks/escalation posture, not just metrics)
* **T0.6** Cost governance slice (budget envelopes, cost-to-outcome receipts, idle-safe enforcement)

**Hard rule:** G3B must be executed on the same dev_full substrate and must produce durable evidence bundles. Paper policies do not count.

---

### 10B.1 Entry conditions (G3B may start only if)

1. **G1 PASS** baseline exists (wiring stable).
2. **G2 PASS** exists (data realism pinned; audit fields and monitoring baselines defined).
3. **G3A is at least HOLD with complete metrics surfaces** (you can run G3B before G3A PASS, but not if the platform cannot produce required evidence at all).
4. Ops/Gov numeric contract sections are activatable:

   * no required `TBD`
   * measurement surfaces declared
   * anti-gaming rules pinned

If any are false, G3B exits `HOLD_REMEDIATE`.

---

### 10B.2 Promotion corridor certification (release governance is real)

#### What it must prove

* Promotions are **fail-closed** on missing evidence.
* Promotions are **traceable** (who/what/why).
* Promotions are **transport-proven** (not “we wrote a file”).
* “One active bundle per scope” is enforced deterministically.

#### Required steps (minimum)

1. **Candidate eligibility precheck**

   * Candidate bundle exists with lineage complete.
   * Compatibility checks pass (schema/contract/runtime compatibility).

2. **Promotion commit with transport proof**

   * Publish promotion event and prove:

     * broker ACK received
     * consumer readback finds the event
     * payload hash matches (no mutation)
     * uniqueness holds (no duplicates)

3. **ACTIVE resolution**

   * Resolve ACTIVE bundle deterministically for the intended scope.
   * Prove readback: runtime sees the ACTIVE bundle identity.

4. **Post-promotion observation window**

   * Observe a fixed window (duration pinned) and record:

     * error rate
     * latency p95/p99 (where applicable)
     * consumer lag p95/p99
     * active bundle tag present in telemetry

#### Required artifacts

* `g3b_promotion_precheck_snapshot.json`
* `g3b_promotion_transport_proof.json`
* `g3b_active_resolution_snapshot.json`
* `g3b_post_promotion_observation_snapshot.json`
* `g3b_promotion_verdict.json`

**Hard rule:** If transport proof is missing, promotion cannot be claimed even if the system “seems updated.”

---

### 10B.3 Rollback drill certification (bounded restore)

Rollback is mandatory. A corridor without rollback is not production-ready.

#### What it must prove

* You can revert to last-known-good within a bound.
* The system returns to stable operation (defined stability conditions).
* The rollback is traceable and auditable.

#### Required drill shape

1. Promote a candidate (or simulate a bad promotion condition).
2. Trigger rollback criteria (policy-based or manual trigger is fine, but must be explicit).
3. Execute rollback to last-known-good.
4. Verify:

   * ACTIVE bundle now points to LKG
   * key SLIs stabilize (lag/latency/error)
   * integrity checks pass (no double side effects created by rollback)

#### Required metrics

* rollback time (detect→restore)
* time-to-stable after rollback
* post-rollback error/latency/lag snapshot

#### Required artifacts

* `g3b_rollback_drill_report.json` including:

  * rollback target
  * observed timing
  * verification checks
  * links to affected promotion records

**Hard rule:** Rollback must be executed, not just described.

---

### 10B.4 Audit drill certification (fast answerability)

Audit readiness is proven only by a drill.

#### What it must prove

For a selected decision/event, you can answer within a bounded time:

* what decision happened
* which model/version/bundle produced it
* which promotion record activated that version
* which training run and dataset fingerprint produced that model
* what config/policy was in effect
* what action/outcome was recorded

#### Required drill procedure

1. Pick a decision ID (or event ID) from the mission window.
2. Use platform records (decision log, lineage store, promotion ledger, evidence store) to reconstruct the full chain.
3. Record:

   * audit response time
   * completeness score (required fields present/missing)
   * any remediation actions needed

#### Required artifacts

* `g3b_audit_query_pack.json` (queries used or pointers to how)
* `g3b_audit_drill_report.json` (timeline, completeness, response time)

**Hard rule:** If any required linkage is missing, the audit claim remains HOLD until fixed.

---

### 10B.5 Runbooks/alerts/escalation governance (observability governance slice)

This is about the *operating model*, not “we have CloudWatch.”

#### What it must prove

* Critical alerts are actionable.
* Alerts link to runbooks.
* Ownership and escalation are defined.
* Incident response produces postmortem-quality artifacts.

#### Required outputs

1. **Alert inventory**

   * list of critical alerts for:

     * lag spike
     * checkpoint failure
     * error rate spike
     * latency p99 breach
     * sink backlog
     * cost anomaly
   * each has severity and owner

2. **Runbook linkage**

   * each critical alert links to a runbook with:

     * triage steps
     * mitigation actions
     * verification steps
     * rollback/degrade triggers (where relevant)

3. **Incident drill record**

   * from a drill (lag spike, dependency degrade, or schema evolution), produce an incident-style record:

     * TTD and TTDiag
     * actions taken
     * recovery time
     * prevention follow-up

#### Required artifacts

* `g3b_alert_inventory.json`
* `g3b_runbook_index.json`
* `g3b_incident_drill_record.json`

**Hard rule:** “Alerts exist” without runbooks/ownership is not claimable as production readiness.

---

### 10B.6 Cost governance certification (budget envelopes + receipts + enforcement)

This proves “bounded spend” is real at ops level, not only runtime level.

#### What it must prove

* Budget envelopes are declared and recorded **before** runs.
* Cost-to-outcome receipts are produced after runs.
* Overruns trigger defined action (alert/throttle/stop/teardown).
* Idle-safe posture is verifiable.

#### Required artifacts

* `g3b_budget_envelopes.json`
* `g3b_cost_to_outcome_receipts.json`
* `g3b_cost_guardrail_policy.json`
* `g3b_idle_safe_verification_snapshot.json`

#### Required drill

* cost guardrail drill (may be shared with G3A) proving:

  * breach detection
  * enforcement action
  * post-action verification

---

### 10B.7 Evidence bundle schema + naming + deterministic paths

#### Required bundle root

* `evidence/dev_full/production_ready/g3b_ops_gov/<platform_run_id>/`

#### Required index

* `g3b_ops_gov_evidence_index.json` listing:

  * promotion corridor artifacts
  * rollback drill artifacts
  * audit drill artifacts
  * runbook/alert artifacts
  * cost governance artifacts
  * final verdict + blocker list

#### Required final verdict

* `g3b_ops_gov_verdict.json` with:

  * `overall_pass`
  * `verdict` (`PASS` or `HOLD_REMEDIATE`)
  * `open_blockers` list
  * `next_gate` suggestion (G4 or remediation)

---

### 10B.8 Exit criteria / DoD (G3B PASS)

G3B is PASS only if:

1. Promotion corridor proof is complete (precheck + transport proof + ACTIVE resolution + observation snapshot).
2. Rollback drill executed and bounded restore verified.
3. Audit drill executed and response time + completeness meet thresholds.
4. Alert inventory + runbook index exist and are linked; at least one incident-style drill record exists.
5. Cost governance receipts and idle-safe enforcement are proven; guardrail drill passes.
6. All evidence indexes exist, are readable, and `open_blockers = 0`.

If any condition fails, G3B exits `HOLD_REMEDIATE` with explicit blockers and rerun boundaries.

---

### 10B.9 Common traps (explicitly forbidden)

* Declaring “promotion works” without transport proof and readback.
* Treating rollback as “possible” without executing the rollback drill.
* Claiming auditability without a timed audit drill and completeness checks.
* Claiming operability because dashboards exist (runbooks/ownership missing).
* Claiming cost control because receipts exist (no enforcement drill).

---

## 11. Gate G4: Go-live rehearsal (escape velocity gate)

G4 is the “rocket leaves the atmosphere” gate. It is the only gate that proves dev_full is not just testable, but **operable as a production-like system over time**.

G4 is a **single mission rehearsal run** that must:

* operate continuously for a meaningful period,
* endure at least one controlled incident/drill and recover,
* perform at least one controlled change (promotion/deploy) safely,
* preserve correctness under cohorts (dupes/out-of-order/hot keys),
* remain auditable,
* and close with cost-bounded idle-safe teardown.

**Hard rule:** Production-ready dev_full can only be declared after G4 PASS.

---

### 11.1 Intent (what G4 proves)

G4 proves that dev_full can execute an end-to-end production-like mission where:

* the runtime path meets SLO posture under real load shapes,
* streaming correctness holds under messiness and reprocessing,
* the learning/promotion corridor can execute safely and reversibly,
* operations are diagnosable and auditable under pressure,
* and cost is bounded with clean teardown.

This is where “greens” become a “mission.”

---

### 11.2 Rehearsal profile (duration, envelope, cohort mix, observation windows)

#### 11.2.1 Duration

The rehearsal must run continuously for a pinned duration. The exact duration is defined in the numeric contract (dev_full feasible), but the rule is:

* long enough to include: steady operation, a burst, recovery, and soak-like behavior
* long enough that slow failures surface (backlog creep, checkpoint drift, sink backpressure)

A common dev_full baseline is 6–12 hours; a stronger rehearsal is 24 hours.

#### 11.2.2 Envelope and injection path

The rehearsal must declare:

* `injection_path` (`via_IG` preferred for full end-to-end realism; `via_MSK` allowed for hot-path-only rehearsals but must be labeled)
* the envelope profile used (RC2-S required)

If `via_MSK` is used, G4 cannot be used to declare IG boundary readiness beyond what’s already proven elsewhere.

#### 11.2.3 Cohort mix

The rehearsal must include cohorts from the G2 Data Realism Pack:

* duplicates
* out-of-order
* hot-key skew
* payload extremes
* representative event-type mix

**Hard rule:** A clean stream with no cohorts is not a rehearsal.

#### 11.2.4 Observation windows

G4 must include explicit observation windows:

* pre-change window
* post-change window
* post-incident recovery window

These windows are where you prove stability and generate audit-ready evidence snapshots.

---

### 11.3 Required events during rehearsal (minimum set)

To be claimable, the rehearsal must include the following “mission events”:

#### Event E1 — Sustained operation segment

A sustained steady segment at RC2-S steady, long enough to produce stable distributions.

#### Event E2 — Burst segment

A burst segment at the RC2-S burst profile.

#### Event E3 — Controlled incident/drill and recovery

At least one of the following must be executed during the run:

* lag spike + recovery drill, or
* dependency degrade drill, or
* schema evolution drill

This drill must produce:

* time-to-detect (TTD)
* time-to-diagnose (TTDiag)
* recovery time to stable
* integrity verification (no corruption, no double side effects)

#### Event E4 — Controlled change (promotion/deploy)

At least one controlled change must occur:

* model promotion via the corridor (preferred), or
* controlled deployment change in the runtime plane

This event must be governed:

* precheck gates satisfied
* transport proof produced
* post-change observation snapshot recorded

#### Event E5 — Rollback readiness (and optionally rollback execution)

At minimum, rollback readiness must be proven; ideally, a rollback drill is executed during G4 or immediately adjacent as part of the rehearsal pack.

#### Event E6 — Audit drill during or immediately after the run

A timed audit drill must be performed using the run’s artifacts.

#### Event E7 — Cost closure + idle-safe teardown

The run must close with:

* cost-to-outcome receipt
* residual scan clean
* idle_safe verification

**Hard rule:** Without these events, G4 is not considered production-like.

---

### 11.4 Rehearsal scorecard + drill integration (what must be measured)

G4 is not “a long run.” It is a measured run.

#### Required scorecard metrics families (at minimum)

**Hot path SLO (T0.2)**

* end-to-end latency p95/p99 (phase-by-phase)
* error/timeout rates
* recovery-to-stable time after burst/incident

**Streaming health and correctness (T0.3)**

* consumer lag p95/p99
* checkpoint success + checkpoint duration p95
* dedupe hit rate + duplicate-admission rate
* quarantine rate + top reasons
* replay integrity invariants (if replay executed)

**Observability and diagnosability (T0.4)**

* correlation coverage %
* TTD/TTDiag for the incident drill
* runbook execution record

**Auditability (T0.5)**

* audit response time
* provenance completeness for selected decisions/models

**Cost and idle-safe (T0.6)**

* total cost for the rehearsal
* unit cost (per N events processed)
* budget adherence
* idle-safe verification

#### Required outputs

* `g4_rehearsal_scorecard.json` (phase-by-phase)
* `g4_rehearsal_scorecard_report.md`
* `g4_mission_event_timeline.json` (timestamps for E1–E7)

---

### 11.5 Cost and idle-safe closure for the rehearsal

G4 must prove you can operate economically.

#### Required pre-run artifacts

* `g4_budget_envelope.json` (declared before run)

#### Required post-run artifacts

* `g4_cost_to_outcome_receipt.json`
* `g4_cost_anomaly_scan.json` (if applicable)
* `g4_residual_scan.json` (must be clean unless explicitly waived with reason)
* `g4_idle_safe_snapshot.json` (idle_safe=true)

**Hard rule:** If teardown leaves residuals or cost is not attributable, G4 cannot PASS.

---

### 11.6 Evidence bundle schema + naming + deterministic paths

#### Required bundle root

* `evidence/dev_full/production_ready/g4_go_live_rehearsal/<platform_run_id>/`

#### Required index

* `g4_rehearsal_evidence_index.json` listing:

  * mission charter
  * scorecard artifacts
  * drill artifacts (incident, replay, rollback, audit, cost guardrail)
  * promotion/deploy change artifacts
  * cost and teardown artifacts
  * final verdict + blocker list

#### Required final verdict

* `g4_rehearsal_verdict.json` with:

  * `overall_pass`
  * `verdict` (`PASS` or `HOLD_REMEDIATE`)
  * `open_blockers` list
  * `production_ready_declared` boolean
  * `next_actions` list (if HOLD)

---

### 11.7 Final verdict rule: production-ready dev_full declared

G4 is PASS and production-ready dev_full is declared only if:

1. Rehearsal duration met and all mission events E1–E7 completed.
2. Scorecard metrics meet RC2-S thresholds (or declared degradation policies were triggered and remained within safe bounds).
3. Cohort realism requirements were included and did not break correctness invariants.
4. At least one controlled incident/drill was executed and recovery bound met.
5. At least one controlled change occurred (promotion/deploy) with governance evidence and post-change observation snapshot.
6. Audit drill executed and passed (bounded time + completeness).
7. Cost envelope adhered to and idle-safe teardown verified.
8. `open_blockers = 0` and evidence index is complete and readable.

If any are false, G4 exits `HOLD_REMEDIATE` with explicit blockers and rerun boundaries.

---

### 11.8 Common failure patterns (what to watch out for)

* Passing short runs but failing long soak due to checkpoint drift or state growth.
* Hot-key skew causing one partition to lag while global averages look fine.
* Archive sink backpressure dragging down the hot path.
* Promotion succeeds but post-change observation shows latency/lag regression and no rollback action.
* Audit drill fails because lineage fields are missing or not joinable.
* Teardown leaves hidden costs running (stream apps/endpoints not stopped).

---

### 11.9 Output of G4 (what you will use outwardly)

If G4 PASSes, you can produce a **senior-grade Point X statement** backed by proof:

* “dev_full is production-ready within envelope RC2-S”
* and attach:

  * the scorecard report
  * drill reports (rollback/replay/incident)
  * audit drill report
  * cost receipts + teardown proof

That is exactly the non-toy evidence pack recruiters and senior interviewers recognize.

---

## 12. Numeric acceptance contracts (referenced artifacts)

This section defines how numeric thresholds are created, governed, and used. The key goal is to prevent the failure mode you identified:

> “Observed values become the standard,” which makes certification meaningless.

Numeric contracts exist to make Gates G3/G4 **executable and fail-closed**. They do not replace the mission spec (Section 3) or the proof model (Section 5); they provide the **numbers** needed to decide PASS/FAIL.

---

### 12.1 Overview: what a numeric contract is (and is not)

**A numeric contract is:**

* A single authoritative table of **envelopes, thresholds, sample minima, and bounds** used to judge certification runs.

**A numeric contract is not:**

* A dump of “what happened last time.”
* A list of observed numbers without policy targets and guardbands.
* A place to hide missing metrics by setting thresholds to “N/A.”

**Hard rule:** Certification runs may not be declared PASS unless the applicable numeric contract sections are **activatable** (no required TBD) and measurements satisfy thresholds.

---

### 12.2 Contract types (what contracts exist)

This road uses two numeric contracts:

1. **Runtime numeric contract**

* defines RC2-S (required) and RC2-L (stretch)
* defines runtime thresholds for: SLO hot path, streaming health/correctness, runtime observability, runtime cost
* used by **G3A** and runtime portions of **G4**

2. **Ops/Gov numeric contract**

* defines thresholds for: promotion governance, rollback bounds, audit response time/completeness, alert actionability/runbook coverage, cost governance
* used by **G3B** and ops/gov portions of **G4**

These contracts are referenced by this road-to-production doc; they are not duplicated here.

---

### 12.3 Runtime numeric contract (RC2-S / RC2-L)

#### 12.3.1 Required envelope split

The runtime contract must contain:

* **RC2-S (required, dev_full operational envelope)**

  * steady_rate, steady_duration, min_processed_events
  * burst_rate (or multiplier), burst_duration
  * soak_duration
  * recovery_bound_seconds (time to return to stable)
  * replay_window_size_min (must be meaningful)
  * cohort realism minima (dupe %, out-of-order %, hot-key skew)

* **RC2-L (stretch)**

  * same structure, higher values
  * explicitly marked “not required for production-ready dev_full”

**Hard rule:** G3A/G4 must certify against RC2-S. RC2-L exists to guide future scaling, not to block readiness.

#### 12.3.2 Metric thresholds (runtime)

The runtime contract must define PASS/FAIL thresholds with:

* measurement surface (where measured)
* distribution requirements (p50/p95/p99)
* sample minima and duration minima
* explicit “missing metric” failure path

At minimum it must cover:

**Hot path SLO (T0.2)**

* end-to-end decision latency p95/p99
* error/timeout rate ceiling
* recovery-to-stable bound

**Streaming health/correctness (T0.3)**

* consumer lag p95/p99 ceilings
* checkpoint success rate minimum + checkpoint duration p95 ceiling
* duplicate-admission rate ceiling
* dedupe hit rate reporting requirement
* quarantine rate and top reasons reporting requirement

**Runtime observability (T0.4 slice)**

* correlation coverage minimum
* TTD/TTDiag bounds for drills (if tracked)

**Runtime cost (T0.6 slice)**

* budget adherence required
* unit cost ceilings (cost per N events)
* idle burn ceiling (post-run)

#### 12.3.3 Measurement surface rule (mandatory)

Every threshold row must include a `measurement_surface` field, e.g.:

* `IG_ADMITTED_EVENTS_PER_SEC`
* `MSK_CONSUME_RATE_EVENTS_PER_SEC`
* `FLINK_PROCESSED_EVENTS_PER_SEC`
* `DECISION_COMMITTED_PER_SEC`
* `SINK_WRITTEN_RECORDS_PER_SEC`

**Hard rule:** A throughput threshold without a measurement surface is invalid and blocks activation.

---

### 12.4 Ops/Gov numeric contract

#### 12.4.1 Promotion corridor thresholds (T0.1)

Must define:

* gate pass requirements (eligibility + compatibility required)
* transport proof requirements (ack + readback + payload hash match)
* ACTIVE resolution determinism checks
* post-promotion observation window duration and thresholds (latency/lag/error with active bundle tag)

#### 12.4.2 Rollback thresholds (T0.1)

Must define:

* rollback restore time bound (seconds/minutes)
* time-to-stable bound after rollback
* verification checklist requirements (LKG active, key SLIs normalized)

#### 12.4.3 Audit thresholds (T0.5)

Must define:

* audit response time bound
* provenance completeness minimum
* required trace chain fields (decision → model → promotion → dataset → training run)
* completeness scoring rules (what counts as missing/invalid)

#### 12.4.4 Observability governance thresholds (T0.4)

Must define:

* critical alert inventory coverage minimum
* runbook linkage coverage minimum
* alert precision/actionability minimum (or a proxy such as “alert review evidence exists per run”)
* escalation posture required (owner fields, severity rules)

#### 12.4.5 Cost governance thresholds (T0.6)

Must define:

* budget envelope requirements (pre-run)
* receipt completeness requirements (post-run)
* enforcement drill requirements (what action occurs on breach)
* idle-safe verification requirements

---

### 12.5 How numbers are set (policy vs measured baseline)

This is the critical part that prevents “observed becomes standard.”

Each numeric row must include:

* **Type:** `policy` or `measured`
* **Baseline:** measured value (from a cited run) if available
* **Target:** policy target (what you are trying to meet)
* **Guardband:** headroom or safety margin (how much slack you allow)
* **Source reference:** run id / artifact reference for measured baselines

**Rules:**

1. **Measured baselines inform targets; they do not automatically become targets.**
2. Policy targets must be justified (dev_full operational envelope, budget, risk posture).
3. Any time you change a policy target, you must record:

   * why it changed
   * what evidence prompted it
   * whether it moves closer to prod_target or is purely dev_full

---

### 12.6 Contract activation rules (what makes a contract “activatable”)

A contract section is “activatable” only if:

* no required threshold is `TBD`
* measurement surfaces are declared for every required metric
* sample minima and duration minima are declared
* missing-metric failure path is defined
* injection path rules are encoded (via_IG vs via_MSK)

**Hard rule:** If the contract is not activatable, certification must not run. The correct verdict is `HOLD_REMEDIATE` before spending money.

---

### 12.7 Calibration procedure (how contracts evolve without drift)

Contracts evolve through a controlled procedure:

1. **Baseline capture:** run a controlled profile (steady/burst/soak) and measure baselines
2. **Decision:** set or update policy targets using baselines + guardbands
3. **Change log:** record what changed and why
4. **Re-certify:** rerun profiles to see if platform meets targets
5. **Freeze:** when the mission run is ready, freeze RC2-S for that mission cycle

**Hard rule:** Do not “tighten after failing” or “loosen after failing” without a written rationale. Otherwise you’re gaming.

---

### 12.8 What gets referenced where (to avoid duplicated numeric authorities)

To prevent contradictory numbers in multiple docs:

* The **mission spec** (Section 3) references envelopes by name only (RC2-S/RC2-L).
* G3A/G3B reference thresholds only through the numeric contracts.
* Any older runtime-cert plan numbers must either:

  * be removed, or
  * be replaced with “see numeric contract section X.”

**Hard rule:** Only one numeric authority per domain (runtime vs ops/gov). If two docs disagree, the numeric contract wins.

---

### 12.9 Failure handling: blockers driven by contract gaps

Numeric contract failures must generate explicit blockers:

* threshold not met → blocker with measurement surface and rerun boundary
* metric missing → blocker with “metric emission required”
* invalid measurement surface → blocker with “wrong surface; must re-measure”
* contract non-activatable (TBD) → blocker with “contract activation required”

This forces progress toward production-ready rather than repeated non-claimable runs.

---

## 12. Numeric acceptance contracts (referenced artifacts)

This section defines how numeric thresholds are created, governed, and used. The key goal is to prevent the failure mode you identified:

> “Observed values become the standard,” which makes certification meaningless.

Numeric contracts exist to make Gates G3/G4 **executable and fail-closed**. They do not replace the mission spec (Section 3) or the proof model (Section 5); they provide the **numbers** needed to decide PASS/FAIL.

---

### 12.1 Overview: what a numeric contract is (and is not)

**A numeric contract is:**

* A single authoritative table of **envelopes, thresholds, sample minima, and bounds** used to judge certification runs.

**A numeric contract is not:**

* A dump of “what happened last time.”
* A list of observed numbers without policy targets and guardbands.
* A place to hide missing metrics by setting thresholds to “N/A.”

**Hard rule:** Certification runs may not be declared PASS unless the applicable numeric contract sections are **activatable** (no required TBD) and measurements satisfy thresholds.

---

### 12.2 Contract types (what contracts exist)

This road uses two numeric contracts:

1. **Runtime numeric contract**

* defines RC2-S (required) and RC2-L (stretch)
* defines runtime thresholds for: SLO hot path, streaming health/correctness, runtime observability, runtime cost
* used by **G3A** and runtime portions of **G4**

2. **Ops/Gov numeric contract**

* defines thresholds for: promotion governance, rollback bounds, audit response time/completeness, alert actionability/runbook coverage, cost governance
* used by **G3B** and ops/gov portions of **G4**

These contracts are referenced by this road-to-production doc; they are not duplicated here.

---

### 12.3 Runtime numeric contract (RC2-S / RC2-L)

#### 12.3.1 Required envelope split

The runtime contract must contain:

* **RC2-S (required, dev_full operational envelope)**

  * steady_rate, steady_duration, min_processed_events
  * burst_rate (or multiplier), burst_duration
  * soak_duration
  * recovery_bound_seconds (time to return to stable)
  * replay_window_size_min (must be meaningful)
  * cohort realism minima (dupe %, out-of-order %, hot-key skew)

* **RC2-L (stretch)**

  * same structure, higher values
  * explicitly marked “not required for production-ready dev_full”

**Hard rule:** G3A/G4 must certify against RC2-S. RC2-L exists to guide future scaling, not to block readiness.

#### 12.3.2 Metric thresholds (runtime)

The runtime contract must define PASS/FAIL thresholds with:

* measurement surface (where measured)
* distribution requirements (p50/p95/p99)
* sample minima and duration minima
* explicit “missing metric” failure path

At minimum it must cover:

**Hot path SLO (T0.2)**

* end-to-end decision latency p95/p99
* error/timeout rate ceiling
* recovery-to-stable bound

**Streaming health/correctness (T0.3)**

* consumer lag p95/p99 ceilings
* checkpoint success rate minimum + checkpoint duration p95 ceiling
* duplicate-admission rate ceiling
* dedupe hit rate reporting requirement
* quarantine rate and top reasons reporting requirement

**Runtime observability (T0.4 slice)**

* correlation coverage minimum
* TTD/TTDiag bounds for drills (if tracked)

**Runtime cost (T0.6 slice)**

* budget adherence required
* unit cost ceilings (cost per N events)
* idle burn ceiling (post-run)

#### 12.3.3 Measurement surface rule (mandatory)

Every threshold row must include a `measurement_surface` field, e.g.:

* `IG_ADMITTED_EVENTS_PER_SEC`
* `MSK_CONSUME_RATE_EVENTS_PER_SEC`
* `FLINK_PROCESSED_EVENTS_PER_SEC`
* `DECISION_COMMITTED_PER_SEC`
* `SINK_WRITTEN_RECORDS_PER_SEC`

**Hard rule:** A throughput threshold without a measurement surface is invalid and blocks activation.

---

### 12.4 Ops/Gov numeric contract

#### 12.4.1 Promotion corridor thresholds (T0.1)

Must define:

* gate pass requirements (eligibility + compatibility required)
* transport proof requirements (ack + readback + payload hash match)
* ACTIVE resolution determinism checks
* post-promotion observation window duration and thresholds (latency/lag/error with active bundle tag)

#### 12.4.2 Rollback thresholds (T0.1)

Must define:

* rollback restore time bound (seconds/minutes)
* time-to-stable bound after rollback
* verification checklist requirements (LKG active, key SLIs normalized)

#### 12.4.3 Audit thresholds (T0.5)

Must define:

* audit response time bound
* provenance completeness minimum
* required trace chain fields (decision → model → promotion → dataset → training run)
* completeness scoring rules (what counts as missing/invalid)

#### 12.4.4 Observability governance thresholds (T0.4)

Must define:

* critical alert inventory coverage minimum
* runbook linkage coverage minimum
* alert precision/actionability minimum (or a proxy such as “alert review evidence exists per run”)
* escalation posture required (owner fields, severity rules)

#### 12.4.5 Cost governance thresholds (T0.6)

Must define:

* budget envelope requirements (pre-run)
* receipt completeness requirements (post-run)
* enforcement drill requirements (what action occurs on breach)
* idle-safe verification requirements

---

### 12.5 How numbers are set (policy vs measured baseline)

This is the critical part that prevents “observed becomes standard.”

Each numeric row must include:

* **Type:** `policy` or `measured`
* **Baseline:** measured value (from a cited run) if available
* **Target:** policy target (what you are trying to meet)
* **Guardband:** headroom or safety margin (how much slack you allow)
* **Source reference:** run id / artifact reference for measured baselines

**Rules:**

1. **Measured baselines inform targets; they do not automatically become targets.**
2. Policy targets must be justified (dev_full operational envelope, budget, risk posture).
3. Any time you change a policy target, you must record:

   * why it changed
   * what evidence prompted it
   * whether it moves closer to prod_target or is purely dev_full

---

### 12.6 Contract activation rules (what makes a contract “activatable”)

A contract section is “activatable” only if:

* no required threshold is `TBD`
* measurement surfaces are declared for every required metric
* sample minima and duration minima are declared
* missing-metric failure path is defined
* injection path rules are encoded (via_IG vs via_MSK)

**Hard rule:** If the contract is not activatable, certification must not run. The correct verdict is `HOLD_REMEDIATE` before spending money.

---

### 12.7 Calibration procedure (how contracts evolve without drift)

Contracts evolve through a controlled procedure:

1. **Baseline capture:** run a controlled profile (steady/burst/soak) and measure baselines
2. **Decision:** set or update policy targets using baselines + guardbands
3. **Change log:** record what changed and why
4. **Re-certify:** rerun profiles to see if platform meets targets
5. **Freeze:** when the mission run is ready, freeze RC2-S for that mission cycle

**Hard rule:** Do not “tighten after failing” or “loosen after failing” without a written rationale. Otherwise you’re gaming.

---

### 12.8 What gets referenced where (to avoid duplicated numeric authorities)

To prevent contradictory numbers in multiple docs:

* The **mission spec** (Section 3) references envelopes by name only (RC2-S/RC2-L).
* G3A/G3B reference thresholds only through the numeric contracts.
* Any older runtime-cert plan numbers must either:

  * be removed, or
  * be replaced with “see numeric contract section X.”

**Hard rule:** Only one numeric authority per domain (runtime vs ops/gov). If two docs disagree, the numeric contract wins.

---

### 12.9 Failure handling: blockers driven by contract gaps

Numeric contract failures must generate explicit blockers:

* threshold not met → blocker with measurement surface and rerun boundary
* metric missing → blocker with “metric emission required”
* invalid measurement surface → blocker with “wrong surface; must re-measure”
* contract non-activatable (TBD) → blocker with “contract activation required”

This forces progress toward production-ready rather than repeated non-claimable runs.

---

## 13. Evidence pack index (what must exist and where)

This section defines the **canonical evidence bundles** required to declare production-ready dev_full. It is intentionally deterministic so you can:

* generate senior-defensible claims without hunting through logs,
* prevent “scrubbed evidence” and cherry-picking,
* and keep Codex from declaring PASS without producing the required bundles.

**Hard rule:** If an evidence pack is missing or unreadable, the corresponding gate cannot PASS.

---

### 13.1 Required bundle list per gate (G1–G4)

#### G1 — Wiring Stable Baseline Pack

**Purpose:** prove wiring is stable; establish baseline anchor.
**Required pack name:** `G1_WIRING_STABLE_BASELINE_PACK`

#### G2 — Data Realism Pack (7d)

**Purpose:** ground the platform in real data; pin cohorts, joins, IEG decisions, monitoring baselines.
**Required pack name:** `G2_DATA_REALISM_PACK_7D`

#### G3A — Runtime Operational Certification Pack

**Purpose:** prove hot path SLO posture, streaming correctness, runtime drills, cost runtime posture.
**Required pack name:** `G3A_RUNTIME_CERT_PACK_RC2S`

#### G3B — Ops/Gov Operational Certification Pack

**Purpose:** prove promotion corridor, rollback, audit drill, runbook/alert governance, cost governance.
**Required pack name:** `G3B_OPS_GOV_CERT_PACK`

#### G4 — Go-Live Rehearsal Mission Pack

**Purpose:** prove continuous mission operation, controlled change + incident recovery, final closure.
**Required pack name:** `G4_GO_LIVE_REHEARSAL_PACK`

---

### 13.2 Canonical storage roots and naming conventions

To avoid drift, all evidence packs must live under a deterministic root. Use the same root across gates.

#### Canonical root (recommended)

`evidence/dev_full/production_ready/`

#### Pack-level root

Each pack MUST be stored under:

`evidence/dev_full/production_ready/<PACK_NAME>/<platform_run_id>/`

Example:
`evidence/dev_full/production_ready/G3A_RUNTIME_CERT_PACK_RC2S/22595073028/`

#### Required pack index file

Every pack must include:

`evidence_index.json`

This file is the **single entry point** and must be readable without additional context.

---

### 13.3 Evidence pack schemas (minimum contents)

Each pack must include:

* an index file
* a verdict file
* a blocker register
* the required artifacts specific to the pack

#### 13.3.1 Common files required in every pack

1. `evidence_index.json`

   * pack name, version
   * run ids (platform_run_id, scenario_run_id)
   * timestamps
   * references (paths) to all required artifacts
   * measurement surfaces used (where applicable)
2. `verdict.json`

   * PASS/HOLD_REMEDIATE
   * open_blockers count and list
   * next gate pointer
3. `blocker_register.json`

   * blocker code, severity, failed metric/threshold
   * rerun boundary
   * remediation notes pointer
4. `run_charter.json`

   * window definition, injection path, budget envelope, as-of/maturity params

**Hard rule:** If any common file is missing, pack is invalid.

---

### 13.4 Pack-specific requirements

#### 13.4.1 G1_WIRING_STABLE_BASELINE_PACK

**Must include:**

* `g1_wiring_stable_baseline_pack.json` (category PASS/FAIL)
* baseline run anchor (fields pinned)
* teardown/idle-safe verification snapshot
* residual scan output

**Must prove:**

* wiring categories A–G PASS
* baseline anchor pinned for later gates

---

#### 13.4.2 G2_DATA_REALISM_PACK_7D

**Must include:**

* `g2_window_charter.json`
* `g2_profile_rollup.json`
* per-table `g2_table_profile_*.json`
* `g2_join_matrix.json` + `g2_join_decisions.md`
* `g2_rtdl_allowlist.yaml` + `g2_rtdl_denylist.yaml`
* IEG decisions:

  * `g2_ieg_node_catalog.json`
  * `g2_ieg_edge_catalog.json`
  * `g2_ieg_graph_decisions.md`
  * `g2_ieg_state_budget.json`
* monitoring baselines: `g2_monitoring_baselines.json`
* load campaign seed: `g2_load_campaign_seed.json`
* learning realism:

  * `g2_label_maturity_report.json`
  * `g2_learning_window_spec.json`
  * `g2_leakage_policy.md`

**Must prove:**

* reality is measured and pinned
* cohort mix is known
* joinability is known
* time-safe runtime policy is pinned
* learning windows are time-causal and enforceable

---

#### 13.4.3 G3A_RUNTIME_CERT_PACK_RC2S

**Must include:**

* `g3a_preflight_snapshot.json`
* scorecard phase artifacts:

  * `g3a_scorecard_steady.json`
  * `g3a_scorecard_burst.json`
  * `g3a_scorecard_recovery.json`
  * `g3a_scorecard_soak.json`
  * `g3a_scorecard_report.md`
* cohort artifacts:

  * `g3a_cohort_manifest.json`
  * `g3a_cohort_results.json`
* drill artifacts:

  * `g3a_drill_replay_integrity.json`
  * `g3a_drill_lag_recovery.json`
  * `g3a_drill_schema_evolution.json`
  * `g3a_drill_dependency_degrade.json`
  * `g3a_drill_cost_guardrail.json`
* cost artifacts:

  * `g3a_budget_envelope.json`
  * `g3a_cost_receipt.json`
  * `g3a_idle_safe_snapshot.json`

**Must prove:**

* steady/burst/recovery/soak run completed with required minima
* metrics surfaces match contract
* drills pass recovery bounds and integrity checks

---

#### 13.4.4 G3B_OPS_GOV_CERT_PACK

**Must include:**

* promotion corridor artifacts:

  * `g3b_promotion_precheck_snapshot.json`
  * `g3b_promotion_transport_proof.json`
  * `g3b_active_resolution_snapshot.json`
  * `g3b_post_promotion_observation_snapshot.json`
* rollback artifacts:

  * `g3b_rollback_drill_report.json`
* audit artifacts:

  * `g3b_audit_query_pack.json`
  * `g3b_audit_drill_report.json`
* runbook/alerts governance artifacts:

  * `g3b_alert_inventory.json`
  * `g3b_runbook_index.json`
  * `g3b_incident_drill_record.json`
* cost governance artifacts:

  * `g3b_budget_envelopes.json`
  * `g3b_cost_to_outcome_receipts.json`
  * `g3b_idle_safe_verification_snapshot.json`

**Must prove:**

* governed promotion is real (transport proof + ACTIVE)
* rollback is executed and bounded
* audit can be answered within bound with completeness
* ops governance exists (alerts→runbooks→incident record)

---

#### 13.4.5 G4_GO_LIVE_REHEARSAL_PACK

**Must include:**

* mission timeline and scorecard:

  * `g4_mission_event_timeline.json`
  * `g4_rehearsal_scorecard.json`
  * `g4_rehearsal_scorecard_report.md`
* controlled change artifacts:

  * promotion/deploy artifacts plus post-change observation window report
* incident/drill artifacts:

  * at least one incident drill report + recovery verification
* audit drill artifacts:

  * audit drill report for a decision produced in this run
* cost and closure artifacts:

  * `g4_budget_envelope.json`
  * `g4_cost_to_outcome_receipt.json`
  * `g4_residual_scan.json`
  * `g4_idle_safe_snapshot.json`
* final verdict:

  * `g4_rehearsal_verdict.json`

**Must prove:**

* continuous operation
* controlled change
* controlled incident and recovery
* audit answerability
* bounded cost and clean teardown
* open_blockers=0

---

### 13.5 Artifact naming + canonical paths (deterministic)

To ensure evidence is reusable and reviewable:

* Artifact names must be stable and consistent across runs (as specified above).
* All artifacts must include:

  * `platform_run_id`
  * `scenario_run_id`
  * timestamp in ISO8601 or a deterministic run-scoped folder
* No ad-hoc “random filename” evidence that breaks automation.

---

### 13.6 Minimum bundle checks (automatable)

Every pack must be machine-checkable by a simple verifier that checks:

1. required files exist
2. required files are readable JSON/MD/YAML
3. `verdict.json` exists and matches `open_blockers`
4. `evidence_index.json` references only existing files
5. all “required” artifacts for the pack are present
6. measurement surfaces referenced in scorecards are declared

If any check fails, the pack is invalid.

---

### 13.7 Evidence retention and “scrubbed evidence” prohibitions

#### 13.7.1 Retention rule

* Keep at least:

  * latest PASS pack per gate
  * latest HOLD pack per gate
  * last-known-good baseline pack
* Do not delete failed runs if they explain why remediation happened; they are part of the evidence chain.

#### 13.7.2 Scrubbed evidence prohibition

* You may not replace failure artifacts with later success artifacts without maintaining the history.
* You may not cherry-pick “best run” metrics from different runs to form a fake PASS.
* Observed values can be recorded as baselines, but they do not automatically become thresholds.

#### 13.7.3 One status owner rule

* Gate progression decisions must be derived from the pack verdict + blocker register, not from ad-hoc notes.

---

## 14. Implementer operating rules (Codex instructions)

This section is written for Codex. Its purpose is to ensure the implementer never works in a vacuum, never confuses “green checklists” with production-ready, and always produces evidence that moves the platform toward the **Production-Grade Run**.

**Hard rule:** Any work that does not map to a gate, a mission requirement, and an evidence artifact is out of scope.

---

### 14.1 How to use this document day-to-day

For every work session, Codex must begin by selecting one of:

* **G1 Wiring baseline maintenance**
* **G2 Data realism (7d)**
* **G3A Runtime certification pack**
* **G3B Ops/Gov certification pack**
* **G4 Go-live rehearsal**

Codex must state in the implementation notes:

* which gate is active,
* which mission requirement(s) (MR-xx) are being advanced,
* which pillar(s) and Tier-0 claim(s) are targeted,
* and which evidence pack(s) will be updated.

If Codex cannot identify this mapping, it must stop and request clarification rather than proceeding.

---

### 14.2 Required output for every change (the “work item template”)

Every code/config/infra change must produce a work item record containing:

1. **Change ID** (deterministic naming)
2. **Gate target** (G1/G2/G3A/G3B/G4)
3. **Mission requirement(s)** advanced (MR-xx)
4. **Claim(s)** advanced (C-T0.1 … C-T0.6)
5. **Reason** (what blocker or risk it addresses)
6. **Expected effect** (what metric/artifact will change)
7. **Evidence produced** (new/updated artifacts and where they live)
8. **Rerun boundary** (what must be rerun to validate the change)
9. **Verdict impact** (what blocker(s) should clear if successful)

**Hard rule:** No change is “done” until the rerun boundary produces evidence that updates the relevant pack verdict/blockers.

---

### 14.3 Drift detection and escalation rule (“stop and surface mismatch”)

Codex must halt and escalate if any of the following are detected:

**A) Goal drift**

* A plan is being executed that does not advance the Production-Grade Run (Section 3).
* Work is being justified as “it’s green” rather than “it reduces mission risk.”

**B) Evidence drift**

* Required evidence artifacts are missing, unreadable, or renamed ad-hoc.
* A PASS is being claimed without required drill bundles or scorecard distributions.

**C) Numeric drift**

* Thresholds are being changed to match observed values without policy justification.
* Measurement surfaces are inconsistent or unspecified (e.g., Flink internal rate used as platform throughput).

**D) Architecture drift**

* Runtime placement changes (EKS vs Managed Flink vs ECS) occur without updating:

  * the mission spec, and
  * the relevant contracts, and
  * the proof packs.

**E) Boundary drift**

* Runtime uses forbidden truth surfaces.
* Learning uses “future” Oracle rows beyond `as_of` and `maturity_lag`.
* Injection path is not declared and certification claims are made anyway.

**Escalation output required:**
`drift_report.json` containing:

* drift type (goal/evidence/numeric/architecture/boundary)
* what was observed
* what doc/contract it conflicts with
* recommended remediation options

---

### 14.4 Rerun scope discipline (don’t rerun the world)

Codex must minimize cost and time by rerunning only what is required to clear blockers.

**Rules:**

* If the failure is a missing artifact/metric emission → rerun the smallest step that emits it.
* If the failure is a profile threshold miss (lag/latency) → rerun the affected load profile only.
* If the failure is correctness (duplicates/replay) → rerun the cohort window and replay drill only.
* If the failure is promotion corridor transport proof → rerun promotion commit/readback only.
* If the failure is audit completeness → rerun audit drill only.
* If the failure is teardown/idle-safe → rerun teardown verification only.

**Hard rule:** “Rerun everything” is not allowed unless the blocker explicitly demands it.

---

### 14.5 Measurement surface rule (no false throughput claims)

For any throughput/latency claim, Codex must declare:

* injection path (`via_IG` or `via_MSK`)
* measurement surface (IG-admitted, MSK-consumed, Flink-processed, decision-committed, sink-written)
* whether the metric is end-to-end or component-local

If Codex cannot reconcile at least two surfaces for end-to-end claims (e.g., IG-admitted vs decision-committed), the claim remains HOLD.

---

### 14.6 “Observed value is not the standard” rule (numeric contract discipline)

Codex must never turn a measurement into a threshold by default.

**Required numeric row format:**

* baseline (measured)
* target (policy)
* guardband (policy)
* source ref (run id + artifact pointer)
* measurement surface

If Codex proposes changing a policy target:

* it must include a rationale and tradeoff statement,
* it must state whether this moves closer to prod_target or is dev_full-only,
* and it must not invalidate prior evidence packs without explicit versioning.

---

### 14.7 Anti-gaming enforcement (certification integrity)

Codex must enforce:

* minimum durations and sample sizes per profile
* distribution reporting (p50/p95/p99)
* inclusion of cohort messiness (dupes/out-of-order/hot keys)
* replay window size must be meaningful (not a tiny probe)
* peak slice inclusion for at least one run

If these are not met, the correct verdict is HOLD_REMEDIATE even if nothing “crashes.”

---

### 14.8 Pack-first workflow (how to avoid “scrubbed evidence”)

Codex must treat the evidence pack as the primary artifact of work.

**Rules:**

* A PASS is only valid if `evidence_index.json` is complete and `open_blockers=0`.
* Failed packs must be retained (do not delete) if they explain remediation.
* Do not cherry-pick “best metrics” from different runs to fake PASS.
* Every gate has exactly one authoritative pack verdict at any moment (latest verdict wins).

---

### 14.9 Mandatory “Point X update” after each gate attempt

After any attempt at G2/G3/G4, Codex must produce a short update:

* current Point X summary (goal-referenced)
* which Tier-0 claims moved from L2→L3 (or stayed HOLD)
* which blockers remain (by code)
* what the next minimal rerun boundary is

**Output artifact:**
`point_x_update.md` stored alongside the pack.

This ensures progress is always articulated relative to the end goal, not internal implementation trivia.

---

### 14.10 Implementer success criteria (how Codex knows it’s doing well)

Codex is succeeding if:

* each iteration reduces the blocker list,
* evidence packs become complete and readable,
* certification runs become repeatable,
* and the platform approaches G4 PASS without changing the definition of PASS.

Codex is failing if:

* numbers drift to match observations,
* artifacts become inconsistent,
* or the platform “looks green” without completing the mission run and drills.

---

## 15. Open decisions, risk register, and roadmap

This section keeps the program honest and prevents silent drift. It explicitly records:

* what is still undecided,
* what could block the mission run,
* what is deferred,
* and what the next milestones are.

Codex must update this section (or its referenced artifacts) whenever decisions or risks change materially.

---

### 15.1 Open decisions table

Open decisions are items that affect either:

* mission feasibility,
* claimability (Tier-0 proofs),
* or cost/scope.

Each open decision must have:

* an owner (you or Codex),
* options,
* evaluation criteria,
* a due-by gate (G2, G3A, G3B, or G4),
* and a “default if not decided” stance.

**Template**

* **OD-ID**
* **Decision**
* **Why it matters**
* **Options**
* **Decision criteria**
* **Owner**
* **Due by gate**
* **Status**

**Seed open decisions list (likely candidates)**

* **OD-01 Injection path policy for certification**: when to use `via_IG` vs `via_MSK` and how claims are scoped.
* **OD-02 RC2-S envelope numbers**: final steady/burst/soak rates/durations and replay window sizes, grounded in 7d realism.
* **OD-03 Watermarks/allowed lateness posture**: how out-of-order events are handled in RTDL.
* **OD-04 IEG minimal graph**: which entity nodes/edges are in-scope and TTL/state bounds.
* **OD-05 Archive sink design**: connector vs bespoke service; partitioning and file sizing.
* **OD-06 Decision explainability**: reason code schema and minimal decision explanation fields.
* **OD-07 Label maturity definition**: label availability time vs event time; maturity lag choice.
* **OD-08 Promotion observation window**: duration and which signals must be stable post-promotion.
* **OD-09 Cost budgets**: per gate and per mission run budget envelopes and enforcement posture.

---

### 15.2 Risk register (mission blockers)

Risks are not “interesting problems.” They are things that can prevent:

* G3 packs from passing,
* or G4 mission run from completing.

Each risk must have:

* severity,
* early warning signals,
* mitigation plan,
* and a verification method.

**Template**

* **R-ID**
* **Risk**
* **Severity** (High/Med/Low)
* **Early warning**
* **Mitigation**
* **Verification**
* **Owner**
* **Due by gate**

**Seed risk list (typical for your platform)**

* **R-01 Skew/hot-key blowup**: one key dominates partitions, causing lag spikes and missed SLOs.

  * Mitigation: partitioning strategy, salting/capping policy, side-path handling.
* **R-02 State blowup / checkpoint failure**: Flink state grows unbounded; checkpoints fail; recovery breaks.

  * Mitigation: TTLs, state budget limits, smaller windows, backpressure tuning.
* **R-03 Sink backpressure**: archive/audit writing slows the hot path.

  * Mitigation: connector tuning, async sinks, buffer policies, file sizing.
* **R-04 Aurora saturation**: p99 latency spikes due to connection pool pressure or slow queries.

  * Mitigation: indexes, batching, pool limits, caching in Redis, write patterns.
* **R-05 DDB idempotency hotspot**: hot partition keys or TTL patterns cause throttling at IG.

  * Mitigation: key design, adaptive backoff, partition spread, throttles.
* **R-06 Learning leakage**: truth/labels leak into runtime or training uses future rows.

  * Mitigation: strict allowlists, as-of/maturity enforcement, leakage guardrail reports.
* **R-07 Numeric contract gaming**: thresholds drift to match observed values.

  * Mitigation: policy vs baseline separation, versioned approvals, anti-gaming checks.
* **R-08 Cost runaway**: long runs or un-teardownable resources exceed budget.

  * Mitigation: budget envelopes, enforced stop conditions, idle-safe verification.
* **R-09 Audit incompleteness**: cannot trace decision → model → dataset → run within bound.

  * Mitigation: required audit fields spec, audit drill, fail-closed missing fields.
* **R-10 Mission run operational failure**: go-live rehearsal fails due to untested incident class.

  * Mitigation: drill catalog, rehearsal includes incident + recovery, postmortem loop.

---

### 15.3 Deferred items (explicitly postponed)

Deferred means: not needed for **production-ready dev_full**, but potentially needed later for prod_target or stretch scaling.

**Examples**

* **RC2-L stretch envelope** (bank-scale throughput targets)
* **Multi-region DR**
* **Advanced ML monitoring** (beyond baseline distributions and drift candidates)
* **Full case management UI**
* **Prod_target substrate expansion** (more enterprise-like stack)

**Hard rule:** Deferred items must not block G4 PASS unless explicitly promoted into scope via change control.

---

### 15.4 Roadmap milestones (what happens next)

This is the “plan of record” that should remain short.

**Milestone M1 — G2 Data Realism Pack complete**

* 7d profile
* join matrix + decisions
* RTDL allowlist
* IEG minimal graph + TTL/state budget
* monitoring baselines
* load campaign seed
* learning window spec + maturity lag pinned

**Milestone M2 — G3A Runtime Cert Pack PASS**

* RC2-S scorecard run PASS
* cohorts included
* runtime drill pack PASS
* runtime evidence pack complete

**Milestone M3 — G3B Ops/Gov Cert Pack PASS**

* promotion corridor proof complete
* rollback drill PASS (bounded restore)
* audit drill PASS (bounded answerability)
* runbooks/alerts governance complete
* ops/gov evidence pack complete

**Milestone M4 — G4 Go-Live Rehearsal PASS**

* continuous run achieved
* controlled change achieved
* incident + recovery achieved
* cost bounded + idle-safe closure achieved
* open_blockers=0
* production-ready dev_full declared

---

### 15.5 “Definition of done” for this document itself

This document is considered “ready to hand to Codex” when:

* all sections that define rules are written in binding language (no ambiguity),
* references to numeric contracts are consistent (single numeric authority per domain),
* evidence pack index is complete and deterministic,
* traceability matrix is complete enough that every major task maps to mission requirements,
* and open decisions/risk register exists with initial entries (even if unresolved).

---

## Appendix A. Workload envelope assumptions (dev_full baseline vs stretch)

This appendix defines the **workload envelope model** used by this road-to-production program. It prevents the most common source of drift:

> “We certified something, but nobody knows what load pattern it was certified under.”

It also prevents the opposite failure mode:

> “We pinned bank-scale numbers too early, so we can never pass and we waste time.”

The envelope model is intentionally split into:

* **RC2-S (dev_full baseline envelope)**: required for production-ready dev_full
* **RC2-L (stretch envelope)**: aspirational, not required for production-ready dev_full

Numeric values are not hardcoded here; they are pinned in the numeric contracts (Section 12). This appendix defines the **structure and assumptions**.

---

### A.1 Envelope principles (how to think about load)

1. **Envelope is a contract**: every SLO, cost claim, and drill result is interpreted “within this envelope.”
2. **Envelope must reflect real data**: cohort mix and skew are derived from the G2 Data Realism Pack (7d).
3. **Envelope is a distribution**: report and validate p50/p95/p99 for latency and lag; do not rely on averages.
4. **Envelope is end-to-end**: whenever possible, measure throughput at multiple surfaces (IG-admitted, MSK-consumed, Flink-processed, decision-committed, sink-written).
5. **Two envelopes**:

   * RC2-S proves production-ready dev_full
   * RC2-L guides future scaling, not current claimability

---

### A.2 Workload taxonomy (what flows the envelope applies to)

The platform has multiple flows; not all have the same criticality.

#### A.2.1 Runtime hot path (highest priority)

* Ingestion → streaming projections → decisioning → audit/action/case triggers
* Must be SLO-grade within RC2-S

#### A.2.2 Control plane and run control

* Step Functions orchestration, gate transitions, evidence publishing
* Must be reliable but not necessarily “high EPS”

#### A.2.3 Archive/audit sinking

* Durable landing of audit and archive streams
* Must not backpressure the hot path beyond policy

#### A.2.4 Learning/evolution (delayed supervision)

* Dataset builds, training/eval, promotion and rollback
* Must be time-causal and auditable; latency is less critical than correctness and governance

---

### A.3 Traffic envelope structure (steady, burst, soak, recovery)

Every envelope (RC2-S and RC2-L) defines the same shape:

#### A.3.1 Steady profile

* A sustained rate intended to represent typical operation.
* Must run long enough to generate meaningful p95/p99 distributions.

Fields:

* `steady_rate` (events/sec)
* `steady_duration`
* `steady_min_processed_events`

#### A.3.2 Burst profile

* A short spike meant to model peak demand or retry storms.
* Used to prove backpressure and recovery behavior.

Fields:

* `burst_rate` or `burst_multiplier`
* `burst_duration`
* `burst_ramp_style` (step vs ramp)

#### A.3.3 Recovery profile

* The period after burst where the system must return to stable.
* “Stable” is defined as: lag and latency within thresholds, error rates normalized.

Fields:

* `recovery_bound_seconds`
* `stability_definition` (which metrics must be back under threshold)

#### A.3.4 Soak profile

* Sustained operation to surface slow failures:

  * state growth, checkpoint drift, sink backpressure, cost creep.

Fields:

* `soak_rate` (often equal to steady or p95 steady)
* `soak_duration`
* `soak_drift_checks` (what must not worsen over time)

---

### A.4 Cohort realism assumptions (what must be present in the load)

The envelope is not “clean traffic.” It includes production messiness derived from the 7d profile.

Each envelope must define minimum cohort presence:

* **Duplicates cohort**: % duplicate attempts by dedupe key
* **Out-of-order cohort**: % late events / ordering violations
* **Hot-key skew**: top keys contribute at least X% of volume (or a target skew band)
* **Payload extremes**: % near max payload size
* **Event mix**: distribution of event types (or a minimum set)

These are taken from:

* `g2_load_campaign_seed.json`
* `g2_profile_rollup.json`

---

### A.5 Data volume and window assumptions (what “voluminous” means in dev_full)

Dev_full production-ready does not require bank-scale absolute volume, but it must be:

* large enough to produce stable p95/p99 distributions,
* large enough to expose skew and checkpoint/state behavior,
* large enough to exercise replay integrity meaningfully.

Therefore, RC2-S must specify:

* minimum processed events per phase
* minimum replay window size that produces meaningful integrity checks
* minimum number of unique keys (flow_id/merchant_id/entity_id) present in the run

**Important:** “unique keys” must be actual join/partition keys (e.g., flow_id), not proxy counts like “event types.”

---

### A.6 Latency and lag budget model (how you interpret SLOs)

The envelope is tied to SLOs.

#### A.6.1 Hot path latency budgets

Define end-to-end boundary precisely:

* start: IG admission timestamp (or MSK injection timestamp if via_MSK)
* end: decision commit timestamp (and/or action/audit commit timestamp)

Report:

* p50/p95/p99 latency
* error/timeout rates
* recovery time-to-stable

#### A.6.2 Streaming lag budgets

Report:

* consumer lag p95/p99
* checkpoint success and checkpoint duration p95
* backlog recovery bound

**Note:** Lag budgets must be interpreted with skew in mind: one hot partition can dominate.

---

### A.7 Replay/backfill window assumptions (correctness under reprocessing)

Replay is essential for production credibility.

Each envelope must define:

* `replay_window_size_min` (meaningful size)
* `replay_time_to_complete_bound`
* invariants to check:

  * no double side effects
  * consistent decision counts
  * consistent aggregates (if used)
  * audit trail includes replay provenance

A replay window is only meaningful if it:

* exercises duplicates/out-of-order behavior, and
* produces enough events to catch “double write” bugs.

---

### A.8 Learning window assumptions (time-causal supervision)

To respect “no future Oracle”:

* events/features must satisfy `event_ts <= as_of_time`
* labels must satisfy `label_available_ts <= as_of_time - maturity_lag`
* if labels are sparse, the eligible labeled subset may be a smaller slice of the window (acceptable if explicitly declared)

G2 produces:

* label maturity distribution
* recommended maturity lag candidates

RC2-S uses that to pin the learning window spec for mission runs.

---

### A.9 Cost envelope assumptions (what “bounded spend” means)

Each envelope must define:

* total budget envelope (USD)
* per-run budget envelope (optional)
* unit cost targets:

  * cost per N events processed
  * cost per replay
  * cost per training/eval run
* idle burn ceiling
* enforcement behavior on breach:

  * alert/throttle/stop/teardown

The envelope is invalid if:

* cost cannot be attributed to lanes or at least to major categories,
* teardown cannot verify idle-safe posture.

---

### A.10 Injection path assumptions (what is being certified)

The envelope must declare injection path:

* `via_IG`:

  * certifies IG truth boundary performance and end-to-end behavior
* `via_MSK`:

  * certifies hot path compute and sinks but does not certify IG throughput

A production-ready declaration should prefer `via_IG`, but `via_MSK` is acceptable for hot-path capacity testing as long as claims are scoped correctly.

---

### A.11 Validation methods (how envelope compliance is proven)

Envelope compliance must be proven with:

1. **Scorecard run**: steady→burst→recovery→soak
2. **Cohort report**: duplicates/out-of-order/hot-key/payload extremes included
3. **Drill pack**: replay integrity, lag recovery, schema evolution, dependency degrade, cost guardrail
4. **Evidence bundle index**: all artifacts present and readable
5. **Blocker register**: open_blockers=0 for PASS

---

### A.12 How the envelope evolves without drift

* RC2-S values may be updated only via the calibration procedure (Section 12):

  * measured baselines inform targets
  * targets remain policy with guardbands
* RC2-L can be revised freely as aspirational but must not block RC2-S certification unless promoted into scope via change control.

---

### Appendix A.1 Workload envelope template (fill-in form for RC2-S / RC2-L)

Use this as a **machine-checkable** template Codex can populate. It is intentionally fields-only (no prose) so it can be validated automatically and compared across runs.

Copy this block twice:

* once for **RC2-S (required)**
* once for **RC2-L (stretch)**

```yaml
envelope_id: RC2-S                # RC2-S (required) or RC2-L (stretch)
envelope_version: v0
status: DRAFT                     # DRAFT | ACTIVE | FROZEN
effective_date_utc: TBD
owner: Codex
approved_by: Esosa                # optional

# 1) Charter / scope
mission_binding:
  mission_name: DEV_FULL_PROD_GRADE_RUN_v0
  platform_run_id: TBD            # filled when executed
  scenario_run_id: TBD            # filled when executed
  manifest_fingerprint: "{manifest_fingerprint}"
  scenario_id: TBD
  window_start_ts_utc: TBD
  window_end_ts_utc: TBD
  as_of_time_utc: TBD
  label_maturity_lag: TBD

# 2) Injection path (required for claim scope)
injection_path:
  mode: via_IG                    # via_IG | via_MSK
  scope_notes: TBD                # what this envelope is allowed to certify

# 3) Load campaign shape (steady/burst/recovery/soak)
load_campaign:
  steady:
    rate_eps: TBD                 # policy target
    duration_min: TBD             # policy target
    min_processed_events: TBD     # policy target
    ramp_style: step              # step | ramp
  burst:
    rate_eps: TBD                 # policy target (or use multiplier below)
    multiplier: TBD               # optional; if set, rate_eps can be derived
    duration_min: TBD             # policy target
    ramp_style: step              # step | ramp
  recovery:
    bound_seconds: TBD            # time-to-return-to-stable
    stable_definition:
      lag_p99_max: TBD
      latency_p99_max_ms: TBD
      error_rate_max: TBD
  soak:
    rate_eps: TBD                 # optional; often equals steady
    duration_min: TBD
    drift_checks:
      lag_p99_drift_max: TBD
      latency_p99_drift_max_ms: TBD
      error_rate_drift_max: TBD

# 4) Cohort realism requirements (derived from G2; must be present)
cohorts:
  duplicates:
    enabled: true
    min_duplicate_attempt_rate: TBD        # e.g., 0.5% of events retried
    dedupe_key: TBD                        # what key is used for idempotency
  out_of_order:
    enabled: true
    min_late_event_rate: TBD
    allowed_lateness_seconds: TBD          # watermark/late policy
    handling_policy: TBD                   # drop | side_output | reprocess
  hot_keys:
    enabled: true
    key_name: TBD                          # flow_id / merchant_id / entity_id
    top_0_1pct_volume_share_min: TBD       # skew floor to ensure realism
    mitigation_policy: TBD                 # salting | capping | side_path
  payload_extremes:
    enabled: true
    p99_payload_bytes_max: TBD
    max_payload_bytes_hard_limit: TBD
  event_mix:
    enabled: true
    expected_event_type_distribution_ref: TBD  # pointer to G2 profile artifact

# 5) Sample/coverage minima (anti-toy requirements)
sample_minima:
  min_total_processed_events: TBD
  min_unique_flow_id: TBD
  min_unique_merchant_id: TBD
  max_unmatched_join_rate: TBD             # from G2 join matrix decision
  max_fanout_p99: TBD                      # fanout limit for joins
  replay:
    replay_window_min_events: TBD
    replay_time_to_complete_bound_seconds: TBD

# 6) SLO / thresholds (policy targets; map to Tier-0 claims)
thresholds:
  hot_path_slo:
    decision_latency_ms:
      p95_max: TBD
      p99_max: TBD
    error_rate_max: TBD
    timeout_rate_max: TBD
  streaming_health:
    consumer_lag:
      p95_max: TBD
      p99_max: TBD
    checkpoints:
      success_rate_min: TBD
      duration_ms_p95_max: TBD
  correctness:
    duplicate_admission_rate_max: TBD
    quarantine_rate_max: TBD
    quarantine_top_reasons_required: true
    invariants_required:
      - no_double_side_effects
      - consistent_decision_counts
  observability:
    correlation_coverage_min: TBD
    ttd_seconds_p90_max: TBD               # time-to-detect (from drills)
    ttdiag_seconds_p90_max: TBD            # time-to-diagnose (from drills)
  cost:
    budget_envelope_usd: TBD
    unit_cost:
      cost_per_1m_events_usd_max: TBD
      cost_per_replay_usd_max: TBD
    idle_burn_usd_per_day_max: TBD

# 7) Measurement surfaces (mandatory; prevents wrong-metric certification)
measurement_surfaces:
  throughput:
    steady_surface: TBD                    # IG_ADMITTED | MSK_CONSUMED | FLINK_PROCESSED | DECISION_COMMITTED
    burst_surface: TBD
  latency:
    e2e_start: TBD                         # IG_ADMISSION_TS | MSK_INJECT_TS
    e2e_end: TBD                           # DECISION_COMMIT_TS | ACTION_COMMIT_TS
  lag:
    surface: MSK_CONSUMER_LAG
  costs:
    surface: COST_EXPLORER_ATTRIBUTED      # or billing tags if used

# 8) Required drills (must be executed for claimability)
drills_required:
  - replay_integrity
  - lag_spike_recovery
  - schema_evolution
  - dependency_degrade
  - audit_drill
  - cost_guardrail_idle_safe
  - rollback_drill                         # may be executed in G3B but referenced here

# 9) Evidence outputs (deterministic names)
evidence_contract:
  evidence_root: "evidence/dev_full/production_ready"
  pack_name: G3A_RUNTIME_CERT_PACK_RC2S
  required_files:
    - evidence_index.json
    - verdict.json
    - blocker_register.json
    - run_charter.json
    - g3a_scorecard_steady.json
    - g3a_scorecard_burst.json
    - g3a_scorecard_recovery.json
    - g3a_scorecard_soak.json
    - g3a_scorecard_report.md
    - g3a_cohort_manifest.json
    - g3a_cohort_results.json
    - g3a_drill_replay_integrity.json
    - g3a_drill_lag_recovery.json
    - g3a_drill_schema_evolution.json
    - g3a_drill_dependency_degrade.json
    - g3a_drill_cost_guardrail.json

# 10) Policy vs measured baselines (prevents “observed becomes standard”)
calibration:
  baseline_run_refs: []                    # list of run ids / artifact refs used as baselines
  rows:
    - metric: decision_latency_ms.p99
      type: policy                         # policy | measured
      baseline_value: TBD                  # measured baseline
      target_value: TBD                    # policy target
      guardband: TBD                       # headroom or strictness margin
      source_ref: TBD                      # artifact pointer

# 11) Change log (mandatory for updates)
changelog:
  - date_utc: TBD
    author: Codex
    change_summary: "initial draft"
    rationale: "TBD"
```

---

Here’s a **validator checklist** for the Appendix A workload envelope file (the YAML template in **A.1**). It’s designed to prevent the exact failure mode you’re fighting: “we ran something small / measured the wrong surface / declared it production-like.”

You can implement this as a script/CI check, and you can also use it manually.

---

## Workload Envelope Validator Checklist (Appendix A.1)

### 1) File-level integrity

* [ ] File exists at the canonical path referenced by the evidence pack index.
* [ ] YAML parses successfully.
* [ ] `envelope_id` is either `RC2-S` or `RC2-L`.
* [ ] `envelope_version` set (e.g., `v0`).
* [ ] `status` is one of: `DRAFT | ACTIVE | FROZEN`.
* [ ] `owner` set.

**Fail-closed code:** `ENV_FILE_INVALID`

---

### 2) Mission binding completeness

* [ ] `mission_binding.mission_name` set (must match the mission profile name).
* [ ] `mission_binding.manifest_fingerprint` present and matches the required token format (`{manifest_fingerprint}`).
* [ ] `mission_binding.scenario_id` set.
* [ ] `mission_binding.window_start_ts_utc` and `window_end_ts_utc` set.
* [ ] `mission_binding.as_of_time_utc` set.
* [ ] `mission_binding.label_maturity_lag` set (explicitly, even if “0d”).
* [ ] `mission_binding.platform_run_id` and `scenario_run_id` may be TBD in DRAFT, but **must be set** in ACTIVE/FROZEN.

**Fail-closed code:** `ENV_MISSION_UNBOUND`

---

### 3) Injection path declared and scoping notes present

* [ ] `injection_path.mode` is exactly `via_IG` or `via_MSK`.
* [ ] `injection_path.scope_notes` is non-empty and explicitly states what claims are allowed.

  * If `via_MSK`, it must explicitly say it **does not certify IG capacity/envelope**.

**Fail-closed code:** `ENV_INJECTION_PATH_INVALID`

---

### 4) Load campaign shape is complete

For **steady/burst/recovery/soak**, verify required fields:

**Steady**

* [ ] `load_campaign.steady.rate_eps` set and numeric > 0.
* [ ] `load_campaign.steady.duration_min` set and numeric > 0.
* [ ] `load_campaign.steady.min_processed_events` set and numeric > 0.
* [ ] `load_campaign.steady.ramp_style` is `step` or `ramp`.

**Burst**

* [ ] Either `burst.rate_eps` OR `burst.multiplier` must be set (at least one).
* [ ] If `multiplier` is set, it must be > 1.
* [ ] `burst.duration_min` set > 0.
* [ ] `burst.ramp_style` valid.

**Recovery**

* [ ] `recovery.bound_seconds` set > 0.
* [ ] `recovery.stable_definition` fields set:

  * `lag_p99_max`
  * `latency_p99_max_ms`
  * `error_rate_max`

**Soak**

* [ ] `soak.duration_min` set > 0.
* [ ] `soak.rate_eps` either set > 0 or explicitly omitted with a rule “soak uses steady rate.”
* [ ] `soak.drift_checks` fields set:

  * `lag_p99_drift_max`
  * `latency_p99_drift_max_ms`
  * `error_rate_drift_max`

**Fail-closed code:** `ENV_CAMPAIGN_INCOMPLETE`

---

### 5) Anti-toy consistency checks (math + meaning)

These checks prevent “tiny runs” from being called steady/burst/soak.

* [ ] Steady consistency:
  `steady.rate_eps * steady.duration_min * 60 >= steady.min_processed_events`
  (Allow a small tolerance; but not orders of magnitude.)
* [ ] Burst consistency (if `burst.rate_eps` set):
  `burst.rate_eps * burst.duration_min * 60 >= some_min_burst_events` (must be pinned in `sample_minima` or derived).
* [ ] Recovery bound is not trivial:

  * must be less than or equal to a sensible fraction of soak duration (e.g., recovery bound <= 25% of soak duration in seconds).
* [ ] Soak duration is meaningfully longer than burst:

  * soak duration >= 3× burst duration (or explicit justification).

**Fail-closed code:** `ENV_ANTI_TOY_FAIL`

---

### 6) Cohort realism requirements present and non-trivial

For each cohort block:

**Duplicates**

* [ ] `duplicates.enabled == true`
* [ ] `min_duplicate_attempt_rate` set and > 0 (not zero).
* [ ] `dedupe_key` set.

**Out-of-order**

* [ ] `out_of_order.enabled == true`
* [ ] `min_late_event_rate` set and >= 0
* [ ] `allowed_lateness_seconds` set > 0
* [ ] `handling_policy` set (drop/side_output/reprocess)

**Hot keys**

* [ ] `hot_keys.enabled == true`
* [ ] `key_name` set
* [ ] `top_0_1pct_volume_share_min` set and > 0
* [ ] `mitigation_policy` set (salting/capping/side_path)

**Payload extremes**

* [ ] `payload_extremes.enabled == true`
* [ ] `p99_payload_bytes_max` set > 0
* [ ] `max_payload_bytes_hard_limit` set > 0
* [ ] `p99_payload_bytes_max <= max_payload_bytes_hard_limit`

**Event mix**

* [ ] `event_mix.enabled == true`
* [ ] `expected_event_type_distribution_ref` set (points to G2 artifact)

**Fail-closed code:** `ENV_COHORTS_INVALID`

---

### 7) Sample minima and join realism minima present

These are mandatory to prevent “it ran but taught us nothing.”

* [ ] `sample_minima.min_total_processed_events` set > 0.
* [ ] `min_unique_flow_id` set > 0.
* [ ] `min_unique_merchant_id` set > 0.
* [ ] `max_unmatched_join_rate` set between 0 and 1 (or 0–100% explicitly with unit).
* [ ] `max_fanout_p99` set > 0.

**Replay minima**

* [ ] `sample_minima.replay.replay_window_min_events` set and meaningfully > 0.
* [ ] `replay_time_to_complete_bound_seconds` set > 0.

**Fail-closed code:** `ENV_SAMPLE_MINIMA_MISSING`

---

### 8) Tier-0 thresholds completeness (policy targets, not just baselines)

Ensure the envelope includes thresholds for each family:

**Hot path SLO**

* [ ] `decision_latency_ms.p95_max` set
* [ ] `decision_latency_ms.p99_max` set
* [ ] `error_rate_max` set
* [ ] `timeout_rate_max` set

**Streaming health**

* [ ] `consumer_lag.p95_max` and `p99_max` set
* [ ] `checkpoints.success_rate_min` set
* [ ] `checkpoints.duration_ms_p95_max` set

**Correctness**

* [ ] `duplicate_admission_rate_max` set
* [ ] `quarantine_rate_max` set
* [ ] `quarantine_top_reasons_required == true`
* [ ] `invariants_required` includes at least:

  * `no_double_side_effects`
  * `consistent_decision_counts`

**Observability**

* [ ] `correlation_coverage_min` set
* [ ] `ttd_seconds_p90_max` set
* [ ] `ttdiag_seconds_p90_max` set

**Cost**

* [ ] `budget_envelope_usd` set
* [ ] `cost_per_1m_events_usd_max` set
* [ ] `idle_burn_usd_per_day_max` set
* [ ] `costs per replay` thresholds if replay is required (`cost_per_replay_usd_max`)

**Fail-closed code:** `ENV_THRESHOLDS_INCOMPLETE`

---

### 9) Measurement surfaces are declared (prevents “wrong metrics”)

* [ ] `measurement_surfaces.throughput.steady_surface` set to one of:

  * `IG_ADMITTED`, `MSK_CONSUMED`, `FLINK_PROCESSED`, `DECISION_COMMITTED`, `SINK_WRITTEN`
* [ ] `measurement_surfaces.throughput.burst_surface` set similarly.
* [ ] `measurement_surfaces.latency.e2e_start` set (`IG_ADMISSION_TS` or `MSK_INJECT_TS`).
* [ ] `measurement_surfaces.latency.e2e_end` set (`DECISION_COMMIT_TS` or `ACTION_COMMIT_TS`).
* [ ] `measurement_surfaces.lag.surface == MSK_CONSUMER_LAG`
* [ ] `measurement_surfaces.costs.surface` set (`COST_EXPLORER_ATTRIBUTED` or equivalent).

**Fail-closed code:** `ENV_MEASUREMENT_SURFACE_MISSING`

---

### 10) Required drills list matches gate requirements

* [ ] `drills_required` includes at least:

  * `replay_integrity`
  * `lag_spike_recovery`
  * `schema_evolution`
  * `dependency_degrade`
  * `audit_drill`
  * `cost_guardrail_idle_safe`
  * `rollback_drill`
* [ ] If `rollback_drill` is not executed in G3A, the envelope must explicitly note “rollback handled in G3B” in `injection_path.scope_notes` or a dedicated field.

**Fail-closed code:** `ENV_DRILLS_INCOMPLETE`

---

### 11) Evidence contract completeness

* [ ] `evidence_contract.evidence_root` set.
* [ ] `pack_name` set (e.g., `G3A_RUNTIME_CERT_PACK_RC2S`).
* [ ] `required_files` includes:

  * `evidence_index.json`, `verdict.json`, `blocker_register.json`, `run_charter.json`
  * scorecard files (steady/burst/recovery/soak)
  * cohort manifest and results
  * required drill bundles

**Fail-closed code:** `ENV_EVIDENCE_CONTRACT_INCOMPLETE`

---

### 12) Calibration row structure (prevents “observed becomes standard”)

For each entry in `calibration.rows`:

* [ ] `metric` set (valid dotted path).
* [ ] `type` is `policy` or `measured`.
* [ ] `baseline_value` set if type is policy (baseline must exist to justify).
* [ ] `target_value` set if type is policy.
* [ ] `guardband` set if type is policy.
* [ ] `source_ref` set (artifact pointer) for any baseline.

**Fail-closed code:** `ENV_CALIBRATION_TRACE_MISSING`

---

### 13) Status gating rules: DRAFT vs ACTIVE vs FROZEN

If `status == DRAFT`:

* allowed to have `TBD` fields, but must be syntactically valid.

If `status == ACTIVE`:

* [ ] No `TBD` anywhere in required sections (campaign, cohorts, sample minima, thresholds, measurement surfaces, evidence contract).
* [ ] `effective_date_utc` set.
* [ ] `calibration.baseline_run_refs` non-empty (must cite at least one baseline).

If `status == FROZEN`:

* [ ] All ACTIVE rules hold.
* [ ] `changelog` includes an entry: “Frozen for mission `<platform_run_id>`” with date and rationale.

**Fail-closed code:** `ENV_NOT_ACTIVATABLE`

---

## Recommended validator output

When implemented, output:

* `overall_valid: true/false`
* list of failures:

  * `code`, `path`, `message`
* `status_recommendation: DRAFT|ACTIVE|FROZEN`

---

## Appendix B. Failure-mode catalog + drill matrix (production-ready dev_full)

This appendix defines the **minimum failure modes** the platform must survive to be considered production-ready (dev_full), and the **drills** that must be executed to prove it. It is intentionally concrete so the mission run cannot “look good” without being resilient.

**Hard rule:** A claim is not production-ready unless its associated drills have been executed and the drill bundles are present and readable.

---

### B.1 Principles

1. **Production means failure is normal.** Retries, duplicates, replays, lag spikes, and partial outages are expected.
2. **Drills must be time-bounded.** Each drill must record: detection time, diagnosis time, recovery time, and integrity verification.
3. **Drills must be attributable.** Every drill must specify:

   * injection path (`via_IG` or `via_MSK`)
   * measurement surfaces used for success criteria
4. **Drills produce durable evidence bundles.** No “we did it” without artifacts.

---

### B.2 Drill bundle schema (required for every drill)

Every drill must emit a JSON bundle with the following fields:

* `drill_id`
* `run_id` / `platform_run_id`
* `scenario` (what failed / what was injected)
* `expected_behavior`
* `injection_method`
* `timestamps`:

  * `start_utc`
  * `detect_utc`
  * `diagnose_utc`
  * `mitigation_start_utc`
  * `stable_utc`
* `metrics_before` / `metrics_during` / `metrics_after`
* `recovery_bound_seconds` and `recovery_bound_met`
* `integrity_checks` (PASS/FAIL + details)
* `artifacts` (links to logs/dashboards/queries used)
* `runbook_ref` (which runbook was followed)
* `blockers_emitted` (if any)

---

### B.3 Failure-mode catalog (what can go wrong, by plane)

#### Plane 1: Ingestion truth boundary (IG)

**FM-IG-01 Duplicate delivery / client retries**

* Risk: double side effects if idempotency fails.
* Proof: dedupe hit rate, duplicate-admission rate, side-effect invariants.

**FM-IG-02 Invalid/oversize payload**

* Risk: hot path polluted; undefined failures; cost spikes.
* Proof: 413 response, quarantine reason distribution, no downstream decisions for rejected payloads.

**FM-IG-03 DDB throttling / hot partitions**

* Risk: admission collapses under skew, platform appears “slow”.
* Proof: throttling signals visible, mitigation exists (rate limit / backoff / key spread).

#### Plane 2: MSK (bus) and consumer health

**FM-MSK-01 Consumer lag spike**

* Risk: backlog grows, misses SLO, time-causal logic breaks.
* Proof: lag p95/p99, recovery-to-stable bound met.

**FM-MSK-02 Producer errors or broker instability**

* Risk: silent drops, partial ingestion.
* Proof: errors surfaced, no silent loss; mitigation steps.

#### Plane 3: Stream compute (Flink)

**FM-FLK-01 Checkpoint failure**

* Risk: state corruption, restart loops.
* Proof: checkpoint failure detected; stable recovery; integrity invariants hold.

**FM-FLK-02 Backpressure / state blow-up**

* Risk: lag grows indefinitely, cost explodes.
* Proof: backpressure detected; mitigation executed (scale/TTL/tuning); recovery bound met.

**FM-FLK-03 Out-of-order event handling**

* Risk: windows produce wrong projections; joins inconsistent.
* Proof: watermarks/allowed lateness policy applied; late events handled per policy.

#### Plane 4: State stores (Aurora / Redis)

**FM-DB-01 Aurora latency / connection saturation**

* Risk: p99 decision latency spikes, timeouts.
* Proof: saturation detected; mitigation (pool config/index/batching); stable restored.

**FM-REDIS-01 Redis latency/outage**

* Risk: feature/join failures; decision degradation.
* Proof: degrade mode triggers safely; recovery verified.

#### Plane 5: Decision + Audit + Archive sinks

**FM-DL-01 Decision path regression**

* Risk: errors/latency post-change; user impact.
* Proof: post-change observation detects it; rollback executed.

**FM-AUD-01 Audit sink backlog**

* Risk: audit truth delayed; S3 sink backpressure.
* Proof: backlog detected and bounded; no hot-path collapse.

**FM-ARCH-01 Tiny-file explosion**

* Risk: offline queries unusable; costs rise.
* Proof: file sizing/partitioning enforced; metrics show acceptable file counts.

#### Plane 6: Learning and promotion corridor

**FM-LRN-01 Leakage (“future rows”)**

* Risk: invalid models; fake performance.
* Proof: leakage checks fail-closed; no training on future rows.

**FM-LRN-02 Dataset immutability violation**

* Risk: training not reproducible; audits impossible.
* Proof: fingerprint mismatch blocks promotion.

**FM-PROM-01 Promotion transport ambiguity**

* Risk: active bundle undefined; cannot prove what’s running.
* Proof: ack + readback + hash match required; fail-closed if not satisfied.

---

### B.4 Mandatory drill set (production-ready dev_full)

These are the drills that must appear in G3A/G3B/G4 evidence packs.

#### DR-01 Replay/backfill integrity drill (T0.3)

* Inject: replay a bounded window.
* Prove: invariants PASS (no double side effects; consistent counts).
* Evidence: `drill_replay_integrity.json`.

#### DR-02 Lag spike + recovery drill (T0.2/T0.3/T0.4)

* Inject: controlled lag/backpressure (pause consumer, reduce parallelism, etc.).
* Prove: detect → diagnose → recover within bound; lag returns under threshold.
* Evidence: `drill_lag_recovery.json`.

#### DR-03 Schema evolution drill (T0.3)

* Inject: compatible + incompatible schema change.
* Prove: compatible passes; incompatible quarantined/blocked; no silent corruption.
* Evidence: `drill_schema_evolution.json`.

#### DR-04 Dependency degrade drill (T0.2/T0.4)

* Inject: Aurora latency spike or Redis impairment.
* Prove: degrade posture activates safely; recovery bound met; stability verified.
* Evidence: `drill_dependency_degrade.json`.

#### DR-05 Promotion + rollback drill (T0.1)

* Inject: promote candidate; trigger rollback criteria.
* Prove: rollback restores LKG within bound; ACTIVE points to LKG; stability verified.
* Evidence: `drill_rollback.json`.

#### DR-06 Audit drill (T0.5)

* Inject: pick a decision/event from run.
* Prove: answer “what ran and why” within bound; completeness PASS.
* Evidence: `drill_audit.json`.

#### DR-07 Cost guardrail + idle-safe drill (T0.6)

* Inject: cost threshold breach simulation or controlled stop condition.
* Prove: enforcement action occurs; teardown clean; idle_safe=true.
* Evidence: `drill_cost_guardrail.json`.

---

### B.5 Drill-to-claim mapping (what each drill makes claimable)

| Claim                              | Drill(s) Required                            |
| ---------------------------------- | -------------------------------------------- |
| T0.2 Hot path SLO-grade            | DR-02, DR-04 (+ steady/burst/soak scorecard) |
| T0.3 Replay-safe correctness       | DR-01, DR-02, DR-03                          |
| T0.1 Governed promotion + rollback | DR-05                                        |
| T0.5 Auditability                  | DR-06                                        |
| T0.6 Cost control                  | DR-07                                        |
| T0.4 Observability/diagnosability  | DR-02, DR-04, DR-06 (TTD/TTDiag captured)    |

---

### B.6 Drill cadence (how often you run them)

For production-ready dev_full:

* **During G3A:** DR-01, DR-02, DR-03, DR-04, DR-07 (runtime posture)
* **During G3B:** DR-05, DR-06 (governance posture)
* **During G4:** at least one incident drill (DR-02 or DR-04), one controlled change + rollback readiness (DR-05), plus audit and cost closure (DR-06, DR-07)

---

### B.7 Pass/fail rules (how drills are judged)

A drill PASS requires:

* recovery bound met (`stable_utc - start_utc <= bound`)
* integrity checks PASS (no double side effects, no corruption)
* evidence bundle complete and readable
* blocker_register empty (or only non-mission-blocking notes if explicitly allowed)

A drill FAIL requires:

* a blocker code
* rerun boundary definition
* remediation plan

---

### B.8 Anti-gaming rules for drills

* Drills cannot be “toy sized.” Replay windows and lag spikes must be meaningful.
* Drills must be run under a declared envelope (RC2-S).
* Drills must use the correct measurement surfaces.
* Drills must reference the runbook used and capture TTD/TTDiag.

---

### Appendix B.1 Drill injection methods (safe, controlled, production-shaped)

This section gives **practical, controlled ways** to trigger each drill in a **dev_full production-like environment** *without* turning it into chaos engineering for its own sake.

**Safety rules (mandatory)**

* Run drills only in **dev_full rehearsal/cert windows** with a pinned budget envelope and a rollback plan.
* Use **explicit “injection on/off” switches** (feature flags, config toggles, or a dedicated drill harness), and record exactly what was changed.
* Prefer **reversible degradations** (latency injection, throttling, pausing consumers) over destructive actions.
* Always capture **before/during/after** metrics and verify **integrity checks** (no double side effects, no silent drops).

---

## B.1.1 DR-02 Lag spike + recovery drill (create lag/backpressure safely)

**Goal:** Force consumer lag to rise, then prove detection → localization → mitigation → recovery within the bound.

### Option A — Pause/slow the consumer (cleanest, reversible)

* Temporarily **pause** the Flink consumer (or reduce its processing rate) while producers continue.
* How (examples of mechanisms):

  * Reduce Flink application parallelism to a low value for a short window.
  * Toggle a “slow mode” flag in the consumer pipeline that adds a small controlled delay per batch/window (bounded sleep).
  * Temporarily pause the consumer group (where your tooling permits controlled pausing).

**Why this is good:** You get deterministic lag growth and deterministic recovery by restoring normal settings.

### Option B — Increase producer rate (burst) beyond consumer capacity briefly

* Run the burst phase so ingest > processing capacity for a bounded duration.
* This is best when your campaign generator is reliable and you want “realistic peak”.

**Watch out:** Don’t confuse “producer overload” with “IG throttles” if you’re `via_IG`. Label the injection path.

### Option C — Hot-key skew injection (production-realistic lag)

* Route a disproportionate share of events to a small set of keys (hot flows/merchants).
* This creates lag in one partition even when total EPS is unchanged.

**Why this is valuable:** It’s the most common real-world failure mode for stream systems.

**Required evidence for all lag drills**

* Lag p95/p99 before/during/after
* Checkpoint success rate + checkpoint duration
* Recovery-to-stable time (time until lag and latency are back under thresholds)
* Clear mitigation action record (what you changed to recover)

---

## B.1.2 DR-03 Schema evolution drill (compatible vs incompatible)

**Goal:** Prove schema change behavior is intentional:

* compatible change flows through safely,
* incompatible change is blocked/quarantined (fail-closed),
* no silent corruption.

### Compatible change injection patterns

Choose one:

* **Add an optional field** (new field that is not required).
* **Add a new event type** that is allowed by a versioned contract and routes safely.
* **Add a new enum value** that your consumer treats as “unknown-but-safe” (routes to a known fallback path).

**Expected outcome:** events are accepted, downstream processors continue, and new field is either used or ignored safely.

### Incompatible change injection patterns

Choose one:

* **Remove a required field** from the payload.
* **Change a field type** (string → number, object → string).
* **Change key semantics** (e.g., `flow_id` missing or malformed).
* **Break the contract intentionally** for a subset of events.

**Expected outcome:** events are rejected/quarantined with clear reason taxonomy; no downstream decisions are produced from quarantined inputs.

**Required evidence**

* Quarantine rate spike + top reasons (must include the schema violation reason)
* Proof that incompatible events did **not** produce decisions/audit/cases
* Readback of quarantine records and policy evidence (the rule that caused the block)

---

## B.1.3 DR-04 Dependency degrade drill (Aurora/Redis latency/outage)

**Goal:** Prove the platform degrades safely when a dependency is slow/unavailable, and returns to stable.

### Option A — Inject latency in the application (safest)

* Add a temporary, bounded “latency injection” flag in the dependency call path:

  * e.g., add 50–200ms delay before DB query/Redis call for a short window.

**Why this is good:** You don’t break infrastructure; you test platform behavior under slowness.

### Option B — Saturate the dependency with controlled load (realistic)

* Run a controlled “pressure worker” that increases query rate or cache misses for a short window.
* For Aurora: increase concurrent queries within a bounded envelope.
* For Redis: force more cache misses / wider key range.

**Watch out:** You must cap this so you can recover deterministically.

### Option C — Temporary network impairment (advanced, still controlled)

* Use a controlled mechanism (e.g., AWS fault injection tools in your own account) to add network latency or temporarily disrupt connectivity between compute and the dependency.

**Watch out:** Only do this if you can guarantee quick rollback and you are not impacting shared environments.

**Expected platform behavior**

* Degrade mode triggers (or the platform fails closed if degrade is not allowed for that dependency).
* Alerts fire and localization is correct (“dependency latency”, not “mystery failure”).
* Recovery is time-bounded once normal conditions are restored.

**Required evidence**

* Pre/during/post dependency latency p95/p99
* Decision path latency and error rate impact
* Degrade posture activation record (when/why)
* Recovery-to-stable time and integrity checks

---

## B.1.4 DR-01 Replay/backfill integrity drill (meaningful replay, not tiny probes)

**Goal:** Replay a bounded window and prove:

* no double side effects (decisions/cases/audit),
* consistent counts/aggregates,
* replay provenance is auditable.

### Recommended injection pattern

* Choose a replay window that includes:

  * duplicates cohort
  * out-of-order cohort
  * at least one hot key
* Re-run that window through your replay mechanism and compare invariants.

**Evidence**

* Replay window definition (start/end, key filters)
* Invariant checks (PASS/FAIL)
* “No double write” proof for downstream sinks
* Replay completion time bound met

---

## B.1.5 DR-05 Promotion + rollback drill (make rollback unavoidable)

**Goal:** Promote a candidate, observe a regression trigger, rollback to last-known-good, verify stability and traceability.

### Ways to force a rollback condition safely

* **Canary guardrail trigger:** set a canary threshold that the candidate will breach (latency or error rate), so rollback is policy-driven.
* **Synthetic regression trigger:** temporarily enable a “slow mode” in the candidate-serving path so p99 latency breaches.
* **Compatibility mismatch prevention test:** attempt promotion with known incompatibility and prove fail-closed (this is a *non-promotion* drill).

**Evidence**

* Promotion transport proof (ack + readback + hash match)
* Post-promotion observation window snapshot (lag/latency/error tagged by active bundle)
* Rollback drill report with:

  * rollback time bound
  * “ACTIVE points to LKG” proof
  * stability verification

---

## B.1.6 DR-06 Audit drill (prove answerability, not just logging)

**Goal:** For a real decision/event, answer within bound:

* what ran (model/version),
* why it ran (promotion record),
* what data/config produced it (lineage + dataset fingerprint),
* what outcome occurred (audit/action).

### Practical method

* Pick a decision/event ID from the run output.
* Use the platform’s audit queries (pre-pinned query pack) to traverse:
  decision → model bundle → promotion ledger → training run → dataset manifest/fingerprint → config.

**Evidence**

* Audit response time
* Completeness score (required fields present)
* Any missing fields produce blockers (fail-closed)

---

## B.1.7 DR-07 Cost guardrail + idle-safe drill (prove stewardship)

**Goal:** Show you can enforce budgets and return to idle-safe.

### Injection methods

* **Budget threshold breach simulation:** configure a low guardrail threshold for the drill run and prove the enforcement action triggers (alert/throttle/stop/teardown).
* **Idle-safe verification:** after stopping load, verify all “expensive” resources are scaled down or stopped per policy.

**Evidence**

* Budget envelope declaration
* Cost snapshot/receipt
* Enforcement action record
* Residual scan clean + idle_safe=true verification

---

## B.1.8 Injection method selection rules (senior discipline)

* Prefer **Option A style injections** first (controlled, reversible, minimal blast radius).
* Only use “hard” injections (network impairment / forced restarts) after you’ve proven soft injections.
* Every drill must be tied to a **specific claim** and must produce the **drill bundle** described in Appendix B.2.

---

Here’s the drill planner updated with **which gate pack must contain each drill** (G3A Runtime, G3B Ops/Gov, G4 Go-Live Rehearsal). This makes it impossible to “forget” a drill and still claim readiness.

### Drill planner with gate ownership

| Drill ID                                    | Must appear in which pack(s)                                              | What it proves (Tier-0 claim)                                   | Preferred injection (safe-first)                                                                         | Measurement surfaces to record                                                                     | PASS conditions (minimum)                                                                             | Common pitfalls                                                                 |
| ------------------------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **DR-01 Replay/Backfill Integrity**         | **G3A**, optional repeat in **G4**                                        | Replay safety, no double side effects (**T0.3**)                | Replay a pinned window including dupes + out-of-order + at least one hot key                             | Decision-committed count, sink-written count, quarantine count, “double write” invariants          | Invariants PASS, counts consistent, replay completes within bound, replay provenance recorded         | Window too small; comparing wrong counters; missing sink idempotency checks     |
| **DR-02 Lag Spike + Recovery**              | **G3A**, at least one incident drill in **G4**                            | SLO posture + diagnosability under backlog (**T0.2/T0.4/T0.3**) | Reduce consumer capacity briefly (parallelism down or slow-mode), then restore                           | MSK lag p95/p99, checkpoints, e2e latency p95/p99, error rate; **TTD/TTDiag**                      | Alerts fire; localized root cause; mitigation executed; recovery within bound                         | Creating lag via IG throttles; no stable definition; wrong measurement surface  |
| **DR-03 Schema Evolution**                  | **G3A**, optional repeat in **G4**                                        | Fail-closed on incompatible change (**T0.3**)                   | Compatible change then incompatible change for a subset                                                  | Quarantine reasons, downstream decision counts, reject rates                                       | Compatible passes; incompatible quarantined/blocked; no downstream decisions from invalid inputs      | Silent drops; vague reason taxonomy; not exercising consumers                   |
| **DR-04 Dependency Degrade (Aurora/Redis)** | **G3A**, at least one incident drill in **G4**                            | Safe degrade + bounded recovery (**T0.2/T0.4**)                 | App-level latency injection flag or bounded pressure worker                                              | Aurora/Redis latency + saturation, decision latency/errors, degrade posture events; **TTD/TTDiag** | Degrade/fail-closed per policy; alerts localize; recovery within bound; integrity OK                  | Uncontrolled outage; no degrade policy; only infra metrics recorded             |
| **DR-05 Promotion + Rollback**              | **G3B** (mandatory), at least one controlled change in **G4**             | Governed reversible change (**T0.1**)                           | Promote candidate; trigger rollback criteria via canary guardrail or induced regression; rollback to LKG | ACTIVE bundle ID, post-promo latency/error/lag tagged by bundle, rollback time, time-to-stable     | Transport proof; post-promo observation; rollback bound met; ACTIVE points to LKG; stability verified | Promotion without transport proof; rollback not executed; no observation window |
| **DR-06 Audit Drill**                       | **G3B** (mandatory), repeat in **G4** using that run’s decision           | Fast answerability & provenance (**T0.5**)                      | Pick decision/event ID; trace decision→model/version→promotion→training→dataset fingerprint/config       | Audit response time; completeness score; trace chain coverage                                      | Answer within bound; required links present; evidence readable                                        | Screenshots not records; missing version headers; lineage not joinable          |
| **DR-07 Cost Guardrail + Idle-safe**        | **G3A** (runtime cost), **G3B** (governance), mandatory closure in **G4** | Bounded spend + enforced shutdown (**T0.6**)                    | Low threshold drill or breach simulation; verify enforcement; teardown + residual scan                   | Cost receipt, budget adherence, enforcement action log, residual scan count, idle_safe flag        | Guardrail triggers action; receipts produced; residual scan clean; idle_safe=true                     | Receipts without enforcement; hidden resources; wrong unit-cost counter         |

### Extra “gate rule” summary (for Codex)

* **G3A must include:** DR-01/02/03/04/07
* **G3B must include:** DR-05/06 (+ DR-07 governance slice)
* **G4 must include:** at least **one** incident drill (DR-02 or DR-04), **one** controlled change with rollback readiness (DR-05), plus **DR-06** and **DR-07** for final closure.

---

## Appendix C. Monitoring baseline inventory (runtime + ML monitoring derived from 7d profile)

This appendix defines what “good monitoring” means for **production-ready dev_full**. It prevents two failure modes:

1. **Invented dashboards** (thresholds not grounded in real data), and
2. **Infra-only monitoring** (you can’t detect model/data issues or streaming correctness issues).

All baselines here must be derived from the **G2 Data Realism Pack (7d)** and then validated during **G3A/G3B/G4** runs.

---

### C.1 Principles

1. **Baselines come from reality**: thresholds are derived from 7d distributions, not guesses.
2. **Monitoring is layered**: service health + stream health + data health + model/decision health + cost health.
3. **Every alert must be actionable**: alerts must link to a runbook and define “stable again.”
4. **Distributions, not averages**: p50/p95/p99 are default for latency and lag.
5. **Every metric has a measurement surface**: IG-admitted vs MSK-consumed vs Flink-processed vs decision-committed vs sink-written.

---

## C.2 Runtime monitoring inventory (what to monitor continuously)

### C.2.1 Ingestion Gate (IG) monitoring (truth boundary health)

**Metrics**

* Admit rate (events/sec), reject rate, quarantine rate
* p95/p99 IG latency
* DDB idempotency metrics: throttles, hot partition signals, TTL expiry rate
* DLQ message rate (if used)
* Oversize payload rejects (413 rate)

**Baselines from G2**

* expected admit rate bands per time-of-day
* normal quarantine reason distribution
* expected payload size distribution (p95/p99)

**Alerts (examples)**

* IG p99 latency above baseline band for N minutes
* DDB throttles > X for N minutes
* Quarantine rate spike > baseline + guardband
* DLQ rate > baseline + guardband

**Runbook must answer**

* Is this an IG capacity issue, a DDB hotspot, or upstream payload anomaly?
* What mitigation is allowed (throttle, backoff, temporary reject posture)?

---

### C.2.2 MSK monitoring (bus health)

**Metrics**

* Producer error rate, consumer error rate
* Consumer lag p95/p99 per topic/consumer group
* Partition skew signals (if available)
* Rebalance frequency (if applicable)

**Baselines**

* normal lag distribution per topic
* expected lag during burst and expected recovery time

**Alerts**

* Lag p99 breach sustained beyond recovery bound
* Producer error spikes
* Rebalance storm (if observed)

---

### C.2.3 Flink / stream compute monitoring (processing health)

**Metrics**

* Checkpoint success rate
* Checkpoint duration p95
* Backpressure indicators
* Restart count and restart-to-stable time
* Processing latency (operator-level if available)
* State size growth trend (if available)

**Baselines**

* checkpoint duration distribution during steady and soak
* acceptable restart frequency (ideally near zero)

**Alerts**

* checkpoint failures
* checkpoint duration p95 above baseline + guardband
* persistent backpressure
* repeated restarts

**Runbook must answer**

* Is skew causing state blowup?
* Is sink backpressure causing stalls?
* Is parallelism mis-sized?

---

### C.2.4 State stores monitoring (Aurora + Redis)

**Aurora metrics**

* Connection pool usage / saturation
* p95 query latency
* deadlocks/timeouts
* CPU/IO saturation

**Redis metrics**

* p95 latency
* hit rate
* evictions/memory pressure
* connection errors

**Baselines**

* normal query latency distribution under steady and burst
* normal cache hit rate bands

**Alerts**

* Aurora p95 query latency breach sustained
* connection saturation
* Redis latency breach or hit rate collapse

---

### C.2.5 Decision chain monitoring (DF/AL/DLA)

**Metrics**

* Decision commit rate
* Decision error rate
* Action execution success/failure counts
* Audit log write success rate
* Post-promotion metrics by active bundle (tagged)

**Baselines**

* expected decision rates (tied to admit rates)
* normal error rate bands

**Alerts**

* decision commit rate drops below expected while IG is admitting
* error rate spike
* audit sink backlog/lag

---

### C.2.6 Archive/audit sink monitoring (S3 sink health)

**Metrics**

* Sink write throughput (records/sec, bytes/sec)
* Sink backlog (if measurable)
* Failed writes / retries
* File sizing indicators:

  * files/hour
  * average file size
  * tiny-file rate

**Baselines**

* expected bytes/hour from 7d window
* acceptable file size distribution

**Alerts**

* sink backlog growing faster than recovery bound
* tiny-file explosion
* sustained sink errors

---

### C.2.7 Teardown and idle-safe monitoring (cost + resource hygiene)

**Metrics**

* Residual resource count post-teardown
* Idle burn rate (cost/day when idle)
* Unexpected “always-on” resources

**Alerts**

* Idle burn above ceiling
* Residual scan non-zero

---

## C.3 Data health monitoring (data-plane correctness signals)

These are “content” monitors derived from reality profiles.

### C.3.1 Schema/contract compliance

* Schema validation pass rate
* Quarantine reasons by type
* “unknown event type” rate

### C.3.2 Duplicate and replay signals

* Duplicate attempt rate
* Duplicate admission rate (must be near zero)
* Hash mismatch rate (same key, different payload)
* Replay/backfill completion success rate

### C.3.3 Out-of-order and lateness

* Late event rate (per key)
* Max lateness observed
* % events dropped/side-output due to lateness policy

### C.3.4 Skew and hot keys

* Top 0.1% key volume share
* Largest key volume in window
* Skew drift over time (hot keys changing)

**Why these matter:** these signals explain lag spikes and correctness failures far better than CPU graphs.

---

## C.4 Learning and ML monitoring inventory (what you can monitor without pretending)

This is “production-shaped ML monitoring” given label delays.

### C.4.1 Training dataset health (OFS)

* Dataset row count
* Feature missingness rates (top features)
* Key coverage (flow_id coverage, entity id coverage)
* Label coverage rate (within maturity window)
* Leakage guardrail PASS/FAIL

### C.4.2 Model training/eval health (MF)

* Train/eval success rate
* Time-to-train/eval distribution
* Eval metrics vs baseline (whatever you measure: AUC/F1/etc.)
* Reproducibility checks (within tolerance)

### C.4.3 Online inference/model usage health

* Active model/bundle ID distribution (ensure correct version usage)
* Score distribution baseline (p50/p95/p99 of scores)
* Confidence/uncertainty proxy if available
* Decision rate and reason code distribution

### C.4.4 Drift candidates (without labels)

Even without immediate labels, you can monitor:

* feature distribution shifts (PSI/KS on key features)
* score distribution shifts
* rate shifts in key entity reuse signals
* out-of-order and duplicate rate changes

### C.4.5 Label-based performance (delayed)

When labels mature:

* precision/recall proxy (if definable)
* false positive proxy (case escalation rate)
* “model incident rate” (rollbacks due to degradation)

**Important rule:** label-based metrics must be reported with label maturity lag; don’t pretend you have instant truth.

---

## C.5 Monitoring baseline derivation procedure (how to set thresholds)

Each monitored metric must include:

* baseline distribution from 7d realism (p50/p95/p99)
* chosen threshold policy:

  * “baseline p99 + guardband” or
  * “SLO absolute ceiling” where applicable
* the runbook and what action is taken

**Example threshold policy patterns**

* Lag p99 threshold = `baseline_p99 * 1.5` during steady, `baseline_p99 * 2.0` during burst
* Quarantine rate threshold = `baseline + 3σ` or `baseline_p99 + guardband`
* Checkpoint duration threshold = `baseline_p95 + guardband`

---

## C.6 Alert quality standards (production-ready requirement)

To avoid “alert spam”:

* Every critical alert must have:

  * severity
  * owner
  * runbook link
  * stable condition definition
* Track:

  * alert precision (actionability)
  * time-to-detect (TTD)
  * time-to-diagnose (TTDiag)

---

## C.7 Required monitoring artifacts (must exist)

These must be produced as part of G2 and validated in G3/G4:

1. `g2_monitoring_baselines.json` (baseline distributions and proposed thresholds)
2. `monitoring_dashboard_inventory.md` (what dashboards exist, what they show)
3. `alert_inventory.json` (critical alerts, severity, owners)
4. `runbook_index.json` (alert → runbook mapping)
5. `incident_drill_record.json` (at least one incident-style record from a drill)

---

### C.8 Minimum runtime “overview dashboard” (what a senior checks daily)

A production-ready dev_full platform must be able to present, at minimum:

* end-to-end decision latency p95/p99
* MSK lag p95/p99
* Flink checkpoint success/duration
* quarantine rate + top reasons
* duplicate admission rate
* cost burn + idle burn
* active bundle ID + post-promotion health

This is the simplest “senior posture” dashboard set.

---

### Appendix C.1 Monitoring baselines template (fill-in form; derived from G2 7d profile)

This template is designed to be **machine-fillable** and **machine-checkable**. Codex should populate it from:

* `G2_DATA_REALISM_PACK_7D` outputs (profiles, join matrix, label maturity),
* plus validated observations from G3A/G3B/G4 runs.

Copy this as a single file:

`g2_monitoring_baselines.v0.yaml`

```yaml id="jlh9py"
monitoring_baselines_version: v0
status: DRAFT                # DRAFT | ACTIVE | FROZEN
owner: Codex
approved_by: Esosa           # optional
source_packs:
  g2_data_realism_pack_ref: TBD
  g3a_runtime_pack_ref: TBD  # optional
  g3b_ops_gov_pack_ref: TBD  # optional

window_basis:
  window_start_ts_utc: TBD
  window_end_ts_utc: TBD
  as_of_time_utc: TBD
  label_maturity_lag: TBD

# ========== 1) Global rules ==========
rules:
  distribution_required: [p50, p95, p99]
  missing_metric_policy: FAIL_CLOSED
  threshold_policy_default: "baseline_p99 + guardband"
  guardband_default_multiplier: 1.5
  peak_slice_required: true
  injection_path_scope:
    via_IG:
      certifies: [IG, end_to_end_hot_path]
    via_MSK:
      certifies: [stream_compute_hot_path]
      does_not_certify: [IG_capacity]

# ========== 2) Runtime Hot Path (T0.2) ==========
runtime_hot_path:
  decision_latency_ms:
    measurement_surface:
      start: IG_ADMISSION_TS        # or MSK_INJECT_TS for via_MSK runs
      end: DECISION_COMMIT_TS
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      p95_max: TBD                  # policy target
      p99_max: TBD                  # policy target
      guardband_multiplier: TBD
    alerts:
      - alert_id: HP_LATENCY_P99_BREACH
        severity: CRITICAL
        owner: TBD
        runbook_ref: RB_HOTPATH_LATENCY
        stable_condition: "p99 <= p99_max for 10m"
  error_rate:
    measurement_surface: DECISION_ERRORS_PER_TOTAL
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: TBD
    alerts:
      - alert_id: HP_ERROR_RATE_SPIKE
        severity: CRITICAL
        owner: TBD
        runbook_ref: RB_HOTPATH_ERRORS
        stable_condition: "error_rate <= max for 10m"

# ========== 3) Ingestion Gate (IG) (truth boundary) ==========
ingestion_gate:
  admit_rate_eps:
    measurement_surface: IG_ADMITTED_EVENTS_PER_SEC
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      min: TBD                      # optional (detect drops)
      max: TBD                      # optional (detect runaway)
    alerts:
      - alert_id: IG_ADMIT_DROP
        severity: HIGH
        owner: TBD
        runbook_ref: RB_IG_ADMIT_DROP
        stable_condition: "admit_rate within band for 10m"
  ig_latency_ms:
    measurement_surface:
      start: IG_REQUEST_RECEIVED_TS
      end: IG_ADMISSION_TS
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      p99_max: TBD
    alerts:
      - alert_id: IG_LATENCY_P99_BREACH
        severity: HIGH
        owner: TBD
        runbook_ref: RB_IG_LATENCY
        stable_condition: "p99 <= p99_max for 10m"
  quarantine_rate:
    measurement_surface: IG_QUARANTINED_PER_TOTAL
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: TBD
    required_top_reasons:
      - schema_invalid
      - payload_too_large
      - auth_failed
      - contract_violation
    alerts:
      - alert_id: IG_QUARANTINE_SPIKE
        severity: HIGH
        owner: TBD
        runbook_ref: RB_IG_QUARANTINE
        stable_condition: "quarantine_rate <= max for 15m"
  ddb_throttle_events:
    measurement_surface: DDB_THROTTLES
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: TBD
    alerts:
      - alert_id: IG_DDB_THROTTLE
        severity: CRITICAL
        owner: TBD
        runbook_ref: RB_IG_DDB_THROTTLE
        stable_condition: "throttles <= max for 10m"

# ========== 4) MSK / Bus health ==========
bus_health:
  consumer_lag:
    measurement_surface: MSK_CONSUMER_LAG
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      p95_max: TBD
      p99_max: TBD
    alerts:
      - alert_id: MSK_LAG_P99_BREACH
        severity: CRITICAL
        owner: TBD
        runbook_ref: RB_STREAM_LAG_SPIKE
        stable_condition: "lag_p99 <= p99_max for 10m"
  producer_errors:
    measurement_surface: MSK_PRODUCER_ERRORS
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: TBD
    alerts:
      - alert_id: MSK_PRODUCER_ERROR_SPIKE
        severity: HIGH
        owner: TBD
        runbook_ref: RB_MSK_PRODUCER_ERRORS
        stable_condition: "producer_errors <= max for 10m"

# ========== 5) Flink / Stream compute health ==========
stream_compute:
  checkpoints:
    success_rate:
      measurement_surface: FLINK_CHECKPOINT_SUCCESS_RATE
      baseline:
        p50: TBD
        p95: TBD
        p99: TBD
      thresholds:
        min: TBD
    duration_ms:
      measurement_surface: FLINK_CHECKPOINT_DURATION_MS
      baseline:
        p50: TBD
        p95: TBD
        p99: TBD
      thresholds:
        p95_max: TBD
    alerts:
      - alert_id: FLINK_CHECKPOINT_FAIL
        severity: CRITICAL
        owner: TBD
        runbook_ref: RB_FLINK_CHECKPOINT_FAIL
        stable_condition: "success_rate >= min for 10m"
  backpressure:
    measurement_surface: FLINK_BACKPRESSURE
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: TBD
    alerts:
      - alert_id: FLINK_BACKPRESSURE_HIGH
        severity: HIGH
        owner: TBD
        runbook_ref: RB_FLINK_BACKPRESSURE
        stable_condition: "backpressure <= max for 10m"
  restarts:
    measurement_surface: FLINK_RESTART_COUNT
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: TBD

# ========== 6) Data correctness signals (T0.3) ==========
data_correctness:
  duplicate_admission_rate:
    measurement_surface: DUPLICATE_ADMITTED_PER_TOTAL
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: TBD
    alerts:
      - alert_id: DUPLICATE_ADMISSION
        severity: CRITICAL
        owner: TBD
        runbook_ref: RB_DUPLICATE_ADMISSION
        stable_condition: "dup_admission <= max for 10m"
  out_of_order_rate:
    measurement_surface: LATE_EVENT_RATE
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: TBD
    handling_policy_ref: TBD
  hot_key_skew:
    measurement_surface: TOP_0_1PCT_KEY_VOLUME_SHARE
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: TBD
    key_name: TBD
    mitigation_policy_ref: TBD

# ========== 7) State stores ==========
state_stores:
  aurora_query_latency_ms:
    measurement_surface: AURORA_QUERY_LATENCY_MS
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      p95_max: TBD
      p99_max: TBD
    alerts:
      - alert_id: AURORA_LATENCY_SPIKE
        severity: CRITICAL
        owner: TBD
        runbook_ref: RB_AURORA_LATENCY
        stable_condition: "p99 <= p99_max for 10m"
  aurora_conn_saturation:
    measurement_surface: AURORA_CONN_POOL_SATURATION
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: TBD
  redis_latency_ms:
    measurement_surface: REDIS_LATENCY_MS
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      p95_max: TBD
      p99_max: TBD
  redis_hit_rate:
    measurement_surface: REDIS_HIT_RATE
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      min: TBD

# ========== 8) Audit & provenance (T0.5) ==========
auditability:
  trace_coverage:
    measurement_surface: TRACE_CHAIN_COMPLETENESS
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      min: TBD
  audit_response_time_seconds:
    measurement_surface: AUDIT_DRILL_RESPONSE_TIME
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      p95_max: TBD
  provenance_completeness:
    measurement_surface: PROVENANCE_FIELDS_PRESENT_RATE
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      min: TBD

# ========== 9) Cost (T0.6) ==========
cost:
  budget_envelope_usd:
    value: TBD
  unit_cost_per_1m_events_usd:
    measurement_surface: COST_PER_1M_EVENTS
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: TBD
  idle_burn_usd_per_day:
    measurement_surface: IDLE_BURN_USD_PER_DAY
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: TBD
  residual_scan_count:
    measurement_surface: RESIDUAL_RESOURCE_COUNT
    baseline:
      p50: TBD
      p95: TBD
      p99: TBD
    thresholds:
      max: 0

# ========== 10) Runbook index (must exist for production-ready) ==========
runbooks:
  required:
    - RB_HOTPATH_LATENCY
    - RB_HOTPATH_ERRORS
    - RB_IG_ADMIT_DROP
    - RB_IG_LATENCY
    - RB_IG_QUARANTINE
    - RB_IG_DDB_THROTTLE
    - RB_STREAM_LAG_SPIKE
    - RB_FLINK_CHECKPOINT_FAIL
    - RB_FLINK_BACKPRESSURE
    - RB_AURORA_LATENCY
    - RB_DUPLICATE_ADMISSION
  index_ref: TBD

# ========== 11) Change log ==========
changelog:
  - date_utc: TBD
    author: Codex
    change_summary: "initial draft"
    rationale: "derived from G2 7d profile"
```

---

Here’s a **validator checklist** for `g2_monitoring_baselines.v0.yaml`. It’s written so Codex can implement it as a simple script (or a CI check) and so you can manually review it if needed.

---

## Monitoring Baselines Validator Checklist (C.1)

### 1) File-level integrity

* [ ] File exists at the canonical path (per your evidence pack index).
* [ ] YAML parses successfully (no syntax errors).
* [ ] `monitoring_baselines_version` is set (e.g., `v0`).
* [ ] `status` is one of: `DRAFT`, `ACTIVE`, `FROZEN`.
* [ ] `owner` is set.
* [ ] `source_packs.g2_data_realism_pack_ref` is non-empty.

**Fail-closed rule:** If any of the above fails → **INVALID_BASELINES_FILE**.

---

### 2) Window binding

* [ ] `window_basis.window_start_ts_utc` set.
* [ ] `window_basis.window_end_ts_utc` set.
* [ ] `window_basis.as_of_time_utc` set.
* [ ] `window_basis.label_maturity_lag` set (even if “0d” initially, it must be explicit).

**Fail-closed rule:** Missing any → **BASELINES_WINDOW_UNBOUND**.

---

### 3) Global rules sanity

* [ ] `rules.distribution_required` contains at least `p95` and `p99`.
* [ ] `rules.missing_metric_policy == FAIL_CLOSED`.
* [ ] `rules.peak_slice_required == true`.
* [ ] `rules.injection_path_scope.via_IG.certifies` includes `end_to_end_hot_path`.
* [ ] `rules.injection_path_scope.via_MSK.does_not_certify` includes `IG_capacity`.

**Fail-closed rule:** Any mismatch → **BASELINES_GLOBAL_RULES_INVALID**.

---

### 4) Metric block completeness and schema

For each metric block with a `baseline` and `thresholds`:

**Baseline completeness**

* [ ] baseline has required percentiles: `p50`, `p95`, `p99` (or at least those listed in `rules.distribution_required`).
* [ ] baseline values are numeric and non-negative.

**Threshold completeness**

* [ ] thresholds exist.
* [ ] thresholds numeric fields are set (not `TBD`).
* [ ] any “min” thresholds are ≤ any “max” thresholds where both exist.
* [ ] guardband fields (if present) are numeric and > 0.

**Measurement surface completeness**

* [ ] `measurement_surface` exists for the metric.
* [ ] If the metric has a time boundary (latency), it has `start` and `end` fields.

**Fail-closed rule:** Any missing required field → **BASELINES_METRIC_INCOMPLETE**.

---

### 5) Required metric families present (minimum production-ready inventory)

These must exist in the YAML (not necessarily fully activated yet, but fields must be populated before `ACTIVE`):

**Runtime hot path**

* [ ] `runtime_hot_path.decision_latency_ms`
* [ ] `runtime_hot_path.error_rate`

**IG**

* [ ] `ingestion_gate.admit_rate_eps`
* [ ] `ingestion_gate.ig_latency_ms`
* [ ] `ingestion_gate.quarantine_rate`
* [ ] `ingestion_gate.ddb_throttle_events`

**Bus health**

* [ ] `bus_health.consumer_lag`
* [ ] `bus_health.producer_errors`

**Stream compute**

* [ ] `stream_compute.checkpoints.success_rate`
* [ ] `stream_compute.checkpoints.duration_ms`
* [ ] `stream_compute.backpressure`
* [ ] `stream_compute.restarts`

**Correctness**

* [ ] `data_correctness.duplicate_admission_rate`
* [ ] `data_correctness.out_of_order_rate`
* [ ] `data_correctness.hot_key_skew`

**State stores**

* [ ] `state_stores.aurora_query_latency_ms`
* [ ] `state_stores.aurora_conn_saturation`
* [ ] `state_stores.redis_latency_ms`
* [ ] `state_stores.redis_hit_rate`

**Auditability**

* [ ] `auditability.trace_coverage`
* [ ] `auditability.audit_response_time_seconds`
* [ ] `auditability.provenance_completeness`

**Cost**

* [ ] `cost.budget_envelope_usd`
* [ ] `cost.unit_cost_per_1m_events_usd`
* [ ] `cost.idle_burn_usd_per_day`
* [ ] `cost.residual_scan_count`

**Fail-closed rule:** Missing any family → **BASELINES_REQUIRED_FAMILY_MISSING**.

---

### 6) Alert validity (actionability requirement)

For every alert entry:

* [ ] `alert_id` is set and unique within the file.
* [ ] `severity` is one of: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.
* [ ] `owner` is set (non-empty).
* [ ] `runbook_ref` is set (non-empty).
* [ ] `stable_condition` is set (non-empty).

**Fail-closed rule:** Any missing field → **ALERT_NOT_ACTIONABLE**.

---

### 7) Runbook inventory integrity

* [ ] `runbooks.required` is non-empty.
* [ ] `runbooks.index_ref` is set (points to runbook index artifact).
* [ ] Every `runbook_ref` used by alerts exists in `runbooks.required` **or** is resolvable via `runbooks.index_ref`.

**Fail-closed rule:** Unresolved runbook reference → **RUNBOOK_REF_INVALID**.

---

### 8) Threshold sanity checks (basic logic guards)

* [ ] Latency thresholds: `p95_max <= p99_max` where both exist.
* [ ] Lag thresholds: `p95_max <= p99_max` where both exist.
* [ ] Error thresholds: `0 <= max <= 1` if represented as a fraction (or explicitly declare unit as percent elsewhere).
* [ ] Correlation coverage thresholds: `0 <= min <= 1` (or percent declared explicitly).
* [ ] Residual scan threshold must be `max: 0` (no leftovers).

**Fail-closed rule:** Any invalid bound → **THRESHOLD_SANITY_FAIL**.

---

### 9) Status gating rules (DRAFT vs ACTIVE vs FROZEN)

If `status == DRAFT`:

* Allowed to have `TBD` fields, but must still be syntactically valid.

If `status == ACTIVE`:

* [ ] No `TBD` values in required metric families.
* [ ] All required alerts are actionable (Section 6).
* [ ] Window binding is complete (Section 2).

If `status == FROZEN`:

* [ ] Same as ACTIVE.
* [ ] `changelog` contains an entry stating it is frozen for a specific mission run.

**Fail-closed rule:** Any ACTIVE/FROZEN violation → **BASELINES_NOT_ACTIVATABLE**.

---

### 10) Calibration traceability (prevents “observed becomes standard”)

For each major threshold (hot path latency, lag p99, checkpoint duration p95, unit cost):

* [ ] baseline values are present.
* [ ] thresholds are present.
* [ ] file includes either:

  * explicit guardband multipliers, or
  * explicit “baseline + margin” rule in `rules.threshold_policy_default`.

**Fail-closed rule:** If thresholds exist with no baseline context → **CALIBRATION_TRACE_MISSING**.

---

## Validator output format (recommended)

When implemented, the validator should output:

* `overall_valid: true/false`
* list of failed checks with:

  * `code` (one of the FAIL-closed codes above),
  * `path` (YAML path),
  * `message`
* `status_recommendation` (DRAFT/ACTIVE/FROZEN)

---
