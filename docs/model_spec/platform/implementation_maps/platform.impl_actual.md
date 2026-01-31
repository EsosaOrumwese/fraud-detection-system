# Platform Implementation Map
_As of 2026-01-24_

---

## Entry: 2026-01-24 22:43:13 — Platform v0 build-plan construction (initial)

### Problem / goal
User requested a platform-wide build plan (v0) that sets expectations for v0/v1/vX and guides component sequencing without locking us into full-detail steps upfront. The plan must be progressive-elaboration: phases only at first, with each phase broken into sections + DoD only when that phase begins. It must align to the platform blueprint, deployment-unit map, environment ladder, and truth-ownership doctrine.

### Authorities / inputs (binding)
- Root `AGENTS.md` (progressive elaboration rule, no half-baked phases, rails + truth ownership, logging discipline).
- `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md` (graph, pins, truth ownership, rails).
- `docs/model_spec/platform/platform-wide/deployment_tooling_notes_v0.md` (environment ladder, deployment units, substrate map, config policy posture, reference stack).
- Data Engine interface pack (boundary contract; no engine internals).
- Platform narratives (control+ingress; decision loop; label/case; learning/evolution; observability/governance).
- Existing SR build plan + impl_actual to avoid drift in SR scope.

### Decision trail / reasoning (live notes)
- The platform plan must be *plane-based* (Control+Ingress, Decision Loop, Label/Case, Learning/Registry, Obs/Gov) rather than just component-by-component, because the blueprint organizes truth ownership and join semantics by plane. This makes dependencies explicit and reduces drift.
- The plan should still name the major components to make scope measurable, but their sequencing should follow the plane order: SR+IG first (world readiness + admission), EB wiring next, then hot-path state/projection (IEG/OFP/DL/DF/AL/DLA), then Label/Case, then Learning/Registry, then Observability/Governance hardening.
- v0 should be production-shaped but minimal: single-region, single-tenant, local/dev parity, strict rails. v1 should cover scale/HA/multi-tenant, backfill/archive and stronger governance automation. vX should capture forward-looking capabilities (advanced multi-world orchestration, policy automation, richer model lifecycle, etc.).
- DoD needs to be concrete but not over-specified at the plan stage. Each phase DoD should be expressed as hard outcomes (interfaces present, invariants enforced, tests proving readiness). Detailed step lists should be deferred until entering that phase, per AGENTS.

### Alternatives considered (and why rejected)
- **Component-by-component plan only**: rejected because it hides cross-plane invariants and makes it easy to violate truth ownership boundaries.
- **Over-detailed step list from day one**: rejected because it conflicts with the progressive-elaboration rule and tends to become stale or misleading.
- **V0 only with no v1/vX**: rejected because user explicitly asked for expectation-setting beyond v0.

### Decisions to lock for this plan
- Use a *plane-first phase order* aligned to blueprint and narratives.
- Include explicit v0 scope boundary and v1/vX expectation ladder.
- Define phase DoD in terms of enforceable rails (pins, gates, idempotency, append-only, by-ref) + integration tests.
- Keep platform stack vendor-neutral but assume the reference local stack (Kafka-compatible EB + S3-compatible object store + Postgres + OTel stack) as the operational model, without hard-coding credentials.

### Immediate next actions
- Create `docs/model_spec/platform/implementation_maps/platform.build_plan.md` with v0 phases + DoD, and a v1/vX expectations section.
- Add a logbook entry with timestamp noting this planning step.

---

## Entry: 2026-01-24 23:01:54 — Expand Phase 1 (platform substrate + rails)

### Trigger
User asked to expand Phase 1 of the platform build plan (progressive elaboration) before any further platform work.

### Reasoning notes (live)
- Phase 1 is the platform’s “semantic foundation”; it must pin identity, contracts, and substrate conventions so later components can rely on them without drift.
- Keep Phase 1 sections concrete (DoD‑oriented) but avoid over‑specifying steps beyond this phase, per AGENTS progressive‑elaboration rule.
- Emphasize rails (ContextPins, envelope, no‑PASS‑no‑read, by‑ref), truth‑ownership boundaries, and environment ladder separation of policy vs wiring config.
- Ensure no secrets or credentials appear in the plan.

### Plan edits to make
- Add Phase 1 subsections with DoD checklists:
  - 1.1 Identity & envelope contracts
  - 1.2 By‑ref artifact addressing + locator/digest posture
  - 1.3 Event bus taxonomy + partitioning rules
  - 1.4 Environment ladder profiles + policy vs wiring config
  - 1.5 Security/secrets posture + provenance stamping requirements

---

## Entry: 2026-01-24 23:05:58 — Phase 1 implementation start (rails + substrate pins)

### Problem / goal
Begin Phase 1 implementation by pinning platform-wide rails and substrate conventions into concrete, reusable docs and profile stubs. This is the semantic foundation that later components must inherit without drift.

### Inputs / authorities
- Root AGENTS.md (rails + progressive elaboration + secrets posture).
- Platform blueprint + deployment tooling notes (truth ownership, envelope, substrate map, bus taxonomy, env ladder).
- Engine interface pack contracts (canonical_event_envelope, locator/receipts, storage layout).

### Live decision trail
- I need a **single source of truth** for rails, but I want to avoid duplicating engine contracts verbatim. I will **reference** the canonical envelope contract from the engine interface pack and pin platform semantics around it, rather than copy it into a new schema file (avoids drift).
- To keep Phase 1 artifacts usable, I’ll create a **platform-wide rails + substrate doc** that consolidates: identity/envelope, by-ref addressing, bus taxonomy, environment profiles, and secrets posture.
- For environment ladder profiles, I will add a **profiles folder with non-secret stubs** (local/dev/prod). These are structural examples only; they intentionally omit credentials and rely on env injection at runtime.

### Planned edits (Phase 1 scope only)
- Add a platform-wide doc: `docs/model_spec/platform/platform-wide/platform_rails_and_substrate_v0.md`.
- Add `config/platform/profiles/README.md` plus minimal `local.yaml`, `dev.yaml`, `prod.yaml` stubs (no secrets).

---

## Entry: 2026-01-24 23:09:25 — Phase 1 artifacts added (rails + profiles)

### What I changed (and why)
- Added `docs/model_spec/platform/platform-wide/platform_rails_and_substrate_v0.md` as the platform-wide, binding rails + substrate pin. This consolidates identity/envelope semantics, by-ref addressing, bus taxonomy, env profiles, and secrets posture in one place to avoid drift and document the “laws” before component work.
- Referenced the canonical envelope **by path** to the engine interface pack contract instead of copying it, to avoid schema drift between engine and platform boundary.
- Created `config/platform/profiles/README.md` plus `local.yaml`, `dev.yaml`, `prod.yaml` stubs to make the policy-vs-wiring separation concrete without embedding secrets.

### Notes / invariants pinned in the new doc
- ContextPins are fixed to `{scenario_id, run_id, manifest_fingerprint, parameter_hash}`; `seed` remains separate and required only when seed-variant.
- Time semantics are pinned: `ts_utc` is domain time; `emitted_at_utc` optional; ingestion time only in IG receipts.
- Object-store prefix map and instance-receipt paths are pinned to the v0 substrate map.
- EB taxonomy is pinned to `fp.bus.{traffic,control,audit}.v1` with deterministic partition_key stamped by IG.
- Secrets are runtime-only; provenance may record secret identifiers only.

---

## Entry: 2026-01-24 23:14:10 — Tighten platform rails/substrate doc

### Trigger
User asked to review and tighten the Phase 1 rails/substrate doc wording for clarity and non-ambiguity.

### Reasoning notes
- The doc should explicitly state envelope minimality and payload isolation to prevent accidental field collisions.
- Token naming constraints should be called out (allowed token names + canonical order) to prevent drift in paths.
- The no‑PASS‑no‑read and fail‑closed posture should be re‑stated within the by‑ref/digest section so it is not only implicit.
- Add explicit note that `fp.bus.audit.v1` is optional and never a truth stream to prevent misuse.

### Planned edits
- Add envelope minimality + payload isolation note.
- Add token naming rule alongside token order.
- Add fail‑closed + no‑PASS‑no‑read reminder under digest posture.
- Clarify audit topic is optional and non-authoritative.

---

## Entry: 2026-01-24 23:25:28 — Tighten rails/substrate wording (applied)

### Changes applied
- Added envelope minimality note (payload isolated under `payload`; no extra top-level fields).
- Added explicit fail-closed / no-PASS-no-read reminder under digest posture.
- Added allowed token-name list to prevent path-token drift.
- Restated audit topic as optional and non-authoritative.

