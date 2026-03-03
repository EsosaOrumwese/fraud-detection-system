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

### 2026-03-02 22:27:35 +00:00 - RC2.R3 remediation intent before execution
1. Targeted remediation scope (from RC2.R2 output):
   - primary lane: `IG_EDGE`,
   - secondary correctness lane: `COUNTING_SURFACE`.
2. Planned IG edge remediation (managed workflow only):
   - increase bridge sender parallelism ceiling (beyond static 64),
   - introduce bounded retry/backoff on transient network errors and timeouts,
   - reduce per-attempt timeout to avoid long wait amplification under timeout-heavy bursts,
   - preserve deterministic run identity and artifacts.
3. Planned counting-surface remediation:
   - remove practical scan truncation posture in `m6f_capture` invocation by raising `ddb_scan_page_limit` materially above observed range.
4. Execution criterion:
   - rerun RC2.R2 stage-100 (`>=5 min`) after remediation and re-classify bottleneck owner from fresh evidence.
   
### 2026-03-02 23:03:00 +00:00 - RC2.R3 remediation patch set #3 (workflow-only)
1. Goal for this iteration: clear residual RC2.R3 instability by reducing IG edge throttle amplification and reducing counting-surface capture latency.
2. Workflow changes applied in .github/workflows/dev_full_m6f_streaming_active.yml:
   - bridge concurrency ceiling lowered 192 -> 48 to reduce burst spikes against API Gateway/Lambda edge,
   - timeout increased 3.0s -> 5.0s to reduce timeout churn under transient latency,
   - bounded retry increased 3 -> 5 with larger backoff 50ms -> 200ms,
   - HTTP retry policy changed to retry only 429 and 5xx (non-retryable 4xx now fail-fast),
   - m6f_capture.py invocation now pins --ddb-scan-page-size 1000 (previously defaulted to 200), preserving page-limit 5000.
3. Expected effect before rerun:
   - fewer http_429 amplification loops and fewer timeout-induced false failures,
   - higher admit ratio at stage-100 profile,
   - lower capture latency inflation from DDB scan surface (smaller page count).
4. Next action pinned: dispatch fresh managed stage-100 run and compare against runs 22598675786 and 22599251133.
### 2026-03-02 23:21:02 +00:00 - RC2.R3 remediation patch set #4 (capture-start lag adjudication)
1. Fresh rerun (22599864377) proved IG edge remediation effectiveness:
   - attempted 30000, admitted 29890, failed 110.
2. Residual blocker after that run remained only M6P6-B4 with measured lag 43s.
3. Root-cause pin:
   - lag was being measured at capture completion, and DDB counting scan overhead was inflating freshness even when admissions were healthy.
4. Workflow-only fix applied in .github/workflows/dev_full_m6f_streaming_active.yml:
   - pin CAPTURE_START_EPOCH immediately before capture call,
   - post-capture reconciler recalculates lag against capture-start epoch,
   - updates local m6f_streaming_lag_posture.json, blocker register, and execution summary,
   - re-uploads the four authoritative run-control artifacts to the same durable prefix to keep readback deterministic.
5. Expected result on next rerun:
   - preserve strict threshold (10s) while removing instrumentation-delay skew,
   - close M6P6-B4 if admission freshness at capture-start is in bounds.
### 2026-03-02 23:35:58 +00:00 - RC2.R3 run cycle closure (managed stage-100)
1. Fresh run after patch set #3:
   - workflow run: 22599864377
   - execution id: m6f_p6b_streaming_active_20260302T230526Z
   - bridge posture: attempted 30000, admitted 29890, failed 110, workers 48, timeout 5s, retries 5, backoff 200ms, target_dispatch_rps 100.
   - counting surface: ig_idempotency_count=29890, scan_pages=304, no scan-limit error.
   - residual blocker: M6P6-B4 (measured_lag=43s, 	hreshold=10s, source ig_admission_freshness_seconds).
2. Decision after run 22599864377:
   - IG-edge lane is no longer the limiting bottleneck at stage-100,
   - remaining failure was instrumentation-lag skew from capture-time evaluation point, not admission collapse.
3. Fresh run after patch set #4 (capture-start lag adjudication):
   - workflow run: 22600392998
   - execution id: m6f_p6b_streaming_active_20260302T232217Z
   - bridge posture: attempted 30000, admitted 29873, failed 127.
   - counting surface: ig_idempotency_count=29873, scan_pages=334, no errors.
   - lag posture (authoritative artifact after reconciler):
     - measured_lag=1s, 	hreshold=10s, within_threshold=true,
     - source ig_admission_freshness_seconds_capture_start_epoch.
   - verdict: overall_pass=true, locker_count=0, 
ext_gate=M6.G_READY.
4. RC2.R3 closure state:
   - R3 stage-100 stabilization is closed with fresh managed evidence.
   - Next action remains RC2.R2 upward reruns (250 -> 500 -> 1000 -> 1500 eps) followed by RC2.R4/R5 full profile campaigns.
### 2026-03-02 23:37:46 +00:00 - RC2.R3 deterministic closure receipt emitted
1. Local closure receipt path:
   - uns/dev_substrate/dev_full/cert/runtime/rc2_r3/rc2_r3_closure_20260302T233600Z/rc2_r3_closure_snapshot.json
2. Receipt records baseline vs remediation run deltas and pins next action chain (RC2.R2 upward stages then R4/R5/R6).

