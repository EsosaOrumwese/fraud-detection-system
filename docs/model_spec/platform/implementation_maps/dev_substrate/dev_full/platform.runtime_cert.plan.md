# Dev Full Runtime Certification Plan

Status: `RC2_HOLD_REMEDIATION_REQUIRED`
Reset baseline as of: `2026-03-02`

## 1) Purpose
This plan certifies runtime behavior against the production truth anchor:
- `docs/experience_lake/platform-production-standard.md`

It is separate from the build-phase map and focused on proving Tier 0..2 runtime claims for `dev_full` with fail-closed evidence discipline.

## 2) Reset Context (Binding)
1. Prior runtime-cert attempt on `2026-03-02` is treated as `SCRAPPED_NON_CLAIMABLE`.
2. No claimability posture may reference scrapped attempt artifacts for pass assertions.
3. Certification restarts clean at `RC0` using this plan as authority.

## 3) Authority Inputs
1. Truth anchor:
   - `docs/experience_lake/platform-production-standard.md`
2. Dev-full closure baseline:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/cert_handoff.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M15.build_plan.md`
3. Execution law sources:
   - `AGENTS.md` (repo root)
   - `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

## 4) Non-Negotiable Certification Laws (Runtime)
1. Managed-only execution law:
   - runtime-cert workloads must execute on pinned managed lanes only;
   - local compute is orchestration/readback only.
2. No-local-compute claim law:
   - evidence produced by local runtime execution is non-claimable;
   - any such occurrence is fail-closed blocker.
3. Fresh-only evidence law:
   - Tier-0 claimability requires evidence produced in the active runtime-cert window.
4. Historical-lineage exclusion law:
   - historical `M*` artifacts may be read for context but cannot satisfy fresh Tier-0 claim evidence.
5. Fail-closed blocker law:
   - unresolved blockers halt lane advancement and final verdict.
6. No silent waivers:
   - waivers must be explicit, time-bounded, and recorded.
7. Deterministic artifact law:
   - required artifacts, IDs, and field sets are fixed per lane.

## 5) Claim Coverage Map (Runtime)
Tier 0 claims to certify:
1. `T0.2` SLO-grade online decision path.
2. `T0.3` Replay-safe streaming correctness.
3. `T0.4` Default observability and diagnosability (runtime slice).
4. `T0.6` Cost-to-outcome control (runtime slice).

### 5.1) Tier 0 thresholds (runtime slice, pinned)
`T0.2` online decision path:
1. decision latency `p95 <= 250 ms`, `p99 <= 500 ms`.
2. success availability `>= 99.5%` for steady/burst/soak windows.
3. non-retryable error rate `<= 0.10%`.

`T0.3` replay-safe streaming:
1. replay integrity mismatch count `= 0`.
2. duplicate side-effect count `= 0`.
3. ingress->core lag `p95 <= 5 s`, `p99 <= 15 s` during steady.
4. unresolved `PUBLISH_UNKNOWN` count `= 0` at lane close.

`T0.4` runtime observability/diagnosability:
1. correlation-id coverage across critical path `>= 99.9%`.
2. runtime `TTD p95 <= 5 min`.
3. runtime `TTDiag p95 <= 15 min`.

`T0.6` runtime cost-to-outcome:
1. unattributed runtime spend count `= 0`.
2. cost attribution coverage `= 100%` for certified runtime runs.
3. cert window must remain below alert-2 without approved exception; alert-3 is hard fail.

Tier 1 claims (best-effort on current stack):
1. Non-leaky runtime-learning boundaries.
2. Drift-to-mitigation runtime loop responsiveness.
3. Training-serving consistency runtime checks.

Tier 2 claims (best-effort):
1. Extended pressure profiles and replay-window diversity.
2. Additional resilience drills beyond minimum Tier 0 set.

## 6) Certification Window and Identity Contract
1. Runtime certification execution id format:
   - `runtime_cert_execution_id=<lane>_<purpose>_<YYYYMMDDThhmmssZ>`
2. Required identity fields in every cert artifact:
   - `platform_run_id`, `scenario_run_id`, `runtime_cert_execution_id`, `captured_at_utc`.
3. Active cert window must be explicit in lane snapshots:
   - `cert_window_start_utc`, `cert_window_end_utc`.

## 7) Runtime Certification Lanes
### RC0 - Claim model lock and metric dictionary
Goal:
1. Pin claim->metric->artifact->drill mappings.

