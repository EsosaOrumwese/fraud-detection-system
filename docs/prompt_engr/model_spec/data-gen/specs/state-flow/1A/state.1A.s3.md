# S3 — Cross-border eligibility & branch gate (deterministic, pre-ZTP)

## S3.1 Inputs (from S0/S1/S2 + artefacts)

For each merchant $m$ that exited S2 with an accepted domestic count $N_m\ge 2$ (i.e., `is_multi(m)=1` from S1):

* **Identity & home:** $(\texttt{merchant_id}_m,\ \texttt{home_country_iso}_m=c)$ from ingress.
* **Deterministic flags (materialised in S0):** a row in
  $\texttt{crossborder_eligibility_flags}$ (partitioned by `{parameter_hash}`) with schema fields
  $(\texttt{merchant_id},\ \texttt{is_eligible},\ \texttt{reason},\ \texttt{rule_set})$.
* **Previously computed state:** $N_m\in\{2,3,\dots\}$ from S2; $\texttt{mcc}_m$, $\texttt{channel}_m$ from ingress/S0.
* **Lineage:** `parameter_hash`, `manifest_fingerprint` (for partitioning + validation joins).

**Domain of S3.** S3 is evaluated **only** for merchants with `is_multi=1`. Single-site merchants (S1 outcome `false`) bypass S2–S6 and go straight to S7 per the journey spec.

---

## S3.2 Eligibility function and deterministic decision

Let the governed rule family be

$$
\mathcal{E} \subseteq \mathbb{N}\times\{\mathrm{CP},\mathrm{CNP}\}\times \mathcal{I},
$$

defined by configuration (no randomness). The **eligibility indicator** is

$$
\boxed{\ e_m \;=\; \mathbf{1}\Big\{ \big(\texttt{mcc}_m,\texttt{channel}_m,\texttt{home_country_iso}_m\big) \in \mathcal{E} \Big\}\ }.
$$

S0 has already materialised $e_m$ to `crossborder_eligibility_flags.is_eligible` with `reason` and `rule_set`; in S3 we **read** that row (no mutation).

Define the **gate**:

$$
\boxed{\ \text{eligible branch if } e_m=1;\quad \text{domestic-only branch if } e_m=0.\ }
$$

Only merchants on the eligible branch are allowed to enter the ZTP foreign-count stage (S4). This matches the design: “Only merchants that passed the hurdle and are designated to attempt cross-border expansion enter this branch.”

---

## S3.3 Derived (in-memory) state set for downstream

Introduce the country-set **container** to be filled later:

$$
\mathcal{C}_m \subseteq \mathcal{I},\quad \text{with ordered ranks to be persisted in `country_set` (rank 0 = home).}
$$

* **If $e_m=0$** (domestic-only):

  $$
  \boxed{\ K_m \leftarrow 0,\quad \mathcal{C}_m \leftarrow \{c\}\ (\text{home only, rank 0}),\quad \text{skip S4–S6}\to\text{S7}. }
  $$

  (No stochastic action; the ordered set $\{c\}$ will be persisted when `country_set` is written for all merchants, with only `rank=0` present.)

* **If $e_m=1$** (eligible for cross-border):

  $$
  \boxed{\ \mathcal{C}_m \leftarrow \{c\}\ (\text{rank 0 reserved}),\quad \text{proceed to S4 (ZTP for }K_m\ge1). }
  $$

  (The eventual `country_set` will contain `rank=0` for $c$ plus $K_m$ foreign ranks selected in S6.)

**Note.** `country_set` is the **only** authoritative store for cross-country order; S3 only defines the branch and initial contents (home at rank 0). Persistence happens after selection (S6).

---

## S3.4 Determinism & correctness invariants

* **I-EL1 (no RNG).** S3 performs **no** random draws; outputs depend only on deterministic inputs (`crossborder_eligibility_flags`, ingress fields). Therefore S3 is bit-replayable by data alone.
* **I-EL2 (dataset contract).** Every merchant reaching S3 **must** have exactly one row in `crossborder_eligibility_flags` under the active `{parameter_hash}`. Missing or duplicate rows are structural failures. Schema fields must satisfy: `merchant_id` present, `is_eligible` boolean, `rule_set` non-null; `reason` may be null only if `is_eligible=true`.
* **I-EL3 (branch coherence).**

  * If $e_m=0$: there must be **no** ZTP/Gumbel/Dirichlet RNG events (`ztp_*`, `gumbel_key`, `dirichlet_gamma_vector`) for $m$. (Validators check absence.)
  * If $e_m=1$: there **must** exist subsequent ZTP events for $m$ (S4), or an explicit abort event if capped; absence → validation failure.
* **I-EL4 (country_set consistency).** When `country_set` is eventually persisted (S6), merchants with $e_m=0$ must have exactly **one** row: $(\texttt{merchant_id}=m,\ \texttt{country_iso}=c,\ \texttt{is_home}=true,\ \texttt{rank}=0)$; merchants with $e_m=1$ must have this home row **plus** $K_m$ foreign rows (ranks 1..$K_m$).

---

## S3.5 Failure modes (abort semantics)

* **Missing flag row:** no `crossborder_eligibility_flags` row for $m$ under active `{parameter_hash}` → abort (schema/lineage violation).
* **Inconsistent branch:** presence of any S4–S6 RNG events for $m$ while `is_eligible=false` → abort during validation (contradicts I-EL3).
* **Illegal home ISO:** $c\notin \mathcal{I}$ (violates FK in `country_set`) → abort before persistence.

---

## S3.6 Outputs (state boundary)

S3 produces **no new datasets** (deterministic gate), but it fixes the **branch state** for each multi-site merchant:

* **Authoritative deterministic input carried forward:**
  $e_m\in\{0,1\}$ from `crossborder_eligibility_flags`.
* **In-memory state for downstream:**

  $$
  \boxed{
  \begin{cases}
  \text{domestic-only:}& (K_m\!=\!0,\ \mathcal{C}_m\!=\!\{c\})\ \Rightarrow\ \text{skip S4–S6}\to\text{S7},\\[3pt]
  \text{eligible:}& (\mathcal{C}_m\!=\!\{c\})\ \Rightarrow\ \text{enter S4 (ZTP for }K_m\ge1).
  \end{cases}}
  $$
* **Implicit contract for later persistence:** when `country_set` (partitioned by `{seed,parameter_hash}`) is written, S3’s decision must be reflected exactly as per **I-EL4**.

---

### Remark on placement of responsibilities

S3 is the **policy firewall**: it enforces the documented rule that “only merchants designated to attempt cross-border expansion” may proceed to ZTP. The ZTP itself (S4), the currency→country expansion (S5), the Gumbel-top-k selection (S6), and the `country_set` persistence occur **after** this gate.