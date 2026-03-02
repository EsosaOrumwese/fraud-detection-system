# Dev Full Runtime Certification Notes
Status: `ACTIVE`
Last updated: `2026-03-02`

## 1) Purpose
This notebook captures live reasoning, execution decisions, artifact locations, and blocker handling for runtime certification (`RC*`).
It is separate from implementation remediations; platform implementation adjustments remain in `platform.impl_actual.md`.

## 2) Execution Ledger
### 2026-03-02 13:56:00 +00:00 - RC0 kickoff intent
1. Goal set: execute `RC0` first (claim model lock + metric dictionary) before any runtime load/drill lane.
2. Decision: Tier 0 is hard gate for deployability; Tier 1/2 are still graded and tracked, but do not silently upgrade to hard gate without explicit repin.
3. Decision: create deterministic RC0 artifacts (claim matrix, metric dictionary, evidence bundle rules, execution snapshot) and mirror to durable store if AWS credential context is available.

### 2026-03-02 14:41:28 +00:00 - RC0 execution and closure
1. Executed RC0 artifact materialization with deterministic execution id:
   - `runtime_cert_execution_id=rc0_claim_model_lock_20260302T144121Z`.
2. Context pins loaded from M15 closure summary:
   - `platform_run_id=platform_20260302T080146Z`
   - `scenario_run_id=scenario_9de27c0bd83aed3a4aea4d0063c981f1`.
3. RC0 artifacts created locally:
   - `runtime_claim_matrix.json`
   - `runtime_metric_dictionary.json`
   - `runtime_evidence_bundle_rules.json`
   - `rc0_execution_snapshot.json`.
4. Durable publication and readback succeeded (AWS session available):
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z/`.
5. RC0 verdict:
   - `overall_pass=true`, `blockers=[]`, `advisories=[]`, `next_gate=RC1_READY`.
6. Tier handling pinned in execution artifacts:
   - Tier-0 rows are hard-gate claims,
   - Tier-1/2 rows are advisory claims with explicit metric + evidence mappings (no silent omission).

### 2026-03-02 14:45:38 +00:00 - RC1 execution and closure
1. Executed runtime evidence inventory lane with deterministic id:
   - `runtime_cert_execution_id=rc1_runtime_evidence_inventory_20260302T144531Z`.
2. Inputs pinned:
   - RC0 artifacts from `rc0_claim_model_lock_20260302T144121Z`,
   - context pins `platform_run_id=platform_20260302T080146Z`, `scenario_run_id=scenario_9de27c0bd83aed3a4aea4d0063c981f1`.
3. Evidence crawl coverage:
   - local runtime JSON surfaces crawled: `1352`,
   - durable S3 evidence keys crawled: `2672`,
   - durable crawl errors: `[]`.
4. RC1 artifacts produced:
   - `runtime_evidence_inventory.json`
   - `runtime_evidence_gap_register.json`
   - `rc1_execution_snapshot.json`
5. Durable publication succeeded:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T144531Z/`.
6. RC1 verdict:
   - `overall_pass=true`,
   - `lane_blockers=[]`,
   - `next_gate=RC2_READY_WITH_GAP_REGISTER`.
7. Assertion discipline preserved:
   - no claim is marked pass in RC1 (`evaluation_status=NOT_EVALUATED`, `pass_asserted=false` for all claim rows).

### 2026-03-02 15:36:39 +00:00 - RC2 execution (fail-closed HOLD)
1. Executed RC2 scorecard lane against pinned mandatory profiles (steady/burst/soak/replay-window).
2. Initial run `rc2_tier0_scorecard_20260302T153540Z` was superseded immediately by `rc2_tier0_scorecard_20260302T153633Z`:
   - reason: corrected `best_available_candidate` ranking logic in blocker reporting.
