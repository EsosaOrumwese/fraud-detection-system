# L2 — Orchestration / DAG for 1A.S0 (spec-true, no over-engineering)

> Sources of truth:
> - `state.1A.s0.expanded.txt` (S0 spec)
> - `pseudocode-1A.s0.L0.txt` (L0 primitives)
> - `pseudocode-1A.s0.L1.txt` (L1 routines)

# 1) Purpose & non-goals

**Purpose.** Define the exact **wiring** of State-0 (S0) using only the frozen L0 primitives and L1 routines. This section specifies the **ordering, barriers, the single parallel window, lineage key availability, and persistence scopes** so the run is deterministic and reproducible. It does not introduce logic; it orchestrates what already exists in the sources of truth.

**Non-goals.**

* No new algorithms, samplers, numeric formulas, or tie-break rules.
* No schema/dictionary/registry changes; no new artefacts beyond those enumerated by the spec.
* No reordering that would alter **`parameter_hash`**, **`manifest_fingerprint`**, or **`run_id`** derivation.
* No RNG **events** in S0 (the RNG **audit row only**, as defined in L1/L0).
* No alternative numeric policy, math libraries, or environment flags; L2 does not relax L0/L1 constraints.
* No additional caching/shuffling/parallelism beyond the **single** documented window.
* No new configuration knobs (only the documented `emit_hurdle_pi_cache` diagnostic switch).
* No reinterpretation of failures: L2 surfaces L1/L0 failures via the existing abort path; it does not mask or retry.

---

# 2) Contract (inputs → outputs → side-effects)

This section is grounded in the frozen spec and L0/L1; it defines a **closed set** of inputs and outputs. L2 adds no new artefacts or behaviors beyond what those documents require.

## Inputs (closed set)

1. **Run seed**

   * `seed : u64` (the only RNG seed referenced by S0; S0 emits **audit only**, no events).

2. **Governed parameter bundle 𝓟**

   * The complete set of governed parameter files (ASCII basenames, unique), exactly what S0.2 hashes to form `parameter_hash`.
   * L2 must obtain these via the host shim `list_parameter_files()` before S0.2 runs.

3. **Opened artefacts 𝓐 needed by S0 (must be opened before S0.2)**

   * **Numeric policy**: `numeric_policy.json` (numeric governance).
   * **Pinned math profile**: `math_profile_manifest.json` (deterministic libm profile).
   * **Universe refs**: ISO set, GDP vintage asset, Jenks-5 bucket map (read-only).
   * **Governance**: schema authority files and dataset dictionary/registry anchors that S0.1 resolves and relies on.
   * L2 must obtain the set of artefacts opened so far via `list_opened_artifacts()`; S0.2’s fingerprint must include *all* of them.

4. **Build/runtime notes**

   * `build_commit` (raw commit bytes rendered in L1 S0.10), `code_digest?`, `hostname?`, `platform?`, `notes?`.
   * These are metadata carried into the RNG audit row and the validation bundle (per L1 S0.3/S0.10).

5. **Config**

   * `emit_hurdle_pi_cache : bool` (diagnostic; controls S0.7 only).
   * No other switches are accepted by L2.

> **Invariant:** Nothing else is read by S0. L2 must not introduce additional inputs or defer opening any 𝓐 past S0.2.

---

## Outputs (closed set)

1. **Parameter-scoped datasets (partitioned under `parameter_hash=…`)**

   * `crossborder_eligibility_flags` (S0.6, **required**) — each row must embed the same `parameter_hash` as the partition key.
   * `hurdle_pi_probs` (S0.7, **optional**, only if `emit_hurdle_pi_cache=true`) — each row embeds `parameter_hash`.

2. **RNG audit log (S0.3) — audit row only**

   * Partitioned under `{ seed, parameter_hash, run_id }`.
   * Contains the single pre-draw audit row (algorithm id, key/counter words, and build metadata).
   * **No RNG events** are produced in S0.

3. **Validation bundle (S0.10) — fingerprint-scoped**

   * Published under `fingerprint={manifest_fingerprint}` with `_passed.flag` gate.
   * Contains the normative file set per L1 S0.10, including at minimum:

     * `numeric_policy_attest.json` (from S0.8),
     * `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`,
     * bundle metadata (commit, artefact counts, compiler/numeric profile info),
     * `_passed.flag` computed over **ASCII-sorted** file bytes (excluding the flag itself).

> **Invariant:** No other datasets or logs are produced by S0; in particular **no RNG event streams** originate in S0.

---

## Side-effects

* **None beyond the outputs above.**
* L2 does **not** change numeric policy, sampling, or schema; it only orchestrates L1 and relies on L0 for publishing/gating.
* **Abort behavior:** on any L1/L0 failure, L2 calls the existing `abort_run(…)` path (writes `failure.json` and sentinel, marks incomplete outputs atomically) and does not proceed to S0.10.

---

### Verification checklist (DoD for §2)

* Inputs list includes **only**: `seed`, 𝓟, 𝓐 (with numeric policy + math profile + refs + governance), build/runtime notes, and the single config flag.
* Outputs list is **closed**: parameter-scoped partitions (eligibility; optional hurdle cache), RNG **audit** only, fingerprint-scoped validation bundle with `_passed.flag`.
* Partition scopes and embedded lineage fields are stated explicitly.
* Statement “no RNG events in S0” is present.
* No “TBD” or optional wording remains; nothing relies on memory or unspecified behavior.

---

# 3) “Must-be-open” inputs before S0.2 fingerprint (anti-drift)

This section lists **exactly** the artefacts that must be opened *before* `compute_manifest_fingerprint(...)` runs in **S0.2**. The fingerprint must include *all* artefacts opened up to that point, plus the raw build commit bytes and the parameter bundle digest bytes.

> Rule (normative wiring): **S0.2 fingerprints (`manifest_fingerprint`) over:**
> (i) the **set 𝓐 of artefacts opened so far**,
> (ii) the **raw git commit bytes** (`git32`), and
> (iii) the **parameter bundle digest bytes** (`param_b32`).
> L2 must ensure 𝓐 is complete at S0.2 and **no additional governance artefacts** are first opened after S0.2.

## Must-be-open table (at S0.2)

| Basename / asset (examples)                                        | Kind                      | Opened by                         | Why included in the fingerprint                                                                                            |
|--------------------------------------------------------------------|---------------------------|-----------------------------------|----------------------------------------------------------------------------------------------------------------------------|
| **All governed parameter files (𝓟)**                              | Parameter bundle          | S0.2 (via `list_parameter_files`) | Parameter changes affect the run; their tuple-hash forms `parameter_hash`, and `param_b32` is folded into the fingerprint. |
| **`numeric_policy.json`**                                          | Numeric policy governance | S0.1 → S0.2                       | Changing rounding/FMA/FTZ policy must flip reproducibility; ensure numeric governance is captured.                         |
| **`math_profile_manifest.json`**                                   | Pinned libm/profile       | S0.1 → S0.2                       | Changing the deterministic math profile (e.g., `lgamma`) must flip the fingerprint.                                        |
| **ISO reference set**                                              | Read-only universe asset  | S0.1                              | Universe membership & FK checks depend on it; replacement must flip the fingerprint.                                       |
| **GDP vintage asset** (e.g., 2024, const-2015 USD)                 | Read-only universe asset  | S0.1                              | Merchant features (`g_c`) derive from this; vintage changes must flip the fingerprint.                                     |
| **Jenks-5 bucket map**                                             | Read-only universe asset  | S0.1                              | Design vectors depend on dev-5 buckets; map/version changes must flip the fingerprint.                                     |
| **Schema authority files / Dataset dictionary & registry anchors** | Governance                | S0.1                              | They define what “valid ingress/egress” and “partition contracts” mean; changing these must flip the fingerprint.          |

**Also included by S0.2 (non-file inputs to the fingerprint algorithm):**

* **`git32`** — **raw** build commit bytes read at S0.2 (folded into the fingerprint alongside 𝓐 and `param_b32`).
* **`param_b32`** — the 32 raw bytes of the parameter bundle tuple-hash from S0.2.

> Note: dictionaries/coefficients consumed later by S0.5 are part of the **governed parameter bundle 𝓟** (already hashed) and need not be opened before S0.2 *unless* your process opens them earlier. If they’re opened before S0.2, they automatically join 𝓐 and are included.

## Invariants L2 enforces here

* **Completeness:** Before calling `compute_manifest_fingerprint(artifacts=…, git32, param_b32)`, L2 must assemble 𝓐 as **every artefact opened by S0.1/S0.2** (use `list_opened_artifacts()`), including numeric policy, math profile, ISO/GDP/Jenks, and schema/dictionary/registry governance anchors.
* **No late governance opens:** L2 must not first open new *governance* artefacts after S0.2. (S0.8 writes attestation files but does **not** introduce new inputs.)
* **Raw commit, not hex:** The fingerprint uses the **raw** 32-byte commit payload (`read_git_commit_32_bytes()`), not a hex string.

## DoD checklist for §3

