# Observability + Governance Plane Pre-design Decisions (v0, Open to adjustment where necessary)

_As of 2026-02-05_

This plane defines the **rules and minimum evidence** the platform must emit to remain **debuggable, auditable, and governable** without slowing the hot path. Mechanisms (identity, secrets, network, deployment) live in Run/Operate; this document pins **what must be observed and what must be governed**.

**v0 principle:** prefer **aggregated counters + immutable evidence refs** over verbose per-event logging. Hot path emits **minimal structured facts**; deep forensics are satisfied via **by-ref evidence** already stored in receipts/audit stores/archives.

---

## P0 — Must settle before you plan/build

## 1) v0 goals and non-goals for Observability + Governance

**Questions**

* What must be observable in v0 (minimum viable ops)?
* What must be governed in v0 (minimum viable safety + control)?
* What do we explicitly *not* do in v0 to avoid performance drag?

**Pinned defaults**

* **v0 Observability goal:** detect and localize failures quickly using **(a)** health probes, **(b)** per-component counters, **(c)** run-scoped reconciliation summaries, and **(d)** anomaly events.
* **v0 Governance goal:** enforce and audit lifecycle actions that change platform behavior (bundle promotion, policy changes, label acceptance, ref access).
* **v0 non-goals:** full distributed tracing everywhere, fine-grained per-event logs at high volume, heavy lineage graph computation online, and real-time dashboards that require expensive joins.

---

## 2) Telemetry surfaces and performance budget

**Questions**

* What telemetry surfaces are allowed on the hot path?
* What sampling/throttling rules apply?
* What is the “no unnecessary log computation” rule?

**Pinned defaults**

* Hot path emits **counters** and **bounded structured events only**:

  * Counters: in-memory + periodic flush (e.g., 10–60s) to metrics sink.
  * Structured events: **only** for governance actions and anomalies.
* Per-event logging is prohibited except under:

  * explicit debug mode, or
  * anomaly/quarantine paths (rare by design).
* Sampling is allowed only for **diagnostic-only** telemetry and must be explicit per environment profile.
* Every component must support **run-scoped metric labels**: `platform_run_id`, `scenario_run_id` (and `mode`, `policy_rev` where relevant).

---

## 3) Canonical identifiers and evidence boundary

**Questions**

* What IDs must appear on all observability records?
* What is the evidence boundary for “what happened”?
* How do we avoid cross-run mixing in logs and governance facts?

**Pinned defaults**

* Every observability/governance record must include:

  * `platform_run_id`, `scenario_run_id`
  * `manifest_fingerprint`, `parameter_hash`, `scenario_id`
  * `policy_rev` (or `run_config_digest`) where policy/config matters
* **Evidence boundary**:

  * Online truth: EB **origin_offset** evidence + DLA decision records + AL outcomes
  * Replay truth: Archive origin_offset evidence + DLA + LS timelines
* Any record without `platform_run_id` is **invalid** in v0 (fail closed for governance events; counters may be global only if explicitly configured).

---

## 4) Minimal run-scoped reconciliation (cheap, high value)

**Questions**

* What must we be able to reconcile per run without expensive computation?
* Where is the reconciliation artifact written?
* Who owns producing it?

**Pinned defaults**

* v0 must support a **single run reconciliation JSON** (append-only per run/day), written to:

  * `s3://fraud-platform/{platform_run_id}/obs/reconciliation/YYYY-MM-DD.json`
* Reconciliation is produced by a lightweight “run reporter” job or periodic control-plane writer (not on the hot path).
* Minimum required counters (by topic/class where applicable):

  * **Control & Ingress:** WSP sent, IG received, admitted, duplicate, quarantined, publish_ambiguous, receipts_written, receipt_write_failed
  * **RTDL:** inlet_seen, inlet_deduped, context_updates, flowbinding_writes, join_wait, degraded (by reason), decisions_emitted, actions_requested, actions_outcomes
  * **Case/Labels:** case_triggers, cases_created, timeline_events_appended, labels_pending, labels_accepted, labels_rejected
  * **Learning:** datasets_built, eval_pass, eval_fail, bundles_published, promotions, rollback_events
* Reconciliation always references **evidence refs** (receipt ids / audit ids), never raw payload copies.

---

## 5) Anomaly taxonomy and “fail closed” rules

**Questions**

* What constitutes an anomaly vs an expected condition?
* What is the standard response: warn, quarantine, fail closed?
* Where do anomaly events go?

**Pinned defaults**

* Anomalies are **structured events**, low volume, append-only. They are emitted to:

  * `fp.bus.control.v1` as governance/anomaly facts (or equivalent control stream), and referenced in object store evidence.
* v0 anomaly categories (minimum):

  * `PAYLOAD_HASH_MISMATCH` (same dedupe tuple, different payload_hash)
  * `PUBLISH_AMBIGUOUS` (unknown publish success)
  * `SCHEMA_POLICY_MISSING` / `SCHEMA_INVALID`
  * `REPLAY_BASIS_MISMATCH` (EB vs Archive disagreement)
  * `INCOMPATIBLE_BUNDLE_RESOLUTION` (MPR fail closed)
  * `REF_ACCESS_DENIED` (governance gate)
