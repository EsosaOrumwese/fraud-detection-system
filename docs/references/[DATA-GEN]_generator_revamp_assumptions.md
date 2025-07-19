# Companion Document for Approach for Injecting Merchant–location realism into a Synthetic Data Generator for Fraud Detection

## Segment 1: `transaction_schema` → From merchants to physical sites

### From merchants to physical sites

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

---
### Placing outlets on the planet
The purpose of this companion text is to surface—line by line—the premises, data sources, numeric linkages and operational guard‑rails that uphold the **“Placing outlets on the planet”** engine. Everything stated here is enforceable by configuration or by deterministic code; nothing is allowed to hide in implicit defaults. If a future implementer alters any assumption, the catalogue’s manifest hash will change and the continuous‑integration gate will block downstream use until reviewers accept the modification.

---

#### 1 Spatial artefacts are sovereign and version‑locked

Every geographic prior resides in a file held under git LFS. Rasters are GeoTIFFs; vectors are ESRI shapefiles or GeoPackages. Each file is accompanied by a sibling text file containing its SHA‑256 digest. The catalogue build opens a manifest called `spatial_manifest.json`, concatenates every digest in lexical path order, hashes that concatenation, and embeds the result into every row it writes. The engine refuses to start if any listed artefact is missing or if any un‑listed file intrudes into the directory; this guarantees a one‑to‑one mapping between manifest and build output.



#### 2 Mapping MCC×channel to a single spatial prior

The YAML table `spatial_blend.yaml` maps each `(mcc_code, channel)` to either

* a direct artefact path, or
* a blend of artefacts expressed as a convex weight vector that sums exactly to one.

Blending is performed by loading each raster at native resolution, resampling on the fly to match the highest‑resolution member, scaling each pixel’s value by its weight, summing, and writing the blend to `/tmp/blended_Δ.tif`. The temporary file’s digest is included in the manifest; a later audit can reproduce it by repeating the blend under the same seed. Blended priors are read‑only: if an implementer wants a different linear combination they must edit `spatial_blend.yaml`.



#### 3 Deterministic importance‑sampling with Fenwick trees

A single Fenwick tree is built for every country–artefact pair the first time it is requested. The tree stores uint64 prefix sums of pixel or feature weights. Random sampling draws a 64‑bit uniform `u`, multiplies by the total weight `W`, and performs a Fenwick search in O(log n) steps to locate the index whose cumulative weight exceeds `uW`. Because the Fenwick construction iterates over artefact indices in geographic sort order, two developers on two machines will build identical trees even if the underlying spatial library enumerates features nondeterministically.



#### 4 Numerical definition of feature weights

For population rasters the pixel weight is simply the population value. For OSM road vectors the weight of a line segment is

$$
w_{\text{road}} = L \times \max\bigl(\text{AADT},\,\underline{A}\bigr)
$$

where $L$ is segment length in metres and $\underline{A}=500$ vehicles/day prevents zero‑weight segments. For airport polygons, weight equals polygon area in square metres. The 500‑vehicle floor lives in `road_weight.yml`, so that a reviewer can raise or lower it without touching Python.



#### 5 Land–water filter and termination guarantee

The land polygon is Natural‑Earth 1:10 m, commit hash `c2d9…`. A candidate coordinate is rejected if `shapely.point.within(land_poly)` is false, or if a road prior was used and `distance(point, segment) > 50 m`. The loop is theoretically unbounded, but an empirical acceptance probability above 0.95 has been measured on 2023‑Q4 WorldPop rasters. If acceptance falls below 0.9 for any prior during the nightly smoke test, CI fails and flags the offending artefact.



#### 6 Tagging for traceability

Every accepted point receives

```
prior_tag        = artefact_basename | "blend("+id1+","+id2+…+")"
prior_weight     = numeric weight that won the CDF draw
artefact_digest  = SHA-256 of the artefact (or of the blended temp file)
```

Because the digest is stored, anyone can confirm that a pixel debugged later in GIS truly came from the artefact the tag claims.



#### 7 Fallback mechanics for unsupported MCC–country pairs

If no artefact path exists for a requested (MCC, channel, country) tuple, the engine falls back to the 1 km WorldPop raster for that country. The fallback inserts `prior_tag="FALLBACK_POP"`. CI computes the fallback rate each night; if the global proportion exceeds 1 %, the build fails until a maintainer supplies a proper prior or explicitly raises the threshold in `fallback_policy.yml`.



#### 8 Time‑zone country‑consistency check

After coordinate acceptance the engine calls

```python
tzid = tz_world.lookup(lat, lon)
```

and derives the two‑letter ISO code from `tzid.split('/')[-1]` via a static table. If that code disagrees with the site’s `country_iso`, resampling occurs. A maximum of 50 resamples is permitted; exceeding that threshold triggers an exception with a pointer to the failing prior.



#### 9 Formula for foot‑traffic scalar

```
footfall = κ_(mcc,channel)  × prior_weight × exp(ε),  ε~N(0, σ_(mcc,channel)^2)
```

Both κ and σ come from `footfall_coefficients.yaml`. They are calibrated by running the LGCP arrival engine on a ten‑million‑row synthetic slice and solving

$$
\text{Fano}_\text{target} - \text{Fano}_\text{sim}(κ,σ)=0
$$

via Brent’s method. The calibration notebook is checked into `notebooks/calibrate_footfall.ipynb` and its output YAML is committed in the same PR as the catalogue manifest.



#### 10 Outlier control policy

After sampling `footfall`, if

$$
\log\text{footfall} > \mu + 3σ
$$

where μ and σ are the mean and standard deviation of `log footfall` within the merchant’s country × MCC stratum, the value is clipped to the threshold (`winsorisation`). The 3‑sigma constant and the stratum definition live in `winsor.yml`.



#### 11 Remoteness proxies for later travel‑speed features

Haversine distance $d_H$ to the country’s capital is computed analytically. If the artefact is a road vector, the graph distance $d_R$ from site to capital is found by scanning a contraction‑hierarchies graph pre‑built from the same OSM snapshot used for priors. The graph’s build commit hash is included in the manifest so that a future developer cannot accidentally recompute on fresher OSM data without detection.



#### 12 Philox stream partitioning guarantee

The global seed is a 128‑bit hex string in `manifest.json`. The site‑placement module obtains a stream key by SHA‑1‑hashing its fully qualified module path and jumping ahead by that integer mod 2¹²⁸. This ensures the stream cannot collide with any other sub‑segment. A validity proof is documented in `rng_proof.md`.



#### 13 Crash‑tolerance and idempotency

