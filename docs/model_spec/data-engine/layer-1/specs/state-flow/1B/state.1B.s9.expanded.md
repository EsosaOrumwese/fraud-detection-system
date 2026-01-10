#  State-9 — Validation bundle & PASS gate

# 1) Document metadata & status **(Binding)**

**State ID (canonical):** `layer1.1B.S9` — *Validation bundle & PASS gate (fingerprint-scoped).*
**Document type:** Contractual specification (behavioural + data contracts; no code/pseudocode). **Shapes** are owned by JSON-Schema; **IDs→paths/partitions/writer policy** resolve via the Dataset Dictionary; provenance/operational posture lives in the Artefact Registry. Implementations **MUST NOT** hard-code paths. 

## 1.1 Status & governance

**Status:** planning → alpha → beta → **stable** (governance-controlled).
**Precedence (tie-break):** **Schema** ≻ **Dictionary** ≻ **Registry** ≻ **this state spec**. If Dictionary prose and Schema ever disagree on **shape**, **Schema wins**; Dictionary governs **paths/partitions/writer policy**. 

## 1.2 Normative language (RFC 2119/8174)

Key words **MUST, MUST NOT, SHALL, SHALL NOT, SHOULD, SHOULD NOT, MAY** are normative. Unless explicitly labelled *Informative*, all clauses are **Binding**. 

## 1.3 Compatibility window (baselines assumed by S9)

S9 v1.* assumes the following frozen surfaces:

* **S7 prep dataset:** `s7_site_synthesis` — Schema anchor, partitions **`[seed, fingerprint, parameter_hash]`**, writer sort `[merchant_id, legal_country_iso, site_order]` (Dictionary bound). 
* **S8 egress dataset:** `site_locations` — Schema anchor, partitions **`[seed, fingerprint]`**, writer sort `[merchant_id, legal_country_iso, site_order]`, **final_in_layer: true** (order-free egress).
* **Layer RNG surfaces:** event streams and core logs under **`[seed, parameter_hash, run_id]`** with the common envelope (`draws` dec-u128, `blocks` u64, 128-bit counters); specifically **`rng_event_site_tile_assign`**, **`rng_event_in_cell_jitter`**, **`rng_audit_log`**, **`rng_trace_log`** (Dictionary/Registry).
* **Hashing/flag law (reference):** 1A validation bundle is **fingerprint-scoped** and its `_passed.flag` equals **SHA-256 over the raw bytes of files listed in `index.json` (ASCII-lex by `path`, flag excluded)**; S9 reuses this law for 1B. 

A **MAJOR** in any baseline that changes these bound interfaces requires S9 re-ratification.

## 1.4 Identity & lineage posture (state-wide)

* **Bundle identity:** S9 publishes a fingerprint-scoped bundle under `…/validation/fingerprint={manifest_fingerprint}/`; whenever lineage appears in bundle files, embedded `manifest_fingerprint` **MUST** equal the `fingerprint=` path token (**path↔embed equality**). This mirrors the fingerprint posture used for gates and validation surfaces.
* **Inputs identity (read-side):** S7 under **`[seed, fingerprint, parameter_hash]`** and S8 under **`[seed, fingerprint]`**; RNG logs/layer1/1B/core logs under **`[seed, parameter_hash, run_id]`**.
* **Publish posture:** write-once; stage → fsync → **single atomic move**; **file order non-authoritative**. 

## 1.5 Audience & scope notes

**Audience:** implementation agents, validators, and reviewers. This document binds **S9 behaviour** for validating S0–S8 outputs and packaging the 1B **validation bundle** with a fingerprint-scoped **PASS flag**; **Schema** remains the sole shape authority for datasets/logs; **Dictionary/Registry** bind paths/partitions/writer policy and operational posture.

---

### Contract Card (S9) - inputs/outputs/authorities

**Inputs (authoritative; see Section 3.2-3.3 for full list):**
* `s7_site_synthesis` - scope: SEED+FINGERPRINT+PARAMETER; source: 1B.S7
* `site_locations` - scope: EGRESS_SCOPED; source: 1B.S8
* `rng_event_site_tile_assign` - scope: LOG_SCOPED; source: 1B.S5
* `rng_event_in_cell_jitter` - scope: LOG_SCOPED; source: 1B.S6
* `rng_audit_log` - scope: LOG_SCOPED; source: layer1 RNG core
* `rng_trace_log` - scope: LOG_SCOPED; source: layer1 RNG core

**Authority / ordering:**
* Validation bundle index + hash gate is the sole consumer gate for 1B.

**Outputs:**
* `validation_bundle_1B` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `validation_bundle_index_1B` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `validation_passed_flag_1B` - scope: FINGERPRINT_SCOPED; gate emitted: final consumer gate

**Sealing / identity:**
* External inputs (ingress/reference/1A egress) MUST appear in `sealed_inputs_1B` for the target `manifest_fingerprint`.

**Failure posture:**
* Any validation failure -> do not publish `_passed.flag`; bundle records failure evidence.


# 2) Purpose & scope **(Binding)**

**Mission.** S9 **validates S0–S8 outputs** and **publishes the 1B validation bundle** for a given fingerprint. It computes egress checksums, reconciles RNG budgets/coverage, and writes a fingerprint-scoped bundle with a **PASS flag** that downstream consumers **MUST** verify before reading 1B egress (**“No PASS → no read”**). The bundle uses the **same hashing/index law** as 1A’s validation bundle.

## 2.1 In-scope (what S9 SHALL do)

* **Row & key parity:** Prove `|S8.site_locations| == |S7.s7_site_synthesis|` and identical keyset on `[merchant_id, legal_country_iso, site_order]`.
* **Egress checksums:** Compute stable per-file and composite SHA-256 for **`site_locations`** under `[seed, fingerprint]` (order-free, writer-sort bound) and persist in the bundle. 
* **RNG accounting (coverage + budgets + trace):**
  – **S5** `site_tile_assign`: **exactly one** event per assigned site. 
  – **S6** `in_cell_jitter`: **≥1 event per site (per attempt)** with **per-event budget** `blocks=1`, `draws="2"`. Reconcile event totals with **`rng_trace_log`** and enforce the envelope counter delta law.
* **Bundle publish (fingerprint-scoped):** Write `MANIFEST.json`, `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`, `rng_accounting.json`, `s9_summary.json`, `egress_checksums.json`, `index.json`, then `_passed.flag`. The flag equals **`sha256_hex` over the raw bytes of all files listed in `index.json` in ASCII-lex order of `path` (flag excluded)**.
* **Gate rule for consumers:** Require downstream readers of `site_locations` to verify the flag for the same fingerprint (**No PASS → no read**). 

## 2.2 Out of scope (what S9 SHALL NOT do)

* **No RNG** and **no data mutation**: S9 does not resample, alter S7/S8 rows, or touch 1A egress; it validates and packages only. 
* **No order encoding:** S9 must not introduce any inter-country order (egress remains order-free; order comes from 1A S3). 
* **No extra surfaces:** S9 MUST NOT depend on priors/policies or new geometry beyond what’s implied by S7/S8 and RNG logs/layer1/1B/core logs. (Events/trace identity and partitions are already governed.) 

