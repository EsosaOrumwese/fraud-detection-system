## Authoring Guide — `licenses/license_map.yaml` (+ `LICENSES/` folder)

### 0) Purpose (Binding)

This artefact provides the **single authoritative mapping** from:

* the license string used in your **artefact registries / dataset dictionaries** (e.g., `ODbL-1.0`, `CC-BY-4.0`, `Public-Domain`, `Proprietary-Internal`)
  to:
* a **canonical SPDX-ish identifier** (when applicable),
* an **attribution template**,
* and a pointer to a **local license text file** under `LICENSES/`.

This prevents “license drift” and gives Codex a deterministic way to:

* validate license fields,
* materialise attribution bundles,
* and ensure the repo always contains the referenced license texts.

---

## 1) Identity & location (Binding)

* **Path:** `licenses/license_map.yaml`
* **Folder:** `LICENSES/` (sibling of `licenses/`)
* **Lineage:** bytes must be treated as governance input (if you hash governance bundles)

---

## 2) Required top-level structure (Binding)

Top-level keys MUST be exactly:

* `semver` (string)
* `version` (string; `YYYY-MM-DD`)
* `licenses` (map)

Reject unknown keys and duplicate keys.

---

## 3) License entry shape (Binding)

Each entry `licenses.<license_key>` MUST be:

```yaml
spdx: <string|null>
osi_approved: <bool|null>
redistribution: "open" | "restricted" | "internal"
notice_required: <bool>
sharealike: <bool>
source_disclosure: <bool>
text_path: <string>          # must point into LICENSES/
attribution_template: <string|null>
notes: <string|null>
```

Rules:

* `text_path` MUST exist in repo (Codex must create it if missing).
* `redistribution` governs whether artefacts under that license can be published to public repos.
* `attribution_template` is a short template (not a long text; keep it under ~10 lines).

---

## 4) Minimal set of license keys you must support (Binding for your current engine)

Based on the datasets you’ve pinned so far, you need at least:

* `ODbL-1.0`
* `CC-BY-4.0`
* `Public-Domain`
* `Proprietary-Internal`

(You can add more later.)

---

## 5) `LICENSES/` folder convention (Binding)

* Store license texts as plaintext `.txt` (or `.md`) under `LICENSES/`.
* Filenames must match the `text_path` entries exactly.
* For standard licenses:

  * ODbL-1.0 → include the full license text (Open Data Commons ODbL v1.0)
  * CC-BY-4.0 → include the full legal code (Creative Commons Attribution 4.0 International)
* For Public Domain:

  * include a short note file describing “Public domain / no known restrictions” and the source policy
* For Proprietary-Internal:

  * include an internal notice describing redistribution restrictions

---

## 6) Minimal v1 `license_map.yaml` (Codex can author verbatim)

```yaml
semver: "1.0.0"
version: "2024-12-31"

licenses:
  ODbL-1.0:
    spdx: "ODbL-1.0"
    osi_approved: null
    redistribution: "open"
    notice_required: true
    sharealike: true
    source_disclosure: true
    text_path: "LICENSES/ODbL-1.0.txt"
    attribution_template: |
      License: ODbL 1.0 (Open Data Commons Open Database License).
      You MUST retain attribution and share-alike terms for derivative databases.
      See LICENSES/ODbL-1.0.txt.
    notes: "Use for databases derived from OpenStreetMap / ODbL sources."

  CC-BY-4.0:
    spdx: "CC-BY-4.0"
    osi_approved: null
    redistribution: "open"
    notice_required: true
    sharealike: false
    source_disclosure: false
    text_path: "LICENSES/CC-BY-4.0.txt"
    attribution_template: |
      License: CC BY 4.0.
      You MUST provide attribution to the original source.
      See LICENSES/CC-BY-4.0.txt.
    notes: null

  Public-Domain:
    spdx: null
    osi_approved: null
    redistribution: "open"
    notice_required: false
    sharealike: false
    source_disclosure: false
    text_path: "LICENSES/Public-Domain.txt"
    attribution_template: |
      Public domain / no known restrictions.
      Source attribution is recommended as a best practice.
      See LICENSES/Public-Domain.txt.
    notes: "Used for Natural Earth (public domain) and similar sources."

  Proprietary-Internal:
    spdx: null
    osi_approved: null
    redistribution: "internal"
    notice_required: true
    sharealike: false
    source_disclosure: false
    text_path: "LICENSES/Proprietary-Internal.txt"
    attribution_template: |
      Proprietary / Internal use only.
      Redistribution outside the project is not permitted.
      See LICENSES/Proprietary-Internal.txt.
    notes: "Used for engine-generated or internally authored artefacts."
```

---

## 7) Required `LICENSES/` files (Codex must create)

Codex must ensure these files exist:

* `LICENSES/ODbL-1.0.txt`
* `LICENSES/CC-BY-4.0.txt`
* `LICENSES/Public-Domain.txt`
* `LICENSES/Proprietary-Internal.txt`

**Important:** the full legal texts for ODbL and CC-BY are copyrighted legal documents, but they are meant to be redistributed as license texts. Still, Codex should source them from the official publishers (ODC / Creative Commons) and store them verbatim.

---

## 8) Acceptance checklist (Codex must enforce)

* `licenses/license_map.yaml` parses, no unknown top-level keys
* every `text_path` exists in repo
* every license key used anywhere in artefact registries / dataset dictionaries is present in this map
* no license key is “invented” outside this map (fail closed)

---