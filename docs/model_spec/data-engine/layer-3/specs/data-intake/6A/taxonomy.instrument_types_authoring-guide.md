# Authoring Guide — `taxonomy.instrument_types` (6A.S3 instrument + scheme + token vocab, v1)

## 0) Purpose

`taxonomy.instrument_types` is the **sealed authority** for the **closed vocabulary** used by **6A.S3** when creating the world’s instrument universe (`s3_instrument_base_6A`) and its link table(s).

This single taxonomy pack MUST cover the codes that appear on instrument rows, including (at minimum):

* `instrument_type` (what kind of credential is this?)
* `scheme` / `network` (card network, bank rail, wallet network)
* `brand_tier` (basic/premium/business/corporate…)
* `token_type` (none / network token / device token…)
* `identifier_type` (PAN-like, IBAN-like, wallet-handle, alias-id…)

S3 explicitly requires that any `instrument_type`, `scheme`, `brand_tier`, `token_type`, and `identifier_type` emitted must exist in the corresponding taxonomy pack.

This artefact MUST be:

* **token-less** (no timestamps, no embedded digests)
* **deterministic / RNG-free**
* **fields-strict** (unknown keys invalid)
* **non-toy** (enough vocab depth for realistic downstream flows)

---

## 1) File identity (binding)

* **Manifest key (referenced by 6A.S3 dependencies):** `engine.layer3.6A.taxonomy.instrument_types` 
* **Role in `sealed_inputs_6A`:** `TAXONOMY` (ROW_LEVEL)
* **Path:** `config/layer3/6A/taxonomy/taxonomy.instrument_types.v1.yaml`
* **Format:** YAML (UTF-8, LF)
* **Digest posture:** token-less; do **not** embed digests. 6A.S0 seals exact bytes via `sha256_hex`.

**Dependencies:** authored after `taxonomy.party` and `taxonomy.account_types` because this taxonomy references:

* `party_type` values (`RETAIL`, `BUSINESS`, `OTHER`)
* account `ledger_class` concepts (DEPOSIT / CREDIT_* / SETTLEMENT) for eligibility constraints

---

## 2) Scope and non-goals

### In scope

* Enumerating instrument-related codes and **capability flags** used by S3 and later by 6B flow synthesis.
* Declaring **eligibility constraints** (which owner kinds and ledger classes can hold which instrument type).
* Declaring structural, stable properties (physical vs virtual, supports chargeback, tokenisable, etc.).

### Out of scope (MUST NOT appear here)

* Probabilities / shares / distributions (those belong to `prior.instrument_mix` and `prior.instrument_per_account`). 
* Any “fraud” semantics (S5 priors).
* Scenario-specific behaviour.

---

## 3) Strict YAML structure (MUST)

### 3.1 Top-level keys (exactly)

Required:

* `schema_version` *(int; MUST be `1`)*
* `taxonomy_id` *(string; MUST be `taxonomy.instrument_types.v1`)*
* `instrument_classes` *(list of strings)*
* `schemes` *(list of objects)*
* `brand_tiers` *(list of objects)*
* `token_types` *(list of objects)*
* `identifier_types` *(list of objects)*
* `instrument_types` *(list of objects)*

Optional:

* `tag_vocabulary` *(list of strings)*
* `notes` *(string)*

Unknown top-level keys: **INVALID**.

### 3.2 ID naming rules (MUST)

All ids (`schemes[].id`, `brand_tiers[].id`, `token_types[].id`, `identifier_types[].id`, `instrument_types[].id`, tags) MUST:

* be ASCII
* match: `^[A-Z][A-Z0-9_]{1,63}$`

### 3.3 Ordering & formatting (MUST)

* Lists MUST be sorted by `id` ascending:

  * `schemes`, `brand_tiers`, `token_types`, `identifier_types`, `instrument_types`, `tag_vocabulary`
* **No YAML anchors/aliases**
* 2-space indentation

---

## 4) Enumerations

### 4.1 `instrument_classes[]` (required)

MUST include at least:

* `CARD`
* `BANK_ACCOUNT`
* `WALLET`
* `TOKEN`

(You may add `OTHER`, but avoid it unless you really need it.)

### 4.2 `schemes[]` (required)

Each scheme object MUST contain:

* `id`
* `kind` *(enum: `CARD_NETWORK`, `BANK_RAIL`, `WALLET_NETWORK`)*
* `label`
* `description`

### 4.3 `brand_tiers[]` (required)

Each brand tier object MUST contain:

* `id`
* `label`
* `description`