3. Latest authoritative RC2 execution:
   - `runtime_cert_execution_id=rc2_tier0_scorecard_20260302T153633Z`
   - local root: `runs/dev_substrate/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z`
   - durable root: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z/`
4. RC2 outputs published:
   - `runtime_scorecard_profiles.json`
   - `runtime_blocker_register.json`
   - `runtime_certification_verdict.json`
   - `rc2_execution_snapshot.json`
5. RC2 verdict:
   - `overall_pass=false`, `verdict=HOLD`, `next_gate=RC2_REMEDIATION_REQUIRED`.
6. Active blockers (`RC-B4`) from latest run:
   - steady profile below pinned floor (`target=500 eps`, `min_sample=900,000`; best observed `49.49 eps`, sample `11,878`),
   - burst profile below pinned floor (`target=1,500 eps`, `min_sample=900,000`; best observed `49.49 eps`, sample `11,878`),
   - soak profile below pinned floor (`target=300 eps for 6h`, `min_sample=6,480,000`; best sample `11,878`),
   - replay-window profile below pinned floor (`min_sample=10,000,000`; best sample `11,878`).
7. Intentional discipline:
   - RC2 did not synthesize fake distributions; missing profile-grade evidence remained fail-closed and explicit.

### 2026-03-02 15:51:49 +00:00 - RC3 planning and source-selection posture
1. RC3 lane will execute as a deterministic drill-pack certification pass over existing dev_full evidence surfaces.
2. Entry-gate decision:
   - `RC1` PASS is required and satisfied.
   - `RC2` HOLD is non-blocking for RC3 execution, but remains active for final runtime green verdict.
3. Mandatory drill-family source candidates pinned pre-execution:
   - `DR-02` replay/backfill integrity:
     - `runs/dev_substrate/dev_full/m9/m9c_p12_replay_basis_20260226T075941Z/m9c_replay_basis_receipt.json`
     - `runs/dev_substrate/dev_full/m15/m15g_semantic_non_regression_20260302T083157Z/m15g_replay_asof_continuity_report.json`
   - `DR-03` lag spike and recovery:
     - `runs/dev_substrate/dev_full/m6/_gh_run_22409183214/m6f-streaming-active-20260225T175655Z/m6f_streaming_lag_posture.json`
     - `runs/dev_substrate/dev_full/m6/_gh_run_22409183214/m6f-streaming-active-20260225T175655Z/m6f_publish_ambiguity_register.json`
   - `DR-04` schema evolution safety:
     - `runs/dev_substrate/dev_full/m2/m2d_20260222T230240Z/m2d_schema_registry_snapshot.json`
   - `DR-05` dependency outage with degrade/recover:
     - `runs/dev_substrate/dev_full/m4/m4g_20260224T063238Z/m4g_failure_injection_snapshot.json`
     - `runs/dev_substrate/dev_full/m4/m4g_20260224T063238Z/m4g_recovery_rollback_snapshot.json`
     - `runs/dev_substrate/dev_full/m4/m4g_20260224T063238Z/m4g_runtime_drill_snapshot.json`
   - `DR-07` runtime cost guardrail response:
     - `runs/dev_substrate/dev_full/m15/m15h_cost_perf_closure_20260302T084018Z/cost_guardrail_snapshot.json`
     - `runs/dev_substrate/dev_full/m15/m15h_cost_perf_closure_20260302T084018Z/m15_phase_cost_outcome_receipt.json`
4. Fail-closed interpretation pinned:
   - each mandatory drill row must include scenario, expected behavior, observed outcome, integrity checks, and recovery-bound fields;
   - missing required fields or only implicit proof is recorded as `RC-B5` and lane verdict is `HOLD`.

### 2026-03-02 15:55:24 +00:00 - RC3 execution (fail-closed HOLD)
1. Executed RC3 drill-pack certification lane with deterministic id:
   - `runtime_cert_execution_id=rc3_tier0_drill_pack_20260302T155517Z`.
2. Context pins held constant from RC0:
   - `platform_run_id=platform_20260302T080146Z`
   - `scenario_run_id=scenario_9de27c0bd83aed3a4aea4d0063c981f1`.
3. RC3 artifacts produced:
   - `runtime_drill_bundle.json`
   - `runtime_blocker_register.json`
   - `runtime_certification_verdict.json`
   - `rc3_execution_snapshot.json`
4. Durable publication/readback succeeded:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z/`.
5. Drill-family adjudication:
   - pass: `DR-02`, `DR-05`
   - fail-closed: `DR-03`, `DR-04`, `DR-07`.
6. RC3 verdict:
   - `overall_pass=false`, `verdict=HOLD`, `next_gate=RC3_REMEDIATION_REQUIRED`.
7. Active RC3 blockers (`RC-B5`):
   - `DR-03` missing explicit lag-spike injection/recovery drill evidence,
   - `DR-04` missing explicit schema-break injection + quarantine/recovery drill evidence,
   - `DR-07` missing explicit threshold-breach -> action -> idle-safe drill evidence.

### 2026-03-02 16:10:09 +00:00 - RC1 fresh-only rerun (inventory PASS, Tier-0 fresh gaps explicit)
1. Executed fresh-only RC1 inventory lane with deterministic id:
   - `runtime_cert_execution_id=rc1_runtime_evidence_inventory_fresh_20260302T161002Z`.
2. Freshness posture enforced:
   - allowed evidence roots restricted to runtime-cert prefixes,
   - historical lineage from `runs/dev_substrate/dev_full/m*` does not count as fresh.
