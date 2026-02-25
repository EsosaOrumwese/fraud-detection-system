# Cluster 9 - Round 1 Answers

## Q1) Define your "truth model" in one paragraph

My truth model is operational and owner-scoped: **Case Mgmt owns append-only case timeline truth**, **Label Store owns append-only label timeline truth**, and **Decision Log Audit owns append-only audit truth** (canonical records plus append-only quarantine for non-admissible lineage); corrections never overwrite prior truth, they append new events/records with explicit supersedes linkage, and retries/replays converge through idempotency rather than creating new truth rows. What can be rebuilt or replaced are **derived surfaces** only (indexes, read models, queue/search projections, export helpers, pointer events), because they are convenience/query layers, not authoritative state; if a derived artifact is digest-bound, rebuild produces a new artifact/ref instead of mutating the old one. In practice, “truth” means that for any decision/case/label claim, I can reconstruct a deterministic chain from immutable, run-scoped records using pinned IDs/provenance (ContextPins, decision/action IDs, audit refs, case timeline events, label assertions with observed/effective time), with explicit conflict/quarantine outcomes rather than silent interpretation.

## Q2) What are the lanes/stores involved (names in your system)?

At this layer, I use four explicit lanes with hard ownership boundaries.

### 1) Decision lane (`DL/DF/AL -> DLA`)

1. **`degrade_ladder` (`DL`)**: posture/governance lane (for decision posture state and degradations).
2. **`decision_fabric` (`DF`)**: emits `decision_response` records and decision lineage refs.
3. **`action_layer` (`AL`)**: emits `action_intent` and `action_outcome` records under idempotent execution rails.
4. **`decision_log_audit` (`DLA`)**: consumes decision-lane lineage events and is the audit truth writer.

Primary decision/audit stores:

1. DLA canonical truth store (today, local_parity anchor run) is DB-backed:
   - `dla_audit_index` (audit identity + digest + object_ref pointer),
   - lineage/intake tables (`dla_intake_candidates`, `dla_intake_quarantine`, `dla_intake_checkpoints`, `dla_intake_attempts`, `dla_lineage_chains`, `dla_lineage_intents`, `dla_lineage_outcomes`).
2. Optional DLA object export surface (contracted path shape, not required for closure on this retained run):
   - `decision_log_audit/records/<audit_id>.json`.
3. DLA derived/query surfaces:
   - `dla_audit_index` (query/index surface),
   - run-level observability artifacts (`metrics`, `reconciliation`, `health`) used for closure evidence.
4. AL local ledgers:
   - `al_intent_ledger`, `al_semantic_ledger`, `al_outcomes_append`, `al_outcome_publish`.

This lane answers: what was decided, what was attempted, what outcome happened, and what immutable audit record proves it.

### 2) Case lane (`CaseTrigger -> CaseMgmt`)

1. **`case_trigger`**: converts decision/audit/outcome evidence into case-trigger envelopes (`event_type=case_trigger`), replay-safe.
2. **`case_mgmt`**: case-system-of-record for append-only case timeline truth.

Primary case stores:

1. Case trigger replay/publish/checkpoint surfaces:
   - `case_trigger_replay_ledger`,
   - `case_trigger_payload_mismatches`,
   - `case_trigger_publish`,
   - `case_trigger_checkpoint_tokens`.
2. Case management truth and handshake surfaces:
   - `cm_cases`,
   - `cm_case_timeline`,
   - `cm_case_timeline_stats`,
   - `cm_case_timeline_links`,
   - `cm_case_trigger_intake`,
   - `cm_case_trigger_mismatches`,
   - `cm_action_intents`,
   - `cm_label_emissions`,
   - `cm_evidence_resolution_requests`,
   - `cm_evidence_resolution_events`.

This lane answers: why was this case opened, what investigation steps happened, and what label/action requests were issued from that case timeline.

### 3) Label lane (`Label Store`)

1. **`label_store`** is the only label truth writer.
2. It stores label assertions and the resolved append-only timeline view; it also exposes as-of and slice surfaces for learning joins.

Primary label stores:

1. `ls_label_assertions` (assertion ledger),
2. `ls_label_timeline` (append-only timeline truth surface),
3. `ls_label_assertion_mismatches` (conflict/replay mismatch diagnostics).

Primary label artifacts:

1. `assertion_ref` path shape is deterministic:
   - `runs/fraud-platform/<platform_run_id>/label_store/assertions/<label_assertion_id>.json`
   - this is a logical reference contract in the writer boundary.
2. Bulk slice artifacts are optional exports for OFS/MF joins:
   - `runs/fraud-platform/<platform_run_id>/label_store/slices/resolved_as_of_<basis_digest16>_<slice_digest16>.json`
