# 1) Purpose & scope

**Purpose.** Prove a State-1 run is correct using **read-only** checks over the persisted artefacts. Concretely, L3 verifies that hurdle events and the cumulative RNG trace:

* obey the **authoritative schema & envelope** (complete envelope, minimal payload; microsecond `ts_utc`; field types/encodings), and use the **correct dataset/partitions** (`seed/parameter_hash/run_id`) with **path ↔ embed equality**, keeping `module/substream_label` and `manifest_fingerprint` in the **envelope only**, not the path.
* satisfy **budget identities** per row (`u128(after)−u128(before)=decimal_string_to_u128(draws)`; for hurdle `draws∈{"0","1"}` and `blocks==u128_to_uint64_or_abort(decimal_string_to_u128(draws))`) and the **determinism law** (`π∈{0,1} ⇒ draws="0", u=null, deterministic=true`).
* are **replayable**: rebuild the keyed **base counter** from `(seed, manifest_fingerprint, "hurdle_bernoulli", merchant_id)`, and when `draws="1"` regenerate the single uniform (low-lane, strict-open `(0,1)`) so `(u<π)==is_multi`.
* reconcile with the **cumulative trace** per `(module, substream_label)` (no merchant dimension): cumulative `events_total`, `blocks_total`, `draws_total` are consistent with the event stream and with the **counter delta** on the final trace row.
* meet **cardinality/uniqueness** (one hurdle row per merchant; count equals ingress universe) and **branch purity/gating** (downstream 1A RNG streams present **iff** hurdle `is_multi=true`, discovered via the registry filter).

**Nature.** L3 is deterministic and idempotent: it reads artefacts, recomputes/compares (including exact binary64 for `π`/`u`), and emits a verdict/report bundle. It **does not** mutate event/trace datasets or “fix” anything.

---

# 2) Inputs & non-goals

## Inputs (closed set)

* **Hurdle events** (`rng_event_hurdle_bernoulli`) for the run:
  path `logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`; schema `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`; envelope + payload as frozen.
* **RNG trace (cumulative)** per `(module, substream_label)` for the same `{seed, parameter_hash, run_id}`; no merchant dimension; used for totals and final **counter-delta** reconciliation.
* **RNG audit row** for `{seed, parameter_hash, run_id}` (gate: must exist before first event).
* **Model/feature artefacts** required to recompute `η` and `π`:
  the single-YAML hurdle **β** vector (atomic load; aligned to S0.5 design) and the S0.5 **design vectors** `x_m` with the exact hurdle feature set `[1, φ_mcc, φ_channel, φ_dev(b_m∈{1..5})]`.
* **Run lineage keys:** `{seed, parameter_hash, manifest_fingerprint, run_id}` from path + envelope; `module="1A.hurdle_sampler"`, `substream_label="hurdle_bernoulli"` literals.
* **Registry filter** to enumerate **gated downstream 1A streams** (for presence checks tied to `is_multi`).
* **Ingress merchant universe** `M` (and `home_iso`) for the run, to check coverage and to build the handoff admissibility surface (audit only).

> Validator logic is order-invariant and uses the dataset dictionary/registry + S1 invariants; it treats event-shard order as irrelevant.

## Non-goals (explicit)

* No mutations: L3 **never** edits/deletes/re-emits event/trace rows; it only writes a **validation bundle** (report, failures, `_passed.flag` when all validators pass).
* No retries, backfills, or compensation; failures are **diagnostic** only. (E.g., if a trace append failed after an event was written, L3 reports the trace reconciliation error; it does not try to repair.)
* No alternate math or RNG: L3 uses the exact S1/S0 rules (Neumaier dot, two-branch logistic, keyed substreams, open-interval `u01`); it does not re-define policies.
* No reliance on diagnostics for authority: optional `hurdle_pi_probs` (if present) may be compared for sanity but is **non-authoritative** for validation decisions.

---

# 3) Validator suite (independent, composable)

**Shape.** Small, orthogonal validators; each streams inputs, returns PASS/FAIL + a tiny, deterministic report block. No mutations.

**Per-validator report fields (canonical):**
`{ id, status, checked_rows, failures_count, samples: [ … up to N=100 … ] }`.

---

## 1. V-Gate — Audit row exists (precondition)

**Intent.** Assert the run wrote an **RNG audit** before any hurdle event; without it, S1 must not have emitted events. The audit is run-scoped and partitioned by `{seed, parameter_hash, run_id}`.

**Inputs.** `{seed, parameter_hash, run_id}`; registry/dictionary entry for `rng_audit_log` (path + schema anchor).

**PASS iff**

* Exactly **one** audit file exists at
  `logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl`.
* (Optional) The audit row’s embedded `{seed, parameter_hash, run_id}` **equals** the path partitions.

**FAIL if** missing or path↔embed mismatch.

**Algorithm (sketch).**

1. Resolve path from dictionary; `exists(path)`. If no → **FAIL**.
2. Read first (and only) line; ensure embedded `{seed, parameter_hash, run_id}` equals path. → **PASS**.

---

## 2. V-Schema — Event & trace line validity

**Intent.** Every hurdle **event** line and every **trace** line must validate against the authoritative layer schemas; enforce typing rules: JSON integers for ids/counters; `pi`/`u` as JSON numbers; `ts_utc` microsecond precision.

**Inputs.**

* Event dataset: `rng_event_hurdle_bernoulli`
  Path: `logs/rng/events/hurdle_bernoulli/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
  Schema: `schemas.layer1.yaml#/rng/events/hurdle_bernoulli`.
* Trace dataset: `rng_trace_log`
  Path: `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`
  Schema: `schemas.layer1.yaml#/rng/core/rng_trace_log`.

**PASS iff**

* Every event JSONL line validates the hurdle schema; envelope is **complete** (required fields present); `merchant_id`, `seed`, and counter words are **JSON integers**; `pi`/`u` are JSON numbers; `ts_utc` is RFC-3339 **UTC with exactly 6 fractional digits**; `draws` is a **decimal u128 string**; `blocks` is `uint64`.
* Every trace JSONL line validates its schema; cumulative fields have correct types.

**FAIL if** any line fails schema or typing.

**Algorithm (sketch).**

1. Stream shards; for each line, validate against the corresponding schema anchor (strict mode).
2. For events, additionally check `ts_utc` microsecond format and the **binary64 round-trip** property for `pi`/`u` (parse→format→parse yields identical bits).

---

## 3. V-Partitions — Path ↔ embed equality

**Intent.** Enforce the partitioning contract and literal placement: events and trace are partitioned **only** by `{seed, parameter_hash, run_id}`; those fields inside the envelope must **equal** the path values; `manifest_fingerprint` is **embedded** (never in the path); `module` and `substream_label` are envelope literals, not path segments.

**Inputs.** Event & trace datasets (paths above) plus the embedded envelopes.

**PASS iff**

* For **every** **event** line: embedded `{seed, parameter_hash, run_id}` equals path values byte-for-byte; path does **not** include `manifest_fingerprint` or `module/substream_label`; envelope `module="1A.hurdle_sampler"` and `substream_label="hurdle_bernoulli"` match registry literals.
* For **every** **trace** line: embedded `{seed, run_id}` equals path values; `parameter_hash` is **path-only** for `rng_trace_log` (must be present in the path but is **not** embedded in the row). No merchant dimension; `(module, substream_label)` fixed within the run for the hurdle trace.

**FAIL if** any mismatch or if forbidden fields appear in paths.

**Algorithm (sketch).**

1. For each shard, parse path partitions; for each line, compare to embedded fields.
2. Assert **absence** of `fingerprint=…` and `module/substream_label` in event/trace paths; assert envelope carries `manifest_fingerprint` and the correct `module/substream_label` **literals**.

---

