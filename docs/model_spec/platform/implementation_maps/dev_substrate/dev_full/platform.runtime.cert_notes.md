# Dev Full Runtime Certification Notes
Status: `RC2_HOLD_REMEDIATION_REQUIRED`
Last updated: `2026-03-02`

## 1) Purpose
This notebook is the runtime-cert state ledger for `RC*` lanes.
It records only certification state, authoritative run receipts, blocker posture, and artifact roots.
Implementation reasoning and decision process are recorded in:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`
- `docs/logbook/03-2026/2026-03-02.md`

## 2) Reset Marker (Binding)
1. Prior runtime-cert attempt on `2026-03-02` is superseded as `SCRAPPED_NON_CLAIMABLE`.
2. No Tier-0 pass assertion may use superseded attempt artifacts.
3. Runtime certification restarted at `RC0` under managed-only + fresh-only + no-local-compute laws.

## 3) Superseded Attempt Register (Non-claimable)
| runtime_cert_execution_id | prior lane | prior status | classification |
| --- | --- | --- | --- |
| rc0_claim_model_lock_20260302T144121Z | RC0 | PASS | SCRAPPED_NON_CLAIMABLE |
| rc1_runtime_evidence_inventory_20260302T144531Z | RC1 | PASS | SCRAPPED_NON_CLAIMABLE |
| rc2_tier0_scorecard_20260302T153540Z | RC2 | HOLD | SCRAPPED_NON_CLAIMABLE |
| rc2_tier0_scorecard_20260302T153633Z | RC2 | HOLD | SCRAPPED_NON_CLAIMABLE |
| rc3_tier0_drill_pack_20260302T155517Z | RC3 | HOLD | SCRAPPED_NON_CLAIMABLE |
| rc1_runtime_evidence_inventory_fresh_20260302T161002Z | RC1 (fresh) | PASS | SCRAPPED_NON_CLAIMABLE |

## 4) Clean Campaign Identity Pins
1. Strategy: `NEW_CAMPAIGN_IDENTITY`.
2. Campaign identity:
   - `platform_run_id=platform_cert_20260302T182050Z`
   - `scenario_run_id=scenario_cert_b2e31c46102062661ea43f12a8ceef77`
3. Claimable roots:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/`
   - `runs/dev_substrate/dev_full/cert/runtime/` (local mirror)
4. Non-claimable roots:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/_scrapped/`
   - `runs/dev_substrate/dev_full/cert/_scrapped/`

## 5) Quarantine Ledger (Failed RC0 Attempts)
1. Quarantine root (local):
   - `runs/dev_substrate/dev_full/cert/_scrapped/runtime_failed_rc0_20260302T183432Z/`
2. Quarantine root (durable):
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/_scrapped/runtime_failed_rc0_20260302T183432Z/`
3. Quarantined attempt:
   - `rc0_claim_model_lock_20260302T182833Z`
4. Non-materialized failed attempt:
   - `rc0_claim_model_lock_20260302T182821Z` (no local/durable artifacts)

