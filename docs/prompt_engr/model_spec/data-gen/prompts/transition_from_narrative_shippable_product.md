# Edge-case CFSW
Below are two production‑grade templates—**Edge‑Case Catalogue‑Finder v1** and **Edge‑Case Spec‑Writer v1**—that mirror the rigor of your Hole‑Finder / Fixer pipeline.
They are tuned to force the model to exhaustively enumerate every single edge‑case pathway and then generate laser‑specific recovery clauses, leaving nothing for a brutal reviewer to flag as “hand‑wavy”.

---

## ➊  EDGE‑CASE CATALOGUE‑FINDER v1  (ECC‑F)

```text
##########################################################
#  EDGE‑CASE CATALOGUE‑FINDER • Sub‑segment {{NAME}}     #
##########################################################

ROLE  
You are a senior JP Morgan Site‑Reliability Engineer auditing the pair  
Narrative.txt + Assumptions.txt (plus appendices) for this sub‑segment.

DEFINITION — Edge‑Case Pathway  
Any event that can disrupt determinism, correctness, or reproducibility, including but not limited to  
  1. **Input failures**  – corrupt file, missing artefact, schema drift, wrong CRS.  
  2. **Temporal anomalies** – DST fold/skip, leap second, timezone boundary flips.  
  3. **Resource limits** – OOM, executor lost, thread starvation, disk quota.  
  4. **Random‑seed collisions** – Philox counter overlap, RNG state lost on retry.  
  5. **External dependency** – HTTP 5xx, S3 throttling, licence key expiry.  
  6. **Parameter domain error** – Dirichlet α ≤ 0, variance < 0, division by 0.  
  7. **Race / idempotence** – double catalog build, partial Parquet write, duplicate row keys.  
  8. **Governance gate** – licence mismatch, missing SHA‑256, privacy leak test fail.

OUTPUT WHEN NONE FOUND  
Write exactly `No edge‑cases found.` then `<<EC‑END>>`.

CATALOGUE BLOCK FORMAT  
(No summaries. One block per edge‑case. No bullets. No code.)

--- EC {{ID}} | Stage={{stage_name}} | Severity={{Crit|High|Med|Low}} ---
Failure_event: one‑line description
Anchor: "exact sentence or clause"                        ← quote from source
Current_handled: {{Yes|No|Partial}}
Detection_gap: {{Yes|No}}         ← if Current_handled ≠ Yes, must be Yes
Recovery_gap:  {{Yes|No}}
Idempotence_gap: {{Yes|No}}
Metrics_gap:    {{Yes|No}}
Expected_format: {{units/shape/dtype/valid range}}
Default_policy: {{abort|skip|use prior|other}}
Interface_affected: {{artefact/module/function}}
Test_pathway: {{CI/property/fuzz; how to induce}}
Context: “one sentence before … {{TARGET}} … one after”
Confidence={{HIGH|MEDIUM|LOW}}
--- END EC {{ID}} ---

RULES  
• Scan every section, appendix, table and code snippet.  
• For each candidate failure event, ask: “Is detection logic, recovery action, idempotence note, and monitoring metric **fully** specified?” If any gap flag is Yes → produce a block.  
• Combine duplicates (same stage + same failure_event) by merging anchor quotes.  
• Assign Severity:  
    Crit   = data corruption or privacy breach, fatal stop.  
    High   = reproducibility broken, leads to wrong synthetic data.  
    Med    = performance / quota risk, output still correct.  
    Low    = minor clarity / logging gap.  
• Stop when all text scanned; write `<<EC‑END>>`.

TOKEN MGMT  
If a response nears 6 500 tokens, finish current block, output `<<EC‑CONTINUE>>`,  
then resume in a new message starting `<<EC‑CONTINUATION>>`.  
Never split an EC block.

##########################################################
#  END EDGE‑CASE CATALOGUE‑FINDER                        #
##########################################################
```

---

## ➋  EDGE‑CASE SPEC‑WRITER v1  (ECS‑W)

