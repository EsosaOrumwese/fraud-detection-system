# Sub-Branch Investigation: `arrival_events_5B` Physical and Virtual Endpoint Geography

## Sub-branch question

The physical/virtual routing branch established that physical arrivals resolve through `site_id`, while virtual arrivals resolve through `edge_id`.

This sub-branch asks a more concrete question:

> Can we visualize the difference between physical site geography and virtual edge geography so that the route split is understandable as an operating distinction, not just a null-profile rule?

The short answer is yes, but with one correction to the initial intuition: virtual routing is not non-geographic. Virtual edges also carry coordinates. The difference is what the coordinates represent.

## Evidence used

Primary workbench evidence:

- [`arrival_events_physical_virtual_routing.md`](arrival_events_physical_virtual_routing.md)
- [`plot_arrival_events_physical_virtual_endpoint_geography.py`](../../../../scratch/plot_arrival_events_physical_virtual_endpoint_geography.py)
- [`selected_endpoint_merchants.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/endpoint_geography/selected_endpoint_merchants.csv)
- [`representative_physical_merchant_sites.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/endpoint_geography/representative_physical_merchant_sites.csv)
- [`representative_virtual_merchant_edges.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/endpoint_geography/representative_virtual_merchant_edges.csv)
- [`representative_virtual_merchant_settlement.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/endpoint_geography/representative_virtual_merchant_settlement.csv)
- [`endpoint_counts_by_route_merchant.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/endpoint_geography/endpoint_counts_by_route_merchant.csv)

Coordinate authorities used from the pinned run:

- `data/layer1/1B/site_locations`
- `data/layer1/3B/edge_catalogue`
- `data/layer1/3B/virtual_settlement`
- `data/layer2/5B/arrival_events`

## What the geography means

Physical route geography and virtual route geography are both spatial, but they describe different operating objects.

For physical routing, the geography is an outlet/site estate. The coordinate rows describe physical merchant sites: places the platform can treat as concrete merchant operating locations. In the coordinate authority used here, those locations are expressed as `merchant_id`, `legal_country_iso`, `site_order`, `lat_deg`, and `lon_deg`. In `arrival_events_5B`, physical arrivals carry `site_id` rather than `edge_id`, so the arrival is being attached to the physical site side of the route model.

For virtual routing, the geography is an operational edge estate. The coordinate rows describe virtual edges: network/payment/commerce endpoints that can carry routed traffic for the virtual merchant. They are still geographic because the edge catalogue carries `country_iso`, `lat_deg`, `lon_deg`, `tzid_operational`, and `edge_weight`. But those points should not be read as storefronts. They are route endpoints in a virtualized operating fabric.

The virtual merchant also has a settlement anchor. That anchor has its own `lat_deg`, `lon_deg`, and `tzid_settlement`. It is not the same thing as every operational edge. This is why virtual geography can have at least two layers: the edge locations that carry operational route context, and the settlement location that anchors settlement-time context.

## Why this uses a merchant pair, not one merchant

The current `arrival_events_5B` route-mode evidence says every merchant belongs to exactly one route mode in this primitive. A merchant is physical-routed or virtual-routed here; no merchant appears in both route modes.

So a single merchant cannot honestly demonstrate both physical sites and virtual edges inside this surface. To make the distinction visible without inventing a mixed merchant, this sub-branch uses:

| Example role | Merchant | Endpoint estate | Arrival rows |
|---|---:|---:|---:|
| physical example | `4991141159764472327` | `34` physical site coordinates across `6` countries | `10,937` |
| virtual example | `4363910952380256924` | `18` virtual edge coordinates across `17` countries, plus `1` settlement anchor | `80,018` |

The physical example is selected because it gives a visible multi-country site footprint. The virtual example is selected near the median virtual edge count, so it demonstrates that a virtual merchant can have multiple operational edges without needing an extreme case.

## Visual evidence and assessment

### G1. Physical site geography versus virtual edge geography

<img src="../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/endpoint_geography/figures/01_representative_endpoint_geography.png" alt="Representative physical site geography and virtual edge geography" width="820">

This figure makes the route distinction concrete.

The physical panel shows a merchant whose route estate is made of physical site coordinates. Each point represents a site location tied to a legal country/site-order coordinate row. The geography therefore reads like an outlet estate: the merchant has places where physical route context can attach.

The virtual panel shows a different object. The gold points are operational edges, not stores. They are distributed route endpoints in the virtual routing fabric. The purple star is the settlement anchor, which is separate from the edge points. This separation is the reason it is wrong to think of a virtual merchant as simply "having no geography." It has geography, but the geography is not a storefront/site geography.

The figure also shows why `is_virtual` should not be reduced to channel language. A virtual merchant can have a broad edge footprint, and a physical merchant can have a broad site footprint. The relevant distinction is the operating endpoint: site estate versus edge estate.

What this figure proves is endpoint-semantics difference. It does not prove that either route is riskier, larger in total fraud, or operationally harder to manage. Those questions require behavioural streams, truth products, and case products.

### G2. Virtual edge estate versus settlement anchor

<img src="../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/endpoint_geography/figures/02_virtual_edge_network_anchor.png" alt="Virtual edge estate and settlement anchor" width="760">

This figure isolates the virtual side because it is the easier one to misunderstand.

The virtual merchant has `18` operational edges across `17` countries. Those are the points that represent the routing/edge estate. The settlement anchor sits in `Europe/Copenhagen`. The faint lines are not transaction flows; they are visual aids showing that the edge estate and settlement anchor are separate coordinate concepts attached to the same virtual merchant.

This is the practical interpretation: a virtual arrival can carry operational route geography through an edge while settlement-time context can be anchored elsewhere. If a later analysis groups virtual traffic by operational geography, settlement geography, or timezone, those are not automatically the same denominator.

That distinction matters for downstream analysis. A case-rate or fraud-rate view by `tzid_operational` may answer a different question from a view by `tzid_settlement`. The geography visible here is the reason those questions should not be collapsed prematurely.

### G3. Endpoint counts per merchant

<img src="../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/endpoint_geography/figures/03_endpoint_count_distribution.png" alt="Endpoint count distribution for physical site estates and virtual edge estates" width="820">

This figure answers the "one or more" question.

Physical merchants can have more than one site. In the physical estate summarized here, the median physical merchant has `17` site coordinates, while the selected illustrative merchant has `34`. The full physical range runs from `1` to `124` sites per merchant.

Virtual merchants can also have more than one endpoint. In the virtual estate, the median virtual merchant has `18` operational edges, and the selected virtual merchant also has `18`. The full virtual range runs from `6` to `55` edges per merchant.

So the distinction is not "physical has many geographic points, virtual has one abstract network id." Both sides can have multi-endpoint estates. The difference is the type of endpoint estate: physical sites represent outlet-like locations, while virtual edges represent operational routing endpoints.

This figure also helps avoid a later denominator mistake. If we compare physical and virtual traffic by merchant only, we hide endpoint estate size. If we compare by endpoint only, we change the denominator again. Both views can be valid, but they answer different questions.

## Working interpretation

Physical and virtual route geography should be read as two different endpoint models, not as geographic versus non-geographic traffic.

Physical route geography is site geography: concrete locations/outlets where physical route context attaches. Virtual route geography is edge geography: distributed operational endpoints through which virtual route context attaches, with settlement geography carried separately by the virtual settlement anchor.

For later interface-world analysis, this means route mode should travel with geography and timezone interpretation. A physical `site_id` and a virtual `edge_id` are not interchangeable keys. They both help locate traffic, but they locate different operating objects.

## Lead carried forward

When we later inspect behavioural streams, truth products, and case products, route geography should be tested with at least three denominators:

- merchant-level route mode
- endpoint-level estate size
- operational versus settlement geography for virtual traffic

That prevents us from accidentally treating a virtual edge location, a settlement anchor, and a physical site as the same kind of place.
