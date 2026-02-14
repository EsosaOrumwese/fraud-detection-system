# Cluster 5 - Round 1 Answers

## Q1) What contracts are validated where (which components validate what, at what boundary)?

The platform uses a **multi-boundary contract posture**.  
I do not rely on one global validator at the end. I validate at each ownership handoff, and each component re-validates what it consumes.

### Boundary 1: Control-plane run setup (SR -> WSP and run materialization)

- **Owner validating:** Scenario Runner (SR), then World Streamer Producer (WSP).
- **What is validated:**
  - run request contract,
  - re-emit request contract,
  - oracle/run-facts manifest contract.
- **Why here:** This is where run identity, run intent, and stream shape are fixed. If this boundary is loose, every downstream contract is operating on unstable assumptions.
- **Fail posture:** reject run setup (no stream start).
- **Authority files (pinned):**
  - `docs/model_spec/platform/contracts/scenario_runner/run_request.schema.yaml`
  - `docs/model_spec/platform/contracts/scenario_runner/reemit_request.schema.yaml`
  - `docs/model_spec/platform/contracts/scenario_runner/run_ready_signal.schema.yaml`
  - `docs/model_spec/platform/contracts/scenario_runner/run_facts_view.schema.yaml`

### Boundary 2: Producer publish boundary (DF/AL/CaseTrigger -> IG)

- **Owner validating:** publishing components (Decision Fabric, Action Layer, Case Trigger) before sending to Ingestion Gate.
- **What is validated:**
  - canonical event envelope shape,
  - required ContextPins/provenance fields needed by IG and downstream consumers.
- **Why here:** Prevents malformed events from entering ingress path and gives immediate component-local failure signal.
- **Fail posture:** do not publish event.
- **Authority files (pinned):**
  - `docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml`
  - `docs/model_spec/platform/contracts/real_time_decision_loop/decision_payload.schema.yaml`
  - `docs/model_spec/platform/contracts/real_time_decision_loop/action_intent.schema.yaml`
  - `docs/model_spec/platform/contracts/case_and_labels/case_trigger.schema.yaml`

### Boundary 3: Ingress admission boundary (IG as hard gateway)

- **Owner validating:** Ingestion Gate (IG), as authoritative ingress contract enforcer.
- **What is validated:**
  - canonical envelope schema,
  - payload schema resolved from event class policy (including allowed schema versions),
  - class-policy compatibility checks (event class, pins, version constraints).
- **Additional contracts IG validates before persisting evidence:**
  - ingestion receipt contract,
  - quarantine record contract.
- **Why here:** IG is the admission authority. Admission must be schema-valid, policy-valid, and evidence-valid before it is treated as platform truth.
- **Fail posture:** fail-closed quarantine/no admission.
- **Authority files (pinned):**
  - `docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml`
  - `docs/model_spec/platform/contracts/ingestion_gate/ingestion_receipt.schema.yaml`
  - `docs/model_spec/platform/contracts/ingestion_gate/quarantine_record.schema.yaml`

### Boundary 4: Event bus consumption boundary (EB -> RTDL services)

- **Owner validating:** each consuming service at intake (IEG, OFP, DF inlet, DLA inlet, and other event consumers).
- **What is validated:**
  - canonical event envelope contract again at consumer ingress.
- **Why here:** Defends against upstream drift, replay irregularities, and mixed-producer reality. Consumers do not trust that “someone else already validated.”
- **Fail posture:** reject/quarantine/skip with logged reason (no silent parse).
- **Authority files (pinned):**
  - `docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml`

### Boundary 5: Component domain-contract boundary (inside each service lane)

- **Owner validating:** each component’s contract module at service ingress and state-transition points.
- **What is validated (examples):**
  - DF: decision-response and action-intent structures + lineage constraints,
  - AL: action-intent/action-outcome structures + lineage safety,
  - Case/Label lane: case trigger payloads, timeline events, label assertions,
  - CSFB/Archive/Degrade lane: join-flow bindings, archive records, degrade decision structures,
  - Learning lane: train/build/eval/bundle/lifecycle records.
- **Why here:** Envelope validation alone is not enough; domain invariants (IDs, lineage, state transition legality) must be enforced where business logic executes.
- **Fail posture:** reject transition and record explicit error, not partial commit.

### Boundary 6: Registry and learning governance boundary

- **Owner validating:** Learning Registry and learning-related components.
- **What is validated:**
  - dataset registration contracts,
  - evaluation record contracts,
  - model bundle/lifecycle contracts,
  - bundle resolution and activation structures.
- **Why here:** prevents model/feature governance drift and protects promotion lifecycle from malformed registry payloads.
- **Fail posture:** no activation/promotion on invalid contract state.

