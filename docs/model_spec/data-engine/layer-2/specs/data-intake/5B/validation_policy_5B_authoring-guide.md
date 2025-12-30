# Authoring Guide — `validation_policy_5B` (5B.S5 HashGate validations + realism checks)

## 0) Purpose

`validation_policy_5B` is the **sealed authority** for what 5B.S5 must validate before emitting:

* `validation_bundle_5B` + `_passed.flag_5B`

It pins:

* required upstream PASS gates,
* structural invariants across S1–S4 outputs,
* RNG accounting invariants against `arrival_rng_policy_5B`,
* realism corridors (non-toy sanity for λ, counts, timestamps, routing),
* and fail/abort thresholds.

S5 MUST treat this as the only authority for validations (no ad-hoc checks).

---

## 1) File identity (MUST)

* **Artefact ID:** `validation_policy_5B`
* **Path:** `config/layer2/5B/validation_policy_5B.yaml`
* **Schema anchor:** `schemas.5B.yaml#/policy/validation_policy_5B` *(permissive; this guide pins real structure)*
* **Token-less posture:** do **not** embed digests/timestamps; S0 sealing inventory handles digests.

---

## 2) Required top-level structure (fields-strict by this guide)

Top-level YAML object with **exactly**:

1. `policy_id` (MUST be `validation_policy_5B`)
2. `version` (non-placeholder, e.g. `v1.0.0`)
3. `require_upstream_pass` (object)
4. `structural_checks` (object)
5. `rng_accounting_checks` (object)
6. `realism_checks` (object)
7. `failure_policy` (object)

No extra keys.

---

## 3) Upstream gate requirements (MUST)

`require_upstream_pass` MUST contain:

```yaml
require_upstream_pass:
  layer1_required: [1A, 1B, 2A, 3A, 3B]
  layer2_required: [5A]
  optional: [2B]   # conditional: required if any physical routing occurs (see routing_realism)
```

Pinned meaning:

* S5 MUST verify `_passed.flag` hashes for required segments before reading their egress.
* If any arrival is routed physically (NON_VIRTUAL, or HYBRID with a physical outcome), then 2B MUST be present and PASS-gated.

---

## 4) Structural checks (MUST)

`structural_checks` MUST include:

### 4.1 S1 time grid integrity

```yaml
s1_time_grid:
  require_bucket_index_contiguous: true
  require_half_open_intervals: true
  require_duration_seconds_matches_policy: true
  max_buckets_per_scenario: 200000
```

### 4.2 S2 realised intensity integrity

```yaml
s2_realised_intensity:
  require_nonnegative_lambda: true
  require_finite_lambda: true
  require_lambda_zero_implies_count_zero: true
  max_lambda_realised: 1000000000.0
```

### 4.3 S3 bucket count integrity

```yaml
s3_bucket_counts:
  require_integer_counts: true
  require_counts_nonnegative: true
  max_count_per_bucket: 200000
  require_no_rng_event_when_lambda_zero: true
```

### 4.4 S4 arrival events integrity

```yaml
s4_arrival_events:
  require_event_time_in_bucket: true
  require_time_half_open: true
  require_sorted_within_bucket: true
  require_exactly_N_events_per_bucket: true
  require_routing_keys_present: true
```

---

## 5) RNG accounting checks (MUST)

These checks reconcile emitted RNG events/logs with the pinned budgets from `arrival_rng_policy_5B`.

`rng_accounting_checks` MUST include:

### 5.1 Stream counter monotonicity

```yaml
streams:
  require_monotonic_counters: true
  require_next_before_equals_prev_after: true
  forbid_counter_overlap: true
  abort_on_wrap: true
```

### 5.2 Family budget checks

```yaml
budgets:
  s2_latent_vector:
    require_one_event_per_group_when_enabled: true
    draws_u64_expected: "2H"     # symbolic; H from time grid
  s3_bucket_count:
    poisson_draws_u64: 1
    nb2_draws_u64: 2
    require_no_event_when_deterministic_zero: true
  s4_time_jitter_draws_u64: 1
  s4_site_pick_draws_u64: 2
  s4_edge_pick_draws_u64: 1
```

### 5.3 Trace/log completeness (if you keep audit/trace logs)

```yaml
trace:
  require_trace_row_per_rng_event: true
  require_append_after_each_event: true
```

---

## 6) Realism checks (MUST; non-toy)

These are “world plausibility” corridors. They do not change generation; they only PASS/FAIL.

### 6.1 Intensity factor plausibility (if LGCP enabled)

```yaml
lgcp_realism:
  require_mean_factor_near_one: true
  mean_factor_abs_tol: 0.05
  require_factor_bounds_respected: true
  min_factor: 0.20
  max_factor: 5.00
```

