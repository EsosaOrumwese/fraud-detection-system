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

## Entry: 2026-02-11 11:00AM - Pre-change lock: set dev_min Oracle pins in operator env

### Trigger
USER requested that missing Oracle env pins be set directly and asked for recommended values.

### Decision
Set deterministic `dev_min` Oracle env values in `.env.dev_min` using:
1. managed object-store bucket naming aligned to current `dev_min` prefix convention,
2. a known local engine run source path for sync/backfill,
3. explicit run root + stream-view root + scenario pin for O1 execution.

### Planned values
1. `DEV_MIN_OBJECT_STORE_BUCKET=fraud-platform-dev-min-object-store`
2. `DEV_MIN_ORACLE_ROOT=s3://fraud-platform-dev-min-object-store/dev_min/oracle`
3. `DEV_MIN_ORACLE_ENGINE_RUN_ROOT=s3://fraud-platform-dev-min-object-store/dev_min/oracle/c25a2675fbfbacd952b13bb594880e92`
4. `DEV_MIN_ORACLE_SCENARIO_ID=baseline_v1`
5. `DEV_MIN_ORACLE_STREAM_VIEW_ROOT=s3://fraud-platform-dev-min-object-store/dev_min/oracle/c25a2675fbfbacd952b13bb594880e92/stream_view/ts_utc`
6. `DEV_MIN_ORACLE_SYNC_SOURCE=runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`

### Validation check before edit
Confirmed local sync source path exists.

### Cost posture
Local config edit only; no paid resource actions in this step.

## Entry: 2026-02-11 11:08AM - Execution lock: retry Oracle O1 run now that network is restored

### Trigger
USER requested retry after network recovery.

### Execution sequence (O1)
1. Verify AWS connectivity and principal (`sts get-caller-identity`).
2. Verify destination Oracle bucket reachability.
3. Execute landing sync (`source_root` -> `oracle_engine_run_root`).
4. Execute stream-sort closure for required output refs.
5. Run strict Oracle check against pinned root/scope.

### Cost posture declaration (pre-action)
This run touches paid AWS S3 surfaces:
1. list/head/copy/put during sync and sort.
2. object storage growth at destination Oracle root.

Post-run decision will be explicitly logged as `KEEP ON` or `TURN OFF NOW`.

## Entry: 2026-02-11 11:21AM - Oracle sync run interrupted and process terminated on user stop

### What happened
1. AWS identity and destination bucket reachability checks passed.
2. Landing sync (`aws s3 sync`) was started against the pinned source->destination roots.
3. USER interrupted the run due long execution window.
4. Follow-up process check showed `aws` process `PID 9848` still active.
5. Process was force-stopped immediately.

### Outcome
- No `aws` sync process remains active after termination.
- O1 execution is intentionally paused until USER approves restart.

### Cost decision
`TURN OFF NOW` for this sync attempt (process terminated; no background transfer left running).

## Entry: 2026-02-11 11:24AM - Execution lock: user-directed bucket cleanup before manual sync/sort

### Trigger
USER instructed:
1. clean out the bucket,
2. USER will run sync and stream-sort manually afterward,
3. AGENT should provide the exact ordered steps to sync up.

### Decision
Perform full cleanup of the configured dev Oracle object bucket (`DEV_MIN_OBJECT_STORE_BUCKET`) so the next sync is deterministic and free from stale artifacts.

### Planned execution
1. Load `.env.dev_min` into session.
2. Verify AWS identity + target bucket.
3. Remove all current objects from bucket.
4. Verify bucket is empty.

### Cost posture declaration (pre-action)
Paid surface touched: AWS S3 API operations (delete/list/head).

## Entry: 2026-02-11 11:25AM - Correction lock: bucket is versioned; full purge required for true clean state

### Finding
Post-clean verification revealed bucket versioning is enabled, so object versions and delete markers remained after recursive remove.

### Decision
Execute version-aware purge of all versions + delete markers until zero remain, so user starts sync/sort from a truly empty bucket.

### Cost posture declaration (pre-action)
Paid surfaces: additional S3 list-object-versions + delete-objects calls.

## Entry: 2026-02-11 11:34AM - Versioned bucket cleanup confirmed complete

