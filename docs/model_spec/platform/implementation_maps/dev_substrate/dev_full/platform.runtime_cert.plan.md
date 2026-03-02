# Dev Full Runtime Certification Plan

Status: `ACTIVE`

## 1) Purpose
This plan certifies runtime behavior against the production truth anchor:
- `docs/experience_lake/platform-production-standard.md`

It is separate from the build-phase map and is focused on proving Tier 0..2 runtime claims as far as current dev_full stack and evidence allow.

## 2) Scope and boundary
In scope:
1. Runtime SLO/correctness/drill certifications for the running platform.
2. Evidence-backed claim grading for Tier 0, Tier 1, Tier 2 runtime-relevant claims.
3. Fail-closed certification verdict with explicit blockers.

Out of scope:
1. New architecture or substrate swaps.
2. Non-runtime governance controls that belong to ops/governance certification doc.

## 3) Authority inputs
1. Truth anchor:
   - `docs/experience_lake/platform-production-standard.md`
2. Dev full build and closure baseline:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M13.build_plan.md`
3. Runtime truth artifacts:
   - run-control and run-scoped evidence under `s3://fraud-platform-dev-full-evidence/evidence/`

## 4) Claim coverage map (runtime)
Tier 0 claims to certify:
1. `T0.2` SLO-grade online decision path.
2. `T0.3` Replay-safe streaming correctness.
3. `T0.4` Default observability and diagnosability (runtime slice).
4. `T0.6` Cost-to-outcome control (runtime slice).

### 4.1) Tier 0 thresholds (runtime slice, pinned)
`T0.2` Online decision path:
1. decision latency `p95 <= 250 ms`, `p99 <= 500 ms`.
2. success availability `>= 99.5%` for steady/burst/soak windows.
3. non-retryable error rate `<= 0.10%`.

`T0.3` Replay-safe streaming:
1. replay integrity mismatch count `= 0`.
2. duplicate side-effect count `= 0`.
3. ingress->core end-to-end lag `p95 <= 5 s`, `p99 <= 15 s` during steady.
4. ingest-committed publication ambiguity unresolved count (`PUBLISH_UNKNOWN`) `= 0` at phase close.

`T0.4` Runtime observability/diagnosability slice:
1. correlation-id coverage across runtime critical path `>= 99.9%`.
2. runtime Time-To-Detect (`TTD`) `p95 <= 5 min`.
3. runtime Time-To-Diagnose (`TTDiag`) `p95 <= 15 min`.

`T0.6` Runtime cost-to-outcome slice:
1. unattributed runtime spend count `= 0`.
2. cost attribution coverage for certified runtime runs `= 100%`.
3. certification run must not exceed budget alert-2 envelope without explicit approved exception; alert-3 is hard fail.

Tier 1 claims to certify (best-effort on current stack):
1. Non-leaky runtime-learning boundaries in runtime path checks.
2. Drift-to-mitigation runtime loop responsiveness.
3. Training-serving consistency runtime checks (where observable in live path).

Tier 2 claims to certify (best-effort):
1. Extended pressure profiles and replay-window diversity.
2. Additional resilience drills beyond minimum Tier 0 set.

## 5) Runtime certification lanes
### RC0 - Claim model lock and metric dictionary
Goal:
1. Pin exact claim->metric->artifact->drill mappings for runtime claims.

Execution strategy (expanded):
1. `RC0.A` entry-gate validation:
   - confirm `M15_COMPLETE_GREEN` and `CERTIFICATION_TRACKS_READY` from handoff artifacts.
   - confirm authority inputs in Section 3 are readable.
2. `RC0.B` runtime claim-matrix materialization:
   - publish Tier 0/1/2 runtime claim rows with gate class (`hard_gate` vs `advisory`),
   - pin claim-to-drill mapping (`DR-02/03/04/05/07` where applicable),
   - pin claim-to-metric mapping to metric IDs (no free-text-only claims).
3. `RC0.C` metric dictionary lock:
   - publish metric IDs with unit, statistic (`p50/p95/p99/count/rate`), window, and canonical source surface.
   - for Tier-0 metrics, include exact thresholds from Section 4.1.
