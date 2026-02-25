## Cluster 4 — Datastore hardening across services

### What Cluster 4 is claiming (plain English)

You stabilized cross-service state when reality hit: reserved words, schema portability, long-running transactions, connection churn, locks, and “works locally but dies under orchestration.”

To certify it, I need **one “DB broke the platform” incident** + **the fix** + **proof it stayed fixed**.

### Cluster 4 — Verification Questions (Round 1)

1. What databases are in play (local_parity now, dev_min target), and what each is used for (state vs receipts vs checkpoints).
2. Give one concrete incident (choose your strongest):

   * reserved keyword (“offset”) collision
   * connection pooling/churn
   * transaction lifecycle/locks
   * schema drift across services
3. Pin it:

   * which component(s)
   * which phase/run did it break
   * what exactly failed (error class, symptom)
4. What was the root cause (not the symptom)?
5. What change did you make (schema, naming, migrations, connection pattern, retry discipline)?
6. How did you verify it (repeat run, targeted test, soak, “no regression” check)?
7. What new guardrail did you add so it doesn’t silently recur?

---
