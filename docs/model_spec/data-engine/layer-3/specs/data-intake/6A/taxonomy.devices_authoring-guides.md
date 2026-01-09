# Authoring Guide — `taxonomy.devices` (6A.S4 device-type + OS/UA + static tiers vocab, v1)

## 0) Purpose

`taxonomy.devices` is the **sealed authority** for the closed vocab that 6A uses when emitting **static device attributes** in **6A.S4** (device/IP graph). In particular, 6A.S4 expects device rows to carry **device classification** fields such as:

* `device_type` (e.g., `MOBILE_PHONE`, `TABLET`, `DESKTOP`, `POS_TERMINAL`, `ATM`, `KIOSK`)
* `os_family` (e.g., `ANDROID`, `IOS`, `WINDOWS`, `MACOS`, `LINUX`, `EMBEDDED`)
* optional `ua_family` (browser/app family)
* optional static tiers such as `device_risk_tier` (`LOW`, `STANDARD`, `HIGH`)

…and S4 is required to **fail closed** if required taxonomies are missing/malformed or don’t contain the codes it needs to emit. 

This taxonomy is a **vocabulary + compatibility contract**, not a distribution. **Prevalence** (how many devices of each type, how often rooted, etc.) is defined in priors/config packs, not here. 

---

## 1) File identity (binding)

* **Manifest key (referenced as a dependency by 6A.S4 outputs):** `mlr.6A.taxonomy.devices` 
* **Role in `sealed_inputs_6A`:** `TAXONOMY` (ROW_LEVEL) 
* **Path:** `config/layer3/6A/taxonomy/taxonomy.devices.v1.yaml`
* **Format:** YAML (UTF-8, LF line endings)
* **Schema anchor:** `schemas.6A.yaml#/taxonomy/device_taxonomy_6A`
* **Digest posture:** **token-less**; do **not** embed digests/timestamps in-file. 6A.S0 sealing records the file's `sha256_hex`.

---

## 2) Scope and non-goals

### In scope

* Enumerating allowed values for: `device_type`, `os_family`, optional `ua_family`, optional `device_risk_tier`.
* Declaring **compatibility constraints** (e.g., which OS families are allowed for a device type).
* Declaring **stable capability tags** (e.g., “supports contactless”) as vocabulary, not prevalence.

### Out of scope (MUST NOT appear here)

* Probabilities/shares (e.g., “70% Android”) — belongs to device priors. 
* Rules for how devices attach to parties/accounts/merchants — belongs to linkage priors/rules. 
* Fraud roles/labels — belongs to 6A.S5 priors.

---

## 3) Strict YAML structure (MUST)

### 3.1 Top-level keys (exactly)

Required:

* `schema_version` *(int; MUST be `1`)*
* `taxonomy_id` *(string; MUST be `taxonomy.devices.v1`)*
* `device_types` *(list of objects)*
* `os_families` *(list of objects)*
* `risk_tiers` *(list of objects)*

Optional:

* `ua_families` *(list of objects)*
* `capability_vocabulary` *(list of strings)*
* `notes` *(string)*

Unknown top-level keys: **INVALID**.

### 3.2 ID naming rules (MUST)

All ids (`device_types[].id`, `os_families[].id`, `ua_families[].id`, `risk_tiers[].id`, tags) MUST:

* be ASCII
* match: `^[A-Z][A-Z0-9_]{1,63}$`

### 3.3 Ordering & formatting (MUST)

* Lists MUST be sorted by `id` ascending:

  * `device_types`, `os_families`, `ua_families`, `risk_tiers`, `capability_vocabulary`
* **No YAML anchors/aliases**
* 2-space indentation

---

## 4) Object schemas (fields-strict)

### 4.1 `os_families[]` (required)

Each object MUST contain:

* `id` *(e.g., `ANDROID`)*
* `label`
* `description`

Recommended:

* `kind` *(enum string: `MOBILE`, `DESKTOP`, `EMBEDDED`)*