## 6) Clean Run Register
| runtime_cert_execution_id | lane | started_utc | durable_root | status |
| --- | --- | --- | --- | --- |
| rc0_claim_model_lock_20260302T182821Z | RC0 | 2026-03-02T18:28:21Z | N/A | FAILED_NON_CLAIMABLE_NO_ARTIFACTS |
| rc0_claim_model_lock_20260302T182833Z | RC0 | 2026-03-02T18:28:33Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/_scrapped/runtime_failed_rc0_20260302T183432Z/rc0_claim_model_lock_20260302T182833Z/ | FAILED_NON_CLAIMABLE_QUARANTINED |
| rc0_claim_model_lock_20260302T182859Z | RC0 | 2026-03-02T18:28:59Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc0_claim_model_lock_20260302T182859Z/ | PASS_RC1_READY |
| rc1_runtime_evidence_inventory_20260302T191046Z | RC1 | 2026-03-02T19:10:46Z | N/A | FAILED_NON_CLAIMABLE_IAM_S3_LIST_DENIED |
| rc1_runtime_evidence_inventory_20260302T191353Z | RC1 | 2026-03-02T19:13:53Z | N/A | FAILED_NON_CLAIMABLE_IAM_S3_PUT_DENIED |
| rc1_runtime_evidence_inventory_20260302T191532Z | RC1 | 2026-03-02T19:15:32Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T191532Z/ | PASS_RC2_READY_WITH_GAP_REGISTER |
| rc1_runtime_evidence_inventory_20260302T192109Z | RC1 | 2026-03-02T19:21:09Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T192109Z/ | PASS_RC2_READY_WITH_GAP_REGISTER_REVALIDATED |
| rc2_tier0_scorecard_20260302T193820Z | RC2 | 2026-03-02T19:38:20Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T193820Z/ | HOLD_REMEDIATION_REQUIRED_MISSING_FRESH_EVIDENCE |
| rc2_tier0_scorecard_20260302T202938Z | RC2 | 2026-03-02T20:29:38Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T202938Z/ | HOLD_REMEDIATION_REQUIRED_PRE_PATCH_WINDOW_FILTER |
| rc2_tier0_scorecard_20260302T203534Z | RC2 | 2026-03-02T20:35:34Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T203534Z/ | HOLD_REMEDIATION_REQUIRED_THRESHOLD_NOT_MET_SAMPLE_0 |
| rc2_tier0_scorecard_20260302T204844Z | RC2 | 2026-03-02T20:48:44Z | s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T204844Z/ | HOLD_REMEDIATION_REQUIRED_THRESHOLD_NOT_MET_SAMPLE_4783 |

## 7) Phase Verdict Log (Current)
| Lane | Verdict | Notes |
| --- | --- | --- |
| RC0 | PASS | rc0_claim_model_lock_20260302T182859Z, next_gate=RC1_READY |
| RC1 | PASS | rc1_runtime_evidence_inventory_20260302T192109Z, next_gate=RC2_READY_WITH_GAP_REGISTER |
| RC2 | HOLD | rc2_tier0_scorecard_20260302T204844Z, next_gate=RC2_REMEDIATION_REQUIRED, blocker_count=4 |
| RC3 | NOT_STARTED | blocked by RC2 hold |
| RC4 | NOT_STARTED | waiting for RC2 closure |
| RC5 | NOT_STARTED | waiting for RC2 closure |
| RC6 | BLOCKED | blocked by Tier-0 hold posture |

## 8) Current RC2 Blocker Posture (Authoritative)
1. Latest RC2 execution: `rc2_tier0_scorecard_20260302T204844Z` (run `22595073028`).
2. Verdict:
   - `overall_pass=false`
   - `verdict=HOLD`
   - `next_gate=RC2_REMEDIATION_REQUIRED`
   - `blocker_count=4`
   - `tier0_hold_count=4`
3. Blocker class:
   - all four blockers are `RC-B4` with `profile evidence present but thresholds not met`.
4. Profile evidence posture:
   - all required profiles are `FRESH_EVIDENCE_FOUND`.
   - observed sample per profile: `4783`.
5. Tier-0 holds:
   - `T0.2`, `T0.3`, `T0.4`, `T0.6` remain `HOLD_REMEDIATION_REQUIRED`.

## 9) RC2 Threshold Gap Snapshot
1. Current observed volume/rate in latest RC2 run:
   - `sample_size_events=4783`
   - `observed_events_per_second=0.570287349469417`
2. Required profile floors:
   - steady: `>=900,000` sample, `>=500 eps`, `>=30 min` logical duration
   - burst: `>=900,000` sample, `>=1500 eps`, `>=10 min` logical duration
   - soak: `>=6,480,000` sample, `>=300 eps`, `>=360 min` logical duration
   - replay_window: `>=10,000,000` sample

## 10) Upstream Managed Volume Probe Receipt
1. Managed run used to inject fresh campaign admissions before latest RC2 rerun:
   - workflow: `dev_full_m6f_streaming_active.yml`
   - run id: `22594867808`
   - execution: `m6f_p6b_streaming_active_20260302T204315Z`
2. Bridge summary:
   - `attempted=5000`, `admitted=4783`, `failed=217`.
3. Probe note:
   - M6.F lane itself failed its lag gate, but admissions were written and were consumed by RC2.

## 11) Next Gate Condition
RC2 can move from `RC2_REMEDIATION_REQUIRED` to `RC3_READY_WITH_SCORECARD` only when:
1. all four required profiles satisfy sample/eps/duration thresholds,
2. `blocker_count=0`,
3. Tier-0 claims no longer hold.
