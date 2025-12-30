# Authoring Guide — `behaviour_prior_pack_6B` (S1 behaviour priors pack, v1)

## 0) Purpose

`behaviour_prior_pack_6B` is the **behaviour-priors authority** for **how S1 selects among sealed 6A entities** when attaching them to sealed 5B arrivals, and (optionally) how S1 parameterises sessionisation. It provides **per-segment / per-channel / per-geo** distributions for things like:

* visit/engagement propensity (which parties are more likely to appear),
* account / instrument selection preferences,
* device/IP reuse and exposure preferences,
* multi-merchant / multi-channel propensity parameters (as priors, not hard rules).

Hard boundary: this pack **does not create new entities or arrivals**; it only shapes selection among entities defined by 6A and arrivals defined by 5B.

---

## 1) Contract identity and sealing

### 1.1 Required presence and sealing

6B.S0 is responsible for binding and sealing all 6B behaviour/campaign/labelling packs in `sealed_inputs_6B` (digest recorded), but S0 must not interpret their semantics.

### 1.2 Registration note

In the current `dataset_dictionary.layer3.6B.yaml` excerpted in this chat, I do **not** see an explicit entry for `behaviour_prior_pack_6B` alongside the other policies; you’ll want to register it (or explicitly treat your existing `attachment_policy_6B` + `sessionisation_policy_6B` as the “equivalent”).

### 1.3 Recommended v1 wiring (to add to dictionary + registry)

* **dataset_id:** `behaviour_prior_pack_6B`
* **manifest_key:** `mlr.6B.policy.behaviour_prior_pack` *(recommended naming to match other policy keys)*
* **path:** `config/layer3/6B/behaviour_prior_pack_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/behaviour_prior_pack_6B` *(add anchor stub if needed)*
* **sealed_inputs role:** `behaviour_prior`
* **status:** `REQUIRED`
* **read_scope:** `ROW_LEVEL`

(If you prefer the manifest_key literal `behaviour_prior_pack_6B` because you reference it that way in docs, that’s fine—just keep it consistent across dictionary/registry and S0 sealing.)

---

## 2) Consumers and dependency boundary

### Primary consumer

* **6B.S1** (entity attachment + sessions) uses this pack as the numeric priors for “how” selection works.

### Secondary consumers (optional)

* S2/S3/S4 may read it only as **context** (e.g., segment-level “digital affinity” knobs), but must not override their own dedicated policies.

### Mandatory companion policies

S1 is still governed by:

* `attachment_policy_6B` (structural candidate-set rules / requiredness)
* `sessionisation_policy_6B` (session key + gap thresholds)
* `rng_policy_6B` (RNG families/budgets)
  This pack supplies **numbers** (priors/weights), not the structural rules or RNG budget contracts.

---

## 3) What this pack must contain (v1)

This pack must be sufficient for Codex to parameterise S1 selection without inventing numbers in code.

### 3.1 Dimensions (recommended v1 keys)

All tables should be keyed by some subset of:

* `region_id`
* `party_type`
* `segment_id`
* `channel_group`

(These are all available from 6A party base + S1 arrival context; and they match the “per-segment/channel/geo” requirement.)

### 3.2 Required priors (minimum set)

1. **Geo affinity priors**

* `p_home_geo` (probability mass on “home geo” party candidates vs global/cross-geo) by `(segment_id, channel_group)`

2. **Account preference priors**

* weights by `ledger_class` (DEPOSIT / CREDIT_REVOLVING / CREDIT_INSTALLMENT / SETTLEMENT) by `(segment_id, channel_group)`

3. **Instrument preference priors**

* weights by `instrument_class` and/or `instrument_kind` (CARD_PHYSICAL / CARD_VIRTUAL / BANK_HANDLE / WALLET_TOKEN) by `(segment_id, channel_group)`

4. **Device reuse priors**

* `p_primary_device` (choose primary-owner device vs secondary/other) by `(segment_id, channel_group)`
* optional: terminal-vs-customer device mixture for POS/ATM

