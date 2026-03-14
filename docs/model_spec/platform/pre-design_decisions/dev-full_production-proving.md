# dev_full Production Proving Program (L4)

## 0. Document role and boundary

### 0.1 Role

This document is the **binding authority** for converting:

**`dev_full production-ready (L3)` → `production-proven (L4)`**

It defines the **post-certification operating program** (real-time, live management) and the **evidence standard** required to truthfully claim the platform was **operated like a production system**, not merely certified.

### 0.2 Boundary

This document begins **only after** `dev_full` has already been declared **production-ready** by the existing road-to-production program (PR0–PR5).

* This document **does not** modify, replace, or re-interpret PR0–PR5.
* PR0–PR5 remain the sole authority for “production-ready dev_full”.
* This document is solely about **L4 proof**: sustained operation + operational management + learning loops.

### 0.3 Scope

This document governs the **live operation** of the platform while it is running, including:

* continuous uptime posture (no “pause the system to fix it” norm)
* scheduled stress windows (steady + burst + recovery) while live
* planned incident drills (realistic failures) while live
* controlled change windows (deploy/config/policy/model changes) while live
* runbooks, dashboards, alerting, and operator access posture
* evidence capture (metrics + incident/change/audit artifacts)
* verdict rules (PASS / HOLD_REMEDIATE / FAIL) for L4 proof

### 0.4 Single source of truth: the proving window

All L4 proof in this document is measured over **wall-clock proving time**, not event-time in the data.

* **MIN proving window:** **7 consecutive wall-clock days**
* **MAX proving window:** **30 consecutive wall-clock days**
* A checkpoint report is produced at **day 7**; day 30 is the stronger, extended proof.

### 0.5 What this document produces

A successful execution produces:

1. **L4 proving verdict**: `PASS` / `HOLD_REMEDIATE` / `FAIL`
2. A complete **L4 evidence pack** that is recruiter/auditor readable:

   * continuous health metrics over the proving window
   * stress-window scorecards (steady/burst/recovery/soak slices)
   * incident drill timelines + outcomes + postmortems
   * controlled change record + rollback readiness evidence
   * audit drill outputs + time-to-answer measurement
   * cost receipts + unit-cost summary for the declared duty cycle

### 0.6 Non-negotiables (anti-gloss rules)

The following are binding:

* **No event-time substitution:** replaying “90 days of dated data” in a few hours does **not** count as a “90-day” L4 window.
* **No silent drift:** metric definitions, measurement surfaces, and load-shaping policy must remain stable for the proving window (or the window must restart).
* **No “single-run L4”:** L4 requires sustained operation and operational learning loops; a single short run is not acceptable as L4 proof.
* **No “operator = only you”:** the platform must be operable via documented access paths + runbooks such that a credentialed operator can diagnose/mitigate.

---

## 1. Purpose and non-goals

### 1.1 Purpose

To prove—through real operational behavior over real elapsed time—that the platform can be **managed like a production system**:

* it stays **live**
* it experiences **variation** (baseline + stress windows)
* it withstands **incidents** (planned drills and/or real faults) with bounded impact
* it supports **safe change** (controlled change + rollback readiness)
* it supports **audit answerability** under time pressure
* it produces durable evidence that the above is true

This is explicitly meant to demonstrate **senior ML Platform + senior MLOps operating responsibility**, not just implementation.

### 1.2 What “production-proven (L4)” means in this project

For this project, “L4 production-proven” means:

* **Sustained operation:** the platform operates continuously over the proving window with an explicit uptime posture.
* **SLO posture:** you can state what “good” looks like for the live system and show how close/far you were across the window (including burn/violation periods).
* **Incident learning:** at least one incident/drill results in a postmortem + a remediation, and the remediation is later verified (improvement or non-regression).
* **Repeatable auditability:** you can answer “what happened and why?” from platform evidence (not memory), and you can measure time-to-answer.
* **Transferable operations:** runbooks + dashboards + access allow a qualified operator to take over without you being the only brain.

### 1.3 Non-goals (what this doc is not)

This document is **not**:

* A second “road to production-ready” or a PR0–PR5 extension
* A rewrite of the platform architecture or a place to add new major components
* A “feature roadmap” (no scope expansion beyond operating proof)
* A BI/analytics product build (only the dashboards needed for ops + platform impact proof)
* A requirement to reach `prod_target` before you can claim L4 (this doc proves L4 on the `dev_full` operated system)

### 1.4 What success looks like (in plain language)

Success is being able to truthfully say:

> “The platform ran as a live system for 7–30 real days, we operated it via dashboards and runbooks, we handled incidents and changes without ‘taking it offline as the default move,’ we produced postmortems and verified fixes, we could answer audit questions quickly from evidence, and we can prove all of that with a clean evidence pack.”

---

## 2. Relationship to existing roads/specs

### 2.1 Precedence and authority

This document is **binding** for all post-certification work whose purpose is to establish **L4 production-proven** status.

Authority is ordered as follows:

1. **Road-to-production (PR0–PR5) authority** governs *production-ready dev_full* and remains unchanged.
2. This **Production Proving (L4)** document governs *post-production-ready proving* and is authoritative for:

   * proving-window rules (MIN 7d / MAX 30d wall-clock)
   * what counts as continuous operation
   * what counts as valid L4 evidence
   * what forces restart / invalidation
   * verdict criteria for L4 PASS / HOLD_REMEDIATE / FAIL

This document MUST NOT be used to redefine or “soften” any production-ready requirements. Likewise, passing PR0–PR5 MUST NOT be treated as equivalent to L4 proof.

### 2.2 Entry condition

The L4 proving program MAY begin only when **all** of the following are true:

1. `dev_full` has a **production-ready** verdict (`PASS`) under the existing road-to-production program.
2. The production-ready verdict is accompanied by:

   * a complete evidence pack for PR0–PR5 as defined by the road-to-production authority,
   * `open_blockers = 0` at production-ready declaration time.
3. The system is operable without “local orchestration” dependencies:

   * platform execution and observation are performed via the managed substrate and published evidence surfaces,
   * operator access paths exist (console/CLI) using appropriate credentials.

If any of the above is false, this program MUST NOT start; the correct action is remediation under the road-to-production program.

### 2.3 Continuity rule: no re-certification ladder

This document is explicitly **not** a second certification ladder.

* It does not introduce PR-style subphases as gates.
* It introduces a **single proving window** measured in wall-clock time, within which required operating events must occur.
* The proving window may be **extended** from MIN (7 days) to MAX (30 days) without changing the program structure; it is the same program with a longer observation period.

### 2.4 Compatibility with numeric contracts and runtime envelopes

The L4 proving program MUST operate under the **already pinned** production-ready runtime envelope and metric definitions.

* The runtime envelope used during L4 proving MUST be the same as the one used for production-ready declaration (e.g., `RC2-S`), unless an explicit repin is performed.
* Any repin of thresholds, metric definitions, measurement surfaces, or load-shaping policy is treated as a **material change** and triggers proving-window restart (see Section 11 restart/invalidation rules; authored later in this document).

### 2.5 What changes are allowed during L4 proving

L4 proving is an operating program. Some changes are expected and are part of the proof (controlled change + rollback readiness). However, changes must be governed:

Allowed:

* **Controlled changes** executed under the program’s change policy (defined later), including:

  * configuration changes,
  * deployment changes,
  * policy/model updates,
  * operational parameter tuning that does **not** redefine metric meaning.
* Operational mitigation actions taken during incidents (degrade modes, throttling, rollback, restart).

Not allowed:

* Any change that alters the meaning of the proving metrics, measurement surfaces, or load policy *without* declaring a restart.
* “Stop the world” interventions that break continuous operation posture except where explicitly allowed by the incident playbook and recorded as an incident.

### 2.6 Required link-out references (binding)

This document assumes and depends on the following existing authorities (names refer to your repository’s existing documents):

* The **road-to-production plan and implementation notes** for PR0–PR5 (production-ready authority).
* The **production standard** defining claim levels (L0–L4) and evidence expectations.
* The **data engine interface** (as the upstream data/Oracle boundary for platform operation).
* The **dev_full pre-design decisions** for production-ready (defines baseline interpretation and constraints).

Where any conflict exists:

* Conflicts about “production-ready” are resolved by the road-to-production authority.
* Conflicts about “production-proven (L4)” are resolved by this document **and** the production standard, with this document providing the binding operational interpretation.

---

## 3. Definitions and interpretations

### 3.1 The three clocks (binding)

This program distinguishes three clocks. All evidence MUST declare which clock it is using.

1. **Event-time (data-time)**
   The timestamps carried by events (e.g., synthetic dates such as Jan 1 → Mar 31).
   Event-time supports realism and coverage claims (seasonality, cohort behavior, maturity windows), but it does **not** define “time operated” for L4 proving.

2. **Injection-time (playback-time)**
   The wall-clock schedule at which events are injected into the platform.
   Injection-time is affected by load controls such as **stream speedup** and burst shaping.
   Injection-time governs achieved EPS and the shape of stress windows.

3. **Proving-time (wall-clock operating time)**
   The actual elapsed real time during which the platform is live and being operated under this program.
   **Proving-time is the only clock that counts for “7 days” / “30 days” proving windows.**

**Rule:** Replaying “90 days of event-time” in a few hours by injection-time compression does **not** constitute “90 days of proving.” It is a stress technique, not a proving window.

---

### 3.2 Meaning of “continuous operation” (binding)

For this program, “continuous operation” means:

* The platform remains **up and operable** for the entire proving window in proving-time.
* Operators manage the system using dashboards, logs, runbooks, and controlled procedures while the platform remains live.
* Normal maintenance actions are allowed (rolling restarts, controlled changes) **without** treating downtime as the default operating mode.

