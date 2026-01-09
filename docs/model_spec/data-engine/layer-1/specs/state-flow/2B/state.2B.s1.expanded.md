# State 2B.S1 — Per-merchant weight freezing

## 1. **Document metadata & status (Binding)**

**Component:** Layer-1 · Segment **2B** — **State-1 (S1)** · *Per-merchant weight freezing*
**Document ID:** `seg_2B.s1.weights`
**Version (semver):** `v1.0.0-alpha`
**Status:** `alpha` *(normative; semantics lock at `frozen` in a ratified release)*
**Owners:** Design Authority (DA): **Esosa Orumwese** · Review Authority (RA): **Layer 1 Governance**
**Effective date:** **2025-11-02 (UTC)**

**Authority chain (Binding):**
**JSON-Schema pack** = shape authority → `schemas.2B.yaml`
**Dataset Dictionary** = ID→path/partitions/format → `dataset_dictionary.layer1.2B.yaml`
**Artefact Registry** = existence/licence/retention → `artefact_registry_2B.yaml`

**Normative cross-references (Binding):**

* Prior state evidence: **`s0_gate_receipt_2B`**, **`sealed_inputs_2B`**.
* Upstream egress: **`site_locations`** (Layer-1 · 1B).
* Policy: **`alias_layout_policy_v1`** (quantisation/floor/encoding constraints for S1/S2).
* Optional pins (read-only): **`site_timezones`**, **`tz_timetable_cache`** (Layer-2 · 2A).
* Segment overview: `state-flow-overview.2B.txt` (context only).

**Segment invariants (Binding):**

* **Run identity:** `{ seed, manifest_fingerprint }`.
* **Partitioning for S1 outputs:** `[seed, fingerprint]`; **path↔embed equality** MUST hold.
* **Catalogue discipline:** Dictionary-only resolution; literal paths forbidden.
* **RNG posture:** **S1 is RNG-free**; later RNG-bounded states in 2B use governed Philox per policy.
* **Gate law:** Downstreams rely on S0; **No PASS → No read** remains in force across the segment.

---

## 2. **Purpose & scope (Binding)**

**Purpose.** Freeze a **deterministic probability law** over sites for each merchant, derived from sealed inputs, and publish it as a byte-stable table for downstream routing. The result fixes long-run outlet shares and is the **only** weight source S2–S6 may use.

**S1 SHALL:**

* **Read authority via S0.** Operate only after a valid 2B.S0 receipt for the target `manifest_fingerprint`; resolve inputs **by Dictionary IDs**.
* **Derive base weights deterministically** from policy-declared source fields in `site_locations` (e.g., a precomputed site scalar or composition thereof) as specified by **`alias_layout_policy_v1`**.
* **Apply policy constraints** (floor/cap, min positive mass, tolerance `ε/ε_q`, bit-depth) exactly as declared by `alias_layout_policy_v1`.
* **Normalise per merchant** to obtain `p_i` with Σᵢ `p_i = 1` (within policy tolerance), then **quantise** to the policy bit-depth for downstream alias construction.
* **Record provenance** for every row: `weight_source` (policy-declared), `quantised_bits`, and `floor_applied` (boolean). Set `created_utc` to the run’s canonical time (echo of S0 `verified_at_utc`).
* **Partition identity** by `{seed, manifest_fingerprint}`; enforce path↔embed equality; write-once; idempotent.

**Scope (operations included).**

* Deterministic transformation from catalogued inputs to the egress **`s1_site_weights`** (fields/shape per schema anchor).
* Per-merchant grouping, floor/cap application, normalisation, quantisation, and deterministic writer ordering (PK order).
* Policy-defined **fallback** when a merchant’s effective pre-normalisation mass is zero or `NaN` (e.g., uniform within the merchant set); S1 SHALL implement the fallback declared by the policy.

**Out of scope.**

* Alias table construction (S2), day-effect draws (S3), zone re-normalisation (S4), per-arrival routing (S5/S6), audits/CI (S7), and the 2B PASS bundle (S8).
* Network access, stochastic sampling, or inference beyond what the catalogue and policy declare.

**Non-goals / prohibitions.**

* S1 SHALL NOT invent columns, read literal paths, or depend on runtime environment variance.
* S1 SHALL NOT modify upstream identities/keys from `site_locations`; it only emits weights and provenance alongside the PK defined by the output anchor.

---

## 3. **Preconditions & sealed inputs (Binding)**

### 3.1 Preconditions (Abort on failure)

* **Prior gate evidence.** A valid **`s0_gate_receipt_2B`** for the target **`manifest_fingerprint`** MUST exist.
* **Run identity fixed.** The pair **`{ seed, manifest_fingerprint }`** is fixed at start of S1 and MUST remain constant.
* **RNG posture.** S1 performs **no random draws** (RNG-free).
* **Dictionary-only.** All inputs **MUST** resolve by **Dataset Dictionary IDs**; literal paths are forbidden.

### 3.2 Required sealed inputs (must all be present)

S1 SHALL read **only** the following, for this run’s identity:

1. **`site_locations`** — Layer-1 · 1B egress at
   `seed={seed} / fingerprint={manifest_fingerprint}`.
2. **`alias_layout_policy_v1`** — policy pack governing **weight source**, floors/caps, normalisation tolerance `ε`, quantisation bit-depth and tolerance `ε_q`, and required metadata fields.

> These assets **MUST** be resolvable via the Dictionary for the target partitions and **MUST** appear in the S0 inventory for the same fingerprint.

### 3.3 Optional pins (all-or-none; read-only)

If S0 sealed them for this fingerprint, S1 MAY read **both** of:

* **`site_timezones`** — at `seed={seed} / fingerprint={manifest_fingerprint}`
* **`tz_timetable_cache`** — at `fingerprint={manifest_fingerprint}`

If exactly one is present in S0’s inventory, S1 MUST treat this as **mixed pins** (WARN) and proceed **without** using either.

### 3.4 Resolution & partition discipline

* **Exact partitioning.**
  • For `site_locations`: **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
  • For `alias_layout_policy_v1`: **no partition tokens**; select the **exact S0-sealed path** (and digest) for this fingerprint.
  • For optional pins: as stated above.
* **Subset of S0.** Every asset S1 reads **MUST** be a subset of (or equal to) the assets sealed in S0's `sealed_inputs_2B` for this fingerprint. Accessing any asset not listed there is an error.
* **No re-hashing upstream gates.** S1 MUST NOT recompute the 1B bundle hash; the S0 receipt is the sole attestation.

### 3.5 Input field expectations (from policy; Abort if unmet)

`alias_layout_policy_v1` **MUST** declare at minimum:

* `weight_source` (the column in `site_locations` or deterministic transform to use),
* `floor_spec` (e.g., absolute/relative floor and zero-mass fallback),
* `normalisation_epsilon` **ε**,
* `quantised_bits` and `quantisation_epsilon` **ε_q**,
* required output metadata flags (`floor_applied`, `weight_source`, `quantised_bits`).

S1 SHALL abort if any required policy entry is missing or if `site_locations` lacks the referenced input columns.

