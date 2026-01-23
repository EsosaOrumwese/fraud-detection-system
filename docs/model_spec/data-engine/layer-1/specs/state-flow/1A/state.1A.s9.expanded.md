# S9 SPEC — Replay Validation & Publish Gate (Layer 1 · Segment 1A)

# 0) Document metadata & status **(Binding)**

## 0.1 State ID, SemVer, effective date

* **State ID (canonical):** `layer1.1A.S9` — “Replay Validation & Publish Gate”.
* **SemVer:** **MAJOR.MINOR.PATCH**.
  **MAJOR** when any binding interface changes, including (non-exhaustive):
  – `_passed.flag` format or hashing rule; the location/partitioning of the validation bundle; consumer-gate semantics (**no PASS → no read**); dataset IDs or `$ref` anchors for S9 inputs/outputs; lineage equality rules; RNG envelope/accounting laws used by the validator.  
  **MINOR** for backward-compatible additions (new optional bundle files/metrics, extra validator summaries) that do **not** alter existing contracts.
  **PATCH** for clarifications that do **not** change behaviour, schemas, or gates.
* **Effective date:** `YYYY-MM-DD` (set at ratification).

## 0.2 Normative language

This spec uses **RFC 2119/8174** key words (**MUST/SHALL/SHOULD/MAY**) with their normative meanings. Unless explicitly labelled **Informative**, every clause in S9 is **Binding**. (S7/S8 use the same convention for cross-state consistency.)  

## 0.3 Document status & section classes

* The default for all sections is **Binding**.
* **Informative** material (worked micro-examples, bundle layout illustrations) is confined to appendices and **MUST NOT** be used by implementers to weaken Binding rules.

## 0.4 Compatibility window (authorities & lines)

S9 v1.* assumes the following remain on their **v1.* line**; a **MAJOR** bump in any requires S9 re-ratification and a SemVer **MAJOR** increment here:

* `schemas.layer1.yaml` (layer-wide RNG/log/core schemas),
* `schemas.1A.yaml` (1A tables/egress/validation),
* `schemas.ingress.layer1.yaml` (ingress/reference),
* `dataset_dictionary.layer1.1A.yaml` (IDs, path templates, partitions, writer sorts).  

## 0.5 Numeric environment (inherited; MUST hold)

S9 **inherits S0.8 verbatim** and **MUST** attest the numeric regime before running validations: IEEE-754 **binary64**, **RNE** (round-to-nearest, ties-to-even), **FMA off**, **no FTZ/DAZ**, subnormals honoured; deterministic libm profile pinned by `math_profile_manifest.json`. These artefacts are enumerated in the S0 manifest; changing either flips the **`manifest_fingerprint`**.  

## 0.6 Run sealing & lineage (identifiers, partitions, equality)

* **Lineage keys:** `{seed, parameter_hash, run_id}` on RNG logs and validator reads; `{manifest_fingerprint}` for the validation bundle/flag partition. **Path tokens MUST equal embedded columns byte-for-byte** wherever both exist. 
* **Validation bundle location:** `data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/` (manifest_fingerprint partition). `_passed.flag` lives **inside** this folder. 
* **Gate semantics (consumer binding):** `_passed.flag` contains `sha256_hex = <hex64>`, where `<hex64>` is the SHA-256 over **all files listed in `index.json` (excluding `_passed.flag`)** in **ASCII-lexicographic order of the `index.json` `path` entries**; consumers **MUST** verify this for the same fingerprint **before** reading egress (**no PASS → no read**).

## 0.7 Change control & ratification

* **Source of truth:** JSON-Schema (layer/segment/ingress) and the Dataset Dictionary remain the sole schema and path authorities; this S9 spec binds validator behaviour **under** those authorities. Any PR that changes Binding parts of S9 **MUST**:
  (a) bump SemVer per §0.1; (b) update anchors in the Dictionary/Registry where applicable; (c) attach the updated bundle schema entry; (d) re-ratify the consumer gate in CI.  

### Contract Card (S9) - inputs/outputs/authorities

**Inputs (authoritative; see Section 1+ for full list):**
* `outlet_catalogue` - scope: EGRESS_SCOPED; sealed_inputs: required
* `rng_audit_log`, `rng_trace_log`, and required RNG event families - scope: LOG_SCOPED; sealed_inputs: required
* Validation evidence inputs from S0-S8 (schemas and dictionary refs are authoritative).

**Authority / ordering:**
* Validation bundle index + hash gate is the sole consumer gate for 1A.

**Outputs:**
* `validation_bundle_1A` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `validation_bundle_index_1A` - scope: FINGERPRINT_SCOPED; gate emitted: none
* `validation_passed_flag_1A` - scope: FINGERPRINT_SCOPED; gate emitted: final consumer gate

**Sealing / identity:**
* Validation bundle partitioned by `manifest_fingerprint`; `_passed.flag` hashes the bundle index.

**Failure posture:**
* Any validation failure -> do not publish `_passed.flag`; bundle records failure evidence.

---

# 1) Purpose, scope, non-goals **(Binding)**

## 1.1 Purpose

S9’s role is to **re-derive and verify** the promises made by **S0–S8**, then **publish a fingerprint-scoped validation bundle** and a **single consumer gate flag**. If and only if all checks pass, S9 writes `validation_bundle_1A/` under
`data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/` and a colocated `_passed.flag` whose **content hash equals `SHA256(validation_bundle_1A)`**. **Consumers MUST verify this flag for the same fingerprint before reading `outlet_catalogue`** (**no PASS → no read**).   

## 1.2 Scope — what S9 MUST do

S9 is **read-only** over the produced data/streams and **MUST**:

**a) Structural & schema validation.**
Assert schema validity, partition law, PK/UK, and FK targets for all inputs in scope, including `outlet_catalogue` (egress; `[seed, manifest_fingerprint]` partitions), `s3_candidate_set` (sole inter-country order; `[parameter_hash]`), optional `s3_integerised_counts`, and the RNG families/core logs used across S1–S8 (`rng_event.*`, `rng_trace_log`, `rng_audit_log`).   

**b) Lineage equality & identity.**
Enforce **path↔embed equality** for lineage tokens wherever both exist: e.g., `outlet_catalogue.manifest_fingerprint equals the `manifest_fingerprint` path token` path token; RNG events embed `{seed, parameter_hash, run_id}` equal to their path tokens. For parameter-scoped tables, embedded `parameter_hash` **MUST** equal the partition key. 

**c) RNG envelope accounting & trace coverage.**
Reconcile **every** RNG family touched in S1/S2/S4/S6/S7/S8:
`u128(after)−u128(before) == blocks` (per event), **non-consuming** families carry `draws="0", blocks=0`, and **exactly one** `rng_trace_log` row is appended **after each event**; final trace totals match the sum of event budgets. **Uniforms are strict-open** `u∈(0,1)` as fixed in S0.    

**d) Cross-state replay checks (facts re-derived from written inputs only).**

* **S1 hurdle:** exactly one decision per merchant; extremes consume zero; open-interval `u` and budget identity hold; trace totals reconcile. 
* **S2 NB:** one `nb_final` (non-consuming); Gamma/Poisson component coverage and budgets reconcile; accepted `N≥2`. 
* **S3 order:** `candidate_rank` is **total, contiguous**, with **home=0**; S9 **never** invents order. 
* **S4 ZTP:** `ztp_final` unique; rejection attempts coherent with Poisson components. 
* **S6 membership:** if `s6_membership` was used, it **MUST** match re-derivation from `gumbel_key` (+S3/S4 facts); **S6 PASS is required** to read the convenience surface. 
* **S7 integerisation:** reconstruct floors + **`dp_resid=8` residual_rank** order and prove `Σ_i count_i = N`; no cross-country order created by S7. 
* **S8 egress & sequences:** per (merchant,country) block, `site_order = 1..n_i` with `site_id` `^[0-9]{6}$`; exactly one `sequence_finalize` (non-consuming) per block; overflow guard respected; **egress encodes no inter-country order** (join S3).  

**e) Gates & consumer publish.**
If S8 (or earlier states) read convenience surfaces, S9 **verifies** the corresponding **PASS receipts** (e.g., S6). On success, S9 publishes `validation_bundle_1A/` and `_passed.flag` **atomically**; on failure, S9 publishes the bundle **without** `_passed.flag`.  

## 1.3 Non-goals (what S9 MUST NOT do)

* **No new RNG draws, no reseeding, no counter advances.** S9 **MUST NOT** emit RNG events or consume counters. (It only reads/validates envelopes and traces.) 
* **No egress authoring or mutation.** S9 does **not** write or alter `outlet_catalogue` or any S3/S6/S7 surfaces; it only validates them. 
* **No new order or counts.** S9 does **not** define inter-country order (S3 is sole authority) or recompute authoritative counts; it only **re-derives to compare**. 
* **No weight computation or persistence.** S9 does **not** read or rewrite S5 weight surfaces unless a separate 4B harness is active (outside 1A’s S9 gate); the 1A S9 gate does **not** depend on S5. 
* **No heuristic “repairs.”** Any breach is a **fail-closed**; S9 does not auto-correct producer outputs. 

## 1.4 Decision & gate semantics (run outcome)

* **PASS:** all checks in scope succeed → write `validation_bundle_1A/` and `_passed.flag` (content hash equals bundle SHA-256), enabling downstream reads for this **fingerprint**. 
* **FAIL:** any binding check fails → write bundle (with failures) **without** `_passed.flag`; **consumers MUST NOT read `outlet_catalogue` for this fingerprint**. 

---

# 2) Sources of authority & precedence **(Binding)**

## 2.1 Schema authority (single source of shape truth)

S9 **MUST** treat JSON-Schema as the **sole authority** for shapes, required fields, domains, and envelope semantics. The following schema sets are **binding**:

* **Layer-wide logs & RNG events:** `schemas.layer1.yaml` — e.g., core logs `rng_audit_log`, `rng_trace_log`; event families used by 1A such as `hurdle_bernoulli`, `gamma_component`, `poisson_component`, `ztp_*`, `gumbel_key`, `residual_rank`, `sequence_finalize`, `site_sequence_overflow`; and governance objects (`numeric_policy_profile`, `math_profile_manifest`).   
* **Segment 1A tables/bundles:** `schemas.1A.yaml` — e.g., `s3/candidate_set`, `s3/integerised_counts`, optional `s3/site_sequence`, egress `egress/outlet_catalogue`, and the fingerprint-scoped `validation/validation_bundle`. 
* **Ingress & FK targets:** `schemas.ingress.layer1.yaml` (e.g., `iso3166_canonical_2024`), referenced by 1A tables and S8 egress. 

**Anchor-resolution rule (normative).** Bare anchors resolve as follows:
-  `#/rng/**` → `schemas.layer1.yaml`
- `#/validation/validation_bundle` → `schemas.1A.yaml`
- `#/validation/s6_receipt` → `schemas.layer1.yaml` 
- `#/s3/**` and `#/egress/**` → `schemas.1A.yaml`

## 2.2 Dataset Dictionary (IDs, paths, partitions, writer policy)

The **Dataset Dictionary** is authoritative for **dataset IDs, canonical paths, partitions, writer sort, and consumer gates**; S9 **MUST** obey it exactly when locating inputs and publishing outputs. Examples:

* **Egress** `outlet_catalogue`: `[seed, manifest_fingerprint]` partitions; writer sort `[merchant_id, legal_country_iso, site_order]`; **no cross-country order encoded**; consumers **MUST** verify the fingerprint-scoped gate before reads. 
* **Order authority** `s3_candidate_set`: `[parameter_hash]` partition; `candidate_rank` is the **sole** inter-country order surface. 
* **Core logs** `rng_audit_log`, `rng_trace_log`: `[seed,parameter_hash,run_id]` partitions; trace rows are **cumulative** and **one row is appended after each RNG event append**. 

## 2.3 Artefact Registry (runtime bindings & gates)

The **Artefact Registry** pins gate artefacts and their semantics used by S9:

* **Validation bundle (fingerprint-scoped)** `validation_bundle_1A` under `data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/`. 
* **Consumer flag** `_passed.flag` whose **content** is `sha256_hex = <SHA256(bundle)>`; **consumers must verify** this for the same fingerprint **before** reading `outlet_catalogue` (**no PASS → no read**). 

## 2.4 Authority surfaces (what decides *what*)

S9 **MUST** enforce the following lines of authority; if any dependent surface disagrees, S9 **fails**:

1. **Inter-country order:** **S3 `candidate_rank` is single authority** (home rank = 0; ranks total & contiguous). Neither S7 nor S8 encodes or overrides cross-country order; S9 must never invent it.  
2. **Per-country integer counts:** Either **`s3_integerised_counts`** (if emitted) or counts reconstructed deterministically from **S7 `residual_rank`** over the S3 domain (S9 selects the configured path, but **does not** re-decide policy).  
3. **Egress content:** `outlet_catalogue` is **order-free across countries**, fingerprint-scoped, and must pass dictionary/schema checks; downstream join-back to S3 provides order. 
4. **RNG envelope & trace law:** Event rows **must** satisfy the layer envelope (`before/after/blocks/draws`) and trace obligations; **non-consuming** families (e.g., `sequence_finalize`, `site_sequence_overflow`, `residual_rank`) have `blocks=0`, `draws="0"`, and still cause a **single** trace append.  
5. **Numeric environment:** S0 binds **IEEE-754 binary64, RNE, FMA-off, no FTZ/DAZ**, and a pinned libm profile. S9 **inherits** this and validates under the same profile. 

## 2.5 Gating & read-before-use (MUST verify receipts)

* **Fingerprint gate (1A → consumers):** The `_passed.flag` under `validation/manifest_fingerprint={manifest_fingerprint}/` **MUST** verify (content hash equals bundle SHA-256) **before** `outlet_catalogue` can be read. S9 publishes this flag only on PASS.  
* **Upstream convenience gates:** If S9 reads any convenience surface that is gated upstream (e.g., `s6/membership`), it **MUST** verify the corresponding **S6 PASS receipt** first. 

## 2.6 Precedence on conflict (descending)

When documents disagree, S9 **MUST** apply this precedence ladder:

1. **JSON-Schema** (layer + segment + ingress) → shapes/domains/envelopes;
2. **Dataset Dictionary** → dataset IDs, canonical paths/partitions, writer order, consumer gate;
3. **Artefact Registry** → concrete publish locations and gate coupling;
4. **State specs S0–S8 (Binding)** → semantics, invariants, and authority separation that schemas/dictionary alone don’t express;
5. **Non-binding notes** (concept docs/previews) → informative only.
   Examples: (i) If a file’s columns validate but its partition keys or writer sort don’t match the dictionary, **dictionary wins**; (ii) if an event row exists but violates the envelope schema (e.g., non-consuming family with `draws≠"0"`), **schema wins**.   

## 2.7 Path↔embed equality & identity (applies to all S9 reads/writes)

Where lineage appears **both** in the path and in embedded columns/fields, **byte-equality is binding** (e.g., `outlet_catalogue.manifest_fingerprint equals the `manifest_fingerprint` path token` (path), and for logs/layer1/1A/events `{seed,parameter_hash,run_id}` equal their path tokens). **File order is non-authoritative.** 

---

*Status: this section is **Binding** and governs how S9 recognises truth and decides ties before executing any validation checks.*

---

# 3) Inputs — inventory & read-gates **(Binding)**

## 3.0 Overview (read-only stance)

S9 is **read-only**. It enumerates **exactly** which datasets/logs/layer1/1A/events it may read, with their **IDs → schema anchors → partitions**, and the **gates** that **MUST** be verified **before** use. Path↔embed lineage equality is **binding** for every read in scope.  

---

## 3.1 Fingerprint-scoped egress to validate

**Dataset ID:** `outlet_catalogue` → **`schemas.1A.yaml#/egress/outlet_catalogue`**.
**Partitions:** `[seed, manifest_fingerprint]` at `data/layer1/1A/outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`.
**Binding rules:** rows **MUST NOT** encode inter-country order; consumers later **MUST** join `s3_candidate_set.candidate_rank`. `manifest_fingerprint` (column) **MUST** byte-equal the `manifest_fingerprint` path token; `global_seed` **MUST** equal the `seed` token.  

---

## 3.2 Parameter-scoped authorities (order, counts, optional sequence)

**Required (order authority).**
`s3_candidate_set` → **`schemas.1A.yaml#/s3/candidate_set`**; **partitions:** `[parameter_hash]`. **S3 is the single authority for inter-country order:** `candidate_rank` is **total & contiguous**, with **home=0**.  

**Counts surface (choose ONE path for S9’s replay):**
**Path A (if present):** `s3_integerised_counts` → **`schemas.1A.yaml#/s3/integerised_counts`**; `[parameter_hash]`. Authoritative per-country integers `count` with `residual_rank`. 
**Path B (default):** re-derive counts deterministically from **S7 evidence** (`rng_event.residual_rank`) over the S3 domain and prove `Σ_i count_i = N`. (See §7/§8 in this spec for the replay law.) 

**Optional cross-check (if produced upstream):**
`s3_site_sequence` → **`schemas.1A.yaml#/s3/site_sequence`**; `[parameter_hash]`. S9 **must not** require it; if present, only parity-check with S8 sequencing. 

---

## 3.3 RNG core logs (run-scoped) — required for accounting

* `rng_audit_log` → **`schemas.layer1.yaml#/rng/core/rng_audit_log`**; path `logs/layer1/1A/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl`; **partitions:** `{seed, parameter_hash, run_id}`. 
* `rng_trace_log` → **`schemas.layer1.yaml#/rng/core/rng_trace_log`**; path `logs/layer1/1A/rng/trace/…`; **emit exactly one cumulative row after each RNG event append** (S9 selects the **final** row per `(module,substream_label,run_id)`). 

**Run binding.** S9 **MUST** take the set of `{run_id}` values observed in the **event streams it validates** (below) and read the matching `rng_trace_log`/`rng_audit_log` partitions for those `(seed, parameter_hash, run_id)` tuples. (Trace is run-scoped; events embed lineage and, per S1/S0, include `manifest_fingerprint` for run-to-egress binding.)  

---

## 3.4 RNG event families in scope (S1–S8)

All event streams are **JSONL**, partitioned by `{seed, parameter_hash, run_id}`, and must carry the **layer envelope** (pre/post 128-bit counters; `blocks`; decimal-u128 `draws`). **Non-consuming families** have `blocks=0`, `draws="0"`. **One** `rng_trace_log` row is appended **after each event append**.  

**S1 (hurdle):** `rng_event.hurdle_bernoulli` → `#/rng/events/hurdle_bernoulli`. Extremes consume **zero**; stochastic branch consumes **one**; envelope + trace discipline apply.  

**S2 (NB mixture):** `rng_event.gamma_component`, `rng_event.poisson_component`, and **non-consuming** `rng_event.nb_final` (finaliser). 

**S4 (ZTP target):** `rng_event.ztp_final` (non-consuming) + Poisson attempt components under the ZTP label. 

**S6 (selection keys):** `rng_event.gumbel_key` (single-uniform: `blocks=1`, `draws="1"`); optional `stream_jump` if registered; logs/layer1/1A/trace updated. 

**S7 (integerisation evidence):** `rng_event.residual_rank` — **non-consuming**, residuals quantised to **dp=8**, rank ≥1, one per `(merchant,country)` in domain.  

**S8 (egress instrumentation):** `rng_event.sequence_finalize` (**non-consuming**; one per `(merchant,country)` with `{start_sequence="000001", end_sequence=zfill6(n)}`) and guardrail `rng_event.site_sequence_overflow` (**non-consuming**, `severity="ERROR"`).  

---

## 3.5 Membership surfaces (choose ONE; gate applies)

**Path M1 (preferred when present):** `s6_membership` → **`schemas.1A.yaml#/alloc/membership`**; `[seed, parameter_hash]`. **Gate:** `s6_validation_receipt` (co-located) MUST be valid **PASS** before reading (`S6_VALIDATION.json` + `_passed.flag`). 
**Path M2 (default):** re-derive membership from `rng_event.gumbel_key` (+S3 domain and S4 `K_target`), supporting reduced logging by counter-replay where defined. (No S6 PASS required for events.) 

---

## 3.6 Foreign-count sources (choose ONE; no weights read)

**Path C1 (if present):** `s3_integerised_counts` (authoritative counts). 
**Path C2 (default):** reconstruct from S7 `residual_rank` evidence over the S3 domain; prove `Σ_i count_i = N` from S2 `nb_final`. **S9 does not read S5 weights.** 

---

## 3.7 Reference/FK targets (for schema/FK checks)

* `iso3166_canonical_2024` → **`schemas.ingress.layer1.yaml#/iso3166_canonical_2024`** for `country_iso`/`legal_country_iso` FKs in S3/S8 surfaces. 

---

## 3.8 Read-gates & receipts (verify before use)

> **Coupling to layer schema.** All `module` and `substream_label` literals used by RNG events **MUST** be admitted by `schemas.layer1.yaml` (either via explicit enum sets or documented string patterns). If the layer schema later enumerates these values, the literals listed here **MUST** appear in those enums.

* **S6 PASS gate (membership convenience).** If `s6_membership` is used, S9 **MUST** verify the **co-located** S6 receipt (`…/s6/seed={seed}/parameter_hash={parameter_hash}/(S6_VALIDATION.json, _passed.flag)`) **before** reading membership. 
* **Fingerprint gate (consumer hand-off).** S9 itself publishes `validation_bundle_1A/` and `_passed.flag` under `validation/manifest_fingerprint={manifest_fingerprint}/`. Consumers **MUST** verify that `_passed.flag` content hash equals `SHA256(validation_bundle_1A)` for the same fingerprint **before** reading `outlet_catalogue`. *(Stated here for coupling; publish semantics live in §4.)* 

---

## 3.9 Path↔embed equality (applies to **all** reads)

Where lineage appears **both** in the path and embedded fields, **byte-equality is mandatory**:

* Egress: `outlet_catalogue.manifest_fingerprint equals the `manifest_fingerprint` path token` (path), `global_seed == seed`. 
* Parameter-scoped tables: each row embeds `parameter_hash` equal to the path token. 
* RNG logs/layer1/1A/events: embedded `{seed, parameter_hash, run_id}` **must equal** their path tokens on **every** row; events also carry the **layer envelope** (`before/after/blocks/draws`) and obey the **trace-after-each-event** rule.  

---

**Status:** §3 is **Binding**. It fixes the **complete input inventory**, **exact read gates**, **lineage equality**, and **partition laws** S9 must obey **before** performing any validation or replay.

---

# 4) Outputs — bundle & flag **(Binding)**

## 4.1 Validation bundle (fingerprint-scoped folder)

**Identifier:** `validation_bundle_1A`
**Location (partitioned):**
`data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/`
**Authority anchors:** Dataset Dictionary ID `validation_bundle_1A`; schema anchor `schemas.1A.yaml#/validation/validation_bundle`.  

**Role.** The bundle is the machine-readable proof set for S9’s checks and the basis for the consumer gate; it **MUST** be written for exactly one **fingerprint** and **MUST** not contain any producer data mutations. 

**Required files (minimum set).** S9 **MUST** write at least:

* `MANIFEST.json` — run metadata (includes `manifest_fingerprint`, `parameter_hash`, created time, code id). 
* `parameter_hash_resolved.json` — resolved parameter set identity. 
* `manifest_fingerprint_resolved.json` — resolved fingerprint identity. 
* `rng_accounting.json` — per-family event/trace reconciliation, audit/trace presence & path↔embed parity. 
* `s9_summary.json` — PK/UK/FK results, join-back stats, N-sum law, overflow list, lineage equality results (may include S8 checks carried forward). 
* `egress_checksums.json` — stable hashes for `outlet_catalogue` files in `[seed, manifest_fingerprint]` (per-file and composite) for byte-identity re-runs. 
* `index.json` — bundle index **conforming to** the schema: table with columns `{artifact_id, kind∈(plot|table|diff|text|summary), path, mime?, notes?}`; **every** non-flag file **MUST** appear exactly once with a relative `path`. 

**Folder-level invariants.**

* Partitioning is **[manifest_fingerprint]**; the embedded `manifest_fingerprint` in bundle files **MUST** equal the folder token. 
* All paths in `index.json` **MUST** be **relative** to the bundle root and ASCII-lexicographically orderable (used by §4.2 hashing). 
* Dependencies recorded in the Artefact Registry (at minimum `outlet_catalogue`, `rng_audit_log`) **MUST** be satisfied. 

## 4.2 Consumer gate flag (file)

**Identifier:** `validation_passed_flag_1A`
**Path:** `…/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag` (co-located with the bundle). 

**Content (exact).** One line:
`sha256_hex = <hex64>`
where `<hex64>` is the **SHA-256 over the concatenation of the raw bytes of all files listed in `index.json`** (excluding `_passed.flag`), in **ASCII-lexicographic order of the `index.json` `path` entries**. Hex is lower-case, 64 chars.

**Consumer rule (binding).** Downstream readers (e.g., `outlet_catalogue` consumers) **MUST** verify that `_passed.flag` **matches** `SHA256(validation_bundle_1A)` for the **same fingerprint** **before** any read. **No PASS → no read.** The Dictionary entry for `outlet_catalogue` **repeats** this consumer obligation.  

## 4.3 Publish & atomicity

S9 **MUST** publish atomically: stage the entire bundle in a temporary directory under the validation path (e.g., `…/validation/_tmp.{uuid}`), compute `_passed.flag` **in the staged folder**, then perform a **single atomic rename** to `manifest_fingerprint={manifest_fingerprint}/`. **Partial contents MUST NOT become visible**. On failure, delete the temp. 

**PASS vs FAIL outcome.**

* **PASS:** write the full bundle **and** `_passed.flag` (computed as above). 
* **FAIL:** write the bundle **without** `_passed.flag`; the gate remains failed for that fingerprint. 

## 4.4 Idempotency & equivalence

Re-running S9 for the same `{seed, parameter_hash, manifest_fingerprint}` under identical inputs **MUST** produce **byte-identical** bundle contents; two bundles are **equivalent** iff `MANIFEST.json` matches byte-for-byte, all files listed in `index.json` (excluding `_passed.flag`) match byte-for-byte, and `_passed.flag` hashes match. 

## 4.5 Retention & lineage

Retention/TTL for `validation_bundle_1A` follows the Dictionary; lineage within bundle files **MUST** embed the same `manifest_fingerprint` as the path token. (Additional lineage like `parameter_hash` may be included per S0’s enumerations.)  

---

**Status:** §4 is **Binding**. It fixes the **what/where** of S9’s outputs, the **exact flag hashing rule**, **atomic publish**, and the **consumer gate** that protects `outlet_catalogue`.

---

# 5) Structural validation (schemas, partitions, FK) **(Binding)**

## 5.1 Scope (what S9 validates structurally)

S9 **MUST** validate, for every subject in scope, that **(a)** rows conform to the JSON-Schema anchor, **(b)** files live under the **Dictionary** path with the declared **partitions**, **(c)** embedded lineage **byte-equals** path tokens wherever both exist, **(d)** declared **PK/UK** constraints hold **per partition**, **(e)** **FKs** resolve to their targets. Subjects:

* **Egress:** `outlet_catalogue` → `schemas.1A.yaml#/egress/outlet_catalogue` (partitions `[seed, manifest_fingerprint]`). 
* **Authorities (parameter-scoped):** `s3_candidate_set` (required), optional `s3_integerised_counts`, optional `s3_site_sequence`.   
* **Membership (if used):** `s6_membership` (+ S6 receipt gate checked in §3). 
* **RNG core logs:** `rng_audit_log`, `rng_trace_log`. 
* **RNG event families (S1–S8 used by 1A):** hurdle/gamma/poisson/ztp/gumbel/residual_rank/sequence_finalize/site_sequence_overflow. (Schema anchors under `schemas.layer1.yaml#/rng/*`.)  

---

## 5.2 JSON-Schema conformance (shapes & domains)

For each dataset/log/event in §5.1, S9 **MUST** validate rows against the declared `$ref`:

* **Bundle schema:** `validation_bundle_1A` (for S9’s own output index and file descriptors) → `schemas.1A.yaml#/validation/validation_bundle`.  
* **Egress & S3 tables:** anchors in `schemas.1A.yaml` (e.g., `#/egress/outlet_catalogue`, `#/s3/candidate_set`, `#/s3/integerised_counts`, `#/s3/site_sequence`).  
* **Logs & events:** anchors in `schemas.layer1.yaml` for `rng_audit_log`, `rng_trace_log`, and all 1A event families (`#/rng/events/*`). 

**Notes (binding examples).**

* `manifest_fingerprint`/other SHA-256 fields must match the schema **pattern** (64 lowercase hex) where defined. 
* Event envelopes must contain the layer fields (`before`, `after`, `blocks`, `draws`, lineage, module/substream). (Accounting rules are verified in §7; presence/shape is structural here.) 

---

## 5.3 Partition law & path↔embed equality

S9 **MUST** verify that each subject lives under its **Dictionary path** with the declared **partition keys**, and where lineage fields are embedded they **byte-equal** the path tokens:

* **Egress `outlet_catalogue`:** path `…/outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`; partitions `[seed, manifest_fingerprint]`; enforce **`global_seed == seed`** and **`manifest_fingerprint equals the `manifest_fingerprint` path token`**. 
* **S3 datasets:** `…/parameter_hash={parameter_hash}/`; enforce embedded `parameter_hash` equals path token. 
* **S6 membership (if used):** `…/s6/seed={seed}/parameter_hash={parameter_hash}/`; enforce path↔embed equality; **gate verified in §3**. 
* **Core logs:** `rng_audit_log` and `rng_trace_log` under `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`; **every row** embeds `{seed, parameter_hash, run_id}` equal to the path. 
* **Event families (e.g., `sequence_finalize`, `site_sequence_overflow`):** paths per Dictionary/Registry; verify lineage equals path tokens.  

File order is **non-authoritative**; partition keys and PKs define truth. 

---

## 5.4 Primary/unique keys (per partition)

S9 **MUST** enforce the PK/UK constraints specified by schema/dictionary on a per-partition basis:

* **`outlet_catalogue`** — **PK/Sort:** `[merchant_id, legal_country_iso, site_order]`; enforce **uniqueness** per `(seed, manifest_fingerprint)` partition. 
* **`s3_candidate_set`** — uniqueness over `[merchant_id, candidate_rank, country_iso]` per `parameter_hash` partition (order authority is replay-checked in §8; here we enforce structural uniqueness). 
* **`s3_integerised_counts`** (if present) — uniqueness over `[merchant_id, country_iso]` per `parameter_hash`. 
* **`s3_site_sequence`** (if present) — uniqueness over `[merchant_id, country_iso, site_order]` per `parameter_hash`. 
* **RNG logs/layer1/1A/events** — JSONL streams **MUST NOT** contain duplicate rows for the same event identity fields as defined by the event schema (module/substream + envelope counters + payload identity); S9 treats duplicate physical files/lines with identical content as a **structural error**.

---

## 5.5 Foreign keys (referential integrity)

S9 **MUST** check FKs exactly as declared by schema/dictionary:

* **ISO-2 codes:** all `country_iso`/`legal_country_iso` fields in S3/S6/S8 surfaces **FK** to `iso3166_canonical_2024.country_iso` (uppercase ISO-3166-1 alpha-2; placeholders forbidden by the ingress schema).  
* **Event vs egress naming:** **events** use `country_iso`; **egress** uses `legal_country_iso`; both **FK** to the same ISO table (S9 enforces FK resolution under both names). 
* Any additional schema-declared FKs (e.g., to merchant seed lists) **MUST** resolve if present in the anchors (S9 uses the anchor’s `$ref` list to drive checks). 

---

## 5.6 Writer policy & file invariants

Where the Dictionary declares a **writer sort**, S9 **MUST** verify monotonicity **within each file** and **across file boundaries** in a partition:

* **`outlet_catalogue` writer sort:** `[merchant_id, legal_country_iso, site_order]`. 
  For JSONL streams, only **partitioning** and **schema** are binding (no sort requirement), but S9 **MUST** verify **one** cumulative `rng_trace_log` append **after each event append** exists (presence/placement is structural for trace; accounting is §7). 

---

## 5.7 Structural failure classes (binding)

On any breach below, S9 **fails** the run structurally (bundle written **without** `_passed.flag`):

* `E_SCHEMA_INVALID` — row violates its JSON-Schema. (Includes pattern/domain failures such as non-hex fingerprints.) 
* `E_PATH_EMBED_MISMATCH` — path tokens and embedded lineage differ (e.g., `manifest_fingerprint` mismatch). 
* `E_PARTITION_MISPLACED` — files not under Dictionary path/partitions. 
* `E_DUP_PK` — duplicate PK within a partition. (Applies to subjects in §5.4.) 
* `E_FK_ISO_INVALID` — ISO FK does not resolve (either `country_iso` or `legal_country_iso`). 
* `E_TRACE_COVERAGE_MISSING` — missing final `rng_trace_log` row(s) corresponding to event appends (structural presence check; numeric reconciliation in §7). 

---

**Status:** §5 is **Binding**. It defines exactly how S9 proves **shape**, **placement**, **identity**, and **referential** correctness **before** it performs RNG accounting (§7) or cross-state replay checks (§8).

---

# 6) Lineage & determinism checks **(Binding)**

## 6.1 Recompute & attest lineage keys (must match exactly)

S9 **MUST** recompute the lineage identifiers and prove equality to what producers wrote:

* **`parameter_hash`** — Recompute from the governed set **𝓟** using S0.2.2’s **UER + tuple-hash** procedure over canonical basenames; compare to the **partition key** and any embedded `parameter_hash` in parameter-scoped inputs (e.g., S3 tables). **Equality is mandatory.**  
* **`manifest_fingerprint`** — Recompute using S0.2.3 over the actually opened artefacts (𝓐), `git_32`, and `parameter_hash_bytes`; the result **MUST** byte-equal the `manifest_fingerprint` path token for `outlet_catalogue` and the bundle folder, and any embedded `manifest_fingerprint` fields.  
* **`run_id` (logs-only)** — Verify `run_id` presence and uniqueness per `{seed, parameter_hash}` using S0.2.4 (UER payload with bounded collision loop). S9 **MUST** assert that `run_id` partitions **only** logs/layer1/1A/events and that egress/parameter-scoped tables **do not** depend on `run_id`. 

S9 writes `parameter_hash_resolved.json` and `manifest_fingerprint_resolved.json` into the bundle as the attestation artefacts. 

---

## 6.2 Path↔embed identity (all subjects; byte-equality)

For **every** dataset/log/event S9 reads, **embedded lineage fields MUST byte-equal path tokens** where both appear:

* **Egress:** `outlet_catalogue.manifest_fingerprint equals the `manifest_fingerprint` path token` and `global_seed == seed`. 
* **Parameter-scoped inputs (e.g., S3):** embedded `parameter_hash == parameter_hash` path token. 
* **RNG logs & events:** each row embeds `{seed, parameter_hash, run_id}` that **must equal** the `{seed, parameter_hash, run_id}` in its path. (Event envelopes also satisfy layer schema presence; accounting is checked in §7.)  

Any mismatch ⇒ `E_PATH_EMBED_MISMATCH` (FAIL). *(Structural rules in §5 apply; this section enforces lineage equality as a determinism prerequisite.)* 

---

## 6.3 Partition identity, immutability & idempotence (must hold)

S9 **MUST** confirm the identity/immutability rules the producers were bound to:

* **Egress identity:** `(dataset='outlet_catalogue', seed, manifest_fingerprint)` is **write-once**; if the partition existed prior to the validated run, byte content **must** be identical. S9 records stable per-file and composite hashes in `egress_checksums.json`.  
* **Parameter-scoped identity:** `(dataset_id, parameter_hash)` instances are immutable once published. 
* **Logs identity:** `(stream, seed, parameter_hash, run_id)` instances are immutable; S9 treats duplicate physical lines/files for the *same* event identity as structural errors. 

Re-running S9 with identical inputs **MUST** yield a **byte-identical** bundle and `_passed.flag`. 

---

## 6.4 Determinism w.r.t. concurrency, sharding & scheduling (evidence checks)

S9 cannot observe worker counts; instead it proves outcomes are **independent** of them by checking invariants guaranteed by S7–S8:

* **Egress row-set determinism:** within each `(seed, manifest_fingerprint)` partition, `outlet_catalogue` obeys the Dictionary **writer sort** and encodes no cross-country order; equality is by **row set**, not file order.  
* **S8 block atomicity:** per `(merchant, legal_country_iso)` there is **exactly one** `sequence_finalize` event (non-consuming) with `{start="000001", end=zfill6(n)}`; overflow emits `site_sequence_overflow` and **no** egress rows for that merchant. 
* **Join-back stability:** distinct `(merchant, legal_country_iso)` in egress join 1:1 to S3 on `(merchant_id, country_iso)`, and sorting by `candidate_rank` yields one consistent cross-country order (egress itself remains order-free). 

---

## 6.5 No reliance on file order; set semantics

S9 **MUST** treat Parquet/JSONL physical order as **non-authoritative**; equality and checks are defined by schema keys and totals (plus writer sort where declared for egress). *(Inherited from S0/S8 determinism and the Dictionary.)*  

---

## 6.6 Roles of lineage keys (non-interchangeable; enforced)

S9 **MUST** enforce that lineage keys are used only in their scoped roles:

* **`seed`** drives RNG; partitions **all** RNG logs/layer1/1A/events (never S3/S5). 
* **`parameter_hash`** versions parameter-scoped inputs/outputs (e.g., S3, S5). Changing any **𝓟** member’s bytes flips it. 
* **`manifest_fingerprint`** versions egress/validation; consumers **must** verify the fingerprint-scoped gate before reading egress. 
* **`run_id`** partitions logs only; **never** influences model state or egress. 

Any misuse (e.g., `run_id` in an egress partition, or `seed` on parameter-scoped S3 tables) ⇒ `E_PARTITION_MISPLACED`. 

---

**Status:** §6 is **Binding**. It fixes how S9 **recomputes lineage**, enforces **path↔embed identity**, and proves **determinism/idempotence** independent of concurrency, ensuring the validated run is fully reproducible under the S0–S8 contracts.

---

# 7) RNG accounting & envelope invariants **(Binding)**

## 7.1 Per-event envelope checks (family-independent) — **MUST**

For **every** RNG event row S9 validates (S1/S2/S4/S6/S7/S8 families in scope):

* **Envelope presence & types.** Row **MUST** conform to the layer envelope (`rng_envelope`): `{ts_utc, module, substream_label, seed, parameter_hash, run_id, rng_counter_before_{lo,hi}, rng_counter_after_{lo,hi}, blocks:uint64, draws:dec_u128}`. 
* **Counter delta identity.** `blocks == u128(after) − u128(before)` in **unsigned 128-bit** arithmetic. **Fail** if not equal. 
* **Non-consuming invariants.** Families declared non-consuming **MUST** have `before == after`, `blocks = 0`, `draws = "0"`. **Fail** if any differs. 
* **Draws = actual uniforms.** `draws` **MUST** equal the sampler’s **actual** U(0,1) count for that event (independent of `blocks`). **Fail** on mismatch.  
* **Lane policy is implied by budgets.** Single-uniform families advance **one** block (low lane used, high lane discarded); two-uniform families consume **both lanes** of **one** block. 

**Failure classes (per row):** `E_RNG_COUNTER_MISMATCH` (blocks≠after−before); `E_RNG_BUDGET_VIOLATION` (draws≠budgeted); `E_NONCONSUMING_CHANGED_COUNTERS` (non-consuming but before≠after). 

---

## 7.2 Budget table by family — **MUST**

S9 applies the following **normative budgets** when reconciling `draws` and counter deltas (`blocks`). Family schemas further constrain payload/fields.

**S1 — hurdle_bernoulli** (`module=1A.hurdle_sampler`, `substream_label=hurdle_bernoulli`)

* **Deterministic branch** (π∈{0,1}): `blocks=0`, `draws='0'`, `u=null`.
* **Stochastic branch** (0<π<1): `blocks=1`, `draws='1'`.
* Schema enforces `draws∈{'0','1'}`, `blocks∈{0,1}` and `u∈(0,1)` when present.  

**S2 — NB mixture attempts & final** (modules per family; see Appendix A.1)

* **gamma_component** (`module="1A.nb_and_dirichlet_sampler"`, `substream_label="gamma_nb"`): **variable** draws (exact actual-use from Marsaglia–Tsang; includes 2 uniforms per Box–Muller normal + 1 uniform where required).
* **poisson_component** (`module="1A.nb_poisson_component"`, `substream_label="poisson_nb"`, `context="nb"`): **variable**; regime per S0 (§PTRS vs inversion) governs typical usage.
* **nb_final** (`module="1A.nb_sampler"`): **non-consuming** ⇒ `blocks=0`, `draws='0'`.
* Attempt structure: exactly **one** gamma then **one** poisson per attempt; finaliser once (accepted `N≥2`).  

**S4 — ZTP target** (`module=1A.ztp_sampler`)

* **poisson_component (context='ztp')**: **consuming**; regime fixed per merchant: **inversion** if λ<10, **PTRS** if λ≥10.
* **ztp_rejection / ztp_retry_exhausted / ztp_final**: **non-consuming** ⇒ `blocks=0`, `draws='0'`.
* Attempts are **1-based**, strictly increasing; **exactly one** `ztp_final` when resolved (unless policy=`abort`). Trace append after **each** event.   

**S6 — selection keys** (`module=1A.foreign_country_selector`, `substream_label=gumbel_key`)

* **gumbel_key**: **single-uniform** ⇒ `blocks=1`, `draws='1'`.
* Optional `stream_jump` markers (if present): **non-consuming** ⇒ `blocks=0`, `draws='0'`.  

**S7 — integerisation evidence**

