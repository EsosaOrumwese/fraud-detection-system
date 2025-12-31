# Authoring Guide — `policy.s3.thresholds.yaml` (Deterministic integer bounds & feasibility thresholds)

This policy is **optional** and exists only to enable the **bounded Hamilton** variant of integer allocation (floors/ceilings) when distributing a merchant’s total outlets `N` across its legal country set `C` (home + selected foreigns).

If this file is absent **or** `enabled: false`, the engine uses the **unbounded** integerisation path.

---

## 1) File identity (binding)

* **Name:** `policy.s3.thresholds.yaml`
* **Path:** `config/policy/s3.thresholds.yaml`
* **Role:** deterministic lower/upper integer bounds `(L_i, U_i)` and feasibility behaviour for integerisation.
* **Dependencies:** `iso3166_canonical_2024` (only if you later add per-ISO overrides; v1 does not require overrides).

---

## 2) What the engine expects this policy to provide

For each merchant, given:

* `N` = total outlets for that merchant (integer, `N ≥ 1`)
* `C` = set of legal countries for that merchant (includes home; size `M = |C|`)

The policy must deterministically produce per-row bounds:

* `L_i` (lower bound) and `U_i` (upper bound) for every country `i ∈ C`

Then the bounded Hamilton method applies, and **must enforce**:

* feasibility guard: `Σ L_i ≤ N ≤ Σ U_i`
* final counts satisfy: `L_i ≤ count_i ≤ U_i` and `Σ count_i = N`

If feasibility fails, the policy must dictate what happens (v1: fail merchant).

---

### 2.1 Realism sanity (MUST)

If you enable bounds, you MUST ensure they do not cause large-scale infeasibility for realistic `(N, |C|)` pairs produced by your upstream states. A bounded policy that fails a large fraction of merchants will destroy realism.

---

## 3) Required top-level structure (MUST)

```yaml
semver: "<MAJOR.MINOR.PATCH>"
version: "<YYYY-MM-DD>"
enabled: <true|false>

home_min: <int >= 0>

force_at_least_one_foreign_if_foreign_present: <true|false>
min_one_per_country_when_feasible: <true|false>

foreign_cap_mode: "none" | "n_minus_home_min"

on_infeasible: "fail"
```

### 3.1 Placeholder resolution (MUST)

Replace the angle-bracket tokens in the shape block with:

* `<MAJOR.MINOR.PATCH>`: semantic version string like `1.0.0`.
* `<YYYY-MM-DD>`: release date label for the policy.
* `<true|false>`: YAML boolean value (`true` or `false`).
* `<int >= 0>`: non-negative integer.

Do not introduce additional keys without a semver bump.

Rules:

* Unknown keys: **reject** (fail closed).
* `on_infeasible` is pinned to `"fail"` in v1 (no silent fallback).

---

## 4) Deterministic bound construction (Codex implements; this doc specifies)

Let:

* `M = |C|`
* `is_home(i)` is true for the home row, false otherwise

### 4.1 Home row bounds

Compute:

* `L_home = min(home_min, N)`  *(so it never exceeds N)*

Compute `U_home`:

* If `force_at_least_one_foreign_if_foreign_present == true` AND `M > 1` AND `N >= 2`:

  * `U_home = N - 1`  *(forces at least 1 non-home outlet)*
* Else:

  * `U_home = N`

### 4.2 Foreign row bounds (for each non-home i)

Lower bound `L_foreign`:

* If `min_one_per_country_when_feasible == true` AND `N >= M` AND `N >= 2`:

  * `L_foreign = 1`  *(enforce at least one outlet per country when feasible)*
* Else:

  * `L_foreign = 0`

Upper bound `U_foreign`:

* If `foreign_cap_mode == "n_minus_home_min"`:

  * `U_foreign = max(L_foreign, N - L_home)`
    *(ensures home minimum can always be satisfied; when N==1 this becomes 0)*
* If `foreign_cap_mode == "none"`:

  * `U_foreign = N`

### 4.3 Feasibility guard (MUST)

After constructing all bounds:

* If `Σ L_i > N` OR `Σ U_i < N`:

  * apply `on_infeasible`
  * v1 requires: **FAIL** (no partial outputs)

---

## 5) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
semver: "1.0.0"
version: "2024-12-31"

# Feature-flag
enabled: true

# Home country must keep at least one outlet (when N>=1)
home_min: 1

# If the merchant has any foreign countries in its legal set and N>=2,
# cap home to N-1 to force at least one non-home outlet.
force_at_least_one_foreign_if_foreign_present: true

# If N is large enough to give every country at least one (N >= |C|, N>=2),
# enforce min 1 per foreign country; otherwise allow 0 for some countries.
min_one_per_country_when_feasible: true

# Foreign cap ensures home_min remains satisfiable
foreign_cap_mode: "n_minus_home_min"

# Feasibility behaviour
on_infeasible: "fail"
```

This baseline is:

* deterministic
* usually feasible
* enforces “crossborder means at least one foreign outlet” when foreigns exist and `N>=2`
* enforces “one per country” only when mathematically feasible (`N >= |C|`)

---

## 6) Acceptance checklist (Codex must enforce)

* YAML parses with **no duplicate keys**
* Required keys present; no unknown keys
* `semver` matches `^\d+\.\d+\.\d+$`
* `version` matches `^\d{4}-\d{2}-\d{2}$`
* `enabled` boolean
* `home_min` integer ≥ 0
* `foreign_cap_mode ∈ {"none","n_minus_home_min"}`
* `on_infeasible == "fail"`

Runtime sanity checks (policy self-test; SHOULD):

* Using expected ranges of `N` (from S2) and `|C|` (from S6), verify that infeasibility is rare and explain any intended failure regime.

* For a grid of `(N, M)` values (e.g., N=1..50, M=1..min(10,N+5)), compute bounds and verify:

  * `L_i ≤ U_i` for all i
  * feasibility guard passes for the “typical” region (it will sometimes fail for adversarial M/N; that’s acceptable because `on_infeasible: fail` is explicit)

---