3. Truth boundary for the anchor run: retained closure evidence in this run is DB-backed metrics/reconciliation/health plus governance append logs; assertion/slice object exports were not materialized in the retained local artifact tree.

This lane answers: what label truth exists for a subject at a specific as-of boundary, and what assertion chain created it.

### 4) Audit/governance append lane (cross-cutting)

1. **DLA canonical/quarantine append surfaces** are the main audit truth lane for decision causality.
2. **Component governance append logs** exist for case/label operations:
   - `case_mgmt/governance/events.jsonl`,
   - `label_store/governance/events.jsonl`.
3. Reconciliation/health artifacts are emitted per component (`metrics`, `health`, `reconciliation`) and then folded into run-level reporting.

This lane answers: are the truth writers healthy, are anomalies explicit, and can an operator prove closure without mutating truth.

## Q3) What is the writer map at this layer, and what prevents accidental multi-writer drift?

I enforce writer ownership by **component boundary + contract validation + idempotent/immutability constraints**.

### 1) Decision/Audit writer map

1. **DF/AL write decision lineage events to traffic bus** (`decision_response`, `action_intent`, `action_outcome`).
2. **DLA is the only writer of audit truth artifacts**:
   - canonical DB truth (`dla_audit_index`, `dla_intake_*`, `dla_lineage_*`),
   - optional object export path shape under `decision_log_audit/records/<audit_id>.json` when export surface is enabled/materialized.

Drift prevention:

1. DLA intake policy allowlists admissible event families and schema versions (non-allowlisted traffic is not canonicalized into audit truth).
2. DB/index writer is append-only by digest: existing `audit_id` with same digest => `DUPLICATE`, different digest => `HASH_MISMATCH`.
3. When object export is enabled, object writer applies same law on path+digest (no overwrite).
4. `audit_id` is primary-key constrained in index storage.

Result: no second writer can silently replace an existing audit record for the same identity.

### 2) Case writer map

1. **CaseTrigger worker** writes case-trigger replay/publish/checkpoint ledgers.
2. **CaseMgmt intake** is the writer for case truth tables:
   - `cm_cases`,
   - `cm_case_timeline`,
   - `cm_case_timeline_stats`,
   - `cm_case_timeline_links`,
   - plus mismatch ledgers.
3. **CaseMgmt handshakes** (`action_handshake`, `label_handshake`, evidence resolver) write handshake-specific ledgers, but timeline truth still appends through the same CM timeline path.

Drift prevention:

1. CM worker only accepts `event_type=case_trigger` on its intake path; foreign event families are rejected.
2. Case IDs and timeline IDs are deterministic and contract-validated before write.
3. `cm_case_timeline` enforces:
   - primary key `case_timeline_event_id`,
   - uniqueness on `(case_id, timeline_event_type, source_ref_id)`.
4. Replay with identical payload hash increments replay counters; payload drift increments mismatch counters and is surfaced explicitly, not overwritten.

Result: retries converge; conflicting payloads are visible anomalies, not hidden timeline mutations.

### 3) Label writer map

1. **LabelStore writer boundary** is the only writer for label truth ledgers:
   - `ls_label_assertions`,
   - `ls_label_timeline`,
   - `ls_label_assertion_mismatches`.
2. **CaseMgmt label handshake** is the authorized case-plane emitter into LabelStore in this flow.

Drift prevention:

1. Label emission policy gates who can emit and what can be emitted:
   - allowed label families,
   - allowed actor ID prefixes,
   - allowed source types.
2. Label contracts enforce deterministic `label_assertion_id`, required pins, and typed evidence refs.
3. Missing evidence refs are rejected.
4. Existing assertion with same payload => replay accept; different payload => explicit `PAYLOAD_HASH_MISMATCH`; incompatible subject tuple => `DEDUPE_TUPLE_COLLISION`.
5. Timeline insert is idempotent (`ON CONFLICT(label_assertion_id) DO NOTHING`), so duplicates cannot fork label history.

Result: only policy-conforming assertions enter label truth, and collisions become explicit rejects.

### 4) Governance/audit append writer map

1. Each component writes its own governance append stream (`.../governance/events.jsonl`) under run scope.
2. Reconciliation/health artifacts are component-owned and then aggregated by reporting.

Drift prevention:

1. Component-local ownership avoids “shared mutable status file” anti-pattern.
2. Derived reports are recomputed from component artifacts, not hand-edited status.

### 5) Important honesty point (so this is interview-safe)

In local parity, writer ownership is enforced primarily by **process boundaries + code contracts + DB constraints**, not by cloud IAM/database role grants.

That is still strong for correctness and replay safety, but it is different from production IAM enforcement.  
During dev migration, the same writer map is carried forward with role-scoped runtime identities so ownership boundaries become infrastructure-enforced as well.

## Q4) What is an as-of view in your system?