### Runtime outcome
1. Cleanup took longer because bucket versioning required removal of object versions + delete markers, not just current objects.
2. Final checks confirm:
   - current objects: `0`,
   - object versions: `0`,
   - delete markers: `0`.
3. No `aws` process remains active.

### Cost posture
`TURN OFF NOW` for cleanup loop (no background cleanup process running).

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

## Entry: 2026-02-11 12:08PM - Pre-change lock: implement Phase 3.C.1 operator framework (sync progress + stream-sort + strict validation)

### Trigger
USER requested implementation of a runnable framework so they can:
1. run Oracle landing sync to a proper managed bucket with live terminal progress visibility,
2. run stream-sort closure after sync,
3. execute strict authority validation in a fail-closed sequence.

### Problem framing
Current repo posture has:
1. existing generic Oracle commands (`platform-oracle-sync`, `platform-oracle-stream-sort`, `platform-oracle-check-strict`),
2. no dedicated `dev_substrate` Phase `3.C.1` orchestration script that binds O1 pin checks, progress reporting, policy-ref output selection, and strict closure evidence in one lane.

Resulting risk:
- execution is possible but operator flow remains fragmented and easier to run out of order.

### Options considered
1. Keep only existing generic targets and provide command snippets.
- Rejected: does not harden O1 sequencing or produce coherent phase-scoped evidence.
2. Implement only a shell wrapper around existing targets.
- Rejected: weak validation/reporting and brittle progress semantics.
3. Implement a dedicated Python runner + explicit Make targets for `preflight -> sync -> stream-sort -> validate`.
- Selected: strongest fail-closed posture while preserving existing Oracle service codepaths.

### Decisions locked before code
1. Create `scripts/dev_substrate/phase3c1_oracle_authority_lock.py` with explicit subcommands:
- `preflight`, `sync`, `stream-sort`, `validate`, `run`.
2. `sync` must show terminal-visible progress while uploading:
- stream `aws s3 sync` output live,
- emit periodic destination-prefix progress snapshots (`files/bytes`) against scanned source totals.
3. `stream-sort` output selection must be profile-policy driven:
- always include `traffic_output_ids_ref`,
- include context outputs by explicit mode (`fraud` default, with baseline/both override).
4. `validate` must include:
- strict Oracle checker gate (`strict_seal`),
- stream-view artifact presence checks per required output (`_stream_view_manifest.json`, `_stream_sort_receipt.json`, `part-*.parquet`),
- fail-closed final decision.
5. Add `Makefile` targets under the existing phase-3 dev_min family for each step and sequential run.

### Planned file touchpoints
1. `scripts/dev_substrate/phase3c1_oracle_authority_lock.py` (new).
2. `Makefile` (new phase `3.C.1` targets and tunables).
3. `docs/logbook/02-2026/2026-02-11.md` (decision/action logging).
4. This implementation map file (pre + post entries).

### Invariants to preserve
1. Engine remains Oracle truth owner; platform remains consumer.
2. No local fallback accepted in `dev_min` path.
3. No secret material written to logs/evidence docs.
4. O1 integrated acceptance remains blocked until validation PASS.

### Validation plan
1. Syntax/compile checks for new script.
2. Dry execution checks of CLI surfaces (`--help` and preflight).
3. Confirm Make targets resolve and invoke the correct subcommands.

## Entry: 2026-02-11 12:13PM - Applied Oracle 3.C.1 operator framework (sync + stream-sort + strict validate)

### What was implemented
1. Added a new phase-scoped runner:
- `scripts/dev_substrate/phase3c1_oracle_authority_lock.py`
- Subcommands:
  - `preflight` (pin and policy-ref checks),
  - `sync` (AWS sync with live terminal output + periodic destination progress snapshots),
  - `stream-sort` (policy-ref-driven traffic/context output sorting),
  - `validate` (strict Oracle checker + stream-view artifact presence checks),
  - `run` (sequential `preflight -> sync -> stream-sort -> validate`).