Execution plan (expanded):
1. `RC0.A` fail-closed entry-gate precheck:
   - verify `M15_COMPLETE_GREEN` and `CERTIFICATION_TRACKS_READY`,
   - verify runtime cert durable root is clean for new `runtime_cert_execution_id`,
   - verify no superseded runtime-cert attempt artifacts are being referenced in claim rows.
2. `RC0.B` deterministic claim-matrix materialization:
   - publish Tier-0/1/2 claim rows with gate class (`hard_gate` vs `advisory`),
   - map each claim to explicit metric IDs and required drill families,
   - prohibit free-text-only claim rows.
3. `RC0.C` metric dictionary lock:
   - publish each metric with unit, statistic, window, threshold, and canonical evidence source definition,
   - enforce explicit Tier-0 threshold parity with Section 5.1.
4. `RC0.D` evidence bundle rule lock:
   - publish minimum artifact bundle requirements per claim,
   - enforce deterministic artifact name requirements and required identity fields.
5. `RC0.E` authoritative publication + readback:
   - publish authoritative artifacts to durable S3 first,
   - publish local mirror second for operator convenience,
   - run durable readback checks over all published objects.
6. `RC0.F` determinism and integrity validation:
   - validate artifact schema completeness and identity field presence,
   - validate deterministic serialization digest stability for unchanged inputs,
   - validate no secret/token leakage in published artifacts.
7. `RC0.G` blocker adjudication and lane verdict:
   - evaluate `RC-B1`, `RC-B2`, `RC-B3`, `RC-B8`, `RC-B9`,
   - close lane only with `blocker_count=0` and `next_gate=RC1_READY`.

Pre-execution decision gate (mandatory before RC0 execution):
1. Certification identity strategy must be explicitly pinned:
   - selected option: `A` (`NEW_CAMPAIGN_IDENTITY`) on `2026-03-02`.
2. Pinned clean campaign identity values:
   - `platform_run_id=platform_cert_20260302T182050Z`
   - `scenario_run_id=scenario_cert_b2e31c46102062661ea43f12a8ceef77`
3. Allowed evidence roots for this campaign:
   - durable authoritative root: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/`
   - local mirror root: `runs/dev_substrate/dev_full/cert/runtime/`
4. Forbidden roots for claimability:
   - any path under `.../cert/_scrapped/`
   - any superseded runtime-cert execution IDs from scrapped attempt register in `platform.runtime.cert_notes.md`
   - direct `runs/dev_substrate/dev_full/m*/` evidence paths for Tier-0 pass assertions
5. RC0 execution remains blocked until artifacts reference the pinned campaign identity and allowed roots only.

Runtime budget gate:
1. Target RC0 wall time: `<= 20 min`.
2. Hard stop: `> 45 min` without full deterministic artifact set.
3. No infrastructure mutation is allowed in RC0.

DoD:
- [x] claim matrix for Tier 0..2 runtime slice is published.
- [x] minimum evidence bundle rules are pinned per claim.
- [x] metric dictionary (units, windows, statistics, thresholds) is unambiguous.
- [x] durable publication + readback succeeds for all RC0 artifacts.
- [x] blocker adjudication is complete with `blocker_count=0`.
- [x] blocker register is empty.

RC0 execution closure snapshot (`2026-03-02`):
1. authoritative pass execution:
   - `runtime_cert_execution_id=rc0_claim_model_lock_20260302T182859Z`
   - `verdict=PASS`, `next_gate=RC1_READY`, `blocker_count=0`
2. identity contract used:
   - `platform_run_id=platform_cert_20260302T182050Z`
   - `scenario_run_id=scenario_cert_b2e31c46102062661ea43f12a8ceef77`
3. local mirror root:
   - `runs/dev_substrate/dev_full/cert/runtime/rc0_claim_model_lock_20260302T182859Z/`
4. durable authoritative root:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc0_claim_model_lock_20260302T182859Z/`
5. deterministic RC0 artifact set:
   - `runtime_claim_matrix.json`
   - `runtime_metric_dictionary.json`
   - `runtime_evidence_bundle_rules.json`
   - `rc0_execution_snapshot.json`

### RC1 - Runtime evidence inventory and fresh-gap register
Goal:
1. Produce deterministic inventory and classify fresh evidence gaps.

Execution plan (expanded):
1. `RC1.A` entry-gate precheck:
   - require authoritative `RC0` pass execution (`rc0_claim_model_lock_20260302T182859Z`),
   - verify failed RC0 attempts are non-claimable and quarantined from runtime claim roots,
   - verify active campaign identity remains pinned (`platform_run_id`, `scenario_run_id`).
