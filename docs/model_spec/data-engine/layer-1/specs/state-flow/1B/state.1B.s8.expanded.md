# State-8 — Egress `site_locations` (deterministic publish)

# 1) Document metadata & status **(Binding)**

**State ID (canonical):** `layer1.1B.S8` — *Egress publish: `site_locations` (order-free).*
**Document type:** Contractual specification (behavioural + data contracts; no code/pseudocode). **Shapes** are owned by JSON-Schema; **IDs→paths/partitions/writer policy** resolve via the Dataset Dictionary; provenance/licence/operational notes live in the Artefact Registry. Implementations **MUST NOT** hard-code paths.

## 1.1 Status & governance

**Status:** planning → alpha → beta → **stable** (governance-controlled).
**Precedence (tie-break):** **Schema** ≻ **Dictionary** ≻ **Registry** ≻ **this state spec**. If Dictionary prose and Schema ever disagree on **shape**, **Schema wins**; Dictionary governs **paths/partitions/writer policy**. 

## 1.2 Normative language (RFC 2119/8174)

Key words **MUST, MUST NOT, SHALL, SHALL NOT, SHOULD, SHOULD NOT, MAY** are normative. Unless explicitly labelled *Informative*, all clauses are **Binding**. 

## 1.3 Compatibility window (baselines assumed by S8)

S8 v1.* is written against—and assumes—these frozen surfaces:

* **Egress anchor:** `schemas.1B.yaml#/egress/site_locations` — **partitions `[seed, manifest_fingerprint]`**, writer sort `[merchant_id, legal_country_iso, site_order]`, columns_strict=true, **order-free** egress. 
* **Dictionary entry:** `site_locations` → path
  `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`, **partitioning `[seed, manifest_fingerprint]`**, writer sort `[merchant_id, legal_country_iso, site_order]`, **final_in_layer: true**. 
* **Registry stanza:** `site_locations` (egress) with role “Concrete per-outlet coordinates (order-free; join 1A S3 for inter-country order)”; notes: write-once; atomic move; file order non-authoritative. 

A **MAJOR** change to any of the above (e.g., egress partitions, writer sort, or the egress schema) requires re-ratifying S8.

## 1.4 Identity & lineage posture (state-wide)

* **Egress identity:** exactly one `{seed, manifest_fingerprint}` publish per run; egress partitions are **`[seed, manifest_fingerprint]`**. Where lineage appears both in **path** and **rows** (e.g., `manifest_fingerprint`), values **MUST** be byte-identical (path↔embed equality).
* **Order law:** Egress is **order-free**; any inter-country order remains outside 1B egress and is obtained by joining 1A S3 `candidate_rank`.
* **Publish posture:** write-once; stage → fsync → **single atomic move** into the identity partition; file order non-authoritative. 

## 1.5 Audience & scope notes

**Audience:** implementation agents, validators, and reviewers. This document binds **S8 behaviour** (deterministic transform from S7 to the egress shape and publish under the egress partition law). **Schema** remains the sole authority for egress columns; **Dictionary/Registry** bind paths/partitions/writer policy and operational posture.

---

Here’s **Section 2 — Purpose & scope (Binding)** for **L1·1B·S8**.

### Contract Card (S8) - inputs/outputs/authorities

**Inputs (authoritative; see Section 3.2 for full list):**
* `s7_site_synthesis` - scope: SEED+FINGERPRINT+PARAMETER; source: 1B.S7

**Authority / ordering:**
* Egress is order-free; inter-country order remains outside 1B egress.

**Outputs:**
* `site_locations` - scope: EGRESS_SCOPED; gate emitted: none (gated by S9 bundle)

**Sealing / identity:**
* External inputs (ingress/reference/1A egress) MUST appear in `sealed_inputs_1B` for the target `manifest_fingerprint`.

**Failure posture:**
* Missing required inputs or schema violations -> abort; no outputs published.


# 2) Purpose & scope **(Binding)**

**Mission.** S8 **publishes** the 1B egress dataset **`site_locations`** by transforming the S7 per-site synthesis into the **egress shape** and writing it under the **order-free** identity **`[seed, manifest_fingerprint]`**. S8 is **deterministic** and **RNG-free**; it MUST NOT encode inter-country order (downstreams join 1A S3 when order is required).

## 2.1 In-scope (what S8 SHALL do)

* **Row mapping (S7 → S8).** For every site key `(merchant_id, legal_country_iso, site_order)` in **S7**, select/map fields to the egress anchor **`#/egress/site_locations`** (Schema-owned). 
* **Partition shift.** Write to `site_locations` under **`data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`** (drop `parameter_hash` from partitions; fingerprint subsumes parameters). 
* **Writer discipline.** Publish in writer sort `[merchant_id, legal_country_iso, site_order]`; treat **file order as non-authoritative**; publish via stage → fsync → **single atomic move**.
* **Parity.** Ensure **1:1** row parity with S7’s keyset (S8 emits exactly one row per S7 row). 

## 2.2 Out of scope (what S8 SHALL NOT do)

* **No RNG or re-sampling.** SHALL NOT consume RNG or alter coordinates decided upstream.
* **No inter-country order.** SHALL NOT encode or imply cross-country order (egress remains order-free). 
* **No 1A reads or bundle packaging.** SHALL NOT read 1A surfaces nor produce/modify validation bundles; S8 only publishes egress rows. 

## 2.3 Success definition (pointer)

