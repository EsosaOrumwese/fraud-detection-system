# Authoring Guide — `mcc_channel_rules.yaml` (3B virtual-classification rules, v1)

## 0) Purpose

`mcc_channel_rules.yaml` is the **governed, sealed** rule table that 3B.S1 uses to decide a merchant’s virtual eligibility **based only on**:

* `mcc` (Merchant Category Code), and
* `channel` (`card_present` vs `card_not_present`).

This is a **v1 “exact-match table”** (no wildcards, no priorities, no overrides). Anything richer (allow/deny lists, per-country constraints, priorities) is **v2+**.

---

## 1) File identity (MUST)

* **Dataset ID:** `mcc_channel_rules`
* **Path:** `config/virtual/mcc_channel_rules.yaml`
* **Schema authority:** `schemas.3B.yaml#/policy/virtual_rules_policy_v1`
* **Token-less posture:** do **not** embed any digest in-file; digest is tracked by 3B.S0 sealing inventory.

---

## 2) Required file shape (MUST match schema)

Top-level YAML object with exactly:

* `version` : string (non-placeholder governance tag, e.g. `v1.0.0`)
* `rules` : array (minItems ≥ 1)

Each rule object:

* `mcc` : string
* `channel` : string
* `decision` : enum `{virtual, physical}`
* `notes` : string (optional by schema, but **required by this guide**, see §5.4)

**No extra keys** anywhere (schema is fields-strict).

---

## 3) Pinned semantics (decision-free)

### 3.1 Exact match lookup (v1 pinned)

For a merchant with `(mcc, channel)`:

* If the rules table contains a rule with exact match on both fields:

  * `decision=virtual` ⇒ S1 outcome `VIRTUAL`
  * `decision=physical` ⇒ S1 outcome `NON_VIRTUAL`
* If there is **no matching rule**, S1 MUST default to `NON_VIRTUAL` and record `decision_reason="NO_RULE_MATCH"`.

### 3.2 Uniqueness constraint (MUST)

There MUST be **at most one** rule per `(mcc, channel)` pair.

Duplicate `(mcc, channel)` pairs ⇒ **FAIL CLOSED** (do not publish).

### 3.3 Deterministic ordering (MUST)

Write `rules[]` sorted by:

1. `mcc` ascending (as 4-digit string)
2. `channel` ascending (`card_not_present` before `card_present` is acceptable, as long as pinned; pick one and keep it fixed)

---

## 4) Authoring inputs (MUST exist)

Codex must generate a “real deal” rule table using:

1. **Canonical MCC list**

   * `mcc_canonical_vintage` (must provide MCC code + description/name)

2. **Merchant universe snapshot (for calibration / realism checks)**

   * `merchant_ids` (derived from `transaction_schema_merchant_ids`) with columns:

     * `merchant_id`, `mcc`, `channel`, `home_country_iso`

If `mcc_canonical_vintage` is missing, Codex MUST fail closed (don’t guess MCC domains).

---

## 5) Deterministic authoring algorithm (Codex-no-input)

### 5.1 Canonical formatting (MUST)

Represent every MCC as a **zero-padded 4-digit string**:

* `mcc_str = f"{mcc_int:04d}"`
* Pattern enforced: `^[0-9]{4}$`

Allowed channels (pinned):

* `card_present`
* `card_not_present`

### 5.2 Compute a “virtual-likelihood” score per MCC (deterministic)

From `mcc_canonical_vintage.description` (or name field), compute:

* Normalize: lowercase, ASCII-fold, collapse whitespace.
* Keyword hit set (pinned list, v1):

`KW = {`
`"digital","online","internet","web","software","cloud","streaming","subscription",`
`"telecom","telephone","communications","data","information services",`
`"computer","gaming","video","music","app","hosting","saas",`
`"direct marketing","mail order","e-commerce","electronic"}`
`}`

Score law (pinned):

* `score(mcc) = count_of_distinct_keywords_in_description(KW)`
* Tie-break key for ranking: `(-score, mcc_str)`

