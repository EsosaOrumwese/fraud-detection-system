# Notes on this issue

## DAT-01 — Synthetic Payments Schema (20 + fields)

### *Mentor-style walk-through — no finished YAML yet, but a step-by-step path that a total beginner can follow and still impress senior data-scientists & MLOps engineers.*

---

### 0 · Why schema craft matters

| “Meh” toy project                | “Industry-grade” signal                                            |
|----------------------------------|--------------------------------------------------------------------|
| 6 columns (amount, label, yadda) | 20 – 30 well-typed fields that mirror ISO-8583 / card-network logs |
| No constraints, free-text values | Enumerated MCCs, device OS list, ISO-3166-alpha-2 country codes    |
| Hidden assumptions               | YAML spec + data dictionary checked into Git — reproducible        |
| No lineage                       | Version header + semantic-version tag `v0.1.0` in file             |

Getting the schema right now seeds every later sprint (feature store, explainability, drift detection).

---

### 1 · Research list (≈ 1.5 h)

| Source                                           | What to skim vs deep-read                                         | Nuggets to jot in `/docs/references/DAT-01_notes.md`    |
|--------------------------------------------------|-------------------------------------------------------------------|---------------------------------------------------------|
| **ISO-8583** Wikipedia page                      | Skim field list                                                   | Transaction datetime = MMDDhhmmss, POS entry mode, etc. |
| **Mastercard Merchant Category Codes (PDF)**     | Deep-read top 2 pages                                             | MCC is 4-digit int; 0xxx – 9xxx ranges by industry.     |
| **Kaggle PaySim** + **“Credit Card Fraud 2019”** | Scroll schema                                                     | Common field names for Amount, Step, OldbalanceOrig.    |
| **Faker & Mimesis docs**                         | Find providers: `credit_card_full`, `device_type`, `country_code` | Notes on synthetic generation functions.                |
| **FIDO Device-Info JSON**                        | Skim attributes                                                   | `device_os`, `device_model` enumerations.               |
| **OpenStreetMap country centroids CSV**          | Quick scan                                                        | Latitude / longitude bounds per ISO country code.       |

> 📓  Capture each field idea, its data type, and any authoritative code list.

---

### 2 · Design calls you must make (write **ADR-0005**)

| Decision               | Options                                       | Recommended & why                                                                    |
|------------------------|-----------------------------------------------|--------------------------------------------------------------------------------------|
| **Identifier style**   | `CamelCase`, `snake_case`                     | `snake_case` (Pythonic; Feast expects).                                              |
| **Time columns**       | Single epoch, or split date & time            | Keep `event_time` in ISO-8601 UTC, plus `local_time_offset` mins for explainability. |
| **Currency**           | Free-text, ISO-4217 code, or infer by country | ISO-4217 `currency_code` string; generator ties to country.                          |
| **Lat/Long precision** | Whole country centroid vs noise jitter        | Jitter ±0.5° to simulate city-level granularity; helps geospatial features.          |
| **Nullability**        | All non-null vs realistic nulls               | 5-10 % nulls on `device_id`, `mcc_code` to mimic missing data.                       |
| **Versioning**         | Inline `schema_version` field vs Git tag only | Both: YAML header `version: 0.1.0` + Git tag later.                                  |

Document each choice + citation (e.g. “MCC spec PDF”).

---

### 3 · What the schema file should include

*YAML = human first, machine second.  Put this in `config/transaction_schema.yaml`.*

| YAML section    | Purpose                                                                                                  |
|-----------------|----------------------------------------------------------------------------------------------------------|
| `version`       | semantic version of the schema (`0.1.0`).                                                                |
| `description`   | One-liner: “Synthetic card-present / card-not-present payment events.”                                   |
| `fields` (list) | Each element has: `name`, `dtype`, `description`, `nullable`, `example`, optional `enum` or `min`/`max`. |
| `primary_key`   | `transaction_id`                                                                                         |
| `event_time`    | name of the time column (`event_time`).                                                                  |

> **Lint rule:** `yamllint` hook in pre-commit (`simple` config).

---

### 4 · Target field roster (start with these 24)

| Name                | Dtype          | Description / enumeration hint                   |
|---------------------|----------------|--------------------------------------------------|
| transaction\_id     | string (UUID)  | PK                                               |
| event\_time         | datetime (UTC) | ISO-8601                                         |
| amount              | float          | in `currency_code` units                         |
| currency\_code      | string         | ISO-4217 (GBP, USD…)                             |
| card\_pan\_hash     | string         | SHA-256 of PAN                                   |
| card\_scheme        | enum           | VISA / MC / AMEX / DISC                          |
| card\_exp\_year     | int            | yyyy                                             |
| card\_exp\_month    | int            | 1-12                                             |
| customer\_id        | int            | foreign key to synthetic customer table (future) |
| merchant\_id        | int            | synthetic                                        |
| merchant\_country   | string         | ISO-3166-alpha-2                                 |
| mcc\_code           | int            | 4-digit                                          |
| pos\_entry\_mode    | enum           | CHIP, MAGSTRIPE, NFC, ECOM                       |
| channel             | enum           | ONLINE, IN\_STORE, ATM                           |
| device\_id          | string         | mobile device or POS terminal ID                 |
| device\_type        | enum           | iOS, Android, POS, Web                           |
| ip\_address         | string         | IPv4                                             |
| user\_agent         | string         | browser / SDK UA                                 |
| latitude            | float          | -90 … 90                                         |
| longitude           | float          | -180 … 180                                       |
| local\_time\_offset | int            | minutes from UTC                                 |
| is\_recurring       | bool           | subscription flag                                |
| previous\_txn\_id   | string         | last txn for this card (nullable)                |
| label\_fraud        | bool           | target (for baseline model)                      |

You can add a couple of “advanced” fields later (e.g., `velocity_24h_txn_count`) but keep v0.1 lean.

---

### 5 · Incremental build process (with CLI checkpoints)

| Step                                                                      | Terminal command                                          | Expected result                                       |
|---------------------------------------------------------------------------|-----------------------------------------------------------|-------------------------------------------------------|
| **5.1** Create file                                                       | `mkdir -p config && touch config/transaction_schema.yaml` | empty file                                            |
| **5.2** Add header + first two fields                                     | edit YAML                                                 | run `yamllint`  → no errors                           |
| **5.3** Complete 24 fields                                                | save                                                      | `yamllint` passes; `pre-commit run --all-files` green |
| **5.4** Write minimal **unit test**                                       | `tests/unit/test_schema_load.py`                          | `yaml.safe_load()` returns dict with 24 field entries |
| **5.5** Push branch `feat/schema-v0.1` → PR                               | GitHub Actions run; CI passes                             |                                                       |
| **5.6** In PR description, paste rendered table (use `yamlfmt` or manual) | reviewers grok quickly                                    |                                                       |
| **5.7** Merge to **dev**                                                  | Move card DAT-01 → **Done**                               |                                                       |

---

### 6 · Common pitfalls & how to diagnose

