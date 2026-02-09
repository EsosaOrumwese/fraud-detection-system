# CaseTrigger Build Plan (v0)
_As of 2026-02-09_

## Purpose
Provide an executable, component-scoped plan for the CaseTrigger service aligned to platform Phase `5.2`.

## Authorities (binding)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `5.2`)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md`
- `docs/model_spec/platform/platform-wide/v0_environment_resource_tooling_map.md`
- `docs/model_spec/platform/component-specific/case_mgmt.design-authority.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`

## Planning rules (binding)
- Progressive elaboration only: expand active phase details as execution begins.
- No half-baked transitions: each phase requires explicit evidence-backed DoD closure.
- Rails are non-negotiable: ContextPins, by-ref evidence, append-only facts, idempotency, fail-closed compatibility.

## Component boundary
- CaseTrigger owns:
  - trigger eligibility/mapping from approved source evidence,
  - deterministic trigger identity + canonical hash generation,
  - publish boundary for explicit CaseTrigger events,
  - trigger-level observability/reconciliation.
- CaseTrigger does not own:
  - case timeline truth (`case_mgmt`),
  - label truth (`label_store`),
  - side effects (`action_layer`),
  - audit truth (`decision_log_audit`).

## Phase plan (v0)

### Phase 1 — Contract + taxonomy lock
**Intent:** lock explicit trigger vocab and payload contract before writer runtime code.

**DoD checklist:**
- Trigger vocab and source mapping are pinned and versioned.
- Contract includes required ContextPins, CaseSubjectKey, evidence refs, ids, and payload hash.
- Contract schema and runtime validator are aligned and tested.

### Phase 2 — Source adapters + eligibility gates
**Intent:** convert upstream evidence into valid trigger candidates without ambiguous mapping.

**DoD checklist:**
- Source adapters for `DF`/`AL`/`DLA`/external/manual classes are explicit.
- Unsupported source facts fail closed.
- Minimal by-ref enrichment is applied; no payload truth duplication.

### Phase 3 — Deterministic identity + collision handling
**Intent:** guarantee retry-safe and replay-safe trigger identities.

**DoD checklist:**
- Deterministic recipes for `case_id` and `case_trigger_id` are enforced.
- Canonical payload hash includes stable ref ordering.
- Same dedupe key + different payload hash emits anomaly and blocks overwrite.

### Phase 4 — Publish corridor (IG/EB or dedicated stream by profile)
**Intent:** publish CaseTriggers through a policy-governed ingress boundary.

**DoD checklist:**
- Publish path is pinned per env profile and runbooked.
- Publish outcomes (`ADMIT`, `DUPLICATE`, `QUARANTINE`, ambiguous) are explicit and persisted.
- Actor attribution derives from auth context at writer boundary.

### Phase 5 — Retry/checkpoint/replay safety
**Intent:** keep CaseTrigger deterministic under at-least-once transport.

**DoD checklist:**
- Retries preserve identity (no regenerated ids).
- Checkpoint progression waits on durable publish outcome.
- Replay reproduces identical trigger identities and downstream CM behavior.

### Phase 6 — CM intake integration gate
**Intent:** verify CaseTrigger->CM boundary correctness for case creation behavior.

**DoD checklist:**
- CM intake consumes CaseTrigger contract directly.
- Case creation idempotency holds on CaseSubjectKey.
- Duplicate trigger behavior is deterministic (append/no-op) and no-merge policy is preserved.

### Phase 7 — Observability + governance
**Intent:** make the trigger lane operationally diagnosable and auditable.

**DoD checklist:**
- Run-scoped counters emitted: `triggers_seen`, `published`, `duplicates`, `quarantine`, `publish_ambiguous`.
- Structured anomaly/governance events emitted for collision/publish failures.
- Reconciliation refs are available for plane-level run reporting.

### Phase 8 — Parity closure (20 + 200 evidence runs)
**Intent:** close CaseTrigger service readiness with monitored parity evidence.

**DoD checklist:**
- Monitored 20-event and 200-event parity runs capture CaseTrigger evidence artifacts.
- Negative-path injections prove fail-closed collision and unsupported-source behavior.
- Closure statement is explicit in impl map and linked to platform Phase `5.2` gate.

## Status (rolling)
- Phase 1 (`Contract + taxonomy lock`): complete (`10 passed` on 2026-02-09).
- Phase 2 (`Source adapters + eligibility gates`): complete (`8 passed` adapter suite; `18 passed` combined Phase1+2 suite on 2026-02-09).
- Phase 3 (`Deterministic identity + collision handling`): complete (`4 passed` replay suite; `22 passed` combined Phase1+2+3 suite on 2026-02-09).
- Phase 4 (`Publish corridor`): complete (`7 passed` phase4+IG onboarding suite; `31 passed` combined Phase1+2+3+4 suite on 2026-02-09).
- Phase 5 (`Retry/checkpoint/replay safety`): complete (`5 passed` phase5 checkpoint suite; `36 passed` combined Phase1+2+3+4+5 suite on 2026-02-09).
- Next action: begin Phase 6 (`CM intake integration gate`) with idempotent case-creation assertions on CaseSubjectKey.