* Default behavior:

  * **Training datasets:** fail closed on replay anomalies
  * **Governance actions:** fail closed (no silent fallback unless explicitly defined)
  * **Runtime decisioning:** degrade only via explicit degrade policy; never silently “skip checks”

---

## 6) Governance event stream and lifecycle facts (low volume)

**Questions**

* What are the governance facts we must record?
* Which events are required for auditability?
* What is the idempotency rule for governance events?

**Pinned defaults**

* Governance facts are append-only events with deterministic IDs (idempotent under retries).
* Required governance fact types (v0 minimal):

  * Run lifecycle: `RUN_READY_SEEN`, `RUN_STARTED`, `RUN_ENDED`, `RUN_CANCELLED`
  * Registry lifecycle: `BUNDLE_PUBLISHED`, `BUNDLE_APPROVED`, `BUNDLE_PROMOTED_ACTIVE`, `BUNDLE_ROLLED_BACK`, `BUNDLE_RETIRED`
  * Label lifecycle: `LABEL_SUBMITTED`, `LABEL_ACCEPTED`, `LABEL_REJECTED`
  * Access/audit: `EVIDENCE_REF_RESOLVED` (see section 8)
  * Policy/config: `POLICY_REV_CHANGED` (when applicable)
* Every governance event includes:

  * `platform_run_id`, `scenario_run_id` (or explicit “not run-scoped” flag for global registry events)
  * actor attribution: `actor_id` + `source_type` (`HUMAN|SYSTEM`)
  * evidence refs where relevant (manifest refs, eval report refs, decision ids, etc.)
* Idempotency: each governance event has `event_id = hash(event_type + scope_key + primary_ref_id + timestamp_bucket)` (exact construction pinned per event type).

---

## 7) Corridor checks (policy enforcement at the boundaries)

**Questions**

* Where are the enforcement points (corridors)?
* What must be checked at each corridor in v0?
* What is the minimum “corridor check” evidence?

**Pinned defaults**
Corridor checks are enforced at the smallest number of choke points:

* **IG corridor:** producer auth mode, required pins, schema policy, dedupe tuple + payload_hash anomaly, publish state machine.
* **DLA corridor:** append-only decision records must include evidence offsets + policy/bundle refs.
* **AL corridor:** idempotent action execution keyed by decision_id; outcomes recorded append-only.
* **LS corridor:** dedupe tuple + payload_hash anomaly detection; durable ack only after commit.
* **MPR corridor:** promotion/rollback requires governance actor; resolution fails closed on incompatibility.
* **Evidence ref resolution corridor:** “refs visible ≠ refs resolvable”; see section 8.

v0 corridor checks must emit only:

* counters (for monitoring),
* and a structured anomaly/governance event **only on failure** (to avoid noise).

---

## 8) Access governance for evidence refs (security decisions live here)

**Questions**

* Who is allowed to resolve evidence refs (archive, DLA, LS, receipts)?
* What must be logged when a ref is resolved?
* How do we keep this low overhead?

**Pinned defaults**

* Evidence refs can be displayed broadly, but **resolving** a ref requires RBAC-gated access.
* Each ref resolution emits a minimal audit record:

  * `actor_id`, `source_type`, `ref_type`, `ref_id`, `purpose`, `platform_run_id` (if applicable), `observed_time`
* v0 performance rule: ref-resolution audit is **one record per resolution**, not per byte read; do not log payload contents.
* Signed/time-bound access and secrets are substrate concerns; this plane pins only the “who/what/when/purpose must be recorded.”

---

## 9) Registry governance and corridor checks (MPR)

**Questions**

* What is the minimum approval model in v0?
* How are promotions/rollbacks proven and audited?
* How does DF resolution fail closed safely?

**Pinned defaults**

* v0 approval model: explicit governance actor must approve promotion; approvals become registry events.
* `ScopeKey = { environment, mode, bundle_slot, tenant_id? }` and exactly one ACTIVE per scope.
* Deterministic resolution order: tenant-specific ACTIVE → global ACTIVE → explicit safe fallback → fail closed.
* Every resolution failure must emit a structured governance/anomaly fact and be captured in the decision record provenance.

---

## P1 — Settle soon (useful, but not required to start building)

## 10) Distributed tracing and high-cardinality telemetry

* v0: optional and sampled only; do not require cross-service tracing to operate.
* P1: enable end-to-end tracing for a small sampled slice, tied to a trace_id carried in envelopes.

## 11) Advanced lineage graph and compliance exports

* v0: manifests + eval reports + registry events are sufficient lineage.
* P1: build derived lineage graphs offline from those immutable records.

## 12) Automated corridor compliance checks (“corridor checks as code”)

* v0: corridor checks exist as explicit component behaviors.
* P1: formalize them into versioned check suites with PASS/FAIL artifacts.

---

## Summary of v0 “don’t slow the platform” posture

* Hot path: **counters + rare structured anomalies only**
* Deep truth: already lives in **receipts, DLA, archives, LS timelines**
* Governance: **append-only low-volume events** for actions that change state
* Reconciliation: **run-scoped summary jobs**, not continuous heavy computation