2. `RC1.B` evidence-discovery scope lock:
   - lock authoritative discovery roots (durable first) and local mirrors (context only),
   - classify roots into `claimable_candidate`, `historical_context`, `scrapped_non_claimable`,
   - deny `_scrapped` and superseded execution IDs for Tier-0 pass eligibility.
3. `RC1.C` deterministic evidence inventory materialization:
   - emit metric-level rows for all Tier-0 required metrics,
   - include row fields: `metric_id`, `required_artifact`, `evidence_ref`, `captured_at_utc`, `lineage_class`, `execution_posture`, `readability_status`,
   - enforce deterministic row ordering and stable schema versioning.
4. `RC1.D` fresh-gap register derivation:
   - for every Tier-0 metric lacking `EVIDENCED_FRESH` lineage, emit explicit gap rows,
   - include `gap_reason` (`MISSING`, `HISTORICAL_ONLY`, `SCRAPPED_ONLY`, `UNREADABLE`),
   - map each gap row to intended remediation lane (`RC2` scorecard or `RC3` drill pack).
5. `RC1.E` no-pass claimability posture lock:
   - RC1 must not mark any Tier-0 claim as pass/fail final,
   - RC1 output posture is inventory + gap adjudication only (`NOT_EVALUATED_IN_RC1` claim status).
6. `RC1.F` authoritative publication + readback:
   - publish authoritative artifacts to durable S3 first,
   - publish local mirror second,
   - hash/readback verify every published RC1 artifact.
7. `RC1.G` blocker adjudication and lane verdict:
   - evaluate structural blockers `RC-B1`, `RC-B2`, `RC-B3`, `RC-B8`, `RC-B9`,
   - fresh-evidence gaps are recorded in gap register and do not bypass blocker semantics,
   - lane closes only with explicit verdict and next gate (`RC2_READY_WITH_GAP_REGISTER` or `RC1_REMEDIATION_REQUIRED`).

Pre-execution decision gate (mandatory before RC1 execution):
1. Pin `rc1_runtime_evidence_inventory_<timestamp>` execution id.
2. Pin certification window for fresh classification:
   - `cert_window_start_utc` from active campaign,
   - `cert_window_end_utc` at RC1 snapshot closure.
3. Pin discovery roots and denylist roots for claimability classification.
4. Pin remediation routing for each gap reason (`RC2` vs `RC3`).

Runtime budget gate:
1. Target RC1 wall time: `<= 25 min`.
2. Hard stop: `> 60 min` without full inventory + gap-register artifacts.
3. No infrastructure mutation is allowed in RC1.

Deterministic RC1 artifacts:
1. `runtime_evidence_inventory.json`
2. `runtime_fresh_gap_register.json`
3. `rc1_execution_snapshot.json`

DoD:
- [x] evidence inventory is complete and deterministic.
- [x] fresh-gap register explicitly lists all Tier-0 missing metrics.
- [x] no claim row is marked pass in RC1.
- [x] durable publication + readback succeeds for all RC1 artifacts.
- [x] blocker adjudication and next gate are explicit.

RC1 execution closure snapshot (`2026-03-02`):
1. authoritative pass execution:
   - `runtime_cert_execution_id=rc1_runtime_evidence_inventory_20260302T191532Z`
   - `verdict=PASS`, `next_gate=RC2_READY_WITH_GAP_REGISTER`, `blocker_count=0`
2. identity contract used:
   - `platform_run_id=platform_cert_20260302T182050Z`
   - `scenario_run_id=scenario_cert_b2e31c46102062661ea43f12a8ceef77`
3. local run root:
   - `runs/dev_substrate/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T191532Z/`
4. durable authoritative root:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T191532Z/`
5. deterministic RC1 artifact set:
   - `runtime_evidence_inventory.json`
   - `runtime_fresh_gap_register.json`
   - `rc1_execution_snapshot.json`
6. RC1 outcome posture:
   - `tier0_gap_count=15` captured as explicit remediation input for RC2/RC3.
7. managed revalidation pass:
   - workflow run `22591814086` produced `runtime_cert_execution_id=rc1_runtime_evidence_inventory_20260302T192109Z`
   - verdict unchanged: `PASS`, `next_gate=RC2_READY_WITH_GAP_REGISTER`, `blocker_count=0`, `tier0_gap_count=15`
   - durable root: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_20260302T192109Z/`

