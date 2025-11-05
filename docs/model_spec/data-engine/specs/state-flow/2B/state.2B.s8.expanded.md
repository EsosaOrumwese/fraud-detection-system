# State 2B.S8 — Validation bundle & `_passed.flag`

## 1. **Document metadata & status (Binding)**

**Component:** Layer-1 · Segment **2B** — **State-8 (S8)** · *Validation bundle & `_passed.flag`*
**Document ID:** `seg_2B.s8.validation_bundle`
**Version (semver):** `v1.0.1-alpha`
**Status:** `alpha` *(normative; semantics lock at `frozen`)*
**Owners:** Design Authority (DA): **Esosa Orumwese** · Review Authority (RA): **Layer-1 Governance**
**Effective date:** **2025-11-05 (UTC)**
**Canonical location:** `contracts/specs/l1/seg_2B/state.2B.s8.expanded.v1.0.1.txt`

**Authority chain (Binding).**

* **JSON-Schema packs** are **shape authority**:

  * **Bundle index law** (canonical) and **flag** anchors (see §6).
  * 2B pack anchors for `s7_audit_report_v1`, S0 receipt/inventory, and S2/S3/S4 shapes.
* **Dataset Dictionary** is **catalogue authority** (IDs → paths/partitions/format). S8 resolves **by ID only**; **no literal paths**.
* **Artefact Registry** is **metadata only** (owners/licence/retention; write-once/atomic flags).
* **Gate law:** **No PASS → No read** remains in force; S8 **must** see S0 evidence and PASS S7 reports before publish.
* **RNG posture:** **RNG-free**.

**Normative cross-references (Binding).**
S8 SHALL treat these surfaces as authoritative and Dictionary-resolvable:

* **S0 evidence (2B):** `s0_gate_receipt_2B`, `sealed_inputs_v1` — fingerprint-scoped.
* **S7 audit:** `s7_audit_report_v1` — one per **seed** at `[seed, fingerprint]` and status **PASS**.
* **Plans referenced for provenance (read-only):** `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights` — all at `[seed, fingerprint]`.
* **Policies (token-less; S0-sealed):** `alias_layout_policy_v1`, `route_rng_policy_v1`, `virtual_edge_policy_v1`.
* **Validation bundle laws:**

  * **Index schema (canonical):** fields-strict `{ path, sha256_hex }`; **paths are relative**; entries **ASCII-lex** by `path`.
  * **Flag schema:** `_passed.flag` is a **single line** `sha256_hex = <hex64>` and is **not** listed in the index.

**Segment invariants (Binding).**

* **Partitioning:** S8 **publishes** under `data/layer1/2B/validation/fingerprint={manifest_fingerprint}/` (fingerprint-only).
* **Write discipline:** **single writer**, **write-once + atomic move**; idempotent re-emit **must** be byte-identical.
* **Catalogue discipline:** Dictionary-only resolution; **no network I/O**; **no re-auditing** (S8 packages evidence and verifies digests; S7 is the audit).

---

## 2. **Purpose & scope (Binding)**

**Purpose.** Publish the **authoritative PASS evidence** for **Layer-1 · 2B** at a given `manifest_fingerprint`. S8 is **RNG-free** and **fingerprint-scoped**. It **does not re-audit**; it **packages** already-sealed evidence into a deterministic **validation bundle** and emits the canonical **`_passed.flag`**. **No PASS → No read** for any 2B consumer remains in force.

**S8 SHALL do (in scope):**

* **Verify prerequisites (RNG-free):**

  1. S0 receipt & sealed-inputs exist for this fingerprint.
  2. **Seed set discovery** for the bundle using a deterministic rule (**intersection** of seeds present in `s2_alias_index`, `s3_day_effects`, `s4_group_weights`).
  3. For **every** seed in that set, an **S7 audit report** exists at `[seed,fingerprint]` and its **status is PASS** (WARNs are permitted unless policy forbids).

* **Assemble the bundle (deterministic layout):**

  * Create a workspace under a temporary root; place:
    • all `s7_audit_report@[seed,fingerprint]` (one per seed) under `reports/seed={seed}/`;
    • S0 evidence (receipt + sealed_inputs) under `evidence/s0/`;
    • optional provenance snapshots (e.g., policy files, S2/S3/S4 digests) under `evidence/refs/`.
  * **No byte rewriting** of any included file.

* **Index the bundle:**

  * Write **`index.json`** (fields-strict): array of `{ path, sha256_hex }` where
    • `path` is **relative** to the bundle root (no absolute/parent segments),
    • entries are **ASCII-lex ordered by `path`**,
    • `sha256_hex` is computed over the **raw bytes** at each path.
  * **Do not include `_passed.flag` in the index.**

* **Compute and emit the flag:**

  * Compute **bundle digest** = `SHA256(concat(indexed file bytes in ASCII-lex order of path))`.
  * Emit **`_passed.flag`** with **exactly one line**:
    `sha256_hex = <bundle_digest>`.

* **Publish atomically (identity discipline):**

  * Publish the bundle directory at
    `data/layer1/2B/validation/fingerprint={manifest_fingerprint}/`
    via **single atomic move**; **write-once**; idempotent re-emit must be **byte-identical**.

**Out of scope (SHALL NOT):**

* Re-run S7 checks, modify S2/S3/S4 or policies, generate any run-scoped logs, or write to any path outside the fingerprint-scoped bundle.
* Use network I/O or literal file paths; all reads are **Dataset-Dictionary** resolved; **S0‑evidence rule** in force:
  cross‑layer/policy assets **MUST** appear in S0’s sealed inventory; within‑segment inputs are **NOT** S0‑sealed and
  **MUST** be resolved by **Dictionary ID** at exactly **`[seed, fingerprint]`** (no literals).

**Determinism & numeric discipline (Binding).**

* **No RNG.** Hashing is **SHA-256** over bytes; index order is **ASCII-lex**; all decisions (seed discovery, file layout) are defined deterministically so a re-run yields **identical bytes**.
* **Path↔embed equality:** any identity echoed inside included reports (e.g., S7’s `seed`, `fingerprint`) **must** equal their path tokens.

**Effect.** On success, consumers have a single, reproducible proof that **all required seeds passed S7** and that the **exact bytes** of 2B’s evidence are frozen—enforced by the bundle’s index/flag pair.

---

## 3. **Preconditions & sealed inputs (Binding)**

**3.1 Gate & authority (must hold before any read)**

* **S0 evidence present for this fingerprint.** `s0_gate_receipt_2B` **and** `sealed_inputs_v1` exist at `[fingerprint]` and validate against the 2B pack. S8 **relies** on S0 (does not re-hash upstream 1B). 
* **Index/flag laws in force.** S8 will use the canonical **bundle index schema** (fields `{path, sha256_hex}`, relative paths, ASCII-lex order) and the **`_passed.flag`** law (exact one-line `sha256_hex = <hex64>`).
* **RNG posture:** **RNG-free**. No random draws are permitted anywhere in S8. *(Hashing only.)*

**3.2 Seed set discovery (deterministic; binding)**

* **Required seeds = intersection** of seeds present at this fingerprint across:
  `s2_alias_index@[seed,fingerprint]`, `s3_day_effects@[seed,fingerprint]`, `s4_group_weights@[seed,fingerprint]`.
  If the intersection is **empty**, **Abort** (no bundle can be formed). 
* The discovery procedure and the resulting ordered list of seeds **must** be deterministic (e.g., ASCII-lex on decimal `seed` strings) to guarantee identical bytes on re-emit.

**3.3 Audit prerequisite (binding)**

