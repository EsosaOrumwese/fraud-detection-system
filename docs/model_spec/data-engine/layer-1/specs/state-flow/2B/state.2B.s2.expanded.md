# State 2B.S2 — Alias tables (O(1) sampler build)

## 1. **Document metadata & status (Binding)**

**Component:** Layer-1 · Segment **2B** — **State-2 (S2)** · *Alias tables (O(1) sampler build)*
**Document ID:** `seg_2B.s2.alias`
**Version (semver):** `v1.0.0-alpha`
**Status:** `alpha` *(normative; semantics lock at `frozen` in a ratified release)*
**Owners:** Design Authority (DA): **Esosa Orumwese** · Review Authority (RA): **Layer 1 Governance**
**Effective date:** **2025-11-02 (UTC)**

**Authority chain (Binding):**
**JSON-Schema pack** = shape authority → `schemas.2B.yaml`
**Dataset Dictionary** = ID→path/partitions/format → `dataset_dictionary.layer1.2B.yaml`
**Artefact Registry** = existence/licence/retention → `artefact_registry_2B.yaml`

**Normative cross-references (Binding):**

* Prior state evidence: **`s0_gate_receipt_2B`**, **`sealed_inputs_v1`**.
* Upstream in-segment input: **`s1_site_weights`** (2B · S1).
* Policy: **`alias_layout_policy_v1`** (layout/endianness/alignment, bit-depth, decode/encode law).
* Segment overview: `state-flow-overview.2B.txt` (context only; this spec governs).

**Segment invariants (Binding):**

* **Run identity:** `{ seed, manifest_fingerprint }`.
* **S2 outputs partitioning:** `[seed, fingerprint]`; **path↔embed equality** MUST hold.
* **Catalogue discipline:** Dictionary-only resolution; literal paths forbidden.
* **RNG posture:** **S2 is RNG-free**; downstream RNG-bounded states (e.g., S3/S5) use governed Philox per policy.
* **Gate law:** Downstreams rely on S0; **No PASS → No read** remains in force across the segment.

---

## 2 Purpose & scope (Binding)

**Purpose.** Construct **deterministic O(1) sampling artefacts** (alias structures) per merchant from `s1_site_weights`, so downstream routing can pick a site in **constant time** without recomputing probabilities. S2 serialises these tables into a **binary blob** with a matching **index**, both byte-stable and reproducible.

**S2 SHALL:**

* **Rely on S1 weights** only: take `s1_site_weights@{seed,fingerprint}` and the policy **`alias_layout_policy_v1`** as the governing sources of truth.
* **Reconstruct integer grid masses** deterministically from S1: `m_i = round_even(p_weight·2^b)` + policy’s deterministic Δ-adjust to ensure `Σ m_i = 2^b` (where `b = quantised_bits`).
* **Build per-merchant alias tables** from `{m_i}` using the policy-declared **encode/decode law** (e.g., Walker/Vose style) — **RNG-free**.
* **Serialise** all alias tables into a single **`s2_alias_blob`** using the exact **layout/endianness/alignment** declared by policy; emit a companion **`s2_alias_index`** with per-merchant `{offset, length, sites, quantised_bits, checksum}` and global `{blob_sha256, layout_version, created_utc}`.
* **Preserve identity & provenance:** partition outputs by **`[seed, fingerprint]`**, set `created_utc = S0.verified_at_utc`, and record policy identifiers/digests needed for replay.
* **Guarantee idempotence:** same sealed inputs ⇒ **bit-identical** blob and index; write-once, atomic publish.

**Scope (operations included).**

* Dictionary-only resolution of inputs; grouping by merchant; deterministic grid reconstruction; alias encode; binary serialisation; index generation; blob digesting; publish.

**Out of scope.**

* Day-effect draws (S3), zone-group re-normalisation (S4), per-arrival routing (S5/S6), audits/CI (S7), PASS bundle (S8).
* Any stochastic sampling; any reweighting beyond the policy-defined integer-grid reconstruction; network I/O; literal-path resolution.

---

## 3. **Preconditions & sealed inputs (Binding)**

### 3.1 Preconditions (Abort on failure)

* **Prior gate evidence.** A valid **`s0_gate_receipt_2B`** for the target **`manifest_fingerprint`** MUST exist.
* **Run identity fixed.** The pair **`{ seed, manifest_fingerprint }`** is fixed at S2 start and MUST remain constant.
* **RNG posture.** S2 performs **no random draws** (RNG-free).
* **Dictionary-only.** All inputs **MUST** resolve by **Dataset Dictionary IDs**; literal paths are forbidden.
* **No re-hash of 1B.** S2 MUST NOT recompute the 1B bundle hash; S0’s receipt is the sole gate attestation.

### 3.2 Required sealed inputs (must all be present)

S2 SHALL read **only** the following assets for this run’s identity:

1. **`s1_site_weights`** — 2B · S1 output at
   `seed={seed} / fingerprint={manifest_fingerprint}`.
2. **`alias_layout_policy_v1`** — policy pack declaring **layout/endianness/alignment**, **bit-depth** (`quantised_bits`), **encode/decode law**, and **checksumming/digest** rules for alias artefacts.
   *This policy is a single file with **no partition tokens**; the selection is the exact path/digest sealed by S0 for this fingerprint.*

> All required assets MUST be resolvable via the Dictionary and MUST appear in S0’s `sealed_inputs_v1` for the same fingerprint.

### 3.3 Policy minima (Abort if unmet)

`alias_layout_policy_v1` **MUST** declare, at minimum:

* **`layout_version`** (string) — semantic version of the binary layout.
* **`endianness`** (enum) and **`alignment_bytes`** (int ≥ 1) for the blob.
* **`quantised_bits`** (int >= 1) - bit-depth **b** used to reconstruct the integer grid (G = 2^b).
* **`quantisation_epsilon`** (float > 0) — ε_q used by validators for decode error bounds.
* **`decode_law`** (identifier) — the deterministic alias decode semantics S5/S6 will use (e.g., Walker/Vose variant).
* **`encode_spec`** — fields sufficient to build alias arrays deterministically from integer masses `{m_i}`.
* **`checksum`** — row- or merchant-level checksum spec (algorithm, scope) for index rows, and **`blob_sha256`** rule for the full blob.
* **`required_index_fields`** — the index keys S2 MUST emit per merchant (e.g., `{merchant_id, offset, length, sites, quantised_bits, checksum}`).

Absence of any listed policy entry is an **Abort**.

### 3.4 Resolution & partition discipline

* **Exact partitions.**
  • `s1_site_weights`: **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
  • `alias_layout_policy_v1`: **no partition tokens** — select the **exact S0-sealed path** and validate its digest.
* **Subset of S0.** Every asset S2 reads **MUST** be present in S0’s `sealed_inputs_v1` for this fingerprint. Accessing any asset not listed there is an error.
* **No optional pins.** S2 SHALL NOT read 2A pins (`site_timezones`, `tz_timetable_cache`); they are not required for alias construction.

### 3.5 Integrity & provenance inputs

* **Created time.** Discover canonical `created_utc` from S0’s receipt (`verified_at_utc`) and use it for all S2 outputs.
* **Quantisation coherence input.** `s1_site_weights` MUST contain `quantised_bits` per row; S2 SHALL verify the policy’s `quantised_bits` equals this value (acceptance enforces).
* **Key coverage input.** The set of merchants and `(merchant_id, legal_country_iso, site_order)` keys in `s1_site_weights` is the authoritative universe for S2 (acceptance enforces 1:1 coverage in the index).

### 3.6 Prohibitions

* **No network I/O.** All bytes are local/managed.
* **No extra inputs.** S2 MUST NOT read any dataset/policy other than §3.2.
* **No implicit transforms.** All computations MUST be derivable from `s1_site_weights` and the policy; S2 SHALL NOT invent new features or reweight beyond the integer-grid reconstruction declared by policy.

---

## 4. **Inputs & authority boundaries (Binding)**

### 4.1 Catalogue authorities

* **Schema pack** (`schemas.2B.yaml`) is the **shape authority** for S2 outputs and referenced inputs.
* **Dataset Dictionary** (`dataset_dictionary.layer1.2B.yaml`) is the **sole authority** for resolving **IDs → path templates, partitions, format** (token expansion is binding).
* **Artefact Registry** (`artefact_registry_2B.yaml`) governs **existence/licence/retention/ownership**; it does **not** override Dictionary paths.

### 4.2 Inputs S2 MAY read (and nothing else)