### RC2 - Tier 0 runtime scorecard certification (steady/burst/soak + replay-window)
Goal:
1. Certify Tier-0 runtime scorecard against pinned profile floors.

Execution plan (expanded):
1. `RC2.A` fail-closed entry gate:
   - require latest authoritative RC1 pass snapshot (`next_gate=RC2_READY_WITH_GAP_REGISTER`),
   - load active gap register (`tier0_gap_count=15`) as mandatory remediation input,
   - reject execution if identity triplet differs from pinned campaign (`platform_run_id`, `scenario_run_id`, `runtime_cert_execution_id` envelope).
2. `RC2.B` capability-lane exposure and lock (phase-coverage law):
   - authority/handles: managed workflow name, role ARN, profile runner handles pinned,
   - identity/IAM: OIDC-only assumption with cert-prefix S3 read/write and no static creds,
   - network: source/sink endpoints and allowed traffic paths pinned before run,
   - data stores: S3 evidence roots and any profile input datasets pinned read-only,
   - messaging: profile ingress stream/topic handles pinned with replay posture declared,
   - secrets: secret sources declared; no secret values in runtime artifacts/logs,
   - observability/evidence: metric capture points + scorecard artifact schema pinned,
   - rollback/rerun: deterministic rerun strategy and non-claimable classification rules pinned,
   - teardown: post-run cleanup and idle-safe posture pinned (`desired_count=0` where applicable),
   - budget: performance + cost envelopes pinned before dispatch.
3. `RC2.C` mandatory profile execution contract:
   - steady: `500 eps`, `30 min`, sample `>= 900,000`,
   - burst: `1,500 eps`, `10 min`, sample `>= 900,000`,
   - soak: `300 eps`, `6 h logical window`, sample `>= 6,480,000`,
   - replay-window: `24 h logical window`, sample `>= 10,000,000`,
   - all profiles must run under managed execution posture (`NO_LOCAL_COMPUTE` law).
4. `RC2.D` deterministic metric capture and aggregation:
   - capture throughput, success availability, non-retryable errors, decision latency `p50/p95/p99`,
   - capture replay integrity mismatches, duplicate side effects, ingress->core lag `p50/p95/p99`,
   - capture observability/diagnostic SLI proxies and runtime cost attribution coverage,
   - compute profile summaries using fixed window math and deterministic serialization ordering.
5. `RC2.E` Tier-0 threshold evaluation and claim adjudication:
   - evaluate `T0.2`, `T0.3`, `T0.4`, `T0.6` against Section 5.1 thresholds,
   - produce per-claim status: `PASS`, `HOLD_REMEDIATION_REQUIRED`, or `NOT_EVALUABLE`,
   - map every failed/unknown metric to explicit blocker IDs and remediation owners.
6. `RC2.F` RC1 gap-to-remediation binding:
   - for each RC1 gap row, bind either:
     - `RESOLVED_BY_RC2_PROFILE_EVIDENCE`, or
     - `DEFER_RC3_DRILL_REQUIRED` with explicit drill family target,
   - unresolved rows remain open blockers for Tier-0 final closure.
7. `RC2.G` authoritative publication and readback:
   - durable-first publication to S3 runtime cert root,
   - local mirror copy second (non-authoritative),
   - hash/readback verify each RC2 artifact and fail closed on mismatch.
8. `RC2.H` blocker adjudication and lane verdict:
   - evaluate `RC-B3`, `RC-B4`, `RC-B8`, `RC-B9` as lane-critical blockers,
   - if any Tier-0 claim remains `HOLD`, lane verdict remains remediation posture,
   - lane next-gate outcomes:
     - `RC3_READY_WITH_SCORECARD` when `blocker_count=0`,
     - `RC2_REMEDIATION_REQUIRED` when any blocker persists.
9. `RC2.I` performance and cost gates (pre-implementation budgets):
   - complexity target: object/metric scans `O(N + M)` with indexed lookups; no quadratic joins,
   - runtime targets:
     - steady `<= 45 min` wall time,
     - burst `<= 20 min`,
     - soak logical-window evidence with wall-time target `<= 120 min` (escalate if infeasible),
     - replay-window evidence wall-time target `<= 120 min`,
   - hard-stop rule: stop on unexplained stall/regression and complete bottleneck analysis before rerun,
   - cost envelope must publish planned vs observed spend by profile and lane.
10. `RC2.J` closure sync:
   - publish lane snapshot with verdict, next gate, blockers, and open Tier-0 holds,
   - synchronize runtime cert notes + impl map + logbook with execution receipts and unresolved set.

