# Authoring Guide — `label_rng_policy_6B` (S4 RNG families, budgets & keying, v1)

## 0) Purpose

`label_rng_policy_6B` is the **required RNG contract** for **6B.S4**. It defines:

* the **only RNG families** S4 may consume,
* fixed **`draws` / `blocks` budgets** per decision locus,
* the **keying scheme** for reproducible per-flow/per-case randomness,
* and emission obligations so S5 can validate RNG accounting.

S4 explicitly uses RNG for:

* truth ambiguity (if enabled),
* detection/dispute/chargeback delays/outcomes,
* case timeline stochasticity (if enabled).

If this policy is missing/invalid, S4 must fail preconditions and must not emit the S4 outputs.

---

## 1) Contract identity (MUST)

From the 6B contracts:

* **dataset_id:** `label_rng_policy_6B`
* **manifest_key:** `mlr.6B.policy.label_rng_policy`
* **path:** `config/layer3/6B/label_rng_policy_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/label_rng_policy_6B`
* **consumed_by:** `6B.S0`, `6B.S4`

Token-less posture:

* no timestamps/UUIDs/digests in-file; S0 sealing records `sha256_hex` in `sealed_inputs_6B`.

---

## 2) Dependencies (MUST)

Required:

* `rng_profile_layer3` (open-interval law; budget law `blocks=ceil(draws/2)`; substream derivation)
* `truth_labelling_policy_6B` (may require ambiguity draws)
* `bank_view_policy_6B` (decision ids for auth/detection/dispute/chargeback)
* `delay_models_6B` (delay models declare which family/decision_id they use)
* `case_policy_6B` (case stochastic splitting / close delay may require RNG)

Hard rule:

* `run_id` is log-only and MUST NOT be included in keying.

---

## 3) Family inventory (MUST)

v1 defines **exactly these S4 families**:

1. `rng_event_truth_label_ambiguity`
2. `rng_event_detection_delay`
3. `rng_event_dispute_delay`
4. `rng_event_chargeback_delay`
5. `rng_event_case_timeline`

S4 MUST NOT consume any family not listed here.

---

## 4) Deterministic budget law (MUST)

S4 RNG consumption must be inferable from:

* number of flows,
* whether flow is ambiguous (policy predicate),
* whether flow is eligible for detection/dispute/chargeback,
* whether the policy chooses to sample a delay/outcome,
* number of cases and whether case stochastic splitting/close-delay is enabled.

Therefore:

* each “decision locus” emits at most one consuming event with a fixed draw budget,
* deterministic loci emit non-consuming envelopes if `require_non_consuming_envelopes_when_deterministic=true`.

No rejection sampling or outcome-dependent loops.

---

## 5) Budgets per family (v1)

All families are **single-uniform** in v1:

* consuming: `draws="1"`, `blocks=1`
* non-consuming: `draws="0"`, `blocks=0`

This is compatible with:

* categorical choices (truth ambiguity),
* Bernoulli flags + quantile delays (delay models require 1 uniform),
* mixture choices via deterministic split/remap.

If any policy requires >1 uniform for a single locus, it must be decomposed into multiple loci, each with its own RNG event and decision_id.

---

## 6) Keying scheme (MUST; no run_id)

### 6.1 Common prefix (all families)

All S4 RNG events MUST key by:

* `manifest_fingerprint`
* `parameter_hash`
* `seed`
* `scenario_id` (for flow-level decisions)

### 6.2 Flow-level decisions

For decisions tied to a flow:

* include `flow_id`
* include `decision_id` (string literal; see below)

### 6.3 Case-level decisions

For decisions tied to a case:

* include `case_id` or `case_key_string` (as defined by case_policy)
* include `decision_id`
* include `case_event_index` or `case_index_within_key` as needed for uniqueness

### 6.4 Decision IDs (MUST match policies)

`decision_id` values must match those referenced in:

* truth policy ambiguity models (e.g., `"truth"`) 
* bank view policy (`auth_decision`, `detect_flag`, `detect_delay`, `dispute_flag`, `dispute_delay`, `chargeback_flag`, `chargeback_delay`, etc.)
* delay models (`detect_delay`, `dispute_delay`, `chargeback_delay`, `case_close_delay`)
* case policy (`case_split`, `case_close_delay`)

Hard rule:

* If a consuming policy references a decision_id not present in this RNG policy, S4 must fail preconditions.

---

## 7) Emission obligations (MUST)

### 7.1 Truth ambiguity

Emit `rng_event_truth_label_ambiguity` only when the truth policy marks a flow as ambiguous and defines a candidate distribution; otherwise non-consuming envelope allowed.

### 7.2 Detection/dispute/chargeback

For each flow:

* if eligible and model is stochastic:

  * emit the corresponding RNG event(s) with the appropriate decision_id
* if deterministic (prob 0 or 1, or degenerate delay):

  * emit non-consuming envelope if required.

### 7.3 Case timeline

Emit `rng_event_case_timeline` only when case policy enables stochastic splitting or stochastic close delay; otherwise non-consuming envelope allowed.

---

## 8) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be 1)
2. `policy_id` (string; MUST be `label_rng_policy_6B`)
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

## 9) Minimal v1 policy (copy/paste baseline)

```yaml
schema_version: 1
policy_id: label_rng_policy_6B
policy_version: v1

rng_profile_ref:
  policy_id: rng_profile_layer3
  required: true

families:
  - family_id: rng_event_truth_label_ambiguity
    decisions:
      - decision_id: truth
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, decision_id]

  - family_id: rng_event_detection_delay
    decisions:
      - decision_id: auth_decision
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, decision_id]
      - decision_id: detect_flag
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, decision_id]
      - decision_id: detect_at_auth_flag
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, decision_id]
      - decision_id: detect_delay
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, decision_id]

  - family_id: rng_event_dispute_delay
    decisions:
      - decision_id: dispute_flag
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, decision_id]
      - decision_id: dispute_delay
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, decision_id]

  - family_id: rng_event_chargeback_delay
    decisions:
      - decision_id: chargeback_flag
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, decision_id]
      - decision_id: chargeback_type
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, decision_id]
      - decision_id: chargeback_outcome
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, decision_id]
      - decision_id: chargeback_delay
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, scenario_id, flow_id, decision_id]

  - family_id: rng_event_case_timeline
    decisions:
      - decision_id: case_split
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, case_key_string, flow_id, decision_id]
      - decision_id: case_close_delay
        budgets: { consuming: { draws: "1", blocks: 1 }, non_consuming: { draws: "0", blocks: 0 } }
        key_ids: [manifest_fingerprint, parameter_hash, seed, case_id, decision_id]

keying:
  forbid_run_id_in_key: true
  indices_are_zero_based: true
  decision_id_field: decision_id

sampling_primitives:
  discrete_choice_draws: "1"
  delay_draws_per_sample: "1"
  forbid_rejection_sampling: true
  forbid_variable_draws_per_locus: true

emission_rules:
  require_non_consuming_envelopes_when_deterministic: true
  forbid_unknown_families: true
  forbid_data_dependent_budget_variation: true

guardrails:
  max_rng_events_per_flow: 32
  max_rng_events_per_case: 16
```

---

## 10) Acceptance checklist (MUST)

1. Contract pins match (`mlr.6B.policy.label_rng_policy`, correct path/schema_ref).
2. Families include the S4 families referenced by S4 spec and by the S4 policies (truth/bank/delay/case).
3. All consuming decisions are one-uniform (`draws="1"`, `blocks=1`), and non-consuming envelopes are supported.
4. Keying includes `(mf, ph, seed, scenario_id, flow_id, decision_id)` for per-flow decisions and forbids run_id.
5. If a policy references a decision_id not listed here, S4 must fail preconditions.
6. No rejection sampling or outcome-dependent loops.

---
