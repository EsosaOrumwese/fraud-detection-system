# Data Dictionary - v0.1.0

Synthetic payment events emulating ISO-8583 card-present / CNP logs.

| Name | Type | Null? | Description |
|------|------|-------|-------------|
| `transaction_id` | string | False | Globally unique transaction identifier (UUIDv4). |
| `event_time` | datetime | False | RFC-3339 timestamp (UTC) when transaction occurred. |
| `local_time_offset` | int | False | Minutes between local merchant time and UTC (-720 … +840). |
| `amount` | float | False | Transaction amount in minor currency units (e.g. 12.30). |
| `currency_code` | string | False | ISO-4217 code (GBP, USD, EUR…). |
| `card_pan_hash` | string | False | SHA-256 hash of primary account number (PAN). |
| `card_scheme` | enum | False | Card network / scheme. |
| `card_exp_year` | int | False | Expiry year (YYYY). |
| `card_exp_month` | int | False | Expiry month (1-12). |
| `customer_id` | int | False | Synthetic foreign-key to customer table (future sprint). |
| `merchant_id` | int | False | Synthetic merchant identifier. |
| `merchant_country` | string | False | ISO-3166-alpha-2 country code of merchant. |
| `mcc_code` | int | True | 4-digit Merchant Category Code (ISO-8583 field 18). |
| `channel` | enum | False | High-level purchase channel. |
| `pos_entry_mode` | enum | False | Detailed POS entry mode. |
| `device_id` | string | True | Device or terminal identifier. |
| `device_type` | enum | True | Device operating system / terminal class. |
| `ip_address` | string | True | IPv4 address of customer (CNP only). Dotted quad. |
| `user_agent` | string | True | Browser or SDK User-Agent string (trimmed). |
| `latitude` | float | False | Approximate merchant lat, jittered ±0.5°. |
| `longitude` | float | False | Approximate merchant lon, jittered ±0.5°. |
| `is_recurring` | bool | False | True if part of subscription / standing order. |
| `previous_txn_id` | string | True | Immediate previous transaction for this card (nullable). |
| `label_fraud` | bool | False | Fraud ground-truth (1 = fraud, 0 = legit). |
