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

For the exact incident scope (the two 6B flow-anchor outputs), what I can defend is:

- `s2_flow_anchor_baseline_6B` = **124,724,153** rows,
- `s3_flow_anchor_with_fraud_6B` = **124,724,153** rows,
- combined workload for this OOM job scope = **249,448,306** rows.

Truth note: an earlier working note referenced `~374M` during stream-sort stress. That was a broader mixed-workload estimate during redesign, not the final audited count for this two-output OOM incident. For recruiter-facing claims, I use the audited per-output counts above.

### C) What failed and how it manifested

Failure manifestation was explicit:

- **DuckDB OOM** during full-range sort of those two 6B outputs on a **16GB machine**.
- Build path attempted full ordered materialization and exceeded practical memory limits.

Failure anchor (truthful boundary):

- The incident is pinned in timestamped implementation/logbook records in the `2026-01-30` window, before chunked-sort rollout.
- The repo retains the failure-class record (`DuckDB OOM` for these outputs on 16GB) but not the original failing DuckDB stacktrace artifact line.
- Primary implementation-map authority for this incident:
  - `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md`
  - entry marker: `## Entry: 2026-01-30 21:46:10 — Chunked stream sort (day windows)`

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

Concrete applied value in the hardening posture:

- `STREAM_SORT_CHUNK_DAYS=1` (day-window mode for large time-key outputs).
- Config/evidence surfaces for this setting:
  - applied run-note: `docs/logbook/02-2026/2026-02-01.md` (`04:07PM` entry includes `chunk_days=1`),
  - operator/runbook surface: `docs/runbooks/platform_parity_walkthrough_v0.md` (`$env:STREAM_SORT_CHUNK_DAYS="1"`),
  - runtime consumption point: `src/fraud_detection/oracle_store/stream_sorter.py` (`os.getenv("STREAM_SORT_CHUNK_DAYS", "0")`).

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

Concrete receipt field checks:

- `raw_stats.row_count == sorted_stats.row_count`
- `raw_stats.hash_sum == sorted_stats.hash_sum`
- `raw_stats.hash_sum2 == sorted_stats.hash_sum2`
- `raw_stats.min_ts_utc == sorted_stats.min_ts_utc`
- `raw_stats.max_ts_utc == sorted_stats.max_ts_utc`

If these do not match, the run fails closed (`STREAM_SORT_VALIDATION_FAILED`) instead of writing a “best effort” success.

### 2) Deterministic ordering invariant

Ordering semantics had to stay deterministic across reruns:

- primary key ordering on resolved sort key (time-key lane here),
- deterministic tie-breakers (`filename`, `file_row_number`),
- chunked mode preserves chronology by emitting chunks in sequence with deterministic part numbering.

Concrete cross-chunk ordering check/mechanism:

- each chunk query orders by `CAST(ts_utc AS TIMESTAMP), filename, file_row_number`,
- chunk windows are non-overlapping `[start, end)` intervals traversed forward in time,
- output parts are emitted as `part-000000`, `part-000001`, ... in that same temporal sequence.

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

## Q6) What evidence proves improvement (runtime, memory peak, success rate, or “now completes under Gate-200 reliably”)?

The strongest evidence is a **before/after completion-state change with preserved correctness artifacts**.

### Before (failure state)

- The full-range sort path for:
  - `s2_flow_anchor_baseline_6B`
  - `s3_flow_anchor_with_fraud_6B`
  hit DuckDB OOM on a 16GB local parity machine.
- Result: stream-view build for those targets was not operationally completable under the original strategy.

Failure anchor:

- Incident window documented before the `2026-01-30 21:46:10` chunked-sort entry in `oracle_store.impl_actual`.
- Failure class explicitly recorded there: DuckDB OOM on full-range sort for these two outputs.
- Raw failing stacktrace artifact was not retained in the repository.

### After (post-fix state)

With chunked day-window execution enabled (`STREAM_SORT_CHUNK_DAYS`), the same class of outputs moved to successful completion posture:

- stream views materialized under flat per-output roots (`.../stream_view/ts_utc/output_id=<output_id>/part-*.parquet`),
- receipts/manifests present per output,
- Oracle Store local-parity posture marked green with the expected stream-view artifact family present for verified outputs.

Success anchor (concrete root + artifacts):

- engine run root: `s3://oracle-store/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`
- stream-view root: `s3://oracle-store/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/stream_view/ts_utc`
- example output artifact family:
  - `.../output_id=s2_flow_anchor_baseline_6B/part-*.parquet`
  - `.../output_id=s2_flow_anchor_baseline_6B/_stream_sort_receipt.json`
  - `.../output_id=s2_flow_anchor_baseline_6B/_stream_view_manifest.json`
- same artifact contract applies to:
  - `output_id=s3_flow_anchor_with_fraud_6B`

### Why this is valid improvement evidence

This is not a cosmetic signal.  
For this incident, the blocker was “cannot complete under resource envelope.”  
The improvement proof is therefore:

- from deterministic OOM failure class  
  to  
- repeatable completion with contract artifacts and validation surfaces still intact.

### What I did and did not claim

- I **can claim** elimination of this specific OOM failure class for the targeted 6B sort path under chunked execution plus successful artifact closure.
- I **do not claim** a fully instrumented memory-peak benchmark chart for this exact fix in these notes.
- I **do not substitute** unrelated Gate-200 metrics here, because this incident’s acceptance surface is Oracle stream-view build completion + receipt integrity, not ingress bounded-run throughput.
- I **do not claim** retained raw failing stacktrace logs for the pre-fix attempt; that part is represented by timestamped implementation/logbook records and post-fix artifact closure.