“Continuous operation” does **not** mean:

* “Everything must remain perfect at all times,” or
* “No restarts are permitted,” or
* “No mitigations are allowed.”

It does mean:

* You do not routinely “stop the whole platform” to debug.
* If downtime occurs, it is treated as an **incident**, timed, explained, and remediated—then counted against the reliability posture.

---

### 3.3 What constitutes “an incident” in this program

An incident is any event that materially threatens one or more of:

* service availability / SLO posture,
* latency or error-rate ceilings,
* lag/backlog stability,
* correctness/safety (replay behavior, schema safety),
* auditability/provenance completeness,
* bounded cost posture.

Incidents may be:

* **planned drills** (explicitly injected failures), or
* **unplanned faults**.

Both count as “real operations” evidence if they are recorded, managed, and learned from.

---

### 3.4 What constitutes a “controlled change”

A controlled change is a deliberate modification applied while the platform remains live, executed under an explicit change plan, with:

* declared change intent,
* expected impact and rollback plan,
* verification steps,
* rollback readiness evidence (even if rollback is not used),
* post-change validation against the live metric surfaces.

Examples include:

* config changes (rate limits, scaling policy, thresholds),
* deployment changes (service version update),
* policy/model updates (promotion within the governed corridor),
* operational tuning (so long as it does not redefine metric meaning without restart).

---

### 3.5 “Runbook” definition (what it must contain)

A runbook is an operator playbook that enables a credentialed operator to:

* identify symptoms using the named dashboards/logs,
* follow first-check steps that narrow the cause,
* apply safe mitigations (and avoid unsafe actions),
* verify recovery using named signals,
* record outcomes and produce the incident/change artifact.

A runbook MUST include at minimum:

* entry conditions / symptoms,
* first 5–10 minute checks (links/paths to the views),
* safe actions + unsafe actions,
* verification checklist,
* escalation / “declare incident” trigger,
* rollback steps where applicable.

---

### 3.6 “Dashboard” definition (what it must enable)

A dashboard is an operator-facing view that supports fast situational awareness and diagnosis.

For this program, dashboards must enable:

* “Is the system healthy right now?”
* “What’s broken (latency/errors/lag/cost)?”
* “What changed recently?”
* “Where do I look next?”

Dashboards are not required to be pretty; they are required to be operationally useful and referenced by runbooks.

---

### 3.7 Evidence and proof terms

* **Evidence artifact:** a persisted record (metrics snapshot, scorecard, timeline, run receipt, postmortem, audit drill output) stored in the run/evidence system.
* **Proof:** a claim supported by evidence artifacts with stable definitions.
* **Claimable L4:** a proof that is measured over proving-time MIN/MAX windows, includes at least one learning loop (incident → remediation → verification), and supports repeatable audit answerability.

---

### 3.8 “Day-7 checkpoint” and “Day-30 close”

* **Day-7 checkpoint:** the minimum proving window completion report. If blockers exist, the program exits `HOLD_REMEDIATE` and the proving window must restart after remediation.
* **Day-30 close:** the extended proving completion report. It strengthens the L4 proof by demonstrating durability over a longer operated period, not by changing program structure.

These are not “extra gates.” They are time-based reporting points in a single proving program.

---

## 4. Binding pinned decisions

This section is the **single source of truth** for all values and rules that MUST NOT be treated as advisory. Any deviation is a program violation and must be handled via restart/invalidation rules (defined later).

### 4.1 Proving window policy (binding)

1. **Proving-time clock:** The proving window is measured in **wall-clock operating time** (Section 3.1), not event-time span.
2. **Minimum proving window:** **7 consecutive wall-clock days**.
3. **Maximum proving window:** **30 consecutive wall-clock days**.
4. **Day-7 checkpoint:** At the end of day 7, produce a checkpoint report and verdict:

   * If `open_blockers > 0` → verdict MUST be `HOLD_REMEDIATE` and the proving window MUST restart after remediation.
   * If `open_blockers = 0` → verdict MAY be `PASS_L4_MIN` and the proving window continues unchanged toward day 30.
5. **Day-30 close:** At the end of day 30, produce the final close report and verdict `PASS_L4_STRONG` (if eligible) or `HOLD_REMEDIATE` / `FAIL` (if not).

### 4.2 Continuous operation posture (binding)

1. The platform MUST remain **live and operable** for the entirety of the proving window.
2. Platform management must occur via:

   * dashboards/alerts,
   * logs/traces (where applicable),
   * runbooks,
   * controlled change and incident procedures.
3. “Stop-the-world” interventions (pausing the platform as the default troubleshooting technique) are disallowed.

   * If downtime occurs, it MUST be treated as an incident, timed, recorded, and counted against reliability posture.

### 4.3 Operating program shape (binding)

The proving window MUST include all of the following program elements:

1. **Always-on baseline operation** (continuous).
2. **Scheduled stress windows** (repeatable) that exercise:

   * steady load segment(s),
   * burst segment(s),
   * recovery verification.
3. **At least one controlled incident drill** executed while live.
4. **At least one controlled change** executed while live, with rollback readiness proof.
5. **At least one audit drill** executed while live, with measured time-to-answer.

These elements are mandatory for L4 claimability. A proving window that lacks any one of them is ineligible for `PASS_L4_*`.

### 4.4 Load shaping and injection policy (binding)

1. Load shaping controls (e.g., stream speedup, burst shaping) MAY be used to achieve the declared envelope, but only if:

   * the load shaping policy is explicitly declared at proving-window start,
   * the policy is stable for the proving window,
   * the policy is recorded in run receipts and evidence artifacts,
   * the policy does not break semantic correctness constraints (e.g., time-causality/maturity rules).
2. Any change to load shaping policy during the proving window is a **material change** and triggers proving-window restart.

### 4.5 Metric definitions and measurement surfaces (binding)

1. All “Tier-0” proving metrics MUST have:

   * stable definitions (no mid-window reinterpretation),
   * declared measurement surfaces/boundaries,
   * recorded computation sources.
2. Any change to:

   * metric definition,
   * measurement surface,
   * aggregation method,
   * threshold family,
     is a **material change** and triggers proving-window restart unless explicitly handled by an approved “restart-with-repin” procedure.

### 4.6 Change policy and repin policy (binding)

1. **Controlled changes** are allowed and are part of the proof (Section 3.4), but must be executed under the program’s change procedure and recorded.
2. **Re-pinning** (changing thresholds, envelopes, or authoritative expectations) is not forbidden, but it is never silent:

   * all repins must be explicit,
   * repins must include rationale and impact analysis,
   * repins must be recorded in the evidence pack,
   * repins MUST restart the proving window unless explicitly allowed by a documented “repin during proving” exception (default is restart).

### 4.7 Operator transferability (binding)

The proving program MUST demonstrate that the platform is not “only operable by one person.”

Minimum requirement:

* runbooks exist and are actually used during at least one incident or drill,
* dashboards provide a “first 2 minutes” health view,
* access paths are documented such that a credentialed operator can triage, mitigate, and verify recovery.

### 4.8 Cost posture (binding even if budget is generous)

Even if spend is not currently constrained, the platform MUST still operate with:

1. A declared budget envelope and cost-alert posture (to prove operability under guardrails).
2. A unit-cost metric (at minimum one) computed for the declared duty cycle.
3. An idle-safe closure / teardown procedure verified at least once (typically at the end of the program).

Cost governance is part of L4 claimability because “production-proven” implies the system can be operated without uncontrolled runaway spend.

---

## 5. Proving program design (day-to-day operating model)

This section defines the **binding operating program** for the proving window. It is written to ensure the platform is managed **as a live product**, with variation, incidents, and change—without normalizing downtime.

### 5.1 Program overview (what must happen while live)

During the entire proving window (MIN 7d / MAX 30d), the platform MUST be operated under the following live program:

1. **Always-on baseline operation** runs continuously (proving-time).
2. **Daily scheduled stress windows** exercise the declared runtime envelope (steady + burst + recovery verification).
3. **Controlled incident drills** are executed while live (minimum 1 in the window; more in the 30-day extension).
4. **Controlled change windows** are executed while live (minimum 1 in the window; more in the 30-day extension).
5. **Audit drills** are executed while live (minimum 1 in the window; more in the 30-day extension).
6. **Daily operator loop** is performed: review dashboards/alerts, record an ops summary, and ensure evidence capture is complete.

These are not optional “nice to haves.” A proving window that does not include all elements above is **ineligible** for `PASS_L4_*`.

---

### 5.2 Always-on baseline operation (continuous)

**Baseline operation** means the platform is live and producing/processing work continuously.

**Binding requirements:**

1. Baseline operation MUST run for the full proving window with no planned “stop the platform” periods.
2. Baseline load MUST be **non-zero** and stable enough to make monitoring meaningful.
3. Baseline MUST be operated through the managed substrate (no local orchestration dependency).
4. Baseline monitoring MUST be active continuously (dashboards + alarms).
5. Any baseline interruption MUST be treated as an incident (timed, recorded, explained).

**Baseline load policy (binding):**

* The proving program SHALL define a `PP.baseline_profile` at window start (recorded in receipts), expressed relative to the declared runtime envelope:

  * `PP.baseline_rate_eps := k × RC2-S.steady_rate_eps`, where `k` is pinned at proving start and remains stable through the window.
* The baseline MAY vary diurnally only if the diurnal schedule is pinned at proving start (stable definition; recorded).

This preserves realism (always-on) while allowing controlled variation.

---

### 5.3 Daily scheduled stress windows (steady + burst + recovery)

Stress windows exist to prove that the platform can hit and survive the declared envelope **while live**, not in isolated benchmark mode.

**Minimum cadence (binding):**

