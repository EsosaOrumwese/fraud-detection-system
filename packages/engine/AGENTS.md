# AGENTS.md - Data Engine Router (Layer-1 / Segment 1A / States S5-S9)
_As of 2025-10-14_

This router tells you what is binding, what to read first, and which parts of the engine are in play. It is not a design doc and prescribes no commands.

---

## 0) Scope (you are here)
- Package: `packages/engine`
- Active build: Layer-1 -> Segment 1A -> States **S5-S9** (States S0-S4 are sealed references).
- Other segments (1B...4B) are read-only unless they are explicitly unlocked.
- "XX" below refers to the relevant sub-segment directory under `docs/model_spec/data-engine/specs/`.

---

## 1) Reading order (strict)
Read these before editing code so you align with the frozen specs:

**A. Conceptual references (repo-wide, non-binding)**
- `docs/references/closed-world-enterprise-conceptual-design*.md`
- `docs/references/closed-world-synthetic-data-engine-with-realism*.md`

**B. Layer-1 narratives (orientation)**
- `docs/model_spec/data-engine/narrative/`

**C. State design for Segment XX (binding expanded specs)**
- `docs/model_spec/data-engine/specs/state-flow/XX/`
  - `overview*.md` -> orientation only
  - `s0*expanded*.md`, `s1*expanded*.md`, ... -> expanded state specs (S0-S4 sealed reference; S5-S9 active execution)
  - Historical L0/L1/L2/L3 pseudocode exists for **S0-S4 only**. For **S5-S9** derive the split directly from the expanded spec:
    - L0 = primitives/helpers
    - L1 = kernels
    - L2 = state orchestrator
    - L3 = validator

**D. Data-intake specs (structure & intent)**
- `docs/model_spec/data-engine/specs/data-intake/XX/`
  - `preview/*.md` -> intended dataset shape (orientation)
  - `data/*.md` -> ingestion approach (guidance)
- Treat `.csv`/`.json` samples as non-authoritative scaffolds.

**E. Contract specs (blueprints for `contracts/`)**
- `docs/model_spec/data-engine/specs/contracts/`

> Never promote narratives, previews, or samples to binding authority. Only the contracts and expanded specs govern code.

---

## 2) Test-yourself policy
- Reflect the root router: run deterministic tests (`python -m pytest`, state-specific CLIs) and document results.
- When touching validators or manifests, rerun the relevant quick-reference tests below.

---

## 3) Ignore list (keep these read-only)
- `docs/**/overview/**`
- Anything explicitly marked deprecated or combined

---

## 4) 1A essentials (read if you only read five things)
1. The expanded document for the active state (`docs/model_spec/data-engine/specs/state-flow/1A/s#*.expanded.md`).
2. Archived pseudocode bundles (L0-L3) for S0-S4 when you need historical context; infer L0-L3 yourself for S5-S9 as described above.
3. The contract spec for that state (`docs/model_spec/data-engine/specs/contracts/1A/...`).
4. The data-intake notes for 1A (`docs/model_spec/data-engine/specs/data-intake/1A/preview|data/*.md`).
5. The relevant quick-reference section below.

---

## 5) Quick references

### S2 - Domestic outlet counts
- Policy: `contracts/policies/l1/seg_1A/s2_validation_policy.yaml`
- CLI: `python -m engine.cli.s2_nb_outlets --validation-policy .`
- Validation artefacts: `validation/parameter_hash=*/run_id=*/s2/` and `validation_bundle/manifest_fingerprint=*/s2_nb_outlets/`
- Tests: `python -m pytest tests/engine/layers/l1/seg_1A/test_s2_nb_validator.py tests/engine/cli/test_s2_nb_cli.py`

### S3 - Cross-border universe
- Policy: `contracts/policies/l1/seg_1A/policy.s3.rule_ladder.yaml` (+ optional base-weight/threshold policies)
- Runner: `python -m engine.cli.segment1a --param policy.s3.rule_ladder.yaml=...`
- Validator: `engine.layers.l1.seg_1A.s3_crossborder_universe.l3.validator.validate_s3_outputs`
- Tests: `python -m pytest tests/engine/layers/l1/seg_1A/test_s3_runner.py`

(Extend this list as additional states come online.)

---

## House style (soft guidance)
- Prefer clarity and determinism over cleverness.
- Keep modules focused (L0 primitives, L1 kernels, L2 orchestration, L3 validation) and surface TODOs when the spec leaves gaps.

_This router remains command-free by design. Execution strategy, test harness, and internal folder improvements stay up to you while respecting the governing specs._