Resolve **only** the following via the Dictionary (no literal paths):

1. **`s1_site_weights`** — 2B · S1 output at `seed={seed} / fingerprint={manifest_fingerprint}`.
2. **`alias_layout_policy_v1`** — policy pack (**no partition tokens**); select the **exact S0-sealed path/digest** for this fingerprint.

> S2 SHALL NOT read 2A pins (`site_timezones`, `tz_timetable_cache`) or any other artefacts.

### 4.3 S0-evidence rule

Cross-layer/policy assets **MUST** appear in S0's `sealed_inputs_v1` for this fingerprint (token-less policies are selected by exact S0‑sealed `path+sha256_hex`, `partition={}`).
Within-segment datasets (e.g., `s1_site_weights`, S2 outputs) are **NOT** S0‑sealed and **MUST** be resolved by **Dataset Dictionary ID** at exactly **`[seed, fingerprint]`**. Literal paths and network I/O are forbidden.

### 4.4 Prohibited resources & behaviours

* **No literal paths** (env overrides, ad-hoc strings/globs).
* **No network I/O** (HTTP/remote FS/cloud buckets).
* **No re-hashing of 1B**; S0’s receipt is the sole gate attestation.
* **No extra inputs** beyond §4.2; **no** on-the-fly feature invention outside policy.

### 4.5 Resolution & token discipline

* **Exact partitions:**
  • `s1_site_weights` → **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
  • `alias_layout_policy_v1` → **no tokens**; select the **S0-sealed** path and verify its digest.
* **Path↔embed equality (outputs):** any embedded identity in S2 outputs **MUST** equal the path tokens the Dictionary produced.

### 4.6 Trust boundary & sequencing

1. Verify S0 evidence for the target fingerprint exists.
2. Resolve `alias_layout_policy_v1` and `s1_site_weights` via the Dictionary.
3. Perform alias construction strictly from these sealed inputs; do not consult any other sources.

### 4.7 Input field expectations (checked or assumed)

* `s1_site_weights` provides PK `[merchant_id, legal_country_iso, site_order]`, `p_weight ∈ [0,1]`, and a constant `quantised_bits` per run; S2 **relies** on these as already validated by S1.
* `alias_layout_policy_v1` provides `layout_version`, `endianness`, `alignment_bytes`, `quantised_bits`, `encode_spec`, `decode_law`, and checksum/digest rules; absence is handled per §3.3 (Abort).

---

## 5. **Outputs (datasets) & identity (Binding)**

### 5.1 Products (IDs)

* **`s2_alias_index`** — per-merchant **index** describing where each merchant’s alias table lives inside the blob and the invariants needed to decode it.
* **`s2_alias_blob`** — contiguous **binary blob** that stores all merchants’ alias tables in the policy-declared layout/endianness/alignment.

### 5.2 Identity & partitions

* **Run identity:** `{ seed, manifest_fingerprint }`.
* **Partitions (binding):** both products partition by **`[seed, fingerprint]`** only.
* **Path↔embed equality:** any embedded `manifest_fingerprint` (and, if echoed, `seed`) in either product **MUST** byte-equal the corresponding path tokens.

### 5.3 Path families, format & catalogue authority

* The **Dataset Dictionary** is the sole authority for ID → path/partitions/format. S2 **SHALL** write to the Dictionary-bound locations:

  * `s2_alias_index` → **JSON** (fields-strict) under
    `…/s2_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/index.json`
  * `s2_alias_blob` → **binary** under
    `…/s2_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/alias.bin`
* Literal paths are forbidden.

### 5.4 Shape & schema anchors (shape authority)

* **`s2_alias_index`** → `schemas.2B.yaml#/plan/s2_alias_index` (**columns/fields strict**).
  **Must include:**

  * **Global header:** `{ blob_sha256, layout_version, endianness, alignment_bytes, quantised_bits, created_utc, policy_id, policy_digest }`
  * **Per-merchant rows (one per merchant, writer-sorted):**
    `{ merchant_id, offset, length, sites, quantised_bits, checksum }`
* **`s2_alias_blob`** → `schemas.2B.yaml#/binary/s2_alias_blob` (**binary contract**), whose **layout/endianness/alignment** are dictated solely by `alias_layout_policy_v1`.

### 5.5 Writer order & structural constraints (index + blob)

* **Index writer order:** strictly ascending `merchant_id`.
* **Offset discipline:** `offset` values **strictly increase**; each range `[offset, offset+length)` **MUST** be within the blob size and **MUST NOT** overlap.
* **Bit-depth coherence:** all rows carry `quantised_bits = policy.quantised_bits`.
* **Blob digest:** `blob_sha256` in the index **MUST** equal the SHA-256 of the **raw bytes** of `s2_alias_blob`.
* **Checksums:** per-merchant `checksum` is computed exactly as declared by policy (algorithm/scope).

### 5.6 Provenance & stamping

* **Creation time:** `created_utc` **MUST** equal the canonical S0 time (`verified_at_utc`) for this fingerprint.
* **Policy echo:** index **MUST** echo `{ policy_id="alias_layout_policy_v1", policy_digest=<hex64> }` taken from S0’s inventory row for that policy.
* **Layout echo:** `layout_version`, `endianness`, `alignment_bytes` are copied from the policy bytes used.

### 5.7 Write-once, immutability & idempotency

* **Single-writer, write-once:** target partitions **MUST** be empty before first publish.
* **Idempotent re-emit:** re-publishing to the same `(seed,fingerprint)` is allowed **only** if **both** index and blob bytes are **bit-identical**; otherwise **Abort**.
* **Atomic publish:** stage → fsync → atomic move for **both** artefacts; no partial files may become visible.

### 5.8 Downstream reliance

* **S5/S6** are required to:

  1. verify `blob_sha256` from the index against the blob,
  2. use the **decode law** identified by the policy and the **layout_version/endianness/alignment** echoed in the index, and
  3. treat `s2_alias_index` as the **sole directory** for merchant table locations (no scanning or guessing inside the blob).

---

## 6. **Dataset shapes & schema anchors (Binding)**

### 6.1 Shape authority

All shapes in this state are governed by the **2B schema pack** (`schemas.2B.yaml`). Shapes are **fields-strict** (no extras). The **Dataset Dictionary** binds IDs → path/partitions/format. The **Artefact Registry** carries ownership/licence/retention only.

---

### 6.2 Index — `schemas.2B.yaml#/plan/s2_alias_index`

**Type:** JSON object (fields-strict).
**Purpose:** Directory for the alias blob plus per-merchant slices.

**Required (global header)**

* `layout_version` — string (policy version of the binary layout).
* `endianness` — string enum: `"little"` | `"big"`.
* `alignment_bytes` — integer ≥ 1 (byte alignment for each merchant slice).
* `quantised_bits` — integer ≥ 1 (bit-depth **b** used to reconstruct grid `G = 2^b`).
* `created_utc` — RFC-3339/ISO-8601 timestamp (UTC) = S0 `verified_at_utc`.
* `policy_id` — string constant `"alias_layout_policy_v1"`.
* `policy_digest` — hex64 (digest of the policy bytes sealed by S0).
* `blob_sha256` — hex64 (SHA-256 of **raw bytes** of `s2_alias_blob`).
* `blob_size_bytes` — integer ≥ 0.
* `merchants_count` — integer ≥ 0.
* `merchants` — array of **row** objects (fields-strict), writer-sorted by `merchant_id`.

**Per-merchant row (all required)**

* `merchant_id` — id64 (layer/common def).
* `offset` — integer ≥ 0 (byte offset in blob; **multiple of `alignment_bytes`**).
* `length` — integer ≥ 1 (byte length of this merchant’s table).
* `sites` — integer ≥ 1 (Kᵢ).
* `quantised_bits` — integer ≥ 1 (must equal header `quantised_bits`).
* `checksum` — hex string per policy (default hex64; algorithm declared by policy).

**Notes (binding semantics)**

* Arrays/objects are **fields-strict**; unknown fields are forbidden.
* `offset + length ≤ blob_size_bytes`; merchant ranges **MUST NOT overlap**.
* Row order is strictly ascending `merchant_id`; header counts **must** match (`merchants_count = len(merchants)`).

---

### 6.3 Binary contract — `schemas.2B.yaml#/binary/s2_alias_blob`

**Type:** Binary contract (non-JSON).
**Purpose:** Concatenation of per-merchant alias tables in the **policy-declared** layout.

**Binding properties (declared in the anchor)**

