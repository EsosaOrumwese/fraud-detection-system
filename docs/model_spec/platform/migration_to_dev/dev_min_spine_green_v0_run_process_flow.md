# DEV_MIN — SPINE GREEN v0 RUN PROCESS FLOW (Twin of Local Parity)

## 0. Document Control

### 0.1 Status

* **Status:** v0 (draft-initial; Sections 0–1 complete)
* **As-of:** 2026-02-12 (Europe/London)
* **Scope:** **Spine Green v0 only** (Control+Ingress, RTDL, Case+Labels, Run/Operate+Obs/Gov). **Learning/Registry (OFS/MF/MPR) is explicitly out-of-scope** for this runbook translation.

### 0.2 Roles and Audience

* **Designer / Spec Authority:** GPT-5.2 Thinking (this document is authoritative for dev_min run execution + gates)
* **Implementer:** Codex (executes implementation within pinned bounds)
* **Operator:** You (runs bring-up/run/teardown and checks evidence)
* **Primary audience:** Codex + Operator (execution + wiring)
* **Secondary audience:** reviewers validating “no drift” vs local_parity semantics

### 0.3 Authority Boundaries

**Pinned (MUST follow)**

* This runbook is a **dev_min translation** of the local_parity **Spine Green v0** phase machine `P0..P11` (with `P12` teardown). Phase ordering, retry rules, and the meaning of PASS gates are preserved.
* `dev_min` must satisfy the dev-min migration authority: **managed Kafka (Confluent)** + **AWS S3 for oracle/archive/quarantine/evidence**, strict **demo → destroy**, **~£30/mo cap**, and **no NAT / no always-on LB / no always-on fleets**. 
* **No laptop dependency:** laptop is operator-only; runtime compute for the platform is managed/ephemeral (ECS tasks/services). 
* **Orchestration posture:** v0 dev_min remains **CLI-orchestrated** (no Step Functions in v0). 
* **Semantic invariants MUST NOT change across envs** (schemas/envelopes/pins/dedupe/append-only/evidence basis/explicit degrade).

**Implementer freedom (Codex MAY choose)**

* ECS decomposition (task vs service per phase), sizing, and deployment mechanics, **as long as** all pinned gates and proofs are satisfied and demo→destroy is preserved.
* Exact Terraform module decomposition and naming (within pinned handles registry conventions to be defined next).

### 0.4 Precedence

If any conflict appears, follow this precedence:

1. `dev-min_managed-substrate_migration.design-authority.v0.md` (migration authority, prohibitions, budget posture) 
2. This runbook twin (dev_min execution and phase-by-phase translation)
3. Local parity phase semantics + gates + job cards (source truth for “meaning”)
4. Platform pre-design decisions (Control/Ingress, RTDL, Case/Labels, Run/Operate, Obs/Gov)

### 0.5 Normative References (source truth)

**Local parity “meaning” sources (Spine Green v0)**

* `spine_green_v0_run_process_flow.txt` (canonical spine flow capture, scope lock)
* `addendum_1_phase_state_machine_and_gates.txt` (phase machine + retry rules + commit evidence per phase)
* `addendum_1_operator_gate_checklist.txt` (operator PASS checks per phase) 
* `addendum_2_process_job_cards.txt` (process/job semantics, IO ownership notes, fail-closed behaviors) 

**Dev-min migration authority**

* `dev-min_managed-substrate_migration.design-authority.v0.md` 
* `addendum_1_phase_to_packaging_map.txt` (dev_min packaging target per phase; “no laptop compute”, “CLI-only”, “demo→destroy”) 

---

## 1. Pinned Global Decisions (Dev-min v0)

### 1.1 Scope lock (Spine Green v0)

* **IN SCOPE:** phases `P0..P11` that constitute Spine Green v0 (Control+Ingress, RTDL, Case+Labels, Run/Operate+Obs/Gov).
* **OUT OF SCOPE:** Learning/Registry (`OFS/MF/MPR`) — must not be required for dev_min “green”.

### 1.2 Canonical phase IDs and lifecycle

* The **only** canonical identifiers for run phases are `P0..P11` (and `P12` teardown).
* The phase order and retry loops are inherited from the local parity phase machine (e.g., P3 per-output rerun, P5 SR lease rules, P11 single-writer constraints).

### 1.3 No laptop dependency (runtime compute policy)

* **MUST:** no platform runtime compute executes on the laptop in dev_min. 
* **MUST:** all phases that execute code run as **managed, destroyable compute** (ephemeral ECS tasks/services) within the demo window.
* **MUST:** laptop is operator-only (provision, trigger, inspect evidence). 

### 1.4 Substrate pins (dev_min = managed primitives)

* **Kafka (Event Bus backend):** Confluent Cloud Kafka (demo stack).
* **Object store (durable substrate):** AWS S3 (core stack) for:

  * oracle store
  * archive
  * quarantine payloads
  * evidence bundles (run closure)
* **State stores:** must be non-laptop. Exact product choices are pinned later in the **handles registry**, but the policy is already pinned: CM/LS require a managed runtime DB; IG/RTDL state must not rely on local files/SQLite.

### 1.5 Orchestration posture (v0)

* **MUST:** v0 dev_min remains **CLI-orchestrated** (no Step Functions).
* Operator commands must exist (names flexible; semantics required):

  * `dev-min-up` (bring up core+demo substrate, deploy services)
  * `dev-min-run` (execute phases P1..P11)
  * `dev-min-down` (destroy demo infra; core remains)

### 1.6 Budget posture + teardown discipline

* **MUST:** budget cap ~£30/mo with **demo → destroy** as the default posture.
* **MUST NOT:** NAT Gateway, always-on load balancers, always-on compute fleets.
* **MUST:** teardown is an explicit phase (P12) and is part of the definition of “dev_min done”.

### 1.7 Semantic invariants (no drift)

Dev_min is a substrate + packaging translation only. The following invariants remain:

* Run pins and correlation (`platform_run_id`, `scenario_run_id`) carried everywhere and treated as the run-scoped truth anchors.
* Fail-closed gating and explicit retry loops (no “best effort” skipping).
* “Stream view first”: WSP consumes `stream_view` outputs that are ordered and receipted (P3 is a **real batch job**, not an incidental step).

### 1.8 Writer-boundary auth posture (v0 dev_min)

* **MUST:** IG ingress remains a writer boundary that enforces auth (local parity shows API-key mode with `X-IG-Api-Key`); dev_min must preserve an equivalent writer-boundary check.
* **NOTE:** dev/prod-grade mTLS/signed service identity is a future hardening step; v0 dev_min preserves the writer-boundary *discipline* first (auth required, fail closed, attributed).

### 1.9 Evidence and “green” definition (dev_min)

* A phase is “green” only if its **exit gate** is satisfied and the **commit evidence** exists. Dev_min must re-materialize these gates against managed substrate outputs.
* Dev_min “Spine Green v0” means **P0..P11 PASS** using the dev_min equivalents of the operator checklist checks.

### 1.10 Open-but-required items (must be pinned in the handles registry before implementation)

These are not “optional”; they are simply not pinned in Sections 0–1 yet:

* Exact AWS resource names (S3 buckets, prefixes), Confluent cluster identifiers, topic parameters (partitions/retention), SSM parameter paths.
* Exact managed DB choice(s) for IG admission state, RTDL state, CM/LS timelines.
* ECR repo name(s) and image tag/digest recording policy.
* ECS cluster/network identifiers (subnets/SGs) consistent with “no NAT” and “demo→destroy”.

(We pin these in `dev_min_handles.registry.v0.md` next, so Codex can implement without inventing names.)

---

## 2. Definitions

This section defines the canonical terms used throughout the dev_min runbook twin. These definitions are **normative** for dev_min execution.

### 2.1 Environments and scope terms

* **`local_parity`**: the local harness environment where the spine run was proven green using local shims (MinIO/LocalStack/etc). This is the source-of-truth for *semantics* (what the phases mean and what gates require).
* **`dev_min`**: the managed-substrate environment for this runbook. It preserves the same phase semantics/gates but runs with:

  * managed Kafka (Confluent),
  * AWS S3 durable substrate,
  * managed runtime compute (no laptop dependency),
  * demo→destroy cost posture.
* **Spine Green v0**: the in-scope “green” baseline for migration planning. It includes **Control+Ingress**, **RTDL**, **Case+Labels**, **Run/Operate + Obs/Gov**. It explicitly excludes Learning/Registry (OFS/MF/MPR).

### 2.2 Canonical phase identifiers

* **Phase IDs (`P#`)**: the only canonical identifiers for the run lifecycle in this doc.

  * `P0..P11` are the Spine Green v0 phases.
  * `P12` is teardown (destroy demo infra).
* **Phase semantics**: the meaning of each phase (what it does, what gates it must satisfy) is inherited from the local parity phase state machine and operator checklist.

### 2.3 Identity and correlation terms

* **`platform_run_id`**: execution-scope identifier for a single platform run. It is the primary correlation key for evidence, logs, and run closure.
* **`scenario_run_id`**: deterministic scenario identity derived from an equivalence key; paired with `platform_run_id` during execution.
* **`event_id`**: deterministic identifier for an event instance (stable across retries).
* **`flow_id`**: deterministic flow anchor identifier used for flow-binding and (for some datasets) sorting/joins.
* **`ts_utc`**: canonical UTC timestamp used as the primary time ordering key for stream views.

### 2.4 Substrate terms

* **Oracle Store**: the sealed truth store holding engine outputs for a run. In dev_min this lives in AWS S3 under run-scoped prefixes.
* **`stream_view`**: the deterministic, sorted, stream-consumable materialization produced from oracle outputs. WSP MUST consume stream_view (not raw oracle outputs).
* **Event Bus (EB)**: the durable stream transport for admitted events. In dev_min, EB is Confluent Cloud Kafka topics.
* **Archive**: durable event history store. In dev_min, archive artifacts are stored in S3 under `archive/` (bounded in v0).
* **Quarantine**: routing destination for rejected/anomalous events; payloads and metadata are preserved for analysis and governance. In dev_min, quarantine is stored in S3 under `quarantine/`.

### 2.5 Compute and packaging terms

* **Managed compute**: any compute that is not the laptop (ECS tasks/services, Batch jobs, etc.). In dev_min, all runtime compute is managed/ephemeral. 
* **ECS Task**: a one-shot run (e.g., SR emit READY, WSP streaming run, oracle stream-sort job, reporter close).
* **ECS Service**: long-running daemon/workers (e.g., IG service, RTDL consumers, CM/LS APIs where applicable). 
* **Container image**: a built artifact containing the platform code and dependencies, pushed to a registry (ECR), referenced by ECS task/service definitions.

### 2.6 Evidence and gate terms

* **Gate / PASS**: a phase’s required acceptance checks. A phase is “green” only if its exit gate is satisfied and commit evidence exists.
* **Commit evidence**: the minimal set of artifacts that prove the phase completed correctly (examples: READY published, receipts written, audit slices produced, closure marker exists).
* **Evidence bundle**: run-scoped artifacts written to S3 under `evidence/runs/<platform_run_id>/...` capturing provenance, summaries, replay anchors, and closure. (Exact schema pinned later.)
* **Rollback**: a safe, explicit undo action that returns the system to a known state suitable for rerun (e.g., delete a run-scoped prefix, clear a lease, destroy demo infra).

### 2.7 Handles and the registry

* **Handle**: any named resource identifier required to run dev_min (bucket names, prefixes, topic names, SSM parameter paths, DB endpoints, ECS cluster names, task definitions).
* **Handles registry**: `dev_min_handles.registry.v0.md` is the single source of truth for all handles used in dev_min. Code and docs must reference handles defined there; no “random names” are allowed.

---

## 3. Dev-min Operator Overview (One screen)

This section is the “operator front page” for running Spine Green v0 on dev_min with **no laptop runtime dependency**. It is intentionally compact; phase details live in Section 5.

### 3.1 Operator posture (pinned)

* Operator machine (laptop) is used **only** to:

  * apply/destroy Terraform,
  * trigger runs (CLI),
  * inspect logs/evidence.
* All platform runtime compute executes on managed compute (ECS tasks/services). 

### 3.2 Primary operator commands (pinned semantics)

Implementations may choose exact CLI names, but the **three semantic actions** MUST exist:

1. **Bring-up**

* `dev-min-up`
* Meaning:

  * Apply **core** infra (AWS S3 + tfstate + lock + budgets + IAM scaffolding)
  * Apply **demo** infra (Confluent Kafka + topics + creds → SSM; runtime DB; ECS runtime deployment)
  * Validate prerequisites (handles resolvable; creds present; topics present; buckets writable)

2. **Run**

* `dev-min-run`
* Meaning:

  * Execute phases `P1..P11` in canonical order (per phase machine)
  * Produce the dev_min evidence bundle under:

    * `s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/...`
  * Enforce phase gates (fail closed)

3. **Teardown**

* `dev-min-down`
* Meaning:

  * Execute phase `P12` teardown discipline:

    * destroy demo infra (Kafka cluster/resources, ECS tasks/services, runtime DB, demo-only resources)
    * leave core infra + evidence intact
  * Verify “no expensive resources remain”

### 3.3 One-screen execution sequence (canonical)

```text
# 0) Bring up dev_min
dev-min-up

# 1) Run spine green v0 (P1..P11)
dev-min-run

# 2) Tear down demo infra (P12)
dev-min-down
```

### 3.4 Quick preflight checklist (operator)

Before `dev-min-run`, operator MUST be able to confirm:

* **Handles registry is populated** and consistent (no missing keys).
* **Kafka**:

  * Confluent cluster exists (demo scope)
  * required topics exist (Appendix C / handles registry)
  * bootstrap + api key/secret exist in SSM paths
* **S3**:

  * oracle bucket/prefix exists (seeded or will be seeded in P3 lane)
  * evidence bucket writable
* **Runtime DB** (for “no laptop dependency”):

  * endpoint reachable from runtime compute
  * credentials exist in SSM
* **ECR images**:

  * required image(s) exist and are referenced by ECS task/service defs

(Exact names/paths come from `dev_min_handles.registry.v0.md`.)

### 3.5 “Green” checkpoint summary (operator)

A run is considered Spine Green v0 on dev_min only if:

* All phase exit gates `P0..P11` pass (per operator checklist semantics).
* The evidence bundle exists in S3 and contains the required closure markers and summaries.
* Teardown (`P12`) leaves only core infra + evidence (demo resources destroyed).

---

## 4. Phase Map (Summary Table)

This table is the **one-screen backbone** of Spine Green v0 on `dev_min`: what each phase does, **where it runs**, what it reads/writes, what proves PASS, and how to roll back safely. Phase semantics and gate meanings are inherited from the local parity phase machine + operator checklist; packaging targets follow the dev_min packaging map and migration authority.

> **Handle rule:** any bucket/topic/SSM path/DB endpoint/ECR repo referenced below must be defined in `dev_min_handles.registry.v0.md` (single source of truth). No “random names” in code or docs.

