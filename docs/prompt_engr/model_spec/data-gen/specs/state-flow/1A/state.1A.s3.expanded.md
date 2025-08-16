# S3.1 — Inputs & canonical materialisation (deterministic, no RNG)

## 1) Purpose & scope (normative)

This sub-state **binds** the authoritative, deterministic inputs that the S3 gate needs for each merchant $m$ that exited S2 with an accepted multi-site outlet count. It **reads**:

* the ingress merchant identity/features,
* the **parameter-scoped** eligibility flags materialised in S0, and
* the accepted $N_m$ from S2,

and produces an **in-memory** bundle for S3.2. **No datasets are written** and **no RNG is consumed** in S3.1.

---

## 2) Authoritative contracts (what we read, exactly)

### 2.1 Ingress merchant record (canonical)

Read the following columns from the **ingress** table referenced by `schemas.ingress.layer1.yaml#/merchant_ids`:

* `merchant_id:int64` (PK)
* `mcc:int32`
* `channel:string ∈ {"card_present","card_not_present"}`
* `home_country_iso: ISO-3166-1 alpha-2` (FK to canonical ISO)

> **Notes.** Channel values are the two enumerants above (not “CP/CNP” strings); the ISO code must be uppercase `[A–Z]{2}` and FK-valid against the canonical ISO list defined in your ingress schema.

### 2.2 Eligibility flags (parameter-scoped, produced in S0)

Read **exactly one** row per merchant from:

```
data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/
  schema_ref: schemas.1A.yaml#/prep/crossborder_eligibility_flags
  partition_keys: ["parameter_hash"]
```

Required columns:
`merchant_id`, `is_eligible:boolean`, `rule_set:string (non-null)`, `reason:string|null`. This table is the **single source of truth** for the S3 gate; it is **parameter-scoped** (filtered by the **current** `{parameter_hash}`).

### 2.3 Accepted outlet count from S2 (multi-site only)

S2’s state boundary provides the accepted **NB** outlet count:

$$
\boxed{\,N_m \in \{2,3,\dots\}\,}
$$

and emits an RNG event `nb_final` (exactly 1 row per merchant) in:

```
logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…
  schema_ref: schemas.layer1.yaml#/rng/events/nb_final
```

S3.1 **does not** read the event payloads, but **requires** that the merchant has passed S2 (presence of exactly one `nb_final` row) to enter S3.

### 2.4 Lineage keys (carried through)

* `parameter_hash` (parameter scope; partitions the flags table and most 1A caches), and
* `manifest_fingerprint` (run scope; used later on persisted outputs like `country_set` and for validator joins).

---

## 3) Preconditions (MUST hold before S3.1 binds)

1. **Multi-site only.** Merchant must have `is_multi=1` from S1 and a valid S2 acceptance: `count_rows(nb_final where merchant_id=m) == 1` under the current `seed, parameter_hash, run_id`. Otherwise abort `E_NOT_MULTISITE_OR_MISSING_S2`.
2. **Ingress schema conformance.** The projected columns must conform to `schemas.ingress.layer1.yaml#/merchant_ids` (reject unknown enumerants; enforce ISO pattern).
3. **Flags partition ready.** A **single** row for `(parameter_hash, merchant_id)` **must** exist in `crossborder_eligibility_flags` (see §4.2 invariants). S3 reads **after** S0 has committed the partition.

---

## 4) Determinism, invariants, and FK truths

* **No-RNG invariant.** S3.1 consumes **no** RNG streams; it is a pure function of ingress + parameter-scoped flags + S2 acceptance.
* **I-S3.1-Uniq.** Exactly **one** flags row exists per `(parameter_hash, merchant_id)`. Missing or duplicate rows are structural errors.
* **I-S3.1-Schema.** `is_eligible` is **boolean**; `rule_set` is **non-null**; `reason` may be null. Enforced by `schemas.1A.yaml`.
* **I-S3.1-ISO-FK (for later S6 write).** `home_country_iso` must be FK-valid against the canonical ISO table referenced in the ingress schema; this anticipates the FK of `alloc/country_set.columns.country_iso`.

---

## 5) Canonical materialisation procedure (normative)

**Inputs (to this sub-state):**
`merchant_id, mcc, channel, home_country_iso` (ingress); `parameter_hash`, `manifest_fingerprint`; `N_m` (from S2).

**Output (in-memory for S3.2):**
`S3_inputs = { merchant_id, home_country_iso, mcc, channel, N_m, flags_row = (is_eligible, rule_set, reason), parameter_hash, manifest_fingerprint }`.

**Algorithm (reference pseudocode, language-agnostic):**

```pseudo
function s3_1_bind_inputs(m: MerchantID,
                          seed: int64,
                          parameter_hash: hex64,
                          run_id: uuid) -> S3Inputs:
    # 1) Verify S2 acceptance (multi-site)
    nb_ok := count_rows(
              from logs/rng/events/nb_final
              where merchant_id = m
                and seed = seed
                and parameter_hash = parameter_hash
                and run_id = run_id) == 1
    if not nb_ok:
        abort E_NOT_MULTISITE_OR_MISSING_S2(m)

    # 2) Read ingress projection (strict schema)
    (mid, mcc, channel, c) := select merchant_id, mcc, channel, home_country_iso
                              from ingress.merchant_ids
                              where merchant_id = m
    assert channel in {"card_present","card_not_present"}      # schema enum
    assert iso2_regex_match(c) and fk_iso2_exists(c)            # ingress FK

    # 3) Lookup the parameter-scoped eligibility row
    rows := select merchant_id, is_eligible, rule_set, reason
            from data.layer1.1A.crossborder_eligibility_flags
            where parameter_hash = parameter_hash
              and merchant_id = m
    if len(rows) == 0: abort E_FLAGS_MISSING(m)
    if len(rows) >  1: abort E_FLAGS_DUPLICATE(m)
    row := rows[0]
    assert typeof(row.is_eligible) == BOOLEAN
    assert row.rule_set is not NULL

    # 4) Bind and return the in-memory bundle (no writes here)
    return {
      merchant_id: mid,
      home_country_iso: c,
      mcc: mcc,
      channel: channel,
      N: read_S2_N(m),                         # carried context
      flags: {is_eligible: row.is_eligible,
              rule_set: row.rule_set,
              reason: row.reason},
      parameter_hash: parameter_hash,
      manifest_fingerprint: current_manifest_fingerprint()
    }
```

**Joins/keys (MUST use):**

* RNG event presence check (S2 acceptance): join on `(merchant_id, seed, parameter_hash, run_id)` to `rng_event_nb_final`.
* Flags lookup: equality on `(parameter_hash, merchant_id)` into `crossborder_eligibility_flags`.

---

## 6) Failure taxonomy (detected in S3.1; all are **abort**)

* `E_NOT_MULTISITE_OR_MISSING_S2(m)` — Missing `nb_final` acceptance or merchant is not multi-site; S3 is undefined for single-site merchants (bypass S2–S6 by journey spec).
* `E_FLAGS_MISSING(m)` — No row in `crossborder_eligibility_flags/parameter_hash={parameter_hash}` for `merchant_id=m`.
* `E_FLAGS_DUPLICATE(m)` — >1 row for `(parameter_hash, merchant_id)`; violates I-S3.1-Uniq.
* `E_INGRESS_SCHEMA(channel|home_country_iso)` — Channel not in enum or ISO not FK-valid per ingress schema.

Each abort MUST surface a minimal diagnostic payload including the probed keys and the dictionary pointer (dataset id + `schema_ref`) to guide operators.

---

## 7) Observability (structured log; optional, non-authoritative)

Emit one **system log** record per merchant to assist incident response (validator does **not** rely on this):

```
logs/system/eligibility_gate.v1.jsonl
{ event: "s3_inputs_bound",
  merchant_id, parameter_hash, manifest_fingerprint,
  ingress: {mcc, channel, home_country_iso},
  flags: {is_eligible, rule_set, reason},
  N_from_S2: N }
```

This mirrors what will feed S3.2 and lets ops diff a problematic merchant quickly. (Dataset dictionary already pins authoritative tables/streams; this system log is just a convenience.)

---

## 8) Conformance tests (suite skeleton)

1. **Happy path.** Given ingress row with `channel="card_present"`, valid ISO; flags table contains **one** row `{is_eligible=true, rule_set="default_v1", reason=null}` under the current `{parameter_hash}`; exactly one `nb_final` event exists → **bind succeeds** and returns the bundle.
2. **Missing flags.** Remove the flags row for that merchant under the current `{parameter_hash}` → **abort `E_FLAGS_MISSING`**.
3. **Duplicate flags.** Duplicate the row (same `merchant_id`, same `parameter_hash`) → **abort `E_FLAGS_DUPLICATE`**.
4. **Wrong channel literal.** Set `channel="CP"` in ingress (violates enum) → **abort `E_INGRESS_SCHEMA(channel)`**.
5. **Single-site merchant.** Remove `nb_final` for the merchant (or set S1 to `is_multi=0`) → **abort `E_NOT_MULTISITE_OR_MISSING_S2`**.
6. **ISO FK failure.** Set `home_country_iso="UK"` (not an ISO-2) → **abort `E_INGRESS_SCHEMA(home_country_iso)`**.

---

## 9) Complexity & performance

S3.1 performs O(1) lookups per merchant: one key read in ingress, one partition-filtered point lookup in `crossborder_eligibility_flags`, and an existence check against `nb_final`. All I/O is **parameter-scoped** or **run-scoped** via partitions specified in the dictionary, so lookups are index-friendly.

---

## 10) Outputs (to S3.2)

S3.1 produces an **in-memory** structure (no persistence):

```
{ merchant_id,
  home_country_iso,
  mcc, channel,
  N,                                  # accepted in S2
  flags: {is_eligible, rule_set, reason},
  parameter_hash,
  manifest_fingerprint }
```