* The table above lists **all** artefact categories S0 opens before S0.2 (numeric policy, math profile, ISO, GDP, Jenks-5, schema/dictionary/registry, and the governed parameter bundle 𝓟).
* L2 states that `compute_manifest_fingerprint` takes **(𝓐, git32, param_b32)** and that L2 **ensures 𝓐 is complete** at that call site.
* It explicitly calls out **raw** commit bytes and the parameter bundle digest bytes as inputs to the fingerprint.
* It explicitly forbids first-time opening of governance artefacts **after** S0.2.
* No “TBD” or optional wording remains.

---

# 4) Stateflow DAG (with explicit barriers)

This is the **only** legal execution order for S0, wired strictly to the frozen L1 entrypoints and relying on L0 for lineage, numeric policy, and audit mechanics. It encodes both **sequencing** and the **single parallel window** allowed by the spec.

```
S0.1 (Universe/Auth) 
   ↓
S0.2 (Hashes/IDs: parameter_hash, manifest_fingerprint, run_id)
   ↓
S0.8 (Numeric policy & self-tests — gate)
   ↓
S0.3 (RNG bootstrap — audit row only, no events)
   ├───────────────┬────────────────────────────────┐   (Parallel window opens)
   │               │                                │
   │          Branch A                              │  Branch B
   │      S0.4 → S0.5 → [S0.7 optional]             │  S0.6
   │               │                                │
   └───────────────┴────────────────────────────────┘   (Parallel window closes)
   ↓
S0.10 (Validation bundle: assemble → gate → publish)
```

## Barriers (normative)

1. **Gate-1 (pre-audit):**
   `S0.8` **must pass** before `S0.3` runs. Numeric environment and libm attestation are a **hard gate**; S0 cannot proceed if they fail.

2. **Gate-2 (post-branches):**
   `S0.10` **must not start** until **both** branches complete:

   * **Branch A:** `S0.4` → `S0.5` → `[S0.7?]` (S0.7 runs only if `emit_hurdle_pi_cache=true`).
   * **Branch B:** `S0.6`.

## Rules embedded in the DAG

* **No RNG events in S0.**
  `S0.3` writes the **single audit row** only (using L0’s master derivation + audit writer). All RNG **events** begin in later states (outside S0).

* **Lineage keys availability.**
  Nothing that persists lineage-keyed outputs runs until `S0.2` has produced `{parameter_hash, manifest_fingerprint, run_id}`.

* **Fingerprint inclusion.**
  `S0.2` computes `manifest_fingerprint` over **all artefacts opened so far** (including numeric policy, math profile, ISO/GDP/Jenks, schema/dictionary/registry) plus raw commit bytes and the parameter bundle digest bytes. L2 **must not** first open new governance artefacts after `S0.2`.

* **Single parallel window.**
  Only `{ S0.4→S0.5→[S0.7?] }` may run in parallel with `S0.6`, and only **after** `S0.3`. Any failure in either branch **aborts** the run (L2 does not proceed to `S0.10`).

* **Partition scopes are distinct and enforced later.**
  Branch outputs (S0.6 and optionally S0.7) are **parameter-scoped** (`parameter_hash=…`, rows embed same). `S0.10` is **fingerprint-scoped** and writes the validation bundle with `_passed.flag`.

## DoD checklist for §4

* ASCII DAG shows **S0.1 → S0.2 → S0.8 → S0.3 → {Branch A || Branch B} → S0.10** with the parallel window and both barriers explicitly marked.
* States that S0 emits **audit only** (no RNG events).
* States **S0.8 before S0.3** (gate), and **S0.10 after both branches** (join).
* Reiterates fingerprint inclusion and lineage availability constraints tied to `S0.2`.
* No extra branches, no alternative orders, no additional parallelism.

---

# 5) Stage-by-stage call map (inputs • calls • persistence • failures)

This section names the **exact L1 entrypoints** each S0 stage calls, what they **consume/produce**, what (if anything) they **persist** (and under which partition), and how failures are **surfaced** (via S0.9). No new helpers are introduced here.

---

## S0.1 — Universe, symbols, authority (no RNG)

**Calls (L1):**
`load_and_validate_merchants` → `load_canonical_refs` → `authority_preflight` → `enforce_domains_and_map_channel` → `derive_merchant_u64` → `freeze_run_context`

**Inputs:** ingress `merchant_ids`; ISO set; GDP vintage asset; Jenks-5 bucket map; schema/dictionary/registry anchors.

**Outputs (in-memory):** `U = (merchants, iso_set, gdp_map, bucket_map, authority)`.

**Persistence:** none (context only).

**Failure surfacing:** via S0.9 (e.g., ingress/schema violations). L2 does not reinterpret.

---

## S0.2 — Hashes & identifiers (no RNG)

**Calls (L1):**
`compute_parameter_hash(list_parameter_files())` →
`compute_manifest_fingerprint(list_opened_artifacts(), read_git_commit_32_bytes(), param_bytes)` →
`derive_run_id(fp_bytes, seed, now_ns(), exists=run_id_exists)`

**Inputs:** governed parameter bundle 𝓟; artefacts opened in S0.1 (numeric policy, math profile, ISO/GDP/Jenks, schema/dictionary/registry); raw 32-byte commit; time (ns) via `now_ns()`.

**Outputs (in-memory):** `parameter_hash (hex & bytes)`, `manifest_fingerprint (hex & bytes)`, `run_id`.
**Derivations (once here, reused later):** `build_commit = hex64(read_git_commit_32_bytes())` — used verbatim in **S0.3** audit and as `ctx.git_commit_hex` in **S0.10**.

**Persistence:** none (lineage only).

**Failure surfacing:** via S0.9 (parameter/artifact hashing/fingerprint issues).

---

## S0.8 — Numeric policy & self-tests (gate)

**Calls (L1):**
`set_numeric_env_and_verify` → `attest_libm_profile` → `run_self_tests_and_emit_attestation`

**Inputs:** numeric policy; math profile; host numeric environment.

**Outputs:** in-memory **attestation object** and pass/fail status.
**Handoff:** L2 retains this `numeric_attest` object and passes it into **S0.10** as `ctx.numeric_attest` (no mutation).

**Persistence:** none here; S0.10 writes the attestation into the fingerprint-scoped validation bundle.

**Barrier:** **must pass** before S0.3 begins.

**Failure surfacing:** via S0.9 (numeric policy/attestation failure). L2 stops the run.

---

## S0.3 — RNG bootstrap (audit row only)

**Calls (L1):**
`rng_bootstrap_audit(seed, parameter_hash, manifest_fingerprint, manifest_fingerprint_bytes, run_id, build_commit, code_digest?, hostname?, platform?, notes?)`
(internally uses L0 `derive_master_material` and `emit_rng_audit_row`)

**Inputs:** `seed`, lineage keys, build/runtime notes.
**Derivation:** `build_commit` is the single value defined in **S0.2** as `hex64(read_git_commit_32_bytes())` (do not re-derive).

**Outputs:** none (to callers).

**Persistence:** **single audit row** under `logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}`; **no RNG events** in S0.

**Failure surfacing:** via S0.9 (audit precondition/format issues).

---

## Branch A — S0.4 → S0.5 → \[S0.7 optional] (no RNG)

### S0.4 — GDP bucket attachment

**Calls (L1):** `S0_4_attach_gdp_features(merchants, iso_set, gdp_map, bucket_map)`

**Inputs:** `U` from S0.1.

**Outputs (to S0.5):** per-merchant features `(g_c, b_m)`.

**Persistence:** none (passed down).

**Failure surfacing:** via S0.9 (coverage/lookup issues).

### S0.5 — Design matrices

**Calls (L1):**
`build_dicts_and_assert_shapes(bundle)` → `encode_onehots(m)` → `build_design_vectors(m, gdp_map, bucket_map)` → `S0_5_build_designs_stream(...)`

**Inputs:** merchants; dictionaries/coefficients; `gdp_map`, `bucket_map`.

**Outputs:** design vectors (`x_hurdle`, `x_nb_mu`, `x_nb_phi`) and any parameter-scoped artefacts per L1 routine.

**Persistence:** parameter-scoped writes **embed `parameter_hash`** when materialized (L1 enforces).

**Failure surfacing:** via S0.9 (shape/coverage).

### S0.7 — Hurdle π diagnostic cache (optional)

**Calls (L1):**
`S0_7_build_hurdle_pi_cache(merchants, beta, dicts, gdp_map, bucket_map, parameter_hash, produced_by_fp)`

**Inputs:** design dicts & coefficients; `gdp_map`, `bucket_map`; lineage keys.

**Outputs:** per-merchant `(logit, π)` diagnostics.

**Persistence:** `hurdle_pi_probs` under `parameter_hash={…}`; rows **embed the same `parameter_hash`**.

**Failure surfacing:** via S0.9 (partition lineage/shape issues).

---

## Branch B — S0.6 (no RNG)

**Calls (L1):**
`S0_6_apply_eligibility_rules(merchants, params, I, K, parameter_hash, produced_by_fp)`
(internally uses `write_eligibility_flags`)

**Inputs:** merchants; `iso_set (I)`; `mcc_set (K)`; lineage keys; governed rule set.

