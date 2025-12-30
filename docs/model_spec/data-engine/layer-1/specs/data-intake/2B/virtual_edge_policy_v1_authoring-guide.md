# Authoring Guide — `virtual_edge_policy_v1` (2B.S6 virtual edge catalogue)

This policy is the **sealed catalogue** that 2B.S6 uses to pick a **network edge** for **virtual arrivals** (`is_virtual=1`). It must be **production-plausible** in both **coverage** (global) and **volume** (hundreds/thousands of edges), not just schema-valid.

---

## 1) File identity (binding)

* **Dictionary ID:** `virtual_edge_policy_v1`
* **Path:** `contracts/policy/2B/virtual_edge_policy_v1.json`
* **Format:** JSON
* **Token-less:** yes (S0 seals by exact bytes; selection is by S0-sealed `path + sha256`)

**Important:** the schema for this policy is **fields-strict**. Do **not** add `sha256_hex` inside the file; digest is tracked by the sealing inventory, not embedded.

---

## 2) Schema shape (MUST match exactly)

Top-level object:

* `policy_id` : MUST equal `"virtual_edge_policy_v1"`
* `version_tag` : non-empty string (real governance tag)
* `edges` : array, `minItems=1`
* optional: `notes` : string

Each `edges[i]` is **fields-strict** and MUST include:

* `edge_id` : string, unique across the whole file
* `ip_country` : ISO-3166-1 alpha-2 (uppercase)
* `edge_lat` : number in `[-90, +90]`
* `edge_lon` : number in `(-180, +180]`  (**-180 is forbidden**)
* and **exactly one of**:

  * `weight` : number `> 0`  **OR**
  * `country_weights` : object `{ ISO2 -> number >= 0 }`, with at least 1 key

---

## 3) Semantics pinned by this guide (so it can’t devolve into “toy”)

### 3.1 Interpretation (v1 pinned)

For v1, author this policy using **`weight` on every edge** (global edge mass). Avoid `country_weights` unless you *explicitly* want origin-conditioned routing later.

S6 selection mass is:

* `mass(edge) = edge.weight`

and the runtime selects one `edge_id` from the **full edge list** (or a deterministic subset, if your S6 implementation filters — but this guide assumes full-list selection).

### 3.2 Deterministic ordering (MUST)

The `edges[]` array MUST be written in a stable canonical order:

* primary: `ip_country` ascending
* secondary: `edge_id` ascending

This is critical for replay (alias construction, audits, and byte stability).

---

## 4) Real-deal construction algorithm (Codex-no-input, deterministic)

This is the heart of the guide: how Codex generates a **large**, **plausible**, **globally distributed** edge catalogue with no human judgement.

### 4.1 Inputs (read-only; must already be shopped)

Use these already-existing Layer-1 externals:

* `iso3166_canonical_2024` (authoritative ISO2 set)
* `world_countries` (country polygons)
* `population_raster_2025` (WorldPop raster)

If any input is missing → **FAIL CLOSED**.

### 4.2 Choose a target edge count (MUST; prevents toy)

Pin a production baseline:

* `TARGET_EDGES = 2000`

Hard bounds:

* MUST be `800 ≤ TARGET_EDGES ≤ 5000`

(If you ever want to tune this later, that’s a **new version_tag**.)

### 4.3 Country coverage set (MUST)

Let `C` be the set of ISO2 codes that satisfy:

* present in `iso3166_canonical_2024` **and**
* have a polygon in `world_countries`

Countries missing polygons:

* If count missing > 5% of ISO2 set → **ABORT**
* Else, drop them with an explicit warning recorded in `notes`

### 4.4 Compute “demand weight” per country (deterministic)

Compute per-country total population:

* `POP[c] = sum(population_raster_2025 cells within country polygon c)`

If raster coverage for a country is zero or missing:

* fallback `POP[c] = area_km2(country)` (from polygon), but **record fallback count** in `notes`
* If fallback count > 10% of `|C|` → **ABORT**

Define demand score (heavy-tail but stable):

* `Q[c] = POP[c] ^ 0.90`

### 4.5 Allocate number of edges per country (exact sum == TARGET_EDGES)

We want global realism: many edges in large/high-demand countries, but at least one per country.

1. Base allocation:

* `k_raw[c] = TARGET_EDGES * Q[c] / sum(Q)`
* `k[c] = max(1, floor(k_raw[c]))`

2. Remainder fix (largest remainder, deterministic):

* `R = TARGET_EDGES - sum(k[c])`
* rank countries by fractional part `(k_raw[c] - floor(k_raw[c]))` descending, tie-break by `c` ascending
* add `+1` to the first `R` countries

3. Caps (prevent silly extremes):

* enforce `k[c] ≤ 80`
* if capping changes totals, re-run remainder fix across uncapped countries; if impossible → **ABORT**

This yields exactly `sum k[c] == TARGET_EDGES`.

### 4.6 Choose edge coordinates inside each country (population-peaks, deterministic)

For each country `c`, select `k[c]` edge locations:

1. Mask raster cells to country polygon.
2. Sort candidate cells by:

   * population descending
   * tie-break: `(row_index, col_index)` ascending (or tile_id ascending)
3. Greedy pick with minimum separation:

   * `MIN_SEP_KM = 50` (or 25 for tiny countries; deterministic rule below)
   * iterate candidates in sorted order:

     * accept cell centroid if it’s ≥ MIN_SEP_KM from all already accepted points
     * continue until you have `k[c]`

Tiny-country deterministic rule:

* If country area `< 10,000 km²`, set `MIN_SEP_KM = 15`.

Fallback if you cannot find enough separated points:

* fill remaining with highest-pop cells ignoring separation, but **record a `sep_relaxed_count`** in `notes`.
* If relaxed fills > 5% of all edges → **ABORT**.

### 4.7 Assign `edge_id` (unique, stable, non-toy)

For the j-th edge in country `c` (1-indexed by selection order):

* `edge_id = f"{c}-EDGE-{j:03d}"`

This is stable, sortable, and realistic-looking.

### 4.8 Assign weights (global, heavy-tail, deterministic)

We want weights that look like real “traffic mass” distribution.

1. Allocate a country total mass (not uniform):

* `W_country[c] ∝ Q[c]` (same Q as above)

2. Allocate within-country edge mass:

* Let `p_j` be the population of the chosen cell for edge j
* define edge raw mass:

  * `w_raw = (p_j + POP[c] / (10*k[c])) ^ 0.85`
  * (the additive term prevents near-zero edges in sparse areas)

3. Normalize:

* First normalize within country so `sum_j w[c,j] = W_country[c]`
* Then normalize globally across all edges so `sum_all_edges weight = 1.0`

4. Floors (schema requires >0 and realism requires no near-zero dust):

* enforce `weight ≥ 1e-12`
* renormalize globally after flooring

---

## 5) Realism floors (MUST; fail closed)

Codex MUST abort if any fails:

### 5.1 Volume & coverage

* `len(edges) == TARGET_EDGES`
* Unique `edge_id` count == `TARGET_EDGES`
* Country coverage: number of distinct `ip_country` in edges MUST be:

  * ≥ 85% of `|C|` **and**
  * ≥ 200 (absolute floor)

### 5.2 Coordinate validity

For every edge:

* `edge_lat ∈ [-90,90]`
* `edge_lon ∈ (-180,180]` (**must not equal -180 exactly**)
* Point should fall inside its `ip_country` polygon; if point-in-polygon check fails:

  * allow up to 0.5% failures *only if* the point is within 5 km of the border (numeric jitter)
  * otherwise **ABORT**

### 5.3 Weight validity + non-toy distribution

* all edges use `weight` (v1 pinned) and `weight > 0`
* global sum: `abs(sum(weight) - 1.0) ≤ 1e-9`
* heavy-tail check (prevents “flat toy weights”):

  * top 1% of edges carry at least 10% of total mass **OR**
  * top 5% carry at least 30%
  * if neither is true → **ABORT**

---

## 6) Notes field (recommended, not toy)

Populate `notes` with a compact provenance string (still deterministic), e.g.:

* input vintages used (`iso3166_canonical_2024`, `world_countries`, `population_raster_2025`)
* TARGET_EDGES
* exponent choices (0.90, 0.85)
* fallback counters (missing polygons, pop-fallback, sep-relaxed)
* generation timestamp should **not** be included (would break determinism); use the sealed inventory for timestamps.

---

## 7) Minimal shape example (DO NOT use as a real file)

Just to show structure (real file must be ~2000 edges):

```json
{
  "policy_id": "virtual_edge_policy_v1",
  "version_tag": "v1.0.0",
  "edges": [
    { "edge_id": "GB-EDGE-001", "ip_country": "GB", "edge_lat": 51.5074, "edge_lon": -0.1278, "weight": 0.00123 },
    { "edge_id": "NG-EDGE-001", "ip_country": "NG", "edge_lat": 6.5244,  "edge_lon": 3.3792,  "weight": 0.00087 }
  ],
  "notes": "Generated deterministically from iso3166_canonical_2024 + world_countries + population_raster_2025; TARGET_EDGES=2000; Q=POP^0.90; w=(p+POP/(10k))^0.85."
}
```

---

## 8) Acceptance checklist (Codex MUST enforce)

1. JSON parses; top-level keys valid; no extra fields in edges.
2. `policy_id` correct; `version_tag` is non-placeholder.
3. `TARGET_EDGES` hit exactly; ordering rule enforced.
4. All edge coordinates within numeric bounds; `edge_lon != -180`.
5. Weights strictly positive and normalized; heavy-tail check passes.
6. Coverage thresholds met.
7. Any fallback usage is within allowed limits; otherwise abort.

---

## Placeholder resolution (MUST)

- Replace placeholder edge lists with the actual allowed edges for v1.
- Replace any example weights with the final distribution (must sum correctly by context).
- Replace placeholder policy IDs/versions with final identifiers.

