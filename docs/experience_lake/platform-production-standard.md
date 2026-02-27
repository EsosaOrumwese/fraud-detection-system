# Fraud Platform Truth Anchor

## 1) Purpose and scope (Truth/Goal Anchor for prod_target end-state)

### 1.1 Purpose

This document defines the **end-state truth** (“Point X at the goal”) for a **production fraud ML platform** such that a seasoned Senior **ML Platform Engineer** and Senior **MLOps Engineer** could credibly say:
“I built and operate this platform in production,” and back that statement with **qualifiable and quantifiable evidence**.

It exists to:

* Act as the **north-star benchmark** for what “done” means at prod_target maturity.
* Provide a **stable reference** for evaluating your current Point X (today) against the goal (without drifting into tool lists or vague claims).
* Define what is **claimable** at the end-state: the platform capabilities, operating posture, and required evidence quality.

### 1.2 Intended audience

* **Primary:** you (as the platform builder and narrator of Point X)
* **Secondary:** any implementer/reviewer helping you build parts of the platform
* **Tertiary:** recruiters/hiring managers/technical interviewers (as the “what I can prove” reference)

### 1.3 Scope (what this truth anchor covers)

This truth anchor covers the **production-shaped platform responsibilities** and the **evidence standard** required to prove them, for an end-game fraud platform that includes:

* A **real-time decision path** (online scoring/decisioning) operated to **SLO-grade** expectations.
* A **streaming ingestion and processing backbone** where **retries, duplicates, and replays** are correctness-preserving (replay-safe).
* A **learning + promotion corridor** where datasets and models are **governed, reproducible, auditable, and reversible** (promotion + rollback is real, not theoretical).
* **Observability + auditability by default** (diagnosable operations, traceability from event → decision → model/data/code/config).
* **Cost-to-outcome discipline** (bounded spend, measurable unit economics, and controls that prevent uncontrolled burn).

It also covers the **tiered claim model** (Tier 0/1/2 supporting claims) and the corresponding **impact metrics + artifacts + drills** required to defend those claims.

### 1.4 Out of scope (what this is not)

This document is **not**:

* A detailed implementation spec, repo layout, or build plan.
* A vendor/tool justification document (it should remain valid as tooling evolves).
* A model research paper (it does not define feature meaning, fraud strategy, or business policy logic beyond what’s needed to operate safely).
* A UI/product requirements spec for case management (unless needed for operational evidence loops).

### 1.5 Assumptions and constraints (end-state framing)

* The end-state reflects a **regulated, high-stakes production posture** (financial-institution style): auditability, reversibility, and controlled change are non-negotiable.
* The platform is evaluated as a **running service**, not a one-off demo: incident posture, SLOs, operational routines, and evidence quality matter as much as functionality.
* The document is **goal-referenced**: it defines the destination truth; progress is evaluated as “what portion of that truth is already provable at current Point X.”

---

## 2) End-state Point X summary (prod_target mini-profile)

At the end goal, the fraud platform is a **production-operated ML delivery and real-time decision system** that allows multiple teams to ship and run fraud models **safely, repeatedly, and at scale** in a regulated environment. It provides a **paved road** for ML: standardized training and deployment workflows, versioned contracts, controlled promotion, and defaults that make the “safe path” the easiest path.

The **core online decision path** meets **SLO-grade reliability**: end-to-end latency and availability targets are defined, monitored, and defended with runbooks, on-call posture, and proven recovery actions (rollback and degrade modes). The **streaming ingestion and processing backbone** is correctness-preserving under real failure modes—**retries, duplicates, replays/backfills, ordering uncertainty, and schema evolution**—so the system stays consistent even when the world is messy.

The **learning and promotion corridor** is governed end-to-end: training datasets are time-correct (as-of and maturity controls), reproducible, and leakage-protected; training/evaluation produces auditable artifacts; and model promotion is **gated, traceable, and reversible** with proven rollback drills. Operations are **observable and diagnosable by default**: every decision can be traced from event → processing path → model/version → data/code/config provenance, and platform health can be localized quickly across data, model, pipeline, and infrastructure layers.

Finally, the platform is operated with **cost-to-outcome discipline**: spend is bounded, unit economics are measurable (cost per event, cost per retrain), and cost controls are built into the operating model (budget envelopes, idle-safe behavior, and capacity/right-sizing policies). A seasoned senior can credibly defend this end-state with a small set of impact metrics (delivery performance, SLO attainment, drift-to-mitigation, audit response time, and unit cost) and inspectable artifacts (promotion gates, dashboards/alerts, runbooks, lineage records, decision logs, rollback drills, and cost receipts).

---

## 3) Senior experience talk tracks (how the end-state is explained)

### 3.1 30–45 second talk track (executive summary)

“I own the ML platform that ships and operates fraud models in a regulated production environment. I built the paved road: standard training and deployment workflows, fail-closed promotion gates, and default observability so teams can release safely and repeatedly. The online decision path runs to SLO with fast rollback and degrade modes, and the streaming backbone is replay-safe under duplicates, retries, and reprocessing. Learning is governed end-to-end with time-correct datasets, reproducible training/eval, and reversible promotions with proven rollback drills. I measure impact with lead time, change failure rate, MTTR/rollback time, SLO attainment, drift-to-mitigation time, audit response time, and unit cost.”

### 3.2 ~2 minute talk track (expanded, interview-ready)

“In my current role I’m responsible for the shared ML platform that delivers and operates fraud decisioning in production under regulated constraints. The goal is to make ML delivery a repeatable capability rather than bespoke pipelines per team.

On the platform side, I built the paved road: standardized workflows and contracts for training, packaging, registration, promotion, and deployment. Releases are governed by a fail-closed promotion corridor—changes do not reach production unless required checks pass, and every release has a verified rollback path to last-known-good. This reduced risky one-off deployments and made releases auditable and repeatable across teams.

Operationally, we run the online decision path like a production service. We define SLIs/SLOs for availability, latency percentiles, and error budgets; we ship dashboards and actionable alerts; and we maintain runbooks for the top failure modes. Recovery is designed in, not improvised: rollback and degrade modes are exercised and time-bounded, so MTTR is measurable and improves over time.

A major focus is streaming correctness. The ingestion and processing backbone is built for real failure modes—duplicates, retries, replays/backfills, ordering uncertainty, and schema evolution—so correctness is preserved under stress. We track lag and checkpoint health, enforce idempotency boundaries, and have safe reprocessing procedures.

For learning, we govern the full lifecycle: datasets are time-correct with as-of and maturity controls, leakage protections are enforced, training and evaluation are reproducible with complete provenance, and promotion is gated and reversible with proven rollback drills. We can trace any production decision to the model/version and the data/code/config that produced it.

I communicate impact with outcomes: lead time, change failure rate, rollback time, MTTR, SLO attainment, drift detect-to-mitigate time, audit response time, adoption of the golden path, and cost per unit (event processed, retrain run), with artifacts that back each claim.”

### 3.3 Talk track rules (so it always lands “senior”)

* Lead with **ownership + outcomes**, not tools.
* Use the same structure every time: **X summary → 3 supporting claims → proof points**.
* For each supporting claim, be ready with: **2 metrics + 1 artifact + 1 failure-mode drill**.
* Keep internal environment names out of the talk track; speak in **production capabilities** and **operational evidence**.

---

## 4) Proof model (definitions, rules, and “claimability”)

### 4.1 Core definitions

* **Point X (end-state):** the destination mini-profile (Section 2). It is the *headline truth* about what the platform is and how it is operated in production.
* **Supporting claim:** a **bounded, testable statement** that makes Point X believable. Each supporting claim must map to a senior responsibility (platform or MLOps) and must be provable with evidence.
* **Proof points (impact metrics):** quantitative measures that demonstrate an outcome (speed, reliability, correctness, auditability, cost).
* **Artifacts:** inspectable evidence objects that demonstrate mechanisms and controls (gates, dashboards, runbooks, lineage, logs, policy records, drill reports).
* **Failure-mode drill:** a deliberate demonstration that proves behavior under stress (rollback works, replay is safe, schema drift blocks safely, degrade mode restores service).

---

### 4.2 What makes a supporting claim “good”

A strong supporting claim has four properties:

1. **Scope is explicit**
   Example: “Online decision path,” “promotion corridor,” “replay-safe ingestion,” “audit traceability.”

2. **Outcome is explicit**
   Example: “meets SLO,” “reversible,” “fail-closed,” “diagnosable,” “cost-bounded.”

3. **Failure-mode is acknowledged**
   Example: “under retries/replays,” “under lag spikes,” “under schema evolution,” “during partial outages.”

4. **Evidence expectations are implied**
   A claim that cannot naturally attach metrics + artifacts + drills is not a real claim yet.

---

### 4.3 Minimum evidence bundle rule (per supporting claim)

A supporting claim is **claimable** only if it has at least:

* **2 impact metrics** (outcome measures)
* **1 artifact** (inspectable control/mechanism evidence)
* **1 failure-mode drill** (proves behavior under stress)

**Recommended “senior-grade” evidence pack (stronger):**

* 3–5 impact metrics (includes at least one reliability metric and one delivery/correctness metric)
* 2–4 artifacts (e.g., a gate definition + dashboard + runbook + lineage record)
* 1–2 drills (one “recover/rollback” drill and one “correctness under replay/invalid input” drill)

---

### 4.4 Evidence quality rules (what counts, what doesn’t)

**Counts as proof**

* Metrics measured over a defined window (e.g., 7/30/90 days) with a stable definition.
* Artifacts that are **inspectable and reproducible** (dashboards, gate outputs, runbooks, registry records, lineage records).
* Drills that produce **time-bounded results** and a durable report (what was injected, what was observed, how recovery happened).

**Does not count as proof**

* “It ran once” without a repeatable runbook + metrics.
* Tool lists (“we use Kafka/K8s/MLflow”) without outcomes.
* Screenshots without traceable sources (unless paired with the underlying dashboard/query definition).
* Claims without explicit failure-mode handling (no rollback story, no replay story, no “what happens when X breaks”).

---

### 4.5 Claimability levels (how we grade progress toward the end-state)

Each supporting claim can be assigned a maturity level. This lets you truthfully present “where we are” while staying anchored to the end goal.

* **L0 — Not started:** no mechanism exists.
* **L1 — Implemented:** mechanism exists, but evidence bundle is incomplete.
* **L2 — Tested:** metrics exist + at least one artifact + basic drill performed in controlled conditions.
* **L3 — Pressure-tested:** demonstrated under realistic load/failure modes (scale/soak/replay/backfill) with stable metrics.
* **L4 — Production-proven:** sustained operation with SLO posture (error budgets), incident learning (postmortems), and audit-ready traceability.

**End-state requirement:** Tier 0 claims should be **L4**, Tier 1 claims should be **L3–L4**, Tier 2 claims should be **L2–L4** depending on scope.

---

### 4.6 Standard proof shapes (so evidence is comparable)

To avoid “random metrics,” each claim’s metrics should fit one of these shapes:

* **Delivery / change safety:** lead time, change failure rate, rollback time, gate pass rate
* **Reliability / SLO:** availability, p95/p99 latency, error budget burn, MTTR
* **Correctness under streaming:** dedupe rate, replay/backfill success, lag distributions, quarantine rates/reasons
* **Learning governance:** train/eval success rate, drift detect→mitigate time, promotion time, rollback drill time, reproducibility rate
* **Auditability:** provenance completeness, audit query response time, trace/correlation coverage
* **Cost-to-outcome:** cost per unit (event/prediction/retrain), idle burn, budget adherence

(Section 8 will define the platform’s “essential scorecard,” but this section defines the *proof grammar*.)

---

### 4.7 Drill rules (what a drill must specify)

A drill is valid only if it states:

* **Scenario:** what failed or what was simulated (e.g., dependency outage, replay window, schema break)
* **Expected behavior:** what should happen (fail-closed, degrade, rollback, quarantine, recover)
* **Observed outcome:** what actually happened (with timestamps)
* **Recovery bound:** time to restore-to-stable (and what “stable” means)
* **Integrity check:** proof that correctness held (no double-count, no state corruption, no silent regressions)
* **Artifact output:** a drill report that can be referenced later

---

### 4.8 Anti-gaming rules (to keep the truth anchor honest)

* **Every metric must have a definition** and a source of truth; no “vanity stats.”
* **Metrics must be paired with controls:** if you claim low change failure rate, show gates/rollbacks that make it possible.
* **Claims must survive failure modes:** if a claim collapses under replay or rollback, it’s not claimable yet.
* **Prefer trends over single points:** show improvement and stability, not one-off best-case numbers.

---

## 5) Tier 0 supporting claims (must-have senior claims)

Tier 0 claims are the **minimum set** that makes the end-state “seasoned senior in production” story believable. Each claim below is written in a fixed format so it can be defended the same way every time.

---

### T0.1 Governed release corridor with fast rollback (fail-closed promotion)

**Claim (1 sentence):**
All platform and model changes move through a **controlled promotion corridor** that is **fail-closed**, fully traceable, and **reversible** with a proven rollback path to last-known-good.

**Why it matters (risk / speed / compliance):**
Prevents unsafe changes from reaching production, makes releases auditable, reduces incident risk, and turns rollback into a routine safety action rather than a crisis.

**Required proof metrics (minimum):**

* **Lead time:** merge/approval → running in production (median + p90).
* **Change failure rate:** % releases that cause SLO breach, rollback, hotfix, or incident.
* **Rollback time:** detection → last-known-good restored (median + p90).
* **Gate pass rate:** % promotions passing required gates on first attempt.

**Required artifacts (inspectable):**

* Versioned **promotion policy** (what gates exist, what “fail-closed” means).
* Release **gate outputs** (eval report references, data contract checks, artifact integrity checks).
* **Promotion ledger** / registry stage transitions (who promoted what, when, why).
* **Rollback runbook** (step-by-step, with verification checks).
* Post-release **health snapshot** template (what must be captured after promotion).

**Required drill (must be demonstrated):**

* **Rollback drill:** promote a change (platform or model), trigger rollback criteria (manual or automatic), restore last-known-good, and verify:

  * traffic is served by the restored version
  * key SLIs return to normal
  * audit record captures promotion + rollback actions

**Acceptance thresholds (end-state expectation):**

* Promotions are impossible without gate evidence (no bypass path).
* Rollback is time-bounded and verified (bounded restore + integrity checks).
* Change safety trends improve over time (CFR and rollback frequency are explainable and decreasing).

---

### T0.2 SLO-grade online fraud decision path (production reliability posture)

**Claim (1 sentence):**
The end-to-end online decision path (ingress → stream/feature joins → scoring/decision → action/log) operates to defined **SLIs/SLOs**, with proven **degrade** and **recovery** behavior under failure.

**Why it matters:**
Fraud decisioning is high-stakes; reliability failures cause direct financial loss, customer friction, and regulatory risk. The platform must behave predictably under real-world stress.

**Required proof metrics (minimum):**

* **End-to-end latency:** p95 and p99 for decision completion (event received → decision recorded).
* **Availability / error budget:** monthly availability and error budget burn rate for the decision path.
* **Error rate:** timeouts + 5xx/failed-decision rate (overall + by component boundary).
* **MTTR:** restore-to-stable time for incidents impacting the decision path.

**Required artifacts:**

* Published **SLI/SLO spec** (including what “stable” means).
* Dashboards for latency, availability, errors, saturation, and backlog/lag.
* Alert rules tied to SLOs (actionable, owned, severity-tagged).
* **Degrade ladder policy** (what gets degraded, when, and how correctness is preserved).
* Incident runbooks: “latency spike,” “dependency down,” “lag spike,” “feature store degraded,” “model service degraded.”

**Required drill:**

* **Degrade + recover drill:** simulate a dependency failure (feature retrieval, stream lag, state store pressure) and demonstrate:

  * detection (alerts fire)
  * controlled degrade mode activation (bounded behavior, documented posture)
  * restore-to-stable (recovery actions, verified)
  * post-incident evidence (timeline, root cause category, prevention actions)

**Acceptance thresholds:**

* SLOs exist and are enforced by operating decisions (not just dashboards).
* Degrade mode is a first-class, tested operating capability.
* Recovery is measurable and repeatable (bounded MTTR with runbook execution).

---

### T0.3 Replay-safe streaming correctness (retries/duplicates/replays don’t corrupt truth)

**Claim (1 sentence):**
The platform preserves correctness under streaming failure modes—**retries, duplicates, replays/backfills, ordering uncertainty, and schema evolution**—so state and decisions are not double-counted or corrupted.

**Why it matters:**
Fraud systems must remain correct when the world is messy: network retries, consumer restarts, reprocessing windows, and producer changes are normal, not exceptional.

**Required proof metrics (minimum):**

* **Dedupe effectiveness:** dedupe hit rate and duplicate-admission rate (per million).
* **Replay/backfill success:** % replays completing with integrity checks passing + time-to-complete.
* **Lag health:** consumer lag p95/p99 and breach frequency.
* **Quarantine rate:** % quarantined events + top reasons and trend.

**Required artifacts:**

* **Idempotency contract** (idempotency keys, TTL rules, collision handling).
* **Offset/continuity policy** (how event positions are tracked and validated).
* Schema evolution policy (compatibility guarantees, validation, quarantine rules).
* Reprocessing playbook: “replay window X,” “backfill,” “rebuild projection safely.”
* Integrity check definitions: what proves “no double-count” and “state is consistent.”

**Required drill:**

* **Replay integrity drill:** replay a known window and prove:

  * decision counts, aggregates, and derived stores match expected invariants
  * no duplicate side effects (no double case creation, no double ledger writes)
  * audit trail shows replay provenance and results

**Acceptance thresholds:**

* Replays/backfills are routine and safe (documented and time-bounded).
* Schema drift never silently degrades: it is blocked, quarantined, or safely migrated by policy.
* Correctness is validated by invariants, not by “looks fine.”

---

### T0.4 Default observability + diagnosability (fast detection and localization)

**Claim (1 sentence):**
The platform is observable by default and failures are diagnosable: it can quickly distinguish whether an issue is **data**, **model**, **pipeline**, or **infrastructure**, and guide operators to mitigation.

**Why it matters:**
In production, “we have logs” is not enough. Senior-level operation requires fast detection, low noise, and rapid localization to reduce MTTR and prevent silent failures.

**Required proof metrics (minimum):**

* **Time to detect (TTD)** and **time to diagnose (TTDiag)** (median + p90).
* **Alert quality:** actionable alert precision (% alerts that require action).
* **MTTR** trend (should improve as observability matures).
* **Correlation coverage:** % events with end-to-end correlation across components.

**Required artifacts:**

* Standard correlation/trace context: event IDs propagated across ingress → stream → decision → action → logs.
* Dashboards that isolate failure domains (lag vs latency vs dependency vs data anomalies).
* Runbooks linked directly from alerts (one-click “what to do now”).
* Postmortem template that forces “control improvements” (gates, alerts, runbooks, defaults).

**Required drill:**

* **Localization drill:** introduce one controlled failure (lag spike, schema change, dependency latency) and show:

  * alert fires with correct severity
  * dashboard isolates root cause domain quickly
  * runbook produces a bounded mitigation outcome

**Acceptance thresholds:**

* Operational truth is “one hop away”: alerts → dashboard → runbook → mitigation.
* Noise is managed; alerts are owned and tuned.
* Diagnosis does not require tribal knowledge.

---

### T0.5 Audit-grade provenance + decision traceability (answer “what happened and why” fast)

**Claim (1 sentence):**
Every production decision is traceable end-to-end: event → processing path → decision → model/version → data/code/config provenance, enabling fast audits and reliable “what changed?” answers.

**Why it matters:**
In regulated environments, you must prove what ran, why it ran, and who approved it—quickly and reliably—without reconstruction guesswork.

**Required proof metrics (minimum):**

* **Provenance completeness:** % decisions/models with complete traceability fields present.
* **Audit query response time:** time to answer a standard audit question using platform records.
* **“What changed?” latency:** time to identify the change responsible for a regression (median/p90).

**Required artifacts:**

* Append-only **decision log** with model-version headers and key context.
* **Lineage/provenance store**: links training runs, datasets, configs, model artifacts, deployments.
* Access control + retention policy for audit records.
* Standard audit queries/examples (pre-written, reproducible).

**Required drill:**

* **Audit drill:** pick a production decision and demonstrate you can produce:

  * the exact model/version used
  * the deployment/promotion record
  * the training run lineage (code/data/config)
  * the justification/approval trail
    within the bounded audit response time target.

**Acceptance thresholds:**

* Audit answers come from first-class records, not manual reconstruction.
* Provenance is complete for production decisions/models as a default property.
* “What changed?” is answerable quickly and reliably.

---

### T0.6 Cost-to-outcome control (bounded spend with unit economics)

**Claim (1 sentence):**
The platform is cost-governed: spend is bounded, measurable, and tied to outcomes (unit economics), with controls that prevent runaway cost and idle burn.

**Why it matters:**
Senior ownership includes stewardship. Production platforms must be economically sustainable, not just technically impressive.

**Required proof metrics (minimum):**

* **Unit cost:** cost per 1M events processed (online/stream) and cost per retrain (learning lane).
* **Idle burn rate:** cost incurred while “not actively running.”
* **Budget adherence:** envelope vs actual per lane/run/release.
* **Efficiency signals:** utilization and right-sizing improvements over time.

**Required artifacts:**

* Budget envelopes per run/release and **cost-to-outcome receipts**.
* Idle-safe controls (auto teardown, minimum-on footprint, scheduled shutdown).
* Autoscaling/right-sizing policies tied to SLO posture.
* FinOps dashboard showing cost trends per lane (ingest, stream, decision, learning).

**Required drill:**

* **Cost guardrail drill:** demonstrate that exceeding budget thresholds triggers action (alert + throttle/stop/degrade/teardown policy), and that the platform returns to an idle-safe state without manual heroics.

**Acceptance thresholds:**

* Spend is visible, attributable, and controllable at lane level.
* Unit costs are measured and used in decisions (not retroactive accounting).
* Idle burn is minimized and enforced by automation.

---

## 6) Tier 1 supporting claims (differentiators)

Tier 1 claims are the **high-signal differentiators** that make the end-state read like “seasoned senior” rather than “good platform.” They are still operational and evidence-backed, but they go beyond the minimum Tier 0 safety bar.

---

### T1.1 Non-leaky, time-correct learning inputs (as-of + maturity + leakage enforcement)

**Claim (1 sentence):**
Training datasets are **time-correct and leakage-protected** through explicit **as-of** rules and **label maturity** cutoffs, so learning never trains on information that would not exist at inference time.

**Why it matters:**
Leakage is one of the most common sources of “great offline results, bad production behavior.” In fraud, leakage can create false confidence and severe real-world harm.

**Required proof metrics (minimum):**

* **Leakage violation rate:** % runs blocked due to leakage checks (and the trend as controls mature).
* **As-of compliance:** % training rows meeting feature_asof rules (violations per million).
* **Label maturity compliance:** % labels meeting maturity cutoff; label lateness distribution.
* **Reproducibility rate:** rerun consistency within tolerance for key datasets.

**Required artifacts:**

* Formal **as-of policy** and **label maturity policy** (definitions + cutoffs).
* Dataset manifests including time windows, as-of constraints, label maturity bounds.
* Leakage check report template and storage of pass/fail outcomes.
* “Forbidden truth surfaces” list (what must never appear in training features).

**Required drill:**

* **Leakage attempt drill:** intentionally construct a violating training input (future feature/label) and prove it **fails closed**, producing an auditable report showing which rule was violated.