* For the **7-day MIN** proving window: **at least 1 stress window per day**.
* For the **30-day MAX** proving window: **at least 1 stress window per day** continues unchanged (optionally increased later only by explicit repin + restart rules; default is stable cadence).

**Stress window template (binding):**
Each stress window MUST execute the following segments in-order, while baseline remains live:

1. `W0` **Pre-check / entry lock**

   * confirm dashboards green enough to start
   * confirm operator access works
   * record “window start” receipt

2. `W1` **Steady segment**

   * inject at `RC2-S.steady_rate_eps` for `RC2-S.steady_duration`
   * measure on declared surfaces
   * record steady scorecard + receipts

3. `W2` **Burst segment**

   * inject at `RC2-S.burst_rate_eps` for `RC2-S.burst_duration`
   * use declared shaping policy (no silent changes)
   * record burst scorecard + receipts

4. `W3` **Recovery verification**

   * verify the system returns to stable within the declared recovery bounds
   * record recovery scorecard + receipts

5. `W4` **Window close**

   * snapshot key metrics (latency/error/lag/cost deltas)
   * mark window as PASS/FAIL at the window level
   * record “window end” receipt

**Hard rule:** Stress windows do not permit “stop the platform to reset state.” Any required reset is an incident and counts against continuous operation.

---

### 5.4 Controlled incident drills (operate through failure, not around it)

Incident drills are mandatory because production-proven requires demonstrated capability to detect, diagnose, mitigate, recover, and learn.

**Minimum cadence (binding):**

* For the **7-day MIN** proving window: **at least 1 controlled incident drill**.
* For the **30-day MAX** proving window: **at least 1 controlled incident drill per calendar week** of operation.

**Drill selection (binding constraints):**

* Drills MUST be realistic and tied to plausible failure modes of the platform (streaming/backlog, dependency degradation, schema incompatibility, compute restart, throttling/saturation, etc.).
* Drills MUST be executed while the platform remains live (no “offline drill” credit).
* Drill injection MUST be declared and logged (no stealth breakage without timestamps/receipts).

**Incident drill execution template (binding):**

1. `D0` Declare drill window and intent; record entry receipt.
2. `D1` Inject the fault (controlled).
3. `D2` Detect and acknowledge using dashboards/alerts (record TTD).
4. `D3` Diagnose via runbook-driven steps (record TTDiag).
5. `D4` Mitigate and recover while live (record MTTR and recovery verification).
6. `D5` Produce a postmortem artifact within the program’s reporting cadence.
7. `D6` Track remediation item(s) and schedule a later verification (required for L4).

**Hard rule:** At least one drill MUST result in a remediation action that is later verified (this is the “incident learning” obligation).

---

### 5.5 Controlled change windows (ship safely while live)

Controlled change proves you can operate change in production posture: deploy, verify, and maintain rollback readiness.

**Minimum cadence (binding):**

* For the **7-day MIN** proving window: **at least 1 controlled change**.
* For the **30-day MAX** proving window: **at least 1 controlled change per calendar week** of operation.

**Controlled change execution template (binding):**

1. `C0` Declare change intent, scope, expected impact, and rollback plan; record entry receipt.
2. `C1` Execute the change while the platform remains live.
3. `C2` Verify expected behavior using named metric surfaces (latency/error/lag/cost).
4. `C3` Produce rollback readiness evidence:

   * demonstrate rollback path is available and safe,
   * record rollback plan and “rollback readiness” receipt.
5. `C4` Record change close receipt and link to all supporting artifacts.

**Hard rule:** “Change completed” without verification artifacts is invalid. A controlled change that cannot demonstrate rollback readiness is a program violation.

---

### 5.6 Audit drills (answerability under time pressure)

Audit drills prove that the platform can answer “what happened and why?” from evidence, not memory.

**Minimum cadence (binding):**

* For the **7-day MIN** proving window: **at least 1 audit drill**.
* For the **30-day MAX** proving window: **at least 1 audit drill per calendar week** of operation.

**Audit drill execution template (binding):**

1. Select a decision/event slice (or incident period) and declare the audit question.
2. Execute the audit answer procedure using evidence surfaces (logs/provenance/registries).
3. Record:

   * time-to-answer,
   * evidence sources used,
   * the final answer artifact.
4. If gaps are found (missing provenance, missing linkage), create remediation items and track them.

---

### 5.7 Daily operator loop (the “live product” rhythm)

Every calendar day during the proving window MUST include an operator loop.

**Daily loop requirements (binding):**

1. Review the “first 2 minutes” health view and confirm current posture.
2. Review alarms and incident queue (even if empty).
3. Confirm scheduled stress window(s) executed and evidence artifacts were captured.
4. Record a **daily ops summary artifact** that includes:

   * uptime posture notes (any incidents / downtime),
   * stress window outcomes (PASS/FAIL and key deltas),
   * cost posture (spend deltas / unit cost snapshot),
   * outstanding remediation items and their status.
5. Ensure any ad-hoc operational steps taken that day are captured as:

   * runbook updates, or
   * appended “operator notes” artifacts linked to the relevant incident/change.

This is mandatory because L4 is about sustained operation and evidence continuity, not one-off success.

---

### 5.8 Program schedule summary (binding minimums)

To remove ambiguity, the proving program MUST meet at least these minimums:

**Within MIN 7-day window:**

* baseline always-on for 7 consecutive days,
* ≥ 1 stress window per day,
* ≥ 1 controlled incident drill total,
* ≥ 1 controlled change total,
* ≥ 1 audit drill total,
* daily ops summary artifact for each day.

**Within MAX 30-day window (continuation):**

* baseline always-on through day 30,
* ≥ 1 stress window per day through day 30,
* ≥ 1 controlled incident drill per week,
* ≥ 1 controlled change per week,
* ≥ 1 audit drill per week,
* daily ops summary artifact for each day.

Failure to meet any minimum above results in `HOLD_REMEDIATE` (or `FAIL` if unrecoverable) and the proving window is not claimable as L4.

---

## 6. Required metric surfaces (always-on during proving)

This section defines the **mandatory metric families** that MUST exist and be observed during the proving window. These are the minimum surfaces required to operate the platform like a production system and to assemble an L4 evidence pack.

### 6.1 General rules (binding)

1. **Always-on requirement:** All metric families in this section MUST be available continuously during the proving window (baseline + stress windows + drills).
2. **Stable definitions:** Metric definitions, aggregation windows, and measurement surfaces MUST remain stable for the proving window.
3. **Named boundary:** Each metric MUST declare the boundary it measures (e.g., `via_IG`, service boundary, stream processor boundary, DB boundary).
4. **Distribution first:** Where applicable, metrics MUST be captured as distributions (p50/p95/p99) rather than only averages.
5. **Evidence linkage:** Each metric family MUST be linkable to evidence artifacts (daily ops summary, stress window scorecard, incident drill timeline, audit drill output).

---

### 6.2 Runtime service health (SLO posture)

These metrics provide the primary “is the service healthy?” view.

**Must include:**

* **Availability / success rate** (success ratio of requests or decisions at the primary claim boundary).
* **Error rate** (overall and by major class where possible: 4xx/5xx/timeouts/retries).
* **Error budget posture** (at minimum: a daily burn indicator + cumulative burn for the proving window).

**Evidence expectations:**

* Availability + error rate plotted continuously for baseline and stress windows.
* Error budget burn reported in daily ops summary.

---

### 6.3 Latency performance (distributions)

These metrics prove responsiveness under baseline, stress, and degraded modes.

**Must include:**

* **Latency p50/p95/p99** at the primary claim boundary.
* Latency for key internal hops if available (optional but recommended for diagnosis).

**Evidence expectations:**

* Stress window scorecards must snapshot latency distributions during steady and burst.
* Incident drill artifacts must show latency impact and recovery.

---

### 6.4 Throughput and load realization

These metrics prove that the intended injection profile was realized.

**Must include:**

* **Achieved EPS** during stress windows:

  * `steady_rate_eps (observed)` and `burst_rate_eps (observed)`
* **Processed EPS** at key processing stages if available (to detect throttling/backpressure).

**Evidence expectations:**

* Stress window scorecards must show target vs observed EPS and identify the measurement surface.
* Any shaping policy (speedup/shaper) must be recorded alongside throughput metrics.

---

### 6.5 Lag / backlog / checkpoint health (streaming operability)

These metrics prove the platform can keep up and recover from stress without accumulating hidden debt.

**Must include (as applicable to your streaming architecture):**

* **Consumer lag** (p95/p99) or equivalent backlog measure.
* **Backlog depth** (queue depth / partition backlog / unprocessed events).
* **Checkpoint / commit health** (checkpoint success rate; time since last successful checkpoint).
* **Replay/backfill safety signals** (where your system exposes them).

**Evidence expectations:**

* Stress window scorecards must include lag/backlog distributions and checkpoint health.
* Recovery verification must explicitly show return-to-stable for lag/backlog.

---

### 6.6 Correctness and safety surfaces (runtime semantics)

These metrics ensure speed isn’t achieved by breaking correctness.

**Must include:**

* **Admission outcomes** and failure reasons (accepted vs rejected; reason distribution).
* **Schema safety / contract failures** (schema mismatch counts; incompatible payload counts).
* **Replay/duplicate handling indicators** (duplicates detected/dropped/merged; idempotency violations if any).

**Evidence expectations:**

* Incident drill artifacts must include correctness signals (no “silent corruption”).
* Daily ops summary must include any correctness anomalies and their disposition.

---

### 6.7 Operational excellence metrics (diagnosis + recovery)

These metrics prove you can run the system, not just observe it.

**Must include:**

* **TTD** (time-to-detect) for incidents/drills.
* **TTDiag** (time-to-diagnose).
* **MTTR** (time-to-recover to stable).
* **Change failure rate** (for controlled changes inside proving window; at minimum: count + whether rollback was needed).
* **Rollback readiness time** (time to execute rollback steps, if exercised; otherwise readiness evidence).

