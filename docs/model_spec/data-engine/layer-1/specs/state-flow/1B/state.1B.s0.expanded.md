# 1B · State S0 (“Gate-in & Foundations”)

# 0) Document metadata & status **(Binding)**

**State ID (canonical):** `layer1.1B.S0` — “Gate-in & Foundations”
**Document type:** Contractual specification (no code, no pseudocode) — the agent implements this design. 

---

## 0.1 Versioning (SemVer) & effective date

**Versioning scheme:** **MAJOR.MINOR.PATCH** (Semantic Versioning). 

**Initial version:** `v1.0.0` (to be ratified).
**Effective date:** `YYYY-MM-DD` (filled on ratification; release tag + commit recorded in governance). 

### Changes requiring a **MAJOR** bump (breaking)

* Changing **consumer-gate semantics** S0 enforces for 1A hand-off (location/content of `_passed.flag`, hashing rule, or “**no PASS → no read**”).  
* Any change to **dataset IDs**, **schema `$ref` anchors**, or **partition law** for S0 outputs (e.g., `s0_gate_receipt_1B`) or the governed upstreams S0 allows 1B to read. 
* Weakening or altering **path↔embed byte-equality** lineage rules. 
* Altering the **authority/precedence** model (JSON-Schema as sole shape authority; Dictionary as IDs/paths/partitions; Registry as bindings). 

### Changes that are **MINOR** (backward-compatible)

* Adding **nullable/optional fields** to the S0 gate receipt that do not affect PK/UK/sort/partitions. 
* Adding **informative** appendices or non-mandatory instrumentation that does not alter contracts or gates. 

### Changes that are **PATCH** (non-behavioural)

* Editorial clarifications, typo fixes, or examples that **do not change** behaviour, schemas, paths, keys, partitions, or gates. 

---

## 0.2 Normative language (RFC 2119/8174)

Key words **MUST/SHALL/SHOULD/MAY** are normative. Unless explicitly labelled **Informative**, all clauses in this document are **Binding**. This mirrors the convention used in 1A S5–S9.  

---

## 0.3 Document scope & status framing

* **Scope (what S0 does):** verifies the **1A validation gate** for the target fingerprint and **pins** the set of reference inputs 1B may read. S0 **consumes no RNG**.  
* **Non-goals:** no tiling, priors, geometry, or egress production; those occur in subsequent 1B states.
* **Status classes:** default is **Binding**; any *Informative* material (e.g., operational notes) is confined to appendices. 

---

## 0.4 Compatibility window (assumed baselines)

S0 v1.* assumes the following remain on their **v1.* line**; a **MAJOR** bump in any requires S0 re-ratification:

* `schemas.layer1.yaml` (layer-wide RNG/log/core schemas);
* `schemas.ingress.layer1.yaml` (ingress/reference authorities);
* `schemas.1A.yaml` and `dataset_dictionary.layer1.1A.yaml` (since S0 verifies 1A’s gate and permits reading `outlet_catalogue`).  
* `schemas.1B.yaml` (1B subsegment shapes, including `#/validation/s0_gate_receipt`).
* `dataset_dictionary.layer1.1B.yaml` (IDs/paths/retention for 1B, including the receipt path).

---

## 0.5 Lifecycle & ratification record

On ratification, **record**: `semver`, `effective_date`, `ratified_by`, git commit (and optional SHA-256 of this file) in release notes / governance registry; downstreams **continue** to verify the 1A validation gate before reading `outlet_catalogue`.  

---

## 0.6 Cross-references (anchors S0 relies on)

* **Validation bundle & flag rule (1A):** folder shape, `index.json` schema, and `_passed.flag` hashing (ASCII-lex order over indexed files; SHA-256) — **anchor:** `schemas.1A.yaml#/validation/validation_bundle`. **Consumers must verify before reads**.  
* **Dictionary contract (1A):** `outlet_catalogue` is `[seed,fingerprint]`-partitioned, **order-free**, and **gated by** `_passed.flag`. 

---

> **Binding summary:** S0’s change control mirrors 1A’s S5–S9 practice; it locks gate semantics, authority order, and lineage law up front so later 1B states can proceed deterministically against a verified, reproducible base. 

---

# 1) Purpose & scope **(Binding)**

## 1.1 Purpose

S0 establishes a **hard consumer gate** for 1B: it **verifies** the 1A validation bundle for the **target `manifest_fingerprint`** and **only then** authorises any 1B reads of 1A egress, specifically `outlet_catalogue`. If the `_passed.flag` does not exist or its content hash does not match the bundle, S0 **MUST abort**: **no PASS → no read**.   

S0 also **pins the upstream authorities** that 1B may rely on downstream:

* `outlet_catalogue` is **order-free egress** under `[seed,fingerprint]`; consumers obtain inter-country order by **joining** `s3_candidate_set.candidate_rank` (the single order authority).  
* The **precedence chain** is reaffirmed for 1B: **JSON-Schema is the sole shape authority**; the **Dataset Dictionary** governs dataset IDs/paths/partitions/writer policy and repeats consumer gates; the **Artefact Registry** records runtime bindings of the gate artefacts.  

Finally, S0 **records lineage constraints** that 1B must preserve: whenever lineage fields appear both in the path and the rows, **path tokens MUST byte-equal embedded columns** (e.g., `fingerprint` ↔ `manifest_fingerprint`).  

## 1.2 Scope (what S0 does)

* **Gate verification:** locate `…/validation/fingerprint={manifest_fingerprint}/`, recompute the bundle hash over all files listed in `index.json` (ASCII-lex order), compare to `_passed.flag`, and decide PASS/ABORT for this fingerprint.  
* **Authority sealing:** enumerate and freeze the exact upstreams 1B is allowed to read after the gate (at minimum: 1A `outlet_catalogue`; plus shared reference surfaces declared in ingress/layer schemas). 
* **Lineage discipline:** enforce path↔embed equality on any S0 side-effects (e.g., a fingerprint-scoped gate receipt, if emitted) and restate partitions law for downstream states. 
* **Idempotence & audit:** the outcome and any S0 receipt (if used) **MUST be byte-identical** for the same `{fingerprint}` and **MUST NOT** allow partial visibility of validation contents (S9 atomic publish rule).

## 1.3 Non-goals (out of scope for S0)

S0 **does not** perform tiling, priors, cell selection, jitter, or geometry writes; it **does not** redefine inter-country order (which remains solely in `s3_candidate_set`), and it **does not** read any convenience surface that has its own gate (e.g., S6 convenience outputs) unless that separate gate is verified.  

## 1.4 Outcome (entry criteria for S1)

After S0, for the chosen fingerprint:

* 1A’s `_passed.flag` is **verified** against its bundle;
* `outlet_catalogue` is **authorised for read** under `[seed,fingerprint]`;
* lineage/partition rules to be upheld downstream are **restated** (path↔embed equality).   

**Binding effect:** S0 turns 1A’s PASS into a concrete, reproducible **read permission** for 1B and freezes the inputs and lineage law that all subsequent 1B states rely on—nothing more, nothing less. 

---

# 2) Sources of authority & precedence **(Binding)**

## 2.1 Schema authority (single source of **shape** truth)

S0 **MUST** treat **JSON-Schema as the sole authority** for all row shapes, domains, PK/UK/FK declarations, and RNG envelope fields. Avro (if any) is **non-authoritative**. For 1B, the binding schema set is:

* **Layer-wide logs & RNG events:** `schemas.layer1.yaml` (e.g., `#/rng/core/*`, `#/rng/events/*`, envelope fields `before/after/blocks/draws`).  
* **Segment-1B tables & bundles:** `schemas.1B.yaml` (e.g., `#/prep/tile_index`, `#/prep/tile_weights`, `#/egress/site_locations`, `#/validation/validation_bundle_1B`). *(Assumed to exist per brief.)*
* **Segment-1A tables & bundles (read-only for S0 gate):** `schemas.1A.yaml` (e.g., `#/egress/outlet_catalogue`, `#/validation/validation_bundle`).  
* **Ingress / FK targets:** `schemas.ingress.layer1.yaml` (e.g., `#/iso3166_canonical_2024`). 

**Anchor-resolution rule (normative).** When a `$ref` omits its document prefix:

* `#/rng/**` → **layer** schema `schemas.layer1.yaml`;
* `#/egress/**`, `#/prep/**`, `#/validation/**` **for 1B** → `schemas.1B.yaml`;
* `#/egress/**`, `#/s3/**`, `#/validation/validation_bundle` **for 1A (read)** → `schemas.1A.yaml`;
* `#/iso…` and other ingress FKs → `schemas.ingress.layer1.yaml`. 

If a dictionary entry and a schema **disagree on shape or typing**, the **schema wins** and the dictionary **MUST** be corrected. **All I/O resolves via the dictionary; no literal paths.**  

---

## 2.2 Dataset Dictionary (IDs, paths, partitions, writer policy)

The **Dataset Dictionary is authoritative** for **dataset IDs → schema `$ref`**, **canonical paths**, **partition keys**, **writer sort**, and **consumer-gate text**. S0 **MUST** obey it verbatim when locating 1A egress (`outlet_catalogue`) and when declaring any 1B outputs later in this subsegment. Examples from 1A that S0 relies on as precedent:

* **Egress `outlet_catalogue`:** partitions `[seed, fingerprint]`; writer sort `[merchant_id, legal_country_iso, site_order]`; **no cross-country order encoded**; consumers **MUST** verify the fingerprint-scoped gate before reads.  
* **Core logs:** `rng_audit_log`, `rng_trace_log` under `[seed, parameter_hash, run_id]` (trace rows cumulative; **one trace append after each event append**).  

*(For 1B we will introduce `dataset_dictionary.layer1.1B.yaml` with the same authority role.)*

---

## 2.3 Artefact Registry (runtime bindings & gates)

The **Artefact Registry** is authoritative for **runtime artefact bindings**, **gate artefact locations**, and **their semantics** (e.g., which flag gates which dataset). Precedent from 1A (that S0 enforces as the consumption rule):