* `layout_version` — string (must equal index/header).
* `endianness` — `"little"` | `"big"` (must equal index/header).
* `alignment_bytes` — integer ≥ 1 (each merchant slice starts at an offset that is a multiple of this).
* `record_layout` — **opaque to the spec**; defined by **`alias_layout_policy_v1.encode_spec`** (e.g., Walker/Vose arrays, compressed forms, padding rules).
* `padding_rule` — alignment padding bytes value (e.g., `0x00`) if required by policy.

**Notes (binding semantics)**

* Blob bytes are authoritative; `blob_sha256` in the index **MUST** equal the SHA-256 of these raw bytes.
* Merchant slices appear in the same order as index rows (ascending `merchant_id`).
* Decoding **must** follow the policy’s `decode_law` using `quantised_bits = b` (from header).

---

### 6.4 Referenced anchors (inputs/policy)

* **Weights table:** `schemas.2B.yaml#/plan/s1_site_weights` (PK, partitions, required provenance).
* **Policy:** `schemas.2B.yaml#/policy/alias_layout_policy_v1` (declares `layout_version`, `endianness`, `alignment_bytes`, `quantised_bits`, `encode_spec`, `decode_law`, and checksum rules).
* **Common defs (layer/segment):** `#/$defs/hex64`, `#/$defs/partition_kv`; timestamps reuse `schemas.layer1.yaml#/$defs/rfc3339_micros`.

---

### 6.5 Format & storage (Dictionary authority)

* **`s2_alias_index`** — **JSON** at the Dictionary path family `…/s2_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/index.json`; partitions `[seed, fingerprint]`; writer order = ascending `merchant_id`.
* **`s2_alias_blob`** — **binary** at `…/s2_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/alias.bin`; partitions `[seed, fingerprint]`.

---

### 6.6 Structural & cross-field constraints (checked by validators)

* **Alignment:** Every `offset % alignment_bytes == 0`.
* **Coverage:** `merchants_count` equals the number of distinct merchants in `s1_site_weights`; each row’s `sites` equals that merchant’s site count.
* **Bit-depth:** per-row `quantised_bits` equals header `quantised_bits` equals the policy’s `quantised_bits`.
* **Bounds:** For all rows, `0 ≤ offset < blob_size_bytes` and `offset + length ≤ blob_size_bytes`; ranges do not overlap.
* **Digest coherence:** `blob_sha256` equals the SHA-256 of the blob’s **raw bytes**.

---

## 7. **Deterministic algorithm (RNG-free) (Binding)**

**Overview.** S2 performs a fixed, reproducible transform from catalogued inputs (`s1_site_weights`, `alias_layout_policy_v1`) to a byte-stable **index** + **blob**. There are **no random draws** and **no network I/O**. Arithmetic follows the programme’s numeric discipline (binary64, round-to-nearest-even), with stable serial reductions and explicit tie-break rules.

### 7.1 Resolve & sanity

1. **Verify S0 evidence** exists for this `manifest_fingerprint`.
2. **Resolve inputs by Dictionary IDs only:**

   * `s1_site_weights@{seed,fingerprint}`
   * `alias_layout_policy_v1` (single file; **no partition tokens**; select the **exact S0-sealed path/digest**).
3. **Read policy minima** (must exist; else Abort): `layout_version`, `endianness`, `alignment_bytes`, `quantised_bits = b ≥ 1`, `encode_spec`, `decode_law`, checksum rules.
4. **Discover canonical time:** `created_utc ← S0.verified_at_utc`.
5. **Bit-depth coherence precheck:** assert that all rows in `s1_site_weights` carry the same `quantised_bits` value and that it equals policy `b`. (Full enforcement via acceptance.)

### 7.2 Grouping & key order

6. **Group by merchant** using the site key carried from `s1_site_weights` (`PK = merchant_id, legal_country_iso, site_order`).
7. **Within each merchant**, process sites in **deterministic PK order**; all reductions and tie-breaks use this order. Let the merchant have **K ≥ 1** sites.

### 7.3 Integer grid reconstruction (from S1 weights)

8. **Grid size:** `G = 2^b`. For each site row with `p = p_weight`:

   * Compute real mass `m* = p · G`.
   * Initial integer `m⁰ = round_half_to_even(m*)` (ties-to-even).
   * Track fractional remainder `r = m* − floor(m*)` for tie-breaks.
9. **Mass reconciliation:** let `Δ = G − Σ m⁰`.

   * If `Δ = 0`, set `m = m⁰`.
   * If `Δ > 0` (deficit): increment **+1** the **Δ** rows with **largest** `r`.
   * If `Δ < 0` (surplus): decrement **−1** the **|Δ|** rows with **smallest** `r`.
   * **Tie-break deterministically by PK order.**
     Result: integer masses `{m_i}` with `Σ m_i = G` and `0 ≤ m_i ≤ G`.
10. **Sanity:** if any `m_i` becomes negative or exceeds `G`, **Abort**.

> This reconstruction **must** yield the same integer grid S1 would produce under its quantisation law (used there for coherence checks); this is the sole input to alias encoding.

### 7.4 Alias encoding (policy-declared law; RNG-free)

11. **Threshold:** `M = G / K` (integer division is not used here; use binary64 arithmetic, then compare against *exact* integer masses).
12. **Queue initialisation (deterministic):**

* **small** ← indices with `m_i < M`, in **PK order**.
* **large** ← indices with `m_i ≥ M`, in **PK order**.
* (If `m_i = M`, treat as **large**; this is deterministic and avoids aliasing trivial 1/K entries.)

13. **Encode loop (Vose/Walker style; policy `encode_spec` fixes exact fields):**
    While `small` and `large` are non-empty:
    a) pop **s** from `small` (front), pop **l** from `large` (front).
    b) Emit an alias entry for **s** using **l** as its alias peer; compute the per-entry scalar per `encode_spec` from `m_s` and `M`.
    c) Update `m_l ← m_l − (M − m_s)`;

    * if `m_l < M`, push **l** to **small**’s back;
    * else if `m_l > M`, push **l** to **large**’s back;
    * else (`m_l = M`), place **l** into **large**’s back (deterministic convention).
      d) Continue until one queue empties.
14. **Finalize:** for any remaining indices in **large** or **small**, emit self-alias entries per `encode_spec` (they represent exact `1/K` cells).
15. **Determinism notes:**

* Queue order is **stable** (PK ascending on insertion).
* No floating probabilistic comparisons beyond integer masses and `M`.
* Any equality is resolved by the deterministic conventions above.

### 7.5 Blob serialisation (layout/endianness/alignment)

16. **Serialise per merchant** the alias data produced in §7.4 into a byte slice exactly as `alias_layout_policy_v1.encode_spec` declares (record/field order, integer widths, endianness).
17. **Alignment & padding:** start each merchant slice at an offset that is a **multiple of `alignment_bytes`**. If padding is required between slices, fill with the policy’s `padding_rule` (e.g., `0x00`).
18. **Per-merchant checksum:** compute the row checksum **over that merchant’s raw slice bytes** using the policy’s checksum algorithm; record it in the index row.
19. **Offset/length bookkeeping:** track `{offset, length}` for each merchant in ascending `merchant_id`.

### 7.6 Index construction & global digest

20. **Header fields:**

* `layout_version`, `endianness`, `alignment_bytes`, `quantised_bits = b`, `created_utc`, `policy_id="alias_layout_policy_v1"`, `policy_digest` (from S0 inventory).

21. **Blob digest:** compute `blob_sha256` as the SHA-256 of the **raw blob bytes**.
22. **Counts & bounds:** set `blob_size_bytes`, `merchants_count = len(merchants)`; assert each `[offset, offset+length)` is within `blob_size_bytes` and **non-overlapping**.

### 7.7 Write & immutability

23. **Targets (Dictionary-resolved):**

* `s2_alias_blob@seed={seed}/fingerprint={manifest_fingerprint}`
* `s2_alias_index@seed={seed}/fingerprint={manifest_fingerprint}`

24. **Write-once:** partitions MUST be empty; otherwise **Abort**, unless bytes are **bit-identical** (idempotent re-emit).
25. **Atomic publish:** write to staging in the same filesystem, `fsync`, then **atomic rename** both artefacts.

### 7.8 Post-publish assertions

26. **Path↔embed equality:** any embedded identity equals the path tokens.
27. **Digest coherence:** recompute `blob_sha256` and match the index header.
28. **Decode spot-check (deterministic):** using the policy’s `decode_law`, decode a bounded, deterministic sample of merchants (e.g., first N in `merchant_id`) from the blob and assert:

* per-merchant Σ `p̂` = 1 exactly;
* per-row `|p̂ − p_weight| ≤ ε_q` (policy’s `quantisation_epsilon`).
  Failure → **Abort** with alias-decode error.

### 7.9 Prohibitions & determinism guards

29. **No RNG; no network** I/O.
30. **No literal paths; no extra inputs** beyond §3.2.
31. **Stable arithmetic:** binary64; ties-to-even; serial reductions; no data-dependent re-ordering that changes numeric outcomes.
32. **Replay:** re-running S2 with identical sealed inputs (including identical policy bytes) **MUST** reproduce **bit-for-bit identical** index and blob.

---

## 8. **Identity, partitions, ordering & merge discipline (Binding)**

### 8.1 Identity law

* **Run identity:** `{ seed, manifest_fingerprint }` fixed at S2 start.
* **Output identity:** both `s2_alias_index` and `s2_alias_blob` are identified by **both** tokens.

### 8.2 Partitions & exact selection

* **Write partitions:**
  `…/s2_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/index.json`
  `…/s2_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/alias.bin`
* **Exact selection:** single `(seed,fingerprint)` partition per publish; no wildcards, ranges, or multi-partition writes.

### 8.3 Path↔embed equality

* Any embedded `manifest_fingerprint` (and, if echoed, `seed`) in either artefact **MUST** byte-equal the corresponding path tokens. Inequality is an error.

### 8.4 Writer order & structural order

* **Index writer order:** rows **MUST** be emitted in strictly ascending `merchant_id`.
* **Blob structural order:** merchant slices **MUST** appear in the same `merchant_id` order as the index; `offset` values strictly increase and respect `alignment_bytes`.

### 8.5 Single-writer, write-once

* Target partitions **MUST** be empty prior to first publish.
* If a target exists:

  * **Byte-identical:** treat as a no-op (idempotent re-emit).
  * **Byte-different:** **Abort** with immutable-overwrite error.

### 8.6 Atomic publish (two-artefact transaction)

* Write each artefact to a same-filesystem **staging** location, `fsync`, then **atomic rename** both into place. No partial files may become visible.
* Post-publish, S2 **MUST** verify cross-artefact coherence (index↔blob) before returning success.

### 8.7 Concurrency

* At most **one** active publisher per `(component=2B.S2, seed, manifest_fingerprint)`.
* A concurrent publisher **MUST** either observe existing byte-identical artefacts and no-op, or abort on attempted overwrite.

### 8.8 Merge discipline

* **No appends, compactions, or in-place updates.** Any change requires publishing to a **new** `(seed,fingerprint)` identity (or a new fingerprint per change-control rules).

### 8.9 Determinism & replay

* Re-running S2 with **identical sealed inputs** (including policy bytes) **MUST** reproduce **bit-for-bit identical** index and blob.
* Numeric outcomes **MUST NOT** depend on thread scheduling or data-dependent re-ordering that changes reduction order.

### 8.10 Token hygiene

* Partition tokens **MUST** appear exactly once and in this order: `seed=…/fingerprint=…/`.
* Literal paths, environment-injected overrides, or ad-hoc globs are prohibited.

### 8.11 Cross-artefact coherence (binding)

* `blob_sha256` in the index **MUST** equal the SHA-256 of the blob’s **raw bytes**.
* For every index row, `[offset, offset+length)` **MUST** be within the blob size and **MUST NOT** overlap other rows.
* Header `quantised_bits`, `layout_version`, `endianness`, `alignment_bytes` **MUST** be consistent with the policy and all rows.

### 8.12 Retention & provenance

* Retention/licence/ownership are governed by the Registry; immutability is enforced by this section.
* `created_utc` **MUST** equal the canonical S0 time (`verified_at_utc`) for this fingerprint.

### 8.13 Downstream propagation

* Consumers (S5/S6) **MUST**: verify `blob_sha256`, rely on the index for slice locations, and decode using the policy’s `decode_law` with the echoed `layout_version/endianness/alignment`. File order is non-authoritative beyond the constraints above.

---

## 9. **Acceptance criteria (validators) (Binding)**

**Outcome rule.** **PASS** iff all **Abort** validators succeed. **WARN** validators may fail without blocking publish but MUST be recorded in the run-report.

**V-01 — Prior gate evidence present (Abort).**
` s0_gate_receipt_2B` exists for the target `manifest_fingerprint` and is discoverable via the Dictionary.

**V-02 — Dictionary-only resolution (Abort).**
All inputs (`s1_site_weights`, `alias_layout_policy_v1`) were resolved by **Dictionary IDs**; zero literal paths.

**V-03 — Partition/selection exact (Abort).**
Reads used only `s1_site_weights@seed={seed}/fingerprint={manifest_fingerprint}` and the **exact S0-sealed path** for `alias_layout_policy_v1` (no partition tokens).

**V-04 - Policy minima present (Abort).**
`alias_layout_policy_v1` provides at least: `layout_version`, `endianness`, `alignment_bytes`, `quantised_bits` (= **b**), `quantisation_epsilon` (= **ε_q**), `encode_spec`, `decode_law`, checksum rules, and required index fields.

**V-05 — S1 bit-depth coherence (Abort).**
All rows in `s1_site_weights` have constant `quantised_bits = b` and **b equals the policy’s `quantised_bits`**.

**V-06 — Output shape: index valid (Abort).**
` s2_alias_index` validates against `schemas.2B.yaml#/plan/s2_alias_index` (fields-strict).

**V-07 — Output shape: blob contract (Abort).**
` s2_alias_blob` satisfies the binary contract `#/binary/s2_alias_blob`: header echoes (`layout_version`, `endianness`, `alignment_bytes`, `quantised_bits`) match policy, and alignment rules apply.

**V-08 — Coverage: merchants (Abort).**
`index.merchants_count = number_of_distinct_merchants(s1_site_weights)` and the set of `merchant_id` in the index equals that from `s1_site_weights`.

**V-09 — Coverage: sites per merchant (Abort).**
For every `merchant_id`, index `sites` equals the count of `(merchant_id, legal_country_iso, site_order)` in `s1_site_weights`.

**V-10 — Writer/structural order (Abort).**
Index rows are in **strictly ascending `merchant_id`**; blob merchant slices appear in the same order; index `offset` values **strictly increase**.

**V-11 — Alignment & bounds (Abort).**
For every index row: `offset % alignment_bytes == 0`, `0 ≤ offset < blob_size_bytes`, and `offset + length ≤ blob_size_bytes`.

**V-12 — Non-overlap (Abort).**
Per-merchant byte ranges `[offset, offset+length)` do **not** overlap.

**V-13 — Header counts & sizes (Abort).**
`merchants_count = len(index.merchants)` and `blob_size_bytes = actual_size(s2_alias_blob)`.

**V-14 — Blob digest (Abort).**
`index.blob_sha256` equals the SHA-256 of the **raw bytes** of `s2_alias_blob`.

**V-15 — Bit-depth constant (Abort).**
Every merchant row carries `quantised_bits = b` and header `quantised_bits = b`.

**V-16 — Grid mass reconstruction (Abort).**
Reconstruct integer masses from `s1_site_weights` using S1’s law (`m* = p·2^b`, ties-to-even, deterministic Δ-adjust) and **require** per-merchant `Σ m_i = 2^b`.

**V-17 — Alias decode coherence (Abort).**
Decode each merchant’s slice from the blob per policy `decode_law`; let `p̂` be decoded weights. Require **per-row** `|p̂ − p_weight| ≤ ε_q` and **per-merchant** `Σ p̂ = 1` exactly.

**V-18 — Index↔blob coherence (Abort).**
For every row, decoding the slice at `[offset, length)` yields exactly `sites` weights for that `merchant_id`; checksum in the row matches the slice checksum computed per policy.

**V-19 — Policy echo & provenance (Abort).**
Index `{ policy_id="alias_layout_policy_v1", policy_digest }` matches the ID and digest recorded in S0’s inventory for this fingerprint.

**V-20 — Creation time canonical (Abort).**
`index.created_utc` equals S0 receipt’s `verified_at_utc` for this fingerprint.

**V-21 — Path↔embed equality (Abort).**
Any embedded identity in index/blob equals the dataset path tokens (`seed`, `fingerprint`).

**V-22 — Write-once immutability (Abort).**
Target partitions for index and blob were empty before publish, or existing bytes are **bit-identical**.

