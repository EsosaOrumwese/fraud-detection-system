# World Streamer (WS) Implementation Map
_As of 2026-01-26_

This is the **decision trail notebook** for WS. It captures the reasoning and choices as they are made.

---

## Entry: 2026-01-26 02:24:10 — Design authority creation (WS)

### Trigger
User requested a design authority doc for the new inlet vertex that turns sealed engine outputs into a temporal stream (World Streamer).

### Live reasoning
- The platform already pins **SR as readiness authority** and **IG as admission boundary**. A streaming inlet must sit **between** them to avoid violating truth ownership.
- WS must be **by‑ref**: it reads `run_facts_view` + locators and never scans engine directories or infers “latest.”
- WS must **not** publish to EB; it must push into IG so all trust and schema enforcement happens in one place.
- Temporal realism requires a **release frontier** so the platform only sees events “up to now,” not the whole sealed world.
- Checkpoints must be durable and monotonic. Postgres is the safest default because WS is an ingestion‑grade component and we already depend on Postgres for authority/leases.

### Decisions captured in the design authority
- WS consumes READY + `run_facts_view` and streams only `business_traffic` locators.
- WS emits canonical envelopes into IG push ingress (never directly to EB).
- WS enforces no‑future‑leak via a release frontier (wall‑clock or accelerated).
- WS persists checkpoints (run_id/output_id/file/cursor/frontier_ts_utc) in Postgres; object store JSONL is local fallback only.

### Files created
- `docs/model_spec/platform/component-specific/world_streamer.design-authority.md`

