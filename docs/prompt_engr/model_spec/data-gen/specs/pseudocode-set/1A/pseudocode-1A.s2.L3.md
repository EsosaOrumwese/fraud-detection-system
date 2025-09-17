# S2.L3 — Validator (Read-Only, Evidence-Driven)

## 1) Purpose & Position

L3 **proves**—from **bytes on disk**—that S2 satisfied its contract: lineage/numeric attestations; schema/partition and **path↔embed** discipline; RNG envelope identities (**`blocks` from counters; `draws` as decimal-u128, independent**); per-attempt **Γ→Π** ordering & pairing **by counter intervals**; a **non-consuming** finaliser that **bit-echoes** $(\mu,\phi)$; coverage; and corridor gates. L3 is **read-only** and **fail-fast**: on the first failure it writes **one** canonical Batch-F record and exits; on success it writes only `_passed.flag`.

---

## 2) Scope & Non-Goals

**In scope.** Re-derive lineage (`parameter_hash`, `manifest_fingerprint`) and numeric attestation; validate dictionary/schema/partitions for S2 families; enforce envelope identities and timestamp format; reconstruct attempts and acceptance; verify finaliser echo & non-consumption; check coverage and trace discipline; compute corridor metrics; publish the validation bundle **atomically**.

**Out of scope.** Emitting events, replaying samplers, changing schemas/paths, adding datasets, backfilling partial merchants, or running L2 orchestration—**evidence is produced by L1 (via L0), not L3**.

---

## 3) Authorities & Inputs (read-only)

**Run descriptor (authoritative).** `{seed, parameter_hash, manifest_fingerprint, run_id}` — used to re-compute lineage and to check **path↔embed** equality.

**Evidence streams (dictionary-pinned RNG families).**

* `rng_event_gamma_component` (`#/rng/events/gamma_component`)
* `rng_event_poisson_component` (`#/rng/events/poisson_component`)
* `rng_event_nb_final` (`#/rng/events/nb_final`)
  All three live under partitions **`{seed, parameter_hash, run_id}`**; presence is **gated** by the S1 hurdle (`is_multi==true`). L3 lists/reads these **only via the dictionary** (no path literals).

**Trace stream.** `rng_trace_log` under the **same path partitions**, but its **envelope embeds only `{seed, run_id}`** (`parameter_hash` is **path-only**). Used to verify event→trace pairing and **saturating** totals.

**Schema & envelope rules (JSON-Schema).**

* Payload **numbers are JSON numbers** (no stringified floats).
* `draws` is **decimal uint128** with domain **`^(0|[1-9][0-9]{0,38})$`** (no sign; no leading zeros except `"0"`).
* Timestamps are **RFC 3339 UTC with exactly 6 fractional digits** (**microseconds**, **truncated**, **trailing `Z`**).
* Envelope identity: **`blocks == u128(after) − u128(before)`** (checked as an unsigned-128 delta).
* **No Avro authority**—validation is against the JSON-Schema surfaces only.

**Upstream artefacts for recomputation.** Governed coefficient YAMLs and fixed design vectors to recompute $(\mu,\phi)$ deterministically (**Neumaier dots + `exp` in binary64; FMA-off, fixed order**) and require **bit-equality** with `nb_final.{mu, dispersion_k}`. Substream labels/modules come from the frozen S2 literals (`gamma_nb` / `poisson_nb` / `nb_final`).

**Gating source.** Hurdle stream `rng_event_hurdle_bernoulli` confirms presence/uniqueness and `is_multi` for **branch purity**: S2 evidence exists **iff** `is_multi==true`.

**Embed-only fields.** `module`, `substream_label`, and `manifest_fingerprint` are **embedded-only**; they never appear in path partitions.

---

## 4) Outputs & Bundle Layout

**What L3 writes (and only this):**

* **Success bundle (validation):** a small, read-only bundle under
  `…/validation/fingerprint={manifest_fingerprint}/seed={seed}/run_id={run_id}/`
  containing the validator’s artefacts (e.g., `validator_report.json`, optionally `corridors.json`, and small summaries strictly **derivable** from evidence).
  The bundle is finalized by writing **`_passed.flag`** whose **content equals the SHA-256** of the **ASCII-sorted (by relative path) raw bytes** of **all other files** in the bundle (i.e., the hash **excludes** `_passed.flag`). `_passed.flag` is written **last**.

* **Failure record (Batch-F):** on the **first** failing check, write exactly **one** canonical Batch-F failure payload (plus sentinels) under the same `fingerprint/seed/run_id` scope, then **exit**. No success bundle is produced in this case (and no `_passed.flag`).

**Atomicity & idempotence:**

* Publish is **atomic**: stage files in a hidden temp area, compute the bundle SHA-256, then atomically move the set and write `_passed.flag`. No partial bundles or stray temp files may remain.
* Re-running L3 over the same bytes reproduces the **same failure** (same payload) or the **same success** (same `_passed.flag` content).
* L3 never adds business datasets, never rewrites producer outputs, and never emits RNG evidence.

---

## 5) Validator Order (fail-fast pipeline)

> Checks run in this exact order. The validator stops at the **first** failure and writes one Batch-F record.

**V0 — Lineage & Numeric Policy**
Recompute `parameter_hash` and `manifest_fingerprint` exactly; verify numeric attestation (binary64, RNE, FMA-OFF, no FTZ/DAZ, fixed evaluation order).

**V1 — Dictionary / Schema / Partitions**
All S2 families exist only under partitions `{seed, parameter_hash, run_id}`; payload types match **JSON-Schema** (**numbers are numbers**; `draws` is decimal-u128 with domain `^(0|[1-9][0-9]{0,38})$`); no unknown/extra fields; **no Avro authority**.

**V2 — Gating, Cardinality & Idempotence**
S2 evidence appears **iff** hurdle is present/unique and `is_multi==true` (branch purity). Per (run, merchant): **≤ 1** `nb_final`.

