# State 8 (S8) — Materialise outlet stubs & sequences

# 0) Document metadata & status **(Binding)**

**State ID (canonical):** `layer1.1A.S8` — “Materialise outlet stubs & sequences”
**Document type:** Contractual specification (no code, no pseudocode)
**Primary egress governed by this spec:** `outlet_catalogue` (see dictionary + schema anchors).

---

## 0.1 Versioning (SemVer) & effective date

* **Versioning scheme:** **MAJOR.MINOR.PATCH** (Semantic Versioning).
* **Initial version:** `v1.0.0` (ratified 2025-10-14).  *(File name revisions do not imply SemVer changes.)*
* **Effective date:** 2025-10-14 (release tag and commit recorded alongside this document).

### What requires a **MAJOR** bump (breaking):

* Any change to **dataset IDs**, **schema `$ref` anchors**, or **column/PK/partition** contracts for `outlet_catalogue`. 
* Any change to **partition law** or lineage fields used by S8 (e.g., switching egress partitions away from `[seed, fingerprint]`). 
* Changing **“no cross-country order in egress”** (i.e., encoding inter-country order in `outlet_catalogue`). 
* Altering **PASS-gate semantics** for 1A hand-off (validation bundle and `_passed.flag` relationship). 

### What is **MINOR** (backward-compatible):

* Adding **nullable/optional columns** to `outlet_catalogue` that do not affect PK/UK/sort/partitions. 
* Adding **new instrumentation streams** (e.g., additional guardrail events) that don’t change existing envelopes or required events. 
* Adding **informative** appendices, metrics, or validation outputs that do not alter the egress/table contract. 

### What is **PATCH** (non-behavioural):

* Editorial clarifications, typo fixes, and examples that **do not change** behaviour, schemas, paths, keys, partitions, or gates.

---

## 0.2 Normative language (RFC 2119/8174)

* Terms **MUST/SHALL/SHOULD/MAY** are normative.
* Unless explicitly labelled *Informative*, all clauses in this document are **Binding**.

---

## 0.3 Document scope & non-goals (status framing)

* This document **governs only** S8 behaviour and artefacts needed to materialise `outlet_catalogue` and its minimal instrumentation events. It **does not** define cross-country order, counts, or weights; those remain with S3/S7/S5 respectively and are referenced in later sections.
* S8 egress is **fingerprint-scoped** and partitioned `[seed, fingerprint]`; **path↔embed equality** for `manifest_fingerprint` is enforced elsewhere in this spec. 

---

## 0.4 Lifecycle & ratification record

On ratification:

* Record **semver**, **effective_date**, **ratified_by**, and the **git commit** (and optional SHA-256 of this file) in the release notes and governance registry.
* Downstream consumers (e.g., 1B) **MUST** continue to verify the 1A **validation gate** before reading `outlet_catalogue` (`_passed.flag` content hash equals `SHA256(validation_bundle_1A)` for the same fingerprint). 

---

## 0.5 Cross-references (anchors used by S8)

* **Dataset Dictionary:** `dataset_dictionary.layer1.1A.yaml` — IDs/paths/partitions for `outlet_catalogue`, S3 candidate set, validation bundle, and RNG streams.
* **JSON-Schema (authority):**
  - `schemas.1A.yaml` → `#/egress/outlet_catalogue`, `#/s3/candidate_set` (referenced later). 
  - `schemas.layer1.yaml` (RNG/core logs & event families used/observed by 1A, incl. `sequence_finalize`, `site_sequence_overflow`, `residual_rank`). 
  - `schemas.ingress.layer1.yaml` (FK targets such as `iso3166_canonical_2024`). 
For brevity, unqualified `$ref` anchors (e.g., `#/rng/events/sequence_finalize`) are resolved per §3.1 **Anchor resolution rule**.
---

## 0.6 House rules this document inherits

* **No PASS → no read**: consumers of `outlet_catalogue` must verify the 1A validation gate for the same `fingerprint`. 
* **Deterministic math & environment**: numeric environment (IEEE-754 binary64, RNE, FMA off) is inherited from Layer-1 policy and S0; S8 will not weaken those guarantees. 

---

> **Status:** This section is **Binding**. Once you mark this doc `v1.0.0` and ratify, §0 governs change control for all future edits to the S8 spec.

---

# 1) Purpose & scope **(Binding)**

## 1.1 Purpose

S8 **materialises immutable outlet stubs** for each `(merchant_id, legal_country_iso)` by writing the **`outlet_catalogue`** dataset. For every country in the merchant’s domain, S8 emits a **contiguous within-country sequence** `site_order = 1..final_country_outlet_count` and a deterministic **6-digit `site_id`** derived from that sequence. 
**Inter-country order is not encoded** in this egress; downstream MUST join S3’s `candidate_rank` when a cross-country order is required.

## 1.2 What S8 consumes (conceptual)

S8 **consumes** already-ratified facts and authorities; it does **not** derive them:

* **Counts (N and per-country integers):** `N` comes from S2 (via `nb_final` evidence), and per-country integer counts come from S7 residual-rank evidence (or `s3_integerised_counts` if S3 is designated to own integerisation).
* **Membership & domain:** the foreign membership is taken from S6 (convenience `s6_membership` if emitted, or reconstructable from S6 RNG events), joined with S3’s candidate set to align with order authority. 
* **Inter-country order authority:** **only** S3’s `s3_candidate_set.candidate_rank` (total, contiguous; `home` at rank 0).

> S8 does not require S5 weight surfaces. Weights authority remains with S5 (used upstream by S6/S7); any S5 artefact consumption elsewhere remains gated by its PASS policy.

**Single vs multi reminder.** S8 writes **only** multi-site merchants (`raw_nb_outlet_draw ≥ 2`, `single_vs_multi_flag=true`)—singles are out of scope for this egress.

## 1.3 What S8 produces

* **Primary egress:** `outlet_catalogue` at `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/` with partitions `[seed, fingerprint]`, PK/Sort `[merchant_id, legal_country_iso, site_order]`, and the column set fixed by the schema (incl. `manifest_fingerprint`, `site_order`, `site_id`). **No cross-country order is present.**
* **Instrumentation streams:**
  - `rng_event.sequence_finalize` per `(merchant,country)` block with `{site_count,start_sequence,end_sequence}` (for audit and replay accounting).
  - `rng_event.site_sequence_overflow` on overflow (guardrail → merchant-scoped failure).

## 1.4 Scope constraints (non-goals)

S8 **MUST NOT**:

* invent or encode **inter-country order** (that remains with S3), nor reinterpret S3’s `candidate_rank`.
* change `N` or re-allocate per-country counts determined upstream (S7/S3). 
* read or persist S5 weights, or create any new weights/order surface. 
* weaken lineage/partition law or introduce side-channel ordering via file layout (PK/sort keys are normative; readers MUST NOT rely on file order). 

## 1.5 Consumers & gating

* **No PASS → no read:** Consumers (e.g., 1B) **MUST** verify the 1A validation gate for the same `fingerprint` (`_passed.flag` content hash equals `SHA256(validation_bundle_1A)`) **before** reading `outlet_catalogue`. 
* S8 itself is **fingerprint-scoped** egress; all path tokens MUST match embedded lineage where present (defined later in lineage law). 

## 1.6 Success criteria (outcome statement)

On successful completion for a `fingerprint`, S8 yields:

1. a byte-stable `outlet_catalogue` partition with contiguous per-country `site_order` (and 6-digit `site_id`) for every `(merchant, legal_country_iso)` where `final_country_outlet_count ≥ 1`;
2. complete `sequence_finalize` coverage for those blocks; and 
3. no violation of the inter-country order boundary (all cross-country ordering recoverable by joining S3 `candidate_rank`).

**Status:** This section is **Binding**.

---

# 2) Definitions & notation **(Binding)**

This section freezes the vocabulary, symbols, and lineage tokens S8 uses. All terms below are **normative**.

## 2.1 Lineage & partition tokens

* **`seed`** — 64-bit unsigned master RNG seed; partitions **RNG logs/events** and appears in their paths. 
* **`parameter_hash`** — **lowercase hex64** (SHA-256) of the opened parameter bundle; partitions **parameter-scoped tables** and RNG logs/events; where embedded, bytes **MUST** equal the path token.
* **`run_id`** — run-scoped identifier (**lowercase hex 32-character string**) for RNG event/log partitions (as per layer schema `$defs.run_id`).  
* **`manifest_fingerprint`** (a.k.a. **`fingerprint`** in paths) — **lowercase hex64** lineage digest for the whole 1A run; it **partitions S8 egress** and is also stored per row in `outlet_catalogue` as `manifest_fingerprint`. **Naming rule:** any `fingerprint={…}` path segment carries the value of `manifest_fingerprint`.

## 2.2 Entities & keys

* **`merchant_id`** — 64-bit ID for a merchant (`$ref: #/$defs/id64`). Appears in S3 and S8 schemas. 
* **`home_country_iso`** — ISO-3166-1 alpha-2 code for the onboarding/home country (FK → canonical ISO registry). 
* **`legal_country_iso` / `country_iso`** — ISO-3166-1 alpha-2 code for the country a site or candidate belongs to (FK → canonical ISO registry). 
* **`candidate_rank`** — **sole authority** for inter-country order from S3; **total and contiguous** per merchant with **`candidate_rank(home)=0`**. 
* **Domain `Dₘ`** — the per-merchant legal set used by S8: `{home_country_iso} ∪ (S6-selected foreign ISO2s)`, aligned to S3’s candidate set. (`s6_membership` is convenience-only; S6 RNG events are authoritative for reconstruction.)

## 2.3 Upstream facts S8 treats as read-only

* **Domestic outlet count `N`** — the accepted Negative-Binomial draw **per merchant** from **`rng_event.nb_final`** (`n_outlets ≥ 2`, **non-consuming** event). Denoted `Nₘ`. 
* **Foreign target count `K_target`** — the S4 single-acceptance outcome from **`rng_event.ztp_final`** (non-consuming); consumed by S6. Denoted `Kₘ^*`.
* **Integer per-country counts** — from **S7 residual evidence** (`rng_event.residual_rank`) or, if designated, S3’s deterministic **`s3_integerised_counts`** (parameter-scoped).

## 2.4 S8 egress: `outlet_catalogue` column terms (all **Binding**)

* **Primary key (PK)** — `[merchant_id, legal_country_iso, site_order]`. **Unique key equals PK.** Sort keys are identical. Partition keys: `[seed, fingerprint]`. 
* **`manifest_fingerprint`** — per-row **lowercase hex64** equal to the egress `fingerprint` path token (lineage equality).
* **`site_order`** — **within-country** contiguous sequence `1..nᵢ` for each `(merchant_id, legal_country_iso)` block (**no gaps**). 
* **`site_id`** — **mandatory** 6-digit zero-padded string for the within-country sequence (`^[0-9]{6}$`). It encodes **only** the local sequence, not global order. 
* **`single_vs_multi_flag`** — boolean copy of the S1 hurdle decision at merchant level (1 if multi-site). 
* **`raw_nb_outlet_draw`** — the accepted S2 domestic draw `N` prior to cross-border allocation (`≥ 2`). 
* **`final_country_outlet_count`** — integer outlets allocated to this `legal_country_iso` (`≥ 1`, `≤ 999,999`). Sum over a merchant’s legal set equals `N`. 
* **`global_seed`** — 64-bit master seed persisted for audit/replay parity. 

