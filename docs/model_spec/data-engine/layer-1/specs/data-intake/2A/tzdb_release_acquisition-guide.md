# Acquisition Guide — `tzdb_release` (Pinned IANA tzdata archive + release tag)

## 0) Purpose and role in the engine

`tzdb_release` is the engine’s **pinned IANA Time Zone Database “data” distribution** (tzdata) for a specific `release_tag` (e.g., `2025a`). 2A uses it to compile the **authoritative transition timetable cache** (`tz_timetable_cache`) and to make civil-time legality checks reproducible across runs. ([IANA][1])

This guide exists so Codex can **fetch, verify, and package** the archive deterministically, with **fail-closed** behaviour.

---

## 1) Engine requirements (MUST)

### 1.1 Identity (MUST)

* **Artefact ID:** `tzdb_release`
* **Version token:** `{release_tag}` (pattern: `^20[0-9]{2}[a-z]?$`)
* **Storage root (Dictionary/Registry):** `artefacts/priors/tzdata/{release_tag}/`
* **Schema authority:** `schemas.2A.yaml#/ingress/tzdb_release_v1`

  * Required fields: `release_tag`, `archive_sha256` (hex64)

### 1.2 What “archive_sha256” means (MUST)

`archive_sha256` is the **SHA-256 of the exact downloaded archive bytes** (the compressed `tzdata…tar.gz` file), **not** the extracted contents. This digest is what 2A seals in S0 and what S3 later re-verifies against the bytes it reads.

### 1.3 Version pinning rule (MUST)

Codex **MUST NOT** choose “latest” implicitly.

* The acquisition pipeline must be given an explicit `release_tag` (e.g., by programme config / scenario selection / pinned intake manifest).
* If `release_tag` is missing → **FAIL CLOSED**.

> Practical note: if you want civil-time assets aligned, prefer matching `tz_world_<release>` and `tzdb_release.release_tag` (e.g., both `2025a`). The engine can tolerate `tzdb_release` newer than `tz_world`, but the pin must be intentional.

---

## 2) Recommended source (authoritative + versioned)

### Primary: IANA Time Zone Database distribution

Use IANA’s official distribution endpoints for the Time Zone Database (tz/zoneinfo). The IANA “Time Zone Database” page lists the latest release and provides direct links to the distributions (complete, data-only, code-only). ([IANA][1])

**We want the “Data Only Distribution”:** `tzdata{release_tag}.tar.gz`. ([IANA][1])

### Fallback: IANA FTP directory listing

If direct HTTP download 404s (or redirects unexpectedly), use the IANA FTP directory listing to confirm the expected filename exists for the pinned `release_tag`. ([IANA FTP][2])

---

## 3) Acquisition method (download)

### 3.1 Determine the filename (MUST)

Given `release_tag`:

* `archive_filename = "tzdata" + release_tag + ".tar.gz"`

  * Example: `release_tag = "2025a"` → `tzdata2025a.tar.gz`

### 3.2 Deterministic download URLs (MUST)

Attempt in this order:

1. **HTTP (preferred):** `https://www.iana.org/time-zones/repository/releases/{archive_filename}` ([IANA][1])
2. **FTP mirror (fallback):** `https://ftp.iana.org/tz/releases/{archive_filename}` ([IANA FTP][2])

Also download the detached signature file (optional but recommended for audit trail):

* `{archive_filename}.asc` from the same directory (exists in the IANA release listings). ([IANA FTP][2])

### 3.3 Fail-closed network behaviour (MUST)

Codex MUST abort if any of the following occur:

* HTTP status is not 200.
* The response is HTML/text error content instead of a gzip’d tarball.
* The downloaded file size is unreasonably small (e.g., < 50 KB).
* The filename does not exactly match `tzdata{release_tag}.tar.gz`.

---

## 4) Shaping / packaging rules (Codex implements; this doc specifies)

### 4.1 Output layout (MUST)

