# Dev-Min Managed-Substrate Migration (Local Parity → Managed Kafka + AWS Evidence) — Design-Authority v0

## 0. Document Control

### 0.1 Status

* **Status:** v0 (Design-Authority; implementer execution authorized)
* **As-of:** 2026-02-10 (Europe/London)
* **Scope of v0:** define the **dev-min rung** (budget-safe managed substrate) and its relationship to the existing env ladder; pin non-negotiable decisions + guardrails; leave implementation choices to Codex where explicitly marked.

### 0.2 Roles and Audience

* **Designer / Spec Authority:** GPT-5.2 Thinking (this document is the authority for pinned decisions)
* **Implementer:** Codex (GPT-5.3) — expected to implement *within* pinned bounds
* **Primary reader:** Codex (for implementation)
* **Secondary readers:** Esosa (for approval), any reviewer validating drift vs pinned flow narrative

### 0.3 Authority Boundaries

**Pinned (Codex MUST follow)**

* **Env ladder semantics remain:** `local_parity → dev → prod` as the platform environment ladder. 
* **dev-min is a “dev rung/profile”, not a new governance environment.** It exists to prove “same laws, different wiring” using managed substrate under a £30/mo cap.
* **Budget posture:** hard cap **~£30/month**, default posture **demo → destroy** (ephemeral infra is destroyed after each demo run).
* **Kafka decision:** dev-min uses **managed Kafka (Confluent Cloud)** as the EB backend for day-to-day dev-min runs.
* **AWS evidence substrate:** dev-min uses **AWS S3** as the durable substrate for oracle/archive/quarantine/evidence artifacts (and Terraform state).
* **Prohibited cost footguns:** no NAT Gateway; no always-on load balancers; no always-on compute fleets.
* **Semantic invariants do not change across envs:** schema pins, envelope pins, dedupe tuple + payload_hash anomaly semantics, append-only truth stores, origin_offset evidence basis, explicit degrade only.   

**Implementer Freedom (Codex MAY choose)**

* Exact Terraform module layout, naming (within pinned naming conventions), and internal resource composition (as long as constraints/guards are met).
* Whether dev-min compute runs **locally** (recommended for budget) or as **ephemeral AWS tasks** (allowed only if destroy-by-default).
* Observability backend wiring details (as long as it meets the “minimal counters + rare anomalies” posture and writes run reconciliation/evidence to S3). 
* Optional “AWS-native Kafka flex demo”: Codex may add a **feature-flagged** MSK Serverless module *only if* it is strictly ephemeral and does not compromise the £30/mo cap. (Not required for v0.)

### 0.4 Document Conventions

* **Normative language:**

  * **MUST / MUST NOT** = pinned requirement
  * **SHOULD** = strong preference, overridable only with explicit decision-log entry
  * **MAY** = implementer discretion
* **Drift policy:** if implementation requires violating any MUST/MUST NOT, Codex must stop and request a repin (no silent redesign).

### 0.5 References (Normative)

* Platform flow narrative (overall intended flow + invariant laws). 
* Run/Operate pre-design decisions (env ladder, identity/config/promotion posture). 
* Observability & Governance pre-design decisions (counters, anomalies, reconciliation, corridors). 
* Control & Ingress pre-design decisions (IG admission laws, dedupe tuple, receipts, publish ambiguity). 
* RTDL pre-design decisions (evidence basis, archive posture, idempotency, replay). 
* Platform parity walkthrough (local_parity harness baseline). 

### 0.6 References (Non-normative / Working Notes)

* `dev_substrate_to_production_resource_tooling_notes.md` (tooling/migration notes; helpful context but not an authority source).

---

## 1. Problem Statement

### 1.1 The gap we discovered (local_parity ≠ dev/prod)

We built a working **local_parity** system that correctly implements the platform’s **semantic laws** (integrity gating, dedupe/receipts, append-only auditability, explicit degrade, replayability).   

However, the implementation path implicitly assumed that “dev/prod” would be achieved by **containerizing and deploying the same home-built substrate** (hand-built bus/store/ops plumbing) that exists locally. This creates two failures:

1. **Wrong workload:** we end up implementing a bespoke tool stack (mini-infra) rather than exercising the platform logic on **managed primitives** (Kafka/object store/managed DB/observability), which is what dev/prod actually looks like.  
2. **False readiness:** local_parity hides key dev/prod realities (identity boundaries, managed service failure modes, durable evidence posture, and operational ergonomics).  

**Therefore:** continuing the “self-built substrate → deploy” track would produce a system that may be correct, but is not convincingly “production-like” in the way relevant to the target roles.

### 1.2 Why migrate now (portfolio credibility + operational feasibility)

The project goal includes being able to honestly claim that the platform is **production-like** (bank-shaped decisioning loop, auditable evidence trails, deterministic replay, incident drills under load). 

To support that claim, we must demonstrate:

* The same semantic laws hold while using **managed Kafka** for the event bus and **AWS S3** for durable truth/evidence storage (and associated operational controls).  
* The run can be operated with **run/operate discipline** (explicit run IDs, pinned configuration, repeatable execution, evidence bundles). 
* The system can be validated via **observability + reconciliation** without relying on “it’s local, just inspect the container.” 

This migration is also required for practical reasons: the home-built substrate becomes a bottleneck quickly, and scaling it diverts effort away from proving the platform’s actual value proposition.

### 1.3 What success must feel like (dev-min rung definition)

Success is a **dev-min managed-substrate environment** that:

* Preserves **all platform semantic invariants** from the flow narrative and plane decisions (no redesign).   
* Uses **managed Kafka (Confluent Cloud)** as the primary EB backend and **AWS S3** as the durable evidence substrate.
* Is **budget-safe**: operates under a **~£30/month cap** by being **demo → destroy** (ephemeral resources torn down after each demo run).
* Produces a **portfolio-grade evidence bundle** per run (run summary, receipts/audit slices, offsets/replay proof, minimal dashboards), stored durably. 
* Can be brought up and torn down reproducibly via **Terraform** (no manual console clicking required for the core dev-min posture). 

In short: **local_parity remains the correctness harness**, while **dev-min becomes the proof** that the platform operates on managed primitives with real operational posture—without turning this project into an infrastructure build.

---

## 2. Goals and Non-Goals

### 2.1 Goals (what v0 dev-min MUST accomplish)

1. **Managed-substrate proof (Kafka + AWS evidence)**

   * Run the platform with **managed Kafka (Confluent Cloud)** as the event bus backend.
   * Persist durable truth/evidence artifacts to **AWS S3** (oracle/archive/quarantine/evidence + Terraform state).  

2. **No semantic drift**

   * Preserve platform laws across envs:

     * Dedupe tuple + payload_hash anomaly semantics
     * Append-only truth stores (receipts, DLA, labels)
     * origin_offset evidence for replay
     * Explicit degrade (no silent guessing)
     * Provenance pins carried end-to-end   

3. **Budget-safe operations under £30/month**

   * Default posture is **demo → destroy**:

     * expensive resources are created only for demos and destroyed afterward.
   * Infrastructure is designed to prevent silent cost creep. 

4. **Reproducible bring-up and teardown**

   * A single operator (you) can:

     * bring up dev-min,
     * run a demo (including incident drills),
     * collect evidence,
     * tear down the demo infrastructure,
       using scripted commands and Terraform.

5. **Portfolio-grade “proof artifacts”**

   * Each demo run MUST produce a durable **evidence bundle** stored in S3 that supports the claim:

     * “I operated the platform, ran incident drills, and used deterministic replay to prove fixes with auditable trails.”  

### 2.2 Non-Goals (explicitly out of scope for this migration)

1. **No full production hardening**

   * We are not delivering regulated-prod posture (full compliance, multi-account org governance, WORM enforcement, formal approvals).

2. **No mandatory Kubernetes/Flink/Temporal**

   * This v0 migration MUST NOT require standing up:

     * Kubernetes (EKS),
     * Flink,
     * Temporal,
       as dependencies to complete dev-min. (These may appear later as dev-full/prod-target upgrades.)

3. **No always-on environment**

   * dev-min is not intended to run 24/7.
   * The expected usage pattern is **demo sessions** (hours), not continuous uptime.

4. **No re-architecture of planes**

   * We do not change the component network topology or responsibility boundaries established in the flow narrative and pre-design decisions. 

### 2.3 Constraints (hard boundaries Codex MUST respect)

* **Budget cap:** ~£30/month (assume no AWS credits; keep AWS side minimal, Kafka costs controlled by uptime).
* **Destroy-by-default:** ephemeral resources must be destroyable via Terraform without manual cleanup.
* **Avoid known AWS budget traps:** MUST NOT introduce NAT Gateway; MUST NOT require always-on ALB/NLB unless explicitly repinned.
* **Solo operator:** the runbook must be executable by one person with CLI tools.
* **Time realism:** prefer simplest managed primitives that preserve semantics over “enterprise maximalism.”

---

## 3. Definitions and Shared Terms

### 3.1 Environment Ladder Terms

* **`local_parity`**: Local harness environment used to validate **semantic correctness** under production-shaped contracts using local shims (e.g., local object store/bus/db). This is the **correctness + determinism** proving ground.  
* **`dev_min`**: The **managed-substrate proof rung** defined by this document. It MUST preserve all semantic laws, but swaps substrate primitives to **managed Kafka + AWS S3 evidence** under a strict **demo → destroy** budget posture.  
* **`dev_full`**: An optional later rung that adds stronger operational posture (richer observability, stricter identity, richer runbooks/alerts). Not required to complete v0 dev_min.  
* **`prod_target`**: Aspirational “late-stage” production architecture target used for design direction only. Not required to run as a paid always-on environment for portfolio purposes. 

### 3.2 Run Identity and Correlation Terms

* **`platform_run_id`**: Execution-scope identifier for a single platform run. It is the primary correlation key across planes, receipts, audit, and evidence bundles.  
* **`scenario_run_id`**: Deterministic scenario identity derived from an equivalence key; paired with `platform_run_id` during execution (both must be carried in control/ingress semantics).  
* **`event_id`**: Deterministic identifier of an event instance within an event class (stable across retries). 
* **`event_class`**: Canonical event type/classification used for admission policy, partitioning, and dedupe semantics (resolved by IG). 

### 3.3 Admission, Dedupe, and Integrity Terms

