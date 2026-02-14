## Cluster 3 — Streaming consumer reliability + bounded acceptance semantics

### What Cluster 3 is claiming (plain English)

You hit real streaming failure modes (start position mistakes, iterator starvation, replay storms, consumer identity drift), and you designed **bounded acceptance runs** (20/200) so you can validate end-to-end behavior without infinite streams.

To certify it, I need **one streaming failure** + **one bounded-run proof** + **the fix + evidence it worked**.

### Cluster 3 — Verification Questions (Round 1)

1. What is the “bounded run” mechanism in your system (20/200): what does it cap, where is it enforced, and how do you know it really stopped?
2. What are your stream start-position policies (e.g., trim-horizon vs latest) and when do you use each?
3. Describe the “consumer identity” model: how do you ensure you don’t accidentally fork consumer groups or re-consume from the wrong position?
4. Give one concrete incident:

   * what went wrong (starvation / wrong start / replay storm / stuck iterator)
   * how you detected it (symptoms + the check that proved it)
   * what you changed
   * what evidence confirmed recovery
5. What are your retry rules (what is retryable vs not), and how do you prevent “duplicate publish” during transient errors?
6. What is your “stream health vs flow health” lesson: what looked healthy but wasn’t, and how you proved the truth.
7. Anchor run:

   * `platform_run_id`
   * logs/evidence path(s) that show stream start → bounded stop
   * IG/EB evidence that confirms admitted offsets match expectations

---