**Acceptance thresholds:**

* Leakage controls are enforced automatically and can’t be bypassed in production workflows.
* Datasets are reproducible and time-correct by construction, not by manual discipline.

---

### T1.2 Drift-to-action loop (detect → decide → mitigate, within policy)

**Claim (1 sentence):**
Drift and degradation do not “sit on dashboards”—they trigger a governed action path (rollback, retrain, degrade) within defined time bounds.

**Why it matters:**
Monitoring without response is theatre. Senior MLOps is measured by how quickly and safely the platform reacts when model behavior shifts.

**Required proof metrics (minimum):**

* **Drift detection-to-mitigation time:** detect → action completed (median + p90).
* **Mitigation effectiveness:** post-action stability window (time until metrics return to acceptable range).
* **Rollback/retrain success rate:** % mitigations that complete without incident.
* **Silent regression rate:** % degradations detected by users vs monitoring (should approach zero).

**Required artifacts:**

* Drift monitors tied to a **policy**: thresholds, severity, decision rules.
* Playbooks for each response: rollback, retrain, degrade, quarantine.
* Decision records: why action was taken, what was chosen, who approved (if required).
* Post-mitigation verification checklist (what “restored” means).

**Required drill:**

* **Simulated drift drill:** introduce a controlled distribution shift and demonstrate: detect → classify severity → execute mitigation → verify recovery, all within policy bounds.

**Acceptance thresholds:**

* Drift triggers are actionable and owned; mitigation is routine, not hero work.
* The platform can demonstrate “detect → mitigate” with durable evidence.

---

### T1.3 Champion/challenger evaluation and controlled rollout (safe improvement delivery)

**Claim (1 sentence):**
Model improvements are delivered through a controlled evaluation and rollout mechanism (baseline comparisons + canary/shadow), making new models provably safer before full adoption.

**Why it matters:**
Senior teams do not “swap models.” They compare, gate, and roll out gradually, with rollback criteria ready.

**Required proof metrics (minimum):**

* **Candidate win rate:** % challengers beating baseline on acceptance metrics.
* **Canary/shadow health:** SLO adherence during rollout; rollback trigger rate.
* **Model regression rate:** % promotions reverted due to performance regressions.
* **Promotion cycle time:** candidate ready → safely promoted (median/p90).

**Required artifacts:**

* Standard evaluation report bundle (metrics, slices, stability, leakage checks).
* Controlled rollout policy: canary/shadow configuration + guardrails.
* Rollback criteria tied to monitored signals during rollout.
* Promotion records linking evaluation artifacts to the deployed version.

**Required drill:**

* **Controlled rollout drill:** run a challenger in shadow/canary, demonstrate automated checks and rollback triggers, and show evidence that full rollout is conditional on stability.

**Acceptance thresholds:**

* Promotions are evidence-driven; rollback criteria are defined and exercised.
* The rollout mechanism is reusable across models and teams.

---

### T1.4 Training-serving consistency enforcement (feature correctness, skew detection, safe evolution)

**Claim (1 sentence):**
The platform prevents silent training-serving skew through feature contracts, freshness controls, and skew detection, making feature evolution safe.

**Why it matters:**
Many production ML failures are not “bad models” but mismatched features, staleness, or silent schema/semantic drift.

**Required proof metrics (minimum):**

* **Skew incident rate:** skew violations per release/window.
* **Feature freshness SLI:** age of online features at inference time; TTL breach rate.
* **Feature retrieval latency:** p95/p99 for feature fetch path.
* **Contract compliance:** % feature producers meeting contract consistently.

**Required artifacts:**

* Feature contract definitions (types, semantics where enforceable, versioning rules).
* Freshness/TTL policies and enforcement mechanism.
* Skew detection checks integrated into release/promotion gates.
* Safe migration/deprecation process for feature changes.

**Required drill:**

* **Skew injection drill:** introduce a controlled skew or breaking feature change and demonstrate detection + block/quarantine/degrade path, with clear audit evidence.

**Acceptance thresholds:**

* Feature evolution is governed and safe; skew is detected and actionable.
* Serving correctness does not depend on tribal knowledge.

---

### T1.5 Reliability hardening under failure-mode test suites (beyond “it recovers once”)

**Claim (1 sentence):**
The platform is continuously hardened using failure-mode test suites (scale/soak/replay/outage scenarios) that produce measurable reliability improvements over time.

**Why it matters:**
The difference between “works” and “production-grade” is the ability to survive stress repeatedly and improve after incidents.

**Required proof metrics (minimum):**

* **Restart-to-stable time** under controlled component failures.
* **Checkpoint success rate** (for streaming) and recovery time after restarts.
* **Incident recurrence rate** (repeat incidents should decline).
* **Error budget burn** impact of releases (should improve with maturity).

**Required artifacts:**

* Failure-mode test catalog (what scenarios exist, how they run).
* Reports for load/soak/replay and outage drills.
* Postmortems and tracked remediation items (with closure evidence).
* SLO compliance trend dashboards.

**Required drill:**

* **Repeatable outage drill:** intentionally break a key dependency (stream processor restart, state store latency) and demonstrate predictable recovery, integrity verification, and improved runbook/tooling over time.

**Acceptance thresholds:**

* Failure-mode tests are routine and repeatable, not one-off demonstrations.
* Reliability posture improves measurably (MTTR, recurrence, SLO attainment).

---

## 7) Tier 2 supporting claims (platform-as-product maturity)

Tier 2 claims represent the “very senior” polish that shows the platform is not only safe and reliable, but also **adopted**, **supportable**, and **sustainable** across teams and over time. These claims are often the difference between “strong platform” and “platform organization maturity.”

---

### T2.1 Golden-path adoption and self-serve delivery (platform as a product)

**Claim (1 sentence):**
The platform is a true internal product: teams can ship models through a **self-serve golden path** without bespoke platform intervention, while maintaining governance and reliability.

**Why it matters:**
A senior ML platform engineer is judged not just on building capabilities, but on making them **usable and adopted**. Adoption reduces fragmentation, improves reliability, and accelerates delivery.

**Required proof metrics (minimum):**

* **Golden-path adoption rate:** % model deployments using standard templates/SDK workflows.
* **Time-to-first-production:** median time for a new team/model to reach production.
* **Self-serve rate:** % releases completed without manual platform team involvement.
* **Support load trend:** ticket volume and time-to-resolution (should stabilize or decline as DX improves).

**Required artifacts:**

* Versioned templates/SDK, onboarding docs, “first production model” guide.
* Standard service/pipeline scaffolds with built-in observability and governance.
* Deprecation/migration policy (versioning rules, compatibility guarantees).
* Support model: escalation routes, office hours, ticket triage playbook.

**Required drill:**

* **Onboarding drill:** a “new team” follows documentation to ship a model to production via golden path, with the same gates and observability, within the target time-to-first-prod.

**Acceptance thresholds:**

* Most production releases use the golden path; bespoke flows are exceptions.
* Onboarding is predictable and measurable; docs and templates are maintained like product assets.

---

### T2.2 Security and compliance are baked in (policy by default, least privilege)

**Claim (1 sentence):**
Security and compliance controls are default platform behavior: least privilege, secure secrets, artifact integrity, and auditable approvals are enforced without slowing delivery into manual gatekeeping.

**Why it matters:**
In regulated production, senior engineers are expected to build systems that are secure and auditable by design, not by after-the-fact process.

**Required proof metrics (minimum):**

* **Signed/verified artifact coverage:** % model artifacts/images with integrity assurance.
* **Vulnerability remediation SLA adherence:** % critical issues fixed within policy window.
* **Access audit completeness:** % sensitive accesses logged and attributable.
* **Exception rate trend:** frequency of security/compliance waivers (should be bounded and decreasing).

**Required artifacts:**

* IAM policies/roles showing least privilege and separation of duties.
* Secrets management policy and evidence of non-leakage practices.
* Artifact integrity controls (scan/sign/attest as applicable) integrated into CI/CD.
* Approval/exception workflow with durable audit records.

**Required drill:**

* **Access control drill:** attempt an unauthorized access or policy violation and demonstrate it is blocked, logged, and attributable; prove a compliant approval path exists for legitimate exceptions.

**Acceptance thresholds:**

* Security posture is measurable and enforced via automation.
* Exceptions exist but are controlled, auditable, and rare.

---

### T2.3 Case/labels operational maturity (human loop is production-reliable)

**Claim (1 sentence):**
The platform’s human loop (case management and labels) is reliable enough to support learning and audits: cases are created, tracked, reconciled, and labels mature predictably.

**Why it matters:**
Fraud systems often depend on human review and delayed truth. If the label pipeline is unreliable, learning becomes noisy and governance becomes weak.

**Required proof metrics (minimum):**

* **Case backlog SLA:** time-to-first-action / time-to-close distributions.
* **Label latency distribution:** event → label available (median/p90) and maturity rate.
* **Reconciliation correctness:** % cases/labels correctly linked to originating events/decisions.
* **Manual review rate:** cases per 1k transactions/events (trend and stability).

**Required artifacts:**

* Case creation policy and decision-to-case routing rules.
* Label capture and maturity policies (including quality checks).
* Reconciliation reports that show linkage integrity.
* Audit queries tying decisions → cases → labels.

**Required drill:**

* **Truth surfacing drill:** pick a set of production decisions and demonstrate the full chain: decision → case → label → inclusion/exclusion in training under maturity rules.

**Acceptance thresholds:**

* Labels are usable and reliable; learning inputs remain time-correct and auditable.
* Human loop is treated as an operational system, not a manual afterthought.

---

### T2.4 Business outcome proxies tied to platform controls (fraud-specific, platform-enabled)

**Claim (1 sentence):**
Platform controls demonstrably improve fraud operations by affecting measurable outcome proxies (reduced friction, stable capture performance, controlled review load) without harming reliability.

**Why it matters:**
Senior engineers in production environments often need to show that platform improvements translate into safer, better business outcomes—not just cleaner architecture.

**Required proof metrics (minimum):**

* **False positive proxy:** decline/step-up rate, customer friction indicators (trend).
* **Review load:** manual review rate and backlog stability (trend).
* **Capture proxy:** detection/capture indicators or loss-prevention proxies (where measurable).
* **Latency impact:** user-facing timeouts/fallback rates (should not regress).

**Required artifacts:**

* KPI dashboards connecting platform releases to outcome proxy shifts.
* Release notes tying changes to expected outcome effects and guardrails.
* Experimentation/rollout records for controlled changes (where applicable).

**Required drill:**

* **Outcome verification drill:** after a controlled rollout, demonstrate measurement of outcome proxies with guardrails (no SLO regressions, rollback criteria present).

**Acceptance thresholds:**

* Outcome proxies are monitored and tied to release decisions.
* Platform changes are evaluated with both reliability and business impact in view.

---

## 8) Essential impact metrics scorecard (end-state operating metrics)

This section defines the **minimum scorecard** the platform must be able to report continuously at the prod_target end-state. It is organized around the five essential proof areas we agreed:

1. core online path is SLO-grade
2. streaming/replay semantics are correct
3. learning + promotion corridor is governed + reversible
4. operations are observable + auditable
5. spend is bounded and justified

Each metric below is given with: **definition**, **typical target form**, and **source-of-truth type**. (Exact numeric targets can be pinned later once the platform’s scale assumptions are set.)

---

### 8.1 Delivery performance and change safety (DORA + ML-aware gates)

These metrics prove the platform enables safe, repeatable change.

1. **Lead time for change (LT)**

* **Definition:** time from approved merge (or change approval) → running in production.
* **Target form:** median and p90 (e.g., hours/days).
* **Source of truth:** CI/CD pipeline + promotion records.

2. **Deployment frequency (DF)**

* **Definition:** number of successful promotions/releases per week (platform + model bundle).
* **Target form:** releases/week; track trend.
* **Source of truth:** promotion ledger/registry stage transitions.

