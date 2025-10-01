# Enterprise Fraud Platform — End-State (Closed-World, Production)

## Purpose & constraints

This system runs like a bank, but in a **sealed universe**: the **Data Engine** is the only source of **transactions and labels**. No external enrichment, no third-party feeds. Every component is contract-driven (JSON-Schema authority), reproducible (seed + parameter set + manifest), and gated (**no PASS, no read**). The goal is low-latency, explainable **decisions** backed by rigorous **governance, replay, and audit**.

## Control plane (before anything moves)

On start, the platform **seals its world**: it loads version-pinned schemas and parameters, verifies that JSON-Schema is the sole authority, and fixes two anchors—`parameter_hash` and `manifest_fingerprint`. Those anchors ride with every dataset, feature, and decision. Release gates are universal: a producer must publish a validation bundle and PASS flag; consumers refuse to read otherwise (**no PASS, no read**).

## Concept Map
```
                            CLOSED-WORLD ENTERPRISE FRAUD PLATFORM — DETAILED ASCII MAP
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ CROSS-CUTTING RAILS:  CONTRACTS • LINEAGE • VALIDATION • PRIVACY/SECURITY • SLOs/OBSERVABILITY                           │
│ JSON-Schema is authority · no PASS→no read · parameter_hash + manifest_fingerprint · deterministic replay · RBAC & KMS   │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────┐          drives            ┌──────────────────────────────────────────┐        sidecars (not in flow)
   │   SCENARIO RUNNER    │ =========================> │               DATA ENGINE                │ ================================┐
   │ (traffic & campaigns)│                            │ L1: world/merchant realism  (1A..3B)    │                                │
   │ rate/seed/manifest   │                            │ L2: temporal arrivals       (2A..)      │                                │
   │ controlled replays   │                            │ L3: fraud flows/dynamics    (3A..)      │                                │
   └──────────────────────┘                            │ 4A/4B: reproducibility & validation     │                                │
                                                       │ sealed, deterministic, lineage-anchored │                                │
                                                       └────────────┬─────────────────────────────┘                                │
                                        emits canonical tx + lineage │                                                              │
                                                                     ▼                                                              ▼
                                                         ┌───────────────────────┐                                      ┌───────────────────────────┐
                                                         │     INGESTION GATE    │                                      │ AUTHORITY SURFACES (RO)  │
                                                         │ schema+lineage verify │                                      │ sites • zones/DST • order│
                                                         │ idempotent • tokenize │                                      │ civil-time legality       │
                                                         └────────────┬──────────┘                                      │ lineage anchors (read-only)│
                                                                      │                                                 └───────────────────────────┘
                                                                      ▼
                                             (contract-checked stream; lineage preserved)
                                                         ┌───────────────────────┐
                                                         │       EVENT BUS       │  (e.g., Kinesis)
                                                         └────────────┬──────────┘
                                      features (low latency)          │                       features+labels (batch parity)
      ┌───────────────────────────────────────────┐                   │                 ┌────────────────────────────────────────┐
      │        ONLINE FEATURE PLANE               │                   │                 │        OFFLINE FEATURE PLANE           │
      │ counters, windows, trust, TTL/freshness   │◄──────────────────┘                 │ same transforms • same schemas        │
      │ p95-safe reads (DynamoDB)                 │                                     │ dataset assembly for train/replay (S3)│
      └───────────────┬───────────────────────────┘                                     └───────────────────────┬────────────────┘
                      │                                                                                         │
                      ▼                                                                                         ▼
            ┌─────────────────────────────┐                                              ┌──────────────────────────────┐
            │ IDENTITY & ENTITY GRAPH     │◄──────────────── stream updates ─────────────│      DECISION LOG & AUDIT    │
            │ link device/person/account  │                                              │  STORE (immutable, queryable)│
            │ mule rings • collusion      │                                              │ inputs • features • versions │
            └──────────────┬──────────────┘                                              │ explanations • timings      │
                           │ features                                                    └───────────────┬─────────────┘
                           ▼                                                                            │
                 ┌───────────────────────────────┐                                                      │
                 │        DECISION FABRIC        │ <========= metrics & labels feedback ================┘
                 │ 1) guardrails (cheap)         │ ---------------- deploy bundles -------------------->  ┌──────────────────────────┐
                 │ 2) primary ML (calibrated)    │                                                      │   MODEL/POLICY REGISTRY   │
                 │ 3) optional 2nd stage         │                                                      │ bundles in S3 + pointers  │
                 │ reasons + provenance (signed) │                                                      │ in DynamoDB (immutable)   │
                 └──────────────┬────────────────┘                                                      └──────────────┬───────────┘
                                │ decisions                                                                     registry │/deploy
          ┌─────────────────────┴────────────────────┐                                                          ┌────────▼───────────┐
          │               ACTIONS LAYER              │                                                          │     MODEL FACTORY   │
          │ APPROVE • STEP-UP • DECLINE • QUEUE      │                                                          │ train • eval • pkg  │
          │ idempotent • audited (gateway sim)       │                                                          │ shadow→canary→ramp  │
          └──────────────┬──────────────┬────────────┘                                                          └─────────────────────┘
                         │ outcomes     │ queued cases
                         ▼              ▼
               ┌─────────────────┐   ┌───────────────────────────┐
               │   LABEL STORE   │   │ CASE MGMT / WORKBENCH     │
               │ fraud/FP/disputes│  │ queues • playbooks • links│
               │ lagged states    │  └───────────────────────────┘
               └──────────────────┘

                                ┌─────────────────────────────────────────────────────────────────────────────────────────┐
                                │                         DEGRADE LADDER (automatic)                                      │
                                │ skip 2nd stage → use last-good features → raise STEP-UP → rules-only (keep SLOs)       │
                                └─────────────────────────────────────────────────────────────────────────────────────────┘


      ┌──────────────────────────────────────────────────────── RUN / OPERATE PLANE (AWS-oriented) ──────────────────────────────────────────────────────┐
      │ Orchestrate: Airflow (MWAA) DAGs → ECS Fargate tasks (engine runs, training, deploy, replay)                                                    │
      │ Containers: ECR images per service (engine, scoring, replayer, feature updaters); healthchecks; blue/green                                      │
      │ Storage: S3 (KMS) for lake + bundles • DynamoDB for online features & registries • RDS/Aurora for cases/audits                                  │
      │ Bus: Kinesis streams (contract-checked puts) • Secrets: Secrets Manager/SSM • Access: least-privilege IAM                                       │
      │ Engine Run Registry: manifests (seed, params, git, digests) • Engine State Registry: DAG of layers/subsegments/states                            │
      └──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘


┌───────────────────────────────────────────────────────────────────── OBSERVABILITY & GOVERNANCE ─────────────────────────────────────────────────────┐
│ Golden signals: latency p50/95/99, TPS, error rates, saturation • Data health: schema errors, nulls, volume deltas, lineage mismatches              │
│ Feature freshness & train/serve skew • Model drift & decision-mix deltas • Corridor checks (synthetic probes) • Replay/DR from manifests            │
│ Change control: contract tests in CI, determinism checks (re-run & byte-diff), dual read/write on risky paths • Security: encryption, redaction,   │
│ retention policies • Audit: every decision carries {manifest_id, feature_view_hash, model/policy versions, reasons, timings}                        │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Legend (compact):
• (RO) authority = read-only truth surfaces (never re-derived) • arrows = data/control flow • sealed = closed-world, engine-only data
```

