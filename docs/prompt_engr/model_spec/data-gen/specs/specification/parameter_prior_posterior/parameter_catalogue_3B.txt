############################################################
#  PARAMETER CATALOGUE‑FINDER • Sub‑segment 3B             #
############################################################

--- PP 1 ---
Name: Virtual-merchant MCC classification rules
Symbol: Policy (YAML-driven)
Scope: merchant_location
Prior_type: Deterministic policy mapping (YAML)
Prior_specified: Yes
Calibration_recipe: Yes (static rules, config/virtual/mcc_channel_rules.yaml, CI dry-run compares YAML/Parquet, test_virtual_rules.py)
Posterior_validation: Yes (bytewise equality test in CI, manifest digest, logs/test_virtual_rules.log)
Provenance_tag: Yes (config/virtual/mcc_channel_rules.yaml, virtual_rules_digest)
Units: Boolean is_virtual per merchant
Default_policy: abort (if drift or mismatch)
Interface_consumer: derive_is_virtual.py, merchant_master parquet, test_virtual_rules.py
Description: Classifies merchants as virtual using MCC/channel/ship rules from governed YAML; CI enforces bytewise policy-parquet lock.
Anchor: "MCC table shipped in mcc_channel_rules.yaml... YAML is located at config/virtual/mcc_channel_rules.yaml... CI script test_virtual_rules.py performs a dry run, re-derives the is_virtual column... asserts byte-equality with the column persisted in merchant_master.parquet."
Context: "Each merchant_id carries the boolean flag is_virtual, derived from the MCC table... YAML is located at config/virtual/mcc_channel_rules.yaml... CI script test_virtual_rules.py performs a dry run..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 1 ---

--- PP 2 ---
Name: Settlement node coordinate and provenance
Symbol: site_id, lat, lon, evidence_url
Scope: merchant_location
Prior_type: Deterministic lookup (CSV + hash)
Prior_specified: Yes
Calibration_recipe: Yes (CSV, geocoder bundle, evidence scraping, verify_coords_evidence.py)
Posterior_validation: Yes (5km haversine test, logs/verify_coords_evidence.log, manifest, pelias_digest)
Provenance_tag: Yes (artefacts/virtual/virtual_settlement_coords.csv, pelias_cached.sqlite, settlement_coord_digest, pelias_digest)
Units: site_id: 40-char hex, lat/lon: decimal degrees, evidence_url: string
Default_policy: abort (any failed evidence or coordinate drift)
Interface_consumer: derive_virtual.py, build_edge_catalogue.py, verify_coords_evidence.py
Description: Legal-seat coordinate and site_id for settlement node, reproducibly derived and checked against evidence filings and geocoder.
Anchor: "The lookup table virtual_settlement_coords.csv holds these values and their evidence URLs... geocoded via the offline pelias_cached.sqlite bundle... CI job verify_coords_evidence.py pulls ten random rows nightly, fetches the evidence_url, scrapes the address string... geocodes it... asserts that the distance to the recorded coordinate is below 5 km..."
Context: "The coordinate is used only for settlement reporting... The evidence_url is geocoded via the offline pelias_cached.sqlite bundle... CI job verify_coords_evidence.py pulls ten random rows nightly..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 2 ---

--- PP 3 ---
Name: CDN edge country weights and edge scaling
Symbol: $w_c$ (weight), $E$ (edge_scale), $k_c$ (rounded edge count)
Scope: merchant_location
Prior_type: Discrete weights (YAML, real and integer)
Prior_specified: Yes
Calibration_recipe: Yes (Akamai SOTI, etl/akamai_to_yaml.sql, empirical weights, edge_scale in YAML)
Posterior_validation: Yes (sum/rounding check, digest, logs/test_cdn_key.log)
Provenance_tag: Yes (config/virtual/cdn_country_weights.yaml, cdn_weights_digest)
Units: $w_c$: probability, $E$: integer, $k_c$: integer
Default_policy: use prior (abort if YAML, edge_scale, or weights missing)
Interface_consumer: build_edge_catalogue.py, edge_catalogue parquet, alias table constructor
Description: Edge weights and scale factor per merchant/country, rounded to integer edge node counts for edge catalogue construction.
Anchor: "cdn_country_weights.yaml... ledger lives at config/virtual/cdn_country_weights.yaml (keys: country_iso → weight, edge_scale, semver, sha256_digest)... each country weight is multiplied by a global integer E=500... rounded with the same largest-remainder routine used elsewhere."
Context: "The catalogue is built once, immediately after the settlement node, by reading the YAML ledger cdn_country_weights.yaml... each country weight is multiplied by a global integer E=500..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 3 ---

