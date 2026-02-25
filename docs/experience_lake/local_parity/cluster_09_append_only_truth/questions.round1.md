## Cluster 9 — Append-only truth for Case/Label/Audit

### What Cluster 9 is claiming (plain English)

You didn’t treat “cases/labels/audit” as an afterthought. You designed a **truth model** where:

* decisions/cases/labels are **append-only** (no silent overwrites)
* every run produces **as-of views** and **durable evidence** you can audit later
* conflicts (duplicates, replays, late arrivals, collisions) have a **defined posture** (quarantine / block closure / explicit remediation)
* writer ownership is pinned (single-writer where it matters)

To certify it, I need **one anchor run** + **one conflict/immutability incident** + **proof of as-of/audit artifacts**.

### Cluster 9 — Verification Questions (Round 1)

1. Define your “truth model” in one paragraph:

   * what is append-only
   * what is allowed to be derived/overwritten (if anything)
   * what “truth” means in your platform (not philosophy — operationally)
2. What are the lanes/stores involved (names in your system):

   * Decision lane (DF/AL → DLA?)
   * Case lane (CaseTrigger / CaseMgmt?)
   * Label lane (Label Store?)
   * Any “audit store” / governance append
3. What is the “writer map” at this layer:

   * who is allowed to write each lane/table/prefix
   * what prevents accidental multi-writer drift
4. What is an **as-of view** in your system:

   * what is “as-of” indexed by (time, offsets, run id, sequence)
   * where is it materialized (file/table prefix)
   * what guarantees it gives (immutability, reproducibility)
5. What are the commit-evidence artifacts for this layer:

   * What proves “decision chain committed”
   * What proves “cases committed”
   * What proves “labels committed”
   * What proves “audit closed”
6. Pick one anchor run and give:

   * `platform_run_id`
   * root run path
   * the exact evidence paths for decision/case/label outputs
7. Give one real conflict/immutability incident:

   * what attempted to overwrite/duplicate
   * how it was detected (receipt, constraint, mismatch)
   * what the system/operator did (block closure? quarantine? new run?)
   * what you changed to make it safe
8. How do reruns interact with truth:

   * what changes when you rerun with the same platform_run_id (if allowed)
   * what forces a new platform_run_id
   * how do you prevent “truth contamination” across runs
9. What is your “audit story”:

   * if someone asks “why did this case exist / why was this label assigned?”
   * what chain of artifacts do you point to (minimum path)
10. Migration angle:

* what invariants about append-only truth must remain identical in dev_min
* what can change (storage tech, service packaging) without breaking truth semantics

(These map to the Case/Label/Audit cluster items you listed as “strong add-ons.”) 

---
