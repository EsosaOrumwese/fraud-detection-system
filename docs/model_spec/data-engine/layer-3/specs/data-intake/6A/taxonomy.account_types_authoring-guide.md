# Authoring Guide — `taxonomy.account_types` (6A.S2 account/product enumerations, v1)

## 0) Purpose

`taxonomy.account_types` is the **sealed authority** for the closed vocabulary that 6A uses to populate:

* `account_type` (appears in dataset ordering for both `s2_account_base_6A` and `s2_merchant_account_base_6A`) 
* `product_family` / `product_tier` style fields referenced by 6A.S2 (“account & product taxonomies”) 

This taxonomy exists so Codex can author **realistic, non-toy** product/account codes without smuggling distributions into the taxonomy. **Distributions live in priors** (`prior.product_mix`, `prior.account_per_party`); the taxonomy only defines *what can exist*. 

This artefact MUST be:

* **token-less** (no timestamps, no embedded digests)
* **deterministic / RNG-free**
* **fields-strict** (unknown keys invalid)
* **non-toy** (enough types to support realistic heterogeneity across retail/business/merchant)

---

## 1) File identity (binding)

* **Artefact name:** `taxonomy.account_types`
* **Intended role in `sealed_inputs_6A`:** `TAXONOMY` (ROW_LEVEL) 
* **Path:** `config/layer3/6A/taxonomy/taxonomy.account_types.v1.yaml`
* **Format:** YAML (UTF-8, LF)
* **Schema anchor:** `schemas.6A.yaml#/taxonomy/account_taxonomy_6A`
* **Digest posture:** token-less; do **not** embed any digest fields. 6A.S0 seals by exact bytes.

**Dependency:** authored after `taxonomy.party`, because this file references `party_type` codes (`RETAIL`, `BUSINESS`, `OTHER`).

---

## 2) Scope and non-goals

### In scope

* Enumerating **account types** and **product families/tiers**.
* Declaring **eligibility constraints** (what owner kinds can hold which type; which party_types).
* Declaring **structural attributes** that are stable (deposit vs credit, requires instrument, currency policy).

### Out of scope (MUST NOT appear here)

* Shares, probabilities, or counts (that’s priors).
* Fraud semantics.
* Scenario/time behaviour.

---

## 3) Strict YAML structure (MUST)

### 3.1 Top-level keys (exactly)

Required:

* `schema_version` *(int; MUST be `1`)*
* `taxonomy_id` *(string; MUST be `taxonomy.account_types.v1`)*
* `owner_kinds` *(list of strings; MUST include `PARTY` and `MERCHANT`)*
* `ledger_classes` *(list of strings; see §3.3)*
* `currency_policies` *(list of objects)*
* `product_families` *(list of objects)*
* `account_types` *(list of objects)*

Optional:

* `notes` *(string)*

Unknown top-level keys: **INVALID**.

### 3.2 ID naming rules (MUST)

All ids (`currency_policies[].id`, `product_families[].id`, `account_types[].id`) MUST:

* be ASCII
* match: `^[A-Z][A-Z0-9_]{1,63}$`

### 3.3 Enumerations (MUST)

`ledger_classes` MUST contain at least these values (you may add more):

* `DEPOSIT`
* `CREDIT_REVOLVING`
* `CREDIT_INSTALLMENT`
* `SETTLEMENT`

---

## 4) Object schemas (fields-strict)

### 4.1 `currency_policies[]` (required)

Each object MUST contain:

* `id`
* `label`
* `description`
* `is_multi_currency` *(bool)*

Optional:

* `default_currency_source` *(enum string; e.g., `HOME_CCY`, `LEGAL_TENDER`, `MERCHANT_CCY`)*

Rules:

* if `is_multi_currency: true`, description MUST specify the intended behaviour (e.g., “supports balances in multiple currencies”).

### 4.2 `product_families[]` (required)

Each object MUST contain:

* `id`
* `label`
* `description`

Optional:

* `tier` *(enum string; e.g., `BASIC`, `PREMIUM`, `BUSINESS`, `MERCHANT`)*

### 4.3 `account_types[]` (required)

Each object MUST contain:

* `id`
* `label`
* `description`
* `owner_kind` *(enum: `PARTY` or `MERCHANT`)*
* `ledger_class` *(must be in `ledger_classes`)*
* `product_family_id` *(must match a `product_families[].id`)*
* `currency_policy_id` *(must match a `currency_policies[].id`)*
* `requires_instrument` *(bool)*

Conditional required:

* if `owner_kind: PARTY` → `allowed_party_types` MUST be present *(list; subset of `{RETAIL,BUSINESS,OTHER}`)*

Optional (recommended for downstream realism/constraints):

* `supports_chargeback` *(bool; default false)*
* `can_be_joint` *(bool; default false; PARTY only)*
* `notes` *(string)*

Rules:

* Merchant-owned account types MUST NOT declare `allowed_party_types`.
* `requires_instrument: true` SHOULD only be used for account types that will be associated with instruments in S3 (e.g., cards).

---

## 5) Realism requirements (NON-TOY)

Minimum floors (MUST):

* total `account_types` **≥ 12**
* PARTY account types **≥ 8**
* MERCHANT account types **≥ 2**
* `product_families` **≥ 6**
* `currency_policies` **≥ 2**
* coverage of ledger classes:

  * at least one `DEPOSIT`
  * at least one `CREDIT_REVOLVING`
  * at least one `CREDIT_INSTALLMENT`
  * at least one `SETTLEMENT`

Recommended realism (SHOULD):

* include both **basic** and **premium** variants (to let priors create realistic stratification)
* include at least one business credit product distinct from retail
* include at least one merchant “reserve/holdback” style account (common in payments ecosystems)

---

## 6) Authoring procedure (Codex-ready)

1. Define `owner_kinds = [MERCHANT, PARTY]` (sorted).
2. Define `ledger_classes` (include required set).
3. Define 2–3 `currency_policies` (single-currency + multi-currency).
4. Define 6–10 `product_families` (basic/premium, deposit/credit, merchant settlement/reserve).
5. Define `account_types`:

   * at least 8 PARTY types spanning deposit + revolving + installment
   * at least 2 MERCHANT types spanning settlement + reserve
   * set `requires_instrument` consistently (e.g., cards true; deposits/loans false)
6. Run acceptance checks (§9).
7. Freeze formatting:

   * lists sorted by `id`
   * no YAML anchors/aliases
   * token-less posture

---

## 7) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
taxonomy_id: taxonomy.account_types.v1
notes: >
  Account/product taxonomy for 6A.S2. Stable ids are treated as API tokens.

owner_kinds: [MERCHANT, PARTY]

ledger_classes:
  - CREDIT_INSTALLMENT
  - CREDIT_REVOLVING
  - DEPOSIT
  - SETTLEMENT

currency_policies:
  - id: MULTI_CURRENCY
    label: Multi-currency
    description: Supports balances and transactions in multiple currencies.
    is_multi_currency: true
    default_currency_source: HOME_CCY
  - id: SINGLE_HOME_CCY
    label: Single currency (home)
    description: Single-currency account using the owner’s home/legal currency.
    is_multi_currency: false
    default_currency_source: HOME_CCY

product_families:
  - id: BUSINESS_CREDIT
    tier: BUSINESS
    label: Business credit
    description: Credit products tailored to business customers.
  - id: BUSINESS_DEPOSIT
    tier: BUSINESS
    label: Business deposit
    description: Deposit accounts for business cash management.
  - id: MERCHANT_SETTLEMENT
    tier: MERCHANT
    label: Merchant settlement
    description: Settlement accounts used to receive funds from payment processing.
  - id: MERCHANT_TREASURY
    tier: MERCHANT
    label: Merchant reserve / treasury
    description: Reserve/holdback or treasury accounts used for risk buffers and payouts.
  - id: RETAIL_CREDIT
    tier: PREMIUM
    label: Retail credit
    description: Retail revolving and installment credit products.
  - id: RETAIL_DEPOSIT
    tier: BASIC
    label: Retail deposit
    description: Retail current and savings accounts.

