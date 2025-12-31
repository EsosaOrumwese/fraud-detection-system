# Derivation Guide — `virtual_settlement_coords.csv` (3B settlement coordinate source keyed by `merchant_id`)

## 0) Purpose (what this is for)

`virtual_settlement_coords.csv` is a **pinned, evidence-backed** coordinate source used by **3B.S1** to attach a settlement node to merchants that are classified as virtual (and it’s allowed to contain rows for *all* merchants to prevent “missing coord” failures when policies evolve).

This guide makes it **Codex-no-input**, **non-toy**, and **fail-closed**.

---

## 1) Output contract (MUST)

### 1.1 Path + format

* **Path:** `artefacts/virtual/virtual_settlement_coords.csv`
* **Format:** CSV with header row, UTF-8, LF newlines

### 1.2 Schema (MUST match `schemas.3B.yaml#/reference/virtual_settlement_coords_v1`)

Columns (strict; no extras):

1. `merchant_id` (uint64, NOT NULL) — primary key
2. `lat_deg` (float, NOT NULL) — WGS84 latitude in `[-90, +90]`
3. `lon_deg` (float, NOT NULL) — WGS84 longitude in `(-180, +180]` (**-180 forbidden**)
4. `evidence_url` (string, nullable)
5. `coord_source` (string, nullable)
6. `tzid_settlement` (IANA tzid string, nullable)
7. `notes` (string, nullable)

### 1.3 Ordering (MUST)

* Output rows MUST be sorted by `merchant_id` ascending.

### 1.4 Deterministic numeric formatting (MUST)

To avoid cross-platform float-print drift, write:

* `lat_deg`, `lon_deg` with **exactly 6 digits** after the decimal point (rounded half-away-from-zero is fine as long as it’s deterministic in your implementation).

---

## 2) Required inputs (MUST exist; fail closed)

Codex MUST have:

### 2.1 Merchant universe snapshot (engine ingress)

* `transaction_schema_merchant_ids` (must include `merchant_id`, `home_country_iso`)

### 2.2 Gazetteer bundle (external, already shopped for 3B)

* `pelias_cached.sqlite` (built from GeoNames dump(s), containing a `geoname` table with at least: `geonameid, latitude, longitude, population, country_code, feature_class, feature_code, timezone`)

### 2.3 Optional (recommended for strict ISO sanity)

* `iso3166_canonical_2024` (to validate `home_country_iso`)

If any required input is missing → **FAIL CLOSED**.

---

## 3) Pinned evidence URL law (MUST; decision-free)

Use GeoNames stable feature URIs:

* `evidence_url = "https://sws.geonames.org/{geonameid}/"`

GeoNames documents this URI pattern with examples. ([GeoNames][1])

---

## 4) Deterministic selection law (MUST; decision-free)

This derivation is not RNG. It uses a deterministic hash-mix per merchant.

### 4.1 Deterministic `u_det` (open-interval) (MUST)

For any “stage label” `stage`:

* `msg = UTF8("3B.settlement|" + stage + "|" + merchant_id + "|" + home_country_iso + "|" + coordinate_batch)`
* `h = SHA256(msg)`
* `x = uint64_be(h[0:8])`
* `u_det = (x + 0.5) / 2^64`  → guarantees `u_det ∈ (0,1)`

### 4.2 `coordinate_batch` (MUST; no human input)

Codex MUST set:

* `coordinate_batch = <version token of the pinned transaction_schema_merchant_ids snapshot>`

If that version token cannot be resolved from the intake manifest/path → **FAIL CLOSED**.

(You can optionally append a fixed suffix like `"+geonames"` as long as it is deterministic and pinned, but keep it stable across runs.)

---

### 4.3 Placeholder resolution (MUST)

Replace placeholder tokens as follows:

* `<version token ...>`: the exact `{version}` directory label of the pinned `transaction_schema_merchant_ids` snapshot (e.g., `2025-12-01`).
* `{geonameid}` in the evidence URL: the integer GeoNames id from the chosen candidate row.

Do not invent new batch labels; they must be derivable from pinned inputs.

---

## 5) Candidate settlement universe per country (MUST)

For each ISO2 country `c` appearing in `transaction_schema_merchant_ids.home_country_iso`:

Query candidates from `pelias_cached.sqlite`:

* `country_code == c`
* `feature_class == "P"` (populated places)
* `population >= 0`

Sort candidates by:

1. `population` descending
2. `geonameid` ascending (tie-break)

Let the sorted list be `L_c` with length `n_c`.

**Fail-closed coverage rule:**