### 4.2 `ua_families[]` (optional but recommended)

If present, each object MUST contain:

* `id` *(e.g., `CHROME`)*
* `kind` *(enum string; e.g., `BROWSER`, `WEBVIEW`, `APP`, `TERMINAL_FIRMWARE`, `API_CLIENT`)*
* `label`
* `description`

Rule:

* If `ua_families` is **absent**, 6A.S4 MUST treat `ua_family` as **not modelled** (either omit the column or write NULLs only).

### 4.3 `risk_tiers[]` (required)

Each object MUST contain:

* `id` *(minimum set: `LOW`, `STANDARD`, `HIGH`)*
* `label`
* `description`

Rule:

* These tiers are **static posture descriptors**, not “fraud labels”.

### 4.4 `device_types[]` (required)

Each object MUST contain:

* `id` *(e.g., `MOBILE_PHONE`)*
* `label`
* `description`

Required structural fields:

* `owner_kind` *(enum string: `PARTY`, `MERCHANT`, `EITHER`)*
* `is_mobile` *(bool)*
* `is_terminal` *(bool)*  *(POS/ATM/KIOSK true; consumer devices false)*
* `allowed_os_families` *(list of `os_families[].id`; non-empty)*

Optional but strongly recommended:

* `allowed_ua_families` *(list of `ua_families[].id`; non-empty if `ua_families` present)*
* `default_os_family` *(one of `allowed_os_families`)*
* `capability_tags` *(subset of `capability_vocabulary`)*
* `notes`

Rules:

* `default_os_family` (if present) MUST be in `allowed_os_families`.
* If `ua_families` exists and `allowed_ua_families` is present, every entry MUST exist in `ua_families`.
* Compatibility is enforced by **membership** in `allowed_os_families` / `allowed_ua_families`.

---

## 5) Realism requirements (NON-TOY)

Minimum floors (MUST):

* `len(device_types) >= 10`
* device type coverage:

  * ≥ 5 consumer/party devices (`owner_kind` in `{PARTY,EITHER}` and `is_terminal=false`)
  * ≥ 3 merchant/terminal devices (`owner_kind` in `{MERCHANT,EITHER}` and `is_terminal=true`)
* `len(os_families) >= 6` and MUST include:

  * `ANDROID`, `IOS`, `WINDOWS`, `MACOS`, `LINUX`, `EMBEDDED`
* `len(risk_tiers) >= 3` and MUST include:

  * `LOW`, `STANDARD`, `HIGH`

If `ua_families` is present (recommended), minimum floors (MUST):

* `len(ua_families) >= 7`
* MUST include browser/app coverage:

  * `CHROME`, `SAFARI`, `FIREFOX`, `EDGE`, `WEBVIEW`, `API_CLIENT`, `POS_FIRMWARE`

Recommended realism (SHOULD):

* Include `WEARABLE` and/or `IOT_DEVICE` if you want richer device-sharing + “non-browser” flows.
* Include `SERVER` if you model automation/API access patterns.

---

## 6) Authoring procedure (Codex-ready)

1. **Define OS families** (include required set; add `CHROMEOS` if desired).
2. **Define UA families** (recommended; include required set).
3. **Define risk tiers** (`LOW`, `STANDARD`, `HIGH`).
4. **(Optional) Define capability vocabulary** (10–20 tags) such as:

   * `CONTACTLESS`, `BIOMETRIC`, `NFC`, `GPS`, `ROOTABLE`, `JAILBREAKABLE`, `EMULATOR_PRONE`, `CAMERA`, `SMS_CAPABLE`, `PUSH_NOTIFICATIONS`
5. **Define device types**:

   * consumer types: mobile phone, tablet, laptop, desktop
   * merchant terminal types: POS terminal, ATM, kiosk
   * plus 1–3 extras: wearable, server, iot
   * for each, declare `allowed_os_families` (and UA families if modelled)
