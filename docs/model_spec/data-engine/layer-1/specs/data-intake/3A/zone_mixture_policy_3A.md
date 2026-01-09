# Authoring Guide — `zone_mixture_policy_3A` (3A.S1 Mixture / Escalation Policy)

## 0) Purpose

`zone_mixture_policy_3A` is the **only governed decision surface** that 3A.S1 is allowed to interpret. It determines—**deterministically and RNG-free**—which `(merchant_id, legal_country_iso)` pairs are **escalated** into the zone-level Dirichlet + integerisation pipeline (3A.S2–S4) vs treated as **monolithic**.

This policy is sealed by **3A.S0** (and therefore contributes to `parameter_hash`). Its bytes are later hashed into the **routing universe hash** (3A.S5), so the file MUST be stable and timestamp-free.

---

## 1) File identity (MUST)

* **Artefact name (registry):** `zone_mixture_policy`
* **Path:** `config/layer1/3A/policy/zone_mixture_policy.yaml`
* **Schema authority:** `schemas.3A.yaml#/policy/zone_mixture_policy_v1`
* **Token-less posture:** do **not** embed any digest inside the file; digest is tracked by the S0 sealing inventory.

---

## 2) Required top-level keys (MUST)

Top-level object with **exactly** these keys (schema is `additionalProperties: false`):

* `policy_id` : string (MUST be `zone_mixture_policy_3A`)
* `version` : string (MUST be a real governance tag, e.g. `v1.0.0`)
* `theta_mix` : number in `[0.0, 1.0]`
* `rules` : array (optional by schema, but **required by this guide**; see §5)

---

## 3) Meaning of `theta_mix` (MUST)

`theta_mix` is the **mixing rate** used by S1 for *eligible* pairs:

* When a pair passes all **monolithic guard rules**, S1 computes a **deterministic** `u_det ∈ (0,1)` from `(merchant_id, legal_country_iso, parameter_hash)` and applies:

**Pinned u_det law (MUST; decision-free):**
* `msg = UTF8("3A.S1.theta_mix|" + merchant_id + "|" + legal_country_iso + "|" + parameter_hash_hex)`
* `x = first_8_bytes(SHA256(msg))` interpreted as uint64 big-endian
* `u_det = (x + 0.5) / 2^64`  (open interval)

* If `u_det < theta_mix` ⇒ `is_escalated = true`, `decision_reason = "default_escalation"`

* Else ⇒ `is_escalated = false`, `decision_reason = "legacy_default"`

This gives you a realistic “not everyone disperses across zones” mixture **without any RNG**.

> Note: If you later decide S1 should not use a hash-mix step, that’s a **policy version change** and an S1 behaviour change (don’t silently repurpose `theta_mix`).

---

## 4) Rule ladder semantics (MUST)

### 4.1 What rules are for

`rules[]` defines **deterministic guards and forced branches** that run **before** the `theta_mix` mixing step.

Rules are evaluated in array order. The **first matching rule wins**.

### 4.2 Rule object shape (MUST)

Each rule is an object with:

* `metric` (string)
* `threshold` (number)
* `decision_reason` (string)
* optional `bucket` (string) — may be omitted

### 4.3 Allowed metrics (MUST; decision-free)

To prevent “toy/ambiguous” rule DSLs, Codex MUST use only these metrics:

* `site_count_lt`
  Match if `site_count(m,c) < threshold`

* `zone_count_country_le`
  Match if `zone_count_country(c) ≤ threshold`

* `site_count_ge`
  Match if `site_count(m,c) ≥ threshold`

* `zone_count_country_ge`
  Match if `zone_count_country(c) ≥ threshold`

(Any other `metric` value ⇒ FAIL CLOSED in authoring validation.)

### 4.4 Allowed decision reasons + implied action (MUST)

To keep S1 implementation decision-free, **action is implied by `decision_reason`**:

**Monolithic reasons (implies `is_escalated=false`):**