````text
##########################################################
#  EDGE‑CASE SPEC‑WRITER • Sub‑segment {{NAME}}          #
##########################################################

INPUT  
A JSON array of EC ids to resolve appears **above** this template:

```json
{"ec_ids":[2,5,8]}
```

GOAL
For each listed EC id, write a rock‑solid recovery clause that closes **all** gaps flagged by Catalogue‑Finder.

FIX BLOCK FORMAT
(Strict order; no bullets; no summaries.)

<<<EC‑FIX id={{ID}}>
Stage: {{stage_name}}
Failure_event: {{copied from catalogue}}
Detection:
trigger: deterministic condition or metric
error_code: JP‑M code (numeric)
Recovery:
action: retry | skip | abort
max_retries: n
backoff_sec: n
Idempotence:
guarantee: describe state re‑run effect
Monitoring:
metric_name: prometheus metric
alert_thresh: expression
Expected_format: α ∈ ℝ⁺, len=N, dtype=float64
Default_policy: use prior Dirichlet(ones)
Interface_affected: outlet_alloc.py/alloc_dirichlet()
Test_pathway: fuzz test injects zero vector; assert abort/recovery
<<<END EC‑FIX>>>

COLLECT‑AND‑ORDER RULE
• Buffer all EC‑FIX blocks → sort ascending by id → emit one header:
`##### EDGE‑CASE SPEC.txt #####`, the blocks, then `##### END EDGE‑CASE SPEC #####`.
• If output > 6000 tokens, break **between** blocks and insert
`<<ES‑CONTINUE>>` / `<<ES‑CONTINUATION>>`.

RATIONALITY NOTE
After the spec file, emit one line per id:
`id={{ID}} | Confidence={{HIGH|MEDIUM|LOW}} | Notes=…`
≤ 2 sentences each, no bullets.

END TOKEN
Write `<<ES‑END>>` when done.

##########################################################
# END EDGE‑CASE SPEC‑WRITER
##########################################################
````

---

# Parameter Priors vs. Posteriors CFSW
## ➊  PARAMETER CATALOGUE‑FINDER v1  (PCF)

````text
############################################################
#  PARAMETER CATALOGUE‑FINDER • Sub‑segment {{NAME}}       #
############################################################

ROLE  
You are a Quant at JP Morgan extracting every stochastic parameter, hyper‑parameter, or prior distribution referenced across:
  • Narrative.txt
  • Assumptions.txt  (main body)
  • Appendix A – Mathematical Definitions & Conventions

DEFINITION — Parameter Gap  
A parameter has a gap if **any** of the following fields is missing or ambiguous:
  1. Prior distribution type (e.g., Dirichlet, LogNormal, Gamma)
  2. Prior hyper‑parameters (α, μ, σ, etc.)
  3. Calibration recipe (data path, objective, optimiser, seed, tolerance)
  4. Posterior validation test (metric, acceptance range)
  5. Provenance tag (artefact digest or script SHA‑256)
  6. Units or scale (e.g., USD, log(footfall), per hour)
  7. Default/fallback policy if parameter or artefact missing
  8. Interface consumer (artefact or code module that uses this param)
  9. Short description

OUTPUT WHEN NONE  
Write `No parameter gaps found.` then `<<PP‑END>>`.

CATALOGUE BLOCK FORMAT  
(no bullets, no summaries)

--- PP {{ID}} ---
Name: {{plain_english_name}}
Symbol: {{math_symbol}}
Scope: {{merchant_location | arrival_engine | fraud_cascade | validation}}
Prior_type: {{Dirichlet | LogNormal | ... | Unknown}}
Prior_specified: {{Yes|No|Partial}}
Calibration_recipe: {{Yes|No}}
Posterior_validation: {{Yes|No}}
Provenance_tag: {{Yes|No}}
Units: {{unit or dimensionless or Unknown}}
Default_policy: {{abort | impute | use prior | other}}
Interface_consumer: {{artefact/code consuming this parameter}}
Description: {{one sentence in plain English}}
Anchor: "exact sentence or clause"             ← quote from source
Context: “one sentence before … {{TARGET}} … one after”
Gap_flags:
  prior_missing={{Y|N}}
  hyperparams_missing={{Y|N}}
  calibration_missing={{Y|N}}
  posterior_missing={{Y|N}}
  provenance_missing={{Y|N}}
  units_missing={{Y|N}}
  default_policy_missing={{Y|N}}
  interface_consumer_missing={{Y|N}}
  description_missing={{Y|N}}
