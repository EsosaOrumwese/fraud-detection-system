# S5 SPEC — Currency→Country Weight Expansion (Layer 1 · Segment 1A)

# 0. Document metadata & status

**0.1 State identifiers, versioning, effective date**

* **State ID (canonical):** `layer1.1A.S5` — “Currency→Country Weight Expansion”. Sub-modules fixed by this spec:
  **`1A.derive_merchant_currency`** (S5.0) and **`1A.expand_currency_to_country`** (S5). 
* **Document name:** `state.1A.s5.spec`.
* **Semver:** `MAJOR.MINOR.PATCH`.
  **MAJOR** bumps on any breaking change to schemas or invariants (e.g., dataset/field rename, default `dp` change, Σ-tolerance change, tie-break rule change, coverage rules). **MINOR** for backward-compatible additions (optional columns, new metrics). **PATCH** for clarifications that do not alter contracts.
* **Effective date:** filled at ratification by release management (`effective_date: YYYY-MM-DD`).

**0.2 Normative language policy**

* **RFC 2119/8174** terms are used with their normative meanings (“MUST/SHALL/SHOULD/MAY”).
* All requirements in this document are **Binding** unless explicitly marked **Informative**.

**0.3 Sources of authority (single schema authority)**

* **Only JSON-Schema is authoritative** for 1A. Avro (if present) is **non-authoritative** and MUST NOT be referenced in registry/dictionary contracts. The following schema sets and IDs are the sole authorities:
  – Ingress schemas: **`schemas.ingress.layer1.yaml`** (`$id: schemas.ingress.layer1.yaml`). 
  – 1A schemas: **`schemas.1A.yaml`** (`$id: schemas.1A.yaml`). 
  – Layer-wide RNG/log schemas: **`schemas.layer1.yaml`** (`$id: schemas.layer1.yaml`). *(S5 does not emit RNG but remains bound to layer conventions.)* 
  Your S0/S4 documents already establish JSON-Schema as the only authority; this spec inherits that rule.

**0.4 Compatibility window (what this spec binds to in S0–S4)**
This S5 spec is **compatible with** and **assumes** the following already-ratified contracts remain on their **v1.* line**:

* **Dictionary:** `dataset_dictionary.layer1.1A.yaml` **v1.0** (IDs, paths, partitioning). 
* **Schema sets:** `schemas.ingress.layer1.yaml v1.0`, `schemas.1A.yaml v1.0`, `schemas.layer1.yaml v1.0`.
* **Order authority:** S3’s `s3_candidate_set.candidate_rank` is the **sole** inter-country order authority; `outlet_catalogue` **does not** encode cross-country order. *(S5 MUST NOT alter/encode country order.)* 
* **Lineage keys & partition law:** `parameter_hash` (parameter-scoped), `manifest_fingerprint` (egress/validation), `run_id` (logs). S5 is **parameter-scoped only** (no RNG/log partitions).
  If any of the above bump **MAJOR**, this document MUST be re-ratified.

**0.5 Schema anchors & dataset IDs in scope (read/write set)**

* **Inputs (ingress; parameter-scoped read):**
  – `settlement_shares_2024Q4` → `schemas.ingress.layer1.yaml#/settlement_shares`. 
  – `ccy_country_shares_2024Q4` → `schemas.ingress.layer1.yaml#/ccy_country_shares`. 
  – `iso3166_canonical_2024` (FK target) → `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`. 
* **Outputs (parameter-scoped; produced by S5):**
  – `ccy_country_weights_cache` → `schemas.1A.yaml#/prep/ccy_country_weights_cache`; **PK** `(currency, country_iso)`; path `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/`.
  – `merchant_currency` (S5.0) → `schemas.1A.yaml#/prep/merchant_currency`; path `data/layer1/1A/merchant_currency/parameter_hash={parameter_hash}/`. 
  – `sparse_flag` (per-currency diagnostics) → `schemas.1A.yaml#/prep/sparse_flag`; path `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/`. 
  All IDs, schema `$ref`s, PK/FK rules, and paths above are **normative** and MUST match the dictionary. 

**0.6 Hash canonicalisation (applies to S5 policy files)**

* S5 inherits **S0.2** hashing rules: **SHA-256 over exact bytes**, names included, sorted by **ASCII basename**, encoded by the **Universal Encoding Rule (UER)** (UTF-8 length-prefixed strings; LE64 integers; concatenation without delimiters).
* **Parameter hash contribution:** Any S5 policy/config file named in §4 **MUST** be added to the governed set that feeds `parameter_hash`; changing its bytes **MUST** flip `parameter_hash`. *(This is a contract on bytes, not YAML semantics; no normalization is permitted.)* 
* **Path↔embed equality:** For all S5 outputs, the embedded `parameter_hash` column **MUST equal** the `parameter_hash={…}` partition value byte-for-byte. 

**0.7 Document status & lifecycle**

* **Status:** `planning → beta → stable`. Publication on `stable` requires Section 9 PASS on a representative run and dictionary/schema lint clean for all `$ref`s noted above. 
* **Change control:** governed by §16 (semver triggers, deprecation, rollback); S5 remains **Binding** for the `v1.*` family of S0–S4 contracts cited in **0.4**.

---

# 1. Intent, scope, and non-goals

**1.1 Problem statement (what S5 does)**
S5 produces a **deterministic, parameter-scoped authority** of **currency→country weights** for later selection. Concretely, given the sealed, long-form share surfaces **`settlement_shares_2024Q4`** and **`ccy_country_shares_2024Q4`** (both Σ=1 per currency) and governed S5 policy, S5 emits **`ccy_country_weights_cache`**: per-currency, per-ISO weights that (a) live entirely under `parameter_hash`, (b) are **RNG-free**, and (c) are **S6-ready** for restriction to each merchant’s ordered candidate set from S3.

**1.2 Scope (what S5 covers)**
S5 SHALL:
a) Read only **parameter-scoped** S0-sealed datasets and policy named in this spec (§3–§4). Inputs include **`settlement_shares_2024Q4`** and **`ccy_country_shares_2024Q4`** as defined by the **ingress JSON-Schemas** and the dataset dictionary.
b) Optionally materialise a **`merchant_currency`** cache (S5.0) that provides each merchant’s settlement currency κₘ for downstream joins; it is parameter-scoped and listed in the dictionary. 
c) Produce **`ccy_country_weights_cache`** with **PK `(currency, country_iso)`**, **fixed-dp `weight_dp`**, and embedded `parameter_hash`, at the **parameter-scoped** path declared in the dictionary. 
d) Enforce that **coverage per currency equals the union** of ISO codes appearing in either input surface, unless policy narrows it (see §5.5/§6.10).
e) Preserve **S3’s sole authority over inter-country order**; S5 emits **no order** and SHALL NOT modify or imply order. S6 MUST continue to obtain order exclusively from **`s3_candidate_set.candidate_rank`**.
f) Adhere to **JSON-Schema as the single schema authority** for all inputs/outputs referenced in this document. 

**1.3 Non-goals (what S5 does not do)**
S5 SHALL NOT:
a) **Consume RNG** or write any `rng_*` streams; RNG traces and counters are out of scope for S5. (S5 is deterministic by construction.)
b) **Create, alter, or encode inter-country order**; the only order authority remains S3’s `candidate_rank`. 
c) **Make merchant-level choices** (e.g., selecting countries for a merchant, setting K, or allocating counts). Those belong to S6+ and remain gated by S3/S4 contracts. 
d) **Re-derive S0/S3 invariants** (e.g., ISO enumerations, Σ=1 constraints of ingress surfaces); S5 validates them pre-flight and fails closed if violated (see §3.6/§9). 
e) **Write egress artifacts** (e.g., `outlet_catalogue`) or any dataset partitioned by `{seed,fingerprint}`; S5 is **parameter-scoped only**. 

**1.4 Success criteria (what “done right” means)**
A run of S5 satisfies this spec iff all of the following hold:

1. **Determinism & Idempotence:** Same inputs + same policy bytes ⇒ **byte-identical** outputs (paths and rows). (See §6.9/§10.)
2. **Correctness of weights:** For each currency, `weight_dp ∈ [0,1]`, and the **decimal sum equals exactly `1` at declared `dp`** (Σ=1 property). 
3. **Coverage:** For each currency, output countries match the **union of input countries** (unless narrowed by policy recorded in lineage/metrics). 
4. **Schema & lineage:** Every dataset passes its **JSON-Schema**; partitions are `parameter_hash` only; **path↔embed equality** holds. 
5. **Interface fitness:** Outputs can be **restricted by S6 to each merchant’s ordered candidate set** from S3 without additional transforms or re-derivation. 

**1.5 Practical constraints (binding guardrails)**

* Inputs must already pass their **ingress schema constraints**, notably **Σ share = 1.0 ± 1e-6 per currency** and ISO/CCY domain checks; otherwise S5 MUST fail closed. 
* All policy/configuration named in §4 contributes to the **parameter hash**; changing any such file MUST change `parameter_hash`. (S5 is sealed by parameter-scope only.) 

---

# 2. Interfaces & “no re-derive” boundaries

**2.1 Upstream dependencies & invariants (what S5 may read and must assume)**
a) **Authoritative inputs (parameter-scoped; JSON-Schema bound).** S5 MAY read only the following sealed datasets and FK references, exactly as registered in the dictionary and bound by the ingress schema set:
• `settlement_shares_2024Q4` → `schemas.ingress.layer1.yaml#/settlement_shares` (PK: `(currency,country_iso)`).
• `ccy_country_shares_2024Q4` → `schemas.ingress.layer1.yaml#/ccy_country_shares` (PK: `(currency,country_iso)`).
• `iso3166_canonical_2024` → `schemas.ingress.layer1.yaml#/iso3166_canonical_2024` (FK target for `country_iso`).
All three are listed as **approved** in the dataset dictionary. JSON-Schema is the **single authority** for domains and constraints.

b) **Ingress pre-flight constraints (must hold before S5 runs).** For each input surface, S5 SHALL require: (i) PK uniqueness, (ii) `currency ∈ ISO-4217` and uppercase, (iii) `country_iso ∈ ISO2` uppercase and FK-valid, (iv) `share ∈ [0,1]`, `obs_count ≥ 0`, and (v) **group sum** `Σ share = 1.0 ± 1e-6` per `currency`. Violations are **hard FAIL** (S5 does not repair ingress).

c) **Policy/config inputs (parameter-scoped).** S5 MAY read the governed smoothing policy at `configs/policy.ccy_smoothing_params.yaml` (domains and precedence will be defined in §4). Any byte change to this file contributes to `parameter_hash`. 

d) **Order authority is upstream (S3).** Inter-country order is defined **only** by `s3_candidate_set.candidate_rank` (parameter-scoped). The egress `outlet_catalogue` explicitly **does not** encode cross-country order. S5 MUST neither read nor infer any alternative ordering.

e) **Lineage & partition law inherited.** S5 operates **parameter-scoped only**; it MUST NOT read or write `{seed,fingerprint}` partitions. Paths and embedded lineage fields are governed by the dictionary/schema pairs for S5 outputs. 

---

**2.2 Downstream usage (what S6+ may consume and how)**
a) **Consumable S5 outputs.** S6 and later 1A states MAY consume:
• `ccy_country_weights_cache` (`schemas.1A.yaml#/prep/ccy_country_weights_cache`, **PK** `(currency,country_iso)`), parameter-scoped path under `…/ccy_country_weights_cache/parameter_hash={parameter_hash}/`.
• (Optionally) `merchant_currency` cache (`schemas.1A.yaml#/prep/merchant_currency`) if present for κₘ joins.
These dataset IDs, schema refs, and paths are normative per the dictionary.

b) **Join pattern required.** Downstream selection/allocation MUST: (i) obtain **order** from `s3_candidate_set.candidate_rank`; (ii) obtain **weights** from `ccy_country_weights_cache`; (iii) if merchant-scoped joins are needed, obtain κₘ from `merchant_currency`; and (iv) perform joins using the keys defined by the respective schemas (e.g., `(currency,country_iso)` for weights; `merchant_id` for κₘ). No other source may be used for order or weights.

c) **Read gate.** Downstream MUST read S5 outputs **only after** the S5 PASS artefact defined in §9 is present for the same `parameter_hash` (**no PASS → no read**). (This mirrors Layer-1 egress gating already used for other 1A surfaces.) 

d) **Scope of permissible transforms.** Downstream MAY **restrict** weights to each merchant’s S3 candidate set and (if required by its own spec) renormalise within that set **for ephemeral computation only**. Downstream MUST NOT persist altered copies of S5 weights nor re-smooth/re-blend from ingress surfaces. Persisted weights remain the S5 authority. 

---

**2.3 “No re-derive” guarantees & prohibitions (who owns which truth)**
a) **S5 guarantees to downstream:**
• A complete per-currency coverage equal to the **union** of countries present in either ingress surface (unless explicitly narrowed by policy recorded in lineage/metrics).
• Schema-valid rows with a weight column exactly as specified by `schemas.1A.yaml#/prep/ccy_country_weights_cache` (field names and types per schema), partitioned by `parameter_hash`, with path↔embed equality. 

b) **S5 will NOT:**
• Emit, encode, or imply inter-country order.
• Use RNG or write any RNG traces/events.
• Alter or “repair” ingress surfaces that violate schema or Σ-constraints (S5 fails closed instead).

c) **Downstream MUST NOT:**
• Recompute weights from `settlement_shares_2024Q4` or `ccy_country_shares_2024Q4`, or apply alternative smoothing policies not included in the `parameter_hash`.
• Infer order from S5 outputs or any source other than `s3_candidate_set.candidate_rank`.
• Persist renormalised/re-weighted copies as substitutes for `ccy_country_weights_cache` (any persisted variant would constitute a new dataset and MUST NOT shadow S5).

d) **Ownership matrix (normative):**
• **Order (inter-country)** → **S3** (`s3_candidate_set.candidate_rank`).
• **Weights (currency→country)** → **S5** (`ccy_country_weights_cache`).
• **Merchant settlement currency κₘ** → **S5.0** (`merchant_currency`).
• **Egress outlet ordering & counts** → **S3/S4/S7/S8** surfaces; `outlet_catalogue` encodes **within-country** order only.


**2.4 Forward contracts to S6 (selection hand-off).**
a) **Domain.** S6 MUST select from the **intersection** of S5 weights and S3’s `s3_candidate_set` for each merchant. Weights present for **non-admissible** countries are **ignored** (not an error).
b) **Missing weights for admissible countries.** Only allowed if policy explicitly narrowed coverage (§8.6). In that case, S6 MAY renormalise **ephemerally** within the intersection; persisted weights remain the S5 authority.
c) **Order.** S6 MUST take order only from `candidate_rank`; S5 encodes no order.

---

# 3. Inputs — datasets, schemas, partitions

**3.1 Required datasets (read set; JSON-Schema authoritative)**
S5 SHALL read **only** the following sealed artefacts, exactly as registered in the dataset dictionary. Field names, types, domains, PK/FK, and constraints are governed by the referenced JSON-Schema anchors.

* **`settlement_shares_2024Q4`** — long-form currency→country settlement share vectors with observation counts.
  **Path:** `reference/network/settlement_shares/2024Q4/settlement_shares.parquet` (no partitions).
  **Schema ref (dictionary):** `schemas.ingress.layer1.yaml#/settlement_shares` *(alias resolving to the vintage anchor used in S0)*.
  **PK:** `(currency, country_iso)`.
  **Licence/retention:** per dictionary entry.

* **`ccy_country_shares_2024Q4`** — long-form currency→country split (“priors”) with observation counts.
  **Path:** `reference/network/ccy_country_shares/2024Q4/ccy_country_shares.parquet` (no partitions).
  **Schema ref (dictionary):** `schemas.ingress.layer1.yaml#/ccy_country_shares`.
  **PK:** `(currency, country_iso)`. 

