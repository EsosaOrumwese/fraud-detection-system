# Authoring Guide — `behaviour_config_6B` (optional feature flags & guardrails, v1)

## 0) Purpose

`behaviour_config_6B` is an **optional, sealed control-plane pack** that lets you **narrow** or **disable** parts of 6B behaviour *without changing code*.

It is intended for:

* feature flags (enable/disable specific sub-features in S1–S5),
* scoping (restrict to certain `scenario_id`s / seeds / campaign types for a run),
* guardrails (caps and “fail-closed vs degrade” posture for optional behaviours).

If present, it MUST be:

* **registered + schema-referenced** and **sealed by S0** (digest recorded in `sealed_inputs_6B`).
  If absent, 6B MUST behave as if it were `enabled_all + no_filters` (i.e., ignore it safely). 

---

## 1) Contract identity (MUST)

From your 6B dictionary/registry:

* **dataset_id:** `behaviour_config_6B` (status: `optional`) 
* **manifest_key:** `mlr.6B.policy.behaviour_config` 
* **path:** `config/layer3/6B/behaviour_config_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/behaviour_config_6B`
* **consumed_by:** `6B.S0–6B.S5` 

**Sealing rule:** If used, S0 MUST include it in the S0 contract/config set and record `sha256_hex` in `sealed_inputs_6B`.

**Schema requirement (MUST):** `schemas.6B.yaml#/policy/behaviour_config_6B` MUST exist (even as a placeholder `type: object`) so S0 can schema-validate this file. Missing anchor -> S0 must FAIL CLOSED.

---

## 2) Authority boundary (critical)

This config is **restrictive only**:

* It MAY **disable** features or **narrow** domains (e.g., allow-list scenarios).
* It MUST NOT introduce new behaviours outside what other 6B policies already define.

Pinned rule:

* **Effective behaviour** = (other policy semantics) ∩ (behaviour_config allow/enable flags)

So it’s always safe: you can’t “turn on a new campaign type” here—only allow/disable campaign types that already exist in `fraud_campaign_catalogue_config_6B`, etc.

---

## 3) Required structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `config_id` (string; MUST be `behaviour_config_6B`)
3. `config_version` (string; MUST be `v1`)
4. `scope_filters` (object)
5. `feature_flags` (object)
6. `guardrails` (object)
7. `degrade_posture` (object)
8. `notes` (optional string)

Unknown keys ⇒ **INVALID** (fail closed at S0). 

Token-less rules:

* no timestamps (`generated_at`), no digests, no UUIDs in-file.

---

## 4) Semantics

### 4.1 `scope_filters`

Restricts what partitions S1–S5 will process (without changing the underlying arrivals/entities).

Recommended fields (all OPTIONAL; default is “no restriction”):

* `scenario_id_allowlist` (list[string])
* `scenario_id_blocklist` (list[string])
* `seed_allowlist` (list[int])
* `seed_blocklist` (list[int])
* `campaign_type_allowlist` (list[string]) *(S3/S4 scope only)*
* `campaign_type_blocklist` (list[string])

Rules:

* allowlist and blocklist MUST NOT overlap (hard invalid).
* If allowlist is present, only those values are in-scope; blocklist is then redundant and MUST be empty.

### 4.2 `feature_flags`

A per-state set of toggles. All OPTIONAL; default is “enabled”.

#### S1 flags

* `enable_attachment_steps` (map step→bool), steps in:

  * `ATTACH_PARTY`, `ATTACH_ACCOUNT`, `ATTACH_INSTRUMENT`, `ATTACH_DEVICE`, `ATTACH_IP`
* `enable_sessionisation` (bool)
* `enable_stochastic_session_boundary` (bool)

Pinned degrade rules:

* If a step is disabled, S1 MUST emit the corresponding columns as NULL / sentinel, but MUST still emit rows with stable keys.
* If sessionisation is disabled, S1 MUST treat each arrival as its own session (deterministic). 

#### S2 flags

