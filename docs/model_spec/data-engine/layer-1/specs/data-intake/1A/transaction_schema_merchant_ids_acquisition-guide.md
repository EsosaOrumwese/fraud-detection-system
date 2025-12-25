# Acquisition Guide — `transaction_schema_merchant_ids` (Ingress merchant universe snapshot)

## 0) Purpose and role in the engine

`transaction_schema_merchant_ids` is the **authoritative merchant-universe snapshot** that **Segment 1A** consumes at **S0.1** to freeze:

* the set of merchants `𝓜`
* the per-merchant categorical tokens used throughout 1A (`mcc`, `channel`, `home_country_iso`)

This dataset is a **processed, column-normalised snapshot** (not a raw export). The engine assumes it is **already cleaned and made deterministic** before 1A starts.

---

## 1) Engine requirements (what you must deliver)

### 1.1 Dataset identity (MUST)

* **ID:** `transaction_schema_merchant_ids`
* **Format:** Parquet
* **Path template:** `reference/layer1/transaction_schema_merchant_ids/{version}/`
* **Partitioning:** `[version]` (the `{version}` directory key is the partition)
* **PII:** `false` (do not include names/addresses/real-world identifiers)
* **License:** Proprietary-Internal

### 1.2 Schema (MUST match `schemas.ingress.layer1.yaml#/merchant_ids`)

Columns (exactly these for v1 of the engine):

* `merchant_id` (int64, NOT NULL, **minimum 1**) — **PK**
* `mcc` (int32, NOT NULL)
* `channel` (string, NOT NULL, enum: `card_present | card_not_present`)
* `home_country_iso` (string, NOT NULL, ISO2 uppercase)

### 1.3 Domain constraints (MUST)

* `merchant_id` is unique
* `mcc ∈ [0, 9999]` (hard fail if outside)
* `channel ∈ {"card_present","card_not_present"}` (hard fail if anything else)
* `home_country_iso` MUST be in `iso3166_canonical_2024.country_iso` (FK; hard fail if not)

### 1.4 “Engine contract” consequences (MUST keep in mind)

* If `transaction_schema_merchant_ids` violates schema/domains, **1A aborts at S0.1** (no RNG, no parameter/fingerprint artefacts).
* Therefore: **all cleaning, deduping, and conflict resolution happens upstream of the engine.**

---

## 2) Ownership boundary (who builds it)

This dataset is best treated as an **Ingress Authoring artefact** owned by the **Control & Ingress plane** (or a dedicated “Universe Builder”), not by 1A.

### 2.1 Binding bootstrap config (Route B authority)

When using Route B (closed-world authored ingress), Codex MUST NOT “implement the guide” by inventing defaults.
Instead, Route B MUST be driven by a **governed bootstrap config artefact**:

* **Config path (binding):** `config/ingress/transaction_schema_merchant_ids.bootstrap.yaml`
* **Role:** pins scale + distributions + correlations + determinism seed rules for authoring the merchant universe
* **Rule:** if this config file is missing or fails schema validation → FAIL CLOSED (do not guess).

* The **Scenario Runner selects** which `{version}` (and other reference artefact versions) are pinned inside the chosen `manifest_fingerprint`.
* The **engine consumes** the pinned snapshot as read-only authority.

---

## 3) Acquisition / authoring routes (decision-free)

### 3.0 Routing policy (MUST; decision-free)

* **Default:** Route B (closed-world authored ingress) so Codex can run without depending on an external merchant master.
* Route A is permitted only if you explicitly provide an upstream merchant master/transaction schema dataset (out of scope for this guide).

### Route A - Derive from a "transaction schema" or merchant master (most literal)

Use this if you already have an upstream dataset that represents “merchant identity + attributes” (even if synthetic), or a merchant master table.

**Inputs (typical)**

* A table with a stable merchant key, plus some form of MCC/category, channel indicator, and country.

**What you do**

* Extract the merchant universe (unique merchants).
* Normalise columns to the exact schema and domain constraints.
* Produce the `{version}` snapshot.

This is the cleanest route if you already have a controlled upstream “transaction schema” dataset.

### Route B — Closed-world authoring (recommended for your project goal)

Use this if you do **not** have (or do not want) any real merchant feed.

You explicitly **author** the merchant universe as a governed input, using the binding bootstrap config in §2.1.

#### Realism bar (SHOULD, to avoid "toy" universes)

* MUST be **non-degenerate**: >1 distinct `home_country_iso`, >1 distinct `channel`, and a meaningful spread of `mcc` values (not a handful).
* SHOULD be **skewed** (not uniform): home countries and MCCs should follow long-tailed / Zipf-like frequency, reflecting real commerce concentration.
* SHOULD include **correlations**: e.g., channel mix varies by MCC (online-heavy vs in-person-heavy categories).
* SHOULD include **coverage** beyond "top countries only" so cross-border logic has realistic candidate sets.

**Binding rule (MUST; decision-free):**

* Read `config/ingress/transaction_schema_merchant_ids.bootstrap.yaml` and apply its pinned policy exactly:
  * merchant count `N`
  * deterministic seed derivation
  * `home_country_iso` weighting/spine constraints
  * `mcc` weighting from `mcc_canonical_<vintage>`
  * `channel` conditional rules by MCC (correlation)
