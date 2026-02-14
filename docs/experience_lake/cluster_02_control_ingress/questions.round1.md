## Cluster 2 — Control & Ingress correctness rails

### What Cluster 2 is claiming (plain English)

You didn’t just “stream data.” You built a **correctness boundary** where runs are scoped, READY is meaningful, ingestion is idempotent, duplicates/collisions are handled safely, and you can prove what was admitted (with receipts) — even under retries and at-least-once delivery.

To certify it, I need **one anchor run** + **one incident** (collision/ambiguity/replay) + **proof the boundary is fail-closed**.

### Cluster 2 — Verification Questions (Round 1)

1. Define the ingress boundary: what SR does vs WSP vs IG vs EB, and what “ADMITTED” means in your system.
2. What are the canonical IDs in play: `platform_run_id`, `scenario_run_id`, `event_id`, `event_class`, READY `message_id` (if any). Who mints what?
3. What exactly is READY: fields + guarantees + idempotency rules (what happens on duplicate READY)?
4. What is the IG dedupe law: define “duplicate” vs “collision” (same tuple, different payload) and the action for each (drop vs quarantine).
5. Walk me through your publish/admission state machine: `PUBLISH_IN_FLIGHT`, `ADMITTED`, `PUBLISH_AMBIGUOUS` — what triggers ambiguity and how it gets resolved.
6. What is “receipt truth” at this boundary: which receipt(s) are the commit evidence and what fields they must carry (counts, offsets/refs, hashes, run IDs).
7. Pick one anchor run and give me:

   * the `platform_run_id`
   * the root evidence path
   * the IG receipts prefix (or equivalent)
8. Give me one real “correctness saved” incident:

   * what happened (duplicate storm / collision / ambiguous publish / replay-start bug)
   * what evidence recorded it
   * what you changed
   * what proof shows it’s fixed
9. Where do you record provenance for this boundary (config digest / parameter_hash / image digest / git sha), and where does it live in the run artifacts?
10. What invariants must remain identical when moving from local_parity → dev_min for Control/Ingress (what is allowed to change vs not)?

---
