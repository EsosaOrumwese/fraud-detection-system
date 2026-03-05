# Dev Full Runtime Numeric Contract v0

## 0) Metadata
- Version: `v0`
- Status: `DRAFT`
- Track: `dev_full`
- Effective date: `TBD`
- Owner: `TBD`
- Supersedes: `none`
- Companion process doc: `TBD` (runtime certification procedure document)

---

## 1) Authority and Scope
This contract is the pass/fail numeric authority for runtime certification on `dev_full`.

Scope covered:
- ingress and control-plane handoff under declared injection path,
- streaming/data-plane throughput and stability,
- decision-path latency and error posture,
- state-store and archive behavior under load,
- data-realism and time-causality safety gates,
- cost-to-outcome and idle-safe posture.

Certification modes:
- `RC2-S` (required): operational envelope required for production-readiness claim.
- `RC2-L` (stretch): target envelope; non-blocking for `RC2-S` closure unless explicitly promoted.

Injection path declaration (mandatory):
- `via_IG` (end-to-end ingress path; required for full boundary claim),
- `via_MSK` (hot-path throughput claim only; does not certify IG ingress boundary by itself).

Fail-closed:
- If injection path is not declared, verdict is `HOLD_REMEDIATE`.
- If claim scope exceeds declared injection path coverage, verdict is `HOLD_REMEDIATE`.

---

## 2) Certified Envelope

### 2.1 RC2-S (Required)
| Dimension | Value | Unit | Source Ref | Type |
|---|---:|---|---|---|
| steady_rate | `25347` | events/sec | `runs/.../m7p8_stress_s5_20260304T205741Z/stress/m7p8_ieg_snapshot.json#performance_snapshot.throughput_observed` | measured |
| burst_rate | `30000` | events/sec | `policy_guardband_v0: 1.18x steady_rate derived from measured m7p8 throughput` | policy |
| burst_duration | `5` | min | `runs/.../m4_stress_s0_20260303T184138Z/stress/m4_lane_matrix.json#dispatch_profile.burst_window_minutes` | policy |
| soak_duration | `30` | min | `platform-realism envelope guidance (dev_full soak target 30-60 min)` | policy |
| recovery_window | `5` | min | `runs/.../m4_stress_s0_20260303T184138Z/stress/m4_lane_matrix.json#dispatch_profile.recovery_budget_seconds(300s)` | policy |
| replay_window_size | `18` | events | `runs/.../m9_stress_s1_20260305T001004Z/stress/m9c_replay_basis_receipt.json#origin_offset_ranges[0].observed_count` | measured |
| min_processed_events | `2190000986` | events | `runs/.../m7p8_stress_s5_20260304T205741Z/stress/m7p8_ieg_snapshot.json#performance_snapshot.sample_size` | measured |
| min_unique_keys | `8` | count | `runs/.../m7_stress_s5_20260304T212520Z/stress/m7_data_profile_summary.json#event_type_count` | measured |

RC2-S derivation notes:
- `steady_rate` is pinned from latest strict non-toy RTDL throughput evidence (`M7.P8 S5`).
- `burst_rate` is policy-derived from measured steady throughput to avoid certifying a no-headroom envelope while keeping near-term achievability.
- `soak_duration` is policy-pinned for production realism and cost control in `dev_full`.

### 2.2 RC2-L (Stretch, non-blocking by default)
| Dimension | Value | Unit | Source Ref | Type |
|---|---:|---|---|---|
| steady_rate | `TBD` | events/sec | `TBD` | measured |
| burst_rate | `TBD` | events/sec | `TBD` | measured |
| burst_duration | `TBD` | min | `TBD` | policy |
| soak_duration | `TBD` | min | `TBD` | policy |
| recovery_window | `TBD` | min | `TBD` | policy |

Activation rule:
- `RC2-S` rows must be fully populated (no `TBD`) before certification run is valid.
- `RC2-L` may remain `TBD` unless explicitly activated for required closure.

---

## 3) Tier-0 Runtime Thresholds (Pass/Fail)
| Claim | Metric | Threshold | Aggregation | Fail Code |
|---|---|---|---|---|
| Throughput | processed_rate | `>= 20000` events/sec | p50, p95 | `RC-B01` |
| Decision latency | decision_latency_ms | `p95 <= 1250` ms and `p99 <= 1300` ms | p95, p99 | `RC-B02` |
| Stability | error_rate_pct | `<= 0.5%` | run window avg | `RC-B03` |
| Consumer lag | consumer_lag | `p95 <= 20` and `p99 <= 30` | p95, p99 | `RC-B04` |
| Flink checkpoints | checkpoint_success_rate_pct | `>= 99.0%` | run window | `RC-B05` |
| Flink checkpoints | checkpoint_duration_ms | `p95 <= 120000` ms | p95 | `RC-B06` |
| Recovery | recovery_to_stable_sec | `<= 300` sec | single run bound | `RC-B07` |
| Unit cost | usd_per_1k_events | `<= 0.00005` USD | run window | `RC-B08` |
| Idle burn | usd_per_day_idle | `<= 10.0` USD | daily | `RC-B09` |