| Phase | Name                     | Dev-min packaging target (no laptop runtime)                                                       | Primary IO (dev-min)                                                                      | Gate owner               | Proof anchor (dev-min)                                                                      | Rollback (safe undo)                                                                                                                   |
| ----- | ------------------------ | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| P(-1) | PACKAGING_READY          | **Operator**: build + push image(s) to ECR                                                         | ECR (images)                                                                              | Operator                 | Image digest/tag exists and is resolvable by ECS task defs                                  | Revert tag/digest pointer; delete failed image tag                                                                                     |
| P0    | SUBSTRATE_READY          | **Operator**: `terraform apply core` then `terraform apply demo`                                   | S3 + Dynamo lock + Budgets + SSM + Confluent Kafka + runtime DB + ECS cluster scaffolding | Operator                 | All handles resolvable; SSM secrets present; topics exist; buckets writable                 | `terraform destroy demo` (keep core); if core wrong, destroy core intentionally                                                        |
| P1    | RUN_PINNED               | **Operator CLI** (or one-shot ECS task if you prefer): create `platform_run_id`, pin config digest | S3 evidence prefix                                                                        | Operator                 | `evidence/runs/<platform_run_id>/run.json` (or equivalent run header) exists                | Delete `evidence/runs/<platform_run_id>/` prefix; re-run P1                                                                            |
| P2    | DAEMONS_READY            | **ECS services** up (IG, RTDL workers, CM/LS APIs as in-scope)                                     | ECS + runtime DB                                                                          | Operator (health checks) | Service health endpoints OK; CloudWatch logs show “started”; no crashloops                  | Scale services to 0 / redeploy; destroy demo if drifted                                                                                |
| P3    | ORACLE_READY             | **One-shot job(s)** on managed compute: seed/sync → stream-sort → checker                          | S3 oracle inputs → S3 `stream_view` outputs                                               | Oracle lane              | Stream-view receipt/manifest exists; checker PASS artifact exists                           | Delete `oracle/<run>/stream_view/...` prefix + receipts; rerun P3 (per-output allowed)                                                 |
| P4    | INGEST_READY             | **IG ECS service** reachable + topic readiness                                                     | IG endpoint + Kafka topics                                                                | Operator + IG            | IG health “ready”; topics exist; auth boundary active                                       | Roll IG deployment; clear only IG runtime state (not evidence)                                                                         |
| P5    | READY_PUBLISHED          | **SR one-shot ECS task** emits READY                                                               | S3 SR artifacts + Kafka control topic                                                     | SR                       | READY published + SR artifacts written for this run                                         | Clear SR lease (if needed) + rerun P5 (lease rules apply)                                                                              |
| P6    | STREAMING_ACTIVE         | **WSP one-shot ECS task** reads `stream_view`, POSTs to IG                                         | S3 stream_view → IG ingest                                                                | WSP                      | WSP logs show stream start/stop; IG receives requests                                       | Stop WSP task; rerun P6 (idempotent event_id; IG dedupe absorbs replays)                                                               |
| P7    | INGEST_COMMITTED         | **IG ECS service** admits/dedupes/quarantines and publishes to Kafka                               | Kafka traffic + context topics; S3 receipts/quarantine                                    | IG                       | Receipt summary exists + Kafka offsets advanced (admitted messages visible)                 | Do **not** delete admitted Kafka data mid-run; rerun relies on dedupe + evidence. Quarantine/receipts may be rerun-scoped cleanup only |
| P8    | RTDL_CAUGHT_UP           | **RTDL core ECS workers** consume Kafka and commit state                                           | Kafka topics → runtime DB + S3 (archive/evidence slices)                                  | RTDL core                | Offsets advanced only after commits; reconciliation artifact(s) exist                       | Stop workers; clear rebuildable RTDL state only (per rerun rules); rerun P8                                                            |
| P9    | DECISION_CHAIN_COMMITTED | **Decision lane ECS workers** (DL/DF/AL/DLA)                                                       | Kafka → runtime DB + S3 audit evidence                                                    | Decision lane            | Append-only DLA evidence exists; action outcomes recorded; parity proofs (where applicable) | Stop lane; rerun with idempotency keys; never mutate audit history                                                                     |
| P10   | CASE_LABELS_COMMITTED    | **CM/LS ECS services** + managed DB                                                                | Kafka triggers/audit refs → DB timelines + S3 evidence summaries                          | Case/Labels              | Case timelines appended; label assertions appended; dedupe/ack semantics hold               | Stop services; rerun uses idempotency keys; never rewrite timelines                                                                    |
| P11   | OBS_GOV_CLOSED           | **Single-writer reporter one-shot job**                                                            | runtime evidence → S3 evidence bundle                                                     | Reporter                 | Run report + governance events + env conformance written under run evidence prefix          | Re-run reporter (idempotent single-writer); if partial, overwrite only derived summaries (never mutate base truth)                     |
| P12   | TEARDOWN                 | **Operator**: `terraform destroy demo` + teardown verification                                     | Demo infra removed; core/evidence remains                                                 | Operator                 | No demo resources remain (Kafka cluster gone, ECS stopped, DB gone); evidence still present | If anything remains, destroy by tag; stop-the-line until billing-safe                                                                  |

### Notes (pinned interpretation)

* **“No laptop runtime dependency”** means: the operator can still run Terraform and trigger CLI commands, but **no platform services/jobs** depend on local machine execution.
* **Proof anchors must be durable**: anything that was “local filesystem proof” in local_parity must become **S3 evidence proof** in dev_min (run-scoped).
* **Rollback must respect append-only truth**: derived artifacts can be regenerated, but base truth stores (receipts/audit/label timelines) must never be rewritten in-place.

---

## 5. Phase-by-Phase Runbook (Authoritative)

### P(-1) PACKAGING_READY

**Intent:** Ensure the platform code is packaged into runnable container image(s) so that **no laptop runtime dependency** is possible in dev_min. This phase exists because ECS/Batch can only run what has been containerized and pushed to a registry.

**Local parity source:** This is the “implicit packaging” that existed on your laptop. In dev_min it becomes explicit and gated.

---

#### P(-1).1 Semantics (what this phase means)

* The platform’s Spine Green v0 phases `P0..P11` MUST be executable on managed compute using container images.
* The images MUST contain:

  * the platform runtime code (`src/fraud_detection/...`)
  * all Python dependencies required for spine phases
  * the CLI/entrypoints required to execute one-shot jobs (oracle jobs, SR, WSP, reporter)
  * the service entrypoints required to run daemons (IG, RTDL workers, CM/LS services if in-scope)

---

#### P(-1).2 Pinned decisions (non-negotiable)

1. **Image registry**

* **MUST:** use **AWS ECR** in the pinned AWS region (eu-west-2).
* **MUST:** image references used by ECS task/service definitions must be ECR URLs.

2. **Image count strategy (v0)**

* **MUST:** v0 uses **a single “platform” image** capable of running all Spine Green v0 entrypoints.

  * Different phases select different commands/args, but they reference the same image digest/tag.
* **MAY (later):** split into multiple images only if required for size/security; doing so requires an explicit repin.

3. **Tagging strategy**

* **MUST:** every build produces an immutable tag containing the **git commit SHA** (e.g., `git-<sha>`).
* **MAY:** also publish a convenience mutable tag (e.g., `dev-min-latest`) for operator ergonomics, but ECS definitions MUST be able to pin to the immutable SHA tag for reproducibility.

4. **No secrets baked into images**

* **MUST NOT:** bake Confluent creds, DB creds, or any secrets into the image.
* **MUST:** secrets are injected at runtime via SSM (and/or task env) and referenced via handles registry.

5. **CLI-only orchestration remains**

* **MUST:** building/pushing images is driven by CLI/CI (no manual console workflow required).

---

#### P(-1).3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

This runbook phase references the following handle keys (names only; values pinned in registry):

* `AWS_REGION`
* `ECR_REPO_NAME`
* `IMAGE_TAG_GIT_SHA_PATTERN`
* `IMAGE_TAG_LATEST_OPTIONAL`
* `IMAGE_DIGEST_EVIDENCE_FIELD` (where the digest is recorded in run evidence)
* `CLOUDWATCH_LOG_GROUP_PREFIX` (for ECS logs later)

---

#### P(-1).4 Entrypoints that MUST exist in the image (Spine Green v0)

The single v0 image MUST be able to execute, at minimum, the following “job card” entrypoints (names here are logical; Codex binds them to real module entrypoints):

**Oracle lane**

* Oracle seed/sync job (if used in dev_min)
* Oracle stream-sort job
* Oracle checker job

**Control/Ingress**

* SR run (gate + READY emit)
* WSP run (stream_view → IG)
* IG service start

**RTDL**

* RTDL core workers start (consume topics, commit state)
* Decision lane workers start (DL/DF/AL/DLA)

**Case/Labels**

* CM service start
* LS service start

**Closure**

* Reporter single-writer run (obs/gov close + evidence bundle write)

> This is exactly why a “single image” is viable: it packages the whole platform runtime; phases select commands.

---

#### P(-1).5 Operator procedure (how to run P(-1) in practice)

**MUST** provide one of the following operator flows (implementer choice):

**Option A: GitHub Actions (recommended)**

* On push/merge to migration branch:

  * build Docker image
  * run minimal smoke import (optional)
  * push to ECR with `git-<sha>` tag
  * output image digest

**Option B: Local CLI build (allowed)**

* Operator runs:

  * `docker build ...`
  * `docker push ...` to ECR
  * records resulting digest/tag

In both options, the result MUST be the same: an ECR image reference usable by ECS tasks/services.

---

#### P(-1).6 Gates / PASS criteria

P(-1) is PASS only if all are true:

1. **Image exists in ECR**

* The immutable tag `git-<sha>` exists in ECR.
* The image digest is retrievable.

2. **Image is runnable**

* A minimal “container start” smoke test succeeds (example: `--help` output or `python -c "import fraud_detection"`).
* This test MUST NOT require runtime secrets.

3. **Image reference is ready for ECS**

* ECS task definition(s) can reference the image (even if services are not deployed yet).
* No image pull errors.

---

#### P(-1).7 Proof artifacts (what proves PASS)

* ECR image exists with immutable tag `git-<sha>`
* ECR image digest recorded (at minimum in operator logs; later also written into `run.json` evidence under `IMAGE_DIGEST_EVIDENCE_FIELD`)
* Smoke test output captured (CI logs acceptable)

---

#### P(-1).8 Rollback / rerun rules

* If the build is broken:

  * rollback by re-pointing ECS task definitions to the previous known-good immutable tag, or
  * rebuild and repush under a new git SHA (preferred).
* **MUST NOT:** reuse an immutable tag for a different image.
* Mutable tag (if used) may be overwritten, but must never be used as the only reproducibility reference.

---

#### P(-1).9 Cost notes

* ECR storage is low cost at this scale; keep images bounded by:

  * avoiding embedding large datasets in images
  * pruning old tags if needed later (not required in v0)

---

### P0 SUBSTRATE_READY

**Intent:** Provision and validate the **dev_min substrate** required to run Spine Green v0 with **no laptop runtime dependency**. This phase brings up core + demo infrastructure, pins the handles, and ensures everything required for P(-1)/P2..P12 can run and be torn down safely.

---

#### P0.1 Semantics (what this phase means)

P0 means:

* **Core stack** exists (persistent, low-cost):

  * S3 buckets for oracle/archive/quarantine/evidence
  * Terraform state bucket + lock table
  * Budgets/alerts
  * Minimal IAM scaffolding
* **Demo stack** exists (ephemeral, destroy-by-default):

  * Confluent Cloud Kafka cluster + topics
  * SSM secrets for Confluent bootstrap/key/secret
  * ECS cluster + networking (no NAT) and service scaffolding
  * Managed runtime DB (demo-scoped)
  * Any demo-scoped SSM parameters (DB creds, IG API key if you store it there)
* All **handles** referenced in the dev_min runbook can be resolved and are consistent.
* Substrate readiness is confirmed **before** any runtime tasks are executed.

---

#### P0.2 Pinned decisions (non-negotiable)

1. **Core vs demo split**

* **MUST:** core and demo stacks are separate and have separate Terraform state keys.
* **MUST:** demo can be destroyed without affecting core evidence. 

2. **No laptop dependency posture**

* **MUST:** substrate includes everything required to run P2..P11 without laptop runtime:

  * ECS cluster/scaffolding
  * runtime DB
  * Confluent cluster/topics/creds
  * S3 buckets/prefixes 

3. **Budget posture**

* **MUST:** demo infra is destroy-by-default.
* **MUST NOT:** NAT gateway.
* **MUST NOT:** always-on load balancer required for normal operation.

4. **CLI-only orchestration**

* **MUST:** operator uses CLI targets to apply/destroy infra (no Step Functions required).

---

#### P0.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**Terraform**

* `TF_STATE_BUCKET`, `TF_STATE_KEY_CORE`, `TF_STATE_KEY_DEMO`, `TF_LOCK_TABLE`
* `TF_STACK_CORE_DIR`, `TF_STACK_DEMO_DIR`
* `ROLE_TERRAFORM_APPLY`

**S3 buckets/prefixes**

* `S3_ORACLE_BUCKET`, `S3_ARCHIVE_BUCKET`, `S3_QUARANTINE_BUCKET`, `S3_EVIDENCE_BUCKET`
* prefix patterns in Section 3 of handles registry

**Confluent**

* `CONFLUENT_ENV_NAME`, `CONFLUENT_CLUSTER_NAME`, `CONFLUENT_CLUSTER_TYPE`
* `SSM_CONFLUENT_*` paths
* topic map keys (`FP_BUS_*`)

**ECR/images**

* `ECR_REPO_NAME`, `ECR_REPO_URI` (even if P(-1) not executed yet, substrate must allow it)

**ECS/network**

* `ECS_CLUSTER_NAME`, `VPC_ID`, `SUBNET_IDS_PUBLIC`, `SECURITY_GROUP_ID_APP`, `SECURITY_GROUP_ID_DB`
* `CLOUDWATCH_LOG_GROUP_PREFIX`

**Runtime DB**

* `DB_ENGINE`, `DB_SCOPE`, `RDS_*`, `SSM_DB_*`

**Budgets**

* `AWS_BUDGET_*` handles

---

#### P0.4 Operator procedure (how to execute P0)

P0 is executed as infrastructure bring-up + handle validation.

1. **Apply core**

* `terraform apply` in `TF_STACK_CORE_DIR`
* Confirm outputs/created resources include:

  * S3 buckets (oracle/archive/quarantine/evidence)
  * tfstate bucket (if separate) + lock table
  * budgets/alerts
  * IAM scaffolding

2. **Apply demo**

* `terraform apply` in `TF_STACK_DEMO_DIR`
* Confirm outputs/created resources include:

  * Confluent cluster + topics
  * Confluent creds written to SSM paths
  * ECS cluster/scaffolding (and any required service discovery)
  * runtime DB created
  * DB creds written to SSM paths

3. **Preflight validation (operator checks)**

* Read SSM:

  * Confluent bootstrap/key/secret exist
  * DB user/password exist
* Validate S3:

  * evidence bucket writable (write a small marker object)
  * oracle bucket exists
* Validate Kafka:

  * topics exist (list topics)
* Validate “no NAT”:

  * NAT gateways list is empty
* Validate teardown viability:

  * `terraform destroy demo` would only delete demo-scoped resources (dry-run plan acceptable)

---

#### P0.5 Gates / PASS criteria

P0 is PASS only if all are true:

1. **Core applied**

* core Terraform apply succeeded and core resources exist.

2. **Demo applied**

* demo Terraform apply succeeded and demo resources exist.

3. **Handles resolvable**

* All required handle values are known and reachable:

  * S3 buckets exist and are accessible
  * SSM secrets exist (Confluent + DB)
  * Kafka topics exist and are accessible

