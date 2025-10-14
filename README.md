# Closed-World Enterprise Fraud Platform — Concept Overview

> **Status:** Conceptual, non-binding.  
> **Mission:** Build a bank-grade, closed-world fraud platform. All data (train/test/stream/labels) comes **only** from the **Data Engine**. No third-party enrichment. Everything is governed by contracts, lineage, validation gates, and reproducible runs.
> *Refer to `docs/references/closed-world-synthetic-data-engine-with-realism-conceptual-design.md` for more information*

---

## Quick TL;DR
- **Closed world:** the Data Engine is the single source of truth.  
- **Contracts-first:** JSON-Schema is the authority; consumers must pass validation (**no PASS → no read**).  
- **Reproducible:** every run is identified by `{ seed, parameter_hash, manifest_fingerprint }`.  
- **Two feature planes:** online (low-latency, freshness SLOs) and offline (training/replay) with **identical transforms**.  
- **Decision fabric:** guardrails → primary ML → optional 2nd stage; returns **ACTION + reasons + provenance** with a **degrade ladder** to keep latency SLOs.  
- **Auditability:** immutable decision log + label store; deterministic replay/DR from lineage.


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
- **Separation of concerns.**  
  - **L0** emitters (schema-bound I/O)  
  - **L1** pure kernels  
  - **L2** orchestrators  
  - **L3** validators (read-only proofs)

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
- **Current focus:** Data Engine — **Layer-1 / Segment 1A, States S0–S4** (design frozen; implementation next).  
- **Reading order:** `contracts/` → `packages/engine/` → `services/` (concept) → `orchestration/` (concept).  
- **Promotion path:** when a service becomes real, it graduates from `services/<name>/` (docs) to `packages/svc-<name>/` (its own package).

---

## Repository layout
```text
fraud-enterprise/
├─ packages/                     # buildable Python distributions (each with its own pyproject & src/)
│  └─ engine/                    # the Data Engine package (active: Layer-1/1A S0–S4 lives here)
│     ├─ pyproject.toml
│     └─ src/engine/
│        ├─ cli/                 # (concept) command entry points: run / validate / manifest
│        ├─ registry/            # (concept) loads the declarative state registry
│        ├─ core/                # (concept) lineage, RNG mapping, numeric policy, IO, paths
│        ├─ validation/          # (concept) structural/corridor/adversarial checks; PASS bundle
│        ├─ scenario_runner/     # (concept) sealed-world traffic driver
│        └─ layers/              # (active) engine code by layer → segment → state (L0/L1/L2/L3)
│           └─ l1/seg_1A/
│              ├─ s0_foundations/{l0,l1,l2,l3}/
│              ├─ s1_hurdle/{l0,l1,l2,l3}/
│              ├─ s2_nb_outlets/{l0,l1,l2,l3}/
│              ├─ s3_crossborder_universe/{l0,l1,l2,l3}/
│              └─ s4_ztp_target/{l0,l1,l2,l3}/
│  # add more packages later as they become real (e.g., packages/svc-decision-fabric, packages/lib-shared)
│
├─ services/                     # runtime microservices — conceptual stubs (docs only until “promoted” to packages/)
│  ├─ ingestion/README.md        # schema/lineage gate, idempotent intake, tokenization
│  ├─ feature_online/README.md   # low-latency feature reads/writes; freshness parity with offline
│  ├─ decision_fabric/README.md  # rules + ML scoring, explanations, degrade ladder
│  ├─ replayer/README.md         # stream engine-generated events to the event bus
│  ├─ model_registry/README.md   # read-only pointers to immutable bundles
│  └─ consumer_gate/README.md    # enforce “no PASS → no read” for data consumers
│
├─ shared/README.md              # cross-service helper notes (logging, typing, time); not engine primitives
│
├─ contracts/                    # authoritative contracts (schemas, dataset dictionary, governed policies)
│  ├─ schemas/…                  # canonical JSON-Schemas for events/tables across layers/subsegments
│  ├─ dataset_dictionary/…       # dataset names, partitions, gating rules (concept)
│  └─ policies/…                 # versioned policy bundles consumed by kernels (concept)
│
├─ orchestration/                # workflow layer (concept)
│  ├─ airflow/…                  # runner-specific glue/DAGs if/when chosen
│  └─ state_registry/…           # declarative map: layer → segment → states with {after, gates}
│
├─ infra/                        # infrastructure & containerization (concept)
│  ├─ terraform/…                # modules + env compositions (network/compute/storage/observability)
│  └─ docker/…                   # image definitions (one image per package/service)
│
├─ config/                       # canonical non-secret configs + replayable run manifests
│  ├─ models/…                  # governed priors + versioned model exports (e.g., hurdle)
│  ├─ policy/…                  # channel/allocation/cross-border knobs (s3.rule_ladder.yaml, etc.)
│  ├─ runs/…                    # sealed JSON configs (e.g., s0_synthetic_config.json)
│  └─ scenario_profiles/…       # sealed-world traffic profiles for the Scenario Runner
│
├─ artefacts/                    # external artefact manifests & licenses (no raw data)
│  ├─ registry/…                 # logical name → manifest mapping (hash, license)
│  ├─ manifests/…                # provenance descriptors (source, license, digest)
│  └─ licences/…                 # third-party license texts
│
├─ tests/                        # test tree (concept)
│  ├─ unit/…                     # core primitives & state kernels/emitters; service API units
│  ├─ integration/…              # path↔embed equality; event→trace adjacency; determinism
│  └─ e2e/…                      # scenario → stream → decision → validation PASS (closed-world)
│
├─ docs/                         # narrative/context; not authoritative
├─ scripts/                      # small dev helpers; no business logic
├─ runs/                         # local run manifests & numeric attestations (gitignored; outputs live in data lake)
└─ examples/                     # non-authoritative demos (notebooks/scripts)
```