**V-23 — Idempotent re-emit (Abort).**
Re-running S2 with identical sealed inputs reproduces **bit-for-bit identical** index and blob; otherwise abort rather than overwrite.

**V-24 — No network & no extra reads (Abort).**
Execution performed with network I/O disabled and accessed **only** the assets listed in S0’s `sealed_inputs_v1` for this fingerprint.

**V-25 — Endianness & alignment echo (Abort).**
Header `endianness` and `alignment_bytes` equal the policy values; every merchant slice begins at an offset aligned to `alignment_bytes`.

**V-26 — Header required fields present (Abort).**
Header includes: `layout_version`, `endianness`, `alignment_bytes`, `quantised_bits`, `created_utc`, `policy_id`, `policy_digest`, `blob_sha256`, `blob_size_bytes`, `merchants_count`, `merchants[]`.

**V-27 — Deterministic queues convention (Warn).**
During encode, equality cases (e.g., `m_i = M`) followed the documented deterministic convention (classification to **large**, stable queue order). Violations log **WARN** with evidence sample.

**Reporting.** The run-report MUST include validator outcomes, counts (`merchants_total`, `sites_total`), `blob_sha256`, max `|p̂−p|`, and deterministic samples of index entries and decoded rows.

---

## 10. **Failure modes & canonical error codes (Binding)**

**Code namespace.** `2B-S2-XYZ` (zero-padded). **Severity** ∈ {**Abort**, **Warn**}.
Every failure log entry **MUST** include: `code`, `severity`, `message`, `fingerprint`, `seed`, `validator` (e.g., `"V-14"` or `"runtime"`), and a `context{…}` object with the keys listed below.

### 10.1 Gate & catalogue discipline

* **2B-S2-001 S0_RECEIPT_MISSING (Abort)** — No `s0_gate_receipt_2B` for target fingerprint.
  *Context:* `fingerprint`.
* **2B-S2-020 DICTIONARY_RESOLUTION_ERROR (Abort)** — Input ID could not be resolved for required partition(s)/path.
  *Context:* `id`, `expected_partition_or_path`.
* **2B-S2-021 PROHIBITED_LITERAL_PATH (Abort)** — Attempted read/write via a non-Dictionary path.
  *Context:* `path`.
* **2B-S2-022 UNDECLARED_ASSET_ACCESSED (Abort)** — Asset accessed but absent from S0 `sealed_inputs_v1`.
  *Context:* `id|path`.
* **2B-S2-023 NETWORK_IO_ATTEMPT (Abort)** — Network I/O detected.
  *Context:* `endpoint`.

### 10.2 Policy shape & minima

* **2B-S2-031 POLICY_SCHEMA_INVALID (Abort)** — `alias_layout_policy_v1` fails schema/parse.
  *Context:* `schema_errors[]`.
* **2B-S2-032 POLICY_MINIMA_MISSING (Abort)** — Required policy fields missing (e.g., `layout_version`, `endianness`, `alignment_bytes`, `quantised_bits`, `encode_spec`, `decode_law`, checksum rules).
  *Context:* `missing_keys[]`.

### 10.3 Output shapes & header

* **2B-S2-040 INDEX_SCHEMA_INVALID (Abort)** — `s2_alias_index` fails its schema.
  *Context:* `schema_errors[]`.
* **2B-S2-041 BLOB_CONTRACT_VIOLATION (Abort)** — `s2_alias_blob` violates binary contract (layout/endianness/alignment).
  *Context:* `detail`.
* **2B-S2-042 HEADER_FIELDS_MISSING (Abort)** — Required index header fields absent.
  *Context:* `missing_keys[]`.
* **2B-S2-045 HEADER_COUNT_MISMATCH (Abort)** — `merchants_count` or `blob_size_bytes` disagrees with computed values.
  *Context:* `header_merchants_count`, `actual_merchants_count`, `header_blob_size`, `actual_blob_size`.

### 10.4 Coverage & order

* **2B-S2-050 MERCHANT_COVERAGE_MISMATCH (Abort)** — Index merchant set ≠ `s1_site_weights` merchant set.
  *Context:* `missing_merchants[]`, `extra_merchants[]`.
* **2B-S2-051 SITES_COUNT_MISMATCH (Abort)** — Per-merchant `sites` ≠ count in `s1_site_weights`.
  *Context:* `merchant_id`, `index_sites`, `weights_sites`.
* **2B-S2-083 WRITER_ORDER_NOT_ASC (Abort)** — Index rows not strictly ascending by `merchant_id`.
  *Context:* `first_offending_row_index`.

### 10.5 Bit-depth & grid reconstruction

* **2B-S2-058 BIT_DEPTH_INCOHERENT (Abort)** — `quantised_bits` not constant across weights or ≠ policy `b`.
  *Context:* `policy_bits`, `observed_bits[]`.
* **2B-S2-052 GRID_SUM_INCORRECT (Abort)** — For some merchant, Σ `m_i` ≠ `2^b`.
  *Context:* `merchant_id`, `sum_m`, `expected=2^b`.
* **2B-S2-053 NEGATIVE_OR_OVERFLOW_MASS (Abort)** — Any reconstructed `m_i < 0` or `m_i > 2^b`.
  *Context:* `merchant_id`, `site_order`, `m_i`.

### 10.6 Index ↔ blob coherence

* **2B-S2-060 RANGE_OUT_OF_BOUNDS (Abort)** — `[offset, offset+length)` falls outside blob size.
  *Context:* `merchant_id`, `offset`, `length`, `blob_size_bytes`.
* **2B-S2-061 RANGE_OVERLAP (Abort)** — Merchant byte ranges overlap.
  *Context:* `merchant_id_a`, `merchant_id_b`.
* **2B-S2-062 BLOB_DIGEST_MISMATCH (Abort)** — `index.blob_sha256` ≠ SHA-256(raw blob bytes).
  *Context:* `expected_sha256`, `actual_sha256`.
* **2B-S2-063 CHECKSUM_MISMATCH (Abort)** — Per-merchant checksum disagrees with recomputed slice checksum.
  *Context:* `merchant_id`, `expected_checksum`, `actual_checksum`.
* **2B-S2-064 ENDIANNESS_OR_ALIGNMENT_MISMATCH (Abort)** — Index header endianness/alignment differ from policy or slice offsets violate alignment.
  *Context:* `endianness_header`, `endianness_policy`, `alignment_bytes`, `offending_offset`.

### 10.7 Alias decode coherence

* **2B-S2-055 ALIAS_DECODE_INCOHERENT (Abort)** — Decoding a slice per `decode_law` yields per-row `|p̂ − p| > ε_q` or per-merchant Σ `p̂ ≠ 1`.
  *Context:* `merchant_id`, `epsilon_q`, `max_abs_delta`, `mass_sum_hat`.

### 10.8 Identity, partitions & immutability

* **2B-S2-070 PARTITION_SELECTION_INCORRECT (Abort)** — Not exactly `seed={seed}/fingerprint={fingerprint}` (or wrong policy selection semantics).
  *Context:* `id`, `expected`, `actual`.
* **2B-S2-071 PATH_EMBED_MISMATCH (Abort)** — Embedded identity differs from path token(s).
  *Context:* `embedded`, `path_token`.
* **2B-S2-080 IMMUTABLE_OVERWRITE (Abort)** — Target partition not empty and bytes differ.
  *Context:* `target_path`.
* **2B-S2-081 NON_IDEMPOTENT_REEMIT (Abort)** — Re-emit produced byte-different outputs for identical inputs.
  *Context:* `digest_prev`, `digest_now`.
* **2B-S2-082 ATOMIC_PUBLISH_FAILED (Abort)** — Staging/rename not atomic or post-publish verification failed.
  *Context:* `staging_path`, `final_path`.

### 10.9 Provenance & timing

* **2B-S2-085 POLICY_ECHO_MISMATCH (Abort)** — `{policy_id, policy_digest}` in index header ≠ S0 inventory values.
  *Context:* `header_policy_digest`, `s0_policy_digest`.
* **2B-S2-086 CREATED_UTC_MISMATCH (Abort)** — `created_utc` ≠ S0 `verified_at_utc`.
  *Context:* `created_utc`, `verified_at_utc`.

### 10.10 Deterministic conventions (WARN class)

* **2B-S2-090 DETERMINISTIC_QUEUE_CONVENTION (Warn)** — Equality cases in encode (e.g., `m_i = M`) not handled per documented convention; output still decodes coherently.
  *Context:* `merchant_id`, `evidence_sample`.

