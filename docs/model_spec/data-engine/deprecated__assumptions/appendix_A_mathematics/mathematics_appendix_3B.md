## Subsegment 3B: Special treatment for purely virtual merchants
This appendix codifies every numeric, geometric and cryptographic operation in the **“Special treatment for purely virtual merchants”** sub‑segment.  Each section lists the *purpose*, the *code module* (with path), the *exact formulae* (with units), any *domain notes*, and references to the *manifest keys* or *CI tests* that guarantee governance.

---

### A.1 Settlement‑Node Identifier

**Purpose:** produce a reproducible, 40‑char hex `site_id` for the single settlement node of a virtual merchant.
**Code:** `derive_virtual.py:create_settlement_node`

1. **Concatenate:**

   $$
     B = \mathrm{UTF8}(\texttt{merchant_id}) \;\|\;\texttt{"SETTLEMENT"}.
   $$
2. **SHA‑1 Digest:**

   $$
     D = \mathrm{SHA1}(B)\quad(160\text{‐bit binary}).
   $$
3. **Hex Encoding:**

   $$
     \text{site_id} = \mathrm{hex}(D)\quad(\text{lowercase, 40 characters}).
   $$

> **Domain note:**  the constant string `"SETTLEMENT"` must be ASCII and in uppercase; any change invalidates past `site_id`s.

---

### A.2 Geocode Evidence Validation (Haversine)

**Purpose:** confirm that scraped headquarters coordinates match the CSV record within 5 km.
**Code:** `ci/verify_coords_evidence.py`
Given recorded $(\varphi_r,\lambda_r)$ and geocoded $(\varphi_g,\lambda_g)$ in **radians**:

$$
\Delta\varphi = \varphi_g - \varphi_r,\quad
\Delta\lambda = \lambda_g - \lambda_r.
$$

$$
a = \sin^2\Bigl(\tfrac12\Delta\varphi\Bigr)
    + \cos(\varphi_r)\,\cos(\varphi_g)\,\sin^2\Bigl(\tfrac12\Delta\lambda\Bigr),
$$

$$
d = 2\,R\,\arcsin(\sqrt{a})\quad(\text{meters}),\;R=6\,371\,000\text{ m}.
$$

Assert

$$
d < 5\,000\text{ m}.
$$

> **Units:** angles in radians; output in meters.  CI fails if any of ten sampled rows violate this.

---

### A.3 Edge‑Weight Scaling & Largest‑Remainder Rounding

**Purpose:** convert real weights into integer counts summing exactly to the scale factor E.
**Code:** `generator/virtual.py:round_edge_weights`

1. **Raw Expectation:**

   $$
     e_c = w_c \times E,\quad w_c\ge0,\;E\in\mathbb{N}.
   $$
2. **Floor & Remainder:**

   $$
     \bar k_c = \lfloor e_c\rfloor,\quad
     r_c = e_c - \bar k_c,\quad
     R = E - \sum_c \bar k_c.
   $$
3. **Distribution of Remainder:**
   Sort countries by descending $r_c$ (tie‑break lexicographically by ISO code); for the top $R$ entries increment $\bar k_c$ by one.

   $$
     k_c = \bar k_c + \mathbf{1}_{\{c\in\text{top-}R\}}.
   $$

> **Example:** if $E=5$, weights $[0.6,0.3,0.1]$ yield $e=[3,1.5,0.5]$, floors $[3,1,0]$, remainders $[0,0.5,0.5]$, $R=5-4=1$; ties broken by ISO, so one extra to the country with smaller ISO.

---

### A.4 Fenwick‑Tree Sampling from HRSL Raster

**Purpose:** draw pixel indices proportional to population counts in the 100 m HRSL raster.
**Code:** `sampling/fenwick.py:sample_pixel`

1. **Flatten weights:** $p_1,\dots,p_N\in\mathbb{Z}_{\ge0}$.
2. **Prefix sums:**

   $$
     P_i = \sum_{j=1}^i p_j,\quad P_N>0.
   $$
