# Acquisition Guide — `mcc_canonical_<vintage>` (Merchant Category Code authority table)

## 0) Purpose and role in the engine

`mcc_canonical_<vintage>` is the engine’s **canonical MCC authority**: a frozen mapping from **4-digit MCC → description (+ optional grouping metadata)**.

Why this matters (in “real” payments terms):

* MCCs are a required/validated field in card-network message flows; Mastercard explicitly treats invalid/obsolete MCCs as rejectable. ([Mastercard][1])
* Visa defines MCC as a 4-digit number describing the merchant’s primary business, and notes some MCCs can identify a specific merchant/type of transaction. 
* ISO 18245 is the international standard that defines MCC code values (but bulk access can be commercial). ([ISO][2])

In your **closed-world** engine, this artefact gives you:

* **Validation**: `transaction_schema_merchant_ids.mcc` is either a known code or triggers a deterministic policy (FAIL / OTHER).
* **Stable feature space**: coefficient packs and priors can be tied to a pinned MCC universe.
* **Future enrichment**: later segments can join on MCC for macro-category priors without bloating ingress.

---

## 1) Engine requirements (what you must freeze)

### 1.1 Artefact identity (MUST)

* **ID:** `mcc_canonical_<vintage>`
* **Version label:** `<vintage>` (recommended: `YYYY-MM-DD`)
* **Format:** Parquet
* **Proposed path template:** `reference/industry/mcc_canonical/<vintage>/mcc_canonical.parquet`
  *(Add to artefact registry + dataset dictionary when you formalise it.)*

### 1.1.1 Contract alignment (MUST)

This MCC authority table is **not yet sealed** in the engine contracts. Before using it as an authoritative input, you MUST:

* add it to the artefact registry (path + schema anchor), and
* add a dataset dictionary entry that matches the path + versioning rules.

Until then, treat this guide as **acquisition-only** (do not claim the engine has sealed it).

### 1.1.2 Placeholder resolution (MUST)

`<vintage>` is the version label for this MCC snapshot. Use a date string in `YYYY-MM-DD` format, and apply it consistently in:

* the artefact ID `mcc_canonical_<vintage>`
* the folder path `reference/industry/mcc_canonical/<vintage>/`
* provenance metadata (`source_vintage` and retrieval date)

Do not mix multiple vintages in a single published parquet.

### 1.2 Minimal schema (MUST)

* `mcc` (int32) **PK**
* `description` (string, non-empty)
* `source_system` (string; e.g., `ISO18245`, `Visa`, `Mastercard`, `Alipay+`, `Mixed`)
* `source_vintage` (string; e.g., `Oct-2025`, `Nov-2025`, `Apr-2024`)
* `mcc_kind` (enum) — **RECOMMENDED**, because real lists mix types:

  * `iso_generic` (normal category codes)
  * `merchant_specific` (e.g., airline/hotel specific codes)
  * `private_use` (scheme/processor/private codes)

*(You can keep only the minimal 2 columns for v1, but you’ll regret it later. The above is still lightweight.)*

### 1.3 Hard constraints (MUST)

* `mcc` unique
* `0 <= mcc <= 9999`
* `description` non-null, non-empty
* If you include `mcc_kind`, it must be one of the allowed values

---

## 2) Source strategy (the “don’t end up with a toy dataset” rule)

You need **two layers**:

### 2.1 Normative anchor (what MCC “is”)

* ISO 18245:2023 defines MCC code values and the maintenance process. ([ISO][2])

**Reality check:** ISO’s bulk lists are often commercial; don’t plan your build around pirated mirrors.

### 2.2 Extractable source (what you can actually download and freeze)

Pick at least one **downloadable/public** source to build the table, then optionally **cross-check** against network manuals.

Recommended extractable sources:

* **Alipay+ “MCC list” page**: includes an ISO-18245 table (“A1: Codes defined by ISO 18245”), plus explicit sections for private-use and “other payment systems” (merchant-specific codes). ([docs.alipayplus.com][3])
* **Checkout.com MCC reference page**: states it uses ISO 18245 MCCs; useful as a secondary cross-check. ([checkout.com][4])
* **Citi “Merchant Category Codes” PDF**: a public, downloadable MCC listing (useful as another cross-check). 

Cross-check (high value, but typically proprietary / rights-reserved):

* **Visa Merchant Data Standards Manual (Oct 2025)** includes a Merchant Category Code listing section and explicitly states it’s © Visa / all rights reserved. 
* **Mastercard Quick Reference Booklet—Merchant Edition (Nov 2025)** is proprietary and states MCC validity requirements; it also references a downloadable “MCC Listing” spreadsheet via the HTML version’s attachments. ([Mastercard][1])

---

## 3) Acquisition routes (decision-free)

### 3.0 Routing policy (MUST; decision-free)

* **Default:** Route A (Alipay+ MCC list).
* **Fallback (ONLY if default fails):** Route B (Citi PDF).
* Failure triggers: download 404/410, file unreadable, or extracted table missing MCC codes/descriptions.
* Vintage policy: set the artefact `version` to the upstream retrieval date (YYYY-MM-DD) and record `raw_bytes_sha256` + `upstream_url` in provenance.

### Route A (recommended): Alipay+ ISO table as the base

**Why:** It’s structured (ISO vs private-use vs other systems), and the site is explicit about MCC usage/updates. ([docs.alipayplus.com][3])