* If `n_c == 0` for any country that has ≥1 merchant → **FAIL CLOSED**.

---

## 6) Non-toy selection mechanism (bucketed, deterministic)

This avoids the “everyone ends up in the capital” toy failure mode while still being realistic (big cities get more mass, but not total monopoly).

### 6.1 Build up to 5 ranked buckets per country (MUST)

For each country list `L_c`:

* Consider at most `N_MAX = 500` top candidates (or all if fewer).
* Define bucket index ranges (0-based):

  * `B1 = [0]`
  * `B2 = [1..min(4, n-1)]`
  * `B3 = [5..min(19, n-1)]`
  * `B4 = [20..min(99, n-1)]`
  * `B5 = [100..min(N_MAX-1, n-1)]`

Discard empty buckets.

### 6.2 Bucket probabilities (MUST)

Base probs (in this order):
`P = [0.15, 0.25, 0.30, 0.20, 0.10]`

After discarding empty buckets, renormalize the remaining probabilities to sum to 1.0.

### 6.3 Choose a bucket (MUST)

For merchant `m` in country `c`:

* `u1 = u_det(stage="bucket")`
* Select bucket by CDF over the renormalized bucket probs.

### 6.4 Choose within-bucket candidate (MUST)

Within the chosen bucket, use population-weighted selection:

* weight per candidate `i`:
  `w_i = (population_i + 1000) ^ 0.85`

Then:

* `u2 = u_det(stage="within")`
* Select by weighted CDF (stable; ties fall to the lowest index).

---

## 7) Emitted row construction (MUST)

For each merchant `m`:

1. Determine `home_country_iso = c` from merchant snapshot

   * Validate it’s ISO2 uppercase (and optionally in `iso3166_canonical_2024`).

2. Choose a GeoNames candidate `g` from `L_c` using §6.

3. Set:

* `merchant_id = m`
* `lat_deg = round6(g.latitude)`
* `lon_deg = round6(g.longitude)` then:

  * wrap into `(-180, 180]`:

    * if `lon_deg == -180.000000`, set `lon_deg = 180.000000`
* `evidence_url = "https://sws.geonames.org/{geonameid}/"`
* `coord_source = "geonames:cities500_via_pelias_cached"`
* `tzid_settlement`:

  * if `g.timezone` is a non-empty string and matches IANA tzid shape → set it
  * else set null
* `notes`:

  * recommended deterministic note: `"geonameid={geonameid};bucket={B#}"`
    (or null if you want smaller files)

---

## 8) Validation checklist (MUST; fail closed)

### 8.1 Structural

* Exactly one row per `merchant_id` in the merchant snapshot (no missing, no duplicates)
* All required columns present; no extra columns

### 8.2 Numeric bounds

* All `lat_deg` finite and in `[-90,90]`
* All `lon_deg` finite and in `(-180,180]` (enforce the `-180 → +180` rule)

### 8.3 Evidence integrity (non-toy “evidence-backed”)

* For every row where `evidence_url` is non-null:

  * parse `{geonameid}` from the URL
  * verify that `geonameid` exists in the `geoname` table inside `pelias_cached.sqlite`
* If evidence integrity fails for any row → **FAIL CLOSED**

### 8.4 Realism floors (MUST)

Let `M = #merchants`.

* **Diversity floor:** distinct `geonameid` chosen globally ≥ `max(500, floor(0.05 * M))`
* **Country-level spread floor:** for any country with ≥ 200 merchants:

  * distinct settlements chosen in that country ≥ 10
* **Anti-collapse floor:** for any country with ≥ 1000 merchants:

  * the most common settlement in that country must be ≤ 40% of that country’s merchants
    (If violated → treat as failure; do not silently accept “everyone in one city”.)

---

## 9) Provenance sidecar (MANDATORY)

Write:

* `artefacts/virtual/virtual_settlement_coords.provenance.json`

Include at minimum:

* `dataset_id: "virtual_settlement_coords"`
* `coordinate_batch`
* input pointers + digests:

  * merchant snapshot identity (path/version + digest)
  * `pelias_cached.sqlite` sha256 + `pelias_version` (if you track it)
* algorithm parameters:

  * bucket boundaries, base probs, exponent `0.85`, smoothing `1000`, rounding `6dp`
* summary stats:

  * row count
  * distinct settlements (global + per-country)
  * max share of top settlement per large country (so audits are cheap)

---

### Practical note

This guide intentionally makes the coordinate dataset **complete for all merchants**, so 3B.S1 won’t start failing with `E3B_S1_SETTLEMENT_COORD_MISSING` just because the virtual-classification policy changes later.
