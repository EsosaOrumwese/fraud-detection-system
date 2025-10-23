# Segment 1B · S4 Allocation Plan Runbook (Draft)

Updated: 2025‑10‑23  
Status: **Implementation pending** — use this runbook as the checklist for building and validating the state.

---

## 1. Scope
State 4 converts each S3 site requirement into per-tile integer allocations using S2’s fixed-decimal weights. It is deterministic (no RNG) and emits `s4_alloc_plan`, which sums to the S3 counts for every `(merchant_id, legal_country_iso)`.

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

## 3. Target Dataset
| ID | Path pattern | Keys | Columns |
|----|--------------|------|---------|
| `s4_alloc_plan` | `data/layer1/1B/s4_alloc_plan/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` | PK: `[merchant_id, legal_country_iso, tile_id]`<br>Sort: `[merchant_id, legal_country_iso, tile_id]` | `merchant_id`, `legal_country_iso`, `tile_id`, `n_sites_tile` (≥1) |

Control-plane evidence (outside partition):
- Run report (JSON) with S3 reference counts, rounding statistics, PAT counters.
- Determinism receipt `{partition_path, sha256_hex}`.

---

## 4. Implementation Checklist
1. **Package scaffolding**: `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/{l0,l1,l2,l3}` mirroring S3 style.
2. **Loaders (L0)**:
   - Receipt (`s0_gate_receipt_1B`), requirements, weights, tile index, ISO table.
   - Enforce path↔embed equality (`seed`, `manifest_fingerprint`, `parameter_hash`).
3. **Deterministic kernels (L1)**:
   - Join S3 requirements to eligible tiles (via `tile_index`).
   - Apply fixed-dp integerisation:
     * `base = floor(weight_fp * n_sites / 10^dp)`
     * Compute residues & shortfall.
     * Allocate remaining units via descending residue, tie-break on ascending numeric `tile_id`.
   - Drop zero allocations.
   - Validate FK: tile exists in index; ISO uppercase.
4. **Orchestration (L2)**:
   - Prepare run context (dictionary, governed parameters).
   - Materialise parquet partition atomically (stage → digest → move).
   - Emit run report + determinism receipt.
5. **Validator (L3)**:
   - Recompute allocations from inputs (S3 + S2) and match outputs.
   - Enforce schema, sort order, PK uniqueness.
   - Check sum-to-n, FK coverage, residue tie-break logic.
   - Verify determinism receipt (parquet digest).

---

## 5. Execution Plan
While S4 is under development:
- Integrate into `Segment1BOrchestrator` after S3; update CLI summaries once code lands.
- Accept new CLI switches if S4 needs additional knobs (currently none expected).
- Update `scripts/run_segment1b.py` result payload to surface S4 artefacts.

Once implemented:
```bash
python -m engine.cli.segment1b run \
  --data-root /abs/path/to/root \
  --parameter-hash <parameter_hash> \
  --manifest-fingerprint <manifest_fingerprint> \
  --seed <seed>
```
(S4 will execute as part of the chain.)

Validation (future):
```bash
python -m engine.cli.segment1b validate-s4 \
  --data-root /abs/path/to/root \
  --parameter-hash <parameter_hash> \
  --manifest-fingerprint <manifest_fingerprint> \
  --seed <seed>
```
(Add once validator exists.)

---

## 6. Testing Strategy (to be implemented)
- **Unit**: deterministic rounding, tie-breaks, residue handling, coverage failures.
- **Property-based**: random weights, ensure sum-to-n and monotonicity.
- **Integration**: replay S1→S4 with synthetic fixtures; ensure run reports record shortfall stats.
- **CLI / Scenario**: extend existing Segment 1B tests to cover S4 artefact emission.

---

## 7. Observability & PAT Expectations
- Capture counts (`rows_emitted`, `pairs_total`, `shortfall_total`, `ties_broken_total`).
- Record IO stats (`bytes_read_s3`, `bytes_read_weights`, `bytes_read_index`) and wall clock / CPU.
- Determinism receipts mirror S1/S2/S3 recipes (lex order, SHA‑256).
- Any PAT thresholds (RSS, open files, throughput) should follow §11 of the spec; add enforcement hooks in L2 before publish.

---

## 8. Failure Codes to Implement
| Code | Meaning |
|------|---------|
| `E401_REQUIREMENTS_MISSING` | No S3 rows for tile allocation. |
| `E402_WEIGHTS_MISSING` | Missing tile weight rows for required tiles. |
| `E403_SHORTFALL_MISMATCH` | Sum of allocations ≠ S3 count. |
| `E404_TIE_BREAK` | Tie-break applied incorrectly. |
| `E405_SCHEMA_INVALID` | Schema/columns/sort drift. |
| `E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL` | Existing partition differs. |
(Adapt codes to the taxonomy finalised during implementation.)

---

## 9. Open Questions / TODO
- Confirm PAT metrics required by ops for Phase 1B (are per-country summaries sufficient?).
- Decide whether to store residue diagnostics (optional evidence file).
- Validate if `tile_id` tie-break uses numeric order or lexicographic (spec says numeric — confirm during development).
- Plan CLI ergonomics: consider `--dry-run-s4` for debugging?

---

## 10. References
- Spec: `docs/model_spec/data-engine/specs/state-flow/1B/state.1B.s4.expanded.md`
- Contracts: `contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml`, `contracts/schemas/layer1/schemas.1B.yaml#/plan/s4_alloc_plan`
- Upstream runbooks: `docs/runbooks/s3_requirements.md`, `docs/runbooks/s2_tile_weights.md`

---

Capture implementation updates in this runbook as S4 progresses. Once the state ships, replace placeholder CLI/test instructions with concrete commands mirroring S3/S2 sections.