3. **Change failure rate (CFR)**

* **Definition:** % releases that cause rollback, hotfix, incident, or SLO breach within a defined window.
* **Target form:** percent, monthly.
* **Source of truth:** incident logs + rollback records + SLO breach events.

4. **MTTR (restore-to-stable)**

* **Definition:** time from incident start → service stable within SLO bounds.
* **Target form:** median/p90.
* **Source of truth:** incident timeline + SLO recovery timestamp.

5. **Rollback time**

* **Definition:** detect regression → last-known-good restored and verified.
* **Target form:** median/p90, plus drill results.
* **Source of truth:** deployment records + verification checks.

6. **Gate pass rate**

* **Definition:** % promotions passing mandatory gates on first attempt.
* **Target form:** percent + top failure reasons.
* **Source of truth:** gate outputs and block registers.

---

### 8.2 Core online fraud decision path (SLO-grade)

These metrics prove the online path is production-operated and reliable.

1. **End-to-end decision latency (p95/p99)**

* **Definition:** time from ingress acceptance → decision recorded (and action emitted where applicable).
* **Target form:** p95/p99 thresholds; breach count.
* **Source of truth:** distributed tracing or correlated timestamps across boundary logs.

2. **Availability / error budget burn**

* **Definition:** percent of time the decision path meets availability; rate of error budget consumption.
* **Target form:** monthly SLO attainment and burn rate.
* **Source of truth:** SLO monitoring service.

3. **Error rate and timeout rate**

* **Definition:** % of requests/events resulting in errors/timeouts in the decision path (by component boundary).
* **Target form:** percent; alert thresholds.
* **Source of truth:** service metrics, gateway metrics, decision-service metrics.

4. **Degrade mode activation rate**

* **Definition:** frequency and duration of degraded operation; % traffic processed under degrade posture.
* **Target form:** time-in-degrade, occurrences/month.
* **Source of truth:** decision fabric logs + degrade posture events.

5. **Recovery bound (RTO proxy)**

* **Definition:** restore-to-stable time following defined failure classes (dependency outage, lag spike).
* **Target form:** bounded time by failure type; drill results.
* **Source of truth:** drill reports + incident timelines.

---

### 8.3 Streaming correctness and replay safety

These metrics prove “real-world messiness” does not break correctness.

1. **Consumer lag (p95/p99)**

* **Definition:** lag distribution for core stream consumers/processors.
* **Target form:** p95/p99 thresholds; breach frequency.
* **Source of truth:** streaming system metrics (consumer lag dashboards).

2. **Checkpoint success rate (stream processing)**

* **Definition:** % successful checkpoints (and checkpoint duration distribution).
* **Target form:** percent success; p95 duration threshold.
* **Source of truth:** stream processor metrics.

3. **Dedupe hit rate / duplicate-admission rate**

* **Definition:** % events suppressed by idempotency; % duplicates that slip through.
* **Target form:** per million; trend.
* **Source of truth:** ingress/idempotency store metrics + decision ledger integrity checks.

4. **Replay/backfill success rate + time-to-complete**

* **Definition:** % replays/backfills that complete with integrity checks passing; elapsed time.
* **Target form:** percent + median/p90 duration.
* **Source of truth:** replay job logs + integrity check reports.

5. **Quarantine rate + top reasons**

* **Definition:** % events quarantined; breakdown of quarantine reasons (schema, contract, validation, corruption).
* **Target form:** percent + reason distribution trend.
* **Source of truth:** quarantine store + validation gate output.

6. **Integrity invariants pass rate**

* **Definition:** % runs/windows where invariants (no double count, consistent aggregates, consistent side effects) hold.
* **Target form:** percent, tracked per lane.
* **Source of truth:** invariant check suite outputs.

---

### 8.4 Learning and promotion corridor (governed, reproducible, reversible)

These metrics prove senior MLOps loop closure.

1. **Training pipeline success rate**

* **Definition:** % training pipelines completing successfully within SLA windows.
* **Target form:** percent + top failure reasons.
* **Source of truth:** orchestrator run metrics.

2. **Time-to-train/evaluate (median/p90)**

* **Definition:** end-to-end time from dataset ready → evaluation report produced.
* **Target form:** duration thresholds.
* **Source of truth:** pipeline runtime metrics.

3. **Leakage violation rate**

* **Definition:** % training attempts blocked due to leakage/as-of/maturity rule violations.
* **Target form:** percent; should decrease as controls and workflows mature.
* **Source of truth:** leakage guardrail reports.

4. **Reproducibility rate**

* **Definition:** % reruns reproducing key evaluation results within tolerance.
* **Target form:** percent; tolerance defined in policy.
* **Source of truth:** experiment tracking + reproducibility harness.

5. **Promotion cycle time**

* **Definition:** candidate ready → safely promoted to production (including approvals).
* **Target form:** median/p90.
* **Source of truth:** registry + promotion ledger timestamps.

6. **Rollback drill time (model promotions)**

* **Definition:** time to revert a model promotion and restore stable operation.
* **Target form:** bounded time + drill report.
* **Source of truth:** drill reports + deployment records.

7. **Drift detect → mitigate time**

* **Definition:** time from drift detection → mitigation completed (rollback/retrain/degrade).
* **Target form:** median/p90 + policy thresholds.
* **Source of truth:** monitoring events + mitigation action logs.

8. **Non-regression pass rate**

* **Definition:** % promotions/releases passing regression suites across platform and learning lanes.
* **Target form:** percent.
* **Source of truth:** CI/CD + validation suite outputs.

---

### 8.5 Observability, auditability, and diagnosability

These metrics prove the platform is operable and regulated-ready.

1. **Time to detect (TTD)**

* **Definition:** incident start → alert triggered.
* **Target form:** median/p90; reduction over time.
* **Source of truth:** incident events + alert timestamps.

2. **Time to diagnose (TTDiag)**

* **Definition:** alert → root cause domain identified (data/model/pipeline/infra).
* **Target form:** median/p90.
* **Source of truth:** incident records + postmortem logs.

3. **Correlation/trace coverage**

* **Definition:** % events with end-to-end correlation across ingress → processing → decision → action.
* **Target form:** percent.
* **Source of truth:** tracing context propagation metrics.

4. **Alert precision (actionability)**

* **Definition:** % alerts that are actionable vs noise.
* **Target form:** percent + tuning trend.
* **Source of truth:** alert review logs.

5. **Provenance completeness**

* **Definition:** % production decisions/models with complete lineage fields populated.
* **Target form:** percent (target near 100% for regulated posture).
* **Source of truth:** provenance store audits.

6. **Audit query response time**

* **Definition:** time to answer “what ran, with what model/data/config, and why” using platform records.
* **Target form:** bounded minutes, measured.
* **Source of truth:** audit drill reports.

---

### 8.6 Cost-to-outcome and FinOps controls

These metrics prove senior stewardship and sustainability.

1. **Cost per unit (online)**

* **Definition:** cost per 1M events processed (or per 1k predictions), end-to-end.
* **Target form:** £/unit + trend.
* **Source of truth:** cost allocation + workload counters.

2. **Cost per retrain**

* **Definition:** total cost of a full training/evaluation cycle.
* **Target form:** £/run + variability.
* **Source of truth:** job cost attribution + pipeline runs.

3. **Idle burn rate**

* **Definition:** cost incurred when platform is not actively running (baseline footprint).
* **Target form:** £/day; minimize.
* **Source of truth:** cloud billing + resource inventory.

4. **Budget adherence**

* **Definition:** % runs/releases staying within pre-declared budget envelopes.
* **Target form:** percent + exception trend.
* **Source of truth:** budget envelopes + receipts.

5. **Utilization efficiency**

* **Definition:** CPU/GPU utilization and waste metrics; scale-to-load behavior.
* **Target form:** improved utilization without SLO regression.
* **Source of truth:** infra metrics + cost reports.

---

### 8.7 Scorecard governance rules (to keep metrics credible)

* Every metric must have a stable definition and source-of-truth.
* Report median + p90 (or p95) wherever distributions matter.
* Prefer trends (7/30/90 day) over single best-case values.
* Tie metrics to actions: alerts, gates, rollbacks, drills, postmortems.
* Any metric used in claims must be reproducible and explainable.

---

## 9) Operating rhythm at end-state (what the senior focuses on day-to-day)

This section defines the **operating posture** of the platform at the prod_target end-state. It describes what a seasoned senior actually *does* to keep the platform reliable, safe, auditable, and cost-controlled. The focus is not “checking dashboards,” but **running a system with SLOs, gates, drills, and continuous hardening**.

---

### 9.1 Daily focus (health, risk, and fast detection)

A senior’s daily rhythm is centered around **SLO posture**, **change safety**, and **leading indicators** of failure.

**A) Online path posture**

* Review **SLO dashboards** for the online decision path:

  * latency p95/p99, error rate, availability, error budget burn
* Check for **degrade mode usage**:

  * time-in-degrade, posture flips, and whether degrade is behaving as designed
* Validate that **alerting is actionable**:

  * top alerts, false positives, and missing coverage

**B) Streaming posture**

* Review **lag distributions** (p95/p99) and checkpoint health:

  * consumer lag breaches, checkpoint failures, restart frequency
* Scan **quarantine reasons**:

  * top quarantine causes, spikes, repeated producer contract violations
* Check **dedupe/idempotency effectiveness**:

  * duplicate-admission anomalies, idempotency store health

**C) Cost posture**

* Review **unit cost trend** (cost per unit, cost per retrain) and **idle burn**
* Verify no runaway footprint:

  * unexpected resources, autoscaling anomalies, baseline cost drift

**D) “Today’s risk register”**

* Maintain a small daily list:

  * current risks (e.g., new producer schema change, backlog growth, upcoming release)
  * planned mitigations (gates, canary, freeze, additional monitors)

---

### 9.2 Per-release focus (preflight → rollout → verification → closure)

Every release (platform or model) is treated as a controlled operation.

**A) Preflight**

* Confirm required **gates and evidence** are present:

  * data contracts, evaluation thresholds, artifact integrity, approval traces
* Confirm **rollback is ready**:

  * last-known-good identified, rollback procedure tested, verification checks ready

**B) Rollout**

* Execute controlled rollout:

  * shadow/canary where applicable
  * guardrails for SLO breaches and correctness anomalies
* Monitor leading indicators during rollout:

  * latency, errors, lag, dedupe anomalies, quarantine spikes

**C) Post-release verification**

* Capture post-release health snapshot:

  * SLO status, lag status, key correctness invariants, cost delta
* Decide explicit closure:

  * “release accepted” vs “release reverted” (with recorded rationale)

**D) Closure record**

* Every release produces a closure record containing:

  * what changed, what gates passed, rollout method, observed outcomes, and any follow-ups

---

### 9.3 Weekly focus (stability, improvement, and adoption)

Weekly rhythm is about improving the system, not just keeping it alive.

**A) Reliability and incident trend review**

* Review incident rate, MTTR, and error budget burn trends
* Identify recurring failure classes:

  * lag spikes, schema drift, dependency timeouts, data quality regressions
* Convert recurring issues into:

  * new gates, better defaults, improved alerts/runbooks, or infrastructure hardening

**B) Change safety review**

* Track change failure rate and rollback frequency
* Review top gate failure reasons:

  * which checks fail most often, why, and how to reduce friction without reducing safety

**C) Learning and promotion health**

* Review drift events and actions taken:

  * detect→mitigate time, outcome effectiveness
* Review training pipeline success and cycle times:

  * bottlenecks, instability causes, reproducibility issues

**D) Platform-as-product signals (if applicable)**

* Golden-path adoption rate
* Onboarding experience (time-to-first-production)
* Support load trend and top issues (reduce recurring friction)

---

### 9.4 Monthly/quarterly focus (governance and strategic hardening)

This cadence aligns with regulated production realities.

**A) SLO reset and error budget governance**

