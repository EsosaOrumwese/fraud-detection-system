# S3.1 — Inputs (from S0/S1/S2 + artefacts)

## Goal

Materialise the **deterministic inputs** S3 needs to make the cross-border eligibility gate for each merchant $m$ that left S2 with an accepted domestic count $N_m\ge2$ (i.e., `is_multi=1` from S1). No RNG is used here.

---

## Inputs (authoritative sources and contracts)

1. **Identity & home (ingress):**
   $(\texttt{merchant_id}_m,\ \texttt{home_country_iso}_m=c)$. These come from the canonical merchant ingress row prepared in S0/S1 and used throughout the journey.

2. **Deterministic flags (materialised in S0):**
   Exactly **one** row in the **parameter-scoped** table `crossborder_eligibility_flags`, partitioned by `{parameter_hash}`, with schema fields:
   $(\texttt{merchant_id},\ \texttt{is_eligible},\ \texttt{reason},\ \texttt{rule_set})$.
   This table is the single source of truth for the eligibility decision; it’s written in S0 and only **read** in S3.

3. **Previously computed state:**

* $N_m\in\{2,3,\dots\}$ accepted in S2 (multi-site branch).
* $\texttt{mcc}_m,\ \texttt{channel}_m$ from ingress/S0 encoders.

4. **Lineage keys (for joins & validation):**
   `parameter_hash` (parameters scope), `manifest_fingerprint` (run scope). S3 reads parameter-scoped inputs now; later persistence (e.g., `country_set`) uses `{seed, parameter_hash}`.

**Domain restriction.** S3 is evaluated **only** for merchants with `is_multi=1`. Single-site merchants bypass S2–S6 and go directly to S7 by the journey spec.

---

## Canonical materialisation (deterministic)

For each merchant $m$ with $N_m\ge2$:

1. **Ingress bind.** Read $(\texttt{merchant_id}_m,\ \texttt{home_country_iso}_m=c,\ \texttt{mcc}_m,\ \texttt{channel}_m)$ from the normalised ingress view used in S0/S1.

2. **Eligibility row lookup.** Under the active `parameter_hash`, locate the **unique** row in `crossborder_eligibility_flags` with `merchant_id=m`; extract
   `is_eligible ∈ {false,true}`, `rule_set` (non-null), and `reason` (nullable—usually null when eligible). Enforce the table’s schema/partitioning (parameter-scoped).

3. **Carry S2 output.** Attach the accepted $N_m$ from S2 for context (no change here).

4. **Lineage attach.** Retain `parameter_hash` and `manifest_fingerprint` for downstream joins and bundle validation; no new partitions are written in S3.

---

## Properties & invariants (checked before the gate in S3.2)

* **I-S3.1-1 (exactly one flag row):** For each $m$ at S3, there is **exactly one** row in `crossborder_eligibility_flags` under the current `parameter_hash`. Missing/duplicate rows are structural failures.
* **I-S3.1-2 (schema fields):** `is_eligible` is boolean; `rule_set` is non-null; `reason` may be null (e.g., when eligible). Enforced by `schemas.1A.yaml`.
* **I-S3.1-3 (journey coherence):** Only merchants with prior S1 `is_multi=1` and S2 `nb_final` should appear here; single-site merchants must not. (Validators scan event coverage from earlier states.)
* **I-S3.1-4 (ISO legality for later FK):** `home_country_iso` must lie in the canonical ISO-3166 list; this is required later when persisting `country_set` (FK).
* **I-S3.1-5 (no RNG):** S3.1 is purely deterministic; no Philox counters advance.

---

## Failure semantics (abort with diagnostics)

* `eligibility_flags_missing(m)` if no row found in `crossborder_eligibility_flags` for `parameter_hash`.
* `eligibility_flags_duplicate(m)` if multiple rows found.
* `eligibility_schema_violation(m)` if any required column is null/ill-typed (e.g., missing `rule_set`).
* `journey_incoherent(m)` if `is_multi=0` merchant appears in S3.1 (violates journey spec).
* `illegal_home_iso(m,c)` if $c\notin$ canonical ISO (anticipates later FK in `country_set`).

---

## Determinism & replay

Given fixed ingress rows and the parameter-scoped `crossborder_eligibility_flags` under a specific `parameter_hash`, S3.1’s realised inputs are **byte-reproducible** across machines and runs; no RNG usage occurs.

---

## Minimal reference algorithm (language-agnostic)