2. Added Makefile execution surfaces:
- `platform-dev-min-phase3c1-preflight`
- `platform-dev-min-phase3c1-sync`
- `platform-dev-min-phase3c1-stream-sort`
- `platform-dev-min-phase3c1-validate`
- `platform-dev-min-phase3c1-run`
3. Added phase tunables in Make defaults:
- `DEV_MIN_PHASE3C1_OUTPUT_ROOT`
- `DEV_MIN_PHASE3C1_CONTEXT_MODE`
- `DEV_MIN_PHASE3C1_PROGRESS_SECONDS`
- `DEV_MIN_PHASE3C1_SYNC_EXTRA_ARGS`
- `DEV_MIN_PHASE3C1_SKIP_AWS_HEAD`

### Decision notes during implementation
1. Kept Oracle migration as operator-led, fail-closed sequence rather than implicit side effects in existing generic targets.
2. Reused existing Oracle service code paths (`oracle_store.cli`, `oracle_store.stream_sort_cli`) rather than introducing new business logic branches.
3. Required output-id selection remains pinned to profile refs (`traffic_output_ids_ref` + context mode), not ad-hoc manual lists.
4. Validation includes both strict seal checker and stream-view artifact presence assertions to enforce O1.C/O1.D closure signals.

### Validation executed
1. `python -m py_compile scripts/dev_substrate/phase3c1_oracle_authority_lock.py` (`PASS`).
2. `python scripts/dev_substrate/phase3c1_oracle_authority_lock.py --help` (`PASS`).
3. Dry preflight execution with explicit pins and `--skip-aws-head`:
- `python scripts/dev_substrate/phase3c1_oracle_authority_lock.py preflight ... --skip-aws-head` (`PASS`, evidence emitted).
4. Make target resolution checks:
- `make -n platform-dev-min-phase3c1-{preflight,sync,stream-sort,validate,run}` (`PASS` render).
5. Make preflight execution check:
- `make platform-dev-min-phase3c1-preflight DEV_MIN_PHASE3C1_SKIP_AWS_HEAD=1` (`PASS`, evidence emitted).

### Result
Phase `3.C.1` now has a concrete operator framework for managed landing sync with terminal progress, policy-ref stream-sort, and strict validation sequencing. Execution closure remains pending actual user-run sync/sort/validate against live managed S3 roots.

### Cost posture
Implementation + dry checks only; no paid sync/sort execution performed in this pass.

## Entry: 2026-02-11 01:53PM - Pre-change lock: fix DuckDB S3 credential bridge for Phase 3.C.1 stream-sort on managed Oracle roots

### Trigger
USER reported `phase3c1_oracle_stream_sort` failure immediately after successful managed sync:
1. sync checks passed (`aws_sync_exit_code=0`, source/destination file+byte floors equal),
2. stream-sort failed in DuckDB with `HTTP 403 Forbidden` and auth hint (`No credentials are provided`).