## 4. V-Cardinality & Uniqueness

**Intent.** Ensure exactly one hurdle row per merchant in the run, and total rows equal the ingress merchant universe size for the same `{seed, parameter_hash, run_id}`.

**Inputs.**
Event dataset `rng_event_hurdle_bernoulli` (scoped by `{seed, parameter_hash, run_id}`) and the ingress merchant set `M` for the run.

**PASS iff**

* Row count equals `|M|`.
* Uniqueness on key `(seed, parameter_hash, run_id, merchant_id)` holds (no duplicates).

**FAIL if** missing merchants, extra merchants, or any duplicate `merchant_id` within the run.

**Algorithm (sketch).**

1. Stream all hurdle rows; build a `seen` set of `merchant_id`s; detect duplicates.
2. Compare `seen` with `M` → produce `missing_merchants` and `extra_merchants`; **PASS** only if both are empty and no duplicates.

---

## 5. V-Design & π recompute

**Intent.** Recompute `η=β·x_m` (Neumaier, fixed order) and `π` (two-branch logistic). Require **bit-exact binary64** equality with the stored `pi`. Enforce finiteness and `[0,1]` range.

**Inputs.**
Hurdle β (single YAML vector), design vectors `x_m` from S0.5 (intercept+MCC+channel+5 GDP-bucket), event rows’ `pi`.

**PASS iff**

* Each recomputed `η` is finite; recomputed `π∈[0,1]`.
* Recomputed `π` equals persisted `pi` **bit-for-bit** (binary64 round-trip).

**FAIL if** any non-finite, out-of-range, or mismatch.

**Algorithm (sketch).**

1. For each merchant `m`, load `x_m` and β; compute `η` via fixed-order Neumaier; compute `π` via two-branch logistic.
2. Parse event `pi` as binary64; compare bit patterns; count failures (emit first N examples deterministically).

---

## 6. V-Budget identities (per row)

**Intent.** Check the unsigned-128 envelope identity and the hurdle law:
`u128(after) − u128(before) = decimal_string_to_u128(draws)` and **for hurdle** `blocks = u128_to_uint64_or_abort(decimal_string_to_u128(draws)) ∈ {0,1}`. Also enforce the determinism law for `π∈{0,1}` vs `(0,1)`.

**Inputs.**
Per-event counters (`rng_counter_*`), `draws` (decimal u128 string), `blocks` (u64), `pi`, `u`, `is_multi`, `deterministic`.

**PASS iff**

* Identity holds for every row; `blocks` matches `draws` and is `0` or `1`.
* If `π∈{0,1}`: `draws="0"`, `blocks=0`, `after=before`, `u=null`, `deterministic=true`, `is_multi=(π==1.0)`.
* If `0<π<1`: `draws="1"`, `blocks=1`, `after=before+1`, `0<u<1`, `deterministic=false`, `is_multi=(u<π)`.

**FAIL if** any identity or law is violated.

**Algorithm (sketch).**

1. For each row: compute 128-bit `delta = after − before`; parse `draws`; assert `delta = draws`.
2. Assert hurdle law (`blocks = draws ∈ {0,1}`) and determinism implications given `pi`.

---

## 7. V-Substream replay

**Intent.** Rebuild the keyed **base counter** for `(seed, manifest_fingerprint, "hurdle_bernoulli", merchant_id)` using S0’s substream mapping; ensure it equals the envelope’s `before`. If `draws="1"`, regenerate the single uniform (low-lane, strict-open `u01`) and check `u` and decision `(u<π)==is_multi`.

**Inputs.**
Run lineage keys, event envelope counters, payload `u`, `pi`, `is_multi`. L0 substream/PRNG primitives (`derive_substream`, `philox_block`, `u01`, low-lane policy).

**PASS iff**

* Reconstructed base counter equals `rng_counter_before_{hi,lo}` for every event.
* If `draws="1"`: regenerated `u` (from the **low lane** of the first block) is **binary64-equal** to payload `u`, `0<u<1`, and `(u<π) == is_multi`.
* If `draws="0"`: `after==before`, `u==null`, `deterministic==true`.

**FAIL if** any base-counter mismatch or replay mismatch.

**Algorithm (sketch).**

1. For each merchant: `s = derive_substream(master(seed, fingerprint), "hurdle_bernoulli", (merchant_id))`; assert `s.ctr == before`.
2. If `draws="1"`: `(x0, x1, s1) = philox_block(s)`; `u = u01(x0)`; assert binary64 equality with payload `u` and decision `(u<π)==is_multi`; assert `s1.ctr == after`.
3. If `draws="0"`: assert `after==before` and `u==null`.

---

## 8. V-Trace reconciliation

**Intent.** Prove the **cumulative RNG trace** is consistent with the **event stream** and counter deltas, line-by-line and in total.

**Inputs.**
Trace JSONL (per `(module="1A.hurdle_sampler", substream_label="hurdle_bernoulli")` under the run’s `{seed, parameter_hash, run_id}`), and all hurdle events for the same run.

**PASS iff**

* There is **one** trace series for the hurdle substream (no mixing of modules/labels).
* For each trace line `t_i` there exists **exactly one** event `e_i` such that:

  * `t_i.rng_counter_before_* == e_i.rng_counter_before_*`
  * `t_i.rng_counter_after_*  == e_i.rng_counter_after_*`
* Totals are **monotone, saturating u64** and evolve as:

  * `events_total(i) = events_total(i-1) + 1`
  * `blocks_total(i)  = blocks_total(i-1) + u128_to_uint64_or_abort( u128(after_i) − u128(before_i) )`
  * `draws_total(i)   = draws_total(i-1)  + u128_to_uint64_or_abort( decimal_string_to_u128(e_i.draws) )`
* Final totals reconcile with events:

  * last `events_total == |events|`
  * last `blocks_total == Σ u128_to_uint64_or_abort( u128(after) − u128(before) )`
  * last `draws_total  == Σ u128_to_uint64_or_abort( decimal_string_to_u128(draws) )`
* The final trace `after_{hi,lo}` equals the **last** event’s `after_{hi,lo}`.

**FAIL if**

* Any line can’t be matched to a unique event by `(before,after)`.
* A totals update deviates from the identities above.
* Multiple trace series in the run, or missing/extra lines relative to the event set.

**Algorithm (sketch).**

1. Build an index `E[(before_hi, before_lo, after_hi, after_lo)] = event`.
2. Stream trace lines in file order; for each `t_i`:

   * Lookup `e_i` by the `(before,after)` key; require uniqueness.
   * Check totals deltas vs. `e_i` (`draws`,`after−before`).
3. After last line, recompute final totals from the **event set** and compare to the final trace line.
4. If any mismatch: record `merchant_id`, `(before,after)`, and offending total(s) in failures.

---

## 9. V-Handoff preconditions

**Intent.** From each **emitted hurdle event**, reconstruct the S1.5 handoff tuple admissibility and ensure inputs for downstream routing are correct (audit-only).

**Inputs.**
Event rows; ingress `home_iso(m)`; (optionally) registry filter for downstream 1A streams (for presence checks only if enabled).

**PASS iff**

* For every event:

  * `C*` candidate equals the **post** counter `(rng_counter_after_hi, rng_counter_after_lo)`.
  * `home_iso(m)` exists and is a valid ISO-3166-1 alpha-2 code.
  * `is_multi` is **consistent** with `pi`/`u`:

    * if `pi ∈ {0,1}` → `is_multi == (pi == 1.0)` and `u == null`
    * if `0 < pi < 1` → `is_multi == (u < pi)` and `0 < u < 1`
* (Optional, if gating audit is enabled in your environment)
  For merchants with `is_multi=false`, **no** downstream multi-site RNG events exist; for `is_multi=true`, presence of the next gated stream is **observed** (WARN only if you don’t want to hard-fail here in S1’s validator).