**Outputs:** eligibility decisions per merchant.

**Persistence:** `crossborder_eligibility_flags` under `parameter_hash={…}`; rows **embed the same `parameter_hash`**.

**Failure surfacing:** via S0.9 (rule parsing/coverage; partition lineage).

---

## S0.10 — Validation bundle (fingerprint-scoped)

**Calls (L1):**
`preflight_partitions_exist(parameter_hash, emit_hurdle_pi_probs)` →
`assemble_validation_bundle(ctx)` →
`compute_gate_hash_and_publish_atomically(tmp_dir, fingerprint)`

**Inputs:** seed; lineage keys; **attestation object** (`numeric_attest` from S0.8); presence of parameter-scoped outputs.

**Outputs:** validation directory with the required files and `_passed.flag`.

**Persistence:** publish under `fingerprint={manifest_fingerprint}`; `_passed.flag` computed over **ASCII-sorted** file bytes (excluding the flag).

**Failure surfacing:** via S0.9 (preflight missing; gate/atomic publish; lineage mismatch).

---

### DoD checklist for §5

* Every block lists **only** L1 functions that exist in **L1 v5-frozen** (no new helper names).
* Inputs/outputs match the frozen routines; persistence scopes and **embedded lineage rules** are stated where applicable.
* S0.3 clearly indicates **audit row only** (no events).
* Failure handling is consistently “surfaced via S0.9”; L2 adds no retries or reinterpretation.
* No “TBD” or optional language remains.

---

# 6) Concurrency model (one window, hard barriers, fail-fast)

**Model.** State-0 has exactly **one** parallel window, opened **after** the RNG audit row is written and **closed** before the validation bundle is assembled. No other concurrency is permitted.

## Allowed parallel window

After `S0.3 (audit only)`, run the two branches **in parallel**:

* **Branch A:** `S0.4 → S0.5 → [S0.7 optional]`
  Dependencies: needs `U=(M,I,G,B)` from S0.1 and the `parameter_hash`/`fingerprint` from S0.2.
  Notes: S0.7 is gated by `emit_hurdle_pi_cache=true` and depends on S0.5 outputs (dicts/β and the same `G,B`).

* **Branch B:** `S0.6`
  Dependencies: needs `U.merchants`, `U.iso_set` from S0.1 and the `parameter_hash`/`fingerprint` from S0.2.
  Independence: does **not** depend on S0.4/5/7.

**Join:** `S0.10` must not start until **both** branches complete (regardless of whether S0.7 ran).

## Why this is safe (frozen L0/L1 guarantees)

* **No RNG draws in S0.** The only RNG operation is the **audit row** in `S0.3`; no event producers run in S0. (L1 S0.3 + L0 audit writer.)
* **Disjoint persistence scopes.**

  * Branch A/B produce **parameter-scoped** outputs that **embed** the exact `parameter_hash`.
  * `S0.10` writes the validation bundle **under `fingerprint={manifest_fingerprint}`** with `_passed.flag`.
    There is no shared file/partition between the branches or with S0.10.
* **Pure computations over frozen bytes.** S0.4/5/6/7 operate only on `U`, governed parameters, and opened artefacts already covered by S0.2’s fingerprint—no mutable global numeric state, no shared mutable caches.
* **Atomic I/O.** Writes use the L0 atomic publish helpers and lineage verifiers; a task cannot publish to an incorrect partition.

## Failure & cancellation policy

* **Fail-fast:** If any task in the parallel window fails, L2 immediately calls the S0.9 abort path and **does not** start `S0.10`. The sibling task is cancelled or allowed to complete without publish; no partial bundle is assembled.
* **No retries/masking:** L2 surfaces the first error; it does not reinterpret, backoff, or retry.

## Determinism constraints

* **No cross-task writes to the same dataset partition.**
  Branch A writes only its parameter-scoped outputs; Branch B writes only its parameter-scoped flags. Each row embeds the same `parameter_hash` as in the path—L1 enforces this.
* **Idempotent re-runs.** Re-running S0 with identical inputs produces byte-identical artefacts (row order may be unspecified where the schema allows; the validation gate hashes exact bytes).
* **No pre-fingerprint writes.** Nothing that depends on lineage keys may persist before S0.2 has produced `{parameter_hash, manifest_fingerprint, run_id}`.

## DoD checklist for §6

* States **exactly one** parallel window: `{ S0.4→S0.5→[S0.7?] } || { S0.6 }` **after** S0.3 and **before** S0.10.
* States both **barriers**: must pass S0.8 before S0.3; must complete both branches before S0.10.
* Affirms **no RNG events** in S0; **audit row only**.
* Affirms **disjoint persistence scopes** (parameter-scoped vs fingerprint-scoped) and **embedded lineage** requirements.
* Specifies **fail-fast** behavior and **no retries/masking**.
* Prohibits pre-fingerprint writes and cross-task partition sharing.

This section is strictly derived from the frozen L1 routines (what each stage reads/writes) and L0’s publish/gate primitives; no extra concurrency, knobs, or side effects are introduced.

---

# 7) Determinism, lineage, partitions (checklist)

This section encodes the **run-invariants** L2 enforces so S0 remains deterministic and all artefacts carry the correct lineage. It references only frozen L0/L1 mechanics—no new policy.

---

## 7.1 Lineage availability & usage

* **No lineage-keyed writes before S0.2.**
  Nothing may persist to a lineage-scoped partition until S0.2 has produced:
  `parameter_hash (hex & bytes)`, `manifest_fingerprint (hex & bytes)`, and `run_id`.
  *(Matches L1 S0.2 call sites; L0 provides the tuple-hash and fingerprint functions.)*

* **Fingerprint composition is fixed at S0.2.**
  `compute_manifest_fingerprint(artifacts, git32, param_b32)` takes the **full set 𝓐** of artefacts opened so far, **raw 32-byte** commit (`read_git_commit_32_bytes()`), and the **32-byte** parameter bundle digest, and returns `(hex, bytes)`. *(Defined in L0; called in L1 S0.2.)*

* **RNG identifiers are lineage-scoped.**
  RNG audit is partitioned by `{seed, parameter_hash, run_id}` and must be written **after** S0.2. *(L1 S0.3 uses L0’s audit writer.)*

---

## 7.2 Partition scopes & equivalence (dictionary-backed)

L2 must ensure every persisted dataset uses the **correct partition scope** *and* that each row **embeds** the same lineage keys as the path. Use the dictionary-backed verifier L0 exposes:

* **Verifier:** `verify_partition_keys(dataset_id, path_keys, row_embedded)`

  * For **parameter-scoped** datasets (e.g., `crossborder_eligibility_flags`, `hurdle_pi_probs`):
    `expect = { "parameter_hash": path_keys["parameter_hash"] }`
    `got    = { "parameter_hash": row_embedded["parameter_hash"] }`
    Abort on mismatch (`F5: partition_mismatch`). *(L0 provides the exact check.)*
  * For **RNG log-scoped** datasets (S0 audit only):
    `expect = { "seed", "parameter_hash", "run_id" }` equals row-embedded set. *(L0.)*
  * For the **validation bundle**:
    `expect = { "manifest_fingerprint": path_keys["manifest_fingerprint"] }` equals the embedded field. *(L0.)*

> **Where enforced:** L1 writers call the verifier; L2 treats any failure as terminal via the S0.9 abort path.
> **What L2 enforces additionally:** Never publish to a partition whose keys are not yet known (see §7.1).

---

## 7.3 RNG determinism within S0

* **Audit row only.**
  S0 emits **no RNG events**. `rng_bootstrap_audit(...)` derives the root key/counter via L0 `derive_master_material(...)` and writes a single **audit row** under `{seed, parameter_hash, run_id}` using `emit_rng_audit_row(...)`. *(L1 S0.3 + L0 audit writer.)*

* **Counters & blocks never advance in S0.**
  Because S0 doesn’t draw, event envelopes (`before/after/blocks/draws`) are irrelevant here; the only RNG artefact is the audit row.

---

## 7.4 Numeric determinism (gate, not wiring)

* **Numeric attestation gates the run.**
  `set_numeric_env_and_verify` + `attest_libm_profile` + `run_self_tests_and_emit_attestation` must **pass** in S0.8 **before** S0.3.
  This fixes: rounding mode (RNE), FMA-off, FTZ/DAZ-off, and the pinned libm profile (incl. `lgamma`), ensuring deterministic math in all downstream states. *(L1 S0.8; artefacts written under `fingerprint`.)*

> L2 does **not** change numeric policy; it only enforces the **barrier** ordering so the attestation is in effect before any RNG-relevant stage elsewhere.

---

## 7.5 Validation gate & atomic publish (fingerprint-scoped)

* **Gate hash over ASCII-sorted bytes.**
  The validation bundle under `fingerprint={manifest_fingerprint}` must call the L0 `_passed.flag` writer, which:

  * lists bundle files in **bytewise ASCII** order,
  * concatenates the **raw bytes** of every file except `_passed.flag`,
  * SHA-256s the concatenation to produce the flag content,
  * then **atomically renames** the temp dir into the final `fingerprint=…` partition. *(L0 `write_passed_flag` and `publish_atomic`.)*

