# AGENTS.md - Data Engine Router (Layer-1 / Segment 1B)
_As of 2025-10-17_

This router tells you what is binding, what to read first, and which parts of the engine are in play. Segment 1A (S0-S9) is online and sealed—treat it as read-only unless a migration is explicitly authorised. Segment 1B is the active build.

---

## 0) Scope (you are here)
- Package: `packages/engine`
- Active build: Layer-1 → Segment **1B** → States **S0-S9**
- Sealed references: Segment 1A S0-S9 (authority surfaces for 1B inputs)
- Other segments (2A...4B) remain locked until explicitly opened.

---

## 1) Reading order (strict)
Read these in order before touching code so you align with the frozen specs.

**A. Conceptual references (repo-wide, non-binding)**
- `docs/references/closed-world-enterprise-conceptual-design*.md`
- `docs/references/closed-world-synthetic-data-engine-with-realism*.md`

**B. Layer-1 narratives (orientation)**
- `docs/model_spec/data-engine/narrative/`

**C. Segment 1B state design (binding)**
- `docs/model_spec/data-engine/specs/state-flow/1B/state-flow-overview.1B.md`
- `docs/model_spec/data-engine/specs/state-flow/1B/s#*.expanded.md`
  - No archived pseudocode—derive L0/L1/L2/L3 from the expanded spec.

**D. Data-intake specs (structure & intent)**
- `docs/model_spec/data-engine/specs/data-intake/1B/preview|data/*.md` (when unlocked)

**E. Contract specs (blueprints for `contracts/`)**
- `docs/model_spec/data-engine/specs/contracts/1B/` (authoritative once published)

> Never promote narratives, previews, or samples to binding authority. Only the expanded specs and contract documents govern code.

---

## 2) Test-yourself policy
- Run targeted pytest jobs (`python -m pytest ...`) for the state you modify.
- When adding RNG or egress logic, layer in regression cases that exercise both happy-path and gate-fail scenarios (mirror the Segment 1A test harness).
- Document results when handing work off (logbook or PR notes).

---

## 3) Ignore list (keep these read-only)
- `docs/**/overview/**`
- Anything explicitly marked deprecated or combined
- Segment 1A code paths unless a migration is authorised

---

## 4) Segment 1A references (sealed authority)
1. Expanded specs (`docs/model_spec/data-engine/specs/state-flow/1A/s#*.expanded.md`)
2. Contract specs (`docs/model_spec/data-engine/specs/contracts/1A/`)
3. Data intake (`docs/model_spec/data-engine/specs/data-intake/1A/preview|data/*.md`)
4. Validation bundles (`validation_bundle/manifest_fingerprint=*/...`)
5. Tests: `python -m pytest tests/contracts/test_seg_1A_dictionary_schemas.py tests/engine/cli/test_segment1a_cli.py tests/engine/layers/l1/seg_1A`

---

## 5) Segment 1B quick references (initial)
- **State overview:** `docs/model_spec/data-engine/specs/state-flow/1B/state-flow-overview.1B.md`
- **State flow short labels:**
  - S0 Gate in (verify 1A `_passed.flag`, load outlet catalogue)
  - S1 Country tiling (eligible raster/polygon grid)
  - S2 Tile priors (deterministic weights)
  - S3 Site counts (derive `N_i` per merchant/country)
  - S4 Integerise shares (largest remainder / deterministic policy)
  - S5 Cell selection (RNG: `raster_pick_cell`)
  - S6 Point jitter (RNG: within-cell jitter, bounded resample)
  - S7 Site synthesis (attributes, 1:1 parity with 1A)
  - S8 Egress (`site_locations` partitioned by `[seed, fingerprint]`)
  - S9 Validation bundle (`validation_bundle_1B/...`, `_passed.flag`)
- **RNG envelope:** reuse the 1A Philox/open-interval contract (`engine.layers.l1.seg_1A.s9_validation` is the reference implementation).
- **Validation hash rule:** `_passed.flag` remains `sha256_hex = <digest>` over bundle files in ASCII-lexicographic order (same as 1A).

Extend this section with concrete CLIs, policy paths, and test commands as you implement each state.

---

## House style (soft guidance)
- Prefer clarity and determinism over cleverness.
- Preserve the L0/L1/L2/L3 separation inside each state package.
- Surface TODOs or questions when the spec leaves gaps; do not improvise contracts.
- Keep logging informative—mirror the Segment 1A CLI/orchestrator patterns so smoke tests stay readable.

_This router remains command-free by design. Execution strategy, test harness, and internal folder improvements stay up to you while respecting the governing specs._