**V3 — Path↔Embed Equality & Envelope Invariants**
Events: path partitions equal embedded `{seed, parameter_hash, run_id}`; `blocks == u128(after) − u128(before)`; timestamps are **RFC-3339 UTC with exactly 6 fractional digits** (microseconds), **truncated**, **trailing `Z`**.
Trace: path `{seed, parameter_hash, run_id}`, **envelope embeds `{seed, run_id}` only** (`parameter_hash` path-only).

**V4 — Attempt Ordering & Pairing (Γ→Π)**
Within a merchant, reconstruct attempts **solely by counter intervals** (not time): each **valid** attempt is exactly **Gamma → Poisson**; counters monotone/non-overlapping per family; **no cross-label counter chaining**.

**V5 — Finaliser Contract (Echo & Non-Consumption)**
`nb_final`: `before==after`, `blocks=0`, `draws:"0"`. Recompute `(μ,φ)` (Neumaier dots + `exp` in binary64) from design vectors & governed coeffs; require **bit-equality** with `nb_final.{mu, dispersion_k}`.

**V6 — Coverage & Outcome Reconstruction**
If final exists: there are ≥1 prior Γ **and** ≥1 prior Π; accepted attempt’s `K` equals `n_outlets`; `nb_rejections` equals the count of rejected attempts with `K∈{0,1}`.

**V7 — Trace Discipline**
Exactly **one** cumulative **saturating** trace append **after each event** (writer-driven); per `(module, substream_label)` the **final** row is monotone; trace-implied counts agree with observed events.

**V8 — Corridors (policy thresholds)**
Run-level gates: overall rejection rate `ρ ≤ 0.06`; `p99(r) ≤ 3`; (optional) one-sided CUSUM within configured `(k,h)`.

**V9 — Atomic Publish**
Bundle complete; `_passed.flag` content equals the bundle SHA-256; no temp debris; bundle partitions match the run descriptor.

---

## 6) Loading & Partition Hygiene

**Read via the dictionary—never by path.**
All file discovery (events, trace, hurdle, coeff/design inputs, and validation-bundle base) comes from the **dataset dictionary**. L3 must not hand-compose paths or join strings; it asks the dictionary for dataset **ID → path template** and **partitions**, then iterates accordingly. **No path literals** anywhere.

**Streaming, bounded memory.**
Validators stream JSONL and fold statistics with bounded state:

* Iterate **per (seed, parameter\_hash, run\_id, merchant\_id, family)** window.
* Keep only rolling state needed for a check (e.g., last `(before_hi, before_lo)`, a tiny Γ→Π pairing window per family, and per-merchant counters for coverage).
* For bundle hashing, read files in a **stable order** (below); never load the whole bundle in memory.

**Stable, deterministic ordering.**
When order is required for determinism (bundle hashing, per-merchant logs, pairing ties), use:

* **ASCII ascending** of **relative file paths** within a dataset, then
* **unsigned lexicographic** on `(rng_counter_before_hi, rng_counter_before_lo)` for within-merchant ordering (never timestamp or mtime).

**Enumerate only evidence the dictionary says exists.**

* **Events (Gamma/Poisson/Final):** partitions are **exactly** `{seed, parameter_hash, run_id}`.
* **Trace:** same path partitions; **envelope embeds only `{seed, run_id}`** (parameter\_hash is **path-only**).
* **Hurdle:** presence/uniqueness and `is_multi` for branch purity.
  If the dictionary marks a dataset **required** for S2 and it’s missing, fail **immediately** (structural).

**Partition hygiene guards.**
As you stream each row:

* Parse envelope `{seed, parameter_hash, run_id}` and assert **path↔embed equality** (for **trace**, assert the embed set is `{seed, run_id}` only).
* Reject rows with extra/missing partitions, unexpected dataset IDs, or invalid timestamps: `ts_utc` must be **RFC-3339 UTC with exactly 6 fractional digits** (microseconds), **truncated**, and **trailing `Z`**.
* Never coerce types: **numbers must be numbers**; `draws` must be a **decimal uint128** string with domain `^(0|[1-9][0-9]{0,38})$`; counters are **unsigned** 64-bit halves.

**No producer state.**
Do not consult producer-side caches, RNG states, or L2 logs. All checks must be provable from **bytes on disk** + dictionary/schemas + governed artefacts.

---

## 7) V0 — Lineage & Numeric Policy

> **Fail-fast gate.** Before looking at any S2 evidence, prove the run’s identity and math profile. Any failure here is **terminal**.

### V0.1 Recompute `parameter_hash` (governed artefacts)

**Goal:** independently recompute the run’s **parameter set digest** and compare to the run descriptor.

**Method (deterministic):**

1. Build the governed set 𝓟 of S2 inputs (coeff YAMLs, gating-policy YAMLs, any priors/constants S2 relies on).
2. For each element in 𝓟: read **raw bytes**, compute SHA-256, and form a record `(logical_name, byte_len, sha256hex)`.
3. **ASCII-sort** the records by `logical_name`; serialize canonically (e.g., newline-delimited UTF-8).
4. Hash that canonical stream with SHA-256 ⇒ `parameter_hash*`.
5. **Assert:** `parameter_hash* == parameter_hash` from the run descriptor.

**Fail on:** missing/ unreadable bytes, zero-length where forbidden, duplicate `logical_name`, or hash mismatch.

### V0.2 Recompute `manifest_fingerprint` (artefacts opened pre-run)

**Goal:** confirm the broader **manifest** exactly matches what producers declared.

**Method (deterministic):**

1. Build artefact set 𝓐 actually opened prior to/at S0 (e.g., tz/OSM, rasters, licences, S2 lookups).
2. For each artefact: read **raw bytes**, derive `(logical_name, byte_len, sha256hex)`.
3. Form the canonical stream: **ASCII-sorted** 𝓐 records **+** the raw **32-byte** repo commit **+** the raw **32-byte** `parameter_hash` bytes (**not** hex).
4. SHA-256 over that canonical stream ⇒ `manifest_fingerprint*`.
5. **Assert:** `manifest_fingerprint* == manifest_fingerprint` from the run descriptor.

