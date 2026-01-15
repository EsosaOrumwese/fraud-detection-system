black-box framing:
{
""""
Through a hierarchical modular lens, the **Model Factory** is the **offline build pipeline** that turns replayable data + labels into **versioned, evaluable model/policy bundles** ready to be registered and deployed.

## Level 0 — Black-box view

**Inputs**

* **Training datasets** (from replay + offline features + labels) or dataset refs/manifests
* **Training configuration** (model family, hyperparams, feature group versions, splits, objectives)
* **Governance constraints** (what data/time windows are allowed, leakage rules, approval gates)

**Outputs**

* A **Model Bundle** (artifact pack) including:

  * model weights / policy config
  * feature schema expectations (which FeatureGroups/versions)
  * training metadata (data manifests, time windows, metrics)
  * reproducibility anchors (hashes/digests, code/version refs)
* **Evaluation reports** (metrics, slices, drift checks, fairness checks if you include them)
* **Promotion artifacts** (shadow/canary/ramp readiness signals) to feed the Registry/rollout process

One sentence: **“Produce a reproducible model bundle + evidence that it meets quality gates.”**

---

## Level 1 — Minimal responsibility chunks (v0-thin)

These are *facets* you can spec without committing to a particular ML stack.

1. **Run Orchestration & Run Ledger (Training Run)**

* Defines a training run identity (`train_run_id`)
* Captures configs, inputs, outputs, status, and timestamps (append-only record)

2. **Dataset Intake**

* Accepts dataset manifests/refs (not raw files)
* Validates schema/version compatibility at a high level
* Pins exactly what data was used (for reproducibility)

3. **Feature/Label Join Policy (Leakage discipline)**

* Defines as-of semantics and prevents peeking into the future
* Ensures labels are joined by observed_time rules (from Label Store)
* Ensures features come from OFS reconstruction aligned to as-of

4. **Training & Evaluation Engine**

* Trains the model/policy
* Evaluates against held-out splits and slice metrics
* Produces metrics + artifacts

5. **Quality Gates**

* Defines pass/fail criteria for promotion to registry (metrics thresholds, stability checks)
* Outputs a gate receipt (PASS/FAIL + reasons)

6. **Bundle Packaging**

* Produces a versioned **ModelBundle** with:

  * model artifact(s)
  * required feature group versions and schema expectations
  * training data manifests and digests
  * evaluation report refs

7. **Export/Publish to Registry**

* Emits a “bundle ready” artifact or event that the Model/Policy Registry can ingest

---

## Level 2 — Boundaries with other components

* **Consumes:** dataset manifests (from offline feature plane + labels/cases), governance constraints, and maybe Decision Log slices.
* **Produces:** model bundle + evaluation + gate receipts for **Model/Policy Registry**.
* **Does not:** deploy directly; registry/rollout controls that.

---

## Cross-cutting “laws” (what must be tight)

* **Reproducibility:** every training run is reconstructable (inputs pinned by refs+digests).
* **Leakage control:** explicit as-of joins; no future data in training features/labels.
* **Immutability:** run records and produced bundles are append-only/immutable.
* **Compatibility:** bundle declares its required feature schema/version set.
* **Promotion gates:** “ready for deployment” is evidence-based, not manual guesswork.
""""
}


tighten vs loose split
{
""""
Here’s the **v0-thin “tighten vs stay loose”** for the **Model Factory**.

## What needs tightening (pin this)

### 1) Authority boundaries

* Model Factory is authoritative for: **training runs, evaluation evidence, and producing model bundles**.
* It is not authoritative for: online decisioning, label truth, feature definitions (it consumes pinned versions).

### 2) Training run identity + ledger artifacts (reproducibility core)

Pin:

* `train_run_id` and what defines “same run” vs new run
* append-only run record (config, inputs, outputs, status)
* required provenance fields (who triggered, when, which code/config version)

### 3) Input contracts: dataset and config are by-ref and versioned

Pin:

* Training dataset comes in as a **DatasetManifest ref** (not raw data)
* Required fields: schema_version, partitions, digests, time window, join keys, ContextPins posture if applicable
* Training config must record: model family, hyperparams, feature group versions, label family/values, split policy

### 4) Leakage / as-of join policy (non-negotiable)

Pin the rule that training uses:

* labels **as-of observed_time** (no future truth)
* features reconstructed **as-of** the same cut (OFS semantics)
* explicit time windows for train/val/test (no ambiguous “latest”)

### 5) Model bundle contract (what gets produced)

Pin minimum bundle contents:

* artifact refs (weights/policy)
* feature schema expectations: FeatureGroups + versions
* training data manifests refs + digests
* evaluation report ref
* run identity + config hash
* bundle version and compatibility fields

### 6) Evaluation outputs + metrics schema (minimum)

Pin:

* required metrics set (v0 small: ROC-AUC/PR-AUC, precision/recall at thresholds, calibration, latency proxy if needed)
* slice metrics posture (optional)
* deterministic report structure (so registry can parse it)

### 7) Quality gates and receipts (pass/fail evidence)

Pin:

* gate receipt object: PASS/FAIL, thresholds, metrics observed, reasons
* rule that only PASS bundles are eligible for promotion (registry enforces)

### 8) Publishing interface to Model/Policy Registry

Pin:

* what MF emits: `ModelBundle` + `GateReceipt` (+ metadata)
* idempotency on publish (same train_run_id + bundle_id shouldn’t re-register duplicates)

### 9) Privacy / governance posture

Pin:

* no raw PII in bundles/reports; by-ref only
* access control posture: who can trigger training, who can read artifacts

---

## What can stay loose (implementation freedom)

* ML framework (sklearn, XGBoost, PyTorch, etc.)
* Training infrastructure (local, batch, managed ML)
* Hyperparam tuning strategy
* Exact metric computation library
* Artifact storage backend
* Orchestration engine (Dagster/Airflow/custom)
* Model explainability tooling (optional v0)

---

### One-line v0 contract for Model Factory

**“Model Factory produces reproducible model bundles from versioned dataset manifests under strict as-of leakage rules, emits evaluation reports and gate receipts, and publishes PASS bundles to the Registry.”**

""""
}