**Evidence expectations:**

* Each incident drill timeline must record TTD/TTDiag/MTTR.
* Controlled change artifacts must record verification outcome and rollback readiness proof.

---

### 6.8 Auditability and provenance surfaces (answerability)

These metrics prove that you can answer “what happened and why?” from evidence.

**Must include:**

* **Time-to-answer** for audit drills (measured).
* **Provenance completeness** indicator (at minimum: % of sampled decisions/events that have full linkage to:

  * runtime config,
  * model/policy version,
  * data/feature version or fingerprint,
  * code/build identity,
  * run receipt / deployment identity).

**Evidence expectations:**

* Audit drill outputs must show time-to-answer and evidence sources used.
* Any provenance gaps must become tracked remediation items.

---

### 6.9 Cost governance surfaces (bounded operation)

These metrics prove the platform can be operated responsibly (even if budget is generous).

**Must include:**

* **Spend vs budget envelope** over time (daily).
* **Top cost drivers** (service-level or component-level contributors).
* **Unit cost** for the declared duty cycle (at minimum one):

  * e.g., `$ per million events processed` or `$ per 1k decisions`, pinned definition.
* **Cost anomaly detection** (alert or daily check rule).

**Evidence expectations:**

* Daily ops summary must include spend delta + unit cost snapshot.
* Any anomaly triggers an operator action record (even if only an investigation).

---

### 6.10 Evidence capture minimums per program element

To ensure metric surfaces are actually used:

* **Baseline (continuous):** availability, error rate, latency, lag/backlog, cost must be continuously visible.
* **Each stress window:** must produce a scorecard containing:

  * target vs observed EPS,
  * latency p95/p99,
  * error rate,
  * lag/backlog p95/p99,
  * recovery verification.
* **Each incident drill:** must capture TTD/TTDiag/MTTR + metric deltas + final stable confirmation.
* **Each controlled change:** must capture pre/post verification + rollback readiness evidence.
* **Each audit drill:** must capture time-to-answer + provenance completeness sample.

If any required surface is missing at the time it is needed, the program must record a blocker and the proving window becomes ineligible for `PASS_L4_*` until remediated and restarted (per restart rules defined later).

---

## 7. Dashboards and alerting inventory (operability contract)

This section pins the **minimum operational views and alerting policy** required to run the platform like a production system during the proving window. Dashboards and alerts are treated as part of the platform contract: if they do not exist (or are not usable), the platform is not operable and L4 proof is invalid.

### 7.1 General rules (binding)

1. Dashboards MUST be the primary operator interface during proving (not ad-hoc local scripts).
2. Every runbook MUST reference the named dashboards/log views in this section.
3. Every alert MUST map to:

   * a named dashboard view for context,
   * a named runbook for response.
4. Alerting MUST be “actionable by design”:

   * if an alert fires and there is no safe action, it is noise and must be corrected.
5. A “silent failure” is treated as a proving failure:

   * if a drill breaks the system and no alert fires, this is a blocker (observability gap).

---

### 7.2 The “First 2 Minutes” dashboard (Tier 0)

This is the single most important operational view. It answers:
**“Is the platform healthy right now, and if not, what class of problem is it?”**

**Must include (live, continuously):**

* Availability / success rate (primary claim boundary)
* Error rate (overall) + top error classes
* Latency p95/p99 (primary boundary)
* Throughput (current EPS) + stress window indicator
* Lag/backlog p95/p99 (or equivalent)
* Cost (today spend delta vs envelope) + anomaly indicator

**Binding requirement:** Every daily operator loop starts with this dashboard.

---

### 7.3 Runtime performance dashboards (Tier 0)

These dashboards provide deeper operational context.

**Must include:**

* Latency distributions over time (p50/p95/p99)
* Error rate over time with breakdown (timeouts, dependency errors, throttles, validation failures)
* Throughput realized vs target during stress windows (target vs observed overlay)
* Recovery views: lag/backlog decay after burst and after incidents

---

### 7.4 Streaming health dashboards (Tier 0 where streaming exists)

**Must include:**

* Consumer lag distribution (p95/p99)
* Backlog depth / queue depth
* Checkpoint/commit health
* Restart/rebalance indicators (if applicable)
* Dead-letter / quarantine volumes (if present)

**Binding requirement:** These views must be sufficient to diagnose “can’t keep up” vs “downstream blocked” vs “schema mismatch” without guessing.

---

### 7.5 Correctness & safety dashboards (Tier 1)

These dashboards support “speed without corruption.”

**Must include:**

* Admission outcomes (accepted vs rejected)
* Rejection reason distribution
* Schema mismatch / contract failure counts
* Replay/duplicate handling indicators (if exposed)

---

### 7.6 Change and incident timeline dashboard (Tier 0)

This view overlays operational events on metrics.

**Must include:**

* Deployments / controlled changes annotated on time series
* Incident/drill start/end annotations
* A link from each annotation to the change record / incident record artifact

**Binding requirement:** Every incident and every controlled change must appear on this timeline, or it is treated as an evidence integrity failure.

---

### 7.7 Cost governance dashboards (Tier 0)

Even with generous budget, cost must be operable.

**Must include:**

* Spend vs envelope (daily and cumulative)
* Top cost drivers (service/component level)
* Unit cost view (pinned definition; trend over time)
* Anomaly detection indicator (alerted or flagged)

---

### 7.8 Auditability dashboard / views (Tier 1)

This supports “answerability under time pressure.”

**Must include:**

* Quick links/search patterns for retrieving:

  * decision records / decision logs
  * provenance linkages (model/policy/config identity)
  * deployment/run receipts
* A “time-to-answer” log for audit drills (even if manually tracked into an artifact at v0)

---

### 7.9 Alert policy (severity model)

Alerts must be categorized and mapped to actions.

**Minimum severity levels (binding):**

* **SEV0:** platform unavailable / catastrophic correctness risk / runaway cost
* **SEV1:** SLO breach imminent, sustained high error rate, sustained lag/backlog growth
* **SEV2:** partial degradation, elevated latency, moderate backlog, non-critical dependency issues
* **SEV3:** informational (no paging), early warning, capacity trend signals

**Binding requirement:** Only SEV0–SEV2 may page/interrupt an operator. SEV3 must not page.

---

### 7.10 Minimum alert set (Tier 0)

At minimum, the proving program MUST have alerts for:

* Availability drop below threshold (primary boundary)
* Error rate above threshold (overall and/or critical class)
* Latency p95/p99 above threshold
* Lag/backlog growth beyond bound
* Checkpoint/commit failure or staleness
* Cost anomaly / spend rate anomaly
* Auditability gap indicator (if provenance completeness drops sharply, or if audit linkages break)

Each alert MUST specify:

* the severity
* the dashboard to open first
* the runbook to follow

---

### 7.11 Alert-to-runbook mapping (binding)

No alert may exist without a runbook mapping.

**Binding rule:** If an alert fires and there is no mapped runbook, this is a blocker and must be remediated. Likewise, if a drill triggers a failure mode and no alert fires, this is a blocker.

---

### 7.12 Evidence requirements for dashboards and alerts

To be claimable in the evidence pack:

* screenshots are not sufficient on their own
* dashboard configuration must be reproducible (exported definition or IaC reference)
* alert configuration must be reproducible (rules + thresholds + routing)
* the daily ops summary must reference the dashboard views used that day

Failure to provide reproducible dashboard/alert definitions is an evidence integrity violation and makes L4 proof ineligible.

---

## 8. Runbook set (minimal but production-real)

This section defines the **mandatory runbooks** for the proving program and the minimum structure each runbook must follow. The goal is not to predict every future failure; it is to ensure a credentialed operator can triage, mitigate, recover, and verify using repeatable procedures.

### 8.1 Runbook format (binding template)

Every runbook MUST use this structure:

1. **Name / Scope**

   * What system/component boundary it covers

2. **When to use (symptoms / triggers)**

   * Which alerts (by name) or dashboard symptoms activate this runbook

3. **Safety constraints**

   * What MUST NOT be done (unsafe actions)
   * What is safe to do (safe actions)

4. **First 10 minutes checklist**

   * Exactly which dashboards/log views to open (by name)
   * Exactly what to check first (ordered steps)

5. **Diagnosis decision tree (minimal)**

   * “If X then check Y” style branching
   * Focused on the most likely causes

6. **Mitigation steps**

   * Concrete operator actions that reduce impact (throttle, degrade, isolate, restart safely, rollback)

7. **Recovery verification**

   * What metrics must return to what posture
   * How long to observe before declaring stable

8. **Escalation / declare incident**

   * When to declare SEV0/SEV1
   * Who/what to notify (even if “record incident artifact” for solo operator)

9. **Evidence capture requirements**

   * What artifacts must be written (timeline, metrics snapshots, action log)
   * Links to the incident/change record template

**Binding rule:** A runbook is not considered “present” unless it includes dashboard/log references and verification steps.

---

### 8.2 Mandatory runbooks (Tier 0 set)

The following runbooks are mandatory for L4 proving. Each must exist and be used at least once where relevant (incident drill, controlled change, audit drill).

#### RB0 — Operator quickstart: “First 10 minutes”

Purpose: enable any credentialed operator to determine health and where to look next.

Must include:

* access prerequisites (what credentials/tools are needed)
* the “First 2 Minutes” dashboard link
* basic triage: availability, errors, latency, lag/backlog, cost
* where logs/traces live and how to search the last 15 minutes
* how to find active deployment/run receipts
* how to declare an incident artifact

#### RB1 — Incident management: “Acknowledge → Mitigate → Recover”