### Runtime evidence reviewed
1. Failure surfaced at `read_parquet('s3://...')` from `stream_sorter._duckdb_columns`.
2. Process logs show `botocore.credentials` found credentials in shared credentials file (`~/.aws/credentials`).
3. Existing `_duckdb_connect` only injects S3 creds when env vars `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are present.
4. Therefore credential resolution diverges:
- boto3 path (used elsewhere) succeeds via shared profile chain,
- DuckDB path fails because shared-profile creds are not bridged into DuckDB settings.

### Problem statement
Oracle stream-sort in dev_min must be S3-native and fail-closed, but it currently cannot consume the same credential source that AWS CLI/boto3 is using unless static env credentials are exported. This creates false failures during Phase 3.C.1 despite successful managed sync.

### Options considered
1. Require users to export static `AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY` before stream-sort.
- Rejected: fragile operator UX; contradicts current workflow where AWS CLI and boto3 already resolve credentials from shared profile.
2. Switch stream-sort reads from DuckDB S3 to local temporary pull first.
- Rejected: violates managed-only migration posture and adds heavy copy overhead.
3. Resolve credentials through boto3 session and bridge frozen credentials + region into DuckDB `httpfs` settings.
- Selected: aligns DuckDB auth with existing AWS credential chain while preserving S3-native execution and fail-closed behavior.

### Decisions locked before code
1. Introduce explicit AWS runtime credential resolver in `stream_sorter.py` with precedence:
- env static keys first,
- then boto3 session/shared-profile chain,
- capture region fallback from AWS env/session when profile wiring region is absent.
2. Keep secrets out logs/evidence:
- log only credential source (`env` vs `boto3_session` vs `none`), never values.
3. Inject resolved credentials into DuckDB settings exactly once per connection.
4. Add unit tests for resolver precedence/fallback to prevent regression.
5. Keep fail-closed posture unchanged: if creds are still unavailable or unauthorized, stream-sort remains failed.

### Planned file touchpoints
1. `src/fraud_detection/oracle_store/stream_sorter.py`
2. `tests/services/oracle_store/test_stream_sorter_credentials.py` (new)
3. `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.impl_actual.md` (this lock + applied entry)
4. `docs/logbook/02-2026/2026-02-11.md` (action log)

### Validation plan
1. Run targeted pytest for new credential resolver tests.
2. Re-run `phase3c1` stream-sort command path (or equivalent make target) to confirm credential bridge removes `No credentials are provided` class of failure.
3. If bucket/policy denies remain, capture exact fail-closed reason post-auth-bridge.

### Cost posture declaration
Code + local tests only in this step; no paid sync operations are initiated by this patch itself.

## Entry: 2026-02-11 02:00PM - Applied DuckDB credential bridge fix for managed Oracle stream-sort

### Changes applied
1. Updated `src/fraud_detection/oracle_store/stream_sorter.py`:
- added `_resolve_aws_runtime_credentials(profile_region)` with precedence:
  - env static creds (`AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY`),
  - fallback to boto3 session/shared profile chain (`AWS_PROFILE` aware),
  - region fallback from profile/env/session.
- wired resolved credentials into `_duckdb_connect` via:
  - `SET s3_access_key_id`,
  - `SET s3_secret_access_key`,
  - optional `SET s3_session_token`,
  - `SET s3_region` from resolved value.
- added SQL literal escaping helper for dynamically injected pragma/SET string values.
- enriched duckdb config log with non-secret `credential_source` and final `s3_region`.
2. Added regression tests:
- `tests/services/oracle_store/test_stream_sorter_credentials.py`
  - env creds precedence,
  - boto3 session/shared-profile fallback,
  - no-credential fallback behavior.

### Validation executed
1. Compile checks:
- `python -m py_compile src/fraud_detection/oracle_store/stream_sorter.py tests/services/oracle_store/test_stream_sorter_credentials.py` (`PASS`).
2. Targeted tests:
- `python -m pytest tests/services/oracle_store/test_stream_sorter_credentials.py tests/services/oracle_store/test_checker.py tests/services/oracle_store/test_packer.py -q` (`PASS`, 9 passed).
3. Runtime credential resolution probe in current shell:
- `_resolve_aws_runtime_credentials(None)` returned `source=boto3_session`, credentials present, region `eu-west-2`.
4. Real managed S3 read-path probe (same failing locator class) using DuckDB:
- `_duckdb_columns(..., include_file_meta=True)` on `s3://.../part-*` returned columns successfully (`PASS`).
- This confirms the prior `No credentials are provided` path is remediated.

### Drift assessment
1. Ownership boundary preserved:
- Oracle remains engine-owned truth;
- patch only changes consumer-side auth bridging inside stream-sort runtime.
2. Fail-closed posture preserved:
- missing/invalid credentials still fail stream-sort;
- no local fallback introduced.
3. Contract posture preserved:
- stream-view output identity/layout and receipts/manifests unchanged.

### Cost posture
One read-only managed-S3 probe was executed (list/head/get class operations only). No background transfer/sync remains active. `TURN OFF NOW` for this debugging step.

## Entry: 2026-02-11 02:04PM - Pre-change lock: add managed AWS compute lane for Phase 3.C.1 stream-sort

### Trigger
USER direction: move stream-sort compute off local workstation to a cheap AWS runtime because local network-bound sort/upload loop is too slow for full Oracle world size.

### Current posture and gap
1. Existing `phase3c1` stream-sort command executes locally (`python -m ...stream_sort_cli`) even though data roots are managed S3.
2. This preserves data authority in S3 but leaves compute on user laptop.
3. No existing repo script currently submits/monitors managed sort compute jobs.

### Design intent alignment
- Preserve Oracle ownership and fail-closed acceptance gates.
- Keep output contracts unchanged (`stream_view/ts_utc/output_id=...` + manifest/receipt).
- Add managed compute as execution substrate only; no contract/schema drift.