In this platform, the strict **as-of view** is defined in the Label Store lane and means:  
"Resolve label truth for a subject using only assertions known by `observed_as_of`."

### 1) What it is indexed by

Single-subject as-of resolution is keyed by:

1. `platform_run_id`,
2. `event_id` (label subject identity),
3. `label_type`,
4. `as_of_observed_time`.

Resolution law:

1. Eligibility filter: assertion is eligible only if `assertion.observed_time <= as_of_observed_time`.
2. Deterministic winner sort key over eligible assertions:
   - highest `effective_time`,
   - then highest `observed_time`,
   - then `label_assertion_id` (stable tie-break).
3. If top-tied assertions disagree on label value, result is explicit `CONFLICT` (not silent precedence).
4. If none are eligible, result is `NOT_FOUND`.
5. If one deterministic value wins, result is `RESOLVED`.

So as-of is not "latest row"; it is a deterministic selection rule with explicit conflict posture.

### 2) Where it is materialized

Primary as-of source:

1. `ls_label_timeline` table (append-only timeline rows with observed/effective time).

Primary API/read surfaces:

1. `label_as_of(...)` for one `(run, event, label_type, as_of)`.
2. `resolved_labels_as_of(...)` for all label types on one subject.

Bulk as-of materialization (for OFS/MF-scale joins):

1. `LabelStoreSliceBuilder.build_resolved_as_of_slice(...)` produces a deterministic slice payload.
2. Artifact export path:
   - `runs/fraud-platform/<platform_run_id>/label_store/slices/resolved_as_of_<basis_digest16>_<slice_digest16>.json`
3. Slice payload carries:
   - `observed_as_of`,
   - `effective_at`,
   - `target_set_fingerprint`,
   - `basis_digest`,
   - `slice_digest`,
   - per-row status (`RESOLVED|CONFLICT|NOT_FOUND`).

### 3) What guarantees it gives

1. **Leakage safety:** future-known labels are excluded by observed-time eligibility.
2. **Determinism:** same timeline + same `as_of` + same target set yields same winners and same slice digest.
3. **Conflict honesty:** disagreement is surfaced as `CONFLICT`, never hidden by implicit overwrite.
4. **Run-scope isolation:** bulk slice builder fails closed if target set mixes multiple `platform_run_id` values.
5. **Immutability of exported slices:** if slice artifact path already exists with different digest, export fails with immutability-violation error (no overwrite).
6. **Rebuildability from truth:** timeline can be rebuilt from assertion ledger deterministically, so as-of results are reproducible from append-only truth.

### 4) Clarification for interview precision

At this layer, "as-of" is a **label-truth query contract**, not a general event-bus offset query.  
Bus offsets and DLA replay checkpoints are separate replay-control surfaces; label as-of is the truth-time resolution surface used for case/learning joins.

## Q5) What are the commit-evidence artifacts for this layer?

I do not treat this as one "green file."  
I treat it as a **closure bundle**: each claim (decision committed, case committed, label committed, audit closed) has required artifacts and explicit pass/fail interpretation.

### 1) What proves "decision chain committed"

Required evidence set:

1. `runs/fraud-platform/<platform_run_id>/obs/platform_run_report.json`
   - `rtdl.decision` > 0 (decision_response evidence seen),
   - `rtdl.outcome` > 0 (action_outcome evidence seen),
   - `rtdl.audit_append` > 0 (DLA append observed).
2. `runs/fraud-platform/<platform_run_id>/decision_log_audit/metrics/last_metrics.json`
   - `metrics.append_success_total` confirms canonical DLA appends happened.
3. `runs/fraud-platform/<platform_run_id>/decision_log_audit/reconciliation/last_reconciliation.json`
   - `reconciliation.lineage.unresolved_total == 0` for closure-grade run acceptance.
4. `runs/fraud-platform/<platform_run_id>/decision_log_audit/health/last_health.json`
   - `health_state = GREEN` for closure; non-GREEN means decision chain is not closure-safe.

Fail-closed interpretation:

1. If event counts exist but `audit_append` is zero, decision activity happened but audit truth did not close.
2. If unresolved lineage is non-zero, decision chain is not closure-safe even when events flowed.

### 2) What proves "cases committed"

Required evidence set:

1. `runs/fraud-platform/<platform_run_id>/case_trigger/reconciliation/reconciliation.json`
   - `totals.published` > 0 proves case-trigger publication happened,
   - `totals.publish_ambiguous == 0` required for clean closure posture.
2. `runs/fraud-platform/<platform_run_id>/case_mgmt/metrics/last_metrics.json`
   - `metrics.cases_created` > 0,
   - `metrics.timeline_events_appended` > 0.