**Fail on:** missing artefact, size/hash mismatch, commit length ≠ 32 bytes, or fingerprint mismatch.

### V0.3 Numeric policy attestation (math profile)

**Goal:** verify the pinned math environment guaranteeing replayability.

**Required flags (all must be true):**

* IEEE-754 **binary64** everywhere
* **RNE** (round-to-nearest, ties-to-even)
* **FMA OFF**; **no FTZ/DAZ**
* **Fixed evaluation order** (no vectorized/autoparallel reductions)
* **Neumaier** reductions for sums/dots where specified
* Deterministic `exp/log/log1p/expm1/sqrt/lgamma` under the pinned profile

**Source:** a small **attestation JSON** (written upstream) with booleans for each flag **and** a reproducible signature (env+build hash). L3 asserts every required field exists and is `true`.

**Fail on:** attestation missing/malformed, or any required flag `false`/absent.

### V0.4 RNG audit presence (run-level sanity)

**Goal:** confirm the run’s RNG was bootstrapped exactly once **before** any S2 events.

**Checks:**

* There exists an **rng audit** row for `{seed, parameter_hash, run_id}` (per S0/S1 policy).
* If the dictionary requires a **single** audit row per run, assert **exactly one**; else assert **≥ 1** and **monotone** counters.
* The audit `ts_utc` is RFC-3339 microseconds (6 digits, `Z`) and **strictly earlier** than the **minimum** S2 event timestamp.

**Fail on:** no audit; duplicate/ill-formed audit entries; or audit timestamp **after** the first S2 event.

---

### V0 Failure mapping (Batch-F)

* **Lineage mismatch** (`parameter_hash` or `manifest_fingerprint`) → `F_lineage_mismatch` (run-scoped, **atomic abort**).
* **Numeric policy fail** → `F_numeric_policy` (run-scoped, **atomic abort**).
* **Audit discipline fail** → `F_rng_audit_missing_or_late` (run-scoped, **atomic abort**).

On any V0 failure: write **one** Batch-F record (run-scoped) with a minimal, canonical payload (recomputed vs declared values, missing keys, or failing booleans) and **exit**.

---

## 8) V1 — Dictionary / Schema / Partitions

**Goal.** Before any deeper reasoning, prove every S2 file you will read is exactly the dataset the **dictionary** says it is, and every row conforms to the **JSON-Schema** anchor for that family. **No path literals; no Avro authority; no extra fields.**

**What to check (streaming, read-only):**

* **Dictionary presence & partitions (dataset level)**

  * Only these S2 RNG families are consulted:
    `rng_event_gamma_component`, `rng_event_poisson_component`, `rng_event_nb_final`, and `rng_trace_log`.
  * Their **path partitions** are **exactly** `{seed, parameter_hash, run_id}` (trace uses the same partitions on disk).
  * No extra/missing partition keys; no unexpected dataset IDs. *(Path↔embed equality is verified later in V3.)*

* **Schema/type discipline (row level)**

  * Validate against the **JSON-Schema** for the family:

    * All float payload fields (e.g., `alpha`, `gamma_value`, `lambda`, `mu`, `dispersion_k`) are **JSON numbers**, not strings.
    * `draws` is a **decimal unsigned 128-bit** string with domain `^(0|[1-9][0-9]{0,38})$`; it must parse to u128.
    * Counter halves are **unsigned 64-bit** integers: `rng_counter_before_{hi,lo}`, `rng_counter_after_{hi,lo}`.
    * `ts_utc` is **RFC-3339 UTC** with **exactly 6** fractional digits (microseconds), **truncated**, trailing **`Z`**.
    * Required keys present; **no extra/unknown keys**.
  * Context literals:

    * Gamma/Poisson payloads carry `context:"nb"` (and Gamma also `index:0`).
    * Labels/modules come from the **closed set** fixed for S2 (referenced symbolically; do not hand-type).

* **Trace schema (row level)**

  * `rng_trace_log` rows conform to the trace schema; totals are **unsigned 64-bit**; and the **envelope embeds only `{seed, run_id}`** (not `parameter_hash`) — `parameter_hash` appears **only** in the **path**.

**How to run it (code-agnostic, streaming):**

1. For each family, obtain the path template and partitions from the dictionary; enumerate files for `{seed, parameter_hash, run_id}`.
2. Stream JSONL; for each row, validate against the family’s JSON-Schema. Reject on first schema/type violation.
3. For trace, enforce the different **embed set** (envelope `{seed, run_id}` only).

**Failure mapping (fail-fast):**

* Unknown dataset / partition-set mismatch → **F\_schema\_or\_partition** (run).
* Schema/type violation (stringified float, bad `draws`, missing/extra fields, bad `ts_utc`) → **F\_schema\_or\_partition** (run).
* Trace envelope contains `parameter_hash` or otherwise malformed → **F\_schema\_or\_partition** (run).

---

## 9) V2 — Gating, Cardinality & Idempotence

**Goal.** Enforce presence logic and **one-finaliser** semantics from the bytes: only **gated** merchants may have S2 evidence, and **at most one** `nb_final` per merchant/run. This establishes branch-purity and resume/idempotence before deeper checks.

**What to check (read-only):**

* **Presence gate (branch purity)**

  * Build the hurdle index for the run (presence & uniqueness per merchant).
  * **Rule:** S2 evidence (any Gamma/Poisson/Final rows) may appear **iff** a hurdle exists and `is_multi == true`.
  * If any S2 row exists for a merchant with no/duplicate hurdle or `is_multi==false` → **violation**.

* **Hurdle uniqueness**

  * Exactly **one** hurdle row per merchant in this run scope; **duplicates or absence** are **terminal** for S2 validation.

