# Segment 1A Test Plan (S0-S3)

## Automated Coverage
- `python -m pytest tests/engine/layers/l1/seg_1A/test_s2_nb_validator.py` - NB replay, envelope integrity, corridor guardrails (breach/missing-policy paths).
- `python -m pytest tests/engine/cli/test_s2_nb_cli.py` - CLI happy path: RNG logs, catalogue emission, validation artefacts.
- `python -m pytest tests/engine/layers/l1/seg_1A/test_s3_runner.py` - S3 deterministic context → runner → candidate set validator.

## Latest Execution (2025-10-10)
- `python -m pytest tests/engine/cli/test_s2_nb_cli.py tests/engine/layers/l1/seg_1A/test_s2_nb_validator.py tests/engine/layers/l1/seg_1A/test_s3_runner.py`

## Next Additions
- Extend CLI coverage once S3 validator wiring integrates with end-to-end scenario runner.
