# Authoring Guide — `virtual_validation.yml` (3B virtual validation tolerances, v1)

## 0) Purpose

`virtual_validation.yml` is the **sealed tolerance pack** used by 3B’s validation contract/harness to judge whether the **virtual/CDN surfaces** behave plausibly:

* **IP-country mix tolerance:** how far realised IP-country shares are allowed to deviate from the target mix implied by `cdn_country_weights.yaml`.
* **Settlement cut-off tolerance:** a time-window slack (seconds) used when validating settlement-day / cut-off boundary logic (to avoid false fails from boundary-adjacent events).

This file is **token-less** and must be authored deterministically. The file MUST be small, but its **values must be production-plausible**, not “toy defaults”.

---

## 1) File identity (MUST)

* **Dataset ID:** `virtual_validation_policy`
* **Path:** `config/virtual/virtual_validation.yml`
* **Schema authority:** `schemas.3B.yaml#/policy/virtual_validation_policy_v1`
* **Digest posture:** do **not** embed any file digest in-file; the SHA-256 is recorded by 3B.S0 sealing inventory.

---

## 2) Required file shape (MUST match schema)

Top-level YAML object with **exactly** these keys:

* `version` : string (non-placeholder governance tag, e.g. `v1.0.0`)
* `ip_country_tolerance` : number, `>= 0.0`
* `cutoff_tolerance_seconds` : integer, `>= 0`
* `notes` : string (optional)

*(Schema is fields-strict: no extra keys.)*

---

## 3) Pinned semantics (decision-free)

### 3.1 `ip_country_tolerance`

A single scalar tolerance used by “IP-country mix” validation tests.

**Pinned v1 interpretation:**
Let `p_target(c)` be the target country share from `cdn_country_weights.yaml` (after canonicalisation and normalisation).
Let `p_obs(c)` be the observed country share computed by the validation harness from one of:

* **Edge-catalogue view:** share of edges in `edge_catalogue_3B` with `country_iso = c`, aggregated per merchant or cohort.
* **Event view:** share of virtual events with `event.ip_country = c`, aggregated per merchant or cohort.

Then the harness applies the **max-absolute deviation** check over countries with non-trivial target mass:

* Define `C_active = { c : p_target(c) ≥ 1e-4 }`
* Require: `max_{c ∈ C_active} |p_obs(c) - p_target(c)| ≤ ip_country_tolerance`

If `C_active` is empty (should not happen in production mixes) → validation MUST FAIL.

### 3.2 `cutoff_tolerance_seconds`

A single slack window used by “settlement cut-off / clock” validation tests.

**Pinned v1 interpretation:**
When a test validates day-boundary logic (e.g., whether `settlement_day` and the chosen `settlement_cutoff_rule` are being applied consistently), any event whose **settlement-local time** is within:

* `± cutoff_tolerance_seconds`

of the cut-off boundary is treated as **boundary-ambiguous** and MUST be excluded from “hard” pass/fail comparisons (but MAY be counted for diagnostics).

This prevents false fails caused by seconds-level rounding or boundary jitter while keeping the rule strict away from the boundary.

---

## 4) Deterministic authoring algorithm (Codex-no-input)

### 4.1 Inputs (MUST exist)

Codex MUST read:

* `config/virtual/cdn_country_weights.yaml` (to obtain `edge_scale`)

If missing → **FAIL CLOSED**.

### 4.2 Choose `ip_country_tolerance` (non-toy, edge-scale aware)

Let `E = edge_scale` from `cdn_country_weights.yaml`.

Set:

* `ip_country_tolerance = clamp(max(0.01, 5.0 / E), 0.01, 0.05)`

Rationale:

* prevents “toy strictness” (`0.0`),
* scales sensibly if `edge_scale` is ever revised,
* remains tight enough to actually detect broken mixes.

### 4.3 Choose `cutoff_tolerance_seconds` (production-plausible)

Set:

* `cutoff_tolerance_seconds = 1800`  *(30 minutes)*

This is large enough to absorb boundary jitter, but small enough to keep validation meaningful.

### 4.4 Notes (optional, deterministic)

If you include `notes`, keep it static, e.g.:

* `"v1: ip_country_tolerance=max(0.01,5/E) clamped; cutoff_tolerance_seconds=1800"`

No timestamps.

---

## 5) Realism floors (MUST; fail closed)

Codex MUST abort authoring if any fails:

* `version` is placeholder-like (`test`, `example`, `todo`, `TBD`, etc.)
* `edge_scale` missing from `cdn_country_weights.yaml`
* `ip_country_tolerance < 0.005` or `ip_country_tolerance > 0.08`
* `cutoff_tolerance_seconds < 300` or `cutoff_tolerance_seconds > 7200`
* `cutoff_tolerance_seconds == 0` (toy / brittle)

---

## 6) Recommended v1 production file (example)

```yaml
version: v1.0.0
ip_country_tolerance: 0.010000
cutoff_tolerance_seconds: 1800
notes: "v1: ip_country_tolerance=max(0.01,5/E) clamped; cutoff_tolerance_seconds=1800"
```

*(Formatting of `ip_country_tolerance` can be plain decimal; keep it deterministic.)*

---

## 7) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. Validates against `schemas.3B.yaml#/policy/virtual_validation_policy_v1`.
3. `version` non-placeholder.
4. `cdn_country_weights.yaml` exists and `edge_scale` is readable.
5. `ip_country_tolerance` computed exactly by §4.2 and passes realism floors.
6. `cutoff_tolerance_seconds == 1800` and passes realism floors.
7. UTF-8, LF newlines, no timestamps.

If any check fails → **FAIL CLOSED** (do not publish; do not seal).