```
INPUT:
  merchant_id, home_country_iso=c, mcc, channel       # ingress/S0
  N >= 2                                              # from S2
  parameter_hash                                      # active
  crossborder_eligibility_flags[parameter_hash]       # table

OUTPUT (in-memory bundle for S3.2):
  merchant_id, c, mcc, channel, N,
  is_eligible, reason, rule_set,
  parameter_hash, manifest_fingerprint

1  row := lookup_unique(crossborder_eligibility_flags, parameter_hash, merchant_id)
2  if row == MISSING: abort("eligibility_flags_missing", merchant_id)
3  if row == DUPLICATE: abort("eligibility_flags_duplicate", merchant_id)
4  assert type(row.is_eligible) == boolean
5  assert row.rule_set is not null
6  # reason may be null by schema; keep as-is
7  assert is_valid_iso2(c)            # for later FK in country_set
8  return (merchant_id, c, mcc, channel, N,
          row.is_eligible, row.reason, row.rule_set,
          parameter_hash, manifest_fingerprint)
```


## What S3.1 “exports” to S3.2

An **in-memory, deterministic bundle** per merchant: identity $m$, home $c$, features $(\texttt{mcc},\texttt{channel})$, accepted $N_m$, and the **eligibility row** $(\texttt{is_eligible}, \texttt{reason}, \texttt{rule_set})$ under the current `parameter_hash`—plus lineage keys. S3.2 will consume this bundle to make the gate decision; single-site merchants should never reach this point per the journey.

---

# S3.2 — Eligibility function & deterministic decision

## Goal

Apply a **policy firewall** before any foreign spread: decide, for each multi-site merchant $m$, whether it is allowed to attempt cross-border expansion. The decision is **deterministic**, sourced from the governed rule family $\mathcal{E}$ that was **materialised in S0** as `crossborder_eligibility_flags` and is **read-only** here.

---

## Inputs (from S3.1 / S0)

For each $m$ at S3:

* Categorical features: $(\texttt{mcc}_m,\texttt{channel}_m\in\{\mathrm{CP},\mathrm{CNP}\},\ \texttt{home_country_iso}_m\in\mathcal{I})$.
* Parameter-scoped row in `crossborder_eligibility_flags` with schema
  $(\texttt{merchant_id},\ \texttt{is_eligible},\ \texttt{reason},\ \texttt{rule_set})$. Exactly **one** row per merchant under the active `{parameter_hash}`; this table is the single source of truth for the gate.

---

## Formal definition (policy set and indicator)

Let the **governed rule family** be a fixed set

$$
\mathcal{E}\ \subseteq\ \underbrace{\mathbb{N}}_{\text{MCC}}\ \times\ \underbrace{\{\mathrm{CP},\mathrm{CNP}\}}_{\text{channel}}\ \times\ \underbrace{\mathcal{I}}_{\text{ISO-3166 home}},
$$

defined entirely by configuration (artefacts hashed into `parameter_hash`). Define the **eligibility indicator**:

$$
\boxed{\,e_m\;=\;\mathbf{1}\!\Big\{(\texttt{mcc}_m,\texttt{channel}_m,\texttt{home_country_iso}_m)\in\mathcal{E}\Big\}\,}.
$$

S0 has already computed and **materialised** $e_m$ as `crossborder_eligibility_flags.is_eligible`, with the applied `rule_set` identifier and (optional) `reason` when ineligible; S3 **reads** this row (no mutation, no RNG).

---

## Gate (branch function)

Map the indicator to a branch tag:

$$
\boxed{\ \text{eligible branch if } e_m=1;\qquad \text{domestic-only branch if } e_m=0.\ }
$$

Only $e_m=1$ merchants may enter **S4 (ZTP foreign-count)**; $e_m=0$ merchants bypass S4–S6 and head to S7 with $\mathcal{C}_m=\{\text{home}\}$. This matches the design narrative and state-flow.

---

## Properties & invariants (checked at S3.2)

* **I-EL-Determinism.** S3.2 performs **no** random draws; outputs are pure functions of the parameter-scoped flag table + ingress fields. Bit-replay holds by data alone.
* **I-EL-Uniqueness.** Exactly **one** `crossborder_eligibility_flags` row exists per $(\texttt{parameter_hash},\texttt{merchant_id})$; duplicates/missing rows are structural failures.
* **I-EL-Schema.** `is_eligible` is boolean; `rule_set` is **non-null**; `reason` may be null (commonly when eligible). Enforced by the schema.
* **I-EL-Branch coherence.**

  * If $e_m=0$: **no** S4–S6 RNG events (`poisson_component` with `context="ztp"`, `ztp_rejection`, `gumbel_key`, `dirichlet_gamma_vector`) may exist later for $m$.
  * If $e_m=1$: S4 events **must** exist (or an explicit capped-out diagnostic), else validation fails.