Confidence={{HIGH|MEDIUM|LOW}}
--- END PP {{ID}} ---

RULES  
• Scan inline math (`$…$`) and Appendix A tables; extract every Greek or variable followed by distribution verbs (“~”, “drawn”, “sample”, “prior”, “posterior”).  
• If a parameter appears multiple times, merge into one block and OR‑together gap flags.  
• Severity = High if any of calibration_missing OR posterior_missing OR prior_missing = Y; else Medium if hyperparams_missing or provenance_missing = Y; else Low.  
• Stop when done; write `<<PP‑END>>`.

TOKEN SPLIT  
At ~6 500 tokens, close current PP block, output `<<PP‑CONTINUE>>`, then resume in `<<PP‑CONTINUATION>>`.

############################################################
#  END PARAMETER CATALOGUE‑FINDER                          #
############################################################
````

---

## ➋  PARAMETER SPEC‑WRITER v1  (PSW)

````text
############################################################
#  PARAMETER SPEC‑WRITER • Sub‑segment {{NAME}}            #
############################################################

INPUT  
A JSON array of parameter ids to resolve appears *above* this template:

```json
{"pp_ids":[2,7,11]}
```

GOAL
For each pp_id, fill every gap flagged by PCF and emit a deterministic spec block.

SPEC BLOCK FORMAT (no bullets)

<<<PP‑FIX id={{ID}}>
Name: {{plain_english_name}}
Symbol: {{math_symbol}}
Scope: {{scope_from_catalogue}}
---------------------------------


PRIOR:
type: {{Dirichlet|LogNormal|...}}
hyperparameters:
{{key1}}: {{value}}
{{key2}}: {{value}}
units: {{unit or dimensionless}}
default_policy: {{abort | impute | use prior | other}}
justification: one concise sentence
CALIBRATION_RECIPE:
input_path: s3://bucket/path/TBD
objective: {{e.g., MLE, KL divergence}}
algorithm: {{Nelder‑Mead | L‑BFGS | HMC}}
random_seed: 42
convergence_tol: 1e-6
script_digest: sha256:{{64‑hex}}
INTERFACE_CONSUMER:
artefact_name: {{file, module, or script}}
function: {{class/function consuming param}}
description: {{one sentence on interface link}}
POSTERIOR_VALIDATION:
metric: {{e.g., KS distance, over‑dispersion Δ}}
acceptance_range: [min, max]
sample_size: {{n}}
PROVENANCE_TAG:
artefact_name: {{file_or_script}}
sha256: {{64‑hex}}
SHORT_DESCRIPTION:
{{one‑sentence, plain‑English description}}
TEST_PATHWAY:
test: {{property-based, CI, or script}}
input: {{synthetic or real data}}
assert: {{acceptance condition}}
Confidence={{HIGH|MEDIUM|LOW}}
<<<END PP‑FIX>>>

COLLECT‑AND‑ORDER RULE
• Buffer all PP‑FIX blocks → sort ascending by id.
• Emit one header `##### PARAMETER_SPEC.txt #####`, the blocks, then `##### END PARAMETER_SPEC #####`.
• If output > 6 000 tokens, split between blocks with `<<PS‑CONTINUE>>` / `<<PS‑CONTINUATION>>`.

RATIONALE FOOTER
After the spec, output one line per id:<br>
`id={{ID}} | gaps_closed={{prior|calib|post|prov}} | notes=…` (≤ 20 words)

END TOKEN
Write `<<PS‑END>>` when finished.

############################################################
# END PARAMETER SPEC‑WRITER
############################################################
````
---

