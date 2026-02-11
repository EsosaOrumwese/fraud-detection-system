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

## Entry: 2026-02-11 10:51AM - Pre-change lock: carry stream-sort contract from local parity into dev_substrate Oracle plan

### Trigger
USER requested that Oracle build planning explicitly include the sorted-stream requirement from local parity because downstream runtime consumes sorted stream views, not raw landed artifacts.

### Context reviewed
1. `docs/runbooks/platform_parity_walkthrough_v0.md` section 4.3 stream sort contract:
   - per-output stream view under `stream_view/ts_utc/output_id=<output_id>/part-*.parquet`,
   - deterministic ordering and required receipts/manifests.
2. `local_parity/oracle_store.impl_actual.md` and `local_parity/platform.impl_actual.md`:
   - stable per-output sort contract,
   - tie-breakers (`filename`, `file_row_number`) with `ts_utc`,
   - explicit policy for non-`ts_utc` outputs,
   - fail-closed on partial stream-view state.

### Decision
Update Oracle and platform build plans so `3.C.1` explicitly requires stream-sort closure after landing sync:
1. landing sync alone is insufficient for acceptance,
2. stream-view artifacts/receipts become mandatory Oracle authority evidence,
3. non-`ts_utc` outputs must use explicit pinned fallback sort keys (no ad-hoc runtime choice),
4. partial stream view must fail closed.

### Planned edits
1. `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.build_plan.md`
   - add stream-sort subphase and DoD under O1.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - extend `3.C.1` required checks/stop conditions to include sort-contract evidence.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-11 10:54AM - Corrective precision note: output-id source refs pinned for stream-sort selection

### Correction
Added an explicit checklist item in `oracle_store.build_plan.md` O1.C requiring output-id sets to be pinned from policy refs before executing stream-sort.

### Why
Prevents ambiguous operator selection of datasets and ensures sort coverage aligns with declared runtime traffic/context output contracts.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-11 10:53AM - Applied stream-sort contract into Oracle O1 plan

### Applied changes
1. Updated `dev_substrate/oracle_store.build_plan.md` to make sorted stream-view closure explicit in O1:
   - added `O1.C Stream-view sort closure`,
   - shifted downstream sections to `O1.D`/`O1.E`/`O1.F`.
2. Added required sorting contract details:
   - per-output path: `stream_view/ts_utc/output_id=<output_id>/part-*.parquet`,
   - deterministic ordering for `ts_utc` outputs (`ts_utc`, `filename`, `file_row_number`),
   - explicit pinned fallback sort keys for non-`ts_utc` outputs,
   - per-output `_stream_view_manifest.json` + `_stream_sort_receipt.json`,
   - fail-closed on partial view leftovers.
3. Expanded Oracle validation matrix expectations to include stream-sort closure and manifest/receipt integrity.

### Resulting posture
Landing sync alone is no longer sufficient for Oracle O1 closure; runtime-consumable sorted stream views are now part of the non-negotiable acceptance gate.

### Cost posture
Docs-only pass; no paid services touched.