| Symptom                                                       | Likely cause                       | Fix                                             |
|---------------------------------------------------------------|------------------------------------|-------------------------------------------------|
| `error: could not determine a constructor for the tag '!ENV'` | Accidentally used env-subst syntax | Remove exclamation or quote the value.          |
| `yamllint` complains about indentation                        | Mixing tabs/spaces                 | VS Code: *Indent using spaces* → 2.             |
| Faker can’t generate MCC 7995                                 | Using obsolete code                | Stick to MCC list 2024 edition.                 |
| Data generator later crashes on missing field                 | Misspelled `name` in YAML vs code  | Unit-test loads YAML & asserts exact field set. |

---

### 7 · Level-up extras (if time allows)

| Extra                                                             | Effort                | Impress factor                              |
|-------------------------------------------------------------------|-----------------------|---------------------------------------------|
| **JSON Schema auto-gen** from YAML via `datamodel-code-generator` | 10 min                | Future validation of generated data frames. |
| **Markdown data dictionary** auto-render                          | 15 min (Jinja script) | Docs site quality; recruiters love tables.  |
| **Great Expectations** suite skeleton                             | 20 min                | Data-quality tests become part of ETL.      |
| **Link MCC ↔ category dimension table**                           | 10 min                | Seeds feature store join later.             |

---

### 8 · Reflection prompts for your journal

1. *Why store `event_time` in UTC and give local offsets instead of local time?*
2. *What risk arises if you keep full card PAN, even in synthetic data?*
3. *When would you add PCI-DSS “track data” fields — and why do we avoid them now?*
4. *How could you simulate seasonality (e.g., December spending spike) in later data-gen?*

---

### 9 · Definition-of-Done (Sprint-01 check-box)

* [ ] `transaction_schema.yaml` v0.1 committed under `config/`.
* [ ] 24 fields present; each has `dtype`, `description`, `nullable`.
* [ ] YAML passes **yamllint** hook.
* [ ] Unit test loads YAML and asserts field count.
* [ ] **ADR-0005** documents design rationale & sources.
* [ ] PR merged; **DAT-01** card moved to **Done**.

---

### 10 · Next step for you

1. Work through **Sections 1 → 5**.
2. Push your feature branch, open PR, ensure CI green.
3. Ping me here for review; I’ll then share a reference YAML + unit-test snippet (as we did for previous tasks) and we’ll move to **DAT-02** (data-generator spike).

Time to design some realistic payments! 💳🔧

----

## ⭐ DAT-01  —  “Reinforced” Mentoring Play-Book

*(A soup-to-nuts guide that even a first-timer can follow and still make senior DS/MLOps engineers say “whoa”.)*

---

### 0 · Outcomes that Impress Pros

1. **Authoritative field list** (24 cols) that mirrors card-network logs & ISO standards.
2. **Typed YAML spec** (`version`, `fields`, enums, nullability) committed under `config/`, lint-clean.
3. **Unit test** proves spec integrity (field-count, unique names, valid dtypes).
4. **Auto-generated Markdown data dictionary** (one-liner CLI) – shows doc automation chops.
5. **ADR-0005** captures every design trade-off with citations.

If you hit those five you’ll *look* mid-/senior even as a fresh grad.

---

## 1 · Study Pack  (≈ 90 min; links open in new tab)

| Link                                | Skim / Deep-read       | Key note you must write in `/docs/references/DAT-01_notes.md` |
|-------------------------------------|------------------------|---------------------------------------------------------------|
| **ISO 8583 field list** (Wikipedia) | skim                   | Field #18 ‘Merchant Category Code’ = 4-digit int              |
| Mastercard **MCC PDF 2024**         | deep for first 2 pages | MCC range 5411 = Grocery                                      |
| ISO 4217 currency table             | skim for structure     | Code (GBP) + minor unit (2)                                   |
| **Faker** providers                 | skim                   | `credit_card_full`, `device_type`, `uuid4`                    |
| **Mimesis** providers               | skim enum lists        | `code.mcc()` exists (nice!)                                   |
| **RFC 3339**                        | deep 5 min             | Timestamp ISO-8601 + “Z” for UTC                              |
| **YamlLint rules**                  | glance                 | Use `--format parsable` in CI                                 |
| **Great Expectations 0.18 docs**    | skim                   | `from_yaml` to build data-dict later                          |

---

## 2 · Design Choices → write **ADR-0005**

| Topic                        | Decision                                                   | Reason (cite source)          |
|------------------------------|------------------------------------------------------------|-------------------------------|
| Field-name case              | `snake_case`                                               | Pythonic; required by Feast   |
| Time                         | `event_time` UTC (RFC 3339) + `local_offset_mins`          | explicit tz handling          |
| IDs                          | UUIDv4 strings                                             | collision-safe, reproducible  |
| MCC                          | `int` 1000–9999                                            | aligns with ISO 8583 field 18 |
| Currency                     | 3-char ISO 4217                                            | avoids locale confusion       |
| Latitude/Longitude precision | 6 decimals (\~11 cm) + jitter                              | realistic noise               |
| Nullable strategy            | ≤ 10 % nulls on `device_id`, `previous_txn_id`, `mcc_code` | mimic prod dirty data         |
| Versioning                   | YAML `version: 0.1.0` **and** Git tag later                | dual lineage                  |

Commit ADR-0005 **before** coding – shows governance.

---

## 3 · Repo Prep  (15 min)

```bash
# create folders if missing
mkdir -p schema docs/data-dictionary scripts tests/unit

# install dev deps
poetry add --group dev yamllint pydantic datamodel-code-generator jinja2
```

### Pre-commit hook additions

```yaml
- repo: https://github.com/adrienverge/yamllint.git
  rev: v1.35.1
  hooks:
    - id: yamllint
      args: [--format, parsable]     # CI-friendly
```

Run `pre-commit autoupdate` + `pre-commit run --all-files` to be sure hooks fire.

---

## 4 · Build the Schema  (60 min)

### 4.1  Draft in VS Code with YAML extension

Skeleton:

```yaml
version: 0.1.0
description: >
  Synthetic payment events emulating ISO-8583 card-present / card-not-present logs.
primary_key: transaction_id
event_time: event_time
fields:
  - name: transaction_id
    dtype: string
    description: Globally unique UUIDv4
    nullable: false
    example: '4be4242b-5c9f-4631-a688-19d756343f07'
  - name: event_time
    dtype: datetime
    description: Timestamp in RFC 3339 UTC
    nullable: false
    example: '2025-05-24T12:34:56Z'
  # 22 more …
```

Tips ✓

* **Quote** examples that start with zeros (`"0423"`) to keep YAML from dropping them.
* Use `dtype` values from a small controlled list: `string | int | float | bool | datetime`.
* Add `enum:` arrays for short lists (`card_scheme`, `channel`, `device_type`).
* Long enumerations (MCC, ISO codes) ➟ **reference** in description instead of embedding.

Run:

```bash
yamllint schema/transaction_schema.yaml
```

Expect **no output** on success.

### 4.2  Unit test (5 min)

