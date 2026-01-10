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
      ├─ mathematics_appendix_<ID>.txt   (human, already written. You might replace this with algorithmic logic)
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


### Expanded, step-by-step roadmap

*(each step adds just enough detail so you know **what feeds what**, **who fills it**, and **why it must come before the next step**)*

| #      | File(s) you create / finalise                         | Filled **from**                                                               | Key fields you must pin **now**                                            | Why the **next** step needs it                                                                      |
| ------ | ----------------------------------------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| **1**  | **`artefact_registry`**                               |  • design narrative • assumptions • governing YAML/CSV models                 | `artifact_id`, `digest_key`, `version/vintage`, `sha256`                   | Every downstream contract refers to artefacts by the *exact IDs* & digests registered here.         |
| **2**  | **`dataset_dictionary.layer1.yaml`**                  |  • artefact registry (points to data files)<br> • prose describing outputs    | dataset ID, owner stage, path/prefix, `schema_ref` *placeholder*           | Gives each sub-segment a *canonical dataset name* to reference in its own `schemas.<ID>.yaml`.      |
| **3a** | **`schemas.<ID>.yaml`** *(8 files)*                   |  • dataset dictionary row for that stage<br> • narrative (column list, types) | Column list, nullability, partitioning, ordering                           | Invariants need column names + semantics to write rules; logging needs required fields.             |
| **3b** | **`invariants.<ID>.yaml`**                            |  • narrative rules<br> • maths appendix (tolerances)                          | invariant `id`, description, `expression.sql / py`, linked exception       | Tells logging which errors to emit; link-contracts use invariants to check cross-stage guarantees.  |
| **3c** | **`rng_contract.<ID>.yaml`**                          |  • maths appendix algorithm steps<br> • assumptions on determinism            | seed fields, namespace, retry caps, required RNG events                    | Logging contract must list the same RNG events; invariant “required RNG audit events” points here.  |
| **3d** | **`logging_contract.<ID>.yaml`**                      |  • rng\_contract (event list)<br> • invariants (error payload fields)         | path, rotation, `event_taxonomy` slice, payload schema, coverage rule      | Interface contract will embed a digest of this file; taxonomy will later deduplicate the enums.     |
| **3e** | **`performance.<ID>.yaml`**                           |  • SRE notes / runbook                                                        | `batch_size_rows`, placeholder targets                                     | Interface contract pins perf spec; taxonomy lists metric names you declare here.                    |
| **4**  | **`mathematics_appendix_<ID>.txt`** *(already exist)* | —                                                                             | —                                                                          | Function/parameter registries quote section numbers; invariants reference eq-IDs here.              |
| **4a** | **`function_registry.<ID>.yaml`**                     |  • appendix sections A.\*                                                     | each `function.id`, inputs/outputs, RNG draws                              | Parameter dictionary checks that every symbol used here is defined.                                 |
| **4b** | **`parameter_dictionary.<ID>.yaml`**                  |  • appendix equations                                                         | each symbol → artefact key / dataset.column                                | Interface contract “thin” form can avoid redeclaring mapping logic.                                 |
| **5**  | **`interface_contract.<ID>.yaml`** *(thin)*           |  • digests of *all* files from steps 2-4                                      | `components.*.sha256`, upstream/downstream dataset refs                    | CI can rebuild and diff; link-contract generator needs both sides’ interface files.                 |
| **6**  | **`link_contract.<N→N+1>.yaml`** *(CI auto-gen)*      |  • schemas.N (egress) • schemas.N+1 (ingress)                                 | dataset name, column compat table, partition/ordering checks               | Manifest pins its digest to prove boundary compatibility at build time.                             |
| **7a** | **`error_catalogue.layer1.yaml`**                     |  • invariants (exception names)<br> • logging payload schemas                 | `error.id`, code, message template, `must_include_fields`                  | Logging contracts must use these IDs; taxonomy links to `severity`.                                 |
| **7b** | **`id_namespace_registry.layer1.yaml`**               |  • schemas (ID columns) • rng\_contracts                                      | bit-width, sequencing, derivation formula                                  | Downstream layers allocate new IDs without collision and reference upstream ones.                   |
| **7c** | **`prior_library.layer1.yaml`**                       |  • maths appendix symbol tables<br> • artefact YAML/CSV containing priors     | distribution & hyper-params, artefact path                                 | Later behavioural layers reuse the same priors and track changes by digest.                         |
| **7d** | **`taxonomy.layer1.yaml`**                            |  • logging contracts (event types)<br> • performance specs (metric names)     | canonical `event_types`, `metrics`, `log_levels` enums                     | Logging contract payload schemas must reference these enums; observability dashboards rely on them. |
| **8**  | **`layer1_merchant_location_realism.manifest.yaml`**  |  • SHA-256 of every file from steps 1-7                                       | sub-segment digests, link-contract digests, component digests, bundle hash | Downstream layers pin **one** hash—the manifest’s bundle SHA-256—to trust all of Layer 1.           |

---

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

######################################################################################################
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
        path: config/layer1/1A/models/hurdle/exports/version={config_version}/{iso8601_timestamp}/hurdle_coefficients.yaml
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
######################################################################################################

## `DATASET_DICTIONARY.<LAYER-ID>.yaml` (layer scope))

Below are is the template for ( `dataset_dictionary.layer1.yaml` ).

> **File:** `dataset_dictionary.layer1.yaml`
> *Use once per layer; each sub-segment references rows here.*

```yaml
# dataset_dictionary.<layer_or_subsegment>.yaml
version: "1.0"

lifecycle:
  phase: "planning"        # planning|alpha|beta|stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"]

layer:
  id: "<layer_id>"
  name: "<Layer descriptive name>"

# ── External / seed / canonical inputs ─────────────────────────────────────
reference_data:
  - id: "<short_id>"
    status: "approved"                 # proposed|approved|deprecated
    owner_subsegment: "ingress"
    description: "<What this file is used for>"
    version: "<YYYY-MM-DD or semver>"
    format: "<csv|shapefile|cog|...>"
    path: "<repo-relative path or s3://…>"
    partitioning: []                  # list directory keys e.g. ["year","month"]
    ordering: []                      # row sort keys
    schema_ref: "schemas.ingress.<layer_id>.yaml#/<pointer>"
    columns:                           # OR columns_ref: "<pointer>"
      - { name: "<col>", dtype: "<dtype>", semantics: "<meaning>" }
    lineage:
      produced_by: null               # external
      consumed_by: ["<subsegment_id>"]
      final_in_layer: false
    retention_days: 1095
    pii: false
    licence: "<CC-BY-4.0 | ODbL-1.0 | Proprietary-Internal>"

# ── Internally generated datasets ──────────────────────────────────────────
datasets:
  - id: "<short_id>"
    status: "approved"
    owner_subsegment: "<first_producing_subsegment>"
    description: "<One-line purpose>"
    version: "{manifest_key}"
    format: "parquet"
    path: "data/<area>/<dataset>/{manifest_key}/"
    partitioning: []                  # ["manifest_key"] etc.
    ordering: []
    schema_ref: "schemas.<layer_id>.yaml#/pointer"
    columns: []                       # or columns_ref: "..."
    lineage:
      produced_by: "<spark_job_or_fn>"
      consumed_by: ["<subsegment_id>", "..."]
      final_in_layer: false
    retention_days: 365
    pii: false
    licence: "Proprietary-Internal"

# Add as many dataset blocks as needed …                                   #

# ── Governance / integrity ────────────────────────────────────────────────
integrity:
  bundled_schema_sha256: null
  dataset_count: <INT>

open_questions:
  - id: "any_outstanding_issue"
    note: "<clarification needed>"
    owner: "<team>"
    due_by: null

waivers:
  - id: "any_temporary_waiver"
    covers_datasets: ["<id1>", "<id2>"]
    reason: "<reason>"
    expires_on: "YYYY-MM-DD"
```

**Key points**

