# State 2B.S4 — Zone-group renormalisation

## 1. **Document metadata & status (Binding)**

**Component:** Layer-1 · Segment **2B** — **State-4 (S4)** · *Zone-group renormalisation*
**Document ID:** `seg_2B.s4.group_weights`
**Version (semver):** `v1.0.0-alpha`
**Status:** `alpha` *(normative; semantics lock at `frozen` in a ratified release)*
**Owners:** Design Authority (DA): **Esosa Orumwese** · Review Authority (RA): **Layer-1 Governance**
**Effective date:** **2025-11-04 (UTC)**
**Canonical location:** `contracts/specs/l1/seg_2B/state.2B.s4.expanded.v1.0.0.txt`

**Authority chain (Binding):**
**JSON-Schema pack** = shape authority → `schemas.2B.yaml`
**Dataset Dictionary** = ID→path/partitions/format → `dataset_dictionary.layer1.2B.yaml`
**Artefact Registry** = existence/licence/retention → `artefact_registry_2B.yaml`

**Normative cross-references (Binding):**

* Prior state evidence: **`s0_gate_receipt_2B`**, **`sealed_inputs_v1`**.
* Inputs: **`s1_site_weights`** (2B · S1), **`site_timezones`** (2A egress), **`s3_day_effects`** (2B · S3).
* Segment overview: `state-flow-overview.2B.txt` (context only; this spec governs).

**Segment invariants (Binding):**

* **Run identity:** `{ seed, manifest_fingerprint }`.
* **Partitioning for S4 outputs:** `[seed, fingerprint]`; **path↔embed equality** MUST hold.
* **Catalogue discipline:** Dictionary-only resolution; literal paths forbidden; subset-of-S0 rule enforced.
* **RNG posture:** **RNG-free**.
* **Numeric discipline:** IEEE-754 binary64, round-to-nearest-even; stable serial reductions.
* **Gate law:** **No PASS → No read** applies throughout the segment.

---

## 2. **Purpose & scope (Binding)**

**Purpose.** Produce the **per-merchant, per-UTC-day** routing **mix across tz-groups** by combining S1 **base shares** (aggregated by tzid) with S3 **γ(d, tz_group)** and **renormalising across groups** so each merchant’s day total sums to **1.0**. The step is **RNG-free** and deterministic; with S3’s `E[γ]=1`, the long-run expectation of each group’s share remains the S1 base share.

**S4 SHALL:**

* **Form base shares deterministically**: join S1 keys to `site_timezones`, group by tzid per merchant, and compute
  `base_share(group) = Σ_site p_weight` (exact within a fixed tolerance ε).
* **Combine with S3 factors**: for every `{merchant_id, utc_day, tz_group_id}`, compute
  `raw = base_share(group) × gamma(d, group)`.
* **Renormalise across groups (per day, per merchant)**:
  `p_group = raw / Σ_groups raw`, requiring `Σ raw > 0` (Abort otherwise).
  Emit `{merchant_id, utc_day, tz_group_id, p_group, base_share, gamma, created_utc}`.
* **Preserve determinism and identity**: operate **RNG-free**, write `s4_group_weights` partitioned by `[seed, fingerprint]`, emit rows in **PK order**, and set `created_utc =` S0 `verified_at_utc`.

**Scope (included).**

* Catalogue-only resolution of inputs.
* Exact tz-grouping by **IANA tzid**.
* Binary64 arithmetic, round-to-nearest-even; fixed normalisation tolerance ε.
* Write-once, atomic publish; idempotent re-emit allowed only if bytes are identical.

**Out of scope.**

* Building alias tables (S2), drawing γ (S3), per-arrival routing (S5/S6), audits/PASS packaging (S7/S8), or any change to site-level weights.

**Prohibitions.**

* No network I/O.
* No literal paths (Dictionary-only).
* No alternative groupings or reweighting beyond `base_share × gamma` and cross-group renormalisation.

---

## 3. **Preconditions & sealed inputs (Binding)**

### 3.1 Preconditions (Abort on failure)

* **Prior gate evidence.** A valid **`s0_gate_receipt_2B`** for the target **`manifest_fingerprint`** MUST exist.
* **Run identity fixed.** The pair **`{ seed, manifest_fingerprint }`** is fixed at S4 start and MUST remain constant.
* **RNG posture.** S4 performs **no random draws** (RNG-free).
* **Catalogue discipline.** All inputs resolve by **Dataset Dictionary IDs**; **literal paths are forbidden**.
* **Subset-of-S0 rule.** Every asset S4 reads MUST appear in S0’s `sealed_inputs_v1` for this fingerprint.

### 3.2 Required sealed inputs (must all be present)

S4 SHALL read **only** the following, for this run’s identity:

1. **`s1_site_weights`** — 2B · S1 output at `seed={seed} / fingerprint={manifest_fingerprint}` (provides site-level `p_weight`).
2. **`site_timezones`** — 2A egress at `seed={seed} / fingerprint={manifest_fingerprint}` (provides `tzid` per site for tz-grouping).
3. **`s3_day_effects`** — 2B · S3 output at `seed={seed} / fingerprint={manifest_fingerprint}` (provides `gamma` factors per `{merchant_id, utc_day, tz_group_id}`).

> All required assets MUST be resolvable via the Dictionary and MUST appear in S0’s inventory for the same fingerprint.

### 3.3 Resolution & partition discipline (Binding)

* **Exact partitions (reads):**
  • `s1_site_weights` → **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
  • `site_timezones` → **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
  • `s3_day_effects` → **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
* **Day grid source.** The set of `utc_day` values S4 uses is **exactly** the inclusive day grid present in `s3_day_effects`; S4 **does not** materialise days independently.
* **Key join basis.** Form tz-groups by joining `s1_site_weights` keys `(merchant_id, legal_country_iso, site_order)` to `site_timezones` on the **same** keys and taking `tzid` as `tz_group_id`.

### 3.4 Integrity & provenance inputs (Binding)

* **Created time.** Discover canonical `created_utc` from S0’s receipt (`verified_at_utc`) and use it for all S4 rows.
* **Base-share aggregation basis.** For each merchant, **aggregate S1** over the join result to compute
  `base_share(group) = Σ_site p_weight`; this aggregation is authoritative for S4 and MUST sum to **1.0 within tolerance ε** across groups for the merchant (validated later).

### 3.5 Prohibitions (Binding)

* **No network I/O.** All bytes are local/managed.
* **No extra inputs.** S4 MUST NOT read any dataset/policy other than §3.2.
* **No re-hashing of 1B.** S4 relies on S0’s gate receipt; it SHALL NOT recompute upstream bundle hashes.
* **No alternate groupings.** Tz-group identity is the **IANA `tzid`** from `site_timezones`; S4 SHALL NOT invent or substitute other grouping keys.

---

## 4. **Inputs & authority boundaries (Binding)**

### 4.1 Catalogue authorities

* **Schema pack** (`schemas.2B.yaml`) is the **shape authority** for S4’s output and for any referenced input anchors.
* **Dataset Dictionary** (`dataset_dictionary.layer1.2B.yaml`) is the **sole authority** for resolving **IDs → path templates, partitions, and format** (token expansion is binding).
* **Artefact Registry** (`artefact_registry_2B.yaml`) governs **existence/licence/retention/ownership**; it does **not** override Dictionary paths.