4. **No forbidden infra**

* No NAT gateway exists.
* No always-on LB required for normal operation.

5. **Teardown path is viable**

* Demo infra can be destroyed cleanly without deleting evidence (core remains).

---

#### P0.6 Commit evidence (dev_min durable proof)

P0 MUST write a run-independent substrate snapshot (core-level or operator-level) OR (preferred) a run-scoped snapshot when a run is initiated.

For simplicity in v0:

* **MUST:** write a **demo apply snapshot** to S3 evidence bucket under a stable prefix, e.g.:

  * `evidence/dev_min/substrate/demo_apply_snapshot.json`
    Containing:
* timestamps
* terraform outputs summary (non-secret)
* resource identifiers (cluster names, bucket names)
* “no NAT” check result
* budgets enabled confirmation

(Exact filename may be adjusted, but a durable substrate readiness record is mandatory.)

---

#### P0.7 Rollback / rerun rules (safe)

* If core apply fails: fix Terraform core and reapply.
* If demo apply fails: fix Terraform demo and reapply.
* If Confluent resources are misconfigured: destroy demo stack and reapply.
* If runtime DB is misconfigured: destroy demo DB (as part of demo destroy) and reapply.

Never “patch” by manually creating resources in console unless you also encode them back into Terraform.

---

#### P0.8 Cost notes

* Core resources are designed to be low cost and persistent.
* Demo resources begin accruing cost immediately; keep demo window short and proceed to P(-1)/P1 quickly, then run and teardown.

---

If you want, next we’ll draft **P1 RUN_PINNED** (platform_run_id creation, config digest, and run.json in S3 evidence).


---

### P1 RUN_PINNED

**Intent:** Create the run’s identity and provenance **once**, up front, and persist it durably so every subsequent phase can enforce **run-scope**. P1 is the “start of run” anchor: it creates `platform_run_id`, derives/records `scenario_run_id` inputs (equivalence key), writes the run config payload + digest, and creates the S3 evidence root for the run.

---

#### P1.1 Semantics (what this phase means)

P1 means:

* A new `platform_run_id` is created for the run session.
* The run’s effective configuration is **pinned**:

  * environment = `dev_min`
  * topic map identity (handle keys)
  * S3 bucket/prefix map (handle keys)
  * runtime DB identity (handle keys)
  * image identity (tag/digest from P(-1))
  * any important runtime knobs (concurrency/backpressure)
* A deterministic digest is computed over that config (so drift is detectable).
* The run evidence root exists in S3 at:

  * `evidence/runs/<platform_run_id>/`
* This pinned run identity is then injected into all daemon/services (P2) as `REQUIRED_PLATFORM_RUN_ID`.

> Note: `scenario_run_id` itself is authoritatively derived/confirmed in P5 (SR). In P1 we pin the *equivalence key input* and record it as provenance.

---

#### P1.2 Pinned decisions (non-negotiable)

1. **Run-scope enforcement depends on P1**

* **MUST:** every later phase references the `platform_run_id` produced here.
* **MUST:** P2 daemons MUST use this value as required scope (fail closed if missing/mismatch).

2. **Durable evidence-first**

* **MUST:** P1 writes `run.json` to S3 evidence before starting heavy work.

3. **No laptop runtime dependency**

* **MUST:** P1 may be executed as an operator CLI action (operator-only is allowed), but it MUST NOT require any platform runtime services on the laptop.
* **MAY:** implement P1 as a one-shot ECS task if you prefer strict “everything is a task.” Either is acceptable as long as results are identical.

4. **Config digest is required**

* **MUST:** compute a deterministic config digest and store it in `run.json`.
* **MUST:** any config change requires a new run (no silent mid-run drift).

---

#### P1.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**Evidence root**

* `S3_EVIDENCE_BUCKET`
* `S3_EVIDENCE_RUN_ROOT_PATTERN`
* `EVIDENCE_RUN_JSON_KEY`

**Field names**

* `FIELD_PLATFORM_RUN_ID`
* `FIELD_SCENARIO_RUN_ID`
* `FIELD_WRITTEN_AT_UTC`

**Config digest**

* `CONFIG_DIGEST_ALGO` *(pin later; e.g., sha256)*
* `CONFIG_DIGEST_FIELD = "config_digest"`

**Image provenance**

* `ECR_REPO_URI`
* `IMAGE_TAG_GIT_SHA_PATTERN`
* `IMAGE_DIGEST_EVIDENCE_FIELD`
* `IMAGE_TAG_EVIDENCE_FIELD`
* `IMAGE_GIT_SHA_EVIDENCE_FIELD`

**Substrate handles (referenced by key)**

* All bucket handles: `S3_*_BUCKET`
* All topic handles: `FP_BUS_*`
* DB handles: `RDS_*`, `DB_NAME`

---

#### P1.4 Operator procedure (how to execute P1)

1. **Generate `platform_run_id`**

* Use UTC timestamped format consistent with your run naming (or your existing generator).
* Record it as the authoritative run ID.

2. **Assemble run config payload**
   Include at minimum:

* env = `dev_min`
* `platform_run_id`
* scenario equivalence key input (raw value or hashed pointer)
* handle references:

  * S3 buckets + prefix patterns
  * topic map keys
  * DB identifiers
* runtime knobs:

  * concurrency/backpressure knobs if used
* image identity:

  * immutable tag `git-<sha>`
  * digest (if available)

3. **Compute `config_digest`**

* deterministic canonical JSON serialization + hash
* store digest in payload

4. **Write `run.json` to S3 evidence**

* write to:

  * `evidence/runs/<platform_run_id>/run.json`

5. **(Optional) Write run-start marker**

* `run_started.json` if you want explicit start marker separate from run.json.

---

#### P1.5 Gates / PASS criteria

P1 is PASS only if all are true:

1. **Evidence root created**

* `evidence/runs/<platform_run_id>/` exists (at least one object written).

2. **run.json exists and is complete**

* Contains:

  * `platform_run_id`
  * env
  * config payload
  * config digest
  * image provenance fields (tag at minimum)

3. **Config digest stable**

* Recomputing the digest over the same payload yields the same value.

---

#### P1.6 Commit evidence (dev_min durable proof)

P1 MUST write:

* `evidence/runs/<platform_run_id>/run.json`

Optional:

* `evidence/runs/<platform_run_id>/run_started.json`

---

#### P1.7 Rollback / rerun rules (safe)

* If P1 was created incorrectly (wrong config/handles):

  * delete the run evidence root:

    * `evidence/runs/<platform_run_id>/`
  * generate a new `platform_run_id` and rerun P1.
* Do not reuse a `platform_run_id` for a different config digest.

---

#### P1.8 Cost notes

* P1 is near-zero cost (S3 writes only).
* It prevents expensive mistakes later by making run-scope and config drift explicit.


---

### P2 DAEMONS_READY

**Intent:** Start (and verify) the **always-on Spine Green v0 packs** as managed runtime daemons on `dev_min`, with **run-scope enforced** for the active `platform_run_id`. This phase is the dev_min translation of “start local run_operate packs and confirm they’re RUNNING,” but implemented as **ECS services/workers** (no laptop compute).

---

#### P2.1 Semantics (what this phase means)

* All **in-scope** long-running packs are started and remain running for the duration of the run:

  * `control_ingress`
  * `rtdl_core`
  * `rtdl_decision_lane`
  * `case_labels`
  * `obs_gov`
* Learning jobs are **explicitly not started** in this baseline.
* Each pack enforces **run-scope**: daemons MUST be configured to require the `platform_run_id` pinned in `P1`, and MUST fail closed if the run scope does not match.
* Operator must be able to query “packs RUNNING” status, and there must be durable “commit evidence” that the daemons were healthy enough to proceed.

---

#### P2.2 Pinned decisions (non-negotiable)

1. **No laptop compute**

* **MUST:** all daemons run on managed compute (ECS services/workers). 

2. **Spine-only packs**

* **MUST:** start only the 5 Spine Green v0 packs listed in P2.1.
* **MUST NOT:** start the learning-jobs pack for this baseline.

3. **Run-scope enforcement**

* **MUST:** each daemon is started with `REQUIRED_PLATFORM_RUN_ID = <platform_run_id>` (from P1) (or an equivalent pinned run-scope mechanism).
* **MUST:** daemons fail closed if run scope mismatch.
* **MUST:** do not run duplicate “manual once” consumers in parallel for the same lane/consumer group.

4. **Replica policy (v0)**

* **MUST:** v0 runs **1 replica per daemon/service** (no horizontal scaling) to keep consumer group behavior deterministic and avoid accidental duplicate consumption during migration.

5. **Destroy-by-default**

* **MUST:** these daemons are demo-scoped: they are started for the run and removed during `P12 TEARDOWN`.

---

#### P2.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**ECS / runtime**

* `ECS_CLUSTER_NAME`
* `VPC_ID`, `SUBNET_IDS`, `SECURITY_GROUP_IDS` (no NAT posture)
* `CLOUDWATCH_LOG_GROUP_PREFIX`

**Run scope**

* `REQUIRED_PLATFORM_RUN_ID_ENV_KEY` (name of the env var)
* `ACTIVE_RUN_ID_SOURCE` (how the value is provided: env override / SSM param / etc.)
  *(mechanism is allowed to vary, but must be pinned in the registry and used consistently)*

**Service identifiers (by pack)**

* `SVC_IG` (control_ingress)
* `SVC_RTDL_CORE_*` (archivewriter, IEG, OFP, CSFB intake, etc.)
* `SVC_DECISION_LANE_*` (DL/DF/AL/DLA workers)
* `SVC_CASE_LABELS_*` (CaseTrigger/CM/LS)
* `SVC_OBS_GOV_*` (environment conformance + reporter if daemonized)

**Substrate**

* `S3_*_BUCKET` handles
* `SSM_CONFLUENT_*` handles
* `KAFKA_TOPIC_MAP_*` handles
* `RDS_*` handles (dev_min runtime DB; no laptop DB)

---

#### P2.4 What “packs” mean in dev_min (mapping)

In local parity, P2 “packs” are run_operate supervision groups. In dev_min, each pack maps to a set of ECS services/workers (still grouped logically as a pack).

**Dev_min pack contents (Spine Green v0)**

* `control_ingress` pack runs:

  * **IG service daemon**
  * (No requirement for an always-on READY consumer in v0; orchestration remains CLI-driven)
* `rtdl_core` pack runs:

  * ArchiveWriter + IEG projector + OFP projector + CSFB intake (daemon workers)
* `rtdl_decision_lane` pack runs:

  * DL + DF + AL + DLA (daemon workers)
* `case_labels` pack runs:

  * CaseTrigger worker + CM worker/service + LS worker/service (writer-boundary semantics preserved)
* `obs_gov` pack runs:

  * environment_conformance worker
  * platform_run_reporter *may exist as a daemon*, but **P11 remains the single-writer closeout**; do not allow concurrent writers.

---

#### P2.5 Operator procedure (how to execute P2)

P2 is executed as “start the Spine Green v0 packs and confirm RUNNING,” using dev_min equivalents of the local status checks.

**Start (dev_min equivalents of `platform-operate-*-up`)**

* Start/ensure **ECS services** are deployed with:

  * correct image tag/digest (from P(-1))
  * Confluent creds injected (SSM)
  * run-scope env set to `platform_run_id` (from P1)
  * DB connectivity injected (SSM)
* Wait until each service reaches **RUNNING/healthy** state.

**Status (dev_min equivalents of `platform-operate-*-status`)**

* Query ECS service health for each pack group.
* Confirm no unexpected extra tasks are running for any consumer group.

> Implementation detail (Codex freedom): you may wrap these as `make dev-min-operate-*-up/status` commands, but the semantics above must hold.

---

#### P2.6 Gates / PASS criteria

P2 is PASS only if all are true:

1. **All in-scope packs RUNNING**

* `control_ingress`, `rtdl_core`, `rtdl_decision_lane`, `case_labels`, `obs_gov` are RUNNING (1 replica each).

2. **Run-scope enforced**

* Each daemon confirms (log + status) that `REQUIRED_PLATFORM_RUN_ID == <platform_run_id>`.
* Any mismatch must fail closed (no “partial run”).

3. **No duplicate consumers**

* No manual once-off consumers or duplicate ECS tasks consuming the same lane in parallel.

4. **Dependency readiness**

* Daemons can reach their substrate dependencies (Kafka bootstrap, S3 prefixes, runtime DB) and do not crashloop due to missing handles.

---

#### P2.7 Commit evidence (dev_min durable proof)

Local parity writes pack state/status files; dev_min must produce a durable equivalent:

* **MUST:** write a run-scoped “daemon readiness snapshot” into the evidence prefix, e.g.:

  * `evidence/runs/<platform_run_id>/operate/daemons_ready.json`
    containing:
  * pack IDs
  * ECS service names + task ARNs
  * desired_count/running_count
  * run-scope value used
  * timestamp

(Exact filename/schema is finalized later; the existence of a durable readiness snapshot is mandatory.)

---

#### P2.8 Reset / retry rules (safe)

* **Preferred retry:** restart the affected pack’s ECS services (not ad-hoc manual consumers).
* **Never run** “once” commands concurrently with daemon consumers for the same lane.
* If services were started under the wrong run scope:

  * stop them,
  * correct the run-scope value,
  * start again (do not proceed to P3/P4/P5 with mismatched scope).

---

#### P2.9 Cost notes

* P2 is the first phase that can meaningfully burn money (ECS services + runtime DB).
* **MUST:** keep replicas at 1 and keep demo windows bounded; teardown (P12) is mandatory.

---

### P3 ORACLE_READY (Oracle seed + stream-sort + checker)

**Intent:** Ensure the run’s Oracle inputs are present in **S3**, and materialize a deterministic **`stream_view`** for the in-scope datasets (traffic + required context) using managed compute (no laptop), then validate it. This phase exists because **WSP MUST consume `stream_view`, not raw oracle outputs**, and because local sort is memory/time prohibitive.

> **Operator reality:** P3 is the first “heavy compute” phase. In dev_min, it must run as managed one-shot jobs that read/write S3 and emit receipts/manifest artifacts.

---

#### P3.1 Semantics (what this phase means)

P3 consists of three sub-steps that must succeed in order:

1. **Oracle seed/sync (if needed)**

* Ensure the oracle inputs required for this run exist in S3 under the pinned oracle prefix layout.
* Dev_min allows seeding by copying from local (MinIO/local FS) until the engine writes directly to S3, but the *result* must match the canonical oracle layout.

2. **Stream-sort**

* For each required oracle dataset/output_id:

  * read oracle dataset objects
  * sort into a deterministic stream_view ordering keyed by `ts_utc` and/or `flow_id` (per dataset rule)
  * write stream_view shards + manifests/receipts to S3 under `oracle/<platform_run_id>/stream_view/...` (exact pattern pinned in handles registry later)
* Sorting must be deterministic and restartable.

3. **Oracle checker**

* Validate:

  * required datasets exist
  * stream_view exists for each required dataset/output_id
  * manifests/receipts exist
  * (optionally) basic invariants such as monotone ordering, expected row counts, and required columns
* Fail closed on any missing receipt/manifest.

---

#### P3.2 Pinned decisions (non-negotiable)

1. **No laptop compute**

* **MUST:** stream-sort and checker run on managed compute (one-shot ECS tasks or AWS Batch jobs). 