* **One file per layer**—not per sub-segment—so downstream specs have a single lookup table.
* Each dataset row includes a `schema_ref` that points into the authoritative `schemas.<ID>.yaml` file, avoiding duplication.
* `lineage.produced_by` / `consumed_by` lets CI auto-check that every referenced dataset has both a writer and at least one reader, or is explicitly marked `final_in_layer: true`.
* `integrity.bundled_schema_sha256` lets your release process pin *all* Layer 1 schema digests with one hash.

---


######################################################################################################
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
######################################################################################################

## `FUNCTION_REGISTRY.<ID>.yaml` & `PARAMETER_DICTIONARY.<ID>.yaml`

These “mathematics appendices” are exactly what most teams are missing: they’re the **computational source‑of‑truth** (formulae, distributions, parameter linkages, code refs). They shouldn’t be forced into the Interface‑Contract body; instead, keep them **as a separate, governed component** that other docs *reference and validate against*.

Below is how I’d place and use them, plus a small set of templates so you can operationalize them in CI without rewriting the appendices.

---

#### Where they fit in the doc set

Add a sixth component to the thin Interface Contract:

```yaml
components:
  math_spec:
    file: "mathematics_appendix_<ID>.txt"
    sha256: null     # pinned by CI to catch drift
    required: true
```

Then **link from other components to the math spec**:

* **Invariants**: many rules are direct consequences of the math (e.g., NB multi must yield $N\ge2$; ZTP retry cap 64; LRR error bound $|n_i-w_iN|\le1$). Your 1A appendix states each of these explicitly, so invariants should cite those sections.&#x20;
* **RNG**: required event sets and counter semantics fall out of the algorithmic steps listed in the appendices (e.g., hurdle→gamma→poisson→nb\_final→dirichlet, with `stream_jump` and `sequence_finalize`).&#x20;
* **Logging**: payload fields and “must include” keys are enumerated in the math appendices for 1A/1B (e.g., `lambda_extra` for ZTP, Fenwick build fields, placement failure reasons).
* **Schemas**: some field shapes/semantics are defined here (e.g., site‑ID sequencing, event\_time storage, fold bit, tz index digest).
* **Validation/Perf**: acceptance envelopes come straight from the math (e.g., share convergence, barcode slope, router long‑run share/correlation checks, throughput thresholds).

In short, the appendices become **normative** for algorithms and parameterization; the other specs are **contractual wrappers** that bind IO, determinism, logging, and SLOs to those algorithms.

---

#### What to *do* with the appendices (honest, practical plan)

1. **Register them as governed artefacts**
   Treat each appendix as a tracked input with a pinned digest. Put the filename and hash in your artefact registry and the Interface Contract’s `components.math_spec`. (You already do this rigorously elsewhere—apply the same pattern here.)

2. **Derive two machine‑readable indices from them (lightweight, not rewrites):**

   * **Function Registry**: one YAML per sub‑segment that catalogs *each function/computation* named in the appendix, with inputs/outputs, units, RNG consumption, code refs, and which invariants/log events it touches.
   * **Parameter Dictionary**: a flat list of *symbols and parameters* appearing in the formulas, mapped to their **operational names** (dataset columns / YAML keys), with units and ranges.

3. **Use CI to cross‑link**

   * Every **invariant** must reference at least one function or parameter from the Function Registry.
   * Every **logging event** must list its payload fields; CI checks those fields are mentioned in either the Function Registry or the appendix section it cites.
   * Every **schema column** that originates from a formula (e.g., `event_time_utc`, `fold`, `site_id`) must have a back‑reference to the math that defines it.

4. **Property tests from the math**
   Write tiny deterministic vectors (or ranges) where the math implies a property (LRR sums to $N$; ZTP `k=0` never appears; alias sampling reproduces $p$ in long‑run; DST conversions obey the gap/fold rules). Those test recipes are already present in the appendices (often with exact equations and code pointers).

---

### A) Function Registry (per sub‑segment)

Save as `function_registry.<ID>.yaml`

```yaml
version: "1.0"
subsegment: { id: "TBD", name: "TBD" }
math_spec_ref: { file: "mathematics_appendix_<ID>.txt", sha256: null }

functions:
  - id: "hurdle_logistic"
    section_ref: "A.1"                     # points into the appendix
    purpose: "Decide single vs multi-site"
    code_refs: ["generator/hurdle.py:logit_decide"]
    inputs:
      - { name: "mcc", source: "ingress.merchant_core.mcc", dtype: "int|enum", units: null }
      - { name: "channel", source: "ingress.merchant_core.channel", dtype: "enum", units: null }
      - { name: "gdp_bucket", source: "artefact:gdp_bucket_map", dtype: "int", units: null }
      - { name: "beta", source: "artefact:hurdle_coefficients", dtype: "vector<float64>", units: null }
    outputs:
      - { name: "pi", dtype: "float64", units: null }
      - { name: "is_multi", dtype: "bool", units: null }
    randomness:
      draws: [{ dist: "Uniform(0,1)", count: 1, stream: "1A" }]
      rejection: null
    touches:
      invariants: ["nb-multi-requires-N>=2"]
      logging_events: ["hurdle_bernoulli"]
      egress_columns: []
    notes: "Logit with MCC/channel/dev dummies."
```

> You’ll add one entry per computation in each appendix: NB mixture, ZTP, Gumbel‑top‑k, Dirichlet, LRR, Fenwick scaling, Alias build/sample, TZ fold hashing, etc. The math already lists formulas and code refs (e.g., 1A A.1–A.12, 1B Sections 1–18, 2A A.1–A.10, 2B A.1–A.10, 3A A.1–A.12, 3B A.1–A.9, 4A/4B global constructs).

### B) Parameter Dictionary (per sub‑segment)

Save as `parameter_dictionary.<ID>.yaml`

```yaml
version: "1.0"
subsegment: { id: "TBD", name: "TBD" }
math_spec_ref: { file: "mathematics_appendix_<ID>.txt", sha256: null }

parameters:
  - symbol: "mu"
    meaning: "NB mean"
    appears_in: ["A.2"]
    source_binding: { type: "artefact_or_model", name: "nb_dispersion_coefficients|mean_link" }
    dtype: "float64"
    units: null
    valid_range: { min: 0.0, max: null }
  - symbol: "phi"
    meaning: "NB dispersion"
    appears_in: ["A.2"]
    source_binding: { type: "artefact_or_model", name: "nb_dispersion_coefficients|dispersion_link" }
    dtype: "float64"
    units: null
    valid_range: { min: 0.0, max: null }
  - symbol: "lambda_extra"
    meaning: "ZTP Poisson rate"
    appears_in: ["A.3"]
    source_binding: { type: "derived", expression: "theta0 + theta1*log(N)" }
    dtype: "float64"
    units: null
    valid_range: { min: 0.0, max: null }
```

> This resolves symbols (μ, ϕ, λ, α, κ, σ, etc.) to their operational names/locations so your schemas/invariants can point to the same objects the equations use. Examples exist across the appendices: NB links & mappings in 1A; Fenwick scaler $S$ and integer weights $\tilde w_i$ in 1B; DST fields in 2A; alias arrays in 2B; Dirichlet and floors in 3A; edge rounding $k_c$ in 3B; parameter‑hash/seed/jump in 4A/4B.

---

#### Why keep the appendices separate (and governed)

* They already capture the **complete algorithmic sequence** per stage (e.g., 1A’s hurdle→NB→ZTP→Gumbel→Dirichlet→LRR→ID sequencing, with explicit logging schema). Folding that into the interface file would bloat it and risk drift.&#x20;
* They contain **code paths** and **units** that are essential for reproducibility but don’t belong in IO contracts (e.g., Fenwick integer scaling $S$, polygon sampling, road proximity filters, attempt caps; alias build/save formats; RLE and fold hashing).
* Validation math (e.g., share convergence, barcode slope, Beta intervals, GLM dispersion) is **global** and feeds your 4B validators; it’s better referenced once than repeated.

---