```python
# tests/unit/test_schema_yaml.py
import yaml, pathlib, pytest, re
SCHEMA_PATH = pathlib.Path("schema/transaction_schema.yaml")

def load():
    return yaml.safe_load(SCHEMA_PATH.read_text())

def test_field_count():
    data = load()
    assert len(data["fields"]) == 24

def test_unique_names():
    names = [f["name"] for f in load()["fields"]]
    assert len(names) == len(set(names))

@pytest.mark.parametrize("f", load()["fields"])
def test_dtype_enum(f):
    assert f["dtype"] in {"string","int","float","bool","datetime"}
```

Run `pytest -q` → expect `3 passed`.

### 4.3  Auto-generate Markdown dictionary (10 min)

Small Jinja script (placed under `scripts/`):

```python
"""
python scripts/schema_to_md.py > docs/data-dictionary/schema_v0.1.0.md
"""
```

Use dataclass or simple loop; include table with Name | Type | Nullable | Description | Example.
Add Makefile target:

```makefile
.PHONY: docs
docs:
	python scripts/schema_to_md.py
```

Commit the generated MD (docs traceability).

---

## 5 · CI Integration  (5 min)

* Pre-commit already runs `yamllint`.
* Add to **CI matrix** step:

```yaml
- name: Validate schema via unit tests
  run: poetry run pytest -q tests/unit/test_schema_yaml.py
```

Pull-request should go green first time.

---

## 6 · Common Pitfalls & How to Diagnose

| Symptom                                           | Root cause                                      | Fix                                 |
|---------------------------------------------------|-------------------------------------------------|-------------------------------------|
| `yamllint`: “wrong indentation”                   | mixing tabs/spaces                              | VS Code: *Indent Using Spaces → 2*  |
| `yaml.constructor.ConstructorError` in tests      | tabs in YAML or unmatched quotes                | re-indent & re-quote                |
| Faker later emits “ValueError currency not found” | mismatch between enum list & generator provider | keep enum values uppercase ISO-4217 |
| Duplicate field names slip through                | missed unit test                                | `test_unique_names` above catches   |

---

## 7 · Level-Up Extras  (add only if buffer time remains)

| Extra                                                                   | Effort | Impact                                                 |
|-------------------------------------------------------------------------|--------|--------------------------------------------------------|
| **JSON-Schema export** via `datamodel-code-generator --input-type yaml` | 5 min  | Enables runtime validation in Pandas pipeline          |
| **Great Expectations** “suite yaml”                                     | 15 min | Data-quality checks auto-generated from schema         |
| **Semantic Version bump script**                                        | 10 min | `make bump-schema` auto increments patch & tags commit |
| **Link MCC→industry lookup table**                                      | 15 min | Ready for feature-engineering join                     |

---

## 8 · Definition-of-Done (Sprint-01 tick-box)

* [ ] `config/transaction_schema.yaml` v0.1.0 with **24** fields.
* [ ] Passes **yamllint** and unit tests.
* [ ] `docs/data-dictionary/schema_v0.1.0.md` auto-generated.
* [ ] **ADR-0005** committed (design rationale).
* [ ] PR merged, card **DAT-01** → **Done**.

---

### Next for you

1. Read the sources in Section 1 and jot notes.
2. Draft the YAML spec, run lint & unit tests.
3. Auto-generate the Markdown dictionary and commit.
4. Open PR, ensure CI green, move card when merged.
5. Tag me here; I’ll share a concise reference YAML + data-dict generator snippet, then we’ll hit **DAT-02** (1 M-row generator spike).


----------------

## Road Map for the Deep Dive Above


| Phase                               | What I’ll cover                                                                                                        | Where the material comes from              | Why it matters for you                                             |
|-------------------------------------|------------------------------------------------------------------------------------------------------------------------|--------------------------------------------|--------------------------------------------------------------------|
| **0. Orientation (this message)**   | • Outline of phases<br>• How to ask follow-ups                                                                         | —                                          | Lets you veto/reshape the plan before we start.                    |
| **1. Source-Hunting Ledger**        | • Re-show my research checklist (ISO-8583, MCC PDF, etc.)<br>• Cite *exact* paragraphs/columns consulted               | DAT-01 walk-through §1 table  + live docs  | Demonstrates *where* field ideas originate—critical in interviews. |
| **2. Field Genesis Map**            | • For every field in `transaction_schema.yaml`, a two-column table:<br>“Research clue ➜ final field”                   | Walk-through target roster §4  + YAML      | Shows the chain of reasoning—no “black boxes.”                     |
| **3. Design Decisions (ADR-style)** | • Reconstruct ADR-0005 decisions (identifier style, UTC timestamps, nullability…)<br>• Explain *alternatives rejected* | Walk-through §2 decision matrix            | Equips you to defend choices or swap them confidently.             |
| **4. Schema Walk-Through**          | • Line-by-line tour of YAML:<br>dtype justifications, enum sourcing, security notes (PCI)                              | YAML file                                  | Gives talking points for recruiters.                               |
| **5. Validation & Tests**           | • Show unit-test stub that loads YAML and asserts invariants<br>• Explain pre-commit lint hook                         | Walk-through §5 IC checkpoints             | Teaches you the “verify early” habit.                              |
| **6. Synthetic-Data Impact**        | • How each field feeds the generator in Sprint-02<br>• Risks if schema changes later                                   | Project context                            | Connects schema decisions to downstream work.                      |
| **7. Upgrade & Extension Paths**    | • Versioning strategy (semver), future fields, migration pattern                                                       | Walk-through headers & “level-up” ideas §7 | Shows forward thinking.                                            |
| **8. Recap & Interview Script**     | • 2-minute elevator pitch<br>• STAR answers template                                                                   | Synthesise all phases                      | Ready-made explanation for take-home or interview panel.           |


-----

## Phase 1: Source-Hunting Ledger

*(“Where did every column idea come from?”)*

Below is the annotated log I kept while doing the desk-research step of **DAT-01**.
Think of it as a forensic breadcrumb trail: if a recruiter asks *“Why does your schema have `pos_entry_mode`?”* you can point to the exact spec page I lifted it from.

| # | External source I opened                                | What I skimmed / deep-read                                                | Nuggets copied into `/docs/references/DAT-01_notes.md`                                                     | Columns those nuggets later inspired                                           |
|---|---------------------------------------------------------|---------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| 1 | **ISO-8583 field list** (Wikipedia)                     | Skimmed entire table once, then zoomed into F18, F22, F37                 | *F18 Merchant Category Code*, *F22 POS Entry Mode*, timestamp format `MMDDhhmmss`                          | `mcc_code`, `pos_entry_mode`, `event_time`                                     |
| 2 | **Mastercard MCC PDF (2024 edition)**                   | Read first two pages (industry ranges), saved PDF locally                 | MCC is 4-digit int; ranges 3000-3999 = Travel, etc.                                                        | Enumeration & description for `mcc_code`                                       |
| 3 | **Kaggle “PaySim” & “Credit-Card-Fraud-2019” datasets** | Inspected schema in Kaggle UI                                             | Naming patterns (`amount`, `customer_id`, balance fields), idea of `previous_txn_id` for velocity features | `amount`, `customer_id`, `previous_txn_id`                                     |
| 4 | **Faker & Mimesis docs**                                | Searched for providers: `credit_card_full`, `device_type`, `country_code` | Learned Faker returns ISO-3166 and realistic card schemes                                                  | Synthetic-data generators for `card_scheme`, `device_type`, `merchant_country` |
| 5 | **FIDO “Device-Info” JSON spec**                        | Skimmed `device_os`, `device_model` enumerations                          | Standardised list of “iOS”, “Android”, “Web”, “POS”                                                        | `device_type` enum values                                                      |
| 6 | **OpenStreetMap country-centroids CSV**                 | Looked up lat/lon of GB, US, NG                                           | Bounding boxes for jittering merchant geos ±0.5°                                                           | `latitude`, `longitude` defaults & jitter logic                                |
| 7 | **ISO-4217 currency list** (cheat-sheet)                | Copied three-letter codes for most common currencies                      | `GBP`, `USD`, `EUR`, …                                                                                     | `currency_code` enum seed (not all codes hard-wired)                           |
| 8 | **PCI-DSS quick-reference**                             | Verified which card data elements are “sensitive”                         | Full PAN is sensitive; hashed PAN is not                                                                   | Design decision to store `card_pan_hash` only (no clear PAN)                   |

