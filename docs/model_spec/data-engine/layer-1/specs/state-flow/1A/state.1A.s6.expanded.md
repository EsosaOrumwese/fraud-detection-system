# S6 SPEC — Foreign Set Selection (Layer 1 · Segment 1A)

# 0. Document metadata & status **(Binding)**

**0.1 State ID, version, semver policy, effective date**

* **State ID:** `layer1.1A.S6` (“Foreign Set Selection”).
* **Versioning:** semantic versioning **MAJOR.MINOR.PATCH**.

  * **MAJOR** bump required for: any change to read/write dataset IDs or schemas, tie-break rules, RNG event family shapes, partition law, or PASS-gate semantics.
  * **MINOR**: additive fields/metrics, optional convenience dataset enablement.
  * **PATCH**: clarifications with zero behaviour/schema impact.
* **Effective date:** set by release tag on approval.

**0.2 Normative marks & RFC 2119/8174 usage**

* **MUST/SHALL/SHOULD/MAY** are per RFC 2119/8174 and are **binding** in this spec.
* This document is **binding** unless a clause is explicitly labelled *Informative*.

**0.3 Sources of authority (precedence)**

1. **JSON-Schema** (`schemas.1A.yaml`, `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`) is the **sole** schema authority for all S6 inputs/outputs/logs. 2) **Dataset Dictionary** (`dataset_dictionary.layer1.1A.yaml`) governs dataset IDs, paths, partitions, PK/FK, retention, and ownership. 3) This S6 spec (behavioural rules) sits beneath those authorities. 

**0.4 Compatibility window (bound S0–S5; numeric environment)**

* **Numeric policy:** S6 **inherits S0.8** verbatim — IEEE-754 **binary64**, **round-to-nearest ties-to-even**, **FMA off**, **no FTZ/DAZ**, deterministic libm profile; any decision-critical math follows S0’s fixed-order and attestation rules.
* **Assumed baselines (v1.* line unless re-ratified):**

  * **Dictionary:** `dataset_dictionary.layer1.1A.yaml` v1.0.
  * **Schemas:** `schemas.ingress.layer1.yaml` v1.0; `schemas.1A.yaml` v1.0; `schemas.layer1.yaml` v1.0.
  * **Order authority:** **S3** `s3_candidate_set.candidate_rank` is **sole** inter-country order; `outlet_catalogue` carries **no** cross-country order. If any baseline bumps **MAJOR**, S6 must be re-ratified. 

**0.5 Schema anchors & dataset IDs in scope (explicit read/write set)**

* **Inputs (read):**

  * `s3_candidate_set` → `schemas.1A.yaml#/s3/candidate_set` (partition `[parameter_hash]`). **Authority for order & admissible set A.** 
  * `rng_event_ztp_final` → `schemas.layer1.yaml#/rng/events/ztp_final` (partitions `{seed, parameter_hash, run_id}`); carries `K_target`. 
  * `ccy_country_weights_cache` → `schemas.1A.yaml#/prep/ccy_country_weights_cache` (partition `[parameter_hash]`); authority for currency→country weights. 
  * *(Optional)* `merchant_currency` → `schemas.1A.yaml#/prep/merchant_currency` (partition `[parameter_hash]`). 
  * Canonical ISO FK table per dictionary (e.g., `iso3166_canonical_2024`). 
* **Outputs (write):**

  * **RNG events:** `rng_event.gumbel_key` → `schemas.layer1.yaml#/rng/events/gumbel_key` (partitions `{seed, parameter_hash, run_id}`); **logging mode:** if `log_all_candidates=true`, one per **considered** candidate; if `false`, keys only for **selected** candidates. Envelope fields (`before/after/blocks/draws`) per layer law; **trace row appended after each event**.
  * **Core RNG logs updated:** `rng_audit_log`, `rng_trace_log` per layer schemas; cumulative **trace** by `(module, substream_label)`. 
  * *(Optional)* **`s6_membership`** → `schemas.1A.yaml#/s6/membership` (PK `(merchant_id, country_iso)`, partitions `{seed, parameter_hash}`); **authority note:** must be re-derivable from RNG events; **no** inter-country order (*order remains in S3 `candidate_rank`*).

**0.6 Hashing & manifests (lineage identifiers & participation)**

* **`parameter_hash` (S0.2.2):** a hash over the governed set **𝓟**; partitions parameter-scoped datasets. S6 **adds its policy file(s)** to 𝓟; changing their bytes **MUST** flip `parameter_hash`. *(Cross-note: S0.2.2 must enumerate the S6 policy basename(s) to keep 𝓟 canonical.)* 

* **`manifest_fingerprint` (S0.2.3):** flips if **any opened artefact** (by bytes), the **code commit**, or the **parameter bundle** changes; all artefacts S6 actually opens (inputs, schemas, dictionary, numeric policy, S6 policy) **contribute** to the manifest. 

* **`run_id`:** partitions **logs** only; never affects modelling state or RNG decisions. 

* **Partition/embedding equality (layer law):** where present, embedded lineage fields `{seed, parameter_hash, run_id}` in events/logs **MUST equal** the path tokens byte-for-byte; `rng_trace_log` lineage is enforced via partition keys. 

* **Numeric environment attestation:** successful S0.8 self-tests are a **precondition**; S6 assumes the environment and math profile in effect. 

---

# 1. Intent, scope, and non-goals **(Binding)**

**1.1 Goal (what S6 does).**
For each **eligible multi-site** merchant, S6 selects a **subset of foreign ISO2 countries** of size
$$
K_{\text{realized}}=\min\big(K_{\text{target}},\,|\text{Eligible}|\big)
$$
where **$K_{\text{target}}$** comes from **S4’s `rng_event.ztp_final`** and **Eligible** is the set of S3 **foreign** candidates (home excluded) with **strictly positive** S5 weight **after** applying policy filters/caps (§4.2; Appendix A). The **selection domain** is the **intersection** of S3’s candidate set and **S5’s `ccy_country_weights_cache`** for the merchant’s settlement currency; weights are taken from S5. **S5 must have PASSed** for the same `parameter_hash` before S6 reads.

**1.2 Out of scope (what S6 will not do).**

* **No inter-country order creation or implication.** **S3 `candidate_rank`** is the **sole** authority for cross-country order; S6 produces **membership only**. Egress datasets (e.g., `outlet_catalogue`) **do not** encode cross-country order and consumers must keep joining S3 for order.
* **No allocation of outlet counts across countries (S7 job).** S6 does **not** split N; the count allocation state uses its own RNG family (e.g., `rng_event.dirichlet_gamma_vector`) and contracts.
* **No site materialisation / IDs (S8 job).** S6 emits no site stubs and does not touch egress; `outlet_catalogue` remains ordered **within-country** only.
* **No re-derivation or persistence of weights.** Any subset **renormalisation is ephemeral** (for scoring/selection only) and **must not be persisted**; the persisted authority for currency→country weights remains **S5 `ccy_country_weights_cache`**.
* **No modification of S4’s `K_target`.** S6 reads `K_target` as fixed from S4’s non-consuming final event and does not overwrite it. 

**1.3 Success criteria (how we know S6 is correct).**

* **Deterministic-under-seed:** For a fixed `{seed, parameter_hash, run_id}`, the realized foreign set equals the **top-`K_target`** countries by the S6 scoring rule over the domain (ties broken per §6), or **all `|\text{Eligible}|`** when `|\text{Eligible}| < K_target`. Inputs (`s3_candidate_set`, `rng_event.ztp_final`, `ccy_country_weights_cache`) are consumed exactly as registered in the dictionary/schemas.
* **Membership-only output:** Any optional S6 “membership” surface contains **no order** and is provably **re-derivable from S6 RNG events + S3/S5 inputs**. 
* **RNG logging completeness & isolation:** If `log_all_candidates=true`, write exactly one `rng_event.gumbel_key` **per considered candidate** (domain after policy). If `false`, write keys **only for selected candidates** and rely on §9.3 counter-replay. In both modes, only S6 families appear; envelopes/trace totals reconcile.
* **Upstream gate honored:** S6 reads S5 only after verifying the **S5 PASS** receipt for the same `parameter_hash` (**no PASS → no read**).

---

# 2. Interfaces & “no re-derive” boundaries **(Binding)**

**2.1 Upstream (must exist to run S6).**

* **S3 candidate set (authority for domain & order).** `s3_candidate_set` → `schemas.1A.yaml#/s3/candidate_set` (partitioned by `parameter_hash`). **A** is the count of **foreign** rows per merchant (home has `candidate_rank=0`). `candidate_rank` is **total & contiguous** and is the **sole** authority for inter-country order.
* **S4 target K (logs-only):** `rng_event_ztp_final` → `schemas.layer1.yaml#/rng/events/ztp_final` under `{seed,parameter_hash,run_id}`; exactly **one** per resolved merchant. S6 **MUST** read `K_target` here and **MUST NOT** infer it from any other rows.
* **S5 weights (parameter-scoped):** `ccy_country_weights_cache` → `schemas.1A.yaml#/prep/ccy_country_weights_cache` under `parameter_hash={…}`. **Read gate:** S6 **MUST** verify S5 **PASS** (presence of `S5_VALIDATION.json` + valid `_passed.flag`) for the **same `parameter_hash`** before reading (**no PASS → no read**).

**2.2 Downstream (what consumes S6 and how).**

* **S7 (allocation):** consumes **membership only** (domain = home + S6-selected foreigns). S7 **MAY** renormalise **ephemerally** within this domain to drive its own RNG (e.g., `rng_event.dirichlet_gamma_vector`) but **MUST NOT** persist new weights as S5. 
* **S8 (materialisation):** never encodes cross-country order; consumers derive order **only** from S3 `candidate_rank`. `outlet_catalogue` egress explicitly states “does NOT encode cross-country order.” 

**2.3 “No re-derive” guarantees (promises S6 makes).**

* **No order creation or implication.** S6 **MUST NOT** create, persist, or imply inter-country order; downstream must continue to use **S3 `candidate_rank`** as the only order authority. 
* **No weight replacement.** S6 **MUST NOT** alter or persist weights; any subset renormalisation used for scoring/selection is **ephemeral** and **not written**. Persisted currency→country weights remain **S5**. 
* **No reinterpretation of S4 context.** `lambda_extra`, `regime`, `attempts`, `exhausted?` in `ztp_final` are **audit** fields only; S6 **MUST NOT** use them as selection weights or gates beyond reading `K_target`. 
* **RNG isolation.** S6 **reads/writes only** its own RNG families (e.g., `rng_event.gumbel_key`) and **MUST NOT** write to any S1–S5 streams; envelopes and trace obey the layer budgeting law. 

**2.4 Forward contracts to S7 (what S6 guarantees to its consumer).**

* **Selection size:** S6 **MUST** realise
  $$
  K_{\text{realized}}=\min\!\big(K_{\text{target}},\,|\text{Eligible}|\big)
  $$
  using the S3 foreign domain and S5 weights; if `|\text{Eligible}| < K_target`, S6 selects **all `|\text{Eligible}|`** (shortfall).

* **Provenance & replay:** If `log_all_candidates=true`, write exactly **one** `rng_event.gumbel_key` per **considered** candidate; if `false`, write keys **only for selected** candidates and rely on §9.3 counter-replay. Selection is re-derivable from events + S3/S5 in both modes. (Membership, if emitted, is convenience-only and exactly re-derivable.)

---

# 3. Inputs — datasets, schemas, partitions **(Binding)**

**3.1 Required datasets (IDs, `$ref`, PK/FK; partitions).**

* **`s3_candidate_set`** → `schemas.1A.yaml#/s3/candidate_set`; **partition:** `parameter_hash={…}`; **row order (logical):** `(merchant_id, candidate_rank, country_iso)`; **authority:** `candidate_rank` is **total & contiguous** per merchant with **home=0**.
* **`rng_event_ztp_final`** (S4) → `schemas.layer1.yaml#/rng/events/ztp_final`; **partition:** `{seed, parameter_hash, run_id}`; **one** acceptance record per resolved merchant; consumed by **S6**. 
* **`ccy_country_weights_cache`** (S5) → `schemas.1A.yaml#/prep/ccy_country_weights_cache`; **partition:** `parameter_hash={…}`; **PK:** `(currency, country_iso)`; downstream **must** verify **S5 PASS** for same `parameter_hash` (**no PASS → no read**).
* *(Optional)* **`merchant_currency`** → `schemas.1A.yaml#/prep/merchant_currency`; **partition:** `parameter_hash={…}`; **PK:** `(merchant_id)`; precedence & domains pinned in S5.
* **Canonical ISO registry** (FK target), e.g. **`iso3166_canonical_2024`** → `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`. 
* **RNG core logs** (read-only by validator): `rng_audit_log`, `rng_trace_log` → `schemas.layer1.yaml#/rng/core/*`; **partition:** `{seed, parameter_hash, run_id}`. 

**3.2 Domains, types, nullability (per schema anchors).**

* **S3 candidate set:** `merchant_id:u64`, `country_iso: ISO-3166-1 (A–Z)`, `candidate_rank:u32 (total, contiguous)`, `is_home:bool`; embedded `parameter_hash` **must equal** path key. 
* **S4 ztp_final:** event schema under layer catalog; partitions `{seed, parameter_hash, run_id}`; **exactly one** final per resolved merchant.
* **S5 weights cache:** `currency: ISO-4217 (A–Z)`, `country_iso: ISO2 (A–Z, FK→ISO)`, `weight∈[0,1]`, optional `obs_count≥0`; **Σ weight = 1 ± 1e-6** per currency; embedded `parameter_hash` equals path key. 
* **merchant_currency (if produced):** `merchant_id:id64`, `kappa: ISO-4217`, `source enum`, `tie_break_used:bool`; **1 row per merchant** in S0 universe. 