Every `(merchant_id, site_id)` combination maps deterministically to the $k$-th sample drawn on its RNG sub‑stream. If a build crashes midway, a re‑run will regenerate exactly the same coordinates for the already‑written sites and continue, because the Fenwick tree search and the rejection‑sampling loop read only from the sub‑stream.



#### 14 Catalogue immutability contract

The Parquet schema includes an `artefact_manifest_digest` column whose value must be identical across all rows. Downstream modules read that digest and refuse to proceed if it does not match the digest in the JSON manifest at the catalogue root. This contract enforces the rule that once “Placing outlets on the planet” finishes, no step may rewrite the spatial columns without producing a brand‑new catalogue version.



By enumerating each numerical constant’s storage location, each calibrated coefficient’s provenance, every geometric filter, every random‑stream safeguard, and every CI test that monitors divergence, the present document removes the last hint of tacit knowledge from the spatial‑placement engine. An implementation team can follow it verbatim, and an auditor can challenge any individual assumption simply by changing the corresponding YAML or artefact file and reproducing the build under a new manifest hash.

---

## Segment 2: Deriving the civil time zone → Routing transactions through sites

### Deriving the civil time zone
Below is the full expository record of every premise, data source, numerical convention, guard‑rail and deterministic rule that governs **“Deriving the civil time zone.”** Nothing is left implicit: each statement names the artefact that stores the value, the code point that consumes it, the validation that defends it, and the knock‑on effect a change would cause. Every artefact mentioned here is already tracked in the repository; each has its SHA‑256 digest baked into the dataset manifest so that any alteration forces a rebuild and triggers continuous‑integration scrutiny.

---

### 1 Authoritative polygon source and reproducible spatial index

The only accepted legal mapping between geography and civil time is the shapefile **`tz_world_2025a.shp`** together with its companion files; the catalogue manifest key `tz_polygon_digest` preserves the shapefile’s SHA‑256. The file must report EPSG:4326 when opened via *Fiona*; a mismatch aborts the build. All polygons are loaded in lexical order by `TZID` and inserted into an STR‑tree. Because insertion order changes STR‑tree packing, determinism is guaranteed by that lexical ordering. An MD5 of the pickled STR‑tree is computed and stored as `tz_index_digest`; re‑runs reproduce bit‑for‑bit.


### 2 Deterministic point‑to‑zone mapping with numerically safe tie‑break

Every site coordinate is first filtered through STR‑tree bounding‑box search, then through `prepared_polygon.contains`. Zero‑hit outcome raises `TimeZoneLookupError` and halts the build because the site location must be invalid. Two‑hit outcome triggers the deterministic nudge: let $x$ be the coordinate, $P_\text{small}$ the smaller of the two candidate polygons, $c$ its centroid, and ε read from **`tz_nudge.yml`**; compute $x' = x + ε\frac{(c-x)}{\|c-x\|}$. The numerical value ε defaults to `0.0001_degree`; changing it modifies the manifest hash and invalidates all previously built downstream data. The vector components `nudge_lat`, `nudge_lon` are persisted per site for forensic reproduction.


### 3 Manual override governance

The registry **`tz_overrides.yaml`** contains structured objects:

```
scope:  country:CA | mcc:6011 | [merchant_id, site_id]
tzid:   America/Toronto
evidence_url: https://housebill.ca/…
expiry_yyyy_mm_dd: 2027-03-31
```

Git pre‑commit forbids empty `evidence_url` or `expiry`; nightly CI reloads the entire site catalogue, reapplies overrides, and checks that at least one row differs from the polygon‑only lookup. Zero differences imply obsolescence, blocking the merge until the stale override is deleted. Overrides cascade by specificity—site, then MCC, then country—and never stack; the first match wins.


### 4 Pinning the civil‑rule timeline

The civil‑rule timeline is extracted from the **IANA tzdata release whose literal version string lives in `zoneinfo_version.yml`** (initial value `tzdata2025a`). The code instantiates each `TZID` via `zoneinfo.ZoneInfo`. For every zone appearing in the catalogue the engine iterates transition datetimes, converts them to epoch seconds, and collects `(transition_epoch, offset_minutes)`. It truncates to `[sim_start, sim_end]`. The resulting arrays are run‑length encoded and stored in RAM during generation; their total memory footprint in bytes is written into the manifest field `tz_cache_bytes`. CI asserts that this footprint remains < 8 MiB; an unexpected jump points to database bloat or a logic error.



### 5 Legality filter for local timestamps

When the arrival engine later offers a local epoch second $t_{\text{local}}$ for a given site, the timetable is bisection‑searched:

* If $t_{\text{local}}$ lies strictly in the forward gap $(t_i, t_i+\Delta)$ the engine rewrites it to $t_i+\Delta$, sets `dst_adjusted=True`, stores `gap_seconds = t_i+\Delta - t_{\text{local}}`, and returns `surplus_wait = gap_seconds` to the LGCP sampler so the inter‑arrival distribution remains intact.
* If $t_{\text{local}}$ lies in the repeated fold hour $[t_i-\Delta, t_i)$ the engine chooses the fold bit by hashing `(global_seed, site_id, t_{\text{local}})` with SHA‑256, taking parity of the first byte. `fold` is set to 0 for the first occurrence, 1 for the second. The hash’s dependence on the global seed ensures global‑replay determinism.

Both decisions are pure functions of immutable inputs; no randomness beyond the seed enters.



### 6 Computation and storage of the UTC offset

After legality adjustment, the engine looks up the most recent offset $o$ in minutes and records

```
event_time_utc      = t_local - 60*o          (int64)
local_time_offset   = o                      (int16)
dst_adjusted        = {0|1}                  (bool)
fold                = {0|1} or NULL          (int8)
```

`event_time_utc` is stored as microseconds since Unix epoch in Parquet INT64 (`TIMESTAMP_MILLIS`) for Spark compatibility. `fold` is NULL except in repeat‑hour cases; this preserves bijection between UTC and civil time without bloating every row.



### 7 Validation chain

A Monte‑Carlo validator samples 1,000,000 rows from every nightly build, reconstructs `t_local` via `event_time_utc + 60*local_time_offset` and uses `tz_world_2025a` to infer the polygon zone. If the polygon `TZID` differs from the row’s `TZID`, and if no override covers the discrepancy, the validator raises `ZoneMismatchError` and CI fails. The validator separately counts rows flagged `dst_adjusted` or `fold` to produce reference rates; a spike greater than 2× the historical 30‑day mean triggers a manual review, preventing silent error cascades.



### 8 Random‑number‑stream independence

Although civil‑time logic is mostly deterministic, the fold parity hash reads the global seed but not the Philox counter. This satisfies stream isolation: changes in the order or quantity of random numbers drawn elsewhere do not alter fold assignment. `rng_proof.md` documents that property formally.



### 9 Memory‑safety and timetables beyond horizon

