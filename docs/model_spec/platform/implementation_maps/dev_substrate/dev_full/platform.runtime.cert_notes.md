# Dev Full Runtime Certification Notes
Status: `RC0_PASS_RC1_READY`
Last updated: `2026-03-02`

## 1) Purpose
This notebook captures live reasoning, execution decisions, artifact locations, and blocker handling for runtime certification (`RC*`) from the clean restart baseline.

## 2) Reset Marker (Binding)
1. Prior runtime-cert attempt on `2026-03-02` is superseded as `SCRAPPED_NON_CLAIMABLE`.
2. No Tier-0 pass assertion may use superseded attempt artifacts.
3. Runtime certification restarts at `RC0` under managed-only + fresh-only + no-local-compute laws.

## 3) Superseded Attempt Register (Non-claimable)
The following attempts are retained for audit continuity only and are excluded from claimability:

| runtime_cert_execution_id | prior lane | prior status | classification |
| --- | --- | --- | --- |
| rc0_claim_model_lock_20260302T144121Z | RC0 | PASS | SCRAPPED_NON_CLAIMABLE |
| rc1_runtime_evidence_inventory_20260302T144531Z | RC1 | PASS | SCRAPPED_NON_CLAIMABLE |
| rc2_tier0_scorecard_20260302T153540Z | RC2 | HOLD | SCRAPPED_NON_CLAIMABLE |
| rc2_tier0_scorecard_20260302T153633Z | RC2 | HOLD | SCRAPPED_NON_CLAIMABLE |
| rc3_tier0_drill_pack_20260302T155517Z | RC3 | HOLD | SCRAPPED_NON_CLAIMABLE |
| rc1_runtime_evidence_inventory_fresh_20260302T161002Z | RC1 (fresh) | PASS | SCRAPPED_NON_CLAIMABLE |

## 4) Clean Restart Entry Gates
1. `M15_COMPLETE_GREEN` and `CERTIFICATION_TRACKS_READY` are revalidated from handoff artifacts.
2. Runtime cert plan status transition for clean campaign:
   - entry state: `NOT_STARTED`,
   - current state: `RC0_PASS_RC1_READY`.
3. Managed execution lanes are reachable for RC workload execution.
4. Certification window and identity pins for restart are declared before RC0 execution.

### 4.1) Pinned Identity Strategy Decision (2026-03-02)
1. Selected strategy: `NEW_CAMPAIGN_IDENTITY` (Option A).
2. Pinned campaign identity:
   - `platform_run_id=platform_cert_20260302T182050Z`
   - `scenario_run_id=scenario_cert_b2e31c46102062661ea43f12a8ceef77`
3. Claimability allowlist roots:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/`
   - `runs/dev_substrate/dev_full/cert/runtime/` (local mirror only).
4. Claimability denylist roots:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/_scrapped/`
   - `runs/dev_substrate/dev_full/cert/_scrapped/`
   - any superseded RC execution IDs listed in the superseded register.

## 5) Clean Run Register
To be populated only by clean restart executions.

| runtime_cert_execution_id | lane | started_utc | durable_root | status |
| --- | --- | --- | --- | --- |
| rc0_claim_model_lock_20260302T182821Z | RC0 | 2026-03-02T18:28:21Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc0_claim_model_lock_20260302T182821Z/ | FAILED_NON_CLAIMABLE_SCRIPT_PRECHECK |
| rc0_claim_model_lock_20260302T182833Z | RC0 | 2026-03-02T18:28:33Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc0_claim_model_lock_20260302T182833Z/ | FAILED_NON_CLAIMABLE_SCRIPT_UPLOAD |
| rc0_claim_model_lock_20260302T182859Z | RC0 | 2026-03-02T18:28:59Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc0_claim_model_lock_20260302T182859Z/ | PASS_RC1_READY |

## 6) Clean Evidence Index
To be populated only by clean restart executions.
1. `rc0_claim_model_lock_20260302T182859Z/runtime_claim_matrix.json`
2. `rc0_claim_model_lock_20260302T182859Z/runtime_metric_dictionary.json`
3. `rc0_claim_model_lock_20260302T182859Z/runtime_evidence_bundle_rules.json`
4. `rc0_claim_model_lock_20260302T182859Z/rc0_execution_snapshot.json`

## 7) Active Blockers (Clean Baseline)
1. none at RC0 closure (`blocker_count=0`).

## 8) Phase Verdict Log (Clean Baseline)
| Lane | Verdict | Notes |
| --- | --- | --- |
| RC0 | PASS | rc0_claim_model_lock_20260302T182859Z, next_gate=RC1_READY |
| RC1 | NOT_STARTED | gate open (`RC1_READY`) |
| RC2 | NOT_STARTED | waiting for clean restart |
| RC3 | NOT_STARTED | waiting for clean restart |
| RC4 | NOT_STARTED | waiting for clean restart |
| RC5 | NOT_STARTED | waiting for clean restart |
| RC6 | NOT_STARTED | waiting for clean restart |