* **Validation bundle (fingerprint-scoped):** `validation_bundle_1A` at `…/validation/fingerprint={manifest_fingerprint}/`.
* **Consumer flag:** `_passed.flag` with content `sha256_hex = <SHA256(bundle)>`. Consumers **MUST verify** this for the **same fingerprint** **before** reading `outlet_catalogue` → **no PASS → no read**.  

*(For 1B we will introduce `artefact_registry_1B.yaml` using the same gate idiom for 1B egress.)*

---

## 2.4 Authority surfaces (what decides *what*)

S0 **MUST** enforce these lines of authority; if any dependent surface disagrees, S0 **fails closed**:

1. **Inter-country order authority**: **only** 1A **S3** `s3_candidate_set.candidate_rank` (home=0; ranks total & contiguous). Neither 1B S0 nor any 1B output may encode or override cross-country order; **consumers join S3** when order is required.  
2. **Egress content authority (1A)**: `outlet_catalogue` is **order-free**, fingerprint-scoped, and its read is **gated** by the 1A validation bundle’s `_passed.flag`.  
3. **RNG envelope & trace law (layer)**: event rows obey `before/after/blocks/draws`; **non-consuming** families have `blocks=0`, `draws="0"`, with a **single** trace append after each event append. *(S0 consumes no RNG but pins this environment.)*  
4. **Lineage & partitions law**: where lineage appears both in **path** and **rows**, values **MUST byte-equal** (e.g., `manifest_fingerprint` ↔ `fingerprint`, `seed` ↔ path). Identity is by partition keys; partitions are immutable; publish is atomic.  

---

## 2.5 Consumption gate for S0 (binding precondition)

Before **any** S0 read of `outlet_catalogue`, S0 **MUST**:

* Locate `…/validation/fingerprint={manifest_fingerprint}/`;
* Recompute the bundle hash over **all files listed in `index.json`** (ASCII-lex order of `path`), **excluding** `_passed.flag`;
* Assert `_passed.flag == SHA256(validation_bundle_1A)` for the **same fingerprint**; else **ABORT** (**no PASS → no read**).  

---

## 2.6 Precedence chain (tie-break law)

When sources disagree, S0 applies this **precedence**:

1. **JSON-Schema** (layer, 1A, 1B, ingress) — **shape/domains/keys**;
2. **Dataset Dictionary** — **IDs → `$ref`**, **paths**, **partitions**, **writer sort**, **consumer gate text**;
3. **Artefact Registry** — **runtime bindings** and **gate artefact semantics**;
4. **This state spec (S0)** — behavioural obligations & prohibitions consistent with (1)–(3).

Schema outweighs dictionary on shape; dictionary outweighs any literal path; registry fixes which artefact/flag gates what; implementations **MUST NOT** hard-code paths.  

**Binding effect:** With this chain, S0 can deterministically turn a **verified 1A PASS** into explicit **read authority** for 1B and lock the authorities 1B will rely on in later states. 

---

# 3) Run identity & lineage keys **(Binding)**

## 3.1 Canonical tokens (definitions)

* **`seed`** — 64-bit unsigned master RNG seed. Appears in path partitions for **RNG logs/layer1/1B/events** and **egress**. Where embedded (e.g., in event envelopes), it **MUST** equal the path token (see §3.3). 
* **`parameter_hash`** — **lowercase hex64** (SHA-256) of the opened parameter bundle for the run. Partitions **parameter-scoped** datasets and **RNG logs/layer1/1B/events**; where embedded, it **MUST** equal the path token. 
* **`run_id`** — run-scoped identifier (**lowercase 32-hex** by layer schema). Partitions **RNG logs/layer1/1B/events**; where embedded, it **MUST** equal the path token.  
* **`manifest_fingerprint`** (path alias: **`fingerprint`**) — **lowercase hex64** lineage digest for the sealed run. Partitions **egress**; when embedded in rows, **`manifest_fingerprint` MUST equal** the `fingerprint` path token (naming rule). Pattern enforcement (64 lowercase hex) is binding.  

> **Note.** Some 1A surfaces embed a `global_seed`; where present in 1B, it **MUST** equal the `seed` path token (string-equal). 

---

## 3.2 Partition law (by dataset family)

S0 fixes the **partition keys** 1B will use (mirroring 1A so consumers get a uniform lineage discipline):

1. **Egress (order-free)** → partitions **`[seed, fingerprint]`**.
   *Precedent:* `outlet_catalogue` lives at
   `…/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`.  

2. **Parameter-scoped tables** (deterministic inputs/derivations) → partitions **`[parameter_hash]`** (no `seed` in path).
   *Precedent:* `s3_candidate_set`, `s3_integerised_counts`, etc.  

3. **RNG logs & event streams** → partitions **`[seed, parameter_hash, run_id]`**.
   *Precedent:* `rng_audit_log`, `rng_trace_log`, and event families under `logs/layer1/1B/rng/events/...`. 

**Immutability.** Partitions are **immutable**; file/listing order is **non-authoritative** (PK/UK + partitions define truth). 

---

## 3.3 Path↔embed equality (hard law)

Where lineage appears in both the **path** and the **row**, values **MUST be byte-equal**:

* **Egress rows** (1A precedent that 1B adopts):
  `row.manifest_fingerprint == fingerprint` (path token); if `seed` is embedded, `row.seed == seed` (path token). 

* **Parameter-scoped tables**:
  `row.parameter_hash == parameter_hash` (path token). **No `seed` in these paths.** 

* **RNG logs/layer1/1B/events**:
  `row.seed == seed`, `row.parameter_hash == parameter_hash`, `row.run_id == run_id` (all path tokens). Event rows also embed `manifest_fingerprint`, which **MUST** equal the run’s egress fingerprint (synced to the `fingerprint` path used by egress).  

* **Trace nuance (precedent)**: for `rng_trace_log`, embedded envelope fields present (`seed`, `run_id`) equal path tokens; `parameter_hash` may be path-only. 1B follows the same rule. 

Violations are **structural errors** and **MUST** fail validation. 

---

## 3.4 Identity in S0 side-effects

If S0 emits a **`s0_gate_receipt_1B`** (fingerprint-scoped), it **MUST**:

* live under `…/fingerprint={manifest_fingerprint}/`;
* embed `manifest_fingerprint` that **equals** the path token; and
* enumerate the exact upstreams and reference surfaces sealed for 1B.
  This mirrors the 1A lineage law and keeps S0 idempotent and auditable.  

---

## 3.5 Downstream expectations (carried from 1A)

* **Order authority** stays outside egress: cross-country order comes **only** from `s3_candidate_set.candidate_rank`; egress stays order-free and consumers **join** S3 when needed. Identity/lineage rules above ensure that join is deterministic. 

**Binding effect:** With these tokens, partitions, and equality checks fixed, 1B inherits 1A’s deterministic lineage model: every read/write is attributable to a unique `{seed, parameter_hash, run_id, manifest_fingerprint}`, and any drift is detectably non-conformant. 

---

# 4) Entry gate to 1A (consumer hand-off) **(Binding)**

## 4.1 Locate the validation bundle (by **fingerprint**)

Given a target `manifest_fingerprint`, S0 **MUST** resolve the 1A validator bundle at:

```
data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/
```

This folder is fingerprint-scoped; bundle files embed the same `manifest_fingerprint` as the path token. 

**Preconditions inside the folder (MUST hold):**

* `index.json` exists and lists **every** non-flag file **exactly once**; `artifact_id` values are unique and `path` entries are **relative** (used for hashing order). 
* Required files (minimum set) are present (e.g., `MANIFEST.json`, `rng_accounting.json`, `egress_checksums.json`, `s9_summary.json`, `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`, `index.json`). 

## 4.2 Verify the consumer gate flag (the **only** read gate for 1A egress)

S0 **MUST** enforce the canonical **no PASS → no read** rule by validating `_passed.flag` co-located in the bundle folder:

```
…/validation/fingerprint={manifest_fingerprint}/_passed.flag
```

**Flag content (exact):** UTF-8 text, exactly one line (trailing newline optional) `sha256_hex = <hex64>` (lowercase 64-hex; no leading/trailing spaces). Producers/consumers MUST treat the file bytes as UTF-8; comparison ignores a single terminal `\n` if present.

**Hashing rule S0 MUST implement:**

1. Read `index.json`.
2. List **all** files named in `index.json` (exclude `_passed.flag`).
3. Concatenate their **raw bytes** in **ASCII-lexicographic order of the `path` entries**.
4. Compute SHA-256 of the concatenation and compare to `<hex64>` from `_passed.flag`.
   If the file is missing, the set is incomplete, `path` is not relative/ASCII-sortable, or the hash **mismatches**, the gate **FAILS**.  

**Atomicity assumption:** S9 publishes the bundle **atomically** (stage → compute flag → single rename), so partial contents **must not** be visible; missing flag or mismatch means **not passed**. 

## 4.3 Decide PASS / ABORT (and what it enables)

* **PASS:** `_passed.flag` matches `SHA256(validation_bundle_1A)` for this fingerprint → 1B is **authorised** to read 1A egress for this fingerprint. This is the only consumer gate for `outlet_catalogue`.  
* **ABORT:** `_passed.flag` missing or mismatched → 1B **MUST NOT** read `outlet_catalogue` for this fingerprint (**no PASS → no read**). 

> Scope boundary: parameter-scoped receipts (e.g., S6 membership receipts) are **separate** and do **not** substitute for this fingerprint gate; if 1B later reads such conveniences, it must verify those receipts **in addition** to this gate. 

## 4.4 Open the 1A egress only after PASS (path & lineage checks)

On **PASS**, S0 **MAY** open:

```
data/layer1/1A/outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/
```

and **MUST** re-assert **path↔embed equality** for rows it touches: `outlet_catalogue.manifest_fingerprint == fingerprint` (path token) and *(if present)* `global_seed == seed`. (Egress remains **order-free** across countries; consumers join S3 for order.)

## 4.5 Index hygiene S0 MUST check (pre-hash sanity)

Before computing the hash in §4.2, S0 **MUST** validate these index invariants (fail-closed on any breach):

* Every non-flag file in the folder appears **once** in `index.json`; `artifact_id` is unique.
* All `path` values in `index.json` are **relative** (no leading `/`, no `..`) and ASCII-sortable.  

