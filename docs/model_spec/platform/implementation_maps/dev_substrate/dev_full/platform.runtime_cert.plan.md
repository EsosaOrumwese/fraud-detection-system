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
1. steady profile
2. burst profile
3. bounded soak profile

DoD:
- [ ] scorecard metrics meet pinned thresholds for all profiles.
- [ ] latency/availability/lag/error posture is recorded with distributions.
- [ ] profile verdicts are deterministic and blocker-aware.

### RC3 - Tier 0 runtime drill pack certification
Goal:
1. Prove required runtime failure-mode drills with bounded recovery and integrity checks.

Mandatory drill families (aligned to truth anchor):
1. replay/backfill integrity
2. lag spike and recovery
3. schema evolution safety
4. dependency outage with degrade/recover
5. runtime cost guardrail response

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

## 6) Runtime blocker taxonomy
1. `RC-B1` claim mapping incompleteness.
2. `RC-B2` metric definition/window ambiguity.
3. `RC-B3` missing or unreadable runtime evidence.
4. `RC-B4` steady/burst/soak scorecard failure.
5. `RC-B5` drill integrity or recovery-bound failure.
6. `RC-B6` non-deterministic rollup/verdict artifact.
7. `RC-B7` unresolved Tier 0 claim in final verdict.

## 7) Acceptance posture
1. Runtime certification is `GREEN` only when all Tier 0 runtime claims are evidence-pass and blocker-free.
2. Tier 1/Tier 2 can be partial, but must be explicitly marked with closure debt and no hidden ambiguity.
3. Any ambiguity defaults to fail-closed.