**3.3 Pre-flight checks (run MUST abort on failure).**
Per `{seed, parameter_hash[, run_id]}`:
a) **Presence & schema pass** for **all** inputs above; **path↔embed equality** holds (where embedded).
b) **S3**: for each merchant, `candidate_rank` is present, **home=0**, contiguous, no dups; compute **A = #foreign candidates**. 
c) **S0 eligibility (explicit)**: `crossborder_eligibility_flags.is_eligible == true` for the merchant under the same `parameter_hash`; otherwise **do not run S6** (`E_UPSTREAM_GATE`). 
d) **S4**: exactly **one** `ztp_final` for each merchant that is multi+eligible (per S1/S0 gating upstream). 
e) **S5**: weights cache exists for the **same `parameter_hash`** and **S5 PASS receipt** is present and valid under that partition (`S5_VALIDATION.json` + `_passed.flag`); otherwise **no read**. 
f) **Domains/FK**: ISO codes uppercase and FK-valid to `iso3166_canonical_2024`; currencies uppercase ISO-4217.

**3.4 Hard rejections (fail-closed).**

* **`E_UPSTREAM_GATE`** — missing required dataset/partition; S5 PASS receipt absent/invalid; S3 candidate set missing or malformed (non-contiguous ranks, no home).
* **`E_LINEAGE_PATH_MISMATCH`** — any embedded lineage field not byte-equal to its partition token. 
* **`E_DOMAIN_FK`** — unknown or non-uppercase ISO/ISO-4217 codes; FK violation to canonical ISO. 
* **`E_S5_CONTENT`** — `ccy_country_weights_cache` group-sum/ bounds/coverage breach (Σ≠1±1e-6, weight out of [0,1], or union-coverage violated). 

**Partition law (summary, binding).**

* **Parameter-scoped tables** (S3, S5, optional membership): `…/parameter_hash={parameter_hash}/` and embed the **same** `parameter_hash`.
* **RNG logs/layer1/1A/events** (S4/S6 and core logs): `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`.

---

# 4. Configuration & policy **(Binding)**

**4.1 Policy file(s), `$ref`, version pinning**

* **Basenames & location.** One or more S6 policy files (the “S6 policy set”) **MUST** exist under the governed parameters directory and be **registered** in the schema catalog with a stable `$ref` (e.g., `schemas.layer1.yaml#/policy/s6_selection`). The exact basenames **MUST** be enumerated in **S0.2.2’s governed set 𝓟** so that changing any of their bytes flips `parameter_hash`. 
* **Schema requirement.** Each policy file **MUST** validate against its JSON-Schema with **`additionalProperties: false`** (unknown keys are a **hard FAIL**).
* **Version pinning.** The policy file(s) **MUST** declare `policy_semver` and **MUST** be pinned by `$ref` version; bump rules follow §16 (MAJOR when keys or semantics change in a breaking way).

**4.2 Keys & domains (values, defaults, and semantics)**
The policy **MUST** define the following keys in the **`defaults`** block, with optional currency-specific overrides in **`per_currency`** (keys = **uppercase ISO-4217**):

* `emit_membership_dataset : bool` — default **false**. If true, S6 **produces** the convenience **membership** dataset (authority note still applies in §5.2).
* `log_all_candidates : bool` — default **true**.

  * **true:** write one `rng_event.gumbel_key` **for every considered candidate** (recommended).
  * **false:** write keys **only for selected candidates**; the validator **MUST** use **counter-replay** in stable iteration order to regenerate the missing keys (§9.3).
* `max_candidates_cap : int ≥ 0` — default **0** (no cap). If >0, S6 **MUST** truncate the S3 domain to the first **`max_candidates_cap`** countries by **S3 `candidate_rank`** (no re-order).
* `zero_weight_rule : enum{"exclude","include"}` — default **"exclude"**.
* `dp_score_print : int ≥ 0` — **optional, diagnostic-only** (formatting for logs/layer1/1A/UI). It MUST NOT affect scoring, selection, RNG budgets, or any validator checks.

  * **"exclude":** candidates with **S5 weight == 0** are **dropped** from the domain (no key written; they do not contribute to selection or event counts).
  * **"include":** zero-weight candidates are **considered for logging** (keys may be written per `log_all_candidates`) but are **not eligible for selection** (`ln(0) = −∞`).
  * **Definitions (binding):**

    * **Considered set** = S3 candidates after cap and policy filters (**may** include zero-weights if `"include"`).
    * **Eligible set** = considered set **with weight > 0**. Selection **MUST** draw from the **eligible set** only; the validator **MUST** treat expected event counts using the **considered** set, and cardinality using the **eligible** set.

* **Domain rules (binding).**

  * Currency overrides: `per_currency["[A–Z]{3}"]` **MAY** override any key above except `log_all_candidates` and `dp_score_print` (both global-only, to keep validator mode uniform).
  * ISO-level overrides (per country) are **not allowed** unless a future schema explicitly adds them (presently prohibited).
  * Unknown currency codes, non-uppercase keys, or out-of-range values are **policy validation failures** (see 4.4).

**4.3 Override precedence (deterministic resolution)**

* Resolution order per merchant **MUST** be: **per-currency override → defaults**.
* If a key is **absent** in a per-currency block, the **defaults** value **MUST** be used.
* If both blocks omit a **required** key, this is a **schema error** (hard FAIL).
* Overrides **MUST NOT** change semantics outside §6 (e.g., cannot redefine tie-breaks, RNG families, or numeric environment bound in S0.8). 

**4.4 Parameter hashing & manifests (lineage participation)**

