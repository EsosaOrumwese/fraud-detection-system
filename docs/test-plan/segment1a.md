# Segment 1A Test Plan (S0–S2)

## Automated Coverage
- `python -m pytest tests/engine/layers/l1/seg_1A/test_s2_nb_validator.py` – NB replay, envelope integrity, corridor guardrails (breach/missing-policy paths).
- `python -m pytest tests/engine/cli/test_s2_nb_cli.py` – CLI happy path: RNG logs, catalogue emission, validation artefacts.

## Latest Execution (2025-10-10)
- ✅ `python -m pytest tests/engine/cli/test_s2_nb_cli.py tests/engine/layers/l1/seg_1A/test_s2_nb_validator.py`

## Next Additions
- S3 hand-off fixture using `S2StateContext.counts_by_merchant()` once cross-border state opens.