### 4.2 Inputs S4 MAY read (and nothing else)

Resolve **only** these IDs via the Dictionary (no literal paths):

1. **`s1_site_weights`** — 2B · S1 output at `seed={seed} / fingerprint={manifest_fingerprint}`.
2. **`site_timezones`** — 2A egress at `seed={seed} / fingerprint={manifest_fingerprint}` (provides `tzid` per site).
3. **`s3_day_effects`** — 2B · S3 output at `seed={seed} / fingerprint={manifest_fingerprint}` (provides `{utc_day, tz_group_id, gamma}`).

> **Subset-of-S0 rule:** Every asset S4 reads **MUST** appear in S0’s `sealed_inputs_v1` for the same fingerprint. Accessing any asset not in that inventory is an error.

### 4.3 Prohibited resources & behaviours

* **No literal paths** (env overrides, ad-hoc strings/globs).
* **No network I/O** (HTTP/remote FS/cloud buckets).
* **No extra inputs** beyond §4.2.
* **No re-hashing of 1B**; S0’s receipt is the sole gate attestation.

### 4.4 Resolution & token discipline

* **Exact partitions (reads):**
  • `s1_site_weights` → **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
  • `site_timezones` → **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
  • `s3_day_effects` → **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
* **Day grid source:** S4 derives the set of `utc_day` values **only** from `s3_day_effects`; it MUST NOT synthesise or infer days independently.
* **Path↔embed equality (outputs):** any embedded identity in `s4_group_weights` **MUST** equal the Dictionary path tokens.

### 4.5 Input field & join expectations

* **Join basis:** join `s1_site_weights` keys `(merchant_id, legal_country_iso, site_order)` to `site_timezones` on the **same** keys; take `tzid` as `tz_group_id`.
* **Cardinality:** the join MUST be **1:1** for every key in `s1_site_weights`. Missing or multiple `tzid` for a key is an **Abort**.
* **Gamma lookup:** for each `{merchant_id, utc_day, tz_group_id}` produced by the join and S3 day grid, **exactly one** `gamma` must exist in `s3_day_effects` (one-to-one). Absence or duplicates is an **Abort**.

### 4.6 Trust boundary & sequencing

1. Verify S0 evidence for the target fingerprint exists.
2. Resolve `s1_site_weights`, `site_timezones`, and `s3_day_effects` via the Dictionary.
3. Form tz-groups from the join, aggregate base shares, then combine with S3 `gamma` and renormalise—strictly from these sealed inputs; do not consult any other sources.

### 4.7 Numeric & determinism constraints (inputs)

* **Numeric discipline:** read values as IEEE-754 binary64; no implicit type coercions that change value.
* **Ordering:** any grouping/aggregation MUST be performed in a stable order (PK order) so results are deterministic across runs and platforms.

---

## 5. **Outputs (datasets) & identity (Binding)**

### 5.1 Product (ID)

* **`s4_group_weights`** — per-merchant, per-UTC-day, per-`tz_group_id` **day-specific group mix** (normalised).

### 5.2 Identity & partitions

* **Run identity:** `{ seed, manifest_fingerprint }`.
* **Partitions (binding):** `[seed, fingerprint]` only.
* **Path↔embed equality:** Any embedded `manifest_fingerprint` (and, if echoed, `seed`) **MUST** byte-equal the path tokens.

### 5.3 Path family, format & catalogue authority

* **Dictionary binding (required):**
  `data/layer1/2B/s4_group_weights/seed={seed}/fingerprint={manifest_fingerprint}/`
  The **Dataset Dictionary** is the sole authority for ID → path/partitions/format; **literal paths are forbidden**.
* **Storage format:** `parquet` (Dictionary authority).
* **Shape authority:** `schemas.2B.yaml#/plan/s4_group_weights`.

### 5.4 Keys, writer order & order posture

* **Primary key (PK):** `[merchant_id, utc_day, tz_group_id]`.
* **Writer order:** **exactly** the PK order.
* **Order-free read:** Consumers MUST treat file order as non-authoritative; joins/aggregations are by PK only.

### 5.5 Required columns (anchor-owned)

Rows **MUST** include at least:

* `p_group` (double, ≥ 0) — normalised group weight for the `{merchant, day, group}`.
* `base_share` (double, ≥ 0) — Σ of S1 `p_weight` over sites in the group.
* `gamma` (double, > 0) — echo of S3 factor for `{merchant, day, group}`.
* `created_utc` (RFC-3339 UTC) — equals S0 `verified_at_utc`.
  *(Optional audit fields the anchor MAY expose: `mass_raw`, `denom_raw`.)*

### 5.6 Coverage & FK discipline

* **Coverage:** For every `utc_day` present in `s3_day_effects` and every tz-group in the merchant’s join set, **exactly one** row exists.
* **FK basis:** `tz_group_id` is the IANA `tzid` obtained by joining S1 keys with `site_timezones`; S4 MUST NOT introduce new keys.

### 5.7 Normalisation & tolerance (binding)

* For each `{merchant_id, utc_day}`, **Σ_group `p_group` = 1** within tolerance **ε** (programme constant).
* For each `{merchant_id}`, **Σ_group `base_share` = 1** within **ε** (recomputed from S1 join).

### 5.8 Write-once, immutability & idempotency

* **Single-writer, write-once:** Target partition **MUST** be empty before first publish.
* **Idempotent re-emit:** Re-publishing to the same partition is permitted **only** if bytes are **bit-identical**; otherwise **Abort**.
* **Atomic publish:** Stage → fsync → single atomic move; no partial files may become visible.

### 5.9 Provenance stamping

* `created_utc` **MUST** equal S0 `verified_at_utc`.
* If policy/dataset identifiers are echoed in metadata (anchor-permitting), they **MUST** match the S0-sealed values for this fingerprint.

### 5.10 Downstream reliance

* **S5/S6** SHALL: (1) select by `(seed, fingerprint)` via the Dictionary, (2) sample the tz-group using `p_group` for the given `{merchant, day}`, then (3) sample the site within that group using the **static S2 alias**.

---

## 6. **Dataset shapes & schema anchors (Binding)**

### 6.1 Shape authority

All shapes in this state are governed by the **2B schema pack** (`schemas.2B.yaml`). Shapes are **fields-strict** (no extras). The **Dataset Dictionary** binds IDs → path/partitions/format. The **Artefact Registry** carries ownership/licence/retention only.

---

### 6.2 Output table — `schemas.2B.yaml#/plan/s4_group_weights`

**Type:** table (**columns_strict: true**)

**Identity & keys (binding)**

* **Primary key (PK):** `[merchant_id, utc_day, tz_group_id]`
* **Partition keys:** `[seed, fingerprint]`
* **Writer sort:** `[merchant_id, utc_day, tz_group_id]`

**Columns (required unless marked “optional”)**