3. Outputs published:
   - `runtime_evidence_inventory.json`
   - `runtime_evidence_gap_register.json`
   - `rc1_execution_snapshot.json`
4. Durable publication/readback succeeded:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_fresh_20260302T161002Z/`.
5. Lane verdict:
   - `overall_pass=true` (inventory lane),
   - `next_gate=RC2_READY_WITH_FRESH_GAP_REGISTER`.
6. Fresh Tier-0 evidence blockers made explicit:
   - `15` open `RC-B3` blockers across all Tier-0 metrics (`MISSING_FRESH_EVIDENCE` or `HISTORICAL_LINEAGE`).
7. Prior RC1 (`rc1_runtime_evidence_inventory_20260302T144531Z`) is now treated as superseded for strict fresh-evidence certification posture.

## 3) Run Register
| runtime_cert_execution_id | phase | started_utc | local_root | durable_root | status |
| --- | --- | --- | --- | --- | --- |
| rc0_claim_model_lock_20260302T144121Z | RC0 | 2026-03-02T14:41:21Z | runs/dev_substrate/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z | PASS |
| rc1_runtime_evidence_inventory_20260302T144531Z | RC1 | 2026-03-02T14:45:31Z | runs/dev_substrate/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T144531Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T144531Z | PASS |
| rc2_tier0_scorecard_20260302T153633Z | RC2 | 2026-03-02T15:36:33Z | runs/dev_substrate/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z | HOLD |
| rc3_tier0_drill_pack_20260302T155517Z | RC3 | 2026-03-02T15:55:17Z | runs/dev_substrate/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z | HOLD |
| rc1_runtime_evidence_inventory_fresh_20260302T161002Z | RC1 (fresh) | 2026-03-02T16:10:02Z | runs/dev_substrate/dev_full/cert/runtime/rc1_runtime_evidence_inventory_fresh_20260302T161002Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_fresh_20260302T161002Z | PASS |

## 4) Metrics Register
To be populated during RC0 materialization and updated as RC2+ runs execute.

## 5) Evidence Index
1. RC0 claim matrix:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z/runtime_claim_matrix.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z/runtime_claim_matrix.json`
2. RC0 metric dictionary:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z/runtime_metric_dictionary.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z/runtime_metric_dictionary.json`
3. RC0 evidence bundle rules:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z/runtime_evidence_bundle_rules.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z/runtime_evidence_bundle_rules.json`
4. RC0 execution snapshot:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z/rc0_execution_snapshot.json`
5. RC1 evidence inventory:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T144531Z/runtime_evidence_inventory.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T144531Z/runtime_evidence_inventory.json`
6. RC1 gap register:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T144531Z/runtime_evidence_gap_register.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T144531Z/runtime_evidence_gap_register.json`
7. RC1 execution snapshot:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T144531Z/rc1_execution_snapshot.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T144531Z/rc1_execution_snapshot.json`
8. RC2 scorecard profiles:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z/runtime_scorecard_profiles.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z/runtime_scorecard_profiles.json`
9. RC2 blocker register:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z/runtime_blocker_register.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z/runtime_blocker_register.json`
10. RC2 verdict:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z/runtime_certification_verdict.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z/runtime_certification_verdict.json`
11. RC3 drill bundle:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z/runtime_drill_bundle.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z/runtime_drill_bundle.json`
12. RC3 blocker register:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z/runtime_blocker_register.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z/runtime_blocker_register.json`
13. RC3 verdict:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z/runtime_certification_verdict.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z/runtime_certification_verdict.json`
14. RC3 execution snapshot:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z/rc3_execution_snapshot.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z/rc3_execution_snapshot.json`
15. RC1 fresh evidence inventory:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc1_runtime_evidence_inventory_fresh_20260302T161002Z/runtime_evidence_inventory.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_fresh_20260302T161002Z/runtime_evidence_inventory.json`
16. RC1 fresh gap register:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc1_runtime_evidence_inventory_fresh_20260302T161002Z/runtime_evidence_gap_register.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_fresh_20260302T161002Z/runtime_evidence_gap_register.json`
17. RC1 fresh execution snapshot:
   - local: `runs/dev_substrate/dev_full/cert/runtime/rc1_runtime_evidence_inventory_fresh_20260302T161002Z/rc1_execution_snapshot.json`
   - durable: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_fresh_20260302T161002Z/rc1_execution_snapshot.json`

## 6) Blocker Register
1. Active (`RC2`):
   - `RC-B4` steady profile evidence below pinned floor.
   - `RC-B4` burst profile evidence below pinned floor.
   - `RC-B4` soak profile evidence below pinned floor.
   - `RC-B4` replay-window profile evidence below pinned floor.
