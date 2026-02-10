# Platform Version Boundaries (v0 → v1 → v2+)
_As of 2026-02-05_

This document clarifies what “v0”, “v1”, and “v2+” mean for the platform, using the platform’s already-pinned design laws:
- deterministic evidence boundaries (`origin_offset`)
- idempotency + `payload_hash` anomaly detection
- append-only truth stores (DLA, Label Store)
- explicit archive truth posture
- governed activation through MPR (fail closed)
- minimal-hot-path observability (counters + low-volume governance facts)

---

## v0 definition
**v0 = the deterministic, auditable spine works end-to-end.**

v0 is the first version where the platform is *coherent as a system*: everything important is pinned, idempotent, replayable, and fails closed on integrity breaks. v0 can be modest in scale and can rely on manual ops/governance, but it must not rely on “tribal knowledge” for correctness.

### v0 “done” criteria
- **Truth rails are real**
  - Dedupe keys and `payload_hash` anomaly rules exist and are enforced at writer boundaries.
  - `origin_offset` evidence is stamped and carried as the evidence boundary.
  - DLA decisions and Label Store assertions are append-only and by-ref.
  - Archive truth posture is pinned (EB is retention-bounded; Archive is long-horizon truth).

- **Corridors exist at the correct choke points**
  - IG: validate → dedupe → publish state machine + receipts/backfill markers.
  - RTDL: inlet idempotency + context/FlowBinding join rules + DLA append.
  - AL: idempotent side effects keyed by decision identity.
  - LS: writer boundary with durable ack and anomaly handling.
  - MPR: deterministic resolution and explicit promotion/rollback events.

- **The loop closes**
  - EB → RTDL → DLA/AL → CM/LS → OFS/MF → MPR → DF resolves bundles deterministically.
  - No plane invents truth; all derived artifacts are by-ref and immutable.

- **Ops is minimally viable (low overhead)**
  - Counters + periodic run reconciliation JSON.
  - Low-volume governance facts for state-changing actions.
  - No heavy distributed tracing or real-time lineage computation required.

- **Promotion is safe but can be manual**
  - MPR is the sole activation authority.
  - Approvals/promotions/rollbacks are explicit and append-only.

---

## v0 → v1 boundary
**v1 = production hardening without changing v0’s laws.**

v1 keeps the same contracts and evidence discipline, but removes operational foot-guns and makes the platform safe under real failure modes, access controls, and environment hardening.

### v1 “done” criteria
- **Security is enforced, not just defined**
  - Strong service identity in dev/prod (mTLS or signed service tokens).
  - RBAC-enforced evidence ref resolution with time-bound access and audit.
  - Least-privilege boundaries are real (not “best effort”).

- **Run/config freeze becomes enforceable**
  - `run_config_digest` (or equivalent) is carried and validated consistently.
  - Mid-run changes are blocked or forced into explicit revision boundaries.

- **Durability is complete**
  - Archive writer is standard, not optional/planned.
  - Retention knobs are pinned/recorded; backfill paths exist.
  - “Publish ambiguous” reconciliation is implemented.

- **Operational resilience improves**
  - Backpressure + retry policies are robust (429/5xx/timeouts).
  - Receipts and reconciliation are reliable even under partial failures.
  - Health gates behave consistently with explicit “fail closed vs degrade” rules.

- **Controlled rollout can be introduced (optional but typical in v1)**
  - Shadow/canary modes exist as explicit, auditable modes.
  - Manual promotion still supported, automation optional.

---

## v1 → v2+ boundary
**v2+ = scale, automation, and optimization (while preserving v0/v1 laws).**

By v2+, the platform is no longer proving correctness; it is reducing cost/latency and increasing autonomy—without loosening evidence discipline.

### Typical v2+ upgrades
- **Scale + performance**
  - Higher throughput and lower latency.
  - Improved partition strategies (e.g., restoring join locality by enriching traffic).
  - More efficient state stores/caching and faster rebuilds.

- **Automation**
  - Automated retrain triggers (drift, delayed-label performance, anomaly thresholds).
  - Automated evaluation pipelines with explicit gates.
  - Automated promotion under policy (still explicit and auditable).

- **Advanced governance/compliance**
  - Corridor checks “as code” with PASS/FAIL artifacts.
  - Richer lineage graphs computed offline from immutable evidence.
  - Compliance exports and stronger multi-tenant isolation.

- **Operational maturity**
  - Multi-region/DR planning, stricter egress controls, automated key rotation.
  - SLO/SLA enforcement and structured incident workflows.

---

## Rule of thumb
- **v0:** Correct and replayable (the spine works).
- **v1:** Correct, replayable, and safe to operate in production.
- **v2+:** Correct, safe, and optimized/automated at scale.

---

## Non-negotiable invariants after v0
Once v0 ships, later versions must not break:
- `origin_offset` as evidence boundary (online and replay truth posture)
- append-only truth stores (DLA, Label Store) with by-ref evidence
- idempotency + `payload_hash` anomaly detection on writer boundaries
- deterministic, auditable promotion/rollback (MPR as activation authority)
- no silent “latest” reads in offline training paths (manifest-pinned inputs)