Under:

`artefacts/priors/tzdata/{release_tag}/`

write:

1. `tzdata{release_tag}.tar.gz`
2. `tzdb_release.json` (metadata object matching schema)
3. `tzdb_release.provenance.json` (mandatory provenance sidecar)
4. (Optional) `tzdata{release_tag}.tar.gz.asc`

### 4.2 `tzdb_release.json` content (MUST)

A single JSON object:

```json
{
  "release_tag": "2025a",
  "archive_sha256": "<sha256 of tzdata2025a.tar.gz bytes>"
}
```

### 4.2.1 Placeholder resolution (MUST)

Replace placeholders as follows:

* `<sha256 of tzdata2025a.tar.gz bytes>`: the lowercase hex SHA-256 of the downloaded archive bytes.
* `{release_tag}` elsewhere in this guide: the pinned tzdb release string (e.g., `2025a`), applied consistently in paths and filenames.

Must validate against `schemas.2A.yaml#/ingress/tzdb_release_v1`:

* `release_tag` matches `^20[0-9]{2}[a-z]?$`
* `archive_sha256` is lowercase hex64

### 4.3 No transformation of tzdata (MUST)

Do **not** edit or rewrite the archive.
Do **not** repack it.
Do **not** normalise line endings.
The archive bytes are the sealed authority.

---

## 5) Engine-fit validation checklist (MUST pass)

### 5.1 Structural (MUST)

* `tzdata{release_tag}.tar.gz` exists and is readable.
* SHA-256 computed from the file bytes equals `tzdb_release.json.archive_sha256`.
* `tzdb_release.json.release_tag` equals `{release_tag}`.

### 5.2 Archive sanity (SHOULD)

Without fully extracting, inspect the tar member list and ensure it contains the normal tzdata payload (examples include `africa`, `europe`, `northamerica`, `backward`, `etcetera`, `zone.tab`, `zone1970.tab`, `tzdata.zi`, `version`). (The exact set changes across releases, so validate “presence of several expected members”, not an exact manifest.)

### 5.3 Provenance completeness (MUST)

`tzdb_release.provenance.json` exists and contains required fields (see §6).

---

## 6) Provenance sidecar (MANDATORY)

Write `tzdb_release.provenance.json` containing, at minimum:

* `artefact_id: "tzdb_release"`
* `release_tag`
* `upstream`:

  * `primary_url` (the URL that actually succeeded)
  * `fallback_urls_attempted` (array; may be empty)
* `retrieved_at_utc` (rfc3339)
* `raw`:

  * `filename`
  * `bytes`
  * `sha256`
* `signature` (optional object; include if `.asc` downloaded)

  * `asc_filename`
  * `asc_sha256`
* `licence_note`

  * IANA describes the time zone database as public domain in its repository material. ([IANA][3])
  * (If your Registry/Dataset Dictionary currently labels this differently, record that here so licence_map can stay consistent until you reconcile.)

---

## 7) Working links (copy/paste)

```text
# IANA landing page (lists latest release + official links)
https://www.iana.org/time-zones

# Preferred direct download pattern (HTTP)
https://www.iana.org/time-zones/repository/releases/tzdata{release_tag}.tar.gz
https://www.iana.org/time-zones/repository/releases/tzdata{release_tag}.tar.gz.asc

# Fallback directory (FTP-over-HTTP listing + downloads)
https://ftp.iana.org/tz/releases/
https://ftp.iana.org/tz/releases/tzdata{release_tag}.tar.gz
https://ftp.iana.org/tz/releases/tzdata{release_tag}.tar.gz.asc
```

---

### Notes for Codex (kept simple on purpose)

* Do not infer `release_tag` from “latest”; require it as an explicit input.
* Always hash the **compressed** archive bytes.
* Store the archive + metadata + provenance together under the `{release_tag}` directory so 2A.S0 sealing and 2A.S3 compilation remain hermetic.