* **Governed set 𝓟.** All S6 policy basenames are **required members of 𝓟**; changing any of their **bytes** **MUST** flip `parameter_hash` and therefore re-partition all **parameter-scoped** reads/writes that carry it. 
* **Manifest participation.** All artefacts S6 **opens** (S3/S4/S5 datasets, ISO registry, schemas, dictionary, S0.8 numeric policy files, S6 policy files) **MUST** be included in the **`manifest_fingerprint`** calculation as per S0.2.3 (flip on any byte change). 
* **Path ↔ embed equality.** Where lineage fields are embedded, their values **MUST** equal the partition tokens byte-for-byte; violations are **hard FAIL** during pre-flight (§3.3/§3.4). 
* **Policy validation (binding).** Prior to any selection work, the S6 runner **MUST**:

  1. Validate the policy file(s) against the registered `$ref`;
  2. Resolve overrides deterministically (§4.3);
  3. Record the **effective** policy (global + per-currency) in the S6 validation bundle for provenance;
  4. Abort with **`E_POLICY_SCHEMA`**/**`E_POLICY_DOMAIN`** on schema/domain violations (unknown keys, bad ranges, non-uppercase ISO-4217), or **`E_POLICY_CONFLICT`** when resolution yields an inconsistent state (e.g., `max_candidates_cap` < size of **eligible** positives for a normative test case).

**Notes on numeric & RNG environment.** S6 **inherits S0.8’s** numeric determinism (binary64, RNE, FMA-off, no FTZ/DAZ) and the RNG envelope law; policy **MUST NOT** attempt to change number modes or RNG families—those are fixed by the layer and schema authorities.

---

# 5. Outputs — datasets & contracts **(Binding)**

**5.1 RNG event families (authoritative; partitions `{seed, parameter_hash, run_id}`)**
S6 **produces** the following RNG artefacts; these are the **sole authoritative evidence** of selection and are governed by the layer RNG envelope law (open-interval mapping; `before/after/blocks/draws`; one **trace** append per event).

* **`rng_event.gumbel_key`** — **logging mode:** if `log_all_candidates=true`, one event per **considered** candidate (post-cap, post-policy); if `false`, keys only for **selected** candidates (budgets unchanged; validator uses §9.3 counter-replay).

  * **Schema anchor:** `schemas.layer1.yaml#/rng/events/gumbel_key`.
  * **Dictionary entry & path pattern:** `logs/layer1/1A/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.
  * **Payload (binding semantics):** `merchant_id`, `country_iso`, **`weight` (S5 subset-renormalised)**, the **uniform `u`**, the **Gumbel `key`**, a **`selected`** flag, and optional `selection_order` (**1..K when `selected=true`; omitted otherwise**); plus the standard envelope fields.
    **Budgets:** `draws="1"`, `blocks=1` for each event.
    **Zero-weight rows:** if `weight==0` (allowed only when `zero_weight_rule="include"`), S6 **MUST NOT** emit a numeric key — set `key: null`. Such rows are **diagnostic only** and **never eligible**; `selection_order` MUST be absent.
* **Core RNG logs (updated by S6):**

  * **`rng_audit_log`** — run-scoped audit entries; one per run context per policy.
  * **`rng_trace_log`** — **exactly one cumulative row appended after each event**; saturating totals per `(module, substream_label)`. (Both are already registered with partitions `{seed, parameter_hash, run_id}`.) 

**5.2 Selection membership surface (optional convenience)**
When enabled by policy (`emit_membership_dataset=true`), S6 **MAY** write a **membership** dataset to simplify S7 joins.

* **Authority note (binding):** this surface is **entirely re-derivable** from `rng_event.gumbel_key` + S3/S5 inputs and **MUST NOT** encode or imply inter-country order; consumers **MUST** continue to obtain order exclusively from **S3 `candidate_rank`**. 
* **Schema & dictionary:** **MUST** have an approved dataset ID and JSON-Schema `$ref` registered **before** any consumer reads.
* **Primary key & partitions:** **PK** `(merchant_id, country_iso)` per `{seed, parameter_hash}`; **path↔embed equality** is binding.
* **Writer sort (non-semantic to readers):** `(merchant_id ASC, country_iso ASC)`.

**5.3 Partition law & path discipline (binding)**

* **Events/logs:** `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` for `rng_event.gumbel_key`, `rng_audit_log`, `rng_trace_log`; embedded lineage fields **MUST** equal the path tokens byte-for-byte. 
* **Membership (if produced):** `…/seed={seed}/parameter_hash={parameter_hash}/…` and embeds the **same** `parameter_hash`.

**5.4 Sort, stability & byte policy**

* **Event files:** reader semantics are **set-based**; **row order is non-semantic**.
* **Byte identity:** if the Registry pins a writer policy (codec/level/row-group), producers **MUST** adhere to it; otherwise only **value identity** is required across re-runs. (See registry notes for event/log families.) 

**5.5 Retention, ownership & gating**

* **Ownership:** S6 is the **producer** for `rng_event.gumbel_key`; core RNG logs are owned by the layer RNG emitters; consumer is **validation** (and downstream audit). 
* **Retention:** as per Dataset Dictionary (e.g., events typically **180 days**, core logs **365 days**). 
* **Read gate:** Downstream states (S7/S8) **MUST NOT** read any S6-scoped convenience surface unless the **S6 PASS** receipt (see §9) exists for the same `{seed, parameter_hash}`; for inputs derived from S5, readers **MUST** also observe the **S5 PASS** gate. 

**5.6 Cross-references (normative anchors)**

* **Event schema & dictionary entries** for `gumbel_key`, `ztp_final`, `dirichlet_gamma_vector`, and core logs are registered and versioned with partitions exactly as shown in the Dataset Dictionary and Artefact Registry.

---

# 6. Deterministic processing specification — no pseudocode **(Binding)**

**6.1 Gating (must be true to run S6).**
S6 **MUST** proceed for a merchant only if all are true:

* **S1** decided `is_multi == true` (gate carried by dictionary on upstream RNG families). 
* **S3 eligibility present** and an ordered candidate set exists (`s3_candidate_set`, home has `candidate_rank=0`, ranks total & contiguous).
* **S4** wrote exactly one `rng_event_ztp_final` fixing `K_target` for the merchant (logs under `{seed, parameter_hash, run_id}`).
* **S5** weights cache exists **and has PASS** for the same `parameter_hash` (S5 receipt present); otherwise **no read**. 

---

**6.2 Selection domain & weights (read-only authorities).**

* **Domain:** foreign candidates = **S3 `candidate_set` minus home**; intersect with S5’s `ccy_country_weights_cache` for the merchant’s settlement currency (from S5; `merchant_currency` optional). **S6 MUST NOT add countries not present in S3.**
* **Cap (optional):** if `max_candidates_cap>0`, **truncate by S3 `candidate_rank` prefix** to the first `A_cap` foreigns. **No re-order is permitted.** 
* **Zero-weight policy:**

  * `"exclude"` (default): drop candidates with S5 weight `== 0` from the **considered** set (hence also from the eligible set); **no key written**.
  * `"include"`: such countries may be **considered** (keys may be logged), but are **not eligible** for selection (see score rule below).
    *(Considered set is for logging expectations; eligible set is for selection.)*
* **Subset renormalisation:** within the **eligible** subset *(eligible ⊂ considered)*, **ephemerally renormalise** weights in **binary64** for scoring; **MUST NOT** persist any new weights (persisted weight authority remains S5).
  *Equivalence note:* renormalising on the **considered** subset yields identical numeric results because candidates with `w==0` contribute **0** to the normaliser; we write “eligible” to emphasise the selection domain.
---

**6.3 RNG substreams, numeric law, and scoring (authoritative).**

* **Uniforms:** S6 **MUST** use the S0 **open-interval** mapping $u\in(0,1)$ for all uniforms (never exact 0 or 1). 
* **Numeric environment:** **inherit S0.8** — IEEE-754 **binary64**, round-to-nearest-ties-even, **FMA off**, **no FTZ/DAZ**, deterministic libm; decision kernels run in fixed order. 
* **Iteration order:** when drawing, **iterate in S3 `candidate_rank` order** to keep substream counters reproducible. 
* **Event family (logging mode):** if `log_all_candidates=true`, write exactly **one** `rng_event.gumbel_key` for each **considered** candidate; if `false`, write keys **only for selected** candidates (validator counter-replays per §9.3). Append **exactly one** trace row after each event (per RNG trace law).
* **Score (`key`) definition:** For candidate $c$ with weight $w_c>0$, compute **binary64**
  $$
  \text{key}_c = \ln(w_c) - \ln\!\big(-\ln u_c\big),\quad u_c\in(0,1).
  $$
  **Zero-weight convention:** when `zero_weight_rule="include"` and `w_c==0`, producers set `key: null`. Validators **MUST** treat `key:null` as $-\infty$ for ordering.
---

**6.4 Selection rule (K-realisation).**

* Let $A_{\text{filtered}}$ be the **considered** foreign candidate count after policy filters/cap, and let $|\text{Eligible}|$ be the number of **eligible** candidates with $w>0$ in that domain; let $K_{\text{target}}$ come from S4.
* S6 **MUST** select the **top $K_{\text{target}}$** countries by **`key`** from the **eligible** subset; if $|\text{Eligible}| < K_{\text{target}}$, select **all $|\text{Eligible}|$** (shortfall).

---

**6.5 Tie-breaks (total order).**
When two candidates have equal **`key`** in binary64:

1. choose lower **S3 `candidate_rank`** (ascending);
2. then `country_iso` **A→Z**.
   Tie-breaks are **binding** to ensure a total order consistent with S3. 

---

**6.6 Order-authority separation (no new order).**
S6 **MUST NOT** persist or imply inter-country order. Any projected order for display **MUST** inherit **S3 `candidate_rank`** for selected members; egress order remains defined only within country (S8). 

---

**6.7 Logging discipline (budgeting & modes).**

* **Stable loop:** produce keys in **S3 `candidate_rank`** order; **logging mode** → if `log_all_candidates=true`, **one** `gumbel_key` per **considered** candidate; if `false`, keys only for **selected** candidates. 
* **Expected event count per merchant:**  
  - if `log_all_candidates=true`: $\mathrm{events}(\texttt{gumbel\_key})=A_{\text{filtered}}$;  
  - if `false`: $\mathrm{events}(\texttt{gumbel\_key})=K_{\text{realized}}$.  
  (after zero-weight policy and cap). The validator **counter-replays** missing keys in reduced-logging mode (§9.3).
* **Trace rule:** emit **exactly one** `rng_trace_log` row **after each event**; cumulative totals reconcile to sum of event budgets for the `(module, substream_label)` key. 

---

**6.8 Determinism & idempotence.**
With identical `{seed, parameter_hash, run_id}`, the **considered** set, the sequence of uniforms, the **keys**, and the selected membership **MUST** be identical across re-runs; envelopes satisfy S0 budget/counter invariants; path↔embed equality holds. 

---

**6.9 Write semantics (publish discipline).**

* **Write-once partitions.** On success, atomically publish event/log files under `{seed, parameter_hash, run_id}`; optional membership dataset under `{seed, parameter_hash}`.
* **Row/byte stability.** Reader semantics are set-based; if a registry writer policy is pinned (codec/level/row-group), producers **MUST** adhere to it; otherwise **value-identity** across re-runs is sufficient. 

---

# 7. Invariants & integrity constraints **(Binding)**

**7.1 Gating invariants (must hold per merchant before selection).**

* **S1 hurdle:** merchant is **multi** (`is_multi==true`) as carried via dictionary gating. 
* **S3 domain:** `s3_candidate_set` exists; **home has `candidate_rank=0`**, ranks are **total & contiguous** per merchant (no gaps/dups).
* **S4 target:** exactly **one** `rng_event_ztp_final` fixing `K_target` under `{seed, parameter_hash, run_id}`. 
* **S5 weights:** `ccy_country_weights_cache` exists **and S5 PASS is present** for the **same `parameter_hash`** (**no PASS → no read**). 

**7.2 Domain & FK invariants.**

* **Subset law:** Selected foreigns ⊆ S3 **foreign** candidates (home excluded) **and** ⊆ S5 weight support for the merchant’s currency.
* **ISO/ISO-4217 validity:** all `country_iso` and `currency` values are **uppercase** and **FK-valid** against the canonical registries. 

**7.3 Cardinality invariant.**
For each merchant, the realized set size is
$$
|\text{selected}| = K_{\text{realized}}=\min\!\big(K_{\text{target}},\,|\text{Eligible}|\big),
$$
where $|\text{Eligible}|$ is the eligible-count **after** applying `max_candidates_cap` and the `zero_weight_rule` (positives only). Shortfall $|\text{Eligible}| < K_{\text{target}}$ **MUST** result in selecting **all $|\text{Eligible}|$**. 

**7.4 Tie-break determinism.**
When `key` values are exactly equal in **binary64**, order **MUST** resolve by **S3 `candidate_rank`** (ascending), then `country_iso` A→Z, ensuring a **total order consistent with S3**. 

**7.5 RNG event/logging invariants (authoritative evidence).**

* **Per-merchant event count:**  
  - if `log_all_candidates=true`, equals the **considered** domain size after policy/cap (`A_filtered`).  
  - if `false`, equals **`K_realized`** (validator **counter-replays** the missing keys).
* **Isolation:** S6 **MUST NOT** write to any RNG families other than those declared for S6; validator finds **only** S6 families and matching trace deltas. 
* **Trace duty:** **exactly one** cumulative `rng_trace_log` row is appended **after each event**; pairing/replay relies on **envelope counters**, not file order. 

**7.6 Partitioning & lineage equality.**

* **Events/logs:** paths are `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`; embedded lineage fields (where present) **MUST** equal the path tokens **byte-for-byte**; for `rng_trace_log`, lineage is enforced via partition keys. 
* **Tables (parameter-scoped):** any convenience **membership** dataset is partitioned by `{seed, parameter_hash}` and **MUST** embed the **same** `parameter_hash`. 

**7.7 Primary key & uniqueness.**

* If the **membership** surface is produced: **PK** `(merchant_id, country_iso)` is **unique** per `{seed, parameter_hash}`; **no duplicates** per merchant. (Authority remains the RNG events; membership is re-derivable.) 

**7.8 Order-authority separation.**
No S6 output **may encode or imply** inter-country order; consumers **MUST** continue to obtain order exclusively from **S3 `candidate_rank`**. `outlet_catalogue` carries **no** cross-country order.

**7.9 Idempotence & stability.**
With identical `{seed, parameter_hash, run_id}` and identical inputs, the **considered** set, uniform sequence, **keys**, and selected membership are **identical** across re-runs. If a writer policy is pinned in the registry, producers **MUST** adhere to it; otherwise **value-identity** suffices.

**7.10 S5 weight authority preserved.**
Any subset renormalisation used during selection is **ephemeral** and **MUST NOT** be persisted; persisted currency→country weights remain **S5** (`Σ=1±1e-6`, bounds). 

**7.11 PASS-gate coupling.**

* **S6 PASS**: S7/S8 **MUST NOT** read S6 convenience surfaces without `S6_VALIDATION.json` + `_passed.flag` for the same `{seed, parameter_hash}`.
* **S5 PASS**: S6 **MUST** have verified S5 PASS before reading weights (parameter-scoped receipt). 

**7.12 Numeric & RNG law inheritance.**
All decision-critical math executes under **S0.8** (IEEE-754 binary64; RNE; FMA-off; no FTZ/DAZ); uniforms use the **open-interval** mapping; counters/budgets obey the layer envelope rules. 

---

# 8. Error handling, edge cases & degrade ladder **(Binding)**

**Overview.** S6 is **fail-closed** for structural/lineage/RNG breaches; otherwise it returns **deterministic empties** for well-defined edge cases. State-level `E_*` errors MUST also map to S0’s failure classes (F2–F10) for fleet observability.

---

## 8.1 Deterministic empty selections (non-error outcomes)

When these conditions hold, S6 **MUST** emit a **valid, empty selection** for the merchant (no rows in the optional membership surface) and record a **reason_code** (diagnostic). RNG events are **not** written for un-considered candidates.

* **`NO_CANDIDATES`** — $A=0$: S3 exposes only `home` (no foreigns). 
* **`K_ZERO`** — S4 fixed `K_target=0` (short-circuit/downgrade path). 
* **`ZERO_WEIGHT_DOMAIN`** — After applying S6 policy filters (cap + `zero_weight_rule`), **no candidate with weight>0** remains in the eligible set (S5 is still PASS). 
* **`CAPPED_BY_MAX_CANDIDATES`** *(diagnostic only)* — Domain truncated by `max_candidates_cap` (selection still proceeds if any eligible >0 remain).

Shortfall **is not an error**: if $|\text{Eligible}| < K_{\text{target}}$, S6 MUST select **all $|\text{Eligible}|$** (validator may log `SHORTFALL_ELIG_LT_K`). 

---

## 8.2 Hard FAIL conditions (run-abort for the affected merchant)

On any of the following, S6 **MUST** NOT publish outputs for the merchant; it **MUST** emit an `E_*` with a canonical S0 failure class.

* **`E_UPSTREAM_GATE`** — Missing required inputs or gates:

  * S5 PASS receipt absent/invalid for the same `parameter_hash` (**no PASS → no read**);
  * `s3_candidate_set` missing/malformed (no home, non-contiguous ranks);
  * S4 `ztp_final` missing/duplicated.
    → Map to **F1/F2/F9** as appropriate.

* **`E_RNG_ENVELOPE`** — RNG envelope or accounting violations in S6 events/logs: missing `before/after/blocks/draws`, counter deltas inconsistent, audit not present before first draw, or trace row not appended **after each event**. → **F4**. 

* **`E_LINEAGE_PATH_MISMATCH`** — Any embedded lineage field differs from its partition token (e.g., `{seed, parameter_hash, run_id}`). → **F5**. 

* **`E_SCHEMA_AUTHORITY`** — Dataset or log does not validate against the **JSON-Schema** anchor registered in the dictionary (JSON-Schema is sole authority). → **F6**. 

* **`E_NUMERIC_POLICY`** — S0.8 numeric environment violation detected on an ordering/decision path (binary64, RNE, **FMA off**, **no FTZ/DAZ**, deterministic libm). → **F7**.

* **`E_EVENT_COVERAGE`** — Required S6 RNG families missing/inconsistent (e.g., wrong count of `rng_event.gumbel_key` vs. **considered** domain, when `log_all_candidates=true`). → **F8**. 

* **`E_DUP_PK`** — Duplicate `(merchant_id, country_iso)` in the optional membership surface. → **F10**. 

* **`E_ORDER_INJECTION`** — Any S6 output encodes or implies inter-country order (S3 `candidate_rank` is the **sole** authority; `outlet_catalogue` explicitly carries **no** cross-country order). → **F9**.

---

## 8.3 Policy and configuration failures (pre-flight)

These abort **before** selection:

* **`E_POLICY_SCHEMA` / `E_POLICY_DOMAIN`** — Policy fails JSON-Schema or value ranges/uppercase code rules.
* **`E_POLICY_CONFLICT`** — Deterministic resolution (§4.3) yields an inconsistent effective policy.
  Map to S0 **F2/F1** as applicable (parameter/fingerprint & ingress/schema classes). 

---

## 8.4 RNG isolation & cross-stream interaction

S6 **MUST** write only its declared RNG families (e.g., `rng_event.gumbel_key`) and **MUST NOT** write to S1–S5 families; validator confirms **only** S6 families appear and trace deltas match appends. Violations → `E_RNG_ENVELOPE` (**F4**). 

---

## 8.5 I/O integrity & publish atomics

Any short write, partial instance, non-atomic promote, or mismatched writer policy (when byte-identity is pinned) is `E_IO_ATOMICS` → **F10**. The partition law and path discipline from the dictionary/registry **MUST** be obeyed. 

---

## 8.6 Degrade vocabulary (per-merchant; closed set)

S6 **MUST** record one of the following **reason_codes** when emitting a deterministic empty (non-error) or when cap diagnostics apply:

* `{none, NO_CANDIDATES, K_ZERO, ZERO_WEIGHT_DOMAIN, CAPPED_BY_MAX_CANDIDATES}`

These are **diagnostics**; they **do not** authorize re-ordering, re-weighting, or policy changes downstream. (S7 remains responsible for count allocation; S3 remains order authority.) 

---

## 8.7 Exit codes (runner)

* **`SUCCESS`** — All merchants processed; PASS receipt written (§9).
* **`STRUCTURAL_FAIL`** — Any of §8.2/§8.3 failures encountered (per-merchant aborts allowed; run fails if policy dictates).
* **`RNG_ACCOUNTING_FAIL`** — Envelope/trace breaches.
* **`RE_DERIVATION_FAIL`** — Validator cannot reconstruct membership from events + S3/S5 (or counter-replay when `log_all_candidates=false`).
* **`SHORTFALL_NOTED`** — Non-error; at least one merchant had $|\text{Eligible}| < K_{\text{target}}$.

(Exact numeric codes enumerated in Appendix **B** alongside RNG family names and schema anchors.) 

---

## 8.8 Cross-state gates (consumption rules)

Downstream states **MUST** verify the **S6 PASS** receipt before reading S6 convenience surfaces, and continue to respect the **S5 PASS** gate when joining S5 outputs. `No PASS → no read` remains binding. 

---

# 9. Validation battery & PASS gate **(Binding)**

**Purpose.** Prove that S6 produced a **correct, reproducible** foreign-set membership under the S0–S5 contracts, with **isolation** to S6 RNG families, and publish a **receipt** that downstream MUST check (**no PASS → no read**). JSON-Schema + the Dataset Dictionary remain the **sole** authorities for shapes/paths/partitions. 

---

## 9.1 Structural validation (schemas, partitions, lineage)

**Inputs present & valid (precondition recap).**

* `s3_candidate_set` exists for `parameter_hash={…}` and validates against its `$ref`; ranks total/contiguous with home=0. 
* Exactly one `rng_event_ztp_final` per merchant under `{seed,parameter_hash,run_id}` (schema-valid). 
* `ccy_country_weights_cache` exists for **the same** `parameter_hash` and S5 **PASS** is present (S5 receipt + valid `_passed.flag`). **No PASS → no read.** 

**S6 outputs/logs (produced here).**

* `rng_event.gumbel_key`, `rng_audit_log`, `rng_trace_log` validate against registered schema anchors; partitions are `{seed,parameter_hash,run_id}`; **path↔embed equality** holds where embedded (trace lineage enforced via partition keys). 
* If the optional **membership** dataset is enabled, it validates against its `$ref`, is partitioned by `{seed, parameter_hash}`, and embeds the **same** `parameter_hash`. **PK** `(merchant_id,country_iso)` is unique. 

**Lineage discipline.** For all produced artefacts, embedded `{seed,parameter_hash,run_id}` (if present) **MUST** equal path tokens **byte-for-byte**. Violations are **hard FAIL**. 

---

## 9.2 Content checks (domain, cardinality, order separation)

* **Subset law:** Selected foreigns ⊆ S3 **foreign** candidates and ⊆ S5 weight support for the merchant’s currency. (Home is never selectable.) 
* **Cardinality:** For each merchant,
  $$
  |{\text{selected}}| = K_{\text{realized}} = \min(K_{\text{target}},\,|\text{Eligible}|),
  $$
  where $|\text{Eligible}|$ is the count of candidates with $w>0$ **after** policy filters and any S3-rank cap. Shortfall (`|\text{Eligible}| < K_{\text{target}}`) **MUST** result in selecting **all `|\text{Eligible}|`**. 
* **Tie-break determinism:** When **`key`** values are equal in **binary64**, break by **S3 `candidate_rank`** (ascending), then by `country_iso` A→Z. (Ensures a total order consistent with S3.)
* **No order encoding:** Any S6 surface (incl. membership) **MUST NOT** encode or imply inter-country order; downstream MUST continue to read order **exclusively** from S3 `candidate_rank`. 

---

## 9.3 Re-derivation (authoritative proof of selection)

**Mode A – `log_all_candidates = true` (recommended).**

* **Expectations:** For each merchant, **exactly one** `rng_event.gumbel_key` exists **per considered candidate** (`A_filtered`). The validator recomputes **`key` values** from **logged `u` (or verifies logged `key`) + S5 weights + S3 domain** in the **same iteration order (S3 rank)** and recomputes the **top-`K_target`** set. The recomputed membership **MUST** equal the published membership (or, if no membership surface is written, the validator must derive the same set from events). 

**Mode B – `log_all_candidates = false` (reduced logging).**

* **Expectations:** Only **selected** candidates have logged keys. The validator performs **counter-replay** on the S6 substream in **S3-rank order** to regenerate the missing keys, recomputes **key values**, and verifies the selected set equals the run’s published membership. Any divergence is **FAIL**. (This mirrors S5’s “re-derive to byte equality” posture, adapted to S6’s stochastic key logs.)

**Numeric/RNG law:** Re-derivation runs under the S0.8 numeric profile; uniforms use the S0 open-interval mapping; pairing uses **envelope counters**, not file order. 

---

## 9.4 RNG isolation & accounting

* **Family isolation:** Only S6 RNG families (e.g., `rng_event.gumbel_key`) appear in S6; validator finds **no writes** to S1–S5 families. 
* **Trace duty:** After **each** RNG event append, **exactly one** cumulative `rng_trace_log` row is appended; **draws/blocks/events** totals reconcile per `(module,substream_label)`. Any counter/total drift is **FAIL**. 
* **Event coverage:** When `log_all_candidates=true`, per-merchant count of `gumbel_key` events **equals** `A_filtered`. (When `false`, coverage is verified via counter-replay.) 

---

## 9.5 Validator artefacts (S6 PASS receipt; seed/parameter-scoped)

S6 writes a **seed/parameter-scoped receipt** under the S6 task path:

```
data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/
  S6_VALIDATION.json          # summary: structural/content/RNG checks; per-merchant diagnostics
  _passed.flag                # single line: 'sha256_hex = <hex64>'
```

* `_passed.flag` contains the **SHA-256** over the **ASCII-lexicographic** concatenation of all other files in this receipt (currently **`S6_VALIDATION.json`**; exclude the flag itself). This mirrors the **parameter-scoped** receipt pattern used in S5 and the layer-wide gate pattern used for egress. **Atomic publish** applies.
* **Minimum required fields (normative) in `S6_VALIDATION.json`:**
  `seed`, `parameter_hash`, `policy_digest` (hex64 of S6 policy bytes), `merchants_processed`, `events_written`, `gumbel_key_expected` vs `written` (by mode), `shortfall_count`, `reason_code_counts{NO_CANDIDATES,K_ZERO,ZERO_WEIGHT_DOMAIN,CAPPED_BY_MAX_CANDIDATES}`, `rng_isolation_ok: bool`, `trace_reconciled: bool`, `re_derivation_ok: bool`. (Per-merchant detail may be emitted to a sibling `S6_VALIDATION_DETAIL.jsonl`.)
* **`policy_digest` construction (binding):** compute as **`sha256_hex` of the byte-concatenation of all S6 policy files, sorted by ASCII basename**. This ordering is binding to avoid toolchain drift.

---

## 9.6 PASS/consume semantics (gates)

* **S6 PASS (seed/parameter-scoped):** All checks in §§9.1–9.4 succeed **and** the receipt exists with a valid `_passed.flag` whose hash matches its contents. **Downstream S7/S8** MUST verify S6 PASS for the same `{seed,parameter_hash}` before reading any S6 convenience surface (**no PASS → no read**). 
* **S5 PASS (dependency):** S6 MUST have verified S5 PASS for the same `parameter_hash` before reading weights; consumers that touch S5 surfaces continue to verify S5 PASS independently. 
* **Layer-wide PASS (unchanged):** Egress readers (e.g., `outlet_catalogue`) keep verifying the **fingerprint-scoped** validation bundle `_passed.flag` per S0/Dictionary.

---

## 9.7 Failure handling (publish discipline)

* **FAIL:** Any breach in §§9.1–9.4, or missing/invalid `_passed.flag`, **aborts** the run for the affected merchant set; **no partial publishes** to S6 outputs. Follow S0 abort semantics (write failure sentinel if defined; freeze; non-zero exit). 
* **Idempotence:** Re-running S6 with identical inputs and policy bytes must yield **value-identical** outputs and an identical PASS receipt; if a writer policy is pinned in the registry, **byte-identity** applies. 

---

# 10. Lineage, partitions & identifiers **(Binding)**

**Purpose.** Fix **where S6 writes**, **which identifiers appear**, and the **immutability/atomicity** rules. JSON-Schema + the Dataset Dictionary remain the single authorities for shapes, paths, and partition keys. 

---

## 10.1 Partitioning law (normative)

* **RNG events & core logs (S6-produced/updated).**
  **Path:** `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`
  **Applies to:** `rng_event.gumbel_key`, `rng_audit_log`, `rng_trace_log`. **These IDs and partition keys are already defined in the Dictionary/Registry.** 

* **S6 convenience membership dataset (if produced).**
  **Path:** `…/seed={seed}/parameter_hash={parameter_hash}/…` — seed is required because membership is **seed-dependent**; `parameter_hash` binds the parameter scope. **S3 deterministic inputs remain parameter-scoped only** (`parameter_hash` partition), per their contracts. 

---

## 10.2 Embedded lineage & path↔embed equality (binding)

* **Events/logs.** Where lineage fields are embedded, **`{seed, parameter_hash, run_id}` MUST byte-equal the path tokens**. For `rng_trace_log`, lineage is enforced via its partition keys and cumulative rows; one trace row is appended **after each event**. **Any mismatch is a hard FAIL.** 
* **Parameter-scoped tables.** Any S6 membership table (if enabled) **embeds the same `parameter_hash`** as its partition (and **MUST NOT** embed a different seed than its path). S3 inputs embed `parameter_hash` by spec. 

---

## 10.3 Identifier semantics (roles; non-interchangeable)

* **`seed`** — Determines stochastic outcomes; partitions **all RNG event/log paths** and any seed-dependent convenience surface. **Never appears in parameter-scoped S3/S5 tables.** 
* **`parameter_hash`** — Hash of the governed set **𝓟** (per S0.2.2). **All parameter-scoped inputs (S3/S5)** and the **S6 receipt/membership** carry this. **Policy bytes for S6 are required 𝓟 members**, so changing them flips this value and re-partitions reads/writes. 
* **`run_id`** — Partitions **logs only**; **does not change modelling state** or selection outcomes. Multiple `run_id`s may exist for the same `{seed, parameter_hash}` without changing the dataset semantics. 
* **`manifest_fingerprint`** — Layer-wide content/address for **egress** and the layer validation bundle; **not** used by S6 outputs. (S3/S5 keep using `parameter_hash`; egress (e.g., `outlet_catalogue`) remains fingerprint-scoped.) 

---

## 10.4 Atomic publish, immutability & idempotent retries (binding)

* **Write-once partitions.** Producers **MUST** stage → fsync → **atomic rename** into the dictionary location; **no partials** or mismatched partitions. Once published with PASS, **immutable**. 
* **Idempotence.** Re-running S6 with identical `{seed, parameter_hash, run_id}` and inputs **MUST** yield **value-identical** events/logs (and receipt). If a registry writer policy (codec/level/row-group) is pinned for the family, **byte-identity** applies. 
* **Resume semantics.** On failure, producers **MUST NOT** partially publish; they may retry the same `{seed, parameter_hash, run_id}` after cleaning any temp paths. (Receipt rules in §9 control final gating.) 

---

## 10.5 Canonical path patterns (normative)

* **`rng_event.gumbel_key`** → `logs/layer1/1A/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` (schema: `schemas.layer1.yaml#/rng/events/gumbel_key`). 
* **`rng_audit_log`** → `logs/layer1/1A/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl` (schema: core audit). 
* **`rng_trace_log`** → `logs/layer1/1A/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl` (schema: core trace). 
* **S3 input** `s3_candidate_set` → `data/layer1/1A/s3_candidate_set/parameter_hash={parameter_hash}/…` (schema: `schemas.1A.yaml#/s3/candidate_set`). 
* **S5 input** `ccy_country_weights_cache` → `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/…` with **S5 PASS receipt** co-located. 
* **S6 receipt (PASS gate)** → `data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/(S6_VALIDATION.json, _passed.flag)` (see §9). 

---

## 10.6 Producer/consumer & ownership

* **Producers:**

  * `rng_event.gumbel_key` — **S6** only.
  * `rng_audit_log` / `rng_trace_log` — layer RNG emitters; S6 **appends** per envelope law. 
  * Membership dataset (if enabled) — **S6** only; **authority remains the RNG events**.
* **Consumers:** Validation (S6 validator), then **S7/S8** post **S6 PASS**. Egress (`outlet_catalogue`) continues to rely on **fingerprint-scoped** validation per Dictionary. 

---

## 10.7 Cross-artefact lineage consistency (binding checks)

* **Path/Embed parity.** Every produced artefact with embedded lineage **MUST** match its path tokens **byte-for-byte**; any drift is `E_LINEAGE_PATH_MISMATCH`. 
* **Authority separation.** S3’s `candidate_rank` remains the **sole** order authority; S6 outputs **MUST NOT** encode order. (Dictionary and S3 spec reiterate this.)
* **Gate coupling.** S6 **MUST** verify **S5 PASS** (parameter-scoped receipt) before reading S5; downstream **MUST** verify **S6 PASS** before consuming any S6 convenience surface. **No PASS → no read.** 

---

# 11. Interaction with RNG & logs **(Binding)**

**Purpose.** Pin exactly **which RNG families** S6 produces, how **substreams** are derived, the **budgeting/trace** law (`before/after/blocks/draws`), and what the **producer vs validator** may read/write.

---

## 11.1 Event families & substream taxonomy (authoritative)

* **Produced by S6 (events):**
  **`rng_event.gumbel_key`** — **logging mode:** if `log_all_candidates=true`, one event **per considered candidate** (post-cap & policy filter); if `false`, keys only for **selected** candidates (validator counter-replays missing keys per §9.3). **Schema anchor:** `schemas.layer1.yaml#/rng/events/gumbel_key`. **Partition:** `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`.

* **Core logs updated by S6:**
  **`rng_audit_log`** and **`rng_trace_log`**, both under `{seed, parameter_hash, run_id}` per the Dataset Dictionary. **Trace is cumulative per `(module, substream_label)`** and **emits exactly one row after each RNG event append** (saturating totals). 

* **Optional control event:** **`rng_event.stream_jump`** — explicit Philox stream/substream jump records (enabled only if the registry entry is present for 1A). 

* **Module & substreams (naming convention for S6):**
  **`module="1A.foreign_country_selector"`**, **`substream_label ∈ {"gumbel_key","stream_jump"}`**; IDs & partitions follow the registry/dictionary listings above. 

---

## 11.2 Substream derivation & ID tuple (normative)

* **Keyed substreams.** For event family label **ℓ** (e.g., `"gumbel_key"`) and ordered **ids**, derive the keyed Philox state per **S0** (UER/SER framing → SHA-256 → `(k,(hi,lo))`). **IDs for `gumbel_key`:** `(merchant_u64, country_iso)` with **uppercase ISO2** under UER; types fixed by schema. **All draws for that event must come from `PHILOX(k(ℓ,ids),·)` with a monotonically advancing 128-bit counter.** 

* **Open-interval uniforms.** Uniforms **MUST** use S0’s **strict-open** mapping $u\in(0,1)$ with the binary64 hex literal multiplier; exact `0.0`/`1.0` are **forbidden** (apply the clamp rule). 

* **Lane policy (single-uniform).** Single-uniform events consume the **low lane** from one Philox block and **discard the high lane** → **`blocks=1`, `draws="1"`** (see budgeting law below). **`gumbel_key` is a single-uniform event.** 

---

## 11.3 Budgeting law: `before/after/blocks/draws` (binding)

* **Envelope arithmetic.** For every RNG event row:
  `blocks := u128(after) − u128(before)` (unsigned 128-bit); **`draws`** is a **decimal uint128 string** equal to the **actual number of $U(0,1)$** consumed by the sampler(s) for that event and is **independent** of the counter delta. 

* **Budgets by family.**
  **`gumbel_key`**: **`blocks=1`, `draws="1"`** (single uniform);
  **non-consuming** markers (if any) must have `before==after`, `blocks=0`, `draws="0"`. (Patterns follow the layer’s envelope rules.) 

* **Trace duty (per event).** After **each** RNG event append, S6 **MUST** append **exactly one** cumulative row to **`rng_trace_log`** for `(module, substream_label)`; totals reconcile (saturating) as specified by the dictionary/core schemas.

---

## 11.4 Producer vs validator scope (isolation & allowed reads)

* **Producer scope (S6 runner):**
  **MUST write** only the S6 families (`rng_event.gumbel_key` + optional `stream_jump`) and **MUST update** `rng_audit_log`/`rng_trace_log` per the envelope/trace law; **MUST NOT write** to S1–S5 event families. 

* **Validator scope (read-only):**
  **MAY read** S6 events and the **core RNG logs** to: (a) reconcile budgets/totals; (b) prove isolation (no cross-family writes); (c) re-derive selection from logged keys or via **counter-replay** in S3-rank order when `log_all_candidates=false` (see §9). **Validator MUST NOT write** RNG logs. 

---

## 11.5 Event coverage & expected counts (binding)

* **Per-merchant coverage.** The number of `rng_event.gumbel_key` events **MUST equal** the size of the **considered** domain **after** applying `max_candidates_cap` and `zero_weight_rule` (when `log_all_candidates=true`). If reduced logging is enabled, coverage is verified via **counter-replay** (see §9). 

* **Cumulative totals.** On the **final** `rng_trace_log` row for a given `(module, substream_label)`, validators check `draws_total = Σ parse_u128(draws)` and `blocks_total = Σ blocks` (saturating), per the core schema guidance. 

---

## 11.6 Partitions, lineage & equality (binding)

* **Partitions:** All S6 RNG events and core logs **MUST** live under `…/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` with **embedded lineage equal to path tokens** where present. Mismatch is **hard FAIL**.

* **Immutability & idempotence:** Event/log partitions are **write-once**; re-runs with identical `{seed, parameter_hash, run_id}` must be **value-identical** (and **byte-identical** if the registry pins a writer policy). 

---

## 11.7 Cross-state consistency clauses (binding)

* **S4 handoff:** S6 **reads** `K_target` exclusively from **`rng_event.ztp_final`** (one per resolved merchant) and **must not** infer it elsewhere. 
* **S5 handoff:** S6 **reads** weights only from **`ccy_country_weights_cache`** after verifying **S5 PASS** for the same `parameter_hash` (**no PASS → no read**). 

---

# 12. Performance, scaling & resource envelope **(Informative; determinism sub-clauses Binding)**

**Scope.** This section sets practical run-shape expectations and operational envelopes for S6. Items explicitly marked **(Binding)** are determinism requirements that implementers **must** satisfy; the rest are guidance to hit predictable performance without altering behaviour.

---

## 12.1 Cardinalities & expected volumes

* Let **M** be the number of merchants passing S6 gating; let **Aₘ** be each merchant’s foreign candidate count from S3; after policy (`max_candidates_cap`, `zero_weight_rule`) define **A_filtered,ₘ**.
* **Event counts.**

  * If `log_all_candidates=true`: total `rng_event.gumbel_key` ≈ **Σₘ A_filtered,ₘ** (Binding expectation is enforced in §9).
  * If `false`: total events ≈ **Σₘ K_realized,ₘ**; validator uses **counter-replay** to cover missing keys (see §9).
* **Data written.** Core RNG logs grow linearly with the number of events (one **trace** append per event). 

## 12.2 Concurrency & determinism (Binding)

* **12.2.1 Concurrency unit = merchant (Binding).** Work **MAY** be sharded by merchant, but **MUST NOT** interleave state for the same merchant across shards.
* **12.2.2 Shard-count invariance (Binding).** Changing the number of shards/threads **MUST NOT** change: considered domain per merchant, uniform draw sequence, selected set, or the PASS receipt.
* **12.2.3 Deterministic merges (Binding).** Independent of shard count, producers **MUST**:

  * iterate candidates in **S3 `candidate_rank`** order when drawing;
  * logging mode: if `log_all_candidates=true`, write one `gumbel_key` per **considered** candidate; if `false`, write keys only for **selected** candidates;
  * append **exactly one** `rng_trace_log` row **after each** event;
  * ensure any optional membership surface is **writer-sorted** `(merchant_id, country_iso)` (row order non-semantic to readers).
* **12.2.4 Writer policy (Binding when pinned).** If the Registry pins codec/level/row-group policy for an S6 family, producers **MUST** use it (byte-identity); otherwise value-identity suffices. 

## 12.3 Memory envelope (per merchant)

* **Working set.** Implementation **should** bound peak memory to **O(A_filtered)** per merchant: weights (read-only), one uniform, one **key** per candidate, plus small envelope state.
* **Streaming discipline.** **Prefer** streaming: compute→emit events per candidate in order; avoid accumulating all **keys** when `A_filtered` is large (use online top-K).
* **Join posture.** Reads should stream-join **S3 domain** with **S5 weights** by `country_iso` (both uppercase, FK-valid) to avoid full materialisations. (Authority on domains from schemas/dictionary remains binding.) 

## 12.4 CPU envelope & algorithmic shape

* **Per-merchant complexity.** Expected **O(A_filtered · log K_target)** for top-K selection with a bounded structure; **O(A_filtered)** if using Gumbel top-K with an online threshold scheme.
* **Numerics (Binding).** All scoring and comparisons execute under **S0.8** (IEEE-754 binary64; RNE; FMA-off; no FTZ/DAZ). Any deviation is a run-fail (see §8 `E_NUMERIC_POLICY`). 

## 12.5 I/O & file layout

* **Events/logs.** Expect small JSONL chunks per partition; throughput scales linearly with events (see §12.1). **Row order is non-semantic** to readers. 
* **Optional membership surface.** One file per `{seed, parameter_hash}` partition is **recommended** for simpler atomic promote; if the Registry pins a writer policy, follow it (Binding when pinned). 

## 12.6 Retry cost & atomicity (Binding cross-ref §10.3)

* **Staging→atomic publish.** Producers **MUST** stage to a temp path, fsync, and **atomically rename** into place; **no partial publishes**. Re-runs with the same `{seed, parameter_hash, run_id}` are idempotent (value-identical; byte-identical if policy pinned). 
* **Failure handling.** On any §8 hard fail, **do not** publish events/membership; the PASS receipt **must not** be created.

## 12.7 Practical sizing guidance (non-binding, recommended)

* **Shard sizing.** Size shard counts to keep `A_filtered` × (`key`+`weight`) within memory headroom; prefer many small shards to avoid per-shard spikes.
* **Caps.** Use `max_candidates_cap` to bound worst-case `A_filtered` in extreme markets without changing S3 order (cap applies as S3-rank prefix only).
* **Diagnostics.** Enable `log_all_candidates=true` in early runs for simpler validation and performance sizing; switch to reduced logging only with §9 counter-replay wired.

## 12.8 Telemetry hooks (tie-in to §14)

* Expose counters needed to validate the envelopes above: `events_written`, `gumbel_key_expected` vs `written`, selection size histogram, and shard-count invariance checks (hash of selected set per merchant). (See §14 for required metric names.) 

---

# 13. Orchestration & CLI contract **(Binding at interface; Informative for ops)**

**Purpose.** Define the **entrypoints**, **required arguments**, **modes**, **exit codes**, and **DAG wiring** to run S6 in production. JSON-Schema + the Dataset Dictionary remain the single authorities for shapes, IDs, and partition keys; downstream consumption is gated by **PASS receipts** (**no PASS → no read**). 

---

## 13.1 Required arguments (Binding)

* `--seed <u64>` — RNG seed for this run; **partitions all S6 RNG events/logs** (`…/seed={seed}/…`). 
* `--parameter-hash <hex64>` — exact **parameter scope**; must match S3/S5 partitions and S6 receipt location. (**S6 policy bytes are members of 𝓟; changing them flips this value.**) 
* `--run-id <string>` — logical run instance (ULID/ISO-ts acceptable). **Partitions logs only**; does **not** change selection outcomes. 
* `--input-root <path>` — root directory used with the **Dataset Dictionary path patterns** to locate **S3/S4/S5** inputs. 
* `--output-root <path>` — root directory where S6 writes events/logs and the S6 **PASS receipt**. 
* `--dictionary <path|ref>` — the **dataset_dictionary.layer1.1A.yaml** (or service handle) to resolve IDs → schemas, partitions, and paths. 
* `--schemas <path|ref>` — schema catalog(s) (**`schemas.1A.yaml`**, **`schemas.layer1.yaml`**, ingress catalog) used for validation. 
* `--policy-file <path>[,<path>…]` — S6 policy set; **must validate** against the registered `$ref`; **must be in 𝓟** (flips `parameter_hash` on byte change). 

**Notes (Binding):** the runner **MUST** fail pre-flight if any required argument is missing, if schemas/dictionary do not load, or if S6 policy fails schema validation. (See §4 for policy validation and §3 for input pre-flight.)

---

## 13.2 Switches & modes (Binding where stated)

* `--emit-membership-dataset` (default **false**) — if set, write the **convenience membership** table (authority remains the RNG events; **no order encoded**). 
* `--log-all-candidates` (default **true**) —

  * **true:** write one `rng_event.gumbel_key` **per considered candidate**.
  * **false:** write keys **only for selected**; validator **MUST** use **counter-replay** in **S3-rank** order to regenerate missing keys. (See §9.3.) 
* `--validate-only` — run the **validator** only: read existing S6 events/logs (and membership if present), perform **§§9.1–9.4**, and write the **S6 PASS receipt** in place.

  * **Binding semantics:** **requires** the S6 events/logs to already exist for `{seed, parameter_hash, run_id}`; **MUST NOT** create RNG events or membership; **USAGE** error if required inputs are absent. Receipt placement:
    `data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/(S6_VALIDATION.json,_passed.flag)`. 
* `--fail-on-degrade` — if set, treat deterministic empties (`NO_CANDIDATES`, `K_ZERO`, `ZERO_WEIGHT_DOMAIN`, `CAPPED_BY_MAX_CANDIDATES`) as **STRUCTURAL_FAIL** for the run instead of recording diagnostics only. (Names per §8.6.) 

**Operational (Informative):** You may add **`--workers N` / `--shards N --shard-id i`** to parallelise **by merchant** (S6 determinism requires **shard-count invariance** and deterministic merges; see §12.2). 

---

## 13.3 Exit codes & artefacts (Binding at interface)

**Symbolic exit codes** (exact numeric values listed in Appendix **B**):

* **`SUCCESS`** — All checks passed; S6 **PASS receipt** written under `…/s6/seed={seed}/parameter_hash={parameter_hash}/`. 
* **`STRUCTURAL_FAIL`** — Any §8.2/§8.3 failure (inputs, schema, policy, lineage) encountered. 
* **`RNG_ACCOUNTING_FAIL`** — Envelope/trace mismatch (S6 families). 
* **`RE_DERIVATION_FAIL`** — Unable to reconstruct membership from events (+ counter-replay when reduced logging). 
* **`SHORTFALL_NOTED`** — Non-error; ≥1 merchant had $|\text{Eligible}| < K_{\text{target}}$.

**Published artefacts (mandatory on SUCCESS):**

* `S6_VALIDATION.json` and `_passed.flag` (hash over other receipt files, ASCII-lexicographic concat). **Atomic publish** required. 

---

## 13.4 DAG wiring (Binding)

**Prerequisites (gates):**

1. **S3** candidate set present & schema-valid for `parameter_hash={…}`.
2. **S4** `ztp_final` present (one per resolved merchant) under `{seed, parameter_hash, run_id}`.
3. **S5** weights cache present for same `parameter_hash` **and S5 PASS receipt exists** (**no PASS → no read**). 

**Nodes & order (single run):**

1. **Draw keys** — iterate S3 domain (policy-filtered/capped) in **S3-rank** order; if `log_all_candidates=true`, write one `rng_event.gumbel_key` **per considered candidate**; if `false`, write keys only for **selected** candidates; append **one** `rng_trace_log` row **after each** event.
2. **Select** — compute keys, apply top-`K_target` rule with tie-breaks; (optional) write membership surface (authority note: re-derivable; no order). 
3. **Validate** — run §9 structural/content/RNG isolation & (re)derivation checks.
4. **Publish** — atomic publish of S6 receipt (and membership if enabled). **On FAIL:** publish nothing; return appropriate exit code (above). 

**Gates to S7:** S7 **MUST** verify S6 PASS for the same `{seed, parameter_hash}` before reading any S6 convenience surface, and must continue to respect **S5 PASS** when joining S5 outputs. **No PASS → no read.** 

## 13.5 ASCII overview *(Informative; non-authoritative)*

> This diagram is for **reader orientation only**. It does **not** add requirements. On any discrepancy, §§6–11 and §§13.1–13.4 (Binding) prevail.

```
[ENTER S6]
   │
   │ Load dictionary & schemas; resolve {seed, parameter_hash, run_id}
   │ Load S6 policy set (in 𝓟) and validate against $ref
   │—— fail → [STOP: E_POLICY_*]
   v
[Pre-flight (N1)]
   │  Inputs present & schema-valid:
   │    • S3 candidate_set (home=0; ranks total/contiguous)
   │    • S4 rng_event.ztp_final (one per merchant) → K_target
   │    • S5 ccy_country_weights_cache (same parameter_hash) + S5 PASS
   │  Lineage checks: path↔embed equality
   │—— fail → [STOP: E_UPSTREAM_GATE / E_SCHEMA_AUTHORITY / E_LINEAGE_PATH_MISMATCH]
   v
┌───────────────────────────────────────────────────────────────────────────────┐
│ For each merchant m (shard by merchant; deterministic merges)                │
│   │                                                                           │
│   │ [Build selection domain D_m]                                              │
│   │   D_m := (S3 foreign candidates) ∩ (S5 weight support for κ_m)            │
│   │   If max_candidates_cap>0 → keep first cap by S3 candidate_rank           │
│   │   Apply zero_weight_rule:                                                 │
│   │     - "exclude": eligible = {w>0}                                         │
│   │     - "include": considered may include w=0 (never eligible)              │
│   │   A_filtered := |considered| ; Eligible := {w>0}                           │
│   │                                                                           │
│   │ Any deterministic-empty reasons?                                          │
│   │—— A=0               → [EMIT EMPTY: NO_CANDIDATES] → next merchant         │
│   │—— K_target=0        → [EMIT EMPTY: K_ZERO] → next merchant                │
│   │—— Eligible=∅        → [EMIT EMPTY: ZERO_WEIGHT_DOMAIN] → next merchant    │
│   │ (If cap applied: record diagnostic CAPPED_BY_MAX_CANDIDATES)              │
│   v                                                                           │
│ [Draw keys (RNG events)]                                                      │
│   Iterate considered in S3 candidate_rank order                               │
│   For each candidate c:                                                       │
│     u ~ U(0,1) (open interval); G = -ln(-ln u); key = ln(w_c) - ln(-ln u)     │
│     log_all_candidates?                                                       │
│       • true  → write rng_event.gumbel_key for every considered c             │
│       • false → write rng_event.gumbel_key only for selected set (below)      │
│   (Append exactly one rng_trace_log row after each RNG event)                 │
│   │                                                                           │
│   v                                                                           │
│ [Select]                                                                      │
│   K_realized := min(K_target, |Eligible|)                                     │
│   Choose top-K_realized by key; ties → S3 candidate_rank, then country_iso    │
│   (No order is created; S3 remains sole authority for inter-country order)    │
│   │                                                                           │
│   v                                                                           │
│ [Optional write: membership dataset]                                          │
│   If emit_membership_dataset=true → write (merchant_id, country_iso)          │
│   (authority = RNG events; no order encoded; writer sort only)                │
└───────────────────────────────────────────────────────────────────────────────┘
   │
   v
[Validator & Receipt (N3)]
   │  Structural: schemas, partitions, PK/FK, path↔embed equality
   │  Content: subset law, cardinality, tie-break determinism, no-order encoding
   │  RNG isolation & accounting: only S6 families; trace totals reconcile
   │  Re-derivation:
   │    • if log_all_candidates=true  → recompute from logged keys + S3/S5
   │    • if log_all_candidates=false → counter-replay keys in S3-rank order
   │—— fail → [STOP: RE_DERIVATION_FAIL / RNG_ACCOUNTING_FAIL / STRUCTURAL_FAIL]
   v
[Atomic publish (N4)]
   │  Stage → single rename; write-once
   │  Emit S6_VALIDATION.json + _passed.flag under …/s6/seed={seed}/parameter_hash={H}/
   v
[STOP: S6 PASS — downstream MAY read (seed+parameter scope)]
   (S7/S8 must verify S6 PASS; S5 PASS still required where S5 is read)
```

---

# 14. Observability & metrics **(Binding for names/semantics)**

**Scope.** These metrics/log fields are **canonical**. Names, units, and dimensions here are **binding**; implementation may add more, but **MUST NOT** change these. Dimensions default to `{seed, parameter_hash, run_id}` (the lineage triplet used across RNG events/logs and receipts). The Dataset Dictionary and RNG core logs remain the authorities for paths/partitions.

---

## 14.1 Run-level counters & gauges (Binding)

Emit the following **per run** (dimensions: `{seed, parameter_hash, run_id}`):

**Volume & gating**

* `s6.run.merchants_total : counter` — merchants seen by S6 after §3 pre-flight.
* `s6.run.merchants_gated_in : counter` — merchants satisfying S1/S3/S4/S5 gates. 
* `s6.run.merchants_selected : counter` — merchants with `K_realized > 0`.
* `s6.run.merchants_empty : counter` — merchants with deterministic empty (sum of reason codes below).

**Domain & selection**

* `s6.run.A_filtered_sum : counter` — Σ over merchants of considered domain size after cap & `zero_weight_rule`.
* `s6.run.K_target_sum : counter` — Σ over merchants of `K_target` (from S4 `ztp_final`). 
* `s6.run.K_realized_sum : counter` — Σ over merchants of selected set size.

**Shortfall & reasons**

* `s6.run.shortfall_merchants : counter` — count where `|Eligible| < K_target` (selection proceeded with all `|Eligible|`).
* `s6.run.reason.NO_CANDIDATES : counter` — (A=0).
* `s6.run.reason.K_ZERO : counter` — `K_target=0`.
* `s6.run.reason.ZERO_WEIGHT_DOMAIN : counter` — eligible set empty after policy.
* `s6.run.reason.CAPPED_BY_MAX_CANDIDATES : counter` — diagnostic; cap truncated domain (non-error). *(Closed set—no other labels permitted.)*

**RNG coverage & accounting**

* `s6.run.events.gumbel_key.expected : counter` — if `log_all_candidates=true`, Σ `A_filtered`; else Σ `K_realized`.
* `s6.run.events.gumbel_key.written : counter` — number of `rng_event.gumbel_key` rows written.
* `s6.run.trace.events_total : counter` — final `events_total` from `rng_trace_log` for `(module="1A.foreign_country_selector", substream_label="gumbel_key")`.
* `s6.run.trace.blocks_total : counter` — final blocks total for the same key.
* `s6.run.trace.draws_total : counter` — final draws total for the same key. *(Trace fields mirror the core RNG schema; one trace append per event is required.)* 

**Policy & mode attestation**

* `s6.run.policy.log_all_candidates : gauge(bool)` — policy mode used.
* `s6.run.policy.max_candidates_cap : gauge(int)` — cap value used (0 = none).
* `s6.run.policy.zero_weight_rule : gauge(enum{"exclude","include"})`.
* `s6.run.policy.currency_overrides_count : counter` — number of currencies with per-currency overrides applied (names in validator report).

**Result shape**

* `s6.run.selection_size_histogram : histogram` — bucketed `K_realized` with **fixed buckets**: `b0=0`, `b1=1`, `b2=2`, `b3_5=3–5`, `b6_10=6–10`, `b11_plus=11+`. *(Bucket names fixed; implementations record bucket counts.)*

**Gate flags**

* `s6.run.rng_isolation_ok : gauge(bool)` — true iff only S6 families appear and totals reconcile. 
* `s6.run.re_derivation_ok : gauge(bool)` — true iff §9.3 re-derivation passes (logged or counter-replay mode).
* `s6.run.pass : gauge(bool)` — true iff the S6 receipt is written with a valid `_passed.flag`. (Downstream **must** still read the receipt and enforce gates.) 

---

## 14.2 Per-merchant diagnostics (Binding names; high-cardinality → log, not metrics)

Emit as **structured log rows** (JSONL) or a per-run detail file; do **not** export as cardinality-heavy metrics:

* `merchant_id:u64`, `A:int`, `A_filtered:int`, `K_target:int`, `K_realized:int`.
* `considered_expected_events:int`, `gumbel_key_written:int` (equals `considered_expected_events` only when `log_all_candidates=true`).
* `is_shortfall:bool` — true iff `|Eligible| < K_target`, `reason_code:enum{NO_CANDIDATES,K_ZERO,ZERO_WEIGHT_DOMAIN,CAPPED_BY_MAX_CANDIDATES,none}`.
* `ties_resolved:int` — count of key ties broken by S3 `candidate_rank` / ISO.
* `policy_cap_applied:bool`, `cap_value:int`.
* `zero_weight_considered:int` — count of considered candidates with `w==0` (under `"include"` mode).
* `rng.trace.delta.{events,blocks,draws}:int` — deltas observed in `rng_trace_log` for this merchant’s S6 substream.
  *(Order remains S3’s authority; membership surface (if enabled) encodes no order.)*

---

## 14.3 RNG audit metrics (Binding)

For each `(module="1A.foreign_country_selector", substream_label∈{"gumbel_key","stream_jump"})`, expose:

* `s6.rng.trace.events_total : counter`
* `s6.rng.trace.blocks_total : counter`
* `s6.rng.trace.draws_total : counter`
* `s6.rng.trace.append_rows : counter` — **MUST equal** `events_total` for `gumbel_key`.
  Values **MUST** be read from the **final row(s)** of `rng_trace_log` and agree with S6 event budgets (`gumbel_key` uses `blocks=1`, `draws="1"`).

---

## 14.4 Structured logs (Binding fields)

Every S6 structured log line (INFO/WARN/ERROR) **MUST** include:

* **Lineage:** `seed`, `parameter_hash`, `run_id`.
* **Context:** `stage:enum{"preflight","draw","select","write","validate","publish"}`, `module:"1A.foreign_country_selector"`.
* **Keys:** `merchant_id` *(omit on run-level messages)*, optional `country_iso` on candidate-level messages.
* **Reasoning:** `reason_code` (from the closed set above) when emitting empties or diagnostics.
* **Counters (when applicable):** `A`, `A_filtered`, `K_target`, `K_realized`, `gumbel_key_written`, `considered_expected_events`.
  These fields align with the RNG core and dataset contracts so operators can correlate logs with RNG trace and dictionary paths.

---

## 14.5 Golden fixtures *(Binding to ship & keep green; values themselves are non-normative)*

Maintain **three tiny, deterministic fixtures** (seeded) checked in CI; they **MUST** run under §12’s shard-invariance rules and assert §9 signals:

1. **Nominal selection:** `A=4, K_target=2`, non-zero S5 weights → `K_realized=2`; `log_all_candidates=true`; event coverage = `A_filtered`; re-derivation passes.
2. **Deterministic empty (no candidates):** `A=0` → reason `NO_CANDIDATES`; zero S6 events; PASS receipt still required.
3. **Zero-weight domain:** S5 weights zero on all foreigns after policy → reason `ZERO_WEIGHT_DOMAIN`; zero S6 events; PASS receipt required.

Each fixture **MUST** assert: schema/PK/FK, path↔embed equality, RNG isolation & accounting (trace rows = events), and **“no order encoding”** (order remains from S3 `candidate_rank`).

---

## 14.6 Source-of-truth reminders (Binding)

* **Order authority** remains S3 `candidate_rank`; egress (`outlet_catalogue`) carries **no** cross-country order—operators must not infer order from S6 row order. 
* **RNG receipts** rely on core logs: `rng_audit_log` (run-scoped) and `rng_trace_log` (cumulative per `(module,substream_label)`); one trace append **after each** event is mandatory. 
* **S5 PASS gate** remains in force when joining S5 outputs; S6 PASS is **seed+parameter-scoped** and must be verified by S7/S8 (`no PASS → no read`).

---

# 15. Security, licensing & compliance **(Binding)**

**Purpose.** Keep S6 within the platform’s **closed-world, contract-governed** posture; ensure all artefacts are **licensed**, **non-PII**, **immutable** under their lineage keys, and **auditable** end-to-end. JSON-Schema + the Dataset Dictionary remain the single authorities for shapes, paths, partitions, retention, and licence classes. 

---

## 15.1 Data provenance & closed-world stance

* S6 operates **only** on the sealed, version-pinned artefacts enumerated in §3 (S3 candidate set, S4 `ztp_final`, S5 weights) plus the S6 policy (§4). **No external enrichment or network reads** are permitted. 
* Provenance (owner, retention, licence, `schema_ref`) for inputs/outputs is declared in the **Dataset Dictionary**; S6 **MUST NOT** deviate from those entries.

## 15.2 Licensing (inputs, outputs, registry alignment)

* **Ingress examples (for transitive awareness):**
  `iso3166_canonical_2024` → **CC-BY-4.0**; `world_countries` → **ODbL-1.0** (ingress). These licences are already pinned in the Dictionary.
* **S6-produced/updated artefacts:**
  `rng_event.gumbel_key`, `rng_audit_log`, `rng_trace_log` are **Proprietary-Internal**, with declared **retention** and **pii=false** in the Dictionary; S6 **MUST** publish/update under those classes. 
* **Optional S6 membership dataset (if enabled):** before any consumer reads, a Dictionary entry **MUST** be registered with `pii:false`, an explicit **licence class** (default **Proprietary-Internal**), retention window, and a `$ref` schema; until then it is **not consumable**. 
* The Artefact Registry **MUST** carry licence metadata for S6 families/configs; storage policies (e.g., `compression_zstd_level3`) are referenced there and **MUST** be respected when pinned.

## 15.3 Privacy & PII posture

* All S6 inputs/outputs in scope are **`pii:false`** in the Dictionary; S6 **MUST NOT** introduce PII or fields enabling re-identification. 
* Structured logs and the S6 receipt **MUST NOT** contain row-level payloads beyond **codes and counts** (e.g., ISO codes, integer counters). (See §14 for required fields.) 

## 15.4 Access control, encryption, and secrets

* S6 inherits platform rails: **least-privilege IAM**, **KMS-backed encryption** at rest/in transit, and **audited access** to governed artefacts.
* S6 **MUST NOT** embed secrets in datasets/logs; use the platform secret store if credentials are required (none are required for S6’s normal operation). *(Policy, schemas, and dictionaries are public-internal artefacts.)* 

## 15.5 Retention & immutability

* Retention periods are governed by the Dictionary (e.g., **365 days** for S6 outputs/logs; ingress typically **1095 days**). S6 **MUST NOT** override retention.
* Event/log partitions are **content-addressed** by `{seed, parameter_hash, run_id}` and are **write-once**; S6 uses **atomic publish** and **never** mutates published partitions (see §10). 

## 15.6 Licence & compliance checks (validator duties)

The S6 validator (§9) **MUST additionally assert**:

* **Dictionary/licence presence:** every dataset ID read or written by S6 has a Dictionary entry with **non-empty `licence`** and `retention_days`. Missing ⇒ **FAIL**. 
* **Receipt summary:** `S6_VALIDATION.json` **MUST** include `licence_summary` listing `{dataset_id, licence, retention_days}` for all S6-touched artefacts (inputs: S3/S4/S5 IDs; outputs: S6 event/log families and membership if produced), plus `policy_digest` and `parameter_hash`. (Names align with §14 diagnostics.) 
* **Registry policy adherence:** when a writer policy is pinned in the Registry (codec/level/row-group), the produced files reflect that policy (else **FAIL**).

## 15.7 Redistribution & downstream use

* S6 event/log streams and any membership surface are **internal authorities** (Proprietary-Internal). Downstream systems **MUST NOT** republish them externally or change licence class without governance approval. 
* **Order authority** remains S3; S6 outputs **MUST NOT** be used to derive or imply inter-country order for publication or release. 

---

# 16. Change management, compatibility & rollback **(Binding)**

**Purpose.** Define how S6 evolves without breaking consumers; how changes interact with **`parameter_hash`** (𝓟), **`manifest_fingerprint`**, schemas, the Dataset Dictionary, and the Artefact Registry. JSON-Schema and the Dictionary remain the **sole** authorities for shapes/IDs/paths. 

---

## 16.1 Versioning model (SemVer) — interface vs lineage (Binding)

* **SemVer scope (this spec & its public interfaces).**

  * **MAJOR** — breaking changes to: dataset **IDs/paths/partitions**, schema shapes/required fields, **RNG event family** payloads or budgeting law, **tie-break rules**, **substream naming**, PASS-gate semantics, or adding **new required** CLI args.
  * **MINOR** — additive, backwards-compatible changes: optional fields/metrics, enabling the **optional membership** dataset, adding **diagnostic** fields, enabling **reduced logging** mode provided §9 supports counter-replay, registering a **writer policy** in the Registry.
* **Lineage keys are separate from SemVer.**

  * **`parameter_hash`** flips whenever **any** member of the governed set **𝓟** changes **bytes** (S0.2.2). S6 policy files are **required** 𝓟 members. 
  * **`manifest_fingerprint`** flips when **any opened artefact** (schemas/dictionary/ISO, etc.) or the **code commit** changes (S0.2.3). 

---

## 16.2 Compatibility window (Binding)

S6 v1.* is compatible with the following **v1.* baselines** (or as re-ratified):

* **Dictionary:** `dataset_dictionary.layer1.1A.yaml` v1.* (IDs/paths for `rng_event_ztp_final`, `rng_event_gumbel_key`, core RNG logs, S3/S5 datasets). 
* **Schemas:** `schemas.layer1.yaml` (RNG events/logs), `schemas.1A.yaml` (S3/S5 tables) v1.*.
* **S0 lineage law:** S0.2.* (`parameter_hash`, `manifest_fingerprint`, `run_id`). 
  If any of the above bump **MAJOR**, S6 **must** be re-ratified and its SemVer **MAJOR** incremented.

---

## 16.3 Event families & schema evolution (Binding)

* **RNG events.** `rng_event_gumbel_key` is the **authoritative** S6 event; its **schema_ref** and **partitioning** are fixed by the Dictionary. Backwards-compatible additions (optional fields) are **MINOR**; any required-field or budgeting change is **MAJOR**. 
* **Core logs.** `rng_audit_log`/`rng_trace_log` are shared; S6 **must not** alter their shapes—any change is Dictionary-governed (likely **MAJOR** at layer-scope). 
* **Membership dataset (optional).** Introducing it is **MINOR** if schema is additive and it carries **no order** (authority remains RNG events). Any future claim to authority would be **MAJOR**.

---

## 16.4 Policy changes & logging mode (Binding)

* **S6 policy is in 𝓟.** Changing policy bytes **MUST** flip `parameter_hash` (new parameter scope). 
* **`log_all_candidates` default.** Switching default **true→false** is **MINOR** if §9 counter-replay is implemented and enabled; reverting is also **MINOR**. (Per-currency overrides are disallowed; mode is global to keep validation uniform.)
* **`max_candidates_cap` changes.** Adjusting cap is **MINOR** (diagnostic `CAPPED_BY_MAX_CANDIDATES` required); removing the cap is **MINOR**.
* **`zero_weight_rule` changes.** `"exclude"↔"include"` toggles are **MINOR** (selection unchanged for positive weights; logging/expected-events differ and §9 covers both).

---

## 16.5 Registry & writer policy (Binding)

* **Writer policy.** If the Artefact Registry pins a writer policy (e.g., **ZSTD-3** and row-group sizes), S6 **MUST** use it; changing or pinning such policy is **MINOR** (value semantics unchanged; **byte-identity** may newly apply). 
* **Deprecated datasets.** The Registry keeps legacy **`country_set`** for compatibility but marks it **deprecated as order authority** (S3 owns order). S6 must **not** re-elevate it. 

---

## 16.6 Migration patterns (Binding)

When introducing **MINOR** changes:

1. **Shadow**: run S6 with new policy/schema in **shadow** (`--validate-only`) against existing events/logs; produce a PASS receipt without publishing new artefacts. 
2. **Dual-write (if needed)**: for new optional surfaces/fields, **dual-write** for at least one retention window; consumers switch by config.
3. **Canary**: enable for a small shard of merchants (seed-consistent) and confirm §14 telemetry and §9 PASS.
4. **Promote**: expand to 100% once green; remove shadow paths.

For **MAJOR** changes:

* **New IDs or schema_refs** in the Dictionary, or a new **module/substream** name; keep the prior family **readable** for ≥ retention window.

---

## 16.7 Deprecation policy (Binding)

* Announce in the Dictionary entry (`status: deprecated`, `notes`) and Registry (`notes:`) for at least one **retention** cycle before removal; provide the replacement ID/field.
* During deprecation, S6 **MUST** continue to write the legacy surface **or** produce a deterministic shim the validator can re-derive from the authoritative events.

---

## 16.8 Rollback (Binding)

* **What rollback means.** Revert to the **last-good** `{seed, parameter_hash}` and S6 **SemVer** that produced a PASS receipt; re-run with the earlier **policy bytes** and **code commit** to regenerate identical outputs (value-identical; **byte-identical** if writer policy pinned). 
* **Mechanics.**

  1. Restore previous S6 policy file(s) (𝓟 member); this restores the prior `parameter_hash`. 
  2. Check out the last-good code commit (participates in `manifest_fingerprint`). 
  3. Re-run S6 with the same `{seed, run_id}` (or a **new** `run_id`, since it does not affect modelling state). 
  4. Publish the S6 PASS receipt; downstream reads remain gated by PASS receipts (S5 and S6). 

---

## 16.9 Consumer impact matrix (Binding)

* **S3** — No impact unless S3 schema/IDs change (**MAJOR** there); S6 must continue to read `candidate_set` v1.*. 
* **S4** — `ztp_final` contract unchanged; any S4 MAJOR requires S6 re-ratification. 
* **S5** — S6 continues to enforce **S5 PASS** for the same `parameter_hash` (`no PASS → no read`). If S5 changes schema/IDs (**MAJOR**), S6 must re-ratify and bump **MAJOR**. 
* **S7/S8** — Downstream continue to rely on S6 **PASS** receipt and on S3 order authority; optional membership surface remains convenience only.

---

## 16.10 Golden fixtures & CI gates (Binding)

* Keep §14.5 golden fixtures **green** across changes; add new fixtures when introducing **MINOR** features (e.g., reduced logging mode) and **MAJOR** interfaces. The CI **must** assert: schema/PK/FK, path↔embed equality, RNG accounting (trace rows = events), re-derivation, and **no order encoding**. 

---

# 17. Acceptance checklist **(Binding)**

Use this **tick-box** list to sign off S6 before hand-off to implementation/ops. All items are **binding**.

---

## 17.1 Build-time (before any run)

* [ ] **Dictionary & schemas loaded** — `dataset_dictionary.layer1.1A.yaml` and schema catalogs (`schemas.1A.yaml`, `schemas.layer1.yaml`) resolve; IDs & `$ref`s for:
  `s3_candidate_set`, `rng_event_ztp_final`, `rng_event_gumbel_key`, core RNG logs (`rng_audit_log`, `rng_trace_log`), plus optional membership surface (if enabled).
* [ ] **Order authority pinned** — dictionary states **S3 `candidate_rank` is the sole inter-country order**; `outlet_catalogue` encodes **no** cross-country order. (Sanity: S6 must not encode order.)
* [ ] **RNG event families registered** — `rng_event.gumbel_key` exists with correct path/partitions `{seed,parameter_hash,run_id}` and `gated_by` = hurdle (`is_multi==true`). 
* [ ] **Core RNG logs registered** — `rng_audit_log`, `rng_trace_log` have correct partitions and schema anchors. 
* [ ] **S6 policy files validated** — JSON-Schema `$ref` passes; basenames **listed in S0.2.2 governed set 𝓟** so byte changes flip `parameter_hash`. (Cross-check 𝓟 discipline.) 
* [ ] **S5 contract in place** — S5 defines `ccy_country_weights_cache` with Σ rules and **parameter-scoped PASS receipt** (`S5_VALIDATION.json` + `_passed.flag`) required **before reads**.
* [ ] **Registry writer policy (if pinned)** — any codec/level/row-group requirements for S6 families present in Artefact Registry (for byte identity). 

---

## 17.2 Run-time (per run; fail-closed if any item fails)

**Pre-flight (§3):**

* [ ] **Inputs present & schema-valid** — S3 candidate set (home=0; ranks contiguous), S4 `ztp_final` (exactly one per merchant), S5 weights (same `parameter_hash`) with **S5 PASS receipt**; path↔embed equality holds.
* [ ] **Lineage triplet** — `{seed, parameter_hash, run_id}` resolved and used for S6 paths.

**Selection & RNG (§6/§11):**

* [ ] **Domain built correctly** — foreign = S3 candidates ∖ home, ∩ S5 weight support; optional cap is **S3-rank prefix only**. No out-of-domain countries admitted. 
* [ ] **Event coverage** — if `log_all_candidates=true`: **one** `rng_event.gumbel_key` **per considered candidate** (`A_filtered`). If false: keys only for selected, and validator will **counter-replay**. 
* [ ] **Trace duty** — **one** `rng_trace_log` append **after each** RNG event; totals reconcile per `(module, substream_label)`. 
* [ ] **Top-K rule** — select `min(K_target, |Eligible|)` by **`key`**; ties → S3 `candidate_rank`, then ISO A→Z. `K_target` read **only** from `rng_event_ztp_final`.
* [ ] **No order encoding** — S6 writes **no** cross-country order; membership surface (if emitted) is **authority-free** and re-derivable from events. 

**Validator (§9):**

* [ ] **Structural** — schemas/PK/FK pass; partition law & path↔embed equality hold for all S6 artefacts. 
* [ ] **Content** — subset law (selected ⊆ S3 foreign ∩ S5 support), cardinality, tie-break determinism, **no order encoding**. 
* [ ] **RNG isolation & accounting** — only S6 families appear; per-merchant/event totals match expectations; trace totals = Σ event budgets. 
* [ ] **Re-derivation** — Mode A: recompute from logged keys + S3/S5; Mode B: **counter-replay** missing keys in S3-rank order; published membership matches. 

**Gates:**

* [ ] **S5 PASS verified** (same `parameter_hash`) **before** any S5 reads. 

---

## 17.3 Publish (write-once; atomic promote; gate armed)

* [ ] **Receipt written** — under `…/s6/seed={seed}/parameter_hash={parameter_hash}/`:
  `S6_VALIDATION.json` + `_passed.flag` (SHA-256 over ASCII-lexicographic concat of other receipt files). **Atomic publish**; no partials. 
* [ ] **Events/logs partitions** — `rng_event.gumbel_key`, `rng_audit_log`, `rng_trace_log` under `{seed,parameter_hash,run_id}`; embedded lineage equals path tokens.
* [ ] **Optional membership surface** — if enabled, partitioned by `{seed,parameter_hash}`, **writer-sorted**, and **re-derivable** from RNG events; **no order** encoded.
* [ ] **Downstream gates armed** — S7/S8 must verify **S6 PASS** (seed+parameter) and continue to enforce **S5 PASS** for weight joins (**no PASS → no read**). 

---

# Appendix A. Glossary & symbols *(Normative)*

**A (raw foreign candidates).**
For a merchant $m$, **A** is the count of **foreign** rows in **S3 `s3_candidate_set`** (home has `candidate_rank=0` and is excluded). Ranks are total & contiguous per merchant.

**A_cap (rank-prefix cap).**
If policy `max_candidates_cap>0`, **A_cap = min(A, cap)** by taking the **first** `cap` foreign candidates in **S3 `candidate_rank`** order (no re-order).

**Considered set / $A_{\text{filtered}}$.**
The **considered** domain after policy filters: take the foreign S3 set, apply the cap, then apply `zero_weight_rule`.

* If `"exclude"` (default): drop candidates with `w==0`.
* If `"include"`: keep `w==0` in the considered set (they can be **logged** but never selected).
  Define **$A_{\text{filtered}}$** as the **size of the considered** set.

**Eligible set / $|\text{Eligible}|$.**
Subset of the **considered** set with **strictly positive** S5 weight (**$w>0$**). S6 **selects only** from this set. Its size $|\text{Eligible}|$ may be < $A_{\text{filtered}}$ when `"include"` is used.

**$K_{\text{target}}$.**
Per-merchant target cardinality fixed by **S4 `rng_event.ztp_final`** (logs-only authority; exactly one final per resolved merchant).

**$K_{\text{realized}}$.**
The realized selection size:
$$
K_{\text{realized}}=\min\big(K_{\text{target}},\ |\text{Eligible}|\big).
$$
If the eligible set is smaller than $K_{\text{target}}$ (shortfall), S6 selects **all** eligible countries.

**Gumbel `key` (a.k.a. score $S$).**
S6 scores each **considered** candidate $c$ (with S5 weight $w_c$) using:
$$
S_c = \ln(w_c) + G_c,\qquad G_c = -\ln\big(-\ln u_c\big),\quad u_c\in(0,1).
$$

* **Uniforms:** $u_c$ come from the layer’s **strict-open** (U(0,1)) mapping (never 0 or 1).
* **Zero weights:** if `zero_weight_rule="include"`, treat $\ln(0)=-\infty$ (loggable, **not** selectable).
  *Event payload note (binding cross-ref to §§5.1/6.3): when `weight==0`, the event **MUST** encode `key: null` (never $\pm\infty$); such rows are diagnostic only and cannot be selected.*
* **Tie-breaks (total order):** higher $S$ first; exact tie → lower **S3 `candidate_rank`**; then `country_iso` A→Z.

**ULP (Unit in the Last Place).**
For IEEE-754 **binary64**, the **ULP** at a value $x$ is the difference between $x$ and the next representable binary64 number. ULPs matter only for **comparisons** (e.g., equality of $S$ in binary64); they **do not** change the scoring formula or selection rule.

**RNG envelope *counters* and *budgets*.**
Every RNG event row carries a **lineage envelope**:

* `before`, `after` — **128-bit** Philox counters (as decimal strings) **before** and **after** the event.
* `blocks` — unsigned 128-bit delta: `u128(after) − u128(before)`.
* `draws` — **decimal uint128 string** equal to the **actual number of $U(0,1)$** draws consumed by the event’s sampler(s) (independent of `blocks`).
* **Single-uniform family (`gumbel_key`):** `blocks=1`, `draws="1"`.
* **Non-consuming markers (if any):** `before==after`, `blocks=0`, `draws="0"`.

**RNG trace *budget totals*.**
For each `(module="1A.foreign_country_selector", substream_label∈{"gumbel_key","stream_jump"})`, S6 appends **exactly one** cumulative row to **`rng_trace_log`** **after each event**; validators check:

* `events_total` increments by 1 per event append,
* `draws_total = Σ parse_u128(draws)`,
* `blocks_total = Σ blocks` (saturating),
  and that **only S6 families** appear (isolation).

**Lineage triplet.**
`{seed, parameter_hash, run_id}` — required partition keys for S6 RNG events/logs; embeddings (when present) **must byte-equal** path tokens.

**Receipts & gates (reminder).**

* **S5 PASS (parameter-scoped):** `S5_VALIDATION.json` + `_passed.flag` **must exist** before S6 reads S5.
* **S6 PASS (seed+parameter-scoped):** `S6_VALIDATION.json` + `_passed.flag` gate downstream reads of any S6 convenience surface.

---

# Appendix B. Enumerations & reference tables *(Normative)*

## B.1 Dataset IDs and schema anchors (read/write set)

| ID (Dictionary)                      | Type         | Partitions                     | Schema `$ref`                                            | Notes                                                                                                                                                            |
|--------------------------------------|--------------|--------------------------------|----------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `s3_candidate_set`                   | dataset      | `parameter_hash`               | `schemas.1A.yaml#/s3/candidate_set`                      | Order & admissible set **A** (home `candidate_rank=0`, ranks total & contiguous).                                                                                |
| `rng_event_ztp_final`                | rng_event    | `seed, parameter_hash, run_id` | `schemas.layer1.yaml#/rng/events/ztp_final`              | S4 **fixes `K_target`**; exactly one per resolved merchant. **Consumed by S6.**                                                                                  |
| `rng_event_gumbel_key`               | rng_event    | `seed, parameter_hash, run_id` | `schemas.layer1.yaml#/rng/events/gumbel_key`             | **Logging mode:** if `log_all_candidates=true`, one per **considered** candidate; if `false`, keys only for **selected** candidates (validator counter-replays). |
| `rng_audit_log`                      | rng core log | `seed, parameter_hash, run_id` | `schemas.layer1.yaml#/rng/core/rng_audit_log`            | Run-scoped audit; emitted before events.                                                                                                                         |
| `rng_trace_log`                      | rng core log | `seed, parameter_hash, run_id` | `schemas.layer1.yaml#/rng/core/rng_trace_log`            | Cumulative per `(module, substream_label)`; **one append after each event**.                                                                                     |
| `ccy_country_weights_cache`          | dataset      | `parameter_hash`               | `schemas.1A.yaml#/prep/ccy_country_weights_cache`        | S5 currency→country **weights**; **S5 PASS** required before S6 reads (**no PASS → no read**).                                                                   |
| `merchant_currency` *(optional)*     | dataset      | `parameter_hash`               | `schemas.1A.yaml#/prep/merchant_currency`                | Deterministic κₘ cache for S5/S6 joins.                                                                                                                          |
| `rng_event_dirichlet_gamma_vector`   | rng_event    | `seed, parameter_hash, run_id` | `schemas.layer1.yaml#/rng/events/dirichlet_gamma_vector` | S7 allocator (downstream of S6).                                                                                                                                 |
| `rng_event_stream_jump` *(optional)* | rng_event    | `seed, parameter_hash, run_id` | `schemas.layer1.yaml#/rng/events/stream_jump`            | Explicit Philox stream/substream jump records.                                                                                                                   |
| `country_set` *(legacy/compat)*      | dataset      | `seed, parameter_hash`         | `schemas.1A.yaml#/alloc/country_set`                     | **Deprecated as order authority;** S3 remains sole order source.                                                                                                 |

> **Authority reminder:** JSON-Schema + Dataset Dictionary govern IDs, shapes, and paths; S6 **must not** encode inter-country order—consumers **must** join S3 `candidate_rank`. 

---

## B.2 RNG family names and substream conventions

* **Module name (S6):** `module="1A.foreign_country_selector"` *(normative)*.
* **Substream labels (S6):** `substream_label ∈ {"gumbel_key","stream_jump"}` *(if `stream_jump` is registered)*. 
* **Families touched by S6:**

  * **Produced:** `rng_event.gumbel_key` (S6). 
  * **Updated core logs:** `rng_audit_log`, `rng_trace_log` (append per event). 
  * **Optional:** `rng_event.stream_jump` (if present in the registry). 
* **Related upstream/downstream families (read or next state):**
  `rng_event.ztp_final` (S4) → **read by S6**; `rng_event.dirichlet_gamma_vector` (S7) → **downstream**.

---

## B.3 Reason codes *(closed vocabulary; diagnostics only)*

These codes annotate **deterministic empties or cap diagnostics** (they do **not** authorise re-weighting or re-ordering):

* `NO_CANDIDATES` — S3 exposes only home (`A=0`).
* `K_ZERO` — S4 fixed `K_target=0`.
* `ZERO_WEIGHT_DOMAIN` — after policy, no candidate with `w>0` remains.
* `CAPPED_BY_MAX_CANDIDATES` — domain truncated by S3-rank cap (non-error).

*(Names align with §8; downstream still uses S3 order and S5 weights.)*

---

## B.4 Error codes *(hard FAIL; per-merchant unless noted)*

S6 **fails closed** with these canonical codes; map to S0 failure classes in ops dashboards.

* `E_UPSTREAM_GATE` — Missing/malformed required inputs or missing S5 PASS.
* `E_RNG_ENVELOPE` — Envelope/counter/trace breach (missing `before/after/blocks/draws`, no trace append, or cross-family writes).
* `E_LINEAGE_PATH_MISMATCH` — Embedded `{seed, parameter_hash, run_id}` not equal to path tokens.
* `E_SCHEMA_AUTHORITY` — Any S6 artefact fails its registered JSON-Schema.
* `E_NUMERIC_POLICY` — Violation of S0.8 numeric environment on decision paths.
* `E_EVENT_COVERAGE` — Missing/inconsistent `gumbel_key` coverage vs **considered** domain (when `log_all_candidates=true`).
* `E_DUP_PK` — Duplicate `(merchant_id, country_iso)` in membership surface (if emitted).
* `E_ORDER_INJECTION` — Any S6 output encodes or implies inter-country order.
* `E_POLICY_SCHEMA` / `E_POLICY_DOMAIN` — S6 policy fails JSON-Schema or value domains.
* `E_POLICY_CONFLICT` — Deterministic override resolution yields inconsistent state.
* `E_IO_ATOMICS` — Non-atomic publish, short write, or mismatched writer policy.

*(Exit codes for the runner are listed in §13.3 and are distinct from these `E_*` codes.)*

---

## B.5 Path patterns (authoritative excerpts)

* `logs/layer1/1A/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` → `schemas.layer1.yaml#/rng/events/gumbel_key`. 
* `logs/layer1/1A/rng/events/ztp_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` → `schemas.layer1.yaml#/rng/events/ztp_final`. 
* `logs/layer1/1A/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl` → `schemas.layer1.yaml#/rng/core/rng_audit_log`. 
* `logs/layer1/1A/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl` → `schemas.layer1.yaml#/rng/core/rng_trace_log`. 
* `data/layer1/1A/ccy_country_weights_cache/parameter_hash={parameter_hash}/` → `schemas.1A.yaml#/prep/ccy_country_weights_cache`. 
* *(Compat)* `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/` → `schemas.1A.yaml#/alloc/country_set` (**deprecated as order authority**). 

---

## B.6 Registry tie-ins (writer policy / compression)

* **Compression policy (when pinned):** `compression_zstd_level3` (ZSTD-3) in the Artefact Registry; when present, producers **MUST** adhere for byte-identity. 
* **Storage path pattern (egress reference):** `storage_path_pattern` documents fingerprint-scoped egress (e.g., `outlet_catalogue`). *(S6 writes seed+parameter-scoped RNG streams and receipts.)* 

---

## B.7 Cross-refs (normative)

* **S5 PASS receipt** location & semantics (parameter-scoped): `S5_VALIDATION.json` + `_passed.flag` under the weights cache partition. **Required before S6 reads.** 
* **Layer validation bundle** (fingerprint-scoped) for egress consumption remains unchanged. 

---

# Appendix C. Worked example *(Non-normative)*

> Tiny, concrete walk-through. Numbers are illustrative and computed in **binary64**; this appendix **does not** add requirements. Binding rules live in §§6–11 & §13.

## Setup (single merchant $m$)

* **S3 candidate set (home excluded from selection):**
  `home=GB (candidate_rank=0)`, foreigns:

  1. **FR** (rank 1) · 2) **DE** (rank 2) · 3) **ES** (rank 3) · 4) **IT** (rank 4) ⇒ **A=4**
* **S4 target:** `K_target = 2`.
* **S5 weights (raw, before subset renorm):** FR 0.25, DE 0.15, ES 0.10, IT 0.05 (sum over these four = **0.55**).
  Ephemeral **subset renormalisation** (foreign-only):
  FR 0.454545…, DE 0.272727…, ES 0.181818…, IT 0.090909… (sum = 1.0).
* **Policy:** `log_all_candidates=true`, `max_candidates_cap=0`, `zero_weight_rule="exclude"`.

## Gumbel keys & key values

For each **considered** candidate $c$: draw $u_c\in(0,1)$, compute
$G_c=-\ln(-\ln u_c)$, $S_c=\ln(w_c)+G_c$ (binary64). Stable iteration = **S3 rank**.

| S3 rank | ISO | $w_{\text{raw}}$ | $w_{\text{norm}}$ |  $u$ |       $G$ | $\ln w_{\text{norm}}$ |           $S$ | Selected? |
|--------:|:---:|-----------------:|------------------:|-----:|----------:|----------------------:|--------------:|:---------:|
|       1 | FR  |             0.25 |          0.454545 | 0.22 | −0.414840 |             −0.788457 |     −1.203297 |           |
|       2 | DE  |             0.15 |          0.272727 | 0.51 |  0.395498 |             −1.299283 |     −0.903785 |   **✓**   |
|       3 | ES  |             0.10 |          0.181818 | 0.73 |  1.156101 |             −1.704748 | **−0.548647** |   **✓**   |
|       4 | IT  |             0.05 |          0.090909 | 0.04 | −1.169032 |             −2.397895 |     −3.566927 |           |

**Result:** sort by $S$ (desc) → **ES**, **DE**, FR, IT.
Since `K_target=2`, **$K_{\text{realized}}=\min(2,4)=2$** → selected set = **{ES, DE}**.
*(No tie encountered; if (S) ties in binary64, break by **S3 `candidate_rank`**, then ISO A→Z.)*

## RNG evidence (events & trace)

* With `log_all_candidates=true`, **one** `rng_event.gumbel_key` per **considered** candidate (here 4 events), appended in **S3-rank order**: FR → DE → ES → IT.
* **Budgets:** each event consumes **`blocks=1`, `draws="1"`** (single-uniform family).
* **Trace:** exactly **4** `rng_trace_log` appends; final totals for `(module="1A.foreign_country_selector", substream_label="gumbel_key")` are:
  `events_total=4`, `blocks_total=4`, `draws_total=4`.
* Validator **re-derives** the membership from logged keys + S3/S5 and matches **{ES, DE}**.

## Persisted order (authority separation)

* If a **membership** dataset is emitted, it contains **unordered** pairs `(merchant_id, country_iso)` (writer-sorted only).
* Any **display/order** of the selected set **MUST** be obtained by **joining S3** and using `candidate_rank` (here the projected order would appear as **DE (rank 2), ES (rank 3)**). **S6 does not encode inter-country order.**

---