**Steps**

1. Download the MCC list spreadsheet from the Alipay+ MCC list page (or scrape the table if needed). ([docs.alipayplus.com][3])
2. Build your canonical table from **A1 (ISO codes)** only (ISO-only scope).
3. Freeze as `mcc_canonical_<vintage>` and record provenance.

### Route B (fallback): Citi "Merchant Category Codes" PDF listing

**Why:** Public, downloadable MCC table that can be frozen deterministically.

**Steps**

1. Download the Citi MCC PDF.
2. Extract the MCC table into structured rows `(mcc, description)`.
3. Freeze as `mcc_canonical_<vintage>` and record provenance.

### Route C (optional cross-check, internal-only): Visa manual listing

**Steps**

1. Download the Visa manual PDF.
2. Extract the MCC listing section into structured form.
3. Tag codes that are "merchant-specific" where applicable (the Visa text itself notes some MCCs are merchant-specific).
4. Freeze and record provenance.

**Important:** Visa manual is rights-reserved; treat derived datasets as **internal artefacts**, not something you casually publish in an open repo.

### Route D (optional cross-check, internal-only): Mastercard "MCC Listing spreadsheet"

Mastercard’s booklet says there is a downloadable MCC Listing spreadsheet accessible from the **HTML version** via “Download Attachments”. ([Mastercard][5])
If you can retrieve that spreadsheet, it can be an excellent base for your canonical table.

**Important:** Mastercard material is proprietary/rights reserved. ([Mastercard][1])

---

## 4) Canonicalisation rules (Codex implements; this doc specifies)

### 4.1 Parsing rules (MUST)

* Treat MCC as **4-digit codes** but store as `int32`.
* Preserve leading zeros conceptually (e.g., “0742” stored as `742` is fine as long as formatting is handled consistently when rendering).

### 4.2 Scope rule (PINNED for v1; decision-free)

* Scope is **ISO-only**: keep only the “generic” ISO codes (no airline/hotel merchant-specific ranges; no private-use extensions).
* If you later want merchant-specific/private-use codes, create a **separate** artefact (do not silently widen `mcc_canonical_<vintage>`).

### 4.3 De-duplication rule (MUST)

If two sources disagree on `description` for the same `mcc`:

* Choose a single primary source precedence order and document it (e.g., Alipay+ A1 → Visa → Mastercard → Citi → Checkout.com).
* Record the losing description in provenance notes (don’t silently drift).

---

## 5) Engine-fit validation checklist (MUST pass before freezing)

### 5.1 Table integrity

* `mcc` unique
* all `mcc` in `[0..9999]`
* `description` non-empty
* `mcc_kind` (if present) in allowed enum

### 5.2 Coverage vs ingress

**Pinned enforcement (MUST; decision-free):** Strict mode.

* Every `transaction_schema_merchant_ids.mcc` MUST exist in `mcc_canonical_<vintage>` or snapshot build fails.
* No "OTHER=9999" escape hatch in v1 unless you explicitly revise this guide/spec.

---

## 6) Deliverables (what “done” looks like)

1. `reference/industry/mcc_canonical/<vintage>/mcc_canonical.parquet`
2. Provenance sidecar containing:

   * source URLs + access date/time
   * source document versions (e.g., “Visa Oct 2025”, “Mastercard Nov 2025”, “Alipay+ Apr 2024 release”)
   * scope choice (ISO-only vs extended)
   * any precedence rules used for conflicts
   * checksums (raw + output)

---

## 7) Working links (copy/paste)

```text
# ISO normative anchor (standard pages)
https://www.iso.org/standard/79450.html            # ISO 18245:2023
https://www.iso.org/standard/33365.html            # ISO 18245:2003 (older)

# Recommended downloadable/public base source
https://docs.alipayplus.com/alipayplus/alipayplus/mcc-standards/mcc-lists

# Secondary cross-check sources (public pages)
https://www.checkout.com/docs/developer-resources/codes/merchant-category-codes
https://www.citibank.com/tts/solutions/commercial-cards/assets/docs/govt/Merchant-Category-Codes.pdf

# Network manuals (high value, but proprietary / rights-reserved)
https://usa.visa.com/content/dam/VCOM/download/merchants/visa-merchant-data-standards-manual.pdf
https://www.mastercard.com/content/dam/mccom/shared/business/support/rules-pdfs/mastercard-quick-reference-booklet-merchant.pdf
```

---

If you want the cleanest flow: use Route A (Alipay+ A1 ISO table) as the canonical base, treat Visa/Mastercard as cross-checks only, then validate the merchant universe deterministically via `transaction_schema_merchant_ids`.

[1]: https://www.mastercard.com/content/dam/mccom/shared/business/support/rules-pdfs/mastercard-quick-reference-booklet-merchant.pdf "Quick Reference Booklet"
[2]: https://www.iso.org/standard/79450.html "ISO 18245:2023 - Merchant category codes"
[3]: https://docs.alipayplus.com/alipayplus/alipayplus/mcc-standards/mcc-lists "MCC list | Alipay+ MCC Standards | Alipay+ Docs"
[4]: https://www.checkout.com/docs/developer-resources/codes/merchant-category-codes "Merchant category codes - Docs"
[5]: https://www.mastercard.us/content/dam/public/mastercardcom/na/global-site/documents/quick-reference-booklet-merchant.pdf "Quick Reference Booklet"