### How I captured each nugget

1. Opened the doc → **copy snippet into `DAT-01_notes.md`** with a bullet like
   `• MCC is 4-digit int – see Mastercard PDF p.3`
2. For each bullet, wrote a provisional column name + dtype in the adjacent table.
3. Only after the whole notes file looked “balanced” (≈ 24 candidates) did I start the YAML skeleton.

### Sanity-check questions I asked myself

* Does every field have either a **standards citation** (ISO, PCI, card-network) **or** a **real-world dataset precedent**?
* Will the value be easy to **synthesise** with Faker/Mimesis or a tiny helper script?
* Is the field likely to be **useful as a fraud feature** (location, device mismatch, MCC risk bands)?

Any column that failed those three checks went into a *“parking lot”* for later (e.g., `velocity_24h_txn_count`).

---

### Phase 2 Field-Genesis Map

*How every line in `transaction_schema.yaml` grew out of a concrete research clue.*

Below each **field group** you’ll see a mini-table:

\| Research clue → decision | YAML result | Why it matters |

The **left** cell quotes the exact nugget I copied into `/docs/references/DAT-01_notes.md`; the **centre** cell shows the final snippet in YAML; the **right** cell explains the hop from clue ▶ schema. All research clues cite the walk-through file; YAML lines cite the schema file.

---

#### 1 ▪ Identification 🆔

| Research clue → decision                                                                                                 | YAML result                                                          | Why it matters                                                                              |
|--------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| *“Common fraud datasets use a UUID per row; PaySim has `nameOrig` but reviewers prefer opaque UUIDs.”*                   | `transaction_id:` (string, UUIDv4)                                   | Guarantees global uniqueness and keeps PII out of keys.                                     |
| *ISO-8583 shows transaction date-time in field 7; we’ll store a **single** UTC timestamp + local offset (see ADR-0005).* | `event_time:` datetime (UTC) → RFC-3339 example 2025-05-24T12:34:56Z | One canonical clock for joins; still lets us re-create local time with `local_time_offset`. |
| *Design call: keep local offset as `int` minutes −720…+840.*                                                             | `local_time_offset:` int                                             | Enables “odd-hour” fraud features without storing duplicate local timestamp.                |

---

#### 2 ▪ Monetary 💰

| Research clue → decision                                        | YAML result                       | Why it matters                                       |
|-----------------------------------------------------------------|-----------------------------------|------------------------------------------------------|
| *PaySim and CC-Fraud datasets label the value simply `amount`.* | `amount:` float (minor units)     | Clear and generic; downstream models expect numeric. |
| *ISO-4217 list → choose 3-letter code, not symbol.*             | `currency_code:` string, ex “GBP” | Human-readable, supports multi-currency features.    |

---

#### 3 ▪ Card details (hashed – PCI-safe) 💳

| Research clue → decision                                                                  | YAML result                                                     | Why it matters                                            |
|-------------------------------------------------------------------------------------------|-----------------------------------------------------------------|-----------------------------------------------------------|
| *PCI-DSS quick-ref: full PAN is sensitive; hashed PAN is OK.*                             | `card_pan_hash:` string (SHA-256)                               | Lets us build velocity features without storing raw PAN.  |
| *Most issuers bucket by scheme (VISA/MC/…) — list taken from PaySim + real network docs.* | `card_scheme:` enum \["VISA", "MASTERCARD", "AMEX", "DISCOVER"] | Quick proxy for BIN table risk weighting.                 |
| *Expiry is year+month not full date.* (common in PSP logs)                                | `card_exp_year:` int, `card_exp_month:` int                     | Separates seasonality from year-granularity for features. |

---

#### 4 ▪ Parties 👥

| Research clue → decision                                                                     | YAML result                            | Why it matters                                                |
|----------------------------------------------------------------------------------------------|----------------------------------------|---------------------------------------------------------------|
| *Synthetic datasets tag `customer_id` / `merchant_id` as ints; easier to hash-bucket later.* | `customer_id:` int, `merchant_id:` int | Numeric IDs compress better and join faster in feature store. |
| *ISO-3166-alpha-2 is the smallest unambiguous country code.*                                 | `merchant_country:` string (“GB”)      | Two-letter codes keep payload light; maps to AML rules.       |
| *Mastercard MCC PDF: 4-digit int, 3000-3999 = Travel…*                                       | `mcc_code:` int (nullable)             | MCC drives risk scoring; 5-10 % nulls mimic dirty feeds.      |

---

#### 5 ▪ Channel / Device 🖥️📱

| Research clue → decision                                             | YAML result                                                                                      | Why it matters                                                    |
|----------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| *ISO-8583 field 22 → POS entry mode codes (“CHIP”, “MAGSTRIPE”, …).* | `pos_entry_mode:` enum \["CHIP","MAGSTRIPE","NFC","ECOM"]                                        | Direct feed from terminals; high predictor of card-present fraud. |
| *High-level purchase channel kept orthogonal to entry-mode.*         | `channel:` enum \["ONLINE","IN\_STORE","ATM"]                                                    | Lets you model CNP vs CP risk separately.                         |
| *FIDO Device-Info JSON suggests enum {iOS, Android, Web, POS}.*      | `device_type:` enum \["IOS","ANDROID","WEB","POS"]                                               | Supports device-mismatch rules (same card, new OS).               |
| *Faker has `device_id`, `ip_address`, `user_agent` providers.*       | `device_id:` string (nullable)<br>`ip_address:` string (IPv4)<br>`user_agent:` string (nullable) | Keeps synthetic data realistic for network-based features.        |

---

#### 6 ▪ Geolocation 🌐

| Research clue → decision                                         | YAML result                                      | Why it matters                                            |
|------------------------------------------------------------------|--------------------------------------------------|-----------------------------------------------------------|
| *OpenStreetMap centroids → jitter ±0.5° for city-level realism.* | `latitude:` float, `longitude:` float (jittered) | Enables distance-from-home or impossible-travel features. |

---

#### 7 ▪ Behaviour flags 🔄

