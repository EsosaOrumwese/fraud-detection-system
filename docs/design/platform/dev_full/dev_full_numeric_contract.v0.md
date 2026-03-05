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
| steady_rate | `TBD` | events/sec | `TBD` | measured |
| burst_rate | `TBD` | events/sec | `TBD` | measured |
| burst_duration | `TBD` | min | `TBD` | policy |
| soak_duration | `TBD` | min | `TBD` | policy |
| recovery_window | `TBD` | min | `TBD` | policy |
| replay_window_size | `TBD` | events | `TBD` | measured |
| min_processed_events | `TBD` | events | `TBD` | policy |
| min_unique_keys | `TBD` | count | `TBD` | policy |

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
| Throughput | processed_rate | `>= TBD` | p50, p95 | `RC-B01` |
| Decision latency | decision_latency_ms | `p95 <= TBD` and `p99 <= TBD` | p95, p99 | `RC-B02` |
| Stability | error_rate_pct | `<= TBD` | run window avg | `RC-B03` |
| Consumer lag | consumer_lag | `p95 <= TBD` and `p99 <= TBD` | p95, p99 | `RC-B04` |
| Flink checkpoints | checkpoint_success_rate_pct | `>= TBD` | run window | `RC-B05` |
| Flink checkpoints | checkpoint_duration_ms | `p95 <= TBD` | p95 | `RC-B06` |
| Recovery | recovery_to_stable_sec | `<= TBD` | single run bound | `RC-B07` |
| Unit cost | usd_per_1k_events | `<= TBD` | run window | `RC-B08` |
| Idle burn | usd_per_day_idle | `<= TBD` | daily | `RC-B09` |

---

## 4) Component Gates (Hard)
| Component | Required Metrics | Pass Rule | Fail Code |
|---|---|---|---|
| IG (`API GW/Lambda/DDB`) | admit_rate, p95/p99 latency, throttle profile, DDB hot-partition rate | all metrics within pinned thresholds | `RC-B10` |
| MSK | producer_error_rate, broker throttle, consumer lag p95/p99 | all metrics within pinned thresholds | `RC-B11` |
| Flink (`MSF`) | checkpoint health, backpressure, restart_count, processing latency | all metrics within pinned thresholds | `RC-B12` |
| Aurora | connection saturation, query latency p95/p99, timeout/deadlock rate | all metrics within pinned thresholds | `RC-B13` |
| Redis | latency p95/p99, hit rate, timeout rate | all metrics within pinned thresholds | `RC-B14` |
| Archive/Audit sink | sink throughput, retry/backlog, tiny-file rate | all metrics within pinned thresholds | `RC-B15` |

---

## 5) Data-Realism and Semantic Gates (Hard)
| Gate | Metric | Threshold | Fail Code |
|---|---|---|---|
| Join coverage | required join unmatched_rate | `<= TBD` | `RC-B20` |
| Join fanout | 1->many expansion ratio | `<= TBD` | `RC-B21` |
| Skew | top_0.1pct_key_share | `<= TBD` | `RC-B22` |
| Duplicates | duplicate_rate or dedupe-proof failure | `<= TBD` or zero unhandled duplicates | `RC-B23` |
| Out-of-order | late_event_rate with watermark policy | `<= TBD` and policy pass | `RC-B24` |
| Label maturity | mature_label_coverage | `>= TBD` | `RC-B25` |
| Time-causality | future-access violations | `must be 0` | `RC-B26` |
| Explainability | decision records with required provenance fields | `>= TBD%` completeness | `RC-B27` |

Required policy pins for this section:
- RTDL allowlist/denylist must be active and auditable.
- Truth surfaces (`s4_*`) must remain offline-only for runtime decision path.

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
