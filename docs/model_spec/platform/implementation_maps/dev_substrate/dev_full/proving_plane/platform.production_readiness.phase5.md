# Phase 5 - Learning + Evolution / MLOps Plane Readiness

The goal of `Phase 5` is to prove that the `dev_full` learning corridor can take authoritative runtime and label truth from the already-promoted working platform, admit only semantically valid worlds and datasets, build the right offline basis, train and evaluate on the right basis, and govern candidate/active bundle truth on the real managed surfaces without hidden local shortcuts.

This phase does not close because Databricks, SageMaker, and MLflow exist. It closes only when the learning corridor is shown to be:

- semantically admissible,
- operationally credible,
- lineage-complete,
- rollback-capable,
- and materially useful for model evolution rather than just artifact production.

## Why this phase exists in the full plan

Earlier phases proved that the platform can:

- admit production-shaped traffic,
- make runtime decisions,
- materialize case truth,
- and commit authoritative labels.

`Phase 5` exists because that is still not enough for a production-ready ML platform. The platform must also prove that:

- the data entering learning is the right data,
- the labels are the right supervision,
- the features are time-safe and leakage-safe,
- the model/eval story is grounded in the actual data,
- and the governed active-bundle truth can be explained and rolled back.

So this phase is where `100% Platform` and `100% MLOps` must be carried together.

## What must be true for the phase goal to be genuinely accomplished

`Phase 5` is only genuinely accomplished when all of the following are true:

1. the live managed learning surfaces are pinned and observable,
2. learning basis admission is governed by the interface pack and `6B.S5` world-gate truth,
3. current runtime + label truth can be turned into an offline dataset basis without time or supervision corruption,
4. train/eval can be shown to run on the same bounded basis being claimed,
5. cohort / regime / label-family visibility is sufficient to judge model usefulness rather than just training success,
6. candidate bundle truth is complete and attributable,
7. promotion and rollback truth are readable, deterministic, and governed,
8. no hidden local worker path is required to make the corridor look healthy.

If any one of those is false, the phase is not closed.

## Components, paths, and cross-plane relationships that contribute to that goal

### Upstream working-platform basis
- promoted working platform:
  - `Control + Ingress + RTDL + Case + Label`
- current authoritative source scope:
  - `execution_id = phase4_case_label_coupled_20260312T003302Z`
  - `platform_run_id = platform_20260312T003302Z`

### Data-semantic authorities allowed for this phase
- interface contract:
  - `docs/model_spec/data-engine/interface_pack/data_engine_interface.md`
- engine gate map:
  - `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml`
- engine output catalogue:
  - `docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`
- semantic build/state references:
  - `docs/model_spec/data-engine/implementation_maps/segment_5B.build_plan.md`
  - `docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s5.expanded.md`
  - `docs/model_spec/data-engine/implementation_maps/segment_6B.build_plan.md`
  - `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s5.expanded.md`

### Managed learning corridor in scope
- `Databricks / OFS`
  - workspace: `https://dbc-d0b53c09-b6fa.cloud.databricks.com`
  - build job: `fraud-platform-dev-full-ofs-build-v0`
  - quality job: `fraud-platform-dev-full-ofs-quality-v0`
  - compute policy: `serverless-jobs-only`
- `SageMaker / MF`
  - execution role: `arn:aws:iam::230372904534:role/fraud-platform-dev-full-sagemaker-execution`
  - training prefix: `fraud-platform-dev-full-mtrain`
  - batch prefix: `fraud-platform-dev-full-mbatch`
  - model package group: `fraud-platform-dev-full-models`
  - serving handle: `fraud-platform-dev-full-online-v0`
- `MLflow / MPR`
  - tracking mode / URI path resolved through Databricks-backed tracking

### Critical cross-plane paths that must be understood inside this phase
- runtime archive truth -> offline dataset basis
- label truth -> supervision basis
- admitted world -> offline build -> train/eval -> candidate bundle
- candidate bundle -> promotion / rollback governance truth
- active-bundle truth -> later runtime resolution

## Real subphases derived from the actual work

The previous rushed closeout treated Learning too much like one bounded green receipt. That is not enough. The real work splits into the following subphases.

## Phase 5.A - Semantic admission and telemetry gate
Purpose:
- pin the live learning corridor and prove that the candidate current learning basis is observable and admissible before any bounded learning proof is accepted.

This subphase is green only when all of the following are true:
1. Databricks, SageMaker, and MLflow surfaces are materially readable,
2. the current source scope is pinned to authoritative runtime + label truth,
3. the current world is admitted only through interface-pack-authorized outputs,
4. `6B.S5` gate truth is readable for the same world being claimed,
5. live logs, progress counters, boundary health, and fail-fast triggers are pinned for the active learning corridor.

Telemetry burden:
- live logs:
  - Databricks job output
  - SageMaker train/eval logs
  - MLflow / promotion / rollback event surfaces
- live counters:
  - admitted world count
  - rejected world count by reason
  - label coverage and maturity counters
  - dataset build stage counters
- live boundary health:
  - correct `platform_run_id` / source scope present
  - intended outputs resolve only through allowed interface-pack surfaces
  - `6B.S5` gate truth materially readable
- fail-fast triggers:
  - any missing gate surface
  - any ungoverned output basis
  - any unreadable managed surface required for the next bounded slice