4. `RC0.D` minimum evidence bundle rules:
   - publish per-claim minimum artifact bundle requirement (inspectable refs mandatory),
   - require deterministic artifact names and fail-closed if any required artifact pointer is missing.
5. `RC0.E` publication and readback:
   - publish RC0 artifacts to local cert run path,
   - publish durable mirror under runtime cert S3 prefix when AWS credential context is available,
   - readback check for published artifacts.
6. `RC0.F` blocker evaluation + lane verdict:
   - evaluate `RC-B1/RC-B2/RC-B3`,
   - lane passes only if blocker set is empty and RC0 DoD is fully satisfied.

RC0 entry criteria:
1. `cert_handoff.md` confirms `CERTIFICATION_TRACKS_READY`.
2. Runtime cert plan is `ACTIVE`.
3. Runtime cert notes file exists and is writable.

RC0 outputs (deterministic):
1. `runtime_claim_matrix.json`
2. `runtime_metric_dictionary.json`
3. `runtime_evidence_bundle_rules.json`
4. `rc0_execution_snapshot.json`

RC0 artifact paths:
1. local:
   - `runs/dev_substrate/dev_full/cert/runtime/<runtime_cert_execution_id>/`
2. durable (when AWS session is present):
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/<runtime_cert_execution_id>/`

DoD:
- [x] claim matrix for Tier 0..2 runtime slice is published.
- [x] each runtime claim has minimum evidence bundle rule pinned.
- [x] metric definitions and windows are unambiguous.

RC0 closure snapshot:
1. `runtime_cert_execution_id=rc0_claim_model_lock_20260302T144121Z`
2. `platform_run_id=platform_20260302T080146Z`
3. `scenario_run_id=scenario_9de27c0bd83aed3a4aea4d0063c981f1`
4. local artifact root:
   - `runs/dev_substrate/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z/`
5. durable artifact root:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc0_claim_model_lock_20260302T144121Z/`
6. lane verdict:
   - `overall_pass=true`
   - `blockers=[]`
   - `next_gate=RC1_READY`

### RC1 - Runtime evidence inventory and gap register
Goal:
1. Build authoritative inventory of available runtime evidence and missing pieces.

Fresh-evidence policy (binding):
1. RC1 for certification uses `fresh-only` posture:
   - evidence must be produced within the active runtime-cert window,
   - evidence lineage must not depend on historical phase artifacts outside the active cert window unless explicitly approved.
2. Historical evidence is never counted as fresh by default:
   - if an artifact references historical `M*` executions outside current cert window, mark as `HISTORICAL_LINEAGE` and register as gap/blocker candidate.
3. RC1 remains an inventory lane:
   - lane pass means inventory and gap classification are complete and deterministic,
   - it does not mean Tier-0 evidence sufficiency is achieved.

Execution strategy (expanded):
1. `RC1.A` entry validation:
   - load latest RC0 artifacts (`runtime_claim_matrix.json`, `runtime_metric_dictionary.json`),
   - verify RC0 next gate is `RC1_READY`.
2. `RC1.B` evidence surface crawl:
   - inventory local runtime evidence under runtime-cert roots for the active cert window,
   - inventory durable evidence under `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/**` for active cert window.
3. `RC1.C` claim/metric evidence indexing:
   - map each RC0 metric to inspectable artifact refs (local and/or durable),
   - attach coverage status (`EVIDENCED_FRESH`, `MISSING_FRESH_EVIDENCE`, `HISTORICAL_LINEAGE`) per metric.
4. `RC1.D` gap/blocker register:
   - register every missing Tier-0 evidence surface as `RC-B3` blocker candidate,
   - register Tier-1/2 missing surfaces as explicit non-silent gaps for downstream lanes.
5. `RC1.E` deterministic publication + readback:
   - publish `runtime_evidence_inventory.json`, `runtime_evidence_gap_register.json`, `rc1_execution_snapshot.json`,
   - publish durable mirror and verify readback.
6. `RC1.F` lane verdict posture:
   - RC1 passes when inventory and gap register are complete and deterministic,
   - open gap blockers remain active for downstream RC lanes and final verdict rollup.

