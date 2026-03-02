# Dev Full Runtime Certification Plan

Status: `NOT_STARTED`
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

DoD:
- [ ] claim matrix for Tier 0..2 runtime slice is published.
- [ ] minimum evidence bundle rules are pinned per claim.
- [ ] metric dictionary (units, windows, statistics, thresholds) is unambiguous.
- [ ] blocker register is empty.

### RC1 - Runtime evidence inventory and fresh-gap register
Goal:
1. Produce deterministic inventory and classify fresh evidence gaps.

Rules:
1. Inventory can include historical refs for context.
2. Tier-0 claimability counts only `EVIDENCED_FRESH` rows.

DoD:
- [ ] evidence inventory is complete and deterministic.
- [ ] fresh-gap register explicitly lists all Tier-0 missing metrics.
- [ ] no claim row is marked pass in RC1.

### RC2 - Tier 0 runtime scorecard certification (steady/burst/soak + replay-window)
Goal:
1. Certify Tier-0 runtime scorecard against pinned profile floors.

Mandatory profiles:
1. steady: `500 eps`, `30 min`, sample `>= 900,000`.
2. burst: `1,500 eps`, `10 min`, sample `>= 900,000`.
3. soak: `300 eps`, `6 h`, sample `>= 6,480,000`.
4. replay-window: `24 h logical window`, sample `>= 10,000,000`.

DoD:
- [ ] all mandatory profiles have fresh managed-run evidence.
- [ ] each profile meets pinned sample/eps/duration thresholds.
- [ ] required p50/p95/p99 distributions are present.
- [ ] blocker register is empty.

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
