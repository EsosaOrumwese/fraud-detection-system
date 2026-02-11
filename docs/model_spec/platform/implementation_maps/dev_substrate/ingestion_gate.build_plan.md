# Ingestion Gate Build Plan (dev_substrate)
_As of 2026-02-11_

## Purpose
Migrate IG for `dev_min` Control + Ingress (`3.C`) as the sole admission boundary with deterministic dedupe/publish semantics and append-only receipt truth.

## Authority anchors
- `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (Phase `3.C`)

## Migration phases (3.C scoped)
### Phase C1 - Profile/wiring + auth boundary gate
**Intent:** bind IG to dev_min corridor with explicit ingress auth and substrate handles.

**DoD checklist:**
- [ ] IG loads `dev_min` profile with no legacy/local fallback drift.
- [ ] Ingress auth posture is explicit and enforced.
- [ ] Required runtime stores (object/evidence/quarantine + state tables) resolve correctly.

### Phase C2 - Admission semantics gate
**Intent:** preserve canonical envelope + class/policy + dedupe correctness.

**DoD checklist:**
- [ ] Envelope/schema/pin checks are fail-closed.
- [ ] Dedupe tuple + payload-hash anomaly semantics hold.
- [ ] Class-map/policy alignment remains explicit for traffic/context/control/audit families.

### Phase C3 - Publish state machine + receipt truth gate
**Intent:** ensure admitted outcomes are durable and auditable.

**DoD checklist:**
- [ ] Publish state transitions (`IN_FLIGHT`, `ADMITTED`, `AMBIGUOUS`) are persisted.
- [ ] `ADMITTED` always includes valid `eb_ref`.
- [ ] Receipt/quarantine refs are run-scoped and append-only.

### Phase C4 - Run/operate + obs/gov onboarding
**Intent:** integrate IG lifecycle and governance outputs into migration meta-layers.

**DoD checklist:**
- [ ] IG lifecycle is pack-managed in `dev_min`.
- [ ] Governance/anomaly emissions are present for admission and policy surfaces.
- [ ] Run reporter can resolve IG evidence refs without manual stitching.

### Phase C5 - IG migration matrix closure
**Intent:** close IG green before EB final coupled-chain closure.

**DoD checklist:**
- [ ] IG matrix green on `dev_min` for admit/duplicate/quarantine/publish paths.
- [ ] Evidence refs recorded in dev_substrate impl/logbook.
- [ ] No unresolved fail-open behavior remains.

## Current status
- Phase C1: not started
- Phase C2: not started
- Phase C3: not started
- Phase C4: not started
- Phase C5: not started