## 4.6 What S0 MUST NOT do

* **Do not** read `outlet_catalogue` (or any other 1A surface) **before** the gate passes. 
* **Do not** infer cross-country order from egress; order authority remains **S3 `candidate_rank`**. 

## 4.7 Optional hardening (recommended, not required to pass the gate)

After a successful flag check, S0 **MAY** (advised for supply-chain assurance) recompute the bundle hash from `index.json` (ASCII-lex over `index.path`; flag excluded) and optionally re-hash `fingerprint_artifacts.jsonl` / `param_digest_log.jsonl` if present. On mismatch, treat it as a **producer contract violation** and abort consumption; do **not** reinterpret or regenerate `_passed.flag` (the gate remains defined solely by the bundle hash).

---

**Binding effect:** This section makes S0 a deterministic **consumer gate**: it proves the fingerprint’s bundle using the exact `index.json`→ASCII-lex→SHA-256 rule, then—and only then—permits 1B to read `outlet_catalogue` for that fingerprint, while preserving lineage equality and order-authority separation.  

---

# 5) Inputs S0 pins for 1B **(Binding)**

S0 **fixes** which upstream datasets 1B is allowed to rely on. Reads of 1A egress are **conditioned** on the PASS gate; reference/FK surfaces are sealed for downstream use. Anything not listed here is **out-of-scope** for S0.

---

## 5.1 Authoritative 1A egress (read **only after** PASS)

* **`outlet_catalogue`** — immutable outlet stubs per `(merchant_id, legal_country_iso, site_order)`; **order-free across countries** (downstreams must join S3 for inter-country order).
  **Path/partitions:** `data/layer1/1A/outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` (**[seed, fingerprint]**).
  **Consumer gate (binding):** read **only if** the co-located `_passed.flag` under `…/validation/fingerprint={manifest_fingerprint}/` **exists** and its content equals **`SHA256(validation_bundle_1A)`** for the same fingerprint (**no PASS → no read**).   

---

## 5.2 Order authority surface (read-only, for joins in later 1B states)

* **`s3_candidate_set`** — deterministic, **single** authority for inter-country order; provides **`candidate_rank`** (total, contiguous; home rank = 0).
  **Path/partitions:** `data/layer1/1A/s3_candidate_set/parameter_hash={parameter_hash}/` (**[parameter_hash]**).
  **Note:** S0 does **not** need to read this; it **pins** it as the only permissible order source for later 1B states.  

*(Informative contrast for reviewers: `country_set` exists but is **not authoritative for inter-country order**.)* 

---

## 5.3 Reference / FK targets (sealed for 1B use)

* **`iso3166_canonical_2024`** — canonical ISO-3166-1 alpha-2 list (FK target for `country_iso` / `legal_country_iso`). Schema anchor: `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`.  
* **`world_countries`** — GeoParquet country polygons (for later point-in-country checks). Declared consumable by **1B** in the dictionary. 
* **`tz_world_2025a`** — time-zone polygons (RESERVED for later segments such as 2A/2B). Provenance-only for 1B v1; **not consumed** by any 1B state. Schema anchor: `schemas.ingress.layer1.yaml#/tz_world_2025a`.
* **`population_raster_2025`** — population COG raster (spatial prior used by 1B). Declared consumable by **1B** in the dictionary; schema anchor in ingress.  

---

## 5.4 Inputs S0 **MUST NOT** read without separate gates

* **`s6_membership`** (optional convenience surface): **forbidden** unless the **S6 PASS receipt** at
  `data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/(S6_VALIDATION.json, _passed.flag)` is verified **for the same `{seed, parameter_hash}`**. *(S0 does not require this; it pins the rule for any future consumer in 1B.)*  

---

## 5.5 Lineage expectations on any rows S0 touches (recap)

Where lineage fields appear both in **path** and **rows**, values **MUST byte-equal**: for egress reads,
`outlet_catalogue.manifest_fingerprint == fingerprint` and (if embedded) `global_seed == seed`. 

**Binding effect:** After §4’s PASS check, S0 authorises **only** the inputs above for 1B, preserves order-authority separation (join S3 for order), and locks the FK/reference surfaces 1B will rely on downstream.

---

# 6) Environment invariants (numeric & RNG) **(Binding)**

> S0 **consumes no RNG**; it **pins** the numeric environment and RNG protocol that **all** 1B states must use. These mirror the 1A baselines so replay and validation remain bit-stable across the layer. 

## 6.1 Numeric environment (must hold)

* **Format:** IEEE-754 **binary64** for any computation that can affect branching, ordering, acceptance, counts, or integerisation. **No FMA**, **RNE** rounding, **no FTZ/DAZ**. Any NaN/Inf on decision paths is a **hard error**. 
* **Deterministic libm profile:** pin an approved math profile for `exp/log/log1p/expm1/sqrt/sin/cos/atan2/pow/tanh/erf/lgamma`; results are **bit-deterministic** under the pinned profile; `sqrt` must be correctly rounded. 
* **Constants:** decision-critical constants **MUST** be encoded as **binary64 hex literals** (not decimal recomputation). 
* **Serial kernels:** reductions/sorts that influence decisions **MUST** execute in fixed order; parallel “fast-math”/contraction are **forbidden** on decision paths. 
* **Artefactisation:** `numeric_policy.json` and `math_profile_manifest.json` are part of the sealed set; changing either flips the **`manifest_fingerprint`**. 

## 6.2 RNG algorithm & scope (must hold)

* **Algorithm:** Counter-based **philox2x64-10** (layer-wide). S0 fixes this for 1B; producers and validators announce it in the audit log. 
* **Open-interval uniforms:** map 64-bit outputs to **strict-open** (0,1) via the hex-float rule; clamp the rare `u==1.0` to `1−2⁻⁵³`. **Exact 0.0/1.0 MUST NOT occur.** 
* **Keyed substreams:** every event family **derives** its Philox key/counter deterministically from frozen literals (domain string + label + ID tuple) via **SHA-256**; draws **MUST** come from that substream with a monotonically advancing 128-bit counter. 

## 6.3 Lane policy & budget classes (must hold)

* **Single-uniform families** consume the **low lane** of one Philox block, **discard** the high lane ⇒ **`blocks=1`, `draws="1"`** (e.g., `gumbel_key`). 
* **Two-uniform families** consume **both lanes** of one block ⇒ **`blocks=1`, `draws="2"`** (e.g., Box–Muller normal). This pattern governs 1B two-uniform samplers such as “point jitter in cell.”  
* **Non-consuming finals/markers** (if any) keep counters unchanged ⇒ **`before==after`, `blocks=0`, `draws="0"`**. 

## 6.4 Envelope fields & identities (must hold)

Every RNG **event** row (any 1B event family) carries the **layer envelope**:
`{ ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo}, draws, blocks }`.

**Identities:**

* `blocks := u128(after) − u128(before)` (unsigned 128-bit); **independent** of `draws`.
* `draws` is a **decimal uint128 string** equal to **actual** uniforms consumed by that event.
* Path↔embed **byte-equality** for `{seed, parameter_hash, run_id}` is **binding**.  

## 6.5 Trace & audit duties (must hold)

* **`rng_audit_log`**: one row at run start, before any RNG event, announcing `(seed, manifest_fingerprint, parameter_hash, algorithm, counters, build commit, ts_utc)`. **Core log; not an event.** 
* **`rng_trace_log`**: **append exactly one** cumulative row **after each** RNG event append for the same `(module, substream_label)`; on the **final** row, validators check:
  `draws_total = Σ event.draws`, `blocks_total = Σ event.blocks`, `events_total = #events`.  

## 6.6 Timestamps, ordering & file semantics (must hold)

* **`ts_utc`** format: RFC-3339 UTC with **exactly 6 fractional digits** (microseconds). **Observational only**—never used for ordering.  
* **Order authority:** ordering/replay is by **counters only**; **file order is non-authoritative**. 
* **Set semantics:** JSONL streams are treated as **sets**; duplicate identity rows are structural errors. 

## 6.7 Partitions & lineage (must hold)

* **Events & core logs** live under `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`; embedded lineage (when present) **MUST equal** path tokens. 
* **Egress** remains `[seed, fingerprint]`; parameter-scoped tables remain `[parameter_hash]`. (S0 restates; downstream states apply.) 

## 6.8 Concurrency & overflow guards (must hold)

* **Per-merchant substreams are serial**; parallelism is across merchants only. Merge/sink stages **must** be deterministic with respect to writer-sort policies. 
* **Trace totals are uint64 (saturating)**; producers **MUST** detect imminent overflow and abort with the budget-violation failure before saturation. 

## 6.9 Label registry & anchors (must hold)

* `module` / `substream_label` are **registry-closed** literals per event family. 1B will register its own families and labels; **consumers/validators must enforce exact literal matches**. 
* Bare `$ref` anchors resolve to **layer** for `#/rng/**` and to the subsegment schema for `#/prep/**`, `#/egress/**`, `#/validation/**` (1A precedent; 1B mirrors). 

## 6.10 1B examples (binding budgets by family)

* **`raster_pick_cell`** (1B) — **single-uniform**: **`blocks=1`, `draws="1"`**; one event per site to pick a raster cell. *(New family; budgets follow the single-uniform rule.)* 
* **`point_jitter`** (1B) — **two-uniform**: **`blocks=1`, `draws="2"`** to place `(lat,lon)` uniformly within the chosen cell. *(New family; budgets follow the two-uniform rule; cf. Box–Muller budget.)*  

## 6.11 Prohibitions (must not)

* **MUST NOT** consume any RNG in S0. 
* **MUST NOT** rely on timestamps or file order for replay; **counters only**. 
* **MUST NOT** deviate from open-interval mapping, lane policy, or envelope identities; **non-consuming** events **MUST** keep counters equal. 

**Binding effect:** S0 freezes the numeric profile and RNG protocol—**binary64/RNE, philox2x64-10, strict-open U(0,1), keyed substreams, `before/after/blocks/draws` envelope, trace-after-every-event**—so every 1B state is replayable, auditable, and byte-stable under the same gates that govern 1A.  

