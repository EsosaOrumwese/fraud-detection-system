# Control & Ingress — how worlds become real

This plane is the **border between imagination and reality**.

Upstream, a scenario runner and a synthetic engine can conjure whole universes: merchants, sites, time zones, arrivals, fraud campaigns, parties, devices, labels. Downstream, the fraud platform wants to behave as if it is staring at a live production stream.

The Control & Ingress plane is the strip in the middle that says:

> “This is the world we’re in today. These are the events that count. Everything below this line treats them as real.”

It has four main actors:

* a **Scenario Runner** that decides *which* synthetic world exists today and how it should move,
* the **Data Engine** itself (already fully spec’d),
* a set of **Authority Surfaces (RO)** that publish the world’s laws as read-only tables, and
* a thin but strict **Ingestion Gate** that admits events from that world into the platform.

Everything else in the platform takes these decisions as given.

---

## 1. Scenario Runner — choosing a universe and hitting “play”

The scenario runner’s job is not to simulate fraud or calculate features. Its job is to **choose a universe and schedule it**.

It takes four knobs:

* a **parameter pack** (`parameter_hash`) that defines model, priors and policy choices for the engine,
* a **world manifest** (`manifest_fingerprint`) that pins all external datasets and engine code,
* one or more **seeds** that determine stochastic realisations inside that world, and
* a set of **scenarios** (e.g. baseline, promo spike, holiday, abuse stress) that specify how traffic and campaigns should behave.

From the platform’s point of view, a “run” is something like:

> “For world W (fingerprint F, params P), spin up seed 42 under the baseline scenario, at 1x wall-clock rate, for the next N hours.”

The scenario runner:

* asks the Data Engine to build or reuse a world with `(parameter_hash, manifest_fingerprint)`,
* instructs it which scenario(s) to realise and at what rate,
* keeps a registry of these runs: start/end timestamps, world IDs, scenario IDs, and the resulting engine HashGates,
* and exposes simple facts to the rest of the platform, such as “run R is emitting events tagged with world F, params P, seed S, scenario SC”.

It **does not** peek into engine internals. It treats the engine as a sealed black box that can be told:

> “Given these inputs, please produce a world and a stream that looks like production.”

---

## 2. Data Engine — the only reality upstream

The Data Engine itself is already fully spec’d: Layer-1 (1A–3B) builds the world and geography; Layer-2 (5A–5B) builds intensities and arrivals; Layer-3 (6A–6B) builds entities, flows, fraud overlays, labels and cases.

From the Control & Ingress plane’s perspective, the engine does three things:

1. It produces **canonical streams** of events and flows for each world/seed/scenario.
2. It produces **authority surfaces**: stable tables that describe “what the world is” (sites, zones, routing universes, entity graph, labels, etc.).
3. It publishes **HashGates** for each segment: validation bundles + `_passed.flag_*` that say “this surface is safe to rely on” or “no PASS → no read”.

The important part here is not how the engine achieves that, but that:

* every event the engine emits is tagged with **world identity** (`parameter_hash`, `manifest_fingerprint`) and **realisation identity** (`seed`, `scenario_id`, `run_id`), and
* the engine **never changes its mind** about a world once it is sealed: the same identities always lead to the same surfaces and stream.

This is what allows the downstream platform to treat engine output as if it were live production traffic.

---

## 3. Authority Surfaces — law books on the side

Alongside the stream, the engine publishes a set of **Authority Surfaces (RO)**: read-only datasets that describe the world’s structure and outcomes.

Conceptually, these include:

* **Geography & time**: sites, zones, DST rules, civil-time legality checks.
* **Routing & zones**: how merchants are spread across zones, how traffic is routed to outlets and virtual edges.
* **Entity graph & posture**: parties, accounts, instruments, devices, IPs, and their static fraud roles.
* **Labels & case timelines**: truth labels, bank-view labels, and case timelines from 6B.

In this plane:

* authority surfaces are **never re-derived** by the platform,
* they are always keyed by `manifest_fingerprint` (the world ID),
* and they are **only ever read**.

Events flowing out of the engine carry just enough identity (merchant/site IDs, party/account IDs, world IDs) that downstream components can **join back** to these surfaces when they need to know “where is this?”, “who is this?”, or “what is the ground truth?”.

The Control & Ingress plane doesn’t consume authority surfaces itself, but it is responsible for making sure they exist and that downstream consumers know how to find them.

---

## 4. Ingestion Gate — the front door

The Ingestion Gate is the **first “pure platform” component** that touches engine data.

It is deliberately thin:

* It receives events from the engine’s run (or from an engine-shaped connector in a real deployment).
* It validates those events against **schemas** and **lineage expectations**:

  * schema refs match the platform’s contracts,
  * world IDs (`parameter_hash`, `manifest_fingerprint`, `seed`, `scenario_id`) are present and well-formed,
  * and engine HashGates have been verified for the underlying world (no PASS → no read).
* It enforces **idempotency** at the boundary (so retried deliveries don’t duplicate records downstream).
* It stamps **arrival timestamps and correlation IDs** on the platform side.
* It **tokenises PII by default**, even though the engine’s data is synthetic, so the platform can be run under the same privacy posture as real traffic.

What it explicitly does **not** do:

* It does not call external systems.
* It does not apply business logic or fraud rules.
* It does not “fix” engine data or reinterpret authority surfaces.
* It does not fan out into multiple domains; it outputs a single, normalised event shape.

Its contract is simple:

> “Anything you see downstream has passed schema and lineage checks, is tagged with world identity, is deduplicated at the boundary, and is safe to treat as real as far as the platform is concerned.”

From here on, the event is just “an event” to the rest of the system.

---

## 5. Identity & governance in this plane

Identity and governance concepts are threaded through everything the Control & Ingress plane touches:

* The **scenario runner** chooses `(parameter_hash, manifest_fingerprint, seed, scenario_id)` for each run and records them.
* The **Data Engine** uses those IDs internally and surfaces them on streams and authority tables.
* Each engine segment emits its own **HashGate**, and the platform obeys “no PASS → no read” at the segment boundary.
* The **Ingestion Gate** verifies those HashGates and **refuses to ingest** from worlds that have not passed validation.
* Every ingested event carries world IDs forward so that downstream components can:

  * join to authority surfaces,
  * reconstruct which world/model/policy produced which decisions,
  * and replay or rebuild state exactly for that world.

The Control & Ingress plane is therefore the first place where the platform says:

> “For this world, we trust these surfaces and this stream; we know exactly who they are and where they came from.”

---

## 6. What this plane must never do

To keep later specs and implementations aligned with this narrative, it helps to be explicit about things this plane should **not** try to own:

* It does **not** define or alter the behaviour of the Data Engine. The engine is treated as sealed and authoritative downstream of the scenario runner.
* It does **not** compute features, scores, or decisions. It only admits events.
* It does **not** re-derive or mutate authority surfaces. Those remain read-only law books.
* It does **not** reach out to external systems on the hot path. It is a tight, local gate.

Its job is to pick the world, validate that the engine has done its job correctly, and then hand a clean, well-labelled stream into the rest of the platform.

Everything that follows in the decision loop and learning loop narratives assumes this plane is doing exactly that—and no more.