* For **every seed** in the discovered set, an **authoritative** `s7_audit_report` exists at
  `data/layer1/2B/s7_audit_report/seed={seed}/fingerprint={manifest_fingerprint}/s7_audit_report.json`, validates against `schemas.2B.yaml#/validation/s7_audit_report_v1`, and its `summary.overall_status == "PASS"`. *(WARNs permitted unless a governance policy forbids; FAIL not permitted.)* 

**3.4 Inputs S8 SHALL read (sealed; read-only)**
Resolve **by Dataset Dictionary ID only**.
Evidence posture: cross‑layer/policy assets **MUST** appear in S0’s sealed inventory for this fingerprint;
within‑segment datasets (`s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights`) are **NOT** S0‑sealed and **MUST**
be read at exactly **`[seed, fingerprint]`** (no literals, no network).

* **S0 evidence (fingerprint-scoped):** `s0_gate_receipt_2B`, `sealed_inputs_v1` (for provenance and sealed digests/paths). 
* **S7 reports (seed×fingerprint-scoped):** one `s7_audit_report` per required seed (PASS). **Shape:** `#/validation/s7_audit_report_v1`. 
* **Plans for provenance echo (seed×fingerprint-scoped):**
  `s2_alias_index` (`#/plan/s2_alias_index`), `s2_alias_blob` (`#/binary/s2_alias_blob`), `s3_day_effects` (`#/plan/s3_day_effects`), `s4_group_weights` (`#/plan/s4_group_weights`). *(S8 does **not** re-audit these; used to echo/verify digests and to compute the seed intersection.)* 
* **Policies (token-less; S0-sealed path+digest):** `alias_layout_policy_v1`, `route_rng_policy_v1`, `virtual_edge_policy_v1`. *(Single files; `partition={}`.)* 

**3.5 Selection, partitions & identity discipline (binding)**

* **Dictionary-only resolution.** No literal paths; no network I/O.
* **Exact partitions:** S2/S3/S4 & S7 read at **`[seed,fingerprint]`**; policies selected by **exact S0-sealed** `path` **and** `sha256_hex` (`partition={}`).
* **Path↔embed equality:** where lineage is embedded (e.g., `seed`/`fingerprint` in S7), values **must** byte-equal the path tokens. 

**3.6 Integrity pre-flight before packaging (abort on failure)**

* **S7 presence & status:** every required seed has a report; each validates (`s7_audit_report_v1`) with `overall_status="PASS"`. 
* **Sealed‑digest parity (policies only):** for token‑less policies, the `(path, sha256_hex)` in `sealed_inputs_v1` **must** match what S8 resolves.
  S8 does **not** require S0 parity for S2/S3/S4; these are within‑segment and **must** be selected by ID at **`[seed, fingerprint]`**
  (their integrity is audited upstream; S8 packages evidence only).
* **Bundle law availability:** the implementation must have the canonical **index schema** and **flag** anchors available (see §6) to validate `index.json` and `_passed.flag` prior to publish.

**3.7 Prohibitions (binding)**

* **No RNG; no network I/O; no literal paths.**
* **No mutation** of any input artefact; S8 writes **only** the fingerprint-scoped validation bundle (`index.json` + `_passed.flag`), **write-once** with an **atomic move**. *(Idempotent re-emit must be byte-identical.)* 

> With these preconditions, S8’s inputs are **sealed and partition-exact**, the **seed set** is deterministic and complete, S7 PASS coverage is enforced, and the **index/flag** laws are in place—so the published bundle is a reproducible, authoritative PASS signal for Segment 2B.

---

## 4. **Inputs & authority boundaries (Binding)**

**4.1 Authority chain (who governs what)**

* **JSON-Schema packs = shape authority.** S8 binds to the **bundle index law** and **`_passed.flag`** anchors (canonical index with `{path, sha256_hex}`; paths **relative**; entries **ASCII-lex**; flag is single line `sha256_hex = <hex64>` and **not** indexed). 
* **2B pack** provides shapes for **`s7_audit_report_v1`** (authoritative audit), plus S2/S3/S4 plan/binary anchors referenced for provenance. 
* **Dataset Dictionary = catalogue authority** (IDs → paths/partitions/format). S8 resolves **only by ID** at the exact partitions declared. 
* **Artefact Registry = metadata only** (owners/licence/retention; write-once/atomic flags), not shapes/partitions.
* **Gate law.** S0 evidence (receipt + sealed inventory) is authoritative; S8 packages evidence and **does not re-audit**. (S7 performed the audit; S8 requires S7 **PASS** per seed.) 

**4.2 Inputs S8 SHALL read (sealed; read-only; Dictionary-resolved)**
Evidence rule: cross‑layer/policy inputs **MUST** appear in S0’s sealed inventory; within‑segment inputs are **not** S0‑sealed and
**MUST** be selected by ID at **`[seed, fingerprint]`**.

* **S0 evidence (fingerprint):** `s0_gate_receipt_2B`, `sealed_inputs_v1` — provenance + sealed digests/paths.
* **S7 audit reports (one per required seed):**
  `s7_audit_report@seed={seed}/fingerprint={manifest_fingerprint}`
  **Shape:** `schemas.2B.yaml#/validation/s7_audit_report_v1` (fields-strict). **Partition:** `[seed, fingerprint]`.  
* **Plan/binary provenance (used for seed discovery & echo only):**
  `s2_alias_index@{seed,fingerprint}` → `#/plan/s2_alias_index` · `s2_alias_blob@{seed,fingerprint}` → `#/binary/s2_alias_blob`;
  `s3_day_effects@{seed,fingerprint}` → `#/plan/s3_day_effects`;
  `s4_group_weights@{seed,fingerprint}` → `#/plan/s4_group_weights`. 
* **Policies (token-less; S0-sealed path+digest):**
  `alias_layout_policy_v1`, `route_rng_policy_v1`, `virtual_edge_policy_v1`. *(Single files; `partition={}`.)* 

**4.3 Bundle laws S8 SHALL enforce (shape authority)**

* **Index schema (canonical):** index entries are `{path, sha256_hex}`; `path` **relative** to bundle root; entries **ASCII-lex** by `path`; **no duplicates**; every listed file **exists** under the bundle root; `_passed.flag` is **never** in the index. 
* **Flag schema:** file content is **exactly** one ASCII line `sha256_hex = <hex64>`; the value equals **SHA-256 over raw bytes of all files listed in the index**, concatenated in **ASCII-lex** path order; the flag itself is **excluded**.  

**4.4 Partition & identity discipline (binding)**

* **Exact partitions:**
  • S2/S3/S4 and S7 reads at **`[seed, fingerprint]`**;
  • Policies are token-less (`partition={}`) and selected by **exact S0-sealed** `path`+`sha256_hex`.  
* **Publish partition:** the validation bundle is **fingerprint-scoped** under `data/layer1/2B/validation/fingerprint={manifest_fingerprint}/`. (Write-once; atomic move; idempotent re-emit must be **byte-identical**.) 
* **Path↔embed equality:** any lineage echoed inside included evidence (e.g., `seed`/`fingerprint` fields in S7 JSON) **must** byte-equal the path tokens. 

**4.5 Prohibitions & boundaries (binding)**

* **No re-auditing:** S8 does **not** re-run S7 validators; it only verifies presence/digests and packages evidence. (S7 is the audit gate.) 
* **RNG-free;** **no network I/O;** **no literal paths.** All reads are Dictionary-resolved sealed artefacts; S8 writes only the **bundle** (`index.json` + `_passed.flag`). 
* **Single writer:** one logical writer for the fingerprint bundle; **atomic publish**; **file order non-authoritative** (only the index order governs hashing). 

---

## 5. **Outputs (datasets) & identity (Binding)**

**5.1 Authoritative egress (fingerprint-scoped bundle).**
S8 produces **exactly two artefacts** under the fingerprint path:

* **Bundle index** — `data/layer1/2B/validation/fingerprint={manifest_fingerprint}/index.json`
  *Fields-strict; entries are `{ path, sha256_hex }`, with `path` **relative** to the bundle root and rows **ASCII-lex ordered by `path`**.* 
* **PASS flag** — `data/layer1/2B/validation/fingerprint={manifest_fingerprint}/_passed.flag`
  *Exactly one ASCII line: `sha256_hex = <hex64>`; the flag **itself is not listed** in `index.json`.*

**5.2 Identity & partitions (binding).**

* **Partition law:** **fingerprint-only**; no `seed`, `parameter_hash`, or `run_id` appear in the publish path. 
* **Path↔embed equality:** any identity echoed inside included files (e.g., S7 report `seed`/`fingerprint`) **must** byte-equal their path tokens; S8 does **not** rewrite those files. 

**5.3 Shapes & anchors (binding).**

* `index.json` MUST validate the canonical **bundle index law**: `{ path, sha256_hex }`, `path` **relative**, entries **ASCII-lex**, no duplicates.
* `_passed.flag` MUST validate the canonical **flag** anchor: **single line** `sha256_hex = <hex64>`.

**5.4 Write discipline (binding).**

* **Write-once + atomic publish:** build the bundle in a temp workspace, fsync, then **single atomic move** to the final fingerprint path.
* **Idempotent re-emit:** allowed only if **bytes are identical** to the existing bundle; otherwise **Abort**.
* **Single writer** for the fingerprint bundle. *(File order inside the directory is non-authoritative; only the index governs hashing.)* 

**5.5 Digest parity (binding).**

* For **every** row in `index.json`, the recorded `sha256_hex` MUST equal the digest of the file’s **raw bytes** at `path`.
* The flag’s `sha256_hex` MUST equal the **SHA-256 over the concatenation of all indexed file bytes in ASCII-lex `path` order**. 

**5.6 Catalogue notes (Dictionary/Registry).**
Register two IDs in the **Dataset Dictionary** (and mirror them in the **Artefact Registry** as metadata with `write_once: true`, `atomic_publish: true`):

* `validation_bundle_2B` → `…/fingerprint={manifest_fingerprint}/index.json`
  `format: json` · `schema_ref: …#/validation/validation_bundle.index_schema`. 
* `validation_passed_flag_2B` → `…/fingerprint={manifest_fingerprint}/_passed.flag`
  `format: text` · `schema_ref: …#/validation/passed_flag`. 

> Net: S8 emits a **single, fingerprint-scoped validation bundle** whose **index.json** and **`_passed.flag`** form the authoritative PASS proof for 2B; identity is fingerprint-only; ordering and digests follow the canonical bundle laws; and publish is **write-once + atomic**.

---

## 6. **Dataset shapes & schema anchors (Binding)**

**6.1 Shape authority**
JSON-Schema is **sole** shape authority. S8 binds to the canonical **bundle index law** and **flag** anchors, and *references* existing 2B/Layer anchors for inputs included as evidence. The **Dataset Dictionary** governs ID→path/partitions/format; the **Artefact Registry** is metadata-only.

---

**6.2 Bundle index — `index.json` (Binding)**
**Anchor (canonical):** `schemas.1A.yaml#/validation/validation_bundle.index_schema`
**Fields-strict** JSON array of objects with exactly:

* `path` (string) — **relative** to the bundle root; **no** leading `/`, **no** `..` segments; UTF-8.
* `sha256_hex` (string) — lowercase hex of **SHA-256 over raw file bytes** at `path`.

**Ordering (binding):** array entries are **ASCII-lex sorted by `path`**.
**No duplicates:** each `path` appears once.
**Coverage:** every listed `path` **exists** under the bundle root.
**Exclusion rule:** `_passed.flag` **MUST NOT** appear in the index.

*(Publisher note: JSON encoding is UTF-8; whitespace/pretty-print is non-authoritative, but must yield a stable byte sequence for idempotent re-emit.)*

---

**6.3 PASS flag — `_passed.flag` (Binding)**
**Anchor (canonical):** `schemas.1B.yaml#/validation/passed_flag`
**Shape:** a single ASCII line:

```
sha256_hex = <hex64>
```

Where `<hex64>` equals the **SHA-256 of the concatenation** of **all indexed file bytes** in the **ASCII-lex `path` order** given by `index.json`. The flag file **is not** listed in the index.

---

**6.4 Referenced anchors (read-only evidence)**
S8 *does not re-audit*; it references these anchors to validate prerequisites and to copy/echo evidence:

* **Audit reports:** `schemas.2B.yaml#/validation/s7_audit_report_v1` (one per seed at `[seed,fingerprint]`).
* **Plans/Binary (provenance echo & seed discovery):**
  `#/plan/s2_alias_index`, `#/binary/s2_alias_blob`, `#/plan/s3_day_effects`, `#/plan/s4_group_weights`.
* **Policies (token-less; S0-sealed path+digest):**
  `#/policy/alias_layout_policy_v1`, `#/policy/route_rng_policy_v1`, `#/policy/virtual_edge_policy_v1`.

---

**6.5 Partition law & identity (Binding)**

* **Publish partition:** `data/layer1/2B/validation/fingerprint={manifest_fingerprint}/` (fingerprint-only).
* **Inputs:** S7/S2/S3/S4 are selected at **`[seed,fingerprint]`**; policies are **token-less** (`partition={}`) and selected by **exact S0-sealed** `path` + `sha256_hex`.
* **Path↔embed equality:** any lineage echoed *inside included evidence* (e.g., S7 JSON `seed`, `fingerprint`) **MUST** byte-equal path tokens; S8 does **not** modify evidence bytes.

---

**6.6 Bundle layout constraints (Binding)**

* Layout under the bundle root is **non-authoritative**; the **index.json** governs coverage and hashing.
* **Recommended** deterministic layout (informative):

  * `reports/seed={seed}/s7_audit_report.json` (one per seed)
  * `evidence/s0/{s0_gate_receipt_2B.json, sealed_inputs_v1.json}`
  * `evidence/refs/{policies|s2|s3|s4}/…` (optional snapshots)
* All files listed in `index.json` **must** reside **within** the bundle root.

---

**6.7 Hash & encoding law (Binding)**

* Hash algorithm is **SHA-256** over **raw file bytes**.
* The bundle digest used in `_passed.flag` is **SHA-256(concat(indexed file bytes in ASCII-lex path order))**.
* JSON must be UTF-8; text files (including `_passed.flag`) must be ASCII/UTF-8. End-of-line is `\n`.

---

**6.8 Validation sequence (Binding)**
Implementations **MUST** validate, prior to publish:

1. `index.json` against the **index** anchor (fields-strict, relative paths, ASCII-lex, no duplicates).
2. Each `sha256_hex` row against the on-disk bytes.
3. `_passed.flag` against the **flag** anchor; recompute bundle digest equals the flag value.
4. Partition/path discipline (fingerprint-scoped publish; no extra files listed outside the root).

> With these anchors and rules, the S8 bundle is a **deterministic, fingerprint-scoped** PASS artefact: anyone can re-hash the bytes listed in `index.json` and match `_passed.flag`, and S8 never re-audits or mutates evidence—only packages it under the canonical index/flag laws.

---

## 7. **Deterministic algorithm (RNG-free) (Binding)**

**Overview.** S8 performs **no RNG**. Every decision (seed discovery, file layout, index ordering, hashing) is fully deterministic, producing **byte-identical** output on re-runs with the same sealed inputs.

### 7.1 Resolve & verify prerequisites (RNG-free)