**Outcome.** On success, S9 publishes a **fingerprint-scoped** bundle and `_passed.flag`; on failure, it publishes the bundle **without** the flag. Downstream consumers enforce the gate before reading 1B egress. 

---

# 3) Preconditions & sealed inputs **(Binding)**

## 3.1 Run identity is sealed before S9

S9 executes under a fixed lineage tuple **`{seed, manifest_fingerprint, parameter_hash, run_id}`** for the run. Where lineage appears both in **paths** and **embedded fields** (e.g., `manifest_fingerprint`), values **MUST** byte-equal (**path↔embed equality**). Egress `site_locations` is partitioned by **`[seed, fingerprint]`**; S7 is partitioned by **`[seed, fingerprint, parameter_hash]`**.

## 3.2 Required upstream datasets (this identity)

S9 **SHALL** read only the following sealed surfaces for **this** identity:

* **S7 — `s7_site_synthesis`** (deterministic per-site absolutes; RNG-free)
  **Path family:** `data/layer1/1B/s7_site_synthesis/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/` · **Partitions:** `[seed, fingerprint, parameter_hash]` · **Writer sort:** `[merchant_id, legal_country_iso, site_order]` · **Schema:** `schemas.1B.yaml#/plan/s7_site_synthesis`. 

* **S8 — `site_locations`** (egress; order-free; final in layer)
  **Path family:** `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` · **Partitions:** `[seed, fingerprint]` · **Writer sort:** `[merchant_id, legal_country_iso, site_order]` · **Schema:** `schemas.1B.yaml#/egress/site_locations`. 

## 3.3 Required RNG evidence surfaces (this run)

S9 **SHALL** read the 1B RNG evidence (event streams and core logs) for the same `{seed, parameter_hash, run_id}`:

* **Event — `rng_event_site_tile_assign`** (S5; **one event per site**)
  `logs/layer1/1B/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` · **Partitions:** `[seed, parameter_hash, run_id]` · **Schema:** `schemas.layer1.yaml#/rng/events/site_tile_assign`. 

* **Event — `rng_event_in_cell_jitter`** (S6; **≥1 event per site (per attempt)**; **per-event budget** `blocks=1`, `draws="2"`)
  `logs/layer1/1B/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` · **Partitions:** `[seed, parameter_hash, run_id]` · **Schema:** `schemas.layer1.yaml#/rng/events/in_cell_jitter`.

* **Core — `rng_audit_log`** (one row at run start) and **`rng_trace_log`** (append-only cumulative counters) under `[seed, parameter_hash, run_id]` per the layer RNG core schemas and envelope invariants (`u128(after)−u128(before)=blocks`; `draws` dec-u128). 

## 3.4 Egress finality & order posture (read-side facts)

Before packaging, S9 **assumes** `site_locations` is present under `[seed, fingerprint]`, **final_in_layer: true**, and order-free (writer sort bound; file order non-authoritative). 

## 3.5 Resolution rule (no literal paths)

Implementations **SHALL** resolve dataset/log **IDs → path families, partitions, writer policy** **exclusively** via the **Dataset Dictionary**; Schema remains the sole shape authority; Registry binds the write-once/atomic-move posture. 

## 3.6 Fail-closed access

S9 **SHALL** read **only** the inputs enumerated in **§3.2–§3.3**. Reading any unlisted priors, policies, or alternative spatial/time surfaces is **non-conformant** for this state. 

*(Subsequent sections bind the bundle content, hashing/flag law, and validators that reconcile S7/S8 parity and RNG accounting.)*

---

# 4) Inputs & authority boundaries **(Binding)**

## 4.1 Authority stack (precedence)

* **Shape authority:** JSON-Schema anchors for datasets/logs.
* **IDs → paths/partitions/writer policy:** **Dataset Dictionary** (no literal paths).
* **Operational posture:** **Artefact Registry** (write-once; atomic move; file order non-authoritative). 

## 4.2 Bound datasets (sealed for this identity)

S9 SHALL read **only** the following dataset surfaces for the run’s fixed identity:

* **S7 — `s7_site_synthesis`** (deterministic per-site absolutes; RNG-free)
  **Schema:** `schemas.1B.yaml#/plan/s7_site_synthesis` · **Path family:**
  `data/layer1/1B/s7_site_synthesis/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/` · **Partitions:** `[seed, fingerprint, parameter_hash]` · **Writer sort:** `[merchant_id, legal_country_iso, site_order]`. 

* **S8 — `site_locations`** (egress; order-free; final in layer)
  **Schema:** `schemas.1B.yaml#/egress/site_locations` · **Path family:**
  `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` · **Partitions:** `[seed, fingerprint]` · **Writer sort:** `[merchant_id, legal_country_iso, site_order]`. 

## 4.3 Bound RNG evidence (same run)

S9 SHALL reconcile RNG **events** and **core logs** for the same `{seed, parameter_hash, run_id}`:

* **Event stream — `rng_event_site_tile_assign` (S5):** **one event per site**.
  **Schema:** `schemas.layer1.yaml#/rng/events/site_tile_assign` · **Path family:**
  `logs/layer1/1B/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`. 