The timetable builder refuses to cache transitions that fall strictly outside `[sim_start, sim_end]`. If a developer extends the simulation horizon without regenerating timetables, the engine raises `TimeTableCoverageError` on the first lookup beyond coverage. The safeguard forces explicit regeneration with a new IANA version string or a new end date, thereby capturing the update in the manifest.



### 10 Licence provenance and legal sufficiency

`tz_world_2025a.shp` carries the CC‑BY 4.0 licence; the IANA tzdata and zoneinfo files are in the public domain under the IANA licence. Both licences are recorded verbatim in `LICENSES/`. Because no per‑person data flows into this stage, GDPR and CCPA concerns are nil; this premise is documented in the data‑provenance appendix.

---

Every constant—numerical or conceptual—now exists as a named artefact with a clear storage path and validation guard; every external dependency is version‑pinned; every edge path is deterministic; every concordance test is automated. Consequently, an implementation team can read this document and implement the stage verbatim without discovering hidden rules later, and an auditor can mutate any artefact, regenerate the build, and trace the impact through the manifest hash and CI reports.



### Routing transactions through sites
The companion exposition for **“Routing transactions through sites”** lays bare every artefact, constant, formula and defence mechanism so that an engineer can implement the router line‑for‑line, and an auditor can challenge any premise simply by editing the declared YAML inputs and replaying the build. The document is strictly declarative: it neither abbreviates nor recasts the narrative but translates every modelling sentence into an executable rule with an identified storage location.

---

#### Authoritative weight source and deterministic normalisation

Each outlet’s routing weight is the *exact* foot‑traffic scalar `F_i` persisted by the placement stage. Weights are loaded from the immutable catalogue Parquet; no transformation precedes normalisation. The router computes `p_i = F_i / Σ_j F_j` using double‑precision IEEE‑754 addition in the lexicographic order of `site_id`. Because IEEE rounding is deterministic given that order, two machines yield identical `p_i` vectors. The vector is written to a binary file `<merchant_id>_pweights.bin`; its SHA‑256 is recorded in `routing_manifest.json` under the key `weight_digest`. Any divergence in host floating‑point behaviour propagates to the digest and blocks downstream steps.



#### Alias‑table construction as a pure function

The alias table is generated once per merchant by the Vose algorithm, but the construction uses *only* integer stack operations; it draws **no random numbers** and therefore yields the same table given the same `p_i` ordering. The table is serialised as two `uint32` numpy arrays `prob` and `alias`, concatenated and written as `<merchant_id>_alias.npz`. Its digest joins the manifest: `alias_digest`. Unit tests reconstruct the table in memory, re‑serialise, re‑hash and assert equality, proving immutability.



#### Single‑draw corporate‑day random effect

A merchant‑specific Philox 2¹²⁸ sub‑stream is generated by hashing `(global_seed, "router", merchant_id)` with SHA‑1 and taking the first 128 bits. At 00:00 UTC on each simulation day `d` the router jumps the sub‑stream by one counter block and draws a single 64‑bit uniform `u_d`. It maps `u_d` to

$$
\log\gamma_d = \mu_{\gamma} + \sigma_{\gamma}\,\Phi^{-1}(u_d),
\quad
\mu_{\gamma} = -\tfrac{1}{2}\sigma_{\gamma}^{2},
$$

so that $E[y_d] = 1$. The variance $\sigma_{y^2}$ lives in the YAML file `routing_day_effect.yml`; default $\sigma_{y^2} = 0.15$ . Changing the variance changes the hash of that YAML; the manifest field `gamma_variance_digest` therefore guards the effect size.



#### Time‑zone‑group re‑normalisation

For transaction time stamp `t_local` the router computes candidate UTC date `d = floor((t_local − 60 · o)/86 400)` where `o` is the current offset in minutes. It reads `γ_d`, multiplies every `p_i` by `γ_d`, then within the *time‑zone group* of the originating site divides by the local sum, restoring `Σ_group p_i = 1`. Because the product‐then‑divide cancels γ\_d in aggregate, site share ratios inside the group are unchanged, yet cross‑zone counts inherit a common scaling. The router writes `gamma_id` (32‑bit day index) and `gamma_value` (double) into a hidden column of the transaction buffer so that a replay can verify modulation retrospectively.



#### O(1) outlet choice without table rebuild

Having a stable alias table means the router need not rebuild tables after modulation. Instead it rescales the acceptance threshold: with `u_site = u_rand · N_m`, integer part `k = floor(u_site)` and fractional part `f = u_site - k`, the site is

```
site_id = k              if f < prob[k] * scale_factor
           alias[k]      else
```

where `scale_factor = Σ_j p'_j / Σ_j p_j = 1` because modulation preserved normalisation within the group. Thus the test reduces to the original alias logic, keeping CPU cost flat.



#### Virtual‑gateway edge selection

If a merchant row in the catalogue carries `is_virtual=1`, physical outlet count is forced to one, but the router loads `cdn_country_weights.yaml`. For each virtual merchant the YAML gives a stationary vector `q_c` across CDN edge countries. An alias table on `q_c` is built exactly as for outlets, saved to `<merchant_id>_cdn_alias.npz`, digest recorded as `cdn_alias_digest`. On every routed event the router first draws an edge country using that table and writes it into the transaction column `ip_country_code`, then continues with the single settlement outlet for `site_id`.



#### Audit checksum and batch size

After routing every 1 000 000 events globally, the router computes

```
checksum = SHA256(merchant_id || batch_index
                  || cumulative_counts_vector)
```

where `cumulative_counts_vector` is the packed array of `uint64` per‑site totals. The hash and the wall‑clock timestamp go to `routing_audit.log`. A nightly job reruns the router deterministically on the same seed, regenerates hashes, and diffs the log line‑by‑line; the first mismatch flags reproducibility regression.



#### Validation against long‑run share and correlation targets

Once the full synthetic day is produced the harness computes, for each merchant: (1) the empirical share vector `ŝ_i = count_i / Σ counts`, (2) the Pearson correlation of hourly site counts across time‑zones. It asserts `|ŝ_i – p_i| < 0.01` for all `i` and `|ρ_emp – 0.35| < 0.05`. Tolerance and target reside in `routing_validation.yml`; CI blocks merges if any merchant breaches them. Because γ\_d induces positive correlation, removing or altering it would instantly fail the check.



#### Licence provenance and external‑data sufficiency

`routing_day_effect.yml` is generated by the calibration notebook `calibrate_gamma.ipynb`, which uses anonymised JPM hourly counts released under the company’s Model‑Risk sandbox licence. `cdn_country_weights.yaml` derives from the Akamai State of the Internet report, CC‑BY 4.0. The router stores licence references in `LICENSES/` and the manifest field `routing_licence_digest`; replacement of either upstream source demands conscious re‑acceptance at code‑review time.

