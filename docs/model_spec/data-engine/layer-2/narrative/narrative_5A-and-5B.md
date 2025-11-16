## Layer-2 — Arrival mechanics (tempo & busy-ness)

Layer-1 gave us a **frozen world**: a sealed catalogue of merchants, physical outlets and virtual edges, all sitting on a well-defined civil-time surface. Every outlet knows where it is, which time zone it sits in, and how it connects to the routing fabric.

Layer-2 is the part of the engine that **presses play**. Its job is to decide *when* synthetic customers show up in that world, and *how busy* everything should feel across time and space.

We split that into two segments:

---

## Segment 5A — Arrival surfaces & calendar (deterministic)

5A doesn’t generate any events. Instead, it builds the **blueprint for traffic**.

Starting from Layer-1 outputs and a sealed scenario calendar, 5A:

* Groups merchants into sensible classes (e.g. small local, big-box, 24/7, virtual-only).
* For each merchant and zone, defines a **baseline weekly pattern**: how busy a typical Monday morning is compared to a Friday evening, in local time.
* Layers on **calendar effects**: pay-day spikes, public holidays, weekends, maintenance windows, campaigns and “quiet” periods.
* Encodes any **cross-merchant structure** you care about: e.g. all UK salary-day merchants respond to the same monthly factor; all US retailers lean into Black Friday in synchrony.

The result is a set of **deterministic intensity surfaces** – “this is how busy this outlet *should be on average* at this time, under this scenario”. For a fixed parameter set, 5A will always rebuild the same surfaces: no randomness, just governed functions of time, zone and merchant.

These surfaces become the authority for busy-ness in the rest of the system.

---

## Segment 5B — Arrival realisation (time brings the world to life)

5B takes those intensity surfaces and **turns them into actual arrivals**.

Given the 5A surfaces and the Layer-1 routing artefacts (alias tables, zone allocations, virtual edge catalogues), 5B:

* Samples **how much traffic actually happens** in each time bucket, allowing for natural variation and bursts rather than perfectly smooth curves.
* Within each bucket, samples **exact arrival timestamps** in UTC and maps them to local time via the Layer-1 timezone cache.
* Routes each arrival through the existing routing fabric to a **concrete site or edge**:

  * physical outlets via the site alias tables,
  * virtual merchants via the virtual edge catalogue and alias.
* Tags each arrival with a **scenario label** (normal, salary-day, holiday, campaign, etc.) so later layers can reason about context.

The output is a **skeleton event stream**:

> `(utc_ts, merchant_id, site_id or edge_id, tzid, scenario_id, arrival_id, …)`

In the long run, counts per merchant, zone and scenario line up with the surfaces from 5A. In any given run, you see realistic noise and co-movement: quiet mornings, lunchtime rushes, payday spikes, and occasional lulls.

Throughout 5B, all randomness is driven by the same Philox/RNG discipline as Layer-1, with counters and traces wired into the Layer-2 validation bundle so every draw is replayable.

---

## Hand-off to Layer-3

Arrival mechanics **never decides fraud, approval, or transaction outcome**. Layer-2’s responsibility stops at:

* *when* traffic happens,
* *how much* traffic happens, and
* *where* in the Layer-1 world each arrival lands.

Because 5A and 5B are fully tied back to the Layer-1 contracts (geometry, time zones, routing, validation bundles), Layer-3 can treat the Layer-2 stream as a clean, sealed skeleton: a realistic clock of customer activity on top of the merchant universe you’ve already built, ready to be turned into transactions, fraud campaigns, and decision flows.