2. **S3 is the oracle store for dev_min**

* **MUST:** oracle inputs and stream_view outputs live in AWS S3.

3. **Stream-view-first**

* **MUST:** WSP reads only from `stream_view` artifacts produced by P3.
* **MUST NOT:** WSP read “raw oracle outputs” as a shortcut.

4. **Per-output rerun is allowed**

* **MUST:** P3 supports per-output rerun (re-sort only the output_id that failed) as in local parity.

5. **Determinism + receipts**

* **MUST:** stream_sort emits receipts/manifests that the checker validates.
* **MUST:** checker is fail-closed (no partial pass).

6. **Budget posture**

* **MUST:** compute is ephemeral and destroyed at teardown; no always-on big workers.
* **MUST:** no NAT gateway.

---

#### P3.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**Oracle S3**

* `S3_ORACLE_BUCKET`
* `S3_ORACLE_PREFIX_PATTERN` (includes `<platform_run_id>`)
* `S3_STREAM_VIEW_PREFIX_PATTERN`
* `S3_STREAM_VIEW_MANIFEST_PATTERN`
* `S3_STREAM_SORT_RECEIPT_PATTERN`

**Datasets / output IDs**

* `ORACLE_REQUIRED_OUTPUT_IDS` (Spine Green v0 set)
* `ORACLE_SORT_KEY_BY_OUTPUT_ID` (ts_utc vs flow_id)

**Compute**

* `TD_ORACLE_SEED` (if seed runs as task)
* `TD_ORACLE_STREAM_SORT`
* `TD_ORACLE_CHECKER`
* (If Batch is used) `BATCH_JOB_QUEUE`, `BATCH_JOB_DEFINITION`

**IAM**

* `ROLE_ORACLE_JOB` (S3 read oracle inputs; S3 write stream_view + receipts; CloudWatch logs write)

---

#### P3.4 Packaging target (how P3 runs in dev_min)

P3 is executed as **one-shot jobs**.

**Pinned v0 recommendation: ECS run-task**

* One ECS task per sub-step:

  * `oracle_seed` (optional)
  * `oracle_stream_sort` (repeatable per output_id)
  * `oracle_checker`
* Rationale: aligns with “no laptop dependency” without introducing Batch complexity.

**Allowed alternative: AWS Batch**

* If you already have Batch handles wired, you may implement stream_sort as Batch jobs.
* If Batch is used, the job queue/definition MUST be pinned as handles and must be destroyable (demo stack).
  (Choice is implementer freedom, but the interface + proof are pinned.)

---

#### P3.5 Oracle seed/sync sub-step (P3.A)

**Purpose:** ensure oracle inputs exist in S3.

* **MAY:** seed by copying from local store until engine writes directly to S3.
* **MUST:** preserve the canonical oracle layout (do not invent new structure).
* **MUST:** seeding must be resumable and incremental (copy deltas), because oracle size is large.

**PASS proof for seed:**

* required oracle input prefixes exist for `platform_run_id`
* object count/size checks recorded into evidence snapshot

---

#### P3.6 Stream-sort sub-step (P3.B)

**Purpose:** materialize `stream_view` per required output_id.

**Sorting rules (pinned):**

* Each `output_id` must be sorted using the pinned key:

  * `ts_utc` for time-ordered datasets
  * `flow_id` for flow-anchored datasets (where applicable)

**Output contract (pinned at conceptual level):**
For each `output_id`, stream-sort MUST write:

* stream_view shards (e.g., `part-*.parquet` or equivalent)
* a manifest describing shard set + ordering metadata
* a receipt describing:

  * input fingerprint (what was read)
  * output fingerprint (what was written)
  * sort key used
  * counts (rows/files)
  * started_at/ended_at

(Exact filenames/patterns are pinned in handles registry.)

**Per-output invocation (pinned interface):**

* The stream-sort job MUST accept:

  * `platform_run_id`
  * `output_id`
  * input prefix (oracle dataset)
  * output prefix (stream_view)
  * sort_key (`ts_utc` or `flow_id`)

---

#### P3.7 Checker sub-step (P3.C)

**Purpose:** fail-closed validation that `stream_view` is ready for WSP.

Checker MUST validate, for each required output_id:

* input exists (oracle dataset present)
* stream_view exists
* manifest exists
* receipt exists
* (optional) basic ordering invariant checks

Checker MUST produce:

* `oracle_checker_pass.json` (or equivalent) under the evidence prefix
* summary of per-output PASS/FAIL

---

#### P3.8 Gates / PASS criteria (phase-level)

P3 is PASS only if all are true:

1. **Oracle inputs present in S3** for this run (seeded or already written)
2. **For every required output_id**:

   * stream_view shards exist
   * manifest exists
   * receipt exists
3. **Checker PASS** exists and reports all required output_ids PASS
4. **Per-output rerun works** (a failed output_id can be re-sorted without rerunning everything)

---

#### P3.9 Commit evidence (dev_min durable proof)

P3 must write **both** oracle-lane artifacts and run evidence artifacts:

**Oracle lane (in S3 oracle prefix)**

* stream_view shards
* stream_view manifest(s)
* stream_sort receipt(s)

**Run evidence (in S3 evidence prefix)**

* `oracle/seed_snapshot.json` (if seed performed)
* `oracle/stream_sort_summary.json` (per-output summary)
* `oracle/checker_pass.json` (checker result)

(Exact filenames are pinned later; existence + content is mandatory.)

---

#### P3.10 Rollback / rerun rules (safe)

* **Per-output rerun:** delete only the failed output_id’s stream_view prefix + receipt/manifest, then rerun stream-sort for that output_id.
* **Never delete raw oracle inputs** as part of rerun (unless you are re-seeding intentionally).
* If checker fails due to missing artifacts:

  * rerun only the missing producer step(s)
  * do not proceed to P5/P6 until checker PASS exists.

---

#### P3.11 Cost and performance notes (pinned expectations)

* P3 is heavy compute; optimize by:

  * per-output parallelization (multiple tasks, one per output_id) is allowed **only if** it does not create conflicting writes (each output_id writes to a disjoint prefix).
  * keep tasks ephemeral.
* Since we avoid NAT, tasks must be placed in networking that can reach S3 and CloudWatch without NAT (public subnets with locked SG is allowed in v0 dev_min; exact networking pinned in handles registry).

---

### P4 INGEST_READY

**Intent:** Ensure the **Ingestion Gate (IG)** is ready to accept WSP traffic in dev_min: service is running on managed compute, writer-boundary auth is enforced, required Kafka topics exist and are writable, and IG can persist its required state to **managed runtime storage** (no laptop DB). This phase is the “nothing downstream starts until ingress is truly ready” safety gate.

---

#### P4.1 Semantics (what this phase means)

P4 means:

* IG is deployed as a long-running daemon (ECS service) and is healthy.
* IG has all required configuration/handles resolved:

  * Kafka bootstrap + credentials
  * topic map (traffic + context + control/audit as applicable)
  * quarantine + receipts S3 prefixes
  * managed DB connection (if IG uses DB state)
* IG enforces the writer boundary:

  * requests without auth fail closed
  * requests with auth are accepted and processed
* “Downstream readiness” is true:

  * Kafka topics exist and are writable
  * IG can publish admitted events
  * IG can emit quarantine + receipts evidence

---

#### P4.2 Pinned decisions (non-negotiable)

1. **No laptop runtime**

* **MUST:** IG runs in dev_min as an ECS **service** (daemon), not on the laptop. 

2. **Writer-boundary auth must exist**

* **MUST:** preserve the local parity writer-boundary discipline (API-key style is acceptable v0).
* **MUST:** unauthenticated requests MUST fail closed (no “dev bypass”).

3. **Managed Kafka publish target**

* **MUST:** IG publishes admitted events to Confluent Kafka topics (traffic + context) defined in the handles registry topic map.
* **MUST:** IG publish ambiguity must remain modeled and fail closed where required (no “assume publish succeeded”).

4. **Quarantine + receipts are durable**

* **MUST:** quarantine payloads and receipts summaries must be written to S3 (dev_min durable substrate).

5. **No local sqlite checkpoints**

* **MUST:** IG may not rely on laptop-local files/SQLite for any required runtime persistence.
* **MUST:** any required IG state is persisted to managed storage (exact backend pinned in handles registry).

6. **No NAT / no always-on LB**

* **MUST NOT:** NAT gateway.
* **MAY:** an internal load-balancer is permitted only if strictly required for service reachability; prefer private networking within ECS when possible. (If any LB is used, it must be demo-scoped.)

---

#### P4.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**IG service**

* `SVC_IG`
* `IG_LISTEN_ADDR` (container bind)
* `IG_PORT`
* `IG_HEALTHCHECK_PATH`

**Auth boundary**

* `IG_AUTH_HEADER_NAME` (e.g., `X-IG-Api-Key`)
* `SSM_IG_API_KEY_PATH` (or equivalent secure source)

**Kafka**

* `SSM_CONFLUENT_BOOTSTRAP_PATH`
* `SSM_CONFLUENT_API_KEY_PATH`
* `SSM_CONFLUENT_API_SECRET_PATH`
* Topic map keys (at minimum):

  * `FP_BUS_TRAFFIC_FRAUD_V1`
  * `FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1`
  * `FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1`
  * `FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1`
  * `FP_BUS_CONTROL_V1` (if IG emits control/anomaly events)
* Producer client config knobs (timeouts/retries) (names only)

**S3 (receipts/quarantine)**

* `S3_QUARANTINE_BUCKET`, `S3_QUARANTINE_PREFIX_PATTERN`
* `S3_EVIDENCE_BUCKET`, `S3_EVIDENCE_PREFIX_PATTERN`
* (If receipts are materialized under oracle/quarantine buckets, those prefixes too)

**Managed DB (if IG needs it)**

* `RDS_ENDPOINT`
* `DB_NAME`
* `SSM_DB_USER_PATH`
* `SSM_DB_PASSWORD_PATH`

**ECS runtime**

* `ECS_CLUSTER_NAME`, `SUBNET_IDS`, `SECURITY_GROUP_IDS`
* `ROLE_IG_SERVICE` (least privilege: Kafka publish + S3 write + DB connect + logs)

---

#### P4.4 Operator procedure (how to execute P4)

P4 is executed as “deploy IG and prove it is ready before we stream.”

1. **Deploy IG service**

* Ensure ECS service `SVC_IG` is deployed with:

  * correct image tag/digest (P(-1))
  * Kafka creds injected from SSM
  * IG API key injected from SSM
  * S3 bucket/prefix config injected via handles
  * DB creds injected if required
* Desired count = 1, running count must reach 1.

2. **Health check**

* Confirm IG health endpoint returns OK (from within the VPC or via permitted reachability path).

3. **Auth check**

* Send one unauthenticated request → MUST fail (401/403).
* Send one authenticated “dry-run” or minimal request → MUST be accepted.

  * If you don’t have a “dry-run” endpoint, use a minimal synthetic event payload that conforms to existing contracts (do not invent a new schema).

4. **Kafka publish smoke**

* Trigger a minimal admission that causes IG to publish to a Kafka topic.
* Confirm the topic offset advances and a consumer can read the published message.

5. **S3 write smoke**

* Confirm IG can write a small receipt/quarantine marker to the configured S3 prefix.

> Operator note: these smoke checks can be wrapped in a `dev-min-ig-preflight` command, but the semantics are pinned.

---

#### P4.5 Gates / PASS criteria

P4 is PASS only if all are true:

1. **IG service RUNNING and healthy**

* ECS service is stable (no crashloop), health endpoint returns OK.

2. **Writer boundary enforced**

* Requests without `IG_AUTH_HEADER_NAME` fail closed.
* Requests with valid key are accepted.

3. **Kafka writable**

* IG can publish at least one admitted message to the correct topic(s) using Confluent creds.
* Topic offsets advance and are readable by a consumer.

4. **Durable outputs writable**

* IG can write to S3 receipts/quarantine prefixes (permissions correct).

5. **No laptop persistence dependency**

* IG does not require local file paths/SQLite to start or run.

---

#### P4.6 Commit evidence (dev_min durable proof)

P4 MUST write a run-scoped readiness artifact to S3 evidence, e.g.:

* `evidence/runs/<platform_run_id>/ingest/ig_ready.json`

Containing at minimum:

* IG service name + task ARN(s)
* timestamp
* healthcheck result
* auth check result (pass/fail)
* Kafka publish smoke result (topic + partition + offset)
* S3 write smoke result (object key)

(Exact schema finalized later; this artifact is mandatory.)

---

#### P4.7 Rollback / rerun rules (safe)

* If IG fails to start or fails health checks:

  * stop/rollback the ECS service deployment
  * fix config/handles/permissions
  * redeploy and rerun P4
* If auth boundary is misconfigured:

  * rotate the key in SSM
  * redeploy IG (force new task)
* If Kafka publish fails:

  * do not proceed to P5/P6
  * verify Confluent creds + ACLs + topic existence
* Do not delete Kafka topics mid-run; resolve publish issues and retry.

---

#### P4.8 Cost notes

* IG is a daemon: it will accrue compute cost for the demo window.
* Keep desired count = 1 for v0.
* Teardown (P12) must stop IG service and destroy demo infra.

---

### P5 READY_PUBLISHED

**Intent:** Execute the **Scenario Runner (SR)** gate checks against the oracle store and publish the **READY** signal that authorizes streaming. SR is the “no PASS → no read” enforcer: downstream streaming MUST NOT begin until SR has validated the run facts and pinned the run’s gating artifacts.

---

#### P5.1 Semantics (what this phase means)

P5 means:

* SR loads the run’s oracle facts from S3 (dev_min oracle store).
* SR validates the run gates (PASS conditions) and writes **run facts artifacts**.
* SR publishes a **READY** control message that includes the pinned run identifiers and required provenance pointers.
* READY is the explicit authorization for WSP to begin streaming.

SR must preserve the local parity semantics:

* deterministic `scenario_run_id` derivation by equivalence key
* strict gate enforcement (fail closed)
* idempotent behavior (re-run policy governed by lease rules)

---

#### P5.2 Pinned decisions (non-negotiable)

1. **No laptop runtime**

* **MUST:** SR runs on managed compute as a **one-shot ECS task** (not on laptop). 

2. **Run-scope enforcement**

* **MUST:** SR is invoked for the `platform_run_id` pinned in P1.
* **MUST:** SR writes artifacts and READY message scoped to that run only.

3. **Fail-closed gating**

* **MUST:** if any SR gate fails, READY MUST NOT be published.

4. **READY is required**

* **MUST:** WSP streaming (P6) requires READY.
* **MUST NOT:** WSP start streaming without READY (no bypass).

5. **Managed Kafka control topic**

* **MUST:** READY is published to the dev_min control topic (`FP_BUS_CONTROL_V1`) on Confluent Kafka.

6. **Lease rules preserved**

* **MUST:** SR reruns obey the local parity lease rules (equivalence key governs deterministic `scenario_run_id` and prevents conflicting runs).

---

#### P5.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**ECS task**

* `TD_SR` (task definition name)
* `ROLE_SR_TASK` (IAM role: S3 read oracle + S3 write evidence + Kafka publish + logs)

**Oracle store**

* `S3_ORACLE_BUCKET`
* `S3_ORACLE_PREFIX_PATTERN` (includes `<platform_run_id>`)
* `S3_STREAM_VIEW_PREFIX_PATTERN` (SR may validate presence of stream_view outputs)