* Evaluate if SLOs reflect reality and risk appetite
* Update alert thresholds and operational policies accordingly

**B) Audit readiness checks**

* Run scheduled audit drills:

  * “trace decision X to model/data/code/config”
  * verify retention, access controls, and completeness
* Track provenance completeness and reduce missing fields to near-zero

**C) Disaster recovery and resilience drills**

* Repeat failure-mode drills:

  * component restarts, partial outages, replay/backfill integrity, rollback drills
* Record drill results and remediation actions

**D) Cost governance**

* Review unit economics and resource posture:

  * right-sizing opportunities
  * scaling strategy updates
  * idle burn reduction goals

---

### 9.5 Incident posture (how a senior runs incidents)

**A) Triage pattern**

* Identify the failure domain quickly:

  * infra vs stream lag vs data contract break vs model behavior shift
* Stabilize service first:

  * rollback, degrade, throttle, quarantine, pause promotion/retraining

**B) Restore-to-stable**

* Use runbooks to return within SLO bounds
* Verify integrity:

  * no double-count, no corrupted state, correctness invariants pass

**C) Postmortem discipline**
Every incident produces:

* a timeline, root cause classification, customer impact
* a set of **systemic fixes** (new gate, better alert, safer default, or architectural hardening)
* a measurable target (reduce recurrence, improve MTTR, lower burn rate)

---

### 9.6 “Senior focus” summary (what they’re really doing)

At end-state, a seasoned senior’s rhythm is essentially:

* **Protect the SLOs** (online path, streaming health)
* **Protect correctness under messiness** (replay-safe semantics, quarantines, invariants)
* **Protect the corridor** (fail-closed promotion + rollback readiness)
* **Protect auditability** (traceability is always complete and fast)
* **Protect cost** (bounded, attributable, and optimized without reliability regressions)

---

## 10) Boundaries and non-goals (prevent narrative drift)

This section exists to keep the truth anchor **clean, defensible, and non-confusing**. In production organizations, senior credibility often depends on being precise about **what you own**, what you enable, and what you influence but don’t directly control.

---

### 10.1 Ownership boundaries (what the platform and MLOps roles own)

#### A) Senior ML Platform Engineer ownership (platform-as-a-product)

Owns the shared capabilities that make ML delivery **repeatable, safe, and operable** across teams:

* **Paved road:** templates/SDKs, standard workflows for train → register → promote → deploy
* **Platform contracts:** versioned interfaces, schema/contract enforcement surfaces
* **Control plane:** promotion gates, approvals/exceptions, policy enforcement, lineage/provenance standards
* **Observability defaults:** standard metrics/logs/traces, dashboards/alerts hooks, correlation propagation
* **Serving primitives:** standard deployment patterns and reliability controls (timeouts, health checks, rollbacks)
* **Reliability posture:** SLO definitions, error budget monitoring for platform services, incident readiness patterns
* **DX and adoption:** onboarding, docs, migration paths, support model and compatibility strategy

**They are accountable for:**
Platform reliability, safety guardrails, and self-serve adoption outcomes.

---

#### B) Senior MLOps Engineer ownership (operating model systems on the platform)

Owns the operational lifecycle of specific ML systems built on top of the platform:

* **Reproducible pipelines:** training, evaluation, batch scoring, retraining orchestration
* **ML-aware CI/CD:** validation gates, evaluation thresholds, packaging, promotion readiness
* **Deployment operations:** controlled rollouts, canary/shadow where applicable, rollback execution and verification
* **Monitoring and action loops:** model/data/service health monitoring tied to mitigation actions
* **Drift response:** detect → decide → mitigate (rollback/retrain/degrade), within policy bounds
* **Learning governance:** as-of/maturity enforcement, leakage controls, reproducibility checks
* **Operational playbooks:** runbooks, incident readiness, postmortems for model/pipeline incidents

**They are accountable for:**
Safe and reliable operation of model lifecycle workflows and production model health.

---

### 10.2 What both roles influence (but may not “own” alone)

In real orgs, these are shared outcomes with other teams:

* **Business KPIs** (fraud capture rate, customer friction, review load): influenced by platform controls and model quality, but not solely owned by platform/MLOps.
* **Label strategy and ground truth quality:** depends on operations/case workflows and domain decisions.
* **Feature semantics:** domain teams define meaning; platform enforces contracts and operational constraints.
* **Risk appetite and policy thresholds:** set by product/risk/compliance; platform implements enforcement and reporting.

The truth anchor can reference these outcomes as **platform-enabled**, but should not over-claim sole ownership.

---

### 10.3 Non-goals (explicitly out of scope for the end-state claim)

The end-state is not required to prove the following in order to be “seasoned senior platform/MLOps”:

* Inventing the best fraud model architecture or feature set (model science is separate).
* Achieving top-tier fraud business performance metrics without production labels (domain-dependent).
* Building a full enterprise case management product UI (unless necessary for label/traceability proofs).
* Solving organizational process problems (stakeholder alignment is important, but not the platform’s functional proof).
* Implementing every possible serving mode (streaming, online, batch) if not required; what matters is that the chosen modes are **safe, reliable, and governed**.

---

### 10.4 “No over-claiming” rules (truth discipline)

To keep the narrative defensible:

* If you claim **SLO-grade reliability**, you must show SLOs, error budgets, and incident posture evidence.
* If you claim **replay-safe correctness**, you must show invariants + replay/backfill drills.
* If you claim **governed learning**, you must show as-of/maturity enforcement + leakage controls + reproducibility.
* If you claim **audit readiness**, you must show provenance completeness + bounded audit response.
* If you claim **cost control**, you must show unit economics + budget envelopes + idle-safe controls.

---

### 10.5 Boundary summary (one paragraph)

At the end-state, the ML Platform Engineer proves they built and operate the shared **paved road** and control plane that make ML delivery safe, observable, auditable, and scalable across teams. The MLOps Engineer proves they operationalize model systems on that road—pipelines, releases, monitoring, and learning loops—so models remain reliable under drift, data issues, and production failure modes. Domain/model teams own problem framing and feature meaning, while the platform enforces operational constraints and provides the evidence surfaces that make production operation defensible.

---

## 11) Evidence artifact index (end-state checklist)

This section is the **inspectable inventory** of what must exist at the prod_target end-state to make the Point X summary and tiered claims defensible. It is intentionally written as a checklist-style index so it can later become a “closure register” for the goal.

---

### 11.1 Paved road artifacts (platform product surfaces)

These prove the platform exists as a reusable product, not bespoke pipelines.

* **Golden-path templates** for:

  * training pipeline project scaffold
  * batch scoring scaffold (with idempotent output patterns)
  * online serving scaffold (health checks, timeouts, version headers, metrics)
* **SDK/CLI interfaces** (or equivalent standardized interfaces) for:

  * submitting jobs/runs, fetching run metadata
  * registering artifacts/models, requesting promotions
  * querying active versions and provenance
* **Documentation set**:

  * “first model to production” guide
  * troubleshooting guide for common failures
  * versioning/deprecation/migration policy
* **Reference architecture diagram**:

  * control plane vs data plane boundaries
  * ownership boundaries and the “safe path” workflow

---

### 11.2 Release corridor artifacts (governance + promotion + rollback)

These prove safe change and reversibility.

* **Promotion policy** (fail-closed gates + required evidence)
* **Gate outputs** and **release bundles** linking:

  * data contract validation
  * evaluation threshold checks
  * artifact integrity checks (scan/sign/attest where applicable)
  * required approval traces (exceptions recorded and time-bounded)
* **Promotion ledger / registry stage transitions**:

  * who promoted what, when, why, under what checks
* **Rollback runbooks** (platform and model) with:

  * last-known-good definition
  * verification steps (“stable” criteria)
* **Rollback drill reports**:

  * what was rolled back, what triggered it, how long it took, what was verified

---

### 11.3 Online path reliability artifacts (SLO posture and incident readiness)

These prove production operation, not one-off success.

* **SLI/SLO definitions** for online decision path
* **Error budget tracking** and burn alerts
* **Dashboards**:

  * latency p95/p99, error/timeout rates
  * saturation and bottleneck signals (CPU/memory, queue depth)
  * decision throughput and backlog
* **Alert rules** mapped to runbooks with clear ownership
* **Runbooks** for top failure modes:

  * latency spike, dependency outage, stream lag spike
  * feature retrieval degraded, model service degraded
  * fallback/degrade activation and verification
* **Incident artifacts**:

  * incident timeline records
  * postmortem templates and completed postmortems
  * remediation items with closure evidence

---

### 11.4 Streaming correctness artifacts (replay safety, idempotency, schema evolution)

These prove correctness under “real-world mess.”

* **Idempotency contract**:

  * idempotency keys, TTL/collision rules, dedupe store semantics
* **Offset/continuity tracking**:

  * how positions are recorded, validated, and used for reprocessing
* **Schema evolution policy**:

  * compatibility guarantees, validation rules, quarantine rules
* **Lag and checkpoint dashboards**:

  * consumer lag p95/p99, checkpoint success rates and durations
* **Quarantine store + reason taxonomy**:

  * searchable quarantine evidence, top reason trends
* **Replay/backfill playbooks**:

  * how to replay a window safely
  * integrity check procedure and acceptance criteria
* **Integrity invariant suite**:

  * “no double-count” checks
  * “consistent aggregates” checks
  * “no duplicate side-effects” checks (cases/actions/log entries)

---

### 11.5 Learning and promotion corridor artifacts (governed MLOps loop)

These prove learning is safe, reproducible, and reversible.

* **Dataset manifests**:

  * as-of window definitions and enforcement
  * label maturity cutoffs and lateness reporting
  * reproducibility references (data/version pointers)
* **Leakage guardrail reports**:

  * pass/fail results with violation diagnostics
* **Experiment tracking / provenance**:

  * code version, data references, config parameters, metrics, artifacts
* **Evaluation report bundle**:

  * baseline/champion comparisons
  * stability checks and slice reporting (as applicable)
* **Controlled rollout policy** (shadow/canary, rollback criteria)
* **Promotion evidence records**:

  * linking evaluation artifacts to deployed versions
* **Drift monitoring + mitigation records**:

  * drift events, severity classification, action taken, time-to-mitigate
* **Retraining triggers and governance policy**:

  * when retraining occurs, what gates apply, and how rollback is handled

---

### 11.6 Observability and auditability artifacts (traceability and diagnosability)

These prove the platform can answer production questions quickly and reliably.

* **Correlation/tracing propagation standard**

  * event ID and trace context across ingress → stream → decision → action
* **Audit-grade decision log**

  * append-only record with model version and key context
* **Lineage/provenance store**

  * links: decision → deployment → model artifact → training run → dataset manifest → code/config
* **Standard audit queries / “audit drill scripts”**

  * “what model was used for decision X?”
  * “why was model Y deployed?”
  * “what changed between version A and B?”
* **Audit drill reports**

  * measured audit response time, completeness checks, missing-field remediation

---

### 11.7 Cost-to-outcome artifacts (FinOps controls)

These prove spend is managed as part of platform engineering.

* **Unit cost dashboards**

  * cost per 1M events (online/stream), cost per retrain
* **Budget envelopes + receipts**

  * pre-declared budget per run/release + post-run cost-to-outcome evidence
* **Idle-safe enforcement**

  * automatic teardown/shutdown policies and verification evidence
* **Capacity and right-sizing records**

  * scaling policies tied to SLO posture
  * utilization metrics and optimization decisions

---

### 11.8 “Minimum artifact bundle” per Tier 0 claim (summary)

For each Tier 0 claim, the minimum artifact bundle must include:

* 1 **gate/control** artifact (policy + outputs)
* 1 **observability** artifact (dashboard/alert)
* 1 **operational** artifact (runbook)
* 1 **traceability** artifact (ledger/lineage/decision log)
* 1 **drill** artifact (report with time-bounded outcome)

---

### 11.9 Completion rule (end-state checklist)

