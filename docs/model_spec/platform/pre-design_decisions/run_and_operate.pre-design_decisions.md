# Run/Operate / Substrate Plane Pre-design Decisions (v0, Open to adjustment where necessary)

*As of 2026-02-05*

This plane defines the **mechanisms** that enforce the policies in Observability + Governance and make the four business planes operable: **Control & Ingress**, **RTDL**, **Case + Labels**, **Learning + Evolution**. It covers orchestration, deployment, environment ladder, configuration/secrets, and promotion mechanics. It must be **v0-practical**: production-shaped, but minimal—avoid platform drag and unnecessary complexity.

**v0 principle:** standardize *identity, config, secrets, and promotion* across services; keep runtime overhead low; fail closed on unsafe operations; use explicit environment profiles.

---

## P0 — Must settle before you plan/build

## 1) Environment ladder and “parity contracts”

**Questions**

* What environments exist (local/dev/prod) and what must be identical vs allowed to differ?
* How do we prevent “works in local, breaks in prod” drift?

**Pinned defaults**

* Environments: `local_parity`, `dev`, `prod`.
* Parity contract:

  * Same **schemas**, **envelope pins**, **dedupe keys**, **manifest/receipt layouts**, **registry scope rules** across all envs.
  * Allowed differences: capacity/scale (Kinesis shards, DB sizing), retention windows, auth mode (weaker locally), and observability sampling.
* Every run records `environment` in all governance facts and DatasetManifests.

---

## 2) Service identity and authentication modes (mechanism)

**Questions**

* How do services authenticate to each other in each environment?
* How do we keep this minimal in v0 but production-shaped?

**Pinned defaults**

* `local_parity`: API key allowlist (static) for IG and LS writer boundaries; no mTLS required.
* `dev`/`prod`: service-to-service authentication uses **mTLS** (preferred) or **signed service tokens** (acceptable). Choice must be uniform across platform services.
* All inbound writer boundaries (IG ingest, LS writer, MPR governance endpoints) must enforce authn and attach an `actor_id` (`SYSTEM::<service_name>` for services; `HUMAN::<id>` for operators).
* Writer boundaries must enforce authz allowlists per producer type; missing or invalid `actor_id` / `source_type` fails closed.
* `actor_id` is derived from the authn context (never from payload). `source_type` must match: `SYSTEM` or `HUMAN`.

---

## 3) Secrets and key management

**Questions**

* Where do secrets live and how are they injected?
* What is the rotation story in v0?

**Pinned defaults**

* Secrets stored in a single secret manager (implementation choice), injected at runtime; never committed to repo.
* Keys for encryption-at-rest (object store, DB) are managed via KMS-equivalent (implementation choice).
* Rotation:

  * v0: support manual rotation with a documented procedure; log rotation events as governance facts.
  * prod: enforce periodic rotation policy (P1 hardening).

---

## 4) Network posture and least privilege

**Questions**

* Which services are exposed vs internal?
* How do we prevent accidental data exfiltration?

**Pinned defaults**

* Public ingress allowed only for:

  * IG ingest (if needed externally)
  * CM UI/API (if present)
  * MPR governance endpoints (operator-only)
* All other services internal-only.
* Egress allowlist is recommended for prod (P1), but v0 must at least support network segmentation and private connectivity between core services.

---

## 5) Configuration authority, pinning, and run-config digests

**Questions**

* How do services load config, and what is pinned per run?
* How do we avoid config drift mid-run?

**Pinned defaults**

* Each service loads “wiring config” at startup, but **run-scoped operations must record config digests**:

  * IG: `policy_rev` derived from schema_policy + class_map + partitioning profiles, included in receipts.
  * RTDL: records bundle_ref + feature_def_set + policy_rev in decisions.
  * LS: records writer boundary version + label_type vocab version in label acks.
  * OFS/MF: record feature_def_set versions + `ofs_code_release_id`/`mf_code_release_id` in manifests/bundles.
* v0 posture: config changes mid-run are allowed only as explicit `policy_rev` boundaries; no silent mutation. (Obs/Gov records `POLICY_REV_CHANGED` facts.)
* Run-scoped operations must carry the expected `policy_rev`/config digest; missing or mismatched values fail closed (reject/quarantine). A policy_rev change starts a new run segment and never retroactively mutates prior evidence.

