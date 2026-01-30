# Oracle Store Implementation Map
_As of 2026-01-28_

---

## Entry: 2026-01-28 13:16:54 — Oracle Store component initiation (sealed world boundary)

### Trigger
User approved building **Oracle Store** as a **separate platform component** alongside WSP, with a configurable `oracle_root` (use `runs/local_full_run-5` now; migrate to `runs/data-engine` later) and no secrets in plans/logs.

### Authorities / inputs (binding)
- Root `AGENTS.md` (progressive elaboration, append‑only decision trail, no secrets).
- Platform blueprint + deployment tooling notes (engine outputs are sealed by‑ref world artifacts).
- Engine interface pack (locator schema, digest posture, receipts).
- WSP design authority (streams only from SR join surface; no scanning).

### Live decision trail (notes as I think)
- Oracle Store is **not** a service that transforms data; it is a **boundary contract** that defines how the sealed world is stored, referenced, and verified.
- This boundary must be **explicit** so multiple components (SR verifier, WSP, legacy pull/backfill) can use the same invariant without hidden drift.
- `oracle_root` must be **configurable** because:
  - local data already exists under `runs/local_full_run-5`
  - the long‑term target is `runs/data-engine/` (or S3 in dev/prod)
  - hard‑coding would force code edits for environment changes
- Oracle Store must enforce **immutability + by‑ref access**:
  - sealed runs are write‑once
  - consumers read by locator + digest only
  - no “latest” discovery; SR’s `run_facts_view` is the entrypoint
- Keep Oracle Store **vendor‑neutral** (filesystem vs S3); adapters are wiring, not policy.

### Alternatives considered (and why rejected)
- **Fold Oracle Store into WSP only**: rejected; boundary must be shared and explicit across the platform.
- **Treat `oracle_root` as a policy constant**: rejected; it is wiring/environmental, not a semantic policy.
- **Allow scanning for “latest run”**: rejected; violates SR join‑surface law and risks provenance drift.

### Planned steps (before coding)
1) Create Oracle Store design authority doc:
   - `docs/model_spec/platform/component-specific/oracle_store.design-authority.md`
2) Create Oracle Store build plan:
   - `docs/model_spec/platform/implementation_maps/oracle_store.build_plan.md`
3) Define v0 contract:
   - `oracle_root` config (default `runs/local_full_run-5`)
   - path conventions (run_id‑scoped, immutable)
   - locator/digest checks (by‑ref only)
4) Wire references in WSP plan to the Oracle Store contract (no code until plans are recorded).

---

## Entry: 2026-01-28 13:32:07 — Wire oracle_root into platform profiles (pre-change)

### Trigger
WSP Phase 1 implementation starts and requires `oracle_root` to be surfaced in platform profiles as a wiring value (no secrets).

### Live reasoning (notes)
- Oracle Store is a **boundary contract**, but it still needs a concrete **wiring hook** (`oracle_root`) to point at the current sealed world location.
- Defaulting `oracle_root` to `runs/local_full_run-5` aligns with the only fully materialized local run, while keeping it adjustable for the future `runs/data-engine` move.
- For dev/prod, the value should remain **wiring** (env or S3 URI) and must not embed credentials.

### Planned edit
- Update `config/platform/profiles/*.yaml` to include `wiring.oracle_root`.
- Update profiles README to document `oracle_root` semantics and the “no secrets” posture.

---

## Entry: 2026-01-28 13:38:37 — Applied: oracle_root wiring in profiles

### What changed
- Added `wiring.oracle_root` to all platform profiles.
- Updated `config/platform/profiles/README.md` to define Oracle Store wiring and its non‑secret posture.

### Notes
- Local/dev_local default to `runs/local_full_run-5` (temporary).
- Dev/prod use `${ORACLE_ROOT}` so the location can be swapped without code edits.

---

## Entry: 2026-01-28 14:37:34 — Applied: Oracle Store Phase‑1 checks (local by‑ref verification)

### What I changed
- Added an **Oracle Store checker** (`src/fraud_detection/oracle_store/`) with:
  - profile loader (wiring + policy; no secrets),
  - run_facts_view schema validation,
  - locator existence checks (local + S3),
  - required gate PASS validation (catalogue‑driven),
  - seal marker detection (soft in v0 unless `--strict-seal`).