Pre-execution decision gate (mandatory before RC2 execution):
1. Pin `runtime_cert_execution_id=rc2_tier0_scorecard_<timestamp>`.
2. Pin authoritative upstream RC1 execution ID for this run.
3. Pin managed workflow handler/version and exact dispatch inputs.
4. Pin profile input authorities (datasets/streams), time-window semantics, and load model parameters.
5. Pin remediation routing owner for each current gap reason (`RC2` profile evidence vs `RC3` drill evidence).
6. Pin explicit performance envelope + cost envelope and hard-stop conditions.
7. Pin rerun/quarantine posture for failed/non-claimable RC2 attempts.

Runtime budget gate:
1. Target RC2 orchestration wall time: `<= 180 min` (including profile execution + publication + readback).
2. Hard stop: any profile exceeding `+50%` of its budget without recovery trend.
3. No unmanaged infrastructure mutation is allowed in RC2.

Deterministic RC2 artifacts:
1. `runtime_scorecard_profiles.json`
2. `runtime_scorecard_claim_adjudication.json`
3. `runtime_scorecard_gap_resolution.json`
4. `runtime_blocker_register.json`
5. `rc2_execution_snapshot.json`
6. `runtime_cost_outcome_receipt.json`

DoD:
- [ ] all mandatory profiles have fresh managed-run evidence.
- [ ] each profile meets pinned sample/eps/duration thresholds or is explicitly marked `HOLD_REMEDIATION_REQUIRED`.
- [ ] required `p50/p95/p99` distributions are present and threshold-adjudicated.
- [ ] every RC1 gap row is resolved by RC2 evidence or explicitly deferred to RC3 drill evidence.
- [ ] blocker register and next gate are explicit and deterministic.
- [ ] durable publication + hash readback passes for all RC2 artifacts.

RC2 strict remediation sequence (production-envelope, no floor downgrade):
1. `RC2.R1` evidence-shape correctness gate (must pass before load scale):
   - each profile (`steady|burst|soak|replay_window`) must have its own campaign execution id and distinct campaign window,
   - profile metrics must be computed from campaign-bounded windows (no shared-window reuse across profiles),
   - admission counting must be complete (no scan truncation posture such as fixed page limits),
   - if evidence shape fails, classify run `NON_CLAIMABLE` and stop.
2. `RC2.R2` managed bottleneck-localization ramp:
   - run managed-only ramp campaigns at `100 -> 250 -> 500 -> 1000 -> 1500 eps`,
   - fixed short duration per ramp stage (`>=5 min`) with deterministic receipts,
   - capture lane metrics per stage:
     - IG edge admit/error posture,
     - run-window admissions and ingestion lag,
     - downstream bus and core-lane progression,
   - identify first failing stage and pin explicit bottleneck owner (`IG_EDGE`, `BUS`, `CORE_RUNTIME`, `COUNTING_SURFACE`).
3. `RC2.R3` lane remediation loop (fail-closed):
   - remediate only identified bottleneck lane(s),
   - rerun `RC2.R2` from failed stage upward until target stage is stable,
   - no threshold edits, no waiver, no historical substitution.
4. `RC2.R4` mandatory profile campaigns at pinned floors:
   - `steady`: `500 eps`, `30 min`, sample `>=900,000`,
   - `burst`: `1,500 eps`, `10 min`, sample `>=900,000`,
   - `soak`: `300 eps`, `6 h`, sample `>=6,480,000`.
5. `RC2.R5` replay-window campaign:
   - managed replay-window campaign with sample `>=10,000,000`,
   - explicit replay integrity and duplicate-side-effect surfaces included in profile evidence.
6. `RC2.R6` RC2 scorecard closure:
   - execute RC2 rollup using only `RC2.R4/R5` fresh campaign execution ids,
   - pass criteria: `blocker_count=0`, Tier-0 holds cleared, next gate `RC3_READY_WITH_SCORECARD`.

RC2 strict remediation DoD:
- [x] `RC2.R1` evidence-shape correctness gate passes.
- [x] bottleneck owner is explicitly identified from `RC2.R2` stage evidence.
- [x] `RC2.R3` stage-100 rerun is stabilized with `blocker_count=0` on fresh managed evidence.
- [ ] all required profile campaigns meet pinned floors with fresh managed evidence.
- [ ] replay-window campaign meets pinned sample floor.
- [ ] RC2 rollup closes with `overall_pass=true` and `blocker_count=0`.

