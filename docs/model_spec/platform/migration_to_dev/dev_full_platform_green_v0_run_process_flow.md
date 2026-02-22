# DEV_FULL - FULL PLATFORM GREEN v0 RUN PROCESS FLOW

## 0. Document Control

### 0.1 Status

* **Status:** v0 (active authority draft; run-process closure pass aligned to dev_full design-authority pins)
* **As-of:** 2026-02-22 (Europe/London)
* **Scope:** full-platform green on `dev_full` (Spine + Learning/Evolution) with managed runtime and no laptop compute.

### 0.2 Roles and audience

* **Design authority:** USER + Codex
* **Implementer:** Codex
* **Operator:** USER
* **Primary audience:** implementation and operations

### 0.3 Authority boundaries

**Pinned (MUST follow)**

1. Spine semantics for `P0..P11` are inherited from dev_min/local-parity and MUST NOT be reinterpreted.
2. `dev_full` extends closure with `P12..P16` (learning/evolution + full-platform verdict) and `P17` teardown/idle-safe closure.
3. Runtime compute is managed only. Laptop is control-plane/operator only.
4. Event bus is AWS MSK Serverless with IAM auth posture.
5. No phase may claim closure without explicit PASS gate and durable commit evidence.
6. No lane may claim closure without six proof classes: deploy, monitor, failure drill, recovery, rollback, cost-control.

### 0.4 Precedence

1. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
2. This runbook
3. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (spine inheritance source)
4. local-parity semantic sources under `docs/design/platform/local-parity/`

### 0.5 Normative references

1. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
2. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
3. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`

---

## 1. Pinned Global Decisions (Dev-full v0)

### 1.1 Scope lock

* **IN SCOPE:** Spine (`Control+Ingress`, `RTDL`, `Case+Labels`, `Run/Operate+Obs/Gov`) + Learning/Evolution (`OFS`, `MF`, `MPR`).
* **OUT OF SCOPE (v0):** multi-region active-active and compliance-program expansion beyond engineering controls.

### 1.2 Canonical phase IDs

* Canonical phase keys are `P(-1)`, `P0..P17`.
* `P0..P11`: spine semantics inherited.
* `P12..P16`: learning/evolution + integrated closure.
* `P17`: teardown/idle-safe closeout.

### 1.3 Substrate and tooling pins

1. Runtime orchestration: `EKS`
2. Event bus: `AWS MSK Serverless` (`SASL_IAM`, `MSK_REGION=eu-west-2`)
3. Durable object store/evidence/archive: `S3`
4. Runtime relational state: `Aurora PostgreSQL Serverless v2 Multi-AZ`
5. Low-latency join/state cache: `ElastiCache Redis`
6. OFS compute lane: `Databricks` (job clusters only)
7. MF train/serve lane: `SageMaker` (realtime endpoint + batch transform)
8. Experiment/registry tracking: `Databricks managed MLflow`
9. Orchestration split: `Step Functions` (run-state/gates) + `MWAA Airflow` (learning schedules)
10. Delivery/IaC: `Terraform + GitHub Actions`
11. Telemetry baseline: `OpenTelemetry` + CloudWatch-backed operational signals

### 1.4 Budget and teardown posture

* `DEV_FULL_MONTHLY_BUDGET_LIMIT_USD=300`
* Alerts: `$120` / `$210` / `$270`
* Alert-3 is fail-closed for phase advancement until remediation approval.
* Idle-safe posture is mandatory at run closure (`P17`).

### 1.5 Semantic invariants (no drift)

Unchanged from local-parity/dev_min:

1. dedupe identity and payload-hash anomaly law
2. append-only truth ownership boundaries
3. origin-offset evidence boundary
4. explicit degrade posture only
5. deterministic provenance references for replay/audit

---

## 2. Canonical Runtime/Evidence Terms

### 2.1 Identity anchors

* `platform_run_id`
* `scenario_run_id`
* `event_id`
* `event_class`
* `dataset_fingerprint`
* `bundle_id`, `bundle_version`, `policy_rev`
* `run_config_digest`

### 2.2 Gate and evidence terms

* **Entry gate:** preconditions required before phase execution.
* **PASS gate:** acceptance checks that must evaluate true for closure.
* **Commit evidence:** durable artifacts proving phase closure.
* **Blocker:** fail-closed condition that stops phase progression.

### 2.3 Evidence root contract

* Run-scoped root:
  * `s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/`
* Control/run-control root:
  * `s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m_phase_execution_id>/`

---

## 3. Operator Execution Contract

### 3.1 Required command families (semantic contract)

1. `dev-full-up`
   * apply all required stacks and deploy baseline runtime surfaces.
2. `dev-full-run`
   * execute `P1..P16` for a pinned run.
3. `dev-full-down`
   * execute `P17` teardown/idle-safe checks.

### 3.2 Canonical operator sequence

1. `dev-full-up`
2. `dev-full-run --platform_run_id <id> --scenario_run_id <id>`
3. verify `P16` final verdict and proof matrix
4. `dev-full-down`
5. verify `P17` idle-safe/cost-safe evidence

### 3.3 Fail-closed entry rule

Execution MUST NOT start if any required handle class is unresolved:

1. IAM role handles
2. secret path handles
3. topic handles
4. S3 path-pattern handles
5. run lock/reporter lock handles

### 3.4 Cost-to-outcome execution rule

Execution MUST NOT start a phase unless a phase spend envelope is recorded with:

1. max spend allowance for this phase window,
2. expected phase window duration,
3. hard stop condition if spend/quality drifts,
4. expected proof artifacts for closure.

Phase closure MUST publish a cost-to-outcome receipt containing:

1. spend consumed in phase window,
2. proof artifacts emitted,
3. decision/risk retired by that phase spend.

Phase advancement is fail-closed if spend is consumed without material proof outcome.

---

## 4. Phase Map (Summary)

| Phase | Name | Primary runtime | Closure anchor |
| --- | --- | --- | --- |
| P(-1) | PACKAGING_READY | GH Actions + ECR | immutable image digest + provenance |
| P0 | SUBSTRATE_READY | Terraform stacks | required handles resolvable |
| P1 | RUN_PINNED | Step Functions run-state entry | run header + config digest committed |
| P2 | DAEMONS_READY | EKS services | required service set healthy |
| P3 | ORACLE_READY | S3 + stream-view validation | oracle + stream-view contract valid |
| P4 | INGEST_READY | IG + MSK preflight | writer-boundary + bus ready |
| P5 | READY_PUBLISHED | SR + control topic | READY signal + receipt committed |
| P6 | STREAMING_ACTIVE | WSP + IG + MSK | ingest streaming active + lag bounded |
| P7 | INGEST_COMMITTED | IG receipts/quarantine | admit/quarantine/offset evidence complete |
| P8 | RTDL_CAUGHT_UP | RTDL + Redis/Aurora | inlet/projection closure committed |
| P9 | DECISION_CHAIN_COMMITTED | DF/AL/DLA | decision/action/audit closure committed |
| P10 | CASE_LABELS_COMMITTED | CM/LS + Aurora | case/label closure committed |
| P11 | SPINE_OBS_GOV_CLOSED | reporter/governance | spine closure + non-regression pack |
| P12 | LEARNING_INPUT_READY | OFS precheck lane | anti-leakage + replay basis pinned |
| P13 | OFS_DATASET_COMMITTED | Databricks | dataset manifest + fingerprint |
| P14 | MF_EVAL_COMMITTED | SageMaker + MLflow | train/eval + candidate bundle |
| P15 | MPR_PROMOTION_COMMITTED | MPR corridor | promote + rollback drill committed |
| P16 | FULL_PLATFORM_CLOSED | verdict aggregator | blocker-free final verdict |
| P17 | TEARDOWN_IDLE_SAFE | teardown workflow | cost-safe idle posture evidence |

---

## 5. Phase-by-Phase Authoritative Gates

For every phase below:

* Entry gate is mandatory before execution.
* PASS gate is mandatory for closure.
* Commit evidence must be durable in S3 evidence root.

### P(-1) PACKAGING_READY

* Entry gate: source revision pinned.
* PASS gate:
  1. image build/push success,
  2. immutable digest recorded,
  3. SBOM/provenance metadata emitted.
* Commit evidence: image digest manifest + release metadata receipt.
* Blockers: `DFULL-RUN-BP1` (build fail), `DFULL-RUN-BP2` (digest missing).

### P0 SUBSTRATE_READY

* Entry gate: remote state and lock backend reachable.
* PASS gate:
  1. stacks `core/streaming/runtime/data_ml/ops` apply cleanly,
  2. required IAM/secret surfaces exist,
  3. budget/alerts queryable.
* Commit evidence: stack apply snapshots + required-handle conformance report.
* Blockers: `DFULL-RUN-B0` (missing handles), `DFULL-RUN-B0.1` (state/lock failure).

### P1 RUN_PINNED

* Entry gate: `platform_run_id`, `scenario_run_id`, and config payload provided.
* PASS gate:
  1. run header committed once,
  2. `run_config_digest` committed,
  3. phase evidence root created.
* Commit evidence: run header JSON + run lock receipt.
* Blockers: `DFULL-RUN-B1` (pin missing/invalid), `DFULL-RUN-B1.1` (digest mismatch).

### P2 DAEMONS_READY

* Entry gate: service manifests resolved against pinned image digest.
* PASS gate:
  1. required service set healthy,
  2. run-scope env conformance true,
  3. telemetry heartbeat present.
* Commit evidence: daemon readiness snapshot + service binding matrix.
* Blockers: `DFULL-RUN-B2` (service health), `DFULL-RUN-B2.1` (binding drift).

### P3 ORACLE_READY

* Entry gate: oracle inputs and stream-view roots declared.
* PASS gate:
  1. required outputs present,
  2. stream-view materialization checks pass,
  3. manifest/contract checks pass fail-closed.
* Commit evidence: oracle readiness snapshot + required-output matrix.
* Blockers: `DFULL-RUN-B3` (missing output), `DFULL-RUN-B3.1` (stream-view contract failure).

### P4 INGEST_READY

* Entry gate: IG boundary handles and auth posture loaded.
* PASS gate:
  1. ingest and ops health endpoints healthy,
  2. boundary auth checks enforced,
  3. MSK topic readiness passes.
* Commit evidence: ingress preflight snapshot.
* Blockers: `DFULL-RUN-B4` (IG boundary failure), `DFULL-RUN-B4.1` (topic readiness failure).

### P5 READY_PUBLISHED

* Entry gate: SR joins/replay prerequisites pass.
* PASS gate:
  1. READY emitted to `fp.bus.control.v1`,
  2. READY receipt committed,
  3. duplicate/ambiguous READY prevented.
* Commit evidence: READY event proof + receipt artifact.
* Blockers: `DFULL-RUN-B5` (READY emission failure), `DFULL-RUN-B5.1` (duplicate ambiguity).

### P6 STREAMING_ACTIVE

* Entry gate: WSP source roots pinned for run.
* PASS gate:
  1. WSP->IG streaming active,
  2. lag within threshold,
  3. no unresolved publish ambiguity.
* Commit evidence: streaming counters snapshot + lag posture evidence.
* Blockers: `DFULL-RUN-B6` (streaming stall), `DFULL-RUN-B6.1` (publish unknown unresolved).

### P7 INGEST_COMMITTED

* Entry gate: active ingestion counters non-zero or explicit empty-run waiver.
* PASS gate:
  1. admit/quarantine summaries committed,
  2. offset snapshot committed,
  3. dedupe/anomaly checks pass.
* Commit evidence: receipt summary + quarantine summary + offset proof.
* Blockers: `DFULL-RUN-B7` (receipt surface missing), `DFULL-RUN-B7.1` (dedupe drift).

### P8 RTDL_CAUGHT_UP

* Entry gate: RTDL services healthy and consuming.
* PASS gate:
  1. inlet/projection closure passes,
  2. lane lag and reconciliation within threshold,
  3. archive writer closure evidence present.
* Commit evidence: RTDL core snapshot + archive closure marker.
* Blockers: `DFULL-RUN-B8` (RTDL lag), `DFULL-RUN-B8.1` (archive closure missing).

### P9 DECISION_CHAIN_COMMITTED

* Entry gate: RTDL closure from P8 is green.
* PASS gate:
  1. decision lane non-regressed and committed,
  2. action/outcome evidence committed,
  3. DLA append-only audit evidence committed.
* Commit evidence: decision/action/audit triplet snapshot.
* Blockers: `DFULL-RUN-B9` (decision chain drift), `DFULL-RUN-B9.1` (audit append failure).

### P10 CASE_LABELS_COMMITTED

* Entry gate: case trigger and label writer services healthy.
* PASS gate:
  1. case timeline append closes,
  2. label assertion/ack closure passes,
  3. writer-boundary anomalies absent.
* Commit evidence: case-label closure snapshot + append proofs.
* Blockers: `DFULL-RUN-B10` (case/label append failure), `DFULL-RUN-B10.1` (writer-boundary drift).

### P11 SPINE_OBS_GOV_CLOSED

* Entry gate: P8..P10 closures are all green.
* PASS gate:
  1. run report + reconciliation committed,
  2. governance append closure committed,
  3. spine non-regression anchor pack emitted.
* Commit evidence: spine closure pack + governance close marker.
* Blockers: `DFULL-RUN-B11` (obs/gov closure failure), `DFULL-RUN-B11.1` (non-regression pack missing).

### P12 LEARNING_INPUT_READY

* Entry gate: archive + labels + replay references resolved from spine closure.
* PASS gate:
  1. label as-of policy pinned,
  2. anti-leakage checks pass,
  3. learning input window/fingerprint basis committed.
* Commit evidence: learning input readiness snapshot.
* Blockers: `DFULL-RUN-B12` (leakage risk), `DFULL-RUN-B12.1` (input basis unresolved).

### P13 OFS_DATASET_COMMITTED

* Entry gate: P12 is green.
* PASS gate:
  1. OFS dataset build completes,
  2. dataset manifest committed,
  3. dataset fingerprint committed,
  4. rollback recipe committed.
* Commit evidence: OFS manifest + quality report + rollback recipe.
* Blockers: `DFULL-RUN-B13` (dataset build failure), `DFULL-RUN-B13.1` (manifest/fingerprint missing).

### P14 MF_EVAL_COMMITTED

* Entry gate: OFS dataset artifact from P13 is immutable.
* PASS gate:
  1. training/evaluation run completes,
  2. metrics/leakage checks pass,
  3. candidate bundle committed with provenance,
  4. safe-disable/rollback path committed.
* Commit evidence: MF eval report + MLflow run refs + candidate bundle receipt.
* Blockers: `DFULL-RUN-B14` (train/eval failure), `DFULL-RUN-B14.1` (quality gate fail).

### P15 MPR_PROMOTION_COMMITTED

* Entry gate: candidate bundle eligible from P14.
* PASS gate:
  1. promotion corridor event committed,
  2. rollback drill executed and recorded,
  3. active-bundle resolution checks pass,
  4. compatibility fail-closed checks pass.
* Commit evidence: promotion receipt + rollback drill report.
* Blockers: `DFULL-RUN-B15` (promotion gate failure), `DFULL-RUN-B15.1` (rollback drill missing).

### P16 FULL_PLATFORM_CLOSED

* Entry gate: phases `P1..P15` have no unresolved blockers.
* PASS gate:
  1. full source matrix is blocker-free,
  2. six-proof matrix complete for each major lane,
  3. final verdict published.
* Commit evidence: full-platform verdict bundle.
* Blockers: `DFULL-RUN-B16` (incomplete matrix), `DFULL-RUN-B16.1` (verdict inconsistency).

### P17 TEARDOWN_IDLE_SAFE

* Entry gate: P16 final verdict published.
* PASS gate:
  1. non-essential runtime scaled to zero or destroyed,
  2. no forbidden residual resources,
  3. budget/cost snapshot committed,
  4. evidence remains readable.
* Commit evidence: teardown snapshot + cost guardrail snapshot + residual scan report.
* Blockers: `DFULL-RUN-B17` (residual cost risk), `DFULL-RUN-B17.1` (evidence unreadable post-teardown).

---

## 6. Rerun/Reset Law (Dev-full)

### 6.1 Rerun constraints

1. Never rerun by deleting append-only truth surfaces.
2. Rerun from failed phase boundary using run-scoped reset playbook only.
3. If identity/config digest changes, issue new `platform_run_id`.

### 6.2 Mandatory reset classes

1. **Service/runtime reset:** restart/redeploy bounded lane only.
2. **Checkpoint reset:** only where reset policy is explicitly defined.
3. **Data replay reset:** rerun from committed replay basis, never from ad-hoc local inputs.

### 6.3 Stop-the-line conditions

1. Any unresolved `PUBLISH_UNKNOWN` ambiguity.
2. Any append-only ownership violation.
3. Any missing required evidence artifact at phase closure.
4. Any runtime drift from pinned stack substitutions.
5. Any phase that consumed spend without an accepted cost-to-outcome receipt.

---

## 7. Required Companion Authorities

Execution is blocked until these documents are present and pinned:

1. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`