* `merchant_id` — `$ref: 'schemas.layer1.yaml#/$defs/id64'`, **nullable: false**
* `utc_day` — `{ type: string, format: date }`, **nullable: false**  *(UTC calendar day; `YYYY-MM-DD`.)*
* `tz_group_id` — `{ type: string, minLength: 1 }`, **nullable: false**  *(IANA `tzid` as group ID)*
* `p_group` — `{ type: number, minimum: 0.0, maximum: 1.0 }`, **nullable: false**  *(normalised day mix)*
* `base_share` — `{ type: number, minimum: 0.0, maximum: 1.0 }`, **nullable: false**  *(Σ of S1 `p_weight` over sites in group)*
* `gamma` — `{ type: number, exclusiveMinimum: 0.0 }`, **nullable: false**  *(echo of S3 factor)*
* `created_utc` — `$ref: 'schemas.layer1.yaml#/$defs/rfc3339_micros'`, **nullable: false**
* `mass_raw` — `{ type: number, minimum: 0.0 }`, **nullable: true** *(optional audit; = `base_share × gamma`)*
* `denom_raw` — `{ type: number, minimum: 0.0 }`, **nullable: true** *(optional audit; per-merchant/day Σ of `mass_raw`)*

**Notes (binding semantics)**

* For each `{merchant_id, utc_day}`: `Σ_group p_group = 1` **within ε** (validator-enforced).
* For each `{merchant_id}`: `Σ_group base_share = 1` **within ε** (recomputed from S1 join).
* `gamma` must equal the corresponding value in `s3_day_effects@{seed,fingerprint}`.

---

### 6.3 Referenced anchors (inputs)

* **Weights table (read-only):** `schemas.2B.yaml#/plan/s1_site_weights`
* **Site time-zones (read-only):** `schemas.2A.yaml#/egress/site_timezones`
* **Day effects (read-only):** `schemas.2B.yaml#/plan/s3_day_effects`

---

### 6.4 Common definitions

* `$defs.hex64` — `^[a-f0-9]{64}$`
* `$defs.partition_kv` — object of string tokens; **minProperties: 0** (token-less assets allowed in receipts/inventory)
* Timestamps reuse `schemas.layer1.yaml#/$defs/rfc3339_micros`.

---

### 6.5 Format & storage (Dictionary authority)

* **ID:** `s4_group_weights`
* **Path family:** `data/layer1/2B/s4_group_weights/seed={seed}/fingerprint={manifest_fingerprint}/`
* **Format:** `parquet`
* **Partitioning:** `[seed, fingerprint]` (no other tokens)

---

### 6.6 Structural & domain constraints (checked by anchor + validators)

* Table is **fields-strict**; no extra columns.
* PK uniqueness; writer order = PK.
* `p_group ∈ [0,1]`, `base_share ∈ [0,1]`, `gamma > 0`.
* Optional audits (if present) satisfy `p_group = mass_raw / denom_raw` and `denom_raw > 0`.
* Path↔embed equality holds for the partition tokens.

---

## 7. **Deterministic algorithm (RNG-free) (Binding)**

**Overview.** S4 performs a fixed transform from catalogued inputs to a byte-stable `s4_group_weights` table. No random draws, no network I/O. Arithmetic is IEEE-754 binary64, round-to-nearest-even; reductions are serial and order-stable. All selections and writes are Dictionary-resolved.

### 7.1 Resolve & snapshot

1. **Fix identity.** Capture `{seed, manifest_fingerprint}` from the run context.
2. **Resolve inputs by Dictionary IDs only:**
   `s1_site_weights@{seed,fingerprint}`, `site_timezones@{seed,fingerprint}`, `s3_day_effects@{seed,fingerprint}`.
3. **Set `created_utc`.** Read from S0 receipt `verified_at_utc` and use for all output rows.
4. **Materialise day grid `D`.** Extract the **distinct** `utc_day` values present in `s3_day_effects` and sort ascending (`YYYY-MM-DD`).

### 7.2 Build deterministic tz-groups (base shares)

5. **Join keys.** Left-join `s1_site_weights` PK `(merchant_id, legal_country_iso, site_order)` to `site_timezones` on the same keys. Abort if any key is missing or maps to multiple `tzid`.
6. **Group per merchant.** For each `merchant_id`, collect distinct `tz_group_id = tzid` and sort **lexicographically** (deterministic group order).
7. **Aggregate base shares.** For each `{merchant_id, tz_group_id}`, compute
   `base_share(merchant, group) = Σ_site p_weight` over the joined rows belonging to that group, summing in stable PK order.
8. **Base-mass check.** For each `merchant_id`, require `|Σ_group base_share − 1| ≤ ε`. Abort otherwise.

### 7.3 Combine with S3 factors (per day)

9. **Gamma lookup.** For each `{merchant_id, utc_day, tz_group_id}` with `utc_day ∈ D`, fetch the unique `gamma` from `s3_day_effects`. Abort on missing/duplicate rows.
10. **Raw mass.** Compute `mass_raw = base_share × gamma`. (Domain: `base_share ≥ 0`, `gamma > 0` ⇒ `mass_raw ≥ 0`.)

### 7.4 Cross-group renormalisation (per merchant, per day)

11. **Denominator.** For each `{merchant_id, utc_day}`, compute
    `denom_raw = Σ_group mass_raw` in the group order from §7.2.
12. **Positive mass requirement.** Require `denom_raw > 0`. (With `gamma > 0` and Σ base_share = 1 this holds; guard remains binding.)
13. **Normalise.** For each group, set `p_group = mass_raw / denom_raw`.
14. **Tiny-negative guard (numeric).** If any `p_group` is `−δ` with `0 < δ ≤ ε`, clamp to `0` and renormalise once to restore mass within ε. Abort if any `p_group < −ε` or if post-renormalisation `|Σ_group p_group − 1| > ε`.
15. **Echo values.** For each row, carry `base_share`, `gamma`, and (if the schema exposes them) `mass_raw` and `denom_raw`.

### 7.5 Row materialisation (writer order = PK)

16. **Record shape.** For every `{merchant_id, utc_day, tz_group_id}` in the Cartesian product of the merchant’s group set and `D`, emit
    `{ merchant_id, utc_day, tz_group_id, p_group, base_share, gamma, created_utc, [mass_raw?, denom_raw?] }`.
17. **Writer order.** Emit rows strictly in PK order `[merchant_id ↑, utc_day ↑, tz_group_id ↑]`.

### 7.6 Publish (write-once; atomic)

18. **Target partition (Dictionary-resolved):**
    `s4_group_weights@seed={seed}/fingerprint={manifest_fingerprint}`.
19. **Immutability.** Target must be empty; otherwise allow only **bit-identical** re-emit; else Abort.
20. **Atomic publish.** Write to staging on the same filesystem, `fsync`, then atomic rename. No partial files may become visible.

### 7.7 Post-publish assertions

21. **Path↔embed equality.** Any embedded identity equals path tokens.
22. **Coverage grid.** For every `merchant_id`, for every `tz_group_id` in that merchant’s group set, and for every `utc_day ∈ D`, exactly **one** row exists.
23. **Normalisation audit.** For each `{merchant_id, utc_day}`, require `|Σ_group p_group − 1| ≤ ε`.
24. **Base-share audit.** For each `merchant_id`, require `|Σ_group base_share − 1| ≤ ε` (recomputed from the join).