RC2 execution closure snapshot (`2026-03-02`):
1. managed execution:
   - workflow run `22592516146` (branch `cert-platform`, head `7c996d1b7`)
   - `runtime_cert_execution_id=rc2_tier0_scorecard_20260302T193820Z`
2. identity contract used:
   - `platform_run_id=platform_cert_20260302T182050Z`
   - `scenario_run_id=scenario_cert_b2e31c46102062661ea43f12a8ceef77`
   - upstream pins:
     - `rc0_claim_model_lock_20260302T182859Z`
     - `rc1_runtime_evidence_inventory_20260302T192109Z`
3. lane verdict:
   - `overall_pass=false`, `verdict=HOLD`, `next_gate=RC2_REMEDIATION_REQUIRED`
   - `blocker_count=4` (`RC-B4` for steady, burst, soak, replay-window missing fresh profile evidence)
   - `tier0_hold_count=4` (`T0.2`, `T0.3`, `T0.4`, `T0.6`)
4. durable authoritative root:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T193820Z/`
5. deterministic RC2 artifact set materialized:
   - `runtime_scorecard_profiles.json`
   - `runtime_scorecard_claim_adjudication.json`
   - `runtime_scorecard_gap_resolution.json`
   - `runtime_blocker_register.json`
   - `runtime_cost_outcome_receipt.json`
   - `rc2_execution_snapshot.json`
6. RC2.R1 managed enforcement + verification refresh (`2026-03-02`):
   - workflow implementation commits:
     - `9232c705a` (`ci: enforce rc2 r1 evidence-shape gate`)
     - `c9f027467` (`fix: import timedelta in rc2 runtime-cert lane`)
     - `e737f67fb` (`fix: keep rc2 profile windows distinct for r1 gate`)
   - authoritative run:
     - workflow run `22597588836` (`cert-platform`)
     - `runtime_cert_execution_id=rc2_tier0_scorecard_20260302T215921Z`
     - durable root: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T215921Z/`
   - RC2.R1 gate result:
     - `r1_evidence_shape_gate.passed=true`
     - checks passed: profile coverage complete, execution ids unique, campaign windows distinct + bounded, probe count completeness true.
   - remaining blockers after RC2.R1 closure:
     - `RC-B4 x4` (steady, burst, soak, replay_window thresholds not met),
     - next gate remains `RC2_REMEDIATION_REQUIRED`.
7. RC2.R2 managed bottleneck-localization stage execution (`2026-03-02`):
   - stage executed (first ramp stage):
     - target stage: `100 eps` (`R2_STAGE_100_EPS`)
     - workflow run: `22597880983` (`dev-full-m6f-streaming-active`, branch `cert-platform`)
     - source execution id: `m6f_p6b_streaming_active_20260302T220724Z`
     - local receipt: `runs/dev_substrate/dev_full/cert/runtime/rc2_r2/rc2_r2_bottleneck_localization_20260302T222214Z/rc2_r2_bottleneck_snapshot.json`
   - measured lane metrics:
     - lane window: `789s` (`>=5 min` satisfied),
     - IG edge bridge: `attempted=30000`, `admitted=28440`, `failed=1560`, `observed_eps=36.0456`,
     - lag posture: `24s` vs threshold `10s` (`within_threshold=false`),
     - downstream lane states: `WSP=RUNNING`, `SR_READY=RUNNING`,
     - run-window admission count probe: `ig_idempotency_count_error=dynamodb_scan_page_limit_reached` (counting-surface warning).
   - first failing stage:
     - `R2_STAGE_100_EPS` (did not meet stage target).
   - pinned bottleneck owner:
     - `IG_EDGE` (primary).
   - secondary diagnostic signal:
     - `COUNTING_SURFACE` (`dynamodb_scan_page_limit_reached`) recorded as non-primary.
   - progression decision:
     - stop ramp escalation at first failing stage to avoid unnecessary spend,
     - proceed to `RC2.R3` remediation loop focused on IG edge path.