S8 is successful only if the acceptance suite in **§9** passes: **row parity S7↔S8**, **egress schema conformance**, **partition & path↔embed equality**, **writer-sort discipline**, and **order-free pledge**.

---

# 3) Preconditions & sealed inputs **(Binding)**

## 3.1 Run identity is sealed before S8

S8 executes under a fixed lineage tuple **`{seed, manifest_fingerprint, parameter_hash, run_id}`** for the run. Egress publishes under **`[seed, manifest_fingerprint]`**; any lineage fields embedded in rows (e.g., `manifest_fingerprint`, if present) **MUST** byte-equal the corresponding **path tokens** (`manifest_fingerprint=…`).

## 3.2 Upstream dataset required (for this identity)

S8 SHALL read **only** the following sealed input for **this** `{seed, manifest_fingerprint, parameter_hash}`:

* **S7 — `s7_site_synthesis`** (deterministic per-site absolutes; RNG-free)
  **Path family:** `data/layer1/1B/s7_site_synthesis/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/`
  **Partitions / writer sort:** `[seed, manifest_fingerprint, parameter_hash]`; `[merchant_id, legal_country_iso, site_order]`.
  **Shape authority:** `schemas.1B.yaml#/plan/s7_site_synthesis`. 

*(S8 does not read S1 or 1A surfaces; S7 has already produced conformed per-site rows.)*

## 3.3 Egress target identity (preview)

S8 MUST publish **`site_locations`** at
`data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` with **partitions `[seed, manifest_fingerprint]`** and **writer sort `[merchant_id, legal_country_iso, site_order]`**. The egress dataset is **order-free**.

## 3.4 Resolution rule (no literal paths)

Implementations **SHALL** resolve dataset **IDs → path families, partitions, writer policy** exclusively via the **Dataset Dictionary**. Hard-coded paths are non-conformant. 

## 3.5 Publish posture & immutability

Egress is **write-once** per identity; publish via **stage → fsync → single atomic move**; **file order is non-authoritative**. This posture is binding for `site_locations`. 

## 3.6 Fail-closed access

S8 **SHALL NOT** read any surface other than **`s7_site_synthesis`**. Attempting to read priors, policies, alternative geometries, or RNG logs is a validation failure for this state. (S7 is the only upstream dependency for `site_locations` in Dictionary/Registry.)

---

# 4) Inputs & authority boundaries **(Binding)**

## 4.1 Authority stack (precedence)

* **Shape authority:** `schemas.1B.yaml` anchors — **`#/plan/s7_site_synthesis`** (upstream) and **`#/egress/site_locations`** (this state). 
* **IDs → paths/partitions/writer policy:** **Dataset Dictionary** — `s7_site_synthesis` under `[seed, manifest_fingerprint, parameter_hash]`; `site_locations` under `[seed, manifest_fingerprint]`. 
* **Provenance/operational posture:** **Artefact Registry** — write-once, atomic move, file order non-authoritative; egress role “order-free; join 1A S3 for inter-country order.” 

## 4.2 Bound input (sealed for this identity)

S8 SHALL read **only**:

* **`s7_site_synthesis`** — deterministic per-site absolutes (RNG-free).
  **Shape:** `schemas.1B.yaml#/plan/s7_site_synthesis` · **Path family/identity:** `…/s7_site_synthesis/seed={seed}/manifest_fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` · **Partitions:** `[seed, manifest_fingerprint, parameter_hash]` · **Writer sort:** `[merchant_id, legal_country_iso, site_order]`.

## 4.3 Egress target (authoritative output surface)

* **`site_locations`** — egress dataset.
  **Shape:** `schemas.1B.yaml#/egress/site_locations` · **Path family/identity:** `…/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` · **Partitions:** `[seed, manifest_fingerprint]` · **Writer sort:** `[merchant_id, legal_country_iso, site_order]` · **Final in layer:** **true**.

## 4.4 Order authority (what S8 MUST NOT encode)

Egress is **order-free**. Any inter-country ordering is obtained downstream by joining **1A S3 `candidate_rank`** (Dictionary text: “order-free; join S3”). S8 SHALL NOT encode or imply cross-country order. 

## 4.5 Resolution rule (no literal paths)

Implementations SHALL resolve all dataset **IDs → path families, partitions, writer policy** exclusively via the **Dataset Dictionary**; Schema remains the sole shape authority; Registry sets operational posture.

## 4.6 Prohibited surfaces (fail-closed)

S8 SHALL NOT read any surface other than **`s7_site_synthesis`**. The egress Registry stanza lists **only** `s7_site_synthesis` as a dependency for `site_locations`; reading priors, policies, S1 geometry, RNG logs, or any other surface in S8 is non-conformant. 

---

# 5) Outputs (datasets) & identity **(Binding)**

## 5.1 Egress dataset — `site_locations`

**ID → Schema:** `site_locations` → `schemas.1B.yaml#/egress/site_locations` (**columns_strict=true**; Schema owns exact columns). 

**Path family (Dictionary):**
`data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` 

**Partitions (binding):** `[seed, manifest_fingerprint]` · **Writer sort:** `[merchant_id, legal_country_iso, site_order]` · **Final in layer:** **true** · **Retention:** 365 days · **Format:** parquet. 

**Order posture:** **order-free**; consumers obtain any inter-country order by joining 1A S3 `candidate_rank` (Dictionary description). 