### 10.11 Validator → code map (Binding)

| Validator                                | Canonical codes (may emit multiple) |
|------------------------------------------|-------------------------------------|
| **V-01 Prior gate evidence present**     | 2B-S2-001                           |
| **V-02 Dictionary-only resolution**      | 2B-S2-020, 2B-S2-021                |
| **V-03 Partition/selection exact**       | 2B-S2-070                           |
| **V-04 Policy minima present**           | 2B-S2-031, 2B-S2-032                |
| **V-05 S1 bit-depth coherence**          | 2B-S2-058                           |
| **V-06 Output shape: index valid**       | 2B-S2-040, 2B-S2-042, 2B-S2-045     |
| **V-07 Output shape: blob contract**     | 2B-S2-041, 2B-S2-064                |
| **V-08 Coverage: merchants**             | 2B-S2-050                           |
| **V-09 Coverage: sites per merchant**    | 2B-S2-051                           |
| **V-10 Writer/structural order**         | 2B-S2-083, 2B-S2-044 *(if used)*    |
| **V-11 Alignment & bounds**              | 2B-S2-060                           |
| **V-12 Non-overlap**                     | 2B-S2-061                           |
| **V-13 Header counts & sizes**           | 2B-S2-045                           |
| **V-14 Blob digest**                     | 2B-S2-062                           |
| **V-15 Bit-depth constant**              | 2B-S2-058                           |
| **V-16 Grid mass reconstruction**        | 2B-S2-052, 2B-S2-053                |
| **V-17 Alias decode coherence**          | 2B-S2-055                           |
| **V-18 Index↔blob coherence**            | 2B-S2-063                           |
| **V-19 Policy echo & provenance**        | 2B-S2-085                           |
| **V-20 Creation time canonical**         | 2B-S2-086                           |
| **V-21 Path↔embed equality**             | 2B-S2-071                           |
| **V-22 Write-once immutability**         | 2B-S2-080                           |
| **V-23 Idempotent re-emit**              | 2B-S2-081                           |
| **V-24 No network & no extra reads**     | 2B-S2-023, 2B-S2-022, 2B-S2-021     |
| **V-25 Endianness & alignment echo**     | 2B-S2-064                           |
| **V-26 Header required fields present**  | 2B-S2-042                           |
| **V-27 Deterministic queues convention** | 2B-S2-090 *(Warn)*                  |

---

## 11. **Observability & run-report (Binding)**

### 11.1 Purpose

Emit a **single structured run-report** that proves what S2 read, how it constructed the alias artefacts, and what it published. The run-report is **diagnostic (non-authoritative)**; the **index + blob** remain the sources of truth.

### 11.2 Emission

* S2 **MUST** write the run-report to **STDOUT** as one JSON document on successful publish (and on abort, if possible).
* S2 **MAY** persist the same JSON to an implementation-defined log. Persisted copies **MUST NOT** be used by downstream contracts.

### 11.3 Top-level shape (fields-strict)

The run-report **MUST** contain these top-level fields:

* `component`: `"2B.S2"`
* `fingerprint`: `<hex64>`
* `seed`: `<string>`
* `created_utc`: ISO-8601 UTC (echo of S0 `verified_at_utc`)
* `catalogue_resolution`: `{ dictionary_version: <semver>, registry_version: <semver> }`
* `policy`:

  * `id`: `"alias_layout_policy_v1"`
  * `version_tag`: `<string>`
  * `sha256_hex`: `<hex64>`
  * `layout_version`: `<string>`
  * `endianness`: `"little" | "big"`
  * `alignment_bytes`: `<int>`
  * `quantised_bits`: `<int>` *(b)*
* `inputs_summary`:

  * `weights_path`: `<string>` *(Dictionary-resolved path to `s1_site_weights@seed,fingerprint`)*
  * `merchants_total`: `<int>`
  * `sites_total`: `<int>`
* `blob_index`:

  * `blob_path`: `<string>`
  * `index_path`: `<string>`
  * `blob_size_bytes`: `<int>`
  * `blob_sha256`: `<hex64>`
  * `merchants_count`: `<int>`
* `encode_stats`:

  * `grid_bits`: `<int>` *(= b)*
  * `grid_size`: `<int>` *(= 2^b)*
  * `max_abs_delta_decode`: `<float>` *(max |p̂ − p| across all rows, post-decode check)*
  * `merchants_mass_exact_after_decode`: `<int>` *(should equal `merchants_total`)*
* `publish`:

  * `targets`: `[ { id: "s2_alias_index", path: <string>, bytes: <int> }, { id: "s2_alias_blob", path: <string>, bytes: <int> } ]`
  * `write_once_verified`: `<bool>`
  * `atomic_publish`: `<bool>`
* `validators`: `[ { id: "V-01", status: "PASS|FAIL|WARN", codes: [ "2B-S2-0XX", … ] } … ]`
* `summary`: `{ overall_status: "PASS|FAIL", warn_count: <int>, fail_count: <int> }`
* `environment`: `{ engine_commit?: <string>, python_version: <string>, platform: <string>, network_io_detected: <int> }`

### 11.4 Evidence & samples (bounded, deterministic)

Include **bounded**, **deterministic** samples sufficient for offline verification without scanning the full artefacts:

* `samples.index_rows` — up to **20** index entries `{ merchant_id, offset, length, sites, quantised_bits, checksum }` in ascending `merchant_id` (first N).
* `samples.decode_rows` — up to **20** rows `{ merchant_id, site_order, p_weight, p_hat, abs_delta }` selected by **largest `abs_delta` first**, then PK order.
* `samples.boundary_checks` — up to **10** entries showing nearest-neighbor ranges around the **smallest** and **largest** offsets to illustrate non-overlap: `{ merchant_id, offset, length, next_offset, gap_bytes }`.
* `samples.alignment` — up to **10** entries `{ merchant_id, offset, alignment_bytes, aligned: <bool> }` (deterministic pick: first N by `merchant_id`).

All sample values **MUST** be copied from authoritative artefacts (index/blob/weights), not recomputed beyond the algorithm in this spec.

### 11.5 Counters (minimum set)

S2 **MUST** emit at least:

* `merchants_total`, `sites_total`, `merchants_count`
* `blob_size_bytes`, `publish_bytes_total` *(sum over both artefacts)*
* `grid_bits`, `grid_size`
* `non_overlap_violations` *(should be 0)*, `alignment_violations` *(should be 0)*
* Durations (milliseconds): `resolve_ms`, `reconstruct_ms`, `encode_ms`, `serialize_ms`, `digest_ms`, `decode_check_ms`, `publish_ms`

### 11.6 Histograms / distributions (optional, bounded)

If emitted, histograms **MUST** be bounded in size and deterministic in binning:

* `hist.abs_delta_decode` — fixed bins over `[0, ε_q]` with counts.
* `hist.slice_lengths_bytes` — fixed bins (log-scaled or fixed widths) over slice lengths with counts.

### 11.7 Determinism of lists

Arrays in the run-report **MUST** be emitted in deterministic order:

* `validators`: sorted by validator ID (`"V-01"` …).
* `targets`: fixed order `["s2_alias_index", "s2_alias_blob"]`.
* `samples.*`: as specified in §11.4 (largest-delta first where stated; otherwise ascending `merchant_id`).

### 11.8 PASS/WARN/FAIL semantics

* `overall_status = "PASS"` iff **all Abort-class validators** succeeded.
* WARN-class failures increment `warn_count` and **MUST** appear in `validators[]` with `status: "WARN"`.
* On any Abort-class failure, `overall_status = "FAIL"`; publish **MUST NOT** occur, but an attempted run-report **SHOULD** still be emitted with partial data when safe.

### 11.9 Privacy & retention

* The run-report **MUST NOT** include raw blob bytes; only keys, paths, counts, digests, checksums, offsets/lengths, and derived metrics.
* Retention is governed by the Registry’s diagnostic-log policy; the run-report is **not** an authoritative artefact and **MUST NOT** be hashed into any bundle.

### 11.10 ID-to-artifact echo

For traceability, S2 **MUST** echo an `id_map` array of the exact Dictionary-resolved paths used:

```
id_map: [
  { id: "s1_site_weights",      path: "<…/s1_site_weights/seed=…/fingerprint=…/>" },
  { id: "alias_layout_policy_v1", path: "<…/contracts/policy/2B/alias_layout_policy_v1.json>" },
  { id: "s2_alias_index",         path: "<…/s2_alias_index/seed=…/fingerprint=…/index.json>" },
  { id: "s2_alias_blob",          path: "<…/s2_alias_blob/seed=…/fingerprint=…/alias.bin>" }
]
```

Paths **MUST** match those actually resolved/written at runtime.

---

## 12. **Performance & scalability (Informative)**

### 12.1 Workload model & symbols

Let:

* **M** = number of merchants; **Kᵢ** = sites for merchant *i*; **S = Σᵢ Kᵢ** (total sites).
* **b** = `quantised_bits`; **G = 2ᵇ** (grid size).
* **B** = final blob size in bytes; **A** = `alignment_bytes`.

S2 is a single pass over **S** rows to reconstruct integer masses and encode alias structures, plus a streamed write of **B** bytes and one SHA-256 over those **B** bytes.

---

### 12.2 Time characteristics

* **Integer-grid reconstruction:** `O(S)` (scale→round-even→Δ-adjust per merchant; stable ordering).
* **Alias encoding:** `O(S)` overall (each merchant `O(Kᵢ)`; each row enqueued/dequeued at most once).
* **Blob serialisation:** `O(B)` (writing + per-merchant checksum).
* **Digesting:** `O(B)` (stream SHA-256 over raw bytes).
* **Index construction:** `O(M)` (one row per merchant).
* **Optional external sort:** if `s1_site_weights` is not grouped by merchant/PK, a deterministic external sort costs `O(S log S)` comparisons with streaming I/O.

Overall: `O(S + B)` on grouped input; `O(S log S + B)` if a sort is required.

---

### 12.3 Memory footprint

* **Working set:** `O(max Kᵢ)` if processing one merchant at a time. Keep only:

  * per-merchant arrays (`m*`, remainders, small/large queues),
  * the encoded slice buffer (can be streamed).
* **Streaming mode:** compute the per-merchant slice **length** during encode, write bytes directly to the blob stream, and update `offset`/`length` counters; no need to hold the entire blob in memory.
* **Checksum/digest:** maintain a rolling per-merchant checksum and a **single** streaming SHA-256 for the whole blob to avoid re-reads.

---

### 12.4 I/O discipline

* **One read pass** over `s1_site_weights` (project only the required columns).
* **One write stream** for the blob (append-only, aligned) + **one small JSON write** for the index.
* **Alignment:** when the next merchant slice would start at an unaligned offset, write `≤ A−1` bytes of padding (policy’s `padding_rule`) before the slice.
* **Atomic publish:** write both artefacts to staging paths on the **same filesystem**, `fsync`, then atomic rename to final paths.

---

### 12.5 Parallelism (safe patterns)

* **Across merchants:** safe if each worker owns a **disjoint, deterministic shard** of merchants and emits:

  1. a private shard-blob and shard-index, then
  2. a **deterministic merge** step concatenates shard-blobs **in ascending `merchant_id`** and merges index rows, updating offsets with exact prefix sums (including padding).
* **Within a merchant:** keep **serial reductions** and queue operations to preserve determinism.
* **Forbidden:** any parallelism that reorders merchants, alters per-merchant processing order, or changes reduction/queue order.

---

### 12.6 Numeric determinism guardrails

* **Arithmetic:** binary64, round-to-nearest-even; no FMA/FTZ/DAZ; no data-dependent re-ordering of reductions.
* **Quantisation reconstruction:** ties-to-even then Δ-adjust with **fractional remainder** priority and **PK tiebreak**.
* **Alias encode queues:** initialise `small`/`large` in **PK order**; pop/push from the **front/back** as specified to keep queue state deterministic across platforms.

---

### 12.7 Throughput tips (non-binding)

* **Project columns early:** read `(merchant_id, legal_country_iso, site_order, p_weight, quantised_bits)` only.
* **Remainder pass:** keep `(remainder, PK_index)` in a small array; use a stable partial selection (no full sort) when Δ is small.
* **Two-phase write (optional):** if layout requires sizes up front, encode to a small per-merchant buffer to get `length`, allocate/pad, then stream the buffer into the blob; otherwise encode directly to the blob while accumulating `length`.
* **Digest while writing:** feed blob bytes into SHA-256 as they are written; no second pass needed.
* **Row group sizing:** if Parquet/JSON side artefacts accompany the blob (e.g., diagnostics), use bounded row groups; do not affect blob order.

---

### 12.8 Scale limits & mitigations

* **Very large merchants (high `Kᵢ`):** ensure encode is strictly linear in `Kᵢ`; use bounded buffers and avoid quadratic alias implementations.
* **Huge S:** if input is ungrouped, use an **external merge sort** with fixed chunk size and deterministic fan-in order. Spill to a local temp area on the same device as the final blob to keep rename atomic and cheap.
* **Large `B`:** blob write is bandwidth-bound; ensure sequential writes and avoid small, scattered writes. Keep alignment `A` modest; excessive padding inflates `B`.

---

### 12.9 Observability KPIs (suggested)

Track and alert on:

* **Counts:** `merchants_total`, `sites_total`, `merchants_count`, `non_overlap_violations`, `alignment_violations`.
* **Size/throughput:** `blob_size_bytes`, `publish_bytes_total`, bytes/sec during serialize/digest.
* **Quality:** `max_abs_delta_decode` (≤ ε_q), `merchants_mass_exact_after_decode` (== `merchants_total`).
* **Timing:** `resolve_ms`, `reconstruct_ms`, `encode_ms`, `serialize_ms`, `digest_ms`, `decode_check_ms`, `publish_ms`.

---

### 12.10 Non-goals

* No network I/O, compression tricks, or probabilistic sampling.
* No record-level updates/merges post-publish; any change requires a new `{seed,fingerprint}` (or new fingerprint per change-control).

---

## 13. **Change control & compatibility (Binding)**

### 13.1 Scope

This section governs permitted changes to **2B.S2** after ratification and how those changes are versioned and rolled out. It applies to: the **procedure**, the **outputs** (`s2_alias_index`, `s2_alias_blob`), the **binary layout/endianness/alignment**, the **encode/decode law**, required **header/row fields**, and **validators/error codes**.

---

### 13.2 Stable, non-negotiable surfaces (unchanged without a **major** bump)

Within the same **major** version, S2 **MUST NOT** change:

* **Output identities & partitions:** dataset IDs `s2_alias_index`, `s2_alias_blob`; partitions `[seed, fingerprint]`; **path↔embed equality**; write-once + atomic publish (two-artefact transaction).
* **Binary contract & layout law:** presence of a single **contiguous blob**; **layout_version** semantics; **endianness** and **alignment_bytes** meaning; merchant slices non-overlapping and ordered by ascending `merchant_id`.
* **Index/header law:** required header fields (`layout_version`, `endianness`, `alignment_bytes`, `quantised_bits`, `created_utc`, `policy_id`, `policy_digest`, `blob_sha256`, `blob_size_bytes`, `merchants_count`, `merchants[]`) and required per-merchant fields (`merchant_id`, `offset`, `length`, `sites`, `quantised_bits`, `checksum`).
* **Quantisation reconstruction law:** `G = 2^b`; **round half-to-even**; deterministic Δ-adjust by fractional remainder with PK tiebreak; per-merchant Σ `m_i = 2^b`.
* **Alias encode/decode invariants:** deterministic queue conventions; decode returns `p̂` with per-row `|p̂ − p| ≤ ε_q` and per-merchant Σ `p̂ = 1`.
* **Digest/checksum law:** `blob_sha256` = SHA-256 over **raw** blob bytes; per-merchant `checksum` semantics as declared by policy.
* **Deterministic posture:** S2 is **RNG-free**; Dictionary-only resolution; no network I/O.
* **Acceptance posture:** the set and meaning of **Abort-class** validators (by ID).

Any change here is **breaking** → **new major** of this spec and associated schema anchors.

---

### 13.3 Backward-compatible changes (allowed with **minor** or **patch** bump)

* **Editorial clarifications** and examples that do not change behaviour. *(patch)*
* **Run-report** additions (new counters/samples/histograms); run-report is non-authoritative. *(minor/patch)*
* **Index metadata (optional):** add **optional** header keys or per-merchant metadata fields that validators ignore and consumers are not required to read. *(minor)*
* **WARN-class validators:** add new WARN checks or improve messages/context without altering PASS/FAIL criteria. *(minor)*
* **Policy surface extensions** that are **optional** (e.g., an optional secondary checksum field) and do not alter existing required behaviour. *(minor)*

