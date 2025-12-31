# Authoring Guide — `segment_validation_policy_6B` (S5 checks, severities, thresholds, HashGate posture, v1)

## 0) Purpose

`segment_validation_policy_6B` is the **single authority** for what **6B.S5** must validate before emitting:

* `validation_bundle_6B/index.json`
* `validation_passed_flag_6B` (`_passed.flag`)

It defines:

* the **check inventory** (structural, behavioural, RNG accounting, realism),
* **severity** per check (`REQUIRED | WARN | INFO`),
* numeric **thresholds/corridors**,
* and the **sealing rule**: when WARN still permits PASS vs when any WARN should fail.

It must be strict enough that Codex cannot “pass” on a toy run, but flexible enough to tolerate harmless noise when flagged as WARN/INFO.

---

## 1) Contract identity (MUST)

From your 6B contracts:

* **dataset_id:** `segment_validation_policy_6B`
* **manifest_key:** `mlr.6B.policy.segment_validation_policy`
* **path:** `config/layer3/6B/segment_validation_policy_6B.yaml`
* **schema_ref:** `schemas.6B.yaml#/policy/segment_validation_policy_6B`
* **consumed_by:** `6B.S0`, `6B.S5`

Token-less posture:

* no timestamps/UUIDs/digests in-file; S0 seals bytes and records `sha256_hex` in `sealed_inputs_6B`.

---

## 2) Dependencies (MUST)

S5 validates across S0–S4 artefacts and their input seals. It must enforce **No PASS → No read** posture downstream.

This policy is authored assuming S5 can read:

* S0 `sealed_inputs_6B` + gate receipt,
* S1 attachment + sessions,
* S2 baseline flows/events,
* S3 campaign catalogue + with-fraud flows/events,
* S4 truth + bank view + cases,
* all RNG logs/traces referenced by the RNG policies.

---

## 3) Required YAML structure (fields-strict)

Top-level keys **exactly**:

1. `schema_version` (int; MUST be 1)
2. `policy_id` (string; MUST be `segment_validation_policy_6B`)
3. `policy_version` (string; MUST be `v1`)
4. `seal_rules` (object)
5. `check_groups` (list of objects)
6. `checks` (list of objects)
7. `thresholds` (object)
8. `rng_accounting` (object)
9. `realism_corridors` (object)
10. `reporting` (object)
11. `notes` *(optional)*

Unknown keys ⇒ INVALID.
No YAML anchors/aliases.

---

## 4) Seal rules (MUST)

`seal_rules` define how S5 converts check results into PASS/FAIL:

Required fields:

* `fail_on_any_required_failure: true`
* `fail_on_any_warn_failure` (bool; v1 recommended false)
* `warn_still_pass_max_fraction` (float in [0,1]) *(if fail_on_any_warn_failure=false)*
* `info_never_blocks_pass: true`
* `required_check_min_coverage` (float in (0,1]) *(fraction of expected partitions/events that must be checked; v1 recommended 1.0)*

Also define:

* `bundle_hashing_law` reference:

  * index.json ASCII-lex path order,
  * hash over raw bytes,
  * exclude `_passed.flag` from index.

---

## 5) Check inventory (MUST)

Checks are grouped for readability but each check is an explicit row in `checks[]`.

### 5.1 Required check groups (recommended)

* `UPSTREAM_GATES`
* `SCHEMA_AND_KEYS`
* `COVERAGE_PARITY`
* `RNG_ACCOUNTING`
* `TEMPORAL_INVARIANTS`
* `BEHAVIOURAL_REALISM`
* `FRAUD_REALISM`
* `BANK_VIEW_REALISM`
* `CASE_TIMELINE_REALISM`

---

## 6) Check definitions (MUST)

Each `checks[]` entry MUST include:

* `check_id` (stable token)
* `group_id` (must exist)
* `severity` ∈ `{REQUIRED, WARN, INFO}`
* `applies_to` (list of artefact ids or stage ids S0..S4)
* `expected_scope` (what partition axes it checks: e.g., per seed+scenario, per fingerprint)
* `method` (enum id; implementation references)
* `threshold_ref` (optional; points into `thresholds` or `realism_corridors`)
* `fail_message` (short)
* `notes` (optional)

---

## 7) Required check content (what v1 MUST include)

### 7.1 Upstream gates & sealing (REQUIRED)