* **`iso3166_canonical_2024`** — canonical ISO-3166 alpha-2 list used for FK validation.
  **Path:** `reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet` (no partitions).
  **Schema ref (dictionary):** `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`.
  **PK:** `(country_iso)`. 

* **Policy/config:** **`ccy_smoothing_params`** — governed parameters file for S5 (alpha/floors/overrides).
  **Path:** `configs/allocation/ccy_smoothing_params.yaml`.
  **Contribution to lineage:** **MUST** contribute to `parameter_hash`. 

> **Authority note.** JSON-Schema is the **only** schema authority for these inputs; Avro (if any) is non-authoritative. 

---

**3.2 Domains, types, and nullability (as per schema anchors)**
For both share surfaces (`settlement_shares_2024Q4`, `ccy_country_shares_2024Q4`):

* `currency` **MUST** be ISO-4217 **uppercase** 3-letter code.
* `country_iso` **MUST** be ISO-3166 **uppercase** alpha-2 and **FK-valid** to `iso3166_canonical_2024.country_iso`.
* `share` **MUST** be numeric **in [0,1]**.
* `obs_count` **MUST** be integer **≥ 0** (presence and type per ingress schema).
* **Primary key** uniqueness: no duplicate `(currency,country_iso)` rows.

No row-order requirements apply (dictionary `ordering: []`). 

---

**3.3 Row-group preconditions (per currency block, must hold before S5 proceeds)**
For **each** input surface independently:

* **Group sum rule:** for every `currency`, `Σ share = 1.0 ± 1e-6`.
* **Domain conformance:** all rows satisfy §3.2 domains and PK uniqueness.
* **Schema hygiene:** no extra/missing columns beyond the schema; strict type conformance.

---

**3.4 Rejection conditions (hard FAIL; S5 does not repair ingress)**
If any of the following are observed in either share surface, S5 **MUST** fail closed before producing outputs:

* Unknown `currency` (non-ISO-4217), non-uppercase, or null.
* Unknown `country_iso` or FK violation against `iso3166_canonical_2024`.
* Any `share` outside [0,1], NaN/Inf, or null where disallowed.
* Any `obs_count < 0` or non-integer where disallowed.
* **PK collision** on `(currency,country_iso)`.
* **Group sum** outside tolerance for any `currency`.
* Columns missing or extra vs schema anchor. 

---

**3.5 Enumerations and forbidden placeholders (Binding)**

* `country_iso` **MUST** belong to the **pinned** ISO set from `iso3166_canonical_2024`; placeholder codes such as `XX`, `ZZ`, `UNK` are **forbidden**.
* `currency` **MUST** belong to the ISO-4217 domain defined in the ingress schema set.

---

**3.6 Partitioning & lineage stance for inputs**

* All three datasets listed in §3.1 are **reference** inputs with **no path partitions** (vintage is in the folder name where applicable). S5 reads them **as-is** (S0 sealed them).
* The **policy file** `ccy_smoothing_params.yaml` is **parameter-scoped** by contract: any byte change **MUST** flip `parameter_hash` (see §0.6). 

---

# 4. Configuration & policy

**4.1 Policy file (location, consumers, version pinning)**

* **ID & path (registry):** `ccy_smoothing_params` at `configs/allocation/ccy_smoothing_params.yaml`. This artefact **MUST** appear in the artefact registry with a manifest key (e.g., `mlr.1A.params.ccy_smoothing`) and metadata (semver, version, digest). It is **first consumed in S5/S6** and governs the build of `ccy_country_weights_cache` (and the optional `merchant_currency` cache).  
* **Authority scope:** This document defines the **normative key set and domains** for the file. (JSON-Schema for this config may be added to the schema authority; until then, the rules in §4.2–§4.6 are binding.) 
* **Consumers:** S5 **weights builder** and S6 **merchant_currency** cache builder. Changing this file **changes policy** → **new `parameter_hash`**. 
* **Versioning fields in-file:** `semver: "MAJOR.MINOR.PATCH"` and `version: "YYYY-MM-DD"` **MUST** be present. 

**4.2 Keys & domains (normative content of `ccy_smoothing_params.yaml`)**
The policy file **MUST** contain exactly the following top-level structure (no extra keys):

* `semver : string` — semantic version string `\d+\.\d+\.\d+`. 
* `version : string` — date string `YYYY-MM-DD`. 
* `dp : int` — **fixed decimals for OUTPUT weights**; **domain:** `0…18` inclusive. 
* `defaults : object` — global defaults used unless overridden:
  • `blend_weight : number ∈ [0,1]`
  • `alpha : number ≥ 0` (additive Dirichlet α per ISO)
  • `obs_floor : integer ≥ 0` (minimum effective mass)
  • `min_share : number ∈ [0,1]` (per-ISO floors applied post-smoothing)
  • `shrink_exponent : number ≥ 0` (0=no shrink; >1 reduces impact of huge masses) 
* `per_currency : object` — optional per-ISO-4217 blocks (uppercase 3-letter) overriding any subset of `defaults` for that **currency**; keys **MUST** be valid ISO-4217 codes (uppercase). 
* `overrides : object` — optional **ISO-scoped** adjustments for a given currency:
  • `alpha_iso : { <CCY> : { <ISO2> : number ≥ 0 } }`
  • `min_share_iso : { <CCY> : { <ISO2> : number ∈ [0,1] } }`
  All ISO2 keys **MUST** be uppercase and exist in `iso3166_canonical_2024`. 

**Conformance & hygiene:**

* The loader **MUST** fail closed on **unknown keys**, **duplicate keys**, or values outside domain. 
* All currency codes in `per_currency` and under `overrides.*` **MUST** be uppercase ISO-4217; all ISO2 codes under `overrides.*.*` **MUST** be uppercase and FK-valid to the canonical ISO set. 

**4.3 Override precedence (deterministic resolution)**
For any policy quantity **Q** and a given **currency** `cur` and **ISO** `iso` (when relevant), the effective value is resolved in this exact order:

1. **ISO override**: `overrides.<Q>_iso[cur][iso]` if present (where defined for `Q`), else
2. **Currency override**: `per_currency[cur].<Q>` if present, else
3. **Global default**: `defaults.<Q>`.
   If none exist for required Q, **hard FAIL** (`E_POLICY_MISSING_Q`). (Note: `blend_weight`, `obs_floor`, `shrink_exponent` are resolved at **currency** level only; ISO overrides apply only to `alpha` and `min_share`.) 

**4.4 Parameter hashing (governed-set membership)**

* **Governed files (hash set).** Only `configs/allocation/ccy_smoothing_params.yaml` contributes to `parameter_hash` for S5. Its raw bytes MUST be included in the S0 parameter set that feeds `parameter_hash`; changing its bytes MUST flip `parameter_hash`. No normalization is permitted: hash the exact bytes. No other S5 files contribute unless this spec is amended.
* **Registry alignment:** the artefact registry entry for `ccy_smoothing_params` MUST include its current digest and path; S0 seals that digest into lineage. 
**4.5 Domain ranges & value rules (cross-checks)**

* **Numeric domains (re-stated):** `dp ∈ [0,18]`; `blend_weight ∈ [0,1]`; `alpha ≥ 0`; `obs_floor ≥ 0`; `min_share ∈ [0,1]`; `shrink_exponent ≥ 0`. 
* **Feasibility guard:** For each currency with `min_share_iso` overrides, **Σ_iso `min_share_iso[cur][iso]` ≤ 1.0**; otherwise **hard FAIL** (`E_POLICY_MINSHARE_FEASIBILITY`). 
* **Enumerations:** ISO2 under overrides **MUST** exist in `iso3166_canonical_2024`; placeholders like `XX/ZZ/UNK` are forbidden. 
* **Units & case:** All codes uppercase; policy numbers are parsed as numbers (not strings). 

**4.6 Required presence & defaults**

* **Required keys:** `semver`, `version`, `dp`, `defaults`. Missing any of these is **hard FAIL**. 
* **Optional sections:** `per_currency`, `overrides`. Absence implies no overrides. 
* **Tolerance inheritance:** Where a quantity is not defined at ISO/currency level, the resolver **MUST** fall back per §4.3. 

**4.7 Traceability of overrides (record-keeping contract)**

* S5 **MUST** produce a **per-currency record** of any overrides applied (source = `global|per_currency|iso`, keys, and final effective values) to support the observability metrics enumerated in §14. (Format of metrics is defined in §14; this clause only requires that the information be derivable and emitted.) 

**4.8 Interaction with inputs & dictionary (cross-references)**

* This policy is used to blend **(9)** `settlement_shares_2024Q4` and **(10)** `ccy_country_shares_2024Q4` (both with `Σ share = 1 ± 1e-6` per currency) into `ccy_country_weights_cache` under **parameter scope**; dictionary IDs and schema anchors are binding.   
* The output dataset contract (ID, path, PK) is fixed by the dataset dictionary and `schemas.1A.yaml#/prep/ccy_country_weights_cache`.  

---

# 5. Outputs — datasets & contracts

All outputs in this section are **parameter-scoped** and governed by the **dataset dictionary** and **JSON-Schema** anchors cited below. Readers MUST NOT infer cross-country order from any S5 output (order remains S3’s `candidate_rank`). 

---

## 5.1 `ccy_country_weights_cache` (authority for currency→country weights)

**Dataset ID (dictionary):** `ccy_country_weights_cache`
**Schema authority:** `schemas.1A.yaml#/prep/ccy_country_weights_cache`
**Path & partitions:** `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/` with partitioning **[parameter_hash]**. **Embedded `parameter_hash` MUST equal the path key** (S0 lineage rule).

**Primary key:** `(currency, country_iso)` (unique within each `parameter_hash`). 

**Columns & semantics (must match schema):**

* `currency : ISO4217` (uppercase).
* `country_iso : ISO2` (uppercase; **FK →** `iso3166_canonical_2024.country_iso`).
* `weight : pct01` (numeric in **[0,1]**; **Σ=1** per currency under tolerance).
* `obs_count? : int64 (≥0)` — optional, observations supporting merged/smoothed surface.
* `smoothing? : string` — optional provenance note (e.g., `"alpha=0.5"`). 

**Invariants (binding):**

* **Group sum constraint:** for each `currency`, `Σ weight = 1.0 ± 1e-6` (schema `group_sum_equals_one`).
* **Domain:** codes in ISO domains; `weight∈[0,1]`; `obs_count≥0` when present.
* **Coverage:** for each `currency`, **country set equals the union** of ISO codes present in **`settlement_shares_2024Q4`** and **`ccy_country_shares_2024Q4`**, unless narrowed by policy (recorded via metrics/lineage).
* **Row order:** **no semantic order for readers** (schema `sort_keys: []`). Writers MUST emit rows **sorted `(currency ASC, country_iso ASC)`** for determinism; readers MUST NOT depend on physical order.

**Retention & ownership (dictionary):** retention 365 days; owner `1A`; produced by `1A.expand_currency_to_country`; status `approved`. 


*Path↔embed equality is enforced by the validator; atomic promote is required; no append on re-run.*


---

## 5.2 `merchant_currency` (S5.0 cache of κₘ per merchant)

**Dataset ID (dictionary):** `merchant_currency`
**Schema authority:** `schemas.1A.yaml#/prep/merchant_currency`
**Path & partitions:** `data/layer1/1A/merchant_currency/parameter_hash={parameter_hash}/` with partitioning **[parameter_hash]**. **Embedded `parameter_hash` MUST equal the path key**.

**Primary key:** `(merchant_id)` (unique within each `parameter_hash`). 

**Columns & semantics (must match schema):**

* `merchant_id : id64` (FK to ingress merchants via layer rules).
* `kappa : ISO4217` — settlement currency κₘ.
* `source : enum{"ingress_share_vector","home_primary_legal_tender"}` — provenance.
* `tie_break_used : boolean` — true iff lexicographic tie-break applied. 

**Retention & ownership (dictionary):** retention 365 days; owner `1A`; produced by `1A.derive_merchant_currency`. 

**Cardinality & coverage.** If `merchant_currency` is produced, it MUST contain exactly one row per merchant in the S0 merchant universe (`schemas.ingress.layer1.yaml#/merchant_ids`). Missing or duplicate rows for any `merchant_id` are hard FAIL: `E_MCURR_CARDINALITY`. κₘ MUST be ISO-4217 uppercase; unknown codes are hard FAIL: `E_MCURR_RESOLUTION`.

**Source of truth & fallback.** κₘ is resolved deterministically with provenance in `source`:
- `ingress_share_vector` — κₘ comes from a sealed ingress field or table declared in the dictionary (if such source is listed).
- `home_primary_legal_tender` — κₘ is the primary legal tender of `merchant_ids.home_country_iso` as declared in the dictionary (if listed).
If neither declared source exists in the dictionary for a given deployment, do not produce `merchant_currency`. Producing a partial table is forbidden.

**Interoperability.** `merchant_currency` is optional for S6. When produced, S6 MUST NOT override κₘ; it may only read it as is.

---



## 5.3 `sparse_flag` (per-currency sparsity diagnostics)

**Dataset ID (dictionary):** `sparse_flag`
**Schema authority:** `schemas.1A.yaml#/prep/sparse_flag`
**Path & partitions:** `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/` with partitioning **[parameter_hash]**. **Embedded `parameter_hash` MUST equal the path key**.

**Primary key:** `(currency)` (unique within each `parameter_hash`). 

**Columns & semantics (must match schema):**

* `currency : ISO4217` (uppercase).
* `is_sparse : boolean` — true iff observations below policy threshold.
* `obs_count : int64 (≥0)` — observed mass used in the decision.
* `threshold : int64 (≥0)` — cutoff used. 

**Retention & ownership (dictionary):** retention 365 days; produced by `1A.expand_currency_to_country`; consumed by 1A/validation. 

---

## 5.4 Partitioning, paths, and lineage (common to all S5 outputs)

* **Partitioning law:** **parameter-scoped only**; S5 outputs MUST NOT include `{seed}` or `{fingerprint}` partitions. Paths MUST be exactly those in the dictionary; **path↔embed equality** is required for `parameter_hash`.
* **Immutability & write semantics:** Partitions are **write-once**. Any retry stages under a temp path and atomically promotes on success (S0 rule). Re-runs with identical inputs/policy MUST yield **byte-identical** content. 
* **Schema authority:** Only **JSON-Schema** anchors cited above are authoritative for fields, domains, PK/FK, and the Σ constraint. Avro (if any) is non-authoritative. 

---

## 5.5 Coverage & join contracts (downstream read expectations)


---

## 5.6 Validity constraints (Σ and domains)

* For `ccy_country_weights_cache`, validators MUST enforce the schema constraint: per currency, `Σ weight = 1.0 ± 1e-6`, with all codes FK-valid to the canonical ISO table. (This mirrors the ingress constraints on the two input share surfaces.)
* *Path↔embed equality is enforced by the validator; atomic promote is required; no append on re-run.*

* **Weights authority:** `ccy_country_weights_cache` is the **only** persisted authority for **currency→country weights**. Downstream MAY restrict to a merchant’s candidate set from S3 and renormalise **ephemerally**; persisted weights remain S5’s authority. 
* **Order authority:** Inter-country order MUST be read only from **`s3_candidate_set.candidate_rank`**; S5 outputs MUST NOT be used to infer order. 

---

## 5.6 Validity constraints (Σ and domains)

* For `ccy_country_weights_cache`, validators MUST enforce the **schema constraint**: per currency, `Σ weight = 1.0 ± 1e-6`, with all codes FK-valid to the canonical ISO table. (This mirrors the ingress constraints on the two input share surfaces.)

---

# 6. Deterministic processing specification — no pseudocode

> This section fixes **what must be computed and how it must behave**, without prescribing implementation code. All math is **IEEE-754 binary64** until the final quantisation step. JSON-Schema remains the single authority for all field types and constraints. 

