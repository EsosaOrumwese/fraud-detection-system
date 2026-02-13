# Experience Evidence Bank (Fraud Detection System)

Status: Draft v2 from logbook + implementation-map scan.
Coverage used: `docs/logbook` from `2025-05-11` through `2026-02-11` (`208` daily log files).
Implementation-map coverage used:
- Data Engine: `10` segment implementation logs (`24,914` lines reviewed at signal level).
- Platform local_parity: `19` component implementation logs (`26,369` lines reviewed at signal level).
- Platform dev_substrate: `3` implementation logs (`2,349` lines reviewed at signal level).
Purpose: convert real project work into recruiter-ready evidence for UK 45k-50k GBP roles.

## 1) Project Scope You Can Claim Clearly
- Built and iterated a production-style fraud platform over ~9 months (active build from 2025 into 2026).
- Worked across system design, data contracts, runtime orchestration, reliability gates, cloud migration planning, and operational evidence.
- Operated in a contract-first, fail-closed architecture with explicit ownership boundaries and run-scoped provenance.

## 2) Evidence Categories (Recruiter-Facing)

### A. Product Ownership, Planning, and Delivery Management
What I did:
- Bootstrapped project governance from day one: charter, lifecycle plan, issue tracking, branch strategy, sprint posture.
- Ran phased implementation with explicit Definition-of-Done checklists and closure gates.
- Used living implementation maps and daily decision logs to keep design and execution auditable.

Logbook evidence snapshots:
- `2025-05-11`: repo/bootstrap planning, project charter, project management setup, CI quality gates.
- `2026-01-24`: progressive build-plan method and phased SR roadmap with DoD hardening.
- `2026-02-07` to `2026-02-11`: platform phase expansions, closure gates, and ordered remediation waves.

Recruiter signal:
- Can own ambiguity, sequence multi-phase delivery, and manage technical scope to closure.

### B. Architecture and System Design
What I did:
- Designed and enforced contract-first platform behavior (schemas, canonical envelopes, by-ref evidence).
- Modeled component boundaries and truth ownership (SR/IG/EB/Engine/DLA/etc.) and blocked drift with fail-closed decisions.
- Translated conceptual design docs into executable phased build plans for multiple components.

Logbook evidence snapshots:
- `2025-09-04`: state-validator design hardening, helper centralization, failure taxonomy alignment.
- `2026-02-07`: expanded DF/DL phased plans and implemented against explicit authority notes.
- `2026-02-10` to `2026-02-11`: architecture-level migration/settlement/oracle gate planning with explicit stop conditions.

Recruiter signal:
- Can reason at system level, not just write isolated scripts.

### C. Data Engineering and Data Contracts
What I did:
- Built and refreshed curated reference datasets with deterministic provenance (ISO, GDP, MCC, geospatial/timezone/population, merchant universe).
- Maintained dataset dictionary + artifact registry + schema alignment, including migration/correction when sources changed.
- Enforced deterministic pathing, run identity pinning, and manifest-linked evidence.

Logbook evidence snapshots:
- `2025-12-31`: large intake wave, provenance sidecars, schema/dictionary/registry updates, dependency ordering.
- `2026-01-01` onward: deep schema/contract audits and mismatch remediation backlog management.

Recruiter signal:
- Strong in data quality, reproducibility, and traceable data lifecycle management.

### D. MLOps / Platform Engineering
What I did:
- Built orchestration-ready tooling around scenario execution, readiness, gating, and evidence capture.
- Implemented run-scoped controls (idempotency posture, lease/store semantics, replay-safe behavior).
- Added operator frameworks (`preflight -> sync -> stream-sort -> validate`) with fail-closed output.

Logbook evidence snapshots:
- `2026-01-24`: SR storage and hardening phases with S3/Postgres parity setup.
- `2026-02-10`: run/operate hardening, active-run id resolution, full parity validation loops.
- `2026-02-11`: Oracle migration operator lanes, strict authority lock, stream-sort reliability fixes.