# Interface Contract CFSW
## ➊  INTERFACE CONTRACT CATALOGUE‑FINDER v1  (IC‑F)

````text
######################################################################
#  INTERFACE CONTRACT CATALOGUE‑FINDER • Sub‑segment {{NAME}}        #
######################################################################

ROLE  
You are a JP Morgan Data‑Engineering Architect cataloguing every pipeline stage, artefact, and schema reference across:
  • Narrative.txt
  • Assumptions.txt
  • Appendices (Mathematics, Artefact Registry)

DEFINITION — Interface Gap  
A stage or artefact has an interface gap if **any** of the following is missing or ambiguous:  
  1. Input artefact name or digest  
  2. Input schema (column names, dtypes, nullability)  
  3. Output artefact name or digest  
  4. Output schema  
  5. Partitioning & ordering rules  
  6. Success metric (row count, checksum)  
  7. Error codes & retry policy

OUTPUT WHEN NONE  
Write `No interface gaps found.` then `<<IC‑END>>`.

CATALOGUE BLOCK FORMAT (strict, no bullets)

--- IC {{ID}} ---
Stage: {{stage_name}}
Anchor: "exact sentence or clause"
Input_artefact: {{name|Missing}}
Input_schema: {{Yes|Partial|No}}
Output_artefact: {{name|Missing}}
Output_schema: {{Yes|Partial|No}}
Partitioning_rule: {{Yes|No}}
Success_metric: {{Yes|No}}
Error_code_policy: {{Yes|No}}
Schema_version: {{semver or hash or Missing}}
Access_policy: {{read_policy|write_policy|Missing}}
Consumed_by: {{module/function/ETL_stage|Missing}}
Test_pathway: {{property-based|schema-fuzz|integration|Missing}}
Gap_flags:
  input_missing={{Y|N}}
  input_schema_missing={{Y|N}}
  output_missing={{Y|N}}
  output_schema_missing={{Y|N}}
  partition_missing={{Y|N}}
  metric_missing={{Y|N}}
  error_policy_missing={{Y|N}}
  schema_version_missing={{Y|N}}
  access_policy_missing={{Y|N}}
  consumed_by_missing={{Y|N}}
  test_pathway_missing={{Y|N}}
Severity={{Crit|High|Med|Low}}
Context: “… previous sentence … {{TARGET}} … next sentence …”
Confidence={{HIGH|MEDIUM|LOW}}
--- END IC {{ID}} ---

RULES  
• “Stage” = any named transform, job, or script (e.g. *LoadSpatialPriors*, *BuildOutletCatalogue*).  
• Use regex `(?i)^(load|build|derive|route|validate|write).+` to catch verbs.  
• Severity = High if any of input/output artefact OR schema missing; Crit if both sides missing.  
• Combine duplicates (same stage) by OR‑ing gap flags.  
• Output blocks ordered by first appearance.  
• Stop when done, write `<<IC‑END>>`.

TOKEN SPLIT  
If nearing 6500 tokens, finish current block, write `<<IC‑CONTINUE>>`, resume in `<<IC‑CONTINUATION>>`.

######################################################################
#  END INTERFACE CONTRACT CATALOGUE‑FINDER                           #
######################################################################
````

---

## ➋  INTERFACE CONTRACT SPEC‑WRITER v1  (IC‑S)

````text
######################################################################
#  INTERFACE CONTRACT SPEC‑WRITER • Sub‑segment {{NAME}}            #
######################################################################

INPUT  
A JSON array of interface‑contract ids to resolve appears *above* this template:

```json
{"ic_ids":[4,7,12]}
```

GOAL
For each ic_id, generate a deterministic contract that closes **all** gap flags.

SPEC BLOCK FORMAT  (no bullets)