- Added CLI entrypoint: `python -m fraud_detection.oracle_store.cli`.
- Added Make target `platform-oracle-check` with `ORACLE_RUN_FACTS_REF` input.
- Updated Oracle Store design authority with v0 transitional notes (pack‑root aliasing + no seal markers locally).

### Rationale (live)
- The checker provides a **green/red** readiness gate for the Oracle boundary before we harden WSP.
- It is **fail‑closed** on missing locators or required gate receipts, but **warn‑only** on missing seal markers in v0 local runs.
- Locators are validated without scanning for “latest”; only locator‑implied listing is allowed for `part-*`.

### Guardrails
- No secrets are stored or logged; all endpoints are wiring only.
- S3 checks are optional by virtue of the profile wiring; local is the default for v0.

---

## Entry: 2026-01-28 14:45:50 — Expand Oracle Store build plan for implementation + hardening

### Trigger
User asked to update the Oracle Store build plan so we can start **implementation + hardening** (local then dev).

### Live reasoning (notes)
- Phase 1 (contract) is effectively complete; we now need **implementation steps** that make the Oracle boundary verifiable and “green.”
- Local must tolerate missing seal markers (v0 transitional rule), but **dev must be strict**.
- Sealing tooling should be **external to the engine** (black‑box rule) and must be **write‑once** to avoid mutation.
- S3 compatibility needs explicit validation (path expansion, head/list) before we declare dev‑readiness.

### Planned plan changes
- Mark Phase 1 complete and expand Phase 2 into concrete implementation steps (checker CLI, strict‑seal, S3 validation, failure taxonomy).
- Add a dedicated phase for **seal/manifest tooling** (packer CLI) with write‑once semantics.
- Add an ops/governance hardening phase (immutability enforcement, tombstone policy, least‑privilege reads).

---

## Entry: 2026-01-28 14:58:40 — Phase 2 hardening (reason codes + strict‑seal + S3 tests)

### Trigger
User requested Phase 2 hardening of Oracle Store (stable reason codes, strict‑seal for dev, and S3 validation tests).

### Live reasoning (notes)
- The checker already validates locators and gates, but **reason codes must be stable** so operators can classify failures deterministically.
- Dev/prod must **fail on unsealed packs**; local remains WARN‑only until a packer exists.
- We need **unit‑level S3 path validation tests** (no real S3) to ensure glob expansion and head/list logic are correct.

### Planned edits
1) Add stable reason codes to `OracleCheckReport` (codes + issue details).
2) Enforce strict‑seal default for `profile_id in {dev, prod}` in the CLI (override allowed).
3) Add S3 path validation tests using stubbed clients; add tests for oracle path resolution.

---

## Entry: 2026-01-28 14:51:51 — Applied: Phase 2 hardening (reason codes + strict‑seal + tests)

### What changed
- **Stable reason codes:** `OracleCheckReport` now emits `reason_codes` + structured `issues` with `code/detail/severity` (PACK_NOT_SEALED, LOCATOR_MISSING, DIGEST_MISSING, GATE_PASS_MISSING, RUN_FACTS_INVALID/UNREADABLE).
- **Strict‑seal default for dev/prod:** CLI now enforces strict seal markers for `profile_id in {dev, prod}` unless explicitly overridden.
- **S3 path validation tests:** added unit tests for S3 head + glob listing and oracle path resolution.

### Notes
- Local runs still WARN on missing seal markers (v0 transitional rule).
- Missing digest is treated as error when `require_digest` is true; use `--allow-missing-digest` to relax.

---

## Entry: 2026-01-28 15:02:20 — Phase 3 planning (seal + manifest tooling)

### Trigger
User asked to proceed to Phase 3 planning once Phase 2 hardening is done.

### Live reasoning (notes)
- Dev strict‑seal already fails without seal markers; Phase 3 must **introduce seal/manifest tooling** to make dev green.
- We cannot touch engine internals, so sealing must be done by a **separate packer/CLI** that writes only **new metadata objects** at the pack root.
- We must support the **v0 pack‑root alias** (existing `runs/local_full_run-*` roots) without moving data.
- The manifest must capture interpretation identity (engine release + catalogue/gate-map identifiers) to keep future reads reproducible.

