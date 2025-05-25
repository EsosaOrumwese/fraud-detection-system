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
mkdir -p config docs/data-dictionary scripts tests/unit

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
yamllint config/transaction_schema.yaml
```

Expect **no output** on success.

### 4.2  Unit test (5 min)

```python
# tests/unit/test_schema_yaml.py
import yaml, pathlib, pytest, re
SCHEMA_PATH = pathlib.Path("config/transaction_schema.yaml")

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

Take your time—high-quality schemas pay off for the rest of the project. 🚀
