# Auditable Container Release Pipeline with Immutable Image Identity

## 1) Claim Statement

### Primary claim
I built and operated an auditable container release pipeline in which a CI workflow is the authoritative build lane, every release publishes immutable image identity (`tag` plus `digest`), and machine-readable provenance and verification gates enforce fail-closed behavior before a release is accepted.

### In-scope boundary
This claim covers:
- deterministic container build and publish flow from CI to registry,
- immutable release identity and promotion-safe referencing by digest,
- provenance artifacts that capture build inputs, release identity, and verification outcomes,
- fail-closed release checks that block progression when required evidence or validations are missing.

### Non-claim boundary
This claim does not assert:
- organization-wide production rollout governance beyond this release lane,
- complete software supply-chain attestation maturity (for example full signing/SBOM enforcement across all services),
- runtime incident-free operation of downstream services (that belongs to separate reliability and operations claims).

## 2) Outcome Target

### 2.1 Operational problem this release lane must solve
Container delivery usually fails in three practical ways:
- release identity is mutable or ambiguous (for example tag-only deployment),
- release evidence is incomplete (build happened but traceability is weak),
- checks fail but releases still advance due to weak enforcement.

The target outcome of this work is to remove those three failure classes from the delivery path used for platform runtime images.

### 2.2 Engineering outcome definition (what "success" means)
Success means the release lane behaves as a controlled system with explicit acceptance conditions, not as a best-effort script. For every accepted release:
- artifact identity is immutable and unambiguous,
- provenance is machine-readable and sufficient for audit and reproduction,
- failed or missing checks stop progression by default,
- accepted artifacts can be referenced and promoted safely without identity drift.

### 2.3 Measurable success criteria (all must be true)
The outcome is considered achieved only when every criterion below is satisfied for a release candidate:

1. Identity integrity
- The released image has both a human-usable label (`tag`) and an immutable content identifier (`digest`).
- The digest used for deployment or promotion matches the digest published by the build lane.
- No step in the release lane depends on mutable tag lookup as the only identity control.

2. Provenance completeness
- A machine-readable release record exists for the candidate.
- The record links at minimum: source revision, build invocation context, produced image identity, and gate outcomes.
- Provenance is produced by automation, not by manual retrospective notes.

3. Gate enforcement
- Required checks are explicit and executable.
- If any required check fails or required evidence is missing, release progression halts.
- "Warning-only" behavior is not allowed for required controls in this lane.

4. Reproducibility posture
- The release process is deterministic enough that identical inputs reproduce the same outcome class (accepted vs rejected) under the same gate set.
- Any intentional input change (code, dependency set, build configuration) is reflected in provenance and release identity.

5. Audit retrieval posture
- A reviewer can answer, without code archaeology: what was built, from which source state, by which automated lane, with which exact immutable artifact identity, and under which gate results.

### 2.4 Failure conditions (explicit non-success states)
The lane is treated as non-compliant for this claim if any of the following occur:
- release artifact is promoted by tag without digest lock,
- provenance artifact is absent, partial, or manually fabricated,
- required checks are bypassed or downgraded informally,
- build succeeds but identity/provenance cross-check fails,
- evidence exists but cannot be mapped to the released artifact deterministically.

### 2.5 Risk reduction objective (why this matters to a senior role)
This outcome directly reduces operational and hiring-relevant risk:
- rollback risk: immutable digest identity prevents "same tag, different image" ambiguity,
- incident response risk: provenance shortens triage because release facts are queryable,
- governance risk: fail-closed gates prevent silent drift in release hygiene,
- team scaling risk: release safety no longer depends on tribal memory.

### 2.6 Evidence expectation for this section
This section defines target outcomes; proof details are provided later in:
- controls/guardrails section (what enforces behavior),
- validation section (how checks were executed),
- results section (what passed in practice),
- proof hooks section (where anchor artifacts are located).

## 3) System Context

### 3.1 System purpose within the platform
This release lane exists to solve a platform-level control problem: runtime services must run artifacts that are traceable, immutable, and policy-validated. Without this lane, deployment quality depends on manual process discipline and cannot be audited reliably.

This system is therefore not "just CI." It is a release-control boundary between:
- source changes (code and build configuration),
- runtime artifact creation (container image),
- runtime execution eligibility (only validated, traceable artifacts should progress).

### 3.2 Main actors and ownership model
The lane is modeled as four actors with explicit ownership:

1. Source owner
- owns application code and build context.
- proposes candidate changes through version control.

2. Authoritative build orchestrator (CI workflow)
- performs reproducible build and publish steps.
- computes and emits immutable artifact identity.
- evaluates required checks and decides pass/fail progression.

3. Artifact registry
- stores built image artifacts.
- is the source of truth for published tag and digest mapping at release time.

4. Evidence and audit surface
- stores machine-readable release/provenance records and gate outcomes.
- provides queryable audit material for later review, incident response, or rollback decisions.

### 3.3 End-to-end flow (control flow and data flow)
At a high level, each release candidate follows this sequence:

1. Trigger
- a controlled CI invocation starts the release lane.
- ad hoc local builds are not treated as authoritative release outputs.

2. Build
- container image is built from the declared source state and build configuration.
- build process emits a candidate image artifact.

3. Publish
- candidate artifact is pushed to the registry.
- both tag and digest are collected as release identity outputs.

4. Verify identity and provenance
- build lane cross-checks identity surfaces (what was built vs what was published).
- machine-readable provenance payload is generated with source, build, artifact, and gate metadata.

5. Gate decision
- required checks are evaluated.
- if any check fails or required evidence is missing, progression stops.

6. Accept or reject
- accepted: candidate becomes an eligible runtime artifact reference.
- rejected: candidate is blocked; no "soft accept" path exists for required controls.