### Operational rule across all boundaries

The enforcement law is: **validate at producer boundary, validate at ingress authority, validate again at consumer boundary, and validate domain transitions at the component that owns the state change.**

That is why contract failure cannot silently “pass through” the platform as long as each ownership boundary is operating.

## Q2) What was the key schema resolution failure you hit (e.g., `$id` anchor, resolver pathing, draft mismatch, registry collisions)?

The key failure was a **fragment-resolution collapse at IG payload validation**:

- IG policy correctly pointed to row-level schema fragments (for per-event validation),
- but the resolver treated those fragments like standalone schemas,
- so root schema graph context was lost during validation.

In practical terms, one contradiction drove the problem:

- I needed strict Draft 2020-12 validation against real engine contracts,
- but the resolver path was not preserving how those contracts were authored (graph-style refs across files and anchors).

The failure had three linked mechanics:

1. **Anchor/context loss on fragment loads**
   - Loading only `#/.../items` dropped root-level `$id`, `$schema`, and `$defs`.
   - Internal refs that depended on root context then failed.

2. **Relative `$id`/URI anchoring mismatch**
   - Some contract files used relative or missing `$id` semantics.
   - Without URI normalization, relative refs had no stable base anchor.

3. **Mixed reference-style pathing**
   - Real contracts mixed reference styles (bare filenames, repo-root `docs/...` refs, and interface-pack-relative refs).
   - A single naive resolver root could not resolve all three reliably.

So the “key failure” was not just a bad schema file.  
It was that our validator was strict, but its **resolution model** was weaker than the real multi-file contract topology.

Concrete incident pin (the failure slice):
- **Event family that exposed it:** `arrival_events_5B` (`event_class=context_arrival`) at IG payload validation.
- **Policy entry involved:** `config/platform/ig/schema_policy_v0.yaml` for `event_type: arrival_events_5B`.
- **Fragment ref that failed in practice:** `docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml#/egress/s4_arrival_events_5B/items`.
- **Why this fragment mattered:** once IG moved to item-level validation, fragment-only loading dropped root `$defs/$id/$schema` and triggered resolver failures on internal refs.

## Q3) What exactly broke (false PASS vs false FAIL vs inconsistent behavior across machines)?

It was primarily a **false FAIL** problem, with a secondary **environment-consistency risk**.

### 1) Primary break: false FAIL at ingress admission

Valid events were being rejected by IG even when producer payload intent was correct.

- Failure modes observed:
  - `SCHEMA_FAIL` (schema validation reject),
  - `INTERNAL_ERROR` from resolver/ref handling.
- Why that is false FAIL:
  - the event payload shape/business meaning could be valid,
  - but validation failed because resolver context was incomplete (fragment/context loss) or path assumptions were wrong,
  - not because the business contract itself was necessarily violated.

Operationally, this appeared as deterministic quarantine/admission failure on classes that should have been admissible under the intended contract mapping.

Concrete failure anchors:
- **Signature 1 (schema mismatch stage):**
  - platform log pattern during the Jan-29 SR->WSP->IG chain run: `IG quarantine ... reason=SCHEMA_FAIL` for `event_type=arrival_events_5B`.
- **Signature 2 (resolver stage after item-fragment switch):**
  - IG emitted `INTERNAL_ERROR` when resolving refs like `#/$defs/...` from a fragment-loaded schema context.
- **Run-anchored receipt proof for the same false-fail class (schema enforcement at IG):**
  - `platform_run_id=platform_20260207T221155Z`
  - `s3://fraud-platform/platform_20260207T221155Z/ig/receipts/0a7e36376ffc8fb37e9d2fca7b4a02c3.json`
  - `s3://fraud-platform/platform_20260207T221155Z/ig/quarantine/0a7e36376ffc8fb37e9d2fca7b4a02c3.json`
  - observed reason path: `reason_codes=["SCHEMA_FAIL"]`.

### 2) Secondary break: inconsistent behavior across execution contexts

Before hardening, schema reference resolution had path-style sensitivity:

- interface-pack-relative refs,
- bare-filename refs,
- repo-root `docs/...` refs.

When resolver assumptions did not match the active reference style, behavior could differ across runs/environments, producing non-uniform failure surfaces.

That is not acceptable for a platform contract boundary: same contract + same payload must produce the same admission verdict regardless of runtime context.

### 3) What did **not** happen

- This was **not** a “false PASS” class (we were not silently admitting invalid payloads because validation was disabled).
- The platform posture stayed fail-closed; the cost was over-rejection and instability in resolver behavior, not permissive bad-data admission.

### 4) Practical impact on platform flow

Because IG is the admission authority, this false-FAIL class blocked downstream planes:

- RTDL traffic admission became unreliable for affected event families,
- bounded acceptance runs could fail for contract-path reasons instead of true business-rule reasons,
- and debugging signal quality dropped because resolver mechanics were polluting contract verdicts.

## Q4) What was the fix:

I fixed this in layered order. It was not one patch.

### 1) `$id`/anchor fix (schema graph anchoring)

I changed schema loading so the validator always has a usable URI anchor:

- if a loaded schema had missing or non-URI `$id`, I assigned an in-memory file-URI base before validator construction,
- for policy fragment validation, I stopped treating fragment nodes as standalone documents and validated through a `$ref` wrapper anchored to the base file URI.

That preserved root graph context (`$id`, `$defs`, `$schema`) while still validating row-level payload fragments.

### 2) Resolver logic fix (real contract topology support)

I replaced brittle resolution assumptions with registry-based resolution and explicit retrieval rules:

- migrated to `referencing.Registry`/`Resource` + Draft 2020-12 validator flow,
- introduced deterministic file-URI retrieval logic (including Windows path normalization),
- hardened resolution order for mixed reference styles:
  - interface-pack-relative path resolution,
  - repo-root handling for explicit `docs/...` refs,
  - controlled fallback for shared engine schema filenames.

I kept fail-closed behavior for unresolved/unsupported refs; no permissive fallback was added.

### 3) Schema-dialect compatibility fix (nullable semantics)

After path/anchor hardening, another contract-interoperability gap remained:

- some upstream schemas used OpenAPI-style `nullable: true`,
- Draft 2020-12 validator does not natively treat that as a null union.

I normalized loaded schemas in-memory so nullable fields become explicit JSON-Schema-compatible null unions before validation.  
This removed a false-fail class without weakening strict validation rules.

### 4) Canonical serialization/hashing fix (deterministic contract posture)

Resolver hardening was the blocker fix.  
Separately, I hardened canonical serialization surfaces so contract decisions remain stable:

- payload-hash canonicalization uses stable JSON serialization (`sort_keys`, fixed separators, UTF-8) over the intended payload tuple,
- policy-digest computation also uses canonical JSON content normalization.

This was important for drift prevention and repeatability, but it was not the primary root-cause fix for the resolver collapse.

Concrete code anchors for the resolver hardening:
- **Registry + Draft 2020-12 wiring:**
  - `src/fraud_detection/ingestion_gate/schema.py`
  - `src/fraud_detection/ingestion_gate/schemas.py`
- **Fragment validated via wrapper `$ref` anchored to base URI:**
  - `src/fraud_detection/ingestion_gate/schema.py` -> `_load_schema_ref(...)` (`schema_for_validation = {"$ref": f"{base_uri}#{fragment}"}`)
- **`nullable: true` normalization:**
  - `src/fraud_detection/ingestion_gate/schema.py` -> `_normalize_nullable(...)`
- **Filename fallback + repo-root/docs path resolution for mixed ref styles:**
  - `src/fraud_detection/ingestion_gate/schemas.py` -> `SchemaRegistry._uri_to_path(...)`
  - `src/fraud_detection/ingestion_gate/schema.py` -> `_load_schema_ref(...)` (`docs/` and absolute path handling)

## Q5) How do you ensure determinism:

I enforce determinism as a contract law at validation time:

- **same payload + same schema bundle + same policy map + same validator dialect = same verdict**.

Everything in the fix was aimed at making that equation true in practice.

### 1) Fixed validator dialect and execution model

- Validation is pinned to Draft 2020-12 (`Draft202012Validator`).
- Resolution is pinned to `referencing.Registry` + explicit resource retrieval.

This removes “it depends on legacy resolver behavior” drift.

### 2) URI-anchored schema graph resolution

- Loaded schema documents are anchored to file URIs.
- Relative or missing `$id` issues are normalized before validation.
- Fragment validation is executed as URI `$ref` into the anchored root document, not as detached fragment documents.

This guarantees internal refs resolve from the same base graph every run.

### 3) Deterministic path resolution posture

- Explicit `docs/...` references are treated as repo-root scoped.
- Interface-pack style references are supported deliberately.
- Shared filename fallback is controlled and stable for known contract topology.

This is how we removed the former “reference style changes outcome” behavior.

### 4) Canonicalization for hash-sensitive contract decisions

Where contract behavior depends on content hashing (for dedupe/policy digests), I use canonical JSON serialization:

- sorted keys,
- fixed separators,
- UTF-8 bytes.

So equivalent payloads map to the same hash/verdict path.

### 5) No working-directory drift (practical guarantee scope)

The practical anti-CWD rule is:

- schema roots/policy refs are loaded from pinned profile wiring,
- once a schema is loaded, all downstream resolution is file-URI anchored rather than shell-location anchored.