Recruiter signal:
- Can build runtime substrate and operational rails, not just ML notebooks.

### E. Cloud and Infrastructure (AWS + Terraform)
What I did:
- Managed dev-min substrate lifecycle with Terraform-driven plan/up/down/down-all flows.
- Controlled cost/risk posture via explicit gates (`AllowPaidApply`, `AllowPaidDestroyAll`) and runtime cost decisions.
- Implemented role-aware S3 versioning policy (object-store vs evidence/state trade-offs).

Logbook evidence snapshots:
- `2026-02-10`: phase2 infra controls, parity substrate validation, runbook-hardening.
- `2026-02-11`: S3 bucket cleanup/versioning implications and migration operations.
- Current session change: role-aware versioning defaults + fail-closed env override validation.

Recruiter signal:
- Can operate cloud resources with cost awareness and safety controls.

### F. Reliability, Testing, and Quality Gates
What I did:
- Established quality baseline early: pre-commit, linting, unit tests, CI checks.
- Added targeted regression tests with each fix wave across multiple services.
- Used fail-closed validation style: unknown/missing contracts block progression.

Logbook evidence snapshots:
- `2025-05-11`: pre-commit + GitHub Actions setup.
- `2026-01` and `2026-02`: repeated component test sweeps (DL/DF/AL/DLA/IG/OFP/CSFB/SR), parity matrix checks, runtime evidence verification.

Recruiter signal:
- Strong engineering hygiene, not "works on my machine" delivery.

### G. Incident Response and Deep Debugging
What I did:
- Diagnosed cross-component runtime faults under live-like runs (offset handling, checkpoint drift, SQL placeholder mismatches, replay start-position starvation, observability miscounts).
- Implemented targeted fixes, added tests, reran bounded/full streams, and recorded closure evidence.
- Performed root-cause-first remediation sequencing to reduce collateral regressions.

Logbook evidence snapshots:
- `2026-02-08`: RTDL drift closures (schema version emission, IG fail-fast guards, SQL identifier and replay/start-position fixes).
- `2026-02-09`: multi-wave P0/P1/P2 closure with evidence-backed reruns.
- `2026-02-11`: DuckDB S3 credential bridge fix after sync-pass/stream-sort-fail pattern.

Recruiter signal:
- Can troubleshoot production-like systems systematically.

### H. Observability, Governance, and Auditability
What I did:
- Built/maintained run-scoped evidence artifacts and governance traces across components.
- Enforced provenance fields and policy stamps for downstream replay/audit posture.
- Normalized run reporting to active run IDs to prevent stale evidence scope.

Logbook evidence snapshots:
- `2026-02-08` to `2026-02-10`: run report + governance + conformance alignment fixes.
- Multiple entries in platform impl logs tying evidence to explicit run IDs and scenario IDs.

Recruiter signal:
- Understands regulated/auditable data-system operating models.

### I. Documentation and Technical Communication
What I did:
- Maintained large technical documentation surface: runbooks, build plans, implementation maps, contracts/readmes.
- Wrote decision trails with rationale, alternatives, and validation outcomes.
- Kept docs synchronized with actual runtime behavior and tooling interfaces.

Logbook evidence snapshots:
- Consistent across `2025-09`, `2025-12`, `2026-01`, and `2026-02` with pre-change and post-change entries.

Recruiter signal:
- Can communicate complex engineering work clearly to teams/stakeholders.

### J. AI-Assisted Engineering Workflow (Human-in-the-Loop)
What I did:
- Used AI coding assistance to accelerate implementation and analysis while retaining human ownership of technical decisions.
- Worked in a disciplined prompt -> design -> patch -> validate -> evidence cycle.
- Preserved verification responsibility via tests, run outputs, and explicit decision logs.

Recruiter signal:
- Modern engineering workflow literacy with strong judgment and quality control.

## 3) Timeline of Progression (High-Level)

### Phase 1: Engineering Foundation (May-Jun 2025)
- Repo initialization, project charter, branch/process setup.
- Pre-commit + CI checks established.
- Early simulation/data-generator improvements began.

