# Authoring Guide — `cdn_country_weights.yaml` (3B CDN country mix + edge scale, v1)

## 0) Purpose

`cdn_country_weights.yaml` is the **sealed** policy that 3B.S2 uses as the **sole authority** for:

* the **country-level mix** over `country_iso` codes, and
* a single integer **edge scale** `E` that expands the mix into **per-merchant edge counts**.

This is not a toy config: it must look like a real CDN distribution (heavy-tailed, broad coverage, stable).

---

## 1) File identity (MUST)

* **Dataset ID:** `cdn_country_weights`
* **Path:** `config/virtual/cdn_country_weights.yaml`
* **Schema authority:** `schemas.3B.yaml#/policy/cdn_country_weights_v1`
* **Token-less posture:** **do not embed any digest in-file**. The digest is recorded by 3B.S0 sealing inventory.

---

## 2) Required file shape (MUST match schema)

Top-level YAML object with **exactly**:

* `version` : string (non-placeholder governance tag, e.g. `v1.0.0`)
* `edge_scale` : integer (≥ 1)
* `countries` : array (minItems ≥ 1)

Each `countries[i]` object (fields-strict) must have:

* `country_iso` : ISO2 uppercase (e.g. `GB`)
* `weight` : number (≥ 0.0)
* `notes` : string (optional)

---

## 3) Pinned semantics (decision-free)

### 3.1 Meaning of `edge_scale`

`edge_scale = E` is the **total number of CDN edges allocated per virtual merchant** under v1.

* For each virtual merchant `m`, S2 MUST set: `total_edges(m) = E`.

### 3.2 Meaning of `countries[].weight`

`weight(c)` is the **global country mix** used to split the `E` edges across countries.

S2 MUST interpret the list as a distribution:

* `weight(c) ≥ 0`
* intended to be normalized (Σ weight = 1)

### 3.3 Integerisation rule (MUST; so S2 can’t invent its own)

To allocate per-country edge counts for a merchant with total `E`:

1. Compute targets: `t(c) = E * weight(c)`
2. Set `k(c) = floor(t(c))`
3. Let residuals: `r(c) = t(c) - floor(t(c))`
4. Let `R = E - Σ k(c)`
5. Distribute `+1` to the **R** countries with largest `r(c)`; tie-break by `country_iso` ascending.
6. Output `k(c)`; guarantees Σ k(c) = E.

No RNG. No other heuristics.

---

## 4) Inputs Codex MUST have (fail-closed)

This wrapper policy is derived from an external base weights artefact plus the ISO/country geometry spine.

### 4.1 External base weights (MUST exist)

* **Artefact:** `cdn_weights_ext_yaml`
* **Path (registry):** `artefacts/external/cdn_country_weights.yaml`

The base weights file MUST provide at minimum a mapping of **country code → non-negative mass**.

Pinned accepted base formats (Codex must support exactly these two, fail otherwise):

**Format A (preferred):**

```yaml
version: "<vintage>"
countries:
  - country_iso: "US"
    weight: 0.1234
  - country_iso: "GB"
    weight: 0.0456
```

**Format B:**

```yaml
version: "<vintage>"
weights:
  US: 0.1234
  GB: 0.0456
```

Anything else → **FAIL CLOSED**.

### 4.2 Country universe authority (MUST exist)

* `iso3166_canonical_2024` (ISO2 set)
* `world_countries` (must provide a polygon for ISO2 codes you’ll emit)

If more than **5%** of ISO2 codes in `iso3166_canonical_2024` lack polygons in `world_countries` → **ABORT** (geo spine incomplete).

---

## 5) Deterministic authoring algorithm (Codex-no-input, non-toy)

### Step 1 — Parse and canonicalise external weights

1. Load `cdn_weights_ext_yaml` using §4.1 accepted formats.
2. Canonicalise country codes:

   * trim whitespace
   * uppercase
3. Apply a **pinned** alias map (only these; no guessing):

   * `UK → GB`
   * `EL → GR`
   * `FX → FR`
4. Drop any codes that are not exactly `^[A-Z]{2}$`.

If, after cleaning, `Σ w_ext == 0` → **FAIL CLOSED**.

### Step 2 — Define the output country universe `C`

Let:

* `C = ISO2 codes that exist in iso3166_canonical_2024 AND have polygons in world_countries`

This prevents S2 from being asked to place edges in countries with no geometry.