So validation does not drift because a process was launched from a different folder, **provided the same wiring/profile inputs are used**.

### 6) Determinism fail posture

If resolver context is incomplete or a ref cannot be resolved, the path is fail-closed (reject/quarantine), not permissive fallback.

That prevents non-deterministic “best effort pass” behavior from entering admission truth.

## Q6) Give one artifact proving the new posture (e.g., registry bundle, resolver trace log, or a repeatable validation command with stable output).

My strongest proof artifact is a **repeatable ref-resolution contract gate**:

- **Artifact type:** deterministic compatibility test (binary pass/fail).
- **Command:**
  - `python -m pytest -q tests/services/scenario_runner/test_contract_compatibility.py::test_interface_pack_refs_resolve -q`
- **Observed result on current repo state:** `1 passed`.

### Why this is valid proof (not just a unit-test vanity metric)

This gate walks interface-pack references and fails if any contract reference cannot be resolved under the hardened resolver rules.

It directly exercises the failure classes we fixed:

- mixed reference styles (interface-pack relative, repo-root `docs/...`, and filename-style lookups),
- fragment pointer traversal and fallback matching behavior,
- deterministic ref traversal without working-directory dependency assumptions.

So when this gate passes, it proves the schema-reference graph is resolvable under the current contract corpus; when it fails, it fails loudly with the broken ref path.

### Why I use this as the interview artifact

It is:

- **repeatable** (same command any reviewer can run),
- **deterministic** (same contracts -> same result),
- **relevant to the exact incident class** (resolver/path/anchor stability),
- and **fail-closed** (no soft-success masking unresolved refs).

## Q7) What rule did you adopt that prevents “schema drift” from creeping back in?

I adopted a strict **contract-coherence law** for onboarding and runtime:

- **no event family is considered onboarded unless four surfaces are coherent at the same time**:
  1. class mapping (`event_type -> class`),
  2. schema policy (required version + payload schema ref),
  3. required pin set for that class,
  4. partitioning profile/stream mapping.

If any one of these drifts, that is a hard failure, not a warning.

### 1) Runtime enforcement rule (fail-fast, not best-effort)

At IG startup, policy/class coherence checks run before live admission:

- RTDL families must map to expected classes,
- schema version requirements must be explicit and allowlisted,
- required pins must include the full run/provenance set and exclude invalid pin semantics,
- mismatches fail startup (`IG_RTLD_POLICY_ALIGNMENT_FAILED` class).

This prevents silent misclassification drift from entering runtime.

Enforcement pin:
- Implemented in `src/fraud_detection/ingestion_gate/admission.py` via `_validate_rtdl_policy_alignment(...)`.
- Hard-fail signal: raises `RuntimeError("IG_RTLD_POLICY_ALIGNMENT_FAILED:...")` before live admission starts.

### 2) Change-control rule (digest-bound policy identity)

Policy surfaces are digest-bound through canonical hashing:

- schema policy file,
- class map file,
- partitioning profile file.

That digest is carried as policy revision identity in receipts/quarantine provenance.  
So “policy changed but nobody noticed” becomes auditable drift, not invisible drift.

Digest + recording pins:
- Digest computation: `src/fraud_detection/ingestion_gate/policy_digest.py` -> `compute_policy_digest(...)`.
- Digest source set at startup in `IngestionGate.build(...)` from:
  - `schema_policy_ref`
  - `class_map_ref`
  - `partitioning_profiles_ref`
- Recorded in admission evidence payloads:
  - receipt: `policy_rev.content_digest` and `run_config_digest`
  - quarantine: `policy_rev.content_digest` and `run_config_digest`
  (implemented in `src/fraud_detection/ingestion_gate/admission.py`).

### 3) Resolver-authority rule (no ad-hoc schema forks)

I do not duplicate schema fragments into ad-hoc local copies to make validation pass.

- schema refs remain anchored to contract-authority families,
- resolver hardening is done in loader/retriever behavior, not by loosening contracts,
- unresolved/ambiguous refs remain fail-closed.

That prevents forked-schema drift over time.

### 4) Onboarding-gate rule (tests required for every new family)

A new event family is only accepted when contract gates prove coherence end-to-end:

- class map + schema policy assertions,
- partition profile routing assertions,
- alignment checks that fail on mismatch.

This is why additions like RTDL decision/action families and case-trigger family were enforced through explicit onboarding tests rather than manual config edits.

### 5) Practical anti-drift summary

My anti-drift rule is simple:

- **No coherent map, no runtime.**
- **No digested policy change, no trusted provenance.**
- **No contract gate pass, no onboarding claim.**

That rule keeps schema governance from regressing back into “works on one path” behavior.