8. RC2.R3 managed remediation loop closure (`2026-03-02`):
   - workflow commits (workflow-only remediation):
     - `524c0028c` (`ci: tune rc2 r3 ig bridge and ddb scan sizing`)
     - `3b34e72a6` (`ci: reconcile m6f lag at capture start for rc2 r3`)
   - validation run 1 (`22599864377`):
     - execution id: `m6f_p6b_streaming_active_20260302T230526Z`
     - bridge posture: `attempted=30000`, `admitted=29890`, `failed=110`
     - counting surface: `ig_idempotency_count=29890`, `scan_pages=304`, no truncation error
     - residual blocker: `M6P6-B4` only (`measured_lag=43s` vs `10s`)
   - validation run 2 (`22600392998`):
     - execution id: `m6f_p6b_streaming_active_20260302T232217Z`
     - bridge posture: `attempted=30000`, `admitted=29873`, `failed=127`
     - lag posture: `measured_lag=1s`, source `ig_admission_freshness_seconds_capture_start_epoch`
     - lane verdict: `overall_pass=true`, `blocker_count=0`, `next_gate=M6.G_READY`
   - closure decision:
     - RC2.R3 stage-100 stabilization is complete on fresh managed evidence.
     - Proceed to RC2.R2 upward stages (`250 -> 500 -> 1000 -> 1500`) and then RC2.R4/R5.

### RC2 Remediation Program - Close `RC-B4` Before RC3/RC6
Goal:
1. Eliminate current RC2 blockers by producing fresh managed profile evidence for all mandatory profiles, then re-run RC2 adjudication to close Tier-0 holds.

Anti-repeat execution law (new, binding):
1. RC2 adjudication dispatch is blocked unless a preflight manifest proves all four profile families are present as fresh claimable managed evidence in the active campaign window:
   - `steady`, `burst`, `soak`, `replay_window`.
2. If manifest completeness is false for any profile, execution must stop at planning/remediation and must not dispatch RC2 adjudication.
3. Any run violating this gate is classified `NON_CLAIMABLE_SEQUENCE_BREACH`.

Remediation phases:
1. `RC2R.A` decision closure gate:
   - pin remediation execution IDs and profile ownership order,
   - pin managed runner mechanism for profile generation,
   - pin profile window semantics (logical vs wall-time acceptance for soak/replay).
2. `RC2R.B` managed profile generation lane implementation:
   - implement repository-tracked managed handlers for:
     - `rc2_profile_steady_<timestamp>`
     - `rc2_profile_burst_<timestamp>`
     - `rc2_profile_soak_<timestamp>`
     - `rc2_profile_replay_window_<timestamp>`
   - each emits deterministic profile snapshot artifacts and publishes durable-first.
3. `RC2R.C` per-profile threshold verification:
   - evaluate sample/eps/duration requirements per profile,
   - fail closed per profile if requirements are not met,
   - quarantine failed profile attempts as non-claimable.
4. `RC2R.D` profile-evidence manifest gate:
   - emit `runtime_profile_evidence_manifest.json` with one row per required profile:
     - `profile_id`, `execution_id`, `captured_at_utc`, `platform_run_id`, `scenario_run_id`,
     - `meets_thresholds`, `claimable`, `evidence_ref`.
   - `manifest_complete=true` only when all four rows are claimable + threshold-pass.
5. `RC2R.E` RC2 re-adjudication run:
   - dispatch fresh `rc2_tier0_scorecard_<timestamp>` adjudication only after manifest gate passes,
   - require `blocker_count=0` and `tier0_hold_count=0` for remediation closure.
6. `RC2R.F` closure sync and gate transition:
   - update runtime notes/plan/logbook/impl map with closure receipts,
   - only then transition next gate to `RC3_READY_WITH_SCORECARD`.

Pre-execution decision gate for remediation (mandatory):
1. Pin exact managed workflow topology:
   - profile generation workflow ID (or lane extension) and adjudication workflow ID.
2. Pin per-profile execution budget and stop conditions.
3. Pin fallback policy when a profile misses thresholds (`rerun_count`, quarantine rules, escalation trigger).
4. Pin manifest schema/version and the exact completeness predicate.
5. Pin RC2 re-adjudication input contract to consume only manifest-approved profile evidence.

Remediation deterministic artifacts:
1. `rc2_profile_steady_snapshot.json`
2. `rc2_profile_burst_snapshot.json`
3. `rc2_profile_soak_snapshot.json`
4. `rc2_profile_replay_window_snapshot.json`
5. `runtime_profile_evidence_manifest.json`
6. `runtime_scorecard_profiles.json` (re-adjudicated)
7. `runtime_scorecard_claim_adjudication.json` (re-adjudicated)
8. `runtime_scorecard_gap_resolution.json` (re-adjudicated)
9. `runtime_blocker_register.json` (re-adjudicated)
10. `runtime_cost_outcome_receipt.json` (re-adjudicated)
11. `rc2_execution_snapshot.json` (re-adjudicated)

