# Authoring Guide — `merchant_class_policy_5A` (5A.S1 demand classing, v1)

## 0) Purpose

`merchant_class_policy_5A` is the **sealed, deterministic** policy that 5A.S1 uses to map each in-scope `(merchant_id, legal_country_iso, tzid)` to:

* `demand_class` (required), and optionally
* `demand_subclass`, `profile_id`, and `class_source` (recommended for audit/debug).

It MUST be **RNG-free**, **total** (covers every domain row), **unambiguous** (exactly one match per row), and **real-deal** (not a handful of sample rules).

---

## 1) File identity (MUST)

* **Artefact / dictionary id:** `merchant_class_policy_5A`
* **Path:** `config/layer2/5A/policy/merchant_class_policy_5A.v1.yaml`
* **Schema anchor:** `schemas.5A.yaml#/policy/merchant_class_policy_5A` *(permissive; this guide pins the real contract)*
* **Digest posture:** token-less; **do not embed any file digest** in the YAML (S0 sealing inventory records the file’s sha).

---

## 2) Pinned semantics (how S1 must interpret it)

### 2.1 Domain (what gets classified)

S1 classifies the full `(merchant, zone)` domain discovered from upstream `zone_alloc` (3A authority). This policy MUST NOT redefine that universe; it only labels it.

### 2.2 Exactly-one classification (MUST)

For every domain row:

* exactly one `demand_class` must be produced.
* if zero rules match → FAIL CLOSED (policy incomplete).
* if more than one rule matches → FAIL CLOSED (policy ambiguous).

To enforce this, the v1 policy is interpreted as a **decision tree** with **exclusive branches** (see §3.4). No “multiple rules can apply with precedence” in v1.

### 2.3 Inputs (feature vocabulary; no guessing)

S1 may only use features derived from sealed inputs. This policy may reference only these feature keys:

**Merchant features**

* `mcc` (4-digit string)
* `mcc_sector` (derived via this policy’s MCC map; §3.2)
* `channel_group` (derived via this policy’s channel map; §3.3)
* `merchant_home_country_iso` (from ingress merchant table)

**Zone features (from 3A zone_alloc)**

* `legal_country_iso`
* `tzid`
* `zone_site_count` (int ≥ 0)
* `merchant_country_site_count` (sum over zones for that merchant×country)
* `zone_site_share = zone_site_count / merchant_country_site_count` (if denom>0 else 0)
* `zones_per_merchant_country` (count distinct tzid for merchant×country)

**Virtual features (from 3B)**

* `virtual_mode` in `{NON_VIRTUAL, HYBRID, VIRTUAL_ONLY}`
* `is_virtual` boolean (= virtual_mode != NON_VIRTUAL)

Optional civil-time signal (allowed but not required):

* `tzid_settlement` (from 3B virtual_settlement_3B, if sealed)

If any referenced feature is missing at runtime, S1 must FAIL CLOSED unless the policy defines a fallback for it (v1 allows only the fallbacks explicitly listed below).

---

## 3) Required policy structure (fields-strict as authored by this guide)

Top-level YAML object with **exactly** these keys:

1. `policy_id` (string; MUST be `merchant_class_policy_5A`)
2. `version` (string; non-placeholder governance tag, e.g. `v1.0.0`)
3. `demand_class_catalog` (list; class definitions)
4. `mcc_sector_map` (object; MCC→sector mapping)
5. `channel_group_map` (object; raw channel→channel_group mapping)
6. `decision_tree_v1` (object; exclusive classification logic)
7. `realism_targets` (object; distribution guardrails for authoring-time checks)

No extra keys.

### 3.1 `demand_class_catalog` (MUST)

A list of objects, each with:

* `demand_class` (string id; pattern `^[a-z][a-z0-9_]{2,31}$`)
* `description` (string, non-empty)
* `intended_shape_family` (string; helps S2 template resolution)
* optional `notes`

**Real-deal minimum:** at least **10** classes (see §6).

### 3.2 `mcc_sector_map` (MUST; non-toy)

A mapping from MCC strings (`"0000"`..`"9999"`, but only those in your MCC universe) to a small sector enum:

Allowed sectors (v1 pinned):

* `digital_services`
* `general_retail`
* `grocery_pharmacy`
* `fuel_auto`
* `travel_hospitality`
* `dining_entertainment`
* `cash_fin_services`
* `utilities_bills`
* `government_education`
* `other`

**Authoring requirement:** this map MUST cover **every MCC that appears in your merchant universe snapshot** (fail closed if not).

### 3.3 `channel_group_map` (MUST)

Mapping from raw `channel` values in your merchant ingress to:

Allowed channel groups (v1 pinned):

* `card_present`
* `card_not_present`
* `mixed`

This prevents ambiguity if upstream uses multiple spellings.

### 3.4 `decision_tree_v1` (MUST; exclusive branches)

A fields-strict object with exactly:

* `virtual_branch` (object)
* `nonvirtual_branch` (object)
* `default_class` (string; must exist in catalog)
* `subclass_rules` (object)

**virtual_branch**:

* `virtual_only_class` (string)
* `hybrid_class` (string)

**nonvirtual_branch**:

* `by_channel_group` (object with keys `card_present`, `card_not_present`, `mixed`)

  * each value is a `by_sector` object mapping the 10 sectors to a class

This structure guarantees **exactly one** output because the path is:
`virtual_mode → channel_group → mcc_sector → class`.

**subclass_rules**:

* `zone_role` thresholds (see §5.3)

### 3.5 `realism_targets` (MUST)

Object with numeric guardrails used during authoring-time validation:

* `max_class_share` (e.g. 0.55)
* `min_nontrivial_classes` (e.g. 6)
* `min_class_share_for_nontrivial` (e.g. 0.02)
* `min_virtual_share_if_virtual_present` (e.g. 0.01)
* `max_single_country_share_within_class` (e.g. 0.35)

---

## 4) Deterministic authoring algorithm (Codex-no-input)

Codex must generate a “real deal” policy from sealed upstream references, with no human tuning.

### 4.1 Inputs (MUST exist; fail closed)

* `transaction_schema_merchant_ids` (merchant_id, mcc, channel, home_country_iso)
* MCC canonical dataset (`mcc_canonical_vintage` with MCC descriptions/names)
* `zone_alloc` (to compute zones_per_merchant_country and zone_site_share for distribution checks)
* `virtual_classification_3B` (if present in the engine build; otherwise treat all as NON_VIRTUAL)

### 4.2 Build `mcc_sector_map` (deterministic)

Using MCC canonical descriptions, assign each MCC to one of the 10 sectors by keyword scoring (pinned sets; no ML, no randomness):

Example keyword sets (v1 pinned; Codex must use exactly these):

* `digital_services`: {digital, online, internet, software, cloud, streaming, subscription, hosting, telecom}
* `grocery_pharmacy`: {grocery, supermarket, food, pharmacy, drug}
* `fuel_auto`: {fuel, gas, gasoline, petroleum, auto, automotive, service station}
* `travel_hospitality`: {airline, travel, hotel, lodging, car rental, railway, cruise}
* `dining_entertainment`: {restaurant, dining, bar, nightclub, cinema, entertainment, gambling, amusement}
* `cash_fin_services`: {atm, financial, bank, money, securities, insurance, cash}
* `utilities_bills`: {utility, electric, gas utility, water, telecommunications bill, cable, internet bill}
* `government_education`: {government, tax, tuition, education, university, school}
* `general_retail`: {retail, store, apparel, merchandise, shopping, department}
* `other`: fallback if no keywords hit

Tie-break: if multiple sectors tie, pick by this fixed priority order:
`digital_services > cash_fin_services > travel_hospitality > dining_entertainment > grocery_pharmacy > fuel_auto > utilities_bills > government_education > general_retail > other`

Then **override** using merchant-universe evidence:

* If an MCC appears in merchant universe with >5% of merchants and was classified as `other`, reassign it to `general_retail` (prevents “large mass in other” toy behaviour).

### 4.3 Build `channel_group_map` (deterministic)

Pinned mapping rules:

* if raw channel string contains `not_present` or equals `ecom` → `card_not_present`
* if contains `present` or equals `pos` → `card_present`
* if equals `mixed` → `mixed`
  Otherwise → FAIL CLOSED (unexpected channel values must be handled upstream or by extending the map explicitly).

### 4.4 Build `demand_class_catalog` (fixed v1 taxonomy)

Codex must emit at least these 10 classes (exact ids pinned so later policies can refer to them):

1. `office_hours`
2. `consumer_daytime`
3. `evening_weekend`
4. `always_on_local`
5. `online_24h`
6. `online_bursty`
7. `travel_hospitality`
8. `fuel_convenience`
9. `bills_utilities`
10. `low_volume_tail`

(Descriptions + intended_shape_family are required; you can tune families later in shape_library.)

### 4.5 Populate `decision_tree_v1` (deterministic mapping)

Pinned mapping table (sector → class) for each channel group:

**Virtual branch**

* `VIRTUAL_ONLY` → `online_24h`
* `HYBRID` → `online_24h`

**Non-virtual, card_not_present**

* `digital_services` → `online_24h`
* `cash_fin_services` → `online_bursty`
* `travel_hospitality` → `online_bursty`
* `dining_entertainment` → `online_bursty`
* `general_retail` → `online_24h`
* `grocery_pharmacy` → `online_24h`
* `fuel_auto` → `online_bursty`
* `utilities_bills` → `bills_utilities`
* `government_education` → `office_hours`
* `other` → `online_24h`

**Non-virtual, card_present**

* `digital_services` → `office_hours`
* `cash_fin_services` → `office_hours`
* `travel_hospitality` → `travel_hospitality`
* `dining_entertainment` → `evening_weekend`
* `general_retail` → `consumer_daytime`
* `grocery_pharmacy` → `consumer_daytime`
* `fuel_auto` → `fuel_convenience`
* `utilities_bills` → `bills_utilities`
* `government_education` → `office_hours`
* `other` → `consumer_daytime`

**Non-virtual, mixed**

* use the `card_present` mapping (v1 pinned).

**Default class**

* `default_class = consumer_daytime`

This yields a total, exclusive decision tree (no overlap, no missing case).

### 4.6 Subclassing (zone_role) (deterministic, optional output)

Define `demand_subclass` as a zone role based on `zone_site_share`:

* if `zone_site_share ≥ 0.60` → `primary_zone`
* else if `zone_site_share ≤ 0.10` → `tail_zone`
* else → `secondary_zone`

If `merchant_country_site_count == 0`, force `tail_zone`.

Define `profile_id` as:
`"<demand_class>.<demand_subclass>.<channel_group>"`

All lowercase, max 64 chars; if longer, FAIL CLOSED (means class ids aren’t controlled).

---

## 5) Output YAML requirements (format + determinism)

* UTF-8, LF newlines
* key order pinned as in §3
* `demand_class_catalog` sorted by `demand_class` ascending
* `mcc_sector_map` keys sorted ascending
* `channel_group_map` keys sorted ascending
* no timestamps / generated_at / environment fields

---

## 6) Realism floors (MUST; fail closed)

Codex must validate the authored policy against the actual merchant×zone universe (from `zone_alloc`) and abort if any fail:

### 6.1 Non-toy catalog

* at least **10** demand classes present (exact v1 taxonomy above)
* at least **8** of them actually appear in the merchant×zone domain for the current merchant universe (prevents “defined but unused” toy classes)

### 6.2 Distribution sanity

Compute class shares over all in-scope `(merchant, zone)` rows:

* no class share exceeds `max_class_share` (recommend 0.55)
* at least `min_nontrivial_classes` classes have share ≥ `min_class_share_for_nontrivial` (recommend 6 classes ≥ 2%)

### 6.3 Virtual sanity (if virtual merchants exist upstream)

If any merchant has `virtual_mode != NON_VIRTUAL`:

* share of rows classified as `online_24h` must be ≥ `min_virtual_share_if_virtual_present` (recommend 1%)

### 6.4 Country dominance guard (prevents “all of a class in one country”)