---

## Failure semantics (abort conditions)

* `eligibility_flags_missing/duplicate(m)` — missing or multiple rows in `crossborder_eligibility_flags` for active `{parameter_hash}`.
* `eligibility_schema_violation(m)` — bad types or null `rule_set`.
* `inconsistent_branch(m)` — presence/absence of S4–S6 events contradicts the decided branch (checked by validator).

---

## Determinism & lineage

* Decision $e_m$ is **parameter-scoped** via `crossborder_eligibility_flags` (partitioned by `{parameter_hash}`), hence stable across replays with the same artefact bundle. No Philox counters are touched in S3.2.

---

## Minimal reference algorithm (language-agnostic)

```
INPUT:
  merchant_id, mcc, channel, home_country_iso
  parameter_hash
  crossborder_eligibility_flags[parameter_hash]

OUTPUT (in-memory to S3.3+):
  e, reason, rule_set, branch

1  row := lookup_unique(crossborder_eligibility_flags, parameter_hash, merchant_id)
2  if row missing:    abort("eligibility_flags_missing", merchant_id)
3  if row duplicate:  abort("eligibility_flags_duplicate", merchant_id)
4  assert is_boolean(row.is_eligible) and row.rule_set != null
5  e := row.is_eligible
6  branch := (e ? "eligible→S4" : "domestic_only→S7")
7  return (e, row.reason, row.rule_set, branch)
```

This is **read-only** wrt the eligibility artefact; S3.2 never rewrites flags nor consumes RNG.

---

## What S3.2 “exports”

A compact, deterministic **branch decision** per merchant:

$$
\boxed{\ e_m\in\{0,1\},\ \texttt{rule_set},\ \texttt{reason},\ \text{branch tag}\ }
$$

which S3.3 uses to initialise the ordered country set and route into S4 (if eligible) or S7 (if not).

---

# S3.3 — Derived (in-memory) country-set container (deep dive)

## Object, semantics, and why we need it

We instantiate, per merchant $m$, an **ordered, duplicate-free sequence** of ISO-2 codes:

$$
\boxed{\ \mathcal{C}_m=(c_0,c_1,\ldots,c_{K_m})\ \text{ with }c_i\in\mathcal{I},\ c_i\neq c_j\ (i\ne j)\ }.
$$

By **contract**, `country_set` is the *only* authoritative store for this order; its schema encodes `rank` (0 = home), and its PK is $(\texttt{merchant_id},\texttt{country_iso})$. We initialise $\mathcal{C}_m$ here and only **persist** it after S6 has appended $K_m$ foreign ISOs.

---

## Branch-specific initialisation (deterministic, no RNG)

Let $c$ be the **home** ISO from ingress and $\mathcal{I}$ the canonical ISO-3166 set.

* **Domestic-only** ($e_m=0$):

  $$
  \boxed{\,K_m\leftarrow 0,\quad \mathcal{C}_m\leftarrow(c)\,}\quad\text{(length 1; skip S4–S6 \(\to\) S7).}
  $$

  When `country_set` is written later, this yields exactly **one** row: `(merchant_id=m, country_iso=c, is_home=true, rank=0)`.

* **Eligible** ($e_m=1$):

  $$
  \boxed{\,\mathcal{C}_m\leftarrow(c)\ \text{(rank 0 reserved)}\,}\quad\text{then proceed to S4 to obtain }K_m\ge1.
  $$

  After S6, we will have `(rank=0)` for $c$ **plus** $K_m$ foreign rows `(rank=1..K_m)`.

**Why do this now?** It fixes the **anchor** (home at rank 0) and establishes the exact container that S4–S6 will *append to*—never reordering or deleting—so that later persistence is a pure “dump” of $\mathcal{C}_m$ into `country_set`.

---

## Container → dataset mapping (future write, made explicit)

When S6 completes, persistence to `country_set` writes one row per position $i$:

$$
\text{row}_i = \big(\texttt{merchant_id}=m,\ \texttt{country_iso}=c_i,\ \texttt{is_home}=\mathbf{1}\{i=0\},\ \texttt{rank}=i\big)
$$

