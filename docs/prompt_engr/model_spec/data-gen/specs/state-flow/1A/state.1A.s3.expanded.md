# S3.1 — Inputs & canonical materialisation (deterministic, no RNG)

## 1) Purpose & scope (normative)

This sub-state **binds** the authoritative, deterministic inputs the S3 gate needs for each merchant $m$ that exited **S2** with an **accepted multi-site** outlet count. It **reads**:

* the ingress merchant identity/features,
* the **parameter-scoped** eligibility flags materialised in **S0**, and
* the **accepted count $N_m$** from **S2**,

and produces an **in-memory** bundle for **S3.2**. **No datasets are written** and **no RNG is consumed** in S3.1.

---

## 2) Authoritative contracts (what we read, exactly)

### 2.1 Ingress merchant record (canonical)

Read the following columns from the **ingress** table referenced by `schemas.ingress.layer1.yaml#/merchant_ids`:

* `merchant_id: int64` (PK)
* `mcc: int32`
* `channel: string ∈ {"card_present","card_not_present"}`
* `home_country_iso: ISO-3166-1 alpha-2` (FK to canonical ISO)

> **Notes.** Channel values are the two enumerants above (not “CP/CNP” strings). ISO must be uppercase `[A–Z]{2}` and FK-valid against the canonical ISO list defined in the ingress schema.

### 2.2 Eligibility flags (parameter-scoped, produced in S0)

Read **exactly one** row per merchant from:

```
data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/
  schema_ref: schemas.1A.yaml#/prep/crossborder_eligibility_flags
  partition_keys: ["parameter_hash"]
```

**Required columns (governed types):**

* `merchant_id: int64`
* `is_eligible: boolean`      // maps to math symbol eₘ
* `eligibility_rule_id: string` (non-null)
* `eligibility_hash: string` (hex; non-null)
* `reason_code: string|null` with **enum** when non-null:
  `{"mcc_blocked","cnp_blocked","home_iso_blocked"}`
* `reason_text: string|null` (optional free-text complement)

This table is the **single source of truth** for the S3 gate; it is **parameter-scoped** (filtered by the **current** `{parameter_hash}`).

### 2.3 Accepted outlet count from S2 (multi-site only)

S2 emits **exactly one** RNG event row per merchant carrying the accepted NB draw:

```
logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/...
  schema_ref: schemas.layer1.yaml#/rng/events/nb_final
```

* **Presence requirement:** exactly one row for `(merchant_id, seed, parameter_hash, run_id)`.
* **Authoritative value of N:** read `nb_final.value:int64` from that row.

> Reading the event payload does **not** consume RNG; it’s a deterministic log read.

### 2.4 Lineage keys (carried through)

Carry these untouched for downstream joins and provenance:

* `seed: int64` (RNG family key)
* `run_id: string/uuid` (run-scoped log partition)
* `parameter_hash: string` (parameter-set scope; partitions flags/caches)
* `manifest_fingerprint: string` (parameter-set/artefact fingerprint; embedded later in persisted outputs)

---

## 3) Preconditions (MUST hold before S3.1 binds)

1. **Multi-site only.** Merchant must have `is_multi=1` from **S1** **and** an accepted S2 draw:
   `count_rows(nb_final where merchant_id=m and seed and parameter_hash and run_id) == 1`.
   Otherwise abort `E_NOT_MULTISITE_OR_MISSING_S2`.
2. **Ingress schema conformance.** The projected columns conform to `schemas.ingress.layer1.yaml#/merchant_ids` (reject unknown enumerants; enforce ISO pattern + FK).
3. **Flags partition ready.** A **single** row for `(parameter_hash, merchant_id)` exists in `crossborder_eligibility_flags`. S3 reads **after** S0 has committed the partition.

---

## 4) Determinism & invariants

* **No-RNG invariant.** S3.1 consumes **no** RNG streams; it is a pure function of ingress + parameter-scoped flags + S2 acceptance.
* **I-S3.1-Uniq.** Exactly **one** flags row exists per `(parameter_hash, merchant_id)`. Missing/duplicate rows are structural errors.
* **I-S3.1-Schema.** `is_eligible` **boolean**; `eligibility_rule_id`/`eligibility_hash` **non-null**; when non-null, `reason_code` ∈ the governed enum; `reason_text` optional.
* **I-S3.1-ISO-FK (precondition for later S6 write).** `home_country_iso` is FK-valid against the canonical ISO table.

---

## 5) Canonical materialisation procedure (normative)

**Inputs (to this sub-state):**
`merchant_id, mcc, channel, home_country_iso` (ingress); `seed, run_id, parameter_hash, manifest_fingerprint` (lineage).

**Output (in-memory for S3.2):**

```
S3Inputs = {
  merchant_id,
  home_country_iso,
  mcc, channel,
  N,  # accepted in S2 from nb_final.value
  flags: {
    is_eligible,              # boolean
    eligibility_rule_id,      # string
    eligibility_hash,         # hex string
    reason_code,              # enum or null
    reason_text               # optional
  },
  seed, run_id,
  parameter_hash,
  manifest_fingerprint
}
```

**Algorithm (reference pseudocode, language-agnostic):**

```pseudo
function s3_1_bind_inputs(m: MerchantID,
                          seed: int64,
                          parameter_hash: hex64,
                          run_id: uuid) -> S3Inputs:
    # 1) Verify S2 acceptance (multi-site) and read N
    rowN := select value
            from logs.rng.events.nb_final
            where merchant_id = m
              and seed = seed
              and parameter_hash = parameter_hash
              and run_id = run_id
    if count(rowN) != 1:
        abort E_NOT_MULTISITE_OR_MISSING_S2(m)
    N := rowN.value
    assert N >= 2                                    # multi-site

    # 2) Read ingress projection (strict schema)
    (mid, mcc, channel, home_iso) :=
        select merchant_id, mcc, channel, home_country_iso
        from ingress.merchant_ids
        where merchant_id = m
    assert channel in {"card_present","card_not_present"}
    assert iso2_regex_match(home_iso) and fk_iso2_exists(home_iso)

    # 3) Lookup the parameter-scoped eligibility row
    flags := select merchant_id,
                     is_eligible,
                     eligibility_rule_id,
                     eligibility_hash,
                     reason_code,
                     reason_text
             from data.layer1.1A.crossborder_eligibility_flags
             where parameter_hash = parameter_hash
               and merchant_id = m
    if count(flags) == 0: abort E_FLAGS_MISSING(m)
    if count(flags) >  1: abort E_FLAGS_DUPLICATE(m)
    f := flags[0]
    assert typeof(f.is_eligible) == BOOLEAN
    assert f.eligibility_rule_id is not NULL
    assert f.eligibility_hash   is not NULL
    assert f.reason_code is NULL
           or f.reason_code in {"mcc_blocked","cnp_blocked","home_iso_blocked"}

    # 4) Bind and return the in-memory bundle (no writes here)
    return {
      merchant_id: mid,
      home_country_iso: home_iso,
      mcc: mcc,
      channel: channel,
      N: N,
      flags: {
        is_eligible: f.is_eligible,
        eligibility_rule_id: f.eligibility_rule_id,
        eligibility_hash: f.eligibility_hash,
        reason_code: f.reason_code,
        reason_text: f.reason_text
      },
      seed: seed,
      run_id: run_id,
      parameter_hash: parameter_hash,
      manifest_fingerprint: current_manifest_fingerprint()
    }
```

**Joins/keys (MUST use):**

* S2 acceptance & value of `N`: equality on `(merchant_id, seed, parameter_hash, run_id)` into `logs/rng/events/nb_final`.
* Flags lookup: equality on `(parameter_hash, merchant_id)` into `crossborder_eligibility_flags`.

---

## 6) Failure taxonomy (detected in S3.1; all are **abort**)

* `E_NOT_MULTISITE_OR_MISSING_S2(m)` — Missing/duplicate `nb_final` acceptance or `N < 2`.
* `E_FLAGS_MISSING(m)` — No row in `crossborder_eligibility_flags/parameter_hash={parameter_hash}` for `merchant_id=m`.
* `E_FLAGS_DUPLICATE(m)` — >1 row for `(parameter_hash, merchant_id)`.
* `E_INGRESS_SCHEMA(channel|home_country_iso)` — Channel not in enum or ISO not FK-valid per ingress schema.

