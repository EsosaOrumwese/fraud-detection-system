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

## 3) Run Register
| runtime_cert_execution_id | phase | started_utc | local_root | durable_root | status |
| --- | --- | --- | --- | --- | --- |
| rc0_claim_model_lock_20260302T144121Z | RC0 | 2026-03-02T14:41:21Z | runs/dev_substrate/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z | PASS |
| rc1_runtime_evidence_inventory_20260302T144531Z | RC1 | 2026-03-02T14:45:31Z | runs/dev_substrate/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T144531Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T144531Z | PASS |
| rc2_tier0_scorecard_20260302T153633Z | RC2 | 2026-03-02T15:36:33Z | runs/dev_substrate/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z | HOLD |

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

## 6) Blocker Register
1. Active (`RC2`):
   - `RC-B4` steady profile evidence below pinned floor.
   - `RC-B4` burst profile evidence below pinned floor.
   - `RC-B4` soak profile evidence below pinned floor.
   - `RC-B4` replay-window profile evidence below pinned floor.

## 7) Phase Verdict Log
| Lane | Verdict | Notes |
| --- | --- | --- |
| RC0 | PASS | Claim model + metric dictionary + evidence bundle rules materialized and mirrored durably |
| RC1 | PASS | Runtime evidence inventory and gap register materialized with deterministic refs; no claim marked pass |
| RC2 | HOLD | Scorecard lane executed fail-closed; mandatory profile evidence not yet at pinned scale |