* **Dedupe Tuple (canonical)**: `(platform_run_id, event_class, event_id)` — the required identity tuple for admission idempotency. 
* **`payload_hash`**: Hash of admitted payload used to detect integrity mismatches. If the same dedupe tuple is seen with a different payload hash, it MUST be treated as an anomaly and routed per quarantine/anomaly policy (not silently overwritten).  
* **Receipt**: Append-only admission record produced by IG indicating outcomes such as `ADMIT`, `DUPLICATE`, `QUARANTINE` (plus provenance/evidence fields). Receipts are evidence, not mutable state.  
* **Quarantine**: Routing destination for rejected/anomalous events; preserves payload + metadata for analysis and governance visibility.  

### 3.4 Evidence, Replay, and Offsets Terms

* **`origin_offset`**: The durable consumption evidence pointer for an event on the bus (topic/partition/offset). It is the basis for replay proofs and reconciliation.  
* **Replay**: Re-execution of a run (or a slice) using the same sealed inputs and recorded offsets/provenance to reproduce decisions and validate fixes deterministically.  
* **Evidence Bundle**: A run-scoped collection of artifacts (run summary, receipts/audit slices, offset ranges, reconciliation outputs, key metrics) written to durable storage to support auditability and portfolio claims.  

### 3.5 Oracle / Streaming Terms

* **Oracle Store**: The sealed truth store for engine outputs used to drive streaming and gating; in dev_min this is AWS S3.  
* **`stream_view`**: A deterministic, sorted view of oracle outputs designed for streaming consumption (rather than reading raw outputs ad hoc). 
* **PASS gate / “no PASS → no read”**: Rule that streaming/consumption is allowed only after upstream gates validate run facts; enforced by SR/IG control semantics.  
* **READY signal**: The control-plane message emitted once gates are satisfied and run facts are pinned, authorizing downstream streaming.  

### 3.6 Operational Boundary Terms

* **Core (persistent) infra**: Resources allowed to exist outside demo windows (must be low-cost): e.g., S3 buckets for evidence/state, Terraform state + lock, minimal metadata tables, budgets/alerts, IAM scaffolding. 
* **Demo (ephemeral) infra**: Resources that MUST be created only for a demo run and destroyed afterward (default posture): compute tasks, optional load balancers, optional AWS-native Kafka flex module, etc. 
* **Destroy-by-default**: Policy requiring the operator path to end with `terraform destroy` for demo infra, leaving only core persistent artifacts (especially evidence bundles). 

---

## 4. Env Ladder Contract

### 4.1 What `local_parity` certifies (correctness harness)

`local_parity` is the **semantic correctness harness**. It MUST continue to be used as the place where we prove the platform’s laws without ambiguity, using local shims to move fast.  

`local_parity` MUST certify, at minimum:

* **Flow correctness** across planes per the flow narrative (Control/Ingress → RTDL → Case/Labels, plus meta-layer behaviors). 
* **Ingress integrity**: PASS gating, schema/pins validation, canonical `event_class`, dedupe tuple, receipts, and payload_hash anomaly behavior. 
* **RTDL evidence correctness**: origin_offset capture/propagation, explicit degrade behavior, and append-only audit semantics. 
* **Observability posture alignment**: counters + rare anomalies + reconciliation outputs exist as described (even if the backend is local). 

`local_parity` MAY use local substitutes (MinIO/LocalStack/etc) so long as the **interfaces and laws** match. 

### 4.2 What `dev_min` MUST prove (“same laws, different wiring”)

`dev_min` is the first environment rung that must demonstrate the platform is **production-like** in the sense that matters: it runs on **managed primitives** and still obeys the same laws.  

`dev_min` MUST prove:

1. **Managed substrate substitution**

   * Event bus uses **managed Kafka (Confluent Cloud)** for the EB topics relevant to the demo run.
   * Durable truth/evidence uses **AWS S3** (oracle/archive/quarantine/evidence + Terraform state).
2. **No semantic drift**

   * The semantic invariants in Section 7 remain true without “dev exceptions.”   
3. **Operational credibility**

   * Runs are executed as an operator would: pinned IDs/config, explicit run start/stop, repeatable demo procedure, evidence bundle produced and stored durably. 
4. **Budget posture**

   * Default posture is **demo → destroy** under ~£30/mo; expensive resources are not left running idle. 

`dev_min` SHOULD minimize scope by allowing compute to run locally while still using managed Kafka + AWS evidence (unless explicitly repinned). This supports the budget and time constraints.

### 4.3 What `dev_full` adds (optional polish rung)

`dev_full` is not required for v0, but defines the “next rung” once dev_min is stable. It adds stronger operational posture (Day-2 readiness), without changing semantics.  

`dev_full` MAY include:

* Richer observability backend (structured dashboards/alerts, tracing collection pipeline).
* Stronger identity posture and stricter runtime boundaries.
* More formal runbooks and reconciliation outputs.
* (Optional) moving more compute into managed runtime (ECS/EKS), if cost/complexity remains controlled.

`dev_full` MUST NOT introduce semantic changes; it only strengthens operational posture and tooling.

### 4.4 What `prod_target` means (aspirational, not required-to-pay-run)

`prod_target` represents the late-stage production architecture that the platform can grow into (multi-AZ reliability, stricter governance, stronger compliance posture). It is a **design direction**, not a requirement for the portfolio project to be continuously deployed as a paid always-on system. 

`prod_target` exists to:

* Inform how we structure interfaces/contracts now so we don’t paint ourselves into a corner later.
* Provide a credible “where this goes in industry” narrative without forcing infra-hell today.

`prod_target` MUST NOT be used to justify adding heavy dependencies (K8s/Flink/Temporal) into v0 dev_min unless explicitly repinned.

---

## 5. Pinned Decisions (NON-NEGOTIABLE)

### 5.1 Primary `dev_min` stack selections (fixed)

The following selections are **pinned** for v0 `dev_min`:

1. **Event Bus (EB) substrate**

   * **MUST:** Use **managed Kafka** via **Confluent Cloud** as the EB backend for `dev_min`.
   * **MUST:** Provision Kafka resources via IaC where possible (Terraform preferred).
   * **MUST:** Use Kafka topics for the platform buses required to run the demo (traffic/context/control/audit/case/labels as applicable).

2. **Durable truth + evidence substrate**

   * **MUST:** Use **AWS S3** as the durable substrate for:

     * Oracle Store (sealed outputs used for streaming)
     * Archive outputs (durable replay substrate)
     * Quarantine payloads
     * Evidence bundles (run summaries, reconciliation, audit slices)
     * Terraform remote state (tfstate bucket)

3. **Terraform**

   * **MUST:** Use **Terraform** as the primary IaC tool to provision AWS resources.
   * **SHOULD:** Use Terraform to provision Confluent Cloud resources (topics, service accounts, API keys, ACLs), unless blocked by provider constraints; any manual steps must be documented and minimized.

4. **Compute/runtime for `dev_min`**

   * **MUST:** Default to **local compute** for platform services during day-to-day `dev_min` runs (budget posture).
   * **MAY:** Add an **ephemeral AWS compute path** (ECS tasks/services) strictly for demo-day runs, provided it is destroy-by-default.

5. **Orchestration**

   * **MUST:** Use a lightweight orchestration approach compatible with demo → destroy:

     * **Option pinned for v0:** AWS **Step Functions** is permitted and recommended for `dev_min` run orchestration.
   * **MAY:** Continue to use the existing local run orchestrator for local runs (this does not violate dev_min), but dev_min must have a repeatable operator run procedure.

6. **Observability backend**

   * **MUST:** Preserve Observability & Governance posture (counters + rare anomalies + reconciliation outputs).
   * **MUST:** Produce a durable S3 evidence bundle per run.
   * **MAY:** Use CloudWatch and/or a minimal OTel export path; do not introduce heavy observability stacks in v0.

---

### 5.2 Cost posture (hard budget constraints)

1. **Budget cap**

   * **MUST:** Design so typical usage remains under **~£30/month**.
   * **MUST:** Assume no AWS credits are available.

2. **Demo → destroy**

   * **MUST:** Expensive resources MUST be created only for demos and destroyed immediately afterward.
   * **MUST:** The normal operating posture is *off by default*.

3. **Cost guardrails**

   * **MUST:** Create AWS cost alerts/budgets early (e.g., £10/£20/£28 thresholds).
   * **MUST:** Add lifecycle/retention limits to logs and non-evidence S3 paths (evidence may be retained longer).

---

### 5.3 Always-on vs Ephemeral resource policy (fixed)

1. **Core (persistent) resources — allowed**

   * **MUST:** Keep persistent resources minimal and low-cost:

     * S3 buckets (oracle/archive/quarantine/evidence/tfstate)
     * Terraform state lock table
     * IAM roles/policies
     * Budgets/alerts
     * (Optional) small DynamoDB tables for quarantine index / run index

2. **Demo (ephemeral) resources — destroy-by-default**

   * **MUST:** Any compute deployed to AWS for demos must be destroyable with Terraform and not left running idle.
   * **MUST:** Any optional AWS-native Kafka “flex demo” resources must be ephemeral.

---

### 5.4 Prohibited patterns (MUST NOT)

These are **hard prohibitions** for v0 `dev_min`:

* **MUST NOT** introduce a **NAT Gateway** (budget trap).
* **MUST NOT** require an **always-on load balancer** (ALB/NLB) for normal operation.
* **MUST NOT** deploy an always-on microservices mesh in AWS for dev_min (no 24/7 fleets).
* **MUST NOT** adopt **MSK provisioned** clusters for this project’s dev_min budget posture.
* **MUST NOT** introduce mandatory dependencies on Kubernetes/Flink/Temporal for v0 dev_min.

---

### 5.5 Evidence posture (what MUST be persisted)

Each demo run MUST produce an **evidence bundle** stored durably in S3 that supports:

* “This run happened” (run IDs, config digest/pins, timestamps)
* “Ingress laws were enforced” (receipt summaries + anomaly/quarantine counts)
* “Decisions happened and are auditable” (audit slices / DLA summary)
* “Replay is supported” (recorded origin_offset ranges and/or checkpoints)
* “Incidents were exercised” (which drills ran; observed outcomes)
* “Operator view exists” (minimal metrics snapshot + reconciliation summary)

---

## 6. Plane-by-Plane Mapping (WHAT moves where)

This section pins **what each plane uses in `dev_min`** (managed substrate wiring) while explicitly stating **what does not change** (the laws and component responsibilities). The intent is to keep Codex implementing wiring/adapters, not redesigning semantics. 

### 6.0 Cross-plane invariants (apply to every plane in every env)

Regardless of environment (`local_parity`, `dev_min`, later rungs), the following MUST remain true:

* The flow narrative’s end-to-end story remains the authority for connectivity and meaning. 
* Ingress integrity (PASS gating, dedupe tuple, receipts, payload_hash anomaly behavior) remains unchanged. 
* origin_offset evidence is captured/propagated for replay and reconciliation. 
* Append-only truth stores (receipts, DLA, labels) remain append-only. 
* Explicit degrade is used whenever join/evidence requirements are not met (no silent guess). 

---

### 6.1 World Builder Plane (Engine → Oracle → SR → READY)

**What stays the same (semantics):**

* Oracle outputs are treated as **sealed truth** for the run.
* Scenario Runner (SR) validates gates and publishes a READY signal with pinned run facts.  

**What changes in `dev_min` (substrate wiring):**

* **Oracle Store:** MinIO → **AWS S3**

  * Engine outputs are uploaded to S3 under run-scoped paths.
* **READY/control signaling:** local control bus → **Kafka control topic** (Confluent Cloud) OR Step Functions trigger path

  * Pinned choice for v0: Kafka control topic is allowed; Step Functions may orchestrate around it.

**Pinned `dev_min` resources used by this plane:**

* S3 bucket(s): `oracle/` (sealed outputs + stream_view materializations)
* Kafka topic: `fp.bus.control.v1` (or equivalent pinned naming)

**Implementer freedom:**

* Whether SR is run locally or as an ephemeral AWS task during demo-day (must remain destroy-by-default if in AWS).

---

### 6.2 Control & Ingress Plane (WSP → IG → EB + Quarantine + Receipts)

**What stays the same (semantics):**

* WSP streams deterministic events using stable `event_id`.
* IG is the integrity boundary:

  * validates pins/schema
  * resolves canonical `event_class`
  * dedupes on `(platform_run_id, event_class, event_id)`
  * payload_hash mismatch ⇒ anomaly/quarantine
  * writes receipts and publishes admitted events to EB 

**What changes in `dev_min` (substrate wiring):**

* **Event Bus:** Redpanda/LocalStack → **Confluent Cloud Kafka**

  * EB topics are real Kafka topics.
* **Quarantine payload store:** MinIO/local → **AWS S3**
* **Quarantine metadata index:** local DB/files → **AWS DynamoDB** (optional but recommended for dev_min)
* **Receipts store:** local Postgres/files → **S3 evidence + (optional) managed Postgres**

  * v0 allows receipts to remain in Postgres if compute is local, but an evidence summary MUST land in S3.

**Pinned `dev_min` resources used by this plane:**

* Kafka topics:

  * `fp.bus.traffic.v1`
  * `fp.bus.context.v1` (or separate context topics as per your design)
  * `fp.bus.control.v1`
* S3 buckets/prefixes:

  * `quarantine/` payloads
  * `evidence/receipts/` run evidence outputs
* DynamoDB:

  * `quarantine_index` (keyed by dedupe tuple + reason)

**Implementer freedom:**

* How IG persists receipts internally (db schema, files), as long as:

  * receipts remain append-only
  * S3 evidence summary is produced per run
  * anomaly/quarantine semantics remain correct

---

### 6.3 RTDL Plane (EB consumption → projections/join → DF/AL/DLA)

**What stays the same (semantics):**

* RTDL consumes admitted EB topics and records **origin_offset** evidence.
* Context topics build state; traffic triggers decisions.
* Join readiness is bounded and missing context triggers explicit degrade. 

**What changes in `dev_min` (substrate wiring):**

* **EB consumption:** now from Confluent Kafka using consumer groups.
* **Audit sinks:** DLA outputs MUST also be materialized to S3 evidence (at least as slices/summaries for demo runs).
* **Join-plane stores:** if you use a join store (CSFB), dev_min may use a managed KV (optional; can remain local for v0 if you are only proving Kafka + S3).

**Pinned `dev_min` resources used by this plane:**

* Kafka topics:

  * admitted traffic/context topics
  * `fp.bus.audit.v1` / decision/audit topic(s)
* S3 prefix:

  * `evidence/audit/` (DLA slices + summary)
  * `evidence/replay/` (offset ranges, checkpoints)

**Implementer freedom:**

* Whether projections/join state remains local for v0 (per budget/time) vs moved to managed Redis (allowed but not required in v0 dev_min).

---

### 6.4 Label & Case Plane (CM + LS loop)

**What stays the same (semantics):**

* CaseSubjectKey and LabelSubjectKey identity rules remain.
* CM timeline and LS assertions remain append-only and idempotent at the boundary. 

**What changes in `dev_min` (substrate wiring):**

* Event inputs come from Kafka topics (case triggers, audit topics).
* Evidence outputs (case/label summaries for the run) land in S3 evidence bundle.

**Pinned `dev_min` resources used by this plane:**

* Kafka topics:

  * `fp.case.triggers.v1` (or equivalent)
  * `fp.labels.assertions.v1` (or equivalent)
* S3 prefix:

  * `evidence/cases/`
  * `evidence/labels/`

**Implementer freedom:**

* Whether CM/LS operational DB remains local vs moved to managed Postgres in v0 dev_min (allowed to remain local if evidence exports exist).

---

### 6.5 Learning & Evolution Plane (Archive → OFS → MF → MPR)

**What stays the same (semantics):**

* Replay and dataset build are anchored to recorded evidence (offset ranges / archive truth).
* Label joins must be leakage-safe (as-of semantics). 

**What changes in `dev_min` (substrate wiring):**

* Archive lake is S3 (even if only Parquet/event dumps for now).
* Orchestration may be Step Functions for offline pipelines (optional in v0 dev_min).

**Pinned `dev_min` resources used by this plane:**

* S3 prefix:

  * `archive/` (event history)
  * `evidence/datasets/` (dataset fingerprints + manifests)
  * `evidence/models/` (training/eval summaries)

**Implementer freedom:**

* This plane is not required to be fully executed in v0 dev_min; only the archive substrate and evidence wiring must not block future work.

---

### 6.6 Meta Layers (Run/Operate + Obs/Gov)

**What stays the same (semantics):**

* Run/Operate defines how runs are initiated, pinned, observed, and closed. 
* Observability & Governance posture remains: metrics + anomalies + reconciliation outputs. 

**What changes in `dev_min` (substrate wiring):**

* Evidence bundles are written to S3 and are the durable “proof artifacts.”
* Operator run procedure is explicit and repeatable, with a teardown step.

**Pinned `dev_min` resources used by this plane:**

* S3 prefix: `evidence/runs/<platform_run_id>/...`
* (Optional) Step Functions state machine(s) for “demo run orchestration”
* CloudWatch logs/metrics (minimal posture)

**Implementer freedom:**

* Exact operational tooling (Make targets, scripts, runbook layout), provided the run is reproducible and destroy-by-default.

---

## 7. Laws that MUST NOT change (Semantic invariants across envs)

These invariants are **environment-agnostic**. The `dev_min` migration is permitted to change **wiring/substrate**, but **MUST NOT** change these laws.  

### 7.1 Dedupe tuple + `payload_hash` anomaly semantics

* **MUST:** IG dedupe identity is **exactly** `(platform_run_id, event_class, event_id)`. 
* **MUST:** `event_id` is stable across retries for the same logical event. 
* **MUST:** Same dedupe tuple + same `payload_hash` ⇒ treat as **DUPLICATE** (idempotent admit behavior), emit/write a receipt reflecting duplication. 
* **MUST:** Same dedupe tuple + **different** `payload_hash` ⇒ **anomaly**; MUST NOT overwrite; MUST route to quarantine/anomaly handling and surface via governance.  
* **MUST:** Any ambiguity about publish success MUST be modeled explicitly (no “assume publish failed/succeeded” shortcuts that break idempotency). 

### 7.2 Append-only truth stores (no mutation of history)

* **MUST:** IG receipts are **append-only** evidence (derive “current state” as a view; do not update prior receipts).  
* **MUST:** DLA audit/decision records are **append-only** (no in-place edits).  
* **MUST:** Label Store assertions are **append-only** (labels are added as new assertions; never “rewrite history”). 
* **MUST:** Case timelines are **append-only** event logs (a case view can be derived, but history is not mutated). 
* **MUST:** Any “resolved/current” representations MUST be generated as *derived views* from append-only records. 

### 7.3 `origin_offset` evidence + replay requirements

* **MUST:** Consumers record **origin_offset** evidence (topic/partition/offset) sufficient to reconstruct what was consumed for a run.  
* **MUST:** Replay proof is offset-anchored (and/or archive-anchored) — **MUST NOT** rely on “time window” selection as the truth anchor. 
* **MUST:** Evidence bundle MUST include the replay anchors for the demo run (offset ranges/checkpoints and the pinned run identifiers).  
* **MUST:** Do not advance “I consumed this” state unless the corresponding durable write/commit is done (no acking offsets ahead of durability). 

### 7.4 Explicit degrade rules (no silent guessing)

* **MUST:** Any missing join context / late context / unmet readiness constraint triggers **explicit degrade** (with reason) rather than implicit fallback. 
* **MUST:** Degrade posture used must be recorded into the decision/audit trail as provenance (so downstream and postmortems can explain behavior).  
* **MUST:** Compatibility/policy/model resolution failures are fail-closed or degrade-by-policy — never “best effort guess” without provenance.  

### 7.5 Provenance requirements (pins carried end-to-end)

* **MUST:** `platform_run_id` and `scenario_run_id` are present in control and evidence surfaces and remain the primary correlation keys.  
* **MUST:** Decision/audit/evidence outputs include the run’s pinned provenance inputs (at minimum: run IDs, relevant schema/policy/bundle identifiers, and evidence pointers).  
* **MUST:** Run/Operate posture holds: changes in configuration/behavior occur at explicit boundaries (new run / new policy rev / new bundle activation), not silently mid-run. 

---

## 8. Infrastructure-as-Code Plan (Terraform)

### 8.1 Repo layout and module boundaries (pinned)

**MUST** implement the `dev_min` IaC in **two stacks** with **separate state**:

1. **Core stack (persistent, low-cost)**

* **Purpose:** hold only resources that are safe to exist outside demo windows.
* **Location (pinned):** `infra/terraform/dev_min/core/`

2. **Demo stack (ephemeral, destroy-by-default)**

* **Purpose:** everything that can create meaningful cost or should not persist between demos.
* **Location (pinned):** `infra/terraform/dev_min/demo/`

**MUST** keep “core” and “demo” strictly separated so that:

* `terraform destroy` in **demo** leaves **core** intact.
* `terraform destroy` in **core** is a deliberate act (not required for normal demo teardown). 