This becomes the input to **S3.2 (eligibility function & branch)**, where the gate indicator `e_m` is read from `flags.is_eligible` and mapped to the branch tag (eligible → S4, ineligible → S7).

---

# S3.2 — Eligibility function & deterministic branch decision (no RNG)

## 1) Purpose & scope (normative)

This sub-state **decides the branch** for each multi-site merchant $m$: either **eligible for cross-border** (proceed to S4) or **domestic-only** (skip S4–S6, go to S7). The decision is **purely deterministic** and sourced from the **parameter-scoped** table `crossborder_eligibility_flags` materialised in S0; S3.2 **does not** perform any RNG draws or dataset writes.

**Predecessor:** S3.1 completed and provided an in-memory bundle:

```
S3_inputs = {
  merchant_id, home_country_iso, mcc, channel, N,
  flags: {is_eligible, rule_set, reason},
  parameter_hash, manifest_fingerprint
}
```

where `channel ∈ {"card_present","card_not_present"}`, `home_country_iso` is ISO2, and exactly one flags row exists under the current `parameter_hash`.

---

## 2) Formal definition (policy set and indicator)

Let $\mathcal{I}$ be the canonical ISO-3166-1 alpha-2 code set (uppercase). Let the **governed rule family** be a fixed set:

$$
\mathcal{E}\ \subseteq\ \underbrace{\mathbb{N}}_{\text{MCC}}\ \times\ \underbrace{\{\texttt{card_present},\texttt{card_not_present}\}}_{\text{channel}}\ \times\ \underbrace{\mathcal{I}}_{\text{home ISO-2}},
$$

defined entirely by configuration and compiled in S0 into `crossborder_eligibility_flags` (all such artefacts are included in the `parameter_hash`).

For merchant $m$ with features $(\texttt{mcc}_m,\texttt{channel}_m,\texttt{home_country_iso}_m=c\in\mathcal{I})$, define the **eligibility indicator**:

$$
\boxed{\ e_m\;=\;\mathbf{1}\Big\{(\texttt{mcc}_m,\texttt{channel}_m,c)\in\mathcal{E}\Big\}\ }.
$$

In practice, $e_m$ is read as the boolean `flags.is_eligible` from the parameter-scoped table `crossborder_eligibility_flags` for the current `parameter_hash`; S3.2 **does not recompute** $e_m$.

---

## 3) Inputs (authoritative sources)

* **Flags row (parameter-scoped):**
  `data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/`, schema `schemas.1A.yaml#/prep/crossborder_eligibility_flags`.
  Required columns: `merchant_id, is_eligible:boolean, rule_set:string (non-null), reason:string|null`. **Exactly one row** per `(parameter_hash, merchant_id)`.

* **Ingress fields (validated in S3.1):**
  `mcc:int32`, `channel ∈ {"card_present","card_not_present"}`, `home_country_iso: ISO2`. Schema: `schemas.ingress.layer1.yaml#/merchant_ids`.

* **S2 acceptance evidence (precondition):**
  Exactly one RNG event `nb_final` exists for the merchant under `(seed, parameter_hash, run_id)`. Schema: `schemas.layer1.yaml#/rng/events/nb_final`.

---

## 4) Preconditions (MUST hold before decision)

1. **Multi-site branch:** Merchant has S1 `is_multi=true` and S2 acceptance: `count_rows(nb_final where merchant_id=m and seed,parameter_hash,run_id match) == 1`. Else abort `E_NOT_MULTISITE_OR_MISSING_S2`.
2. **Unique flags row:** Exactly one row in `crossborder_eligibility_flags` for `(parameter_hash, merchant_id)`. Else `E_FLAGS_MISSING`/`E_FLAGS_DUPLICATE`.
3. **Schema conformance:** `is_eligible` is boolean; `rule_set` non-null; `reason` nullable. Else `E_FLAGS_SCHEMA`.
4. **Ingress conformance:** `channel` matches the ingress enum and `home_country_iso` is valid ISO2 (already enforced in S3.1).

---

## 5) Branch function (normative)

Define the **gate**:

$$
\boxed{\ \text{if } e_m\!=\!1\Rightarrow \text{branch}=\texttt{eligible},\quad \text{else } \texttt{domestic_only}. }
$$

* **Eligible branch** $(e_m=1)$: S4 will compute a foreign country **count** $K_m\ge 1$ via ZTP, then S6 will select and order foreign ISOs; later, S7 integerises across the ordered countries; `country_set` will persist order (rank 0 = home).
* **Domestic-only branch** $(e_m=0)$: Skip S4–S6; downstream S7 will allocate all $N_m$ domestically; eventual `country_set` will contain only the home ISO with `rank=0`. `country_set` remains the **only** authority for cross-country order.

---

## 6) Determinism & validator hooks (evidence wiring)

**No-RNG invariant.** S3.2 **consumes no RNG**; its output is a pure function of `(merchant_ids projection, crossborder_eligibility_flags)` under the current `parameter_hash`.

**Branch coherence rules (checked by S9 using event streams):**

* If `e_m==0` (**domestic-only**) ⇒ there MUST be **no** S4–S6 RNG events for $m$ under the same `(seed, parameter_hash, run_id)`:

  * `poisson_component` with `context="ztp"`,
  * `ztp_rejection`,
  * `ztp_retry_exhausted`,
  * `gumbel_key`,
  * `gamma_component` with `context="dirichlet"`,
  * `dirichlet_gamma_vector`.
    Violation ⇒ `F_EL_BRANCH_INCONSISTENT`.

* If `e_m==1` (**eligible**) ⇒ there MUST be evidence of entering S4 or an explicit exhaustion:

  * Presence of at least one `poisson_component` (context=`"ztp"`) **or** a `ztp_retry_exhausted` record for $m$.
    The exact joining keys are `(merchant_id, seed, parameter_hash, run_id)` plus the event’s `context` where applicable.

**Why these streams?** Paths/schemas for all referenced events are fixed by the **dataset dictionary** and **layer schemas** (see ids `rng_event_poisson_component`, `rng_event_ztp_rejection`, `rng_event_ztp_retry_exhausted`, `rng_event_gumbel_key`, `rng_event_dirichlet_gamma_vector`).

---

## 7) Procedure (reference pseudocode; language-agnostic)

```pseudo
function s3_2_decide_gate(inputs: S3Inputs) -> S3Branch:
    # Preconditions (S3.1 already enforced; re-check defensively)
    assert inputs.flags is not null
    assert typeof(inputs.flags.is_eligible) == BOOLEAN
    assert inputs.flags.rule_set is not NULL

    # 1) Read the indicator from flags (no recomputation)
    e := inputs.flags.is_eligible        # boolean

    # 2) Decide the branch (deterministic)
    if e == true:
        branch := "eligible"             # proceed to S4
    else:
        branch := "domestic_only"        # skip S4-S6 → S7

    # 3) Prepare minimal export for S3.3/S4/S7 (in-memory only)
    export := {
        merchant_id: inputs.merchant_id,
        e: e,
        rule_set: inputs.flags.rule_set,
        reason:  inputs.flags.reason,    # MUST be NULL when e==true (policy)
        home_country_iso: inputs.home_country_iso,
        mcc: inputs.mcc,
        channel: inputs.channel,
        N: inputs.N,
        parameter_hash: inputs.parameter_hash,
        manifest_fingerprint: inputs.manifest_fingerprint,
        branch: branch
    }
    return export
```

**Policy note (reason field).** If `e==true` then `reason MUST be NULL`; if `e==false` then `reason` SHOULD be one of the governed codes (e.g., `"mcc_blocked"`, `"cnp_blocked"`, `"home_iso_blocked"`). Enforced by the compiler that produced `crossborder_eligibility_flags`; S3.2 treats it as an assertion.

---

## 8) Failure taxonomy (detected at/around S3.2)

* `E_NOT_MULTISITE_OR_MISSING_S2` — Missing S2 `nb_final` acceptance or merchant is not multi-site. (Precondition)
* `E_FLAGS_MISSING` / `E_FLAGS_DUPLICATE` — No/duplicate flags row for `(parameter_hash, merchant_id)`. (Precondition)
* `E_FLAGS_SCHEMA` — Type/NULLability violation on `is_eligible`/`rule_set`/`reason` vs schema.
* `F_EL_BRANCH_INCONSISTENT` (validator) — Evidence of S4–S6 RNG events for an `e==0` merchant, or absence of any S4 evidence for `e==1` merchants (no `poisson_component(context="ztp")` and no `ztp_retry_exhausted`). Evidence joins: `(merchant_id, seed, parameter_hash, run_id)`.

Each abort MUST include diagnostics: `(merchant_id, parameter_hash, run_id)`, dataset id + `schema_ref`, and the failing invariant id (e.g., `I-EL-Uniqueness`, `I-EL-Branch`).

---

## 9) Observability (optional, non-authoritative system log)

Emit (optionally) to `logs/system/eligibility_gate.v1.jsonl` a single record per merchant:

```json
{ "event":"s3_decision",
  "merchant_id": ..., "parameter_hash":"...", "manifest_fingerprint":"...",
  "e": true|false, "rule_set":"...", "reason": null|"mcc_blocked",
  "branch":"eligible"|"domestic_only" }
```

Validators do **not** rely on this log; it is for incident response only. (Authoritative sources remain the flags table and RNG streams listed above.)

---

## 10) Conformance tests (suite skeleton)

