# Online Feature Plane Implementation Map
_As of 2026-02-05_

---

## Entry: 2026-02-05 15:13:10 — Phase 4 planning kickoff (OFP scope + pins)

### Problem / goal
Prepare Phase 4.3 by locking OFP v0 outer-contract decisions (inputs, provenance, and serve semantics) before code is written.

### Authorities / inputs
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/online_feature_plane.design-authority.md`
- Platform rails (canonical envelope, ContextPins, no-PASS-no-read).
- RTDL contracts in `docs/model_spec/platform/contracts/real_time_decision_loop/`.

### Decisions captured (v0 stance)
- OFP is **hot-path projector + serve surface**; consumes admitted EB events; no batch-only posture.
- Scope is **run/world-scoped by ContextPins**; no cross-run features in v0.
- Serving is **as-of time**: DF calls `get_features(as_of_time_utc = event ts_utc)`; no hidden “now.”
- Provenance required in every response: `input_basis` (EB offsets), feature group versions, `graph_version` (if IEG consulted), and `snapshot_hash`.
- Idempotent update key must include `(stream, partition, offset, key_type, key_id, group_name, group_version)`; duplicates/out-of-order are normal.
- Feature definitions are versioned artifacts; OFP records the activated feature-def policy revision in snapshot provenance.

### Planned implementation scope (Phase 4.3)
- Define Postgres schema for feature state + checkpoints.
- Implement EB consumer (file-bus first; Kinesis later) with idempotent apply.
- Implement `get_features` API (internal call surface) returning deterministic snapshot + provenance.
- Emit OFP health/lag signals for DL input (metrics/logs; no business events).

---