* **Finaliser cardinality (idempotence)**

  * For each `(seed, parameter_hash, run_id, merchant_id)`, count `nb_final` rows:

    * **Require:** count ∈ {0,1}. `count > 1` → **multiple finalisers** violation.

* **Optional early hygiene**

  * If policy requires, record whether a merchant has *components with no finaliser*. Do **not** fail here—coverage/outcome logic handles semantics later. Here we only enforce **“≤ 1 finaliser”** and **branch purity**.

**How to run it (code-agnostic, streaming):**

1. Stream hurdle once; build `H[merchant_id] = {present:bool, is_multi:bool, unique:bool}`.
2. One streaming pass over S2 families keyed by `(merchant_id)`:

   * If `H[m].is_multi != true` and any S2 row for `m` is seen → **branch purity** failure.
   * Maintain a tiny `final_count[m]` for `nb_final`; if it exceeds 1 → **multiple finalisers** failure.

**Failure mapping (fail-fast):**

* Hurdle absent/non-unique or `is_multi==false` with any S2 evidence → **F\_branch\_purity** (run).
* Multiple `nb_final` for a merchant/run → **F\_multiple\_finaliser** (run).

**Notes & boundaries:**

* **Do not** require a finaliser to exist here; a gated merchant may still have no finaliser (e.g., crash). Later sections (Coverage & Outcome) decide whether that state is acceptable.
* This stage **does not** inspect counter math or attempt pairing; those are V3/V4. It only enforces **who** is allowed to have S2 bytes and the **single-final** rule.

---

## 10) V3 — Path↔Embed Equality & Envelope Invariants

**Goal.** Prove, row-by-row, that every S2 event’s **path partitions equal its embedded lineage**, and that each envelope is internally consistent. (Do this **before** any ordering/pairing.)

**What to prove per *event* row (streaming):**

* **Path↔embed equality (events).** Path partitions are **exactly** `{seed, parameter_hash, run_id}` and **equal** the envelope trio `seed`, `parameter_hash`, `run_id`.
* **Embed set (trace).** Trace files use the same path partitions, but each **trace row’s envelope embeds only `{seed, run_id}`** (parameter\_hash is path-only).
* **Counters & blocks.**
  Parse `rng_counter_before_{hi,lo}` and `rng_counter_after_{hi,lo}` as u64 halves; form u128 `before`, `after`. Require `after > before` for **all** component events; require `after == before` for the finaliser.
  Check **identity:** `blocks == (after − before)` (as u128 → u64) for every row.
* **Draws (independent of blocks).**
  `draws` is a **decimal unsigned 128-bit** string. Parse to u128 successfully for every row.
  Do **not** attempt `draws == blocks` (that identity must **not** hold in general). Only assert:
  – Component rows: `draws > 0`.
  – Finaliser: `draws == 0`.
* **Timestamp & types.** `ts_utc` is RFC3339 with **exactly 6** fractional digits and trailing `Z`. All numeric payload fields (`alpha`, `gamma_value`, `lambda`, `mu`, `dispersion_k`, …) are **JSON numbers** (not strings). No extra/unknown keys.
* **Closed literals.** `module` and `substream_label` belong to the closed S2 set; Gamma/Poisson payloads carry `context:"nb"` (Gamma also `index:0`).

**Streamed procedure (code-agnostic):**

1. For each dataset family (Gamma, Poisson, Final, Trace), obtain file list from the **dictionary** for the target `{seed, parameter_hash, run_id}`; never hand-compose paths.
2. Stream JSONL; for each row, perform:

   * Path↔embed checks (events; and the trace embed set rule).
   * Counter parse; compute u128 `before/after`; verify `blocks == after − before`.
   * `draws` parse to u128; check **>0** for components; **==0** for final.
   * Schema/type & timestamp checks; closed-set literal checks.
3. Fail fast on the **first** violation (run-scoped).

---

## 11) V4 — Attempt Reconstruction & Ordering (Γ→Π)

**Goal.** Reconstruct **attempts** for each gated merchant using **counter intervals only** (never timestamps or file order), and prove the Γ→Π order per valid attempt with no cross-label coupling mistakes.

**Definitions.** For a row `r` define the u128 interval $I(r) = [\,\text{before}(r),\,\text{after}(r)\,)$. Within a merchant:

* Let $\{\Gamma_t\}$ be the Gamma rows (label `gamma_nb`) **sorted by** `before`.
* Let $\{\Pi_s\}$ be the Poisson rows (label `poisson_nb`) **sorted by** `before`.

**Required inequalities (per valid attempt $t$):**

$$
\text{before}(\Gamma_t) \;<\; \text{after}(\Gamma_t) \;\le\; \text{before}(\Pi_t) \;<\; \text{after}(\Pi_t).
$$

This encodes **Γ then Π** and disallows overlaps or reversals. (Finaliser is handled in V5; do not mix it into attempts.)

**Pairing algorithm (two pointers; streaming-friendly):**

```
pairs = []
j = 0  # index into Poisson rows
for each Gamma row G in ascending before:
    # advance Poisson cursor until its before >= after(G)
    while j < len(Poisson) and before(Poisson[j]) < after(G):
        # A Poisson that starts before Gamma ends cannot pair to this Gamma.
        j += 1
    if j == len(Poisson): break  # no partner; Gamma-only terminal case handled later

    P = Poisson[j]
    # Validate Γ→Π inequalities for this candidate pair
    require after(G) <= before(P)  and  before(P) < after(P)

    # Record attempt; move to next Poisson for next Gamma
    pairs.append((G,P))
    j += 1
```

**What must hold after pairing:**

* **Cardinality per attempt:** exactly **one** Γ and exactly **one** Π per **valid** attempt (in order Γ→Π).
  – A **Gamma-only terminal** (no subsequent Π satisfying the inequality) is permitted **only** as the λ-invalid pattern handled later (see §17).
  – A Π with **no preceding** Γ interval satisfying `after(Γ) ≤ before(Π)` is **invalid** (ordering error).