### Phase 2: Contract and Determinism Discipline (Jul-Nov 2025)
- Expanded state-level design and validation posture.
- Consolidated helper layers to reduce drift and ambiguity.
- Hardened gate semantics and schema authority alignment.

### Phase 3: Data Intake and Provenance Expansion (Dec 2025)
- Built deterministic external-data intake pipeline with sidecar provenance.
- Managed schema/dictionary/registry contract updates.
- Added LFS discipline for large artifacts.

### Phase 4: Platformization and Runtime Hardening (Jan-Feb 2026)
- Implemented SR storage/hardening and local parity stack.
- Expanded and implemented DL/DF phases with tests and closure checks.
- Ran full parity validation loops and fixed cross-component runtime blockers.
- Advanced dev-substrate migration planning and Oracle authority tooling.

## 4) Tooling Evidence Map
- Languages: Python, SQL, YAML/JSON schema contract work, shell scripting (PowerShell/Bash).
- Data stack: Parquet workflows, DuckDB, Polars, provenance sidecars.
- Infra/Cloud: AWS S3-focused workflows, Terraform env lifecycle management, cost/safety gates.
- Runtime/Stores: Postgres + SQLite parity patterns, object-store semantics.
- Integration/Streaming context: event-bus orchestration patterns, run-scoped replay/offset controls.
- Quality: pytest-driven regressions, pre-commit checks, CI gates, fail-closed validation flows.
- Ops: Makefile automation, preflight scripts, run reports, observability/gov evidence outputs.

## 5) Roles This Evidence Supports (45k-50k GBP band)
- Data Engineer (strong fit)
- MLOps Engineer / Platform Engineer (strong fit)
- Applied Data Scientist with production engineering ownership (fit if role values systems delivery)

## 6) Resume Bullet Bank (Ready to Tailor)
- Built a contract-first fraud platform workflow with fail-closed gates and run-scoped evidence, improving reproducibility and auditability across ingestion, decisioning, and observability paths.
- Implemented multi-phase platform migration rails from local parity to managed substrate with explicit preflight, sync, stream-sort, and validation steps.
- Designed and enforced deterministic identity/provenance mechanics (run IDs, scenario scope, policy digests, by-ref evidence) across component boundaries.
- Diagnosed and remediated cross-service runtime failures (schema mismatches, checkpoint drift, SQL placeholder incompatibilities, replay start-position starvation) with targeted regression tests.
- Built and validated local parity runtime stacks (S3-compatible object store + Postgres) for scenario runner hardening and integration verification.
- Authored and maintained living build plans and implementation maps with decision rationale, alternatives, validation outcomes, and closure criteria.
- Automated infra lifecycle controls with Terraform and guard-railed run commands to reduce accidental paid operations and unsafe teardown behavior.
- Implemented role-aware S3 versioning posture to reduce object-store cost growth while preserving evidence/state durability requirements.
- Constructed deterministic data intake/provenance pipelines for core reference assets (ISO, GDP, MCC, geospatial/timezone/population, merchant universe) and aligned contracts accordingly.
- Established quality baseline via pre-commit + CI gates and sustained high test coverage through iterative platform hardening waves.

## 7) Gaps To Fill Next (for stronger recruiter conversion)
- Add 2-3 quantitative impact metrics tied to runtime outcomes (lead time reduction, MTTR, test throughput, incident recurrence reduction).
- Add one concise architecture diagram for portfolio presentation.
- Prepare 3 interview stories (incident, migration, architecture trade-off) with STAR format.

## 8) Notes on This Pass
This draft now includes a second-pass extraction from implementation maps, not just daily logbooks.
It should be treated as an evidence bank, not the final CV wording.

## 9) Deep Evidence by Component Family