## 6.1 Currency scope & country-set construction

* **Per-currency working set.** For each `currency`, form the **union** of `country_iso` present in **(9)** `settlement_shares_2024Q4` and **(10)** `ccy_country_shares_2024Q4`. Missing pairs are treated as **share=0, obs_count=0** for that surface. **Duplicates are forbidden** by the inputs’ PK rule. Writers must process the union in **`country_iso` A→Z** order (determinism); readers must not rely on file order.
* **Domain & FK.** All `country_iso` values **must** be uppercase ISO-3166 and FK-valid to `iso3166_canonical_2024`. All `currency` values **must** be uppercase ISO-4217. These are inherited ingress constraints S5 **validates** before any processing (§3). 

## 6.2 Numeric type & blending of share surfaces

* **Numeric type:** All arithmetic through §6.6 is in **binary64**. 
* **Blending rule (per currency).** Let `w ∈ [0,1]` be the effective `blend_weight` resolved by §4.3. For each `country_iso` in the union:
  **`q[c] = w · s_ccy[c] + (1−w) · s_settle[c]`** (missing shares treated as 0). 
* **Input discipline:** Each input surface must already satisfy **Σ share = 1.0 ± 1e-6** per currency; S5 does not repair ingress (§3.3/§3.4). 

## 6.3 Effective evidence mass (sparsity robustness)

* Compute a per-currency effective mass from observed counts:
  **`N0 = w · Σ n_ccy + (1−w) · Σ n_settle`** and **`N_eff = max(obs_floor, N0^(1/shrink_exponent))`** with `shrink_exponent ≥ 0` (policy). `shrink_exponent = 1.0` ⇒ `N_eff = max(obs_floor, N0)`. 

## 6.4 Prior / smoothing policy (Dirichlet-style add-α)

* Resolve **α** using §4 precedence: base per-currency `alpha` with optional **per-ISO** overrides. Let **`α[c] ≥ 0`**, and **`A = Σ_c α[c]`**.
* Compute the **smoothed posterior** per ISO (binary64):
  **`posterior[c] = ( q[c] · N_eff + α[c] ) / ( N_eff + A )`.** 

## 6.5 Floors & feasibility (apply then prove)

* Resolve **minimum shares** per §4 (`min_share` global, with optional **`min_share_iso`** per currency/ISO). For each country:
  **`p′[c] = max( posterior[c], min_share_for_c )`.**
* **Feasibility:** For every currency with any ISO-level floors, it **must** hold that
  **`Σ_c min_share_iso[cur][c] ≤ 1.0`** (policy guard). Otherwise **hard FAIL** (`E_POLICY_MINSHARE_FEASIBILITY`). 

## 6.6 Renormalisation (Σ = 1 before quantisation)

* **Required renormalisation (binary64):** After floors, compute a single normaliser **`Z = Σ_c p′[c]`** and set **`p[c] = p′[c] / Z`** for all countries of the currency so that **`Σ_c p[c] = 1`** in binary64. Renormalisation **must occur after floors** and **before** any quantisation. 



**Persistence type.** `weight` is persisted as a numeric (`pct01`) per schema; the decimal exact-sum at `dp` requirement is a property of the quantised values, not of storing strings. Pre-quant arithmetic remains binary64 with tolerances per §3.3/§7.4; post-quant the decimal sum MUST equal exactly `1` at `dp` after tie-break.
s_count : int64 (≥0)` — observed mass used in the decision.
* `threshold : int64 (≥0)` — cutoff used. 

**Retention & ownership (dictionary):** retention 365 days; produced by `1A.expand_currency_to_country`; consumed by 1A/validation. 

---

## 5.4 Partitioning, paths, and lineage (common to all S5 outputs)

* **Partitioning law:** **parameter-scoped only**; S5 outputs MUST NOT include `{seed}` or `{fingerprint}` partitions. Paths MUST be exactly those in the dictionary; **path↔embed equality** is required for `parameter_hash`.
* **Immutability & write semantics:** Partitions are **write-once**. Any retry stages under a temp path and atomically promotes on success (S0 rule). Re-runs with identical inputs/policy MUST yield **byte-identical** content. 
* **Schema authority:** Only **JSON-Schema** anchors cited above are authoritative for fields, domains, PK/FK, and the Σ constraint. Avro (if any) is non-authoritative. 

---

## 5.5 Coverage & join contracts (downstream read expectations)


---

## 5.6 Validity constraints (Σ and domains)

* For `ccy_country_weights_cache`, validators MUST enforce the schema constraint: per currency, `Σ weight = 1.0 ± 1e-6`, with all codes FK-valid to the canonical ISO table. (This mirrors the ingress constraints on the two input share surfaces.)
* *Path↔embed equality is enforced by the validator; atomic promote is required; no append on re-run.*

* **Weights authority:** `ccy_country_weights_cache` is the **only** persisted authority for **currency→country weights**. Downstream MAY restrict to a merchant’s candidate set from S3 and renormalise **ephemerally**; persisted weights remain S5’s authority. 
* **Order authority:** Inter-country order MUST be read only from **`s3_candidate_set.candidate_rank`**; S5 outputs MUST NOT be used to infer order. 

---

## 5.6 Validity constraints (Σ and domains)

* For `ccy_country_weights_cache`, validators MUST enforce the **schema constraint**: per currency, `Σ weight = 1.0 ± 1e-6`, with all codes FK-valid to the canonical ISO table. (This mirrors the ingress constraints on the two input share surfaces.)

---

# 6. Deterministic processing specification — no pseudocode

> This section fixes **what must be computed and how it must behave**, without prescribing implementation code. All math is **IEEE-754 binary64** until the final quantisation step. JSON-Schema remains the single authority for all field types and constraints. 

## 6.1 Currency scope & country-set construction

* **Per-currency working set.** For each `currency`, form the **union** of `country_iso` present in **(9)** `settlement_shares_2024Q4` and **(10)** `ccy_country_shares_2024Q4`. Missing pairs are treated as **share=0, obs_count=0** for that surface. **Duplicates are forbidden** by the inputs’ PK rule. Writers must process the union in **`country_iso` A→Z** order (determinism); readers must not rely on file order.
* **Domain & FK.** All `country_iso` values **must** be uppercase ISO-3166 and FK-valid to `iso3166_canonical_2024`. All `currency` values **must** be uppercase ISO-4217. These are inherited ingress constraints S5 **validates** before any processing (§3). 

## 6.2 Numeric type & blending of share surfaces

* **Numeric type:** All arithmetic through §6.6 is in **binary64**. 
* **Blending rule (per currency).** Let `w ∈ [0,1]` be the effective `blend_weight` resolved by §4.3. For each `country_iso` in the union:
  **`q[c] = w · s_ccy[c] + (1−w) · s_settle[c]`** (missing shares treated as 0). 
* **Input discipline:** Each input surface must already satisfy **Σ share = 1.0 ± 1e-6** per currency; S5 does not repair ingress (§3.3/§3.4). 

## 6.3 Effective evidence mass (sparsity robustness)

* Compute a per-currency effective mass from observed counts:
  **`N0 = w · Σ n_ccy + (1−w) · Σ n_settle`** and **`N_eff = max(obs_floor, N0^(1/shrink_exponent))`** with `shrink_exponent ≥ 0` (policy). `shrink_exponent = 1.0` ⇒ `N_eff = max(obs_floor, N0)`. 

## 6.4 Prior / smoothing policy (Dirichlet-style add-α)

* Resolve **α** using §4 precedence: base per-currency `alpha` with optional **per-ISO** overrides. Let **`α[c] ≥ 0`**, and **`A = Σ_c α[c]`**.
* Compute the **smoothed posterior** per ISO (binary64):
  **`posterior[c] = ( q[c] · N_eff + α[c] ) / ( N_eff + A )`.** 

## 6.5 Floors & feasibility (apply then prove)

* Resolve **minimum shares** per §4 (`min_share` global, with optional **`min_share_iso`** per currency/ISO). For each country:
  **`p′[c] = max( posterior[c], min_share_for_c )`.**
* **Feasibility:** For every currency with any ISO-level floors, it **must** hold that
  **`Σ_c min_share_iso[cur][c] ≤ 1.0`** (policy guard). Otherwise **hard FAIL** (`E_POLICY_MINSHARE_FEASIBILITY`). 

## 6.6 Renormalisation (Σ = 1 before quantisation)

* **Required renormalisation (binary64):** After floors, compute a single normaliser **`Z = Σ_c p′[c]`** and set **`p[c] = p′[c] / Z`** for all countries of the currency so that **`Σ_c p[c] = 1`** in binary64. Renormalisation **must occur after floors** and **before** any quantisation. 

## 6.7 Quantisation for output (fixed-dp; deterministic tie-break)

* **Fixed-dp rounding:** Convert `p[c]` to **`weight`** in **fixed-dp** with the configured `dp` using **round-half-even** (no other rounding mode allowed). 
* **Group-sum property at dp.** After rounding, the **decimal** sum **MUST** equal **`1` to exactly `dp` places**. If direct half-even rounding induces a residual drift, apply a **deterministic largest-remainder placement** of ±1 ULP adjustments on the rounded decimal values **within the currency** until the decimal sum equals **`1`** at `dp`.
  **Tie-break order (closed):** sort candidates by **descending** fractional remainder (pre-round), then **`country_iso` A→Z**. This rule ensures **byte-identical** outputs across runs and shard counts. *(This is stricter than the schema’s tolerance and is required by this spec.)* 

## 6.8 Determinism requirements (no RNG; stable evaluation)

* **RNG prohibition:** S5 **MUST NOT** emit or consume any RNG events or alter RNG traces. 
* **Stable iteration:** Processing is defined **per currency**; within a currency, the canonical **evaluation order is `country_iso` A→Z**. Parallelism is **permitted by currency** only; merges **MUST** preserve `(currency ASC, country_iso ASC)` writer order. 
* **Numeric consistency:** Use binary64 throughout; no alternative rounding or fused-multiply-add modes on decision paths (inherits S0 numeric policy). 

## 6.9 Idempotence & re-run semantics

* **Byte-identity:** Given identical inputs and **identical policy bytes** (contributing to `parameter_hash`), S5 **MUST** produce **byte-identical** outputs (rows, values, and file boundaries) at the same parameter-scoped path(s). 
* **Path↔embed equality:** For every S5 dataset, embedded `parameter_hash` **MUST** equal the path partition key **byte-for-byte**. 
* **Writer sort:** Writers **MUST** emit rows sorted `(currency ASC, country_iso ASC)`; readers **MUST NOT** treat file order as authoritative. 

## 6.10 Coverage rule (what rows must exist)

* **Per-currency coverage:** The set of `country_iso` emitted for each `currency` **MUST** equal the **union** of countries observed in (9) and (10), unless **explicitly narrowed by policy** recorded in lineage/metrics. Any narrowing must be **discoverable** via §14 metrics and §10 lineage. 

---

# 7. Invariants & integrity constraints

> These properties **must hold** for all S5 outputs at the time the PASS gate in §9 is computed. Where a rule duplicates a JSON-Schema constraint, the **schema remains authoritative**; this section makes those constraints explicit for operators and downstream specs.

**7.1 Schema & dictionary conformance**

* Every S5 dataset (`ccy_country_weights_cache`, `merchant_currency`, `sparse_flag`) **MUST** pass its JSON-Schema anchor from `schemas.1A.yaml`, and match the dataset dictionary’s ID, path pattern, partitions and ownership.

**7.2 Primary keys & uniqueness**

* `ccy_country_weights_cache` **PK** is `(currency, country_iso)` and **MUST** be unique within each `parameter_hash` partition.
* `merchant_currency` **PK** is `(merchant_id)`; `sparse_flag` **PK** is `(currency)`. 

**7.3 Domains & foreign keys**

* Codes **MUST** be uppercase and valid in their enumerations: `currency ∈ ISO-4217`, `country_iso ∈ ISO-3166-1 α-2` with FK to the canonical ISO table.
* Numeric domains: `weight ∈ [0,1]`; when present, `obs_count ≥ 0`. 

**7.4 Group-sum constraint (per currency)**

* In `ccy_country_weights_cache`, the **schema group constraint** MUST hold: for each `currency`, `Σ weight = 1.0` within tolerance `1e-6`. (This mirrors the ingress constraints on the two input share surfaces.)

**7.5 Coverage parity**

* For each `currency`, the set of `country_iso` values present in `ccy_country_weights_cache` **MUST equal** the **union** of `country_iso` observed for that currency in `settlement_shares_2024Q4` and `ccy_country_shares_2024Q4`, except where explicitly narrowed by S5 policy (recorded via lineage/metrics).

**7.6 Quantisation & dp exactness (output discipline)**

* Although `weight` is stored as a numeric (`pct01`), each value **MUST** be the round-half-even quantisation of the pre-quantised probability to the configured **`dp`** from S5 policy; when the `weight`s are expressed to exactly `dp` decimal places as strings, their **decimal sum MUST equal `1` at `dp`**. (This is stricter than the schema tolerance and is required by this spec.) 

**7.7 Sorting & deterministic writer order**

* Physical row order is **not** an interface guarantee (dictionary `ordering: []`), but writers **MUST** emit rows sorted `(currency ASC, country_iso ASC)` to ensure byte-stable reruns; readers MUST NOT rely on file order. 

**7.8 Partitioning, lineage & equality**

* All S5 datasets are **parameter-scoped only**; no `{seed}` or `{fingerprint}` partitions are permitted.
* **Path↔embed equality:** the embedded `parameter_hash` column **MUST equal** the partition key byte-for-byte.
* **Immutability & idempotence:** a concrete `parameter_hash` partition is **write-once**; reruns with identical inputs + policy bytes produce **byte-identical** results. 

**7.9 RNG non-interaction**

* S5 **MUST NOT** emit any `rng_*` streams or alter RNG traces; the RNG log families defined for Layer-1 remain untouched across S5. The validator in §9 MUST be able to demonstrate no change in RNG trace length versus the S4 manifest. 

**7.10 Order authority separation (no implicit order in S5)**

* Inter-country order is **owned by S3** only (`s3_candidate_set.candidate_rank`). S5 outputs **MUST NOT** encode, imply, or be used to infer inter-country order; `outlet_catalogue` continues to omit cross-country order by design.

**7.11 Egress/readiness dependency**

* Downstream readers **MUST** only consume S5 outputs once the S5 PASS artefact (defined in §9) exists for the **same `parameter_hash`** (**no PASS → no read**), consistent with Layer-1 gating norms. 

**7.12 Diagnostics visibility**

* If `sparse_flag` is emitted, its PK and domain constraints must hold (`currency` valid; `is_sparse` boolean; `obs_count, threshold ≥ 0`), and it lives under the same `parameter_hash`. 

---

# 8. Error handling, edge cases & degrade ladder

> This section defines **run-fail conditions** (hard FAIL), **per-currency degradations** (allowed fallbacks), and the **diagnostics** that MUST be produced. Where rules duplicate JSON-Schema or dictionary constraints, the schema/dictionary remain authoritative.

## 8.1 Pre-flight hard FAIL (ingress)

S5 MUST **abort the run** before writing any outputs if **either** share surface violates its ingress contract (§3). Violations include:

* PK collision on `(currency,country_iso)`; unknown or non-uppercase `ISO2/ISO-4217`; `share∉[0,1]`; `obs_count<0`; or **Σ share ≠ 1.0 ± 1e-6** per currency. **Error:** `E_INPUT_SCHEMA` / `E_INPUT_SUM`.

## 8.2 Policy file errors (hard FAIL)

S5 MUST fail closed on any policy/config non-conformance:

* Unknown keys; values outside domains (`dp∈[0,18]`, `blend_weight∈[0,1]`, `alpha≥0`, `obs_floor≥0`, `min_share∈[0,1]`, `shrink_exponent≥0`). **Error:** `E_POLICY_DOMAIN`. 
* Unknown **currency** or **ISO** in overrides (not in canonical enumerations). **Error:** `E_POLICY_UNKNOWN_CODE`. 
* **Feasibility breach:** for any currency, `Σ min_share_iso > 1.0`. **Error:** `E_POLICY_MINSHARE_FEASIBILITY`. 

## 8.3 Processing-time hard FAIL (per currency → run abort)

If any of the following occur for any currency during §6:

* **Zero mass after floors:** `Σ p′[c] = 0` before renormalisation. **Error:** `E_ZERO_MASS`.
* **Renormalisation/quantisation failure:** after §6.7 tie-breaks, the **decimal** group sum cannot be made exactly `1` at `dp`. **Error:** `E_QUANT_SUM_MISMATCH`.
* **Output schema breach:** FK/PK violation, domain breach (`weight∉[0,1]`, negative `obs_count`). **Error:** `E_OUTPUT_SCHEMA`.
  The run MUST abort; S5 produces no partial outputs. 

## 8.4 Missing/partial source surfaces (per-currency degrade)

If, for a given currency:

* **Only** `ccy_country_shares_2024Q4` has rows (Σ=1 within tolerance) and `settlement_shares_2024Q4` has **none**, S5 MAY proceed using the available surface with **degrade_mode=`ccy_only`**. **Reason code:** `SRC_MISSING_SETTLEMENT`. 
* **Only** `settlement_shares_2024Q4` has rows (Σ=1) and `ccy_country_shares_2024Q4` has **none**, S5 MAY proceed with **degrade_mode=`settlement_only`**. **Reason code:** `SRC_MISSING_CCY`. 
* **Neither** surface contains the currency ⇒ currency is **out of scope** (no output rows). If policy explicitly references the currency, **hard FAIL** `E_POLICY_UNKNOWN_CODE`. Otherwise, no rows are written for that currency and no degrade is logged. 

**Contract:** Degraded currencies MUST still satisfy §6.1 union coverage (union is the non-empty source’s support), §6.6 Σ=1 (binary64 pre-quant), and §6.7 exact decimal Σ at `dp`. 

## 8.5 Sparsity handling (diagnostic, not degrade)

Low-evidence situations (small `N_eff` under §6.3) are handled via **policy floor/α smoothing**; this is **not** a degrade. Emit `sparse_flag` where the policy threshold marks a currency as sparse; persist under `parameter_hash`. **Reason code in metrics:** `SPARSITY_LOW_MASS`.

## 8.6 Coverage narrowing by policy (allowed)

If policy explicitly **narrows** the country set for a currency (e.g., removing specific ISOs), S5 MAY proceed **provided**:

* Narrowing is discoverable via lineage/metrics (§10/§14), and
* The resulting set still passes §6.6/§6.7 (Σ=1 rules).
  **Reason code:** `POLICY_NARROWING`. (No change to **degrade_mode**, which remains `none`.) 

## 8.7 Degrade vocabulary & emission (per-currency)

When a per-currency degrade in **8.4** is used, S5 MUST:

* Record **`degrade_mode ∈ {none, settlement_only, ccy_only, abort}`** and **`degrade_reason_code`** (closed set: `{SRC_MISSING_SETTLEMENT, SRC_MISSING_CCY, POLICY_NARROWING}` plus `OTHER` as last resort) in run-level metrics (§14).
* Ensure outputs still satisfy §7 invariants; otherwise escalate to **`abort`** (run FAIL). 

## 8.8 RNG non-interaction breaches (hard FAIL)

Any presence of `rng_*` streams written under S5 tasking, or a **change in RNG trace length** vs the S4 manifest, is a breach. **Error:** `E_RNG_INTERACTION`. 

## 8.9 Path/lineage equality breaches (hard FAIL)

Mismatch between embedded `parameter_hash` and the partition path key for any S5 dataset, or any write that violates **write-once/atomic-promote** semantics, MUST abort. **Error:** `E_LINEAGE_PATH_MISMATCH` / `E_ATOMICITY`. 

## 8.10 Diagnostics artefacts (minimal, parameter-scoped)

S5 MUST emit, alongside outputs:

* A **validation report** (format free) listing per-currency `degrade_mode`, `degrade_reason_code`, Σ checks pre/post quantisation, and any policy overrides in force (to support §14 metrics).
* Optional `sparse_flag` dataset per dictionary (`schema_ref: #/prep/sparse_flag`). 