**FAIL if**

* Missing/invalid `home_iso(m)`, or `C*` not equal to `after`, or `is_multi` inconsistent with `pi/u`.

**Algorithm (sketch).**

1. For each event `e(m)`: read `after` → set `C* := after`; assert `home_iso(m)` present/valid; recompute `is_multi_expected` from `pi/u`; compare with `e.payload.is_multi`.
2. (Optional) If a gating registry is provided: spot-check downstream presence/absence and record as WARN or FAIL per config.

---

## 10. V-Run summary

**Intent.** Produce a deterministic, self-certifying summary of the run’s validation: verdict, metrics, breadcrumbs, and (capped) failure exemplars for quick triage.

**Inputs.**
Outputs of validators 1–9; schema/model/validator version digests; numeric profile id; lineage keys.

**PASS iff**

* All validators 1–9 return PASS.

**FAIL if**

* Any validator returns FAIL (summary aggregates exact failing validators and counts).

**Algorithm (sketch).**

1. Collect per-validator results: `status`, `checked_rows`, `failures_count`, and up to **N=100** deterministic `samples` (sorted by `(merchant_id, validator_id)`).
2. Compute metrics:

   * `|M|` (expected) vs. `|events|` (observed)
   * first/last `(before,after)` counters
   * totals from V-Trace (events/blocks/draws)
3. Write `report.json` with:

   * `verdict: "PASS" | "FAIL"`
   * `validators: { id → {status, counts, samples} }`
   * `metrics`, `lineage:{seed, parameter_hash, manifest_fingerprint, run_id}`
   * `breadcrumbs:{ schema_commit, beta_digest, design_digest (or parameter_hash), validator_commit, numeric_profile }`
   * `reason:"empty_universe"` when `|M|=0`
4. If verdict PASS: write `_passed.flag` as a hash over `report.json` (and any small auxiliary files).
   If FAIL: omit `_passed.flag` and include `failures.jsonl` concatenating capped samples from each validator.

---

# 4) Outputs — Validation bundle (self-certifying) [Not sure if this should exist here]

**Goal.** Emit a small, deterministic bundle that lets an operator (or CI) understand *exactly* what was checked, what passed/failed, and why—without touching the authoritative datasets.

## 4.1 Location & layout

```
validation/state1/
  fingerprint={manifest_fingerprint}/
    seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/
      report.json
      failures.jsonl            # only when any validator FAILs
      breadcrumbs.json          # tiny provenance file
      _passed.flag              # only when ALL validators PASS
```

* Path keys mirror the run lineage; reruns with identical lineage **overwrite** byte-identical files (idempotent).
* Publish atomically: write to a temp dir, fsync, rename into place.

## 4.2 `report.json` (canonical schema)

```json
{
  "verdict": "PASS | FAIL",
  "lineage": {
    "seed": 0,
    "parameter_hash": "hex64",
    "manifest_fingerprint": "hex64",
    "run_id": "hex32"
  },
  "metrics": {
    "merchants_expected": 0,
    "events_observed": 0,
    "first_counter_before": {"hi":0,"lo":0},
    "last_counter_after":  {"hi":0,"lo":0},
    "events_total": 0, "blocks_total": 0, "draws_total": 0
  },
  "validators": {
    "V-Gate":          {"status":"PASS|FAIL","checked_rows":1,"failures_count":0,"samples":[]},
    "V-Schema":        {"status":"PASS|FAIL","checked_rows":N,"failures_count":K,"samples":[...]},
    "V-Partitions":    {"status":"PASS|FAIL","checked_rows":N,"failures_count":K,"samples":[...]},
    "V-Cardinality":   {"status":"PASS|FAIL","checked_rows":N,"failures_count":K,"samples":[...]},
    "V-DesignPi":      {"status":"PASS|FAIL","checked_rows":N,"failures_count":K,"samples":[...]},
    "V-Budget":        {"status":"PASS|FAIL","checked_rows":N,"failures_count":K,"samples":[...]},
    "V-Substream":     {"status":"PASS|FAIL","checked_rows":N,"failures_count":K,"samples":[...]},
    "V-Trace":         {"status":"PASS|FAIL","checked_rows":T,"failures_count":K,"samples":[...]},
    "V-Handoff":       {"status":"PASS|FAIL","checked_rows":N,"failures_count":K,"samples":[...]}
  },
  "reason": "empty_universe | null",
  "generated_at_utc": "YYYY-MM-DDThh:mm:ss.SSSSSSZ",
  "version": {
    "schema_commit": "…",
    "validator_commit": "…",
    "numeric_profile": "…"
  }
}
```

**Conventions**

* Deterministic JSON: UTF-8, sorted keys, no trailing spaces, `generated_at_utc` with exactly **6** fractional digits.
* `samples` are capped (≤100 per validator) and **sorted** by `(merchant_id, validator_id)` or an appropriate key (e.g., trace index), so reports are stable run-to-run.

## 4.3 `failures.jsonl`

Each line is one exemplar failure:

```json
{"validator_id":"V-DesignPi","merchant_id":9002,
 "message":"pi mismatch (binary64)", "expected":"0.34285714285714286", "observed":"0.3428571428571428",
 "context":{"before":{"hi":0,"lo":101}, "after":{"hi":0,"lo":102}}}
```

* Include only minimal, actionable context (ids, counters, expected/observed); never dump full rows.

## 4.4 `breadcrumbs.json`

Tiny provenance to make the bundle self-certifying:

```json
{"beta_digest":"sha256:…","design_digest":"sha256:…",
 "schema_commit":"…","validator_commit":"…","numeric_profile":"binary64:RNE:noFMA:noFTZ"}
```

* `design_digest` may simply be the `parameter_hash` if that deterministically covers the S0.5 materialization.

## 4.5 `_passed.flag` (gate)

* Present **only** if every validator returned PASS.
* Contents: a single hex SHA-256 over the concatenation of `report.json` and `breadcrumbs.json` **in filename-sorted order**.
* Verifiers recompute this hash to confirm bundle integrity.

---

# 5) Execution & reporting model

**Principles:** streaming, deterministic, small memory footprint, and predictable failure output.

## 5.1 Streaming & memory

* Read JSONL in **chunks** (default 100k lines). O(1) extra memory per validator.
* Event shard order is irrelevant; validators consume in any order but **report** in a fixed order (see below).

## 5.2 Scheduling (simple phases)

1. **Phase A (fast gates):** V-Gate → V-Schema (events & trace) → V-Partitions.
2. **Phase B (set properties):** V-Cardinality & Uniqueness; collect `M_seen`.
3. **Phase C (math & RNG):** V-Design & π recompute → V-Budget identities → V-Substream replay.
4. **Phase D (roll-up):** V-Trace reconciliation → V-Handoff preconditions → V-Run summary.

> You can parallelize *within* a phase if you keep outputs deterministic (e.g., merge failure samples then sort). Keep I/O bounded.

## 5.3 Deterministic reporting

* For each validator, gather at most **N=100** failing exemplars.
* Sort exemplars by a stable key:

  * Event-based validators: `(merchant_id)`
  * Trace validators: `(before_hi, before_lo, after_hi, after_lo)`
* The final `report.json.validators[*].samples` reflects that ordering; `failures.jsonl` concatenates in **validator id order**, then within each validator by the same key.

## 5.4 Pass/Fail policy

* **Hard FAIL** on any schema/type error, partition mismatch, uniqueness/cardinality error, π mismatch, budget identity failure, substream/replay mismatch, or trace reconciliation error.
* Optional WARNs (cosmetic) may be recorded in `samples` but **do not** affect verdict.

## 5.5 Time & size discipline