Each abort MUST surface a minimal diagnostic payload including the probed keys and the dictionary pointer (dataset id + `schema_ref`).

---

## 7) Observability (structured log; optional, non-authoritative)

Emit one **system log** record per merchant to assist incident response (validator does **not** rely on this):

```
logs/system/eligibility_gate.v1.jsonl
{
  event: "s3_inputs_bound",
  merchant_id, seed, run_id, parameter_hash, manifest_fingerprint,
  ingress: { mcc, channel, home_country_iso },
  flags: {
    is_eligible, eligibility_rule_id, eligibility_hash,
    reason_code, reason_text
  },
  N_from_S2: N
}
```

---

## 8) Conformance tests (suite skeleton)

1. **Happy path.** Ingress valid; flags row present with
   `{is_eligible=true, eligibility_rule_id="default_v1", eligibility_hash="…", reason_code=null}`; exactly one `nb_final` with `value≥2` → **bind succeeds** and returns the bundle.
2. **Missing flags.** Remove the flags row under current `{parameter_hash}` → **abort `E_FLAGS_MISSING`**.
3. **Duplicate flags.** Duplicate the row (same `merchant_id`, same `parameter_hash`) → **abort `E_FLAGS_DUPLICATE`**.
4. **Wrong channel literal.** Set `channel="CP"` in ingress → **abort `E_INGRESS_SCHEMA(channel)`**.
5. **Single-site merchant.** Remove `nb_final` (or set S1 `is_multi=0`) → **abort `E_NOT_MULTISITE_OR_MISSING_S2`**.
6. **ISO FK failure.** Set `home_country_iso="UK"` (not ISO-2) → **abort `E_INGRESS_SCHEMA(home_country_iso)`**.

---

## 9) Complexity & performance

O(1) lookups per merchant: one key read in ingress, one partition-filtered point lookup in `crossborder_eligibility_flags`, and a single-row lookup in `nb_final`. All I/O is **parameter-scoped** or **run-scoped** via partitions, so lookups are index-friendly.

---

## 10) Output to S3.2 (state boundary)

S3.1 produces an **in-memory** structure (no persistence):

```
{
  merchant_id,
  home_country_iso,
  mcc, channel,
  N,   # accepted in S2 (nb_final.value)
  flags: { is_eligible, eligibility_rule_id, eligibility_hash,
           reason_code, reason_text },
  seed, run_id,
  parameter_hash,
  manifest_fingerprint
}
```

**S3.2** consumes this bundle; it reads `eₘ ← flags.is_eligible` and applies the branch policy (eligible → **S4**; ineligible → **S6** per single-writer doctrine).

---

# S3.2 — Eligibility function & deterministic branch decision (no RNG)

## 1) Purpose & scope (normative)

Decide the branch for each **multi-site** merchant $m$ using the **parameter-scoped** eligibility flags:

* **eligible** → proceed to **S4**;
* **domestic-only** → route to **S6** with $K^*=0$ so **S6** (single writer) persists `country_set` with **home @ rank 0**, then proceed to S7.
  S3.2 is **purely deterministic** and **writes nothing**.

**Predecessor:** S3.1 produced:

```
S3Inputs = {
  merchant_id, home_country_iso, mcc, channel, N,
  flags: {
    is_eligible,               # boolean
    eligibility_rule_id,       # string
    eligibility_hash,          # hex
    reason_code,               # enum|null
    reason_text                # optional
  },
  seed, run_id,
  parameter_hash, manifest_fingerprint
}
```



---

## 2) Formal definition (policy set and indicator)

Let $\mathcal{I}$ be ISO-3166-1 alpha-2 (uppercase). The governed rule family is:

$$
\mathcal{E}\subseteq \underbrace{\mathbb{N}}_{\text{MCC}}\times
\underbrace{\{\texttt{card_present},\texttt{card_not_present}\}}_{\text{channel}}\times
\underbrace{\mathcal{I}}_{\text{home ISO-2}},
$$

compiled in S0 into `crossborder_eligibility_flags` under the current `{parameter_hash}`. The indicator

$$
\boxed{\,e_m=\mathbf{1}\{(\texttt{mcc}_m,\texttt{channel}_m,\texttt{home_country_iso}_m)\in\mathcal{E}\}\,}
$$

is **read**, not recomputed: `e_m ≡ flags.is_eligible`.

---

## 3) Inputs (authoritative sources)

* **Flags (parameter-scoped):** `crossborder_eligibility_flags/parameter_hash={parameter_hash}` with exactly one row per merchant; governed types: `is_eligible:boolean`, `eligibility_rule_id:string`, `eligibility_hash:string`, `reason_code ∈ {"mcc_blocked","cnp_blocked","home_iso_blocked"}|null`, `reason_text:string|null`.
* **Ingress fields (validated in S3.1):** `mcc:int32`, `channel ∈ {"card_present","card_not_present"}`, `home_country_iso: ISO2`.
* **S2 acceptance (precondition):** exactly one `nb_final` under `(merchant_id, seed, parameter_hash, run_id)`; `N ≥ 2`.

---

## 4) Preconditions (MUST hold)

1. Multi-site branch only (`is_multi=1` in S1) **and** accepted S2 draw (`nb_final` present).
2. Unique flags row under active `{parameter_hash}`.
3. Flags schema satisfied (types, non-nulls, enum).
4. Ingress enum/FK already satisfied by S3.1.

---

## 5) Branch function (normative)

$$
\boxed{\ \text{if } e_m=1 \Rightarrow \textsf{eligible};\ \text{else } \textsf{domestic_only}\ }
$$

* **Eligible (`e=1`):** proceed to **S4** for ZTP on $K\ge1$; later S6 selects/ordains foreign ISOs; `country_set` persists order with home at rank 0.
* **Domestic-only (`e=0`):** **route to S6** with $K^*=0$ so S6 writes `country_set` with only the home ISO at `rank=0` (single-writer doctrine), then proceed to S7. This replaces older “skip S4–S6 → S7” wording to avoid orphaning the home row.

---

## 6) Determinism & validator hooks

* **No RNG:** S3.2 consumes **no** RNG; output is a pure function of `(ingress, flags)` under `{parameter_hash}`.
* **Branch coherence (checked in S9):**

  * If `e=0` ⇒ **no** S4–S6 RNG events (`poisson_component(context="ztp")`, `ztp_*`, `gumbel_key`, `dirichlet_gamma_vector`).
  * If `e=1` ⇒ evidence of entering S4 (presence of `poisson_component(context="ztp")` **or** `ztp_retry_exhausted`).
    Joins: `(merchant_id, seed, parameter_hash, run_id)`.

---

## 7) Procedure (reference pseudocode)

```pseudo
function s3_2_decide_gate(inp: S3Inputs) -> S3Branch:
    assert typeof(inp.flags.is_eligible) == BOOLEAN
    assert inp.flags.eligibility_rule_id != NULL
    assert inp.flags.eligibility_hash    != NULL
    assert inp.flags.reason_code == NULL
           or inp.flags.reason_code in {"mcc_blocked","cnp_blocked","home_iso_blocked"}

    e := inp.flags.is_eligible

    if e == true:
        next_state := "S4"
        K := null          # unknown until S4 (JSON null)
        C := [inp.home_country_iso]  # rank 0 reserved
    else:
        next_state := "S6" # single-writer persists country_set (home only)
        K := 0
        C := [inp.home_country_iso]

    return {
      merchant_id: inp.merchant_id,
      e: e,
      eligibility_rule_id: inp.flags.eligibility_rule_id,
      eligibility_hash:    inp.flags.eligibility_hash,
      reason_code: inp.flags.reason_code,
      reason_text: inp.flags.reason_text,
      home_country_iso: inp.home_country_iso,
      mcc: inp.mcc, channel: inp.channel,
      N: inp.N,
      C: C, K: K,
      next_state: next_state,
      seed: inp.seed, run_id: inp.run_id,
      parameter_hash: inp.parameter_hash,
      manifest_fingerprint: inp.manifest_fingerprint
    }
```

Notes: JSON-native `null` is used for “unknown” $K$ to avoid non-serialisable sentinels; `C` is ordered, dup-free, with rank 0 = home.

---

## 8) Failure taxonomy (at/around S3.2)