3. `runs/fraud-platform/<platform_run_id>/case_mgmt/reconciliation/last_reconciliation.json`
   - `reconciliation.anomalies_total == 0` for closure-grade acceptance.
4. `runs/fraud-platform/<platform_run_id>/case_mgmt/health/last_health.json`
   - `health_state = GREEN`.

Fail-closed interpretation:

1. Trigger publication alone is not enough; case timeline append evidence must exist.
2. Any mismatch lane/anomaly in reconciliation means case commitment is degraded, not silently accepted.

### 3) What proves "labels committed"

Required evidence set:

1. `runs/fraud-platform/<platform_run_id>/label_store/metrics/last_metrics.json`
   - `metrics.accepted` > 0 for non-empty label runs,
   - `metrics.timeline_rows` > 0 confirms timeline append surface is populated.
2. `runs/fraud-platform/<platform_run_id>/label_store/reconciliation/last_reconciliation.json`
   - `reconciliation.metrics.accepted` and `reconciliation.anomalies_total` provide closure truth.
3. `runs/fraud-platform/<platform_run_id>/label_store/health/last_health.json`
   - `health_state = GREEN` for closure acceptance.
4. Assertion-level evidence refs
   - label timeline rows carry deterministic `assertion_ref` values in truth rows;
   - in the anchor run retained locally, assertion object files were not materialized under `runs/fraud-platform/platform_20260212T085637Z/label_store/assertions/`.

Fail-closed interpretation:

1. Accepted count with anomaly lanes (`PAYLOAD_HASH_MISMATCH`, `DEDUPE_TUPLE_COLLISION`) is not treated as clean closure.
2. Missing evidence refs or assertion mismatch is explicit reject/mismatch posture, not silent overwrite.

### 4) What proves "audit closed"

At this layer, audit close means: **decision/case/label truths all committed and reconciled under one run scope with no open blocker conditions**.

Required evidence set:

1. `runs/fraud-platform/<platform_run_id>/obs/platform_run_report.json`
   - cross-lane summary is present (`ingress`, `rtdl`, `case_labels`),
   - `ingress.publish_ambiguous == 0`,
   - decision and case/label summaries agree with component artifacts.
2. `runs/fraud-platform/<platform_run_id>/obs/environment_conformance.json`
   - conformance result is `PASS`.
3. Component reconciliation/health closure:
   - `decision_log_audit/reconciliation/last_reconciliation.json` + `health/last_health.json`,
   - `case_mgmt/reconciliation/last_reconciliation.json` + `health/last_health.json`,
   - `label_store/reconciliation/last_reconciliation.json` + `health/last_health.json`.
4. Governance append evidence exists for traceability:
   - `case_mgmt/governance/events.jsonl`,
   - `label_store/governance/events.jsonl`.

Fail-closed interpretation:

1. Missing any required artifact means no audit-close claim.
2. Any open ambiguity/unresolved lineage/anomaly blocker means "run executed but audit not closed."
3. I only make the closure claim when all four bundles above are simultaneously true for the same `platform_run_id`.

## Q6) Pick one anchor run and give platform_run_id, root path, and exact decision/case/label evidence paths

I anchor this cluster on the same closure-grade local parity run used in prior certified clusters:

1. `platform_run_id = platform_20260212T085637Z`
2. Local run root: `runs/fraud-platform/platform_20260212T085637Z/`
3. Object-store root shape for same run: `s3://fraud-platform/platform_20260212T085637Z/`

These are the exact paths I use for an audit-style defense.

### 1) Decision output evidence (DL/DF/AL -> DLA)

1. `runs/fraud-platform/platform_20260212T085637Z/obs/platform_run_report.json`
   - run-level decision closure signals: `rtdl.decision`, `rtdl.outcome`, `rtdl.audit_append`.
2. `runs/fraud-platform/platform_20260212T085637Z/decision_log_audit/metrics/last_metrics.json`
   - DLA append and processing counters.
3. `runs/fraud-platform/platform_20260212T085637Z/decision_log_audit/reconciliation/last_reconciliation.json`
   - lineage closure state (`resolved_total`, `unresolved_total`) and anomaly lanes.
4. `runs/fraud-platform/platform_20260212T085637Z/decision_log_audit/health/last_health.json`
   - health-state gate used for closure acceptance.

### 2) Case output evidence (CaseTrigger -> CaseMgmt)

1. `runs/fraud-platform/platform_20260212T085637Z/case_trigger/reconciliation/reconciliation.json`
   - publish outcomes (`published`, `duplicates`, `quarantine`, `publish_ambiguous`).
2. `runs/fraud-platform/platform_20260212T085637Z/case_mgmt/metrics/last_metrics.json`
   - case creation + case timeline append totals.
3. `runs/fraud-platform/platform_20260212T085637Z/case_mgmt/reconciliation/last_reconciliation.json`
   - anomalies and reconciliation totals.