Purpose: standard procedure for handling any SEV0–SEV2 alert.

Must include:

* severity decision rules
* TTD / TTDiag / MTTR capture requirements
* how to apply degrade mode / throttle
* how to decide rollback vs restart vs wait
* post-incident: create postmortem and remediation item(s)

#### RB2 — Rollback and revert readiness

Purpose: prove you can undo changes safely.

Must include:

* rollback triggers and “do not hesitate” conditions
* step-by-step rollback procedure for:

  * runtime deployment change
  * configuration change
  * policy/model change (if applicable)
* rollback verification checklist
* evidence: rollback readiness receipt (even if rollback not executed)

#### RB3 — Lag/backlog runaway and catch-up control

Purpose: handle sustained lag growth, backlog creep, or checkpoint stalling.

Must include:

* how to confirm lag/backlog is real (not metric artifact)
* how to identify the bottleneck stage (ingest vs processing vs sink)
* safe actions:

  * throttle ingress / apply backpressure intentionally
  * scale processing (if supported)
  * isolate bad partitions/keys (if supported)
* recovery verification:

  * lag/backlog returns within bound
  * checkpoint health returns to stable
* unsafe actions:

  * wiping state without replay safety proof

#### RB4 — Schema incompatibility / contract breach handling

Purpose: manage schema drift or incompatible payloads without corrupting downstream.

Must include:

* how to detect schema mismatch vs parsing vs validation failures
* how to route to quarantine / DLQ (if applicable)
* how to stop propagation safely (fail-closed posture)
* how to reprocess after remediation (with replay safety)
* evidence: list of offending schema versions/payload signatures and disposition

#### RB5 — Replay/backfill safety procedure

Purpose: prove replay safety and operational correctness under reprocessing.

Must include:

* when replay/backfill is permitted
* idempotency expectations and duplicate handling checks
* how to validate that replay will not cause double-counting or corruption
* verification: compare counts/checksums/receipts pre vs post replay

#### RB6 — Cost anomaly / runaway spend procedure

Purpose: demonstrate cost operability even when budget is generous.

Must include:

* how to detect anomaly (dashboard + alert)
* top cost driver identification steps
* safe mitigation:

  * reduce duty cycle / pause stress windows
  * scale down non-critical components
  * apply degrade mode
* verification: spend rate returns toward expected slope
* evidence: anomaly record + mitigation actions + post-run cost receipt

#### RB7 — Audit answerability procedure (“Why did decision X happen?”)

Purpose: prove audit-ready traceability.

Must include:

* how to select a decision/event and retrieve its record
* how to retrieve:

  * policy/model version identity
  * runtime config identity
  * deployment/run receipt identity
  * input evidence (features/data lineage where applicable)
* time-to-answer capture
* evidence: final answer artifact with sources

---

### 8.3 “Use during proving” requirement (binding)

The proving program MUST demonstrate runbooks are not shelfware.

Minimum usage requirements:

1. RB0 MUST be referenced in daily operator loop at least once (first day and whenever operator access changes).
2. RB1 MUST be used during the controlled incident drill(s).
3. RB2 MUST be used during the controlled change window(s) to produce rollback readiness evidence.
4. RB7 MUST be used during audit drill(s).
5. At least one of RB3/RB4/RB5/RB6 MUST be exercised during the proving window (via drill or real fault), to demonstrate non-happy-path operations.

If a required runbook exists but is not exercised when its corresponding event occurs, this is an evidence integrity blocker.

---

### 8.4 Runbook-to-alert linkage (binding)

Every SEV0–SEV2 alert MUST reference:

* the primary runbook to follow (RB* id),
* the dashboard(s) to open first,
* the verification checklist to confirm recovery.

If any SEV0–SEV2 alert lacks a runbook mapping, this is a blocker and invalidates L4 proof until fixed and the proving window restarted (restart rules later).

---

### 8.5 Runbook versioning and drift control (binding)

Runbooks are operational contracts.

* Runbooks MUST be versioned.
* Any runbook changes during the proving window MUST be logged in the daily ops summary (what changed and why).
* If a runbook changes because of an incident, the postmortem MUST reference the updated runbook revision.

This ensures the proving window demonstrates “operability that improves,” not ad-hoc hero debugging.

---

## 9. Incident learning loop (what makes this L4)

This section defines the **mandatory learning obligation** that separates “we survived incidents” (L3-ish) from **production-proven operation** (L4). The platform must not only recover; it must demonstrate that failures lead to durable improvements that are later verified.

### 9.1 Binding requirement: at least one verified learning loop

During the proving window, the program MUST complete **at least one** full learning loop:

1. **Incident (or drill) occurs**
2. **Postmortem is written**
3. **Remediation is implemented**
4. **Remediation is verified** by a later run/drill showing improvement or non-regression

If no learning loop is completed, the program is **ineligible** for `PASS_L4_*` even if uptime was good.

---

### 9.2 Incident record vs postmortem (definitions)

* **Incident record (live log):** created at incident start, updated during response.
  Contains timeline timestamps and operator actions.
* **Postmortem (learning artifact):** created after stabilization, focused on causes and prevention.
  Must be evidence-backed, not memory-based.

Both are required. The incident record proves real operations; the postmortem proves learning.

---

### 9.3 Postmortem template (binding)

Every postmortem MUST include:

1. **Summary**

   * What happened (one paragraph)
   * Impact (what was affected)

2. **Timeline**

   * detection time (TTD)
   * diagnosis time (TTDiag)
   * mitigation steps and timestamps
   * recovery time (MTTR)
   * return-to-stable verification time

3. **Customer/platform impact**

   * Which SLOs were breached or threatened
   * Error budget impact for the incident period
   * Lag/backlog impact (if applicable)
   * Cost impact (if notable)

4. **Root cause analysis (evidence-backed)**

   * “Primary cause” and “contributing factors”
   * Supporting evidence references (logs/metrics/receipts)

5. **What worked / what didn’t**

   * Which alerts fired (or didn’t)
   * Which runbooks helped (or were missing/insufficient)

6. **Remediation items**

   * Concrete actions with owners (even if owner = you)
   * Priority
   * Expected outcome metric(s)
   * Deadline (within the proving program timeline)

7. **Verification plan**

   * When/how the remediation will be verified
   * What “success” means (pinned measurement)
   * Which drill or stress window will validate it

---

### 9.4 Remediation tracking (binding)

All remediation actions MUST be tracked with:

* unique id
* description
* severity (SEV0/1/2)
* status (OPEN / IN_PROGRESS / DONE / VERIFIED)
* link to the incident/postmortem
* link to the verification evidence

A remediation is not complete until it is **VERIFIED**.

---

### 9.5 Verification requirement (binding)

Verification MUST be performed during the proving window (MIN 7d / MAX 30d) unless explicitly impossible.

Verification MUST include:

* a repeat of the relevant condition (drill or comparable stress window)
* before/after metric comparison where applicable
* confirmation of non-regression on correctness and safety metrics
* a verification artifact linked to the remediation id

**Rule:** “We fixed it” without verification evidence does not count as learning.

---

### 9.6 Observability improvement obligation (binding)

At least one learning loop must include an improvement in **operability**, not only throughput or latency.

Examples:

* an alert that failed to fire is corrected and validated by re-running the drill
* a noisy alert is tuned and shown to reduce false positives
* a missing dashboard panel is added and referenced in the runbook
* a runbook is expanded and demonstrated in a later incident/drill

This ensures the L4 proof demonstrates “operability that improves,” not just “compute got faster.”

---

### 9.7 Evidence artifacts required for the learning loop

For the learning loop to count, the evidence pack MUST contain:

* incident record (timeline + actions)
* postmortem document
* remediation tracking entry (DONE)
* verification artifact (VERIFIED) with linked metrics
* updated runbook/dashboard references if applicable

If any artifact is missing, the learning loop does not count and L4 proof is invalid.

---

## 10. Audit drills and answerability (traceability proof)

This section defines the **mandatory audit proof** required for L4 claimability. The goal is to demonstrate that the platform can answer “what happened and why?” from evidence, under time pressure, without relying on the operator’s memory.

### 10.1 Binding requirement: at least one audit drill

During the proving window, the program MUST execute **at least one** audit drill (MIN 7d) and then repeat audits on a weekly cadence during the MAX 30d extension.

An audit drill must be executed **while live** and must produce a durable audit artifact.

---

### 10.2 Audit question set (binding minimum)

Each audit drill MUST answer at least the following minimum questions for a selected decision/event slice:

1. **What happened?**

   * Identify the event/decision(s) under audit (ids, time range, boundary).

2. **Why did it happen?**

   * Explain the causal chain at the decision boundary (rule/policy outcome and/or model output, with feature/context reference if available).

3. **What version was responsible?**

   * Identify:

     * policy/model version identity (or decision logic identity),
     * runtime configuration identity,
     * deployment/build identity (what code was running),
     * environment identity (dev_full proving window identifier).

4. **What inputs were used?**

   * Identify the primary input evidence available to the decision boundary:

     * event payload signature and schema version,
     * feature references / fingerprints where applicable,
     * any enrichment/join provenance pointers.

5. **What changed recently?**

   * Determine whether a controlled change or incident occurred near the audited event time, and whether it plausibly affected behavior.

6. **Is the answer reproducible?**

   * Provide the references required for a second operator to reproduce the same answer by following the audit procedure/runbook.

---

### 10.3 Audit drill selection rules

Each audit drill MUST select one of the following as its target:

* a normal baseline period decision slice, **or**
* a stress window decision slice (steady or burst), **or**
* an incident period decision slice (preferred at least once in the 30-day window).

**Rule:** At least one drill (across 7–30 days) should be incident-adjacent, because auditability under failure pressure is part of “production-proven.”

---