* **Event stream — `rng_event_in_cell_jitter` (S6):** **≥1 event per site (one per attempt)**; **per-event** budget **`blocks=1`**, **`draws="2"`**.
  **Schema:** `schemas.layer1.yaml#/rng/events/in_cell_jitter` · **Path family:**
  `logs/layer1/1B/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.

* **Core logs — `rng_audit_log`, `rng_trace_log`:** partitioned by `[seed, parameter_hash, run_id]`; counter law **u128(after) − u128(before) = blocks**; `draws` is decimal-encoded u128. *(Layer RNG core posture referenced by S6/S7 docs.)* 

## 4.4 Egress order authority (read-side fact)

`site_locations` is **order-free**; any inter-country order remains outside 1B egress and is obtained downstream by joining **1A S3 `candidate_rank`**. S9 MUST NOT introduce or rely on any other ordering semantics. 

## 4.5 Resolution rule (no literal paths)

Implementations SHALL resolve all dataset/log **IDs → path families / partitions / writer policy** **exclusively** via the **Dataset Dictionary**; Schema remains the sole shape authority; Registry binds write-once/atomic-move/file-order-non-authoritative posture.

## 4.6 Prohibited surfaces (fail-closed)

S9 SHALL read **only** the inputs enumerated in **§4.2–§4.3**. Reading priors, policies, alternative geometries, or any unlisted surfaces is **non-conformant** for this state. 

---

# 5) Outputs (bundle) & identity **(Binding)**

## 5.1 Bundle root & partition law

* **Root path (fingerprint-scoped):**
  `data/layer1/1B/validation/manifest_fingerprint={manifest_fingerprint}/`
  **Partition:** `[fingerprint]` (path token **MUST** byte-equal any embedded `manifest_fingerprint` fields in bundle files → **path↔embed equality**). 

* **Publish posture:** write-once; stage → fsync → **single atomic move** into the fingerprint folder; **file order non-authoritative**. 

## 5.2 Required contents (minimum set)

S9 **SHALL** produce at least the files below under the bundle root:

1. `MANIFEST.json` — run identity and pointers (informative).
2. `parameter_hash_resolved.json` — the parameter set used during S7/S8 validation.
3. `manifest_fingerprint_resolved.json` — the fingerprint being certified.
4. `rng_accounting.json` — per-family coverage/budget/trace reconciliation (S5 & S6). 
5. `s9_summary.json` — acceptance verdicts and counters (parity, writer-sort, path↔embed, etc.).
6. `egress_checksums.json` — stable per-file SHA-256 (and optional composite) for **`site_locations`** under `[seed, fingerprint]`.
7. `index.json` — **bundle index** (each non-flag file listed exactly once; relative, ASCII-sortable paths). **Shape reuses the 1A bundle index schema.** 
8. `_passed.flag` — see §5.3.

*(Dictionary/Registry may further document the folder; this spec binds the partition and file set.)* 

## 5.3 PASS flag — hashing/index law (binding)

* **Content:** single line
  `sha256_hex = <hex64>`

* **Computation:** SHA-256 over the **raw bytes** of all files **listed in `index.json`**, concatenated in **ASCII-lexicographic order of the `path`**, **excluding** `_passed.flag` itself. 

* **Validity rule:** Consumers MUST recompute this digest from the listed files and require equality before reading 1B egress (**“No PASS → no read”**). 

## 5.4 Identity & lineage equality (binding)

* Any embedded `manifest_fingerprint` within bundle files MUST byte-equal the `fingerprint=` path token of the bundle root (**path↔embed equality**). 

## 5.5 Egress reference (readers’ gate target)

* The bundle certifies the **S8 egress**:
  `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`
  (partitions `[seed, fingerprint]`; writer sort `[merchant_id, legal_country_iso, site_order]`; **order-free**). 

## 5.6 Index constraints (binding)

* Every non-flag file in §5.2 MUST appear **exactly once** in `index.json` with a **relative** `path` that is **ASCII-sortable**.
* The **order used for hashing** is the ASCII-lex ordering of these `path` values (example shown in prior state text). 

## 5.7 On ABORT

* If any acceptance check fails, S9 MAY write all non-flag files (including `index.json`) but SHALL **NOT** write `_passed.flag` under the fingerprint. Downstream readers MUST treat the egress as **unauthorised** until a valid flag is present. 

*(This binds the fingerprint-scoped bundle location, required files, hashing law, equality rules, and publish posture consistent with the 1A bundle/index contract and the 1B S0/S8/S9 flow.)*

---

# 6) Dataset shapes & schema anchors **(Binding)**

**JSON-Schema is the sole shape authority.** Implementations **MUST** validate against the anchors below and **MUST NOT** restate columns outside Schema. IDs→paths/partitions/writer policy resolve **exclusively** via the **Dataset Dictionary**.

## 6.1 Datasets S9 reads (shape authority)

* **S7 (prep):** `s7_site_synthesis` → `schemas.1B.yaml#/plan/s7_site_synthesis`
  **PK** `[merchant_id, legal_country_iso, site_order]` · **partitions** `[seed, fingerprint, parameter_hash]` · **writer sort** `[merchant_id, legal_country_iso, site_order]` · `columns_strict: true`. 
* **S8 (egress):** `site_locations` → `schemas.1B.yaml#/egress/site_locations`
  **PK** `[merchant_id, legal_country_iso, site_order]` · **partitions** `[seed, fingerprint]` · **writer sort** `[merchant_id, legal_country_iso, site_order]` · `columns_strict: true` · **order-free**. 

## 6.2 RNG event families S9 reads (shape authority)

* **S5 event stream:** `rng_event_site_tile_assign` → `schemas.layer1.yaml#/rng/events/site_tile_assign`
  **Partitions** `[seed, parameter_hash, run_id]` · inherits the **layer RNG envelope** (open-interval U(0,1), `draws` = dec-u128 string, `blocks` = u64, 128-bit counters). 
* **S6 event stream:** `rng_event_in_cell_jitter` → `schemas.layer1.yaml#/rng/events/in_cell_jitter`
  **Partitions** `[seed, parameter_hash, run_id]` · **per-event budget pinned by the anchor** (two-uniform family; `blocks=1`, `draws="2"`), plus the common envelope invariants. 

## 6.3 RNG core logs S9 reads (shape authority)

* **`rng_audit_log`**, **`rng_trace_log`** → layer core schemas under **`[seed, parameter_hash, run_id]`**; envelope law **MUST** hold (`u128(after) − u128(before) = blocks`; `draws` dec-u128). 

## 6.4 Bundle index S9 writes (shape authority)

* **`index.json`** **MUST** validate the **1A bundle-index schema** (reused here): every non-flag file listed **exactly once** with a **relative**, ASCII-sortable `path`. Hashing order (for `_passed.flag`) is the ASCII-lex order of these `path` values. 

## 6.5 Resolution & path law **(Binding)**

All dataset/log **IDs → path families / partitions / writer policy** resolve **only** via the **Dataset Dictionary**; Schema owns shapes; Registry binds **write-once; atomic move; file-order non-authoritative** posture.

## 6.6 Scope of this section

This section **binds shapes** for the inputs S9 validates and for the **bundle index** it writes. JSON files like `s9_summary.json` and `rng_accounting.json` are **non-identity** artefacts whose contents are specified behaviorally in this state; they are not dataset entries and **need no Dictionary path/partition**. The accept/reject logic for them is enforced in §9. 

---

# 7) Deterministic algorithm (RNG-free) **(Binding)**

## 7.1 Assemble sealed inputs (fixed identity)

For the run’s sealed identity **`{seed, manifest_fingerprint, parameter_hash, run_id}`**, open:

* **S7** `s7_site_synthesis` under `…/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/` (partitions `[seed, fingerprint, parameter_hash]`, writer sort `[merchant_id, legal_country_iso, site_order]`). 
* **S8** `site_locations` under `…/seed={seed}/fingerprint={manifest_fingerprint}/` (partitions `[seed, fingerprint]`, writer sort `[merchant_id, legal_country_iso, site_order]`, order-free, final-in-layer). 
* **RNG evidence (same run)** under `[seed, parameter_hash, run_id]`:
  – `rng_event_site_tile_assign` (S5; **one event per site**),
  – `rng_event_in_cell_jitter` (S6; **≥1 event per site (per attempt)**; **per-event** budget `blocks=1`, `draws="2"`),
  – `rng_audit_log` & `rng_trace_log` (core).

## 7.2 Parity & identity checks (dataset-level)