under the dictionary-pinned path:

```
data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/
```

with schema `schemas.1A.yaml#/alloc/country_set` (PK: `(merchant_id,country_iso)`, FK: `country_iso` → canonical ISO). `rank` carries the order; there are **no** sort keys in storage (order is columnar).

---

## Allowed operations on $\mathcal{C}_m$ (and forbidden ones)

Think of $\mathcal{C}_m$ as an **append-only** list with strict guards:

* **Init**: `init_container(m,c)`
  Preconditions: $c\in\mathcal{I}$. Result: $\mathcal{C}_m=(c)$. (S3.3)

* **AppendForeign** (used later by S6): `append_foreign(C, i)`
  Preconditions: $i\in\mathcal{I}$, $i\neq c_0$, $i\notin\{c_1,\dots\}$, and $i$ is in the S6 candidate universe. Result: $(c_0,\dots,c_r,i)$. (Not executed in S3.3; specified to make the interface explicit.)

* **Forbidden** in S3.3–S6: deletion, in-place swaps, or insertions at $j\ne\text{len}(C)$. This enforces that the persisted `rank` equals construction order (Gumbel-top-K later).

These rules guarantee `country_set`’s **PK** uniqueness (no duplicate `(merchant_id,country_iso)`), **rank** soundness (`rank>=0`, `rank=0` ↔ home), and ISO FK validity.

---

## Invariants established **now** (checked immediately; re-checked on write)

1. **Rank-0 home:** $c_0=c$ and `is_home=true` iff `rank=0`. Never changes.
2. **Legality:** $c\in\mathcal{I}$ (canonical ISO FK will be enforced when writing). Abort **now** if not.
3. **Branch coherence:**

   * $e_m=0\Rightarrow |\mathcal{C}_m|=1,\ K_m=0,$ and the pipeline **must not** later emit S4–S6 RNG events for $m$.
   * $e_m=1\Rightarrow |\mathcal{C}_m|\ge 1$ and S4–S6 **must** run for $m$. (Validator checks both.)

---

## How downstream consumes this (previewed, not executed here)

* **S4 (ZTP)** reads $(\mathcal{C}_m,N_m)$, samples $K_m\ge1$ (eligible only). $\mathcal{C}_m$ remains `(c)` during S4.
* **S6 (selection)** appends $K_m$ foreign ISOs in **Gumbel order** (ties by ISO ASCII), producing `(c_0=c, c_1,\dots,c_{K_m})`. This list is then persisted to `country_set`.
* **1B / egress** later **must join** on `country_set.rank` to recover inter-country order; egress never encodes this order itself.

---

## Failure semantics (what S3.3 can and should fail fast on)

* `illegal_home_iso(m,c)`: $c\notin\mathcal{I}$ (prevents later FK breach on `country_set`). **Abort here.**
* `journey_incoherent(m)`: merchant with $e_m=0$ observed later with any S4–S6 RNG events (caught by validator, but we document the contract here).

---

## Extended reference algorithm (explicit state bundle + guards)

```
INPUT:
  merchant_id = m
  home_country_iso = c
  e ∈ {0,1}                   # from S3.2
  N >= 2                      # from S2 (context only)
  I = canonical ISO-3166 set  # from ingress artefact

OUTPUT (in-memory to S4 or S7):
  C      # ordered container of ISO-2 codes
  K      # foreign count target (0 if e=0; unknown yet if e=1)
  meta   # annotations used later when persisting country_set

# Guards now (fail fast if violated)
1  if c ∉ I: abort("illegal_home_iso", m, c)                # will be FK later
2  C := (c)                                                 # rank 0 = home
3  if e == 0:
4      K := 0
5      meta := { will_persist_country_set: true,
                 expected_rows: 1,                          # (m,c,rank=0)
                 persist_schema_ref: "#/alloc/country_set",
                 partition_keys: ["seed","parameter_hash"] }
6      next_state := "S7"                                   # skip S4–S6
7  else:
8      K := ⊥  # determined in S4
9      meta := { will_persist_country_set: true,
                 expected_rows: "1 + K (to be set in S4/S6)",
                 persist_schema_ref: "#/alloc/country_set",
                 partition_keys: ["seed","parameter_hash"] }
10     next_state := "S4"
11 return (C, K, meta, next_state)
```

**Notes.**

* We track `meta.expected_rows` purely for validation clarity; the *actual* write happens after S6 using the dictionary contract.
* `⊥` marks “unknown yet” and is resolved by S4’s ZTP. No RNG is consumed in S3.3.


