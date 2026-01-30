# Segment 1A — Design vs Implementation Observations (Pre‑Data Assessment)

Date: 2026-01-30
Scope: Read-only analysis of 1A state-expanded specs (S0–S9) and 1A contracts, plus segment_1A.impl_actual.md (implementation decisions). This report captures what was **noticed** about design intent and how it was **interpreted** in implementation before examining the produced datasets.

## Sources Reviewed
- 1A state-expanded specs: `docs/model_spec/data-engine/layer-1/specs/state-flow/1A/state.1A.s0.expanded.md` … `state.1A.s9.expanded.md`
- 1A contracts: `docs/model_spec/data-engine/layer-1/specs/contracts/1A/{dataset_dictionary.layer1.1A.yaml, artefact_registry_1A.yaml, schemas.1A.yaml, schemas.layer1.yaml, schemas.ingress.layer1.yaml}`
- Implementation decisions: `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md`

## Design Intent — What 1A is trying to achieve
Segment 1A is the **foundation and outlet world constructor** for Layer‑1. The intent is:
- Deterministic, sealed construction of merchant/outlet universes using governed parameters and strict hashing (parameter_hash, manifest_fingerprint).
- Strict input provenance and reproducibility (sealed_inputs, s0_gate_receipt, immutable outputs, validation bundles).
- Explicit RNG tracing and auditability where stochastic components exist, while preserving deterministic outputs for fixed identity tuples.
- Clear separation between **authority surfaces** (catalogues, candidate sets, design matrices) and **validation/gate artifacts** (bundles, receipts).
- A strictly enforced “no PASS → no read” posture for external consumers, with S9 as the canonical validation publisher.

In short: 1A is designed to produce **auditable, deterministic world stubs** (outlets and related scaffolding) that are stable under replay and safe for downstream segments to consume.

## Implementation Interpretation — What changed or was clarified
The implementation log is rich and shows a number of clarifications and corrections made to align behavior with the intended spec. The major patterns I noticed are:

### 1) S9 as the canonical validation bundle publisher
**Design intent:** S9 owns the final validation bundle + PASS gate.
**Implementation decision:** S0 bundle emission was disabled by default to avoid immutability violations. S9 becomes canonical; S0 bundle output only via explicit opt‑in.
**Implication:** The runtime no longer risks overwriting S9’s authoritative bundle; validation readiness is cleaner, but some debugging artifacts are now opt‑in.

### 2) Contract source switching (model_spec vs contracts mirror)
**Design intent:** Contracts exist and are binding, but the code needed an abstraction to switch between `docs/model_spec` and `contracts/` without path rewrites.
**Implementation decision:** A ContractSource abstraction was introduced to keep lookups consistent and environment‑switchable.
**Implication:** 1A is now intentionally flexible between spec and deployed contract roots. This affects how validation schemas and dictionaries are resolved and is an important assumption in any data assessment.

### 3) Input resolution order and run-local staging
**Design intent:** Prefer run-local staged inputs when available.
**Implementation decision:** Pre‑run S0 input resolution cannot consult run-local staging because run_id doesn’t exist yet. This is documented as a temporary limitation.
**Implication:** For S0, staging is effectively external‑root first; later stages may differ. This is a known deviation to remember when tracing provenance or comparing sealed_inputs to expectations.

### 4) Parameter hash and manifest fingerprint specifics
**Design intent:** strict basenames, explicit dependency closure, deterministic hashing.
**Implementation decision:** parameter_hash uses spec-governed basenames; manifest_fingerprint uses file basenames and enforces uniqueness. Git commit bytes are included in manifest hash.
**Implication:** The manifest fingerprint is path‑name‑based and can fail on duplicate basenames. That is a deliberate strictness choice which can surface as failures if multiple artifacts share a filename.

### 5) JSON Schema enforcement for ingress
**Design intent:** merchant_ids table validated against schema; no “silent semantics.”
**Implementation decision:** explicit JSON Schema adapter plus row‑level validation.
**Implication:** Merchant table quality is enforced before any RNG; design intent is stricter than many typical pipelines and may lead to early S0 aborts if inputs don’t match schema.