1. **Key parity:** derive `K7 = {(merchant_id, legal_country_iso, site_order)}` from **S7** and `K8` from **S8**; require `K7 == K8`. Enforce PK uniqueness per partition.
2. **Egress identity law:** confirm **S8** lives under `[seed, fingerprint]` and any embedded lineage (if present) **byte-equals** path tokens (**path↔embed equality**). 
3. **Writer discipline:** verify **non-decreasing** `[merchant_id, legal_country_iso, site_order]` within each **S8** partition; file order is non-authoritative. 

## 7.3 RNG coverage & envelope reconciliation

Using **S7** as the authoritative site keyset:

**S5 — `site_tile_assign` (events per site):**

* Join events to `K7`; require **exactly one** event per site.
* Envelope law: for every event, parse `u128(after) − u128(before) == blocks`. Summed **event** blocks/draws equal **trace** totals for `(module="1B.S5.assign", substream_label=…)` at run end. 

**S6 — `in_cell_jitter` (events per attempt):**

* Join events to `K7`; require **event_count(site) ≥ 1**.
* **Per-event budget** (from schema): **`blocks = 1`, `draws = "2"`**; enforce envelope law per event and reconcile summed event blocks/draws with the final **`rng_trace_log`** row for `(module="1B.S6.jitter", substream_label="in_cell_jitter")`. 

**Core logs (run-scoped):**

* Confirm one `rng_audit_log` row for `{seed, parameter_hash, run_id}`;
* From `rng_trace_log`, read final cumulative `{events_total, draws_total, blocks_total}` per `(module, substream_label)` and require equality with sums from the **event** files above; enforce **`u128(after) − u128(before) = blocks`** on every row. 

## 7.4 Egress checksums (deterministic)

Enumerate all **S8** files under `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`. For each file, compute **SHA-256 over raw bytes** and write `egress_checksums.json` (path → hex). Paths recorded **relative to the bundle root** (see §7.6) to make them ASCII-sortable. 

## 7.5 S9 summary & RNG accounting artefacts

Produce two JSON artefacts (non-identity, packaged in the bundle):

* **`s9_summary.json`** — identity, `|S7|`, `|S8|`, parity verdicts, egress writer-sort/path↔embed checks, and RNG reconciliation verdicts.
* **`rng_accounting.json`** — per-family tables: coverage (per-site counts), totals (events/blocks/draws), and trace alignment for S5/S6.

## 7.6 Build bundle, index, and PASS flag

1. **Stage** files in a temp dir, e.g., `…/validation/_tmp.{uuid}/`.
2. **Write** (at minimum): `MANIFEST.json`, `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`, `egress_checksums.json`, `rng_accounting.json`, `s9_summary.json`. 
3. **`index.json` (binding):** list **every non-flag file exactly once** with a **relative** `path`. The **hashing order** is ASCII-lex by `path`. Validate `index.json` against the **1A bundle-index schema**. 
4. **`_passed.flag`:** compute `sha256_hex` = SHA-256 over the **raw bytes of files listed in `index.json`**, concatenated in **ASCII-lex order**, **excluding** the flag; write single-line `sha256_hex = <hex64>`. 
5. **Atomic publish:** move the staged dir to
   `data/layer1/1B/validation/manifest_fingerprint={manifest_fingerprint}/` (write-once; atomic move; file order non-authoritative).

## 7.7 ABORT semantics (fail-closed)

If any check in §7.2–§7.3 fails, **do not** write `_passed.flag`. You MAY publish the bundle **without** the flag (for diagnostics), but downstream consumers MUST enforce **“No PASS → no read”** for `site_locations` until a valid flag appears. 

*(This algorithm binds the exact inputs, parity/identity/writer-sort checks, RNG coverage & envelope reconciliation, deterministic egress hashing, and the fingerprint-scoped bundle/flag publish — all reusing the 1A bundle index/flag law.)*

---

# 8) Identity, partitions, ordering & merge discipline **(Binding)**

## 8.1 Bundle identity (fingerprint-scoped)

* **Partition:** the validation bundle **MUST** publish under
  `data/layer1/1B/validation/manifest_fingerprint={manifest_fingerprint}/` (**partition** `[fingerprint]`).
  Fingerprint scoping and naming align with existing 1B validation artefacts (e.g., S0 gate receipt) and the 1A bundle pattern. **Path↔embed equality** applies wherever `manifest_fingerprint` appears.

## 8.2 Input/output identities used by S9 (read-side facts)

* **S7** `s7_site_synthesis`: partitions **`[seed, fingerprint, parameter_hash]`**; writer sort `[merchant_id, legal_country_iso, site_order]`. 
* **S8** `site_locations` (egress): partitions **`[seed, fingerprint]`**; writer sort `[merchant_id, legal_country_iso, site_order]`; **order-free; final_in_layer: true**.
* **RNG logs/layer1/1B/core** for this run: partitions **`[seed, parameter_hash, run_id]`** (events & core); **file order non-authoritative**.

## 8.3 Ordering posture

* **Datasets:** Where S9 verifies rows (S7/S8), semantics are governed by the **writer sort** `[merchant_id, legal_country_iso, site_order]`; **file order is non-authoritative**. 
* **Egress order-free law:** S8 encodes **no inter-country order**; downstreams join 1A S3 for any order. S9 MUST NOT introduce or rely on any alternative ordering semantics. 

## 8.4 Stable merge & parallelism

* Implementations **MAY** shard (e.g., by country/merchant) provided the final S8/S7 views used by S9 are the result of a **stable merge** in the binding writer sort and are **byte-stable** irrespective of worker count/scheduling. 

## 8.5 Atomic publish & idempotence (bundle)

* Publish the bundle via **stage → fsync → single atomic move** into `…/validation/fingerprint={manifest_fingerprint}/`.
* **Write-once:** re-publishing the same fingerprint **MUST** be byte-identical; **file order non-authoritative**. 

## 8.6 Identity-coherence checks (must hold before publish)

* **S7↔S8 parity identity:** `{seed,fingerprint}` in S8 **MUST** equal `{seed,fingerprint}` in the consumed S7 partition (parameter-scoped at S7; dropped at S8). 
* **RNG‐run identity:** all RNG evidence reconciled by S9 **MUST** come from the same `{seed, parameter_hash, run_id}` set; logs carry **no** fingerprint partition. 
* **Path↔embed equality:** wherever lineage appears in bundle files (e.g., `manifest_fingerprint` fields), values **MUST** byte-equal the `fingerprint` path token. 

## 8.7 Prohibitions (fail-closed)

* **MUST NOT** mix identities within the bundle publish (no cross-fingerprint contamination). 
* **MUST NOT** rely on file order for semantics (datasets or logs). 
* **MUST NOT** encode or infer inter-country order (egress remains order-free). 

*(This section binds the fingerprint-scoped bundle identity, the dataset/log identities S9 reads, order discipline, atomic publish posture, and coherent identity checks consistent with S7/S8 and the layer RNG contracts.)*

---

# 9) Acceptance criteria (validators) **(Binding)**

A run **PASSES** S9 only if **all** checks below succeed.