1. **Resolve by ID (Dictionary-only):** `s0_gate_receipt_2B`, `sealed_inputs_v1`; all **S7** reports; **S2/S3/S4** plans; token-less **policies** (selected by S0-sealed path+digest). **No network I/O; no literal paths.**
2. **Seed discovery (intersection):** Required seeds = **intersection** of seeds present at this fingerprint in `s2_alias_index`, `s3_day_effects`, `s4_group_weights`. **Abort** if empty. Sort seeds **ASCII-lex** by their decimal string for stability. 
3. **S7 coverage:** For **every** discovered seed, load `s7_audit_report@[seed,fingerprint]`, validate against `#/validation/s7_audit_report_v1`, and require `summary.overall_status == "PASS"`. (WARN allowed unless policy forbids.) 
4. **Sealed-digest parity (policies only):** For token-less policies, echo `(path, sha256_hex)` from `sealed_inputs_v1` and require equality.
   For S2/S3/S4 (within-segment), select by **Dataset Dictionary ID** at exactly **`[seed,fingerprint]`** (no literals); do not require S0 parity. 

### 7.2 Stage bundle workspace (RNG-free)

5. **Create temp workspace** under a deterministic local path (not the final publish path).
6. **Deterministic layout (informative):**

   * `reports/seed={seed}/s7_audit_report.json` (one per seed, seeds in sorted order)
   * `evidence/s0/{s0_gate_receipt_2B.json, sealed_inputs_v1.json}`
   * `evidence/refs/{policies|s2|s3|s4}/…` (optional snapshots)
     Copy or hard-link **bytes unchanged** (no normalisation, no re-write). Paths in the bundle **must be under the root** (no `..`). 

### 7.3 Build `index.json` (binding)

7. **Enumerate files** under the bundle root **excluding `_passed.flag`**. For each file, compute `sha256_hex = SHA256(raw bytes)`.
8. **Materialise the index** as a **fields-strict** JSON array of `{ path, sha256_hex }` where `path` is **relative**.
9. **Sort entries** **ASCII-lex by `path`**. **No duplicates**. Validate `index.json` against the **canonical bundle index** anchor. 

### 7.4 Emit `_passed.flag` (binding)

10. **Compute bundle digest** = `SHA256(concat(indexed file bytes in ASCII-lex order of path))`.
11. Write `_passed.flag` containing **exactly**:

```
sha256_hex = <bundle_digest>
```

Validate against the **flag** anchor. **The flag is not listed** in `index.json`. 

### 7.5 Pre-publish validations (binding)

12. Re-validate: index schema; every index row’s `sha256_hex` vs file bytes; flag value vs recomputed bundle digest; fingerprint partition law. **Abort** on any mismatch. 

### 7.6 Publish (binding)

13. **Atomic move** the workspace to `data/layer1/2B/validation/fingerprint={manifest_fingerprint}/`.
14. **Write-once & idempotent:** if the target exists, bytes **must** be identical; otherwise **Abort** (no overwrite). File order in the directory is non-authoritative; the **index** governs hashing. 

### 7.7 Determinism & encoding rules (binding)

* **No RNG;** hash = **SHA-256** over raw bytes.
* **JSON encoding:** UTF-8; stable serializer (key order and whitespace fixed by implementation so re-runs produce identical bytes).
* **Path discipline:** all `path` values are relative, UTF-8, no leading `/`, no `..`.
* **Path↔embed equality:** any lineage echoed inside included reports (e.g., S7 `seed`/`fingerprint`) equals path tokens; S8 never edits those files. 

> Outcome: a **deterministic, fingerprint-scoped** validation bundle whose `index.json` and `_passed.flag` can be independently re-hashed to the same digest, proving 2B is **PASS** for all required seeds.

---

## 8. **Identity, partitions, ordering & merge discipline (Binding)**

**8.1 Publish identity (authoritative).**

* **Partition:** fingerprint-only — bundle lives at
  `data/layer1/2B/validation/fingerprint={manifest_fingerprint}/`. 
* **No run/seed tokens** appear in the publish path. Inputs that S8 reads remain at `[seed,fingerprint]` (S2/S3/S4/S7); policies are token-less. 

**8.2 Path↔embed equality.**

* Any lineage echoed **inside** included evidence (e.g., S7 report `seed`, `fingerprint`) **MUST** byte-equal the tokens in its path. S8 does not rewrite bytes; mismatches are fatal. 

**8.3 Index ordering & path law (binding).**

* `index.json` is the **sole ordering authority**: entries are `{path, sha256_hex}`; `path` is **relative**, no leading `/`, no `..`; entries are **ASCII-lex ordered by `path`**; **no duplicates**. `_passed.flag` is **never** indexed. 
* Disk file order and directory listing order are **non-authoritative**. Only `index.json` governs hashing/digest. 

**8.4 Write discipline & atomicity.**

* **Single writer** for the fingerprint bundle. Build in a temp workspace and **publish by single atomic move** into the final path. 
* **Write-once.** Re-publishing is allowed **only** if bytes are **identical** (idempotent re-emit). Otherwise **Abort**. 

**8.5 Merge discipline.**

* **No cross-bundle merges.** Never merge across different fingerprints.
* **No partial updates.** The bundle is published as a complete unit; additions require a new publication that produces byte-identical content or a new fingerprint. 

**8.6 Hashing determinism.**

* Per-row `sha256_hex` in `index.json` **MUST** equal the SHA-256 of the file’s **raw bytes** at `path`.
* `_passed.flag.sha256_hex` **MUST** equal `SHA256(concat(indexed file bytes in ASCII-lex path order))`.

**8.7 Prohibitions.**

* **No network I/O**, **no literal paths**; all reads are **Dataset-Dictionary** resolved sealed artefacts.
* **No mutation** of any included evidence file; S8 copies/links bytes unchanged. 

> Result: the S8 bundle is a **fingerprint-scoped, write-once** artefact whose identity, ordering, and digests are fully deterministic and verifiable from `index.json` and `_passed.flag`.

---

## 9. **Acceptance criteria (validators) (Binding)**

> S8 is **RNG-free**. All inputs are **Dataset-Dictionary** resolved; all publishes are **fingerprint-scoped**. Index/flag laws are **canonical**.

**V-01 — Gate evidence present (S0)**
**Check:** `s0_gate_receipt_2B` **and** `sealed_inputs_v1` exist at `[fingerprint]` and validate.
**Fail →** ⟨2B-S8-001 S0_RECEIPT_MISSING⟩. 

**V-02 — S0-evidence & Dictionary-only**
**Check:** All cross-layer/policy assets appear in the **S0 sealed inventory** for this fingerprint; all within-segment
inputs (`s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights`) resolve **by Dataset Dictionary ID** at exactly
**`[seed,fingerprint]`** (no literals / no network). Policies are token-less and selected by **S0-sealed `path+sha256_hex`** (`partition={}`).
**Fail →** ⟨2B-S8-020 DICTIONARY_RESOLUTION_ERROR⟩ / ⟨2B-S8-021 PROHIBITED_LITERAL_PATH⟩ / ⟨2B-S8-023 NETWORK_IO_ATTEMPT⟩.

**V-03 — Seed set discovery (intersection, non-empty)**
**Check:** Required seeds = **intersection** of seeds present in `s2_alias_index`, `s3_day_effects`, `s4_group_weights` at this fingerprint; result is **non-empty** and deterministically ordered (ASCII-lex on decimal).
**Fail →** ⟨2B-S8-030 SEED_SET_EMPTY_OR_INCOHERENT⟩. 

**V-04 — S7 coverage & status**
**Check:** For **each** required seed, `s7_audit_report@[seed,fingerprint]` exists, validates `#/validation/s7_audit_report_v1`, and `summary.overall_status == "PASS"`. (WARN allowed unless policy forbids.)
**Fail →** ⟨2B-S8-031 S7_REPORT_NOT_PASS⟩ / ⟨2B-S8-032 S7_REPORT_MISSING⟩. 