account_types:
  # PARTY — retail deposit
  - id: RETAIL_CURRENT_BASIC
    owner_kind: PARTY
    allowed_party_types: [RETAIL]
    ledger_class: DEPOSIT
    product_family_id: RETAIL_DEPOSIT
    currency_policy_id: SINGLE_HOME_CCY
    requires_instrument: false
    label: Retail current (basic)
    description: Basic retail current account for everyday payments and transfers.
    supports_chargeback: false
    can_be_joint: true

  - id: RETAIL_CURRENT_PREMIUM
    owner_kind: PARTY
    allowed_party_types: [RETAIL]
    ledger_class: DEPOSIT
    product_family_id: RETAIL_DEPOSIT
    currency_policy_id: SINGLE_HOME_CCY
    requires_instrument: false
    label: Retail current (premium)
    description: Premium retail current account with higher service tier and eligibility.
    supports_chargeback: false
    can_be_joint: true

  - id: RETAIL_SAVINGS_INSTANT
    owner_kind: PARTY
    allowed_party_types: [RETAIL]
    ledger_class: DEPOSIT
    product_family_id: RETAIL_DEPOSIT
    currency_policy_id: SINGLE_HOME_CCY
    requires_instrument: false
    label: Retail savings (instant access)
    description: Instant-access savings account for short-term saving and transfers.
    supports_chargeback: false
    can_be_joint: true

  - id: RETAIL_SAVINGS_FIXED
    owner_kind: PARTY
    allowed_party_types: [RETAIL]
    ledger_class: DEPOSIT
    product_family_id: RETAIL_DEPOSIT
    currency_policy_id: SINGLE_HOME_CCY
    requires_instrument: false
    label: Retail savings (fixed term)
    description: Fixed-term savings account with restricted withdrawals.
    supports_chargeback: false
    can_be_joint: false

  # PARTY — retail credit (cards/loans)
  - id: RETAIL_CREDIT_CARD_STANDARD
    owner_kind: PARTY
    allowed_party_types: [RETAIL]
    ledger_class: CREDIT_REVOLVING
    product_family_id: RETAIL_CREDIT
    currency_policy_id: MULTI_CURRENCY
    requires_instrument: true
    label: Retail credit card (standard)
    description: Standard retail revolving credit card product.
    supports_chargeback: true
    can_be_joint: false

  - id: RETAIL_CREDIT_CARD_PREMIUM
    owner_kind: PARTY
    allowed_party_types: [RETAIL]
    ledger_class: CREDIT_REVOLVING
    product_family_id: RETAIL_CREDIT
    currency_policy_id: MULTI_CURRENCY
    requires_instrument: true
    label: Retail credit card (premium)
    description: Premium retail revolving credit card product.
    supports_chargeback: true
    can_be_joint: false

  - id: RETAIL_PERSONAL_LOAN_UNSECURED
    owner_kind: PARTY
    allowed_party_types: [RETAIL]
    ledger_class: CREDIT_INSTALLMENT
    product_family_id: RETAIL_CREDIT
    currency_policy_id: SINGLE_HOME_CCY
    requires_instrument: false
    label: Retail personal loan (unsecured)
    description: Unsecured installment credit for retail customers.
    supports_chargeback: false
    can_be_joint: false

  # PARTY — business deposit/credit
  - id: BUSINESS_CURRENT
    owner_kind: PARTY
    allowed_party_types: [BUSINESS]
    ledger_class: DEPOSIT
    product_family_id: BUSINESS_DEPOSIT
    currency_policy_id: SINGLE_HOME_CCY
    requires_instrument: false
    label: Business current
    description: Business current account for operating cashflows and payments.
    supports_chargeback: false
    can_be_joint: false

  - id: BUSINESS_SAVINGS
    owner_kind: PARTY
    allowed_party_types: [BUSINESS]
    ledger_class: DEPOSIT
    product_family_id: BUSINESS_DEPOSIT
    currency_policy_id: SINGLE_HOME_CCY
    requires_instrument: false
    label: Business savings
    description: Business savings/treasury deposit account.
    supports_chargeback: false
    can_be_joint: false

  - id: BUSINESS_CREDIT_CARD
    owner_kind: PARTY
    allowed_party_types: [BUSINESS]
    ledger_class: CREDIT_REVOLVING
    product_family_id: BUSINESS_CREDIT
    currency_policy_id: MULTI_CURRENCY
    requires_instrument: true
    label: Business credit card
    description: Revolving credit card product for business spend.
    supports_chargeback: true
    can_be_joint: false

  - id: BUSINESS_TERM_LOAN
    owner_kind: PARTY
    allowed_party_types: [BUSINESS]
    ledger_class: CREDIT_INSTALLMENT
    product_family_id: BUSINESS_CREDIT
    currency_policy_id: SINGLE_HOME_CCY
    requires_instrument: false
    label: Business term loan
    description: Installment credit for business investment and working capital.
    supports_chargeback: false
    can_be_joint: false

  # MERCHANT — settlement / reserve
  - id: MERCHANT_SETTLEMENT_ACCOUNT
    owner_kind: MERCHANT
    ledger_class: SETTLEMENT
    product_family_id: MERCHANT_SETTLEMENT
    currency_policy_id: SINGLE_HOME_CCY
    requires_instrument: false
    label: Merchant settlement account
    description: Account used to receive settlement flows from payment processing.
    supports_chargeback: false

  - id: MERCHANT_RESERVE_ACCOUNT
    owner_kind: MERCHANT
    ledger_class: SETTLEMENT
    product_family_id: MERCHANT_TREASURY
    currency_policy_id: SINGLE_HOME_CCY
    requires_instrument: false
    label: Merchant reserve / holdback account
    description: Reserve/holdback account used for risk buffers and delayed payouts.
    supports_chargeback: false
