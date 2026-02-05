# Case + Labels Flow (human truth loop) Pre-design Decisions (Open to adjustment where necessary)
_As of 2026-02-05_

Here are the **designer questions I’d want settled** for the Case + Labels (human truth loop) plane so it’s implementable without drift, and so it stays consistent with your upstream discipline (by-ref evidence, append-only, idempotent, provenance, AL owns effects).

I’m grouping by the few decisions that most often cause rework.

---

## P0 — Must settle before you plan/build

### 1) What is the **case identity** (CaseSubjectKey) and when do we merge?

* What is the canonical subject for a case: `decision_id`, `flow_id`, `event_id`, `(platform_run_id, event_class, event_id)`, or entity-level (account/party)?
* When multiple triggers arrive (decision + later action failure + anomaly), do they attach to **one case** or spawn multiple?
* Do we allow merges in v0, or explicitly **no merges** (recommended for v0 unless you need it)?

Detailed answers (recommended defaults, based on current implementation posture):
- CaseSubjectKey = `(platform_run_id, event_class, event_id)` as the canonical default. This aligns with the upstream dedupe tuple and keeps joins deterministic.
- Multiple triggers referencing the same CaseSubjectKey attach to **one case** (append-only timeline events), not new cases.
- v0 policy: **no merges**. If cross-entity aggregation is needed later, add an explicit meta-case type rather than silent merges.
- Pin (P0): `case_id = hash(CaseSubjectKey)`; case creation is idempotent on CaseSubjectKey alone. Triggers become timeline events (deduped), not new cases.

### 2) What is the **case trigger artifact** CM consumes?

You say CM consumes DLA + AL outcomes “by-ref.” Pin one ingestion shape:

* **Option A:** CM consumes `CaseTrigger` events (produced by RTDL/AL or a small “case trigger writer”).
* **Option B:** CM directly consumes DLA decisions + AL outcomes and derives triggers internally.

This affects idempotency keys, replay, and observability.

Detailed answers (recommended defaults, based on current implementation posture):
- Choose **Option A**: CM consumes explicit `CaseTrigger` events (from RTDL/DLA/AL or a thin trigger writer).
- CaseTrigger carries ContextPins, CaseSubjectKey, evidence refs (decision_id, action_outcome_id, audit_record_id), and a stable idempotency key.
- This keeps CM opaque and idempotent, and avoids CM parsing multiple upstream streams directly.

### 3) What is the **idempotency key** for case creation and timeline append?

* Case create dedupe: what exactly is the key?
* Timeline append dedupe: what exactly is the key per event type?

* Suggested: `(case_id, timeline_event_type, source_ref_id)`
* Collision rule: what happens if the same dedupe key arrives with different payload (anomaly/quarantine)?

Detailed answers (recommended defaults, based on current implementation posture):
- Case create dedupe key: `CaseSubjectKey` only (aligned to `case_id = hash(CaseSubjectKey)`); trigger refs create timeline events, not new cases.
- Timeline append dedupe key: `(case_id, timeline_event_type, source_ref_id)` as the default.
- Collision rule: same dedupe key with different payload => **ANOMALY + reject/flag** (no silent overwrite).

### 4) What is the **evidence reference contract** (what refs exist and how they resolve)?

* What’s the stable reference format for:

  * `audit_record_id` (DLA)
  * `decision_id`
  * `action_outcome_id`
  * EB `origin_offset` basis
* Does CM store only refs + small metadata, or does it store partial snapshots?
* What is the v0 rule for access/redaction (even if simple)?

Detailed answers (recommended defaults, based on current implementation posture):
- CM stores **refs + minimal metadata only**. No authoritative payload snapshots inside CM.
- Required ref types: `audit_record_id` (DLA), `decision_id`, `action_outcome_id`, and EB `origin_offset` basis.
- Access posture: refs resolve through RBAC-gated services; CM UI can show redacted previews but not store payload truth.

### 5) What is the **ActionIntent contract** between CM and AL?

You already pinned “CM never performs side effects.” Now settle:

* ActionIntent schema: minimal fields (`intent_type`, `subject_key`, `reason`, `requested_by`, refs)
* Idempotency key for ActionIntent (so repeated clicks don’t duplicate)
* How outcomes attach back to the case timeline (which ref is authoritative)

Detailed answers (recommended defaults, based on current implementation posture):
- Minimal ActionIntent fields: `intent_type`, `subject_key`, `requested_by`, `reason`, ContextPins, and `evidence_refs[]`.
- Idempotency key: `hash(case_id + source_case_event_id + intent_type + subject_key)` (stable per request).
- Outcomes attach via **action_outcome_id** from AL/DLA; CM records the outcome as a timeline event with by-ref evidence.

