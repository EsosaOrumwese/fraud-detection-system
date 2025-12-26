# Authoring Guide — `country_zone_alphas_3A` (3A Country×TZ Dirichlet α prior pack)

## 0) Purpose

`country_zone_alphas_3A` is the **governed prior surface** that defines **raw Dirichlet α mass** per `(country_iso, tzid)` for Segment **3A**.

3A.S2 reads this pack (as part of the sealed parameter set) and produces the parameter-scoped `s2_country_zone_priors` table after applying `zone_floor_policy_3A`. This pack is therefore:

* **RNG-free**
* **token-less / seal-by-bytes** (digest lives in the S0 sealing inventory, not inside the file)
* required to be **realistic in coverage and volume** (not a toy prior pack)

---

## 1) File identity (MUST)

* **Artefact name (registry):** `country_zone_alphas`
* **Path:** `config/allocation/country_zone_alphas.yaml`
* **Schema authority:** `schemas.3A.yaml#/policy/country_zone_alphas_v1`
* **Digest posture:** do **not** embed any digest field; S0 sealing inventory records SHA-256 of the exact bytes.

---

## 2) Required file shape (MUST match schema)

Top-level YAML object with **exactly** these keys:

* `version` : string (real governance tag, e.g. `v1.0.0`)
* `countries` : object mapping `ISO2 -> { tzid_alphas: [...], notes?: ... }`

For each country entry:

* `tzid_alphas` : array of objects, each with:

  * `tzid` : IANA tzid (string)
  * `alpha` : number, `>= 0.0`

Optional per-country key:

* `notes` : string (keep short and deterministic if used)

No extra top-level keys are allowed.

---

## 3) Authoritative domain definitions (pinned)

### 3.1 Country set `C_priors` (MUST)

This pack defines `C_priors` via the countries it contains.

For “real deal” coverage, Codex MUST set:

* `C_priors = { c | c is an ISO2 in iso3166_canonical_2024 AND c has a polygon in world_countries AND Z(c) ≠ ∅ }`

If more than **5%** of ISO2s in `iso3166_canonical_2024` are missing from `world_countries`, **ABORT** (your geography spine is incomplete).

### 3.2 Zone universe per country `Z(c)` (MUST)

`Z(c)` MUST be derived exactly as the engine defines it:

* `Z(c) = { tzid | tz_polygon(tzid) ∩ country_polygon(c) ≠ ∅ }`

Where:

* `tz_polygon(tzid)` comes from `tz_world_2025a`
* `country_polygon(c)` comes from `world_countries`

This ensures the prior pack and the engine compute the same country→tzid universe.

---

## 4) Inputs Codex MUST use (read-only)

These are already shopped in earlier segments, but are **required** for authoring this pack:

* `iso3166_canonical_2024` (ISO2 country spine)
* `world_countries` (country polygons; key `country_iso`)
* `tz_world_2025a` (tz polygons; key `tzid, polygon_id`)
* `population_raster_2025` (COG, EPSG:4326; persons)

If any is missing → **FAIL CLOSED**.

---

## 5) Deterministic construction algorithm (Codex-no-input)

### Step 1 — Build `Z(c)` for every in-scope country (MUST)

* For each `country_iso = c` in `world_countries` (restricted to ISO2s in `iso3166_canonical_2024`):

  * spatially intersect `country_polygon(c)` with `tz_world_2025a` polygons
  * collect the set of tzids with non-empty intersection
* If `Z(c) = ∅` for any in-scope country → **ABORT** (your tz geometry doesn’t cover the country polygon)

### Step 2 — Compute population mass per `(c, z)` (MUST)

For each `(c, z)` where `z ∈ Z(c)`:

* Define region geometry: `G(c,z) = country_polygon(c) ∩ tz_polygon(z)` (MultiPolygon allowed)
* Compute:

  * `pop(c,z) = sum(population_raster_2025 over G(c,z))`

Rules:

* Treat raster `nodata` as zero.
* Clamp negative raster values (e.g. -1 nodata) to zero before summing.
* If `pop(c,z) == 0` due to resolution/coverage limits, mark as “pop_missing” for that zone.

### Step 3 — Country-level fallback if population is unreliable (MUST)

Let `pop_total(c) = Σ_z pop(c,z)`.

If `pop_total(c) == 0` (or `pop_missing` for > 50% of zones in the country), fallback deterministically:

* Compute area mass instead:

  * `area_km2(c,z) = area(G(c,z))` in km² using an equal-area projection
* Set `mass(c,z) = area_km2(c,z)` for all zones
* Record `notes` for that country (optional): `"mass_basis=area_fallback"`

If both population and area are zero (shouldn’t happen) → **ABORT**.

Otherwise:

* `mass(c,z) = pop(c,z)` and (optionally) `notes="mass_basis=population"`

### Step 4 — Smooth masses so every zone gets positive share (MUST)

For each country `c`:

* `n = |Z(c)|`
* `M = Σ_z mass(c,z)`

Define a deterministic pseudo-mass:

* `eps = max(1000.0, M / 10000.0)`  (persons-equivalent or area-equivalent)

Then:

* `mass_s(z) = mass(c,z) + eps`
* `share(z) = mass_s(z) / Σ_z mass_s(z)`

This guarantees **all zones** have strictly positive share without producing uniform vectors.

### Step 5 — Choose concentration `A(c)` (MUST; realistic scale)

Let:

* `p_m = max(M, 1.0) / 1e6`  (millions in the mass basis)

Define:

* `A(c) = clamp( 12 + 3*n + 8*ln(1 + p_m), 20, 140 )`

Where `clamp(x, lo, hi)` bounds `x` into `[lo, hi]`.

This yields:

* larger concentration for larger / multi-zone countries,
* bounded so it doesn’t become “almost deterministic”.

### Step 6 — Emit α values (MUST)

For each `z ∈ Z(c)`:

* `alpha(c,z) = A(c) * share(z)`

Enforce a tiny positive lower bound to avoid numerical dust:

* `alpha(c,z) = max(alpha(c,z), 0.005)`

(Do **not** renormalize after this; the later floor policy is designed to handle small zones. The concentration scale remains “close enough” and stable.)

### Step 7 — Ordering + formatting (MUST)

* Countries written in ascending ISO2 order.
* For each country, `tzid_alphas` sorted by `tzid` ascending.
* UTF-8, LF newlines, no timestamps.

---

## 6) Realism floors (MUST; fail-closed)

Codex MUST abort if any fails:

### 6.1 Coverage / size

* `|countries| ≥ 200`
* Coverage must be at least **90%** of ISO2s that have polygons and non-empty `Z(c)`.

### 6.2 Exact universe match

For every country `c` in the file:

* tzids listed must be **exactly** `Z(c)` (no missing tzids, no extras)
* no duplicate tzids

### 6.3 Strict positivity (non-toy)

* For every `(c,z)` entry: `alpha(c,z) > 0.0`

### 6.4 Concentration sanity

For every country `c`:

* `alpha_sum(c) = Σ_z alpha(c,z)` must satisfy `15 ≤ alpha_sum(c) ≤ 160`

### 6.5 Not-uniform sanity (prevents “uniform toy priors”)

Consider the set:

* `E = { c | |Z(c)| ≥ 3 and pop_total(c) (or mass basis) corresponds to ≥ 5 million }`

Requirement:

* For at least **70%** of countries in `E`, the distribution is meaningfully non-uniform:

  * `max_share(c) / min_share(c) ≥ 1.2`

If `E` is empty (unexpected) → ABORT.

---

## 7) Minimal structure example (NOT a real file)

Real file will be large (hundreds of countries).

```yaml
version: v1.0.0
countries:
  GB:
    tzid_alphas:
      - tzid: Europe/London
        alpha: 58.342117
  US:
    tzid_alphas:
      - tzid: America/Anchorage
        alpha: 4.912883
      - tzid: America/Chicago
        alpha: 18.227441
      - tzid: America/Denver
        alpha: 8.104991
      - tzid: America/Los_Angeles
        alpha: 13.883022
      - tzid: America/New_York
        alpha: 31.779663
```

---

## 8) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. Validates against `schemas.3A.yaml#/policy/country_zone_alphas_v1`.
3. Country set coverage meets §6.1.
4. For every country, tzid set equals `Z(c)` exactly (§6.2).
5. All α strictly positive; α sums within bounds (§6.3–§6.4).
6. Not-uniform sanity passes (§6.5).
7. Deterministic ordering + formatting rules satisfied (§5.7).

If any check fails → **FAIL CLOSED** (do not publish; do not seal).

---