```

---

## 8) Operational notes (how priors should use this)

* `prior.product_mix` chooses **which `account_type` exists** for a given `(party_type, segment_id, …)` cell. 
* `prior.account_per_party` determines **how many** accounts of each type per party. 
* S3 instrument priors should treat `requires_instrument: true` as the eligibility switch for attaching instruments to accounts.

---

## 9) Acceptance checklist (MUST)

### 9.1 Structural checks

* YAML parses cleanly.
* `schema_version == 1`
* `taxonomy_id == taxonomy.account_types.v1`
* Unknown keys absent (top-level and nested objects).
* All ids match `^[A-Z][A-Z0-9_]{1,63}$`.
* Uniqueness:

  * `currency_policies[].id` unique
  * `product_families[].id` unique
  * `account_types[].id` unique
* Referential integrity:

  * `account_types[].ledger_class` ∈ `ledger_classes`
  * `account_types[].product_family_id` exists
  * `account_types[].currency_policy_id` exists
  * if `owner_kind: PARTY` then `allowed_party_types` exists and is non-empty
  * if `owner_kind: MERCHANT` then `allowed_party_types` is absent

### 9.2 Realism floors

* `len(account_types) >= 12`
* PARTY types ≥ 8; MERCHANT types ≥ 2
* `len(product_families) >= 6`
* `len(currency_policies) >= 2`
* ledger class coverage: DEPOSIT + CREDIT_REVOLVING + CREDIT_INSTALLMENT + SETTLEMENT each present at least once.

### 9.3 Stability / digest posture

* No timestamps/UUIDs/in-file digests.
* Lists sorted by id ascending.
* No YAML anchors/aliases.

---

## 10) Change control (MUST)

* `account_type.id` is a stable API token:

  * never repurpose an existing id for a new meaning
  * prefer adding new types over renaming existing ones
* Breaking changes require bumping the filename version (`taxonomy.account_types.v2.yaml`) and updating dependent priors.
