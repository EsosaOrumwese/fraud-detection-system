# Segment 1B - S4 Allocation Plan Runbook

Updated: 2025-10-23 (Phase 7 refresh)

---

## 1. Scope
State 4 converts each S3 site requirement into per-tile integer allocations using S2's fixed-decimal weights. It is deterministic (no RNG) and emits `s4_alloc_plan`, which sums to the S3 counts for every `(merchant_id, legal_country_iso)`.

---

## 2. Prerequisites
| Artefact | Notes |
|----------|-------|
| `s0_gate_receipt_1B` | Fingerprint-scoped receipt proving the 1A PASS. |
| `s3_requirements` | Counts source (`seed`, `manifest_fingerprint`, `parameter_hash`). |
| `tile_weights` | Fixed-dp weights per tile (`parameter_hash`). |
| `tile_index` | Eligible tile universe (`parameter_hash`). |
| `iso3166_canonical_2024` | FK domain for `legal_country_iso`. |

All IO resolves via `engine.layers.l1.seg_1B.shared.dictionary`.

---

## 3. Dataset Contract
| ID | Path pattern | Keys | Columns |
|----|--------------|------|---------|
| `s4_alloc_plan` | `data/layer1/1B/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` | PK: `[merchant_id, legal_country_iso, tile_id]`<br>Sort: `[merchant_id, legal_country_iso, tile_id]` | `merchant_id`, `legal_country_iso`, `tile_id`, `n_sites_tile` (>=1) |

Control-plane evidence (dictionary-resolved, outside the dataset partition):
- `control/s4_alloc_plan/seed=.../fingerprint=.../parameter_hash=.../s4_run_report.json`
- Determinism receipt embedded in the run report (`determinism_receipt`) computed per spec §10.4.

---

## 4. Execution
Run S0→S4 via the Segment 1B CLI (S4 artefacts appear in the JSON summary):

```bash
python -m engine.cli.segment1b run \
  --data-root /abs/path/to/root \
  --parameter-hash <parameter_hash> \
  --manifest-fingerprint <manifest_fingerprint> \
  --seed <seed>
```

Add `--skip-s0` if the S0 receipt already exists. Automation via `scripts/run_segment1b.py` should pass the same arguments; the orchestrator now materialises S4 immediately after S3.

---

## 5. Validation
```bash
python -m engine.cli.segment1b validate-s4 \
  --data-root /abs/path/to/root \
  --parameter-hash <parameter_hash> \
  --manifest-fingerprint <manifest_fingerprint> \
  --seed <seed>
```

Optional: `--dictionary <path>` to pin a custom dictionary.  
The validator recomputes allocations from S3+S2 inputs, verifies schema/order, enforces FK/coverage, checks run-report counters, and reconciles the determinism receipt digest.

---

## 6. Testing
- Unit & integration: `python -m pytest tests/engine/l1/seg_1B/test_s4_alloc_plan_scaffolding.py`
- Scenario runner: `python -m pytest tests/scenario_runner/test_segment1b.py`
- CLI smoke (run + validate-s4): `python -m pytest tests/engine/cli/test_segment1b_cli.py`
- Upstream S3 invariants: `python -m pytest tests/engine/l1/seg_1B/test_s3_requirements.py`

---

## 7. Observability & PAT
- Run report fields (presence enforced by validator):
  - Lineage + aggregation: `rows_emitted`, `merchants_total`, `pairs_total`, `shortfall_total`, `ties_broken_total`, `alloc_sum_equals_requirements`
  - Determinism & lineage: `determinism_receipt`, `ingress_versions`
- PAT counters: `bytes_read_s3`, `bytes_read_weights`, `bytes_read_index`, `wall_clock_seconds_total`, `cpu_seconds_total`, `workers_used`, `max_worker_rss_bytes`, `open_files_peak`
- Optional auditor aids: `merchant_summaries` (per-merchant countries / total allocations / pair counts)
- Determinism receipts follow the S1/S2/S3 recipe (ASCII-lex order of files → SHA-256 digest).  
- rss / handle counts are collected via `psutil`; values are monotonic snapshots at materialisation time.
- Sample evidence bundle illustrating these counters lives at `docs/evidence/s4_sample_run/`.

---

## 8. Failure Codes
| Code | Meaning |
|------|---------|
| `E401_REQUIREMENTS_MISSING` | `s3_requirements` partition missing. |
| `E402_WEIGHTS_MISSING` | Tile weights absent or inconsistent for a required country/dp. |
| `E403_SHORTFALL_MISMATCH` | Allocations do not sum to the S3 requirement. |
| `E404_TIE_BREAK` | Reserved for deterministic tie-break violations. |
| `E405_SCHEMA_INVALID` | Schema or column set drift. |
| `E406_SORT_INVALID` | Sort order not `[merchant_id, legal_country_iso, tile_id]`. |
| `E407_PK_DUPLICATE` | Duplicate `(merchant_id, legal_country_iso, tile_id)` rows. |
| `E408_COVERAGE_MISSING` | Tile coverage mismatch (weights/index/ISO). |
| `E409_DETERMINISM` | Run report or digest mismatch. |
| `E411_IMMUTABLE_CONFLICT` | Attempt to overwrite an existing partition with different bytes. |

---

## 9. Notes
- `shortfall_total` sums how many +1 adjustments were applied; `ties_broken_total` counts increments where residues collided.
- `merchant_summaries` are emitted when the partition is non-empty and give auditors a per-merchant conservation snapshot.
- `psutil` is required for PAT capture; install via project dependencies before running S4 environments.

---

## 10. Governance & Release
- New dictionary entries (`s3_requirements`, `s4_alloc_plan`, `s3_run_report`, `s4_run_report`) and schema anchors are staged under `contracts/`; raise a governance review ticket before promoting to shared registry.
- Capture sample evidence (run report + determinism receipt) and attach to the release bundle for consumer sign-off.
- Update downstream automation and documentation to reference the new CLI `validate-s4`.

---

## 11. References
- Spec: `docs/model_spec/data-engine/specs/state-flow/1B/state.1B.s4.expanded.md`
- Contracts: `contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml`, `contracts/schemas/layer1/schemas.1B.yaml#/plan/s4_alloc_plan`
- Related runbooks: `docs/runbooks/s3_requirements.md`, `docs/runbooks/s2_tile_weights.md`