#### What CI can automate directly from these appendices

* **Coverage check:** Every function in the appendix must appear in `function_registry.<ID>.yaml`; warn on gaps (you said 90% confident—this quantifies the remaining 10%).
* **Binding check:** Every parameter symbol used in any function must appear in the **Parameter Dictionary** with a bound source (dataset column, artefact key, or derived expression).
* **Interface link:** Each invariant in `invariants.<ID>.yaml` must cite `functions[*].id` and/or `parameters[*].symbol` that justify the rule.
* **Logging link:** For every mandated event in the appendix, assert a matching entry in `logging_contract.<ID>.yaml` with required payload fields (e.g., `lambda_extra` for ZTP; `fenwick_build` fields; `routing_checksum`).
* **Golden properties:** Auto‑run micro tests derived from the math (e.g., ZTP never yields 0; LRR sums to $N$; `event_time_utc` calculation; fold bit parity; alias long‑run shares).

---

#### If you want, I can convert one appendix into a Function Registry now

For example, I can turn **1A** into a `function_registry.1A.yaml` with entries for:

* `hurdle_logistic` (A.1), `nb_mixture` (A.2), `ztp_poisson` (A.3), `ccy_to_country` (A.4), `gumbel_topk` (A.5), `dirichlet_draw` (A.6), `largest_remainder_round` (A.7), `site_id_sequence` (A.8), `manifest_param_hash` (A.9), `seed_counter_map` (A.10), `lineage_policy` (A.11), and the **event taxonomy** linkage (A.12).&#x20;

That would give you a concrete example to pattern‑match across 1B–4B and immediately highlight any missing parameters or unbound symbols.

---

#### Bottom line

* Keep the appendices **as they are**—they’re the **math‑normative spec**.
* Add **two small, machine‑readable indices** (Function Registry + Parameter Dictionary) per sub‑segment that *point back* to the appendix and *bind* symbols to operational names.
* Reference the appendix from the Interface Contract as a **component with a pinned digest**, and wire CI to check coverage and consistency across **schemas, invariants, RNG, logging, and performance**.

### Minimal Stubs
Great—here’s a **practical stub** for one sub‑segment (**2B – Routing transactions through sites**) showing both files you asked for. I kept them tight but useful: each function lists inputs/outputs and where randomness/logging is involved; each symbol in the parameter dictionary is bound to a source or config. After the YAML, I’ve added short grounding notes so you can verify against the appendix quickly.

---

#### `function_registry.2B.yaml` (stub)

```yaml
version: "1.0"
subsegment: { id: "2B", name: "Routing transactions through sites" }
math_spec_ref: { file: "mathematics_appendix_2B.txt", sha256: null }

functions:

  - id: "weight_normalization"
    section_ref: "A.1"
    purpose: "Turn raw site weights F into a probability vector p"
    code_refs: ["router/io.py:load_weights"]
    inputs:
      - { name: "F", source: "artefacts/site_catalogue.parquet", dtype: "float64[]" }
    outputs:
      - { name: "p", dtype: "float64[]", semantics: "normalized weights (sum=1)" }
      - { name: "W", dtype: "float64", semantics: "sum(F)" }
    randomness: { draws: [], rejection: null }
    touches:
      invariants: ["no_zero_weight_distribution?"]
      logging_events: []
      egress_columns: []
    notes: "Abort if W==0 via RoutingZeroWeightError"

  - id: "build_alias_table"
    section_ref: "A.2"
    purpose: "Build Vose alias arrays for O(1) sampling"
    code_refs: ["router/alias.py:build_alias_table"]
    inputs:
      - { name: "p", source: "weight_normalization", dtype: "float64[]" }
    outputs:
      - { name: "prob", dtype: "uint32[]"}
      - { name: "alias", dtype: "uint32[]"}
      - { name: "alias_npz_path", dtype: "path" }
    randomness: { draws: [], rejection: null }
    touches:
      invariants: []
      logging_events: []
      egress_columns: []

  - id: "corporate_day_effect"
    section_ref: "A.3"
    purpose: "Daily log‑normal multiplier γ_d for cross‑zone co‑movement"
    code_refs: ["router/seed.py:derive_philox_seed", "router/prng.py:get_uniform"]
    inputs:
      - { name: "global_seed", source: "manifest", dtype: "bytes" }
      - { name: "merchant_id", source: "ingress", dtype: "int64" }
      - { name: "sigma_gamma_sq", source: "config/routing/routing_day_effect.yml", dtype: "float64" }
    outputs:
      - { name: "gamma_d", dtype: "float64", semantics: "lognormal multiplier" }
    randomness:
      draws:
        - { dist: "Uniform(0,1)", count: 1, stream: "philox", counter: "0 per day" }
      rejection: null
    touches:
      invariants: []
      logging_events: []
      egress_columns: []

  - id: "sample_site_alias"
    section_ref: "A.4"
    purpose: "O(1) site sampling using alias arrays"
    code_refs: ["router/sampler.py:sample_site"]
    inputs:
      - { name: "prob", source: "build_alias_table", dtype: "uint32[]" }
      - { name: "alias", source: "build_alias_table", dtype: "uint32[]" }
      - { name: "N_m", source: "derived(len(prob))", dtype: "int32" }
      - { name: "day_index", source: "clock", dtype: "int32" }
      - { name: "i", source: "internal_counter", dtype: "int64" }
    outputs:
      - { name: "site_index", dtype: "int32" }
      - { name: "site_id", dtype: "int64" }
    randomness:
      draws:
        - { dist: "Uniform(0,1)", count: 1, counter: "d+1+i" }
      rejection: null
    touches:
      invariants: []
      logging_events: ["alias_sample"]
      egress_columns: []

  - id: "sample_cdn_country"
    section_ref: "A.5/A.12"
    purpose: "Alias sampling over CDN country weights for virtual merchants"
    code_refs: ["router/alias.py:build_alias_table","router/sampler.py:sample_cdn_country"]
    inputs:
      - { name: "Q", source: "config/routing/cdn_country_weights.yaml", dtype: "float64[]" }
    outputs:
      - { name: "ip_country_code", dtype: "string" }
    randomness:
      draws:
        - { dist: "Uniform(0,1)", count: 1 }
      rejection: null
    touches:
      invariants: []
      logging_events: ["cdn_alias_sample"]
      egress_columns: []

  - id: "audit_checksum"
    section_ref: "A.6"
    purpose: "Batch checksum over cumulative counts"
    code_refs: ["router/audit.py:emit_checksum"]
    inputs:
      - { name: "merchant_id", source: "ingress", dtype: "int64" }
      - { name: "batch_index", source: "internal", dtype: "int64" }
      - { name: "C", source: "router state (cumulative counts)", dtype: "uint64[]" }
    outputs:
      - { name: "checksum", dtype: "char(64)" }
    randomness: { draws: [], rejection: null }
    touches:
      invariants: []
      logging_events: ["routing_batch_checksum"]
      egress_columns: []

  - id: "validation_metrics_longrun"
    section_ref: "A.7/A.14"
    purpose: "Long‑run share deviation and hour‑corr checks"
    code_refs: ["router/validation.py:run_checks"]
    inputs:
      - { name: "C", source: "counts", dtype: "int64[]" }
      - { name: "p", source: "weight_normalization", dtype: "float64[]" }
      - { name: "epsilon_p", source: "routing_validation.yml", dtype: "float64" }
      - { name: "rho_star", source: "routing_validation.yml", dtype: "float64" }
    outputs:
      - { name: "assertion_status", dtype: "bool" }
    randomness: { draws: [], rejection: null }
    touches:
      invariants: ["share_deviation_within_epsilon","hourly_corr_within_epsilon"]
      logging_events: ["validation_failed?"]
      egress_columns: []

  - id: "guard_zero_weight"
    section_ref: "A.8"
    purpose: "Abort if total weight W==0"
    code_refs: ["router/errors.py:check_zero_weight"]
    inputs:
      - { name: "W", source: "weight_normalization", dtype: "float64" }
    outputs: []
    randomness: { draws: [], rejection: null }
    touches:
      invariants: ["no_zero_weight_distribution"]
      logging_events: ["routing_error"]

  - id: "perf_metrics"
    section_ref: "A.9"
    purpose: "Emit throughput (MB/s) and memory (GB)"
    code_refs: ["router/metrics.py"]
    inputs:
      - { name: "bytes_routed", source: "router", dtype: "uint64" }
      - { name: "elapsed_seconds", source: "clock", dtype: "float64" }
    outputs:
      - { name: "TP_MBps", dtype: "float64" }
      - { name: "Mem_GB", dtype: "float64" }
    randomness: { draws: [], rejection: null }
    touches:
      invariants: []
      logging_events: ["metrics"]

  - id: "manifest_and_artifact_governance"
    section_ref: "A.10"
    purpose: "Compute and enforce routing manifest digest"
    code_refs: ["router/manifest.py"]
    inputs:
      - { name: "artefact_list", source: "routing_manifest.json", dtype: "list<path>" }
    outputs:
      - { name: "routing_manifest_digest", dtype: "char(64)" }
    randomness: { draws: [], rejection: null }
    touches:
      invariants: ["manifest_digest_present"]
      logging_events: []

  - id: "scaled_threshold_lookup"
    section_ref: "A.11"
    purpose: "Scale acceptance threshold per group without alias rebuild"
    code_refs: ["router/sampler.py:sample_site (mode: scaled_threshold)"]
    inputs:
      - { name: "gamma_d", source: "corporate_day_effect", dtype: "float64" }
      - { name: "group", source: "tz_cluster", dtype: "id" }
    outputs:
      - { name: "site_index", dtype: "int32" }
    randomness:
      draws:
        - { dist: "Uniform(0,1)", count: 1 }
      rejection: null
    touches:
      invariants: []
      logging_events: ["alias_sample"]

  - id: "routing_audit_log_schema"
    section_ref: "A.13"
    purpose: "Define required audit fields and ordering constraints"
    code_refs: ["router/audit.py:append_event"]
    inputs: []
    outputs: []
    randomness: { draws: [], rejection: null }
    touches:
      invariants: ["required_audit_fields_present","event_ordering_monotone"]
      logging_events: ["routing_batch_checksum","routing_error","OOM"]

  - id: "license_and_provenance_enforcement"
    section_ref: "A.15"
    purpose: "Verify LICENSE digests for all governed inputs"
    code_refs: ["router/license_check.py:verify"]
    inputs:
      - { name: "LICENSES/*", source: "repo", dtype: "path[]" }
    outputs:
      - { name: "license_check_status", dtype: "bool" }
    randomness: { draws: [], rejection: null }
    touches:
      invariants: ["license_digest_matches"]
      logging_events: ["routing_error"]
```

