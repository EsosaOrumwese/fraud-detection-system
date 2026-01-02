# Guide: Derive `contracts/gate_receipt.schema.yaml` (Binding)
Goal: define a portable receipt format for PASS/FAIL that readers can verify.

## A) Important reality check
Some segments may use:
- a text `_passed.flag` with `sha256_hex = ...`
others may emit:
- JSON receipts + flag
others may have:
- bundle index hashes

The schema should support:
- `receipt_kind: "text_flag" | "json_receipt" | "bundle_flag"`
and then a `oneOf` payload.

## B) Minimal fields (common)
- gate_id
- status (PASS/FAIL)
- manifest_fingerprint (and/or other identity fields relevant to scope)
- produced_at
- digests:
  - digest_algorithm (sha256)
  - digest_hex
  - what_was_hashed (description)

## C) Derivation steps
1) From expanded docs: list all gate artifacts and formats
2) From implementation: confirm exact text format (line structure) and hashing inputs
3) Define schema with `oneOf` for each receipt kind
4) Keep the schema black-box: it specifies format, not how upstream computed it

## D) Acceptance checks
- Readers can implement verification using only gate map + receipt schema
- Compatible with existing `_passed.flag` formats in the repo