The end-state is claimable only when:

* All **Tier 0 claims** are **L4 (production-proven)** per the claimability model.
* Tier 1 claims are **L3–L4** (pressure-tested / production-proven).
* The essential scorecard metrics are continuously available and stable.
* Drill reports exist and are repeatable on demand (not one-off).

---

## Appendix A: Workload envelope and assumptions (prod_target end-state)

This appendix pins the **operational envelope** the platform is built to meet. It makes “SLO-grade,” “replay-safe,” and “cost-to-outcome” claims unambiguous by defining the load patterns, latency budgets, failure expectations, and retention/compliance assumptions those claims must hold under.

### A.1 Envelope principles

* **End-state is envelope-driven:** every Tier 0 claim is interpreted as “true within this envelope.”
* **Envelope is expressed as distributions, not single numbers:** median + p95/p99, plus burst shapes.
* **Multiple envelopes are allowed:** you can define S (portfolio), M (target), L (aspirational) as long as each is measurable and testable. For the truth anchor, the goal is **at least one** clearly pinned envelope that is “production-shaped.”

---

### A.2 Workload taxonomy (what flows through the platform)

Define the set of production flows that share infrastructure and SLOs:

* **Online decision flow:** transaction/event ingress → stream processing/joins → scoring/decision → action and decision log.
* **Control flow:** configuration, policy changes, posture changes (degrade, rollout control).
* **Case/label flow:** case creation, human review actions, label surfacing and maturity updates.
* **Learning flow:** dataset materialization, training/evaluation jobs, promotion requests and rollbacks.
* **Audit flow:** trace queries, evidence retrieval, compliance export.

Each flow should have a pinned expectation for:

* expected rate and burst behavior
* latency criticality (hard vs soft)
* retention and audit requirements
* allowed degradation behavior

---

### A.3 Traffic envelope (rates, bursts, sizes)

Pin the platform’s load assumptions as a small set of measurable fields.

**A.3.1 Steady-state rates**

* **Online ingress steady rate:** `E_steady` events/sec (median over normal operation).
* **Online ingress p95 rate:** `E_p95` events/sec (sustained within typical peaks).
* **Online ingress peak rate:** `E_peak` events/sec (shorter peak periods).
* **Daily/weekly seasonality:** time-of-day and day-of-week pattern assumptions.

**A.3.2 Burst profile (critical for streaming fraud systems)**
A burst profile should specify:

* **Burst multiplier:** `B_mult` (peak over steady, for example 3×, 5×, 10×).
* **Burst duration:** `B_dur` (how long the burst lasts).
* **Burst ramp:** step vs ramp (instant spike vs gradual increase).
* **Burst correlation:** whether bursts hit many partitions/keys evenly or concentrate on a subset.
* **Retry storm assumption:** expected amplification factor during upstream retries (for example 1.2×–3× additional effective load).

**A.3.3 Payload sizes**

* **Average payload size:** `S_avg` bytes.
* **p95 payload size:** `S_p95` bytes.
* **Max payload size:** `S_max` bytes (hard limit).
* **Payload growth assumption:** expected schema evolution growth rate and bounds.

**A.3.4 Concurrency**

* **Max in-flight requests/events:** `C_max` at ingress and in key services.
* **Concurrency drivers:** burst ramp, retries, and downstream backpressure.

---

### A.4 Latency envelope (end-to-end budgets and hop budgets)

Latency must be budgeted end-to-end and by major boundary to support diagnosis and SLO enforcement.

**A.4.1 End-to-end decision latency**
Pin targets as distributions:

* **p50 decision latency target:** `L_p50_target`
* **p95 decision latency target:** `L_p95_target`
* **p99 decision latency target:** `L_p99_target`

Define the measurement boundary precisely:

* Start: ingress accepted (or received)
* End: decision recorded (and action emitted if that is part of the definition)

**A.4.2 Hop-level latency budgets**
Define budgets by boundary so “where time went” is observable:

* Ingress accept and validation
* Bus publish and consumption
* Stream processing and state joins
* Feature retrieval (if online features)
* Model scoring
* Decision persistence and action emission

Each hop should have:

* a p95 budget
* a p99 budget (if meaningful)
* an allowed degradation posture (what can be skipped or simplified)

**A.4.3 Latency under burst**
Define what must remain true during bursts:

* whether p95 must hold under burst or only p99 can degrade
* what backpressure behavior is allowed
* when degrade mode is triggered

---

### A.5 Streaming and backlog envelope (lag, recovery, integrity)

These assumptions connect directly to replay safety and correctness.

**A.5.1 Lag limits**

* **Consumer lag p95/p99 limits:** `Lag_p95_max`, `Lag_p99_max`
* **Lag breach tolerance:** how long a breach can persist before action is required
* **Late event tolerance:** if event-time semantics exist, define allowable lateness bounds

**A.5.2 Recovery-to-stable bounds**
Define what “stable” means and how fast recovery must be:

* **Restart-to-stable target:** `R_stable_target` (median and p90)
* **Checkpoint recovery expectations:** success rate and maximum recovery time
* **Data integrity after recovery:** invariants that must hold (no double-count, no missing side effects)

**A.5.3 Backpressure assumptions**

* expected queue depth thresholds
* how the system behaves when downstream slows (throttle, degrade, queue, reject)

---

### A.6 Replay and backfill envelope (time windows and completion bounds)

Replay safety is only meaningful if replay windows and completion expectations are pinned.

**A.6.1 Replay/backfill windows**
Define typical and worst-case windows:

* **Standard replay window:** `W_std` (for example 15m, 1h, 24h)
* **Max replay window:** `W_max`
* **Backfill frequency expectation:** how often reprocessing is expected (rare, periodic, frequent)

**A.6.2 Completion bounds**

* **Replay completion time target:** `T_replay_target` (median/p90)
* **Backfill completion time target:** `T_backfill_target`

**A.6.3 Integrity requirements**
For any replay/backfill:

* idempotency must prevent double side effects
* invariants must pass (counts, aggregates, downstream actions)
* audit records must show what was replayed and why

---

### A.7 Learning and promotion envelope (cadence and timeliness)

Pin “how often” and “how fast” learning is expected to run, because it affects ops, cost, and audit posture.

* **Dataset build cadence:** scheduled frequency or trigger conditions
* **Training and evaluation completion window:** `T_train_eval_target`
* **Label maturity expectation:** maturity delay distribution and cutoffs
* **Promotion cadence:** expected promotion frequency and maximum promotion latency
* **Rollback expectations:** rollback must be time-bounded and drill-proven

---

### A.8 Availability and disaster recovery assumptions

These are end-state expectations for a regulated production posture.

* **Availability target class:** defined SLO for the online decision path and key dependencies
* **RTO:** restore-to-stable bounds for critical components
* **RPO:** data loss tolerance (if applicable) for decision logs and key state
* **Failure domains:** multi-AZ baseline; multi-region is optional unless you explicitly want it in the end-state
* **Degraded operation rules:** what must continue functioning under partial outage

---

### A.9 Retention, audit, and data handling assumptions

These anchor auditability and cost.

* **Decision log retention:** duration and access control expectations
* **Event retention:** stream retention vs lake retention (separate)
* **Evidence retention:** how long to keep gate outputs, drill reports, lineage
* **PII handling assumptions:** encryption, access logging, masking rules where relevant
* **Audit query expectations:** required queries and maximum response time bound

---

### A.10 Cost envelope (unit economics and budget posture)

Pin the cost frame that “bounded spend” means.

* **Unit cost targets:** cost per 1M events, cost per retrain, cost per audit drill (if relevant)
* **Budget envelopes:** per release, per run, per replay/backfill
* **Idle burn target:** baseline cost when inactive must be bounded and enforced
* **Scaling assumptions:** autoscaling posture and right-sizing rules tied to SLOs

---

### A.11 Validation and measurement rules (how the envelope is proven)

For each envelope area, define how it is tested and measured:

* **Load tests:** steady + burst scenarios that match the burst profile
* **Soak tests:** sustained operation at `E_p95` for a defined duration
* **Replay/backfill drills:** run `W_std` and `W_max` windows and prove invariants
* **Failure-mode drills:** dependency outage, lag spike, schema evolution event, rollback drill
* **Scorecard reporting:** every metric in Section 8 must be derivable from a stable source of truth

---

### A.12 Assumption register format (so it stays maintainable)

Each pinned envelope assumption should be written as:

* **Assumption ID**
* **Statement** (what is assumed)
* **Reason** (why it matters)
* **How validated** (test/drill/measurement)
* **Evidence artifact** (where proof lives)
* **Last reviewed date** (so the envelope evolves deliberately)

---

## Appendix B: Failure-mode catalog + drill matrix (prod_target end-state)

This appendix defines the **canonical failure modes** the platform is expected to survive, and the **drills** that prove it. It operationalizes “designed for failure” by pinning: failure class → expected platform behavior → integrity checks → recovery bounds → evidence artifacts.

### B.1 Principles

* Failure modes are **normal**, not exceptional: retries, lag spikes, partial outages, schema evolution, and bad data will happen.
* A drill is valid only if it produces durable evidence: **scenario → expected behavior → observed outcomes → recovery bound → integrity checks → artifact output**.
* Drills should be runnable in a controlled way and repeated over time (not one-off demos).

---

## B.2 Failure-mode catalog (by platform lane)

### Lane 1: Ingress / Idempotency boundary (Control + Admission)

**FM-IG-01 Duplicate delivery (client retry / network retry)**

* **Failure:** same event delivered multiple times with same idempotency key.
* **Expected behavior:** duplicate suppressed; no double side effects.
* **Integrity checks:** no double case creation; no duplicate decision log writes; counters consistent.
* **Primary metrics:** duplicate-admission rate, dedupe hit rate.
* **Primary artifacts:** idempotency contract; dedupe metrics dashboard.

**FM-IG-02 Partial write / uncertain ack**

* **Failure:** client times out after sending; platform may or may not have accepted.
* **Expected behavior:** idempotency guarantees exactly-once-ish side effects.
* **Integrity checks:** dedupe store correctness; no missing or double effects.
* **Artifacts:** ingress receipts; idempotency store audit logs.

**FM-IG-03 Bad payload / schema invalid**

* **Failure:** payload violates schema or contract.
* **Expected behavior:** fail-closed admission; quarantine (or reject) with reason; no downstream processing.
* **Integrity checks:** quarantine count equals invalid input count; no decisions for quarantined events.
* **Artifacts:** quarantine reason taxonomy; validation outputs.

**FM-IG-04 Hot partition / key skew**

* **Failure:** disproportionate traffic for a subset of keys causing load imbalance.
* **Expected behavior:** controlled backpressure, throttling, or scaling; no correctness loss.
* **Integrity checks:** no data loss; bounded lag; stable dedupe behavior.
* **Artifacts:** partition/consumer metrics, throttling policies.

---

### Lane 2: Event bus / streaming substrate

**FM-EB-01 Producer publish failures**

* **Failure:** intermittent publish errors, retries, partial outages.
* **Expected behavior:** bounded retries; DLQ/quarantine when unrecoverable; observability surfaces clear.
* **Integrity checks:** no silent drops; error counters consistent with DLQ entries.
* **Artifacts:** DLQ policies; publish error dashboards.

**FM-EB-02 Consumer lag spike**

* **Failure:** downstream slows; lag grows.
* **Expected behavior:** alert fires; backpressure/degrade policy triggers; recovery returns lag within bound.
* **Integrity checks:** no data loss; replay/backfill procedures available; invariants hold post-recovery.
* **Artifacts:** lag dashboards; runbook “lag spike”.

**FM-EB-03 Rebalance storm**

* **Failure:** frequent consumer group rebalances cause instability.
* **Expected behavior:** stable processing resumes; checkpoints and recovery behave predictably.
* **Integrity checks:** checkpoint success rate; no duplicate side effects.
* **Artifacts:** consumer metrics; stream processor logs; runbook.