2. Active (`RC3`):
   - `RC-B5` `DR-03` lag-spike injection/recovery drill proof missing.
   - `RC-B5` `DR-04` schema-break injection + quarantine/recovery drill proof missing.
   - `RC-B5` `DR-07` breach-response cost guardrail drill proof missing.
3. Active (`RC1 fresh-only`):
   - `RC-B3` Tier-0 metrics currently lack fresh evidence (`15` blockers total; see fresh gap register).
   - explicit metric set:
     - `T0.2`: `decision_latency_p95_ms`, `decision_latency_p99_ms`, `decision_success_availability_pct`, `decision_non_retryable_error_rate_pct`
     - `T0.3`: `replay_integrity_mismatch_count`, `duplicate_side_effect_count`, `ingress_to_core_lag_p95_seconds`, `ingress_to_core_lag_p99_seconds`, `publish_unknown_unresolved_count`
     - `T0.4`: `runtime_correlation_id_coverage_pct`, `runtime_ttd_p95_minutes`, `runtime_ttdiag_p95_minutes`
     - `T0.6`: `runtime_unattributed_spend_count`, `runtime_cost_attribution_coverage_pct`, `runtime_budget_alert_level`

## 7) Phase Verdict Log
| Lane | Verdict | Notes |
| --- | --- | --- |
| RC0 | PASS | Claim model + metric dictionary + evidence bundle rules materialized and mirrored durably |
| RC1 | PASS | Runtime evidence inventory and gap register materialized with deterministic refs; no claim marked pass |
| RC2 | HOLD | Scorecard lane executed fail-closed; mandatory profile evidence not yet at pinned scale |
| RC3 | HOLD | Drill-pack lane executed fail-closed; DR-03/DR-04/DR-07 remain incomplete and blocked |
| RC1 (fresh) | PASS | Fresh-only inventory lane closed with deterministic gaps; Tier-0 fresh blockers explicit (15x RC-B3) |

### 2026-03-02 16:38:40 +00:00 - RC1 remediation lane restart (OIDC trust drift)
1. Attempted fresh managed `M6.F` lane dispatch from active branch `cert-platform`:
   - run id: `22585644818`
   - execution id: `m6f_p6b_streaming_active_20260302T163640Z`
   - platform run id: `platform_20260302T163640Z`
2. Run failed before lane execution at AWS credential bootstrap:
   - step: `Configure AWS credentials via OIDC`
   - failure: `Not authorized to perform sts:AssumeRoleWithWebIdentity`
3. Root cause confirmed from IAM trust policy:
   - role `GitHubAction-AssumeRoleWithAction` allowed `main/dev/migrate-dev` only,
   - active runtime-cert branch `cert-platform` was not listed.
4. Remediation applied directly in IAM trust (no branch operations):
   - removed stale subject `...:ref:refs/heads/migrate-dev`,
   - added `...:ref:refs/heads/cert-platform`,
   - post-change allow-list: `main`, `dev`, `cert-platform`.

### 2026-03-02 16:49:10 +00:00 - Fresh M6.F remediation pass (runtime path switch)
1. First rerun with OIDC fixed but default runtime path (`EKS_EMR_ON_EKS`) failed fail-closed:
   - run id: `22585858766`
   - execution id: `m6f_p6b_streaming_active_20260302T164158Z`
   - blockers:
     - `M6P6-B2` lane refs remained `SUBMITTED` (not `RUNNING`),
     - `M6P6-B3` run-window admission progression zero,
     - `M6P6-B4` lag posture unresolved.
2. Decision: switch lane runtime path to `EKS_FLINK_OPERATOR` (already pinned and supported by workflow) to avoid EMR-on-EKS scheduler stall for RC1 fresh evidence generation.
3. Second rerun succeeded:
   - run id: `22586052165`
   - execution id: `m6f_p6b_streaming_active_20260302T164648Z`
   - platform run id: `platform_20260302T164648Z`
   - verdict: `overall_pass=true`, `next_gate=M6.G_READY`.
4. Fresh evidence produced in run-control for this execution:
   - `m6f_streaming_active_snapshot.json` shows:
     - `runtime_path=EKS_FLINK_OPERATOR`,
     - `wsp_state=RUNNING`, `sr_ready_state=RUNNING`,
     - run-window IG admission count `12`.
5. RC1 remediation posture after this step:
   - OIDC branch-trust blocker is closed,
   - fresh streaming-active evidence surface is now available for current cert window,
   - next required closure is fresh P7 ingest-commit/rollup surfaces (M6.G/M6.H/M6.I) for full Tier-0 metric coverage.