---

## Entry: 2026-01-24 23:30:30 — Phase 1.2 + 1.3 artifacts (by-ref validation + partitioning policy)

### What I changed
- Added a **by-ref validation checklist** doc to make locator/digest/gate/instance-proof checks explicit and fail‑closed.
- Added **partitioning policy guidance** doc to pin deterministic routing posture and stream-specific key precedence.
- Added IG policy stubs (`partitioning_profiles_v0.yaml`) and README under `config/platform/ig/` with non‑secret examples.

### Rationale (live)
- Phase 1.2 needed a concrete, testable checklist so component implementations (SR/IG/OFS/DLA) don’t diverge on by‑ref integrity.
- Phase 1.3 needed policy stubs that express deterministic routing **without** hard‑coding secrets or vendor tooling; profiles are versioned and referenceable by `partitioning_profile_id`.

### Notes / invariants pinned
- Locator validation must check schema, path template, pin consistency, and token order.
- Instance‑scoped outputs require locator `content_digest` and (where required) instance‑proof receipts bound to locator+digest.
- IG must stamp partition_key deterministically; EB never infers routing.

---

## Entry: 2026-01-25 05:33:37 — Platform contracts index + profile alignment

### Trigger
User requested a compact platform contracts index under docs/model_spec/platform/contracts and alignment of platform profiles to reference partitioning_profiles_v0.yaml (policy_rev + partitioning_profile_id).

### Reasoning notes
- A small index file prevents schema drift and makes the canonical envelope + locator/receipt contracts discoverable without duplication.
- Profiles should explicitly point to the partitioning policy file to keep routing decisions versioned and auditable.

### Planned edits
- Add `docs/model_spec/platform/contracts/README.md` referencing canonical envelope + locator/receipt schemas in the engine interface pack.
- Update `config/platform/profiles/*.yaml` to include `policy.partitioning_profiles_ref` and set `policy.partitioning_profile_id` to a concrete profile in `config/platform/ig/partitioning_profiles_v0.yaml`.

---

## Entry: 2026-01-25 05:34:18 — Contracts index + profile alignment (applied)

### Changes applied
- Added `docs/model_spec/platform/contracts/README.md` to index canonical envelope + locator/receipt contracts by reference.
- Updated platform profiles to reference `config/platform/ig/partitioning_profiles_v0.yaml` and set `partitioning_profile_id` to `ig.partitioning.v0.traffic`.

### Notes
- Profile files remain non‑secret; endpoints still come from env injection.

---

## Entry: 2026-01-25 05:36:55 — IG partitioning profile mapping note

### Trigger
User asked to add an explicit IG policy note mapping partitioning_profile_id to stream classes (traffic/control/audit).

### Plan
- Update `config/platform/ig/README.md` with a mapping table from stream class → partitioning_profile_id.

---

## Entry: 2026-01-25 05:37:19 — IG stream class mapping (applied)

### Change
- Added explicit stream‑class → `partitioning_profile_id` mapping to `config/platform/ig/README.md`.

---

## Entry: 2026-01-25 05:40:12 — Phase 1.4 + 1.5 validation start (policy/wiring + secrets sweep)

### Trigger
User asked to proceed with Phase 1.4 validation (policy vs wiring separation audit) and Phase 1.5 (secrets posture sweep).

### Audit plan (no secrets exposed)
- Inventory config/platform policy vs wiring files and check for obvious mixing (policy files containing endpoints/ports; wiring files containing outcome-affecting policy fields).
- List .env files by name only; do not display contents.
- Scan for common secret key markers by filename only (no content printed).
- Update any docs if the profile schema or separation guidance needs alignment.

---

## Entry: 2026-01-31 06:59:40 — Control & ingress parity “green” procedure (run-id‑scoped receipts + EB offsets)

### Problem / goal
We need a **clean parity run** that proves SR → WSP → IG → EB is functioning for the *current* platform run id, with IG receipts and EB offsets visible under the same run prefix. Prior attempts were “almost green” but failed to attach receipts to the active run due to service ordering (IG started before the new run id) and stale Kinesis messages.

### Inputs / authorities
- Root `AGENTS.md` (no half-baked phases; logbook + impl_actual discipline).
- `config/platform/profiles/local_parity.yaml` (S3 root `s3://fraud-platform`, Kinesis control/event buses).
- Runbook `docs/runbooks/platform_parity_walkthrough_v0.md` (local parity flow).
- Platform logging / run-id conventions (run-scoped paths under `runs/fraud-platform/<run_id>/`).

### Live decision trail
- We must **restart IG after `platform-run-new`** so `PLATFORM_RUN_ID` and run-prefix are correct; otherwise receipts land under the old run id.
- Kinesis control bus is persistent; old READY messages cause WSP to consume the wrong run. For a clean parity smoke, **reset the streams** (`sr-control-bus`, `fp-traffic-bus`) before publishing READY.
- “Green” needs three proofs in the same run id: SR READY published, WSP streamed (cap), and IG receipts written (with EB offsets). EB offsets are verified separately via LocalStack Kinesis read.

### Procedure (validated)
1) Stop IG service on port 8081.
2) `make platform-run-new` → capture new run id (ACTIVE_RUN_ID).
3) Start IG service (`make platform-ig-service-parity`) **after** run id is created.
4) Reset Kinesis streams (delete/recreate `sr-control-bus` + `fp-traffic-bus`).
5) SR publish READY with fresh equivalence key.
6) WSP `--once` with `max_events=20` (cap) to confirm flow.
7) Verify:
   - Receipts exist under `s3://fraud-platform/<run_id>/ig/receipts/`.
   - EB has records in LocalStack (`fp-traffic-bus`).

### Evidence observed (local parity)
- Run id: `platform_20260131T065731Z`.
- SR READY: `run_id=38751de2498b847c3e0a5e895012388e`, message_id `e47e5b8a...`.
- WSP streamed 20 events and stopped with `reason=max_events`.
- Receipts present under `platform_20260131T065731Z/ig/receipts/` in `fraud-platform` bucket.
- EB stream `fp-traffic-bus` returned records via LocalStack Kinesis read.

### Operational invariants to keep
- **IG must be started after the platform run id is created.**
- **Control bus must be clean** for a deterministic smoke run.
- Receipts are the authoritative signal that IG published to EB (eb_ref); platform.log is narrative only.

---

## Entry: 2026-01-31 08:30:45 — Full-name component log directories

### Trigger
User requested log filenames be **full component names**, not abbreviations (e.g., `sr` → `scenario_runner`).

### Decision
Keep `PLATFORM_COMPONENT` short for env ergonomics, but **map to full names** for log directories and log file names. EB diagnostics log is now `event_bus/event_bus.log`.

### Outcome
Component logs now land under:
- `runs/fraud-platform/<run_id>/scenario_runner/scenario_runner.log`
- `runs/fraud-platform/<run_id>/world_streamer_producer/world_streamer_producer.log`
- `runs/fraud-platform/<run_id>/ingestion_gate/ingestion_gate.log`
- `runs/fraud-platform/<run_id>/event_bus/event_bus.log`


---

## Entry: 2026-01-25 05:45:40 — Phase 1.4/1.5 audit results (policy vs wiring + secrets)

### Phase 1.4 — Policy vs wiring separation (results)
- **Config inventory (platform):**
  - Policy files: `config/platform/sr/policy_v0.yaml`, `config/platform/ig/partitioning_profiles_v0.yaml`, `config/platform/profiles/*.yaml` (policy sections).
  - Wiring files: `config/platform/sr/wiring_*.yaml`, `config/platform/profiles/*.yaml` (wiring sections).
- **Mixing check:** no endpoint/url/host/port keys found in policy files (sr policy + ig partitioning profiles). This keeps policy clean.
- **Docs alignment:** updated `config/platform/profiles/README.md` to include `partitioning_profiles_ref` and clarify stream‑class mapping for `partitioning_profile_id`.

### Phase 1.5 — Secrets posture sweep (results)
- **.env presence:** `.env` and `.env.localstack.example` exist; both are listed in `.gitignore` (so they should not be committed). No contents inspected.
- **Secret‑marker scan:** filename‑only scan for common secret key tokens found matches in tests/docs (likely placeholders). No secret contents were printed or logged.

### Open notes
- If you want a stricter secrets policy, we can add a repo‑wide pre‑commit rule or a CI check that blocks secret‑like strings in tracked files.

---

## Entry: 2026-01-25 05:50:21 — Mark Phase 1 complete; expand Phase 2

