# Authoring Guide — `timing_policy_6B` (S2 intra-session + intra-flow time offsets, v1)

## 0) Purpose

`timing_policy_6B` is the **required** policy that defines how **6B.S2** assigns event timestamps (UTC + optional local) for baseline flows by sampling **time offsets** inside:

* the **session window** defined by S1 (`session_start_utc`, `session_end_utc`)
* the **arrival anchors** (arrival timestamps) used to create flows/events
* the **event templates** defined by `flow_shape_policy_6B`

This policy pins:

* which events are anchored to arrival time vs offset from prior events,
* the allowed delay distributions for event-to-event timing (auth→clear, auth→refund, auth retries, step-up),
* “no time travel” constraints (monotone per flow),
* guardrails (max flow duration, max inter-event gaps).

All randomness is via `flow_rng_policy_6B`; this policy defines decision points and distribution parameters only.

---

## 1) Contract identity (MUST)

From 6B contracts:

* **dataset_id:** `timing_policy_6B`
* **manifest_key:** `mlr.6B.policy.timing_policy`
* **path:** `config/layer3/6B/timing_policy_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/timing_policy_6B`
* **consumed_by:** `6B.S0`, `6B.S2`

Token-less posture:

* no timestamps, UUIDs, or digests in-file (sealed via S0).

---

## 2) Dependencies (MUST)

This policy is applied in S2 and depends on sealed inputs:

* `flow_shape_policy_6B` (event templates + branch semantics)
* S1 outputs: `s1_session_index_6B` and arrival timestamps (from arrival entities table)
* `flow_rng_policy_6B` (RNG family/budget for timing draws)
* `rng_profile_layer3` (open-interval law, normal primitive if used by timing distributions)

Hard rule:

* Timing cannot consult future states (S3/S4). It must be determined from S1+S2 context only.

---

## 3) What the policy must specify

### 3.1 Anchoring rule

For each flow/event, define whether:

* anchored to an **arrival timestamp** (common for AUTH_REQUEST), or
* anchored to a **prior event time** (common for CLEARING, STEP_UP_COMPLETE), or
* anchored to a **session boundary** (rare; optional).

### 3.2 Offset distributions

For each event transition, define:

* a distribution for `Δt_seconds ≥ 0`
* any context conditioning (channel_group, flow_type)
* guardrails (cap, min)

### 3.3 Monotonicity

Per flow:

* event times MUST be non-decreasing in `event_seq`.
* if the policy proposes a negative time or violates monotonicity, S2 must FAIL (v1) rather than silently reorder.

---

## 4) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be 1)
2. `policy_id` (string; MUST be `timing_policy_6B`)
3. `policy_version` (string; MUST be `v1`)
4. `bindings` (object)
5. `time_units` (object)
6. `anchor_rules` (object)
7. `offset_models` (object)
8. `composition_rules` (object)
9. `guardrails` (object)
10. `realism_targets` (object)
11. `notes` *(optional string)*

Unknown keys ⇒ INVALID.
No YAML anchors/aliases. Token-less.

---

## 5) Bindings (MUST)

`bindings` MUST include:

* `channel_groups` (allowed set)
* `event_type_vocab` (must match flow shape policy)
* `rng_family_for_timing_draw` (e.g., `rng_event_timing_offset`)
* `rng_family_for_anchor_jitter` (optional; e.g., `rng_event_arrival_jitter`)
* `no_run_id_in_key: true`

---

## 6) Time units (MUST)

`time_units` MUST pin:

* `timestamp_resolution`: `microsecond` (consistent with 5B and 6B schemas)
* `offset_unit`: `seconds`
* `min_positive_offset_seconds`: e.g., `0.0` or `0.001` (if you want strictly increasing time)

---

## 7) Anchor rules (MUST)

Define per event_type how the event timestamp is anchored.

Minimum v1 anchored model (recommended):

* `AUTH_REQUEST`: anchor to `arrival_ts_utc` (plus optional micro-jitter)
* `AUTH_RESPONSE`: anchor to `AUTH_REQUEST` + `Δ_auth_response`
* `CLEARING`: anchor to `AUTH_REQUEST` + `Δ_auth_to_clear`
* `STEP_UP_CHALLENGE`: anchor to `AUTH_REQUEST` + `Δ_step_up_start`
* `STEP_UP_COMPLETE`: anchor to `STEP_UP_CHALLENGE` + `Δ_step_up_complete`
* `REFUND`: anchor to `CLEARING` + `Δ_clear_to_refund`
* `REVERSAL`: anchor to `AUTH_REQUEST` + `Δ_auth_to_reversal`

