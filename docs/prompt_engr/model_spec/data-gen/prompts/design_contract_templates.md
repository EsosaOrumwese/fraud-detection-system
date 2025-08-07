# Templates for each Contract used in Design

## Lean dependency flow (populate in this order)

```
1. artefact_registry
      ↓
2. dataset_dictionary.layer1.yaml
      ↓
3. sub-segment specs
      ├─ schemas.<ID>.yaml
      ├─ invariants.<ID>.yaml
      ├─ rng_contract.<ID>.yaml
      ├─ logging_contract.<ID>.yaml
      └─ performance.<ID>.yaml
      ↓
4. maths → machine bridge
      ├─ mathematics_appendix_<ID>.txt   (human, already written)
      ├─ function_registry.<ID>.yaml
      └─ parameter_dictionary.<ID>.yaml
      ↓
5. interface_contract.<ID>.yaml          (thin index that pins all files above)
      ↓
6. link_contract.<N→N+1>.yaml            (CI auto-generates boundary checks)
      ↓
7. layer-wide shared tables
      ├─ error_catalogue.layer1.yaml
      ├─ id_namespace_registry.layer1.yaml
      ├─ prior_library.layer1.yaml
      └─ taxonomy.layer1.yaml
      ↓
8. layer1_merchant_location_realism.manifest.yaml
   (pins SHA-256 of EVERY file from steps 1-7)  ← final production lock-down
```

#### Populating order in practice

1. **Fill artefact registry → dataset dictionary.**
2. For each sub-segment, iterate through *schemas → invariants → RNG → logging → performance → maths bridges*.
3. Generate interface contract, commit; CI then auto-generates link contract.
4. When all eight stages pass CI, compile shared tables (error catalogue, ID registry, priors, taxonomy).
5. Run final CI task that writes `layer1_…manifest.yaml` with every SHA-256 and blocks merge unless:

   * all placeholder markers resolved (phase ≥ beta),
   * every link contract passes,
   * bundle hash computed and stored.

Now Layer 1 is **frozen**; later layers reference only:

```yaml
depends_on:
  layer: "merchant_location_realism"
  manifest_sha256: "<pinned_bundle_hash>"
```

If any upstream spec changes, its SHA-256 changes, CI forces a manifest version bump, and downstream contracts refuse to build until they’re re-validated.

### **How Placeholders Are Handled**

* **Placeholders** (like `{semver}`, `{sha256}`, `{iso8601_timestamp}`) are used for any field whose value will be finalized at build time or after artefact creation.

  * **String fields:** Placeholders are enclosed in curly braces `{like_this}` to ensure validation tools and humans know these must be replaced.
  * **Lists:** Even if dependencies are unknown, use an empty list `[]` as a valid placeholder.
  * **Nullable fields:** Use `null` for non-mandatory fields not yet specified.
  * **Boolean:** `cross_layer: true/false` clarifies cross-segment artefact reuse.

### **Comments & Documentation**

* Inline YAML comments explain the type/role of each field.
* Each artefact should have a unique `manifest_key` for manifest tracking.
* Field names and structure align with your realized artefact registries, not just the theoretical template.

### **Generalization**

* The structure is **flexible**: additional optional fields like `notes`, `owner`, `last_updated`, `environment`, or `schema` can be added as needed—see your 1A–4B files for examples.
* This template is directly compatible with JSON Schema validation and CI/CD automation.

---

**If you want a ready-to-use copy, just copy this template and fill in/expand the artefact blocks per subsegment as you add artefacts. You can easily automate instantiation with scripting or YAML templating tools.**

Let me know if you need a minimal, "blank" template (for bootstrapping), or a fully annotated sample for a specific sub-segment!


| Document                                         | Why it exists (one-liner)                                                                                                                                       |
|--------------------------------------------------| --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `artefact_registry`                              | Lists every immutable binary/data artefact the layer needs.                                                                                                     |
| ` dataset_dictionary.layer1.yaml`                | Global lookup of all datasets & columns in the layer (downstream can find any field here).                                                                      |
| `schemas.<ID>.yaml`                              | Full column/type schema for each sub-segment’s inputs & outputs.                                                                                                |
| `invariants.<ID>.yaml`                           | Semantic/structural rules + error contracts the stage must satisfy.                                                                                             |
| `rng_contract.<ID>.yaml`                         | PRNG algorithm, seed derivation, jump rules, retry caps, required RNG audit events.                                                                             |
| `logging_contract.<ID>.yaml`                     | Audit-log file paths, rotation, event taxonomy, required payload fields, coverage rules.                                                                        |
| `performance.<ID>.yaml`                          | Throughput/latency/resource budgets and CI perf-gate targets.                                                                                                   |
| `mathematics_appendix_<ID>.txt`                  | Human math doc: formulas, distributions, algorithm steps.                                                                                                       |
| `function_registry.<ID>.yaml`                    | Machine index of every function in the math appendix: inputs, outputs, RNG, invariants touched.                                                                 |
| `parameter_dictionary.<ID>.yaml`                 | Binds every math symbol/parameter to artefact keys or dataset columns.                                                                                          |
| `interface_contract.<ID>.yaml`                   | Thin index that pins all above component digests for one stage.                                                                                                 |
| `link_contract.<N→N+1>.yaml`                     | Auto-generated proof that Egress(N) is compatible with Ingress(N+1).                                                                                            |
| `error_catalogue.layer1.yaml`                    | Canonical list of all error IDs/codes, severities, required message fields.                                                                                     |
| `id_namespace_registry.layer1.yaml`              | Declares every identifier (merchant_id, site_id, etc.) and RNG namespace: bit-width, sequencing, derivation.                                                  |
| `prior_library.layer1.yaml`                      | Central index of all statistical priors / hyper-parameters with distributions and artefact paths.                                                               |
| `taxonomy.layer1.yaml`                           | Single enum list of log levels, event types, metric names—used by all stages.                                                                                   |
| `layer1_merchant_location_realism.manifest.yaml` | Final lock-down: pins SHA-256 of every sub-segment contract, link contract, shared component, and governing artefact; downstream layers trust this single hash. |

######################################################################################################

######################################################################################################

## `ARTEFACT_REGISTRY.yaml`
Absolutely! Here is a **template for a single, production-ready YAML artefact registry** covering all eight sub-segments (1A–4B), as realized in your actual artefact registries.
This template is generalized from your structure and **annotated for completeness**. It supports placeholder values (e.g., `{semver}`) as per your current build stage, with clear comments explaining the purpose of each field and how placeholders are handled.

---

```yaml
# artefact_registry.yaml
# Central machine-readable registry for all artefacts in merchant-location realism (1A–4B)
# - Designed for strict validation, CI ingest, and deterministic builds
# - Placeholders {like_this} indicate required field to be concretized at build/freeze time

registry_version: "1.0"              # [string] Schema version of this registry format
generated_at: "{iso8601_timestamp}"  # [ISO8601] UTC timestamp when this registry was built/exported
parameter_hash: "{param_hash}"       # [string] Global hash (all configs, code, seeds)
master_seed: "{philox_hex}"          # [string] Philox RNG master seed in hex

build:
  source_sha1: null           # Git tree SHA-1 used to build
  container_image: null       # e.g., gcr.io/project/image:tag
  container_digest: null      # sha256:<...> of the container
  dataset_root: null          # e.g., synthetic_v1_<parameter_hash>

subsegments:
  - id: "1A"
    name: "Merchants to Physical Sites"
    artifacts:
      # Example entry — repeat pattern for all artefacts in 1A
      - name: hurdle_coefficients                 # [string] Short name (no spaces; code-usable)
        path: configs/models/hurdle/hurdle_coefficients.yaml
        type: config                             # [enum] config, data, schema, manifest, log, license, ci_test, script, directory, code, reference, raster, mapping, etc.
        category: hurdle_model                   # [string] High-level grouping for artefact
        semver: "{semver}"                       # [string] Semantic version (placeholder until pinned)
        version: "{config_version}"              # [string] Optional: non-semver version/vintage
        digest: "{sha256}"                       # [string] Content hash (pinned at freeze, placeholder earlier)
        manifest_key: mlr.1A.hurdle.coefficients # [string] Unique manifest digest field
        license: "{spdx_or_internal}"            # [string] SPDX or internal license code
        role: "Coefficients for the logistic hurdle (single vs multi)"  # [string] Human description
        dependencies: [ ]                        # [list] Names of upstream artefacts (by `name`)
        source: internal                         # [string] Origin: internal or external
        owner: { owner_team }                    # [string] Owner team or email
        last_updated: "{iso8601_timestamp}"      # [ISO8601] Last update timestamp (placeholder OK)
        environment: [ runtime ]                 # enum or list: ci|runtime|dev (if applicable)
        schema: null                            # [string/null] Path to schema, if data file
        cross_layer: false                      # [bool] True if used in multiple sub-segments
        notes: null                             # [string/null] Freeform notes, rationale, caveats

      # …repeat above block for each artefact in this subsegment…

  - id: "1B"
    name: "Placing outlets on the planet"
    artifacts:
      # Example artefact entry
      - name: site_catalogue
        path: data/outputs/1B/site_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/
        type: dataset
        category: output
        semver: "{semver}"
        version: "{manifest_fingerprint}"
        digest: "{sha256}"
        manifest_key: mlr.1B.output.site_catalogue
        license: null
        role: "Final per-site rows (coords, tz, remoteness, footfall, provenance); committed atomically via rename."
        dependencies:
          - candidate_pool_index
          - fenwick_snapshot
          # …other dependencies…
        source: internal
        owner: "{owner_team}"
        last_updated: "{iso8601_timestamp}"
        environment: [ runtime ]
        schema: site_catalogue_schema
        cross_layer: true
        notes: "Crash-safe writes; validated by spatial_write_manifest."

      # …repeat for each artefact in this subsegment…

  # --- Repeat for 2A, 2B, 3A, 3B, 4A, 4B (see your per-segment files for field details) ---

# End of registry
```

---

### **How Placeholders Are Handled**

* **Placeholders** (like `{semver}`, `{sha256}`, `{iso8601_timestamp}`) are used for any field whose value will be finalized at build time or after artefact creation.

  * **String fields:** Placeholders are enclosed in curly braces `{like_this}` to ensure validation tools and humans know these must be replaced.
  * **Lists:** Even if dependencies are unknown, use an empty list `[]` as a valid placeholder.
  * **Nullable fields:** Use `null` for non-mandatory fields not yet specified.
  * **Boolean:** `cross_layer: true/false` clarifies cross-segment artefact reuse.

### **Comments & Documentation**

* Inline YAML comments explain the type/role of each field.
* Each artefact should have a unique `manifest_key` for manifest tracking.
* Field names and structure align with your realized artefact registries, not just the theoretical template.

### **Generalization**

* The structure is **flexible**: additional optional fields like `notes`, `owner`, `last_updated`, `environment`, or `schema` can be added as needed—see your 1A–4B files for examples.
* This template is directly compatible with JSON Schema validation and CI/CD automation.

---



######################################################################################################

######################################################################################################

## `DATASET_DICTIONARY.<LAYER-ID>.yaml` (layer scope))

Below are is the template for ( `dataset_dictionary.layer1.yaml` ).

> **File:** `dataset_dictionary.layer1.yaml`
> *Use once per layer; each sub-segment references rows here.*

