# Phase 5 - Learning + Evolution / MLOps Plane Readiness

The goal of `Phase 5` is to prove that the managed learning corridor works on its own production criteria using only authoritative runtime truth and label truth from the already-promoted working platform.

This phase does not close because Databricks, SageMaker, and MLflow exist. It closes only when the platform can build the right datasets from authoritative runtime + label truth, train and evaluate on the right basis, materialize a complete candidate bundle, and govern promotion and rollback on the real managed corridor with full lineage and no shadow local path.

## What must be true for Phase 5 to close
`Phase 5` closes only when all of the following are true:

1. the managed learning corridor is pinned on live, readable surfaces and not on placeholder handles,
2. Databricks / OFS builds datasets from authoritative Phase 4 runtime and label truth only,
3. point-in-time correctness is preserved and leakage violations stay `0`,
4. SageMaker / MF trains and evaluates from the exact authoritative dataset basis being claimed,
5. MLflow / MPR records complete lineage from dataset -> train/eval -> candidate bundle -> active bundle truth,
6. promotion evidence is complete and rollback is real, bounded, and fail-closed,
7. no hidden local or script-only fallback is required for the managed learning corridor to look healthy.

## Active learning corridor in scope

### Managed learning surfaces
- `Databricks / OFS`
  - workspace: `https://dbc-d0b53c09-b6fa.cloud.databricks.com`
  - build job: `fraud-platform-dev-full-ofs-build-v0`
  - quality-gate job: `fraud-platform-dev-full-ofs-quality-v0`
  - compute policy: `serverless-jobs-only`
  - autoscale workers: `1-8`
- `SageMaker / MF`
  - execution role: `arn:aws:iam::230372904534:role/fraud-platform-dev-full-sagemaker-execution`
  - training job prefix: `fraud-platform-dev-full-mtrain`
  - batch-transform job prefix: `fraud-platform-dev-full-mbatch`
  - package group: `fraud-platform-dev-full-models`
  - online endpoint handle: `fraud-platform-dev-full-online-v0`
- `MLflow / MPR`
  - tracking URI path: `/fraud-platform/dev_full/mlflow/tracking_uri`

### Retained proving path
- learning runtime pack:
  - `config/platform/run_operate/packs/dev_full_learning_jobs.v0.yaml`
- readiness / lineage probes:
  - `scripts/dev_substrate/m10b_databricks_readiness.py`
  - `scripts/dev_substrate/m11b_sagemaker_readiness.py`
  - `scripts/dev_substrate/m11f_mlflow_lineage.py`
- bounded learning runner:
  - `scripts/dev_substrate/pr3_s4_learning_bound.py`

### Upstream truth allowed into this phase
- promoted working platform:
  - `Control + Ingress + RTDL + Case + Label`
- latest coupled closure scope:
  - `execution_id = phase4_case_label_coupled_20260312T003302Z`
  - `platform_run_id = platform_20260312T003302Z`
- authoritative runtime + label truth only

## Phase 5.A - Managed telemetry and boundary truth gate
Purpose:
- pin the live managed learning corridor and make the first bounded learning slice observable enough to diagnose honestly.

This subphase is green only when all of the following are true:
1. Databricks workspace, OFS jobs, SageMaker execution surface, and MLflow tracking surface are materially readable,
2. authoritative runtime + label basis can be identified for the active learning slice,
3. live logs, progress counters, boundary health, and fail-fast triggers are pinned for the managed corridor,
4. the bounded learning slice can be started without relying on hidden local fallback behavior.

## Phase 5.B - Bounded learning-plane proof
Purpose:
- prove dataset build, train/eval, lineage, promotion evidence, and rollback discipline on the managed learning corridor itself.

This subphase is green only when all of the following are true:
1. dataset build succeeds on authoritative basis and leakage remains `0`,
2. dataset manifest and fingerprint are complete and stable for the bounded slice,
3. train/eval succeed from the same dataset basis being claimed,
4. candidate bundle provenance is complete,
5. promotion evidence is complete,
6. rollback path exists, succeeds, and resolves active-bundle truth deterministically.

## Phase 5.C - Promotion judgment
Purpose:
- decide whether Learning + Evolution / MLOps is ready to be treated as a production-ready plane in isolation.

This subphase is green only when:
- the managed learning corridor meets its own production criteria,
- the evidence is explainable, attributable, and auditable,
- no hidden non-managed path is required to make the plane appear healthy.

## Current telemetry set entering Phase 5

### Live logs
- Databricks OFS build-job and quality-job outputs
- SageMaker training / evaluation job logs
- MLflow / MPR promotion and rollback events

### Live progress counters
- dataset row counts and build-stage progress
- train/eval job state and bounded duration
- candidate bundle creation and registry publication progress
- promotion / rollback state changes

### Live boundary health
- authoritative dataset basis present and readable
- label truth maturity available for the slice
- active-bundle resolution present and readable
- managed surfaces materially participating rather than only the local launcher

### Fail-fast triggers
- point-in-time or leakage violation detected
- train/eval basis not traceable to authoritative dataset truth
- promotion attempt without complete lineage
- rollback path unavailable or unreadable

### Minimal hardening artifacts
- one run manifest
- one learning / MLOps live summary
- one optional lineage snapshot

## Current impact metrics entering Phase 5

### Promoted upstream truth baseline
- working platform:
  - `Control + Ingress + RTDL + Case + Label`
- latest coupled closure scope:
  - `phase4_case_label_coupled_20260312T003302Z`
- closure truth from that run:
  - steady `3060.177777777778 eps`
  - burst `7118.0 eps`
  - recovery `3018.4333333333334 eps`
  - `4xx = 0`
  - `5xx = 0`
  - CaseTrigger / Case Management / Label Store participation green

### Current accepted starting posture
- `Phase 5.A` is now green on:
  - `execution_id = phase5_learning_mlops_20260312T012219Z`
- pinned managed-surface truth from that gate:
  - Databricks workspace user `eorumwese@gmail.com`
  - OFS build job id `736420749736071`
  - OFS quality job id `37768192213816`
  - SageMaker execution role trust valid
  - SageMaker model package group `fraud-platform-dev-full-models` present
  - MLflow tracking mode `databricks`
- the next honest task is now `Phase 5.B`, not more telemetry pinning.
  - run the smallest bounded managed-learning proof on top of the now-readable corridor.

## Phase 5 closure rule
`Phase 5` closes only when:

1. the managed learning corridor is live-pinned and observable,
2. bounded dataset build, train/eval, promotion, and rollback evidence is green,
3. lineage is complete from authoritative runtime + label truth to candidate bundle and active bundle truth,
4. no leakage or basis ambiguity remains open,
5. notes, logbook, plan state, and readiness graphs all tell the same truthful story.

If any one of those is false, `Phase 5` remains open.
