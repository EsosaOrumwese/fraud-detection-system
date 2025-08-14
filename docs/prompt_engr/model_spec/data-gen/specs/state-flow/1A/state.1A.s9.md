# S9 — Post-write validation & hand-off

## S9.1 Scope, inputs, outputs

**Purpose.** Prove that the immutable egress produced by 1A is (i) schema-valid, (ii) internally consistent with all upstream 1A artefacts and RNG logs, and (iii) statistically sane within governed corridors. On success, emit a signed **validation bundle** and a `_passed.flag` that authorizes the 1A→1B hand-off for the given `manifest_fingerprint`.

**Inputs (read-only).**

1. **Egress**: `outlet_catalogue` partition `seed={seed}/fingerprint={manifest_fingerprint}` with schema `schemas.1A.yaml#/egress/outlet_catalogue`. Key/order and semantics (no inter-country order): as per schema + policy.
2. **Allocation caches**: `country_set` and `ranking_residual_cache_1A` for `(seed, parameter_hash)`.
3. **Diagnostic/eligibility caches**: `hurdle_pi_probs`, `sparse_flag`, `crossborder_eligibility_flags` (parameter-scoped).
4. **RNG evidence**: `rng_audit_log` (run-scoped) and structured rng event logs per label (e.g., `gumbel_key`, `dirichlet_gamma_vector`, `residual_rank`, `sequence_finalize`) under `schemas.layer1.yaml#/rng/...`. (Catalog referenced by registry & dictionary.)
5. **Lineage keys**: `parameter_hash` (from S0), `manifest_fingerprint`, `seed`, `run_id`. (S0 definitions & invariants.)

**Outputs.**

* **`validation_bundle_1A`** (zip) at `data/layer1/1A/validation/fingerprint={manifest_fingerprint}/`, with internal `index.json` matching `schemas.1A.yaml#/validation/validation_bundle`.
* **`_passed.flag`** at the same folder, whose content hash equals the bundle hash (registry contract).
* **Hand-off condition to 1B**: 1B may consume `outlet_catalogue` (egress) **iff** `_passed.flag` exists for the partition and matches the bundle digest. Country order is **only** in `country_set.rank`; 1B **must** join it when it needs inter-country sequencing.

---

## S9.2 Notation (per merchant/country)

For merchant $m$ and legal country $i$:

* $n_{m,i}$ = `final_country_outlet_count` in `outlet_catalogue`.
* $s_{m,i,k}\in\{1,\dots,n_{m,i}\}$ = `site_order` of the $k$-th outlet row.
* $\text{id}_{m,i,k}\in\{000000,\dots,999999\}$ = 6-digit `site_id` string for that row.
* $H_m\in\{0,1\}$ = `single_vs_multi_flag` (1 = multi-site).
* $N^{\text{raw}}_m\in\mathbb{Z}_{\ge 1}$ = `raw_nb_outlet_draw` on the home-country row (pre-spread).
* $R_{m,i}\in[0,1)$ = `ranking_residual_cache.residual` (persisted residual) for $(m,i)$.
* $r_{m,i}\in\{1,2,\dots\}$ = `ranking_residual_cache.residual_rank` (1 = largest).
* $\pi_m\in[0,1]$ = hurdle probability from `hurdle_pi_probs` (if cache enabled).

RNG log objects:

* **Audit envelope** $E=(\text{algo},S_{\text{master}},C_0,\ldots)$ from `rng_audit_log`.
* **Event traces** $T_\ell=\{(\text{before},\text{draws},\text{after},\text{key})\}$ for label $\ell\in$ {`gumbel_key`,`dirichlet_gamma_vector`,`residual_rank`,`sequence_finalize`,…}.

---

## S9.3 Structural validations (schemas, keys, FK)

All checks are **must-pass**; any violation aborts S9 with a reproducible diff inside the bundle.

### (A) Schema conformance

Validate every file against its authoritative JSON-Schema:

* `outlet_catalogue` → `schemas.1A.yaml#/egress/outlet_catalogue`; primary key is `["merchant_id","legal_country_iso","site_order"]`; ordering is `["merchant_id","legal_country_iso","site_order"]`. Inter-country order is intentionally **not encoded**.
* `country_set` → `#/alloc/country_set` (rank carries inter-country order; 0 = home).
* `ranking_residual_cache_1A` → `#/alloc/ranking_residual_cache`.

### (B) Primary/unique keys