6. **Run acceptance checks** (§8) and fail closed if any violation.
7. **Freeze formatting** (sorted lists; no anchors; token-less).

---

## 7) EXAMPLE ONLY - MUST re-derive from current inputs; DO NOT COPY/SHIP

```yaml
schema_version: 1
taxonomy_id: taxonomy.devices.v1
notes: >
  Device taxonomy for 6A.S4 (device_type, os_family, optional ua_family, device_risk_tier).

capability_vocabulary:
  - BIOMETRIC
  - CAMERA
  - CONTACTLESS
  - EMULATOR_PRONE
  - GPS
  - JAILBREAKABLE
  - NFC
  - PUSH_NOTIFICATIONS
  - ROOTABLE
  - SMS_CAPABLE

os_families:
  - id: ANDROID
    kind: MOBILE
    label: Android
    description: Android mobile operating systems.
  - id: EMBEDDED
    kind: EMBEDDED
    label: Embedded
    description: Embedded/firmware OS used by terminals and IoT devices.
  - id: IOS
    kind: MOBILE
    label: iOS
    description: iOS mobile operating systems.
  - id: LINUX
    kind: DESKTOP
    label: Linux
    description: Linux desktop/server operating systems.
  - id: MACOS
    kind: DESKTOP
    label: macOS
    description: Apple desktop operating systems.
  - id: WINDOWS
    kind: DESKTOP
    label: Windows
    description: Microsoft desktop operating systems.

ua_families:
  - id: API_CLIENT
    kind: API_CLIENT
    label: API client
    description: Non-browser API/SDK user agent family.
  - id: CHROME
    kind: BROWSER
    label: Chrome
    description: Chromium-based browser family.
  - id: EDGE
    kind: BROWSER
    label: Edge
    description: Microsoft Edge browser family.
  - id: FIREFOX
    kind: BROWSER
    label: Firefox
    description: Firefox browser family.
  - id: POS_FIRMWARE
    kind: TERMINAL_FIRMWARE
    label: POS firmware UA
    description: POS terminal firmware/network stack user agent family.
  - id: SAFARI
    kind: BROWSER
    label: Safari
    description: Safari browser family.
  - id: WEBVIEW
    kind: WEBVIEW
    label: WebView
    description: In-app embedded web view family.

risk_tiers:
  - id: HIGH
    label: High risk
    description: Higher static risk posture (e.g., rooted/emulated more plausible).
  - id: LOW
    label: Low risk
    description: Lower static risk posture (more stable/managed).
  - id: STANDARD
    label: Standard risk
    description: Typical baseline posture.

device_types:
  - id: ATM
    owner_kind: MERCHANT
    is_mobile: false
    is_terminal: true
    label: ATM
    description: Automated teller machine / cash terminal.
    allowed_os_families: [EMBEDDED]
    allowed_ua_families: [POS_FIRMWARE]
    capability_tags: [CAMERA]

  - id: DESKTOP
    owner_kind: PARTY
    is_mobile: false
    is_terminal: false
    label: Desktop computer
    description: Fixed desktop computer used for web/app access.
    allowed_os_families: [LINUX, MACOS, WINDOWS]
    allowed_ua_families: [CHROME, EDGE, FIREFOX, SAFARI]
    capability_tags: [PUSH_NOTIFICATIONS]

  - id: IOT_DEVICE
    owner_kind: EITHER
    is_mobile: false
    is_terminal: false
    label: IoT device
    description: Embedded connected device (home/office) capable of network activity.
    allowed_os_families: [EMBEDDED]
    allowed_ua_families: [API_CLIENT]
    capability_tags: [EMULATOR_PRONE]

  - id: KIOSK
    owner_kind: MERCHANT
    is_mobile: false
    is_terminal: true
    label: Kiosk terminal
    description: Self-service kiosk terminal (tickets, ordering, etc.).
    allowed_os_families: [EMBEDDED, LINUX, WINDOWS]
    allowed_ua_families: [POS_FIRMWARE, CHROME]
    capability_tags: [CAMERA]

  - id: LAPTOP
    owner_kind: PARTY
    is_mobile: true
    is_terminal: false
    label: Laptop computer
    description: Portable computer used for web/app access.
    allowed_os_families: [LINUX, MACOS, WINDOWS]
    allowed_ua_families: [CHROME, EDGE, FIREFOX, SAFARI]
    capability_tags: [PUSH_NOTIFICATIONS]

  - id: MOBILE_PHONE
    owner_kind: PARTY
    is_mobile: true
    is_terminal: false
    label: Mobile phone
    description: Smartphone device used for apps and mobile web.
    allowed_os_families: [ANDROID, IOS]
    allowed_ua_families: [CHROME, SAFARI, WEBVIEW, API_CLIENT]
    capability_tags: [NFC, BIOMETRIC, GPS, PUSH_NOTIFICATIONS, SMS_CAPABLE, ROOTABLE, JAILBREAKABLE]

  - id: POS_TERMINAL
    owner_kind: MERCHANT
    is_mobile: false
    is_terminal: true
    label: POS terminal
    description: Merchant point-of-sale terminal used for in-person payments.
    allowed_os_families: [EMBEDDED, ANDROID]
    allowed_ua_families: [POS_FIRMWARE, API_CLIENT]
    capability_tags: [CONTACTLESS, NFC]

  - id: SERVER
    owner_kind: EITHER
    is_mobile: false
    is_terminal: false
    label: Server / backend host
    description: Server-like device representing automated backends and services.
    allowed_os_families: [LINUX, WINDOWS]
    allowed_ua_families: [API_CLIENT]
    capability_tags: [EMULATOR_PRONE]

  - id: TABLET
    owner_kind: PARTY
    is_mobile: true
    is_terminal: false
    label: Tablet
    description: Tablet device used for apps and mobile web.
    allowed_os_families: [ANDROID, IOS]
    allowed_ua_families: [CHROME, SAFARI, WEBVIEW, API_CLIENT]
    capability_tags: [BIOMETRIC, GPS, PUSH_NOTIFICATIONS]

  - id: WEARABLE
    owner_kind: PARTY
    is_mobile: true
    is_terminal: false
    label: Wearable
    description: Wearable device (watch/band) used for authentication or payments.
    allowed_os_families: [EMBEDDED, IOS, ANDROID]
    allowed_ua_families: [API_CLIENT]
    capability_tags: [CONTACTLESS, NFC, BIOMETRIC]
```