---

#### `parameter_dictionary.2B.yaml` (stub)

```yaml
version: "1.0"
subsegment: { id: "2B", name: "Routing transactions through sites" }
math_spec_ref: { file: "mathematics_appendix_2B.txt", sha256: null }

parameters:
  - symbol: "F_i"
    meaning: "Raw foot-traffic/site weight for site i"
    appears_in: ["A.1"]
    source_binding: { type: "dataset", name: "artefacts/site_catalogue.parquet", column: "F" }
    dtype: "float64"
    units: null
    valid_range: { min: 0.0, max: null }

  - symbol: "W"
    meaning: "Total raw weight"
    appears_in: ["A.1","A.8"]
    source_binding: { type: "derived", expression: "sum(F_i)" }
    dtype: "float64"
    units: null
    valid_range: { min: 0.0, max: null }

  - symbol: "p_i"
    meaning: "Normalized site probability"
    appears_in: ["A.1","A.2","A.4"]
    source_binding: { type: "derived", expression: "F_i / W" }
    dtype: "float64"
    units: null
    valid_range: { min: 0.0, max: 1.0 }

  - symbol: "N_m"
    meaning: "Number of sites for merchant m"
    appears_in: ["A.2","A.4"]
    source_binding: { type: "derived", expression: "len(p)" }
    dtype: "int32"
    units: null
    valid_range: { min: 1, max: null }

  - symbol: "prob[k]"
    meaning: "Alias acceptance threshold for index k"
    appears_in: ["A.2","A.4"]
    source_binding: { type: "artefact", name: "<merchant_id>_alias.npz:prob" }
    dtype: "uint32"
    units: null
    valid_range: { min: 0, max: null }

  - symbol: "alias[k]"
    meaning: "Alias index for fallback when u<threshold fails"
    appears_in: ["A.2","A.4"]
    source_binding: { type: "artefact", name: "<merchant_id>_alias.npz:alias" }
    dtype: "uint32"
    units: null
    valid_range: { min: 0, max: null }

  - symbol: "u"
    meaning: "Uniform(0,1) draw for sampling"
    appears_in: ["A.4","A.11"]
    source_binding: { type: "rng", name: "philox", stream: "router", counter: "d+1+i" }
    dtype: "float64"
    units: null
    valid_range: { min: 0.0, max: 1.0 }

  - symbol: "k"
    meaning: "Floor(u*N_m) index"
    appears_in: ["A.4","A.11"]
    source_binding: { type: "derived", expression: "floor(u * N_m)" }
    dtype: "int32"
    units: null
    valid_range: { min: 0, max: "N_m-1" }

  - symbol: "f"
    meaning: "Fractional part of u*N_m"
    appears_in: ["A.4"]
    source_binding: { type: "derived", expression: "u * N_m - k" }
    dtype: "float64"
    units: null
    valid_range: { min: 0.0, max: 1.0 }

  - symbol: "gamma_d"
    meaning: "Corporate-day multiplier"
    appears_in: ["A.3","A.11"]
    source_binding: { type: "derived", expression: "exp(mu_gamma + sigma_gamma * Phi^{-1}(u_d))" }
    dtype: "float64"
    units: null
    valid_range: { min: 0.0, max: null }

  - symbol: "epsilon_p"
    meaning: "Tolerance for share deviation"
    appears_in: ["A.7","A.14"]
    source_binding: { type: "config", name: "routing_validation.yml:epsilon_p" }
    dtype: "float64"
    units: null
    valid_range: { min: 0.0, max: 0.1 }   # TBD exact bound

  - symbol: "rho_star"
    meaning: "Target hour-correlation between top-2 zones"
    appears_in: ["A.7","A.14"]
    source_binding: { type: "config", name: "routing_validation.yml:rho_star" }
    dtype: "float64"
    units: null
    valid_range: { min: -1.0, max: 1.0 }

  - symbol: "B"
    meaning: "Batch size for checksum"
    appears_in: ["A.6"]
    source_binding: { type: "constant", name: "batch_events", value: 1000000 }
    dtype: "int64"
    units: "events"
    valid_range: { min: 1, max: null }

  - symbol: "routing_manifest_digest"
    meaning: "SHA-256 digest of routing manifest"
    appears_in: ["A.10","A.13"]
    source_binding: { type: "manifest", name: "routing_manifest.json:digest" }
    dtype: "char(64)"
    units: null
    valid_range: { min: null, max: null }

  - symbol: "Q_k"
    meaning: "CDN country probability for index k"
    appears_in: ["A.5","A.12"]
    source_binding: { type: "config", name: "config/routing/cdn_country_weights.yaml" }
    dtype: "float64"
    units: null
    valid_range: { min: 0.0, max: 1.0 }
```

---

#### Grounding notes (so you can cross‑check fast)

