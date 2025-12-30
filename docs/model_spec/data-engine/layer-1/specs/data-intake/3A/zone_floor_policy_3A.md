# Authoring Guide — `zone_floor_policy_3A` (3A.S2 Floor / Bump Rules for α-priors)

## 0) Purpose

`zone_floor_policy_3A` is a **sealed, deterministic** policy consumed by **3A.S2** to convert **raw country×tzid Dirichlet α priors** into **effective α priors** via *floor / bump* rules.

This policy exists to prevent pathological “vanishing zones” outcomes (e.g., α so small that later draws/integerisation effectively erase a zone), while keeping the behaviour **RNG-free** and **byte-stable**.

---

## 1) File identity (MUST)

* **Artefact name (registry):** `zone_floor_policy`
* **Path:** `config/allocation/zone_floor_policy.yaml`
* **Schema authority:** `schemas.3A.yaml#/policy/zone_floor_policy_v1`
* **Token-less posture:** do **not** embed any digest in the file; digest is tracked by **3A.S0 sealing inventory**.

---

## 2) Required schema shape (MUST)

Top-level object:

* `version` : string (real governance tag; not placeholder)
* `floors` : array of objects

Each `floors[i]` object (no extra keys; `additionalProperties: false`) MUST contain:

* `tzid` : IANA tzid string
* `floor_value` : number, `>= 0.0`
* `bump_threshold` : number, `0.0 ≤ bump_threshold ≤ 1.0`
* `notes` : string (optional)

---

## 3) Pinned semantics (how S2 interprets these fields)

This guide pins an **unambiguous v1 interpretation** so Codex can’t “wing it”.

For each country `c` and zone `z ∈ Z(c)`:

1. **Resolve raw α**

* Let `alpha_raw(c,z)` be the raw prior mass from `country_zone_alphas` after reconciling to the zone universe `Z(c)`.
* If `(c,z)` exists in `Z(c)` but is missing from the raw pack, S2 treats `alpha_raw(c,z) = 0.0` (so floors can still operate deterministically).

2. **Compute raw share (for bump gating)**

* Let `alpha_sum_raw(c) = Σ_{z∈Z(c)} alpha_raw(c,z)`.
* If `alpha_sum_raw(c) == 0`, S2 MUST still remain deterministic:

  * treat every `share_raw(c,z) = 0.0` (so only `bump_threshold == 0.0` entries can activate floors), and
  * rely on floors to make `alpha_sum_effective(c) > 0`.

Otherwise:

* `share_raw(c,z) = alpha_raw(c,z) / alpha_sum_raw(c)`.

3. **Floor activation**

* Lookup the policy row for tzid `z`:

  * if absent: `floor_value(z)=0.0`, `bump_threshold(z)=1.0` (so it never activates).
* Define:

  * `is_bump_candidate(c,z) = (share_raw(c,z) ≥ bump_threshold(z))`.

4. **Floor pseudo-count**

* `floor_alpha(c,z) = floor_value(z)` if `is_bump_candidate(c,z)` else `0.0`.

5. **Effective α (v1)**

* `alpha_effective(c,z) = max(alpha_raw(c,z), floor_alpha(c,z))`.

Recommended diagnostic flags S2 may emit (not required by schema, but good practice):

* `floor_applied = (alpha_effective > alpha_raw)`
* `bump_applied = floor_applied` (in v1 “bump” is the act of applying the floor)

**Key point:** `bump_threshold` is the *activation gate*.

* If you want a floor that always applies when raw α is small/missing, set `bump_threshold = 0.0`.
* If you want floors to apply only to **dominant** zones, set `bump_threshold` high (e.g., `0.6`).

---

## 4) Deterministic authoring algorithm (Codex-no-input, “real-deal”)

This policy must be **large and plausible** (not a tiny sample list). Codex MUST generate it deterministically from already-shopped references.

### 4.1 Inputs (MUST exist)

* `tz_world_2025a` (to obtain the global tzid domain actually used by the engine)
* `iso3166_canonical_2024` (country spine, used to compute tzid presence counts)