<<<IC‑FIX id={{ID}}>
Stage: {{stage_name}}
INPUT_ARTEFACT:
name: {{artefact_name}}
path_pattern: s3://bucket/path/TBD
sha256: {{64‑hex}}
schema: |
{
"name": "{{artefact_name}}",
"type": "record",
"fields": [
{"name":"col1","type":"string","nullable":false},
...
]
}
OUTPUT_ARTEFACT:
name: {{output_name}}
path_pattern: s3://bucket/path/TBD
sha256: {{64‑hex}}          # placeholder if not yet built
schema: |
{ … JSON schema … }
PARTITIONING:
keys: ["tzid","event_date"]
order_by: ["event_date","site_id"]
SUCCESS_METRIC:
metric_name: row_count
expected_range: [1000000, 2000000]
ERROR_POLICY:
error_code: 1203
retry_max: 3
retry_backoff_sec: 60
idempotent: true
SCHEMA_VERSION:
version: {{semver or hash}}
ACCESS_POLICY:
read_policy: {{string}}
write_policy: {{string}}
CONSUMED_BY:
module: {{name}}
function: {{name}}
description: {{one line purpose}}
TEST_PATHWAY:
test_type: {{property-based|integration|fuzz}}
tool: {{avro|pytest|custom}}
script: {{path or url}}
assertion: {{pass/fail condition}}
Confidence={{HIGH|MEDIUM|LOW}}
<<<END IC‑FIX>>>

COLLECT‑AND‑ORDER RULE
• Buffer all IC‑FIX blocks → sort ascending by id.
• Emit header `##### INTERFACE_CONTRACT_SPEC.txt #####`, then blocks, then `##### END INTERFACE_CONTRACT SPEC #####`.
• If file > 6000 tokens, insert `<<IS‑CONTINUE>>` / `<<IS‑CONTINUATION>>` between blocks.

RATIONALE FOOTER
After spec, output one line per id:
`id={{ID}} | gaps_closed={{input|output|schema|metric|error}} | notes=…` (≤ 20 words)

END TOKEN
Write `<<IS‑END>>` when finished.

######################################################################
# END INTERFACE CONTRACT SPEC‑WRITER
######################################################################
````
---

# TEMPORAL VERSION MATRIX FINDER and SPEC WRITER
## ➊  TEMPORAL VERSION MATRIX FINDER v1  (TVM‑F)

```text
######################################################################
#  TEMPORAL VERSION MATRIX FINDER • Sub‑segment {{NAME}}             #
######################################################################

ROLE  
You are a Release‑Management Engineer extracting every artefact that carries a
vintage, semantic version, or release tag across:
  • Narrative.txt
  • Assumptions.txt
  • Appendix B – Governing Artefact Registry

DEFINITION — Version‑Matrix Gap  
An artefact has a gap if any of these fields is missing or ambiguous:  
  1. Vintage / version tag (e.g., 2025‑04‑15, v2.1.0, IANA‑2024a)  
  2. Valid_from / valid_to window  
  3. Update cadence (daily, monthly, “never”)  
  4. Compatibility list with *all* other versioned artefacts  
  5. SHA‑256 digest or signed manifest

OUTPUT WHEN NONE  
Write `No version gaps found.` then `<<TV‑END>>`.

CATALOGUE BLOCK FORMAT  (no bullets)

--- TV {{ID}} ---
Artefact: {{artefact_name}}
Type: {{raster | vector | csv | parquet | code | container}}
Anchor: "exact sentence or clause"
Version_tag: {{tag_or_Missing}}
Valid_window: {{[start,end]|Missing}}
Update_cadence: {{daily|monthly|annual|never|Missing}}
Digest_present: {{Yes|No}}
Compatibility_matrix: {{Yes|Partial|No}}
Gap_flags:
  tag_missing={{Y|N}}
  window_missing={{Y|N}}
  cadence_missing={{Y|N}}
  digest_missing={{Y|N}}
  compat_missing={{Y|N}}
Severity={{High|Med|Low}}
Context: “prev … {{TARGET}} … next”
Confidence={{HIGH|MEDIUM|LOW}}
--- END TV {{ID}} ---

RULES  
• Match artefact names via Appendix B table and inline mentions (`s3://`, `.yaml`, `tz_world`).  
• If any Gap flag = Y → emit a block.  
• Severity: High if tag_missing OR compat_missing; Medium for window/cadence/digest gaps; Low otherwise.  
• Merge duplicates (same artefact) by OR‑ing flags.  
• Stop when done; write `<<TV‑END>>`.

