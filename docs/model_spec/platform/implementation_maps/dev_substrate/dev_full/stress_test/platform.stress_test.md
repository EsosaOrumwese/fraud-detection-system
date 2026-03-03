# Dev Full Platform Stress-Test Program
_Track: dev_substrate/dev_full_
_As of 2026-03-03_
_Status: ACTIVE PROGRAM AUTHORITY_

## 0) Objective
Harden the platform for realistic production throughput and stability by stress testing:
1. components first,
2. planes second,
3. full platform last,
while remediating bottlenecks phase-by-phase (`M0..M15`) before certification attempts.

Certification is treated as a verification event after stress hardening, not as a discovery workflow.

## 1) Why This Program Exists
Root problem:
1. certification was attempted before stress hardening, causing late-stage failures and high remediation cost.

Program correction:
1. use existing build decisions as the test target,
2. detect likely bottlenecks before expensive long runs,
3. adapt design/runtime decisions when evidence shows bottlenecks,
4. rerun only after targeted remediation.

## 2) Core Rules (Binding)
1. Realistic production standards only. No checkbox testing.
2. Fail-closed progression: no phase advancement with unresolved blockers.
3. Decision-first testing: inspect phase build decisions before launching load.
4. Cost-first discipline: do not run tests that are already predicted to fail for known bottlenecks.
5. Determinism and truth-boundary laws are non-negotiable.

## 3) Clarification on Local Development vs No Local Runtime
Pinned interpretation:
1. `No local compute` means runtime/cert claims must not depend on laptop runtime resources.
2. Local engineering work is required and encouraged:
   - design,
   - code changes,
   - local profiling/unit/integration checks.
3. Workflows are for controlled managed execution, regression gates, and evidence capture, not primary ad-hoc debugging.

## 4) M-Phase Stress Overview (Before Deep Plans)
This is the program-level overview of what each `M*` phase stress effort is expected to achieve before deep `platform.M*.stress_test.md` files are elaborated.

| Stress Phase | Build Scope Anchor | What We Aim to Achieve | Exit Signal | Status |
| --- | --- | --- | --- | --- |
| M0 | Mobilization + authority lock | Validate test authority, handles, and stress evidence surfaces before any load | All prerequisite stress handles and evidence sinks are green | ACTIVE |
| M1 | Packaging readiness | Stress packaging/provenance paths for reproducible deploy artifacts under concurrent operations | No packaging bottleneck or provenance drift under stress | NOT_STARTED |
| M2 | Substrate readiness | Stress core substrate primitives (network/store/bus/runtime) for baseline capacity and failure behavior | Substrate can sustain target baseline load without integrity drift | NOT_STARTED |
| M3 | Run pinning + orchestrator readiness | Stress run-control/orchestrator behavior under concurrent run activation and retries | Run pinning remains deterministic; no cross-run mixing | NOT_STARTED |
| M4 | Spine runtime-lane readiness | Stress each spine lane bootstrap path for startup-time, readiness, and dependency bottlenecks | Lane startup and steady-state readiness meet target budgets | NOT_STARTED |
| M5 | Oracle readiness + ingest preflight (`P3-P4`) | Stress oracle-to-ingress preflight flow for input correctness and ingest warm-path limits | Preflight pass is stable; no upstream-induced ingress stalls | NOT_STARTED |
| M6 | Control + Ingress (`P5-P7`) | Stress SR/WSP/IG/bus at component -> plane -> integrated levels for throughput and correctness | Target ingress throughput + latency met with replay-safe semantics | NOT_STARTED |
| M7 | RTDL + Case/Labels (`P8-P10`) | Stress decision loop + case/label pathways for sustained throughput and bounded lag | Decision/action/case/label lanes keep pace with ingress without silent degrade | NOT_STARTED |
| M8 | Spine Obs/Gov (`P11`) | Stress observability/governance paths so evidence remains complete under high event rates | Evidence completeness + low-overhead telemetry proven | NOT_STARTED |
| M9 | Learning input readiness (`P12`) | Stress replay-basis/as-of/maturity extraction paths for correctness under realistic volume | Learning input lanes produce deterministic, timely, leak-safe outputs | NOT_STARTED |
| M10 | OFS dataset closure (`P13`) | Stress offline feature dataset generation for throughput, stability, and cost posture | Dataset builds finish within budget with reproducible manifests | NOT_STARTED |
| M11 | MF train/eval closure (`P14`) | Stress model train/eval orchestration for queueing, runtime, and artifact integrity | Train/eval flow stable with deterministic evidence and bounded runtime | NOT_STARTED |
| M12 | MPR promotion/rollback (`P15`) | Stress model promotion, rollback, and resolution lanes under repeated activation pressure | Promotion/rollback deterministic and fail-closed under stress | NOT_STARTED |
| M13 | Full-platform verdict + teardown (`P16-P17`) | Stress full-platform execution windows plus teardown and idle-safe guarantees | Full-lane run + teardown remains stable, complete, and cost-safe | NOT_STARTED |
| M14 | Runtime-placement repin materialization | Stress any placement repins to validate they improve or preserve performance and reliability | Repinned runtime lanes meet or exceed prior stress baselines | NOT_STARTED |
| M15 | Data semantics realization | Stress real-data semantics in learning/evolution lanes at production-like volume and quality | Semantic realism + runtime budget + no-leakage gates all green | NOT_STARTED |