## Execution plane (how a day actually runs)

### 1) Scenario runner & Data Engine (the only reality)

A scenario runner drives the Data Engine to emit a **production-shaped stream** at wall-clock speed: merchants with realistic outlet networks and civil time, arrivals and diurnals, and fraud campaigns. Every event carries lineage (`parameter_hash`, `manifest_fingerprint`, seed/run) and the authority surfaces (site/zone/order). Because the world is sealed, this stream is the switch—everything downstream treats it as real.

### 2) Ingestion gate (thin, strict)

Events hit a tiny ingress service that **verifies schema and lineage, enforces idempotency**, stamps correlation and arrival times, and **tokenizes PII by default** (even though data are synthetic). It does not call the outside world; it simply guarantees that what enters the decision fabric is on-contract and safely packaged.

### 3) Features, two planes, one truth

The stream forks:

* **Online features** compute the **p99-safe** set needed for real-time scoring (recent velocity windows; device/merchant/site counters; time/geo transforms). They have explicit **freshness SLOs/TTLs** and return within budget.
* The **offline store** mirrors the same transforms for training/replay. Feature code is shared; schema refs are identical. Every decision records a **feature snapshot hash** so replay is exact.

### 4) Decision fabric (rules + ML, with an explicit degrade ladder)

A single decision API runs the **guardrails** (cheap structural/policy checks), then a **calibrated primary model**. An **optional second stage** (graph/device coherence) runs only if there’s budget left. A **policy aggregator** turns score + context into an action (**APPROVE / STEP-UP / DECLINE / QUEUE**) and emits **reasons** plus a **provenance bundle**: model version, feature snapshot hash, lineage anchors, correlation id, and latency.

