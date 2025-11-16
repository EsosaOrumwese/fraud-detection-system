# State 2B.S7 — Audits & CI gate

## 1. **Document metadata & status (Binding)**

**Component:** Layer-1 · Segment **2B** — **State-7 (S7)** · *Audits & CI gate*
**Document ID:** `seg_2B.s7.audit_and_ci`
**Version (semver):** `v1.0.2-alpha`
**Status:** `alpha` *(normative; semantics lock at `frozen`)*
**Owners:** Design Authority (DA): **Esosa Orumwese** · Review Authority (RA): **Layer-1 Governance**
**Effective date:** **2025-11-05 (UTC)**
**Canonical location:** `contracts/specs/l1/seg_2B/state.2B.s7.expanded.v1.0.2.txt`

**Authority chain (Binding).**
Schema packs are the **sole shape authorities**; the **Dataset Dictionary** governs ID→path/partitions/format; the **Artefact Registry** is metadata only. S7 inherits the 2B pack (S2/S3/S4 shapes + policy anchors), the Layer-1 pack (RNG envelope/core logs used only for optional log checks), and the 2A pack for `site_timezones` (context).   

**Normative cross-references (Binding).** S7 SHALL treat the following as authoritative:

* **Prior state evidence (2B.S0):** `s0_gate_receipt_2B` + `sealed_inputs_v1` at `[fingerprint]` prove the sealed inputs; S7 **does not** re-hash 1B. 
* **S2 — Alias mechanics (read-only):** `s2_alias_index` (`#/plan/s2_alias_index`) and `s2_alias_blob` (`#/binary/s2_alias_blob`) at `[seed,fingerprint]`; policy echo via `alias_layout_policy_v1`. 
* **S3 — Day effects (read-only):** `s3_day_effects` (`#/plan/s3_day_effects`) at `[seed,fingerprint]`. 
* **S4 — Group mixes (read-only):** `s4_group_weights` (`#/plan/s4_group_weights`) at `[seed,fingerprint]`. 
* **Policies (token-less; S0-sealed path+digest):** `alias_layout_policy_v1`, `route_rng_policy_v1`, and `virtual_edge_policy_v1` (present in the 2B Dictionary/Registry). 
* **Optional router logs (if present):** S5 `s5_selection_log` row (2B trace anchor) and S6 `s6_edge_log_row` (2B trace anchor); both are **run-scoped** and validated using the **Layer-1 RNG envelope/core logs** (event rows + `rng_trace_log`). *(S7 remains RNG-free; these are read only for evidence checks.)* 

**Segment invariants (Binding).**

* **Gate law:** **No PASS → No read** remains in force; S7 MUST see a valid S0 receipt & inventory for this fingerprint before any read. 
* **Catalogue discipline:** S7 resolves **only** by **Dataset Dictionary IDs** at the **exact partitions** declared (`[seed,fingerprint]` for S2/S3/S4; token-less policies by S0-sealed path+digest). **No literal paths; no network I/O.** 
* **RNG posture:** **RNG-free.** If S5/S6 logs are present, S7 *reads* Layer-1 RNG evidence (events/trace) but emits **no** RNG. (Event families and envelope live in the Layer-1 pack.)
* **Output identity:** S7 produces a single authoritative audit JSON `s7_audit_report` at **`[seed,fingerprint]`** (shape anchor in the 2B pack; see §6), **write-once** with path↔embed equality and idempotent re-emit (byte-identical). *(Dictionary governs its path family; Registry carries ownership/retention.)* 

> With this header, S7 is anchored to the same authorities and identity rails as S0–S6, and all cross-references to S2/S3/S4/policies/logs are explicit and Dictionary-resolvable.

---

## 2. **Purpose & scope (Binding)**

**Purpose.** S7 is the **audit & CI gate** for Segment 2B. It **does not route** or produce new plan surfaces; instead it **verifies** that the sealed artefacts from S2–S4 (and, if present, the S5/S6 diagnostics logs) are **coherent, reproducible, and within spec** before S8 packages the segment PASS bundle. S7 is **RNG-free**. It reads only **sealed, Dictionary-resolved** inputs and emits one authoritative **`s7_audit_report`** at `[seed,fingerprint]`.

**Scope (included).** S7 SHALL:

* **Validate S2 alias mechanics** against their contracts: index shape, blob contract, and **header↔blob parity** (e.g., `blob_sha256`); and perform a bounded, deterministic **decode round-trip** check on sampled merchants to confirm probabilities reconstruct within tolerance and Σ=1. Inputs are `s2_alias_index` and `s2_alias_blob` at **`[seed,fingerprint]`** with shapes `#/plan/s2_alias_index`, `#/binary/s2_alias_blob`. 
* **Validate S3/S4 day surface**: S3 day-grid equals S4 day-grid; **γ echo** holds (`s4.gamma == s3.gamma`); and per-merchant/day **Σ p_group = 1** within tolerance. Inputs are `s3_day_effects` and `s4_group_weights` at **`[seed,fingerprint]`** with shapes `#/plan/s3_day_effects`, `#/plan/s4_group_weights`.
* **(If logs present)** Verify **router evidence**: S5 `s5_selection_log` and S6 `s6_edge_log` must be **run-scoped** (`[seed,parameter_hash,run_id,utc_day]`), arrival-ordered, and schema-valid; reconcile RNG evidence via the Layer-1 core logs (exact two single-uniform events per S5 arrival; one per S6 virtual arrival; counters strictly monotone; streams match policy).
* **Emit** a fields-strict **`s7_audit_report`** (JSON) at **`[seed,fingerprint]`** containing: catalogue/inputs digests, per-validator PASS/WARN/FAIL, key metrics (merchant/group/day counts, decode max|Δ|, Σ-errors, draws expected/observed if logs), deterministic samples, and a summary. (Shape owned by a 2B validation anchor.) 

**Out of scope.** S7 **does not**: re-run routing (S5/S6); re-encode or mutate S2/S3/S4; read via literal paths or network; or publish the segment PASS bundle (that’s S8). Evidence logs remain **read-only**; the only S7 write is the audit report under `[seed,fingerprint]`.

**Determinism posture.** All checks are **RNG-free** and **replayable** under the same sealed inputs. Inputs are resolved **by Dataset Dictionary ID only** (S2/S3/S4 at `[seed,fingerprint]`; S5/S6 logs, if present, at `[seed,parameter_hash,run_id,utc_day]`; policies are token-less, selected by the S0-sealed path+digest). **No PASS → No read** is enforced via the 2B.S0 receipt and sealed inventory.

---

## 3. **Preconditions & sealed inputs (Binding)**

**3.1 Gate & run-identity (must hold before any read)**

* **S0 evidence present** for this `manifest_fingerprint`: `s0_gate_receipt_2B` **and** `sealed_inputs_v1` exist at `[fingerprint]` and validate against the 2B schema pack. S7 **relies** on this receipt; it **does not** re-hash 1B.   
* **S0-evidence rule.** Cross-layer/policy assets **must** appear in the **S0 sealed inventory** for this fingerprint; within-segment datasets (`s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights`) are **not** S0-sealed and **must** be resolved by **Dictionary ID** at exactly **`[seed,fingerprint]`** (no literal paths; no network I/O). 

**3.2 Inputs required by S7 (sealed; read-only)**
Resolve **by ID** under the run identity `{ seed, manifest_fingerprint }` established at S0. Partitions and shapes are governed by the **Dataset Dictionary** and **2B schema pack**:

* **S2 — Alias mechanics (plan + binary):**
  `s2_alias_index@seed={seed}/fingerprint={manifest_fingerprint}` (**shape:** `schemas.2B.yaml#/plan/s2_alias_index`),
  `s2_alias_blob@seed={seed}/fingerprint={manifest_fingerprint}` (**shape:** `#/binary/s2_alias_blob`). 

* **S3 — Day effects:**
  `s3_day_effects@seed={seed}/fingerprint={manifest_fingerprint}` (**shape:** `#/plan/s3_day_effects`). 

* **S4 — Group mixes:**
  `s4_group_weights@seed={seed}/fingerprint={manifest_fingerprint}` (**shape:** `#/plan/s4_group_weights`). 

* **(Optional) Router diagnostics (run-scoped):**
  `s5_selection_log@seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day={utc_day}` (**shape:** `schemas.2B.yaml#/trace/s5_selection_log_row`),
  `s6_edge_log@seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day={utc_day}` (**shape:** `#/trace/s6_edge_log_row`). 

* **Policies (token-less; S0-sealed path + digest):**
  `alias_layout_policy_v1`, `route_rng_policy_v1`, `virtual_edge_policy_v1`. (**Shapes:** `schemas.2B.yaml#/policy/*`.) 

**3.3 Selection & partition discipline (binding)**