Subphase routing note:
1. Deep stress files may be split (for example `M5.P3`, `M6.P5`, `M7.P8`) when a phase has distinct lanes with different bottleneck signatures.

## 5) Stress Methodology (Per Phase)

### 5.1 Stage A - Decision/Bottleneck Pre-Read
Before stressing a phase:
1. read the phase build authority (`platform.M*.build_plan.md` and relevant `impl_actual` entries),
2. map runtime surfaces for that phase (compute, stores, messaging, IAM, network),
3. identify likely bottlenecks and failure points,
4. classify each finding:
   - `PREVENT`: must fix before running,
   - `OBSERVE`: acceptable to test directly with instrumentation,
   - `ACCEPT`: low risk under current target.

No stress run starts if unresolved `PREVENT` items exist.

### 5.2 Stage B - Component Stress
1. stress each component in the phase independently.
2. isolate local component limits before cross-component coupling noise.
3. capture component-specific saturation curves and error boundaries.

### 5.3 Stage C - Plane Stress
1. stress integrated plane flow (for example: Control+Ingress or RTDL).
2. validate count continuity and latency budgets across interfaces.
3. confirm no hidden queue growth or silent degrade.

### 5.4 Stage D - Full Platform Stress (Scoped to Phase Envelope)
1. execute bounded full-lane workload with phase scope.
2. run soak + burst windows.
3. run bounded failure injection.

### 5.5 Stage E - Remediate and Re-Validate
1. rank bottlenecks by impact and remediation cost.
2. apply targeted fixes.
3. rerun same test profile for direct before/after proof.

## 6) Evidence Contract (Required for Every Stress Step)
1. target profile and workload definition.
2. runtime and config digests.
3. throughput/latency results (`p50`, `p95`, `p99`, error rates).
4. queue/lag/posture snapshots.
5. blocker register (`open`, `resolved`, `waived` with explicit user approval only).
6. cost window snapshot and cost-to-outcome receipt.

No stress step is closed without artifact publication and readback verification.

## 7) Program Structure (Mirrors Build Phase Ladder)
Stress program follows the same canonical ladder:
1. `M0`
2. `M1`
3. `M2`
4. `M3`
5. `M4`
6. `M5`
7. `M5.P3`
8. `M5.P4`
9. `M6`
10. `M6.P5`
11. `M6.P6`
12. `M6.P7`
13. `M7`
14. `M7.P8`
15. `M7.P9`
16. `M7.P10`
17. `M8`
18. `M9`
19. `M10`
20. `M11`
21. `M12`
22. `M13`
23. `M14`
24. `M15`

Per-phase stress files are created only when each phase is activated.

## 8) Phase Activation and Naming Convention
Program control file:
1. `stress_test/platform.stress_test.md` (this file).

Per-phase files (progressive creation):
1. `stress_test/platform.M0.stress_test.md`
2. `stress_test/platform.M1.stress_test.md`
3. ...
4. `stress_test/platform.M15.stress_test.md`

Dedicated phase-file creation rule (deterministic):
1. Keep phase inline in `platform.stress_test.md` when all are true:
   - single-lane or low-coupling stress scope,
   - low expected runtime and low spend,
   - no expected architecture/placement repin,
   - simple blocker taxonomy.
2. Create `platform.M*.stress_test.md` when any are true:
   - multi-lane coupled stress path,
   - custom load profile + failure matrix required,
   - moderate/high expected runtime or spend,
   - likely build-decision bottleneck requiring repin,
   - non-trivial blocker and rerun topology.
