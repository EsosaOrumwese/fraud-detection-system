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

#### Phase 1.6 — V0 transitional allowances
**DoD checklist:**
- Pack‑root aliasing documented (current `runs/local_full_run-*` treated as pack roots).
- Seal markers optional for **local** until packer exists; strict seal reserved for dev/prod.
- `run_facts_view` traffic allowlist clarified (v0 uses `output_roles + locators`).

**Status:** complete.

### Phase 2 — Oracle Store v0 implementation (current)
**Intent:** make the Oracle boundary **verifiable** and “green” for local and dev.

#### Phase 2.1 — Profile wiring + config loader
**DoD checklist:**
- `oracle_root` wired into profiles (local/dev/prod).
- Loader resolves env placeholders without secrets.

#### Phase 2.2 — Oracle checker (local)
**DoD checklist:**
- CLI check validates `run_facts_view` schema + locators + required gates.
- Missing seal markers produce **WARN** (local only).
- No scanning beyond locator‑implied `part-*` expansion.

#### Phase 2.3 — Oracle checker (dev strict‑seal)
**DoD checklist:**
- `--strict-seal` enforced for dev/prod.
- Missing seal markers cause FAIL (no READY/stream).

#### Phase 2.4 — S3 path validation
**DoD checklist:**
- `s3://` locator existence and `part-*` expansion validated with list/head.
- Endpoint/region/path‑style honored via wiring (no secrets in files).

#### Phase 2.5 — Failure taxonomy + operator guidance
**DoD checklist:**
- Checker outputs stable reason codes (PACK_NOT_SEALED, LOCATOR_MISSING, GATE_PASS_MISSING, DIGEST_MISSING).
- Operator guidance documented for retry vs terminal failure.

**Status:** in progress.

### Phase 3 — Pack seal + manifest tooling
**Intent:** make sealing explicit without touching engine internals.

#### Phase 3.1 — Seal/manifest writer (write‑once)
**DoD checklist:**
- CLI writes `_oracle_pack_manifest.json` + `_SEALED.json` **only if absent**.
- Pack root id + key tokens + engine release recorded.
- No mutation after seal (fail if seal exists).

#### Phase 3.2 — Strict‑seal enablement
**DoD checklist:**
- Dev/prod checks require seal markers.
- Local remains optional until packer is used routinely.

### Phase 4 — Ops + governance hardening
**Intent:** immutability enforcement, auditability, and operational safety.

#### Phase 4.1 — Immutability enforcement
**DoD checklist:**
- S3 write‑once posture documented (bucket policy/object lock optional).
- Local guidance warns against manual edits after seal.

#### Phase 4.2 — Tombstone + retention posture
**DoD checklist:**
- Tombstone semantics pinned (missing pack => fail‑closed).
- Retention policy documented per env.

#### Phase 4.3 — Access control posture
**DoD checklist:**
- Least‑privilege reader roles documented (SR/WSP/IG/DLA/CM).
- Writer role limited to engine/packer only.

