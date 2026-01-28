# World Stream Producer Build Plan (v0)
_As of 2026-01-28_

## Purpose
Implement WSP as the **primary runtime producer** that replays sealed engine `business_traffic` into IG under SR’s join surface, preserving bank‑like temporal flow.

## Planning rules (binding)
- **Progressive elaboration:** expand only the active phase into sections + DoD.
- **WSP never writes to EB:** IG remains the only writer.
- **No scanning:** READY + `run_facts_view` is the only entrypoint.
- **Speedup is a policy knob in all envs** (same semantics at any speed).

## Phase plan (v0)

### Phase 1 — Core stream head (current)
**Intent:** READY‑driven stream production with canonical envelopes and oracle by‑ref reads.

#### Phase 1.1 — READY intake + join surface
**DoD checklist:**
- Consume READY (control bus) idempotently.
- Resolve and validate `run_facts_view` pins (fail‑closed on mismatch).

#### Phase 1.2 — StreamPlan derivation
**DoD checklist:**
- Derive StreamPlan from `run_facts_view` traffic targets.
- Honor `traffic_delivery_mode=STREAM`; refuse to stream on `PULL`.

#### Phase 1.3 — Oracle Store by‑ref reads
**DoD checklist:**
- Use locators + digests only (no “latest” scans).
- Enforce “no PASS → no read” using proof refs where required.

#### Phase 1.4 — Canonical envelope framing
**DoD checklist:**
- Emit canonical envelope with stable `event_id`, `event_type`, `ts_utc`, pins.
- Preserve legacy pull compatibility where required (naming + payload structure).

#### Phase 1.5 — Temporal pacing + speedup factor
**DoD checklist:**
- Event‑time pacing is defined (no future leakage).
- `stream_speedup` is configurable in **all envs** (policy knob).

#### Phase 1.6 — IG push interface
**DoD checklist:**
- WSP pushes to IG ingress; no direct EB writes.
- Failure handling is explicit (retry vs halt vs quarantine trigger).

**Status:** in progress.

### Phase 2 — Checkpointing + resume
**Intent:** operational continuity under restarts and at‑least‑once delivery.

### Phase 3 — Security + governance hardening
**Intent:** producer identity allowlists, provenance stamping, audit hooks.

### Phase 4 — Validation (smoke + dev completion)
**Intent:** WSP→IG path validates under local smoke and dev completion policies.

