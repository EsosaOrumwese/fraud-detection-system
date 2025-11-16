## Subsegment 2B: Routing transactions through sites

| ID / Key                      | Path Pattern                                                                    | Role                                                            | Semver Field     | Digest Field               |
|-------------------------------|---------------------------------------------------------------------------------|-----------------------------------------------------------------|------------------|----------------------------|
| **site_catalogue_parquet**    | `data/outputs/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/` | Cross‑layer outlet stubs incl. foot‑traffic scalars             | `semver`         | `site_catalogue_digest`    |
| **routing_manifest**          | `artefacts/manifests/routing_manifest.json`                                     | Manifest of all routing artefacts and their digests             | `semver`         | `routing_manifest_digest`  |
| **routing_day_effect**        | `config/routing/routing_day_effect.yml`                                         | Corporate‑day variance parameter σ²                             | `semver`         | `gamma_variance_digest`    |
| **cdn_country_weights**       | `config/routing/cdn_country_weights.yaml`                                       | Edge‑node country weight vector for virtual merchants           | `semver`         | `cdn_alias_digest`         |
| **cdn_weights_ext_yaml**      | `artefacts/external/cdn_country_weights.yaml`                                   | Fixed vintage Akamai country weights (reference)                | `semver`         | `cdn_weights_digest`       |
| **cdn_country_weights**       | `config/routing/cdn_country_weights.yaml`                                       | Internal selector / mapper for CDN weights                      | `semver`         | `cdn_alias_digest`         |
| **routing_validation**        | `config/routing/routing_validation.yml`                                         | Validation thresholds (`tolerance_share`, `target_correlation`) | `semver`         | `validation_config_digest` |
| **logging_config**            | `config/routing/logging.yml`                                                    | Audit‑log batch size, rotation, retention                       | `semver`         | `audit_log_config_digest`  |
| **tz_grouping_policy**        | `config/routing/tz_grouping_policy.yml`                                         | Re‑normalise weights inside originating TZID group              | `semver`         | `tz_group_policy_digest`   |
| **performance_config**        | `config/routing/performance.yml`                                                | Throughput & memory SLA thresholds                              | `semver`         | `perf_config_digest`       |
| **rng_policy**                | `config/routing/rng_policy.yml`                                                 | SHA‑256 → Philox sub‑stream derivation                          | `semver`         | `rng_policy_digest`        |
| **errors_config**             | `config/routing/errors.yml`                                                     | Exception contract (RoutingZeroWeightError, etc.)               | `semver`         | `errors_config_digest`     |
| **routing_audit_schema**      | `config/routing/schemas/routing_audit.schema.json`                              | JSON‑Schema for `routing_audit.log` rows                        | `schema_version` | `audit_schema_digest`      |
| **alias_npz_spec**            | `docs/specs/alias_npz_spec.md`                                                  | Spec for `.npz` format (array names, dtypes, endianness)        | Git commit ref   | `alias_npz_spec_digest`    |
| **alias_determinism_proof**   | `docs/alias_determinism_proof.md`                                               | Formal proof alias build is RNG‑free                            | Git commit ref   | `alias_proof_digest`       |
| **rng_proof**                 | `docs/rng_proof.md`                                                             | Formal proof of RNG stream isolation                            | Git commit ref   | `rng_proof_digest`         |
| **pweights_bin**              | `<merchant_id>_pweights.bin`                                                    | Little‑endian `float64` weight vectors per merchant             | n/a              | `weight_digest`            |
| **alias_npz**                 | `<merchant_id>_alias.npz`                                                       | Uncompressed NumPy arrays (`prob`, `alias`) for alias sampling  | n/a              | `alias_digest`             |
| **cdn_alias_npz**             | `<merchant_id>_cdn_alias.npz`                                                   | Uncompressed NumPy arrays (`prob`, `alias`) for CDN sampling    | n/a              | `cdn_alias_digest`         |
| **errors_config**             | `config/routing/errors.yml`                                                     | Exception definitions (`RoutingZeroWeightError`, etc.)          | `semver`         | `errors_config_digest`     |
| **performance_config**        | `config/routing/performance.yml`                                                | Throughput and memory SLA thresholds                            | `semver`         | `perf_config_digest`       |
| **routing_audit_log**         | `logs/routing/{run_id}/routing_audit.log`                                       | Batch‑checksum audit (1 M events)                               | Manifest semver  | (run‑specific)             |
| **gamma_draw_log**            | `logs/routing/{run_id}/gamma_draw.jsonl`                                        | Per‑day γ_d draws with PRNG context (virtual merchants too)     | Manifest semver  | (run‑specific)             |
| **routing_validation_report** | `artefacts/metrics/routing_validation_{run_id}.parquet`                         | End‑of‑day validation metrics & pass/fail flag                  | Manifest semver  | (run‑specific)             |
| **throughput_metrics**        | `artefacts/metrics/throughput_{run_id}.parquet`                                 | Events/s & RSS samples for perf budget                          | Manifest semver  | (run‑specific)             |
| **routing_error_log**         | `logs/routing/{run_id}/errors.log`                                              | Structured run‑time errors & assertion breaches                 | Manifest semver  | (run‑specific)             |
| **output_buffer**             | `output/buffer/partition_date=*/merchant_id=*/batch_*.parquet`                  | Per‑batch routed‑txn buffer incl. γ‑fields                      | Manifest semver  | `routing_manifest_digest`  |
| **cumulative_counts_vector**  | `artefacts/router/audit/{merchant_id}_cumulative_counts.npy`                    | Packed uint64 per‑site totals for audit checksum                | n/a              | (per‑file)                 |


