# Authoring Guide — `delay_models_6B` (S4 delay distributions, v1)

## 0) Purpose

`delay_models_6B` is the **required** S4 control-plane pack that defines **all stochastic delay distributions** used when S4 simulates:

* detection delays (post-auth),
* dispute delays,
* chargeback delays/outcome timing,
* case close / investigation delays (if modelled).

S4 explicitly treats `delay_models_6B` as a required policy pack and uses it together with `truth_labelling_policy_6B`, `bank_view_policy_6B`, `case_policy_6B`, and `label_rng_policy_6B`. 

---

## 1) File identity

Your S4 spec notes the *names are indicative and must match your contract files*, so wire these to whatever your `contracts_6B` says; the recommended convention is:

* **Path:** `config/layer3/6B/delay_models_6B.yaml`
* **Schema anchor:** `schemas.6B.yaml#/policy/delay_models_6B` *(add anchor when you flesh out policy schemas)*
* **Sealing:** must be listed in `sealed_inputs_6B` with `status="REQUIRED"` and `sha256_hex` before S4 reads any data rows.

---

## 2) Dependency & RNG boundary

This file **does not** define RNG families/budgets. It only defines distributions and constraints.

* RNG families/budgets/keying for S4 delays are owned by `label_rng_policy_6B` (e.g., `rng_event_detection_delay`, `rng_event_dispute_delay`, `rng_event_chargeback_delay`, `rng_event_case_timeline`).
* S4 must be able to compute expected delay-draw counts deterministically from “how many flows require sampling”.

---

## 3) Required modelling rule (non-toy, audit-friendly)

To keep RNG accounting simple, **each delay sample MUST be representable with exactly one open-interval uniform** `u∈(0,1)` (via inverse-CDF or deterministic splitting/remapping for mixtures). No rejection sampling loops. This aligns with S4’s “draws implied by domain size” posture.

---

## 4) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be `1`)
2. `policy_id` (string; MUST be `delay_models_6B`)
3. `policy_version` (string; MUST be `v1`)
4. `time_units` (object)
5. `model_vocab` (object)
6. `delay_models` (list of objects)
7. `sampling_contract` (object)
8. `guardrails` (object)
9. `realism_targets` (object)
10. `notes` *(optional)*

Unknown keys ⇒ INVALID (fail closed).

Token-less: no timestamps / UUIDs / digests in-file.

---

## 5) `time_units` (MUST)

* `timestamp_resolution`: `microsecond`
* `delay_unit`: `seconds`
* `min_positive_delay_seconds`: e.g. `0.001` *(use 0.0 only if you explicitly allow same-instant outcomes)*

---

## 6) `model_vocab` (MUST)

Pin a small, auditable set of distribution ids (all **one-uniform samplable**):

* `EXPONENTIAL_QF_V1`
* `LOGNORMAL_QF_V1`
* `GAMMA_QF_V1`
* `DISCRETE_POINTS_V1`
* `POINT_MASS_PLUS_TAIL_V1`
* `MIXTURE_QF_V1`

---

## 7) `delay_models[]` (MUST)

Each model object MUST contain:

* `delay_model_id` (stable token, e.g. `DETECTION_DELAY_V1`)
* `applies_to` (enum):

  * `POST_AUTH_DETECTION`
  * `DISPUTE`
  * `CHARGEBACK`
  * `CASE_CLOSE`
  * *(you may add `INVESTIGATION_STEP` later; v1 keep small)*
* `anchor_kind` (enum; tells S4 what timestamp to offset from):

  * `AUTH_TS`, `CLEARING_TS`, `DISPUTE_TS`, `DETECTION_TS`, `CASE_OPEN_TS`
* `dist` (object; one of the `model_vocab` ids + params)
* `min_seconds`, `max_seconds` (hard bounds; S4 must FAIL if a draw lands outside after mapping)
* `rng_family` + `decision_id` (referential only; must match `label_rng_policy_6B` family names)
* `notes` (optional)

### v1 required model ids (recommended)

These match what your `bank_view_policy_6B` and `case_policy_6B` will reference:

* `DETECTION_DELAY_V1` (POST_AUTH_DETECTION; anchor `AUTH_TS`)
* `DISPUTE_DELAY_V1` (DISPUTE; anchor `CLEARING_TS` or `AUTH_TS` depending on your worldview)
* `CHARGEBACK_DELAY_V1` (CHARGEBACK; anchor `DISPUTE_TS`)
* `CASE_CLOSE_DELAY_V1` (CASE_CLOSE; anchor `CASE_OPEN_TS`)

S4 uses these delays when it does probabilistic/delayed detection and dispute/chargeback simulation.

---

## 8) `sampling_contract` (MUST)

* `draws_per_delay_sample`: `"1"`
* `forbid_rejection_sampling`: true
* `mixture_sampling`: must specify deterministic split/remap:

  * choose component by cumulative weights
  * remap u within component interval
  * apply component quantile
* `quantile_inputs_open_interval_only`: true

---

## 9) `guardrails` (MUST)

Hard caps (fail closed):

* `max_detection_delay_seconds`
* `max_dispute_delay_seconds`
* `max_chargeback_delay_seconds`
* `max_case_close_delay_seconds`

And sanity floors:

* `min_detection_delay_seconds` (if post-auth)
* `min_dispute_delay_seconds`
* `min_chargeback_delay_seconds`