Calibration anchors:
- `RC-B01/03/04`: strict non-toy component perf snapshots (`m7/_strict_rerun_artifacts/*_performance_snapshot.json`) show `throughput_observed=25347.233634`, `error_rate_pct_observed=0.0`, and lag ceilings at `10/20/30`.
- `RC-B02`: `m7_addendum_service_path_latency_profile.json` (`p95=1161.643`, `p99=1161.643`) and `m7_probe_latency_throughput_snapshot.json` (`p95=1233.899`, `p99=1233.899`).
- `RC-B07`: `m4_lane_matrix.json#dispatch_profile.recovery_budget_seconds=300`.
- `RC-B08`: from `m7_addendum_cost_attribution_receipt.json` spend vs `m7_data_profile_summary.json#rows_scanned` gives measured `usd_per_1k_events ~= 0.000002542`; threshold set with 20x guardband.
- `RC-B09`: `m13_phase_cost_outcome_receipt.json#monthly_limit=300` plus `m13h_cost_guardrail_snapshot.json#idle_safe=true`.
- `RC-B05/RC-B06` are activated in fail-closed metric-presence mode: checkpoint metrics must be emitted in run artifacts; if absent/unreadable, fail `RC-B90`.

---

## 4) Component Gates (Hard)
| Component | Required Metrics | Pass Rule | Fail Code |
|---|---|---|---|
| IG (`API GW/Lambda/DDB`) | admit_rate, admission_latency_ms(p95/p99), ddb_throttle_rate_pct, ddb_hot_partition_rate_pct, offsets_materialized | `admit_rate >= 95%`; `p95 <= 1200 ms`; `p99 <= 1300 ms`; `ddb_throttle <= 0.5%`; `hot_partition <= 1.0%`; `offsets_materialized=true` | `RC-B10` |
| MSK | producer_error_rate_pct, broker_throttle_rate_pct, consumer_lag(p95/p99), broker_ack_and_consumer_readback | `producer_error_rate <= 0.5%`; `broker_throttle <= 1.0%`; `consumer_lag p95 <= 20`; `p99 <= 30`; broker ack + consumer readback pass | `RC-B11` |
| Flink (`MSF`/operator) | checkpoint_success_rate_pct, checkpoint_duration_ms_p95, backpressure_pct, restart_count_per_30m, processing_lag_p99 | `checkpoint_success >= 99.0%`; `checkpoint_duration_p95 <= 120000 ms`; `backpressure <= 10.0%`; `restart_count <= 1/30m`; `lag_p99 <= 30` | `RC-B12` |
| Aurora | connection_saturation_pct, query_latency_ms(p95/p99), timeout_deadlock_rate_pct | `connection_saturation <= 80.0%`; `query_latency p95 <= 250 ms`; `p99 <= 500 ms`; `timeout+deadlock <= 0.1%` | `RC-B13` |
| Redis | latency_ms(p95/p99), hit_rate_pct, timeout_rate_pct | `latency p95 <= 20 ms`; `p99 <= 50 ms`; `hit_rate >= 95.0%`; `timeout_rate <= 0.1%` | `RC-B14` |
| Archive/Audit sink | sink_throughput_rate, retry_backlog_rate_pct, tiny_file_rate_pct, durable_readback_success_rate | `sink_throughput >= 50 events/sec`; `retry_backlog <= 1.0%`; `tiny_file_rate <= 5.0%`; `durable_readback_success >= 99.0%` | `RC-B15` |

Calibration anchors:
- Ingress/lag/error/throughput envelope from `m6p7_*` snapshots and strict M7 component perf snapshots (`p8/p9/p10`).
- Broker readback proof from `m12d_learning_registry_publication_receipt.json` and `m12d_broker_transport_proof.json`.
- Archive floor from `p8d_archive_writer_performance_snapshot.json#throughput_min=50` and fallback durable readback success in `m7p8_archive_snapshot.json`.
- All required component metrics must be explicitly present in run-scoped artifacts (`component_gate_report.json` and source snapshots). Missing/unreadable metric is fail-closed (`RC-B90`), never implicit pass.

---

## 5) Data-Realism and Semantic Gates (Hard)
| Gate | Metric | Threshold | Fail Code |
|---|---|---|---|
| Join coverage | required join unmatched_rate | `<= 0.1%` and `join_scope_match=true` | `RC-B20` |
| Join fanout | 1->many expansion ratio | `<= 1.20` | `RC-B21` |
| Skew | top_0.1pct_key_share | `<= 40.0%` | `RC-B22` |
| Duplicates | duplicate_rate or dedupe-proof failure | injected window `0.5% <= duplicate_rate <= 1.0%` and unhandled duplicates `= 0` | `RC-B23` |
| Out-of-order | late_event_rate with watermark policy | injected window `0.2% <= late_event_rate <= 1.0%` and watermark policy pass | `RC-B24` |
| Label maturity | mature_label_coverage | `>= 95.0%` and `label_maturity_days >= 30` | `RC-B25` |
| Time-causality | future-access violations | `must be 0` | `RC-B26` |
| Explainability | decision records with required provenance fields | `>= 100%` completeness | `RC-B27` |