When latency pressure rises, the system **degrades gracefully in a fixed order**: skip second stage → use last-good features → raise STEP-UP rate → guardrails only (as a final resort). Prefer **STEP-UP** to hard declines when degrading.

### 5) Actions & side-effects (idempotent, audited)

Approvals pass through. STEP-UP challenges (3DS/OTP) are simulated under governance and recorded. Declines notify the merchant and (synthetic) customer. Queued items open **cases**. All effects are idempotent and logged; retries won’t double-charge or double-notify.

### 6) Label store (closed-loop outcomes)

Outcomes are **generated internally** with realistic timing: immediate (challenge pass/fail, explicit blocks) and **delayed** (chargebacks/disputes with governed lags and reason codes). Clean label states (confirmed fraud, false positive, dispute, chargeback) populate a **Label Store** that powers training and monitoring—no external labels required.

### 7) Model factory (learn → prove → promote → watch)

A separate plane assembles training datasets from the stream + Label Store + authority tables, all pinned to schema refs and lineage. Training uses the **same feature code** as serving. Candidates are evaluated (AUROC/PR, calibration, cost), **registered**, then flow **shadow → canary → ramp** with **auto-rollback on SLO breach**. Thresholds and calibration live as **policy artefacts**, not hardcoded. Nothing moves without manifest+schema+lineage+PASS.

### 8) Monitoring & SRE (the system’s nerves)

Golden signals span infra, data, and ML: p50/p95/p99 decision latency, throughput, error budgets; **feature freshness and training/serving skew**; decision mix (approve/decline/step-up); risk heatmaps; schema-error and null-spike rates. Alerting ties to SLOs. The estate is **multi-AZ**, supports **backpressure**, and achieves effectively **exactly-once** outcomes via idempotent writes and replayable partitions. **Replay/DR** can rebuild features and decisions from lineage deterministically.

### 9) Evolution without breakage

Change control is policy: **dual-read/dual-write** patterns for schema migrations, contract compatibility tests in CI, and **no PASS, no read** across the board. Incident playbooks include kill-switches (disable second stage, freeze a rule, raise step-up), model/policy rollback, and “replay to rebuild state.”

### 10) Security, privacy, and compliance—even in synthetic

Least-privilege IAM, key rotation, encrypted data in motion/at rest, default redaction in logs, audited access to sensitive artefacts, codified retention, and licence tracking alongside manifests. Partitions are **content-addressed**, making datasets immutable by key and easy to attest.

## Authority boundaries (what nobody downstream re-derives)

* **Counts (N)** and **country order** come from the location realism flow; order of record is the authority table, not file order.
* **K_target** (intended extra-country count) is fixed by its own sampler; realization happens later, but order still comes from the authority surface.
* **Civil time legality** (IANA/DST) is upstream; real-time checks only **verify**.

## SLO envelope & degrade policy (design targets)

* **Ingestion gate:** p99 ≤ 5 ms
* **Feature fetch (hot):** p99 ≤ 10 ms; freshness ≤ 60 s for specified counters
* **Primary scorer:** p99 ≤ 10 ms
* **Optional second stage:** p99 ≤ 15 ms (skippable)
* **Decision end-to-end:** p99 ≤ 50 ms
  If budgets are threatened: **skip 2nd stage → last-good features → raise STEP-UP → guardrails-only**.

## Life of a transaction (one breath)

Engine emits an event → ingestion verifies & receipts → online features compute within SLO → guardrails + primary model (maybe 2nd stage) → policy returns action + reasons + provenance → action executes idempotently → simulated outcome lands in Label Store → training plane learns and safely promotes the next model → monitors watch latency, quality, and drift; replay is always possible from lineage.

---