```yaml
# dataset_dictionary.layer1.yaml — machine-readable catalogue of every dataset produced or consumed in Layer 1
version: "1.0"

lifecycle:
  phase: "planning"           # planning|alpha|beta|stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"]

layer:
  id: "layer1"
  name: "Merchant Location Realism"

datasets:
  - id: "merchant_core"                 # short, unique key
    status: "proposed"                  # proposed|approved|deprecated
    owner_subsegment: "1A"              # where it is first produced
    description: "Per-merchant attributes used by Layer 1 generators"
    format: "parquet"                   # parquet|csv|jsonl|npz|avro|sqlite
    partitioning: []                    # list of directory partition keys (if any)
    ordering: []                        # sort keys inside each file
    schema_ref: "schemas.1A.yaml#/ingress/datasets/0/columns"
    columns:
      - name: "merchant_id"
        dtype: "int64"
        semantics: "Synthetic merchant identifier"
      - name: "mcc"
        dtype: "int32"
        semantics: "Merchant Category Code"
      - name: "home_country_iso"
        dtype: "char(2)"
        semantics: "ISO 3166-1 alpha-2 home country"
      - name: "channel"
        dtype: "string"
        semantics: "card_present/card_not_present"
    lineage:
      produced_by: "import_seed_data"   # job or function
      consumed_by: ["1A","1B","2B"]     # list of sub-segments
      final_in_layer: false
    retention_days: 365
    pii: false
    licence: "Proprietary-Internal"

  - id: "outlet_catalogue"
    status: "proposed"
    owner_subsegment: "1A"
    description: "Outlet stubs prior to coordinate placement"
    format: "parquet"
    partitioning: []                    # path uses seed & fingerprint; no hive partitions
    ordering: ["merchant_id","legal_country_iso","tie_break_rank"]
    schema_ref: "schemas.1A.yaml#/egress/datasets/0/columns"
    columns_ref: "schemas.1A.yaml#/egress/datasets/0/columns"   # shortcut if identical
    lineage:
      produced_by: "1A"
      consumed_by: ["1B"]
      final_in_layer: false
    retention_days: 365
    pii: false
    licence: "Proprietary-Internal"

  # ── Add one block per dataset across all sub-segments (sites, tz_lookups, routed_tx, edge_catalogue, validation bundles, etc.) ──

integrity:
  bundled_schema_sha256: null      # CI fills with digest of concatenated schema JSON
  dataset_count: null              # CI asserts expected count

open_questions:
  - id: "route_output_shape"
    note: "Do routed_transaction outputs become an explicit dataset in Layer 1 or only stream?"
    owner: "data-modelling"
    due_by: null

waivers:
  - id: "missing_retention_policy"
    covers_datasets: ["edge_catalogue"]
    reason: "SRE review pending"
    expires_on: "2025-10-15"
```

**Key points**

* **One file per layer**—not per sub-segment—so downstream specs have a single lookup table.
* Each dataset row includes a `schema_ref` that points into the authoritative `schemas.<ID>.yaml` file, avoiding duplication.
* `lineage.produced_by` / `consumed_by` lets CI auto-check that every referenced dataset has both a writer and at least one reader, or is explicitly marked `final_in_layer: true`.
* `integrity.bundled_schema_sha256` lets your release process pin *all* Layer 1 schema digests with one hash.

---


######################################################################################################

######################################################################################################

## `SCHEMAS.<ID>.yaml`
Great—let’s start with a **single YAML template** you’ll reuse for **each sub‑segment** to record dataset schemas (both **ingress** and **egress**). Keep everything you haven’t finalized as `null` or `"TBD"` so it’s clear what remains to fill.

---

### Canonical schema file (per sub‑segment)

Save as: `schemas.<SUBSEGMENT_ID>.yaml`
Example filenames: `schemas.1A.yaml`, `schemas.2B.yaml`, …

```yaml
# schemas.<SUBSEGMENT_ID>.yaml  — authoritative schema record for one sub-segment
version: "1.0"

lifecycle:
  phase: "planning"             # planning|alpha|beta|stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"]   # disallow placeholders once hardened


subsegment:
  id: "TBD"               # e.g., "1A"
  name: "TBD"             # e.g., "Merchants to Physical Sites"
  owner: "TBD team/email"
  doc_url: null           # link to design doc / runbook

# Enumerate the exact input datasets this stage reads, with full schemas
ingress:
  datasets:
    - name: "TBD_input_name"          # logical dataset name
      description: "TBD"
      format: "parquet"               # parquet|avro|jsonl|csv|npz|sqlite
      location: null                  # optional path/URI/prefix if fixed
      schema_version: 1               # bump when schema breaks compatibility
      partitioning: []                # expected partition keys (if any)
      primary_key: []                 # ["merchant_id", "site_id"] if applicable
      ordering: []                    # expected sort columns if any
      columns:
        - name: "TBD"
          type: "TBD"                 # see allowed type hints below
          nullable: false
          semantics: "TBD"            # human meaning, e.g., "WGS84 latitude"
          constraints:
            valid_range: null         # [min, max] for numeric; or null
            enum: null                # list of allowed values; or null
            pattern: null             # regex string for text; or null
            unique: false
            fk: null                  # { dataset: "other_ds", column: "id" } if foreign key
          encoding: null              # e.g., "utf-8", "zstd", "decimal(12,2)"
          units: null                 # e.g., "degrees", "minutes", "ms since epoch"
          example: null               # optional example value

# Enumerate the exact output datasets this stage writes, with complete schemas
egress:
  datasets:
    - name: "TBD_output_name"
      description: "TBD"
      format: "parquet"
      location_template: null         # e.g., ".../seed={seed}/fingerprint={fp}/part-*.parquet"
      schema_version: 1
      partitioning:
        by: []                        # e.g., ["partition_date","merchant_id"]
      ordering: []                    # e.g., ["merchant_id","site_id"]
      footer_metadata:                # key/value flags you guarantee to write
        creator_param_hash: true
        additional_kv:
          - key: "TBD_manifest_key"   # e.g., spatial_manifest_digest
            required: true
      primary_key: []                 # if records are unique by these columns
      columns:
        - name: "TBD"
          type: "TBD"
          nullable: false
          semantics: "TBD"
          constraints:
            valid_range: null
            enum: null
            pattern: null
            unique: false
            fk: null
          encoding: null
          units: null
          example: null

# Optional performance/volume hints for schema-aware checks (not SLAs)
profile:
  expected_rows_min: null
  expected_rows_max: null
  expected_row_size_bytes: null

# Machine validation controls (CI can enforce these)
validation:
  forbid_extra_columns: true          # fail if columns beyond this spec appear
  require_all_columns: true           # fail if any listed column is missing
  strict_types: true                  # fail on type mismatch (exact logical type)
  allow_metadata_superset: true       # Parquet footer may contain extra metadata

# Reference: allowed logical type hints (document-only; not parsed by tools)
# int8|int16|int32|int64|uint32|uint64|float32|float64|bool|string|binary
# decimal(p,s)|date32|time32[s]|timestamp[ms]|timestamp[ms, tz=UTC]
# list<type>|struct<field:type,...>
```

---

### How to use this template

1. **Copy it once per sub‑segment** (1A … 4B).
2. For each **ingress** dataset, fill its schema exactly as implemented (column names, types, nullability, constraints).
3. For each **egress** dataset, do the same—and include **partitioning**, **ordering**, and any **footer metadata** you guarantee to write.
4. Keep anything not yet decided as `null`/`"TBD"` until CI populates or reviewers approve.

---

### Optional: tiny column snippet for quick copy‑paste

```yaml
- name: "COLUMN_NAME"
  type: "TYPE_HINT"
  nullable: false
  semantics: "WHAT_THIS_FIELD_MEANS"
  constraints: { valid_range: null, enum: null, pattern: null, unique: false, fk: null }
  encoding: null
  units: null
  example: null
```

---

### filled stub
Below is a **filled stub** of the *schemas file* for **Sub‑segment 1A** using the template we agreed on. I’ve filled everything the current docs make concrete and left truly undecided items as `null`/`"TBD"`. Notes right after the YAML point to the exact places these fields are specified.

---

#### `schemas.1A.yaml` (filled stub)

```yaml
# schemas.1A.yaml — authoritative schema record for Sub‑segment 1A
version: "1.0"

subsegment:
  id: "1A"
  name: "Merchants to Physical Sites"
  owner: "TBD"
  doc_url: null

ingress:
  datasets:
    - name: "merchant_core"
      description: "Per-merchant attributes required by the 1A generator"
      format: "parquet"
      location: null
      schema_version: 1
      partitioning: []
      primary_key: ["merchant_id"]
      ordering: []
      columns:
        - name: "merchant_id"
          type: "int64"
          nullable: false
          semantics: "Synthetic merchant identifier"
          constraints: { valid_range: null, enum: null, pattern: null, unique: true, fk: null }
          encoding: null
          units: null
          example: 123456789
        - name: "mcc"
          type: "TBD"                      # ISO 18245 MCC (usually 4-digit integer)
          nullable: false
          semantics: "Merchant Category Code"
          constraints: { valid_range: null, enum: null, pattern: null, unique: false, fk: null }
          encoding: null
          units: null
          example: 5812
        - name: "home_country_iso"
          type: "string"
          nullable: false
          semantics: "ISO‑3166‑1 alpha‑2 of merchant’s home country"
          constraints: { valid_range: null, enum: null, pattern: "^[A-Z]{2}$", unique: false, fk: null }
          encoding: "utf-8"
          units: null
          example: "US"
        - name: "channel"
          type: "string"                   # e.g., "card_present" / "card_not_present" (TBD exact enum)
          nullable: false
          semantics: "Sales channel used in hurdle/NB models"
          constraints: { valid_range: null, enum: null, pattern: null, unique: false, fk: null }
          encoding: "utf-8"
          units: null
          example: "card_present"

egress:
  datasets:
    - name: "outlet_catalogue"
      description: "Outlet stubs by merchant/country prior to 1B coordinate sampling"
      format: "parquet"
      location_template: ".../outlet_catalogue/seed={seed}/fingerprint={fingerprint}/part-*.parquet"
      schema_version: 1
      partitioning:
        by: []                             # path embeds seed/fingerprint; not physical partitions
      ordering: ["merchant_id","legal_country_iso","tie_break_rank"]
      footer_metadata:
        creator_param_hash: true
        additional_kv:
          - key: "compression"
            required: true
      primary_key: []                      # uniqueness not guaranteed across all columns
      columns:
        - name: "merchant_id"
          type: "int64"
          nullable: false
          semantics: "Synthetic merchant identifier"
          constraints: { valid_range: null, enum: null, pattern: null, unique: false, fk: null }
          encoding: null
          units: null
          example: 123456789
        - name: "site_id"
          type: "string"
          nullable: false
          semantics: "Per-(merchant,legal_country) 6-digit zero-padded sequence"
          constraints: { valid_range: null, enum: null, pattern: "^[0-9]{6}$", unique: false, fk: null }
          encoding: "utf-8"
          units: null
          example: "000123"
        - name: "home_country_iso"
          type: "string"
          nullable: false
          semantics: "ISO‑3166‑1 alpha‑2 of merchant’s home country"
          constraints: { valid_range: null, enum: null, pattern: "^[A-Z]{2}$", unique: false, fk: null }
          encoding: "utf-8"
          units: null
          example: "US"
        - name: "legal_country_iso"
          type: "string"
          nullable: false
          semantics: "ISO‑3166‑1 alpha‑2 of the outlet’s legal‑seat country"
          constraints: { valid_range: null, enum: null, pattern: "^[A-Z]{2}$", unique: false, fk: null }
          encoding: "utf-8"
          units: null
          example: "GB"
        - name: "single_vs_multi_flag"
          type: "bool"
          nullable: false
          semantics: "1 if multi‑site (hurdle=success), else 0"
          constraints: { valid_range: null, enum: null, pattern: null, unique: false, fk: null }
          encoding: null
          units: null
          example: true
        - name: "raw_nb_outlet_draw"
          type: "int32"
          nullable: false
          semantics: "Accepted NB draw for domestic outlets before cross‑border allocation"
          constraints: { valid_range: null, enum: null, pattern: null, unique: false, fk: null }
          encoding: null
          units: null
          example: 17
        - name: "final_country_outlet_count"
          type: "int32"
          nullable: false
          semantics: "Integer outlet count allocated to this legal_country after Dirichlet + LRR"
          constraints: { valid_range: null, enum: null, pattern: null, unique: false, fk: null }
          encoding: null
          units: null
          example: 5
        - name: "tie_break_rank"
          type: "int32"
          nullable: false
          semantics: "Position in deterministic residual ordering (for LRR tie breaks)"
          constraints: { valid_range: null, enum: null, pattern: null, unique: false, fk: null }
          encoding: null
          units: null
          example: 2
        - name: "manifest_fingerprint"
          type: "string"
          nullable: false
          semantics: "Hex‑encoded SHA‑256 lineage fingerprint"
          constraints: { valid_range: null, enum: null, pattern: "^[a-f0-9]{64}$", unique: false, fk: null }
          encoding: "utf-8"
          units: null
          example: "3f0c...abcd"
        - name: "global_seed"
          type: "uint64"
          nullable: false
          semantics: "Philox sub‑stream seed identifier for this stub"
          constraints: { valid_range: null, enum: null, pattern: null, unique: false, fk: null }
          encoding: null
          units: null
          example: 1844674407370955161

profile:
  expected_rows_min: null
  expected_rows_max: null
  expected_row_size_bytes: null

validation:
  forbid_extra_columns: true
  require_all_columns: true
  strict_types: true
  allow_metadata_superset: true
```

**What this stub is grounded on (so you can verify quickly):**