* **Monotone/Non-overlap per family:** within each label, intervals are strictly monotone by `before`, and **non-overlapping**:
  $\text{after}(r_k) \le \text{before}(r_{k+1})$ for consecutive rows in the **same** family.
* **No cross-label counter chaining:** counters advance independently per substream; do **not** rely on Γ’s counters to explain Π’s beyond the pairing law above. (Pairing is a constraint, not a shared counter.)

**Outputs of V4 (for later checks):**

* The paired list `pairs` per merchant (each as `(Γ_row, Π_row)`), in **attempt order**.
* The set of **rejected attempts** = pairs where the Poisson payload has $K \in \{0,1\}$.
  (Used in V6 Coverage to reconstruct `r = #rejections` and the accepted $N$.)

**Failure conditions (fail-fast):**

* Any Π paired to **multiple** Γ, or any Γ paired to **multiple** Π.
* A Π with **no** eligible Γ (`before(Π) < after(last Γ)`).
* A Γ with a Π that **violates** $\text{after}(\Gamma) \le \text{before}(\Pi)$ or any per-family **overlap** / non-monotone counter.
* Any reliance on timestamps/file order to force pairing (pairing must be provable by **counter intervals alone**).

These two sections together guarantee that each event row is self-consistent (V3) and that, for each gated merchant, attempts can be reconstructed deterministically and respect the **Γ→Π** order with clean counter hygiene (V4).

---

## 12) V5 — Finaliser Contract (Echo & Non-Consumption)

**Goal.** For each merchant that has a finaliser row, prove both parts of the contract:

1. the finaliser **consumes nothing**; and
2. it **echoes** the deterministic NB parameters $(\mu,\phi)$ **bit-for-bit**.

**What to check (per `nb_final` row, streaming):**

* **Non-consumption (envelope):**
  `after == before`, `blocks == 0`, and `draws == "0"` (decimal u128).
  (Already schema-validated as numbers/decimal strings; here we enforce the identity.)
* **Echo equality (payload):**
  Recompute $(\mu,\phi)$ using the governed coefficients and the merchant’s frozen design vectors:

  $$
  \mu=\exp(\beta_\mu^\top x^{(\mu)}),\qquad \phi=\exp(\beta_\phi^\top x^{(\phi)}),
  $$

  with **binary64**, fixed-order **Neumaier** dots and **no FMA**. Require **bit equality** with `nb_final.mu` and `nb_final.dispersion_k` (not tolerance).
* **Closed literals:** the row’s `module` and `substream_label` belong to the fixed S2 set (`1A.nb_sampler` / `nb_final`).
* **Type discipline:** payload floats are JSON **numbers** (not strings).

**Procedure (streaming, read-only):**

1. Parse counters; form u128 `before/after`; check `after == before`; check `blocks == 0`.
2. Parse `draws` to u128; check equals 0.
3. Load `x_mu, x_phi` and `β_mu, β_phi` (frozen shapes, governed); compute $(\mu^*,\phi^*)$ with Neumaier+`exp` in binary64; check **bit-equality** against payload.

**Failure mapping (fail-fast):**

* Any of `{after≠before, blocks≠0, draws≠"0"}` → **F\_finaliser\_contract** (merchant; terminal for that merchant).
* Echo mismatch (bitwise) or bad shapes/NaNs in inputs → **F\_finaliser\_contract** (merchant).

---

## 13) V6 — Coverage & Outcome Reconstruction

**Goal.** From the paired attempts (Γ→Π) and the finaliser, reconstruct the outcomes and prove they agree with the finaliser payload and coverage rules.

**Inputs:** the `pairs` produced by V4 for this merchant (each `(Γ_row, Π_row)`), in attempt order.

**Definitions:**

* **Rejected attempts:** those with Poisson payload $K\in\{0,1\}$.
* **Accepted attempt:** the **first** pair with $K\ge 2$ (if any).
* **r:** number of rejections before acceptance.
* **N:** $K$ at the accepted attempt.

**What to enforce (per merchant):**

* **If a finaliser exists:**

  * **Coverage precondition:** there must be **≥1 Γ and ≥1 Π prior** to the finaliser (already ensured by pairing; assert again here if needed for clarity).
  * **Outcome match:**
    `nb_final.n_outlets == N` and `nb_final.nb_rejections == r`.
  * **No components after finaliser:** there must be **no Γ/Π rows whose intervals begin after** the finaliser’s `before` counter (producer must stop emitting once finalised).
* **If no finaliser exists:**

  * If an **accepted attempt** exists (some $K\ge 2$), then the run is **incomplete** → failure (finaliser missing).
  * If **all observed attempts are rejected** and the stream ends (crash/partial), treat as **partial components** (policy terminal; usually run abort).
  * If a **Gamma-only terminal** (λ-invalid) was detected (Gamma present without an eligible Π per V4’s pairing law), classify as **numeric invalid** for that merchant (already handled by earlier stage/policy).

**Procedure (streaming, read-only):**

1. Walk `pairs` once; accumulate `r` until the first $K\ge 2$. If no such $K$ is found, mark `accepted = false`.
2. If finaliser exists: parse its envelope `before`; assert no component interval starts after this `before`. Check `n_outlets == N` and `nb_rejections == r`.
3. If finaliser does **not** exist:

   * If `accepted == true` → **missing finaliser** failure.
   * Else if any Γ/Π exist → **partial components** failure (policy terminal).
   * Else (no S2 evidence for a gated merchant) → branch-purity/gating likely failed earlier; treat per V2 outcome.

**Failure mapping (fail-fast):**

* `n_outlets` or `nb_rejections` mismatch → **F\_coverage** (merchant).
* Components after finaliser → **F\_coverage** (merchant) or **F\_envelope\_invariant** if counters regress.
* Missing finaliser when `accepted == true` → **F\_coverage** (merchant).
* Partial components (no finaliser; some attempts present but no acceptance) → **F\_partial\_components** (run policy: usually run abort).

**Outputs to later checks:**