## A901 — Row parity S7 ↔ S8

**Rule.** `|S8.site_locations| = |S7.s7_site_synthesis|` and the keyset `[merchant_id, legal_country_iso, site_order]` matches exactly; no extras/dups.
**Detection.** Two-way anti-join on the PK; enforce PK uniqueness in both views.

## A902 — Egress schema conformance

**Rule.** Every S8 row validates `schemas.1B.yaml#/egress/site_locations` (**columns_strict=true**).
**Detection.** JSON-Schema validate all S8 files. 

## A903 — Egress partition & path↔embed equality

**Rule.** S8 is written at `…/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/` with partitions `[seed, fingerprint]`; where `manifest_fingerprint` appears in rows it **byte-equals** the `fingerprint` path token.
**Detection.** Compare path-derived identity to embedded fields.

## A904 — Writer sort

**Rule.** S8 rows are a **stable merge** in `[merchant_id, legal_country_iso, site_order]`. File order is **non-authoritative**.
**Detection.** Check within-file and merged partition order. 

## A905 — RNG accounting (coverage, budgets, trace reconciliation)

**Rule.**

* **S5 events (`site_tile_assign`)**: **exactly one** event **per site**.
* **S6 events (`in_cell_jitter`)**: **≥1 event per site (one per attempt)**; **per-event budget** `blocks=1`, `draws="2"`.
* **Envelope law** holds for **every** event: `u128(after) − u128(before) = blocks`.
* **Trace reconciliation**: for each family, Σ(events.blocks/draws) == final `rng_trace_log.{blocks_total,draws_total}` for its `(module, substream_label, run_id)`; one cumulative **trace** row appended after each event append.
  **Detection.** Join events to the S7 keyset; count coverage; validate per-event envelope; aggregate and match to the final trace rows.

## A906 — Bundle contents present (minimum set)

**Rule.** Under `validation/fingerprint={manifest_fingerprint}/` the files exist:
`MANIFEST.json`, `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`, `rng_accounting.json`, `s9_summary.json`, `egress_checksums.json`, `index.json`.
**Detection.** Presence check before flag verification. 

## A907 — Index validity (binding)

**Rule.** `index.json` **lists every non-flag file exactly once**; `path` values are **relative** and **ASCII-sortable**; `artifact_id` values are **unique**.
**Detection.** Validate shape against the 1A bundle-index schema; enforce uniqueness/relativity/sortability.

## A908 — PASS flag hashing rule

**Rule.** `_passed.flag` contains exactly `sha256_hex = <hex64>` where `<hex64>` equals **SHA-256 over the raw bytes of all files listed in `index.json` (excluding `_passed.flag`)** concatenated in **ASCII-lex order of the `path` entries**.
**Detection.** Recompute digest from `index.json` and compare; mismatch ⇒ **FAIL**.

## A909 — Bundle identity & publish posture

**Rule.** Bundle folder is **fingerprint-scoped** (`…/validation/fingerprint={manifest_fingerprint}/`); any embedded `manifest_fingerprint` **byte-equals** the folder token; publish is **write-once** via **atomic move** (no partials visible).
**Detection.** Check folder partition, embedded lineage, and publish logs.

## A910 — Dictionary/Schema coherence

**Rule.** All IDs resolve via the **Dataset Dictionary** and match their Schema anchors (paths/partitions/writer policy), including S7 and S8. No literal paths.
**Detection.** Cross-check `schema_ref` ↔ Dictionary entries used.

## A911 — Egress finality and order-free law

**Rule.** Dictionary marks `site_locations` as **final_in_layer: true** and **order-free**; S9 observes this (no alternative order semantics introduced).
**Detection.** Verify Dictionary entry and absence of order encoding beyond writer sort. 

## A912 — Identity coherence across inputs

**Rule.** The `{seed,fingerprint}` used for S8 equals the `{seed,fingerprint}` of the consumed S7 partition (S7 also carries `parameter_hash` which is dropped at egress).
**Detection.** Compare identities taken from S7/S8 paths.

---

**PASS** requires A901–A912 all true; any violation yields **FAIL** and the bundle **MUST NOT** include `_passed.flag` (consumers enforce **“No PASS → no read”**). 

---

# 10) Failure modes & canonical error codes **(Binding)**

### E901_ROW_MISSING — Missing S8 row for an S7 key *(ABORT)*

**Trigger:** A `(merchant_id, legal_country_iso, site_order)` present in **S7** is absent in **S8**.
**Detection:** Anti-join `S7 \ S8` on the PK is empty. 

### E902_ROW_EXTRA — Extra S8 row *(ABORT)*

**Trigger:** A site key appears in **S8** but not in **S7**.
**Detection:** Anti-join `S8 \ S7` on the PK is empty. 

### E903_DUP_KEY — Duplicate primary key in S8 *(ABORT)*

**Trigger:** Duplicate `(merchant_id, legal_country_iso, site_order)` within an S8 identity partition.
**Detection:** Enforce PK uniqueness per `#/egress/site_locations` (columns_strict). 

### E904_EGRESS_SCHEMA_VIOLATION — Egress row fails schema *(ABORT)*

**Trigger:** Any S8 row fails `schemas.1B.yaml#/egress/site_locations`.
**Detection:** JSON-Schema validation failure (unknown/missing columns, bad types/constraints). 

### E905_PARTITION_OR_IDENTITY — Egress partition/path↔embed mismatch *(ABORT)*

**Trigger:** Any of:

* Egress not under `…/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/` (partitions must be `[seed,fingerprint]`), or
* Embedded `manifest_fingerprint` (if present) ≠ `fingerprint` path token.
  **Detection:** Compare path-derived `{seed,fingerprint}` to embedded lineage. 

### E906_WRITER_SORT_VIOLATION — Writer sort not respected *(ABORT)*

**Trigger:** S8 rows not in non-decreasing `[merchant_id, legal_country_iso, site_order]`.
**Detection:** Verify stable-merge order; file order is non-authoritative. 

### E907_RNG_BUDGET_OR_COUNTERS — Coverage/budget/trace mismatch *(ABORT)*

**Trigger:** Any of:

* **S5** `site_tile_assign` not **exactly one** event per site;
* **S6** `in_cell_jitter` not **≥1 event per site**; or any event violates **per-event budget** `blocks=1`, `draws="2"`;
* Envelope law broken: `u128(after) − u128(before) ≠ blocks`;
* **Trace** totals don’t equal the sum over events for each `(module, substream_label, run_id)`.
  **Detection:** Join events to the S7 keyset; count coverage; validate per-event envelope; aggregate and match to final `rng_trace_log` rows under `[seed,parameter_hash,run_id]`.

### E908_BUNDLE_CONTENTS_MISSING — Required files absent *(ABORT)*

**Trigger:** Any required file is missing: `MANIFEST.json`, `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`, `rng_accounting.json`, `s9_summary.json`, `egress_checksums.json`, `index.json`.
**Detection:** Presence check in `validation/fingerprint={manifest_fingerprint}/`. 