* **Exact partitions:** S2/S3/S4 reads use **exactly** `[seed, fingerprint]`; optional S5/S6 logs use **exactly** `[seed, parameter_hash, run_id, utc_day]`. Policies are token-less and carry `partition = {}` in receipts; selection is by the **exact S0-sealed** `path` **and** `sha256_hex`. **Path↔embed equality** MUST hold wherever lineage is embedded.   

**3.4 Integrity & compatibility pre-checks (abort on failure)**

* **Catalogue discipline:** All reads resolve **by ID**; any literal path or non-sealed asset → `DICTIONARY_RESOLUTION_ERROR / PROHIBITED_LITERAL_PATH`. (Codes enumerated in §10.)
* **S2 parity:** `s2_alias_index.header.blob_sha256 == SHA256(raw bytes of s2_alias_blob)`; header echo (layout/endianness/alignment/bit-depth) coheres with `alias_layout_policy_v1`. 
* **S3/S4 grid & echo availability:** Day grid and γ vectors exist at the same `(seed,fingerprint)` and are schema-valid; Σ per-merchant/day will be checked in §7. 
* **Optional logs (if present):**
  • **S5** log rows conform to `#/trace/s5_selection_log_row`; partitions are `[seed, parameter_hash, run_id, utc_day]`; writer order = arrival order; `manifest_fingerprint` column **byte-equals** the run fingerprint; `created_utc` echoes S0 `verified_at_utc`.  
  • **S6** log rows conform to `#/trace/s6_edge_log_row`; partitions are `[seed, parameter_hash, run_id, utc_day]`; writer order = arrival order; `manifest_fingerprint` column obeys path↔embed equality; `created_utc` present per anchor.  
  • **RNG core logs (evidence reconciliation):** if S5/S6 logs are present, S7 **reads** Layer-1 `rng_audit_log` and `rng_trace_log` at `[seed, parameter_hash, run_id]` to reconcile draws and counters. (S7 itself is **RNG-free**.) 

**3.5 Prohibitions (binding)**

* **No network I/O.**
* **No literal paths.**
* **No mutation** of any input artefact; S7 writes only the audit report under `[seed, fingerprint]`, **write-once** and **atomic publish** (idempotent re-emit requires byte-identical bytes). 

> With these preconditions, S7’s inputs are **sealed, Dictionary-resolved, and immutable**; partitions and identity are unambiguous; and integrity hooks are in place to validate S2/S3/S4 (and optional S5/S6 evidence) deterministically before S8.

---

## 4. **Inputs & authority boundaries (Binding)**

**4.1 Authority chain (who governs what)**

* **JSON-Schema packs** are the **sole shape authorities**: 2B pack for S2/S3/S4 shapes, policy anchors, and the S5/S6 trace-row anchors; Layer-1 pack for RNG core-log/envelope shapes used only when logs are present.
* **Dataset Dictionary** is the **catalogue authority** (IDs → paths/partitions/format). S7 MUST resolve every input **by ID only** (no literal paths). 
* **Artefact Registry** is **metadata only** (ownership/licence/retention/notes); it does not change shapes or partitions (includes optional S5/S6 logs). 
* **Gate law (S0-evidence):** S7 reads **only** cross-layer/policy assets sealed in S0; all within-segment reads are **Dictionary-only** at exactly **`[seed,fingerprint]`**. S7 does **not** re-hash 1B. *(Gate evidence is checked in §3/§9.)*

**4.2 Inputs S7 SHALL read (read-only) and exactly how to select them**
All inputs are **sealed** and **Dictionary-resolved** under the run identity `{seed, manifest_fingerprint}` unless noted.

* **S2 alias mechanics** (plan + binary) @ **`[seed, fingerprint]`**
  IDs: `s2_alias_index` (shape: `schemas.2B.yaml#/plan/s2_alias_index`), `s2_alias_blob` (shape: `#/binary/s2_alias_blob`). 
* **S3 day effects** @ **`[seed, fingerprint]`**
  ID: `s3_day_effects` (shape: `#/plan/s3_day_effects`). 
* **S4 group mixes** @ **`[seed, fingerprint]`**
  ID: `s4_group_weights` (shape: `#/plan/s4_group_weights`). 
* **(Optional) Router diagnostics (run-scoped; only if registered/emitted)**
  • **S5 selection log** @ **`[seed, parameter_hash, run_id, utc_day]`** — row shape: `schemas.2B.yaml#/trace/s5_selection_log_row`.
  • **S6 edge log** @ **`[seed, parameter_hash, run_id, utc_day]`** — row shape: `#/trace/s6_edge_log_row`. 
* **Policies (token-less; S0-sealed path + digest)**
  IDs: `alias_layout_policy_v1`, `route_rng_policy_v1`, `virtual_edge_policy_v1` (all **single files**; `partition = {}` in S0 receipts). 

**4.3 Boundaries S7 SHALL enforce**

* **Dictionary-only resolution** with **exact partitions** as above. Any literal path or network I/O is a hard error. 
* **Path↔embed equality** wherever lineage appears (e.g., optional log rows must carry `manifest_fingerprint` that **byte-equals** the run fingerprint); logs must preserve **arrival order** in each run-scoped partition.
* **RNG posture:** S7 is **RNG-free**. When optional logs are present, S7 *reads* Layer-1 RNG evidence only to reconcile events/trace; shapes/partitions for `rng_audit_log` and `rng_trace_log` are owned by the **Layer-1 pack** under **`[seed, parameter_hash, run_id]`**. 
* **No writes** to any S2/S3/S4 dataset or to log partitions; S7 **only** writes the `s7_audit_report` at **`[seed, fingerprint]`** (write-once; atomic publish; idempotent re-emit = byte-identical). *(Report shape anchor is defined in the 2B pack’s validation section.)*

> Result: S7’s reads are **sealed, partition-exact, and authority-aligned** (2B shapes + Dictionary IDs), optional S5/S6 evidence is **run-scoped** and validated against the **Layer-1 envelope**, and S7’s only write is the **fingerprint-scoped audit report**.

---

## 5. **Outputs (datasets) & identity (Binding)**

**5.1 Authoritative egress (single product).**
S7 emits exactly **one** authoritative artefact per `(seed, manifest_fingerprint)`:

* **ID:** `s7_audit_report`
* **Path family (Dictionary-governed):**
  `data/layer1/2B/s7_audit_report/seed={seed}/fingerprint={manifest_fingerprint}/s7_audit_report.json`
* **Partitioning:** **`[seed, fingerprint]`** (no other tokens).
* **Shape authority:** `schemas.2B.yaml#/validation/s7_audit_report_v1` *(fields-strict; §6 defines required keys)*. 

**5.2 Identity & provenance (binding).**

* **Path↔embed equality:** Any lineage echoed inside the JSON (e.g., `seed`, `fingerprint`) **MUST** byte-equal the path tokens.
* **Created time:** `created_utc` **MUST** equal S0 receipt’s `verified_at_utc`. 
* **Catalogue resolution echo:** The report **MUST** include `catalogue_resolution{ dictionary_version, registry_version }` and an `inputs_digest` section that echoes the IDs, versions and `sha256_hex` of the sealed inputs used (S2/S3/S4/policies), taken from the S0 inventory. 

**5.3 Write policy (binding).**

* **Write-once + atomic publish:** Produce the JSON to a staging location, fsync, then **single atomic move** into the final path.
* **Idempotent re-emit:** Re-publishing the same `(seed, fingerprint)` is permitted **only** if the bytes are **identical**; otherwise a new run must not overwrite. 
* **Single writer:** Exactly one logical writer per `(seed, fingerprint)` partition.

**5.4 Non-authoritative emission (diagnostic).**
S7 **SHALL** also print a **STDOUT run-report** (diagnostic only). Persisted copies (if any) are **non-authoritative**; consumers **MUST NOT** depend on them. (Authoritative output is **only** `s7_audit_report` above.) 

**5.5 Prohibitions (binding).**

* S7 **MUST NOT** write to any fingerprint-scoped **plan/egress** surfaces (`s2_alias_*`, `s3_day_effects`, `s4_group_weights`) or any **run-scoped** router logs (`s5_selection_log`, `s6_edge_log`). Those are read-only inputs; S7’s only write is the audit report.

**5.6 Catalogue notes.**

* Ensure the **Dataset Dictionary** contains an entry for `s7_audit_report` with the partition law **`[seed, fingerprint]`**, format `json`, and `schema_ref: schemas.2B.yaml#/validation/s7_audit_report_v1`. The **Artefact Registry** should mirror it (metadata, owners, write_once/atomic flags). *(Dictionary = ID→paths/partitions/format; Registry = metadata only.)*

> Net: S7 produces a **single, fingerprint-scoped, fields-strict JSON report** under Dictionary control, with strict path↔embed equality, S0-derived provenance, and write-once/atomic publish. No other datasets are written.