* **residual_rank**: **non-consuming** ⇒ `blocks=0`, `draws='0'`; one per `(merchant_id,country_iso)` in domain; residuals quantised to **dp=8**.
* Optional **dirichlet_gamma_vector** (feature-flag): variable (sum of Gamma component budgets). Trace append after each event.  

**S8 — sequencing instrumentation** (`module=1A.site_id_allocator`)

* **sequence_finalize**: **non-consuming** ⇒ `blocks=0`, `draws='0'`; one per `(merchant,country)` with `n≥1`.
* **site_sequence_overflow** (guardrail): **non-consuming** ⇒ `blocks=0`, `draws='0'`. Trace append after each event.  

---

## 7.3 Open-interval uniform law — **MUST**

Where a family exposes a uniform **value** (e.g., S1 payload `u`), S9 **MUST** verify **strict-open** `u∈(0,1)`; exact 0.0 or 1.0 is **forbidden**. (Budget/trace checks do **not** require logging all uniforms; counters and `draws` carry authority.)  

---

## 7.4 Attempt/order invariants (families with loops) — **MUST**

* **S2 NB:** per attempt **exactly one** `gamma_component` then **one** `poisson_component`; on first `K≥2`, **exactly one** `nb_final` (non-consuming). 
* **S4 ZTP:** attempts are **1-based** and **monotone**; each `poisson_component` (consuming) is followed by either acceptance (`ztp_final`, non-consuming) or a **non-consuming** rejection marker; cap policy produces either `ztp_retry_exhausted` (non-consuming; **no** final) or `ztp_final{K_target=0}` (non-consuming). Envelope counters within a merchant’s substream are **monotone, non-overlapping**; replay by **counters**, not file order. 

**Failure classes:** `E_S4_SEQUENCE_INVALID` (attempt index/order breach), `E_FINALISER_CARDINALITY` (0/>1 where exactly one required). 

---

## 7.5 Trace coverage & reconciliation — **MUST**

For each `(module, substream_label)`:

* **Coverage duty.** After **every** event append, there is **exactly one** cumulative `rng_trace_log` row appended (saturating totals). **Fail** if any event lacks a following trace row.  
* **Totals reconciliation.** On the **final** trace row per key (selection per schema note), verify:
  `draws_total == Σ parse_u128(draws)`;
  `blocks_total == Σ blocks`;
  `events_total ==` event count. *(No identity is implied between draws and blocks totals.)*  
* **Isolation.** Only the families owned by that state/module appear under that key (e.g., S6 trace keys only cover `gumbel_key`/`stream_jump`). 

**Failure classes:** `E_TRACE_COVERAGE_MISSING` (coverage), `E_TRACE_TOTALS_MISMATCH` (totals), `E_TRACE_ISOLATION_BREACH`. 

---

## 7.6 Audit presence & lineage parity — **MUST**

* **rng_audit_log** **MUST** exist for each `{seed, parameter_hash, run_id}` observed in events/trace; path↔embed lineage equality holds; algorithm is `philox2x64-10`.  
* **Path↔embed equality** for `{seed, parameter_hash, run_id}` on **every** event/log row (see §6 for lineage checks). 

---

## 7.7 Numeric profile & overflow guards — **MUST**

* Validation assumes S0’s numeric profile: **binary64, RNE, FMA-off, no FTZ/DAZ**; Box–Muller uses the pinned **hex-float TAU** constant and **two uniforms per normal** (no caching).  
* Trace counters are **uint64 saturating**; emitters **MUST** avoid overflow (else **budget violation**). 

---

**Status:** §7 is **Binding**. It fixes how S9 reconciles **per-event envelopes**, **family budgets**, **loop discipline**, and **trace totals**, enforcing the strict-open uniform law and non-consuming semantics before declaring the run PASS.

---

# 8) Cross-state replay checks **(Binding)**

S9 **re-derives facts from written inputs only** (events, tables, logs) and **fails closed** on any mismatch. This section fixes the per-state checks S9 MUST perform—beyond structural (§5) and envelope/budget law (§7).

---

## 8.1 S1 — Hurdle (single vs multi) **MUST**

For each merchant within `{seed, parameter_hash, run_id}`:

* **Cardinality & gating.** Exactly **one** `rng_event.hurdle_bernoulli`; downstream **1A RNG streams** (S2/S4/S6/S7/S8) **exist iff** `is_multi=true`.  
* **Deterministic vs stochastic.**
  – If `pi∈{0.0,1.0}`: `draws='0'`, `blocks=0`, `u=null`, `deterministic=true`.
  – If `0<pi<1`: `draws='1'`, `blocks=1`, `u∈(0,1)`, and `(u < pi) == is_multi`.  
* **Failure classes.** `E_S1_CARDINALITY` (≠1 row), `E_S1_U_OUT_OF_RANGE`, `E_S1_GATING_VIOLATION`. 

---

## 8.2 S2 — NB mixture → `N≥2` (logs) **MUST**

For each merchant with S1 `is_multi=true`:

* **Attempt discipline.** Per attempt: **one** `gamma_component(context='nb')` then **one** `poisson_component(context='nb')`; counters monotone/non-overlapping.  
* **Finaliser.** Exactly **one** **non-consuming** `nb_final` echoing `μ,φ` and fixing `n_outlets=N≥2` and `nb_rejections=r≥0`. 
* **Join to egress.** In `outlet_catalogue`, `raw_nb_outlet_draw` **equals** `nb_final.n_outlets` for the merchant. 
* **Failure classes.** `E_S2_COMPONENT_ORDER`, `E_S2_FINAL_MISSING_OR_DUP`, `E_S2_N_LT_2`. 

---

## 8.3 S3 — Candidate set (sole cross-country order) **MUST**

* **Order authority.** For each merchant: `candidate_rank` is **total & contiguous** with **home=0**; S9 **never invents order**. 
* **FKs & uniqueness.** One row per `(merchant_id,country_iso,candidate_rank)`. (Structural checks in §5.) 
* **Failure classes.** `E_S3_RANK_GAPS`, `E_S3_HOME_NOT_ZERO`. 

---

## 8.4 S4 — ZTP target (`K_target`) **MUST**

For eligible multi-site merchants:

* **Attempt loop.** `poisson_component(context='ztp')` attempts are **1-based**, strictly increasing; each attempt followed by **either** a non-consuming `ztp_rejection` **or** a single non-consuming `ztp_final`. Cap policy respected: `"abort"` ⇒ `ztp_retry_exhausted` and **no** final; `"downgrade_domestic"` ⇒ `ztp_final{K_target=0, exhausted:true}`.  
* **Uniqueness.** ≤1 `ztp_final` per resolved merchant. Regime (`inversion` if λ<10 else `ptrs`) **constant per merchant**. 
* **Failure classes.** `E_S4_SEQUENCE_INVALID`, `E_S4_FINAL_CARDINALITY`, `E_S4_POLICY_VIOLATION`. 

---

## 8.5 S6 — Membership realisation (by events or convenience) **MUST**

S9 must choose **one** path (as declared in §3):

* **M1 — Convenience surface (`s6_membership`)**: **Require S6 PASS** receipt, then assert rows **equal** the top-`K_target` **eligible** countries by **Gumbel key** order (ties: lower S3 `candidate_rank`, then ISO A→Z per schema); `selected=true ⇒ selection_order∈[1..K]`; `weight==0 ⇒ key=null ∧ selected=false`. 
* **M2 — Event replay (`gumbel_key`)**: From `rng_event.gumbel_key` rows (one uniform each), reconstruct keys and select exactly
  `K_realized = min(K_target, |Eligible|)`; **eligible** means considered with `w>0` after policy filters/caps.  
* **Failure classes.** `E_S6_PASS_MISSING` (when M1 chosen), `E_S6_MEMBERSHIP_MISMATCH`, `E_S6_ZERO_WEIGHT_SELECTED`. 

---

## 8.6 S7 — Integer allocation parity (dp=8 residuals) **MUST**

Using `{home} ∪ S6-selected foreigns` in **S3 `candidate_rank` order**:

* **Reconstruct counts.** Apply **largest-remainder** with **dp_resid=8** residuals and the fixed tie-break (residual↓, ISO A→Z, then `candidate_rank↑`), then prove:
  (i) `Σ_i count_i = N` (from S2), and (ii) per-country `residual_rank` equals the persisted evidence.  
* **Failure classes.** `E_S7_PARITY` (residual/order/Σ law mismatch). 

---

## 8.7 S8 — Egress & sequencing **MUST**

For the `(seed, manifest_fingerprint)` partition:

* **Per-block sequencing.** For each `(merchant, legal_country_iso)` with `count_i≥1`: `site_order = 1..count_i` contiguous; `site_id = zfill6(site_order)`; **exactly one** non-consuming `sequence_finalize{start="000001", end=zfill6(count_i)}`; overflow ⇒ `site_sequence_overflow` and **no** egress rows for that merchant.  
* **Sum law & lineage.** Per merchant: `Σ_i final_country_outlet_count_i = N` (from S2). Egress encodes **no cross-country order** (join S3 when needed). `manifest_fingerprint` and `global_seed` **equal** their path tokens.  
* **Failure classes.** `E_S8_SEQUENCE_GAP`, `E_SITE_ID_OVERFLOW`, `E_SUM_MISMATCH`, `E_ORDER_AUTHORITY_DRIFT`.  

---

## 8.8 Cross-state joins & global invariants **MUST**

* **Join-back uniqueness.** `outlet_catalogue` joins **1:1** to S3 on `(merchant_id, country_iso)` (egress uses `legal_country_iso`; both FKs hit canonical ISO).  
* **Cardinality chain.** For each merchant:
  `N (S2) → K_target (S4) → K_realized (S6) → {count_i} (S7) → sequences 1..count_i (S8)`; each step’s equality/inequality laws must hold (e.g., `K_realized = min(K_target, |Eligible|)`).  
* **No weights in S9.** S9 **does not** read S5 weight surfaces; it uses S6 events (or gated membership) and S7 evidence to replay selection/allocation. 

---

**Status:** §8 is **Binding**. It fixes the **per-state replay predicates**, **cross-state joins**, and **failure classes** S9 MUST apply before issuing the PASS decision.

---

# 9) Acceptance thresholds & PASS decision **(Binding)**

## 9.1 What “PASS” means (run-level)

S9 **issues PASS** for a `{seed, manifest_fingerprint}` only if **all** Binding checks in §§5–8 succeed for **every** merchant in scope. On PASS, S9 **publishes** `validation_bundle_1A/` under `…/validation/manifest_fingerprint={manifest_fingerprint}/` **and** a colocated `_passed.flag` whose content hash equals `SHA256(validation_bundle_1A)` (ASCII-lexicographic order of the `index.json` **`path`** entries, excluding `_passed.flag`). **Consumers MUST verify this before reading `outlet_catalogue`** (**no PASS → no read**).   

## 9.2 What “FAIL” means (run-level)

S9 **withholds** `_passed.flag` (bundle still written) if **any** Binding check fails in:
(a) **Structural** (§5: schema/partition/path↔embed/PK/UK/FK/writer policy),
(b) **Lineage/Determinism** (§6: recomputed `parameter_hash`/`manifest_fingerprint`, idempotence, writer sort, join-back stability),
(c) **RNG envelope/accounting** (§7: counters, `draws`, non-consuming invariants, trace coverage/totals, attempt order),
(d) **Cross-state replay** (§8: S1→S8 facts). **No partial PASS** is allowed.    

## 9.3 Tolerated (non-error) cases

The following **do not** prevent PASS when all other checks succeed (they are explicitly defined as non-errors upstream):

* **S6 deterministic empties/shortfalls**: `NO_CANDIDATES`, `K_ZERO`, `ZERO_WEIGHT_DOMAIN`; **shortfall** where (|Eligible|<K_{target}) (select all eligible). S9 records these as **informative** in the bundle. 
* **S8 degenerate but valid**: single-country domain (`DEG_SINGLE_COUNTRY`) and zero-remainder label (`DEG_ZERO_REMAINDER`).  

## 9.4 Optional/absent surfaces (NA semantics)

S9 **does not fail** due to absence of optional convenience surfaces, provided the mandated replay path is followed instead:

* `s6_membership` absent ⇒ replay membership from `gumbel_key` + S3/S4 facts; **S6 PASS** is only required when reading the convenience surface. 
* `s3_integerised_counts` absent ⇒ reconstruct per-country counts from S7 `residual_rank` over S3 domain and enforce Σ-law to `N` (S2). 

## 9.5 Hard-fail classes (non-exhaustive)

S9 **MUST** treat each of the following as **FAIL** for the fingerprint:

**Structural (§5):**
`E_SCHEMA_INVALID`, `E_PARTITION_MISPLACED`, `E_PATH_EMBED_MISMATCH`, `E_DUP_PK`, `E_FK_ISO_INVALID`, `E_TRACE_COVERAGE_MISSING`. 

**Lineage/Determinism (§6):**
Mismatch in recomputed `parameter_hash`/`manifest_fingerprint`; non-idempotent egress content for same `(seed, manifest_fingerprint)`; egress writer sort broken; S8 block atomicity breach (missing/duplicate `sequence_finalize`). 

**RNG envelope/accounting (§7):**
`E_RNG_COUNTER_MISMATCH` (blocks≠after−before), `E_RNG_BUDGET_VIOLATION` (`draws` mismatch), `E_NONCONSUMING_CHANGED_COUNTERS` (non-consuming but counters moved), `E_TRACE_TOTALS_MISMATCH`, `E_S4_SEQUENCE_INVALID`, `E_FINALISER_CARDINALITY`. 

**Cross-state replay (§8):**
S1: `E_S1_CARDINALITY`, `E_S1_U_OUT_OF_RANGE`, `E_S1_GATING_VIOLATION`.
S2: `E_S2_COMPONENT_ORDER`, `E_S2_FINAL_MISSING_OR_DUP`, `E_S2_N_LT_2`.
S3: `E_S3_RANK_GAPS`, `E_S3_HOME_NOT_ZERO`.
S4: `E_S4_FINAL_CARDINALITY`, `E_S4_POLICY_VIOLATION`.
S6: `E_S6_PASS_MISSING` (when using membership surface), `E_S6_MEMBERSHIP_MISMATCH`, `E_S6_ZERO_WEIGHT_SELECTED`.
S7: `E_S7_PARITY` (residual/order/Σ-law mismatch).
S8: `E_S8_SEQUENCE_GAP`, `E_SITE_ID_OVERFLOW`, `E_SUM_MISMATCH`, `E_ORDER_AUTHORITY_DRIFT`.  