### Options considered
1. Replace local sort target entirely with managed sort.
- Rejected for now: removes fallback lane and increases operator risk while managed substrate handles are being staged.
2. Add a parallel managed stream-sort lane (AWS Batch) with terminal monitoring and explicit preflight checks.
- Selected: enables migration immediately while preserving existing local lane for contingency.
3. Replatform sort logic to Glue/EMR now.
- Rejected for current step: larger redesign and slower time-to-value.

### Decisions locked before code
1. Implement new `stream-sort-managed` subcommand in `scripts/dev_substrate/phase3c1_oracle_authority_lock.py`.
2. Managed lane will:
- resolve required output_ids from policy refs locally,
- submit one AWS Batch job per output_id,
- tail CloudWatch logs and job status in terminal,
- emit phase evidence JSON and fail closed on any failed job.
3. New env/pin handles for managed lane:
- `DEV_MIN_PHASE3C1_BATCH_JOB_QUEUE` (required)
- `DEV_MIN_PHASE3C1_BATCH_JOB_DEFINITION` (required)
- optional tunables (name prefix, poll seconds, timeout, log group, wait toggle, vcpu/memory overrides).
4. Keep existing local `stream-sort` target untouched; add parallel Make target(s) for managed path.

### Planned file touchpoints
1. `scripts/dev_substrate/phase3c1_oracle_authority_lock.py`
2. `makefile`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.build_plan.md`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.impl_actual.md`
5. `docs/logbook/02-2026/2026-02-11.md`

### Validation plan
1. `py_compile` for updated script.
2. `--help` coverage for new subcommand.
3. `make -n` render checks for new managed targets.
4. Optional managed preflight/submit dry validation depending on available Batch handles.

### Cost posture declaration
Implementation + local validations only in this step; no managed job submission will be performed unless explicitly invoked.

## Entry: 2026-02-11 02:07PM - Applied Phase 3.C.1 managed stream-sort execution lane (AWS Batch)

### Changes applied
1. Extended `scripts/dev_substrate/phase3c1_oracle_authority_lock.py` with managed sort command:
- new subcommand: `stream-sort-managed`.
- behavior:
  - resolves required output_ids from policy refs,
  - validates Batch queue/definition presence,
  - submits one Batch job per output_id running `fraud_detection.oracle_store.stream_sort_cli` in container,
  - optional VCPU/MEM overrides,
  - optional CloudWatch log tail and status polling,
  - fail-closed evidence artifact: `phase3c1_oracle_stream_sort_managed_*.json`.