---

## 4. **Inputs & authority boundaries (Binding)**

### 4.1 Catalogue authorities

* **Schema pack** (`schemas.2B.yaml`) is the **shape authority** for all S1 outputs and any input anchors referenced here.
* **Dataset Dictionary** (`dataset_dictionary.layer1.2B.yaml`) is the **sole authority** for resolving **IDs → path templates, partitions, and formats**.
* **Artefact Registry** (`artefact_registry_2B.yaml`) provides **existence/licence/retention/ownership** metadata and does **not** override Dictionary paths.

### 4.2 Inputs S1 MAY read (and nothing else)

Resolve **only** these IDs via the Dictionary (no literal paths):

1. **`site_locations`** — Layer-1 · 1B egress at `seed={seed} / fingerprint={manifest_fingerprint}`.
2. **`alias_layout_policy_v1`** — policy governing weight source, floors/caps, normalisation/quantisation tolerances, and required provenance fields.
3. **Optional pins (all-or-none; read-only):**

   * `site_timezones` — 2A egress at `seed={seed} / fingerprint={manifest_fingerprint}`
   * `tz_timetable_cache` — 2A cache at `fingerprint={manifest_fingerprint}`

> **Subset of S0:** Every asset S1 reads **MUST** appear in the S0 `sealed_inputs_2B` for the same fingerprint.

### 4.3 Prohibited resources & reads

* **No literal paths** (env overrides, hard-coded strings, ad-hoc globs).
* **No network I/O** (online fetch, HTTP, remote FS).
* **No extra inputs** beyond §4.2 (including future 2B states).
* **No re-hashing of 1B bundles**; S0 receipt is the sole gate attestation.

### 4.4 Resolution & token discipline

* **Exact partitioning:**
  • `site_locations`: **exactly** `seed={seed} / fingerprint={manifest_fingerprint}`.
  • `alias_layout_policy_v1`: **no partition tokens**; selection is by the **exact S0-sealed path** (and digest).
  • Optional pins: as declared above (all-or-none).
* **Path↔embed equality** MUST hold for S1 outputs; token expansion follows the Dictionary exactly.

### 4.5 Input field & key expectations

* S1 **MUST NOT** invent or rename keys. Merchant/site keys are taken from `site_locations` per their anchor.
* Columns referenced by `alias_layout_policy_v1.weight_source` (and related transforms) **MUST** exist; absence is an error.
* Any derived value used in weighting **MUST** be a deterministic transform of sealed columns per policy (no stochastic or data-dependent randomness).

### 4.6 Trust boundary & sequencing

* S1 **operates only after** a valid S0 receipt exists for the target fingerprint.
* Read order: resolve policy and inputs → group by merchant → process; no reads outside the sealed set.

---

## 5. **Outputs (datasets) & identity (Binding)**

### 5.1 Product (ID)

* **ID:** `s1_site_weights` — per-merchant, per-site **frozen probability law** used by all downstream routing in 2B.

### 5.2 Identity & partitions

* **Run identity:** `{ seed, manifest_fingerprint }`.
* **Partitions (binding):** `[seed, fingerprint]`. No additional partition tokens are permitted.
* **Path↔embed equality:** Any embedded `manifest_fingerprint` field in this dataset **MUST** byte-equal the `fingerprint=` path token.

### 5.3 Path family, format & authority

* **Dictionary binding (required):**
  `data/layer1/2B/s1_site_weights/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
  (Dictionary is the **sole** authority for IDs → path/partitions/format.) 
* **Storage format:** `parquet` (Dictionary authority). 

### 5.4 Shape & schema anchor

* **Shape authority:** `schemas.2B.yaml#/plan/s1_site_weights` (fields-strict).
  This anchor (owned by the schema pack) fixes **PK**, required columns, and domains; this spec **does not** restate columns beyond provenance signals below. 

### 5.5 Keys, writer order & order posture

* **Primary key (PK):** `[merchant_id, legal_country_iso, site_order]` (schema-owned).
* **Writer order:** **exactly** the PK order; file order is non-authoritative.
* **Order-free read:** Consumers MUST treat file order as non-authoritative; merge/join discipline follows the PK.

### 5.6 Required provenance signals (owned by the schema anchor)

* `p_weight` (probability), policy-declared `weight_source`, `quantised_bits`, `floor_applied` (boolean), and `created_utc`.
* **Creation time:** `created_utc` **MUST** equal the canonical S0 time for this fingerprint (the S0 receipt’s `verified_at_utc`). 

### 5.7 Coverage & FK discipline

* **Coverage:** 1:1 with `site_locations` keys for this `{seed, fingerprint}`; every `(merchant_id, legal_country_iso, site_order)` appearing in `site_locations` **MUST** appear exactly once in `s1_site_weights`. (FK membership is enforced by the schema/validators.)
* **No new keys:** S1 MUST NOT introduce keys that do not exist in `site_locations`@`seed, fingerprint`. 

### 5.8 Write-once, immutability & idempotency

* **Single-writer, write-once:** Target partition MUST be empty before first publish.
* **Idempotent re-emit:** Re-publishing to the same partition is allowed **only** if bytes are **bit-identical**; otherwise **Abort**.
* **Atomic publish:** Stage → fsync → single atomic move into the final partition (no partial files visible).

### 5.9 Downstream visibility & reliance

* `s1_site_weights` is the **only** authoritative weight surface for 2B; S2–S6 MUST NOT recompute or derive alternate long-run weights.
* Downstreams MUST **select by** `(seed, fingerprint)` via the Dictionary and rely on the schema anchor for shape; they MUST NOT assume any ordering beyond the PK. 

---

## 6. **Dataset shapes & schema anchors (Binding)**

### 6.1 Shape authority

**JSON-Schema is the sole shape authority.** Shapes live in the **2B schema pack** (`schemas.2B.yaml`), are **fields-strict** (no extra columns), and bind PK/partitions/writer-sort and domains. The **Dataset Dictionary** binds IDs → path families, partitions, and storage formats; the **Artefact Registry** carries ownership/licence/retention only. 

---

### 6.2 Output table — `s1_site_weights` *(plan)*

**ID → Schema:** `schemas.2B.yaml#/plan/s1_site_weights` (**columns_strict: true**).
This state requires the schema pack to expose this anchor; the anchor owns the exact column list, types, domains, PK and partitions. 

**Identity & keys (binding):**

* **PK:** `[merchant_id, legal_country_iso, site_order]` (site identity carried over from 1B).
* **Partitions:** `[seed, fingerprint]` (no additional tokens).
* **Writer order:** exactly the PK order; file order remains non-authoritative.

**Required provenance (owned by the anchor):**

* `p_weight` (probability), `weight_source` (policy-declared), `quantised_bits` (int), `floor_applied` (boolean), `created_utc`.
* `created_utc` **equals** the canonical time from S0’s receipt (`verified_at_utc`) for this fingerprint; timestamp typing reuses the layer pack’s RFC-3339 microseconds definition.

**Domain constraints (shape-level):**

