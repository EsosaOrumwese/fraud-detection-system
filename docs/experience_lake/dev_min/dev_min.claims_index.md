# Dev Min Claims Index (Canonical Ownership + De-duplication)

## 1) Purpose
This document is the merge/synthesis control plane for the dev_min claim set.
It defines:
- what each claim owns,
- which incidents are primary versus supporting,
- how to avoid double-counting the same incident in outward assets.

Use this as the single source of truth before generating Curriculum Vitae (CV), interview answers, or portfolio summaries.

## 2) Canonical Claim Roster
1. `Claim A` - Auditable release pipeline with immutable identity and deterministic build surface  
Primary report: `docs/experience_lake/dev_min/auditable_release_pipeline_immutable_images.report.md`  
Primary signal: Release engineering, immutable artifacts, provenance, fail-closed packaging controls.

2. `Claim B` - Secure continuous integration federation and least-privilege registry authorization  
Primary report: `docs/experience_lake/dev_min/secure_ci_oidc_and_least_privilege_registry_auth.report.md`  
Primary signal: Cloud identity/security hardening under real pipeline failures.

3. `Claim C` - Managed infrastructure as code state locking, lifecycle partitioning, and cost guardrails  
Primary report: `docs/experience_lake/dev_min/managed_iac_state_locking_and_cost_guardrails.report.md`  
Primary signal: Infrastructure governance, safe teardown, bounded spend controls.

4. `Claim D` - Managed secret lifecycle and runtime credential freshness  
Primary report: `docs/experience_lake/dev_min/managed_secret_lifecycle_and_runtime_credential_freshness.report.md`  
Primary signal: Secret hygiene, rotation plus reload correctness, teardown cleanup.

5. `Claim E` - Replay-safe stream ingestion and transport versus durable truth boundaries  
Primary report: `docs/experience_lake/dev_min/replay_safe_stream_ingestion_and_transport_truth_boundaries.report.md`  
Primary signal: Distributed systems correctness under at-least-once and replay pressure.

6. `Claim F` - Evidence-driven runtime assurance and data-plane readiness  
Primary report: `docs/experience_lake/dev_min/evidence_driven_runtime_assurance_and_data_plane_readiness.report.md`  
Primary signal: Gate-driven operations, blocker taxonomy, fail-to-fix-to-pass adjudication.

## 3) Incident Ownership Map (Primary vs Supporting)
1. CI trust/provider missing -> registry permission missing -> publish closure (fail/fail/pass)  
Primary owner: `Claim B`  
Supporting use: `Claim A`  
Canonical anchors:
- `docs/experience_lake/dev_min/secure_ci_oidc_and_least_privilege_registry_auth.report.md:686`
- `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/21985402789`
- `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/21985472266`
- `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/21985500168`

2. Packaging drift (runtime import failure) resolved via immutable rebuild  
Primary owner: `Claim A`  
Supporting use: `Claim B`  
Canonical anchors:
- `docs/experience_lake/dev_min/auditable_release_pipeline_immutable_images.report.md:946`
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_min/platform.impl_actual.md` (`2026-02-20 10:11:00 +00:00`, `2026-02-20 10:24:00 +00:00`)
- `dev-min-m1-packaging` run `22207368985`

3. Credential plane closed but ingestion still failed until client compatibility correction  
Primary owner: `Claim E`  
Supporting use: `Claim D`, `Claim F`  
Canonical anchors:
- `docs/experience_lake/dev_min/replay_safe_stream_ingestion_and_transport_truth_boundaries.report.md:538`
- `src/fraud_detection/event_bus/kafka.py`
- `runs/dev_substrate/m6/20260215T124328Z/m6_c_ingest_ready_snapshot.json`

4. Secret lifecycle chain (materialization -> rotation/redeploy -> cleanup)  
Primary owner: `Claim D`  
Supporting use: `Claim C`  
Canonical anchors:
- `docs/experience_lake/dev_min/managed_secret_lifecycle_and_runtime_credential_freshness.report.md:888`
- `runs/dev_substrate/m2_e/20260213T141419Z/secret_surface_check.json`
- `runs/dev_substrate/m6/20260215T040527Z/m6_b_ig_readiness_snapshot.json`
- `runs/dev_substrate/m9/m9_20260219T155120Z/m9_f_secret_cleanup_snapshot.json`

5. Cost guardrail fail -> fix -> pass with scope uplift rerun  
Primary owner: `Claim C`  
Supporting use: `Claim F`  
Canonical anchors:
- `docs/experience_lake/dev_min/managed_iac_state_locking_and_cost_guardrails.report.md:945`
- `runs/dev_substrate/m9/m9_20260219T160439Z/m9_g_cost_guardrail_snapshot.json`
- `runs/dev_substrate/m9/m9_20260219T160549Z/m9_g_cost_guardrail_snapshot.json`
- `runs/dev_substrate/m9/m9_20260219T185951Z/m9_g_cost_guardrail_snapshot.json`
- `runs/dev_substrate/m9/m9_20260219T181800Z/teardown_proof.json`

6. Runtime assurance closure chain (readiness + evidence integrity + final verdict)  
Primary owner: `Claim F`  
Supporting use: `Claim E`  
Canonical anchors:
- `docs/experience_lake/dev_min/evidence_driven_runtime_assurance_and_data_plane_readiness.report.md:956`
- `runs/dev_substrate/m6/20260215T071807Z/m6_c_ingest_ready_snapshot.json`
- `runs/dev_substrate/m6/20260215T124328Z/m6_c_ingest_ready_snapshot.json`
- `runs/dev_substrate/m8/m8_20260219T082518Z/m8_c_input_readiness_snapshot.json`
- `runs/dev_substrate/m8/m8_20260219T082913Z/m8_c_input_readiness_snapshot.json`
- `runs/dev_substrate/m10/m10_20260222T081047Z/m10_j_certification_verdict_snapshot.json`

## 4) De-duplication Rules for Outward Assets
1. One incident gets one primary owner claim.
2. In other claims, reference it as a supporting boundary condition in one to two lines only.
3. Do not repeat the same run sequence as full proof in multiple bullets.
4. Use strongest proof chain once; reuse only the causal lesson elsewhere.
5. Keep non-claims visible so capability scope remains credible.

## 5) Recommended Narrative Order (Interview or Portfolio)
1. `Claim B` (secure CI auth and least-privilege)  
2. `Claim A` (immutable audited release pipeline)  
3. `Claim E` (distributed ingestion correctness)  
4. `Claim D` (secret lifecycle and runtime freshness)  
5. `Claim F` (runtime assurance and readiness adjudication)  
6. `Claim C` (infrastructure lifecycle and cost governance as staging discipline)

Why this order:
- it moves from secure delivery foundation -> runtime correctness -> operational governance,
- it avoids leading with cost controls as if they were the end-state objective.

## 6) Unified Scope Guardrails
1. Do not frame dev_min as final architecture.
2. Frame dev_min as control-hardening and evidence-hardening stage for larger managed environments.
3. Keep technical language external-facing; use repository identifiers only as proof hooks.