* **A.1 – weight normalization** defines $F_i$, $W$, and $p_i=F_i/W$, and points to the zero‑weight guard (A.8).&#x20;
* **A.2 – alias table** construction with `prob[]` and `alias[]` (`uint32`) and deterministic save to `<merchant_id>_alias.npz`.
* **A.3 – corporate‑day effect**: Philox seed derivation, $u_d\in[0,1)$, $\gamma_d=\exp(\mu_\gamma+\sigma_\gamma\Phi^{-1}(u_d))$.&#x20;
* **A.4 – outlet sampling**: $u\rightarrow k=\lfloor uN_m\rfloor$, fraction $f$, then compare to `prob[k]` or use `alias[k]`.&#x20;
* **A.5/A.12 – CDN/virtual routing**: alias over $Q$ from `cdn_country_weights.yaml`, with event logging of selected `ip_country_code`.&#x20;
* **A.6 – audit checksum**: SHA‑256 over `(merchant_id‖batch_index‖BE(C))`, batch size $B=10^6$, log to `routing_audit.log`.&#x20;
* **A.7 – validation metrics** (long‑run share and hour‑corr); **A.14** maps to CI assertions and abort.&#x20;
* **A.8 – zero‑weight error**: `RoutingZeroWeightError(merchant_id)` when $W=0$.&#x20;
* **A.9 – performance metrics** specify throughput and memory with thresholds from config.
* **A.10 – manifest governance**: artifact SHA‑256s and `routing_manifest_digest`; build abort on drift.&#x20;
* **A.11 – scaled‑threshold**: per‑group scale $s_G$ and accept if $u<\text{prob}[k]\cdot s_G$ without alias rebuild.&#x20;
* **A.13 – routing audit/event schema**: required fields and “mandatory” coverage rules.&#x20;

---

#### How to use these stubs
* In CI, add **coverage checks**:

  * Every `functions[*].section_ref` must exist in the appendix.
  * Every symbol mentioned in any `functions[*].inputs/outputs` is present in the **parameter dictionary**.
* As you tighten things, replace `null`/`TBD` and wire these into your **Interface Contract (v1.1)** via a `components.math_spec` pointer and digest pin.



######################################################################################################
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
######################################################################################################
\

## `LINK_CONTRACT.<N→N+1>.yaml`

**Short take – your draft is *almost* there.**
For a link-contract that CI can generate and downstream specs can trust you only need:

* Both sub-segments’ **interface-contract digests** (not the raw schema digests) – that proves you compared *exact* contracts, not just the schema JSON chunks.
* A **machine-readable diff block** so a failure tells engineers *why* the link broke.
* A tiny **integrity section** (CI hashes the whole file) so the layer-manifest can pin it.

Everything else in your stub is on the right track.
Below is a tightened template that CI can produce automatically and that the layer-manifest can pin.

---

### Recommended `link_contract.<FROM>_to_<TO>.yaml` (v1.0)

```yaml
# link_contract.<FROM>_to_<TO>.yaml — CI-generated; do NOT hand-edit
link_version: "1.0"

boundary: "1B->2A"                  # human label
generated_at: null                  # CI writes ISO-8601

from:
  id: "1B"
  interface_contract: "interface_contract.1B.yaml"
  sha256: null                      # digest of the entire interface contract
  egress_ref: "schemas.1B.yaml#/egress/datasets"

to:
  id: "2A"
  interface_contract: "interface_contract.2A.yaml"
  sha256: null
  ingress_ref: "schemas.2A.yaml#/ingress/datasets"

# 1. Dataset & column compatibility map
mapping:
  datasets:
    - from: "site_catalogue"        # dataset id as produced by 1B
      to:   "site_catalogue_ingress" # dataset id expected by 2A
      column_map:
        site_id:          "site_id"
        lat:              "lat"
        lon:              "lon"
        tzid_operational: "tzid_operational"
      allowed_transforms:
        - "partitioning_change"     # path/partition scheme may differ
        - "ordering_change"         # sort order may differ
      notes: null

# 2. Invariant reconciliation
invariants_reconciled:
  - { id: "no_null_coords",    status: "satisfied" }
  - { id: "iso2-codes-format", status: "satisfied" }
  - { id: "tzid_present",      status: "satisfied" }

# 3. Compatibility result
compatibility_result:
  status: "pass"                    # pass | fail
  failures: []                      # on fail, CI lists mismatches here
  warnings: []

# 4. Integrity (CI fills; layer-manifest pins this hash)
integrity:
  sha256: null
```

#### Why this is “good enough”

| Field                           | Reason                                                                                                                                         |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `interface_contract` + `sha256` | Proves which exact contract versions were compared; if either upstream or downstream changes, CI regenerates this file and the digest changes. |
| `mapping.datasets[].column_map` | Minimal one-to-one map; if names match you can let CI generate an identity map automatically.                                                  |
| `allowed_transforms`            | Keeps the link flexible (partitioning / ordering changes are benign; type changes are not).                                                    |
| `invariants_reconciled`         | States which cross-boundary rules are upheld so downstream invariants don’t have to re-check.                                                  |
| `compatibility_result`          | Single status + machine-readable lists of failures/warnings for CI logs.                                                                       |
| `integrity.sha256`              | Layer-manifest pins this; any silent change breaks the bundle hash and fails the build.                                                        |

---

### CI workflow (fully automated)

1. **After** both `interface_contract.<FROM>.yaml` and `interface_contract.<TO>.yaml` pass linting, the build script:

   * loads the egress schema JSON from `<FROM>` and ingress schema JSON from `<TO>`,
   * computes column/dataset diffs,
   * writes this `link_contract.<FROM>_to_<TO>.yaml` with `status: pass` or `fail`,
   * computes its own SHA-256 and inserts it in the file.
2. The layer-manifest job then collects every link contract’s digest and pins them.
3. **No human edits** – any manual change would alter the digest, break the manifest, and fail CI.


######################################################################################################
######################################################################################################
######################################################################################################

## `ERROR_CATALOGUE.LAYER1.yaml`
```yaml
# error_catalogue.layer1.yaml — global catalogue of all runtime exceptions & error codes for Layer 1
version: "1.0"

lifecycle:
  phase: "planning"                 # planning | alpha | beta | stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"] # no TBD/null once the layer is ≥ beta

layer:
  id: "layer1"
  name: "Merchant Location Realism"

conventions:
  code_format: "E{SubSeg}{3-digit}" # e.g., E1A001, E2B004 …
  severity_enum: ["INFO","WARN","ERROR","FATAL"]
  category_enum: ["structural","semantic","stochastic","system","infra","validation"]
  message_template_style: "jinja2"  # {{field}} interpolation

errors:

  - id: "ZTPOissonRetryExhausted"
    code: "TBD"                     # filled when approved, must respect code_format
    originating_subsegment: "1A"
    status: "proposed"              # proposed | approved | deprecated
    severity: "ERROR"
    category: "stochastic"
    message_template: |
      Exceeded {{cap_retries}} ZTP retries for merchant={{merchant_id}},
      λ_extra={{lambda_extra}}, rejection_count={{rejection_count}}.
    must_include_fields:
      - "merchant_id"
      - "lambda_extra"
      - "rejection_count"
    invariants_triggered: ["ztp-cap-64"]
    logging_event: "ztp_retry_exhausted"
    remediation: "Tune λ_extra or increase cap_retries; investigate parameter set."
    doc_url: null

  - id: "NBRejectionLoopViolation"
    code: "TBD"
    originating_subsegment: "1A"
    status: "proposed"
    severity: "ERROR"
    category: "stochastic"
    message_template: |
      NB draw loop exceeded retry window for merchant={{merchant_id}},
      draw={{raw_nb_outlet_draw}}, counter={{rejection_count}}.
    must_include_fields: ["merchant_id","raw_nb_outlet_draw","rejection_count"]
    invariants_triggered: ["nb-multi-requires-N>=2"]
    logging_event: "routing_error"
    remediation: "Inspect hurdle parameters and NB dispersion."
    doc_url: null

  # ── Add one block per distinct error across 1A … 4B ──
  # Fields may be left null/TBD until phase ≥ alpha.

groups:                # optional logical bundles
  - id: "fatal_system_errors"
    includes: ["CounterWrapError","RNGAuditMissingEvents"]

integrity:
  error_count: null         # CI fills → total number of error entries
  sha256: null              # CI fills → hash of sorted JSON for drift control

open_questions:
  - id: "code-range-allocation"
    note: "Reserve E3x*** for 3A & 3B? align with fraud layer?"
    owner: "architecture"
    due_by: null

waivers:
  - id: "placeholder-codes"
    covers_errors: ["ZTPOissonRetryExhausted","NBRejectionLoopViolation"]
    reason: "Codes to be assigned after RFC-013 approval"
    expires_on: "2025-10-01"
```

