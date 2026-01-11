## Authoring Guide - `validation_policy.yaml` (1A S2 corridor policy: CUSUM `k,h` + `alpha_cap`)

### 0) Purpose

This policy exists solely to govern the **CUSUM corridor gate** used by **1A.S2 corridor validation** (the run-scoped check that can cause the run to fail closed and withhold `_passed.flag`).

In your S2 corridor spec, only **CUSUM parameters** are policy-governed:

* `cusum.reference_k`
* `cusum.threshold_h`
* `cusum.alpha_cap` (optional)

All other corridor thresholds (e.g., overall rejection-rate bound, Q0.99 bound) are *fixed by spec* unless you explicitly promote them into policy later.

---

## 1) Identity & location

* **Path:** `config/layer1/1A/policy/validation_policy.yaml`
* **Type:** authored governance policy (not hunted)
* **Consumption:** read by validation logic (corridor validator / S9 validator)
* **Lineage rule:** because this can change PASS/FAIL outcomes, it MUST be treated as a **sealed governance input** (changing this file must change the run’s validation lineage).

> Note: If you currently don’t have this file registered in the engine contracts, you’ll need to add it to your registry/dictionary later. This guide just defines its contents and authoring rules.

---

## 2) Required top-level structure (strict)

Top-level keys MUST be exactly:

* `semver` (string; `MAJOR.MINOR.PATCH`)
* `version` (string; `YYYY-MM-DD`)
* `cusum` (object)
* `notes` (optional string)

Reject unknown keys and duplicate keys.

---

## 3) `cusum` block (required)

### 3.1 Required keys

```yaml
cusum:
  reference_k: <float>
  threshold_h: <float>
  alpha_cap: <float>   # optional
```

### 3.1.1 Placeholder resolution (MUST)

Replace `<float>` with finite numeric values (no NaN/Inf). Both must be strictly greater than 0.

### 3.2 Semantics

* `reference_k` is the **CUSUM reference value** `k > 0`
* `threshold_h` is the **CUSUM threshold** `h > 0`
* `alpha_cap` (optional) caps per-merchant acceptance probability `alpha_m` used in CUSUM: `alpha_used = min(alpha_m, alpha_cap)` to prevent near-1 alpha values from dominating `z_m`.

The corridor gate is:

* Fail the run if `max_t S_t >= h`
* Where `S_t` is computed by the S2 corridor spec using standardised `z` values.

### 3.3 Domain constraints (MUST)

* `reference_k` MUST be finite and `> 0`
* `threshold_h` MUST be finite and `> 0`
* `alpha_cap` (if present) MUST be finite and in `(0, 1]`
* Recommend practical bounds (SHOULD; for sanity):

  * `reference_k ∈ [0.1, 1.0]`
  * `threshold_h ∈ [3.0, 20.0]`
  * `alpha_cap ∈ [0.95, 0.999]`

---

## 4) Missing-policy behaviour (MUST)

If this file is missing, unreadable, or lacks either `cusum.reference_k` or `cusum.threshold_h`, the corridor validator must **fail closed** with the S2 corridor “policy missing” error.

(This is the whole reason the policy exists: no silent defaults at runtime.)

---

## 5) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

These defaults match the values referenced in your S2 corridor write-up.

```yaml
semver: "1.0.0"
version: "2024-12-31"

cusum:
  reference_k: 0.5
  threshold_h: 8.0
  alpha_cap: 0.999

notes: "CUSUM corridor parameters for 1A.S2 run-scoped validation. Missing => fail closed."
```

---

## 6) Acceptance checklist (Codex must enforce)

* YAML parses; no duplicate keys
* Only allowed top-level keys exist
* `semver` matches `^\d+\.\d+\.\d+$`
* `version` matches `^\d{4}-\d{2}-\d{2}$`
* `cusum.reference_k` and `cusum.threshold_h` exist, finite, and strictly > 0
* If present, `cusum.alpha_cap` is finite and in `(0, 1]`
* File is treated as a sealed governance input (byte changes change lineage)

---

## 7) Does 1B need a validation_policy?

For **1B v1**, typically **no**: 1B’s validation is structural/replay/lineage checks and doesn’t introduce corridor-style statistical gates like S2. If you later add any run-scoped statistical gates to 1B (e.g., spatial density drift detection), then you’d introduce a separate `validation_policy_1B.yaml` (don’t overload the 1A one).

## Non-toy/realism guardrails (MUST)

- Do not ship a “pass-all” or “fail-all” policy; thresholds must allow both outcomes in realistic ranges.
- PASS/WARN/FAIL thresholds must be monotone and non-overlapping; misordered ranges are invalid.
- Every required check in the expanded spec must be present; disabled checks must be explicitly noted.