---

## 6. **Dataset shapes & schema anchors (Binding)**

**6.1 Shape authority**
JSON-Schema is the **sole** shape authority. S7 binds to the **2B schema pack** for S2/S3/S4 shapes, policy anchors, and (when present) S5/S6 trace rows; and to the **Layer-1 schema pack** for RNG core-log/envelope shapes used only when optional logs are validated. The **Dataset Dictionary** governs ID→path/partitions/format; the **Artefact Registry** is metadata only. 

---

**6.2 Output (authoritative) — `s7_audit_report_v1`**
**Anchor (2B pack):** `schemas.2B.yaml#/validation/s7_audit_report_v1` *(fields-strict).*
**Required top-level keys (no extras):**

* `component` (`"2B.S7"`)
* `fingerprint` (`hex64`), `seed` (`uint64`)
* `created_utc` (`rfc3339_micros`) — **echo S0.verified_at_utc**
* `catalogue_resolution` → `{ dictionary_version: <semver>, registry_version: <semver> }`
* `inputs_digest` → echo of sealed inputs (IDs, version_tags, `sha256_hex`, path, partition) for **S2/S3/S4** and **policies** (from S0 inventory)
* `checks[]` → array of `{ id, status: "PASS"|"FAIL"|"WARN", codes: [string], context?: object }`
* `metrics` → `{ merchants_total, groups_total, days_total, selections_checked?, draws_expected?, draws_observed?, alias_decode_max_abs_delta?, max_abs_mass_error_s4? }`
* `summary` → `{ overall_status: "PASS"|"FAIL", warn_count: int, fail_count: int }`

*(Types re-use Layer-1 `$defs` for `hex64`, `uint64`, timestamps.)*

**Partition law (Dictionary authority):** `[seed, fingerprint]` (see §5). Path↔embed equality is **binding**. 

---

**6.3 Referenced input anchors (read-only)**
S7 SHALL resolve and consume **exactly** these shapes by **Dictionary ID**:

* **S2 alias mechanics:**
  `schemas.2B.yaml#/plan/s2_alias_index` · `#/binary/s2_alias_blob` — both at `[seed,fingerprint]`. 
* **S3 day effects:** `#/plan/s3_day_effects` — `[seed,fingerprint]`. 
* **S4 group mixes:** `#/plan/s4_group_weights` — `[seed,fingerprint]`. 
* **Policies (token-less; S0-sealed path+digest):** `#/policy/alias_layout_policy_v1`, `#/policy/route_rng_policy_v1`, `#/policy/virtual_edge_policy_v1`. *(Single files; `partition={}`.)* 
* **(Optional) Router diagnostics (run-scoped):**
  S5 log row → `schemas.2B.yaml#/trace/s5_selection_log_row` *(if registered)*;
  S6 edge log row → `#/trace/s6_edge_log_row` *(if registered)*. *(Both are **run-scoped** and validated using the Layer-1 RNG envelope/core logs.)* 

---

**6.4 RNG evidence shapes (only if S5/S6 logs are present)**
S7 is **RNG-free**; it only *reads* Layer-1 evidence to reconcile draws/counters:

* **Envelope & core logs (Layer-1 pack):** `schemas.layer1.yaml#/$defs/rng_envelope`, `#/rng/core/rng_audit_log`, `#/rng/core/rng_trace_log` — partitions **`[seed, parameter_hash, run_id]`**; S5 uses **two** single-uniform events/arrival; S6 uses **one** single-uniform/virtual arrival. 

---

**6.5 Common `$defs` reused**
From **`schemas.layer1.yaml`**: `hex64`, `uint64`, `id64`, `rfc3339_micros`, `iana_tzid`, `iso2`.
From **`schemas.2B.yaml`**: `$defs.partition_kv` with **`minProperties: 0`** (token-less assets allowed in receipts/inventory). 

---

**6.6 Format & storage (Dictionary authority)**

* **`s7_audit_report`**:
  Path → `data/layer1/2B/s7_audit_report/seed={seed}/fingerprint={manifest_fingerprint}/s7_audit_report.json` · **Partitioning:** `[seed,fingerprint]` · **Format:** `json` · **Schema-ref:** `schemas.2B.yaml#/validation/s7_audit_report_v1`.
* **Referenced inputs:** `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights` at `[seed,fingerprint]`; policies are token-less files selected by **S0-sealed** path+digest.  

---

**6.7 Structural & identity constraints (binding)**

* **Fields-strict**: `s7_audit_report` must contain **only** the keys defined in the anchor.
* **Path↔embed equality** wherever lineage appears (e.g., `seed`, `fingerprint`, `created_utc`).
* **Created-time provenance**: `created_utc` **equals** S0 `verified_at_utc`.
* **No extra writes**: S7 writes **only** the audit report; logs (if present) are read-only and run-scoped. 

> These anchors make S7’s report **authoritative and replayable** while keeping all inputs **sealed & Dictionary-resolved** and any optional log checks aligned with the **Layer-1 RNG envelope**.

---

## 7. **Deterministic checks (RNG-free) (Binding)**

> S7 performs **no RNG**. All checks are pure reads over sealed artefacts resolved by **Dataset Dictionary ID** at the exact partitions (S2/S3/S4 at `[seed,fingerprint]`; optional S5/S6 logs at `[seed,parameter_hash,run_id,utc_day]`). Shapes come from the 2B pack (plan/binary/policies/trace), and—if logs are present—the **Layer-1** envelope/core logs are read for reconciliation.

### A. Alias mechanics (S2) — **index & blob coherence + decode round-trip**

**Inputs:** `s2_alias_index@{seed,fingerprint}`, `s2_alias_blob@{seed,fingerprint}`, `alias_layout_policy_v1` (token-less). Shapes: `#/plan/s2_alias_index`, `#/binary/s2_alias_blob`, `#/policy/alias_layout_policy_v1`. 

1. **Schema/contract validity (Abort on fail).**
   Both artefacts validate against their anchors; required header keys present. `quantised_bits`, `endianness`, `alignment_bytes` exist and are well-typed. 
2. **Header↔blob parity (Abort).**
   Recompute `SHA256(blob)` and require `index.header.blob_sha256 == sha256_hex`. Layout/bit-depth/endianness/alignment in the index **echo** the policy. 
3. **Offsets & alignment (Abort).**
   For each merchant slice in the index: offsets are **sorted**, **non-overlapping**, within blob bounds, and `offset % alignment_bytes == 0`. (Length > 0.) 