### 7.8 Prohibitions & determinism guards

25. **No RNG; no network.**
26. **No literal paths; no extra inputs** beyond §7.1.
27. **Stable arithmetic.** Serial reductions in a deterministic order; no data-dependent re-ordering that changes numeric outcomes.
28. **Replay.** Re-running S4 with identical sealed inputs produces **bit-identical** output.

---

## 8. **Identity, partitions, ordering & merge discipline (Binding)**

### 8.1 Identity law

* **Run identity:** `{ seed, manifest_fingerprint }` fixed at S4 start.
* **Output identity:** `s4_group_weights` **MUST** be identified and selected by **both** tokens.

### 8.2 Partitions & exact selection

* **Write partition:** `…/s4_group_weights/seed={seed}/fingerprint={manifest_fingerprint}/`.
* **Exact selection (read/write):** a single `(seed,fingerprint)` partition per publish; no wildcards, ranges, or multi-partition writes.

### 8.3 Path↔embed equality

* Any embedded `manifest_fingerprint` (and, if echoed, `seed`) **MUST** byte-equal the corresponding path tokens. Inequality is an error.

### 8.4 Writer order & file-order posture

* **Writer order:** rows **MUST** be emitted in **PK order** `[merchant_id, utc_day, tz_group_id]`.
* **Order-free read:** consumers **MUST** treat file order as non-authoritative; joins/aggregations are by PK only.

### 8.5 Single-writer, write-once

* Target partition **MUST** be empty before first publish.
* If the target exists:

  * **Byte-identical:** treat as a no-op (idempotent re-emit).
  * **Byte-different:** **Abort** with immutable-overwrite error.

### 8.6 Atomic publish

* Write to a same-filesystem **staging** location, `fsync`, then **atomic rename** into the final partition. No partial files may become visible.

### 8.7 Concurrency

* At most **one** active publisher per `(component=2B.S4, seed, manifest_fingerprint)`.
* A concurrent publisher **MUST** either observe existing byte-identical artefacts and no-op, or abort on attempted overwrite.

### 8.8 Merge discipline

* **No appends, compactions, or in-place updates.** Any change requires publishing to a **new** `(seed,fingerprint)` identity (or a new fingerprint per change-control rules).

### 8.9 Determinism & replay

* Re-running S4 with identical sealed inputs **MUST** reproduce **bit-identical** output.
* Numeric outcomes **MUST NOT** depend on thread scheduling or data-dependent re-ordering that changes reduction order.

### 8.10 Token hygiene

* Partition tokens **MUST** appear exactly once and in this order: `seed=…/fingerprint=…/`.
* Literal paths, environment-injected overrides, or ad-hoc globs are prohibited.

### 8.11 Provenance echo

* `created_utc` **MUST** equal the canonical S0 time (`verified_at_utc`) for this fingerprint.
* If dataset/policy identifiers are echoed in metadata, they **MUST** match the S0-sealed values.

### 8.12 Retention & ownership

* Retention, licence, and ownership are governed by the Registry; immutability is enforced by this section.

---

## 9. **Acceptance criteria (validators) (Binding)**

**Outcome rule.** **PASS** iff all **Abort** validators succeed. **WARN** validators may fail without blocking publish but MUST be recorded in the run-report.

**V-01 — Prior gate evidence present (Abort).**
` s0_gate_receipt_2B` exists for the target `manifest_fingerprint` and is discoverable via the Dictionary.

**V-02 — Dictionary-only resolution (Abort).**
All inputs (`s1_site_weights`, `site_timezones`, `s3_day_effects`) were resolved by **Dictionary IDs**; zero literal paths.

**V-03 — Partition/selection exact (Abort).**
Reads used only `…@seed={seed}/fingerprint={manifest_fingerprint}` for all three inputs (no wildcards, no cross-seed/fingerprint reads).

**V-04 — Join integrity (Abort).**
Join on keys `(merchant_id, legal_country_iso, site_order)` between `s1_site_weights` and `site_timezones` is **1:1** for every key in S1; no missing partner and no multiple `tzid` per key.

**V-05 — Base-share aggregation Σ=1 (Abort).**
For each merchant, `base_share(group) = Σ_site p_weight` over the joined rows and
`| Σ_group base_share − 1 | ≤ ε` (programme tolerance).

**V-06 — Coverage: merchants × groups × days (Abort).**
For every merchant, for every tz-group (tzid) found in the join, and for every `utc_day` present in `s3_day_effects`, **exactly one** row exists in `s4_group_weights`.

**V-07 — PK uniqueness (Abort).**
No duplicate `(merchant_id, utc_day, tz_group_id)` in `s4_group_weights`.

**V-08 — Writer order = PK (Abort).**
Row emission order is exactly `[merchant_id, utc_day, tz_group_id]` ascending.

**V-09 — Gamma echo coherent (Abort).**
For each `{merchant, utc_day, tz_group_id}`, the echoed `gamma` equals the value in `s3_day_effects@{seed,fingerprint}`.

**V-10 — Domain checks (Abort).**
`base_share ≥ 0`, `gamma > 0`, and `p_group ∈ [0,1]` for every row.

**V-11 — Normalisation across groups (Abort).**
For each `{merchant, utc_day}`, `| Σ_group p_group − 1 | ≤ ε`. Require `denom_raw > 0` if the audit column is present.

**V-12 — Day-grid equality (Abort).**
The set of `utc_day` values in `s4_group_weights` equals the **inclusive** day grid implied by `s3_day_effects` (no gaps, no extras).

**V-13 — Output shape valid (Abort).**
` s4_group_weights` validates against `schemas.2B.yaml#/plan/s4_group_weights` (fields-strict).

**V-14 — Created time canonical (Abort).**
`created_utc` in every row equals the S0 receipt’s `verified_at_utc` for this fingerprint.

**V-15 — Path↔embed equality (Abort).**
Any embedded identity equals the dataset path tokens (`seed`, `fingerprint`).

**V-16 — Write-once immutability (Abort).**
Target partition was empty before publish, or existing bytes are **bit-identical**.

**V-17 — Idempotent re-emit (Abort).**
Re-running S4 with identical sealed inputs produces **byte-identical** output; otherwise abort rather than overwrite.

**V-18 — No network & no extra reads (Abort).**
Execution performed with network I/O disabled and accessed **only** the assets listed in S0’s inventory for this fingerprint.

**V-19 — Optional audit coherence (Abort if present).**
If `mass_raw`/`denom_raw` columns are present, then for each `{merchant, utc_day}`:
`denom_raw = Σ_group mass_raw` and `p_group = mass_raw / denom_raw` (all within ε), with `denom_raw > 0`.

**V-20 — Base-share recomputation check (Abort).**
Re-aggregating S1 over the join during validation reproduces the stored `base_share` values per group within ε.