* **No partial publish.**
  L2 must not attempt to publish anything under the bundle path until the gate has succeeded. *(L0’s publish helpers assume ready-to-publish temp dirs.)*

---

## 7.6 Idempotency & re-run equivalence

Given identical inputs (seed, 𝓟, 𝓐, environment), rerunning S0 must yield:

* identical lineage keys (`parameter_hash`, `manifest_fingerprint`, `run_id`),
* the **same** RNG audit row bytes (same key/counter/metadata),
* the **same** parameter-scoped artefacts (content; row order may be unspecified if schema allows),
* a validation bundle whose `_passed.flag` recomputes to the same value.

This holds because:

* all computations are pure functions of frozen bytes (`U`, 𝓟, 𝓐) after S0.2,
* writers verify partition lineage via `verify_partition_keys(...)`,
* the bundle gate hashes exact bytes in deterministic order.

---

## DoD checklist for §7

* States **no pre-S0.2** lineage-keyed writes.
* Captures the **exact** fingerprint inputs (artefacts set 𝓐 + raw `git32` + `param_b32`) and their timing.
* Specifies **partition scopes** for parameter-scoped, RNG log-scoped, and fingerprint-scoped datasets and requires **embedded = path** lineage via `verify_partition_keys(...)`.
* Affirms **audit-only** RNG behavior in S0 and “no counter advance.”
* Requires S0.8 numeric attestation to **gate** S0.3.
* Details the **ASCII-sorted** `_passed.flag` build and **atomic publish**.
* States the **idempotency**/re-run equivalence expectation.

All items above are directly supported by the frozen L0/L1 exports (audit writer, fingerprint/tuple-hash, partition verifier, gate hash, atomic publish) and by the S0.8 attestation barrier; no extra rules or knobs are introduced.

---

# 8) Error / abort propagation (single path, fail-fast)

L2 does **not** reinterpret failures. Any violation raised by an L1 routine or L0 helper is surfaced via the **single S0.9 abort path** and the run stops. This section pins what L2 must pass and what is written on abort, using only frozen L0/L1 behavior.

---

## 8.1 One abort API (what L2 calls)

L2 must invoke the S0.9 abort with the **canonical payload**:

* **Function (L1/L0):** `abort_run(...)` *(L0 also exposes `abort = abort_run` as an alias; use the canonical name to avoid drift.)*
* **Failure class:** one of `F1…F10` (exact strings).
* **Failure code:** snake_case code defined by the caller (e.g., `l2_gate_failed`, `partition_mismatch`).
* **Context (required fields):**

  * `state`: e.g., `"S0.3"`
  * `module`: e.g., `"1A.S0.orchestrator"` or the concrete submodule
  * `parameter_hash` (hex64), `manifest_fingerprint` (hex64)
  * `seed` (u64), `run_id` (hex32)
  * `detail`: **typed** object per the spec tables (inputs that caused the error, file/basename, expected vs got, etc.)
  * `partial_partitions` (optional list): `{dataset_id, partition_path, reason}` for anything L2/L1 began but must mark as incomplete

These fields and class constraints are defined in **L1 S0.9** (the failure builder) and mirrored by the **L0 abort helper**.

---

## 8.2 What happens on abort (side-effects, all deterministic)

When `abort_run(...)` is called:

* A **failure bundle** is written under the lineage scope (uses the ctx’s `seed`, `parameter_hash`, `run_id`, and `manifest_fingerprint` as appropriate per the frozen implementation).
* Two files are always emitted in the bundle directory:

  * `failure.json` (the canonical payload),
  * `_FAILED.SENTINEL.json` (small header for quick scans).
* Any `partial_partitions` supplied are marked by writing a small `_FAILED.json` under each partition path to **prevent silent partial data**.
* RNG is **frozen** for the run (no further audit/event writes).
* The process **exits non-zero** (no retries/masking).

All of the above behaviors are provided by the frozen **S0.9** routines and the **L0** abort/publish utilities.

---

## 8.3 Where L2 must abort (typical sites)

L2 should immediately call `abort_run(...)` if **any** of the following occurs:

* **S0.1 / S0.2**: ingress invalid; schema/authority failure; parameter hashing/fingerprint errors.
* **S0.8**: numeric policy/profile attestation fails (RNE/FMA/FTZ or libm profile mismatch).
* **S0.3**: audit bootstrap cannot emit the audit row with correct lineage.
* **Branch A** (`S0.4→S0.5→[S0.7?]`) or **Branch B** (`S0.6`): coverage/shape/rule errors; **partition lineage mismatch** (embedded keys ≠ path keys).
* **S0.10**: preflight partitions missing; validation bundle gate fails; atomic publish fails.

> **Fail-fast policy:** if any parallel branch fails, L2 **does not** start `S0.10` and cancels the sibling branch (or lets it finish without publish). First failure wins.

---

## 8.4 What L2 must **not** do

* No retries, backoffs, or “best-effort” publishes.
* No custom error envelopes; always use `abort_run(...)` with the required context.
* No continuing to downstream stages after an abort.
* No silent partial writes: if a writer started a partition, include it in `partial_partitions` so `_FAILED.json` is dropped there.

---

## 8.5 Minimal L2 call pattern (illustrative)

```text
try:
  … run S0.1 → S0.2 → S0.8 …
except Error as e:
  abort_run("F7", "numeric_attestation_failed",
            ctx.seed, ctx.L.parameter_hash_hex, ctx.L.manifest_fingerprint_hex, ctx.L.run_id,
            detail=e.to_detail(),
            partial_partitions=[])
  return

# In parallel window:
resA = taskA()  # may raise
resB = taskB()  # may raise
# If either raises, catch once and call abort_run(...) with the first failure’s class/code/detail.
```

(Actual failure classes/codes must match the frozen S0.9 tables used by each L1 routine; L2 passes through the class/code surfaced by the callee or chooses the appropriate class when the error originates in L2.)

---

## DoD checklist for §8

* **Single abort path** documented with **required fields** (`state`, `module`, lineage keys, RNG ids, typed `detail`).
* **Side-effects** of abort are listed (failure bundle + sentinel, optional per-partition `_FAILED.json`, RNG freeze, non-zero exit).
* **Fail-fast** behavior is explicit for the parallel window; **no retries/masking** stated.
* Concrete places where L2 must call `abort_run` are enumerated for each stage.
* No alternative error formats, no new knobs, no ambiguity about publish after failure.

All elements above are precisely what the frozen **L1 S0.9** and **L0** provide (failure builder, abort writer, atomic publish helpers); L2 simply routes failures to them and stops.

---

# 9) Config surface (frozen & minimal)

**Principle.** L2 exposes only the configuration explicitly implied by the frozen spec and L1/L0. No operational knobs, no performance/tuning switches, no alternate math/RNG behavior. Anything else would change lineage or break determinism.

## 9.1 Single switch (diagnostic only)

**`emit_hurdle_pi_cache : bool`**

* **Scope:** Controls whether **S0.7** runs to materialize the *diagnostic* dataset `hurdle_pi_probs`.
* **Effect:**

  * `false` (default): skip S0.7; no `hurdle_pi_probs` is written.
  * `true`: call `S0_7_build_hurdle_pi_cache(merchants, beta, dicts, G, B, parameter_hash, produced_by_fp)` after S0.5; persist under `parameter_hash=…` with rows embedding the same `parameter_hash`.
* **Determinism:** Does **not** affect `parameter_hash` or `manifest_fingerprint` (the governed parameter bundle and opened-artefact set remain identical); it only controls whether that optional, parameter-scoped artefact is emitted.
* **Where enforced:** L2 orchestration guards the S0.7 call; L1 contains the writer with partition/lineage checks.

> Verified in frozen sources: S0.7 is present as an optional diagnostic writer in L1; L0/L1 contain no other runtime switches. This flag is **L2-only** wiring that decides whether the existing L1 routine is invoked.

## 9.2 Non-configurable by design (must remain fixed)

To prevent drift or hidden variability, all of the following are **not** configurable by L2:

* **RNG & numeric policy:** algorithm (`philox2x64-10`), lane/block semantics, `u01` mapping, samplers, rounding mode (RNE), FMA-off, FTZ/DAZ-off, pinned libm profile (`lgamma`, etc.). These are governed by L0/L1 and attested in **S0.8**.
* **Ordering & barriers:** `S0.1 → S0.2 → S0.8 → S0.3 → { S0.4→S0.5→[S0.7?] || S0.6 } → S0.10`. No alternative orders or extra parallelism.
* **Lineage composition:** `parameter_hash` (tuple-hash of governed parameters) and `manifest_fingerprint(𝓐, git32, param_b32)` (artefacts opened pre-S0.2 + raw 32-byte commit + 32-byte param digest).
* **Partitions & gates:** parameter-scoped outputs embed `parameter_hash`; validation bundle is fingerprint-scoped with ASCII-sorted `_passed.flag`.
* **Operational knobs:** no thread counts, shuffles, retries, “fast-math”, alternate RNGs, logging verbosity switches, or ad-hoc caches.