* `E_NOT_MULTISITE_OR_MISSING_S2` — precondition fail (no `nb_final` / not multi-site).
* `E_FLAGS_MISSING` / `E_FLAGS_DUPLICATE` / `E_FLAGS_SCHEMA` — flags issues under active `{parameter_hash}`.
* `F_EL_BRANCH_INCONSISTENT` (validator): S4–S6 RNG present for `e=0`, or no S4 evidence for `e=1`.

---

## 9) Outputs (to S3.3)

S3.2 returns an **in-memory** `S3Branch`:

```
{
  merchant_id, e,
  eligibility_rule_id, eligibility_hash,
  reason_code, reason_text,
  home_country_iso, mcc, channel,
  N, C, K, next_state,
  seed, run_id, parameter_hash, manifest_fingerprint
}
```

S3.3 initialises/maintains the **country-set container** `C` (rank 0 = home). For `e=0`, **S6** will persist `country_set` with only rank 0; for `e=1`, S4 will determine $K\ge1$ and S6 will extend/persist order.

---

# S3.3 — Country-set container initialisation (deterministic, no RNG)

## 1) Purpose & scope (normative)

Create, per merchant $m$, an **in-memory, ordered, duplicate-free** container $\mathcal{C}_m$ of ISO-2 country codes that:

* anchors **home** at **rank 0** **now**,
* is **append-only** (never reordered) in S4–S6, and
* will be **persisted only after S6** as `alloc/country_set`, the **sole authority** for inter-country order (`rank: 0 = home; 1..K` for foreigns).

S3.3 **performs no writes** and **consumes no RNG**. Inter-country order is **not** encoded in egress; consumers (incl. 1B) **must** join `country_set.rank`.

---

## 2) Inputs (from S3.2; authoritative)

From S3.2 we receive (in-memory):

```
S3Branch {
  merchant_id, home_country_iso = c,
  mcc, channel, N,
  e,                              # boolean eligibility bit
  eligibility_rule_id,            # string
  eligibility_hash,               # hex string
  reason_code, reason_text,       # enum|null + optional text
  C, K,                           # may be set by S3.2; see below
  next_state,                     # may be set by S3.2; re-derived here
  seed, run_id,
  parameter_hash, manifest_fingerprint
}
```

Contracts already enforced in S3.1–S3.2:

* `e:boolean` is read from `crossborder_eligibility_flags` (parameter-scoped; exactly one row per `(parameter_hash, merchant_id)`); `channel ∈ {"card_present","card_not_present"}`.
* `home_country_iso = c` is uppercase ISO-3166-1 alpha-2 and FK-valid against the canonical ISO dataset referenced by the schemas.

---

## 3) Formal definition (container, rank, mapping)

Let $\mathcal{I}$ be the canonical ISO-2 universe. Define the **country-set container** for merchant $m$:

$$
\boxed{\,\mathcal{C}_m = (c_0, c_1, \dots, c_{K_m})\quad\text{with}\quad c_i \in \mathcal{I},\ c_i\neq c_j\ (i\neq j)\,}
$$

with rank function $\mathrm{rank}_{\mathcal{C}_m}(c_i)=i$. By construction $c_0$ is **home**. Persistence (after S6) maps position $i$ to `country_set`:

$$
(\texttt{merchant_id}=m,\ \texttt{country_iso}=c_i,\ \texttt{is_home}=[i=0],\ \texttt{rank}=i),
$$

partitioned by `seed, parameter_hash`, PK `(merchant_id,country_iso)`.

---

## 4) Preconditions (MUST hold)

1. **Branch decision available.** S3.2 completed; `e ∈ {true,false}`; flags are schema-valid.
2. **Home ISO FK.** `c ∈ 𝓘` and passes the ISO FK referenced by schema.
3. **No RNG.** S3.3 neither reads nor writes RNG streams. (S4–S6 evidence for `e=false` is a validation failure, not an S3.3 action.)

---

## 5) Deterministic procedure (normative pseudocode)

```pseudo
# Output (in-memory): CountryInit {
#   merchant_id, C, K, home_country_iso, e, next_state,
#   seed, run_id, parameter_hash, manifest_fingerprint
# }

function s3_3_init_country_container(x: S3Branch) -> CountryInit:
    assert iso2_fk_valid(x.home_country_iso)

    C := []                     # ordered, dup-free
    C.append(x.home_country_iso)  # rank 0 reserved

    if x.e == false:            # domestic-only path
        K := 0
        next_state := "S6"      # single-writer persists country_set (home only)
    else:                       # eligible
        K := null               # unknown until S4 (JSON null)
        next_state := "S4"

    return {
      merchant_id: x.merchant_id,
      C: C,                     # e.g. ["GB"] (len 1 at init)
      K: K,                     # 0 or null
      home_country_iso: x.home_country_iso,
      e: x.e,
      next_state: next_state,
      seed: x.seed, run_id: x.run_id,
      parameter_hash: x.parameter_hash,
      manifest_fingerprint: x.manifest_fingerprint
    }
```

**Container rules (MUST).**
Append-only thereafter (S4–S6); `C[0]` never changes; before any append, assert the candidate ISO isn’t already in `C`; no reordering/deletes; persistence after S6 writes one row per position with `rank=i`.

---

## 6) Determinism & evidence (validator hooks)

* **No-RNG invariant (S3).** S3.1–S3.3 emit **no** RNG. For `e=false`, S9 asserts **absence** of S4–S6 events (`poisson_component(context="ztp")`, `ztp_*`, `gumbel_key`, `dirichlet_gamma_vector`) under `(merchant_id, seed, parameter_hash, run_id)`. Violation ⇒ branch inconsistency.
* **Country-set at write-time.** After S6, `country_set` contains exactly one home row `(is_home=true, rank=0)` and, if eligible, **contiguous** foreign ranks `1..K` with no gaps/dupes; order equals S6’s selection order. (Checked in S9.)

---

## 7) Failure taxonomy (abort; S3.3 is side-effect-free)

* `E_HOME_ISO_INVALID(m)` — `home_country_iso` fails ISO FK.
* `E_CONTAINER_DUP_HOME(m)` — container unexpectedly non-empty before init (runner bug).
* `E_BRANCH_UNSET(m)` — S3.2 didn’t supply `e ∈ {true,false}`.

---

## 8) Persistence mapping (for **S6** single writer; normative contract)

When **S6** completes (foreign selection for `e=true` **or** domestic-only persistence for `e=false`), persist `C` to:

```
path: data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/
schema_ref: schemas.1A.yaml#/alloc/country_set
PK: ["merchant_id","country_iso"]
```

`country_set` is the **ONLY** authoritative store of cross-country order; readers **must** join it.

---

## 9) Conformance tests (suite skeleton)

1. **Domestic-only anchor.** `e=false`, `c="GB"` → `C=["GB"]`, `K=0`, `next_state="S6"`. After S6, `country_set` has exactly `(GB, rank=0)`. **Pass.**
2. **Eligible anchor.** `e=true`, `c="US"` → `C=["US"]`, `K=null`, `next_state="S4"`. After S6, `country_set` shows `("US", rank=0)` + contiguous `1..K`. **Pass.**
3. **No-RNG invariant.** For `e=false`, ensure no `gumbel_key`, `dirichlet_gamma_vector`, or `poisson_component(context="ztp")` exist for `(merchant_id, seed, parameter_hash, run_id)`. **Pass if absent.**
4. **ISO FK negative.** `c="UK"` (non-canonical) → `E_HOME_ISO_INVALID`. **Fail.**

---

## 10) Output (to next state)

```
CountryInit {
  merchant_id,
  C = [home_country_iso],
  K ∈ {0, null},
  home_country_iso, e,
  next_state ∈ {"S4","S6"},
  seed, run_id,
  parameter_hash, manifest_fingerprint
}
```

S4 consumes this for ZTP when `e=true`; **S6** persists `country_set` (home-only when `e=false`, extended when `e=true`) using the partition keys `{seed, parameter_hash}`.

---

**Notes on deviations fixed:**

* Replaced prior “domestic → S7” routing with **domestic → S6** (single writer of `country_set`), eliminating the orphaned home row risk.
* Replaced the non-serialisable `⊥` sentinel with JSON-native **`null`** for unknown `K`.
* Inputs aligned to S3.2’s governed fields; lineage now explicitly carries **`seed`** and **`run_id`** for downstream joins.

