# Learning + Evolution Plane Pre-design Decisions (Open to adjustment where necessary)
_As of 2026-02-06_

Your Learning + Evolution narrative *makes sense* end-to-end and it stays faithful to the upstream “pinned truth / no drift” discipline. The remaining designer work is basically: **make the offline loop unambiguous** about (a) *what data is allowed*, (b) *what time it is “as-of”*, (c) *how evaluation avoids leakage*, and (d) *how bundles are activated deterministically*.

Here are the questions I’d want settled so planning/implementation is ironed out.

---

## P0 — Must settle before you plan/build

### 1) What exactly is the **replay basis** (and what’s the authority)?

* Is replay anchored to **origin_offset ranges** per topic/partition (preferred), or time windows “translated” to offsets?
* When both EB and Archive exist, is **Archive the default truth** and EB only an accelerator?
* Do we require partition-ordered replay strictly, and how do we encode that in the manifest?

Detailed answers (pinned defaults, based on current posture):
- Replay basis is defined as **origin_offset ranges per topic/partition**. This is the authoritative basis for reproducibility.
- Time windows are allowed only as **selectors** that are translated to offset ranges at build time; the resulting offsets are recorded in the DatasetManifest.
- Archive is the durable truth beyond EB retention; EB may be used as an accelerator only when the same offset ranges are available.
- Partition-ordered replay is required; manifests record topic, partition, start_offset, end_offset for every stream included.
- If EB and Archive disagree over the same offset range, OFS fails closed and emits an anomaly report (no dataset produced).

### 2) What is the **dataset identity tuple** (DatasetFingerprint law)?

* What exact fields go into the DatasetFingerprint?
  (replay_basis + label_asof + feature_def_set + join_scope + filters + code/config revs)
* If *any* of those change, do we guarantee a **new fingerprint + new manifest** (never mutate)?

Detailed answers (pinned defaults, based on current posture):
- DatasetFingerprint includes at minimum: replay basis (topic/partition offsets), label_asof_utc + label_resolution_rule_id, join scope (subject key + join sources), feature_def_set versions, filters/cohort rules, and OFS build profile/config revision.
- Any change to any identity field yields a **new fingerprint and new DatasetManifest**; manifests are immutable and never mutated.

### 3) What is the **label cut rule** (anti-leakage) and label completeness policy?

* Is the rule exactly: **use labels with `observed_time <= label_asof_utc`**, always?
* What do we do about “unknown yet” negatives?
  (censor, treat as unlabeled, or allow weak negatives only with explicit policy)
* Are we training on **resolved labels** (per precedence) or raw assertion timelines?

Detailed answers (pinned defaults, based on current posture):
- Label eligibility rule is **observed_time <= label_asof_utc** (always).
- "Unknown yet" negatives are treated as **unlabeled/censored** by default. Weak negatives are allowed only with an explicit maturity window policy recorded in the manifest.
- v0 training uses **resolved labels** (per precedence rules); raw timelines remain for audit/alternate eval only.
- Label coverage is recorded in the manifest. For training-intent builds, insufficient coverage fails closed; incomplete datasets are allowed only when explicitly tagged as non-training.

### 4) What is the **join/entity scope** for OFS datasets?

* What is the primary training subject key (transaction-level via `event_id`, flow-level, account-level)?
* Which joins are allowed: context frames + FlowBinding + graph projection + OFP features?
* What’s the explicit rule for missing context during offline reconstruction (drop / label as degraded / synth defaults)?

Detailed answers (pinned defaults, based on current posture):
- Primary subject key is `(platform_run_id, event_id)` to align with LabelSubjectKey and prevent cross-run leakage.
- Allowed joins are Context JoinFrames (arrival events/entities + flow anchor), FlowBinding, and IEG projection **only if** built from the same replay basis; static world context is allowed only via SR `run_facts_view` with PASS evidence.
- Missing context defaults to **drop the example** for training; manifest records drop counts and reasons. A degraded cohort is allowed only if explicitly pinned and consistent with online degrade behavior.

### 5) Feature definition authority + parity contract

* Where do feature definitions live (single authority shared with OFP), and how are versions pinned?
* What does “parity” mean in v0:
  matching feature values exactly, or matching within tolerances, or matching hashes?
* What evidence artifact is emitted on mismatch, and does it fail the build or just warn?

Detailed answers (pinned defaults, based on current posture):
- Feature definitions are owned by a **single shared authority** (the same source OFP uses). OFS and MF consume version-locked feature definition sets by ref; “latest” is allowed only if explicitly requested and recorded.
- v0 parity posture: compare **feature snapshot hashes** and a minimal set of key feature values; exact value parity is required for deterministic features, tolerances allowed only where definitions explicitly declare numeric tolerance.
- Parity results emit a **parity evidence artifact** (MATCH/MISMATCH/UNCHECKABLE + refs + basis). For training builds, mismatches are warnings by default; for parity rebuild intents, mismatches fail the run unless explicitly overridden.