* **Egress columns, types, and ZSTD‑level‑3 compression** are spelled out in the 1A narrative (the 10 non‑nullable fields and the output path template).
* **Ordering and `tie_break_rank` semantics** (deterministic residual ordering from largest‑remainder rounding) are also described in the narrative.&#x20;
* **Ingress fields**: 1A’s modeling depends on **home country**, **MCC**, and **channel** (used in the hurdle and NB links), and the **merchant\_id** used throughout; these are referenced across the 1A narrative/assumptions. I’ve typed `home_country_iso` and given a regex; `mcc`/`channel` are left `TBD` for exact typing/enums so you don’t over‑commit prematurely.


######################################################################################################

######################################################################################################

## `INVARIANTS.<ID>.yaml`

Great—here’s a compact **Invariant Spec** you can reuse per sub‑segment, plus a **filled 1A example** to show how it looks when populated.

---

### 1) Reusable invariant template (per sub‑segment)

Save as: `invariants.<SUBSEGMENT_ID>.yaml`
(Example: `invariants.1A.yaml`, `invariants.2B.yaml`, …)

```yaml
# invariants.<SUBSEGMENT_ID>.yaml — authoritative invariant spec for one sub‑segment
version: "1.0"

lifecycle:
  phase: "planning"             # planning|alpha|beta|stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"]   # disallow placeholders once hardened


subsegment:
  id: "TBD"            # e.g., "1A"
  name: "TBD"
  owner: "TBD team/email"
  doc_url: null

defaults:
  severity: "error"    # error|warn
  action_on_violation: "abort"   # abort|block_merge|log_only
  evaluation_phase: "post"       # pre|during|post|ci
  applies_to: "egress"           # ingress|egress|both

invariants:
  - id: "TBD_invariant_id"       # short, stable; kebab/snake case
    title: "TBD one‑line summary"
    category: "semantic"         # structural|semantic|stochastic|performance|privacy|logging
    applies_to: "egress"         # overrides defaults if needed
    severity: "error"
    action_on_violation: "abort"
    evaluation_phase: "post"     # when you validate
    scope:
      dataset: "TBD_output_name" # or input dataset if ingress
      level: "row"               # dataset|partition|row|column|system
      columns: []                # optional, if column‑level
    description: "Plain language description of the rule."
    tolerance: null              # e.g., "abs(delta) <= 0.02", or null if strict
    expression:                  # machine‑checkable expression(s); pick the stanza your CI uses
      sql: null                  # SQL that must return 0 failing rows
      py: null                   # Python pseudo‑check; return True when satisfied
      jsonlogic: null            # optional alternative
    exception:                   # if this rule maps to a canonical error
      name: null                 # e.g., "ZTPOisonRetryExhausted"
      code: null                 # e.g., "E1A001"
      must_include_fields: []    # required keys in error payload/log
    references:
      - type: "spec"
        note: "Pointer to narrative/assumptions section"
        url: null
    tests:                       # how CI proves the rule is enforced
      synthetic_vectors: null    # path to small test data
      expect: "pass"             # pass|fail (for negative test)
      seed: null

# Optional: groups are logical bundles you can enable/disable in CI
groups:
  - id: "strict_egress_checks"
    includes: ["TBD_invariant_id", "another_id"]
```

#### Categories to use

* **structural**: schema/typing/partitioning (e.g., “no extra columns”).
* **semantic**: business meaning (e.g., “sum of shares = 1”, ISO codes format).
* **stochastic**: RNG/accept‑reject rules, reproducibility invariants.
* **performance**: batch sizes, latency ceilings (often CI only).
* **privacy**: PII flags, license presence.
* **logging**: required audit fields/events.

---

### 2) Filled example for **Sub‑segment 1A** (guide)

This mirrors the rules you’ve already documented. Keep any still‑undecided bits as `null/TBD` and wire them later.

```yaml
# invariants.1A.yaml — filled guide for Sub‑segment 1A
version: "1.0"

subsegment:
  id: "1A"
  name: "Merchants to Physical Sites"
  owner: "TBD"
  doc_url: null

defaults:
  severity: "error"
  action_on_violation: "abort"
  evaluation_phase: "post"
  applies_to: "egress"

invariants:

  - id: "nb-multi-requires-N>=2"
    title: "Multi-site merchants must have NB draw N ≥ 2"
    category: "stochastic"
    scope: { dataset: "outlet_catalogue", level: "row" }
    description: "If hurdle outcome is multi-site, the accepted Negative-Binomial draw cannot be 0 or 1."
    expression:
      sql: >
        SELECT COUNT(*) AS failures
        FROM outlet_catalogue
        WHERE single_vs_multi_flag = TRUE AND raw_nb_outlet_draw < 2;
    exception:
      name: "NBRejectionLoopViolation"
      code: "E1A-NB-001"
      must_include_fields: ["merchant_id","raw_nb_outlet_draw","rejection_count"]

  - id: "ztp-cap-64"
    title: "ZTP rejection retries ≤ 64"
    category: "stochastic"
    scope: { dataset: "outlet_catalogue", level: "system" }
    description: "Zero-truncated Poisson sampling must not exceed 64 rejections; else emit ztp_retry_exhausted and abort."
    expression:
      py: "assert max(ztp_rejection_attempts) <= 64"
    exception:
      name: "ZTPOisonRetryExhausted"
      code: "E1A-ZTP-064"
      must_include_fields: ["lambda_extra","rejection_count","merchant_id"]

  - id: "dirichlet-lrr-bound"
    title: "Largest‑remainder rounding: |n_i − w_i·N| ≤ 1"
    category: "semantic"
    scope: { dataset: "outlet_catalogue", level: "partition", columns: ["final_country_outlet_count"] }
    description: "Dirichlet weights rounded by LRR with residual quantised to 8dp and deterministic ISO tie‑break; per merchant, integer error no larger than 1 per country."
    tolerance: "abs(n_i - w_i*N) <= 1"
    expression:
      py: "check_lrr_residuals(df)"   # your harness function

  - id: "rng-events-complete"
    title: "Required RNG audit events present per merchant"
    category: "logging"
    applies_to: "both"
    scope: { dataset: "rng_audit_log", level: "partition" }
    description: "Each merchant must have the full sequence of RNG events: hurdle_bernoulli, gamma_component, poisson_component, nb_final, (optional ztp_*), gumbel_key, dirichlet_gamma_vector, stream_jump, sequence_finalize."
    expression:
      sql: >
        WITH expected(event_type) AS (
          SELECT * FROM (VALUES
            ('hurdle_bernoulli'),('gamma_component'),('poisson_component'),
            ('nb_final'),('gumbel_key'),('dirichlet_gamma_vector'),
            ('stream_jump'),('sequence_finalize')
          ) AS t(event_type)
        )
        SELECT merchant_id
        FROM rng_audit_log
        GROUP BY merchant_id
        HAVING COUNT(DISTINCT event_type) FILTER (WHERE event_type IN (SELECT event_type FROM expected)) < 8;
    exception:
      name: "RNGAuditMissingEvents"
      code: "E1A-RNG-001"
      must_include_fields: ["merchant_id","missing_events"]

  - id: "iso2-codes-format"
    title: "ISO‑3166 alpha‑2 formatting on country columns"
    category: "structural"
    scope: { dataset: "outlet_catalogue", level: "column", columns: ["home_country_iso","legal_country_iso"] }
    description: "Country codes must be exactly two uppercase letters."
    expression:
      sql: >
        SELECT COUNT(*) AS failures
        FROM outlet_catalogue
        WHERE home_country_iso !~ '^[A-Z]{2}$' OR legal_country_iso !~ '^[A-Z]{2}$';

  - id: "site-id-format"
    title: "site_id must be 6‑digit zero‑padded"
    category: "structural"
    scope: { dataset: "outlet_catalogue", level: "column", columns: ["site_id"] }
    description: "Deterministic per‑(merchant, country) sequence formatted as ^[0-9]{6}$."
    expression:
      sql: >
        SELECT COUNT(*) AS failures
        FROM outlet_catalogue
        WHERE site_id !~ '^[0-9]{6}$';

  - id: "path-policy"
    title: "Output path embeds seed & fingerprint"
    category: "structural"
    scope: { dataset: "outlet_catalogue", level: "system" }
    description: "Output path MUST follow .../seed={seed}/fingerprint={fingerprint}/ partitioning."
    expression:
      py: "assert all('seed=' in p and 'fingerprint=' in p for p in output_paths)"

  - id: "imm-utxo"
    title: "creator_param_hash & manifest_fingerprint present"
    category: "semantic"
    scope: { dataset: "outlet_catalogue", level: "row", columns: ["manifest_fingerprint"] }
    description: "Every row carries the lineage fingerprint in the footer metadata and column, enabling full replay."
    expression:
      sql: >
        SELECT COUNT(*) AS failures
        FROM outlet_catalogue
        WHERE manifest_fingerprint IS NULL OR length(manifest_fingerprint) <> 64;

exceptions:
  - name: "ZTPOisonRetryExhausted"
    must_include_fields: ["lambda_extra","rejection_count","merchant_id"]
  - name: "NBRejectionLoopViolation"
    must_include_fields: ["merchant_id","raw_nb_outlet_draw","rejection_count"]
  - name: "RNGAuditMissingEvents"
    must_include_fields: ["merchant_id","missing_events"]

groups:
  - id: "strict_egress_checks"
    includes:
      - "nb-multi-requires-N>=2"
      - "dirichlet-lrr-bound"
      - "rng-events-complete"
      - "iso2-codes-format"
      - "site-id-format"
      - "path-policy"
      - "imm-utxo"
```

---

#### How to use this effectively

* **Author once per sub‑segment.** Keep it alongside your `schemas.<ID>.yaml`.
* **Make CI executable:** your validator just needs to interpret the `expression.sql`/`expression.py` stanzas and assert “no failures.”
* **Message contracts:** list required fields in `exceptions.must_include_fields` so error payloads are uniform across stages.
* **Groups:** let you toggle strict bundles (e.g., everything that must pass to emit a “validation\_passed=true”).







######################################################################################################

######################################################################################################

## `RNG_CONTRACT.<ID>.yaml`

Here’s a **planning‑friendly RNG/Determinism contract template** you can use **per sub‑segment**. It matches the style of your schema/invariant templates (lifecycle, CI policy, open questions, waivers), but focuses on seed sources, stream partitioning, jump rules, rejection caps, auditability, and replay.

> Save as: `rng_contract.<SUBSEGMENT_ID>.yaml` (e.g., `rng_contract.1A.yaml`)

