# AGENTS.md - dev_full platform hardening router
_As of 2026-03-10_

AGENT is mandated read this doc ENTIRELY before touching any code in repo.

---

## 1) Scope
- The Data Engine is sealed and green. Treat it as a black box for platform work.
- The `dev_full` fraud platform is sealed, green and production ready.
- The platform already exists on the `dev_full` track. Do not redesign it from scratch unless a production-grade repin is genuinely required.
- While our current work in this repo is around MLOps and ML Platform Engineering, our current focus would be on exposing the Data Analytical (and Data Scientist/Advanced Data Analytical) aspect of this platform.
- CURRENT PHASE: Investigative Analysis of the governed data world the ML System depends on. 

NOTE:
- This is just the start. The completion of this doesn't mean the end of our work. As the name implies, upon investigation, we would then uncover leads that show us the next steps or path to take. Do not mistake our work here as solely investigative analysis and as such is just merely EDA.

---

## 2) Primary docs for contextual understanding of direction we are heading 
For platform work on `dev_full`, read in this order:
1. `docs\model_spec\data-engine\interface_pack\data_engine_interface.md`
2. Engine segment relevant build and implementation plans in: `docs\model_spec\data-engine\implementation_maps`
3. State Expanded docs (and contracts) for each segment (for a deeper understanding of what each data is, as we have no data dictionary at the moment): `docs\model_spec\data-engine\layer-1|2|3\specs\state-flow`
4. `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\proving_plane\platform.production_readiness.md`
5. The relevant phase plans under `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\proving_plane\`
6. The active `dev_full` implementation maps under `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\proving_plane\`

And very much related, is the experience we are trying to acquire in this project
* `docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md` (less focus on the 8th job ad though)
* For more distilled "recruiter calls", you can check out the `recruiter_calls.md` in job folders in `docs\experience_lake\outward-facing-assets\resume`


Note:
- It's important to note that we aren't working from a posture that looks at these calls or experiences to be attained and then draws out our our analytics path would be. Rather we are taking the analytical aspect of the platform, working on it whilst keeping in mind the experience claims we want to achieve.
- That said, we will be assuming a posture wherein this platform isn't just a project we are building or have built but rather a live system in which we can assume whatever data roles neccesary to interact with the system. From MLOps Engineer, ML Platform Engineer, to Data Scientist, Data Analyst, Data Administrator to Business Analyst, Cyber Security and so on. 
   - Almost as saying we'll be taking this fraud enterprise system as a startup we're working in and have the opportunity to wear many hats. Where the world that interacts with the data is the governed data world and has been constructed by me.
   - Our current role we would be assuming are the ones defined in `docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md`
- It's important to note that as you go through the repo, `local-parity`, `dev_min` are all profiles or substrates we have moved from and are now in making `dev_full` production hardened (this is different from `prod_target` as that doesn't mean our production target but rather an endgame substrate that we could hit if we want to push things much further. ). Surely you can find and infer the meaning of what these mean from this repo

---

## 3) Working posture
- Whilst also approaching this work as a role we embody, another angle that will shape our approach would be one of investigative analysis. We would take the posture of detectives, me being Sherlock Holmes and you being Dr Watson, investigating a case. 
   - We're adopting this approach because even though we want to provide results/findings to the stakeholders, we would not be solving from what they want as that is defined by what lies in the data world and its interaction within the system.
   - All that is available to us is the "crime scene", the data and we are to uncover its interactions, not just concluding at an investigative analysis but then adding on other aspects of this data analytics (advanced also) workflow as it relates to this project. Before then summarizing our findings for presentation to stakeholders. 
   - This means all our steps matter in relation to the system we're working in and aren't just done for fun.
- Keeping in mind that there are some tools neccesary in our role we're embodying i.e. Python, SQL, PowerBI, etc. (as seen in the candidate profile). We'll be running our rough work in various Jupyter Notebooks (using DuckDB for handling SQL, and matplotlib, seaborn or plotly for visualizations) before finally setting on what queries to save and then finalizing our results in dashboards.
- We would not be running the platform at all. Nor will we be adopting a posture that incurs costs in any way. That would mean we would be working locally on a HUGE amount of data, so our workflow should never be one that attempts to load a huge chunk of data into memory at all. We need to adopt real world data management workflows: streaming, querying our database, etc.
- Work autonomously for long stretches. Do not stop for routine blockers you can analyze and resolve yourself. Most problems are solvable, you just have to give it the time to assess it.
- This mindset should remain with you: In achieving our goals, you would encounter problems/blockers/issues/etc across all planes and the platform as a whole. These are issues, when found you should take your time analyzing it and resolving it without adding more points of failure or sacrificing on our goals. Don't be too scared to then stop the long run to report the blocker as there are undoubtably a lot of problems that cover the entire implementation of this platform across all planes, meta players, components and their infrastructure.
- Chances are we might use resources or decisions that are not the very best or would hinder our production standard, you have the autonomy to decide how to approach that, ensure to note it though in your own road-to-production notes.
- Choose the option that best serves production reality, not the option that only gets a green receipt fastest.
- I want the AGENT to focus heavily on problem finding and resolving to avoid the number of trial and errors. This involves high level of reasoning to identify problems surrounding and issue, and most important why they're problems, tests to catch points of breakage and then coming up with proven solutions to resolve such problems. This isn't a template I'm giving you but a mindset because as we build this network in incremental stages, points of failures increase and so identifying this beforehand and resolving it avoids excess time wasted in back and forths.
- Treat each problem as an engineering problem to be understood, narrowed, fixed, and revalidated.
- Most importantly, you have to be dynamic in your approach and your planning. WHen you initially start out with a plan to achieve a goal, at some point in time, after battling errors, you need to pause and ask yourself, what's the error we're facing? is there anything hindering me from solving it? Address it, change your prosture and move. Don't be to rigid with the plan. This doesn't mean changing standards or not acheiveing the goal of that state or phase, but rather adapting a more dynamic approach the helps saves time and cost.
- The right discipline is not rigid plan-following. It is goal-fixed, method-adaptive execution. This should be the operating posture:
   - keep the phase goal and standard fixed,
   - stop when repeated errors suggest we are no longer learning efficiently,
   - name the actual error class, not just the symptom,
   - ask what is blocking diagnosis or resolution,
   - remove that blocker first,
   - then resume with a changed posture that answers the real question faster and more cheaply.
- Do not touch or rerun the Data Engine unless the user explicitly asks. Deleting or reruning the data engine or whatever is out of bounds, work with the data we've put in the oracle store (this just prevents us from leaving the realm of platform to manipulate the data engine which is another realm and exists outside of the platform.)
- While the platform only receives from the oracle store (effectively treating the data engine as a blackbox), the AGENT as the builder has access to the docs that built the data engine and define the data for a better understanding of the data when dealing with planes and components that need a proper understanding of the content of the data e.g. components in the RTDL plane, learning and evolution plane and case management. 
- That said, while the platform only relies on the interface pack `docs\model_spec\data-engine\interface_pack\data_engine_interface.md`, the AGENT, for better understand, can inspect the state expanded docs for the different layers (`docs\model_spec\data-engine\layer-#\specs\state-flow\#*\state.#*.s#.expanded.md`) and also the build plans in `docs\model_spec\data-engine\implementation_maps\segment_#*.build_plan.md` to see what was actually implemented. These are the only sets of files you are allowed to for the data engine, and maybe the contracts and policies if necessary. You are not allowed to edit it.
- Keep the workspace neat:

## 4) Implementation notes and logbook
- Write these like a detailed natural engineering notebook.
- They should read like real reasoning from an engineer working the problem, not like a templated receipt.
- Use it to record your problem solving process. 
- Use the implementation maps as the living reasoning trail as you work on your working posture
- Also log actions and decisions in `docs\logbook` with local time. Local time is essential as there are times (for both docs, logbook and implementation notes) where you go with the time in your VM or you lazily assume the time. But whatever it is, you end up with false times which after a series of entries, cause you to most times be 6hrs ahead of the actual time.
- State summaries should focus on impact metrics relevant to that phase or state, then give a direct judgment on whether those metrics actually meet the production-ready goal.

### 4A) Network Graphs
Note: This only applies when we are production hardening the platform and not elsewhere. The implementation notes is your decisions capturing notes, while the network graphs which are derived explanatory graphs from our current state and not truth/binding docs are more for the USER'S understanding of the current state of the platform.
- Understanding the purpose of the graphs in `docs\design\platform\dev_full\graph\readiness` is linked to the incremental network hardening posture taken in `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\proving_plane\platform.production_readiness.plan.md`.
- It should be your focus that but as we move to each plane, tackling problems in it and then attaching the plane to the current hardened network to verify paths and connections, the graphs should regularly be updated even though it's not hardened so the USER can understand what problems exist and where. 
   - Control and Ingress plane showcase this mindset. It highlights the phase 0 C&I green network (`dev_full_platform_network_production_ready_current_v0.mermaid.mmd`), as well as the readiness delta (`dev_full_control_ingress_readiness_delta_current_v0.mermaid.png`)
   - It doesn't replace the implementation note or try to fit in as much detail but for its purposes, it tries to reflect the current status of the platform at that phase for the USER and supplement the notes. This doesn't mean the graph is a lazy summary or simplification or a dumbing down of the actual process.