* Per-merchant tuple `{accepted:bool, N?:i64, r?:i64}` for corridor metrics and any roll-ups.
* Counts needed for V8 corridors (overall rejection rate; p99 of `r`).

---

## 14) V7 — Trace Discipline

**Goal.** Prove the writer/trace discipline from bytes: **one** cumulative trace append per event; correct embed set; monotone **saturating** totals; and agreement between events and trace.

**What to verify (read-only, streaming):**

* **Embed sets & partitions**

  * Trace paths are partitioned by `{seed, parameter_hash, run_id}`; each **trace row embeds only `{seed, run_id}`** (no `parameter_hash` in the envelope).
  * `module`/`substream_label` are from the **closed** S2 set (Gamma/Poisson/Final labels & modules).

* **Per-event → per-trace pairing**

  * For each event row `e` (Gamma/Poisson/Final), there exists **exactly one** trace row `t` with the **same** `(module, substream_label, seed, run_id)` and the **same** counter interval:

    * `t.before == e.before` (hi/lo halves match)
    * `t.after  == e.after`
  * No extra trace rows without a matching event interval; no missing trace rows.

* **Monotone, saturating totals (per (module, substream\_label))**

  * Let `(events_total, blocks_total, draws_total)` be the trace totals in counter order.
  * **Monotone:** all three totals are non-decreasing; `events_total` increments by **1** per matched event.
  * **Exact or saturated sums:**

    * `blocks_total` equals the running sum of `blocks` (from event envelopes), or **UINT64\_MAX** once the sum would overflow (saturation).
    * `draws_total` equals the running sum of `draws_u64`, where `draws_u64 := u128_to_uint64_or_abort(draws)`; after overflow, it remains **UINT64\_MAX** (saturation).
  * **Finaliser effect:** for `nb_final` rows, `blocks == 0` and `draws == "0"`, so only `events_total` increments; `blocks_total`/`draws_total` remain unchanged.

* **No per-event “extra” trace streams**

  * Exactly **one** cumulative trace row per event. No duplicate/parallel trace series for the same `(module, substream_label)`.

**Procedure (code-agnostic):**

1. Enumerate trace files via the **dictionary** for `{seed, parameter_hash, run_id}`; stream in any order; group rows by `(module, substream_label)`; within each group, **sort by `before` counter** (hi,lo) to enforce determinism.
2. Build an index from event rows → expected `(before, after)` pairs for each `(module, substream_label)` (you already validated envelopes in V3).
3. For each event interval, find exactly one matching trace row; check the totals step against prior totals with the saturation rule.

**Failure mapping (fail-fast):**

* Trace row embeds `parameter_hash`, wrong embed set, or wrong partitions → **F\_schema\_or\_partition** (run).
* Missing/extra trace row for an event interval; non-monotone totals; wrong increments; wrong saturation; or duplicate trace streams → **F\_trace\_discipline** (run).

---

## 15) V8 — Corridors (policy thresholds)

**Goal.** Check run-level realism gates over realised evidence, using only **finalised merchants** (those with `nb_final`). These are policy thresholds, not schema checks.

**Inputs for metrics:** For each merchant with a valid `nb_final`, collect

* `r_m := nb_final.nb_rejections` (int ≥ 0),
* `N_m := nb_final.n_outlets` (int ≥ 2).
  Attempt count for that merchant: `A_m := r_m + 1` (rejections plus the accepted attempt).

**Metrics (run-level):**

* **Overall rejection rate:**

  $$
  \rho \;=\; \frac{\sum_m r_m}{\sum_m (r_m + 1)} \;=\; \frac{\sum_m r_m}{\sum_m A_m}.
  $$
* **Tail heaviness (p99):** empirical 99th percentile of `{ r_m }` across finalised merchants.
  Implementation: sort the `r_m` vector; take index `ceil(0.99·M)` with `M = #finalised merchants`.
* **CUSUM (one-sided, optional per policy):** sequence merchants in a deterministic order (e.g., ascending `merchant_id`) and compute

  $$
  S_0 = 0,\quad S_{t} = \max\{0,\, S_{t-1} + (r_{m_t} - k)\},
  $$

  where `k` is the reference level (drift allowance). **Pass** if `\max_t S_t \le h`.

**Thresholds (policy defaults):**

* $\rho \le 0.06$
* $p99(r) \le 3$
* CUSUM: $\max_t S_t \le h$ for configured `(k,h)` (e.g., `k=0.5, h=5` — **use the pinned policy values** for your run).

**Edge handling:**

* If **no merchants finalised** (`M=0`): corridors are **undefined**; treat as terminal (run incomplete) or skip corridors per your policy. (In practice, V6/V9 will already fail this run; corridors can mark as **F\_corridor\_breach\:insufficient\_data** if you require an explicit code.)
* Exclude any **non-finalised** merchants from these metrics (their outcomes aren’t defined).

**Procedure (read-only):**

1. Stream `nb_final` rows; for each, parse `nb_rejections` and `n_outlets`; validate types (already done in V1/V5).
2. Aggregate $\sum r_m$, $\sum A_m$, and the vector `{ r_m }`.
3. Compute `ρ`, `p99(r)`, and the CUSUM statistic; compare to thresholds.

**Failure mapping (fail-fast):**

* `ρ > 0.06` → **F\_corridor\_breach\:rho** (run).
* `p99(r) > 3` → **F\_corridor\_breach\:p99** (run).
* CUSUM threshold exceeded → **F\_corridor\_breach\:cusum** (run).
* Corridor computation impossible due to no finals (policy) → **F\_corridor\_breach\:insufficient\_data** (run), unless explicitly disabled.

**Outputs to publish bundle:**

* Small JSON (e.g., `corridors.json`) with `{ rho, p99_r, cusum_max, thresholds, M, sum_rejections, sum_attempts }`, used only for transparency (not an authority file).
* These numbers are **derived** from evidence and do not alter validation outcomes except via the corridor checks above.

---