3. **Uniform Integer Draw:**

   $$
     u \sim \mathrm{Uniform}\{0,\dots,P_N-1\},
   $$

   using Philox to generate a 64‑bit integer.
4. **Binary Search:**

   $$
     i^* = \min\{i : P_i > u\}.
   $$
5. **Coordinates:** map $i^*$ to raster row, column → latitude/longitude.

> **Units:** prefix sums in raw population units; uniform integer in $[0,P_N-1]$.  All arithmetic in 64‑bit integers.

---

### A.5 Vose Alias‑Table Construction & Sampling

**Purpose:** enable $O(1)$ sampling of edge indices according to integer weights.
**Code:** `alias/voce.py:build_alias, sample_alias`
Given integer weights $\{k_1,\dots,k_E\}$:

1. **Normalize to probabilities:**

   $$
     q_i = \frac{k_i}{\sum_j k_j},\quad \sum q_i = 1.
   $$
2. **Build Tables:**
   Two arrays `prob[0…E−1]`, `alias[0…E−1]` of type `uint32`.  Algorithm partitions events into “small” and “large” based on $q_i\times E$.
3. **Sampling:**

   * Draw uniform integer $m\in\{0,\dots,E-1\}$.
   * Draw uniform real $f\in[0,1)$.
   * If $f < \text{prob}[m]$, output $m$; else output `alias[m]`.

> **Reference:** see Knuth/Walker Vose variant in code.  All `uint32` arrays; uniform real from Philox-based RNG.

---

### A.6 Philox‑Key Derivation for CDN Alias RNG

**Purpose:** isolate RNG streams per merchant for alias sampling.
**Code:** `config/routing/rng_policy.yml`
Define the  key as the SHA‑256 digest of:

$$
B = \texttt{global_seed}\;\|\;\text{"CDN"}\;\|\;\texttt{merchant_id},
$$

then

$$
\texttt{key} = \mathrm{SHA256}(B)\quad(256\text{‐bit binary}).
$$

Philox is seeded with `key` and block counter starts at zero.

> **Manifest:** `cdn_key_digest` records the SHA‑256 of `rng_policy.yml`.  CI test `test_cdn_key.py` asserts reproducibility.

---

### A.7 Stateless LGCP Intensity Scaling

**Purpose:** route settlement‑site arrival intensity to edges without per‑edge state.
**Code:** `routing/virtual_lgcp.py:scale_intensity`
Given settlement‑site rate $\mu_s(t)$ and $E$ edges with integer weights $k_i$:

$$
\mu_e(t) = \mu_s(t)\times\frac{k_i}{\sum_{j=1}^E k_j}.
$$

This adjustment is applied inline before each Poisson draw and then discarded.

> **IEEE‑754 note:** standard double‑precision; rounding and subnormal handling consistent across hosts.

---

### A.8 Virtual‑Universe‑Hash Construction

**Purpose:** bind the alias table to its governing artefacts for drift detection.
**Code:** `routing/virtual_universe_hash.py:compute`
Concatenate three manifest digests in byte order:

$$
D = \texttt{cdn_weights_digest}\;\|\;\texttt{edge_digest}\;\|\;\texttt{virtual_rules_digest}.
$$

Compute

$$
h = \mathrm{SHA256}(D)\quad(256\text{‐bit}).
$$

Embed $h$ as `virtual_universe_hash` in the NPZ metadata.

> **CI:** `test_virtual_universe.py` re‑computes $h$ and compares to NPZ.

---

### A.9 Empirical Distribution Error Test

**Purpose:** assert that simulated `ip_country` shares match policy within tolerance.
**Code:** `validate_virtual.py:check_country_shares`
Let policy weights $\pi_c$ and empirical counts $n_c$. Define empirical share

$$
\hat\pi_c = \frac{n_c}{\sum_k n_k}.
$$

Given tolerance $\tau = \texttt{country_tolerance}$, assert

$$
|\hat\pi_c - \pi_c| \le \tau.
$$

> **Manifest:** `virtual_validation_digest` locks both $\tau$ and policy YAML.