### 6) What is the **label subject key** (LabelSubjectKey) for learning?

This is the most important label decision.

* Are labels attached to: `event_id` (transaction), `flow_id`, `account_id`, `party_id`, `merchant_id`, or a composite?
* If multiple, which is **primary** for training? (v0 should pick one primary to avoid ambiguity.)

Detailed answers (recommended defaults, based on current implementation posture):
- Primary LabelSubjectKey = `(platform_run_id, event_id)` for v0 (execution-scoped labels; no cross-run leakage).
- Other identifiers (flow_id/account_id/party_id) may be carried as metadata but are not training-primary in v0.

### 7) How do we model **effective_time vs observed_time**, and what is “truth” at query time?

* What’s the rule for late labels (chargeback arrives weeks later)?
* Do we maintain a resolved view (latest assertion with precedence), or is the timeline the only interface?
* If investigators “correct” a label, what precedence rules apply?

Detailed answers (recommended defaults, based on current implementation posture):
- Label Store is append-only timeline truth. A resolved view is derived as “latest by observed_time with explicit precedence rules.”
- Late labels are accepted; effective_time captures when it was true, observed_time captures when it was learned.
- Corrections are new assertions; precedence order: human > external feed > automated, then observed_time, then assertion_id.

### 8) Where is the **writer boundary** for Label Store?

Decide one:

* **Option A:** LabelAssertions go through **IG** as an event class/topic; Label Store consumes from EB.
* **Option B:** Label Store has its own IG-equivalent ingress (HTTP writer boundary).

Both work, but mixing both creates drift fast.

Detailed answers (recommended defaults, based on current implementation posture):
- Choose **Option B**: Label Store owns its own writer boundary (IG-equivalent ingress).
- IG/EB can carry label signals as control-plane events, but authoritative label truth writes only at Label Store.
- Pin (P0): Label Store writer enforces idempotency + payload_hash anomaly detection and returns a durable ack/ref only after commit (WAL flushed). CM emits `LABEL_ACCEPTED` only on that ack.

### 9) What is the **commit/ack point** for “label truth emitted”?

You said CM can’t claim label truth until append succeeds—great. Now pin:

* What constitutes “append succeeds” (durable commit/WAL flushed)?
* What does CM do on failure (retry policy, UI state, timeline markers)?
* How are retries idempotent (assertion_id / dedupe key)?

Detailed answers (recommended defaults, based on current implementation posture):
- Commit/ack point = durable append in Label Store (WAL flushed / transaction committed).
- CM records `LABEL_PENDING` then `LABEL_ACCEPTED`/`LABEL_REJECTED`. If Label Store is down, CM remains pending and retries with backoff.
- Idempotency key = `label_assertion_id` derived from a stable CM source (`case_timeline_event_id`) + `LabelSubjectKey` + `label_type`. `observed_time` is fixed at assertion creation and reused on retries.

---

## P1 — Settle soon (affects ops and scale, but not blocking)

### 10) Case SLA posture and backlog

* Is CM allowed to lag behind RTDL (yes), and what’s acceptable lag?
* How do you prioritize cases (severity from decision reasons, anomaly flags, merchant risk)?

Detailed answers (recommended defaults, based on current implementation posture):
- CM can lag RTDL; v0 target is hours-to-days, not real-time. Backlog is acceptable but visible.
- Prioritization order: DF severity/reason codes + anomaly flags + merchant risk tier; ties by observed_time.

### 11) Reconciliation & audit completeness

* What run-level counters do we expect:

  * decisions emitted → cases created → labels asserted → labels accepted
* Where is the reconciliation report written (object store run folder)?

Detailed answers (recommended defaults, based on current implementation posture):
- Required counters: decisions_emitted -> case_triggers -> cases_created -> action_intents -> outcomes_attached -> label_assertions -> labels_accepted/labels_rejected.
- Reconciliation report location: `s3://fraud-platform/{platform_run_id}/case_labels/reconciliation/YYYY-MM-DD.json`.

### 12) Security & governance basics

* Who can view what evidence refs?
* How are investigator actions authenticated and attributed (actor_id)?

Detailed answers (recommended defaults, based on current implementation posture):
- Evidence refs are visible broadly; resolving refs requires RBAC-gated access (least-privilege).
- Every CM timeline event carries actor_id (human or system) + observed_time; label assertions include actor provenance.

---

## Additional

Not the only ones — the list I gave was the **core “correctness + determinism”** set. For this plane, there are a few other angles worth settling so you don’t get surprised later (even in v0):

### 1) External truth ingestion