## 9.6 Gate publication behaviour

* **PASS:** S9 writes `validation_bundle_1A/` **and** `_passed.flag` (one line: `sha256_hex = <hex64>`, computed over the raw bytes of all files listed in `index.json` (excluding `_passed.flag`) in ASCII-lexicographic order of the **`path`** entries), performing an **atomic rename** into `manifest_fingerprint={manifest_fingerprint}/`. 
* **FAIL:** S9 writes the bundle (with failure records) **without** `_passed.flag`. **Consumers MUST NOT** read `outlet_catalogue` for that fingerprint. 

## 9.7 Summary: PASS checklist (must all be TRUE)

1. All subjects pass **schema**/$ref validation. 
2. **Partitions & path↔embed** equality hold for every read subject. 
3. **PK/UK** constraints hold; **FKs** resolve (ISO). 
4. Recomputed `parameter_hash` and `manifest_fingerprint` **match**. 
5. RNG events satisfy **envelope invariants**, **budgets**, and **trace coverage/totals**. 
6. Cross-state replay equalities hold (S1→S8), incl. S8 **sequence_finalize** per (merchant,country) and **Σ-law** to S2 `N`. 
7. S6 **PASS receipt** verified **if** membership convenience surface was used. 
8. Bundle contains required files; `_passed.flag` content hash equals `SHA256(validation_bundle_1A)`. 

---

**Status:** §9 is **Binding**. It defines the **exact PASS/FAIL criteria**, tolerated non-errors, NA semantics for optional surfaces, and the **gate publication** that governs downstream access to `outlet_catalogue`.

---

# 10) Error handling, edge cases & degrade ladder **(Binding)**

## 10.1 Failure scope & actions (normative)

S9 classifies breaches by **scope** and applies the following actions:

| Scope               | What it means                                                                                                                                                                                | Action                                                                                                                   |
|---------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| **Run-scoped**      | Configuration/authority violations that make the whole fingerprint untrustworthy (schema/dictionary/registry conflicts, lineage recompute mismatch, label registry drift, partition misuse). | **FAIL run** → publish **bundle only** (no `_passed.flag`).                                                              |
| **Merchant-scoped** | A specific merchant’s producer outputs/logs violate binding laws (e.g., S2 attempt order broken, S4 attempt sequence invalid, S8 sequence gap).                                              | Mark merchant as **failed** in bundle; **FAIL run** (no `_passed.flag`). *(S9 is a **gate**, not a best-effort linter.)* |

**Run-scoped examples (non-exhaustive):** schema/partition FK violations; path↔embed inequality; label/stream registry breach; dictionary writer-policy breach; recomputed `parameter_hash`/`manifest_fingerprint` mismatch.   

**Merchant-scoped examples (non-exhaustive):** S1 cardinality/gating; S2 component order; S4 attempt/order/policy; S6 membership mismatch; S7 residual parity; S8 sequence gaps/overflow policy breach (see §10.4).      

---

## 10.2 Edge cases (deterministic **non-errors**)

The following outcomes are **valid** when upstream states behaved per spec; S9 **MUST NOT** fail solely due to their occurrence:

* **S6 deterministic empties/shortfalls.** `NO_CANDIDATES`, `K_ZERO`, or (|Eligible|<K_{target}) (select all eligible). Record as **informative** in the bundle. 
* **S8 degenerate domains.** `DEG_SINGLE_COUNTRY` and `DEG_ZERO_REMAINDER` (per-country blocks still 1..nᵢ; finalize events present). 
* **S4 gated zero-target paths.** `A=0` (no admissible foreigns) or policy `downgrade_domestic` resulting in `ztp_final{K_target=0, exhausted:true}`.  

---

## 10.3 Degrade ladder (when optional conveniences are absent)

S9 **MUST** follow this ladder; absence of an optional surface is **not** a failure if the next step is followed correctly:

1. **Counts:** If `s3_integerised_counts` exists, use it; **else** reconstruct counts from S7 `residual_rank` over the S3 domain and enforce Σ-law to S2 `N`. **Never** read S5 weights.  
2. **Membership:** If `s6_membership` exists, **verify S6 PASS** then use it; **else** replay from `gumbel_key` (+ S3/S4 facts). 
3. **Upstream sequence (if present):** `s3_site_sequence` is **cross-check only**; divergence is a **failure** (see below). 

---

## 10.4 Overflow & policy-specific rules (S8)

S8 defines a **guardrail** for per-country site counts `n>999,999`:

* **Correctly handled overflow (merchant-scoped abort; non-error):** S8 **emitted** one **non-consuming** `site_sequence_overflow{…, max_seq=999999, severity="ERROR"}` **and** wrote **no** `outlet_catalogue` rows for that merchant. S9 records the merchant in the bundle and **does not** fail solely for the overflow condition.  
* **Policy breach (failure):** any egress rows exist for an overflowed merchant **or** the overflow event is missing/inconsistent → `E_OVERFLOW_POLICY_BREACH` (**merchant-scoped**) and **FAIL run**. 

---

## 10.5 S4 cap & policy handling

S4’s zero-draw cap and policy are **governed**:

* **Allowed policies:** `abort` or `downgrade_domestic` (part of `parameter_hash`). 
* **Validator checks:** attempts are **1-based**; `ztp_retry_exhausted` appears only at cap; **either** no `ztp_final` when policy=`abort` **or** `ztp_final{K_target=0, exhausted:true}` when policy=`downgrade_domestic`. Any other combination ⇒ **merchant-scoped failure** (cap/policy violation).  

---

## 10.6 Failure vocabulary (canonical S9 codes)

S9 **MUST** use the following failure codes in bundle records (non-exhaustive, aligned to §§5–8):

* **Structural:** `E_SCHEMA_INVALID`, `E_PARTITION_MISPLACED`, `E_PATH_EMBED_MISMATCH`, `E_DUP_PK`, `E_FK_ISO_INVALID`, `E_TRACE_COVERAGE_MISSING`.   
* **Lineage/Determinism:** `E_LINEAGE_RECOMPUTE_MISMATCH`, `E_WRITER_SORT_BROKEN`, `E_S8_BLOCK_ATOMICITY`.   
* **RNG envelope/accounting:** `E_RNG_COUNTER_MISMATCH`, `E_RNG_BUDGET_VIOLATION`, `E_NONCONSUMING_CHANGED_COUNTERS`, `E_TRACE_TOTALS_MISMATCH`, `E_S4_SEQUENCE_INVALID`, `E_FINALISER_CARDINALITY`.  
* **Cross-state replay:** `E_S1_CARDINALITY`, `E_S1_GATING_VIOLATION`, `E_S2_COMPONENT_ORDER`, `E_S2_N_LT_2`, `E_S3_RANK_GAPS`, `E_S3_HOME_NOT_ZERO`, `E_S6_MEMBERSHIP_MISMATCH`, `E_S7_PARITY`, `E_S8_SEQUENCE_GAP`, `E_ORDER_AUTHORITY_DRIFT`, `E_SUM_MISMATCH`, `E_OVERFLOW_POLICY_BREACH`.    

---

## 10.7 Bundle logging (required fields)

S9 **MUST** write failure/intel rows into `s9_summary.json` and index them in `index.json`, using stable keys:

```
s9.fail.code, s9.fail.scope ∈ {"RUN","MERCHANT"},
s9.fail.reason, s9.fail.dataset_id?, s9.fail.anchor?,
s9.run.seed, s9.run.parameter_hash, s9.run.manifest_fingerprint,
s9.fail.merchant_id?, s9.fail.country_iso?, s9.fail.attempt?, s9.fail.expected?, s9.fail.observed?
```

These mirror upstream producer diagnostics (e.g., S4 failure keys) and enable 1:1 correlation with validator checks.  

---

## 10.8 No partial visibility & atomicity

On any **run-scoped** or **merchant-scoped** failures, S9 **MUST** still write a complete bundle; `_passed.flag` is **withheld** on FAIL. Publish uses **stage → compute hash → atomic rename**; **no partial contents** may become visible.  

---

**Status:** §10 is **Binding**. It fixes the **scope→action** rules, enumerates **non-error edge cases**, defines the **degrade ladder**, sets overflow/policy handling precisely, and standardises **failure vocabulary and logging** for the S9 validation bundle.

---

# 11) Concurrency, sharding & atomics **(Binding)**

## 11.1 Execution model (read-parallel, order-agnostic)

S9 is a **read-only** validator. It **MAY** scan inputs in parallel but **MUST NOT** rely on physical file order. For JSONL logs/layer1/1A/events the Dataset Dictionary declares **set semantics** (`ordering: []`), so S9’s checks **MUST** be defined by keys and totals, not by line/file sequence. Egress order is governed by the Dictionary **writer sort** and is verified as a constraint (see §5).  

## 11.2 Sharding & run binding

* **Run binding (logs).** RNG events and core logs are partitioned by `{seed, parameter_hash, run_id}`. S9 **MUST** derive the set of observed `{run_id}` from the event streams in scope and validate **matching** `rng_trace_log` and `rng_audit_log` partitions for each tuple. 
* **Multi-run coexistence.** Multiple `run_id`s may exist for the same `{seed, parameter_hash}`; S9 treats each independently when reconciling envelopes/trace and then aggregates per the spec’s totals rules. (Egress remains fingerprint-scoped.) 

## 11.3 Deterministic reductions (commutative/associative)

All S9 aggregations **MUST** be deterministic regardless of worker count/scheduling:

* **Trace reconciliation.** Select the **final** cumulative `rng_trace_log` row per `(module,substream_label,run_id)` using this deterministic key:
  `ORDER BY events_total DESC, ts_utc DESC, rng_counter_after_hi DESC, rng_counter_after_lo DESC LIMIT 1`.
  This selection is independent of file arrival order and filesystem chunking.
* **Row-set equality.** Where S9 compares tables across files (e.g., egress partitions), equality is by **PK/UK and content**, not physical sequence; writer-sort monotonicity is checked per §5.6. 
* **Join-back checks.** S9 computes join/permutation checks using S3’s **`candidate_rank`** as the single order authority; the computation is key-driven and stable. 

## 11.4 Atomic publish (bundle & flag)

S9 **MUST** publish the validation bundle **atomically**: build under a temporary directory (e.g., `…/validation/_tmp.{uuid}`), compute `_passed.flag` over **all files listed in `index.json` (excluding `_passed.flag`)** in **ASCII-lexicographic order of the `path` entries**, then perform a **single atomic rename** to `manifest_fingerprint={manifest_fingerprint}/`. **No partial contents** may become visible; on failure, remove the temp.  

## 11.5 Idempotent re-runs & equivalence

Re-running S9 with identical inputs and authorities **MUST** produce a **byte-identical** bundle and the same `_passed.flag` content. Two bundles are **equivalent** iff `MANIFEST.json` and **all** other files match byte-for-byte and the flag’s SHA-256 equals `SHA256(validation_bundle_1A)` for the same fingerprint. 

## 11.6 Concurrency-safety checks S9 MUST enforce

* **Trace coverage under parallelism.** For every validated event append, there is **exactly one** subsequent cumulative `rng_trace_log` row for its `(module, substream_label, run_id)`; totals reconcile on the final row. **Any gap or double-append is FAIL** (see §7). 
* **Egress monotonicity across files.** Within each `(seed, manifest_fingerprint)` egress partition, S9 verifies Dictionary **writer sort** `[merchant_id, legal_country_iso, site_order]` **within files and across file boundaries**. 
* **Set semantics for logs/layer1/1A/events.** JSONL streams are treated as **sets**; duplicate identity rows are structural errors; physical order is non-authoritative. 

## 11.7 No reliance on producer worker count

S9’s outcomes **MUST NOT** change with producer/validator worker counts or scheduling. This is guaranteed by:

* dictionary-pinned partitions and writer sort (egress),
* key-based joins to S3 order authority,
* set-based event/log semantics with cumulative trace, and
* atomic, fingerprint-scoped publish of the bundle/flag.   

---

**Status:** §11 is **Binding**. It fixes how S9 stays deterministic under parallel reads, enforces **set semantics**, and publishes the **bundle + gate** atomically and idempotently.

---

# 12) Bundle contents & metrics **(Binding)**

## 12.1 Bundle root & index (what the folder MUST contain)

* **Location (partitioned):**
  `data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/` (manifest_fingerprint partition). 
* **Every non-flag file MUST be listed once in `index.json`** using the schema below; `path` entries are **relative** to the bundle root; `kind ∈ {plot|table|diff|text|summary}`. **`artifact_id` MUST be unique.**
* **Index field hygiene:** `artifact_id` **MUST** match `^[A-Za-z0-9._-]+$` (ASCII only). `path` **MUST** be **relative** (no leading slash, no `..` segments) and ASCII-normalised.
* **Hashing precondition:** The gate hash (§9) is computed over the byte contents of **all files listed in `index.json`** (excluding `_passed.flag`) in **ASCII-lexicographic order of the `path` entries**.
* **Gate coupling (reminder):** `_passed.flag` sits in the same folder and contains `sha256_hex = <hex64>` computed over the raw bytes of **all files listed in `index.json` (excluding `_passed.flag`)**, in **ASCII-lexicographic order of the `path` entries**. Consumers **MUST** verify this for the same fingerprint **before** reading `outlet_catalogue`.

**`index.json` (schema — Binding):**

```
{ artifact_id: string, kind: "plot"|"table"|"diff"|"text"|"summary",
  path: string, mime?: string, notes?: string }
```

(Per `schemas.1A.yaml#/validation/validation_bundle.index_schema`.) 

---

## 12.2 Required artifacts (minimum set; MUST exist)

S9 **MUST** write at least the files below; all MUST appear in `index.json` (except `_passed.flag`):