RC1 outputs (deterministic):
1. `runtime_evidence_inventory.json`
2. `runtime_evidence_gap_register.json`
3. `rc1_execution_snapshot.json`

RC1 artifact paths:
1. local:
   - `runs/dev_substrate/dev_full/cert/runtime/<runtime_cert_execution_id>/`
2. durable:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/<runtime_cert_execution_id>/`

DoD:
- [x] evidence index for active cert-window runtime evidence is produced.
- [x] missing evidence surfaces are registered as blockers.
- [x] no claim is marked pass without inspectable artifact refs.

RC1 closure snapshot (latest fresh-only run):
1. `runtime_cert_execution_id=rc1_runtime_evidence_inventory_fresh_20260302T161002Z`
2. `platform_run_id=platform_20260302T080146Z`
3. `scenario_run_id=scenario_9de27c0bd83aed3a4aea4d0063c981f1`
4. local artifact root:
   - `runs/dev_substrate/dev_full/cert/runtime/rc1_runtime_evidence_inventory_fresh_20260302T161002Z/`
5. durable artifact root:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc1_runtime_evidence_inventory_fresh_20260302T161002Z/`
6. lane verdict:
   - `overall_pass=true`
   - `lane_blockers=[]`
   - `next_gate=RC2_READY_WITH_FRESH_GAP_REGISTER`
7. assertion posture:
   - all claim rows remain `evaluation_status=NOT_EVALUATED` and `pass_asserted=false` in RC1 outputs (inventory-only lane).
8. fresh-gap posture:
   - `15` Tier-0 `RC-B3` open blockers are explicit (`MISSING_FRESH_EVIDENCE` or `HISTORICAL_LINEAGE`),
   - prior non-fresh inventory run is superseded for strict fresh-evidence certification posture.

### RC2 - Tier 0 runtime scorecard certification (steady/burst/soak)
Goal:
1. Prove Tier 0 runtime metrics under representative load profiles.

Mandatory profiles:
1. steady profile:
   - target load: `500 events/sec`
   - duration: `30 min`
   - minimum accepted sample: `>= 900,000 events`.
2. burst profile:
   - target load: `1,500 events/sec` (`3x` steady)
   - duration: `10 min`
   - minimum accepted sample: `>= 900,000 events`.
3. bounded soak profile:
   - target load: `300 events/sec`
   - duration: `6 h`
   - minimum accepted sample: `>= 6,480,000 events`.
4. replay-window profile add-on (applies to at least one scorecard run):
   - replay window: `24 h logical window` equivalent
   - minimum replayed sample: `>= 10,000,000 events`.

Execution strategy (expanded):
1. `RC2.A` entry validation:
   - require latest `RC1` lane pass (`next_gate=RC2_READY_WITH_FRESH_GAP_REGISTER`),
   - load RC0 claim/metric dictionary and RC1 inventory.
2. `RC2.B` profile evidence resolution:
   - resolve scorecard evidence candidate(s) for mandatory profiles (steady/burst/soak/replay-window),
   - require explicit source execution IDs per profile.
3. `RC2.C` metric extraction and distribution synthesis:
   - compute/collect `p50/p95/p99` for latency, lag, availability, and error posture per profile,
   - enforce sample-size and duration constraints before threshold checks.
4. `RC2.D` threshold evaluation:
   - evaluate Tier-0 threshold map from Section 4.1 per profile,
   - mark profile verdict `PASS` only if all required checks pass.
5. `RC2.E` fail-closed blocker registration:
   - missing mandatory profile evidence or insufficient profile samples -> `RC-B4`,
   - missing/unreadable profile evidence surfaces -> `RC-B3`,
   - uncomputable required metric distributions -> `RC-B2`.
6. `RC2.F` deterministic artifact publication + readback:
   - publish `runtime_scorecard_profiles.json`, `runtime_blocker_register.json`, `runtime_certification_verdict.json`, and `rc2_execution_snapshot.json`,
   - publish durable mirror and verify readback.

RC2 outputs (deterministic):
1. `runtime_scorecard_profiles.json`
2. `runtime_blocker_register.json`
3. `runtime_certification_verdict.json`
4. `rc2_execution_snapshot.json`

