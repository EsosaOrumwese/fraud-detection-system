# Authoring Guide — `fraud_campaign_catalogue_config_6B` (S3 campaign templates, targeting & schedules, v1)

## 0) Purpose

`fraud_campaign_catalogue_config_6B` is the **sealed, token-less** control-plane pack that **6B.S3** uses to:

* discover the set of **campaign templates** `T` (campaign_type, target domain, constraints),
* decide how many **instances** of each template to realise per `(manifest_fingerprint, seed, scenario_id)`,
* define **targeting quotas** (how many entities/flows/events to target), and
* define **activation schedules/windows** (when the campaign runs inside a scenario).

S3 treats this pack as **the authority** for campaign “what/when/how much”. It must be strong enough that Codex cannot “wing it” and still pass validation.

---

## 1) Registration & sealing expectations

6B.S0 requires all behaviour/campaign policy packs to be **registered**, **schema-referenced**, and included in `sealed_inputs_6B` with `sha256_hex`.

If this pack is marked `REQUIRED` and is missing or invalid, **S3 MUST fail preconditions**. 

> If you haven’t yet registered this artefact in your 6B registry/dictionary, author the guide + file now, then register it as a control-plane artefact so S0 can seal it as required.

---

## 2) Scope boundaries

### In scope (this file owns)

* Template catalog (campaign types + parameters).
* Activation/count models for instances.
* Scheduling/windows for each instance.
* Targeting quotas and target kinds.

### Out of scope (owned elsewhere)

* **How** campaigns mutate flows/events (that’s `fraud_overlay_policy_6B`). 
* RNG budgets and counter wiring (that’s `fraud_rng_policy_6B`). S3 explicitly references RNG families like `rng_event_campaign_activation`, `rng_event_campaign_targeting`, and `rng_event_overlay_mutation` via the RNG policy pack. 
* Truth/bank labels (that’s S4 policies).

---

## 3) Core concepts (terms used in this guide)

* **Template** `T`: a reusable campaign definition (campaign_type, target_kind, eligibility filters, schedule model, intensity model). 
* **Instance** `C`: one realised campaign in a specific world/seed/scenario with a concrete `campaign_id`, concrete window, and concrete target set. 
* **Target kinds** (v1 recommended): `ENTITY`, `FLOW`, `EVENT` (and optional `SESSION`).
* **Campaign catalogue output**: S3 writes `s3_campaign_catalogue_6B`, which records realised instances and their parameters, and is consumed by S4/S5.

---

## 4) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `config_id` (string; MUST be `fraud_campaign_catalogue_config_6B`)
3. `config_version` (string; MUST be `v1`)
4. `vocabulary` (object)
5. `templates` (list of objects)
6. `activation_models` (object)
7. `schedule_models` (object)
8. `quota_models` (object)
9. `targeting_filters` (object)
10. `guardrails` (object)
11. `realism_targets` (object)
12. `notes` (optional string)

Unknown keys ⇒ **INVALID** (fail closed at S0/S3).

Token-less rules:

* no `generated_at`, no timestamps, no in-file digests/UUIDs.
* no YAML anchors/aliases.

---

## 5) `vocabulary` (MUST)

Pins the closed enums referenced by templates.

Required:

* `campaign_type_vocab` (list[str])
* `fraud_family_vocab` (list[str]) *(coarse: e.g., `CARD_TESTING`, `ATO`, `REFUND_ABUSE`, `MERCHANT_COLLUSION`)*
* `target_kind_vocab` (list[str]) *(recommended: `ENTITY`, `FLOW`, `EVENT`)*
* `target_entity_kind_vocab` (list[str]) *(e.g., `PARTY`, `ACCOUNT`, `INSTRUMENT`, `DEVICE`, `IP`, `MERCHANT`)*
* `channel_group_vocab` (list[str]) (must match S1/S2 usage)
* `tactic_vocab` (optional here; if present must be a subset of what `fraud_overlay_policy_6B` allows) 

---

## 6) `templates[]` (MUST)

Each template object MUST contain:

### Identity

* `template_id` (stable token, uppercase snake)
* `campaign_type` (must be in vocab)
* `fraud_family` (must be in vocab)
* `description` (1–3 sentences)

### Targeting

* `target_kind` (ENTITY/FLOW/EVENT)
* `target_entity_kind` *(required if target_kind=ENTITY; else must be absent)*
* `target_flow_scope` *(required if target_kind in {FLOW,EVENT}; describes which S2 flows are eligible)*

### Activation

* `activation_model_id` (ref into `activation_models`)
* `schedule_model_id` (ref into `schedule_models`)
* `quota_model_id` (ref into `quota_models`)
* `filters_id` (ref into `targeting_filters`)

