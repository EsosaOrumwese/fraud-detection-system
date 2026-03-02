# Dev Full Operations and Governance Certification Plan

Status: `NOT_STARTED`

## 1) Purpose
This plan certifies operations/governance posture against the production truth anchor:
- `docs/experience_lake/platform-production-standard.md`

It is separate from build execution phases and separate from runtime-only certification.

## 2) Scope and boundary
In scope:
1. Release corridor governance and rollback operability.
2. Audit-grade provenance and traceability readiness.
3. Operational governance (runbooks, incident response, policy controls).
4. Cost governance and attribution posture across active platforms.

Out of scope:
1. Runtime load-profile scorecard (covered in runtime cert plan).
2. New architecture/tooling migrations outside current dev_full stack.

## 3) Authority inputs
1. Truth anchor:
   - `docs/experience_lake/platform-production-standard.md`
2. Dev full closure baseline:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M13.build_plan.md`
3. Existing governance/closure artifacts:
   - promotion corridor artifacts (`M11/M12`)
   - final verdict + teardown closure artifacts (`M13`)

## 4) Claim coverage map (ops and gov)
Tier 0 claims to certify:
1. `T0.1` Governed release corridor with fast rollback.
2. `T0.5` Audit-grade provenance and decision traceability.
3. `T0.6` Cost-to-outcome control (governance slice).
4. `T0.4` Observability/diagnosability governance slice (alert ownership/runbooks/escalation).

### 4.1) Tier 0 thresholds (ops/gov slice, pinned)
`T0.1` Governed release/rollback:
1. rollback execute objective (RTO) `<= 15 min`.
2. rollback evidence completeness `= 100%` (plan, execution, verdict, post-check).
3. unauthorized promotion/rollback count `= 0`.

`T0.5` Audit/provenance:
1. provenance chain completeness `>= 99.9%`.
2. unresolved provenance gaps for Tier-0 scope `= 0`.
3. audit query response time `p95 <= 60 s`.

`T0.6` Governance cost control:
1. unexplained/unattributed spend count `= 0`.
2. cost-to-outcome receipt coverage for certified releases `= 100%`.
3. certification window must remain below alert-2 unless approved exception; alert-3 is hard fail.

`T0.4` Governance observability/diagnosability slice:
1. critical alerts with owned runbook linkage `= 100%`.
2. critical alerts with explicit owner + escalation path `= 100%`.
3. critical incident initial acknowledgment `p95 <= 10 min`.

Tier 1 claims to certify (best-effort on current stack):
1. Controlled rollout/challenger safety governance.
2. Drift governance and mitigation workflow quality.
3. Training-serving consistency governance controls.

Tier 2 claims to certify (best-effort):
1. Policy sophistication and operational excellence extensions beyond Tier 0/1.

## 5) Operations/governance certification lanes
### OC0 - Claim model lock and governance evidence schema
Goal:
1. Pin claim->metrics->artifacts->drill mapping for ops/governance scope.

DoD:
- [ ] claim matrix for Tier 0..2 ops/governance slice is published.
- [ ] minimum evidence bundle rule is pinned for each claim.
- [ ] evidence schema for policy/runbook/drill artifacts is explicit.

### OC1 - Release corridor and rollback governance certification
Goal:
1. Certify fail-closed promotion corridor and rollback discipline as operated.

Mandatory drill mapping:
1. `OG-DR-01` release rollback drill (truth-anchor rollback family equivalent).
2. `OG-DR-02` gate exception control drill (no silent bypass).

DoD:
- [ ] gate definitions, pass/fail semantics, and exception controls are explicit.
- [ ] rollback path is evidenced with bounded recovery objective.
- [ ] release ledger and promotion/rollback traceability are complete.

### OC2 - Audit and provenance certification
Goal:
1. Certify audit queryability and provenance completeness for decision and promotion paths.

Mandatory drill mapping:
1. `OG-DR-03` audit chain reconstruction drill (event->decision->model/data/code/config).
2. `OG-DR-04` provenance gap injection drill (must fail-closed).

DoD:
- [ ] provenance completeness metrics and thresholds are explicit.
- [ ] audit query response-time posture is evidenced.
- [ ] event->decision->model/data/code/config trace chain is demonstrably complete.

### OC3 - Operational governance certification (runbooks/alerts/incidents)
Goal:
1. Certify that operational governance controls are actionable, owned, and complete.

Mandatory drill mapping:
1. `OG-DR-05` alert-to-runbook execution drill.
2. `OG-DR-06` escalation/incident governance drill.

DoD:
- [ ] critical alert classes are linked to owned runbooks.
- [ ] escalation/severity posture is explicit and auditable.
- [ ] incident drill or postmortem governance artifacts are present and quality-checked.

### OC4 - Cost governance and FinOps certification
Goal:
1. Certify spend discipline and attribution posture across active cost surfaces.

Mandatory drill mapping:
1. `OG-DR-07` budget guardrail breach response drill.
2. `OG-DR-08` unattributed-spend stop-the-line drill.

DoD:
- [ ] budget envelope and guardrail policies are explicit and enforced.
- [ ] cost-to-outcome receipts are present and attributable.
- [ ] unexplained spend policy is fail-closed and evidenced.

### OC5 - Tier 1/2 governance differentiator pack
Goal:
1. Capture best-effort Tier 1/2 governance proofs with explicit maturity grading.

DoD:
- [ ] Tier 1 governance claims are graded with evidence refs.
- [ ] Tier 2 governance claims are graded with explicit unresolved items.

### OC6 - Ops/Gov rollup and staging verdict
Goal:
1. Emit deterministic operations/governance certification verdict for dev_full staging.

Mandatory outputs:
1. ops/gov claim matrix with levels (`L0..L4`) per claim.
2. ops/gov blocker register.
3. ops/gov certification summary verdict.

DoD:
- [ ] Tier 0 ops/gov claims are evidence-pass and blocker-free.
- [ ] Tier 1/Tier 2 are explicitly graded (pass/partial/not-proven).
- [ ] unresolved waivers and expiry triggers are explicit.

## 6.1) Ops/Gov minimum artifact contract (deterministic)
All OC lanes publish under:
1. `s3://fraud-platform-dev-full-evidence/evidence/dev_full/cert/ops_gov/<ops_gov_cert_execution_id>/`

