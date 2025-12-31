# Authoring Guide — `fraud_rng_policy_6B` (S3 RNG families, budgets & keying, v1)

## 0) Purpose

`fraud_rng_policy_6B` is the **required RNG contract** for **6B.S3**. It defines:

* the **only RNG families** S3 is allowed to consume,
* the **fixed `draws` / `blocks` budgets** per decision locus,
* the **keying scheme** (substream ids) for reproducibility,
* the **event-emission obligations** that allow S5 to validate RNG accounting against expected counts.

S3 explicitly references three decision families:

* `rng_event_campaign_activation`
* `rng_event_campaign_targeting`
* `rng_event_overlay_mutation`

If this policy is missing/invalid, S3 must fail preconditions and must not emit `s3_campaign_catalogue_6B` or with-fraud surfaces.

---

## 1) Contract identity (MUST)

From your 6B contracts:

* **dataset_id:** `fraud_rng_policy_6B`
* **manifest_key:** `mlr.6B.policy.fraud_rng_policy`
* **path:** `config/layer3/6B/fraud_rng_policy_6B.yaml` 
* **schema_ref:** `schemas.6B.yaml#/policy/fraud_rng_policy_6B` 
* **consumed_by:** `6B.S0`, `6B.S3` 

Token-less posture:

* no timestamps, UUIDs, or in-file digests.
* S0 sealing records `sha256_hex` in `sealed_inputs_6B`.

---

## 2) Dependencies (MUST)

Required:

* `rng_profile_layer3` (open-interval u01, budget law `blocks=ceil(draws/2)`, substream derivation)
* `fraud_campaign_catalogue_config_6B` (declares activation models + quotas + schedules; may reference families)
* `fraud_overlay_policy_6B` (declares mutation decision points; may reference families)
* `behaviour_config_6B` (optional; may disable campaigns but must not alter RNG laws)

Hard rule:

* `run_id` MUST NOT participate in keying (log-only).

---

## 3) Family inventory (MUST)

v1 defines **exactly these 3 S3 families**:

1. `rng_event_campaign_activation`
2. `rng_event_campaign_targeting`
3. `rng_event_overlay_mutation`

S3 MUST NOT use any other family. If a policy references a non-listed family, S3 must fail preconditions (`S3_RNG_POLICY_INCOMPATIBLE`).

---

## 4) Deterministic budget law (MUST)

S3 must not have outcome-dependent RNG consumption. The expected number of RNG events must be inferable from:

* template count model,
* number of instances,
* schedule model (window count),
* quota model (target counts),
* and the number of mutations per target implied by overlay policy.

Therefore, v1 pins budgets per decision locus and requires **non-consuming envelopes** where deterministic.

* Consuming events have fixed `draws` and implied `blocks`.
* Deterministic loci emit non-consuming events (`draws="0", blocks=0`).

---

## 5) Budgets per family (v1)

### 5.1 `rng_event_campaign_activation` (1 draw)

Used for:

* sampling number of instances `N_T` when activation model is stochastic,
* optionally sampling schedule start offsets if schedule model is stochastic (v1: optional),
* any other “campaign-level” stochastic decision pinned by the catalogue config.

Budgets:

* consuming: `draws="1"`, `blocks=1`
* non-consuming: `draws="0"`, `blocks=0`

### 5.2 `rng_event_campaign_targeting` (1 draw)

Used for:

* selecting targets from a candidate set (weighted-CDF) per target pick,
* sampling quotas when quota model is stochastic (if you allow it).

Budgets:

* consuming: `draws="1"`, `blocks=1`
* non-consuming: `draws="0"`, `blocks=0`

### 5.3 `rng_event_overlay_mutation` (1 draw)

Used for:

* selecting tactic from mixture per target (if selection_mode requires),
* choosing mutation parameters where one-uniform suffices (e.g., bounded multiplier selection),
* choosing swap candidates from a candidate set.

Budgets:

* consuming: `draws="1"`, `blocks=1`
* non-consuming: `draws="0"`, `blocks=0`

**Important constraint:** All S3 mutation parameterisations must be implementable with **single-uniform** decisions per locus (via deterministic remapping/splitting if needed). If a tactic truly requires >1 uniform, it must be broken into multiple loci, each with one event. That ensures deterministic accounting.

---

## 6) Keying scheme (MUST; no run_id)

All S3 families MUST key by:

* `manifest_fingerprint`
* `seed`
* `scenario_id`
* (recommended) `parameter_hash`

Then add decision-specific ids.

### 6.1 Activation keying (instances)

Decision ids:

* `ACTIVATE_TEMPLATE` (draw instance count)
* `SCHEDULE_START` (optional; only if schedule has random start)
* `WINDOW_SELECT` (optional; if multi-window stochastic)