* `0 ≤ p_weight ≤ 1`.
* Per-merchant Σ `p_weight` = 1 within the policy’s normalisation tolerance (the tolerance symbol lives in the policy; the anchor enforces type/domain).
* `quantised_bits` conforms to the bit-depth declared by policy.

**Catalogue binding (Dictionary authority):**
The **Dataset Dictionary** binds `s1_site_weights` to its path family and format and **must** partition by `[seed, fingerprint]`. (Do not write via literal paths.) 

---

### 6.3 Referenced input & policy anchors (read-only)

* **`site_locations`** — `schemas.1B.yaml#/egress/site_locations` (seed+fingerprint egress from 1B; final-in-layer). S1 reads keys and policy-referenced fields only. 
* **`alias_layout_policy_v1`** — `schemas.2B.yaml#/policy/alias_layout_policy_v1` (declares weight source, floors/caps, ε/ε_q tolerances, bit-depth, and required provenance flags). 

*(If S0 sealed optional pins for this fingerprint, they remain read-only context: `schemas.2A.yaml#/egress/site_timezones`, `schemas.2A.yaml#/cache/tz_timetable_cache`.)* 

---

### 6.4 Common definitions (schema packs)

* **Layer/segment defs:** use `$defs.hex64` and `partition_kv` from the 2B pack; reuse the layer’s `rfc3339_micros` for timestamps referenced via S0. 

---

### 6.5 Format & storage (Dictionary authority)

* **Format:** bound by the Dictionary for `s1_site_weights` (Parquet is expected for plan/egress tables in this programme).
* **Write posture:** single-writer, write-once per `(seed, fingerprint)`; atomic publish; **path↔embed equality** must hold where lineage is embedded (Dictionary governs path tokens). 

---

### 6.6 Order & merge discipline

* **Order-free read:** consumers MUST treat file order as non-authoritative; join/merge by PK only.
* **No merges/appends:** updates to `s1_site_weights` require a new partition identity; no record-level mutations.

---

## 7. **Deterministic algorithm (RNG-free) (Binding)**

**Overview.** S1 performs a fixed, reproducible transform from catalogued inputs to a byte-stable `s1_site_weights` table. There are **no random draws** and **no network I/O**. Arithmetic follows the programme’s numeric discipline (binary64, round-to-nearest-even), with stable serial reduction and explicit tie-break rules.

### 7.1 Resolve & sanity

1. **Verify S0 evidence exists** for this `manifest_fingerprint`.
2. **Resolve inputs by Dictionary IDs only:** `site_locations@{seed,fingerprint}`, `alias_layout_policy_v1` (and both optional pins iff S0 sealed both).
3. **Assert required policy entries** are present (weight source, floor/cap spec, `normalisation_epsilon` = ε, `quantised_bits` = b, `quantisation_epsilon` = ε_q, required provenance flags). **Abort** if missing.
4. **Discover canonical `created_utc`** from S0’s receipt; S1 SHALL echo this timestamp in its output rows.

### 7.2 Grouping & key order

5. **Group by merchant** using the site key carried from `site_locations` (PK: `merchant_id, legal_country_iso, site_order`).
6. **Within each merchant**, process sites in **deterministic PK order**; all reductions and tie-breaks use this order.

### 7.3 Base weight extraction (deterministic)

7. **Select the base series** declared by policy: `w_i ← policy.weight_source(site_locations row i)` (either a named column or a policy-defined pure function of sealed columns).
8. **Validate domain:** each `w_i` MUST be finite and ≥ 0. **Abort** on `NaN`/`±Inf`/negative.
9. **Zero-mass check:** compute `W0 = Σ w_i` in stable serial order. (No parallel reductions.)

### 7.4 Floor / cap application (policy)

10. **Apply floor/cap** per policy to obtain `u_i` from `w_i`. Examples (policy chooses the law):

* **Absolute floor:** `u_i = max(w_i, f_abs)`.
* **Relative floor:** `u_i = max(w_i, f_rel · max_j w_j)`.
* **Cap (optional):** `u_i = min(u_i, c_abs|c_rel)`.

11. **Record floor flag:** set `floor_applied = true` for any row where the floor changed `w_i` (cap application does not affect this flag).
12. **Zero-effective-mass fallback:** compute `U0 = Σ u_i`. If `U0 ≤ 0`, apply the **policy fallback** (e.g., **uniform within the merchant’s site set**): `u_i ← 1/K` for K sites; set `floor_applied = true` for all rows in this merchant.

### 7.5 Normalisation (exact within ε)

13. **Normalise per merchant:** `p_i = u_i / Σ u_i` using the **serially computed** denominator.
14. **Check mass:** Enforce `| (Σ p_i) − 1 | ≤ ε` (policy’s `normalisation_epsilon`). **Abort** if violated.
15. **Clamp tiny negatives to zero** only if `−ε ≤ p_i < 0`; otherwise **Abort**. After any clamp, re-normalise once to restore mass (still within ε). (Clamps set `floor_applied = true`.)

### 7.6 Quantisation (grid; deterministic ties)

16. **Bit-depth:** let `b = policy.quantised_bits` (integer ≥ 1). Define grid **G = 2^b**.
17. **Scale & round to integers:** `m_i* = p_i · G`. Compute integers `m_i = round_half_to_even(m_i*)` (ties-to-even).
18. **Mass adjust to exact G:** let `Δ = G − Σ m_i`.

* If `Δ = 0`, keep `m_i`.
* If `Δ > 0` (deficit): give **+1** to the `Δ` rows with **largest** fractional remainders of `m_i* − floor(m_i*)`.
* If `Δ < 0` (surplus): take **−1** from the `|Δ|` rows with **smallest** fractional remainders.
* **Tie-break** deterministically by PK order.
  Resulting integers satisfy `Σ m_i = G`.

19. **Quantisation coherence check:** decoded weights `p̂_i = m_i / G` must satisfy `| (Σ p̂_i) − 1 | = 0` and `|p̂_i − p_i| ≤ ε_q` (policy’s `quantisation_epsilon`) per row. **Abort** if violated.
20. **Record bit-depth:** write `quantised_bits = b` in every output row.

> **Note:** The quantised integers `m_i` are an **implementation detail** for S1; they need not be persisted in `s1_site_weights`. S2 SHALL recompute them from `p_weight` and `b` using the same law.

### 7.7 Provenance & stamping

21. **Provenance fields:**

* `p_weight ← p_i` (post-normalisation, pre-quantisation real weight).
* `weight_source ← policy.weight_source` (string ID).
* `quantised_bits ← b`; `floor_applied ← {true|false}`.
* `created_utc ← S0.verified_at_utc`.

22. **Writer order:** emit rows in **PK order** only.

### 7.8 Output write & immutability

23. **Partition target:** `s1_site_weights@seed={seed}/fingerprint={manifest_fingerprint}` from the Dictionary.
24. **Write-once:** target must be empty; otherwise **Abort**, unless the existing bytes are **bit-identical** (idempotent re-emit).
25. **Atomic publish:** stage → fsync → atomic move; then re-open to assert **path↔embed equality**.