### Decisions to lock
- OracleWorldKey is pinned as `{manifest_fingerprint, parameter_hash, scenario_id, seed}` (run_id excluded).
- Seal artifacts are **write‑once** and **idempotent** (create‑if‑absent; fail on mismatch).
- Pack manifest schema will live under `docs/model_spec/platform/contracts/oracle_store/` (versioned).

### Planned work (Phase 3)
1) Define manifest + seal schema (minimal fields, versioned).
2) Implement packer CLI:
   - Accept `run_facts_view` ref or explicit tokens.
   - Derive pack root from locators (or use explicit `--pack-root`).
   - Write `_oracle_pack_manifest.json` + `_SEALED.json` only if absent.
3) Update oracle checker to read and report manifest metadata when present.

---

## Entry: 2026-01-28 15:18:40 — Phase 3 implementation (packer + manifest + strict seal)

### Live reasoning (decisions made)
- **Manifest contents:** keep minimal but sufficient: `oracle_pack_id`, OracleWorldKey tokens, `engine_release`, `catalogue_digest`, `gate_map_digest`, `created_at_utc`. This anchors interpretation without dragging large payloads.
- **OracleWorldKey tokens:** `{manifest_fingerprint, parameter_hash, scenario_id, seed}` only; `run_id` excluded per design.
- **Pack id derivation:** sha256 over world key + engine_release + catalogue/gate_map digests to avoid collisions across engine versions.
- **Write‑once semantics:** manifest + seal are written with create‑if‑absent; if the file exists and content differs → fail (no overwrite).
- **Pack‑root alias support:** packer derives pack root from run_facts locators when not explicitly provided; if multiple roots → fail (ambiguity).
- **Local safety:** packer refuses to seal if the local pack root directory does not exist (avoid sealing a phantom root).
- **Strict‑seal posture:** dev/prod enforce seal markers by default; local allows unsealed until packer is in routine use.

### What I implemented
- Added Oracle packer (`src/fraud_detection/oracle_store/packer.py`) with:
  - OracleWorldKey + manifest models
  - pack root derivation from locators
  - write‑once manifest + seal creation (`_oracle_pack_manifest.json`, `_SEALED.json`)
- Added seal CLI (`src/fraud_detection/oracle_store/seal_cli.py`) that seals from `run_facts_view`.
- Updated checker to report manifest metadata when present and emit `PACK_MANIFEST_MISSING` warnings.
- Added Make target `platform-oracle-seal` with `ORACLE_ENGINE_RELEASE` + optional `ORACLE_PACK_ROOT`.
- Added unit tests for packer write‑once + mismatch detection.

---

## Entry: 2026-01-28 15:32:10 — Packer idempotency fix + sample seal validation

### What changed
- Adjusted packer idempotency: manifest/seal comparisons now ignore timestamp fields and compare only identity‑critical fields.
- Added local pack root existence check to avoid sealing non‑existent roots.

### Validation (local/dev)
- Sealed pack for `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92` using `run_facts_view` (engine release `engine-local-v0`).
- Strict‑seal check (dev_local) now passes with status **OK**.

---

## Entry: 2026-01-28 15:10:45 — Manifest schema + validation

### What changed
- Added Oracle Store contract schemas:
  - `docs/model_spec/platform/contracts/oracle_store/oracle_pack_manifest.schema.yaml`
  - `docs/model_spec/platform/contracts/oracle_store/oracle_pack_seal.schema.yaml`
- Checker now validates manifests when present and reports `PACK_MANIFEST_INVALID` on schema failure.

### Rationale
- Schemas make pack metadata auditable and enforceable without embedding logic in the engine.
- Validation keeps the seal/manifest tooling honest as we expand to dev/prod.

---

## Entry: 2026-01-28 15:14:20 — Add strict Make target + operator guide

### What changed
- Added Make target `platform-oracle-check-strict` to enforce seal markers explicitly.
- Documented a short “oracle store in action” guide for operators (seal → strict check).

---

## Entry: 2026-01-28 15:46:33 — **IMPORTANT** Oracle Store is external to the platform runtime

### Decision (explicit separation)
The Oracle Store is **not** a platform vertex or runtime component. It is the **external, immutable store of engine worlds** (oracle sets) that the platform reads from. Platform runtime artifacts (logs, SR/IG ledgers, session metadata) live under `runs/fraud-platform` and must **never** be treated as the oracle store.