### 6) Evaluation harness: what is “PASS” and how is backtesting defined?

* What is the evaluation unit: per-event, per-flow, per-account?
* What splits are allowed (time-based split anchored to replay basis vs random)?
* What metrics are mandatory for PASS (even if minimal in v0), and what are the gates:

  * compatibility gates (schema/features)
  * leakage gates (label_asof discipline)
  * performance gates (thresholded metrics)
* Do we require storing a full **EvalReport** that is reproducible from the manifest?

Detailed answers (pinned defaults, based on current posture):
- Evaluation unit defaults to **per-event** for v0 (aligned to `(platform_run_id, event_id)`); other units (per-flow/per-account) must be explicit in the manifest.
- Splits are **time-based** and anchored to the replay basis; random splits are allowed only if the sampling seed + rule are recorded in the manifest.
- PASS gates include: compatibility (feature/schema), leakage (label_asof discipline), and minimum performance thresholds (explicit metrics + thresholds per bundle slot).
- A full **EvalReport** is required and must be reproducible from the DatasetManifest + training config refs; MF writes it as immutable evidence.

### 7) Bundle contents + compatibility checks

* What must a bundle contain (model artifact + feature schema/version + thresholds/policy + required pins + provenance)?
* What does MPR check for compatibility (feature_def_set match, degrade capability mask, schema versions)?
* What is the bundle’s identity/fingerprint and immutability rule?

Detailed answers (pinned defaults, based on current posture):
- Bundle must include: model artifact(s), feature schema/version requirements, thresholds/policy config, required capabilities, and full provenance (training manifests + eval evidence refs).
- MPR compatibility checks at resolve time include: feature_def_set match, required capabilities vs degrade mask, and input contract version match; incompatible bundles fail closed.
- Bundle identity is immutable: `bundle_id + version` is the unit of truth; any change to artifacts or compatibility metadata requires a new version.

### 8) Activation scope & resolution (MPR contract)

* What are the v0 scope dimensions for “ACTIVE”?
  (mode + environment, maybe scenario constraints)
* What is the deterministic resolution path DF uses (and what happens if no compatible ACTIVE exists)?
* What are rollback semantics and audit events (promote/rollback must be explicit and append-only)?

Detailed answers (pinned defaults, based on current posture):
- v0 ScopeKey = `{ environment, bundle_slot, tenant_id? }` (tenant_id optional); exactly one ACTIVE per scope.
- DF resolves deterministically via MPR; if no compatible ACTIVE exists, resolution fails closed or routes only to an explicitly defined safe fallback, and the decision record must capture the failure.
- Promotions/rollbacks are explicit lifecycle actions with append-only registry events; idempotent transitions are required under retries.

---

## P1 — Settle soon (won’t block v0 build, but will bite later)

### 9) Monitoring + retrain triggers

* Which signals drive “retrain intent” (drift metrics, delayed label performance, anomaly rates)?
* Do we support shadow scoring/canary in v0, or only manual promotion?

Detailed answers (pinned defaults, based on current posture):
- Retrain intent is driven by a small, explicit set of signals: feature distribution drift, label-delayed performance degradation, rising anomaly rates (data quality or admissions anomalies), and periodic refresh windows. Each trigger emits a retrain intent record with evidence refs.
- v0 supports **manual promotion only**; shadow scoring/canary is optional and must be explicitly declared per bundle. Retrain intent can be automatic, activation is not.

### 10) Retention and reproducibility posture

* How long do we retain DatasetManifests, materialized datasets, train run records, eval reports?
* What’s the “rebuild guarantee” (you can always rebuild datasets from Archive + Label timelines, even if materialized data expires)?

Detailed answers (pinned defaults, based on current posture):
- DatasetManifests, train run records, and EvalReports are retained long-lived (multi-year) as immutable evidence; materialized datasets may be tiered/expired per environment.
- Rebuild guarantee: as long as Archive + Label timelines are retained, OFS can rebuild any dataset referenced by a manifest; expiration of materialized data does not invalidate reproducibility.

### 11) Governance & access

* Who can resolve evidence refs used in training/eval, and how is that audited?
* Any redaction rules for training exports (even for synthetic, you may still treat identifiers as sensitive)?

Detailed answers (pinned defaults, based on current posture):
- Evidence ref resolution is RBAC-gated and audited; access is time-bound with signed URLs or equivalent, and all accesses are logged.
- Training exports are redacted/tokenized by default for identifiers; explicit approvals are required for raw exports, even in synthetic contexts.

