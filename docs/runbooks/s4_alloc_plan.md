# Segment 1B - S4 Allocation Plan Runbook

Updated: 2025-10-23

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

Control-plane evidence (outside the dataset partition): run report (`s4_run_report.json`) and determinism receipt `{partition_path, sha256_hex}` under `control/s4_alloc_plan/seed=...`.

---

## 4. Execution
Run S0->S4 via the Segment 1B CLI:

```bash
python -m engine.cli.segment1b run \n  --data-root /abs/path/to/root \n  --parameter-hash <parameter_hash> \n  --manifest-fingerprint <manifest_fingerprint> \n  --seed <seed>
```

Add `--skip-s0` if the S0 receipt already exists. Automation via `scripts/run_segment1b.py` now surfaces S4 artefacts in the JSON summary.

---

## 5. Validation
```bash
python -m engine.cli.segment1b validate-s4 \n  --data-root /abs/path/to/root \n  --parameter-hash <parameter_hash> \n  --manifest-fingerprint <manifest_fingerprint> \n  --seed <seed>
```

The validator recomputes allocations from S3 + S2 inputs, verifies schema/order, enforces FK/coverage, and checks the determinism receipt.

---

## 6. Testing
- Unit & integration: `python -m pytest tests/engine/l1/seg_1B/test_s4_alloc_plan_scaffolding.py`
- S3 compatibility: `python -m pytest tests/engine/l1/seg_1B/test_s3_requirements.py`
- Scenario/CLI wiring will be extended in the next phase when S4 is hooked into the orchestrator and CLI summaries.

---

## 7. Observability & PAT
- Run report records `rows_emitted`, `pairs_total`, `shortfall_total`, `ties_broken_total`, ingress versions, and the determinism receipt.
- Determinism receipts follow the S1/S2/S3 recipe (ASCII-lex file order -> SHA-256).
- PAT counters (RSS, open files, IO bytes) can be added as operational requirements evolve; current implementation logs shortfall/tie metrics for audit.

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
- Residue diagnostics/PAT expansion can be added to the run report as follow-up work.
- CLI/Scenario integration will be finalised alongside downstream states (S5+).

---

## 10. References
- Spec: `docs/model_spec/data-engine/specs/state-flow/1B/state.1B.s4.expanded.md`
- Contracts: `contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml`, `contracts/schemas/layer1/schemas.1B.yaml#/plan/s4_alloc_plan`
- Related runbooks: `docs/runbooks/s3_requirements.md`, `docs/runbooks/s2_tile_weights.md`
