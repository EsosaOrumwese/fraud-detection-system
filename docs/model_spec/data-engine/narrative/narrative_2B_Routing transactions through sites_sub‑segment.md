Once the catalogue has given every merchant a concrete constellation of sites, each with a latitude, longitude, time‑zone and foot‑traffic scalar, the simulation must decide—millions of times per synthetic day—**which single outlet actually receives a candidate transaction**. That decision is orchestrated in the sub‑segment called *“Routing transactions through sites,”* and its ambition is to be indistinguishable from the logic that lives inside a real acquirer’s authorisation switch. The core requirement is to translate an abstract arrival event, generated upstream by the Log‑Gaussian‑Cox process in “local civil time,” into an `(event_time_utc, site_id)` pair whose spatial choice respects the long‑run market share implied by foot‑traffic weights, the cross‑zone synchrony of corporate promotions, and the brutally unforgiving reproducibility contract that governs the entire pipeline.

The catalogue Parquet file is located at `artefacts/catalogue/site_catalogue.parquet` and is declared as a governed artefact in `routing_manifest.json` under `site_catalogue_digest` (semver, sha256\_digest), ensuring that the exact input used for weight loading is verifiable;

The routing engine’s first responsibility is to **freeze an immutable probability law** that maps every merchant’s outlet list to a set of normalised weights. Let the merchant have sites indexed by `i = 1 … N_m`. Each site carries a positive foot‑traffic scalar `F_i` inherited verbatim from the placement stage. The engine computes the raw share

$$
w_i = F_i \quad\text{for all } i,
$$

then normalises to obtain

$$
p_i = \frac{w_i}{\sum_{j=1}^{N_m} w_j}.
$$

These weights are written to disk once as a two‑column table `(site_id, p_i)` sorted lexicographically by `site_id`; this strict ordering, together with the fact that the sums of IEEE‑754 doubles are rounded identically on any IEEE‑compliant CPU, means that two developers running the build on different machines will obtain byte‑identical `p_i`. The vector is written little‑endian as a headerless `float64` array in `<merchant_id>_pweights.bin`, with its SHA‑256 recorded as `weight_digest` in `routing_manifest.json`;

Because naïve multinomial sampling in O(N) time would choke on global merchants that own thousands of outlets, the pipeline constructs **an alias table** per merchant. The deterministic alias construction proceeds by streaming through the `p_i` vector, pushing indices into “small” or “large” stacks according to whether `p_i < 1/N_m`, and then popping one from each until both are empty, filling the `prob` and `alias` arrays. The `.npz` file `<merchant_id>_alias.npz` is uncompressed, saved via NumPy 1.23 with named arrays `prob` and `alias`, and its digest is recorded as `alias_digest`;

Long‑run shares, however, are not enough; real data reveal a subtle **cross‑zone co‑movement** when a corporate promotion begins at 00:00 local time. To reproduce that, the routing engine introduces a **latent “corporate‑day” random effect** γ\_d drawn once per merchant per UTC day `d` via

$$
\log\gamma_d \sim \mathcal{N}\!\bigl(-\tfrac{1}{2}\sigma_{\gamma}^2,\;\sigma_{\gamma}^2\bigr),  
$$

with `σ_γ²` governed by `config/routing/routing_day_effect.yml` (`sigma_squared`, semver, `gamma_variance_digest`) and defaulting to 0.15.  Seed derivation uses Python 3.10’s `hashlib.sha1()` on `(global_seed, "router", merchant_id)` in `router/seed.py`, governed by `rng_policy.yml` (`rng_policy_digest`). After the day‑effect draw at counter 0, each subsequent 64‑bit uniform `u` comes from counter 1, 2, … of the Philox sub‑stream as implemented in `router/prng.py`;

When the arrival engine proposes a local timestamp `t_local`, the router computes the candidate UTC date `d`, multiplies each `p_i` by γ\_d in float64 arithmetic (`router/modulation.py`), and re‑normalises within the originating site’s time‑zone group so that ⸨Σ\_group p\_i⸩ = 1. Here, the “time‑zone group” is defined as the subset of outlets whose IANA time‑zone identifier (`tzid`) matches that of the originating site; the re‑normalisation divides each scaled `p_i` by the sum of scaled `p_j` over that same subset, ensuring intra‑zone probabilities sum to one. This preserves the alias table, requiring only a scaled threshold in the O(1) alias lookup:

```
k = floor(u * N_m)
site_id = k if u < prob[k] * scale_factor else alias[k]
```

with `scale_factor = 1`;

Certain merchants flagged `is_virtual=1` receive a shadow list of edge‑node countries drawn from `config/routing/cdn_country_weights.yaml` (`semver`, `sha256_digest`, `q_c`), using the same alias‑table logic to select `ip_country`;

After each outlet selection, the router returns `(site_id, tzid)` to the temporal engine, which converts `t_local` to UTC, handles gap/fold logic, and writes the transaction record unchanged.

Finally, once per million routed events, the engine computes

```
checksum = SHA256(merchant_id || batch_index || cumulative_counts_vector)
```

and appends it with an ISO 8601 timestamp to `logs/routing/routing_audit.log`. Rotation (daily) and 90‑day retention are governed by `config/routing/logging.yml` (`audit_log_config_digest`), and a nightly integration test reruns the router to verify matching checksums;

By anchoring each step to a manifest‑tracked artefact, precise binary format, governed RNG policy, and algebraic invariants—backed by daily audit and strict CI gates—the *“Routing transactions through sites”* sub‑segment delivers outlet‑level realism, computational speed, and forensic repeatability for production readiness.