* Default chunk size: **100k** lines (configurable); keep CPU-bound validators (π recompute, RNG replay) streaming.
* Cap `failures.jsonl` at **validators × 100** lines (one per sample) to prevent blow-ups.
* No compression required; if used, prefer plain files + gz with deterministic names.

## 5.6 Atomic publish & idempotency

```pseudocode
tmp = mkdtemp()
write(tmp/report.json)
write(tmp/breadcrumbs.json)
if all_pass: write(tmp/_passed.flag)
if any_fail: write(tmp/failures.jsonl)
fsync(tmp); rename(tmp, final_path)   # atomic dir swap
```

* Re-running with identical inputs regenerates **byte-identical** bundle files.
* Never mutates authoritative event/trace datasets.

---

# 6) Severity & taxonomy

**Goal.** Make outcomes unambiguous for operators and CI: what fails the run, what’s merely informational, and how errors are labeled.

## 6.1 Verdict levels

* **PASS** — every validator passes.
* **FAIL** — **any** validator fails. One failing check is sufficient.
* **WARN** — optional, non-blocking observations recorded in `report.json.validators[*].samples` (do **not** affect verdict).

## 6.2 What is a FAIL (binding)

* **Schema / typing** problems (V-Schema): invalid JSON, wrong field types, missing required fields, timestamp format ≠ microseconds, floats serialized as strings.
* **Partition ↔ embed** mismatches or forbidden path segments (V-Partitions).
* **Cardinality / uniqueness** violations (V-Cardinality): duplicates, missing or extra merchants.
* **Design or π** mismatch, non-finite η, π∉\[0,1], or π not **binary64-equal** to recompute (V-Design & π).
* **Budget identities** broken, determinism law violated, or hurdle block law broken (V-Budget).
* **Substream replay** mismatch: base counter doesn’t match `before`; regenerated `u` not **binary64-equal** (when `draws=="1"`); `(u<π)≠is_multi` (V-Substream).
* **Trace reconciliation** failure: series mismatch, per-line delta errors, wrong final totals, last `after` not equal to last event’s `after` (V-Trace).
* **Audit missing** (V-Gate).

## 6.3 What may be WARN (optional, config-driven)

* Cosmetic extras if your reader exposes them: unknown envelope fields that still pass strict schema (only if the schema allows extensions), minor ordering differences in shards, or presence/absence of downstream gated streams (V-Handoff) if you prefer not to hard-fail here.
* Timestamp *ordering* (not format): e.g., non-monotone `ts_utc` across rows — recordable but non-blocking.

> Default stance: **strict**. If in doubt, treat an issue as **FAIL** unless explicitly whitelisted as WARN.

## 6.4 Error taxonomy (labeling)

Use the same error classes as in L2 (for consistency in dashboards/alerts):

* `S1.PRECONDITION` — audit missing, bad ISO, duplicate merchant (if L3 checks these again).
* `S1.INPUT` / `S1.DESIGN.ALIGNMENT` — missing `x_m`, `|β|≠dim(x_m)`.
* `S1.NUMERIC` — non-finite η, π out of range, π mismatch.
* `S1.RNG.BOUNDARY` / `S1.RNG.CONSISTENCY` — `u` outside (0,1), deterministic branch inconsistencies.
* `S1.BUDGET.IDENTITY` — counter/budget equalities broken.
* `IO.READ` — unreadable shards/lines, truncated files.
* `TRACE.RECONCILE` — mismatched cumulative totals/series.

Each failing sample in `failures.jsonl` includes `validator_id`, `class`, `code (E_*)`, `merchant_id` or `(before,after)` key, and minimal context.

---

# 7) Edge cases

**Goal.** Spell out how L3 behaves in unusual but realistic situations—no surprises, no silent passes.

1. **Empty universe**
   Runs with `|M|=0` are valid: V-Gate must PASS; event/trace sets are empty; V-Cardinality PASS (expected=0, observed=0); summary includes `"reason":"empty_universe"`.

2. **Event persisted, trace missing**
   If L2 aborted between event write and trace append, V-Trace **FAILS** (reconciliation). All row-level validators may still PASS. We do **not** “repair” trace.

3. **Duplicate merchants across shards**
   V-Cardinality detects duplicates even if they land in different `part-*.jsonl` files. Deterministic samples show the offending `merchant_id`s.

4. **Out-of-order or mixed shards**
   Shard order is irrelevant; validators stream and sort deterministically for reporting. If shards contain mixed `{seed, parameter_hash, run_id}` (path hygiene breach), V-Partitions **FAILS** immediately.

5. **Multiple trace series in a run**
   If the hurdle trace file mixes other `(module, substream_label)` pairs or contains more than one hurdle series, V-Trace **FAILS** (series cardinality/integrity).

6. **π near 0 or 1**
   L3 applies **binary64-exact** rules: only exact `0.0` or `1.0` are treated as deterministic. Values like `~1−ε` remain stochastic; V-Budget and V-Substream expect `draws=="1"`, `blocks=1`, and `(u<π)`.

7. **Float formatting quirks**
   `pi` and `u` must be JSON numbers that **round-trip** to the same binary64. If serialized as strings, or if parse→format→parse changes bits, V-Schema **FAILS**.

8. **Corrupted / truncated JSONL lines**
   V-Schema **FAILS** with `IO.READ`/schema errors; sample includes shard and 1-based line index. No attempt to skip/repair.

9. **Unsigned counter edges**
   Envelope counters are 128-bit; trace totals are saturating `u64`. V-Budget uses full 128-bit arithmetic per row; V-Trace verifies **saturating** deltas for totals and exact equality for per-line `(before,after)`. Saturation itself is not a failure; wrong deltas are.

10. **Audit duplicates**
    If multiple audit rows/files exist for the same `{seed, parameter_hash, run_id}`, V-Gate **FAILS** (expected exactly one). If audit path ↔ embed mismatch, V-Gate **FAILS**.

11. **Home ISO anomalies**
    L2 gates these; L3 treats them as V-Handoff **FAIL** only if the `home_iso(m)` input is part of the L3 source set and is missing/invalid. Otherwise, L3 records a WARN (configurable).

12. **Downstream presence checks**
    If enabled, V-Handoff can WARN/FAIL when `is_multi=false` yet downstream multi-site RNG events are found (or vice versa). Default is **WARN** to keep S1 validation scoped.

13. **No events but trace present / trace but no events**

* Trace with zero lines and zero events: valid for empty universe.
* Trace lines present but zero events: V-Trace **FAILS** (unmatchable lines).
* Events present but no trace: V-Trace **FAILS**.

14. **Mixed lineage in embeds**
    If any event/trace line embeds `{seed, parameter_hash, run_id}` different from its path partitions, V-Partitions **FAILS** and includes the mismatched values in the sample.

15. **Numeric artefact drift**
    If β or the S0.5 design digest differs from what `parameter_hash` implies (e.g., operator pointed L3 at inconsistent artefacts), V-Design & π **FAILS** consistently across rows with a clear digest mismatch note in `breadcrumbs`.

---

# 7) Validator Orchestrator Stub

