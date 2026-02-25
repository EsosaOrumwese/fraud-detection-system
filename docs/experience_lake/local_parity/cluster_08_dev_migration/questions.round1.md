## Cluster 8 — Dev-min managed migration as a real program

### What Cluster 8 is claiming (plain English)

You’re doing a real migration: packaging, IaC, secrets/bootstrap discipline, handle registries, readiness probes, cost constraints, and evidence bundles — while preserving semantic invariants from local_parity.

To certify it, I need **evidence of completed phases** (M0–M3) + **one migration blocker incident** + **proof your guardrails prevented footguns**.

### Cluster 8 — Verification Questions (Round 1)

1. State the migration goal in one line: what “dev_min Spine Green v0” means and what it must preserve from local_parity.
2. What are the non-negotiable guardrails (budget posture, demo→destroy, no NAT/LB, no laptop runtime compute)?
3. What’s the authority stack for migration decisions (what wins when docs conflict)?
4. Walk me through what “DONE” means for M0–M3:

   * what you produced
   * what evidence artifacts exist
   * what the next phase consumes
5. Packaging posture:

   * single-image strategy?
   * entrypoint matrix?
   * provenance (sha/digest) binding?
6. IaC posture:

   * what’s in Terraform vs scripts
   * how you prevent drift
   * how teardown is proven
7. Secrets/bootstrap:

   * how secrets are materialized
   * what is forbidden (baked secrets)
   * how you verify least privilege
8. Give one migration incident:

   * what broke (handles mismatch / readiness probe gap / missing service wiring / cost footgun avoided)
   * how you detected it
   * what changed
   * what evidence proved closure

---
