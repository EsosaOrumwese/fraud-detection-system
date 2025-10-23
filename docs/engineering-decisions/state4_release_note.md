# State 4 (Segment 1B) Release Note — 2025-10-23

## Summary
- S4 allocation plan is now production-ready with deterministic largest-remainder integerisation, per-merchant conservation checks, and full PAT instrumentation.
- CLI integration covers `segment1b run` (S0→S4) and the new `validate-s4` entry point; scenario runner and automation wrappers surface the S4 artefacts.
- Run report schema expanded with PAT counters (`bytes_read_*`, CPU/wall time, RSS, open-file peak), conservation flag, and optional `merchant_summaries`.

## New Requirements
- Runtime dependency: `psutil (>=5.9.0,<6.0.0)` for PAT capture (`pyproject.toml`).
- Dataset dictionary additions: `s3_requirements`, `s4_alloc_plan`, `s3_run_report`, `s4_run_report` (contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml).
- Schema anchors: `schemas.1B.yaml#/plan/s3_requirements`, `#/plan/s4_alloc_plan`.

## Validation & Evidence
- Automated regression: `tests/engine/l1/seg_1B/test_s4_alloc_plan_scaffolding.py`, `tests/scenario_runner/test_segment1b.py`, `tests/engine/cli/test_segment1b_cli.py`.
- Sample evidence bundle: `docs/evidence/s4_sample_run/` (data + run report + determinism receipt) generated with the in-repo runner for governance review.
- Nightly automation (`scripts/run_segment1b.py`) now supports `validate` lists; see `config/runs/segment1b_nightly.yaml`.

## Follow-up Actions
- Submit the updated dictionary/schema artefacts and `psutil` dependency for governance approval.
- Share the sample evidence bundle and updated runbook (`docs/runbooks/s4_alloc_plan.md`) with downstream consumers before enabling S4 reads.
- Coordinate with automation owners to redeploy pipelines with the refreshed wrapper script and CLI commands.
