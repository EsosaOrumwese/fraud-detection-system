# Dev Min Extraction Pack (CV + Interview Anchors)

## 1) Curriculum Vitae (CV) Bullet Set
1. Built a secure continuous integration publish path using federated OpenID Connect role assumption and least-privilege registry permissions, closing real fail/fail/pass release blockers without static cloud keys.  
Proof: `docs/experience_lake/dev_min/secure_ci_oidc_and_least_privilege_registry_auth.report.md:686`

2. Implemented an auditable container release workflow that emits immutable image identity (`tag` plus `digest`) and machine-readable provenance as mandatory release evidence.  
Proof: `docs/experience_lake/dev_min/auditable_release_pipeline_immutable_images.report.md:869`

3. Enforced deterministic image build surfaces in a large monorepo (explicit include/exclude and bounded dependency selection), preventing uncontrolled build-context drift.  
Proof: `docs/experience_lake/dev_min/auditable_release_pipeline_immutable_images.report.md:906`

4. Designed replay-safe stream-ingestion controls with canonical dedupe identity and fail-closed collision handling, keeping transport behavior separate from durable truth ownership.  
Proof: `docs/experience_lake/dev_min/replay_safe_stream_ingestion_and_transport_truth_boundaries.report.md:1036`

5. Diagnosed a managed Kafka blocker where credentials were valid but ingestion still failed, then resolved transport-client compatibility by migrating adapter behavior and revalidating data-plane readback.  
Proof: `docs/experience_lake/dev_min/replay_safe_stream_ingestion_and_transport_truth_boundaries.report.md:1054`

6. Operationalized a full secret lifecycle (secure storage, rotation, mandatory redeploy for runtime freshness, teardown cleanup verification) with fail-closed blocker semantics.  
Proof: `docs/experience_lake/dev_min/managed_secret_lifecycle_and_runtime_credential_freshness.report.md:888`

7. Built an evidence-driven runtime assurance system where progression is gated by machine-readable verdicts, blocker taxonomy, and same-lane rerun closure.  
Proof: `docs/experience_lake/dev_min/evidence_driven_runtime_assurance_and_data_plane_readiness.report.md:953`

8. Implemented managed infrastructure controls with remote state locking, persistent-versus-ephemeral stack boundaries, and teardown-proof cost guardrails to support safe iterative staging toward larger environments.  
Proof: `docs/experience_lake/dev_min/managed_iac_state_locking_and_cost_guardrails.report.md:945`

## 2) Interview Challenge Anchors (Q -> A -> Proof)
1. `Q:` How do you prove CI security hardening was real and not theoretical?  
`A:` Show authentication-plane fail, authorization-plane fail, then closure after bounded remediations.  
Proof: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/21985402789`, `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/21985472266`, `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/21985500168`

2. `Q:` How do you prevent mutable image ambiguity in releases?  
`A:` Treat digest as required identity and emit provenance bundle in the same workflow lane.  
Proof: `docs/experience_lake/dev_min/auditable_release_pipeline_immutable_images.report.md:888`

3. `Q:` How do you handle build-context and packaging drift in a mono-repo?  
`A:` Enforce explicit include/exclude policy and dependency-surface controls as release gates.  
Proof: `docs/experience_lake/dev_min/auditable_release_pipeline_immutable_images.report.md:906`

4. `Q:` How do you prove ingestion is replay-safe under at-least-once delivery?  
`A:` Show canonical dedupe law plus fail-to-fix-to-pass incident chain and final certification verdict.  
Proof: `docs/experience_lake/dev_min/replay_safe_stream_ingestion_and_transport_truth_boundaries.report.md:934`

5. `Q:` How do you separate secret correctness from transport correctness during incident response?  
`A:` Close secret freshness first, then isolate remaining transport compatibility defect as separate control plane.  
Proof: `docs/experience_lake/dev_min/managed_secret_lifecycle_and_runtime_credential_freshness.report.md:782`

6. `Q:` How do you keep runtime progression from becoming operator opinion?  
`A:` Gate progression on machine-readable blocker arrays and same-lane rerun retirement before final verdict.  
Proof: `docs/experience_lake/dev_min/evidence_driven_runtime_assurance_and_data_plane_readiness.report.md:601`

7. `Q:` How do you control cloud spend while still iterating quickly?  
`A:` Use bounded demo->destroy lifecycle with fail-closed cost guardrails and teardown proof artifacts.  
Proof: `docs/experience_lake/dev_min/managed_iac_state_locking_and_cost_guardrails.report.md:876`

## 3) Usage Rules for Consistent Messaging
1. Use each incident once as a primary story; reference it elsewhere only as supporting context.
2. Pair every claim sentence with one proof hook.
3. Keep non-claims explicit to avoid overstatement.
4. Present dev_min as a controlled staging phase, not final architecture.
