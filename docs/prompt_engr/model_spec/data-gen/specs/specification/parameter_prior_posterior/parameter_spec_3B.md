############################################################
#  PARAMETER SPEC‑WRITER • Sub‑segment 3B                   #
############################################################


<<<PP‑FIX id=1>
Name: Virtual-merchant MCC classification rules
Symbol: Policy (YAML-driven)
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic policy mapping (YAML)
hyperparameters:
mcc_channel_rules: config/virtual/mcc_channel_rules.yaml (is_virtual mapping)
units: Boolean is_virtual per merchant
default_policy: abort (drift or mismatch)
justification: Ensures reproducible, auditable virtual classification from governed YAML.
CALIBRATION_RECIPE:
input_path: config/virtual/mcc_channel_rules.yaml
objective: Bytewise match between policy and derived column
algorithm: dry-run match (test_virtual_rules.py)
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see virtual_rules_digest)
INTERFACE_CONSUMER:
artefact_name: derive_is_virtual.py, merchant_master parquet
function: Derives is_virtual field per merchant; used downstream in edge logic and router.
description: Bytewise equality tested in CI; YAML policy is lockstep with persisted column.
POSTERIOR_VALIDATION:
metric: bytewise equality test, manifest hash, logs
acceptance_range: complete column match, hash matches digest
sample_size: all merchants per build
PROVENANCE_TAG:
artefact_name: config/virtual/mcc_channel_rules.yaml
sha256: (see virtual_rules_digest)
SHORT_DESCRIPTION:
YAML policy for virtual-merchant MCC/channel/ship logic, enforced by CI.
TEST_PATHWAY:
test: test_virtual_rules.py, manifest log replay
input: merchant_master.parquet, YAML
assert: All matches/locks in CI; drift aborts build
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=2>
Name: Settlement node coordinate and provenance
Symbol: site_id, lat, lon, evidence_url
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic lookup (CSV + hash)
hyperparameters:
settlement_coords: artefacts/virtual/virtual_settlement_coords.csv, pelias_cached.sqlite
units: site_id: 40-char hex, lat/lon: decimal degrees, evidence_url: string
default_policy: abort (any failed evidence, drift, or missing)
justification: Settlement node coordinates must be auditable, legal, and provably correct via reproducible geocoder and evidence.
CALIBRATION_RECIPE:
input_path: artefacts/virtual/virtual_settlement_coords.csv, pelias_cached.sqlite
objective: Evidence-match, geocode, verify <5 km drift
algorithm: verify_coords_evidence.py, empirical comparison
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see settlement_coord_digest, pelias_digest)
INTERFACE_CONSUMER:
artefact_name: derive_virtual.py, build_edge_catalogue.py
function: Loads legal coordinates and evidence for each virtual settlement node.
description: Used for compliance, reporting, and downstream LGCP; geocoded, tested, and logged.
POSTERIOR_VALIDATION:
metric: haversine drift test <5 km, evidence fetch, logs
acceptance_range: all coords within threshold, all URLs live
sample_size: ten per night (empirical), all at build
PROVENANCE_TAG:
artefact_name: artefacts/virtual/virtual_settlement_coords.csv, pelias_cached.sqlite
sha256: (see settlement_coord_digest, pelias_digest)
SHORT_DESCRIPTION:
Legal, geocoded settlement node coordinates and evidence for each virtual merchant.
TEST_PATHWAY:
test: verify_coords_evidence.py, audit replay
input: CSV, SQLite, logs
assert: All geocodes/evidence within 5 km, all logs match
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=3>
Name: CDN edge country weights and edge scaling
Symbol: $w_c$ (weight), $E$ (edge_scale), $k_c$ (rounded edge count)
Scope: merchant_location
---------------------------------