### A. Data Engine Segment Delivery (High-Signal Evidence)
- Worked across ten major segment tracks (`1A`, `1B`, `2A`, `2B`, `3A`, `3B`, `5A`, `5B`, `6A`, `6B`) with explicit state-by-state planning and implementation logs.
- Repeatedly enforced deterministic/fail-closed laws: `no PASS -> no read`, sealed input universes, strict schema anchor validation, atomic publish, idempotent re-run behavior, deterministic ordering keys.
- Resolved real contract mismatches (dictionary/registry/schema anchor drift) and corrected packaging/index issues instead of bypassing checks.
- Built evidence-heavy gate posture: gate-in receipts, sealed input manifests, final bundle gates, and deterministic digest links across upstream/downstream segments.

### B. Oracle Store Engineering (local_parity -> dev_substrate bridge)
- Designed Oracle as an engine-rooted truth boundary with platform as strict consumer (ownership boundary correction explicitly documented and enforced).
- Built and hardened checker + packer mechanics: strict seal checks, write-once manifest/seal semantics, stable reason codes, schema-validated manifests/receipts.
- Implemented S3-native stream-sort pipeline via DuckDB with idempotent receipt checks and fail-closed behavior on partial/mismatched states.
- Added operational quality improvements: progress visibility, ETA logs, memory/thread/temp tuning knobs, and credential-bridge fixes for DuckDB S3 reads in managed runs.

### C. Scenario Runner Engineering (control-plane authority)
- Implemented deterministic run identity (`run_id`, `attempt_id`) and explicit run truth surfaces (`run_plan`, `run_record`, `run_status`, `run_facts_view`, READY signal).
- Enforced strict commit ordering and idempotency semantics (facts committed before READY publication; append-only event histories).
- Hardened durable authority surfaces (lease/idempotency stores with SQLite/Postgres parity behavior).
- Extended SR for WSP-era coupling with `oracle_pack_ref` and run identity pins (`platform_run_id`, `scenario_run_id`, `run_config_digest`) and READY idempotency keying.

### D. Platform local_parity Hardening
- Built parity-first runtime posture (MinIO/S3-compatible + Postgres + control-bus local stack), then fixed real integration issues until end-to-end C&I flows were green.
- Migrated to run-first artifact layout and standardized run-scoped logging/evidence paths for replay and audit coherence.
- Drove multi-plane closure waves with targeted matrices and regressions (examples in logs include OFP and MF waves with `48+`, `53+`, and `55+` passing test sets in single runs).

### E. Platform dev_substrate Migration Work
- Structured migration as phased execution with explicit closure gates (`Phase 0` to `Phase 3.C`), not ad hoc environment edits.
- Implemented substrate preflights and operator rails (Terraform lifecycle, bootstrap checks, cost sentinel behavior, run evidence generation).
- Delivered Oracle `3.C.1` operator framework (`preflight -> sync -> stream-sort -> validate`) with strict fail-closed evidence and clear terminal progress behavior.
- Delivered SR `3.C.2` early implementation gates (`S1` settlement lock, `S2` Oracle scope + by-ref checks) while preserving full-migration managed-only posture.

## 10) Concrete Credibility Metrics You Can Use
- Maintained an auditable execution history across `208` daily engineering logbook files.
- Operated across `32` implementation-map tracks (`10` data-engine + `19` local_parity + `3` dev_substrate).
- Worked through >`53,000` lines of implementation-decision records (`24,914` engine + `26,369` local_parity + `2,349` dev_substrate) as traceable planning/execution evidence.
- Repeatedly produced closure evidence with explicit PASS/fail-closed outcomes, not implicit "it should work" status.

## 11) Stronger CV Positioning Angle (45k-50k GBP)
- Primary narrative: "Production-minded data/platform engineer who can design, implement, and harden deterministic, auditable systems under strict contracts."
- Supporting narrative: "Not just modeling; owns reliability, contracts, orchestration, cloud migration rails, and incident/debug loops."
- Best-fit role keywords:
  - Data Engineer (platform/data contracts/reproducibility)
  - MLOps Engineer (runtime gates/orchestration/observability)
  - Platform Engineer (migration/cost controls/reliability posture)
