# S2 Tile Weights – Runbook

## CLI execution
### One-off run
```bash
python -m engine.cli.s2_tile_weights run     --data-root /path/to/run     --parameter-hash <hash>     --basis uniform     --dp 2     --dictionary /path/to/dictionary.yaml
```
Outputs
- dataset: `data/layer1/1B/tile_weights/parameter_hash=<hash>/`
- control artefacts:
  - run report: `control/s2_tile_weights/parameter_hash=<hash>/s2_run_report.json`
  - per-country summaries: `.../normalisation_summaries.jsonl`

### Nightly batch
Populate `config/runs/segment1b_nightly.yaml` with the parameter hash, data root, dictionary, and gate artefacts for each nightly job. Then run:
```bash
python scripts/run_segment1b.py --config config/runs/segment1b_nightly.yaml     --results-json runs/segment1b_nightly_results.json
```
Review the JSON summaries for determinism receipts and artefact locations.

## Validation
```bash
python -m engine.cli.s2_tile_weights validate     --data-root /path/to/run     --parameter-hash <hash>     --dictionary /path/to/dictionary.yaml
```
Validation recomputes masses/quantisation, enforces FK & PAT receipts.

## PAT considerations
- Ensure `measure_baselines` can stream tile_index, ISO canonical, and population raster artefacts locally to record reference throughput.
- Record wall-clock, CPU seconds, RSS and open file counts before materialisation; `PatCounters.validate_envelope` enforces the §11 bounds.
- The validator reuses the run-report determinism receipt to confirm byte identity.

## PAT rehearsal
1. Stage full-sized `tile_index` and ingress raster artefacts under the target data root.
2. Execute the nightly runner (or the one-off CLI) with production parameters to materialise weights and capture baselines.
3. Capture `wall_clock_seconds_total`, `bytes_read_*`, baseline throughput values, and determinism receipts; re-run with alternate worker counts to confirm identical receipts and PAT ratios.