PRIOR:
type: Discrete weights (YAML, real and integer)
hyperparameters:
$w_c$: probability per country, edge_scale $E$: 500, $k_c$: integer edges
units: $w_c$: probability, $E$: integer, $k_c$: integer
default_policy: use prior (abort if YAML, scale, or weights missing)
justification: CDN edge country weights scaled and rounded for reproducible edge node allocation.
CALIBRATION_RECIPE:
input_path: config/virtual/cdn_country_weights.yaml, etl/akamai_to_yaml.sql
objective: Empirical fit to Akamai/other CDN, integerise with largest remainder
algorithm: etl script, rounding
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see cdn_weights_digest)
INTERFACE_CONSUMER:
artefact_name: build_edge_catalogue.py, edge_catalogue parquet
function: Rounds and assigns edge nodes per country for merchant edge catalogue.
description: Edge weights and scaling ensure edge node count matches empirical shares; feeds alias table.
POSTERIOR_VALIDATION:
metric: sum/round check, digest match, logs/test_cdn_key.log
acceptance_range: total edge count = $E$, rounding correct, hash match
sample_size: all merchants/countries
PROVENANCE_TAG:
artefact_name: config/virtual/cdn_country_weights.yaml
sha256: (see cdn_weights_digest)
SHORT_DESCRIPTION:
CDN edge country weights and edge scale for edge catalogue construction.
TEST_PATHWAY:
test: test_cdn_key.log, empirical audit
input: YAML, logs
assert: Rounding/sum matches, no drift, all edges present
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=4>
Name: Edge node catalogue and Fenwick-tree sampling
Symbol: edge_id, Fenwick sampler
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic (hash + raster sampling)
hyperparameters:
edge_id: SHA1(merchant_id, country_iso, running_index)
HRSL raster: hrsl_100m.tif
units: edge_id: 40-char hex, lat/lon: decimal degrees, tzid: string, edge_weight: integer
default_policy: abort (schema, digest, or raster error)
justification: Deterministic and reproducible edge node catalogue for virtual merchants, O(log n) Fenwick sampling.
CALIBRATION_RECIPE:
input_path: edge_catalogue/<merchant_id>.parquet, hrsl_100m.tif
objective: Sample nodes proportional to HRSL raster weights
algorithm: Fenwick importance sampler, hash generation
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see edge_digest)
INTERFACE_CONSUMER:
artefact_name: build_edge_catalogue.py, edge_catalogue parquet, router
function: Assigns edge node IDs and coordinates; used for routing and LGCP scaling.
description: Edge catalogue feeds router’s alias sampler and transaction event generator.
POSTERIOR_VALIDATION:
metric: parquet schema test, edge_digest check, logs/test_virtual_universe.log
acceptance_range: all edge_ids correct, hash matches, no duplicates
sample_size: all edges per merchant
PROVENANCE_TAG:
artefact_name: edge_catalogue/<merchant_id>.parquet, hrsl_100m.tif
sha256: (see edge_digest)
SHORT_DESCRIPTION:
Edge node catalogue with O(log n) sampling and Fenwick tree per merchant.
TEST_PATHWAY:
test: test_virtual_universe.log, audit replay
input: parquet, HRSL raster, logs
assert: All edges present, hashes match, O(log n) sampling proven
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=5>
Name: CDN alias routing and virtual universe hash
Symbol: Vose alias table, virtual_universe_hash
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic (alias table, hash contract)
hyperparameters:
cdn_alias_table: <merchant_id>_cdn_alias.npz, virtual_universe_hash: concat(cdn_weights_digest, edge_digest, virtual_rules_digest)
units: probabilities: unitless; hash: 64-char hex
default_policy: abort (hash mismatch, CI fail)
justification: All edge assignment/routing governed by hash-locked alias table and provenance.
CALIBRATION_RECIPE:
input_path: <merchant_id>_cdn_alias.npz, cdn_country_weights.yaml, edge_catalogue parquet
objective: Hash/bytewise match to universe hash for full config linkage
algorithm: Vose alias, hash concat and digest
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see cdn_weights_digest, edge_digest, virtual_rules_digest)
INTERFACE_CONSUMER:
artefact_name: router, transaction row
function: Samples edge node per event, proves linkage to weights, edge and rules
description: All CDN sampling/routing driven by provenance-locked alias table and hash.
POSTERIOR_VALIDATION:
metric: hash match, CI check, logs/test_virtual_universe.log
acceptance_range: all hashes match, all events covered
sample_size: all events per merchant
PROVENANCE_TAG:
artefact_name: <merchant_id>_cdn_alias.npz
sha256: (see cdn_weights_digest, edge_digest, virtual_rules_digest)
SHORT_DESCRIPTION:
CDN O(1) alias sampler and hash contract for event routing.
TEST_PATHWAY:
test: test_virtual_universe.log, audit replay
input: alias npz, logs
assert: Alias matches hash, all hashes match, no drift
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=6>
Name: Dual timezone assignment and operational LGCP scaling
Symbol: tzid_settlement, tzid_operational, $\mu_\text{edge}(t) = \mu_\text{settlement}(t) \frac{w_e}{W}$
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic function (no stochastic parameter)
hyperparameters:
tzid_settlement, tzid_operational: string
$\mu_\text{edge}(t)$: rescaled per edge node
units: tzid: string, mu: dimensionless
default_policy: abort (schema or contract violation)
justification: All transactions tagged with settlement/operational tzid and edge-rescaled intensity.
CALIBRATION_RECIPE:
input_path: transaction_schema.avsc
objective: Schema and scaling contract
algorithm: stateless scaling, schema assertion
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see transaction_schema_digest)
INTERFACE_CONSUMER:
artefact_name: LGCP engine, router, fraud features
function: Ensures all events carry dual timezones and edge-scaled mu in buffer.
description: Feeds downstream fraud features, audit, and statistical reporting.
POSTERIOR_VALIDATION:
metric: field present, CI test_cutoff_time.py, log check
acceptance_range: all rows dual-tagged, all mu rescaled
sample_size: all transaction rows per build
PROVENANCE_TAG:
artefact_name: transaction_schema.avsc
sha256: (see transaction_schema_digest)
SHORT_DESCRIPTION:
All events carry dual tzid and edge-scaled LGCP intensity.
TEST_PATHWAY:
test: test_cutoff_time.py, schema/field audit
input: transaction rows, schema
assert: All events carry correct fields, schema validated
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=7>
Name: Validation thresholds for virtual merchants
Symbol: country_tolerance, time_cutoff_tolerance
Scope: merchant_location
---------------------------------