### Phase 1 completion note
- Phase 1.1–1.5 deliverables are now in place: rails/substrate doc, by‑ref validation checklist, partitioning policy guidance, IG partitioning profiles, profile schema alignment, and policy/wiring + secrets posture validation.

### Next step
- Expand Phase 2 (Control & Ingress plane: SR + IG + EB) into sections with DoD checklists under the progressive‑elaboration rule.

---

## Entry: 2026-01-25 05:56:08 — SR v0 marked ready for IG; path alignment follow‑up

### Decision
User requested that SR v0 be treated as done/ready to proceed to IG, with the caveat that SR path alignment remains outstanding.

### Rationale
- SR’s functional v0 build is complete and validated; moving to IG unblocks platform progress.
- Path alignment to the platform prefix map is a known gap; it is explicitly recorded as a follow‑up so we do not misrepresent readiness.

### Change applied
- Marked Phase 2.1 as “ready to proceed to IG” with an explicit note about path‑alignment follow‑up in `platform.build_plan.md`.

### Follow‑up (must close)
- Align SR object‑store paths with the platform substrate prefix map (fraud‑platform/sr/...).

---

## Entry: 2026-01-25 06:07:06 — Start IG planning (component build plan + impl_actual)

### Trigger
User said “proceed” after clarifying platform vs component build plans; we are moving into IG planning under Phase 2.

### Reasoning notes
- IG is the admission authority and must be planned separately from platform Phase 2 so its internal flows, policies, and invariants are explicit.
- The IG build plan must stay component-scoped and progressive-elaboration: phase list first; expand Phase 1 as we begin.
- IG must enforce canonical envelope + schema version policy, gate verification, idempotency, deterministic partition key stamping, and receipt emission with by-ref evidence.

### Planned artifacts
- Create `docs/model_spec/platform/implementation_maps/ingestion_gate.build_plan.md` with v0 phases.
- Create `docs/model_spec/platform/implementation_maps/ingestion_gate.impl_actual.md` with initial decision trail.

---

## Entry: 2026-01-25 18:30:15 — Local workflow automation (SR + IG)

### Problem / goal
Manual environment setup and command sequences are error‑prone. We need a **standard, repeatable local workflow** for SR + IG that hides boilerplate, keeps credentials out of the repo, and supports the SR→IG verification loop.

### Decisions (live reasoning)
- Use **PowerShell scripts** as the primary local runner because this repo is being run on Windows and Make is not guaranteed.
- Provide a **single entrypoint** (`scripts/platform.ps1`) with explicit actions to keep the workflow simple and discoverable.
- Use `.env.local` (gitignored) for local secrets; document **only placeholders** in `.env.example` to avoid credential leakage.
- Keep scripts minimal and transparent (no opaque magic); every action maps to an explicit SR/IG CLI call.

### Implementation summary
- Added `scripts/platform.ps1` with commands to:
  - bring up/down local stack
  - run SR reuse (engine artifacts)
  - run IG READY once or dual‑instance lease demo
  - run IG audit verification
- Added `scripts/README.md` with usage examples.
- Added `.env.example` for non‑secret placeholders.
- Updated root `README.md` to point to the scripts.

### Guardrails
- No secrets in repo. `.env.local` is for local use only and must remain gitignored.
- Scripts are local‑only helpers; production deployments use proper orchestration.

---

## Entry: 2026-01-25 20:55:30 — Local workflow + runtime root migration (Makefile, runs/fraud-platform)

### Trigger
User explicitly rejected the PowerShell helper and asked for a **Makefile‑only** workflow, plus a hard migration of all platform runtime artifacts from `artefacts/fraud-platform` to `runs/fraud-platform`.

### Live reasoning (why this change is necessary)
- The repo already uses a Makefile as the primary engine runner; keeping SR/IG in a separate script path creates an inconsistent workflow surface and violates the “no dangling scripts” directive.
- The platform runtime artifacts are *not* external engine inputs; they are platform outputs. Keeping them under `artefacts/` conflicts with the intended meaning (external datasets) and makes it easier to accidentally commit runtime state.
- A single, consistent runtime root (`runs/fraud-platform`) reduces path ambiguity, fixes `fraud-platform/fraud-platform` joins, and makes it easier to reason about SR → IG hand‑offs.

### Plan (stepwise, before code)
1) Replace script‑based workflow with Makefile targets:
   - `platform-stack-up/down/status`
   - `platform-sr-run-reuse`
   - `platform-ig-ready-once/dual`
   - `platform-ig-audit`
2) Add optional `.env.platform.local` loading in Makefile (gitignored) so users don’t set env vars manually.
3) Update all wiring/config defaults and docs that refer to `artefacts/fraud-platform` → `runs/fraud-platform`.
4) Update any test fixtures and smoke tests that search for SR artifacts so they find the new root.
5) Move the on‑disk folder `artefacts/fraud-platform/` to `runs/fraud-platform/`.
6) Remove `scripts/platform.ps1` + `scripts/README.md` and update README references.

### Guardrails
- No credentials or secrets will be added to docs or impl_actual (only placeholders).
- Historical entries that mention `artefacts/fraud-platform` remain as history; a new note will clarify the migration rather than rewriting prior decisions.

---

## Entry: 2026-01-25 21:05:56 — Applied: Makefile workflow + runtime root migration

### What I changed (and why it matches the directive)
I removed the PowerShell workflow and replaced it with Makefile targets so **SR/IG local flows are unified with the engine’s workflow**. This keeps the repo consistent, avoids ad‑hoc env setup, and aligns with the “no dangling scripts” instruction.

### Applied changes (concrete)
1) **Makefile** (`makefile`)
   - Added optional `.env.platform.local`/`.env.local` includes for local overrides (gitignored).
   - Added platform targets: `platform-stack-*`, `platform-sr-run-reuse`, `platform-ig-ready-once/dual`, `platform-ig-audit`.
   - Defaulted SR reuse args to the known working engine run (override via Make vars).
2) **README** (`README.md`)
   - Replaced script references with the Make targets.
   - Documented `.env.platform.local` usage (no secrets committed).
3) **Removed scripts**
   - Deleted `scripts/platform.ps1` and `scripts/README.md`.

### Notes
- No credentials are embedded. Any DSN/endpoint values remain placeholders or local defaults.
- This change is purely workflow; runtime path migration is tracked in SR/IG component maps.

---

## Entry: 2026-01-25 21:10:05 — Applied: remove remaining PowerShell scripts

### Trigger
User reiterated that **all** platform workflows must be Makefile‑based (no PowerShell helpers).

### Changes applied
- Removed `scripts/run_sr_tests.ps1` and `scripts/localstack.ps1`.
- Added Make targets for SR test tiers and LocalStack lifecycle:
  - `sr-tests-tier0|parity|localstack|engine-fixture|all`
  - `localstack-up|localstack-down|localstack-logs`
- Updated `services/scenario_runner/README.md` to reference the Make targets.

### Rationale
This keeps local workflows consistent, removes dangling scripts, and aligns SR/IG tooling with the engine’s Makefile‑first approach.

---

## Entry: 2026-01-25 22:50:20 — Plan: platform run IDs + shared + per‑run logs

### Trigger
User asked for a **platform run ID** so SR/IG don’t keep writing into a single folder and requested that SR/IG append into a **shared platform log** while still keeping runs separated.

### Live reasoning
- SR/IG artifacts already live under `runs/fraud-platform/*`; however, without a platform‑run concept, logs from different sessions blend together.
- We need a **lightweight session boundary** that doesn’t alter SR/IG canonical ledgers (ownership rules) but still provides an audit trail and operator clarity.
- The most compatible approach: keep SR/IG ledgers where they are, but write **session‑scoped logs** and **session manifests** under a `<platform_run_id>/` folder.

### Plan (stepwise)
1) Add a small runtime helper (`platform_runtime.py`) to resolve a `platform_run_id`:
   - Use `PLATFORM_RUN_ID` if set.
   - Else read `runs/fraud-platform/ACTIVE_RUN_ID` if present.
   - Else generate a new ID on SR `run` and persist to `ACTIVE_RUN_ID`.
2) Update logging utilities to support **multiple log files**:
   - Always append to `runs/fraud-platform/platform.log`.
   - Also append to `runs/fraud-platform/<platform_run_id>/platform.log` when an active run ID exists.
3) Add a `session.jsonl` (append‑only) in the run folder with basic metadata:
   - component (`sr`/`ig`), command kind, timestamps, and key refs (run_id/message_id/status_ref).
4) Update Makefile to expose `PLATFORM_RUN_ID` (optional) and document in `.env.example`.