---

# 7) Allowed reads & forbidden accesses **(Binding)**

S0 acts as a **consumer gate**. Until the 1A validation gate passes for the target `manifest_fingerprint`, S0’s read surface is restricted to the validation bundle itself. Only after **PASS** may S0 touch 1A egress (`outlet_catalogue`). Anything not listed here is **out-of-scope** for S0.

---

## 7.1 Reads **permitted before PASS** (validation bundle only)

S0 **MUST** read **only** the fingerprint-scoped validation folder:

```
data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/
```

and, inside it, the files required to verify the consumer gate:

* `index.json` (bundle index; every non-flag file appears **exactly once** with a **relative** `path`; `artifact_id` unique; ASCII-lex sortable),
* all files listed in `index.json` (minimum set includes `MANIFEST.json`, `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`, `rng_accounting.json`, `s9_summary.json`, `egress_checksums.json`) — **as defined by** `schemas.1A.yaml#/validation/validation_bundle`,
* `_passed.flag` (single line: `sha256_hex = <hex64>`).
  S0 uses these to recompute the ASCII-lex concatenation hash and compare with `_passed.flag`.    

**Optional extras** (if present) **MAY** be read and are included in the hash: `param_digest_log.jsonl`, `fingerprint_artifacts.jsonl`, `numeric_policy_attest.json`, `DICTIONARY_LINT.txt`, `SCHEMA_LINT.txt`. 

---

## 7.2 Reads **permitted after PASS** (egress; lineage checks)

Only **after** `_passed.flag` matches `SHA256(validation_bundle_1A)` for the **same** fingerprint, S0 **MAY** open:

```
data/layer1/1A/outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/
```

and **MUST** re-assert path↔embed equality where present:
`outlet_catalogue.manifest_fingerprint == fingerprint` (path token) and *(if present)* `global_seed == seed`. `outlet_catalogue` is **order-free**; cross-country order is obtained later by joining S3 `candidate_rank`.    

> S0 **does not** need to read S3 itself; it merely **pins** S3 as the sole order authority for downstream 1B states. 

---

## 7.3 Surfaces S0 **pins** (read by later 1B states, not by S0)

* **`s3_candidate_set`** (parameter-scoped): the **single** authority for inter-country order; home has `candidate_rank = 0`. S0 records this authority boundary; later 1B states **must** join S3 when order is required.  

---

## 7.4 **Forbidden** accesses (fail-closed)

Until PASS:

* **Do not read** `outlet_catalogue` (or any other 1A egress). **No PASS → no read.** 

Always:

* **Do not infer order** from egress, file order, or ISO codes; inter-country order comes **only** from `s3_candidate_set.candidate_rank`.   
* **Do not read** S6 convenience surfaces (e.g., `s6_membership`) unless their **own** PASS receipt (seed+parameter-scoped) is verified for the same `{seed, parameter_hash}`. *(S0 doesn’t need them; this pins the rule for any future 1B consumer.)*  
* **Do not trust** any file in the validation folder that is **not** listed in `index.json`; index must enumerate **every** non-flag file **once** with a **relative** `path`. Reject absolute paths or `..` segments. 
* **Do not rely** on physical file order for any semantic; file order is **non-authoritative**. 

---

## 7.5 Dictionary/Schema resolution (how S0 locates reads)

All path resolutions **MUST** follow the **Dataset Dictionary** and schema anchors—**no hard-coded paths** outside those contracts. If a dictionary entry and a schema disagree on shape or typing, the **schema wins** and the dictionary must be corrected.  

**Binding effect:** S0’s read surface is **minimal and deterministic**—validation bundle first; on PASS, `outlet_catalogue` under `[seed,fingerprint]`; S3 is pinned as the **only** order source. Any other access is a contract breach and **MUST** fail closed.  

---

# 8) Outputs & side-effects **(Binding)**

S0 produces **one** artefact on **PASS** and **nothing** on **ABORT**. It **consumes no RNG** and **must not** modify any 1A partitions.

---

## 8.1 Required output on PASS — `s0_gate_receipt_1B` (fingerprint-scoped)

**Purpose.** A minimal receipt that proves §4’s gate was verified for the target fingerprint and enumerates the upstream surfaces S0 sealed for downstream 1B states. It is **not** a substitute for 1B’s S9 validation bundle; it only records the 1A consumer hand-off.
**Partition:** `[fingerprint]` (where the path token **equals** the embedded `manifest_fingerprint`). **No `seed` partition here.**  

**Canonical template (Dictionary owns the exact final path):**
`data/layer1/1B/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt.json`
*(Dictionary governs the final path/format; this spec fixes the partition to `[fingerprint]` and the equality law.)* 

**Schema anchor:** `schemas.1B.yaml#/validation/s0_gate_receipt`

**Required fields (non-exhaustive, Binding):**

* `manifest_fingerprint : hex64` — **MUST** byte-equal the `fingerprint` path token.
* `validation_bundle_path : string` — resolved folder for `data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/`. 
* `flag_sha256_hex : hex64` — the exact hex read from `_passed.flag` after recomputation. 
* `verified_at_utc : RFC-3339 (microseconds)` — observational timestamp (non-semantic).
* `sealed_inputs : array<object>` — entries S0 authorises for 1B, at minimum:

  * `{ id:"outlet_catalogue", partition:["seed","fingerprint"], schema_ref:"schemas.1A.yaml#/egress/outlet_catalogue" }` (order-free egress; only readable after PASS).  
  * `{ id:"s3_candidate_set", partition:["parameter_hash"], schema_ref:"schemas.1A.yaml#/s3/candidate_set" }` (sole inter-country order authority; pinned for later joins).  
  * `{ id:"iso3166_canonical_2024", "schema_ref":"schemas.ingress.layer1.yaml#/iso3166_canonical_2024" }`,
    `{ id:"world_countries",        "schema_ref":"schemas.ingress.layer1.yaml#/world_countries" }`,
    `{ id:"population_raster_2025","schema_ref":"schemas.ingress.layer1.yaml#/population_raster_2025" }`
    (FK/geo surfaces declared consumable by 1B; Dictionary will encode these same anchors).  
  * `{ id:"tz_world_2025a", "schema_ref":"schemas.ingress.layer1.yaml#/tz_world_2025a" }` (FK/geo surfaces reserved for later segments; dictionary encodes their schema refs).
* `notes : string` — optional free-form, non-semantic.

**Cardinality.** Exactly **one** receipt per `{manifest_fingerprint}` PASS. Re-runs for the same `{fingerprint}` **MUST** be byte-identical. 

---

## 8.2 Side-effects on PASS (and only on PASS)

* **Read-authorisation becomes active** for `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/` (order-free; consumers must join S3 for inter-country order). S0 may **read** it, but S0 **does not** write to any 1A datasets.  
* **No RNG logs/layer1/1B/events** are written in S0 (S0 consumes no RNG); any audit lines belong to general state audit, not RNG channels. 

---

## 8.3 Behaviour on ABORT (flag missing/mismatch)

* **No outputs are written.** Absence of `s0_gate_receipt_1B` under the fingerprint is the expected state.
* Downstream states **MUST NOT** read `outlet_catalogue`; 1A’s **no PASS → no read** remains in force. 

---

## 8.4 Writer policy, atomicity & idempotence (receipt)

* **Atomic publish:** stage the receipt under a temp dir, fsync, then perform a **single atomic rename** into `…/fingerprint={manifest_fingerprint}/`. **Partial contents MUST NOT become visible.** 
* **Immutability:** once published, the receipt partition is **immutable**; a subsequent publication for the same identity must be **byte-identical** or a no-op. 
* **Path↔embed equality:** `row.manifest_fingerprint == fingerprint` path token **MUST** hold. 

---

## 8.5 Prohibitions (fail-closed)

S0 **MUST NOT**:

* write or modify any 1A partition (egress, parameter-scoped tables, RNG logs/layer1/1B/events, or the 1A validation bundle); 
* embed or infer **inter-country order** anywhere; order authority remains **S3 `candidate_rank`** and is only ever obtained by join; 
* write any seed-partitioned artefact (S0 is fingerprint-scoped only). 

---

## 8.6 Rationale (link to precedent)

This output model mirrors 1A’s lineage and publish rules: fingerprint-scoped hand-off artefacts, atomic publish, strict path↔embed equality, and **no PASS → no read**. It keeps S0 **cheap & idempotent**, while giving later 1B states a single, verifiable receipt proving that the only permissible 1A read (`outlet_catalogue`) was authorised and that order authority must still come from S3.   

---

# 9) Lineage & partitions law (applied by S0) **(Binding)**

S0 fixes lineage identity and partitioning for everything it **reads** or **writes**. Where lineage fields appear both in a **path** and as **embedded columns**, values **MUST byte-equal**. File order is **non-authoritative**; identities are by **partition keys + PK/UK** only.  

---

## 9.1 Partition families & identities (normative)

**(a) Fingerprint-scoped egress (read by S0 after PASS).**
**Dataset:** `outlet_catalogue` → **partitions `[seed, fingerprint]`** at
`data/layer1/1A/outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`.
**Identity:** `(dataset='outlet_catalogue', seed, manifest_fingerprint)`.
**Order note:** egress **does not encode** inter-country order; consumers must join S3.  

**(b) Parameter-scoped authorities (read later in 1B, pinned by S0).**
Examples: `s3_candidate_set`, `s3_integerised_counts`, `s3_site_sequence` → **partitions `[parameter_hash]`** at `…/parameter_hash={parameter_hash}/`.
**Identity:** `(dataset_id, parameter_hash)`.  

**(c) RNG logs & event streams (layer law; S0 reads none, but pins the regime).**
`rng_audit_log`, `rng_trace_log`, and all `rng_event_*` → **partitions `[seed, parameter_hash, run_id]`** at `logs/layer1/1B/rng/.../seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`.
**Identity:** `(stream_name, seed, parameter_hash, run_id)`. 

**(d) Validation bundle (S0 reads to enforce the gate).**
`validation_bundle_1A/` at `data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/` → **partition `[fingerprint]`**; `_passed.flag` lives **in the same folder**.
**Identity:** `(bundle, manifest_fingerprint)`.  