1. **`MANIFEST.json`** — run identity & environment
   Required fields (non-exhaustive):
   `version="1A.validation.v1"`, `manifest_fingerprint`, `parameter_hash`, `git_commit_hex`, `artifact_count`, `math_profile_id`, `compiler_flags`, `created_utc_ns`.  
2. **`parameter_hash_resolved.json`** — canonical list of governed parameters (𝓟) with basenames in ASCII-lexicographic order.
3. **`manifest_fingerprint_resolved.json`** — derivation inputs (e.g., `git_commit_hex`, `parameter_hash`). 
4. **`rng_accounting.json`** — per-family RNG accounting & coverage (see §12.4).  
5. **`s9_summary.json`** — structural & replay verdicts (by check & by merchant); failure codes; gate decision summary (see §12.5).
6. **`egress_checksums.json`** — stable per-file & composite SHA-256 for `outlet_catalogue` in `[seed, manifest_fingerprint]` (see §12.6).
7. **`index.json`** — bundle index per §12.1. 

> **Hashing rule for the gate** (normative, repeated): `_passed.flag` = `sha256_hex` of the concatenation of the raw bytes of **all files listed in `index.json`** (excluding `_passed.flag`) in **ASCII-lexicographic order of the `path` entries**. 

---

## 12.3 Recommended/optional artifacts (included in flag hash when present)

* **`param_digest_log.jsonl`** — one line per governed parameter file `{filename,size_bytes,sha256_hex,mtime_ns}`. 
* **`fingerprint_artifacts.jsonl`** — one line per artefact opened into the fingerprint `{path,sha256_hex,size_bytes}`. 
* **`numeric_policy_attest.json`** — attestation of numeric policy (IEEE-754 binary64, RNE, FMA-off, no FTZ/DAZ) and S0.8 self-tests. 
* **`DICTIONARY_LINT.txt`, `SCHEMA_LINT.txt`** — optional lints; if emitted, they are part of the flag hash. 

---

## 12.4 `rng_accounting.json` (Binding — content & metrics)

Purpose: prove **envelope compliance**, **budget reconciliation**, and **trace coverage** for every RNG family used by 1A (S1/S2/S4/S6/S7/S8), per §7 rules.

**Shape (minimum fields):**

```
{
  "runs": [ { "seed": uint64, "parameter_hash": hex64, "run_id": string } ... ],
  "families": {
    "<family>": {
      "events_total": int64,
      "draws_total_u128_dec": string,   // Σ event.draws as decimal u128
      "blocks_total_u64": int64,        // Σ event.blocks
      "nonconsuming_events": int64,     // events with blocks=0, draws="0"
      "trace_rows_total": int64,        // rows seen in rng_trace_log for this key
      "trace_totals": {                 // from the final cumulative trace row
        "events_total": int64,
        "draws_total_u128_dec": string,
        "blocks_total_u64": int64
      },
      "audit_present": boolean,         // rng_audit_log partition exists for every run_id
      "coverage_ok": boolean            // exactly one trace append after each event append
    }, ...
  }
}
```

**Requirements.**

* **Families in scope** at minimum: `hurdle_bernoulli`, `gamma_component`, `poisson_component{context∈[nb,ztp]}`, `ztp_*` finals/rejections, `gumbel_key` (and optional `stream_jump`), `residual_rank`, `sequence_finalize`, `site_sequence_overflow`. (Bound by the Dictionary & layer schemas.)  
* **Trace coverage:** for each `(module, substream_label, run_id)` key, **exactly one** cumulative `rng_trace_log` row **after each** event append (coverage_ok = true). 
* **Totals reconciliation:** `draws_total_u128_dec` and `blocks_total_u64` in `trace_totals` **equal** the set-sums over the validated events (open-interval uniforms never equal {0,1}).  
* **Audit presence:** `rng_audit_log` exists and matches `{seed,parameter_hash,run_id}` partitions. 

---

## 12.5 `s9_summary.json` (Binding — acceptance summary & failures)

Purpose: one machine-readable summary of **structural**, **lineage/determinism**, **RNG accounting**, and **replay** outcomes that determine PASS vs FAIL.

**Shape (minimum fields):**

```
{
  "run": {
    "seed": uint64,
    "parameter_hash": hex64,
    "manifest_fingerprint": hex64,
    "decision": "PASS"|"FAIL"
  },
  "merchants_total": int64,
  "merchants_failed": int64,
  "failures_by_code": { "E_*": int64, ... },  // counts per canonical code
  "counts_source": "s3_integerised_counts"|"residual_rank",
  "membership_source": "s6_membership"|"gumbel_key",
  "checks": {
    "schema_pk_fk": true|false,
    "path_embed_equality": true|false,
    "rng_envelope": true|false,            // per §7.1
    "rng_trace_coverage": true|false,      // per §7.5
    "s1..s8_replay": true|false,           // aggregate of §8 checks
    "egress_writer_sort": true|false
  },
  "notes"?: string
}
```

* **Failure codes** MUST use the canonical vocabulary in §10.6 (e.g., `E_RNG_COUNTER_MISMATCH`, `E_S7_PARITY`, `E_S8_SEQUENCE_GAP`). (Consumer tools rely on these exact strings.)
* **`decision`** MUST match the publication behaviour in §9 (bundle always written; `_passed.flag` only on PASS).

(While `s9_summary.json` has no cross-file anchor, the above fields are **Binding** for S9; the **index.json** entry advertises it as `kind:"summary"`.) 

---

## 12.6 `egress_checksums.json` (Binding — stability & idempotence)

Purpose: prove **byte-stability** of `outlet_catalogue` under re-runs for the same `(seed, manifest_fingerprint)`.

**Shape (minimum fields):**

```
{
  "dataset_id": "outlet_catalogue",
  "seed": uint64,
  "manifest_fingerprint": hex64,
  "files": [ { "path": "part-....parquet", "sha256_hex": hex64, "size_bytes": int64 }, ... ],
  "composite_sha256_hex": hex64          // SHA-256 over concatenation of raw bytes of all listed files in ASCII-lexicographic order of the `path` entries
}
```

* File list MUST cover **all** files in `data/layer1/1A/outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`. **Writer sort** verification lives in §5; this file establishes byte-identity. 
* The **composite hash rule** mirrors the flag’s lexicographic concatenation pattern for determinism. 

---

## 12.7 Metrics (normative definitions the validator MUST compute)

S9 **MUST** compute and persist (via `rng_accounting.json` and `s9_summary.json`) at least:

* **`events_total` / `draws_total_u128_dec` / `blocks_total_u64` per family** (see §12.4) with reconciliation against the **final** cumulative `rng_trace_log` row for that key. 
* **`coverage_ok`** per family (exactly one trace append after each event append). 
* **`merchants_total` / `merchants_failed`** and **`failures_by_code`** (canonical codes per §10.6).
* **`counts_source`** = `"s3_integerised_counts"` or `"residual_rank"` (per chosen path in §3/§8). 
* **`membership_source`** = `"s6_membership"` (S6 PASS verified) or `"gumbel_key"` (events path). 
* **`egress_writer_sort`** boolean (PK/Sort `[merchant_id, legal_country_iso, site_order]` per Dictionary). 

---

## 12.8 Indexing rules (Binding)

* **All** bundle files except `_passed.flag` **MUST** appear in `index.json`.
* `artifact_id` values are **unique** within the bundle.
* `path` entries are **relative** and **ASCII-sortable**; S9 computes the gate’s hash over that lexicographic order.  

---

## 12.9 Retention & lineage (Binding)

* Retention/TTL for `validation_bundle_1A` is governed by the Dictionary (default 365 days). `index.json` and all JSON/JSONL within **embed the same `manifest_fingerprint`** as the path token. 

---

**Status:** §12 is **Binding**. It freezes the **required bundle files**, their **minimum schemas**, the **metrics** S9 MUST compute, and the **hashing/index rules** that couple the bundle to the consumer gate.

---

# 13) Consumer gate & HashGate coupling **(Binding)**

## 13.1 Consumer obligation (egress read rule)

Downstream consumers (e.g., 1B) **MUST NOT** read `outlet_catalogue` for a given `fingerprint` unless the **co-located** `_passed.flag` under
`data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/` **exists** and its **content** equals `SHA256(validation_bundle_1A)` **for the same fingerprint**. This is the canonical **no PASS → no read** gate for 1A egress. The Dataset Dictionary and Artefact Registry restate this consumer duty.  

## 13.2 What consumers MUST verify (exact checks)

Before any read of `outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/…`, a conformant consumer **MUST**:

1. **Locate the bundle** at `…/validation/manifest_fingerprint={manifest_fingerprint}/`. Assert that the egress partition’s path token `manifest_fingerprint` **byte-equals** `manifest_fingerprint` embedded in egress rows (path↔embed equality). 
2. **Verify the flag hashing rule.** Read `_passed.flag` (single line `sha256_hex = <hex64>`), list **all files listed in `index.json` (excluding `_passed.flag`)** in the bundle **in ASCII-lexicographic order of the `path` entries**, concatenate their raw bytes, compute SHA-256, and assert equality to `<hex64>`. *(The flag itself is excluded from the hash.)*  
3. **(Optional but recommended)**: re-hash `fingerprint_artifacts.jsonl` / `param_digest_log.jsonl` advertised by S0 to harden supply-chain checks. Failure of any step ⇒ treat the run as **invalid** and **abort** the read. 

## 13.3 Scope boundaries (what the gate does/does not cover)

* The **only** egress gate that governs `outlet_catalogue` consumption is the **fingerprint-scoped** `_passed.flag` described above; parameter-scoped receipts (e.g., S5 PASS) remain **independent** and are **not** substitutes for the egress gate. 
* If consumers read any **S6 convenience surface** (e.g., `s6_membership`), they **MUST** also verify the **S6 PASS receipt** (`…/s6/seed={seed}/parameter_hash={parameter_hash}/(S6_VALIDATION.json,_passed.flag)`) **before** use. This is separate from, and does not weaken, the S9 egress gate.  

## 13.4 HashGate coupling (CI/runtime metadata; optional)

Projects **MAY** couple the consumer gate to a central **HashGate** metadata service for CI/runtimes. When enabled:

* **Publish:** After a **PASS**, S9 (or CI) **MAY** POST a record keyed by `manifest_fingerprint` with at least: `{dataset_id:"outlet_catalogue", fingerprint, sha256_hex_of_bundle, artifact_count, created_utc_ns, git_commit_hex}`. *(Authoritative truth remains the on-disk bundle; HashGate is a convenience index.)*  
* **Enforce:** CI **MAY** block merges/deploys unless HashGate returns a record whose `sha256_hex` **matches** the `_passed.flag` content and whose `fingerprint` matches the partition being promoted. 
* **Read-time use:** A consumer **MAY** cache a HashGate **URI/receipt** to accelerate lookups, but **MUST** still succeed the **local** flag verification in §13.2 before reading egress. *(HashGate cannot override a failing local flag.)* 

## 13.5 Revocation & drift handling

* If the bundle exists but `_passed.flag` is **missing** or its hash **mismatches**, consumers **MUST** treat the partition as **failed** and refuse reads. *(S9 writes bundles without a flag on FAIL.)* 
* If any consumer detects a **path↔embed mismatch** (e.g., egress row `manifest_fingerprint` ≠ path token), that is a **hard error** equivalent to an invalid gate; refuse reads. 
* Re-publishing a fingerprint with different bytes is **disallowed**; partitions are **immutable**. Any byte drift is a violation; consumers should fail closed. 

## 13.6 Minimal consumer API (normative steps)

A conformant consumer library **MUST** expose (at minimum):

1. `verify_fingerprint_gate(fingerprint) -> PASS|FAIL` implementing §13.2.
2. `require_gate_then_open(dataset_id="outlet_catalogue", seed, fingerprint)` that **fails closed** on any gate/lineage breach.
3. `verify_receipt(path="…/s6/…") -> PASS|FAIL` for S6 where relevant.  

---

**Status:** §13 is **Binding**. It fixes the **consumer’s read-gate duty**, the **exact hashing check**, clarifies **scope boundaries** (egress vs parameter-scoped receipts), and defines an **optional HashGate coupling** for CI—without weakening the mandatory local `_passed.flag` verification.  

---

# 14) Observability & SLOs **(Binding)**

## 14.1 Signals & sinks (what S9 MUST expose)

S9 **MUST** emit machine-readable observability into the **validation bundle** (fingerprint-scoped) and **MAY** mirror selected counters to an ops sink. Required bundle artefacts and their shapes are fixed in §12 (`rng_accounting.json`, `s9_summary.json`, `egress_checksums.json`, `index.json`). These files live under:
`data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/`.  

**Upstream surfaces S9 reads for observability:**

* **Core RNG logs** (`rng_trace_log`, `rng_audit_log`) — JSONL, partitioned by `{seed, parameter_hash, run_id}`, **one cumulative trace row appended after each RNG event append**.  
* **S8 instrumentation families** (`sequence_finalize`, `site_sequence_overflow`) — **non-consuming**; used for coverage and overflow diagnostics; paths and gating as declared for 1A.  

## 14.2 Required counters & gauges (values S9 MUST compute)

S9 **MUST** compute and persist (via §12 artefacts) at least:

* **RNG coverage & totals** (per family used by 1A): `events_total`, `draws_total_u128_dec`, `blocks_total_u64`, `coverage_ok`, `audit_present`, and **final trace** reconciliation (`trace_totals == set-sums of events`). (See `rng_accounting.json` §12.4.) 
* **Run decision & failures:** `decision ∈ {PASS, FAIL}`, `merchants_total`, `merchants_failed`, and `failures_by_code{E_*}` (canonical codes from §10.6) in `s9_summary.json`. 
* **Source declarations:** `counts_source ∈ {"s3_integerised_counts","residual_rank"}`, `membership_source ∈ {"s6_membership","gumbel_key"}` (tie S9’s replay route to concrete sources).  
* **Egress stability:** per-file and composite SHA-256 for `outlet_catalogue` in the `(seed, manifest_fingerprint)` partition (`egress_checksums.json`). 

## 14.3 Lineage for metrics (run keys that MUST label metrics)

