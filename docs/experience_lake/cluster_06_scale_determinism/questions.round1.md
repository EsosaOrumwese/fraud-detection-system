## Cluster 6 — Scale/performance + determinism under large datasets

### What Cluster 6 is claiming (plain English)

You hit real performance ceilings (OOM, overflow, timeouts, parquet/DuckDB pain), and you fixed them without breaking correctness — while keeping deterministic receipts/traceability.

To certify it, I need **one bottleneck story** with **before/after** + **what correctness you preserved**.

### Cluster 6 — Verification Questions (Round 1)

1. Pick your strongest bottleneck incident (OOM / overflow / timeout / parquet ingest fail / BrokenProcessPool / stream-sort stress).
2. Pin it:

   * which dataset/table (or plane)
   * approximate row count scale (not marketing; what you can defend)
   * what failed and how it manifested
3. What was the root cause (memory model, batch size, vectorization limits, Python multiprocessing, spill strategy, etc.)?
4. What did you change (knobs + structural changes), and why that tradeoff?
5. What “correctness invariant” did you protect (conservation, receipts integrity, no silent truncation, determinism)?
6. What evidence proves improvement (runtime, memory peak, success rate, or “now completes under Gate-200 reliably”)?
7. What did you decide *not* to do (and why) — e.g., “we didn’t loosen validation” / “we didn’t drop receipts.”

---