```yaml
# rng_contract.<SUBSEGMENT_ID>.yaml — authoritative RNG & determinism spec for one sub‑segment
version: "1.0"

lifecycle:
  phase: "planning"             # planning|alpha|beta|stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"]   # disallow placeholders once hardened

subsegment:
  id: "TBD"                     # e.g., "1A"
  name: "TBD"
  owner: "TBD team/email"
  doc_url: null

prng:
  algorithm: "TBD"              # e.g., "philox-2x64-10"
  implementation: "TBD"         # e.g., "numpy.random.Generator(Philox)"
  version_pin: null             # library/runtime pin to ensure bit‑stability
  state_bits: null              # e.g., 256
  counter_bits: null            # e.g., 128
  key_bits: null                # e.g., 64 or 128
  endianness: "little"          # if binary files/logs are produced

seed_material:
  consumes_fields:              # upstream manifest/inputs required to derive seeds
    - "parameter_hash"
    - "master_seed"
    - "manifest_fingerprint"    # remove if not used by this stage
    - "run_seed"                # remove if not used by this stage
  master_seed_derivation:
    description: "TBD"          # e.g., "SHA256(parameter_hash || run_seed)[:16]"
    pseudocode: null
  substream_derivation:
    namespace: "TBD"            # e.g., "1A-hurdle", "router", "cdp-gamma"
    key_format: "TBD"           # e.g., "SHA256(master_seed || namespace || merchant_id)"
    variables:
      - "merchant_id"
      - "country_iso"
      - "day_index"
  entropy_domains:              # explicit domain‑separation to avoid cross‑stage collisions
    - name: "TBD_domain"
      label: "TBD_label"        # fixed string baked into key derivation

streams:
  partitioning_policy: "TBD"    # e.g., "per-merchant", "per-(merchant,country)", "per-day"
  jump_policy:
    method: "TBD"               # e.g., "counter_jump", "skip_ahead"
    stride_source: "TBD"        # e.g., "SHA256(namespace || id)[:16]"
    log_every_jump: true
  limits:
    max_draws_per_stream: null  # safety cap (fail if exceeded)
    max_jump_stride: null       # safety cap
    counter_wrap_behavior: "abort"  # abort|rollover (abort recommended)
  ordering_guarantee: "stable"  # stable|none — stable => same call order yields same draws

rejection_sampling:
  policies:
    - id: "ztp_poisson"
      description: "Zero‑truncated Poisson sampler"
      cap_retries: 64           # set null/TBD until finalized
      on_exhaustion: "raise"
      exception:
        name: "ZTPOissonRetryExhausted"
        code: "TBD"
        must_include_fields: ["lambda_extra","rejection_count","identifier"]
    - id: "nb_rejection"
      description: "Reject NB draws {0,1} for multi‑site case"
      cap_retries: null
      on_exhaustion: "raise"
      exception:
        name: "NBRejectionLoopViolation"
        code: "TBD"
        must_include_fields: ["merchant_id","raw_nb_outlet_draw","rejection_count"]

deterministic_tie_breaks:
  rules:
    - id: "dirichlet_lrr"
      description: "Largest‑remainder rounding with residual quantisation & ISO order tiebreak"
      hash_or_order: "ISO-asc"
      quantisation: "1e-8"
    - id: "fold_parity"
      description: "DST fold parity bit selection"
      hash_function: "SHA256"
      input_tuple: ["global_seed","site_id","t_local"]
      modulo: 2

numerical_environment:
  precision: "binary64"         # binary64|binary32
  fma: "disabled"               # disabled|enabled (if it affects results)
  rounding_mode: "ties-to-even" # if relevant
  random_float_open_interval: "(0,1]"  # or "[0,1)"
  quantisation:
    residuals_dp: 8             # for residual sorts/ties (if applicable)

audit_logging:
  files:
    - path: "logs/rng/rng_audit.log"
      rotation_policy: "daily_90d"
      fields:                   # MUST emit these per draw/jump/event
        - "timestamp_utc"
        - "event_type"          # e.g., hurdle_bernoulli, gamma_component, ...
        - "identifier"          # merchant_id/site_id/edge_id as appropriate
        - "pre_counter"
        - "post_counter"
        - "stride_key"          # if jump
        - "parameter_hash"
        - "sequence_index"
        - "rejection_flag"
      redact_fields: []         # if any sensitive values must be masked
  required_event_set:
    - "hurdle_bernoulli"
    - "gamma_component"
    - "poisson_component"
    - "nb_final"
    - "ztp_rejection"
    - "ztp_retry_exhausted"
    - "gumbel_key"
    - "dirichlet_gamma_vector"
    - "stream_jump"
    - "sequence_finalize"

determinism_guarantees:
  stability_contract:
    - "Given identical inputs (artifacts+dIGESTs, seeds, and call order), outputs are bit‑stable."
    - "Substream keys are fully determined by declared variables and namespace."
  nondeterminism_sources: []     # list if any (e.g., multithread race) — ideally empty
  parallelism_constraints:
    execution_model: "TBD"       # single-thread|per-merchant parallel|map-reduce
    scheduling_invariance: true  # true => results independent of scheduling

replay_contract:
  requirements:
    - "rng_audit.log present with matching required_event_set"
    - "All seed_material fields logged in manifest"
  checksum:
    formula: "SHA256(merchant_id || batch_index || cumulative_counts_vector)"
    frequency: "every_1e6_events"
  test_vectors:
    path: null
    seed: null
    expected_first_n: null       # optional known outputs for smoke‑tests

constraints_limits:
  timeouts_ms: null
  memory_ceiling_mb: null
  max_open_files: null

exceptions:                      # canonical RNG/Determinism exceptions for this stage
  - name: "RNGAuditMissingEvents"
    code: "TBD"
    must_include_fields: ["merchant_id","missing_events"]
  - name: "CounterWrapError"
    code: "TBD"
    must_include_fields: ["identifier","counter_value"]

migration_policy:
  algorithm_upgrade:
    requires: ["major_version_bump","RFC"]
    backcompat: "no"            # yes|no — whether mixed runs allowed
  seed_change:
    allowed: "no"               # if yes, specify consequences
    requires: ["reseed_procedure"]

security:
  seed_handling:
    classification: "confidential"  # public|internal|confidential
    storage: "TBD"                  # where seeds are stored
    rotation: null                  # policy if any

open_questions:
  - id: "prng-selection"
    note: "Confirm PRNG algorithm and implementation pin"
    owner: "TBD"
    due_by: null

waivers:
  - id: "ztp-retry-cap-waiver"
    reason: "Under review with risk"
    expires_on: "2025-09-30"
```

---

Below is a **filled RNG/Determinism contract stub for Sub‑segment 1A** using the template we agreed on. I’ve populated only what your 1A docs make explicit and left anything truly undecided as `null`/`"TBD"`. After the YAML, I added short notes pointing to where each filled item comes from in your files.

---

### `rng_contract.1A.yaml` — filled planning stub

```yaml
# rng_contract.1A.yaml — authoritative RNG & determinism spec for Sub‑segment 1A
version: "1.0"

lifecycle:
  phase: "planning"
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"]

subsegment:
  id: "1A"
  name: "Merchants to Physical Sites"
  owner: "TBD"
  doc_url: null

prng:
  algorithm: "philox-2x64 (2^128 counter)"
  implementation: "TBD"          # e.g., numpy.random.Generator(Philox)
  version_pin: null
  state_bits: 128
  counter_bits: 128
  key_bits: null
  endianness: "little"

seed_material:
  consumes_fields:
    - "manifest_fingerprint"
    - "run_seed"
    - "parameter_hash"            # present in logs; not used by the master-seed formula
  master_seed_derivation:
    description: "master = H(manifest_fingerprint || run_seed)"
    pseudocode: null
  substream_derivation:
    namespace: "1A"
    key_format: "first_64_bits_little_endian_of_SHA256(<string_key>)"
    variables:
      - "merchant_id"
  entropy_domains:
    - name: "hurdle"
      label: "hurdle_bernoulli"
    - name: "cross_border_alloc"
      label: "cross-border-allocation"   # module-specific jump/event label

streams:
  partitioning_policy: "per-merchant"
  jump_policy:
    method: "counter_jump"
    stride_source: "first 64 little-endian bits of SHA-256(<string_key>)"
    log_every_jump: true
  limits:
    max_draws_per_stream: null
    max_jump_stride: null
    counter_wrap_behavior: "abort"
  ordering_guarantee: "stable"

rejection_sampling:
  policies:
    - id: "ztp_poisson"
      description: "Zero-truncated Poisson for K (foreign country count)"
      cap_retries: 64
      on_exhaustion: "raise"
      exception:
        name: "ZTPOissonRetryExhausted"
        code: "TBD"
        must_include_fields: ["lambda_extra","rejection_count","merchant_id"]
    - id: "nb_rejection"
      description: "Reject NB draws {0,1} for multi-site merchants until N≥2"
      cap_retries: null
      on_exhaustion: "raise"
      exception:
        name: "NBRejectionLoopViolation"
        code: "TBD"
        must_include_fields: ["merchant_id","raw_nb_outlet_draw","rejection_count"]

deterministic_tie_breaks:
  rules:
    - id: "dirichlet_lrr"
      description: "Largest-remainder rounding with residual quantisation & ISO-ascending tiebreak"
      hash_or_order: "ISO-asc"
      quantisation: "1e-8"

numerical_environment:
  precision: "binary64"
  fma: "disabled"                 # for Dirichlet & residual ops
  rounding_mode: "ties-to-even"
  random_float_open_interval: null
  quantisation:
    residuals_dp: 8

audit_logging:
  files:
    - path: "logs/rng/rng_audit.log"
      rotation_policy: "daily_90d"
      fields:
        - "timestamp_utc"
        - "event_type"
        - "merchant_id"
        - "pre_counter"
        - "post_counter"
        - "parameter_hash"
        - "draw_sequence_index"
        - "rejection_flag"
      redact_fields: []
  required_event_set:
    - "hurdle_bernoulli"
    - "gamma_component"
    - "poisson_component"
    - "nb_final"
    - "ztp_rejection"
    - "ztp_retry_exhausted"
    - "gumbel_key"
    - "dirichlet_gamma_vector"
    - "stream_jump"
    - "sequence_finalize"

determinism_guarantees:
  stability_contract:
    - "Given identical inputs (manifest_fingerprint, run_seed) and call order, outputs are bit-stable."
    - "Substream keys and jumps derive from fixed string keys and merchant_id."
  nondeterminism_sources: []
  parallelism_constraints:
    execution_model: "TBD"
    scheduling_invariance: true

replay_contract:
  requirements:
    - "rng_audit.log present with required_event_set"
    - "manifest_fingerprint and run_seed captured in manifest"
  checksum:
    formula: null
    frequency: null
  test_vectors:
    path: null
    seed: null
    expected_first_n: null

constraints_limits:
  timeouts_ms: null
  memory_ceiling_mb: null
  max_open_files: null

exceptions:
  - name: "RNGAuditMissingEvents"
    code: "TBD"
    must_include_fields: ["merchant_id","missing_events"]
  - name: "CounterWrapError"
    code: "TBD"
    must_include_fields: ["merchant_id","counter_value"]

migration_policy:
  algorithm_upgrade:
    requires: ["major_version_bump","RFC"]
    backcompat: "no"
  seed_change:
    allowed: "no"
    requires: ["reseed_procedure"]

security:
  seed_handling:
    classification: "confidential"
    storage: "TBD"
    rotation: null

open_questions:
  - id: "rng-impl-pin"
    note: "Pin exact PRNG implementation/library for bit-stability"
    owner: "TBD"
    due_by: null

waivers:
  - id: "ztp-retry-cap-finalise"
    reason: "Cap agreed in prose; code audit pending"
    expires_on: "2025-09-30"
```

---

### Why these fields are filled (with pointers)

* **Master seed derivation** – “Philox 2¹²⁸ master seed = H(manifest fingerprint || run seed).”&#x20;
* **Audit‑log fields & required events** – exact header and the mandatory event set (`hurdle_bernoulli`, `gamma_component`, `poisson_component`, `nb_final`, `ztp_rejection`, `ztp_retry_exhausted`, `gumbel_key`, `dirichlet_gamma_vector`, `stream_jump`, `sequence_finalize`).&#x20;
* **Sub‑stream jump rule** – “first 64 little‑endian bits of SHA‑256 of a string key,” and example module key `"cross-border-allocation"`; jumps are logged as `stream_jump`.
* **NB rejection policy** – keep drawing until `N ≥ 2` for multi‑site, with counters logged.&#x20;
* **ZTP cap (64)** and abort on exhaustion (`ztp_retry_exhausted`).&#x20;
* **Dirichlet rounding determinism** – residual quantisation to **8 dp** and ISO‑ascending tiebreak; logs include raw gamma deviates and normalised weights.&#x20;
* **Binary64 arithmetic, FMA disabled, serial reductions** – numeric environment constraints for determinism.&#x20;
* **RNG artefacts (seed, logs) anchored in the registry** – `philox_master_counter`, `run_seed`, `rng_audit.log`, `rng_trace.log`.

---



######################################################################################################

######################################################################################################

## `LOGGING_CONTRACT.<ID>.yaml`

Here’s a **planning‑friendly Logging Contract template** you can reuse **per sub‑segment**. It matches the style of your schema and RNG templates (lifecycle, CI policy, open questions, waivers) and is ready for production once you replace `TBD/null`.

> Save as: `logging_contract.<SUBSEGMENT_ID>.yaml` (e.g., `logging_contract.1A.yaml`)