TOKEN SPLIT  
At ~6500 tokens, close block, write `<<TV‑CONTINUE>>`, resume in `<<TV‑CONTINUATION>>`.

######################################################################
#  END TEMPORAL VERSION MATRIX FINDER                                #
######################################################################
```

---

## ➋  TEMPORAL VERSION MATRIX SPEC‑WRITER v1  (TVM‑S)

````text
######################################################################
#  TEMPORAL VERSION MATRIX SPEC‑WRITER • Sub‑segment {{NAME}}        #
######################################################################

INPUT  
A JSON array of version‑gap ids appears *above* this template:

```json
{"tv_ids":[1,4,9]}
```

GOAL
For each tv_id, provide a concrete matrix entry that closes **all** gap flags.

SPEC BLOCK FORMAT (TOML, deterministic; no bullets)

<<<TV‑FIX id={{ID}}>>>
[{{artefact_name}}]
type = "{{raster|vector|csv|parquet|code|container}}"
version_tag = "{{tag}}"
valid_from = "YYYY‑MM‑DD"
valid_to = "YYYY‑MM‑DD"          # use "9999‑12‑31" if perpetual
update_cadence = "{{daily|monthly|annual|never}}"
sha256 = "{{64‑hex}}"
compatible_with = ["gdp_2025‑04‑15", "tz_world_2024a"]
notes = "{{one‑line justification}}"
<<<END TV‑FIX>>>

COLLECT‑AND‑ORDER RULE
• Buffer all TV‑FIX blocks → sort ascending by id.
• Emit header `##### VERSION_MATRIX.toml #####`, blocks, then `##### END VERSION_MATRIX #####`.
• If file > 6000 tokens, split between blocks with `<<VM‑CONTINUE>>` / `<<VM‑CONTINUATION>>`.

RATIONALE FOOTER
After matrix, one line per id:
`id={{ID}} | gaps_closed={{tag|window|cadence|digest|compat}} | notes=…` (≤ 20 words)

END TOKEN
Write `<<VM‑END>>` when finished.

######################################################################
# END TEMPORAL VERSION MATRIX SPEC‑WRITER
######################################################################
````

# BUILD‑REPRODUCIBILITY CATALOGUE FINDER + SPEC WRITER
## ➊  BUILD‑REPRO CATALOGUE‑FINDER v1  (BR‑F)