**Kafka control**

* `SSM_CONFLUENT_BOOTSTRAP_PATH`
* `SSM_CONFLUENT_API_KEY_PATH`
* `SSM_CONFLUENT_API_SECRET_PATH`
* `FP_BUS_CONTROL_V1`

**Run identity**

* `PLATFORM_RUN_ID`
* `SCENARIO_EQUIVALENCE_KEY_INPUT` (source for scenario determinism)
* `SCENARIO_RUN_ID_DERIVATION_MODE` (pinned behavior)

**Evidence**

* `S3_EVIDENCE_BUCKET`
* `S3_EVIDENCE_PREFIX_PATTERN`

---

#### P5.4 Operator procedure (how to execute P5)

P5 is executed as a one-shot SR task run:

1. **Invoke SR task**

* Run ECS task `TD_SR` with env/config:

  * `platform_run_id`
  * scenario equivalence key
  * oracle S3 prefixes
  * Kafka control topic + creds
  * evidence S3 prefix

2. **Observe SR completion**

* Task exits successfully (0).
* CloudWatch logs show gates evaluated and PASS recorded.

3. **Verify artifacts + READY**

* Verify SR artifacts exist in S3 evidence prefix.
* Verify a READY message exists on the control topic (consume from `FP_BUS_CONTROL_V1`).

---

#### P5.5 Gates / PASS criteria

P5 is PASS only if all are true:

1. **SR task succeeded**

* ECS task completed successfully and did not crash/fail.

2. **SR artifacts written**

* Run facts artifacts exist under:

  * `evidence/runs/<platform_run_id>/sr/...` (exact filenames pinned later)

3. **READY published**

* A READY message exists on `FP_BUS_CONTROL_V1` and includes at minimum:

  * `platform_run_id`
  * `scenario_run_id`
  * pointers/provenance required for downstream authorization

4. **Lease rules respected**

* No conflicting SR lease exists for the same equivalence key/run scope.

---

#### P5.6 Commit evidence (dev_min durable proof)

P5 MUST write:

* `evidence/runs/<platform_run_id>/sr/sr_pass.json` (or equivalent)
* `evidence/runs/<platform_run_id>/sr/ready_publish_receipt.json` containing:

  * topic, partition, offset of READY message
  * timestamp
  * `scenario_run_id`

(Exact schema pinned later; existence is mandatory.)

---

#### P5.7 Rollback / rerun rules (safe)

* If SR gate fails:

  * do not proceed to P6
  * fix oracle inputs/stream_view readiness
  * rerun SR under the same equivalence key only if lease rules allow
* If READY publish fails:

  * verify Kafka creds/topic ACLs
  * rerun SR publish step (do not “manually” craft READY messages)
* If SR artifacts are partial:

  * delete only derived SR artifacts under the run evidence prefix and rerun P5
  * never delete oracle truth inputs as part of SR rerun unless reseeding intentionally

---

#### P5.8 Cost notes

* SR is a short-lived task: cost is bounded to task runtime.
* Keep it one-shot; no need for a persistent SR daemon in v0.

---

### P6 STREAMING_ACTIVE

**Intent:** Run **World Streamer Producer (WSP)** as a one-shot streaming job that reads the run’s **S3 stream_view** outputs and sends traffic + context events to **IG**, using deterministic `event_id` and bounded retry rules. This phase is the bridge from sealed oracle truth → ingress boundary.

---

#### P6.1 Semantics (what this phase means)

P6 means:

* WSP starts only after **READY** exists (P5).
* WSP reads `stream_view` (not raw oracle outputs) for the required datasets/output_ids.
* WSP emits:

  * **traffic events** (fraud-mode)
  * required **context streams** (arrival_events, arrival_entities, flow_anchor)
* WSP sends events to IG using the writer-boundary interface (HTTP + auth header).
* WSP produces deterministic `event_id` and uses it unchanged across retries.
* WSP finishes when it has streamed the run’s intended slice.

---

#### P6.2 Pinned decisions (non-negotiable)

1. **No laptop runtime**

* **MUST:** WSP runs on managed compute as a **one-shot ECS task**. 

2. **READY required**

* **MUST:** WSP requires READY from P5.
* **MUST NOT:** stream without READY (no bypass).

3. **Stream-view-first**

* **MUST:** WSP reads only from `stream_view` artifacts produced in P3.

4. **Deterministic IDs + bounded retries**

* **MUST:** `event_id` is deterministic and stable across retries.
* **MUST:** transient failures may retry with the same `event_id`.
* **MUST:** non-retryable failures (schema/policy validation, 4xx class) must fail closed and stop/record.

5. **WSP does not publish to Kafka**

* **MUST:** WSP sends to IG; IG is the only boundary that publishes admitted events to Kafka.

---

#### P6.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**ECS task**

* `TD_WSP`
* `ROLE_WSP_TASK` (S3 read stream_view + S3 write evidence + logs; no Kafka perms required)

**READY consumption**

* `FP_BUS_CONTROL_V1`
* `SSM_CONFLUENT_BOOTSTRAP_PATH`
* `SSM_CONFLUENT_API_KEY_PATH`
* `SSM_CONFLUENT_API_SECRET_PATH`
* `READY_MESSAGE_FILTER` (how WSP finds READY for `platform_run_id`)

**S3 stream_view inputs**

* `S3_ORACLE_BUCKET`
* `S3_STREAM_VIEW_PREFIX_PATTERN` (includes `<platform_run_id>`)
* `ORACLE_REQUIRED_OUTPUT_IDS` (the set WSP must stream)

**IG target**

* `IG_BASE_URL` (reachable from WSP task networking)
* `IG_AUTH_HEADER_NAME`
* `SSM_IG_API_KEY_PATH`

**Evidence**

* `S3_EVIDENCE_BUCKET`
* `S3_EVIDENCE_PREFIX_PATTERN`

**WSP runtime knobs**

* `WSP_MAX_INFLIGHT`
* `WSP_RETRY_MAX_ATTEMPTS`
* `WSP_RETRY_BACKOFF_MS`
* `WSP_STOP_ON_NONRETRYABLE` (true)

---

#### P6.4 Operator procedure (how to execute P6)

1. **Invoke WSP task**

* Run ECS task `TD_WSP` with env/config:

  * `platform_run_id`
  * READY topic + creds
  * S3 stream_view prefix
  * IG endpoint + auth header/key
  * concurrency/retry knobs

2. **Monitor execution**

* Task remains RUNNING while streaming.
* CloudWatch logs show:

  * READY found
  * stream_view datasets enumerated
  * send loop progress
  * completion summary

3. **Verify downstream signals**

* IG should show receipt/admit activity (P7 will validate formally).
* Optional: Kafka topics show admitted events (again, P7 validates formally).

---

#### P6.5 Gates / PASS criteria

P6 is PASS only if all are true:

1. **READY consumed**

* WSP confirms it located READY for `platform_run_id` (by log + receipt).

2. **Stream_view enumerated**

* WSP confirms stream_view exists for each required output_id before streaming.

3. **Streaming completed**

* WSP exits successfully and records:

  * attempted sends
  * successful sends
  * retries
  * non-retryables (must be zero for PASS unless explicitly allowed by scenario)

4. **Non-retryables fail closed**

* If a non-retryable error occurred, WSP must stop and mark the run as failed at P6 (no silent skipping).

---

#### P6.6 Commit evidence (dev_min durable proof)

P6 MUST write run-scoped evidence to S3, e.g.:

* `evidence/runs/<platform_run_id>/wsp/wsp_start.json`
* `evidence/runs/<platform_run_id>/wsp/wsp_summary.json` containing at minimum:

  * READY offset receipt (topic/partition/offset)
  * per-output_id streamed counts
  * total sends, retries, failures
  * started_at / ended_at timestamps

(Exact schema finalized later; existence is mandatory.)

---

#### P6.7 Rollback / rerun rules (safe)

* WSP rerun is allowed and safe because:

  * `event_id` is deterministic
  * IG dedupe absorbs duplicates (P7 enforces idempotency)
* If WSP fails mid-stream:

  * rerun P6 after fixing the cause (IG reachability, auth key, stream_view completeness)
  * do not modify oracle inputs/stream_view unless P3 is re-run intentionally

---

#### P6.8 Cost notes

* WSP is a one-shot task; cost scales with runtime.
* Concurrency knobs can trade speed vs IG pressure; keep defaults conservative for v0.

---

### P7 INGEST_COMMITTED

**Intent:** Confirm the **Ingestion Gate (IG)** has durably committed the ingest outcomes for this run: admitted events are published to Kafka topics, receipts are written (append-only), quarantines are persisted, and publish ambiguity is handled per fail-closed policy. This phase is the “ingest boundary commit” that makes downstream RTDL safe to run.

---

#### P7.1 Semantics (what this phase means)

P7 means:

* IG has processed the WSP stream for the run and produced durable outcomes:

  * **ADMIT** → published to Kafka topic
  * **DUPLICATE** → recorded via receipt (no duplicate publish)
  * **QUARANTINE / ANOMALY** → payload preserved + metadata recorded
* IG receipts are **append-only evidence**, not mutable state.
* IG publish ambiguity is explicitly modeled and must not be “hand-waved.”

Local parity invariants preserved:

* Canonical dedupe key: `(platform_run_id, event_class, event_id)` (no deviation).
* Same dedupe tuple + different payload hash → **anomaly**; must not overwrite.
* No PASS → no read: downstream begins only after P7 gate passes.

---

#### P7.2 Pinned decisions (non-negotiable)

1. **IG is the only publisher to Kafka for admitted events**

* **MUST:** admitted events to traffic/context topics are published by IG only.

2. **Canonical dedupe identity**

* **MUST:** IG dedupe identity is exactly:

  * `(platform_run_id, event_class, event_id)`
* **MUST:** duplicates do not cause double-publish or double-actions.

3. **Append-only evidence**

* **MUST:** receipts are append-only.
* **MUST:** quarantines preserve payloads; no overwrites that destroy evidence.

4. **Publish ambiguity modeled + fail-closed**

* **MUST:** “publish unknown success” outcomes are represented explicitly (e.g., `PUBLISH_AMBIGUOUS`) and treated per fail-closed gate rules.
* **MUST NOT:** assume publish success/failure without evidence.

5. **Durable storage targets (dev_min)**

* **MUST:** Kafka is Confluent Cloud (topics pinned in handles registry).
* **MUST:** receipts + quarantine outputs are durably materialized to S3 under run scope.

---

#### P7.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**Kafka topics (writers)**

* `FP_BUS_TRAFFIC_FRAUD_V1`
* `FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1`
* `FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1`
* `FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1`
* (Optional) `FP_BUS_CONTROL_V1` for anomaly/governance facts

**Kafka connection**

* `SSM_CONFLUENT_BOOTSTRAP_PATH`
* `SSM_CONFLUENT_API_KEY_PATH`
* `SSM_CONFLUENT_API_SECRET_PATH`

**Receipts/quarantine**

* `S3_EVIDENCE_BUCKET`, `S3_EVIDENCE_PREFIX_PATTERN`
* `S3_QUARANTINE_BUCKET`, `S3_QUARANTINE_PREFIX_PATTERN`
* `RECEIPT_SUMMARY_PATH_PATTERN`
* `QUARANTINE_INDEX_PATH_PATTERN` (if you write index summaries)

**IG runtime**

* `SVC_IG`
* `ROLE_IG_SERVICE`

**Evidence**

* `EVIDENCE_RUN_ROOT_PATTERN` (canonical run root)

---

#### P7.4 Operator procedure (how to execute/verify P7)

P7 is mostly a **verification** phase (IG is already running from P2 and has been receiving traffic from P6). Operator does:

1. **Confirm IG is healthy**

* Ensure `SVC_IG` still RUNNING and not crashlooping.

2. **Confirm Kafka admits exist**

* Verify that each required topic has advanced offsets during this run window.
* Confirm messages are readable by a consumer (dev_min verifier task or CLI).

3. **Confirm receipt/quarantine evidence exists**

* Verify run-scoped receipt summaries exist in S3.
* If quarantines occurred, verify payloads exist in S3 quarantine prefixes.

4. **Confirm no publish ambiguity gate failure**

* Check for presence of any `PUBLISH_AMBIGUOUS` receipts/events. If present, P7 is FAIL unless explicitly allowed by scenario (default: FAIL).

---

#### P7.5 Gates / PASS criteria

P7 is PASS only if all are true:

1. **Admitted topics populated**

* Required Kafka topics contain messages for the run (offsets advanced and messages readable).

2. **Receipts are present and coherent**

* Receipt summaries exist and totals make sense (admit + duplicate + quarantine + anomaly = total attempts).
* Receipts are append-only (no evidence of overwrites).

3. **No publish ambiguity**

* No `PUBLISH_AMBIGUOUS` outcomes remain unresolved for the run. (Default rule: this is a hard fail.)

4. **Quarantine durable**

* Any quarantined/anomalous events have payloads persisted and are visible in evidence summaries.

5. **Downstream safe to consume**

* Only after P7 PASS may RTDL consume as “official run consumption.”

---

#### P7.6 Commit evidence (dev_min durable proof)

P7 MUST write run-scoped evidence under S3 evidence prefix, e.g.:

* `evidence/runs/<platform_run_id>/ingest/receipt_summary.json`

  * counts by outcome: ADMIT/DUPLICATE/QUARANTINE/ANOMALY/PUBLISH_AMBIGUOUS
  * counts by event_class
* `evidence/runs/<platform_run_id>/ingest/kafka_offsets_snapshot.json`

  * per topic: partition, start_offset, end_offset
  * timestamp snapshot
* `evidence/runs/<platform_run_id>/ingest/quarantine_summary.json` (if applicable)

(Exact schema finalized later; these summaries are mandatory.)

---

#### P7.7 Rollback / rerun rules (safe)

* **Do not delete Kafka topics or admitted messages mid-run.**
* If P7 fails due to publish ambiguity:

  * treat as stop-the-line
  * resolve by investigating IG publish evidence and rerunning under controlled conditions (often requires rerun of the full ingest slice, not partial).
* If failures are due to configuration/creds:

  * fix handles/ACLs
  * rerun WSP (P6); IG dedupe prevents double-admit where possible.
* Receipts/quarantine summaries can be regenerated, but **base receipts/audit evidence must remain append-only**.

---

#### P7.8 Cost notes

* Costs are dominated by:

  * IG service runtime
  * Kafka throughput (small for demos)
  * S3 writes for receipts/quarantine
* Teardown (P12) must shut down IG and destroy Kafka cluster/resources to stop ongoing costs.

---

### P8 RTDL_CAUGHT_UP

**Intent:** Run the RTDL core workers to consume admitted Kafka topics, build the required online state (context projections / join surfaces), and advance consumption only after durable commits, producing **origin_offset evidence** that supports replay and reconciliation. This phase declares that RTDL is “caught up enough” to proceed into the decision chain.

---

#### P8.1 Semantics (what this phase means)

P8 means:

* RTDL core workers consume the admitted dev_min Kafka topics:

  * traffic + required context streams (fraud-mode set).
* Context streams build/refresh state; traffic triggers join reads and prepares decision inputs.
* Workers record **origin_offset evidence** (topic/partition/offset) and only advance “I consumed this” checkpoints after durable commits.
* Missing context / late context triggers **explicit degrade** (reason recorded), never silent guessing.
* RTDL must reach a stable “caught up” condition (lag within thresholds / all partitions progressed) so decision chain can proceed.