Every metric line S9 emits **MUST** carry `{seed, parameter_hash, run_id, manifest_fingerprint}` so that dashboards and forensics are keyed to immutable lineage (values-only; bytes-safe). 

## 14.4 SLO envelope (binding expectations S9 MUST attest)

The following are **SLO-style invariants** S9 **MUST** check and record (PASS requires all of them; see §9):

* **Gate integrity SLO.** `_passed.flag` exists **only** on PASS and its `sha256_hex` equals `SHA256(validation_bundle_1A)` (ASCII-lexicographic over all files listed in `index.json` (excluding `_passed.flag`)). Atomic publish: stage → compute → **single rename**; **no partial visibility**.  
* **Trace coverage SLO.** For each `(module, substream_label, run_id)` validated, there is **exactly one** cumulative `rng_trace_log` row **after each** event append; final trace totals reconcile with event sums. 
* **Determinism SLO.** Re-running S9 on identical inputs produces a **byte-identical** bundle and the same `_passed.flag`; egress file hashes are stable per `(seed, manifest_fingerprint)`.  
* **Order & partition SLO.** Egress obeys writer sort `[merchant_id, legal_country_iso, site_order]` within the `(seed, manifest_fingerprint)` partition; lineage **path↔embed equality** holds for all subjects. 

## 14.5 Alerting conditions (emit + record; MUST fail run)

S9 **MUST** record these conditions in `s9_summary.json` and **FAIL** the fingerprint (bundle written, flag withheld):

* Gate mismatch or partial publish (hash inequality / missing flag / non-atomic publish). 
* Trace coverage gap or totals mismatch for any family in scope. 
* Any structural, lineage, RNG-envelope, or replay failure listed in §9.5 (use canonical `E_*` codes). 

## 14.6 Optional latency & throughput (recommended)

S9 **SHOULD** add timing fields to `s9_summary.json` (or a separate `s9_timings.json` indexed in `index.json`):
`started_utc_ns`, `completed_utc_ns`, `duration_ms`, `events_validated_total`, `throughput_events_per_s` (values-only; no paths/PII). *(Optional metrics do not alter the gate hash rule beyond normal inclusion in the bundle.)* 

## 14.7 Retention & hygiene (binding via Dictionary)

Retention and storage hygiene for the bundle and logs follow the **Dataset Dictionary** (typical: bundles 365 days; core RNG logs 365 days; event families 180 days). JSONL streams are **set-semantics**; equality is by row set, not file order.  

---

**Status:** §14 is **Binding**. It fixes the **signals**, **required counters**, **lineage labels**, **SLO-style invariants** S9 must attest, **alerting conditions**, and the **retention/hygiene** rules—anchored to the same bundle/log authorities used across 1A.

---

# 15) Schema & Dictionary anchors in scope **(Binding)**

## 15.1 Schema sets in force & anchor resolution (normative)

* **Segment schemas:** `schemas.1A.yaml` (1A tables, egress, bundle). 
* **Layer schemas:** `schemas.layer1.yaml` (RNG events, core logs, validation receipts). 
* **Ingress schemas:** `schemas.ingress.layer1.yaml` (FK targets like ISO). 
* Anchor rule:
  - `#/rng/**` → layer schema
  - `#/validation/validation_bundle` → 1A schema
  - `#/validation/s6_receipt` → layer schema
  - `#/s3/**` & `#/egress/**` → 1A schema
  - ingress FKs (e.g., `#/iso3166_canonical_2024`) → ingress schema

## 15.2 Segment-1A schema anchors S9 touches

* **Egress:** `#/egress/outlet_catalogue`. (PK `[merchant_id,legal_country_iso,site_order]`; partitions `[seed, manifest_fingerprint]`.)  
* **Order authority:** `#/s3/candidate_set` (total & contiguous `candidate_rank`, home=0).  
* **Counts (optional path):** `#/s3/integerised_counts`.  
* **Sequence (optional cross-check):** `#/s3/site_sequence`. 
* **Membership (convenience surface):** `#/alloc/membership`.
* **Validation bundle (output of S9):** `#/validation/validation_bundle` + its `index_schema`.  

## 15.3 Layer-wide RNG & validation anchors S9 validates

* **Core logs:** `#/rng/core/rng_audit_log`, `#/rng/core/rng_trace_log`.  
* **S1:** `#/rng/events/hurdle_bernoulli`. 
* **S2:** `#/rng/events/gamma_component`, `#/rng/events/poisson_component`, `#/rng/events/nb_final`.  
* **S4 (ZTP):** `#/rng/events/poisson_component` (context ‘ztp’), `#/rng/events/ztp_rejection`, `#/rng/events/ztp_final`. 
* **S6:** `#/rng/events/gumbel_key` (and `#/rng/events/stream_jump` if emitted).  
* **S7:** `#/rng/events/residual_rank`. 
* **S8 instrumentation:** `#/rng/events/sequence_finalize`, `#/rng/events/site_sequence_overflow`.  
* **S6 receipt (gate):** `#/validation/s6_receipt`. 

## 15.4 Ingress / FK anchors

* **ISO FK target:** `schemas.ingress.layer1.yaml#/iso3166_canonical_2024` (uppercase ISO-2; placeholders forbidden).  

## 15.5 Dataset Dictionary IDs (IDs → path → partitions → `$ref`) used by S9

* **`outlet_catalogue`** → `data/layer1/1A/outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/` → `[seed, manifest_fingerprint]` → `schemas.1A.yaml#/egress/outlet_catalogue`. *(Writer sort `[merchant_id,legal_country_iso,site_order]`; “no PASS → no read”.)*  
* **`s3_candidate_set`** → `…/s3_candidate_set/parameter_hash={parameter_hash}/` → `[parameter_hash]` → `#/s3/candidate_set`. 
* **`s3_integerised_counts`** (optional) → `…/s3_integerised_counts/parameter_hash={parameter_hash}/` → `[parameter_hash]` → `#/s3/integerised_counts`. 
* **`s3_site_sequence`** (optional cross-check) → `…/s3_site_sequence/parameter_hash={parameter_hash}/` → `[parameter_hash]` → `#/s3/site_sequence`.  
* **`s6_membership`** (if used) → `…/s6/membership/seed={seed}/parameter_hash={parameter_hash}/` → `[seed,parameter_hash]` → `#/alloc/membership` (**gate**: `s6_validation_receipt`).
* **`s6_validation_receipt`** → `…/s6/seed={seed}/parameter_hash={parameter_hash}/` → `[seed,parameter_hash]` → `schemas.layer1.yaml#/validation/s6_receipt`. 
* **`rng_audit_log`** → `logs/layer1/1A/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl` → `[seed,parameter_hash,run_id]` → `#/rng/core/rng_audit_log`. 
* **`rng_trace_log`** → `logs/layer1/1A/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl` → `[seed,parameter_hash,run_id]` → `#/rng/core/rng_trace_log`. 
* **`rng_event.sequence_finalize`** → `logs/layer1/1A/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` → `[seed,parameter_hash,run_id]` → `#/rng/events/sequence_finalize`. 
* **`rng_event.site_sequence_overflow`** → `logs/layer1/1A/rng/events/site_sequence_overflow/…` → `[seed,parameter_hash,run_id]` → `#/rng/events/site_sequence_overflow`. 
* **`rng_event.residual_rank`** → `logs/layer1/1A/rng/events/residual_rank/…` → `[seed,parameter_hash,run_id]` → `#/rng/events/residual_rank`. 
* **`rng_event.gumbel_key`** → `logs/layer1/1A/rng/events/gumbel_key/…` → `[seed,parameter_hash,run_id]` → `#/rng/events/gumbel_key`. 
* **`rng_event.gamma_component` / `rng_event.poisson_component` / `rng_event.nb_final` / `rng_event.ztp_rejection` / `rng_event.ztp_final`** → `logs/layer1/1A/rng/events/{family}/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` → `[seed,parameter_hash,run_id]` → corresponding `#/rng/events/*` anchors.  
* **`validation_bundle_1A`** (output of S9) → `data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/` → `[manifest_fingerprint]` → `schemas.1A.yaml#/validation/validation_bundle`. *(Flag `_passed.flag` co-located; content hash equals `SHA256(bundle)`.)*  

---

**Status:** §15 is **Binding**. It freezes the **exact anchors** and **Dictionary IDs/paths/partitions** S9 recognises and enforces during validation and publish.

---

# Appendix A) Enumerations & literal labels **(Normative)**

This appendix freezes the **exact strings/enums** S9 relies on when validating S0–S8 and publishing the bundle/flag. Everything here is **binding**.

## A.1 RNG `module` / `substream_label` pairs (by state; S9 reads only)

* **S1 Hurdle**

  * `module="1A.hurdle_sampler"`, `substream_label="hurdle_bernoulli"`. 

* **S2 NB mixture**

  * `gamma_component`: `module="1A.nb_and_dirichlet_sampler"`, `substream_label="gamma_nb"`.
  * `poisson_component` (context `"nb"`): `module="1A.nb_poisson_component"`, `substream_label="poisson_nb"`.
  * `nb_final` (non-consuming): `module="1A.nb_sampler"`. 

* **S4 ZTP target**

  * `poisson_component` (context `"ztp"`): `module="1A.ztp_sampler"`, `substream_label="poisson_component"`.
  * `ztp_rejection` / `ztp_retry_exhausted` / `ztp_final` (non-consuming): `module="1A.ztp_sampler"`; `substream_label ∈ {"ztp_rejection","ztp_retry_exhausted","ztp_final"}`.  

* **S6 Selection keys**

  * `module="1A.foreign_country_selector"`, `substream_label ∈ {"gumbel_key","stream_jump"}` (`stream_jump` optional). 

* **S7 Integerisation (evidence)**

  * `residual_rank`: `module="1A.integerisation"`, `substream_label="residual_rank"`.
  * `dirichlet_gamma_vector` (if enabled): `module="1A.dirichlet_allocator"`, `substream_label="dirichlet_gamma_vector"`. 

* **S8 Sequencing instrumentation (non-consuming)**

  * `module="1A.site_id_allocator"`, `substream_label ∈ {"sequence_finalize","site_sequence_overflow"}`. 

> **Note.** **Budget literals** follow the layer envelope: single-uniform families `(blocks=1, draws="1")`, two-uniform Box–Muller `(blocks=1, draws="2")`, non-consuming `(blocks=0, draws="0")`. S9 enforces these in §7.  

---

## A.2 RNG family names & fixed payload enums

* **Families (S9 validates):**
  `hurdle_bernoulli`, `gamma_component`, `poisson_component{context∈{"nb","ztp"}}`, `nb_final`, `ztp_rejection`, `ztp_retry_exhausted`, `ztp_final`, `gumbel_key`, `stream_jump` (optional), `residual_rank`, `sequence_finalize`, `site_sequence_overflow`, and the layer helpers (e.g., `normal_box_muller`).  

* **S4 fixed enums (payload):**
  `context="ztp"`; `regime ∈ {"inversion","ptrs"}`; optional `reason="no_admissible"` on `ztp_final` (when present in the schema version). 

* **S6 fixed semantics (payload excerpts):**
  `gumbel_key`: `blocks=1`, `draws="1"`; if `weight==0` ⇒ `key=null`, `selected=false`, no `selection_order`. 

---

## A.3 Dataset Dictionary IDs → partitions → `$ref` (S9 read/write set)

* **Egress:** `outlet_catalogue` → partitions `[seed, manifest_fingerprint]` → `schemas.1A.yaml#/egress/outlet_catalogue`. *(No inter-country order encoded.)* 
* **Order authority (required):** `s3_candidate_set` → `[parameter_hash]` → `#/s3/candidate_set`. *(Home rank=0; ranks total & contiguous.)* 
* **Counts (optional path):** `s3_integerised_counts` → `[parameter_hash]` → `#/s3/integerised_counts`. 
* **Optional sequence cross-check:** `s3_site_sequence` → `[parameter_hash]` → `#/s3/site_sequence`. 
* **Membership convenience:** `s6_membership` → `[seed,parameter_hash]` → `#/alloc/membership` (gate = `s6_validation_receipt`).  
* **Core logs:** `rng_audit_log`, `rng_trace_log` → `[seed,parameter_hash,run_id]` → layer `#/rng/core/*`. 
* **Validation outputs (S9 writes):**
  `validation_bundle_1A` (folder) & `validation_passed_flag_1A` (file `_passed.flag`) under `validation/manifest_fingerprint={manifest_fingerprint}/`. 

---

## A.4 Gate & bundle literals

* **Flag filename:** `_passed.flag`
  **Content (one line):** `sha256_hex = <hex64>` where `<hex64>` is **SHA-256 over the raw bytes of all files listed in `index.json`**, in **ASCII-lexicographic order of the `path` entries**. *(Flag file excluded from the hash.)*

* **Bundle root:** `data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/`
  **Index schema kind:** `kind ∈ {"plot","table","diff","text","summary"}`. 

* **Required bundle filenames:**
  `MANIFEST.json`, `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`, `rng_accounting.json`, `s9_summary.json`, `egress_checksums.json`, `index.json`. 

---

## A.5 S8 sequencing constants (validated by S9)

* **`six_digit_seq` regex:** `^[0-9]{6}$` for `site_id`, `start_sequence`, `end_sequence`.
* **Overflow guardrail:** `max_seq = 999999`; `site_sequence_overflow.severity="ERROR"`; event is **non-consuming**.  

---

## A.6 Closed vocabularies & result labels

* **S4 policy enums:** `ztp_exhaustion_policy ∈ {"abort","downgrade_domestic"}`. 
* **S4 regime enum:** `regime ∈ {"inversion","ptrs"}`. 
* **S6 reason codes (diagnostic, non-error):** `NO_CANDIDATES`, `K_ZERO`, `ZERO_WEIGHT_DOMAIN`, `CAPPED_BY_MAX_CANDIDATES`. 
* **S8 outcome labels (informative):** `DEG_SINGLE_COUNTRY`, `DEG_ZERO_REMAINDER`. 
* **S9 run decision:** `PASS` | `FAIL`. *(Gate behaviour in §9; flag as above.)*

---