### 10.4 Time-to-answer (binding measurement)

Each audit drill MUST measure **time-to-answer**:

* start time: when the audit question is declared
* end time: when the final audit artifact is produced and can be reviewed

Time-to-answer MUST be recorded in the audit artifact along with:

* all evidence sources consulted
* any missing linkage encountered

**Binding rule:** If the audit answer requires manual guessing because provenance is missing, that is a blocker and must generate remediation items.

---

### 10.5 Provenance completeness (binding sampling)

Each audit drill MUST include a small provenance completeness sampling step:

* sample `N` decisions/events from the audited slice (N pinned by the program; default can be modest)
* for each sample, check whether you can link to:

  1. decision record
  2. policy/model identity
  3. runtime config identity
  4. deployment/build identity
  5. input payload signature + schema version
  6. run receipt / mission identifier

Record:

* `% complete`
* the missing link types (if any)
* remediation items for missing link patterns

---

### 10.6 Audit drill execution template (binding)

Every audit drill MUST follow this structure:

1. **Declare**

   * question(s)
   * target slice (ids/time range)
   * start timestamp

2. **Collect evidence**

   * decision/event logs
   * deployment/config/model/policy references
   * change/incident timeline references
   * input evidence pointers

3. **Synthesize**

   * produce the narrative answer (“what/why/version/inputs/changes”)
   * include direct pointers to evidence locations

4. **Measure**

   * time-to-answer
   * provenance completeness sampling result

5. **Conclude**

   * pass/fail for audit drill
   * remediation items (if needed)
   * end timestamp

---

### 10.7 Audit runbook requirement (binding)

Audit drills MUST be executed using the audit runbook (RB7).
The audit artifact MUST reference the runbook version used.

If RB7 exists but is not used, the audit drill does not count as L4 proof.

---

### 10.8 Evidence artifacts required for auditability

For each audit drill, the evidence pack MUST contain:

* audit drill artifact (answers + evidence pointers)
* time-to-answer measurement
* provenance completeness sampling results
* remediation items (if any) with tracking ids
* references to change/incident timeline entries (where relevant)

Missing artifacts invalidate the audit drill and make the proving window ineligible for `PASS_L4_*`.

---

## 11. Evidence pack, restart rules, and verdicts

This section defines (a) what evidence MUST exist for L4 claimability, (b) what invalidates or forces restart of the proving window, and (c) the binding verdict rules at day 7 and day 30.

### 11.1 Verdict states (binding)

The proving program emits exactly one of the following verdicts:

* `PASS_L4_MIN`
  L4 proof achieved at the **7-day minimum** proving window.

* `PASS_L4_STRONG`
  L4 proof strengthened by completing the **30-day maximum** proving window.

* `HOLD_REMEDIATE`
  Proof is not claimable due to open blockers, missing evidence, or invalidation conditions. Remediation is required and the proving window must restart.

* `FAIL`
  The proving attempt is invalidated in a way that cannot be corrected without a full reset (e.g., evidence integrity loss that cannot be reconstructed, unlogged material change, or repeated critical failures that break the program’s continuity/operability intent). A new proving attempt must be started after corrective action.

**Hard rule:** `PASS_L4_*` is only possible when `open_blockers = 0`.

---

### 11.2 Evidence pack definition (binding)

The L4 evidence pack MUST be complete, inspectable, and reproducible. It MUST contain:

#### A) Proving window identity + receipts

* proving window id (unique)
* start/end timestamps (proving-time)
* pinned proving parameters at window start:

  * baseline profile (`PP.baseline_profile`)
  * stress window cadence
  * declared load shaping policy (if any)
  * change policy cadence
* operator access confirmation record (RB0 execution receipt)

#### B) Continuous metric archive (always-on)

* time series for all required metric families in Section 6 over the full proving window
* explicit note of any metric gaps (if any gaps exist, they must be addressed under restart rules)

#### C) Daily operator loop artifacts

* 1 daily ops summary artifact per calendar day of proving-time (Section 5.7)

Each daily ops summary MUST include:

* health posture summary (availability/errors/latency/lag)
* stress window outcome(s) that day (PASS/FAIL + links)
* cost posture snapshot (spend delta + unit cost snapshot)
* incidents/changes/audits executed that day (links)
* current remediation ledger status

#### D) Stress window scorecards

For each stress window executed:

* window entry/exit receipts
* steady scorecard (target vs observed EPS + latency/error/lag + surface)
* burst scorecard (target vs observed EPS + latency/error/lag + surface)
* recovery verification scorecard
* PASS/FAIL adjudication for the window

#### E) Incident drill artifacts

For each controlled incident drill (and any real incident):

* incident record (timeline + actions)
* TTD / TTDiag / MTTR measurements
* metric deltas + recovery verification
* postmortem artifact (Section 9.3)
* remediation items (Section 9.4)

#### F) Controlled change artifacts

For each controlled change:

* change declaration artifact (intent/scope/risk)
* execution record (what changed, when)
* verification artifact (named metrics before/after)
* rollback readiness artifact (RB2 usage evidence + rollback plan)
* change close receipt linked on the change/incident timeline dashboard

#### G) Audit drill artifacts

For each audit drill:

* audit question declaration + target slice
* time-to-answer measurement
* evidence pointers used
* provenance completeness sampling results
* remediation items for any provenance gaps

#### H) Dashboard and alert reproducibility proof

* exported definitions or IaC references for:

  * “First 2 Minutes” dashboard
  * change/incident timeline dashboard
  * Tier-0 alert rules (SEV0–SEV2) and routing
* alert-to-runbook mapping table (must be complete)

#### I) Remediation ledger (single list)

* consolidated remediation ledger with:

  * ids
  * linked incident/postmortem/change/audit
  * status (OPEN/IN_PROGRESS/DONE/VERIFIED)
  * verification evidence link for VERIFIED items

#### J) Final reports

* Day-7 checkpoint report (required)
* Day-30 close report (required only if extending to MAX)

---

### 11.3 Blockers and `open_blockers` computation (binding)

A **blocker** is any condition that prevents a truthful L4 claim.

`open_blockers` is the count of blockers that remain unresolved at checkpoint/close time.
A blocker is not resolved until there is evidence of remediation and (where required) verification.

#### Blocker families (non-exhaustive but binding categories)

1. **CONTINUITY_BREACH**

   * proving window is not continuous in proving-time (platform intentionally stopped or prolonged outage without incident framing and recovery evidence)
   * baseline does not run continuously for the required window length

2. **MISSING_REQUIRED_PROGRAM_ELEMENT**

   * missing daily stress window(s)
   * missing required incident drill(s)
   * missing required controlled change(s)
   * missing required audit drill(s)
   * missing daily ops summary for any day

3. **METRIC_SURFACE_GAP**

   * required metric families were not available during the window
   * metric gaps exist that cannot be reconstructed from authoritative sources
   * metric definitions/surfaces were changed without restart

4. **EVIDENCE_INTEGRITY_FAILURE**

   * required artifacts are missing
   * dashboards/alerts are not reproducible (only screenshots, no exported definitions/IaC reference)
   * alerts exist without runbook mappings or drills fail without alerts firing (silent failures)

5. **UNDECLARED_MATERIAL_CHANGE**

   * load shaping policy changed mid-window
   * measurement surfaces changed mid-window
   * thresholds/envelopes repinned mid-window
   * any other material change defined in Section 4 occurred without explicit restart

6. **SLO_POSTURE_FAILURE (UNRESOLVED)**

   * sustained breaches of the pinned production-ready envelope remain unremediated by checkpoint time
   * recovery obligations are not met (system does not return to stable after stress/incident within declared bounds)

7. **LEARNING_LOOP_INCOMPLETE**

   * no verified learning loop completed (incident/drill → postmortem → remediation → verification)

8. **AUDITABILITY_FAILURE**

   * audit drill cannot answer minimum questions (Section 10.2) from evidence
   * provenance completeness shows systemic linkage gaps without remediation tracking

9. **COST_GOVERNANCE_FAILURE**

   * cost surfaces missing (cannot show spend vs envelope / unit cost)
   * runaway cost event occurred without detection + mitigation procedure evidence

**Hard rule:** Any single blocker family above is sufficient to make the window ineligible for `PASS_L4_*`.

---

### 11.4 Restart vs continue rules (binding)

The proving window is designed to survive incidents and controlled changes **without restarting**, as long as integrity is preserved. However, certain events force restart.

#### A) Events that DO NOT require restart (allowed, expected)

* controlled incidents/drills executed and recovered while live with complete artifacts
* controlled changes executed with verification + rollback readiness artifacts
* rolling restarts as part of controlled operations, provided:

  * continuous operation posture is maintained
  * incident/change artifacts capture the action and its effect
  * metric continuity is preserved

#### B) Events that REQUIRE restart (material change / invalidation)

The proving window MUST restart from day 0 if any of the following occur:

1. **Metric meaning drift**

   * any required metric definition changes (aggregation method, denominator, boundary)
   * any required measurement surface changes
   * any threshold family repin affecting verdict meaning

2. **Load policy drift**

   * load shaping policy changes (speedup/shaper parameters, injection path semantics)
   * stress cadence changes (number/duration) without explicit repin+restart

3. **Evidence integrity loss**

   * missing continuous metrics for any required Tier-0 family that cannot be reconstructed
   * missing daily ops summary for any day (cannot be backfilled)
   * missing stress window scorecards for required windows

4. **Undeclared material change**

   * any change that should have been declared but was not (even if beneficial)

5. **Stop-the-world operations**

   * the platform is intentionally stopped as a routine troubleshooting method (not incident-managed)

Restart means:

* declare `HOLD_REMEDIATE`
* remediate the cause
* begin a new proving window with a new proving window id

---

