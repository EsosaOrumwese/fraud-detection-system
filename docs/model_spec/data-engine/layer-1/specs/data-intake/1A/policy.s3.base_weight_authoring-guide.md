# Authoring Guide — `policy.s3.base_weight.yaml` (Deterministic base-weight prior formula)

This policy is **optional**. It is used only when **1A.S3** is configured to compute **deterministic base-weight priors** in **S3.4**, emitted as `s3_base_weight_priors`. 

These priors are **deterministic scores (not probabilities)** and are **quantised** to a fixed decimal precision `dp`, then emitted as a **fixed-dp string** (`base_weight_dp`) alongside the numeric `dp`. 

---

## 1) File identity (binding)

* **Name:** `policy.s3.base_weight.yaml`
* **Path:** `config/policy/s3.base_weight.yaml` 
* **Governance:** treated as a sealed policy input; changing bytes is a policy change (new lineage).
* **If present, it must be opened** when S3 computes priors; missing/invalid policy causes S3.4 to fail with `ERR_S3_WEIGHT_CONFIG`. 

---

## 2) What S3 expects from this policy (binding)

S3.4 uses this file to:

1. compute a real-valued weight `w_i` per candidate row (deterministically),
2. quantise it into `w_i^⋄ = round_to_dp(w_i, dp)` under binary64/RNE, and
3. emit `w_i^⋄` as a **string** with exactly `dp` decimals in `s3_base_weight_priors`, with `dp` constant within the run. 

If weights are enabled, S3 integerisation uses these quantised priors via:

* `s_i = w_i^⋄ / Σ w_j^⋄` (guarding `Σ w_j^⋄ == 0`), then allocates counts by Hamilton/largest remainder. 

---

## 3) Required top-level shape (MUST)

```yaml
version: "<semver>"
dp: <u8>                  # fixed decimal places for quantisation & emission
model: { ... }            # deterministic formula definition
bounds: { ... }           # safety clamps (log-space and/or linear space)
```

### 3.1 Placeholder resolution (MUST)

Replace the angle-bracket tokens in the shape block with:

* `<semver>`: semantic version string like `1.0.0`.
* `<u8>`: integer in `[0,255]` representing the fixed decimal precision.

Do not add new top-level keys without a semver bump.

Unknown top-level keys SHOULD be rejected (avoid silent drift).

---

## 4) Deterministic model (v1 pinned, minimal but "real")

### 4.0 Realism sanity (MUST)

Even though this is deterministic, the parameter choices affect realism. Before sealing:

* Ensure `beta_home` creates a meaningful domestic bias (home should usually be competitive, not drowned by foreigns).
* Ensure `beta_rank` is not so negative that ranks > ~10 become effectively impossible in practice (unless you intentionally want that).
* Run a quick policy self-test on a candidate-rank grid (e.g., ranks 0..50) and confirm weights remain positive and not numerically degenerate after quantisation.

To keep S3 green and avoid coupling this policy to rule-ladder reason/tag vocabularies, v1 SHOULD depend only on fields always present in S3:

Candidate fields available:

* `is_home` (bool)
* `candidate_rank` (u32; `home` is rank 0) 

### 4.1 Model form (MUST)

Use a log-linear score:

* `log_w = β0 + β_home * I(is_home) + β_rank * candidate_rank`
* `w = exp(log_w)`

### 4.2 Evaluation order (MUST)

Compute in spelled order:

1. `x_home = I(is_home)`
2. `x_rank = candidate_rank`
3. `log_w = β0 + β_home*x_home + β_rank*x_rank`
4. clamp `log_w` to `[log_w_min, log_w_max]`
5. `w = exp(log_w)`
6. clamp `w` to `[w_min, w_max]`
7. quantise: `w^⋄ = round_to_dp(w, dp)` (binary64/RNE)
8. emit `w^⋄` as fixed-dp decimal string with exactly `dp` places (this becomes `base_weight_dp`) 

---

## 5) Bounds & safety (MUST)

This policy MUST include clamps that prevent:

* `exp()` overflow/underflow to 0
* `Σ w_i^⋄ == 0` across a merchant’s candidate set (which would trigger the fallback/error path) 

Recommended v1 bounds:

* `log_w_min = -50.0` (keeps `exp(log_w)` comfortably > 0 in binary64)
* `log_w_max = +50.0`
* `w_min = 1e-12`
* `w_max = 1e12`

---

## 6) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
version: "1.0.0"

# Quantisation precision used by S3.4 and emitted in s3_base_weight_priors.dp
dp: 8

model:
  kind: "loglinear_rank_home"
  coeffs:
    beta0: 0.0
    beta_home: 1.6     # home gets exp(1.6) ≈ 4.95x baseline
    beta_rank: -0.35   # weight decays with candidate_rank

bounds:
  log_w_min: -50.0
  log_w_max: 50.0
  w_min: 1.0e-12
  w_max: 1.0e12
```

This is sufficient for S3.4 to compute and emit `s3_base_weight_priors` with `base_weight_dp` (string) + `dp` (u8), and for integerisation to consume `w_i^⋄` when priors are enabled. 

---

## 7) Acceptance checklist (Codex must enforce)

* File exists at `config/policy/s3.base_weight.yaml`. 
* `version` is non-empty semver string.
* `dp` exists, integer `0..255`. (Missing `dp` ⇒ S3.4 must fail `ERR_S3_WEIGHT_CONFIG`.) 
* `model.kind == "loglinear_rank_home"` and `coeffs` contains exactly `beta0`, `beta_home`, `beta_rank`.
* `bounds` contains `log_w_min < log_w_max`, `0 < w_min < w_max`.
* For any candidate set, computed `w_i^⋄ > 0` and `Σ w_i^⋄ > 0` (policy sanity).
* Coefficients pass the realism sanity checks in section 4.0 (home bias present; decay not pathological).
* Quantisation semantics match S3: `round_to_dp(…, dp)` under binary64/RNE, and emit fixed-dp string with exactly `dp` places. 

---
