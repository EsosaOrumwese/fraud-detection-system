# State vector

For merchant $m$, the evolving state is

$$\mathcal{S} = \big(m,\, \text{home\_iso},\, \text{MCC},\, \text{channel},\, \text{GDP\_bucket},\, \pi,\, \text{flag},\, N,\, \text{elig},\, K,\, \mathcal{C},\, {\alpha},\, \mathbf{w},\, \mathbf{n},\, \text{seq}\big)$$

with meanings introduced as we enter each state. All draws are Philox-based and logged to per-event JSONL streams (hurdle, NB components, ZTP, Gumbel keys, Dirichlet gamma vectors, residual ranks, stream jumps, sequence finalize).

***

# S0 — Prepare features, parameters, and lineage

**Goal:** assemble fixed inputs, compute deterministic quantities, and bind lineage.

* Inputs: normalised merchant row (`merchant_id`, `home_country_iso`, `MCC`, `channel`), GDP-per-capita vintage (for buckets), canonical ISO list.
* Build the **design vector** $x_m = [\text{intercept}, \text{MCC one-hots}, \text{channel one-hots}, \text{GDP bucket}]$. Load hurdle/NB coefficients; select **cross-border hyperparams** ($\theta$-vector, Dirichlet $\alpha$ lookup).
* Compute or load $\pi_m$ (logit-hurdle success prob) to `hurdle_pi_probs`.
* Apply **cross-border eligibility rules** $\rightarrow$ `crossborder_eligibility_flags`.
* Bind **parameter\_hash/manifest\_fingerprint** (lineage keys used throughout paths and rows). `country_set` partitions on $\{\text{seed}, \text{parameter\_hash}\}$; `outlet_catalogue` on $\{\text{seed}, \text{fingerprint}\}$.

**Leaves:** $\mathcal{S}$ enriched with $x_m$, $\pi_m$, eligibility flag, and lineage keys.

***

# S1 — Hurdle (single vs multi)

**Goal:** decide if merchant is multi-site.

* Draw $u \sim U(0,1)$; if $u < \pi_m$ set `flag` = multi, else single with $N = 1$. Log `hurdle_bernoulli`.
* Single-site merchants skip S3–S6 by design (no cross-border path).

**Branch:**
- **Single:** set $K = 0$, $\mathcal{C} = \{\text{home}\}$, go to S7 (integerisation becomes trivial) $\rightarrow$ S8.
- **Multi:** proceed to S2.

***

# S2 — Domestic outlet count $N$ (multi-site only)

**Goal:** sample $N \ge 2$ for the home country.

* NB via Poisson–Gamma mixture; **reject** until $N \in \{2,3,\dots\}$. Log `gamma_component`, `poisson_component`, `nb_final`. Corridor: overall rejection rate $\in [0,0.06]$, per-merchant p99 $\le 3$.

**Leaves:** $N$ and diagnostics.

***

# S3 — Check cross-border eligibility (gate before ZTP)

**Goal:** enforce policy before trying foreign spread.

* Read `crossborder_eligibility_flags` (`is_eligible`, reason, rule\_set). Only **multi-site & eligible** merchants enter ZTP.

**Branch:**
- **Ineligible:** set $K = 0$, $\mathcal{C} = \{\text{home}\}$ $\rightarrow$ S7.
- **Eligible:** proceed to S4.

***

# S4 — Foreign country count $K$ (ZTP)

**Goal:** sample number of foreign countries.

* $K \sim \text{ZTPoisson}(\lambda_{\text{extra}})$ with $\lambda_{\text{extra}} = \exp(\theta_0 + \theta_1 \log N + \theta_2 X)$, $0 < \theta_1 < 1$. Classical rejection from Poisson until $K \ge 1$; hard cap 64 $\rightarrow$ `ztp_retry_exhausted`. Log `ztp_rejection`.

