# By‑Ref Validation Checklist (v0)
_As of 2026-01-24_

This checklist pins the **minimum validation steps** for any component that consumes or publishes **by‑ref artifacts**. It is a Phase‑1.2 deliverable and applies platform‑wide.

---

## A) Output locator validation (engine_output_locator)

**Authority:**  
`docs/model_spec/data-engine/interface_pack/contracts/engine_output_locator.schema.yaml`

**Checks (fail‑closed):**
1. **Schema validity** — locator conforms to the contract (required fields present; no extra fields).
2. **Path template match** — locator `path` matches the catalogue template for its `output_id`:
   `docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`.
3. **Pin consistency** — locator pins match the run context:
   - `manifest_fingerprint` must match the run’s manifest.
   - `parameter_hash`, `seed`, `scenario_id`, `run_id` must match when present and expected by the output’s scope.
4. **Token order** — partition tokens appear in canonical order:
   `seed -> parameter_hash -> manifest_fingerprint -> scenario_id -> run_id -> utc_day`.

## B) Digest posture (content integrity)

**Checks (fail‑closed):**
1. **Instance‑scoped outputs require content digest**  
   If the output scope includes any of `seed`, `scenario_id`, `parameter_hash`, or `run_id`, then:
   - `engine_output_locator.content_digest` **must** be present.
2. **Digest verification**  
   When a digest is present, recompute and compare:
   - mismatch ⇒ **FAIL/QUARANTINE** (do not proceed).
3. **Multi‑file outputs**  
   If output is multi‑file, use bundle manifest digest (or gate‑defined digest law). Never “best‑effort” hash.

## C) Gate receipts (no‑PASS‑no‑read)

**Authority:**  
`docs/model_spec/data-engine/interface_pack/contracts/gate_receipt.schema.yaml`  
`docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml`

**Checks (fail‑closed):**
1. **Gate exists and authorizes output** — gate_id must exist and list the output_id.
2. **Receipt integrity** — receipt schema valid, status PASS, and hashing law verification succeeds.
3. **Missing/invalid receipt** — **no PASS → no read** (WAITING or FAIL per policy).

## D) Instance‑proof receipts (if required)

**Authority:**  
`docs/model_spec/data-engine/interface_pack/contracts/instance_proof_receipt.schema.yaml`

**Checks (fail‑closed):**
1. If instance proof is required by scope, a receipt **must** bind:
   - `target_ref` == locator ref
   - `target_digest` == locator digest
2. If engine does not emit receipts, SR may emit **verifier receipts** using the same schema, but consumers must still validate the binding.

---

## Quarantine rules
- Any failure above must produce a **quarantine outcome** with by‑ref evidence pointers.
- Silent drops are not allowed.