---

# S3.4 — Determinism, lineage, and validator hooks (no RNG)

## 1) Purpose & scope (normative)

S3 is a **deterministic gate**. S3.4 formalises:

* the **lineage model** (which keys scope data vs logs),
* the **no-RNG invariant** for S3,
* the **evidence contracts** S9 uses to prove S3’s decision matches downstream behaviour (presence/absence of S4–S6 RNG events), and
* the **failure taxonomy** & **conformance probes** tied to the dictionary & schemas.

S3.4 **reads/writes no datasets** and **consumes no RNG**.

---

## 2) Lineage model (keys, scopes, partitions)

**Keys & scopes (normative):**

* `parameter_hash` — **parameter scope** (all governed configuration, including **eligibility rules**). All parameter-scoped datasets (e.g., `crossborder_eligibility_flags`, `country_set`, `ranking_residual_cache_1A`) partition by this key and embed it per row.
* `manifest_fingerprint` — **artefact fingerprint** (complete artefact set + VCS + parameter hash). Embedded in persisted outputs/validation bundle; not a partition key for logs.
* `seed` — RNG universe key; partitions RNG event logs and seed-dependent artefacts.
* `run_id` — **logs-only** execution id (partitions logs/audits); **must not** influence results.

**Partitioning contracts (from dictionary/spec):**

* Parameter-scoped dataset:
  `data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/` (schema `#/prep/crossborder_eligibility_flags`).
* RNG events (logs):
  `logs/rng/events/<label>/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` (schema `schemas.layer1.yaml#/rng/events/<label>`).
* `country_set` (persisted by **S6**):
  `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/` (schema `#/alloc/country_set`).
* Validation bundle binds to `{manifest_fingerprint}`; gate to 1B passes only when `_passed.flag == SHA256(bundle)`.

---

## 3) No-RNG invariant & replay posture

**I-EL1 (No RNG in S3).** Sub-states **S3.1–S3.3** perform **zero** random draws. Their outputs are a pure function of:

$$
(\text{merchant_ids projection},\ \text{crossborder_eligibility_flags}[{\parameter_hash}],\ N_m \text{ from S2}),
$$

under fixed `(seed, parameter_hash, manifest_fingerprint)`. S3 is therefore **bit-replayable** by data alone. (S2 acceptance is evidenced by exactly one `nb_final` event.)

---

## 4) Evidence contracts for S9 (presence/absence rules)

S9 must **prove** that S3’s branch decision

$$
\boxed{\ \text{branch}_m = \begin{cases}
\textsf{eligible}      & \text{if } e_m=1,\\
\textsf{domestic_only} & \text{if } e_m=0
\end{cases}}
$$

is **consistent** with downstream stochastic activity (S4–S6), using only logs/datasets, joined on `(merchant_id, seed, parameter_hash, run_id)`.

### 4.1 Authoritative RNG event streams

* **ZTP (S4):** `rng_event_poisson_component` (`context="ztp"`), `rng_event_ztp_rejection`, `rng_event_ztp_retry_exhausted`.
* **Selection (S6):** `rng_event_gumbel_key` (Gumbel-top-k keys).
* **Dirichlet (S7 evidence):** `rng_event_dirichlet_gamma_vector`.
  *Note:* for **domestic-only** (`|C|=1`) **S7 must not emit Dirichlet events**.

(All partitioned by `seed, parameter_hash, run_id` and typed per `schemas.layer1.yaml#/rng/events/<label>`.)

### 4.2 Coherence rules (normative)

* **I-EL3-DOM (domestic-only coherence).** If `e_m == false`, then **no** S4–S6 RNG events may exist for merchant $m$ under the same `(seed, parameter_hash, run_id)`:

  $$
  \forall \ell \in \{\texttt{poisson_component(ztp)},\ \texttt{ztp_rejection},\ \texttt{ztp_retry_exhausted},\ \texttt{gumbel_key},\ \texttt{dirichlet_gamma_vector}\}:\ |T_\ell(m)| = 0.
  $$

  Violation ⇒ `branch_inconsistent_domestic`.

* **I-EL3-ELIG (eligible coherence).** If `e_m == true`, **S4 is entered**; S9 must find **at least one** `poisson_component(context="ztp")` **or** a terminal `ztp_retry_exhausted`. Absence of both ⇒ `branch_inconsistent_eligible`.

* **I-EL2 (flags uniqueness & schema).** For each `(parameter_hash, merchant_id)` there is **exactly one** flags row with governed types:
  `is_eligible:boolean`, `eligibility_rule_id:string (non-null)`, `eligibility_hash:string (non-null)`, `reason_code ∈ {"mcc_blocked","cnp_blocked","home_iso_blocked"}|null`, optional `reason_text`. Missing/duplicate/typedrift ⇒ structural fail.

* **I-EL4 (home ISO FK guard).** `home_country_iso` is ISO-2 canonical (pre-FK for later `country_set.country_iso`).

---

## 5) Join semantics (validator)

Validators **must** join on:

$$
(\texttt{merchant_id},\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{run_id})
$$

with event qualifiers (e.g., `context="ztp"`). The join domain is merchants with S2 acceptance (exactly one `nb_final`).

---

## 6) Structured invariants (validator-facing)

For each merchant $m$ in S3’s domain:

* **I-EL1 (No RNG in S3):** zero S3-labelled RNG streams.
* **I-EL2 (Flags):** uniqueness + governed schema satisfied.
* **I-EL3 (Branch):** DOM ⇒ absence of S4–S6 events; ELIG ⇒ presence of S4 evidence or explicit exhaustion.
* **I-EL4 (Home ISO FK):** home ISO in canonical list.

Any breach is a **hard fail**; `_passed.flag` is not written.

---

## 7) Reference validator routine (language-agnostic)

```pseudo
INPUTS:
  Flags := read_table("crossborder_eligibility_flags", part={parameter_hash})
  NB    := read_log("rng_event_nb_final",            part={seed,parameter_hash,run_id})
  ZTP   := union(
             read_log("rng_event_poisson_component").where(context="ztp"),
             read_log("rng_event_ztp_rejection"),
             read_log("rng_event_ztp_retry_exhausted")
           )
  SEL   := read_log("rng_event_gumbel_key")
  DIR   := read_log("rng_event_dirichlet_gamma_vector")
  ISO   := canonical_iso2_table()

M3 := distinct(NB.merchant_id)   # S3 domain

for m in M3:
  f := Flags.lookup(parameter_hash, m)
  if |f| != 1: fail("eligibility_flags_cardinality", m)          # I-EL2
  assert type(f.is_eligible)==BOOLEAN
  assert f.eligibility_rule_id != NULL and f.eligibility_hash != NULL
  assert f.reason_code == NULL or f.reason_code in {"mcc_blocked","cnp_blocked","home_iso_blocked"}

  if f.is_eligible == false:                                      # I-EL3-DOM
     assert ZTP.none(m) and SEL.none(m) and DIR.none(m)
     else fail("branch_inconsistent_domestic", m)
  else:                                                           # I-EL3-ELIG
     assert ZTP.any(m) or ZTP.retry_exhausted(m)
     else fail("branch_inconsistent_eligible", m)

  assert ISO.contains(home_iso(m)) else fail("illegal_home_iso", m)  # I-EL4

emit_rng_accounting_summary()
return PASS
```

All `read_*` calls use the partition keys above; accounting summarises per-label counts by merchant and is embedded in the validation bundle.

---

## 8) Failure taxonomy (names, conditions, evidence)

* **`eligibility_flags_cardinality`** — 0 or >1 flags rows for `(parameter_hash, merchant_id)`.
  *Evidence:* offending subset of `crossborder_eligibility_flags`.
* **`branch_inconsistent_domestic`** — `is_eligible=false` but any of {`poisson_component(ztp)`, `ztp_rejection`, `ztp_retry_exhausted`, `gumbel_key`, `dirichlet_gamma_vector`} present.
  *Evidence:* offending JSONL rows.
* **`branch_inconsistent_eligible`** — `is_eligible=true` but **no** `poisson_component(ztp)` and **no** `ztp_retry_exhausted`.
  *Evidence:* zero-row proof under the same partitions.
* **`illegal_home_iso`** — home ISO not in canonical set.
  *Evidence:* FK target id + offending value.