### Why this matters
- The platform must operate even if `runs/fraud-platform` is wiped; that folder is only **platform output**, not engine truth.
- The Oracle Store is the **source of truth** for WSP streaming and does **not** depend on SR artifacts or platform runtime state.
- Keeping this boundary hard preserves the “engine outside the platform” model and avoids accidental coupling.

### Operational implication (v0)
- Local/dev can point `oracle_root` at `runs/local_full_run-5` **only as a path to the engine world** — it is still treated as external truth, not a platform folder.
- Future environments should point `oracle_root` to `runs/data-engine` or an object store bucket (S3/MinIO).

---

## Entry: 2026-01-28 16:07:27 — **Decisive change**: remove SR‑based sealing, make Oracle Store engine‑rooted only

### Trigger (user direction)
User explicitly rejected SR‑based sealing as a “temporary helper” and required us to **scrap it entirely** to avoid future agents mistaking SR as an oracle authority. Oracle Store must be treated strictly as a **database for engine outputs**, populated by the engine (or a loader) outside the platform.

### Live reasoning (decision trail, no retro‑summary)
- The SR `run_facts_view` is **platform runtime output**, not engine truth. Using it as the sealing input makes Oracle Store **dependent on platform runtime** and violates the new boundary rule we just locked in.
- The Oracle Store’s correct dependency chain is: **Engine outputs → Oracle Store → WSP**, with **no SR dependency**. If we leave any SR‑based path in code/Make targets, future work will drift back to that coupling.
- Because the Oracle Store is a **store**, not a producer, it should **never** assume responsibility for population. It can validate (check) and seal metadata, but the bytes must come from the engine world itself.
- Therefore, the “seal from run_facts_view” pathway must be removed, not just deprioritized. Keeping it as a CLI switch would preserve a confusing escape hatch.

### Plan (what I’m changing next, before code)
1) **Remove SR‑based inputs** from Oracle Store:
   - delete `seal_cli.py` and any CLI args that take `run_facts_ref`.
   - remove `platform-oracle-seal`, `platform-oracle-check`, `platform-oracle-check-strict` Make targets (SR‑dependent).
2) **Replace with engine‑rooted tooling**:
   - new packer entry point to seal **from engine run root** using `run_receipt.json` + `scenario_id`.
   - checker entry point to validate **engine run root** and gate receipts; optional output checks by `output_id` list.
3) **Update tests** to use engine‑rooted inputs (temp engine‑run folder + run_receipt).
4) **Update docs** (impl_actual + operator notes) so only engine‑rooted usage remains visible.

### Expected invariants after change
- Oracle Store **never** reads from `runs/fraud-platform`.
- Removing `runs/fraud-platform` should **not** affect oracle checks or sealing.
- The only required input for Oracle Store tooling is the **engine run root** (plus scenario_id when needed).

---

## Entry: 2026-01-28 16:17:31 — Applied: engine‑rooted Oracle Store tooling (SR‑based paths removed)

### What I actually changed (step‑by‑step, while implementing)
1) **Introduced an engine‑run reader module** so both checker and packer use the same boundary logic:
   - New `oracle_store/engine_reader.py` resolves engine run roots, reads `run_receipt.json`, and discovers `scenario_id` on local runs.
   - I chose a separate module to prevent circular imports between checker/packer and to make “engine‑rooted” logic explicit.

2) **Rebuilt the checker around engine roots** (no run_facts_view):
   - `oracle_store/checker.py` now accepts `engine_run_root` + optional `scenario_id` and validates:
     - `run_receipt.json` is present + readable.
     - `scenario_id` is explicit or uniquely discoverable (error on ambiguity).
     - gate receipts exist at `passed_flag_path_template` locations.
     - pack markers (`_SEALED.*`, `_oracle_pack_manifest.json`) are present (strict‑seal enforces).
     - optional `output_ids` list can be checked without scanning the whole world.
   - I removed the run_facts_view schema dependency so the checker cannot drift back into SR‑based validation.

3) **Rebuilt the packer to seal from engine runs**:
   - `oracle_store/packer.py` now seals **from engine run root**, using `run_receipt.json` + `scenario_id` as the OracleWorldKey.
   - Pack manifest/seal writes remain idempotent and use the same digest logic; I kept the write‑once guarantees intact.