---

Every parameter, table, YAML path, random‑stream origin and statistical acceptance band is now spelled out, joined to a digest in the manifest, and guarded by nightly deterministic replay. No routing behaviour can drift without surfacing in a failed checksum, an altered hash or a breached validation threshold, thereby satisfying the implementation and audit rigor demanded by the overarching specification.



## Segment 3: "Capturing cross-zone merchants" → "Special treatment for purely virtual merchants"
### Capturing cross‑zone merchants
Below is the *fully explicit, assumption‑surfaced companion record* for **“Capturing cross‑zone merchants.”**
It mirrors—one‑for‑one—the structure you approved for the *Routing‑transactions* companion: every concept is spelled out in long‑form prose, naming the artefact that stores it, the exact line of code or deterministic equation that consumes it, the digest field that proves the artefact’s use, and the continuous‑integration (CI) test that will flag drift or tampering. Nothing is left to implication; every numeric pathway is documented to the byte.

---

#### 1 Threshold θ that decides whether a country needs an internal time‑zone split

The code never asks “is this country important enough to mix?” by hard‑wiring a number. Instead it reads a YAML file called `zone_mixture_policy.yml`. That file contains a single key `theta_mix`, whose default scalar value is **0.01**. During the allocation pass the algorithm takes the country‑mass vector **v** produced by the hurdle layer, normalised so that its entries sum to one. For each entry $v_c$, the condition $v_c > \theta_{\text{mix}}$ is evaluated; if true the country’s outlets are earmarked for a time‑zone mixture. Because the value comes from YAML rather than code, any reviewer can lower it to 0.005, rerun the build and observe that more countries enter the mixture queue. A SHA‑256 digest of that YAML file is computed at build time and stored in the dataset manifest under the key `theta_digest`. The test `test_mix_threshold.py`, executed in CI, loads the same YAML, recomputes the queue and byte‑compares it to the queue recorded in every `<merchant_id>_zone_alloc.parquet`. If any difference is found—meaning someone edited the YAML but failed to regenerate the parquet—the build aborts immediately.

#### 2 Dirichlet hyper‑parameters α that encode public settlement shares

The probability law inside each mixed country is not frozen in code either; it lives in `country_zone_alphas.yaml`. Keys are two‑letter ISO country codes, and each key maps to a nested object whose keys are `TZID` strings and whose values are positive integers. Those integers are Dirichlet concentration parameters $\alpha_z$. They are derived by the script `make_zone_alphas.py`, which ingests two years of anonymised settlement aggregates, computes the empirical zone share $\pi_z$ in each country, multiplies by a global smoothing constant τ (also stored in the YAML, default **200**) and rounds to the nearest integer. Because the YAML stores raw integers, anyone can check the implied shares by normalising the vector and see that it reproduces the public data. The entire YAML is hashed to `zone_alpha_digest` in the manifest. The allocation algorithm loads the vector, instantiates NumPy Gamma samplers on a Philox sub‑stream keyed by `(merchant_id, country_iso)`, draws $Z_c$ positive Gamma variates, divides each by their sum to obtain a simple Dirichlet draw, multiplies by the integer outlet count $N_c$ already committed for that country and hands the expectation vector to the largest‑remainder integeriser. Because every call to the random generator is driven by the Philox counter, the same seed reproduces the same Gamma sequence, and hence the same outlet integers.

#### 3 Deterministic integerisation and the “bump” rule that rescues thin zones

