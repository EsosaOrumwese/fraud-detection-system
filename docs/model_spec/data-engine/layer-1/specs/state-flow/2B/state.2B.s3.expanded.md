# State 2B.S3 — Corporate-day modulation (γ draws)

## 1. **Document metadata & status (Binding)**

**Component:** Layer-1 · Segment **2B** — **State-3 (S3)** · *Corporate-day modulation (γ draws)*
**Document ID:** `seg_2B.s3.day_effects`
**Version (semver):** `v1.0.0-alpha`
**Status:** `alpha` *(normative; semantics lock at `frozen` in a ratified release)*
**Owners:** Design Authority (DA): **Esosa Orumwese** · Review Authority (RA): **Layer-1 Governance**
**Effective date:** **2025-11-03 (UTC)**
**Canonical location:** `contracts/specs/l1/seg_2B/state.2B.s3.expanded.v1.0.0.txt`

**Authority chain (Binding):**
**JSON-Schema pack** = shape authority → `schemas.2B.yaml`
**Dataset Dictionary** = ID→path/partitions/format → `dataset_dictionary.layer1.2B.yaml`
**Artefact Registry** = existence/licence/retention → `artefact_registry_2B.yaml`

**Normative cross-references (Binding):**

* Prior state evidence: **`s0_gate_receipt_2B`**, **`sealed_inputs_2B`**.
* Upstream inputs: **`s1_site_weights`** (2B · S1), **`site_timezones`** (2A egress).
* Policy: **`day_effect_policy_v1`** (Philox sub-streams/budgets, σ parameters, day range).
* Segment context: `state-flow-overview.2B.txt` (context only; this spec governs).

**Segment invariants (Binding):**

* **Run identity:** `{ seed, manifest_fingerprint }`.
* **Partitioning for S3 outputs:** `[seed, fingerprint]`; **path↔embed equality** MUST hold.
* **Catalogue discipline:** Dictionary-only resolution; literal paths forbidden; **S0-evidence rule** enforced (policies in S0; within-segment reads by ID at `[seed,fingerprint]`).
* **RNG posture:** **RNG-bounded, reproducible** — counter-based **Philox** with policy-declared sub-streams and draw budgets.
* **Numeric discipline:** binary64, round-to-nearest-even; stable serial reductions.
* **Gate law:** **No PASS → No read** remains in force across the segment.

---

## 2. **Purpose & scope (Binding)**

**Purpose.** Introduce **short-run, zone-level co-movement** in routing by generating **per-merchant, per-UTC-day, per-tz-group** multiplicative factors **γ(d, tz_group)** that **do not change long-run shares**. Factors are **log-normal** with policy-declared variance and are drawn with **counter-based Philox** under a governed RNG policy. S3 **emits the factors only**; application/renormalisation is handled downstream.

**S3 SHALL:**

* **Define tz-groups deterministically** by joining `s1_site_weights` keys to `site_timezones` and grouping by **IANA `tzid`** (the group identifier).
* **Draw factors** for every `{merchant_id, utc_day, tz_group_id}` in the policy’s day range using Philox sub-streams declared by `day_effect_policy_v1`.

  * Distribution: `log_gamma ~ Normal(μ, σ²)` with `σ = sigma_gamma` from policy and `μ = −½·σ²` so that **E[γ] = 1**.
  * Record RNG provenance per row: `rng_stream_id`, `rng_counter_lo`, `rng_counter_hi`.
* **Publish a deterministic table** `s3_day_effects` (partitioned by `[seed, fingerprint]`) containing `{merchant_id, utc_day, tz_group_id, gamma, log_gamma, sigma_gamma, rng_* , created_utc}`.
* **Preserve identity & determinism:** `created_utc =` S0 `verified_at_utc`; same sealed inputs + day range ⇒ **byte-identical** output.

**Scope (included).**

* Catalogue-only resolution of inputs; formation of tz-groups by `tzid`; RNG-bounded factor generation per policy; persistence of factors and RNG provenance; write-once, atomic publish of `s3_day_effects`.

**Out of scope.**

* **No** modification of S1 weights or S2 artefacts.
* **No** renormalisation or application of γ (handled in **S4**).
* **No** routing decisions (S5/S6) or audit/PASS packaging (S7/S8).

**Non-goals / prohibitions.**

* No network I/O; no literal paths; no stochastic behaviour outside the policy; no changes to group definitions without a schema/policy change.

---

## 3. **Preconditions & sealed inputs (Binding)**

### 3.1 Preconditions (Abort on failure)

* **Prior gate evidence.** A valid **`s0_gate_receipt_2B`** for the target **`manifest_fingerprint`** MUST exist.
* **Run identity fixed.** The pair **`{ seed, manifest_fingerprint }`** is fixed at S3 start and MUST remain constant.
* **RNG posture.** S3 is **RNG-bounded, reproducible** (counter-based Philox per governed policy).
* **Catalogue discipline.** All inputs resolve by **Dataset Dictionary IDs**; literal paths are forbidden.
* **S0-evidence rule.** Cross-layer/policy assets **MUST** appear in S0’s `sealed_inputs_2B` for this fingerprint; within-segment datasets are **NOT** S0-sealed and **MUST** be resolved by **Dataset Dictionary ID** at exactly **`[seed,fingerprint]`**.

### 3.2 Required sealed inputs (must all be present)

S3 SHALL read **only** the following assets for this run’s identity:

1. **`s1_site_weights`** — 2B·S1 output at `seed={seed} / fingerprint={manifest_fingerprint}`.
2. **`site_timezones`** — 2A egress at `seed={seed} / fingerprint={manifest_fingerprint}` (provides `tzid` per site for tz-grouping).
3. **`day_effect_policy_v1`** — policy pack declaring RNG/variance/day-range (single file; **no partition tokens** — selection is the **exact S0-sealed path + digest**).

> All required assets MUST be resolvable via the Dictionary and MUST appear in S0’s inventory for the same fingerprint.

### 3.3 Policy minima (Abort if unmet)

`day_effect_policy_v1` **MUST** declare, at minimum:

* **`rng_engine`** (e.g., `philox_2x64_10`) and **`rng_stream_id`** (string/enum) reserved for S3;
* **`draws_per_row` = 1** and the audit posture (record counters per row);
* **`sigma_gamma`** > 0 (standard deviation of `log_gamma`);
* **`day_range`** as UTC date bounds `{ start_day: YYYY-MM-DD, end_day: YYYY-MM-DD }` with **inclusive** semantics and `start_day ≤ end_day`;
* **`record_fields`** to be persisted at minimum: `gamma`, `log_gamma`, `sigma_gamma`, `rng_stream_id`, `rng_counter_lo`, `rng_counter_hi`;
* **`created_utc_policy_echo`** (boolean) indicating whether to echo policy tag/digest in the run-report.

Absence of any listed entry is **Abort**.

### 3.4 Resolution & partition discipline (Binding)

* **Exact partitions (reads):**
  • `s1_site_weights` → **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
  • `site_timezones` → **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
  • `day_effect_policy_v1` → **no tokens**; select the **S0-sealed file path** and validate its digest.
* **Key join basis:** tz-groups are formed by joining `s1_site_weights` keys `(merchant_id, legal_country_iso, site_order)` to `site_timezones` on the **same** key set, taking `tzid` as `tz_group_id`.
* **No re-hash of 1B.** S3 MUST NOT recompute the 1B bundle hash; S0’s receipt is the sole gate attestation.

### 3.5 Integrity & provenance inputs

