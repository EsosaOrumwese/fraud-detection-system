# Cluster 6 - Round 1 Answers

## Q1) Pick your strongest bottleneck incident (OOM / overflow / timeout / parquet ingest fail / BrokenProcessPool / stream-sort stress).

My strongest bottleneck incident was the **DuckDB OOM failure during Oracle stream-view full-range sorting for the large 6B flow-anchor outputs**.

I picked this as the strongest for three reasons:

1. It was on a critical path, not an edge path.  
   If stream views are not materialized reliably, the SR -> WSP -> IG ingestion spine cannot be validated end-to-end at realistic scale.

2. It forced a real engineering tradeoff under pressure.  
   I had to preserve strict chronological ordering and deterministic evidence posture while removing a hard resource ceiling. This was not just “make it faster”; it was “make it finish without weakening correctness law.”

3. The fix required structural redesign, not parameter tweaking.  
   The original full-range strategy was logically correct but operationally non-viable on practical local hardware. The solution required changing execution strategy (chunked ordered emission), while proving ordering semantics and artifact integrity remained intact.

So this incident is the best representative of my scale/determinism strength: I hit a hard runtime ceiling on real data volume, redesigned the execution model, and kept correctness guarantees intact instead of dropping standards to get a green run.

## Q2) Pin it:

### A) Which dataset/table (or plane)

This incident was in the **Oracle Store stream-view build plane** (local parity), specifically on:

- `s2_flow_anchor_baseline_6B`
- `s3_flow_anchor_with_fraud_6B`

These are large 6B flow-anchor outputs that must be sorted into stream views for downstream consumption.

### B) Approximate row-count scale (what I can defend)

What I can defend from implementation records is:

- the stream-view workload was explicitly called out as **multi-hundred-million rows**,
- with a concrete run note around **~374M rows** during this stream-view phase.

I am not claiming exact per-output row counts here because the documented scale anchor in this incident log is the total workload pressure, not a per-table audited count snapshot.

### C) What failed and how it manifested

Failure manifestation was explicit:

- **DuckDB OOM** during full-range sort of those two 6B outputs on a **16GB machine**.
- Build path attempted full ordered materialization and exceeded practical memory limits.

Operationally this meant:

- stream-view generation for the targeted large outputs could not complete under the original execution model,
- which blocked reliable progression of parity validation on the stream-view path until execution strategy changed.

## Q3) What was the root cause (memory model, batch size, vectorization limits, Python multiprocessing, spill strategy, etc.)?

The root cause was a **memory-model mismatch between monolithic sort strategy and dataset scale**.

### 1) Monolithic full-range sort on very large inputs

The original path performed a single-pass full-range ordered write per output:

- read parquet input,
- apply deterministic global ordering (`ts_utc` + tie-breakers),
- write sorted parquet output.

For the 6B anchors at this workload size, that full-range approach created a peak working-set profile that exceeded practical local memory limits.

### 2) Peak working-set amplification from sort semantics

This was not just “rows are many.”  
The sort path also carries deterministic tie-break metadata (`filename`, `file_row_number`) and row-level hash/stat computation surfaces for receipt validation. That improves correctness, but it increases memory/temporary-work pressure during large global ordering operations.

### 3) Environment ceiling: 16GB local hardware

On the local parity machine (16GB), the combination above crossed the available memory envelope for those two outputs under single-pass execution, causing DuckDB OOM.

So the true root cause was:

- **execution strategy** (full-range monolithic ordering)  
  not matching  
- **resource envelope** (local memory ceiling)  
  for  
- **required correctness posture** (deterministic global ordering + validation).

In short: correctness requirements were right, but the original compute plan for satisfying them was not resource-scalable.

## Q4) What did you change (knobs + structural changes), and why that tradeoff?

I changed both the **execution structure** and the **runtime controls**.

### 1) Structural change: full-range sort -> chunked day-window sort

I introduced a chunked sort path for time-key outputs:

- compute the output’s time range (`min_ts_utc` -> `max_ts_utc`),
- split it into day windows,
- run ordered extraction/write per window,
- emit sequential `part-XXXXXX.parquet` files at the output root.

The core shift was from one monolithic sort to bounded ordered windows.

### 2) New control knob: `STREAM_SORT_CHUNK_DAYS`

- `STREAM_SORT_CHUNK_DAYS > 0` enables chunked day-window mode (for example `1` day per chunk),
- `STREAM_SORT_CHUNK_DAYS = 0` preserves the original single-pass path.

This gave us an explicit operational lever: same contract semantics, different execution envelope.

### 3) Supporting runtime controls (kept active)

I kept and used the existing DuckDB execution knobs so chunking and spill behavior stay tunable per machine:

- `STREAM_SORT_MEMORY_LIMIT`
- `STREAM_SORT_TEMP_DIR`
- `STREAM_SORT_MAX_TEMP_SIZE`
- (plus thread/progress controls where needed)

These are supporting controls; chunking was the primary structural remediation.

### 4) Why this tradeoff was chosen

I rejected two bad extremes:

- “just buy bigger hardware,” which makes local parity brittle and non-repeatable,
- “relax ordering/validation rules,” which would weaken correctness.

The chosen tradeoff was:

- accept more parts/files and some extra orchestration overhead,
- in exchange for bounded peak memory and reliable completion,
- while keeping deterministic ordering and receipt validation posture intact.

### 5) What I deliberately did **not** change in this fix

- I did not alter source dataset schema/content.
- I did not drop deterministic ordering requirements.
- I did not remove receipt/stat validation checks.

So this was a compute-plan redesign, not a correctness downgrade.

## Q5) What “correctness invariant” did you protect (conservation, receipts integrity, no silent truncation, determinism)?

I protected four non-negotiable invariants.

### 1) Row-set conservation (no drops, no silent adds)

The sorted output had to represent the same logical row-set as the source input for that output_id.

I enforced this with receipt stats comparison between raw and sorted surfaces:

- `row_count` must match,
- independent aggregate checks must match (`hash_sum`, `hash_sum2`),
- range anchors (`min_ts_utc`, `max_ts_utc`) must match for time-key outputs.

If these do not match, the run fails closed (`STREAM_SORT_VALIDATION_FAILED`) instead of writing a “best effort” success.

### 2) Deterministic ordering invariant

Ordering semantics had to stay deterministic across reruns:

- primary key ordering on resolved sort key (time-key lane here),
- deterministic tie-breakers (`filename`, `file_row_number`),
- chunked mode preserves chronology by emitting chunks in sequence with deterministic part numbering.

So chunking changed memory behavior, not ordering law.

### 3) Evidence/receipt integrity invariant

I kept receipt and manifest integrity as the acceptance authority:

- stream view is considered valid only when receipt/manifest are present and coherent,
- existing receipt mismatch or partial output state is treated as error (not overwritten silently),
- `stream_view_id` and source locator digest are used to bind output evidence to exact input locator set.

This prevents false-green “sorted files exist” claims without proof-grade linkage.

### 4) Schema/content preservation invariant

This fix was a pure re-ordering lane:

- no source schema mutation,
- no payload rewriting,
- no truncation to reduce memory,
- no weakening of validation rules.

That matters because performance fixes often regress semantics; this one was constrained so semantics remained intact.

### Practical summary

The invariant set was:

- **same rows,**
- **deterministic order,**
- **receipt-proven equivalence,**
- **fail-closed on mismatch.**

That is what made this a valid scale fix rather than an accuracy tradeoff.