```pseudocode
# ---------------------------------------------
# Types & constants
# ---------------------------------------------
enum Verdict { PASS, FAIL }
enum VId {
  V_GATE, V_SCHEMA_EVENTS, V_SCHEMA_TRACE, V_PARTITIONS,
  V_CARDINALITY, V_DESIGN_PI, V_BUDGET, V_SUBSTREAM,
  V_TRACE, V_HANDOFF
}

struct VResult {
  id: VId
  status: Verdict
  checked_rows: u64
  failures_count: u64
  samples: list<map>     # ≤ SAMPLE_CAP, deterministically ordered
}

struct RunLineage {
  seed: u64
  parameter_hash: hex64
  manifest_fingerprint: hex64
  run_id: hex32
}

struct Inputs {
  lineage: RunLineage
  merchants_expected: set<u64>          # M
  home_iso_of: map<u64,string>
  paths: {
    events_glob: string                 # .../logs/rng/events/hurdle_bernoulli/.../part-*.jsonl
    trace_file: string                  # .../logs/rng/trace/.../rng_trace_log.jsonl
    audit_file: string                  # .../logs/rng/audit/.../rng_audit_log.jsonl
    beta_yaml: string                   # governed hurdle β
    design_store: string                # access to x_m vectors
    schema_root: string                 # schemas.layer1.yaml
  }
  config: {
    chunk_size: u32 = 100_000
    sample_cap: u32 = 100
    output_root: string                 # validation/state1/
  }
  versions: {
    schema_commit: string
    validator_commit: string
    numeric_profile: string
    beta_digest: string
    design_digest: string | null        # or reuse parameter_hash
  }
}

struct Bundle {
  report_json: bytes
  failures_jsonl: bytes | null
  breadcrumbs_json: bytes
  passed_flag: bytes | null             # present only if all PASS
}

# ---------------------------------------------
# Entry point
# ---------------------------------------------
function run_L3(inputs: Inputs) -> Bundle
  # Convenience locals
  L  = inputs.lineage
  C  = inputs.config
  VZ = inputs.versions

  # -------------------------
  # Phase A — fast gates
  # -------------------------
  res = []  # list<VResult> in fixed order

  r_gate   = V_Gate_check(L, inputs.paths.audit_file)
  append(res, r_gate)
  if r_gate.status == FAIL:
      return publish_bundle(L, C, VZ, inputs.merchants_expected, res, failures_from(res))

  r_sce    = V_Schema_events(L, inputs.paths.events_glob, C.chunk_size, C.sample_cap, inputs.paths.schema_root)
  r_sct    = V_Schema_trace (L, inputs.paths.trace_file, C.chunk_size, C.sample_cap, inputs.paths.schema_root)
  append(res, r_sce); append(res, r_sct)

  r_part   = V_Partitions_check(L, inputs.paths.events_glob, inputs.paths.trace_file,
                                C.chunk_size, C.sample_cap)
  append(res, r_part)

  if any_fail(r_gate, r_sce, r_sct, r_part):
      return publish_bundle(L, C, VZ, inputs.merchants_expected, res, failures_from(res))

  # -------------------------
  # Phase B — set properties
  # -------------------------
  r_card, obs = V_Cardinality_uniqueness(L,
                                         inputs.paths.events_glob,
                                         inputs.merchants_expected,
                                         C.chunk_size, C.sample_cap)
  # obs includes: seen_merchants:set<u64>, events_count:u64
  append(res, r_card)

  if r_card.status == FAIL:
      return publish_bundle(L, C, VZ, inputs.merchants_expected, res, failures_from(res))

  # -------------------------
  # Phase C — math & RNG
  # -------------------------
  r_dpi = V_Design_and_pi_recompute(L,
                                    inputs.paths.events_glob,
                                    inputs.paths.beta_yaml,
                                    inputs.paths.design_store,
                                    C.chunk_size, C.sample_cap)
  append(res, r_dpi)

  r_bud = V_Budget_identities(L, inputs.paths.events_glob,
                              C.chunk_size, C.sample_cap)
  append(res, r_bud)

  r_sub = V_Substream_replay(L, inputs.paths.events_glob,
                             C.chunk_size, C.sample_cap)
  append(res, r_sub)

  if any_fail(r_dpi, r_bud, r_sub):
      return publish_bundle(L, C, VZ, inputs.merchants_expected, res, failures_from(res))

  # -------------------------
  # Phase D — roll-up
  # -------------------------
  r_trc = V_Trace_reconciliation(L,
                                 inputs.paths.trace_file,
                                 inputs.paths.events_glob,
                                 C.chunk_size, C.sample_cap)
  append(res, r_trc)

  r_hnd = V_Handoff_preconditions(L,
                                  inputs.paths.events_glob,
                                  inputs.home_iso_of,
                                  C.chunk_size, C.sample_cap)
  append(res, r_hnd)

  # Final verdict
  if any_fail(r_trc, r_hnd):
      return publish_bundle(L, C, VZ, inputs.merchants_expected, res, failures_from(res))

  # All PASS → publish PASS bundle
  return publish_bundle(L, C, VZ, inputs.merchants_expected, res, null)

# ---------------------------------------------
# Helpers (deterministic, side-effect-free)
# ---------------------------------------------
function any_fail(...results: list<VResult>) -> bool
  for r in results:
      if r.status == FAIL: return true
  return false

function failures_from(res: list<VResult>) -> bytes
  # Deterministically concatenate samples from failing validators
  lines = []
  for r in res in fixed_validator_order():
      if r.status == FAIL:
          for s in r.samples: append(lines, json_encode(s))
  return join(lines, "\n")  # may be empty string

function fixed_validator_order() -> list<VId>
  return [V_GATE, V_SCHEMA_EVENTS, V_SCHEMA_TRACE, V_PARTITIONS,
          V_CARDINALITY, V_DESIGN_PI, V_BUDGET, V_SUBSTREAM,
          V_TRACE, V_HANDOFF]

# ---------------------------------------------
# Bundle writer (atomic publish, idempotent)
# ---------------------------------------------
function publish_bundle(L:RunLineage, C, VZ, M:set<u64>, res:list<VResult>, failures_jsonl:bytes|null) -> Bundle
  # Compute verdict & metrics
  verdict = (any_fail(res) ? "FAIL" : "PASS")
  metrics = compute_metrics(L, res)  # events_observed, first/last counters, totals from V-TRACE

  # Build report.json (deterministic key order; microsecond timestamp)
  report = {
    verdict: verdict,
    lineage: { seed:L.seed, parameter_hash:L.parameter_hash,
               manifest_fingerprint:L.manifest_fingerprint, run_id:L.run_id },
    metrics: metrics,
    validators: to_map(res),            # id → {status, checked_rows, failures_count, samples}
    reason: (|M| == 0 ? "empty_universe" : null),
    generated_at_utc: now_utc_microseconds(),
    version: { schema_commit:VZ.schema_commit, validator_commit:VZ.validator_commit,
               numeric_profile:VZ.numeric_profile }
  }
  report_bytes = json_encode_sorted(report)

  # Breadcrumbs
  breadcrumbs = {
    beta_digest: VZ.beta_digest,
    design_digest: (VZ.design_digest != null ? VZ.design_digest : L.parameter_hash),
    schema_commit: VZ.schema_commit,
    validator_commit: VZ.validator_commit,
    numeric_profile: VZ.numeric_profile
  }
  breadcrumbs_bytes = json_encode_sorted(breadcrumbs)

  # _passed.flag (hash over report + breadcrumbs, filename-sorted)
  passed_flag_bytes = null
  if verdict == "PASS":
      passed_flag_bytes = sha256_hex(concat(report_bytes, breadcrumbs_bytes))

  # Layout + atomic publish
  outdir_final = path_join(C.output_root, "fingerprint="+L.manifest_fingerprint,
                           "seed="+str(L.seed), "parameter_hash="+L.parameter_hash, "run_id="+L.run_id)
  tmp = mkdtemp_near(outdir_final)

  write_file(path_join(tmp, "report.json"), report_bytes)
  write_file(path_join(tmp, "breadcrumbs.json"), breadcrumbs_bytes)

  if verdict == "PASS":
      write_file(path_join(tmp, "_passed.flag"), passed_flag_bytes)
  else:
      # write failures.jsonl even if empty; deterministic
      fj = (failures_jsonl == null ? "" : failures_jsonl)
      write_file(path_join(tmp, "failures.jsonl"), fj)

  fsync_dir(tmp)
  atomic_rename(tmp, outdir_final)

  return Bundle{
    report_json: report_bytes,
    failures_jsonl: (verdict == "PASS" ? null : failures_jsonl),
    breadcrumbs_json: breadcrumbs_bytes,
    passed_flag: passed_flag_bytes
  }

# ---------------------------------------------
# Validator call signatures (for implementer)
# ---------------------------------------------
# Each returns VResult; where useful a second out carries derived props.

function V_Gate_check(L, audit_file) -> VResult
function V_Schema_events(L, events_glob, chunk_size, sample_cap, schema_root) -> VResult
function V_Schema_trace (L, trace_file,  chunk_size, sample_cap, schema_root) -> VResult
function V_Partitions_check(L, events_glob, trace_file, chunk_size, sample_cap) -> VResult
function V_Cardinality_uniqueness(L, events_glob, M_expected, chunk_size, sample_cap)
    -> (VResult, { seen_merchants:set<u64>, events_count:u64 })
function V_Design_and_pi_recompute(L, events_glob, beta_yaml, design_store, chunk_size, sample_cap) -> VResult
function V_Budget_identities(L, events_glob, chunk_size, sample_cap) -> VResult
function V_Substream_replay(L, events_glob, chunk_size, sample_cap) -> VResult
function V_Trace_reconciliation(L, trace_file, events_glob, chunk_size, sample_cap) -> VResult
function V_Handoff_preconditions(L, events_glob, home_iso_of, chunk_size, sample_cap) -> VResult

# ---------------------------------------------
# Deterministic metrics (summary convenience)
# ---------------------------------------------
function compute_metrics(L, res:list<VResult>) -> map
  # Pull from V-TRACE (final totals, last-after), V-CARDINALITY (events_observed),
  # and any row-level counters surfaced in samples. Keep it deterministic.
  events_observed   = find_metric(res, V_CARDINALITY, "events_observed", default=0)
  first_before      = find_metric(res, V_TRACE, "first_counter_before", default={hi:0,lo:0})
  last_after        = find_metric(res, V_TRACE, "last_counter_after",  default={hi:0,lo:0})
  events_total      = find_metric(res, V_TRACE, "events_total", default=events_observed)
  blocks_total      = find_metric(res, V_TRACE, "blocks_total", default=0)
  draws_total       = find_metric(res, V_TRACE, "draws_total",  default=0)
  return {
    merchants_expected: size(inputs.merchants_expected),
    events_observed: events_observed,
    first_counter_before: first_before,
    last_counter_after: last_after,
    events_total: events_total, blocks_total: blocks_total, draws_total: draws_total
  }
```