* **Created time.** Discover canonical `created_utc` from S0’s receipt (`verified_at_utc`) and use it for all S3 rows.
* **Coverage basis.** The universe of rows to produce is the Cartesian product of:
  `{ all merchants in s1_site_weights } × { each merchant’s tz_groups from site_timezones } × { every UTC day in policy.day_range }`.
  (Coverage is validated in acceptance.)

### 3.6 Prohibitions (Binding)

* **No network I/O.** All bytes are local/managed.
* **No extra inputs.** S3 MUST NOT read any dataset/policy other than §3.2.
* **No implicit transforms.** Grouping uses only `tzid`; S3 SHALL NOT infer alternative groupings or modify S1 weights.

---

## 4. **Inputs & authority boundaries (Binding)**

### 4.1 Catalogue authorities

* **Schema pack** (`schemas.2B.yaml`) is the **shape authority** for S3 outputs and referenced inputs.
* **Dataset Dictionary** (`dataset_dictionary.layer1.2B.yaml`) is the **sole authority** for resolving **IDs → path templates, partitions, format** (token expansion is binding).
* **Artefact Registry** (`artefact_registry_2B.yaml`) governs **existence/licence/retention/ownership**; it does **not** override Dictionary paths.

### 4.2 Inputs S3 MAY read (and nothing else)

Resolve **only** these IDs via the Dictionary (no literal paths):

1. **`s1_site_weights`** — at `seed={seed} / fingerprint={manifest_fingerprint}`.
2. **`site_timezones`** — at `seed={seed} / fingerprint={manifest_fingerprint}` (provides `tzid` for tz-grouping).
3. **`day_effect_policy_v1`** — policy pack (**no partition tokens**); select the **exact S0-sealed path/digest** for this fingerprint.

> **S0-evidence rule:** Cross-layer/policy assets **MUST** appear in S0’s `sealed_inputs_2B`; within-segment datasets are **NOT** S0-sealed and are resolved by ID at **`[seed,fingerprint]`**.

### 4.3 Prohibited resources & behaviours

* **No literal paths** (env overrides, ad-hoc strings/globs).
* **No network I/O** (HTTP/remote FS/cloud buckets).
* **No extra inputs** beyond §4.2.
* **No re-hashing 1B**; S0’s receipt is the sole gate attestation.

### 4.4 Resolution & token discipline

* **Exact partitions:**
  • `s1_site_weights` → **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
  • `site_timezones` → **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
  • `day_effect_policy_v1` → **no tokens**; use the **S0-sealed** path and validate its digest.
* **Path↔embed equality (outputs):** any embedded identity in S3 outputs **MUST** equal the Dictionary path tokens.

### 4.5 Input field & join expectations

* **Key basis:** join `s1_site_weights` keys `(merchant_id, legal_country_iso, site_order)` to `site_timezones` on the **same** key set; take `tzid` as `tz_group_id`.
* **Cardinality:** the join MUST be **1:1** for all keys present in `s1_site_weights`; missing or multiple `tzid` values per key is an error (validated later).
* **Policy minima:** S3 relies on `day_effect_policy_v1` to declare `rng_engine`, `rng_stream_id`, `sigma_gamma`, and `day_range`; absence is an error per §3.3.

### 4.6 Trust boundary & sequencing

1. Verify S0 evidence for the target fingerprint exists.
2. Resolve `day_effect_policy_v1`, `s1_site_weights`, and `site_timezones` via the Dictionary.
3. Form tz-groups and perform γ-draws strictly from these sealed inputs; do not consult any other sources.

---

## 5. **Outputs (datasets) & identity (Binding)**

### 5.1 Product (ID)

* **`s3_day_effects`** — per-merchant, per-UTC-day, per-`tz_group_id` **γ-factor table** (log-normal draws with Philox provenance).

### 5.2 Identity & partitions

* **Run identity:** `{ seed, manifest_fingerprint }`.
* **Partitions (binding):** `[seed, fingerprint]` only.
* **Path↔embed equality:** Any embedded `manifest_fingerprint` (and, if echoed, `seed`) **MUST** byte-equal the path tokens.

### 5.3 Path family, format & catalogue authority

* **Dictionary binding (required):**
  `data/layer1/2B/s3_day_effects/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
  (The **Dataset Dictionary** is the sole authority for ID → path/partitions/format.)
* **Storage format:** `parquet` (Dictionary authority).
* **Shape authority:** `schemas.2B.yaml#/plan/s3_day_effects` (fields/PK/partitions are owned by the schema anchor).

### 5.4 Keys, writer order & order posture

* **Primary key (PK):** `[merchant_id, utc_day, tz_group_id]`.
* **Writer order:** **exactly** the PK order; file order is non-authoritative for readers.
* **Order-free read:** consumers MUST treat file order as non-authoritative and join/aggregate by PK only.

### 5.5 Required provenance signals (owned by the schema anchor)

Rows **MUST** include at least:

* `gamma` (double > 0), `log_gamma` (double), `sigma_gamma` (double; policy echo),
* `rng_stream_id` (string/enum), `rng_counter_lo` (uint64), `rng_counter_hi` (uint64),
* `created_utc` (RFC-3339 UTC; equals S0 `verified_at_utc`).
  *(Additional optional metadata may be present if the anchor declares it.)*

### 5.6 Coverage & FK discipline

* **Coverage:** For every `utc_day` in the policy day-range and for every merchant’s tz-group, exactly **one** row MUST exist.
* **FK basis:** `(merchant_id, legal_country_iso, site_order) → tzid` mapping used to form `tz_group_id` **MUST** be derivable from `site_timezones@{seed,fingerprint}` and `s1_site_weights@{seed,fingerprint}`; no new keys may be introduced.

### 5.7 Write-once, immutability & idempotency

* **Single-writer, write-once:** target partition MUST be empty before first publish.
* **Idempotent re-emit:** re-publishing to the same partition is allowed **only** if bytes are **bit-identical**; otherwise **Abort**.
* **Atomic publish:** stage → fsync → single atomic move; no partial files may become visible.

### 5.8 Provenance stamping

* `created_utc` **MUST** equal the canonical S0 time (`verified_at_utc`) for this fingerprint.
* Any policy identifiers/digests echoed in dataset metadata (if the anchor allows) **MUST** match those sealed by S0 for this fingerprint.

### 5.9 Downstream reliance

* **S4** consumes `s3_day_effects` to renormalise **within tz-groups** (and/or across groups per your design), preserving alias mechanics; consumers MUST select by `(seed, fingerprint)` via the Dictionary and rely on the schema anchor for shape.

---

## 6. **Dataset shapes & schema anchors (Binding)**

### 6.1 Shape authority

All shapes in this state are governed by the **2B schema pack** (`schemas.2B.yaml`). Shapes are **fields-strict** (no extras). The **Dataset Dictionary** binds IDs → path/partitions/format. The **Artefact Registry** carries ownership/licence/retention only.

---

### 6.2 Output table — `schemas.2B.yaml#/plan/s3_day_effects`

**Type:** table (**columns_strict: true**)

**Identity & keys (binding)**

* **Primary key (PK):** `[merchant_id, utc_day, tz_group_id]`
* **Partition keys:** `[seed, fingerprint]`
* **Writer sort:** `[merchant_id, utc_day, tz_group_id]`

**Columns (all required unless marked “optional”)**

* `merchant_id` — `$ref: 'schemas.layer1.yaml#/$defs/id64'`, **nullable: false**
* `utc_day` — `{ type: string, format: date }`, **nullable: false**
  *(UTC calendar day; `YYYY-MM-DD`.)*
* `tz_group_id` — `{ type: string, minLength: 1 }`, **nullable: false**
  *(IANA `tzid` used as group identifier; membership already enforced upstream by 2A.)*