Remediation DoD:
- [ ] fresh managed evidence exists for all four mandatory profiles.
- [ ] manifest completeness gate is true and references only claimable evidence.
- [ ] RC2 re-adjudication closes with `blocker_count=0`.
- [ ] Tier-0 claims `T0.2/T0.3/T0.4/T0.6` are no longer `HOLD`.
- [ ] next gate transitions to `RC3_READY_WITH_SCORECARD`.
- [ ] anti-repeat sequence gate is recorded as satisfied.

### RC3 - Tier 0 runtime drill-pack certification
Goal:
1. Certify mandatory failure-mode runtime drills.

Mandatory drill families:
1. `DR-02` replay/backfill integrity.
2. `DR-03` lag spike and recovery.
3. `DR-04` schema evolution safety.
4. `DR-05` dependency outage with degrade/recover.
5. `DR-07` runtime cost guardrail response.

DoD:
- [ ] each drill row includes scenario, expected behavior, observed outcomes, integrity checks, recovery bound.
- [ ] each mandatory drill is evidenced with fresh managed-run artifacts.
- [ ] blocker register is empty.

### RC4 - Tier 1 runtime differentiator pack
Goal:
1. Grade Tier-1 runtime claims with explicit evidence posture.

DoD:
- [ ] Tier-1 claims graded `pass|partial|not_proven` with evidence refs.
- [ ] unresolved items are explicit and non-silent.

### RC5 - Tier 2 runtime stretch pack
Goal:
1. Capture Tier-2 runtime proofs and unresolved maturity gaps.

DoD:
- [ ] Tier-2 claims graded `pass|partial|not_proven`.
- [ ] unresolved maturity items are explicit.

### RC6 - Runtime rollup and final verdict
Goal:
1. Emit deterministic runtime certification verdict.

DoD:
- [ ] Tier-0 claims are graded with explicit fresh evidence and no active Tier-0 blockers.
- [ ] Tier-1/2 grading is explicit.
- [ ] final verdict artifact is deterministic and complete.

Tier-0 gate precedence (binding):
1. If any Tier-0 claim is `HOLD`/blocked, runtime certification is automatically `FAILED_NEEDS_REMEDIATION`.
2. When `FAILED_NEEDS_REMEDIATION` is active, final rollup execution (`RC6`) is blocked and must not emit a claimable certification completion verdict.
3. Remediation closure of all active Tier-0 blockers is mandatory before `RC6` may execute.

## 8) Runtime Artifact Contract (Deterministic)
Durable authority root (authoritative):
1. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/<runtime_cert_execution_id>/`

Local mirror root (non-authoritative convenience copy):
1. `runs/dev_substrate/dev_full/cert/runtime/<runtime_cert_execution_id>/`

Required runtime outputs (rollup scope):
1. `runtime_claim_matrix.json`
2. `runtime_scorecard_profiles.json`
3. `runtime_drill_bundle.json`
4. `runtime_blocker_register.json`
5. `runtime_certification_verdict.json`

## 9) Runtime Blocker Taxonomy
1. `RC-B1` claim mapping incompleteness.
2. `RC-B2` metric definition/window ambiguity or uncomputable required distribution.
3. `RC-B3` missing/unreadable required evidence artifact.
4. `RC-B4` scorecard profile failure (sample/eps/duration/replay floor).
5. `RC-B5` drill integrity or recovery-bound incompleteness.
6. `RC-B6` non-deterministic rollup or verdict artifact.
7. `RC-B7` unresolved Tier-0 claim in final verdict.
8. `RC-B8` certification execution-posture violation (`NO_LOCAL_COMPUTE` or `NON_MANAGED_EXECUTION`).
9. `RC-B9` Tier-0 claim depends on historical-lineage evidence (non-fresh claimability breach).

## 10) Acceptance Posture
1. Runtime certification is `GREEN` only when all Tier-0 claims are fresh-evidence pass and blocker-free.
2. Tier-1/Tier-2 may be partial but must be explicit.
3. Any ambiguity defaults to fail-closed `HOLD`.
4. Tier-1/Tier-2 execution may continue for maturity evidence while Tier-0 is `HOLD`, but this never overrides Tier-0 failure posture and cannot unlock final rollup.

## 11) Point-X Stitch Output (Runtime contribution)
Published only after runtime + ops/gov verdicts are both present:
1. `dev_full_point_x_summary.md`
2. `tier0_claimability_table.json`
3. references to:
   - `runtime_certification_verdict.json`
   - `ops_gov_certification_verdict.json`