### Constraints (fail closed)

* `channel_groups_allowed` (subset of vocab; non-empty)
* `requires_instrument` (bool)
* `requires_device` (bool)
* `requires_ip` (bool)
* `max_instances_per_seed` (int ≥ 0)
* `max_targets_per_instance` (int ≥ 0)
* `min_targets_per_instance` (int ≥ 0)

Rules:

* `min_targets_per_instance <= max_targets_per_instance`
* If the chosen target domain is empty at runtime, S3’s behaviour must follow the template’s `on_no_candidates` posture (see §10). 

---

## 7) `activation_models` (MUST)

Defines how many instances `N_T` of a template exist per `(manifest_fingerprint, seed, scenario_id)`.

Each model MUST specify:

* `model_id`
* `mode` ∈ `{DETERMINISTIC, POISSON_V1, CATEGORICAL_V1}`
* parameters:

  * deterministic: `n_instances`
  * poisson: `lambda`
  * categorical: `support` + `prob`
* `rng_family` (MUST be `rng_event_campaign_activation`) for stochastic modes 
* `key_ids` (MUST include at least: `manifest_fingerprint, seed, scenario_id, template_id`; forbid `run_id`) 

Deterministic rule:

* If the distribution degenerates to a singleton, S3 MUST treat it as deterministic and emit a non-consuming envelope (per RNG policy rules). 

---

## 8) `schedule_models` (MUST)

Defines **when** an instance runs in scenario time.

Each schedule model MUST specify:

* `model_id`
* `mode` ∈ `{FULL_SCENARIO, FIXED_WINDOW_V1, MULTI_WINDOW_V1}`
* `time_basis` ∈ `{UTC, LOCAL_TZID}` *(LOCAL requires S1 attached tzid availability)*
* For fixed/multi windows:

  * `start_offset_seconds`
  * `duration_seconds`
  * optional `repeat_every_seconds` + `repeat_count`
* `rng_family` optional (only if you allow stochastic start time); if used must be `rng_event_campaign_activation` and consume fixed draws. 

Constraints:

* windows must lie within the scenario horizon; if not, template must define whether to clip or fail (`on_out_of_horizon`). v1 recommended: **FAIL** (avoid silent drift).

---

## 9) `quota_models` (MUST)

Defines how many targets each instance will attempt to hit.

Each quota model MUST specify:

* `model_id`
* `mode` ∈ `{FIXED_V1, RATE_PER_DAY_V1, FRACTION_OF_DOMAIN_V1}`
* parameters:

  * fixed: `n_targets`
  * rate: `targets_per_day` + optional `burstiness`
  * fraction: `fraction` + `min_targets` + `max_targets`
* `rng_family` (MUST be `rng_event_campaign_targeting` for any stochastic element) 
* `key_ids` (MUST include: `manifest_fingerprint, seed, scenario_id, campaign_id`; forbid run_id) 

Hard rule:

* quotas must be computable deterministically from sealed inputs and the instance schedule; no reading of “future” S4/S5 outputs.

---

## 10) `targeting_filters` (MUST)

Defines reusable filter blocks used by templates to build deterministic candidate domains before RNG selection. 

Each filter block MUST specify:

* `filters_id`
* `entity_filters` (for ENTITY campaigns):

  * allowed static role sets (from 6A.S5 outputs; e.g., “only parties with role in {CLEAN, …}”)
  * allowed segment ids / party types / regions (subset; optional)
* `flow_filters` (for FLOW/EVENT campaigns):

  * allowed channel_groups
  * allowed flow_type_ids (subset of S2 flow catalog)
  * amount buckets (optional; references `amount_model_6B` family buckets)
* `device_ip_filters` (optional):

  * allowlist of `ip_type` groups (residential vs proxy/datacentre)
  * allowlist of device groups
* `weighting` (deterministic weights before RNG sampling):

  * `mode` ∈ `{UNIFORM, LINEAR_SCORE_V1}`
  * if score: declare features and weights (must be computable from sealed context)

No RNG is used to build candidate sets; RNG is used only to select targets from candidates, via `rng_event_campaign_targeting`. 

---

## 11) Guardrails (MUST)

Hard caps to prevent runaway:

* `max_total_campaign_instances_per_seed_scenario`
* `max_total_targets_per_seed_scenario`
* `max_targets_per_campaign_instance`
* `max_windows_per_campaign_instance`

Fail/degrade posture (v1 recommended):

* if a required cap is exceeded ⇒ FAIL (don’t silently clamp unless your `behaviour_config_6B` explicitly chooses clamp-and-warn).

---

## 12) Realism targets (MUST)

Non-toy corridors checked at authoring time (and optionally validated in S5):