If an event template includes types not declared here, S2 must FAIL (policy incomplete).

---

## 8) Offset models (MUST)

### 8.1 Supported distribution IDs (v1 pinned set)

To keep it auditable, v1 supports only:

* `EXPONENTIAL_V1` (rate λ; support ≥0)
* `LOGNORMAL_V1` (mu_log, sigma_log; support >0)
* `GAMMA_V1` (shape k, scale θ; support ≥0)
* `DISCRETE_POINTS_V1` (explicit seconds points + probs)

Any other dist id ⇒ invalid.

### 8.2 Required transitions

For v1, define at least these transition keys:

* `Δ_auth_response_seconds`
* `Δ_step_up_start_seconds`
* `Δ_step_up_complete_seconds`
* `Δ_auth_to_clear_seconds`
* `Δ_clear_to_refund_seconds`
* `Δ_auth_to_reversal_seconds`
* `Δ_auth_retry_gap_seconds` (if retry flow types exist)

Each transition model must define:

* `dist_id` and parameters
* `cap_seconds` (hard cap)
* `min_seconds` (>=0)
* `rng_family` (must equal `rng_family_for_timing_draw`)
* optional `by_channel_group` overrides

### 8.3 Deterministic if degenerate

If a distribution is a single point (e.g., DISCRETE_POINTS with one point prob=1), S2 must not consume RNG for that transition (non-consuming envelope allowed).

---

## 9) Composition rules (MUST)

These define how to combine offsets into event timestamps.

Required:

* `monotone_mode`: `nondecreasing` or `strictly_increasing`
* `strict_increase_epsilon_seconds` (required if strict)
* `if_violation`: `FAIL` (v1 pinned)

Also define:

* `arrival_jitter` (optional):

  * `enabled` (bool)
  * `jitter_microseconds_max` (int)
  * `rng_family` (if enabled; must be in `flow_rng_policy_6B` budgets)
  * rule: jitter is symmetric in `[-max, +max]`, applied to `AUTH_REQUEST` anchor only.

---

## 10) Guardrails (MUST)

Hard caps to prevent unrealistic timelines:

* `max_flow_duration_seconds` (int)
* `max_session_span_seconds` (int) *(must be consistent with sessionisation guardrail)*
* `max_inter_event_gap_seconds` (int)
* `max_refund_delay_seconds` (int)
* `max_clear_delay_seconds` (int)

If exceeded: v1 must FAIL (unless behaviour_config chooses clamp-and-warn; but baseline v1 should FAIL).

---

## 11) Realism targets (MUST)

Non-toy corridors, per channel_group:

* `auth_response_p50_seconds_range`
* `auth_to_clear_p50_seconds_range`
* `refund_delay_p50_seconds_range`
* `fraction_same_second_auth_and_response_max` (prevents all 0-latency)
* `fraction_clearing_same_day_min` (clearing mostly same day for card purchase, if that’s your worldview)

These are sanity checks the policy must satisfy and S5 may validate.

---

## 12) Minimal v1 example (copy/paste baseline)