## What this guarantees at the S3.3 boundary

* The **shape** of the object that will later back `country_set` is fixed (rank-0 home, append-only thereafter).
* All later constraints in the `country_set` schema—PK, FK to canonical ISO, rank domain—are already **implied** by the construction here plus S6’s append discipline.

---

# S3.4 — Determinism & correctness invariants (expanded)

## I-EL1 — No RNG (purely deterministic)

**Statement.** S3 consumes **no** Philox draws. Outputs are a pure function of the parameter-scoped eligibility table and ingress fields:

$$
e_m \;=\; \mathbf{1}\!\Big\{(\texttt{mcc}_m,\texttt{channel}_m,\texttt{home_country_iso}_m)\in\mathcal{E}\Big\},
$$

but **S3 reads** $e_m$ from `crossborder_eligibility_flags.is_eligible` (materialised in S0); it does not recompute or mutate it. Therefore S3 is **bit-replayable by data alone** (no counter movement in any substream).

**Validator check.** Assert **zero** S3 RNG events exist (there are none defined for S3 in the dictionary), and that downstream ZTP/Gumbel/Dirichlet events—if present—are explained solely by $e_m$ (see I-EL3).

---

## I-EL2 — Dataset contract for `crossborder_eligibility_flags`

**Authority.** `crossborder_eligibility_flags` (partitioned by `{parameter_hash}`) is the **single source of truth** for eligibility. Schema (excerpt):
`merchant_id` (id64, PK), `is_eligible` (bool, non-null), `reason` (nullable), `rule_set` (string, non-null).

**Uniqueness.** For each merchant that reaches S3 under the active `{parameter_hash}`:

$$
\#\{\text{rows in flags for }m\}=1.
$$

Missing or duplicate rows are **structural failures**.

**Type/domain constraints.** Enforce `is_eligible ∈ {false,true}`, `rule_set ≠ NULL`; `reason` may be NULL (policy notes: typically NULL when eligible). These are schema-level guarantees.

**Lineage scope.** Because the table is parameter-scoped, identical `{parameter_hash}` implies identical $\mathcal{E}$ and identical $e_m$ values across replays; `manifest_fingerprint` is carried for run lineage but does not key this dataset.

---

## I-EL3 — Branch coherence (event-presence/absence rules)

**Event families downstream** (all partitioned by `["seed","parameter_hash","run_id"]`):

* **ZTP attempts & gates (S4):** `poisson_component` with `context="ztp"`, `ztp_rejection`, `ztp_retry_exhausted`.
* **Selection & splitting (S5–S6):** `gumbel_key`, `dirichlet_gamma_vector`.

**Coherence rules.**

$$
\begin{aligned}
e_m=0 &: \quad \text{NO rows for } m \text{ in } \{\texttt{poisson_component(ztp)},\ \texttt{ztp_*},\ \texttt{gumbel_key},\ \texttt{dirichlet_gamma_vector}\}.\\
e_m=1 &: \quad \text{At least one S4 ZTP row (or a capped abort via }\texttt{ztp_retry_exhausted}) \text{ must exist for } m.
\end{aligned}
$$

Any contradiction is a **validation failure**. (The same `poisson_component` stream id is used by NB with `context="nb"`; validators distinguish by `context`.)

---

## I-EL4 — `country_set` consistency (eventual persistence)

**Authority & schema.** `country_set` is the **only** store of cross-country order. PK: `(merchant_id,country_iso)`. Partitioning: `["seed","parameter_hash"]`. Columns include `is_home` (bool, non-null) and `rank` (int32, `rank≥0`, with `rank=0` reserved for home).

**Required shapes at write time (from S6):**

* If $e_m=0$: exactly **one** row

  $$
  (\texttt{merchant_id}=m,\ \texttt{country_iso}=c,\ \texttt{is_home}=true,\ \texttt{rank}=0).
  $$
* If $e_m=1$: the same home row **plus** exactly $K_m$ foreign rows with ranks $1..K_m$ (strictly increasing, no duplicates). These are appended in S6 and then persisted.

**FK legality.** Every `country_iso` must exist in the canonical ISO dataset referenced by the schema (FK), hence S3 checks home $c\in\mathcal{I}$ early to avoid late FK failures.

---

## Minimal validator routine for S3 invariants (reference)