### 5.3 Choose the virtual MCC set for `card_not_present` (calibrated, deterministic)

We want a **non-toy** number of virtual merchants, not “0%” and not “everything”.

Let:

* `U_cnp` = merchants where `channel == card_not_present`
* `count_cnp(mcc)` = # of merchants in `U_cnp` with that MCC
* Sort MCCs by `(score desc, mcc_str asc)` to get list `L`.

Pinned corridor targets:

* `p_min = 0.04` and `p_max = 0.20`  (share of **card_not_present merchants** that become virtual)
* `p_target = 0.12`

Selection rule:

1. For `K = 1..|L|`, define `S_K = top K MCCs in L`
2. Compute `p(K) = (Σ_{mcc ∈ S_K} count_cnp(mcc)) / |U_cnp|`
3. Choose **the smallest K** such that:

   * `p(K) ≥ p_target` and `p(K) ≤ p_max`
4. If no such K exists:

   * choose the smallest K such that `p(K) ≥ p_min` and `p(K) ≤ p_max`
5. If still none exists ⇒ **FAIL CLOSED**

Then:

* `VSET = S_K`

### 5.4 Emit full rule table (MUST)

Let `MCC_DOM = all MCCs in mcc_canonical_vintage` (as `mcc_str`).

For each `mcc_str ∈ MCC_DOM` emit exactly **two** rules:

1. `channel: card_present` ⇒ `decision: physical`

   * `notes: "v1:card_present=>physical"`

2. `channel: card_not_present` ⇒

   * `decision: virtual` if `mcc_str ∈ VSET` else `physical`
   * `notes` MUST be:

     * `"v1:cnp=>virtual;score=<score>"` or
     * `"v1:cnp=>physical;score=<score>"`

This produces a complete, future-proof table over the canonical MCC domain.

---

## 6) Realism floors (MUST; fail closed)

Codex MUST abort if any fails:

### 6.1 Coverage + non-toy size

* `|MCC_DOM| ≥ 200`
* `len(rules) == 2 * |MCC_DOM|`
* Both channels present for every MCC

### 6.2 Merchant universe compatibility

Every merchant MCC in `merchant_ids.mcc` must exist in `MCC_DOM`.
If not ⇒ abort (your merchant generator is producing out-of-domain MCCs).

### 6.3 Virtual share corridor (non-toy, not insane)

Using the final rules table:

* Share of **card_not_present merchants** classified virtual must be:

  * `p ∈ [p_min, p_max]` (as defined in §5.3)
* Additionally, overall merchant share virtual must be:

  * between `1%` and `15%` (guards against “almost none” and “nearly all”)

### 6.4 Notes must be informative (prevents “blank toy rules”)

* Every rule must have a non-empty `notes`
* Notes must include either `cnp=>` or `card_present=>` marker

---

## 7) Minimal structure example (NOT a real file)

Real file will contain **hundreds/thousands** of rules.

```yaml
version: v1.0.0
rules:
  - mcc: "0742"
    channel: card_not_present
    decision: physical
    notes: "v1:cnp=>physical;score=0"
  - mcc: "0742"
    channel: card_present
    decision: physical
    notes: "v1:card_present=>physical"
  - mcc: "5815"
    channel: card_not_present
    decision: virtual
    notes: "v1:cnp=>virtual;score=2"
  - mcc: "5815"
    channel: card_present
    decision: physical
    notes: "v1:card_present=>physical"
```

---

## 8) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. Validates against `schemas.3B.yaml#/policy/virtual_rules_policy_v1`.
3. Every MCC formatted as 4-digit string; every channel is one of `{card_present, card_not_present}`.
4. No duplicate `(mcc, channel)` pairs.
5. Sorting rule enforced (§3.3).
6. Realism floors pass (§6).

If any check fails → **FAIL CLOSED** (do not publish; do not seal).

## Placeholder resolution (MUST)

- Replace placeholder MCC groupings with the actual MCC mappings used in v1.
- Replace any example channel rules with the final rule table.
- Replace placeholder IDs/versions with the final identifiers.