**(e) S0 output (if produced): `s0_gate_receipt_1B`.**
**Partition `[fingerprint]`**; embedded `manifest_fingerprint` **MUST** equal the path token (naming rule). *(Path string governed by the 1B dictionary; the partition law is fixed here.)* 

---

## 9.2 Path↔embed equality (must hold)

Where lineage appears in both **path** and **row**, values **MUST byte-equal**:

* **Egress rows (S0 reads):**
  `outlet_catalogue.manifest_fingerprint == fingerprint` (path token) and, if present, `global_seed == seed`. Pattern for `manifest_fingerprint`: `^[a-f0-9]{64}$`. 
* **Parameter-scoped tables:**
  `row.parameter_hash == parameter_hash` (path token). `produced_by_fingerprint` (if present) is **informational only**. 
* **RNG logs/layer1/1B/events (layer law):**
  rows embed `{seed, parameter_hash, run_id}` that **equal** their path tokens; `manifest_fingerprint` embeds the run’s egress fingerprint (not a path token). 

Any violation is **structural FAIL**. 

---

## 9.3 Key formats (schema-anchored)

* `seed`: **uint64**.
* `run_id`: **lowercase hex32**.
* `parameter_hash`, `manifest_fingerprint`: **lowercase hex64**.
  These formats are enforced by the layer/1A schemas and validated by S9.  

---

## 9.4 Immutability, atomic publish, idempotence

* **Atomic publish** for any partition S0 writes (e.g., `s0_gate_receipt_1B`): stage → fsync → **single atomic rename** into the dictionary path; **no partial contents** may be visible.  
* **Immutability:** once published, a partition is **write-once**. Re-publishing the same identity must be **byte-identical** or a no-op. **File order is non-authoritative**. 
* **Idempotence:** with identical inputs, numeric policy, and lineage, outputs are **bit-identical** (egress) and **value-identical** (streams) per writer policy. 

---

## 9.5 Writer sort & set semantics

* **Egress writer sort:** `[merchant_id, legal_country_iso, site_order]`; S9 verifies this **within and across files**; do **not** rely on physical file order.  
* **JSONL logs/layer1/1B/events:** treated as **sets**; duplicate identity rows are errors; physical line order across files/parts is **non-semantic**. 

---

## 9.6 Order authority separation (carried forward)

Egress is **order-free**; inter-country order comes **only** from `s3_candidate_set.candidate_rank` (total & contiguous; home rank = 0). S0 must preserve this boundary (it **MUST NOT** infer order from egress, file order, or ISO codes). 

---

## 9.7 What S0 must check when it reads/writes

* When reading `outlet_catalogue` after PASS, S0 **MUST** assert path↔embed equality as in §9.2. 
* If S0 writes `s0_gate_receipt_1B`, it **MUST**: (i) partition by `[fingerprint]`, (ii) embed `manifest_fingerprint` equal to the path token, and (iii) publish atomically (idempotent).  

---

## 9.8 Failure classifications (signals S9 will raise if S0 breaks lineage)

Downstream validation **WILL** flag lineage/partition drift using canonical codes, e.g., `E_LINEAGE_RECOMPUTE_MISMATCH`, `E_WRITER_SORT_BROKEN`, or `E_ORDER_AUTHORITY_DRIFT`. S0 must keep this section true so later states pass S9 unchanged. 

**Binding effect:** With these rules, S0 guarantees that every 1B read/write is attributable to a unique `{seed, parameter_hash, run_id, manifest_fingerprint}` tuple under immutable, atomically-published partitions—exactly mirroring 1A’s lineage discipline.  

---

# 10) Operational rules (practicalities) **(Binding)**

S0’s ops contract is minimal and deterministic: **verify gate → (optionally) write one receipt → stop.** No RNG, no egress mutation, no partial visibility.

## 10.1 Path resolution & permissions

* **Dictionary-only I/O.** Resolve dataset IDs to paths via the **Dataset Dictionary**; literal paths are non-conformant. 
* **Storage & encryption.** Reads/writes **MUST** occur on encrypted object storage; enforce **SSE-KMS** at bucket level (deny unencrypted PUTs).  

## 10.2 Atomicity (no partials)

* **Bundle read is atomic by construction.** Treat any missing `_passed.flag` or index mismatch as **not passed**; S9 publishes the bundle/flag with a **single atomic rename**. 
* **Receipt write (if produced) is atomic.** **Stage → fsync → atomic rename** into `…/fingerprint={manifest_fingerprint}/`. **No partial contents** may become visible. Partitions are **immutable** after publish.  

## 10.3 Idempotence & skip-if-final

* Re-running S0 for the same `{fingerprint}` **MUST** yield a **byte-identical** `s0_gate_receipt_1B` or be a no-op. Publishing to an existing identity must be byte-identical or skipped.

## 10.4 Read discipline & access patterns

* **Before PASS:** S0 **MUST** read **only** the validation folder and `_passed.flag` + files listed by `index.json` (relative paths, ASCII-sortable).  
* **After PASS:** S0 **MAY** read `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`; enforce path↔embed equality (`manifest_fingerprint == fingerprint`, `global_seed == seed`). **Do not** infer order from egress.  
* **Predicated listing.** Reads should be **partition-token–predicated** (avoid bucket-wide scans). 

## 10.5 Formats, headers & compression (receipt & reads)

* **Receipt file:** JSON (`Content-Type: application/json`). (Dictionary will own the exact path; partition is `[fingerprint]`, §8.) 
* **Egress (if read):** Parquet (`application/vnd.apache.parquet`) with sort `[merchant_id, legal_country_iso, site_order]`; **file order is non-authoritative**.  
* **Helpful metadata (optional):** `x-run-seed`, `x-parameter-hash`, `x-run-id`, `x-content-sha256`. 

## 10.6 Integrity hardening (recommended but enforceable where present)

* If the bundle includes **optional extras** (`param_digest_log.jsonl`, `fingerprint_artifacts.jsonl`, `numeric_policy_attest.json`, lints), they **ARE** part of the flag hash and **MUST** be indexed.  
* Sidecar SHA-256 for parts and folder manifests **SHOULD** be honoured when present; treat mismatches as gate failure. 

## 10.7 Concurrency & single-writer expectations

* Multiple S0 workers targeting the same fingerprint **MUST** converge to one atomic receipt (or none on ABORT); no cooperative multi-part writes are allowed for S0. Idempotence + atomic rename guarantee correctness under contention. 

## 10.8 Retention & housekeeping

* Retention/TTL is governed by the Dictionary; defaults mirror 1A (bundles ~365d). Keep partition dirs clean: only parts, checksums, manifests—no temp artefacts.  

## 10.9 Prohibitions (ops)

* S0 **MUST NOT** modify any **1A** partition (egress, parameter-scoped, logs, bundle). It may only **read** them under §7 rules. 
* S0 **MUST NOT** rely on physical file order for any semantic; identities are by **partition keys + PK/UK**. 

**Binding effect:** These rules make S0 operationally safe: dictionary-resolved paths, encrypted storage, atomic/no-partials publishing, idempotent receipts, strict gate-first reads, and non-authoritative file order—exactly mirroring 1A’s validated publish discipline.   

---

# 11) Exit criteria (what must be true before S1 may start) **(Binding)**

S1 **MUST NOT** begin until **all** items below are **true** for the target `{seed, manifest_fingerprint, parameter_hash}`.

**E1. 1A PASS verified (gate).**
The fingerprint-scoped bundle exists at `…/validation/fingerprint={manifest_fingerprint}/`, `index.json` lists every non-flag file exactly once (relative paths), and `_passed.flag` content equals **SHA-256** over the raw bytes of **all** files listed in `index.json` in **ASCII-lex** path order. **No PASS → no read.**   

**E2. Read authorisation for `outlet_catalogue`.**
Given **E1**, the egress partition at
`data/layer1/1A/outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` is authorised for read; S0 has re-asserted path↔embed equality where present: `manifest_fingerprint == fingerprint` (path token) and *(if present)* `global_seed == seed`. (Cross-country order is **not** encoded in egress.)  

**E3. Authority boundaries recorded.**
S0 has pinned that **inter-country order** comes **only** from `s3_candidate_set.candidate_rank` (home rank = 0; total, contiguous). Any ordering needed downstream will be obtained by **join**; egress remains order-free.  

**E4. Inputs sealed for 1B.**
S0 has enumerated the exact upstreams 1B may rely on downstream:
- `outlet_catalogue` (egress; `[seed,fingerprint]`),
- `s3_candidate_set` (order authority; `[parameter_hash]`),
- FK/geo references: `iso3166_canonical_2024`, `world_countries`, `population_raster_2025`, `tz_world_2025a` (anchors in ingress schema / dictionary; tz_world reserved for later segments).  

**E5. S0 receipt published (idempotent).**
`s0_gate_receipt_1B` exists under `…/fingerprint={manifest_fingerprint}/…`, validates against its schema, and embeds `manifest_fingerprint` **byte-equal** to the path token. Re-publishing the same identity is byte-identical (atomic publish; partitions immutable). *(Receipt is the only S0 output; format/path are governed by the 1B dictionary.)*  