### 3.4 Trust boundaries and security boundaries
This release lane crosses several trust boundaries and therefore requires explicit control points:

1. Source-to-CI boundary
- CI must authenticate as an automation identity; build authority is not delegated to local developer machines.

2. CI-to-cloud boundary
- CI assumes a constrained cloud identity for registry operations.
- permissions are scoped to required actions; missing rights should fail early and loudly.

3. CI-to-registry boundary
- registry push and metadata retrieval are treated as controlled operations.
- identity outputs are read from authoritative publish results, not inferred heuristically.

4. CI-to-evidence boundary
- evidence write must be deterministic and machine-generated.
- manual after-the-fact edits are not considered authoritative proof.

### 3.5 Control philosophy in this context
The lane follows three control principles:

1. Single authoritative build lane
- one automated control path defines release truth.
- secondary/manual paths may exist for development, but they do not establish release authority.

2. Immutable identity over mutable labels
- tag is useful for operator readability.
- digest is mandatory for exact artifact identity and promotion safety.

3. Fail-closed progression
- missing or failing required checks block progression by default.
- acceptance requires positive evidence, not absence of visible errors.

### 3.6 Environmental constraints that shaped design
The design had to operate under practical constraints:
- cloud IAM and registry permissions can be partially configured and fail non-obviously,
- release reliability must hold without relying on human memory,
- evidence must be inspectable by non-authors (recruiter, auditor, incident responder),
- the same lane must support both speed (automation) and control (governed acceptance).

### 3.7 External interfaces and contracts (high level)
This claim depends on stable interfaces, not internal naming:
- CI trigger and execution contract,
- registry push/read contract,
- provenance artifact schema contract,
- release gate contract (required checks and required evidence),
- runtime consumption contract (reference immutable digest for controlled promotion/deploy).

### 3.8 Scope exclusions for context clarity
To prevent over-claiming, this context intentionally excludes:
- service runtime behavior after deployment,
- data-plane correctness of streaming and storage systems,
- organization-wide compliance program maturity,
- full deployment orchestration logic across every environment.

Those are separate claims with their own controls and proof surfaces.

## 4) Problem and Risk

### 4.1 Problem statement
Before this release lane was hardened, "build and publish a usable runtime image" was not a guaranteed property of the system. In practice, success depended on several hidden prerequisites:
- correct federated CI identity setup in cloud IAM,
- complete registry authorization scope for automation roles,
- packaging rules that actually included newly introduced runtime dependencies,
- consistent identity and evidence capture after publish.

The technical problem was therefore not "how to run a container build command."  
It was how to guarantee that a release candidate is both:
- operationally usable by runtime services, and
- auditable and immutable enough for safe promotion and rollback.

### 4.2 Observed failure classes (from real execution)
The failure modes were observed as a progression of real breakpoints, not theoretical risks:

1. Federated CI identity bootstrap failure
- CI execution failed before release actions because cloud-side OIDC identity provider/trust prerequisites were incomplete.
- Operational effect: no authoritative automated release was possible.

2. Registry authorization failure after identity fix
- Once CI identity worked, registry login/push still failed because required authorization scope was incomplete.
- Operational effect: pipeline could authenticate to cloud but still could not publish artifacts.

3. Packaging drift after dependency/runtime change
- A later image built and published successfully, but runtime import failed because a newly required dependency was omitted from curated image dependency selection.
- Operational effect: "build success" did not imply "runtime-usable artifact."

These three classes exposed a common truth: build execution alone is not a valid release acceptance signal.

### 4.3 Risk taxonomy (what could go wrong if untreated)
The untreated state created specific platform risks:

1. Release integrity risk
- Mutable or weakly verified identity can lead to "same label, different artifact" ambiguity.
- Consequence: unreliable rollback, unclear change attribution, and high incident friction.

2. Pipeline trust risk
- CI may appear configured but fail at real cloud boundaries (identity and authorization).
- Consequence: false confidence in delivery readiness and delayed release recovery.

3. Runtime viability risk
- Packaging drift can produce artifacts that publish successfully but fail at startup/runtime.
- Consequence: avoidable deployment failures and unnecessary debugging cycles.

4. Audit and governance risk
- If provenance and gate results are incomplete, teams cannot prove what was released and why it was accepted.
- Consequence: weak incident forensics and poor compliance posture.

5. Team-scale risk
- If correctness depends on operator memory or manual checking, release quality degrades as system complexity grows.
- Consequence: non-repeatable outcomes and brittle handovers.

### 4.4 Severity framing (senior engineering lens)
From an operating-platform perspective, these are high-severity control risks:
- they block release continuity,
- they increase blast radius during incidents,
- they reduce confidence in promotion and rollback decisions,
- they convert routine releases into investigator-led events.

This is why the solution had to be control-oriented (identity, provenance, fail-closed gates), not just "fix one build failure."

### 4.5 Constraints that made the problem non-trivial
The release path had to satisfy multiple constraints simultaneously:
- keep delivery automated (speed),
- enforce safety gates (control),
- preserve immutable artifact identity (reliability),
- produce machine-readable proof (auditability),
- avoid manual release exceptions becoming the norm (scalability of operations).

Any design that optimized only one of these dimensions would fail in production use.

### 4.6 Derived requirements (what Section 5 must solve)
From the failure evidence and risk model, the design requirements were:

1. CI must be the authoritative build/publish lane with explicit cloud trust setup.
2. Registry operations must be fully authorized for automation and fail fast when scope is missing.
3. Released artifacts must carry immutable identity and be consumed by digest-safe references.
4. Provenance must be machine-generated and bound to release identity.
5. Required checks must block acceptance when failing or missing (fail-closed).
6. "Build succeeded" must not be sufficient; runtime-viability and release-proof criteria must be part of acceptance.