* Will **chargebacks / confirmed fraud feeds / customer disputes** come in via CM, via Label Store directly, or via IG/EB?
* What’s the **idempotency key** for those external signals, and how do they map to your LabelSubjectKey?

Detailed answers (recommended defaults, based on current implementation posture):
- v0 posture: external outcomes enter **CM workflow first** and emit LabelAssertions to Label Store (CM remains the human truth workflow).
- Optional later: a dedicated external label ingest can write directly to Label Store, but must follow the same assertion contract and idempotency rules.
- Idempotency key: `hash(external_source + external_reference_id + label_subject_key)`; `observed_time` is a field set at first sighting and does not participate in dedupe.
- Mapping to LabelSubjectKey: use event_id when available; otherwise hold in CM until resolved to a deterministic subject.

### 2) Human workflow semantics

* Do you need **assignment/ownership**, **case locking**, and **concurrent edits** rules in v0?
* What’s the SLA posture (case backlog OK, but how do you prioritize)?

Detailed answers (recommended defaults, based on current implementation posture):
- v0: assignment/ownership supported as timeline-derived fields; no hard locks. Concurrent edits are allowed (append-only timeline).
- SLA posture: backlog acceptable; prioritize by DF severity/reason codes + anomaly flags + merchant risk tier.

### 3) Privacy + evidence access

* What does CM actually store/render: **refs only**, or some redacted preview?
* Who can resolve refs (RBAC), and do evidence refs expire / require signed access?

Detailed answers (recommended defaults, based on current implementation posture):
- CM stores **refs only**; UI may render redacted previews via RBAC-gated resolution service.
- Evidence resolution requires RBAC; prefer short-lived signed access for object store refs.
- Evidence refs do not expire in CM, but access is time-bound and audited.

### 4) CM ↔ Label Store handshake states

* What are the explicit statuses CM records for a label attempt: `PENDING → ACCEPTED/REJECTED → RETRIED`?
* If Label Store is down, how do you represent “investigation complete but label not yet committed”?

Detailed answers (recommended defaults, based on current implementation posture):
- CM records label lifecycle events on the case timeline: `LABEL_PENDING`, `LABEL_ACCEPTED`, `LABEL_REJECTED`, `LABEL_RETRYING`.
- If Label Store is down, CM marks `LABEL_PENDING` and continues investigation; label truth is only declared on ACCEPTED.

### 5) Label “resolution” rules

Even with append-only timelines, consumers need a resolved view:

* How do you resolve **conflicting assertions** (source precedence? latest observed_time? confidence)?
* Do you support “soft labels” / confidence scores in v0, or only hard labels?

Detailed answers (recommended defaults, based on current implementation posture):
- Label Store remains the append-only source of truth; a resolved view is derived as latest by observed_time with explicit precedence.
- Precedence order: human investigator > external feed > automated, then observed_time, then assertion_id.
- v0 supports hard labels plus optional confidence; confidence does not override precedence.
- Pin (P0): `source_type` is explicit (`HUMAN|EXTERNAL|AUTO`) and `actor_id` is required for HUMAN assertions.
- Pin (P0): resolved views are computed per `(LabelSubjectKey, label_type)`; never resolve across label types.

### 6) Backfill + replay behavior

* If you replay archived events and regenerate decisions, do you regenerate cases/labels, or treat CM/LS as **separate human truth** that never rewinds?
* If historic labels arrive late, how are they applied without breaking “what did we know then?”

Detailed answers (recommended defaults, based on current implementation posture):
- CM/Label Store are human truth and **never rewind**; replays do not regenerate cases/labels.
- Late labels are appended with their own effective_time/observed_time; historical views use observed_time to preserve what was known at the time.

### 7) Retention + deletion

* Case timelines and label timelines can be long-lived. What’s the **retention** and **redaction/deletion** policy (even if simple in v0)?

Detailed answers (recommended defaults, based on current implementation posture):
- v0 retention: long-lived (multi-year) for case and label timelines; environment policies can shorten in dev.
- Deletion/redaction is append-only: use redaction/tombstone assertions rather than destructive deletes.

### 8) Observability + reconciliation

* What are the must-have counters: `decisions → case_triggers → cases_created → action_intents → outcomes → label_assertions → labels_accepted`?
* Where does the run-level reconciliation report live?

Detailed answers (recommended defaults, based on current implementation posture):
- Must-have counters: decisions -> case_triggers -> cases_created -> action_intents -> outcomes_attached -> label_assertions -> labels_accepted/labels_rejected.
- Reconciliation report location: `s3://fraud-platform/{platform_run_id}/case_labels/reconciliation/YYYY-MM-DD.json`.