**V-05 — Sealed-digest parity (policies only)**
**Check:** For S2/S3/S4/policies, the `(path, partition, sha256_hex)` echoed from `sealed_inputs_v1` **equals** what S8 resolves (no drift).
**Fail →** ⟨2B-S8-033 SEALED_DIGEST_MISMATCH⟩. 

**V-06 — Index schema (fields-strict)**
**Check:** `index.json` validates the **bundle index law** (`{path, sha256_hex}`, `path` **relative**, no `..`/leading `/`, entries **ASCII-lex by path**, no duplicates).
**Fail →** ⟨2B-S8-040 INDEX_SCHEMA_INVALID⟩ / ⟨2B-S8-041 INDEX_NOT_ASCII_LEX⟩ / ⟨2B-S8-042 INDEX_PATH_NOT_RELATIVE⟩ / ⟨2B-S8-044 INDEX_DUPLICATE_PATH⟩. 

**V-07 — Index coverage**
**Check:** Every `path` listed in `index.json` **exists** under the bundle root; `_passed.flag` is **not** listed.
**Fail →** ⟨2B-S8-043 INDEX_ENTRY_MISSING_FILE⟩ / ⟨2B-S8-045 FLAG_LISTED_IN_INDEX⟩. 

**V-08 — Per-file digest parity**
**Check:** For each index row, recorded `sha256_hex` equals **SHA-256(raw bytes)** of that file.
**Fail →** ⟨2B-S8-050 FILE_DIGEST_MISMATCH⟩. 

**V-09 — Flag schema & bundle digest**
**Check:** `_passed.flag` is exactly one ASCII line `sha256_hex = <hex64>` and its value equals **SHA-256(concat(indexed file bytes in ASCII-lex path order))**.
**Fail →** ⟨2B-S8-051 FLAG_DIGEST_MISMATCH⟩ / ⟨2B-S8-052 FLAG_SCHEMA_INVALID⟩. 

**V-10 — Publish partition & identity**
**Check:** Bundle published at **`…/validation/fingerprint={manifest_fingerprint}/`** (fingerprint-only); no `seed`/`run` tokens in the publish path; any lineage echoed inside included evidence matches its path tokens (path↔embed equality).
**Fail →** ⟨2B-S8-060 PARTITION_LAW_VIOLATION⟩ / ⟨2B-S8-061 PATH_EMBED_MISMATCH⟩.

**V-11 — Write-once, atomic publish, idempotent re-emit**
**Check:** Publish is via **single atomic move**; if target exists, emitted bytes are **identical**; single logical writer.
**Fail →** ⟨2B-S8-080 IMMUTABLE_OVERWRITE⟩ / ⟨2B-S8-081 NON_IDEMPOTENT_REEMIT⟩ / ⟨2B-S8-082 ATOMIC_PUBLISH_FAILED⟩. 

**V-12 — Prohibitions**
**Check:** No network I/O; no literal paths; no RNG anywhere in S8.
**Fail →** ⟨2B-S8-023 NETWORK_IO_ATTEMPT⟩ / ⟨2B-S8-021 PROHIBITED_LITERAL_PATH⟩ / ⟨2B-S8-090 RNG_USED⟩. 

---

### Validator → code map (authoritative)

| Validator                               | Codes on fail                              |
|-----------------------------------------|--------------------------------------------|
| **V-01 Gate evidence**                  | 2B-S8-001                                  |
| **V-02 S0-evidence & Dictionary-only**  | 2B-S8-020, 2B-S8-021, 2B-S8-023            |
| **V-03 Seed discovery**                 | 2B-S8-030                                  |
| **V-04 S7 coverage & PASS**             | 2B-S8-031, 2B-S8-032                       |
| **V-05 Sealed-digest parity (policies only)** | 2B-S8-033                                  |
| **V-06 Index schema**                   | 2B-S8-040, 2B-S8-041, 2B-S8-042, 2B-S8-044 |
| **V-07 Index coverage**                 | 2B-S8-043, 2B-S8-045                       |
| **V-08 Per-file digests**               | 2B-S8-050                                  |
| **V-09 Flag & bundle digest**           | 2B-S8-051, 2B-S8-052                       |
| **V-10 Publish partition & identity**   | 2B-S8-060, 2B-S8-061                       |
| **V-11 Write-once/atomic/idempotent**   | 2B-S8-080, 2B-S8-081, 2B-S8-082            |
| **V-12 Prohibitions**                   | 2B-S8-023, 2B-S8-021, 2B-S8-090            |

> Passing **V-01…V-12** proves that S8 **packages** a deterministic, fingerprint-scoped validation bundle with a canonical `index.json` and `_passed.flag`, that **all required seeds passed S7**, and that publishing obeys **write-once + atomic** with **no RNG** or out-of-band reads.

---

## 10. **Failure modes & canonical error codes (Binding)**

> **Severity classes:** **Abort** (hard stop; S8 MUST NOT publish) and **Warn** (record + continue).
> All codes below are **stable identifiers**; their meaning MUST NOT change within a major.
> Shapes/partitions referenced here are governed by the **bundle index law** + **flag** anchors, the **2B** pack (S7/S2/S3/S4/policies), and the **Dataset Dictionary**.

### 10.1 Gate & catalogue discipline

**2B-S8-001 — S0_RECEIPT_MISSING** · *Abort*
**Trigger:** `s0_gate_receipt_2B` and/or `sealed_inputs_v1` absent/invalid at `[fingerprint]`.
**Detect:** V-01. **Remedy:** publish valid S0 for this fingerprint; fix schema/partition.

**2B-S8-020 — DICTIONARY_RESOLUTION_ERROR** · *Abort*
**Trigger:** Any read not resolved by **Dataset Dictionary ID** (wrong ID/path family/format).
**Detect:** V-02. **Remedy:** resolve by ID only; correct ID/path family.

**2B-S8-021 — PROHIBITED_LITERAL_PATH** · *Abort*
**Trigger:** Literal filesystem/URL access attempted.
**Detect:** V-02. **Remedy:** replace with Dictionary-ID resolution.

**2B-S8-023 — NETWORK_IO_ATTEMPT** · *Abort*
**Trigger:** Any network access during S8.
**Detect:** V-02. **Remedy:** consume only sealed artefacts.

---

### 10.2 Seed coverage & S7 status

**2B-S8-030 — SEED_SET_EMPTY_OR_INCOHERENT** · *Abort*
**Trigger:** Intersection of seeds across `s2_alias_index`, `s3_day_effects`, `s4_group_weights` is empty or non-deterministic.
**Detect:** V-03. **Remedy:** fix upstream generation; ensure all required seeds exist across S2/S3/S4.

**2B-S8-032 — S7_REPORT_MISSING** · *Abort*
**Trigger:** A required seed lacks `s7_audit_report@[seed,fingerprint]`.
**Detect:** V-04. **Remedy:** run S7 for that seed; republish S7 report.

**2B-S8-031 — S7_REPORT_NOT_PASS** · *Abort*
**Trigger:** `summary.overall_status ≠ "PASS"` for any required seed.
**Detect:** V-04. **Remedy:** address S7 failures; re-audit; re-run S8.

---

### 10.3 Sealed-input parity

**2B-S8-033 — SEALED_DIGEST_MISMATCH** · *Abort*
**Trigger:** `(path, partition, sha256_hex)` for S2/S3/S4/policies do not match S0’s sealed inventory.
**Detect:** V-05. **Remedy:** correct drift (re-seal via S0) or fix catalogue entries.

---

### 10.4 Index law (schema, ordering, coverage)