### 7.9 Prohibitions & determinism guards

26. **No RNG; no network.**
27. **No literal paths; no extra inputs** beyond those resolved in §7.1.
28. **Stable arithmetic:** binary64; no FMA; no re-ordering of reductions; no data-dependent branching that changes numeric order across runs.
29. **Reproducibility:** reruns with the same sealed inputs (including identical policy bytes) **MUST** produce byte-identical output.

---

## 8. **Identity, partitions, ordering & merge discipline (Binding)**

### 8.1 Identity law

* **Run identity:** `{ seed, manifest_fingerprint }` is fixed at state start.
* **Output identity:** `s1_site_weights` **MUST** be identified and selected by **both** tokens.

### 8.2 Partitions & selection

* **Partitioning (write):** `…/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/`.
* **Exact selection (read/write):** no wildcards, ranges, or multi-partition writes; a single `(seed,fingerprint)` partition per publish.

### 8.3 Path↔embed equality

* Any embedded `manifest_fingerprint` (and, if echoed, `seed`) in the dataset **MUST** byte-equal the corresponding path tokens. Inequality is an error.

### 8.4 Writer order & file-order posture

* **Writer order:** rows **MUST** be emitted in **PK order** `[merchant_id, legal_country_iso, site_order]`.
* **Order-free read:** consumers **MUST** treat file order as non-authoritative; joins/merges are by PK only.

### 8.5 Single-writer, write-once

* Target partition **MUST** be empty before first publish.
* If the target exists:

  * **Byte-identical:** treat as a no-op (idempotent re-emit).
  * **Byte-different:** **Abort** with immutable-overwrite error.

### 8.6 Atomic publish

* Write to a same-filesystem **staging** location, fsync, then **atomic rename** into the final partition. No partial files may become visible.

### 8.7 Concurrency

* At most **one** active publisher per `(component=2B.S1, seed, manifest_fingerprint)`.
* A concurrent publisher **MUST** either observe existing byte-identical artefacts and no-op, or abort on attempted overwrite.

### 8.8 Merge discipline

* **No appends, compactions, or in-place updates.** Any change requires publishing to a **new** `(seed,fingerprint)` identity or a new fingerprint under the programme’s change-control rules.

### 8.9 Determinism & replay

* Re-running S1 with identical sealed inputs (including identical policy bytes) **MUST** reproduce **bit-identical** output.
* Arithmetic and grouping order **MUST NOT** depend on thread scheduling or data-dependent branching that would alter reduction order.

### 8.10 Token hygiene

* Partition tokens **MUST** appear exactly once and in the declared order: `seed=…/fingerprint=…/`.
* Literal paths, env-injected overrides, or ad-hoc globbing are prohibited.

### 8.11 Provenance echo

* `created_utc` **MUST** equal the canonical `verified_at_utc` from S0 for this fingerprint.
* Any policy identifiers/digests echoed in metadata **MUST** match those sealed by S0 for this fingerprint.

### 8.12 Retention & ownership

* Retention, licence, and ownership are governed by the Registry; immutability is enforced by this section.

---

## 9. **Acceptance criteria (validators) (Binding)**

**Outcome rule.** **PASS** iff all **Abort** validators succeed. **WARN** validators may fail without blocking publish but MUST be recorded in the run-report.

**V-01 — Prior gate evidence present (Abort).**
` s0_gate_receipt_2B` exists for the target `manifest_fingerprint` and is discoverable via the Dictionary.

**V-02 — Dictionary-only resolution (Abort).**
All inputs (`site_locations`, `alias_layout_policy_v1`, optional pins if used) were resolved by **Dictionary IDs**; zero literal paths.

**V-03 — Partition selection exact (Abort).**
Reads used only `site_locations@seed={seed}/fingerprint={manifest_fingerprint}` and the **exact S0-sealed path** for `alias_layout_policy_v1` (no partition tokens). For optional pins (if present), use the exact partitions declared here.

**V-04 — Policy shape & minima present (Abort).**
`alias_layout_policy_v1` provides at least: `weight_source`, `floor_spec`, `normalisation_epsilon` (= ε), `quantised_bits` (= b), `quantisation_epsilon` (= ε_q), and the required provenance flags.

**V-05 — Output shape valid (Abort).**
` s1_site_weights` validates against `schemas.2B.yaml#/plan/s1_site_weights` (fields-strict).

**V-06 — PK uniqueness (Abort).**
No duplicate `(merchant_id, legal_country_iso, site_order)` in `s1_site_weights`.

**V-07 — Writer order = PK (Abort).**
Row emission order is exactly the PK order.

**V-08 — Coverage 1:1 with `site_locations` (Abort).**
Set of keys in `s1_site_weights` equals the set of keys in `site_locations` for this `{seed, fingerprint}` (no missing, no extras).

**V-09 — `p_weight` domain (Abort).**
Every `p_weight` is finite and `0 ≤ p_weight ≤ 1`.

**V-10 — Normalisation within ε (Abort).**
For each merchant, `| Σ_i p_weight_i − 1 | ≤ ε` where ε = `normalisation_epsilon` from policy.

**V-11 — Quantised bit-depth constant & policy-coherent (Abort).**
All rows have `quantised_bits = b`, and `b` equals the policy’s declared `quantised_bits`.

**V-12 — Quantisation coherence within ε_q (Abort).**
Reproduce quantisation with grid `G = 2^b` from the policy:
`m_i* = p_weight_i · G` → ties-to-even → mass-adjust to Σ `m_i = G` → `p̂_i = m_i / G`.
Require for every row `|p̂_i − p_weight_i| ≤ ε_q` and for every merchant `Σ_i p̂_i = 1` exactly.

**V-13 — Floor/fallback provenance (Abort).**
Where the policy’s **zero-mass fallback** applies (e.g., uniform over K sites), `s1_site_weights` shows `p_weight_i = 1/K` for the merchant and `floor_applied = true` for all its rows.
If the policy declares a **floor**, rows that fell below the floor per `weight_source` MUST have `floor_applied = true`.

**V-14 — `weight_source` provenance (Abort).**
Column `weight_source` in every row equals the policy’s `weight_source` identifier.

**V-15 — Creation time canonical (Abort).**
`created_utc` in every row equals the S0 receipt’s `verified_at_utc` for this fingerprint.

**V-16 — Path↔embed equality (Abort).**
Any embedded `manifest_fingerprint` (and, if echoed, `seed`) equals the dataset’s path tokens.

**V-17 — Write-once immutability (Abort).**
Target partition was empty before publish, or existing bytes are bit-identical.

**V-18 — Idempotent re-emit (Abort).**
Re-running S1 with identical sealed inputs reproduces **byte-identical** output; otherwise abort rather than overwrite.

**V-19 — No network & no extra reads (Abort).**
Execution performed with network I/O disabled and only accessed assets listed in S0’s `sealed_inputs_2B` for this fingerprint.

**V-20 — Optional pins all-or-none (Warn).**
If one of `{site_timezones, tz_timetable_cache}` is present for this fingerprint, both are present; otherwise neither.