5. **IP exposure priors**

* weights by `ip_group` (RESIDENTIAL / MOBILE_CARRIER / PUBLIC_SHARED / HOSTING_DATACENTRE / ANONYMIZER_PROXY) by `(segment_id, channel_group)`

These are exactly the “account/instrument preferences” and “device/IP reuse behaviours” S1 calls out for a behaviour prior pack.

---

## 4) RNG posture (MUST)

This pack is **RNG-free**. It supplies only probabilities/weights.

All randomness must flow through `rng_policy_6B` families; S1 must never “sample extra” beyond the budgeted decision loci.

---

## 5) Strict YAML structure (MUST)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `pack_id` (string; MUST be `behaviour_prior_pack_6B`)
3. `pack_version` (string; MUST be `v1`)
4. `vocabulary` (object)
5. `geo_affinity` (object)
6. `account_preferences` (object)
7. `instrument_preferences` (object)
8. `device_preferences` (object)
9. `ip_preferences` (object)
10. `guardrails` (object)
11. `realism_targets` (object)
12. `notes` *(optional)*

Unknown keys ⇒ INVALID (fail closed).

Token-less:

* no timestamps/UUIDs/digests in-file
* no YAML anchors/aliases

---

## 6) Non-toy realism requirements (MUST)

At authoring time, the pack must satisfy:

* **Cross-geo presence:** for at least some segments, `p_home_geo` must be < 1 (cross-border exists, bounded).
* **IP diversity:** for at least some segments/channels, `PUBLIC_SHARED` and `ANONYMIZER_PROXY` must have non-zero weight (but bounded).
* **Device reuse:** primary-device selection must dominate for most segments (realistic reuse), but not be exactly 1 everywhere.
* **Channel differentiation:** POS/ATM must bias toward terminal-style device/IP exposure compared to ECOM (even if only via weights).

---

## 7) Minimal v1 example (starter skeleton)