## 8.11 Run outcome

* **PASS:** No hard FAILs; all outputs meet §7; diagnostics present; (some currencies may have `degrade_mode ≠ none`).
* **FAIL:** Any error in 8.1–8.3, 8.8–8.9, or invariant breach → **no read** by downstream until Section §9 PASS is recorded for the same `parameter_hash`. 

---

# 9. Validation battery & PASS gate

> The S5 validator proves that `ccy_country_weights_cache` (and any S5 side outputs) meet schema, lineage, coverage, Σ, and determinism obligations. It is a **parameter-scoped** gate for S6 reads, distinct from the layer-wide **fingerprint-scoped** gate used for egress (kept as-is per S0/S4). JSON-Schema and the dataset dictionary remain the single authorities for field shapes and paths.

## 9.1 Structural & lineage checks (must pass before any content checks)

1. **Schema conformance.** Every S5 dataset passes its JSON-Schema anchor (e.g., `schemas.1A.yaml#/prep/ccy_country_weights_cache`). Fail closed on any field/type/nullable/required mismatch. 
2. **PK/FK & domains.**
   – `ccy_country_weights_cache` has unique **PK** `(currency, country_iso)`; `currency ∈ ISO-4217`, `country_iso ∈ ISO2` and FK-valid to canonical ISO. 
   – If present, `merchant_currency` and `sparse_flag` obey their PKs and domains. 
3. **Partition & path discipline.** Parameter-scoped outputs live under `…/parameter_hash={parameter_hash}/` and **embed the same `parameter_hash`** byte-for-byte. Writes are **atomic** (stage→fsync→single rename). 
4. **No RNG interaction.** No `rng_*` streams for S5; RNG trace length is **unchanged** vs S4’s manifest. Any delta is a run-fail.

## 9.2 Content checks (weights, sums, quantisation)

1. **Σ rule (numeric).** For each `currency`, the **numeric** sum `Σ weight` equals **1.0 ± 1e-6** (schema group constraint). 
2. **Quantisation discipline.** Re-express each `weight` to exactly `dp` decimal places (policy §4). The **decimal** sum must equal **`1` at `dp`** after the deterministic largest-remainder tie-break; dp used in the run must match policy. 
3. **Bounds.** `0 ≤ weight ≤ 1` and (when present) `obs_count ≥ 0`. 

## 9.3 Coverage & join-shape checks

1. **Union coverage.** For each currency, the set of `country_iso` in `ccy_country_weights_cache` equals the **union** of `country_iso` seen for that currency in `settlement_shares_2024Q4` and `ccy_country_shares_2024Q4`, unless policy **explicitly narrows** (which MUST be recorded in lineage/metrics).
2. **No order implication.** S5 outputs encode **no inter-country order**; downstream must keep reading order exclusively from S3 `s3_candidate_set.candidate_rank`. 

## 9.4 Re-derivation check (no re-derive elsewhere, but validator must prove identity)

The validator **recomputes** the S5 weights from sealed inputs + S5 policy, using the normative rules of §6 (binary64 math; blend; effective mass; α-smoothing; floors; renormalise; quantise+tie-break). It then asserts **byte-for-byte equality** of per-pair decimal values at `dp` (and equality of country coverage). Any mismatch is a **run-fail**. 

## 9.5 Degrade & overrides attestation

If §8’s degrade modes are exercised (`settlement_only` / `ccy_only`) or if any ISO/currency overrides applied, the validator must emit machine-readable **per-currency** attestations (source, reason code, effective values) and ensure **all** invariants in §7 still hold; otherwise abort. 

## 9.6 Validator artefacts (parameter-scoped receipt for S5)

S5 writes a **parameter-scoped receipt** adjacent to the weights cache:

```
data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/
  S5_VALIDATION.json            # summary: counts, Σ checks, coverage parity, overrides, degrade modes
  _passed.flag                  # single line: 'sha256_hex = <hex64>'
```

`_passed.flag` contains the **SHA-256** over the **ASCII-lexicographic** concatenation of all other files in this small receipt (exclude the flag itself). This mirrors the layer-wide gate pattern in S0’s validation bundle, but is **parameter-scoped** for S5. **Atomic publish** applies. 

*Notes.*
– This S5 receipt **does not replace** the 1A **fingerprint-scoped** validation bundle (`validation_bundle_1A`) and its `_passed.flag`; that layer-wide gate remains the authority for egress consumption (e.g., `outlet_catalogue`). 
– The dictionary continues to govern dataset paths; the S5 receipt is a **sidecar manifest** within the approved dataset path, consistent with S0’s publish/atomicity discipline. 

## 9.7 PASS/FAIL semantics

* **S5 PASS (parameter-scoped):** All checks in §§9.1–9.5 succeed **and** the S5 receipt is present with a valid `_passed.flag` whose hash matches its contents. Downstream parameter-scoped readers (**e.g., S6**) MUST verify this receipt **for the same `parameter_hash`** before reading (`no PASS → no read`). 
* **Layer-wide PASS (unchanged):** For egress reads (e.g., `outlet_catalogue`), consumers MUST verify `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/_passed.flag` matches `validation_bundle_1A` for that fingerprint, per S0. 
* **FAIL:** Any breach in §§9.1–9.5, or missing/invalid `_passed.flag`, aborts the run; no partial publishes. Follow S0 abort semantics (write failure sentinel; freeze; exit non-zero). 

## 9.8 Minimal validator report content (normative fields)

`S5_VALIDATION.json` MUST include at least:

* `parameter_hash` (Hex64); `policy_digest` (Hex64 of `ccy_smoothing_params.yaml` bytes). 
* `currencies_processed`, `rows_written`, `degrade_mode_counts{none,settlement_only,ccy_only}`. 
* `sum_check`: counts of currencies passing the numeric Σ test and the **decimal @dp** test.
* `coverage_check`: counts passing union-coverage (and a list of any policy-narrowed currencies). 
* `overrides_applied`: per-currency summary (source: `global|per_currency|iso`). (Detailed metrics format in §14.)

## 9.9 Idempotence & re-run equivalence

Re-running S5 with identical inputs and **identical policy bytes** produces **byte-identical** dataset content and **identical** S5 receipt (and `_passed.flag`). Any divergence is a failure of idempotence. 

---

# 10. Lineage, partitions & identifiers

> This section fixes **where S5 writes**, **which identifiers appear**, and the **immutability/atomicity** rules. JSON-Schema + the Dataset Dictionary remain the single authorities for shapes, paths, and partition keys.

**10.1 Partitioning law (parameter-scoped only)**

* All S5 datasets are **parameter-scoped** with **partition key = `parameter_hash`**. No `{seed}` or `{fingerprint}` partitions are permitted for S5 outputs. The dictionary pins the paths and partitions:
  – `ccy_country_weights_cache → data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/` with `partitioning: [parameter_hash]`. 
  – `merchant_currency → data/layer1/1A/merchant_currency/parameter_hash={parameter_hash}/` with `partitioning: [parameter_hash]`. 
  – `sparse_flag → data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/` with `partitioning: [parameter_hash]`. 
  The **contrast** (for clarity): RNG/egress families are **not** in scope here and remain `{seed,parameter_hash,run_id}` or `{seed,fingerprint}` per S0/S3/S9.

**10.2 Embedded lineage fields & path↔embed equality**

* Where a schema **includes** lineage columns, their values are **normative**:
  – `parameter_hash` **MUST equal** the partition key byte-for-byte (hex64).
  – `produced_by_fingerprint?` (if present in the schema) is **informational only** and MUST equal the run’s `manifest_fingerprint` when populated. 
* S0’s partition lint applies: parameter-scoped datasets live under `parameter_hash=…` and **rows embed the same `parameter_hash`** wherever the schema defines that column. 
* Readers MUST treat **physical file order as non-authoritative** (dictionary `ordering: []`). Writers emit rows sorted `(currency ASC, country_iso ASC)` for byte-stable reruns (§6.8/§7.7). 

**10.3 Identifier semantics (source of truth)**

* **`parameter_hash` (Hex64)** — the **only** partition key for S5 outputs; produced by S0 as SHA-256 over the governed parameter-set bytes (policy files included). Changing `ccy_smoothing_params.yaml` **MUST** flip `parameter_hash`.
* **`manifest_fingerprint` (Hex64)** — global run fingerprint used by the **layer-wide** validation bundle (`validation_bundle_1A`). S5 is parameter-scoped; any `produced_by_fingerprint` field, when present, is optional provenance only. 
* **`run_id`** — used only in RNG logs (not produced by S5). 

**10.4 Paths & schemas (authority alignment)**

* Paths and partition keys for S5 datasets **MUST** match the Dataset Dictionary entries and their schema anchors:
  – `ccy_country_weights_cache → schemas.1A.yaml#/prep/ccy_country_weights_cache` (PK `(currency,country_iso)`, partition_keys `[parameter_hash]`).
  – `merchant_currency → schemas.1A.yaml#/prep/merchant_currency` (PK `(merchant_id)`, partition_keys `[parameter_hash]`).
  – `sparse_flag → schemas.1A.yaml#/prep/sparse_flag` (PK `(currency)`, partition_keys `[parameter_hash]`).
* **JSON-Schema remains authoritative** for lineage columns: some tables enumerate `parameter_hash` explicitly; others declare it as a `partition_keys` property. Both are binding, and S0’s partition lint enforces equality to the path. 

**10.5 Immutability & atomic publish**

* **Write-once per partition.** A concrete `parameter_hash` partition is immutable; re-runs with identical inputs/policy must be **byte-identical** or no-op. 
* **Atomic publish.** Writers MUST stage to a temporary folder and perform a single atomic rename; partial contents MUST NOT become visible. (Same rule S0 uses for validation bundles.) 

**10.6 Retry & promotion semantics**

* Retries write under a temp path; **promotion occurs only after** Section 9 PASS succeeds for the same `parameter_hash` (S5 receipt present and valid). Any earlier partial directories must be removed or remain hidden (no readers). 

**10.7 Scope separation (no seed/fingerprint in S5 outputs)**

* S5 outputs **MUST NOT** introduce `{seed}` or `{fingerprint}` path tokens. Those are reserved for RNG/event logs and egress hand-off datasets such as `outlet_catalogue` (fingerprint-scoped). 

**10.8 Registry & dictionary consistency (governance)**

* The **artefact registry** entries for `ccy_country_weights_cache`, `merchant_currency`, `sparse_flag`, and `ccy_smoothing_params` MUST exist and reflect path, version (`{parameter_hash}`), and schema refs exactly.
* The **dataset dictionary** is the single authority for dataset **IDs, paths, partitioning, owners, and retention**; S5 must not deviate. 

**10.9 Downstream gates (read discipline)**

* **Parameter-scoped readers (e.g., S6)** MUST verify the **S5 receipt** under the same `parameter_hash` before reading (§9). Layer-wide egress readers (e.g., `outlet_catalogue`) remain gated by the **fingerprint-scoped** `_passed.flag` in `validation_bundle_1A` (unchanged by this spec).

---

# 11. Interaction with RNG & logs

> S5 is **purely deterministic** and **RNG-free**. This section fixes what S5 MUST and MUST NOT do with respect to Layer-1 RNG audit/event infrastructure and trace logs. JSON-Schema for RNG envelopes and the dataset dictionary remain the single authorities for shapes, partitions, and producers.

**11.1 RNG event prohibition (no emissions)**

