# Dev Full Runtime Certification Plan

Status: `NOT_STARTED`

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

DoD:
- [ ] claim matrix for Tier 0..2 runtime slice is published.
- [ ] each runtime claim has minimum evidence bundle rule pinned.
- [ ] metric definitions and windows are unambiguous.

### RC1 - Runtime evidence inventory and gap register
Goal:
1. Build authoritative inventory of available runtime evidence and missing pieces.

DoD:
- [ ] evidence index for existing dev_full runs is produced.
- [ ] missing evidence surfaces are registered as blockers.
- [ ] no claim is marked pass without inspectable artifact refs.

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

DoD:
- [ ] scorecard metrics meet pinned thresholds for all profiles.
- [ ] latency/availability/lag/error posture is recorded with `p50/p95/p99` distributions.
- [ ] per-profile sample size is recorded and passes minimum accepted sample.
- [ ] profile verdicts are deterministic and blocker-aware.

### RC3 - Tier 0 runtime drill pack certification
Goal:
1. Prove required runtime failure-mode drills with bounded recovery and integrity checks.

Mandatory drill families (aligned to truth anchor):
1. `DR-02` replay/backfill integrity.
2. `DR-03` lag spike and recovery.
3. `DR-04` schema evolution safety.
4. `DR-05` dependency outage with degrade/recover.
5. `DR-07` runtime cost guardrail response.

DoD:
- [ ] each drill has scenario, expected behavior, observed outcome, integrity checks, recovery bound.
- [ ] each drill emits durable drill bundle artifact.
- [ ] no drill pass is accepted with missing integrity proof.

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