Required artifacts:
1. `ops_gov_claim_matrix.json`
2. `ops_gov_drill_bundle.json`
3. `ops_gov_blocker_register.json`
4. `ops_gov_certification_verdict.json`
5. `ops_gov_release_corridor_receipt.json`
6. `ops_gov_cost_governance_receipt.json`

Contract rules:
1. every artifact includes `platform_run_id`, `scenario_run_id`, `ops_gov_cert_execution_id`, and timestamp fields.
2. verdict artifact must include blocker list, waiver list with expiry, and explicit `GREEN|HOLD`.
3. missing required artifact is fail-closed (`OC-B3`/`OC-B6`).

## 7) Operations/governance blocker taxonomy
1. `OC-B1` release-corridor governance gap.
2. `OC-B2` rollback governance or bounded-restore evidence gap.
3. `OC-B3` audit/provenance incompleteness.
4. `OC-B4` runbook/alert ownership or escalation gap.
5. `OC-B5` cost governance/attribution gap.
6. `OC-B6` non-deterministic ops/gov rollup artifact.
7. `OC-B7` unresolved Tier 0 ops/gov claim in final verdict.

## 8) Joint Point-X certification pack (ops/gov contribution)
Required stitched outputs (published after Runtime + Ops/Gov verdicts are both present):
1. `dev_full_point_x_summary.md`
2. `tier0_claimability_table.json` (merged Tier-0 claim table)
3. link refs to:
   - `runtime_certification_verdict.json`
   - `ops_gov_certification_verdict.json`

## 9) Acceptance posture
1. Ops/Gov certification is `GREEN` only when Tier 0 ops/governance claims are evidence-pass with no active blockers.
2. Tier 1/Tier 2 may be partial, but must be explicit and non-silent.
3. Any ambiguity defaults to fail-closed.