**Branch:**
- **$K=0$** (didn’t enter S4 or ineligible): $\mathcal{C} = \{\text{home}\}$ $\rightarrow$ S7.
- **$K \ge 1$:** proceed to S5.

***

# S5 — Currency $\rightarrow$ country expansion (weights)

**Goal:** expand currency-level settlement shares to country weights.

* Build currency-level settlement vector; expand to country weights using intra-currency split; if any destination sparse ($<30$ obs), apply **Dirichlet smoothing** $\alpha = 0.5$; if still globally sparse, fallback **equal split** and set `sparse_flag = true`. Renormalise; order countries lexicographically by ISO. Persist `sparse_flag`.

**Leaves:** deterministic weight vector $w^{(\text{ccy} \to \text{iso})}$.

***

# S6 — Select the $K$ foreign countries (ordered)

**Goal:** choose a **stable, ordered** foreign set.

* **Gumbel-top-k**: for each candidate $i$, draw $u_i \sim U(0,1)$, form $\text{key}_i = \log w_i - \log(-\log u_i)$; take the $K$ largest keys; ties by ISO. Log `gumbel_key`.
* Emit `country_set` of length $K+1$: **rank 0** = home; **ranks 1..K** = selected ISO codes **in key order**. `country_set` is the **only** authority for cross-country order.

**Leaves:** ordered legal set $\mathcal{C} = \{\text{home}, c_1, \dots, c_K\}$ with ranks.

***

# S7 — Allocate $N$ across $\mathcal{C}$ (Dirichlet + LRR)

**Goal:** convert $N$ into integer per-country counts.

* Load $\alpha = \alpha(\text{home}, \text{MCC}, \text{channel};\, K)$. Draw $\gamma_i \sim \text{Gamma}(\alpha_i, 1)$; set $w_i = \gamma_i / \sum_j \gamma_j$. Log `dirichlet_gamma_vector`.
* **Largest-remainder rounding:**
  $$a_i = \lfloor N w_i \rfloor, \quad d = N - \sum_i a_i; \quad r_i = (N w_i - a_i)$$
  residuals quantised to **8 dp**; sort $r_i$ desc (ISO secondary key); give $+1$ to the top $d$. Persist $(r_i, \text{residual\_rank})$ to `ranking_residual_cache_1A`; log `residual_rank`. Bound: $\lvert n_i - N w_i \rvert \le 1$.

**Leaves:** integer vector $\mathbf{n} = (n_i)_{i \in \mathcal{C}}$ with $\sum n_i = N$.

***

# S8 — Materialise outlet stubs & sequences (egress)

**Goal:** write `outlet_catalogue` and finalise IDs.

* For each country $i$, emit $n_i$ rows with `site_order` $= 1..n_i$ (within-country). Assign a fixed **6-digit zero-padded** `site_id` sequence per $(\text{merchant}, i)$; overflow $> 999999 \rightarrow$ `site_sequence_overflow`. Log `sequence_finalize`. **Do not** encode cross-country order here; consumers must join `country_set.rank`. Primary key and partitions as per schema.

**Leaves:** `outlet_catalogue` (immutable, per merchant $\times$ legal\_country), `country_set`, and `ranking_residual_cache_1A` ready for 1B.

***

# S9 — Deterministic replay & validation bundle

**Goal:** prove the write is self-consistent.

* Re-read the Parquet, recompute $\mu, \phi, K, \mathbf{w}, \mathbf{n}$, residual ordering, `site_order`, and `site_id`s from stored inputs; **any mismatch aborts**. Package metrics/logs into `validation_bundle_1A`. Stream-jump records allow Philox counter reconstruction even with zero rejections. Absence of any required RNG event is a structural failure.

***

## Handoffs/Firewalls

* **Counts & order:** `outlet_catalogue` fixes the per-country outlet counts and within-country sequencing; `country_set.rank` fixes cross-country order. 1B **must not** change either.