* Emit `reference/layer1/transaction_schema_merchant_ids/{version}/` as the pinned universe.

This matches the “closed-world” goal: **the world is what you say it is**, and the runner chooses which world exists today.

---

## 4) Normalisation & conflict rules (Codex implements; this doc specifies)

Even if your upstream source is clean, you MUST specify deterministic rules for the common failure modes.

### 4.1 Merchant identifier policy (MUST)

You must end with `merchant_id: int64`.

Acceptable policies:

* **Synthetic-sequential:** `merchant_id = 1..N` (recommended for Route B)
* **Deterministic remap from upstream key:** build a stable mapping from upstream merchant key → int64, and freeze that mapping for the snapshot.

Rules:

* No gaps requirement is implied, but **minimum is 1**, and **uniqueness is mandatory**.
* The remap MUST be stable for the `{version}` snapshot.

### 4.2 MCC policy (MUST)

* MCC must be an int in `[0,9999]`.
* SHOULD validate MCC membership against your pinned `mcc_canonical_<vintage>` table (recommended for realism + governance).
* If upstream provides MCC as string, you must parse and validate deterministically.
* If upstream MCC is missing/invalid: drop that merchant from the snapshot (MUST; decision-free).

Do **not** silently coerce/clip MCC values.

### 4.3 Channel mapping policy (MUST)

Engine only accepts:

* `card_present`
* `card_not_present`

If upstream has richer categories (POS entry mode, ecommerce flags, wallet, etc.), you MUST define a deterministic mapping table to these two values.

If you cannot map a value deterministically, snapshot build MUST fail (or that merchant must be dropped under a documented rule).

### 4.4 Home country policy (MUST)

* `home_country_iso` MUST be ISO2 uppercase and must FK into `iso3166_canonical_2024`.

If upstream has ISO3/numeric/country names:

* you MUST convert deterministically (using your canonical ISO artefact as authority).

If country is missing/unknown:

* drop the merchant from the snapshot (MUST; decision-free). Do not hardcode defaults.

### 4.5 Duplicate / conflicting records (MUST)

If the upstream source contains multiple records for the “same merchant” with conflicting attributes (common when deriving from transaction logs), you MUST define a deterministic resolution policy, e.g.:

* pick the value with highest supporting count (mode by obs_count),
* if tie, pick lexicographically smallest (for strings) / numerically smallest (for ints),
* if still tied, pick by earliest/lowest upstream key.

Whatever you choose: **document it and keep it stable**.

---

## 5) Versioning (how to pick `{version}`)

Because this dataset is pinned into a `manifest_fingerprint`, `{version}` must be meaningful and reproducible.

Recommended `{version}` forms:

* `YYYY-MM-DD` (snapshot date, UTC)
* `YYYYQn` (quarterly snapshot)
* `vN` (only if you also retain an external provenance record)

MUST record alongside the snapshot:

* what upstream inputs were used (IDs/paths)
* the build timestamp
* deterministic ruleset version (so you can rebuild the same output)

---

## 6) Engine-fit validation checklist (must pass before you pin it)

### 6.1 Schema + domain checks (MUST)

* Columns exactly: `merchant_id, mcc, channel, home_country_iso`
* `merchant_id` int64, NOT NULL, min 1, unique
* `mcc` int32, NOT NULL, `0 ≤ mcc ≤ 9999`
* `channel` in `{card_present, card_not_present}` only
* `home_country_iso` matches `^[A-Z]{2}$` and is present in `iso3166_canonical_2024`

### 6.2 Coverage sanity (SHOULD)

* Merchant count matches your intended world scale for the scenario(s).
* `home_country_iso` distribution is compatible with your other pinned references (GDP + share surfaces), otherwise 1A will abort later due to missing joins.

### 6.3 “No PII” check (MUST)

* No merchant names, addresses, tax IDs, URLs, phone numbers, or anything that can be traced back to a real entity.

---

## 7) Deliverables (what “done” looks like)

1. Parquet dataset at:

   * `reference/layer1/transaction_schema_merchant_ids/{version}/`
     containing the normalised table.

2. A provenance sidecar stored next to it (json/yaml is fine) containing:

   * `{version}`
   * upstream source identifiers (or “closed-world authored”)
   * **bootstrap config reference (Route B):**
     * config path: `config/ingress/transaction_schema_merchant_ids.bootstrap.yaml`
     * sha256 of the config bytes actually used
     * config `version`/`semver` fields (if present)
   * rule-set identifier (channel mapping, conflict resolution policy)
   * counts (rows in/out, dropped merchants if any)
   * checksum(s) for the final parquet

---

## 8) MCC enrichment note (important for later segments)

Do **not** bloat `transaction_schema_merchant_ids` with MCC descriptions, groups, or priors.

If/when you need MCC semantics later, introduce separate governed artefacts:

* `mcc_canonical_<vintage>` (allowed codes + names)
* `mcc_enrichment_<vintage>` (groupings, priors, risk baselines, etc.)

That keeps the ingress universe stable while realism policies evolve cleanly.

---