--- PP 4 ---
Name: Edge node catalogue and Fenwick-tree sampling
Symbol: edge_id, Fenwick sampler
Scope: merchant_location
Prior_type: Deterministic (hash + raster sampling)
Prior_specified: Yes
Calibration_recipe: Yes (Fenwick, edge_id, HRSL raster, population-proportional)
Posterior_validation: Yes (parquet schema, edge_digest, logs/test_virtual_universe.log)
Provenance_tag: Yes (edge_catalogue/<merchant_id>.parquet, edge_catalogue_schema.json, hrsl_100m.tif, edge_digest)
Units: edge_id: 40-char hex, lat/lon: decimal degrees, tzid: string, edge_weight: integer
Default_policy: abort (schema error, digest drift, or missing raster)
Interface_consumer: build_edge_catalogue.py, routing/alias table, transaction row
Description: Per-merchant edge node catalogue, edge_id via SHA1, coordinates via HRSL raster, Fenwick importance sampled, stored in governed parquet.
Anchor: "Coordinates for these edge nodes are sampled from the Facebook HRSL GeoTIFF raster... edge IDs are deterministic SHA‑1 hashes of (merchant_id, country_iso, running_index)... parquet file byte-for-byte, writes the digest under edge_digest_<merchant_id>..."
Context: "Coordinates for these edge nodes are sampled from the Facebook HRSL GeoTIFF raster... edge IDs are deterministic SHA‑1 hashes of (merchant_id, country_iso, running_index)..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 4 ---

--- PP 5 ---
Name: CDN alias routing and virtual universe hash
Symbol: Vose alias table, virtual_universe_hash
Scope: merchant_location
Prior_type: Deterministic (alias table, hash contract)
Prior_specified: Yes
Calibration_recipe: Yes (npz, Vose alias, hash construction)
Posterior_validation: Yes (hash comparison, logs/test_virtual_universe.log)
Provenance_tag: Yes (<merchant_id>_cdn_alias.npz, cdn_weights_digest, edge_digest, virtual_rules_digest)
Units: probabilities: unitless; hash: 64-char hex
Default_policy: abort (hash mismatch or CI fail)
Interface_consumer: router, transaction row, validation
Description: Vose alias O(1) sampler and provenance hash; contract ensures all config/artefact/weight linkage is locked per merchant.
Anchor: "the CDN alias table <merchant_id>_cdn_alias.npz embeds the same universe hash... concatenating cdn_weights_digest ∥ edge_digest ∥ virtual_rules_digest—so the router fails fast if anyone tweaks country weights but forgets to rebuild the alias table."
Context: "the CDN alias table <merchant_id>_cdn_alias.npz embeds the same universe hash... so the router fails fast if anyone tweaks country weights but forgets to rebuild the alias table."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 5 ---

--- PP 6 ---
Name: Dual timezone assignment and operational LGCP scaling
Symbol: tzid_settlement, tzid_operational, $\mu_\text{edge}(t) = \mu_\text{settlement}(t) \frac{w_e}{W}$
Scope: merchant_location
Prior_type: Deterministic function (no stochastic parameter)
Prior_specified: Yes
Calibration_recipe: Yes (transaction_schema.avsc, scaling contract)
Posterior_validation: Yes (schema/field check, CI test_cutoff_time.py)
Provenance_tag: Yes (transaction_schema.avsc, transaction_schema_digest)
Units: tzid: string, mu: dimensionless
Default_policy: abort (schema or contract violation)
Interface_consumer: LGCP engine, router, downstream fraud features, transaction row
Description: LGCP engine and router assign dual time zones per transaction, with stateless scaling by edge weight/W.
Anchor: "Two distinct time-zones for every virtual merchant transaction... The LGCP arrival engine asks for an event... Once a candidate local timestamp appears, the router draws a CDN edge using a per-merchant alias table... multiplies μ accordingly..."
Context: "Two distinct time-zones for every virtual merchant transaction... multiplies μ accordingly and records the edge’s coordinate."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 6 ---

