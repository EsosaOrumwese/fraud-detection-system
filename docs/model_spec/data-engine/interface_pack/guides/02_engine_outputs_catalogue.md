# Guide: Derive `engine_outputs.catalogue.yaml` (Binding)
Goal: produce a machine-readable inventory of engine exposures to the platform.

## A) Source-of-truth rules
- Primary sources:
  1) dataset dictionaries (IDs, keys, schema refs)
  2) artefact registries (paths, provenance, partitions)
- Secondary (confirm):
  - expanded docs (semantics like “order authority”, “convenience only”)
  - implementation (actual writer paths)

If any mismatch occurs, log a DRIFT FINDING; do not silently “choose” a truth.

## B) Required fields per output entry
For each output_id:
- output_id (stable, snake_case)
- class: surface | stream
- scope: parameter | fingerprint | seed_fingerprint | seed_parameter_run | etc. (choose a small enum)
- owner_segment (provenance only)
- path_template (must reflect partition structure)
- partitions (explicit list)
- schema_ref (file + anchor)
- dictionary_ref (if you use dataset_dictionary IDs)
- primary_key (if table)
- join_keys (list; must be safe for downstream joins)
- read_requires_gates (list of gate_id)
- immutability (immutable_once_written: true/false)
- notes (ONLY for black-box constraints like “order not encoded”)

## C) Harvest procedure (segment-by-segment)
For segment <SEG>:
1) Parse artefact registry:
   - find all “emits” / egress / validation outputs
   - extract path templates and partitions
2) Parse dataset dictionary:
   - extract schema_ref, keys (PK/join)
3) Resolve schema refs:
   - confirm anchor exists
4) Classify scope:
   - parameter_hash-only → scope=parameter
   - fingerprint-only → scope=fingerprint
   - seed+fingerprint → scope=seed_fingerprint
   - seed+parameter_hash+run_id → scope=seed_parameter_run
5) Attach gates:
   - if dictionary says “consumer must verify gate X”, add read_requires_gates
   - if not explicit, leave empty (do not assume)

## D) Implementation confirmation
Search code for writer roots:
- locate the function that writes each dataset
- confirm it matches path_template tokens
If mismatch: DRIFT FINDING with:
- spec path_template
- code path_template
- recommended resolution (update spec or code)

## E) Automated checks (recommended)
Codex should implement a validator script that checks:
- unique output_id
- schema_ref resolves
- partitions align with template (every token appears)
- `fingerprint={manifest_fingerprint}` token usage is consistent
- every gate reference exists in engine_gates.map.yaml

## F) Acceptance criteria
- Catalogue covers all externally readable surfaces/streams
- No “internal scratch tables” unless explicitly consumer-visible
- No missing schema anchors
