# Authoring / Derivation Guide — `cdn_key_digest.yaml` (3B CDN key digest, v1)

## 0) Purpose

`cdn_key_digest.yaml` is a **sealed, token-less** “key material” artefact that provides a **semantic digest** for the CDN mix used by 3B.

It serves two purposes:

1. **Provenance bridge:** 3B.S4 writes `cdn_key_digest` into `virtual_routing_policy_3B` so downstream readers can confirm they’re using the same CDN mix **without** needing access to 3B’s sealed-input inventory.

2. **Optional key material:** the digest may be used as stable key material for deriving stream IDs / keys for virtual edge selection (as referenced by 3B.S0), but the digest itself is **not** the file’s sha; it is a semantic digest of the CDN mix policy.

This file is **small**, but must be **non-toy** by being derived from the full production CDN mix (hundreds of countries), not a stub list.

---

## 1) File identity (MUST)

* **Artefact ID:** `cdn_key_digest`
* **Path:** `config/virtual/cdn_key_digest.yaml`
* **Token-less posture:** do **not** embed the file’s SHA-256 inside the file (that digest is tracked by 3B.S0 sealing inventory).
  The field named `cdn_key_digest` below is **semantic key material**, not a file digest.

---

## 2) Required file shape (pinned by this guide)

Top-level YAML object with **exactly** these keys (no extras):

* `version` : string (non-placeholder governance tag, e.g. `v1.0.0`)
* `source_policy_id` : string (MUST be `cdn_country_weights`)
* `source_policy_version` : string (copied from `cdn_country_weights.yaml.version`)
* `edge_scale` : integer (copied from `cdn_country_weights.yaml.edge_scale`)
* `cdn_key_digest` : hex64 lowercase (computed by §4)

> Why include `edge_scale`? Because it is part of the CDN mix semantics that affect the resulting virtual fabric.

**Key order (MUST):**

1. `version`
2. `source_policy_id`
3. `source_policy_version`
4. `edge_scale`
5. `cdn_key_digest`

---

## 3) Inputs (MUST exist; fail closed)

Codex MUST have:

* `config/virtual/cdn_country_weights.yaml` (authored by the `cdn_country_weights` guide)

If missing → **FAIL CLOSED**.

---

## 4) Pinned semantic digest law (MUST; decision-free)

This digest MUST be computed from the **semantic content** of `cdn_country_weights.yaml`, not from its raw bytes (so formatting/whitespace changes don’t change the key).

### 4.1 Parse + validate the source policy (MUST)

Codex MUST parse `cdn_country_weights.yaml` and enforce these invariants before digesting:

* `version` present (non-placeholder)
* `edge_scale` integer and `200 ≤ edge_scale ≤ 2000`
* `countries` list:

  * `len(countries) ≥ 200`
  * every `country_iso` matches `^[A-Z]{2}$`
  * every `weight > 0`
  * all `country_iso` unique
  * `abs(sum(weight) - 1.0) ≤ 1e-12`

If any fail → **FAIL CLOSED** (do not emit `cdn_key_digest.yaml`).

### 4.2 Canonical message bytes (MUST)

Construct UTF-8 bytes exactly as:

**Header lines:**

* `policy_id=cdn_country_weights\n`
* `policy_version=<source_version>\n`
* `edge_scale=<edge_scale>\n`

**Then one line per country, sorted by `country_iso` ascending:**

* `country=<ISO2>|weight=<W>\n`

Where `<W>` is the weight formatted deterministically as:

* fixed-point decimal
* exactly **12 digits after the decimal point**
* no exponent notation
  Example: `0.045612398771`

### 4.3 Digest computation (MUST)

* `cdn_key_digest = SHA256(canonical_bytes)` as lowercase hex64.

---

## 5) Emission (MUST)

Write `config/virtual/cdn_key_digest.yaml` as UTF-8, LF newlines, with the pinned key order (§2), e.g.:

```yaml
version: v1.0.0
source_policy_id: cdn_country_weights
source_policy_version: v1.0.0
edge_scale: 500
cdn_key_digest: <computed_hex64_lower>
```

No timestamps. No “generated_at”.

---

## 6) Realism safeguards (MUST; prevents toy key material)

Codex MUST fail closed if the source CDN mix is toy-like:

* `len(countries) < 200` → abort
* heavy-tail sanity on the source policy:

  * top 5 countries by weight carry **≥ 25%** OR top 10 carry **≥ 40%**
  * if neither true → abort
* `edge_scale < 200` → abort

(These are deliberately aligned with the CDN mix guide so the key digest can’t be generated from a stub.)

---

## 7) Acceptance checklist (Codex MUST enforce)

1. Source file exists and passes §4.1 validation.
2. Canonical bytes constructed exactly per §4.2 (sorting + fixed-point formatting).
3. `cdn_key_digest` computed per §4.3 (hex64 lowercase).
4. Output YAML matches shape in §2 (no extra keys).
5. Recompute digest from the sealed `cdn_country_weights.yaml` semantic content and confirm it matches the emitted `cdn_key_digest`.
6. Deterministic formatting rules satisfied (UTF-8, LF, key order).

If any check fails → **FAIL CLOSED**.

## Placeholder resolution (MUST)

* Replace all placeholder values (e.g., "TODO", "TBD", "example") before sealing.
* Remove or rewrite any "stub" sections so the guide is decision-free for implementers.
