# Derivation Guide — `merchant_mcc_map` (Optional 2A ingress: merchant_id → mcc)

## 0) Purpose and role in the engine

`merchant_mcc_map` is a **programme-owned derived ingress dataset** used only for **2A MCC-scope timezone overrides**.

* If MCC-scope overrides are **enabled / present**, 2A.S0 must be able to **seal an authoritative merchant→MCC mapping** for the run.
* If MCC-scope overrides are **not used**, this dataset is not needed.

This mapping is derived **deterministically** from the canonical merchant universe snapshot `transaction_schema_merchant_ids`, which already contains `merchant_id` and `mcc`. 

---

## 1) Dataset identity (MUST)

* **ID:** `merchant_mcc_map`
* **Format:** Parquet
* **Path template:** `reference/layer1/merchant_mcc_map/{version}/`
* **Partitioning:** `[version]` (directory key)
* **PII:** `false`
* **License:** Proprietary-Internal (same posture as the merchant universe snapshot)

### Version rule (MUST; decision-free)

`{version}` MUST equal the `{version}` used for the pinned `transaction_schema_merchant_ids` snapshot that the scenario/manifest selects. 

If `transaction_schema_merchant_ids` is pinned to `2025-12-01`, then `merchant_mcc_map` MUST be published under `…/merchant_mcc_map/2025-12-01/`.

---

## 2) Schema (v1) (MUST)

Minimal 2-column schema:

* `merchant_id` (int64, NOT NULL) — **PK**
* `mcc` (int32, NOT NULL)

Hard constraints:

* `merchant_id` unique, min 1
* `mcc ∈ [0,9999]`

**Schema authority:** `schemas.ingress.layer1.yaml#/merchant_mcc_map`

---

## 3) Deterministic derivation (Codex implements; this doc specifies)

### 3.1 Input (MUST)

Read the already-normalised merchant universe snapshot:

* `transaction_schema_merchant_ids` at `reference/layer1/transaction_schema_merchant_ids/{version}/` 

### 3.2 Transform (MUST)

1. Select exactly these columns: `{merchant_id, mcc}`
2. Enforce types:

   * `merchant_id` → int64
   * `mcc` → int32
3. Sort rows **ascending by `merchant_id`** (writer determinism)
4. Write as Parquet to the output path.

No other columns, joins, or enrichment are permitted.

---

## 4) Engine-fit validation checklist (MUST pass before publishing)

Codex MUST validate:

### 4.1 Shape and domains

* Columns are exactly: `merchant_id, mcc`
* `merchant_id` NOT NULL; `merchant_id ≥ 1`
* `mcc` NOT NULL; `0 ≤ mcc ≤ 9999`
* No duplicates on `merchant_id`

### 4.2 Coverage equivalence vs upstream snapshot (MUST)

Let `U` be the set of merchants in `transaction_schema_merchant_ids` for `{version}`. 
Let `V` be the set of merchants in `merchant_mcc_map` for `{version}`.

Must hold:

* `U == V`
* Row count equals upstream merchant count

Any mismatch → **FAIL CLOSED**.

---

## 5) Provenance sidecar (MANDATORY)

Write a sidecar next to the parquet output (json/yaml is fine), e.g.:

`reference/layer1/merchant_mcc_map/{version}/merchant_mcc_map.provenance.json`

Must record at minimum:

* `dataset_id: "merchant_mcc_map"`
* `{version}`
* `derived_from`:

  * `transaction_schema_merchant_ids_version: "{version}"`
  * `transaction_schema_merchant_ids_path`
  * checksum/digest of the input parquet(s) or the directory manifest (your standard)
* `built_at_utc`
* output checksum(s) (sha256 of parquet bytes)

---

## 6) Consumption posture note (why this exists)

* This dataset should be treated as a **sealed optional input** for 2A.S0 when MCC-scope overrides are intended.
* If MCC-scope overrides are present/active but `merchant_mcc_map` is missing (or fails validation), the programme should **fail closed** rather than silently running without MCC override capability.
