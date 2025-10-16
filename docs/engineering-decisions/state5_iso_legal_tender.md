# State 5 – `iso_legal_tender_2024`

## Context
- Spec reference: `docs/model_spec/data-engine/specs/data-intake/1A/dataset-preview.md` (Dataset 14).
- Purpose: Provide canonical ISO2 → primary legal tender mapping for the optional `merchant_currency` cache in S5.0.

## Ingestion (2025-10-16)
- Source parity: derived deterministically from `reference/network/ccy_country_shares/2025-10-08/ccy_country_shares.parquet` by selecting the highest-share currency per `country_iso`.
- Output written to `reference/iso/iso_legal_tender/2024/iso_legal_tender.parquet` (80 rows).
- Manifest/QA files record row count plus basic validation (PK uniqueness; uppercase ISO/CCY).
- Schema anchor added at `contracts/schemas/l1/seg_1A/iso_legal_tender.schema.json` and wired into the dataset dictionary (`contracts/dataset_dictionary/l1/seg_1A/layer1.1A.yaml`).

## Assumptions / gaps
- Coverage limited to countries present in `ccy_country_shares_2024Q4` (S5 inputs). Merchants outside this set will inherit the same mapping once shares expand; revisit when additional countries appear upstream.
- Currency choice uses maximum share tie-broken lexicographically to keep the mapping deterministic until production legal tender data is sourced.

## Follow-ups
- When authoritative legal tender data becomes available, regenerate the dataset and update `semver` plus associated QA.
- Extend the mapping if new ISO codes enter the merchant universe or share surfaces.
