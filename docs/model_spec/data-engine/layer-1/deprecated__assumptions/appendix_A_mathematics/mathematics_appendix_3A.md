## Subsegment 3A: Capturing cross‑zone merchants
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
$\theta = \texttt{theta_mix}\in(0,1)$,
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

Assert $\Delta_z < \texttt{share_tolerance}$ for all $z$.

---

#### A.12 Cross-Linkage to Rounding Specification and CI Test Suite

All rounding, largest-remainder, and bump-rule logic must comply **exactly** with the canonical markdown specification in `docs/round_ints.md`.

* **Property-based test suite**: Every update to the rounding code or YAMLs is validated by running `ci/test_rounding_conservation.py` and associated scripts.
* **Formal contract**: Output is only considered valid if all tests pass; failure triggers build abort.

---

#### A.13 Universe Hash, Manifest Drift, and Error Contracts

* **Algorithm:**

  1. Concatenate byte digests in order (see A.8).
  2. Compute `universe_hash` as SHA-256 of the result.
  3. On allocation, write `universe_hash` to `<merchant_id>_zone_alloc.parquet` and `zone_alloc_index.csv`.
  4. On every downstream use, recompute and check; mismatch triggers `UniverseHashError`.
* **Contract**: Any drift detected in digest, hash, or allocation result aborts the pipeline.
* **ZoneAllocDriftError**: Raised and logged if any row in `zone_alloc_index.csv` mismatches on hash replay.

---

#### A.14 Output Schema and Column Contract

* **Output Parquet Schema for `<merchant_id>_zone_alloc.parquet`:**
    
    | Column        | Type     | Description                              |
    |---------------|----------|------------------------------------------|
    | merchant_id   | int64    | Merchant identifier                      |
    | tzid          | string   | Zone identifier                          |
    | n_zones       | int32    | Number of zones allocated                |
    | n_allocated   | int32    | Number of outlets allocated to this zone |
    | is_major_zone | bool     | True if fallback major zone              |
    | expectation   | float64  | Real expectation before rounding         |
    | residual      | float64  | Residual from rounding step              |
    | bump_applied  | bool     | True if bump rule triggered              |
    | universe_hash | char(64) | Allocation lineage (hex)                 |

* **Sorting contract:** Rows sorted by `tzid` ascending, then by `merchant_id`.
* **Null handling:** No column nullable; all fields required.

---

#### A.15 Licence Provenance and Enforcement

* **Each governed YAML/CSV or code artefact must be accompanied by its licence file in `LICENSES/`**.
* The licence’s SHA-256 digest is recorded in the manifest and checked on every CI run.
* Any missing or mismatched licence digest aborts the build.

---

#### A.16 End-to-End Replay/Isolation Guarantees

* **Given the governing YAMLs, `universe_hash`, and master seed, all zone allocation results must be exactly replayable on any system.**
* **Any non-replayability, mismatch, or hidden state is a spec violation and triggers pipeline abort.**

---

#### A.17 CI/Validation Output Artefact Enforcement

* **All property-based test outputs, barcode-slope validation logs, zone-share convergence logs, and drift/error events must be written as governed artefacts.**
* **CI failure logs are tracked, reviewed, and referenced in the manifest for every run.**