```
INPUT:
  flags := crossborder_eligibility_flags[parameter_hash]
  rng_ZTP := {poisson_component where context="ztp",
              ztp_rejection, ztp_retry_exhausted}
  rng_SEL := {gumbel_key, dirichlet_gamma_vector}
  Cset   := country_set[seed, parameter_hash]
  M3     := set of merchants reaching S3 (from S2 nb_final join)

FOR each m in M3:
  rows := flags.where(merchant_id=m)
  if len(rows) != 1: fail("eligibility_flags_cardinality", m)

  e := rows[0].is_eligible
  assert rows[0].rule_set != NULL           # schema/domain
  # reason may be NULL; no extra check beyond schema

  if e == false:
     assert rng_ZTP.has_no_rows(m) and rng_SEL.has_no_rows(m), else
       fail("inconsistent_branch_e0", m)
     # country_set shape at write time:
     cs := Cset.where(merchant_id=m)
     assert len(cs) == 1 and cs[0].is_home == true and cs[0].rank == 0,
       else fail("country_set_shape_e0", m)
  else: # e == true
     assert rng_ZTP.has_any_rows(m) or has_row(ztp_retry_exhausted, m),
       else fail("missing_ztp_e1", m)
     # country_set shape at write time:
     cs := Cset.where(merchant_id=m)
     assert exists c in cs with is_home=true and rank==0
     # and all non-home rows have 1..K ranks with no duplicates
     assert ranks := sorted(cs.where(is_home=false).rank)
     assert ranks == [1,2,...,max(ranks)], else fail("country_set_rank_gap", m)

return PASS
```

* `rng_ZTP`/`rng_SEL` paths and schema refs are pinned by the dataset dictionary; `poisson_component` uses `context="ztp"` in S4 (distinct from NB’s `"nb"`).

---

## Edge cases & clarifications

* **Parameter scope drift.** Changing `{parameter_hash}` **changes** the flags table version; S3 decisions may (legitimately) differ between runs. Validators key joins by `{parameter_hash}` to avoid cross-scope leakage.
* **Run lineage.** `country_set` rows carry `manifest_fingerprint` in addition to partitions. This ties S6 outputs back to the exact artefact set used—even though S3’s gate is parameter-scoped.
* **ZTP hard cap as compliance.** If an eligible merchant never accepts in ZTP within the configured cap, the presence of `ztp_retry_exhausted` satisfies the “existence” side of I-EL3 but triggers S4-specific failure handling; S3 remains coherent.

---

# S3.5 — Failure modes (abort semantics)

## Scope

S3 is a **deterministic gate**. It writes no datasets and consumes no RNG; all failures are detected either **immediately** (missing inputs / illegal ISO) or by the **validator** via joins against the dictionary-pinned streams/tables.

---

## F-EL1 — Missing flag row (schema/lineage violation)

**Condition.** For merchant $m$ present at S3, there is **no** row in `crossborder_eligibility_flags/parameter_hash={parameter_hash}`.
**Why fatal.** The table is the single source of truth for $e_m$ and is **parameter-scoped**; without it, the gate decision is undefined.

**Detection.** During S3.1/S3.2 lookup: zero rows ⇒ `eligibility_flags_missing(m)` (**hard abort**). Validator also asserts **exactly one** row per merchant under the active `{parameter_hash}`.

**Evidence.** The absence is proven by a key lookup in `data/layer1/1A/crossborder_eligibility_flags/parameter_hash={parameter_hash}/` against schema `#/prep/crossborder_eligibility_flags`.

---

## F-EL2 — Inconsistent branch (contradicts I-EL3)

**Condition.** `is_eligible=false` in flags, **yet** any S4–S6 RNG events exist for $m$:

* ZTP: `poisson_component` with `context="ztp"`, `ztp_rejection`, or `ztp_retry_exhausted`;
* Selection: `gumbel_key` or `dirichlet_gamma_vector`.

**Why fatal.** S3 forbids foreign-spread RNG for ineligible merchants; presence implies a pipeline or join breach.

**Detection (validator).** Join flags to event streams (all partitioned by `["seed","parameter_hash","run_id"]`) and assert **absence** of those rows when `is_eligible=false`. Any hit ⇒ `inconsistent_branch(m)` (**validation abort**).

**Evidence.** Offending JSONL rows under `logs/rng/events/{poisson_component|ztp_rejection|ztp_retry_exhausted|gumbel_key|dirichlet_gamma_vector}/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…` with schemas from `schemas.layer1.yaml`.

---

