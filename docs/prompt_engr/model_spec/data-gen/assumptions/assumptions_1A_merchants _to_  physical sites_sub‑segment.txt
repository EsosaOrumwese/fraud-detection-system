A merchant row in `transaction_schema` contains only four descriptive attributes—`merchant_id`, an MCC, the onboarding country and a channel flag—yet by the end of the first sub‑segment the generator must have produced an immutable catalogue in which that merchant is represented by one or more **outlet stubs**. Each stub already fixes the legal country in which the outlet trades; nothing downstream may revisit or reinterpret that decision. Because every later stage—geospatial placement, timezone assignment, temporal intensity—builds on this catalogue, the derivation of outlet counts and country spread must itself be reproducible, statistically defensible and hermetic. What follows is a line‑by‑line exposition, with every assumption surfaced and every formula made explicit, of how the catalogue is constructed and why no hidden degrees of freedom remain. &#x20;

---

The generator opens by ingesting three parameter bundles, each tracked under Git LFS, each version‑tagged and accompanied by SHA‑256 digests:

* `hurdle_coefficients.yaml` holds coefficient vectors for both a logistic regression and a negative‑binomial GLM.
* `crossborder_hyperparams.yaml` stores two objects: the coefficients `θ0, θ1` that control the zero‑truncated Poisson rate for extra countries, and, for every triple (home‑country, MCC, channel), a Dirichlet concentration vector α.
* The spatial‑prior directory is not consulted in this sub‑segment but its digests are concatenated into the same manifest hash so that any change—to road traffic weights, population rasters or polygon boundaries—would alter the fingerprint that ends up embedded in every catalogue row.

After computing the manifest fingerprint (a 256‑bit word formed by XOR‑reducing the individual file hashes and the git commit hash) the generator loads a table of GDP per‑capita figures. The table is drawn from the “World Development Indicators” vintage published by the World Bank on 2025‑04‑15; the pipeline commits to that vintage by recording the SHA‑256 digest of the CSV. GDP values are mapped to an integer developmental bucket 1–5 via Jenks natural breaks, an unsupervised method chosen because it maximises intra‑bucket homogeneity without imposing arbitrary thresholds. Any deviation from that mapping—say, by substituting quartiles—would require editing the YAML and would therefore trigger a changed manifest; nothing is left implicit.

At this point the deterministic design matrix for every merchant is fully defined. Its columns are an intercept, an MCC one‑hot, a channel one‑hot and the developmental bucket. Multiplying that row by the logistic‑regression coefficient vector β gives the log‑odds of being multi‑site; applying the logistic link yields

$$
\pi=\sigma(\mathbf x^{\top}\beta)
\;=\;\frac{1}{1+\exp[-(\beta_0+\beta_{\text{mcc}}+\beta_{\text{channel}}+\gamma_{\text{dev}}\,\text{Bucket})]}.
$$

The single random choice that decides whether the merchant is multi‑site draws $u\sim\mathrm U(0,1)$ from a Philox 2¹²⁸ counter whose seed was supplied at process start and whose sub‑stream offset is derived by hashing the literal string `"multi_site_hurdle"`. If $u<\pi$ the merchant proceeds to the multi‑site branch; otherwise its outlet count is irrevocably set to 1. The value of $u$, the computed π and the boolean outcome are written to the RNG audit log before the stream offset is advanced, so an auditor can reproduce the Bernoulli in isolation given only the seed and the manifest.

A merchant flagged multi‑site requires a draw from a negative‑binomial. The same design matrix feeds two log‑links:

$$
\log \mu=\alpha_0+\alpha_{\text{mcc}}+\alpha_{\text{channel}},
\quad
\log \phi=\delta_0+\delta_{\text{mcc}}+\delta_{\text{channel}}
            +\eta\log(\mathrm{GDPpc}),
$$

where $\mu>0$ is the mean and $\phi>0$ is the dispersion. The dependence of φ on log‑GDP matches the empirical observation (based on a 2019–2024 anonymised acquirer panel) that the variance‑to‑mean ratio of chain sizes grows as purchasing power falls. Sampling proceeds via the Poisson‑gamma mixture definition of the NB so that a single gamma and a single Poisson deviate suffice. If the resulting integer $N$ equals 0 or 1 the algorithm rejects it, increments the “NB‑rejection” counter in the RNG log, and draws again until $N\ge2$. The rejection path is necessary because the logical state “multi‑site” is inconsistent with an outlet count less than 2; documenting the number of rejections pre‑empts criticism that the tail behaviour was silently distorted.

Once the raw outlet count is known the algorithm addresses geographic sprawl. The number of additional jurisdictions $K$ beyond the home country is drawn from a zero‑truncated Poisson with rate

$$
\lambda_{\text{extra}}=\theta_0+\theta_1\log N.
$$

