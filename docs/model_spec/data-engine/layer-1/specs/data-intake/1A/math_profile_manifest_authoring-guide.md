# Authoring Guide — `math_profile_manifest.json`

## 1) What this file is for

`math_profile_manifest.json` is the **sealed declaration of the deterministic `libm` profile** the engine is allowed to use on any decision/order-critical path. It exists so a run can say:

* **which math implementation** was used (vendor + version),
* **which functions** are in scope,
* **which exact built artifacts** were used (by sha256),
* and a single **profile checksum** tying it all together.

This file lives at:

* `reference/governance/math_profile/{version}/math_profile_manifest.json`

and is treated as an **opened artefact** in the `manifest_fingerprint` (byte changes must change lineage).

---

## 2) Pinned v1 strategy (so Codex never needs to ask)

For v1, pin:

* **vendor:** `JuliaMath/openlibm`
* **vendor_version:** `v0.8.7`
* **math_profile_id:** `openlibm-v0.8.7`
* **path_version:** `openlibm-v0.8.7` (recommended: keep directory name equal to `math_profile_id`)
* **functions (sorted):**
  `atan2, cos, exp, expm1, erfinv, lgamma, log, log1p, pow, sin, sqrt, tanh`

This is the *minimum decision-critical set* you’ve already referenced in 1A logic; expand later only when a segment actually calls more functions.

---

## 3) Required JSON shape (what Codex must write)

The schema minimum is:

* `math_profile_id` (string)
* `vendor` (string)
* `version` (string)
* `functions` (array of strings)
* `checksum` (optional by schema, but **REQUIRED by this guide**)

This guide also requires an `artifacts` list so the profile pins real bytes.

### 3.1 Artifact naming (PINNED)

To avoid Codex inventing names, pin the artifact names exactly:

* `openlibm-v0.8.7.tar.gz`  *(the downloaded source archive bytes)*
* `libopenlibm.so`          *(the built library used by the engine)*

If you choose static instead of shared later, add it as a third artifact (don’t rename these two).

---

## 4) Deterministic build and hashing rules (Codex “fill-in contract”)

### 4.1 Build constraints (MUST)

Codex must build OpenLibm under a pinned toolchain that respects your numeric regime:

* no fast-math
* no FMA contraction
* stable target (container recommended)
* stable flags recorded into the manifest `build` string

### 4.2 Artifact digests (MUST)

**Archive bytes rule (MUST):** treat upstream URLs as *untrusted* for checksum stability. Always hash and store the **exact bytes you downloaded** as `openlibm-v0.8.7.tar.gz`, and never assume the same URL will yield identical bytes in the future.

Codex must compute sha256 for:

* the **exact downloaded source archive bytes**
* the **exact built library bytes**

### 4.3 Manifest checksum (MUST)

`checksum` must be:

* `sha256( canonical_json( { math_profile_id, vendor, version, functions, artifacts } ) )`

Where:

* `functions` is lexicographically sorted
* `artifacts` is a list of `{name, sha256}` sorted by `name` ascending
* `canonical_json` is deterministic (recommended: RFC 8785 JSON Canonicalization Scheme; if not, enforce stable key order + no whitespace variance inside canonicalization input)

---

## 5) Final file template (Codex fills sha256 + build)

Codex can write this file as the final output after building + hashing:

```json
{
  "math_profile_id": "openlibm-v0.8.7",
  "vendor": "JuliaMath/openlibm",
  "version": "v0.8.7",
  "build": "<stable_toolchain_id_and_flags>",
  "functions": [
    "atan2",
    "cos",
    "exp",
    "expm1",
    "erfinv",
    "lgamma",
    "log",
    "log1p",
    "pow",
    "sin",
    "sqrt",
    "tanh"
  ],
  "artifacts": [
    { "name": "libopenlibm.so", "sha256": "<64-hex>" },
    { "name": "openlibm-v0.8.7.tar.gz", "sha256": "<64-hex>" }
  ],
  "checksum": "<64-hex>"
}
```

---

## 6) Acceptance checklist (Codex must enforce before sealing)

* File path matches: `reference/governance/math_profile/{version}/math_profile_manifest.json`
* `math_profile_id/vendor/version` match the pinned v1 strategy
* `functions` is sorted; no duplicates
* `artifacts` contains **exactly** the two pinned names above (for v1) and each `sha256` is 64-hex
* `checksum` is 64-hex and equals the checksum rule in §4.3
* No placeholder strings remain (`<...>`)
* A basic libm regression/self-test was executed under the same toolchain (recorded in CI logs or provenance) before sealing, to avoid silently pinning a broken build.

---

## 7) Working links (copy/paste)

```text
# Repo
https://github.com/JuliaMath/openlibm

# Releases (tag v0.8.7 is here)
https://github.com/JuliaMath/openlibm/releases

# Tag page
https://github.com/JuliaMath/openlibm/releases/tag/v0.8.7

# Source archive (preferred tar.gz for the tag)
https://github.com/JuliaMath/openlibm/archive/refs/tags/v0.8.7.tar.gz
https://github.com/JuliaMath/openlibm/archive/refs/tags/v0.8.7.zip
```

## Non-toy/realism guardrails (MUST)

- `functions` MUST include every libm call used by the engine and MUST NOT include extras without a spec change.
- `artifacts` MUST point to real bytes built from the pinned source archive; verify sha256 from actual files.
- `build` MUST record a toolchain that enforces the numeric policy (no fast-math, FMA off).
- `checksum` MUST be recomputed from canonical JSON and match the manifest; mismatch => fail closed.

## Placeholder resolution (MUST)

- Replace `<stable_toolchain_id_and_flags>` with the exact build toolchain string used.
- Replace all `<64-hex>` placeholders with real sha256 digests of the archive and library.
- Replace the manifest `checksum` with the computed canonical checksum.

