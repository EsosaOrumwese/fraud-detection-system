## Assumptions
The paragraphs below enumerate—without omission or shorthand—the complete chain of premises, data sources, numerical linkages and automated protections that animate **“Special treatment for purely virtual merchants.”** Every constant is tied to a named artefact; every artefact is fingerprinted into the dataset manifest; every computation is anchored in deterministic code paths; every safeguard is enforced in continuous‑integration (CI). A reviewer can therefore alter any YAML, re‑run the build and observe the deterministic delta, or inspect a digest mismatch and discover exactly which premise drifted.

---

### 1 Virtual‑merchant classification via MCC rules

The branch that labels a merchant “virtual” is taken when the boolean column `is_virtual` of the `merchant_master` table is true. That column is not inferred on the fly; it is pre‑populated by the script `derive_is_virtual.py`, which reads a ledger called **`config/virtual/mcc_channel_rules.yaml`**. The YAML maps each MCC to an `online_only` flag and, optionally, an override conditioned on the merchant’s declared transaction `channel` or on the field `requires_ship_address`. For example, MCC 5815 (digital streaming) carries `online_only: true`, while MCC 5994 (newsstands) carries `online_only: false` unless `channel==ONLINE` and `requires_ship_address==false`, in which case the flag flips to true. The YAML’s SHA‑256 digest is embedded in the manifest under `virtual_rules_digest`, and CI script `test_virtual_rules.py` performs a dry run, re‑derives the `is_virtual` column from the YAML, and asserts byte‑equality with the column persisted in `merchant_master.parquet`. If a reviewer edits the YAML but forgets to refresh the parquet, CI halts the build immediately.

### 2 Settlement‑node creation and coordinate provenance

Once `is_virtual` is true, the outlet‑count hurdle is bypassed. Instead, the generator creates one **settlement node** whose `site_id` is the hexadecimal SHA‑1 digest of the UTF‑8 string `(merchant_id,"SETTLEMENT")`. The geographic coordinate of that node is not guessed; it is drawn from **`artefacts/virtual/virtual_settlement_coords.csv`**, a two‑column table keyed by `merchant_id`: `lat`, `lon`, plus an `evidence_url` column linking to the SEC 10‑K filing or Companies‑House registry that lists the headquarters address. The CSV is version‑pinned by digest `settlement_coord_digest` in the manifest. CI job `verify_coords_evidence.py` pulls ten random rows nightly, fetches the `evidence_url`, scrapes the address string with a regex, geocodes it via the offline **`artefacts/geocode/pelias_cached.sqlite` bundle**, and asserts that the distance to the recorded coordinate is below 5 km, thereby catching stale filings. The geocoder bundle `artefacts/geocode/pelias_cached.sqlite` carries an inline `semver` and its SHA‑256 is registered as `pelias_digest` in the manifest; CI’s `ci/test_geocoder_bundle.py` verifies the bundle’s checksum before each build.

### 3 CDN‑edge weights from Akamai report

Customer‑facing geography is captured by a second artefact, **`config/virtual/cdn_country_weights.yaml`**. It lists, per virtual merchant, a dictionary `country_iso → weight`. The weights originate from Akamai’s “State of the Internet” quarterly report; the SQL that scrapes the PDF tables and converts volumes to weights lives in `etl/akamai_to_yaml.sql`. The script imports traffic volume for each edge country, divides by global volume, and writes the YAML. A global integer **E = 500**—stored in the same YAML as `edge_scale`—multiplies each weight before rounding, so the smallest weight yields at least one edge node once it is passed through largest‑remainder integerisation. Changing E changes the number of edge nodes; the YAML’s digest `cdn_weights_digest` seals that choice.

### 4 Edge‑catalogue generation from population raster