* `enable_multi_flow_sessions` (bool)
* `enable_refunds` (bool)
* `enable_reversals` (bool)
* `enable_partial_clearing` (bool)
* `allowed_flow_types` (list[string]) *(restrictive; must be subset of flow vocab in `flow_shape_policy_6B`)*

#### S3 flags

* `enable_fraud_overlay` (bool)
* `allowed_campaign_types` (list[string]) *(subset of campaign config vocab)*
* `allowed_tactic_types` (list[string]) *(subset of overlay policy vocab)*

#### S4 flags

* `enable_truth_labelling` (bool) *(normally true; disabling is for dev only)*
* `enable_bank_view` (bool)
* `enable_cases` (bool)
* `enable_delays` (bool)

#### S5 flags

* `validation_scope_mode` ∈ `{FULL, SCOPED}`
* If `SCOPED`: `validation_scope` may restrict which scenarios/campaigns are required for coverage checks **only if** `segment_validation_policy_6B` marks those checks as WARN/INFO. REQUIRED checks must remain REQUIRED.

### 4.3 `guardrails`

Hard caps that prevent runaway outputs.

Recommended (all OPTIONAL; defaults are “no additional cap beyond other policies”):

* `max_sessions_per_seed_scenario`
* `max_flows_per_session`
* `max_events_per_flow`
* `max_campaigns_active_per_day`
* `max_cases_per_seed_scenario`

Rule:

* If a cap is hit, the behaviour must follow `degrade_posture` (next).

### 4.4 `degrade_posture`

Defines “what happens when optional features/caps collide”.

Required keys:

* `on_scope_filter_miss` ∈ `{SKIP_PARTITION, FAIL}`
* `on_guardrail_exceeded` ∈ `{CLAMP_AND_WARN, FAIL}`
* `on_optional_policy_missing` ∈ `{DISABLE_FEATURE, FAIL}`

Must align with S0/Sx required vs optional rules: optional artefacts missing should degrade, not crash, unless explicitly set to FAIL.

---

## 5) Minimal v1 example (safe, realistic defaults)

```yaml
schema_version: 1
config_id: behaviour_config_6B
config_version: v1

scope_filters:
  scenario_id_allowlist: []
  scenario_id_blocklist: []
  seed_allowlist: []
  seed_blocklist: []
  campaign_type_allowlist: []
  campaign_type_blocklist: []

feature_flags:
  s1:
    enable_attachment_steps:
      ATTACH_PARTY: true
      ATTACH_ACCOUNT: true
      ATTACH_INSTRUMENT: true
      ATTACH_DEVICE: true
      ATTACH_IP: true
    enable_sessionisation: true
    enable_stochastic_session_boundary: false

  s2:
    enable_multi_flow_sessions: true
    enable_refunds: true
    enable_reversals: true
    enable_partial_clearing: true
    allowed_flow_types: []

  s3:
    enable_fraud_overlay: true
    allowed_campaign_types: []
    allowed_tactic_types: []

  s4:
    enable_truth_labelling: true
    enable_bank_view: true
    enable_cases: true
    enable_delays: true

  s5:
    validation_scope_mode: FULL
    validation_scope: {}

guardrails:
  max_flows_per_session: 20
  max_events_per_flow: 40
  max_cases_per_seed_scenario: 50000

degrade_posture:
  on_scope_filter_miss: SKIP_PARTITION
  on_guardrail_exceeded: CLAMP_AND_WARN
  on_optional_policy_missing: DISABLE_FEATURE

notes: >
  Optional behaviour config. Empty allowlists mean "no restriction".
  Guardrails add safety caps; primary semantics still come from 6B policy packs.
```

---

## 6) Acceptance checklist (MUST)

1. File is token-less; YAML parses; unknown keys absent.
2. `config_id == behaviour_config_6B`, `config_version == v1`. 
3. Any allowlist/blocklist pairs do not overlap; allowlist + blocklist not both non-empty for same axis.
4. Any enumerations used here (attachment steps, etc.) match the consuming policies (S1/S2/S3/S4) and do not introduce new vocab.
5. If present, S0 seals it (digest in `sealed_inputs_6B`) and downstream states consult it only via `sealed_inputs_6B` (no ad-hoc paths).

---