```text
######################################################################
#  BUILD‑REPRO CATALOGUE‑FINDER • Sub‑segment {{NAME}}               #
######################################################################

ROLE  
You are a DevOps auditor extracting every reproducibility artefact across:
  • Narrative.txt
  • Assumptions.txt
  • Any `Dockerfile`, `pyproject.toml`, `requirements.txt` snippets in appendices

DEFINITION — Repro Gap  
An item has a gap if any of these fields is missing or ambiguous:  
  1. Container/base image name **and** immutable digest (sha256:…)  
  2. Source‑code commit hash (Git SHA or tarball digest)  
  3. Dependency lockfile (pip‑hash or Conda lock) with complete hashes  
  4. Build script digest (`build_pipeline_dag.py`, Makefile, Nix flake)  
  5. CI pipeline manifest (GitHub Actions, Jenkinsfile) pinned to digest/sha  
  6. Global deterministic seed + RNG library version  
  7. Output manifest checksum (e.g., XOR of artefact SHA‑256s)

OUTPUT WHEN NONE  
`No build‑repro gaps found.` then `<<BR‑END>>`.

CATALOGUE BLOCK FORMAT

--- BR {{ID}} ---
Artefact: {{container|code_repo|lockfile|build_script|ci_pipeline|seed|manifest}}
Name_or_path: {{value}}
Anchor: "exact sentence or clause"
Digest_present: {{Yes|No}}
Version_pin: {{Yes|No}}              # tag or commit
Lockfile_complete: {{Yes|No|n/a}}
Build_manifest: {{Yes|No|n/a}}
Env_vars_present: {{Yes|No|n/a}}
Compiler_version_present: {{Yes|No|n/a}}
OS_release_present: {{Yes|No|n/a}}
Source_tarball_digest: {{sha256:...|n/a}}
Repro_instructions_present: {{Yes|No|n/a}}
Gap_flags:
  digest_missing={{Y|N}}
  version_missing={{Y|N}}
  lock_missing={{Y|N}}
  manifest_missing={{Y|N}}
  env_missing={{Y|N}}
  compiler_missing={{Y|N}}
  os_missing={{Y|N}}
  tarball_missing={{Y|N}}
  repro_instructions_missing={{Y|N}}
Severity={{Crit|High|Med|Low}}
Context: “prev … {{TARGET}} … next”
Confidence={{HIGH|MEDIUM|LOW}}
--- END BR {{ID}} ---

RULES  
• For containers look for `FROM`, `image:` or `.docker.io/…@sha256:`.  
• For code repo pin, look for `git_sha=` or commit links.  
• Severity: Crit if digest_missing; High if version_missing or lock_missing; Med otherwise.  
• Merge duplicates by OR‑ing flags.  
• Stop then write `<<BR‑END>>`.

TOKEN SPLIT  
At ~6500 tokens output `<<BR‑CONTINUE>>` / `<<BR‑CONTINUATION>>`.

######################################################################
#  END BUILD‑REPRO CATALOGUE‑FINDER                                  #
######################################################################
```

---

## ➋  BUILD‑REPRO SPEC‑WRITER v1  (BR‑S)

````text
######################################################################
#  BUILD‑REPRO SPEC‑WRITER • Sub‑segment {{NAME}}                    #
######################################################################

INPUT  
JSON array of gaps to fix appears above:

```json
{"br_ids":[3,6,9]}
```

GOAL
For each br_id close **all** gap flags with immutable pins.

SPEC BLOCK FORMAT (no bullets)

<<<BR‑FIX id={{ID}}>
Artefact: {{type}}
Name_or_path: {{value}}
Digest: sha256:{{64‑hex}}
Version_pin: {{tag_or_commit}}
Lockfile:
file: {{path/to/lockfile}}
sha256: {{64‑hex}}
Build_script:
file: {{build.sh|dag.py}}
sha256: {{64‑hex}}
CI_pipeline:
file: .github/workflows/TBD
sha256: {{64‑hex}}
Determinism:
global_seed: 42
rng_library: Philox‑2^128, v{{ver}}
Output_manifest:
algorithm: SHA‑256 XOR
file: build_manifest.txt
sha256: {{64‑hex}}
Env_vars:
LANG: "C.UTF-8"
LC_ALL: "C.UTF-8"
TZ: "UTC"
Compiler_version:
gcc: "TBD"
python: "TBD"
numpy: "TBD"
OS_release:
name: "TBD"
version: "TBD"
Source_tarball:
url: "s3://bucket/path/TBD"
sha256: "sha256:PLACEHOLDER"
Repro_instructions:
docker_run: "docker run ... "
nix_shell: "nix-shell ... "
Confidence={{HIGH|MEDIUM|LOW}}
<<<END BR‑FIX>>>
Confidence={{HIGH|MEDIUM|LOW}}
<<<END BR‑FIX>>>

COLLECT‑AND‑ORDER RULE
• Sort BR‑FIX blocks ascending by id.
• Header `##### BUILD_REPRO_SPEC.txt #####`, blocks, footer `##### END BUILD_REPRO_SPEC #####`.
• If > 6000 tokens, split between blocks with `<<BS‑CONTINUE>>` / `<<BS‑CONTINUATION>>`.

RATIONALE FOOTER
`id={{ID}} | gaps_closed={{digest|version|lock|manifest}} | notes=…`

END TOKEN
`<<BS‑END>>`

######################################################################
# END BUILD‑REPRO SPEC‑WRITER
######################################################################
````