### Step 3 — Build raw vector over `C`

For each `c ∈ C`:

* `w0(c) = max(0, w_ext(c))` if present, else `0`

Let:

* `P = {c | w0(c) > 0}`
* `M = {c | w0(c) == 0}`

If `|P| < 120` → **FAIL CLOSED** (external base is too thin to be “real deal”).

### Step 4 — Allocate a deterministic “tail mass” for missing countries (prevents toy sparsity)

To avoid producing a policy that only covers a small subset of countries, reserve a small tail mass `τ` for missing countries:

* `missing_frac = |M| / |C|`
* `τ = clamp(0.02 + 0.25 * missing_frac, 0.02, 0.20)`

If `M` is empty, set `τ = 0.0`.

Now define:

* For present countries `c ∈ P`:

  * `w1(c) = (1 - τ) * w0(c) / Σ_{j∈P} w0(j)`
* For missing countries `c ∈ M`:

  * `w1(c) = τ / |M|`  (uniform tail)

This keeps the external shape for major countries, while ensuring broad coverage.

### Step 5 — Apply a tiny positive floor and renormalize (strict positivity)

To prevent exact zeros (which can create brittle edge allocation behaviour):

* `w2(c) = max(w1(c), 1e-12)` for all `c ∈ C`
* Renormalize: `w(c) = w2(c) / Σ_{j∈C} w2(j)`

### Step 6 — Choose `edge_scale` (v1 fixed, non-toy)

Pin v1 to a realistic fixed scale:

* `edge_scale = 500`

Hard bounds (authoring-time guardrails):

* MUST satisfy `200 ≤ edge_scale ≤ 2000` (so Codex can’t emit `edge_scale=1`).

### Step 7 — Emit YAML deterministically

Write:

* keys in order: `version`, `edge_scale`, `countries`
* `countries` sorted by `country_iso` ascending
* stable float formatting for `weight` (recommend 12 digits after decimal)

`notes` (optional but recommended):

* for `c ∈ P`: `"src=akamai_ext"`
* for `c ∈ M`: `"src=tail_uniform"`

(Keep notes short; no timestamps.)

---

## 6) Realism floors (MUST; fail-closed)

Codex MUST abort if any fails:

### 6.1 Coverage / size

* `|C| ≥ 200`
* `len(countries) == |C|`  (full geo-supported ISO2 universe)

### 6.2 Weight validity

* For every row: `weight > 0`
* `abs(Σ weight - 1.0) ≤ 1e-9`

### 6.3 Non-toy distribution checks

* Heavy-tail check (prevents “near-uniform toy mix”):

  * top 5 countries by weight carry **≥ 25%** of mass **OR**
  * top 10 carry **≥ 40%** of mass
    If neither true → **ABORT**.

### 6.4 External anchoring preserved (prevents “ignore Akamai”)

Let `rank_ext` be the top 20 countries by `w0` (external raw, after canonicalisation).
Let `rank_final` be the top 20 by final `w`.

* At least **15 of 20** must overlap.
  If not → **ABORT** (the wrapper distorted the source too much).

### 6.5 Edge scale realism

* `edge_scale` must equal **500** in v1.

---

## 7) Minimal structure example (NOT a real file)

Real file will contain ~200+ countries.

```yaml
version: v1.0.0
edge_scale: 500
countries:
  - country_iso: AD
    weight: 0.000002134921
    notes: "src=tail_uniform"
  - country_iso: AE
    weight: 0.006381920114
    notes: "src=akamai_ext"
  - country_iso: GB
    weight: 0.045612398771
    notes: "src=akamai_ext"
  - country_iso: US
    weight: 0.182349817220
    notes: "src=akamai_ext"
```

---

## 8) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. Validates against `schemas.3B.yaml#/policy/cdn_country_weights_v1`.
3. `version` is non-placeholder; `edge_scale == 500`.
4. Country set equals `C` (ISO2 with polygons). No duplicates.
5. All weights strictly positive; sum-to-1 tolerance satisfied.
6. Realism floors (§6) pass.
7. Deterministic ordering and formatting rules followed.

If any check fails → **FAIL CLOSED** (do not publish; do not seal).

## Placeholder resolution (MUST)

* Replace all placeholder values (e.g., "TODO", "TBD", "example") before sealing.
* Remove or rewrite any "stub" sections so the guide is decision-free for implementers.