### E909_INDEX_INVALID — `index.json` invalid *(ABORT)*

**Trigger:** `index.json` does **not** list every non-flag file **exactly once**, or uses non-relative/non-ASCII-sortable paths, or violates the 1A bundle-index schema.
**Detection:** Validate shape and constraints against the 1A bundle-index schema. 

### E910_FLAG_BAD_OR_MISSING — `_passed.flag` absent or digest mismatch *(ABORT)*

**Trigger:** `_passed.flag` missing, or its `sha256_hex` ≠ SHA-256 over **raw bytes of files listed in `index.json`** concatenated in **ASCII-lex order of `path`** (flag excluded).
**Detection:** Recompute and compare; mismatch ⇒ FAIL. 

### E911_FINALITY_OR_ORDER_LEAK — Egress not final/order-free *(ABORT)*

**Trigger:** Dictionary doesn’t mark `site_locations` **final_in_layer: true**, or S8 encodes/implies inter-country order beyond writer sort (order must come from 1A S3).
**Detection:** Check Dictionary entry and audit for order fields/implications. 

### E912_IDENTITY_COHERENCE — S7↔S8 identity mismatch *(ABORT)*

**Trigger:** `{seed,fingerprint}` in S8 doesn’t equal `{seed,fingerprint}` of the consumed S7 partition (where S7 also has `parameter_hash`), or egress accidentally carries `parameter_hash` in its path.
**Detection:** Compare identities from S7/S8 paths; assert egress has **no** `parameter_hash` directory. 

### E913_ATOMIC_PUBLISH_VIOLATION — Non-atomic/duplicate publish *(ABORT)*

**Trigger:** Bundle not published via **stage → fsync → single atomic move**, or re-publishing the same fingerprint yields non-identical bytes.
**Detection:** Publish logs vs Registry posture (**write-once; atomic move; file order non-authoritative**). 

---

**Fail-closed rule:** On any error above, S9 **MUST NOT** write `_passed.flag` under `validation/fingerprint={manifest_fingerprint}/`. Downstream consumers enforce **“No PASS → no read”** on `site_locations`. 

---

# 11) Observability & run-report **(Binding)**

## 11.1 Required artefacts S9 SHALL write (packaged in the bundle)

* **`s9_summary.json`** — run-level verdicts and counters (binding keys in §11.2).
* **`rng_accounting.json`** — per-family RNG coverage/budget/trace reconciliation (binding keys in §11.3).
  Both files are **non-identity** artefacts and MUST be present under
  `data/layer1/1B/validation/manifest_fingerprint={manifest_fingerprint}/` (see §5 for bundle contents).

## 11.2 Binding keys in `s9_summary.json` (minimum set)

S9 SHALL emit a JSON object with at least the keys below; values MUST be computed from the sealed sources listed in §11.4.

```json
{
  "identity": {
    "seed": 0,
    "parameter_hash": "<hex64>",
    "manifest_fingerprint": "<hex64>",
    "run_id": "<hex32>"
  },
  "sizes": {
    "rows_s7": 0,
    "rows_s8": 0,
    "parity_ok": false
  },
  "egress": {
    "path": "data/layer1/1B/site_locations/seed=<seed>/fingerprint=<fingerprint>/",
    "writer_sort_violations": 0,
    "path_embed_mismatches": 0
  },
  "rng": {
    "families": {
      "site_tile_assign": {
        "coverage_ok": false,
        "events_total": 0, "blocks_total": 0, "draws_total": "0",
        "envelope_failures": 0, "trace_reconciled": false
      },
      "in_cell_jitter": {
        "coverage_ok": false,
        "events_total": 0, "blocks_total": 0, "draws_total": "0",
        "envelope_failures": 0, "trace_reconciled": false
      }
    }
  },
  "by_country": { "GB": { "rows_s7": 0, "rows_s8": 0, "parity_ok": true } }
}
```

**Binding expectations for the values**

* `rows_s7`/`rows_s8` are counts of **S7** `s7_site_synthesis` (partition `[seed,fingerprint,parameter_hash]`) and **S8** `site_locations` (partition `[seed,fingerprint]`), and `parity_ok` reflects **exact keyset equality** on `[merchant_id, legal_country_iso, site_order]`.
* `egress.writer_sort_violations` validates S8’s binding writer sort `[merchant_id, legal_country_iso, site_order]`; `egress.path_embed_mismatches` counts path↔embed lineage mismatches at egress. 
* RNG family expectations:
  – **`site_tile_assign` (S5)** — **exactly one** event per site; totals reconcile with **`rng_trace_log`**. 
  – **`in_cell_jitter` (S6)** — **≥1 event per site (one per attempt)**; **per-event budget pinned by schema**: `blocks=1`, `draws="2"`; totals reconcile with **`rng_trace_log`**; envelope law holds (`u128(after) − u128(before) = blocks`). 

## 11.3 Binding keys in `rng_accounting.json` (per-family tables)

S9 SHALL emit a per-family structure with at least:

```json
{
  "families": [
    {
      "id": "site_tile_assign",
      "module": "1B.S5.assign",
      "coverage": { "sites_total": 0, "events_missing": 0, "events_extra": 0 },
      "events_total": 0, "blocks_total": 0, "draws_total": "0",
      "trace_totals": { "events_total": 0, "blocks_total": 0, "draws_total": "0" },
      "trace_reconciled": false,
      "envelope_failures": 0
    },
    {
      "id": "in_cell_jitter",
      "module": "1B.S6.jitter",
      "coverage": { "sites_total": 0, "sites_with_≥1_event": 0, "sites_with_0_event": 0 },
      "events_total": 0, "blocks_total": 0, "draws_total": "0",
      "budget_per_event": { "blocks": 1, "draws": "2" },
      "trace_totals": { "events_total": 0, "blocks_total": 0, "draws_total": "0" },
      "trace_reconciled": false,
      "envelope_failures": 0
    }
  ]
}
```

**Binding expectations for the values**

* **Coverage** joins events to the **S7** keyset; S5 requires `events_missing=0` and `events_extra=0`; S6 requires `sites_with_0_event=0`.
* **Budget & envelope**: every **S6** event has `blocks=1`, `draws="2"`; **all** events satisfy `u128(after) − u128(before) = blocks`. 
* **Trace reconciliation**: Σ(events) `{events_total, blocks_total, draws_total}` **equals** the final **`rng_trace_log`** row for the same `(module, substream_label, run_id)`. 

## 11.4 Sources S9 MUST use for these artefacts

* **S7** `s7_site_synthesis` — `[seed,fingerprint,parameter_hash]`; writer sort `[merchant_id, legal_country_iso, site_order]`. 
* **S8** `site_locations` — `[seed,fingerprint]`; writer sort `[merchant_id, legal_country_iso, site_order]`; **final_in_layer: true**; **order-free**. 
* **RNG events** — `rng_event_site_tile_assign` (S5) and `rng_event_in_cell_jitter` (S6) under `[seed,parameter_hash,run_id]`.
* **RNG core logs** — `rng_audit_log`, `rng_trace_log` under `[seed,parameter_hash,run_id]`. 