4) **Scrapped SR‑based CLI and Makefile targets**:
   - Removed `seal_cli.py` entirely.
   - Added `pack_cli.py` with `--engine-run-root` + `--scenario-id`.
   - Make targets now expose `platform-oracle-pack`, `platform-oracle-check`, `platform-oracle-check-strict` with engine‑rooted inputs only.

5) **Updated operator guidance + build plan**:
   - Oracle Store operator guide now shows engine‑rooted usage only.
   - Build plan sections that assumed SR join‑surface inputs were rewritten to reflect the engine‑rooted boundary.

6) **Updated tests**:
   - Oracle packer tests now write a local `run_receipt.json` and seal from engine run roots.

### Why these changes satisfy the user’s constraint
- There is **no code path** left that can accept SR `run_facts_view`.
- Oracle Store tooling is now **only** a consumer of engine‑materialized truth.
- Wiping `runs/fraud-platform` does **not** affect Oracle Store operations.

### Validation
- `pytest tests/services/oracle_store/test_checker.py tests/services/oracle_store/test_packer.py -q` → 6 passed.

---

## Entry: 2026-01-30 00:38:20 — Correction: dev_local profile removed (oracle checks use local_parity)

### Why this correction
Previous Oracle Store notes referenced `dev_local.yaml` for strict-seal checks. That profile has been removed to remove ladder friction.

### Current authoritative posture
- **Parity gate:** `config/platform/profiles/local_parity.yaml`.
- **Smoke only:** `config/platform/profiles/local.yaml`.

### Impact
Treat earlier `dev_local` mentions as historical; use `local_parity` for parity validation.

---

## Entry: 2026-01-30 01:27:40 — Oracle pack env propagation for MinIO

### Trigger
`platform-oracle-pack` failed with `Invalid endpoint` because `OBJECT_STORE_ENDPOINT` + MinIO credentials were not exported to the packer process; boto fell back to shared AWS credentials.

### Decision trail (live)
- Oracle pack uses S3ObjectStore for MinIO; it must receive endpoint + creds via environment.
- Makefile already loads `.env.platform.local` as make variables, but those are not exported to subprocesses by default.
- Fix is to **explicitly pass** `OBJECT_STORE_*` and `AWS_*` into oracle pack/check commands.

### Implementation notes
- Prefixed `platform-oracle-pack`, `platform-oracle-check`, and `platform-oracle-check-strict` with `OBJECT_STORE_ENDPOINT/REGION` + `AWS_ACCESS_KEY_ID/SECRET` and `AWS_DEFAULT_REGION`.
- Updated runbook note to clarify endpoint export requirement.

### Files touched
- `makefile`
- `docs/runbooks/platform_parity_walkthrough_v0.md`

---

## Entry: 2026-01-30 02:23:28 — Oracle sync target + runbook simplification

### Trigger
User hit `MANIFEST_MISMATCH` and credential confusion when syncing engine outputs into MinIO and sealing Oracle packs.

### Decision trail (live)
- The Oracle Store is MinIO‑backed in parity; the sync step should be **repeatable** without manual AWS CLI env injection.
- Use a Make target that sources MinIO creds from `.env.platform.local` and syncs the local engine run into MinIO.
- Keep the runbook path simple: **sync → pack**, with one short troubleshooting note.

### Implementation notes
- Added `platform-oracle-sync` target to run `aws s3 sync` against MinIO.
- Added `ORACLE_SYNC_SOURCE` to `.env.platform.local` to anchor the local engine path.
- Updated the parity runbook section 4 to use the Make target and to clarify that MinIO is local (data is copied).

### Files touched
- `makefile`
- `.env.platform.local`
- `docs/runbooks/platform_parity_walkthrough_v0.md`

---

## Entry: 2026-01-30 03:25:40 — Ordering reality + global time‑sorted stream view (Option C)

### Trigger
User observed that `arrival_events_5B` is not globally time‑sorted; requested a **global `ts_utc` stream view** (Option C) with receipts and idempotency.

### Observed ordering (local run inspection)
For `runs/local_full_run-5/c25a2675...`:
- `arrival_events_5B` parts appear **lexicographically ordered by** `(scenario_id, merchant_id, arrival_seq)`, *not* `ts_utc`.
- `s2_flow_anchor_baseline_6B` and `s3_flow_anchor_with_fraud_6B` show the same ordering pattern.
- Boundaries between `part-*.parquet` also follow the same key order.