1. **Eligible path (happy).** Flags row has `is_eligible=true`, `reason=NULL`. S3.2 returns `branch="eligible"`. Downstream presence of `poisson_component(context="ztp")` or `ztp_retry_exhausted` satisfies validator hook. **Pass.**
2. **Domestic-only path (happy).** Flags row `is_eligible=false`, `reason="mcc_blocked"`. No downstream S4–S6 RNG events exist for the merchant. **Pass.**
3. **Branch inconsistency (negative).** Flags `is_eligible=false`, but a `gumbel_key` row exists under the same `(seed, parameter_hash, run_id)` → Validator raises `F_EL_BRANCH_INCONSISTENT`. **Fail.**
4. **Missing flags (negative).** No row under current `parameter_hash` → `E_FLAGS_MISSING`. **Fail.**
5. **Schema violation (negative).** `rule_set=NULL` in flags row → `E_FLAGS_SCHEMA`. **Fail.**

---

## 11) Complexity & performance

Per merchant, S3.2 performs **no I/O** beyond what S3.1 already did (flags row read) and **no RNG**; it is O(1) time/space and trivially parallelisable across merchants.

---

## 12) Outputs (to S3.3)

S3.2 returns an **in-memory** export:

```
{ merchant_id, e, rule_set, reason, home_country_iso, mcc, channel,
  N, parameter_hash, manifest_fingerprint, branch }
```

S3.3 will initialise the ordered country-set container $\mathcal{C}_m$ with `rank 0 = home`, and either reserve it for foreign selection (eligible) or fix domestic-only (ineligible); **`country_set`** later persists the order and remains the **only** authority for cross-country rank.

---

# S3.3 — Country-set container initialisation (deterministic, no RNG)

## 1) Purpose & scope (normative)

Create, per merchant $m$, an **in-memory, ordered, duplicate-free** container $\mathcal{C}_m$ of ISO-2 country codes that:

* anchors **home** at **rank 0** **now**,
* is **appended to** (never reordered) by S4–S6, and
* will be **persisted only after S6** as `alloc/country_set`, the **sole authority** for inter-country order (`rank: 0=home; 1..K` for foreigns).

S3.3 **performs no writes** and **consumes no RNG**. It defines the container and routes control either to S4 (eligible) or to S7 (domestic-only). Inter-country order is **not** and will not be encoded in egress; consumers (including 1B) **must** join `country_set.rank`.

---

## 2) Inputs (from S3.2; authoritative)

From S3.2 we receive (in-memory):

```
{ merchant_id, e, rule_set, reason, home_country_iso=c,
  mcc, channel, N, parameter_hash, manifest_fingerprint, branch }
```

Contracts already enforced in S3.1–S3.2:

* `e:boolean` is read from `crossborder_eligibility_flags` (parameter-scoped, exactly one row per `(parameter_hash, merchant_id)`), and `channel ∈ {"card_present","card_not_present"}`.
* `home_country_iso=c` is uppercase ISO-3166-1 alpha-2 and FK-valid against the canonical ISO dataset referenced by your schemas.

---

## 3) Formal definition (container, rank function, mapping)

Let $\mathcal{I}$ be the canonical ISO-2 universe (uppercase letters). Define the **country-set container** for merchant $m$:

$$
\boxed{\ \mathcal{C}_m = (c_0, c_1, \dots, c_{K_m})\ \ \text{with}\ \ c_i \in \mathcal{I},\ \ c_i \neq c_j\ (i\neq j)\ },
$$

and a rank function $\mathrm{rank}_{\mathcal{C}_m}(c_i) = i$. By construction, $c_0$ is **home**. Persistence (after S6) maps position $i$ to a row in `country_set`:

$$
(\texttt{merchant_id}=m,\ \texttt{country_iso}=c_i,\ \texttt{is_home}=\mathbf{1}\{i=0\},\ \texttt{rank}=i).
$$

`country_set` is partitioned by `seed, parameter_hash`, has PK `(merchant_id, country_iso)`, and encodes inter-country order **only** via `rank`. ISO values are FK-validated against the canonical ingress ISO table.

---

## 4) Preconditions (MUST hold before S3.3 runs)

1. **Branch decision available.** S3.2 completed; `e ∈ {true,false}` with `rule_set` non-null; `reason` is null iff `e==true`. (S3.2 invariant.)
2. **Home ISO FK.** `c ∈ \mathcal{I}` and passes the ISO FK referenced by schema.
3. **No RNG.** S3.3 may not read or write RNG streams; any S4–S6 events for a merchant with `e==false` constitute a **branch inconsistency** caught later by validation.

---

## 5) Deterministic procedure (normative, reference pseudocode)

```pseudo
# S3.3 — country-set container initialisation
# Inputs (from S3.2): merchant_id=m, e, home_country_iso=c,
#                     N, parameter_hash, manifest_fingerprint, branch
# Output (in-memory): CountryInit {
#    merchant_id, C, K, home_country_iso, e, next_state,
#    parameter_hash, manifest_fingerprint
# }

function s3_3_init_country_container(inputs: S3Export) -> CountryInit:
    assert iso2_fk_valid(inputs.home_country_iso)        # schema FK
    C := []                                              # empty ordered list
    C.append(inputs.home_country_iso)                    # rank 0 reserved, duplicate-free by construction

    if inputs.e == false:                                # domestic-only
        K := 0
        next_state := "S7"                               # bypass S4–S6
    else:                                                # eligible
        K := ⊥                                           # unknown here; determined by S4
        next_state := "S4"

    return {
      merchant_id: inputs.merchant_id,
      C: C,                                             # e.g. ["GB", ...] (currently length 1)
      K: K,                                             # 0 or ⊥ (unknown)
      home_country_iso: inputs.home_country_iso,
      e: inputs.e,
      next_state: next_state,
      parameter_hash: inputs.parameter_hash,
      manifest_fingerprint: inputs.manifest_fingerprint
    }
```

**Container rules (MUST).**

* **Append-only** thereafter (S4–S6) in **strict order**; `C[0]` must **never** change or be duplicated.
* **Duplicate prohibition:** before any append, assert the candidate is not already in `C`.
* **Stable ordering:** no reordering or deletion is allowed in S4–S6; persistence after S6 writes one row per position with `rank=i`.

---

## 6) Determinism & evidence (validator hooks)

* **No-RNG invariant (S3).** S3 states (3.1–3.3) do **not** emit RNG events. For `e==false` merchants, S9 will assert **absence** of S4–S6 events `poisson_component(context="ztp")`, `ztp_*`, `gumbel_key`, `dirichlet_gamma_vector` under the same `(merchant_id, seed, parameter_hash, run_id)`. Violation ⇒ `F_EL_BRANCH_INCONSISTENT`.
* **Country-set shape at write-time.** After S6, `country_set` **must** contain exactly one home row `(is_home=true, rank=0)` and, if eligible, a **contiguous** set of foreign ranks $\{1,\dots,K_m\}$ with no gaps/dupes; membership & order of foreigns must equal the **Top-K by Gumbel key** from S6. (Checked in S9.)
* **Inter-country order locality.** Egress `outlet_catalogue` will **not** encode inter-country order; any consumer must recover it by joining `country_set.rank`. (S9 asserts this schema separation.)

---

## 7) Failure taxonomy (detected at S3.3; all **abort**)

* `E_HOME_ISO_INVALID(m)` — `home_country_iso` fails ISO FK. (Schema-level FK referenced by `country_set`/`outlet_catalogue` contracts.)
* `E_CONTAINER_DUP_HOME(m)` — defensive: container already has non-empty contents before initialisation (should not happen in a correct runner; treat as bug and abort).
* `E_BRANCH_UNSET(m)` — defensive: S3.2 did not supply `e ∈ {true,false}`.

> **Note:** There are **no** persistence-time failures in S3.3 (no writes). Branch-consistency failures are caught during S9 (presence/absence of S4–S6 RNG events vs `e`).

---

## 8) Persistence mapping (for later S6 writer; normative contract)

When S6 completes foreign selection, persist `C` into `country_set`:

```
path: data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/
schema_ref: schemas.1A.yaml#/alloc/country_set
PK: ["merchant_id","country_iso"]; columns include {is_home:boolean, rank:int32, prior_weight:float64?}
```

`country_set` is **the ONLY** authoritative store of cross-country order; 1B and egress readers **must** join it for order. (The dictionary and schema encode and document that rule.)

---

## 9) Interactions & separations (why this matters)

* **S7 integerisation** will use the ordered `country_set` (home then foreigns) as the **prior** ordering for largest-remainder tie-breaks (`country_set.rank` appears as a secondary key in the residual sort). This keeps S6’s Gumbel order stable through integerisation.
* **S8 egress** writes `(merchant_id, legal_country_iso, site_order)` only; inter-country order is intentionally absent and must be joined from `country_set.rank`.

---

## 10) Conformance tests (suite skeleton)

1. **Domestic-only anchor.** Given `e=false`, `c="GB"`, run S3.3 → `C=["GB"]`, `K=0`, `next_state="S7"`. Later, `country_set` for $m$ must contain exactly one row `{is_home=true, rank=0, country_iso="GB"}`. **Pass.**
2. **Eligible anchor.** Given `e=true`, `c="US"`, run S3.3 → `C=["US"]`, `K=⊥`, `next_state="S4"`. After S6, `country_set` must show `("US", rank=0)` and foreign ranks `1..K_m` contiguous. **Pass.**
3. **No RNG invariant.** For `e=false`, ensure zero events exist in `gumbel_key`, `dirichlet_gamma_vector`, or `poisson_component(context="ztp")` for $m$ under the same `(seed, parameter_hash, run_id)`; else `F_EL_BRANCH_INCONSISTENT`. **Pass if absent, fail if present.**
4. **ISO FK negative.** Set `c="UK"`; FK fails → `E_HOME_ISO_INVALID`. **Fail.**
5. **Duplicate append negative (defensive).** Simulate S6 trying to append `c` again; append must be rejected before persistence. **Fail scenario; runner bug.** (Policy: abort before write.)