```yaml
schema_version: 1
pack_id: behaviour_prior_pack_6B
pack_version: v1

vocabulary:
  channel_groups: [ECOM, POS, ATM, BANK_RAIL, HYBRID]
  ledger_classes: [DEPOSIT, CREDIT_REVOLVING, CREDIT_INSTALLMENT, SETTLEMENT]
  instrument_kinds: [CARD_PHYSICAL, CARD_VIRTUAL, BANK_HANDLE, WALLET_TOKEN]
  ip_groups: [RESIDENTIAL, MOBILE_CARRIER, PUBLIC_SHARED, HOSTING_DATACENTRE, ANONYMIZER_PROXY]

geo_affinity:
  mode: home_vs_global_mixture_v1
  p_home_geo_by_segment_channel:
    # segment_id tokens must match 6A taxonomy.party
    RETAIL_STUDENT:
      ECOM: 0.90
      POS: 0.96
      ATM: 0.98
      BANK_RAIL: 0.92
      HYBRID: 0.92
    RETAIL_AFFLUENT:
      ECOM: 0.80
      POS: 0.92
      ATM: 0.96
      BANK_RAIL: 0.85
      HYBRID: 0.85

account_preferences:
  mode: weights_by_ledger_class_v1
  weights_by_segment_channel:
    RETAIL_STUDENT:
      ECOM: { DEPOSIT: 0.70, CREDIT_REVOLVING: 0.20, CREDIT_INSTALLMENT: 0.10, SETTLEMENT: 0.00 }
      POS:  { DEPOSIT: 0.80, CREDIT_REVOLVING: 0.18, CREDIT_INSTALLMENT: 0.02, SETTLEMENT: 0.00 }
    RETAIL_AFFLUENT:
      ECOM: { DEPOSIT: 0.55, CREDIT_REVOLVING: 0.35, CREDIT_INSTALLMENT: 0.10, SETTLEMENT: 0.00 }
      POS:  { DEPOSIT: 0.60, CREDIT_REVOLVING: 0.38, CREDIT_INSTALLMENT: 0.02, SETTLEMENT: 0.00 }

instrument_preferences:
  mode: weights_by_instrument_kind_v1
  weights_by_segment_channel:
    RETAIL_STUDENT:
      ECOM: { CARD_PHYSICAL: 0.55, CARD_VIRTUAL: 0.25, BANK_HANDLE: 0.15, WALLET_TOKEN: 0.05 }
      POS:  { CARD_PHYSICAL: 0.80, CARD_VIRTUAL: 0.05, BANK_HANDLE: 0.10, WALLET_TOKEN: 0.05 }
    RETAIL_AFFLUENT:
      ECOM: { CARD_PHYSICAL: 0.45, CARD_VIRTUAL: 0.30, BANK_HANDLE: 0.10, WALLET_TOKEN: 0.15 }
      POS:  { CARD_PHYSICAL: 0.75, CARD_VIRTUAL: 0.05, BANK_HANDLE: 0.05, WALLET_TOKEN: 0.15 }

device_preferences:
  mode: primary_vs_other_v1
  p_primary_device_by_segment_channel:
    RETAIL_STUDENT: { ECOM: 0.88, POS: 0.92, ATM: 0.95, BANK_RAIL: 0.90, HYBRID: 0.90 }
    RETAIL_AFFLUENT:{ ECOM: 0.92, POS: 0.94, ATM: 0.96, BANK_RAIL: 0.93, HYBRID: 0.93 }
  terminal_bias_by_channel:
    POS:  { use_terminal_device_prob: 0.85 }
    ATM:  { use_terminal_device_prob: 0.95 }
    ECOM: { use_terminal_device_prob: 0.00 }
    BANK_RAIL: { use_terminal_device_prob: 0.00 }
    HYBRID: { use_terminal_device_prob: 0.10 }

ip_preferences:
  mode: weights_by_ip_group_v1
  weights_by_segment_channel:
    RETAIL_STUDENT:
      ECOM: { RESIDENTIAL: 0.45, MOBILE_CARRIER: 0.35, PUBLIC_SHARED: 0.12, HOSTING_DATACENTRE: 0.04, ANONYMIZER_PROXY: 0.04 }
      POS:  { RESIDENTIAL: 0.40, MOBILE_CARRIER: 0.40, PUBLIC_SHARED: 0.15, HOSTING_DATACENTRE: 0.03, ANONYMIZER_PROXY: 0.02 }
    RETAIL_AFFLUENT:
      ECOM: { RESIDENTIAL: 0.38, MOBILE_CARRIER: 0.30, PUBLIC_SHARED: 0.20, HOSTING_DATACENTRE: 0.05, ANONYMIZER_PROXY: 0.07 }
      POS:  { RESIDENTIAL: 0.35, MOBILE_CARRIER: 0.40, PUBLIC_SHARED: 0.18, HOSTING_DATACENTRE: 0.04, ANONYMizer_PROXY: 0.03 }

guardrails:
  require_all_probs_sum_to_one: true
  forbid_zero_total_weight: true
  max_anonymizer_weight_any_cell: 0.10
  max_hosting_weight_any_cell: 0.15
  min_home_geo_prob_any_cell: 0.70

realism_targets:
  require_nonzero_public_shared_somewhere: true
  require_nonzero_anonymizer_somewhere: true
  require_channel_differentiation: true
```

---

## 8) Acceptance checklist (MUST)

* Pack is registered/sealed as a behaviour-prior artefact (or explicitly replaced by your `attachment_policy_6B` + `sessionisation_policy_6B` combo).
* Token-less YAML; unknown keys invalid; no anchors/aliases.
* All categorical tables sum to 1 (within tolerance) and contain no negative weights.
* No cell has all-zero weights for a required dimension (prevents “no candidates” paths).
* Non-toy corridors satisfied (cross-geo exists but bounded; IP exposure diversity exists; channel differentiation exists).
