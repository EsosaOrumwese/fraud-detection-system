# Authoring Guide — `alias_layout_policy_v1` (2B alias blob layout + quantisation law)

This policy is the **governing contract** for how Segment **2B** turns deterministic site weights into a **byte-stable alias-table blob** + index metadata. It is sealed in **2B.S0** and then used by **2B.S1 (weight quantisation rules)** and **2B.S2 (alias encode + binary layout)**. Downstream decoders treat the chosen layout/decode law as **authoritative**.

This guide is written so Codex can author a **production-plausible** policy (not a toy), deterministically, with fail-closed checks.

---

## 1) File identity (binding)

* **Dictionary ID:** `alias_layout_policy_v1`
* **Path (Dictionary/Registry):** `contracts/policy/2B/alias_layout_policy_v1.json`
* **Format:** JSON
* **Schema anchor (shape authority):** `schemas.2B.yaml#/policy/alias_layout_policy_v1`
  *(Note: the schema anchor is intentionally permissive; this guide is what pins the real contract.)*

---

## 2) What this policy controls (binding)

### 2.1 Controls S1 (weights)

S1 must use this policy to pin:

* `weight_source` (what deterministic rule generated `p_weight`)
* floor/cap and fallback behaviour
* `quantised_bits` (bit-depth used for integer-grid reconstruction in S2)
* `quantisation_epsilon` (εₛ) tolerance for Σ=1 and decode spot-checks
* required provenance flags to emit per row

### 2.2 Controls S2 (alias blob)

S2 must use this policy to pin:

* `layout_version`, `endianness`, `alignment_bytes`, padding rule
* exact **merchant slice format** inside `alias.bin`
* encode law from `{p_weight}` → `{m_i}` → `{prob[], alias[]}`
* decode law identifier (what runtime uses)
* checksum algorithms and scopes
* required index header/row fields to emit

---

## 3) Top-level required keys (MUST)

The JSON object MUST contain these keys (unknown top-level keys are allowed only under `extensions`, see §9):

### 3.1 Identity + sealing keys (MUST)

* `policy_id` (string) - MUST equal `"alias_layout_policy_v1"`
* `version_tag` (string) - opaque version label (see §8)
* Digest is tracked by the S0 sealing inventory (do NOT embed `sha256_hex` inside the file; token-less posture)

### 3.2 Layout keys (MUST)

* `layout_version` (string) — semantic binary layout identifier (e.g., `"2B.alias.blob.v1"`)
* `endianness` (enum) — `"little"` or `"big"` (recommend `"little"`)
* `alignment_bytes` (int ≥ 1) — slice alignment for merchant starts
* `padding_rule` (object) — padding byte + inclusion rules

### 3.3 Quantisation + tolerance keys (MUST)

* `quantised_bits` (int) — bit-depth **b** used for grid size **G = 2^b**
* `quantisation_epsilon` (number > 0) — εₛ used by S1/S2 validators

### 3.4 Weight policy keys (MUST)

* `weight_source` (object) — deterministic rule label + parameters
* `floor_cap` (object) — floor/cap rules for weights
* `fallback` (object) — what to do if a merchant’s pre-normalised weights are degenerate
* `required_s1_provenance` (object) — required emitted flags/fields

### 3.5 Alias encode/decode keys (MUST)

* `encode_spec` (object) — sufficient to deterministically build alias arrays from integer masses
* `decode_law` (string) — identifier for runtime decode semantics
* `record_layout` (object) — binary slice structure inside the blob

### 3.6 Integrity keys (MUST)

* `checksum` (object) — per-merchant checksum rules
* `blob_digest` (object) — full-blob digest rule
* `required_index_fields` (object) — fields S2 MUST emit in index header + merchant rows

Absence of any required key is **ABORT**.

---

## 4) Canonical digest law (MUST; inventory-side)

Compute the canonical SHA-256 for the policy bytes and record it in the S0 sealing inventory; the policy file MUST NOT embed `sha256_hex`.

**Rule:**

1. Serialize using a **canonical JSON** form:

   * UTF-8
   * object keys sorted lexicographically at every level
   * no insignificant whitespace
   * numbers rendered in standard JSON decimal form (no NaN/Inf)
2. `sha256_hex = SHA256(canonical_bytes)` as lowercase hex64.
3. Record the digest in the S0 sealing inventory as the authoritative value.

If the computed digest does not match the inventory value → **FAIL CLOSED**.

---

## 5) Binary blob contract pinned by this policy (binding)

### 5.1 Blob ordering and offsets (MUST)

* Merchant slices are written in strictly ascending `merchant_id`.
* `offset_0 = 0`.
* For slice i:

  * write payload bytes of length `length_i` (defined below)
  * then write padding bytes so the next slice begins at:
    `offset_{i+1} = align_up(offset_i + length_i, alignment_bytes)`