---

#### P8.2 Pinned decisions (non-negotiable)

1. **No laptop runtime**

* **MUST:** RTDL core runs as ECS services/workers (daemon pack) in dev_min. 

2. **Consume only after P7 PASS**

* **MUST:** RTDL core consumption as “official” is allowed only after ingest committed (P7 PASS).

3. **Durable commit before offset advance**

* **MUST:** do not commit consumer offsets ahead of durable state writes (no “ack before write”).

4. **Origin offset evidence is mandatory**

* **MUST:** record origin_offset ranges for replay/reconciliation.

5. **Explicit degrade**

* **MUST:** missing/late context causes explicit degrade with reason captured into audit/evidence (not silent fallback).

6. **State is managed (no laptop DB/files)**

* **MUST:** RTDL state/checkpoints live in managed runtime storage (DB/KV). No local sqlite/files.

---

#### P8.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**RTDL core services**

* `SVC_RTDL_CORE_*` (one per worker type as you implement)
* `ROLE_RTDL_CORE` (Kafka consume + DB/KV write + S3 evidence write + logs)

**Kafka inputs**

* `FP_BUS_TRAFFIC_FRAUD_V1`
* `FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1`
* `FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1`
* `FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1`
* `SSM_CONFLUENT_*` (bootstrap/key/secret)

**Consumer group identities**

* `RTDL_CORE_CONSUMER_GROUP_ID` (pinned naming pattern)
* `RTDL_CORE_OFFSET_COMMIT_POLICY` (commit-after-write)

**State backends**

* `RDS_*` (if using Postgres)
* `CSFB_*` handles (if using a join KV; optional in some designs, but must be non-laptop if present)

**Evidence**

* `S3_EVIDENCE_BUCKET`, `S3_EVIDENCE_PREFIX_PATTERN`
* `S3_ARCHIVE_BUCKET`, `S3_ARCHIVE_PREFIX_PATTERN` (if archive writer is part of RTDL core)
* `OFFSETS_SNAPSHOT_PATH_PATTERN`

**Lag thresholds**

* `RTDL_CAUGHT_UP_LAG_MAX` (pinned for v0 demos)

---

#### P8.4 Operator procedure (how to execute/verify P8)

P8 is executed by ensuring RTDL core services are running and letting them consume until caught-up.

1. **Start/confirm RTDL core workers**

* Ensure the `rtdl_core` pack services are RUNNING (from P2).

2. **Observe consumption**

* Monitor CloudWatch logs and/or metrics:

  * partitions progressing
  * lag decreasing
  * state writes succeeding
  * explicit degrade counts (if any)

3. **Confirm caught-up condition**

* For each input topic/partition:

  * consumer has advanced offsets beyond the “run start” snapshot
  * lag is below `RTDL_CAUGHT_UP_LAG_MAX`

4. **Write offsets evidence snapshot**

* RTDL core (or a verifier task) writes an offsets snapshot artifact to the run evidence prefix.

---

#### P8.5 Gates / PASS criteria

P8 is PASS only if all are true:

1. **RTDL core workers are healthy**

* services not crashlooping; no persistent write failures.

2. **Offsets advanced with durability discipline**

* evidence indicates offsets committed only after durable writes (policy respected).

3. **Caught-up reached**

* lag across required topics/partitions is ≤ `RTDL_CAUGHT_UP_LAG_MAX`
* or “end offsets reached” for demo-sized runs.

4. **Origin_offset evidence exists**

* run-scoped offsets snapshot exists and is complete (topics + partitions + ranges).

5. **Explicit degrade recorded**

* any join misses are recorded as explicit degrade (counts present); no silent defaulting.

---

#### P8.6 Commit evidence (dev_min durable proof)

P8 MUST write run-scoped artifacts such as:

* `evidence/runs/<platform_run_id>/rtdl_core/offsets_snapshot.json`

  * topic, partition, start_offset, end_offset
  * consumer_group_id
  * timestamp
* `evidence/runs/<platform_run_id>/rtdl_core/caught_up.json`

  * lag summary
  * partitions covered
  * degrade counts summary
* (Optional) `archive_write_summary.json` if archive writer runs here

(Exact schema pinned later; existence is mandatory.)

---

#### P8.7 Rollback / rerun rules (safe)

* If RTDL core is misconfigured (wrong topics/creds/group id):

  * stop the services
  * fix handles
  * restart services
* If state backend contains run-scoped tables/keys:

  * clear only run-scoped rebuildable state (never delete append-only audit truth)
* Do not delete Kafka topic data as a rollback mechanism.
* Re-run is achieved by restarting consumers and/or resetting run-scoped state per your rerun rules.

---

#### P8.8 Cost notes

* RTDL core is a daemon pack: costs accrue for demo window.
* Keep replicas = 1 and keep lag thresholds conservative for demo-size data.

---

### P9 DECISION_CHAIN_COMMITTED

**Intent:** Execute and commit the **Decision Lane** end-to-end on dev_min: decision evaluation (DF), action execution (AL), and append-only audit logging (DLA/DLA evidence). This phase proves that for the run’s admitted traffic, the platform produced auditable decisions and idempotent outcomes under managed substrate and managed compute.

---

#### P9.1 Semantics (what this phase means)

P9 means:

* Decision lane consumers are running and healthy:

  * Degrade Ladder (DL) posture inputs are respected (if in-scope for your spine)
  * Decision Fabric (DF) resolves the active bundle/policy pointers and produces decision packages
  * Action Layer (AL) executes idempotent effects and records outcomes
  * Decision Log/Audit (DLA) writes append-only audit evidence and summaries
* The decision chain commits its outputs durably:

  * outcomes are recorded
  * audit records are appended
  * any degrade postures used are recorded as provenance
* No “double action” occurs even if upstream duplicates are replayed (idempotency keys enforced).

---

#### P9.2 Pinned decisions (non-negotiable)

1. **No laptop runtime**

* **MUST:** decision lane runs as ECS services/workers (daemon pack). 

2. **Append-only audit truth**

* **MUST:** DLA audit records are append-only.
* **MUST NOT:** update/overwrite past audit records. Derived views are allowed; truth is append-only.

3. **Idempotent actions**

* **MUST:** AL side effects are idempotent keyed by stable decision/action IDs.
* **MUST:** duplicates upstream must not cause double acts.

4. **Degrade is explicit**

* **MUST:** any degrade posture applied is explicitly recorded into decision/audit evidence; no silent degrade.

5. **No local state dependency**

* **MUST:** any decision lane state/checkpoints are persisted to managed stores (no local sqlite/files).

---

#### P9.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**Decision lane services**

* `SVC_DECISION_LANE_DL`
* `SVC_DECISION_LANE_DF`
* `SVC_DECISION_LANE_AL`
* `SVC_DECISION_LANE_DLA`
* `ROLE_DECISION_LANE` (Kafka consume/produce + DB writes + S3 evidence + logs)

**Kafka topics**

* Inputs:

  * `FP_BUS_RTDL_V1` (decision lane inlet)
  * `FP_BUS_AUDIT_V1` (if DLA publishes to audit topic)
  * (Any action-intent/outcome topics if separate)
* Confluent connection:

  * `SSM_CONFLUENT_*`

**State backends**

* `RDS_*` (if decision lane persists outcomes/indices in Postgres)
* Any policy/model bundle snapshot handles if used (registry snapshot for dev_min)

**Evidence**

* `S3_EVIDENCE_BUCKET`, `S3_EVIDENCE_PREFIX_PATTERN`
* `DLA_EVIDENCE_PATH_PATTERN`

**Idempotency**

* `ACTION_IDEMPOTENCY_KEY_FIELDS` (which fields form the key)
* `ACTION_OUTCOME_WRITE_POLICY` (append-only)

---

#### P9.4 Operator procedure (how to execute/verify P9)

P9 is executed by ensuring the decision lane services are running and letting them consume/commit until stable.

1. **Start/confirm decision lane services**

* Ensure `rtdl_decision_lane` pack services are RUNNING (from P2).

2. **Observe decision chain progress**

* Monitor logs/metrics for:

  * decisions produced
  * actions executed
  * outcomes recorded
  * audit records appended
  * degrade posture counts

3. **Confirm commit evidence written**

* Decision/audit summary artifacts exist under the run evidence prefix.

---

#### P9.5 Gates / PASS criteria

P9 is PASS only if all are true:

1. **Lane healthy**

* no crashloops; no persistent write failures.

2. **Decisions produced**

* DF produced decision packages for the run’s traffic events (counts non-zero unless scenario is zero-traffic).

3. **Actions committed idempotently**

* action outcomes exist, and duplicate drill does not create double acts.

4. **Audit appended**

* DLA audit evidence exists and is append-only (no overwrite semantics).

5. **Degrade recorded**

* any degrade postures appear in audit/evidence summaries (if used).

---

#### P9.6 Commit evidence (dev_min durable proof)

P9 MUST write run-scoped artifacts such as:

* `evidence/runs/<platform_run_id>/decision_lane/decision_summary.json`

  * decisions count
  * per-reason/degrade counts
* `evidence/runs/<platform_run_id>/decision_lane/action_summary.json`

  * intents count
  * outcomes count
  * idempotency duplicates prevented count
* `evidence/runs/<platform_run_id>/decision_lane/audit_summary.json`

  * audit records count
  * pointer(s) to audit slices if stored

Optionally:

* small audit slice files (bounded size) for portfolio proof

(Exact schema pinned later; existence is mandatory.)

---

#### P9.7 Rollback / rerun rules (safe)

* Stop/restart lane services to rerun consumption.
* If run-scoped derived state must be cleared, clear only rebuildable projections/outcome indices; **never** delete append-only audit history.
* Rerun correctness relies on:

  * upstream dedupe at IG
  * idempotency keys in AL
  * append-only audit semantics.

---

#### P9.8 Cost notes

* Decision lane is a daemon pack: cost accrues during the demo window.
* Keep replicas = 1 for v0 to avoid consumer duplication and drift.

---

### P10 CASE_LABELS_COMMITTED

**Intent:** Commit the **human loop surfaces** for the run on dev_min: case trigger ingestion, case timeline append-only updates, and label assertion append-only writes—backed by **managed runtime storage** (no laptop DB). This phase proves that the platform can produce and persist case/label artifacts under dev_min without violating writer-boundary and append-only laws.

---

#### P10.1 Semantics (what this phase means)

P10 means:

* Case/Labels components are running and consuming the correct inputs (case triggers, audit references).
* **Case Management (CM)** builds append-only case timelines keyed by the canonical subject identity (CaseSubjectKey).
* **Label Store (LS)** accepts label assertions as append-only events keyed by LabelSubjectKey.
* Writer boundaries are respected:

  * only the intended writers can append
  * idempotency keys prevent duplicates
  * no merges/re-writes unless explicitly designed (v0: no merges)

---

#### P10.2 Pinned decisions (non-negotiable)

1. **No laptop runtime**

* **MUST:** CM/LS run on managed compute as ECS services/workers. 

2. **Managed operational DB**

* **MUST:** CM/LS operational state is persisted to a **managed runtime DB** (no laptop Postgres, no sqlite checkpoints).

3. **Append-only truth**

* **MUST:** case timelines are append-only.
* **MUST:** label assertions are append-only.
* **MUST NOT:** rewrite or mutate history in place.

4. **Idempotency**

* **MUST:** case timeline appends and label assertion appends are idempotent under stable idempotency keys (duplicates do not double-append).

5. **By-ref evidence posture**

* **MUST:** CM must not duplicate deep payload truth; it stores refs/metadata sufficient to reconstruct evidence via receipts/audit stores.

---

#### P10.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**CM/LS services**

* `SVC_CM`
* `SVC_LS`
* `ROLE_CASE_LABELS` (DB read/write + Kafka consume + S3 evidence write + logs)

**Kafka topics (inputs)**

* `FP_BUS_CASE_TRIGGERS_V1` (if CM consumes triggers)
* `FP_BUS_AUDIT_V1` (if CM uses audit refs)
* `SSM_CONFLUENT_*`

**Managed DB**

* `RDS_ENDPOINT`
* `DB_NAME`
* `SSM_DB_USER_PATH`
* `SSM_DB_PASSWORD_PATH`
* `DB_SECURITY_GROUP_ID`
* (If migrations are required) `TD_DB_MIGRATIONS` (one-shot task)

**Evidence**

* `S3_EVIDENCE_BUCKET`, `S3_EVIDENCE_PREFIX_PATTERN`
* `CASE_EVIDENCE_PATH_PATTERN`
* `LABEL_EVIDENCE_PATH_PATTERN`

**Identity keys**

* `CASE_SUBJECT_KEY_FIELDS` (pinned composition)
* `LABEL_SUBJECT_KEY_FIELDS` (pinned composition)

---

#### P10.4 Operator procedure (how to execute/verify P10)

1. **Ensure DB exists and schema ready**

* Confirm managed DB exists (demo stack).
* Run DB migrations task if required (one-shot ECS task), then confirm schema present.

2. **Start/confirm CM/LS services**

* Deploy ECS services `SVC_CM` and `SVC_LS` with:

  * DB creds from SSM
  * Kafka creds from SSM
  * run-scope `platform_run_id` (if enforced for these services)
* Desired count = 1 each.

3. **Verify consumption and writes**

* Confirm CM consumes case triggers / audit refs and appends timeline events.
* Confirm LS accepts at least one label assertion and appends it.

4. **Verify evidence summaries written**

* Confirm run-scoped CM/LS summary artifacts exist in S3 evidence prefix.

---

#### P10.5 Gates / PASS criteria

P10 is PASS only if all are true:

1. **Services healthy**

* CM and LS services running, not crashlooping.

2. **DB writes succeeded**

* Case timeline append(s) exist in DB for this run.
* Label assertion append(s) exist in DB for this run.

3. **Append-only + idempotency hold**

* Duplicate inputs do not double-append.
* No in-place updates are used to “correct” history.

4. **Evidence summaries exist**

* S3 evidence contains case/label summaries for the run.

---

#### P10.6 Commit evidence (dev_min durable proof)

P10 MUST write run-scoped artifacts such as:

* `evidence/runs/<platform_run_id>/case_labels/case_summary.json`

  * number of case triggers processed
  * number of case timeline events appended
  * key IDs of exemplar cases (bounded)
* `evidence/runs/<platform_run_id>/case_labels/label_summary.json`

  * number of label assertions appended
  * label as-of timestamps (if used)

Optionally:

* bounded slices of case timeline events / label assertions (small, for proof)

(Exact schema pinned later; existence is mandatory.)

---

#### P10.7 Rollback / rerun rules (safe)

* If DB schema/migrations are wrong:

  * destroy demo DB and recreate (demo-only) OR run migrations fix (preferred).
* If services misconfigured:

  * stop services, fix handles, restart.
* Never “repair” by editing prior timeline/label rows in place.
* Rerun uses idempotency keys to avoid duplicate appends.

---

#### P10.8 Cost notes

* This phase introduces DB cost (managed DB) + service runtime.
* Keep demo windows bounded; teardown destroys demo DB.

---

### P11 OBS_GOV_CLOSED (Single-writer reporter)

**Intent:** Close the run with **single-writer** discipline and write the final, durable **evidence bundle** to S3: reconciliation summaries, environment conformance, anomaly summaries, and replay anchors. This phase is what makes the run “provable” and portfolio-grade.