Any hard fail ⇒ bundle with diagnostics; `_passed.flag` **not** written; 1B must not consume egress for the fingerprint.

---

## 9) Optional observability (non-authoritative)

Runners **may** emit per-merchant system logs (validators don’t rely on them):

```
logs/system/eligibility_gate.v1.jsonl
{ event:"s3_decision",
  merchant_id, parameter_hash, manifest_fingerprint,
  e:true|false, eligibility_rule_id, eligibility_hash,
  reason_code:null|"mcc_blocked", reason_text:"...", branch:"eligible"|"domestic_only" }
```

---

## 10) Conformance tests (suite skeleton)

1. **Domestic coherence (pass):** `is_eligible=false`; zero S4–S6 events ⇒ pass.
2. **Domestic inconsistency (fail):** inject one `gumbel_key` ⇒ `branch_inconsistent_domestic`.
3. **Eligible via ZTP (pass):** `is_eligible=true`; at least one `poisson_component(ztp)` ⇒ pass.
4. **Eligible exhaustion (pass):** `is_eligible=true`; no `poisson_component(ztp)` but a `ztp_retry_exhausted` ⇒ pass.
5. **Eligible inconsistency (fail):** `is_eligible=true`; neither ZTP evidence nor exhaustion ⇒ `branch_inconsistent_eligible`.
6. **Flags cardinality (fail):** duplicate flags rows ⇒ `eligibility_flags_cardinality`.
7. **ISO FK (fail):** home ISO `"UK"` ⇒ `illegal_home_iso`.

---

## 11) Complexity & performance

Presence/absence probes are O(1) per merchant per stream with indices on `(seed, parameter_hash, run_id, merchant_id)`. Bundle hashing is linear in bundle size.

---

## 12) Outputs & hand-off

S3.4 writes nothing. **S9**:

* compiles `validation_bundle_1A(fingerprint)`,
* writes `_passed.flag = SHA256(bundle)`, and
* **authorises** 1B consumption only when the flag matches the bundle for the same fingerprint.

Cross-country order is **only** in `country_set.rank`; egress does **not** encode it.

---

# S3.5 — Failure modes & operator playbook (normative, no RNG)

## 1) Scope

S3 is a **deterministic gate**. Failures fall into two buckets:

* **Immediate S3 aborts** — stop the merchant **before** any S4–S6 work (pure data/contract issues).
* **Validation hard-fails (S9)** — caught post-write by the validator via event presence/absence & cross-dataset checks; these **block** the 1A→1B hand-off (`_passed.flag` not written).

S3 writes **no datasets**; failures produce **diagnostic logs** and terminate the merchant’s path for the current run.

---

## 2) Legend (keys, loci, severity)

* **Locus:** `S3.1` (bind), `S3.2` (decide), `S3.3` (container init), `S9` (validator).
* **Join keys:**

  * **Logs:** `(merchant_id, seed, parameter_hash, run_id)`
  * **Parameter-scoped tables:** `(merchant_id, parameter_hash)`
* **Severity:** **Hard fail** blocks bundle sign-off; **Soft warn** — *none for S3*.

---

## 3) Error taxonomy (canonical)

### E_NOT_MULTISITE_OR_MISSING_S2 — *Immediate abort*

**Locus.** S3.1 precondition.
**Condition.** `count_rows(rng_event_nb_final where keys match) != 1` or `nb_final.value < 2`.
**Evidence.** `logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` (schema `#/rng/events/nb_final`).
**Diagnostics.**

```json
{
  "error":"E_NOT_MULTISITE_OR_MISSING_S2",
  "merchant_id": "M", "seed": "S", "parameter_hash": "P", "run_id": "R",
  "probe":{"stream":"nb_final","count":0}
}
```

**Remediation.** Ensure S1 flagged multi-site and S2 wrote **exactly one** `nb_final` with `value ≥ 2`. Re-run S1–S3 for the merchant partition.

---

### E_FLAGS_MISSING — *Immediate abort*

**Locus.** S3.1 lookup.
**Condition.** No row in `crossborder_eligibility_flags` for `(parameter_hash, merchant_id)`.
**Evidence.** Empty result under `…/crossborder_eligibility_flags/parameter_hash={parameter_hash}/` (schema `#/prep/crossborder_eligibility_flags`).
**Diagnostics.**

```json
{
  "error":"E_FLAGS_MISSING",
  "table":"crossborder_eligibility_flags",
  "parameter_hash":"P", "merchant_id":"M"
}
```

**Remediation.** (Re)build S0 flags for the active `{parameter_hash}`; verify PK coverage; re-run S3.

---

### E_FLAGS_DUPLICATE — *Immediate abort*

**Locus.** S3.1 lookup.
**Condition.** >1 row in `crossborder_eligibility_flags` for `(parameter_hash, merchant_id)`.
**Evidence.** Duplicate rows in the same partition; violates uniqueness.
**Diagnostics.**

```json
{
  "error":"E_FLAGS_DUPLICATE",
  "table":"crossborder_eligibility_flags",
  "parameter_hash":"P", "merchant_id":"M", "row_count":2
}
```

**Remediation.** Deduplicate upstream flags (S0); enforce uniqueness; re-run S3.

---

### E_FLAGS_SCHEMA — *Immediate abort*

**Locus.** S3.2 guard (defensive).
**Condition.** Flags row violates governed schema:
`is_eligible` not boolean, **or** `eligibility_rule_id`/`eligibility_hash` NULL, **or** non-null `reason_code` not in enum `{"mcc_blocked","cnp_blocked","home_iso_blocked"}`.
**Evidence.** Row mismatches `schemas.1A.yaml#/prep/crossborder_eligibility_flags`.
**Diagnostics.**

```json
{
  "error":"E_FLAGS_SCHEMA",
  "table":"crossborder_eligibility_flags",
  "parameter_hash":"P", "merchant_id":"M",
  "violations":["eligibility_rule_id:null","reason_code:invalid_enum"]
}
```

**Remediation.** Fix the S0 compiler; rebuild the partition; re-run S3.

---

### E_HOME_ISO_INVALID — *Immediate abort*

**Locus.** S3.1/S3.3 FK pre-guard.
**Condition.** `home_country_iso ∉ ISO-3166-1 alpha-2` canonical set.
**Evidence.** FK miss against ingress ISO table (schema FK target).
**Diagnostics.**

```json
{
  "error":"E_HOME_ISO_INVALID",
  "merchant_id":"M", "home_country_iso":"UK",
  "fk_target":"schemas.ingress.layer1.yaml#/iso3166_canonical_2024"
}
```

**Remediation.** Correct ingress mapping to valid ISO-2 (e.g., `GB` vs `UK`); re-ingest; re-run S3.

---

### F_EL_BRANCH_INCONSISTENT — *Validation hard-fail (S9)*

**Locus.** S9 presence/absence proof.
**Condition.**

* **Case A (domestic-only):** `is_eligible=false` **but** any of
  `poisson_component(context="ztp")`, `ztp_rejection`, `ztp_retry_exhausted`, `gumbel_key`, `dirichlet_gamma_vector` exist.
* **Case B (eligible):** `is_eligible=true` **and** no `poisson_component(context="ztp")` **and** no `ztp_retry_exhausted`.

(Join on `(merchant_id, seed, parameter_hash, run_id)`; filter `context` as applicable.)

**Evidence.** Offending JSONL rows (or zero-row proofs), the merchant’s flags row, and RNG accounting in the validation bundle.
**Diagnostics (validator emits).**

```json
{
  "fail":"F_EL_BRANCH_INCONSISTENT",
  "merchant_id":"M","seed":"S","parameter_hash":"P","run_id":"R",
  "flags":{
    "is_eligible":false,
    "eligibility_rule_id":"default_v1","eligibility_hash":"…",
    "reason_code":"mcc_blocked","reason_text":null
  },
  "rng_evidence":{
    "ztp_poisson_component": 1,
    "ztp_rejection": 0,
    "ztp_retry_exhausted": 0,
    "gumbel_key": 0,
    "dirichlet_gamma_vector": 0
  }
}
```

**Remediation.**