proposed doc plan + contract pack + repo layout
{
""""
Here’s the **Model Factory v0-thin package**: **MF docs + 1 contracts file + file tree** under `docs\model_spec\learning_and_evolution\`.

(I’m keeping it **3 docs** to avoid the “forced 5-pack” overhead.)

---

## MF v0-thin doc set (3 docs)

### **MF1 — Charter, Boundaries, and Run Ledger**

* Purpose: produce reproducible model bundles + evaluation evidence
* Authority boundaries (what MF owns vs consumes)
* Training run identity (`train_run_id`) + append-only run ledger posture
* Non-goals (no deployment; registry handles rollout)

### **MF2 — Inputs, Leakage Policy, Training/Eval Semantics**

* Input contracts (by-ref):

  * `DatasetManifest` refs (schema/version/digests/time windows)
  * `TrainingConfig` (model family, hyperparams, feature group versions, label selection)
* Leakage/as-of rules (labels by observed_time; features as-of same cut; explicit splits)
* Minimal evaluation outputs required (metrics set + report structure posture)

### **MF3 — Model Bundle, Quality Gates, Publish to Registry, Ops & Acceptance**

* `ModelBundle` minimum contents (artifact refs, feature schema expectations, input manifests, config hash, metrics refs)
* Gate receipt (PASS/FAIL + reasons)
* Publish interface to Registry + idempotency rules
* Privacy/governance posture (no raw sensitive data)
* Acceptance scenarios (reproducibility, leakage-safe joins, gate enforcement, publish idempotency)

---

## 1 contracts file (v0)

### `contracts/mf_public_contracts_v0.schema.json`

Recommended `$defs`:

* `TrainRunId` (string format rule)
* `TrainingRunRecord`

  * required: `train_run_id`, `status`, `created_at_utc`, `config_ref_or_hash`, `input_dataset_manifests[]`, `outputs[]`
* `DatasetManifestRef` *(opaque ref + digest)*
* `TrainingConfig` *(thin, by-ref allowed)*

  * required: `model_family`, `feature_group_versions[]`, `label_family`, `split_policy`
  * optional: `hyperparams{}`, `thresholds{}`, `notes`
* `LeakagePolicy` *(thin)*

  * required: `label_as_of_basis`, `feature_as_of_basis`, `train_window`, `eval_windows[]`
* `MetricSet` *(thin; map or list of named metrics)*
* `EvaluationReportRef` *(opaque ref + digest)*
* `GateReceipt`

  * required: `train_run_id`, `gate_status` (PASS/FAIL), `criteria`, `observed_metrics`, `emitted_at_utc`
* `ModelBundle`

  * required: `bundle_id`, `bundle_version`, `train_run_id`, `artifact_refs[]`, `feature_group_versions[]`, `input_dataset_manifests[]`, `evaluation_report_ref`, `gate_receipt_ref_or_embed`
* `PublishBundleRequest/Response` *(optional thin boundary)*
* `ErrorResponse` (thin)

**v0 note:** keep artifact refs opaque; don’t lock storage tech.

---

## File tree (Model Factory)

```text
docs/
└─ model_spec/
   └─ learning_and_evolution/
      └─ model_factory/
         ├─ README.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ MF1_charter_boundaries_run_ledger.md
         │  ├─ MF2_inputs_leakage_policy_training_eval.md
         │  └─ MF3_model_bundle_quality_gates_publish_ops_acceptance.md
         │
         └─ contracts/
            └─ mf_public_contracts_v0.schema.json
```
""""
}