Recommended tiers for realism:

* `BASIC`, `PREMIUM`, `BUSINESS`, `CORPORATE`

### 4.4 `token_types[]` (required)

Each token type object MUST contain:

* `id`
* `label`
* `description`
* `is_tokenised` *(bool)*

Minimum set (v1):

* `NONE` (is_tokenised=false)
* `NETWORK_TOKEN` (true)
* `DEVICE_TOKEN` (true)

### 4.5 `identifier_types[]` (required)

Each identifier type object MUST contain:

* `id`
* `label`
* `description`

Minimum set (v1):

* `PAN` (card-number style)
* `IBAN` (bank-account style)
* `WALLET_ID` (wallet handle)
* `ALIAS_ID` (generic alias / token id)

---

## 5) `instrument_types[]` schema (fields-strict)

Each instrument type object MUST contain:

* `id`
* `instrument_class` *(must be in `instrument_classes`)*
* `label`
* `description`
* `identifier_type` *(must be in `identifier_types`)*

And MUST contain these structural flags:

* `is_physical` *(bool)*
* `is_virtual` *(bool)*
* `supports_chargeback` *(bool)*
* `supports_tokenization` *(bool)*

Eligibility constraints (required):

* `allowed_owner_kinds` *(list; subset of `{PARTY, MERCHANT}`; non-empty)*
* `allowed_party_types` *(required if `PARTY` is allowed; subset of `{RETAIL,BUSINESS,OTHER}`)*
* `allowed_ledger_classes` *(list; subset of `{DEPOSIT, CREDIT_REVOLVING, CREDIT_INSTALLMENT, SETTLEMENT}`; non-empty)*

Scheme rules:

* `allowed_scheme_kinds` *(list; subset of `{CARD_NETWORK,BANK_RAIL,WALLET_NETWORK}`; non-empty)*
* `default_scheme_kind` *(one of allowed kinds)*

Optional (recommended for 6B realism):

* `capability_tags` *(list; each tag must be in `tag_vocabulary`)*
* `allowed_token_types` *(list of `token_types[].id`; required if `supports_tokenization:true`; MUST include `NONE` if you allow “not tokenised” variants)*
* `notes` *(string)*

Rules:

* `is_physical` and `is_virtual` MUST NOT both be false.
* Card-like instrument types SHOULD set `allowed_scheme_kinds` to include `CARD_NETWORK`.
* Bank-account handles SHOULD set scheme kind to `BANK_RAIL`.
* Wallet handles SHOULD set scheme kind to `WALLET_NETWORK`.

---

## 6) Realism requirements (NON-TOY)

Minimum floors (MUST):

* `len(instrument_types) >= 14`
* `len(schemes) >= 8` with kind coverage:

  * ≥ 3 `CARD_NETWORK`
  * ≥ 3 `BANK_RAIL`
  * ≥ 1 `WALLET_NETWORK`
* `len(brand_tiers) >= 4`
* `len(token_types) >= 3`
* `len(identifier_types) >= 4`
* Coverage across classes:

  * ≥ 6 CARD instrument types
  * ≥ 3 BANK_ACCOUNT instrument types
  * ≥ 2 WALLET instrument types

Recommended (SHOULD):

* Include both physical and virtual card types (retail + business).
* Include at least one prepaid instrument type.
* Include both domestic and international bank rails.
* Include at least one wallet-network type that supports device tokenisation.

---

## 7) Authoring procedure (Codex-ready)

1. Define `instrument_classes`.
2. Define `identifier_types`.
3. Define `token_types`.
4. Define `schemes` (card networks + bank rails + wallet networks).
5. Define `brand_tiers`.
6. Define `tag_vocabulary` (optional but recommended), e.g.:

   * `CONTACTLESS`, `ATM_CAPABLE`, `ECOM_CAPABLE`, `MOTO_CAPABLE`, `IN_APP`, `TOKENIZABLE`, `RECURRING_CAPABLE`, `HIGH_LIMIT_ELIGIBLE`
7. Define `instrument_types` ensuring:

   * eligibility constraints are consistent (owner kind + party types + ledger classes)
   * scheme kinds make sense
   * tokenisation fields are consistent
8. Run acceptance checks (§9).
9. Freeze formatting (sorted lists, no anchors, token-less).

---

## 8) Minimal v1 example (realistic)

