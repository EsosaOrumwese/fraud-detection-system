## Cluster 10 — Portability + packaging reality (Windows/env drift/atomic replace)

### What Cluster 10 is claiming (plain English)

You dealt with real-world engineering friction that breaks “toy projects”:

* cross-platform dev issues (Windows vs Linux assumptions)
* environment drift (pathing, file locks, atomic replace behavior, permissions)
* packaging pitfalls (entrypoints, builds, artifacts, reproducibility)
* you didn’t just workaround locally — you made it **repeatable**

To certify it, I need **one “platform friction almost derailed the build” incident** + **the fix** + **proof it stayed fixed** (repeatable run/build).

### Cluster 10 — Verification Questions (Round 1)

1. What is your dev platform matrix today (what do you actually run on):

   * Windows host + Docker?
   * WSL?
   * Linux?
   * What must work vs “nice to work”
2. Pick your strongest portability incident:

   * atomic replace / file locking
   * path normalization / case sensitivity
   * subprocess behavior differences
   * permissions/volume mounts
   * packaging/entrypoint mismatch
3. Pin it:

   * what component broke
   * what stage it broke (build? run? cleanup? reseal? packaging?)
   * what the failure looked like (symptom)
4. What was the actual root cause (not just “Windows is weird”)?
5. What did you change:

   * code change? (path handling / file IO strategy)
   * packaging change? (entrypoint discipline / container boundary)
   * runbook change? (operator steps, prerequisites)
6. What “repeatability proof” do you have now:

   * a command that reliably succeeds
   * a run that reliably closes a phase
   * or a build artifact that’s reproducible (same digest / same outputs)
7. What guardrail did you add so it doesn’t quietly regress:

   * preflight checks
   * fail-closed behavior
   * CI build step (if you have it)
8. What did you decide *not* to support (if anything) and why?
9. How does this link to migration readiness:

   * how did portability work feed into dev_min packaging posture
   * how did it change your “no laptop runtime compute” idea (if at all)
10. One sentence: how this demonstrates “systems thinking” rather than “local hacking.”

(These match your “portability + packaging reality” cluster items.) 

---