* S5 **MUST NOT** emit any dataset whose schema is under **`schemas.layer1.yaml#/rng/*`** (i.e., no `rng_audit_log`, `rng_trace_log`, or any `rng_event_*` streams). This includes all event families registered in the dictionary (e.g., `hurdle_bernoulli`, `gamma_component`, `poisson_component`, `gumbel_key`, `dirichlet_gamma_vector`, `residual_rank`, `sequence_finalize`, `site_sequence_overflow`).

**11.2 No writes under RNG partitions**

* S5 **MUST NOT** write to paths partitioned by **`{seed, parameter_hash, run_id}`** reserved for RNG audit, trace, and event logs; those paths are owned by S1/S2/S4/S6/S7/S8 producers per the dataset dictionary. S5 outputs are **parameter-scoped only** (§10). 

**11.3 No consumption of RNG logs**

* S5 **MUST NOT** read `rng_audit_log`, `rng_trace_log`, or `rng_event_*` streams. S5’s computation depends only on the ingress share surfaces and S5 policy (§3–§4). 

**11.4 Trace invariants (proof of non-interaction)**

* The **cumulative RNG trace** (per `(module, substream_label)`) defined by `rng_trace_log` **MUST** be **unchanged** across an S5 run relative to the preceding S4 manifest: totals (`events_total`, `draws_total`, `blocks_total`) and final `(before/after)` counters per key are **identical**. Any delta indicates an RNG interaction and is a **run-fail** (§9).

**11.5 Envelope & budgeting law (reference; S5 does not produce)**

* RNG events, when produced by other states, must carry the **Layer-1 RNG envelope** (counters, `blocks`, `draws`), with **open-interval** uniform mapping and budget identities enforced by S0/S1/S4. S5 inherits these rules only as constraints it must **not** exercise.

**11.6 S4 trace duty remains intact**

* S4’s contract (“append exactly one cumulative `rng_trace_log` row **after each event append**”) remains authoritative; S5 SHALL NOT append additional trace rows nor alter S4’s trace.

**11.7 Producer/label registry (non-membership of S5)**

* The dataset dictionary enumerates **producer modules** and **`substream_label`** values for 1A RNG streams. S5 is **not** a registered RNG producer and MUST NOT appear as `module` in any RNG JSONL event. 

**11.8 Validation of non-interaction (gate condition)**

* The S5 validator (§9) MUST assert **both**:
  (a) **Absence** of any new/modified files under `logs/rng/**/seed=*/parameter_hash=*/run_id=*` for the run; and
  (b) **Unchanged** final rows in `rng_trace_log` (per key) vs the S4 manifest. Any breach ⇒ `E_RNG_INTERACTION` (hard FAIL). 

**11.9 Separation from order authority**

* RNG-bearing selection/ordering streams (e.g., `gumbel_key`) remain downstream concerns (S6+). S5 MUST NOT encode or imply order, nor interact with those RNG events. Order authority remains **S3 `s3_candidate_set.candidate_rank`**.

---

# 12. Performance, scaling & resource envelope

> Purpose: bound runtime behaviour and concurrency *without* dictating implementation internals. All numeric and determinism rules in §6 remain in force.

**12.1 Expected cardinalities** *(Informative)*

* Currencies in scope: O(10²).
* Countries per currency (union of the two ingress surfaces): O(10²); practical maximum ≲ a few ×10².
* Total pairs processed per run: O(currencies × countries) → typically ≤ O(10⁴–10⁵).
* Policy overrides: sparse relative to total pairs (expected << 10%).

**12.2 Concurrency scope & determinism** *(Binding)*

* **Concurrency boundary:** Parallelism is **per currency only** (no parallel reductions within a single currency). (§6.8)
* **Deterministic merge:** Independent currency shards **MUST** converge to outputs that are **byte-identical** to a single-threaded run, with writer order `(currency ASC, country_iso ASC)`. (§6.8/§7.7)
* **Within-currency evaluation:** The effective computation **MUST** be equivalent to evaluating §6.1–§6.7 in `country_iso` A→Z order using binary64, then applying the §6.7 tie-break. No alternative evaluation order is permitted.
* **Shard-count invariance:** Changing the number of worker shards **MUST NOT** change any output byte.

**12.3 Time complexity** *(Informative)*

* End-to-end runtime is **linear** in the number of input rows plus output rows:
  `T(run) = Θ(|settlement_shares| + |ccy_country_shares| + |weights_cache|)`.