**Reporting.** The run-report MUST include: validator outcomes; counts (`merchants_total`, `tz_groups_total`, `days_total`, `rows_expected`, `rows_written`); max per-merchant/day mass error before/after normalisation; and deterministic samples of rows `{merchant_id, utc_day, tz_group_id, base_share, gamma, p_group}` with evidence of day-grid and normalisation checks.

---

## 10. **Failure modes & canonical error codes (Binding)**

**Code namespace.** `2B-S4-XYZ` (zero-padded). **Severity** ∈ {**Abort**, **Warn**}.
Every failure log entry **MUST** include: `code`, `severity`, `message`, `fingerprint`, `seed`, `validator` (e.g., `"V-11"` or `"runtime"`), and a `context{…}` object with the keys noted below.

### 10.1 Gate & catalogue discipline

* **2B-S4-001 S0_RECEIPT_MISSING (Abort)** — No `s0_gate_receipt_2B` for target fingerprint.
  *Context:* `fingerprint`.

* **2B-S4-020 DICTIONARY_RESOLUTION_ERROR (Abort)** — Input ID could not be resolved for the required partition.
  *Context:* `id`, `expected_partition`.

* **2B-S4-021 PROHIBITED_LITERAL_PATH (Abort)** — Attempted read/write via a non-Dictionary path.
  *Context:* `path`.

* **2B-S4-022 UNDECLARED_ASSET_ACCESSED (Abort)** — Asset accessed but absent from S0 `sealed_inputs_v1`.
  *Context:* `id|path`.

* **2B-S4-023 NETWORK_IO_ATTEMPT (Abort)** — Network I/O detected.
  *Context:* `endpoint`.

* **2B-S4-070 PARTITION_SELECTION_INCORRECT (Abort)** — Not exactly `seed={seed}/fingerprint={fingerprint}` for one or more inputs/outputs.
  *Context:* `id`, `expected`, `actual`.

### 10.2 Join integrity & coverage

* **2B-S4-040 JOIN_KEY_MISMATCH (Abort)** — Missing join partner on `(merchant_id, legal_country_iso, site_order)` between S1 and `site_timezones`.
  *Context:* `missing_keys_sample[]`.

* **2B-S4-041 TZ_GROUP_MULTIMAP (Abort)** — More than one `tzid` for a single site key.
  *Context:* `site_key`, `tzids[]`.

* **2B-S4-050 COVERAGE_MISMATCH (Abort)** — Missing/extra rows vs required `{merchants × tz_groups × days}` grid.
  *Context:* `missing_rows_sample[]`, `extra_rows_sample[]`.

* **2B-S4-083 WRITER_ORDER_NOT_PK (Abort)** — Row emission order differs from PK order.
  *Context:* `first_offending_row_index`.

* **2B-S4-041A PK_DUPLICATE (Abort)** — Duplicate `(merchant_id, utc_day, tz_group_id)` in output.
  *Context:* `key`.

### 10.3 Base shares, gamma echo & normalisation

* **2B-S4-052 BASE_SHARE_INCOHERENT (Abort)** — For a merchant, `|Σ base_share − 1| > ε`, or recomputation from S1 join does not match stored `base_share` within ε.
  *Context:* `merchant_id`, `sum_base_share`, `epsilon`.

* **2B-S4-053 GAMMA_ECHO_MISMATCH (Abort)** — Echoed `gamma` ≠ value in `s3_day_effects@{seed,fingerprint}`.
  *Context:* `merchant_id`, `utc_day`, `tz_group_id`, `expected`, `observed`.

* **2B-S4-051 NORMALISATION_FAILED (Abort)** — For a `{merchant, utc_day}`, `|Σ p_group − 1| > ε`, or `denom_raw ≤ 0` (if present).
  *Context:* `merchant_id`, `utc_day`, `sum_p_group`, `epsilon`, `denom_raw?`.

* **2B-S4-057 DOMAIN_VIOLATION (Abort)** — Any of: `base_share < 0`, `gamma ≤ 0`, or `p_group ∉ [0,1]`.
  *Context:* `merchant_id`, `utc_day`, `tz_group_id`, `field`, `value`.

* **2B-S4-090 DAY_GRID_MISMATCH (Abort)** — `utc_day` set in output ≠ inclusive grid implied by `s3_day_effects`.
  *Context:* `expected_count`, `observed_count`, `first_missing?`, `first_extra?`.

### 10.4 Output shape, identity & immutability

* **2B-S4-030 OUTPUT_SCHEMA_INVALID (Abort)** — `s4_group_weights` fails schema anchor.
  *Context:* `schema_errors[]`.

* **2B-S4-071 PATH_EMBED_MISMATCH (Abort)** — Embedded identity differs from path tokens.
  *Context:* `embedded`, `path_token`.

* **2B-S4-080 IMMUTABLE_OVERWRITE (Abort)** — Target partition not empty and bytes differ.
  *Context:* `target_path`.

* **2B-S4-081 NON_IDEMPOTENT_REEMIT (Abort)** — Re-emit produced byte-different output for identical inputs.
  *Context:* `digest_prev`, `digest_now`.

* **2B-S4-082 ATOMIC_PUBLISH_FAILED (Abort)** — Staging/rename not atomic or post-publish verification failed.
  *Context:* `staging_path`, `final_path`.

* **2B-S4-086 CREATED_UTC_MISMATCH (Abort)** — `created_utc` ≠ S0 `verified_at_utc` for this fingerprint.
  *Context:* `created_utc`, `verified_at_utc`.

### 10.5 Optional audit fields (if present)

* **2B-S4-095 AUDIT_INCOHERENT (Abort)** — If `mass_raw`/`denom_raw` exist: `denom_raw ≠ Σ mass_raw` within ε or `p_group ≠ mass_raw/denom_raw` within ε, or `denom_raw ≤ 0`.
  *Context:* `merchant_id`, `utc_day`, `sum_mass_raw`, `denom_raw`, `epsilon`.

### 10.6 Standard message fields (Binding)

All failures MUST include:
`code`, `severity`, `message`, `fingerprint`, `seed`, `validator` (or `"runtime"`), and `context{…}` as specified above.

### 10.7 Validator → code map (Binding)

| Validator                                    | Canonical codes (may emit multiple) |
|----------------------------------------------|-------------------------------------|
| **V-01 Prior gate evidence present**         | 2B-S4-001                           |
| **V-02 Dictionary-only resolution**          | 2B-S4-020, 2B-S4-021                |
| **V-03 Partition/selection exact**           | 2B-S4-070                           |
| **V-04 Join integrity**                      | 2B-S4-040, 2B-S4-041                |
| **V-05 Base-share aggregation Σ=1**          | 2B-S4-052                           |
| **V-06 Coverage: merchants × groups × days** | 2B-S4-050                           |
| **V-07 PK uniqueness**                       | 2B-S4-041A                          |
| **V-08 Writer order = PK**                   | 2B-S4-083                           |
| **V-09 Gamma echo coherent**                 | 2B-S4-053                           |
| **V-10 Domain checks**                       | 2B-S4-057                           |
| **V-11 Normalisation across groups**         | 2B-S4-051                           |
| **V-12 Day-grid equality**                   | 2B-S4-090                           |
| **V-13 Output shape valid**                  | 2B-S4-030                           |
| **V-14 Created time canonical**              | 2B-S4-086                           |
| **V-15 Path↔embed equality**                 | 2B-S4-071                           |
| **V-16 Write-once immutability**             | 2B-S4-080                           |
| **V-17 Idempotent re-emit**                  | 2B-S4-081                           |
| **V-18 No network & no extra reads**         | 2B-S4-023, 2B-S4-022, 2B-S4-021     |
| **V-19 Optional audit coherence**            | 2B-S4-095                           |
| **V-20 Base-share recomputation check**      | 2B-S4-052                           |

