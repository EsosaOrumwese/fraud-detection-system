# S2 Tile Weights — Runbook

## CLI execution
```bash
python -m engine.cli.s2_tile_weights run     --data-root /path/to/run     --parameter-hash <hash>     --basis uniform     --dp 2     --dictionary /path/to/dictionary.yaml
```
Outputs:
- dataset: `data/layer1/1B/tile_weights/parameter_hash=<hash>/`
- control artefacts:
  - run report: `control/s2_tile_weights/parameter_hash=<hash>/s2_run_report.json`
  - per-country summaries: `.../normalisation_summaries.jsonl`

## Validation
```bash
python -m engine.cli.s2_tile_weights validate     --data-root /path/to/run     --parameter-hash <hash>     --dictionary /path/to/dictionary.yaml
```
Validation recomputes masses/quantisation, enforces FK & PAT receipts.

## PAT considerations
- Baselines measured via runner `measure_baselines`; ensure tile_index and raster reside locally for throughput measurement.
- `PatCounters` requires wall-clock, CPU, RSS and open-file metrics before materialisation.
- Validator reuses run report determinism receipt to assert byte identity.