* verify S0 sealed_inputs include all required policies with digests
* verify upstream HashGates for `{1A–3B, 5A, 5B, 6A}` were checked in S0 receipt (No PASS → No read)

### 7.2 Schema/PK/ordering invariants (REQUIRED)

* each produced dataset conforms to its schema anchors (or contract stubs)
* PK uniqueness:

  * S1: arrival_entities keyed correctly (no duplicates)
  * S2: flow_id uniqueness; event rows match flow rows
  * S3: with-fraud flow/event parity
  * S4: truth rows 1:1 with flows; bank view rows 1:1 with flows; case timeline keyed correctly

### 7.3 Coverage parity checks (REQUIRED)

* `s1_arrival_entities_6B` covers every `arrival_event_id` from 5B in-scope (no drops)
* `s2_flow_anchor_baseline_6B` flows cover all sessions (as per policy)
* `s2_event_stream_baseline_6B` covers all flows
* `s3_flow_anchor_with_fraud_6B` covers all baseline flows (no missing) and flags mutations correctly
* `s4_flow_truth_labels_6B` and `s4_flow_bank_view_6B` cover all with-fraud flows exactly once
* `s4_event_labels_6B` covers all with-fraud events exactly once

### 7.4 RNG accounting (REQUIRED)

* For each RNG policy (S1, S2, S3, S4):

  * all events belong to allowed families
  * `draws/blocks` match policy budgets and `rng_profile_layer3` law
  * trace log counters are consistent (before/after monotone)
* Expected event counts match:

  * S1: per-arrival × attachment steps + boundary decisions
  * S2: per session / per flow / per event slot decisions
  * S3: per template activation + per target + per mutation loci
  * S4: per ambiguous flow + per eligible flow delay/outcome + per case locus

### 7.5 Temporal invariants (REQUIRED)

* per flow: event timestamps monotone in `event_seq`
* within scenario horizon (all ts in [scenario_start, scenario_end))
* delays consistent with delay_models bounds (no negative, no overflow)
* bank timestamps consistent: detection/dispute/chargeback not before relevant anchor event

---

## 8) Thresholds (MUST)

`thresholds` is a structured object of numeric thresholds referenced by check entries.

v1 should include at least:

* `max_missing_fraction` (for WARN coverage checks)
* `max_duplicate_pk_count` (should be 0 for REQUIRED)
* `time_monotonicity_violation_max` (0 for REQUIRED)
* `scenario_oob_timestamp_max` (0 for REQUIRED)
* `rng_budget_violation_max` (0 for REQUIRED)

---

## 9) Realism corridors (MUST)

These are **behavioural** checks that prevent toy output. They are referenced by checks in `BEHAVIOURAL_REALISM`, `FRAUD_REALISM`, `BANK_VIEW_REALISM`, `CASE_TIMELINE_REALISM`.

Minimum recommended corridors:

### 9.1 Baseline behaviour (S2)

* flows-per-session distribution: non-degenerate (fraction multi-flow within range)
* decline/refund/reversal rates within ranges per channel_group
* amount heavy-tail ratios within ranges (from amount policy)

### 9.2 Fraud overlay (S3)

* campaign prevalence within ranges per campaign family
* mutation axis coverage (≥ N axes used)
* fraction of flows mutated within range

### 9.3 Truth/bank view (S4)

* fraud_fraction within range
* abuse_fraction within range
* detection rate ranges by truth_label/subtype
* false positive rate within range
* dispute/chargeback rates within range

### 9.4 Case realism

* case involvement fraction within range
* mean flows per case within range
* mean case duration within range
* chargeback case fraction within range

These corridors should default to `WARN` for early development, but to prevent toy outputs you should make a core subset `REQUIRED`.

---

## 10) RNG accounting section (MUST)

`rng_accounting` defines:

* list of RNG policies to validate: `[rng_policy_6B, flow_rng_policy_6B, fraud_rng_policy_6B, label_rng_policy_6B]`
* `require_non_consuming_envelopes_when_deterministic` (bool; should match the rng policies)
* reconciliation method:

  * verify `blocks` and `draws` fields per event match expectations
  * verify trace log counter continuity per substream

---

## 11) Reporting (MUST)

Defines what S5 emits in the validation bundle beyond `_passed.flag`:

* `validation_bundle_contents` list (paths expected in index.json)
* severity summary format
* whether WARN/INFO details are included in issue tables
* deterministic ordering of report sections

---