Required policy pins for this section:
- RTDL allowlist/denylist must be active and auditable.
- Truth surfaces (`s4_*`) must remain offline-only for runtime decision path.

Calibration anchors:
- Skew/duplicate/late pressure thresholds and observed injected cohorts from `m7_addendum_realism_window_summary.json` (targets: duplicate `0.75%`, late `0.3%`, hotkey `35%`, all pass).
- Label/case pressure minima from `m7_addendum_case_label_pressure_summary.json` and case writer/case-reopen safety from `m7p10_case_lifecycle_profile.json` + `m7p10_writer_conflict_profile.json`.
- Time-causality from `m9e_leakage_guardrail_report.json#violation_count=0` and `m10g_manifest_fingerprint_snapshot.json#time_bound_audit_leakage_future_breach_count=0`.
- Provenance/explainability completeness from `m11f_mlflow_lineage_snapshot.json#required_tags_missing=[]`.
- Join-scope correctness from `m12c_compatibility_precheck_snapshot.json#fingerprint_join_scope_matches_run=true`.
- Join unmatched/fanout metrics are mandatory explicit outputs in realism artifacts; absent metrics are fail-closed (`RC-B90`).

---

## 6) Anti-Gaming Rules (Mandatory)
1. Minimum run duration must be satisfied for each phase (`steady`, `burst`, `recovery`, `soak`).
2. Minimum processed event count must be met; attempted volume does not qualify.
3. Window must include at least one declared peak slice.
4. Report distributions at `p50/p95/p99` (not averages only).
5. Injection path must be declared and matched to claim scope.
6. No PASS if any required artifact is missing/unreadable.
7. No PASS with unresolved blockers or open waivers unless explicitly time-bounded and approved.
8. No PASS if threshold row is still `TBD` in activated scope.

---

## 7) Blocker Taxonomy and Rerun Boundaries
| Code Range | Meaning | Allowed Remediation | Required Rerun Scope |
|---|---|---|---|
| `RC-B01..RC-B09` | envelope/Tier-0 threshold failures | runtime/config/infra tuning | failed stage + downstream rollup |
| `RC-B10..RC-B15` | component gate failures | component-focused remediation | affected component lane + integration stage |
| `RC-B20..RC-B27` | realism/semantic failures | join/model/policy/watermark/TTL/data-contract remediation | realism stage + scorecard rerun |
| `RC-B90` | evidence artifact missing/unreadable | artifact path/schema/publication remediation | artifact stage + final verdict stage |
| `RC-B99` | undeclared scope or gating ambiguity | authority pinning/remediation | full certification rerun |

---

## 8) Evidence Artifact Contract
Required artifacts (run-scoped, deterministic names):
- `run_charter.json`
- `load_campaign_profile.json`
- `scorecard_snapshot.json`
- `component_gate_report.json`
- `reality_profile_summary.json`
- `join_coverage_matrix.json`
- `drill_pack_report.json`
- `cost_outcome_receipt.json`
- `blocker_register.json`
- `phase_execution_summary.json`

Each artifact must include:
- `execution_id`,
- `platform_run_id`,
- `injection_path`,
- `window_start_utc` and `window_end_utc`,
- `generated_at_utc`,
- source refs for measured metrics.

Durability/readback:
- Local and durable (S3) copies are required.
- Durable readback must pass for closure.

---

## 9) Final Verdict Rule
Certification `PASS` is allowed only if all are true:
1. `RC2-S` envelope criteria are fully satisfied.
2. Tier-0 thresholds are all pass.
3. Component gates are all pass.
4. Data-realism/semantic gates are all pass.
5. Drill pack is pass.
6. Required artifacts are complete and readable (local + durable).
7. `open_blockers = 0`.
8. Cost ceilings are within contract.

Else:
- Verdict is `HOLD_REMEDIATE` with explicit blocker codes and rerun scope.

---

## 10) Change Control
- Numeric changes require:
  - reason for change,
  - source reference (measured vs policy),
  - expected impact on pass/fail posture.
- Maintain append-only change log below.

### Change Log
- `v0` (2026-03-05): initial scaffold created with `TBD` thresholds; structure pinned for measured-value population.
- `v0` (2026-03-05): calibrated Sections 3/4/5 thresholds from M6/M7/M9/M10/M11/M12/M13 measured evidence, with fail-closed metric-presence activation for non-emitted telemetry.
