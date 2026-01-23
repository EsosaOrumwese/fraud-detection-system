# Closed-World Enterprise Fraud Platform — Concept Overview

> **Status:** Data Engine specs sealed; implementation complete; final full-run validation in progress.  
> **Mission:** Build a bank-grade, closed-world fraud platform. All data (train/test/stream/labels) comes **only** from the **Data Engine**. No third-party enrichment. Everything is governed by contracts, lineage, validation gates, and reproducible runs.
> *Refer to `docs/references/closed-world-synthetic-data-engine-with-realism-conceptual-design.md` for more information*

---

## Quick TL;DR
- **Closed world:** the Data Engine is the single source of truth.  
- **Contracts-first:** JSON-Schema is the authority; consumers must pass validation (**no PASS → no read**).  
- **Reproducible:** every run is identified by `{ seed, parameter_hash, manifest_fingerprint }`.  
- **Black-box interface:** platform components integrate via `docs/model_spec/data-engine/interface_pack/` (catalogue + gate map + boundary schemas).  
- **Two feature planes:** online (low-latency, freshness SLOs) and offline (training/replay) with **identical transforms**.  
- **Decision fabric:** guardrails → primary ML → optional 2nd stage; returns **ACTION + reasons + provenance** with a **degrade ladder** to keep latency SLOs.  
- **Auditability:** immutable decision log + label store; deterministic replay/DR from lineage.

### Current build status (2026-01-23)
| Segment | States | Status | Notes |
|---------|--------|--------|-------|
| 1A | S0-S9 | **Implemented** | Authority surface for downstream segments |
| 1B | S0-S9 | **Implemented** | Production-ready Layer-1 world realism |
| 2A | S0-S5 | **Implemented** | Gate, TZ pipeline, timetable, legality, bundle |
| 2B | S0-S8 | **Implemented** | Alias build, router core, audits, PASS bundle |
| 3A | S0-S7 | **Implemented** | Layer-1 cross-zone merchants; PASS bundle and `_passed.flag_3A` emitted |
| 3B | S0-S5 | **Implemented** | Layer-1 virtual merchants & CDN; PASS bundle and `_passed.flag_3B` emitted |
| 5A | S0-S5 | **Implemented** | Layer-2 arrival surfaces & calendar |
| 5B | S0-S5 | **Implemented** | Layer-2 arrival realisation (LGCP + routing) |
| 6A | S0-S5 | **Implemented** | Layer-3 entity & product world |
| 6B | S0-S5 | **Implemented** | Layer-3 behaviour & fraud cascades |

Current focus: full end-to-end validation run across 1A.S0 → 6B.S5.

### Spec sources (repo layout)
- **Layer-1** - `docs/model_spec/data-engine/layer-1/.` holds all Layer-1 narratives, contracts, and state-flow docs (Segments 1A-3B) - **sealed**.
- **Layer-2** - `docs/model_spec/data-engine/layer-2/.` mirrors the same structure for Segments 5A/5B - **sealed**.
- **Layer-3** - `docs/model_spec/data-engine/layer-3/.` carries Segments 6A/6B - **sealed**.

All layers reference upstream authorities explicitly (via schemas, dataset dictionaries, and artefact registries); no ad-hoc paths.