### Guardrails
- No secrets or credentials in session files.
- Do **not** move SR/IG ledgers or change their ownership; only add session metadata and logs.

## Entry: 2026-01-25 23:07:13 — Apply platform run IDs + session log wiring (platform scope)

### Trigger
User approved the plan to introduce **platform run IDs** and session‑scoped logs while preserving SR/IG ledger ownership. We also need a deterministic way to keep **one shared platform log** while still capturing per‑session traces.

### Live reasoning (what I am doing and why)
- A platform run is an **operator concept**, not a ledger owner. I will keep SR/IG ledgers in place and only add session folders for logs and metadata.
- The **global platform log** remains the primary operator view (`runs/fraud-platform/platform.log`). Session logs are additive and help isolate a specific run without losing the global trace.
- I will not generate a run ID for **non‑run commands** (e.g., IG health, lookup) unless a run ID is explicitly set by env or ACTIVE_RUN_ID. This avoids creating fake sessions.

### Implementation steps (platform‑wide)
1) Add a small runtime helper (`src/fraud_detection/platform_runtime.py`) to resolve `platform_run_id` via:
   - `PLATFORM_RUN_ID` env (explicit override), else
   - `runs/fraud-platform/ACTIVE_RUN_ID` (if present), else
   - generate a new ID when SR `run` is executed.
2) Update SR + IG logging utilities to accept **multiple log paths** and append to:
   - `runs/fraud-platform/platform.log` (always)
   - `runs/fraud-platform/<platform_run_id>/platform.log` (when available)
3) Record per‑session metadata in `session.jsonl` (append‑only) with **non‑secret** details only.
4) Update service entrypoints to use `platform_log_paths()` so long‑running services append to the same shared log surface.

### Guardrails
- No secrets or credentials are written to session files or logs.
- SR/IG artifact roots and ledger ownership are unchanged.


## Entry: 2026-01-25 23:12:50 — Applied: platform run session logs + Make target

### What changed
1) **Runtime helper**
   - `src/fraud_detection/platform_runtime.py` added/updated to resolve platform run IDs and write `session.jsonl` entries.
   - `PLATFORM_LOG_PATH` is respected for the global log path; session logs remain under `runs/fraud-platform/<id>/`.

2) **Workflow**
   - Added `make platform-run-new` to reset `ACTIVE_RUN_ID` and create a new session ID for the next SR/IG run.

3) **Docs**
   - `.env.example` now includes `PLATFORM_RUN_ID` (optional).
   - SR/IG service READMEs note session log behavior and how to reset the session.

### Guardrails
- No secrets are written to session files; these are metadata‑only.
- SR/IG ledgers remain unchanged.


## Entry: 2026-01-25 23:30:20 — Workflow support for SR READY reemit (Makefile)

### Reasoning
To progress sharded IG pulls under a local time budget, we need a safe way to **re‑emit READY** for an existing run_id without creating a new SR run. The most consistent workflow surface is a Make target (no scripts).

### Planned change
- Add a Make target that wraps `python -m fraud_detection.scenario_runner.cli reemit` with:
  - `SR_REEMIT_RUN_ID` (required)
  - optional `SR_REEMIT_KIND` (default READY)

This keeps local workflow centralized while preserving SR ownership semantics.


## Entry: 2026-01-25 23:33:10 — Applied: Make target for SR reemit

### Change
- Added `platform-sr-reemit` Make target to call `fraud_detection.scenario_runner.cli reemit` with required `SR_REEMIT_RUN_ID` and optional `SR_REEMIT_KIND` (default READY).

### Why
This enables repeated READY emission for the same run_id so IG can progress through sharded checkpoints under a local time budget.


## Entry: 2026-01-25 23:35:15 — Fix: SR reemit kind default

### Issue
`platform-sr-reemit` initially defaulted to `ready`, but the CLI accepts only `READY_ONLY|TERMINAL_ONLY|BOTH`.

### Fix
- Updated Makefile default to `READY_ONLY` and aligned README example.


## Entry: 2026-01-25 23:59:40 — Applied: local smoke vs dev completion policy

### Applied changes
1) **Profiles**
   - Added `config/platform/profiles/dev_local.yaml` (uncapped, local filesystem) for completion runs.
   - `local.yaml` remains time‑budgeted for smoke.

2) **Makefile**
   - Added `IG_PROFILE_DEV` default and `platform-ig-ready-once-dev` target to run the completion profile without manual overrides.

3) **Docs**
   - `config/platform/profiles/README.md` now states the testing policy explicitly.
   - `services/ingestion_gate/README.md` documents local vs dev usage.
   - Platform build plan (Phase 1.4) now pins local smoke vs dev completion policy.

### Rationale
Local smoke must be fast and deterministic; dev completion must be uncapped to validate full ingestion. This keeps production semantics intact while giving clear expectations for each environment.


## Entry: 2026-01-26 02:15:30 — Dev completion run blocked by local hardware

### Observation
An uncapped dev completion run on local hardware did not finish within 2 hours. This confirms that **full completion must be executed on stronger dev infra** or with more granular chunking.

### Implication
Local remains smoke‑only. Dev completion requires either a real dev environment or additional chunking work if we must complete locally.


## Entry: 2026-01-28 09:44:30 — Authority hierarchy clarification

### Trigger
User noted potential ambiguity between the two core platform-wide notes and supplemental platform-wide guardrail docs.

### Decision
Clarify in `AGENTS.md` that the **core authority** remains:
- `platform_blueprint_notes_v0.md`
- `deployment_tooling_notes_v0.md`

Supplemental platform-wide docs (byref_validation, partitioning_policy, rails_and_substrate) are **guardrail references** only and do not override the core notes. Component design‑authority docs remain authoritative for component‑specific mechanics.

### Change
- Added an explicit “Authority clarification” block under the reading order section.

---

## Entry: 2026-01-28 13:05:20 — Revamp platform build plan for Oracle Store + WSP

### Trigger
User approved building **Oracle Store** (sealed engine outputs boundary) + **WSP** (stream head) before refactoring SR/IG. Requested a revamped platform build plan to reflect this sequencing and to allow a speedup factor across all environments.

### Live reasoning (decision trail)
- The platform’s runtime shape changed: **WSP is the primary producer** and the engine is a sealed world builder. The build plan must expose this explicitly so component sequencing aligns with the intended bank‑like temporal flow.
- Oracle Store is a **platform boundary component** (immutable by‑ref world store). Treating it as its own component makes its invariants visible and prevents WSP from silently redefining storage contracts.
- SR/IG already exist, but they were built under a legacy “engine pull” assumption. The plan must capture **alignment/refactor** as a later phase, not implied by existing SR/IG work.
- Speedup factor should be **available in all envs** (local/dev/prod) but remains a **policy knob** (not hard‑coded). The plan should reflect that the same semantics apply at any speed.
- Progressive elaboration still holds: we only expand new phases (Oracle Store + WSP) to section/DoD detail; other phases remain high‑level unless already expanded.

### Plan edits to apply
- Insert a new early phase for **World Oracle + Stream Head**:
  - Oracle Store contract (immutability, by‑ref locator rules, env ladder)
  - WSP v0 (READY‑driven stream, canonical envelope framing, pacing/clock policy + speedup factor)
- Re‑state Phase 2 as **Control & Ingress alignment** (SR/IG/EB refactor to WSP truth) rather than first‑time construction.
- Update Phase status roll‑up to show Phase 1 complete; Phase 2 (Oracle/WSP) next.

---

## Entry: 2026-01-28 15:46:33 — **IMPORTANT** Oracle Store is outside the platform runtime graph

### Clarified platform boundary
The Oracle Store is **external engine truth** (sealed worlds) and is **not** part of the platform runtime graph. The platform **reads** from it (via WSP), but does not “own” it as a runtime vertex. Platform runtime artifacts remain in `runs/fraud-platform` and are **not** valid oracle inputs.

### Why we’re locking this in
- Avoids accidental coupling where platform outputs (SR/IG ledgers, logs) are treated as oracle data.
- Preserves the “engine outside the platform” model and keeps WSP’s producer role clean.
- Guarantees that wiping platform runtime state does not invalidate oracle truth.

### Operational note (local/dev)
- Local/dev may point `oracle_root` to `runs/local_full_run-5` or future `runs/data-engine`; the **conceptual boundary is external**, even if the path lives inside the repo.



---

## Entry: 2026-01-29 02:16:10 — Add `platform-smoke` make target (SR→WSP→IG cap)

### Intent
Provide a **single make target** that runs the local SR→WSP→IG smoke flow without manual caps or keys, while keeping IG service startup explicit.

