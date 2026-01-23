# Authoring Guide — `attachment_policy_6B` (S1 entity selection & linking, v1)

## 0) Purpose

`attachment_policy_6B` defines **how 6B.S1 attaches a sealed arrival (5B)** to a **sealed entity context (6A)** by constructing **candidate sets** and **attachment priors** for:

* `party_id`
* `account_id`
* `instrument_id` *(may be null, depending on channel/rail)*
* `device_id`
* `ip_id`

S1 MUST:

* only use entities that exist in 6A bases and satisfy 6A link semantics,
* only consume RNG via the S1 RNG family (`rng_event_entity_attach`) when more than one candidate exists,
* never drop or mutate arrivals.

---

## 1) Contract identity (MUST)

* **manifest_key:** `mlr.6B.policy.attachment_policy`
* **dataset_id:** `attachment_policy_6B`
* **path:** `config/layer3/6B/attachment_policy_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/attachment_policy_6B`
* **consumed_by:** `6B.S0`, `6B.S1`

Token-less posture:

* no timestamps, UUIDs, or digests in-file (digest comes from S0 sealing).

---

## 2) Dependencies and authority boundary (MUST)

S1 constructs candidate sets and attachments using sealed inputs only:

### 2.1 Required sealed data-plane inputs

S1 loads 6A bases and link tables (ROW_LEVEL) and must validate all output IDs back to these.

### 2.2 Required policy-plane inputs

* `rng_profile_layer3` (Layer-3 RNG law)
* `rng_policy_6B` (S1 families & budgets)
* `sessionisation_policy_6B` (because session key composition depends on attachment fields)
* `behaviour_config_6B` (optional scoping/flags; restrictive only)

### 2.3 Hard rules

* S1 MUST NOT attach incompatible entities (e.g., instrument not belonging to account, account not belonging to party, device not linked as allowed).
* If a required dimension has **no candidates**, that is a fatal error (`S1_ENTITY_NO_CANDIDATES`). 

---

## 3) Attachment step order (MUST)

S1 MUST evaluate attachment dimensions in a fixed order (so policy is deterministic and auditable). The recommended v1 order matches your S1 spec narrative:

1. PARTY
2. ACCOUNT
3. INSTRUMENT
4. DEVICE
5. IP

---

## 4) Candidate sets (MUST be pinned)

The policy MUST define, for each dimension, how candidates are constructed from 6A bases/links:

### 4.1 Party candidates

Minimum v1 candidate sets:

* `PARTY_HOME_COUNTRY`: parties whose `country_iso` matches the arrival’s `legal_country_iso` (or equivalent zone country component if your arrival schema encodes it).
* `PARTY_GLOBAL`: all parties.

Selection between these sets is controlled by a single uniform (see §6) to preserve the 1-draw budget per attachment step.

### 4.2 Account candidates (condition on chosen party)

* `ACCT_OWNED_BY_PARTY`: all accounts where `owner_party_id == chosen party_id`.
  Optionally split into account groups using fields present in `s2_account_base_6A` (e.g., deposit vs credit vs loan) if you want channel-aware choices.

### 4.3 Instrument candidates (condition on chosen account)

* `INSTR_LINKED_TO_ACCOUNT`: instruments linked via `s3_account_instrument_links_6A` (or equivalent).

### 4.4 Device candidates (channel-aware)

Device candidate sources must be explicit:

* `DEVICE_CUSTOMER`: devices linked to the chosen party in `s4_device_links_6A` (owner/secondary roles allowed by 6A).
* `DEVICE_MERCHANT_TERMINAL`: devices linked to `merchant_id` (terminal/back-end devices) when the channel implies merchant-side device.

### 4.5 IP candidates (condition on chosen device and/or merchant)

* `IP_FOR_DEVICE`: IPs linked to the chosen `device_id` in `s4_ip_links_6A`.
* `IP_FOR_MERCHANT`: IPs linked to merchant endpoints (if present in 6A graph).

---

## 5) Requiredness and nullability (MUST)

This policy MUST declare required vs optional dimensions by **channel_group** (or a derived channel classification using arrival fields).

Minimum v1 posture:

* `party_id`: REQUIRED for all arrivals
* `account_id`: REQUIRED for all arrivals
* `device_id`: REQUIRED for all arrivals *(but may be customer device or merchant terminal depending on channel)*
* `ip_id`: REQUIRED for all arrivals
* `instrument_id`: REQUIRED for `CARD_LIKE` channels; OPTIONAL for `BANK_RAIL` channels

If the policy requires `instrument_id` and no valid instrument exists for any viable account, S1 MUST fail (`S1_ENTITY_NO_CANDIDATES`).

---

## 6) Attachment priors and sampling law (MUST be 1 uniform per step)

S1’s S1 RNG budget assumes **1 uniform per stochastic attachment** via `rng_event_entity_attach`.
So v1 MUST use a **single-uniform mixture + weighted-CDF selection**:

### 6.1 One-uniform mixture (for choosing between candidate sources)

If a dimension has multiple candidate sources (e.g., party: home vs global; device: customer vs terminal), define a mixture probability `p_primary_source ∈ [0,1]`.

Given a single uniform `u`:

* If `u < p_primary_source`, choose source A (primary).
* Else choose source B (fallback), with remapped `u' = (u - p_primary_source) / (1 - p_primary_source)`.

### 6.2 One-uniform weighted choice inside a candidate set

Given candidates `c1..cK` with non-negative weights `w_i`:

* If `K==1`: deterministic (no draw; optionally emit non-consuming envelope).
* Else:

  * normalise `p_i = w_i / Σw`
  * compute prefix CDF in **stable candidate order**
  * choose smallest index `i` with `CDF_i ≥ u` (u in (0,1))

Candidate ordering MUST be deterministic and specified (e.g., by ID ascending).

---

## 7) Scoring models (MUST be deterministic and non-toy)

The policy MUST provide explicit weight models for each dimension. v1 should keep them simple but realistic:

### 7.1 Party weights

Suggested inputs (all available from 6A bases/roles that S1 loads):

* party segment/type (`party_type`, `segment_id`)
* holdings size proxies (number of accounts / instruments / devices, derived deterministically)
* party posture (`s5_party_fraud_roles_6A`), if you want higher/lower activity per role

### 7.2 Account weights

Condition on party + channel:

* prefer deposit/credit accounts depending on channel_group
* optionally incorporate account posture (`s5_account_fraud_roles_6A`)

### 7.3 Instrument weights

Condition on account + channel:

* for card-like channels, prefer card-like instruments (by `instrument_type` allowlist in this policy)

### 7.4 Device weights

Channel-aware:

* customer device: choose among party-linked devices; optionally upweight “primary owner” devices
* merchant terminal: choose among merchant-linked terminal devices

### 7.5 IP weights

Condition on chosen device:

* default to “typical device IP” when available; allow non-typical exposure (public/shared, proxy/datacentre) with bounded probability that can be increased for higher-risk parties/devices (but still constrained).

---

## 8) Provenance fields S1 should emit (MUST be supported)

S1 spec expects attachment provenance fields such as `attach_rule_id`, optional `attach_score`, and `attach_rng_family`/version.
This policy MUST define:

* a closed set of `attach_rule_id` values (one per branch)
* which dimensions can emit `attach_score` (optional)
* what “deterministic vs stochastic” means for each dimension

---

## 9) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
policy_id: attachment_policy_6B
policy_version: v1

dependencies:
  rng_profile_layer3: { policy_id: rng_profile_layer3, required: true }
  rng_policy_6B:      { policy_id: rng_policy_6B, required: true }
  behaviour_config_6B:{ policy_id: behaviour_config_6B, required: false }

attachment_steps_order: [PARTY, ACCOUNT, INSTRUMENT, DEVICE, IP]

channel_model:
  # Prefer: use channel_group already present in arrival_events_5B.
  channel_field: channel_group
  default_channel_group: ECOM
  known_channel_groups: [ECOM, POS, ATM, BANK_RAIL, HYBRID]