**Notes:**
* **Binary artefacts** (`.bin`, `.npz`) do not carry semver; path + digest suffice for governance.
* Replace `<merchant_id>` with zero‑padded merchant code where applicable.
* Any addition, removal, or semver/digest drift auto‑refreshes `routing_manifest.json`; CI blocks unsanctioned changes.
* Paths are Unix‑style and case‑sensitive.
* **New enforcement rules:** nightly checksum CI (`router_checksum_ci_test.sh`) must reproduce `routing_audit.log`; throughput CI must respect `performance.yml`; validation must meet thresholds in `routing_validation.yml`.


---
Here is the **fully expanded integration for the Governing Artefacts Appendix (2B)**, closing all governance, output, and contract gaps identified from your narrative/assumptions.
You can **add these rows and enforcement notes directly below your current table and notes**.

---

### Additional Governed Artefacts and Enforcement for Subsegment 2B

#### A. Output, Audit, and Validation Artefacts

| ID / Key                      | Path Pattern                                                   | Role                                                                                                                      | Semver Field    | Digest Field              |
|-------------------------------|----------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|-----------------|---------------------------|
| **routing_audit_log**       | `logs/routing/routing_audit.log`                               | Batch-by-batch audit log (checksum, counts, errors, manifest lineage)                                                     | Manifest semver | (run-specific)            |
| **routing_validation_log**  | `logs/routing/validation.log`                                  | Nightly validation results, assertion outcomes, correlation and share checks                                              | Manifest semver | (run-specific)            |
| **routing_error_log**       | `logs/routing/errors.log`                                      | Structured error log for runtime failures, zero-weight, OOM, assertion breaches, manifest drift                           | Manifest semver | (run-specific)            |
| **output_buffer**            | `output/buffer/partition_date=*/merchant_id=*/batch_*.parquet` | Site-level/txn-level buffer, includes hidden columns (`gamma_id`, `gamma_value`, `ip_country_code` for virtual merchants) | Manifest semver | routing_manifest_digest |
| **output_catalogue_schema** | `output/catalogue_schema.json`                                 | JSON schema for all outputs (buffer, catalogue), all governed fields/columns                                              | schema_version | sha256_digest            |
| **LICENSES**                  | `LICENSES/`                                                    | All licences for YAML/data files; each with SHA-256, referenced in routing_manifest                                      | Manifest semver | per-file sha256           |

#### B. Manifest and Build Contracts

* **Manifest Enforcement:**
  `routing_manifest.json` must include every governed artefact above (inputs, configs, logs, outputs, schemas, licences).

  * Any addition, removal, or semver/digest drift aborts the build and triggers manifest refresh.
  * All outputs and logs must record `routing_manifest_digest`.

* **Audit/Validation Log Enforcement:**

  * Every batch must append an audit event with the fields in A.13 (mathematics appendix).
  * Validation log must show assertion results; failures abort the build.

* **Error Log and Exception Handling:**

  * All runtime errors, assertion failures, and CI aborts must be captured in `routing_error_log`.
  * Error logs must be unique and ordered per batch or event.

* **Output Buffer and Schema Contract:**

  * All per-site, per-batch output buffers must be governed artefacts, must carry full schema, and must be explicitly versioned.
  * Hidden columns required by the router (e.g., `gamma_id`, `gamma_value`, `ip_country_code`) must be listed in `output_catalogue_schema`.

* **Licencing:**

  * Every YAML/config/data file must have a tracked, digest-verified licence in `LICENSES/`, referenced in the manifest.

Great—here’s a **paste‑ready update** for your *governing artefacts* doc for **2B · Routing transactions through sites**. I’ve folded in the artefacts we added (schema, logs, policy/specs) and tightened the governance where your narrative/assumptions require it. Citations point back to your own 2B texts (and, for RNG policy alignment, to 1B’s assumptions).

---

## 2B · Routing transactions through sites — governing artefacts (revision)

### A) Inputs & per‑run manifest

* **`artefacts/catalogue/site_catalogue.parquet`** — cross‑layer input carrying each outlet’s `site_id`, coordinates, and `tzid`; its SHA‑256 is recorded as `site_catalogue_digest` in the routing manifest.&#x20;
* **`routing_manifest.json`** — per‑run roll‑up capturing:
  `site_catalogue_digest, weight_digest, alias_digest, gamma_variance_digest, rng_policy_digest, cdn_alias_digest, routing_licence_digest, audit_log_config_digest` (and, if present, `cdn_country_weights_digest`).&#x20;