```yaml
# logging_contract.<SUBSEGMENT_ID>.yaml — authoritative logging & audit spec for one sub‑segment
version: "1.0"

lifecycle:
  phase: "planning"                 # planning|alpha|beta|stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"] # when lifecycle escalates, placeholders must be gone

subsegment:
  id: "TBD"                         # e.g., "1A"
  name: "TBD"
  owner: "TBD team/email"
  doc_url: null

logging:
  structured: true                  # JSONL recommended
  format: "jsonl"                   # jsonl|ndjson|csv|text
  encoding: "utf-8"
  time_source: "utc"                # utc|system|monotonic (for event_time fields)
  time_field: "timestamp_utc"       # canonical field carrying RFC3339/ISO 8601 or epoch ms
  time_precision: "ms"              # s|ms|us|ns
  tz: "UTC"
  newline_delimited: true

sinks:                               # where logs go (one or more)
  - id: "file_primary"
    type: "file"                    # file|stdout|http|s3|kafka
    enabled: true
    params:
      path_root: "logs/<stage>/"    # base directory
      fsync_on_rotate: true
  - id: "stdout_fallback"
    type: "stdout"
    enabled: true
    params: {}

files:                               # each concrete log stream this sub‑segment must emit
  - role: "audit"                    # audit|progress|error|metrics|debug
    path: "logs/<stage>/audit.log"
    sink_id: "file_primary"
    rotation:
      policy: "daily"                # daily|size|hourly
      size_mb: null                  # used if policy=size
      compress: true                 # gzip/zstd
      keep_days: 90
    permissions:
      owner: "app"
      group: "data"
      mode: "0640"
    crash_tolerance:
      temp_pattern: "*.tmp"
      atomic_rename: true
      write_strategy: "append-fsync" # append-fsync|append-buffered
    retention:
      archive: false                 # if true, define offload target
      offload_target: null           # s3://bucket/prefix or similar

schema:                               # base schema all events MUST include (can be extended per event_type)
  required_fields:
    - "timestamp_utc"
    - "event_type"
    - "run_id"                       # e.g., UUID or hash of (parameter_hash, master_seed)
    - "parameter_hash"
    - "manifest_fingerprint"
  fields:
    - { name: "timestamp_utc",       type: "timestamp[ms, tz=UTC]", nullable: false, description: "Event time" }
    - { name: "event_type",          type: "string",                nullable: false, description: "Event taxonomy key" }
    - { name: "run_id",              type: "string",                nullable: false, description: "Unique run/session id" }
    - { name: "parameter_hash",      type: "string",                nullable: false, description: "64‑hex parameter set hash", pattern: "^[a-f0-9]{64}$" }
    - { name: "manifest_fingerprint",type: "string",                nullable: false, description: "64‑hex lineage fingerprint", pattern: "^[a-f0-9]{64}$" }
    - { name: "merchant_id",         type: "int64",                 nullable: true,  description: "Entity id if applicable" }
    - { name: "site_id",             type: "string",                nullable: true,  description: "Outlet/site id if applicable" }
    - { name: "pre_counter",         type: "uint64",                nullable: true,  description: "RNG counter before draw/jump" }
    - { name: "post_counter",        type: "uint64",                nullable: true,  description: "RNG counter after draw/jump" }
    - { name: "sequence_index",      type: "uint64",                nullable: true,  description: "Monotone index within sequence" }
    - { name: "rejection_flag",      type: "bool",                  nullable: true,  description: "True if rejection occurred" }
    - { name: "stride_key",          type: "string",                nullable: true,  description: "Jump stride id (if stream_jump)" }
    - { name: "level",               type: "string",                nullable: true,  description: "log level", enum: ["INFO","WARN","ERROR","DEBUG"] }
    - { name: "message",             type: "string",                nullable: true,  description: "Human‑readable note" }
    - { name: "payload",             type: "object",                nullable: true,  description: "Event‑specific fields object" }

event_taxonomy:                        # define every event_type and its extra fields
  - event_type: "hurdle_bernoulli"
    description: "Hurdle decision"
    severity: "INFO"                 # INFO|WARN|ERROR
    must_have_fields: ["merchant_id","pre_counter","post_counter","sequence_index"]
    payload_schema:
      - { name: "pi",               type: "float64", nullable: false, description: "probability" }
      - { name: "outcome",          type: "bool",    nullable: false, description: "decision" }
  - event_type: "gamma_component"
    description: "Gamma draw in NB mixture"
    severity: "INFO"
    must_have_fields: ["merchant_id","pre_counter","post_counter","sequence_index"]
    payload_schema:
      - { name: "shape",            type: "float64", nullable: false }
      - { name: "scale",            type: "float64", nullable: false }
  - event_type: "poisson_component"
    description: "Poisson draw in NB mixture"
    severity: "INFO"
    must_have_fields: ["merchant_id","pre_counter","post_counter","sequence_index"]
    payload_schema:
      - { name: "lambda",           type: "float64", nullable: false }
  - event_type: "nb_final"
    description: "Accepted NB count"
    severity: "INFO"
    must_have_fields: ["merchant_id","pre_counter","post_counter","sequence_index"]
    payload_schema:
      - { name: "count",            type: "int32",   nullable: false }
  - event_type: "ztp_rejection"
    description: "Zero‑truncated Poisson rejection"
    severity: "WARN"
    must_have_fields: ["merchant_id","sequence_index"]
    payload_schema:
      - { name: "lambda_extra",     type: "float64", nullable: false }
      - { name: "attempt",          type: "int32",   nullable: false }
  - event_type: "ztp_retry_exhausted"
    description: "Exceeded max ZTP retries"
    severity: "ERROR"
    must_have_fields: ["merchant_id"]
    payload_schema:
      - { name: "lambda_extra",     type: "float64", nullable: false }
      - { name: "rejection_count",  type: "int32",   nullable: false }
  - event_type: "gumbel_key"
    description: "Gumbel key for candidate selection"
    severity: "INFO"
    must_have_fields: ["merchant_id","sequence_index"]
    payload_schema:
      - { name: "country_iso",      type: "string",  nullable: false, pattern: "^[A-Z]{2}$" }
      - { name: "weight",           type: "float64", nullable: false }
      - { name: "u",                type: "float64", nullable: false }
      - { name: "key",              type: "float64", nullable: false }
  - event_type: "dirichlet_gamma_vector"
    description: "Dirichlet via Gamma draws"
    severity: "INFO"
    must_have_fields: ["merchant_id","sequence_index"]
    payload_schema:
      - { name: "countries",        type: "list<string>", nullable: false }
      - { name: "gamma",            type: "list<float64>", nullable: false }
      - { name: "weights_norm",     type: "list<float64>", nullable: false }
  - event_type: "stream_jump"
    description: "RNG sub‑stream jump"
    severity: "INFO"
    must_have_fields: ["merchant_id","pre_counter","post_counter","stride_key"]
    payload_schema:
      - { name: "module",           type: "string",  nullable: false }
  - event_type: "sequence_finalize"
    description: "End of merchant sequence"
    severity: "INFO"
    must_have_fields: ["merchant_id","sequence_index"]
    payload_schema: []

coverage_requirements:                # event coverage your CI will enforce
  per_entity:
    entity_key: "merchant_id"
    required_events:
      - "hurdle_bernoulli"
      - "gamma_component"
      - "poisson_component"
      - "nb_final"
      - "dirichlet_gamma_vector"
      - "sequence_finalize"
  system_wide:
    must_emit_files: ["logs/<stage>/audit.log"]
    min_events_total: null
    max_error_events: null

integrity:
  checksum:
    enabled: true
    frequency: "every_1000000_events"
    formula: "SHA256(merchant_id || batch_index || cumulative_counts_vector)"
    field: "checksum"
  signing:
    enabled: false
    algorithm: null
    key_ref: null

sampling:
  default_rate: 1.0                   # 1.0 = 100% events
  overrides:
    - event_type: "debug"
      rate: 0.1

privacy_security:
  pii: false
  redact:
    rules: []                         # { field: "payload.card_number", method: "hash" }
  access:
    readable_by_groups: ["data","ml"]
    retention_days_max: 90

delivery_durability:
  flush_interval_ms: 200
  max_file_size_mb: 256
  backpressure:
    on_full_disk: "block"             # block|drop|spill_to_tmp
    spill_path: null
  retry_policy:
    enabled: true
    backoff: { initial_ms: 100, max_ms: 5000, factor: 2.0 }

validation:                            # CI checks against emitted logs
  require_schema_fields: true
  forbid_unknown_fields: true
  enforce_event_taxonomy: true
  verify_rotation_and_retention: true
  queries:
    - name: "missing_required_events_per_merchant"
      sql: |
        WITH req(event_type) AS (
          SELECT * FROM (VALUES
            ('hurdle_bernoulli'),('gamma_component'),('poisson_component'),
            ('nb_final'),('dirichlet_gamma_vector'),('sequence_finalize')
          ) t(event_type)
        )
        SELECT merchant_id
        FROM audit_log
        GROUP BY merchant_id
        HAVING COUNT(DISTINCT event_type) FILTER (WHERE event_type IN (SELECT event_type FROM req)) < 6;

observability:                         # metrics derived from logs (names only; details in monitoring)
  metrics:
    - name: "event_count_by_type"
    - name: "nb_rejection_rate_overall"
    - name: "ztp_rejections_mean"
    - name: "nb_rejections_p99"

open_questions:
  - id: "log-signing"
    note: "Decide whether to HMAC‑sign audit batches"
    owner: "TBD"
    due_by: null

waivers:
  - id: "taxonomy-finalization"
    reason: "Event payload schema under review"
    expires_on: "2025-09-30"

# Reference: allowed logical type hints
# string|bool|int32|int64|uint64|float32|float64|timestamp[ms]|timestamp[ms, tz=UTC]|list<type>|object
```

#### How to use it

* **Clone per sub‑segment** and keep undecided pieces `null/TBD` while `lifecycle.phase ∈ {planning, alpha}`.
* **Tie it to RNG**: ensure the `schema.required_fields` (e.g., `parameter_hash`, `manifest_fingerprint`, counters) match your RNG contract.
* **Make CI executable**: validate that required files exist, event schemas are respected, and the **coverage\_requirements** pass (per‑merchant required event set).
* **Slim it down if needed**: if a stage only emits one file, keep just one `files` entry and the subset of `event_taxonomy` you need.

Here’s a **planning‑friendly Logging Contract template** you can reuse **per sub‑segment**. It matches the style of your schema and RNG templates (lifecycle, CI policy, open questions, waivers) and is ready for production once you replace `TBD/null`.

> Save as: `logging_contract.<SUBSEGMENT_ID>.yaml` (e.g., `logging_contract.1A.yaml`)

