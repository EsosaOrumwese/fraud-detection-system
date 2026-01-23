## Layer-3 — Behaviour, Transactions & Fraud Stories

By the time we reach Layer-3, the lower layers are already alive:

* **Layer-1** has built a believable world of merchants, outlets, zones and virtual edges, with routing, geography and time zones all nailed down.
* **Layer-2** is running, turning that world into a **stream of arrivals**: synthetic customers turning up at specific outlets and edges in space and time, with realistic busy-ness and co-movement patterns.

Layer-3 takes that living world and asks a different set of questions:

> *“Who is this? What are they doing? What does the transaction look like? Is it clean, messy, or outright fraud?”*

This layer doesn’t change *where* or *when* things happen — that’s L1/L2’s job. It controls **what actually happens** when those arrivals hit the bank’s systems.

We split that into two conceptual segments:

---

### Segment 6A — Entity & Product World (Who exists?)

6A is about building the **cast of characters** and the products they hold.

Starting from nothing but the Layer-1 merchant universe and the Layer-2 arrival patterns, 6A constructs a closed, synthetic world of:

* **Customers and accounts**

  * Individual and business customers with:

    * basic profiles (home region, rough segment, typical spend level),
    * one or more accounts and cards,
    * links to merchants (e.g. recurring payees, “favourite” stores).
* **Instruments and products**

  * Cards, bank accounts, wallets, loans, and the relationships between them:

    * cards-per-customer, accounts-per-customer, credit limits and balances,
    * how often they’re expected to be used, in which channels.
* **Devices and network footprints**

  * Devices (phones, laptops, POS terminals), user agents and IPs:

    * some devices are used by a single customer,
    * some are shared (family tablets, work laptops),
    * some are “suspicious” (multiple accounts, unusual geos, data-centre IPs).
* **Static fraud posture**

  * A minority of entities are assigned special roles:

    * mule accounts,
    * synthetic identities,
    * merchants with a history of abuse or elevated risk.

The result is an **entity graph**: customers, accounts, cards, devices, IPs and merchants linked by realistic relationships. This graph is still closed-world; there is no external data source. It becomes the **backbone Layer-3 works on**.

Once 6A is done, we know who exists and what they could plausibly do. Layer-2 arrivals can now be anchored on real synthetic actors, not anonymous points.

---

### Segment 6B — Behaviour & Fraud Cascades (What happens?)

6B is the **story engine**. It takes:

* the arrival stream from Layer-2 (when and where traffic happens), and
* the entity graph from 6A (who and what exist),

and turns them into **transactional flows and fraud stories**.

At a high level, for each arrival from Layer-2, 6B does four things:

#### 1. Attach it to entities

For each arrival `(time, merchant, site/edge, scenario)`:

* pick a plausible combination of:

  * customer,
  * account/card,
  * device and IP,
* consistent with:

  * how that customer normally behaves,
  * how that merchant is usually accessed,
  * whatever scenario is active (POS, e-com, mobile app, etc.).

Over time, this produces realistic **usage histories**:

* certain customers frequent specific merchants,
* some devices are used across many accounts,
* some IPs slowly become more “tainted”.

#### 2. Turn arrivals into flows

A bank doesn’t see just single rows; it sees **event sequences**. For each attached arrival, 6B generates a small **flow** of events, for example:

* login → add card → authorisation attempt → 3-DS challenge → retry → approval → clearing,
* or a simple POS swipe → authorisation → clearing,
* or several failed attempts followed by a successful one.

Flows include:

* authorisation requests and responses,
* clearing and settlement events,
* reversals, refunds, chargebacks and disputes where applicable.

These flows give you a time-ordered **event stream**, not just one “transaction” row.

#### 3. Overlay fraud and abuse patterns

On top of baseline behaviour, 6B runs **fraud and abuse campaigns**.

These are structured objects with parameters like:

* type (card testing, account takeover, merchant collusion, refund abuse, …),
* start time and duration,
* target segment (region, merchant class, customer role),
* tactics (many small transactions vs few large ones, device/IP reuse, etc.).

Campaigns **select and reshape** parts of the arrival stream and flows:

* some logins become account takeovers,
* some low-value test transactions appear at “safe” merchants,
* some merchants start issuing suspicious refunds,
* some cards are suddenly hit in rapid succession at multiple locations.

The engine keeps track of:

* which events belong to which campaign,
* which entities are being “used” by which fraud patterns.

#### 4. Decide labels and outcomes

Finally, 6B produces **labels and outcomes** that look like what a bank actually sees:

For each transaction/flow anchor, it decides:

* **Ground truth label**

  * Is this genuinely:

    * legit,
    * fraud caught at authorisation,
    * fraud that cleared and later charged back,
    * abuse (e.g. refund loops),
    * or something more nuanced?

* **Bank’s view over time**

  * What did the bank decide:

    * at authorisation (approve/decline),
    * at clearing,
    * when a dispute or chargeback came in,
    * after any investigation or rule changes?

This produces:

* an **event stream table** (one row per event),
* a **transaction/flow anchor table** (one row per “transaction story”),
* one or more **label surfaces** tying everything together.

You end up with “what actually happened” and “what the bank thinks happened”, with realistic delays and occasionally messy, ambiguous outcomes.

---

### Hand-off to the rest of the system

Layer-3 doesn’t alter the physical world or the tempo:

* it uses Layer-1 for where things land,
* it uses Layer-2 for when they arrive,

and focuses entirely on:

* who is acting,
* what flows look like,
* how fraud and abuse express themselves,
* how the bank’s internal view of those events evolves.

At the end of Layer-3, downstream consumers (models, rules engines, case-management simulations, analysts) see a world that behaves like a real bank’s system:

* entities doing plausible things,
* events arriving in realistic patterns,
* fraud and abuse emerging in structured campaigns,
* labels and outcomes that feel like the messy, delayed ground truth people actually work with.