---

## 6) Deployment artifacts and immutability

**Questions**

* How do we ensure we can reproduce a build and roll back safely?
* What exactly is promoted?

**Pinned defaults**

* All services deployed as immutable artifacts (container images recommended), referenced by digest/tag.
* Runtime records must include `service_release_id` (image digest/tag or git SHA).
* Promotion mechanics:

  * MF publishes bundles; MPR promotes ACTIVE.
  * Only MPR updates ACTIVE pointers; all promotions/rollbacks are append-only registry events (Obs/Gov).

---

## 7) Orchestration and job execution (OFS/MF, reconcilers)

**Questions**

* How are offline jobs triggered and run?
* How do we prevent “always-on” expensive jobs?

**Pinned defaults**

* OFS and MF are executed as **explicit jobs** (scheduled or on-demand) with pinned intent inputs (DatasetManifest refs, label_asof, etc.).
* Job triggers produce governance facts: `OFS_BUILD_REQUESTED/COMPLETED`, `MF_TRAIN_REQUESTED/COMPLETED`.
* Jobs must fail closed on missing pinned inputs (no “latest”).
* Reconciliation/reporting jobs are periodic and low-cost; never block hot path.

---

## 8) Storage substrates and retention knobs (by environment)

**Questions**

* What stores exist for v0 and what retention policies apply?
* How do we align with replay/rebuild guarantees?

**Pinned defaults**

* Object store is the durable substrate for:

  * receipts/quarantines
  * DLA decision records (or refs)
  * archives
  * DatasetManifests, EvalReports, bundles
  * reconciliation artifacts
* DB substrates:

  * IG admission DB (idempotency + publish state)
  * RTDL state stores (Context Store, FlowBinding, OFP, IEG projection) — rebuildable
  * CM and LS stores (append-only timelines)
  * MPR store (registry state + events)
* Retention knobs are environment-specific but must not violate rebuild guarantees:

  * manifests/eval/bundle metadata are long-lived
  * materialized datasets may expire (rebuildable from Archive + LS)
  * EB retention is external config but must be recorded and monitored

---

## 9) Promotion safety corridors (mechanism enforcing governance)

**Questions**

* What prevents unsafe promotions?
* How do we ensure DF always resolves deterministically?

**Pinned defaults**

* Promotions require:

  * governance actor auth
  * evidence refs present (EvalReport, DatasetManifest, compatibility metadata)
* MPR must enforce:

  * ScopeKey uniqueness
  * deterministic resolution order (tenant→global→fallback→fail closed)
  * fail closed on incompatible bundles
* All promotion actions emit registry events and are reflected in run reconciliation summaries.

---

## 10) Evidence ref access mechanism (ties to Obs/Gov)

**Questions**

* How are evidence refs actually resolved securely?
* How do we keep it low overhead?

**Pinned defaults**

* Evidence refs are resolved via short-lived, signed access or service-gated fetch (implementation choice).
* Resolution requires authenticated identity; Obs/Gov defines what must be logged, Substrate enforces it.
* v0: do not log payload contents; log ref resolution events only.
* `local_parity`: allow direct signed URL or service-gated fetch, but always emit ref-resolution audit.
* `dev`/`prod`: evidence access via service-gated endpoint that mints short-lived signed URLs; no direct bucket access. Mechanism is uniform per environment.

---

## P1 — Settle soon (hardening, not required to start)

## 11) Egress allowlists + WAF + DDoS posture

* v0: basic segmentation and inbound auth.
* P1: strict egress allowlists and perimeter controls.

## 12) Automated secret rotation and key rollover

* v0: manual rotation supported.
* P1: automatic rotation with staged rollovers.

## 13) Multi-tenant isolation enforcement

* v0: tenant_id optional; isolate by scope keys and auth.
* P1: full tenant isolation at network/storage layers.

---

## Summary of v0 run/operate posture

* **Uniform auth modes** per env (simple local, strong dev/prod)
* **Immutable deployments** with release IDs recorded everywhere
* **Pinned configs** recorded as digests in evidence artifacts
* **Jobs are explicit**; no “always-on” expensive compute
* **Promotion is gated** by evidence + governance, enforced by MPR mechanics