**MUST** place Confluent Cloud Kafka resources in **demo**, not core (cluster cost control).

* Confluent environment/cluster/topics/API keys are demo-scoped and destroyed after demos unless explicitly repinned.

**MAY** factor shared code into `infra/terraform/modules/*`, but module extraction is optional; separation-by-directory is the pinned requirement.

---

### 8.2 State strategy (remote state + locking) (pinned)

**MUST** use remote Terraform state on AWS with locking:

* **State backend:** S3
* **State lock:** DynamoDB
* **Encryption:** enabled at rest
* **Public access:** blocked (bucket-level public access block)

**MUST** use **two separate state keys**:

* `dev_min/core/terraform.tfstate`
* `dev_min/demo/terraform.tfstate`

**MUST** enable S3 **versioning** on the state bucket (rollback safety).

**MUST** treat Terraform state as **sensitive** (it may contain provider-managed secrets, especially Confluent API keys).

---

### 8.3 Naming and tagging conventions (pinned)

**MUST** define these pinned identifiers:

* `project_slug = "fraud-platform"`
* `env = "dev_min"`
* `region_default = "eu-west-2"` (London) (override permitted via variable)

**MUST** apply resource tags (AWS tags; Confluent labels/tags where available) with at least:

* `project = fraud-platform`
* `env = dev_min`
* `owner = esosa`
* `expires_at = <YYYY-MM-DD>` (operator-set; used as a teardown reminder)

**MUST** ensure S3 bucket names are globally unique by including `(account_id, region)` and/or an explicit suffix.

---

### 8.4 Providers and versions (pinned)

**MUST** use:

* **AWS provider** for core/demo AWS resources
* **Confluent provider** for Confluent Cloud resources (demo stack)

**MUST** pin provider versions by major range in code (exact versions are implementer choice, but version pinning itself is required).

**MUST** keep provider credentials out of the repo (use env vars, AWS profiles, or CI secrets).

---

### 8.5 Outputs and secrets handling (pinned)

**MUST NOT** commit any secrets (API keys, secrets, bootstrap creds) into git.

**MUST** mark any Terraform outputs that contain sensitive values as `sensitive = true`.

**MUST** store Confluent connection material created during demo apply (bootstrap endpoint + API key/secret) in **AWS SSM Parameter Store** as **SecureString** under a pinned path prefix:

* `/fraud-platform/dev_min/confluent/bootstrap`
* `/fraud-platform/dev_min/confluent/api_key`
* `/fraud-platform/dev_min/confluent/api_secret`

**MUST** destroy those SSM parameters when destroying the **demo** stack (avoid stale credentials lingering).

**MAY** additionally generate a local `dev_min` runtime env file (e.g., `.env.dev_min.local`) as a convenience, but it **MUST** be gitignored and treated as ephemeral.

---

### 8.6 Core stack contents (pinned list)

`infra/terraform/dev_min/core` **MUST** provision only:

* S3 buckets/prefixes for:

  * `oracle/`
  * `archive/`
  * `quarantine/`
  * `evidence/`
  * Terraform state bucket
* DynamoDB lock table for Terraform
* IAM scaffolding required for local compute to read/write S3 + read SSM (least privilege)
* AWS Budgets/alerts for the £30 cap (threshold alerts) 
* CloudWatch log groups (only if needed by demo; retention must be short)

Core **MUST NOT** include Kafka clusters, always-on compute, NAT gateways, or load balancers.

---

### 8.7 Demo stack contents (pinned list)

`infra/terraform/dev_min/demo` **MUST** provision:

* Confluent Cloud Kafka:

  * environment + cluster
  * required topics for the demo run (traffic/context/control/audit/case/labels as applicable)
  * service account(s) + ACLs/RBAC
  * API keys (written to SSM SecureString)

Demo **MAY** provision (only if you choose to run compute in AWS for demos):

* ECS tasks/services to run components in AWS during demo windows
* Step Functions state machine(s) to orchestrate the demo run

Demo **MUST NOT** provision NAT Gateway.
Demo **MUST NOT** provision always-on load balancers as a dependency for running the demo.

---

## 9. Networking and Access Posture (Budget-safe AWS)

This section pins a minimal networking posture that supports `dev_min` without introducing common AWS cost traps.

### 9.1 Default networking stance (pinned)

* **MUST:** `dev_min` assumes **local compute is the default** (services run on your machine) and connect outward to:

  * Confluent Cloud Kafka over the public internet,
  * AWS S3 / SSM / DynamoDB via AWS public endpoints.
* **MUST:** Therefore, `dev_min` **does not require** any AWS VPC, subnets, NAT, or load balancers to function in the default path.

This is the **budget-safe baseline**: pay for managed primitives only, avoid idle networking resources.

### 9.2 AWS VPC stance (only if demo compute moves into AWS)

If (and only if) we choose to run some demo compute inside AWS (ephemeral ECS tasks), then:

* **MAY:** Create a minimal VPC inside the **demo stack** (ephemeral).
* **MUST:** Keep it minimal:

  * 1 VPC
  * 2 public subnets (for AZ spread if needed)
  * Internet Gateway
  * Security groups restricted to least privilege
* **MUST NOT:** Create a NAT Gateway (hard prohibition).
* **MUST:** If tasks require outbound internet access, they must use **public subnets with public IPs** (ephemeral tasks) rather than NAT.

Rationale: NAT is a frequent surprise bill and violates the dev_min budget posture.

### 9.3 Public ingress stance (pinned)

* **MUST:** No component requires a public HTTP endpoint to run a dev_min demo. Operator control is via CLI/runbook, and services can be local.
* **MUST NOT:** Provision an always-on ALB/NLB in dev_min core.
* **MAY:** Provision a load balancer only in demo stack **if** a specific demo requires it (e.g., you want to show an external “IG endpoint” call). If used:

  * it MUST be ephemeral (destroyed after demo),
  * it MUST be minimal (no WAF, no extra listeners) unless explicitly repinned.

### 9.4 Connectivity to Confluent Cloud Kafka (pinned)

* **MUST:** Producers/consumers in dev_min connect to Confluent Cloud Kafka via:

  * SASL/SSL credentials (API key/secret) stored in SSM SecureString (Section 8.5).
* **MUST:** No secrets are stored in git.
* **SHOULD:** Use a single service account per “platform demo identity” to reduce IAM sprawl.
* **MAY:** Use multiple service accounts if you want to model writer boundaries more strongly; if so, document them in the topic map appendix.

### 9.5 IAM & least privilege (pinned)

* **MUST:** The operator/service identity used for dev_min must have only:

  * S3 read/write to the project buckets (scoped to relevant prefixes if practical),
  * SSM read/write for the Confluent secret paths,
  * DynamoDB access only to the specific tables used (tf lock + quarantine index).
* **MUST:** Deny broad wildcard permissions in committed policy docs (least-privilege posture).

### 9.6 Data egress awareness (budget note)

* **MUST:** dev_min design should avoid large data downloads from S3 to local unnecessarily (egress can cost money in some cases).
* **SHOULD:** Keep demo datasets small and lifecycle-managed (Section 14), and write evidence bundles compactly.

---

## 10. Secrets, Identity, and Config

This section pins how secrets and identity are handled in `dev_min`, and how configuration is treated as part of run provenance (no silent drift). 

### 10.1 Secrets: where they live (pinned)

* **MUST:** All sensitive values required for `dev_min` runs (especially Kafka credentials) are stored in **AWS SSM Parameter Store** as **SecureString**.
* **MUST:** The pinned parameter path prefix is:

  * `/fraud-platform/dev_min/`
* **MUST:** Confluent connection material paths are:

  * `/fraud-platform/dev_min/confluent/bootstrap`
  * `/fraud-platform/dev_min/confluent/api_key`
  * `/fraud-platform/dev_min/confluent/api_secret`
* **MUST:** Demo stack destroy must remove these parameters (no stale credentials).
* **MUST NOT:** Secrets appear in git, PR diffs, or committed `.env` files.

**Implementer freedom:** whether additional parameters exist for service configs (e.g., topic names, S3 bucket names) — allowed, but secrets must follow the same convention.

### 10.2 Identity: who is allowed to do what (pinned)

* **MUST:** There is a defined **operator identity** (you) used to:

  * run Terraform,
  * read/write required S3 prefixes,
  * read/write required SSM paths,
  * access the DynamoDB lock table (and optionally quarantine index).
* **MUST:** If compute runs locally, services use that operator identity (AWS profile/role) for AWS access.
* **MAY:** If demo compute runs in AWS, each task/service must assume an IAM role with least privilege (scoped to required S3/SSM/Dynamo actions).
* **MUST:** Confluent access uses the Confluent service account API key/secret stored in SSM (no long-lived keys in repo).

### 10.3 Config: pinned per run, no silent drift (pinned)

This is the key “dev/prod reality” constraint:

* **MUST:** A run’s “effective configuration” is treated as **provenance**, not an informal set of flags.
* **MUST:** For each `platform_run_id`, the platform MUST produce a **run config digest** (or equivalent) and store it in the evidence bundle.
* **MUST:** The “run config” MUST include at minimum:

  * environment name (`dev_min`)
  * `platform_run_id`, `scenario_run_id`
  * Kafka cluster endpoint identity (bootstrap or cluster ID)
  * topic name map used in the run
  * S3 bucket/prefix map used in the run (oracle/archive/quarantine/evidence)
  * any policy/bundle pointers used by the run (if applicable to your current stage)
* **MUST:** Mid-run config changes are forbidden; any change requires a new run (or an explicitly recorded boundary event).

**Implementer freedom:** how the digest is computed (hash algorithm, JSON canonicalization), so long as:

* it is deterministic,
* it is stored durably with the run evidence,
* and it changes when the effective config changes.

### 10.4 Local runtime env files (allowed but constrained)

* **MAY:** Generate a local runtime `.env.dev_min.local` file for convenience.
* **MUST:** It must be `.gitignore`’d.
* **MUST:** It must be considered ephemeral and safe to delete.
* **MUST:** It must not be the sole source of truth; the SSM parameters remain the authority for secrets.

### 10.5 Change control for pinned config surfaces

* **MUST:** If Codex changes:

  * topic names,
  * S3 path layout,
  * evidence bundle structure,
  * or secret parameter paths,
    it must update this doc (or the decision log section) and ensure compatibility with existing run evidence expectations.

---

## 11. Observability and Evidence (Dev-min)

This section pins the **minimum** observability posture and the **required evidence bundle** for `dev_min`. The goal is to support auditability, replay, and portfolio claims without standing up heavy observability infrastructure.  