---

### Lane 3: Stream processing / Flink (or equivalent)

**FM-SP-01 Checkpoint failures**

* **Failure:** checkpoint fails due to state pressure or storage errors.
* **Expected behavior:** fail-closed posture for correctness; restart strategy; alerts fire.
* **Integrity checks:** state consistency; no double-count after restart.
* **Artifacts:** checkpoint metrics; recovery logs; integrity suite outputs.

**FM-SP-02 Processor restart / task manager loss**

* **Failure:** processor crashes or nodes are replaced.
* **Expected behavior:** recover within RTO; state restored; lag returns to normal.
* **Integrity checks:** invariants pass after recovery; stable throughput resumes.
* **Artifacts:** restart-to-stable drill report; post-recovery invariants.

**FM-SP-03 State blow-up / memory pressure**

* **Failure:** state grows unexpectedly (skew, bug, retention issue).
* **Expected behavior:** controlled failure; alerts; mitigations (scale, state compaction, degrade).
* **Integrity checks:** no corrupted state; replay plan defined.
* **Artifacts:** saturation dashboards; runbook; mitigation records.

**FM-SP-04 Schema evolution mid-flight**

* **Failure:** producer changes schema (compatible or incompatible).
* **Expected behavior:** compatible changes handled; incompatible changes quarantined/blocked; no silent drift.
* **Integrity checks:** quarantine reason distribution; zero silent parse errors.
* **Artifacts:** schema evolution policy; compatibility gates.

---

### Lane 4: Online feature retrieval / state stores (if used)

**FM-FS-01 Feature store latency spike**

* **Failure:** feature retrieval slows; threatens decision SLO.
* **Expected behavior:** degrade mode triggers (fallback features, cached features, or reduced capability); alerts fire.
* **Integrity checks:** decision path remains within degraded SLO; trace shows degrade posture.
* **Artifacts:** feature latency dashboards; degrade policy; runbook.

**FM-FS-02 Feature store outage**

* **Failure:** store unavailable.
* **Expected behavior:** fail-closed or degrade, per risk policy; no silent incorrect decisions.
* **Integrity checks:** policy compliance; no unbounded error budget burn.
* **Artifacts:** outage runbook; posture change logs.

**FM-SS-01 Write failures to decision log / state store**

* **Failure:** persistence layer errors.
* **Expected behavior:** fail-closed for audit-critical writes; retry with idempotency; alert.
* **Integrity checks:** append-only log invariants; no missing decisions.
* **Artifacts:** persistence error dashboards; integrity checks.

---

### Lane 5: Model serving / decisioning service

**FM-MS-01 Model service latency regression**

* **Failure:** new model version increases latency.
* **Expected behavior:** canary triggers rollback; SLO protected.
* **Integrity checks:** rollback restores latency; version headers confirm.
* **Artifacts:** rollout dashboards; rollback drill report.

**FM-MS-02 Model service error spike**

* **Failure:** elevated exceptions/timeouts.
* **Expected behavior:** rollback or degrade; alert; bounded MTTR.
* **Integrity checks:** error rate returns to baseline; decisions remain traceable.
* **Artifacts:** error dashboards; runbook.

**FM-MS-03 Dependency mismatch / artifact incompatibility**

* **Failure:** promoted model incompatible with serving runtime.
* **Expected behavior:** promotion gate blocks; never reaches prod.
* **Integrity checks:** gate fails closed with diagnostic output.
* **Artifacts:** artifact contract; gate output logs.

---

### Lane 6: Learning pipeline (dataset → train/eval → registry)

**FM-LN-01 Data leakage attempt**

* **Failure:** training data includes future info / forbidden truth.
* **Expected behavior:** pipeline fails closed; report emitted.
* **Integrity checks:** zero leakage-accepted runs.
* **Artifacts:** leakage guardrail report.

**FM-LN-02 Dataset immutability violation**

* **Failure:** training dataset changes after manifest is published.
* **Expected behavior:** blocked or versioned; provenance remains consistent.
* **Integrity checks:** fingerprint mismatch triggers failure; no silent retraining on changed data.
* **Artifacts:** dataset manifest/fingerprint; immutability checks.

**FM-LN-03 Training instability**

* **Failure:** training jobs fail intermittently or exceed runtime window.
* **Expected behavior:** retries bounded; failures surface clearly; cost bounds enforced.
* **Integrity checks:** pipeline success rate; cost per run within envelope.
* **Artifacts:** pipeline dashboards; cost receipts.

---

### Lane 7: Promotion corridor (MPR) and governance

**FM-PR-01 Gate bypass attempt / missing evidence**

* **Failure:** promotion request without required evidence.
* **Expected behavior:** blocked fail-closed; no prod mutation.
* **Integrity checks:** no state change without gate outputs present.
* **Artifacts:** promotion policy; gate logs.

**FM-PR-02 Rollback required**

* **Failure:** promoted model regresses KPI/SLO.
* **Expected behavior:** rollback within bound; audit record preserved.
* **Integrity checks:** stability restored; provenance indicates rollback.
* **Artifacts:** rollback drill report; promotion ledger.

---

### Lane 8: Observability / audit systems

**FM-OB-01 Alert noise / false positives**

* **Failure:** alert storms reduce operability.
* **Expected behavior:** alert tuning; precision increases; on-call burden decreases.
* **Integrity checks:** actionability ratio improves.
* **Artifacts:** alert review log; tuning changes.

**FM-AU-01 Provenance gaps**

* **Failure:** missing fields break audit traceability.
* **Expected behavior:** fail-closed for promotion; remediation workflow exists.
* **Integrity checks:** provenance completeness near 100% for prod.
* **Artifacts:** provenance audits; remediation records.

---

## B.3 Drill matrix (what must be proven, how, and what evidence is produced)

Each drill below follows the same structure.

### Drill format (standard)

* **Drill ID and name**
* **Failure mode(s) covered**
* **Setup conditions** (baseline load, environment, versions)
* **Injection method** (how failure is triggered)
* **Expected behavior**
* **Measurements captured** (metrics and timestamps)
* **Integrity checks**
* **Recovery bound**
* **Artifacts produced** (report + logs + dashboard snapshots)

---

## B.4 Required Tier 0 drill set (minimum)

These drills are mandatory to claim Tier 0 maturity.

### DR-01 Rollback drill (model promotion)

* Covers: FM-MS-01/FM-PR-02
* Proves: rollback time bounded; version headers confirm restored LKG; SLO recovers.

### DR-02 Replay/backfill integrity drill

* Covers: FM-IG-01/FM-EB-02/FM-SP-02
* Proves: replay-safe semantics; no double side effects; invariants pass; completion bound met.

### DR-03 Lag spike + recovery drill

* Covers: FM-EB-02/FM-SP-02
* Proves: detect → mitigate → recover; lag returns under bound; checkpoint recovery works.

### DR-04 Schema evolution drill

* Covers: FM-SP-04/FM-IG-03
* Proves: compatible changes pass; incompatible changes quarantine/block; no silent corruption.

### DR-05 Dependency outage + degrade drill

* Covers: FM-FS-02/FM-SS-01
* Proves: degrade mode engages; decision path remains safe; recovery bounded.

### DR-06 Audit drill

* Covers: FM-AU-01
* Proves: audit query response time bound; provenance completeness; trace chain intact.

### DR-07 Cost guardrail drill

* Covers: cost envelope violations
* Proves: budget envelope triggers action; idle-safe returns; unit costs remain explainable.

---

## B.5 Tier 1 drill set (differentiators)

### DR-08 Leakage attempt drill

* Covers: FM-LN-01
* Proves: leakage enforcement fail-closed with diagnostic report.

### DR-09 Drift simulation → mitigation drill

* Covers: drift-to-action loop
* Proves: detect → classify → mitigate within bounds; post-mitigation verification.

### DR-10 Training-serving skew drill

* Covers: feature skew incidents
* Proves: skew detected and blocked or degraded safely; no silent regressions.

### DR-11 Soak + burst drill

* Covers: burst profile + long-run stability
* Proves: SLO adherence under steady and burst; lag recovery; cost behavior within envelope.

---

## B.6 Evidence outputs required for every drill

Every drill must emit a durable “Drill Report Bundle” containing:

* Scenario + injection description
* Timeline with timestamps
* Observed vs expected behaviors
* Metrics extracted (before/during/after)
* Integrity check results
* Recovery bound result (met / not met)
* Follow-up actions (runbook/gate/monitor changes)

---

## B.7 Drill cadence (how often at end-state)

* **Per release:** DR-01 (rollback readiness check), DR-06 (audit spot-check)
* **Weekly/biweekly:** DR-02/DR-03 (replay and lag recovery)
* **Monthly/quarterly:** DR-04/DR-05/DR-07 and a soak/burst drill
* **On major changes:** DR-08/DR-09/DR-10 when learning or feature systems are altered

---

## Appendix B.8 Cross-reference map (Tier 0 claims → required drills)

This section explicitly links each **Tier 0 supporting claim** to the **minimum drill(s)** that make it defensible at prod_target end-state. The intent is to remove ambiguity: if a drill is missing, the claim is not fully claimable at senior-in-production standard.

---

### T0.1 Governed release corridor with fast rollback

**Required drills**

* **DR-01 Rollback drill (model promotion)**
  Proves rollback is real, time-bounded, and verified.
* **DR-06 Audit drill**
  Proves promotion/rollback actions are traceable and auditable.

**Optional / strengthening drills**

* **DR-11 Soak + burst drill** (run immediately after promotions for stability assurance)

---

### T0.2 SLO-grade online fraud decision path

**Required drills**

* **DR-05 Dependency outage + degrade drill**
  Proves degrade behavior preserves safety and maintains bounded operation.
* **DR-03 Lag spike + recovery drill**
  Proves the platform sustains and recovers when the stream slows (common production failure mode).

**Optional / strengthening drills**

* **DR-11 Soak + burst drill**
  Proves sustained SLO posture under steady + burst envelopes.

---

### T0.3 Replay-safe streaming correctness

**Required drills**

* **DR-02 Replay/backfill integrity drill**
  Proves replay does not double-count or corrupt state and passes invariants.
* **DR-03 Lag spike + recovery drill**
  Proves backlog scenarios can be recovered without correctness loss.
* **DR-04 Schema evolution drill**
  Proves schema change does not silently corrupt or degrade correctness.

**Optional / strengthening drills**

* **DR-11 Soak + burst drill**
  Proves correctness and lag behavior under realistic burst profiles.

---

### T0.4 Default observability + diagnosability

**Required drills**

* **DR-03 Lag spike + recovery drill**
  Proves detection, localization, and guided mitigation for a major failure class.
* **DR-04 Schema evolution drill**
  Proves detection/localization of contract/schema violations and correct quarantine/block behavior.
* **DR-05 Dependency outage + degrade drill**
  Proves the system localizes dependency failures and drives correct operator response.

**Optional / strengthening drills**

* **DR-06 Audit drill** (diagnosability includes traceability)
* **DR-11 Soak + burst drill** (observability under load)

---

### T0.5 Audit-grade provenance + decision traceability

**Required drills**

* **DR-06 Audit drill**
  Proves bounded audit response time and provenance completeness.

**Optional / strengthening drills**

* **DR-01 Rollback drill**
  Proves audit traceability includes promotion/rollback lineage, not just steady-state decisions.
* **DR-02 Replay/backfill drill**
  Proves traceability still holds under reprocessing (audit visibility on replay).

---

### T0.6 Cost-to-outcome control

**Required drills**

* **DR-07 Cost guardrail drill**
  Proves budget envelopes trigger action and idle-safe behavior is enforced.

**Optional / strengthening drills**

* **DR-11 Soak + burst drill**
  Proves unit economics and scaling behavior remain bounded under realistic loads.
* **DR-01 Rollback drill**
  Demonstrates cost impact of rollbacks and the ability to revert expensive regressions quickly.