---

## Additional Questions

The above are the “core rails” that prevent drift and leakage. There are a few other angles worth looking at so the Learning + Evolution plane is **operable** and doesn’t quietly diverge from the online world.

### 1) Data quality + anomaly handling (offline)

* What happens if replay encounters missing partitions, corrupted archive chunks, schema mismatches, or gaps in offsets?
* Do we **fail closed** (no dataset) or produce a dataset with “holes” flagged?
* Where do these anomalies get recorded (audit report / reconciliation artifact)?

Detailed answers (pinned defaults, based on current posture):
- Missing partitions, corrupted archive chunks, schema mismatches, or offset gaps **fail closed** for training datasets. For diagnostic builds, a partial dataset may be produced only if explicitly tagged as incomplete.
- All anomalies are recorded in a **replay anomaly report** referenced by the DatasetManifest and emitted as a governance fact (when enabled).

### 2) Sampling and class-imbalance policy

* Do you downsample negatives / upsample positives? If yes, is sampling **pinned in the manifest** (seed + rule), so training is reproducible?
* How do you avoid bias from “only labeled cases” (selection bias)?

Detailed answers (pinned defaults, based on current posture):
- Sampling (downsample/upsample/stratify) is allowed only if the **sampling rule + seed** are pinned in the manifest. No implicit sampling.
- Selection bias is mitigated by explicit label coverage reporting, mature-window training (see P1.3), and optional weighting rules pinned in the manifest.

### 3) Ground-truth maturity / label delay modeling

* Do you allow training only on “mature” windows (labels likely complete) or do you train with censored data?
* Do you create “delayed-label evaluation” reports (performance at T+7d, T+30d)?

Detailed answers (pinned defaults, based on current posture):
- v0 training defaults to **mature windows**: label_asof_utc is set to ensure sufficient delay (policy-defined, e.g., 30 days).
- Censored/immature windows are allowed only for explicitly tagged datasets.
- Delayed-label evaluation reports are recommended and recorded as EvalReport variants (e.g., T+7d, T+30d) when requested.

### 4) Feature store drift / feature deprecation strategy

* What happens when feature definitions change? Do you maintain adapters, or do you force new bundles and backtests?
* How do you handle deprecating features while preserving reproducibility of older models?

Detailed answers (pinned defaults, based on current posture):
- Feature definition changes require a **new feature_def_set** and therefore new manifests and bundles; no implicit adapters in v0.
- Deprecated features remain resolvable for historical reproducibility (frozen versions), but new bundles must explicitly target updated definitions.

### 5) Model risk + safety checks

* Do you run stability checks (e.g., monotonic constraints, score distribution sanity, calibration) before PASS?
* Do you require “explainability artifacts” (top features, reason-code mapping) as part of bundle packaging?

Detailed answers (pinned defaults, based on current posture):
- v0 PASS checks include basic stability checks (score distribution sanity, calibration if applicable). Monotonicity constraints are enforced only if declared by the model/policy.
- Explainability artifacts are **required when** the bundle exposes reason codes; otherwise optional but recommended. These artifacts are stored alongside EvalReports.

### 6) Performance + cost envelope

* What’s the acceptable runtime / cost for OFS builds and training?
* Do you cache intermediate joins/features, and if so, how are caches pinned and invalidated?

Detailed answers (pinned defaults, based on current posture):
- OFS and MF record runtime and cost metrics per run; acceptable budgets are environment-specific (local/dev/prod) and tracked as governance facts, not hard gates in v0.
- Caching is allowed only if cache keys include replay basis + feature_def_set + join scope; caches are invalidated on any identity change and are never treated as source of truth.

### 7) Multi-run / multi-scenario isolation

* Can OFS build datasets spanning multiple `platform_run_id`s? If yes, what’s the scope and why?
* How do you avoid accidental cross-run mixing when labels are execution-scoped?

Detailed answers (pinned defaults, based on current posture):
- Default posture: datasets are scoped to **one platform_run_id**. Multi-run datasets are allowed only with an explicit manifest scope listing all runs.
- Execution-scoped labels remain isolated via `(platform_run_id, event_id)`; multi-run datasets must keep run_id in subject keys to prevent leakage.

### 8) Human governance workflow integration

* Who approves promotions? Where do approvals live (registry events, signed records)?
* Do you support “candidate bundles” that can be activated only for shadow scoring first?

Detailed answers (pinned defaults, based on current posture):
- Promotions are approved by governance actors and recorded as registry events with evidence refs; approvals live in the registry event stream.
- Candidate bundles are supported as **non-active** by default; shadow scoring is allowed only if explicitly declared and still requires an explicit promote to become ACTIVE.
