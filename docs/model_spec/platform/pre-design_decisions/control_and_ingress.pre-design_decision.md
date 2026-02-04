# Control & Ingress Pre-design Decisions (v0, Open to adjustment where necessary)
_As of 2026-02-04_

Yep — for **Control & Ingress v0 robustness**, there are a few “designer-grade” questions I want settled (or I want to see your pinned answer / implementation notes for). These are the spots where systems that *work* in local parity usually hide their first production holes.

## A) Control plane authority and run lifecycle

1. **Run identity + activation semantics**

* How is `run_id` generated (collision resistance, monotonicity not required)?
* Where is “active run” stored, and what prevents cross-run mixing?
* Can multiple runs be active concurrently (you imply yes later for RTDL)? If so, how do components choose which run(s) to process?

What I’d want to see: READY schema + where “active run pointer” lives + concurrency rule.

2. **READY event idempotency**

* Can READY be emitted/consumed more than once (retries/restarts)?
* What’s the dedupe key for READY consumption (SR and WSP side)?
* If WSP restarts mid-run, does it re-emit the same events (same `event_id`) deterministically?

What I’d want to see: control event envelope + WSP ready-consumer dedupe rule.

3. **Run facts immutability**

* Is `run_facts_view` immutable once written?
* Do you content-hash / include a digest in READY so downstream can validate it didn’t change?
* If SR is re-run for the same run_id, what happens?

What I’d want to see: path convention + digest fields + overwrite policy.

---

## B) WSP producer correctness under retries/backpressure

4. **Event_id generation and stability**

* Is `event_id` **stable across retries** (same event, same `event_id`)?
* Does `event_id` incorporate `event_class` implicitly (you now dedupe by `(run_id, event_class, event_id)`, so either is fine — but it must be consistent)?
* Are you persisting a `payload_hash` at the producer or only at IG?

What I’d want to see: event_id algorithm (at least the “inputs” to it) + whether it’s deterministic.

5. **Retry model (HTTP ingest)**

* How does WSP react to 429/5xx/timeouts?
* Does it resend with the **same** `event_id`?
* Do you cap retries / exponential backoff?
* What happens on a 4xx schema error: drop/quarantine/stop run?

What I’d want to see: WSP retry policy notes + how you avoid duplicate storms.

6. **Time semantics**

* What does “600x speedup” do to `ts_utc` in payload/envelope?
* Are you emitting event_time from the oracle/stream view, or generating new times at emission?
* Do you ever violate event-time ordering within a single output stream (and is that acceptable)?

What I’d want to see: how timestamps are sourced and whether they are deterministic.

---

## C) IG admission pipeline: the real integrity boundary

7. **Admission DB schema + uniqueness guarantees**

* What is the **exact unique constraint** in the admission DB? (It should match your narrative: `(run_id, event_class, event_id)`.)
* Do you store `payload_hash` and enforce anomaly detection (same key, different hash)?
* What’s the retention/TTL of admission rows (must be ≥ any replay window you care about)?

What I’d want to see: table schema (columns + constraints) + TTL policy.

8. **Publish atomicity and “unknown success”**
   This is a classic hole:

* If IG calls Kinesis and the network drops after PutRecord, you may not know if it succeeded.
* On retry, you can publish duplicates even if admission dedupe already passed (because dedupe happens *before* publish).

Questions:

* How do you handle “publish status unknown”?
* Do you record publish attempts / sequence numbers in the admission DB?
* Do you ever re-run publish for an already-admitted event?

What I’d want to see: publish flow notes + what exactly is written when Kinesis returns success vs timeout.

9. **Partitioning determinism + join locality guarantees**

* For each `event_class`, what is the exact partition key derivation?
* For context streams, can you demonstrate that `(merchant_id, arrival_seq)` is always present and always used?
* For traffic, what is the chosen key today (flow_id?) and is it stable?

What I’d want to see: `partitioning_profiles_v0.yaml` + a one-liner “for each class, primary key = …”.

10. **Receipts contract**
    Receipts are your ground truth for reconciliation.

* What minimum fields are in the receipt?

  * dedupe key
  * payload_hash
  * `event_class`
  * target topic
  * partition key used
  * Kinesis shard + sequence number
  * timestamps (admitted_at, published_at)
* Are receipts written only after publish success?
* Do you write “rejected/quarantined” receipts too?

What I’d want to see: receipt JSON schema + example receipt.

11. **Schema policy authority + compatibility**

* Is IG validating against interface pack schemas pinned by the run, or against repo config “current”?
* Do you reject unknown `event_class` hard?
* Do you allow minor versions, adapters, or is it strict in v0?

What I’d want to see: schema resolution rule + failure handling.

12. **Health and gating policy**

* Is `BUS_HEALTH_UNKNOWN` observational only, or can it throttle/stop admission?
* What does IG do if admission DB is down? If MinIO is down (can’t write receipts)? If EB is down?

What I’d want to see: explicit “fail closed vs degrade vs buffer” rules for each dependency.

---

## D) EB assumptions you must be explicit about

13. **Retention + replay window alignment**

* EB retention (env-specific) vs admission DB TTL vs planned archive: are they consistent?
* If EB retention is 7 days but admission DB TTL is 1 day, replay could re-admit duplicates.

What I’d want to see: the three retention numbers side-by-side.

14. **Topic set contract**

* Are the four topics fixed for fraud-mode, or scenario/profile-dependent?
* Does READY include the expected topic set (even if consumers also have static config)?

What I’d want to see: READY includes topic set + run_config_digest (or a statement that it will).

---

## Additional angles to look at for Control & Ingress v0

1. **Security + trust boundary (WSP → IG)**

* How is the caller authenticated (token/mTLS), and how do you prevent cross-run mixing (wrong `run_id`/pins)?
* Do you rate-limit per producer / per run?

2. **Operational observability (beyond logs)**

* Do you have per-class counters: received/admitted/duplicate/rejected/quarantined/published/receipt_written?
* Can you reconcile WSP-send vs IG-admit vs EB-seen vs receipts in one run report?

3. **Backpressure + overload posture**

* What happens when IG is hot (DB slow, EB slow): return 429? queue? drop? degrade?
* What’s your max in-flight per run / per class to avoid memory blowups?

4. **Failure isolation + “poison” handling**

* What do you do with schema-invalid or policy-invalid events: reject + receipt + quarantine bucket?
* Is there a DLQ/quarantine surface for “can’t publish” vs “can’t validate” vs “payload_hash anomaly”?

5. **Config/version pinning at the boundary**

* Do READY + receipts pin `class_map` + `partitioning_profiles` + schema-policy revision (run_config_digest)?
* If configs change mid-run, do you fail fast or keep processing with pinned versions?

6. **Durability of receipts and run facts**

* If MinIO is unavailable, do you still publish? (You shouldn’t, unless you have an alternative durable receipt path.)
* Are receipts written only after publish success, and do they include shard/sequence (or equivalent) to prove admission?

7. **Cost/retention alignment**

* Do EB retention, admission DB TTL, and receipt/archive retention line up so replays don’t accidentally “re-admit” old events?

If you want the tightest “v0 robustness verdict,” the *single most important* missing angle (besides what I listed earlier) is **publish atomicity + unknown success** (IG→Kinesis) *plus* **receipt durability rules**—because that’s where event systems usually lose determinism under real faults.
