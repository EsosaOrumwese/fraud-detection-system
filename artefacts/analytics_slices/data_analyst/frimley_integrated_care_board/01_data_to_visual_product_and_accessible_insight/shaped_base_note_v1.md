
# Shaped Base Note v1

Preparation posture:
- the Frimley slice uses a compact SQL-style shaping step over an inherited mixed-source reporting base
- the shaping layer retains only the fields needed for a user-facing dashboard summary and guided visual-story surface

Retained product grain:
- `amount_band`
- row count retained: `4`

Primary focus band after shaping:
- `50+`
- confirming streams: `3`

Cross-stream focus readings:
- average case-open rate: `10.81%`
- average truth quality: `18.15%`
- case-open spread across retained streams: `+0.04 pp`

Why this shaping layer matters:
- it behaves like the `SQL`-to-product preparation step the Frimley role expects
- it converts a mixed-source analytical pack into a cleaner visual-product base without reopening raw scope