### 11.1 Observability posture (pinned)

`dev_min` observability MUST follow the platform’s Obs/Gov stance:

* **Metrics:** hot path emits counters and latency/lag summaries
* **Rare events:** anomalies/governance facts are captured explicitly
* **Truth:** deep truth is by-reference to receipts/DLA/archive/label timelines, not duplicated into dashboards 

Accordingly, `dev_min` MUST provide:

* **Run-scoped metrics snapshot** (counts and key timings)
* **Anomaly summary** (duplicates, payload hash mismatches, quarantines, join-miss degrades, etc.)
* **Reconciliation summary** (what was intended vs what was observed)

### 11.2 Instrumentation requirements (pinned)

* **MUST:** Every service/component participating in the demo run MUST emit logs that include:

  * `platform_run_id`
  * `scenario_run_id` (where applicable)
  * `event_class` and `event_id` for event-scoped logs (where applicable)
* **SHOULD:** Emit OpenTelemetry-style trace/span IDs when convenient.
* **MUST:** If tracing is implemented, the correlation key for traces MUST include `platform_run_id` (either as trace ID or a top-level attribute).

**Implementer freedom:** whether to use full OpenTelemetry SDK and where to export traces (CloudWatch/X-Ray/other). v0 does not require a full tracing backend; it requires correlation in evidence.

### 11.3 Minimal backends allowed in v0 dev_min (pinned)

* **MAY:** Use CloudWatch Logs for any AWS-hosted demo compute.
* **MAY:** Use local logs + evidence export if compute is local.
* **MUST:** Regardless of backend, the run MUST emit a durable S3 evidence bundle (Section 11.4).

### 11.4 Evidence bundle (MUST produce per demo run)

For each `platform_run_id`, the platform MUST write an evidence bundle to S3 under a pinned layout:

* **Pinned S3 prefix format:**

  * `s3://<evidence_bucket>/evidence/runs/<platform_run_id>/`

Within that prefix, the run MUST produce at minimum:

1. **Run header**

   * `run.json` (or equivalent) containing:

     * `platform_run_id`, `scenario_run_id`
     * env = `dev_min`
     * run start/end timestamps
     * run config digest + the config payload (or reference)
     * git commit SHA (if available)
     * component versions (if available)

2. **Ingress evidence**

   * Receipt summary:

     * counts: ADMIT / DUPLICATE / QUARANTINE / ANOMALY
     * top reasons for quarantine/anomaly
   * If storing receipt samples:

     * include a small, representative slice (do not dump huge volumes)

3. **Decision/audit evidence**

   * DLA summary:

     * decisions count
     * action intents count
     * action outcomes count
     * degrade posture counts
   * Small audit slice (optional but recommended)

4. **Replay anchors**

   * origin_offset range summary for each relevant topic/partition:

     * topic name
     * partition
     * start_offset
     * end_offset
   * Any checkpoints used (if applicable)

5. **Observability snapshot**

   * metrics snapshot (json)
   * anomaly summary (json)
   * reconciliation summary (json)

**MUST:** Evidence outputs MUST be deterministic and reproducible given the same run inputs (run IDs and pins).

### 11.5 Telemetry cost guardrails (pinned)

* **MUST:** CloudWatch log retention must be short in dev_min (3–7 days).
* **MUST:** Evidence bundles MUST be compact:

  * summaries + small slices, not full topic dumps
* **SHOULD:** Sampling is allowed for traces/logs as long as evidence bundle remains sufficient for claims.

### 11.6 “Proof artifacts” for portfolio claims (pinned)

A dev_min demo run is considered “portfolio-credible” only if the evidence bundle supports:

* the run occurred,
* ingress laws held,
* decisions were produced and audited,
* replay anchors exist,
* incident drills were executed and recorded.

---

## 12. Run/Operate Workflows (Dev-min orchestration)

This section pins how a `dev_min` demo run is initiated, executed, and closed in an operator-shaped way, without requiring heavy orchestration platforms. 

### 12.1 Operator model (pinned)

* **MUST:** A demo run is started by an operator action (CLI / Make target), not by ad hoc manual steps in multiple places.
* **MUST:** The run creates and pins:

  * `platform_run_id`
  * `scenario_run_id`
  * run config payload + digest
  * a run “start” event/evidence record
* **MUST:** The operator model includes a “close run” step that finalizes evidence outputs and marks completion.

### 12.2 Dev-min workflow backbone (pinned)

The `dev_min` workflow is defined as the following stages. Implementer may choose whether these are implemented as:

* a Make-driven CLI sequence, or
* an AWS Step Functions state machine,
  but the stage semantics MUST be preserved.

**Stage 0 — Preconditions**

* Validate required secrets exist in SSM (`/fraud-platform/dev_min/confluent/*`).
* Validate required S3 buckets exist (core stack applied).
* Validate Kafka topics exist (demo stack applied).

**Stage 1 — Run initialization**

* Create `platform_run_id`.
* Record/compute run config payload + digest.
* Write `ACTIVE_RUN_ID` pointer (if still used) and a run-start record into the evidence bundle prefix.

**Stage 2 — Gate + READY**

* SR validates run facts/gates based on sealed oracle outputs in S3.
* SR emits READY (control topic and/or internal control event) including:

  * `platform_run_id`, `scenario_run_id`
  * pinned pointers required for downstream authorization

**Stage 3 — Stream world (WSP)**

* WSP reads `stream_view` from oracle S3 and streams:

  * traffic events
  * context events
    with deterministic `event_id`.
* WSP retry rules:

  * transient errors may retry with same `event_id` (idempotent behavior)
  * schema/policy violations are non-retryable and stop/route to governance

**Stage 4 — Ingress gate (IG)**

* IG validates pins + schema.
* IG resolves `event_class`.
* IG performs dedupe on `(platform_run_id, event_class, event_id)` and applies payload_hash anomaly rules.
* IG publishes admitted events to Kafka topics.
* IG writes receipts (append-only) and evidence summaries.

**Stage 5 — RTDL processing**

* RTDL consumes admitted topics.
* RTDL records origin_offset evidence.
* RTDL executes decision loop (including explicit degrade where needed).
* RTDL writes decision/audit outputs.

**Stage 6 — Case/Label loop (if included in demo)**

* CM consumes triggers/audit as per current implementation and builds append-only timelines.
* LS records label assertions (append-only) and produces any label events required.
* Evidence summaries for case/label activity are written to S3 evidence bundle.

**Stage 7 — Run closure**

* Produce reconciliation summary.
* Produce metrics/anomaly snapshot.
* Write replay anchor summary (offset ranges).
* Mark run as completed in evidence bundle (e.g., `run_completed.json`).

### 12.3 Failure handling rules (pinned)

* **MUST:** Differentiate transient vs non-transient failures:

  * transient failures may retry (bounded)
  * permanent validation failures must quarantine/anomaly + stop affected flow
* **MUST:** Do not “ack” or advance consumer state beyond durable writes.
* **MUST:** If any stage fails, the workflow must still write a run evidence record capturing:

  * failure stage
  * error reason
  * partial metrics/anomaly summaries
  * any offsets consumed so far

### 12.4 Incident drill hooks (pinned)

`dev_min` MUST support scripted incident drills during a demo run, and each drill MUST be recorded in the evidence bundle. Examples (not exhaustive):

* duplicates
* missing/late context
* payload_hash mismatch (integrity anomaly)
* intentional lag/backpressure (small scale)

**Implementer freedom:** exact drill mechanism (input shaping, toggles, test fixtures), as long as:

* the drill is identifiable in evidence,
* the expected outcome is asserted and recorded.

### 12.5 Operator commands (pinned interface, not implementation)

The operator MUST have these three commands/targets:

* `dev-min-up` (apply core + apply demo; validate prerequisites)
* `dev-min-run` (execute the demo workflow; produce evidence bundle)
* `dev-min-down` (destroy demo stack; leave only core + evidence)

**Implementer freedom:** exact CLI names and Makefile structure are flexible, but the three semantic actions MUST exist.

---

## 13. Demo-Day Runbook (Operator view)

This is the **operator-facing** procedure for running a `dev_min` demo end-to-end and producing portfolio-grade evidence, then tearing down cost-bearing infra.

### 13.1 Preconditions (pinned)

Before a demo run, the operator MUST confirm:

1. **Core stack exists**

* S3 buckets for `oracle/archive/quarantine/evidence` exist.
* Terraform remote state backend + lock table exist.

2. **Kafka demo substrate exists (demo stack applied)**

* Confluent Cloud Kafka cluster exists.
* Required topics exist.
* Confluent API key/secret and bootstrap are present in SSM.

3. **Local environment ready (default compute path)**

* AWS credentials active (profile/role) with least-privilege access to:

  * S3 buckets/prefixes
  * SSM `/fraud-platform/dev_min/*`
  * DynamoDB lock table (+ optional quarantine index)
* Runtime config points to:

  * env = `dev_min`
  * Kafka bootstrap from SSM
  * S3 bucket map from Terraform outputs/config

### 13.2 Bring-up steps (pinned)

The demo bring-up MUST be a reproducible sequence:

1. **Apply core**

* If not already present:

  * `terraform apply` in `infra/terraform/dev_min/core`

2. **Apply demo**

* `terraform apply` in `infra/terraform/dev_min/demo`
* Validate Confluent outputs are written to SSM (SecureString)

3. **Validate prerequisites**

* Read SSM parameters:

  * bootstrap + api_key + api_secret
* Confirm Kafka topics exist (topic list check)
* Confirm S3 evidence bucket is writable (write a small marker object)

### 13.3 Load sealed inputs (pinned)

* Upload or confirm presence of sealed oracle outputs in S3 under the run-scoped prefix.
* Confirm the `stream_view` exists (or is materialized) and is time-sorted per spec expectations. 

### 13.4 Execute the demo run (pinned)

The operator runs the demo workflow:

1. **Start run**

* Generate `platform_run_id`
* Derive/validate `scenario_run_id`
* Write run header + config digest to the evidence prefix

2. **Gate + READY**

* SR validates gates
* SR emits READY (control topic and/or evidence event)

3. **Stream + ingress + decision loop**

* WSP streams traffic/context into IG
* IG admits/dedupes/quarantines and publishes admitted events to Kafka
* RTDL consumes and produces decisions/audit (DLA)
* CM/LS run if included (case/label plane)

4. **Close run**

* Produce reconciliation + snapshot summaries
* Write replay anchor (offset range) summary
* Mark run completed in evidence

### 13.5 Incident drills (pinned)