### 11.5 Day-7 checkpoint verdict (binding)

At the end of day 7 (proving-time), the program MUST emit a checkpoint report and verdict.

`PASS_L4_MIN` is allowed only if all are true:

1. proving window ran continuously for 7 consecutive days
2. daily ops summary exists for all 7 days
3. ≥ 1 stress window executed per day (and scorecards exist)
4. ≥ 1 controlled incident drill executed with complete artifacts
5. ≥ 1 controlled change executed with verification + rollback readiness artifacts
6. ≥ 1 audit drill executed with time-to-answer + provenance sample
7. ≥ 1 verified learning loop completed (Section 9.1)
8. dashboard + alert reproducibility evidence exists (not screenshots-only)
9. `open_blockers = 0`

If any condition is false → verdict MUST be `HOLD_REMEDIATE` (or `FAIL` if evidence integrity is unrecoverable).

---

### 11.6 Day-30 close verdict (binding)

If the program continues beyond day 7, it MUST run unchanged through day 30 unless a restart condition occurs.

`PASS_L4_STRONG` is allowed only if all are true:

1. proving window ran continuously for 30 consecutive days
2. daily ops summary exists for all 30 days
3. ≥ 1 stress window executed per day for all 30 days (and scorecards exist)
4. weekly cadences were met (Section 5.8):

   * ≥ 1 controlled incident drill per calendar week
   * ≥ 1 controlled change per calendar week
   * ≥ 1 audit drill per calendar week
5. ≥ 1 verified learning loop completed (and remains verified)
6. auditability remains intact (no systemic provenance collapse without remediation)
7. cost governance surfaces remain intact (spend/unit cost measurable throughout)
8. `open_blockers = 0`

If any condition is false → verdict MUST be `HOLD_REMEDIATE` (or `FAIL` if unrecoverable).

---

### 11.7 What “remediate” means (binding)

When in `HOLD_REMEDIATE`:

1. All blockers MUST be explicitly listed with ids and linked evidence.
2. Each blocker MUST have a remediation plan and an owner.
3. Remediation actions MUST be executed and recorded.
4. Where required, remediation MUST be verified (Section 9.5 / Section 10 provenance rules).
5. A new proving window MUST be started from day 0 after remediation, with pinned parameters declared again (Section 4.1 / 4.4 / 4.5).

**Hard rule:** There is no “partial credit” L4 claim after a HOLD unless a subsequent proving window passes.

---

## 12. Open decisions log (v0 → pinned)

This section is the **only place** where unresolved choices are tracked. Anything not explicitly pinned in Sections 0–11 must appear here as **OPEN** (or be inherited by explicit reference to an existing authority such as `RC2-S`).

### 12.1 Status legend

* `PINNED` — binding in this document (or bound by referenced authority)
* `OPEN` — not yet pinned; must be pinned before starting L4 proving
* `CANDIDATE` — proposed value; not binding until promoted to `PINNED`

### 12.2 Decision register

**OD01 — L4 proving window duration policy**

* Status: `PINNED`
* Decision: `MIN=7 consecutive days`, `MAX=30 consecutive days` (wall-clock proving-time)
* Authority: Section 4.1

**OD02 — Stress window cadence**

* Status: `PINNED`
* Decision: ≥ 1 stress window per day (7-day MIN and 30-day MAX)
* Authority: Section 5.3 / 5.8

**OD03 — Stress window segment durations and exact envelope values**

* Status: `OPEN (in this document); inherited by RC2-S where already pinned`
* Decision: Steady duration, burst duration, recovery bound, soak expectation, and target EPS are taken from the declared runtime envelope (`RC2-S`).
* Binding requirement: The proving program must reference the exact `RC2-S` values in receipts and scorecards.
* Action needed: Ensure `RC2-S` definitions are fully pinned and stable before L4 window start.

**OD04 — Baseline duty-cycle profile (`PP.baseline_profile`)**

* Status: `OPEN`
* Decision: Pin the baseline rate as `k × RC2-S.steady_rate_eps`, plus whether diurnal variation is allowed.
* Must include: `k` value, diurnal schedule (if any), and whether baseline ever goes to zero (default: must be non-zero).
* Reason: Without this, “always-on baseline” is ambiguous.

**OD05 — Load shaping policy for L4 window (speedup/shaping)**

* Status: `OPEN`
* Decision: Pin whether `stream_speedup` is used in L4 proving, and the exact shaping parameters.
* Must include: injection path (e.g., `via_IG`), speedup factor(s), burst shaper behavior, and invariants (no metric meaning drift).
* Reason: Any mid-window shaping change forces restart (Section 4.4 / 11.4).

**OD06 — Controlled incident drill set (v0 mandatory drill types)**

* Status: `OPEN`
* Decision: Pin which incident drill(s) are mandatory for `PASS_L4_MIN` and which are required by week for `PASS_L4_STRONG`.
* Candidate drill classes (pick a minimal set and pin it):

  * backlog/lag runaway
  * dependency degradation (partial outage)
  * schema incompatibility / contract breach
  * processor crash loop / restart storm
  * cost anomaly (detection + mitigation)
* Reason: The program requires ≥ 1 drill (MIN) and weekly drills (MAX), but the exact drill types aren’t pinned yet.

**OD07 — Controlled change scope (what counts as a “meaningful” change)**

* Status: `OPEN`
* Decision: Pin the minimum acceptable change scope for L4 proving (e.g., config-only vs deployment vs model/policy promotion).
* Must include: at least one change that exercises rollback readiness in a non-trivial way.
* Reason: Prevents “tiny no-op change” from being used to satisfy the requirement.

**OD08 — Audit drill time-to-answer target**

* Status: `OPEN`
* Decision: Pin an explicit time-to-answer target (even if generous) for `PASS_L4_MIN` and a stronger target for `PASS_L4_STRONG`.
* Reason: Section 10 requires measurement; without a target, “good enough” becomes subjective.

**OD09 — Provenance completeness sampling size (`N`) and acceptance threshold**

* Status: `OPEN`
* Decision: Pin `N` (how many decisions/events to sample per audit drill) and a minimum acceptable completeness %.
* Reason: Prevents cherry-picking one perfect record and calling provenance “complete.”

**OD10 — SLO thresholds for L4 (availability/latency/error/lag)**

* Status: `OPEN (unless already pinned by production-ready authority)`
* Decision: Pin which SLOs are enforced during proving and what constitutes an L4-disqualifying sustained breach vs a remediable incident.
* Reason: L4 requires SLO posture + error budget thinking; the posture must be concrete.

**OD11 — Error budget model (minimal v0)**

* Status: `OPEN`
* Decision: Pin the minimal error budget representation used during proving (e.g., daily burn indicator + cumulative burn), and what burn patterns trigger escalation.
* Reason: “Error budget posture” must be more than a phrase.

**OD12 — Alert severity thresholds (SEV0/SEV1/SEV2 mapping)**

* Status: `OPEN`
* Decision: Pin the thresholds or conditions that classify an event as SEV0 vs SEV1 vs SEV2 for this program.
* Reason: Ensures consistent incident handling and comparable TTD/MTTR evidence.

**OD13 — Budget envelope for the proving window**

* Status: `OPEN`
* Decision: Pin a proving-window budget envelope even if you are willing to spend freely (to prove cost governance).
* Must include: alerting thresholds and “runaway spend” stop triggers.
* Reason: Section 4.8 requires cost posture as part of L4 claimability.

**OD14 — “Stop triggers” / degrade ladder rules during proving**

* Status: `OPEN`
* Decision: Pin when the operator must switch to degrade mode, throttle, or pause stress windows to preserve continuity and safety.
* Reason: Prevents ad-hoc “hero debugging” and proves controlled operations.

**OD15 — Operator access posture (“someone else can operate it”)**

* Status: `OPEN`
* Decision: Pin the minimum access contract: what credentials are required, where the entry points are, and what “operator can take over” means in practice.
* Reason: Section 4.7 requires transferability, but the access contract isn’t yet explicit.

### 12.3 Promotion rule (OPEN → PINNED)

Before starting the L4 proving window, every item marked `OPEN` above MUST either:

* be promoted to `PINNED` in this document, **or**
* be explicitly bound by reference to a stable upstream authority (e.g., `RC2-S`) with the exact identifier recorded at proving start.

Unpinned ambiguity is treated as an evidence integrity risk and will be handled as a blocker if discovered mid-window.

---

## 13. Templates and artifact formats (binding)

This section defines the **required artifact templates** for the L4 proving program. Artifacts MUST be written in these shapes so the evidence pack is consistent, reviewable, and reproducible.

### 13.1 Common header (required in every artifact)

Every artifact MUST begin with the following header block (fields may be null only if explicitly inapplicable):

```yaml
artifact_header:
  proving_window_id: "<PP_...>"
  artifact_type: "<DAILY_OPS_SUMMARY|STRESS_WINDOW|INCIDENT_RECORD|POSTMORTEM|CHANGE_RECORD|AUDIT_DRILL|REMEDIATION_LEDGER|RESTART_DECLARATION|EVIDENCE_PACK_INDEX>"
  created_at_utc: "<YYYY-MM-DDTHH:MM:SSZ>"
  created_by: "<operator_id>"
  scope:
    env: "dev_full"
    claim_boundary: "<via_IG|...>"
  links:
    dashboards:
      first_2_minutes: "<ref>"
      change_incident_timeline: "<ref>"
    runbooks_used: ["RB0", "RB1", "..."]
  integrity:
    metric_definitions_version: "<id>"
    measurement_surfaces_version: "<id>"
    load_policy_version: "<id>"
```

**Rule:** If any of the `integrity.*` versions change during the proving window, a restart is required (per Section 11.4).

---

### 13.2 Daily ops summary (required once per day)