---

## 8) Acceptance checklist (MUST)

### 8.1 Structural checks

* YAML parses cleanly.
* `schema_version == 1`
* `taxonomy_id == taxonomy.devices.v1`
* Unknown keys absent (top-level and nested objects).
* All ids match `^[A-Z][A-Z0-9_]{1,63}$`.
* Lists sorted by `id` ascending.
* No YAML anchors/aliases.
* No timestamps/UUIDs/in-file digests.

### 8.2 Referential integrity

* `device_types[].allowed_os_families` ⊆ `os_families[].id` and non-empty.
* If `ua_families` present:

  * any `allowed_ua_families` ⊆ `ua_families[].id`
* `risk_tiers` contains required ids.

### 8.3 Realism floors

* device_types ≥ 10
* os_families includes the required 6
* risk_tiers includes LOW/STANDARD/HIGH
* coverage floors for consumer vs terminal devices met
* if `ua_families` present: ua_families ≥ 7 and includes required set

---

## 9) Change control (MUST)

* All ids are **stable API tokens**:

  * never repurpose an existing `device_type` / `os_family` / `ua_family` / `risk_tier`
  * additions are preferred over renames
* Breaking changes require bumping filename version (`taxonomy.devices.v2.yaml`) and updating:

  * device priors that reference codes
  * any compatibility checks in 6A.S4 validation (missing-code is a hard fail) 