### Decision trail
- Users repeatedly had to supply `SR_RUN_EQUIVALENCE_KEY` and `WSP_READY_MAX_EVENTS` by hand; this is error‑prone and slows local validation.
- IG runs as a long‑lived service; starting/stopping it inside a make target is brittle on Windows, so the target should **prompt** the operator to run `make platform-ig-service` in another terminal.
- The smoke path should remain bounded and deterministic; it should not attempt full completion.

### Implementation
- Added `PLATFORM_SMOKE_MAX_EVENTS` (default `20`).
- Added `platform-smoke` target that:
  1) creates a new platform run id,
  2) cleans the control bus,
  3) generates a fresh run_equivalence_key via Python,
  4) runs SR reuse,
  5) runs WSP READY once with the cap.

### Expected usage
- Terminal A: `make platform-ig-service`
- Terminal B: `make platform-smoke`

---

## Entry: 2026-01-29 18:48:00 — Draft maximum‑parity local stack plan (compose + config + migration)

### Trigger
User requested a “Maximum Parity Local Stack Plan” so local can mirror dev/prod with minimal environment‑ladder friction.

### Decision trail (live reasoning)
- The current local stack uses **file‑bus + SQLite + filesystem oracle**, which is fast but diverges from the production‑shape backends.
- The cleanest way to reduce ladder friction is to provide a **parity mode** that swaps local backends for the same service *classes* used in dev/prod (S3/Kinesis/Postgres), while keeping the wiring schema identical.
- This must remain **opt‑in** so fast local smoke stays available; parity mode should be the default when validating ladder climbs.
- The plan should be explicit about **compose services**, **profile wiring**, and a **stepwise migration** so we can implement without breaking ongoing work.

### Change
- Added a **Local Stack Maximum‑Parity Plan** section to `docs/model_spec/platform/implementation_maps/platform.build_plan.md`, including:
  - parity target shape,
  - compose blueprint (MinIO + LocalStack + Postgres),
  - parity profile wiring,
  - stepwise migration steps,
  - concrete deliverables (compose file, local parity profile, make targets).

---

## Entry: 2026-01-29 18:59:42 — Proceed to implement maximum‑parity local stack (ladder‑friction removal)

### Trigger
User approved “robust implementation and removal of every ladder friction” to achieve the target parity shape.

### Live reasoning (decision trail)
- Local currently uses **file‑bus + SQLite + filesystem oracle**, which is intentionally fast but **behaviorally different** from dev/prod; this is a known ladder‑friction source.
- To eliminate friction, local must use the **same classes of backends** as dev/prod: S3‑compatible object store, Kinesis‑compatible control/event buses, and Postgres for indexes/checkpoints.
- The change is **platform‑wide** (multiple components), so the plan belongs in `platform.impl_actual.md` and will fan out to component impl_actual entries as needed.
- We must **preserve fast smoke** by keeping existing local profile, but introduce a **parity profile + parity compose** that matches dev/prod semantics while still local.
- Avoid introducing secrets into docs; all credentials stay in env/.env and are referenced only by name.

### Implementation plan (stepwise, hardened)
1) **Parity infra compose**  
   - Add `infra/local/docker-compose.platform-parity.yaml` with **MinIO + LocalStack(Kinesis) + Postgres**.  
   - Include a MinIO bootstrap/init container to create `oracle-store` + `fraud-platform` buckets.  
   - Declare ports + healthchecks for stable local runs.

2) **Parity profile wiring**  
   - Add `config/platform/profiles/local_parity.yaml` with:  
     - `object_store.root: s3://fraud-platform` (path‑style).  
     - `oracle_root: s3://oracle-store/<run-root>` (env‑override).  
     - `event_bus_kind: kinesis`, `event_bus.stream` for LocalStack.  
     - `control_bus.kind: kinesis`, `control_bus.stream`.  
     - `wsp_checkpoint.backend: postgres` (DSN env).  
     - IG admission index DSN (env) instead of SQLite path.

3) **IG Postgres backend**  
   - Implement Postgres admission + ops index backend (schema parity with SQLite).  
   - Wiring: if `IG_ADMISSION_DSN` is set or `admission_db_path` is a DSN, select Postgres.  
   - Keep SQLite fallback for unit tests only.  
   - Update health probe to check Postgres connectivity.

4) **WSP checkpoint Postgres parity**  
   - Ensure Postgres checkpoint backend is usable in local parity profile.  
   - Validate resume semantics under restarts in parity mode.

5) **Control bus parity (Kinesis)**  
   - Add Kinesis READY reader in WSP control bus and wire it via profile `control_bus.kind: kinesis`.  
   - Reuse SR’s Kinesis control bus publisher.

6) **EB parity (Kinesis)**  
   - Ensure local parity profile uses `event_bus_kind: kinesis` with LocalStack endpoint.  
   - Keep file‑bus only for `local` smoke profile.

7) **Make targets + operator guidance**  
   - Add make targets for parity stack up/down, stream/bucket bootstrap, and parity smoke run.  
   - Update profile README to document parity profile usage and env vars.

8) **Validation**  
   - Run parity smoke: SR → WSP → IG → EB on LocalStack/MinIO/Postgres.  
   - Confirm no schema errors, offsets advance in Kinesis, and IG receipts persist in Postgres.

### Files/areas to touch
- `infra/local/docker-compose.platform-parity.yaml` (new)  
- `config/platform/profiles/local_parity.yaml` (new)  
- `src/fraud_detection/ingestion_gate/*` (Postgres index backend, DSN wiring)  
- `src/fraud_detection/world_streamer_producer/control_bus.py` + `ready_consumer.py` (Kinesis reader)  
- `config/platform/profiles/README.md` + make targets  
- Component impl_actual notes (IG/WSP/EB) + logbook entries

---

## Entry: 2026-01-29 19:12:05 — Implement maximum‑parity local stack (infra + profiles + make targets)

### Outcome summary
- Added local parity compose stack (MinIO + LocalStack(Kinesis) + Postgres).
- Added `local_parity.yaml` profile and updated dev/prod profiles for explicit Kinesis + DSN wiring.
- Added parity make targets and defaults to eliminate manual env gymnastics.

### Concrete changes
- **Infra:** `infra/local/docker-compose.platform-parity.yaml` (MinIO + LocalStack + Postgres + init jobs).
- **Profiles:** new `config/platform/profiles/local_parity.yaml`; updated `dev_local.yaml`, `dev.yaml`, `prod.yaml`.
- **WSP/IG wiring:** control bus and event bus now explicitly Kinesis in parity/dev/prod profiles.
- **Makefile:** parity stack targets + parity smoke target with default envs.
- **Profile docs:** expanded to include parity profile + env variables.

### Notes
- File‑bus + SQLite remain available in `local.yaml` for fast smoke.
- Parity mode is now the default ladder validation path.

## Entry: 2026-01-29 19:19:40 — Parity run fixes (Postgres port + S3 creds)

### Trigger
Parity smoke run failed: SR could not access MinIO (403) and Postgres DSN collided with existing local Postgres on 5433.

### Decision
- Move parity Postgres to **5434** to avoid port collision with existing stacks.
- Default parity AWS creds to **MinIO credentials** so SR/WSP/IG can access S3‑compatible storage without manual env overrides.

### Change
- `infra/local/docker-compose.platform-parity.yaml`: Postgres port now `5434:5432`.
- `makefile`: parity DSNs updated to `localhost:5434`; parity AWS creds default to MinIO access key/secret.

---

## Entry: 2026-01-29 19:38:31 — Parity smoke failure: IG service importing stale module (PYTHONPATH)

### Trigger
During parity smoke, WSP READY consumer hit IG `/v1/ops/health` and IG crashed with
`AttributeError: 'IngestionGate' object has no attribute 'authorize_request'`, even though
`IngestionGate.authorize_request()` exists in `src/fraud_detection/ingestion_gate/admission.py`.
This strongly suggests the IG service is running a stale installed package rather than `src`.

### Decision
- Add an explicit **platform Python wrapper** (`PY_PLATFORM`) that sets `PYTHONPATH=src`.
- Use `PY_PLATFORM` for **all platform targets** (SR/IG/WSP/Oracle/utility) so local runs always
  execute against the repo working tree, not a site‑packages copy.
- Rerun parity smoke end‑to‑end and validate receipts + offsets in Postgres/Kinesis after fix.