4. `runs/fraud-platform/platform_20260212T085637Z/case_mgmt/health/last_health.json`
   - case-lane health state for gate decisions.
5. `runs/fraud-platform/platform_20260212T085637Z/case_mgmt/governance/events.jsonl`
   - append-only governance/event trail for case-side operations.
6. `runs/fraud-platform/platform_20260212T085637Z/case_labels/reconciliation/case_mgmt_reconciliation.json`
   - case-side contribution artifact folded into cross-lane case/label reconciliation.

### 3) Label output evidence (LabelStore)

1. `runs/fraud-platform/platform_20260212T085637Z/label_store/metrics/last_metrics.json`
   - label acceptance/duplicate/reject/timeline counters.
2. `runs/fraud-platform/platform_20260212T085637Z/label_store/reconciliation/last_reconciliation.json`
   - label anomaly lanes and reconciliation totals.
3. `runs/fraud-platform/platform_20260212T085637Z/label_store/health/last_health.json`
   - label-lane health gate.
4. `runs/fraud-platform/platform_20260212T085637Z/label_store/governance/events.jsonl`
   - append-only label governance trail.
5. `runs/fraud-platform/platform_20260212T085637Z/case_labels/reconciliation/label_store_reconciliation.json`
   - label-side contribution artifact folded into cross-lane case/label reconciliation.

### 4) Cross-lane closure context used with the above outputs

1. `runs/fraud-platform/platform_20260212T085637Z/obs/environment_conformance.json`
2. `runs/fraud-platform/platform_20260212T085637Z/case_labels/reconciliation/2026-02-12.json`

Why these matter: they bind decision/case/label artifacts into one run-scoped closure claim, so I am not proving each lane in isolation and guessing system closure.

## Q7) One real conflict/immutability incident: what happened, how it was detected, what we did, and what changed

### Incident summary

This incident occurred in the DLA append-only audit lane on:

1. `platform_20260212T075128Z` (first failing run),
2. `platform_20260212T084037Z` (repeat failing run of same class),
3. resolved on `platform_20260212T085637Z` (closure-grade pass).

### 1) What attempted to overwrite/duplicate (the conflict class)

Strictly, this was not a naive "same-row overwrite" attempt.  
It was a **causal-chain conflict** in append-only audit truth:

1. action/decision events were being consumed with a first-read posture that could miss earlier chain links when checkpoints were absent,
2. DLA accepted append records but could not fully resolve one lineage chain (`unresolved_total=1`),
3. a permissive system would silently "heal" or reinterpret chain truth; this platform does not do that.

Operationally, this is exactly the class append-only law is designed to catch: **do not mutate truth to hide causality gaps**.

### 2) How it was detected (artifact-level)

Failing-run evidence (`platform_20260212T075128Z`):

1. `runs/fraud-platform/platform_20260212T075128Z/decision_log_audit/reconciliation/last_reconciliation.json`
   - `reconciliation.lineage.unresolved_total = 1`
2. `runs/fraud-platform/platform_20260212T075128Z/decision_log_audit/health/last_health.json`
   - `health_state = AMBER`
   - `health_reasons` includes `UNRESOLVED_AMBER`
3. Same failure class reappeared on
   `runs/fraud-platform/platform_20260212T084037Z/decision_log_audit/reconciliation/last_reconciliation.json`
   with `unresolved_total = 1`.

This is what made it a real incident instead of a one-off noisy metric.

### 3) What the system/operator did

Fail-closed posture was applied:

1. did **not** certify audit closure for the failing runs,
2. treated unresolved lineage as a hard blocker for closure-grade run acceptance,
3. executed recovery as a fresh L2 run (`new platform_run_id`) instead of mutating prior run truth.

### 4) What we changed to make it safe

We changed first-read stream start semantics for run-pinned consumers so they cannot skip historical chain links when no checkpoint exists:

1. DLA Kinesis intake:
   - `src/fraud_detection/decision_log_audit/intake.py`
   - when `checkpoint is None` and `required_platform_run_id` is set, force `start_position = "trim_horizon"`.
2. AL worker consumer:
   - `src/fraud_detection/action_layer/worker.py`
   - same first-read rule under required run pin.

This aligned replay start behavior with append-only audit integrity expectations.

### 5) Proof it passed after remediation

Recovery run (`platform_20260212T085637Z`) evidence:

1. `runs/fraud-platform/platform_20260212T085637Z/decision_log_audit/reconciliation/last_reconciliation.json`
   - `reconciliation.lineage.unresolved_total = 0`
2. `runs/fraud-platform/platform_20260212T085637Z/decision_log_audit/health/last_health.json`
   - `health_state = GREEN`
