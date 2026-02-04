# Control & Ingress Pre-design Decisions (v0, Open to adjustment where necessary)
_As of 2026-02-04_

Below are the design-level questions to settle for Control & Ingress. Answers are written in the same style as the RTDL pre-design decisions: concise, explicit, and anchored to the current implementation posture.

## A) Control plane authority and run lifecycle

1. **Run identity + activation semantics**

- How is `run_id` generated (collision resistance, monotonicity not required)?
- Where is "active run" stored, and what prevents cross-run mixing?
- Can multiple runs be active concurrently? If so, how do components choose which run(s) to process?

Detailed answers (recommended defaults, based on current implementation posture):
- Scenario `run_id` is deterministic: sha256("sr_run|" + run_equivalence_key) -> 32 hex. The SR equivalence registry rejects conflicting intent fingerprints for the same equivalence key (EQUIV_KEY_COLLISION).
- Platform session run_id is separate: "platform_YYYYMMDDTHHMMSSZ" stored at `runs/fraud-platform/ACTIVE_RUN_ID`, overridable via `PLATFORM_RUN_ID`. This controls run-scoped artifact/log paths, not scenario run selection.
- Multiple scenario runs can be active concurrently. SR uses per-run leases to enforce a single leader for each run_id; WSP consumes READY messages across runs; IG admits all runs based on envelope pins.
- Gaps: IG dedupe key omits run_id; if event_id collides across runs, the later run can be marked DUPLICATE. WSP does not validate READY run_id against the oracle receipt run_id when streaming.

2. **READY event idempotency**

- Can READY be emitted/consumed more than once (retries/restarts)?
- What is the dedupe key for READY consumption (SR and WSP side)?
- If WSP restarts mid-run, does it re-emit the same events (same `event_id`) deterministically?

Detailed answers (recommended defaults, based on current implementation posture):
- READY can be emitted multiple times. SR publishes READY with deterministic message_id = sha256("ready|" + run_id + "|" + (bundle_hash or plan_hash)). Re-emit uses bundle_hash or a hash of run_facts_view if bundle_hash is absent.
- File control bus is idempotent per message_id filename; Kinesis can deliver duplicates. WSP dedupes READY by message_id and skips only if prior status == STREAMED.
- WSP restart uses checkpoint store per (pack_key, output_id). Missing checkpoints cause a replay; event_id stays deterministic, so IG dedupe absorbs duplicates.

3. **Run facts immutability**

- Is `run_facts_view` immutable once written?
- Do you content-hash / include a digest in READY so downstream can validate it did not change?
- If SR is re-run for the same run_id, what happens?

Detailed answers (recommended defaults, based on current implementation posture):
- `run_facts_view` is write-once (write_json_if_absent). If content differs on re-run, SR raises FACTS_VIEW_DRIFT. READY signal is also write-once (READY_SIGNAL_DRIFT).
- READY payload includes facts_view_ref + bundle_hash + optional oracle_pack_ref. There is no explicit run_facts_view digest beyond bundle_hash.
- If the same run_equivalence_key and intent_fingerprint are used, SR reuses the same run_id and artifacts without rewriting. A different intent_fingerprint for the same equivalence key is rejected (EQUIV_KEY_COLLISION).

---

## B) WSP producer correctness under retries/backpressure

4. **Event_id generation and stability**

- Is `event_id` stable across retries (same event, same `event_id`)?
- Does `event_id` incorporate `event_class` implicitly (you now dedupe by `(run_id, event_class, event_id)`, so either is fine)?
- Are you persisting a `payload_hash` at the producer or only at IG?

Detailed answers (recommended defaults, based on current implementation posture):
- event_id is deterministic: sha256 over output_id + primary key values + pins (manifest_fingerprint, parameter_hash, seed, scenario_id). This is derived by `derive_engine_event_id` and fails if any primary key is missing.
- event_class is not part of event_id; event_type == output_id. IG derives event_class later via class_map and dedupes on (event_type, event_id).
- payload_hash is not emitted by WSP and not stored by IG (gap for anomaly detection).
- run_id is included in the envelope but not in event_id; cross-run collisions remain possible if pins + primary keys match.

5. **Retry model (HTTP ingest)**