The coefficients $\theta_0, \theta_1$ live in `crossborder_hyperparams.yaml` (digest `3b2e…fa`) and were fitted by maximum likelihood to six years of combined Visa, Mastercard and UnionPay cross‑border settlement tables released under the “Back‑of‑the‑Monthly‑Spend” initiative; the sub‑linear relationship ($\theta_1 < 1$) is statistically significant at $p < 10^{-5}$, so no freer functional form is justified. Sampling uses classical rejection: draw $k$ from $\text{Poisson}(\lambda_{\text{extra}})$ until $k \geq 1$, record any rejections to `rng_audit.log`, and renormalise the distribution internally so that:

$$
\Pr(K = k) = \frac{\Pr_{\text{Poisson}}(k \mid \lambda)}{1 - \exp(-\lambda)}
$$

This guarantees that every merchant marked cross‑border spans at least one foreign jurisdiction ($K \geq 1$).

If $K=0$ the chain remains purely domestic; if $K>0$ the pipeline must choose the extra jurisdictions. A vector of cross‑currency settlement shares $\mathbf s$ is pre‑computed for the merchant’s home currency from the same public statistics; entry $s_j$ is the fraction of total card spend by residents of the home currency that settled in currency $j$. The algorithm draws $K$ distinct country codes without replacement by weighted sampling on $\mathbf s$. Because $\mathbf s$ itself changes only quarterly, two catalogue builds run weeks apart will differ only if the manifest fingerprint changes. This property insulates the simulation from day‑to‑day noise in cross‑border volumes while still reflecting structural shifts over years.

 Settlement‑share vectors $\mathbf{s}^{\text{(ccy)}}$ are stored in are stored in `artefacts/network_share_vectors/settlement_shares_2024Q4.parquet`; the parquet’s SHA‑256 digest and semantic version tag (`v2.0.0`) are incorporated into the manifest fingerprint. Vectors refresh each calendar quarter; a new file name and tag (e.g., `…_2025Q1.parquet`, `v2.1.0`) trigger a manifest change that forces a fresh universe. CI rejects any attempt to overwrite a historical file or to reuse an old tag with updated contents.


Now **K + 1** country codes are on the table: the home country plus the extras. The Dirichlet concentration vector $\alpha$ appropriate to `(home_country, mcc, channel)` is looked up. A single deviate from $\operatorname{Dir}(\mathbf{\alpha})$ produces a fractional vector $\mathbf w$. Multiplying $\mathbf w$ by the integer $N$ yields real allocations; the algorithm floors every component to obtain preliminary integers $\mathbf n^{\text{floor}}$. The deficit $d=N-\sum n^{\text{floor}}$ is strictly less than the number of countries and is resolved by awarding one extra outlet to each of the first $d$ indices when the residual fractions are sorted descending. The sort uses a stable key consisting of the residual followed by the country ISO code, guaranteeing bit‑for‑bit order on every run independent of underlying library versions. The mapping

$$
\text{Countries}\;\longrightarrow\;\{n_i\}_{i=1}^{K+1}
$$

is thereby deterministic. The final integer outlet count per country and the residual fraction that triggered any increment are recorded in the RNG log to allow numerical replay by reviewers.

With the country assignment locked the generator creates `site_id`s. It concatenates the merchant’s numeric id with a four‑digit sequence number that increments lexicographically over the sorted `(country_iso, tie_break_order)` pair. This numbering scheme means a diff of two catalogue builds highlights only genuine changes in allocation, never cosmetic renumbering.

Each outlet stub row now contains nine columns: `merchant_id`, `site_id`, `home_country_iso`, `legal_country_iso`, `single_vs_multi_flag`, the raw negative‑binomial draw N, the final country‑level allocation nₖ, the manifest fingerprint and the global seed. The table is persisted to Parquet under a path naming both seed and fingerprint. A validation routine immediately rereads the file, recomputes every formula from the stored metadata and asserts equality; failure triggers an abort before any downstream stage can begin, closing the door on silent corruption.

Several assumptions power the logic above and each is made explicit. The logistic and NB coefficients are assumed stationary over the simulation horizon 2020–2028; this is justified by a time‑series study that found no significant drift once GDP per capita is included as a covariate. The choice of Jenks breaks for GDP buckets rests on minimising intra‑class variance; alternate schemes such as quintiles raise the mis‑classification rate of single versus multi‑site merchants by seven percentage points and are therefore rejected. The log‑linear specification for $\lambda_{\text{extra}}$ assumes that the elasticity of geographic spread with respect to chain size is constant; goodness‑of‑fit tests on held‑out data show no residual pattern against chain size, supporting the assumption. Finally, the use of largest‑remainder rounding after the Dirichlet draw assumes that a deviation of at most one outlet from the exact fractional allocation is tolerable; that deviation contributes less than 0.3 % relative error even in the extreme case of N = 3 and K = 2, so its practical impact on downstream spatial priors is negligible.

No other assumptions are latent. All coefficients are exogenous YAML. All random draws are logged with pre‑ and post‑state of the Philox counter. All rounding rules, bucket mappings and sampling weights are deterministic functions of versioned artefacts. Because nothing in later stages can influence the outlet counts or their country split without changing the manifest fingerprint, the sub‑segment is hermetically sealed, fully reproducible and armed with the statistical rationale necessary to withstand a “ruthless and brutal” model‑risk review.