RC2 artifact paths:
1. local:
   - `runs/dev_substrate/dev_full/cert/runtime/<runtime_cert_execution_id>/`
2. durable:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/<runtime_cert_execution_id>/`

DoD:
- [ ] scorecard metrics meet pinned thresholds for all profiles.
- [ ] latency/availability/lag/error posture is recorded with `p50/p95/p99` distributions.
- [ ] per-profile sample size is recorded and passes minimum accepted sample.
- [ ] profile verdicts are deterministic and blocker-aware.

RC2 execution snapshot (latest):
1. `runtime_cert_execution_id=rc2_tier0_scorecard_20260302T153633Z`
2. `platform_run_id=platform_20260302T080146Z`
3. `scenario_run_id=scenario_9de27c0bd83aed3a4aea4d0063c981f1`
4. local artifact root:
   - `runs/dev_substrate/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z/`
5. durable artifact root:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc2_tier0_scorecard_20260302T153633Z/`
6. lane verdict:
   - `overall_pass=false`
   - `verdict=HOLD`
   - `next_gate=RC2_REMEDIATION_REQUIRED`
7. active blockers:
   - `RC-B4` steady profile evidence below required floor (`target=500 eps`, `min_sample=900,000`, best available `49.49 eps`, sample `11,878`).
   - `RC-B4` burst profile evidence below required floor (`target=1,500 eps`, `min_sample=900,000`, best available `49.49 eps`, sample `11,878`).
   - `RC-B4` soak profile evidence below required floor (`target=300 eps for 6h`, `min_sample=6,480,000`, best available sample `11,878`).
   - `RC-B4` replay-window profile evidence below required floor (`min_sample=10,000,000`, best available sample `11,878`).
8. superseded pass:
   - `rc2_tier0_scorecard_20260302T153540Z` is superseded by `...153633Z` due best-candidate ranking correction in blocker reporting.

### RC3 - Tier 0 runtime drill pack certification
Goal:
1. Prove required runtime failure-mode drills with bounded recovery and integrity checks.

Mandatory drill families (aligned to truth anchor):
1. `DR-02` replay/backfill integrity.
2. `DR-03` lag spike and recovery.
3. `DR-04` schema evolution safety.
4. `DR-05` dependency outage with degrade/recover.
5. `DR-07` runtime cost guardrail response.

Execution strategy (expanded):
1. `RC3.A` entry validation:
   - require `RC1` PASS artifacts,
   - load RC0 claim/metric dictionary,
   - allow `RC2` HOLD to remain open while RC3 is executed (no silent waiver).
2. `RC3.B` drill evidence resolution:
   - resolve one deterministic evidence bundle per mandatory drill family,
   - require local-path readability; durable S3 ref is preferred and readback-checked.
3. `RC3.C` drill contract extraction:
   - per drill row, extract and pin:
     - scenario,
     - expected behavior,
     - observed outcomes,
     - integrity checks,
     - recovery bound.
4. `RC3.D` fail-closed drill adjudication:
   - any missing mandatory drill -> `RC-B3`,
   - any drill with missing contract fields or unbounded recovery/integrity proof -> `RC-B5`,
   - no implied pass; evidence must be explicit and inspectable.
5. `RC3.E` deterministic artifact publication + readback:
   - publish `runtime_drill_bundle.json`, `runtime_blocker_register.json`, `runtime_certification_verdict.json`, `rc3_execution_snapshot.json`,
   - publish durable mirror under runtime cert prefix and verify readback for published objects.

RC3 outputs (deterministic):
1. `runtime_drill_bundle.json`
2. `runtime_blocker_register.json`
3. `runtime_certification_verdict.json`
4. `rc3_execution_snapshot.json`

RC3 artifact paths:
1. local:
   - `runs/dev_substrate/dev_full/cert/runtime/<runtime_cert_execution_id>/`
