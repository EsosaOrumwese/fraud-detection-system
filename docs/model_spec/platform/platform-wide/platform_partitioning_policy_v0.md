# Partitioning Policy Guidance (v0)
_As of 2026-01-24_

This note pins **how partition routing is chosen** at the platform edge (IG). It is guidance for Phase‑1.3 and is not a full IG spec.

---

## Core rules (binding)

1. **IG stamps partition_key** — EB never infers partitioning.
2. **Partitioning is deterministic** — the same event must yield the same `partition_key`.
3. **Ordering is partition‑only** — choose keys that preserve the ordering that matters to the hot path.
4. **Routing profiles are versioned** — IG uses `partitioning_profile_id` from policy profiles.
5. **Invariant changes require new stream versions** — do not change routing identity in place.

---

## Recommended v0 posture

### Traffic stream (`fp.bus.traffic.v1`)
Prefer **entity‑local ordering** so projections and features remain stable under replay.

Typical precedence (use the first available):
1. `flow_id`
2. `merchant_id`
3. `account_id` / `party_id`
4. `event_id` (fallback only)

### Control stream (`fp.bus.control.v1`)
Use **run‑scoped ordering** to keep control facts ordered by run:
1. `run_id`
2. `manifest_fingerprint`
3. `event_id`

### Audit pointer stream (`fp.bus.audit.v1`)
Pointers are non‑authoritative; ordering only needs to be stable:
1. `event_id`
2. `manifest_fingerprint`

---

## Implementation note (IG policy)
The policy profile should express **what fields or JSON paths** to use, with fallbacks. IG computes the final `partition_key` deterministically from those inputs.

