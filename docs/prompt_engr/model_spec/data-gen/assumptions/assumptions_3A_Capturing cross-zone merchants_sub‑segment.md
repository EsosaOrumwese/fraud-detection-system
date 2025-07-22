Below is the *fully explicit, assumption‑surfaced companion record* for **“Capturing cross‑zone merchants.”**
It mirrors—one‑for‑one—the structure you approved for the *Routing‑transactions* companion: every concept is spelled out in long‑form prose, naming the artefact that stores it, the exact line of code or deterministic equation that consumes it, the digest field that proves the artefact’s use, and the continuous‑integration (CI) test that will flag drift or tampering. Nothing is left to implication; every numeric pathway is documented to the byte.

---

#### 1 Threshold θ that decides whether a country needs an internal time‑zone split

The code never asks “is this country important enough to mix?” by hard‑wiring a number. Instead it reads a YAML file called `config/allocation/zone_mixture_policy.yml`. That file contains a single key `theta_mix`, whose default scalar value is **0.01**. During the allocation pass the algorithm takes the country‑mass vector **v** produced by the hurdle layer, normalised so that its entries sum to one. For each entry $v_c$, the condition $v_c > \theta_{\text{mix}}$ is evaluated; if true the country’s outlets are earmarked for a time‑zone mixture. Because the value comes from YAML rather than code, any reviewer can lower it to 0.005, rerun the build and observe that more countries enter the mixture queue. A SHA‑256 digest of that YAML file is computed at build time and stored in the dataset manifest under the key `theta_digest`. The test `ci/test_mix_threshold.py`, executed in CI, loads the same YAML, recomputes the queue and byte‑compares it to the queue recorded in every `<merchant_id>_zone_alloc.parquet`. If any difference is found—meaning someone edited the YAML but failed to regenerate the parquet—the build aborts immediately.

#### 2 Dirichlet hyper‑parameters α that encode public settlement shares

The probability law inside each mixed country is not frozen in code either; it lives in `config/allocation/country_zone_alphas.yaml`. Keys are two‑letter ISO country codes, and each key maps to a nested object whose keys are `TZID` strings and whose values are positive integers. Those integers are Dirichlet concentration parameters $\alpha_z$. They are derived by the script `make_zone_alphas.py`, which ingests two years of anonymised settlement aggregates, computes the empirical zone share $\pi_z$ in each country, multiplies by a global smoothing constant $\tau$ (also stored in the YAML, default **200**) and rounds to the nearest integer. Because the YAML stores raw integers, anyone can check the implied shares by normalising the vector and see that it reproduces the public data. The entire YAML is hashed to `zone_alpha_digest` in the manifest. The allocation algorithm loads the vector, instantiates NumPy Gamma samplers on a Philox sub‑stream keyed by `(merchant_id, country_iso)`, draws $Z_c$ positive Gamma variates, divides each by their sum to obtain a simple Dirichlet draw, multiplies by the integer outlet count $N_c$ already committed for that country and hands the expectation vector to the largest‑remainder integeriser. Because every call to the random generator is driven by the Philox counter, the same seed reproduces the same Gamma sequence, and hence the same outlet integers.

#### 3 Deterministic integerisation and the “bump” rule that rescues thin zones