> **Scope note:** `outlet_catalogue` **does not encode inter-country order**; consumers **MUST** join S3’s `candidate_rank` when a cross-country order is required. 

## 2.5 RNG events & logs S8 observes/emits (schema-anchored names)

* **Core logs (read-only by validators):**
  **`rng_audit_log`** (run-scoped audit) and **`rng_trace_log`** (cumulative counters; **append exactly one** trace row after **each** RNG event append). Partitions `{seed, parameter_hash, run_id}`. 
* **Upstream evidence consumed by S8 validators:**
  **`rng_event.nb_final`** (defines `N`), **`rng_event.residual_rank`** (S7 residual ordering evidence),
  **`rng_event.gumbel_key`** **and** **`rng_event.ztp_final`** (S6 membership reconstruction when needed).
* **S8 instrumentation (emitted by S8):**
  **`rng_event.sequence_finalize`** — per `(merchant_id, country_iso)` block: `{site_count, start_sequence, end_sequence}`; partitions `{seed, parameter_hash, run_id}`.
  **`rng_event.site_sequence_overflow`** — guardrail event on sequence exhaustion.

## 2.6 Sets, symbols & equalities (notation used later)

* **`zfill6(x)`** — left-pad integer `x` with ASCII `'0'` to 6 digits (e.g., `1→"000001"`).
* **`Dₘ`** — merchant’s legal domain set for S8 (home + selected foreigns; aligned to S3). **Cardinality:** `|Dₘ| = 1 + |S6_selected|`. 
* **`Nₘ`** — merchant-level domestic outlets from `nb_final.n_outlets`. **Invariant later (§9):** `Σ_{c∈Dₘ} nₘ,c = Nₘ`. 
* **`nₘ,c`** — per-country final integer count in `outlet_catalogue.final_country_outlet_count` for merchant `m` and country `c`. 
* **`site_order` sequence** — for each `(m,c)`, the ordered list `⟨1,…,nₘ,c⟩`. `site_id` is the 6-digit rendering of this sequence. 
* **Path↔embed equality** — whenever lineage columns are embedded: egress `manifest_fingerprint` **MUST** equal the `fingerprint` path token; event rows **MUST** embed `{seed, parameter_hash, run_id, manifest_fingerprint}` where `{seed, parameter_hash, run_id}` **MUST** equal their path tokens and `manifest_fingerprint` **MUST** equal the run’s egress fingerprint (not a path token).

## 2.7 Consumption gates (terms used throughout)

* **S6 PASS** — the S6 validation receipt folder whose `_passed.flag` content hash equals `SHA256(S6_VALIDATION.json)` for the same `{seed, parameter_hash}`; required before reading S6 convenience surfaces.
* **1A PASS (hand-off to 1B)** — the `validation_bundle_1A` at `…/validation/fingerprint={manifest_fingerprint}/`; consumers must verify `_passed.flag` content hash equals `SHA256(bundle)` before reading `outlet_catalogue`.

**Status:** All terms above are **Binding** and will be used verbatim in §§3–13.

---

# 3) Authority & precedence **(Binding)**

## 3.1 Precedence chain (normative)

**Anchor resolution rule (normative).** When a `$ref` omits the document prefix:
- `#/rng/**` resolves to `schemas.layer1.yaml`.
- `#/validation/validation_bundle` resolves to `schemas.1A.yaml`; `#/validation/s6_receipt` resolves to `schemas.layer1.yaml`.
- `#/s3/**` and `#/egress/**` resolve to `schemas.1A.yaml`.
- `#/iso**` and other ingress FK anchors resolve to `schemas.ingress.layer1.yaml`.

1. **JSON-Schema is the single schema authority** for all S8 inputs/outputs/logs: `schemas.1A.yaml`, `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`. **Avro (if any) is non-authoritative.**
2. The **Dataset Dictionary** (`dataset_dictionary.layer1.1A.yaml`) governs **dataset IDs, physical path templates, partitions, writer sort, PK/FK, lifecycle and retention**. 
3. **This S8 spec** defines the **behavioural rules** under (1) and (2). (Pattern established in S7/S6 carries forward unchanged.)

> If a dictionary entry and a schema disagree on **shape or typing**, the **schema wins** (dictionary must be fixed). If an implementation uses literal paths, it is non-conformant—**all IO resolves via the dictionary**. 

## 3.2 What each authority decides (scope partitioning)

* **JSON-Schema (source of truth):** row/record **shape**, field domains & types, **PK/UK** definitions, event envelope fields, and required lineage columns.
* **Dataset Dictionary:** dataset **IDs → schema `$ref`**, **partition keys** (e.g., `[seed, fingerprint]` for S8 egress; `[parameter_hash]` for parameter-scoped inputs), **writer sort**, and **consumer gates** text. 
* **This S8 spec:** behavioural rules (e.g., “within-country sequencing only”), **prohibitions**, invariants, error/degrade ladder, and **PASS-gate** expectations. 

## 3.3 Fixed upstream authorities S8 MUST honour

* **Inter-country order authority:** **only** S3 `s3_candidate_set.candidate_rank` (total, contiguous; `home=0`). S8 **MUST NOT** encode or alter cross-country order; consumers **MUST** join S3 when order is required.
* **Counts authority:** merchant-level `N` from **`rng_event.nb_final`** (S2, non-consuming) and **per-country integer counts** from S7 residual evidence (or `s3_integerised_counts` if S3 owns it). S8 **MUST NOT** re-derive either.
* **Gating principle:** **No PASS → no read** remains in force for 1A consumers; the dictionary’s `outlet_catalogue` entry encodes this gate for 1B.

## 3.4 Prohibitions & legacy notes (binding)

* **Avro `.avsc`** files (if generated) are **non-authoritative** and **MUST NOT** be referenced by registry/dictionary entries. 
* **Legacy `country_set`** is **not** an order authority; using it for cross-country order is non-conformant. 
* **File order is non-authoritative** (RNG/event streams use counters & envelopes; tables rely on PK/sort defined in the dictionary). 

**Status:** Section 3 is **Binding**.

---

# 4) Compatibility window & numeric environment **(Binding)**

## 4.1 Baselines S8 binds to (v1.* line)

S8 v1.* is compatible with—and **assumes**—the following authorities remain on their **v1.* line**; a **MAJOR** bump in any requires S8 re-ratification and a SemVer **MAJOR** increment for this spec:

* **Layer-wide RNG/log schemas:** `schemas.layer1.yaml v1.0`. 
* **1A tables & egress schemas:** `schemas.1A.yaml v1.0`. 
* **Ingress/reference schemas:** `schemas.ingress.layer1.yaml v1.0`. 
* **Dataset Dictionary:** `dataset_dictionary.layer1.1A.yaml` (IDs, path templates, partitions, writer sort). 

## 4.2 Lineage interaction with compatibility (fingerprints vs parameter scope)

* **`parameter_hash`** flips when **any governed parameter bytes** change (policy/config members of 𝓟). **`manifest_fingerprint`** flips when **any opened artefact** (schemas, dictionary, ISO, governance files) or the **code commit** changes. These keys are **orthogonal** to SemVer and govern partitions and reproducibility for S8. 
* The **manifest** explicitly **includes** the pinned **numeric policy** and **math profile manifest**, so changing either will change the **`manifest_fingerprint`** for the run. 

## 4.3 Numeric environment (must hold for S8)

S8 **inherits** the Layer-1 numeric environment; producers and validators **MUST** attest it before publishing S8 egress:

* **Policy pins (governance):**
  - **Rounding:** **RNE** (round-to-nearest, ties-to-even)
  - **FMA:** **off**
  - **FTZ/DAZ:** **off** (no flush-to-zero, no denormals-are-zero)
  - **Subnormals:** **preserved**
  These are defined in `schemas.layer1.yaml#/governance.numeric_policy_profile` and pinned in the Artefact Registry as `numeric_policy_profile`.
* **Math library profile (deterministic libm):** function set/signatures are frozen via `math_profile_manifest` and participate in the manifest fingerprint.
* **Attestation artefact:** S0 writes `numeric_policy_attest.json` into the fingerprinted validation bundle; fields include `rounding_ok`, `fma_off_ok`, `subnormals_ok`, `libm_regression_ok`, `neumaier_ok`, `total_order_ok`, `passed`. S8 **MUST** run only under a fingerprint where this attestation **passed**.

> **Note:** S8’s egress (`outlet_catalogue`) is integer/string-typed; however, S8 **still** relies on this environment for deterministic validation and any numeric checks performed during sequencing and logging. 

## 4.4 S8 numeric constants & identifier limits (binding)

* **Six-digit sequence tokens:** any within-country sequence values exposed in events use the `$defs.six_digit_seq` pattern `^[0-9]{6}$`. 
* **Overflow guardrail:** if a per-country allocation would exceed the 6-digit ceiling, producers **MUST** emit `rng_event.site_sequence_overflow` with `{attempted_count, max_seq=999999, overflow_by}` and **fail the merchant**. 
* **Sequence finalize event:** per `(merchant_id,country_iso)` block, `rng_event.sequence_finalize` records `{site_count, start_sequence, end_sequence}` using `six_digit_seq`. 

## 4.5 Evolution rules (numeric/compatibility changes)

* **MAJOR (re-ratify S8):** changing any field/domain in `numeric_policy_profile` (e.g., enabling FMA), altering `six_digit_seq` width/range, or changing the required fields/semantics of `sequence_finalize` / `site_sequence_overflow`.
* **MINOR (backward-compatible):** adding optional **attestation** fields, or **diagnostic** event payload members that do not affect required fields or envelopes; updating `math_profile_manifest` contents **with** a fresh attestation (this flips `manifest_fingerprint` but does not break readers).

**Status:** Section 4 is **Binding**.

---

# 5) Identity, lineage & partition law **(Binding)**

This section fixes **what keys partition which artefacts**, how **path tokens must equal embedded lineage**, and the **atomic publish/idempotence** rules. All clauses here are **normative**.

## 5.1 Canonical partitions & paths (by artefact class)

**Egress (S8 output).**
`outlet_catalogue` is **fingerprint-scoped** under
`data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/` with partitions `[seed, fingerprint]` and writer sort `[merchant_id, legal_country_iso, site_order]`. Schema anchor: `schemas.1A.yaml#/egress/outlet_catalogue`.