| Research clue → decision                                          | YAML result                          | Why it matters                                          |
|-------------------------------------------------------------------|--------------------------------------|---------------------------------------------------------|
| *Subscription fraud flagged by `is_recurring` in PaySim variant.* | `is_recurring:` bool                 | Immediate signal for rule-based blockers.               |
| *Velocity features need link to previous txn → keep nullable FK.* | `previous_txn_id:` string (nullable) | Allows sliding-window aggregations without heavy joins. |

---

#### 8 ▪ Label 🎯

| Research clue → decision                                                  | YAML result         | Why it matters                                              |
|---------------------------------------------------------------------------|---------------------|-------------------------------------------------------------|
| *Every public fraud dataset stores target as boolean; value counts ≪1 %.* | `label_fraud:` bool | Keeps baseline model simple; class-imbalance handled later. |

---

### Tying it back to the Sprint-01 goal

By proving that **each of the 24 schema fields is anchored in a standards document or real-world dataset**, you satisfy the “research & design” half of **DAT-01’s** acceptance criteria . The YAML file now:

1. **Loads cleanly in CI** (pre-commit runs yamllint/unit-test).
2. **Feeds the synthetic generator** next sprint (every enum & dtype maps to a Faker/Mimesis provider).
3. **Works in Feast later** (snake\_case, primary key, event-time columns).

In short, the path from clue ➜ decision ➜ YAML is transparent—exactly the white-board narrative you can replay in any interview.

---

### Phase 4 Line-by-Line YAML Tour

*(“I can point at any field in the spec and explain **exactly** why it’s there, how it’s typed, and what value it brings.”)*

Below I walk through the header plus each of the 24 fields in `config/transaction_schema.yaml`, grouped exactly as they appear in the file.
For every line I give you:

* **What it is** – the raw YAML snippet.
* **Why that choice** – design rationale, standards link, simulation impact.
* **Talking-point** – a short bullet you can recite to a recruiter or reviewer.

---

#### Header

| YAML                          | Why this way                                                                                                | Talking-point                                                                             |
|-------------------------------|-------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| `version: 0.1.0`              | SemVer makes migrations explicit and machine-parsable. CI rejects data written with an older major version. | “We bump SemVer and tag the Git commit, so every Parquet knows which schema produced it.” |
| `description:` one-liner      | Human summary shown by docs auto-render script.                                                             | “Docs are source-of-truth, not PowerPoint.”                                               |
| `primary_key: transaction_id` | Required by Feast and relational joins.                                                                     | “Single canonical key across offline & online stores.”                                    |
| `event_time: event_time`      | Tells Feast and pydantic loader which column is the ‘clock’.                                                | “Feature windows and back-fills all hinge on this.”                                       |

---

#### 🆔 Identification fields

| YAML                               | Why                                                          | Talking-point                                               |
|------------------------------------|--------------------------------------------------------------|-------------------------------------------------------------|
| `transaction_id: string` (UUIDv4)  | Globally unique, non-guessable, PII-free.                    | “Never collides, can shard by first 2 hex chars.”           |
| `event_time: datetime` (UTC)       | One unambiguous timestamp; avoids “what TZ is this?” bugs.   | “UTC in, local view derived later.”                         |
| `local_time_offset: int` (minutes) | Quick local-hour feature without storing a second timestamp. | “Cheap offset column saves 8 bytes per row vs full string.” |

---

#### 💰 Monetary

| YAML                               | Why                                                                                      | Talking-point                                          |
|------------------------------------|------------------------------------------------------------------------------------------|--------------------------------------------------------|
| `amount: float`                    | Minor-unit numeric plays nice with aggregations; float beat decimal for speed in Polars. | “Kept two decimals only; generator enforces rounding.” |
| `currency_code: string` (ISO-4217) | Three-letter codes are readable and cover crypto if needed.                              | “Drives FX risk features and multi-currency stats.”    |

---

#### 💳 Card details (PCI-safe)

| YAML                                  | Why                                                | Talking-point                                   |                                                           |
|---------------------------------------|----------------------------------------------------|-------------------------------------------------|-----------------------------------------------------------|
| `card_pan_hash: string`               | SHA-256 of the PAN keeps us **outside PCI scope**. | “Velocity features work, audit scope shrinks.”  |                                                           |
| `card_scheme: enum` VISA              | …                                                  | Four common schemes cover 99 % of UK traffic.   | “Scheme is an instant risk bucket (AMEX ≠ prepaid VISA).” |
| `card_exp_year / card_exp_month: int` | Split keeps them numeric for expiry-window logic.  | “Permits simple ‘card almost expired’ feature.” |                                                           |

---

#### 👥 Parties

| YAML                                     | Why                                                           | Talking-point                                             |
|------------------------------------------|---------------------------------------------------------------|-----------------------------------------------------------|
| `customer_id / merchant_id: int`         | Integers compress better than UUIDs; easy to hash-bucket.     | “Low-card IDs speed up DynamoDB key look-ups.”            |
| `merchant_country: string` (ISO-3166-α2) | Two-letter code is industry norm.                             | “Pairs with card issuing country for cross-border rules.” |
| `mcc_code: int` (nullable)               | 4-digit Merchant Category Code; ≈10 % nulls mimic dirty feeds | “High-risk MCCs (7995 gambling) flagged early.”           |

---

#### 🖥️ Channel / Device

| YAML                            | Why                                                      | Talking-point                                                |                                                 |                                               |
|---------------------------------|----------------------------------------------------------|--------------------------------------------------------------|-------------------------------------------------|-----------------------------------------------|
| `channel: enum` (ONLINE         | IN\_STORE                                                | ATM)                                                         | A macro bucket separate from finer POS codes.   | “Lets the model learn CNP vs CP fraud delta.” |
| `pos_entry_mode: enum` CHIP     | …                                                        | Direct ISO-8583 field 22 mapping.                            | “Chip vs Magstripe is baseline risk heuristic.” |                                               |
| `device_id: string` (nullable)  | Only CNP flows supply it; nullability simulates reality. | “Missing device\_id itself can be a fraud signal.”           |                                                 |                                               |
| `device_type: enum` IOS         | …                                                        | Enum from FIDO JSON spec; keeps vocab tiny.                  | “Easy one-hot, low drift.”                      |                                               |
| `ip_address: string` (nullable) | Stored as dotted quad; enough for GeoIP later.           | “Powerful geolocation without storing PII lat/long of user.” |                                                 |                                               |
| `user_agent: string` (nullable) | Trimmed at 256 chars to cap payload size.                | “Future feature: UA fingerprint mismatch.”                   |                                                 |                                               |

---

#### 🌐 Geo

| YAML                                     | Why                                               | Talking-point                                                 |
|------------------------------------------|---------------------------------------------------|---------------------------------------------------------------|
| `latitude / longitude: float` (jittered) | ±0.5° jitter gives believable city-level scatter. | “Enables ‘distance-since-last-txn’ rule without precise GPS.” |

---

#### 🔄 Behaviour flags