**Path↔embed equality (binding):** wherever lineage fields appear in rows (e.g., `manifest_fingerprint`, if present), their values **MUST** byte-equal the corresponding path tokens (`manifest_fingerprint=…`). 

**Publish posture (binding):** write-once under the identity partition; publish via **stage → fsync → single atomic move**; file order is **non-authoritative** (Registry posture for 1B datasets). 

## 5.2 Logs

S8 introduces **no** RNG/event logs; egress consists solely of the `site_locations` dataset under the path family above. 

---

# 6) Dataset shapes & schema anchors **(Binding)**

**JSON-Schema is the sole shape authority.** Implementations MUST validate against the anchors below and MUST NOT restate columns outside Schema. Paths/partitions/writer policy resolve via the **Dataset Dictionary** only.

## 6.1 Egress table (shape authority)

**ID → Schema:** `site_locations` → `schemas.1B.yaml#/egress/site_locations`.
The anchor fixes **PK** `[merchant_id, legal_country_iso, site_order]`, **partitions** `[seed, manifest_fingerprint]`, **writer sort** `[merchant_id, legal_country_iso, site_order]`, and `columns_strict: true`. 

**Dictionary binding (for the same ID):**
Path family `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`; **partitioning** `[seed, manifest_fingerprint]`; **ordering** `[merchant_id, legal_country_iso, site_order]`; `final_in_layer: true`. 

## 6.2 Referenced input anchor (read-only)

**ID → Schema:** `s7_site_synthesis` → `schemas.1B.yaml#/plan/s7_site_synthesis`.
The anchor fixes **PK** `[merchant_id, legal_country_iso, site_order]`, **partitions** `[seed, manifest_fingerprint, parameter_hash]`, **writer sort** `[merchant_id, legal_country_iso, site_order]`, and `columns_strict: true`. 

**Dictionary binding (for the same ID):**
Path family `data/layer1/1B/s7_site_synthesis/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/`; **partitioning** `[seed, manifest_fingerprint, parameter_hash]`; **ordering** `[merchant_id, legal_country_iso, site_order]`. 

## 6.3 Resolution & path law **(Binding)**

All dataset **IDs → path families / partitions / writer policy** resolve **exclusively** via the **Dataset Dictionary**; Schema remains the sole shape authority; Registry binds operational posture (write-once; atomic move; file-order non-authoritative).

*(No logs are introduced by S8; the only bound output surface is `site_locations` as above.)*

---

# 7) Deterministic algorithm (RNG-free) **(Binding)**

## 7.1 Ingress stream (fixed identity)

For the sealed identity `{seed, manifest_fingerprint, parameter_hash}`, open **S7** as a streaming, writer-sorted source:

* **ID:** `s7_site_synthesis`
* **Path family / partitions / sort (resolve via Dictionary):**
  `…/s7_site_synthesis/seed={seed}/manifest_fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` · partitions `[seed, manifest_fingerprint, parameter_hash]` · writer sort `[merchant_id, legal_country_iso, site_order]`.

## 7.2 Row mapping (S7 → S8 egress shape)

Process the S7 stream **in writer sort**. For each site key `(merchant_id, legal_country_iso, site_order)`:

1. **Select/map** the fields required by the **egress anchor** `schemas.1B.yaml#/egress/site_locations` (Schema owns exact columns; no additions here). 
2. **Carry forward** deterministic values from S7 (no RNG, no resampling, no geometry reads).
3. **Do not encode order** beyond writer sort (egress is **order-free**). 

## 7.3 Partition shift (drop parameter scope at egress)

Materialise the mapped rows to the **egress path family** with the egress identity:

* **ID:** `site_locations`
* **Path family / partitions / sort (resolve via Dictionary):**
  `…/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` · partitions `[seed, manifest_fingerprint]` · writer sort `[merchant_id, legal_country_iso, site_order]`.
  `parameter_hash` **does not** appear in the egress partition (it is subsumed by `manifest_fingerprint`). 

## 7.4 Writer discipline & stable merge

Maintain the binding writer sort throughout emission and perform a **stable merge** by `[merchant_id, legal_country_iso, site_order]` when consolidating shards. **File order is non-authoritative.** 

## 7.5 Identity & lineage law

Where lineage appears in rows (e.g., `manifest_fingerprint`, if present), it **MUST** byte-equal the corresponding **path tokens** (`manifest_fingerprint=…`) at the egress location. 

## 7.6 Publish posture

Write to a **staging** location under the target identity, **fsync**, then perform a **single atomic move** into:
`data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`. Enforce **write-once; atomic move; file order non-authoritative**. 

## 7.7 Prohibitions (fail-closed)

* **No RNG** (S8 is deterministic).
* **No extra reads**: S8 SHALL read **only** `s7_site_synthesis`; do **not** read S1/1A/prior/policy/RNG surfaces.
* **No order encoding**: inter-country order remains outside egress (join 1A S3 downstream when needed). 

*(This algorithm binds the S7→S8 pass-through into the egress shape and identity, consistent with the Schema/Dictionary/Registry contracts for `s7_site_synthesis` and order-free `site_locations`.)*

---

# 8) Identity, partitions, ordering & merge discipline **(Binding)**

## 8.1 Identity tokens (one publish per identity)

* **Egress identity:** exactly one `{seed, manifest_fingerprint}` per publish to `site_locations`. Where lineage appears in rows (e.g., an embedded `manifest_fingerprint` field), the value **MUST** byte-equal the `manifest_fingerprint=` path token (**path↔embed equality**). 
* **Execution tokens:** `run_id` is **not** part of egress identity or partitions (S8 introduces no RNG logs). 