## 11.5 Emission & bundling posture

* `s9_summary.json` and `rng_accounting.json` MUST be included in the bundle’s `index.json`; hashing for `_passed.flag` is computed over the **raw bytes** of all non-flag files listed there in **ASCII-lex** order of `path`. **No PASS → no read**.

---

This section binds exactly **what S9 must report**, **how those values are derived**, and **where they live** in the fingerprint-scoped bundle, consistent with the egress contracts and the layer RNG event/core schemas.

---

# 12) Performance & scalability *(Informative)*

**Goal:** validate S7/S8 and package the fingerprint-scoped bundle **quickly and deterministically**, while honoring the egress contracts (Schema shapes; Dictionary paths/partitions/writer-sort; Registry’s **write-once → atomic move** posture).

## 12.1 Streamed parity & identity checks

* **Merge-join in writer sort.** S7 and S8 share the writer sort `[merchant_id, legal_country_iso, site_order]`, so parity (`K7 == K8`) can be done as a **single pass merge-join** over their sorted streams—no global shuffle. Memory ~ O(mismatches). 
* **Partition-aware reads.** Open S7 under `[seed,fingerprint,parameter_hash]` and S8 under `[seed,fingerprint]`; derive `{seed,fingerprint}` once and carry it through the pipeline to enforce **path↔embed equality** without re-reading. 

## 12.2 RNG accounting fast-path

* **Use trace as a reducer.** For each event family, aggregate **events** (coverage & envelope checks) and reconcile against the **final `rng_trace_log` row** keyed by `(module, substream_label, run_id)` to avoid re-scanning earlier event files. 
* **Per-event validation in stream.** Validate `u128(after)−u128(before) = blocks` and the **per-event budget** (`blocks=1`, `draws="2"` for `in_cell_jitter`) as you read events; keep only running totals needed for trace reconciliation. 

## 12.3 Deterministic egress hashing

* **One pass per file.** Walk the S8 partition once; compute **per-file SHA-256 over raw bytes** and store `{relative_path → hex}`. Persist to `egress_checksums.json`. 
* **Index then flag.** Build `index.json` with **relative**, ASCII-sortable paths; compute `_passed.flag` as SHA-256 over the **concatenation of bytes** for files listed in `index.json`, in **ASCII-lex order**, excluding the flag. This mirrors the **1A bundle law**. 

## 12.4 Concurrency & staging

* **Shard safely.** It’s fine to shard parity/RNG checks by **country** or **merchant buckets** so long as the final verdicts are a **stable merge** of shard outputs; S7/S8 semantics are governed by writer sort, not file order. 
* **Atomic publish.** Write all bundle files to a temporary folder (e.g., `…/validation/_tmp.{uuid}`), fsync, then **single atomic move** to `validation/fingerprint={manifest_fingerprint}/`. Never expose partial bundles. 

## 12.5 I/O & memory discipline

* **Single-read discipline.** While scanning S7/S8 for parity, optionally emit **by-country counters** for `s9_summary.json` to avoid a second pass. 
* **Bounded memory joins.** Use streaming iterators over the sorted PK; for RNG coverage joins (events↔S7 keys), keep only the current window and per-site counters.

## 12.6 Determinism & serialization

* **Canonical JSON.** For JSON artefacts in the bundle, choose a stable key order and encoding; paths stored in `index.json` **must be relative** and ASCII-sortable to keep hashing deterministic. 
* **File-order neutrality.** Do not rely on physical file order anywhere—S7/S8 contracts mark **file order non-authoritative**; writer sort and bundle hashing rules define semantics. 

## 12.7 Gate posture in the flow

* **Fail-closed.** If any validator fails, publish the bundle **without** `_passed.flag`. Downstream consumers must enforce **“No PASS → no read.”** 

*(These practices keep S9 fast, byte-stable, and fully aligned with the S7/S8 Dictionary contracts and the 1A-style bundle/index hashing law.)*

---

# 13) Change control & compatibility **(Binding)**

## 13.1 Versioning model (SemVer)

S9 uses **MAJOR.MINOR.PATCH**. The bundle is **write-once; stage → fsync → single atomic move; file order non-authoritative**. 

## 13.2 What counts as **MAJOR** (non-exhaustive)

Any change that can invalidate previously valid runs or alters bound interfaces/laws:

1. **Bundle identity or location**

   * Changing the bundle partition from `validation/fingerprint={manifest_fingerprint}/` or renaming the path family. *(Fingerprint-scoped is binding.)* 

2. **Hashing / index law**

   * Altering `_passed.flag` semantics, the 1A-style **index.json** shape, or the **ASCII-lex order over relative paths** used to compute the flag digest. *(Hashing/index law is binding.)* 

3. **Required contents**

   * Adding/removing any file from the **minimum set** S9 must publish (e.g., `egress_checksums.json`, `rng_accounting.json`, `s9_summary.json`, `index.json`). *(Presence is binding.)* 

4. **Consumer gate posture**

   * Changing the rule that downstream must verify the PASS flag for the same fingerprint (**“No PASS → no read”**). *(Gate is binding.)* 

5. **Egress contracts referenced by S9**

   * Changing `site_locations` **partitions** `[seed, fingerprint]`, **writer sort** `[merchant_id, legal_country_iso, site_order]`, or the egress **shape**. *(S9 validates against these.)* 

6. **Upstream prep contracts referenced by S9**

   * Changing `s7_site_synthesis` **partitions** `[seed, fingerprint, parameter_hash]` or its PK/writer sort. *(S9 uses S7 as the authoritative keyset.)* 

7. **RNG evidence contracts**

   * Changing RNG **event partitions** `[seed, parameter_hash, run_id]`, the **envelope law** `u128(after)−u128(before)=blocks`, or **per-event budget** for `in_cell_jitter` (`blocks=1`, `draws="2"`). *(S9’s A905 relies on these.)* 

8. **Order posture**

   * Introducing any inter-country order into egress (S8/S9 must remain **order-free**; order comes from 1A S3). 

## 13.3 What may be **MINOR** (strictly backward-compatible)

* **Additive, non-identity** fields in `s9_summary.json` or `rng_accounting.json` (e.g., extra diagnostic counters); keep existing keys and acceptance rules intact.
* **Additional non-flag files** in the bundle **listed in `index.json`** and incorporated into hashing, without removing required files or changing acceptance.
* Clarifications in Registry/Dictionary notes that do **not** alter schema, partitions, writer sort, bundle location, or gate posture. 

## 13.4 What is **PATCH**

Editorial fixes and cross-reference cleanups that do **not** change behaviour, shapes, paths/partitions, writer sort, hashing/index law, gate posture, or acceptance outcomes.

## 13.5 Compatibility baselines (this spec line)

S9 v1.* assumes the following contracts are in force:

* **Egress** `site_locations` — **partitions `[seed, fingerprint]`**, writer sort `[merchant_id, legal_country_iso, site_order]`, **final_in_layer: true**, order-free. 
* **Prep** `s7_site_synthesis` — **partitions `[seed, fingerprint, parameter_hash]`**, writer sort `[merchant_id, legal_country_iso, site_order]`. 
* **RNG evidence** — event streams and core logs under **`[seed, parameter_hash, run_id]`** with the common envelope; `in_cell_jitter` per-event budget **`blocks=1`, `draws="2"`**. 
* **Registry posture** — write-once; atomic move; file order non-authoritative for datasets/logs. 

A **MAJOR** change to any baseline above that affects S9’s acceptance or bundle contracts requires an S9 **MAJOR** (or an explicit compatibility shim).

## 13.6 Forward-compatibility guidance

* **If RNG contracts evolve** (e.g., new event families or different per-event budgets), add **new** accounting sections and validators; do **not** silently reinterpret existing streams. Keep acceptance tolerant only if prior valid runs still pass. 
* **If egress shape/identity must evolve**, **add a new egress ID/anchor** (e.g., `site_locations_v2`) instead of mutating the current one; keep both lanes for ≥1 **MINOR**, mark only one as **final_in_layer: true**, and document migration. 
* **If S7 partitions/keys change**, version S7 accordingly and update S9 to reference the new anchor/Dictionary entry; this is typically **MAJOR** for S9 if acceptance changes. 

## 13.7 Deprecation & migration (binding posture)

* **Dual-lane window:** When introducing a replacement bundle/egress, maintain both old and new lanes for ≥1 **MINOR** with validators accepting either (IDs distinct; one lane marked final at a time).
* **Removal:** Removing a superseded lane is **MAJOR** and MUST be called out in the S9 header with a migration note. 

## 13.8 Cross-state compatibility

* **Upstream handshake:** S9 depends on S7/S8 as stated; a **MAJOR** in S7 or S8 that alters keys/partitions or egress posture requires S9 re-ratification.
* **Downstream gate enforcement:** Consumers of `site_locations` must verify the fingerprint-scoped PASS flag before reading (**“No PASS → no read”**); changing this discipline is **MAJOR**. 

This binds how S9 may evolve without breaking existing, valid fingerprints—and what changes require a coordinated **MAJOR** across the S7/S8/S9 chain.

---

# Appendix A — Bundle tree & hashing law *(Informative)*

## A.1 Bundle layout (fingerprint-scoped)

Root (one folder per fingerprint):

```
validation/
└─ fingerprint={manifest_fingerprint}/
   ├─ MANIFEST.json
   ├─ parameter_hash_resolved.json
   ├─ manifest_fingerprint_resolved.json
   ├─ rng_accounting.json
   ├─ s9_summary.json
   ├─ egress_checksums.json
   ├─ index.json                 # index of all non-flag files
   └─ _passed.flag              # "sha256_hex = <hex64>"
```

The folder name is the **identity** (partition `[fingerprint]`). Any `manifest_fingerprint` embedded inside bundle files should echo this token (path↔embed equality). Publish is **write-once → atomic move** into this folder; file order is non-authoritative.

---

## A.2 `index.json` (reusing the 1A index schema)

The bundle’s `index.json` **lists every non-flag file exactly once** with a **relative**, ASCII-sortable `path`. Example (illustrative only):

```json
[
  { "artifact_id": "manifest",        "kind": "summary", "path": "MANIFEST.json",                     "mime": "application/json" },
  { "artifact_id": "param_hash",      "kind": "summary", "path": "parameter_hash_resolved.json",      "mime": "application/json" },
  { "artifact_id": "fingerprint",     "kind": "summary", "path": "manifest_fingerprint_resolved.json","mime": "application/json" },
  { "artifact_id": "rng_accounting",  "kind": "summary", "path": "rng_accounting.json",               "mime": "application/json" },
  { "artifact_id": "s9_summary",      "kind": "summary", "path": "s9_summary.json",                   "mime": "application/json" },
  { "artifact_id": "egress_checksums","kind": "summary", "path": "egress_checksums.json",             "mime": "application/json" },
  { "artifact_id": "self_index",      "kind": "summary", "path": "index.json",                        "mime": "application/json", "notes": "Index file is itself indexed." }
]
```

Validators rely on the **1A bundle-index schema** (shape + constraints) when checking this file.

**Practical notes (informative):**

* Paths are **relative to the bundle root** (no leading slash).
* Keep paths **ASCII-sortable** (avoid case/locale surprises).
* Prefer POSIX style (`/`); avoid `.` / `..` segments.
* `sha256_hex` here is the per-artifact digest (helpful for auditing); the PASS flag is computed from the **raw bytes** of the files themselves, not from these hex strings.

---

## A.3 Hashing recipe for `_passed.flag`

**File content (single line):**

```
sha256_hex = <hex64>
```

**How to compute `<hex64>` (deterministic):**

1. Read `index.json` and extract the list of **all** artifacts’ `path` values (exclude `_passed.flag` by definition—it is not listed).
2. **Sort** those paths in **ASCII-lexicographic** order.
3. For each path in that order, read the file’s **raw bytes** from the bundle and **concatenate** them (no separators).
4. Compute **SHA-256** over that byte stream and encode as **lower-case hex** → `<hex64>`.
5. Write `_passed.flag` with the exact line above (no trailing spaces).

This is the same **index + ASCII-lex + raw-bytes** law used in the 1A validation bundle. 

**Common pitfalls to avoid (informative):**

* Don’t include `_passed.flag` in `index.json`.
* Don’t hash the **hex strings** in `index.json`; always hash the **files’ bytes** in the sorted order.
* Keep `index.json` stable (canonical key order helps reproducibility, even though the index schema governs shape).
* Ensure files are closed and flushed **before** hashing; publish via a single **atomic move** only after the flag is written. 

---

## A.4 What goes into `egress_checksums.json`

This file records **per-file SHA-256** for the certified egress partition:

```
data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/...
```

Record paths **relative to the bundle root** (so they participate cleanly in ASCII-lex sorting) and map each to its hex digest; you may also include a composite checksum over the partition for convenience. 

---

## A.5 Minimal end-to-end checklist (informative)

* Build all non-flag files (MANIFEST, resolved ids, RNG/accounting, summary, egress checksums).
* Populate **`index.json`** with **every** non-flag file (unique, relative, ASCII-sortable).
* Compute `_passed.flag` exactly as in **A.3**. 
* Stage under a temp dir, then **atomic move** to `validation/fingerprint={manifest_fingerprint}/`. 

---

## A.6 Reader’s gate (informative reminder)

Consumers validate `index.json` and recompute `_passed.flag` before reading egress. If the flag is missing or the digest mismatches, the 1B egress must be treated as **unauthorised** (**No PASS → no read**). 

*(This appendix summarises the tree, the **1A-style** index & hashing law reused by S9, and pragmatic steps to keep the bundle reproducible and byte-stable.)*

---