3. Default focus guidance:
   - `M0` is inline by default.
   - `M1` and `M3` are usually inline unless complexity expands.
   - heavy phases are expected to get dedicated files (`M2`, `M4`, `M5+subphases`, `M6`, `M7+subphases`, `M8`, `M9..M15`).
4. Re-evaluation rule:
   - if an inline phase expands beyond rule-1 boundaries during execution, create a dedicated phase file before further stress work.

Each phase file must contain:
1. scope and dependency map,
2. pre-read bottleneck analysis,
3. component stress plan,
4. plane stress plan,
5. phase-full run plan,
6. remediation loop and rerun policy,
7. DoD and blocker taxonomy,
8. budget envelope and teardown posture.

## 9) Runtime and Cost Gates (Global)
Global runtime gates:
1. no phase run is accepted with unexplained stalls/hours-long single-state runtime unless explicitly user-waived.
2. no unresolved count mismatch across critical producer/consumer boundaries.
3. no persistent lag growth at steady-state target load.

Global cost gates:
1. no unattributed spend.
2. non-active lanes remain stopped.
3. each stress window has deterministic teardown.

## 10) Adaptation Policy (When to Cut/Increase/Change Direction)
For any phase:
1. if measured bottleneck is algorithmic/path-bound, optimize code and data path first.
2. if bottleneck remains after path optimization, resize runtime resources.
3. if both fail, repin architecture/placement decision for that lane.
4. if a test profile is clearly invalid for current known constraints, stop early and remediate first instead of burning cost.

## 11) Relationship to Existing Build Authorities
1. Build authorities remain the design and infrastructure intent source.
2. Stress authorities validate whether those decisions meet realistic production standards.
3. When stress evidence contradicts a build decision:
   - open blocker,
   - propose decision change,
   - update authority before proceeding.

## 12) Program Status (Initial)
1. Program bootstrapped.
2. Active phase: `M0` (inline in this file).
3. Per-phase stress files not yet created.
4. Next step: close M0 `PREVENT` items, then decide `M0 DONE -> M1` transition.

## 13) Active Phase - M0 (Inline)
Status:
1. `ACTIVE`

M0 stress objective:
1. ensure stress program governance is execution-ready before any runtime load is attempted.

M0 stress scope:
1. authority and precedence readback for stress program.
2. stress handle and evidence-surface readiness checks.
3. phase activation control and blocker taxonomy lock.

Stage A pre-read inputs used:
1. `platform.M0.build_plan.md`
2. `platform.build_plan.md`
3. `dev_full_handles.registry.v0.md`

Stage A findings classification:

| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M0-ST-F1` | `PREVENT` | Stress program does not yet pin a dedicated stress-handle packet (targets/profile IDs/window settings) independent of certification knobs. | Define and pin `M0` stress-handle packet before `M1` stress activation. |
| `M0-ST-F2` | `PREVENT` | Stress evidence contract exists, but M0 has no explicit stress blocker register artifact path yet. | Pin M0 stress blocker register artifact contract in M0 closure step. |
| `M0-ST-F3` | `OBSERVE` | Handles registry still contains unresolved `TO_PIN` items mapped to later runtime phases (`M2+`). | Track as forward dependency risk; no M0 runtime action required. |
| `M0-ST-F4` | `ACCEPT` | M0 build phase is docs/control-only with no runtime mutation; this aligns with stress program startup posture. | Continue M0 inline execution and close governance prerequisites. |

M0 blockers (open):
1. `M0-ST-B1`: stress-handle packet not yet pinned.
2. `M0-ST-B2`: explicit M0 stress blocker-register artifact contract not yet pinned.

M0 DoD (stress):
- [x] Stage A pre-read completed and classified (`PREVENT`/`OBSERVE`/`ACCEPT`).
- [ ] Stress-handle packet pinned for downstream phase activation.
- [ ] M0 stress blocker-register artifact contract pinned.
- [ ] M0 blocker set closed (`M0-ST-B1`, `M0-ST-B2`).
- [ ] M0 closure note written in stress implementation map and logbook.

M0 immediate actions:
1. Add M0 stress-handle packet section (targets/windows/profile IDs) to this authority or a dedicated handle companion.
2. Add explicit M0 blocker-register artifact path pattern to evidence contract.
3. Close `M0-ST-B1/B2`, then mark `M0 DONE` and move to `M1` decision pre-read.
