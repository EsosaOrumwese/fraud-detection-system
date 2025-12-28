# Authoring Guide — `grouping_policy_5B` (5B.S1 deterministic grouping plan for latent fields + count keys)

## 0) Purpose

`grouping_policy_5B` is the **sealed authority** that tells 5B.S1 how to assign each arrival-driving entity to a **group_id** for:

* **S2 latent field realisation** (one latent vector per `(scenario_id, group_id)`), and
* downstream bookkeeping / diagnostics.

It must be:

* deterministic / RNG-free,
* non-toy (enough groups to model heterogeneity, but not millions),
* stable (byte-stable, no timestamps, no in-file digests),
* and consistent with upstream semantics (uses only sealed features).

---

## 1) File identity (MUST)

* **Artefact ID:** `grouping_policy_5B`
* **Path:** `config/layer2/5B/grouping_policy_5B.yaml`
* **Schema anchor:** `schemas.5B.yaml#/config/grouping_policy_5B` *(permissive; this guide pins the real contract)*
* **Token-less posture:** do **not** embed file digests; S0 sealing inventory is authoritative.

---

## 2) Authority boundaries (MUST)

* This policy **does not** define the domain; the domain comes from 5A/3A/3B surfaces (merchant×zone×scenario).
* This policy **only** defines how to compute `group_id` from allowed features.
* S1 MUST produce a **group assignment table** (`s1_grouping_plan_5B`) that includes:

  * the entity key (merchant_id, zone_representation, scenario_id),
  * derived grouping features,
  * and the `group_id`.

---

## 3) Allowed feature vocabulary (MUST; decision-free)

A grouping policy may reference only these feature keys:

### 3.1 Merchant / zone identity (always available)

* `merchant_id`
* `legal_country_iso`
* `tzid` (zone representation)
* `scenario_id`

### 3.2 5A-derived labels (sealed)

* `demand_class`
* `channel_group`
* `virtual_mode` (or `is_virtual`)

### 3.3 Structural keys (sealed upstream)

* `zones_per_merchant_country` (int)
* `zone_role` (`primary_zone|secondary_zone|tail_zone`) if available

### 3.4 Optional compressed geography (allowed)

* `zone_group_id` derived deterministically from tzid using this policy’s hash law (see §5.2)

No other features are permitted in v1 (prevents accidental “hidden dependency” creep).

---

## 4) Grouping modes (v1 pinned)

v1 supports exactly one grouping mode to avoid ambiguity:

* `mode: stratified_bucket_hash_v1`

Meaning:

* `group_id` is formed by:

  1. building a small **stratum key** from categorical features, and
  2. applying a deterministic **hash bucket** within each stratum to cap group explosion.

This yields “many groups” (heterogeneity) but controlled and repeatable.

---

## 5) Deterministic group_id law (MUST)

### 5.1 Stratum key (MUST)

v1 stratum key is the tuple:

* `stratum = (scenario_band, demand_class, channel_group, virtual_band, zone_group_id)`

Where:

* `scenario_band` is derived from scenario flags:

  * `baseline` if `scenario_is_baseline=true`
  * `stress` if `scenario_is_stress=true`
  * (if both false, abort; if both true, abort)
* `virtual_band` is:

  * `virtual` if `virtual_mode != NON_VIRTUAL`
  * `physical` otherwise
* `zone_group_id` is computed from tzid (below)

### 5.2 `zone_group_id` hash (MUST)

To avoid thousands of tzids blowing up groups, we compress tzid into a small bucket.

Policy pins:

* `zone_group_buckets = 16`
* `zone_group_id = "zg" + str( SHA256("5B.zone_group|" + tzid)[0] % zone_group_buckets )`

Where:

* `SHA256(...)[0]` means the first byte of the digest interpreted as 0..255.

This yields `zg0..zg15`.

### 5.3 In-stratum hash bucket (MUST)

Within each stratum, assign a stable bucket:

* `B = in_stratum_buckets` (policy value; v1 recommended 32)

Compute:

* `msg = UTF8("5B.group|" + scenario_id + "|" + demand_class + "|" + channel_group + "|" + virtual_band + "|" + zone_group_id + "|" + merchant_id)`
* `x = uint64_be(SHA256(msg)[0:8])`
* `b = x % B`

Then:

* `group_id = "g|" + scenario_band + "|" + demand_class + "|" + channel_group + "|" + virtual_band + "|" + zone_group_id + "|b" + two_digit(b)`

Example:

* `g|baseline|consumer_daytime|card_present|physical|zg03|b07`

This ensures:

* group_id is deterministic,
* stable across reruns,
* and the number of groups is bounded.

---

## 6) Required policy file structure (fields-strict by this guide)

Top-level YAML object with **exactly**:

1. `policy_id` (MUST be `grouping_policy_5B`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `mode` (MUST be `stratified_bucket_hash_v1`)
4. `zone_group_buckets` (int; MUST be 16 in v1)
5. `in_stratum_buckets` (int; MUST be 32 in v1)
6. `scenario_band_law` (string; pinned)
7. `virtual_band_law` (string; pinned)
8. `stratum_fields` (list; pinned)
9. `group_id_format` (string; pinned)
10. `realism_targets` (object)

### 6.1 Pinned string fields (MUST equal these)

* `scenario_band_law: "baseline_if_is_baseline_else_stress"`
* `virtual_band_law: "virtual_if_virtual_mode_not_NON_VIRTUAL_else_physical"`
* `stratum_fields: ["scenario_band","demand_class","channel_group","virtual_band","zone_group_id"]`
* `group_id_format: "g|{scenario_band}|{demand_class}|{channel_group}|{virtual_band}|{zone_group_id}|b{b:02d}"`

### 6.2 `realism_targets` (MUST)

* `min_groups_per_scenario: 200`
* `max_groups_per_scenario: 50000`
* `min_group_members_median: 10` *(median rows per group)*
* `max_single_group_share: 0.02` *(no group should contain >2% of rows)*

These are checked against the actual domain size.

---

## 7) Realism floors (MUST; fail closed)

After applying grouping to the run’s domain, Codex/S1 MUST validate:

* `#groups_per_scenario` within `[min_groups_per_scenario, max_groups_per_scenario]`
* median `rows_per_group ≥ min_group_members_median`
* largest group share ≤ `max_single_group_share`
* at least **80%** of groups have >1 member (prevents “almost every row its own group” toy failure)

If any fail → FAIL CLOSED (grouping policy not suitable for this world).

---

## 8) Recommended v1 policy file (copy/paste baseline)

```yaml
policy_id: grouping_policy_5B
version: v1.0.0

mode: stratified_bucket_hash_v1

zone_group_buckets: 16
in_stratum_buckets: 32

scenario_band_law: baseline_if_is_baseline_else_stress
virtual_band_law: virtual_if_virtual_mode_not_NON_VIRTUAL_else_physical

stratum_fields:
  - scenario_band
  - demand_class
  - channel_group
  - virtual_band
  - zone_group_id

group_id_format: "g|{scenario_band}|{demand_class}|{channel_group}|{virtual_band}|{zone_group_id}|b{b:02d}"

realism_targets:
  min_groups_per_scenario: 200
  max_groups_per_scenario: 50000
  min_group_members_median: 10
  max_single_group_share: 0.02
```

---

## 9) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys; keys exactly as §6.
2. `policy_id` correct; `version` non-placeholder.
3. `zone_group_buckets == 16` and `in_stratum_buckets == 32` in v1.
4. Hash laws and band laws pinned as required strings.
5. Apply policy to the actual domain and confirm realism floors (§7) pass.
6. No timestamps / generated fields.

---