This matches the engine’s deterministic writer order but **does not** guarantee global time monotonicity.

### Decision trail (live, pending approval)
- Provide an **external, derived stream view** sorted globally by `ts_utc` without modifying engine outputs.
- Store the derived view **under the engine run root** but in a clearly separate folder to avoid conflation.
- Add a **validation receipt** proving row‑set equality (no dupes/no drops) between original and sorted views.
- Ensure **idempotency**: if a valid receipt exists, do nothing; if mismatch, fail closed.
- Operate **directly on S3** (MinIO locally, AWS S3 in dev/prod) since engine outputs already live there.

### Proposed placement (not yet implemented)
```
s3://oracle-store/data-engine/<engine_run_id>/data/.../arrival_events_ts_sorted/part-*.parquet
```
Folder name TBD (e.g., `arrival_events_ts_sorted` or `stream_view_ts_utc`) to avoid confusing with engine‑native outputs.

### Receipt requirements (draft)
- `row_count` + `content_hash` (order‑invariant) for both original and sorted views.
- `source_locator_hash` over original `part-*.parquet` paths for traceability.
- `sorted_view_manifest` with sort keys and partitions (for deterministic rebuilds).

### Open decisions (to confirm)
- Sorting engine: DuckDB external sort vs. PyArrow dataset sort.
- Stream view partitioning: by `stream_date` or `stream_hour`.
- Payload storage: full payload rows vs. pointer/offsets to original files.

---

## Entry: 2026-01-30 10:24:24 — Option C locked: stream view sort helper (engine‑rooted, S3‑native)

### Trigger
User rejected policy‑based ordering assumptions and requested a **most‑efficient, reliable** Option C with explicit receipts + idempotency, operating directly against S3/MinIO.

### Decision trail (live, explicit)
- We must **not** change engine outputs or engine code. The stream view must be **derived** and stored **alongside** the engine run root, clearly separated from engine‑native folders.
- We must be **S3‑native** because engine outputs will live in object storage for dev/prod. Local parity should mimic that (MinIO).
- The sorter must be **idempotent**: if a valid receipt exists, do nothing; if the receipt conflicts, fail closed and force operator action.
- We need a **receipt** that proves the sorted view is the same row‑set as the source inputs (no missing/dup rows), with traceability back to the exact source parts.
- We need a **generic helper**, not a one‑off: accept any dataset list and build a unified time‑sorted stream view for WSP to consume.

### Locked design choices
- **Sorting engine:** DuckDB external sort (fast, vectorized, handles large Parquet datasets; supports S3/MinIO URIs).
- **Placement:** under the engine run root, but in a **distinct folder** so it never looks like engine‑native output.
  - Proposed path (final):  
    `s3://oracle-store/<engine_run_root>/stream_view/ts_utc/<stream_view_id>/...`
- **Partitioning:** by `stream_date` (`YYYY‑MM‑DD`) to keep file sizes manageable and keep replay windows efficient.
- **Row payload:** store a canonical JSON payload per event (`payload_json`) + `ts_utc` + `event_type` (output_id), so WSP can rehydrate without rereading original files.
- **Receipt strategy:** record **row_count**, `min_ts`, `max_ts`, and **two independent hash sums** over `payload_json` (order‑invariant) to detect mismatches. Also record a `source_locator_digest` over all source `part-*.parquet` URIs for traceability.
  - This is probabilistic but high‑confidence; collisions are extremely unlikely for the v0 use case and can be revisited if we need a cryptographic multiset proof later.

### Invariants to enforce
- **No overwrite:** if a receipt exists for the target stream view, only proceed if it matches the current source locator digest + row_count.
- **Fail‑closed:** if source outputs are missing, schema mismatch, or receipt mismatch → abort.
- **No secrets in logs/receipts:** only store URIs + digests, never credentials.

### Planned mechanics (before code)
1) Implement `oracle_store/stream_sorter.py`:
   - Build a union view over configured output_ids (from config).
   - For each output_id, map to `event_type`, `ts_utc`, and `payload_json`.
   - External sort by `ts_utc` (tie‑break by `event_type`, `hash(payload_json)`).
   - Write Parquet partitioned by `stream_date`.