```yaml
schema_version: 1
taxonomy_id: taxonomy.instrument_types.v1
notes: >
  Instrument + scheme + token vocab for 6A.S3. Ids are stable API tokens.

instrument_classes: [BANK_ACCOUNT, CARD, TOKEN, WALLET]

tag_vocabulary:
  - ATM_CAPABLE
  - CONTACTLESS
  - ECOM_CAPABLE
  - HIGH_LIMIT_ELIGIBLE
  - IN_APP
  - MOTO_CAPABLE
  - RECURRING_CAPABLE
  - TOKENIZABLE

schemes:
  - id: ACH
    kind: BANK_RAIL
    label: ACH
    description: Batch bank transfer rail (US-style).
  - id: FPS
    kind: BANK_RAIL
    label: Faster Payments
    description: Near-real-time domestic bank transfer rail (UK-style).
  - id: SEPA_CREDIT
    kind: BANK_RAIL
    label: SEPA Credit Transfer
    description: Domestic/regional bank transfer rail (EU-style).
  - id: SWIFT
    kind: BANK_RAIL
    label: SWIFT
    description: International bank transfer messaging/rail.
  - id: VISA
    kind: CARD_NETWORK
    label: Visa
    description: Global card network.
  - id: MASTERCARD
    kind: CARD_NETWORK
    label: Mastercard
    description: Global card network.
  - id: AMEX
    kind: CARD_NETWORK
    label: American Express
    description: Card network with distinct acceptance patterns.
  - id: APPLE_PAY
    kind: WALLET_NETWORK
    label: Apple Pay
    description: Wallet network using device tokenisation.
  - id: GOOGLE_PAY
    kind: WALLET_NETWORK
    label: Google Pay
    description: Wallet network using device tokenisation.

brand_tiers:
  - id: BASIC
    label: Basic
    description: Entry tier with standard eligibility.
  - id: PREMIUM
    label: Premium
    description: Higher tier with enhanced benefits and eligibility.
  - id: BUSINESS
    label: Business
    description: Business-oriented tier.
  - id: CORPORATE
    label: Corporate
    description: Corporate tier with higher limits and controls.

token_types:
  - id: DEVICE_TOKEN
    is_tokenised: true
    label: Device token
    description: Token bound to a device wallet/container.
  - id: NETWORK_TOKEN
    is_tokenised: true
    label: Network token
    description: Token issued via card network tokenisation.
  - id: NONE
    is_tokenised: false
    label: Not tokenised
    description: Underlying identifier is used directly.

identifier_types:
  - id: ALIAS_ID
    label: Alias id
    description: Generic alias/token identifier (non-PII; synthetic).
  - id: IBAN
    label: IBAN-like
    description: Bank-account style identifier (synthetic format).
  - id: PAN
    label: PAN-like
    description: Card-number style identifier (masked/synthetic).
  - id: WALLET_ID
    label: Wallet id
    description: Wallet handle identifier.

instrument_types:
  # CARD — retail
  - id: RETAIL_DEBIT_CARD_PHYSICAL
    instrument_class: CARD
    label: Retail debit card (physical)
    description: Physical debit card linked to a deposit account.
    identifier_type: PAN
    is_physical: true
    is_virtual: false
    supports_chargeback: true
    supports_tokenization: true
    allowed_token_types: [NONE, DEVICE_TOKEN, NETWORK_TOKEN]
    allowed_owner_kinds: [PARTY]
    allowed_party_types: [RETAIL]
    allowed_ledger_classes: [DEPOSIT]
    allowed_scheme_kinds: [CARD_NETWORK]
    default_scheme_kind: CARD_NETWORK
    capability_tags: [CONTACTLESS, ATM_CAPABLE, ECOM_CAPABLE, TOKENIZABLE, RECURRING_CAPABLE]

  - id: RETAIL_DEBIT_CARD_VIRTUAL
    instrument_class: CARD
    label: Retail debit card (virtual)
    description: Virtual debit credential for online/in-app use.
    identifier_type: PAN
    is_physical: false
    is_virtual: true
    supports_chargeback: true
    supports_tokenization: true
    allowed_token_types: [NONE, DEVICE_TOKEN, NETWORK_TOKEN]
    allowed_owner_kinds: [PARTY]
    allowed_party_types: [RETAIL]
    allowed_ledger_classes: [DEPOSIT]
    allowed_scheme_kinds: [CARD_NETWORK]
    default_scheme_kind: CARD_NETWORK
    capability_tags: [ECOM_CAPABLE, IN_APP, TOKENIZABLE, RECURRING_CAPABLE]

  - id: RETAIL_CREDIT_CARD_PHYSICAL
    instrument_class: CARD
    label: Retail credit card (physical)
    description: Physical revolving credit card credential.
    identifier_type: PAN
    is_physical: true
    is_virtual: false
    supports_chargeback: true
    supports_tokenization: true
    allowed_token_types: [NONE, DEVICE_TOKEN, NETWORK_TOKEN]
    allowed_owner_kinds: [PARTY]
    allowed_party_types: [RETAIL]
    allowed_ledger_classes: [CREDIT_REVOLVING]
    allowed_scheme_kinds: [CARD_NETWORK]
    default_scheme_kind: CARD_NETWORK
    capability_tags: [CONTACTLESS, ECOM_CAPABLE, HIGH_LIMIT_ELIGIBLE, TOKENIZABLE, RECURRING_CAPABLE]

  - id: RETAIL_CREDIT_CARD_VIRTUAL
    instrument_class: CARD
    label: Retail credit card (virtual)
    description: Virtual revolving credit credential for online/in-app use.
    identifier_type: PAN
    is_physical: false
    is_virtual: true
    supports_chargeback: true
    supports_tokenization: true
    allowed_token_types: [NONE, DEVICE_TOKEN, NETWORK_TOKEN]
    allowed_owner_kinds: [PARTY]
    allowed_party_types: [RETAIL]
    allowed_ledger_classes: [CREDIT_REVOLVING]
    allowed_scheme_kinds: [CARD_NETWORK]
    default_scheme_kind: CARD_NETWORK
    capability_tags: [ECOM_CAPABLE, IN_APP, TOKENIZABLE, RECURRING_CAPABLE]

  - id: RETAIL_PREPAID_CARD_PHYSICAL
    instrument_class: CARD
    label: Retail prepaid card (physical)
    description: Physical prepaid credential linked to a deposit-like balance.
    identifier_type: PAN
    is_physical: true
    is_virtual: false
    supports_chargeback: true
    supports_tokenization: true
    allowed_token_types: [NONE, DEVICE_TOKEN, NETWORK_TOKEN]
    allowed_owner_kinds: [PARTY]
    allowed_party_types: [RETAIL]
    allowed_ledger_classes: [DEPOSIT]
    allowed_scheme_kinds: [CARD_NETWORK]
    default_scheme_kind: CARD_NETWORK
    capability_tags: [CONTACTLESS, ECOM_CAPABLE, TOKENIZABLE]

  # CARD — business
  - id: BUSINESS_DEBIT_CARD_PHYSICAL
    instrument_class: CARD
    label: Business debit card (physical)
    description: Physical debit credential for business deposit accounts.
    identifier_type: PAN
    is_physical: true
    is_virtual: false
    supports_chargeback: true
    supports_tokenization: true
    allowed_token_types: [NONE, DEVICE_TOKEN, NETWORK_TOKEN]
    allowed_owner_kinds: [PARTY]
    allowed_party_types: [BUSINESS]
    allowed_ledger_classes: [DEPOSIT]
    allowed_scheme_kinds: [CARD_NETWORK]
    default_scheme_kind: CARD_NETWORK
    capability_tags: [CONTACTLESS, ATM_CAPABLE, ECOM_CAPABLE, TOKENIZABLE, RECURRING_CAPABLE]

  - id: BUSINESS_CREDIT_CARD_PHYSICAL
    instrument_class: CARD
    label: Business credit card (physical)
    description: Physical revolving credit credential for business spend.
    identifier_type: PAN
    is_physical: true
    is_virtual: false
    supports_chargeback: true
    supports_tokenization: true
    allowed_token_types: [NONE, DEVICE_TOKEN, NETWORK_TOKEN]
    allowed_owner_kinds: [PARTY]
    allowed_party_types: [BUSINESS]
    allowed_ledger_classes: [CREDIT_REVOLVING]
    allowed_scheme_kinds: [CARD_NETWORK]
    default_scheme_kind: CARD_NETWORK
    capability_tags: [CONTACTLESS, ECOM_CAPABLE, HIGH_LIMIT_ELIGIBLE, TOKENIZABLE, RECURRING_CAPABLE]

  # BANK_ACCOUNT — party handles (IBAN-like)
  - id: PARTY_BANK_ACCOUNT_DOMESTIC
    instrument_class: BANK_ACCOUNT
    label: Party bank account (domestic rail)
    description: Bank-account handle used for domestic transfers.
    identifier_type: IBAN
    is_physical: false
    is_virtual: true
    supports_chargeback: false
    supports_tokenization: false
    allowed_owner_kinds: [PARTY]
    allowed_party_types: [RETAIL, BUSINESS, OTHER]
    allowed_ledger_classes: [DEPOSIT, SETTLEMENT]
    allowed_scheme_kinds: [BANK_RAIL]
    default_scheme_kind: BANK_RAIL
    capability_tags: [RECURRING_CAPABLE]

  - id: PARTY_BANK_ACCOUNT_INTERNATIONAL
    instrument_class: BANK_ACCOUNT
    label: Party bank account (international rail)
    description: Bank-account handle used for international transfers.
    identifier_type: IBAN
    is_physical: false
    is_virtual: true
    supports_chargeback: false
    supports_tokenization: false
    allowed_owner_kinds: [PARTY]
    allowed_party_types: [RETAIL, BUSINESS, OTHER]
    allowed_ledger_classes: [DEPOSIT, SETTLEMENT]
    allowed_scheme_kinds: [BANK_RAIL]
    default_scheme_kind: BANK_RAIL

  # WALLET — tokenised handles
  - id: WALLET_DEVICE_TOKEN
    instrument_class: WALLET
    label: Device wallet token
    description: Wallet-based credential using device tokenisation.
    identifier_type: WALLET_ID
    is_physical: false
    is_virtual: true
    supports_chargeback: true
    supports_tokenization: true
    allowed_token_types: [DEVICE_TOKEN, NETWORK_TOKEN]
    allowed_owner_kinds: [PARTY]
    allowed_party_types: [RETAIL, BUSINESS]
    allowed_ledger_classes: [DEPOSIT, CREDIT_REVOLVING]
    allowed_scheme_kinds: [WALLET_NETWORK]
    default_scheme_kind: WALLET_NETWORK
    capability_tags: [IN_APP, ECOM_CAPABLE, TOKENIZABLE, RECURRING_CAPABLE]

  # MERCHANT — payout/settlement handle
  - id: MERCHANT_PAYOUT_BANK_ACCOUNT
    instrument_class: BANK_ACCOUNT
    label: Merchant payout bank account
    description: Merchant-owned settlement/payout bank-account handle.
    identifier_type: IBAN
    is_physical: false
    is_virtual: true
    supports_chargeback: false
    supports_tokenization: false
    allowed_owner_kinds: [MERCHANT]
    allowed_ledger_classes: [SETTLEMENT]
    allowed_scheme_kinds: [BANK_RAIL]
    default_scheme_kind: BANK_RAIL
```