## 8.2 Partition law & path family (resolve via Dictionary; no literal paths)

* **Dataset:** `site_locations` → `schemas.1B.yaml#/egress/site_locations`.
  **Path family:** `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
  **Partitions:** `[seed, manifest_fingerprint]` · **Writer sort:** `[merchant_id, legal_country_iso, site_order]` · **Final in layer:** **true**. 

## 8.3 Ordering posture (writer sort vs file order)

* **Binding writer sort:** rows MUST be a stable merge in `[merchant_id, legal_country_iso, site_order]`. **File order is non-authoritative.** 
* **Order-free egress:** inter-country order is **not encoded** in `site_locations`; downstreams obtain any order by joining 1A S3 `candidate_rank`.

## 8.4 Parallelism & stable merge

Parallel materialisation (e.g., by country or merchant buckets) is **permitted** iff the final dataset is the result of a **stable merge** by `[merchant_id, legal_country_iso, site_order]`, producing the same bytes regardless of worker count/scheduling. 

## 8.5 Publish posture, immutability & idempotence

Publish via **stage → fsync → single atomic move** into the identity partition. Re-publishing the same `{seed, manifest_fingerprint}` MUST be byte-identical. **Write-once; file order non-authoritative.** 

## 8.6 Path↔embed equality (lineage law)

Whenever lineage fields appear both in the **path** and **rows**, values MUST be byte-identical (e.g., `manifest_fingerprint` path token equals embedded `manifest_fingerprint`). 

## 8.7 Identity-coherence checks (must hold before publish)

* **Upstream parity:** the `{seed, manifest_fingerprint}` used for egress MUST match the upstream **S7** partition’s `{seed, manifest_fingerprint}` for the same `parameter_hash` consumed during S7→S8 mapping. 
* **Partition shift law:** egress **drops** `parameter_hash` from partitions (it is subsumed by `manifest_fingerprint` per Schema/Dictionary for `site_locations`).

## 8.8 Prohibitions (fail-closed)

* **MUST NOT** mix identities within a publish (no cross-seed or cross-fingerprint contamination). 
* **MUST NOT** encode or imply inter-country order in egress. 
* **MUST NOT** rely on file order for semantics; only writer sort governs. 

---

# 9) Acceptance criteria (validators) **(Binding)**

A run **PASSES** S8 only if **all** checks below succeed.

## A801 — Row parity S7 ↔ S8

**Rule.** `|site_locations| = |s7_site_synthesis|` and the keyset on `[merchant_id, legal_country_iso, site_order]` matches exactly (1 row in S8 per S7 row; no extras/dups).
**Detection.** Two-way anti-join on the PK; enforce PK uniqueness in S8. 

## A802 — Schema conformance (egress)

**Rule.** Every S8 row validates `schemas.1B.yaml#/egress/site_locations` (**columns_strict = true**).
**Detection.** JSON-Schema validate all egress files. 

## A803 — Partition & identity law (egress)

**Rule.** Egress is written at
`data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` with partitions **`[seed, manifest_fingerprint]`**; any embedded lineage (e.g., `manifest_fingerprint`, if present) **byte-equals** the path token (**path↔embed equality**).
**Detection.** Compare path-derived identity to embedded fields; verify Dictionary partitions.

## A804 — Writer sort

**Rule.** Non-decreasing `[merchant_id, legal_country_iso, site_order]` within each identity partition; **file order non-authoritative**.
**Detection.** Check within-file and merged partition order.

## A805 — Order-authority pledge (order-free egress)

**Rule.** S8 does **not** encode inter-country order; downstream order comes only from 1A S3 `candidate_rank` (egress is **order-free**).
**Detection.** Audit that S8 contains no ordering columns/implications beyond writer sort; cross-check Dictionary/Registry egress text.

## A806 — Dictionary/Schema coherence

**Rule.** For `site_locations`, Dictionary **path/partitions/sort** match the egress Schema anchor; no literal paths used.
**Detection.** Cross-check `schema_ref` against Dictionary entry.

## A807 — Partition shift law (S7 → S8)

**Rule.** S7 input is under `[seed, manifest_fingerprint, parameter_hash]`; S8 egress **drops `parameter_hash`** and publishes under `[seed, manifest_fingerprint]`.
**Detection.** Verify S8 `{seed,fingerprint}` equals S7’s `{seed,fingerprint}` for the consumed `{parameter_hash}`; ensure no parameter_hash appears in egress paths.

## A808 — Publish posture

**Rule.** **Write-once** per `{seed,fingerprint}`; publish via **stage → fsync → single atomic move**; **file order non-authoritative**.
**Detection.** Check publish logs and Registry posture for `site_locations`. 

## A809 — Final-in-layer flag

**Rule.** The Dictionary marks `site_locations` as **final_in_layer: true**; the produced dataset corresponds to that terminal surface.
**Detection.** Verify the Dictionary entry and that S8 writes only to that surface. 

## A810 — Resolution discipline

**Rule.** All dataset IDs (input S7 and output S8) resolve **exclusively** via the Dataset Dictionary; no hard-coded paths.
**Detection.** Inspect code/config to confirm Dictionary lookups are used for IDs → path families/partitions/sort. 

---

# 10) Failure modes & canonical error codes **(Binding)**

### E801_ROW_MISSING — Missing S8 row for an S7 key *(ABORT)*