Key ids MUST include:

* `template_id` for activation decisions
* `campaign_id` for per-instance schedule decisions (if any)

### 6.2 Targeting keying (target selection)

Decision ids:

* `SELECT_TARGET` (one draw per target pick)
* `QUOTA_REALISATION` (if quota is stochastic; v1 recommended deterministic quotas)

Key ids MUST include:

* `campaign_id`
* `target_index` (0-based within the campaign instance)
* if selection is by window: include `window_index`

### 6.3 Mutation keying (overlay)

Decision ids:

* `SELECT_TACTIC` (if mixture selection)
* `APPLY_MUTATION_PARAM` (amount factor, time factor, etc.)
* `SELECT_SWAP_CANDIDATE` (device/ip/instrument swap)
* `SELECT_ROUTING_ANOMALY` (site/edge shift)

Key ids MUST include:

* `campaign_id`
* `target_id` (stable identifier of the targeted item: entity_id or flow_id or event_id)
* `mutation_step_index` (0-based if multiple mutations per target)
* `tactic_id` when applicable

---

## 7) Emission obligations (MUST)

To make auditing possible:

* **Activation:** emit exactly one activation RNG event per `(scenario_id, template_id)` when activation model is stochastic; otherwise emit non-consuming envelope if policy requires event emission for audit.
* **Targeting:** emit exactly one targeting RNG event per target pick when candidate_count>1; if candidate_count<=1 emit non-consuming envelope.
* **Mutation:** emit exactly one mutation RNG event per mutation decision locus (tactic select, swap select, parameter draw) when stochastic; otherwise non-consuming.

No loops with variable draw counts are allowed (no rejection sampling).

---

## 8) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be 1)
2. `policy_id` (string; MUST be `fraud_rng_policy_6B`)
3. `policy_version` (string; MUST be `v1`)
4. `rng_profile_ref` (object)
5. `families` (list)
6. `keying` (object)
7. `sampling_primitives` (object)
8. `emission_rules` (object)
9. `guardrails` (object)
10. `notes` *(optional)*

Unknown keys ⇒ INVALID.

---

## 9) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
policy_id: fraud_rng_policy_6B
policy_version: v1

rng_profile_ref:
  policy_id: rng_profile_layer3
  required: true

families:
  - family_id: rng_event_campaign_activation
    decisions:
      - decision_id: ACTIVATE_TEMPLATE
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, template_id]
      - decision_id: SCHEDULE_START
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, campaign_id]

  - family_id: rng_event_campaign_targeting
    decisions:
      - decision_id: SELECT_TARGET
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, campaign_id, window_index, target_index]
      - decision_id: QUOTA_REALISATION
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, campaign_id]

  - family_id: rng_event_overlay_mutation
    decisions:
      - decision_id: SELECT_TACTIC
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, campaign_id, target_id, mutation_step_index]
      - decision_id: APPLY_MUTATION_PARAM
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, campaign_id, target_id, tactic_id, mutation_step_index]
      - decision_id: SELECT_SWAP_CANDIDATE
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, campaign_id, target_id, tactic_id, mutation_step_index]
      - decision_id: SELECT_ROUTING_ANOMALY
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, campaign_id, target_id, tactic_id, mutation_step_index]

keying:
  forbid_run_id_in_key: true
  decision_id_field: decision_id
  target_id_format: "stable opaque id (entity_id|flow_id|event_id)"
  indices_are_zero_based: true

sampling_primitives:
  discrete_choice_draws: "1"
  forbid_rejection_sampling: true
  forbid_variable_draws_per_locus: true

emission_rules:
  require_non_consuming_envelopes_when_deterministic: true
  forbid_unknown_families: true
  forbid_data_dependent_budget_variation: true

guardrails:
  max_mutation_steps_per_target: 4
  max_target_picks_per_campaign_instance: 200000
```

---

## 10) Acceptance checklist (MUST)

1. Contract pins match (`mlr.6B.policy.fraud_rng_policy`, correct path/schema_ref).
2. Families include exactly the three S3 families named in S3 spec.
3. Budgets are fixed per locus, and non-consuming envelopes are allowed/required where deterministic.
4. Keying includes mf/seed/scenario and forbids `run_id`.
5. No rejection sampling or outcome-dependent loops.
6. Guardrails prevent runaway target picks/mutations.

---

## Non-toy/realism guardrails (MUST)

- Only the three S3 families are allowed; any extra family is invalid.
- Budgets are fixed per locus (`draws` 0/1) and must not depend on outcomes.
- Campaign counts/targets must be inferable from configs; no rejection sampling loops.
- Keying must exclude `run_id` and follow the substream basis in the policy.

