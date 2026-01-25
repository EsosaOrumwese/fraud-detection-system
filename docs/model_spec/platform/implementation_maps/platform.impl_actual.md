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