### B) Weight law & alias table (deterministic)

* **`<merchant_id>_pweights.bin`** — headerless little‑endian `float64` vector of normalised weights `p_i`, sorted lexicographically by `site_id`; digest saved as `weight_digest`.&#x20;
* **`<merchant_id>_alias.npz`** — uncompressed NumPy 1.23 `.npz` with `prob:uint32`, `alias:uint32`; digest `alias_digest`. Unit tests reconstruct→re‑serialise→re‑hash to assert immutability. &#x20;
* **`alias_npz_spec`** *(doc/spec)* — freezes array names, dtypes, endianness and NumPy version to prevent drift.&#x20;

### C) Corporate‑day random effect & RNG policy

* **`routing_day_effect.yml`** — governs variance `σ_γ²` for log‑normal draw `γ_d` (default 0.15), recorded as `gamma_variance_digest`.&#x20;
* **`rng_policy.yml`** — **use SHA‑256** to derive Philox sub‑stream keys from `(global_seed, "router", merchant_id)`; this aligns with 1B’s *“SHA‑1 prohibited”* constraint.&#x20;
* **`router/seed.py`**, **`router/prng.py`** — implement the SHA‑256‑based keying and the Philox counter stream (day draw at counter 0, subsequent uniforms thereafter).&#x20;
* **`gamma_draw_log`** *(log)* — per (merchant, UTC day) record: `gamma_id`, `gamma_value`, and seed/stream info for exact replay.&#x20;

### D) Time‑zone‑group modulation (no table rebuild)

* **`tz_grouping_policy.yml`** — explicitly defines *“renormalise within the originating site’s `tzid` group; do not rebuild alias tables.”*&#x20;
* **`router/modulation.py`** — multiplies each `p_i` by `γ_d`, then divides by the group sum so `∑_group p_i = 1`; overall scale factor stays **1**, preserving O(1) alias lookups.&#x20;

### E) Virtual‑merchant edge selection

* **`artefacts/external/cdn_country_weights.yaml`** — stationary edge‑country weights `q_c` (Akamai “State of the Internet”); licence recorded.&#x20;
* **`config/routing/cdn_country_weights.yaml`** — thin wrapper/mapping over the external weights (optional).&#x20;
* **`<merchant_id>_cdn_alias.npz`** — alias table over `q_c`, digest captured as `cdn_alias_digest`; the router writes chosen `ip_country_code` on each event.&#x20;

### F) Logging & audit surface

* **`config/routing/logging.yml`** — governs rotation (daily) and 90‑day retention for routing logs; digest `audit_log_config_digest`.&#x20;
* **`routing_audit.schema.json`** *(schema)* — pins the row shape for the audit log. **\[New]**
* **`logs/routing/routing_audit.log`** — every **1,000,000** events compute and append
  `checksum = SHA256(merchant_id || batch_index || cumulative_counts_vector)` (with ISO‑8601 timestamp). &#x20;
* **`<merchant_id>_cumulative_counts.npy`** — packed `uint64` per‑site totals backing the checksum.&#x20;
* **`router_checksum_ci_test`** *(CI test)* — nightly deterministic rerun; diffs audit log line‑by‑line and fails on first mismatch. **\[New]**&#x20;

### G) Validation gates (share & correlation)

* **`config/routing/routing_validation.yml`** — targets/tolerances:
  `|ŝ_i − p_i| < 0.01` for all sites; `|ρ_emp − 0.35| < 0.05`; CI blocks on breach.&#x20;
* **`empirical_share_validation.py`** → **`routing_validation_report`** (per‑merchant metrics with pass/fail), run after full‑day simulation. **\[New]**&#x20;

### H) Licence & provenance

* **`LICENSES/`** — includes the Model‑Risk sandbox licence for JPM hourly counts (used by `calibrate_gamma.ipynb`) and CC‑BY 4.0 for the Akamai report; the routing manifest carries `routing_licence_digest`.&#x20;

---

## CI / audit rules to record explicitly

1. **Determinism:** re‑serialised alias tables must hash equal (`alias_digest` stable); fail otherwise.&#x20;
2. **Audit checksum:** nightly rerun must reproduce `routing_audit.log` exactly (first mismatch fails).&#x20;
3. **Validation:** enforce share/correlation thresholds from `routing_validation.yml`.&#x20;
4. **RNG policy:** key derivation **must be SHA‑256** (1B forbids SHA‑1); any change bumps `rng_policy_digest`.&#x20;
5. **Manifest completeness:** `routing_manifest.json` must include all digests listed in section A; CI checks presence and changes.&#x20;

---

### “New in this revision” (add to your artefact index)

`routing_audit_schema`, `gamma_draw_log`, `routing_validation_report`, `router_checksum_ci_test`, `alias_npz_spec`, `tz_grouping_policy` — all are now referenced in the registry and governed here. &#x20;