---

### A.10 Settlement Cut‑Off Time Alignment

**Purpose:** verify final daily transaction aligns with legal‑seat midnight ±5 s.
**Code:** `validate_virtual.py:check_cutoff_time`
For each merchant and UTC day $d$:

1. Let $t_{\max}$ = max `event_time_utc` in that day.
2. Convert to settlement local time:

   $$
     t_{\mathrm{loc}} = t_{\max} + 60 \times o_s \quad(\text{seconds}),
   $$

   where $o_s$ = settlement offset (minutes).
3. Compute seconds‐past‐midnight:

   $$
     s = t_{\mathrm{loc}} \bmod 86\,400.
   $$
4. Assert

   $$
     86\,395 \le s \le 86\,399.
   $$

> **Units:** $t$ in Unix seconds; $s$ in seconds.  CI test `test_cutoff_time.py` enforces this.

---

### A.11 Output Table Schema and Contract**

* **All outputs to `edge_catalogue/<merchant_id>.parquet` must conform to this schema:**

| Column                | Type     | Description                             |
|-----------------------|----------|-----------------------------------------|
| edge_id               | string   | Unique identifier for each virtual edge |
| country_iso           | char(2)  | Country ISO code                        |
| tzid                  | string   | Time zone identifier                    |
| lat                   | float64  | Latitude in decimal degrees (WGS84)     |
| lon                   | float64  | Longitude in decimal degrees (WGS84)    |
| edge_weight           | int32    | Edge sampling weight (after rounding)   |
| virtual_universe_hash | char(64) | Provenance digest (see A.8)             |

* **Sorting contract:**
  Rows must be sorted by `country_iso`, then `edge_id`.
* **All columns non-nullable and present for every output row.**
* **Schema enforced by `edge_catalogue_schema.json`, which is a governed artefact.**

---

### A.12 Error Log, Drift Sentinel, and Crash Recovery Enforcement

* **Error log artefact:**
  All runtime errors, CI failures (`VirtualUniverseMismatchError`, geocoder validation, cutoff assertion), and drift events must be written to `logs/virtual_error.log`, governed and referenced in the manifest.
* **Crash recovery/progress log:**
  All build progress for edge creation, crash/interruption points, and recovery events are written to `logs/edge_progress.log`, which is also governed.
* **Any missing or duplicate error/progress log entry, or any failed test output, must abort the build and invalidate outputs.**

---

### A.13 Test, Validation, and CI Contracts

* **All property-based and deterministic tests for virtual merchant rules** (e.g., `test_virtual_rules.py`, `verify_coords_evidence.py`, `test_cdn_key.py`, `test_virtual_universe.py`, `test_cutoff_time.py`, `validate_virtual.py`) must be run nightly and produce log outputs, all of which are governed and tracked in the manifest.
* **Any failed test, missing log, or validation drift aborts the build and triggers error log entry.**
* **Test log artefacts:**

  * `logs/test_virtual_rules.log`
  * `logs/verify_coords_evidence.log`
  * `logs/test_cdn_key.log`
  * `logs/test_virtual_universe.log`
  * `logs/test_cutoff_time.log`
  * `logs/validate_virtual.log`

---

### A.14 Manifest and Licence Provenance Contracts

* **Manifest drift:**
  Any change in manifest, schema, YAML, or referenced digest must trigger manifest refresh and abort current/queued builds.
* **Licence mapping:**
  Every YAML/CSV/NPZ/Parquet artefact must be explicitly mapped to a tracked file in `LICENSES/`, with SHA-256 digest checked on every CI run.
* **Any missing, mismatched, or unreferenced licence digest aborts the build.**

---

### A.15 End-to-End Reproducibility and Replay Guarantee

* Given all governed artefacts (YAMLs, NPZs, CSVs, JSON schema, manifests, and seed), the entire virtual edge and arrival generation pipeline must be exactly replayable on any system.
* Any non-reproducibility, mismatch, or hidden state is a pipeline violation and must be recorded as an error event.