* **A (domestic but events present):** fix runner to **route domestic multi-site to S6** (home-only write) and **emit no S4–S6 RNG**; purge stray logs for this `(seed,parameter_hash,run_id)`; re-run S3→S9.
* **B (eligible but no S4 evidence):** ensure S4 executes and logs ZTP (or exhaustion) for `e=true`; re-run S3→S9.

---

## 4) Detection & joins (authoritative sources)

* **Flags table (parameter-scoped).**
  `data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/` — the **only** source of truth for `is_eligible`; governed fields: `eligibility_rule_id`, `eligibility_hash`, `reason_code|reason_text`. Schema `#/prep/crossborder_eligibility_flags`.
* **RNG events (logs).**
  `logs/rng/events/<label>/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` — `poisson_component`, `ztp_*`, `gumbel_key`, `dirichlet_gamma_vector`. Validators must filter `context="ztp"` where shared.
* **Validator artefacts.**
  `validation_bundle_1A(fingerprint)` with `rng_accounting.json` and diagnostics; `_passed.flag` must equal `SHA256(bundle)` to authorise 1B.

---

## 5) Diagnostics (runner system log; mandatory shape)

On any **immediate S3 abort**, emit a JSONL record (non-authoritative; for ops only):

```
logs/system/eligibility_gate.v1.jsonl
{
  "event":"s3_abort",
  "error": "<ID>",
  "merchant_id":"M",
  "parameter_hash":"P",
  "manifest_fingerprint":"F",
  "seed":"S","run_id":"R",
  "dataset": "crossborder_eligibility_flags" | "rng_event_nb_final" | "ingress",
  "details": { … minimal, redaction-safe … },
  "ts_utc":"..."
}
```

Authoritative evidence remains the tables/log streams and the validation bundle.

---

## 6) Operator playbook (step-by-step)

**A) Flags missing/duplicate/schema (E_FLAGS_\*)**

1. Inspect `…/crossborder_eligibility_flags/parameter_hash={P}/`.
2. Fix S0 compiler (coverage, PK uniqueness, governed types: `is_eligible`, `eligibility_rule_id`, `eligibility_hash`, `reason_code`).
3. Rebuild the partition; **re-run S3**.

**B) Not multi-site / missing S2 (E_NOT_MULTISITE_OR_MISSING_S2)**

1. Check `nb_final` at `…/rng_event_nb_final/seed={S}/parameter_hash={P}/run_id={R}/`.
2. If missing: re-run S1–S2; if duplicate: fix re-entry/transactionality.
3. Re-run S3 after exactly one acceptance exists with `value ≥ 2`.

**C) Illegal ISO (E_HOME_ISO_INVALID)**

1. Verify `home_country_iso` against the canonical ISO FK target.
2. Correct ingress mapping (`UK→GB`, etc.).
3. Re-ingest; re-run S3.

**D) Branch inconsistency (F_EL_BRANCH_INCONSISTENT)**

1. Open the bundle’s `rng_accounting.json` to see which stream tripped.
2. If `e=false` but any S4–S6 RNG exists: update runner to **short-circuit S4** and **persist via S6 (home-only)**; clean logs.
3. If `e=true` but no S4 evidence: ensure S4 emits `poisson_component(context="ztp")` or `ztp_retry_exhausted`.
4. Re-run S3→S9; `_passed.flag` will only be written once the bundle passes.

---

## 7) Idempotence & retries

* **S3 idempotence.** S3 uses **no RNG** and writes **no datasets**; repeating S3 with the same `(seed, parameter_hash, manifest_fingerprint)` and identical inputs yields identical outputs.
* **Validation retries.** Fixes to flags or runner logic require re-running S3→S9; 1B remains **locked out** until the new `validation_bundle_1A` passes and `_passed.flag` matches its digest for the same fingerprint.

---

## 8) Conformance tests (suite skeleton)

1. **E_FLAGS_MISSING.** Remove the flags row for `M` → S3.1 aborts `E_FLAGS_MISSING`.
2. **E_FLAGS_DUPLICATE.** Duplicate `(M,P)` row → S3.1 aborts `E_FLAGS_DUPLICATE`.
3. **E_FLAGS_SCHEMA.** Set `eligibility_rule_id=NULL` → S3.2 aborts `E_FLAGS_SCHEMA`.
4. **E_HOME_ISO_INVALID.** `home_country_iso="UK"` → S3.1/S3.3 aborts.
5. **F_EL_BRANCH_INCONSISTENT (domestic).** Flags `is_eligible=false` but emit one `gumbel_key` → S9 hard-fails; `_passed.flag` not written.
6. **F_EL_BRANCH_INCONSISTENT (eligible).** Flags `is_eligible=true` but **no** ZTP evidence or exhaustion → S9 hard-fails.

---

## 9) Why this is safe

* Flags are **parameter-scoped**; identical `{parameter_hash}` ⇒ identical `e_m` across replays.
* S3 emits **no RNG**; stochastic evidence is confined to S4–S6 logs that S9 inspects via fixed schemas/paths.
* Hand-off to 1B is cryptographically gated via `_passed.flag == SHA256(bundle)` for the same `manifest_fingerprint`.

---

# S3.6 — Outputs (state boundary, deterministic, no RNG)

## 1) Purpose & scope (normative)

S3 is a **deterministic gate** that **writes no datasets** and **consumes no RNG**. S3.6 defines the **state boundary**: the *only* thing that leaves S3 is an **in-memory export** (per merchant) carrying the **branch decision**, the **seeded lineage**, and the **initialised country-set container** (home at rank 0). Persistence of cross-country order happens **later** in `alloc/country_set` after **S6**; egress `outlet_catalogue` is **order-agnostic** and must be joined to `country_set.rank`.

---

## 2) Inputs to S3.6 (provenance recap; already bound)

From S3.1–S3.3 (all **deterministic**, parameter/run-scoped):

* `merchant_id:int64`
* `home_country_iso = c` (ISO-3166-1 alpha-2, FK-valid)
* `mcc:int32`, `channel ∈ {"card_present","card_not_present"}`
* `N:int32` — accepted **NB** outlet count from S2 (`N ≥ 2`, evidenced by exactly one `nb_final`)
* `flags` (governed):
  `is_eligible:boolean` ≡ `e`,
  `eligibility_rule_id:string`, `eligibility_hash:string`,
  `reason_code ∈ {"mcc_blocked","cnp_blocked","home_iso_blocked"}|null`, `reason_text:string|null`
* Lineage: `seed:uint64`, `run_id:string/uuid`, `parameter_hash:hex64`, `manifest_fingerprint:hex64`

---

## 3) Formal outputs (per merchant) — **export object**

Define the S3 **export** (non-persisted; passed by value/reference to the next state):

```
S3Export {
  merchant_id: int64,
  home_country_iso: string[ISO2],
  mcc: int32,
  channel: enum{"card_present","card_not_present"},
  N: int32,                               # accepted in S2 (N >= 2)
  e: boolean,                             # eligibility bit from flags
  eligibility_rule_id: string,            # governed code
  eligibility_hash: string,               # hex
  reason_code: enum{"mcc_blocked","cnp_blocked","home_iso_blocked"} | null,
  reason_text: string | null,
  C: list[string[ISO2]],                  # ordered, dup-free; rank 0 = home
  K: int32 | null,                        # 0 if domestic-only; null until S4 otherwise
  next_state: enum{"S4","S6"},            # S6 is single writer for country_set
  seed: uint64,
  run_id: string,
  parameter_hash: hex64,
  manifest_fingerprint: hex64
}
```

**Construction rules (deterministic, no RNG):**

* Initialise `C := [home_country_iso]` (rank 0 = home).
* If `e == false`: set `K := 0` and `next_state := "S6"` (**route domestic multi-site to S6** so it persists `country_set` with home-only).
* If `e == true`: set `K := null` (unknown; determined by S4) and `next_state := "S4"`.
* Duplicates in `C` are forbidden (assert before any later append).

---

## 4) What S3 **does not** do (normative non-actions)

* **No persistence.** S3 writes **no** rows to any dataset; in particular, it does **not** write `country_set`. Cross-country order is persisted **after S6** to `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/` (schema `#/alloc/country_set`), which is the **only** authoritative store of inter-country rank.
* **No RNG.** S3 emits **no** RNG event streams. Any S4–S6 RNG evidence for a merchant with `e==false` causes validator fail `branch_inconsistent_domestic`.
* **No egress.** `outlet_catalogue` is S8’s responsibility and is **order-agnostic**; consumers must verify the 1A validation gate before reading and must join `country_set.rank` for cross-country order.

