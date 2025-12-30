# Authoring Guide — `numeric_policy.json` (Layer-wide numeric determinism policy)

## 1) Purpose and where it is used

`numeric_policy.json` is a **governance artefact** that declares the **numeric environment + kernel rules** the engine must obey on any **decision/order-critical path** (ranking, acceptance tests, integerisation, etc.). It is **opened** in 1A.S0 and included in the **manifest enumeration**; changing its bytes **must flip `manifest_fingerprint`**. 

It operationalises the S0.8 numeric contract: **IEEE-754 binary64**, **RNE**, **FMA off**, **no FTZ/DAZ**, **serial fixed-order reductions**, and hard-fail on NaN/Inf.

---

## 2) File identity and location (binding)

* **Artefact Registry name:** `numeric_policy_profile` 
* **Path template:** `reference/governance/numeric_policy/{version}/numeric_policy.json` 
* **Manifest behaviour:** opened + hashed as exact bytes; included in `manifest_fingerprint`.

**Byte discipline:** hash the exact bytes (no normalisation). For stable digests, adopt a single canonical formatting convention (indentation, key order, newline-at-EOF) and enforce it in CI.

---

## 3) Required fields (binding minimum)

This file must satisfy the layer governance shape for the “numeric policy profile” by including at least: 

* `rounding`: `"RNE"`
* `fma`: `"off"`
* `ftz_daz`: `"off"`
* `subnormals`: `"preserved"`

You may include additional keys (allowed by the schema), but **they must not contradict** the required four fields.

**Anti-drift rule (SHOULD):** avoid writing multiple synonymous keys for the same concept (e.g., `rounding` and `rounding_mode`) unless you also enforce an equality constraint in CI. Fewer keys -> fewer ways for the policy to contradict itself.

---

## 4) Normative semantics that the policy must declare

### 4.1 Floating-point environment (MUST)

* `binary_format`: IEEE-754 **binary64** for all computations that can influence decisions/order. 
* Rounding: **round-to-nearest, ties-to-even (RNE)**. 
* FMA: **off** on any ordering-critical path.
* Subnormals: **preserved**; FTZ/DAZ **off**.
* NaN/Inf: any NaN/Inf produced in model computations is a **hard error**.

### 4.2 Reduction / aggregation policy (MUST)

* Decision-critical reductions must be **serial**, fixed-order, using **Neumaier compensated summation** (no BLAS reorder, no parallel reduction topologies).

### 4.3 Concurrency rule (MUST)

* Any computation that feeds a **branch/order** must run in a **single-threaded** scalar kernel with pinned iteration order.

### 4.4 Sorting / comparisons (MUST)

* Float ordering for keys must follow IEEE-754 **totalOrder** semantics; **NaNs forbidden** in sort keys; tie-break by deterministic secondary keys.

### 4.5 Constants policy (MUST)

* Decision-critical constants must be encoded as **binary64 hex literals**; recomputing constants from others (e.g., `2*pi`) is forbidden. 

---

## 5) Runtime obligations (how this interacts with attestation)

S0.8 requires runtime self-tests (rounding/FTZ, FMA detection, libm regression, Neumaier sum, totalOrder sanity) and failures abort the run with canonical error codes. 
Separately, runtime must serialize effective flags/env into an attestation artefact (`numeric_policy_attest.json`) within the validation bundle.

**This policy file should declare the expected invariants; the attest proves they held.**

---

## 6) Minimal v1 file content (Codex can write this verbatim)

```json
{
  "version": "1.0",

  "binary_format": "ieee754-binary64",

  "rounding": "RNE",
  "rounding_mode": "rne",

  "fma": "off",
  "fma_allowed": false,

  "ftz_daz": "off",
  "flush_to_zero": false,
  "denormals_are_zero": false,

  "subnormals": "preserved",

  "reductions": {
    "sum_policy": "serial_neumaier",
    "parallel_decision_kernels": "disallowed"
  },

  "sorting": {
    "float_total_order": "ieee754_totalOrder",
    "nan_forbidden_in_sort_keys": true,
    "tie_break_rule": "lexicographic_secondary_key"
  },

  "constants_policy": {
    "require_binary64_hex_literals": true,
    "forbid_derived_constants": true
  },

  "exceptions": {
    "mask_fp_exceptions": true,
    "nan_inf_is_hard_error": true
  },

  "notes": null
}
```

**Consistency rule (MUST):** if both `rounding` and `rounding_mode` exist they must agree (RNE ↔ rne); similarly `fma` ↔ `fma_allowed`, and `ftz_daz` ↔ `flush_to_zero/denormals_are_zero`.

---

## 7) Acceptance checklist (Codex should enforce before sealing)

* File exists at `reference/governance/numeric_policy/{version}/numeric_policy.json`. 
* Contains required fields: `rounding="RNE"`, `fma="off"`, `ftz_daz="off"`, `subnormals="preserved"`. 
* Declares binary64 + serial Neumaier + disallow parallel decision kernels.
* No internal contradictions (consistency rule above).
* File bytes are stable under your formatting convention (so digests don’t drift).

---

## Non-toy/realism guardrails (MUST)

- Enforce binary64 + round-to-nearest-even, FMA off, and no FTZ/DAZ; any deviation is a hard failure.
- Avoid duplicate or synonymous keys unless CI enforces equality; drift here breaks replayability.
- Any policy byte change MUST bump the relevant hash lineage (parameter_hash or manifest_fingerprint).