---

### 13.4 Breaking changes (require **major** bump + migration)

* Renaming output IDs, changing **partitions**, or altering **path families**.
* Changing **binary layout**, **endianness**, **alignment_bytes**, or the rule for slice order/overlap.
* Removing/renaming required **index header** or **per-merchant** fields, or changing their semantics.
* Changing the **quantisation reconstruction law** (rounding mode, Δ-adjust ordering/ties).
* Changing the **alias encode/decode law** so that decoded `p̂` differs beyond ε_q or mass is not exactly 1.
* Replacing SHA-256 for `blob_sha256`, or changing the per-merchant `checksum` algorithm without providing a new field and validator mapping.
* Reclassifying a **WARN** validator to **Abort**, or adding a **new Abort** validator that can fail for previously valid outputs.
* Allowing **literal paths** or **network I/O**, or removing Dictionary-only resolution.

---

### 13.5 SemVer & release discipline

* **Major:** any change listed in §13.4 → bump spec + schema anchors (e.g., `#/plan/s2_alias_index_v2`, `#/binary/s2_alias_blob_v2`), update Dictionary/Registry entries, and provide migration notes.
* **Minor:** additive behaviour that is backward-compatible (optional metadata, WARN validators, run-report fields).
* **Patch:** editorial only (no shape/procedure/validators change).

When Status = **frozen**, post-freeze edits are **patch-only** unless a ratified minor/major is published.

---

### 13.6 Relationship to policy bytes

* The values of **`layout_version`**, **`endianness`**, **`alignment_bytes`**, **`quantised_bits`**, **`encode_spec`**, **`decode_law`**, and checksum rules are provided by **`alias_layout_policy_v1`**. Updating the **bytes** of that policy **does not change this spec** and is **not** a spec version event; it simply yields different sealed inputs for a run (captured by S0 and echoed in the index).
* However, **removing** a required policy entry or changing its **meaning** so S2’s acceptance changes is **breaking** and requires a **major** of this spec and the policy anchor.

---

### 13.7 Compatibility guarantees to downstream states (S5/S6)

* Downstreams **MAY** rely on: presence and shape of `s2_alias_index` + `s2_alias_blob`; ascending `merchant_id` order; non-overlap and alignment; `blob_sha256`; constant bit-depth **b**; and the decode law indicated by policy.
* Downstreams **MUST NOT** assume any undocumented record layout beyond what the policy and index header declare, nor rely on run-report fields.

---

### 13.8 Deprecation & migration protocol

* Changes are proposed → reviewed → ratified with a **change log** describing impact, validator deltas, new anchors, and migration steps.
* For majors, a **dual-publish window** is recommended: emit `v1` and `v2` artefacts in parallel (v2 authoritative; v1 legacy) for a time-boxed period, or provide a decode shim that accepts both.

---

### 13.9 Rollback policy

* Outputs are **write-once**; rollback means publishing a **new** `(seed,fingerprint)` (or reverting to a prior fingerprint) that reproduces the last known good behaviour. No in-place mutation.

---

### 13.10 Evidence of compatibility

* Each release MUST include: schema diffs, validator table diffs, and a conformance run showing that previously valid S2 outputs still **PASS** (for minor/patch).
* CI MUST run a regression suite: index/blob schema validity, coverage, ordering, alignment, non-overlap, digest/checksum coherence, decode coherence, immutability, idempotent re-emit.

---

### 13.11 Registry/Dictionary coordination

* Dictionary changes that alter ID names, path families, or partition tokens for `s2_alias_index`/`s2_alias_blob` are **breaking** unless accompanied by new anchors/IDs and a migration plan.
* Registry edits limited to **metadata** (owner/licence/retention) are compatible; edits that change **existence** of required artefacts are breaking.

---

### 13.12 Validator/code namespace stability

* Validator IDs (`V-01`…`V-27`) and canonical codes (`2B-S2-…`) are **reserved**. New codes may be added; the meaning of existing codes **MUST NOT** change within a major.

---

## Appendix A — Normative cross-references *(Informative)*

> This appendix lists the authoritative artefacts S2 references. **Schemas** govern shape; the **Dataset Dictionary** governs ID → path/partitions/format; the **Artefact Registry** governs ownership/licence/retention. Binding rules live in §§1–13.

### A.1 Authority chain (this segment)

* **Schema pack (shape authority):** `schemas.2B.yaml`

  * Output anchors used by S2:

    * `#/plan/s2_alias_index` — alias index (fields-strict)
    * `#/binary/s2_alias_blob` — alias blob (binary contract)
  * Input/policy anchors referenced by S2:

    * `#/plan/s1_site_weights` — per-merchant weights from S1
    * `#/policy/alias_layout_policy_v1` — layout/endianness/alignment, bit-depth **b**, encode/decode law, checksum rules
  * Common defs: `#/$defs/hex64`, `#/$defs/partition_kv`
    *(timestamps reuse `schemas.layer1.yaml#/$defs/rfc3339_micros`)*

* **Dataset Dictionary (catalogue authority):** `dataset_dictionary.layer1.2B.yaml`

  * **S2 outputs & path families:**

    * `s2_alias_index` → `data/layer1/2B/s2_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/index.json` (format: json)
    * `s2_alias_blob`  → `data/layer1/2B/s2_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/alias.bin` (format: binary)
  * **S2 inputs (Dictionary IDs):**

    * `s1_site_weights` → `data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/` (format: parquet)
    * `alias_layout_policy_v1` → `contracts/policy/2B/alias_layout_policy_v1.json` (single file; no partition tokens)

* **Artefact Registry (metadata authority):** `artefact_registry_2B.yaml`

  * Ownership/retention for `s2_alias_index`, `s2_alias_blob`, `s1_site_weights`, and `alias_layout_policy_v1`; cross-layer notes as applicable.

### A.2 Prior state evidence (2B.S0)

* **`s0_gate_receipt_2B`** — gate verification, identity, catalogue versions (fingerprint-scoped).
* **`sealed_inputs_v1`** — authoritative list of sealed assets (IDs, tags, digests, paths, partitions).
  *(S2 does not re-hash 1B; it relies on this evidence.)*

### A.3 Inputs consumed by S2 (read-only)

* **Weights table (from S1):**

  * `s1_site_weights` → `data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/`
  * **Shape:** `schemas.2B.yaml#/plan/s1_site_weights`
* **Policy (layout & decode law):**

  * `alias_layout_policy_v1` → `contracts/policy/2B/alias_layout_policy_v1.json`
  * **Shape:** `schemas.2B.yaml#/policy/alias_layout_policy_v1`
  * **Selection:** single file, **no partition tokens**; use the **exact S0-sealed path/digest** for this fingerprint.

> **Note:** S2 **does not** read 2A pins (`site_timezones`, `tz_timetable_cache`).

### A.4 Outputs produced by this state

* **`s2_alias_index`** (JSON; `[seed, fingerprint]`)
  **Shape:** `schemas.2B.yaml#/plan/s2_alias_index`
  **Dictionary path:** `data/layer1/2B/s2_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/index.json`
  **Header (required):** `layout_version`, `endianness`, `alignment_bytes`, `quantised_bits`, `created_utc`, `policy_id`, `policy_digest`, `blob_sha256`, `blob_size_bytes`, `merchants_count`, `merchants[]`
  **Row (required):** `merchant_id`, `offset`, `length`, `sites`, `quantised_bits`, `checksum`
  **Writer order:** ascending `merchant_id`

* **`s2_alias_blob`** (binary; `[seed, fingerprint]`)
  **Contract:** `schemas.2B.yaml#/binary/s2_alias_blob`
  **Dictionary path:** `data/layer1/2B/s2_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/alias.bin`
  **Layout:** `layout_version`, `endianness`, `alignment_bytes` from policy; slices non-overlapping, ordered by `merchant_id`

### A.5 Identity & token discipline

* **Tokens:** `seed={seed}`, `fingerprint={manifest_fingerprint}`
* **Partition law:** both outputs partition by **both** tokens; inputs selected exactly as declared (policy is token-less, path chosen from S0 inventory).
* **Path↔embed equality:** any embedded identity in index/blob (and echoed metadata) must equal the path tokens.

### A.6 Segment context

* **Segment overview:** `state-flow-overview.2B.txt` *(context only; this S2 spec governs).*
* **Layer identity & gate laws:** programme-wide rules (No PASS → No read; hashing law; write-once + atomic publish).

---