## F-EL3 — Illegal home ISO (pre-FK guard)

**Condition.** Home $c\notin\mathcal{I}$ (canonical ISO-3166).
**Why fatal.** `country_set.country_iso` has a **foreign key** into the canonical ISO table; persisting `(m,c,rank=0)` would violate FK.

**Detection.** S3.3 checks `c∈\mathcal{I}` **eagerly** and aborts before any persistence: `illegal_home_iso(m,c)`. The validator re-asserts FK at `country_set` write (`#/alloc/country_set`).

**Evidence.** FK definition in `schemas.1A.yaml#/alloc/country_set.columns.country_iso.fk` to `schemas.ingress.layer1.yaml#/iso3166_canonical_2024`.

---

## (Elaborations consistent with S3.4)

**Duplicate flag rows.** More than one `crossborder_eligibility_flags` row for the same `(parameter_hash, merchant_id)` is a **structural failure** (`eligibility_flags_duplicate`). The uniqueness is implied by schema PK and S3.4 I-EL2.

**Flag schema violations.** `is_eligible` not boolean or `rule_set` NULL ⇒ **schema failure** on the flags table. (S3.4 I-EL2; enforced by schema.)

---

## Abort semantics & locus

* **Immediate aborts (during S3):** F-EL1 (missing flag), F-EL3 (illegal ISO). No S4–S6 are entered.
* **Validation aborts (post-run S3 bundle checks):** F-EL2 (inconsistent branch), duplicates, or schema/type violations in flags. Metrics and diffs are written; no `_passed.flag`.

---

## Minimal validator routine (reference)

```
INPUT:
  Flags := crossborder_eligibility_flags[parameter_hash]
  ZTP   := {poisson_component where context="ztp",
            ztp_rejection, ztp_retry_exhausted}
  SEL   := {gumbel_key, dirichlet_gamma_vector}
  I     := canonical ISO set
  M3    := merchants entering S3 (from S2 nb_final join)

FOR m in M3:
  rows := Flags[m]
  if len(rows) != 1: fail("eligibility_flags_cardinality", m)             # F-EL1 or duplicate
  (e, rule_set, reason) := rows[0].is_eligible, rows[0].rule_set, rows[0].reason
  assert type(e) == bool and rule_set != NULL                             # schema
  if e == false:
     assert no_rows(ZTP, m) and no_rows(SEL, m) else fail("inconsistent_branch", m)  # F-EL2
  assert home_iso(m) ∈ I else fail("illegal_home_iso", m)                 # F-EL3
return PASS
```

Streams, partitions, and schema refs used above are fixed by the **dataset dictionary** and **layer schemas**.

---

## Remediation hints (operator playbook)

* **F-EL1:** Rebuild `crossborder_eligibility_flags` for the active `{parameter_hash}` (S0), re-run S3.
* **F-EL2:** Ensure the S3 gate routes $e_m{=}0$ merchants away from S4–S6; purge any stray RNG emissions; revalidate.
* **F-EL3:** Correct `home_country_iso` to a canonical ISO-2 before S6/`country_set` write; the FK target is enumerated in the ingress schema.

This completes S3.5 with explicit conditions, detection points, and evidence paths consistent with your dictionary and schemas.

---

# S3.6 — Outputs (state boundary)

## What S3 **fixes** (and what it does **not**)

S3 is a **deterministic gate**. It **persists no new datasets** and **consumes no RNG**. Its only job is to set the **branch state** for each multi-site merchant and carry forward a small, explicit in-memory bundle to S4 or S7.


## Authoritative inputs carried forward

* **Eligibility bit:** $\boxed{e_m\in\{0,1\}}$ read from `crossborder_eligibility_flags.is_eligible` (parameter-scoped table; one row per merchant under the active `{parameter_hash}`). This table is the **only** source of truth for the gate.

* **Lineage keys:** `parameter_hash` (parameters scope) and `manifest_fingerprint` (run scope) travel with the in-memory bundle to enable validated joins when later datasets are written.


## In-memory export (per merchant) to downstream

Define the **country-set container** $\mathcal{C}_m$ (ordered, duplicate-free ISO-2 codes; rank 0 reserved for home), which **will** be persisted later as `country_set` (partitioned by `{seed, parameter_hash}`) and is the **only** authoritative store of cross-country order.