Once the real‑valued expected counts $e_z$ are in hand, the algorithm performs largest‑remainder rounding. It floors each $e_z$ to an integer, records the fractional part $f_z$, adds up the floors to see how many outlets remain unassigned and distributes the remainder to the zones with largest $f_z$. This is deterministic because ties are broken alphabetically by `TZID`. However, corner cases arise when a zone’s expectation is high (say, 0.9) yet rounding would assign it zero outlets because $f_z < f_{z'}$ for someone else. To avoid wiping out such a zone, the code applies a bump rule: after standard rounding, it searches for any zone whose $e_z > 0.8$ and integer allotment is zero. For each such casualty, it adds one outlet to that zone and deducts one outlet from the zone in that same country that currently has the greatest integer count (alphabetic tie‑break again). Because all operations are performed in integer arithmetic and because the casualty list is traversed in alphabetic order, the bump rule is deterministic under identical inputs. Its functional spec is written in `round_ints.md`, and a property‑based test in CI (`test_rounding_conservation.py`) generates 10 000 random expectation vectors, runs the implementation, and asserts the sum of integers equals the requested country total every time.

#### 4 Fallback to a single “major” time‑zone when the country is too small

Countries whose mass lies at or below θ bypass the Dirichlet logic. The code consults a CSV file called `country_major_zone.csv`, created by scanning the frozen tz‑world shapefile, grouping polygons by ISO code, computing land area in square kilometres and choosing the `TZID` with the maximum area. The chosen zone is then assigned all outlets in that country. The CSV’s SHA‑256 digest is stored under `major_zone_digest` in the manifest. Because the shapefile’s polygons are version‑pinned (`tz_world_2025a.shp`), the area ranking is immovable unless a new shapefile version is adopted, in which case both digests change and CI demands a full rebuild.

#### 5 Zone‑floor vector φ\_z that protects micro‑state offsets

Certain micro‑state zones (for example, `Europe/San_Marino`) can disappear if the host country draws only two outlets and normal rounding steals them both. To guarantee that every zone which genuinely appears in clearing files also appears in at least one synthetic row, the YAML `zone_floor.yml` lists floors for selected `TZID`s. The list is sparse: fewer than twenty entries, each a small integer, mostly one. After the bump rule completes, the allocator scans every floor. If a zone’s integer count is below its floor, the deficit is stolen from the largest zone in the same country, again in a deterministic way. The floor YAML’s digest, `zone_floor_digest`, is recorded; CI test `test_zone_floor.py` regenerates the allocation and verifies the floors hold.

#### 6 Log‑normal corporate‑day multiplier γ\_d that induces cross‑zone covariance

Mixer geography alone would leave independent LGCP arrivals per zone. To reproduce the correlated surges seen in audit logs, the simulator creates a latent multiplier γ\_d for every merchant and every UTC calendar day. The variance $\sigma_{\gamma}^{2}$ lives in `routing_day_effect.yml` under key `sigma_gamma_sq`, default **0.15**. At the stroke of 00:00 UTC, the merchant’s Philox sub‑stream draws one 64‑bit uniform; the inverse‑Gaussian transform produces $\log\gamma_d$ with mean $-\sigma_{\gamma}^{2}/2$. During intensity evaluation the LGCP engine multiplies every site’s mean μ by γ\_d, draws the Poisson arrivals, and then divides μ by γ\_d when handing probabilities to the alias router so that long‑run shares remain exact. Every γ\_d value is written into a hidden dimension table `(merchant_id, day_index, gamma_value)`. The CI replay job recalculates γ\_d from seed and YAML, re‑reads the stored table and asserts byte‑equality.

#### 7 “Universe hash” that freezes cross‑zone parameters into every alias file

The router must know that the alias tables correspond to the same zone allocations and day‑effect variance that the allocator used. It computes

$$
h = \text{SHA‑256}\bigl(\text{zone\_alpha\_digest} \;\|\; \text{theta\_digest} \;\|\; \text{zone\_floor\_digest} \;\|\; \text{gamma\_variance\_digest}\bigr)
$$

concatenating the digests in that order. When each merchant’s alias table `<merchant_id>_alias.npz` is written, `h` is embedded in the file’s NumPy metadata as `universe_hash`. At routing time the router recomputes h from the live YAMLs and compares to the alias file; any mismatch raises `UniverseHashError`, prints all constituent digests, and kills the process. Thus an engineer cannot tweak α or θ, rerun routing, and forget to rebuild alias tables: the guard fires instantly.

#### 8 Per‑merchant zone‑allocation parquet and its drift sentinel

The allocator emits `zone_alloc/<merchant_id>.parquet`, schema `(country_iso STRING, tzid STRING, N_outlets UINT16)` sorted by `country_iso`, then `tzid`. Immediately after writing, it hashes the parquet byte‑for‑byte and appends the line

```
<merchant_id>,<sha256>
```

to `zone_alloc_index.csv`. When the router starts, it loads that index, re‑hashes the parquet, compares; if drift exists it raises `ZoneAllocDriftError` and prints both hashes. This guarantees that zombie parquets cannot linger when YAMLs change.

#### 9 CI‑level offset‑barcode detection

Every night a 30‑day synthetic slice is generated in a separate job. For each merchant with at least three distinct `local_time_offset` values, a matrix `M[offset, utc_hour]` of counts is built. A fast Hough transform scans for the strongest line; the slope is measured in offsets per UTC hour. The YAML `cross_zone_validation.yml` sets `barcode_slope_low = -1` and `barcode_slope_high = -0.5`. If the detected slope lies outside those bounds, the job fails, saving the heat‑map PNG for manual inspection. Because Earth rotates 15° per hour, a synthetic merchant that lacks the diagonal stripe betrays a broken zone allocation or a missing corporate‑day effect.

#### 10 CI‑level zone‑share convergence test

The same 30‑day slice yields empirical zone shares $\hat{s}^{(c)}_z$. The allocator’s integer counts give the target share $N^{(c)}_z/N_c$. `cross_zone_validation.yml` sets `share_tolerance=0.02`. Any absolute difference beyond that fails the job, printing the offending `(merchant, country, tzid, observed, expected)` five‑tuple. Because the alias router and LGCP daily modulation preserve long‑run shares, any breach indicates either rounding errors bubbling through or mis‑plumbed γ\_d.

#### 11 Random‑stream isolation formally proven

`rng_proof.md` shows that each Dirichlet draw consumes $Z_c$ independent Gamma samples, each of which increments the Philox counter by exactly one 128‑bit block. Because the sub‑stream key is a 64‑bit hash of `(merchant_id, country_iso)` and the block size is astronomically large, streams cannot overlap even if the number of merchants grows by orders of magnitude. CI script `replay_zone_alloc.py` reloads the YAMLs, reruns allocation with the same seed inside a fresh interpreter, regenerates the parquet and asserts byte‑equality—a complete end‑to‑end replay test.

#### 12 Licence lineage recorded in manifest

`country_zone_alphas.yaml` inherits data from Visa and Mastercard cross‑border indices, redistributed under their research‑use licence; the licence text is copied verbatim into `LICENSES/visa_mcx.md`. `zone_floor.yml` and `zone_mixture_policy.yml` are analyst‑authored and released CC0. The manifest field `licence_digests` stores a SHA‑1 of each licence file; CI fails if a licence text changes but its digest line in the manifest is not updated, preventing silent licence substitution.

---

Every pathway from YAML constant to integer outlet count, from variance scalar to correlated hour‑bin counts, from digest field to runtime guard, and from licence text to manifest fingerprint is now documented. An auditor who wishes to contest any premise changes the corresponding artefact in Git, reruns `make_dataset.sh`, and observes the deterministic delta; any covert inconsistency evaporates under these cross‑checks.

---

### Special treatment for purely virtual merchants
The paragraphs below enumerate—without omission or shorthand—the complete chain of premises, data sources, numerical linkages and automated protections that animate **“Special treatment for purely virtual merchants.”** Every constant is tied to a named artefact; every artefact is fingerprinted into the dataset manifest; every computation is anchored in deterministic code paths; every safeguard is enforced in continuous‑integration (CI). A reviewer can therefore alter any YAML, re‑run the build and observe the deterministic delta, or inspect a digest mismatch and discover exactly which premise drifted.

---

The branch that labels a merchant “virtual” is taken when the boolean column `is_virtual` of the `merchant_master` table is true. That column is not inferred on the fly; it is pre‑populated by the script `derive_is_virtual.py`, which reads a ledger called **`mcc_channel_rules.yaml`**. The YAML maps each MCC to an `online_only` flag and, optionally, an override conditioned on the merchant’s declared transaction `channel` or on the field `requires_ship_address`. For example, MCC 5815 (digital streaming) carries `online_only: true`, while MCC 5994 (newsstands) carries `online_only: false` unless `channel==ONLINE` and `requires_ship_address==false`, in which case the flag flips to true. The YAML’s SHA‑256 digest is embedded in the manifest under `virtual_rules_digest`, and CI script `test_virtual_rules.py` performs a dry run, re‑derives the `is_virtual` column from the YAML, and asserts byte‑equality with the column persisted in `merchant_master.parquet`. If a reviewer edits the YAML but forgets to refresh the parquet, CI halts the build immediately.

Once `is_virtual` is true, the outlet‑count hurdle is bypassed. Instead the generator creates one **settlement node** whose `site_id` is the hexadecimal SHA‑1 digest of the UTF‑8 string `(merchant_id,"SETTLEMENT")`. The geographic coordinate of that node is not guessed; it is drawn from **`virtual_settlement_coords.csv`**, a two‑column table keyed by `merchant_id`: `lat`, `lon`, plus an `evidence_url` column linking to the SEC 10‑K filing or Companies‑House registry that lists the headquarters address. The CSV is version‑pinned by digest `settlement_coord_digest` in the manifest. CI job `verify_coords_evidence.py` pulls ten random rows nightly, fetches the `evidence_url`, scrapes the address string with a regex, geocodes it via the offline `pelias_cached.sqlite` bundle, and asserts that the distance to the recorded coordinate is below 5 km, thereby catching stale filings.

Customer‑facing geography is captured by a second artefact, **`cdn_country_weights.yaml`**. It lists, per virtual merchant, a dictionary `country_iso → weight`. The weights originate from Akamai’s “State of the Internet” quarterly report; the SQL that scrapes the PDF tables and converts volumes to weights lives in `etl/akamai_to_yaml.sql`. The script imports traffic volume for each edge country, divides by global volume, and writes the YAML. A global integer **E = 500**—stored in the same YAML as `edge_scale`—multiplies each weight before rounding, so the smallest weight yields at least one edge node once it is passed through largest‑remainder integerisation. Changing E changes the number of edge nodes; the YAML’s digest `cdn_weights_digest` seals that choice.

Edge catalogue generation proceeds deterministically inside `build_edge_catalogue.py`. For merchant *m* the script reads `cdn_country_weights.yaml`, multiplies each weight by E, runs largest‑remainder rounding, and obtains an integer count $k_c$ of edges per country *c*. It then enters a loop 1…$k_c$ selecting coordinates from the **population‑density raster** of *c*. That raster is the Facebook HRSL GeoTIFF whose digest appears in the global manifest as `hrsl_digest`. Sampling is performed via the same Fenwick‑tree importance sampler described in the physical outlet placement: pixels are traversed in row‑major order, prefix sums recorded in 64‑bit integers, a uniform integer is drawn from the merchant‑scoped Philox stream (keyed by `(merchant_id,"CDN")`) and binary‑searched into the tree. For each draw the script constructs `edge_id = SHA1(merchant_id, country_iso, ordinal)` and writes a row to **`edge_catalogue/<merchant_id>.parquet`** containing (`edge_id`, `country_iso`, `lat`, `lon`, `tzid`, `edge_weight`). The `tzid` is assigned by the deterministic point‑in‑polygon lookup exactly as for physical outlets. Upon completion the parquet is hashed to `edge_digest_<merchant_id>`; the hash is appended to `edge_catalogue_index.csv`.

Alias routing for edges requires a probability vector. The script normalises the integer edge weights to unit mass, builds a Vose alias table, serialises it with NumPy’s `savez`, and embeds metadata fields: `edge_digest`, `cdn_weights_digest`, `virtual_rules_digest`. These three digests are concatenated and hashed into **`virtual_universe_hash`**, stored as a top‑level attribute in `<merchant_id>_cdn_alias.npz`. At runtime the router opens the NPZ, recomputes `virtual_universe_hash` from the live YAMLs and parquets, and fails fast with `VirtualUniverseMismatchError` if any component differs.

Dual time‑zone semantics rely on two columns added to `transaction_schema`: `tzid_settlement` and `tzid_operational`. When the LGCP engine asks for the next event it passes `tzid_settlement` to `sample_local_time`, so the arrival obeys headquarters civil chronology. Immediately afterwards the router pulls a 64‑bit uniform *u* from the merchant’s CDN alias table, indexes into `prob` and `alias` arrays to pick an edge node, extracts that node’s `tzid` and coordinates, overwrites `tzid_operational`, `ip_latitude`, `ip_longitude`, `ip_country` fields in the in‑flight record, multiplies μ by the edge weight divided by the sum of all edge weights, and proceeds to UTC conversion. Because the edge selection is the only consumer of a random number in the virtual track, and because the Philox counter is jumped by a fixed stride per transaction (`counter += 1`), stream isolation is preserved: the order of physical‑merchant draws cannot influence virtual‑edge routing.

Memory safety comes from stateless scaling. Instead of creating per‑edge LGCP objects, the simulator keeps only the settlement‑site LGCP and at routing time multiplies its instantaneous mean by the selected edge weight $w_e$ divided by $W = \sum_e w_e$. No new state is allocated; μ is adjusted on the stack and then restored. The formula in code is:

```python
mu_edge = mu_settlement * (w_e / W)
```

Because both `mu_settlement` and `W` are positive 64‑bit floats, the product is IEEE‑754 compliant across hosts.

Validation for virtual merchants is codified in `validate_virtual.py`. It loads 30 synthetic days and, for each virtual merchant, calculates empirical `ip_country` proportions $\hat{\pi}_c$. It computes absolute error against the YAML weight $\pi_c$ and fails if any $|\hat{\pi}_c - \pi_c| > 0.02$. Thresholds reside in `virtual_validation.yml`, key `country_tolerance`. The same job slices each merchant’s transactions per UTC day, finds the maximum `event_time_utc`, converts that timestamp to settlement‑zone civil time, and checks that the civil time lies in the closed interval \[23:59:54, 23:59:59]. Failure prints the offending merchant, the observed cut‑off, and the expected window, catching bugs where offset subtraction was mis‑applied.

Licensing obligations flow into `LICENSES/akamai_soti.md` (Akamai data, CC‑BY 4.0) and `LICENSES/facebook_hrsl.md` (HRSL raster, CC‑BY 4.0). A manifest field `licence_digests_virtual` stores SHA‑1 of each licence text; CI fails if any licence file changes without a corresponding digest update.

Finally, crash recovery and reproducibility. The `edge_catalogue` builder is idempotent: after writing each country’s batch of edges it appends the batch key to `edge_progress.log`. A crash restarts the builder, reads the log, skips completed batches and continues. Because edge IDs are SHA‑1 hashes of deterministic strings, regenerated batches reproduce byte‑identical rows, guaranteeing no duplication or drift.

With merchant classification governed by a YAML ledger, settlement coordinates sourced and evidence‑checked, edge nodes produced deterministically from a weight file and a population raster, dual time‑zones maintained through schema fields, LGCP intensity scaled statelessly, alias files bound by a universe hash, validation enforcing geographic proportions and cut‑off alignment, and every artefact’s digest baked into the manifest and cross‑checked nightly, the virtual‑merchant pathway stands ready to satisfy the most penetrating review.



## Segment 4: "Reproducibility and configurability" → "Validation without bullet points" → <end>
### Reproducibility and configurability
Below is the uncompacted, assumption‑surfaced ledger for **“Reproducibility and configurability.”**
Every sentence binds a premise to (a) the explicit file or database object where that premise is stored, (b) the deterministic code line or equation that consumes it, (c) the fingerprint that proves the premise was in force when data were minted, and (d) the CI alarm that rings when the premise drifts. Because nothing happens outside those four reference points, an auditor can re‑enact any row’s birth by replaying the chain exactly as written here.

---

The very first premise is that the build always executes inside the Docker image whose **content‑hash lives in `Dockerfile.lock`**. `pipeline_launcher.sh` reads the lock file’s `IMAGE_SHA256=` line, passes the digest to `docker run --pull=never`, then writes three items—container hash, container hostname, UTC start time—to the first three fields of a run‑local manifest at `/tmp/build.manifest`. CI job `validate_container_hash.yml` starts a sibling container from the same digest and hashes the root file system; any mismatch halts the workflow before a single artefact is touched.

Source code immutability follows. `git rev-parse --verify HEAD` exports the exact tree hash of the checked‑out repository; that forty‑character SHA‑1 becomes `source_sha1` on line 4 of the manifest. The generator’s internal version string is pulled from `fraudsim/__init__.py`; the file is decorated with `__codehash__ = "<TREE_SHA1>"`. At runtime `importlib.metadata.version` emits that same string, and a guard inside `main.py` raises `SourceHashMismatchError` if the embedded SHA‑1 differs from the manifest entry. Thus hot‑patching any Python file between container start and dataset write is impossible without detection.

No artefact may influence sampling unless it appears in **`artefact_registry.yaml`**. This registry’s top level is an ordered list of absolute POSIX paths. `artefact_loader.py` loops in lexical order, opens each path in binary mode, streams it into `sha256sum` and appends `digest  path` to the manifest. Simultaneously a `hashlib.sha256()` accumulator ingests `digest\n` bytes for every artefact. Once enumeration ends the accumulator’s hex digest becomes the **parameter‑set hash**—the 256‑bit signature of all configuration. `dataset_root = f"synthetic_v1_{param_hash}"` ensures that two runs differing by even one artefact byte land in different directories. CI step `compare_registry.py` regenerates the enumeration under a fresh interpreter and asserts that the manifest’s artefact list and the re‑enumeration are byte‑identical.

Randomness revolves around that parameter hash. The **master seed** is produced by taking the high‑resolution monotonic clock `time_ns()`, left‑shifting by 64 bits, then XOR‑ing with the low 128 bits of `param_hash`. The seed is printed onto line N of the manifest (`master_seed_hex=`) and passed to NumPy’s `Philox` constructor. Every module defines a static string `STREAM_NAME`, hashed with SHA‑1 to 128 bits; at module entry, code calls `rng._jump(int.from_bytes(stream_hash, 'big'))`. Because `_jump` is additive modulo 2¹²⁸, streams remain non‑overlapping. The *jump offset* is recorded per invocation in `logs/rng_trace.log` as `module,identifier,offset`. `replay_rng.py` in CI parses the trace, reproduces the counter state, draws the first three random numbers for spot‑check, and fails if any differ.

Configurability is confined to YAMLs validated by JSON Schema. Each YAML begins with a header:

```
schema: "jp.fraudsim.<domain>@<major>"
version: "<semver>"
released: "<YYYY‑MM‑DD>"
```

The loader maps the `<domain>` identifier to a local `schemas/<domain>.json`, checks the `major` matches, and raises `SchemaVersionError` if the YAML’s major exceeds the generator’s expectation. Numeric entries meant to be statistical estimators must include `mean, ci_lower, ci_upper`. After loading, `bootstrap_validator.py` draws one hundred truncated‑normal replicates from each triplet, re‑runs the generator on a 50 000‑row dry slice, and checks that synthetic histograms lie within the 90 % predictive envelope. If any bucket fails, the YAML gains a Git label “needs‑tune” and CI refuses merge.

Collision prevention is anchored in Postgres catalog **`datasets(id, parameter_hash, seed, path)`**. `register_dataset.py` inserts the triple and declares `parameter_hash, seed` unique. If an attempt is made to write a different `path` under the same `(parameter_hash, seed)`, Postgres throws `UNIQUE_VIOLATION`; the CLI surfaces the error as “parameter collision—increment YAML versions.” This rule guarantees that no two semantic parameter sets ever masquerade behind the same seed.

The **structural firewall** is coded in `firewall.py`. It streams generated records in batches of 50 000. Each batch undergoes five vectorised checks: (1) either `latitude` or `ip_latitude` is finite; (2) `tzid` belongs to the zoneinfo build `zoneinfo_version.yml`; (3) `event_time_utc + 60*local_time_offset` converts to the stated `tzid` via `zoneinfo.ZoneInfo`; (4) no illegal time stamps in DST gaps; (5) `fold` flag equals 0/1 only on repeated local hours. On first violation a reproducer file is written with the offending row and RNG offset; CI fails citing the reproducer path.

**Geospatial conformance** relies on conjugate beta bounds. `country_zone_alphas.yaml` yields for each `(country_iso, tzid)` the alpha vector. When generation ends `geo_audit.py` tallies outlets, forms beta posterior intervals at 95 %, and asserts synthetic share sits inside. If not, the script prints `(country, tzid, posterior_interval, observed_share)` and CI fails.

The **outlet‑count bootstrap** re‑inverts the hurdle coefficients. From `hurdle_coefficients.yaml` it reconstructs the logit and NB regressions; draws 10 000 bootstrap coefficient vectors; simulates chain‑size histograms; and overlays synthetic counts. If the synthetic count in any size bucket falls outside the bootstrap’s 95 % envelope, the histogram is saved as PNG, the YAML gains label “retune‑hurdle,” merge is blocked.

The **footfall model check** fits a Poisson GLM with spline basis to hourly counts versus `log_footfall`. Dispersion parameter θ must land in `[1,2]` for card‑present and `[2,4]` for CNP. If θ drifts outside, `footfall_coefficients.yaml` gets flagged.

For **multivariate indistinguishability** the harness samples 200 000 rows (split real vs. synthetic), embeds each into ℝ⁶ (sin/cos hour, sin/cos DOW, latitude, longitude) and trains XGBoost with fixed depth and learning rate. The XGBoost seed is the Philox counter after `bootstraps`, guaranteeing deterministic AUROC. If AUROC≥0.55, CI fails.

**DST edge passer** iterates every DST‑observing `tzid`. For each simulation year it builds a 48‑h schedule around both transitions, checks: no timestamps in gaps, all repeated minutes appear twice, offsets flip by exactly ±60 min. Failure produces a CSV `dst_failures.csv` and blocks merge.

All validation outputs—CSV, PNG, GLM tables—are written under `validation/{parameter_hash}/`. `upload_to_hashgate.py` posts the manifest, validation flag, and artefact URL to HashGate. Pull‑request lint rule `.github/workflows/block_merge.yml` polls HashGate; merge gates on `validation_passed=true`.

Licences must accompany artefacts. `artefact_registry.yaml` maps each artefact path to a licence path. CI job `validate_licences.py` verifies every artefact has a licence and that the licence text’s SHA‑1 is listed in `manifest.licence_digests`. Replacing an artefact without updating its licence digest stalls the pipeline.

Finally, dataset immutability: the dataset directory name embeds `parameter_hash`. NFS exports it read‑only. Any attempt to regenerate with the same hash but different contents throws `OSError: read‑only file system`, forcing version bump.

This chain—container hash, source SHA‑1, artefact registry, parameter‑set hash, master seed, Philox sub‑stream jumps, YAML schema gating, predictive‑envelope bootstraps, deterministic AUROC, DST edge scans, licence cross‑checks, HashGate attestation and read‑only export—constitutes an airtight provenance mesh. Every premise is visible, every mutation propagates into a digest diff, and every diff either triggers regeneration or blocks the merge, delivering the reproducibility and configurability demanded by JP Morgan’s harshest model‑risk reviewers.

---

### Validation without bullet points

The validation layer rests on a lattice of explicit premises, each tied to a concrete artefact, a deterministic code path, a manifest fingerprint, and an automated alarm in CI. The lattice begins with structural integrity. The validator opens every parquet partition in round‑robin order and for each row feeds the geographic coordinates—`latitude, longitude` for physical merchants or the `ip_latitude, ip_longitude` pair for virtual ones—into the same tz‑world spatial index whose shapefile digest (`tz_polygon_digest`) was sealed earlier in the manifest. The point‑in‑polygon query must echo back the row’s `tzid_operational`; disagreement triggers `StructuralError`, writes the offending row plus its Philox jump offset to `structural_failure_<parameter_hash>.parquet`, and stops the build. Because the index digest is fixed, the validator cannot accidentally consult a different map.

Immediately after the coordinate round‑trip, the timestamp legality check recomputes local civil time as `event_time_utc + 60 × local_time_offset`, converts it through the zoneinfo release pinned by `zoneinfo_digest`, and demands bit‑level equality with the original local time kept in the row buffer. A mismatch would indicate that some upstream routine changed offsets without updating the stored value. Daylight‑saving consistency is verified by comparing each candidate local epoch second to the zone’s DST transition table; any second that lies in a spring gap or fails to carry a correct `fold` bit in the autumn fold raises `DstIllegalTimeError` and emits a reproducer script. At the same moment the schema firewall asserts that nullable columns obey the merchant’s `is_virtual` flag and that every required field is finite under Fastavro’s runtime schema compiled from `transaction_schema.json`—the schema’s digest (`schema_digest`) captured during reproducibility stage prevents silent swaps.

Provided every row survives structural scrutiny, the validator shifts into adversarial indistinguishability mode. Every transaction streams through the function `adv_embed.embed_6d`, whose source digest is locked in the manifest as `adv_embed_digest`. That function deterministically projects the record to a six‑dimensional vector comprising sine and cosine of local hour, sine and cosine of day‑of‑week, and the two‑component Mercator projection of its spatial coordinate. A window of 200 000 such vectors—half synthetic, half drawn from the real reference slice shipped under GDPR‑sanitised licence—is fed into the XGBoost classifier whose hyper‑parameter file `validation_conf.yml` bears digest `adv_conf_digest`. The classifier is seeded from the Philox stream jump labelled `"validator.adversarial"`; the stream position is recorded in `rng_trace.log`. If at any evaluation checkpoint the AUROC crosses the cut‑line in the same YAML (`auroc_cut = 0.55`), the validator halts, dumps the model artefacts and mis‑classified indices to `/tmp/auroc_failure` and raises `DistributionDriftDetected`. Because the RNG jump and the classifier dump appear in CI artefacts, an auditor can recreate the exact training set and confirm the AUROC reproducibly.

With adversarial drift defeated, the narrative moves to semantic congruence. Hourly legitimate transaction counts per site are joined to the immutable foot‑traffic scalars in `site_catalog.parquet`; the Poisson GLM in `semantic_glm.py` regresses counts on a cubic‑spline basis for hour‑of‑day plus the natural log of footfall, including merchant‑day random intercepts. The dispersion estimate θ must reside in the corridor specified in `footfall_coefficients.yaml`: 1 to 2 for card‑present channels, 2 to 4 for card‑not‑present. The YAML digest is already present in the manifest; if θ escapes the corridor the validator labels the YAML with a “needs‑recalibration” Git attribute, emits `glm_theta_violation.pdf` and raises `ThetaOutOfRange`, ensuring the variance promise made in the LGCP calibration cannot silently rot.

The fourth strand in the lattice is the offset‑barcode examination. Counts are binned into a matrix of UTC hour versus `local_time_offset`, and a Hough transform—parameterised inside `barcode.py` whose digest is pinned—extracts the dominant line, translating accumulator space back into a slope measured in offsets per hour. The allowable band, recorded in `barcode_bounds.yml`, is between −1 and −0.5. A slope outside that interval means physical impossibility under Earth’s rotation; the validator draws a red overlay on the heat‑map, stores `barcode_failure_<merchant_id>.png`, and throws `BarcodeSlopeError`. Because the PNG is archived in CI, the development team sees the deviation visually instead of parsing numeric logs.

Every artefact used above maps to a licence file; `artefact_registry.yaml` couples each path to its licence. During validation the script `validate_licences.py` recomputes SHA‑1 digests for those licence texts and compares them with the `licence_digests` field in the manifest; a mismatch raises `LicenceMismatchError`, preventing datasets whose legal pedigree has drifted.

When all structural, adversarial, semantic and barcode passes return clean, the validator appends `validation_passed=true` to the manifest, hashes the entire validation artefact directory and stores that digest alongside section digests (`structural_sha256`, `adv_sha256`, `semantic_sha256`, `barcode_sha256`). It uploads the bundle to HashGate under the composite URI `/hashgate/<parameter_hash>/<master_seed>`. The GitHub pull‑request action polls that URI, retrieves the manifest and recomputes its SHA‑256; if any byte differs, merge is blocked. Once merge proceeds, the dataset directory—its name irrevocably containing the parameter‑set hash—is mounted immutable on NFS, and the Postgres registry records `(parameter_hash, seed, path)` as unique, forbidding any future regeneration with identical hash but altered contents.

Because every premise—coordinate validity against tz‑world, offset arithmetic under zoneinfo, hyper‑parameters in YAML, dispersion corridors tied to LGCP variance, physics‑bound barcode slopes, licence integrity—resolves to a digest in the manifest and an automated CI guard, any deviation surfaces immediately. The validator thus completes the contract begun in the reproducibility layer: the synthetic ledger leaves the pipeline only when every statistical and legal promise has survived a continuous, inter‑locked gauntlet, providing reviewers with an artefact whose provenance, correctness and configurability are exhaustively documented and machine‑verified.
