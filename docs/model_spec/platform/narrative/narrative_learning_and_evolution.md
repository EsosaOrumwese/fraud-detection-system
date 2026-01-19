# Learning & Evolution — how the system gets smarter without breaking

The Real-time Decision Loop is about *doing the right thing now*.
The Label & Case plane is about *what that meant in the end*.

The Learning & Evolution plane is about **using that history to change the system**—carefully.

This plane answers questions like:

* “Given what we’ve seen, can we make better decisions tomorrow?”
* “Can we deploy a new model without silently breaking SLOs or policies?”
* “If something goes wrong, can we retreat safely and understand why?”

It has three main pillars:

* an **Offline Feature Plane** that reconstructs the feature view around past decisions,
* a **Model Factory** that trains, evaluates, and packages candidate models/policies, and
* a **Model/Policy Registry + Deployment Pipeline** that puts those candidates into the Decision Fabric under strict control.

Throughout, the same identities and contracts apply as everywhere else:

* `parameter_hash`, `manifest_fingerprint`, `seed`, `scenario_id` (world/run/setup),
* HashGates and “no PASS → no read” for engine outputs,
* schema authority via JSON Schema and dataset dictionaries.

---

## 1. What this plane is for

From a distance, this plane does four things:

1. **Rebuilds what we knew at decision time** for a population of events/flows.
2. **Trains and evaluates** alternative models and policies on that reconstructed view.
3. **Packages and registers** those models/policies as versioned bundles.
4. **Rolls them out** into the Decision Fabric via shadow/canary/ramp, watching SLOs and metrics, and **rolls them back** if needed.

Crucially, it does all this **without guessing**, because it stands on:

* the **Decision Log & Audit Store** (what we decided and why),
* the **Label Store** (what we think actually happened),
* the **Authority Surfaces** (world structure and truth), and
* the **Offline Feature Plane** (same transforms as online).

---

## 2. Offline Feature Plane — rebuilding the view

The Offline Feature Plane is the **historian** of feature values.

It listens to the same Event Bus as the online plane, but instead of answering queries in milliseconds, it focuses on reconstructing, for any world and time range:

> “What would the feature vector have been for entity X at time T, according to our agreed transforms?”

Conceptually, it:

* consumes the raw event stream for relevant worlds (`manifest_fingerprint`, `seed`, `scenario_id`),
* replays the same feature logic as the online plane:

  * same code paths,
  * same schemas and feature groups,
  * same definitions of windows and keys,
* writes out **feature snapshots**:

  * keyed by world IDs, entity IDs, and time,
  * with clear schema references.

The aim is not to keep a perfect snapshot for every event ever, but to be able to **recompute** those snapshots reliably for any training or evaluation slice.

Every decision recorded in the Decision Log carries a **feature snapshot hash** (or enough information to re-derive one), so the Offline Feature Plane can be asked:

> “For these 10M flows, please rebuild the features as they were at decision time.”

Its contract with the Learning Plane is simple:

* **Same transforms as online.**
* **Deterministic under the same world + code + config.**
* **Keyed by the same identities that run through the rest of the system.**

---

## 3. Assembling training and replay datasets

The **Model Factory** doesn’t work in isolation; it stands on a table that the Offline Feature Plane and Label & Case plane fill.

For a given training or evaluation job, the factory will define a **cohort** of interest:

* e.g. “all card-present auth flows in worlds {W₁, W₂} between dates D₁–D₂”,
* or “all flows for merchant segment S across seeds and scenarios”.

For that cohort, the Learning & Evolution plane assembles rows by joining four kinds of information:

1. **What happened at decision time**

   * From the Decision Log: event envelope, world identity, model version in use, feature snapshot hash, guardrail hits, etc.

2. **What features were (or would be) available at the time**

   * From the Offline Feature Plane: feature vectors reconstructed for the exact decision point, using the snapshot hash and world IDs.

3. **What we think happened afterward**

   * From the Label Store: truth labels, bank-view labels, case outcomes, with appropriate lags and lifecycle states.

4. **Stable context**

   * From Authority Surfaces and the entity graph:

     * merchant segment, channel, geography,
     * static posture (mule party, risky device, collusive merchant),
     * world metadata (scenario type, parameter pack).

The result is a **training/eval dataset** with:

* well-defined columns (schema-anchored),
* explicit world IDs and time references,
* and clear separation between:

  * features,
  * labels,
  * and experiment metadata.

This dataset is the starting point for every model or policy experiment.

---

## 4. Model Factory — training and evaluation

The **Model Factory** is the workshop where ideas turn into candidate models and policies. It reads the assembled datasets and:

1. **Defines the problem**

   * e.g. “binary classification of fraud vs legit”,
   * “early detection of high-risk cases”,
   * or “which flows to queue vs auto-decline”.

2. **Trains candidate models**

   * On explicitly chosen worlds and cohorts.
   * Using fixed feature sets (or explicit feature families), tied to schema refs.
   * With proper train/validation/test splits, possibly across worlds to measure generalisation.