**2B-S8-040 — INDEX_SCHEMA_INVALID** · *Abort*
**Trigger:** `index.json` fails the canonical index anchor (missing/extra fields, wrong types).
**Detect:** V-06. **Remedy:** re-materialise index per anchor.

**2B-S8-041 — INDEX_NOT_ASCII_LEX** · *Abort*
**Trigger:** Entries not sorted **ASCII-lex by `path`**.
**Detect:** V-06. **Remedy:** sort strictly ASCII-lex.

**2B-S8-042 — INDEX_PATH_NOT_RELATIVE** · *Abort*
**Trigger:** An index `path` is absolute or contains `..`.
**Detect:** V-06. **Remedy:** emit **relative** paths under bundle root only.

**2B-S8-044 — INDEX_DUPLICATE_PATH** · *Abort*
**Trigger:** Duplicate `path` entries.
**Detect:** V-06. **Remedy:** de-duplicate; one row per file.

**2B-S8-043 — INDEX_ENTRY_MISSING_FILE** · *Abort*
**Trigger:** A listed file is not present under the bundle root.
**Detect:** V-07. **Remedy:** ensure all indexed files exist within the bundle.

**2B-S8-045 — FLAG_LISTED_IN_INDEX** · *Abort*
**Trigger:** `_passed.flag` appears in `index.json`.
**Detect:** V-07. **Remedy:** remove flag from index; regenerate digest.

---

### 10.5 Digest correctness

**2B-S8-050 — FILE_DIGEST_MISMATCH** · *Abort*
**Trigger:** An index row’s `sha256_hex` ≠ SHA-256(raw bytes at `path`).
**Detect:** V-08. **Remedy:** correct row or file; re-hash.

**2B-S8-052 — FLAG_SCHEMA_INVALID** · *Abort*
**Trigger:** `_passed.flag` is not exactly one line `sha256_hex = <hex64>`.
**Detect:** V-09. **Remedy:** re-emit per anchor.

**2B-S8-051 — FLAG_DIGEST_MISMATCH** · *Abort*
**Trigger:** Flag value ≠ SHA-256(concat(all indexed file bytes in ASCII-lex path order)).
**Detect:** V-09. **Remedy:** recompute digest; fix index or content.

---

### 10.6 Publish identity & provenance

**2B-S8-060 — PARTITION_LAW_VIOLATION** · *Abort*
**Trigger:** Publish path not fingerprint-scoped (`…/validation/fingerprint={manifest_fingerprint}/`).
**Detect:** V-10. **Remedy:** publish to canonical fingerprint path.

**2B-S8-061 — PATH_EMBED_MISMATCH** · *Abort*
**Trigger:** Identity echoed inside included evidence (e.g., S7 JSON `seed`/`fingerprint`) doesn’t match path tokens.
**Detect:** V-10. **Remedy:** fix upstream evidence; S8 never rewrites bytes.

---

### 10.7 Write-once & atomic publish

**2B-S8-080 — IMMUTABLE_OVERWRITE** · *Abort*
**Trigger:** Target bundle exists and bytes differ.
**Detect:** V-11. **Remedy:** treat as write-once; publish only byte-identical or use a new fingerprint.

**2B-S8-081 — NON_IDEMPOTENT_REEMIT** · *Abort*
**Trigger:** Re-emit for same inputs yields different bytes.
**Detect:** V-11. **Remedy:** stabilise serialisation/order; ensure deterministic rebuild.

**2B-S8-082 — ATOMIC_PUBLISH_FAILED** · *Abort*
**Trigger:** Staging/rename not atomic or post-publish verification failed.
**Detect:** V-11. **Remedy:** stage → fsync → single atomic move; verify final bytes.

---

### 10.8 Prohibitions

**2B-S8-090 — RNG_USED** · *Abort*
**Trigger:** Any RNG draw observed in S8 (should be hashing only).
**Detect:** V-12. **Remedy:** remove RNG; S8 is deterministic packaging.

---

### 10.9 Code ↔ validator map (authoritative)

| Validator (from §9)                     | Codes on fail                              |
|-----------------------------------------|--------------------------------------------|
| **V-01 Gate evidence**                  | 2B-S8-001                                  |
| **V-02 S0-evidence & Dictionary-only**  | 2B-S8-020, 2B-S8-021, 2B-S8-023            |
| **V-03 Seed discovery**                 | 2B-S8-030                                  |
| **V-04 S7 coverage & PASS**             | 2B-S8-031, 2B-S8-032                       |
| **V-05 Sealed-digest parity (policies only)** | 2B-S8-033                                  |
| **V-06 Index schema**                   | 2B-S8-040, 2B-S8-041, 2B-S8-042, 2B-S8-044 |
| **V-07 Index coverage**                 | 2B-S8-043, 2B-S8-045                       |
| **V-08 Per-file digests**               | 2B-S8-050                                  |
| **V-09 Flag & bundle digest**           | 2B-S8-051, 2B-S8-052                       |
| **V-10 Publish partition & identity**   | 2B-S8-060, 2B-S8-061                       |
| **V-11 Write-once/atomic/idempotent**   | 2B-S8-080, 2B-S8-081, 2B-S8-082            |
| **V-12 Prohibitions**                   | 2B-S8-023, 2B-S8-021, 2B-S8-090            |

> These codes make S8 enforce what it’s for: **package, don’t re-audit**; **index/flag** must be canonical; **digests** must match bytes; publish is **fingerprint-scoped, write-once, atomic**; and **all required seeds** must already have **S7 = PASS**.

---

## 11. **Observability & run-report (Binding)**

**11.1 Purpose**
Emit a single **diagnostic** JSON run-report to **STDOUT** that proves *what S8 read, what it packaged, and why the bundle is PASS*. The **authoritative** artefacts are the bundle’s `index.json` and `_passed.flag`; the run-report is **non-authoritative**.

**11.2 Emission rules (binding)**

* Print **exactly one** JSON object to **STDOUT** upon success (and on abort, if possible). Persisted copies (if any) are **non-authoritative**.
* The bundle itself is published fingerprint-scoped under `…/validation/fingerprint={manifest_fingerprint}/` via **single atomic move** (write-once; idempotent re-emit must be byte-identical). 

**11.3 Fields-strict run-report shape (binding)**
S8 MUST emit a JSON with **exactly** the keys below (no extras). Types reuse layer `$defs` (`hex64`, `uint64`, `rfc3339_micros`).

```
{
  "component": "2B.S8",
  "fingerprint": "<hex64>",
  "created_utc": "<rfc3339_micros>",               // echo S0.receipt.verified_at_utc
  "catalogue_resolution": {
    "dictionary_version": "<semver>",
    "registry_version": "<semver>"
  },
  "seed_coverage": {
    "rule": "intersection(s2_alias_index, s3_day_effects, s4_group_weights)",
    "seeds_discovered": ["<uint64>", ...],         // ASCII-lex order
    "required_count": <int>,
    "s7_pass_count": <int>,
    "missing_or_fail_count": <int>
  },
  "inputs_digest": {                                // policies echo from S0; S2/S3/S4 record resolved (path, partition);
    "s2_alias_index": { "path": "<...>", "partition": {"seed":"…","fingerprint":"…"}, "sha256_hex":"<hex64>" },
    "s2_alias_blob":  { "path": "<...>", "partition": {"seed":"…","fingerprint":"…"}, "sha256_hex":"<hex64>" },
    "s3_day_effects": { "path": "<...>", "partition": {"seed":"…","fingerprint":"…"}, "sha256_hex":"<hex64>" },
    "s4_group_weights": { "path": "<...>", "partition": {"seed":"…","fingerprint":"…"}, "sha256_hex":"<hex64>" },
    "policies": {
      "alias_layout_policy_v1": { "path":"<...>", "sha256_hex":"<hex64>" },
      "route_rng_policy_v1":    { "path":"<...>", "sha256_hex":"<hex64>" },
      "virtual_edge_policy_v1": { "path":"<...>", "sha256_hex":"<hex64>" }
    }
  },
  "bundle": {
    "publish_path": "data/layer1/2B/validation/fingerprint=<fingerprint>/",
    "index_path": "…/index.json",
    "flag_path":  "…/_passed.flag",
    "files_indexed": <int>,                         // rows in index.json
    "bytes_indexed_total": <uint64>,
    "index_ascii_lex": true,                        // validated
    "flag_excluded_from_index": true,               // validated
    "bundle_digest": "<hex64>",                     // computed SHA-256(concat bytes in index order)
    "flag_digest_matches": true                     // validated
  },
  "validators": [ { "id": "V-06", "status": "PASS|FAIL", "codes": ["2B-S8-040"], "context": {} }, … ],
  "summary": { "overall_status": "PASS|FAIL", "warn_count": <int>, "fail_count": <int> }
}
```