---

## 11. **Observability & run-report (Binding)**

### 11.1 Purpose

Emit one **structured JSON run-report** that proves what S4 read, how it formed tz-groups and combined γ, what it published, and the normalisation quality per merchant/day. The run-report is **diagnostic (non-authoritative)**; **`s4_group_weights`** remains the source of truth.

### 11.2 Emission

* S4 **MUST** write the run-report to **STDOUT** as a single JSON document on successful publish (and on abort, if possible).
* S4 **MAY** persist the same JSON to an implementation-defined log. Persisted copies **MUST NOT** be referenced by downstream contracts.

### 11.3 Top-level shape (fields-strict)

The run-report **MUST** contain:

* `component`: `"2B.S4"`
* `fingerprint`: `<hex64>`
* `seed`: `<string>`
* `created_utc`: ISO-8601 UTC (echo of S0 `verified_at_utc`)
* `catalogue_resolution`: `{ dictionary_version: <semver>, registry_version: <semver> }`
* `inputs_summary`:

  * `weights_path`: `<string>` *(Dictionary-resolved `s1_site_weights@seed,fingerprint`)*
  * `timezones_path`: `<string>` *(Dictionary-resolved `site_timezones@seed,fingerprint`)*
  * `day_effects_path`: `<string>` *(Dictionary-resolved `s3_day_effects@seed,fingerprint`)*
  * `merchants_total`: `<int>`
  * `tz_groups_total`: `<int>` *(distinct `merchant_id × tz_group_id` pairs)*
  * `days_total`: `<int>` *(distinct `utc_day` from S3)*
* `aggregation`:

  * `base_share_sigma_max_abs_error`: `<float>` *(max over merchants of |Σ base_share − 1|)*
  * `epsilon`: `<float>` *(programme tolerance)*
* `normalisation`:

  * `max_abs_mass_error_per_day`: `<float>` *(max over merchants×days of |Σ p_group − 1|)*
  * `merchants_days_over_epsilon`: `<int>` *(should be 0)*
* `publish`:

  * `target_path`: `<string>` *(Dictionary-resolved path to `s4_group_weights`)*
  * `bytes_written`: `<int>`
  * `write_once_verified`: `<bool>`
  * `atomic_publish`: `<bool>`
* `validators`: `[ { id: "V-01", status: "PASS|FAIL|WARN", codes: [ "2B-S4-0XX", … ] } … ]`
* `summary`: `{ overall_status: "PASS|FAIL", warn_count: <int>, fail_count: <int> }`
* `environment`: `{ engine_commit?: <string>, python_version: <string>, platform: <string>, network_io_detected: <int> }`

*(Fields-strict: no extra keys beyond those listed.)*

### 11.4 Evidence & samples (bounded, deterministic)

Provide **bounded** samples sufficient for offline verification; all selections are **deterministic**:

* `samples.rows` — up to **20** output rows
  `{ merchant_id, utc_day, tz_group_id, base_share, gamma, p_group }`
  *(pick by PK order; first N)*

* `samples.normalisation` — up to **20** merchant×day aggregates
  `{ merchant_id, utc_day, sum_p_group, abs_error }`
  *(pick largest `abs_error` first; stable tiebreak by `merchant_id`, then `utc_day`)*

* `samples.base_share` — up to **20** merchants
  `{ merchant_id, sum_base_share, abs_error }`
  *(pick largest `abs_error` first; then `merchant_id`)*

* `samples.coverage` — up to **10** days
  `{ utc_day, expected_groups: <int>, observed_groups: <int> }`
  *(earliest days first)*

* `samples.gamma_echo` — up to **20** rows with mismatch diagnostics **only if** V-09 fails (otherwise omit)
  `{ merchant_id, utc_day, tz_group_id, expected_gamma, observed_gamma }`
  *(PK order; first N mismatches)*

### 11.5 Counters (minimum set)

S4 **MUST** emit at least:

* `merchants_total`, `tz_groups_total`, `days_total`
* `rows_expected` *(= groups_total × days_total)*, `rows_written`
* `pk_duplicates` *(should be 0)*, `join_misses` *(should be 0)*, `multimap_keys` *(should be 0)*
* `merchants_over_base_share_epsilon` *(should be 0)*
* `merchants_days_over_norm_epsilon` *(should be 0)*
* `publish_bytes_total`
* Durations (ms): `resolve_ms`, `join_groups_ms`, `aggregate_ms`, `combine_ms`, `normalise_ms`, `write_ms`, `publish_ms`

### 11.6 Histograms / distributions (optional, bounded)

If emitted, histograms **MUST** be bounded and deterministically binned:

* `hist.abs_mass_error_per_day` — fixed bins over `[0, ε]` with counts.
* `hist.base_share` — fixed bins over `[0,1]` with counts.
* `hist.p_group` — fixed bins over `[0,1]` with counts.

### 11.7 Determinism of lists

Arrays **MUST** be emitted in deterministic order:

* `validators` sorted by validator ID (`"V-01"` …).
* `samples.rows` in PK order; other sample sets per their stated ordering.
* Any lists of IDs/digests lexicographic by ID with 1:1 alignment to digest lists.

### 11.8 PASS/WARN/FAIL semantics

* `overall_status = "PASS"` iff **all Abort-class validators** succeeded.
* WARN-class validator failures increment `warn_count` and **MUST** appear in `validators[]` with `status: "WARN"`.
* On any Abort-class failure, `overall_status = "FAIL"`; publish **MUST NOT** occur, but an attempted run-report **SHOULD** still be emitted with partial data when safe.

### 11.9 Privacy & retention

* The run-report **MUST NOT** include raw dataset bytes; only keys, paths, counts, digests, and derived metrics.
* Retention is governed by the Registry’s diagnostic-log policy; the run-report is **not** an authoritative artefact and **MUST NOT** be hashed into any bundle.

### 11.10 ID-to-artifact echo

For traceability, S4 **MUST** echo an `id_map` array of the exact Dictionary-resolved paths used:

```
id_map: [
  { id: "s1_site_weights",  path: "<…/s1_site_weights/seed=…/fingerprint=…/>" },
  { id: "site_timezones",   path: "<…/site_timezones/seed=…/fingerprint=…/>" },
  { id: "s3_day_effects",   path: "<…/s3_day_effects/seed=…/fingerprint=…/>" },
  { id: "s4_group_weights", path: "<…/s4_group_weights/seed=…/fingerprint=…/>" }
]
```

Paths **MUST** match those actually resolved/written at runtime.

---

## 12. **Performance & scalability (Informative)**

### 12.1 Workload model & symbols

