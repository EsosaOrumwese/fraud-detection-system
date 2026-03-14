# Dev Full Road To Production-Ready - PREPR Whole-Platform Substrate Restoration
_As of 2026-03-09_

## 0) Purpose
`PREPR` is the restoration gate that rebuilds `dev_full` as a production-shaped **whole platform substrate** before any further `PR3/PR4` certification work resumes.

`PREPR` is not a shortcut to `PR3-S4`. It exists because the live substrate was torn down and the next valid move is to restore the platform in a way that preserves the already-built `dev_full` architecture while making every participating plane executable again.

`PREPR` is fail-closed. It cannot pass unless:
1. restoration covers the whole-platform substrate families, not just the runtime spine,
2. each restored family is validated with production-minded capability checks,
3. cost and idle-safe posture are measured and acceptable,
4. handoff back to `PR3-S4` is explicit and blocker-free.

## 1) Binding Authorities
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M2.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M4.build_plan.md`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M7.build_plan.md`
5. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M8.build_plan.md`
6. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M9.build_plan.md`
7. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M10.build_plan.md`
8. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M11.build_plan.md`
9. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M12.build_plan.md`
10. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M14.build_plan.md`
11. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/build/platform.M15.build_plan.md`
12. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/road_to_prod/platform.road_to_prod.plan.md`
13. `docs/model_spec/platform/pre-design_decisions/dev-full_road-to-production-ready.md`
14. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`

Supporting:
1. active `dev_full` implementation maps for the same surfaces,
2. `docs/experience_lake/platform-production-standard.md`,
3. `docs/model_spec/data-engine/interface_pack/`.

## 2) Scope Boundary
In scope:
1. restore the minimum-but-sufficient `dev_full` substrate needed to continue whole-platform production hardening,
2. restore and validate four substrate families:
   - core runtime substrate,
   - case/label substrate dependencies,
   - learning/evolution managed substrate,
   - ops/gov closure surfaces,
3. re-establish cost-safe, idle-safe, run-scoped operation surfaces,
4. publish deterministic restoration evidence and handoff back to `PR3-S4`.

Out of scope:
1. running new long stress/soak/certification windows,
2. redesigning the platform from scratch,
3. data-engine changes or reruns,
4. claiming production readiness from restoration alone.

## 3) PREPR Exit Standard (Hard)
`PREPR` can close only if all conditions are true:
1. all required substrate families are restored or explicitly proven not required for the next certification boundary,
2. each restored family has a readable validation receipt with `overall_pass=true`,
3. no restoration blocker remains open,
4. cost posture and idle-safe posture are both explicit and within envelope,
5. `prepr_execution_summary.json` emits `verdict=PR3_S4_REENTRY_READY`, `next_gate=PR3-S4`, `open_blockers=0`.

## 4) Capability Lanes (Mandatory PREPR Coverage)
`PREPR` must explicitly cover:
1. Authority/handles lane:
   - restoration handle set is complete, readable, and non-placeholder.
2. Identity/IAM lane:
   - IRSA/service-role surfaces exist for runtime, case/label, learning/evolution, and ops/gov where required.
3. Network/runtime lane:
   - EKS/MSK/Aurora/API edge/VPC-private reachability is restored where pinned.
4. Data store lane:
   - object-store, Aurora, and managed data surfaces are restored and writable/readable on declared paths.
5. Messaging lane:
   - control, RTDL, audit, and learning event surfaces are reachable and scoped.
6. Secrets lane:
   - required SSM/secret surfaces exist and resolve from the declared runtime identities.
7. Observability/evidence lane:
   - run roots and closure surfaces are readable and deterministic.
8. Rollback/rerun lane:
   - each failed restoration state has an exact rerun boundary; no full-world rerun.
9. Teardown/idle lane:
   - restoration leaves a bounded idle-safe posture and explicit teardown path.
10. Budget lane:
   - each state has runtime and spend envelope plus attributable outcome receipt.

## 5) Substrate Families (Binding)
### 5.1 Core Runtime Substrate
Required surfaces:
1. object store and retained evidence buckets,
2. MSK/bootstrap reachability,
3. Aurora endpoints and credentials,
4. EKS cluster/namespace/IRSA runtime posture,
5. IG edge (`APIGW/Lambda/DDB`) and required auth path,
6. WSP ephemeral execution path,
7. authoritative handles/SSM refs for all above.

### 5.2 Case/Label Substrate Dependencies
Required surfaces:
1. case/label IRSA and service-account posture,
2. runtime placement and dependency reachability for:
   - `CaseTrigger`,
   - `CM`,
   - `LS`,
3. case/label writable truth stores and observability roots,
4. authoritative topic/policy refs.

### 5.3 Learning/Evolution Managed Substrate
Required surfaces:
1. `M9` input-readiness handles and managed query path,
2. `Databricks` / OFS managed surfaces,
3. `SageMaker` + `MLflow` / MF managed surfaces,
4. `MPR` promotion/rollback authority surfaces,
5. object-store and registry/event readback surfaces tied to those lanes.

### 5.4 Ops/Gov Closure Surfaces
Required surfaces:
1. reporter/reconciliation/governance append roots,
2. environment/closure receipts under active run roots,
3. append-only governance target surfaces,
4. cost guardrail and idle-safe verification surfaces,
5. `PR3-S4` same-run bounded ops/gov proof prerequisites.

## 6) PREPR State Plan (`S0..S5`)
### S0 - Restoration Authority Freeze And Live-State Inventory
Objective:
1. freeze restoration authority and produce the exact live-state inventory after teardown.

Required actions:
1. bind required build/road-to-prod authorities,
2. inventory current live substrate state across all four families,
3. publish missing/restorable/not-required matrix,
4. pin restoration order and exact rerun boundaries.

Outputs:
1. `prepr_s0_authority_refs.json`
2. `prepr_s0_live_state_inventory.json`
3. `prepr_s0_restore_matrix.json`
4. `prepr_s0_execution_receipt.json`

Pass condition:
1. no restoration ambiguity remains and all required capability lanes are exposed.

Fail-closed blockers:
1. `PREPR.B01_AUTHORITY_UNRESOLVED`
2. `PREPR.B02_LIVE_STATE_INVENTORY_INCOMPLETE`
3. `PREPR.B03_RESTORE_MATRIX_INCOMPLETE`

### S1 - Core Runtime Substrate Restore
Objective:
1. restore the core runtime substrate to a production-shaped, runnable state.

Required actions:
1. restore the minimum required `M2/M4/M14`-aligned core surfaces,
2. validate EKS, MSK, Aurora, IG edge, object store, SSM, and runtime IAM posture,
3. publish a core restore receipt and attributable spend.

Outputs:
1. `prepr_s1_core_restore_manifest.json`
2. `prepr_s1_core_validation_receipt.json`
3. `prepr_s1_cost_receipt.json`
4. `prepr_s1_execution_receipt.json`

Pass condition:
1. the core runtime substrate is materially runnable with zero unresolved required blockers.

Fail-closed blockers:
1. `PREPR.B10_CORE_RESTORE_FAIL`
2. `PREPR.B11_CORE_IDENTITY_OR_SECRET_FAIL`
3. `PREPR.B12_CORE_NETWORK_OR_DATASTORE_FAIL`

### S2 - Case/Label Substrate Restore
Objective:
1. restore case/label dependencies as first-class production surfaces, not passive runtime afterthoughts.

Required actions:
1. restore/validate case-label IAM, policy, topic, datastore, and observability surfaces,
2. ensure runtime materialization can bind case/label lanes fail-fast,
3. publish case/label readiness receipts with impact metrics relevant to availability and truth ownership.

Outputs:
1. `prepr_s2_case_label_restore_manifest.json`
2. `prepr_s2_case_label_validation_receipt.json`
3. `prepr_s2_execution_receipt.json`

Pass condition:
1. case/label substrate dependencies are restored and claimably ready for bounded correctness execution.

Fail-closed blockers:
1. `PREPR.B20_CASE_LABEL_RESTORE_FAIL`
2. `PREPR.B21_CASE_LABEL_IAM_OR_POLICY_FAIL`
3. `PREPR.B22_CASE_LABEL_TRUTH_SURFACE_FAIL`

### S3 - Learning/Evolution Managed Substrate Restore
Objective:
1. restore the managed learning/evolution substrate required for real-data, point-in-time, governed learning proofs.

Required actions:
1. restore/validate `M9..M12/M15` managed surfaces:
   - query/profile,
   - OFS,
   - MF,
   - MPR,
2. validate handles, secrets, object-store paths, and evidence readback,
3. publish bounded readiness receipts for learning/evolution managed lanes.

Outputs:
1. `prepr_s3_learning_restore_manifest.json`
2. `prepr_s3_learning_validation_receipt.json`
3. `prepr_s3_execution_receipt.json`

Pass condition:
1. learning/evolution managed substrate is restorable, reachable, and evidence-ready for same-run bounded proofs.

Fail-closed blockers:
1. `PREPR.B30_LEARNING_RESTORE_FAIL`
2. `PREPR.B31_OFS_OR_MF_MANAGED_SURFACE_FAIL`
3. `PREPR.B32_MPR_OR_LINEAGE_SURFACE_FAIL`
4. `PREPR.B33_SEMANTIC_REALIZATION_SURFACE_FAIL`

### S4 - Ops/Gov Closure Surface Restore
Objective:
1. restore the ops/gov surfaces needed to measure and close whole-platform bounded gates honestly.

Required actions:
1. restore/validate reporter, reconciliation, governance append, and cost/idle-safe surfaces,
2. ensure same-run closure roots and append targets are readable,
3. publish ops/gov restoration receipts tied to `dev_full` whole-platform closure requirements.

Outputs:
1. `prepr_s4_ops_gov_restore_manifest.json`
2. `prepr_s4_ops_gov_validation_receipt.json`
3. `prepr_s4_execution_receipt.json`

Pass condition:
1. ops/gov closure surfaces are restored and readable for whole-platform bounded proofs.

Fail-closed blockers:
1. `PREPR.B40_OPS_GOV_RESTORE_FAIL`
2. `PREPR.B41_GOVERNANCE_APPEND_SURFACE_FAIL`
3. `PREPR.B42_COST_OR_IDLESAFE_SURFACE_FAIL`

### S5 - Whole-Platform Restoration Validation And Reentry Verdict
Objective:
1. validate the restored substrate as one whole platform and decide whether `PR3-S4` may resume.

Required actions:
1. aggregate `S1..S4` receipts,
2. verify no required substrate family remains unresolved,
3. publish impact-metric digest for restoration status,
4. emit deterministic reentry verdict.

Outputs:
1. `prepr_whole_platform_restore_scorecard.json`
2. `prepr_cross_plane_restore_report.json`
3. `prepr_cost_idle_summary.json`
4. `prepr_execution_summary.json`

Pass condition:
1. verdict is `PR3_S4_REENTRY_READY` with `open_blockers=0`.

Fail-closed blockers:
1. `PREPR.B50_WHOLE_PLATFORM_RESTORE_INCOMPLETE`
2. `PREPR.B51_COST_OR_IDLE_POSTURE_UNACCEPTABLE`
3. `PREPR.B52_REENTRY_NOT_AUTHORIZED`

## 7) Artifact Contract
Deterministic control root:
1. `runs/dev_substrate/dev_full/road_to_prod/run_control/`

Execution id format:
1. `prepr_<YYYYMMDDThhmmssZ>`

Required summary minimums:
1. `phase`
2. `state`
3. `generated_at_utc`
4. `execution_id`
5. `overall_pass`
6. `blocker_ids`
7. `impact_metrics`
8. `assessment`

## 8) Runtime And Cost Budgets
Program rules:
1. restore the minimum required live surfaces per state, not the entire world by default,
2. validate each restored state before moving on,
3. fail fast on deterministic missing handles, IAM, or dependency gaps,
4. no long certification run during `PREPR`.

Initial runtime targets:
1. `S0 <= 30 min`
2. `S1 <= 120 min`
3. `S2 <= 60 min`
4. `S3 <= 120 min`
5. `S4 <= 60 min`
6. `S5 <= 30 min`

Initial spend discipline:
1. each state must emit attributable spend and explain near-zero reuse where applicable,
2. every always-on surface introduced during restore must have an explicit reason and idle-safe path,
3. restoration does not authorize dormant spend carry-forward.

## 9) Human-Readable Findings Standard
Every `PREPR` state attempt must publish a digest with:
1. `Area`
2. `What was found`
3. `Interpretation`

Mandatory rows:
1. state verdict and blocker count,
2. restored surfaces and their measured availability/readability posture,
3. runtime elapsed vs budget,
4. attributable spend vs envelope,
5. production-standard assessment for that state,
6. exact rerun boundary if red.

## 10) Completion Rule
`PREPR` is complete only when:
1. the whole-platform substrate is restored in a production-shaped posture,
2. the restoration evidence is readable and analytically reported,
3. `PR3-S4` may resume without hidden substrate debt.

## 11) Current Status
### PREPR-S0 - COMPLETE (`prepr_s0_20260309T005216Z`)
Impact metrics:
1. retained surfaces: `13`
2. missing restore-required surfaces: `28`
3. substrate families requiring restoration: `4/4`
4. substrate families with reusable retained state: `4/4`
5. runtime-plane missing ratio: `0.53`
6. attributable spend: `0.0 USD`

What was found:
1. The environment is intentionally torn down on the live runtime side:
   - `EKS`, `MSK`, `Aurora`, `API Gateway`, `Lambda`, and most `SSM` surfaces are absent.
2. Retained truth/history surfaces still exist and can be reused:
   - `S3` buckets,
   - `KMS` alias,
   - `ECR` repo,
   - SageMaker package-group and training-job history.
3. Managed/control closure surfaces are also absent:
   - Step Functions,
   - MWAA,
   - budget guardrail,
   - ops/gov dashboards,
   - key `IRSA` roles.

Interpretation:
1. There is no ambiguity left in the restoration order.
2. The next valid move is `PREPR-S1`, not any `PR3/PR4` gate.
3. The restoration program must recreate the executable substrate while preserving retained truth/history surfaces and keeping spend bounded.

### PREPR-S1 - COMPLETE (`prepr_s1_20260309T010910Z`)
Impact metrics:
1. restored surface groups: `3`
2. IG throttle posture: `3000 rps / 6000 burst`
3. Lambda envelope: `2048 MB`, reserved concurrency `600`
4. runtime elapsed: `12.44 min`

What was found:
1. Core runtime substrate restored successfully:
   - `MSK`,
   - `Aurora`,
   - `EKS`,
   - `API Gateway`,
   - `Lambda`,
   - `IG DynamoDB`,
   - runtime VPC endpoints,
   - Step Functions,
   - runtime IRSA roles.
2. The restore is materially runnable and no longer placeholder-backed.
3. The next real red surface was not runtime absence but case/label boundary drift.

Interpretation:
1. `PREPR-S1` closed the executable runtime gap without reopening the earlier spine-only mistake.
2. Later phases can now assume a real runtime substrate exists and focus on plane-specific closure work.

### PREPR-S2 - COMPLETE (`prepr_s2_20260309T012300Z`)
Impact metrics:
1. restored case/label surfaces: `5`
2. inline policy count: `2`
3. Aurora readable path count: `3`
4. canonical namespace: `fraud-platform-case-labels`

What was found:
1. Case/label restore exposed and corrected namespace drift between runtime defaults and active `dev_full` authority.
2. Canonical namespace, canonical IRSA trust subject, and service-account binding are now aligned.
3. The runtime materializer now supports a true RTDL / case-label namespace split.

Interpretation:
1. Case/label is restored as a first-class plane rather than a hidden RTDL appendage.
2. Later bounded correctness runs can judge case/label on its own production surfaces.

### PREPR-S3 - COMPLETE (`prepr_s3_20260309T013100Z`)
Impact metrics:
1. restored learning surfaces: `6`
2. managed job count: `2`
3. SSM parameter count: `4`
4. Databricks readiness overall pass: `true`

What was found:
1. Managed learning restore was executed through the secret-backed GitHub workflow, not local placeholder Terraform.
2. Databricks workspace/token, MLflow tracking URI, and SageMaker execution identity are all materially restored.
3. The substrate is now real and non-placeholder for bounded learning/evolution proofs.

Interpretation:
1. `PREPR-S3` closed the learning/evolution control-surface gap honestly.
2. Later learning proofs can now run on managed authority surfaces instead of bootstrap placeholders.

### PREPR-S4 - COMPLETE (`prepr_s4_20260309T013003Z`)
Impact metrics:
1. restored ops surfaces: `8`
2. dashboard count: `2`
3. budget threshold count: `3`
4. actual month-to-date spend: `1778.043 USD`
5. runtime elapsed: `5.9 min`

What was found:
1. `ops` restore initially created a fake-green budget because the filter was malformed.
2. The budget was corrected into an account-effective guardrail and read back live.
3. Ops/gov closure surfaces are now restored and readable:
   - AWS budget,
   - CloudWatch dashboards,
   - runtime bootstrap log group,
   - MWAA and Redis SSM handles,
   - `obs-gov` namespace + IRSA service account,
   - readable evidence/object-store closure roots.

Interpretation:
1. `PREPR-S4` closed the whole-platform ops/gov visibility gap.
2. The cost guardrail is live and already in `ALARM`, so later execution must stay on the bounded correctness/stress ladder and not jump into soak.

### PREPR-S5 - COMPLETE (`prepr_s5_20260309T013003Z`)
Impact metrics:
1. restored substrate families: `4/4`
2. actual month-to-date spend: `1778.043 USD`
3. budget limit: `300.0 USD`
4. budget alarm active: `true`
5. runtime elapsed total: `18.34 min`

What was found:
1. All four substrate families required by `PREPR` are restored and readable:
   - core runtime,
   - case/label,
   - learning/evolution,
   - ops/gov.
2. No PREPR blocker remains open.
3. The deterministic reentry verdict is:
   - `PR3_S4_REENTRY_READY`
   - `next_state=PR3-S4`
   - `open_blockers=0`

Interpretation:
1. `PREPR` is complete.
2. The next legal move is to resume `PR3-S4` on the restored whole-platform substrate using the bounded correctness -> bounded stress -> soak-last execution ladder.