4. **Deterministic decode round-trip (Abort on exceed).**
   For a **bounded deterministic sample** of merchants (pick the **K** with lowest ASCII-lex `merchant_id`, **K = min(32, #merchants)**):
   • Parse their alias arrays from the blob using index offsets.
   • Compute implied probabilities **p̂** from `(prob[], alias[])` and require `Σ p̂ = 1` within tolerance.
   • If the policy declares a decode tolerance (e.g., `quantisation_epsilon`), require `max_i |p̂_i − p_i^enc| ≤ ε_q`; otherwise enforce **binary64** numerical tolerance on the Σ=1 law only.
   • Record `alias_decode_max_abs_delta` into the report’s `metrics`. 

### B. Day effects & mixes (S3/S4) — **grid equality, γ echo, normalisation**

**Inputs:** `s3_day_effects@{seed,fingerprint}`, `s4_group_weights@{seed,fingerprint}`. Shapes: `#/plan/s3_day_effects`, `#/plan/s4_group_weights`.

1. **Day-grid equality (Abort).**
   The set of `(merchant_id, utc_day)` in S4 equals the set in S3 (no missing/multi-map). 
2. **γ echo (Abort).**
   Join S4 to S3 on `(merchant_id, utc_day, tz_group_id)` and require `S4.gamma == S3.gamma` for every row (binary64 equality). 
3. **Group normalisation (Abort).**
   For each `(merchant_id, utc_day)`, require `Σ_{tz_group} S4.p_group = 1` within binary64 tolerance; store `max_abs_mass_error_s4` in `metrics`. Writer/PK discipline (unique, ordered by `[merchant_id, utc_day, tz_group_id]`) is upheld. 

> *Note:* If you also elect to supply `s1_site_weights` in the sealed inventory, S7 **may** recompute and spot-check S4 `base_share` aggregation vs S1 (Σ base_share = 1 per merchant); otherwise this sub-check is skipped.

### C. Router evidence (S5/S6) — **only if logs are present & registered**

**Inputs (optional):**
• S5 log rows at `s5_selection_log@{seed,parameter_hash,run_id,utc_day}` (row shape `#/trace/s5_selection_log_row`).
• S6 log rows at `s6_edge_log@{seed,parameter_hash,run_id,utc_day}` (row shape `#/trace/s6_edge_log_row`).
• Layer-1 **core logs**: `rng_audit_log`, `rng_trace_log` at `{seed,parameter_hash,run_id}` for reconciliation.

1. **Trace row shape & lineage (Abort).**
   Rows validate against their anchors; partitions are exactly `[seed,parameter_hash,run_id,utc_day]`; `manifest_fingerprint` **byte-equals** the run fingerprint; **arrival order** preserved; write-once.
2. **S5 draw law (Abort).**
   Reconcile that **two** single-uniform events per selection were emitted (`alias_pick_group` → `alias_pick_site`), in order, with one `rng_trace_log` append **after each** event append; counters strictly monotone, no wrap; streams match `route_rng_policy_v1`. *(S5 spec; Layer-1 envelope).* 
3. **S6 draw law (Abort).**
   Reconcile **one** single-uniform `cdn_edge_pick` per **virtual** arrival, with one trace append after each event; counters strictly monotone; streams match `route_rng_policy_v1`. *(S6 spec; Layer-1 envelope).* 
4. **Mapping & attribute coherence (Abort if violated).**
   • **S5:** for a bounded, deterministic sample of rows (min(1 000, 1%) per `(merchant, day)`), assert the log’s `tz_group_id` equals the site’s time-zone group if `site_timezones@{seed,fingerprint}` is available; if not available, record `WARN` that external mapping could not be verified.
   • **S6:** for every sampled row, ensure `ip_country` is ISO-3166-1 alpha-2 and `edge_lat ∈ [−90,90]`, `edge_lon ∈ (−180,180]` (domain from S6 trace anchor); attributes exist for the chosen `edge_id`. 

### D. Report assembly (authoritative, RNG-free)

**Output:** `s7_audit_report@{seed,fingerprint}` (shape `#/validation/s7_audit_report_v1`). The report SHALL include:
• `catalogue_resolution`; `inputs_digest` echoing sealed S2/S3/S4/policies (IDs, version_tags, sha256_hex, path, partition).
• `checks[]` with PASS/WARN/FAIL and code(s) per sub-check above.
• `metrics` with: `{ merchants_total, groups_total, days_total, selections_checked?, draws_expected?, draws_observed?, alias_decode_max_abs_delta?, max_abs_mass_error_s4? }`.
• `summary{ overall_status, warn_count, fail_count }`. *(Identity rules: path↔embed equality on `seed`/`fingerprint`; `created_utc =` S0.verified_at_utc.)* 

> These checks make S7 a **replayable, RNG-free** gate: S2 alias **parity + decode**, S3/S4 **grid/echo/Σ laws**, and—when present—S5/S6 **RNG budgets, counters, ordering, and coherence** against the Layer-1 envelope and the 2B trace anchors.

---

## 8. **Identity, partitions, ordering & merge discipline (Binding)**

**8.1 Lineage tokens & where they live (authoritative)**

* **Read surfaces (plan/egress):** `{ seed, manifest_fingerprint }` — used by **S2/S3/S4** inputs S7 reads:
  `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights` **at exactly** `seed={seed}/fingerprint={manifest_fingerprint}` per the Dictionary. 
* **Optional router logs (evidence only):** `{ seed, parameter_hash, run_id, utc_day }` — if present, S5 `s5_selection_log` and S6 `s6_edge_log` are **run-scoped** log partitions validated against the Layer-1 RNG envelope/core logs. 
* **S7 output (authoritative):** `s7_audit_report` is **fingerprint-scoped** at `data/layer1/2B/s7_audit_report/seed={seed}/fingerprint={manifest_fingerprint}/…` (Dictionary governs the path family; schema governs shape). 

**8.2 Partition selection (binding)**

* S7 **MUST** resolve all inputs **by Dataset Dictionary ID** with **exact partitions**:
  `…/seed={seed}/fingerprint={manifest_fingerprint}` for S2/S3/S4; token-less **policies** (e.g., `alias_layout_policy_v1`, `route_rng_policy_v1`, `virtual_edge_policy_v1`) are selected by the **exact S0-sealed** `path` + `sha256_hex`. **No literal paths. No network I/O.** 
* Optional S5/S6 logs (if present) **must** be selected at `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day={utc_day}` with their registered schema anchors. 

**8.3 Path↔embed equality (binding)**
Where lineage appears **both** in the path and in the payload, values **MUST** be byte-equal to the path tokens:

* In `s7_audit_report`, JSON fields `seed` and `fingerprint` equal their path tokens; `created_utc` equals S0’s `verified_at_utc`. 
* In optional S5/S6 logs, the `manifest_fingerprint` column equals the run fingerprint for those log partitions. 

**8.4 Writer order & file layout (binding)**

* **S7 audit report:** one JSON file per `(seed, fingerprint)` partition. Inside the JSON, arrays (e.g., `checks[]`) **SHOULD** be ordered deterministically (e.g., by validator id) to guarantee idempotent bytes.
* **Optional logs:** S7 does not write them, but when present they **must** preserve arrival order within each run-scoped partition; S7 enforces this in validation. 

**8.5 Immutability & atomic publish (binding)**

* `s7_audit_report` is **write-once** with a **single atomic move** into the final path; any retry **MUST** be byte-identical or target a new partition. Single logical writer per `(seed, fingerprint)`. (Registry carries write-once/atomic metadata; Dictionary governs the path family.) 

**8.6 Merge discipline (binding)**

* **No cross-partition merges.** Never merge reports across different seeds or fingerprints. If compaction is needed, publish a brand-new file atomically with **identical bytes** (idempotent rule).
* **No writes** to S2/S3/S4 inputs or to S5/S6 log partitions (they are read-only for S7). 

**8.7 Evidence hooks (what validators check)**
S7’s validator set asserts: exact **Dictionary partitions**, **path↔embed** equality, **arrival-order** in optional logs, and **write-once/atomic** publish + idempotent re-emit for the audit report. These mirror the identity and catalogue laws already established for 2B.

> Net: S7’s only write is a **fingerprint-scoped, fields-strict** audit JSON under Dictionary control; all reads are **sealed and partition-exact**; any optional router evidence is **run-scoped** and validated against the Layer-1 RNG envelope and its partitions.

---

## 9. **Acceptance criteria (validators) (Binding)**

> Every validator below is **mandatory**. S7 is **RNG-free**; when S5/S6 logs are present, S7 only **reads** Layer-1 evidence (events + trace) to reconcile counts/counters/ordering. Inputs are resolved **by Dataset Dictionary ID** at exact partitions; shapes come from the **2B pack** (plan/binary/policies/trace), and Layer-1 only for RNG envelope/core logs.

**V-01 — Gate evidence present (S0)**
**Check:** `s0_gate_receipt_2B` **and** `sealed_inputs_v1` exist at `[fingerprint]` and are schema-valid.
**Fail →** ⟨2B-S7-001 S0_RECEIPT_MISSING⟩. 

**V-02 - S0-evidence & Dictionary-only resolution**
**Check:** All cross-layer/policy assets appear in the **S0 sealed inventory** for this fingerprint; all within-segment inputs (`s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights`) resolve **by Dataset Dictionary ID** at exactly **`[seed,fingerprint]`** (no literals / no network).
**Fail →** ⟨2B-S7-020 DICTIONARY_RESOLUTION_ERROR⟩ / ⟨2B-S7-021 PROHIBITED_LITERAL_PATH⟩ / ⟨2B-S7-023 NETWORK_IO_ATTEMPT⟩. 

**V-03 — Exact partitions & policy selection**
**Check:** S2/S3/S4 are read at **`[seed,fingerprint]`**; S5/S6 logs (if present) at **`[seed,parameter_hash,run_id,utc_day]`**; token-less policies are selected by **S0-sealed** `path+sha256_hex`.
**Fail →** ⟨2B-S7-070 PARTITION_SELECTION_INCORRECT⟩.

---

### A. S2 alias mechanics (index + blob)  *(read-only)*

**V-04 — Index & blob schema validity**
**Check:** `s2_alias_index` validates `#/plan/s2_alias_index`; `s2_alias_blob` validates `#/binary/s2_alias_blob`; required header fields present.
**Fail →** ⟨2B-S7-200 INDEX_SCHEMA_INVALID⟩ / ⟨2B-S7-201 BLOB_CONTRACT_VIOLATION⟩. 

**V-05 — Header↔blob parity & policy echo**
**Check:** `SHA256(blob) == index.header.blob_sha256`; header’s `layout_version/endianness/alignment_bytes/quantised_bits` **echo** `alias_layout_policy_v1`.
**Fail →** ⟨2B-S7-202 BLOB_DIGEST_MISMATCH⟩ / ⟨2B-S7-205 BIT_DEPTH_INCOHERENT⟩. 

**V-06 — Offsets, bounds & alignment**
**Check:** Merchant slices are **sorted**, **non-overlapping**, within blob bounds; `offset % alignment_bytes == 0`; `length > 0`.
**Fail →** ⟨2B-S7-203 OFFSET_OVERLAP⟩ / ⟨2B-S7-204 ALIGNMENT_ERROR⟩. 

**V-07 — Deterministic decode round-trip**
**Check:** For a deterministic sample of merchants (e.g., lowest ASCII-lex K; K≤32): decode `(prob,alias)` and require `Σ p̂ = 1` (binary64 tolerance); if policy declares `quantisation_epsilon`, also require `max|p̂−p_enc| ≤ ε_q`. Record `alias_decode_max_abs_delta` in report `metrics`.
**Fail →** ⟨2B-S7-206 ALIAS_DECODE_INCOHERENT⟩. 

---

### B. S3/S4 day surface *(read-only)*

**V-08 — Day-grid equality**
**Check:** Sets of `(merchant_id, utc_day)` in S3 and S4 are **identical**.
**Fail →** ⟨2B-S7-300 DAY_GRID_MISMATCH⟩. 

**V-09 — γ echo**
**Check:** Join on `(merchant_id, utc_day, tz_group_id)`; **S4.gamma == S3.gamma** (binary64).
**Fail →** ⟨2B-S7-301 GAMMA_ECHO_MISMATCH⟩. 

**V-10 — Group normalisation (Σ=1)**
**Check:** For each `(merchant_id, utc_day)`, `Σ_g S4.p_group = 1` within binary64 tolerance; write `max_abs_mass_error_s4` to report `metrics`.
**Fail →** ⟨2B-S7-302 S4_NORMALISATION_FAILED⟩. 

**V-11 — (Optional) Base-share echo vs S1**
**Check:** If `s1_site_weights` is present in the S0 inventory, recompute and spot-check S4 base-share aggregation (Σ base_share per merchant = 1).
**Fail →** ⟨2B-S7-303 JOIN_KEY_MISMATCH⟩ (or corresponding base-share code). *(Skip if S1 not sealed.)*

---

### C. Router evidence *(only if logs are present & registered)*

**V-12 — Trace row shape & lineage (S5/S6 logs)**
**Check:** Rows validate (`#/trace/s5_selection_log_row` / `#/trace/s6_edge_log_row`); partitions are **`[seed,parameter_hash,run_id,utc_day]`**; `manifest_fingerprint` **byte-equals** the run fingerprint; **arrival order** preserved; write-once.
**Fail →** ⟨2B-S7-400 TRACE_SCHEMA_INVALID⟩ / ⟨2B-S7-401 TRACE_ORDER_VIOLATION⟩ / ⟨2B-S7-503 PATH_EMBED_MISMATCH⟩. 

**V-13 — S5 RNG budgets & ordering**
**Check:** Exactly **two** single-uniform events per selection (`alias_pick_group` → `alias_pick_site`), in order; **one** `rng_trace_log` append **after each** event; counters strictly monotone; no wrap; streams match `route_rng_policy_v1`.
**Fail →** ⟨2B-S7-402 RNG_DRAWS_MISMATCH⟩ / ⟨2B-S7-403 RNG_COUNTER_NOT_MONOTONE⟩ / ⟨2B-S7-404 RNG_COUNTER_WRAP⟩ / ⟨2B-S7-405 RNG_STREAM_MISCONFIGURED⟩. 

**V-14 — S6 RNG budget**
**Check:** Exactly **one** `cdn_edge_pick` per **virtual** arrival; **one** trace append **after** each event; counters monotone/no wrap; streams match policy.
**Fail →** ⟨2B-S7-402⟩ / ⟨2B-S7-403⟩ / ⟨2B-S7-404⟩ / ⟨2B-S7-405⟩. 

**V-15 — Mapping & attribute coherence**
**Check:**
• **S5:** sampled rows map `site_id → tz_group_id` via 2A `site_timezones@{seed,fingerprint}` (when available); must equal logged `tz_group_id`.
• **S6:** sampled rows carry `ip_country` (ISO-2), `edge_lat ∈ [−90,90]`, `edge_lon ∈ (−180,180]`; attributes exist for chosen `edge_id`.
**Fail →** ⟨2B-S7-410 GROUP_SITE_MISMATCH⟩ / ⟨2B-S7-411 EDGE_ATTR_MISSING⟩. 

**V-16 — Evidence reconciliation (run-scoped)**
**Check:** For each run, `rng_trace_log.total_draws == (2×#S5_selections + #S6_virtuals)` and equals the sum across relevant event families.
**Fail →** ⟨2B-S7-402 RNG_DRAWS_MISMATCH⟩. 

---

### D. Report identity & immutability

**V-17 — Report shape & provenance**
**Check:** `s7_audit_report` validates `#/validation/s7_audit_report_v1`; `seed`/`fingerprint` **byte-equal** path tokens; `created_utc` equals S0 `verified_at_utc`; `catalogue_resolution` populated; `inputs_digest` echoes sealed inputs (IDs, version_tags, sha256_hex, path, partition).
**Fail →** ⟨2B-S7-500 REPORT_SCHEMA_INVALID⟩ / ⟨2B-S7-503 PATH_EMBED_MISMATCH⟩.

**V-18 — Write-once, atomic publish, idempotent re-emit**
**Check:** The report is **write-once**; published via **atomic move**; any retry is byte-identical (otherwise new partition). Single logical writer per `(seed,fingerprint)`.
**Fail →** ⟨2B-S7-501 IMMUTABLE_OVERWRITE⟩ / ⟨2B-S7-502 NON_IDEMPOTENT_REEMIT⟩. 

---

### Inputs/anchors these validators rely on (for auditors)

* **2B pack (shapes):** `#/plan/s2_alias_index`, `#/binary/s2_alias_blob`, `#/plan/s3_day_effects`, `#/plan/s4_group_weights`, `#/policy/*`, `#/trace/s5_selection_log_row`, `#/trace/s6_edge_log_row`, `#/validation/s7_audit_report_v1`.
* **Layer-1 pack (RNG evidence shapes):** `#/rng/core/rng_audit_log`, `#/rng/core/rng_trace_log` + `#/$defs/rng_envelope` (run-scoped). 

> Passing **V-01…V-18** proves S7 reads only **sealed, partition-exact** inputs, confirms **S2/S3/S4** coherence and normalisation, and—when logs are present—verifies **RNG budgets, counters, ordering, and mapping/attribute coherence**; it then writes a single, **fields-strict** `s7_audit_report` with S0-anchored provenance.

---

## 10. **Failure modes & canonical error codes (Binding)**

> **Severity classes:** **Abort** (hard stop; S7 MUST NOT continue) and **Warn** (record + continue). Codes are **stable identifiers**; meanings MUST NOT change within a major. Shapes/partitions referenced below are governed by the 2B schema pack, the Layer-1 RNG pack (for optional logs), and the Dataset Dictionary.

### 10.1 Gate & catalogue discipline

* **2B-S7-001 — S0_RECEIPT_MISSING** · *Abort*
  **Trigger:** `s0_gate_receipt_2B` and/or `sealed_inputs_v1` absent/invalid at `[fingerprint]`.
  **Detect:** V-01. **Remedy:** publish valid S0 for this fingerprint; fix schema/partition. 

* **2B-S7-020 — DICTIONARY_RESOLUTION_ERROR** · *Abort*
  **Trigger:** Any input not resolved by **Dataset Dictionary ID** (wrong ID/path family/format).
  **Detect:** V-02/V-03. **Remedy:** resolve by ID only; correct ID/path family. 

* **2B-S7-021 — PROHIBITED_LITERAL_PATH** · *Abort*
  **Trigger:** Literal filesystem/URL read attempted.
  **Detect:** V-02/V-03. **Remedy:** replace with Dictionary ID resolution.

* **2B-S7-023 — NETWORK_IO_ATTEMPT** · *Abort*
  **Trigger:** Any network access during S7.
  **Detect:** V-02/V-03. **Remedy:** consume only sealed artefacts.

* **2B-S7-070 — PARTITION_SELECTION_INCORRECT** · *Abort*
  **Trigger:** Partitioned reads not **exactly** `[seed,fingerprint]` (S2/S3/S4) or optional logs not `[seed,parameter_hash,run_id,utc_day]`; token-less policies not selected by **S0-sealed** `path+sha256_hex`.
  **Detect:** V-03. **Remedy:** fix tokens/selection semantics.

---

### 10.2 S2 alias integrity & decode

* **2B-S7-200 — INDEX_SCHEMA_INVALID** · *Abort*
  **Trigger:** `s2_alias_index` fails `#/plan/s2_alias_index`.
  **Detect:** V-04. **Remedy:** republish index per anchor. 

* **2B-S7-201 — BLOB_CONTRACT_VIOLATION** · *Abort*
  **Trigger:** `s2_alias_blob` fails `#/binary/s2_alias_blob`.
  **Detect:** V-04. **Remedy:** republish blob per anchor. 

* **2B-S7-202 — BLOB_DIGEST_MISMATCH** · *Abort*
  **Trigger:** `SHA256(blob) ≠ index.header.blob_sha256`.
  **Detect:** V-05. **Remedy:** fix blob or header; republish. 

* **2B-S7-203 — OFFSET_OVERLAP** · *Abort*
  **Trigger:** Merchant slices overlap / out of order / out of bounds.
  **Detect:** V-06. **Remedy:** correct offsets/lengths; republish. 

* **2B-S7-204 — ALIGNMENT_ERROR** · *Abort*
  **Trigger:** `offset % alignment_bytes ≠ 0` or `length ≤ 0`.
  **Detect:** V-06. **Remedy:** fix alignment/lengths. 

* **2B-S7-205 — BIT_DEPTH_INCOHERENT** · *Abort*
  **Trigger:** `quantised_bits`/layout/endianness mis-echo policy.
  **Detect:** V-05. **Remedy:** fix header/policy echo. 

* **2B-S7-206 — ALIAS_DECODE_INCOHERENT** · *Abort*
  **Trigger:** Round-trip decode fails: Σp̂≠1 (b64 tol) or `max|p̂−p_enc|>ε_q` when declared.
  **Detect:** V-07. **Remedy:** correct encode/policy; republish. 

---

### 10.3 S3/S4 day surface

* **2B-S7-300 — DAY_GRID_MISMATCH** · *Abort*
  **Trigger:** `(merchant_id,utc_day)` sets differ between S3 and S4.
  **Detect:** V-08. **Remedy:** fix upstream generation. 

* **2B-S7-301 — GAMMA_ECHO_MISMATCH** · *Abort*
  **Trigger:** `S4.gamma ≠ S3.gamma` per `(merchant,day,group)`.
  **Detect:** V-09. **Remedy:** correct γ echo. 

* **2B-S7-302 — S4_NORMALISATION_FAILED** · *Abort*
  **Trigger:** per-day Σ p_group ≠ 1 (b64 tol).
  **Detect:** V-10. **Remedy:** fix S4 normalisation. 

* **2B-S7-303 — JOIN_KEY_MISMATCH** · *Abort*
  **Trigger:** S3/S4 join not 1:1 on `(merchant,day)` (or base-share echo fails when enabled).
  **Detect:** V-11. **Remedy:** fix join/base-share aggregation.

* **2B-S7-304 — BASE_SHARE_INCOHERENT** · *Abort* *(only if base-share echo is enabled)*
  **Trigger:** Σ base_share per merchant ≠ 1.
  **Detect:** V-11. **Remedy:** correct S1→S4 aggregation.

---

### 10.4 Router evidence (only if logs present & registered)

* **2B-S7-400 — TRACE_SCHEMA_INVALID** · *Abort*
  **Trigger:** S5/S6 log rows fail `#/trace/*` anchors.
  **Detect:** V-12. **Remedy:** fix emitters; regenerate logs. 

* **2B-S7-401 — TRACE_ORDER_VIOLATION** · *Abort*
  **Trigger:** Arrival order not preserved within a log partition.
  **Detect:** V-12. **Remedy:** fix writer ordering.

* **2B-S7-402 — RNG_DRAWS_MISMATCH** · *Abort*
  **Trigger:** Draw counts don’t equal `2×#S5 + #S6_virtual`; or event counts disagree with trace totals.
  **Detect:** V-13/V-14/V-16. **Remedy:** emit exact budgets; reconcile trace. 

* **2B-S7-403 — RNG_COUNTER_NOT_MONOTONE** · *Abort*
  **Trigger:** `after−before ≠ 1` or counters reused.
  **Detect:** V-13/V-14. **Remedy:** fix counter mapping.

* **2B-S7-404 — RNG_COUNTER_WRAP** · *Abort*
  **Trigger:** 128-bit counter overflow/wrap.
  **Detect:** V-13/V-14. **Remedy:** adjust ranges; never reuse counters.

* **2B-S7-405 — RNG_STREAM_MISCONFIGURED** · *Abort*
  **Trigger:** Event stream/substreams don’t match `route_rng_policy_v1`.
  **Detect:** V-13/V-14. **Remedy:** bind to policy-declared streams.

* **2B-S7-410 — GROUP_SITE_MISMATCH** · *Abort*
  **Trigger:** Logged `tz_group_id` disagrees with 2A mapping for `site_id` (when mapping available).
  **Detect:** V-15. **Remedy:** fix router mapping or 2A reference.

* **2B-S7-411 — EDGE_ATTR_MISSING** · *Abort*
  **Trigger:** S6 log row’s `edge_id` lacks ISO2/lat/lon or values outside domain.
  **Detect:** V-15. **Remedy:** complete policy attributes.

---

### 10.5 Report identity, immutability & publish

* **2B-S7-500 — REPORT_SCHEMA_INVALID** · *Abort*
  **Trigger:** `s7_audit_report` fails `#/validation/s7_audit_report_v1`.
  **Detect:** V-17. **Remedy:** fix shape/fields-strict. 

* **2B-S7-501 — IMMUTABLE_OVERWRITE** · *Abort*
  **Trigger:** Target `[seed,fingerprint]` already has a report and bytes differ.
  **Detect:** V-18. **Remedy:** write-once only; otherwise new partition. 

* **2B-S7-502 — NON_IDEMPOTENT_REEMIT** · *Abort*
  **Trigger:** Re-emit not byte-identical for same inputs.
  **Detect:** V-18. **Remedy:** ensure exact bytes; else new partition.

* **2B-S7-503 — PATH_EMBED_MISMATCH** · *Abort*
  **Trigger:** Embedded `seed`/`fingerprint`/`created_utc` not equal to path tokens or S0 receipt.
  **Detect:** V-17. **Remedy:** echo path tokens; use S0 timestamp. 

* **2B-S7-504 — ATOMIC_PUBLISH_FAILED** · *Abort*
  **Trigger:** Staging/rename not atomic, or post-publish verification failed.
  **Detect:** V-18. **Remedy:** stage → fsync → single atomic move; verify final bytes.

---

### 10.6 Validator → code map (authoritative)

| Validator (from §9)                          | Codes on fail                              |
| -------------------------------------------- | ------------------------------------------ |
| **V-01 Gate evidence present**               | 2B-S7-001                                  |
| **V-02 S0-evidence & Dictionary-only**       | 2B-S7-020, 2B-S7-021, 2B-S7-023            |
| **V-03 Exact partitions & policy selection** | 2B-S7-070                                  |
| **V-04 Index/blob schema validity**          | 2B-S7-200, 2B-S7-201                       |
| **V-05 Header↔blob parity & policy echo**    | 2B-S7-202, 2B-S7-205                       |
| **V-06 Offsets/bounds/alignment**            | 2B-S7-203, 2B-S7-204                       |
| **V-07 Decode round-trip**                   | 2B-S7-206                                  |
| **V-08 Day-grid equality**                   | 2B-S7-300                                  |
| **V-09 γ echo**                              | 2B-S7-301                                  |
| **V-10 Σ p_group = 1**                       | 2B-S7-302                                  |
| **V-11 Base-share echo (opt.)**              | 2B-S7-303, 2B-S7-304                       |
| **V-12 Trace row shape & lineage**           | 2B-S7-400, 2B-S7-401, 2B-S7-503            |
| **V-13 S5 budgets/counters/ordering**        | 2B-S7-402, 2B-S7-403, 2B-S7-404, 2B-S7-405 |
| **V-14 S6 budget/counters**                  | 2B-S7-402, 2B-S7-403, 2B-S7-404, 2B-S7-405 |
| **V-15 Mapping & attributes**                | 2B-S7-410, 2B-S7-411                       |
| **V-16 Evidence reconciliation**             | 2B-S7-402                                  |
| **V-17 Report shape & provenance**           | 2B-S7-500, 2B-S7-503                       |
| **V-18 Write-once/atomic/idempotent**        | 2B-S7-501, 2B-S7-502, 2B-S7-504            |

> These codes and severities align S7 with your **Dictionary-only**, **partition-exact** posture, the **2B** shape authorities (S2/S3/S4/policies/validation), and the **Layer-1** RNG envelope for optional evidence—ensuring the audit gate is deterministic, reproducible, and enforceable.

---

## 11. **Observability & run-report (Binding)**

**11.1 Purpose**
Emit (i) one **authoritative** fingerprint-scoped audit artefact `s7_audit_report` (see §5/§6), and (ii) one **diagnostic** STDOUT JSON run-report. The audit report is the only persisted, authoritative output of S7; the STDOUT run-report is for operator visibility and CI logs only. 

**11.2 Emission rules**

* **Authoritative artefact:** write `s7_audit_report` once per `(seed, fingerprint)` (write-once + atomic publish; idempotent re-emit must be **byte-identical**). 
* **Run-report (diagnostic):** print **exactly one** JSON object to **STDOUT** on success (and on abort, if possible). Any persisted copy is **non-authoritative**. 

**11.3 Run-report (fields-strict shape)**
S7 MUST output a single JSON object with **exactly** these top-level keys (no extras). Types reuse Layer-1 `$defs` for `hex64`, `uint64`, and `rfc3339_micros`.

```
{
  "component": "2B.S7",
  "seed": "<uint64>",
  "fingerprint": "<hex64>",
  "created_utc": "<rfc3339_micros>",                    // echo S0.receipt.verified_at_utc
  "catalogue_resolution": {
    "dictionary_version": "<semver>",
    "registry_version": "<semver>"
  },
  "inputs_digest": {                                     // echo sealed inputs from S0 inventory
    "s2_alias_index": { "version_tag": "<str>", "sha256_hex": "<hex64>", "path": "<...>", "partition": {"seed":"…","fingerprint":"…"} },
    "s2_alias_blob":  { "sha256_hex": "<hex64>", "path": "<...>", "partition": {"seed":"…","fingerprint":"…"} },
    "s3_day_effects": { "version_tag": "<str>", "sha256_hex": "<hex64>", "path": "<...>" },
    "s4_group_weights": { "version_tag": "<str>", "sha256_hex": "<hex64>", "path": "<...>" },
    "policies": {
      "alias_layout_policy_v1": { "version_tag": "<str>", "sha256_hex": "<hex64>", "path": "<...>" },
      "route_rng_policy_v1":    { "version_tag": "<str>", "sha256_hex": "<hex64>", "path": "<...>" },
      "virtual_edge_policy_v1": { "version_tag": "<str>", "sha256_hex": "<hex64>", "path": "<...>" }
    }
  },
  "metrics": {
    "merchants_total": <int>,
    "groups_total": <int>,
    "days_total": <int>,
    "alias_decode_max_abs_delta?": <float>,              // from S2 round-trip sample (§7.A)
    "max_abs_mass_error_s4?": <float>,                   // Σ_g p_group − 1 (§7.B)
    "draws_expected?": <uint64>,                         // 2×|S5| + |S6_virtual| when logs present
    "draws_observed?": <uint64>                          // from Layer-1 trace totals (logs present)
  },
  "checks": [                                            // one element per validator in §9
    { "id": "V-04", "status": "PASS|FAIL|WARN", "codes": ["2B-S7-200"], "context": { "merchant_id": "<id64>", "note": "<...>" } },
    ...
  ],
  "samples": {                                           // bounded, deterministic
    "alias_decode": [ { "merchant_id": "<id64>", "max_abs_delta": <float> }, ... ],
    "group_norm":  [ { "merchant_id": "<id64>", "utc_day": "YYYY-MM-DD", "sum_p_group": <float> }, ... ],
    "logs?": { "runs": [ { "parameter_hash": "<hex64>", "run_id": "<hex32>", "events_total": <uint64> } ... ] }
  },
  "summary": { "overall_status": "PASS|FAIL", "warn_count": <int>, "fail_count": <int> },
  "target": { "audit_report_path": "data/layer1/2B/s7_audit_report/seed=<seed>/fingerprint=<fingerprint>/s7_audit_report.json" }
}
```

* `created_utc` MUST echo the S0 receipt’s `verified_at_utc`. 
* `inputs_digest` MUST mirror the sealed inputs as recorded at S0 (IDs, version_tags, `sha256_hex`, path, partition). 
* `target.audit_report_path` MUST match the Dictionary path family for `s7_audit_report` at `[seed,fingerprint]`. 

**11.4 Evidence coupling (when S5/S6 logs are present)**

* S7 is **RNG-free**; it only **reads** the Layer-1 core logs (`rng_audit_log`, `rng_trace_log`) and event rows to reconcile totals (**2 events/selection for S5; 1 per virtual for S6**) and counter monotonicity. The run-report MUST include `draws_expected` and `draws_observed` and assert equality (see §9 V-16). 

**11.5 Deterministic samples (bounded)**

* Include at most **K=32** merchants for alias-decode deltas and a bounded set of `(merchant,day)` samples for S4 group sums. Sampling MUST be deterministic (e.g., lowest ASCII-lex merchants/days). Values placed under `samples` are **illustrative**, not authoritative; the authoritative decision is the `summary.overall_status`. (S7’s only persisted authority is `s7_audit_report`.) 

**11.6 Identity & lineage echo**

* The run-report MUST echo `{seed, fingerprint}` and the `audit_report_path`; the authoritative report itself is partitioned `[seed,fingerprint]` and enforces **path↔embed equality** on `seed` and `fingerprint`. 

**11.7 Prohibitions (binding)**

* No literal paths; no network I/O; no writes besides `s7_audit_report`. Optional S5/S6 logs, if present, are **read-only** and **run-scoped** (`[seed,parameter_hash,run_id,utc_day]`) per their Dictionary entries. 

> Net: observability consists of a **fields-strict** STDOUT run-report tied to the Dictionary and sealed inputs, plus one **authoritative** fingerprint-scoped `s7_audit_report` with S0-anchored provenance—no RNG, no extra writes, and full reconciliation when S5/S6 logs are present.

---

## 12. **Performance & scalability (Informative)**

**Goal.** Keep S7 **RNG-free**, single-pass, and **streaming**—so CI can audit large partitions with stable CPU/memory while producing one small JSON report.

### 12.1 Asymptotic cost (per `(seed, fingerprint)`)

* **S2 alias checks.**

  * **Schema/offsets/alignment:** `O(R_index)` over index rows (streaming).
  * **Blob digest:** `O(B_blob)` (streaming SHA-256; no random seeks required).
  * **Decode round-trip sample:** `O(∑_{m∈Sample} N_m)` where `N_m` is sites for merchant `m`. Keep `|Sample| = K ≤ 32` (deterministic pick) so this is bounded and predictable.
* **S3/S4 grid/echo/normalisation:** single join + reductions over day rows → `O(R_s3 + R_s4)` (column-projected scans).
* **Optional logs (S5/S6):** `O(E)` where `E` is total log event rows read (events + trace). All checks (ordering, counters, budgets) are streaming.

### 12.2 Memory envelope

* **Index/row state:** `O(1)` per row (validate → discard).
* **Blob:** hold only the current merchant slice (alias arrays) + small scratch; **never** mmap the whole blob.
* **Accumulators:** running digests, max deltas, and small bounded sample buffers for the report.

### 12.3 I/O strategy

* **Column projection:** when reading Parquet (S3/S4), project only needed columns (ids, day, gamma, p_group).
* **Row-group streaming:** process row groups sequentially; avoid materialising joins—use merge-join over sorted PKs (or external sort if needed).
* **Blob hashing:** read in fixed-size chunks (e.g., 8–32 MiB) to balance throughput and cache pressure.

### 12.4 Concurrency & sharding

* **Safe parallelism:** S7 is read-only; you may parallelise **independent checks** (e.g., S2 sample decodes vs S3/S4 scans) and/or **by merchant shards** for the S2 sample.
* **Single writer:** only the final `s7_audit_report` is written; keep one logical writer per `(seed, fingerprint)` and assemble the JSON deterministically (e.g., sort `checks[]` by validator id) to guarantee idempotent bytes.
* **Multi-run CI:** run different `(seed,fingerprint)` partitions concurrently; they are disjoint.

### 12.5 Determinism & sampling

* **Merchant/day samples:** choose deterministically (e.g., lowest ASCII-lex ids or a fixed hash stride). This keeps the cost bounded and the report reproducible.
* **Numerics:** binary64, ties-to-even; stable serial reductions; store tolerances (e.g., ε for Σ laws, ε_q for decode) in the report for audit traceability.

### 12.6 Zero/large-log regimes

* **No logs present:** skip §C checks; set `draws_expected/observed` null; still compute S2/S3/S4 metrics—runtime ≈ `O(R_index + B_blob + R_s3 + R_s4)`.
* **Huge logs:** treat each `(seed, parameter_hash, run_id)` stream as an independent scan; reconcile counts via cumulative `rng_trace_log` rows to avoid keeping per-arrival state.

### 12.7 Failure-first behaviour

* **Short-circuit hard fails:** stop early on gate/partition/schema violations; emit a minimal `s7_audit_report` with FAIL and collected context (still write once).
* **Progressive metrics:** compute `alias_decode_max_abs_delta` and `max_abs_mass_error_s4` during streaming; no second pass required.

### 12.8 Practical knobs (CI profiles)

* `K` (S2 decode sample size, default 32), `chunk_bytes` for blob hashing, `join_buffer_rows` for S3/S4 merge-join, and a `logs_max_scan` cap for quick PR checks vs full nightly. All knobs are **non-normative**; outputs remain identical given the same sealed inputs and chosen `K`.

> Net: S7 scales linearly in the size of sealed artefacts (plus any optional logs), uses constant-space streaming, and writes a single deterministic JSON report—making it cheap for PR gating and predictable for nightly full CI.

---

## 13. **Change control & compatibility (Binding)**

**13.1 Versioning (SemVer) — what changes bump what**

* **MAJOR** when any binding interface changes: input **IDs or partition law**, the **required validator set/semantics**, Σ/normalisation/alias **laws**, or the **report identity/shape** (anchor rename or required keys). Making S5/S6 **logs mandatory** or changing their **budget expectations** (S5≠2, S6≠1) is also **MAJOR**.
* **MINOR** for backward-compatible additions: new **WARN** validators, new **optional** report fields/samples, new **optional** policy echoes/metrics, support for **additional optional inputs** (kept read-only). Minor changes must **not** flip any PASS→FAIL for previously valid inputs.
* **PATCH** for editorial fixes, clarifications, and non-semantic schema tidy (e.g., descriptions), with no shape/behaviour change.

**13.2 Compatibility surface (stable within S7 v1.x)**
Consumers MAY rely on the following remaining stable across 1.x:

* **Inputs & selection** (read-only):
  `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights` at **`[seed,fingerprint]`**; policies `alias_layout_policy_v1`, `route_rng_policy_v1`, `virtual_edge_policy_v1` are **token-less** and selected by **S0-sealed** `path+sha256_hex`.
  Optional logs (if present): `s5_selection_log`, `s6_edge_log` at **`[seed,parameter_hash,run_id,utc_day]`** (run-scoped).
* **RNG posture:** S7 is **RNG-free**. When logs are present, S7 only **reads** Layer-1 evidence and expects budgets: **S5 = 2 events/selection** (group→site), **S6 = 1 event/virtual**; counters strictly monotone; one trace append after each event.
* **Output identity:** exactly one authoritative `s7_audit_report` per `(seed,fingerprint)`, **fields-strict** per `s7_audit_report_v1`, with **path↔embed equality** and **write-once + atomic publish**.
* **Validator/Code IDs:** Validator IDs (`V-01…`) and error codes (`2B-S7-…`) are **reserved**; meanings stay stable within the major.

**13.3 Backward-compatible (MINOR) changes**

* Add **WARN** validators (e.g., soft hints for borderline Σ errors) without changing existing PASS/FAIL definitions.
* Add **optional** keys to `s7_audit_report` (e.g., extra metrics or sample blocks). If the anchor is **fields-strict**, publish a new **minor anchor** (e.g., `s7_audit_report_v1.1`) and **dual-accept** in consumers.
* Expand policy echo recorded in `inputs_digest` (e.g., additional non-authoritative fields), or allow **optional** extra evidence families to be read without affecting outcomes or existing reconciliations.

**13.4 Breaking (MAJOR) changes**

* Changing any **required validator** semantics (e.g., Σ law tolerance tightening that flips prior PASS to FAIL), decode/normalisation **laws**, or the **deterministic sampling** rule.
* Altering input **IDs**, their **path families**, **formats**, or **partitions**; making S5/S6 logs **required**; or altering their **partition law**.
* Renaming/removing validator IDs or error codes; changing `s7_audit_report` required keys or moving the report to a different partition.

**13.5 Coordination with neighbouring states**

* **S2**: Changes to index/blob **anchors** (required fields, offset/alignment law, `blob_sha256` presence) must be coordinated; adding non-required header fields is compatible, removing/renaming required ones is **MAJOR** for S7.
* **S3/S4**: Internal impl changes are fine if anchors, **Σ=1** law, γ-echo, PK/writer order, and partitions remain stable.
* **S5/S6**: Any change to **budgets**, **event ordering**, or **run-scoped envelope** requires an S7 **MAJOR** (validators V-13…V-16 depend on them). Adding new optional event families is compatible if current families remain.
* **Layer-1 RNG pack**: Envelope/core-log anchors and partitions must remain stable; adding new families is compatible; changing the envelope is **MAJOR**.

**13.6 Dictionary/Registry coordination**

* Adding `s7_audit_report` to the **Dictionary** (ID, path family, partition law `[seed,fingerprint]`, format `json`, schema-ref) and to the **Registry** (metadata, write_once, atomic) is required for go-live.
* Future **Dictionary** edits that rename IDs, change path families, or alter partitions for S7 inputs/output are **MAJOR**. Registry metadata tweaks (owners/licence/retention) are compatible unless they impact existence.

**13.7 Deprecation & migration protocol**

* Publish a **change log** with: summary, impact, validator/code diffs, schema diffs, migration steps.
* For MAJORs, prefer **dual-publish** (accept both old/new report anchors) for a migration window; provide a shim to down-level new reports if needed.

**13.8 Rollback policy**

* S7 is **write-once**; rollback = publish a new `(seed,fingerprint)` that restores last-known-good behaviour (or revert to an earlier fingerprint). **No in-place mutation** of existing reports.

**13.9 No new authorities**

* This section defines **no new datasets** beyond `s7_audit_report`. Shapes stay governed by the 2B pack (plans/policies/validation) and Layer-1 pack (RNG evidence, if read); **ID→paths/partitions** remain under the Dataset Dictionary; the **Artefact Registry** remains metadata-only.

> Net: within a major, S7 stays a **RNG-free, streaming audit gate** producing a single fingerprint-scoped, fields-strict report; inputs/partitions and validator semantics are stable; any change that alters those guarantees requires a coordinated **MAJOR**.

---

## Appendix A — Normative cross-references *(Informative)*

**A.1 Shape authorities (packs)**

* **2B schema pack** — primary authority for S7 (and S2/S3/S4, policies, S5/S6 trace rows): `schemas.2B.yaml`. 
* **Layer-1 RNG pack** — evidence envelope + core logs used *only if* S5/S6 logs are present: `schemas.layer1.yaml`. 
* **2A pack (context only)** — `site_timezones` used in S5 mapping checks referenced by S7: `schemas.2A.yaml`. 

**A.2 2B anchors used by S7**

* **Plans/Binary:** `#/plan/s2_alias_index`, `#/binary/s2_alias_blob`, `#/plan/s3_day_effects`, `#/plan/s4_group_weights`. 
* **Policies (token-less; S0-sealed):** `#/policy/alias_layout_policy_v1`, `#/policy/route_rng_policy_v1`, `#/policy/virtual_edge_policy_v1`. 
* **Trace rows (optional diagnostics):** `#/trace/s5_selection_log_row`, `#/trace/s6_edge_log_row`. 
* **S7 report shape:** `#/validation/s7_audit_report_v1`. 

**A.3 Layer-1 RNG evidence (read-only, only if logs exist)**

* **Envelope & core logs:** `#/$defs/rng_envelope`, `#/rng/core/rng_audit_log`, `#/rng/core/rng_trace_log`. 
* **Event families (registered):** `rng_event.cdn_edge_pick` (S6, single-uniform). *(S5 families are validated via envelope/trace reconciliation even if not explicitly anchored here.)* 

**A.4 Dataset Dictionary IDs & partitions (catalogue authority)**

* **S2/S3/S4 (read-only):** `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights` @ **`[seed, fingerprint]`**. 
* **Policies (token-less; S0-sealed):** `alias_layout_policy_v1`, `route_rng_policy_v1`, `virtual_edge_policy_v1`. 
* **Optional logs (run-scoped):** `s5_selection_log`, `s6_edge_log` @ **`[seed, parameter_hash, run_id, utc_day]`**. 
* **S7 output (authoritative):** `s7_audit_report` @ **`[seed, fingerprint]`** *(add entry if not already present: json; schema_ref `schemas.2B.yaml#/validation/s7_audit_report_v1`)*. 

**A.5 Artefact Registry (metadata only; owners/licence/retention)**

* Current entries cover 2B policies/logging surfaces added in earlier steps (e.g., `virtual_edge_policy_v1`, optional `s6_edge_log`). 
* **S7 audit report** should be mirrored here with `write_once: true` and `atomic_publish: true` (metadata addition; shape stays governed by the schema pack). 

**A.6 Cross-pack references (context)**

* **2A egress:** `schemas.2A.yaml#/egress/site_timezones` — used only for S5 mapping coherence checks referenced by S7 (no writes). 

> These references tie S7’s **authoritative output** (`s7_audit_report`) to the 2B shapes and Dictionary IDs, and—when present—the Layer-1 RNG evidence used for reconciliation, while keeping all reads sealed and partition-exact.

---