* **M** = merchants
* **Gᵢ** = tz-groups (distinct `tzid`) for merchant *i*
* **D** = #UTC days present in `s3_day_effects` (inclusive grid)
* **S** = total sites in `s1_site_weights` (used only for the base-share aggregation)
* **R** = output rows = `D × Σᵢ Gᵢ`

S4 is one pass to (a) join & aggregate base shares, then (b) combine with γ and renormalise per merchant/day to emit **R** rows.

---

### 12.2 Time characteristics

* **Join & base-share aggregation:** `O(S)` on PK-ordered inputs (stable group-by)
* **Day-grid materialisation:** `O(D)`
* **Combine & renormalise:** `O(R)` (constant work per row + one per-merchant/day reduction)
* **Serialisation:** `O(R)` to write `s4_group_weights`

Overall: `O(S + R)` (or `O(S log S + R)` if a deterministic external sort is needed before the join).

---

### 12.3 Memory footprint

* Working set **`O(max Gᵢ)`** per merchant (tzid set + small accumulators).
* No full-table buffering: rows are emitted in PK order; per-merchant/day state is small (a few doubles per group).
* If inputs are ungrouped, use an external sort with bounded runs; memory stays fixed.

---

### 12.4 I/O discipline

* **Reads:** one scan of `s1_site_weights@{seed,fingerprint}` (project **PK + p_weight** only); one scan of `site_timezones@{seed,fingerprint}` (project **PK + tzid**); one scan of `s3_day_effects@{seed,fingerprint}` (project **PK + gamma**).
* **Writes:** one partition `…/s4_group_weights/seed={seed}/fingerprint={manifest_fingerprint}/` (write-once).
* **Atomic publish:** stage on the same filesystem → `fsync` → atomic rename.

---

### 12.5 Parallelism (safe patterns)

* **Across merchants and/or days:** shard the Cartesian grid into **disjoint, deterministic slices** (e.g., merchant ranges or day blocks). Each shard produces rows in local PK order; a **deterministic merge** concatenates shard outputs into global PK order before the single atomic publish.
* **Within a merchant/day:** keep reductions **serial** to preserve numeric determinism.
* **Forbidden:** parallelism that reorders PKs, changes reduction order, or introduces non-deterministic hash-iteration effects.

---

### 12.6 Numeric determinism guardrails

* IEEE-754 **binary64**, round-to-nearest-even; no FMA/FTZ/DAZ.
* Stable, serial reductions for `Σ p_weight`, `Σ mass_raw`, and `Σ p_group`.
* Single renormalisation pass; if tiny negatives (|x|≤ε) arise, clamp-and-renormalise **once** (as specified) to keep mass within ε.

---

### 12.7 Throughput tips (non-binding)

* **Project early:** read only required columns from each input.
* **Group cache:** precompute and sort each merchant’s tzid list once; stream days over that list.
* **Map joins:** build a compact `(merchant_id, legal_country_iso, site_order) → tzid` map for the run; reuse it while scanning S1.
* **Write batching:** emit in PK order with moderate Parquet row-groups (avoid tiny groups that hurt scans).
* **Counters first:** compute per-merchant/day denominators once; reuse for all groups that day.

---

### 12.8 Scale limits & mitigations

* **Large S (many sites):** cost dominated by the initial aggregation; ensure the join is on projected columns and uses a deterministic external sort when inputs aren’t PK-ordered.
* **Large D (long horizons):** linear growth in **R**; prefer day sharding and deterministic merges.
* **Skewed merchants (large Gᵢ):** memory remains `O(Gᵢ)`; if extreme, stream groups in chunks but preserve PK order and a single final normalisation per merchant/day.

---

### 12.9 Observability KPIs (suggested)

* Counts: `merchants_total`, `tz_groups_total`, `days_total`, `rows_expected`, `rows_written`.
* Quality: `base_share_sigma_max_abs_error`, `max_abs_mass_error_per_day`, `merchants_over_base_share_epsilon`, `merchants_days_over_norm_epsilon`.
* Runtime: `resolve_ms`, `join_groups_ms`, `aggregate_ms`, `combine_ms`, `normalise_ms`, `write_ms`, `publish_ms`.
* Hygiene: `pk_duplicates`, `join_misses`, `multimap_keys`.

---

### 12.10 Non-goals

* No network I/O or literal-path access.
* No record-level appends/updates post-publish; any change requires a new `{seed,fingerprint}` (or new fingerprint per change control).

---

## 13. **Change control & compatibility (Binding)**

### 13.1 Scope

This section governs permitted changes to **2B.S4** and how they are versioned/rolled out. It covers: the **procedure**, the **output dataset** `s4_group_weights`, the **normalisation law**, required **columns/PK/partitions**, and **validators/error codes**.

---

### 13.2 Stable, non-negotiable surfaces (unchanged without a **major** bump)

Within the same **major** version, S4 **MUST NOT** change:

* **Output identity & partitions:** dataset ID `s4_group_weights`; partitions `[seed, fingerprint]`; **path↔embed equality**; write-once + atomic publish.
* **PK & keys:** primary key `[merchant_id, utc_day, tz_group_id]`; one row per `{merchant, tz_group (tzid), day}`.
* **Group identity:** `tz_group_id` is the **IANA `tzid`** joined from `site_timezones`; no alternative grouping.
* **Day grid source:** set of `utc_day` values comes **only** from `s3_day_effects` (inclusive grid); S4 does not synthesize days.
* **Deterministic posture:** **RNG-free**; Dictionary-only resolution; **no** network I/O.
* **Normalisation law (across groups):** `p_group = (base_share × gamma) / Σ_groups(base_share × gamma)` with `Σ_group p_group = 1` (within ε) and `Σ_group base_share = 1` (within ε).
* **Numeric discipline:** IEEE-754 binary64; round-to-nearest-even; serial, order-stable reductions; single clamp-and-renormalise pass for tiny negatives as specified.
* **Required columns & meanings:** `p_group`, `base_share`, `gamma`, `created_utc` (semantics as defined in this spec).
* **Acceptance posture:** the set and meaning of **Abort-class** validators (by ID).

Any change here is **breaking** → bump **major** (with new anchors/IDs as needed).

---

### 13.3 Backward-compatible changes (allowed with **minor** or **patch** bump)

* **Editorial clarifications** and examples that do not change behaviour. *(patch)*
* **Run-report** additions (new counters/samples/histograms); run-report is non-authoritative. *(minor/patch)*
* **Optional metadata/audit columns** in `s4_group_weights` (e.g., `mass_raw`, `denom_raw`) that validators treat as optional. *(minor)*
* **WARN-class validators**: add new WARN checks or improve messages without altering PASS/FAIL criteria. *(minor)*

---

### 13.4 Breaking changes (require **major** bump + migration)