* `forced_monolithic`
* `below_min_sites`
* `legacy_default`

**Escalated reasons (implies `is_escalated=true`):**

* `forced_escalation`
* `default_escalation`

(Any other `decision_reason` ⇒ FAIL CLOSED in authoring validation.)

---

## 5) Realism floors (MUST; prevents toy policies)

Codex MUST reject an authored policy if any fail:

### 5.1 Rule set must be non-trivial

* `rules` MUST exist and MUST have **at least 3 rules**.
* `rules` MUST include at least:

  * one `site_count_lt` rule (minimum size guard),
  * one `zone_count_country_le` rule with `threshold = 1` (single-zone countries are monolithic),
  * one forced escalation rule (`site_count_ge` or `zone_count_country_ge`) to ensure large chains / high-zone countries consistently escalate.

### 5.2 Threshold sanity

* For `site_count_lt` minimum guard, `threshold` MUST be in `[2, 10]`.
* For forced escalation by size, `site_count_ge.threshold` MUST be in `[20, 200]`.
* For forced escalation by zone complexity, `zone_count_country_ge.threshold` MUST be in `[3, 12]`.

### 5.3 Mixing rate sanity

* `theta_mix` MUST satisfy: `0.10 ≤ theta_mix ≤ 0.70`

  * below 0.10 produces near-toy “almost no escalation”
  * above 0.70 tends to “everything escalates”

### 5.4 No placeholders

* `version` MUST NOT be placeholder-like (`test`, `example`, `todo`, `TBD`, etc.)
* `policy_id` MUST be exactly `zone_mixture_policy_3A`

---

## 6) Deterministic formatting (MUST)

Because the policy bytes are sealed and hashed later:

* Use UTF-8.
* Use LF (`\n`) newlines.
* Use a stable key order in YAML:

  1. `policy_id`
  2. `version`
  3. `theta_mix`
  4. `rules`
* No timestamps, “generated_at”, or machine-specific metadata inside the file.

---

## 7) Recommended v1 production policy (non-toy baseline)

```yaml
policy_id: zone_mixture_policy_3A
version: v1.0.0
theta_mix: 0.35
rules:
  # Guard: too few outlets in-country → monolithic
  - metric: site_count_lt
    threshold: 3
    decision_reason: below_min_sites

  # Guard: country has only one tzid → monolithic
  - metric: zone_count_country_le
    threshold: 1
    decision_reason: forced_monolithic

  # Forced: very multi-zone countries → escalate (once size guard passed)
  - metric: zone_count_country_ge
    threshold: 4
    decision_reason: forced_escalation

  # Forced: very large chains within a country → escalate
  - metric: site_count_ge
    threshold: 40
    decision_reason: forced_escalation
```

S1 behaviour with this policy:

* Apply rules in order; first match decides.
* If no rule matches, apply deterministic hash-mix using `theta_mix`:

  * `u_det < 0.35` ⇒ `default_escalation`
  * else ⇒ `legacy_default`

---

## 8) Acceptance checklist (Codex MUST enforce)

1. YAML parses; no duplicate keys.
2. Validates against `schemas.3A.yaml#/policy/zone_mixture_policy_v1`.
3. `policy_id == "zone_mixture_policy_3A"` and `version` is non-placeholder.
4. `theta_mix` in `[0,1]` and passes realism floor bounds.
5. `rules` present, ≥ 3, includes required metric types (§5.1).
6. Every rule uses an allowed `metric` and allowed `decision_reason`.
7. Threshold sanity bounds pass (§5.2).
8. File is written deterministically (§6).

If any check fails → **FAIL CLOSED** (do not publish; do not seal).

---

## Placeholder resolution (MUST)

- Replace `policy_id`, `version`, and `theta_mix` with final values.
- Populate `rules[]` with the final metrics, thresholds, and decision_reason values.
- Ensure rule ordering is final and no example buckets remain.