**Trigger:** A `(merchant_id, legal_country_iso, site_order)` present in **S7** has **no** matching row in **S8**.
**Detection:** Anti-join `S7 \ S8` on the PK is empty; S7 keyset is authoritative. 

### E802_ROW_EXTRA — Extra S8 row *(ABORT)*

**Trigger:** A site key exists in **S8** that is **not** present in **S7**.
**Detection:** Anti-join `S8 \ S7` on the PK is empty. 

### E803_DUP_KEY — Duplicate primary key in S8 *(ABORT)*

**Trigger:** Duplicate `(merchant_id, legal_country_iso, site_order)` within an S8 identity partition.
**Detection:** Enforce PK uniqueness per the egress anchor `#/egress/site_locations` (columns_strict = true). 

### E804_SCHEMA_VIOLATION — Egress row fails schema *(ABORT)*

**Trigger:** Any S8 row does **not** validate `schemas.1B.yaml#/egress/site_locations`.
**Detection:** JSON-Schema validation fails (unknown/missing columns, invalid types/constraints). 

### E805_PARTITION_OR_IDENTITY — Partition/path or path↔embed mismatch *(ABORT)*

**Trigger:** Any of:

* Egress not under `…/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`, or
* embedded lineage (e.g., `manifest_fingerprint`, if present) ≠ path token.
  **Detection:** Compare path-derived `{seed,fingerprint}` to embedded fields; verify Dictionary partitions. 

### E806_WRITER_SORT_VIOLATION — Writer sort not respected *(ABORT)*

**Trigger:** Records in S8 are not in non-decreasing `[merchant_id, legal_country_iso, site_order]`.
**Detection:** Validate stable-merge order per Dictionary/Schema; file order is non-authoritative.

### E807_ORDER_LEAK — Inter-country order encoded *(ABORT)*

**Trigger:** S8 encodes or implies cross-country order beyond writer sort.
**Detection:** Audit that egress is **order-free** (Dictionary/Registry state this) and that downstream ordering is via 1A S3 `candidate_rank`.

### E808_DICT_SCHEMA_MISMATCH — Dictionary vs Schema disagreement *(ABORT)*

**Trigger:** Dictionary **path/partitions/sort** for `site_locations` do not match the egress Schema anchor, or literal paths used.
**Detection:** Cross-check `schema_ref` ↔ Dictionary entry and implementation resolution.

### E809_PARTITION_SHIFT_VIOLATION — S7→S8 identity mismatch *(ABORT)*

**Trigger:** Egress failed to **drop `parameter_hash`** from partitions, or `{seed,fingerprint}` used in S8 does not equal S7’s `{seed,fingerprint}` for the consumed `{parameter_hash}`.
**Detection:** Verify S7 input under `[seed, manifest_fingerprint, parameter_hash]` and S8 output under `[seed, manifest_fingerprint]` share identical `{seed,fingerprint}`; ensure no `parameter_hash` in egress paths.

### E810_PUBLISH_POSTURE — Not write-once / non-atomic publish *(ABORT)*

**Trigger:** Re-publishing the same `{seed,fingerprint}` is not byte-identical, or publish skipped **stage → fsync → single atomic move**.
**Detection:** Check publish logs; Registry posture requires **write-once; atomic move; file order non-authoritative**. 

### E811_FINAL_FLAG_MISMATCH — Egress not marked final *(ABORT)*

**Trigger:** Dictionary does not mark `site_locations` as **`final_in_layer: true`**, or S8 writes to a surface other than that final egress.
**Detection:** Verify Dictionary entry for `site_locations` and target surface used by S8. 

### E812_RESOLUTION_DISCIPLINE — IDs not resolved via Dictionary *(ABORT)*

**Trigger:** Implementation hard-codes paths/partitions instead of resolving dataset **IDs → path families/partitions/sort** via the Dictionary.
**Detection:** Inspect configuration/code for Dictionary-based resolution. 

---

# 11) Observability & run-report **(Binding)**

## 11.1 Required run-level summary S8 SHALL expose

Produce a single run-scoped JSON summary (non-identity-bearing) with at least:

**Identity**

```
{ "seed": u64,
  "manifest_fingerprint": "<hex64>",
  "parameter_hash_consumed": "<hex64>" }   // the S7 partition used
```

**Parity & sizes**

* `rows_s7` = |`s7_site_synthesis`| for `{seed,fingerprint,parameter_hash_consumed}`. 
* `rows_s8` = |`site_locations`| for `{seed,fingerprint}`. 
* `parity_ok` (bool) — exact keyset equality on `[merchant_id, legal_country_iso, site_order]` (S7 ↔ S8). 

**Validation counters**

* `schema_fail_count` — rows failing `#/egress/site_locations` (columns_strict). 
* `path_embed_mismatches` — any embedded lineage value ≠ path tokens at egress (`manifest_fingerprint=` ↔ `manifest_fingerprint`). 
* `writer_sort_violations` — rows out of `[merchant_id, legal_country_iso, site_order]` sort in the egress partition. 
* `order_leak_indicators` — count of prohibited order-bearing fields/implications beyond writer sort (egress is **order-free**). 

**By-country roll-up (diagnostic)**

```
by_country[ISO]: { rows_s7, rows_s8, parity_ok }
```

## 11.2 Sources this summary MUST draw from

