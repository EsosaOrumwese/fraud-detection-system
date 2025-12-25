# Authoring Guide — `tz_overrides` (2A Civil Time override registry)

This file is a **governed policy list** that 2A seals in **S0** and applies in **S2** to turn S1’s `tzid_provisional` into the final `tzid` for each site.

It exists for **rare, explicit corrections** (border ambiguity, known polygon mistakes, programme-specific “pinning”), not as a second timezone system.

---

## 1) File identity (binding)

* **Policy id:** `tz_overrides`
* **Path:** `config/timezone/tz_overrides.yaml`
* **Schema authority:** `schemas.2A.yaml#/policy/tz_overrides_v1`
* **Sealed input:** yes (2A.S0 records digest + version tag; bytes changing ⇒ new lineage)

**Empty file is allowed** (an empty list means “no overrides”; S2 passes through polygon results).

---

## 2) What the policy does (binding)

For each site, S2 forms candidate overrides and chooses **at most one** using:

* **precedence:** `site » mcc » country`
* **active rule:** an override is **active** iff `expiry_yyyy_mm_dd` is null **or** `expiry_yyyy_mm_dd ≥ date(S0.receipt.verified_at_utc)`
  (no wall-clock dependence; the cut-off date is the S0 receipt date)

If no override applies, the final tzid is the polygon tzid from S1.

---

## 3) Record shape (binding)

Each list element is an object:

* `scope`: one of `site | mcc | country`
* `target`: a string (scope-dependent encoding; see §4)
* `tzid`: IANA tzid (must satisfy the layer’s `iana_tzid` domain)
* optional:

  * `evidence_url`: string (recommended)
  * `expiry_yyyy_mm_dd`: `YYYY-MM-DD` or null
  * `notes`: string or null

**Duplicate keys inside a record are forbidden** (fail closed).

---

## 4) Target encoding by scope (binding, so Codex can’t “guess”)

Even though the schema types `target` as a string, **S2 matching depends on a precise encoding**. Author this file using these canonical encodings:

### 4.1 `scope: country`

* `target` MUST be ISO-3166-1 alpha-2 uppercase:
  **pattern:** `^[A-Z]{2}$`
  Example: `GB`, `NG`, `US`

### 4.2 `scope: mcc`

* `target` MUST be a **4-digit MCC code**, zero-padded:
  **pattern:** `^[0-9]{4}$`
  Example: `6011`, `7995`, `0000`

**Important:** MCC-scope overrides are only usable if the programme seals an authoritative `merchant_id → mcc` mapping in 2A.S0. If not sealed, MCC-scope overrides must be treated as **inactive** (and any attempt to apply them must abort).

### 4.3 `scope: site`

* `target` MUST encode the site key `(merchant_id, legal_country_iso, site_order)` as:
  **`"<merchant_id>|<ISO2>|<site_order>"`**

Constraints:

* `merchant_id` is base-10 uint64, no leading zeros: `[1-9][0-9]{0,19}`
* `ISO2` uppercase: `[A-Z]{2}`
* `site_order` base-10 integer ≥1, no leading zeros: `[1-9][0-9]*`

**pattern:** `^[1-9][0-9]{0,19}\|[A-Z]{2}\|[1-9][0-9]*$`
Example: `42|GB|3`

This makes the override target stable across seeds (site identity is key-based, not coordinate-based).

---

## 5) Duplicate and expiry rules (binding)

* For any given cut-off date (S0 receipt date), there must be **at most one active row per `(scope, target)`**.

  * You MAY keep older historical rows with the same `(scope,target)` if they are expired such that they’re not active for the run’s cut-off date.
  * If two rows for the same `(scope,target)` would both be active → **S2 must abort**.

---

## 6) Minimal v1 file (Codex can write verbatim)

```yaml
# tz_overrides (2A) — governed override list
# Empty list means: no overrides; S2 passes through polygon tzids.

[]
```

---

## 7) Example file (small, realistic)

```yaml
- scope: country
  target: "EG"
  tzid: "Africa/Cairo"
  evidence_url: "https://example.org/decision-note"
  expiry_yyyy_mm_dd: null
  notes: "Programme pin for legacy reporting consistency."

- scope: mcc
  target: "6011"
  tzid: "Europe/London"
  expiry_yyyy_mm_dd: "2026-12-31"
  notes: "Temporary pin for MCC 6011 where polygon border noise causes flips."

- scope: site
  target: "42|GB|3"
  tzid: "Europe/London"
  expiry_yyyy_mm_dd: null
  notes: "Known border jitter: force stable tzid for this site key."
```

---

## 8) Acceptance checklist (Codex must enforce)

1. YAML parses with **no duplicate keys**.
2. Top-level is a **list** (array), not an object.
3. Every row validates to the schema: required `scope,target,tzid`; optional fields well-typed.
4. `scope`-specific `target` patterns enforced exactly as §4.
5. No `(scope,target)` has **multiple active rows** at the run’s cut-off date (S0 receipt date).
6. Every `tzid` is:

   * valid IANA tzid domain, **and**
   * present in the sealed `tz_world` tzid domain for the release used by the run (otherwise 2A.S2 will abort).
7. If any `scope: mcc` rows exist and are intended to be active, ensure the programme seals `merchant_id → mcc` mapping in S0; otherwise treat MCC overrides as unusable for that run.

---

If you want, next we can do `tz_nudge` right after this (it’s simpler: semver + epsilon + digest, and it’s applied only for deterministic border tie-breaks in S1).