--- PP 7 ---
Name: Validation thresholds for virtual merchants
Symbol: country_tolerance, time_cutoff_tolerance
Scope: merchant_location
Prior_type: Fixed threshold (YAML-governed)
Prior_specified: Yes
Calibration_recipe: Yes (country_tolerance, time_cutoff_tolerance, config/virtual/virtual_validation.yml)
Posterior_validation: Yes (empirical test, logs/validate_virtual.log, manifest)
Provenance_tag: Yes (config/virtual/virtual_validation.yml, virtual_validation_digest)
Units: country_tolerance: float, time_cutoff_tolerance: float (seconds)
Default_policy: abort (threshold breach)
Interface_consumer: validate_virtual.py, ci/test_virtual_validation.py
Description: Maximum allowed deviation in country share and settlement cutoff time; enforced in CI and manifest.
Anchor: "The validation thresholds are declared in config/virtual/virtual_validation.yml (fields: country_tolerance, time_cutoff_tolerance, semver, sha256_digest), with its SHA-256 stored as virtual_validation_digest in the manifest and byte-compared by ci/test_virtual_validation.py..."
Context: "Validation adds two tests specific to virtual merchants... the empirical distribution of ip_country codes lies within two percentage points of the YAML weights; another confirms that the settlement cut-off hour alignment remains perfect by asserting that the UTC timestamp of the final transaction each day is 23:59:59 ± 5 seconds settlement-zone time."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 7 ---

--- PP 8 ---
Name: Artefact and licence governance
Symbol: licence_digests_virtual
Scope: merchant_location
Prior_type: Deterministic mapping (SHA-1 digests, no stochastic parameter)
Prior_specified: Yes
Calibration_recipe: Yes (SHA-1 over every virtual artefact licence file, LICENSES/*.md, manifest refresh, CI)
Posterior_validation: Yes (digest test, build abort if mismatch, referenced in manifest)
Provenance_tag: Yes (licence_files_virtual, licence_digests_virtual)
Units: SHA-1 digest (hex string)
Default_policy: abort (any unreferenced, missing, or mismatched licence digest)
Interface_consumer: CI, manifest, legal compliance, validation scripts
Description: All virtual artefact licence files must be mapped and SHA-1-digested; manifest, build, and CI enforce full lineage and mapping.
Anchor: "Every YAML/CSV/NPZ/Parquet artefact must be explicitly mapped to a tracked file in LICENSES/, with SHA-256 digest checked on every CI run. Any missing, mismatched, or unreferenced licence digest aborts the build."
Context: "Licence governance... manifest field licence_digests_virtual stores SHA-1 of each licence text; CI fails if any licence file changes without a corresponding digest update."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 8 ---

--- PP 9 ---
Name: Edge build progress and error log contract
Symbol: logs/edge_progress.log, logs/virtual_error.log
Scope: merchant_location
Prior_type: Deterministic contract (no stochastic parameter)
Prior_specified: Yes
Calibration_recipe: Yes (CI and builder write log on progress and error, rotated and validated)
Posterior_validation: Yes (progress log, error log, build restart, duplicate/missing entry check)
Provenance_tag: Yes (logs/edge_progress.log, logs/virtual_error.log)
Units: log entry (string, timestamped)
Default_policy: abort (on any missing, duplicate, or failed entry)
Interface_consumer: build_edge_catalogue.py, CI, crash recovery, manifest, validation scripts
Description: Builder logs all edge creation progress, errors, and recovers deterministically; logs are governed and validated by CI and manifest.
Anchor: "Builder ensures crash recovery by logging progress to logs/edge_progress.log (rotated daily and retained 90 days per config/logging/virtual_logging.yml); upon restart, the builder reads this log, skips completed batches, and continues without duplicating rows."
Context: "Crash recovery and reproducibility. The edge_catalogue builder is idempotent: after writing each country’s batch of edges it appends the batch key to logs/edge_progress.log..."
Gap_flags:
  prior_missing=N
  hyperparams_missing=N
  calibration_missing=N
  posterior_missing=N
  provenance_missing=N
  units_missing=N
  default_policy_missing=N
  interface_consumer_missing=N
  description_missing=N
Confidence=HIGH
--- END PP 9 ---

<<PP‑END>>