### 6.2 Count distribution sanity

```yaml
count_realism:
  require_nontrivial_nonzero_fraction: true
  min_nonzero_bucket_fraction: 0.01
  require_heavy_tail: true
  p99_p50_ratio_min: 4.0
```

### 6.3 Timestamp micro-placement sanity

```yaml
time_realism:
  require_not_all_at_bucket_start: true
  min_distinct_offsets_per_1000_events: 50
```

### 6.4 Routing sanity

```yaml
routing_realism:
  require_2B_pass_if_physical_present: true
  require_physical_and_virtual_coverage_when_present: true
  require_no_missing_alias_rows: true
  require_country_mix_close_if_virtual: true
  ip_country_max_abs_dev: 0.05
```

Pinned meaning:
* If any arrival is routed physically (NON_VIRTUAL, or HYBRID where the coin selects physical at least once), then 2B MUST be present in the manifest and PASS-gated. If no physical routing occurs in the run, 2B may be absent.

---

## 7) Failure policy (MUST)

Pin whether checks are hard-fail or warn-only. v1 is fail-closed:

```yaml
failure_policy:
  mode: fail_closed
  max_warnings: 0
```

---

## 8) Recommended v1 file (copy/paste baseline)

```yaml
policy_id: validation_policy_5B
version: v1.0.0

require_upstream_pass:
  layer1_required: [1A, 1B, 2A, 3A, 3B]
  layer2_required: [5A]
  optional: [2B]   # conditional: required if any physical routing occurs (see routing_realism)

structural_checks:
  s1_time_grid:
    require_bucket_index_contiguous: true
    require_half_open_intervals: true
    require_duration_seconds_matches_policy: true
    max_buckets_per_scenario: 200000
  s2_realised_intensity:
    require_nonnegative_lambda: true
    require_finite_lambda: true
    require_lambda_zero_implies_count_zero: true
    max_lambda_realised: 1000000000.0
  s3_bucket_counts:
    require_integer_counts: true
    require_counts_nonnegative: true
    max_count_per_bucket: 200000
    require_no_rng_event_when_lambda_zero: true
  s4_arrival_events:
    require_event_time_in_bucket: true
    require_time_half_open: true
    require_sorted_within_bucket: true
    require_exactly_N_events_per_bucket: true
    require_routing_keys_present: true

rng_accounting_checks:
  streams:
    require_monotonic_counters: true
    require_next_before_equals_prev_after: true
    forbid_counter_overlap: true
    abort_on_wrap: true
  budgets:
    s2_latent_vector:
      require_one_event_per_group_when_enabled: true
      draws_u64_expected: "2H"
    s3_bucket_count:
      poisson_draws_u64: 1
      nb2_draws_u64: 2
      require_no_event_when_deterministic_zero: true
    s4_time_jitter_draws_u64: 1
    s4_site_pick_draws_u64: 2
    s4_edge_pick_draws_u64: 1
  trace:
    require_trace_row_per_rng_event: true
    require_append_after_each_event: true

realism_checks:
  lgcp_realism:
    require_mean_factor_near_one: true
    mean_factor_abs_tol: 0.05
    require_factor_bounds_respected: true
    min_factor: 0.20
    max_factor: 5.00
  count_realism:
    require_nontrivial_nonzero_fraction: true
    min_nonzero_bucket_fraction: 0.01
    require_heavy_tail: true
    p99_p50_ratio_min: 4.0
  time_realism:
    require_not_all_at_bucket_start: true
    min_distinct_offsets_per_1000_events: 50
routing_realism:
  require_2B_pass_if_physical_present: true
  require_physical_and_virtual_coverage_when_present: true
  require_no_missing_alias_rows: true
  require_country_mix_close_if_virtual: true
  ip_country_max_abs_dev: 0.05

failure_policy:
  mode: fail_closed
  max_warnings: 0
```

---

## 9) Acceptance checklist (Codex MUST enforce)

1. YAML parses; keys exactly as §2; `policy_id` correct; version non-placeholder.
2. Upstream gate list matches 5B.S0 requirements and is enforced in S5.
3. Structural checks cover S1–S4 outputs and use the same max bounds as generation configs.
4. RNG checks match `arrival_rng_policy_5B` budgets and enforce monotonic counters.
5. Realism checks are non-toy but not impossibly strict.
6. Failure mode is fail-closed (v1).
7. No digests/timestamps embedded.

---

## Placeholder resolution (MUST)

- Replace `policy_id` and `version` with final identifiers.
- Replace `require_upstream_pass` lists with the actual required segments.
- Set `structural_checks`, `rng_accounting_checks`, and `realism_checks` thresholds to final values.