* `min_templates_total` (int; recommended ≥ 6)
* `min_fraud_family_coverage` (e.g., at least 3 distinct families present)
* `campaign_prevalence_ranges` (by fraud_family; `{min,max}` as fraction of sessions/flows/entities)
* `targeting_diversity_min` (at least N templates that target different kinds: entity + flow)
* `proxy_usage_presence` (bool) *(at least one template may target proxy/anonymizer IP context)*
* `collusion_cluster_presence` (bool) *(if you model merchant collusion)*

---

## 13) Minimal v1 example (skeleton)

```yaml
schema_version: 1
config_id: fraud_campaign_catalogue_config_6B
config_version: v1

vocabulary:
  campaign_type_vocab: [CARD_TESTING, ATO, REFUND_ABUSE, MERCHANT_COLLUSION, BONUS_ABUSE, PROMO_FRAUD]
  fraud_family_vocab: [CARD_TESTING, ATO, REFUND_ABUSE, MERCHANT_COLLUSION, ABUSE_OTHER]
  target_kind_vocab: [ENTITY, FLOW, EVENT]
  target_entity_kind_vocab: [PARTY, ACCOUNT, INSTRUMENT, DEVICE, IP, MERCHANT]
  channel_group_vocab: [ECOM, POS, ATM, BANK_RAIL, HYBRID]

templates:
  - template_id: T_CARD_TESTING_V1
    campaign_type: CARD_TESTING
    fraud_family: CARD_TESTING
    description: "Burst of small auth attempts across many instruments."
    target_kind: ENTITY
    target_entity_kind: INSTRUMENT
    activation_model_id: ACT_POISSON_LOW
    schedule_model_id: SCH_FIXED_2D
    quota_model_id: QUOTA_RATE_BURSTY
    filters_id: F_CARDLIKE_ECOM
    channel_groups_allowed: [ECOM]
    requires_instrument: true
    requires_device: true
    requires_ip: true
    max_instances_per_seed: 5
    min_targets_per_instance: 50
    max_targets_per_instance: 5000
    on_no_candidates: SKIP_INSTANCE

activation_models:
  ACT_POISSON_LOW:
    mode: POISSON_V1
    lambda: 1.0
    rng_family: rng_event_campaign_activation
    key_ids: [manifest_fingerprint, seed, scenario_id, template_id]

schedule_models:
  SCH_FIXED_2D:
    mode: FIXED_WINDOW_V1
    time_basis: UTC
    start_offset_seconds: 0
    duration_seconds: 172800

quota_models:
  QUOTA_RATE_BURSTY:
    mode: RATE_PER_DAY_V1
    targets_per_day: 1200
    burstiness: 0.6
    rng_family: rng_event_campaign_targeting
    key_ids: [manifest_fingerprint, seed, scenario_id, campaign_id]

targeting_filters:
  F_CARDLIKE_ECOM:
    entity_filters:
      allowed_party_types: [RETAIL, BUSINESS]
      allowed_static_party_roles: [CLEAN, SYNTHETIC_ID, MULE]   # example; must match 6A role vocab
    flow_filters: {}
    device_ip_filters:
      allowed_ip_groups: [RESIDENTIAL, MOBILE_CARRIER, PUBLIC_SHARED, ANONYMIZER_PROXY]
    weighting:
      mode: LINEAR_SCORE_V1
      features:
        - { name: party_risk_tier, weight: 0.30 }
        - { name: device_high_risk_flag, weight: 0.20 }
      clamp: { min: 0.10, max: 5.0 }

guardrails:
  max_total_campaign_instances_per_seed_scenario: 50
  max_total_targets_per_seed_scenario: 200000
  max_targets_per_campaign_instance: 100000
  max_windows_per_campaign_instance: 20

realism_targets:
  min_templates_total: 6
  min_fraud_family_coverage: 3
  targeting_diversity_min: 3
  proxy_usage_presence: true
  campaign_prevalence_ranges:
    CARD_TESTING: { min: 0.0005, max: 0.03 }
    ATO:          { min: 0.0001, max: 0.01 }
```

---

## 14) Acceptance checklist (MUST)

1. Token-less, YAML parses, strict keys (unknown keys invalid).
2. At least one template exists; realism floors satisfied. 
3. All referenced `activation_model_id / schedule_model_id / quota_model_id / filters_id` exist.
4. All referenced RNG families are present in `fraud_rng_policy_6B` and used only where policy says (S3 references these families explicitly). 
5. Candidate filtering is deterministic; RNG is used only for instance counts/target selection as described in S3. 
6. Outputs are sufficient for S3 to produce `s3_campaign_catalogue_6B` which is required downstream (S4/S5).

---
