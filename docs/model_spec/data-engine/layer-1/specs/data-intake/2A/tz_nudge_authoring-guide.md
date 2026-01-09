# Authoring Guide — `tz_nudge` (2A.S1 deterministic border ε)

`tz_nudge` is a tiny, **sealed** policy file that exists for exactly one reason:

When 2A.S1 does point-in-polygon and gets a **non-unique** result (border / overlap / precision weirdness), it applies **one deterministic ε-nudge** to the site coordinate to force a single membership — or **fails closed** if that still doesn’t resolve.

---

## 1) File identity (binding)

* **Artefact id:** `tz_nudge`
* **Path:** `config/layer1/2A/timezone/tz_nudge.yml`
* **Schema authority:** `schemas.2A.yaml#/policy/tz_nudge_v1`
* **Sealed in:** `2A.S0` (bytes change ⇒ new lineage / new `manifest_fingerprint`)

---

## 2) Behavioural meaning (binding)

### 2.1 When S1 uses it

S1 applies ε-nudge **only** if the initial membership test returns **cardinality ≠ 1** (ambiguous or empty).

### 2.2 Exactly what S1 does with ε

Given `(lat, lon)` and `ε = epsilon_degrees`:

* Compute nudged coordinate:
  `lat' = lat + ε`
  `lon' = lon + ε`

* Then constrain deterministically:

  * **latitude:** clamp to `[-90, +90]`
  * **longitude:** wrap into `(-180, +180]` using this exact rule:
    - let `x = lon' + 180`
    - let `r = x - 360 * floor(x / 360)`   (so r ∈ [0, 360))
    - let `lon_wrapped = r - 180`          (so lon_wrapped ∈ [-180, 180))
    - if `lon_wrapped == -180`, set `lon_wrapped = +180` (to make the range (-180, 180])

* Re-evaluate membership once using `(lat', lon')`.

Rules:

* **At most one nudge per site**.
* If membership is still **ambiguous or empty** after this single nudge → **ABORT** (fail closed).
* If a nudge was used, S1 MUST record `nudge_lat_deg = lat'` and `nudge_lon_deg = lon'`; otherwise both are null.

---

## 3) Required keys (MUST)

Top-level object with **exactly** these keys (no extras; reject unknown keys; reject duplicate keys):

* `semver : string`
* `epsilon_degrees : number` (MUST be `> 0.0`)
* `sha256_digest : hex64` (lowercase 64-char hex)

---

## 4) Choosing `epsilon_degrees` (guidance)

This ε is a **tie-break** constant, not a “move the point to a new place” constant.

Recommendations:

* Prefer **very small** values (e.g. `0.000001` degrees) so you only break ties near borders.
* Don’t change ε casually: changing it can flip borderline sites and will change downstream civil-time artefacts.

Hard rule:

* `epsilon_degrees` MUST be strictly greater than 0.0 (0 is invalid because it can’t resolve ties).

---

## 5) `sha256_digest` definition (binding, so Codex can compute it)

`sha256_digest` MUST be computed from the **effective payload** (not file bytes), using this exact UTF-8 material:

```
semver=<semver>
epsilon_degrees=<epsilon_string>
```

### 5.1 Placeholder resolution (MUST)

Where:

* `<semver>` is the literal `semver` value.
* `<epsilon_string>` is the decimal representation you write in the YAML for `epsilon_degrees` and MUST be:

  * fixed-point decimal (no exponent)
  * at least one digit before the decimal point
  * at least one digit after the decimal point

Then:

* `sha256_digest = SHA256( UTF8(material + "\n") )` as lowercase hex.

This makes the digest stable and independent of YAML formatting/whitespace.

---

## 6) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
semver: v1.0.0-alpha
epsilon_degrees: 0.000001
sha256_digest: cf4ea77c4a0f07b1c291e460529a64724655a0494fbc4989c17d98408c64f8ff
```

(That digest is the SHA-256 of the exact material:
`semver=v1.0.0-alpha\nepsilon_degrees=0.000001\n`.)

---

## 7) Acceptance checklist (Codex MUST enforce)

1. YAML parses; **no duplicate keys**.
2. Top-level is an **object**, not a list.
3. Keys are **exactly** `{semver, epsilon_degrees, sha256_digest}`.
4. `epsilon_degrees` is a number and **> 0.0**.
5. `sha256_digest` is hex64 and **matches** the digest computed by §5.
6. File is sealed by 2A.S0; if bytes change, S0 must treat it as a policy change (new lineage).

## Non-toy/realism guardrails (MUST)

- Nudges must be sparse and targeted; no global shifts.
- Offsets must be small (minutes/hours), not whole-timezone jumps, unless explicitly justified.
- All `tzid` values must be valid in the pinned tzdb release; conflicts fail closed.