* `created_utc` **must** echo S0 `verified_at_utc`. 
* `seed_coverage.rule` **must** document the deterministic **intersection** rule used in §3.2 and list seeds in **ASCII-lex** order. 
* `inputs_digest` policy entries **must** mirror S0’s sealed `(path, sha256_hex)`; for S2/S3/S4, record the resolved `(path, partition)`
  and any available digests from their own metadata (e.g., `s2_alias_index.blob_sha256`). 
* `bundle.*` proves index/flag conformance to the **canonical index law** and **flag law**.

**11.4 Required reconciliations (binding)**
The run-report MUST document these and S8 MUST enforce them before publish:

* `index_ascii_lex == true` (rows sorted by `path`), every `path` **relative**, no duplicates; `_passed.flag` **not** listed. 
* For each index row, `sha256_hex == SHA-256(raw bytes at path)`.
* `bundle_digest == SHA-256(concat(all indexed bytes in ASCII-lex path order))`.
* `flag_digest_matches == true` (the flag’s value equals `bundle_digest`). 

**11.5 Prohibitions & scope reminders**

* S8 writes **no** run-scoped logs; it only publishes the fingerprint-scoped bundle (`index.json` + `_passed.flag`) via **write-once + atomic** publish. 
* **No network I/O, no literal paths**; all reads are **Dictionary-resolved** sealed artefacts. 

> This run-report makes S8 transparent and reproducible: it shows the **seed set**, the **sealed inputs** echoed from S0, the **exact files indexed**, and the **flag/bundle digest** proof—while the authoritative evidence remains the fingerprint-scoped **index/flag pair** governed by the canonical bundle laws.

---

## 12. **Performance & scalability (Informative)**

**Goal.** Make S8 a **streaming, RNG-free** packager whose work is linear in the total size of files it bundles and whose output bytes are **bit-stable** across re-runs.

### 12.1 Cost model (per fingerprint)