### How this template is “done right”

| Feature                                                  | Purpose                                                                               |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| **Layer-wide scope** & `originating_subsegment`          | Ensures every error is unique across 1A … 4B yet still traceable to its source stage. |
| **Pinned digest via `integrity.sha256`**                 | CI can detect if anyone edits an error definition without a review bump.              |
| **`must_include_fields`**                                | Aligns with logging contract so downstream replay code can rely on a stable payload.  |
| **`invariants_triggered` + `logging_event` cross-links** | Guarantees invariants and audit logs stay consistent with the error catalogue.        |
| **Lifecycle & waivers**                                  | Allows placeholders (`TBD`) during planning but blocks them at beta/stable.           |



######################################################################################################
######################################################################################################
######################################################################################################

## `ID_NAMESPACE_REGISTRY.LAYER1.yaml`

```yaml
# id_namespace_registry.layer1.yaml — canonical registry of every identifier & RNG namespace in Layer 1
version: "1.0"

lifecycle:
  phase: "planning"                 # planning | alpha | beta | stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"]   # no TBD/null once layer ≥ beta

layer:
  id: "layer1"
  name: "Merchant Location Realism"

# 1 ▪ Entity / Record Identifiers
identifiers:

  - id: "merchant_id"
    status: "proposed"                # proposed | approved | deprecated
    owner_subsegment: "seed_import"   # stage that first defines it
    description: "Opaque 64-bit synthetic merchant identifier"
    bit_width: 64
    signed: false
    uniqueness_scope: "global"        # global | per-X (specify)
    sequencing:
      strategy: "random"              # sequential | random | hash | ULID | other
      algorithm: "philox-stream 0 seed=parameter_hash"   # if random/hash
      collision_handling: "reject"    # reject | retry | modulo
    format:
      display: "decimal"              # decimal | hex | base32 | string
      regex: "^[0-9]{1,20}$"
    example: "123456789012"
    pii: false
    cross_layer: true                 # referenced outside Layer 1?
    provenance_fields_in_schema: []   # dataset.column where it appears first
    references:
      datasets_produced: ["merchant_core"]
      datasets_consumed: ["outlet_catalogue","routing_events"]
      logging_fields: ["merchant_id"]
      rng_streams: ["per-merchant"]
    notes: null

  - id: "site_id"
    status: "proposed"
    owner_subsegment: "1A"
    description: "6-digit per-(merchant,legal_country) outlet sequence"
    bit_width: 24                     # 6 decimal digits ≈ 2^20
    signed: false
    uniqueness_scope: "merchant+country"
    sequencing:
      strategy: "sequential"
      start_at: 1
      padding: 6
      collision_handling: "abort"
    format: { display: "string", regex: "^[0-9]{6}$" }
    example: "000123"
    cross_layer: true
    provenance_fields_in_schema: ["outlet_catalogue.site_id"]
    references:
      datasets_produced: ["outlet_catalogue"]
      datasets_consumed: ["site_catalogue","rng_audit_log"]
      logging_fields: ["site_id"]
      rng_streams: ["per-site"]
    notes: null

  # ── Add one block for each ID: edge_id (3B), tzlookup_id (2A), routed_tx_id (2B), validation_id (4B) etc. ──

# 2 ▪ RNG & Counter Namespaces
rng_namespaces:

  - id: "1A"
    status: "proposed"
    description: "All Philox sub-streams for merchant→site generation"
    counter_bits: 128
    key_bits: 64
    derivation:
      namespace_string: "1A"
      seed_fields: ["manifest_fingerprint","run_seed"]
      variables: ["merchant_id"]
      formula: "philox_key = first_64_le_bits(SHA256(namespace||merchant_id))"
    jump_stride_source: "SHA256(namespace||merchant_id)[:16]"
    audit_event_required: true        # stream_jump must be logged
    required_event_set: ["hurdle_bernoulli","gamma_component","poisson_component","nb_final","stream_jump","sequence_finalize"]
    notes: null

  - id: "router"
    status: "proposed"
    description: "Per-merchant or per-merchant-per-day streams for alias sampling"
    counter_bits: 128
    key_bits: 64
    derivation:
      namespace_string: "2B-router"
      seed_fields: ["parameter_hash","master_seed"]
      variables: ["merchant_id","day_index"]
      formula: "key = SHA256(ns || merchant_id || day_index)[:8]"
    jump_stride_source: "SHA256(ns||merchant_id||day_index)[:16]"
    audit_event_required: true
    required_event_set: ["alias_sample","day_effect_draw","stream_jump"]
    notes: null

  # ── Add one block for each RNG namespace used across the layer ──

# 3 ▪ Integrity & Governance
integrity:
  identifier_count: null              # CI fills
  rng_namespace_count: null           # CI fills
  sha256: null                        # digest of sorted JSON (identifiers+rng_namespaces)

change_management:
  requires:
    - "increment id_namespace_registry.layer1.yaml version"
    - "update ALL affected sub-segment contracts"
    - "owner & architecture approval"

open_questions:
  - id: "edge_id-bitwidth"
    note: "Decide 3B edge_id width (32 vs 48 bits)"
    owner: "3B-design"
    due_by: null

waivers:
  - id: "rng-namespace-review"
    reason: "Namespace for validation layer still in flux"
    expires_on: "2025-10-15"
```

### How this template is “production-ready”

1. **Single source of truth** – every identifier & RNG namespace is declared exactly once.
2. **Direct cross-links** – `references.datasets_produced / consumed / logging_fields / rng_streams` make CI verify that each ID really appears where declared.
3. **Bit-width + sequencing rules** – prevents silent overflow or collision when new IDs are added.
4. **Pinned integrity hash** – any change triggers a digest diff in the Layer Manifest, forcing review.
5. **Lifecycle & waivers** – allows placeholders now, blocks them when the layer matures.

######################################################################################################
######################################################################################################
######################################################################################################