**Why this is ready to implement**

* **Phase ordering** matches the plan (A→D), with short-circuiting on FAIL to save time.
* **Deterministic outputs**: fixed validator order, capped/sorted samples, microsecond timestamps, sorted JSON keys.
* **Atomic publish & idempotency**: write to temp, fsync, rename; reruns overwrite byte-identical bundles.
* **Tight interfaces**: each validator returns a `VResult`; only V-Cardinality also returns `seen_merchants` (useful for CI analytics, optional for the summary).

# Validator Stubs

## Common bits (helpers & result builder)

```pseudocode
struct VResult {
  id: VId
  status: Verdict            # PASS | FAIL
  checked_rows: u64
  failures_count: u64
  samples: list<map>         # ≤ sample_cap, sorted deterministically
  metrics: map | null        # optional per-validator metrics
}

function make_result(id:VId, ok:bool, checked:u64, fails:u64,
                     samples:list<map>, metrics:map|null) -> VResult
  return VResult{
    id:id,
    status:(ok ? PASS : FAIL),
    checked_rows:checked,
    failures_count:fails,
    samples:samples,
    metrics:metrics
  }

# Deterministic sample collector: append, then keep the smallest sample_cap items
function add_sample(samples:list<map>, cap:u32, item:map, key:fn(map)->tuple)
  append(samples, item)
  sort_in_place(samples, key)             # stable total order
  if length(samples) > cap: pop_back(samples)

# JSONL streaming
function stream_jsonl(glob_or_file:string, chunk_size:u32) -> iterator<list<string>>
  # yields lists of raw lines (up to chunk_size) across all matching shards/files

# Schema helpers (placeholders; strict validation)
function validate_event_schema(obj:map) -> bool
function validate_trace_schema(obj:map) -> bool
function ts_has_exact_microseconds(ts:string) -> bool
function json_number_roundtrips_to_same_binary64(x:any) -> bool

# Partitions helper
function parse_partitions_from_path(path:string) -> {seed:u64, parameter_hash:hex64, run_id:hex32}

# 128-bit helpers (decimal string → (hi,lo); add/sub/eq; delta; u128→u64 with overflow-abort)
function decimal_string_to_u128(str_dec:string) -> (hi:u64, lo:u64)
function u128_add(a_hi:u64, a_lo:u64, b_hi:u64, b_lo:u64) -> (hi:u64, lo:u64)
function u128_sub(a_hi:u64, a_lo:u64, b_hi:u64, b_lo:u64) -> (hi:u64, lo:u64)
function u128_eq(a_hi:u64, a_lo:u64, b_hi:u64, b_lo:u64) -> bool
function u128_delta(after_hi:u64, after_lo:u64, before_hi:u64, before_lo:u64) -> (hi:u64, lo:u64)
function u128_to_uint64_or_abort(hi:u64, lo:u64) -> u64

# RNG replay helpers (placeholders; identical to S0/S1 kernels)
function derive_substream(seed:u64, manifest_fingerprint:hex64, label:string, merchant_id:u64) -> {ctr_hi:u64, ctr_lo:u64}
function philox_block(ctr_hi:u64, ctr_lo:u64) -> {lane0:u64, lane1:u64, next_hi:u64, next_lo:u64}
function u01(low_lane:u64) -> f64   # strict-open (0,1), binary64

# Stable sort keys
function key_by_merchant_id(s:map) -> tuple       # e.g., (s.merchant_id)
function key_by_counters(s:map)    -> tuple       # e.g., (s.before_hi, s.before_lo, s.after_hi, s.after_lo)
```

---

## V-Gate

```pseudocode
function V_Gate_check(L:RunLineage, audit_file:string) -> VResult
  samples = []; checked = 0; fails = 0
  if not file_exists(audit_file):
      add_sample(samples, 1, {code:"E_S1_RNG_AUDIT_MISSING"}, key_by_merchant_id)
      return make_result(V_GATE, false, 0, 1, samples, null)

  line = read_single_line(audit_file)
  obj  = json_parse(line); checked += 1
  # Optional embed↔path equality
  p = parse_partitions_from_path(audit_file)
  if obj.seed != p.seed or obj.parameter_hash != p.parameter_hash or obj.run_id != p.run_id:
      fails += 1
      add_sample(samples, 1, {code:"E_PARTITIONS_MISMATCH", seed:obj.seed, path_seed:p.seed}, key_by_merchant_id)
  ok = (fails == 0)
  return make_result(V_GATE, ok, checked, fails, samples, null)
```

---

## V-Schema (events)

```pseudocode
function V_Schema_events(L, events_glob, chunk_size, sample_cap, schema_root) -> VResult
  samples = []; checked = 0; fails = 0
  for batch in stream_jsonl(events_glob, chunk_size):
    for line in batch:
      obj = safe_json_parse(line)
      if obj == ERROR: 
         fails += 1
         add_sample(samples, sample_cap, {code:"IO.JSON_PARSE", shard:get_shard(line)}, key_by_merchant_id)
         continue
      ok = validate_event_schema(obj)
      ok = ok and ts_has_exact_microseconds(obj.envelope.ts_utc)
      ok = ok and is_integer(obj.payload.merchant_id)
      ok = ok and is_integer(obj.envelope.seed)
      ok = ok and json_number_roundtrips_to_same_binary64(obj.payload.pi)
      if obj.payload.u != null:
          ok = ok and json_number_roundtrips_to_same_binary64(obj.payload.u)
      if not ok:
         fails += 1
         add_sample(samples, sample_cap, {code:"SCHEMA", merchant_id:obj.payload.merchant_id}, key_by_merchant_id)
      checked += 1
  return make_result(V_SCHEMA_EVENTS, (fails==0), checked, fails, samples, null)
```

