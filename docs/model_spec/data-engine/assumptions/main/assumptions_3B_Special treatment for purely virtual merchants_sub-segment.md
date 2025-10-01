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