```yaml
artifact_header: <COMMON_HEADER>

daily_ops_summary:
  day_index: <1..30>
  window_day_utc:
    start_utc: "<...Z>"
    end_utc: "<...Z>"

  health_posture:
    availability:
      observed: "<value>"
      notes: "<short>"
    errors:
      observed_rate: "<value>"
      top_error_classes: ["<class>:<rate>", "..."]
    latency:
      p95_ms: "<value>"
      p99_ms: "<value>"
    lag_backlog:
      p95: "<value>"
      p99: "<value>"
      checkpoint_health: "<ok|degraded|failed>"
    cost:
      spend_delta_usd: "<value>"
      unit_cost_value: "<value>"
      unit_cost_definition: "<e.g. USD_per_1M_events>"

  program_events_today:
    stress_windows: ["SW_<id_1>", "SW_<id_2>"]
    incidents: ["INC_<id_...>"]
    controlled_changes: ["CHG_<id_...>"]
    audit_drills: ["AUD_<id_...>"]

  blockers:
    opened_today: ["BLK_<id_...>"]
    closed_today: ["BLK_<id_...>"]
    open_blockers_total: <int>

  remediation_ledger_status:
    open: <int>
    in_progress: <int>
    done_unverified: <int>
    verified: <int>

  operator_notes:
    - "<what happened / what you did / why>"
```

---

### 13.3 Stress window record + scorecard (required per stress window)

```yaml
artifact_header: <COMMON_HEADER>

stress_window:
  stress_window_id: "SW_<id>"
  scheduled: true
  timestamps_utc:
    start_utc: "<...Z>"
    end_utc: "<...Z>"

  declared_targets:
    steady_rate_eps: "<RC2-S.steady_rate_eps>"
    burst_rate_eps: "<RC2-S.burst_rate_eps>"
    steady_duration: "<RC2-S.steady_duration>"
    burst_duration: "<RC2-S.burst_duration>"
    recovery_bound: "<RC2-S.recovery_bound>"

  observed_results:
    steady:
      achieved_rate_eps: "<value>"
      latency_p95_ms: "<value>"
      latency_p99_ms: "<value>"
      error_rate: "<value>"
      lag_p95: "<value>"
      lag_p99: "<value>"
    burst:
      achieved_rate_eps: "<value>"
      latency_p95_ms: "<value>"
      latency_p99_ms: "<value>"
      error_rate: "<value>"
      lag_p95: "<value>"
      lag_p99: "<value>"
    recovery_verification:
      time_to_stable_s: "<value>"
      stable_criteria_met: true|false
      notes: "<short>"

  adjudication:
    pass: true|false
    failed_thresholds: ["<name>", "..."]
    artifacts:
      metrics_snapshot_refs: ["<ref>", "..."]
      logs_refs: ["<ref>", "..."]
```

---

### 13.4 Incident record (live log) — required per incident/drill

```yaml
artifact_header: <COMMON_HEADER>

incident_record:
  incident_id: "INC_<id>"
  incident_kind: "<CONTROLLED_DRILL|UNPLANNED>"
  severity: "<SEV0|SEV1|SEV2|SEV3>"
  declared_at_utc: "<...Z>"
  detected_at_utc: "<...Z>"
  acknowledged_at_utc: "<...Z>"
  mitigated_at_utc: "<...Z>"
  recovered_at_utc: "<...Z>"
  verified_stable_at_utc: "<...Z>"

  drill_injection:
    planned: true|false
    injection_method: "<what you broke>"
    injection_receipt_ref: "<ref>"

  timings:
    ttd_seconds: "<value>"
    ttdiag_seconds: "<value>"
    mttr_seconds: "<value>"

  impact_summary:
    slo_breach: true|false
    key_metrics_delta:
      error_rate: "<before->after>"
      latency_p99_ms: "<before->after>"
      lag_p99: "<before->after>"
      cost_spend_rate: "<before->after>"

  actions_taken:
    - at_utc: "<...Z>"
      action: "<throttle|degrade|rollback|restart|scale|...>"
      reason: "<short>"
      evidence_refs: ["<ref>", "..."]

  outcome:
    stabilized: true|false
    notes: "<short>"
    postmortem_id: "PM_<id>"   # must be created later
    remediation_ids: ["REM_<id>", "..."]
```

---

### 13.5 Postmortem — required per incident/drill used for learning

```yaml
artifact_header: <COMMON_HEADER>

postmortem:
  postmortem_id: "PM_<id>"
  incident_id: "INC_<id>"
  summary: "<one paragraph>"
  impact:
    what_broke: "<short>"
    user/platform_effect: "<short>"
    slo_impact: "<short>"
    error_budget_impact: "<short>"

  timeline:
    - at_utc: "<...Z>"
      event: "<detect|ack|diagnose|mitigate|recover|verify>"
      notes: "<short>"

  root_cause:
    primary: "<short>"
    contributing_factors: ["<short>", "..."]
    evidence_refs: ["<ref>", "..."]

  what_worked:
    - "<short>"
  what_didnt:
    - "<short>"

  remediation_plan:
    - remediation_id: "REM_<id>"
      action: "<short>"
      expected_effect_metric: "<metric>"
      priority: "<P0|P1|P2>"
      status: "<OPEN|IN_PROGRESS|DONE|VERIFIED>"
      verification_plan: "<how it will be verified>"

  runbook_dashboard_updates:
    runbooks_updated: ["RBx@<rev>", "..."]
    dashboards_updated: ["<dash>@<rev>", "..."]
```

---

### 13.6 Remediation ledger (single consolidated list, required)

```yaml
artifact_header: <COMMON_HEADER>

remediation_ledger:
  items:
    - remediation_id: "REM_<id>"
      source_type: "<INCIDENT|AUDIT|CHANGE|OBSERVABILITY>"
      source_id: "<INC_x|AUD_x|CHG_x>"
      created_at_utc: "<...Z>"
      description: "<short>"
      priority: "<P0|P1|P2>"
      status: "<OPEN|IN_PROGRESS|DONE|VERIFIED>"
      done_evidence_refs: ["<ref>", "..."]
      verification_evidence_refs: ["<ref>", "..."]
```

---

### 13.7 Controlled change record (required per change)

```yaml
artifact_header: <COMMON_HEADER>

change_record:
  change_id: "CHG_<id>"
  change_kind: "<DEPLOYMENT|CONFIG|POLICY|MODEL|SCALING|OTHER>"
  declared_at_utc: "<...Z>"
  executed_at_utc: "<...Z>"
  verified_at_utc: "<...Z>"

  intent: "<short>"
  expected_impact: "<short>"
  rollback_plan: "<short>"

  verification:
    pre_metrics_snapshot_ref: "<ref>"
    post_metrics_snapshot_ref: "<ref>"
    verification_notes: "<short>"
    rollback_readiness_proof_ref: "<ref>"

  adjudication:
    pass: true|false
    notes: "<short>"
```

---

### 13.8 Audit drill artifact (required per audit)

```yaml
artifact_header: <COMMON_HEADER>

audit_drill:
  audit_id: "AUD_<id>"
  declared_at_utc: "<...Z>"
  completed_at_utc: "<...Z>"
  time_to_answer_seconds: "<value>"

  target_slice:
    type: "<BASELINE|STRESS_WINDOW|INCIDENT_ADJACENT>"
    ids_or_range: "<ids/time range>"

  questions_answered:
    what_happened: "<answer>"
    why: "<answer>"
    version_responsible:
      policy_or_model_id: "<id>"
      config_id: "<id>"
      deployment_id: "<id>"
    inputs_used:
      payload_signature: "<id>"
      schema_version: "<id>"
      feature_refs: ["<ref>", "..."]
    what_changed_nearby: "<answer>"
    reproducibility: "<how another operator repeats this>"

  evidence_sources:
    - "<ref>"
    - "<ref>"

  provenance_sampling:
    sample_size_n: <int>
    completeness_percent: "<value>"
    missing_link_types: ["<type>", "..."]
    remediation_ids: ["REM_<id>", "..."]
```

---

### 13.9 Restart declaration (required whenever restart is triggered)

```yaml
artifact_header: <COMMON_HEADER>

restart_declaration:
  restart_id: "RST_<id>"
  trigger_time_utc: "<...Z>"
  reason_family: "<METRIC_MEANING_DRIFT|LOAD_POLICY_DRIFT|EVIDENCE_INTEGRITY_LOSS|UNDECLARED_MATERIAL_CHANGE|STOP_THE_WORLD|OTHER>"
  description: "<short>"
  impacted_sections: ["4.4", "6.2", "11.4", "..."]
  blockers_opened: ["BLK_<id>", "..."]
  next_steps: "<remediation plan summary>"
```

---

### 13.10 Evidence pack index (required at day-7 and day-30)

```yaml
artifact_header: <COMMON_HEADER>

evidence_pack_index:
  checkpoint: "<DAY_7|DAY_30>"
  proving_window_span_utc:
    start_utc: "<...Z>"
    end_utc: "<...Z>"

  artifacts:
    daily_ops_summaries: ["DOS_<day1>", "..."]
    stress_windows: ["SW_<id>", "..."]
    incidents: ["INC_<id>", "..."]
    postmortems: ["PM_<id>", "..."]
    changes: ["CHG_<id>", "..."]
    audits: ["AUD_<id>", "..."]
    remediation_ledger_ref: "<ref>"
    dashboards_export_refs: ["<ref>", "..."]
    alerts_export_refs: ["<ref>", "..."]

  final_verdict:
    verdict: "<PASS_L4_MIN|PASS_L4_STRONG|HOLD_REMEDIATE|FAIL>"
    open_blockers: <int>
    blocker_ids: ["BLK_<id>", "..."]
    notes: "<short>"
```

---