- How does WSP react to 429/5xx/timeouts?
- Does it resend with the same `event_id`?
- Do you cap retries / exponential backoff?
- What happens on a 4xx schema error: drop/quarantine/stop run?

Detailed answers (recommended defaults, based on current implementation posture):
- WSP performs a single HTTP POST with timeout=30 seconds. Any HTTP >= 400 raises IG_PUSH_FAILED and stops streaming (no retries/backoff).
- Retries are operator-driven (restart WSP). Duplicates are expected and must be deduped by IG.
- 4xx schema/policy errors stop the stream; WSP does not quarantine locally.
- There is no local queue/DLQ. Replay window is defined by the last checkpoint; events after the last checkpoint may be resent on restart.

6. **Time semantics**

- What does "600x speedup" do to `ts_utc` in payload/envelope?
- Are you emitting event_time from the oracle/stream view, or generating new times at emission?
- Do you ever violate event-time ordering within a single output stream (and is that acceptable)?

Detailed answers (recommended defaults, based on current implementation posture):
- WSP uses ts_utc from stream_view rows (oracle/engine time) and does not rewrite it.
- stream_speedup only compresses wall-clock delay between events; it does not change ts_utc.
- Ordering is guaranteed only within each output_id (stream_view sorted by ts_utc, filename, file_row_number). Cross-output ordering is not guaranteed when output concurrency > 1.

---

## C) IG admission pipeline: the real integrity boundary

7. **Admission DB schema + uniqueness guarantees**

- What is the exact unique constraint in the admission DB? (Should match narrative: `(run_id, event_class, event_id)`.)
- Do you store `payload_hash` and enforce anomaly detection (same key, different hash)?
- What is the retention/TTL of admission rows?

Detailed answers (recommended defaults, based on current implementation posture):
- Admissions table is keyed by dedupe_key (PRIMARY KEY). dedupe_key = sha256(event_type + ":" + event_id).
- Stored fields: receipt_ref, eb_topic, eb_partition, eb_offset, eb_offset_kind, eb_published_at_utc.
- No payload_hash; no anomaly detection; no run_id or event_class in the key.
- TTL/retention: none. Rows persist until manually purged.
- Gap: dedupe scope is smaller than (run_id, event_class, event_id) and can mis-dedupe across runs.

8. **Publish atomicity and "unknown success"**

- If IG calls Kinesis and the network drops after PutRecord, you may not know if it succeeded.
- On retry, you can publish duplicates even if admission dedupe already passed (because dedupe happens before publish).

Questions:
- How do you handle "publish status unknown"?
- Do you record publish attempts / sequence numbers in the admission DB?
- Do you ever re-run publish for an already-admitted event?

Detailed answers (recommended defaults, based on current implementation posture):
- Flow is validate -> dedupe lookup -> publish -> receipt -> admission_index.record.
- No explicit handling for unknown success. If publish raises, IG quarantines and does not record dedupe.
- Publish attempts are not recorded as a separate state; only successful publish produces eb_ref + admission row.
- File EB publish fsyncs and is low-risk for unknown success; Kinesis is at-least-once and still vulnerable to unknown success.

9. **Partitioning determinism + join locality guarantees**

- For each event_class, what is the exact partition key derivation?
- For context streams, can you demonstrate that (merchant_id, arrival_seq) is always present and always used?
- For traffic, what is the chosen key today (flow_id?) and is it stable?

Detailed answers (recommended defaults, based on current implementation posture):
- Partitioning uses class_map -> profile_id -> key_precedence (first present value), hashed via sha256.
- control: run_id -> manifest_fingerprint -> event_id.
- audit: event_id -> manifest_fingerprint.
- traffic (baseline/fraud): payload.flow_id -> payload.merchant_id -> payload.account_id -> payload.party_id -> event_id.
- context arrival_events/arrival_entities: payload.merchant_id -> payload.arrival_seq -> event_id.
- context flow_anchor baseline/fraud: payload.flow_id -> payload.merchant_id -> payload.arrival_seq -> event_id.
- If required keys are missing, IG falls back to later keys; if all missing, PARTITION_KEY_MISSING -> quarantine.
- Gap: IG does not enforce payload fields directly; locality relies on payload schema correctness.

10. **Receipts contract**