---

## 9) Acceptance checklist (MUST)

### 9.1 Structural

* YAML parses cleanly.
* `schema_version == 1`
* `taxonomy_id == taxonomy.instrument_types.v1`
* Unknown keys absent (top-level and nested).
* All ids match `^[A-Z][A-Z0-9_]{1,63}$`.
* Uniqueness:

  * all ids unique within each list (`schemes`, `brand_tiers`, `token_types`, `identifier_types`, `instrument_types`)

### 9.2 Referential integrity

* Every `instrument_types[].instrument_class` ∈ `instrument_classes`
* Every `instrument_types[].identifier_type` exists in `identifier_types`
* `allowed_owner_kinds` non-empty; subset of `{PARTY, MERCHANT}`
* If `PARTY` allowed → `allowed_party_types` exists and non-empty
* `allowed_ledger_classes` non-empty; subset of `{DEPOSIT, CREDIT_REVOLVING, CREDIT_INSTALLMENT, SETTLEMENT}`
* `allowed_scheme_kinds` non-empty; subset of `{CARD_NETWORK, BANK_RAIL, WALLET_NETWORK}`
* `default_scheme_kind` ∈ `allowed_scheme_kinds`
* If `supports_tokenization:true` → `allowed_token_types` exists and every entry exists in `token_types`
* If `capability_tags` present → tags ⊆ `tag_vocabulary`

### 9.3 Realism floors

* instrument_types ≥ 14
* schemes ≥ 8 with required kind coverage
* brand_tiers ≥ 4
* token_types ≥ 3
* identifier_types ≥ 4
* class coverage floors satisfied (CARD/BANK_ACCOUNT/WALLET)

### 9.4 Stability / digest posture

* No timestamps/UUIDs/in-file digests.
* Lists sorted by id ascending.
* No YAML anchors/aliases.

---

## 10) Change control (MUST)

* All ids in this taxonomy are **stable API tokens**.
* Never repurpose an existing id for a new meaning.
* Breaking changes (removals/renames or semantic repurposing) require:

  * bumping filename version (`taxonomy.instrument_types.v2.yaml`)
  * updating any 6A priors that reference these ids
  * updating 6B logic/configs if they treat specific instrument types specially