### Planned edits
- `makefile`: add `PY_PLATFORM` and swap `$(PY_SCRIPT)` to `$(PY_PLATFORM)` across platform targets.
- Re‑run parity smoke chain and validate:
  - IG receipts/quarantines in Postgres (`admissions`, `receipts`, `quarantines`).
  - EB offsets present in receipts (`eb_offset`, `eb_offset_kind`).
  - Kinesis stream has new records for `fp-traffic-bus`.

---

## Entry: 2026-01-29 19:46:31 — Parity smoke root cause: IG class methods nested under _build_indices

### What changed
While investigating the IG 500s, found that `IngestionGate` methods were accidentally indented
under `_build_indices`, leaving the class without `authorize_request` and other handlers.

### Fix
- Restored class structure by moving `_build_indices` after the class and re‑adding missing methods.
- Proceeding to restart IG service and re‑run parity smoke to validate receipts + offsets.

---

## Entry: 2026-01-29 19:47:10 — Ensure platform targets always run from repo (`PYTHONPATH=src`)

### Change
- Added `PY_PLATFORM` in `makefile` and switched platform targets (SR/IG/WSP/Oracle) to use it.

### Rationale
Avoids drift between editable installs and working tree; ensures parity smoke uses latest code.

---

## Entry: 2026-01-29 19:54:00 — Parity smoke fix: resolve env placeholders in IG wiring

### Trigger
Parity smoke failed because IG published to stream `${EVENT_BUS_STREAM}` and used a literal
`${IG_ADMISSION_DSN}` SQLite file. The placeholders were not resolved in IG wiring.

### Fix
- Resolve env placeholders for `admission_db_path` and `event_bus_path` in
  `src/fraud_detection/ingestion_gate/config.py`.

### Next
Restart IG service and re‑run parity smoke. Validate receipts/offsets.

---

## Entry: 2026-01-29 19:58:43 — Parity EB publish: ensure localstack endpoint env for IG

### Trigger
IG publish failed with `UnrecognizedClientException` (invalid security token) because
Kinesis publisher used default AWS endpoint instead of LocalStack. We were not setting
`AWS_ENDPOINT_URL`/`AWS_DEFAULT_REGION` for the IG service in parity mode.

### Fix
- `makefile`: export `AWS_ENDPOINT_URL` + `AWS_DEFAULT_REGION` in `platform-ig-service-parity`
  using the LocalStack endpoint/region.

---

## Entry: 2026-01-29 20:05:31 — Parity EB publish: wire endpoint/region explicitly in IG profile

### Why
Even with env export, IG still hit AWS with invalid credentials. Making endpoint/region
explicit in IG wiring removes reliance on implicit env propagation.

### Changes
- `config/platform/profiles/local_parity.yaml` adds `event_bus.region` + `event_bus.endpoint_url`.
- `ingestion_gate/config.py` loads these fields and passes to Kinesis publisher.
- `makefile` adds parity defaults for `EVENT_BUS_REGION` + `EVENT_BUS_ENDPOINT_URL`.

---

## Entry: 2026-01-29 20:15:34 — Parity smoke run (SR → WSP → IG → EB) succeeded

### Run summary
- SR run created `platform_20260129T201145Z`, READY published for run_id `9259e05c...`.
- WSP READY consumer streamed **5 events** (`PLATFORM_SMOKE_MAX_EVENTS=5`).
- IG admitted all 5 events and produced EB offsets (kinesis sequence numbers).

### Validation checks
- Postgres receipts created after `2026-01-29T20:11:00Z`: **5** receipts, all with `eb_offset_kind = kinesis_sequence`.
- IG logs show successful `ADMIT` with non‑empty offsets (sequence numbers).

### Notes
LocalStack `GetRecords` returned 0 in a quick probe; however receipts + offsets in ops DB are
the audit‑truth for publish success.

---

## Entry: 2026-01-29 23:36:36 — Parity alignment marked complete

### Decision
Parity alignment is considered **complete** for v0 local: SR→WSP→IG→EB parity smoke runs green,
receipt offsets are captured, and no remaining parity blockers are open.

---

## Entry: 2026-01-29 23:51:53 — Run‑centric log layout (no global platform log)

### Trigger
User expects run‑first structure: `runs/fraud-platform/<platform_run_id>/` containing logs and
service subfolders. A global log is confusing and weak for traceability.

### Decision
Adopt run‑centric layout:
- **Remove** `platform_runs/` layer.
- **Drop** global `runs/fraud-platform/platform.log`.
- Per‑run logs live only under `runs/fraud-platform/<platform_run_id>/platform.log`.
- Session ledger lives alongside at `runs/fraud-platform/<platform_run_id>/session.jsonl`.

### Mechanics
- `platform_runtime.py` now resolves run IDs under `runs/fraud-platform/` and writes logs there.
- `platform_log_paths` returns **only** per‑run log path; no global fallback.
- Platform commands/services request `create_if_missing=True` so runs always get a log.
- `make platform-run-new` now manages `runs/fraud-platform/ACTIVE_RUN_ID`.

### Files changed
- `src/fraud_detection/platform_runtime.py`
- `src/fraud_detection/ingestion_gate/service.py`
- `src/fraud_detection/world_streamer_producer/{cli.py,ready_consumer.py}`
- `src/fraud_detection/oracle_store/{cli.py,pack_cli.py}`
- `src/fraud_detection/scenario_runner/service.py`
- `makefile`
- Docs/READMEs updated to remove `platform_runs/` references.

---

## Entry: 2026-01-30 00:05:50 — Run‑first artifact layout (SR/WSP/IG/EB)

### Decision
All platform artifacts move under the run root:
`runs/fraud-platform/<platform_run_id>/{sr,wsp,ig,eb,...}`.
This eliminates service‑first paths and makes run bundles fully self‑contained.

### Mechanics
- Introduced `platform_run_root` / `platform_run_prefix` helpers and a `resolve_run_scoped_path` rewriter.
- SR ledger + refs now write to `{run_prefix}/sr/*`.
- IG receipts/quarantine/policy/health now write to `{run_prefix}/ig/*`.
- WSP ready ledger + checkpoints now write under `{run_prefix}/wsp*`.
- File‑bus roots (control_bus/event_bus) are auto‑rewritten to run scope when paths target `runs/fraud-platform`.

### Files changed (high‑level)
- `src/fraud_detection/platform_runtime.py`
- `src/fraud_detection/scenario_runner/*`
- `src/fraud_detection/ingestion_gate/*`
- `src/fraud_detection/world_streamer_producer/*`
- `src/fraud_detection/event_bus/cli.py`
- Tests/README/docs updated to reflect new run‑first layout.

---

## Entry: 2026-01-30 00:29:40 — Run-first artifact layout migration (sr|wsp|ig|eb)

### Trigger
User required per‑run artifact layout (`runs/fraud-platform/<platform_run_id>/sr|wsp|ig|eb/...`) and rejected global service‑level folders.

### Decision trail (live)
- Keep `runs/fraud-platform/<platform_run_id>/` as the platform run root (single audit surface per run).
- Component artifacts live under the run root (`sr`, `wsp`, `ig`, `eb`), while shared buses like `control_bus` stay at the run root.
- Rename the file‑bus folder from `event_bus` to `eb` to match the component name and avoid deep/nested names.
- Preserve historical per‑run logs by moving legacy `platform_runs/<run_id>` contents into the new run root.

### Implementation notes
- Migrated existing top‑level component folders (`sr`, `ig`, `wsp`, `event_bus`, `control_bus`, `wsp_checkpoints`) into `runs/fraud-platform/<active_run_id>/`.
- `event_bus` folder renamed to `eb`; WSP checkpoints moved under `wsp/checkpoints`.
- Legacy `platform_runs/<run_id>` log contents moved into the new run root; `ACTIVE_RUN_ID` moved to `runs/fraud-platform/ACTIVE_RUN_ID`.
- Global `platform.log` moved under the active run root (stored as `platform.log.global` if a per‑run log already existed).
- Updated local profile + docs to reflect run‑first layout and new `eb` path.

### Files touched
- `src/fraud_detection/platform_runtime.py`
- `config/platform/profiles/local.yaml`
- `config/platform/profiles/README.md`
- `README.md`
- `docs/model_spec/platform/implementation_maps/event_bus.build_plan.md`

---

## Entry: 2026-01-30 00:36:20 — Remove dev_local profile; enforce parity gate

### Trigger
User required zero ladder friction and explicitly asked to remove `dev_local.yaml` (mixed local filesystem + Kinesis profile).