$$
\boxed{
\begin{aligned}
\textbf{If } e_m=0\ (\text{domestic‐only}):\qquad
&K_m \leftarrow 0,\quad \mathcal{C}_m \leftarrow (c),\quad \text{next} \leftarrow \text{S7}.\\[4pt]
\textbf{If } e_m=1\ (\text{eligible}):\qquad
&\mathcal{C}_m \leftarrow (c)\ \text{(rank 0 home)},\quad \text{next} \leftarrow \text{S4}.
\end{aligned}}
$$

No foreign ISOs are appended yet; S4 will determine $K_m\ge1$ (eligible only), S6 will append the $K_m$ foreign ISO codes in order, and **then** `country_set` is written.

**Why the container now?** Locking rank-0 $c$ here makes later persistence a direct dump of the built sequence; S3 does **not** persist `country_set`, it only defines its initial contents.

## Implicit contract S3 imposes on **later** persistence

When `country_set` is finally materialised (after S6), S3’s decision must be visible **exactly** as:

* $e_m=0$: **one** row
  $(\texttt{merchant_id}=m,\ \texttt{country_iso}=c,\ \texttt{is_home}=true,\ \texttt{rank}=0)$.
* $e_m=1$: the same home row **plus** exactly $K_m$ foreign rows with ranks $1..K_m$ (strictly increasing; no duplicates).
  This shape is enforced by `schemas.1A.yaml#/alloc/country_set` and the dictionary entry, with partitions `["seed","parameter_hash"]`.

Downstream consumers (S8/egress and **1B**) must **not** infer inter-country order from anywhere else; `outlet_catalogue` intentionally **does not** encode that order and must be joined to `country_set.rank` when needed.


## Boundary invariants the validator will assert

1. **No RNG in S3.** There are no S3 RNG streams; any draws for a merchant with $e_m=0$ in S4–S6 (`poisson_component` context `"ztp"`, `ztp_*`, `gumbel_key`, `dirichlet_gamma_vector`) are a **branch inconsistency**.
2. **Flags cardinality.** Exactly one `crossborder_eligibility_flags` row per merchant under the active `{parameter_hash}`.
3. **Country-set shape at write time.** The persisted `country_set` matches the two cases above (rank 0 = home; foreign ranks continuous 1..$K_m$).


## Remark on placement of responsibilities

S3 is the **policy firewall**: it enforces the documented rule that *only merchants designated to attempt cross-border expansion* may proceed to ZTP. Everything probabilistic or constructive happens **after** this deterministic gate:

* **S4 (ZTP)** — sample the foreign-country count $K_m$ (eligible merchants only).
* **S5 (currency→country expansion)** — build deterministic candidate weights/prior mass over countries.
* **S6 (Gumbel-top-k + allocation)** — select and **append** the $K_m$ foreign ISO codes in order; this sequence becomes authoritative order.
* **`country_set` persistence** — occurs **after** S6; rank 0 = home, ranks $1..K_m$ = selected foreigns.

S3 itself writes no datasets and consumes no RNG; it fixes only the branch state and the initial container $\mathcal{C}_m=(c)$.


## Minimal reference algorithm (handoff only)

```
INPUT:
  merchant_id=m, home_country_iso=c
  e ∈ {0,1}  # from crossborder_eligibility_flags (parameter-scoped)
  N ≥ 2      # from S2 (context)
  parameter_hash, manifest_fingerprint

OUTPUT (in-memory bundle):
  { merchant_id, c, e, C, K, next_state, parameter_hash, manifest_fingerprint }

1  C := (c)                 # rank 0 reserved for home
2  if e == 0:
3      K := 0
4      next_state := "S7"   # bypass S4–S6
5  else:
6      K := ⊥               # determined by S4 (eligible only)
7      next_state := "S4"
8  return {...}
```

This bundle is not persisted by S3; it’s consumed immediately by S4 (eligible) or S7 (domestic-only). The eventual `country_set` write uses `{seed, parameter_hash}` partitions and the schema `#/alloc/country_set`.

## Writer/runner checklist (to close S3 cleanly)

* Do **not** write any S3 dataset; only pass the in-memory bundle onward.
* Ensure the `crossborder_eligibility_flags` table (under current `{parameter_hash}`) exists and has **exactly one** row per merchant.
* For merchants routed to S7 ($e_m=0$), guarantee **no** S4–S6 RNG events are emitted later. For $e_m=1$, S4 must emit ZTP events and determine $K_m$.

That’s S3.6: no writes, no randomness—just a crisp branch state and a container that will become `country_set` after S6, with all contracts pinned to your dictionary and schemas.

---



