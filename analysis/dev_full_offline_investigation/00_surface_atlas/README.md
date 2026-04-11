# Surface Atlas

The atlas is the operating map of the platform's governed data world.

It is not a generic data dictionary. It records how important surfaces function inside `dev_full`.

For each surface, the atlas captures:

- what the surface means in platform terms
- which engine segment or state owns it
- whether it is traffic, context, truth, or telemetry
- the grain and main join keys
- whether it is safe for RTDL use or offline-only
- which plane primarily consumes it
- which analytical questions it can support

The atlas exists to prevent three common analytical mistakes:

1. treating join surfaces as if they were canonical traffic
2. treating offline truth as if it were valid live-decision context
3. treating telemetry or audit evidence as if it were business data

Primary files:

- `surface_atlas.md`: readable narrative version
- `surface_atlas.csv`: tabular version for filtering, joins, and notebook use