**Parameter-scoped inputs (RNG-free; upstream).**
Examples: `s3_candidate_set`, `s3_integerised_counts`, `s3_site_sequence` when present. These live under `…/parameter_hash={parameter_hash}/` (partition `[parameter_hash]`). Schema anchors: `schemas.1A.yaml#/s3/*`.

**RNG core logs & events (read by validators / instrumentation).**
All RNG JSONL streams (e.g., `rng_audit_log`, `rng_trace_log`, `rng_event.*` including `sequence_finalize`, `site_sequence_overflow`) are partitioned by `{seed, parameter_hash, run_id}` with canonical paths like
`logs/rng/<stream>/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`. Envelope fields are governed by `schemas.layer1.yaml` and **required** on every event row.

**Validation bundle & hand-off gate.**
The 1A validation bundle is **fingerprint-scoped** at
`data/layer1/1A/validation/fingerprint={manifest_fingerprint}/` and supplies the `_passed.flag` that gates 1B consumption.

## 5.2 Path↔embed equality (must hold)

**Egress rows.** `outlet_catalogue.manifest_fingerprint` **MUST byte-equal** the `fingerprint` path token for the same partition, and `global_seed` **MUST** equal the `seed` path token. **Pattern (for `manifest_fingerprint`):** `^[a-f0-9]{64}$`.

**Parameter-scoped tables.** Each row **MUST** embed `parameter_hash` and it **MUST equal** the `parameter_hash` path token. If present, `produced_by_fingerprint` is **informational only** (not a partition key nor part of equality).

**RNG logs/events.** Event rows **MUST** embed `{seed, parameter_hash, run_id, manifest_fingerprint}`. `{seed, parameter_hash, run_id}` **MUST** match their path tokens **byte-for-byte**. `manifest_fingerprint` **MUST** equal the run’s egress fingerprint (it is **not** a path token).

## 5.3 Identity, immutability & atomic publish

**Identity of a partition.** *(“fingerprint” path token equals `manifest_fingerprint` column value.)*

* Egress: `(dataset='outlet_catalogue', seed, manifest_fingerprint)`.
* Parameter-scoped: `(dataset_id, parameter_hash)`.
* RNG streams: `(stream_name, seed, parameter_hash, run_id)`.
  Publishing to an existing identity **MUST** result in **byte-identical content** or be a no-op. 

**Atomicity.** Producers **MUST** stage to a temp path, fsync, then perform a single **atomic rename** into the dictionary path. **No partial contents** may become visible.

**Immutability & idempotence.** A published partition is **immutable**; re-runs with identical inputs, numeric policy, and lineage **MUST** yield **bit-identical** outputs for egress and **value-identical** rows for streams (byte-identity if a writer policy is pinned). **File order is non-authoritative.**

## 5.4 Key formats & allowed values (schema-anchored)

* `seed` is `uint64`. `run_id` is **lowercase hex32**. `parameter_hash` and `manifest_fingerprint` are **lowercase hex64**. These formats are enforced in `schemas.layer1.yaml` `$defs`. 
* `site_id` follows `^[0-9]{6}$` and is **not** a partition key. 

## 5.5 Writer sort & non-authoritative physical order