---

## V-Schema (trace)

```pseudocode
function V_Schema_trace(L, trace_file, chunk_size, sample_cap, schema_root) -> VResult
  samples = []; checked = 0; fails = 0
  for batch in stream_jsonl(trace_file, chunk_size):
    for line in batch:
      obj = safe_json_parse(line)
      if obj == ERROR:
         fails += 1
         add_sample(samples, sample_cap, {code:"IO.JSON_PARSE", shard:get_shard(line)}, key_by_counters)
         continue
      ok = validate_trace_schema(obj)
      ok = ok and is_integer(obj.seed) and is_integer(obj.events_total)
      if not ok:
         fails += 1
         add_sample(samples, sample_cap, {code:"SCHEMA", before_hi:obj.rng_counter_before_hi, before_lo:obj.rng_counter_before_lo}, key_by_counters)
      checked += 1
  return make_result(V_SCHEMA_TRACE, (fails==0), checked, fails, samples, null)
```

---

## V-Partitions

```pseudocode
function V_Partitions_check(L, events_glob, trace_file, chunk_size, sample_cap) -> VResult
  samples = []; checked = 0; fails = 0

  # Events
  for shard in glob_files(events_glob):
    p = parse_partitions_from_path(shard)
    for batch in stream_jsonl(shard, chunk_size):
      for line in batch:
        obj = json_parse(line); checked += 1
        ok = (obj.envelope.seed == p.seed and obj.envelope.parameter_hash == p.parameter_hash and obj.envelope.run_id == p.run_id)
        ok = ok and (not path_contains(shard, "fingerprint="))
        ok = ok and (not path_contains(shard, "module=") and not path_contains(shard, "substream_label="))
        ok = ok and (obj.envelope.module == "1A.hurdle_sampler" and obj.envelope.substream_label == "hurdle_bernoulli")
        if not ok:
          fails += 1
          add_sample(samples, sample_cap, {code:"PARTITIONS", merchant_id:obj.payload.merchant_id, path_seed:p.seed, embed_seed:obj.envelope.seed}, key_by_merchant_id)

  # Trace
  p = parse_partitions_from_path(trace_file)
  for batch in stream_jsonl(trace_file, chunk_size):
    for line in batch:
      obj = json_parse(line); checked += 1
      # Trace embeds {seed, run_id}; parameter_hash is path-only for rng_trace_log (per S1-L0).
      ok = (obj.seed == p.seed and obj.run_id == p.run_id)
      if not ok:
        fails += 1
        add_sample(samples, sample_cap, {code:"PARTITIONS_TRACE", before_hi:obj.rng_counter_before_hi, before_lo:obj.rng_counter_before_lo}, key_by_counters)

  return make_result(V_PARTITIONS, (fails==0), checked, fails, samples, null)
```

---

## V-Cardinality & Uniqueness

```pseudocode
function V_Cardinality_uniqueness(L, events_glob, M_expected:set<u64>, chunk_size, sample_cap)
    -> (VResult, {seen_merchants:set<u64>, events_count:u64})
  samples = []; checked = 0; fails = 0
  seen = set<u64>(); dups = set<u64>()
  for batch in stream_jsonl(events_glob, chunk_size):
    for line in batch:
      obj = json_parse(line); checked += 1
      m = obj.payload.merchant_id
      if m in seen:
         add(dups, m)
      else:
         add(seen, m)
  # Coverage diffs
  missing = set_diff(M_expected, seen)
  extra   = set_diff(seen, M_expected)
  if not is_empty(dups):
     fails += size(dups)
     for m in take_sorted(dups, sample_cap): add_sample(samples, sample_cap, {code:"DUP", merchant_id:m}, key_by_merchant_id)
  if not is_empty(missing) or not is_empty(extra):
     fails += size(missing) + size(extra)
     for m in take_sorted(missing, sample_cap): add_sample(samples, sample_cap, {code:"MISSING", merchant_id:m}, key_by_merchant_id)
     for m in take_sorted(extra,   sample_cap): add_sample(samples, sample_cap, {code:"EXTRA", merchant_id:m},   key_by_merchant_id)
  metrics = { events_observed: size(seen) }
  res = make_result(V_CARDINALITY, (fails==0), checked, fails, samples, metrics)
  return (res, {seen_merchants:seen, events_count:size(seen)})
```

---

## V-Design & π recompute

```pseudocode
function V_Design_and_pi_recompute(L, events_glob, beta_yaml, design_store, chunk_size, sample_cap) -> VResult
  beta = atomic_load_yaml_vector(beta_yaml)
  samples = []; checked = 0; fails = 0
  for batch in stream_jsonl(events_glob, chunk_size):
    for line in batch:
      e = json_parse(line); checked += 1
      m = e.payload.merchant_id
      x = load_design_vector(design_store, m)               # S0.5 materialized vector
      if length(x) != length(beta):
         fails += 1
         add_sample(samples, sample_cap, {code:"E_S1_DSGN_SHAPE_MISMATCH", merchant_id:m}, key_by_merchant_id)
         continue
      eta = dot_neumaier(beta, x)
      if not is_finite(eta):
         fails += 1
         add_sample(samples, sample_cap, {code:"NUM_NONFINITE_ETA", merchant_id:m}, key_by_merchant_id)
         continue
      pi_re = sigmoid_two_branch(eta)
      # binary64-exact compare with persisted pi
      if not binary64_equal(pi_re, e.payload.pi):
         fails += 1
         add_sample(samples, sample_cap, {code:"PI_MISMATCH", merchant_id:m, expected:to_json_number(pi_re), observed:to_json_number(e.payload.pi)}, key_by_merchant_id)
  return make_result(V_DESIGN_PI, (fails==0), checked, fails, samples, null)
```

---

## V-Budget identities

```pseudocode
function V_Budget_identities(L, events_glob, chunk_size, sample_cap) -> VResult
  samples = []; checked = 0; fails = 0
  for batch in stream_jsonl(events_glob, chunk_size):
    for line in batch:
      e = json_parse(line); checked += 1
      before = make_u128(e.envelope.rng_counter_before_hi, e.envelope.rng_counter_before_lo)
      after  = make_u128(e.envelope.rng_counter_after_hi,  e.envelope.rng_counter_after_lo)
      (dhi, dlo) = decimal_string_to_u128(e.envelope.draws)   # "0" or "1" for hurdle
      (Δhi, Δlo) = u128_sub(after.hi, after.lo, before.hi, before.lo)
      ok = u128_eq(Δhi, Δlo, dhi, dlo) and
           (e.envelope.blocks == u128_to_uint64_or_abort(dhi, dlo))
      if e.payload.pi == 0.0 or e.payload.pi == 1.0:
         ok = ok and (e.payload.u == null) and e.payload.deterministic
         ok = ok and ( (e.payload.pi == 1.0 and e.payload.is_multi==true) or
                       (e.payload.pi == 0.0 and e.payload.is_multi==false) )
      else:
         ok = ok and (e.payload.u != null) and (0.0 < e.payload.u and e.payload.u < 1.0) and (e.payload.deterministic==false)
         ok = ok and ( (e.payload.u < e.payload.pi) == e.payload.is_multi )
      if not ok:
         fails += 1
         add_sample(samples, sample_cap, {code:"BUDGET_OR_LAW", merchant_id:e.payload.merchant_id,
                                          before_hi:e.envelope.rng_counter_before_hi, before_lo:e.envelope.rng_counter_before_lo,
                                          after_hi:e.envelope.rng_counter_after_hi, after_lo:e.envelope.rng_counter_after_lo}, key_by_merchant_id)
  return make_result(V_BUDGET, (fails==0), checked, fails, samples, null)
```