* Uniqueness:

  $$
  \big|\text{rows in } \texttt{outlet_catalogue}\big|\;=\;\big|\text{unique }(\texttt{merchant_id},\texttt{legal_country_iso},\texttt{site_order})\big|.
  $$

  Similarly enforce the declared primary keys of `country_set` and `ranking_residual_cache_1A`.

### (C) Foreign keys / lineage

* Every `legal_country_iso` and `home_country_iso` must be valid ISO-3166-1 alpha-2 and appear in the canonical ingress table referenced by schema FKs.
* `manifest_fingerprint` is a 64-hex string on **every** row and equals the partition’s `fingerprint`.

---

## S9.4 Cross-dataset invariants (exact equalities)

All equalities below are checked with integer/bit-exact comparisons.

1. **Site count realization** (per $m,i$):

   $$
   n_{m,i} \;=\; \#\{\text{rows in } \texttt{outlet_catalogue} \text{ for } (m,i)\}.
   $$

   And `site_order` is a permutation of $\{1,\dots,n_{m,i}\}$ with no gaps/dupes.

2. **Country-set coverage & order** (per $m$):

   1) **Home uniqueness.** `country_set` has **exactly one** row with `is_home=true` and `rank=0`.  
      Its `country_iso` must equal the `home_country_iso` present on every egress row for $m$.

   2) **Foreign rank contiguity (no gaps/dupes).** Let $K_m$ be the number of non-home rows for merchant $m$ in `country_set`.  
      All non-home rows must satisfy $\texttt{rank} \in \{1,\dots,K_m\}$ and, for each $i \in \{1,\dots,K_m\}$, there is **exactly one** row with `rank=i`.

   3) **Order = Top-K by Gumbel key.** Let $S$ be the list of **foreign** ISO codes for merchant $m$ sorted by:
      - primary key: descending `gumbel_key.key`,  
      - secondary tie-break: ascending ISO code (lexicographic).
      
      Then the set of non-home `country_set.country_iso` equals the set in $S$, **and** their order by increasing `rank` equals the order of $S$.  
      Any mismatch in membership or order ⇒ **failure**.

3. **Allocation conservation** (per $m$):
   Let $\mathcal{I}_m$ be legal countries in `country_set`. Then

   $$
   \sum_{i\in\mathcal{I}_m} n_{m,i} \;=\; N^{\text{raw}}_m,
   $$

   i.e., the integerized cross-border spread sums back to the **accepted NB draw**. (The left side is recomputed from egress; the right side read from the home-country row’s `raw_nb_outlet_draw`.)

4. **Largest-remainder tie-break reproducibility** (per $m$):
   Sorting $R_{m,i}$ descending gives ranks $r_{m,i}$, which must match the persisted `residual_rank`. Let $q_{m,i}$ be the *pre-integer* fractional allocations; S9 recomputes $R_{m,i}=\mathrm{frac}(q_{m,i})$ from the deterministic inputs used in 1A (no extra RNG), and checks both `residual` and `residual_rank`. (This is the stability contract captured by the residual cache.)

5. **Site-ID sequencing** (per $(m,i)$):
   If we define the site-id integer $u_{m,i,k}$ as the lexicographic index of `site_order=k` (1-based), then

   $$
   \text{id}_{m,i,k} \;=\; \text{zpad6}(u_{m,i,k}).
   $$

   This is compared against every row’s `site_id`. Additionally, validators must confirm that **exactly one** `sequence_finalize` event exists for the $(m,i)$ block (see §S9.5), without implying any per-site event mapping.

6. **`sequence_finalize` cardinality** (global equality):

   $$
   \sum_{(m,c)} \mathbf{1}\{\,n_{m,c}>0\,\} \;=\; \#\text{rows in }\texttt{rng_event_sequence_finalize}.
   $$

   Any mismatch is a **structural failure**.

---

## S9.5 RNG determinism & replay checks

Let $E$ be the audit envelope and $T_\ell$ the event traces for label $\ell$.

1. **Envelope identity.** Verify audit fields: algorithm = `"philox2x64-10"`, master seed equals the `global_seed` column in every egress row, and `(parameter_hash, manifest_fingerprint)` match the partition. (One-to-many equality.)