3. `runs/fraud-platform/platform_20260212T085637Z/obs/platform_run_report.json`
   - includes non-zero `rtdl.audit_append` and cross-lane closure summary.

### 6) Why this is an append-only truth incident (interview-safe framing)

The key point is not "we fixed a metric."  
The key point is: when causal truth was incomplete, the platform **refused to paper over it**, blocked closure, and required a replay-safe run posture that preserves immutable evidence semantics.

## Q8) How reruns interact with truth (same run vs new run) and how contamination is prevented

### 1) What changes when I rerun with the same `platform_run_id` (when allowed)

Same-run rerun is allowed as an **idempotency/replay operation**, not as a way to rewrite history.

What remains stable (authoritative truth):

1. DLA intake candidate identity is run-scoped:
   - primary key `(platform_run_id, event_type, event_id)` in `dla_intake_candidates`.
2. Case truth identity is stable:
   - `cm_cases.case_id` primary key,
   - `cm_case_timeline.case_timeline_event_id` primary key,
   - unique `(case_id, timeline_event_type, source_ref_id)`.
3. Label truth identity is stable:
   - `ls_label_assertions.label_assertion_id` primary key,
   - `ls_label_timeline.label_assertion_id` primary key with `ON CONFLICT DO NOTHING`.

So a same-run replay does not create a second truth row for the same canonical identity.

What can change on same-run rerun:

1. replay counters can increment (`replay_count` style fields),
2. mismatch counters can increment if payload drift is observed (`mismatch_count` lanes),
3. derived observability snapshots (`last_metrics.json`, `last_health.json`, `last_reconciliation.json`) are refreshed.

Important boundary: these are **diagnostic/derived updates** or replay telemetry, not mutation of canonical truth rows.

### 2) What forces a new `platform_run_id`

I mint a fresh run id when I need a new closure claim, not just more processing.

Hard triggers for fresh run scope:

1. closure blocker in current run (example from Q7: DLA `unresolved_total > 0`),
2. any run-defining pin/provenance change (scenario/world/config profile, policy/bundle/run-config basis),
3. any restart/recovery posture where prior checkpoint/offset state could blur audit boundaries,
4. any acceptance rerun intended to produce a certifiable "green" statement.

Practical rule I follow:

1. same-run rerun = replay/idempotency check,
2. fresh run (`L2`) = certification-grade recovery or acceptance.

### 3) How truth contamination is prevented across runs

Contamination prevention is multi-layered, not one control.

Runtime run-scope gates:

1. DLA inlet rejects out-of-scope envelopes via `RUN_SCOPE_MISMATCH` when `required_platform_run_id` is pinned.
2. CaseMgmt worker drops case triggers whose subject run id does not match required run id.
3. LabelStore worker only exports for active/required run scope and resolved scenario scope.

Storage/identity rails:

1. truth tables include run-scoped identity axes (`platform_run_id` in subject keys and lineage tables),
2. append-only writes use deterministic IDs + PK/unique constraints to converge duplicates instead of duplicating truth,
3. mismatch ledgers record drift explicitly instead of mutating prior rows.

Artifact/evidence rails:

1. artifacts are run-rooted (`runs/fraud-platform/<platform_run_id>/...`),
2. cross-lane closure is evaluated against one run root at a time (`obs/platform_run_report.json`, conformance, reconciliation bundle),
3. label bulk as-of slice builder fails closed if target set mixes multiple `platform_run_id` values.

Net effect:

1. reruns are safe under at-least-once delivery,
2. truth remains append-only and run-scoped,
3. cross-run bleed is blocked by runtime gates + key design + artifact scoping, not by operator memory.

## Q9) Audit story: minimum chain I use to answer “why did this case exist / why was this label assigned?”

This is a **causal chain proof**, not a metric screenshot.

Also important: in this baseline, the minimum chain is **hybrid**:

1. authoritative per-entity truth is in CM/LS/DLA stores (tables),
2. run-root artifacts provide closure/audit envelope (`platform_run_report`, conformance, reconciliation).

### A) “Why did this case exist?” - minimum proof chain

For an anchor-run case claim (`platform_20260212T085637Z`), I walk this chain:

1. Case existence and scope
   - `cm_cases` row for `case_id` (contains subject key + run pins).
2. Trigger-to-case causality
   - `cm_case_timeline` for that `case_id`, find `CASE_TRIGGERED` event(s),
   - `source_ref_id` / evidence refs show the case-trigger source.
3. Cross-lane evidence links
   - `cm_case_timeline_links` for the same timeline event:
     - `decision_id`,
     - `action_outcome_id` (when present),
     - `audit_record_id`,
     - `event_id` / `case_trigger_id`.
4. Decision/audit lineage proof
   - query DLA by `decision_id` (via DLA query surface or lineage tables):
     - decision chain status,
     - intent/outcome refs,
     - unresolved reasons (must be empty for closure-grade claim).