## `PRIOR_LIBRARY.LAYER1.yaml`
```yaml
# prior_library.layer1.yaml ── canonical index of every model prior / hyper-parameter
# ────────────────────────────────────────────────────────────────────────────────
#  PURPOSE
#  • One per *layer* (not per stage) so later layers can import priors by ID.
#  • Each entry names the symbol, its distribution or fixed value, where it comes
#    from (artefact / config), and which functions in the Function Registry use it.
#  • CI will hash this file; any change bumps layer-manifest version.
# ────────────────────────────────────────────────────────────────────────────────
version: "1.0"

lifecycle:
  phase: "planning"                 # planning | alpha | beta | stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true          # `null` or "TBD" permitted while ≤ alpha
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"] # placeholders outlawed once ≥ beta

layer:
  id: "layer1"
  name: "Merchant Location Realism"

# ── GLOBAL METADATA ABOUT THE LIBRARY ───────────────────────────────────────────
defaults:
  dtype: "float64"
  units: null
  status: "proposed"                # proposed | approved | deprecated

# ── LIST OF PRIORS / HYPER-PARAMETERS ──────────────────────────────────────────
priors:

  - id: "beta_hurdle"               # unique, camel_or_snake; referenced by code
    symbol: "β"                     # TeX/Greek symbol (informational)
    description: "Logistic-link coefficients for hurdle (single vs multi-site)"
    originating_subsegment: "1A"
    source:
      type: "artefact"              # artefact | config | constant | derived
      path: "hurdle_coefficients.yaml"
      key: "beta_vector"
    prior_type: "vector"
    distribution: null              # fixed vector, so no prior distribution
    shape: [K]                      # comment: K = number of MCC/channel dummies
    dtype: "float64"
    units: null
    default_value: null
    valid_range: null
    used_by_functions: ["hurdle_logistic"]
    status: "proposed"
    last_updated: null
    references:
      math_sections: ["A.1"]
      docs_url: null

  - id: "phi_nb_dispersion"
    symbol: "ϕ"
    description: "Dispersion parameter for NB mixture in outlet count model"
    originating_subsegment: "1A"
    source:
      type: "artefact"
      path: "nb_dispersion_coefficients.yaml"
      key: "phi"
    prior_type: "scalar"
    distribution:
      name: "InverseGamma"
      parameters: { alpha: 2.0, beta: 1.0 }   # p(ϕ) ∝ ϕ^{-α−1} e^{−β/ϕ}
    dtype: "float64"
    units: null
    default_value: null
    valid_range: { min: 0.0, max: null }
    used_by_functions: ["nb_mixture"]
    status: "proposed"
    last_updated: null
    references:
      math_sections: ["A.2"]
      docs_url: null

  - id: "sigma_gamma_sq"
    symbol: "σ_γ²"
    description: "Variance of log-normal day-effect multiplier γ_d"
    originating_subsegment: "2B"
    source:
      type: "config"
      path: "config/routing/routing_day_effect.yml"
      key: "sigma_gamma_sq"
    prior_type: "scalar"
    distribution:
      name: "HalfNormal"
      parameters: { scale: 0.5 }     # σ_γ ~ HalfNormal(0, 0.5)
    dtype: "float64"
    units: null
    default_value: null
    valid_range: { min: 0.0, max: 1.0 }
    used_by_functions: ["corporate_day_effect"]
    status: "proposed"
    last_updated: null
    references:
      math_sections: ["A.3"]
      docs_url: null

  # ── Add one block for every prior / hyper-parameter referenced in Functions ──

# ── INTEGRITY & GOVERNANCE ─────────────────────────────────────────────────────
integrity:
  prior_count: null                 # CI fills actual number of priors
  sha256: null                      # CI fills digest of canonical JSON to detect drift

change_management:
  requires:
    - "update Version or lifecycle.phase when priors change shape or distribution"
    - "owner & architecture approval"

open_questions:
  - id: "rho_star_distribution"
    note: "Should ρ* have Beta prior? pending Model RFC-017"
    owner: "2B-modelling"
    due_by: null

waivers:
  - id: "beta_hurdle-placeholder"
    covers_priors: ["beta_hurdle"]
    reason: "Final coefficients depend on MCC regrouping study"
    expires_on: "2025-11-01"
```

### Template rationale (“why it’s built right”)

| Design choice                                                   | Benefit                                                                                                            |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Layer scope** (not per stage)                                 | Later layers need a single, stable library to import from; avoids duplication.                                     |
| **`source` block**                                              | Explicitly binds each prior to an artefact/config/constant, so CI can hash-pin it and the code can load it by key. |
| **`distribution` vs `default_value`**                           | Handles both true Bayesian priors (Inverse-Gamma, Half-Normal, Dirichlet) *and* fixed parameter vectors.           |
| **Cross-refs to `function_registry` and maths section numbers** | Enables automated checks that every function’s parameters are defined, and vice-versa — no orphan symbols.         |
| **Lifecycle + waivers**                                         | Lets you keep placeholders (`null`/`TBD`) in planning while enforcing completeness before β/stable.                |
| **Global integrity hash**                                       | One digest for the whole file; pinned in the Layer-manifest so any silent change forces a review.                  |

Copy this template, list every parameter from the maths appendices (NB μ/ϕ, ZTP λ\_extra, Dirichlet α\_i, LRR ε, fold hash constants, validation priors, etc.), and pin its SHA-256 in your layer-manifest.






## `TAXONOMY.LAYER1.yaml`
```yaml
# taxonomy.layer1.yaml — central list of event-types, metrics, & log-levels for Layer 1
# ────────────────────────────────────────────────────────────────────────────────
#  PURPOSE
#  • Eliminate drift: every sub-segment must use one of these canonical enums.
#  • CI checks: Interface & Logging contracts reference ids defined here.
#  • Layer-scope (one file) → future layers import & extend, never duplicate.
# ────────────────────────────────────────────────────────────────────────────────
version: "1.0"

lifecycle:
  phase: "planning"                   # planning | alpha | beta | stable
  last_reviewed: null
  approver: null

ci_policy:
  allow_placeholders: true
  placeholder_markers: ["TBD", null]
  block_on_phase: ["beta","stable"]   # placeholders outlawed once ≥ beta

layer:
  id: "layer1"
  name: "Merchant Location Realism"

# 1 ▪ Log-level Enum (shared across all sub-segments)
log_levels: ["DEBUG","INFO","WARN","ERROR","FATAL"]

# 2 ▪ Event-type Catalogue
event_types:

  - id: "hurdle_bernoulli"
    status: "proposed"                # proposed | approved | deprecated
    originating_subsegment: "1A"
    severity: "INFO"                  # must be one of log_levels
    description: "Bernoulli draw for single vs multi-site"
    payload:
      required_fields: ["merchant_id","pre_counter","post_counter","pi","outcome"]
    references:
      math_sections: ["1A A.1"]
      logging_contract_ref: "logging_contract.1A.yaml#/event_taxonomy"

  - id: "ztp_rejection"
    status: "proposed"
    originating_subsegment: "1A"
    severity: "WARN"
    description: "Rejected ZTP draw (k=0) before cap"
    payload:
      required_fields: ["merchant_id","lambda_extra","attempt"]
    references:
      math_sections: ["1A A.3"]

  - id: "ztp_retry_exhausted"
    status: "proposed"
    originating_subsegment: "1A"
    severity: "ERROR"
    description: "Exceeded 64 ZTP retries"
    payload:
      required_fields: ["merchant_id","lambda_extra","rejection_count"]
    references:
      error_catalogue_ref: "error_catalogue.layer1.yaml#/errors/0"
      invariants_ref:      "invariants.1A.yaml#/invariants/ztp-cap-64"

  # ── Continue: gamma_component, nb_final, gumbel_key, dirichlet_gamma_vector,
  #              stream_jump, sequence_finalize, fenwick_build, pixel_draw,
  #              tz_lookup, alias_sample, routing_checksum, etc. ──

# 3 ▪ Metrics Catalogue (names consumed by Prometheus / StatsD, etc.)
metrics:

  - name: "throughput_rows_per_sec"
    status: "proposed"
    originating_subsegment: "2B"
    unit: "rows/sec"
    description: "Router processed rows per second (1-minute EWMA)"
    references:
      performance_contract_ref: "performance.2B.yaml#/observability_metrics"

  - name: "latency_ms_p99"
    status: "proposed"
    originating_subsegment: "2B"
    unit: "ms"
    description: "End-to-end p99 latency per batch"
    references: {}

  - name: "nb_rejection_rate_overall"
    status: "proposed"
    originating_subsegment: "1A"
    unit: "ratio"
    description: "Mean NB rejection count divided by total draws"
    references:
      logging_contract_ref: "logging_contract.1A.yaml#/observability"

  # ── Add every metric referenced in performance.*.yaml or invariants.*.yaml ──

# 4 ▪ Integrity & Governance
integrity:
  event_type_count: null          # CI fills
  metric_count: null              # CI fills
  sha256: null                    # CI fills canonical JSON digest

change_management:
  requires:
    - "bump taxonomy.layer1.yaml version"
    - "update affected logging_contracts & performance specs"
    - "owner + architecture approval"

open_questions:
  - id: "metric-units-standard"
    note: "Adopt Prometheus base units or keep free-form?"
    owner: "observability"
    due_by: null

waivers:
  - id: "sample-rate-metric-tbd"
    covers_metrics: ["sample_rate_overall"]
    reason: "Name may change after perf RFC"
    expires_on: "2025-10-15"
```

### Why this template “gets it right”

