# Segment 1B · S3 Requirements Runbook

Updated: 2025‑10‑23

---

## 1. Purpose
State 3 derives deterministic site counts per `(merchant_id, legal_country_iso)` by grouping the sealed `outlet_catalogue`. The state is RNG-free and writes `s3_requirements`, the source of truth for downstream allocation.

---

## 2. Prerequisites
- S0 gate has produced `s0_gate_receipt_1B` for the target `manifest_fingerprint`.
- Segment 1A artefacts (`outlet_catalogue`) are present under `seed={seed}/fingerprint={manifest_fingerprint}`.
- Segment 1B S1+S2 outputs exist for the chosen `parameter_hash` (`tile_index`, `tile_weights`).
- Dataset dictionary/schemas are synced (see `contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml`).

---

## 3. Inputs (dictionary IDs)
| Dataset | Notes |
|---------|-------|
| `s0_gate_receipt_1B` | Proves 1A PASS; no bundle re-hash is performed. |
| `outlet_catalogue` | Counts source (Segment 1A egress). |
| `tile_weights` | Used only for coverage assertions (no values read beyond country presence). |
| `iso3166_canonical_2024` | FK domain for `legal_country_iso`. |

All reads must resolve via the dataset dictionary helpers (`engine.layers.l1.seg_1B.shared.dictionary`); do **not** hard-code paths.

---

## 4. Outputs
- `s3_requirements` (Parquet) under `data/layer1/1B/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/`
  * PK & sort: `[merchant_id, legal_country_iso]`
  * Columns: `merchant_id`, `legal_country_iso`, `n_sites`
- Control-plane artefacts (outside the dataset partition):
  * Run report: `control/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s3_run_report.json`
  * Determinism receipt (embedded in the run report)

---

## 5. Execution
Run S0→S3 via the Segment 1B CLI:
```bash
python -m engine.cli.segment1b run \
  --data-root /abs/path/to/root \
  --parameter-hash <parameter_hash> \
  --manifest-fingerprint <manifest_fingerprint> \
  --seed <seed> \
  --dictionary /abs/path/to/layer1.1B.yaml
```

If S0 was already executed and the receipt is present, you may skip it:
```bash
python -m engine.cli.segment1b run \
  --data-root /abs/path/to/root \
  --parameter-hash <parameter_hash> \
  --manifest-fingerprint <manifest_fingerprint> \
  --seed <seed> \
  --skip-s0
```

Automation (nightly/smoke) can continue to use `scripts/run_segment1b.py`; the script now emits S3 artefact paths in the JSON summary.

---

## 6. Validation
Use the CLI validator to check a published partition:
```bash
python -m engine.cli.segment1b validate-s3 \
  --data-root /abs/path/to/root \
  --parameter-hash <parameter_hash> \
  --seed <seed> \
  --manifest-fingerprint <manifest_fingerprint> \
  --dictionary /abs/path/to/layer1.1B.yaml
```

The validator enforces:
- Schema & sort conformance
- Path↔embed equality (`seed`, `manifest_fingerprint`)
- FK domain (ISO-2 uppercase)
- Coverage against `tile_weights`
- Count match to `s3_requirements`
- Determinism receipt hash matches parquet bytes

---

## 7. Development & Tests
- Unit suite: `python -m pytest tests/engine/l1/seg_1B/test_s3_requirements.py`
  * Covers happy path, receipt absence, FK violations, coverage gaps, immutability guard, and determinism evidence.
- Scenario runner: `python -m pytest tests/scenario_runner/test_segment1b.py`
  * Verifies orchestrator wiring and optional S0 skip.
- CLI smoke: `python -m pytest tests/engine/cli/test_segment1b_cli.py`

---

## 8. Troubleshooting
| Failure code | Typical cause | Remedy |
|--------------|---------------|--------|
| `E301_NO_PASS_FLAG` | Missing or mismatched S0 receipt | Run S0 gate or confirm fingerprint. |
| `E302_FK_COUNTRY` | ISO code not present in canonical table | Inspect `legal_country_iso` for non-ISO values or casing issues. |
| `E303_MISSING_WEIGHTS` | Country missing in S2 `tile_weights` | Ensure S2 ran with the same `parameter_hash`. |
| `E304_ZERO_SITES_ROW` | Zero-count row attempted | Investigate source catalogue for anomalies. |
| `E306_TOKEN_MISMATCH` | Path tokens ≠ embedded values | Confirm manifest/seed columns match partition tokens. |
| `E313_NONDETERMINISTIC_OUTPUT` | Report or digest mismatch | Re-run S3; confirm no post-write mutations. |

For unexpected issues, inspect the run report JSON, determinism receipt, and unit tests before escalating.

---

## 9. Notes
- S3 is RNG-free, so reruns with identical sealed inputs must produce byte-identical partitions.
- Downstream stages (S4+) assume `s3_requirements` exists; keep identities consistent (`{seed, manifest_fingerprint, parameter_hash}`).
- Add new evidence fields only inside control-plane artefacts; the dataset schema is strictly governed by `schemas.1B.yaml#/plan/s3_requirements`.