### 6) RNG trace accounting and S9 fixes
**Design intent:** exactly one trace row per RNG event, deterministic reconciliation.
**Implementation decisions:** multiple fixes were required:
- remove extra finalize rows,
- correct trace aggregation logic and keying,
- ensure trace ordering matches spec,
- aggregate per trace key when multiple families share the same substream.
**Implication:** Trace consistency was a real implementation risk and is now explicitly managed. This will affect audit surfaces and S9 PASS status. Any data assessment must confirm trace outputs align with the final trace accounting rules.

### 7) Eligibility handling for ZTP scope
**Design intent:** Eligibility should be derived from explicit eligibility rules/policies.
**Implementation decision:** S9 was modified to load the eligibility map using the correct schema anchor and to avoid wrongly marking “no foreign candidates” as ineligible.
**Implication:** S9 now depends on correct schema refs. If eligibility map ingestion fails, S9 can mis‑classify in/out‑of‑scope merchants. This is a key item to verify in the data outputs.

### 8) Count domain behavior when counts are inferred
**Design intent:** parity checks enforce consistency between counts and outputs.
**Implementation decision:** When `s3_integerised_counts` is absent, missing domain counts are treated as zero rather than error, but extra-domain entries still fail.
**Implication:** There is a built‑in tolerance for “implicit zero” counts depending on the counts authority. When we assess dataset parity, we must interpret missing domains accordingly.

### 9) Immutability guard for S9 bundles
**Design intent:** audit‑safe, write‑once bundles.
**Implementation decision:** added atomic publish guard: if a bundle exists and differs, fail closed. If identical, skip publish.
**Implication:** reruns against existing fingerprints should not overwrite. Data assessment must not expect multiple bundle variants per fingerprint.

### 10) Numeric self‑test alignment (math profile)
**Design intent:** deterministic numeric profile locked to runtime dependencies.
**Implementation decision:** updated math_profile manifest to align with numpy/scipy versions after downgrade.
**Implication:** The manifest fingerprint and sealed inputs include this profile; it affects reproducibility and may explain differences between older runs vs current outputs.

### 11) Deterministic utc_day and run receipt selection
**Design intent:** run partitions should be stable for a given run_id.
**Implementation decision:** utc_day derived from run_receipt.created_utc, not wall‑clock. Latest receipt selection is now stable (created_utc, not mtime).
**Implication:** Outputs are now stable across re‑runs on later dates, but older runs may still carry pre‑fix behavior. For this assessment run, it should be stable.

## Observations on Implementation Philosophy
- The implementation log shows **active reconciliation** of spec vs reality. Many fixes are consistency repairs (trace coverage, eligibility scoping, immutability, schema anchors).
- The design intent appears strict and audit‑driven; the implementation added explicit safety rails rather than loosening the spec.
- Several decisions were made to preserve deterministic outputs even under operational constraints (e.g., run-local staging order and write-once bundle rules).

## What This Means for the Dataset Assessment (next step)
When we compare design intent to actual data outputs for the given run, the following are the **most important cross‑checks** implied by the design/implementation decisions:

1) **Validation bundle location and immutability**
   - Confirm S9 publishes the bundle and `_passed.flag`, and that S0 does not emit its own bundle by default.

2) **Eligibility flags and ZTP scope**
   - Confirm `crossborder_eligibility_flags` exists and is used to define scope (not overwritten by “no candidates” logic).

3) **Trace logs consistency**
   - Check that trace outputs are consistent with “one row per event” and that S9 coverage logic would PASS.

4) **Manifest/parameter hash inputs**
   - Ensure the parameter/manifest inputs include the correct policy basenames, including any late‑added policy files (e.g., tile_weights).

5) **Sealed input inventory correctness**
   - Confirm sealed_inputs lists all external refs and parameter artifacts defined in S0 spec.

6) **Counts parity expectations**
   - For domains where counts are inferred from egress (rather than s3_integerised_counts), treat missing domains as zero counts per the implementation decision.

These are the areas most likely to reveal whether a mismatch is due to design ambiguity, implementation drift, or actual data generation issues.

---

If you want this reformatted as a formal design‑audit memo or want deeper tracing of specific states (e.g., S3 or S6), say so and I’ll expand it.