## 12) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
policy_id: segment_validation_policy_6B
policy_version: v1

seal_rules:
  fail_on_any_required_failure: true
  fail_on_any_warn_failure: false
  warn_still_pass_max_fraction: 0.02
  info_never_blocks_pass: true
  required_check_min_coverage: 1.0
  bundle_hashing_law: index_json_ascii_lex_raw_bytes_excluding_passed_flag

check_groups:
  - { group_id: UPSTREAM_GATES,         description: "Upstream HashGates and sealed inputs." }
  - { group_id: SCHEMA_AND_KEYS,        description: "Schema conformance, PK uniqueness, ordering." }
  - { group_id: COVERAGE_PARITY,        description: "1:1 coverage and parity across stages." }
  - { group_id: RNG_ACCOUNTING,         description: "RNG families/budgets/counter trace reconciliation." }
  - { group_id: TEMPORAL_INVARIANTS,    description: "Monotone timestamps, in-horizon, delay bounds." }
  - { group_id: BEHAVIOURAL_REALISM,    description: "Baseline realism corridors." }
  - { group_id: FRAUD_REALISM,          description: "Campaign/mutation realism corridors." }
  - { group_id: BANK_VIEW_REALISM,      description: "Detection/dispute/chargeback realism corridors." }
  - { group_id: CASE_TIMELINE_REALISM,  description: "Case volumes and durations realism corridors." }

checks:
  - check_id: REQ_UPSTREAM_HASHGATES
    group_id: UPSTREAM_GATES
    severity: REQUIRED
    applies_to: [S0]
    expected_scope: fingerprint
    method: verify_upstream_passed_flags_and_digests
    fail_message: "Upstream HashGate verification failed or missing."

  - check_id: REQ_PK_UNIQUENESS
    group_id: SCHEMA_AND_KEYS
    severity: REQUIRED
    applies_to: [S1, S2, S3, S4]
    expected_scope: seed_scenario
    method: pk_uniqueness_zero_duplicates
    threshold_ref: thresholds.max_duplicate_pk_count
    fail_message: "Duplicate primary keys detected."

  - check_id: REQ_FLOW_LABEL_COVERAGE
    group_id: COVERAGE_PARITY
    severity: REQUIRED
    applies_to: [S4]
    expected_scope: seed_scenario
    method: flow_truth_and_bankview_cover_all_flows_exactly_once
    fail_message: "Truth/bank view coverage mismatch for flows."

  - check_id: REQ_RNG_BUDGETS
    group_id: RNG_ACCOUNTING
    severity: REQUIRED
    applies_to: [S1, S2, S3, S4]
    expected_scope: seed_scenario
    method: rng_families_and_budgets_match_policies
    threshold_ref: thresholds.rng_budget_violation_max
    fail_message: "RNG budgets/families do not match policy."

thresholds:
  max_duplicate_pk_count: 0
  rng_budget_violation_max: 0
  time_monotonicity_violation_max: 0
  scenario_oob_timestamp_max: 0

rng_accounting:
  rng_policies_required:
    - rng_policy_6B
    - flow_rng_policy_6B
    - fraud_rng_policy_6B
    - label_rng_policy_6B
  require_non_consuming_envelopes_when_deterministic: true

realism_corridors:
  baseline:
    decline_rate_range_by_channel:
      ECOM: { min: 0.01, max: 0.25 }
      POS:  { min: 0.01, max: 0.20 }
    refund_rate_range_by_channel:
      ECOM: { min: 0.001, max: 0.10 }
  fraud:
    fraud_fraction_range: { min: 0.0005, max: 0.10 }
  bank_view:
    false_positive_rate_range: { min: 0.0005, max: 0.02 }
  cases:
    case_involvement_fraction_range: { min: 0.0005, max: 0.20 }

reporting:
  include_issue_table: true
  issue_table_max_rows: 20000
```

---

## 13) Acceptance checklist (MUST)

* Contract pins match (path + schema_ref + manifest_key).
* S5 enforces “No PASS → No read” by emitting `_passed.flag` only when required checks pass, using the bundle hashing law.
* RNG accounting checks reconcile all 4 RNG policies against the actual RNG logs (families, budgets, trace counters).
* Coverage parity checks ensure 1:1 flows/events across S2→S4 and that all arrivals are attached in S1.
* Realism corridors prevent toy output; at least a core subset are REQUIRED, not only WARN.