---

## Glossary
- **Closed world** — all data (train/test/stream/labels) is produced internally by the Data Engine.  
- **Validation bundle / `_passed.flag`** — proof that a dataset/run passed structural & corridor checks.  
- **`parameter_hash`** — digest of governed parameter sets that define run semantics.  
- **`manifest_fingerprint`** — digest of everything the run opened (incl. git tree and artefacts).  
- **Degrade ladder** — automatic path to meet SLOs under pressure (skip 2nd stage → last-good features → STEP-UP → rules-only).

---

> **Note:** This README describes the **destination**. Many folders are intentionally **conceptual** until unlocked. The **Data Engine** (Layer-1 / 1A S0–S4) is the active build target and as we progress, more will be unlocked

## Data Engine Progress

```
============================ DATA ENGINE (progress) ============================
[ Merchant-Location Realism ] | [ Arrival Mechanics ] | [ Flow Dynamics ]
            [   OPEN   ]      |       [  LOCKED ]     |     [  LOCKED ]

                 ^ focus now
-------------------------------------------------------------------------------
| 4A Reproducibility + 4B Validation = CROSS-CUTTING (baked into every box)   |
| VALIDATION HARNESS: ON FROM DAY 0 (spans all layers; not a tail-end step)   |
-------------------------------------------------------------------------------
```

```
=========== Merchant-Location Realism (open) ===========
Sub-segments:
  1A  Merchants → Physical Sites  ............. [ OPEN ]  <-- current focus
  1B  Place Sites on Planet ................... [ LOCKED ]
  2A  Civil Time Zone (IANA/DST) .............. [ LOCKED ]
  2B  Routing Through Sites ................... [ LOCKED ]
  3A  Cross-Zone Merchants .................... [ LOCKED ]
  3B  Purely Virtual Merchants ................ [ LOCKED ]

[4A/4B overlay]  >>> applied to every sub-segment above (inputs/outputs, RNG,
                   manifests, schema checks, and per-state validation gates)
```

```
=========== 1A state-flow (10 states; concept exposed) ===========
S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S9

Where (short labels just to anchor the flow):
S0 Prep      S1 Hurdle     S2 Domestic N   S3 X-border gate   S4 Foreign K
S5 Weights   S6 Select K   S7 Allocate N   S8 Egress/IDs      S9 Replay+Gate

Legend:
[OPEN]   = exposed/being worked
[LOCKED] = not yet opened to define
4A/4B    = reproducibility + validation, cross-cutting across all boxes/states
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