---

## 11) Complexity & performance

O(1) per merchant (create a one-element array and set two scalars). Trivially parallelisable; zero I/O, zero RNG. The only I/O will occur later at S6 persistence.

---

## 12) Output (to next state)

S3.3 produces an **in-memory** structure:

```
CountryInit {
  merchant_id, C=(c0=home), K (0 or ⊥),
  home_country_iso, e, next_state ∈ {"S4","S7"},
  parameter_hash, manifest_fingerprint
}
```

* If `e==true` → **S4** (ZTP to determine $K_m\ge1$).
* If `e==false` → **S7** (deterministic domestic allocation with `C=(c)` only).
  The eventual `country_set` write (after S6) uses `seed` and `parameter_hash` partitions and the schema `#/alloc/country_set`; egress continues to rely on `country_set.rank` for inter-country order.

---

# S3.4 — Determinism, lineage, and validator hooks (no RNG)

## 1) Purpose & scope (normative)

S3 is a **deterministic gate**. S3.4 formalises:

* the **lineage model** (which keys scope data vs. logs),
* the **no-RNG invariant** for S3,
* the **evidence contracts** S9 will use to prove S3’s decision is consistent with downstream behaviour (presence/absence of S4–S6 RNG events), and
* the **failure taxonomy** & **conformance probes** tied to your dictionary & schemas.

S3.4 **reads/writes no datasets** and **consumes no RNG**; it is a specification layer binding S3 to validation.

---

## 2) Lineage model (keys, scopes, partitions)

**Keys and scopes (normative):**

* `parameter_hash` — **parameter scope** (what governs the modelling configuration). All parameter-scoped datasets (e.g., `crossborder_eligibility_flags`, `country_set`, `ranking_residual_cache_1A`) partition by this key and embed it in row metadata. Defined in S0 via double-SHA256 over the governed parameter set.
* `manifest_fingerprint` — **run/egress scope** (the complete artefact universe + git + parameter hash). All egress and validation artefacts (e.g., `outlet_catalogue`, validation bundle) bind to this key; it is embedded in rows.
* `seed` — RNG universe key for the whole run; partitions RNG event logs and later alloc artefacts that are seed-dependent.
* `run_id` — **logs-only** execution id (not a modelling input). Partitions RNG logs and audit trails; must not influence results.

**Partitioning contracts (from dictionary/spec):**

* Parameter-scoped dataset example:
  `data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/` (schema `#/prep/crossborder_eligibility_flags`).
* RNG events (logs):
  `logs/rng/events/<label>/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` (schema `schemas.layer1.yaml#/rng/events/<label>`).
* Validation bundle & hand-off gate to 1B bind to `{manifest_fingerprint}` and must pass `_passed.flag == SHA256(bundle)`.

---

## 3) No-RNG invariant & replay posture

**I-EL1 (No RNG in S3).** Sub-states **S3.1–S3.3** execute **zero** random draws. Their outputs are a pure function of:

$$
\big(\text{merchant_ids projection},\ \text{crossborder_eligibility_flags[parameter_hash]},\ N_m \text{ from S2}\big),
$$

under fixed `(seed, parameter_hash, manifest_fingerprint)`; S3 is therefore **bit-replayable** by data alone. (S2’s acceptance is evidenced by exactly one `nb_final` event.)

---

## 4) Evidence contracts for S9 (presence/absence rules)

S9 must be able to **prove** that S3’s branch decision

$$
\boxed{\ \text{branch}_m = \begin{cases}
\texttt{eligible} & \text{if } e_m=1,\\
\texttt{domestic_only} & \text{if } e_m=0
\end{cases}}
$$

is **consistent** with downstream stochastic activity (S4–S6), using only logs & datasets, joined on `(merchant_id, seed, parameter_hash, run_id)`.

### 4.1 Event streams (authoritative IDs & schemas)

The following RNG event streams are authoritative for S4–S6 (as per dictionary & layer schemas):

* **ZTP (S4):**
  `rng_event_poisson_component` (`context="ztp"`), `rng_event_ztp_rejection`, `rng_event_ztp_retry_exhausted`.
* **Selection (S6):**
  `rng_event_gumbel_key` (Gumbel-top-k keys).
* **Dirichlet weights (S7 pre-integerisation evidence):**
  `rng_event_dirichlet_gamma_vector`. (S3 itself doesn’t run S7, but absence/presence rules refer to this for e==0 coherence.)

Each stream partitions by `["seed","parameter_hash","run_id"]` and uses a fixed JSON-Schema under `schemas.layer1.yaml#/rng/events/<label>`.

### 4.2 Coherence rules (normative)

* **I-EL3-DOM (domestic-only coherence).** If `e_m == false`, then **no** S4–S6 events may exist for merchant $m$ under the same `(seed, parameter_hash, run_id)`:

  $$
  \forall \ell \in \{\texttt{poisson_component (ztp)},\ \texttt{ztp_rejection},\ \texttt{ztp_retry_exhausted},\ \texttt{gumbel_key},\ \texttt{dirichlet_gamma_vector}\}:\ \ |T_\ell(m)| = 0.
  $$

  In addition, when `|C| = 1` (which holds for the domestic-only branch), S7 MUST NOT emit `gamma_component(context="dirichlet")`. Any presence of these events ⇒ `F_EL_BRANCH_INCONSISTENT`.

* **I-EL3-ELIG (eligible coherence).** If `e_m == true`, then S4 must be entered; S9 must find **at least one** `poisson_component` with `context="ztp"` **or** a terminal `ztp_retry_exhausted` record (when the configured retry policy exhausts). Absence of both ⇒ **`F_EL_BRANCH_INCONSISTENT`**.

* **I-EL2 (flags uniqueness & schema).** For each `(parameter_hash, merchant_id)` there is **exactly one** row in `crossborder_eligibility_flags` with `is_eligible:boolean`, `rule_set:non-null`, `reason:nullable`. Missing/duplicate/typedrift ⇒ **structural fail**.

* **I-EL4 (home ISO FK guard).** `home_country_iso ∈ ISO-3166 alpha-2` (canonical FK target) — enforced before any persistence of `country_set`. (S3 checks eagerly; S9 re-asserts FK at `country_set` write.)

**Note.** S2 acceptance is evidenced by exactly one `nb_final` event per merchant under the same `(seed, parameter_hash, run_id)`; S3 operates only on such merchants.

---

## 5) Join semantics (how validators link evidence)

Validators MUST join on:

$$
(\texttt{merchant_id},\ \texttt{seed},\ \texttt{parameter_hash},\ \texttt{run_id})
$$

with any additional event qualifiers (e.g., `context="ztp"` for `poisson_component`). The join domain is the set of merchants with S2 acceptance (`nb_final` present exactly once). This guarantees per-run, per-universe accounting, and avoids cross-run leakage.

---

## 6) Structured invariants (validator-facing)

For each merchant $m$ in the S3 domain:

* **I-EL1 (No RNG):** S3 emits no RNG events. (Enforced by the absence of any S3-labelled RNG streams; S9 reports counts in `rng_accounting.json`.)
* **I-EL2 (Flags uniqueness & schema):** exactly one flags row; conforms to `#/prep/crossborder_eligibility_flags`.
* **I-EL3 (Branch coherence):**
  **DOM** — absence of S4–S6 events; **ELIG** — presence of S4 evidence or explicit exhaustion.
* **I-EL4 (Home ISO FK):** home ISO in canonical list (anticipating `country_set.country_iso` FK to ingress ISO table).

S9 will **hard-fail** on any invariant breach; the bundle is produced with diagnostics but `_passed.flag` is not written.

---

## 7) Reference validator routine (normative, language-agnostic)

```pseudo
INPUT:
  Flags := read_table("crossborder_eligibility_flags", part={"parameter_hash"})
  NB    := read_log("rng_event_nb_final", part={"seed","parameter_hash","run_id"})
  ZTP   := union(
             read_log("rng_event_poisson_component").where(context="ztp"),
             read_log("rng_event_ztp_rejection"),
             read_log("rng_event_ztp_retry_exhausted")
           )
  SEL   := read_log("rng_event_gumbel_key")
  DIR   := read_log("rng_event_dirichlet_gamma_vector")
  ISO   := canonical_iso2_table()

# Domain: merchants admitted to S3 = S2-accepted ids
M3 := distinct(NB.merchant_id)

for m in M3:
  rows = Flags.lookup(parameter_hash, m)
  if |rows| != 1: fail("eligibility_flags_cardinality", m)   # I-EL2
  (e, rule_set, reason) = rows[0].is_eligible, rows[0].rule_set, rows[0].reason
  assert type(e)==BOOLEAN and rule_set != NULL               # I-EL2 schema

  # Coherence checks (I-EL3)
  if e == false:
     assert ZTP.none(m) and SEL.none(m) and DIR.none(m)
     else fail("branch_inconsistent_domestic", m)
  else:  # e == true
     assert ZTP.any(m) or ZTP.retry_exhausted(m)
     else fail("branch_inconsistent_eligible", m)

  # Home ISO FK (I-EL4); 'home' sourced from ingress join when persisting country_set
  assert ISO.contains(home_iso(m)) else fail("illegal_home_iso", m)

return PASS
```

*All `read_log` calls use partition filters and join keys `(merchant_id, seed, parameter_hash, run_id)` to ensure run-local accounting.*

**Accounting output.** The validator MUST summarise per-label presence/uniqueness counts by merchant in `rng_accounting.json`, embedded in the **validation bundle** and signed by `_passed.flag`.

---

## 8) Failure taxonomy (names, conditions, evidence)

