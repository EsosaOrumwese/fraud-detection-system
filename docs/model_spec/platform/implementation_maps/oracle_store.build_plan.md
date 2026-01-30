# Oracle Store Build Plan (v0)
_As of 2026-01-28_

## Purpose
Define the **sealed world boundary** for engine outputs as an explicit platform component. Oracle Store is a contract: immutable by‑ref artifacts, locator/digest rules, and environment ladder wiring.

## Planning rules (binding)
- **Progressive elaboration:** expand only the active phase into sections + DoD.
- **No secrets:** never embed credentials or tokens in plans or logs.
- **No discovery-by-scanning:** Oracle Store tools require an explicit engine run root or pack root; no “latest world” lookup.

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
- Oracle Store is **external engine truth**; platform components do not “own” it.
- WSP reads Oracle Store directly using explicit world identity (no SR‑based discovery).
- Legacy IG pull does not scan Oracle Store; it only follows explicit locators.

#### Phase 1.5 — Validation checklist
**DoD checklist:**
- Explicit checklist for locator validation + digest verification.
- Documented “no PASS → no read” and “fail‑closed when unknown.”

#### Phase 1.6 — V0 transitional allowances
**DoD checklist:**
- Pack‑root aliasing documented (current `runs/local_full_run-*` treated as pack roots).
- Seal markers optional for **local** until packer exists; strict seal reserved for dev/prod.
- No SR‑based inputs for Oracle Store tooling (engine‑root only).

**Status:** complete.

### Phase 2 — Oracle Store v0 implementation (current)
**Intent:** make the Oracle boundary **verifiable** and “green” for local and dev.

#### Phase 2.1 — Profile wiring + config loader
**DoD checklist:**
- `oracle_root` wired into profiles (local/dev/prod).
- Loader resolves env placeholders without secrets.

#### Phase 2.2 — Oracle checker (local)
**DoD checklist:**
- CLI check validates engine run root + required gates (optionally specific outputs).
- Missing seal markers produce **WARN** (local only).
- No discovery-by-scanning; only explicit engine roots.

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
- Checker outputs stable reason codes (PACK_NOT_SEALED, GATE_RECEIPT_MISSING, OUTPUT_MISSING, SCENARIO_ID_*).
- Operator guidance documented for retry vs terminal failure.

**Status:** complete.

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

#### Phase 3.3 — Pack identity + manifest schema
**DoD checklist:**
- OracleWorldKey is pinned as `{manifest_fingerprint, parameter_hash, scenario_id, seed}` (run_id excluded).
- Pack manifest schema is versioned (minimal JSON schema under `docs/model_spec/platform/contracts/oracle_store/`).
- Manifest records `oracle_pack_id`, OracleWorldKey tokens, `engine_release`, and catalogue/gate-map identifiers.

#### Phase 3.4 — Local pack sealing helper (v0 migration)
**DoD checklist:**
- CLI can seal an existing local pack root **without** moving bytes (pack‑root alias).
- Inputs are derived from engine run receipt + scenario_id (no SR‑based inputs).
- Seal + manifest writes are idempotent (create‑if‑absent; fail‑closed on mismatch).

**Status:** in progress.

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

---

### Phase 5 — Global time‑sorted stream view (Option C)
**Intent:** produce **per‑output `ts_utc`‑sorted stream views** without modifying engine outputs.

#### Phase 5.1 — Stream view placement (separate from engine native outputs)
**DoD checklist:**
- Derived view stored under engine run root but in a **distinct folder** (no collision with native outputs).
- Final naming pinned: `stream_view/ts_utc/output_id=<output_id>/part-*.parquet` (under the engine run root).
- Stream view lives under Oracle Store (engine world), **not** under `runs/fraud-platform`.

#### Phase 5.2 — Per‑output sort builder (S3‑native)
**DoD checklist:**
- Sorter reads **directly from S3** (MinIO locally; AWS S3 in dev/prod).
- External sort uses **DuckDB** (disk‑backed, vectorized).
- Deterministic tie‑break documented: `ts_utc`, `filename`, `file_row_number`.
- Output schema preserved (no extra columns; sort does not mutate payload).
- Output is **flat** per output_id (no bucket partition in the path).

#### Phase 5.3 — Validation receipt (no dupes/no drops)
**DoD checklist:**
- Receipt contains `row_count`, `min_ts`, `max_ts` and **order‑invariant hash sums** for both source and sorted view.
- Receipt includes `source_locator_digest` (hash of all source part URIs) + sort keys + partitioning.
- Fail‑closed if receipt mismatch or missing.

#### Phase 5.4 — Idempotency & rerun posture
**DoD checklist:**
- If a valid receipt exists, the builder **exits cleanly** (no rewrite).
- If receipt exists but fails validation, **abort** (do not overwrite).

#### Phase 5.5 — WSP integration switch (stream view vs raw)
**DoD checklist:**
- `stream_view_root` pin in profiles; WSP is **always** stream-view in v0 (no `stream_mode` toggle).
- WSP reads stream view manifest/receipt and uses it as the single source of events.
- Local may allow fallback to raw engine outputs; dev/prod require stream view when enabled.

**Status:** implemented (smoke validation pending).