- What minimum fields are in the receipt?
  - dedupe key
  - payload_hash
  - event_class
  - target topic
  - partition key used
  - Kinesis shard + sequence number
  - timestamps (admitted_at, published_at)
- Are receipts written only after publish success?
- Do you write rejected/quarantined receipts too?

Detailed answers (recommended defaults, based on current implementation posture):
- Receipts are written for ADMIT, DUPLICATE, and QUARANTINE. QUARANTINE also writes a quarantine_record with the envelope (payload removed).
- Receipt fields include: receipt_id, decision, event_id, event_type, ts_utc, manifest_fingerprint, policy_rev, dedupe_key, pins, plus optional schema_version, producer, partitioning_profile_id, partition_key, eb_ref, reason_codes, evidence_refs.
- ADMIT receipts are written after publish success and include eb_ref with topic/partition/offset/offset_kind/published_at_utc.
- Gaps: payload_hash not recorded; event_class not recorded; admitted_at timestamp not recorded (only published_at_utc in eb_ref).

11. **Schema policy authority + compatibility**

- Is IG validating against interface pack schemas pinned by the run, or against repo config "current"?
- Do you reject unknown event_class hard?
- Do you allow minor versions, adapters, or is it strict in v0?

Detailed answers (recommended defaults, based on current implementation posture):
- IG loads schema_policy_ref + class_map_ref from wiring config at startup (not pinned by run).
- Envelope validation uses canonical_event_envelope.schema.yaml from engine contracts.
- Unknown event_type -> SCHEMA_POLICY_MISSING -> quarantine. schema_version enforcement is strict per policy; no adapters/compat shims in v0.
- Gap: no run-level schema pinning; config changes mid-run take effect immediately.

12. **Health and gating policy**

- Is BUS_HEALTH_UNKNOWN observational only, or can it throttle/stop admission?
- What does IG do if admission DB is down? If MinIO is down (cannot write receipts)? If EB is down?

Detailed answers (recommended defaults, based on current implementation posture):
- HealthProbe checks object store write, ops index probe, bus health, and read-failure counters. RED -> fail closed; AMBER -> warn + optional deny/sleep.
- BUS_HEALTH_UNKNOWN (kinesis) yields AMBER unless health_deny_on_amber is true.
- EB publish failure -> quarantine and publish-failure counter incremented.
- Admission DB is not health-checked; failures during lookup/record propagate as request errors (no buffer).
- Object store down -> RED (fail closed). If object store fails after publish, receipt write errors bubble out (no compensation).

---

## D) EB assumptions you must be explicit about

13. **Retention + replay window alignment**

- EB retention (env-specific) vs admission DB TTL vs planned archive: are they consistent?
- If EB retention is 7 days but admission DB TTL is 1 day, replay could re-admit duplicates.

Detailed answers (recommended defaults, based on current implementation posture):
- Local parity file EB retention is effectively indefinite (append-only files).
- Admission DB has no TTL; receipts in object store have no TTL.
- Kinesis retention is external config and not pinned in repo yet (gap for prod parity).

14. **Topic set contract**

- Are the four topics fixed for fraud-mode, or scenario/profile-dependent?
- Does READY include the expected topic set (even if consumers also have static config)?

Detailed answers (recommended defaults, based on current implementation posture):
- Topic set is derived from class_map + partitioning profiles. It is not included in READY today.
- READY payload includes run_id, facts_view_ref, bundle_hash, optional oracle_pack_ref. No run_config_digest or topic list yet.
- Gap: if run-specific topic sets are needed, READY must carry them (and a config digest) in v1.

---

## Additional angles to look at for Control & Ingress v0

1. **Security + trust boundary (WSP -> IG)**

- How is the caller authenticated (token/mTLS), and how do you prevent cross-run mixing (wrong run_id/pins)?
- Do you rate-limit per producer / per run?

Detailed answers (recommended defaults, based on current implementation posture):
- IG auth_mode supports disabled or api_key allowlist; JWT unsupported; no mTLS in v0.
- WSP does not attach an auth token by default (profile-dependent). IG trusts envelope pins and required_pins enforcement.
- Rate limiting is global per IG process (in-memory limiter), not per producer or per run.
- Gap: no signed pins, no run_id allowlist at IG.

