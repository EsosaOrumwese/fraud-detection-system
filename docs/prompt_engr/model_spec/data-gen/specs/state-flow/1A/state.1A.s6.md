# S6 — Foreign country selection (Gumbel-top-$K$), deterministic & auditable

## S6.0 Pre-screen/cap with candidate size $M$

Let $\mathcal{D}(\kappa_m)$ be the member-country set for the merchant’s currency $\kappa_m$ after S5 expansion. Exclude the **home** ISO and define
$$
M_m := \big|\mathcal{D}(\kappa_m)\setminus\{\text{home}\}\big|,\qquad
K_m^\star := \min\big(K_m,\; M_m\big).
$$

**Rules.**
* If $M_m = 0$, set $K_m^\star = 0$ and **skip Gumbel** (S6). Proceed to S7 with $\mathcal{C}_m = \{\text{home}\}$ and reason `"no_candidates"` recorded in the validation bundle.
* If $M_m < K_m$, proceed with $K_m^\star$ (capped) in S6. Validators assert $0 \le K_m^\star \le M_m$.
* No schema changes; `country_set` remains the sole authority for cross-country order emitted by S6.


## S6.1 Universe, symbols, authority

* **Domain.** Evaluate this state **only** for merchants $m$ that:

  1. are multi-site (`is_multi=1` from S1),
  2. passed the cross-border gate (`is_eligible=1` in S3), and
  3. have an accepted **foreign count** $K_m\ge 1$ from S4.
     The ordered result is persisted to the **authoritative** `country_set` (rank 0 = home, ranks $1..K_m$ = selected foreigns).

* **Authoritative schemas & event streams.**

  * RNG event stream `gumbel_key` (one **uniform** per candidate, always logged), schema `schemas.layer1.yaml#/rng/events/gumbel_key`.
  * Allocation dataset `country_set` (ordered set, rank carried as a column), schema `schemas.1A.yaml#/alloc/country_set`.
  * Dataset dictionary pins paths/partitions for both.

* **Design choice (selection mechanism).** Weighted sampling **without replacement** uses **Gumbel-top-$K$** with keys

  $$
  z_i \;=\; \log w_i \;-\; \log\!\bigl(-\log u_i\bigr),\qquad u_i\sim U(0,1)\ \text{(open interval)}.
  $$

  Select the $K_m$ largest keys; ties resolved lexicographically by ISO. This consumes **exactly one** uniform per candidate and is fully replayable.

---

## S6.2 Inputs (per merchant $m$)

* **Identity & home:** $\texttt{merchant_id}_m$, home country $c\in\mathcal{I}$. (From ingress/S0.)

* **Foreign count:** $K_m\in\{1,2,\dots\}$ from S4. (S4 event lineage in RNG envelope.)

* **Candidate prior weights (deterministic):** read $\kappa_m$ from `merchant_currency` (S5.0), then use the **currency→country weights cache** from S5, `ccy_country_weights_cache` keyed by $\kappa_m$:

  $$
  \{(\kappa_m, i, w_i^{(\kappa_m)}) : i\in \mathcal{D}(\kappa_m)\subset\mathcal{I}\},\quad \sum_{i} w_i^{(\kappa_m)}=1.
  $$

  (S5 produced and persisted these with group-sum-equals-1 constraint.)

* **RNG lineage:** `seed`, `parameter_hash`, `manifest_fingerprint`, and S0’s Philox sub-stream discipline; S6 uses the sub-stream labelled **"gumbel_key"**. (Envelope is required on every event.)

---

## S6.3 Candidate set and renormalisation

From the currency expansion, form the **foreign** candidate set by excluding the home ISO:

$$
\mathcal{F}_m \;=\; \mathcal{D}(\kappa_m)\setminus\{c\},\qquad M_m = |\mathcal{F}_m|.
$$

Define the **renormalised** probability vector on $\mathcal{F}_m$:

$$
\tilde w_i \;=\; \frac{w_i^{(\kappa_m)}}{\sum_{j\in\mathcal{F}_m} w_j^{(\kappa_m)}}\quad \text{for } i\in\mathcal{F}_m .
$$

**Guards.**

* If $M_m=0$ (no foreign candidates), **abort** as `no_foreign_candidates` (contradiction with $K_m\ge1$).
* If $K_m>M_m$, **abort** as `insufficient_candidates` (policy: we do **not** collapse $K$; cross-branch consistency requires $K_m\le M_m$).
  The `country_set` schema explicitly encodes rank $0..K_m$ and is the only authoritative order store; enforcing these guards avoids downstream inconsistencies.

---

## S6.4 RNG protocol & event contract

**Substream label:** $\ell=$ `"gumbel_key"`. Use the keyed substream mapping (S0.3.3) for $(\ell,m)$. Exactly **one** uniform is drawn per candidate $i\in\mathcal{F}_m$; open-interval `u01` per S0.3.4.
**Draw accounting (S0.3.6).** Event `draws` must equal the number of candidate countries evaluated for that merchant.
**Uniforms & mapping:** uniforms via **S0.3.4**; keyed mapping via **S0.3.3**.

**Per-candidate event (always emitted):**
$$
u_i \sim U(0,1), \quad z_i = \log\tilde{w}_i - \log(-\log u_i).
$$

