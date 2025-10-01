# SCHEMA AUTHORITY POLICY (Layer 1 · Merchant-Location Realism)

## Purpose

Eliminate schema drift and confusion. Define a **single source of truth** for all Layer 1 (1A–4B) datasets—starting now with **1A**—and specify how any other formats (e.g., Avro) relate to that source.

## Scope

* **Authoritative**: `schemas.ingress.layer1.yaml`, `schemas.1A.yaml`, and `schemas.layer1.yaml` (RNG events shared across subsegments).
* **Out of scope / non-authoritative** for 1A: any `.avsc` files (Avro). If Avro is ever needed, it must be **generated** from the JSON-Schema at release time and **not** referenced by 1A artefacts.

## Source of Truth

* The only authoritative schema definitions for 1A are:

  * Ingress (seed merchants): `schemas.ingress.layer1.yaml#/merchant_ids`
  * Model & allocation (1A): `schemas.1A.yaml`

    * `#/model/hurdle_design_matrix`
    * `#/model/hurdle_pi_probs`
    * `#/prep/sparse_flag`
    * `#/alloc/ranking_residual_cache`
    * `#/alloc/country_set`
    * `#/egress/outlet_catalogue`
  * Layer-wide RNG events: `schemas.layer1.yaml#/rng/events/*`
    (e.g., `#/rng/events/residual_rank`)

**All** dataset entries in the artefact registry and data dictionary **must** use `schema_ref:` pointers to these JSON-Schema paths (JSON Pointer fragments).

## Avro (AVSC) Policy

* 1A **must not** reference `.avsc` files in its artefact registry or data dictionary.
* Any existing AVSC artefacts under 1A should be **removed** from the registry and **not** treated as authoritative.
* If a downstream system requires Avro, generate it from JSON-Schema at build/release time and ship it as a **build artefact**, not as a source-controlled, referenced schema.

## Canonical Contracts (quick map)

* `merchant_ids` → `schemas.ingress.layer1.yaml#/merchant_ids`
* `hurdle_design_matrix` → `schemas.1A.yaml#/model/hurdle_design_matrix`
* `hurdle_pi_probs` → `schemas.1A.yaml#/model/hurdle_pi_probs`
* `sparse_flag` → `schemas.1A.yaml#/prep/sparse_flag`
* `ranking_residual_cache` → `schemas.1A.yaml#/alloc/ranking_residual_cache`
* `country_set` → `schemas.1A.yaml#/alloc/country_set`
* `outlet_catalogue` → `schemas.1A.yaml#/egress/outlet_catalogue`
* `rng_event_residual_rank` → `schemas.layer1.yaml#/rng/events/residual_rank`
* `s3_candidate_set` → `schemas.1A.yaml#/s3/candidate_set`
* `s3_base_weight_priors` → `schemas.1A.yaml#/s3/base_weight_priors`
* `s3_integerised_counts` → `schemas.1A.yaml#/s3/integerised_counts`
* `s3_site_sequence` → `schemas.1A.yaml#/s3/site_sequence`

> Note on upstream `transaction_schema.avsc`: it is a **cross-layer/external** contract and **not** consumed directly by 1A. 1A consumes the **normalised merchant snapshot** defined by `merchant_ids` above.

## Naming & Semantics (1A fixes baked into the policy)

* `residual_rank` = rank (1..m) of **largest-remainder residuals** used during integerisation (per merchant×country).
* `site_order` = deterministic **within-country** outlet sequence (1..nᵢ) used by `outlet_catalogue`.
* **Inter-country order is not encoded** in `outlet_catalogue`; consumers **must** use `s3_candidate_set.candidate_rank` (0 = home; contiguous foreign order from S3).

## Evolution Rules (planning phase)

* Allowed without breaking compatibility:

  * Add **nullable** columns, add/clarify **descriptions/notes**, widen numeric ranges where safe.
* Breaking changes (e.g., rename, type-narrowing, required-field addition) must be staged and documented in the design changelog before implementation.
* Any PR that changes a schema **must**:

  1. Update the **artefact registry** `schema:` references if needed (JSON-Schema only).
  2. Update the **data dictionary** `schema_ref:` and `ordering/keys` if impacted.
  3. Align **narrative** and **assumptions** wording (field names/semantics).
  4. Confirm egress ordering: `["merchant_id","legal_country_iso","site_order"]`.

## File Placement & Referencing

* Keep authoritative schemas under `/schemas/` as above.
* Do **not** commit `.avsc` under 1A; if generated for integration, place them under `/build/` or release artefacts, and do **not** reference them from the registry/dictionary.

## Migration Checklist (apply once, then enforce)

* Remove AVSC entries from `artefact_registry_1A.yaml`.
* Ensure every 1A dataset’s `schema:` / `schema_ref:` points to **JSON-Schema** (paths above).
* Confirm `residual_rank` and `site_order` names in all schema, dictionary, and prose.
* Append the egress note: *"Inter-country order is not encoded; use `s3_candidate_set.candidate_rank`."*

