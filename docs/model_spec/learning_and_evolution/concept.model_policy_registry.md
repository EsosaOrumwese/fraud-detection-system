black-box framing:
{
""""
Through a hierarchical modular lens, the **Model/Policy Registry** is the platform’s **controlled “source of deployable truth”**: it stores versioned bundles (models/policies), manages their lifecycle (approved → active → retired), and provides deterministic resolution for Decision Fabric (“what should I use for this decision right now?”).

## Level 0 — Black-box view

**Inputs**

* **Bundle publish requests** from Model Factory (ModelBundle + GateReceipt + metadata)
* **Governance actions** (approve, reject, promote, rollback, retire)
* Optional: runtime signals (performance/incident triggers) to support automated rollback policies

**Outputs**

* A **registry of bundles** with:

  * immutable bundle artifacts + metadata
  * evaluation evidence refs
  * compatibility info (required feature group versions, schema expectations)
* A **resolution interface** for Decision Fabric:

  * “Given context (env, tenant, model family, maybe degrade mode), resolve the active bundle”
* Lifecycle events (optional): `bundle_registered`, `bundle_promoted`, `bundle_retired`

One sentence: **“Store deployable bundles and deterministically answer ‘what’s active’ under governance.”**

---

## Level 1 — Minimal responsibility chunks (v0-thin)

1. **Bundle Intake & Validation**

* Accepts a bundle publish payload (by-ref artifacts + metadata)
* Validates: schema versions, required fields, gate receipt PASS, uniqueness constraints

2. **Bundle Store (Immutable)**

* Persists bundle metadata + artifact refs immutably
* Assigns `bundle_id` / `bundle_version` (or verifies MF-assigned IDs)

3. **Lifecycle / Promotion State Machine**

* States like: `DRAFT` → `CANDIDATE` → `APPROVED` → `ACTIVE` → `RETIRED`
* Who can transition states (approval policy)
* Rollback posture (activate previous bundle deterministically)

4. **Resolution Service (Selection Rules)**

* Deterministic “active bundle” selection:

  * per environment (dev/stage/prod)
  * per tenant/scenario (if you have multi-tenant)
  * optional: per model family / policy name
* Tie-break rules (no “latest by timestamp” unless explicitly defined)

5. **Compatibility & Constraints**

* Bundle declares required feature group versions (and possibly minimum schema versions)
* Registry enforces compatibility or surfaces warnings (fail closed vs warn-only posture)

6. **Audit & Governance Logging**

* Append-only registry event log for state changes (who/when/why)
* Query surfaces (list bundles, fetch metadata, fetch active)

---

## Level 2 — Boundaries with other components

* **Consumes:** Model Factory outputs (ModelBundle + GateReceipt)
* **Serves:** Decision Fabric resolution (“which model/policy bundle is active?”)
* **Feeds:** Observability/Governance for tracking promotions/rollbacks

---

## Cross-cutting “laws” (what must be tight)

* **Deterministic selection:** Decision Fabric must always get the same answer given the same resolution inputs.
* **Evidence-based promotion:** only PASS bundles can become active.
* **Append-only history:** registry state changes are auditable; no silent edits.
* **Rollback is explicit:** “active” changes are recorded and reversible via policy.
* **Compatibility pinned:** bundle specifies required feature versions; registry enforces or flags.
""""
}


tighten vs loose split
{
""""
Here’s the **v0-thin “tighten vs stay loose”** for the **Model/Policy Registry**, specifically to keep **Codex** from guessing the critical bits.

## What needs tightening (pin this in the spec)

### 1) Bundle identity + immutability rules

* What uniquely identifies a bundle:

  * `bundle_id` + `bundle_version` (or `model_family` + semver)
* Bundles are **immutable** once registered (metadata + artifact refs + digests).
* “Correction” = new bundle version, not edits.

### 2) Intake contract (what Registry accepts)

Pin minimum required fields for a `PublishBundleRequest`:

* `ModelBundle` (artifact refs + feature compatibility info + config hash)
* `GateReceipt` must be **PASS** (or registry rejects)
* provenance refs: training run id, evaluation report ref, dataset manifest refs
* submitter identity and timestamp (audit)

### 3) Lifecycle state machine + who can change it

* State enum list + allowed transitions (e.g., `REGISTERED → CANDIDATE → APPROVED → ACTIVE → RETIRED`)
* Who can perform transitions (role-level; minimal)
* “ACTIVE is unique” rule per scope (see §4)

### 4) Resolution scope + deterministic selection rules (most important)

Pin:

* What “scope” means (env, tenant, model_family/policy_name, maybe scenario class)
* Rule: at most **one ACTIVE** per `(scope_key_tuple)`
* Deterministic selection inputs DF provides (exact fields)
* Tie-break rules (never “latest by timestamp” unless explicitly defined)
* Rollback semantics: how to return to prior active bundle (explicit state change recorded)

### 5) Compatibility enforcement posture

Pin what Registry checks before allowing ACTIVE:

* required FeatureGroup versions / schema versions declared in bundle must be present/compatible with the platform
* fail-closed vs warn-only posture (choose v0 stance)

### 6) Audit log / event history requirements

* Registry must record every lifecycle change as an append-only `RegistryEvent`:

  * who/when/why + before/after state + bundle ref
* Query surfaces must be able to return the current active bundle and the history.

### 7) Idempotency and duplicate handling

* Publishing the same bundle twice must be safe:

  * same `bundle_id+version` → idempotent accept (return existing)
* Lifecycle transitions should be idempotent where possible (repeat “approve” = no-op).

### 8) Error model

Pin error categories and retryability:

* invalid payload, gate not PASS, conflict (active already exists), unknown bundle, auth, internal error.

---

## What can stay loose (implementation freedom)

* Storage backend (DB/object store) and indexing tech
* API transport (HTTP/gRPC/CLI)
* Exact auth implementation (as long as posture and audit fields exist)
* UI/approval workflow mechanics
* Whether lifecycle events are emitted to EB (optional)
* Caching strategy for resolution
* Performance/scaling choices

---

### One-line v0 contract

**“Registry stores immutable model/policy bundles, enforces evidence-based promotion, and provides deterministic ‘active bundle’ resolution per scope with full audit history.”**

""""
}