Once the real‑valued expected counts $e_z$ are in hand, the algorithm performs largest‑remainder rounding. It floors each $e_z$ to an integer, records the fractional part $f_z$, adds up the floors to see how many outlets remain unassigned and distributes the remainder to the zones with largest $f_z$. This is deterministic because ties are broken alphabetically by `TZID`. However, corner cases arise when a zone’s expectation is high (say, 0.9) yet rounding would assign it zero outlets because $f_z < f_{z'}$ for someone else. To avoid wiping out such a zone, the code applies a bump rule: after standard rounding, it searches for any zone whose $e_z > 0.8$ and integer allotment is zero. For each such casualty, it adds one outlet to that zone and deducts one outlet from the zone in that same country that currently has the greatest integer count (alphabetic tie‑break again). Because all operations are performed in integer arithmetic and because the casualty list is traversed in alphabetic order, the bump rule is deterministic under identical inputs. Its functional spec is written in `docs/round_ints.md`, and a property‑based test in CI (`ci/test_rounding_conservation.py`) generates 10 000 random expectation vectors, runs the implementation, and asserts the sum of integers equals the requested country total every time.

#### 4 Fallback to a single “major” time‑zone when the country is too small

Countries whose mass lies at or below θ bypass the Dirichlet logic. The code consults a CSV file called `artefacts/allocation/country_major_zone.csv`, created by scanning the frozen tz‑world shapefile, grouping polygons by ISO code, computing land area in square kilometres and choosing the `TZID` with the maximum area. The chosen zone is then assigned all outlets in that country. The CSV’s SHA‑256 digest is stored under `major_zone_digest` in the manifest. Because the shapefile’s polygons are version‑pinned (`tz_world_2025a.shp`), the area ranking is immovable unless a new shapefile version is adopted, in which case both digests change and CI demands a full rebuild.

#### 5 Zone‑floor vector φ\_z that protects micro‑state offsets

Certain micro‑state zones (for example, `Europe/San_Marino`) can disappear if the host country draws only two outlets and normal rounding steals them both. To guarantee that every zone which genuinely appears in clearing files also appears in at least one synthetic row, the YAML `config/allocation/zone_floor.yml` lists floors for selected `TZID`s. The list is sparse: fewer than twenty entries, each a small integer, mostly one. After the bump rule completes, the allocator scans every floor. If a zone’s integer count is below its floor, the deficit is stolen from the largest zone in the same country, again in a deterministic way. The floor YAML’s digest, `zone_floor_digest`, is recorded; CI test `ci/test_zone_floor.py` regenerates the allocation and verifies the floors hold.

#### 6 Log‑normal corporate‑day multiplier γ\_d that induces cross‑zone covariance

Mixer geography alone would leave independent LGCP arrivals per zone. To reproduce the correlated surges seen in audit logs, the simulator creates a latent multiplier γ\_d for every merchant and every UTC calendar day. The variance $\sigma_{\gamma}^{2}$ lives in `config/routing/routing_day_effect.yml` under key `sigma_gamma_sq`, default **0.15**. At the stroke of 00:00 UTC, the merchant’s Philox sub‑stream draws one 64‑bit uniform; the inverse‑Gaussian transform produces $\log\gamma_d$ with mean $-\sigma_{\gamma}^{2}/2$. That Philox sub‑stream is seeded by computing the SHA‑256 of the UTF‑8 bytes of `global_seed` concatenated with the literal string `"gamma_day"` and the merchant’s `merchant_id`; this derivation is governed by `config/routing/rng_policy.yml` and its SHA‑256 is stored as `gamma_day_key_digest` in the manifest to enforce deterministic corporate‑day draws. During intensity evaluation the LGCP engine multiplies every site’s mean μ by γ\_d, draws the Poisson arrivals, and then divides μ by γ\_d when handing probabilities to the alias router so that long‑run shares remain exact. Every γ\_d value is written into a hidden dimension table `(merchant_id, day_index, gamma_value)`. The CI replay job recalculates γ\_d from seed and YAML, re‑reads the stored table and asserts byte‑equality.

#### 7 “Universe hash” that freezes cross‑zone parameters into every alias file

The router must know that the alias tables correspond to the same zone allocations and day‑effect variance that the allocator used. It computes

$$
h = \mathrm{SHA256}\bigl(\text{zone_alpha_digest}\;\|\;\text{theta_digest}\;\|\;\text{zone_floor_digest}\;\|\;\text{gamma_variance_digest}\bigr),
$$

concatenating the digests in that order. When each merchant’s alias table `<merchant_id>_alias.npz` is written, `h` is embedded in the file’s NumPy metadata as `universe_hash`. At routing time the router recomputes h from the live YAMLs and compares to the alias file; any mismatch raises `UniverseHashError`, prints all constituent digests, and kills the process. Thus an engineer cannot tweak α or θ, rerun routing, and forget to rebuild alias tables: the guard fires instantly.

#### 8 Per‑merchant zone‑allocation Parquet and its drift sentinel

The allocator emits `artefacts/allocation/<merchant_id>_zone_alloc.parquet`, schema `(country_iso STRING, tzid STRING, N_outlets UINT16)` sorted by `country_iso`, then `tzid`. Immediately after writing, it hashes the Parquet byte‑for‑byte and appends the line

```
<merchant_id>,<sha256>
```

to `artefacts/allocation/zone_alloc_index.csv`. When the router starts, it loads that index, re‑hashes the Parquet, compares; if drift exists it raises `ZoneAllocDriftError` and prints both hashes. This guarantees that zombie Parquets cannot linger when YAMLs change.

#### 9 CI‑level offset‑barcode detection

Every night a 30‑day synthetic slice is generated in a separate job. For each merchant with at least three distinct `local_time_offset` values, a matrix $M[\text{offset},\,\text{utc\_hour}]$ of counts is built. A fast Hough transform scans for the strongest line; the slope is measured in offsets per UTC hour.The YAML `config/validation/cross_zone_validation.yml` sets `barcode_slope_low = -1` and `barcode_slope_high = -0.5`. A SHA‑256 of that file is recorded in the manifest under `cross_zone_validation_digest`, and the CI test `ci/test_cross_zone_validation.py` byte‑compares the live YAML against it to prevent untracked threshold changes. If the slope still lies outside bounds, the job fails, saving the heat‑map PNG for manual inspection. Because Earth rotates 15° per hour, a synthetic merchant that lacks the diagonal stripe betrays a broken zone allocation or a missing corporate‑day effect.

#### 10 CI‑level zone‑share convergence test

The same 30‑day slice yields empirical zone shares $\hat{s}^{(c)}_z$. The allocator’s integer counts give the target share $N^{(c)}_z/N_c$. `config/validation/cross_zone_validation.yml` sets `share_tolerance=0.02`. Any absolute difference beyond that fails the job, printing the offending `(merchant, country, tzid, observed, expected)` five‑tuple. Because the alias router and LGCP daily modulation preserve long‑run shares, any breach indicates either rounding errors bubbling through or mis‑plumbed γ\_d.

#### 11 Random‑stream isolation formally proven

`docs/rng_proof.md` shows that each Dirichlet draw consumes $Z_c$ independent Gamma samples, each of which increments the Philox counter by exactly one 128‑bit block. Because the sub‑stream key is a 64‑bit hash of `(merchant_id, country_iso)` and the block size is astronomically large, streams cannot overlap even if the number of merchants grows by orders of magnitude. CI script `ci/replay_zone_alloc.py` reloads the YAMLs, reruns allocation with the same seed inside a fresh interpreter, regenerates the Parquet and asserts byte‑equality—a complete end‑to‑end replay test.

#### 12 Licence lineage recorded in manifest

`config/allocation/country_zone_alphas.yaml` inherits data from Visa and Mastercard cross‑border indices, redistributed under their research‑use licence; the licence text is copied verbatim into `LICENSES/visa_mcx.md`. `config/allocation/zone_floor.yml` and `config/allocation/zone_mixture_policy.yml` are analyst‑authored and released CC0. The manifest field `licence_digests` stores a SHA‑1 of each licence file; CI fails if a licence text changes but its digest line in the manifest is not updated, preventing silent licence substitution.

---

### Appendix A – Mathematical Definitions & Conventions

Below are the precise formulae, units, code cross‑references and domain notes for every core computation in **“Capturing cross‑zone merchants.”**

---

#### A.1 Mixture Threshold Test

**Purpose:** decide which countries require time‑zone splitting.
**Code:** `allocation/mixture.py:flag_escalation_countries`
Given the normalised country‑mass vector

$$
\mathbf{v} = [v_1,\dots,v_C],\quad \sum_{c=1}^C v_c = 1,
$$

and threshold
$\theta = \texttt{theta\_mix}\in(0,1)$,
compute the escalation set

$$
\mathcal{E} = \{\,c: v_c > \theta\,\}.
$$

Entries in $\mathcal{E}$ undergo Dirichlet allocation.

> **Domain note:** $\theta$ is loaded from YAML (ms), not hard‑coded.

---

#### A.2 Dirichlet Zone Shares

**Purpose:** sample a continuous prior for zone‑share expectations.
**Code:** `allocation/zone_allocator.py:compute_dirichlet_shares`
Let $\alpha = [\alpha_1,\dots,\alpha_Z]$ from YAML and integer outlet count $N$. Draw independent Gamma variates

$$
g_z \sim \mathrm{Gamma}(\alpha_z,1),
$$

then set

$$
s_z = \frac{g_z}{\sum_{k=1}^Z g_k},
\quad
\sum_{z=1}^Z s_z = 1.
$$

Expectation vector

$$
e_z = s_z \times N  
\quad(\text{real},\;\sum_z e_z = N).
$$

---

#### A.3 Largest‑Remainder Integerisation

**Purpose:** convert real expectations $e_z$ into integers summing exactly to $N$.
**Code:** `allocation/zone_allocator.py:largest_remainder_round`
Compute floors and residuals:

$$
\bar n_z = \lfloor e_z\rfloor,  
\quad r_z = e_z - \bar n_z,  
\quad R = N - \sum_{z=1}^Z \bar n_z.
$$

Sort zones by descending $r_z$ (tie‑break on `TZID`), then for the top $R$ zones increment $\bar n_z$ by one. The result $\{n_z\}$ satisfies $\sum_z n_z = N$.

---

#### A.4 Bump Rule for High‑Expectation Zones

**Purpose:** ensure zones with large expectation never drop to zero.
**Code:** `allocation/zone_allocator.py:apply_bump_rule`
For each zone $z$ such that

$$
e_z > 0.8 \quad\text{and}\quad \bar n_z = 0,
$$

set
$\bar n_z \leftarrow 1$
and subtract one outlet from the zone $w$ with maximal $\bar n_w$ (tie‑break on `TZID`). This preserves $\sum_z \bar n_z = N$.

---

#### A.5 Fallback Major‑Zone Selection

**Purpose:** assign all outlets to a single zone when $v_c \le \theta$.
**Code:** `allocation/zone_allocator.py:select_major_zone`
Let CSV rows $(\texttt{country_iso},\;\texttt{tzid},\;A)$ with $A$ area in km². Compute

$$
\texttt{tzid}_{\max} = \arg\max_{\texttt{tzid}} A
$$

and set $n_{\texttt{tzid}_{\max}} = N$, all others zero.

---

#### A.6 Zone‑Floor Enforcement

**Purpose:** protect micro‑zones from elimination.
**Code:** `allocation/zone_allocator.py:enforce_zone_floors`
Given floor vector $\phi_z$ from YAML and integer counts $\bar n_z$, for any $z$ with

$$
0 < \bar n_z < \phi_z,
$$

increase $\bar n_z$ to $\phi_z$ and deduct $\phi_z - \bar n_z$ outlets from the zone $w$ with largest $\bar n_w$.

---

#### A.7 Corporate‑Day Log‑Normal Multiplier

**Purpose:** induce cross‑zone covariance in arrivals.
**Code:** `routing/day_effect.py:compute_gamma`
For each UTC day index $d$, draw uniform

$$
u_d = \mathrm{Philox}(\texttt{key},\;0)\in[0,1),
$$
Here, $(\texttt{key}=\mathrm{SHA256}(\texttt{global_seed}\;\|\;"gamma_day"\;\|\;\texttt{merchant_id}))$. This derivation is governed by `config/routing/rng_policy.yml`, and its SHA‑256 is stored as `gamma_day_key_digest` in the manifest to guarantee reproducible corporate‑day streams.

then

$$
\log\gamma_d = -\tfrac12\,\sigma^2 + \sigma\,\Phi^{-1}(u_d),
\quad
\gamma_d = \exp(\log\gamma_d),
$$

where $\sigma^2 = \texttt{sigma_gamma_sq}$. Multiplicative in LGCP mean, later divided out.

---

#### A.8 Universe‑Hash Construction

**Purpose:** guard cross‑artifact integrity.
**Code:** `allocation/universe_hash.py:compute_universe_hash`
Concatenate manifest digests in byte order:

$$
D = \text{zone_alpha_digest}\;\|\;\theta_digest\;\|\;\text{zone_floor_digest}\;\|\;\gamma_variance_digest\;\|\;\text{zone_alloc_parquet_digest},
$$

then
$\mathrm{universe_hash} = \mathrm{SHA256}(D).$

---

#### A.9 Drift Sentinel via Parquet Index

**Purpose:** detect stale allocations at runtime.
**Code:** `allocation/zone_allocator.py:emit_drift_index`
After writing `<merchant_id>_zone_alloc.parquet`, compute
$\delta = \mathrm{SHA256}(\text{file bytes})$
and append `(<merchant_id>,\delta)` to `zone_alloc_index.csv`; the router re‑loads and re‑hashes to raise `ZoneAllocDriftError` on mismatch.

---

#### A.10 Offset‑Barcode Slope Detection

**Purpose:** validate corporate‑day surges in CI.
**Code:** `validation/cross_zone_validation.py:detect_offset_barcode`
Build count matrix $M[o,h]$ for offsets $o$ and UTC hours $h$. Apply Hough transform $H(ρ,θ)$ to the set of points $\{(o,h)\}$; find $(ρ^*,θ^*) = \arg\max H$. The slope in offsets per hour is

$$
m = -\tan(θ^*),
$$

and must satisfy
$-1 \le m \le -0.5.$

---

#### A.11 Zone‑Share Convergence Check

**Purpose:** enforce long‑run share fidelity in CI.
**Code:** `validation/cross_zone_validation.py:check_share_convergence`
Let empirical counts $c_z$ and normalized weights $n_z/N$. Compute empirical share

$$
\hat s_z = \frac{c_z}{\sum_k c_k},
\quad
\Delta_z = \bigl|\hat s_z - \tfrac{n_z}{N}\bigr|.
$$

Assert $\Delta_z < \texttt{share\_tolerance}$ for all $z$.

---

*All formulae reference code modules and artefacts by path, with units, types, and invariant behaviours defined. With this appendix, every transformation in the cross‑zone layer is unambiguously specified.*

---

## Governed Artefact Registry

Append this table to the end of **assumptions\_3A\_Capturing cross‑zone merchants\_sub‑segment.txt**. Every entry must be declared in the main manifest with the indicated metadata; any change to the file, its semver or its digest will produce a new manifest digest and trigger CI checks.

| ID / Key                    | Path Pattern                                            | Role                                                        | Semver Field | Digest Field                   |
|-----------------------------|---------------------------------------------------------|-------------------------------------------------------------|--------------|--------------------------------|
| **zone\_mixture\_policy**   | `config/allocation/zone_mixture_policy.yml`             | Attention‑threshold θ for escalation queue                  | `semver`     | `theta_digest`                 |
| **country\_zone\_alphas**   | `config/allocation/country_zone_alphas.yaml`            | Dirichlet concentration parameters α per ISO country→TZID   | `semver`     | `zone_alpha_digest`            |
| **rounding\_spec**          | `docs/round_ints.md`                                    | Functional spec for largest‑remainder & bump rule           | n/a          | `rounding_spec_digest`         |
| **zone\_floor**             | `config/allocation/zone_floor.yml`                      | Minimum outlet counts φₙ for micro‑zones                    | `semver`     | `zone_floor_digest`            |
| **country\_major\_zone**    | `artefacts/allocation/country_major_zone.csv`           | Fallback mapping country→major TZID by land‑area            | n/a          | `major_zone_digest`            |
| **zone\_alloc\_parquet**    | `artefacts/allocation/<merchant_id>_zone_alloc.parquet` | Per‑merchant `(country_iso, tzid, N_outlets)` allocation    | n/a          | `zone_alloc_parquet_digest`    |
| **zone\_alloc\_index**      | `artefacts/allocation/zone_alloc_index.csv`             | Drift‑sentinel index mapping `<merchant_id>,<sha256>`       | n/a          | `zone_alloc_index_digest`      |
| **routing\_day\_effect**    | `config/routing/routing_day_effect.yml`                 | Corporate‑day log‑normal variance σ\_γ²                     | `semver`     | `gamma_variance_digest`        |
| **rng\_proof**              | `docs/rng_proof.md`                                     | Formal RNG‑isolation proof                                  | n/a          | `rng_proof_digest`             |
| **cross\_zone\_validation** | `config/validation/cross_zone_validation.yml`           | CI thresholds for offset‑barcode slope & share convergence  | `semver`     | `cross_zone_validation_digest` |
| **license\_files**          | `LICENSES/*.md`                                         | Licence texts for public data and analyst‑authored policies | n/a          | `licence_digests`              |

**Notes:**

* `n/a` in **Semver Field** indicates no inline semver; the file’s path and digest alone govern it.
* Replace `<merchant_id>` with the zero‑padded merchant code.
* All paths use Unix‑style forward slashes and are case‑sensitive.
* Any addition, removal, or version change of these artefacts must follow semver and manifest rules and will automatically refresh the overall manifest digest via CI.