The demo MUST include at least one incident drill, recorded in evidence:

* **Duplicates drill:** inject duplicate event(s) with same dedupe tuple and same payload_hash; verify DUPLICATE receipts and no double-actions.
* **Missing context drill:** cause a traffic event to arrive before its context; verify explicit degrade and provenance recorded.
* **Integrity mismatch drill (optional but strong):** same dedupe tuple with different payload_hash; verify anomaly/quarantine routing.

Each drill MUST produce:

* a drill identifier in the evidence bundle
* expected vs observed outcomes
* counts in anomaly/receipt summaries

### 13.6 Evidence collection checklist (pinned)

After run closure, the operator MUST verify in S3:

* `evidence/runs/<platform_run_id>/run.json` exists
* ingress receipt summary exists
* DLA/audit summary exists
* replay anchors (offset ranges) exist
* metrics/anomaly/reconciliation summaries exist
* drill records exist (at least one)

Optional (but recommended):

* a small audit slice file
* screenshots/exports of any dashboards used

### 13.7 Teardown (pinned)

After evidence verification, the operator MUST tear down demo infra:

1. **Destroy demo stack**

* `terraform destroy` in `infra/terraform/dev_min/demo`

2. **Confirm teardown**

* Confluent cluster/topics destroyed (or at minimum disabled/paused per provider behavior)
* SSM Confluent parameters removed (or invalidated per destroy)
* No ECS tasks/services or load balancers remain (if created)
* No VPC/NAT resources remain (if created)

3. **Core remains**

* S3 evidence remains intact
* Terraform state remains intact
* Budgets/alerts remain intact

---

## 14. Teardown, Retention, and Data Lifecycle

This section pins what survives teardown, and how data is lifecycle-managed so the platform remains budget-safe while preserving portfolio evidence.

### 14.1 What survives teardown (pinned)

After a normal `dev_min` demo session and teardown:

* **MUST remain (persistent):**

  * S3 evidence for completed runs (`evidence/` prefix)
  * S3 terraform state bucket + versions (state history)
  * DynamoDB terraform lock table
  * AWS Budgets/alerts configuration
  * IAM scaffolding (roles/policies) needed for future demos

* **MUST NOT remain (ephemeral):**

  * Confluent Cloud Kafka cluster/topics/service accounts/API keys created for demo
  * Any demo compute in AWS (ECS tasks/services)
  * Any load balancers (if created)
  * Any demo VPC resources (if created)

This is the default “demo → destroy” posture.

### 14.2 Data retention classes (pinned)

All dev_min data falls into one of three retention classes:

1. **Evidence (keep)**

* Operator-intended, portfolio-grade artifacts that support claims.
* Stored under `evidence/`.
* Retention: long enough to support portfolio demos (default: keep until you choose to delete).

2. **Run inputs and operational working data (short-lived)**

* Oracle outputs and stream_views that can be regenerated.
* Stored under `oracle/`.
* Retention: short (default: 14 days).

3. **Quarantine and operational byproducts (short/medium)**

* Quarantine payloads and indexes (useful for drill evidence, not forever).
* Stored under `quarantine/`.
* Retention: medium (default: 30 days).

4. **Archive (bounded in dev_min)**

* Archive outputs can grow quickly; in dev_min we keep it bounded.
* Stored under `archive/`.
* Retention: default 30–60 days (enough for learning-plane experiments later without runaway cost).

### 14.3 S3 lifecycle rules (pinned defaults)

Core stack MUST create S3 lifecycle policies (defaults; can be changed later with explicit repin):

* `oracle/`:

  * expire objects after **14 days**
* `quarantine/`:

  * expire objects after **30 days**
* `archive/`:

  * expire objects after **60 days**
* `evidence/`:

  * **no automatic expiry** by default (manual curation)

**MUST:** Buckets MUST have:

* versioning enabled (at least for tfstate and optionally evidence)
* public access blocked
* server-side encryption enabled

### 14.4 Log retention (pinned)

* **MUST:** CloudWatch log group retention must be short in dev_min:

  * default 3–7 days
* **MUST:** Anything you want to keep long-term must be exported into S3 evidence, not left in CloudWatch indefinitely.

### 14.5 Verification checklist after teardown (pinned)

After `dev-min-down`, the operator MUST verify:

* Demo Confluent resources are gone (or deactivated per provider behavior)
* SSM Confluent secret parameters are removed
* No ECS services/tasks remain (if used)
* No NAT Gateway exists
* No ALB/NLB exists
* Only core S3/Dynamo/IAM/Budgets remain

### 14.6 Evidence curation policy (pinned)

* **MUST:** Evidence bundles must be compact (summaries + small slices), not full raw stream dumps.
* **SHOULD:** Maintain a “top N best runs” set for your portfolio (e.g., one clean run, one duplicate drill run, one integrity mismatch run).
* **MAY:** Copy selected evidence bundles into a separate “portfolio spotlight” prefix for quick sharing.

---

## 15. Acceptance Gates (Definition of Done for `dev_min`)

This section pins what must be true before `dev_min` is considered complete and ready to use as a portfolio-grade “production-like” demo environment.

### 15.1 Infrastructure gates (IaC + cost posture)

`dev_min` passes infra gates only if all are true:

1. **Core apply/destroy correctness**

* **MUST:** `terraform apply` succeeds in `infra/terraform/dev_min/core`
* **MUST:** `terraform destroy` succeeds in `infra/terraform/dev_min/core` (when intentionally run)

2. **Demo apply/destroy correctness**

* **MUST:** `terraform apply` succeeds in `infra/terraform/dev_min/demo`
* **MUST:** `terraform destroy` succeeds in `infra/terraform/dev_min/demo`
* **MUST:** Demo destroy leaves no cost-bearing resources behind (Confluent Kafka cluster/topics/API keys removed; any AWS demo resources removed).

3. **Budget guardrails exist**

* **MUST:** AWS Budgets alert(s) exist for the £30 cap with at least 3 thresholds (e.g., £10/£20/£28).
* **MUST:** A teardown checklist exists in docs and is runnable by a single operator.

4. **Cost footguns absent**

* **MUST:** No NAT Gateway exists.
* **MUST:** No always-on ALB/NLB exists as a dependency of normal operation.
* **MUST:** No always-on compute fleet exists in AWS for `dev_min`.

### 15.2 Semantic gates (laws preserved)

`dev_min` passes semantic gates only if all are true:

1. **Ingress laws preserved**

* **MUST:** Deduplication uses `(platform_run_id, event_class, event_id)`.
* **MUST:** Duplicate drill produces DUPLICATE receipts and does not create double actions.
* **MUST:** Payload hash mismatch drill routes to anomaly/quarantine (no overwrite).

2. **Append-only evidence preserved**

* **MUST:** Receipts are append-only.
* **MUST:** Audit/decision logs are append-only.
* **MUST:** Labels/case timelines remain append-only.

3. **Replay anchors preserved**

* **MUST:** origin_offset evidence is recorded.
* **MUST:** Evidence bundle contains offset range summary sufficient for replay proof.

4. **Explicit degrade preserved**

* **MUST:** Missing context drill results in explicit degrade with reason recorded into audit evidence.

### 15.3 Operational gates (runbook + evidence)

`dev_min` passes operational gates only if all are true:

1. **Runbook runnable**

* **MUST:** A single operator can follow the Demo-Day Runbook end-to-end.
* **MUST:** Operator commands exist for:

  * `dev-min-up`
  * `dev-min-run`
  * `dev-min-down`
    (names flexible; semantics required)

2. **Evidence bundle exists and is complete**
   For a completed run, S3 contains:

* run header (`run.json`)
* ingress receipt summary
* audit/decision summary
* replay anchors (offset ranges/checkpoints summary)
* metrics/anomaly/reconciliation summaries
* incident drill record(s)

3. **Destroy-by-default proven**

* **MUST:** After `dev-min-down`, only core resources remain plus S3 evidence.
* **MUST:** Operator can demonstrate (via AWS console or CLI) that no expensive resources remain.

### 15.4 “Portfolio claim” gate (the human test)

`dev_min` is only considered done if you can honestly show:

* a single run’s evidence bundle,
* a second run demonstrating at least one incident drill,
* and a deterministic replay proof narrative anchored by offsets/evidence,
  without hand-waving or “trust me, it worked locally.”

---

## 16. Drift Watchlist and Change Control

This section pins how we detect drift (implementation diverging from intended flow/laws) and how changes are proposed without silently redesigning the platform.

### 16.1 What counts as drift (pinned)

Any of the following is considered **design drift** and MUST trigger stop-the-line:

1. **Identity / correlation drift**

* `platform_run_id` or `scenario_run_id` not carried through control/evidence surfaces.
* `platform_run_id` not used as the primary correlation key in run evidence.

2. **Ingress law drift**

* Dedupe key not exactly `(platform_run_id, event_class, event_id)`.
* Payload hash mismatches treated as “update” rather than anomaly/quarantine.
* Publish ambiguity treated as “assume success/failure” without explicit state.

3. **Evidence / audit drift**

* Receipts/audit/labels/case timelines mutated in place (not append-only).
* Replay proof depends on time windows rather than recorded origin_offset ranges.

4. **Degrade drift**

* Missing context resolved by silent defaulting/guessing rather than explicit degrade.
* Degrade posture not recorded into audit/evidence outputs.

5. **Env ladder drift**

* `dev_min` introduces major new dependencies (K8s/Flink/Temporal) without explicit repin.
* `dev_min` becomes “always-on” rather than demo → destroy.

6. **Budget drift**

* NAT Gateway introduced.
* Always-on ALB introduced.
* Always-on compute fleet introduced.
* MSK provisioned cluster introduced.

### 16.2 How Codex proposes changes (pinned protocol)

If Codex believes a pinned decision must change, it MUST:

1. **Open a PR** that includes:

* a concise “Change Request” section in the PR description
* the exact pinned clause(s) affected (by section number)
* the proposed new decision wording

2. **Add a decision-log entry** (Section 17) including:

* what changed
* why it changed
* what alternatives were rejected
* risk/impact (especially on budget and semantic laws)

3. **Do not implement silent changes**

* Codex MUST NOT “just implement” a changed decision and hope it’s accepted.
* No drift-by-implementation.

### 16.3 Post-run flow audit ritual (pinned)

After each full `dev_min` demo run, we MUST perform a quick flow audit:

* Confirm run evidence bundle completeness (Section 11.4)
* Confirm incident drill recording (Section 13.5)
* Confirm no expensive resources remain post-teardown (Section 14.5)
* Confirm semantic invariants still hold (Section 7)