2) Compute `source_stats` via DuckDB (row_count, min/max ts, hash sums).
3) Write:
   - `_stream_sort_receipt.json`
   - `_stream_view_manifest.json` (sort keys, partitioning, source list, stream_view_id).
4) Add a CLI + Make target (`platform-oracle-stream-sort`) for operators.
5) Update WSP to consume stream view when `stream_mode=stream_view` is set.

### Validation/tests
- Unit‑test receipt match/mismatch behavior (idempotency).
- Integration smoke: build stream view for local parity data (MinIO), then run WSP in stream_view mode and confirm steady progress.

---

## Entry: 2026-01-30 10:38:00 — Applied: stream view builder + CLI + Make target

### What I implemented
1) **Stream view builder** (`src/fraud_detection/oracle_store/stream_sorter.py`)
   - DuckDB external sort over multiple output_ids.
   - Emits Parquet partitioned by `stream_date`.
   - Writes `_stream_view_manifest.json` + `_stream_sort_receipt.json`.
   - Idempotent: receipt must match `source_locator_digest` + output list or it fails closed.

2) **CLI entrypoint** (`src/fraud_detection/oracle_store/stream_sort_cli.py`)
   - Required inputs: `--engine-run-root`, `--scenario-id`, optional `--stream-view-root`.
   - Uses `config/platform/wsp/traffic_outputs_v0.yaml` by default for output_ids.

3) **Makefile target**
   - Added `platform-oracle-stream-sort` with MinIO creds + endpoint exported.

4) **Profile + env wiring**
   - Added `oracle_stream_view_root` to profiles.
   - Added `ORACLE_STREAM_VIEW_ROOT` to `.env.platform.local`.

### Notes
- Stream view output lives **under the engine run root** (Oracle Store), not in `runs/fraud-platform`.
- Parity/dev/prod default to `stream_mode=stream_view`; local smoke stays on `engine` mode.

---

## Entry: 2026-01-30 10:58:04 — Stream view progress logs + DuckDB progress bar

### Trigger
User requested **live visibility** during the stream view build (milestone logs + progress bar).

### What I changed
- Added milestone logs: start → source stats → sort/write → sorted stats → receipt/manifest → done.
- Enabled DuckDB progress bar (`PRAGMA enable_progress_bar`).
- Added optional `STREAM_SORT_PROGRESS_SECONDS` env knob to control progress bar refresh.

---

## Entry: 2026-01-30 10:59:12 — ETA‑style logging for stream sort

### Trigger
User requested **ETA‑style** visibility during stream view build.

### What I changed
- Added ETA estimates after source stats scan using `STREAM_SORT_SORT_MULTIPLIER` (default 2.0).
- Logs estimated completion time (UTC) and compares actual sort time to ETA.

---

## Entry: 2026-01-30 11:06:12 — Fix DuckDB hash sum overflow in receipts

### Trigger
Stream view build failed with `OutOfRangeException` during `hash_sum2` computation (UINT64 multiplication overflow).

### Decision trail (live)
- We still need **order‑invariant** integrity checks without overflow.
- Keep two independent aggregates but compute them in **bounded ranges** to avoid UINT64 overflow.

### What I changed
- Switched `hash_sum` to **DOUBLE** sum of hash values.
- Switched `hash_sum2` to a **modular sum** (`hash % 1_000_000_007`) to preserve variance without overflow.

### Implications
- Receipt remains high‑confidence for “same row‑set” validation.
- If we later need cryptographic multiset proofs, we can replace sums with a proper multiset digest.

---

## Entry: 2026-01-30 11:24:05 — Stream sort performance knobs (memory/temp/threads)

### Trigger
User observed long stream view build time (multi‑hour ETA) on ~374M rows.

### What I changed
- Added optional DuckDB tuning knobs:
  - `STREAM_SORT_MEMORY_LIMIT` → `PRAGMA memory_limit`
  - `STREAM_SORT_TEMP_DIR` → `PRAGMA temp_directory`
  - `STREAM_SORT_THREADS` already supported (kept)

### Operator guidance
- Set `STREAM_SORT_THREADS` to available cores (e.g., 8–16).
- Use a fast local SSD for `STREAM_SORT_TEMP_DIR`.
- Increase `STREAM_SORT_MEMORY_LIMIT` to reduce spill to disk.