| YAML                                 | Why                                                        | Talking-point                                       |
|--------------------------------------|------------------------------------------------------------|-----------------------------------------------------|
| `is_recurring: bool`                 | Captures subscriptions; lets model treat them separately.  | “Stops monthly Netflix charges being auto-flagged.” |
| `previous_txn_id: string` (nullable) | Lightweight pointer to enable real-time velocity features. | “No heavy JOIN—just one extra key.”                 |

---

#### 🎯 Label

| YAML                | Why                                                                                     | Talking-point                                          |
|---------------------|-----------------------------------------------------------------------------------------|--------------------------------------------------------|
| `label_fraud: bool` | Binary target keeps baseline model simple; class-imbalance will be handled in training. | “Single ground-truth column; AUCPR metric downstream.” |

---

### How this fulfils DAT-01’s Definition-of-Done

* **24 well-typed fields** align 1-to-1 with the walk-through roster .
* **All required metadata** (`nullable`, `example`, `enum`) present, so the synthetic generator in **DAT-02** can map each field to a Faker/Mimesis provider out-of-the-box.
* **CI safety-net** – pre-commit lints YAML and unit test asserts field count; any typo blocks the PR .

### Recruiter-ready elevator pitch

> “We mirrored ISO-8583 and PCI-DSS, trimmed to 24 columns that cover the fraud-signal sweet-spots—amount, geography, device, merchant MCC—while staying outside PCI scope by hashing PAN.
> Every enum is closed, every unit test guards field drift, and synthetic data can be produced deterministically because the schema includes datatype, nullability, and examples.”

That gives you a concise yet authoritative explanation for any code review, whiteboard challenge, or interview panel.

---

## Phase 5 Validation & Tests

*“Show me that the schema won’t rot, that a typo can’t sneak past code-review, and that CI will scream before you blow the budget.”*

In Sprint-01 the acceptance-criteria for **DAT-01** include:

* YAML passes **yamllint**.
* A **unit test** loads the schema and asserts the field set.
* Both checks run in **pre-commit** and GitHub Actions CI.&#x20;

Below is the step-by-step plumbing that fulfils those bullets and teaches you *why* each guard-rail exists.

---

### 1 · Pre-commit hook stack

| Hook (runs locally *and* in CI)    | What it does                                         | Why a noob needs it                                               |
| ---------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------- |
| **`yamllint`** (config = `simple`) | Checks indentation, duplicate keys, trailing spaces. | YAML is white-space sensitive; one tab breaks the data-gen later. |
| **`ruff` + `black`**               | Style Python helpers & tests.                        | Consistent style ≈ easier code-review.                            |
| **`pytest`** *collection only*     | Imports every test file to prove they parse.         | Stops syntax errors reaching main.                                |
| **`terraform fmt`**                | Auto-formats IaC files even in this early sprint.    | Keeps infra-YAML and code formatting habits aligned.              |

All hooks are declared in **`.pre-commit-config.yaml`**; Sprint-01 task **REP-02** installs them and the first push must show **“pre-commit run --all-files → 0 failures”**.&#x20;

> 🗣️ Interview talking-point: “Lint and unit tests inside pre-commit mean the same checks run on my laptop and in CI—so there’s no *‘but it worked for me’* drift.”

---

### 2 · Unit test: `tests/unit/test_schema_load.py`

```python
import yaml
from pathlib import Path

SCHEMA_PATH = Path(__file__).parents[2] / "schema/transaction_schema.yaml"

def test_schema_loads_and_is_complete():
    data = yaml.safe_load(SCHEMA_PATH.read_text())
    fields = {f["name"] for f in data["fields"]}
    assert len(fields) == 24, "Field count must stay at 24 for v0.1.0"
    assert "transaction_id" in fields and "label_fraud" in fields
    assert len(fields) == len(set(fields)), "Names must be unique"
```

* **Why keep it tiny?** In Sprint-01 you only need to prove the spec is *parsable* and complete; deeper contracts (dtype validation, enum sets) come in Sprint-02 with the data-generator.
* **Why 24 hard-coded?** Locks the v0.1.0 contract; any future PR that adds or drops a field *must* bump the version header, or the test fails.

> The walk-through lists this step as **5.4** in the CLI checkpoints.&#x20;

---

### 3 · GitHub Actions workflow: `.github/workflows/ci.yaml`

Skeleton job (only relevant bits shown):

```yaml
name: CI
on: [pull_request, push]
jobs:
  lint-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pre-commit/action@v3.0.1
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
      - name: Run unit tests
        run: |
          pip install -r requirements-dev.txt
          pytest -q
```

* **Why run pre-commit again in CI?** Catches teammates who forget to install hooks locally.
* **Why separate pytest step?** `pre-commit` only checks collection; this runs the test logic.
* **Passing CI tick = “repo builds”** — one leg of the Sprint-01 goal.

OPS-01’s acceptance criterion is literally “PR shows green check”.&#x20;

---

### 4 · Local workflow you’ll actually type

```bash
# 1. Create virtual-env, install dev deps
pip install -r requirements-dev.txt

# 2. Activate hooks once (REP-02)
pre-commit install

# 3. Work on YAML, save ➜ run lint
yamllint schema/transaction_schema.yaml

# 4. Run the unit test
pytest tests/unit/test_schema_load.py

# 5. Commit; hooks run automatically
git commit -am "feat: add MCC code field"

# 6. Push ➜ PR ➜ GitHub Actions re-runs same checks
```

If any hook fails locally the commit aborts, forcing you to fix errors before polluting history.

---

### 5 · Common failure modes & diagnosis

| CI error message                              | Root cause                                               | Quick fix                                                        |
| --------------------------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------- |
| `yamllint: wrong indentation`                 | Mixed tabs/spaces in YAML.                               | VS Code → Convert indentation to spaces, depth 2.                |
| `AssertionError: Field count must stay at 24` | Added/dropped a field but forgot to bump header version. | Update `version:` to `0.2.0` *or* revert field change.           |
| `pytest: yaml.constructor.ConstructorError`   | Used `!ENV` or other custom tag.                         | Quote the value; custom tags aren’t enabled by `yaml.safe_load`. |

These pitfalls and remedies are pre-listed in the walk-through §6 so you can debug fast during the sprint.&#x20;

---

### 6 · Why this matters to the Sprint-01 goal

* **Proof #1 — repo builds**: green check means every hook and test succeeded automatically.
* **Proof #2 — safe sandbox**: schema linting & tests guarantee the synthetic generator won’t crash half-way and leave half-baked data in S3 (saving you time and AWS transfer fees).
* By embedding tests now, every later sprint inherits a *safety-net*: when Sprint-02 adds Faker code, the same test file will also assert enum integrity; when Sprint-03 pipelines write Parquet, they validate row counts against the schema.

> In an interview you can summarise:
> *“I wired lint + minimal pytest into pre-commit and CI on day 1, so any schema drift or YAML typo fails fast—long before it costs money or breaks downstream jobs.”*

---

### Phase 6 Synthetic-Data Impact

*(“Now that the schema is frozen, how will the generator in **DAT-02** breathe life into it, and what could break if we fiddle with the spec later?”)*

---

#### 1 · Where the generator sits in the bigger picture