* **`eligibility_flags_cardinality`** — 0 or >1 flags rows for `(parameter_hash, merchant_id)`; structural failure. Evidence: offending subset of `crossborder_eligibility_flags`.
* **`branch_inconsistent_domestic`** — `is_eligible=false` yet any of {`poisson_component(ztp)`, `ztp_rejection`, `ztp_retry_exhausted`, `gumbel_key`, `dirichlet_gamma_vector`} exist. Evidence: offending JSONL rows under their log paths. **Hard fail.**
* **`branch_inconsistent_eligible`** — `is_eligible=true` but S4 evidence is absent (no `poisson_component(ztp)`, no `ztp_retry_exhausted`). Evidence: zero-row proof under the same partitions. **Hard fail.**
* **`illegal_home_iso`** — Home ISO not in canonical set (pre-FK guard). Evidence: FK definition `#/alloc/country_set.columns.country_iso.fk` and the ingress ISO table id. **Hard fail.**

On any hard fail, S9 produces a bundle with diagnostics; `_passed.flag` is **not** written, and 1B MUST NOT consume egress for the fingerprint.

---

## 9) Optional observability (non-authoritative system log)

Runners **may** emit per-merchant S3 system logs to help incident response (validators don’t rely on them):

```
logs/system/eligibility_gate.v1.jsonl
{ event:"s3_decision",
  merchant_id, parameter_hash, manifest_fingerprint,
  e:true|false, rule_set, reason, branch:"eligible"|"domestic_only" }
```

These logs are **not** inputs to hashing or validation decisions.

---

## 10) Conformance tests (suite skeleton)

1. **Domestic-only coherence (pass).** Flags `is_eligible=false`; show **no** S4–S6 events under the same `(seed, parameter_hash, run_id)` → validator passes.
2. **Domestic-only inconsistency (fail).** Same as (1) but insert one `gumbel_key` row → `branch_inconsistent_domestic`.
3. **Eligible coherence via ZTP (pass).** Flags `is_eligible=true`; include at least one `poisson_component(context="ztp")` → validator passes.
4. **Eligible exhaustion (pass).** Flags `is_eligible=true`; include **no** `poisson_component(ztp)` but a `ztp_retry_exhausted` row → validator passes (entered S4, exhausted).
5. **Eligible inconsistency (fail).** Flags `is_eligible=true`; **no** ZTP evidence and **no** `ztp_retry_exhausted` → `branch_inconsistent_eligible`.
6. **Flags cardinality (fail).** Duplicate flags rows for a merchant → `eligibility_flags_cardinality`.
7. **ISO FK (fail).** Home ISO = `"UK"` (non-canonical) → `illegal_home_iso`.

---

## 11) Complexity & performance

Validator-side S3 evidence checks are dominated by keyed lookups in partitioned logs/tables; with indices on `(seed, parameter_hash, run_id, merchant_id)`, the presence/absence probes are O(1) per merchant per stream. Bundle generation includes a small accounting aggregation and a SHA256 compute for `_passed.flag`.

---

## 12) Outputs & hand-off relevance

S3.4 itself writes nothing. Its contracts are enforced downstream by **S9**, which:

* compiles **`validation_bundle_1A(fingerprint)`**,
* writes **`_passed.flag`** whose content hash equals `SHA256(bundle)`, and
* **authorises** 1B to read egress **only** when the flag matches the bundle for the same fingerprint.

All consumers needing inter-country order **must** join `country_set.rank`; egress does **not** encode cross-country order.

---

# S3.5 — Failure modes & operator playbook (normative, no RNG)

## 1) Scope

S3 is a **deterministic gate**. Its failures fall into two buckets:

* **Immediate S3 aborts** — stop the merchant **before** any S4–S6 work can occur (pure data/contract issues).
* **Validation hard-fails (S9)** — caught post-write by the validator using event presence/absence and cross-dataset checks; these **block** the 1A→1B hand-off (`_passed.flag` not written).

S3 never writes datasets; failures produce **diagnostic logs** and terminate the merchant’s path for the current run.

---

## 2) Error taxonomy (canonical IDs, locus, condition, evidence, remediation)

### Legend

* **Locus:** where it’s detected — `S3.1` (bind), `S3.2` (decide), `S9` (validator).
* **Join keys:** `(merchant_id, seed, parameter_hash, run_id)` for logs; `(merchant_id, parameter_hash)` for parameter-scoped tables.
* **Severity:** **Hard fail** stops bundle sign-off; **Soft warn** (none apply in S3).

---

### E_NOT_MULTISITE_OR_MISSING_S2  — *Immediate abort*

**Locus.** S3.1 precondition.
**Condition.** `count_rows(rng_event_nb_final where keys match) != 1`. (S3 domain is multi-site merchants with accepted NB draw.)
**Evidence.** Zero/duplicate `nb_final` events under `logs/rng/events/nb_final/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`. Schema `#/rng/events/nb_final`.
**Diagnostics payload.**

```json
{ "error":"E_NOT_MULTISITE_OR_MISSING_S2",
  "merchant_id": M, "seed": S, "parameter_hash": P, "run_id": R,
  "probe":{"stream":"nb_final","count":0|>1} }
```

**Remediation.** Ensure the S1 hurdle flagged multi-site and S2 wrote exactly one `nb_final`. Re-run S1–S3 for the merchant partition. (No RNG consumed in S3; re-runs are idempotent.)

---

### E_FLAGS_MISSING  — *Immediate abort*

**Locus.** S3.1 lookup.
**Condition.** No row in `crossborder_eligibility_flags` for `(parameter_hash, merchant_id)`.
**Evidence.** Empty result under `data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/`. Schema `#/prep/crossborder_eligibility_flags`.
**Diagnostics.**

```json
{ "error":"E_FLAGS_MISSING",
  "table":"crossborder_eligibility_flags",
  "parameter_hash": P, "merchant_id": M }
```

**Remediation.** (Re)build S0 flags for the active `{parameter_hash}`; verify PK coverage; re-run S3.

---

### E_FLAGS_DUPLICATE  — *Immediate abort*

**Locus.** S3.1 lookup.
**Condition.** >1 row in `crossborder_eligibility_flags` for `(parameter_hash, merchant_id)`.
**Evidence.** Duplicate rows under the same partition; violates I-EL2 uniqueness.
**Diagnostics.**

```json
{ "error":"E_FLAGS_DUPLICATE",
  "table":"crossborder_eligibility_flags",
  "parameter_hash": P, "merchant_id": M, "row_count": K }
```

**Remediation.** Deduplicate upstream flags (S0); enforce uniqueness constraint; re-run S3.

---

### E_FLAGS_SCHEMA  — *Immediate abort*

**Locus.** S3.2 guard (defensive), but typically caught by schema validation in S9 as well.
**Condition.** `is_eligible` not boolean or `rule_set` is NULL (schema contract breach).
**Evidence.** Row with wrong types/nullability against `schemas.1A.yaml#/prep/crossborder_eligibility_flags`.
**Diagnostics.**

```json
{ "error":"E_FLAGS_SCHEMA",
  "table":"crossborder_eligibility_flags",
  "parameter_hash": P, "merchant_id": M,
  "violations":["is_eligible:not_boolean","rule_set:null"] }
```

**Remediation.** Fix the compiler that writes flags; rebuild the partition under `{parameter_hash}`; re-run.

---

### E_HOME_ISO_INVALID (aka illegal_home_iso)  — *Immediate abort*

**Locus.** S3.1/S3.3 FK pre-guard.
**Condition.** `home_country_iso ∉ ISO-3166 alpha-2` canonical set referenced by the schema FK for `country_set.country_iso`.
**Evidence.** ISO lookup miss against the canonical ingress ISO table (schema FK target).
**Diagnostics.**

```json
{ "error":"E_HOME_ISO_INVALID",
  "merchant_id": M, "home_country_iso": "UK",
  "fk_target":"schemas.ingress.layer1.yaml#/iso3166_canonical_2024" }
```

**Remediation.** Correct ingress normalization/mapping to valid ISO-2 (e.g., `GB` vs `UK`); re-run S3.

---

### F_EL_BRANCH_INCONSISTENT  — *Validation hard-fail (S9)*

**Locus.** S9 (presence/absence proof).
**Condition.**

* Case A (domestic-only): `is_eligible=false` **but** any S4–S6 RNG events exist for $m$: `poisson_component(context="ztp")`, `ztp_rejection`, `ztp_retry_exhausted`, `gumbel_key`, `dirichlet_gamma_vector`.
* Case B (eligible): `is_eligible=true` **and** neither `poisson_component(context="ztp")` nor `ztp_retry_exhausted` exists.
  (Join on `(merchant_id, seed, parameter_hash, run_id)`, filter `context` where applicable.)
  **Evidence.** Offending JSONL rows (or zero-row proofs) under `logs/rng/events/...` partitions; flags row for the merchant; RNG accounting table inside the bundle.
  **Diagnostics (validator emits into bundle).**

```json
{ "fail":"F_EL_BRANCH_INCONSISTENT",
  "merchant_id": M, "seed": S, "parameter_hash": P, "run_id": R,
  "flags":{"is_eligible": false|true, "rule_set":"...", "reason": null|"mcc_blocked"},
  "rng_evidence":{
    "ztp_poisson_component": N1,
    "ztp_rejection": N2,
    "ztp_retry_exhausted": N3,
    "gumbel_key": N4,
    "dirichlet_gamma_vector": N5
  } }
```

**Remediation.**

* **A (domestic-only but events present):** fix runner to **bypass S4–S6** when `e=false`; purge stray RNG emissions for this `(seed,parameter_hash,run_id)`; re-run S3+validation.
* **B (eligible but no S4 evidence):** ensure S4 executes and logs ZTP events (or exhausts with `ztp_retry_exhausted`) for `e=true`; re-run.

---

## 3) Detection & joins (authoritative sources)