* `gamma` — `{ type: number, exclusiveMinimum: 0 }`, **nullable: false**
* `log_gamma` — `{ type: number }`, **nullable: false**
* `sigma_gamma` — `{ type: number, exclusiveMinimum: 0 }`, **nullable: false**
  *(Echo of policy variance parameter; constant across rows for a run.)*
* `rng_stream_id` — `{ type: string, minLength: 1 }`, **nullable: false**
* `rng_counter_lo` — `{ type: integer, minimum: 0, maximum: 18446744073709551615 }`, **nullable: false**
* `rng_counter_hi` — `{ type: integer, minimum: 0, maximum: 18446744073709551615 }`, **nullable: false**
* `created_utc` — `$ref: 'schemas.layer1.yaml#/$defs/rfc3339_micros'`, **nullable: false**

> **Notes (binding semantics):**
>
> * `sigma_gamma` must equal the value declared in `day_effect_policy_v1`.
> * `(rng_counter_hi, rng_counter_lo)` capture the 128-bit Philox counter at draw time.
> * `created_utc` equals S0 receipt’s `verified_at_utc` for this fingerprint.

---

### 6.3 Referenced anchors (inputs/policy)

* **Weights table (read-only):** `schemas.2B.yaml#/plan/s1_site_weights`
* **Site time-zones (read-only):** `schemas.2A.yaml#/egress/site_timezones`
* **Day-effect policy:** `schemas.2B.yaml#/policy/day_effect_policy_v1` *(declares RNG engine/stream, `sigma_gamma`, `day_range`, audit fields)*

---

### 6.4 Common definitions

* `$defs.hex64` — `^[a-f0-9]{64}$`
* `$defs.partition_kv` — object of string tokens; **minProperties: 0** (token-less assets allowed in receipts/inventory)
* Timestamps reuse `schemas.layer1.yaml#/$defs/rfc3339_micros`.

---

### 6.5 Format & storage (Dictionary authority)

