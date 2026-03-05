# Dev Full Road To Production-Ready Plan (Main)
_As of 2026-03-05_

## 0) Purpose
This is the main execution authority to move `dev_full` from stress-tested wiring to production-ready status under the binding authority:
- `docs/model_spec/platform/pre-design_decisions/dev-full_road-to-production-ready.md`

This document is not a progress checklist. It is a fail-closed gate program:
1. A phase cannot close because tasks were completed.
2. A phase closes only when gate intent is proven on realistic behavior/load with claimable evidence.
3. Any unresolved mismatch between gate intent and evidence blocks advancement.

## 1) Program Goal
Complete the production-grade mission objective (not toy validation) and declare `dev_full` production-ready within `RC2-S` only when:
1. `G1`, `G2`, `G3A`, `G3B`, and `G4` are all `PASS`.
2. Required evidence packs exist with deterministic paths and readable indexes.
3. Final verdict has `open_blockers=0`.

Mission-level intent that must be true at closure:
1. Platform sustains meaningful load (`steady -> burst -> recovery -> soak`) with SLO posture on correct measurement surfaces.
2. Platform preserves correctness under realistic data messiness (duplicates, replay, out-of-order, skew/hotkeys, join sparsity).
3. Platform is operationally governable (promotion proof, rollback proof, audit answerability, runbook/alert ownership).
4. Platform demonstrates bounded spend and clean idle-safe closure.

## 2) Phase And Gate Closure Sufficiency Standard (Binding)
Every phase and subphase must satisfy all closure tests below before it can be marked complete:
1. **Intent fidelity test**:
   The produced evidence proves the purpose of the gate/phase, not just execution of steps.
2. **Realism test**:
   Evidence is from declared realistic window/cohorts/load profile, using declared measurement surfaces.
3. **Claimability test**:
   Required artifacts, indexes, and verdict files are present/readable and deterministic.
4. **Blocker test**:
   `open_blockers=0` for the closing boundary, or status is explicitly `HOLD_REMEDIATE`.
5. **Anti-toy test**:
   No short-window/proxy-only/waived-low-sample closure is accepted for required claims.

## 3) Current Posture
1. Foundation wiring and control-plane hardening work is already present from prior stress program.
2. Production-ready declaration is not yet closed.
3. Remaining closure focus is data realism, operational certification packs, and go-live rehearsal.

## 4) Phase Ladder (PR0-PR5)

### PR0 - Program Lock And Status Owner Sync
Intent:
1. Establish one authoritative status surface for this road.
2. Pin mission charter identity and active gate map.
3. Materialize initial blocker register for unresolved required `TBD` fields in active scope.

Exit / DoD:
1. Status owner file is pinned and current.
2. Mission charter is present and scoped (`injection_path`, envelope, budgets, windows).
3. Initial blocker register exists with rerun boundaries.
4. No gate progression ambiguity exists between status owner and evidence pack posture.

### PR1 - G2 Data Realism Pack Closure
Intent:
1. Close 7-day realism and semantic readiness from actual platform-fed data.
2. Pin decisions for joins, allowlists, IEG minimal graph, and label maturity.

Subphase template:
1. `S0` entry and window pinning.
2. `S1` realism profile measurements.
3. `S2` join coverage and fanout closure.
4. `S3` RTDL allowlist and IEG decisions.
5. `S4` learning maturity and time-causality closure.
6. `S5` deterministic pack rollup and verdict.

Exit / DoD:
1. `G2` data realism pack complete and readable.
2. Required realism decisions pinned.
3. `open_blockers=0` for `G2`.
4. Unknowns are converted to pinned decisions or explicit blockers with rerun boundaries (no silent unknowns).

### PR2 - Numeric Contract Activation
Intent:
1. Activate required runtime and ops/gov numeric contract sections with no required `TBD`.
2. Ensure every threshold has declared measurement surface, sample minima, and failure path.

Subphase template:
1. `S0` required row inventory and gap map.
2. `S1` threshold population from measured evidence plus policy guardbands.
3. `S2` activation validation and anti-gaming checks.
4. `S3` activation verdict and blocker rollup.