Current status:
- exploratory probes have already shown that the managed surfaces and current semantic basis are materially reachable,
- but that telemetry pinning must now be treated as a real subphase entry condition rather than closure evidence by itself.

## Phase 5.B - OFS dataset-basis proof
Purpose:
- prove that the offline dataset basis is built from the right admitted truth and that it remains point-in-time-correct, leakage-safe, and supervision-usable.

This subphase is green only when all of the following are true:
1. only interface-pack-authorized outputs are admitted into the bounded learning basis,
2. the current world passes the declared `6B.S5` admission posture for learning use,
3. label as-of and maturity rules are enforced,
4. supervision coverage is materially usable for the bounded slice,
5. offline feature admissibility is explicit and future-derived leakage remains `0`,
6. dataset manifest, fingerprint, and lineage are complete and readable.

Primary questions:
- are we learning from the right world?
- are we learning from the right labels?
- are we building features from allowed offline surfaces only?
- do the bounded datasets preserve meaningful fraud / legit / case-linked signal rather than just row count?

Focus metrics:
- authoritative-world admission compliance
- unauthorized basis count
- point-in-time correctness violations
- future leakage violations
- label maturity / as-of violations
- supervision coverage by label family / cohort
- dataset manifest completeness

## Phase 5.C - MF train/eval proof
Purpose:
- prove that bounded training and evaluation run on the right dataset basis and produce interpretable evidence rather than mere job completion.

This subphase is green only when all of the following are true:
1. train/eval runs from the same dataset basis being claimed,
2. training and evaluation complete successfully on the managed corridor,
3. cohort / regime / label-family visibility is readable enough to judge model usefulness,
4. the selected model/eval story is interpretable against the admitted data rather than tooling convenience,
5. candidate bundle completeness and provenance are readable.

Primary questions:
- did train/eval use the exact admitted basis?
- are the eval outputs meaningful on important cohorts and regimes?
- can we justify the model/eval result in terms of the underlying data?

Focus metrics:
- training success / duration
- evaluation success / duration
- reproducibility / basis consistency
- bounded subgroup / regime visibility
- candidate bundle completeness

## Phase 5.D - MPR promotion / rollback / active-truth proof
Purpose:
- prove the governance corridor around candidate and active bundle truth on the managed path.

This subphase is green only when all of the following are true:
1. promotion evidence is complete,
2. rollback evidence is complete and bounded,
3. active bundle truth resolves deterministically,
4. no hidden local registry shortcut is needed,
5. candidate, promoted, and rollback truths remain attributable to the same learning evidence chain.

Focus metrics:
- promotion evidence completeness
- rollback success rate
- rollback RTO / RPO
- active-bundle truth determinism

## Phase 5.E - Plane judgment
Purpose:
- decide whether Learning + Evolution / MLOps is honestly plane-ready.

This subphase is green only when:
- the earlier subphases are green,
- the evidence is explainable, attributable, and auditable,
- no major semantic ambiguity remains open,
- the learning corridor is not being made to look healthy by hidden local execution or weak proof scope.

## Current known starting facts entering the rebuilt phase

These are starting facts only. They are not closure evidence.

### Current authoritative source scope
- `execution_id = phase4_case_label_coupled_20260312T003302Z`
- `platform_run_id = platform_20260312T003302Z`
- the current world carries:
  - manifest fingerprint `76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460`
  - intended outputs:
    - `s2_event_stream_baseline_6B`
    - `s3_event_stream_with_fraud_6B`

### Current semantic admission candidate
- the current world has readable `6B` validation artefacts
- prior exploratory reads showed:
  - `_passed.flag` present
  - `s5_validation_report_6B.json` readable
  - required machine-gate rails visible and green

### Current managed surface pinning candidate
- prior exploratory probes showed:
  - Databricks workspace readable
  - OFS build / quality jobs pinned
  - SageMaker execution role and model package group readable
  - MLflow tracking mode resolved through Databricks

### Important caution on prior exploratory receipts
- recent exploratory receipts and scripts may still be useful for narrowing and reuse,
- but they are not to be treated as final `Phase 5` closure authority unless and until the rebuilt subphase structure above is honestly satisfied.

### Current execution-path constraint already visible
- retained OFS execution still has a direct Databricks API path and can support a CLI-first managed proof
- retained MF train/eval and retained MPR promotion still default to GitHub workflow dispatch
- that means the rebuilt phase should move first on:
  - semantic admission,
  - dataset-basis proof,
  - and only then decide whether train/eval and promotion/rollback are to be justified on workflow dispatch or repinned onto a more direct managed path

## Current immediate execution order

1. repin `Phase 5.A` as a true semantic admission + telemetry gate,
2. decide the smallest honest `Phase 5.B` dataset-basis proof,
3. run that bounded proof with fail-fast telemetry,
4. make an explicit method judgment on the current `5.C` / `5.D` workflow dependence,
5. only after that judgment move deeper into train/eval and promotion / rollback proof.

## Phase closure rule

`Phase 5` closes only when:

1. semantic admission is governed and readable,
2. dataset-basis proof is green,
3. train/eval proof is green,
4. promotion / rollback / active-truth proof is green,
5. the full learning-plane story is explainable, attributable, and auditable,
6. notes, logbook, plan state, and readiness graphs all tell the same truthful story.

If any one of those is false, `Phase 5` remains open.
