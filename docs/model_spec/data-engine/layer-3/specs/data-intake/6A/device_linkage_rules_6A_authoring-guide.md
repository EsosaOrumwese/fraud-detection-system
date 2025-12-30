# Authoring Guide — `device_linkage_rules_6A` (`DEVICE_LINKAGE_RULES`, v1)

## 0) Purpose

`device_linkage_rules_6A` is the **sealed graph-structure config** that 6A.S4 uses to build `s4_device_links_6A` (device→party/account/instrument/merchant edges) and to enforce **link-role semantics + degree caps + forbidden combinations**.

This pack is where you pin, in a **guided / non-toy** way:

* how devices get **primary owners** (`primary_party_id` / `primary_merchant_id` in `s4_device_base_6A`) 
* the allowed **link_role vocabulary** (e.g., `PRIMARY_OWNER`, `SECONDARY_USER`, `MERCHANT_TERMINAL`, `ASSOCIATED_ACCOUNT_ACCESS`)
* device **sharing patterns** (single-user vs shared; #parties per shared device; #accounts per device; #instruments per device)
* hard **constraints/caps** (max parties per device, max devices per party, max accounts per device, forbidden combos) 

S4 treats linkage-rule violations as hard errors (`LINKAGE_RULE_VIOLATION` style), and must fail closed rather than “guess”. 

---

## 1) File identity (v1 contract pins)

This artefact is registered in the 6A v2 contract surface and MUST be sealed by S0 as a row-level policy input.

**Recommended v1 wiring:**

* **manifest_key:** `mlr.6A.policy.device_linkage_rules`
* **dataset_id:** `device_linkage_rules_6A`
* **path:** `config/layer3/6A/policy/device_linkage_rules_6A.v1.yaml`
* **schema_ref:** `schemas.6A.yaml#/policy/device_linkage_rules_6A`
* **sealed_inputs role:** `DEVICE_LINKAGE_RULES`
* **sealed_inputs status:** `REQUIRED`
* **sealed_inputs read_scope:** `ROW_LEVEL`
* **source:** internal, authored (no acquisition)

Token-less posture: **no timestamps, UUIDs, or digests in-file**. S0 sealing records file digest (`sha256_hex`) in `sealed_inputs_6A`.

---

## 2) Scope and non-goals

### In scope

* Rules for `s4_device_links_6A` semantics and validity.
* Rules that determine **primary ownership** fields in `s4_device_base_6A` (party-owned vs merchant-owned device types). 
* Deterministic sampling/selection logic for:

  * secondary users (shared devices),
  * account/instrument accessibility edges.

### Out of scope (MUST NOT be here)

* “How many devices exist” (that’s `prior_device_counts_6A`).
* “How many IPs exist / devices per IP” (that’s `prior_ip_counts_6A` or a separate graph pack).
* Fraud roles (that’s S5 priors).
* Per-arrival behaviour (6B).

---

## 3) What S4 must guarantee (invariants this pack exists to enforce)

Given `s4_device_base_6A` and upstream bases `s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A`, S4 must produce `s4_device_links_6A` such that:

* every referenced `device_id` exists in `s4_device_base_6A`
* any referenced `party_id/account_id/instrument_id/merchant_id` exists upstream
* link roles are valid and obey “required-nonnull fields” rules
* degree caps and forbidden combinations are respected (per this linkage pack)

---

## 4) Strict YAML structure (MUST)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `config_id` (string; MUST be `device_linkage_rules_6A`)
3. `config_version` (string; MUST be `v1`)
4. `bindings` (object)
5. `device_groups` (object)
6. `link_role_vocabulary` (list of objects)
7. `owner_policy` (object)
8. `sharing_policy` (object)
9. `access_policy` (object)
10. `degree_caps` (object)
11. `forbidden_combinations` (list of objects)
12. `realism_targets` (object)
13. `acceptance_checks` (object)
14. `notes` (optional string)

Unknown keys: **INVALID**.
No YAML anchors/aliases. Token-less only.

---

## 5) `bindings` (MUST)

Required fields:

* `party_taxonomy_ref: taxonomy_party_6A`
* `account_taxonomy_ref: taxonomy_account_types_6A`
* `instrument_taxonomy_ref: taxonomy_instrument_types_6A`
* `device_taxonomy_ref: taxonomy_devices_6A`

Purpose: Codex can validate that every `device_type/account_type/instrument_type` referenced in rules exists in those taxonomies before S4 runs.

---

## 6) `device_groups` (MUST)

This pack MUST declare a small set of **device_group_id** values and a mapping from `device_type → device_group_id`, so rules can be written by group rather than per-type explosion.

Required:

* `groups`: list of `{group_id, device_types:[...], semantics}`
* `device_type_to_group`: explicit map OR implied by group membership
* `group_priority`: if a device_type appears in multiple groups (should not happen), first match wins; duplicates are INVALID.

Minimum recommended groups (v1):

* `CONSUMER_PERSONAL` (phones, wearables)
* `CONSUMER_SHARED` (shared desktops/tablets)
* `COMPUTER_PORTABLE` (laptops)
* `MERCHANT_TERMINAL` (POS/ATM/kiosk)
* `BACKEND_SERVER` (servers/API clients) *(optional)*

---

## 7) `link_role_vocabulary` (MUST)

Each role object MUST include:

* `role_id` (string, uppercase snake)
* `label`
* `description`
* `required_nonnull_fields` (subset of `{party_id, account_id, instrument_id, merchant_id}`)
* `allowed_field_patterns` (list of patterns, see below)

### 7.1 Minimum required roles (v1)

These are explicitly referenced as valid examples in S4: 

* `PRIMARY_OWNER`
* `SECONDARY_USER`
* `MERCHANT_TERMINAL`
* `ASSOCIATED_ACCOUNT_ACCESS`

Recommended additions (helps realism without exploding complexity):

* `ASSOCIATED_INSTRUMENT_ACCESS`
* `SERVICE_ACCOUNT_ACCESS` (for backend/server devices)

### 7.2 Allowed field patterns (MUST be explicit)

Because `s4_device_links_6A` is a wide table (`party_id/account_id/instrument_id/merchant_id` nullable), you must pin which combinations are allowed per role:

A pattern is an object:

* `pattern_id`
* `party_id` ∈ `{REQUIRED, FORBIDDEN, OPTIONAL}`
* `account_id` ∈ `{REQUIRED, FORBIDDEN, OPTIONAL}`
* `instrument_id` ∈ `{REQUIRED, FORBIDDEN, OPTIONAL}`
* `merchant_id` ∈ `{REQUIRED, FORBIDDEN, OPTIONAL}`

Example (typical):

* `PRIMARY_OWNER` for consumer device: `party_id=REQUIRED`, all others FORBIDDEN
* `MERCHANT_TERMINAL`: `merchant_id=REQUIRED`, others FORBIDDEN
* `ASSOCIATED_ACCOUNT_ACCESS`: `party_id=OPTIONAL`, `account_id=REQUIRED`, others FORBIDDEN
* `ASSOCIATED_INSTRUMENT_ACCESS`: `party_id=OPTIONAL`, `instrument_id=REQUIRED`, others FORBIDDEN

---

## 8) `owner_policy` (MUST)

This defines how S4 populates `primary_party_id` / `primary_merchant_id` in `s4_device_base_6A`.

Required fields:

* `owner_kind_by_group` (map group_id → enum `{PARTY, MERCHANT}`)
* `primary_owner_role_id` (MUST be `PRIMARY_OWNER` for PARTY-owned groups, and `MERCHANT_TERMINAL` for MERCHANT-owned terminal groups)
* `selection_scope` (enum):

  * `WITHIN_DEVICE_CELL_ONLY` (recommended): primary owner must come from the same `(region_id, party_type, segment_id)` cell the device was planned under
  * `WITHIN_REGION_ONLY` (allowed for special devices like servers)

Required deterministic rule:

* For PARTY-owned devices, primary owner is always a **single party**.
* For MERCHANT-owned terminal devices, primary owner is always a **single merchant**.
* A device MUST NOT have both `primary_party_id` and `primary_merchant_id` set.

---

## 9) `sharing_policy` (MUST)

Defines when a PARTY-owned device is shared and how many parties it is shared across.

Required fields:

* `p_shared_by_group` (map group_id → float in [0,1])
* `shared_party_count_model_by_group`:

  * each group has `{model_id, min_k, max_k, params...}`
  * supported v1 `model_id` values: `geometric_capK_v1`, `zipf_capK_v1`

Pinned semantics:

* If device is not shared → exactly 1 party (`PRIMARY_OWNER`)
* If device is shared → 1 primary owner + `(k-1)` secondary users (`SECONDARY_USER`)
* Secondary users MUST be distinct parties.
* For `CONSUMER_PERSONAL`, `p_shared` MUST be low (non-toy constraint).
* For `CONSUMER_SHARED`, `p_shared` MUST be materially higher than personal devices.

---

## 10) `access_policy` (MUST)

Defines how to create account/instrument access edges from devices.

### 10.1 Account access

Required fields:

* `accounts_per_device_by_group`:

  * `{model_id, min_k, max_k, params...}`
  * v1 supported: `poisson_capK_v1`, `zi_poisson_capK_v1`
* `account_selection_scope` enum:

  * `OWNERS_ONLY` (recommended): choose only accounts owned by linked parties
  * `OWNERS_AND_SHARED_HOUSEHOLD` (allowed): for shared devices, choose accounts from any linked party

Pinned semantics:

* For each device:

  * gather eligible accounts from scope
  * choose `k` accounts (k may be 0)
  * emit `ASSOCIATED_ACCOUNT_ACCESS` edges for each selected account

Fail/degrade rules:

* If eligible set is empty → emit 0 account edges (do not fail), unless `min_k > 0` (then fail).

### 10.2 Instrument access

Required fields:

* `instruments_per_device_by_group`:

  * `{model_id, min_k, max_k, params...}` (same supported set)
* `instrument_selection_scope` enum:

  * `FROM_SELECTED_ACCOUNTS_ONLY` (recommended): only instruments linked to chosen accounts
  * `FROM_ALL_OWNER_ACCOUNTS` (allowed)

Pinned semantics:

* emit `ASSOCIATED_INSTRUMENT_ACCESS` edges (if role included), otherwise omit instrument edges entirely.

---

## 11) `degree_caps` (MUST)

Degree caps must be explicit and separated into:

### 11.1 Per-device caps

* `max_parties_per_device_by_group`
* `max_accounts_per_device_by_group`
* `max_instruments_per_device_by_group`
* `max_merchants_per_device_by_group` (usually 0 for consumer groups, 1 for terminals)

### 11.2 Per-entity caps

* `max_devices_per_party` (global hard cap; must be coherent with `prior_device_counts_6A`)
* `max_devices_per_account`
* `max_devices_per_instrument`
* `max_devices_per_merchant` (for terminals)

Caps are enforced as hard constraints; if the plan would violate a hard cap for required edges, S4 must fail (`LINKAGE_RULE_VIOLATION`). 

---

## 12) `forbidden_combinations` (MUST)

List of explicit prohibitions, each as:

* `rule_id`
* `when` (predicate fields)
* `forbid` (predicate fields)

Examples (typical v1):

* terminals (`MERCHANT_TERMINAL` group) MUST NOT link to `party_id`
* consumer personal devices MUST NOT use `MERCHANT_TERMINAL` role
* backend servers MUST NOT have `SECONDARY_USER` edges
* `ASSOCIATED_ACCOUNT_ACCESS` edges MUST NOT include `merchant_id`

This prevents silent schema misuse.

---

## 13) Realism targets (NON-TOY corridors)

These are corridor checks S4 (or CI) can validate deterministically.

Required corridors:

* `shared_fraction_range_by_group` (group_id → {min,max})
* `mean_parties_per_shared_device_range_by_group` (group_id → {min,max})
* `mean_accounts_per_device_range_by_group` (group_id → {min,max})
* `mean_instruments_per_device_range_by_group` (group_id → {min,max})
* `fraction_devices_with_any_account_access_range_by_group` (group_id → {min,max})
* `fraction_devices_with_any_instrument_access_range_by_group` (group_id → {min,max})
* `enrichment_rules` (list), e.g.:

  * shared devices must have higher mean parties than personal devices by ≥ ratio

These corridors are the “no toy stuff” enforcement.

---

## 14) Minimal v1 example (shape)

```yaml
schema_version: 1
config_id: device_linkage_rules_6A
config_version: v1

bindings:
  party_taxonomy_ref: taxonomy_party_6A
  account_taxonomy_ref: taxonomy_account_types_6A
  instrument_taxonomy_ref: taxonomy_instrument_types_6A
  device_taxonomy_ref: taxonomy_devices_6A

device_groups:
  groups:
    - group_id: BACKEND_SERVER
      device_types: [SERVER]
      semantics: "Backend / automated clients."
    - group_id: COMPUTER_PORTABLE
      device_types: [LAPTOP]
      semantics: "Portable computers."
    - group_id: CONSUMER_PERSONAL
      device_types: [MOBILE_PHONE, WEARABLE]
      semantics: "Mostly personal devices."
    - group_id: CONSUMER_SHARED
      device_types: [DESKTOP, TABLET]
      semantics: "Shared household devices."
    - group_id: MERCHANT_TERMINAL
      device_types: [POS_TERMINAL, ATM, KIOSK]
      semantics: "Merchant terminals."
  group_priority: { CONSUMER_PERSONAL: 10, CONSUMER_SHARED: 20, COMPUTER_PORTABLE: 30, MERCHANT_TERMINAL: 40, BACKEND_SERVER: 50 }

link_role_vocabulary:
  - role_id: ASSOCIATED_ACCOUNT_ACCESS
    label: Account access
    description: "Device can access the account (app/web/terminal context)."
    required_nonnull_fields: [account_id]
    allowed_field_patterns:
      - { pattern_id: ACC_ONLY, party_id: OPTIONAL, account_id: REQUIRED, instrument_id: FORBIDDEN, merchant_id: FORBIDDEN }

  - role_id: ASSOCIATED_INSTRUMENT_ACCESS
    label: Instrument access
    description: "Device can use/access the instrument credential."
    required_nonnull_fields: [instrument_id]
    allowed_field_patterns:
      - { pattern_id: INSTR_ONLY, party_id: OPTIONAL, account_id: FORBIDDEN, instrument_id: REQUIRED, merchant_id: FORBIDDEN }

  - role_id: MERCHANT_TERMINAL
    label: Merchant terminal
    description: "Device is a merchant-owned terminal."
    required_nonnull_fields: [merchant_id]
    allowed_field_patterns:
      - { pattern_id: TERM_ONLY, party_id: FORBIDDEN, account_id: FORBIDDEN, instrument_id: FORBIDDEN, merchant_id: REQUIRED }

  - role_id: PRIMARY_OWNER
    label: Primary owner
    description: "Primary owner of a device."
    required_nonnull_fields: [party_id]
    allowed_field_patterns:
      - { pattern_id: OWNER_PARTY, party_id: REQUIRED, account_id: FORBIDDEN, instrument_id: FORBIDDEN, merchant_id: FORBIDDEN }

  - role_id: SECONDARY_USER
    label: Secondary user
    description: "Additional party using a shared device."
    required_nonnull_fields: [party_id]
    allowed_field_patterns:
      - { pattern_id: COUSER, party_id: REQUIRED, account_id: FORBIDDEN, instrument_id: FORBIDDEN, merchant_id: FORBIDDEN }

owner_policy:
  owner_kind_by_group:
    CONSUMER_PERSONAL: PARTY
    CONSUMER_SHARED: PARTY
    COMPUTER_PORTABLE: PARTY
    MERCHANT_TERMINAL: MERCHANT
    BACKEND_SERVER: MERCHANT
  selection_scope: WITHIN_DEVICE_CELL_ONLY

sharing_policy:
  p_shared_by_group:
    CONSUMER_PERSONAL: 0.03
    COMPUTER_PORTABLE: 0.08
    CONSUMER_SHARED: 0.25
    MERCHANT_TERMINAL: 0.00
    BACKEND_SERVER: 0.00
  shared_party_count_model_by_group:
    CONSUMER_PERSONAL: { model_id: geometric_capK_v1, min_k: 2, max_k: 4, p: 0.70 }
    COMPUTER_PORTABLE: { model_id: geometric_capK_v1, min_k: 2, max_k: 4, p: 0.65 }
    CONSUMER_SHARED: { model_id: geometric_capK_v1, min_k: 2, max_k: 6, p: 0.55 }

access_policy:
  accounts_per_device_by_group:
    CONSUMER_PERSONAL: { model_id: zi_poisson_capK_v1, min_k: 0, max_k: 5, p_zero: 0.05, mu: 1.6 }
    COMPUTER_PORTABLE: { model_id: zi_poisson_capK_v1, min_k: 0, max_k: 6, p_zero: 0.08, mu: 1.9 }
    CONSUMER_SHARED: { model_id: zi_poisson_capK_v1, min_k: 0, max_k: 8, p_zero: 0.15, mu: 2.2 }
    MERCHANT_TERMINAL: { model_id: zi_poisson_capK_v1, min_k: 0, max_k: 2, p_zero: 0.60, mu: 0.6 }
    BACKEND_SERVER: { model_id: zi_poisson_capK_v1, min_k: 0, max_k: 4, p_zero: 0.35, mu: 1.0 }
  account_selection_scope: OWNERS_ONLY

  instruments_per_device_by_group:
    CONSUMER_PERSONAL: { model_id: zi_poisson_capK_v1, min_k: 0, max_k: 6, p_zero: 0.10, mu: 1.4 }
    COMPUTER_PORTABLE: { model_id: zi_poisson_capK_v1, min_k: 0, max_k: 6, p_zero: 0.12, mu: 1.3 }
    CONSUMER_SHARED: { model_id: zi_poisson_capK_v1, min_k: 0, max_k: 8, p_zero: 0.18, mu: 1.8 }
  instrument_selection_scope: FROM_SELECTED_ACCOUNTS_ONLY

degree_caps:
  per_device_by_group:
    CONSUMER_PERSONAL: { max_parties: 4, max_accounts: 5, max_instruments: 6, max_merchants: 0 }
    COMPUTER_PORTABLE: { max_parties: 4, max_accounts: 6, max_instruments: 6, max_merchants: 0 }
    CONSUMER_SHARED: { max_parties: 6, max_accounts: 8, max_instruments: 8, max_merchants: 0 }
    MERCHANT_TERMINAL: { max_parties: 0, max_accounts: 2, max_instruments: 0, max_merchants: 1 }
    BACKEND_SERVER: { max_parties: 0, max_accounts: 4, max_instruments: 0, max_merchants: 1 }
  per_entity_global:
    max_devices_per_party: 20
    max_devices_per_account: 12
    max_devices_per_instrument: 8
    max_devices_per_merchant: 40

forbidden_combinations:
  - rule_id: TERM_NO_PARTY
    when: { device_group_id: MERCHANT_TERMINAL }
    forbid: { role_id: [PRIMARY_OWNER, SECONDARY_USER] }

  - rule_id: OWNER_NO_MERCHANT_FIELD
    when: { role_id: PRIMARY_OWNER }
    forbid: { merchant_id: ANY }

realism_targets:
  shared_fraction_range_by_group:
    CONSUMER_PERSONAL: { min: 0.00, max: 0.08 }
    COMPUTER_PORTABLE: { min: 0.02, max: 0.18 }
    CONSUMER_SHARED: { min: 0.10, max: 0.40 }
  mean_parties_per_shared_device_range_by_group:
    CONSUMER_PERSONAL: { min: 2.0, max: 3.0 }
    CONSUMER_SHARED: { min: 2.2, max: 4.5 }
  mean_accounts_per_device_range_by_group:
    CONSUMER_PERSONAL: { min: 0.8, max: 2.8 }
    CONSUMER_SHARED: { min: 1.0, max: 3.8 }
  fraction_devices_with_any_account_access_range_by_group:
    CONSUMER_PERSONAL: { min: 0.70, max: 0.98 }
    CONSUMER_SHARED: { min: 0.65, max: 0.98 }

acceptance_checks:
  require_exactly_one_primary_owner_per_device: true
  require_terminal_devices_have_merchant_owner: true
  enforce_degree_caps: true
  enforce_forbidden_combinations: true
```

---

## 15) Acceptance checklist (MUST)

### 15.1 Structural strictness

* YAML parses.
* Unknown keys absent everywhere.
* Token-less (no timestamps/UUIDs/digests).
* No YAML anchors/aliases.
* Deterministic ordering:

  * `link_role_vocabulary` sorted by `role_id`
  * group lists sorted by `group_id`
  * forbidden rules sorted by `rule_id`

### 15.2 Compatibility

* Every `device_type` referenced exists in `taxonomy_devices_6A`.
* Every link role referenced in policies exists in `link_role_vocabulary`.
* Any `account_type/instrument_type` restriction you add must exist in their taxonomies.

### 15.3 Table semantics alignment

* `s4_device_base_6A` primary owner fields are consistent with this pack.
* `s4_device_links_6A` uses `link_role` exactly as defined here and respects the allowed field patterns.

### 15.4 Degree constraints

* Per-device and per-entity caps enforced; violations fail closed (`LINKAGE_RULE_VIOLATION`). 

### 15.5 Non-toy realism

* All corridors in `realism_targets` pass, especially:

  * shared devices materially exist (but not everywhere)
  * shared fraction is higher for shared-device groups than personal-device groups
  * most consumer devices have some account access edges (but not 100%)

---