---

#### P11.1 Semantics (what this phase means)

P11 means:

* A **single writer** (reporter) executes the close-out procedure for `platform_run_id`.
* It gathers evidence from prior phases (ingest receipts, Kafka offset snapshots, RTDL audit summaries, case/label summaries, conformance checks).
* It writes the canonical run closure artifacts under:

  * `evidence/runs/<platform_run_id>/...`
* It records:

  * run status = completed (or failed with stage)
  * replay anchors (origin_offset ranges)
  * reconciliation of intended vs observed counts
  * governance/anomaly summary
  * environment conformance snapshot

This is a strict translation of your local parity “reporter / closure” behavior with the same single-writer invariant.

---

#### P11.2 Pinned decisions (non-negotiable)

1. **No laptop runtime**

* **MUST:** reporter runs on managed compute as a **one-shot ECS task**. 

2. **Single-writer**

* **MUST:** only one reporter instance may write run closure for a given `platform_run_id`.
* **MUST:** if a lock/lease exists and is held, additional reporters must fail closed.

3. **Durable closure in S3**

* **MUST:** closure artifacts are written to S3 evidence prefix for the run.
* **MUST:** closure artifacts are derived summaries; they must not mutate base truth stores (receipts/audit/timelines).

4. **Replay anchors are mandatory**

* **MUST:** write origin_offset range summaries sufficient to support deterministic replay proof.

5. **Governance posture preserved**

* **MUST:** produce anomaly summary and environment conformance outputs consistent with your local checklist posture.

---

#### P11.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**Reporter task**

* `TD_REPORTER`
* `ROLE_REPORTER_SINGLE_WRITER` (S3 read prior evidence + S3 write closure + Kafka read offsets snapshots if needed + DB read for summaries + logs)

**Evidence**

* `S3_EVIDENCE_BUCKET`, `S3_EVIDENCE_PREFIX_PATTERN`
* `RUN_CLOSURE_MARKER_PATH_PATTERN`
* `RUN_REPORT_PATH_PATTERN`
* `REPLAY_ANCHORS_PATH_PATTERN`
* `RECONCILIATION_PATH_PATTERN`
* `ENV_CONFORMANCE_PATH_PATTERN`

**Inputs (summaries from prior phases)**

* `RECEIPT_SUMMARY_PATH_PATTERN`
* `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`
* `RTDL_CORE_EVIDENCE_PATH_PATTERN`
* `DECISION_LANE_EVIDENCE_PATH_PATTERN`
* `CASE_EVIDENCE_PATH_PATTERN`
* `LABEL_EVIDENCE_PATH_PATTERN`

**Single-writer lock**

* `REPORTER_LOCK_BACKEND` (DB table or S3 object lock pattern; pinned later)
* `REPORTER_LOCK_KEY_PATTERN`

---

#### P11.4 Operator procedure (how to execute/verify P11)

1. **Invoke reporter task**

* Run ECS task `TD_REPORTER` with env/config:

  * `platform_run_id`
  * evidence root prefix
  * any required pointers to Kafka topics or DB endpoints
  * lock backend config

2. **Observe completion**

* Task completes successfully (exit 0).
* Logs show:

  * lock acquired
  * evidence gathered
  * closure artifacts written
  * lock released

3. **Verify S3 evidence bundle**

* Confirm the run evidence directory contains:

  * run report
  * reconciliation summary
  * replay anchors
  * environment conformance snapshot
  * closure marker

---

#### P11.5 Gates / PASS criteria

P11 is PASS only if all are true:

1. **Single-writer lock succeeded**

* reporter acquired lock for this run and no concurrent writer succeeded.

2. **Closure marker exists**

* A run completion marker exists under the run evidence prefix.

3. **Evidence bundle complete**

* Required closure artifacts exist and reference the correct `platform_run_id`:

  * run report
  * reconciliation
  * replay anchors
  * conformance snapshot
  * anomaly/governance summary

4. **Replay anchors are valid**

* offset ranges are present for required topics/partitions and are consistent with prior phase snapshots.

---

#### P11.6 Commit evidence (dev_min durable proof)

P11 MUST write at minimum:

* `evidence/runs/<platform_run_id>/run_completed.json` (closure marker)
* `evidence/runs/<platform_run_id>/run_report.json`
* `evidence/runs/<platform_run_id>/reconciliation.json`
* `evidence/runs/<platform_run_id>/replay_anchors.json`
* `evidence/runs/<platform_run_id>/obs/environment_conformance.json`
* `evidence/runs/<platform_run_id>/obs/anomaly_summary.json`

(Exact schema pinned later; these paths are the dev_min equivalent of your local parity proof artifacts. )

---

#### P11.7 Rollback / rerun rules (safe)

* Reporter rerun is allowed if:

  * it remains single-writer (lock enforced)
  * it overwrites only **derived closure summaries** (not base truth)
* If partial artifacts exist:

  * rerun reporter to regenerate derived outputs
  * do not manually edit closure files unless you are repinning schema/contract

---

#### P11.8 Cost notes

* Reporter is a short-lived task; cost is bounded.
* It is the final “make the run provable” step.

---

### P12 TEARDOWN

**Intent:** Enforce the dev_min cost posture: **demo → destroy**. Tear down all demo-scoped infrastructure and runtime compute so no ongoing costs remain, while preserving **core** infra (S3 evidence + tfstate + budgets) and the run’s evidence bundle. P12 is part of the definition of “dev_min done.”

---

#### P12.1 Semantics (what this phase means)

P12 means:

* Everything created for the demo window is destroyed:

  * Confluent Kafka cluster/resources (if demo-scoped)
  * ECS services and tasks (IG, RTDL, decision lane, CM/LS, etc.)
  * runtime DB (RDS/Aurora/whatever is pinned for dev_min runtime)
  * any demo VPC/network resources (if created)
  * any demo-only SSM parameters (e.g., Confluent API keys)
* Core resources remain:

  * S3 evidence bucket + evidence bundles
  * S3 tfstate bucket + versions
  * DynamoDB lock table
  * budgets/alerts
  * minimal IAM scaffolding

P12 is not “optional cleanup.” It is the formal close-out that prevents budget bleed.

---

#### P12.2 Pinned decisions (non-negotiable)

1. **Destroy demo infra**

* **MUST:** run `terraform destroy` (demo stack) after each demo session.

2. **Core remains**

* **MUST:** core stack remains unless intentionally destroyed:

  * evidence persists
  * tfstate persists
  * budgets/alerts persist 

3. **No forbidden cost footguns**

* **MUST:** confirm no NAT Gateway exists.
* **MUST:** confirm no always-on LB exists.
* **MUST:** confirm no always-on compute fleet remains.

4. **Secrets hygiene**

* **MUST:** demo-scoped SSM parameters (e.g., Confluent API key/secret) are removed during teardown.
* **MUST NOT:** leave stale keys lying around for later accidental use.

---

#### P12.3 Required handles (must exist in `dev_min_handles.registry.v0.md`)

**Terraform**

* `TF_STATE_BUCKET`
* `TF_STATE_KEY_CORE`
* `TF_STATE_KEY_DEMO`
* `TF_LOCK_TABLE`

**Tagging**

* `TAG_PROJECT`, `TAG_ENV`, `TAG_OWNER`, `TAG_EXPIRES_AT`
  (used to locate and validate teardown)

**Demo resources**

* `CONFLUENT_ENV_NAME`, `CONFLUENT_CLUSTER_NAME`
* ECS service names (`SVC_*`)
* runtime DB identifiers (`RDS_INSTANCE_ID` / `RDS_CLUSTER_ID`)
* demo SSM paths (Confluent + DB creds if demo-scoped)

---

#### P12.4 Operator procedure (how to execute P12)

1. **Stop runtime compute (optional pre-step)**

* Scale ECS services to 0 or stop services if needed for clean shutdown.
  (Terraform destroy should handle this, but pre-stop can speed teardown.)

2. **Destroy demo stack**

* Run:

  * `terraform destroy` in `infra/terraform/dev_min/demo`

3. **Verify teardown**

* Confirm:

  * no ECS services remain running for dev_min
  * runtime DB is deleted
  * Confluent cluster/resources are deleted (or deprovisioned per provider behavior)
  * demo SSM secrets removed

4. **Confirm core + evidence remain**

* Evidence bundle still exists under:

  * `s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/...`

---

#### P12.5 Gates / PASS criteria

P12 is PASS only if all are true:

1. **Demo resources destroyed**

* Terraform demo destroy completes successfully.

2. **No cost-bearing leftovers**

* No ECS services/tasks remain.
* No demo DB remains.
* No demo network resources remain.
* No NAT Gateway exists.

3. **Secrets removed**

* Demo Confluent creds are removed from SSM.

4. **Evidence preserved**

* Evidence bundle still exists in S3 and is readable.

---

#### P12.6 Commit evidence (dev_min durable proof)

P12 MUST write a teardown proof artifact into the evidence bundle, e.g.:

* `evidence/runs/<platform_run_id>/teardown/teardown_proof.json`

Containing at minimum:

* timestamp
* terraform destroy status (success)
* a list of “confirmed absent” resource categories:

  * ecs_services=false
  * db=false
  * nat_gateway=false
  * load_balancer=false
  * confluent_cluster=false
* operator identity (optional)

(Exact schema pinned later; existence is mandatory.)

---

#### P12.7 Rollback / recovery rules

* If destroy fails:

  * do not “move on”
  * fix the teardown blockers and rerun destroy until PASS.
* If a resource remains (e.g., stray ECS service):

  * destroy it explicitly by tag and update Terraform state if necessary.
* The only acceptable end state is “billing-safe”.

---

#### P12.8 Cost notes

* P12 is the phase that enforces the £30/mo posture.
* It must be treated as part of the run, not afterthought.

---

## 6. Evidence Bundle Contract (Dev-min)

This section pins the **minimum dev_min evidence bundle** required for Spine Green v0. The evidence bundle is the durable “proof pack” for: gating, auditability, replay anchors, and run closure. It MUST exist in S3 and MUST be sufficient to validate every phase gate without relying on “it worked on my laptop.”

### 6.1 Evidence bundle root (pinned)

All run evidence MUST be written under:

* `s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/`

`<S3_EVIDENCE_BUCKET>` and any additional prefixing are pinned in `dev_min_handles.registry.v0.md`. 

### 6.2 Evidence design principles (pinned)

1. **Durable, run-scoped, correlation-first**

* Every evidence file MUST include `platform_run_id`.
* Where applicable, include `scenario_run_id`.
* Evidence must be reproducible or at least re-derivable, and written as immutable run-scoped artifacts.

2. **Append-only truth vs derived summaries**

* Base truth stores (receipts/audit/label timelines) are append-only and MUST NOT be rewritten.
* Derived summaries (counts, reconciliation, dashboards snapshots) MAY be regenerated by rerunning the reporter (P11) but must not claim to be “truth.”

3. **Compactness**

* Evidence should be summary-first with bounded slices.
* Do not dump full streams into evidence; the replay anchors + archive are the truth substrate.

4. **Phase gating friendliness**

* For each phase P#, there must be at least one clear proof artifact that the operator checklist can validate.

### 6.3 Required files (minimum set for Spine Green v0)

These are the **mandatory** artifacts for a dev_min run to be considered “Spine Green v0” complete.

#### 6.3.1 Run header and config provenance

* `run.json`

  * includes:

    * `platform_run_id`
    * `scenario_run_id` (if available at P1; else added by P5/SR and referenced)
    * env = `dev_min`
    * start/end timestamps (end set at P11)
    * run config payload (or pointer) + config digest
    * code version (git sha)
    * image digest/tag (from P(-1))
* `run_started.json` (optional if run.json already includes started_at; may be merged)

#### 6.3.2 Operate readiness (P2)

* `operate/daemons_ready.json`

  * ECS service/task ARNs
  * desired/running counts
  * run-scope value used

#### 6.3.3 Oracle lane evidence (P3)

* `oracle/seed_snapshot.json` (only if seed executed)
* `oracle/stream_sort_summary.json`

  * per required `output_id`: PASS/FAIL + counts + receipt pointers
* `oracle/checker_pass.json` (hard PASS marker)

#### 6.3.4 Ingest readiness and commit (P4–P7)

* `ingest/ig_ready.json` (P4)
* `ingest/ready_publish_receipt.json` (READY publish receipt; may live under sr/)
* `ingest/receipt_summary.json` (P7)

  * counts by ADMIT/DUPLICATE/QUARANTINE/ANOMALY/PUBLISH_AMBIGUOUS
  * counts by event_class
* `ingest/kafka_offsets_snapshot.json` (P7)

  * per topic: partition/start/end offsets

Optional but recommended:

* `ingest/quarantine_summary.json` (if quarantines occurred)

#### 6.3.5 RTDL core evidence (P8)

* `rtdl_core/offsets_snapshot.json`
* `rtdl_core/caught_up.json`

  * lag summary + degrade counts

#### 6.3.6 Decision lane evidence (P9)

* `decision_lane/decision_summary.json`
* `decision_lane/action_summary.json`
* `decision_lane/audit_summary.json`
* bounded audit slice(s) (optional)

#### 6.3.7 Case/Labels evidence (P10)

* `case_labels/case_summary.json`
* `case_labels/label_summary.json`
* bounded slices (optional)

#### 6.3.8 Obs/Gov closure + replay anchors (P11)

* `obs/environment_conformance.json`
* `obs/anomaly_summary.json`
* `replay_anchors.json`
* `reconciliation.json`
* `run_report.json`
* `run_completed.json` (hard completion marker)

#### 6.3.9 Teardown proof (P12)

* `teardown/teardown_proof.json`

### 6.4 Required fields (minimum schema)

Exact JSON schemas can be pinned later; for now the minimum required fields are:

* **All files**: `platform_run_id`, `written_at_utc`
* **Where applicable**:

  * `scenario_run_id`
  * `phase_id` (P#)
  * `source_handles` (references to handles registry keys used)
  * `counts` (if summary file)
  * `offset_ranges` (if offsets/replay)
  * `digests` (config digest; image digest)

### 6.5 Replay anchors (pinned requirement)

* Replay anchors MUST include, at minimum:

  * topic name
  * partition
  * start_offset
  * end_offset
  * capture timestamp
* Replay anchors must cover all topics required for Spine Green v0 proofs.

### 6.6 Evidence generation responsibilities (ownership)

* P2 writes daemon readiness snapshot.
* P3 writes oracle lane evidence.
* P4 writes IG ready evidence.
* P5 writes SR/READY receipts.
* P6 writes WSP summaries.
* P7 writes ingest commit summaries + offsets snapshot.
* P8/P9/P10 write their lane summaries.
* P11 reporter aggregates + writes closure artifacts and run_completed marker.
* P12 writes teardown proof.

### 6.7 Size and retention guidance (dev_min)

* Evidence bundle must remain compact:

  * summaries + bounded slices
* Long-lived evidence is retained; non-evidence operational data is lifecycle-managed elsewhere (oracle/quarantine/archive are bounded per migration authority). 

---

## 7. Drift Watchlist (Dev-min specific)

This section is the stop-the-line checklist for dev_min. If any item here occurs, it is considered **design drift** (or budget drift) and must be corrected before proceeding. This list is intentionally strict to prevent “it works on my laptop though” failures and to keep Codex from improvising beyond pinned decisions.

### 7.1 Semantic drift (platform laws violated)

Stop-the-line if any of these occur:

1. **Dedupe identity drift**

* IG dedupe identity is not exactly `(platform_run_id, event_class, event_id)`.

2. **Payload integrity drift**

* Same dedupe tuple with different payload hash is not treated as anomaly/quarantine (i.e., “overwrite” behavior appears).

3. **Append-only truth drift**

* Receipts, audit logs, case timelines, or label assertions are mutated in place (updates/deletes) rather than appended and derived into views.

4. **Stream_view bypass drift**

* WSP reads raw oracle outputs instead of `stream_view` artifacts (or P3 is skipped).

5. **READY bypass drift**

* WSP begins streaming without SR READY gate (P5).

6. **Offset discipline drift**

* Consumer offsets are advanced/committed before durable writes are complete (“ack before write”).

7. **Explicit degrade drift**

* Missing/late context or join failures cause silent defaulting/guessing rather than explicit degrade with reason recorded.

8. **Single-writer drift**

* Reporter close-out (P11) runs concurrently for the same `platform_run_id` or writes without lock discipline.

### 7.2 Migration scope drift (baseline definition violated)

Stop-the-line if:

1. **Learning/Registry sneaks in**

* OFS/MF/MPR work becomes required to declare “green” for this dev_min baseline.

2. **Phase semantics altered**

* P0..P11 meaning changes or gates are weakened to “make it run.”

### 7.3 Infrastructure drift (wrong substrate / wrong posture)

Stop-the-line if:

1. **Laptop runtime dependency appears**

* Any spine phase is executed on the laptop as part of the platform runtime (operator-only use is fine). 

2. **Kafka substrate drift**

* Event Bus does not use Confluent Cloud Kafka (for dev_min).

3. **S3 substrate drift**

* Oracle/evidence/quarantine/archive are not in S3 as pinned.

4. **Handles drift**

* Code or docs introduce a resource name/path that is not defined in `dev_min_handles.registry.v0.md`.

### 7.4 Budget drift (cost footguns)

Stop-the-line if:

1. **NAT Gateway exists**

* Any NAT gateway is provisioned (explicit prohibition).

2. **Always-on load balancer is introduced**

* ALB/NLB kept running outside demo window; or LB is required for normal dev_min operation.

3. **Always-on compute fleets**

* ECS services/DB/Kafka left running outside demo windows. (Core is allowed to remain; demo must be destroyed.)

4. **No teardown discipline**

* P12 teardown not executed, or teardown leaves cost-bearing resources behind.

### 7.5 Evidence drift (cannot prove the run)

Stop-the-line if:

1. **Evidence bundle incomplete**

* Required evidence bundle artifacts (Section 6) missing (no “run_completed.json”, no replay anchors, etc.).

2. **Proof is only in logs**

* Proof is not materialized to S3 evidence bundle and relies on “look at CloudWatch.” (Logs can supplement; evidence must be durable and run-scoped.)

3. **Offsets/replay anchors missing**

* Cannot support replay narrative because origin_offset ranges are missing.

### 7.6 Change control rule (how to handle drift)

* Any fix that changes a pinned decision MUST:

  * update the design-authority migration doc and this runbook,
  * update handles registry (if naming changes),
  * and include a decision-log entry in the PR.
* Codex MUST NOT “just implement around” pinned decisions to get a green run.

---

## Appendices

### Appendix A. Link map to local parity docs (where semantics were sourced)

This appendix is a **traceability map**: it shows exactly which local parity documents were used as the source-of-truth for semantics, gates, and process meanings in this dev_min runbook twin.

> Rule: If a future change modifies dev_min semantics, it must cite which local source(s) were reinterpreted or repinned.

#### A.1 Canonical phase flow (major process narrative)

* **Local source:** `spine_green_v0_run_process_flow.txt`

  * Used for: the canonical ordered flow of Spine Green v0, what “green” means, and the phase narrative boundaries (Spine-only).

#### A.2 Phase lifecycle + retry loops + commit evidence

* **Local source:** `addendum_1_phase_state_machine_and_gates.txt`

  * Used for: phase IDs `P0..P11` (and teardown), allowed rerun loops (e.g., P3 per-output rerun), lease discipline, and what constitutes phase PASS at the state-machine level.

#### A.3 Operator PASS checklist (what an operator checks)

* **Local source:** `addendum_1_operator_gate_checklist.txt`

  * Used for: the PASS/FAIL checks in dev_min phases (translated to managed substrate), and for defining proof artifacts required to proceed between phases. 

#### A.4 Process/job semantics + IO expectations

* **Local source:** `addendum_2_process_job_cards.txt`

  * Used for: what each process actually does, required IO, fail-closed behaviors, and highlighting migration-critical pitfalls (e.g., publish ambiguity, sqlite checkpoints, missing platform_run_id dedupe gap). 

#### A.5 Dev-min packaging intent (job vs daemon translation)

* **Local source:** `addendum_1_phase_to_packaging_map.txt`

  * Used for: dev_min packaging targets per phase, “no laptop compute” stance, CLI-only orchestration stance, and demo→destroy expectations. 

#### A.6 Dev-min migration authority + prohibitions

* **Dev-min authority source:** `dev-min_managed-substrate_migration.design-authority.v0.md`

  * Used for: substrate pins (Confluent + S3), budget posture, forbidden infra (no NAT, no always-on LB), evidence bundle policy, and change-control semantics. 

---

### Appendix B. Topic map pointer (source of truth = handles registry)

This appendix pins **where** the topic map is defined and how it is referenced. It intentionally avoids duplicating topic names in multiple places to prevent drift.

#### B.1 Source of truth

* The **only** source of truth for dev_min Kafka topic names (and their partitions/retention defaults) is:

  * `dev_min_handles.registry.v0.md` → Section **Kafka Topic Map**.

#### B.2 Referencing rule (non-negotiable)

* Code and docs MUST reference topics via their **handle keys**, not raw strings, wherever practical.

  * Example:

    * `FP_BUS_TRAFFIC_FRAUD_V1` (handle key)
    * rather than hardcoding `fp.bus.traffic.fraud.v1` everywhere.
* If any code path must embed a literal topic name (e.g., a third-party library constraint), that literal MUST match the handle registry value exactly, and the code must contain a comment referencing the handle key.

#### B.3 In-scope topics (Spine Green v0)

Spine Green v0 requires, at minimum, these topic handles to exist in the registry (exact strings pinned there):

* `FP_BUS_CONTROL_V1`
* `FP_BUS_TRAFFIC_FRAUD_V1`
* `FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1`
* `FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1`
* `FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1`
* `FP_BUS_RTDL_V1`
* `FP_BUS_AUDIT_V1`
* `FP_BUS_CASE_TRIGGERS_V1`
* `FP_BUS_LABELS_EVENTS_V1` *(optional if you emit derived label events; otherwise omit)*

#### B.4 Topic configuration defaults (where pinned)

* Default partitions and retention policies are pinned in the handles registry alongside the topic names.
* Any deviation for a demo run must be explicitly recorded in the run evidence bundle as part of the config digest payload (so it’s auditable and replayable).

---

### Appendix C. IAM boundary summary (by role)

This appendix summarizes **who can do what** in dev_min. It is a **high-level boundary map**; the exact IAM policy JSON is implementation detail, but must obey least privilege and match the IO ownership and writer boundaries defined in the local job cards.

> **Rule:** Every ECS task/service MUST run under a named role from the handles registry. No “default role” or shared admin role for runtime.

#### C.1 Source of truth

* Role names and the mapping from phase → role are pinned in:

  * `dev_min_handles.registry.v0.md` → **IAM Role Map** section.
* This appendix describes the required permission *shape* per role.

---

#### C.2 Roles (pinned set for Spine Green v0)

##### ROLE_TERRAFORM_APPLY (Operator / CI)

**Purpose:** Provision and destroy infra (core + demo) via Terraform.

**Must be able to:**

* Create/destroy:

  * S3 buckets/policies/lifecycle rules (core)
  * DynamoDB lock table (core)
  * Budgets/alerts (core)
  * ECS cluster/services/tasks + networking (demo)
  * RDS/Aurora (demo)
  * SSM parameters for demo secrets (demo)
* (If Confluent provider is used by Terraform) manage Confluent resources (demo).

**Must not be used by runtime services.**

---

##### ROLE_ECS_TASK_EXECUTION (ECS execution role)

**Purpose:** Standard ECS execution permissions (pull images, write logs).

**Must be able to:**

* Pull image from ECR
* Write logs to CloudWatch

**Must not:**

* Access S3/Kafka/DB application data (that belongs to task roles below).

---

##### ROLE_ORACLE_JOB (P3 sub-steps)

**Purpose:** Oracle seed/sync (optional), stream-sort, checker.

**Must be able to:**

* Read from `S3_ORACLE_BUCKET` input prefixes for `platform_run_id`
* Write to `S3_ORACLE_BUCKET` stream_view prefixes for `platform_run_id`
* Write oracle evidence summaries to `S3_EVIDENCE_BUCKET`
* Write logs to CloudWatch

**Must not:**

* Publish to Kafka (oracle jobs don’t publish to EB)
* Access CM/LS DB tables

---

##### ROLE_SR_TASK (P5)

**Purpose:** Scenario Runner gate + READY publish.

**Must be able to:**

* Read oracle inputs / stream_view readiness from S3 (as needed for gating)
* Write SR artifacts to `S3_EVIDENCE_BUCKET`
* Publish READY to Kafka control topic (`FP_BUS_CONTROL_V1`)
* Write logs

**Must not:**

* Publish to traffic/context topics
* Execute WSP streaming

---

##### ROLE_WSP_TASK (P6)

**Purpose:** World Streamer Producer.

**Must be able to:**

* Consume READY from `FP_BUS_CONTROL_V1` (Kafka read)
* Read `stream_view` from S3
* Call IG endpoint (network access)
* Write WSP evidence summaries to S3 evidence
* Write logs

**Must not:**

* Publish to Kafka topics directly (WSP → IG only)
* Write to quarantine bucket directly

---

##### ROLE_IG_SERVICE (P2/P4/P7)

**Purpose:** Ingestion Gate writer boundary.

**Must be able to:**

* Read runtime config/secrets (SSM paths) needed for Kafka and IG auth key
* Publish to Kafka topics:

  * traffic + context (and optionally control/anomaly)
* Write receipts summaries + quarantine payloads to S3
* Write IG readiness/commit evidence to S3 evidence
* (If IG uses DB state) read/write its tables in managed DB
* Write logs

**Must not:**

* Consume RTDL topics as a worker
* Write decision/audit truth

---

##### ROLE_RTDL_CORE (P2/P8)

**Purpose:** RTDL core workers (archive writer, projections, join prep).

**Must be able to:**

* Consume from Kafka admitted topics (traffic + context)
* Read/write its managed state backend (DB/KV) for projections/join state
* Write offsets snapshots and rtdl_core evidence to S3 evidence
* (If archive writer present) write bounded archive outputs to S3 archive
* Write logs

**Must not:**

* Execute actions (AL)
* Write append-only DLA truth (decision lane role owns that)

---

##### ROLE_DECISION_LANE (P2/P9)

**Purpose:** DL/DF/AL/DLA workers.

**Must be able to:**

* Consume decision inputs (rtdl lane topics)
* Read join surfaces/state needed for DF (DB/KV)
* Write outcomes/state to managed DB as required
* Append audit evidence and write decision lane summaries to S3 evidence
* Publish audit topic messages if part of design
* Write logs

**Must not:**

* Mutate receipts or oracle artifacts

---

##### ROLE_CASE_LABELS (P2/P10)

**Purpose:** CaseTrigger, CM, LS services.

**Must be able to:**

* Consume case triggers/audit refs as required
* Read/write CM/LS tables in managed DB
* Write case/label evidence summaries to S3 evidence
* Write logs

**Must not:**

* Publish admitted traffic/context (IG only)

---

##### ROLE_REPORTER_SINGLE_WRITER (P11)

**Purpose:** Run closure + reconciliation + replay anchors.

**Must be able to:**

* Read all run-scoped evidence summaries from S3
* Optionally query DB for counts/summaries (read-only)
* Optionally read Kafka for offsets snapshots if not already written
* Write closure artifacts to S3 evidence
* Acquire/release a run-scoped lock (DB table or S3 lock object)
* Write logs

**Must not:**

* Publish to traffic/context topics
* Mutate base truth stores

---

#### C.3 Least-privilege and writer-boundary rules (pinned)

* Every role must be scoped to:

  * only the buckets/prefixes it needs
  * only the topics it needs
  * only the DB tables it owns
* Roles must be distinct across major writer boundaries:

  * IG publisher role is not reused for RTDL or case/labels
  * reporter is not reused for workers

#### C.4 Future hardening (non-goals for v0)

* mTLS, service meshes, and organization-grade policy-as-code are future upgrades.
* v0 requirement is: writer boundary discipline exists, permissions are least privilege, and failures are fail-closed.

---

### Appendix D. Cost guardrails quick checklist

This appendix is the “operator safety card” to keep dev_min within the **~£30/mo** posture and prevent surprise bills. It is aligned with the pinned migration authority: **demo → destroy**, no NAT, no always-on LB, no always-on fleets.

#### D.1 Before you start a demo (preflight)

* [ ] Confirm Confluent trial/usage status and that the cluster type is **Basic**.
* [ ] Confirm AWS Budgets alerts exist (e.g., £10 / £20 / £28).
* [ ] Confirm demo window duration (set an “end time” so you don’t forget teardown).
* [ ] Confirm S3 lifecycle policies exist for non-evidence prefixes (oracle/quarantine/archive bounded). 

#### D.2 During the demo (keep costs bounded)

* [ ] Keep ECS replicas at **1** for all services (v0).
* [ ] Keep P3 (stream-sort) jobs scoped to only required output_ids; use per-output reruns, not full reruns.
* [ ] Avoid excessive log verbosity (CloudWatch ingestion can grow).
* [ ] Keep demo datasets small unless explicitly testing throughput.

#### D.3 Hard prohibitions (stop-the-line)

* [ ] **No NAT Gateway** exists (must be 0).
* [ ] No always-on ALB/NLB required for normal operation.
* [ ] No always-on ECS fleets outside demo window.
* [ ] No MSK provisioned cluster (out of budget posture).

#### D.4 End of demo (mandatory teardown)

* [ ] Run `dev-min-down` (terraform destroy demo).
* [ ] Verify Confluent cluster/resources are deleted (or deprovisioned) for demo scope.
* [ ] Verify ECS services/tasks are gone (0 running).
* [ ] Verify runtime DB is deleted.
* [ ] Verify demo SSM secrets are removed (Confluent keys, DB creds if demo-scoped).
* [ ] Verify evidence bundle remains in S3 under `evidence/runs/<platform_run_id>/...`.

#### D.5 “Did we leave money running?” quick commands (operator hints)

(Exact commands are implementation detail; Codex can supply these in the operator runbook.)

* List NAT gateways (expect none)
* List load balancers (expect none or demo-scoped deleted)
* List ECS services (expect none in demo after teardown)
* List RDS instances (expect none in demo after teardown)

#### D.6 If teardown fails (recovery)

* Stop-the-line until billing-safe:

  * destroy remaining resources by tag (`project=fraud-platform`, `env=dev_min`)
  * reconcile Terraform state if necessary
* Do not start a new demo run until the environment is back to “core-only + evidence.”

---