Emit a row to `logs/rng/events/gumbel_key/...` with payload:
$$
\{\texttt{merchant_id},\ \texttt{country_iso}=i,\ \texttt{weight}=\tilde{w}_i,\ \texttt{u}=u_i,\ \texttt{key}=z_i,\ \texttt{selected},\ \texttt{selection_order}\}
$$
plus the RNG envelope fields. Schema `#/rng/events/gumbel_key` requires these fields and types.

---

## S6.5 Selection rule (mathematical)

Let the total order $\succ$ on candidates be defined by

$$
i \succ j \iff
\big(z_i > z_j\big)\ \text{or}\ \big(z_i=z_j\ \text{and}\ i<_{\mathrm{ASCII}} j\big).
$$

Define the selected set $S_m\subset \mathcal{F}_m$ as the top $K_m$ elements under $\succ$, with **selection order** $r=1,\dots,K_m$ induced by the sort. Each selected candidate has `selected=true` and `selection_order=r`; others have `selected=false`, `selection_order=null`. (Tie-break by ISO ASCII is mandated by the assumptions and encoded in our invariants below.)

---

## S6.6 Persistence (authoritative ordered set)

After selection, persist the **ordered** set for the merchant to `country_set` (partitioned by `{seed, parameter_hash}`) with exactly $K_m+1$ rows:

$$
\begin{aligned}
&(\texttt{merchant_id}=m,\ \texttt{country_iso}=c,\ \texttt{is_home}=\texttt{true},\ \texttt{rank}=0,\ \texttt{prior_weight}=\texttt{null}),\\
&(\texttt{merchant_id}=m,\ \texttt{country_iso}=i_r,\ \texttt{is_home}=\texttt{false},\ \texttt{rank}=r,\ \texttt{prior_weight}=\tilde w_{i_r}),\quad r=1,\dots,K_m,
\end{aligned}
$$

where $(i_1,\dots,i_{K_m})$ is the Gumbel order. The schema defines PK $(\texttt{merchant_id},\texttt{country_iso})$, FK on ISO, and carries `rank` as the stable order carrier. **This dataset is the only authoritative place for cross-country order**; 1B must join here if it needs order.

---

## S6.7 Determinism & correctness invariants

* **I-G1 (bit-replay).** For fixed $(\tilde w,\ K_m,\ \texttt{seed},\texttt{parameter_hash},\texttt{manifest_fingerprint})$, the uniform vector $(u_i)_{i\in\mathcal{F}_m}$, keys $(z_i)$, selected set $S_m$, and ranks are **bit-identical** across runs. (Counter-based Philox + fixed sub-stream label + fixed one-draw-per-candidate discipline.)
* **I-G2 (event coverage).** Exactly **$M_m$** `gumbel_key` events per merchant (one per candidate). Selected countries must have `selected=true` and `selection_order\in\{1,\dots,K_m\}`; non-selected must have `selected=false` and `selection_order=null`. Missing or extra rows is a structural failure.
* **I-G3 (weight & ISO constraints).** Every event row satisfies `weight∈(0,1]` with $\sum_{i\in\mathcal{F}_m}\tilde w_i=1$ (within $10^{-12}$ pre-logging), and `country_iso` passes the FK to the canonical ISO set. Violations abort.
* **I-G4 (tie-break determinism).** If $z_i=z_j$ at binary64, order is by ASCII ISO; therefore the selection order is a **pure function** of $(\tilde w,\ u)$. (Schema stores `selection_order` to make this explicit.)
* **I-G5 (country_set coherence).** Persist exactly one home row (`rank=0`) plus $K_m$ foreign rows in the **same** order as the `gumbel_key` winners. Any mismatch between `country_set.rank` and the winners’ `selection_order` is a validation failure.

---

## S6.8 Failure modes (abort semantics)

* **Insufficient candidates:** $K_m>M_m$ or $M_m=0$ (see §S6.3).
* **Missing weights:** no cache row for $\kappa_m$ in `ccy_country_weights_cache` → abort (input precondition of S5/S6).
* **Schema/envelope violation:** any `gumbel_key` row missing required fields or RNG envelope; `u` not in open interval; invalid ISO → abort.
* **Order persistence gap:** a merchant with any `gumbel_key.selected=true` but missing corresponding `country_set` rows → validation abort.

---

## S6.9 Inputs → outputs (state boundary)

* **Inputs (per merchant):**
  $K_m\ge1$ (from S4); home ISO $c$; currency $\kappa_m$; candidate prior weights $\{w_i^{(\kappa_m)}\}$ from `ccy_country_weights_cache`; RNG lineage (`seed`, `parameter_hash`, `manifest_fingerprint`).

* **Outputs:**

  1. **RNG event stream:** `logs/rng/events/gumbel_key/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl` with **$M_m$** rows per merchant, schema `#/rng/events/gumbel_key`.
  2. **Allocation dataset:** `data/layer1/1A/country_set/seed={seed}/parameter_hash={parameter_hash}/…` with $K_m+1$ rows (home `rank=0` + $K_m$ foreigns in **Gumbel order**), schema `#/alloc/country_set`.