* **Important:** `length_i` recorded in the index **EXCLUDES** alignment padding bytes.

### 5.2 Per-merchant slice payload format (MUST)

The slice payload is:

1. **Slice header** (fixed-size)

* `n_sites` : uint32
* `prob_qbits` : uint32 (MUST equal the policy’s `record_layout.prob_qbits`)
* `reserved0` : uint32 (MUST be 0)
* `reserved1` : uint32 (MUST be 0)

2. **Alias arrays**

* `prob_q[0..n_sites-1]` : uint32 each

  * Q0.`prob_qbits` fixed-point representation of `prob[j] ∈ (0,1]`
  * encoding rule in §6.4
* `alias[0..n_sites-1]` : uint32 each

  * each value in `[0, n_sites-1]`

No other fields are permitted in v1 payload.

### 5.3 Padding rule (MUST)

* `padding_rule.pad_byte` is a single byte value (recommend `0x00`)
* padding bytes MAY be written only between slices to satisfy alignment
* padding bytes are NOT included in per-merchant checksum scope (unless policy explicitly says otherwise)

---

## 6) Alias encode + decode law pinned by this policy (binding)

### 6.1 Grid definition (MUST)

* `b = quantised_bits`
* `G = 2^b`
* Hard guardrail: `1 ≤ b ≤ 30` (to avoid overflow in common integer paths)

### 6.2 Mass reconstruction from `p_weight` (MUST)

Given merchant with `N` sites and site weights `p_weight[k]` (Σ≈1):

1. Compute `raw_k = p_weight[k] * G` in binary64.
2. Initial integer mass:

   * `m_k = round_to_nearest_ties_to_even(raw_k)`
3. Let `Δ = G - Σ m_k`.
4. If `Δ ≠ 0`, apply deterministic Δ-adjust:

**Ranking key for adjustment** (deterministic, no RNG):

* `residual_k = raw_k - floor(raw_k)`  (in [0,1))
* Sort candidate indices by:

  * if `Δ > 0`: residual descending, then `k` ascending
  * if `Δ < 0`: residual ascending, then `k` ascending
* Apply ±1 to the first `|Δ|` indices, skipping any decrement that would make `m_k < 0` (continue down the ranked list).
* If you cannot satisfy Σ=G after exhausting indices → **ABORT**.

### 6.3 Alias build algorithm (MUST)

Use **classic Walker/Vose** on the normalised probabilities `p_k = m_k / G`:

* scaled weights: `s_k = p_k * N`
* build `prob[0..N-1] ∈ (0,1]` and `alias[0..N-1] ∈ {0..N-1}` deterministically

Deterministic conventions for edge cases (MUST):

* When choosing from “small” and “large” worklists, pop in **ascending index order**.
* When a computed value is numerically within `quantisation_epsilon` of 1.0, treat as exactly 1.0.

### 6.4 `prob_q` encoding (MUST)

Let `Q = 2^prob_qbits` and `prob_qbits = record_layout.prob_qbits` (recommend 32).

For each `j`:

* `q = floor(prob[j] * Q)` in binary64
* clamp: `q = min(q, Q-1)`
* ensure strictly positive: `q = max(q, 1)`
* store `prob_q[j] = uint32(q)`

### 6.5 Decode law identifier (MUST)

Set:

* `decode_law = "walker_vose_q0_32"` if `prob_qbits=32`

Runtime decode semantics:

* draw open-interval `u ∈ (0,1)`
* `j = floor(u*N)`
* `r = u*N - j`
* `r_q = floor(r * 2^prob_qbits)`
* pick `j` if `r_q < prob_q[j]` else `alias[j]`

---

## 7) Checksums and integrity (binding)

### 7.1 Per-merchant checksum (MUST)

Policy must declare:

* algorithm: `"sha256"`
* scope: `"slice_payload_bytes"` (exactly `length_i` bytes starting at `offset_i`, excluding alignment padding)
* encoding: `"hex64_lower"`

Index field `checksum` MUST equal this value.

### 7.2 Blob digest (MUST)

* algorithm: `"sha256"`
* scope: `"raw_blob_bytes"`
* encoding: `"hex64_lower"`

Index header `blob_sha256` MUST equal digest of the full blob file bytes.

---

## 8) Versioning posture (non-toy, binding)

To avoid “sample config” posture, the version fields are not optional:

* `version_tag` MUST be a real governance tag, not `"example"` / `"test"` / `"todo"`.
* Recommended: `version_tag = "v1.0.0"` for the first committed production policy.
* Any change that can alter emitted bytes (layout, quantised_bits, epsilon, checksum scope, etc.) MUST bump `version_tag` and MUST change the sealed digest recorded by S0.

---

## 9) Realism floors (MUST; prevents toy policies)

Codex MUST reject authoring attempts that violate these:

* `quantised_bits ≥ 20` (avoid visibly coarse routing weights)
* `alignment_bytes ∈ {8,16,32}` (realistic binary alignment; recommend 8)
* `prob_qbits ∈ {24,32}` (realistic fixed-point precision; recommend 32)
* `quantisation_epsilon` MUST be consistent with the grid:
  `quantisation_epsilon ≥ 1 / (2^(quantised_bits + 1))` and `≤ 1e-3`
* `checksum.algorithm` MUST be cryptographic (`sha256`) in v1 (no “toy CRC”)
* `policy_id` and `version_tag` MUST be present and non-placeholder

Optional additional keys MUST live under:

* `extensions: { ... }`
  so the core contract stays stable.

---

## 10) Required index fields declaration (MUST)

Policy must explicitly pin what S2 writes in the index so decoders and audits can fail-closed.

`required_index_fields` MUST include:

### 10.1 Header fields (MUST)

* `blob_sha256`
* `blob_size_bytes`
* `layout_version`
* `endianness`
* `alignment_bytes`
* `quantised_bits`
* `created_utc`
* `policy_id`
* `policy_digest`
* `merchants_count`
* `merchants`  *(the per-merchant row array/container)*

### 10.2 Per-merchant row fields (MUST)

* `merchant_id`
* `offset`
* `length`
* `sites`
* `quantised_bits`
* `checksum`

---

## 11) Recommended “v1 production” policy (example JSON)

This is a complete, non-toy baseline that Codex can write deterministically:

```json
{
  "policy_id": "alias_layout_policy_v1",
  "version_tag": "v1.0.0",
  "layout_version": "2B.alias.blob.v1",
  "endianness": "little",
  "alignment_bytes": 8,
  "padding_rule": {
    "pad_byte_hex": "00",
    "pad_included_in_slice_length": false
  },
  "quantised_bits": 24,
  "quantisation_epsilon": 1e-6,
  "weight_source": {
    "id": "uniform_by_site",
    "notes": "Deterministic baseline: equal weight per site within a merchant."
  },
  "floor_cap": {
    "floor_p": 1e-12,
    "cap_p": 0.999999,
    "apply_floor_then_renormalise": true,
    "apply_cap_then_renormalise": true
  },
  "fallback": {
    "on_all_zero_or_nonfinite": "uniform_by_site",
    "on_empty_site_set": "abort"
  },
  "required_s1_provenance": {
    "emit_weight_source": true,
    "emit_floor_applied": true
  },
  "encode_spec": {
    "mass_rounding": "round_to_nearest_ties_to_even",
    "delta_adjust": "residual_ranked_plus_minus_one",
    "worklist_order": "ascending_index",
    "treat_within_epsilon_of_one_as_one": true
  },
  "decode_law": "walker_vose_q0_32",
  "record_layout": {
    "slice_header": "u32_n_sites,u32_prob_qbits,u32_reserved0,u32_reserved1",
    "prob_qbits": 32,
    "prob_q_encoding": "Q0.32_floor_clamp_1_to_2^32-1",
    "alias_index_type": "u32"
  },
  "checksum": {
    "algorithm": "sha256",
    "scope": "slice_payload_bytes",
    "encoding": "hex64_lower"
  },
  "blob_digest": {
    "algorithm": "sha256",
    "scope": "raw_blob_bytes",
    "encoding": "hex64_lower"
  },
  "required_index_fields": {
    "header": [
      "blob_sha256",
      "blob_size_bytes",
      "layout_version",
      "endianness",
      "alignment_bytes",
      "quantised_bits",
      "created_utc",
      "policy_id",
      "policy_digest",
      "merchants_count",
      "merchants"
    ],
    "merchant_row": [
      "merchant_id",
      "offset",
      "length",
      "sites",
      "quantised_bits",
      "checksum"
    ]
  },
  "extensions": {}
}
```
The canonical digest is recorded by S0 in the sealing inventory; do not embed it in the file.

---

## 12) Acceptance checklist (Codex MUST enforce)

1. JSON parses; required keys present.
2. `policy_id == "alias_layout_policy_v1"`.
3. `version_tag` is non-placeholder.
4. Realism floors in §9 pass.
5. `required_index_fields` includes all fields in §10.
6. `record_layout.prob_qbits` ∈ {24,32}; if 32 then `decode_law == "walker_vose_q0_32"`.
7. `quantised_bits` ∈ [1,30] and ≥ 20 for production.
8. `endianness` ∈ {little,big}; `alignment_bytes` ≥ 1 and recommended set for production.
9. No `sha256_hex` key is present (token-less posture; digest recorded by S0).

If any check fails → **FAIL CLOSED** (do not emit or seal the policy).

---

## Placeholder resolution (MUST)

* Replace all placeholder values (e.g., "TODO", "TBD", "example") before sealing.
* Remove or rewrite any "stub" sections so the guide is decision-free for implementers.