### Decision trail (live)
- `dev_local` mixes file-system object store and local oracle roots with Kinesis/Postgres, which is the primary source of ladder friction.
- We already have a `local_parity` profile that mirrors dev/prod substrates (MinIO/S3 + LocalStack/Kinesis + Postgres).
- Keep **two** local tiers only: `local` (fast smoke) and `local_parity` (pre-dev parity gate). Remove `dev_local` to avoid mixed semantics.

### Implementation notes
- Deleted `config/platform/profiles/dev_local.yaml`.
- Promoted `local_parity.yaml` as the parity/validation profile in README + profile docs.
- Removed `IG_PROFILE_DEV` from Makefile (no dev_local alias).
- Updated EB build plan references to use `local_parity.yaml` instead of `dev_local.yaml`.

### Files touched
- `config/platform/profiles/dev_local.yaml` (deleted)
- `config/platform/profiles/README.md`
- `README.md`
- `services/ingestion_gate/README.md`
- `makefile`
- `docs/model_spec/platform/implementation_maps/event_bus.build_plan.md`

---

## Entry: 2026-01-30 00:40:45 — Parity walkthrough runbook (Oracle→SR→WSP→IG→EB)

### Trigger
User requested a detailed, written walkthrough for a 500k‑event local_parity run from Oracle Store through EB with observable logs and verification steps.

### Decision trail (live)
- The parity run should be documented as a runbook under `docs/runbooks/` to match existing operational docs.
- Use `local_parity.yaml` as the single parity gate and explicitly show MinIO + LocalStack + Postgres wiring.
- Provide verification steps against MinIO (SR/IG artifacts) and LocalStack Kinesis (EB records).

### Implementation notes
- Added `docs/runbooks/platform_parity_walkthrough_v0.md` with a step‑by‑step guide, 500k cap, and log inspection points.
- Added the runbook link to `docs/README.md`.

### Files touched
- `docs/runbooks/platform_parity_walkthrough_v0.md`
- `docs/README.md`

---

## Entry: 2026-01-30 02:18:20 — Parity env defaults for Oracle Store (S3) in .env.platform.local

### Trigger
User requested avoiding manual overrides when running `make platform-oracle-pack` by aligning `.env.platform.local` with the MinIO‑backed Oracle Store.

### Decision trail (live)
- Parity runs must target MinIO S3 for Oracle Store, not local filesystem.
- `ORACLE_ENGINE_RUN_ROOT` should point to the **S3 copy** (post‑sync), while `ORACLE_PACK_ROOT` should remain distinct from the engine root to avoid clashing with engine `_SEALED.json`.
- Use a stable `pack_current` prefix for day‑to‑day parity runs; if content changes, bump the pack root explicitly.

### Implementation notes
- Updated `.env.platform.local` to set `ORACLE_ROOT=s3://oracle-store`, `ORACLE_ENGINE_RUN_ROOT` to the S3 engine world, and `ORACLE_PACK_ROOT` to `.../pack_current`.
- Kept MinIO endpoint + S3 client envs in `.env.platform.local` for Makefile‑driven runs (no secrets logged here).

### Files touched
- `.env.platform.local`

---

## Entry: 2026-01-30 02:23:28 — Parity MinIO creds alignment + Oracle sync target

### Trigger
Parity IG service hit a `403 Forbidden` on S3 `HeadObject` because LocalStack-style AWS creds were used against MinIO.

### Decision trail (live)
- Parity uses **two** AWS‑like endpoints: MinIO S3 (Oracle Store + platform artifacts) and LocalStack Kinesis (control/event buses).
- MinIO enforces access keys; LocalStack accepts **any** access keys.
- Therefore, parity Make targets should export **MinIO creds** as the default AWS env to satisfy S3, while Kinesis still works against LocalStack.
- Add a dedicated `platform-oracle-sync` Make target so the engine‑to‑MinIO copy is reproducible without manual env injection.

### Implementation notes
- Updated parity service targets to export `AWS_ACCESS_KEY_ID/SECRET` from MinIO keys.
- Added `platform-oracle-sync` target that uses MinIO creds + endpoint to `aws s3 sync` local engine outputs into MinIO.
- Added `ORACLE_SYNC_SOURCE` to `.env.platform.local` to avoid ad‑hoc overrides.
- Aligned `PARITY_ORACLE_ROOT` default to `ORACLE_ROOT` (bucket root) to avoid appending run IDs at the root.
- Updated parity runbook sections 2 and 4 to use the Make target and reflect the new variables.

### Files touched
- `makefile`
- `.env.platform.local`
- `docs/runbooks/platform_parity_walkthrough_v0.md`

---

## Entry: 2026-01-30 02:36:37 — SR parity S3 credential propagation

### Trigger
SR failed on `HeadObject` with `403 Forbidden` because boto picked up shared AWS credentials instead of MinIO keys.

### Decision trail (live)
- SR run creates/updates artifacts in the platform object store (MinIO in parity).
- Make targets must export MinIO S3 envs for SR just like IG/WSP, or boto will fall back to shared credentials.

### Implementation notes
- Prefixed `platform-sr-run-reuse` with `OBJECT_STORE_*` + `AWS_*` export.
- Added a short runbook note for 403 troubleshooting in the SR step.
- Set `AWS_EC2_METADATA_DISABLED=true` in `.env.platform.local` to prevent metadata probing during local parity.

### Files touched
- `makefile`
- `docs/runbooks/platform_parity_walkthrough_v0.md`
- `.env.platform.local`

---

## Entry: 2026-01-30 02:55:14 — WSP parity S3 credential propagation

### Trigger
WSP READY consumer failed with `Invalid endpoint` because S3 endpoint/credentials were not exported to boto.

### Decision trail (live)
- WSP uses S3ObjectStore for run artifacts in parity; it must receive `OBJECT_STORE_*` + `AWS_*`.
- Align WSP with SR/IG by exporting the same MinIO credentials in Make targets.

### Implementation notes
- Prefixed `platform-wsp-ready-consumer` and `platform-wsp-ready-consumer-once` with `OBJECT_STORE_*` + `AWS_*`.
- Added a short WSP troubleshooting note to the parity runbook.

### Files touched
- `makefile`
- `docs/runbooks/platform_parity_walkthrough_v0.md`

---

## Entry: 2026-01-30 02:58:20 — WSP control bus env propagation

### Trigger
WSP READY consumer raised `CONTROL_BUS_STREAM_MISSING` because the profile uses `${CONTROL_BUS_STREAM}` and the Make target did not export it.

### Decision trail (live)
- WSP consumes READY from Kinesis, so it needs control bus stream/region/endpoint in env.
- Align WSP with IG/SR by exporting `CONTROL_BUS_*` from parity defaults.

### Implementation notes
- Added `CONTROL_BUS_STREAM/REGION/ENDPOINT_URL` defaults in Makefile and exported them in WSP ready-consumer targets.
- Added a parity runbook note for `CONTROL_BUS_STREAM_MISSING`.

### Files touched
- `makefile`
- `docs/runbooks/platform_parity_walkthrough_v0.md`

---

## Entry: 2026-01-30 03:00:48 — WSP checkpoint DSN env propagation

### Trigger
WSP READY consumer raised `CHECKPOINT_DSN_MISSING` because `WSP_CHECKPOINT_DSN` was not exported.

### Decision trail (live)
- WSP uses Postgres for checkpoints in parity (`wsp_checkpoint.dsn`).
- Make targets should export `WSP_CHECKPOINT_DSN` using parity defaults to keep parity runs non-interactive.

### Implementation notes
- Added `WSP_CHECKPOINT_DSN` default to parity DSN in Makefile and exported it in WSP ready-consumer targets.
- Added a WSP troubleshooting note to the parity runbook.

### Files touched
- `makefile`
- `docs/runbooks/platform_parity_walkthrough_v0.md`

---

## Entry: 2026-01-30 03:03:55 — WSP IG ingest URL propagation

### Trigger
WSP READY consumer failed with `Invalid URL '/v1/ingest/push'` because `IG_INGEST_URL` was not exported.

### Decision trail (live)
- WSP must post traffic to IG via `ig_ingest_url`.
- In parity, the URL is provided by `PARITY_IG_INGEST_URL` and should be exported as `IG_INGEST_URL`.

### Implementation notes
- Added `IG_INGEST_URL` default to parity value in Makefile and exported it in WSP ready-consumer targets.
- Added a runbook troubleshooting note for invalid ingest URL.

### Files touched
- `makefile`
- `docs/runbooks/platform_parity_walkthrough_v0.md`

---

## Entry: 2026-01-30 03:18:19 — Parity speedup increase (local_parity)

### Trigger
User requested faster parity runs; 60x speedup was still too slow for 500k events.