5. Run-level closure context
   - `runs/fraud-platform/platform_20260212T085637Z/decision_log_audit/reconciliation/last_reconciliation.json`
   - `runs/fraud-platform/platform_20260212T085637Z/case_trigger/reconciliation/reconciliation.json`
   - `runs/fraud-platform/platform_20260212T085637Z/obs/platform_run_report.json`

That gives me a defensible answer from case row -> timeline event -> linked decision/audit IDs -> closure artifacts.

### B) “Why was this label assigned?” - minimum proof chain

I do not answer from a final label value alone. I prove assertion causality:

1. Label acceptance record
   - `cm_label_emissions` by `label_assertion_id`:
     - `status` (ACCEPTED/REJECTED/PENDING),
     - `source_case_event_id`,
     - `assertion_ref` (logical ref when present).
2. Label timeline and assertion truth
   - `ls_label_timeline` row for `label_assertion_id` (observed/effective + payload hash),
   - `ls_label_assertions.assertion_json` for canonical assertion payload and pins.
3. Link back to case event
   - `cm_case_timeline` row for `source_case_event_id` (`LABEL_ACCEPTED` or related),
   - evidence refs include the originating case event and assertion linkage.
4. Link further back to decision/audit cause
   - from the case timeline links/evidence refs, follow:
     - `decision_id` -> DLA lineage chain,
     - `audit_record_id` -> DLA audit lineage.
5. Run-level closure context
   - `runs/fraud-platform/platform_20260212T085637Z/label_store/reconciliation/last_reconciliation.json`
   - `runs/fraud-platform/platform_20260212T085637Z/case_mgmt/reconciliation/last_reconciliation.json`
   - `runs/fraud-platform/platform_20260212T085637Z/obs/platform_run_report.json` (`case_labels.summary`)

### C) Why this is the minimum credible chain

1. It ties every claim to immutable IDs (`case_id`, `case_timeline_event_id`, `label_assertion_id`, `decision_id`).
2. It uses append-only history and link tables, not mutable status fields.
3. It proves both local causality (case/label rows) and system closure (run artifacts).

If any hop in this chain is missing or contradictory, I do not call the claim audit-closed.

## Recruiter Hardening Pins (Cluster 9)

### 1) Canonical truth location today (DLA / CaseMgmt / LabelStore)

For the certified local-parity anchor run, canonical truth is DB-first with run-scoped closure artifacts:

1. DLA canonical truth: DB tables (`dla_audit_index`, `dla_intake_*`, `dla_lineage_*`) plus run-scoped observability artifacts.
2. CaseMgmt canonical truth: DB tables (`cm_cases`, `cm_case_timeline`, `cm_case_timeline_stats`, `cm_case_timeline_links`, mismatch/intake ledgers).
3. LabelStore canonical truth: DB tables (`ls_label_assertions`, `ls_label_timeline`, `ls_label_assertion_mismatches`).
4. Run-root artifact set (`metrics`, `reconciliation`, `health`, `governance/events.jsonl`) is closure/audit evidence, not the primary mutable truth store.

### 2) Concrete pin for canonical audit object truth (or DB-only status)

Truth status for this retained anchor run is DB-backed + closure artifacts; canonical per-audit object files were not materialized in the retained local run tree.

Concrete closure anchors for audit truth on the anchor run:

1. `runs/fraud-platform/platform_20260212T085637Z/decision_log_audit/reconciliation/last_reconciliation.json`
2. `runs/fraud-platform/platform_20260212T085637Z/decision_log_audit/metrics/last_metrics.json`
3. `runs/fraud-platform/platform_20260212T085637Z/decision_log_audit/health/last_health.json`

Contracted object path shape (when export is enabled/materialized):

1. `runs/fraud-platform/<platform_run_id>/decision_log_audit/records/<audit_id>.json`

### 3) Concrete pin for label assertion/slice artifacts (or truthful downgrade)

Truth status for this retained anchor run is DB-backed + closure artifacts; there are no materialized files under:

1. `runs/fraud-platform/platform_20260212T085637Z/label_store/assertions/`
2. `runs/fraud-platform/platform_20260212T085637Z/label_store/slices/`

Concrete label closure anchors for the anchor run:

1. `runs/fraud-platform/platform_20260212T085637Z/label_store/metrics/last_metrics.json`
2. `runs/fraud-platform/platform_20260212T085637Z/label_store/reconciliation/last_reconciliation.json`
3. `runs/fraud-platform/platform_20260212T085637Z/label_store/health/last_health.json`

Contracted export path shapes (optional surfaces):

1. `runs/fraud-platform/<platform_run_id>/label_store/assertions/<label_assertion_id>.json`
2. `runs/fraud-platform/<platform_run_id>/label_store/slices/resolved_as_of_<basis_digest16>_<slice_digest16>.json`

