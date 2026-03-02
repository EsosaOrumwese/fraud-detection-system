## Cluster 5 — Contract-first validation + schema resolution hardening

### What Cluster 5 is claiming (plain English)

You did the painful “platform correctness” work: schema anchors, `$id` resolution, draft semantics, canonical hashing/serialization, and you prevented silent validation drift across components/runs.

To certify it, I need **one schema failure that mattered** + **the fix** + **proof the validator now behaves deterministically**.

### Cluster 5 — Verification Questions (Round 1)

1. What contracts are validated where (which components validate what, at what boundary)?
2. What was the key schema resolution failure you hit (e.g., `$id` anchor, resolver pathing, draft mismatch, registry collisions)?
3. What exactly broke (false PASS vs false FAIL vs inconsistent behavior across machines)?
4. What was the fix:

   * change in schema `$id`/anchors
   * change in resolver logic
   * change in canonical serialization/hashing rules
5. How do you ensure determinism:

   * same inputs → same validation result
   * no “depends on working directory”
6. Give one artifact proving the new posture (e.g., registry bundle, resolver trace log, or a repeatable validation command with stable output).
7. What rule did you adopt that prevents “schema drift” from creeping back in?

---