---

## 10. **Failure modes & canonical error codes (Binding)**

**Code namespace.** `2B-S1-XYZ` where `XYZ` is a zero-padded integer. **Severity** ∈ {**Abort**, **Warn**}.
Each failure **MUST** be logged with: `code`, `severity`, `message`, `fingerprint`, `seed`, and a `context{}` object (keys noted below).

### 10.1 Gate & catalogue discipline

* **2B-S1-001 S0_RECEIPT_MISSING (Abort)** — No `s0_gate_receipt_2B` found for the target fingerprint.
  *Context:* `fingerprint`.

* **2B-S1-020 DICTIONARY_RESOLUTION_ERROR (Abort)** — Input ID could not be resolved for the required partition(s).
  *Context:* `id`, `expected_partition`.

* **2B-S1-021 PROHIBITED_LITERAL_PATH (Abort)** — Attempted read/write via a literal path (not Dictionary-resolved).
  *Context:* `path`.

* **2B-S1-022 UNDECLARED_ASSET_ACCESSED (Abort)** — Asset was accessed but is absent from S0’s `sealed_inputs_2B`.
  *Context:* `id|path`.

* **2B-S1-023 NETWORK_IO_ATTEMPT (Abort)** — Network I/O detected.
  *Context:* `endpoint`.

### 10.2 Policy shape & requirements

* **2B-S1-031 POLICY_SCHEMA_INVALID (Abort)** — `alias_layout_policy_v1` fails schema/parse.
  *Context:* `schema_errors[]`.

* **2B-S1-032 POLICY_MINIMA_MISSING (Abort)** — Required policy entries absent (e.g., `weight_source`, `floor_spec`, `normalisation_epsilon`, `quantised_bits`, `quantisation_epsilon`).
  *Context:* `missing_keys[]`.

* **2B-S1-033 POLICY_REFERS_UNKNOWN_COLUMN (Abort)** — `weight_source` (or declared transform) references a non-existent column in `site_locations`.
  *Context:* `weight_source`, `missing_columns[]`.

### 10.3 Output shape & key coverage

* **2B-S1-040 OUTPUT_SCHEMA_INVALID (Abort)** — `s1_site_weights` fails its schema anchor.
  *Context:* `schema_errors[]`.

* **2B-S1-041 PK_DUPLICATE (Abort)** — Duplicate `(merchant_id, legal_country_iso, site_order)`.
  *Context:* `key`.

* **2B-S1-042 COVERAGE_MISMATCH (Abort)** — Keys missing/extra vs `site_locations` for this `{seed,fingerprint}`.
  *Context:* `missing_keys[]`, `extra_keys[]`.

* **2B-S1-083 WRITER_ORDER_NOT_PK (Abort)** — Row emission order differs from PK order.
  *Context:* `first_offending_row_index`.

### 10.4 Domain, normalisation & quantisation

* **2B-S1-050 INVALID_BASE_WEIGHT (Abort)** — Negative, `NaN`, or `±Inf` encountered in base weights.
  *Context:* `merchant_id`, `site_order`, `value`.

* **2B-S1-051 NORMALISATION_FAILED (Abort)** — Per-merchant `|Σ p_weight − 1| > ε` (policy `normalisation_epsilon`).
  *Context:* `merchant_id`, `sum`, `epsilon`.

* **2B-S1-057 P_WEIGHT_OUT_OF_RANGE (Abort)** — Any `p_weight` is outside `[0,1]`.
  *Context:* `merchant_id`, `site_order`, `value`.

* **2B-S1-058 BIT_DEPTH_MISMATCH (Abort)** — `quantised_bits` not constant or ≠ policy bit-depth.
  *Context:* `expected_bits`, `observed_bits[]`.

* **2B-S1-052 QUANTISATION_INCOHERENT (Abort)** — Reconstructed `p̂_i` from grid `2^b` violates per-row `ε_q` or per-merchant Σ `p̂_i ≠ 1`.
  *Context:* `merchant_id`, `epsilon_q`, `offending_sites[]`.

* **2B-S1-053 ZERO_MASS_FALLBACK_MISAPPLIED (Abort)** — Policy fallback (e.g., uniform) not applied when required or applied inconsistently.
  *Context:* `merchant_id`, `K`, `observed_distribution_sample[]`.

* **2B-S1-054 FLOOR_FLAG_INCOHERENT (Abort)** — `floor_applied` flags don’t reflect floor/fallback semantics.
  *Context:* `merchant_id`, `site_order`.

* **2B-S1-055 WEIGHT_SOURCE_MISMATCH (Abort)** — `weight_source` column value ≠ policy identifier.
  *Context:* `expected`, `observed`.

* **2B-S1-056 CREATED_UTC_MISMATCH (Abort)** — `created_utc` ≠ S0 `verified_at_utc` for this fingerprint.
  *Context:* `created_utc`, `verified_at_utc`.

### 10.5 Identity, partitions & immutability

* **2B-S1-070 PARTITION_SELECTION_INCORRECT (Abort)** — Read/write didn’t target exactly `seed={seed}/fingerprint={fingerprint}` (or fingerprint-only for policies).
  *Context:* `id`, `expected_partition`, `actual_partition`.

* **2B-S1-071 PATH_EMBED_MISMATCH (Abort)** — Embedded identity differs from path token(s).
  *Context:* `embedded`, `path_token`.

* **2B-S1-080 IMMUTABLE_OVERWRITE (Abort)** — Target partition not empty and bytes differ.
  *Context:* `target_path`.

* **2B-S1-081 NON_IDEMPOTENT_REEMIT (Abort)** — Re-emit produced byte-different output for identical inputs.
  *Context:* `digest_prev`, `digest_now`.

* **2B-S1-082 ATOMIC_PUBLISH_FAILED (Abort)** — Staging/rename not atomic or verification failed post-publish.
  *Context:* `staging_path`, `final_path`.

### 10.6 Optional pins & WARN class

* **2B-S1-090 OPTIONAL_PINS_MIXED (Warn)** — Exactly one of `{site_timezones, tz_timetable_cache}` present for this fingerprint.
  *Context:* `present_ids[]`, `absent_ids[]`.

### 10.7 Standard message fields (Binding)

Every failure log entry **MUST** include:
`code`, `severity`, `message`, `fingerprint`, `seed`, `context{…}`, and `validator` (e.g., `"V-10"`), or `"runtime"` if not tied to a validator.

### 10.8 Validator → code map (Binding)