* Per-currency work is Θ(#countries in that currency).

**12.4 Memory envelope** *(Informative)*

* Per-currency working set is O(#countries) for a small number of vectors (blend `q`, priors `α`, floors, `p′`, `p`).
* Implementations SHOULD bound peak memory by processing **one currency at a time** (or a small batch) and streaming rows; global, all-currency in-memory accumulation is discouraged.

**12.5 I/O & file layout** *(Informative)*

* Inputs are reference tables (no partitions); outputs are parameter-scoped directories (§10).
* Producers MAY write multiple files per partition for I/O efficiency, but **MUST** preserve dataset-level sort and produce **identical bytes** regardless of file splitting.
* Readers MUST treat physical file boundaries as non-semantic (dictionary `ordering: []`).

**12.6 Streaming vs. in-memory** *(Informative)*

* A **single pass per currency** is sufficient after forming the union of countries (§6.1).
* Join of the two ingress surfaces MAY be implemented as a streamed merge on `(currency, country_iso)`; no global sort across all currencies is required by this spec.

**12.7 Large-currency stress behaviour** *(Informative)*

* For currencies with very wide support (e.g., ≳200 ISO codes), implementers SHOULD:

  * keep per-currency processing isolated (avoid cross-currency buffers),
  * ensure renormalisation (§6.6) and quantisation+tiebreak (§6.7) do not allocate super-linear intermediates,
  * surface **metrics** on renormalisation magnitude and largest-remainder placements (see §14.2).

**12.8 Retry cost & atomicity** *(Informative → Binding where referenced)*

* Retries SHOULD be scoped to the affected `parameter_hash` only.
* **Binding:** Atomic publish and write-once rules in §10.5/§10.6 apply; partial outputs MUST NOT be made visible.

**12.9 External calls & side effects** *(Binding)*

* S5 **MUST NOT** perform network calls or read any data source beyond the artefacts listed in §3 and the policy in §4; doing so would violate parameter-scope determinism.

**12.10 Throughput targets & SLO posture** *(Informative)*

* This spec does not set wall-clock SLOs; operators SHOULD size concurrency to available vCPUs (min(#currencies, vCPUs)) while respecting §12.2.
* Recommended telemetry: `currencies_processed/sec`, `rows_written/sec`, back-pressure indicators (see §14.1).

**12.11 Failure domains** *(Informative)*

* Pre-flight hard FAILs (§8.1–§8.2) short-circuit the run before any writes.
* Per-currency errors in §8.3 escalate to **run abort** (no partial publish).
* Degrades (§8.4/§8.6) are **per currency** and do not affect others, but PASS requires all invariants (§7) to hold on emitted outputs.

---

# 13. Orchestration & CLI contract **(Binding at interface; Informative for ops)**

> Goal: fix the **invocation surface** and **publish semantics** for S5 without prescribing implementation details. Paths/partitions must align with the **Dataset Dictionary** and schema authority. No DAG wiring yet (reserved for §13.4 to be added later). JSON-Schema and the dictionary remain the single authorities for shapes and locations.

## 13.1 Command interface (Binding)

**Canonical producer name (dictionary `produced_by`):** `1A.expand_currency_to_country`. 

**Invocation (normative flags — no implicit defaults for locations):**

* `--parameter-hash <HEX64>` **(required)** — selects the **parameter-scoped** partition for all S5 outputs. **Must** match the embedded `parameter_hash` written into rows. 
* `--input-root <DIR>` **(required)** — root under which **reference inputs** are resolved, e.g.
  `reference/network/settlement_shares/2024Q4/settlement_shares.parquet`,
  `reference/network/ccy_country_shares/2024Q4/ccy_country_shares.parquet`,
  `reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet`.
* `--output-root <DIR>` **(required)** — root under which S5 must publish **parameter-scoped** outputs exactly at dictionary paths, e.g.
  `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/`,
  `data/layer1/1A/merchant_currency/parameter_hash={parameter_hash}/`,
  `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/`. **Write-once.**
* `--policy-file <PATH>` **(required)** — bytes of `ccy_smoothing_params.yaml`; include in run lineage/receipt (§9). (Changing bytes **must** flip `parameter_hash` per S0 hashing rules.)
* `--dictionary <PATH>` **(required)** — dataset dictionary file (e.g., `dataset_dictionary.layer1.1A.yaml`); S5 **must** resolve IDs→paths/partitions from here and **fail** on drift. 
* `--schemas <PATH>` **(required)** — schema authority bundle (e.g., `schemas.1A.yaml`, `schemas.ingress.layer1.yaml`); used by the validator to enforce schema/constraint checks.

**Optional interface switches (Binding where stated):**

* `--emit-sparse-flag` *(MAY; default off)* — if set, produce `sparse_flag` per dictionary/schema. 
* `--validate-only` *(MAY)* — perform §9 validation and emit the S5 receipt **without** writing the weights cache; returns the same exit code semantics as a full run.
* `--fail-on-degrade` *(MAY)* — if any per-currency `degrade_mode ≠ none` (per §8.4), exit as FAIL even if §7 invariants hold (used in strict CI).

**Argument rules (Binding):**

* Locations **MUST NOT** be inferred from environment; each required path/ID must be provided explicitly as above.
* The command **MUST** reject unknown flags and missing required flags with a usage error (see §13.3).
* The producer **MUST** honour dictionary paths/partitions exactly (no ad-hoc subfolders). 

---

## 13.2 Idempotent rerun & temp-artifact policy (Binding)

* **Write-once per partition.** If `…/parameter_hash={H}/` exists for any S5 dataset, the producer **MUST** refuse to overwrite; re-runs with identical inputs/policy must be **byte-identical** (§10). 

* **Exists/resume.** If the target `…/parameter_hash={H}/` already exists:
  (i) if byte-for-byte identical, no-op and exit with PASS;
  (ii) otherwise hard FAIL `E_PARTITION_EXISTS` (do not overwrite or append).
* **Atomic publish.** Writers **MUST** stage to a temp directory under the target parent and perform a **single atomic rename**; no partial contents may become visible. This mirrors S0’s atomic bundle publish. 
* **Path↔embed equality.** After publish, embedded `parameter_hash` **MUST** equal the partition key **byte-for-byte**; any mismatch is a run-fail. 
* **No RNG paths.** S5 **MUST NOT** touch `{seed, parameter_hash, run_id}` log partitions reserved for RNG streams. 

---

## 13.3 Exit codes & emitted artefacts (Binding)

**Exit codes (minimal, unambiguous):**

* `0` — **PASS**: all checks in §9 succeed; S5 receipt present and valid for the given `parameter_hash`. (Degrades allowed; see metrics for `degrade_mode` counts.)
* `64` — **USAGE**: missing/unknown/invalid CLI flags or non-existent required paths.
* `65` — **INPUT_SCHEMA**: ingress dataset breach (schema/PK/FK/Σ) detected pre-flight. 
* `66` — **POLICY_DOMAIN**: policy file domain/feasibility error (e.g., `Σ min_share_iso>1`). 
* `67` — **OUTPUT_SCHEMA**: any S5 output fails its schema or lineage partition rules. 
* `68` — **RNG_INTERACTION**: any RNG log written/changed or trace length delta vs S4 manifest. 
* `1` — **GENERAL_FAIL**: any other invariant breach in §7/§8/§9.

**Emitted artefacts on PASS (parameter-scoped, alongside weights cache):**

* `S5_VALIDATION.json` — machine-readable validation summary (normative fields in §9.8).
* `_passed.flag` — single-line sha256 receipt over the S5 receipt files (hash excludes the flag itself), mirroring S0’s gate pattern (but **parameter-scoped**). 

**Read gate reminder:** Downstream readers (e.g., S6) **MUST** verify the S5 receipt for the **same `parameter_hash`** before reading (`no PASS → no read`). The **layer-wide** fingerprint-scoped validation bundle for egress remains unchanged and separate. 

---

## 13.4 DAG wiring — internal & S0–S4 integration

*(Binding at interfaces; Informative for scheduling)*

> This subsection fixes the **node boundaries, prerequisites, edges, and gates** for S5. It is framework-agnostic (no Airflow/Prefect specifics). Dataset IDs, schema refs, and paths come from the **Dataset Dictionary** and **Schema Authority** and remain the single sources of truth.

### 13.4.1 Run prerequisites (Binding)

**P1 — Parameter scope fixed.** A concrete **`parameter_hash`** is selected (CLI §13.1) and corresponds to the governed parameter set sealed by S0. Policy bytes **`ccy_smoothing_params.yaml`** must be part of that set; changing its bytes flips `parameter_hash`. 

**P2 — Inputs exist and are sealed.** The ingress surfaces listed in §3 are present and conform to their schema anchors:
• `settlement_shares_2024Q4` → `schemas.ingress.layer1.yaml#/settlement_shares`
• `ccy_country_shares_2024Q4` → `schemas.ingress.layer1.yaml#/ccy_country_shares`
• `iso3166_canonical_2024` (FK target)
All are registered/approved in the dictionary/registry.

**P3 — Dictionary & schema availability.** The producer has the **Dataset Dictionary** (`dataset_dictionary.layer1.1A.yaml`) and schema bundle(s) at run start; S0’s path/partition lints apply. 

**P4 — RNG stance.** No RNG streams are to be produced by S5; S5 will later verify **no change** in `rng_trace_log` totals vs the pre-run snapshot for this run context (see §11 / §9). 

> **Note.** S5 has **no hard data dependency** on S1–S4 datasets to compute weights. S3’s order authority and S4’s ZTP logs are relevant only to **downstream** readers and the **non-interaction proof**, respectively.

---

### 13.4.2 Nodes & edges (Binding at interfaces)

**N0 — Resolve policy & hash (Binding).**
Inputs: `ccy_smoothing_params.yaml` (bytes), dictionary, schemas.
Responsibilities: (a) validate policy keys/domains/overrides (§4), (b) assert inclusion into the governed parameter set for this `parameter_hash`, (c) record policy digest for the S5 receipt (§9). **Outputs:** ephemeral policy handle (in-memory), `policy_digest`. **On failure:** `E_POLICY_*` (abort). 

**N1 — Pre-flight ingress checks (Binding).**
Inputs: `settlement_shares_2024Q4`, `ccy_country_shares_2024Q4`, `iso3166_canonical_2024`.
Responsibilities: enforce §3.2–§3.4 (PK/FK, domains, **Σ=1±1e-6** per currency). **On failure:** `E_INPUT_SCHEMA`/`E_INPUT_SUM` (abort). 
**Edge:** `N0 → N1`.

**N2 — Build `ccy_country_weights_cache` (Binding).**
Inputs: N1 datasets + N0 policy.
Responsibilities: apply §6.1–§6.7 (union coverage; blend; effective mass; α smoothing; floors; renormalise; **fixed-dp + deterministic largest-remainder**; writer sort `(currency,country_iso)` ASC). **Output dataset:** `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/` with **PK `(currency,country_iso)`** and **path↔embed equality**. 
**Edge:** `N1 → N2`.

**N2b — (Optional) Build `merchant_currency` (Binding).**
Inputs: ingress surfaces + policy (if needed by your rule).
Output: `data/layer1/1A/merchant_currency/parameter_hash={parameter_hash}/` (PK `merchant_id`). May run **in parallel** with N2 once N1 passes. 

**N3 — S5 validator & receipt (Binding).**
Inputs: outputs from N2/N2b; dictionary & schemas; pre-run RNG trace snapshot.
Responsibilities (see §9): schema+PK/FK; **Σ numeric** and **decimal@dp = 1**; union coverage; **re-derivation**; **RNG non-interaction** (trace totals unchanged); write `S5_VALIDATION.json` and `_passed.flag` **under the weights cache partition** (parameter-scoped). **On failure:** abort; no publish.
**Edge:** `N2 → N3` (and `N2b → N3` if N2b executed).

**N4 — Atomic publish (Binding).**
Publish S5 datasets by **staging → single atomic rename**; ensure **write-once** for the target `parameter_hash`. **Downstream read gate:** S6 **MUST** see S5 `_passed.flag` before reading. 
**Edge:** `N3 (PASS) → N4`.

---

### 13.4.3 Wiring to S0–S4 (Binding)

* **S0 (governance & gates).** S5 inherits S0’s partition law and atomicity: parameter-scoped outputs embed the same `parameter_hash` as the path, and validation receipts use the `_passed.flag` pattern (ASCII-sorted hash over sidecar files). 

* **S1/S2 (no direct data dependency).** S5 does not read hurdle/NB artefacts. Their RNG streams and budgets remain untouched during S5. 

* **S3 (order authority stays in S3).** S5 produces **no order**; downstream states must continue to join order only from **`s3_candidate_set.candidate_rank`**. S5 outputs are designed to be **S6-ready** (restrict/renormalise within merchant’s candidate set only in S6).

* **S4 (RNG logs only; S5 non-interaction proof).** S4 appends ZTP events and updates `rng_trace_log` under `{seed,parameter_hash,run_id}`; S5 MUST NOT write to those paths and MUST prove **no change** in trace totals pre→post run.

---

### 13.4.4 Concurrency & idempotence (Binding)

* **Shard boundary:** currencies may be processed in parallel **by currency** only; merges must yield **byte-identical** results to a single-threaded run and preserve writer sort `(currency,country_iso)` ASC. 
* **Re-runs:** a completed `parameter_hash` partition is **immutable**; re-running with identical inputs/policy must be **byte-identical** or refused. 

---

### 13.4.5 Failure & abort semantics (Binding)

* On any **hard FAIL** from §8 or §9, S5 follows S0’s abort procedure: stop emitting, **delete temp dirs**, write failure sentinel(s) if any partial escaped temp, and **exit non-zero**; no `_passed.flag` means **no read** downstream. 

---

### 13.4.6 Artefact and registry alignment (Binding)

* The **artefact registry** entries for `ccy_country_weights_cache`, `merchant_currency`, and `ccy_smoothing_params` must exist and match dictionary IDs, schema refs, paths, and version semantics (`{parameter_hash}` for datasets). 

Perfect—updated. Here’s the **non-normative, human-readable** DAG section to drop in.

### 13.4.7 ASCII overview *(Informative; non-authoritative)*

> This diagram is for **reader orientation only**. It does **not** add requirements. On any discrepancy, §§6–11 and §§13.1–13.4.6 (Binding) prevail.

```
[ENTER S5]
   │
   │ Resolve parameter scope + policy bytes (N0)
   │—— fail → [STOP: E_POLICY_*]
   v
[Pre-flight ingress checks (N1)]
   │  (PK/FK, domains, Σ=1 per currency on each input surface)
   │—— fail → [STOP: E_INPUT_*]
   v
[OPTIONAL N2b: Build merchant_currency]   (may run in parallel with N2 after N1)
   │
   v
┌───────────────────────────────────────────────────────────────────────────────┐
│ For each currency κ (A→Z)                                                    │
│    │                                                                          │
│    │ Any source rows for κ?                                                   │
│    │—— no → [SKIP κ] (no outputs; no degrade)                                 │
│    v                                                                          │
│ [Union country set for κ]                                                     │
│    │                                                                          │
│    │ Only one surface present?                                                │
│    │—— yes → set degrade_mode = ccy_only | settlement_only                    │
│    v                                                                          │
│ [Blend  q = w*s_ccy + (1−w)*s_settle]                                         │
│    v                                                                          │
│ [Effective mass N_eff; α-smoothing]                                           │
│    v                                                                          │
│ [Apply floors (min_share*, incl. ISO overrides)]                              │
│    │                                                                          │
│    │ Σ min_share_iso > 1 ?                                                    │
│    │—— yes → [ABORT RUN: E_POLICY_MINSHARE_FEASIBILITY]                       │
│    v                                                                          │
│ [Renormalise p so Σ=1 (binary64)]                                             │
│    v                                                                          │
│ [Quantise to dp (half-even) + largest-remainder tie-break]                    │
│    │                                                                          │
│    │ Decimal Σ@dp == 1 ?                                                      │
│    │—— no → [ABORT RUN: E_QUANT_SUM_MISMATCH]                                 │
│    v                                                                          │
│ [Write rows for κ → ccy_country_weights_cache (sorted by currency, ISO2)]     │
└───────────────────────────────────────────────────────────────────────────────┘
   │
   v
[S5 Validator & Receipt (N3)]
   │  Re-derive; schema/PK/FK; union coverage; Σ numeric & decimal@dp;
   │  RNG non-interaction (trace totals unchanged); record overrides/degrades
   │—— fail → [ABORT RUN: no publish]
   v
[Atomic publish (N4)]
   │  Stage → single rename; write-once; emit S5_VALIDATION.json + _passed.flag
   v
[STOP: S5 PASS — downstream MAY read (parameter scope)]
```

---

# 14. Observability & metrics **(Binding for metric names/semantics; Informative where marked)**

> Purpose: make S5’s correctness and policy effects **visible and auditable** without prescribing implementation code. Metrics are **parameter-scoped** and live with the S5 receipt (see §9). JSON-Schema and the Dataset Dictionary remain the single authorities for dataset shapes and paths; S5 does **not** introduce a new dataset for metrics.

## 14.1 Surfaces (where metrics appear)

* **S5 receipt (Binding):** `S5_VALIDATION.json` adjacent to `ccy_country_weights_cache/parameter_hash={parameter_hash}/` (same partition), plus `_passed.flag`. This file **MUST** contain the run-level summary (§14.3) and per-currency records (§14.4). No separate metrics dataset is created. 
* **Structured logs (Binding for fields, Informative for transport):** JSON-lines emitted during N0–N4 (see §13.4) with the required fields in §14.5. Transport/backends are out of scope.
* **Layer-wide bundle (Informative):** fingerprint-scoped validation bundle remains unchanged and separate; it is not a sink for S5 parameter-scoped metrics. 

## 14.2 Dimensions & identity (Binding)

Every record in `S5_VALIDATION.json` **MUST** carry:

* `parameter_hash : hex64` — the partition key for S5 outputs. 
* `policy_digest : hex64` — SHA-256 of the **bytes** of `ccy_smoothing_params.yaml` consumed by the run. 
* `producer : "1A.expand_currency_to_country"` — matches dictionary `produced_by`. 
* `schema_refs : object` — anchors used to validate inputs/outputs (must include `schemas.ingress.layer1.yaml#/settlement_shares`, `#/ccy_country_shares`, and `schemas.1A.yaml#/prep/ccy_country_weights_cache`).

## 14.3 Run-level metrics (Binding)

Top-level object **MUST** include these keys (types/semantics fixed):

* **Cardinality & output:**

  * `currencies_total : int` — distinct currencies seen in inputs (union). 
  * `currencies_processed : int` — currencies for which rows were written (may be `< currencies_total` if some had no source rows).
  * `rows_written : int` — total rows in `ccy_country_weights_cache` for this `parameter_hash`. 

* **Σ & quantisation discipline:**

  * `sum_numeric_pass : int` — count of currencies where **numeric** Σ(weight)=1.0±1e-6 (schema group constraint). 
  * `sum_decimal_dp_pass : int` — count of currencies where the **decimal** sum at `dp` equals exactly `"1"` after tie-break. (Target: equals `currencies_processed`.)

* **Rounding/tie-break effort:**

  * `largest_remainder_total_ulps : int` — total absolute ULP adjustments applied across all currencies in §6.7 (0 means half-even already hit exact decimal Σ).
  * `largest_remainder_ulps_quantiles : {p50:int,p95:int,p99:int}` — distribution over per-currency ULP adjustments.

* **Policy application:**

  * `overrides_applied_count : int` — total ISO- or currency-level overrides used (from §4).
  * `floors_triggered_count : int` — total `(currency, ISO)` pairs where the **floor** was binding (`posterior < min_share*`).
  * `degrade_mode_counts : {none:int, settlement_only:int, ccy_only:int}` — per-currency degrade tallies (no `abort` here; aborts are run-fail per §8).

* **Coverage:**

  * `coverage_union_pass : int` — count of currencies where output ISO set equals the **union** of input ISOs.
  * `coverage_policy_narrowed : int` — count of currencies narrowed by policy (must also be listed in `policy_narrowed_currencies[]`). 

* **RNG non-interaction:**

  * `rng_trace_delta_events : int` — sum of deltas in `rng_trace_log.events_total` across all (module,substream) keys (MUST be 0).
  * `rng_trace_delta_draws : int` — sum of deltas in `draws_total` (MUST be 0). 

* **Lists (for operator visibility):**

  * `policy_narrowed_currencies : [ISO4217]` — currencies explicitly narrowed by policy (§8.6).
  * `degraded_currencies : [{currency, mode, reason_code}]` — per-currency degrade summary (§8.4/§8.7).

## 14.4 Per-currency records (Binding)

`S5_VALIDATION.json` **MUST** contain a collection `by_currency : [ … ]` with one object per processed currency, each with:

* **Identity:** `currency`, `parameter_hash`, `policy_digest`.
* **Coverage:** `countries_union_count : int`; `countries_output_count : int`; `policy_narrowed : bool`. (If `true`, include `narrowed_isos : [ISO2]`.) 
* **Σ checks:**

  * `sum_numeric_ok : bool` (schema group check). 
  * `sum_decimal_dp_ok : bool` (exact decimal Σ at `dp`).
* **Rounding effort:** `largest_remainder_ulps : int`.
* **Policy effects:** `overrides_applied : {alpha_iso:int, min_share_iso:int, per_currency:int}`; `floors_triggered : int`.
* **Degrade:** `degrade_mode : "none"|"settlement_only"|"ccy_only"`; `degrade_reason_code : enum` (see §8.7).
* **Evidence (Informative):** `N0 : number`, `N_eff : number`, and `dp : int` used.

## 14.5 Structured logs (Binding for fields; Informative taxonomy)

Each log line **MUST** be a single JSON object with at least:

* `ts : string(ISO8601)`; `level : "INFO"|"WARN"|"ERROR"`;
* `component : "1A.expand_currency_to_country"`;
* `stage : "N0"|"N1"|"N2"|"N2b"|"N3"|"N4"` (see §13.4);
* `parameter_hash : hex64`; `currency? : ISO4217`;
* `event : string` (stable programmatic name, e.g., `"POLICY_OVERRIDES_APPLIED"`, `"QUANT_TIE_BREAK"`, `"DEGRADE_USED"`);
* `reason_code? : string` (closed vocab from §8); `details? : object` (small, structured).

**Error taxonomy (Binding):** usage → `USAGE`; input schema/sum → `E_INPUT_*`; policy domain/feasibility → `E_POLICY_*`; output schema/lineage → `E_OUTPUT_SCHEMA`/`E_LINEAGE_PATH_MISMATCH`; RNG breach → `E_RNG_INTERACTION`; quantisation sum mismatch → `E_QUANT_SUM_MISMATCH`. (Names align with §8 and §13.3.) 

## 14.6 Metric naming & units (Binding)

* Counts are **integers**; ULP totals are **integers**; quantiles report integers; `N0`/`N_eff` are **binary64 numbers**.
* Code/enum fields use **uppercase ISO domains** pinned by ingress/schema authority (ISO2/ISO-4217).
* All metrics are **parameter-scoped**; do **not** partition or key them by `{seed, run_id}` (RNG/log partitions remain reserved for RNG systems). 

## 14.7 Golden fixtures & audit snapshots *(Informative)*

Operators SHOULD maintain one tiny, public-derivable fixture (≤ 3 currencies, ≤ 6 ISO codes) with a frozen `ccy_smoothing_params.yaml` to sanity-check: (a) union coverage, (b) floors/overrides application, (c) largest-remainder behavior, and (d) exact decimal Σ at `dp`. The fixture’s outputs and `S5_VALIDATION.json` live in the same parameter-scoped partition as the weights cache and are versioned by `parameter_hash`. 

---

**Notes.**
– Nothing in §14 alters dataset contracts; the **weights cache** remains the only persisted authority for currency→country weights, and **order** continues to be owned by S3’s candidate set (not by S5 metrics).
– RNG logs (audit/trace/event) are **unchanged**; S5 merely proves non-interaction via zero deltas.

---

# 15. Security, licensing & compliance

> Purpose: ensure S5’s inputs/outputs obey the platform’s **closed-world, contract-governed** posture; keep artefacts licenced, non-PII, immutable by key, and auditable. JSON-Schema and the Dataset Dictionary remain the single authorities for shapes, paths, owners, **retention**, and **licence** fields. 

## 15.1 Data provenance & closed-world stance

* S5 operates **only** on the sealed, version-pinned artefacts enumerated in §3 and the S5 policy in §4; **no external enrichment or network reads** are permitted. This follows the enterprise “sealed universe” control-plane rules (no PASS → no read; JSON-Schema authority; lineage anchors). 
* Provenance for each input/output is already declared in the **Dataset Dictionary** (owner, retention, licence, schema_ref). S5 MUST NOT deviate. 

## 15.2 Licensing (inputs, outputs, and registry alignment)

* **Ingress licences (examples relevant to S5):**
  – `iso3166_canonical_2024` → **CC-BY-4.0** (external reference). 
  – `settlement_shares_2024Q4` → **Proprietary-Internal**. 
  – `ccy_country_shares_2024Q4` → **Proprietary-Internal**. 
* **S5 outputs’ licence class:** `ccy_country_weights_cache`, `merchant_currency`, and `sparse_flag` are **Proprietary-Internal**, retained 365 days; S5 MUST publish under those exact classes and retention windows declared in the dictionary. 
* **Licence mapping artefact:** the registry exposes `licenses/license_map.yaml` for tracing artefact→licence during validation/release. S5 MUST confirm the **presence** of a licence entry for every input it consumes; absence is a **run-fail**. (No need to interpret legal text—presence + ID match is required.) 

## 15.3 Privacy & PII posture

* All S5 inputs and outputs in scope are declared **`pii: false`** in the dictionary; S5 MUST NOT introduce PII or fields enabling re-identification.
* Structured logs and the S5 receipt MUST avoid row-level payloads; they MAY include **codes and counts only** (currency, ISO, integer counters). See §14 for allowed fields. 

## 15.4 Access control, encryption, and secrets

* S5 inherits platform security rails: **least-privilege IAM**, **KMS-backed encryption** at rest/in transit, and **audited access** to governance artefacts. S5 MUST NOT embed secrets in datasets/logs and MUST rely on the platform’s secret store when credentials are needed (none are required by S5).

## 15.5 Retention & immutability

* Retention periods are governed by the dictionary (e.g., **365 days** for S5 outputs; **1095 days** for most ingress references). S5 MUST NOT override retention.
* Datasets are **content-addressed by `parameter_hash`** at write time and are **write-once** per partition (immutability); atomic publish rules in §10 apply. 

## 15.6 Licence & compliance checks (validator duties)

The S5 validator (§9) MUST additionally assert:

* **Dictionary/licence presence:** for each input dataset ID consumed, there exists a dictionary entry with **non-empty `licence`** and `retention_days`. Missing ⇒ **FAIL**. 
* **Licence-map coverage:** an entry exists in `license_map` for each input ID (compare IDs, not legal text). Missing ⇒ **FAIL**. 
* **Receipt fields:** `S5_VALIDATION.json` MUST include `licence_summary` listing `{dataset_id, licence, retention_days}` for all inputs and the output family, plus `policy_digest` and `parameter_hash` (see §14.2). 

## 15.7 Redistribution & downstream use

* S5 outputs are **internal authorities** (Proprietary-Internal). Downstream systems MUST NOT republish them externally or change licence class without governance approval. The **order authority** remains S3; S5 weights MAY be used downstream only under the **no re-derive** rules in §2 and after S5 PASS. 

## 15.8 Geospatial & other external datasets (for completeness)

* Spatial datasets pinned in Layer-1 (e.g., `world_countries`, `tz_world`, `population_raster`) carry **ODbL-1.0** or similar licences in the dictionary; although S5 does not read them, their licence posture is part of the environment and MUST NOT be altered by S5. 

---

**Compliance note.** These clauses do not expand legal obligations; they operationalise what is already declared in the **Dataset Dictionary** and **Artefact Registry** so that S5 remains sealed, non-PII, licenced, and auditable.

---

# 16. Change management, compatibility & rollback

> Purpose: define how S5 evolves without breaking consumers, how deprecations are handled, and how to roll back safely. Dataset IDs, paths, partitions, owners, retention and schema refs remain governed by the **Dataset Dictionary** and **Artefact Registry**.

## 16.1 Semver triggers (what forces MAJOR/MINOR/PATCH)

**MAJOR** (breaking for consumers; requires re-ratification and dictionary/registry updates):

* Change to **dataset IDs, paths, or partition keys** for any S5 output (e.g., anything other than `parameter_hash`), or change to **PKs**/join keys. 
* Change to **schema fields or types** for `ccy_country_weights_cache`/`merchant_currency`/`sparse_flag` (rename, removal, type change; group-sum tolerance). 
* Change to **quantisation/tie-break rule** (§6.7) or default **`dp`**; change to the **Σ rule** beyond `1e-6`. (Alters persisted values.)
* Change to **PASS gate semantics** or receipt location/naming (e.g., rename `_passed.flag` or move receipt). 
* Removal of an output currently marked **approved** in the dictionary. 

**MINOR** (backward compatible):

* Add **optional** columns with default `null`/non-required semantics to S5 outputs or to the S5 receipt. 
* Add new **metrics**/fields in `S5_VALIDATION.json` (§14).
* Add an **optional** output dataset such as diagnostics (kept parameter-scoped, with its own schema_ref and dictionary entry).

**PATCH**:

* Clarifications, doc fixes, stronger wording that does **not** change dataset shapes, values, gates, or paths.

**Policy file (`ccy_smoothing_params.yaml`)**: bump **MAJOR** if keys/semantics change (e.g., add new mandatory key or change domain of an existing key); **MINOR** to add optional keys; **PATCH** for comments/description only. The policy artefact carries semver in the registry and contributes to `parameter_hash`. 

## 16.2 Compatibility window & cross-state contracts

* S5 remains bound to the **v1.* lines** of the schema bundles and dictionary cited in §0/§5. A MAJOR bump in those upstream authorities requires S5 re-ratification.
* **Order authority** remains in S3; S5 must not encode order. This separation is stable across versions. 
* Ingress schemas may provide **compatibility aliases** (e.g., `settlement_shares` → `settlement_shares_2024Q4`); S5 may rely on those aliases without change to its own IDs. 

## 16.3 Deprecation & migration (how we retire things)

* Use the dictionary’s `status: deprecated` to retire legacy datasets (kept read-only for a deprecation window); do not delete without a migration note. Examples exist for **`country_set`** and **`ranking_residual_cache_1A`**.
* Deprecations MUST include: dataset ID, replacement surface, last supported semver, and an **end-of-life** date in release notes (outside this spec).
* During the window, S5/S6 MUST continue producing/consuming the **authoritative** surfaces (e.g., `ccy_country_weights_cache`), and MUST NOT re-elevate deprecated ones to authority. 

## 16.4 Rollback strategy (parameter-scoped; no mutation)

* **What to roll back:** select the **last-good `parameter_hash`** whose S5 receipt exists and `_passed.flag` is valid under the weights cache partition. No data mutation is required.
* **How:** point downstream (e.g., S6) to that `parameter_hash` (or re-run S5 using the prior policy bytes to reproduce the same `parameter_hash`). **Atomic publish** guarantees no partials are visible. 
* **Registry alignment:** the Artefact Registry tracks `{semver, version='{parameter_hash}', digest}` for S5 datasets and the policy, enabling operators to reference an exact previous version.

## 16.5 Forward/Backward compatibility guidance

* **Minor upgrades** MUST keep dataset IDs, paths, partitions, PKs and schema types stable so that older readers continue to function. 
* If adding optional columns/metrics, mark them **nullable** and avoid changing PKs or constraints. 
* **Breaking changes** MUST provide a migration note and a grace period where both old and new forms co-exist (old marked **deprecated**) before removal. 

## 16.6 Release & ratification hooks

* Any MAJOR change in §16.1 requires: (a) Schema updates; (b) Dictionary entries updated (`schema_ref`, `path`, `version`); (c) Registry entries updated (`semver`, `digest`, `manifest_key`); (d) S0 CI re-sealing so the new bytes appear in the **manifest**.
* Publish notes MUST list the affected dataset IDs and policy semver, and state whether downstream (S6) requires action. (S6 continues to read by `parameter_hash`; no action if shapes unchanged.)

## 16.7 Breaking-change checklist (Binding)

Before merging a change that would bump **MAJOR**, ensure all are true:

1. Schema diffs applied to `schemas.1A.yaml` and validated; dictionary entries updated to match.
2. Artefact Registry rows updated (`semver`, `version`, `digest`, `manifest_key`). 
3. S0 sealing passes with a new **`manifest_fingerprint`** and the validation bundle `_passed.flag` is correct.
4. Deprecation window and migration notes published where applicable (dictionary `status`/notes for legacy items). 

---

# 17. Acceptance checklist

> Use this as the go/no-go gate for promoting S5 outputs. Each item is **required** unless marked optional. Cross-references point to the normative clauses that define the rule.

## 17.1 Build-time (before first run)

* [ ] **Parameter scope fixed** and communicated (`parameter_hash` chosen for this run). (§0.6, §10.1–§10.3)
* [ ] **Policy file present** at `ccy_smoothing_params.yaml`; has `semver`, `version`, `dp`; passes key/domain rules and feasibility (**Σ min_share_iso ≤ 1**); all codes upper-case and valid. (§4.2–§4.6)
* [ ] **Dictionary + schema bundles** available and readable; S5 will treat **JSON-Schema as the only authority**. (§0.3, §5, §13.1)
* [ ] **Artefact registry** entries exist for: `ccy_country_weights_cache`, `merchant_currency` (if used), `sparse_flag` (if used), and `ccy_smoothing_params`. (§10.8)
* [ ] **CLI wiring**: required flags supplied (`--parameter-hash`, `--input-root`, `--output-root`, `--policy-file`, `--dictionary`, `--schemas`). No implicit defaults. (§13.1)
* [ ] **No external reads** beyond §3 inputs and §4 policy; network access not required/used. (§12.9, §15.1)

## 17.2 Run-time (execution checks)

* [ ] **Ingress pre-flight passes** for both share surfaces: PK/FK, domains, **Σ share = 1 ± 1e-6** per currency; schema-exact columns. (§3.2–§3.4, §8.1)
* [ ] **Union coverage formed** per currency (countries = union of both surfaces; missing treated as 0). (§6.1)
* [ ] **Degrade rules respected** when one surface is missing: `degrade_mode ∈ {ccy_only, settlement_only}` with reason code; otherwise no degrade. (§8.4, §8.7)
* [ ] **Numeric discipline**: all math in **binary64** through blend → effective mass → α-smoothing → floors → renormalise. (§6.2–§6.6)
* [ ] **Feasibility guard** enforced for floors (Σ min_share_iso ≤ 1). (§6.5, §8.2)
* [ ] **Quantisation** uses fixed-dp **round-half-even** then deterministic **largest-remainder** tie-break; per-currency **decimal Σ@dp = 1**. (§6.7)
* [ ] **Determinism**: no RNG usage; stable order within currency (ISO A→Z); parallelism only **by currency**; writer sort `(currency ASC, country_iso ASC)`. (§6.8, §12.2, §11)
* [ ] **Outputs conform** to schemas and dictionary: IDs, paths, PKs, partitioning (parameter-scoped only). (§5, §10.1, §7.2–§7.5)
* [ ] **Path↔embed equality** for `parameter_hash` holds byte-for-byte. (§7.8, §10.2)
* [ ] **RNG non-interaction**: S5 writes **no** `rng_*`; `rng_trace_log` totals unchanged vs pre-run snapshot. (§11.1–§11.4)
* [ ] *(Optional if enabled)* `merchant_currency` and/or `sparse_flag` built and schema-valid. (§5.2–§5.3)

## 17.3 Validator & PASS artefacts (publish gate)

* [ ] **Re-derivation succeeds**: validator recomputes weights from inputs+policy per §6 and matches **byte-for-byte** at `dp`. (§9.4)
* [ ] **Structural/content checks pass**: schema, PK/FK, domain, **numeric Σ**, **decimal Σ@dp**, coverage parity (or recorded policy-narrowing). (§9.1–§9.3)
* [ ] **Degrade/override attestations** present for every affected currency. (§9.5)
* [ ] **S5 receipt written** under the weights cache partition: `S5_VALIDATION.json` (required fields present) and `_passed.flag` with a valid hash computed as specified. (§9.6, §9.8)
* [ ] **Write-once + atomic publish** observed; no partial visibility; retry semantics respected. (§10.5–§10.6)
* [ ] **Downstream gate armed**: policy that **no PASS → no read** is enforced for S6 by contract. (§9.7)

## 17.4 Operability & compliance (post-run sign-off)

* [ ] **Metrics sanity**: totals in `S5_VALIDATION.json` (currencies_processed, rows_written, Σ checks, ULP adjustments) look plausible; RNG deltas are zero. (§14.3)
* [ ] **Per-currency records present** with coverage, Σ flags, ULP counts, overrides/floors, degrade mode. (§14.4)
* [ ] **Licence summary present** in the receipt; dictionary shows licences and retention for all inputs/outputs. (§15.2, §15.6)
* [ ] **Rollback pointer** noted (current `parameter_hash`) and last-good `parameter_hash` recorded for operators. (§16.4)

**Acceptance outcome:**

* **PASS:** All boxes checked above → S5 is **green** for this `parameter_hash`; S6 may read.
* **FAIL:** Any unchecked mandatory item → remediate and re-run; **downstream reads remain blocked** until §9 PASS is present for the same `parameter_hash`.

---

# Appendix A. Glossary & symbols **(Normative)**

> Terms below are binding for S5. Where a definition references an artefact, the **Dataset Dictionary** and **JSON-Schema** anchors are the single authorities for IDs, paths, types, and partitions.

## A.1 Identifiers & partitions

* **`parameter_hash` (Hex64)** — The sole **parameter-scoped** partition key for S5 outputs and related caches. It is embedded (where the schema includes it) and must equal the path key byte-for-byte. Changing governed policy bytes flips this value. Paths using `parameter_hash` are pinned in the dictionary (e.g., S3 deterministic surfaces). 
* **`manifest_fingerprint` (Hex64)** — Layer-wide run fingerprint used for **egress** gating (e.g., `outlet_catalogue`). Not a partition for S5 outputs.
* **`run_id`** — Per-run identifier **only** for RNG log partitions `{seed, parameter_hash, run_id}`; S5 does not read/write these. 

## A.2 Schema, dictionary & domains

* **JSON-Schema authority** — For 1A, **JSON-Schema is the only schema authority**; Avro (if present) is non-authoritative. Every dataset/stream must reference its `$ref` into `schemas.*.yaml`.
* **Dataset Dictionary** — Registry of dataset **IDs, paths, partitions, ordering, schema_ref, retention, licence** (e.g., `s3_candidate_set`, `outlet_catalogue`). Consumers must honour dictionary paths and gates. 
* **ISO2 / ISO-4217** — Uppercase ISO-3166-1 alpha-2 country codes and uppercase currency codes as constrained by ingress/schema. FK to canonical ISO is enforced where declared. 

## A.3 Order authorities & hand-offs

* **`candidate_rank`** — The **sole authority** for **inter-country order** (S3). It is total, contiguous, and has `candidate_rank(home)=0`. S5 must not encode or imply country order.
* **`outlet_catalogue`** — Immutable egress of site stubs; **does not encode cross-country order**. Consumers must join S3’s `candidate_rank` when order is needed.

## A.4 RNG infrastructure (referential; S5 is RNG-free)

* **RNG logs** — Families under `schemas.layer1.yaml#/rng/*` (events/audit/trace), partitioned by `{seed, parameter_hash, run_id}`. **RNG trace** totals are cumulative per `(module, substream_label)`; S4 appends exactly one trace row per event. S5 must not change any RNG totals. 

## A.5 Policy & smoothing terms (S5)

* **`ccy_smoothing_params.yaml`** — Governed S5 policy artefact contributing to `parameter_hash`; contains keys below (domains in §4).
* **`dp`** — Fixed decimal places used for **output quantisation** of weights (0…18).
* **`blend_weight (w)`** — Convex weight in [0,1] used to blend two share surfaces.
* **`alpha, alpha_iso`** — Non-negative Dirichlet-style prior(s) (per currency; optional per-ISO overrides).
* **`min_share, min_share_iso`** — Lower bounds on per-ISO weights (feasible only if Σ floors ≤ 1).
* **`obs_floor`** — Minimum effective mass for smoothing; integer ≥ 0.
* **`shrink_exponent`** — Exponent ≥ 0 used to shrink large masses when computing effective evidence. *(All policy fields are normative; see §4 for domains/precedence.)*

## A.6 Probability surfaces & working symbols

* **`s_settle[c]`, `s_ccy[c]`** — Input share for country `c` from the settlement and currency-country surfaces, respectively; each surface individually satisfies Σ=1 per currency by ingress contract. 
* **`q[c]`** — Blended share: `q[c] = w·s_ccy[c] + (1−w)·s_settle[c]`.
* **`N0`** — Evidence mass from counts: `N0 = w·Σ n_ccy + (1−w)·Σ n_settle`.
* **`N_eff`** — Effective mass: `max(obs_floor, N0^(1/shrink_exponent))`.
* **`posterior[c]`** — Smoothed value: `(q[c]·N_eff + α[c]) / (N_eff + Σ α)`.
* **`p′[c]`** — Post-floor value: `max(posterior[c], min_share_for_c)`.
* **`p[c]`** — Renormalised value: `p′[c] / Σ p′`.
* **`Z`** — Renormaliser `Σ p′`.
  *(All arithmetic is IEEE-754 binary64 until quantisation.)*

## A.7 Quantisation & exact-sum discipline

* **Round-half-even (banker’s rounding)** — Required rounding mode when converting `p[c]` to fixed-dp decimals.
* **Largest-remainder tie-break** — Deterministic placement of ±1 ULP adjustments **within a currency** when the fixed-dp decimal sum deviates from exactly `1.00…0` at `dp`. Sort by **descending** fractional remainder (pre-round), then by `country_iso` A→Z. Output must become **byte-identical** across shard counts after applying this rule.
* **ULP** — One **unit in the last place** of the fixed-dp decimal representation used for the Σ=1 exactness step.
* **Σ (sum) tolerance** — Schema-level numeric group constraint of `1.0 ± 1e-6`; S5 additionally requires **decimal** Σ at `dp` to equal **exactly** `"1"` after tie-break. 

## A.8 Coverage, joins & scope

* **Union coverage** — For each currency, S5 outputs rows for the **union** of ISO codes appearing in either input surface, unless narrowed by policy (recorded via lineage/metrics).
* **Join keys** — Weights join on `(currency, country_iso)`; S3 order joins on `(merchant_id, country_iso)` with `candidate_rank` as the order key. 
* **Parameter scope vs egress scope** — S5 outputs are **parameter-scoped** (`parameter_hash=…`); egress (e.g., `outlet_catalogue`) is **fingerprint-scoped** (`fingerprint=…`). 

## A.9 Degrade modes & attestations (per currency)

* **`degrade_mode`** — `{none, settlement_only, ccy_only}` indicating a single-surface fallback was used.
* **`degrade_reason_code`** — Closed set including `{SRC_MISSING_SETTLEMENT, SRC_MISSING_CCY, POLICY_NARROWING}` (and `OTHER` as last resort).
* **S5 receipt** — `S5_VALIDATION.json` + `_passed.flag` written under the weights partition as the **parameter-scoped** PASS artefact; required for downstream reads. *(Names and placement are normative in §9.)*

## A.10 Notation & abbreviations

* **A→Z / ASC** — Lexicographic ascending order.
* **PK / FK** — Primary key / Foreign key as declared in JSON-Schema and the dictionary. 
* **`home`** — The merchant’s home (registration) country; appears in S3 candidate set at `candidate_rank=0`. 
* **`A`** — Admissible foreign universe size `|C\{home}|` from S3; used downstream (e.g., S4’s `A=0` short-circuit). 

---

**Cross-reference note.** For the authoritative order surface and its guarantees, see **S3** (`s3_candidate_set`). For RNG trace/partition rules see **S4**. For egress order absence and with-in-country sequencing, see **`outlet_catalogue`** schema/dictionary entries.

---

# Appendix B. Enumerations & reference tables **(Normative)**

> These closed vocabularies and anchors are **binding** for S5. Where a table cites an ID/`$ref`, the **Dataset Dictionary** and **JSON-Schema** are the single authorities. Consumers MUST NOT assume anything outside these sets.

## B.1 Read/write dataset anchors (IDs, `$ref`, PKs, partitions)

| Role                   | Dataset ID                  | `$ref` (schema anchor)                                | PK (per partition)       | Partition keys     | Dictionary path (prefix)                                                      |
| ---------------------- | --------------------------- | ----------------------------------------------------- | ------------------------ | ------------------ | ----------------------------------------------------------------------------- |
| **Input**              | `settlement_shares_2024Q4`  | `schemas.ingress.layer1.yaml#/settlement_shares`      | `(currency,country_iso)` | —                  | `reference/network/settlement_shares/2024Q4/…`                                |
| **Input**              | `ccy_country_shares_2024Q4` | `schemas.ingress.layer1.yaml#/ccy_country_shares`     | `(currency,country_iso)` | —                  | `reference/network/ccy_country_shares/2024Q4/…`                               |
| **FK target**          | `iso3166_canonical_2024`    | `schemas.ingress.layer1.yaml#/iso3166_canonical_2024` | `(country_iso)`          | —                  | `reference/iso/iso3166_canonical/2024-12-31/…`                                |
| **Output (authority)** | `ccy_country_weights_cache` | `schemas.1A.yaml#/prep/ccy_country_weights_cache`     | `(currency,country_iso)` | `[parameter_hash]` | `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/`   |
| *(Optional)*           | `merchant_currency`         | `schemas.1A.yaml#/prep/merchant_currency`             | `(merchant_id)`          | `[parameter_hash]` | `data/layer1/1A/merchant_currency/parameter_hash={parameter_hash}/`           |
| *(Optional)*           | `sparse_flag`               | `schemas.1A.yaml#/prep/sparse_flag`                   | `(currency)`             | `[parameter_hash]` | `data/layer1/1A/sparse_flag/parameter_hash={parameter_hash}/`                 |

**Notes.** JSON-Schema governs field types/domains (e.g., `currency : ISO4217`, `country_iso : ISO2`, `share∈[0,1]`, per-currency **Σ share = 1 ± 1e-6** for the two ingress surfaces).

---

## B.2 Code domains & FK constraints

| Symbol                  | Domain (closed)                                                                                | Source of truth / enforcement                                                |
| ----------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `country_iso`           | **ISO-3166-1 alpha-2**; **uppercase**; placeholder codes such as `XX/ZZ/UNK` are **forbidden** | Must FK to `iso3166_canonical_2024.country_iso`.                             |
| `currency`              | **ISO-4217**; **uppercase** 3-letter                                                           | Domain pinned by ingress schema for both share surfaces.                     |
| Inter-country **order** | **S3 `s3_candidate_set.candidate_rank` only** (home=0, contiguous)                             | Consumers MUST join order only from this surface; S5 must not encode order.  |

---

## B.3 Policy file keys (top-level & overrides)

**Artefact:** `configs/allocation/ccy_smoothing_params.yaml` (contributes to `parameter_hash`). Keys and domains are closed as below. 

| Key                                    | Type / Domain              | Scope    | Precedence                     |   |
| -------------------------------------- | -------------------------- | -------- | ------------------------------ | - |
| `semver`                               | string `MAJOR.MINOR.PATCH` | file     | —                              |   |
| `version`                              | date `YYYY-MM-DD`          | file     | —                              |   |
| `dp`                                   | int **[0,18]**             | global   | —                              |   |
| `defaults.blend_weight`                | number **[0,1]**           | currency | global→currency                |   |
| `defaults.alpha`                       | number **≥0**              | ISO      | global→currency→ISO            |   |
| `defaults.obs_floor`                   | int **≥0**                 | currency | global→currency                |   |
| `defaults.min_share`                   | number **[0,1]**           | ISO      | global→currency→ISO            |   |
| `defaults.shrink_exponent`             | number **≥0**              | currency | global→currency                |   |
| `per_currency.<CCY>.{…}`               | subset of `defaults` keys  | currency | overrides `defaults`           |   |
| `overrides.alpha_iso.<CCY>.<ISO2>`     | number **≥0**              | ISO      | top priority                   |   |
| `overrides.min_share_iso.<CCY>.<ISO2>` | number **[0,1]**           | ISO      | top priority; **Σ floors ≤ 1** |   |

---

## B.4 Degrade & reason vocabularies (per-currency)

| Field                 | Allowed values (closed)                                              | Semantics                                                        |
| --------------------- | -------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `degrade_mode`        | `{none, settlement_only, ccy_only}`                                  | Used when only one ingress surface exists for a currency (§8.4). |
| `degrade_reason_code` | `{SRC_MISSING_SETTLEMENT, SRC_MISSING_CCY, POLICY_NARROWING, OTHER}` | Machine-readable reason recorded in S5 metrics.                  |

*(Both fields are required in the S5 metrics/receipt when applicable.)*

---

## B.5 Error code taxonomy (S5 producer & validator)

| Code                                      | Raised when                                                                          |
| ----------------------------------------- | ------------------------------------------------------------------------------------ |
| `USAGE`                                   | CLI contract violation (missing/unknown flags, missing paths).                       |
| `E_INPUT_SCHEMA` / `E_INPUT_SUM`          | Ingress schema/PK/FK breach or **Σ share** constraint violated on an input surface.  |
| `E_POLICY_DOMAIN`                         | Policy key/domain invalid (incl. unknown currency/ISO in overrides).                 |
| `E_POLICY_MINSHARE_FEASIBILITY`           | For a currency, **Σ min_share_iso > 1.0**.                                           |
| `E_ZERO_MASS`                             | Post-floor mass sums to 0 before renormalisation.                                    |
| `E_QUANT_SUM_MISMATCH`                    | After quantisation + tie-break, decimal Σ at `dp` ≠ `1`.                             |
| `E_OUTPUT_SCHEMA`                         | Any S5 output breaches its schema/PK/FK.                                             |
| `E_RNG_INTERACTION`                       | RNG logs changed or new RNG streams appeared during S5.                              |
| `E_LINEAGE_PATH_MISMATCH` / `E_ATOMICITY` | Path↔embed inequality or non-atomic publish.                                         |
| `E_MCURR_CARDINALITY`                     | Missing or duplicate `merchant_id` rows in `merchant_currency`; partial table forbidden. |
| `E_MCURR_RESOLUTION`                      | Merchant currency κₘ missing/invalid after applying the deterministic rule.               |
| `E_PARTITION_EXISTS`                      | Target partition exists with non-identical content; overwrite/append is forbidden.        |


---

## B.6 Structured-log fields & levels

| Field            | Values / Type                                                                     |
| ---------------- | --------------------------------------------------------------------------------- |
| `level`          | `{INFO, WARN, ERROR}`                                                             |
| `component`      | `"1A.expand_currency_to_country"`                                                 |
| `stage`          | `{N0, N1, N2, N2b, N3, N4}` (see §13.4)                                           |
| `event`          | Closed names, e.g., `POLICY_OVERRIDES_APPLIED`, `DEGRADE_USED`, `QUANT_TIE_BREAK` |
| `parameter_hash` | hex64                                                                             |
| `currency?`      | ISO-4217                                                                          |

*(Records are JSON objects; additional fields allowed but MUST NOT contradict these names.)*

---

## B.7 Metric names (receipt keys)

Run-level (top object in `S5_VALIDATION.json`):

* `parameter_hash`, `policy_digest`, `producer`, `schema_refs` (object);
* `currencies_total`, `currencies_processed`, `rows_written`;
* `sum_numeric_pass`, `sum_decimal_dp_pass`;
* `largest_remainder_total_ulps`, `largest_remainder_ulps_quantiles.{p50,p95,p99}`;
* `overrides_applied_count`, `floors_triggered_count`;
* `degrade_mode_counts.{none,settlement_only,ccy_only}`;
* `coverage_union_pass`, `coverage_policy_narrowed`;
* `rng_trace_delta_events`, `rng_trace_delta_draws`;
* `policy_narrowed_currencies[]`, `degraded_currencies[]`.  

Per-currency (array `by_currency[]`):

* `currency`, `parameter_hash`, `policy_digest`;
* `countries_union_count`, `countries_output_count`, `policy_narrowed`, `narrowed_isos?`;
* `sum_numeric_ok`, `sum_decimal_dp_ok`;
* `largest_remainder_ulps`;
* `overrides_applied.{alpha_iso, min_share_iso, per_currency}`, `floors_triggered`;
* `degrade_mode`, `degrade_reason_code`;
* `N0`, `N_eff`, `dp`.  

---

## B.8 Rounding & tie-break settings (closed)

| Setting           | Allowed value                                                               |
| ----------------- | --------------------------------------------------------------------------- |
| Rounding mode     | **Round-half-even** (banker’s rounding)                                     |
| Tie-break order   | **Descending** fractional remainder (pre-round), then `country_iso` **A→Z** |
| Decimal exact-sum | **Required**: sum of fixed-dp decimals equals `1` exactly at `dp`           |

*(These are stricter than schema tolerance; they are binding for S5.)*

---

## B.9 Receipt artefacts (parameter-scoped gate)

| File                 | Placement                          | Content                                                                                        |
| -------------------- | ---------------------------------- | ---------------------------------------------------------------------------------------------- |
| `S5_VALIDATION.json` | In the weights partition directory | Run-level + per-currency metrics; schema/Σ/coverage attestations; RNG non-interaction deltas.  |
| `_passed.flag`       | Same directory                     | Single line: `sha256_hex = <hex64>` over the receipt files (excluding the flag itself).        |

---

## B.10 Cross-state authority references

| Surface             | Authority                         | Notes                                                                         |
| ------------------- | --------------------------------- | ----------------------------------------------------------------------------- |
| Inter-country order | `s3_candidate_set.candidate_rank` | Sole order source (home=0, contiguous; stable). S5 must not encode order.     |
| Egress outlet stubs | `outlet_catalogue`                | No cross-country order; readers must join S3 order; fingerprint-scoped gate.  |

---

Short answer: yes—include it. A tiny, non-normative worked example removes any ambiguity around **quantisation + tie-break**, **Σ=1 at dp**, floors, and “union” coverage. It also doubles as a golden fixture for your validator and for Codex’s unit tests.

Here’s a ready-to-drop appendix.

# Appendix C. Worked example (tiny, numeric) *(Non-normative)*

> Purpose: illustrate §6 behaviour with small numbers. This appendix does **not** add requirements; if any discrepancy appears, §§6–11 control.

## C.1 No tie-break needed (USD; dp=3)

**Inputs (per currency USD):**

| ISO2 | `s_settle` | `s_ccy` |
| ---- | ---------: | ------: |
| US   |       0.50 |    0.48 |
| DE   |       0.30 |    0.32 |
| JP   |       0.20 |    0.20 |

**Policy:** `w=0.6`, `alpha=0`, `obs_floor=0`, `shrink_exponent=1`, `min_share=0`, `dp=3`.

1. **Blend** `q = w·s_ccy + (1−w)·s_settle`
   US: `0.6·0.48 + 0.4·0.50 = 0.288 + 0.200 = 0.488`
   DE: `0.6·0.32 + 0.4·0.30 = 0.192 + 0.120 = 0.312`
   JP: `0.6·0.20 + 0.4·0.20 = 0.120 + 0.080 = 0.200`
   (Σq = 1.000)

2. **Smoothing / floors:** `alpha=0`, no floors ⇒ posterior = q; `p′ = posterior`.

3. **Renormalise:** `p = p′ / Σp′ = p′` (already 1.0).

4. **Quantise to dp=3 (half-even):**
   US 0.488 → **0.488**, DE 0.312 → **0.312**, JP 0.200 → **0.200**.
   **Decimal Σ@dp = 1.000**, **largest_remainder_ulps = 0**.

**Final row group (USD):** (US,0.488), (DE,0.312), (JP,0.200).

---

## C.2 Tie-break in action (EUR; dp=3)

Assume after §6.6 renormalisation we have:

| ISO2 | pre-quant `p[c]` |
| ---- | ---------------: |
| US   |           0.3334 |
| DE   |           0.3333 |
| JP   |           0.3333 |

**Half-even to dp=3:** all three round to **0.333** ⇒ decimal sum **0.999** (short by 1 ULP at dp=3).
**Largest-remainder placement (§6.7):** fractional remainders are 0.0004 (US), 0.0003 (DE), 0.0003 (JP). Add **+1 ULP (0.001)** to the max remainder (US):

* US → **0.334**, DE → **0.333**, JP → **0.333** ⇒ **Σ@dp = 1.000**.
* **largest_remainder_ulps = 1** for this currency; tie order would fall back to ISO A→Z only if remainders tie.

**Final row group (EUR):** (US,0.334), (DE,0.333), (JP,0.333).

---

## C.3 Infeasible floors (policy guard → FAIL)

**Policy snippet (GBP):** `min_share_iso.GBP.GB = 0.70`, `min_share_iso.GBP.US = 0.35`.
**Check:** Σ floors = **1.05 > 1.0** ⇒ **`E_POLICY_MINSHARE_FEASIBILITY`** (see §6.5/§8.2). Run must fail before producing outputs.

---

# Appendix D. Degrade decision table *(Non-normative)*

| Scenario                               | Degrade           | Reason                  | Notes                                 |
|----------------------------------------|-------------------|-------------------------|---------------------------------------|
| Only `ccy_country_shares` has currency | `ccy_only`        | `SRC_MISSING_SETTLEMENT`| Must still meet §6.6/§6.7             |
| Only `settlement_shares` has currency  | `settlement_only` | `SRC_MISSING_CCY`       | Must still meet §6.6/§6.7             |
| Neither has currency                   | —                 | —                       | Currency out of scope (no rows)       |
| Policy narrowed set                    | `none`            | `POLICY_NARROWING`      | Record via metrics; S6 ephemeral renorm |

# Appendix E. Policy audit fields *(Non-normative)*

The S5 receipt MAY include the following fields under `by_currency[]` to aid audits (names are informative—§14 lists the binding metrics):

- `effective.blend_weight`
- `effective.alpha_total`
- `floors.count`, `floors.sum`
- `overrides.alpha_iso : [ISO2]`
- `overrides.min_share_iso : [ISO2]`