---

## 10) `realism_targets` (MUST)

Corridors to enforce realism (non-toy):

* `p50_seconds_range` by delay_model_id
* `p95_seconds_range` by delay_model_id
* `heavy_tail_ratio_range` (e.g., p95/p50) by delay_model_id
* `presence_requirements` (booleans):

  * “detection delay is not almost always instantaneous”
  * “chargeback delays reach into weeks/months”

These are validated in S5 (segment validation) as part of behavioural realism and accounting. 

---

## 11) Minimal v1 example (starter)

```yaml
schema_version: 1
policy_id: delay_models_6B
policy_version: v1

time_units:
  timestamp_resolution: microsecond
  delay_unit: seconds
  min_positive_delay_seconds: 0.001

model_vocab:
  dist_ids:
    - EXPONENTIAL_QF_V1
    - LOGNORMAL_QF_V1
    - GAMMA_QF_V1
    - DISCRETE_POINTS_V1
    - POINT_MASS_PLUS_TAIL_V1
    - MIXTURE_QF_V1

delay_models:
  - delay_model_id: DETECTION_DELAY_V1
    applies_to: POST_AUTH_DETECTION
    anchor_kind: AUTH_TS
    rng_family: rng_event_detection_delay
    decision_id: detect_delay
    min_seconds: 1.0
    max_seconds: 1209600.0   # 14 days
    dist:
      dist_id: POINT_MASS_PLUS_TAIL_V1
      point_mass:
        seconds: 300.0        # 5 minutes
        prob: 0.25
      tail:
        dist_id: LOGNORMAL_QF_V1
        mu_log: 10.2
        sigma_log: 1.1

  - delay_model_id: DISPUTE_DELAY_V1
    applies_to: DISPUTE
    anchor_kind: CLEARING_TS
    rng_family: rng_event_dispute_delay
    decision_id: dispute_delay
    min_seconds: 3600.0
    max_seconds: 7776000.0   # 90 days
    dist:
      dist_id: LOGNORMAL_QF_V1
      mu_log: 12.0
      sigma_log: 1.0

  - delay_model_id: CHARGEBACK_DELAY_V1
    applies_to: CHARGEBACK
    anchor_kind: DISPUTE_TS
    rng_family: rng_event_chargeback_delay
    decision_id: chargeback_delay
    min_seconds: 86400.0
    max_seconds: 15552000.0  # 180 days
    dist:
      dist_id: MIXTURE_QF_V1
      components:
        - weight: 0.65
          dist: { dist_id: GAMMA_QF_V1, shape_k: 2.0, scale_theta: 604800.0 }   # mean ~14d
        - weight: 0.35
          dist: { dist_id: LOGNORMAL_QF_V1, mu_log: 13.2, sigma_log: 0.9 }      # longer tail

  - delay_model_id: CASE_CLOSE_DELAY_V1
    applies_to: CASE_CLOSE
    anchor_kind: CASE_OPEN_TS
    rng_family: rng_event_case_timeline
    decision_id: case_close_delay
    min_seconds: 3600.0
    max_seconds: 7776000.0   # 90 days
    dist:
      dist_id: GAMMA_QF_V1
      shape_k: 1.6
      scale_theta: 259200.0  # mean ~4.8d

sampling_contract:
  draws_per_delay_sample: "1"
  forbid_rejection_sampling: true
  quantile_inputs_open_interval_only: true

guardrails:
  max_detection_delay_seconds: 1209600.0
  max_dispute_delay_seconds: 7776000.0
  max_chargeback_delay_seconds: 15552000.0
  max_case_close_delay_seconds: 7776000.0

realism_targets:
  p50_seconds_range:
    DETECTION_DELAY_V1: { min: 60.0, max: 86400.0 }
    DISPUTE_DELAY_V1:   { min: 86400.0, max: 2592000.0 }
    CHARGEBACK_DELAY_V1:{ min: 604800.0, max: 7776000.0 }
    CASE_CLOSE_DELAY_V1:{ min: 3600.0, max: 1209600.0 }
  p95_seconds_range:
    DETECTION_DELAY_V1: { min: 3600.0, max: 1209600.0 }
    DISPUTE_DELAY_V1:   { min: 604800.0, max: 7776000.0 }
    CHARGEBACK_DELAY_V1:{ min: 2592000.0, max: 15552000.0 }
    CASE_CLOSE_DELAY_V1:{ min: 86400.0, max: 7776000.0 }
  heavy_tail_ratio_range:
    DETECTION_DELAY_V1: { min: 3.0, max: 200.0 }
    DISPUTE_DELAY_V1:   { min: 2.0, max: 100.0 }
    CHARGEBACK_DELAY_V1:{ min: 1.5, max: 50.0 }
    CASE_CLOSE_DELAY_V1:{ min: 2.0, max: 80.0 }
```

---

## 12) Acceptance checklist (MUST)

* S4 can find `delay_models_6B` in `sealed_inputs_6B` as a REQUIRED policy pack before reading rows.
* Each delay model is bounded (`min_seconds/max_seconds`) and one-uniform samplable (no rejection loops), matching S4’s accounting posture.
* All `rng_family` strings referenced here exist and are budgeted in `label_rng_policy_6B`. 
* Realism corridors are non-degenerate and satisfiable (delays are not all ~0, chargebacks have long tails). 

---
