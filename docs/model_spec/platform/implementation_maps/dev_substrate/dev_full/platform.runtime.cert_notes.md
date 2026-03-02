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

## 9.1) RC2 Observed vs Required Comparison (Latest Authoritative Run)
Source:
- run id `22595073028`
- execution `rc2_tier0_scorecard_20260302T204844Z`

| Profile | Sample (Observed / Required) | EPS (Observed / Required) | Duration min (Observed / Required) | Result |
| --- | --- | --- | --- | --- |
| `steady` | `4,783 / 900,000` (`0.5314%`) | `0.5703 / 500` (`0.1141%`) | `0.1594 / 30` (`0.5314%`) | FAIL |
| `burst` | `4,783 / 900,000` (`0.5314%`) | `0.5703 / 1500` (`0.0380%`) | `0.0531 / 10` (`0.5314%`) | FAIL |
| `soak` | `4,783 / 6,480,000` (`0.0738%`) | `0.5703 / 300` (`0.1901%`) | `0.2657 / 360` (`0.0738%`) | FAIL |
| `replay_window` | `4,783 / 10,000,000` (`0.0478%`) | `N/A` | `N/A` | FAIL |

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

### 2026-03-02 17:31:40 +00:00 - RC2 strict remediation plan update (production-envelope, no floor downgrade)
1. Decision pinned: keep RC2 floors unchanged (`steady=500eps/30m/900k`, `burst=1500eps/10m/900k`, `soak=300eps/6h/6.48M`, `replay_window=10M`).
2. RC2 remediation path updated in runtime-cert plan with explicit sequence `RC2.R1..RC2.R6`:
   - `R1` evidence-shape correctness gate,
   - `R2` managed bottleneck-localization ramp,
   - `R3` lane-specific remediation loop,
   - `R4` full profile campaigns,
   - `R5` replay-window campaign,
   - `R6` RC2 rollup closure.
3. Current proven bottleneck facts (from latest authoritative RC2 surfaces):
   - profile evidence exists but all four profiles are below threshold (`RC-B4 x4`),
   - sample/eps posture remains far below floor (`sample_size_events=4783`, `observed_eps~0.5703`),
   - upstream managed probe was low-volume (`attempted=5000`, `admitted=4783`),
   - run-window admission counting surfaced truncation posture in upstream lane (`dynamodb_scan_page_limit_reached`) and is treated as non-claimable for production scorecard attribution until corrected.
4. Execution posture reaffirmed:
   - managed orchestration only,
   - no local compute,
   - no threshold downgrade,
   - no historical evidence substitution for RC2 closure.

### 2026-03-02 21:50:24 +00:00 - RC2.R1 implementation start (managed lane enforcement)
1. Problem observed in existing RC2 handler:
   - profile evidence generation used a shared cert-window count posture and did not enforce per-profile window distinctness as a hard gate.
2. Decision implemented:
   - enforce `RC2.R1` directly in managed workflow logic (`dev_full_runtime_cert_managed.yml` RC2 lane),
   - require bounded per-profile admission windows with explicit `start_epoch/end_epoch`,
   - require unique `rc2_profile_<profile_id>_<ts>` execution ids and distinct campaign windows across `steady|burst|soak|replay_window`,
   - require explicit count-completeness proof for profile probe rows,
   - fail-closed with `RC-B10` and mark execution `NON_CLAIMABLE` when evidence-shape checks fail.
3. Why this implementation:
   - removes manual interpretation drift and makes RC2.R1 auditable by artifact content.
4. Next action:
   - dispatch fresh managed RC2 run and adjudicate `r1_evidence_shape_gate.passed` from new durable artifacts.

### 2026-03-02 22:01:09 +00:00 - RC2.R1 implementation execution outcome
1. Managed execution trail:
   - dispatch 1: run `22597329751` (baseline after pre-patch dispatch); RC2 remained on old evidence-shape behavior.
   - dispatch 2: run `22597417989` (first patched run) failed with workflow code defect: missing RC2-lane `timedelta` import.
   - dispatch 3: run `22597480463` (import fixed) executed RC2.R1 checks and failed correctly with `RC-B10` (`R1_CAMPAIGN_WINDOWS_NOT_DISTINCT`), classifying execution non-claimable.
   - dispatch 4: run `22597588836` (window derivation corrected) passed RC2.R1 evidence-shape gate.
2. Authoritative RC2.R1 pass evidence:
   - `runtime_cert_execution_id=rc2_tier0_scorecard_20260302T215921Z`
   - durable root: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T215921Z/`
   - `r1_evidence_shape_gate.passed=true`
   - `execution_claimability=CLAIMABLE` (R1 perspective).
3. RC2 lane status after R1 closure:
   - lane verdict remains `HOLD`,
   - blockers now cleanly reduced to `RC-B4 x4` only (profile thresholds), no `RC-B10`.
4. Decision:
   - RC2.R1 is considered implemented and closed.
   - next immediate work moves to `RC2.R2` bottleneck-localization ramp (managed-only).

### 2026-03-02 22:22:14 +00:00 - RC2.R2 stage-1 managed bottleneck-localization execution
1. Execution command posture:
   - used managed workflow `dev_full_m6f_streaming_active.yml` with `phase_mode=m6f`,
   - pinned identity:
     - `platform_run_id=platform_cert_20260302T182050Z`,
     - `scenario_run_id=scenario_cert_b2e31c46102062661ea43f12a8ceef77`,
   - stage load params:
     - `iterations=30000`,
     - `sleep_seconds=0.0`,
     - stage target interpreted as `R2_STAGE_100_EPS`.
2. Authoritative managed run:
   - workflow run: `22597880983`,
   - source lane execution id: `m6f_p6b_streaming_active_20260302T220724Z`,
   - runtime duration window from evidence:
     - `lane_window_start_epoch=1772489252`,
     - `observation_epoch=1772490041`,
     - `lane_window_seconds=789` (`>=300s` pass).
3. Stage metrics captured (fresh evidence):
   - IG edge bridge:
     - `attempted=30000`,
     - `admitted=28440`,
     - `failed=1560`,
     - `bridge_admit_rate=94.8%`,
     - `observed_eps=36.0456` (`28440/789`).
   - lag posture:
     - `measured_lag=24s`,
     - threshold `10s`,
     - `within_threshold=false`.
   - downstream runtime progression:
     - `WSP=RUNNING`,
     - `SR_READY=RUNNING`.
   - run-window counting surface:
     - `ig_idempotency_count_error=dynamodb_scan_page_limit_reached` (`scan_pages=200`).
4. RC2.R2 decision outcome:
   - first failing stage identified at `R2_STAGE_100_EPS` (target not met),
   - pinned bottleneck owner: `IG_EDGE` (primary),
   - secondary signal retained: `COUNTING_SURFACE` warning only.
5. Progression decision:
   - stop ramp escalation at first failing stage (cost-control aligned),
   - move to `RC2.R3` remediation loop on IG edge path, then rerun `RC2.R2` from stage-100 upward.
6. Generated deterministic local receipt:
   - `runs/dev_substrate/dev_full/cert/runtime/rc2_r2/rc2_r2_bottleneck_localization_20260302T222214Z/rc2_r2_bottleneck_snapshot.json`.