3. **Evaluates candidates**

   * Using metrics that reflect cost and risk:

     * AUROC / PR curves,
     * precision/recall at operational points,
     * calibration curves,
     * expected financial cost (loss vs friction).
   * Stratified across segments (merchant types, regions, channels) to detect blind spots.

4. **Checks robustness**

   * If synthetic worlds can simulate stress regimes, models are evaluated:

     * under baseline flows,
     * under campaigns of known fraud patterns,
     * under distribution shifts (more e-comm, more CNP, changed device behaviour).

5. **Packages models/policies**

   * As **bundles**:

     * a model artefact (weights or parameters),
     * feature schema and dependency info,
     * training dataset manifest (which worlds, which time ranges, which labels),
     * validation metrics and summaries.

The Model Factory stops short of deployment. Its job is to produce a **versioned candidate** with a full record of how it was trained and how it performed on agreed benchmarks.

---

## 5. Model/Policy Registry — the catalogue of brains

The **Model/Policy Registry** is the catalogue that the Decision Fabric consults when it needs to know:

* which model/policy is **current**,
* which candidates are **available** for shadow/canary,
* and what each one is **compatible** with.

Conceptually, for each registered bundle it stores:

* an ID and version,
* pointers to the packaged artefacts,
* the feature schema it expects,
* the set of worlds/cohorts it was trained on,
* validation metrics and thresholds,
* and a **status**:

  * `CANDIDATE`, `SHADOW`, `CANARY`, `ACTIVE`, `RETIRED`, etc.

It also records **compatibility rules**:

* which decision endpoints it can be used for,
* which worlds (or world types) it can safely score on,
* and under which policies (e.g. “only for baseline scenario”, “not for merchant class X”).

The Decision Fabric never loads a model from random storage. It asks the Registry:

> “For endpoint E, in world W, with feature set F, what am I allowed to run right now?”

The answer is determined by the registry’s records, not by ad-hoc configuration scattered across services.

---

## 6. Deployment and rollout — shadow, canary, ramp, rollback

Getting a candidate out of the registry and into production is a **policy-driven process**, not a one-off script.

Typical lifecycle:

1. **Shadow**

   * The new model runs **in parallel** with the current model:

     * sees the same events,
     * produces scores and decisions that are **not applied**,
     * metrics are compared offline against Label Store and current behaviour.

2. **Canary**

   * A small subset of traffic (or specific segments/worlds) is actually scored and acted on by the new model.
   * The rest continue to use the current model.
   * Metrics:

     * SLOs (latency, error rates),
     * business metrics (fraud, false positives, cost),
     * model-side metrics (calibration, drift)
       are watched carefully.

3. **Ramp**

   * If canary results pass policy thresholds, the share of traffic handled by the new model increases in controlled steps.
   * At each step, the same metrics and invariants are checked.

4. **Promotion or rollback**

   * If the model passes all gates, it becomes the new `ACTIVE` version for that endpoint.
   * If any SLO or business metric breaches, the system **rolls back** to the previous version (which is always kept in the registry) and marks the candidate appropriately.

Throughout this process, **nothing moves** without:

* manifest + schema + lineage consistency,
* policy approval (encoded as data, not code scattered across services),
* and visible metrics.

The Learning & Evolution plane defines these rollout patterns in **human terms**; later specs will nail down thresholds and mechanics.

---

## 7. Monitoring, drift, and when to retrain

Learning is not a one-time affair. The plane must also answer:

* “Is the world drifting away from what the model was trained on?”
* “Are our models decaying in performance?”
* “Is the decision mix changing in worrying ways?”

It does this by watching:

* **Feature distributions** over time (train vs serve):

  * via the Offline and Online Feature Planes.
* **Label-conditioned metrics**:

  * precision/recall, false positives, false negatives, broken down by segment.
* **Decision mix**:

  * fractions of APPROVE / STEP-UP / DECLINE / QUEUE, by segment and over time.
* **World changes**:

  * new worlds with different mixes of merchants, behaviour, and fraud campaigns.

When drift or degradation is detected, the plane can:

* trigger **retraining** on fresher worlds,
* suggest **segment-specific models** or thresholds,
* or recommend **policy changes** (e.g. more aggressive step-ups in a region).

But crucially:

* It doesn’t “fix things live”; it **proposes updates** to models/policies that must flow through the same training → evaluation → packaging → registry → rollout process.

---

## 8. Boundaries and non-goals

To keep later specs honest, it’s important to state what the Learning & Evolution plane **does not** do:

* It does **not** define real-time decisions; it only trains the brains that the Decision Fabric will apply.
* It does **not** override HashGates or engine validations; it works only with worlds that have passed.
* It does **not** mutate authority surfaces or Label Store records; it reads from them and writes new model/policy bundles and metrics.
* It does **not** assume any particular vendor tooling; it assumes:

  * an event stream,
  * a way to reconstruct features offline,
  * a place to store labels,
  * and a catalogue to register models/policies.

Its job is to make sure that:

* the platform can **learn from its own behaviour**,
* those learnings are captured in **versioned, auditable bundles**,
* and changes to those bundles are **rolled out and rolled back safely**.

Everything the Decision Fabric will do tomorrow depends on this plane doing its part today: turning history into better, safely-deployed decisions.