## 16) V9 — Atomic Publish

**Goal.** Publish the L3 *result* atomically: either (a) a complete validation bundle with a correct `_passed.flag`, or (b) exactly **one** failure record. Never both; never partials.

**Bundle scope & path (dictionary-derived):**
`…/validation/fingerprint={manifest_fingerprint}/seed={seed}/run_id={run_id}/` (no hand-typed paths).

**Success path (deterministic sequence):**

1. **Assemble files** for the bundle (e.g., `validator_report.json`, optional `corridors.json`, any *derived* summaries).

   * Files must be reproducible from evidence (no host timestamps in content).
2. **Stable ordering:** list bundle files (excluding `_passed.flag`) in **ASCII ascending** of relative paths.
3. **Hash:** read each file’s **raw bytes** in that order; stream into SHA-256 → `BUNDLE_SHA256`.
4. **Atomic publish:**

   * Write files to a temp directory under the bundle path (hidden name).
   * Write `_passed.flag` whose **content is exactly `BUNDLE_SHA256`** (hex, lowercase, no newline policy per your standard).
   * **Atomic move/rename** the temp directory into place.
5. **Cleanliness:** no temp debris remains; permissions consistent.

**Failure path:** on first validator failure earlier, write the **single** Batch-F record (+ sentinels) to the same scope and **exit**; do **not** write `_passed.flag`.

**Checks (L3 self-verification before exiting success):**

* Re-open the published bundle, recompute `SHA-256` over the same ASCII-sorted file list, and confirm it equals the `_passed.flag` content.
* Confirm path partitions equal `{seed, parameter_hash, run_id}` and match the run descriptor.

**Fail-fast mapping:** any mismatch, partial publish, missing `_passed.flag`, stale temp files, or wrong partitions ⇒ **F\_publish\_atomicity** (run-scoped, atomic abort).

---

## 17) λ-Invalid & Partial Components Classification

**Goal.** Classify edge cases from evidence without guessing producer state; keep rules orthogonal to acceptance.

**A. λ-invalid (Gamma-only terminal) — merchant-scoped numeric invalid**
**Pattern (provable from counters):**

* A **Gamma row** exists for merchant *m* with interval $[b_\Gamma,a_\Gamma)$,
* **No Poisson row** exists with `before ≥ a_Γ` that satisfies the Γ→Π inequalities for pairing (V4),
* No `nb_final` for *m*.

**Interpretation:** the Poisson step was suppressed because $\lambda=(\mu/\phi)\,G$ was **non-finite or ≤0**.
**Action:** classify as **ERR\_S2\_NUMERIC\_INVALID** (merchant scope). L3 writes a merchant-scoped failure (unless policy escalates).

**B. Partial components (not λ-invalid) — policy terminal (usually run abort)**
**Pattern:** for merchant *m*

* One or more **valid pairs** (Γ→Π) exist, **but no finaliser**,
* Or only Poisson rows exist with **no eligible Γ** (ordering violation already caught earlier),
* Or a mixture of Γ/Π that cannot yield acceptance yet the stream ends (crash/resume), and the situation is **not** explained by λ-invalid.
  **Action:** **ERR\_PARTIAL\_COMPONENTS** under your policy (commonly run-scoped atomic abort). L3 does **not** backfill.

**C. Accepted attempt but missing finaliser — coverage failure**
**Pattern:** a pair with $K\ge2$ exists, **no** `nb_final`.
**Action:** **F\_coverage** (merchant), not λ-invalid; evidence says acceptance occurred but finalisation didn’t.

> These classifications are computed **after** V4 pairing and **before** corridor roll-ups, and they never require timestamps or producer logs—only counters and payloads.

---

## 18) Failure Mapping (Batch-F)

**Single-failure, early-exit:** the first failing check maps to exactly **one** canonical code and scope; L3 writes the Batch-F record and exits. Evidence already written by producers remains intact; L3 never backfills.

| Area                       | Condition (examples)                                                                             | Code (suggested)                                            | Scope                          |     
|----------------------------|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------|--------------------------------|
| **Lineage**                | `parameter_hash` or `manifest_fingerprint` mismatch                                              | `F_lineage_mismatch`                                        | Run                            |     
| **Numeric policy**         | Attestation missing/false flag                                                                   | `F_numeric_policy`                                          | Run                            |     
| **Schema/Partitions**      | Wrong family/partition set; stringified floats; bad `draws`; malformed `ts_utc`                  | `F_schema_or_partition`                                     | Run                            |     
| **Path↔embed**             | Event path partitions ≠ embedded `{seed, parameter_hash, run_id}`; trace embeds `parameter_hash` | `F_schema_or_partition` or `F_path_embed_mismatch`          | Run                            |     
| **Gating / Branch purity** | S2 evidence for non-gated merchant; hurdle non-unique                                            | `F_branch_purity`                                           | Run                            |     
| **Idempotence**            | Multiple `nb_final` for a merchant/run                                                           | `F_multiple_finaliser`                                      | Run                            |     
| **Envelope invariants**    | `blocks ≠ after−before`; finaliser consumes or `draws ≠ "0"`                                     | `F_envelope_invariant` or `F_finaliser_contract`            | Merchant (or Run for systemic) |     
| **Ordering & pairing**     | Π without eligible Γ; overlaps; Γ→Π order broken                                                 | `F_attempt_ordering`                                        | Run                            |     
| **Finaliser contract**     | Echo mismatch (`mu/φ`), or non-consumption broken                                                | `F_finaliser_contract`                                      | Merchant                       |     
| **Coverage**               | `n_outlets`/`nb_rejections` don’t match reconstructed `(N,r)`; components after final            | `F_coverage`                                                | Merchant                       |     
| **Trace discipline**       | Missing/extra trace rows; non-monotone totals; wrong saturation                                  | `F_trace_discipline`                                        | Run                            |     
| **Corridors**              | `ρ>0.06`; `p99(r)>3`; CUSUM > `h`                                                                | `F_corridor_breach:{rho\|p99\|cusum}`                       | Run                            |      
| **λ-invalid**              | Gamma-only terminal per V4/V6 pattern                                                            | `F_numeric_invalid_lambda` (alias `ERR_S2_NUMERIC_INVALID`) | Merchant                       |     
| **Partial components**     | Components without final not explained by λ-invalid                                              | `F_partial_components`                                      | Run (policy)                   |     
| **Publish**                | `_passed.flag` bad/missing; temp debris; wrong bundle scope                                      | `F_publish_atomicity`                                       | Run                            |     