* **Flags table.** `data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/` — the **only** source of truth for `is_eligible`. Schema `#/prep/crossborder_eligibility_flags`. Uniqueness is a **must** (I-EL2).
* **RNG events.** `logs/rng/events/<label>/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…`, e.g., `poisson_component`, `ztp_*`, `gumbel_key`, `dirichlet_gamma_vector`. Validators must filter `context="ztp"` where shared (NB vs ZTP).
* **Validator artefacts.** `validation_bundle_1A(fingerprint)` with `rng_accounting.json` and diagnostics; `_passed.flag` content hash must equal `SHA256(bundle)` to authorise 1B.

---

## 4) Diagnostics (mandatory structure)

On any **immediate S3 abort**, emit one JSONL record to the system log (runner-side, non-authoritative):

```
logs/system/eligibility_gate.v1.jsonl
{
  "event":"s3_abort",
  "error": <ID>,
  "merchant_id": M,
  "parameter_hash": P,
  "manifest_fingerprint": F,
  "seed": S, "run_id": R,
  "dataset": "crossborder_eligibility_flags" | "rng_event_nb_final" | "ingress",
  "details": { … minimal, redaction-safe … },
  "ts_utc": "..."
}
```

Validators **do not** rely on this; authoritative evidence is the tables/log streams above and the bundle contents.

---

## 5) Operator playbook (step-by-step)

**(A) Flags missing/duplicate/schema (E_FLAGS_\*)**

1. Inspect the partition `…/crossborder_eligibility_flags/parameter_hash={P}/`.
2. Fix the S0 compiler (coverage, PK uniqueness, types).
3. Rebuild the partition and **re-run S3**; S3 is deterministic and idempotent.

**(B) Not multi-site / missing S2 (E_NOT_MULTISITE_OR_MISSING_S2)**

1. Check `nb_final` in `logs/rng/events/nb_final/seed={S}/parameter_hash={P}/run_id={R}/`.
2. If missing: re-run S1–S2; if duplicate: investigate runner re-entry/transactionality.
3. Re-run S3 after S2 acceptance exists exactly once.

**(C) Illegal ISO (E_HOME_ISO_INVALID)**

1. Verify `home_country_iso` against canonical ISO table (schema FK target).
2. Correct the ingress mapping (`UK→GB`, etc.).
3. Re-ingest, then re-run S3. (Prevents later FK failure at `country_set` write.)

**(D) Branch inconsistency (F_EL_BRANCH_INCONSISTENT)**

1. Open the bundle’s `rng_accounting.json` to see which stream tripped.
2. If `e=false` but ZTP/selection/Dirichlet events exist: update runner to **short-circuit** S4–S6 when `e=false`; purge stray logs.
3. If `e=true` but no S4 evidence: ensure S4 emits `poisson_component(context="ztp")` (or `ztp_retry_exhausted` according to policy).
4. Re-run S3→S9; `_passed.flag` will only be written once the bundle passes.

---

## 6) Idempotence & retries

* **S3 idempotence.** S3 uses **no RNG** and writes **no datasets**; repeating S3 with the same `(seed, parameter_hash, manifest_fingerprint)` and identical inputs yields identical decisions.
* **Validation retries.** Regenerating flags or fixing runner logic requires re-running S3→S9; 1B remains **locked out** until the new `validation_bundle_1A` is produced and `_passed.flag` matches the bundle digest for the same fingerprint.

---

## 7) Conformance tests (suite skeleton)

1. **E_FLAGS_MISSING.** Remove the flag row for merchant `M` → S3.1 aborts `E_FLAGS_MISSING`. **Pass if caught.**
2. **E_FLAGS_DUPLICATE.** Duplicate the row (same `M,P`) → S3.1 aborts `E_FLAGS_DUPLICATE`. **Pass if caught.**
3. **E_FLAGS_SCHEMA.** Set `rule_set=NULL` → S3.2 aborts `E_FLAGS_SCHEMA`. **Pass if caught.**
4. **E_HOME_ISO_INVALID.** Use `home_country_iso="UK"` → S3.1/S3.3 aborts. **Pass if caught.**
5. **F_EL_BRANCH_INCONSISTENT (domestic).** Flags `is_eligible=false` but emit a `gumbel_key` for `M` → S9 hard-fails; `_passed.flag` not written. **Pass if bundle shows failure.**
6. **F_EL_BRANCH_INCONSISTENT (eligible).** Flags `is_eligible=true` but zero ZTP evidence → S9 hard-fails. **Pass if bundle shows failure.**

---

## 8) Severity mapping to validation outputs

* **Hard fail (blocks hand-off):** any of the above errors surfaced in S9 or schema/PK/FK violations. The **bundle** still materialises with diagnostics, but `_passed.flag` is **not** written; 1B preflight must refuse egress.
* **Soft warn:** *none defined for S3*. (S9 has general numerical soft-warns for other states; not applicable here.)

---

## 9) Why this is safe

* Flags are **parameter-scoped**; identical `{parameter_hash}` ensures identical `e_m` across replays.
* S3 emits **no RNG**; all stochastic evidence lives in S4–S6 logs that the validator inspects via fixed schemas/paths.
* The **hand-off** to 1B is cryptographically gated by the validator via `_passed.flag == SHA256(bundle)` for the same `fingerprint`.

---

# S3.6 — Outputs (state boundary, deterministic, no RNG)

## 1) Purpose & scope (normative)

S3 is a **deterministic gate** that **writes no datasets** and **consumes no RNG**. S3.6 defines the **state boundary**: the *only* thing that leaves S3 is an **in-memory export** (per merchant) that carries the **branch decision**, the **seeded lineage**, and the **initialised country-set container** (home at rank 0). Persistence of cross-country order happens **later** in `alloc/country_set` after S6; egress `outlet_catalogue` remains **order-agnostic** and must be joined to `country_set.rank`.

---

## 2) Inputs to S3.6 (provenance recap; all already bound)

From S3.1–S3.3 (all **deterministic**, parameter/run scoped):

* `merchant_id:int64`
* `home_country_iso=c` (ISO-3166-1 alpha-2, FK-valid)
* `mcc:int32`, `channel ∈ {"card_present","card_not_present"}`
* `N:int32`, the accepted **NB** outlet count from S2 ($N\ge2$, evidenced by exactly one `nb_final`)
* `flags:{is_eligible:boolean, rule_set:string, reason:string|null}` from `crossborder_eligibility_flags/parameter_hash={parameter_hash}` (exactly one row per merchant)
* `e:boolean` ≡ `flags.is_eligible`
* `parameter_hash:hex64`, `manifest_fingerprint:hex64`, and `seed:uint64` carried as lineage keys for downstream partitioning/validation.

---

## 3) Formal outputs (per merchant) — **export object**

Define the S3 **export** (non-persisted, passed by value/reference to the next state):

```text
S3Export {
  merchant_id: int64,
  home_country_iso: string[ISO2],
  mcc: int32,
  channel: enum{"card_present","card_not_present"},
  N: int32,                         # accepted in S2 (N >= 2)
  e: boolean,                       # eligibility bit from flags
  rule_set: string (non-null),      # governed code from flags
  reason: string | null,            # MUST be null when e == true
  C: list[string[ISO2]],            # country-set container (ordered, dup-free)
  K: int32 | ⟂,                     # 0 if domestic-only; ⟂ until S4 otherwise
  next_state: enum{"S4","S7"},
  parameter_hash: hex64,
  manifest_fingerprint: hex64,
  seed: uint64
}
```

**Construction rules (deterministic, no RNG):**

* Initialise `C := [home_country_iso]` (rank 0 = home).
* If `e == false`: set `K := 0` and `next_state := "S7"` (bypass S4–S6).
* If `e == true`: set `K := ⟂` (unknown; will be determined by S4) and `next_state := "S4"`.
* Duplicates in `C` are forbidden (assert before any later append).

---

## 4) What S3 **does not** do (normative non-actions)

* **No persistence.** S3 writes **no** rows to any dataset; in particular, it does **not** write `country_set`. Cross-country order is persisted **after S6** to `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/` (schema `#/alloc/country_set`), which is the **only** authoritative store of inter-country rank.
* **No RNG.** S3 emits **no** RNG event streams. Any S4–S6 RNG evidence for a merchant with `e==false` causes the validator fail `branch_inconsistent_domestic`.
* **No egress.** Egress `outlet_catalogue` is an S8 responsibility and is **fingerprint-scoped**; consumers must verify the 1A validation gate before reading it and must join `country_set.rank` for cross-country order.

---

## 5) Downstream contracts (who consumes which fields, exactly)

### 5.1 S4 (eligible only; `next_state="S4"`)

* **Consumes:** `merchant_id`, `C` (length 1 with home), `N`, `mcc`, `channel`, `home_country_iso`, `parameter_hash`, `seed`, `manifest_fingerprint`.
* **Produces:** ZTP draws to determine $K\ge1$ and logs: `poisson_component(context="ztp")`, `ztp_rejection`, possibly `ztp_retry_exhausted`. **No** modification of `C[0]`.

### 5.2 S7 (domestic-only; `next_state="S7"`)

* **Consumes:** `merchant_id`, `C=[home]`, `K=0`, `N`, `seed`, `parameter_hash`, `manifest_fingerprint`.
* **Produces:** within-country sequencing for the **home country only**. When `|C| = 1`, S7 emits **no** `dirichlet_gamma_vector` nor `gamma_component(context="dirichlet")`. It may emit deterministic residual-ordering evidence (e.g., `residual_rank`), and S8 will emit the non-consuming `sequence_finalize`. Egress still requires joining `country_set` later for order (even though it will have only rank 0).

---

## 6) State-boundary invariants (validator-facing; MUST hold)

For every merchant $m$ admitted to S3:

1. **Flags cardinality (I-EL2).** Exactly one row in `crossborder_eligibility_flags` for `(parameter_hash, merchant_id)` with `is_eligible:boolean`, `rule_set:non-null`, `reason:nullable`.
2. **Branch coherence (I-EL3).**

   * If `e==false` ⇒ **no** S4–S6 RNG events exist for $m$ under `(seed, parameter_hash, run_id)`.
   * If `e==true` ⇒ **at least one** `poisson_component(context="ztp")` **or** a `ztp_retry_exhausted` exists.
3. **Country-set shape at persistence time.** When `country_set` is later written, it must contain exactly one home row `(is_home=true, rank=0, country_iso=c)` and, if eligible, **contiguous** foreign ranks `1..K`. `country_set` is the **only** authoritative store of cross-country order.
4. **Egress separation.** `outlet_catalogue` never encodes cross-country order; 1B must join `country_set.rank`, and must verify the `_passed.flag == SHA256(validation_bundle_1A)` hand-off gate for the same fingerprint **before** reading.

---

## 7) Reference procedure (language-agnostic pseudocode)

```pseudo
# S3.6: finalise the export and route
function s3_6_state_boundary(inputs: S3Export) -> (route, S3Export):
    assert typeof(inputs.e) == BOOLEAN
    assert inputs.C == [inputs.home_country_iso] and iso2_fk_valid(inputs.home_country_iso)
    if inputs.e == false:
        inputs.K = 0
        inputs.next_state = "S7"
        route = "S7"
    else:
        inputs.K = ⟂              # determined by S4
        inputs.next_state = "S4"
        route = "S4"
    return (route, inputs)        # pass by reference/value; no persistence
```

**Join/partition keys preserved:** `(merchant_id, seed, parameter_hash, manifest_fingerprint)` accompany the export so S4/S7 writes can embed them in their datasets/logs.

---

## 8) Failure surface at the boundary

S3.6 itself raises **no new** errors (it only packages decisions). All failures for S3 are those enumerated in **S3.5** (flags missing/duplicate/schema, illegal ISO, branch inconsistency), plus any schema/PK/FK checks performed later at `country_set` persistence and S9 validation.

---

## 9) Conformance tests (suite skeleton)

1. **Domestic-only routing.** Given `e=false`, `C=["GB"]`, run S3.6 ⇒ returns route `S7`, export has `K=0`, `next_state="S7"`. Later, `country_set` must contain only `(GB, rank=0)`. **Pass.**
2. **Eligible routing.** Given `e=true`, `C=["US"]`, run S3.6 ⇒ returns route `S4`, export has `K=⟂`, `next_state="S4"`. S4 must emit ZTP evidence or exhaustion. **Pass.**
3. **No Dirichlet when `|C|=1`.** For `e=false` (domestic-only) or any state where `C` remains length 1, assert **zero** rows in `dirichlet_gamma_vector` and `gamma_component(context="dirichlet")` for `(merchant_id, seed, parameter_hash, run_id)`. **Pass** when absent.
4. **Order authority separation.** After full pipeline, confirm `outlet_catalogue` lacks any cross-country order column and consumers recover order by joining `country_set.rank`. **Pass.**
5. **No-RNG invariant.** Confirm no S3-labelled RNG streams exist; any S4–S6 events for `e=false` trip `branch_inconsistent_domestic`. **Pass/Fail accordingly.**

---

## 10) Complexity & performance

O(1) per merchant (set two scalars, return a struct). **Zero I/O** and **zero RNG** at this boundary. All heavy lifting is deferred to S4/S7. (Downstream persistence/validation costs are governed by their own specs.)

---

## 11) Why this clean boundary matters

* Keeps S3 **replayable**: decisions are derived solely from ingress + parameter-scoped flags + S2 acceptance; with fixed `parameter_hash` and `seed` the export is deterministic.
* Preserves a single source of truth for order: `country_set.rank` (partitioned by `{seed, parameter_hash}`) is the **only** authority; egress and downstream layers avoid duplicating or drifting the notion of cross-country order.

---

# S3.A — Eligibility gate system log (non-authoritative, no RNG)

## 1) Purpose & scope (normative)

S3.A emits **structured JSONL operational events** around the S3 gate:

* **`s3_inputs_bound`** (after S3.1 completes),
* **`s3_decision`** (after S3.2 decides the branch), and
* **`s3_abort`** (when S3.1/S3.2 aborts with a deterministic error ID from S3.5).

The log provides a human/debug-friendly trace but is **not** a model input and is **not** used by S9. Country order remains solely in `alloc/country_set.rank`; egress `outlet_catalogue` is order-agnostic and continues to be authorized only by `_passed.flag == SHA256(validation_bundle_1A)`.

**Zero RNG.** S3.A consumes no RNG streams and must never write `rng_event_*` rows; it is purely system logging. (S3 has no RNG by design.)

---

## 2) Storage layout (pathing, partitions, rotation)

**Dataset (non-authoritative logs):**

```
logs/system/eligibility_gate.v1/run_id={run_id}/part-*.jsonl.gz
```

* **Partition key:** `run_id` only (simplifies incident scoping to the run that produced the egress/validation).
* **In-record lineage:** each record **must** embed `seed`, `parameter_hash`, and `manifest_fingerprint` so operators can correlate with authoritative datasets and S9 bundles.
* **Compression:** `gzip` (recommended; typical record size 250–500 bytes).
* **File size guard:** roll a new `part-*` around 256 MiB (configurable).
* **Retention (ops policy):** 30 days minimum; these logs contain no PII and are small. (Authoritative datasets have their own retention; e.g., `country_set` 365 days.)

> **Non-interference:** This path is separate from parameter-/seed-scoped authoritative tables (`country_set`, `outlet_catalogue`, flags). It must **not** be referenced by the artefact registry or data dictionary as an authoritative dataset.

---

## 3) Event model (enumeration, schema, invariants)

### 3.1 Event types (closed set)

```
"type" ∈ {"s3_inputs_bound", "s3_decision", "s3_abort"}
```

Exactly **one** of `payload_inputs`, `payload_decision`, `payload_abort` is present, according to `type`.

### 3.2 Common envelope (required on **every** record)

* `event_id: string[64 lower-hex]` — deterministic per (type, merchant, run); see §4 (ID derivation).
* `type: enum` — as above.
* `ts_utc: string[RFC3339]` — system wall-clock in UTC.
* `merchant_id: id64`
* `seed: uint64` — the run’s master/global seed.
* `parameter_hash: hex64` — parameter scope.
* `manifest_fingerprint: hex64` — egress/validation scope.
* `run_id: uuid` — execution instance (logs are partitioned by this).
* `module: "1A.S3"` — constant string (helps filtering).
* `version: "v1"` — log schema version.

### 3.3 Type-specific payloads

**A) `s3_inputs_bound` → `payload_inputs`**

* `home_country_iso: ISO2 (uppercase)` — FK-valid canonical ISO code.
* `mcc: int32`
* `channel: enum{"card_present","card_not_present"}` (ingress enum).
* `N: int32 (≥2)` — accepted NB count from S2 (context only).
* `flags: { is_eligible:boolean, rule_set:string(non-null), reason:string|null }` — read from `crossborder_eligibility_flags`.

**B) `s3_decision` → `payload_decision`**

* `e: boolean` — alias of `flags.is_eligible`.
* `branch: enum{"eligible","domestic_only"}`
* `home_country_iso: ISO2`
* `rule_set: string(non-null)`; `reason: string|null` (MUST be `null` when `e==true`).
* `C0: ISO2` — the home ISO placed at `rank=0` in the country container. (Informational; the authoritative sequence is later persisted in `country_set`.)

**C) `s3_abort` → `payload_abort`**

* `error: string` — one of the canonical IDs from S3.5 (e.g., `E_FLAGS_MISSING`, `E_HOME_ISO_INVALID`, `E_NOT_MULTISITE_OR_MISSING_S2`).
* `dataset: string` — the authoritative dataset/stream implicated (e.g., `"crossborder_eligibility_flags"` or `"rng_event_nb_final"`).
* `details: object` — **small**, redaction-safe probe (counts, offending keys); never dump full rows.

> **Invariants:**
> ‣ Envelope fields are **always present**; payload shape matches `type`.
> ‣ Values mirror authoritative sources (ingress, flags); if a value violates its schema (e.g., `channel="CP"`), S3 would already abort and only `s3_abort` may be logged.

---

## 4) Deterministic `event_id` (collision-safe & idempotent)

To deduplicate on retries within the **same** run:

* Let `T` be the literal event type string.
* Let `M` be `merchant_id` as 8-byte big-endian.
* Let `R` be `run_id` as 16 bytes (RFC-4122).
* Let `K` be a 1-byte kind tag: `0x01`=`s3_inputs_bound`, `0x02`=`s3_decision`, `0x03`=`s3_abort`.
* Define:

$$
\text{event_id} \;=\; \mathrm{hex}_{64}\!\left(\mathrm{SHA256}\!\big(K \,\|\, M \,\|\, R \,\|\, \text{bytes}(T)\big)\right).
$$

* **Property.** Re-emitting the same S3 event for the same merchant and run yields the **same** `event_id`. Different `run_id` ⇒ different `event_id` (keeps retries distinct across runs).

**Note.** The log never appears in parameter hashing or egress validation; this ID is for **ops dedupe only**.

---

## 5) JSON-Schema (authoritative for this log)

The following (abridged for readability) is **normative**; enforce with a JSON-Schema validator at write time. Types/patterns for ISO2, hex64, id64 mirror the authoritative table schemas/policies.