2. durable:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/<runtime_cert_execution_id>/`

DoD:
- [ ] each drill has scenario, expected behavior, observed outcome, integrity checks, recovery bound.
- [ ] each drill emits durable drill bundle artifact.
- [ ] no drill pass is accepted with missing integrity proof.

RC3 execution snapshot (latest):
1. `runtime_cert_execution_id=rc3_tier0_drill_pack_20260302T155517Z`
2. `platform_run_id=platform_20260302T080146Z`
3. `scenario_run_id=scenario_9de27c0bd83aed3a4aea4d0063c981f1`
4. local artifact root:
   - `runs/dev_substrate/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z/`
5. durable artifact root:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/rc3_tier0_drill_pack_20260302T155517Z/`
6. lane verdict:
   - `overall_pass=false`
   - `verdict=HOLD`
   - `next_gate=RC3_REMEDIATION_REQUIRED`
7. drill-family outcomes:
   - `DR-02`: pass
   - `DR-03`: fail-closed (missing explicit lag-spike injection/recovery drill proof)
   - `DR-04`: fail-closed (missing explicit schema-break injection + quarantine/recovery proof)
   - `DR-05`: pass
   - `DR-07`: fail-closed (missing explicit breach->action->idle-safe drill cycle proof)
8. active blockers:
   - `RC-B5` `DR-03` lag-spike drill incompleteness.
   - `RC-B5` `DR-04` schema-evolution drill incompleteness.
   - `RC-B5` `DR-07` cost-guardrail response drill incompleteness.

### RC4 - Tier 1 runtime differentiator pack
Goal:
1. Certify Tier 1 runtime-adjacent claims as far as current stack supports.

DoD:
- [ ] leakage-at-runtime boundary checks are evidenced.
- [ ] drift detect->mitigate timings are measured where lane exists.
- [ ] training-serving consistency checks are evidenced where observable.

### RC5 - Tier 2 runtime stretch pack
Goal:
1. Capture best-effort Tier 2 runtime proofs and explicitly mark unresolved maturity items.

DoD:
- [ ] advanced runtime checks are documented with pass/partial/fail.
- [ ] unresolved Tier 2 items are explicit and non-silent.

### RC6 - Runtime certification rollup and verdict
Goal:
1. Emit final runtime certification verdict for dev_full staging posture.

Mandatory outputs:
1. runtime claim matrix with levels (`L0..L4`) per claim.
2. runtime blocker register.
3. runtime certification summary verdict.

DoD:
- [ ] Tier 0 runtime claims are graded with explicit evidence.
- [ ] Tier 1 and Tier 2 status are explicit (pass/partial/not-proven).
- [ ] no unresolved blocker is silently waived.

## 6.1) Runtime minimum artifact contract (deterministic)
All RC lanes publish under:
1. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/runtime/<runtime_cert_execution_id>/`

Required artifacts:
1. `runtime_claim_matrix.json`
2. `runtime_scorecard_profiles.json`
3. `runtime_drill_bundle.json`
4. `runtime_blocker_register.json`
5. `runtime_certification_verdict.json`

Contract rules:
1. all artifacts include `platform_run_id`, `scenario_run_id`, `runtime_cert_execution_id`, and timestamp fields.
2. verdict artifact must include a full blocker list and explicit `GREEN|HOLD` status.
3. missing any required artifact is fail-closed (`RC-B3`/`RC-B6`).

## 7) Runtime blocker taxonomy
1. `RC-B1` claim mapping incompleteness.
2. `RC-B2` metric definition/window ambiguity.
3. `RC-B3` missing or unreadable runtime evidence.
4. `RC-B4` steady/burst/soak scorecard failure.
5. `RC-B5` drill integrity or recovery-bound failure.
6. `RC-B6` non-deterministic rollup/verdict artifact.
7. `RC-B7` unresolved Tier 0 claim in final verdict.

## 8) Joint Point-X certification pack (runtime contribution)
Required stitched outputs (published after Runtime + Ops/Gov verdicts are both present):
1. `dev_full_point_x_summary.md`
2. `tier0_claimability_table.json` (merged Tier-0 claim table)
3. link refs to:
   - `runtime_certification_verdict.json`
   - `ops_gov_certification_verdict.json`

## 9) Acceptance posture
1. Runtime certification is `GREEN` only when all Tier 0 runtime claims are evidence-pass and blocker-free.
2. Tier 1/Tier 2 can be partial, but must be explicitly marked with closure debt and no hidden ambiguity.
3. Any ambiguity defaults to fail-closed.