## 9.3 Interface

```text
struct Config {
  emit_hurdle_pi_cache: bool = false
}
```

**Usage in L2:**

* Branch A: after `S0.5`, `if cfg.emit_hurdle_pi_cache: S0_7_build_hurdle_pi_cache(...)`.
* All other stages ignore `cfg`.

## DoD checklist for §9

* Only **one** flag is exposed (`emit_hurdle_pi_cache`), with scope, effect, default, and determinism note.
* An explicit “**non-configurable by design**” list bans all other knobs (RNG, numeric, ordering, lineage, partitions, operational tuning).
* The L2 usage site of the flag (guarding S0.7) is stated; no other stages are controlled by config.
* No ambiguous “TBD” options, no environment levers, no implicit toggles.

---

# 10) Orchestrator pseudocode (single, spec-true routine)

Below is the **only** legal wiring for S0, calling frozen L1 entrypoints and relying on L0 for bytes/IDs/gates. It includes the two hard barriers and the single parallel window. Host-environment shims are used **only** to fetch bytes/paths/platform info; they do **not** alter logic.

```text
# Host shims (L2-only, no logic): provide bytes/handles the L1/L0 calls need
host = {
  list_parameter_files():         list[(basename, path)],
  open_parameter_bundle(P_files): bundle,           # exposes bundle.load(name)
  list_opened_artifacts():        list[(basename, path)],   # all artefacts opened in S0.1
  read_git_commit_32_bytes():     bytes[32],        # raw 32-byte commit
  run_id_exists(rid: hex32):      bool,             # for uniqueness loop
  platform_descriptor():          string,           # OS/libc/compiler triplet
  compiler_flags():               map,              # structured flags used to build (key→value)
  numeric_policy_paths():         { numeric_policy_json, math_profile_manifest_json },
  read_bytes(path: string):       bytes,            # raw bytes; inclusion into 𝓐 when opened in S0.1
  build_notes():                  { hostname?:string, code_digest?:hex64, notes?:string }
}

# Config surface (single toggle)
struct Config { emit_hurdle_pi_cache: bool = false }

function run_S0(seed: u64, cfg: Config):
  # ─────────────────────────────────────────────────────────────
  # S0.1 — Universe, symbols, authority (no persistence)
  # ─────────────────────────────────────────────────────────────
  M0 = load_and_validate_merchants()                  # ingress → typed rows
  (I, G, B) = load_canonical_refs()                   # ISO set, GDP map, Jenks-5 buckets
  # Ensure numeric policy/profile are opened now so S0.2’s artifact snapshot (𝓐) includes them
  paths = host.numeric_policy_paths()
  _ = host.read_bytes(paths.numeric_policy_json)           # ensure opened for 𝓐
  _ = host.read_bytes(paths.math_profile_manifest_json)    # ensure opened for 𝓐
  # Open governance anchors NOW so they are part of 𝓐 and available to L1:
  # (Exact locations are environment-configured; the host provides bytes. Parsing is pure.)
  reg_bytes  = host.read_bytes("governance/artefact_registry_1A.yaml")      # ensure opened for 𝓐
  dict_bytes = host.read_bytes("governance/dataset_dictionary.layer1.1A.json")  # ensure opened for 𝓐
  registry   = parse_registry_yaml(reg_bytes)
  dictionary = parse_dictionary_json(dict_bytes)
  authority = authority_preflight(registry, dictionary)
  M1 = enforce_domains_and_map_channel(M0, I)         # FK ISO, MCC domain, channel→{CP,CNP}
  M2 = derive_merchant_u64(M1)                        # canonical u64 per merchant
  U  = freeze_run_context(M2, I, G, B, authority)     # immutable run context

  # ─────────────────────────────────────────────────────────────
  # S0.2 — Hashes & identifiers (no persistence)
  # ─────────────────────────────────────────────────────────────
  P_files = host.list_parameter_files()
  (param_hash_hex, param_hash_bytes, param_digest_rows, param_resolved) =
       compute_parameter_hash(P_files)

  arts   = host.list_opened_artifacts()               # must include numeric policy/profile, ISO/GDP/Jenks, schemas/dict/registry opened above
  git32  = host.read_git_commit_32_bytes()
  (fp_hex, fp_bytes, fp_resolved, artifact_rows) =
       compute_manifest_fingerprint(arts, git32, param_hash_bytes)

  t_ns   = now_ns()                                   # from L0 Batch F
  run_id = derive_run_id(fp_bytes, seed, t_ns, host.run_id_exists)

  # ─────────────────────────────────────────────────────────────
  # S0.8 — Numeric policy & self-tests (GATE)
  # ─────────────────────────────────────────────────────────────
  env = set_numeric_env_and_verify()
  paths = host.numeric_policy_paths()
  (math_profile_id, digests) = attest_libm_profile(paths)
  platform = host.platform_descriptor()
  numeric_attest = run_self_tests_and_emit_attestation(env, math_profile_id, digests, platform)
  # HARD BARRIER: if any S0.8 step fails, abort (Section 8). Otherwise proceed.

  # ─────────────────────────────────────────────────────────────
  # S0.3 — RNG bootstrap (audit row only; no events in S0)
  # ─────────────────────────────────────────────────────────────
  bn = host.build_notes()
  rng_bootstrap_audit(seed,
                      param_hash_hex,
                      fp_hex, fp_bytes,
                      run_id,
                      hex64(git32),            # build_commit (hex)
                      bn.code_digest ?? null,
                      bn.hostname   ?? null,
                      platform,
                      bn.notes      ?? null)

  # ─────────────────────────────────────────────────────────────
  # PARALLEL WINDOW: Branch A  ||  Branch B
  # ─────────────────────────────────────────────────────────────
  produced_by_fp = fp_hex

  # ---------- Branch A: S0.4 → S0.5 → [S0.7?] ----------
  taskA = async {
    # S0.4 — coverage check / feature attach (pure over U; validates G,B coverage)
    feat = S0_4_attach_gdp_features(U.merchants, U.iso_set, U.gdp_map, U.bucket_map)
    # S0.5 — dictionaries & designs (pure; may materialize parameter-scoped artefacts if specified in L1)
    dicts, coefs = build_dicts_and_assert_shapes(open_parameter_bundle(P_files))
    stream = S0_5_build_designs_stream(U.merchants, dicts, coefs, U.gdp_map, U.bucket_map)
    drain(stream)   # (internal to L1) consumer is state-internal; no S0 persistence mandated here
    # S0.7 — optional diagnostic cache (parameter-scoped)
    if cfg.emit_hurdle_pi_cache:
       S0_7_build_hurdle_pi_cache(U.merchants, coefs.beta_hurdle, dicts,
                                  U.gdp_map, U.bucket_map,
                                  param_hash_hex, produced_by_fp)
    return "A_OK"
  }

  # ---------- Branch B: S0.6 ----------
  taskB = async {
    S0_6_apply_eligibility_rules(U.merchants, U.iso_set,
                                 param_hash_hex, produced_by_fp)   # writes parameter-scoped flags
    return "B_OK"
  }

  # Join (fail-fast policy handled by the async runner; first exception aborts the run)
  resA = await taskA
  resB = await taskB

  # ─────────────────────────────────────────────────────────────
  # S0.10 — Validation bundle (fingerprint-scoped)
  # ─────────────────────────────────────────────────────────────
  preflight_partitions_exist(param_hash_hex, cfg.emit_hurdle_pi_cache)

  ctx = {
    fingerprint:     fp_hex,
    parameter_hash:  param_hash_hex,
    git_commit_hex:  hex64(git32),
    artifacts:       [name for (name, _) in arts],
    math_profile_id: math_profile_id,
    compiler_flags:  host.compiler_flags(),
    numeric_attest:  numeric_attest,
    param_digests:   param_digest_rows,     # from S0.2
    artifact_digests:artifact_rows,         # from S0.2
    param_filenames_sorted: param_resolved.filenames_sorted,  # from S0.2
    # optional lints; include if earlier stages produced them
    dictionary_lint: null,
    schema_lint:     null
  }
  tmp_dir = assemble_validation_bundle(ctx)
  compute_gate_hash_and_publish_atomically(tmp_dir, fp_hex)

  return { ok: true,
           lineage: { parameter_hash: param_hash_hex,
                      manifest_fingerprint: fp_hex,
                      run_id: run_id } }
```

### Notes (normative, not optional)

* **Barriers:** S0.8 must pass **before** S0.3; S0.10 runs **after** both branches complete.
* **S0 produces no RNG events.** Only the **audit row** is written in S0.3.
* **Partition scopes:** S0.6 and (optionally) S0.7 write **parameter-scoped** datasets embedding the same `parameter_hash` as the path; S0.10 writes the validation bundle under `fingerprint={manifest_fingerprint}` and gates with the ASCII-sorted `_passed.flag`.
* **Fingerprint inclusion:** `host.list_opened_artifacts()` must include everything S0.1 opened (numeric policy/profile, ISO/GDP/Jenks, schema/dictionary/registry). Those exact bytes (+ raw `git32` + `param_b32`) feed `compute_manifest_fingerprint`.
* **Abort policy:** Any failure in any stage causes an immediate `abort_run(...)` (Section 8). L2 does not retry or mask.

