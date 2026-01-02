# Guide: Derive `engine_gates.map.yaml` (Binding)
Goal: define operational gate verification rules and map gates to outputs.

## A) What is a gate here?
A gate is an artifact (or pair) that authorizes reads:
- Validation bundle root + `_passed.flag`
- Receipt JSON + `_passed.flag`
- Any explicit PASS receipt the engine emits

## B) Required fields per gate entry
- gate_id (stable, referenced by outputs)
- segment (provenance)
- scope (fingerprint / parameter / seed_parameter / etc.)
- passed_flag_path_template (or receipt templates)
- bundle_root_template (if bundle-based gate)
- schema_ref for the receipt/flag format
- verification_method (step list; unambiguous)
- authorizes_outputs (list of output_id)
- required_by_components (optional but useful: ingestion_gate, feature_plane, etc.)

## C) Harvest procedure
For each segment:
1) From expanded docs:
   - find the state that writes validation outputs (often S9)
   - copy the exact hashing law / ordering law
   - identify which outputs are “no PASS → no read”
2) From contracts:
   - confirm locations of validation bundle and `_passed.flag`
   - confirm receipt schemas
3) From implementation:
   - confirm exact ordering used (ASCII-lex by index.path, etc.)
   - confirm which files are excluded from digest

## D) Gate-to-output mapping rule
- If output is listed as requiring gate PASS in dictionary/spec, add it.
- If not stated, do not infer.
- Every output’s `read_requires_gates` must be satisfied by at least one gate entry.

## E) Acceptance checks
- No dangling authorizes_outputs
- No dangling output read_requires_gates
- verification_method is executable (a real component could implement it)