---

## 8. Drift Watchlist

Fail-closed drift examples:

1. Any runtime fallback to laptop compute.
2. Any bus substitution away from MSK without authority repin.
3. Learning closure claimed without rollback drill evidence.
4. Full verdict claimed without six-proof lane matrix.
5. Cost-control closure missing at `P17`.

---

## Appendices

### Appendix A. Dev-full topic contract (summary)

Topic continuity and partition/retention classes are pinned by:

* `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md` (Appendix C)

The required v0 topic set includes:

* `fp.bus.control.v1`
* `fp.bus.traffic.fraud.v1`
* `fp.bus.context.arrival_events.v1`
* `fp.bus.context.arrival_entities.v1`
* `fp.bus.context.flow_anchor.fraud.v1`
* `fp.bus.rtdl.v1`
* `fp.bus.audit.v1`
* `fp.bus.case.triggers.v1`
* `fp.bus.labels.events.v1`
* `fp.bus.learning.ofs.requests.v1`
* `fp.bus.learning.ofs.events.v1`
* `fp.bus.learning.mf.requests.v1`
* `fp.bus.learning.mf.events.v1`
* `fp.bus.learning.registry.events.v1`

### Appendix B. Full-platform proof matrix publication rule

For each major lane (`spine`, `ofs`, `mf`, `mpr`, `teardown`) publish:

1. deploy proof
2. monitor proof
3. failure drill proof
4. recovery proof
5. rollback proof
6. cost-control proof

No lane closes without all six.