| Element                                                                               | Purpose                                                                                             |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| **Single list of `log_levels`**                                                       | All logging contracts must pick from this enum—no accidental `Info` vs `INFO`.                      |
| **Event-type sections with `payload.required_fields`**                                | Guarantees every audit log event has a stable, agreed schema (CI validates).                        |
| **Cross-references** (`logging_contract_ref`, `error_catalogue_ref`, `math_sections`) | Lets CI ensure every event & metric mentioned elsewhere is declared here, and vice-versa.           |
| **Metrics catalogue** with `unit` and `description`                                   | Downstream monitoring dashboards can rely on consistent spelling and units.                         |
| **Integrity hash**                                                                    | Pinned in the Layer-manifest so any silent rename or schema tweak breaks the build until reviewed.  |
| **Lifecycle & waivers**                                                               | Enables placeholders (`TBD`) in planning, blocks them later, and lets you time-box undecided enums. |

Copy this template, enumerate all event-types emitted by 1A…4B, and list every metric name referenced in your performance contracts or invariants. Pin the file’s SHA-256 in the Layer-manifest and your taxonomy is frozen for production.

######################################################################################################
######################################################################################################
######################################################################################################


## `LAYER1_MERCHANT_LOCATION_REALISM.MANIFEST.yaml`
```yaml
# layer1_merchant_location_realism.manifest.yaml
# ────────────────────────────────────────────────────────────────────────────────
#  PRODUCTION-GRADE LAYER MANIFEST  (the final “lock-down” file)
#
#  • One file per layer.  Immutable after release; bump `manifest_version`
#    for breaking changes.
#  • CI populates every *_sha256 field with the canonical digest of the
#    referenced file’s normalised JSON/YAML.
#  • Down-stream layers pin just **one** value: this manifest’s sha-256.
# ────────────────────────────────────────────────────────────────────────────────
manifest_version: "1.0"

layer:
  id: "layer1"
  name: "Merchant Location Realism"
  owner: "TBD team/email"
  doc_url: null
  lifecycle_phase: "planning"         # planning | alpha | beta | stable
  release_tag: null                   # set when phase ≥ beta (e.g., "v1.0.0")

ci_policy:
  # CI refuses to merge if any sha256 remains null when phase ≥ beta
  enforce_sha256: ["beta","stable"]

created_at: null                      # ISO-8601 (CI populates)
created_by: null                      # build user / CI job id
build_id: null                        # CI build identifier

# ────────────────────────────────────────────────────────────────────────────────
# 1 ▪ Sub-segment Interface Contracts (authoritative)
# ────────────────────────────────────────────────────────────────────────────────
subsegments:
  # id    contract file                      sha256 (CI fills)     contract_version
  - { id: "1A", contract: "interface_contract.1A.yaml", sha256: null, version: null }
  - { id: "1B", contract: "interface_contract.1B.yaml", sha256: null, version: null }
  - { id: "2A", contract: "interface_contract.2A.yaml", sha256: null, version: null }
  - { id: "2B", contract: "interface_contract.2B.yaml", sha256: null, version: null }
  - { id: "3A", contract: "interface_contract.3A.yaml", sha256: null, version: null }
  - { id: "3B", contract: "interface_contract.3B.yaml", sha256: null, version: null }
  - { id: "4A", contract: "interface_contract.4A.yaml", sha256: null, version: null }
  - { id: "4B", contract: "interface_contract.4B.yaml", sha256: null, version: null }

# ────────────────────────────────────────────────────────────────────────────────
# 2 ▪ Cross-stage Link-Contracts (auto-generated by CI; prove compatibility)
# ────────────────────────────────────────────────────────────────────────────────
link_contracts:
  - { boundary: "1A→1B", file: "link_contract.1A_to_1B.yaml", sha256: null }
  - { boundary: "1B→2A", file: "link_contract.1B_to_2A.yaml", sha256: null }
  - { boundary: "2A→2B", file: "link_contract.2A_to_2B.yaml", sha256: null }
  - { boundary: "2B→3A", file: "link_contract.2B_to_3A.yaml", sha256: null }
  - { boundary: "3A→3B", file: "link_contract.3A_to_3B.yaml", sha256: null }
  - { boundary: "3B→4A", file: "link_contract.3B_to_4A.yaml", sha256: null }
  - { boundary: "4A→4B", file: "link_contract.4A_to_4B.yaml", sha256: null }

# ────────────────────────────────────────────────────────────────────────────────
# 3 ▪ Layer-wide Governed Components (single source shared by all stages)
# ────────────────────────────────────────────────────────────────────────────────
components:
  dataset_dictionary:     { file: "dataset_dictionary.layer1.yaml",     sha256: null }
  error_catalogue:        { file: "error_catalogue.layer1.yaml",        sha256: null }
  id_namespace_registry:  { file: "id_namespace_registry.layer1.yaml",  sha256: null }
  prior_library:          { file: "prior_library.layer1.yaml",          sha256: null }
  taxonomy:               { file: "taxonomy.layer1.yaml",               sha256: null }

# ────────────────────────────────────────────────────────────────────────────────
# 4 ▪ Governing Artefacts (human-readable docs & maths, immutable once pinned)
# ────────────────────────────────────────────────────────────────────────────────
governing_artefacts:
  # filename                                 sha256 (CI fills)   owner_subsegment
  - { file: "narrative_1A_merchants_to_physical sites_sub-segment.txt", sha256: null, subsegment: "1A" }
  - { file: "assumptions_1A_merchants _to physical sites_sub-segment.txt", sha256: null, subsegment: "1A" }
  - { file: "mathematics_appendix_1A.txt", sha256: null, subsegment: "1A" }
  # … repeat for 1B … 4B
  - { file: "mathematics_appendix_4B.txt", sha256: null, subsegment: "4B" }

# ────────────────────────────────────────────────────────────────────────────────
# 5 ▪ Integrity Summary  (CI populates; diff detected → build fails)
# ────────────────────────────────────────────────────────────────────────────────
integrity:
  subsegment_count: 8
  link_contract_count: 7
  component_count: 5
  governing_artefact_count: null         # CI counts lines in `governing_artefacts`
  bundle_sha256: null                    # hash of concatenated, sorted JSON of every pinned file

# ────────────────────────────────────────────────────────────────────────────────
# 6 ▪ Change-Management Rules
# ────────────────────────────────────────────────────────────────────────────────
change_management:
  allowed_if:
    - "manifest_version bumped (semver) OR lifecycle.phase changed forward"
    - "all updated files have new sha256; CI link-contracts regenerated"
  requires:
    - "owner approval"
    - "architecture sign-off"
    - "updated release_tag when entering beta"

open_questions:
  - id: "link-contract-scope"
    note: "Do we emit 4A→4B link if 4B only reads validation bundle?"
    owner: "architecture"
    due_by: null

waivers:
  - id: "component-placeholder-digests"
    covers_components: ["prior_library","taxonomy"]
    reason: "Files drafted; content review pending"
    expires_on: "2025-10-15"
```

### Why this manifest *locks* Layer 1

| Section                   | Guarantee                                                                                |
| ------------------------- | ---------------------------------------------------------------------------------------- |
| **Sub-segment list**      | Every Interface Contract is pinned by digest; any change forces a new manifest.          |
| **Link-contracts**        | Cross-boundary compatibility proved *at build time*; downstream can rely on data shapes. |
| **Components**            | Dataset dictionary, error catalogue, taxonomy, etc., frozen as a single hash.            |
| **Governing artefacts**   | Narratives, assumptions, maths appendices immutable once released.                       |
| **Bundle hash**           | One top-level SHA-256 covers *every* file listed; downstream only needs this value.      |
| **Lifecycle / CI policy** | Placeholders allowed in planning, blocked from beta onward.                              |

Pin this manifest’s `bundle_sha256` in your global pipeline build manifest; from that point, Layer 1 is reproducibly specified for production, and any drift will fail CI.

######################################################################################################
######################################################################################################
######################################################################################################