2. Added Batch execution tunables in `makefile`:
- `DEV_MIN_PHASE3C1_BATCH_JOB_QUEUE`
- `DEV_MIN_PHASE3C1_BATCH_JOB_DEFINITION`
- `DEV_MIN_PHASE3C1_BATCH_JOB_NAME_PREFIX`
- `DEV_MIN_PHASE3C1_BATCH_LOG_GROUP`
- `DEV_MIN_PHASE3C1_BATCH_POLL_SECONDS`
- `DEV_MIN_PHASE3C1_BATCH_TIMEOUT_SECONDS`
- `DEV_MIN_PHASE3C1_BATCH_VCPU`
- `DEV_MIN_PHASE3C1_BATCH_MEMORY_MIB`
- `DEV_MIN_PHASE3C1_BATCH_NO_WAIT`
- `DEV_MIN_PHASE3C1_BATCH_NO_LOG_TAIL`
3. Added Make targets:
- `platform-dev-min-phase3c1-stream-sort-managed`
- `platform-dev-min-phase3c1-stream-sort-managed-validate`.
4. Updated build plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.build_plan.md`
  - O1.C now includes managed sort lane requirement and DoD.
  - O1.C status moved to `in progress` (managed lane coded; live handles pending).

### Validation executed
1. `python -m py_compile scripts/dev_substrate/phase3c1_oracle_authority_lock.py` (`PASS`).
2. CLI help checks:
- `python scripts/dev_substrate/phase3c1_oracle_authority_lock.py --help` (`PASS`)
- `python scripts/dev_substrate/phase3c1_oracle_authority_lock.py stream-sort-managed --help` (`PASS`).
3. Make render check:
- `make -n platform-dev-min-phase3c1-stream-sort-managed platform-dev-min-phase3c1-stream-sort-managed-validate` (`PASS` render).
4. Fail-closed dry execution check with dummy handles:
- `make platform-dev-min-phase3c1-stream-sort-managed DEV_MIN_PHASE3C1_BATCH_JOB_QUEUE=dummy DEV_MIN_PHASE3C1_BATCH_JOB_DEFINITION=dummy DEV_MIN_PHASE3C1_BATCH_NO_WAIT=1`
- expected outcome observed: queue/definition checks `FAIL`, decision `FAIL_CLOSED`.

### Drift assessment
1. Ownership boundaries preserved:
- Oracle artifact semantics unchanged; only compute substrate for sort execution expanded.
2. Fail-closed law preserved:
- missing/miswired Batch handles block execution with explicit failure evidence.
3. Contract posture unchanged:
- output layout + manifest/receipt expectations remain identical.

### Cost posture
Validation touched control-plane AWS Batch describe calls only; no managed sort job was submitted with active handles in this pass. `TURN OFF NOW` for this implementation step.

## Entry: 2026-02-11 02:35PM - Pre-change lock: restore local stream-sort operator clarity with visible DuckDB progress

### Trigger
USER decided to continue with local sort lane for Oracle (`3.C.1`) and reported inability to monitor progress in terminal (`no DuckDB progress bar`).

### Problem framing
Current `cmd_stream_sort` runs child process output through `_run_command` with line-based stream pumps and prefix tagging.
- DuckDB progress rendering often uses carriage-return updates rather than newline lines.
- line-buffered `readline()` pumping can hide/reduce these updates.

### Decision
1. Preserve local lane as primary operator path for now.
2. Change local stream-sort execution to terminal passthrough mode (no output piping) so DuckDB native progress can render.
3. Add explicit Make toggle for sort progress interval that maps to `STREAM_SORT_PROGRESS_SECONDS`.
4. Keep fail-closed reporting/evidence unchanged.

### Planned file touchpoints
1. `scripts/dev_substrate/phase3c1_oracle_authority_lock.py`
2. `makefile`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.impl_actual.md`
4. `docs/logbook/02-2026/2026-02-11.md`

### Validation plan
1. `py_compile` for script.
2. `make -n platform-dev-min-phase3c1-stream-sort` to confirm env mapping.
3. local stream-sort command help/smoke path unchanged.

### Cost posture declaration
Local code update + dry checks only; no paid service actions initiated in this change.

## Entry: 2026-02-11 02:39PM - Applied local stream-sort observability fix (passthrough output + progress toggle)

### Changes applied
1. Updated `scripts/dev_substrate/phase3c1_oracle_authority_lock.py`:
- `_run_command` now supports `passthrough=True` mode (direct terminal inheritance, no stdout/stderr piping).
- `cmd_stream_sort` now executes stream-sort child process in passthrough mode so native DuckDB progress rendering is visible when enabled.
- preserved fail-closed check/evidence path (`stream_sort_<ref>` gate unchanged).
2. Updated `makefile`:
- added `DEV_MIN_PHASE3C1_STREAM_SORT_PROGRESS_SECONDS` (default `2`).
- `platform-dev-min-phase3c1-stream-sort` now exports `STREAM_SORT_PROGRESS_SECONDS` from that tunable.
- `platform-dev-min-phase3c1-run` and `platform-dev-min-phase3c1-stream-sort-managed` also export this value for consistency.

### Validation executed
1. `python -m py_compile scripts/dev_substrate/phase3c1_oracle_authority_lock.py` (`PASS`).
2. `python scripts/dev_substrate/phase3c1_oracle_authority_lock.py stream-sort --help` (`PASS`).
3. `make -n platform-dev-min-phase3c1-stream-sort platform-dev-min-phase3c1-run platform-dev-min-phase3c1-stream-sort-managed` (`PASS` render), confirming env export wiring.

### Operator outcome
- Local sort lane remains primary and unchanged in semantics.
- Terminal visibility improved: with `STREAM_SORT_PROGRESS_SECONDS` set (default now via make), DuckDB progress output can render directly.
- Managed lane remains optional and does not interfere with local execution.

### Cost posture
Local code + dry checks only; no paid service activity initiated in this change. `TURN OFF NOW`.