### Black-box integration (platform-facing)
Use the interface pack (no segment/state internals):
- `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
- `docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`
- `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml`

---

## Concept Map
```
                            CLOSED-WORLD ENTERPRISE FRAUD PLATFORM — DETAILED ASCII MAP
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ CROSS-CUTTING RAILS:  CONTRACTS • LINEAGE • VALIDATION • PRIVACY/SECURITY • SLOs/OBSERVABILITY                           │
│ JSON-Schema is authority · no PASS→no read · parameter_hash + manifest_fingerprint · deterministic replay · RBAC & KMS   │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────┐          drives            ┌──────────────────────────────────────────┐        sidecars (not in flow)
   │   SCENARIO RUNNER    │ =========================> │               DATA ENGINE                │ ===============================┐
   │ (traffic & campaigns)│                            │ L1: world/merchant realism  (1A..3B)     │                                │
   │ rate/seed/manifest   │                            │ L2: temporal arrivals       (2A..)       │                                │
   │ controlled replays   │                            │ L3: fraud flows/dynamics    (3A..)       │                                │
   └──────────────────────┘                            │ 4A/4B: reproducibility & validation      │                                │
                                                       │ sealed, deterministic, lineage-anchored  │                                │
                                                       └────────────┬─────────────────────────────┘                                │
                                       emits canonical tx + lineage │                                                              │
                                                                    ▼                                                              ▼
                                                         ┌───────────────────────┐                                      ┌────────────────────────────┐
                                                         │     INGESTION GATE    │                                      │ AUTHORITY SURFACES (RO)    │
                                                         │ schema+lineage verify │                                      │ sites • zones/DST • order  │
                                                         │ idempotent • tokenize │                                      │ civil-time legality        │
                                                         └────────────┬──────────┘                                      │ lineage anchors (read-only)│
                                                                      │                                                 └────────────────────────────┘
                                                                      ▼
                                             (contract-checked stream; lineage preserved)
                                                         ┌───────────────────────┐
                                                         │       EVENT BUS       │  (e.g., Kinesis)
                                                         └────────────┬──────────┘
                                      features (low latency)          │                       features+labels (batch parity)
      ┌───────────────────────────────────────────┐                   │                 ┌────────────────────────────────────────┐
      │        ONLINE FEATURE PLANE               │                   │                 │        OFFLINE FEATURE PLANE           │
      │ counters, windows, trust, TTL/freshness   │◄──────────────────┘                 │ same transforms • same schemas         │
      │ p95-safe reads (DynamoDB)                 │                                     │ dataset assembly for train/replay (S3) │
      └───────────────┬───────────────────────────┘                                     └───────────────────────┬────────────────┘
                      │                                                                                         │
                      ▼                                                                                         ▼
            ┌─────────────────────────────┐                                              ┌──────────────────────────────┐
            │ IDENTITY & ENTITY GRAPH     │◄──────────────── stream updates ─────────────│      DECISION LOG & AUDIT    │
            │ link device/person/account  │                                              │  STORE (immutable, queryable)│
            │ mule rings • collusion      │                                              │ inputs • features • versions │
            └──────────────┬──────────────┘                                              │ explanations • timings       │
                           │ features                                                    └───────────────┬──────────────┘
                           ▼                                                                             │
                 ┌───────────────────────────────┐                                                       │
                 │        DECISION FABRIC        │ <========= metrics & labels feedback =================┘
                 │ 1) guardrails (cheap)         │ ---------------- deploy bundles -------------------->  ┌───────────────────────────┐
                 │ 2) primary ML (calibrated)    │                                                        │   MODEL/POLICY REGISTRY   │
                 │ 3) optional 2nd stage         │                                                        │ bundles in S3 + pointers  │
                 │ reasons + provenance (signed) │                                                        │ in DynamoDB (immutable)   │
                 └──────────────┬────────────────┘                                                        └──────────────┬────────────┘
                                │ decisions                                                                     registry │/deploy
          ┌─────────────────────┴────────────────────┐                                                          ┌────────▼────────────┐
          │               ACTIONS LAYER              │                                                          │     MODEL FACTORY   │
          │ APPROVE • STEP-UP • DECLINE • QUEUE      │                                                          │ train • eval • pkg  │
          │ idempotent • audited (gateway sim)       │                                                          │ shadow→canary→ramp  │
          └──────────────┬──────────────┬────────────┘                                                          └─────────────────────┘
                         │ outcomes     │ queued cases
                         ▼              ▼
               ┌──────────────────┐   ┌───────────────────────────┐
               │   LABEL STORE    │   │ CASE MGMT / WORKBENCH     │
               │ fraud/FP/disputes│   │ queues • playbooks • links│
               │ lagged states    │   └───────────────────────────┘
               └──────────────────┘

                                ┌─────────────────────────────────────────────────────────────────────────────────────────┐
                                │                         DEGRADE LADDER (automatic)                                      │
                                │ skip 2nd stage → use last-good features → raise STEP-UP → rules-only (keep SLOs)        │
                                └─────────────────────────────────────────────────────────────────────────────────────────┘


      ┌──────────────────────────────────────────────────────── RUN / OPERATE PLANE (AWS-oriented) ────────────────────────────────────────────────────┐
      │ Orchestrate: Airflow (MWAA) DAGs → ECS Fargate tasks (engine runs, training, deploy, replay)                                                   │
      │ Containers: ECR images per service (engine, scoring, replayer, feature updaters); healthchecks; blue/green                                     │
      │ Storage: S3 (KMS) for lake + bundles • DynamoDB for online features & registries • RDS/Aurora for cases/audits                                 │
      │ Bus: Kinesis streams (contract-checked puts) • Secrets: Secrets Manager/SSM • Access: least-privilege IAM                                      │
      │ Engine Run Registry: manifests (seed, params, git, digests) • Engine State Registry: DAG of layers/subsegments/states                          │
      └────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘


┌───────────────────────────────────────────────────────────────────── OBSERVABILITY & GOVERNANCE ───────────────────────────────────────────────────┐
│ Golden signals: latency p50/95/99, TPS, error rates, saturation • Data health: schema errors, nulls, volume deltas, lineage mismatches             │
│ Feature freshness & train/serve skew • Model drift & decision-mix deltas • Corridor checks (synthetic probes) • Replay/DR from manifests           │
│ Change control: contract tests in CI, determinism checks (re-run & byte-diff), dual read/write on risky paths • Security: encryption, redaction,   │
│ retention policies • Audit: every decision carries {manifest_id, feature_view_hash, model/policy versions, reasons, timings}                       │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Legend (compact):
• (RO) authority = read-only truth surfaces (never re-derived) • arrows = data/control flow • sealed = closed-world, engine-only data
```

---

## How a day runs (execution flow)
1. **Scenario Runner → Data Engine.** Emits production-shaped transactions, labels, and **authority surfaces** (sites/zones/DST/order) with lineage.  
2. **Ingestion Gate.** Verifies schema + lineage, enforces idempotency, and tokenizes sensitive fields by default.  
3. **Event Bus.** Broadcasts the contract-checked stream; lineage is preserved end-to-end.  
4. **Features (two planes, one truth).**  
   - **Online:** low-latency windows/counters with freshness SLOs.  
   - **Offline:** same transforms/schemas for training and replay; every decision references a **feature snapshot hash**.  
5. **Decision Fabric.** Guardrails → primary ML → optional 2nd stage; returns **ACTION + reasons + provenance**.  
6. **Actions & side effects.** Approve / Step-up / Decline / Queue are **idempotent** and audited.  
7. **Label Store.** Internal outcomes (immediate + delayed) produce rigorous labels inside the closed world.  
8. **Model Factory & Registry.** Train/evaluate → register immutable bundles → **shadow → canary → ramp** with clear rollback.  
9. **Observability & Governance.** Golden signals, data health, drift, contract tests in CI, and deterministic replays from manifests.

---

## Core tenets
- **JSON-Schema authority.** Schemas live in `contracts/`; code does not redefine fields.  
- **No PASS → no read.** Producers publish a validation bundle `_passed.flag`; consumers must check it.  
- **Lineage anchors.**  
  - `parameter_hash` — governed parameters that define a run’s semantics.  
  - `manifest_fingerprint` — digest of **everything opened** (incl. git tree + artefacts).  
- **Determinism & replay.** Strict RNG mapping; counters/trace envelopes; reproducible runs keyed by `{seed, parameter_hash, manifest_fingerprint}`.  
- **Separation of concerns.** (suggestion not binding) 
  - emitters (schema-bound I/O)  
  - pure kernels  
  - orchestrators  
  - validators (read-only proofs)

---

## Components at a glance
- **Data Engine (L1→L3 + 4A/4B).** Generates canonical ledgers, labels, and authority surfaces; publishes validation bundles.  
- **Ingestion Gate.** First write path; schema + lineage checks; idempotency; tokenization.  
- **Event Bus.** Contract-checked stream for real-time consumers.  
- **Identity & Entity Graph.** Deterministic linking (people/devices/accounts/merchants) and cluster features.  
- **Feature planes.** Online (low-latency; freshness SLOs) and offline (training/replay) with identical logic.  
- **Decision Fabric.** Rules + ML with explanations & provenance; **degrade ladder** to preserve latency SLOs.  
- **Actions Layer.** Idempotent approvals/declines/step-ups/queues; audited.  
- **Label Store.** Ground truth inside the sealed world (fraud/FP/dispute; timing lags modeled).  
- **Decision Log & Audit Store.** Immutable, queryable record of inputs, feature snapshot, versions, action, explanations, timings.  
- **Model Factory & Registry.** Trains/evaluates; registers immutable bundles; resolves **active/canary** for deployment.  
- **Operate/Run plane.** Orchestration of jobs/services; containerized workloads; least-privilege access; secrets outside code.

---

## Authority boundaries (never re-derived downstream)
- **Country order** and **domestic outlet counts `N`** come from the location-realism authority tables (not file order).  
- **Foreign target `K_target`** is fixed by its sampler; realization/capping is downstream, but **order remains upstream**.  
- **Civil time legality** (zone/offset/DST) is an upstream authority; runtime only validates.

---

## SLO envelope & degrade policy (design targets)
- End-to-end decision latency protects a strict p99 budget.  
- Automatic degrade: **skip 2nd stage → use last-good features → raise STEP-UP → rules-only**, while keeping auditability.

---

## Interfaces (high-level contracts)
> Canonical shapes; exact schemas live in `contracts/`.

- **Scoring API (Decision Fabric)**  
  `POST /score` → `{ action, score, reasons[], model_version, policy_version, manifest_id, feature_view_hash, latency_ms }`

- **Replayer → Bus**  
  messages include `{ manifest_id, scenario_id, seq_no, idempotency_key }`

- **Model/Policy Registry (read-only)**  
  `GET /bundles/active/scoring` → `{ model_uri, policy_uri, checksum, promoted_at }`

- **Decision Log row**  
  `{ ts, tx_id, entity_ids, features_hash, model_version, policy_version, action, reasons, latency_ms, manifest_id }`

- **Run manifest**  
  `{ fingerprint, seed, parameter_hashes[], git_tree, artefact_digests, created_at }`

---

## Current scope & reading order
- **Current focus:** Data Engine - **Layer-1 / Segment 3A (spec + pre-implementation)**; Segments 1A, 1B, 2A & 2B are sealed authority surfaces feeding downstream work.  
- **Reading order:** `contracts/` → `packages/engine/` → `services/` (concept) → `orchestration/` (concept).  
- **Promotion path:** when a service becomes real, it graduates from `services/<name>/` (docs) to `packages/svc-<name>/` (its own package).

---

## Repository layout
```text
fraud-enterprise/
├─ packages/
│  └─ engine/
│     ├─ pyproject.toml
│     └─ src/engine/
│        ├─ cli/
│        ├─ registry/
│        ├─ core/
│        ├─ validation/
│        ├─ scenario_runner/
│        └─ layers/
│           └─ l1/seg_1A/...   # representative tree (s0_foundations, s1_hurdle, …)
│  # add more packages later (e.g., packages/svc-decision-fabric, packages/lib-shared)
│
├─ services/
│  ├─ ingestion/README.md
│  ├─ feature_online/README.md
│  ├─ decision_fabric/README.md
│  ├─ replayer/README.md
│  ├─ model_registry/README.md
│  └─ consumer_gate/README.md
│
├─ shared/README.md
├─ contracts/
│  ├─ schemas/
│  ├─ dataset_dictionary/
│  └─ policies/
│
├─ docs/
│  ├─ model_spec/
│  │  └─ data-engine/
│  │     ├─ README.md
│  │     ├─ AGENTS.md
│  │     ├─ layer-1/
│  │     │  ├─ README.md / AGENTS.md
│  │     │  ├─ narrative/, deprecated__assumptions/
│  │     │  └─ specs/…
│  │     └─ layer-2/
│  │        ├─ README.md / AGENTS.md
│  │        └─ specs/state-flow|contracts/{5A,5B}/
│  └─ engineering-decisions/
│
├─ orchestration/
├─ infra/
├─ config/
├─ artefacts/
├─ tests/
├─ scripts/
├─ runs/
└─ examples/
```


---

## Glossary
- **Closed world** — all data (train/test/stream/labels) is produced internally by the Data Engine.  
- **Validation bundle / `_passed.flag`** — proof that a dataset/run passed structural & corridor checks.  
- **`parameter_hash`** — digest of governed parameter sets that define run semantics.  
- **`manifest_fingerprint`** — digest of everything the run opened (incl. git tree and artefacts).  
- **Degrade ladder** — automatic path to meet SLOs under pressure (skip 2nd stage → last-good features → STEP-UP → rules-only).

---

> **Note:** This README describes the **destination**. Many folders are intentionally **conceptual** until unlocked. The **Data Engine** now has Layer-1 Segments 1A–3B sealed and deterministic; the next build frontier is Layer-2 (Segments 5A then 5B) once unlocked.

## Data Engine Progress

```
============================ DATA ENGINE (progress) ============================
[ Merchant-Location Realism ] | [ Arrival Mechanics ]            | [ Flow Dynamics ]
            [  ONLINE  ]      | [ SPECS SEALED - NEXT UP ]      | [ SPECS SEALED - NEXT UP ]

                  ^ implementation focus: 5A/5B and 6A/6B