requiredness:
  PARTY:     { by_channel: { ECOM: REQUIRED, POS: REQUIRED, ATM: REQUIRED, BANK_RAIL: REQUIRED, HYBRID: REQUIRED } }
  ACCOUNT:   { by_channel: { ECOM: REQUIRED, POS: REQUIRED, ATM: REQUIRED, BANK_RAIL: REQUIRED, HYBRID: REQUIRED } }
  INSTRUMENT:{ by_channel: { ECOM: REQUIRED, POS: REQUIRED, ATM: REQUIRED, BANK_RAIL: OPTIONAL, HYBRID: REQUIRED } }
  DEVICE:    { by_channel: { ECOM: REQUIRED, POS: REQUIRED, ATM: REQUIRED, BANK_RAIL: REQUIRED, HYBRID: REQUIRED } }
  IP:        { by_channel: { ECOM: REQUIRED, POS: REQUIRED, ATM: REQUIRED, BANK_RAIL: REQUIRED, HYBRID: REQUIRED } }

party_policy:
  candidate_sources:
    - source_id: PARTY_HOME_COUNTRY
      definition: "party.country_iso == arrival.legal_country_iso"
    - source_id: PARTY_GLOBAL
      definition: "all parties"
  mixture:
    p_primary_source_by_channel: { ECOM: 0.97, POS: 0.98, ATM: 0.98, BANK_RAIL: 0.97, HYBRID: 0.97 }
  scoring:
    mode: linear_positive_v1
    components:
      - { name: base, value: 1.0 }
      - { name: holdings_log1p, weight: 0.25 }     # derived from counts
      - { name: posture_multiplier, weight: 0.00 } # optional
    min_weight_eps: 1.0e-12

account_policy:
  candidates: "accounts where owner_party_id == party_id"
  group_preferences_by_channel:
    ECOM: [DEPOSIT, CREDIT]
    POS:  [DEPOSIT, CREDIT]
    ATM:  [DEPOSIT]
    BANK_RAIL: [DEPOSIT]
    HYBRID: [DEPOSIT, CREDIT]
  scoring:
    mode: group_then_weighted_v1
    min_weight_eps: 1.0e-12
  fallback:
    if_no_candidates: FAIL

instrument_policy:
  candidates: "instruments linked to chosen account"
  allowed_instrument_types_by_channel:
    ECOM: [CARD_LIKE]
    POS:  [CARD_LIKE]
    ATM:  [CARD_LIKE]
    BANK_RAIL: [ANY]
    HYBRID: [CARD_LIKE]
  scoring:
    mode: uniform_if_multiple_v1
  fallback:
    if_required_and_empty: RESELECT_ACCOUNT_THEN_FAIL

device_policy:
  mode_by_channel:
    ECOM: CUSTOMER_DEVICE
    POS:  MERCHANT_TERMINAL_DEVICE
    ATM:  MERCHANT_TERMINAL_DEVICE
    BANK_RAIL: CUSTOMER_DEVICE
    HYBRID: CUSTOMER_DEVICE
  customer_device_candidates: "devices linked to party via 6A device_links"
  terminal_device_candidates:  "devices linked to merchant via 6A device_links"
  scoring:
    mode: prefer_primary_owner_v1
    min_weight_eps: 1.0e-12
  fallback:
    if_required_and_empty: FAIL

ip_policy:
  candidates_by_device: "IPs linked to chosen device via 6A ip_links"
  candidates_by_merchant: "IPs linked to merchant via 6A ip_links (if present)"
  mode_by_channel:
    ECOM: FROM_DEVICE
    POS:  FROM_DEVICE
    ATM:  FROM_DEVICE
    BANK_RAIL: FROM_DEVICE
    HYBRID: FROM_DEVICE
  scoring:
    mode: prefer_typical_ip_v1
    allow_proxy_share_max: 0.08
  fallback:
    if_required_and_empty: FAIL

provenance:
  attach_rule_id_enabled: true
  attach_score_enabled: true
  attach_rng_family_field: attach_rng_family
```

---

## 10) Acceptance checklist (MUST)

1. **Contract pins** match dictionary/registry (path + schema_ref + manifest_key).
2. **Step order** fixed and matches S1 behaviour description.
3. **No forbidden entity combos**: account belongs to party, instrument belongs to account, device/ip links satisfy 6A link tables per policy.
4. **RNG budget compatibility**: each stochastic dimension uses exactly one `rng_event_entity_attach` draw; deterministic decisions consume zero.
5. **No-candidate posture** is explicit: required dimensions with empty candidates produce `S1_ENTITY_NO_CANDIDATES` (fatal). 
6. Token-less, no anchors/aliases, unknown keys invalid.

---
