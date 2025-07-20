Once the catalogue has given every merchant a concrete constellation of sites, each with a latitude, longitude, time‑zone and foot‑traffic scalar, the simulation must decide—millions of times per synthetic day—**which single outlet actually receives a candidate transaction**. That decision is orchestrated in the sub‑segment called *“Routing transactions through sites,”* and its ambition is to be indistinguishable from the logic that lives inside a real acquirer’s authorisation switch. The core requirement is to translate an abstract arrival event, generated upstream by the Log‑Gaussian‑Cox process in “local civil time”, into an `(event_time_utc, site_id)` pair whose spatial choice respects (1) the long‑run market share implied by foot‑traffic weights, (2) the cross‑zone synchrony observed when corporate promotions roll out, and (3) the brutally unforgiving reproducibility contract that governs the entire pipeline.

---

The routing engine’s first responsibility is to **freeze an immutable probability law** that maps every merchant’s outlet list to a set of normalised weights. Let the merchant have sites indexed by `i = 1 … N_m`. Each site carries a positive foot‑traffic scalar `F_i` inherited verbatim from the placement stage. The engine computes the raw share

$$
w_i = F_i \quad\text{for all } i,
$$

then normalises to obtain

$$
p_i = \frac{w_i}{\sum_{j=1}^{N_m} w_j}.
$$

These weights are written to disk once as a two‑column table `(site_id, p_i)` sorted lexicographically by `site_id`; this strict ordering, together with the fact that the sums of IEEE‑754 doubles are rounded identically on any IEEE‑compliant CPU, means that two developers running the build on different machines will obtain byte‑identical `p_i`.

Because naïve multinomial sampling in O(N) time would choke on global merchants that own thousands of outlets, the pipeline constructs **an alias table** per merchant. The deterministic alias construction proceeds by streaming through the `p_i` vector in the order stored on disk, pushing indices into a “small” or “large” stack according to whether `p_i < 1/N_m` or not, and then repeatedly popping one from each until neither stack holds any elements, filling the `prob` and `alias` arrays in place. At no point does the algorithm draw fresh random numbers: the entire table is a pure, deterministic function of the ordered probability vector. The resulting pair of arrays occupies exactly two 32‑bit integers per site and therefore fits comfortably in memory even for the largest chains in the synthetic universe.

Long‑run shares, however, are not enough; real data reveal a subtle **cross‑zone co‑movement** that flares up when a corporate promotion starts at 00:00 local time independent of the head‑office’s zone. To reproduce that phenomenon the routing engine introduces a **latent “corporate‑day” random effect γ\_d**, drawn once per merchant per simulated UTC day `d` from

$$
\log\gamma_d \sim \mathcal N\!\bigl(-\tfrac{1}{2}\sigma_{\gamma}^2,\; \sigma_{\gamma}^2\bigr),
$$

where the mean shift keeps `E[γ_d] = 1`. The variance `σ_γ²` is stored in `routing_day_effect.yml`, calibrated so that, in the real JPM audit logs used as reference, the Pearson correlation of site‑level hourly counts across time‑zones settles around 0.35. The draw occurs on the Philox sub‑stream reserved for the routing module, keyed by the merchant’s identifier; since only one γ\_d is drawn per UTC day per merchant, the random‑number budget is negligible and deterministic.

When the arrival engine proposes a local timestamp `t_local` for some merchant, it passes control to the router before UTC conversion. The router first computes the candidate’s UTC date `d` by subtracting the site’s current offset from `t_local`; it multiplies every `p_i` by `γ_d` and then **re‑normalises within the time‑zone group** to retain each zone’s diurnal shape. This modulation reproduces the observed fact that when a promo email lands in inboxes, the blast lifts every store in the company’s footprint at once, yet the uplift feels strongest inside each zone’s normal trading hours. Because γ\_d is multiplicative and common, re‑normalisation preserves the strictly positive ordering `p_i > 0` and therefore the already‑built alias table remains valid: the router only needs to scale the threshold it compares against the uniform random draw, avoiding any per‑transaction table rebuild.

With weights modulated, the router pulls a single 64‑bit uniform `u` from its Philox sub‑stream, computes the integer column index `k = floor(u * N_m)` and uses the pre‑computed `prob[k]` to decide whether to accept `k` or fall through to `alias[k]`. The whole operation is O(1) and branch‑predictable, so the CPU cost is a few nanoseconds even at high throughput.

Certain merchants are marked **“purely virtual”** in the catalogue. For them, `N_m` equals one by definition because an e‑commerce gateway with no physical storefront owns only the settlement site. Nevertheless reviewers expect variability in the apparent source country of IP addresses. To honour that, the single site gets a shadow list of virtual “edge nodes” whose country attribution follows the regional CDN distribution stored in `cdn_country_weights.yaml`. Routing among those virtual nodes happens with its own alias table built exactly as before, and the chosen node’s geo appears in the row as `ip_country` rather than `merchant_country`, letting downstream location‑mismatch features light up without ever falsifying the merchant’s brick‑and‑mortar footprint.

After an outlet is selected, the router returns its coordinate and `tzid` to the temporal engine, which converts `t_local` to UTC, completes gap/fold logic, and writes the transaction record. Because the router never alters `t_local`, all day‑part seasonality already injected by the LGCP engine survives intact at site granularity.

Finally, the engine logs a **routing checksum** once per million routed events: it hashes the tuple `(merchant_id, batch_index, cumulative_site_counts[])`, where the last element is the vector of how many events each site has received so far, and writes the checksum to `routing_audit.log`. A downstream integration‑test reruns the router in isolation with the same seed and asserts that the checksums match. If a developer mistakenly changes the order of random draws inside the router or alters the alias‑table logic, the audit will fail at the very first batch, guarding against silent erosion of reproducibility.

By anchoring the selection law in static, foot‑traffic‑based alias tables; by introducing a single, low‑entropy, corporate‑day random effect that synchronises zone‑separated sites; by honouring virtual gateways with a country‑weighted edge‑selection layer; and by welding every step to a manifest checksum and Philox stream isolation, the *“Routing transactions through sites”* sub‑segment delivers outlet‑level realism, computational speed, and forensic repeatability that satisfy the most severe production readiness review.