* **ID:** `s3_day_effects`
* **Path family:** `data/layer1/2B/s3_day_effects/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
* **Format:** `parquet`
* **Partitioning:** `[seed, fingerprint]` (no other tokens)

---

### 6.6 Domain & cross-field constraints (validated by anchor + validators)

* `gamma > 0`; `log_gamma` finite; `sigma_gamma > 0` and constant for the run.
* For each `(merchant_id, tz_group_id)`, there is exactly **one** row per `utc_day` in the policy day range.
* `rng_stream_id` present; `(rng_counter_hi, rng_counter_lo)` non-negative and never reused for the same row key.
* Writer order = PK; path↔embed equality holds; table is fields-strict (no extra columns).

---

## 7. **Algorithm (RNG-bounded, reproducible) (Binding)**

**Overview.** S3 emits a byte-stable table of **per-merchant × per-UTC-day × per-tz-group** factors `γ` using a **counter-based Philox** stream governed by `day_effect_policy_v1`. There is **no network I/O**. All arithmetic is binary64, round-to-nearest-even; reductions are serial and order-stable.

### 7.1 Resolve & snapshot

1. **Fix identity**: capture `{seed, manifest_fingerprint}` from the run context.
2. **Resolve inputs by Dictionary IDs only**:
   `s1_site_weights@{seed,fingerprint}`, `site_timezones@{seed,fingerprint}`, and `day_effect_policy_v1` (single file; **no tokens**, select the **S0-sealed path + digest**).
3. **Extract policy minima** (must exist; see §3.3):
   `rng_engine` (Philox variant), `rng_stream_id`, `sigma_gamma>0`, `day_range{start_day..end_day}`, `draws_per_row=1`, and required record fields.
4. **Set `created_utc`** ← S0.receipt.`verified_at_utc`.

### 7.2 Build deterministic tz-groups

5. **Join keys**: left-join `s1_site_weights` PK `(merchant_id, legal_country_iso, site_order)` to `site_timezones` on the same keys; take `tzid` as `tz_group_id`.
6. **Form group universe**: for each `merchant_id`, collect distinct `tz_group_id` (IANA `tzid`) and sort **lexicographically** (deterministic).
7. **Enumerate days**: materialise the inclusive UTC day grid `D = {start_day,…,end_day}` in **ascending ISO date**.

> **Coverage target** (validated later): Cartesian product
> `U = { all merchants } × { each merchant’s tz_group_id } × { each utc_day ∈ D }`.

### 7.3 RNG stream & counter law

8. **RNG engine**: use `rng_engine` from policy (e.g., `philox_2x64_10`) with a **128-bit key** derived from `{manifest_fingerprint, rng_stream_id}` by the policy’s key-derivation rule.
9. **Row ordering for counter mapping**: define a **total order** over rows as the **writer sort**:
   `(merchant_id ↑, utc_day ↑, tz_group_id ↑)`.
10. **Base counter**: obtain a 128-bit `base_counter` from policy (or policy’s deterministic derivation from `{manifest_fingerprint, seed, rng_stream_id}`); this is **constant** for the run.
11. **Per-row counter**: for the row at rank `i` (0-based) in the order of step 9, set
    `counter = base_counter + i` (128-bit unsigned addition, wrap-around forbidden by draw budget).
    Record `(rng_counter_hi, rng_counter_lo)` = high/low 64-bit words of `counter`.

> **Draw budget** (validated later): `draws_total = |U|` and no counter reuse.

### 7.4 Normal draw from one uniform (ICDF)

12. **Uniform on open interval**: from Philox at `counter`, obtain a 64-bit unsigned integer `r`. Map to `u ∈ (0,1)` by
    `u = (r + 0.5) · 2^-64`  (guarantees `0<u<1` deterministically).
13. **Gaussian (ICDF)**: compute a standard normal `Z` via inverse-CDF
    `Z = √2 · erf⁻¹(2u − 1)`
    using the programme’s deterministic libm policy (no FMA/FTZ/DAZ; fixed implementation/approximation as governed by the layer’s numeric discipline).
    *Exactly one uniform is consumed per row (`draws_per_row = 1`).*

### 7.5 Log-normal factor with E[γ]=1

14. Let `σ ← sigma_gamma` (from policy) and set `μ ← −½·σ²`.
15. Compute `log_gamma = μ + σ·Z` and `gamma = exp(log_gamma)`.
16. **Domain check**: require `gamma > 0` and `isfinite(log_gamma)`; otherwise **Abort**.

### 7.6 Row materialisation (writer order = PK)

17. For each row in the order of step 9, emit a record with:
    `merchant_id, utc_day, tz_group_id, gamma, log_gamma, sigma_gamma=σ, rng_stream_id, rng_counter_hi, rng_counter_lo, created_utc`.
18. **Writer order**: emit strictly in `(merchant_id, utc_day, tz_group_id)` ascending order.

### 7.7 Publish (write-once; atomic)

19. **Target partition (Dictionary-resolved)**:
    `s3_day_effects@seed={seed}/fingerprint={manifest_fingerprint}`.
20. **Immutability**: target must be empty; otherwise allow only **bit-identical** re-emit; else **Abort**.
21. **Atomic publish**: write to staging on the same filesystem, `fsync`, then atomic rename. No partial files may become visible.

### 7.8 Post-publish assertions

22. **Path↔embed equality**: any embedded identity equals path tokens.
23. **RNG audit**:

    * `rows_written = |U|`.
    * `draws_total = rows_written`.
    * `(rng_counter_hi, rng_counter_lo)` are **strictly increasing** with row rank (no reuse; no wrap).
24. **Day/group coverage**: for every `(merchant_id, tz_group_id)` and every `utc_day ∈ D`, exactly **one** row exists.

### 7.9 Prohibitions & determinism guards

25. **No network I/O**; **no literal paths**; **no extra inputs** beyond §3.2.
26. **No data-dependent re-ordering** of reductions; numeric behaviour must be invariant to thread scheduling.
27. **Replay**: re-running S3 with identical sealed inputs (incl. identical policy bytes and day range) **MUST** reproduce bit-identical output.

---

## 8. **Identity, partitions, ordering & merge discipline (Binding)**

### 8.1 Identity law

* **Run identity:** `{ seed, manifest_fingerprint }` fixed at S3 start.
* **Output identity:** `s3_day_effects` **MUST** be identified and selected by **both** tokens.

### 8.2 Partitions & exact selection

* **Write partition:** `…/s3_day_effects/seed={seed}/fingerprint={manifest_fingerprint}/`.
* **Exact selection (read/write):** one and only one `(seed,fingerprint)` partition per publish; no wildcards, ranges, or multi-partition writes.

### 8.3 Path↔embed equality

* Any embedded `manifest_fingerprint` (and, if echoed, `seed`) in the dataset **MUST** byte-equal the corresponding path tokens. Inequality is an error.

### 8.4 Writer order & file-order posture

* **Writer order:** rows **MUST** be emitted in **PK order** `[merchant_id, utc_day, tz_group_id]`.
* **Order-free read:** consumers **MUST** treat file order as non-authoritative; joins/aggregations are by PK only.

### 8.5 Single-writer, write-once

* Target partition **MUST** be empty before first publish.
* If the target exists:

  * **Byte-identical:** treat as a no-op (idempotent re-emit).
  * **Byte-different:** **Abort** with immutable-overwrite error.

### 8.6 Atomic publish

* Write to a same-filesystem **staging** location, `fsync`, then **atomic rename** into the final partition. No partial files may become visible at any time.

### 8.7 Concurrency

* At most **one** active publisher per `(component=2B.S3, seed, manifest_fingerprint)`.
* A concurrent publisher **MUST** either observe existing byte-identical artefacts and no-op, or abort on attempted overwrite.

### 8.8 Merge discipline

* **No appends, compactions, or in-place updates.** Any change requires publishing to a **new** `(seed,fingerprint)` identity (or a new fingerprint per change-control rules).

### 8.9 Determinism & replay

* Re-running S3 with identical sealed inputs (including policy bytes and day range) **MUST** reproduce **bit-identical** output.
* Numeric outcomes **MUST NOT** depend on thread scheduling or data-dependent re-ordering that changes reduction order.

### 8.10 Token hygiene

* Partition tokens **MUST** appear exactly once and in this order: `seed=…/fingerprint=…/`.
* Literal paths, environment-injected overrides, or ad-hoc globs are prohibited.

### 8.11 Provenance echo

* `created_utc` **MUST** equal the canonical S0 time (`verified_at_utc`) for this fingerprint.
* If policy identifiers/digests are echoed in dataset metadata, they **MUST** match S0’s sealed values.

### 8.12 Retention & ownership

* Retention, licence, and ownership are governed by the Registry; immutability is enforced by this section.

---

## 9. **Acceptance criteria (validators) (Binding)**

**Outcome rule.** **PASS** iff all **Abort** validators succeed. **WARN** validators may fail without blocking publish but MUST be recorded in the run-report.

**V-01 — Prior gate evidence present (Abort).**
` s0_gate_receipt_2B` exists for the target `manifest_fingerprint` and is discoverable via the Dictionary.

**V-02 — Dictionary-only resolution (Abort).**
All inputs (`s1_site_weights`, `site_timezones`, `day_effect_policy_v1`) resolved by **Dictionary IDs**; zero literal paths.

**V-03 — Partition/selection exact (Abort).**
Reads used only `s1_site_weights@seed={seed}/fingerprint={manifest_fingerprint}`, `site_timezones@seed={seed}/fingerprint={manifest_fingerprint}`, and the **exact S0-sealed path** for `day_effect_policy_v1` (no partition tokens).

**V-04 — Policy minima present (Abort).**
`day_effect_policy_v1` declares `rng_engine`, `rng_stream_id`, `draws_per_row=1`, `sigma_gamma>0`, and a valid inclusive `day_range{start_day..end_day}` with `start_day ≤ end_day`.

**V-05 — Group universe well-defined (Abort).**
Join on keys `(merchant_id, legal_country_iso, site_order)` between `s1_site_weights` and `site_timezones` succeeds with **one** `tzid` per key; no missing/duplicate mappings.

**V-06 — Coverage: merchants × groups × days (Abort).**
For each merchant, for every `tz_group_id` (tzid) present in that merchant’s joined group set, and for every UTC day in the policy day-range, **exactly one** row exists in `s3_day_effects`.

**V-07 — PK uniqueness (Abort).**
No duplicate `(merchant_id, utc_day, tz_group_id)` in `s3_day_effects`.

**V-08 — Writer order = PK (Abort).**
Row emission order is exactly `[merchant_id, utc_day, tz_group_id]` ascending.

**V-09 — Domain: γ/log-γ/sigma (Abort).**
Every row has `gamma > 0`, `isfinite(log_gamma)`, and `sigma_gamma > 0`.

**V-10 — Sigma echo coherent (Abort).**
All rows share the same `sigma_gamma`, and it equals the value in `day_effect_policy_v1`.

**V-11 — RNG engine/stream echo (Abort).**
`rng_stream_id` equals the policy’s stream identifier; RNG engine used equals policy `rng_engine`.

**V-12 — Draws accounting (Abort).**
`rows_written = draws_total = (#UTC days in range) × Σ_merchants ( #tz_groups for merchant )`.

**V-13 — Counter monotonicity / no reuse (Abort).**
Across the writer order, `(rng_counter_hi,rng_counter_lo)` form a strictly increasing 128-bit counter sequence with **no** reuse and **no** wrap-around.

**V-14 — Created time canonical (Abort).**
`created_utc` in every row equals the S0 receipt’s `verified_at_utc` for this fingerprint.

**V-15 — Path↔embed equality (Abort).**
Any embedded identity fields equal the dataset path tokens (`seed`, `fingerprint`).

**V-16 — Output shape valid (Abort).**
` s3_day_effects` validates against `schemas.2B.yaml#/plan/s3_day_effects` (fields-strict).

**V-17 — Write-once immutability (Abort).**
Target partition was empty before publish, or existing bytes are **bit-identical**.

**V-18 — Idempotent re-emit (Abort).**
Re-running S3 with identical sealed inputs and day-range reproduces **byte-identical** output; otherwise abort rather than overwrite.

**V-19 — No network & no extra reads (Abort).**
Execution performed with network I/O disabled and accessed **only** the assets listed in S0’s inventory for this fingerprint.

**V-20 — Day-range materialisation (Abort).**
The set of `utc_day` values in the output equals the inclusive calendar grid from `policy.day_range` (no gaps, no extras).

**V-21 — tzid validity echo (Warn).**
All `tz_group_id` values appear in the set of tzids present in `site_timezones@{seed,fingerprint}`; otherwise emit WARN with examples (S3 does not correct 2A).

**V-22 — RNG draws per row (Abort).**
Exactly **one** Philox draw was consumed per output row (`draws_per_row=1`), evidenced by counter differences.

**V-23 — Join key coherence (Abort).**
For every `(merchant_id, legal_country_iso, site_order)` key present in `s1_site_weights`, there exists a corresponding row in `site_timezones`; missing keys cause Abort.

**Reporting.** The run-report MUST include: validator outcomes; counts (`merchants_total`, `groups_total`, `days_total`, `rows_written`, `draws_total`); `sigma_gamma`; deterministic samples of rows with RNG provenance; and the exact paths of all resolved inputs and the output target.

---

## 10. **Failure modes & canonical error codes (Binding)**

**Code namespace.** `2B-S3-XYZ` (zero-padded). **Severity** ∈ {**Abort**, **Warn**}.
Every failure log entry **MUST** include: `code`, `severity`, `message`, `fingerprint`, `seed`, `validator` (e.g., `"V-12"` or `"runtime"`), and a `context{…}` object with the keys listed below.

### 10.1 Gate & catalogue discipline

* **2B-S3-001 S0_RECEIPT_MISSING (Abort)** — No `s0_gate_receipt_2B` for target fingerprint.
  *Context:* `fingerprint`.

* **2B-S3-020 DICTIONARY_RESOLUTION_ERROR (Abort)** — Input ID could not be resolved for required partition/path.
  *Context:* `id`, `expected_partition_or_path`.

* **2B-S3-021 PROHIBITED_LITERAL_PATH (Abort)** — Attempted read/write via a non-Dictionary path.
  *Context:* `path`.

* **2B-S3-022 UNDECLARED_ASSET_ACCESSED (Abort)** — Asset accessed but absent from S0 `sealed_inputs_2B`.
  *Context:* `id|path`.

* **2B-S3-023 NETWORK_IO_ATTEMPT (Abort)** — Network I/O detected.
  *Context:* `endpoint`.

### 10.2 Policy shape & minima

* **2B-S3-031 POLICY_SCHEMA_INVALID (Abort)** — `day_effect_policy_v1` fails schema/parse.
  *Context:* `schema_errors[]`.

* **2B-S3-032 POLICY_MINIMA_MISSING (Abort)** — Required policy fields missing (e.g., `rng_engine`, `rng_stream_id`, `draws_per_row`, `sigma_gamma`, `day_range`).
  *Context:* `missing_keys[]`.

* **2B-S3-033 DAY_RANGE_INVALID (Abort)** — `day_range` malformed or `start_day > end_day`.
  *Context:* `start_day`, `end_day`.

### 10.3 Grouping & coverage

* **2B-S3-040 JOIN_KEY_MISMATCH (Abort)** — Missing join partner on `(merchant_id, legal_country_iso, site_order)`.
  *Context:* `missing_keys_sample[]`.

* **2B-S3-041 TZ_GROUP_MULTIMAP (Abort)** — More than one `tzid` for a single site key.
  *Context:* `site_key`, `tzids[]`.

* **2B-S3-050 COVERAGE_MISMATCH (Abort)** — Missing/extra rows vs required `{merchants × tz_groups × days}` grid.
  *Context:* `missing_rows_sample[]`, `extra_rows_sample[]`.

* **2B-S3-042 PK_DUPLICATE (Abort)** - Duplicate `(merchant_id, utc_day, tz_group_id)` in output.
  *Context:* `key`.

* **2B-S3-083 WRITER_ORDER_NOT_PK (Abort)** — Row emission order differs from PK order.
  *Context:* `first_offending_row_index`.

### 10.4 Domain & RNG coherence

* **2B-S3-057 NON_POSITIVE_GAMMA (Abort)** — `gamma ≤ 0`.
  *Context:* `merchant_id`, `utc_day`, `tz_group_id`, `gamma`.

* **2B-S3-058 NONFINITE_LOG_GAMMA (Abort)** — `log_gamma` not finite.
  *Context:* `merchant_id`, `utc_day`, `tz_group_id`, `log_gamma`.

* **2B-S3-059 SIGMA_MISMATCH (Abort)** — `sigma_gamma` not constant or ≠ policy value.
  *Context:* `policy_sigma`, `observed_sigma_sample[]`.

* **2B-S3-060 RNG_ENGINE_MISMATCH (Abort)** — RNG engine used ≠ policy `rng_engine`.
  *Context:* `expected`, `observed`.

* **2B-S3-061 RNG_STREAM_MISMATCH (Abort)** — `rng_stream_id` ≠ policy stream id.
  *Context:* `expected`, `observed`.

* **2B-S3-062 RNG_DRAWS_COUNT_MISMATCH (Abort)** — `draws_total` ≠ required rows count or `draws_per_row ≠ 1`.
  *Context:* `expected_draws`, `observed_draws`.

* **2B-S3-063 RNG_COUNTER_NOT_MONOTONE (Abort)** — 128-bit counters not strictly increasing in writer order.
  *Context:* `row_index`, `prev_counter`, `counter`.

* **2B-S3-064 RNG_COUNTER_WRAP (Abort)** — 128-bit counter overflow/wrap detected.
  *Context:* `counter_before`, `counter_after`.

### 10.5 Identity, partitions & immutability

* **2B-S3-070 PARTITION_SELECTION_INCORRECT (Abort)** — Not exactly `seed={seed}/fingerprint={fingerprint}` (or wrong policy selection semantics).
  *Context:* `id`, `expected`, `actual`.

* **2B-S3-071 PATH_EMBED_MISMATCH (Abort)** - Embedded identity differs from path tokens.
  *Context:* `embedded`, `path_token`.

* **2B-S3-086 CREATED_UTC_MISMATCH (Abort)** - `created_utc` ≠ S0 receipt `verified_at_utc`.
  *Context:* `created_utc`, `verified_at_utc`.

* **2B-S3-080 IMMUTABLE_OVERWRITE (Abort)** — Target partition not empty and bytes differ.
  *Context:* `target_path`.

* **2B-S3-081 NON_IDEMPOTENT_REEMIT (Abort)** — Re-emit produced byte-different output for identical inputs.
  *Context:* `digest_prev`, `digest_now`.

* **2B-S3-082 ATOMIC_PUBLISH_FAILED (Abort)** — Staging/rename not atomic or post-publish verification failed.
  *Context:* `staging_path`, `final_path`.

* **2B-S3-030 OUTPUT_SCHEMA_INVALID (Abort)** — `s3_day_effects` fails its schema anchor.
  *Context:* `schema_errors[]`.

### 10.6 Day-range materialisation

* **2B-S3-090 DAY_GRID_MISMATCH (Abort)** — `utc_day` set in output ≠ inclusive grid from policy `day_range`.
  *Context:* `expected_days_count`, `observed_days_count`, `first_missing_day?`, `first_extra_day?`.

### 10.7 WARN class

* **2B-S3-191 TZID_NOT_IN_SITE_TIMEZONES (Warn)** — A `tz_group_id` in output not found in `site_timezones@{seed,fingerprint}`; log examples.
  *Context:* `tzids_sample[]`.

### 10.8 Standard message fields (Binding)

All failures MUST include:
`code`, `severity`, `message`, `fingerprint`, `seed`, `validator` (or `"runtime"`), and `context{…}` as specified above.

### 10.9 Validator → code map (Binding)

| Validator                                    | Canonical codes (may emit multiple) |
|----------------------------------------------|-------------------------------------|
| **V-01 Prior gate evidence present**         | 2B-S3-001                           |
| **V-02 Dictionary-only resolution**          | 2B-S3-020, 2B-S3-021                |
| **V-03 Partition/selection exact**           | 2B-S3-070                           |
| **V-04 Policy minima present**               | 2B-S3-031, 2B-S3-032, 2B-S3-033     |
| **V-05 Group universe well-defined**         | 2B-S3-040, 2B-S3-041                |
| **V-06 Coverage: merchants × groups × days** | 2B-S3-050                           |
| **V-07 PK uniqueness**                       | 2B-S3-042                           |
| **V-08 Writer order = PK**                   | 2B-S3-083                           |
| **V-09 Domain: γ/log-γ/sigma**               | 2B-S3-057, 2B-S3-058, 2B-S3-059     |
| **V-10 Sigma echo coherent**                 | 2B-S3-059                           |
| **V-11 RNG engine/stream echo**              | 2B-S3-060, 2B-S3-061                |
| **V-12 Draws accounting**                    | 2B-S3-062                           |
| **V-13 Counter monotonicity / no reuse**     | 2B-S3-063, 2B-S3-064                |
| **V-14 Created time canonical**              | 2B-S3-086 *(if used)*               |
| **V-15 Path↔embed equality**                 | 2B-S3-071                           |
| **V-16 Output shape valid**                  | 2B-S3-030                           |
| **V-17 Write-once immutability**             | 2B-S3-080                           |
| **V-18 Idempotent re-emit**                  | 2B-S3-081                           |
| **V-19 No network & no extra reads**         | 2B-S3-023, 2B-S3-022, 2B-S3-021     |
| **V-20 Day-range materialisation**           | 2B-S3-090                           |
| **V-21 tzid validity echo**                  | 2B-S3-191 *(Warn)*                  |

*(If you do not number a separate validator for “Created time canonical,” drop the row marked 2B-S3-086 and keep the check embedded under V-15/§8.11 as you’ve done in S1/S2.)*

---

## 11. **Observability & run-report (Binding)**

### 11.1 Purpose

Emit one **structured JSON run-report** that proves what S3 read, the tz-group universe it formed, the RNG it used, the factors it produced, and what it published. The run-report is **diagnostic (non-authoritative)**; **`s3_day_effects`** remains the source of truth.

### 11.2 Emission

* S3 **MUST** write the run-report to **STDOUT** as a single JSON document on successful publish (and on abort, if possible).
* S3 **MAY** persist the same JSON to an implementation-defined log. Persisted copies **MUST NOT** be used by downstream contracts.

### 11.3 Top-level shape (fields-strict)

The run-report **MUST** contain:

* `component`: `"2B.S3"`
* `fingerprint`: `<hex64>`
* `seed`: `<string>`
* `created_utc`: ISO-8601 UTC (echo of S0 `verified_at_utc`)
* `catalogue_resolution`: `{ dictionary_version: <semver>, registry_version: <semver> }`
* `policy`:

  * `id`: `"day_effect_policy_v1"`
  * `version_tag`: `<string>`
  * `sha256_hex`: `<hex64>`
  * `rng_engine`: `<string>` (e.g., `philox_2x64_10`)
  * `rng_stream_id`: `<string>`
  * `sigma_gamma`: `<float>` (σ)
  * `day_range`: `{ start_day: "YYYY-MM-DD", end_day: "YYYY-MM-DD" }` *(inclusive)*
* `inputs_summary`:

  * `weights_path`: `<string>` *(Dictionary-resolved `s1_site_weights@seed,fingerprint`)*
  * `timezones_path`: `<string>` *(Dictionary-resolved `site_timezones@seed,fingerprint`)*
  * `merchants_total`: `<int>`
  * `tz_groups_total`: `<int>` *(distinct `merchant_id × tz_group_id` pairs)*
  * `days_total`: `<int>` *(|inclusive day grid|)*
* `rng_accounting`:

  * `rows_expected`: `<int>` = `merchants_total × avg_groups_per_merchant × days_total`
  * `rows_written`: `<int>`
  * `draws_total`: `<int>` *(should equal `rows_written`)*
  * `first_counter`: `{ hi: <u64>, lo: <u64> }`
  * `last_counter`:  `{ hi: <u64>, lo: <u64> }`
* `publish`:

  * `target_path`: `<string>` *(Dictionary-resolved path to `s3_day_effects`)*
  * `bytes_written`: `<int>`
  * `write_once_verified`: `<bool>`
  * `atomic_publish`: `<bool>`
* `validators`: `[ { id: "V-01", status: "PASS|FAIL|WARN", codes: [ "2B-S3-0XX", … ] } … ]`
* `summary`: `{ overall_status: "PASS|FAIL", warn_count: <int>, fail_count: <int> }`
* `environment`: `{ engine_commit?: <string>, python_version: <string>, platform: <string>, network_io_detected: <int> }`

*(Fields-strict: no extra keys beyond those listed.)*

### 11.4 Evidence & samples (bounded, deterministic)

Include **bounded** samples sufficient for offline verification without scanning the full dataset. All selections are **deterministic**:

* `samples.rows` — up to **20** output rows
  `{ merchant_id, utc_day, tz_group_id, gamma, log_gamma, sigma_gamma, rng_stream_id, rng_counter_hi, rng_counter_lo }`
  *(pick by lexicographic `(merchant_id, utc_day, tz_group_id)` order, first N)*

* `samples.coverage_by_day` — up to **10** entries
  `{ utc_day, expected_groups: <int>, observed_groups: <int> }`
  *(pick earliest days first)*

* `samples.tz_groups_per_merchant` — up to **10** entries
  `{ merchant_id, groups_expected: <int>, groups_observed: <int> }`
  *(pick merchants with largest absolute difference first, then `merchant_id`)*

* `samples.rng_monotonic` — up to **10** adjacent row pairs showing counters are strictly increasing
  `{ row_rank, prev: {hi,lo}, curr: {hi,lo} }`
  *(pick first N pairs where the difference is smallest to surface near-ties)*

* `samples.warn_tzids` *(only if WARN V-21 fired)* — up to **10** tzids not present in `site_timezones`
  `{ tz_group_id }` *(lexicographic first N)*

### 11.5 Counters (minimum set)

S3 **MUST** emit at least:

* `merchants_total`, `tz_groups_total`, `days_total`
* `rows_expected`, `rows_written`, `draws_total`
* `max_abs_log_gamma` *(max over |`log_gamma`|)*
* `sigma_gamma` *(echo)*
* `nonpositive_gamma_rows` *(should be 0)*
* `pk_duplicates` *(should be 0)*, `join_misses` *(should be 0)*
* Durations (milliseconds): `resolve_ms`, `join_groups_ms`, `draw_ms`, `write_ms`, `publish_ms`

### 11.6 Histograms / distributions (optional, bounded)

If emitted, histograms **MUST** use fixed binning and be size-bounded:

* `hist.log_gamma` — fixed bins centred around 0 covering at least `±6·σ`.
* `hist.gamma` — fixed bins over `(0, upper)` with policy-declared cap.
* `hist.groups_per_merchant` — fixed small integer bins.

### 11.7 Determinism of lists

Arrays **MUST** be emitted in deterministic order:

* `validators` sorted by validator ID (`"V-01"` …).
* `samples.rows` in PK order; other samples as specified above.
* Any lists of IDs/digests lexicographic by ID with 1:1 alignment to digest lists.

### 11.8 PASS/WARN/FAIL semantics

* `overall_status = "PASS"` iff **all Abort-class validators** succeeded.
* WARN-class validator failures increment `warn_count` and **MUST** appear in `validators[]` with `status: "WARN"`.
* On any Abort-class failure, `overall_status = "FAIL"`; publish **MUST NOT** occur, but an attempted run-report **SHOULD** still be emitted with partial data when safe.

### 11.9 Privacy & retention

* The run-report **MUST NOT** include raw dataset bytes; only keys, paths, counts, digests, counters, offsets/lengths, and derived metrics.
* Retention is governed by the Registry’s diagnostic-log policy; the run-report is **not** an authoritative artefact and **MUST NOT** be hashed into any bundle.

### 11.10 ID-to-artifact echo

For traceability, S3 **MUST** echo an `id_map` array of the exact Dictionary-resolved paths used:

```
id_map: [
  { id: "s1_site_weights",    path: "<…/s1_site_weights/seed=…/fingerprint=…/>" },
  { id: "site_timezones",     path: "<…/site_timezones/seed=…/fingerprint=…/>" },
  { id: "day_effect_policy_v1", path: "<…/config/layer1/2B/policy/day_effect_policy_v1.json>" },
  { id: "s3_day_effects",     path: "<…/s3_day_effects/seed=…/fingerprint=…/>" }
]
```

Paths **MUST** be the exact values resolved/written at runtime.

---

## 12. **Performance & scalability (Informative)**

### 12.1 Workload model & symbols

* **M** = merchants.
* **Gᵢ** = number of tz-groups for merchant *i*.
* **D** = number of UTC days in `policy.day_range` (*inclusive*).
* **R** = total output rows = `D × Σᵢ Gᵢ`.
* **S** = total sites in `s1_site_weights` (used only to form groups; S3 is group-level).

S3 is a single pass to (a) form tz-groups, then (b) produce **R** log-normal draws and write **R** rows.

---

### 12.2 Time characteristics

* **Group formation (join & distinct):** `O(S)` to join `s1_site_weights` with `site_timezones` on the PK and collect distinct tzids per merchant.
* **Day grid materialisation:** `O(D)`.
* **Draws & row materialisation:** `O(R)` (one Philox draw + constant work per row).
* **Serialisation:** `O(R)` to write `s3_day_effects`.

Overall: `O(S + R)`.

---

### 12.3 Memory footprint

* **Working set:** `O(max Gᵢ)` when emitting one merchant at a time (tzid set + a small per-merchant buffer).
* **Day grid:** `O(1)` if you iterate days; `O(D)` if you prebuild a list.
* **No blob staging:** only a single Parquet partition is written; no whole-dataset buffering.

---

### 12.4 I/O discipline

* **Reads:** one sequential scan of `s1_site_weights@{seed,fingerprint}` (project PK only) and one of `site_timezones@{seed,fingerprint}` (project PK + `tzid`).
* **Writes:** one partition at `…/s3_day_effects/seed={seed}/fingerprint={manifest_fingerprint}/`.
* **Atomic publish:** write to staging on the same filesystem, `fsync`, atomic rename.

---

### 12.5 RNG throughput & counter mapping

* **Draws:** exactly **one** Philox draw per output row (total **R** draws).
* **Counter mapping:** use a contiguous 128-bit counter range `base_counter … base_counter+R−1` in **writer order**; guarantees strict monotonicity with zero coordination if each rank *i* maps to `counter = base_counter + i`.
* **Capacity:** `R ≪ 2¹²⁸` by design; validator checks forbid wraparound.

---

### 12.6 Parallelism (safe patterns)

* **Across merchants and/or days:** shard the Cartesian grid into **disjoint, deterministic intervals of row ranks** (e.g., by merchant ranges, or by day blocks), ensuring each shard owns a contiguous `[i_lo, i_hi]` counter slice.
* **Deterministic merge:** shards emit temporary artefacts; a final single-threaded merge concatenates rows in strict PK order before the single atomic publish. Update counters or preassign rank intervals so the global sequence remains strictly increasing.
* **Forbidden:** any parallelism that changes PK order, reorders reductions, or causes counter reuse.

---

### 12.7 Numeric determinism guardrails

* **Arithmetic:** IEEE-754 binary64; round-to-nearest-even; no FMA/FTZ/DAZ.
* **ICDF:** fixed, deterministic `erf⁻¹`/exp implementation per the layer’s numeric policy (same coefficients/approximant across builds).
* **Serial reductions:** compute set operations (distinct, counts) in a stable order; do not rely on hash-map iteration order.

---

### 12.8 Throughput tips (non-binding)

* **Project early:** read only `{merchant_id, legal_country_iso, site_order}` from weights and `{…, tzid}` from timezones.
* **Group cache:** build a per-merchant sorted list of tzids once; stream days over that list to avoid repeated joins.
* **Row ranking:** compute row rank `i` on the fly as a triple nested loop over `(merchant, day, tz_group)` in PK order—no extra sort needed.
* **Vectorised math:** batch ICDF/`exp` on small arrays; the implementation must remain bit-stable.

---

### 12.9 Scale limits & mitigations

* **Large D (long ranges):** runtime grows linearly with **D**; prefer day sharding and deterministic merges.
* **High group cardinality:** worst-case `Gᵢ` is bounded by distinct tzids; memory stays `O(max Gᵢ)`.
* **Ungrouped inputs:** if inputs aren’t already PK-sorted, perform a deterministic external merge sort (fixed chunk size, fixed fan-in order) before the join.

---

### 12.10 Observability KPIs (suggested)

Track and alert on:

* `merchants_total`, `tz_groups_total`, `days_total`, `rows_expected`, `rows_written`, `draws_total`.
* `max_abs_log_gamma`, `sigma_gamma`.
* Timing: `resolve_ms`, `join_groups_ms`, `draw_ms`, `write_ms`, `publish_ms`.
* Data quality: `pk_duplicates`, `join_misses`, `nonpositive_gamma_rows`, `counter_monotonic_violations`.

---

### 12.11 Non-goals

* No network I/O, compression tricks, or probabilistic sampling beyond the governed Philox draw.
* No record-level updates/merges post-publish; any change requires a new `{seed,fingerprint}` (or new fingerprint per change control).

---

## 13. **Change control & compatibility (Binding)**

### 13.1 Scope

This section governs permitted changes to **2B.S3** after ratification and how those changes are versioned and rolled out. It applies to: the **procedure**, the **output dataset** `s3_day_effects`, the **RNG/distribution law**, required **columns/PK/partitions**, and **validators/error codes**.

---

### 13.2 Stable, non-negotiable surfaces (unchanged without a **major** bump)

Within the same **major** version, S3 **MUST NOT** change:

* **Output identity & partitions:** dataset ID `s3_day_effects`; partitions `[seed, fingerprint]`; **path↔embed equality**; write-once + atomic publish.
* **PK & keys:** primary key `[merchant_id, utc_day, tz_group_id]`; one row per `{merchant, tz_group, day}`; tz-group identity is the **IANA `tzid`** from `site_timezones`.
* **Deterministic/RNG posture:** **counter-based Philox** with governed stream ID and one draw per row; draw accounting and counter monotonicity as specified.
* **Distribution law:** `log_gamma ~ Normal(μ, σ²)` with `μ = −½·σ²` so **E[γ]=1**; `σ = sigma_gamma` from policy.
* **Numeric discipline:** IEEE-754 binary64; round-to-nearest-even; deterministic ICDF; stable serial reductions.
* **Required columns & meanings:** `gamma`, `log_gamma`, `sigma_gamma`, `rng_stream_id`, `rng_counter_lo`, `rng_counter_hi`, `created_utc` (semantics as defined here).
* **Acceptance posture:** the set and meaning of **Abort-class** validators (by ID).

Any change here is **breaking** → bump **major** (new anchors/IDs where applicable).

---

### 13.3 Backward-compatible changes (allowed with **minor** or **patch** bump)

* **Editorial clarifications** and examples that do not change behaviour. *(patch)*
* **Run-report** additions (new counters/samples/histograms); run-report is non-authoritative. *(minor/patch)*
* **Optional metadata columns** in `s3_day_effects` that validators ignore and consumers are not required to read. *(minor)*
* **WARN-class validators**: add new WARN checks or refine messages/contexts without altering PASS/FAIL criteria. *(minor)*
* **Policy surface extensions** that are **optional** (e.g., optional extra provenance fields) and do not alter existing required behaviour. *(minor)*

---

### 13.4 Breaking changes (require **major** bump + migration)

* Renaming the output ID, changing **partitions**, or altering **path families**.
* Changing **PK** or group identity (e.g., no longer using `tzid`), or relaxing the one-row-per `{merchant, tz_group, day}` law.
* Switching RNG engine, changing the **distribution form** (e.g., non-log-normal) or the **E[γ]=1** construction, or altering ICDF/numeric rules such that byte outputs differ for the same inputs.
* Removing or changing semantics of required **columns** (`gamma`, `log_gamma`, `sigma_gamma`, `rng_*`, `created_utc`).
* Reclassifying a **WARN** validator to **Abort**, or adding a **new Abort** validator that can fail for previously valid outputs.
* Allowing **literal paths** or **network I/O**, or removing Dictionary-only resolution / **S0-evidence** rule.

---

### 13.5 SemVer & release discipline

* **Major:** any change listed in §13.4 → bump spec + schema anchor (e.g., `#/plan/s3_day_effects_v2`), update Dictionary/Registry entries, and publish migration notes.
* **Minor:** additive, backward-compatible behaviour (optional metadata, WARN validators, run-report fields).
* **Patch:** editorial only (no shape/procedure/validators change).

When Status = **frozen**, post-freeze edits are **patch-only** unless a ratified minor/major is published.

---

### 13.6 Relationship to policy bytes

* The **values** of `sigma_gamma`, `rng_engine`, `rng_stream_id`, and `day_range` are provided by **`day_effect_policy_v1`**. Updating policy **bytes** does **not** change this spec and is **not** a spec version event; it produces different sealed inputs (captured by S0) and therefore different output rows.
* **Removing** a required policy entry or changing its **meaning** such that S3 acceptance changes is **breaking** and requires a **major** of this spec and the policy anchor.

---

### 13.7 Compatibility guarantees to downstream states (S4–S6)

* Downstreams **MAY** rely on: presence and shape of `s3_day_effects`, PK/partitions, `gamma` semantics (log-normal with E[γ]=1), and RNG provenance fields.
* Downstreams **MUST NOT** rely on run-report structure, nor assume any undocumented columns.

---

### 13.8 Deprecation & migration protocol

* Changes are proposed → reviewed → ratified with a **change log** describing impact, validator deltas, new anchors, and migration steps.
* For majors, a **dual-publish window** is recommended: emit `v1` and `v2` in parallel (v2 authoritative; v1 legacy) for a time-boxed period.

---

### 13.9 Rollback policy

* Outputs are **write-once**; rollback means publishing a **new** `(seed,fingerprint)` (or reverting to a prior fingerprint) that reproduces the last known good behaviour. No in-place mutation.

---

### 13.10 Evidence of compatibility

* Each release MUST include: schema diffs, validator table diffs, and a conformance run showing previously valid S3 inputs still **PASS** (for minor/patch).
* CI MUST run a regression suite: coverage grid, PK uniqueness/order, domain checks, RNG accounting/monotonic counters, immutability, idempotent re-emit.

---

### 13.11 Registry/Dictionary coordination

* Dictionary changes that alter ID names, path families, or partition tokens for `s3_day_effects` are **breaking** unless accompanied by new anchors/IDs and a migration plan.
* Registry edits limited to **metadata** (owner/licence/retention) are compatible; edits that change **existence** of required artefacts are breaking.

---

### 13.12 Validator/code namespace stability

* Validator IDs (`V-01`…`V-23`) and canonical codes (`2B-S3-…`) are **reserved**. New codes may be added; the meaning of existing codes **MUST NOT** change within a major.

---

## Appendix A — Normative cross-references *(Informative)*

> This appendix lists the authoritative artefacts S3 references. **Schemas** govern shape; the **Dataset Dictionary** governs ID → path/partitions/format; the **Artefact Registry** governs ownership/licence/retention. Binding rules live in §§1–13.

### A.1 Authority chain (this segment)

* **Schema pack (shape authority):** `schemas.2B.yaml`

  * **Output anchor used by S3:**

    * `#/plan/s3_day_effects` — per-merchant × per-UTC-day × per-`tz_group_id` γ-factor table (fields-strict)
  * **Input/policy anchors referenced by S3:**

    * `#/plan/s1_site_weights` — frozen per-site weights (S1)
    * `schemas.2A.yaml#/egress/site_timezones` — site → `tzid` mapping (2A)
    * `#/policy/day_effect_policy_v1` — RNG engine/stream, `sigma_gamma`, inclusive `day_range`, record fields
  * **Common defs:** `#/$defs/hex64`, `#/$defs/partition_kv`
    *(timestamps reuse `schemas.layer1.yaml#/$defs/rfc3339_micros`)*

* **Dataset Dictionary (catalogue authority):** `dataset_dictionary.layer1.2B.yaml`

  * **S3 output & path family:**

    * `s3_day_effects` → `data/layer1/2B/s3_day_effects/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` (format: parquet)
  * **S3 inputs (Dictionary IDs):**

    * `s1_site_weights` → `data/layer1/2B/s1_site_weights/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` (parquet)
    * `site_timezones` → `data/layer1/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` (parquet)
    * `day_effect_policy_v1` → `config/layer1/2B/policy/day_effect_policy_v1.json` *(single file; **no partition tokens**; S0-sealed path/digest)*

* **Artefact Registry (metadata authority):** `artefact_registry_2B.yaml`

  * Ownership/retention for `s3_day_effects`, and cross-layer pointers for `site_timezones`; policy ownership for `day_effect_policy_v1`.

### A.2 Prior state evidence (2B.S0)

* **`s0_gate_receipt_2B`** — gate verification, identity, catalogue versions (fingerprint-scoped).
* **`sealed_inputs_2B`** — authoritative list of sealed assets (IDs, tags, digests, paths, partitions).
  *(S3 does not re-hash 1B; it relies on this evidence.)*

### A.3 Inputs consumed by S3 (read-only)

* **Weights table (from S1):**

  * `s1_site_weights` → `data/layer1/2B/s1_site_weights/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
  * **Shape:** `schemas.2B.yaml#/plan/s1_site_weights`
* **Site time-zones (from 2A):**

  * `site_timezones` → `data/layer1/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
  * **Shape:** `schemas.2A.yaml#/egress/site_timezones`
* **Day-effect policy:**

  * `day_effect_policy_v1` → `config/layer1/2B/policy/day_effect_policy_v1.json`
  * **Shape:** `schemas.2B.yaml#/policy/day_effect_policy_v1`
  * **Selection:** token-less; use the **exact S0-sealed path/digest** for this fingerprint.

### A.4 Output produced by this state

* **`s3_day_effects`** (Parquet; `[seed, fingerprint]`)
  **Shape:** `schemas.2B.yaml#/plan/s3_day_effects`
  **Dictionary path:** `data/layer1/2B/s3_day_effects/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
  **PK:** `[merchant_id, utc_day, tz_group_id]`
  **Required fields:** `gamma`, `log_gamma`, `sigma_gamma`, `rng_stream_id`, `rng_counter_lo`, `rng_counter_hi`, `created_utc`
  **Writer order:** `[merchant_id, utc_day, tz_group_id]`

### A.5 Identity & token discipline

* **Tokens:** `seed={seed}`, `fingerprint={manifest_fingerprint}`
* **Partition law:** S3 output partitions by **both** tokens; inputs selected exactly as declared (policy is token-less).
* **Path↔embed equality:** any embedded identity must equal the path tokens.

### A.6 Segment context

* **Segment overview:** `state-flow-overview.2B.txt` *(context only; this S3 spec governs).*
* **Layer identity & gate laws:** programme-wide rules (No PASS → No read; hashing law; write-once + atomic publish; RNG audit discipline).

---