2. **Per-label draw accounting.** For each label $\ell$, sum the `draws` over $T_\ell$ and verify that the post-label counter advance equals the sum of declared draws. Formally, if $C^\text{before}_{\ell,1}$ and $C^\text{after}_{\ell,|T_\ell|}$ are the first/last counters:

   $$
   C^\text{after}_{\ell,|T_\ell|}-C^\text{before}_{\ell,1} \;=\; \sum_{e\in T_\ell} e.\texttt{draws}.
   $$

   (Integers in the Philox 128-bit counter space.)

3. **Event cardinalities** (must match process logic):

   * `gumbel_key`: exactly one draw per (merchant, candidate foreign country).
   * `dirichlet_gamma_vector`: **one** vector draw per merchant when $K\!+\!1>1$; none when $K=0$.
   * `residual_rank`: exactly once per $(m,i)$ with $n_{m,i}\ge 0$.
   * `sequence_finalize`: **exactly one non-consuming event per $(m,i)$ with $n_{m,i}>0$** (envelope counters must satisfy `before == after`, `draws = 0`).  
     Global count equality is enforced in §S9.4(6).

4. **Replay spot-checks.** For a deterministic sample of $(m,i)$, re-draw the first few variates implied by `gumbel_key`/`dirichlet_gamma_vector` from the audited `(seed,counter)` and compare to logged `key`/`gamma` payloads; any mismatch aborts with a reproducer path. (Practice codified in the assumptions doc for RNG audit.)

5. **Trace reconciliation (logs vs events).** For each event stream listed in the dataset dictionary, let
   - $D_{\text{trace}}(\ell)$ be the sum of `draws` over all `rng_trace_log` rows for `(module, substream_label=\ell)$, and
   - $D_{\text{events}}(\ell)$ be $\sum_{e\in T_\ell} e.\texttt{draws}$ from the structured RNG event stream for label $\ell$.
   
   Validators must prove
   $$
   D_{\text{trace}}(\ell) \;=\; D_{\text{events}}(\ell)
   $$
   for every label $\ell$. Any mismatch is a **structural failure** recorded in `rng_accounting.json`.

6. **Budget spot-checks (consistency with expected draw budgets).**
   - **Hurdle.** Let $\mathcal{M}_\star=\{\,m:\ 0<\pi_m<1\,\}$. Require
     $$
     |\mathcal{M}_\star| \;=\; D_{\text{events}}(\text{``hurdle_bernoulli''}),
     $$
     since each such merchant consumes exactly one uniform (deterministic branches consume 0).
   - **NB Gamma.** For `gamma_component` (context = "nb"), require
     $$
     \frac{D_{\text{events}}(\text{``gamma_component''})}{3} \;=\; \sum_m \big(\texttt{nb_final.nb_rejections}_m + 1\big),
     $$
     i.e., total attempts implied by draws/3 equals (rejections + first acceptance).
   - **Dirichlet.** For `dirichlet_gamma_vector`, compute the implied total attempts as
     $$
     A_{\text{tot}} \;=\; \Big\lfloor \frac{D_{\text{events}}(\text{"dirichlet_gamma_vector"})}{3} \Big\rfloor.
     $$
     Confirm this against the per-merchant vector structure (array lengths and constraints) in the logged events; additionally, the validator should verify that
     $$
     D_{\text{events}}(\text{``dirichlet_gamma_vector''}) \;=\; 3\,A_{\text{tot}} \;+\; \#\{\,\alpha_i<1\,\},
     $$
     reflecting the extra one-uniform power step for components with $\alpha_i<1$ (per S0.3.6/S2.x).

7. **Sparse lineage linkage (S5 → S6)**:
   - Let $\kappa_m$ be the settlement currency for merchant $m$, and let $M_m$ be the number of **foreign candidate countries** for $m$ used by the Gumbel-Top-$K$ selection in S6 (i.e., the count of candidates **excluding** the home country).
   - If `sparse_flag(κ_m) = true`, then the emitted Gumbel payload weights for merchant $m$ must be equal-split:
      for every candidate $j \in \{1,\dots,M_m\}$ with an associated event in `gumbel_key`,
      $$
      \big|\, \texttt{gumbel_key.weight}_{m,j} - \tfrac{1}{M_m} \,\big| \;\le\; 10^{-12}.
      $$
      The validator computes $M_m$ as the number of `gumbel_key` entries for merchant $m$ among **foreign** candidates and asserts the bound. Any violation ⇒ **failure**.
---

## S9.6 Statistical corridors (release-time sanity)

Release requires all corridor tests to pass; metrics are written into the bundle with thresholds.

1. **Hurdle calibration (optional if `hurdle_pi_probs` present).**
   Empirical multi-site rate:

   $$
   \widehat{\pi}\;=\;\frac{1}{|\mathcal{M}|}\sum_{m\in\mathcal{M}} H_m.
   $$

   Model-implied average:

   $$
   \bar{\pi}\;=\;\frac{1}{|\mathcal{M}|}\sum_{m\in\mathcal{M}}\pi_m.
   $$

   Check $|\widehat{\pi}-\bar{\pi}|\le \varepsilon_\pi$ (default $\varepsilon_\pi=0.02$). Record both and the absolute deviation in the bundle.

2. **Integerization fidelity (largest-remainder).**
   For each merchant, compute the L1 rounding error of pre-integer allocations $q_{m,i}$ vs. realized shares $n_{m,i}/N^{\text{raw}}_m$. The contract is **exact conservation** (zero global error), but we also report

   $$
   \Delta_m \;=\; \sum_{i} \left| \frac{n_{m,i}}{N^{\text{raw}}_m} - q_{m,i} \right|
   $$

   and require $\max_m \Delta_m \le \varepsilon_{\text{LRR}}$ (default $10^{-12}$, numerical guard).

3. **Sparsity behavior.**
   Let $\widehat{\rho}=$ fraction of currencies flagged `sparse_flag=1`. Require $|\widehat{\rho}-\rho_{\text{expected}}|\le \varepsilon_\rho$ where $\rho_{\text{expected}}$ is derived from the parameterized sparsity rule. (Both $\widehat{\rho}$ and the bound go into the metrics table inside the bundle.)

4. **ZTP acceptance (for foreign-count draw $K$).**
   From RNG events that implement the zero-truncated draw, compute the acceptance rate $\widehat{a}$ and assert it lies in an operational corridor $[a_L,a_U]$ (configured; reported). This is tracked because CI monitoring explicitly calls out **ZTP stats** among 1A drift metrics.

---

## S9.7 Bundle contents & signing

The validator emits a **ZIP bundle** with an index conforming to `schemas.1A.yaml#/validation/validation_bundle`. Minimal contents:

* `index.json` — table of artefacts (plots/tables/diffs/summaries).
* `schema_checks.json` — per-dataset pass/fail + violations.
* `key_constraints.json` — PK/UK/FK results.
* `rng_accounting.json` — per-label draw counts and replay spot-checks.
* `metrics.csv` — corridor metrics (π gap, ZTP acceptance, sparsity rate, LRR max error, etc.).
* `diffs/` — when applicable (e.g., residual-rank mismatches).

Compute `SHA256(bundle)` and write `_passed.flag` whose digest equals that hash; the registry states this flag certifies the config hash passed validation.

---

## S9.8 Failure semantics

* **Hard fail**: any schema violation; PK/UK/FK breach; RNG replay mismatch; conservation failure $\sum_i n_{m,i}\neq N^{\text{raw}}_m$; or corridor outside bounds. The bundle still materializes with full diagnostics; `_passed.flag` is **not** written.
* **Soft warn**: numerical guard trips (e.g., $\varepsilon_{\text{LRR}}$ exceeded but conservation holds); warnings are recorded and can be escalated via release policy.

---

## S9.9 Hand-off to 1B (contract)

On success:

* 1B **reads** `outlet_catalogue` (seed/fingerprint partition) and **must** join `country_set` to obtain inter-country order; `outlet_catalogue` only carries **within-country** `site_order`. This naming/semantics are locked by the schema authority policy.
* 1B discovery uses the artefact registry entry for `outlet_catalogue` (path, partitioning, and schema pointer), which declares it cross-layer and final for 1A.

---

### Inputs (recap)

* `outlet_catalogue(seed,fingerprint)`; `country_set(seed,parameter_hash)`; `ranking_residual_cache_1A(seed,parameter_hash)`; `hurdle_pi_probs(parameter_hash)` (optional); `sparse_flag(parameter_hash)`; `crossborder_eligibility_flags(parameter_hash)`; `rng_audit_log` + rng event logs; and lineage keys `(seed, parameter_hash, manifest_fingerprint, run_id)`.

### Outputs (recap)

* `validation_bundle_1A(fingerprint)` (**zip** with `index.json` as per schema) and `_passed.flag` whose digest equals the bundle hash; authorization for 1B to proceed on this `(seed,fingerprint)` partition.