-------------------------------------------------------------------------------
| 4A Reproducibility + 4B Validation = CROSS-CUTTING (baked into every box)   |
| VALIDATION HARNESS: ON FROM DAY 0 (spans all layers; not a tail-end step)   |
-------------------------------------------------------------------------------
```

```
=========== Merchant-Location Realism (open) ===========
Sub-segments:
  1A  Merchants → Physical Sites  ............. [ ONLINE ]
  1B  Place Sites on Planet ................... [ ONLINE ]
  2A  Civil Time Zone (IANA/DST) .............. [ ONLINE ]
  2B  Routing Through Sites ................... [ ONLINE ]
  3A  Cross-Zone Merchants .................... [ BUILDING ]
  3B  Purely Virtual Merchants ................ [ LOCKED ]

[4A/4B overlay]  >>> applied to every sub-segment above (inputs/outputs, RNG,
                   manifests, schema checks, and per-state validation gates)
```

```
=========== 1A state-flow (10 states; live) ===========
S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S9

Where (short labels just to anchor the flow):
S0 Prep      S1 Hurdle     S2 Domestic N   S3 X-border gate   S4 Foreign K
S5 Weights   S6 Select K   S7 Allocate N   S8 Egress/IDs      S9 Replay+Gate


=========== 1B state-flow (10 states; live) ===========
S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S9