```yaml
# logging_contract.<SUBSEGMENT_ID>.yaml — authoritative logging & audit spec for one sub‑segment
version: "1.0"

lifecycle:
  phase: "planning"                 # planning|alpha|beta|stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"] # when lifecycle escalates, placeholders must be gone

subsegment:
  id: "TBD"                         # e.g., "1A"
  name: "TBD"
  owner: "TBD team/email"
  doc_url: null

logging:
  structured: true                  # JSONL recommended
  format: "jsonl"                   # jsonl|ndjson|csv|text
  encoding: "utf-8"
  time_source: "utc"                # utc|system|monotonic (for event_time fields)
  time_field: "timestamp_utc"       # canonical field carrying RFC3339/ISO 8601 or epoch ms
  time_precision: "ms"              # s|ms|us|ns
  tz: "UTC"
  newline_delimited: true

sinks:                               # where logs go (one or more)
  - id: "file_primary"
    type: "file"                    # file|stdout|http|s3|kafka
    enabled: true
    params:
      path_root: "logs/<stage>/"    # base directory
      fsync_on_rotate: true
  - id: "stdout_fallback"
    type: "stdout"
    enabled: true
    params: {}

files:                               # each concrete log stream this sub‑segment must emit
  - role: "audit"                    # audit|progress|error|metrics|debug
    path: "logs/<stage>/audit.log"
    sink_id: "file_primary"
    rotation:
      policy: "daily"                # daily|size|hourly
      size_mb: null                  # used if policy=size
      compress: true                 # gzip/zstd
      keep_days: 90
    permissions:
      owner: "app"
      group: "data"
      mode: "0640"
    crash_tolerance:
      temp_pattern: "*.tmp"
      atomic_rename: true
      write_strategy: "append-fsync" # append-fsync|append-buffered
    retention:
      archive: false                 # if true, define offload target
      offload_target: null           # s3://bucket/prefix or similar

schema:                               # base schema all events MUST include (can be extended per event_type)
  required_fields:
    - "timestamp_utc"
    - "event_type"
    - "run_id"                       # e.g., UUID or hash of (parameter_hash, master_seed)
    - "parameter_hash"
    - "manifest_fingerprint"
  fields:
    - { name: "timestamp_utc",       type: "timestamp[ms, tz=UTC]", nullable: false, description: "Event time" }
    - { name: "event_type",          type: "string",                nullable: false, description: "Event taxonomy key" }
    - { name: "run_id",              type: "string",                nullable: false, description: "Unique run/session id" }
    - { name: "parameter_hash",      type: "string",                nullable: false, description: "64‑hex parameter set hash", pattern: "^[a-f0-9]{64}$" }
    - { name: "manifest_fingerprint",type: "string",                nullable: false, description: "64‑hex lineage fingerprint", pattern: "^[a-f0-9]{64}$" }
    - { name: "merchant_id",         type: "int64",                 nullable: true,  description: "Entity id if applicable" }
    - { name: "site_id",             type: "string",                nullable: true,  description: "Outlet/site id if applicable" }
    - { name: "pre_counter",         type: "uint64",                nullable: true,  description: "RNG counter before draw/jump" }
    - { name: "post_counter",        type: "uint64",                nullable: true,  description: "RNG counter after draw/jump" }
    - { name: "sequence_index",      type: "uint64",                nullable: true,  description: "Monotone index within sequence" }
    - { name: "rejection_flag",      type: "bool",                  nullable: true,  description: "True if rejection occurred" }
    - { name: "stride_key",          type: "string",                nullable: true,  description: "Jump stride id (if stream_jump)" }
    - { name: "level",               type: "string",                nullable: true,  description: "log level", enum: ["INFO","WARN","ERROR","DEBUG"] }
    - { name: "message",             type: "string",                nullable: true,  description: "Human‑readable note" }
    - { name: "payload",             type: "object",                nullable: true,  description: "Event‑specific fields object" }

event_taxonomy:                        # define every event_type and its extra fields
  - event_type: "hurdle_bernoulli"
    description: "Hurdle decision"
    severity: "INFO"                 # INFO|WARN|ERROR
    must_have_fields: ["merchant_id","pre_counter","post_counter","sequence_index"]
    payload_schema:
      - { name: "pi",               type: "float64", nullable: false, description: "probability" }
      - { name: "outcome",          type: "bool",    nullable: false, description: "decision" }
  - event_type: "gamma_component"
    description: "Gamma draw in NB mixture"
    severity: "INFO"
    must_have_fields: ["merchant_id","pre_counter","post_counter","sequence_index"]
    payload_schema:
      - { name: "shape",            type: "float64", nullable: false }
      - { name: "scale",            type: "float64", nullable: false }
  - event_type: "poisson_component"
    description: "Poisson draw in NB mixture"
    severity: "INFO"
    must_have_fields: ["merchant_id","pre_counter","post_counter","sequence_index"]
    payload_schema:
      - { name: "lambda",           type: "float64", nullable: false }
  - event_type: "nb_final"
    description: "Accepted NB count"
    severity: "INFO"
    must_have_fields: ["merchant_id","pre_counter","post_counter","sequence_index"]
    payload_schema:
      - { name: "count",            type: "int32",   nullable: false }
  - event_type: "ztp_rejection"
    description: "Zero‑truncated Poisson rejection"
    severity: "WARN"
    must_have_fields: ["merchant_id","sequence_index"]
    payload_schema:
      - { name: "lambda_extra",     type: "float64", nullable: false }
      - { name: "attempt",          type: "int32",   nullable: false }
  - event_type: "ztp_retry_exhausted"
    description: "Exceeded max ZTP retries"
    severity: "ERROR"
    must_have_fields: ["merchant_id"]
    payload_schema:
      - { name: "lambda_extra",     type: "float64", nullable: false }
      - { name: "rejection_count",  type: "int32",   nullable: false }
  - event_type: "gumbel_key"
    description: "Gumbel key for candidate selection"
    severity: "INFO"
    must_have_fields: ["merchant_id","sequence_index"]
    payload_schema:
      - { name: "country_iso",      type: "string",  nullable: false, pattern: "^[A-Z]{2}$" }
      - { name: "weight",           type: "float64", nullable: false }
      - { name: "u",                type: "float64", nullable: false }
      - { name: "key",              type: "float64", nullable: false }
  - event_type: "dirichlet_gamma_vector"
    description: "Dirichlet via Gamma draws"
    severity: "INFO"
    must_have_fields: ["merchant_id","sequence_index"]
    payload_schema:
      - { name: "countries",        type: "list<string>", nullable: false }
      - { name: "gamma",            type: "list<float64>", nullable: false }
      - { name: "weights_norm",     type: "list<float64>", nullable: false }
  - event_type: "stream_jump"
    description: "RNG sub‑stream jump"
    severity: "INFO"
    must_have_fields: ["merchant_id","pre_counter","post_counter","stride_key"]
    payload_schema:
      - { name: "module",           type: "string",  nullable: false }
  - event_type: "sequence_finalize"
    description: "End of merchant sequence"
    severity: "INFO"
    must_have_fields: ["merchant_id","sequence_index"]
    payload_schema: []

coverage_requirements:                # event coverage your CI will enforce
  per_entity:
    entity_key: "merchant_id"
    required_events:
      - "hurdle_bernoulli"
      - "gamma_component"
      - "poisson_component"
      - "nb_final"
      - "dirichlet_gamma_vector"
      - "sequence_finalize"
  system_wide:
    must_emit_files: ["logs/<stage>/audit.log"]
    min_events_total: null
    max_error_events: null

integrity:
  checksum:
    enabled: true
    frequency: "every_1000000_events"
    formula: "SHA256(merchant_id || batch_index || cumulative_counts_vector)"
    field: "checksum"
  signing:
    enabled: false
    algorithm: null
    key_ref: null

sampling:
  default_rate: 1.0                   # 1.0 = 100% events
  overrides:
    - event_type: "debug"
      rate: 0.1

privacy_security:
  pii: false
  redact:
    rules: []                         # { field: "payload.card_number", method: "hash" }
  access:
    readable_by_groups: ["data","ml"]
    retention_days_max: 90

delivery_durability:
  flush_interval_ms: 200
  max_file_size_mb: 256
  backpressure:
    on_full_disk: "block"             # block|drop|spill_to_tmp
    spill_path: null
  retry_policy:
    enabled: true
    backoff: { initial_ms: 100, max_ms: 5000, factor: 2.0 }

validation:                            # CI checks against emitted logs
  require_schema_fields: true
  forbid_unknown_fields: true
  enforce_event_taxonomy: true
  verify_rotation_and_retention: true
  queries:
    - name: "missing_required_events_per_merchant"
      sql: |
        WITH req(event_type) AS (
          SELECT * FROM (VALUES
            ('hurdle_bernoulli'),('gamma_component'),('poisson_component'),
            ('nb_final'),('dirichlet_gamma_vector'),('sequence_finalize')
          ) t(event_type)
        )
        SELECT merchant_id
        FROM audit_log
        GROUP BY merchant_id
        HAVING COUNT(DISTINCT event_type) FILTER (WHERE event_type IN (SELECT event_type FROM req)) < 6;

observability:                         # metrics derived from logs (names only; details in monitoring)
  metrics:
    - name: "event_count_by_type"
    - name: "nb_rejection_rate_overall"
    - name: "ztp_rejections_mean"
    - name: "nb_rejections_p99"

open_questions:
  - id: "log-signing"
    note: "Decide whether to HMAC‑sign audit batches"
    owner: "TBD"
    due_by: null

waivers:
  - id: "taxonomy-finalization"
    reason: "Event payload schema under review"
    expires_on: "2025-09-30"

# Reference: allowed logical type hints
# string|bool|int32|int64|uint64|float32|float64|timestamp[ms]|timestamp[ms, tz=UTC]|list<type>|object
```

#### How to use it

* **Clone per sub‑segment** and keep undecided pieces `null/TBD` while `lifecycle.phase ∈ {planning, alpha}`.
* **Tie it to RNG**: ensure the `schema.required_fields` (e.g., `parameter_hash`, `manifest_fingerprint`, counters) match your RNG contract.
* **Make CI executable**: validate that required files exist, event schemas are respected, and the **coverage\_requirements** pass (per‑merchant required event set).
* **Slim it down if needed**: if a stage only emits one file, keep just one `files` entry and the subset of `event_taxonomy` you need.

### Filled stubs
Great question. **The logging contract I gave is a universal template**—it’s not locked to 1A.

* The **top half** (lifecycle, CI policy, sinks/rotation, base schema fields, integrity, privacy, delivery, validation) is **stage‑agnostic**.
* The **parts you tailor per sub‑segment** are mainly:

  * `files[].path` (where this stage writes),
  * `schema.required_fields` (what every event must carry),
  * `event_taxonomy` (the list of `event_type`s and their payloads),
  * `coverage_requirements` (what must be present per entity/run).

To make that concrete, here’s how you’d adapt the universal template to other stages.

---

### How to adapt per sub‑segment

#### What stays the same

* `lifecycle`, `ci_policy`, `structured`, `format`, encoding, UTC timestamps
* rotation/retention/crash‑tolerance scaffolding
* integrity checksum block (if you use it)
* base schema fields you want globally (e.g., `timestamp_utc`, `event_type`, `parameter_hash`)

#### What you swap out

* **Paths**: e.g., `logs/1B/audit.log` vs `logs/2A/audit.log`
* **Event taxonomy**: different `event_type`s and payload fields
* **Coverage rules**: different “must have” sets (per merchant, per site, per zone, etc.)

---

### Quick overlays by stage (examples to guide you)

Below are **small YAML overlays** you can drop on top of the universal template (think: merge/replace) to specialize it. They show only the bits you’d change.

#### 1B – *Placing outlets on the planet* (sampling/spatial)

```yaml
files:
  - role: "audit"
    path: "logs/1B/audit.log"
    # rotation/retention same as base …

event_taxonomy:
  - event_type: "fenwick_build"
    must_have_fields: ["country_iso"]
    payload_schema:
      - { name: "prior_id", type: "string", nullable: false }
      - { name: "n",        type: "int64",  nullable: false }
      - { name: "total_weight", type: "float64", nullable: false }
  - event_type: "pixel_draw"
    must_have_fields: ["site_id","pre_counter","post_counter"]
    payload_schema:
      - { name: "prior_tag",     type: "string",  nullable: false }
      - { name: "pixel_index",   type: "int32",   nullable: false }
      - { name: "cdf_threshold_u", type: "float64", nullable: false }
  - event_type: "feature_draw"      # for vector layers
    must_have_fields: ["site_id"]
    payload_schema:
      - { name: "feature_index", type: "int32", nullable: false }
  - event_type: "tz_mismatch"
    severity: "WARN"
    payload_schema:
      - { name: "tzid_expected", type: "string", nullable: false }
      - { name: "tzid_found",    type: "string", nullable: false }

coverage_requirements:
  per_entity:
    entity_key: "site_id"
    required_events: ["pixel_draw"]  # or ["feature_draw"] depending on prior type
```

#### 2A – *Deriving the civil time zone* (tz polygons / DST)

```yaml
files:
  - role: "audit"
    path: "logs/2A/audit.log"

event_taxonomy:
  - event_type: "tz_lookup"
    must_have_fields: ["site_id"]
    payload_schema:
      - { name: "tzid",      type: "string",  nullable: false }
      - { name: "lat",       type: "float64", nullable: false }
      - { name: "lon",       type: "float64", nullable: false }
  - event_type: "tz_nudge_applied"
    severity: "INFO"
    payload_schema:
      - { name: "nudge_lat", type: "float64", nullable: false }
      - { name: "nudge_lon", type: "float64", nullable: false }
  - event_type: "dst_adjustment"
    payload_schema:
      - { name: "gap_seconds",     type: "int32",   nullable: true }
      - { name: "fold",            type: "int8",    nullable: true }
      - { name: "local_time_offset", type: "int16", nullable: false }

coverage_requirements:
  per_entity:
    entity_key: "site_id"
    required_events: ["tz_lookup"]
```

#### 2B – *Routing through sites* (alias sampling)

```yaml
files:
  - role: "audit"
    path: "logs/2B/routing_audit.log"

event_taxonomy:
  - event_type: "day_effect_draw"
    payload_schema:
      - { name: "gamma_id",    type: "int32",   nullable: false }
      - { name: "gamma_value", type: "float64", nullable: false }
  - event_type: "alias_sample"
    payload_schema:
      - { name: "merchant_id", type: "int64",   nullable: false }
      - { name: "site_id",     type: "string",  nullable: false }
      - { name: "k",           type: "int32",   nullable: false }
      - { name: "prob_k",      type: "float64", nullable: false }
  - event_type: "routing_checksum"
    severity: "INFO"
    payload_schema:
      - { name: "batch_index", type: "int64",   nullable: false }
      - { name: "checksum",    type: "string",  nullable: false }

coverage_requirements:
  system_wide:
    must_emit_files: ["logs/2B/routing_audit.log"]
```

#### 3A – *Cross‑zone merchants* (allocations/rounding)

```yaml
files:
  - role: "audit"
    path: "logs/3A/alloc_audit.log"

event_taxonomy:
  - event_type: "dirichlet_draw"
    payload_schema:
      - { name: "country_iso", type: "string",  nullable: false }
      - { name: "tzid",        type: "string",  nullable: false }
      - { name: "alpha",       type: "float64", nullable: false }
      - { name: "weight",      type: "float64", nullable: false }
  - event_type: "lrr_rounding"
    payload_schema:
      - { name: "requested_total", type: "int32", nullable: false }
      - { name: "delta_max",       type: "float64", nullable: false }
  - event_type: "universe_hash_check"
    severity: "ERROR"
    payload_schema:
      - { name: "universe_hash_expected", type: "string", nullable: false }
      - { name: "universe_hash_found",    type: "string", nullable: false }
```

#### 3B – *Purely virtual merchants* (edges/geocoder/CDN)