---

## 5) Downstream contracts (who consumes which fields, exactly)

### 5.1 S4 (eligible only; `next_state="S4"`)

**Consumes:** `merchant_id, C=[home], N, mcc, channel, home_country_iso, seed, run_id, parameter_hash, manifest_fingerprint`.
**Produces:** ZTP draws to determine `K ≥ 1` and logs: `poisson_component(context="ztp")`, `ztp_rejection`, optionally `ztp_retry_exhausted`. **Never** modifies `C[0]`.

### 5.2 S6 (domestic-only; `next_state="S6"`)

**Consumes:** `merchant_id, C=[home], K=0, N, seed, run_id, parameter_hash, manifest_fingerprint`.
**Produces (domestic path):** persists `country_set` with exactly one row `{country_iso=home, is_home=true, rank=0}`. **No RNG** on this path. Then hands off to S7 for within-country sequencing.

### 5.3 S7 (post-S6 integerisation)

**Consumes:** ordered `country_set` (home at rank 0; possibly foreigns if eligible).
**Produces:** within-country sequencing & integerisation. When `|C| = 1` (domestic-only), S7 emits **no** Dirichlet events (`dirichlet_gamma_vector` / `gamma_component(context="dirichlet")` are absent).

---

## 6) State-boundary invariants (validator-facing; MUST hold)

For every merchant $m$ admitted to S3:

1. **Flags cardinality & schema.** Exactly one row in `crossborder_eligibility_flags` for `(parameter_hash, merchant_id)` with governed fields (`is_eligible`, `eligibility_rule_id`, `eligibility_hash`, `reason_code|reason_text`).
2. **Branch coherence.**

   * If `e==false` ⇒ **no** S4–S6 RNG events under `(merchant_id, seed, parameter_hash, run_id)`.
   * If `e==true` ⇒ **at least one** `poisson_component(context="ztp")` **or** a `ztp_retry_exhausted` exists.
3. **Country-set shape at persistence time.** When `country_set` is later written, it must contain exactly one home row `(is_home=true, rank=0, country_iso=c)` and, if eligible, **contiguous** foreign ranks `1..K`. `country_set` is the **only** authoritative store of inter-country order.
4. **Egress separation.** `outlet_catalogue` never encodes cross-country order; readers must recover it via join to `country_set.rank` and must verify `_passed.flag == SHA256(validation_bundle_1A)` for the same fingerprint **before** reading.

---

## 7) Reference procedure (language-agnostic pseudocode)

```pseudo
# S3.6: finalise the export and route
function s3_6_state_boundary(x: S3Export) -> (route, S3Export):
    assert typeof(x.e) == BOOLEAN
    assert x.C == [x.home_country_iso] and iso2_fk_valid(x.home_country_iso)

    if x.e == false:
        x.K = 0
        x.next_state = "S6"     # single writer for country_set (home-only)
        route = "S6"
    else:
        x.K = null              # determined by S4
        x.next_state = "S4"
        route = "S4"

    # preserve lineage for downstream writes/logs
    assert x.seed != null and x.run_id != null and x.parameter_hash != null and x.manifest_fingerprint != null
    return (route, x)           # pass by value/reference; no persistence
```

**Preserved keys:** `(merchant_id, seed, run_id, parameter_hash, manifest_fingerprint)` accompany the export so S4/S6/S7 writes can embed them in datasets/logs.

---

## 8) Failure surface at the boundary

S3.6 introduces **no new** errors (it only packages decisions). All S3 failures are those in **S3.5** (flags missing/duplicate/schema, illegal ISO, branch inconsistency), plus any schema/PK/FK checks performed later at `country_set` persistence and S9 validation.

---

## 9) Conformance tests (suite skeleton)

1. **Domestic routing.** `e=false`, `C=["GB"]` ⇒ route `S6`, export has `K=0`, `next_state="S6"`. After S6, `country_set` contains only `(GB, rank=0)`. **Pass.**
2. **Eligible routing.** `e=true`, `C=["US"]` ⇒ route `S4`, export has `K=null`, `next_state="S4"`. S4 emits ZTP evidence or exhaustion. **Pass.**
3. **No Dirichlet when `|C|=1`.** For `e=false` (domestic-only), assert **zero** rows in `dirichlet_gamma_vector` and `gamma_component(context="dirichlet")` under `(merchant_id, seed, parameter_hash, run_id)`. **Pass if absent.**
4. **Order authority separation.** End-to-end, confirm `outlet_catalogue` lacks cross-country order columns and order is recovered exclusively via `country_set.rank`. **Pass.**
5. **No-RNG invariant in S3.** Confirm no S3-labelled RNG streams exist; any S4–S6 events for `e=false` trip `branch_inconsistent_domestic`. **Pass/Fail accordingly.**

---

## 10) Complexity & performance

O(1) per merchant (set scalars, return a struct). **Zero I/O** and **zero RNG** at this boundary. All heavy lifting is deferred to S4/S6/S7.

---

## 11) Why this clean boundary matters

* Keeps S3 **replayable**: decisions derive solely from ingress + parameter-scoped flags + S2 acceptance; with fixed `parameter_hash` and `seed`, the export is deterministic.
* Enforces a **single source of truth** for order: `country_set.rank` (partitioned by `{seed, parameter_hash}`) is the **only** authority; egress and downstream layers don’t duplicate or drift inter-country order.

---

# S3.A — Eligibility gate system log (non-authoritative, no RNG)

## 1) Purpose & scope (normative)

Emit **structured JSONL ops events** around the S3 gate:

* `s3_inputs_bound` (after S3.1),
* `s3_decision` (after S3.2),
* `s3_abort` (when S3.1/S3.2 abort deterministically per S3.5).

This log is **for incident response only**; validators and readers **must not** use it as input. Inter-country order remains solely in `alloc/country_set.rank`; `outlet_catalogue` is order-agnostic and may be consumed only when `_passed.flag == SHA256(validation_bundle_1A)` for the same fingerprint.

**Zero RNG.** S3.A never emits `rng_event_*` and has no read-after-write coupling into modelling.

---

## 2) Storage layout (pathing, partitions, rotation)

```
logs/system/eligibility_gate.v1/run_id={run_id}/part-*.jsonl.gz
```

* **Partition key:** `run_id` (scopes incident triage to a single execution).
* **Envelope lineage in every record:** `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`.
* **Compression:** gzip; **rotation:** \~256 MiB per part; **retention:** ≥30 days (ops).
* **Non-interference:** not listed as an authoritative dataset in registry/dictionary; **never** read by pipeline components.

---

## 3) Event model (closed set + envelopes)

### 3.1 Types

```
"type" ∈ {"s3_inputs_bound","s3_decision","s3_abort"}
```

Exactly one of `payload_inputs`, `payload_decision`, `payload_abort` is present.

### 3.2 Common envelope (required on every record)

`event_id: hex64`, `type`, `ts_utc (RFC3339)`, `merchant_id`, `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id (uuid)`, `module:"1A.S3"`, `version:"v1"`.

### 3.3 Type-specific payloads

**A) `s3_inputs_bound` → `payload_inputs`**

* `home_country_iso: ISO2 (uppercase)`
* `mcc:int32`, `channel ∈ {"card_present","card_not_present"}`
* `N:int32 (≥2)` (S2 acceptance, context only)
* `flags:{ is_eligible:boolean, eligibility_rule_id:string, eligibility_hash:string, reason_code ∈ {"mcc_blocked","cnp_blocked","home_iso_blocked"}|null, reason_text:string|null }` (from `crossborder_eligibility_flags`, parameter-scoped).

**B) `s3_decision` → `payload_decision`**

* `e:boolean` (alias of flags.is_eligible)
* `branch ∈ {"eligible","domestic_only"}`
* `home_country_iso: ISO2`
* `eligibility_rule_id:string`, `eligibility_hash:string`
* `reason_code: enum|null`, `reason_text:string|null` (**must be null when `e==true`**)
* `C0: ISO2` (home anchored at rank 0 in the in-memory container; **country order is later persisted only in `country_set`**).

**C) `s3_abort` → `payload_abort`**