* Renaming the output ID, changing **partitions**, or altering **path families**.
* Changing the **PK**, the definition of `tz_group_id`, or the one-row-per `{merchant, tz_group, day}` law.
* Altering the **normalisation law** (e.g., different denominator, different mass combination), or removing the Σ=1 constraints.
* Switching numeric discipline (rounding mode, tolerance policy) such that bytes can differ for identical inputs.
* Removing/renaming required **columns** or changing their semantics.
* Reclassifying a **WARN** validator to **Abort**, or adding a **new Abort** validator that can fail for previously valid outputs.
* Allowing **literal paths** or **network I/O**, or removing Dictionary-only resolution / subset-of-S0 rule.
* Allowing S4 to materialise days independent of `s3_day_effects`.

---

### 13.5 SemVer & release discipline

* **Major:** any change in §13.4 → bump spec + schema anchor (e.g., `#/plan/s4_group_weights_v2`), update Dictionary/Registry IDs/paths if necessary, ship migration notes.
* **Minor:** additive, backward-compatible behaviour (optional metadata, WARN validators, run-report fields).
* **Patch:** editorial only (no shape/procedure/validators change).

When **Status = frozen**, post-freeze edits are **patch-only** unless a ratified minor/major is issued.

---

### 13.6 Relationship to upstream inputs

S4 has **no policy bytes of its own**. Its outputs change when the **sealed inputs** change (`s1_site_weights`, `site_timezones`, `s3_day_effects`). Updating those inputs **does not** change this spec version; it produces different results under a different `{seed, fingerprint}` captured by S0.

---

### 13.7 Compatibility guarantees to downstream states (S5/S6)

Downstreams **MAY** rely on: presence/shape of `s4_group_weights`, PK/partitions, the normalisation law (Σ=1 per merchant/day), and `gamma` being the S3 echo. Downstreams **MUST NOT** rely on run-report structure, nor assume undocumented columns.

---

### 13.8 Deprecation & migration protocol

Changes are proposed → reviewed → ratified with a **change log** (impact, validator deltas, new anchors, migration steps). For majors, use a **dual-publish window** when feasible (v1 and v2 in parallel; v2 authoritative, v1 legacy) or supply a consumer shim during migration.

---

### 13.9 Rollback policy

Outputs are **write-once**; rollback means publishing a **new** `{seed,fingerprint}` (or reverting to a prior fingerprint) that reproduces the last known good behaviour. No in-place mutation.

---

### 13.10 Evidence of compatibility

Each release MUST include: schema diffs, validator table diffs, and a conformance run proving previously valid S4 inputs still **PASS** (for minor/patch). CI MUST cover: join integrity, base-share Σ=1, gamma echo, per-day normalisation, identity/immutability, idempotent re-emit.

---

### 13.11 Registry/Dictionary coordination

Dictionary changes that alter ID names, path families, or partition tokens for `s4_group_weights` are **breaking** unless accompanied by new anchors/IDs and a migration plan. Registry metadata edits (owner/licence/retention) are compatible; edits affecting **existence** of required artefacts are breaking.

---

### 13.12 Validator/code namespace stability

Validator IDs (`V-01`…`V-20`) and canonical codes (`2B-S4-…`) are **reserved**. New codes may be added; existing codes’ meanings **MUST NOT** change within a major.

---

## Appendix A — Normative cross-references *(Informative)*

> This appendix lists the authoritative artefacts S4 references. **Schemas** govern shape; the **Dataset Dictionary** governs ID → path/partitions/format; the **Artefact Registry** governs ownership/licence/retention. Binding rules live in §§1–13.

### A.1 Authority chain (this segment)

* **Schema pack (shape authority):** `schemas.2B.yaml`

  * **Output anchor used by S4:**

    * `#/plan/s4_group_weights` — per-merchant × per-UTC-day × per-`tz_group_id` day mix (fields-strict)
  * **Input anchors referenced by S4:**

    * `#/plan/s1_site_weights` — frozen per-site weights (S1)
    * `schemas.2A.yaml#/egress/site_timezones` — site → `tzid` (2A)
    * `#/plan/s3_day_effects` — γ(d, tz_group) factors (S3)
  * **Common defs:** `#/$defs/hex64`, `#/$defs/partition_kv` *(token-less OK)*; timestamps reuse `schemas.layer1.yaml#/$defs/rfc3339_micros`.

* **Dataset Dictionary (catalogue authority):** `dataset_dictionary.layer1.2B.yaml`

  * **S4 output & path family:**

    * `s4_group_weights` → `data/layer1/2B/s4_group_weights/seed={seed}/fingerprint={manifest_fingerprint}/` (format: parquet; ordering: `[merchant_id, utc_day, tz_group_id]`)
  * **S4 inputs (Dictionary IDs):**

    * `s1_site_weights` → `data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/` (parquet)
    * `site_timezones` → `data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/` (parquet)
    * `s3_day_effects` → `data/layer1/2B/s3_day_effects/seed={seed}/fingerprint={manifest_fingerprint}/` (parquet)

* **Artefact Registry (metadata authority):** `artefact_registry_2B.yaml`

  * Ownership/retention for `s4_group_weights`; cross-layer pointers for `site_timezones`; input dependencies on `s1_site_weights` and `s3_day_effects`.

### A.2 Prior state evidence (2B.S0)

* **`s0_gate_receipt_2B`** — gate verification, identity, catalogue versions (fingerprint-scoped).
* **`sealed_inputs_v1`** — authoritative list of sealed assets (IDs, tags, digests, paths, partitions).
  *(S4 does not re-hash 1B; it relies on this evidence.)*

### A.3 Inputs consumed by S4 (read-only)

* **Weights table (from S1):**

  * `s1_site_weights` → `data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/`
  * **Shape:** `schemas.2B.yaml#/plan/s1_site_weights`
* **Site time-zones (from 2A):**

  * `site_timezones` → `data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/`
  * **Shape:** `schemas.2A.yaml#/egress/site_timezones`
* **Day effects (from S3):**

  * `s3_day_effects` → `data/layer1/2B/s3_day_effects/seed={seed}/fingerprint={manifest_fingerprint}/`
  * **Shape:** `schemas.2B.yaml#/plan/s3_day_effects`

### A.4 Output produced by this state

* **`s4_group_weights`** (Parquet; `[seed, fingerprint]`)
  **Shape:** `schemas.2B.yaml#/plan/s4_group_weights`
  **Dictionary path:** `data/layer1/2B/s4_group_weights/seed={seed}/fingerprint={manifest_fingerprint}/`
  **PK:** `[merchant_id, utc_day, tz_group_id]`
  **Required fields:** `p_group`, `base_share`, `gamma`, `created_utc` *(plus optional audit fields if exposed by the anchor)*
  **Writer order:** `[merchant_id, utc_day, tz_group_id]`

### A.5 Identity & token discipline

* **Tokens:** `seed={seed}`, `fingerprint={manifest_fingerprint}`
* **Partition law:** S4 output partitions by **both** tokens; inputs selected exactly as declared.
* **Day grid:** The set of `utc_day` values **must equal** the inclusive grid present in `s3_day_effects`.
* **Path↔embed equality:** any embedded identity in `s4_group_weights` must equal the path tokens.

### A.6 Segment context

* **Segment overview:** `state-flow-overview.2B.txt` *(context only; this S4 spec governs).*
* **Layer identity & gate laws:** programme-wide rules (No PASS → No read; hashing law; write-once + atomic publish; determinism discipline).

---