PRIOR:
type: Fixed threshold (YAML-governed)
hyperparameters:
country_tolerance: float (as set in YAML)
time_cutoff_tolerance: float (seconds, as set in YAML)
units: country_tolerance: float, time_cutoff_tolerance: float (seconds)
default_policy: abort (if threshold breached)
justification: Validates empirical distribution and cut-off timestamp per spec.
CALIBRATION_RECIPE:
input_path: config/virtual/virtual_validation.yml
objective: Empirical, check share/cutoff per merchant
algorithm: empirical stat calculation, logs
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see virtual_validation_digest)
INTERFACE_CONSUMER:
artefact_name: validate_virtual.py, ci/test_virtual_validation.py
function: Checks share and cutoff for every merchant per build
description: Validation/CI logic, blocking build if thresholds missed.
POSTERIOR_VALIDATION:
metric: share and time deviation, manifest digest
acceptance_range: within tolerance for every merchant/day
sample_size: all merchants/days
PROVENANCE_TAG:
artefact_name: config/virtual/virtual_validation.yml
sha256: (see virtual_validation_digest)
SHORT_DESCRIPTION:
Validation thresholds for country share and cut-off timestamp, enforced in CI.
TEST_PATHWAY:
test: validate_virtual.py, logs, manifest check
input: YAML, logs, outputs
assert: All thresholds met, manifest digest locked
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=8>
Name: Artefact and licence governance
Symbol: licence_digests_virtual
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic mapping (SHA-1 digests, no stochastic parameter)
hyperparameters:
licence_digests_virtual: mapping from artefact to SHA-1(LICENCES/*.md)
units: SHA-1 digest (hex string)
default_policy: abort (any missing, mismatched, or unreferenced digest)
justification: Ensures legal provenance and compliance for every artefact.
CALIBRATION_RECIPE:
input_path: LICENCES/*.md
objective: Complete mapping and digest computation
algorithm: hash, CI audit
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see manifest)
INTERFACE_CONSUMER:
artefact_name: CI, manifest, legal compliance, validation scripts
function: Maps artefact to licence, ensures all are accounted for, legal, and reproducible.
description: Legal artefact lineage, build/CI enforces compliance via digest check.
POSTERIOR_VALIDATION:
metric: digest check, manifest match
acceptance_range: all SHA-1s present and referenced
sample_size: all artefacts per build
PROVENANCE_TAG:
artefact_name: manifest, LICENCES/*.md
sha256: (see manifest)
SHORT_DESCRIPTION:
SHA-1 mapping of all virtual artefacts for legal and compliance lineage.
TEST_PATHWAY:
test: CI digest check, manifest log replay
input: manifest, LICENCES, logs
assert: All digests present, matches manifest, compliance passes
Confidence=HIGH
<<<END PP‑FIX>>

<<<PP‑FIX id=9>
Name: Edge build progress and error log contract
Symbol: logs/edge_progress.log, logs/virtual_error.log
Scope: merchant_location
---------------------------------

PRIOR:
type: Deterministic contract (no stochastic parameter)
hyperparameters:
edge_progress_log: logs/edge_progress.log
virtual_error_log: logs/virtual_error.log
units: log entry (string, timestamp)
default_policy: abort (any missing, duplicate, or failed entry)
justification: Ensures idempotent, crash-recoverable, and auditable edge build with strict log governance.
CALIBRATION_RECIPE:
input_path: logs/edge_progress.log, logs/virtual_error.log, config/logging/virtual_logging.yml
objective: Full log lineage, restart and recovery logic
algorithm: idempotent batch write, log rotation, skip completed
random_seed: not applicable
convergence_tol: not applicable
script_digest: (see manifest)
INTERFACE_CONSUMER:
artefact_name: build_edge_catalogue.py, CI, manifest, validation scripts
function: Writes, audits, and recovers progress/error logs for edge build and crash recovery.
description: Logs enforce deterministic build, audit, and restart logic.
POSTERIOR_VALIDATION:
metric: CI audit, duplicate check, batch recovery
acceptance_range: all entries present, no duplicates, all recoveries successful
sample_size: all edge batches per merchant/build
PROVENANCE_TAG:
artefact_name: logs/edge_progress.log, logs/virtual_error.log
sha256: (see manifest)
SHORT_DESCRIPTION:
Edge build logs and contract for idempotent, auditable, and crash-recoverable builds.
TEST_PATHWAY:
test: CI audit, log replay, recovery test
input: progress/error logs, manifest, outputs
assert: All batches complete, logs match, recovery works
Confidence=HIGH
<<<END PP‑FIX>>

##### END PARAMETER_SPEC #####

id=1 | gaps_closed=prior|calib|post|prov | notes=YAML, dry-run/bytewise, CI-locked  
id=2 | gaps_closed=prior|calib|post|prov | notes=CSV+SQL, evidence/geocoder, nightly CI-locked  
id=3 | gaps_closed=prior|calib|post|prov | notes=YAML, Akamai, rounding, CI/log-locked  
id=4 | gaps_closed=prior|calib|post|prov | notes=parquet+HRSL, hash, Fenwick/CI-locked  
id=5 | gaps_closed=prior|calib|post|prov | notes=alias table+hash, universe linkage contract  
id=6 | gaps_closed=prior|calib|post|prov | notes=schema/contract, CI LGCP/dual tag  
id=7 | gaps_closed=prior|calib|post|prov | notes=YAML, validation script, share/cutoff threshold  
id=8 | gaps_closed=prior|calib|post|prov | notes=SHA-1 mapping, compliance+manifest  
id=9 | gaps_closed=prior|calib|post|prov | notes=log contract, progress, CI, recovery  
<<PS‑END>>
