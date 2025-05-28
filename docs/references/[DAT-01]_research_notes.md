# DAT-01 — Research Notes for Synthetic-Payments Schema  
_Version 0.1 • 17 May 2025_

> Purpose: Collect every standards snippet, dataset clue, and design thought that
> informed `config/transaction_schema.yaml`.  
> Anything that makes it into the schema **must** trace back to a bullet here.

---

## 1  Source Ledger

| ID   | Source                                       | What I read / copied                                         | File path                         |
|------|----------------------------------------------|--------------------------------------------------------------|-----------------------------------|
| S-01 | ISO-8583 field list (Wikipedia)              | Fields 7, 18, 22, 37; timestamp format `MMDDhhmmss`          | `/refs/iso8583_field_table.md`    |
| S-02 | Mastercard Merchant-Category-Code PDF (2024) | MCC is 4-digit int; industry ranges                          | `/refs/mastercard_mcc_2024.pdf`   |
| S-03 | Kaggle *PaySim* & *Credit-Card-Fraud-2019*   | Column names (`amount`, `step`, `nameOrig`, …)               | quick links                       |
| S-04 | Faker & Mimesis docs                         | Providers: `credit_card_full`, `country_code`, `device_type` | `/refs/faker_docs.md`             |
| S-05 | FIDO Device-Info JSON spec                   | Enum values for `device_os`, `device_model`                  | `/refs/fido_deviceinfo.json`      |
| S-06 | OpenStreetMap country-centroids CSV          | Lat/lon for ISO-3166 countries                               | `/refs/osm_country_centroids.csv` |
| S-07 | ISO-4217 currency list                       | Three-letter codes                                           | `/refs/iso4217_cheatsheet.md`     |
| S-08 | PCI-DSS quick-reference guide                | Full PAN is sensitive; hashed PAN OK                         | `/refs/pci_qrg.pdf`               |


---

## 2  Raw Nuggets (chronological dump)

* **ISO-8583 F7** → _“Transaction date-time (MMDDhhmmss)”_ → keep single UTC `event_time` + separate `local_time_offset`.
* **ISO-8583 F18** → _“Merchant Category Code (MCC)”_ → 4-digit `mcc_code` int.
* **ISO-8583 F22** → _“POS Entry Mode”_ → enum `pos_entry_mode` {CHIP, MAGSTRIPE, NFC, ECOM}.
* **Mastercard PDF p.2** → ranges 3000–3999 = Travel, etc. → later join table.
* **PaySim schema** → uses `amount`, `nameOrig`, `isFlaggedFraud` → adopt `amount`, boolean `label_fraud`; rename IDs to `customer_id`.
* **Credit-Card-Fraud-2019** → velocity idea “previous_txn_id”.
* **Faker** → `credit_card_full` returns PAN + name; we’ll hash PAN with SHA-256 → `card_pan_hash`.
* **FIDO spec** → device types {“iOS”, “Android”, “Web”, “POS”} → enum `device_type`.
* **OSM centroids** → store `latitude`, `longitude` jittered ±0.5°.
* **ISO-4217** → 3-letter `currency_code`; keep `amount` in minor units (float).
* **PCI-DSS** → do **not** store full PAN or CVV; OK to store hashed PAN.

---

## 3  Design-Decision Drafts (to be formalised in ADR-0005)

| Topic            | Decision                                     | Rationale                                 |
|------------------|----------------------------------------------|-------------------------------------------|
| Identifier style | `snake_case`                                 | Pythonic; Feast compatible                |
| Time handling    | `event_time` UTC + `local_time_offset` (min) | One canonical clock; retain local context |
| Currency         | ISO-4217 `currency_code`                     | Standard, human-readable                  |
| Geo precision    | jitter ±0.5° around country centroid         | City-level realism without PII            |
| Nullability      | 5-10 % nulls on `device_id`, `mcc_code`      | Mirrors real PSP data quality             |
| Versioning       | file header `version:` + Git tag             | Traceability over sprints                 |


---

## 4  Working Field Register (v0.1 draft)

| name                | dtype           | source(s)             | notes                     |
|---------------------|-----------------|-----------------------|---------------------------|
| `transaction_id`    | string (UUIDv4) | PaySim pattern        | primary key               |
| `event_time`        | datetime        | ISO-8583 F7           | RFC-3339 UTC              |
| `local_time_offset` | int             | design                | minutes −720 … +840       |
| `amount`            | float           | PaySim                | minor units               |
| `currency_code`     | string          | ISO-4217              | enum subset               |
| `card_pan_hash`     | string          | PCI-DSS               | SHA-256 hex               |
| `card_scheme`       | enum            | PaySim + schemes list | VISA/MC/AMEX/DISCOVER     |
| `card_exp_year`     | int             | card UX               | 4-digit                   |
| `card_exp_month`    | int             | card UX               | 1-12                      |
| `customer_id`       | int             | datasets              | FK later                  |
| `merchant_id`       | int             | datasets              | synthetic                 |
| `merchant_country`  | string          | ISO-3166              | alpha-2                   |
| `mcc_code`          | int             | ISO-8583 F18          | nullable 5 %              |
| `channel`           | enum            | design                | ONLINE / IN_STORE / ATM   |
| `pos_entry_mode`    | enum            | ISO-8583 F22          | CHIP / MAG / NFC / ECOM   |
| `device_id`         | string?         | Faker                 | nullable                  |
| `device_type`       | enum            | FIDO spec             | IOS / ANDROID / WEB / POS |
| `ip_address`        | string?         | Faker                 | IPv4                      |
| `user_agent`        | string?         | Faker UA              | trimmed                   |
| `latitude`          | float           | OSM                   | jittered                  |
| `longitude`         | float           | OSM                   | jittered                  |
| `is_recurring`      | bool            | PaySim                | sub-flag                  |
| `previous_txn_id`   | string?         | dataset idea          | velocity join             |
| `label_fraud`       | bool            | datasets              | target                    |


---

## 5  Open “Parking-Lot” Ideas

* `velocity_24h_txn_count`
* `device_score` (later from device-fingerprinting service)
* `bin_country` (from public BIN table)

---

## 6  Next Actions

1. Finalise ADR-0005 with the design decisions above.  
2. Draft `config/transaction_schema.yaml` exactly from the “Working Field Register”.  
3. Write unit test `test_schema_load.py` → assert 24 fields.  
4. Open PR `feat/schema-v0.1` and request review.

---

