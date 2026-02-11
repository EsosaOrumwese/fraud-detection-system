# Dev-Min Migration Narrative (Incremental)
_As of 2026-02-11_

This narrative is intentionally incremental.
Sections will be appended in discussion order, starting from local-parity implemented baseline and moving gate-by-gate into `dev_min`.

## Section 1: Bootstrap Before Swap (Flow Step 1)

We begin from a fully green local-parity platform: all planes function, flow logic is validated, and ownership boundaries are known. Performance is limited by local substrate, but semantics are trusted. So the first migration question is not "which component do we rewrite first?" but "what control surface will govern all rewrites?"

The first step in flow is a trust-and-control bootstrap in `dev_min`. That means establishing identity, credentials, and policy-bearing access for the shared substrates before any component migration. In practical terms, AWS and Confluent credentials are not treated as simple secrets; they are the first runtime control artifacts that define who can provision, publish, consume, observe, and audit.

Next, we stand up the meta-layers early: Run/Operate and Obs/Gov. This is intentional sequencing. If we migrate components before these layers exist, we recreate the same drift risk seen in local-parity evolution, where services can run but are not uniformly orchestrated, observed, or cost-governed.

Only after this bootstrap gate is green do we begin incremental plane migration. Each plane then enters through a controlled path: substrate resources are provisioned, component contracts are mapped, and runtime evidence is emitted under the same operate/govern rails from day one.

So this pre-decision is adopted as a flow law: bootstrap control and trust first, then swap tools and services incrementally under that control.