* **Upstream input:** `s7_site_synthesis` under
  `data/layer1/1B/s7_site_synthesis/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/`
  (partitions `[seed, manifest_fingerprint, parameter_hash]`; writer sort `[merchant_id, legal_country_iso, site_order]`). 
* **Egress output:** `site_locations` under
  `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
  (partitions `[seed, manifest_fingerprint]`; writer sort `[merchant_id, legal_country_iso, site_order]`; **final_in_layer: true**; order-free). 

## 11.3 Publish & posture (binding)

* The summary MAY be persisted as a small JSON sidecar or forwarded to the downstream packaging state; it is **not** identity-bearing.
* Egress data itself is **write-once; atomic move; file order non-authoritative** — mirror the egress Registry notes. 

## 11.4 Minimal JSON shape (binding keys)

S8 SHALL expose at least the keys below (values per §11.1):

```json
{
  "identity": {
    "seed": 0,
    "manifest_fingerprint": "",
    "parameter_hash_consumed": ""
  },
  "sizes": {
    "rows_s7": 0,
    "rows_s8": 0,
    "parity_ok": false
  },
  "validation_counters": {
    "schema_fail_count": 0,
    "path_embed_mismatches": 0,
    "writer_sort_violations": 0,
    "order_leak_indicators": 0
  },
  "by_country": { "GB": { "rows_s7": 0, "rows_s8": 0, "parity_ok": true } }
}
```

*(This section binds only the summary and its sources; the authoritative egress contracts remain the Schema/Dictionary/Registry for `site_locations` and `s7_site_synthesis`.)*

---

# 12) Performance & scalability *(Informative)*

**Goal:** publish `site_locations` quickly and deterministically while honoring the egress contracts (Schema shape; Dictionary paths/partitions/writer-sort; Registry write-once/atomic-move posture).

## 12.1 Parallelism & stable merge

* **Shard safely.** Process `s7_site_synthesis` by **country** or **merchant buckets**; each worker handles a disjoint slice of the S7 keyset `(merchant_id, legal_country_iso, site_order)`. Finalise with a **stable merge** in the binding writer sort `[merchant_id, legal_country_iso, site_order]`.
* **Determinism under concurrency.** Egress bytes must not depend on worker count or scheduling; only writer sort governs, **file order is non-authoritative**. 

## 12.2 Streaming pass-through (no shuffles)

* **Stream S7 → S8.** Read S7 in writer sort and **map/select** directly into the egress shape; no joins or shuffles are required in S8. S7 identity is `[seed, manifest_fingerprint, parameter_hash]`; S8 **drops `parameter_hash`** and writes under `[seed, manifest_fingerprint]`.
* **Single-pass materialisation.** Perform the projection and partition shift in one pass to a staging area under the egress path family. 

## 12.3 I/O layout

* **Writer sort–aligned row groups.** When writing parquet, emit row groups aligned with the writer sort to improve downstream range scans over `[merchant_id, legal_country_iso, site_order]`. 
* **Partition sizing.** Keep identity partitions (`seed, manifest_fingerprint`) balanced; prefer many medium files to a few huge ones for parallel readsG��file order remains non-authoritative.

## 12.4 Memory & batching

* **Bounded memory footprint.** Use streaming readers and batched writers (tens of MB per batch) to avoid large in-memory buffers; S8 is a pure projection, so memory should scale with batch size, not dataset size.
* **Country batching.** If you shard by country, you also localise any error spikes and ease back-pressure handling in sinks.

## 12.5 Idempotent publish & retries

* **Write-once, atomic.** Stage → fsync → **single atomic move** into `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`. Retrying a failed publish must either leave no traces or produce byte-identical output for the same identity. **Do not** rely on file order for semantics. 
* **Identity guard.** Refuse to publish if a different `{seed,fingerprint}` is already present in the target partition (or if present but not byte-identical).

## 12.6 Back-pressure & throughput

* **Bounded sink queue.** Make the final move only when all parts are closed and fsynced; keep per-partition output queues bounded to avoid spiky latency.
* **Throughput knobs.** Increase writers per partition and row-group size until you meet SLOs; avoid tiny files.

## 12.7 Operational checks (cheap, helpful)

* **Pre-publish parity check.** Verify `|S7| == |S8|` by key before the atomic move (mirrors A801).
* **Partition shift sanity.** Assert that **no** `parameter_hash` directory exists under the egress path (mirrors A807). 
* **Run summary.** Emit the §11 counters (rows_s7/rows_s8/parity_ok, etc.) alongside the publish; the summary is non-identity-bearing. 

## 12.8 What S8 deliberately does **not** do

* **No RNG or geometry reads.** All RNG evidence and geometry checks are upstream; S8 is a deterministic pass-through from S7 to the egress anchor. 
* **No order encoding.** Egress remains **order-free**; downstreams obtain any inter-country order via 1A S3 `candidate_rank`. 

This guidance keeps S8 fast, deterministic, and consistent with the **Dictionary** (`site_locations` under `[seed, manifest_fingerprint]`, writer sort) and **Registry** (write-once; atomic move; file-order non-authoritative).

---

# 13) Change control & compatibility **(Binding)**

## 13.1 Versioning model (SemVer)

S8 uses **MAJOR.MINOR.PATCH**. Egress follows **write-once; stage → fsync → single atomic move; file order non-authoritative**. 

## 13.2 What counts as **MAJOR** (non-exhaustive)

Changes that can invalidate previously valid egress or alter bound interfaces:

1. **Identity / path law**

   * Changing egress **partitions** from **`[seed, manifest_fingerprint]`** or its **path family**
     `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`.
   * Changing the **writer sort** from `[merchant_id, legal_country_iso, site_order]`. 

2. **Schema-owned shape**

   * Any change to `schemas.1B.yaml#/egress/site_locations` (add/remove/rename columns, tighter constraints that can fail prior outputs; `columns_strict: true` binds shape). 