---

## Appendix B.9 Cross-reference map (Tier 1 → drills) (optional add-on)

If you want the same explicit mapping for Tier 1 differentiators:

* **T1.1 Non-leaky learning inputs** → **DR-08 Leakage attempt drill**
* **T1.2 Drift-to-action loop** → **DR-09 Drift simulation → mitigation drill**
* **T1.3 Controlled rollout / challenger safety** → **DR-01 Rollback drill** + (rollout drill variant)
* **T1.4 Training-serving consistency** → **DR-10 Training-serving skew drill**
* **T1.5 Reliability hardening** → **DR-11 Soak + burst drill** + recurring DR-03/DR-05 suite

---

## Appendix B.10 Tier 0 claims → mandatory scorecard metrics (tight connector)

This section pins the **exact metrics** that must exist (with stable definitions and sources of truth) for each **Tier 0 supporting claim** to be considered end-state claimable. If a metric is missing, the claim is incomplete.

Each claim has:

* **Core mandatory metrics** (the minimum set)
* **Recommended strengthening metrics** (adds senior-grade completeness)

---

### T0.1 Governed release corridor with fast rollback

**Core mandatory metrics**

1. **Lead time for change (LT)** — merge/approval → running in production
2. **Deployment frequency (DF)** — promotions/releases per week
3. **Change failure rate (CFR)** — % releases causing rollback/SLO breach/incident
4. **Rollback time** — detect → last-known-good restored and verified
5. **Gate pass rate** — % promotions passing required gates first attempt
6. **Post-release regression rate** — % releases triggering rollback criteria within X hours/days

**Recommended strengthening metrics**
7) **Promotion cycle time** — candidate ready → prod (includes approvals)
8) **Exception rate** — % promotions requiring policy waivers (and expiry)
9) **Rollback success rate** — % rollbacks restoring stable state without follow-on incident

---

### T0.2 SLO-grade online fraud decision path

**Core mandatory metrics**

1. **End-to-end decision latency p95**
2. **End-to-end decision latency p99**
3. **Availability / SLO attainment** (and/or **error budget burn rate**)
4. **Decision-path error rate** (errors/timeouts)
5. **MTTR** — restore-to-stable for decision path incidents
6. **Degrade mode usage** — time-in-degrade and/or % traffic degraded

**Recommended strengthening metrics**
7) **Dependency contribution to latency** (top hop latency p95/p99)
8) **Saturation indicators** (CPU/mem/queue depth) correlated with SLO breaches
9) **User-impact proxy** (timeouts/fallback rate) during incidents and releases

---

### T0.3 Replay-safe streaming correctness

**Core mandatory metrics**

1. **Consumer lag p95**
2. **Consumer lag p99**
3. **Checkpoint success rate** (and checkpoint duration p95 if applicable)
4. **Dedupe hit rate**
5. **Duplicate-admission rate** (per million)
6. **Replay/backfill success rate** (with integrity checks passing)
7. **Replay/backfill time-to-complete** (median/p90)
8. **Quarantine rate** + **top quarantine reasons distribution**

**Recommended strengthening metrics**
9) **Integrity invariants pass rate** (no double-count, consistent aggregates)
10) **Late event rate / out-of-order rate** (if event-time semantics exist)

---

### T0.4 Default observability + diagnosability

**Core mandatory metrics**

1. **Time to detect (TTD)**
2. **Time to diagnose (TTDiag)**
3. **Alert precision (actionability)**
4. **Correlation/trace coverage** (edge→stream→decision→action)
5. **MTTR trend** (improvement over time; not just a point estimate)
6. **Top incident class distribution** (data vs model vs pipeline vs infra) with trend

**Recommended strengthening metrics**
7) **Alert recall** (incidents detected by alerts vs user-reported)
8) **Runbook coverage** (% critical alerts with linked runbooks)
9) **Noise budget** (alerts per on-call shift; trend down)

---

### T0.5 Audit-grade provenance + decision traceability

**Core mandatory metrics**

1. **Provenance completeness %** (for prod decisions/models)
2. **Audit query response time** (bounded minutes; median/p90)
3. **“What changed?” time** (time to identify change responsible for regression)
4. **Decision log integrity rate** (append-only invariants; missing/duplicate record rate)
5. **Trace chain completeness** (% decisions linked to model version + promotion record)
6. **Access audit completeness** (% sensitive accesses logged and attributable)

**Recommended strengthening metrics**
7) **Exception traceability completeness** (% exceptions with owner + rationale + expiry)
8) **Retention compliance** (records retained per policy; deletion/expiry correctness)

---

### T0.6 Cost-to-outcome control

**Core mandatory metrics**

1. **Cost per 1M events processed** (end-to-end for the online/stream path)
2. **Cost per retrain** (training/eval pipeline unit cost)
3. **Idle burn rate** (cost/day when “inactive”)
4. **Budget adherence** (% runs/releases within envelope)
5. **Cost anomaly rate** (unexpected spend spikes per period)
6. **Utilization efficiency** (CPU/GPU utilization and waste proxy)

**Recommended strengthening metrics**
7) **Cost per replay/backfill** (unit cost for reprocessing windows)
8) **Autoscaling efficiency** (SLO met with minimal overprovisioning)
9) **Cost-to-outcome ratio** (cost per certified release / per mitigation event)

---

## Appendix B.11 Global “must-exist” metric invariants (for credibility)

Regardless of claim, the scorecard is only credible if:

* Each metric has a stable **definition**, **aggregation window**, and **source-of-truth**.
* Metrics are reported as **distributions** where relevant (median + p90/p95/p99).
* Every Tier 0 claim has at least one metric from each of these families:

  * **Delivery/change safety**
  * **Reliability/SLO**
  * **Correctness (streaming/data)**
  * **Auditability**
  * **Cost**

---

## Appendix B.12 Tier 0 claims → mandatory artifacts (tight connector)

This section pins the **minimum artifact bundle per Tier 0 claim**. If an artifact is missing, that claim is not end-state claimable at “seasoned senior in production” standard.

For each claim, artifacts are grouped by type:

* **Control/Gate** (what enforces behavior)
* **Observability** (what shows health and detects regression)
* **Operations** (how humans respond and verify)
* **Trace/Audit** (how we prove what happened and why)
* **Drill Report** (proof under failure)

---

### T0.1 Governed release corridor with fast rollback

**Control/Gate**

* Promotion policy (fail-closed) with versioned gate definitions
* Promotion gate output bundle (data checks, eval checks, artifact integrity checks)

**Observability**

* Release health dashboard (post-release SLO view + regression indicators)
* Rollout monitoring view (canary/shadow metrics tagged by version)

**Operations**

* Rollback runbook (last-known-good selection + verification checklist)
* Post-release verification checklist (explicit accept/reject closure)

**Trace/Audit**

* Promotion ledger / registry stage transition record (who/what/when/why)
* Exception/waiver record format (owner, rationale, expiry)

**Drill Report**

* DR-01 rollback drill report bundle (timeline, metrics before/after, verification)

---

### T0.2 SLO-grade online fraud decision path

**Control/Gate**

* SLI/SLO specification for online decision path (including “stable” definition)
* Degrade ladder / fallback policy (what degrades, triggers, and correctness guarantees)

**Observability**

* Online path dashboard: latency p95/p99, availability, error rate, saturation
* Alert rules tied to SLO breach and key failure classes (owned + severity)

**Operations**

* Incident runbooks: latency spike, dependency outage, feature degradation, model service degradation
* Recovery verification checklist (what must be true to declare restored)

**Trace/Audit**

* Correlation/trace propagation standard (required headers/fields across boundaries)
* Decision log schema including version headers and correlation IDs

**Drill Report**

* DR-05 dependency outage + degrade drill report bundle (with recovery bound + integrity checks)

---

### T0.3 Replay-safe streaming correctness

**Control/Gate**

* Idempotency contract (keys, TTL, collision handling, side-effect rules)
* Schema evolution/compatibility policy (compatible vs incompatible behavior)
* Replay/backfill policy (who can trigger, what must be recorded, what checks must pass)

**Observability**

* Lag dashboard (consumer lag p95/p99) + checkpoint health dashboard
* Quarantine dashboard with reason taxonomy + trend view
* Dedupe effectiveness dashboard (hit rate + anomalies)

**Operations**

* Replay/backfill runbook (how to replay safely, how to validate invariants)
* Stream recovery runbook (checkpoint failure, restart, rebalance storm handling)

**Trace/Audit**

* Offset/continuity record format (what window was processed/replayed, with provenance)
* Integrity invariant suite outputs (no double-count, no duplicate side effects)

**Drill Report**

* DR-02 replay/backfill integrity drill report bundle (including invariant results)
* DR-04 schema evolution drill report bundle (block/quarantine evidence)

---

### T0.4 Default observability + diagnosability

**Control/Gate**

* Alerting standards (severity definitions, ownership rules, escalation policy)
* “Fail-closed on missing observability” rule for critical releases (optional but strong)

**Observability**

* Domain-isolating dashboards (data vs model vs pipeline vs infra):

  * SLO dashboard for online path
  * lag/checkpoint dashboard for streaming
  * pipeline health dashboard for learning jobs
  * data quality/contract dashboard
* Alert-to-runbook links (every critical alert has a runbook)

**Operations**

* Runbook library (indexed by alert/failure class)
* Incident timeline + postmortem template enforcing systemic fixes

**Trace/Audit**

* Correlation coverage report (percentage of events with full trace chain)
* Standard “diagnostic query pack” (queries that answer “where is it failing?”)

**Drill Report**

* DR-03 lag spike + recovery drill report bundle (shows detect → localize → mitigate)
* DR-04 schema evolution drill report bundle (shows detection and correct routing)

---

### T0.5 Audit-grade provenance + decision traceability

**Control/Gate**

* Provenance completeness gate for production promotion (fail-closed if missing fields)
* Retention/access control policy for audit data

**Observability**

* Provenance completeness dashboard (missing field rate by lane/version)
* Audit readiness dashboard (drill pass/fail status, last run date)

**Operations**

* Audit runbook (“answer question X in Y minutes”) with query examples
* Remediation workflow for missing provenance (how it gets fixed, how it’s prevented)

**Trace/Audit**

* Append-only decision log (immutable, queryable) with:

  * decision ID/event ID, timestamps, model version, correlation IDs
* Lineage store linking:

  * decision → deployment → model artifact → training run → dataset manifest → code/config
* Standard audit query pack:

  * “what model ran for decision X?”
  * “why was model Y promoted?”
  * “what changed between A and B?”

**Drill Report**

* DR-06 audit drill report bundle (includes response time + completeness verification)

---

### T0.6 Cost-to-outcome control

**Control/Gate**

* Budget envelope policy (what must be declared before runs/releases)
* Cost guardrail policy (what happens on threshold breach: alert/throttle/stop/teardown)

**Observability**

* Unit cost dashboard:

  * cost per 1M events, cost per retrain, cost per replay/backfill (if tracked)
* Idle burn dashboard (baseline footprint over time)
* Cost anomaly alerts (spend spike detection)

**Operations**

* FinOps runbook:

  * investigate spend spike
  * right-size/scale policy adjustments
  * verify idle-safe behavior
* Cost attribution method documentation (how costs map to lanes/runs)

**Trace/Audit**

* Cost-to-outcome receipts per run/release (envelope vs actual + outputs achieved)
* Resource inventory snapshots (what was running during spend windows)

**Drill Report**

* DR-07 cost guardrail drill report bundle (threshold breach → action → idle-safe verified)

---

## Appendix B.13 “Minimal artifact bundle” rule (quick check)

A Tier 0 claim is only end-state claimable if it has, at minimum:

* **1 enforceable policy/gate**
* **1 dashboard + alert**
* **1 runbook**
* **1 trace/audit record type**
* **1 drill report**

This ensures every claim is enforceable, observable, operable, auditable, and proven under failure.

---