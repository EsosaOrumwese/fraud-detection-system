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

## 4) Stress Methodology (Per Phase)

### 4.1 Stage A - Decision/Bottleneck Pre-Read
Before stressing a phase:
1. read the phase build authority (`platform.M*.build_plan.md` and relevant `impl_actual` entries),
2. map runtime surfaces for that phase (compute, stores, messaging, IAM, network),
3. identify likely bottlenecks and failure points,
4. classify each finding:
   - `PREVENT`: must fix before running,
   - `OBSERVE`: acceptable to test directly with instrumentation,
   - `ACCEPT`: low risk under current target.

No stress run starts if unresolved `PREVENT` items exist.

### 4.2 Stage B - Component Stress
1. stress each component in the phase independently.
2. isolate local component limits before cross-component coupling noise.
3. capture component-specific saturation curves and error boundaries.

### 4.3 Stage C - Plane Stress
1. stress integrated plane flow (for example: Control+Ingress or RTDL).
2. validate count continuity and latency budgets across interfaces.
3. confirm no hidden queue growth or silent degrade.

### 4.4 Stage D - Full Platform Stress (Scoped to Phase Envelope)
1. execute bounded full-lane workload with phase scope.
2. run soak + burst windows.
3. run bounded failure injection.

### 4.5 Stage E - Remediate and Re-Validate
1. rank bottlenecks by impact and remediation cost.
2. apply targeted fixes.
3. rerun same test profile for direct before/after proof.

## 5) Evidence Contract (Required for Every Stress Step)
1. target profile and workload definition.
2. runtime and config digests.
3. throughput/latency results (`p50`, `p95`, `p99`, error rates).
4. queue/lag/posture snapshots.
5. blocker register (`open`, `resolved`, `waived` with explicit user approval only).
6. cost window snapshot and cost-to-outcome receipt.

No stress step is closed without artifact publication and readback verification.

## 6) Program Structure (Mirrors Build Phase Ladder)
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

## 7) Phase Activation and Naming Convention
Program control file:
1. `stress_test/platform.stress_test.md` (this file).

Per-phase files (progressive creation):
1. `stress_test/platform.M0.stress_test.md`
2. `stress_test/platform.M1.stress_test.md`
3. ...
4. `stress_test/platform.M15.stress_test.md`

Each phase file must contain:
1. scope and dependency map,
2. pre-read bottleneck analysis,
3. component stress plan,
4. plane stress plan,
5. phase-full run plan,
6. remediation loop and rerun policy,
7. DoD and blocker taxonomy,
8. budget envelope and teardown posture.

## 8) Runtime and Cost Gates (Global)
Global runtime gates:
1. no phase run is accepted with unexplained stalls/hours-long single-state runtime unless explicitly user-waived.
2. no unresolved count mismatch across critical producer/consumer boundaries.
3. no persistent lag growth at steady-state target load.

Global cost gates:
1. no unattributed spend.
2. non-active lanes remain stopped.
3. each stress window has deterministic teardown.

## 9) Adaptation Policy (When to Cut/Increase/Change Direction)
For any phase:
1. if measured bottleneck is algorithmic/path-bound, optimize code and data path first.
2. if bottleneck remains after path optimization, resize runtime resources.
3. if both fail, repin architecture/placement decision for that lane.
4. if a test profile is clearly invalid for current known constraints, stop early and remediate first instead of burning cost.

## 10) Relationship to Existing Build Authorities
1. Build authorities remain the design and infrastructure intent source.
2. Stress authorities validate whether those decisions meet realistic production standards.
3. When stress evidence contradicts a build decision:
   - open blocker,
   - propose decision change,
   - update authority before proceeding.

## 11) Program Status (Initial)
1. Program bootstrapped.
2. Per-phase stress files not yet created.
3. Next step: activate `M0` stress file and run Stage A decision/bottleneck pre-read for M0 surfaces.