For each demand_class with share ≥ 2%:

* the largest single `legal_country_iso` share within that class must be ≤ `max_single_country_share_within_class` (recommend 35%)

If any check fails → FAIL CLOSED (policy would be “toy” or degenerate for this world).

---

## 7) Minimal example snippet (NOT a real file)

Real file includes full `mcc_sector_map` coverage for the MCC universe.

```yaml
policy_id: merchant_class_policy_5A
version: v1.0.0

demand_class_catalog:
  - demand_class: bills_utilities
    description: "Bills/utilities payments; steady weekday bias."
    intended_shape_family: bills_weekly
  - demand_class: consumer_daytime
    description: "Daytime consumer spending; lunch/afternoon bias."
    intended_shape_family: consumer_weekly
  - demand_class: evening_weekend
    description: "Evening + weekend spending; nightlife/entertainment skew."
    intended_shape_family: evening_weekly
  - demand_class: fuel_convenience
    description: "Fuel/convenience; broad day coverage and commute peaks."
    intended_shape_family: fuel_weekly
  - demand_class: low_volume_tail
    description: "Very low activity; sparse across week."
    intended_shape_family: low_weekly
  - demand_class: office_hours
    description: "Business/office hours; strong weekday daytime concentration."
    intended_shape_family: office_weekly
  - demand_class: online_24h
    description: "Online spending; 24/7 with mild circadian structure."
    intended_shape_family: online_weekly
  - demand_class: online_bursty
    description: "Online bursty; campaign-like spikes / high variance."
    intended_shape_family: bursty_weekly
  - demand_class: travel_hospitality
    description: "Travel/hospitality; weekend/season effects later via overlays."
    intended_shape_family: travel_weekly
  - demand_class: always_on_local
    description: "Always-on local; near-continuous baseline."
    intended_shape_family: always_weekly

mcc_sector_map:
  "5411": grocery_pharmacy
  "5541": fuel_auto
  "5812": dining_entertainment
  "7011": travel_hospitality
  "7995": dining_entertainment
  "9399": government_education

channel_group_map:
  card_present: card_present
  card_not_present: card_not_present
  mixed: mixed

decision_tree_v1:
  virtual_branch:
    virtual_only_class: online_24h
    hybrid_class: online_24h
  nonvirtual_branch:
    by_channel_group:
      card_present:
        by_sector:
          digital_services: office_hours
          general_retail: consumer_daytime
          grocery_pharmacy: consumer_daytime
          fuel_auto: fuel_convenience
          travel_hospitality: travel_hospitality
          dining_entertainment: evening_weekend
          cash_fin_services: office_hours
          utilities_bills: bills_utilities
          government_education: office_hours
          other: consumer_daytime
      card_not_present:
        by_sector:
          digital_services: online_24h
          general_retail: online_24h
          grocery_pharmacy: online_24h
          fuel_auto: online_bursty
          travel_hospitality: online_bursty
          dining_entertainment: online_bursty
          cash_fin_services: online_bursty
          utilities_bills: bills_utilities
          government_education: office_hours
          other: online_24h
      mixed:
        by_sector: { ...same as card_present... }
  default_class: consumer_daytime
  subclass_rules:
    zone_role:
      primary_share_ge: 0.60
      tail_share_le: 0.10

realism_targets:
  max_class_share: 0.55
  min_nontrivial_classes: 6
  min_class_share_for_nontrivial: 0.02
  min_virtual_share_if_virtual_present: 0.01
  max_single_country_share_within_class: 0.35
```

---

## 8) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. Top-level keys exactly as §3; `policy_id` correct; `version` non-placeholder.
3. `mcc_sector_map` covers every MCC found in merchant universe.
4. `channel_group_map` covers every raw channel found in merchant universe (no unknowns).
5. Decision tree completeness: every branch references only classes in catalog.
6. Exactly-one classification guaranteed by structure (virtual_mode→channel_group→sector).
7. Realism floors in §6 pass on the actual merchant×zone domain.

If any check fails → **FAIL CLOSED** (do not publish; do not seal).

---