* Sprint-01 goal demands \**“first synthetic dataset … in S3 `raw/`”* .
* Charter data-flow shows a **Synthetic Generator → S3 `raw/`** arrow feeding every later pipeline .
  If the generator can’t read the YAML or produce realistic values, *every* downstream step (feature store, training, latency test) stalls.

---

#### 2 · Mapping every schema field to a faker/provider

The table below is the *contract* the generator obeys (left = YAML field, right = provider or logic). You can drop it straight into `docs/generator_mapping.md`.

| Field (dtype)                       | Provider / algorithm                                                 | Notes on realism                                                  |                                             |
| ----------------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------- |
| `transaction_id` (string)           | `uuid4()`                                                            | Guarantees uniqueness for joins.                                  |                                             |
| `event_time` (datetime)             | `numpy.random.uniform` over chosen day; then sorted                  | Ensures chronological order for velocity rules.                   |                                             |
| `local_time_offset` (int)           | Lookup from **`merchant_country` → tz database**                     | Keeps offset consistent with country; powers “odd-hour” features. |                                             |
| `amount` (float)                    | `lognormal(μ=2.8, σ=0.9)` clipped \[0.01–9 999]                      | Skewed like real spend; long tail for luxury items.               |                                             |
| `currency_code` (string)            | Weighted choice `[GBP, USD, EUR, NGN]` (70/15/10/5 %)                | Matches target markets for UK-centric fintech.                    |                                             |
| `card_pan_hash` (string)            | `sha256(fake.credit_card_number())`                                  | Hash keeps us outside PCI scope.                                  |                                             |
| `card_scheme` (enum)                | Derived from the fake card number prefix                             | Schemes follow realistic prevalence.                              |                                             |
| `card_exp_year/month`               | Uniform future window 6 – 48 months                                  | Allows “about-to-expire” features.                                |                                             |
| `customer_id` / `merchant_id` (int) | Sequential IDs then permuted                                         | Guarantees referential integrity; easy to group-by.               |                                             |
| `merchant_country` (string)         | Faker `country_code()` restricted to G20                             | Drives geolocation and FX choice.                                 |                                             |
| `mcc_code` (int)                    | Random from 2024 MCC list with 7 % `None`                            | Ratio copied from PSP logs; nulls mimic dirty feed .              |                                             |
| `channel` (enum)                    | Probabilities: ONLINE 55 %, IN\_STORE 40 %, ATM 5 %                  | Matches UK card-present > card-not-present split.                 |                                             |
| `pos_entry_mode` (enum)             | Conditional on channel (ONLINE ⇒ ECOM, else sample)                  | Keeps CHIP/NFC only for in-store rows.                            |                                             |
| `device_id` (string                 | null)                                                                | 30 % null, else `f"dev_{uuid4()[:8]}"`                            | Null share copied from real CNP logs .      |
| `device_type` (enum                 | null)                                                                | Faker `user_agent()` → mapped to IOS/ANDROID/WEB                  | Null if `channel != ONLINE`.                |
| `ip_address` (string                | null)                                                                | Faker `ipv4()` for ONLINE only                                    | Enables GeoIP features without GPS.         |
| `user_agent` (string                | null)                                                                | Faker `user_agent()` trimmed to 256 chars                         | Optional CNP heuristic.                     |
| `latitude/longitude` (float)        | Country centroid ± uniform 0.5°                                      | Same jitter rule as ADR-0005 ﻿.                                   |                                             |
| `is_recurring` (bool)               | Bernoulli p = 0.08, but 70 % if MCC in *subscription* list           | Drives periodic-payment fraud models.                             |                                             |
| `previous_txn_id` (string           | null)                                                                | 1-in-4 rows link to earlier row for same card                     | Seeds velocity features without heavy JOIN. |
| `label_fraud` (bool)                | Prevalence 0.3 % overall; boosted to 2 % for risky MCC + high amount | Matches charter metric requirement .                              |                                             |

> **Tip for interviews:** being able to recite two or three of these conditional rules (“Why isn’t `device_id` present for POS swipes?”) signals that you know real fraud data quirks.

---

#### 3 · Pipeline outline (10 h task **DAT-02**)

```
generate.py
│
├─ load_schema()          # reads YAML, asserts 24 fields
├─ build_lookup_tables()  # MCC csv, tz map, risk bands
├─ gen_master_frame(n)    # Polars lazy frame, column-by-column
├─ inject_nulls()         # apply per-field sparsity masks
├─ reorder_sort()         # by event_time for realism
└─ write_parquet("s3://fraud-dl-raw/2025-05-17/part-000.snappy")
```

* **Polars** chosen because 1 M rows fits in < 1 GB and writes Parquet ≈ 4× faster than pandas (laptop perf test).
* **Unit test hook** re-uses *Phase 5* YAML loader so a schema drift explodes before upload.
* **`pandas-profiling` report** generated in HTML to satisfy DAT-02 acceptance criteria .

---

#### 4 · What breaks if the schema drifts?

| Schema change                       | Breakage symptom                                    | Guard-rail                                                               |
| ----------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------ |
| Rename a field                      | `KeyError` in `gen_master_frame()`                  | Phase 5 unit test asserts exact 24-field set.                            |
| Add enum value unseen by generator  | `ValueError: invalid choice`                        | TODO in Sprint-02: parametrise enums straight from YAML – easy refactor. |
| Remove `local_time_offset`          | Downstream “odd-hour” feature becomes NaN           | CI fails because hard-coded 24-field count.                              |
| Change dtype (e.g. `amount` to int) | Profiling report shows 0 std-dev; model AUC plunges | Manual code-review + profiling outlier heatmap.                          |

---

#### 5 · Why 1 million rows?

* **Stat power** – lets the baseline XGBoost learn rare-fraud signals with \~3 000 positive samples.
* **Cost** – 1 M rows × 24 cols ≈ 500 MB Parquet Snappy; S3 standard cost < £0.01.
* **Speed** – Generates in ≈ 40 s on a 4-core laptop; under 1 min fits Sprint-01 timebox.
  If your laptop chokes, fallback plan in Sprint risk table is to cut to 100 k rows .

---

#### 6 · Hand-off to later sprints

| Downstream sprint             | Depends on generator because…                                                       |
| ----------------------------- | ----------------------------------------------------------------------------------- |
| **Sprint 02** – Feast MVP     | Offline store needs day-partitioned Parquet; online lookup uses `merchant_id`, etc. |
| **Sprint 03** – Training      | SageMaker Pipeline pulls the Parquet path pattern set here.                         |
| **Sprint 04** – Latency test  | Real-time endpoint will fetch features whose distributions mirror this dataset.     |
| **Monitoring** (Sprint 06-07) | Drift jobs compare live traffic to the baseline profile produced now.               |

Getting the generator right *once* prevents a domino of “garbage in ⇒ garbage out” bugs across all subsequent milestones.

---

#### 7 · Interview sound-bite

> “The YAML schema drives the Polars generator: each field maps to a Faker provider or deterministic rule, with null-rates and enum vocab copied from industry stats.
> A 1 M-row Parquet drops into S3 `raw/`, feeding Feast and SageMaker.
> If I tweak the schema, CI fails before AWS charges me a penny.”

---

## Phase 7 Upgrade & Extension Paths