```yaml
schema_version: 1
policy_id: timing_policy_6B
policy_version: v1

bindings:
  channel_groups: [ECOM, POS, ATM, BANK_RAIL, HYBRID]
  event_type_vocab: [AUTH_REQUEST, AUTH_RESPONSE, STEP_UP_CHALLENGE, STEP_UP_COMPLETE, CLEARING, REFUND, REVERSAL]
  rng_family_for_timing_draw: rng_event_timing_offset
  rng_family_for_anchor_jitter: rng_event_arrival_jitter
  no_run_id_in_key: true

time_units:
  timestamp_resolution: microsecond
  offset_unit: seconds
  min_positive_offset_seconds: 0.001

anchor_rules:
  AUTH_REQUEST: { anchor: ARRIVAL_TS_UTC, allow_jitter: true }
  AUTH_RESPONSE:{ anchor: PREV_EVENT, prev: AUTH_REQUEST, offset: Δ_auth_response_seconds }
  STEP_UP_CHALLENGE:{ anchor: PREV_EVENT, prev: AUTH_REQUEST, offset: Δ_step_up_start_seconds }
  STEP_UP_COMPLETE:{ anchor: PREV_EVENT, prev: STEP_UP_CHALLENGE, offset: Δ_step_up_complete_seconds }
  CLEARING: { anchor: EVENT, event: AUTH_REQUEST, offset: Δ_auth_to_clear_seconds }
  REFUND:   { anchor: EVENT, event: CLEARING,     offset: Δ_clear_to_refund_seconds }
  REVERSAL: { anchor: EVENT, event: AUTH_REQUEST, offset: Δ_auth_to_reversal_seconds }

offset_models:
  Δ_auth_response_seconds:
    dist_id: LOGNORMAL_V1
    mu_log: -0.40
    sigma_log: 0.55
    min_seconds: 0.02
    cap_seconds: 12.0
    rng_family: rng_event_timing_offset

  Δ_step_up_start_seconds:
    dist_id: LOGNORMAL_V1
    mu_log: 0.10
    sigma_log: 0.55
    min_seconds: 0.10
    cap_seconds: 60.0
    rng_family: rng_event_timing_offset

  Δ_step_up_complete_seconds:
    dist_id: LOGNORMAL_V1
    mu_log: 1.40
    sigma_log: 0.55
    min_seconds: 1.0
    cap_seconds: 300.0
    rng_family: rng_event_timing_offset

  Δ_auth_to_clear_seconds:
    dist_id: GAMMA_V1
    shape_k: 2.0
    scale_theta: 1800.0      # mean 3600s
    min_seconds: 60.0
    cap_seconds: 172800.0    # 2 days
    rng_family: rng_event_timing_offset
    by_channel_group:
      ATM:
        shape_k: 1.5
        scale_theta: 900.0
        min_seconds: 30.0
        cap_seconds: 43200.0

  Δ_clear_to_refund_seconds:
    dist_id: GAMMA_V1
    shape_k: 1.2
    scale_theta: 86400.0     # mean ~1 day
    min_seconds: 300.0
    cap_seconds: 7776000.0   # 90 days
    rng_family: rng_event_timing_offset

  Δ_auth_to_reversal_seconds:
    dist_id: EXPONENTIAL_V1
    rate_lambda: 0.001
    min_seconds: 10.0
    cap_seconds: 86400.0
    rng_family: rng_event_timing_offset

composition_rules:
  monotone_mode: strictly_increasing
  strict_increase_epsilon_seconds: 0.001
  if_violation: FAIL

  arrival_jitter:
    enabled: true
    jitter_microseconds_max: 200000     # +/- 0.2s
    rng_family: rng_event_arrival_jitter
    mode: symmetric_uniform

guardrails:
  max_flow_duration_seconds: 15552000        # 180 days
  max_inter_event_gap_seconds: 7776000       # 90 days
  max_clear_delay_seconds: 172800            # 2 days
  max_refund_delay_seconds: 7776000          # 90 days

realism_targets:
  auth_response_p50_seconds_range:
    ECOM: { min: 0.05, max: 2.0 }
    POS:  { min: 0.05, max: 1.5 }
    ATM:  { min: 0.05, max: 2.0 }
  auth_to_clear_p50_seconds_range:
    ECOM: { min: 900.0, max: 21600.0 }
    POS:  { min: 900.0, max: 21600.0 }
    ATM:  { min: 60.0,  max: 7200.0 }
  refund_delay_p50_seconds_range:
    ECOM: { min: 3600.0, max: 1209600.0 }
    POS:  { min: 3600.0, max: 1209600.0 }
  fraction_same_second_auth_and_response_max: 0.40
  fraction_clearing_same_day_min: 0.70
```

---

## 13) Acceptance checklist (MUST)

1. Contract pins match (path + schema_ref + manifest_key).
2. All event types referenced exist in `flow_shape_policy_6B` vocab.
3. All stochastic draws reference RNG families budgeted by `flow_rng_policy_6B`.
4. Monotonicity policy is explicit and enforced (v1: FAIL on violation).
5. Guardrails prevent runaway timelines.
6. Token-less YAML; no anchors/aliases; unknown keys invalid.

---