* `error: enum{E_NOT_MULTISITE_OR_MISSING_S2,E_FLAGS_MISSING,E_FLAGS_DUPLICATE,E_FLAGS_SCHEMA,E_HOME_ISO_INVALID}`
* `dataset: string` (e.g., `"crossborder_eligibility_flags"`, `"rng_event_nb_final"`)
* `details: object` (small, redaction-safe probe).

**Invariants.** Envelope fields always present; payload shape matches `type`. Values mirror authoritative tables; schema-violating ingress would already trigger `s3_abort`.

---

## 4) Deterministic `event_id` (idempotent per run)

For dedupe within a run:

$$
\text{event_id}=\mathrm{hex}_{64}(\mathrm{SHA256}(K\ \|\ M\ \|\ R\ \|\ \text{bytes}(T)))
$$

with `K` ∈ {01,02,03} for inputs/decision/abort, `M`=`merchant_id` (8-byte BE), `R`=`run_id` (16 bytes RFC-4122), `T` literal type. Same (merchant,run,type) ⇒ same `event_id`; different `run_id` ⇒ different `event_id`. Ops-only; never enters parameter hashing or validation.

---

## 5) JSON-Schema (normative for this log; non-authoritative overall)

Abridged here; enforce at write time. Authoritative **dataset** schemas remain `schemas.ingress.layer1.yaml`, `schemas.1A.yaml`, `schemas.layer1.yaml`.

```json
{
  "$id":"schemas.ops.1A.s3_log.v1",
  "type":"object",
  "required":["event_id","type","ts_utc","merchant_id","seed","parameter_hash",
              "manifest_fingerprint","run_id","module","version"],
  "properties":{
    "event_id":{"type":"string","pattern":"^[a-f0-9]{64}$"},
    "type":{"enum":["s3_inputs_bound","s3_decision","s3_abort"]},
    "ts_utc":{"type":"string","format":"date-time"},
    "merchant_id":{"$ref":"schemas.1A.yaml#/$defs/id64"},
    "seed":{"$ref":"schemas.1A.yaml#/$defs/uint64"},
    "parameter_hash":{"type":"string","pattern":"^[a-f0-9]{64}$"},
    "manifest_fingerprint":{"type":"string","pattern":"^[a-f0-9]{64}$"},
    "run_id":{"type":"string","format":"uuid"},
    "module":{"const":"1A.S3"},
    "version":{"const":"v1"},

    "payload_inputs":{
      "type":"object",
      "required":["home_country_iso","mcc","channel","N","flags"],
      "properties":{
        "home_country_iso":{"$ref":"schemas.1A.yaml#/$defs/iso2"},
        "mcc":{"type":"integer"},
        "channel":{"enum":["card_present","card_not_present"]},
        "N":{"type":"integer","minimum":2},
        "flags":{
          "type":"object",
          "required":["is_eligible","eligibility_rule_id","eligibility_hash"],
          "properties":{
            "is_eligible":{"type":"boolean"},
            "eligibility_rule_id":{"type":"string","minLength":1},
            "eligibility_hash":{"type":"string","minLength":1},
            "reason_code":{"enum":["mcc_blocked","cnp_blocked","home_iso_blocked",null]},
            "reason_text":{"type":["string","null"]}
          },
          "additionalProperties":false
        }
      },
      "additionalProperties":false
    },

    "payload_decision":{
      "type":"object",
      "required":["e","branch","home_country_iso","eligibility_rule_id","eligibility_hash"],
      "properties":{
        "e":{"type":"boolean"},
        "branch":{"enum":["eligible","domestic_only"]},
        "home_country_iso":{"$ref":"schemas.1A.yaml#/$defs/iso2"},
        "eligibility_rule_id":{"type":"string","minLength":1},
        "eligibility_hash":{"type":"string","minLength":1},
        "reason_code":{"enum":["mcc_blocked","cnp_blocked","home_iso_blocked",null]},
        "reason_text":{"type":["string","null"]},
        "C0":{"$ref":"schemas.1A.yaml#/$defs/iso2"}
      },
      "allOf":[
        {"if":{"properties":{"e":{"const":true}}},
         "then":{"properties":{"reason_code":{"const":null},"reason_text":{"const":null}}}}
      ],
      "additionalProperties":false
    },

    "payload_abort":{
      "type":"object",
      "required":["error","dataset"],
      "properties":{
        "error":{"enum":[
          "E_NOT_MULTISITE_OR_MISSING_S2","E_FLAGS_MISSING","E_FLAGS_DUPLICATE",
          "E_FLAGS_SCHEMA","E_HOME_ISO_INVALID"
        ]},
        "dataset":{"type":"string"},
        "details":{"type":"object"}
      },
      "additionalProperties":false
    }
  },
  "oneOf":[
    {"properties":{"type":{"const":"s3_inputs_bound"},"payload_inputs":{"type":"object"}}, "required":["payload_inputs"]},
    {"properties":{"type":{"const":"s3_decision"},"payload_decision":{"type":"object"}},   "required":["payload_decision"]},
    {"properties":{"type":{"const":"s3_abort"},"payload_abort":{"type":"object"}},         "required":["payload_abort"]}
  ],
  "additionalProperties":false
}
```

---

## 6) Reference emission procedure (language-agnostic)

```pseudo
function emit_s3_log(type, ctx, payload):
  rec := {
    event_id: derive_event_id(type, ctx.merchant_id, ctx.run_id),
    type, ts_utc: now_rfc3339_utc(),
    merchant_id: ctx.merchant_id,
    seed: ctx.seed,
    parameter_hash: ctx.parameter_hash,
    manifest_fingerprint: ctx.manifest_fingerprint,
    run_id: ctx.run_id,
    module: "1A.S3", version: "v1"
  }
  if type == "s3_inputs_bound": rec.payload_inputs   = payload
  if type == "s3_decision":     rec.payload_decision = payload
  if type == "s3_abort":        rec.payload_abort    = payload

  assert validate_json_schema(rec, "schemas.ops.1A.s3_log.v1")
  try append_jsonl_gz("logs/system/eligibility_gate.v1/run_id="+ctx.run_id+"/part-*.jsonl.gz", rec)
  catch IOErr: warn("S3.A log write failed; continuing (non-authoritative)")
```

**Emit points:** end of S3.1 (`s3_inputs_bound`), end of S3.2 or S3.6 (`s3_decision`), and at abort sites (`s3_abort`). **Idempotence:** same (merchant, run, type) ⇒ same `event_id`.

---

## 7) Determinism & non-interference guarantees

* No module is allowed to read from `logs/system/eligibility_gate.v1/*`.
* S9 ignores this log; 1B consumption requires `_passed.flag` for the fingerprinted bundle.
* **Schema authority** remains the three JSON-Schemas for ingress, 1A, and RNG events; this ops schema is **not** authoritative.

---

## 8) Privacy & redaction

No PII (merchant_id is internal). `payload_abort.details` must stay **small** (counts/keys only).

---

## 9) Failure semantics (logging must not affect modelling)

Best-effort policy: failures to write/validate logs **never** abort S3. Buffer a small in-RAM queue and drop on persistent outage; timestamps are advisory.

---

## 10) Example records

Examples mirror governed fields and lineage:

* **`s3_inputs_bound`** with governed flags (eligibility ids & reason codes)
* **`s3_decision`** with `e=true` ⇒ `reason_code=null, reason_text=null`
* **`s3_abort`** for `E_FLAGS_MISSING` with minimal `details`

(Examples follow the same shapes shown in the expanded spec and ops schema).

---

## 11) Conformance tests (suite skeleton)

1. **Schema pass:** one record of each type validates against `schemas.ops.1A.s3_log.v1`.
2. **Branch rule:** `e=true` ⇒ `reason_code=null`, `reason_text=null`; `e=false` ⇒ governed `reason_code` allowed.
3. **ID idempotence:** same merchant+run+type ⇒ same `event_id`; different `run_id` ⇒ different `event_id`.
4. **Non-interference:** remove the entire log folder and rerun S3 → modelling outputs & S9 unchanged.
5. **Rotation:** >256 MiB produces multiple parts; each is valid JSONL.

---

### Why this is safe

* Log remains **non-authoritative**; schema authority is unchanged.
* Country order stays single-sourced in `country_set` and is **not** encoded in egress; consumers must join `country_set.rank`.

---