Ready. Switching into **technical recruiter / verifier** mode for Cluster 1.

### What Cluster 1 is claiming (in plain English)

You didn’t just “run some services.” You designed and enforced a **phase-gated run lifecycle** (Spine Green v0) where:

* every phase has a **gate + commit evidence**
* you can **fail-closed** (stop the run / refuse readiness claims) when evidence is missing
* you actively prevent **design/implementation drift** via pinned authority rules + drift sentinels + meta-layer blockers

Now I’m going to **certify** this cluster so it becomes a “lake entry” we can defend.

To certify it, I need **one concrete, replayable example run** + **one concrete drift incident** + **proof of enforcement** (not just docs existing).

---

## Cluster 1 — Verification Questions (Round 1)

### 1) Definitions that must be exact

1. What does **“Spine Green v0”** mean in your language? (Which planes/components must be green for the claim to be true?)
2. What does **“20/200”** mean exactly? (20/200 *what* — events, windows, minutes, batches? And what’s the pass condition?)

### 2) Pick one “gold run” we’ll use as the anchor

3. Choose **one** run you consider your best proof of the evidence-gated lifecycle.
   Give me just:

   * the **platform_run_id** (or whatever run identifier is canonical)
   * the **root evidence path** for that run (where the run artifacts live)
4. For that run, list the **actual evidence artifacts** you produced for the run lifecycle.
   Not everything — just the big ones that prove the gates are real. Example of what I mean:

   * run pin artifact (run.json / run_record / ACTIVE_RUN_ID pointer)
   * daemons ready artifact
   * oracle ready artifact
   * ingest committed artifact (receipts)
   * RTDL caught up artifact
   * decision chain committed artifact
   * case/label committed artifact
   * obs/gov closure artifact (run report / conformance / governance append)

(You can answer as a simple file list or directory tree. No screenshots needed.)

### 3) Proof that gates are *enforced*, not just written down

5. How is a gate **enforced** today?

   * Is there a script that exits non-zero?
   * Does the operator checklist explicitly block the next command?
   * Is there a single “run status” file that must transition?
6. Give me **one example of a failed gate** you hit in real life:

   * which phase failed
   * what evidence was missing / invalid
   * what the system/operator did next (stop? quarantine? reopen? reset level?)
   * what you changed to pass next time

### 4) Drift-sentinel incident (this is your “killer proof”)

7. In your drift-sentinel story (Case/Label not daemonized before full-platform proof):
   Walk me through it like I’m skeptical:

   * What *exactly* made it a “material coverage gap” (what would have been untrue)?
   * Where did you notice it (which doc/run output/checklist triggered the alert)?
   * What changes did you make (which services/packs became part of run/operate)?
   * What evidence proved it was closed *before* you continued?

### 5) Anti-drift governance (authority hierarchy)

8. Where is your **authority hierarchy** pinned today, and what are the top 3 “winning” authorities when docs conflict?
9. What is your concrete **stop/log/repin** rule?

   * What triggers it?
   * Who/what is allowed to override it?
   * Where is the decision recorded so it’s auditable later?

### 6) Meta-layer blocker (why this isn’t a toy)

10. You elevated meta-layer closure as a blocker before moving into downstream planes.
    Tell me:

* what counts as “meta-layer closure” (run/operate + obs/gov) in your current truth model
* what artifact(s) prove closure
* what would have gone wrong if you didn’t block it

---

Reply however you want, but the fastest is to answer **1→10 in order**.

Once I have your answers, I’ll tell you whether Cluster 1 is **certified**, **partially certified**, or **needs proof downgrade**, and then I’ll write the **first huge Experience Lake entry** from it.