proposed doc plan + contract pack + repo layout
{
""""
Here’s the **Model/Policy Registry v0-thin package**: **3 spec docs + 1 contracts file + file tree** under `docs\model_spec\learning_and_evolution\model_policy_registry\`.

---

## MPR v0-thin doc set (3 docs)

### **MPR1 — Charter, Boundaries, and Bundle Immutability**

* Purpose: source of deployable truth (bundles + lifecycle)
* Authority boundaries (registry owns bundle truth + activation state; MF produces bundles)
* Bundle identity rules (`bundle_id`, `bundle_version`) + immutability/corrections posture
* Non-goals (no training, no decisioning, no UI spec beyond semantics)

### **MPR2 — Intake Contract, Lifecycle, and Compatibility Rules**

* `PublishBundleRequest` minimum required fields (ModelBundle + PASS GateReceipt + provenance refs)
* Idempotent publish behaviour (same bundle twice is safe)
* Lifecycle state machine (states + allowed transitions + roles posture)
* Compatibility enforcement posture (feature group versions/schema expectations; fail-closed vs warn-only)

### **MPR3 — Resolution API, Audit History, Ops & Acceptance**

* Deterministic “resolve active bundle” interface:

  * scope keys DF supplies (env/tenant/model_family/etc.)
  * uniqueness rule: 1 ACTIVE per scope
  * tie-break rules + rollback semantics
* Registry event log requirements (append-only `RegistryEvent`)
* Observability minimums (promotions, rollbacks, resolution errors/latency)
* Acceptance scenarios (publish idempotent, promotion gated by PASS, deterministic resolution, rollback recorded)

---

## 1 contracts file (v0)

### `contracts/mpr_public_contracts_v0.schema.json`

Recommended `$defs`:

* `BundleId`, `BundleVersion`
* `ScopeKey` *(object with required fields you choose: e.g., `environment`, `model_family`, optional `tenant_id`)*
* `ModelBundleRef` *(opaque ref + digest; can embed minimal metadata too)*
* `GateReceiptRefOrEmbed` *(PASS required for intake)*
* `PublishBundleRequest`

  * required: `bundle` (or `bundle_ref`), `gate_receipt`, `submitted_by`, `submitted_at_utc`
* `PublishBundleResponse`

  * required: `bundle_id`, `bundle_version`, `status` (ACCEPTED|DUPLICATE|REJECTED)
* `LifecycleState` (enum)
* `RegistryEventType` (enum)
* `RegistryEvent`

  * required: `event_id`, `bundle_id`, `bundle_version`, `scope`, `event_type`, `from_state`, `to_state`, `actor`, `observed_at_utc`, `reason`
* `PromoteRequest/Response` *(optional, thin)*
* `ResolveActiveRequest`

  * required: `scope`
* `ResolveActiveResponse`

  * required: `scope`, `active_bundle_ref`, `resolved_at_utc`
* `ErrorResponse` (thin)

**v0 note:** keep bundle artifacts as refs (don’t lock storage tech). Enforce determinism via scope keys + explicit ACTIVE state.

---

## File tree (Model/Policy Registry)

```text
docs/
└─ model_spec/
   └─ learning_and_evolution/
      └─ model_policy_registry/
         ├─ README.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ MPR1_charter_boundaries_bundle_immutability.md
         │  ├─ MPR2_intake_lifecycle_compatibility_rules.md
         │  └─ MPR3_resolution_audit_ops_acceptance.md
         │
         └─ contracts/
            └─ mpr_public_contracts_v0.schema.json
```

""""
}