```yaml
files:
  - role: "audit"
    path: "logs/3B/virtual_audit.log"

event_taxonomy:
  - event_type: "virtual_flag_applied"
    payload_schema:
      - { name: "merchant_id", type: "int64", nullable: false }
      - { name: "rule_id",     type: "string", nullable: false }
  - event_type: "geocoder_verify"
    severity: "INFO"
    payload_schema:
      - { name: "merchant_id", type: "int64",   nullable: false }
      - { name: "error_km",    type: "float64", nullable: false }
  - event_type: "cdn_alias_sample"
    payload_schema:
      - { name: "merchant_id",   type: "int64",   nullable: false }
      - { name: "ip_country",    type: "string",  nullable: false }
      - { name: "edge_id",       type: "string",  nullable: false }
```

#### 4A – *Reproducibility & configurability* (manifests/firewall)

```yaml
files:
  - role: "audit"
    path: "logs/4A/repro_audit.log"
  - role: "error"
    path: "logs/4A/firewall_errors.log"

event_taxonomy:
  - event_type: "container_boot"
    payload_schema:
      - { name: "container_digest", type: "string", nullable: false }
  - event_type: "sourcehash_check"
    payload_schema:
      - { name: "source_sha1",    type: "string", nullable: false }
      - { name: "codehash",       type: "string", nullable: false }
  - event_type: "firewall_violation"
    severity: "ERROR"
    payload_schema:
      - { name: "rule",           type: "string",  nullable: false }
      - { name: "offending_row",  type: "object",  nullable: false }
      - { name: "rng_offset",     type: "uint64",  nullable: true }
```

#### 4B – *Validation* (structural, adversarial, semantic, barcode)

```yaml
files:
  - role: "audit"
    path: "logs/4B/validation_audit.log"

event_taxonomy:
  - event_type: "structural_check"
    payload_schema:
      - { name: "failures",  type: "int32", nullable: false }
  - event_type: "adv_auroc_eval"
    payload_schema:
      - { name: "auroc",     type: "float64", nullable: false }
  - event_type: "semantic_glm_check"
    payload_schema:
      - { name: "theta",     type: "float64", nullable: false }
  - event_type: "barcode_slope_check"
    payload_schema:
      - { name: "slope",     type: "float64", nullable: false }
  - event_type: "hashgate_upload"
    payload_schema:
      - { name: "bundle_uri", type: "string", nullable: false }

coverage_requirements:
  system_wide:
    required_events: ["structural_check","adv_auroc_eval","semantic_glm_check","barcode_slope_check","hashgate_upload"]
```

> **Note:** treat the event names above as *scaffolding*. Use the exact event names you recorded in your artefact registries and narratives.

---

### If you want less duplication

You can keep **one `logging_contract.base.yaml`** and then per‑stage **overlay files** that only override `files`, `event_taxonomy`, and `coverage_requirements`. Merge them in CI (e.g., `yq eval-all 'select(fileIndex==0) * select(fileIndex==1)' base.yaml overlay.yaml`), so the shared defaults live in one place.

---

#### Bottom line

* The template is **universal**.
* The **only 1A‑flavored part** in my earlier message was the example `event_taxonomy`; swap that section per sub‑segment (and adjust coverage).
* Everything else—rotation, base schema, integrity, privacy—works **as‑is** across 1A…4B.


######################################################################################################

######################################################################################################

## `PERFORMANCE.<ID>.yaml`
Absolutely—here’s a **planning‑friendly, stage‑agnostic Performance/SLA contract template** you can reuse **per sub‑segment**. It mirrors the style of your schema, invariants, and RNG templates (lifecycle, CI policy, open questions, waivers), and is designed so CI can progressively harden it from *planning → stable*.

> Save as: `performance.<SUBSEGMENT_ID>.yaml` (e.g., `performance.1A.yaml`)

```yaml
# performance.<SUBSEGMENT_ID>.yaml — authoritative performance/SLA spec for one sub‑segment
version: "1.0"

lifecycle:
  phase: "planning"                  # planning|alpha|beta|stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"]  # once lifecycle escalates, placeholders must be resolved

subsegment:
  id: "TBD"                           # e.g., "1A"
  name: "TBD"
  owner: "TBD team/email"
  doc_url: null

# ── What workload we promise to handle (so targets are meaningful)
workload_definition:
  scale_profile: "TBD"                # e.g., "D30 merchants=1e6, days=30"
  input_volume_estimates:
    rows_min: null
    rows_typical: null
    rows_p95: null
  cardinalities:
    merchants: null
    sites: null
    countries: null
    days: null
  record_size_bytes:
    mean: null
    p95: null

# ── Core throughput/latency expectations
targets:
  throughput_rows_per_sec:
    p50: null
    p95: null
  end_to_end_latency_ms:              # ingest → egress (or stage entry → exit)
    p50: null
    p95: null
    p99: null
  startup_warmup_seconds: null        # cold start to steady state
  recovery_time_seconds: null         # after crash/restart
  sla_window: "TBD"                   # e.g., "rolling 7 days"
  error_budget_pct: null              # % of time allowed out of SLA

# ── How work is chunked and parallelised
execution_model:
  batch_size_rows: 50000              # if batch processing is used
  max_batch_time_ms: null             # cap per batch wall‑clock
  parallelism:
    model: "TBD"                      # single-thread|per-merchant|per-site|map-reduce
    max_concurrency: null             # upper bound (threads or processes)
    cpu_affinity: null
    io_parallelism: null
  scheduling:
    invariance_required: true         # results must not depend on schedule
    queue_depth_target: null

# ── Resource budgets (upper limits; exceeding them is a violation)
resource_budgets:
  cpu_cores_max: null                 # total cores the stage may use
  memory_gb_max: null
  disk_io_mb_s_max: null
  net_io_mb_s_max: null
  temp_space_gb_max: null
  gpu:
    required: false
    type: null
    count_max: null

# ── Spill/Backpressure behavior under load
backpressure_and_spill:
  on_input_slow: "block"              # block|drop|buffer
  on_output_slow: "block"             # block|drop|spill_to_disk
  spill:
    enabled: true
    path: "TBD"
    low_watermark_pct: 20
    high_watermark_pct: 80
  retries:
    enabled: true
    max_retries: 5
    backoff: { initial_ms: 100, max_ms: 5000, factor: 2.0 }
  timeouts:
    op_timeout_ms: null               # per‑op timeout
    batch_timeout_ms: null

# ── Fault tolerance & durability expectations
resilience:
  checkpointing:                      # if applicable
    enabled: false
    frequency_rows: null
    path: null
  crash_recovery:
    resume_from_last_checkpoint: false
    expected_data_loss_rows: 0
  durability:
    fsync_on_rotate: true
    guarantees: ["at-least-once"]     # at-most-once|at-least-once|exactly-once (state what is realistic)

# ── Performance correctness (must still hold under load)
integrity_under_load:
  forbid_data_drops: true
  invariant_checks_enabled: true      # invariants.<ID>.yaml still enforced at target throughput
  rng_determinism_preserved: true

# ── Measurement protocol: how we *prove* we meet targets
measurement_protocol:
  harness: "TBD"                      # name/tool of perf harness
  dataset_fixture:
    generator_seed: null
    scale_profile: "same-as-workload"
  warmup_seconds: 60
  run_duration_minutes: 30
  sampling_interval_ms: 1000
  metrics_collector: "TBD"            # e.g., Prometheus, StatsD, custom CSV
  reproducibility:
    fixed_threads: true
    fixed_affinity: true
    fixed_random_seed: true

# ── What constitutes pass/fail (used by CI/perf‑gate)
acceptance_criteria:
  must_meet:
    - name: "throughput_p95"
      condition: "observed.throughput_rows_per_sec.p95 >= targets.throughput_rows_per_sec.p95"
    - name: "latency_p99"
      condition: "observed.end_to_end_latency_ms.p99 <= targets.end_to_end_latency_ms.p99"
    - name: "cpu_budget"
      condition: "observed.cpu_cores_peak <= resource_budgets.cpu_cores_max"
    - name: "mem_budget"
      condition: "observed.memory_gb_peak <= resource_budgets.memory_gb_max"
    - name: "no_data_drops"
      condition: "observed.data_drops == 0"
  allow_degradation_if:
    - name: "error_budget_not_exceeded"
      condition: "observed.sla_breach_pct <= targets.error_budget_pct"

# ── What we emit to monitor SLAs in prod (names; definitions live in monitoring)
observability_metrics:
  - name: "throughput_rows_per_sec"
  - name: "latency_ms_p50"
  - name: "latency_ms_p95"
  - name: "latency_ms_p99"
  - name: "cpu_cores_peak"
  - name: "memory_gb_peak"
  - name: "disk_io_mb_s_peak"
  - name: "net_io_mb_s_peak"
  - name: "queue_depth"
  - name: "backpressure_events"
  - name: "retries_total"
  - name: "error_rate"
  - name: "sla_breach_pct"

# ── Where perf artefacts are written so reviewers can inspect them
reporting:
  output_dir: "TBD"                   # e.g., validation/<parameter_hash>/perf/
  artefacts:
    - "perf_summary.json"
    - "timeseries.csv"
    - "flamegraph.svg"
    - "heap_profile.txt"

# ── Environment matrix: where this contract applies
environments:
  - name: "ci"
    hardware_class: "TBD"
    os_image: "TBD"
    container_digest: null
  - name: "prod"
    hardware_class: "TBD"
    os_image: "TBD"
    container_digest: null

# ── Upstream/downstream timing budgets (for pipeline coordination)
integration_budgets:
  upstream_wait_ms_max: null
  downstream_flush_ms_max: null

# ── Governance for changes to performance‑critical code/params
change_management:
  perf_gate_required: true
  requires:
    - "updated performance.<ID>.yaml with new targets"
    - "perf report attached"
    - "sign‑off by owner/approver"

open_questions:
  - id: "target-throughput"
    note: "Define p95 throughput for typical scale"
    owner: "TBD"
    due_by: null
  - id: "hardware-class"
    note: "Pin vCPU/RAM/IO profile for CI & prod"
    owner: "TBD"
    due_by: null

waivers:
  - id: "p99-latency-temp-waiver"
    reason: "Index build regression; fix in progress"
    expires_on: "2025-10-01"
```

---

#### How to use this template

* **Universal base:** This file is **not 1A‑specific**. You can copy it as‑is for 1A…4B.
* **Fill the few stage‑specific items:** `workload_definition`, `targets`, `execution_model.parallelism`, and any **resource\_budgets** you know now. Keep the rest `TBD/null` while `lifecycle.phase ∈ {planning, alpha}`.
* **Wire your perf‑gate:** Have CI run the `measurement_protocol`, compute `observed.*`, and evaluate `acceptance_criteria.must_meet`. Fail the build if any condition is false (or if placeholders remain once you flip to `beta/stable`).

### Minimal Filled Stub
Here’s a **minimal filled stub** of the Performance/SLA contract for **Sub‑segment 2B (Routing Transactions Through Sites)**. It keeps the structure lean and only fixes values that are safe to standardize now; all unknowns remain `TBD`/`null` so you won’t “invent” numbers during planning.

> File: `performance.2B.yaml`

