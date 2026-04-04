# Data Capture Control Monitoring Note v1

Control issue surfaced:
- shared band labels, shares, and gap logic were living in downstream outputs rather than one maintained reusable layer

Why it matters:
- repeated shaping increases the risk of drift between reporting outputs
- maintaining the shared layer explicitly makes downstream reuse easier to check and safer to rerun

Focus band still requiring attention:
- `50+` with burden-minus-yield gap `+1.01 pp`