Where (short labels just to anchor the flow):
S0 Gate 1A bundle       S1 Country tiling          S2 Tile priors
S3 Derive site counts   S4 Integerise shares       S5 Pick cells (RNG)
S6 Jitter points (RNG)  S7 Synthesize sites        S8 `site_locations`
S9 Validation bundle


=========== 2A state-flow (6 states; live) ===========
S0 -> S1 -> S2 -> S3 -> S4 -> S5

Where (short labels just to anchor the flow):
S0 Gate & Sealed Inputs        S1 Provisional TZ Lookup       S2 Overrides & Finalisation
S3 Timetable Cache             S4 Legality Report             S5 Validation Bundle


=========== 2B state-flow (9 states; live) ===========
S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8

Where (short labels just to anchor the flow):
S0 Gate & Sealed Inputs        S1 Site Weights                S2 Alias Tables
S3 Day Effects (γ draws)       S4 Group Weights (Σ=1)         S5 Router Core (group→site)
S6 Virtual Edge Routing        S7 Audits & CI Gate            S8 Validation Bundle & `_passed.flag`


=========== 3A state-flow (8 states; specs sealed) ===========
S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7

Where (short labels just to anchor the flow):
S0 Gate & Sealed Inputs        S1 Mixture Policy & Escalation Queue
S2 Dirichlet Priors            S3 Zone Share Draws (Dirichlet)
S4 Integerise w/ Floors & Bump S5 Bind Allocation + Universe Hash
S6 Structural Validation       S7 Validation Bundle & `_passed.flag`