| Validator                                  | Canonical codes (may emit multiple) |
|--------------------------------------------|-------------------------------------|
| **V-01 Prior gate evidence present**       | 2B-S1-001                           |
| **V-02 Dictionary-only resolution**        | 2B-S1-020, 2B-S1-021                |
| **V-03 Partition selection exact**         | 2B-S1-070                           |
| **V-04 Policy shape & minima present**     | 2B-S1-031, 2B-S1-032, 2B-S1-033     |
| **V-05 Output shape valid**                | 2B-S1-040                           |
| **V-06 PK uniqueness**                     | 2B-S1-041                           |
| **V-07 Writer order = PK**                 | 2B-S1-083                           |
| **V-08 Coverage 1:1**                      | 2B-S1-042                           |
| **V-09 `p_weight` domain**                 | 2B-S1-057, 2B-S1-050                |
| **V-10 Normalisation within ε**            | 2B-S1-051                           |
| **V-11 Bit-depth constant & policy**       | 2B-S1-058                           |
| **V-12 Quantisation coherence within ε_q** | 2B-S1-052                           |
| **V-13 Floor/fallback provenance**         | 2B-S1-053, 2B-S1-054                |
| **V-14 `weight_source` provenance**        | 2B-S1-055                           |
| **V-15 Creation time canonical**           | 2B-S1-056                           |
| **V-16 Path↔embed equality**               | 2B-S1-071                           |
| **V-17 Write-once immutability**           | 2B-S1-080                           |
| **V-18 Idempotent re-emit**                | 2B-S1-081                           |
| **V-19 No network & no extra reads**       | 2B-S1-023, 2B-S1-022, 2B-S1-021     |
| **V-20 Optional pins all-or-none**         | 2B-S1-090 *(Warn)*                  |

---

## 11. **Observability & run-report (Binding)**

### 11.1 Purpose

Emit a **single structured run-report** that proves what S1 read, how it transformed, and what it published. The run-report is **diagnostic (non-authoritative)**; the **dataset** `s1_site_weights` remains the source of truth for consumers.

### 11.2 Emission

* S1 **MUST** write the run-report to **STDOUT** as a single JSON document on successful publish (and on abort, if possible).
* S1 **MAY** persist the same JSON to an implementation-defined log. Persisted copies **MUST NOT** be used by downstream contracts.

### 11.3 Top-level shape (fields-strict)

A run-report **MUST** contain the following top-level fields:

* `component`: `"2B.S1"`
* `fingerprint`: `<hex64>`
* `seed`: `<string>`
* `created_utc`: ISO-8601 UTC (echo of S0 `verified_at_utc`)
* `catalogue_resolution`: `{ dictionary_version: <semver>, registry_version: <semver> }`
* `policy`:

  * `id`: `"alias_layout_policy_v1"`
  * `version_tag`: `<string>`
  * `sha256_hex`: `<hex64>`
  * `quantised_bits`: `<int>` *(b)*
  * `normalisation_epsilon`: `<float>` *(ε)*
  * `quantisation_epsilon`: `<float>` *(ε_q)*
* `inputs_summary`:

  * `site_locations_path`: `<string>` *(Dictionary-resolved)*
  * `merchants_total`: `<int>`
  * `sites_total`: `<int>`
* `transforms`:

  * `floors_applied_rows`: `<int>`
  * `caps_applied_rows`: `<int>`
  * `zero_mass_fallback_merchants`: `<int>`
  * `tiny_negative_clamps`: `<int>` *(rows clamped to 0 then re-normalised)*
* `normalisation`:

  * `max_abs_mass_error_pre_quant`: `<float>` *(max over merchants of |Σ p − 1| before quantisation)*
  * `merchants_over_epsilon`: `<int>` *(should be 0)*
* `quantisation`:

  * `grid_bits`: `<int>` *(= b)*
  * `grid_size`: `<int>` *(= 2^b)*
  * `max_abs_delta_per_row`: `<float>` *(max |p̂ − p| over all rows)*
  * `merchants_mass_exact_after_quant`: `<int>` *(should equal merchants_total)*
* `publish`:

  * `target_path`: `<string>` *(Dictionary-resolved path to `s1_site_weights`)*
  * `bytes_written`: `<int>`
  * `write_once_verified`: `<bool>`
  * `atomic_publish`: `<bool>`
* `validators`: `[ { id: "V-01", status: "PASS|FAIL|WARN", codes: [ "2B-S1-0XX", … ] }, … ]`
* `summary`: `{ overall_status: "PASS|FAIL", warn_count: <int>, fail_count: <int> }`
* `environment`: `{ engine_commit?: <string>, python_version: <string>, platform: <string>, network_io_detected: <int> }`

### 11.4 Evidence & samples (bounded)

S1 **MUST** include bounded, deterministic samples that allow offline verification without scanning the full dataset:

* `samples.key_coverage`: up to **20** `(merchant_id, legal_country_iso, site_order)` keys that appear in `site_locations` and their presence indicator in `s1_site_weights` (deterministic pick: lexicographic by PK, first N).
* `samples.normalisation`: up to **20** merchants with `{ merchant_id, sites: <int>, sum_p: <float>, abs_error: <float> }` (deterministic pick: largest absolute error first, then merchant_id).
* `samples.extremes`: top **10** and bottom **10** `p_weight` rows with `{ key, p_weight }` (deterministic ordering: p desc/asc then PK).
* `samples.quantisation`: up to **20** rows with `{ key, p_weight, p_hat, abs_delta }` (deterministic pick: largest `abs_delta` first, then PK).

All sample values **MUST** be copied from authoritative artefacts; no re-computation beyond the algorithm in this spec.

### 11.5 Counters (minimum set)

S1 **MUST** emit at least the following integer counters:

* `merchants_total`, `sites_total`
* `floors_applied_rows`, `caps_applied_rows`, `zero_mass_fallback_merchants`, `tiny_negative_clamps`
* `publish_bytes_total` *(sum across files in the partition)*
* Durations (milliseconds): `resolve_ms`, `transform_ms`, `normalise_ms`, `quantise_ms`, `publish_ms`

### 11.6 Histograms / distributions (optional, bounded)

If emitted, histograms **MUST** be bounded in size and deterministic in binning:

* `hist.p_weight`: fixed bins over `[0,1]` (e.g., 20 equal-width bins) with counts.
* `hist.abs_delta_quant`: fixed bins over `[0, ε_q]` with counts.

### 11.7 Determinism of lists

Arrays in the run-report **MUST** be emitted in deterministic order:

* `validators`: sorted by validator ID (`"V-01"` …).
* `samples.*`: as defined per sample set above.
* Any lists of IDs/digests: lexicographic by ID with 1:1 alignment to digest lists.

### 11.8 PASS/WARN/FAIL semantics

* `overall_status = "PASS"` iff **all Abort-class validators** succeeded.
* WARN-class validator failures increment `warn_count` and **MUST** appear in `validators[]` with `status: "WARN"`.
* On any Abort-class failure, `overall_status = "FAIL"`; publish **MUST NOT** occur, but an attempted run-report **SHOULD** still be emitted with partial data when safe.

### 11.9 Privacy & retention

* The run-report **MUST NOT** contain raw data bytes; only keys, paths, counts, digests, and derived metrics.
* Retention is governed by the Registry’s diagnostic-log policy; the run-report is not an authoritative artefact and **MUST NOT** be hashed into any bundle.

### 11.10 ID-to-artifact echo

For traceability, S1 **MUST** echo an `id_map` array of the exact Dictionary-resolved paths used:

```
id_map: [
  { id: "site_locations",        path: "<…/site_locations/seed=…/fingerprint=…/>" },
  { id: "alias_layout_policy_v1", path: "<…/config/layer1/2B/policy/alias_layout_policy_v1.json>" },
  { id: "s1_site_weights",        path: "<…/s1_site_weights/seed=…/fingerprint=…/>" }
]
```

Paths **MUST** match those actually resolved at runtime.

---

## 12. **Performance & scalability (Informative)**

### 12.1 Workload model & symbols

Let:

* **M** = merchants, **Kᵢ** = sites for merchant *i*, **S = Σᵢ Kᵢ** (total sites).
* **b** = quantisation bit-depth; **G = 2ᵇ**.
* **ε**, **ε_q** = normalisation / quantisation tolerances from policy.

S1 is a single pass transform over **S** rows plus a per-merchant normalise+quantise.

---

### 12.2 Time characteristics

* **Transform path:** `O(S)` for base-weight extraction, floors/caps, normalisation, quantisation, provenance stamp.
* **Ordering cost:** If `site_locations` is not pre-grouped by merchant/PK, perform a **deterministic external sort** by PK → **O(S log S)** comparison cost with streaming I/O. If the input is pre-grouped, S1 remains **O(S)**.
* **Quantisation:** per merchant `O(Kᵢ)`; the deficit/surplus adjustment uses a deterministic pass over fractional remainders (stable tie-break by PK).

---

### 12.3 Memory footprint

* **Working set:** `O(max Kᵢ)` (only one merchant’s window in memory at a time) if input is grouped; otherwise use an external sort with bounded memory.
* **Policy bytes:** negligible (read once).
* **Output buffer:** writer emits in PK order; row groups can be flushed incrementally.

---

### 12.4 I/O discipline

* **Reads:** one sequential scan of `site_locations@{seed,fingerprint}`; small policy read.
* **Writes:** one partition for `s1_site_weights@{seed,fingerprint}`; write-once + atomic publish.
* **Parquet tuning (non-binding guidance):** pick a row-group size that keeps a typical merchant within a few groups; avoid excessive tiny groups that hurt downstream scans.

---

### 12.5 Parallelism (safe patterns)

* **Across merchants:** embarrassingly parallel if each worker owns a **disjoint, deterministic shard** of merchants and emits to **private staging**, followed by a deterministic concatenate in PK order before the single atomic publish.
* **Within a merchant:** keep **serial reductions** (mass sums) to preserve numeric order; avoid parallel floating-point reductions.
* **Forbidden:** concurrent writers to the same `{seed,fingerprint}` partition; any parallelism that changes PK order or reduction order.

---

### 12.6 Numeric determinism guardrails

* **Arithmetic:** binary64, round-to-nearest-even; no FMA; no FTZ/DAZ; no data-dependent re-ordering.
* **Reductions:** compute Σ in **stable serial order**; re-normalise once after any clamps.
* **Quantisation:** compute `mᵢ* = pᵢ·G`, ties-to-even, then deficit/surplus adjustment with **PK-ordered** tie-breaks. This yields identical bytes across platforms.

---

### 12.7 Throughput tips (non-binding)

* **Feature access:** pre-project the exact columns needed by `weight_source` to reduce scan width.
* **Fallback fast-path:** when all `wᵢ` already satisfy floors and Σ≈1, S1 skips cap/floor flags and does a single normalise + quantise.
* **Remainder pass:** keep `(frac, PK_index)` pairs in a small in-memory array per merchant for the Δ-adjustment; stable partition avoids full sort.

---

### 12.8 Scale limits & mitigations

* **Very large merchants (high `Kᵢ`):** stream in chunks but keep **PK order**; if chunking breaks PK order, perform a deterministic local merge before emit.
* **Huge S:** rely on external sort (if needed) with fixed chunk size and deterministic merge fan-in; spills go to a dedicated temp area on the same filesystem to keep atomic rename cheap.

---

### 12.9 Observability KPIs (suggested)

Track and alert on:

* `merchants_total`, `sites_total`, `floors_applied_rows`, `zero_mass_fallback_merchants`, `tiny_negative_clamps`.
* `max_abs_mass_error_pre_quant` (should be ≤ **ε**), `max_abs_delta_per_row` (≤ **ε_q**).
* Timing: `resolve_ms`, `transform_ms`, `normalise_ms`, `quantise_ms`, `publish_ms`.
* Output size (`bytes_written`) and row-group count.

---

### 12.10 Non-goals

* No network I/O, compression fiddling, or probabilistic sampling in S1.
* No record-level updates/merges post-publish; any change requires a new `{seed,fingerprint}` or a new fingerprint per change control.

---

## 13. **Change control & compatibility (Binding)**

### 13.1 Scope

This section governs permitted changes to **2B.S1** after ratification and how those changes are versioned and rolled out. It applies to: the **procedure**, the **output dataset** `s1_site_weights`, the **normalisation & quantisation law**, required **provenance fields**, and **validators/error codes**.

---

### 13.2 Stable, non-negotiable surfaces (unchanged without a **major** bump)

S1 **MUST NOT** change the following within the same major version:

* **Output identity & partitions:** dataset ID `s1_site_weights`; partitions `[seed, fingerprint]`; **path↔embed equality**; write-once + atomic publish.
* **PK & keys:** primary key `[merchant_id, legal_country_iso, site_order]`; no new keys; 1:1 coverage with `site_locations`.
* **Deterministic posture:** S1 is **RNG-free**; no network I/O; Dictionary-only resolution.
* **Normalisation law:** per-merchant Σ `p_weight` = 1 (within policy ε), serial reductions, numeric guardrails (binary64, ties-to-even where applicable).
* **Quantisation law:** grid `G = 2^b`; scale → round half-to-even → deterministic Δ adjustment by fractional remainder with PK tiebreak; coherence checks (per-row ≤ ε_q; per-merchant Σ exact).
* **Provenance signals:** presence and meaning of `p_weight`, `weight_source`, `quantised_bits`, `floor_applied`, `created_utc`.
* **Acceptance posture:** the set of **Abort** validators (by ID) and their semantics.

Any change here is **breaking** and requires a **new major** of this spec and schema anchors.

---

### 13.3 Backward-compatible changes (allowed with **minor** or **patch** bump)

* **Editorial clarifications** and examples that do not change behaviour. *(patch)*
* **Run-report** additions (new counters/samples/histograms); run-report is non-authoritative. *(minor/patch)*
* **Optional metadata columns** in `s1_site_weights` that validators ignore and consumers are not required to read. *(minor)*
* **Validator diagnostics**: add **WARN-class** checks; refine messages/contexts without altering PASS/FAIL criteria. *(minor)*
* **Policy surface extension** in `alias_layout_policy_v1` that remains optional (e.g., allowing a new floor mode while preserving defaults). *(minor)*

---

### 13.4 Breaking changes (require **major** bump + migration)

