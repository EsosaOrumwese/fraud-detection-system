# Guide: Derive `data_engine_interface.md` (Binding)
Goal: write the human-readable, black-box contract for platform components.

## A) What belongs here (and what must not)
### MUST include:
- Scope/non-scope (black box boundary)
- Identity tuple and determinism promise
- Immutability/sealing semantics at the boundary
- Output classes: streams, authority surfaces, gates
- Discovery rules (path templates + partition keys)
- Join semantics (canonical join keys; global vs fingerprint scoped)
- Gate rulebook (“no PASS → no read” + what “verification” means)
- Compatibility/versioning rules

### MUST NOT include:
- State-by-state algorithms
- How distributions/models are computed
- “Why” narratives beyond what is needed to use outputs safely

## B) How to harvest facts
For each segment:
- From expanded docs:
  - any explicit statements like:
    - “inter-country order is not encoded…”
    - “consumer must verify _passed.flag before read…”
    - “run_id is logs-only…”
- From dictionaries/registries:
  - which outputs are fingerprint-scoped vs parameter-scoped vs run-scoped

From implementation:
- confirm the gate hash law and index ordering
- confirm writer path templates
(Do not invent rules not stated in specs.)

## C) Assembly plan (structure)
Use this section structure (keep it stable):
1. Purpose & scope (Binding)
2. Definitions (Binding)
   - identity fields: parameter_hash, manifest_fingerprint, seed, scenario_id, run_id
3. Determinism and replay guarantees (Binding)
4. Sealing & immutability guarantees (Binding)
5. Output classes (Binding)
6. Discovery & addressing (Binding)
   - include canonical templates; require fingerprint token format
7. Join semantics (Binding)
   - list canonical join keys by domain (merchant/site/outlet/etc.)
8. Gate rulebook (Binding)
   - “no PASS → no read”
   - verification method categories (bundle hash, receipt hash, etc.)
9. Compatibility & versioning (Binding)
10. Appendix: segment-to-output quick index (Informative)

## D) Acceptance checks
- Every statement should be traceable to:
  - a contract line (dictionary/registry/schema), or
  - an expanded doc line, or
  - implementation parity check (only as “confirmed by code”)
- No segment internals or algorithm steps appear.