This is the recurring guardrail that prevents slow drift into a “glorified toy” or an “infra science project.”

### 16.4 Change frequency and scope rules (pinned)

* `dev_min` is a stabilization track: changes should prefer **small, reversible** moves.
* Any change that increases cost posture or adds operational burden must be justified against the £30/month cap and demo → destroy posture.

---

## 17. Open Decisions Log (v0)

This section explicitly lists items that are **not pinned** yet. Codex must not “fill gaps” by invention; if any of these become necessary to implement, they must be surfaced as a decision request and then pinned.

### 17.1 Open items (not pinned yet)

1. **Exact Kafka topic name map**

* We have pinned “Kafka topics exist for traffic/context/control/audit/case/labels,” but we have **not pinned** the exact canonical topic names, partition counts, retention, or compaction policies for dev_min.
* Action: Codex proposes a topic map in Appendix C and we pin it.

2. **Confluent cluster type/region**

* Not pinned: Confluent cluster “type” (basic/standard/dedicated), cloud provider/region pairing, and whether clusters are created per demo or reused across multiple demos.
* Pinned constraint still applies: demo → destroy as the default. If reuse is proposed, it must include a cost justification and a teardown policy.

3. **Compute placement for demos**

* Not pinned: whether demo-day compute runs entirely local (recommended baseline) or partly in AWS (ECS tasks).
* Pinned constraint: if AWS compute is used, it must be ephemeral and must not require NAT or always-on ALB.

4. **Managed Postgres vs local Postgres in dev_min**

* Not pinned: whether CM/LS and receipts use a managed Postgres in dev_min or remain local with evidence export.
* Constraint: evidence bundle must be complete regardless.

5. **Join plane substrate in dev_min**

* Not pinned: whether CSFB/join-plane state is moved to managed Redis in dev_min.
* Constraint: do not let this become a blocker for dev_min; it’s optional.

6. **Step Functions vs CLI orchestration**

* Allowed: Step Functions.
* Not pinned: whether it is required for v0 dev_min or whether a CLI pipeline is sufficient.
* Constraint: operator run procedure must exist and be repeatable.

7. **Evidence bundle exact schema**

* We pinned required contents and S3 prefix layout, but not the exact JSON schema files for run.json, receipt summary, offset summary, etc.
* Action: Codex proposes minimal schemas; we pin them.

8. **Budget enforcement mechanism**

* We pinned “AWS Budgets alerts exist,” but did not pin whether a hard-stop mechanism exists (e.g., teardown on threshold).
* Constraint: do not add complex automation until the base is stable.

### 17.2 How to close open decisions (pinned process)

For each open item that becomes implementation-relevant:

* Codex drafts the proposed decision in PR notes (one screen max).
* Designer pins it by updating this section and (if needed) the relevant pinned sections.
* Only then does Codex implement it.

### 17.3 Future upgrades (not pinned, direction only)

These are explicitly “later”:

* dev_full: richer dashboards/alerts, stronger identity posture, optional Temporal, optional managed Redis
* prod_target: multi-AZ, stricter governance, compliance posture, stronger data lake cataloging

---

## 18. Appendices

### Appendix A. Resource Swap Table (local_parity → dev_min → dev_full → prod_target)

This table is **normative for dev_min direction**: it pins what dev_min is allowed/required to swap in, and what remains optional for later rungs.

| Plane/Layer        | Component             | local_parity (reference harness) | dev_min (pinned target)                                    | dev_full (optional)                | prod_target (aspirational)         |
| ------------------ | --------------------- | -------------------------------- | ---------------------------------------------------------- | ---------------------------------- | ---------------------------------- |
| World Builder      | Oracle Store          | MinIO                            | **AWS S3**                                                 | S3 + tighter posture               | S3 + Object Lock/WORM + governance |
| World Builder      | Scenario Runner (SR)  | Compose/local                    | **Local (default)** or ephemeral ECS                       | ECS/EKS + autoscale                | EKS + policy releases              |
| World Builder      | READY/control         | Local control bus                | **Kafka control topic** (Confluent)                        | Kafka + orchestration signals      | Kafka + Temporal signaling         |
| World Builder      | WSP                   | Compose/local                    | **Local (default)** or ephemeral ECS task                  | KStreams/Flink if needed           | Managed Flink/Spark Streaming      |
| Control/Ingress    | Event Bus (EB)        | Redpanda/LocalStack              | **Confluent Cloud Kafka**                                  | Kafka tuned (retention/partitions) | Kafka multi-AZ + tiered storage    |
| Control/Ingress    | IG                    | Compose/local                    | **Local (default)** or ephemeral ECS                       | ECS/EKS + autoscale                | EKS + strict mTLS/rate controls    |
| Control/Ingress    | Quarantine payloads   | Local/MinIO                      | **S3**                                                     | S3 + lifecycle + alarms            | S3 + compliance posture            |
| Control/Ingress    | Quarantine index      | Local DB/files                   | **DynamoDB (recommended)**                                 | DynamoDB + TTL + alarms            | DynamoDB streams → workflows       |
| Control/Ingress    | Receipts store        | Local Postgres/files             | **Evidence summary in S3 (MUST)**; internal store flexible | Postgres managed optional          | Evidence lake + query views        |
| RTDL               | Projections (IEG/OFP) | Local workers                    | **Local (default)** using Kafka consumer groups            | KStreams scaled                    | Flink stateful jobs                |
| RTDL               | Join plane (CSFB)     | Local/in-mem                     | **Optional** (may remain local)                            | Managed Redis                      | Redis Enterprise/Aerospike         |
| RTDL               | DF/AL/DLA             | Local                            | **Local (default)** consuming Kafka + writing evidence     | ECS/EKS optional                   | EKS + stronger posture             |
| RTDL               | Audit lake            | Local files                      | **S3 evidence slices/summaries (MUST)**                    | S3 Parquet/Iceberg                 | Iceberg/Delta + catalog            |
| Label/Case         | Operational DB        | Local Postgres                   | **Optional** managed Postgres (may remain local)           | Managed Postgres recommended       | Aurora multi-AZ + PITR             |
| Label/Case         | CM/LS services        | Local                            | **Local (default)** with evidence export                   | ECS/EKS optional                   | Enterprise auth + compliance       |
| Learning/Evolution | Archive               | Local                            | **S3 archive prefix (bounded)**                            | S3 Parquet/Iceberg                 | Iceberg/Delta lakehouse            |
| Learning/Evolution | OFS                   | Local job                        | **Optional** (not required for dev_min)                    | Glue/EMR/Databricks                | Databricks/Snowflake pipelines     |
| Learning/Evolution | MF orchestration      | Scripts                          | **Optional** Step Functions (allowed)                      | Step/SageMaker/Temporal            | Kubeflow/SageMaker                 |
| Meta               | IaC                   | Compose                          | **Terraform (MUST)**                                       | Terraform + policy checks          | modules + drift detection          |
| Meta               | Budgets               | None/manual                      | **AWS Budgets alerts (MUST)**                              | + anomaly detection                | org-wide cost governance           |
| Meta               | Logs/Metrics/Traces   | Local logs                       | **Minimal posture + S3 evidence (MUST)**                   | OTel collector + dashboards        | Datadog/Prometheus/Jaeger          |

**Notes (pinned interpretation):**

* “Local (default)” in dev_min means: compute runs on your machine, but uses **Confluent Kafka + AWS S3** as the managed substrate.
* Any move of compute into AWS is allowed only as **ephemeral demo infra** (destroy-by-default) and must respect the “no NAT / no always-on LB” prohibitions.

---

### Appendix B. Cost Model Worksheet (Dev-min ≤ £30/mo; demo → destroy)

This appendix pins the **cost envelope**, the **cost drivers**, and the **guardrails** Codex must implement so `dev_min` stays budget-safe while remaining portfolio-credible. 

---

#### B.1 Budget Envelope (PINNED)

* **Total monthly cap (hard):** **≤ £30 / month**
* **Default posture:** **demo → destroy** (demo stack exists only during demo windows). 
* **Budget split target (guidance, not a price claim):**

  * **AWS core (always-on):** aim **≤ £5 / month**
  * **Kafka provider (Confluent) + demo-time extras:** aim **≤ £25 / month**
* **Primary lever:** *uptime hours* of demo resources (Kafka cluster + any AWS demo compute).

**Monthly cost model (worksheet formula):**

* `monthly_total ≈ aws_core_baseline + Σ(demo_session_cost) + confluent_monthly_usage`
* Where `demo_session_cost ≈ demo_hours × (kafka_hourly + optional_compute_hourly + optional_lb_hourly) + per_run_io`

---

#### B.2 What is allowed to cost money (PINNED)

Only these are permitted to accumulate cost across months:

**Core (allowed to be always-on; must be minimal)**

* S3 buckets (oracle/archive/quarantine/evidence/tfstate)
* DynamoDB lock table (and optional small index tables)
* AWS Budgets/alerts
* IAM scaffolding
* Minimal CloudWatch log groups (short retention) 

**Demo (allowed to cost money only during demo windows)**

* Confluent Cloud Kafka cluster + topics
* Optional Step Functions state machine executions
* Optional ECS tasks/services (only if you choose to run compute in AWS)
* Optional load balancer (only if explicitly needed for a demo) 

---

#### B.3 Cost drivers checklist (WHAT to watch)

**AWS cost drivers**

1. **S3**

   * Storage growth (especially `archive/`)
   * Requests (PUT/LIST can grow if you dump raw streams)
   * Data transfer/egress (avoid pulling big data out repeatedly)
2. **CloudWatch**

   * Log ingestion volume + retention duration (cap via retention policy)
3. **Step Functions (if used)**

   * State transitions per run (keep workflow simple; avoid chatty state machines)
4. **ECS/Compute (if used)**

   * CPU/RAM hours (keep tasks short-lived)
5. **Load balancers (if used)**

   * Hourly cost even when idle → avoid except for a specific demo need
6. **Networking**

   * **NAT Gateway** is a known budget trap → **prohibited** (Section 5.4). 

**Confluent Cloud cost drivers**

* Cluster uptime (hours/day)
* Throughput (GB in/out)
* Topic/partition footprint + retention + storage
* Egress (if you move data out frequently)

---

#### B.4 Guardrails Codex MUST implement (PINNED)

1. **AWS Budgets + alerts**

   * Budget for **£30/month** with alert thresholds at **£10 / £20 / £28**
2. **Tagging for cost allocation**

   * All AWS resources must be tagged: `project`, `env`, `owner`, `expires_at`