Exit / DoD:
1. Active contract scope has no required `TBD`.
2. Activation verifier passes.
3. Contract activation blockers are zero.
4. Threshold rows are measurement-surface valid and anti-gaming checks pass.

### PR3 - G3A Runtime Operational Certification Pack
Intent:
1. Certify runtime hot-path behavior under `steady -> burst -> recovery -> soak`.
2. Prove runtime drills with claimable artifacts.

Subphase template:
1. `S0` preflight and run binding.
2. `S1` steady profile.
3. `S2` burst profile.
4. `S3` recovery profile.
5. `S4` soak profile plus runtime drills.
6. `S5` pack rollup and verdict.

Exit / DoD:
1. Required runtime metrics present on correct surfaces and pass thresholds.
2. Required runtime drill artifacts complete.
3. `G3A` pack has `open_blockers=0`.
4. Closure demonstrates runtime gate intent (not probe-only or checklist-only pass).

### PR4 - G3B Ops/Gov Operational Certification Pack
Intent:
1. Certify governed promotion corridor, rollback, audit answerability, and governance posture.
2. Close ops/gov cost enforcement slice.

Subphase template:
1. `S0` entry and authority binding.
2. `S1` promotion corridor proof.
3. `S2` rollback drill proof.
4. `S3` audit drill proof.
5. `S4` runbook and alert governance proof.
6. `S5` cost governance closure and pack verdict.

Exit / DoD:
1. Promotion, rollback, audit, and governance artifacts are complete.
2. Ops/gov thresholds pass.
3. `G3B` pack has `open_blockers=0`.
4. Closure demonstrates operational governability under change, not static-document compliance.

### PR5 - G4 Go-Live Rehearsal Mission Pack
Intent:
1. Run full rehearsal mission with controlled incident and controlled change.
2. Close with bounded cost and idle-safe teardown.

Subphase template:
1. `S0` rehearsal entry lock.
2. `S1` sustained operation segment.
3. `S2` burst and recovery segment.
4. `S3` controlled incident drill and recovery.
5. `S4` controlled change and rollback readiness plus audit drill.
6. `S5` cost closure, teardown residual scan, final verdict.

Exit / DoD:
1. Rehearsal events and required drill artifacts complete.
2. Cost-to-outcome and idle-safe closure complete.
3. Final verdict `PASS` with `open_blockers=0`.
4. Final pack proves mission intent end-to-end and is claimable as production-ready within `RC2-S`.

## 5) Fail-Closed Operating Rules
1. No phase advances with unresolved blockers.
2. No certification claim from missing metrics or missing artifacts.
3. No metric claims from wrong measurement surfaces.
4. No run under non-activatable contract rows.
5. No rerun-the-world posture; rerun only declared blocker boundary.
6. No closure from checklist completion alone without gate-intent proof.

## 6) Rerun Discipline
1. Each blocker record must carry exact rerun boundary.
2. Remediation is accepted only when rerun evidence removes blocker.
3. Historical failed packs remain retained as remediation evidence.

## 7) Forbidden Closure Patterns (Anti-Circle)
1. Marking a phase complete because all substeps ran, while gate-intent evidence remains weak/incomplete.
2. Passing throughput/latency using proxy counters that do not match declared injection path scope.
3. Accepting waived-low-sample posture for required claim boundaries.
4. Declaring readiness with missing mandatory drill bundles.
5. Declaring readiness with unattributed spend or non-clean teardown residuals.

## 8) Execution Rhythm
1. Expand detail only for the active phase/subphase before execution.
2. Keep one status owner updated after every attempt.
3. Append implementation-map and logbook entries at pre-edit and post-edit points.

## 9) Document Completion Rule
This plan's intent is satisfied only when:
1. The mission objective in Section 1 is fully proven by gate outputs.
2. Each phase closure satisfies the sufficiency standard in Section 2.
3. The final production-ready verdict is claimable, auditable, and has `open_blockers=0`.

## 10) Immediate Next Step
1. Start `PR0-S0`: pin authoritative status owner and mission charter entry bindings for this road.