## A.7 Canonical S9 failure codes (write into bundle; see §10)

* **Structural:** `E_SCHEMA_INVALID`, `E_PARTITION_MISPLACED`, `E_PATH_EMBED_MISMATCH`, `E_DUP_PK`, `E_FK_ISO_INVALID`, `E_TRACE_COVERAGE_MISSING`. 
* **Lineage/Determinism:** `E_LINEAGE_RECOMPUTE_MISMATCH`, `E_WRITER_SORT_BROKEN`, `E_S8_BLOCK_ATOMICITY`. 
* **RNG envelope/accounting:** `E_RNG_COUNTER_MISMATCH`, `E_RNG_BUDGET_VIOLATION`, `E_NONCONSUMING_CHANGED_COUNTERS`, `E_TRACE_TOTALS_MISMATCH`, `E_S4_SEQUENCE_INVALID`, `E_FINALISER_CARDINALITY`. 
* **Cross-state replay:**
  `E_S1_CARDINALITY`, `E_S1_U_OUT_OF_RANGE`, `E_S1_GATING_VIOLATION`;
  `E_S2_COMPONENT_ORDER`, `E_S2_N_LT_2`;
  `E_S3_RANK_GAPS`, `E_S3_HOME_NOT_ZERO`;
  `E_S6_MEMBERSHIP_MISMATCH`, `E_S6_ZERO_WEIGHT_SELECTED`;
  `E_S7_PARITY`;
  `E_S8_SEQUENCE_GAP`, `E_SITE_ID_OVERFLOW`, `E_SUM_MISMATCH`, `E_ORDER_AUTHORITY_DRIFT`.  

---

## A.8 Envelope & lineage field names (must-match)

* **Envelope (layer-wide):** `ts_utc`, `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`, `module`, `substream_label`, `rng_counter_before_lo`, `rng_counter_before_hi`, `rng_counter_after_lo`, `rng_counter_after_hi`, `blocks`, `draws`. *(Row names, not order.)* 
* **Lineage equality (path↔embed):** where both exist, **byte-equality is mandatory**:
  e.g., `outlet_catalogue.global_seed == seed` & `manifest_fingerprint equals the `manifest_fingerprint` path token` path token; events/logs `{seed,parameter_hash,run_id}` equal to path tokens. 

---

## A.9 Writer sort & PKs (egress)

* **`outlet_catalogue`** writer sort: `[merchant_id, legal_country_iso, site_order]`; PK/UK identical tuple. *(File order non-authoritative; sort is a constraint.)* 

---

**This appendix is Binding.** Any deviation from these exact literals/enums is a **FAIL** under S9 (§§5–10).

---

# Appendix B) Bundle layout **(Informative)**

This appendix shows the **expected folder shape**, **example filenames**, and **hashing order** for the validation bundle. (Binding rules live in §§4 & 12; paths/IDs come from the Dictionary/Registry and 1A schemas.)   

## B.1 Where the bundle lives (fingerprint-scoped)

Root (partitioned by fingerprint):

```
data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/
```

This folder is the **single source** of validation artifacts for that fingerprint; the **consumer gate** `_passed.flag` is co-located here. (Dictionary + Registry)  

**Naming note.** Any path segment `manifest_fingerprint={…}` carries the run’s `manifest_fingerprint` value (S0 lineage rule). 

## B.2 Minimal bundle tree (PASS case)

```
validation/
└─ manifest_fingerprint={manifest_fingerprint}/
   ├─ MANIFEST.json
   ├─ parameter_hash_resolved.json
   ├─ manifest_fingerprint_resolved.json
   ├─ rng_accounting.json
   ├─ s9_summary.json
   ├─ egress_checksums.json
   ├─ index.json
   └─ _passed.flag              # content: "sha256_hex = <hex64>"
```

* The **files above (except `_passed.flag`) MUST be indexed** in `index.json` per the 1A **bundle index schema**; `artifact_id` unique; `path` **relative**. (Schema anchor: `schemas.1A.yaml#/validation/validation_bundle.index_schema`.) 
* `_passed.flag` content equals **SHA-256 over the raw bytes of all files listed in `index.json` (excluding `_passed.flag`) in this folder** in **ASCII-lexicographic order of the `path` entries**. (Dictionary/Registry notes + S9 §§4 & 12.)  

## B.3 Example `index.json` entries (shape only)

```json
[
  {"artifact_id":"manifest","kind":"text","path":"MANIFEST.json"},
  {"artifact_id":"rng_accounting","kind":"table","path":"rng_accounting.json","notes":"Per-family coverage & totals"},
  {"artifact_id":"summary","kind":"summary","path":"s9_summary.json"},
  {"artifact_id":"egress_hashes","kind":"table","path":"egress_checksums.json"},
  {"artifact_id":"catalog","kind":"table","path":"index.json"}
]
```

(Index schema fields are defined in `schemas.1A.yaml`.) 

## B.4 Optional extras (if present, they **are** part of the flag hash)

```
└─ manifest_fingerprint={manifest_fingerprint}/
   ├─ param_digest_log.jsonl          # one line per governed parameter
   ├─ fingerprint_artifacts.jsonl     # one line per artefact in the fingerprint
   ├─ numeric_policy_attest.json      # S0 numeric profile attestation
   ├─ DICTIONARY_LINT.txt             # optional
   └─ SCHEMA_LINT.txt                 # optional
```

(These are listed in S0 as lineage/attestation artefacts; still indexed in `index.json` when present.) 

## B.5 Lexicographic hashing order (worked example)

Given this file set:

```
egress_checksums.json
MANIFEST.json
manifest_fingerprint_resolved.json
parameter_hash_resolved.json
rng_accounting.json
s9_summary.json
index.json
```

The ASCII-lexicographic order is:

```
MANIFEST.json
egress_checksums.json
index.json
manifest_fingerprint_resolved.json
parameter_hash_resolved.json
rng_accounting.json
s9_summary.json
```

Compute `SHA256(concat(raw_bytes(files_in_order)))` → write `_passed.flag` as:

```
sha256_hex = <hex64>
```

(Flag rule per Registry/Dictionary; consumers **must verify** before reading `outlet_catalogue`.)  

## B.6 What goes into the required bundle files (recap)

* **`MANIFEST.json`** — run identity: `manifest_fingerprint`, `parameter_hash`, `git_commit_hex`, `created_utc_ns`, etc.
* **`parameter_hash_resolved.json` / `manifest_fingerprint_resolved.json`** — canonical derivations.
* **`rng_accounting.json`** — per-family event totals, draws/blocks reconciliation, **trace coverage** (one cumulative `rng_trace_log` row **after each** event append) and **audit presence**. (Layer log paths/keys and coverage rule in the Dictionary.) 
* **`s9_summary.json`** — PASS/FAIL, failure counts by **canonical `E_*` codes**, counts/membership source used.
* **`egress_checksums.json`** — per-file and composite SHA-256 for `outlet_catalogue` under `[seed, manifest_fingerprint]`. (Egress path/partitions/sort per Dictionary.) 

## B.7 Atomic publish (one-shot move)

S9 **stages** the bundle in a temp dir (e.g., `…/validation/_tmp.{uuid}`), computes `_passed.flag` **inside** the staged folder, then **renames atomically** to `manifest_fingerprint={manifest_fingerprint}/`. **No partial contents** may become visible. (S0 write semantics + S9 §§4 & 11.) 

## B.8 Consumer read sequence (at a glance)

1. Locate `validation/manifest_fingerprint={manifest_fingerprint}/`.
2. Read `_passed.flag`; recompute SHA-256 over **all files listed in `index.json` (excluding `_passed.flag`)** in ASCII-lexicographic order of the `path` entries; compare to `sha256_hex`.
3. Only on success, read `outlet_catalogue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/…` (Dictionary explicitly repeats this consumer duty). 

---

**Status:** Appendix B is **Informative**. Shape/paths and the gate rule are governed by the Dictionary/Registry and 1A schemas cited above.   

---

# Appendix C) Worked micro-examples **(Informative)**

## C.1 “Happy-path” multi-site with 2 foreigns

**Lineage (one merchant):** `seed=42`, `parameter_hash=…aa11`, `manifest_fingerprint=…bb22`, `run_id="r1"`.

**S1 (hurdle).** One event (stochastic): `draws="1"`, `blocks=1`, `u=0.43`, `is_multi=true`. Open-interval `u∈(0,1)` holds; budget identity holds.  

**S2 (NB mixture → N).** Attempts (Gamma→Poisson per attempt), then one non-consuming `nb_final{n_outlets=N=7, nb_rejections=2}` (`blocks=0`, `draws="0"`).  

**S3 (order authority).** `s3_candidate_set` for merchant `m42`:

| `candidate_rank` | `country_iso` | `is_home` |
|-----------------:|:-------------:|:---------:|
|                0 |      GB       |   true    |
|                1 |      US       |   false   |
|                2 |      DE       |   false   |

Ranks are total & contiguous; **home=0**. 

**S4 (ZTP target).** Attempt 1: `poisson_component(context="ztp", k=0)` → `ztp_rejection`. Attempt 2: `poisson_component(k=2)` → `ztp_final{K_target=2, exhausted:false}` (non-consuming). Attempts are 1-based, counters monotone. 

**S6 (selection, Gumbel keys).** Considered = `{US, DE}`; keys written in **S3 rank order**; budgets: each `gumbel_key` has `blocks=1`, `draws="1"`. Top-K (K=2) ⇒ selected `{US, DE}`. (Tie-breaks: S3 rank, then ISO.)  

**S7 (integerisation over `{home}∪selected`).** Let ephemeral weights within the domain be `{GB:0.60, US:0.25, DE:0.15}`; with `N=7` → floors `{4,1,1}`, remainder `d=1`. Quantised residuals at **dp=8**: `{0.20000000, 0.75000000, 0.05000000}`; bump goes to `US`. Final counts: `{GB:4, US:2, DE:1}`; non-consuming `residual_rank` emitted for each country.  

**S8 (egress & instrumentation).**
`outlet_catalogue` rows for each `(country, site_order=1..nᵢ)` with `site_id` `^[0-9]{6}$`. S8 emits three **non-consuming** `sequence_finalize` events:

* `sequence_finalize(m42, GB, site_count=4, start="000001", end="000004")`
* `sequence_finalize(m42, US, site_count=2, …, end="000002")`
* `sequence_finalize(m42, DE, site_count=1, …, end="000001")`  

**What S9 verifies (samples).**

* Path↔embed equality on all reads; schema conformance for egress & events. 
* RNG envelopes & budgets: per-event `after−before==blocks`; `sequence_finalize`/`residual_rank` non-consuming. One **trace** append **after each** event; final trace totals match set-sums. 
* Counts: `4+2+1 == N==7` from `nb_final`. **No cross-country order** encoded in egress; join-back to S3 gives order.  

---

## C.2 Single-country domain (A=0) — **valid degenerate**

**S3.** Candidate set contains **home only**: `NG (rank 0)`; **A=0**. 

**S4.** **Short-circuit:** write **one** non-consuming `ztp_final{K_target=0, attempts:0, exhausted:false [,reason:"no_admissible"]?}` (if the field exists in this schema version). No Poisson attempts written. 

**S6.** Skipped (domestic-only path). 

**S7.** Counts = `{NG:N}`; one `residual_rank` with residual `0.00000000`, rank `1`. Sum law holds. 

**S8.** Three egress rows if `N=3` with `site_order=1..3` and one `sequence_finalize(…, country=NG, start="000001", end="000003")`. Label `DEG_SINGLE_COUNTRY` is **informative**. 

**S9.** PASS when all other checks pass; zero-target via **A=0** is tolerated. 

---

## C.3 Shortfall: `K_target=3` but only 2 eligible

**Setup.** S3 foreigns in rank order `{FR, DE, ES, IT}`; policy includes a cap & zero-weight handling such that only `{ES, DE}` have `w>0`. 

**S4.** `ztp_final{K_target=3}` (non-consuming). 

**S6.** Considered size `A_filtered=4`; **eligible** size `|Eligible|=2`. With `log_all_candidates=true`, four `gumbel_key` events (one per considered) are written (each `blocks=1`, `draws="1"`). Realisation law:
`K_realized = min(3, 2) = 2` ⇒ selected `{ES, DE}`.  

**S7.** Integerise over `{home}∪{ES,DE}` to sum to `N` from `nb_final`; `residual_rank` persisted per country. 

**S8/S9.** Egress has only `{home, ES, DE}`; S9 proves membership from events or (if used) gated `s6_membership` and checks Σ-law to `N`. Shortfall is **tolerated** (not an error). 

---

## C.4 Overflow guardrail — **merchant-scoped abort, non-error if handled**

**Scenario.** A single country gets `n=1,000,001` (> `999,999` max).

**S8 behaviour.** Emit **non-consuming** `site_sequence_overflow{attempted_count=1000001, max_seq=999999, overflow_by=2, severity="ERROR"}` and **write no egress rows** for the merchant.  

**S9 handling.** Records the merchant in the bundle; this condition **by itself** is a **non-error** if the overflow event exists and no egress rows were written. (Policy breach—overflow without the event, or rows written anyway—would be `E_OVERFLOW_POLICY_BREACH` and fail the run.) 

---

## C.5 Zero-target via policy (“downgrade_domestic”) — **valid**

**S4.** Cap reached; policy=`"downgrade_domestic"` ⇒ emit **one** non-consuming `ztp_final{K_target=0, exhausted:true}`; **no** `ztp_retry_exhausted` is written under this policy. 

**S6.** Skipped (domestic-only path). **S7/S8** proceed as domestic-only; S9 treats this as **tolerated** (non-error) when all other checks pass. 

---

### What these examples teach the implementer (at a glance)

* **Order is S3 only.** Every display/order need joins `candidate_rank`; egress never encodes cross-country order. 
* **Facts chain:** `N` (S2) → `K_target` (S4) → membership (S6) → integer counts (S7) → sequences (S8). S9 re-derives each from written inputs only.    
* **Budgets & trace:** consuming vs non-consuming envelopes and “trace append after each event” are universal; S9 reconciles totals from the **final** trace rows. 

---