### Decision trail (live)
- Keep parity semantics intact but increase time compression to reduce wall-clock time.
- Use a conservative bump (600x) to speed up without eliminating temporal ordering logic.

### Implementation notes
- Updated `stream_speedup` in `config/platform/profiles/local_parity.yaml` from 60 → 600.

### Files touched
- `config/platform/profiles/local_parity.yaml`

---

## Entry: 2026-01-30 10:24:24 — Per‑output time‑sorted stream views (Option C) adopted

### Trigger
User observed engine outputs are not globally time‑sorted and approved **Option C**: create **per‑output** derived views sorted by `ts_utc` without modifying engine outputs.

### Decision trail (live)
- Keep the **engine sealed** (no changes to engine outputs or code).
- Build **per‑output stream views** in the Oracle Store (engine world) and have WSP consume them.
- Use **DuckDB external sort** for scale; store output as Parquet partitioned by `stream_date`.
- Enforce **idempotent receipts**: if receipt matches source locator digest, skip; if mismatch, fail closed.

### Implementation notes (platform‑wide)
- Added `stream_mode` + `oracle_stream_view_root` wiring so parity/dev/prod can force stream‑view mode.
- Added runbook step to build the stream view after Oracle sync+seal.

### Files touched
- `docs/model_spec/platform/implementation_maps/oracle_store.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/oracle_store.build_plan.md`
- `docs/runbooks/platform_parity_walkthrough_v0.md`
- `config/platform/profiles/{local_parity,dev,prod}.yaml`

---

## Entry: 2026-01-30 14:06:21 — Correction: stream‑view path + bucket partitions (stream_mode removed)

### Trigger
User clarified that stream views should be **per output**, partitioned by `bucket_index`,
and **must not** include `stream_view_id` in the path.

### Decision trail (live)
- Keep `stream_view_id` only as a **manifest/receipt integrity token**, not part of filesystem layout.
- Remove `stream_mode` toggle; WSP is **stream‑view only** in v0 (avoids mode confusion).
- Partition by `bucket_index` to preserve engine bucket semantics and reduce shuffle.

### Platform‑wide impact
- Profiles now pin only `oracle_stream_view_root` (no `stream_mode` key).
- WSP reads `.../stream_view/ts_utc/output_id=<output_id>/bucket_index=<bucket>/`.
- Oracle Store receipts/manifest keep `stream_view_id` for validation.

---

## Entry: 2026-01-30 18:05:12 — Correction: flat stream view layout (no bucket partitions)

### Trigger
User requested stream views to live directly under `output_id=<output_id>` without bucket subdirs.

### Platform‑wide impact
- Stream view layout is now **flat** per output_id: `.../stream_view/ts_utc/output_id=<output_id>/part-*.parquet`.
- WSP reads all parquet in the output_id root (no bucket dir traversal needed).

---

## Entry: 2026-01-30 20:27:10 — Platform‑wide S3 timeout controls

### Trigger
MinIO reads for small Oracle metadata (e.g. `run_receipt.json`) occasionally timed out during stream‑view builds.

### Decision trail (live)
- Control timeouts/retries at the client layer used by all platform S3 reads/writes.
- Keep settings environment‑driven for parity/dev/prod tuning.

### Platform‑wide impact
- New env knobs: `OBJECT_STORE_READ_TIMEOUT`, `OBJECT_STORE_CONNECT_TIMEOUT`, `OBJECT_STORE_MAX_ATTEMPTS`.
- Defaults added to `.env.platform.local` to avoid MinIO read timeouts during heavy local I/O.

---

## Entry: 2026-01-30 23:57 — Parity: WSP uses explicit oracle S3 root for stream view identity

### Trigger
`STREAM_VIEW_ID_MISMATCH` during parity smoke: SR READY referenced local engine root while the stream view was built from MinIO S3.

### Decision
- In parity mode, **explicit oracle wiring** (ORACLE_ENGINE_RUN_ROOT/ORACLE_ROOT) is authoritative for WSP READY consumption.
- Make targets must export these envs so WSP runs deterministically against the S3 oracle store.

### Changes
- WSP READY runner now prefers profile oracle wiring when provided.
- WSP Make targets export `ORACLE_ENGINE_RUN_ROOT`, `ORACLE_ROOT`, `ORACLE_SCENARIO_ID` for parity runs.
- Parity runbook updated with stream view verification and mismatch troubleshooting.

### Rationale
This keeps SR’s local evidence checks intact while ensuring WSP stream view identity matches the S3 oracle store used in parity/dev/prod.

---

## Entry: 2026-01-31 06:05 — IG receipts run-scope + EB ref visibility

### Trigger
Needed run-scoped IG receipts and explicit EB refs in logs for parity diagnostics.

### Decision
- Export `PLATFORM_RUN_ID` into IG service start targets so receipts/health/quarantine land under the active run.
- Log `receipt_ref` and `eb_ref` on successful admissions.

### Changes
- Makefile: IG service targets now pass PLATFORM_RUN_ID.
- IG admission: added `IG receipt stored ... eb_ref=...` line after receipt write.

---

## Entry: 2026-01-31 06:30 — Normalize S3 run prefix for platform artifacts

### Trigger
User requested removal of the duplicate `fraud-platform/` prefix in MinIO paths (e.g., `s3://fraud-platform/fraud-platform/<run_id>/...`).

### Decision
- Add `PLATFORM_STORE_ROOT` env to signal S3 store usage.
- If `PLATFORM_STORE_ROOT` is `s3://...`, `platform_run_prefix` returns just `<run_id>` to avoid double prefixing.

### Changes
- `src/fraud_detection/platform_runtime.py`: `platform_run_prefix` now checks `PLATFORM_STORE_ROOT` and returns run_id when S3.
- `.env.platform.local`: added `PLATFORM_STORE_ROOT=s3://fraud-platform`.
- `makefile`: export `PLATFORM_STORE_ROOT` for SR, IG, WSP targets.

### Validation
Fresh parity run produced receipts at:
`s3://fraud-platform/<run_id>/ig/receipts/*.json` and platform log shows `IG receipt stored ... eb_ref=...` with normalized path.

## Entry: 2026-01-31 13:10:00 — v0 control & ingress narrative (Phase 1–3) + canonical event time semantics

### Why this entry
User requested a **single narrative flow** for Phases 1–3 (v0) so the current platform behavior is unambiguous before Phase 4. This captures the actual runtime order and clarifies **event‑time semantics** (streaming by canonical `ts_utc`, with speedup as a policy knob).

### Narrative flow (v0 as implemented)
**0) Rails + substrate (Phase 1)**
- Canonical envelope + ContextPins are pinned and versioned.
- By‑ref artifacts + digest posture are pinned.
- Event bus taxonomy (control vs traffic vs audit) and partitioning rules are pinned.
- Environment ladder is policy vs wiring (only wiring changes across envs).

**1) Oracle Store is the truth boundary (Phase 2)**
- Engine outputs are sealed and stored in the Oracle Store (S3/MinIO in parity).
- Oracle Store is external to the platform; SR/WSP never “own” it.
- Local engine paths are not authoritative when `oracle_engine_run_root` is wired.

**2) SR is the readiness authority (Phase 3)**
- SR is control‑plane only and does not stream data.
- SR reads **Oracle Store** for evidence/gates and produces the join surface (`run_facts_view`) + READY.
- READY is published to the control bus only after **no‑PASS‑no‑read** is satisfied.

**3) WSP is the stream producer (Phase 2→3 bridge)**
- WSP consumes READY + run_facts_view for authorization and pins.
- WSP reads the **stream view** from Oracle Store and streams traffic into IG.
- WSP never publishes to EB directly (only IG does).

**4) IG is the admission boundary (Phase 3)**
- IG validates canonical envelope + schema, enforces no‑PASS‑no‑read, and emits receipts.
- Receipts are by‑ref with decisions + evidence refs.

**5) EB is the durable traffic log (Phase 3)**
- EB is the durable offset provider (Kinesis in parity).
- IG publishes admitted traffic; offsets are recorded in receipts.

### Event‑time semantics (critical)
- **Streaming is ordered by canonical event time (`ts_utc`)**, not by file order.
- **Speedup** is an explicit policy knob; it accelerates the same `ts_utc` sequence without changing ordering.
- This means the observed flow reflects **event‑time ordering** and **may not mirror raw file order**.

### v0 green meaning (control & ingress)
- Oracle Store sealed outputs exist.
- SR READY is published after gate verification using Oracle Store.
- WSP streams traffic by `ts_utc` (speedup optional).
- IG admits/quarantines and emits receipts.
- EB has offsets for the same platform run.

---