3. **Order posture**

   * Encoding or implying **inter-country order** in egress (S8 is **order-free**; order comes from 1A S3 join). 

4. **Finality & registry posture**

   * Flipping `final_in_layer` for `site_locations` or changing **write-once/atomic-move** posture.

5. **Partition-shift contract**

   * Re-introducing `parameter_hash` into egress partitions (S8 **drops** it; fingerprint subsumes parameters). 

6. **Resolution discipline**

   * Abandoning Dictionary-based resolution for IDs→paths/partitions/writer policy. 

## 13.3 What may be **MINOR** (strictly backward-compatible)

* Adding **non-identity** fields to the **run-summary** (S8 does not define a dataset for the summary).
* Clarifying **Registry notes** or **Dictionary descriptions** that do **not** alter schema, partitions, writer sort, or order-free posture.
* Non-gating validator messages or advisory diagnostics (no change to acceptance rules).

## 13.4 What is **PATCH**

Editorial fixes (typos, cross-refs, prose layout) that **do not** change behaviour, schema, paths/partitions, writer sort, acceptance, or publish posture.

## 13.5 Compatibility baselines (this spec line)

S8 v1.* assumes the following are in effect:

* **Schema:** `schemas.1B.yaml#/egress/site_locations` — **partitions `[seed, manifest_fingerprint]`**, writer sort `[merchant_id, legal_country_iso, site_order]`, `columns_strict: true`, order-free. 
* **Dictionary:** `site_locations` — path family `…/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`, **partitioning `[seed, manifest_fingerprint]`**, writer sort `[merchant_id, legal_country_iso, site_order]`, `final_in_layer: true`. 
* **Registry:** `site_locations` — role “order-free; join 1A S3”, **write-once; atomic move; file order non-authoritative**; dependency on **`s7_site_synthesis`** only. 

A **MAJOR** change to any baseline that affects these contracts requires an S8 **MAJOR** (or an explicit compatibility shim).

## 13.6 Forward-compatibility guidance

* If the egress **shape** must evolve, **add a new egress ID/anchor** (e.g., `site_locations_v2`) rather than mutating the current one; keep both lanes for ≥1 MINOR. Mark only one as `final_in_layer: true` at a time, and document the migration path. 
* If downstream requires an ordered view, provide it as a **separate analytical surface**; **do not** change `site_locations` order-free posture (consumers join 1A S3). 

## 13.7 Deprecation & migration (binding posture)

* **Dual-lane window:** When introducing a replacement egress, run old and new in parallel for at least one **MINOR**; validators MAY accept either lane if shapes are both valid.
* **Removal:** Removing the superseded lane is **MAJOR** and MUST be called out in the S8 header with a migration note.

## 13.8 Cross-state compatibility

* **Upstream handshake:** S8 consumes only **`s7_site_synthesis`** under `[seed, manifest_fingerprint, parameter_hash]`; a MAJOR in S7 that alters its **PK/partitions** or breaks parity requires S8 re-ratification.
* **Downstream neutrality:** `site_locations` is the **final** 1B surface (no further 1B states consume it); keep its identity and order-free law stable. 

---

# Appendix A — Symbols *(Informative)*

## A.1 Keysets

* **S7_keys** — exact site keyset produced by S7:
  `S7_keys = {(merchant_id, legal_country_iso, site_order)}`. S8 emits **one** egress row per S7 key. (S7 is partitioned `[seed, manifest_fingerprint, parameter_hash]` with writer sort `[merchant_id, legal_country_iso, site_order]`; S8 preserves the same writer sort under `[seed, manifest_fingerprint]`.)

## A.2 Identity & lineage tokens

* **seed** — 64-bit unsigned; partitions S7 and S8. 
* **manifest_fingerprint** — hex64 fingerprint of the run manifest; appears in the **path token** `manifest_fingerprint={manifest_fingerprint}` for S7 **and** S8.
* **parameter_hash** — hex64 for the sealed parameter bundle; partitions S7 (and S1 geometry) but is **not** in egress partitions; S8 **drops** it because the fingerprint subsumes parameters.

## A.3 Dataset IDs → path families & partitions (Dictionary law)

* **S7 — `s7_site_synthesis`**
  `data/layer1/1B/s7_site_synthesis/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/`
  Partitions `[seed, manifest_fingerprint, parameter_hash]` · Ordering `[merchant_id, legal_country_iso, site_order]`. 