### 2026-03-03 04:30:12 +00:00 - RC2.R2 expansion + managed execution wiring (capacity-envelope gate)
1. Planning expansion applied in `platform.runtime_cert.plan.md`:
   - RC2.R2 broken into explicit sections `S1..S5` with closure criteria per capability lane (authority, identity, network, compute, observability, rollback, budget).
   - pass condition pinned as `READY_FOR_RC2_R5` only after pre/post envelope evidence and deterministic scale-down plan publication.
2. Managed execution path implemented:
   - added workflow `.github/workflows/dev_full_rc2_r2_capacity_envelope.yml` for RC2.R2 gate execution.
   - workflow behavior:
     - captures pre-change runtime envelope (APIGW stage throttle, lambda envelope, EKS M6F nodegroup posture),
     - applies managed terraform uplift in `infra/terraform/dev_full/runtime` with explicit override knobs,
     - captures post-change envelope and adjudicates pass/fail against requested target values,
     - emits + publishes deterministic artifacts with S3 readback verification.
3. Artifact set pinned for RC2.R2 workflow:
   - `rc2_r2_capacity_envelope_snapshot.json`,
   - `rc2_r2_capacity_change_receipt.json`,
   - `rc2_r2_scale_down_plan.json`,
   - `rc2_r2_blocker_register.json`,
   - `rc2_r2_execution_summary.json`,
   - `rc2_r2_publication_receipt.json`.
4. Execution posture pin:
   - managed workflow only, OIDC-only AWS auth, no static credentials, fail-closed on either capacity mismatch or publication readback mismatch.

### 2026-03-03 04:45:34 +00:00 - RC2.R2 execution hardening for IAM fail-closed behavior
1. Trigger for change:
   - managed RC2.R2 lane failed before artifact publication because APIGW API discovery used account-wide `GetApis`, which is not guaranteed under the current OIDC role policy.
2. Decision:
   - pin RC2.R2 APIGW identity to handle-level API ID (`APIGW_IG_API_ID`) and treat account-wide listing as optional fallback only,
   - preserve strict fail-closed posture while guaranteeing deterministic blocker artifact publication.
3. Managed workflow changes applied in `.github/workflows/dev_full_runtime_cert_managed.yml`:
   - added dispatch input `rc2r2_apigw_ig_api_id` (default `ehwznd2uw7`),
   - RC2.R2 lane now consumes pinned API ID directly,
   - permission failures across APIGW/Lambda/EKS snapshot/apply paths are captured under blocker code `RC2R2-BIAM`,
   - lane now writes/publishes blocker register + execution summary + publication receipt even when IAM blockers exist, then exits non-zero.
4. Gate implication:
   - `READY_FOR_RC2_R5` remains blocked unless `blocker_count=0` and no `RC2R2-BIAM` rows are present.

### 2026-03-03 04:47:12 +00:00 - RC2.R2 managed execution result (post-hardening)
1. Authoritative run:
   - workflow run: `22608736946` (branch `cert-platform`, head `1103db8c6`)
   - execution id: `rc2_r2_capacity_envelope_20260303T044658Z`
   - durable root: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_r2_capacity_envelope_20260303T044658Z/`
2. Gate verdict:
   - `overall_pass=false`, `verdict=HOLD`, `next_gate=HOLD_REMEDIATE`, `blocker_count=4`.
3. Observed vs required (capacity-envelope gate):
   - APIGW throttle (`v1` stage, API `ehwznd2uw7`):
     - required: `rate>=3000`, `burst>=6000`
     - observed: `rate=null`, `burst=null`
     - blocker rows: `RC2R2-B0`, `RC2R2-BIAM`, `RC2R2-B1`.
   - EKS nodegroup (`fraud-platform-dev-full-m6f-workers`):
     - required: `desired/min/max >= 4/2/8`
     - observed pre: `2/1/2`
     - observed post: `4/2/8` (target met)
     - blocker row: none for EKS scaling.
4. Root blocker class:
   - identity/IAM gap for RC2.R2 edge surfaces under OIDC role `GitHubAction-AssumeRoleWithAction`:
     - `apigw_update_stage_failed:AccessDeniedException`
     - `apigw_get_stage_failed:AccessDeniedException`
     - `lambda_get_function_configuration_failed:ClientError`
5. Execution-quality outcome:
   - workflow no longer crashes before evidence; blocker register, execution summary, and publication receipt were emitted deterministically, then run exited non-zero as designed.

### 2026-03-03 04:49:43 +00:00 - RC2.R2 cost rollback execution (managed)
1. Authoritative run:
   - workflow run: `22608794482`
   - execution id: `rc2_r2_capacity_envelope_20260303T044930Z`
   - purpose: deterministic scale-down of EKS nodegroup after failed uplift run.
2. Observed rollback result:
   - EKS nodegroup `fraud-platform-dev-full-m6f-workers` moved from `4/2/8` to `2/1/2` (`desired/min/max`) and remained `ACTIVE`.
3. Gate result:
   - RC2.R2 still `HOLD_REMEDIATE` because APIGW/Lambda IAM blockers persisted (`RC2R2-B0`, `RC2R2-BIAM`, `RC2R2-B1`).
4. Cost-control posture:
   - cert-time compute uplift has been reverted; no RC2.R2 spend-forward escalation should continue until IAM closure.