Edge catalogue generation proceeds deterministically inside `build_edge_catalogue.py`. For merchant *m* the script reads `config/virtual/cdn_country_weights.yaml`, multiplies each weight by E, runs largest‑remainder rounding, and obtains an integer count $k_c$ of edges per country *c*. It then enters a loop 1…$k_c$ selecting coordinates from the Facebook HRSL GeoTIFF raster (`artefacts/rasters/hrsl_100m.tif`, resolution 100 m) whose digest is `hrsl_digest` in the manifest. Sampling is performed via the same Fenwick‑tree importance sampler described in the physical outlet placement: pixels are traversed in row‑major order, prefix sums recorded in 64‑bit integers, a uniform integer is drawn from the merchant‑scoped Philox stream (keyed by `(merchant_id,"CDN")`) and binary‑searched into the tree. For each draw the script constructs `edge_id = SHA1(merchant_id, country_iso, ordinal)` and writes a row to **`edge_catalogue/<merchant_id>.parquet`** containing (`edge_id`, `country_iso`, `lat`, `lon`, `tzid`, `edge_weight`). The Philox sub‑stream key is defined as the SHA‑256 of the UTF‑8 concatenation of `global_seed`, the literal string `"CDN"`, and the `merchant_id`; this policy resides in `config/routing/rng_policy.yml` (with inline `semver` and `sha256_digest` stored as `cdn_key_digest` in the manifest) to guarantee deterministic alias sampling. Upon completion the parquet is hashed to `edge_digest_<merchant_id>` and indexed in `edge_catalogue_index.csv`.

### 5 Alias routing and virtual universe‑hash

Alias routing for edges requires a probability vector. The script normalises the integer edge weights to unit mass, builds a Vose alias table, serialises it with NumPy’s `savez`, and embeds metadata fields: `edge_digest`, `cdn_weights_digest`, `virtual_rules_digest`. These three digests are concatenated in the order

```
cdn_weights_digest ∥ edge_digest ∥ virtual_rules_digest
```

and hashed into **`virtual_universe_hash`**, stored as a top‑level attribute in `<merchant_id>_cdn_alias.npz`. At runtime the router opens the NPZ, recomputes `virtual_universe_hash` from the live YAMLs and parquets, and fails fast with `VirtualUniverseMismatchError` if any component differs.

### 6 Dual time‑zone semantics in LGCP sampling

Dual time‑zone semantics rely on two columns added to `schema/transaction_schema.avsc`: `tzid_settlement` and `tzid_operational`. When the LGCP engine asks for the next event it passes `tzid_settlement` to `sample_local_time`, so the arrival obeys headquarters civil chronology. These fields are defined in `schema/transaction_schema.avsc` (versioned via `semver` and `sha256_digest` in the schema registry) to cover `tzid_settlement`, `tzid_operational`, `ip_latitude`, `ip_longitude` and `ip_country`, with CI test `ci/test_schema_registry.py` enforcing manifest‑locked consistency. Immediately afterwards the router pulls a 64‑bit uniform *u* from the CDN alias table, indexes into `prob` and `alias` arrays to pick an edge node, extracts that node’s `tzid` and coordinates, overwrites `tzid_operational`, `ip_latitude`, `ip_longitude`, `ip_country` fields in the in‑flight record, multiplies μ by the edge weight divided by total edge weight, and proceeds to UTC conversion. Because the edge selection is the only consumer of a random number in the virtual track, and because the Philox counter is incremented by one per transaction, stream isolation is preserved.

### 7 Stateless LGCP intensity scaling

Memory safety comes from stateless scaling. Instead of creating per‑edge LGCP objects, the simulator keeps only the settlement‑site LGCP and at routing time multiplies its instantaneous mean by the selected edge weight $w_e$ divided by $W = \sum_e w_e$:

$$
\mu_{\text{edge}}(t) = \mu_{\text{settlement}}(t) \times \frac{w_e}{W}.
$$

No new state is allocated; μ is adjusted on the stack and then restored. This IEEE‑754‑compliant multiplication yields identical results across hosts.

### 8 CI‑level virtual‑merchant validation

Validation for virtual merchants is codified in `validate_virtual.py`. It loads 30 synthetic days and, for each virtual merchant, calculates empirical `ip_country` proportions $\hat{\pi}_c$. It computes absolute error against the YAML weight $\pi_c$ and fails if any $|\hat{\pi}_c - \pi_c| > 0.02$. Thresholds reside in `config/virtual/virtual_validation.yml`, key `country_tolerance`. The same job slices each merchant’s transactions per UTC day, finds the maximum `event_time_utc`, converts that timestamp to settlement‑zone civil time, and checks that the civil time lies in the closed interval \[23:59:54, 23:59:59]. Failure prints the offending merchant, the observed cut‑off, and the expected window, catching bugs where offset subtraction was mis‑applied.