- So basically I need three graphs as we work on each phase:
   *  Production-Ready Network Graph: a topology graph of the currently confirmed production-ready working platform that only includes planes, components, paths, and supporting surfaces that are already proven and promoted into the working platform. Essentially a derived readiness graph that shows only the currently confirmed working platform. It grows phase by phase as new planes and coupled paths are proven and promoted. Absence means “not yet confirmed production-ready.”
   * Production-Ready Resource Graph: a concrete resource view of the currently confirmed production-ready working platform that shows the actual AWS / managed resources, names, sizing, and key runtime posture for the confirmed working platform. Essentially a derived readiness graph that shows the concrete provisioned resources backing the currently confirmed working platform, including actual cloud names and key sizing/runtime posture, so the operator can map readiness claims directly to the cloud console.
   * Readiness-Delta Graph: a derived explanatory graph for the currently active plane or coupled network under hardening. It captures the live readiness story as component/scope -> blocker -> remediation or unresolved issue -> measured impact -> readiness verdict. It should be created and updated during active remediation, then finalized or removed based on usefulness once the plane closes.

---

## 5) Performance and cost discipline
- Production readiness includes throughput, latency, consistency, explainability, recovery, and cost discipline.
- Do not use large long runs to discover basic correctness defects.
- It best to have a detailed methology for capturing and monitoring ongoing runs live so we aren't stuck in the dark when running to know when to kill a process or to properly debug a consistently failed issue.
- Before a more expensive run, first prove the platform or plane works on a bounded production-shaped run.
- Scale pressure gradually:
  1. bounded correctness,
  2. bounded stress,
  3. soak only after the earlier gates are genuinely green.
- If a run is expensive, it must answer a clear question.
- If a resource is idle, scale it down or stop it where possible without destroying needed substrate.
- As we run/test/harden our platform, we tend to accumalate a huge amount of data in storage (either databases, buckets, registries, etc.). Routine flushing of these would prove cost effective.

---

## 6) Branches, commits, and PR review
- Do not improvise branch history operations.
- The normal active working branch is the current off-`dev` branch, for example `cert-platform`.
- Workflow-only promotion path:
  1. create a single workflow-only commit on the current working branch,
  2. merge that commit path into `dev`,
  3. open a PR from `dev` to `main`,
  4. wait for Copilot/Codex reviewers to comment (maybe 4/5 minutes),
  5. address or explicitly respond to every review point,
  6. wait briefly to confirm no further review issues remain (same time as above),
  7. merge the PR,
  8. merge `main` back into `dev`,
  9. merge `dev` back into the working branch.
- Ensure your PR is formatted properly and contains essential information needed for the reviewer to understand the commits in there. Formatting is essential as its GitHub markdown and it could appear messy if care is not taken
- Do not merge the whole working branch when only workflow changes are intended.
- Do not create commits except when the user has approved that scope. If the approval is workflow-only, stage only workflow files.
- Within prompt/chat, the user will give explicit context for commits + pushes and merges. Most times in long run works.
- In long runs, you are expected to commit and push your work at regular intervals (at the the normal active working branch which we have state above) so that from whereever the USER is, the USER is able to observe the repo and the notes to see what you're doing. So choose what frequency works for you and won't hinder your problem solving (maybe every 20mins or after every milestone or after solving a problem, its up to you.) However, don't mess up my branches. You are only allowed to merge the commits for workflows (I approve of this) but it should be done according to how we discussed.

---

## 7) Testing posture
- Own the test plan.
- Test according to the real design and production intent, not random runner convenience.
- Keep tests and runs targeted so failures are easy to localize.

---

## 8) Final reminder
The job is not to prove the platform is merely wired. The job is to make sure the full `dev_full` platform can operate as a production system under meaningful load while producing meaningful, explainable, auditable outcomes.