* **Discovery & checks:** set operations over seed lists in S2/S3/S4 → **O(#seeds)**.
* **Audit presence:** existence/shape checks for `s7_audit_report@[seed,fingerprint]` → **O(#seeds)**.
* **Hashing & index:** stream-hash each included file once → **O(total_indexed_bytes)**.
* **Flag:** one reduction over per-file digests/bytes in **ASCII-lex** order → linear in index size.

### 12.2 Memory envelope

* Constant space for hashing (fixed-size chunk buffer, e.g., 8–32 MiB).
* Small, deterministic metadata structures: list of relative paths + their digests (fits in memory; if not, spill-sort by path).
* No materialisation of large inputs (S2 blob, S7 reports) beyond stream buffers.

### 12.3 I/O strategy (deterministic & single-pass)

* **Copy/link-then-hash:** while copying (or hard-linking) each file into the workspace, compute SHA-256 on the fly—avoids a second read.
* **Path canonicalisation:** emit **relative, UTF-8** paths with no leading `/` and no `..`. Normalise exactly once at materialisation.
* **Index build:** collect `{path, sha256_hex}` pairs, then sort **ASCII-lex** by `path` for the final index.

### 12.4 Parallelism (safe patterns)

* **Per-file hashing** may run in parallel; ensure the **final index** is strictly **ASCII-lex** and the **bundle digest** concatenates bytes in that order.
* **Do not** parallelise in ways that change bytes-on-disk (e.g., concurrent writers): there is a **single logical writer** for the bundle; publish is a single atomic move.

### 12.5 Early exits (fail fast)

* Abort before heavy I/O when: S0 missing, seed intersection empty, any required S7 missing or not PASS, or sealed-digest parity fails. This keeps wasted hashing near zero.

### 12.6 Determinism knobs (recommended)

* Fix JSON serialiser behaviour (key order, whitespace) so `index.json` bytes are stable.
* Sort seeds and index entries with a locale-independent **bytewise ASCII** comparator.
* Treat all hashing inputs as **raw bytes**; do not transcode line endings.

### 12.7 Sharding & CI posture

* Shard **across fingerprints** (embarrassingly parallel). Within a fingerprint, you may pipeline: discover → copy/hash → index/flag → publish.
* Nightly CI: full re-pack; PR CI: dry-run through discovery + S7 checks + synthetic index assertions (no copy) to prove determinism without I/O.

### 12.8 Large bundles (many seeds / big files)

* Use spill-sort if the index cannot fit in memory; external merge sort still yields the same **ASCII-lex** order.
* Hash chunk size is a throughput knob only; output remains identical regardless of chunking.

### 12.9 What S8 never does

* **No RNG.**
* **No network I/O.**
* **No mutation** of evidence bytes; the bundle is **write-once, atomic**; re-emit must be **byte-identical**.

> Net: S8 is linear-time in the size of what it packages, constant-space aside from the index list, and fully deterministic—so re-running with the same sealed inputs always yields the same `index.json` and `_passed.flag`.

---

## 13. **Change control & compatibility (Binding)**

**13.1 Versioning (SemVer) — what bumps what**

* **MAJOR** when any binding interface changes:

  * **Index/flag law** (fields, relative‐path rule, ASCII-lex order, or digest algorithm), or listing `_passed.flag` in the index.
  * **Partition law** (anything other than fingerprint-only for the bundle).
  * **Seed discovery rule** (e.g., changing the required set from **intersection**), or the **S7 requirement** (e.g., requiring WARN-free when previously allowed).
  * **Required inputs/IDs** or their path families; switching away from **Dictionary-only** resolution.
  * **Report dependencies**: making S7 optional, or removing S7 PASS as a precondition.
  * Introducing **RNG** into S8.

* **MINOR** for backward-compatible additions that **do not change pass/fail semantics** and keep index/flag law intact:

  * Optional **run-report** fields.
  * Optional **evidence snapshots** placed in the bundle **only if** they are part of the sealed inputs for this fingerprint (i.e., the sealed set—and thus the bundle bytes—are expected to change because the **fingerprint** changes).
  * Descriptions/help text in schemas; non-required object members in schema anchors (fields-strict keys unchanged).

* **PATCH** for typos, clarifications, non-semantic schema description edits; **no** shape, law, or output-byte changes.

**13.2 Compatibility surface (stable within S8 v1.x)**

Consumers **MAY rely** on the following remaining stable across 1.x:

* **Publish identity:** bundle lives at
  `data/layer1/2B/validation/fingerprint={manifest_fingerprint}/` (fingerprint-only). 
* **Index law:** `index.json` is a fields-strict array of `{path, sha256_hex}` with **relative** paths, **ASCII-lex** order, no duplicates; `_passed.flag` **excluded**. 
* **Flag law:** `_passed.flag` is exactly `sha256_hex = <hex64>`, where the value equals **SHA-256(concat(all indexed bytes in ASCII-lex path order))**. 
* **Prerequisites:** S0 present; **every required seed** (intersection of S2/S3/S4) has **S7 PASS** at `[seed,fingerprint]`; S8 does **not** re-audit.
* **Catalogue discipline:** **Dictionary-only** resolution; policies selected by **S0-sealed path + sha256** (`partition = {}`); **no network I/O**.
* **Write policy:** single writer; **write-once + atomic publish**; idempotent re-emit must be **byte-identical**. 

**13.3 Backward-compatible (MINOR) changes**

Allowed without breaking consumers **provided idempotence is preserved for a given fingerprint**:

* Add optional keys to the **STDOUT run-report** (diagnostic only).
* Add optional **schema descriptions** or non-required members to anchors (fields-strict required keys unchanged).
* Allow **additional evidence files** only when the sealed input set (and therefore the **fingerprint**) changes; i.e., do **not** change bundle contents for an unchanged fingerprint.

**13.4 Breaking (MAJOR) changes**

Require a coordinated **major** for S8 and contract packs:

* Change **hash algorithm**, relative-path rule, or ASCII-lex ordering.
* Change bundle **partitioning** or publish location.
* Change **seed discovery** rule or the **S7 PASS** requirement.
* Add/remove **required** files in the bundle or include `_passed.flag` in the index.
* Make network/literal-path access permissible, or introduce RNG.

**13.5 Coordination with neighbouring states/packs**

* **S7**: Any change to `s7_audit_report_v1` **required keys** or PASS semantics is **MAJOR** for S8 (V-04 depends on it).
* **S2/S3/S4**: Internal implementation may evolve, but anchors, partition law, and the presence used by the intersection rule must remain stable; changing those anchors or partitions is **MAJOR**. 
* **S0**: Sealing format/anchors must remain stable; otherwise S8’s sealed-digest parity (V-05) breaks. 
* **Bundle index/flag anchors**: must stay canonical; moving them or altering shape is **MAJOR**.

**13.6 Dictionary/Registry coordination**

* **Required IDs:** `validation_bundle_2B` (index) and `validation_passed_flag_2B` (flag) must be present with fingerprint-only partitioning and write-once/atomic metadata in the Registry. Any rename, path-family change, or partition change is **MAJOR**. 
* **Optional:** run-report is diagnostic; not catalogued.

**13.7 Deprecation & migration protocol**

* Publish a **change log** detailing: index/flag law diffs, validator diffs, schema diffs, and migration steps.
* For MAJOR transitions, prefer **dual-acceptance** windows in consumers (e.g., accept `index_schema_v1` and `index_schema_v2`) and provide a shim tool to regenerate the new index from existing bytes when feasible.

**13.8 Rollback policy**

* Bundles are **write-once**; rollback = publish a new fingerprint (or revert to a prior fingerprint) that reproduces last-known-good contents. No in-place mutation of an existing bundle.

**13.9 No new authorities**

* S8 introduces **no new shape authorities** beyond the canonical **index** and **flag** anchors; inputs remain governed by 2B/Layer packs; **ID→path/partitions** remain governed by the **Dataset Dictionary**; the **Artefact Registry** stays metadata-only.

> Net: S8 remains a **deterministic, RNG-free packager** with a **fingerprint-scoped** bundle whose **index/flag** laws, **S7 PASS** precondition, and **write-once/atomic** publish are the stable contract. Any change that would alter those guarantees is a coordinated **MAJOR**.

---

## Appendix A — Normative cross-references *(Informative)*

**A.1 Shape authorities (packs)**

* **Bundle laws (canonical):**
  • **Index schema:** `schemas.1A.yaml#/validation/validation_bundle.index_schema` (array of `{path, sha256_hex}`; paths **relative**; entries **ASCII-lex**).
  • **PASS flag:** `schemas.1B.yaml#/validation/passed_flag` (single line `sha256_hex = <hex64>`; **flag not indexed**).
* **2B pack (segment surfaces):** `schemas.2B.yaml` — `#/validation/s7_audit_report_v1` (S7 report), plus S2/S3/S4 plan/binary anchors and policy anchors.
* **Layer-1 pack (only if needed for provenance checks elsewhere):** common `$defs` (e.g., `hex64`, `uint64`, `rfc3339_micros`).

---

**A.2 2B anchors S8 references (read-only evidence)**

* **S0 evidence:** `#/validation/s0_gate_receipt_2B`, `#/validation/sealed_inputs_v1` (fingerprint-scoped provenance).
* **S7 audit:** `#/validation/s7_audit_report_v1` (one per seed at `[seed,fingerprint]`).
* **Plans/Binary:**
  • `#/plan/s2_alias_index` · `#/binary/s2_alias_blob`
  • `#/plan/s3_day_effects`
  • `#/plan/s4_group_weights`
* **Policies (token-less; S0-sealed path+digest):**
  • `#/policy/alias_layout_policy_v1`
  • `#/policy/route_rng_policy_v1`
  • `#/policy/virtual_edge_policy_v1`

---

**A.3 Dataset Dictionary IDs & partitions (catalogue authority)**

* **Inputs (read-only):**
  • `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights` → **`[seed, fingerprint]`**
  • `s7_audit_report` → **`[seed, fingerprint]`**
  • Policies `alias_layout_policy_v1`, `route_rng_policy_v1`, `virtual_edge_policy_v1` → **token-less** (`partition = {}`), **selected by S0-sealed path+sha256**
  • S0 evidence (`s0_gate_receipt_2B`, `sealed_inputs_v1`) → **`[fingerprint]`**
* **Outputs (authoritative):**
  • `validation_bundle_2B` → `…/fingerprint={manifest_fingerprint}/index.json` (**`[fingerprint]`**; `format: json`; `schema_ref: …#/validation/validation_bundle.index_schema`)
  • `validation_passed_flag_2B` → `…/fingerprint={manifest_fingerprint}/_passed.flag` (**`[fingerprint]`**; `format: text`; `schema_ref: …#/validation/passed_flag`)

---

**A.4 Artefact Registry (metadata only)**

* Mirror Dictionary entries for `validation_bundle_2B` and `validation_passed_flag_2B` with `write_once: true` and `atomic_publish: true`.
* Registry records **owners/licence/retention**; shapes/partitions stay governed by the schema pack and Dictionary.

---

**A.5 Deterministic rules (law references)**

* **Seed discovery:** deterministic **intersection** of seeds present in `s2_alias_index`, `s3_day_effects`, `s4_group_weights` for the fingerprint; seeds listed **ASCII-lex**.
* **Index law:** entries `{path, sha256_hex}`; `path` **relative**; entries **ASCII-lex by `path`**; no duplicates; every file exists under bundle root; **do not index `_passed.flag`**.
* **Flag law:** value equals **SHA-256(concat(indexed file bytes in ASCII-lex path order))**.
* **Identity & publish:** bundle is **fingerprint-scoped**, **write-once**, published by **single atomic move**; idempotent re-emit must be **byte-identical**.
* **Prohibitions:** **RNG-free**; **no network I/O**; **no literal paths**; S8 **does not re-audit** (S7 is authoritative).

---

**A.6 Recommended bundle layout (non-authoritative)**

* `reports/seed={seed}/s7_audit_report.json` (one per seed)
* `evidence/s0/{s0_gate_receipt_2B.json, sealed_inputs_v1.json}`
* `evidence/refs/{policies|s2|s3|s4}/…` (optional snapshots)

> These cross-references pin S8’s authority chain: canonical **index/flag** laws for the bundle; 2B and S0/S7 anchors for evidence; Dictionary IDs for selection & partitions; and Registry metadata for write-once/atomic publish.

---
