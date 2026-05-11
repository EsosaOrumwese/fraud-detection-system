
# Data Provision Scope Note v1

Bounded provision window:
- `Mar 2026`

Controlled provision lane:
- one monthly analytical provision path
- one maintained `flow_id`-grain dataset inherited from InHealth `3.C`
- one protected downstream monthly summary derived from that controlled lane

What this slice proves:
- production of one bounded analytical provision lane
- management of source contribution and release-safe fields
- protection against unsafe raw event-grain release
- integrity checks before downstream analytical use

What this slice does not prove:
- enterprise-wide organisational data management
- full systems integration ownership
- broad charity information-governance ownership