### DoD for §10

* Single routine that wires **only** frozen L1 names and L0 helpers.
* Shows both barriers and the single parallel window.
* Supplies every input expected by L1 functions (including `fp_bytes`, `param_b32`, `git32`, platform/flags).
* Produces all required outputs (audit row; parameter-scoped partitions; fingerprint-scoped validation bundle with gate).
* No new knobs, no invented algorithms, no ambiguity.

---

# 11) Definition of Done (acceptance checks)

This section is the go/no-go list for S0. A run is **Done** only if **all** checks below pass. Each check is grounded in the frozen L0/L1 and the S0 spec—no extra rules, no new artefacts.

## 11.1 Required files & partitions exist (scope-correct)

1. **RNG audit (audit-only in S0):**
   One audit row exists under
   `logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl`.
   There are **no** RNG *event* files under this lineage scope.

2. **Parameter-scoped datasets:**

   * `crossborder_eligibility_flags` exists under `parameter_hash={parameter_hash}`.
   * If `emit_hurdle_pi_cache=true`: `hurdle_pi_probs` exists under `parameter_hash={parameter_hash}`.
   * Each row **embeds** the same `parameter_hash` as the path key.

3. **Validation bundle (fingerprint-scoped):**
   Directory exists at `validation/fingerprint={manifest_fingerprint}` and contains at least:

   * `numeric_policy_attest.json` (S0.8),
   * `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`,
   * `_passed.flag` (see §11.4).

## 11.2 Lineage re-derivation matches

Using the L0 primitives (or the already-emitted *_resolved* JSONs):

* Recompute `parameter_hash` from the governed parameter bundle 𝓟; must equal the emitted `parameter_hash`.
* Recompute `manifest_fingerprint = compute_manifest_fingerprint(arts, git32, param_b32)` using **exactly** the artefacts opened pre-S0.2 (S0.1’s set), the **raw** 32-byte commit, and the **32-byte** parameter-bundle digest; must equal the emitted `manifest_fingerprint`.

## 11.3 Partition lineage equals row lineage (dictionary-backed)

For every persisted dataset in §11.1:

* Run L0 `verify_partition_keys(dataset_id, path_keys, row_embedded)`.

  * **Parameter-scoped** datasets must have `row.parameter_hash == path.parameter_hash`.
  * **RNG audit** must embed `{seed, parameter_hash, run_id}` equal to its path.
  * **Validation bundle** must embed `manifest_fingerprint` equal to its path.

Any mismatch → **fail (F5: partition_mismatch)**.

## 11.4 Validation gate (_passed.flag) is correct

* List bundle files in **bytewise ASCII** order, **excluding** `_passed.flag`.
* Concatenate each file’s **raw bytes** in that order; SHA-256 the result.
* The `_passed.flag` content must equal that digest; publish location must match `fingerprint={manifest_fingerprint}`.
* Publish was done atomically (temp dir → final dir with a single rename).

Any difference or non-atomic publish → **fail (F10: bundle_gate_or_publish_failed)**.

## 11.5 Numeric attestation gate passed (pre-RNG)

* S0.8 outputs `numeric_policy_attest.json` with pass status for:

  * RNE rounding, FMA-off, FTZ/DAZ-off,
  * pinned libm profile (incl. `lgamma`),
  * self-tests (Neumaier sum, total-order key, libm regression).
* L2 executed S0.8 **before** S0.3 (RNG bootstrap).

If missing or failed → **fail (F7: numeric_attestation_failed)**.

## 11.6 RNG audit content is consistent

Read the single audit row and confirm:

* Algorithm string is exactly `"philox2x64-10"`.
* The root key/counter words equal L0 `derive_master_material(seed, manifest_fingerprint_bytes)` *(independent recompute)*.
* The audit partition keys `{seed, parameter_hash, run_id}` match the row’s embedded fields.
* There are **zero** RNG event envelopes recorded for S0 (only the audit row exists under this lineage scope).

Any discrepancy → **fail (F4a: rng_audit_inconsistent_or_missing)**.

## 11.7 Determinism & re-run equivalence (scope-true)

Re-run S0 with **identical inputs** (𝓟, artefacts set 𝓐, `seed`, environment). Acceptance:

* `parameter_hash` and `manifest_fingerprint` must be identical.
* **RNG root key/counter** from audit must be identical (same `seed` and `fingerprint`).
* Parameter-scoped datasets (`crossborder_eligibility_flags`, optional `hurdle_pi_probs`) must be byte-identical (row order may be unspecified if schema allows; content must match).
* Validation bundle files (excluding `_passed.flag`) must be byte-identical; `_passed.flag` therefore matches.

> **Note:** `run_id` is designed to be unique per run (depends on `now_ns()`); the **audit path** may differ, but the **audit row’s key/counter** and **all parameter/fingerprint-scoped artefacts** must match.

## 11.8 No late governance opens

Audit that **all governance and universe artefacts** (numeric policy, math profile, ISO/GDP/Jenks, schema/dictionary/registry) were opened **before** S0.2 fingerprinting, and that S0 didn’t first open any such artefact after S0.2. If violated → **fail (F2: fingerprint_inputs_incomplete)**.

## 11.9 Fail-fast behavior

* If any stage fails, a failure bundle exists with `failure.json` and `_FAILED.SENTINEL.json` under the lineage scope; any started dataset partitions have a small `_FAILED.json`.
* No S0.10 bundle is published after an abort.
* No retries/backoffs observed in logs.

Violation → **fail (F9: abort_policy_violation)**.

---

### DoD summary (all must pass)

* Presence & scope of outputs (§11.1)
* Lineage re-derivation (§11.2)
* Partition equivalence (§11.3)
* Gate hash & atomic publish (§11.4)
* Numeric attestation ordering & pass (§11.5)
* Audit consistency & no events in S0 (§11.6)
* Determinism across re-runs (with `run_id` caveat) (§11.7)
* No late governance artefacts (§11.8)
* Fail-fast abort semantics (§11.9)

This DoD uses only the frozen L0/L1 primitives and the S0 spec’s rules; it introduces **no** new behaviours and leaves **no** ambiguous, optional checks.

---

# 12) Pitfalls to explicitly avoid (normative prohibitions)

This section lists the **forbidden moves** when wiring S0. Each item is justified by the frozen L0/L1 and the S0 spec so an implementer can’t “optimize” their way into drift. For each, we state the **symptom**, the **prohibition**, and the **correct action**.

---

## 12.1 Lineage & fingerprint

1. **Fingerprint too early / incomplete**
   * **Symptom:** `manifest_fingerprint` computed before opening numeric policy, math profile, ISO/GDP/Jenks, or schema/dictionary/registry.
   * **Forbidden:** Calling `compute_manifest_fingerprint(...)` without the **full** artefacts set 𝓐 opened by S0.1.
   * **Do instead:** After S0.1, gather 𝓐 via `list_opened_artifacts()` and pass **𝓐 + raw git32 (32B) + param_b32 (32B)** to `compute_manifest_fingerprint(...)`.

2. **Hex commit bytes**
   * **Symptom:** Feeding hex-encoded commit into the fingerprint.
   * **Forbidden:** Using any non-raw representation for `git32`.
   * **Do instead:** Use **raw 32 bytes** from `read_git_commit_32_bytes()`.

3. **Run-id in fingerprints / lineage keys**
   * **Symptom:** `run_id` influencing RNG or fingerprint.
   * **Forbidden:** Including `run_id` in any derivation of RNG or `manifest_fingerprint`.
   * **Do instead:** Use `run_id` **only** for audit/log partitioning and uniqueness.

---

## 12.2 Orchestration & concurrency

4. **Skipping the numeric gate**

   * **Symptom:** Running RNG bootstrap (S0.3) before S0.8 attestation.
   * **Forbidden:** Any RNG stage before the numeric policy gate **passes**.
   * **Do instead:** Enforce barrier: `S0.1 → S0.2 → S0.8 → S0.3`.

5. **Extra parallelism or reordered branches**

   * **Symptom:** Running S0.6 before S0.3, or interleaving S0.4/5 with S0.2.
   * **Forbidden:** Any order other than
     `S0.1 → S0.2 → S0.8 → S0.3 → {S0.4→S0.5→[S0.7?] || S0.6} → S0.10`.
   * **Do instead:** Use the single allowed parallel window only after S0.3 and join before S0.10.

6. **Persisting before lineage exists**

   * **Symptom:** Writing parameter-scoped outputs during/ before S0.2.
   * **Forbidden:** Any lineage-scoped write without `{parameter_hash, manifest_fingerprint, run_id}`.
   * **Do instead:** Persist only after S0.2 produced lineage keys.

---

## 12.3 RNG & numeric policy

7. **RNG events in S0**

   * **Symptom:** Event envelopes with `{before, after, blocks, draws}` appearing in S0 logs.
   * **Forbidden:** Producing any RNG **event** in S0.
   * **Do instead:** In S0.3 **only** emit the **audit row** with `emit_rng_audit_row(...)`.