* Egress writer sort is `[merchant_id, legal_country_iso, site_order]` as per **Dataset Dictionary**/**Schema**; readers **MUST NOT** rely on file order beyond these keys.
* RNG JSONL **row order across files is non-semantic**; equality is by **row set**. Within a file, line order reflects append order only. 

## 5.6 Multi-run semantics (logs)

`run_id` partitions **logs only** and does **not** alter modelling state/outcomes; multiple `run_id`s may coexist for the same `{seed, parameter_hash}` without changing dataset semantics. 

## 5.7 Receipt & gate placement (lineage consequences)

* Egress is **fingerprint-scoped** and consumed **only after** verifying the validation bundle `_passed.flag` for the **same** fingerprint (content hash equals `SHA256(bundle)`). 
* S8 MUST verify **upstream gates** before reading convenience surfaces (e.g., **S6 PASS** if reading `s6_membership`). Gate locations and partitions are defined in the dictionary. 

## 5.8 Retention & ownership (for completeness)

Retention periods and producer/consumer ownership are normative in the **Dataset Dictionary** and **Artefact Registry** (e.g., RNG events typically 180 days; core logs 365 days); S8 producers **MUST** respect these policies when publishing.

**Status:** Section 5 is **Binding**.

---

# 6) Read set & pre-read gates **(Binding)**

This section freezes **exactly what S8 is allowed to read** (IDs → schema anchors → partitions), and the **gates** S8 MUST verify *before* reading any convenience surface. All items below are **normative**.

## 6.1 Required inputs (IDs → `$ref` → partitions)

* **Inter-country order & domain (sole authority):**
  **`s3_candidate_set`** → `schemas.1A.yaml#/s3/candidate_set` → **partition:** `parameter_hash={…}`.
  *Guarantees:* total & contiguous `candidate_rank` per merchant; `candidate_rank(home)=0`; embedded `parameter_hash` equals path key (path↔embed equality). S8 MUST use this for **all** cross-country ordering.

* **Domestic count (fact `N` for each merchant):**
  **`rng_event.nb_final`** → `schemas.layer1.yaml#/rng/events/nb_final` → **partition:** `{seed, parameter_hash, run_id}`; **exactly one** per resolved merchant; **non-consuming** envelope. S8 uses `n_outlets` to populate `raw_nb_outlet_draw` and for sum checks.

* **Per-country integer counts (authority for `final_country_outlet_count`):**
  **Variant A (preferred, if present):** **`s3_integerised_counts`** → `schemas.1A.yaml#/s3/integerised_counts` → **partition:** `parameter_hash={…}`. Contains `{merchant_id,country_iso,count,residual_rank}`; S8 MUST read this when it exists. 
  **Variant B (no S3 counts surface):** counts flow *in-process* from S7 into S8; S8 MUST NOT reconstruct counts from weights. (Validators will re-derive independently; see §11.) The deprecated `ranking_residual_cache_1A` is **not** an authority.

* **Membership of foreigns (domain members beyond home):**
  **Option 1 (convenience surface):** **`s6_membership`** → `schemas.1A.yaml#/s6/membership` → **partition:** `seed={seed}, parameter_hash={parameter_hash}`. **Gate required** (see §6.3). Order still comes from S3. 
  **Option 2 (authoritative log reconstruction):** **`rng_event.gumbel_key`** → `schemas.layer1.yaml#/rng/events/gumbel_key` and **`rng_event.ztp_final`** → `schemas.layer1.yaml#/rng/events/ztp_final` → **partition:** `{seed, parameter_hash, run_id}`. Use keys + `K_target` to recover membership when `s6_membership` is absent. 

> **FK sources** are enforced by schema on egress (ISO2); S8 needn’t read ISO directly. (FK target: `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`.) 

## 6.2 Conditional/variant inputs (read only if present)

* **If sequencing is owned upstream:** **`s3_site_sequence`** → `schemas.1A.yaml#/s3/site_sequence` → `parameter_hash={…}`. When present, S8 **cross-checks** it but still writes `outlet_catalogue`; S8 **MUST NOT** change sequence semantics. 

## 6.3 Pre-read gates S8 MUST enforce

* **S6 gate (for any S6 convenience surface):** If reading **`s6_membership`**, verify the **S6 PASS receipt** at
  `data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/` where `_passed.flag` content hash equals `SHA256(S6_VALIDATION.json)` for the **same** `{seed,parameter_hash}`. **No PASS → no read.**

* **S5 gate:** S8 does **not** require S5 surfaces. If any implementation chooses to *touch* S5 artefacts, S8 MUST verify the **S5 parameter-scoped PASS** first. (By spec, S8 SHOULD NOT read S5.) 

* **Path↔embed lineage equality:** For every read where lineage columns are embedded, bytes **must equal** the path tokens (e.g., `parameter_hash` on S3 datasets; `{seed,parameter_hash,run_id}` on RNG events). 

## 6.4 Input validity checklist (fail-fast; MUST pass before any write)

Per merchant, S8 SHALL assert:

1. **S3 candidate set** present and schema-valid; `candidate_rank` is total, contiguous; exactly one `home` with rank `0`. 
2. **`nb_final`** present (exactly one per merchant) and schema-valid. 
3. **Counts source available:** either `s3_integerised_counts` present (schema-valid) **or** an in-process counts handoff from S7 is active; **never** reconstruct from weights in S8. Deprecated `ranking_residual_cache_1A` MUST NOT be read.
4. **Membership resolved:** EITHER `s6_membership` is present **and** S6 PASS is verified, OR `gumbel_key` **and** `ztp_final` events exist to reconstruct; otherwise **abort** with `E_PASS_GATE_MISSING` (if S6 PASS missing) or `E_COUNTS_SOURCE_MISSING` (if counts source missing).
5. **Lineage parity:** all embeds equal their path partitions (S3 tables, RNG events). 

## 6.5 Prohibitions (read side)

* S8 MUST NOT read **S5 weight surfaces** to derive counts or order; S5 remains weights authority for S6/S7 only. 
* S8 MUST NOT use legacy **`country_set`** as an order authority; use S3 `candidate_rank` only. 

**Status:** Section 6 is **Binding**.

---

# 7) Write set & contracts **(Binding)**

This section fixes **exactly what S8 writes**, with schema anchors, partitions, PK/sort, column domains, and the **only** instrumentation events S8 emits.

---

## 7.1 Primary egress — `outlet_catalogue` (immutable)

**Dataset ID & schema.** `outlet_catalogue` → `schemas.1A.yaml#/egress/outlet_catalogue`. 

**Path & partitions.** `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/` with partitions `[seed, fingerprint]`. **Writer sort** `[merchant_id, legal_country_iso, site_order]`. **No cross-country order is encoded** in this table. 

**Keys.** **PK** = **UK** = `[merchant_id, legal_country_iso, site_order]`. Rows are immutable within a `(seed,fingerprint)` partition. 

**Lineage column.** `manifest_fingerprint` **MUST** be a lowercase hex64 and **MUST byte-equal** the `fingerprint` path token for the partition. 

**Inter-country order boundary (binding).** Consumers that need cross-country order **MUST** join S3 `s3_candidate_set.candidate_rank` (home rank = 0). `outlet_catalogue` **MUST NOT** encode that order. 

---

## 7.2 Column contract (types, domains, FK)

S8 **MUST** write exactly the columns below with the stated domains:

* `manifest_fingerprint` — `string`, pattern `^[a-f0-9]{64}$` (**equals** partition `fingerprint`). 
* `merchant_id` — `$ref: #/$defs/id64`, non-null. 
* `site_id` — `string` (non-null), **6-digit zero-padded** per-(merchant, `legal_country_iso`) sequence, pattern `^[0-9]{6}$`.
* `home_country_iso` — `$ref: #/$defs/iso2`, FK → `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`. 
* `legal_country_iso` — `$ref: #/$defs/iso2`, FK → `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`. 
* `single_vs_multi_flag` — `boolean` (copy of S1 hurdle outcome). 
* `raw_nb_outlet_draw` — `int32`, **minimum 2** (accepted NB draw `N` before cross-border allocation). 
* `final_country_outlet_count` — `int32`, **1..999,999** (integer outlets allocated to this `legal_country_iso`). 
* `site_order` — `int32`, **minimum 1**, contiguous `1..nᵢ` per `(merchant_id, legal_country_iso)` block. 
* `global_seed` — `$ref: #/$defs/uint64` (master seed retained for audit/replay). 

**Dictionary echo (normative).** The Dataset Dictionary restates the path, partitions, ordering, schema `$ref`, and the **“no cross-country order”** note; 1B consumption is **gated** by the validation bundle for the same fingerprint. 

---

## 7.3 Instrumentation events S8 emits (logs)

S8 emits exactly two **rng_event** families, both partitioned at
`logs/rng/events/<family>/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` and validated by `schemas.layer1.yaml`. Gating in the Dictionary ties them to multi-site merchants. 

1. **`rng_event.sequence_finalize`** — final sequence allocation per `(merchant, country)` block.
   **Schema anchor:** `schemas.layer1.yaml#/rng/events/sequence_finalize` (required fields: `merchant_id, country_iso, site_count, start_sequence, end_sequence`). 
   **Dictionary entry & path pattern:** as above; gated by hurdle `is_multi==true`. 

2. **`rng_event.site_sequence_overflow`** — guardrail event when 6-digit sequence space would be exceeded; **severity = ERROR**; producer must abort the merchant.
   **Schema anchor:** `schemas.layer1.yaml#/rng/events/site_sequence_overflow` (required fields: `merchant_id, country_iso, attempted_count, max_seq=999999, overflow_by, severity`). 
   **Dictionary entry & path pattern:** as above. 

**Gating (both families).** Emitted **only** for merchants where the hurdle outcome is `is_multi == true` (as pinned in the Dataset Dictionary gating for S8 streams).

**Trace duty (binding).** After **each** event append above, emit **exactly one** cumulative row to `rng_trace_log` for the corresponding `(module, substream_label)`; partitions `{seed, parameter_hash, run_id}`; schema `schemas.layer1.yaml#/rng/core/rng_trace_log`. 

---

## 7.4 Lineage embedding & equality (write-time checks)

* **Egress rows:** `outlet_catalogue.manifest_fingerprint` **MUST equal** the `fingerprint` path token (hex64).
* **Events:** every event row **MUST** embed `{seed, parameter_hash, run_id, manifest_fingerprint}`. `{seed, parameter_hash, run_id}` **MUST** equal their path tokens; `manifest_fingerprint` **MUST** equal the egress fingerprint for this run. 

---

## 7.5 Physical format, writer sort & immutability

* `outlet_catalogue` **format:** Parquet; **writer sort:** `[merchant_id, legal_country_iso, site_order]`; partitioned `[seed, fingerprint]`; immutable once published. 
* **Event files:** JSONL; reader semantics are **set-based** (row order non-authoritative). Trace/audit logs use the core RNG schemas. 
* **Compression policy:** if the registry pins codecs/levels (e.g., ZSTD level 3), producers **MUST** adhere; otherwise value-identity suffices. (Outlet entry notes storage policy and gate.) 

---

## 7.6 Prohibitions & scope limits (write side)

* S8 **MUST NOT** write any artefact that **implies or encodes** inter-country order; consumers **MUST** obtain order from S3 `candidate_rank`. 
* S8 **MUST NOT** derive counts from weights or re-allocate across countries; `final_country_outlet_count` is an upstream fact (S7/S3). (Validators will cross-check in §11.) 

---

## 7.7 Consumer gate (egress)

While the **validator/PASS rules** are formalised in §11, the Dictionary **already** states the consumption gate: consumers (e.g., 1B) **MUST** verify that `_passed.flag` content hash equals `SHA256(validation_bundle_1A)` for the **same** fingerprint before reading `outlet_catalogue`. 

**Status:** Section 7 is **Binding**.

---

# 8) Behavioural rules — materialisation & authority boundaries **(Binding)**

This section fixes **how S8 behaves** when turning upstream facts into the immutable **`outlet_catalogue`** and what S8 is **forbidden** to do. All items are **normative**.

---

## 8.1 Domain & row emission (what becomes rows)

* **Domain source.** S8’s per-merchant legal domain is the **S3 candidate set** (`s3_candidate_set`) — the only authority for cross-country membership and order (home has `candidate_rank=0`).
* **Counts authority.** For each `(merchant_id, legal_country_iso)`, the integer count **`nᵢ`** comes from **S7 residual evidence** (or **`s3_integerised_counts`** if S3 owns it). S8 **MUST NOT** re-derive counts from weights or any other surface.
* **Emission rule.** S8 **emits rows only for countries with `nᵢ ≥ 1`**. If `nᵢ == 0`, S8 emits **no rows** for that `(merchant,country)`. 
* **Multi-site scope.** `outlet_catalogue.raw_nb_outlet_draw` is defined with **minimum 2**; therefore **S8 writes only multi-site merchants** (`is_multi==true`). Singles are out of scope for this egress. 

---

## 8.2 Within-country sequencing (what S8 constructs)

* **Contiguous local order.** For each `(merchant_id, legal_country_iso)` with `nᵢ≥1`, S8 **MUST** produce a contiguous **`site_order = 1..nᵢ`** (no gaps, no duplicates). 
* **Deterministic `site_id`.** S8 **MUST** render `site_id = "{site_order:06d}"` (zero-padded 6-digit string; e.g., `1→"000001"`, `42→"000042"`). `site_id` uniqueness is **scoped to `(merchant_id, legal_country_iso)`**. 
* **No cross-country order.** S8 **MUST NOT** encode any inter-country order in `outlet_catalogue`. Consumers that need cross-country order **MUST** join S3 `candidate_rank`.

---

## 8.3 Instrumentation events (what S8 logs)

* **Finalize per block.** After materialising the rows for a `(merchant, country)` block with `nᵢ≥1`, S8 **MUST** append exactly one **`rng_event.sequence_finalize`** with
  `site_count = nᵢ`, `start_sequence = "000001"`, `end_sequence = "{nᵢ:06d}"`. Event partitions `{seed, parameter_hash, run_id}`; schema `#/rng/events/sequence_finalize`.
* **Overflow guardrail.** If `nᵢ > 999999`, S8 **MUST** emit **`rng_event.site_sequence_overflow`** (`attempted_count=nᵢ`, `max_seq=999999`, `overflow_by=nᵢ−999999`, `severity="ERROR"`) and **fail the merchant** (no egress rows for that merchant). 
* **Non-consuming law.** Both events above are **non-consuming** RNG events: **`before==after`, `blocks=0`, `draws="0"`** (envelope identity). **After each event append,** S8 **MUST** append **exactly one** cumulative row to `rng_trace_log`. 
* **Gating.** S8’s event families are **present iff** the merchant is multi-site (`is_multi==true`) as encoded in the dictionary **gating** for those streams. 

---

## 8.4 Egress row content (how values are filled)

For each persisted row in `outlet_catalogue`:

* `manifest_fingerprint` **MUST** equal the partition `fingerprint` (**hex64**).
* `raw_nb_outlet_draw` **MUST** copy S2’s **`nb_final.n_outlets (N ≥ 2)`** for the merchant (same value on all rows for that merchant). 
* `final_country_outlet_count` equals `nᵢ` for that `(merchant, legal_country_iso)`; **per-merchant sum** `Σᵢ nᵢ = N`. 
* `global_seed` **MUST** equal the run’s master `seed` (uint64). 

---

## 8.5 Authority boundaries (what S8 must respect)

* **Order authority.** **Only** S3 `candidate_rank` may define cross-country order; S8 **MUST NOT** invent, persist, or imply any inter-country order. 
* **Counts authority.** S8 **MUST** treat per-country integer counts as **read-only facts** (S7 / `s3_integerised_counts`). **No renormalisation, no rounding, no re-allocation** in S8.
* **Weights authority.** S8 **MUST NOT** read or persist any weights surface for sequencing; S5 remains weights authority for S6/S7 only. 
* **Legacy surfaces.** `country_set` and any legacy RNG-dependent ranking surfaces are **not** order authorities; S8 **MUST NOT** consult them for order. 

---

## 8.6 Cross-checks S8 must perform before writing (behavioural)

* **Lineage parity.** For all inputs used, **embedded lineage bytes equal path tokens** (`parameter_hash` on S3 tables; `{seed,parameter_hash,run_id}` on RNG events). **Mismatch ⇒ abort.** 
* **S3 membership.** For each `(merchant, country)` with `nᵢ≥1`, confirm that `country` exists in that merchant’s `s3_candidate_set`. **Not in S3 ⇒ abort.** 
* **S6 gate (if used).** If S8 reads `s6_membership`, verify the **S6 PASS** receipt for the same `{seed,parameter_hash}` **before** use. **No PASS ⇒ no read.** 
* **Optional S3 cross-sequence.** If `s3_site_sequence` exists, S8 **MUST** cross-check contiguity/width (1..`nᵢ`) and (if present there) the 6-digit `site_id` format; any divergence is a **hard failure** (`E_SEQUENCE_DIVERGENCE`). S8 **MUST NOT** rewrite S3’s semantics. 

---

## 8.7 Prohibitions (hard “MUST NOT”)

* **No re-computation** of `N`, `nᵢ`, or S3/S6 membership from weights or heuristics. 
* **No cross-country ordering** in `outlet_catalogue` (only within-country `site_order`). 
* **No extra event families** beyond `sequence_finalize` and `site_sequence_overflow` for S8. 
* **No reliance on file order.** Physical file order is non-authoritative; PK/sort keys govern. 

---

## 8.8 Outcomes (deterministic, non-error cases)

S8 recognizes the following **valid** outcomes (still enforcing all invariants in §9):

* **`DEG_SINGLE_COUNTRY`** — Domain contains only home; S8 materialises `n_home=N`, others zero; still emits `sequence_finalize` for home. 
* **`DEG_ZERO_REMAINDER`** — All integer counts are exact floors; `site_order` remains contiguous; instrumentation still emitted. 

---

## 8.9 Publication discipline (write step coupling)

* **Atomicity & idempotence.** After all `(merchant,country)` blocks pass, publish `outlet_catalogue` once under `seed={seed}/fingerprint={manifest_fingerprint}`; content is **immutable** and **byte-stable** for identical inputs/lineage. 
* **Gate reminder.** Downstream (e.g., 1B) **MUST** verify that `_passed.flag` content hash equals `SHA256(validation_bundle_1A)` for the **same fingerprint** before reading `outlet_catalogue`. 

**Status:** Section 8 is **Binding**.

---

# 9) Invariants & integrity constraints **(Binding)**

All clauses below are **normative** and MUST hold for every `(seed,fingerprint)` partition of **`outlet_catalogue`** and its paired S8 instrumentation streams.

---

## 9.1 Row shape, keys, and FK integrity

* **PK/UK law.** Rows in `outlet_catalogue` are **unique** on `[merchant_id, legal_country_iso, site_order]`; writer sort is the same tuple. 
* **Contiguous local order.** For each `(merchant_id, legal_country_iso)` with rows, `site_order` is **exactly** the set `{1,…, final_country_outlet_count}` (no gaps/dupes). 
* **`site_id` bijection.** Within each `(merchant_id, legal_country_iso)` block, `site_id == zfill6(site_order)` and is **unique** in that block; regex `^[0-9]{6}$`. 
* **ISO FKs.** `home_country_iso` and `legal_country_iso` are valid ISO-3166-1 alpha-2 codes (FK to canonical registry). 

---

## 9.2 Lineage equality & immutability

* **Path↔embed equality (egress).** Every row’s `manifest_fingerprint` **MUST** byte-equal the egress path token `fingerprint` (hex64), and `global_seed` **MUST** equal the egress path token `seed`. **Rows are immutable** within a `(seed,fingerprint)` partition.
* **Path↔embed equality (events).** Every S8 event row embeds `{seed, parameter_hash, run_id, manifest_fingerprint}`; `{seed, parameter_hash, run_id}` **MUST** equal their path tokens and `manifest_fingerprint` **MUST** equal the validation fingerprint for this bundle; envelope fields (`blocks`, `draws`) obey the family budgets in the layer schema.

---

## 9.3 Cross-state equalities (counts & sums)

* **Per-merchant sum law.** Let `N` be S2’s accepted draw from `rng_event.nb_final.n_outlets (≥2)`. Summing `final_country_outlet_count` across all `legal_country_iso` for a merchant **MUST equal** `N`. Also, `raw_nb_outlet_draw` is **constant per merchant** and equals `N`.
* **Per-country row law.** For each `(merchant, legal_country_iso)`, the number of rows **equals** that row group’s `final_country_outlet_count`. (Combines with §9.1 contiguity.) 

---

## 9.4 Domain & membership integrity

* **No phantom countries.** Every `(merchant, legal_country_iso)` appearing in `outlet_catalogue` **must** exist in that merchant’s **S3 `s3_candidate_set`**. 
* **Home consistency.** For a given merchant, `home_country_iso` is constant across all rows and equals the **S3 country whose `candidate_rank==0`**. 
* **Zero-count elision.** If an S7/S3 integerised count for a `(merchant,country)` is `0`, **no rows** for that pair appear in `outlet_catalogue`. (S7 integerisation yields non-negative counts with `Σ count_i = N`.) 

---

## 9.5 Authority separation (order & weights)

* **No cross-country order encoded.** `outlet_catalogue` **does not** contain any cross-country ordering; consumers MUST join **S3 `candidate_rank`** when order is required. Presence of any cross-country rank field in egress is a **hard failure**.
* **No weight semantics.** Egress rows **MUST NOT** embed or imply S5 weights; S5 remains weights authority (used upstream by S6/S7 only). 

---

## 9.6 Event coverage & envelope invariants (S8 streams)

For each `(merchant, country)` with `final_country_outlet_count = n ≥ 1`:

* **Exactly one** `rng_event.sequence_finalize` with
  `site_count = n`, `start_sequence = "000001"`, `end_sequence = zfill6(n)`. 
* **Non-consuming law.** `sequence_finalize` and `site_sequence_overflow` (if any) are **non-consuming** events (`before==after`, `blocks=0`, `draws="0"`). 
* **Overflow rule.** If `n > 999999`, producer **must** emit `rng_event.site_sequence_overflow` with `{attempted_count=n, max_seq=999999, overflow_by=n−999999}` and **fail the merchant** (no egress rows for that merchant). 
* **Trace duty.** After **each** event append above, append **exactly one** cumulative `rng_trace_log` row for the corresponding `(module, substream_label)`. 

---

## 9.7 Column-level domain checks (egress)

* `single_vs_multi_flag == true` for all rows (S8 writes multi-site merchants only). 
* `raw_nb_outlet_draw ≥ 2`; `final_country_outlet_count ∈ [1, 999999]`; `site_order ≥ 1`; `site_id` matches `^[0-9]{6}$`; `global_seed` is a valid `uint64`. 

---

## 9.8 Join-back sanity (no permutation against S3)

* Join `outlet_catalogue` (distinct **`legal_country_iso`**) to S3 `s3_candidate_set` on `outlet_catalogue.(merchant_id, legal_country_iso) = s3_candidate_set.(merchant_id, country_iso)` and then:
  (a) succeed for **all** egress countries; and
  (b) show **no permutation** of cross-country order when sorted by `candidate_rank` (egress does not encode order, only that the **set** matches). 

---

## 9.9 Hand-off gate (consumer constraint)

* For a given `fingerprint`, consumers (e.g., 1B) **MUST** verify that the `_passed.flag` in `data/layer1/1A/validation/fingerprint={fingerprint}/` has **content hash equal to `SHA256(validation_bundle_1A)`** for the same fingerprint **before** reading `outlet_catalogue`. **No PASS → no read.** 

**Status:** Section 9 is **Binding**.

---

# 10) Error handling, edge cases & degrade ladder **(Binding)**

This section fixes **how S8 fails, degrades, or proceeds deterministically**. All codes and actions below are **normative**.

---

## 10.1 Error classes (names, triggers, actions)

Each error has a **Trigger → Emit → Action** triad. “Emit” refers to S8’s own streams (when applicable) or to writing a failure record into the fingerprint’s validation bundle context; all emits must follow the schemas and dictionary paths for logs/validation.

**E_PASS_GATE_MISSING**

* **Trigger:** S8 attempts to read a convenience surface that requires a PASS (e.g., `s6_membership`) but the **S6 receipt** folder for the same `{seed,parameter_hash}` is absent or `_passed.flag` content hash ≠ `SHA256(S6_VALIDATION.json)`.
* **Emit:** Failure record in the S8 validator bundle context for this fingerprint.
* **Action:** **Abort** the run before any egress write. **No PASS → no read.** 

**E_SCHEMA_INVALID**

* **Trigger:** Any required input fails its JSON-Schema (`s3_candidate_set`, `rng_event.nb_final`, `rng_event.gumbel_key`/`ztp_final` when reconstructing membership).
* **Emit:** Failure record (schema path, first violation).
* **Action:** **Abort**.

**E_PATH_EMBED_MISMATCH**

* **Trigger:** Any lineage column **bytes-not-equal** to its path token (e.g., `parameter_hash` in S3 tables, `{seed,parameter_hash,run_id}` in RNG events; `manifest_fingerprint` in egress).
* **Emit:** Failure record (dataset/stream, offending value vs token).
* **Action:** **Abort**.

**E_S3_MEMBERSHIP_MISSING**

* **Trigger:** A `(merchant,country)` appears in counts but **not** in `s3_candidate_set` for that merchant.
* **Emit:** Failure record listing the phantom `(merchant,country)`.
* **Action:** **Abort** (S3 is the sole order/membership authority). 

**E_COUNTS_SOURCE_MISSING**

* **Trigger:** Neither `s3_integerised_counts` (when designated) **nor** an in-process S7 counts handoff is available; or per-country counts cannot be recovered from the authoritative S7 evidence.
* **Emit:** Failure record (merchant list).
* **Action:** **Abort** (S8 MUST NOT derive counts from weights).

**E_DUP_PK**

* **Trigger:** Would-be `outlet_catalogue` contains duplicate PK `[merchant_id, legal_country_iso, site_order]`.
* **Emit:** Failure record (first duplicate).
* **Action:** **Abort**. (PK/UK are binding.) 

**E_SEQUENCE_GAP**

* **Trigger:** For any `(merchant, legal_country_iso)` with `n≥1`, proposed `site_order` set is **not exactly** `{1,…,n}`.
* **Emit:** Failure record (first gap/dup).
* **Action:** **Abort**. 

**E_SITE_ID_OVERFLOW**

* **Trigger:** `n > 999,999` for a `(merchant,country)` block.
* **Emit:** **`rng_event.site_sequence_overflow`** with `{attempted_count, max_seq=999999, overflow_by, severity="ERROR"}` **and** a failure record.
* **Action:** **Abort the merchant** (no egress rows for that merchant). 

**E_ORDER_AUTHORITY_DRIFT**

* **Trigger:** Any attempt to **encode** or **imply** cross-country order in `outlet_catalogue`, or divergence from `s3_candidate_set.candidate_rank` when order is joined for checks.
* **Emit:** Failure record (fields that imply order).
* **Action:** **Abort**. (S3 is sole authority.) 

**E_SUM_MISMATCH**

* **Trigger:** For a merchant, `Σ final_country_outlet_count ≠ rng_event.nb_final.n_outlets`.
* **Emit:** Failure record (merchant ID, observed sums).
* **Action:** **Abort**. 

**E_FK_ISO_INVALID**

* **Trigger:** `home_country_iso` / `legal_country_iso` not in canonical ISO registry.
* **Emit:** Failure record (first offending ISO).
* **Action:** **Abort**. 

**E_TRACE_COVERAGE_MISSING**

* **Trigger:** A required S8 event (`sequence_finalize` or `site_sequence_overflow`) was appended but **no** paired `rng_trace_log` row follows; or vice versa coverage counts don’t tally.
* **Emit:** Failure record (event family, counts).
* **Action:** **Abort**. 

---

## 10.2 Edge cases (deterministic non-errors)

These are **valid** outcomes; S8 proceeds and still writes normal outputs and events:

* **DEG_SINGLE_COUNTRY.** Domain is only home; S8 writes `n_home=N`, emits one `sequence_finalize` for home. 
* **DEG_ZERO_REMAINDER.** All integer counts equal floors (no bumps); `site_order` still contiguous `1..nᵢ`; normal finalize events. 

---

## 10.3 Degrade ladder (when optional conveniences are missing)

S8 follows this **ordered** ladder; each step is **binding**:

1. **Prefer S3 parameter-scoped determinism when present.**
   If `s3_integerised_counts` exists, S8 **MUST** read it (authoritative counts) and proceed. 

2. **Otherwise, use in-process S7 counts handoff.**
   S8 **MUST NOT** reconstruct counts from S5 weights; counts must come from S7 evidence (residual ranks) if S3 did not emit counts. 

3. **Membership surface preference.**
   If `s6_membership` exists **and** S6 PASS is verified, use it; **else** reconstruct membership from `rng_event.gumbel_key` + `rng_event.ztp_final`. **Do not abort** simply because the convenience surface is absent.

4. **Optional upstream S3 sequencing.**
   If `s3_site_sequence` exists, S8 **cross-checks** only (does not change semantics). Divergence ⇒ `E_SEQUENCE_DIVERGENCE` (abort). 

---

## 10.4 Emit rules & envelopes (S8 streams)

* **`rng_event.sequence_finalize`**: **exactly one** per `(merchant,country)` with `n≥1`, with `site_count=n`, `start_sequence="000001"`, `end_sequence=zfill6(n)`; event is **non-consuming** (`blocks=0`, `draws="0"`). 
* **`rng_event.site_sequence_overflow`**: only when `n>999999`; severity=`"ERROR"`; **non-consuming** envelope. 
* **`rng_trace_log`**: after **every** append above, S8 appends **exactly one** cumulative trace row. Paths/partitions must match `{seed, parameter_hash, run_id}`. 

---

## 10.5 Abort & cleanup discipline

On any **Abort** action:

* **Do not** publish `outlet_catalogue` for the fingerprint (or the merchant, if the failure is merchant-scoped like overflow).
* Ensure partial temp paths are removed; **no partial contents** become visible (atomic publish discipline in §5). 
* Record the failure in the fingerprint’s validation bundle context for post-hoc inspection; the consumer gate remains **FAILED** (no `_passed.flag`). 

---

## 10.6 Severity mapping (informative for ops)

* **ERROR (hard failure):** all `E_*` codes above.
* **INFO (deterministic outcome):** `DEG_SINGLE_COUNTRY`, `DEG_ZERO_REMAINDER`.

**Status:** Section 10 is **Binding**.

---

# 11) Validation battery & PASS gate **(Binding)**

**Purpose.** Prove that S8 wrote a correct, reproducible `outlet_catalogue` under the S0–S7 contracts; verify instrumentation coverage; and publish a **fingerprint-scoped** validation bundle whose `_passed.flag` is the consumption **gate** for 1B (**no PASS → no read**). 

---

## 11.1 Inputs the validator MUST read (and their anchors)

* **Subject of validation:** `outlet_catalogue` → `schemas.1A.yaml#/egress/outlet_catalogue` (PK/UK, partitions `[seed,fingerprint]`, writer sort). 
* **Order authority:** `s3_candidate_set` → `schemas.1A.yaml#/s3/candidate_set` (total, contiguous ranks; `home` at 0). 
* **Count facts:** `rng_event.nb_final` → `schemas.layer1.yaml#/rng/events/nb_final` (exactly one per merchant; **non-consuming**). If present, also read `s3_integerised_counts` → `schemas.1A.yaml#/s3/integerised_counts`. Otherwise, use S7 residual evidence (`rng_event.residual_rank`).
* **S8 instrumentation:** `rng_event.sequence_finalize`, `rng_event.site_sequence_overflow` (S8-emitted families). Also `rng_trace_log` and `rng_audit_log` for coverage.
* **Gates (if conveniences were used upstream):** `s6_validation_receipt` when `s6_membership` was read by S8. **No PASS → no read.** 

---

## 11.2 Structural checks (schemas, partitions, lineage)

The validator **MUST** assert:

1. **Schema-validity & partitions** for all inputs above (tables/events match their `$ref`; paths match dictionary path templates & partitions).
2. **Path↔embed equality:** every egress row’s `manifest_fingerprint` equals the `fingerprint` path token; every RNG/event row (audit/trace/S8 events) embeds `{seed, parameter_hash, run_id, manifest_fingerprint}` where `{seed, parameter_hash, run_id}` equal the path tokens and `manifest_fingerprint` equals the **validation fingerprint** for this bundle. **Any mismatch ⇒ fail.**
3. **S6 gate (if applicable):** if `s6_membership` was consumed by the producer, the S6 receipt folder exists and `_passed.flag` content hash equals `SHA256(S6_VALIDATION.json)` for the same `{seed,parameter_hash}`. **No PASS → fail.** 

---

## 11.3 Content checks (egress invariants)

For each `(merchant_id, legal_country_iso)` group with rows:

* **Contiguity & keys:** `site_order` is exactly `{1..final_country_outlet_count}` with no gaps/dupes; `site_id` is zero-padded 6-digit rendering of `site_order` (regex `^[0-9]{6}$`). PK unique on `[merchant_id, legal_country_iso, site_order]`. 
* **Lineage fields:** `manifest_fingerprint` is lowercase hex64 and equals the partition token; `global_seed` **equals the `seed` path token** and is a valid `uint64`.
* **No cross-country order encoded:** the table contains **no** field implying inter-country order; dictionary note requires consumers to join S3 `candidate_rank`. Presence of such fields ⇒ fail. 

---

## 11.4 Cross-state equalities (counts, sums, membership)

Per merchant:

* **Sum law vs S2:** `Σ_c final_country_outlet_count == rng_event.nb_final.n_outlets` and egress `raw_nb_outlet_draw` equals that same `N`. 
* **Membership law vs S3:** every `(merchant, legal_country_iso)` present in egress must exist in that merchant’s `s3_candidate_set`; exactly one `home` in S3 and `home_country_iso` constant across egress rows. 
* **Counts authority:** if `s3_integerised_counts` exists, its `{merchant,country,count}` matches egress `{final_country_outlet_count}`; otherwise, the multiset of per-country counts reconstructed from S7 `rng_event.residual_rank` equals egress counts. **Any discrepancy ⇒ fail.**

---

## 11.5 Event coverage & RNG envelope checks

For each `(merchant, country)` with `final_country_outlet_count = n ≥ 1`:

* **Exactly one** `rng_event.sequence_finalize` with `{site_count=n, start_sequence="000001", end_sequence=zfill6(n)}`. 
* **Overflow rule:** if `n > 999999`, there MUST be a `rng_event.site_sequence_overflow{attempted_count=n, max_seq=999999, overflow_by}` and **no** egress rows for that merchant (merchant-scoped abort). 
* **Non-consuming law:** both S8 event families are **non-consuming** (`before==after`, `blocks=0`, `draws="0"`); validator verifies envelopes. 
* **Trace duty:** after **each** event append above, **exactly one** cumulative `rng_trace_log` row exists (saturating totals; `draws_total` equals sum of event `draws`). 

---

## 11.6 Egress join-back sanity (order separation)

Join distinct egress countries back to S3 on `outlet_catalogue.(merchant_id, legal_country_iso) = s3_candidate_set.(merchant_id, country_iso)`; assert the set matches and that sorting by `candidate_rank` yields a consistent cross-country order (egress itself remains order-free).

---

## 11.7 Validator artefacts & PASS gate (fingerprint-scoped)

Write the **validation bundle** under:
`data/layer1/1A/validation/fingerprint={manifest_fingerprint}/` (fingerprint partition). Bundle contains machine-readable results (e.g., schema checks, counts & sums, membership parity, RNG accounting, FK checks). Compute `_passed.flag` as:

* Single line: `sha256_hex = <hex64>`, where `<hex64>` is the SHA-256 over the **ASCII-lexicographic concatenation** of all other bundle files’ bytes (exclude `_passed.flag`). Publish atomically into the fingerprint folder.

**Gate rule (consumer binding):** 1B **MUST** verify that `_passed.flag` content hash equals `SHA256(validation_bundle_1A)` for the **same** fingerprint before reading `outlet_catalogue`. **No PASS → no read.**

---

## 11.8 Exit semantics

* **PASS:** all checks in §§11.2–11.6 succeed; bundle written; `_passed.flag` valid. `outlet_catalogue` remains readable by 1B under the gate. 
* **FAIL:** any structural, lineage, count, membership, or RNG-coverage breach. Publish bundle with failure records; **do not** modify `outlet_catalogue`; gate remains **failed** (no valid `_passed.flag`). 

---

## 11.9 Determinism requirement (validator)

With identical inputs, schemas, dictionary, and numeric environment, the validator **MUST** produce a byte-identical bundle and the same `_passed.flag` hash (idempotent, atomic publish). 

**Status:** Section 11 is **Binding**.

---

# 12) Concurrency, sharding & determinism **(Binding)**

This section fixes how S8 may parallelise work and still produce **byte-stable** `outlet_catalogue` and **value-stable** logs. All clauses are **normative**.

---

## 12.1 Writer discipline (single identity, at-most-once)

* **Partition identity (egress):** `(dataset='outlet_catalogue', seed, fingerprint)`; this partition is **write-once**. If it already exists, producers **MUST** verify byte identity; if different, **hard-fail** (no overwrite). Egress path & sort are fixed by the Dictionary & schema.
* **Atomic publish:** **Stage → fsync → atomic rename** into the Dictionary location; **no partial contents** may become visible. After publish, the partition is **immutable**. (Discipline mirrors S7 §10.4.) 

## 12.2 Sharding model (how to split the work)

* **Shard key:** S8 **MUST** shard on `merchant_id` (ranges or hash buckets). Each worker owns a disjoint merchant set; **no merchant may be processed by two workers**. (Prevents duplicate events/rows.) 
* **Block atomicity:** The unit of emission is a **(merchant, legal_country_iso)** block with `n≥1`. A worker **MUST** emit exactly `n` rows with `site_order=1..n` for that block, then append **one** `sequence_finalize` event.
* **Set semantics across files:** Physical file order is non-authoritative; equality is by **row set**. Writers must honour the Dictionary’s **writer sort** for egress. 

## 12.3 Determinism w.r.t. worker counts, retries & scheduling

* **Worker-count invariance:** Changing the number of workers or task schedule **MUST NOT** change any value or emitted row. Determinism is guaranteed by: S3’s **candidate_rank** authority (order), S7/S3 **counts** authority, fixed egress **sort keys**, and atomic publish.
* **Retry semantics:** On failure, producers **MUST NOT** partially publish; they **MAY** retry after cleaning temp paths. Re-running with identical inputs and lineage **MUST** yield byte-identical egress. (Same discipline as S7 §10.3–10.4.) 

## 12.4 RNG logs under parallelism (events are non-consuming)

* **Families S8 emits:** `rng_event.sequence_finalize` and (guardrail) `rng_event.site_sequence_overflow`, both partitioned by `{seed, parameter_hash, run_id}` and validated by layer schemas.
* **Envelope law:** S8’s events are **non-consuming** (`before==after`, `blocks=0`, `draws="0"`); envelopes **MUST** populate `{seed, parameter_hash, run_id, manifest_fingerprint}` per schema. `manifest_fingerprint` **MUST** equal the egress fingerprint (there is no path token for it on event paths).
* **Trace duty (per event):** After **each** append to `sequence_finalize` or `site_sequence_overflow`, S8 **MUST** append **exactly one** cumulative row to `rng_trace_log` for the corresponding `(module, substream_label)`. Totals reconcile irrespective of concurrency (saturating sums).
* **No double-emission:** A given `(merchant, country)` **MUST NOT** produce multiple `sequence_finalize` events; detect and fail on concurrent write intent. (Same pattern as S7 §10.5.) 

## 12.5 Multi-run semantics (run_id)

* **`run_id` partitions logs only.** Multiple `run_id`s may coexist for the same `{seed, parameter_hash}` without changing model outcomes or egress semantics. Egress remains **fingerprint-scoped**. 
* **Audit first, then events:** Emit `rng_audit_log` once at run start, then events, then traces; all under `{seed, parameter_hash, run_id}` with schema-valid embeddings. 

## 12.6 Ownership & isolation

* **S8 writes only its families** (`sequence_finalize`, `site_sequence_overflow`) plus egress. It **MUST NOT** write S1–S7 families or any RNG core paths owned by other states except its trace/audit appends. (Ownership & schemas enumerated in the registry/dictionary.)
* **No cross-state emissions:** S8 does **not** emit selection keys (`gumbel_key`), NB/ZTP components, or residuals; those belong to S6/S2/S4/S7 respectively.

## 12.7 Lineage equality & canonical paths (concurrency checks)

* **Path↔embed equality** is **binding** on every event/log row for `{seed, parameter_hash, run_id}`, and on egress for `manifest_fingerprint == fingerprint path token`. Mismatch ⇒ abort.
* **Canonical paths only:** All writes **MUST** target the Dictionary paths and partitions for their families/datasets; free-hand paths are non-conformant. 

## 12.8 Storage & writer policy (if pinned)

* **Egress Parquet:** honour Dictionary writer sort `[merchant_id, legal_country_iso, site_order]`; compression **as pinned** (e.g., ZSTD level 3) when specified by the registry; otherwise, value identity suffices.
* **JSONL events:** set semantics across parts; line order within a file has no semantic meaning; validators use cumulative **trace** totals and event counts. 

## 12.9 Consumer guarantees (what parallelism may not break)

Given §§12.1–12.8 and the invariants in §9, consumers are guaranteed that for any fixed `(seed,fingerprint)`:

* `outlet_catalogue` is **byte-stable** and **order-stable** by its sort keys;
* each `(merchant, country)` block contributes `n` rows with `site_order=1..n` and a single `sequence_finalize` event;
* RNG core logs reconcile (`draws_total`, `blocks_total`, `events_total`) regardless of producer concurrency.

**Status:** Section 12 is **Binding**.

---

# 13) Observability & metrics **(Binding)**

This section fixes **what S8 must emit/observe**, **the counters & coverage it must publish**, and **where those metrics live**. All clauses are **normative**.

---

## 13.1 Observability surfaces (streams & locations)

* **Core RNG logs (run-scoped):**
  **`rng_audit_log`** and **`rng_trace_log`** under
  `logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl` and
  `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl`.
  The trace is **per-(module, substream_label)** with saturating totals; **emit exactly one cumulative trace row after each RNG event append**. 

* **S8 instrumentation events (merchant×country blocks):**
  **`rng_event.sequence_finalize`** at
  `logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` (final sequence per block), and
  **`rng_event.site_sequence_overflow`** at
  `logs/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` (guardrail).
  Both families are schema-anchored in `schemas.layer1.yaml` and **gated** to multi-site merchants (`gated_by: rng_event_hurdle_bernoulli; predicate: is_multi==true`).

* **Egress & hand-off context:** `outlet_catalogue` (fingerprint-scoped) and the **validation bundle** folder that gates consumption.

---

## 13.2 Trace & envelope duty (must hold)

* After **each** append to `sequence_finalize` or `site_sequence_overflow`, S8 **MUST** append **exactly one** cumulative row to `rng_trace_log` for the corresponding `(module, substream_label)`. The trace reconciles **events_total**, **draws_total**, and **blocks_total** (per schema: draws_total equals the sum of event-level draws; blocks via counters). 
* S8 event families are **non-consuming** (per §8/§9): validator reconciliation therefore expects **event counts to rise**, while **draws_total/blocks_total contributions from S8 families are zero**; the trace still logs the events_total increment. 

---

## 13.3 Metrics S8 MUST publish (in the validation bundle)

The validator **MUST** write the following artefacts under
`data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`:

1. **`rng_accounting.json`** — event and trace reconciliation:

   * `sequence_finalize_events` (count)
   * `site_sequence_overflow_events` (count)
   * `trace_events_total_delta` for S8 substreams (should equal the sum of the two counts)
   * `trace_draws_total_delta` and `trace_blocks_total_delta` for S8 substreams (expected **0**)
   * `audit_present` (boolean) and audit/trace **path↔embed** parity results.
     *(The bundle is the basis of the consumer gate and already enumerated to contain RNG accounting/metrics.)* 

2. **`s8_metrics.json`** — egress & domain coverage:

   * `merchants_in_egress` (distinct `merchant_id`)
   * `blocks_with_rows` (count of `(merchant, legal_country_iso)` with `n≥1`)
   * `rows_total` (egress rows), checksum of PK tuple hashes, and `rows_total_by_country` (map `legal_country_iso → rows`) — helpful for 1B pre-flight checks
   * `hist_final_country_outlet_count` (bucketed histogram of `n`)
   * `domain_size_distribution` (histogram of `|Dₘ|`, joined from S3)
   * `overflow_merchant_count` and list (ids truncated or hashed)
   * `sum_law_mismatch_count` (should be 0)
   * `s3_membership_miss_count` (should be 0)
   * `iso_fk_violation_count` (should be 0).
     *(Validation bundle is defined to carry “metrics, plots, diffs”; these keys are binding for S8.)* 

3. **`egress_checksums.json`** — stable hashes for reproducibility (e.g., SHA-256 per file and whole-partition composite) to support byte-identity assertions on re-runs. *(Lives in the same bundle as above.)* 

> The bundle’s `_passed.flag` content hash **MUST** equal `SHA256(validation_bundle_1A)` for the same fingerprint; consumers verify this **before** reading `outlet_catalogue`. 

---

## 13.4 SLO-style thresholds (binding alerts)

The validator **MUST** hard-fail (§11) if any of the following non-exhaustive conditions are met (write into the bundle and withhold `_passed.flag`):

* `trace_events_total_delta ≠ sequence_finalize_events + site_sequence_overflow_events`. 
* `sum_law_mismatch_count > 0` or `s3_membership_miss_count > 0`. (Breaks core invariants.) 
* Any **path↔embed** mismatch detected for audit/trace/events. 

---

## 13.5 Retention & access control (operational)

* **Retention:** `rng_audit_log` and `rng_trace_log`: **365 days**; S8 event streams (`sequence_finalize`, `site_sequence_overflow`): **180 days**; `outlet_catalogue` and the validation bundle: **365 days** (minimum). Producers **MUST** adhere to the dictionary’s retention.
* **Gate:** `outlet_catalogue` is readable **only** after the validation bundle’s `_passed.flag` verifies for the same fingerprint (**no PASS → no read**). 

---

## 13.6 Module & labels (log identity)

* S8 producers **MUST** populate the RNG envelopes with the `(module, substream_label)` values enumerated for S8 (see Appendix A). The dictionary lineage shows S8’s producer as **`1A.site_id_allocator`** for `sequence_finalize`; use the same module label across S8 events for consistent trace roll-up. 

**Status:** Section 13 is **Binding**.

---

# Appendix A — Enumerations & literal labels **(Normative)**

This appendix freezes the **exact strings** S8 producers/validators must use in logs, datasets, gates, and error reporting. Unless stated otherwise, all items are **binding**.

---

## A.1 RNG `module` / `substream_label` literals for S8

* **`module` (all S8-emitted events):**
  `1A.site_id_allocator`  — emitter of S8 instrumentation families. 

* **`substream_label` (per family):**
  `sequence_finalize` — final per-(merchant,country) sequence event. 
  `site_sequence_overflow` — guardrail when 6-digit space would overflow. 

> Conformance: these values **MUST** populate the RNG envelope fields `module` and `substream_label` for S8’s event rows (schema `#/rng_envelope`). 

---

## A.2 Event family names & canonical paths (S8)

* **`rng_event.sequence_finalize`**
  Path: `logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
  Schema: `schemas.layer1.yaml#/rng/events/sequence_finalize`
  Gating: `gated_by: rng_event_hurdle_bernoulli`, `predicate: is_multi == true`. 

* **`rng_event.site_sequence_overflow`**
  Path: `logs/rng/events/site_sequence_overflow/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`
  Schema: `schemas.layer1.yaml#/rng/events/site_sequence_overflow`
  Gating: same as above. 

* **Core RNG logs (read by validator):**
  `rng_audit_log` → `logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl` (schema `#/rng/core/rng_audit_log`)
  `rng_trace_log` → `logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl` (schema `#/rng/core/rng_trace_log`)
  *(Trace requires exactly one cumulative row after **each** RNG event append.)*

---

## A.3 Dataset IDs S8 reads/writes (IDs → `$ref` → partitions)

* **Egress (S8 writes):**
  `outlet_catalogue` → `schemas.1A.yaml#/egress/outlet_catalogue` → `[seed, fingerprint]`
  Path: `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`.
  *(Does **not** encode cross-country order; consumers must join S3 candidate rank.)*

* **Order authority (read):**
  `s3_candidate_set` → `schemas.1A.yaml#/s3/candidate_set` → `[parameter_hash]`. 

* **Counts surface (read, variant if present):**
  `s3_integerised_counts` → `schemas.1A.yaml#/s3/integerised_counts` → `[parameter_hash]`. 

* **Optional upstream sequence (cross-check only, if present):**
  `s3_site_sequence` → `schemas.1A.yaml#/s3/site_sequence` → `[parameter_hash]`. 

* **Membership convenience (read if used):**
  `s6_membership` → `schemas.1A.yaml#/s6/membership` → `[seed, parameter_hash]`
  `s6_validation_receipt` → `schemas.layer1.yaml#/validation/s6_receipt` → `[seed, parameter_hash]` *(gate)*. 

---

## A.4 Gate & bundle identifiers (hand-off)

* **Validation bundle (fingerprint-scoped):** `validation_bundle_1A`
  Path: `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/` (schema `schemas.1A.yaml#/validation/validation_bundle`).

* **Consumer gate flag:** `validation_passed_flag` (file: `_passed.flag`)
  Rule: content hash equals `SHA256(validation_bundle_1A)` for the **same** fingerprint (**no PASS → no read**). 

---

## A.5 Payload field literals & constants (S8 events)

* **`sequence_finalize` payload keys:** `merchant_id`, `country_iso`, `site_count`, `start_sequence`, `end_sequence`.
  Domain: `start_sequence`, `end_sequence` ∈ `six_digit_seq` (`^[0-9]{6}$`). 
  Naming note: **Events** use `country_iso`; **egress** uses `legal_country_iso`; both FK → `iso3166_canonical_2024`.

* **`site_sequence_overflow` payload keys:** `merchant_id`, `country_iso`, `attempted_count`, `max_seq`, `overflow_by`, `severity`.
  Constants: `max_seq = 999999`, `severity = "ERROR"`. 

---

## A.6 Lineage & path tokens (exact column/segment names)

* Path tokens used by S8: `seed`, `parameter_hash`, `run_id`, `fingerprint`.
* Embedded lineage columns that must **byte-equal** path tokens where present:
  `manifest_fingerprint` (egress row) ↔ `fingerprint` (path);
  `{seed, parameter_hash, run_id}` (event rows) ↔ their path segments;
  and for **event rows**, `manifest_fingerprint` **MUST** equal the run’s egress fingerprint (not a path token).

---

## A.7 Error & outcome codes (S8)

**Errors (hard failures):**
`E_PASS_GATE_MISSING` · `E_SCHEMA_INVALID` · `E_PATH_EMBED_MISMATCH` · `E_S3_MEMBERSHIP_MISSING` · `E_COUNTS_SOURCE_MISSING` · `E_DUP_PK` · `E_SEQUENCE_GAP` · `E_SITE_ID_OVERFLOW` · `E_ORDER_AUTHORITY_DRIFT` · `E_SUM_MISMATCH` · `E_FK_ISO_INVALID` · `E_TRACE_COVERAGE_MISSING` · `E_SEQUENCE_DIVERGENCE` (if `s3_site_sequence` is present and disagrees). *(These are defined by this spec; severity = ERROR for all.)*

**Deterministic non-errors (informative outcomes):**
`DEG_SINGLE_COUNTRY` · `DEG_ZERO_REMAINDER`. *(Defined by this spec.)*

---

## A.8 Notes on deprecated/legacy IDs (do **not** use for authority)

* `country_set` (legacy RNG-dependent set; **not** an order authority).
* `ranking_residual_cache_1A` (deprecated; superseded by `s3_integerised_counts`). 

---

## A.9 External FK targets (for completeness)

* `iso3166_canonical_2024` — FK target for ISO-2 in `home_country_iso` / `legal_country_iso`. 

**Status:** Appendix A is **Normative**.

---

# Appendix B — Worked micro-examples **(Informative)**

These toy scenarios illustrate S8 behaviour. Values are illustrative only; they do **not** change any binding rule above.

---

## B.1 Normal multi-country merchant (three-country domain)

**Lineage tokens**
`seed=1234567890123456789` (uint64) · `parameter_hash=a1…a1` (**hex64**) · `run_id=9f…9f` (**hex32**) · `fingerprint=0123456789abcdef…(**hex64**)`

**S3 candidate set (sole cross-country order, home rank=0)**
`GB(0), US(1), DE(2)` — total, contiguous.

**Upstream facts**
`N` (S2 `nb_final.n_outlets`) = **7**.
S7 integerised counts: `GB:4, US:2, DE:1` (sum = 7).
S6 membership agrees with S3 domain.

**S8 writes** `outlet_catalogue` (partitioned by `[seed, fingerprint]`; writer sort `[merchant_id, legal_country_iso, site_order]`):

| `merchant_id` | `home_country_iso` | `legal_country_iso` | `site_order` | `site_id` | `raw_nb_outlet_draw` | `final_country_outlet_count` | `manifest_fingerprint` |       `global_seed` |
|---------------|--------------------|---------------------|-------------:|----------:|---------------------:|-----------------------------:|------------------------|--------------------:|
| m42           | GB                 | GB                  |            1 |    000001 |                    7 |                            4 | …fingerprint…          | 1234567890123456789 |
| m42           | GB                 | GB                  |            2 |    000002 |                    7 |                            4 | …                      |                   … |
| m42           | GB                 | GB                  |            3 |    000003 |                    7 |                            4 | …                      |                   … |
| m42           | GB                 | GB                  |            4 |    000004 |                    7 |                            4 | …                      |                   … |
| m42           | GB                 | US                  |            1 |    000001 |                    7 |                            2 | …                      |                   … |
| m42           | GB                 | US                  |            2 |    000002 |                    7 |                            2 | …                      |                   … |
| m42           | GB                 | DE                  |            1 |    000001 |                    7 |                            1 | …                      |                   … |

**S8 emits** instrumentation (non-consuming events; each followed by one `rng_trace_log` row):

* `sequence_finalize(merchant=m42,country=GB, site_count=4, start_sequence="000001", end_sequence="000004")`
* `sequence_finalize(merchant=m42,country=US, site_count=2, …, end_sequence="000002")`
* `sequence_finalize(merchant=m42,country=DE, site_count=1, …, end_sequence="000001")`

**Checks that pass**

* Per-merchant sum: `4+2+1 = 7 = N`.
* Per-country contiguity: each block has `site_order = 1..nᵢ`; `site_id = zfill6(site_order)`.
* No cross-country order encoded; consumers join S3 `candidate_rank` when needed.

---

## B.2 Single-country domain (degenerate but valid)

**S3 candidate set**: `NG(0)` only.
**Upstream facts**: `N = 3`; S7 counts: `NG:3`.
**S8 egress** (three rows) with `legal_country_iso=NG`, `site_order=1..3` (`site_id` 000001..000003).
**S8 events**: one `sequence_finalize(…, country=NG, site_count=3, start="000001", end="000003")`.
**Outcome label**: `DEG_SINGLE_COUNTRY`.

---

## B.3 Overflow guardrail (merchant-scoped abort)

**S3 candidate set**: `CN(0)` only (or any single country).
**Upstream facts**: per-country integer count `n_CN = 1,000,001` (> 999,999 limit).
**S8 behaviour**

* Emit `site_sequence_overflow(merchant=mx, country=CN, attempted_count=1000001, max_seq=999999, overflow_by=2, severity="ERROR")`.
* **Do not** write any `outlet_catalogue` rows for merchant `mx`; mark merchant as failed in the validation bundle.
* Partition remains readable for other merchants; overall fingerprint may still PASS if failures are handled per policy (if policy is “abort merchant only”). *(Exact abort scope is as specified in §10.)*

---

## B.4 Using S3 integerised counts vs S7 evidence (both valid)

* **Variant A (preferred when present):** `s3_integerised_counts` says `BR:2, AR:1, UY:1` (N=4). S8 copies these counts verbatim; sequences are `1..2`, `1..1`, `1..1`.
* **Variant B (no S3 counts surface):** S8 receives the in-process S7 counts handoff (reconstructed by the validator from `rng_event.residual_rank`). Counts identical to above; S8 behaviour is the same.
* In **both** cases, S8 does **not** read weights and does **not** alter counts.

---

## B.5 Path & lineage parity (spot example)

Given path
`…/outlet_catalogue/seed=1234567890123456789/fingerprint=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef/part-000.parquet`,
every egress row **must** embed `manifest_fingerprint = "0123456789abcdef…"` and `global_seed = 1234567890123456789`. Any byte mismatch triggers `E_PATH_EMBED_MISMATCH` (see §10).

---

**Note:** These examples are **Informative**. The **Binding** behaviour, contracts, and gates are defined in §§0–13 and Appendix A.

---

# Appendix C — Storage conventions **(Informative)**

These are **non-binding** operational defaults for files, folders, and object-store hygiene. Authority for **paths, partitions, formats, retention** remains with the **Dataset Dictionary** and **Artefact Registry**; if those pin a storage policy (e.g., compression), that policy **wins**.

---

## C.1 File formats & compression (defaults; become binding if pinned)

* **Parquet (tables):** use **ZSTD level 3** unless the registry says otherwise; keep Parquet as the only format within a dataset/partition. 
* Suggested row-group target: **128–256 MiB** uncompressed; enable statistics; prefer dictionary encoding on low-cardinality columns (e.g., `legal_country_iso`).
* **JSONL (events/logs):** `.jsonl` (optionally **.jsonl.zst**); one JSON object per line, `\n` line endings; do not pretty-print. **RNG logs** are JSONL by dictionary. 

> If the registry publishes a compression profile (e.g., `compression_zstd_level3`), producers **should** use it and treat it as project policy. 

---

## C.2 Part sizing & naming (to avoid tiny files)

* Aim for **64–128 MiB** compressed per part; avoid parts < 8 MiB.
* Naming pattern: `part-00000-of-000NN.<ext>` (fixed batch) or `part-<uuid>.<ext>` (streaming). One family per folder. 

---

## C.3 Writer sort & non-authoritative order

* Follow the dictionary’s **writer sort** for egress (S8): `[merchant_id, legal_country_iso, site_order]`. Readers **MUST NOT** rely on physical file order; equality is by **row set**. RNG JSONL line order is append order **within a file** only.

---

## C.4 Canonical paths & partitions (reminder)

* **Egress (S8):** `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/` with partitions `[seed, fingerprint]` (Parquet). 
* **RNG events/logs:** `logs/rng/{audit|trace|events/<family>}/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` (JSONL). 
* **Validation bundle:** `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`. Gate via `_passed.flag` content hash == `SHA256(bundle)` for the **same** fingerprint. 

---

## C.5 Checksums & manifests (recommended)

* Write a **per-part SHA-256** sidecar: `part-….<ext>.sha256` (hex of compressed bytes).
* Optional folder `_MANIFEST.json`: list parts + sizes + hashes + total logical rows.
* Optional **folder hash**: SHA-256 over part hashes in lexicographic order (quick integrity anchor). 

---

## C.6 Atomic publish (recap)

* **Stage → fsync → atomic rename** into the dictionary path; never expose partial contents. Publish any checksums/manifest **before** the final rename. **Partitions are immutable** after publish. 

---

## C.7 Retention / TTL (use dictionary; typical values)

* **`outlet_catalogue`**: **365 days**.
* **RNG events** (`sequence_finalize`, `site_sequence_overflow`): **180 days**; **core logs** (`rng_trace_log`, `rng_audit_log`): **365 days**.
  Treat these numbers as defaults; the dictionary is the authority.

---

## C.8 Storage class & encryption (ops defaults)

* Object storage: keep in **standard** for first ~30 days, then **infrequent access** if read rates drop.
* Encrypt at rest with **SSE-KMS** (project-scoped key); reject unencrypted puts; maintain server-side checksums (or rely on the SHA-256 sidecars). 

---

## C.9 HTTP headers / object metadata (helpful, not required)

* **Content-Type**: JSONL → `application/x-ndjson`; Parquet → `application/vnd.apache.parquet`.
* Add metadata helpful for debugging: `x-run-seed`, `x-parameter-hash`, `x-run-id`, `x-content-sha256`, `x-module`, `x-substream`. 

---

## C.10 Compaction & housekeeping

* **Small-file compaction:** if > 128 parts or > 30% parts < 8 MiB, compact to target size.
* **Orphan cleanup:** delete `_staging` dirs older than 24 h; alert on dangling staging content.
* Keep only `{parts, .sha256, _MANIFEST.json}` in partition dirs—no temp/editor artefacts. 

---

## C.11 Access patterns (downstream hygiene)

* Always predicate reads on partition tokens rather than bucket-wide listings.
* For Parquet: **column-prune** (`merchant_id`, `legal_country_iso`, `site_order`, lineage).
* For JSONL: stream; avoid concatenating entire partitions in memory. 

---

## C.12 Path template configs (where ops keeps them)

* If ops exposes a **storage path pattern** or compression config in `configs/storage/*` (e.g., `storage_path_pattern.yaml`, `compression.yaml`), treat them as **operational policy**; they’re tracked in the Artefact Registry and participate in run manifesting. 

**Status:** Appendix C is **Informative** (operational guidance only).

---