3. **Lifecycle policies (S3)**

   * `oracle/` expire ~14 days
   * `quarantine/` expire ~30 days
   * `archive/` expire ~60 days
   * `evidence/` default: no expiry (manual curation) 
4. **CloudWatch retention**

   * 3–7 days (dev_min) 
5. **Destroy-by-default enforcement**

   * `dev-min-down` MUST destroy demo resources (Kafka + secrets + any demo compute)

---

#### B.5 “Cost Kill Switch” runbook (PINNED)

At the end of every demo session, the operator MUST run:

* `dev-min-down` (Terraform destroy demo stack)

Then MUST verify:

* Confluent cluster/topics destroyed (or deactivated per provider behavior)
* SSM Confluent secret parameters removed
* No ECS services/tasks remain (if used)
* No ALB/NLB exists
* No NAT Gateway exists 

---

#### B.6 Optional AWS-native Kafka “flex demo” (NOT REQUIRED; if added, strict constraints)

If Codex adds an optional MSK Serverless “AWS-native Kafka” module, it MUST be:

* Feature-flagged
* Demo-only (created only for a demo run; destroyed immediately after)
* Never required for dev_min acceptance gates
* Accompanied by a stricter teardown checklist entry (prove it’s gone)

---

#### B.7 Measurement & reporting (PINNED)

* **AWS:** operator must be able to confirm spend using AWS Billing/Cost Explorer scoped by tags (`project=fraud-platform`, `env=dev_min`).
* **Confluent:** operator must be able to confirm Kafka usage/spend from Confluent Cloud usage dashboards.
* **Evidence:** each demo run’s evidence bundle MUST include:

  * demo session start/end timestamps
  * resources used (Kafka cluster identity, S3 bucket map)
  * any “flex demo” toggles used (if applicable)

---

#### B.8 Cost acceptance gate (PINNED)

Dev-min is considered budget-safe only if:

* You can run at least **two demo sessions in a month** (each including an incident drill + evidence bundle) and remain **≤ £30/month** by destroying demo infra afterwards.

---

### Appendix C. Topic Map (names, partitions, retention defaults)

This appendix **pins the dev_min Kafka topic set** (Confluent Cloud). It is aligned to the topic names already used in your flow narrative + local_parity runbook, and extends it with minimal Case/Label topics.    

#### C.1 Pinned defaults (apply to all topics unless overridden below)

* **cleanup.policy:** `delete` (no compaction in v0 dev_min)
* **retention:**

  * **High-volume topics:** 1 day (`retention.ms = 86400000`)
  * **Low-volume control/governance topics:** 3 days (`retention.ms = 259200000`)
* **partitions:**

  * **High-volume topics:** 3 partitions
  * **Low-volume topics:** 1 partition
* **Replication factor:** use Confluent cluster default (do not override in v0)
* **Envelope rule:** every record MUST carry `ContextPins` (including `platform_run_id`, `scenario_run_id`) and a deterministic `event_id` (or deterministic message id for control/governance events). 

---

#### C.2 Topic set (fraud-mode dev_min demo)

| Topic                                 |                       Required? | Producer                                        | Primary consumer(s)                              | Partitions | Retention | Partition key (pinned)                              |
| ------------------------------------- | ------------------------------: | ----------------------------------------------- | ------------------------------------------------ | ---------: | --------: | --------------------------------------------------- |
| `fp.bus.control.v1`                   |                             YES | SR + run reporter + governance/anomaly emitters | WSP READY consumer; operator/reporting tools     |          1 |        3d | `platform_run_id`                                   |
| `fp.bus.traffic.fraud.v1`             |                             YES | IG (admitted traffic)                           | RTDL decision trigger inlet; archive writer      |          3 |        1d | IG partitioning profile (default: `merchant_id`)    |
| `fp.bus.context.arrival_events.v1`    |                             YES | IG (admitted context)                           | RTDL context inlet; archive writer               |          3 |        1d | `merchant_id` (merchant-local partitioning)         |
| `fp.bus.context.arrival_entities.v1`  |                             YES | IG (admitted context)                           | RTDL context inlet; archive writer               |          3 |        1d | `merchant_id` (merchant-local partitioning)         |
| `fp.bus.context.flow_anchor.fraud.v1` |                             YES | IG (admitted context)                           | RTDL FlowBinding/JoinFrame inlet; archive writer |          3 |        1d | `merchant_id` (merchant-local partitioning)         |
| `fp.bus.audit.v1`                     |                             YES | DLA (append-only audit events)                  | CM (by-ref evidence); archive/evidence sinks     |          3 |        3d | `platform_run_id` (or `decision_id` if present)     |
| `fp.bus.rtdl.v1`                      | YES (for decision-lane publish) | DF/AL lane (decision packages / lane events)    | AL/DF lane consumers; evidence sinks             |          3 |        1d | `decision_id` if present else `platform_run_id`     |
| `fp.bus.case.triggers.v1`             |   YES (if CM consumes triggers) | CaseTrigger writer (thin) or RTDL/AL            | CM                                               |          1 |        3d | `case_id` (where `case_id = hash(CaseSubjectKey)`)  |
| `fp.bus.labels.events.v1`             |  OPTIONAL (derived events only) | LS after durable commit (or CM when requesting) | Learning-plane hooks / reporters                 |          1 |        3d | `platform_run_id` (or `event_id`)                   |

**Also provision (optional baseline mode compatibility):**

* `fp.bus.traffic.baseline.v1` (optional traffic mode) 
* `fp.bus.context.flow_anchor.baseline.v1` (optional baseline context mode) 

---

#### C.3 Pinned notes (important semantics tied to topics)

* **Four admitted RTDL inputs for fraud-mode are fixed** (traffic + 3 context streams):
  `fp.bus.traffic.fraud.v1`, `fp.bus.context.arrival_events.v1`, `fp.bus.context.arrival_entities.v1`, `fp.bus.context.flow_anchor.fraud.v1`. 
* **Anomalies/governance facts** are emitted to **`fp.bus.control.v1`** (low volume, append-only). 
* **Context topics are merchant-local by partitioning** → partition key is pinned to `merchant_id` for all `fp.bus.context.*` topics. 
* **Traffic policy:** one traffic stream per run (baseline OR fraud). Fraud is the dev_min default. 

This appendix closes Open Decision **17.1(1)** (“Exact Kafka topic name map”).

---

### Appendix D. Troubleshooting Quick Hits (Common AWS/Kafka Footguns)

This appendix is a practical “save time” list for `dev_min` demos. It’s **non-normative**, but it aligns with the pinned prohibitions (no NAT, no always-on LB) and with the Kafka + S3 evidence posture.

#### D.1 Confluent Cloud Kafka connection problems

**Symptom:** clients can’t connect / auth fails

* Verify SSM secrets exist and are current:

  * `/fraud-platform/dev_min/confluent/bootstrap`
  * `/fraud-platform/dev_min/confluent/api_key`
  * `/fraud-platform/dev_min/confluent/api_secret`
* Verify your client config uses **SASL_SSL** (Confluent standard):

  * mechanism: `PLAIN` (typical) unless you configured otherwise
* Verify you didn’t rotate credentials by re-applying demo stack without reloading env vars.

**Symptom:** “topic authorization failed”

* Confirm ACLs/RBAC include:

  * `READ`/`DESCRIBE` for consumers
  * `WRITE`/`DESCRIBE` for producers
* Confirm the service account used by your local runtime matches the API key in SSM.

#### D.2 Consumer group “weirdness” (replays not behaving)

**Symptom:** consumer starts at “end” and misses messages

* In a demo, your consumer group may already have committed offsets.
* Use a **new group id** per run or per demo session (recommended).
* Evidence still must record the `origin_offset` ranges you consumed.

**Symptom:** you “replay” but results differ

* Check that your `platform_run_id` is new (or intentionally identical) and that the run config digest changed/held as expected.
* Confirm you didn’t change topic retention/compaction mid-run.
* Confirm deterministic `event_id` generation is unchanged.

#### D.3 Retention too short / data “disappears”

**Symptom:** you try to inspect messages later, but they’re gone

* High-volume topics are pinned to short retention in dev_min (default 1 day).
* The “forever truth” is **S3 evidence + archive**, not Kafka.
* If you need longer inspection windows for a specific demo, explicitly bump retention *for that demo only*.

#### D.4 S3 permissions errors (AccessDenied)

**Symptom:** can’t read/write to buckets/prefixes

* Confirm AWS profile/role in use matches the IAM policy expected.
* Verify bucket public access block doesn’t block your access (it shouldn’t—this only blocks public).
* Verify you’re writing to the correct prefix (`evidence/runs/<platform_run_id>/...`).

#### D.5 Terraform state / lock issues

**Symptom:** “state lock” errors

* Ensure the DynamoDB lock table exists (core stack applied).
* If you hard-killed a terraform process, the lock may be stuck — unlock only if you’re sure no apply is running.

**Symptom:** secrets appear in state outputs

* That’s expected: Terraform state can contain provider-managed values.
* Treat tfstate bucket as sensitive; do not print outputs to logs; keep bucket private.

#### D.6 AWS cost footguns (what to check after each demo)

**Symptom:** bills rising even when “nothing is running”

* Check for forbidden/accidental resources:

  * NAT Gateway (must not exist)
  * Load balancers (ALB/NLB)
  * ECS services with desired count > 0
* Confirm demo stack destroy actually removed Confluent resources (or at least removed keys and cluster resources if provider behavior differs).

#### D.7 Evidence bundle missing / incomplete

**Symptom:** run “worked” but evidence bundle isn’t complete

* Treat this as a **failed run** for dev_min purposes.
* Ensure the run closure step writes:

  * run header
  * receipt summary
  * audit summary
  * replay anchors
  * metrics/anomaly/reconciliation snapshots
  * drill record(s)
* If a stage fails mid-run, still write a partial evidence record with failure stage + offsets consumed so far.

#### D.8 Partitioning mismatch (hot partitions / weird ordering)

**Symptom:** unexpected ordering, missing joins, or hot partition

* Context topics must partition by `merchant_id`.
* Traffic partition key should align with your IG partitioning profile (default merchant-local).
* If you deviate, document it and confirm join readiness constraints still behave as designed.

#### D.9 “It’s slow” during demos

* Dev_min is about proving managed substrate + evidence, not max throughput.
* Keep demo datasets small.
* Reduce log verbosity.
* Keep Kafka partitions small (3 is fine).
* Ensure you’re not doing expensive S3 LIST operations repeatedly.

---