8. **Lane/block policy deviations**

   * **Symptom:** Single-uniform draws that consume a half-block or reuse the high lane.
   * **Forbidden:** Any change to L0’s block advance and lane usage semantics.
   * **Do instead:** When later states emit events, use L0 samplers as-is; for S0 specifically, **no draws**.

9. **Unpinned math / fast-math**

   * **Symptom:** FMA on, FTZ/DAZ on, non-RNE rounding, or unpinned `lgamma`.
   * **Forbidden:** Numeric environment deviations from S0.8.
   * **Do instead:** Require S0.8 to pass; **never** override math after the gate.

---

## 12.4 Partitions, embedding, and publish

10. **Wrong partition scope**

    * **Symptom:** Putting parameter-scoped datasets under `fingerprint=...`, or vice versa.
    * **Forbidden:** Scope mismatch with the dictionary.
    * **Do instead:**
      * Parameter-scoped (`crossborder_eligibility_flags`, optional `hurdle_pi_probs`) → `parameter_hash=...`.
      * Validation bundle → `fingerprint={manifest_fingerprint}`.

11. **Embedded lineage ≠ path lineage**

    * **Symptom:** Rows whose `parameter_hash` doesn’t equal the partition key.
    * **Forbidden:** Writing rows without embedded lineage equivalence.
    * **Do instead:** Call `verify_partition_keys(dataset_id, path_keys, row_embedded)` for every persisted rowset; abort on mismatch (F5).

12. **Non-atomic bundle publish / wrong gate**

    * **Symptom:** `_passed.flag` not matching the ASCII-sorted concatenation hash; temp files visible in final dir.
    * **Forbidden:** Any publish that isn’t “hash → write flag → atomic rename.”
    * **Do instead:** Use L0 gate builder and `publish_atomic(...)`.

---

## 12.5 Inputs, caching, and “helpful” behavior

13. **Late governance opens**

    * **Symptom:** Opening a new schema/ISO/GDP/Jenks/numeric artefact after S0.2.
    * **Forbidden:** Mutating 𝓐 post-fingerprint.
    * **Do instead:** Open all governance artefacts in S0.1; S0.2 fingerprints that closed set.

14. **“Helpful” caches or shuffles**

    * **Symptom:** Reordering reductions, caching partial design matrices, or adding IO-side buffering that alters byte order.
    * **Forbidden:** Any transformation that changes deterministic byte content or order.
    * **Do instead:** Keep S0.4/5/6/7 pure over frozen bytes; use Neumaier order and L0 kernels where defined.

15. **Ad-hoc toggles**

    * **Symptom:** Thread-count flags, debug IO skips, alternate RNG, alternate libm profile flags.
    * **Forbidden:** Any extra config beyond `emit_hurdle_pi_cache`.
    * **Do instead:** Expose **only** `emit_hurdle_pi_cache` to guard S0.7.

---

## 12.6 Abort policy

16. **Continuing after a failure**

    * **Symptom:** Publishing a partial bundle or running S0.10 after a branch error.
    * **Forbidden:** Proceeding past the first failure or masking errors with retries.
    * **Do instead:** Call `abort_run(F*, code, ctx)` immediately; mark partial partitions via `_FAILED.json`; stop.

---

## 12.7 Quick-lint checklist (use this before freezing a run)

* Fingerprint inputs = 𝓐 (from S0.1) + **raw** `git32` + `param_b32`.
* S0.8 **passed** before S0.3; S0.3 wrote **audit row only**.
* Parameter-scoped outputs embed `parameter_hash` == path key.
* Validation bundle under `fingerprint={manifest_fingerprint}`; `_passed.flag` correct; atomic publish.
* No governance artefacts first-opened after S0.2.
* No extra config used; no event envelopes in S0 logs.
* On any failure, abort bundle + sentinel present; no S0.10.

These prohibitions and checks are **mechanical restatements** of what the frozen L0/L1 already enforce. L2’s job is to **wire** them and refuse anything else.

---

# 13) Host shims required by L2 (names & contracts)

This section pins the **only** host-environment hooks L2 is allowed to use. They provide **bytes/paths/metadata only**—no algorithms, no ordering, no policy. Every shim has a **name, purpose, contract, determinism constraints, failure mapping,** and **where it’s used** in S0.

> Source of truth: frozen L0/L1 and the S0 spec. These shims exist only to feed the exact inputs those routines require.

---

## H1. `list_parameter_files() -> list[(basename_ascii: string, abs_path: string)]`

**Purpose.** Enumerate the governed parameter bundle 𝓟 for S0.2 hashing.

**Contract.**

* Returns every governed parameter file **exactly once**.
* `basename_ascii` must be **ASCII** and **unique** across the list.
* Paths must be absolute and readable.

**Determinism.** Order is irrelevant (L0 hashes after **ASCII basename** sort). Contents must be stable for the run.

**Failure mapping.**

* Missing/IO → `F2:param_files_io`.
* Non-ASCII or duplicate basenames → `F2:basenames_invalid_or_duplicate`.

**Used in.** S0.2 `compute_parameter_hash(...)`.

---

## H2. `open_parameter_bundle(P_files) -> bundle_handle`

**Purpose.** Provide a handle to read parameter bytes (for L1 routines that materialize dictionaries/coeffs).

**Contract.**

* `bundle_handle.load(basename_ascii) -> bytes` must return **exact** file bytes.
* Must not mutate or normalize contents (no transcoding, no CRLF changes).

**Determinism.** Byte-identical across re-reads in the same run.

**Failure mapping.**

* Missing file/IO → `F2:param_file_open_failed`.

**Used in.** S0.5 `build_dicts_and_assert_shapes(...)` (and any L1 that needs parameter bytes).

---

## H3. `list_opened_artifacts() -> list[(basename_ascii: string, abs_path: string)]`

**Purpose.** Snapshot the **full set 𝓐** of artefacts opened **before** S0.2 so they can be fingerprinted.

**Contract.**

* Must include everything S0.1 opened: **numeric_policy.json**, **math_profile_manifest.json**, ISO set, GDP vintage, Jenks bucket map, schema/dictionary/registry anchors, etc.
* Same ASCII/unique basename rules as H1.

**Determinism.** The set is **closed** at S0.2. L2 must not first-open any governance artefact after S0.2.

**Failure mapping.**

* Omission/duplication → `F2:fingerprint_inputs_incomplete_or_dup`.

**Used in.** S0.2 `compute_manifest_fingerprint(arts, git32, param_b32)`.

---

## H4. `read_git_commit_32_bytes() -> bytes[32]`

**Purpose.** Supply the **raw** 32-byte commit id for fingerprinting.

**Contract.**

* Returns exactly **32 raw bytes** (not hex, not base64).

**Determinism.** Single commit for the build being executed.

**Failure mapping.**

* Not 32 bytes / unreadable → `F2:git32_invalid`.

**Used in.** S0.2 `compute_manifest_fingerprint(...)`; S0.10 bundle context (hex string derived from these bytes).

---

## H5. `run_id_exists(run_id: hex32) -> bool`

**Purpose.** Allow L1’s `derive_run_id(...)` uniqueness loop to avoid collisions in the audit partition.

**Contract.**

* Returns **true** iff a lineage path exists at
  `logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}`.

**Determinism.** This affects only the **audit path name**; it **must not** influence RNG or fingerprint.

**Failure mapping.**

* Path probe error → `F10:run_id_probe_failed`.

**Used in.** S0.2 `derive_run_id(fp_bytes, seed, now_ns, run_id_exists)`.

---

## H6. `platform_descriptor() -> string`

**Purpose.** Emit a stable description of OS/libc/compiler into attestation/bundle context.

**Contract.**

* A concise triplet or canonical descriptor (e.g., `"Linux-glibc-2.31:clang-17"`).
* Informational only.

**Determinism.** Not part of fingerprint. Stable within a run.

**Failure mapping.**

* If unavailable, return a fixed `"unknown"`; do **not** abort.

**Used in.** S0.8 `run_self_tests_and_emit_attestation(...)` payload; S0.3 audit note.  
*Note:* The validation bundle’s MANIFEST `compiler_flags` field is sourced from **H7 `compiler_flags()`**, not from `platform_descriptor()`.

---

## H7. `compiler_flags() -> map`

**Purpose.** Provide a structured set of compiler/build switches (e.g., to confirm FMA-off) for inclusion in the validation bundle’s MANIFEST.

**Contract.**

* Return a **map** (key → string|bool|number) that captures the effective compiler/build flags.  
  Examples of keys (not exhaustive): `"cc"`, `"cxx"`, `"opt_level"`, `"fma"`, `"ftz"`, `"daz"`, `"rounding_mode"`, `"target_triple"`, `"abi"`, `"ldflags"`, `"cflags"`, `"cxxflags"`.  
  Values must be **deterministic** for the running binary; if unavailable, return an **empty map** (do not fabricate).

**Determinism.** Not part of fingerprint; stable within a run.

