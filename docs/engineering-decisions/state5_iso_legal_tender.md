# State 5 – `iso_legal_tender_2024`

## Context
- Spec reference: `docs/model_spec/data-engine/specs/data-intake/1A/dataset-preview.md` (Dataset 14).
- Purpose: Provide canonical ISO2 → primary legal tender mapping for the optional `merchant_currency` cache in S5.0.

## Ingestion (2025-10-26 refresh)
- Source parity: derived deterministically from `reference/network/ccy_country_shares/2025-10-26/ccy_country_shares.parquet` by selecting the highest-share currency per `country_iso`.
- Output written to `reference/iso/iso_legal_tender/2024/iso_legal_tender.parquet` (271 rows covering 155 currency tokens, including dual-tender strings such as `LSL,ZAR`).
- Manifest/QA files record row count plus basic validation (PK uniqueness; uppercase ISO/CCY).
- Schema anchor added at `contracts/schemas/l1/seg_1A/iso_legal_tender.schema.json` and wired into the dataset dictionary (`contracts/dataset_dictionary/l1/seg_1A/layer1.1A.yaml`).

## Assumptions / gaps
- Coverage now mirrors the canonical ISO->legal tender parquet; future S5 runs inherit new currencies automatically when the share surfaces are regenerated.
- Currency choice uses maximum share tie-broken lexicographically to keep the mapping deterministic until production legal tender data is sourced.

## Follow-ups
- When authoritative legal tender data becomes available, regenerate the dataset and update `semver` plus associated QA.
- Extend the mapping if new ISO codes enter the merchant universe or share surfaces.