If either is missing → **FAIL CLOSED**.

### 4.2 Domain to cover (MUST)

Let `T = { tzid }` be the set of tzids appearing in `tz_world_2025a`.
Codex MUST author a `floors[]` row for **every** `tzid ∈ T`.

### 4.3 Compute tzid “presence score” (deterministic, no geospatial math required)

For each tzid `z ∈ T`:

* `k(z) = number of distinct countries c where z ∈ Z(c)`
  (derive `Z(c)` from `tz_world_2025a` and count unique `country_iso` per tzid)

### 4.4 Assign bump thresholds (non-toy but simple)

Define:

* `k_max = max_z k(z)`
* `s(z) = log1p(k(z)) / log1p(k_max)` in `[0,1]`

Then set:

* `bump_threshold(z) = 0.60` if `s(z) ≥ 0.70`  (dominant-only bump for widely present tzids)
* else `bump_threshold(z) = 0.00`              (always-eligible floor for the rest)

This yields a realistic mixed posture: some tzids are treated “dominant-bump only”, most remain “min-mass” eligible.

### 4.5 Assign floor values (pseudo-count scale, deterministic)

Use a bounded mapping that won’t distort priors but isn’t “all zeros”.

Let:

* `phi_min = 0.01`
* `phi_max = 0.12`

Set:

* `floor_value(z) = phi_min + (phi_max - phi_min) * sqrt(s(z))`

Then, if `bump_threshold(z) == 0.60`, slightly boost to reflect “dominant-zone stability”:

* `floor_value(z) = floor_value(z) * 1.25`

Finally clamp:

* `floor_value(z) = min(max(floor_value(z), 0.0), 0.25)`

### 4.6 Ordering (MUST)

Write `floors[]` sorted by:

* `tzid` ascending

This keeps bytes stable and makes diffs reviewable.

### 4.7 Notes (optional)

Either omit `notes` entirely, or set it deterministically, e.g.:

* `"derived_from=tz_world_2025a; rule=v1; k=...; s=...;"`

Avoid timestamps.

---

## 5) Realism floors (MUST; prevents toy configs)

Codex MUST fail closed if any of these fail:

### 5.1 Coverage & size

* `len(floors) == |T|` (full tzid domain coverage)
* every `tzid` is unique
* every `tzid` in policy exists in `tz_world_2025a`

### 5.2 Non-degeneracy

* At least **50 tzids** have `floor_value ≥ 0.05` (ensures meaningful mass exists)
* At least **200 tzids** have `floor_value > 0.0` (prevents near-all-zero toy floors)
* At least **two distinct** `bump_threshold` values exist, and:

  * ≥ 10% of tzids have `bump_threshold == 0.60`
  * ≥ 50% of tzids have `bump_threshold == 0.00`

### 5.3 Numeric sanity

* `0.0 ≤ bump_threshold ≤ 1.0` for all entries
* `floor_value ≥ 0.0` for all entries

---

## 6) Minimal structure example (NOT a real file)

Real file MUST contain one row per tzid in `tz_world_2025a`.

```yaml
version: v1.0.0
floors:
  - tzid: Africa/Abidjan
    floor_value: 0.034
    bump_threshold: 0.00
  - tzid: Europe/London
    floor_value: 0.118
    bump_threshold: 0.60
```

---

## 7) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. Validates against `schemas.3A.yaml#/policy/zone_floor_policy_v1`.
3. `version` is non-placeholder (e.g., `v1.0.0`).
4. `floors[]` covers exactly the tzid domain from `tz_world_2025a`.
5. Realism floors in §5 pass.
6. Sorted by `tzid` ascending; stable formatting (UTF-8, LF, no timestamps).

If any check fails → **FAIL CLOSED** (do not publish; do not seal).

---

## Placeholder resolution (MUST)

- Replace placeholder floor thresholds with final numeric floors (no TODOs).
- Replace any example zone sets with the real zone taxonomy/vocab.
- Replace placeholder policy IDs/versions with final identifiers.

