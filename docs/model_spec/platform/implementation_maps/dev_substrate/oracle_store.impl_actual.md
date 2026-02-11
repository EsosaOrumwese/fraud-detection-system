# Oracle Store Implementation Map (dev_substrate)
_As of 2026-02-11_

## Entry: 2026-02-11 10:14AM - Pre-change lock: Oracle Store plan hardening to managed-only posture

### Trigger
USER requested a proper Oracle Store build plan and clarified Oracle in `dev_substrate` is not expected to be local.

### Context
`dev_substrate/oracle_store.build_plan.md` existed but was high-level and could still be interpreted with local-parity carry-over assumptions.

### Decision
Harden Oracle planning to strict managed substrate requirements:
1. S3-only truth authority in `dev_min`.
2. Explicit fail-closed checks for manifests/seals/stream-view readiness.
3. No implicit local fallback at any point in Oracle gate execution.
4. Run/operate and obs/gov onboarding as mandatory closure criteria.
5. Component-level cost and security guardrails documented as build DoD.

### Planned edits
1. Rewrite Oracle build-plan phases and DoD for managed-only posture.
2. Record closure rationale and resulting phase status after edit.

### Cost posture
Docs-only pass; no paid resources/services touched.

### Drift sentinel checkpoint
This decision reduces semantic drift risk by making Oracle gate requirements explicit and testable before SR/WSP progression.

## Entry: 2026-02-11 10:15AM - Applied Oracle Store managed-substrate build-plan rewrite

### Applied edits
1. Replaced `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.build_plan.md` with managed-only phase gates `O1..O8`.
2. Added explicit non-negotiable laws in the plan:
   - managed source only,
   - fail-closed compatibility posture,
   - by-ref run-scoped provenance,
   - mandatory run/operate + obs/gov coverage.
3. Added Oracle-specific security/retention/cost sentinel closure gate before matrix acceptance.

### Component-level rationale
Oracle is the first C&I coupling boundary in `3.C`, so ambiguity here propagates downstream quickly (SR/WSP/IG/EB). Tightening Oracle gate semantics first reduces drift probability in all subsequent component migrations.

### Outcome
- Oracle build plan now supports strict `3.C.1` execution with unambiguous managed-substrate expectations and closure criteria.

### Cost posture
Docs-only pass; no cloud/resource operations executed.

## Entry: 2026-02-11 10:46AM - Posture correction lock: Oracle Store is engine-owned truth, platform is consumer with managed landing

### Trigger
USER explicitly corrected Oracle posture to avoid implementation drift:
1. Oracle Store is closer to Data Engine ownership than platform service ownership.
2. Current practical step is managed landing sync/backfill into AWS S3 because direct engine write is not configured yet.
3. Sync can run while other C&I component build work proceeds; integrated run acceptance must wait for Oracle authority closure.

### Drift identified in previous plan wording
Prior wording over-emphasized platform-driven Oracle lifecycle and could be interpreted as if Oracle truth was platform-produced instead of engine-produced.

### Corrected decision
Rewrite Oracle build plan to enforce:
1. Engine-owned truth boundary.
2. Transitional managed landing sync mode (now) and direct engine-write mode (target).
3. O1 closure around source/destination pinning + sync evidence + consumer-side authority validation.
4. Explicit allowed/blocked execution rule while sync is in-flight.

### Files updated in this correction
1. `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.build_plan.md`
   - rewritten with corrected ownership and O1.A..O1.E structure.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - updated `3.C` and `3.C.1` expectation language to match managed landing + consumer-only authority posture.

### Why this is the correct expectation
It keeps platform responsibilities in bounds:
- platform does not claim artifact production ownership,
- platform does enforce fail-closed consumption guarantees and provenance pins.

### Cost posture
Docs/planning only in this pass; no paid resource operations executed.