2. **Operational observability (beyond logs)**

- Do you have per-class counters: received/admitted/duplicate/rejected/quarantined/published/receipt_written?
- Can you reconcile WSP-send vs IG-admit vs EB-seen vs receipts in one run report?

Detailed answers (recommended defaults, based on current implementation posture):
- IG logs counters + latency summaries (metrics recorder). Narrative logs capture admit/duplicate/quarantine counts.
- OpsIndex stores receipts/quarantines and supports lookup by event_id/receipt_id/dedupe_key.
- Gap: no automated run-level reconciliation report; reconciliation is manual today.

3. **Backpressure + overload posture**

- What happens when IG is hot (DB slow, EB slow): return 429? queue? drop? degrade?
- What is your max in-flight per run / per class to avoid memory blowups?

Detailed answers (recommended defaults, based on current implementation posture):
- IG enforces a global rate limiter; when exceeded, it returns 429 (RATE_LIMITED).
- WSP does not retry/backoff on 429/5xx; it fails the stream immediately.
- No queue/buffer is implemented; WSP concurrency is per-output (WSP_OUTPUT_CONCURRENCY) and is the only in-flight control.

4. **Failure isolation + "poison" handling**

- What do you do with schema-invalid or policy-invalid events: reject + receipt + quarantine bucket?
- Is there a DLQ/quarantine surface for "cannot publish" vs "cannot validate" vs payload_hash anomaly?

Detailed answers (recommended defaults, based on current implementation posture):
- Schema/policy failures -> QUARANTINE with quarantine_record + receipt.
- EB publish failures -> QUARANTINE (reason EB_PUBLISH_FAILED) with receipt.
- No separate DLQ topic; quarantine records live in object store under IG prefix.
- Gap: no payload_hash anomaly detection yet.

5. **Config/version pinning at the boundary**

- Do READY + receipts pin class_map + partitioning_profiles + schema-policy revision (run_config_digest)?
- If configs change mid-run, do you fail fast or keep processing with pinned versions?

Detailed answers (recommended defaults, based on current implementation posture):
- IG computes a policy_rev digest from schema_policy + class_map + partitioning profiles and includes it in receipts.
- READY does not pin these configs; IG uses current wiring config at runtime.
- Gap: no run-level freeze; config changes mid-run take effect immediately.

6. **Durability of receipts and run facts**

- If MinIO is unavailable, do you still publish? (You should not, unless you have an alternative durable receipt path.)
- Are receipts written only after publish success, and do they include shard/sequence (or equivalent) to prove admission?

Detailed answers (recommended defaults, based on current implementation posture):
- run_facts_view and run_ready_signal are write-once (no drift).
- ADMIT receipts are written after publish success and include eb_ref (topic, partition, offset, offset_kind, published_at_utc).
- DUPLICATE and QUARANTINE receipts are also written (no EB publish).
- Gap: if object store fails after publish, receipt write errors bubble out with no compensation.

7. **Cost/retention alignment**

- Do EB retention, admission DB TTL, and receipt/archive retention line up so replays do not accidentally re-admit old events?

Detailed answers (recommended defaults, based on current implementation posture):
- Local parity uses indefinite retention (file EB, no admission TTL, object store receipts without TTL).
- Prod alignment is not pinned yet; EB retention vs admission TTL vs receipt/archive retention remains open for RTDL planning.

8. **Publish atomicity + receipt durability (robustness verdict)**

- What is the explicit rule for handling publish "unknown success" (e.g., Kinesis timeout after PutRecord)?
- What is the durability requirement for receipts, and what happens if receipt writes fail after publish?

Detailed answers (recommended defaults, based on current implementation posture):
- Current posture: no explicit handling for publish unknown success. If publish raises, IG quarantines and does not record dedupe. This can lead to duplicates if the publish actually succeeded.
- Receipt durability: receipts are written after publish success; if the object store fails after publish, receipt write errors bubble out and there is no compensation or retry.
- Required pin to close this gap: implement publish-attempt logging (outbox) and treat receipt durability as part of the commit point; do not advance dedupe/offset state unless receipt write succeeds. Add an explicit retry/reconcile path for unknown success to avoid duplicate side-effects.