```yaml
# performance.2B.yaml — minimal performance/SLA stub for Sub‑segment 2B
version: "1.0"

lifecycle:
  phase: "planning"                  # tighten later: alpha → beta → stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"]

subsegment:
  id: "2B"
  name: "Routing Transactions Through Sites"
  owner: "TBD team/email"
  doc_url: null

workload_definition:
  scale_profile: "TBD"               # e.g., merchants=1e6, days=30, tx=… per day
  input_volume_estimates:
    rows_min: null
    rows_typical: null
    rows_p95: null
  cardinalities:
    merchants: null
    sites: null
    days: null
  record_size_bytes:
    mean: null
    p95: null

targets:
  throughput_rows_per_sec:
    p50: null
    p95: null
  end_to_end_latency_ms:
    p50: null
    p95: null
    p99: null
  startup_warmup_seconds: null
  recovery_time_seconds: null
  sla_window: "rolling 7 days"
  error_budget_pct: null

execution_model:
  batch_size_rows: 50000             # safe default; adjust if router batches differently
  max_batch_time_ms: null
  parallelism:
    model: "per-merchant"            # routing is naturally per-merchant
    max_concurrency: null
    cpu_affinity: null
    io_parallelism: null
  scheduling:
    invariance_required: true
    queue_depth_target: null

resource_budgets:
  cpu_cores_max: null
  memory_gb_max: null
  disk_io_mb_s_max: null
  net_io_mb_s_max: null
  temp_space_gb_max: null
  gpu:
    required: false
    type: null
    count_max: null

backpressure_and_spill:
  on_input_slow: "block"
  on_output_slow: "block"
  spill:
    enabled: true
    path: "TBD"
    low_watermark_pct: 20
    high_watermark_pct: 80
  retries:
    enabled: true
    max_retries: 5
    backoff: { initial_ms: 100, max_ms: 5000, factor: 2.0 }
  timeouts:
    op_timeout_ms: null
    batch_timeout_ms: null

resilience:
  checkpointing:
    enabled: false
    frequency_rows: null
    path: null
  crash_recovery:
    resume_from_last_checkpoint: false
    expected_data_loss_rows: 0
  durability:
    fsync_on_rotate: true
    guarantees: ["at-least-once"]

integrity_under_load:
  forbid_data_drops: true
  invariant_checks_enabled: true
  rng_determinism_preserved: true

measurement_protocol:
  harness: "TBD"                      # e.g., tools/perf_runner.py
  dataset_fixture:
    generator_seed: null
    scale_profile: "same-as-workload"
  warmup_seconds: 30
  run_duration_minutes: 10
  sampling_interval_ms: 1000
  metrics_collector: "TBD"
  reproducibility:
    fixed_threads: true
    fixed_affinity: true
    fixed_random_seed: true

acceptance_criteria:
  must_meet:
    - name: "throughput_p95"
      condition: "observed.throughput_rows_per_sec.p95 >= targets.throughput_rows_per_sec.p95"
    - name: "latency_p99"
      condition: "observed.end_to_end_latency_ms.p99 <= targets.end_to_end_latency_ms.p99"
    - name: "cpu_budget"
      condition: "observed.cpu_cores_peak <= resource_budgets.cpu_cores_max"
    - name: "mem_budget"
      condition: "observed.memory_gb_peak <= resource_budgets.memory_gb_max"
    - name: "no_data_drops"
      condition: "observed.data_drops == 0"
  allow_degradation_if:
    - name: "error_budget_not_exceeded"
      condition: "observed.sla_breach_pct <= targets.error_budget_pct"

observability_metrics:
  - name: "throughput_rows_per_sec"
  - name: "latency_ms_p50"
  - name: "latency_ms_p95"
  - name: "latency_ms_p99"
  - name: "cpu_cores_peak"
  - name: "memory_gb_peak"
  - name: "disk_io_mb_s_peak"
  - name: "net_io_mb_s_peak"
  - name: "queue_depth"
  - name: "backpressure_events"
  - name: "retries_total"
  - name: "error_rate"
  - name: "sla_breach_pct"

reporting:
  output_dir: "validation/<parameter_hash>/perf/2B"
  artefacts:
    - "perf_summary.json"
    - "timeseries.csv"

environments:
  - name: "ci"
    hardware_class: "TBD"
    os_image: "TBD"
    container_digest: null
  - name: "prod"
    hardware_class: "TBD"
    os_image: "TBD"
    container_digest: null

integration_budgets:
  upstream_wait_ms_max: null
  downstream_flush_ms_max: null

change_management:
  perf_gate_required: true
  requires:
    - "updated performance.2B.yaml with concrete targets"
    - "perf report attached"
    - "owner approval"

open_questions:
  - id: "2b-targets"
    note: "Set realistic throughput/latency for alias-sampling router"
    owner: "TBD"
    due_by: null
  - id: "spill-path"
    note: "Confirm spill directory and disk budget"
    owner: "TBD"
    due_by: null

waivers:
  - id: "throughput-placeholder"
    reason: "Targets not yet set; planning phase"
    expires_on: "2025-12-31"
```

#### Why this is practical

* **Minimal surface area:** you can paste this today without inventing numbers.
* **Safe defaults only where non‑controversial** (e.g., `batch_size_rows: 50000`, `fsync_on_rotate: true`).
* **CI‑friendly:** once you set `targets` and `resource_budgets`, the `acceptance_criteria` become immediately checkable; until then, placeholders are allowed while `lifecycle.phase: planning`.



######################################################################################################

######################################################################################################

## `FUNCTION_REGISTRY.<ID>.yaml`


######################################################################################################

######################################################################################################


## `PARAMETER_DICTIONARY.<ID>.yaml`


######################################################################################################

######################################################################################################


## `INTERFACE_CONTRACT.<ID>.yaml`

> NOTE: Go with the best practice 

It **doesn’t have to change** in spirit—Template A still works.
What *does* change now that you’ve split out **Schemas**, **Invariants**, **RNG**, **Logging**, and **Performance** is **how you populate** the Interface Contract:

* You can **keep Template A exactly as-is** and paste the content from those docs into the appropriate sections, **or**
* You can keep Template A **thin** and make it a “**bundle index**” that **references** those sub‑docs (preferred for maintenance).

In practice, most teams adopt the second approach: the Interface Contract remains the single authoritative file per stage, but it *points to* the five component docs and pins their digests so CI can detect drift.

**[OUTDATED]**: Use this tiny enhancement of Template A that **adds a `components` and `integrity` block** and lets you *reference* sections instead of duplicating them.

```yaml
# interface_contract.<ID>.yaml — Template A v1.1 (thin; references component docs)
contract_version: "1.1" # this is deprecated. Use updated template below

lifecycle:
  phase: "planning"            # planning|alpha|beta|stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"]

subsegment:
  id: "TBD"                    # e.g., "1A"
  name: "TBD"
  owner: "TBD team/email"
  doc_url: null

# —— New: reference the five component specs you already maintain —— #
components:
  schemas:
    file: "schemas.<ID>.yaml"
    sha256: null               # filled by CI to pin exact version
    required: true
  invariants:
    file: "invariants.<ID>.yaml"
    sha256: null
    required: true
  rng:
    file: "rng_contract.<ID>.yaml"
    sha256: null
    required: true
  logging:
    file: "logging_contract.<ID>.yaml"
    sha256: null
    required: true
  performance:
    file: "performance.<ID>.yaml"
    sha256: null
    required: false

# Ingress/egress keep the same structure as Template A, but can defer details to components
ingress:
  required_artifacts:
    # populate from your artifact registry (concrete IDs + manifest keys)
    - { artifact_id: "TBD", min_version: null, digest_key: "TBD_manifest_key" }

  # Option A (inline): paste full input schemas here (original Template A)
  # Option B (thin): reference them from the schemas file via a JSON Pointer-like path your CI understands
  required_inputs_ref: "schemas.<ID>.yaml#/ingress/datasets"

invariants_ref: "invariants.<ID>.yaml#/invariants"     # defer full list to component file
exceptions_ref: "invariants.<ID>.yaml#/exceptions"     # stable error API

rng_ref:       "rng_contract.<ID>.yaml#/"              # whole RNG spec
logging_ref:   "logging_contract.<ID>.yaml#/"          # whole logging spec
performance_ref: "performance.<ID>.yaml#/targets"      # or the whole file

egress:
  # Option A (inline) or B (thin ref)
  produces_datasets_ref: "schemas.<ID>.yaml#/egress/datasets"
  emits_logs_ref:        "logging_contract.<ID>.yaml#/files"

compatibility:
  egress_mode: "BACKWARD"          # BACKWARD|FORWARD|FULL|NONE
  deprecation_window_days: 90
  breaking_change_requires: ["major_version_bump","RFC"]

# —— New: integrity pins so CI can detect drift across the bundle —— #
integrity:
  bundle_sha256: null              # CI can compute over the normalized JSON of all 5 component files
  includes:
    - "schemas.<ID>.yaml"
    - "invariants.<ID>.yaml"
    - "rng_contract.<ID>.yaml"
    - "logging_contract.<ID>.yaml"
    - "performance.<ID>.yaml"

# Optional: declare expected downstream and upstream to aid link‑contract generation
interfaces:
  upstream_of: "TBD_prev_ID"       # e.g., "1A" has none; "1B" says upstream_of: "1A"
  downstream_of: "TBD_next_ID"     # e.g., 1A → 1B

observability:
  metrics_ref: "performance.<ID>.yaml#/observability_metrics"
```

### How your CI uses this

* **Pinning:** it fills each `components.*.sha256` and the `integrity.bundle_sha256`.
* **Validation:** it loads the referenced files and enforces:

  * Ingress schema presence → from `schemas.<ID>.yaml#/ingress`
  * Egress schema guarantees → from `schemas.<ID>.yaml#/egress`
  * Invariants & error contract → from `invariants.<ID>.yaml`
  * RNG & logging coverage → from the RNG/logging contracts
  * Perf gate (optional) → from `performance.<ID>.yaml`
* **Link contracts:** it can auto‑generate boundary checks (Egress(N) ≍ Ingress(N+1)) without you maintaining a separate file.

---

#### If you prefer the original Template A (monolithic)

You can keep everything **inline** as before (schemas, invariants, RNG, logging, perf all inside the Interface Contract). It’s still valid—just more to edit. The “v1.1 thin‑index” form above reduces duplication and makes reviews cleaner.

---

### Updated version to include param_dictionary and function registry

**Short answer — no redesign needed, just add two more “component” rows.**
The interface contract is still a thin bundle-index; it now pins **seven** sub-files instead of five:

| component                  | why it sits here                                             |
| -------------------------- | ------------------------------------------------------------ |
| `schemas`                  | dataset shapes the stage promises to read/write              |
| `invariants`               | semantic & structural rules + error contract                 |
| `rng`                      | seed derivation, retry caps, required RNG events             |
| `logging`                  | audit-log files, event taxonomy, coverage rule               |
| `performance`              | optional perf-gate targets                                   |
| **`function_registry`**    | machine list of every algorithmic step the stage runs        |
| **`parameter_dictionary`** | binding of every math symbol / prior used by those functions |

Everything else in Template A v1.1 stays identical.

---

### Revised “thin” interface-contract template (v1.2)

```yaml
# interface_contract.<ID>.yaml — Template A v1.2 (pins 7 component files)
contract_version: "1.2"

lifecycle:
  phase: "planning"            # planning|alpha|beta|stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"]

subsegment:
  id: "TBD"                    # e.g., "2B"
  name: "TBD"
  owner: "TBD team/email"
  doc_url: null

components:
  schemas:            { file: "schemas.<ID>.yaml",             sha256: null, required: true }
  invariants:         { file: "invariants.<ID>.yaml",          sha256: null, required: true }
  rng:                { file: "rng_contract.<ID>.yaml",        sha256: null, required: true }
  logging:            { file: "logging_contract.<ID>.yaml",    sha256: null, required: true }
  performance:        { file: "performance.<ID>.yaml",         sha256: null, required: false }
  function_registry:  { file: "function_registry.<ID>.yaml",   sha256: null, required: true }
  parameter_dictionary:
                      { file: "parameter_dictionary.<ID>.yaml",sha256: null, required: true }

ingress:
  required_artifacts:
    - { artifact_id: "TBD", min_version: null, digest_key: "TBD_manifest_key" }
  required_inputs_ref: "schemas.<ID>.yaml#/ingress/datasets"

invariants_ref:   "invariants.<ID>.yaml#/invariants"
exceptions_ref:   "invariants.<ID>.yaml#/exceptions"
rng_ref:          "rng_contract.<ID>.yaml#/"
logging_ref:      "logging_contract.<ID>.yaml#/"
performance_ref:  "performance.<ID>.yaml#/targets"
functions_ref:    "function_registry.<ID>.yaml#/functions"
parameters_ref:   "parameter_dictionary.<ID>.yaml#/parameters"

egress:
  produces_datasets_ref: "schemas.<ID>.yaml#/egress/datasets"
  emits_logs_ref:        "logging_contract.<ID>.yaml#/files"

compatibility:
  egress_mode: "BACKWARD"
  deprecation_window_days: 90
  breaking_change_requires: ["major_version_bump","RFC"]

integrity:
  bundle_sha256: null         # CI computes over all 7 component digests
  includes:
    - "schemas.<ID>.yaml"
    - "invariants.<ID>.yaml"
    - "rng_contract.<ID>.yaml"
    - "logging_contract.<ID>.yaml"
    - "performance.<ID>.yaml"
    - "function_registry.<ID>.yaml"
    - "parameter_dictionary.<ID>.yaml"

interfaces:
  upstream_of: "TBD_prev_ID"
  downstream_of: "TBD_next_ID"

observability:
  metrics_ref: "performance.<ID>.yaml#/observability_metrics"
```

---

### What changes for CI?

* **Pinning:** it now fills two additional `sha256` slots (`function_registry`, `parameter_dictionary`) and recomputes `bundle_sha256`.
* **Validation:**

  * Confirms every function referenced in `invariants_ref` or `logging_ref` exists in the pinned `function_registry`.
  * Confirms every parameter used in the function registry is defined in the pinned parameter dictionary.

No other logic changes. If you’d already generated stubs for 1A-4B, just extend the `components` block in each and let CI re-pin the new digests.






######################################################################################################

######################################################################################################