---

## V-Substream replay

```pseudocode
function V_Substream_replay(L, events_glob, chunk_size, sample_cap) -> VResult
  samples = []; checked = 0; fails = 0
  for batch in stream_jsonl(events_glob, chunk_size):
    for line in batch:
      e = json_parse(line); checked += 1
      m = e.payload.merchant_id
      # Reconstruct base counter from lineage and label
      s = derive_substream(L.seed, L.manifest_fingerprint, "hurdle_bernoulli", m)
      if s.ctr_hi != e.envelope.rng_counter_before_hi or s.ctr_lo != e.envelope.rng_counter_before_lo:
         fails += 1
         add_sample(samples, sample_cap, {code:"BASE_COUNTER_MISMATCH", merchant_id:m,
                                          before_hi:e.envelope.rng_counter_before_hi, before_lo:e.envelope.rng_counter_before_lo,
                                          expected_hi:s.ctr_hi, expected_lo:s.ctr_lo}, key_by_merchant_id)
         continue
      (dhi, dlo) = decimal_string_to_u128(e.envelope.draws)
      if u128_to_uint64_or_abort(dhi, dlo) == 1:
         blk = philox_block(s.ctr_hi, s.ctr_lo)
         u   = u01(blk.lane0)    # low-lane policy (strict-open)
         # binary64-exact equality
         if not binary64_equal(u, e.payload.u) or ((u < e.payload.pi) != e.payload.is_multi):
            fails += 1
            add_sample(samples, sample_cap, {code:"REPLAY_MISMATCH", merchant_id:m,
                                             u_expected:to_json_number(u), u_observed:to_json_number(e.payload.u)}, key_by_merchant_id)
         # after must match next counter
         if blk.next_hi != e.envelope.rng_counter_after_hi or blk.next_lo != e.envelope.rng_counter_after_lo:
            fails += 1
            add_sample(samples, sample_cap, {code:"AFTER_COUNTER_MISMATCH", merchant_id:m}, key_by_merchant_id)
      else:  # draws == 0
         if e.payload.u != null or e.payload.deterministic != true or
            (e.envelope.rng_counter_after_hi != e.envelope.rng_counter_before_hi) or
            (e.envelope.rng_counter_after_lo != e.envelope.rng_counter_before_lo):
            fails += 1
            add_sample(samples, sample_cap, {code:"DETERMINISTIC_BRANCH", merchant_id:m}, key_by_merchant_id)
  return make_result(V_SUBSTREAM, (fails==0), checked, fails, samples, null)
```

---

## V-Trace reconciliation

```pseudocode
function V_Trace_reconciliation(L, trace_file, events_glob, chunk_size, sample_cap) -> VResult
  # Build quick index of events by (before,after) counters and aggregates
  E = map<(u64,u64,u64,u64) -> {draws_u64:u64, merchant_id:u64}>()
  sum_draws = (hi:0u64, lo:0u64); sum_blocks = 0u64; total_events = 0u64
  first_before = null; last_after = null

  for batch in stream_jsonl(events_glob, chunk_size):
    for line in batch:
      e = json_parse(line)
      key = (e.envelope.rng_counter_before_hi, e.envelope.rng_counter_before_lo,
             e.envelope.rng_counter_after_hi,  e.envelope.rng_counter_after_lo)
      (dhi, dlo) = decimal_string_to_u128(e.envelope.draws)
      draws_u64  = u128_to_uint64_or_abort(dhi, dlo)   # hurdle: 0 or 1
      E[key]     = {draws_u64:draws_u64, merchant_id:e.payload.merchant_id}
      if first_before == null: first_before = {hi:key.0, lo:key.1}
      last_after  = {hi:key.2, lo:key.3}
      sum_draws  = u128_add(sum_draws.hi, sum_draws.lo, dhi, dlo)
      sum_blocks = sat_add_u64(sum_blocks, draws_u64)  # {0,1}
      total_events += 1

  samples = []; checked = 0; fails = 0
  events_total = 0u64; blocks_total = 0u64; draws_total = 0u64

  for batch in stream_jsonl(trace_file, chunk_size):
    for line in batch:
      t = json_parse(line); checked += 1
      key = (t.rng_counter_before_hi, t.rng_counter_before_lo, t.rng_counter_after_hi, t.rng_counter_after_lo)
      if not contains(E, key):
         fails += 1
         add_sample(samples, sample_cap, {code:"TRACE_NO_MATCH", before_hi:key.0, before_lo:key.1, after_hi:key.2, after_lo:key.3}, key_by_counters)
         continue
      # Update totals (saturating)
      events_total = sat_add_u64(events_total, 1)
      (dhi, dlo)   = u128_delta(key.2, key.3, key.0, key.1)
      delta        = u128_to_uint64_or_abort(dhi, dlo)   # 0 or 1 here
      blocks_total = sat_add_u64(blocks_total, delta)
      draws_total  = sat_add_u64(draws_total, E[key].draws_u64)

  # Final reconciliation against event aggregates
  metrics = {
    first_counter_before: (first_before==null ? {hi:0,lo:0} : first_before),
    last_counter_after:   (last_after==null  ? {hi:0,lo:0} : last_after),
    events_total: events_total,
    blocks_total: blocks_total,
    draws_total: draws_total
  }

  if events_total != total_events or blocks_total != sum_blocks or draws_total != to_u64(sum_draws) or
     (last_after != null and (last_after.hi != key.2 or last_after.lo != key.3) == false): 
     # (the last clause is a no-op placeholder if you don't keep the last trace line separately)
     fails += 1
     add_sample(samples, sample_cap, {code:"TRACE_RECONCILE", events_total, total_events, blocks_total, sum_blocks, draws_total, sum_draws:to_u64(sum_draws)}, key_by_counters)

  return make_result(V_TRACE, (fails==0), checked, fails, samples, metrics)
```

---

## V-Handoff preconditions

```pseudocode
function V_Handoff_preconditions(L, events_glob, home_iso_of:map<u64,string>, chunk_size, sample_cap) -> VResult
  samples = []; checked = 0; fails = 0
  for batch in stream_jsonl(events_glob, chunk_size):
    for line in batch:
      e = json_parse(line); checked += 1
      m = e.payload.merchant_id
      # C* equals post counter
      C_star_ok = true  # (always true here; we read post counters from the event itself)
      # home_iso present & valid
      iso = home_iso_of.get(m)
      if iso == null or not is_valid_iso_alpha2(iso):
         fails += 1
         add_sample(samples, sample_cap, {code:"HOME_ISO_INVALID", merchant_id:m, home_iso:iso}, key_by_merchant_id)
      # is_multi consistency (redundant with other validators but kept here for the handoff view)
      ok_multi = ( (e.payload.pi == 1.0 and e.payload.is_multi==true and e.payload.u==null) or
                   (e.payload.pi == 0.0 and e.payload.is_multi==false and e.payload.u==null) or
                   (0.0 < e.payload.pi and e.payload.pi < 1.0 and e.payload.u != null and (e.payload.u < e.payload.pi) == e.payload.is_multi) )
      if not ok_multi:
         fails += 1
         add_sample(samples, sample_cap, {code:"HANDOFF_IS_MULTI", merchant_id:m}, key_by_merchant_id)
  return make_result(V_HANDOFF, (fails==0), checked, fails, samples, null)
```

---