# Oracle Store Build Plan (v0)
_As of 2026-01-28_

## Purpose
Define the **sealed world boundary** for engine outputs as an explicit platform component. Oracle Store is a contract: immutable by‑ref artifacts, locator/digest rules, and environment ladder wiring.

## Planning rules (binding)
- **Progressive elaboration:** expand only the active phase into sections + DoD.
- **No secrets:** never embed credentials or tokens in plans or logs.
- **No scanning:** consumers must start from SR’s join surface; no “latest run” discovery.

## Phase plan (v0)

### Phase 1 — Oracle Store contract (current)
**Intent:** pin layout + immutability + locator rules so WSP/SR/IG consume a single boundary contract.

#### Phase 1.1 — Boundary + immutability
**DoD checklist:**
- Oracle Store defined as **write‑once sealed runs**; no in‑place overwrite.
- Contract states **by‑ref only** consumption; payload copies are out of scope.

#### Phase 1.2 — Locator + digest posture
**DoD checklist:**
- Locator schema pinned (reference engine interface pack).
- Content digests required; receipts used for proofed outputs.
- Fail‑closed rule documented (missing/invalid digest → reject/quarantine).

#### Phase 1.3 — Environment ladder + oracle_root config
**DoD checklist:**
- `oracle_root` is a wiring variable (not policy).
- Local default: `runs/local_full_run-5` (temporary; adjustable to `runs/data-engine`).
- Dev/Prod: S3‑compatible bucket + prefix (by‑ref only).

#### Phase 1.4 — Integration pins (SR/WSP/IG)
**DoD checklist:**
- SR `run_facts_view` is the only entrypoint to Oracle Store refs.
- WSP and legacy IG pull consume **only** locators from SR; no direct scanning.

#### Phase 1.5 — Validation checklist
**DoD checklist:**
- Explicit checklist for locator validation + digest verification.
- Documented “no PASS → no read” and “fail‑closed when unknown.”

**Status:** in progress.

### Phase 2 — Adapters (local FS + S3)
**Intent:** implement pluggable access for filesystem and S3‑compatible storage.

### Phase 3 — Ops + governance hardening
**Intent:** immutability enforcement, auditability, and operational safety.

