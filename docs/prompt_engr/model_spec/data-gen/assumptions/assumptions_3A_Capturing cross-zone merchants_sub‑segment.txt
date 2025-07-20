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