**Failure mapping.**

* If unavailable, return **empty map**; do **not** abort.

**Used in.** S0.10 bundle context.

---

## H8. `numeric_policy_paths() -> { numeric_policy_json: string, math_profile_manifest_json: string }`

**Purpose.** Provide absolute paths to numeric policy/profile artefacts for S0.8 attestation **and** ensure they are **opened before S0.2** so they enter 𝓐.

**Contract.**

* Paths must be readable; L2 must **open** them during S0.1 (or earlier) so H3 captures them for fingerprinting.
* These same paths are passed to L1 S0.8.

**Determinism.** Exact bytes must match the ones included in fingerprint.

**Failure mapping.**

* Missing/IO → `F7:numeric_policy_or_profile_missing`.

**Used in.** S0.1 (open for inclusion), S0.8 (attestation inputs).

---

## H9. `build_notes() -> { hostname?: string, code_digest?: hex64, notes?: string }`

**Purpose.** Optional metadata for the audit row and bundle.

**Contract.**

* `code_digest` is a hex64 content hash of the orchestrator layer, if available.
* Absence is permitted (fields omitted or `null`).

**Determinism.** Not used in RNG/fingerprint.

**Failure mapping.**

* None (missing is tolerated).

**Used in.** S0.3 `rng_bootstrap_audit(...)`; S0.10 bundle context.

---

## H10. `read_bytes(path: string) -> bytes`

**Purpose.** Open an artefact path and return its **raw bytes** so that it is considered *opened* for inclusion in 𝓐 (S0.2 fingerprint set).

**Contract.**

* Returns the exact file bytes; **no** transcoding or normalization.
* Must succeed for paths provided by `numeric_policy_paths()` and any other governance artefacts L2 elects to open in S0.1.

**Determinism.** Byte-identical across reads within the run. Opening via this shim ensures `list_opened_artifacts()` captures the artefact for S0.2.

**Failure mapping.**

* Missing/IO → `F2:artifact_open_failed`.

**Used in.** S0.1 (to ensure `numeric_policy.json` and `math_profile_manifest.json` are included in 𝓐 before S0.2).

---

## What is **not** a host shim (use L0/L1 directly)

* `now_ns()` — provided by **L0/Batch F**; call it directly (do **not** re-implement a clock).
* `_passed.flag` builder & `publish_atomic` — **L0** only.
* RNG derivations, samplers, envelopes — **L0/L1** only.
* Partition verification (`verify_partition_keys`) — **L0** only.

---

## DoD checklist for §13

* Exactly **ten** shims are defined (H1–H10), each with **purpose, contract, determinism constraints, failure mapping,** and **usage site**.
* H3 explicitly requires the numeric policy/profile + all governance artefacts to be **opened before S0.2**, matching the fingerprint rules.
* No shim duplicates any L0/L1 behavior (no hashing, RNG, numeric policy, gates, or partition logic).
* All names match those referenced in the L2 orchestrator you froze, so implementers can wire without guessing.

---

# 14) Traceability — where to look when in doubt

Each S0 stage below tells you exactly **where** to verify behavior or bytes:

* **L2**: the orchestrator routine you call.
* **L1**: the *frozen* entrypoints that implement the step.
* **L0**: the underlying primitives (by batch and function).
* **Datasets & partitions**: the authoritative partition scope and embedded lineage keys.
* **Validation bundle**: the files where evidence is persisted.

> Tip: If something doesn’t line up at runtime, check in this order: **L2 call site → L1 entrypoint → L0 primitive → validation bundle**.

---

## S0.1 — Universe, symbols, authority (no persistence)

* **L2:** “S0.1 setup” block.
* **L1:** `load_and_validate_merchants` → `load_canonical_refs` → `authority_preflight` → `enforce_domains_and_map_channel` → `derive_merchant_u64` → `freeze_run_context`.
* **L0:** (none required—this stage only opens artefacts captured later by S0.2).
* **Datasets/Partitions:** none.
* **Validation bundle:** N/A. (These artefacts must appear in S0.2’s **artifact list**.)

---

## S0.2 — Hashes & identifiers

* **L2:** lineage computation block.
* **L1:** `compute_parameter_hash`, `compute_manifest_fingerprint`, `derive_run_id`.
* **L0:** Batch A hashing/encoding (`UER`, `LE64`, basename sorting, streaming SHA-256), Batch F `now_ns`.
* **Datasets/Partitions:** none; returns `parameter_hash`, `manifest_fingerprint`, `run_id`.
* **Validation bundle:** `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`, plus tables of parameter and artifact digests.

---

## S0.8 — Numeric policy & self-tests (gate)

* **L2:** numeric gate section (must pass before S0.3).
* **L1:** `set_numeric_env_and_verify`, `attest_libm_profile`, `run_self_tests_and_emit_attestation`.
* **L0:** Batch E (`sum_neumaier`, `total_order_key`), pinned libm profile per numeric policy.
* **Datasets/Partitions:** none (S0.8 computes an attestation **object** only).
* **Validation bundle:** `numeric_policy_attest.json` is **materialised by S0.10** into the fingerprint-scoped bundle.

---

## S0.3 — RNG bootstrap (audit only)

* **L2:** `rng_bootstrap_audit(seed, …)`.
* **L1:** `rng_bootstrap_audit`.
* **L0:** Batch B (`derive_master_material`), Batch D (`emit_rng_audit_row`).
* **Datasets/Partitions:** RNG **audit** under `seed, parameter_hash, run_id`; **no events** in S0.
* **Validation bundle:** N/A (bundle assembly happens in **S0.10**; S0.3 writes audit row only).

---

## S0.4 — GDP bucket attachment

* **L2:** call to `S0_4_attach_gdp_features`.
* **L1:** `S0_4_attach_gdp_features`.
* **L0:** none (pure lookups).
* **Datasets/Partitions:** none (feed-forward only).
* **Validation bundle:** N/A.

---

## S0.5 — Design matrices

* **L2:** dictionaries + designs block.
* **L1:** `build_dicts_and_assert_shapes`, `encode_onehots`, `build_design_vectors`, `S0_5_build_designs_stream`.
* **L0:** Batch E (Neumaier) where used by L1; otherwise pure encoding.
* **Datasets/Partitions:** none required by S0 (if materialized, they are parameter-scoped).
* **Validation bundle:** dictionary/shape evidence appears via S0.10 context if emitted there.

---

## S0.7 — Hurdle π diagnostic cache (optional)

* **L2:** conditional call guarded by `emit_hurdle_pi_cache`.
* **L1:** `S0_7_build_hurdle_pi_cache`.
* **L0:** Batch E `dot_neumaier`, `logistic_branch_stable`; Batch F `verify_partition_keys`.
* **Datasets/Partitions:** `hurdle_pi_probs` under `parameter_hash=…`; rows embed the same `parameter_hash`.
* **Validation bundle:** referenced in S0.10 context only (dataset itself is parameter-scoped).

---

## S0.6 — Cross-border eligibility

* **L2:** call to `S0_6_apply_eligibility_rules`.
* **L1:** `S0_6_apply_eligibility_rules` (writer `write_eligibility_flags` inside).
* **L0:** Batch F `verify_partition_keys`.
* **Datasets/Partitions:** `crossborder_eligibility_flags` under `parameter_hash=…`; rows embed the same `parameter_hash`.
* **Validation bundle:** referenced in S0.10 context only (dataset itself is parameter-scoped).

---

## S0.10 — Validation bundle (gate & publish)

* **L2:** `preflight_partitions_exist(parameter_hash, emit_hurdle_pi_probs)` → `assemble_validation_bundle` → `compute_gate_hash_and_publish_atomically`.
* **L1:** those three entrypoints.
* **L0:** `_passed.flag` builder (ASCII-sorted bytes, excluding the flag), `publish_atomic`.
* **Datasets/Partitions:** fingerprint-scoped directory with `_passed.flag`.
* **Validation bundle:** the bundle itself (this is where you verify the gate hash and atomic publish). `numeric_attest` is the exact object produced in **S0.8** and injected into the ctx here.

---

## Quick “where do I look?” summary

* **Lineage wrong?** L2 S0.2 call site → L1 `compute_*` functions → L0 hashing helpers → bundle `*_resolved.json`.
* **Numeric drift?** L2 barrier ordering → L1 S0.8 trio → bundle `numeric_policy_attest.json`.
* **RNG confusion?** L2 S0.3 call → L1 `rng_bootstrap_audit` → L0 `derive_master_material` & `emit_rng_audit_row` → audit JSONL under `{seed, parameter_hash, run_id}`.
* **Partition mismatch?** L1 writer (S0.6/S0.7) → L0 `verify_partition_keys` → dataset partition path vs row-embedded lineage.
* **Gate/publish issues?** L1 S0.10 → L0 `_passed.flag` builder & `publish_atomic` → fingerprint directory contents.

**Ctx note (naming consistency):** in S0.10 assembly, `artifacts` lists **names only** (`[artifact_basename]`); per S0.2, all SHA-256 values are carried in `artifact_digests` and `param_digests`. This separation is normative.

---