**Batch-F payloads (minimal, canonical):**

* Always include `{ state:"1A.S2", module:"L3.validator", seed, parameter_hash, manifest_fingerprint, run_id }`.
* Include the **first offending evidence** identifiers (dataset id, relative file, line offset or `before/after` counters) and a short `detail` object (expected vs observed).
* For run-abort cases, **atomic commit** of the failure bundle; for merchant-scoped failures, a single merchant record.

**After mapping:** L3 stops; it does not attempt retries, clamping, or compensating emissions.

---

## 19) Determinism & Idempotence (of the validator)

**Determinism.**

* Results depend **only on bytes** (evidence streams, dictionary, schemas, governed artefacts, attestation). No reliance on file mtimes, ordering of directory listings, or wall-clock time.
* Any ordering required for computation uses **stable keys**:

  * Bundle hashing: **ASCII-ascending** relative paths.
  * Attempt logic: **u128 counters** (`before_hi, before_lo`), never timestamps.
  * Corridor roll-ups: deterministic merchant order (e.g., ascending `merchant_id`).

**Idempotence.**

* Re-running L3 on the same inputs yields the **same verdict** and, if failing, the **same Batch-F payload**; if passing, the **same `_passed.flag`** content.
* Publish is atomic: never produces partial bundles; no temp debris. Existing success/failure artefacts for the same `{fingerprint, seed, run_id}` are **not mutated**.

**Resource bounds.**

* Streaming readers; bounded per-merchant state (pairing windows, counters). No whole-run loads into memory.
* Numeric recomputations (for echo) use the pinned math profile (binary64, Neumaier, no FMA); no tolerance—**bit equality**.

**No producer state.**

* Never consults L0/L1 internal caches, RNG state, or L2 logs; proves claims strictly from evidence + authorities.

## 20) Public API (code-agnostic)

```pseudocode
type Lineage = { seed:u64, parameter_hash:Hex64, manifest_fingerprint:Hex64, run_id:Hex32 }

type Sources = {
  dictionary: DictHandle,         # resolves dataset IDs → path templates + partitions
  schemas: SchemaHandle,          # JSON-Schema anchors for families & trace
  coeffs: ArtefactSet,            # governed NB coefficient YAMLs (raw bytes)
  design_vectors: ArtefactSet,    # frozen design vectors (read-only)
  attestation: NumericAttest      # numeric policy booleans/signature
}

type IO = {
  list_files: fn(dataset_id, partitions) -> Iterator[RelPath],
  read_jsonl_stream: fn(dataset_id, rel_path) -> Iterator[JsonRow],
  read_bytes: fn(rel_or_abs_path) -> ByteStream
}

type Options = {
  thresholds?: { rho_max: f64 = 0.06, p99_max: i64 = 3, cusum?: { k:f64, h:f64 } },
  progress_hook?: fn(stage:string, merchant_id?:u64, detail?:object) -> void
}

type Failure = { code:string, scope:"run"|"merchant", detail:object }

type Result = { ok: true,  bundle_path: string } |
              { ok: false, failure: Failure, bundle_path?: string }

function validate_S2(lineage: Lineage, src: Sources, io: IO, opts?: Options) -> Result
```

**Behavior.**

* Streams evidence (dictionary-resolved), runs checks V0→V9 **fail-fast**, and either:

  * writes a single **Batch-F** record (first failure) and returns `{ok:false, failure}`,
  * or publishes a **validation bundle** with `_passed.flag` and returns `{ok:true, bundle_path}`.
* Never writes producer datasets; never backfills; uses no path literals.

## 21) Acceptance (Definition of Done)

L3 is **green** when all of the following hold:

**Core checks implemented (V0→V9).**

* **V0** lineage recomputation (`parameter_hash`, `manifest_fingerprint`) and numeric attestation pass.
* **V1** dictionary/schema/partition discipline passes; floats are numbers, `draws` parses as decimal u128.
* **V2** gating/branch-purity and **≤1 finaliser/merchant** enforced.
* **V3** path↔embed equality and envelope identities (`blocks == after−before`; finaliser `draws == "0"`) hold.
* **V4** attempts reconstructable by **counters only**; each valid attempt is **Γ→Π**; no cross-label chaining.
* **V5** finaliser is **non-consuming** and **echo-equal** to recomputed `(μ, φ)` (bit-for-bit).
* **V6** coverage: `n_outlets == N`, `nb_rejections == r`, and **no components after finaliser**.
* **V7** trace: one cumulative row per event, monotone **saturating** totals, counts agree with events.
* **V8** corridors satisfy policy thresholds (ρ, p99, optional CUSUM).
* **V9** publish is atomic; `_passed.flag` equals bundle SHA-256; no temp debris.

**Process guarantees.**

* **Fail-once, early exit:** on first failure, exactly one Batch-F record is written and L3 exits.
* **Success bundle only on pass:** on success, only the validation bundle (with `_passed.flag`) is written.
* **Evidence-only:** L3 is read-only over producer outputs; it adds no new business datasets, schemas, or paths; no path literals appear in the validator.

**Determinism & idempotence.**

* Stable ordering keys (ASCII file lists; counter ordering); verdict and outputs reproduce exactly on re-run.
* Resource-bounded streaming; no reliance on time or host scheduling.

When all items above are satisfied and demonstrated in the document, S2 · L3 is ready to implement and considered **green** at the design level.

---