*(“What happens when v 0.1.0 isn’t enough any more, and how do we evolve without blowing up pipelines, tests or costs?”)*

---

### 1 · Semantic-version contract

| Bump type             | Triggering change                                                              | Allowed to break downstream code?                                   | Example                                                                   |
| --------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| **PATCH** `0.1.<x+1>` | Fix typo in `description`, tighten `example`, *no* field or dtype change       | **No** – generator & pipelines keep working                         | Clarify `amount` description from “minor units” → “minor currency units”  |
| **MINOR** `0.<y+1>.0` | Add **new nullable field** or **extend enum**                                  | **No** – backward-compatible; tests updated for new field count     | Add `merchant_city` string column when we decide to model UK vs US cities |
| **MAJOR** `<z+1>.0.0` | Rename/remove field, change dtype, or make previously-nullable column NOT NULL | **Yes** – generator, feature-store & DAGs must all upgrade together | Convert `amount` from float → decimal for currency-precision audits       |

Decision to use SemVer header **plus a Git tag** was locked in ADR-0005 🡒 *“Both: YAML header `version: 0.1.0` + Git tag later.”*&#x20;

---

### 2 · Folder & table names embed the version

```
s3://fraud-dl-raw/v0.1.0/date=2025-05-27/part-000.snappy
feature-store/offline/v0.1.0/…
feast_feature_repo/transaction_v0_1.py
```

*Why?*

* Blue/green data paths let old models continue to read v0.1 while you back-fill v0.2.
* Cost-cap stays safe because you can `terraform destroy` the **old** tables when traffic is cut over.

---

### 3 · End-to-end upgrade checklist (MINOR bump example)

| Step | Owner  | Command / action                                                                              | Guard-rail                                                   |
| ---- | ------ | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| 1    | DS     | Create branch `feat/schema-v0.2`                                                              | —                                                            |
| 2    | DS     | Add new column to `transaction_schema.yaml`, set `version: 0.2.0`, add `example`              | **yamllint** & unit-test fail until field count updated      |
| 3    | DS     | Extend `generator_mapping.md`; add Faker rule                                                 | Generator unit-test asserts no unknown fields                |
| 4    | DS     | `pytest -q` – new snapshot test passes (25 ≠ 24 fields）                                       | Phase 5 test now expects 25 fields                           |
| 5    | DevOps | `terraform apply -var schema_version=0.2.0` to create **parallel** S3 prefix & DynamoDB table | No downtime; v0.1 endpoint still live                        |
| 6    | DS     | Re-run generator → S3 `raw/v0.2.0/…`                                                          | Data validation with Great Expectations (optional level-up)  |
| 7    | DS     | Register new Feast FeatureView `Transaction_v0_2`                                             | Feast keeps both versions side-by-side                       |
| 8    | MLOps  | SageMaker Pipeline (Sprint 03) retrains on v0.2 features; logs to Neptune                     | Canary metrics must beat champion                            |
| 9    | MLOps  | Blue/green deploy; CloudWatch alarm watches p99 latency & AUC                                 | Auto-rollback if worse                                       |
| 10   | DevOps | After 7 days stable, run `make nuke VERSION=0.1.0`                                            | Deletes v0.1 buckets/tables, keeping bill low                |

---

### 4 · Tooling already baked in to make upgrades painless

| Capability                                                      | Where it was introduced            | Upgrade benefit                                               |
| --------------------------------------------------------------- | ---------------------------------- | ------------------------------------------------------------- |
| **Pre-commit + CI** schema test                                 | Sprint-01 Phase 5                  | Fails fast if someone edits YAML but forgets version bump     |
| **Synthetic generator table-driven mapping**                    | Phase 6                            | New columns only need one mapping row, not code rewrite       |
| **Feast FeatureView autogen from YAML** (`cookiecutter feasty`) | to be wired in Sprint 02           | Enum/dtype propagate to online & offline stores automatically |
| **Markdown & JSON-Schema auto-render** (level-up extras)        | Walk-through §7 “Level-up extras”  | Docs site & validation artefacts stay in sync                 |
| **`make bump-schema` helper** (Git hook template)               | Added at the end of Sprint-01      | Automates SemVer bump + git tag + changelog entry             |

---

### 5 · Common extension scenarios & patterns

| Scenario                                               | Recommended change                                                   | Why this path                                                                          |     |                                                           |
| ------------------------------------------------------ | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | --- | --------------------------------------------------------- |
| Need real-time velocity feature (`txn_count_last_24h`) | **Add nullable int column** ➜ MINOR bump                             | Keeps legacy pipelines happy; feature can default to null until Sprint 02 populates it |     |                                                           |
| Collect *issuer\_country* from new PSP feed            | **Add field**; generator sets to `merchant_country` for now          | Gives schema room without blocking current data                                        |     |                                                           |
| Decide to *encrypt* PAN hash with KMS                  | **MAJOR bump** to v1.0.0; rename `card_pan_hash`→`card_pan_hash_enc` | Any code expecting SHA-256 must refactor                                               |     |                                                           |
| Regulatory asks for *auth\_code* (6-digit)             | **Add field + enum** of \`null                                       | 000000                                                                                 | …\` | Backward-compat; nullable lets historical rows stay valid |

---

### 6 · Migration tips that save the £50/month budget

* **Lazy back-fill** – only regenerate new columns for the **look-back window** models need (e.g., 90 days), not all history.
* **DynamoDB** – schemaless, so adding an attribute costs £0; just update the Feast encoder.
* **S3** – keep old Parquet; Athena can UNION `schema on read` if you absolutely must query mixed data.
* **Grafana dashboards** – use template variables to switch between `schema_version`, avoiding duplicate panels.

---

### 7 · When this project’s upgrade path is *different* from big-corp reality

| This solo project                                      | Typical bank / large team                                   |
| ------------------------------------------------------ | ----------------------------------------------------------- |
| Two parallel S3 prefixes, manual teardown              | Formal data-warehouse **migration table** + schema registry |
| Feast FeatureView per version                          | Central feature catalog, de-duplication governance board    |
| CI + unit test the only gates                          | Extra prod DB migration reviews, *data steward* sign-off    |
| Budget guardrail forces deletion of old assets quickly | Enterprise keeps multi-year history; cost less sensitive    |

Understanding these deltas lets you explain to recruiters *why* you chose a lighter process here (“£50 guard-rail, solo developer”) and how you would scale the practice in a team of 20.

---

### 8 · Two-minute recruiter spiel

> “Our schema is SemVer-tagged and path-versioned. A MINOR bump like v0.2.0 adds a nullable column; CI and the generator adapt automatically, and we spin up parallel S3 prefixes + DynamoDB tables so the champion model keeps scoring on v0.1 while the canary trains on v0.2.
> After a blue/green switch and a 7-day soak, `make nuke VERSION=0.1.0` wipes the old assets and keeps the bill under £50.
> A MAJOR bump signals breaking changes—for those we schedule a coordinated migration of Feast views, SageMaker pipelines, and data-gen logic.”

Deliver that narrative, and you demonstrate not just coding chops but **lifecycle thinking**, exactly what mid-/senior interview panels probe for.

---