## Q10) Migration angle: what must remain identical in `dev_min`, and what can change without breaking append-only truth

For this cluster, the migration law is: **change substrate, not truth semantics**.  
If I keep storage/compute services but alter truth laws, I have broken the platform.  
If I change substrate while preserving truth laws, migration is valid.

### 1) Non-negotiable invariants (must remain identical across `local_parity -> dev_min`)

These are closure blockers if violated.

#### A) Append-only law is unchanged

1. No canonical overwrite for decision/case/label truth identities.
2. Same identity + same hash -> converge as replay/duplicate.
3. Same identity + different hash -> explicit mismatch/collision posture (no silent replace).
4. Corrections append new records/events with linkage; they do not mutate historical truth rows.

This applies equally to DLA records, CM timeline truth, and LS assertion/timeline truth.

#### B) Writer ownership map is unchanged

1. DLA remains the audit-truth writer.
2. CaseMgmt remains the case-timeline truth writer.
3. LabelStore remains the label-truth writer.
4. Cross-lane components may emit envelopes/events, but cannot usurp another lane’s truth store.

If migration introduces multi-writer ambiguity, the boundary is broken even if services run.

#### C) Canonical IDs + run-scope pins are unchanged

1. `platform_run_id`, `scenario_run_id`, `event_id`, `decision_id`, `case_id`, `label_assertion_id`, `audit_id` semantics remain stable.
2. Run-scope admission/gating remains fail-closed on run mismatch.
3. Evidence and reconciliation are still evaluated per run root (one closure claim per run scope).

This is required so replay and audit comparisons between local and dev are meaningfully comparable.

#### D) As-of resolution law is unchanged

1. Label as-of still resolves by observed-time eligibility and deterministic tie-break ordering.
2. Conflict posture remains explicit (`CONFLICT`), not policy by silent precedence.
3. Bulk slice exports remain deterministic from the same basis/target set definition.

If as-of semantics drift, learning joins and audit answers become non-reproducible across environments.

#### E) Closure blockers remain fail-closed

1. Unresolved lineage, publish ambiguity, and anomaly blockers still prevent closure-grade claims.
2. “Messages moved” is never sufficient; closure still requires commit-evidence bundles.
3. No single mutable status file becomes authoritative in dev.

If these gates are weakened, migration can produce false-green runs.

### 2) What is allowed to change (without breaking truth semantics)

These are valid migration changes if invariants above remain intact.

#### A) Storage substrate can change

1. Local/Postgres/MinIO-backed surfaces can move to managed RDS/S3-backed surfaces.
2. Table/index physical layout, partitioning, and performance tuning can change.
3. Artifact durability class and retention controls can change.

Allowed condition: canonical IDs, append-only laws, and evidence chain semantics do not change.

#### B) Transport/runtime packaging can change

1. Local daemon process model can move to managed ECS services/tasks.
2. Broker substrate can move from local-compatible setup to managed Kafka/Kinesis posture.
3. Deployment topology, autoscaling envelopes, and restart policies can change.

Allowed condition: idempotency, replay safety, and run-scope gating behavior remain identical.

#### C) Security/control plane can harden

1. IAM role scoping can become stricter than local process boundaries.
2. Secret materialization/injection mechanism can change to managed secret surfaces.
3. Network boundaries and service-to-service auth can tighten.

Allowed condition: hardening must not relax writer ownership or permit cross-run contamination.

#### D) Observability implementation can change

1. Metric/log backends and dashboards can change.
2. Evidence publishing transport can change.
3. Report generation orchestration can change.

Allowed condition: closure-grade artifacts still exist with equivalent claim power.

### 3) Migration-specific anti-drift checks I apply for this cluster

When promoting this layer, I ask four explicit checks:

1. **Truth-law parity check:** does a replay of the same scenario produce the same append-only outcomes (duplicate vs mismatch vs conflict behavior)?
2. **Writer-boundary check:** can any non-owner write owner truth stores in dev? If yes, stop.
3. **Run-scope isolation check:** are out-of-scope run envelopes rejected exactly as in local parity?
4. **Audit-chain reconstructability check:** can I still answer “why case?” and “why label?” from immutable IDs and evidence chain without relying on transient logs?

Any failure means migration posture is not closure-grade for append-only truth, even if infrastructure health looks green.

### 4) Interview-safe summary

For append-only Case/Label/Audit truth, dev migration is successful only if semantics are invariant:

1. same writer map,
2. same append-only/idempotency/conflict laws,
3. same run-scope and as-of semantics,
4. same fail-closed closure criteria,
5. same audit-chain reconstructability.

Everything else (service packaging, managed storage, IAM hardening, transport implementation) is allowed to evolve.