* **S8 (egress) — `site_locations`**
  `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
  Partitions `[seed, manifest_fingerprint]` · Ordering `[merchant_id, legal_country_iso, site_order]` · **final_in_layer: true**. 

*(All dataset IDs resolve via the **Dataset Dictionary**; no literal paths are permitted.)* 

## A.4 Order authority

* **Order-free egress.** `site_locations` carries **no inter-country order**; downstream consumers obtain any global order by joining **1A S3 `candidate_rank`** (this is stated in the egress description). 

## A.5 Writer sort & file-order posture

* **Writer sort:** `[merchant_id, legal_country_iso, site_order]` for both S7 and S8.
* **File order:** non-authoritative; the Registry posture is **write-once; atomic move; file order non-authoritative**. 

## A.6 Identity equality (path↔embed)

Where lineage appears both as **path tokens** and **embedded fields** in rows (e.g., `manifest_fingerprint`), values MUST byte-equal; the path token is always `manifest_fingerprint=…`. (Applied across 1B planning tables and the egress.) 

## A.7 Abbreviations

* **PK** — Primary key (checked on the egress keyset per partition).
* **FK** — Foreign key.
* **RNG** — Random number generation (S8 is RNG-free; upstream RNG evidence remains in S6). 

---

*This appendix is **informative**; the authoritative contracts remain the **Schema** for shapes and the **Dataset Dictionary** for IDs→paths/partitions/writer policy (S7 and `site_locations`).*

---

# Appendix B — Worked example *(Informative)*

## B.1 Identity (fixed for this publish)

```
seed                   = 4242424242
parameter_hash         = "c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00"   # hex64
manifest_fingerprint   = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"   # hex64
```

**Input (S7) partition:**
`data/layer1/1B/s7_site_synthesis/seed=4242424242/manifest_fingerprint=deadbeef…/parameter_hash=c0ffee…/` — partitions `[seed, manifest_fingerprint, parameter_hash]`, writer sort `[merchant_id, legal_country_iso, site_order]`. 

**Output (S8 egress) partition:**
`data/layer1/1B/site_locations/seed=4242424242/manifest_fingerprint=deadbeef…/` — partitions `[seed, manifest_fingerprint]`, writer sort `[merchant_id, legal_country_iso, site_order]`, **final_in_layer: true**. 

---

## B.2 One site, through the pipe

**S7 site key** *(writer-sort PK)*
`(merchant_id=1234567890123, legal_country_iso="GB", site_order=17)` — PK and sort are `[merchant_id, legal_country_iso, site_order]`. 

**S7 row (illustrative; exact columns owned by S7 anchor)**

```
merchant_id=1234567890123
legal_country_iso="GB"
site_order=17
tile_id=240104
lon_deg=-0.21337895
lat_deg=51.50522945
```

(Shape: `schemas.1B.yaml#/plan/s7_site_synthesis`, with PK/partitions/sort and `columns_strict: true`.) 

**S8 mapping → egress shape**
Egress uses `#/egress/site_locations` with PK `[merchant_id, legal_country_iso, site_order]`, partitions `[seed, manifest_fingerprint]`, **order-free**. From the S7 row above, S8 emits: 

```
merchant_id=1234567890123
legal_country_iso="GB"
site_order=17
lon_deg=-0.21337895
lat_deg=51.50522945
```

**Egress path (writer-sort respected):**
`data/layer1/1B/site_locations/seed=4242424242/manifest_fingerprint=deadbeef…/part-0000.snappy.parquet`
(Path family and partition law per Dictionary; writer sort `[merchant_id, legal_country_iso, site_order]`.) 

---

## B.3 Partition shift (what changes from S7 → S8)

* **Input S7:** `[seed, manifest_fingerprint, parameter_hash]` (parameter-scoped). 
* **Output S8:** `[seed, manifest_fingerprint]` (drop `parameter_hash`; fingerprint subsumes parameters). 

---

## B.4 Egress validator perspective (S8 §9 mapping)

* **A801 Row parity S7↔S8:** `|site_locations| == |s7_site_synthesis|` for the shared keyset `[merchant_id, legal_country_iso, site_order]`. With one input row, egress has one output row. 
* **A802 Schema conformance:** the egress row validates `#/egress/site_locations` (columns_strict). 
* **A803 Partition & identity law:** output lives at `…/seed=4242424242/manifest_fingerprint=deadbeef…/` with `[seed, manifest_fingerprint]`; any embedded `manifest_fingerprint` (if present) equals the `manifest_fingerprint` path token. 
* **A804 Writer sort:** rows are in non-decreasing `[merchant_id, legal_country_iso, site_order]`. 
* **A805 Order-authority pledge:** no inter-country order is encoded; egress is **order-free** per Dictionary/Registry.
* **A807 Partition shift law:** `{seed,fingerprint}` match between the consumed S7 partition and the produced S8 partition; **no** `parameter_hash` directory under egress. 

---

## B.5 Run-summary snippet (what S8 exposes)

Matches §11’s binding keys (non-identity-bearing summary):

```json
{
  "identity": {
    "seed": 4242424242,
    "manifest_fingerprint": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    "parameter_hash_consumed": "c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00c0ffee00"
  },
  "sizes": { "rows_s7": 1, "rows_s8": 1, "parity_ok": true },
  "validation_counters": {
    "schema_fail_count": 0,
    "path_embed_mismatches": 0,
    "writer_sort_violations": 0,
    "order_leak_indicators": 0
  },
  "by_country": { "GB": { "rows_s7": 1, "rows_s8": 1, "parity_ok": true } }
}
```

(S7 source under `[seed, manifest_fingerprint, parameter_hash]`; egress under `[seed, manifest_fingerprint]`; writer sorts per Dictionary/Schema.)

---

## B.6 Notes

* **Final in layer:** `site_locations` is terminal for 1B (Dictionary `final_in_layer: true`). 
* **Operational posture:** write-once; atomic move; file order non-authoritative (Registry). 

This example shows the S7→S8 pass-through into the egress shape and identity, with the partition shift and order-free law enforced by the Dictionary and Schema.

---