```json
{
  "$id": "schemas.ops.1A.s3_log.v1",
  "type": "object",
  "required": ["event_id","type","ts_utc","merchant_id","seed","parameter_hash",
               "manifest_fingerprint","run_id","module","version"],
  "properties": {
    "event_id": { "type":"string", "pattern":"^[a-f0-9]{64}$" },
    "type": { "enum":["s3_inputs_bound","s3_decision","s3_abort"] },
    "ts_utc": { "type":"string", "format":"date-time" },   // RFC3339 (UTC)
    "merchant_id": { "$ref":"schemas.1A.yaml#/$defs/id64" },
    "seed": { "$ref":"schemas.1A.yaml#/$defs/uint64" },
    "parameter_hash": { "type":"string", "pattern":"^[a-f0-9]{64}$" },
    "manifest_fingerprint": { "type":"string", "pattern":"^[a-f0-9]{64}$" },
    "run_id": { "type":"string", "format":"uuid" },
    "module": { "const": "1A.S3" },
    "version": { "const": "v1" },

    "payload_inputs": {
      "type":"object",
      "required":["home_country_iso","mcc","channel","N","flags"],
      "properties":{
        "home_country_iso": { "$ref":"schemas.1A.yaml#/$defs/iso2" },
        "mcc": { "type":"integer" },
        "channel": { "enum":["card_present","card_not_present"] },
        "N": { "type":"integer", "minimum": 2 },
        "flags": {
          "type":"object",
          "required":["is_eligible","rule_set"],
          "properties":{
            "is_eligible": { "type":"boolean" },
            "rule_set": { "type":"string", "minLength":1 },
            "reason": { "type":["string","null"] }
          },
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    },

    "payload_decision": {
      "type":"object",
      "required":["e","branch","home_country_iso","rule_set"],
      "properties":{
        "e": { "type":"boolean" },
        "branch": { "enum":["eligible","domestic_only"] },
        "home_country_iso": { "$ref":"schemas.1A.yaml#/$defs/iso2" },
        "rule_set": { "type":"string", "minLength":1 },
        "reason": { "type":["string","null"] },
        "C0": { "$ref":"schemas.1A.yaml#/$defs/iso2" }
      },
      "allOf": [
        { "if": { "properties": { "e": { "const": true } } },
          "then": { "properties": { "reason": { "const": null } } } }
      ],
      "additionalProperties": false
    },

    "payload_abort": {
      "type":"object",
      "required":["error","dataset"],
      "properties":{
        "error": { "enum":[
          "E_NOT_MULTISITE_OR_MISSING_S2","E_FLAGS_MISSING","E_FLAGS_DUPLICATE",
          "E_FLAGS_SCHEMA","E_HOME_ISO_INVALID"
        ] },
        "dataset": { "type":"string" },
        "details": { "type":"object" }
      },
      "additionalProperties": false
    }
  },
  "oneOf": [
    { "properties": { "type": { "const":"s3_inputs_bound" }, "payload_inputs": { "type":"object" } }, "required":["payload_inputs"] },
    { "properties": { "type": { "const":"s3_decision" },     "payload_decision": { "type":"object" } }, "required":["payload_decision"] },
    { "properties": { "type": { "const":"s3_abort" },        "payload_abort": { "type":"object" } }, "required":["payload_abort"] }
  ],
  "additionalProperties": false
}
```

---

## 6) Reference emission procedure (language-agnostic pseudocode)

```pseudo
function emit_s3_log(type, merchant_ctx, payload):
    rec := {
      event_id: derive_event_id(type, merchant_ctx.merchant_id, run_id),
      type: type,
      ts_utc: now_rfc3339_utc(),
      merchant_id: merchant_ctx.merchant_id,
      seed: merchant_ctx.seed,
      parameter_hash: merchant_ctx.parameter_hash,
      manifest_fingerprint: merchant_ctx.manifest_fingerprint,
      run_id: run_id,
      module: "1A.S3",
      version: "v1"
    }
    if type == "s3_inputs_bound":    rec.payload_inputs   = payload
    if type == "s3_decision":        rec.payload_decision = payload
    if type == "s3_abort":           rec.payload_abort    = payload

    assert validate_json_schema(rec, schemas.ops.1A.s3_log.v1)

    # Non-fatal best-effort write:
    path := sprintf("logs/system/eligibility_gate.v1/run_id=%s/part-%05d.jsonl.gz", run_id, current_part())
    try append_jsonl_gz(path, rec) catch IOErr:
        warn("S3.A log write failed; continuing (non-authoritative)")
```

**Placement:**

* Emit `s3_inputs_bound` at the **end of S3.1** (after all preconditions pass).
* Emit `s3_decision` at the **end of S3.2** (branch is known) or at S3.6 boundary.
* Emit `s3_abort` **at the abort site** in S3.1/S3.2 with the canonical error ID from S3.5.

**Idempotence:** The same event may be re-emitted (e.g., task retry); `event_id` dedupes downstream tooling for the **same** `run_id`. See §4.

---

## 7) Determinism & non-interference guarantees

* **No read-after-write coupling.** No 1A module is allowed to read from `logs/system/eligibility_gate.v1/*`.
* **Not part of validation.** S9 ignores system logs; the authorization gate for 1B is **only** the bundle and `_passed.flag`.
* **Schema authority separation.** Authoritative schemas remain `schemas.ingress.layer1.yaml`, `schemas.1A.yaml`, `schemas.layer1.yaml`; this ops schema is **not** part of the model’s schema authority.

---

## 8) Privacy & redaction

* **No PII** is written (merchant_id is an internal surrogate).
* `details` in `s3_abort` must remain **small** (counts/keys only). Never embed entire table rows or parameter file contents.

---

## 9) Failure semantics (logging must never break S3)

**Best-effort policy:** Any I/O failure in S3.A **must not** abort S3 or alter modeling results.

* **Write failure:** log a process-local warning; continue.
* **Schema validation failure (bug):** emit a local warning and **suppress the bad record**, continue.
* **Partition unavailability (object store outage):** buffer up to `B=10,000` events in RAM and attempt periodic flush; on process shutdown, drop silently if still failing.
* **Clock skew:** timestamps are advisory; correctness does **not** depend on `ts_utc`.

---

## 10) Example records (illustrative)

**A) `s3_inputs_bound`**

```json
{
  "event_id":"a1c5…f9",
  "type":"s3_inputs_bound",
  "ts_utc":"2025-08-15T09:20:11Z",
  "merchant_id": 72193488127,
  "seed": 1554909021,
  "parameter_hash":"9f12…ab",
  "manifest_fingerprint":"1c77…3e",
  "run_id":"f3a6c1c0-4a51-4d7a-8d79-9b7f8fb9e1a4",
  "module":"1A.S3",
  "version":"v1",
  "payload_inputs":{
    "home_country_iso":"GB",
    "mcc": 5411,
    "channel":"card_present",
    "N": 7,
    "flags": { "is_eligible": true, "rule_set":"default_v1", "reason": null }
  }
}
```

**B) `s3_decision`**

```json
{
  "event_id":"b97d…21",
  "type":"s3_decision",
  "ts_utc":"2025-08-15T09:20:12Z",
  "merchant_id": 72193488127,
  "seed": 1554909021,
  "parameter_hash":"9f12…ab",
  "manifest_fingerprint":"1c77…3e",
  "run_id":"f3a6c1c0-4a51-4d7a-8d79-9b7f8fb9e1a4",
  "module":"1A.S3",
  "version":"v1",
  "payload_decision":{
    "e": true,
    "branch":"eligible",
    "home_country_iso":"GB",
    "rule_set":"default_v1",
    "reason": null,
    "C0":"GB"
  }
}
```

**C) `s3_abort`**

```json
{
  "event_id":"05ef…d0",
  "type":"s3_abort",
  "ts_utc":"2025-08-15T09:20:06Z",
  "merchant_id": 99002333111,
  "seed": 1554909021,
  "parameter_hash":"9f12…ab",
  "manifest_fingerprint":"1c77…3e",
  "run_id":"f3a6c1c0-4a51-4d7a-8d79-9b7f8fb9e1a4",
  "module":"1A.S3",
  "version":"v1",
  "payload_abort":{
    "error":"E_FLAGS_MISSING",
    "dataset":"crossborder_eligibility_flags",
    "details":{"probe_count":0}
  }
}
```

---

## 11) Conformance tests (suite skeleton)

1. **Schema pass.** Generate one record of each type; validate against `schemas.ops.1A.s3_log.v1` → **pass**.
2. **Branch rule.** For `s3_decision` with `e=true`, `reason` must be `null` → **pass**; with `e=false`, allow a non-null governed code (e.g., `"mcc_blocked"`) → **pass**. (Flags source is authoritative.)
3. **ID idempotence.** Re-emit the same merchant+run+type → identical `event_id`; change `run_id` → different `event_id` → **pass**.
4. **Non-interference.** Delete the entire `logs/system/eligibility_gate.v1/` folder and rerun S3 only → S3 decisions identical; S9 still passes based solely on authoritative artefacts → **pass**.
5. **Rotation.** Force >256 MiB of logs; ensure multiple `part-*` files and valid JSONL in each → **pass**.

---

## 12) Operational notes

* **Ordering:** No global ordering guarantee across files; order by `ts_utc` within a file is best-effort. Consumers should not rely on ordering.
* **Searchability:** Because partitioning is by `run_id`, incident responders can glob by run, then grep by `merchant_id` or `parameter_hash`.
* **Evolution:** Any breaking change bumps to `eligibility_gate.v2` (new path and `version:"v2"`). v1 remains readable; never hot-edit v1 semantics.

---

## 13) Why this is safe

* The system log improves **observability** without creating shadow authority; all **truths** remain in the dictionary-bound datasets (`crossborder_eligibility_flags`, `country_set`, `outlet_catalogue`) and validator bundle.
* S3’s determinism, the S9 **hand-off gate**, and the policy that **inter-country order lives only in `country_set.rank`** stay intact.

---
