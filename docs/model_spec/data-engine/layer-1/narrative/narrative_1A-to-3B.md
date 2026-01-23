## Layer-1 — Merchant Location Realism

Layer-1 is the base of the engine. Its goal is simple to state and hard to do well:

> Take a synthetic merchant universe and turn it into a believable map of **where** those merchants exist, **how** they’re spread across countries and time zones, and **how** traffic will move through that world.

By the time Layer-1 is done, you have:

* A sealed catalogue of merchants and outlets,
* Concrete locations on the planet,
* A clean civil-time surface (IANA time zones and DST behaviour),
* A routing fabric that knows how to send traffic to sites and virtual edges,
* Zone-level structure (cross-zone merchants) that will support temporal realism,
* A full story for virtual-only merchants.

Everything is governed by two cross-cutting concerns:

* **4A – Reproducibility & configuration discipline**, and
* **4B – Validation & HashGate** (no PASS → no read),

but those aren’t separate pipelines — they’re baked into how 1A–3B behave.

---

## Segment 1A — From merchants to outlet stubs

1A starts from an abstract merchant list and decides **how many outlets each merchant has, and in which countries**.

It:

* Uses governed statistical models to decide whether a merchant is single-site or multi-site.
* Decides domestic vs cross-border presence, and how many outlets sit in each country.
* Builds a **country candidate set** per merchant and fixes a deterministic **cross-country order**.

The key output is an **outlet catalogue**:

* One stub per outlet per merchant per country.
* Within each country you get a simple sequence of sites (1,2,…,N).
* Cross-country order is not stored here; it’s kept in a separate candidate set that remains the single authority.

At this point, outlets are abstract: a merchant might have “5 outlets in the UK and 2 in France”, but we don’t yet know where they are on the map.

---

## Segment 1B — Putting outlets on the map

1B takes those outlet stubs and places them into **concrete geography**, within the right countries.

It:

* Uses sealed spatial priors (population rasters, land/sea masks, road networks, etc.) to decide where outlets are likely to be.
* Builds a parameter-scoped grid of eligible tiles per country.
* Assigns each country’s outlet counts to tiles according to those weights.
* For each outlet, picks a tile and applies small, uniform jitter inside the tile, with bounded resampling to keep the point inside the country.

The output is a **site locations** surface:

* One row per outlet stub from 1A,
* With `(lat, lon)` plus any extra geographic detail you need.

1B never touches cross-country order; it just takes “this merchant has N outlets in this country” and turns that into N plausible points in space.

---

## Segment 2A — Civil time: sites to time zones

2A sits on top of 1B and assigns each site to a **civil time zone**, then compiles a compact view of DST behaviour.

It:

* Uses a sealed `tz_world` polygon set to find which IANA TZID each `(lat, lon)` belongs to.
* Applies a small, deterministic nudge near borders to resolve ambiguous boundary cases.
* Applies a governed override policy (per site / merchant / country) for operational exceptions.
* Compiles a **time-zone timetable cache** from a fixed tzdb release so you can map any UTC instant to local time and offset, including gaps and folds.

The main outputs:

* A **site timezones** surface: one `tzid` per site, with provenance.
* A **tz timetable cache** per fingerprint: all the DST transitions needed for the run.

This is the canonical civil-time surface for later layers — 5B will never guess its own zones or DST rules.

---

## Segment 2B — Routing: traffic to sites and edges

2B takes the physical world and time zones and builds a **routing fabric** that future layers can use to send arrivals to sites (and later, virtual edges).

It:

* Derives baseline **site weights** per merchant from L1 information (e.g. outlet size, priors).
* Freezes those into O(1) **alias tables**, so picking a random site for a merchant is constant-time and deterministic given a RNG stream.
* Builds **day-effect surfaces** per merchant and time zone group, so you can modulate volumes over days in a way that induces realistic co-movement.
* Differentiates physical routing (to real outlets) from virtual routing (to network edges, which 3B will define).

2B doesn’t generate any transactions; it just builds the routing machinery:

* A static probability law over sites per merchant,
* Day-by-day modulation parameters,
* Binary alias structures that later layers can call at runtime.

---

## Segment 3A — Cross-zone merchants (zone allocations)

3A captures the idea that some merchants have material presence in **multiple time zones within the same country** (e.g. a chain spread across east and west coasts).

It:

* Examines each merchant’s per-country outlet counts from 1A and asks: “Does this country need to be split across zones or is one zone enough?”
* Uses settlement statistics and governed priors to derive a **Dirichlet distribution over zones** for each country.
* Draws one share vector per merchant×country and then deterministically rounds that into integer per-zone outlet counts, using floors and bump rules to maintain counts and floors.

The output is a **zone allocation** surface:

* For each merchant and country, a breakdown of outlets across legal IANA zones in that country.
* Zone-level counts that sum back to the 1A country counts.

3A never changes **which** countries a merchant occupies or the cross-country order; it only refines “N outlets in a country” into “n1 in zone 1, n2 in zone 2, …”.

It also publishes a **routing universe hash** tying together:

* which priors and policies were used,
* which zone allocations were produced,
* how day-effect variance is defined,

so that 2B and later layers can detect any drift in zone-level routing inputs.

---

## Segment 3B — Virtual merchants & edges

3B is the counterpart to 1B/2B/3A for **virtual-only merchants**: those that don’t have physical sites, but operate purely through a network edge footprint.

It:

* Defines a single **settlement location** per virtual merchant (legal seat).
* Builds an **edge catalogue** of network locations (e.g. CDN nodes, data-centre IPs) that can serve traffic for that merchant.
* Assigns weights to edges and builds alias structures so virtual routing is as efficient and governed as physical routing.
* Defines **dual time-zone semantics** where needed: one for settlement, one for operational “where the customer appears to be”.

The output is a pair of surfaces:

* A virtual edge catalogue per merchant,
* A routing plan that defines how arrivals at a virtual merchant are mapped to edges and what local time context they see.

This lets Layer-2 treat virtual merchants as first-class citizens, with realistic edge footprints instead of floating “nowhere” activity.

---

## 4A & 4B — Cross-cutting: reproducibility and validation

You originally sketched 4A and 4B as separate segments, but in the current design they are **cross-cutting disciplines** woven into 1A–3B:

* **4A — Reproducibility**

  * Every segment starts with an S0 that:

    * fixes a `parameter_hash` and `manifest_fingerprint`,
    * verifies upstream PASS flags,
    * records exactly which artefacts and configs are in scope,
    * never uses wall-clock time or hidden state.
  * All randomness is driven by a shared Philox-based RNG, with events logged to structured RNG streams that can be replayed.

* **4B — Validation & HashGate**

  * Each segment ends with a validation state that:

    * replays the core logic for structural and numerical checks,
    * writes a **validation bundle** (index + evidence files),
    * publishes a `_passed.flag` containing a hash over the bundle.
  * All downstream segments obey **“no PASS → no read”** for upstream surfaces.

Together, 4A and 4B ensure that Layer-1 is not just plausible but **sealed**: every dataset has a clear provenance, and every consumer has a simple rule for whether it can trust a fingerprint’s outputs.

---

## What Layer-1 hands to Layer-2

When Layer-1 is “done”, Layer-2 sees a world where:

* The **merchant graph** is fixed and outlet counts by country and zone are known.
* Every outlet has a concrete point in space and a **time zone** that maps UTC arrivals to local time correctly.
* There is a complete **routing fabric** for:

  * physical merchants → outlets,
  * virtual merchants → edges,
    including static weights, alias tables, and zone-level structure.
* For each segment, there is a fingerprint-scoped **validation bundle + PASS flag** that can be checked cheaply at the boundary.

Layer-1 never decides how many arrivals happen or which ones are fraud. It’s the world-builder: a closed, reproducible, validated map that Layer-2 can press “play” on, and Layer-3 can populate with behaviour and fraud stories.