* Changing the **PK**, partitions, or dataset ID of `s1_site_weights`.
* Altering the **normalisation or quantisation law** (e.g., different rounding mode, different Δ adjustment order).
* Removing or changing semantics of required **provenance fields**.
* Reclassifying a **WARN** validator to **Abort**, or adding a **new Abort** validator that can fail for previously valid outputs.
* Allowing **literal paths** or **network I/O**, or removing Dictionary-only resolution.
* Changing acceptance so that coverage is no longer 1:1 with `site_locations`.

---

### 13.5 SemVer & release discipline

* **Major:** changes listed in §13.4 → bump spec, schema anchor (e.g., `#/plan/s1_site_weights_v2`), and update Dictionary/Registry entries as needed.
* **Minor:** additive, backward-compatible behaviour (optional metadata, WARN validators, run-report fields).
* **Patch:** editorial only (no shape/procedure/validators changes).

When Status = **frozen**, post-freeze edits are **patch-only** barring a formally ratified minor/major.

---

### 13.6 Relationship to policy bytes

* The **values** of `ε`, `ε_q`, `b`, floor/cap parameters, and `weight_source` are provided by **`alias_layout_policy_v1`**. Updating policy bytes **does not change this spec** and is **not** a spec version event; it results in different sealed inputs and therefore may produce different `s1_site_weights` under a new fingerprint or seed.
* However, **removing** a required policy entry or changing its **meaning** such that S1’s acceptance changes is **breaking** and requires a new **major** of the spec & policy anchor.

---

### 13.7 Compatibility guarantees to downstream states (S2–S6)

* Downstreams **MAY** rely on the **presence and shape** of `s1_site_weights`, its PK/partitions, and the quantisation law stated here.
* Downstreams **MUST NOT** assume file order beyond PK or rely on run-report fields.
* If a new major of S1 is released (e.g., `…/s1_site_weights_v2`), downstreams MUST either:
  (a) continue to accept `v1` until EOL, or (b) advertise support for both during a migration window.

---

### 13.8 Deprecation & migration protocol

* Changes are proposed → reviewed → ratified with a **change log** describing impact, validator deltas, new anchors, and migration steps.
* For majors, a **dual-publish window** is recommended: emit `v1` and `v2` in parallel (v2 authoritative; v1 legacy) for a time-boxed period.

---

### 13.9 Rollback policy

* Outputs are **write-once**; rollback means publishing a **new** `(seed,fingerprint)` (or reverting to a prior fingerprint) that reproduces the last known good behaviour. No in-place mutations.

---

### 13.10 Evidence of compatibility

* Each release MUST include: schema diffs, validator table diffs, and a conformance run showing that previously valid inputs still **PASS** (for minor/patch).
* CI MUST execute a regression suite: coverage 1:1 with `site_locations`, PK uniqueness, normalisation within ε, quantisation coherence within ε_q, immutability, idempotent re-emit.

---

### 13.11 Registry/Dictionary coordination

* Dictionary changes that alter ID names, path families, or partition tokens for `s1_site_weights` are **breaking** unless accompanied by new anchors/IDs and a migration plan.
* Registry edits to **metadata** (owner/licence/retention) are compatible; edits that change **existence** of required artefacts are breaking.

---

### 13.12 Validator/code namespace stability

* Validator IDs (`V-01`…`V-20`) and canonical codes (`2B-S1-…`) are **reserved**. New codes may be added; existing codes’ meanings **MUST NOT** change within a major.

---

## Appendix A — Normative cross-references *(Informative)*

> This appendix lists the authoritative artefacts S1 references. **Schemas** govern shape; the **Dataset Dictionary** governs ID → path/partitions/format; the **Artefact Registry** governs ownership/licence/retention. This appendix is descriptive—the binding rules live in §§1–13.

### A.1 Authority chain (this segment)

* **Schema pack (shape authority):** `schemas.2B.yaml`

  * Output anchor used by S1: `#/plan/s1_site_weights`
  * Policy anchor read by S1: `#/policy/alias_layout_policy_v1`
  * Common defs: `#/$defs/hex64`, `#/$defs/partition_kv` (timestamps reuse `schemas.layer1.yaml#/$defs/rfc3339_micros`)
* **Dataset Dictionary (catalogue authority):** `dataset_dictionary.layer1.2B.yaml`

  * Output ID & path family:

    * `s1_site_weights` → `data/layer1/2B/s1_site_weights/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` (format: parquet)
  * Inputs S1 resolves (Dictionary IDs):

    * `site_locations` (seed,fingerprint)
    * `alias_layout_policy_v1` (fingerprint)
    * *(optional pins)* `site_timezones` (seed,fingerprint), `tz_timetable_cache` (fingerprint)
* **Artefact Registry (metadata authority):** `artefact_registry_2B.yaml`

  * Ownership/retention for the above IDs; cross-layer pointers (1B egress, 2A pins).

### A.2 Prior state evidence (2B.S0)

* **`s0_gate_receipt_2B`** (JSON; fingerprint-scoped) — gate verification, identity, catalogue versions.
* **`sealed_inputs_2B`** (JSON table; fingerprint-scoped) — authoritative list of sealed assets (IDs, tags, digests, paths, partitions).
  *(S1 does not re-hash 1B; it relies on this evidence.)*

### A.3 Inputs consumed by S1 (read-only)

* **Layer-1 · 1B egress:**

  * `site_locations` → `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
  * **Shape:** `schemas.1B.yaml#/egress/site_locations`
* **2B policy:**

  * `alias_layout_policy_v1` → `config/layer1/2B/policy/alias_layout_policy_v1.json`
  * **Shape:** `schemas.2B.yaml#/policy/alias_layout_policy_v1`
* **Optional pins (Layer-2 · 2A) — all-or-none:**

  * `site_timezones` → `data/layer1/2A/site_timezones/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
    **Shape:** `schemas.2A.yaml#/egress/site_timezones`
  * `tz_timetable_cache` → `data/layer1/2A/tz_timetable_cache/manifest_fingerprint={manifest_fingerprint}/`
    **Shape:** `schemas.2A.yaml#/egress/tz_timetable_cache`

### A.4 Output produced by this state

* **`s1_site_weights`** (Parquet; `[seed, fingerprint]`)
  **Shape:** `schemas.2B.yaml#/plan/s1_site_weights`
  **Dictionary path:** `data/layer1/2B/s1_site_weights/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
  **PK:** `[merchant_id, legal_country_iso, site_order]`
  **Required provenance (anchor-owned):** `p_weight`, `weight_source`, `quantised_bits`, `floor_applied`, `created_utc`

### A.5 Identity & token discipline

* **Tokens:** `seed={seed}`, `fingerprint={manifest_fingerprint}`
* **Partition law:** S1 output partitions by **both** tokens; inputs selected exactly as declared (no wildcards).
* **Path↔embed equality:** Any embedded `manifest_fingerprint` (and, if echoed, `seed`) must equal the path tokens.

### A.6 Segment context

* **Segment overview:** `state-flow-overview.2B.txt` *(context only; this S1 spec governs).*
* **Layer identity & gate laws:** programme-wide rules (No PASS → No read; hashing law; write-once + atomic publish).

---