### 9 Licence lineage for virtual artefacts

Licensing obligations flow into `LICENSES/akamai_soti.md` (Akamai data, CC‑BY 4.0) and `LICENSES/facebook_hrsl.md` (HRSL raster, CC‑BY 4.0). A manifest field `licence_digests_virtual` stores SHA‑1 of each licence text; CI fails if any licence file changes without a corresponding digest update.

### 10 Crash recovery via progress log

Finally, crash recovery and reproducibility. The `edge_catalogue` builder is idempotent: after writing each country’s batch of edges it appends the batch key to `logs/edge_progress.log`. A crash restarts the builder, reads the log, skips completed batches and continues. Because edge IDs are SHA‑1 hashes of deterministic strings, regenerated batches reproduce byte‑identical rows, guaranteeing no duplication or drift.

---

## Appendix A – Mathematical Definitions & Conventions

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

*With this expanded Appendix A, every numeric algorithm, crypto operation and validation check in the virtual‑merchant flow is specified in mathematical terms, tied to code, manifest keys and CI tests to ensure absolute reproducibility.*

---

## Governed Artefact Registry

Append this table to the end of **assumptions\_3B\_Special treatment for purely virtual merchants\_sub‑segment.txt**. Every entry must appear in the manifest with the indicated metadata; any change to path, semver or digest will trigger CI checks and require a manifest update.

| ID / Key                     | Path Pattern                                      | Role                                                     | Semver Field              | Digest Field                  |
| ---------------------------- | ------------------------------------------------- | -------------------------------------------------------- | ------------------------- | ----------------------------- |
| **virtual\_rules**           | `config/virtual/mcc_channel_rules.yaml`           | MCC→is\_virtual policy ledger                            | `semver`                  | `virtual_rules_digest`        |
| **settlement\_coords**       | `artefacts/virtual/virtual_settlement_coords.csv` | Settlement‑node coordinate & evidence URLs               | `settlement_coord_semver` | `settlement_coord_digest`     |
| **pelias\_bundle**           | `artefacts/geocode/pelias_cached.sqlite`          | Offline Pelias geocoder bundle                           | `semver`                  | `pelias_digest`               |
| **cdn\_weights**             | `config/virtual/cdn_country_weights.yaml`         | CDN edge‑weight policy                                   | `semver`                  | `cdn_weights_digest`          |
| **hrsl\_raster**             | `artefacts/rasters/hrsl_100m.tif`                 | Facebook HRSL 100 m population raster                    | `semver`                  | `hrsl_digest`                 |
| **edge\_catalogue\_parquet** | `edge_catalogue/<merchant_id>.parquet`            | Per‑merchant virtual edge node table                     | n/a                       | `edge_digest`                 |
| **edge\_catalogue\_index**   | `edge_catalogue_index.csv`                        | Drift‑sentinel index for all edge catalogues             | n/a                       | `edge_catalogue_index_digest` |
| **rng\_policy**              | `config/routing/rng_policy.yml`                   | Philox RNG key derivation policy                         | `semver`                  | `cdn_key_digest`              |
| **virtual\_validation**      | `config/virtual/virtual_validation.yml`           | CI thresholds for virtual‑merchant validation            | `semver`                  | `virtual_validation_digest`   |
| **transaction\_schema**      | `schema/transaction_schema.avsc`                  | AVSC schema defining virtual‑flow fields                 | `semver`                  | `transaction_schema_digest`   |
| **virtual\_logging**         | `config/logging/virtual_logging.yml`              | Logging rotation & retention policy for virtual builders | `semver`                  | `virtual_logging_digest`      |
| **licence\_files\_virtual**  | `LICENSES/*.md`                                   | Licence texts for virtual‑merchant artefacts             | n/a                       | `licence_digests_virtual`     |

**Notes:**

* Any entry marked **n/a** in the Semver column means the artefact has no inline version field; it is frozen purely by its digest.
* Replace `<merchant_id>` with the zero‑padded merchant identifier when resolving path patterns.
* All paths use Unix‑style forward slashes and are case‑sensitive.
* The manifest keys shown are the exact JSON fields in your `manifest*.json`; CI tests byte‑compare those against live artefacts.
* Adding, removing or changing any of these artefacts (path, semver or digest) will automatically bump the manifest digest and fail CI until revalidated.