=========== 3B state-flow (6 states; specs sealed) ===========
S0 -> S1 -> S2 -> S3 -> S4 -> S5

Where (short labels just to anchor the flow):
S0 Gate & Sealed Inputs        S1 Virtual ID + Settlement Node
S2 CDN Edge Catalogue (HRSL)   S3 Alias Tables & Universe Hash
S4 Dual-TZ Routing Policy + CI S5 Validation Bundle & `_passed.flag`


Legend:
[OPEN]   = exposed/being worked
[LOCKED] = not yet opened to define
4A/4B    = reproducibility + validation, cross-cutting across all boxes/states
```

```markdown
=========== Arrival Mechanics (Layer 2 - specs sealed) ===========
Sub-segments:
  5A  Arrival Surfaces & Calendar              [ SPECS SEALED - IMPLEMENTATION NEXT ]
  5B  Arrival Realisation (LGCP + Routing)     [ SPECS SEALED - IMPLEMENTATION NEXT ]

Notes:
  - 5A defines deterministic intensity surfaces per merchant/zone/time bucket,
    with calendar/scenario overlays (paydays, holidays, campaigns).
  - 5B realises arrivals from those surfaces using LGCP-style latent fields
    plus Poisson draws, then routes each arrival through L1 alias tables and edges to a site.

[4A/4B overlay]  >>> S0 gate + validation bundle pattern reused for 5A/5B
                   (same run sealing, RNG, and HashGate discipline as Layer 1)


=========== Flow Dynamics (Layer 3 - specs sealed) ===========
Sub-segments:
  6A  Entity & Product World                   [ SPECS SEALED - IMPLEMENTATION NEXT ]
  6B  Behaviour & Fraud Cascades               [ SPECS SEALED - IMPLEMENTATION NEXT ]

Notes:
  - 6A builds the entity graph: customers, accounts, instruments, devices, IPs,
    merchant-side accounts, and static fraud roles (mules, synthetic IDs, risky merchants).
  - 6B maps arrivals to entities, generates transactional flows (auth/clear/refund/
    chargeback), overlays fraud and abuse campaigns, and produces truth plus bank-view labels.

[4A/4B overlay]  >>> same governance rails in Layer 3:
                   sealed inputs, deterministic specs, validation bundles,
                   and "no PASS -> no read" for all L3 outputs
```

---

## Developer Tooling

We ship a lean pre-commit configuration that focuses on the active engine work:

- `ruff` / `ruff-format` for linting and formatting Python sources.
- `pre-commit-hooks` + `pretty-format-yaml` for newline, whitespace, and YAML hygiene limited to governed folders.
- `mypy` scoped to `packages/engine/**` (run manually via `pre-commit run mypy --hook-stage manual`).
- `gitleaks` runs on pre-push for secrets scanning (config in `gitleaks.toml`).

Install or refresh the hooks locally with:

```bash
python -m pre_commit install --install-hooks
```

Run them on demand with:

```bash
python -m pre_commit run --all-files
```

These commands keep the hook environments reproducible without blocking commits for tooling issues outside the governed paths.