**E6. Numeric/RNG baselines pinned for 1B.**
Layer baselines are in force (IEEE-754 **binary64**, RNE, **no** FMA/**no** FTZ/DAZ; counter-based Philox; envelope & trace rules), as inherited from 1A S0/S9. *(S0 consumes no RNG, but pins the environment for 1B.)* 

**E7. No forbidden accesses occurred in S0.**
Before PASS, S0 touched **only** the validation folder; after PASS, S0 did **not** read any convenience/gated surface (e.g., S6 membership) without its **own** co-located PASS receipt.  

**E8. Writer/partition discipline acknowledged for downstream use.**
For `outlet_catalogue`, S0 has acknowledged the dictionary contract: partitions `[seed,fingerprint]`, writer sort `[merchant_id, legal_country_iso, site_order]`, and file order **non-authoritative**—so S1 can rely on deterministic joins and scans.  

> **Binding effect:** When **E1–E8** hold, S0 has turned 1A’s PASS into a concrete, reproducible **read permission**, sealed the precise upstreams and authority boundaries for 1B, and published an immutable receipt—so S1 can start deterministically without re-deciding gates or lineage.

---

# 12) Failure modes & canonical error codes **(Binding)**

> Any failure below is **blocking**. On **FAIL**, S0 **MUST NOT** read `outlet_catalogue` and **MUST NOT** publish a receipt; 1B **MUST** remain stopped (**no PASS → no read**). 

## 12.1 Gate & bundle integrity (fingerprint-scoped)

* **`E_BUNDLE_MISSING`** — `…/validation/fingerprint={manifest_fingerprint}/` not found. **Action:** ABORT. **Fix:** run 1A validation for this fingerprint. 
* **`E_INDEX_MISSING`** — `index.json` absent. **Action:** ABORT. **Fix:** regenerate bundle with required files. 
* **`E_INDEX_INVALID`** — `index.json` violates rules (non-relative paths, non-ASCII sortability, duplicate `artifact_id`, or a non-indexed file present). **Action:** ABORT. **Fix:** make all paths **relative**, ASCII-sortable; each non-flag file listed **exactly once**. 
* **`E_PASS_MISSING`** — `_passed.flag` absent in the bundle folder. **Action:** ABORT. **Fix:** publish PASS correctly (S9 writes the flag only on PASS). 
* **`E_FLAG_FORMAT_INVALID`** — `_passed.flag` not exactly `sha256_hex = <lowercase 64-hex>`. **Action:** ABORT. **Fix:** write exact content format. 
* **`E_FLAG_HASH_MISMATCH`** — recomputed SHA-256 over **all files listed in `index.json`** (excluding the flag) in **ASCII-lex order of `path`** ≠ `sha256_hex` in `_passed.flag`. **Action:** ABORT. **Fix:** rebuild bundle; ensure hashing order/bytes match. 

## 12.2 Access-control violations

* **`E_OUTLET_CATALOGUE_FORBIDDEN_BEFORE_PASS`** — any attempt to read `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/` **before** a passing gate. **Action:** ABORT. **Fix:** verify the flag first; then read. 
* **`E_FORBIDDEN_SURFACE_READ`** — attempted read of a **separately gated** convenience surface (e.g., **S6 membership**) without its own co-located PASS receipt for the same `{seed, parameter_hash}`. **Action:** ABORT. **Fix:** verify the surface’s own PASS receipt. 

## 12.3 Lineage & partition law

* **`E_PATH_EMBED_MISMATCH`** — after PASS, egress rows don’t **byte-equal** path tokens where both exist (e.g., `outlet_catalogue.manifest_fingerprint ≠ fingerprint` or `global_seed ≠ seed`). **Action:** ABORT. **Fix:** correct partitioning or embedded lineage. 
* **`E_PARTITION_MISPLACED`** — egress not under canonical path/partitions (`[seed,fingerprint]`) per the Dictionary/Schema. **Action:** ABORT. **Fix:** write/read only from the declared partition path. 

## 12.4 Receipt publish (S0 output)

* **`E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL`** — a receipt already exists under `fingerprint={manifest_fingerprint}` with **different bytes**. **Action:** ABORT publish (do not overwrite). **Fix:** ensure idempotent re-runs (byte-identical) or write nothing. 
* **`E_RECEIPT_SCHEMA_INVALID`** — `s0_gate_receipt_1B` fails its JSON-Schema (shape/domains/required fields). **Action:** ABORT publish. **Fix:** conform to schema (**JSON-Schema is the sole shape authority**). 

## 12.5 Reference / FK surfaces (presence & anchors sealed by S0)

* **`E_REFERENCE_SURFACE_MISSING`** — any required reference is absent (e.g., `iso3166_canonical_2024`, `world_countries`, `population_raster_2025`). **Action:** ABORT. **Fix:** populate the governed references at their Dictionary paths.
* **`E_SCHEMA_RESOLUTION_FAILED`** — schema anchor for a pinned reference cannot be resolved (e.g., ingress anchors for ISO/country/raster). **Action:** ABORT. **Fix:** fix schema set / anchors. 
* **`E_DICTIONARY_RESOLUTION_FAILED`** — Dataset Dictionary cannot resolve an ID → path/partitions/`$ref` (e.g., malformed Dictionary or missing entry). **Action:** ABORT. **Fix:** correct Dictionary entries. 

---

### Canonical actions & logging (applies to all codes)

* **Action on any `E_*`:** **FAIL CLOSED** — do not read egress; do not publish a receipt; emit an S0 audit line and exit non-zero. 
* **Remediation:** follow the cited contract—fix the bundle/flag/index rules (§§4, 7), lineage/partition equality (§§3, 9), Dictionary/Schema anchors, or reference presence, then re-run.   

> These codes align with the layer’s existing vocabulary (e.g., `E_PATH_EMBED_MISMATCH`) so downstream validation can aggregate failures consistently in `s9_summary.json` if S0’s outcomes are audited later.  

---

# 13) Observability & audit **(Binding)**

S0’s observability is **evidence-driven** and minimal: it proves the 1A gate and leaves a single fingerprint-scoped receipt. S0 **does not** produce RNG logs; those are upstream artefacts accounted for in 1A’s validation bundle (`rng_audit_log`, `rng_trace_log`, `rng_accounting.json`).  

---

## 13.1 Evidence S0 MUST produce (on PASS)

* **`s0_gate_receipt_1B` (fingerprint-scoped)** — written only on PASS; embeds `manifest_fingerprint` equal to the `fingerprint` path token and records the **exact validation folder** verified plus the **flag hash** and **sealed inputs** S0 authorises for 1B (e.g., `outlet_catalogue`, S3 order surface, and FK/geo references). *(Partition and equality law fixed elsewhere; path string is owned by the Dictionary.)*
  **MUST include at minimum:**
  `manifest_fingerprint`, `validation_bundle_path`, `flag_sha256_hex`, `verified_at_utc`, `sealed_inputs[]`.
  (Receipt is immutable; re-publishing the same identity must be **byte-identical**.)  

---

## 13.2 What S0 MUST verify & (therefore) record in the receipt

1. **Bundle location & identity.** Locate `…/validation/fingerprint={manifest_fingerprint}/` and assert the folder’s fingerprint matches the embedded values in bundle files (`*_resolved.json`). 
2. **Index hygiene.** `index.json` exists; every non-flag file is listed **exactly once** with a **relative**, ASCII-sortable `path`; `artifact_id` unique and ASCII-clean.  
3. **Gate hash rule.** Recompute `SHA256(concat(raw_bytes(files in ASCII-lex order of index.path)))` (excluding `_passed.flag`) and assert equality to `_passed.flag: sha256_hex = <hex64>`. Record `<hex64>` in the receipt.  
4. **Egress lineage parity (for any S0 read).** If S0 touches egress after PASS, assert `outlet_catalogue.manifest_fingerprint == fingerprint` and (if present) `global_seed == seed`.  

---

## 13.3 What S0 MUST NOT emit (to keep observability clean)

* **No RNG logs/layer1/1B/events** in S0 (S0 consumes no RNG). Coverage of RNG activity is already attested by 1A’s `rng_accounting.json` and core logs listed in the bundle index.  
* **No mutations** to 1A partitions (egress, parameter-scoped tables, RNG logs, or the validation bundle). Observability is read-only until the receipt is published. 

---

## 13.4 Optional observability (recommended but non-essential)

* **Egress stability awareness.** When present in the bundle, S0 **MAY** read `egress_checksums.json` (per-file & composite SHA-256 for `outlet_catalogue`) to include helpful notes in the receipt (e.g., composite hash). *(Notes are non-semantic; the gate still binds solely to `_passed.flag`.)*  
* **HashGate coupling (if the project enables it).** After PASS, S0 **MAY** mirror `{fingerprint, sha256_hex}` to a central HashGate record for CI/ops. **This never replaces the local flag verification** consumers must perform. 

---

## 13.5 Where observability lives (authoritative sinks)

* **Primary evidence:** the **validation bundle** under `…/validation/fingerprint={manifest_fingerprint}/` (required files + `_passed.flag`, all indexed) and S0’s **fingerprint-scoped receipt**.  
* **Upstream RNG signals (read-only context):** `rng_audit_log`, `rng_trace_log` exist under `{seed, parameter_hash, run_id}` and are reconciled by `rng_accounting.json` inside the bundle; S0 relies on their presence via the index rather than re-computing coverage.  

---

## 13.6 Failure-side audit (ABORT path)

On any **E_*** from §12, S0 **MUST NOT** write a receipt. Operators rely on the bundle’s absence of `_passed.flag` (or hash mismatch) and on standard failure codes captured by upstream validation (`s9_summary.json`) to diagnose. *(S9 writes bundles without the flag on FAIL; consumers must treat as not passed.)*  

---

**Binding effect:** Observability for S0 is **just enough**: prove the gate exactly as 1A defines it, publish a single, immutable receipt capturing what was verified and what inputs are now sealed, and **do nothing else**. All other signals remain with the 1A bundle (and optional CI coupling), keeping S0 simple, auditable, and idempotent.  

---

# 14) Security, licensing, and retention **(Binding)**

S0 is a **closed-world, contract-governed** gate. It verifies 1A’s PASS, then (optionally) writes a single receipt. It **must** enforce platform security rails, honor licence classes declared in governance, and obey retention/immutability rules. JSON-Schema + the Dataset Dictionary remain the single authorities for **shapes, paths, partitions, retention, and licence classes**. 

---

## 14.1 Security posture & access control

* **Closed-world operation.** S0 operates **only** on sealed, version-pinned artefacts; **no external enrichment or network reads**. Provenance (owner, retention, licence, `schema_ref`) comes from the Dictionary and **must** be respected. 
* **Least-privilege IAM & secrets.** Use least-privilege identities; **do not embed secrets** in datasets/logs; if credentials are required, use the platform secret store.  
* **Encryption at rest.** **SSE-KMS** (project-scoped key) is required; set a bucket-level **deny** on unencrypted PUTs; keep server-side checksums (or SHA-256 sidecars).   
* **Atomicity & immutability.** S0 **must** publish any receipt via **stage → fsync → atomic rename**, never exposing partial contents; partitions are **write-once** (immutable). 
* **Dictionary-only resolution.** All I/O resolves via the Dataset Dictionary; **no literal paths** in code or outputs. 
* **Headers / media types.** Use correct `Content-Type` (JSONL → `application/x-ndjson`; Parquet → `application/vnd.apache.parquet`) and helpful metadata such as `x-run-seed`, `x-parameter-hash`, `x-run-id`, `x-content-sha256`. *(S0’s receipt is JSON.)*  
* **Gate enforcement.** The **only** read gate for `outlet_catalogue` is the fingerprint-scoped `_passed.flag` whose value equals **SHA-256 over all files listed in `index.json` (ASCII-lex path order)**. **No PASS → no read.**   

---

## 14.2 Licensing & provenance (what S0 must honor and record)

* **Licence authority.** Licence class and retention live in the **Dictionary / Registry**; S0 **must not** override them. For each sealed input it authorises (e.g., `outlet_catalogue`, `s3_candidate_set`, references), the Dictionary must have a **non-empty licence** and retention. Absence is **run-fail** per governance.  
* **Ingress examples (for 1B references).** `world_countries` → **Public-Domain**; `population_raster_2025` → **Public-Domain**. These are already pinned in the artefact registry and must appear in sealed inputs. 
* **Licence map.** Governance exposes a `license_map` / `LICENSES/` set for traceability; S0’s sealed inputs must be **covered** there (presence check; no legal text interpretation).  
* **Redistribution.** Outputs/sealed surfaces remain **internal** under their licence class; S0’s receipt is **Proprietary-Internal** by default (final class set in the 1B Dictionary). 

---

## 14.3 Privacy & PII posture

* **PII stance.** Inputs/outputs in scope are **`pii:false`**; S0 **must not** introduce PII or re-identification fields. Receipts and logs **must** avoid row-level payloads—**codes & counts only**.  

---

## 14.4 Retention & immutability

* **Retention authority.** Retention windows are governed by the Dictionary; **do not** override. Typical defaults (for reference): `outlet_catalogue` **365 days**; RNG events 180–365 days. S0’s receipt retention is set in the 1B Dictionary.  
* **Write-once.** Partitions are content-addressed by lineage keys and **write-once**; re-publishing the same identity must be **byte-identical** or a no-op.  

---

## 14.5 Validity windows & version pinning (governance)

If governance declares **validity windows** for references/configs, S0 and downstream 1B states must treat out-of-window artefacts as **abort** (or **warn+abort** where specified). Artefacts without windows are **“digest-pinned only (binding)”**.  

---

## 14.6 Prohibitions (fail-closed)

S0 **MUST NOT**:

* read any 1A egress before the PASS check (§4); **no PASS → no read**; 
* modify any 1A partition or validation bundle; 
* encode or infer inter-country order anywhere (order authority remains S3 `candidate_rank`); 
* bypass Dictionary resolution with literal paths; 
* publish receipts non-atomically or without encryption at rest.  

---

**Binding effect:** This section locks S0 to the platform’s security rails (SSE-KMS, least-privilege, atomic publish, dictionary-only I/O), enforces licence/retention governance (including ODbL/CC-BY references), and keeps receipts **non-PII**, immutable, and fully auditable—so the 1B pipeline remains reproducible and compliant.     

---

# 15) Change control & compatibility window **(Binding)**

S0 follows **Semantic Versioning** (**MAJOR.MINOR.PATCH**). Across **v1.***, S0’s behaviour is **stable**: the consumer gate, lineage law, and authorities **must not change**. A **MAJOR** increment is required when any binding interface or gate semantics changes (see below). This mirrors the 1A/S8–S9 precedent.  

---

## 15.1 What changes require **MAJOR** (breaking)

S0 **MUST** bump **MAJOR** and be re-ratified if any of the following change:

* **Gate semantics or location:** format or hashing rule of `_passed.flag`, the **folder/partition** for the validation bundle, or the binding rule **“no PASS → no read.”**  
* **Lineage/partition law:** path↔embed **byte-equality** rules; partition keys for S0’s output (the `s0_gate_receipt_1B` fingerprint partition) or for egress it authorises.  
* **Authority surfaces or IDs:** dataset **IDs**, `$ref` anchors, or canonical path templates in the Dictionary that S0 relies on (e.g., `outlet_catalogue`, `s3_candidate_set`, validation bundle).  
* **Layer schema invariants:** RNG envelope fields or core shapes in `schemas.layer1.yaml` used by gate/lineage checks. 
* **Precedence model:** JSON-Schema as sole shape authority; Dictionary as IDs/paths/partitions/writer policy; Registry for gate artefacts. 

> Rationale: these are the same classes S8/S9 treat as breaking (egress contract, partitions, consumer gate).  

---

## 15.2 What qualifies as **MINOR** (backward-compatible)

* Adding **nullable/optional** fields to `s0_gate_receipt_1B` that do **not** alter PK/UK/partitions or obligations. 
* Allowing additional **sealed inputs** (e.g., a new FK surface) **without** making them mandatory for S1 and **without** changing gate semantics.
* Adding **informative** metrics/notes to the receipt (non-semantic). 

---

## 15.3 What is **PATCH** (non-behavioural)

* Editorial clarifications or examples that **do not change** schemas, paths, partitions, lineage rules, or the gate. 

---

## 15.4 Compatibility window (baselines S0 assumes)

S0 v1.* assumes these authorities stay on their **v1.*** lines; a **MAJOR** in any **requires** S0 re-ratification and a **MAJOR** bump here:

* `schemas.layer1.yaml` (layer-wide RNG/log/core). 
* `schemas.1A.yaml` (1A tables/egress/validation). 
* `schemas.ingress.layer1.yaml` (Ingress/FK).
* `dataset_dictionary.layer1.1A.yaml` (IDs, paths, partitions, writer sorts, consumer gate text).
* `schemas.1B.yaml` (1B shapes, including `#/validation/s0_gate_receipt`).
* `dataset_dictionary.layer1.1B.yaml` (1B IDs/paths/retention, including the S0 receipt path).

> Effect: if 1A moves its egress or changes its bundle/gate under a new **MAJOR**, S0 cannot lawfully proceed until re-ratified for that line. 

---

## 15.5 Forward/backward behaviour guarantees (v1.*)

Within **v1.***:

* The **consumer gate** remains: locate `validation/fingerprint={manifest_fingerprint}/`, recompute ASCII-lex **index.json** hash over all listed files (flag excluded), and match `_passed.flag`. **No PASS → no read.**  
* Egress authorisation remains restricted to `outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`, which is **order-free**; inter-country order **must** be joined from `s3_candidate_set.candidate_rank`. 
* **Path↔embed equality** stays binding everywhere it appears (e.g., `manifest_fingerprint` vs `fingerprint` path token; `global_seed` vs `seed`). 

---

## 15.6 Migration & deprecation rules

* If a future **MAJOR** is ratified, S0 **MUST**: (a) freeze the old v1.* spec; (b) publish S0 v2.0.0 with explicit diffs; (c) require 1A/S8–S9 and the Dictionary entries it relies on to be on their matching **MAJOR** before running. (Consumers cannot “bridge” across gate formats.) 
* Dictionary **aliases** or path rewrites are **not** a substitute for re-ratifying S0 when IDs/partitions change (schema/dictionary are the authorities).  

---

## 15.7 Ratification & recording

On release, record in governance: `semver`, `effective_date`, `ratified_by`, git commit (and optional SHA-256 of this file). This mirrors S8/S9 practice. 

---

**Binding effect:** This section locks S0’s **gate, lineage, and authorities** across **v1.***; any gate/location/partition/authority change is **MAJOR**. As long as the 1A Dictionary+Schemas and the layer schema remain on **v1.***, S0 can run unchanged and deterministically authorise reads of `outlet_catalogue` for a given fingerprint.   

---

# Appendix A) Glossary & notational conventions **(Informative)**

## A.1 Core lineage tokens

* **`manifest_fingerprint`** (aka **`fingerprint`** in paths) — 64-hex run digest that partitions 1A egress and the validation bundle. Any path segment `fingerprint={…}` **carries this value**; where embedded in rows it **must byte-equal** the path token.  
* **`parameter_hash`** — 64-hex SHA-256 of the parameter bundle. Partitions **parameter-scoped** datasets/logs; embedded values **must equal** the path token.  
* **`seed`** — uint64 master PRNG seed used in RNG log/event partitions (and embedded where present). 
* **`run_id`** — 32-hex identifier for RNG log/event partitions (and embedded where present). 

## A.2 Gate & bundle terms

* **Validation bundle (1A)** — fingerprint-scoped folder with required artefacts (`MANIFEST.json`, `rng_accounting.json`, `s9_summary.json`, `egress_checksums.json`, `index.json`, etc.). **Every non-flag file is indexed once** in `index.json` with **relative** ASCII-sortable paths.  
* **Consumer gate `_passed.flag`** — one-line file: `sha256_hex = <hex64>` where the hex equals **SHA-256 over the raw bytes of all files listed in `index.json` (flag excluded)** in **ASCII-lexicographic** order of `path`. **No PASS → no read.**  
* **ASCII-lex order** — the sort key for hashing is the literal `path` string from `index.json` (ASCII, relative; no `..` or leading `/`). 

## A.3 Authority surfaces & datasets (1A → 1B)

* **`outlet_catalogue` (egress)** — immutable stubs under `[seed,fingerprint]`; **does not encode cross-country order**; consumers **must** verify the bundle flag first. Writer sort: `[merchant_id, legal_country_iso, site_order]`.  
* **`s3_candidate_set` (order authority)** — parameter-scoped; defines **`candidate_rank`** as a total, contiguous order per merchant with **home = 0**. The **sole** source of inter-country order.  

## A.4 RNG terminology (layer-wide)

* **RNG envelope (per event row)** — common fields: `ts_utc, run_id, seed, parameter_hash, manifest_fingerprint, module, substream_label, rng_counter_before_{hi,lo}, rng_counter_after_{hi,lo}, draws, blocks`. `draws` = **decimal u128 string of actual U(0,1) draws**; `blocks` = `u128(after) − u128(before)` (unsigned) and fits `uint64`.  
* **Core RNG logs** — `rng_audit_log` (one row at run start) and `rng_trace_log` (**append exactly one cumulative row after each event**; reconcile `events_total/draws_total/blocks_total`). Both partitioned by `[seed, parameter_hash, run_id]`.  
* **Event families & budgets** — e.g., `gumbel_key` is **single-uniform** (`blocks=1`, `draws="1"`); **non-consuming** markers use `blocks=0`, `draws="0"`. 
* **Open-interval uniforms** — schema enforces **(0,1)** (never 0 or 1). 

## A.5 Partition notation & path templates

* Bracket notation denotes partition keys:

  * **Egress:** `[seed, fingerprint]` → `…/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/` 
  * **Parameter-scoped:** `[parameter_hash]` → `…/s3_candidate_set/parameter_hash={parameter_hash}/` 
  * **RNG logs/layer1/1B/events:** `[seed, parameter_hash, run_id]` → `…/logs/layer1/1B/rng/.../seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` 
* **Path↔embed equality** — when lineage exists in both places, values **must be byte-equal** (e.g., `row.manifest_fingerprint == fingerprint` path token). 

## A.6 Naming & formats

* **`hex64`** — `^[a-f0-9]{64}$` (SHA-256 digests like `manifest_fingerprint`, `parameter_hash`). **`hex32`** — `^[a-f0-9]{32}$` (`run_id`). 
* **`u01`** — open-interval uniform `(0,1)`; **`pct01`** — closed interval `[0,1]`. 
* **`six_digit_seq`** — `^[0-9]{6}$` (used by S8 sequencing). 

## A.7 Conventions used in this spec

* **Arrow / implication** — `→` shows flow; `⇒` indicates a logical consequence (e.g., “PASS ⇒ read allowed”). *(Notation only.)*
* **Set / sum** — `∈` (membership), `Σ` (sum); **`dp`** denotes decimal places for fixed-dp strings (e.g., base-weight priors). 
* **“No PASS → no read”** — exact wording for the consumer gate on `outlet_catalogue`; the Dictionary repeats it under that dataset’s contract. 
* **File order** — always **non-authoritative**; egress readers rely on PK/sort; RNG replay relies on **envelope counters** and trace, not physical order.  

## A.8 Minimal examples

* **Gate verification (sketch)** — Locate `…/validation/fingerprint={manifest_fingerprint}/`; recompute SHA-256 over **all files in `index.json`** in ASCII-lex path order; compare to `_passed.flag`. On match, reads of `…/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/` are authorised.  
* **Egress lineage check** — When reading `outlet_catalogue`, assert `row.manifest_fingerprint == fingerprint` and (if present) `global_seed == seed`. 

## A.9 Scope reminders (for 1B)

* **Order authority stays in S3** — 1B must **join** `s3_candidate_set.candidate_rank` when it needs inter-country order; 1B egress **must not** encode it.  
* **RNG in S0** — S0 **consumes no RNG**; it pins the environment (envelope, open-interval, core logs) for later states. 

---

# Appendix B) Examples & templates **(Informative)**

The snippets below illustrate S0’s gate workflow and the minimal artefacts it touches/produces. Shapes/paths/partitions are governed by the 1A Dictionary & Schemas and the 1A validation bundle contract.  

---

## B.1 Minimal consumer recipe (PASS → read)

1. **Locate** `…/validation/fingerprint={manifest_fingerprint}/`.
2. **Read** `index.json`; ensure every non-flag file appears **exactly once**, `path` is **relative** and ASCII-sortable, `artifact_id` unique. 
3. **Compute** `SHA256(concat(raw_bytes(files in ASCII-lex order of index.path)))` (exclude `_passed.flag`). 
4. **Compare** to `_passed.flag` (`sha256_hex = <hex64>`). If equal → **PASS**; else **ABORT**. 
5. **Only on PASS**, **read** `…/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`. **No PASS → no read.** 

---

## B.2 Validation bundle tree (PASS case)

```
validation/
└─ fingerprint={manifest_fingerprint}/
   ├─ MANIFEST.json
   ├─ parameter_hash_resolved.json
   ├─ manifest_fingerprint_resolved.json
   ├─ rng_accounting.json
   ├─ s9_summary.json
   ├─ egress_checksums.json
   ├─ index.json
   └─ _passed.flag        # "sha256_hex = <hex64>"
```

All **non-flag** files must be listed in `index.json` (relative paths). The flag equals the **SHA-256** over the bytes of all files listed by `index.json` in **ASCII-lex** path order (flag excluded).  

---

## B.3 `index.json` (shape-only example)

```json
[
  {"artifact_id":"manifest","kind":"text","path":"MANIFEST.json"},
  {"artifact_id":"rng_accounting","kind":"table","path":"rng_accounting.json"},
  {"artifact_id":"summary","kind":"summary","path":"s9_summary.json"},
  {"artifact_id":"egress_hashes","kind":"table","path":"egress_checksums.json"},
  {"artifact_id":"catalog","kind":"table","path":"index.json"}
]
```

(Fields and constraints per the 1A bundle index schema.) 

---

## B.4 Worked ASCII-lex order

Given these `index.path` entries:

```
egress_checksums.json
MANIFEST.json
manifest_fingerprint_resolved.json
parameter_hash_resolved.json
rng_accounting.json
s9_summary.json
index.json
```

The ASCII-lex order used for hashing is:

```
MANIFEST.json
egress_checksums.json
index.json
manifest_fingerprint_resolved.json
parameter_hash_resolved.json
rng_accounting.json
s9_summary.json
```

Compute SHA-256 over that concatenation → write `_passed.flag` as `sha256_hex = <hex64>`. 

---

## B.5 Egress path & lineage parity (example)

**Authorised path (on PASS):**
`data/layer1/1A/outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` (partitions **[seed, fingerprint]**; writer sort `[merchant_id, legal_country_iso, site_order]`; **order-free**). 

**Row snippet (fields abridged):**

```json
{
  "merchant_id": 1234567890123456,
  "legal_country_iso": "DE",
  "site_order": 2,
  "manifest_fingerprint": "<hex64>",
  "global_seed": 18446744073709551615
}
```

S0’s read must assert:
`row.manifest_fingerprint == fingerprint` **and** (if present) `row.global_seed == seed`.  

---

## B.6 S3 order join (what 1B will use later)

**Order authority surface:**
`data/layer1/1A/s3_candidate_set/parameter_hash={parameter_hash}/` (partitions **[parameter_hash]**).
Rows ordered by `(merchant_id, candidate_rank, country_iso)`; **home has `candidate_rank = 0`**. Egress never encodes cross-country order; consumers **join S3**.  

---

## B.7 S0 receipt template (`s0_gate_receipt_1B`) — JSON (proposed)

```json
{
  "manifest_fingerprint": "<hex64>",   // MUST equal the fingerprint path token
  "validation_bundle_path": "data/layer1/1A/validation/manifest_fingerprint=<hex64>/",
  "flag_sha256_hex": "<hex64>",
  "verified_at_utc": "2025-10-16T05:12:34.123456Z",
  "sealed_inputs": [
    {"id":"outlet_catalogue","partition":["seed","fingerprint"],
     "schema_ref":"schemas.1A.yaml#/egress/outlet_catalogue"},
    {"id":"s3_candidate_set","partition":["parameter_hash"],
     "schema_ref":"schemas.1A.yaml#/s3/candidate_set"},
    {"id":"iso3166_canonical_2024","schema_ref":"schemas.ingress.layer1.yaml#/iso3166_canonical_2024"},
    {"id":"world_countries","schema_ref":"schemas.ingress.layer1.yaml#/world_countries"},
    {"id":"population_raster_2025","schema_ref":"schemas.ingress.layer1.yaml#/population_raster_2025"},
    {"id":"tz_world_2025a","schema_ref":"schemas.ingress.layer1.yaml#/tz_world_2025a"}
  ],
  "notes": ""
}
```

(Partition for this receipt is **[fingerprint]**; path string to be set by the 1B Dictionary. Path↔embed equality for `manifest_fingerprint` is binding.) 

---

## B.8 Optional bundle extras (if present, they’re hashed)

If the bundle contains `param_digest_log.jsonl`, `fingerprint_artifacts.jsonl`, `numeric_policy_attest.json`, `DICTIONARY_LINT.txt`, `SCHEMA_LINT.txt`, they **must** appear in `index.json` and are included in the flag hash.  

---

## B.9 PASS vs ABORT checklist

* `_passed.flag` **present** and equals `SHA256(validation_bundle_1A)` in ASCII-lex order of `index.path` → **PASS**. Then (and only then) read `outlet_catalogue`.  
* Flag **missing/mismatch** or `index.json` **invalid** (non-relative paths, duplicates, non-ASCII sort) → **ABORT**; do **not** read egress; write **no** receipt. 

---

## B.10 Dictionary stubs you’ll likely add for 1B (IDs only)

```yaml
# dataset_dictionary.layer1.1B.yaml  (illustrative)
- id: s0_gate_receipt_1B
  version: '{manifest_fingerprint}'
  format: json
  path: data/layer1/1B/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/s0_gate_receipt.json
  partitioning: [fingerprint]
  ordering: []
  schema_ref: schemas.1B.yaml#/validation/s0_gate_receipt
  lineage:
    produced_by: 1B.S0
    consumed_by: [1B]
    final_in_layer: false
  retention_days: 365
  pii: false
  licence: Proprietary-Internal
```

(The Dictionary owns the exact path string; partition/equality law mirrors 1A’s fingerprint surfaces.) 

---

## B.11 Notes on identity & sets (quick reminders)

* Any path segment `fingerprint={…}` carries `manifest_fingerprint`.
* File order is **non-authoritative**; identity is **partition keys + PK/UK** (egress sort enforced; JSONL streams are **sets**).  

These examples give you ready-to-lift shapes and checklists while staying inside your 1A contracts.

---
