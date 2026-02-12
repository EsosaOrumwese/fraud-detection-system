# Challenge Story Bank

## Story Quality Standard (Pinned)

This standard is binding for every new ID entry in this file.

1. Evidence-first writing:
   Read challenge and solution evidence lines before drafting the story. No assumption-only writing.
2. Fixed section structure:
   Every ID must use this exact order:
   - Context (what was at stake)
   - Problem (specific contradiction/failure)
   - Options considered (2-3)
   - Decision (what you chose and why)
   - Implementation (what you changed)
   - Result (observable outcome/evidence)
   - Why this proves MLOps/Data Eng strength (explicit hiring signal)
3. Depth requirement:
   No shallow summaries. Each section must explain the actual tension, tradeoffs, and consequences.
4. Truth posture:
   Story must reflect real status honestly (`Resolved`, `Partial`, `Superseded`, `Open`) without exaggeration.
5. Options discipline:
   Include 2-3 realistic alternatives and why the final decision was chosen.
6. Evidence anchoring:
   Include concrete repository evidence paths/lines in every entry.
7. Recruiter readability:
   Write in clear, specific, human language. Avoid logbook tone and unnecessary jargon.
8. Quality gate before moving on:
   Self-check each ID for:
   - Truthfulness
   - Specificity
   - Tradeoff clarity
   - Hiring-signal clarity

## ID 1 - Monolithic and rigid architecture

- Context (what was at stake):
  At this stage, the synthetic data generator was not a toy script anymore. It was becoming the foundation for downstream fraud experimentation, repeatable model work, and eventually platform integration. The risk was not only "can we generate rows?" but "can this system evolve safely as requirements expand?" We were entering a point where changes to realism, config, output targets, or orchestration behavior had to happen frequently and predictably. If the architecture stayed rigid, every new requirement would become slower, riskier, and harder to trust.

- Problem (specific contradiction/failure):
  The contradiction was clear: we needed an extensible system, but the implementation concentrated too many responsibilities in one flow centered around `TransactionSimulator` plus a tightly coupled entrypoint path. In practical terms, catalog-like entity generation, transaction simulation, writing, and output concerns were not cleanly separated. This made the code path harder to reason about and made targeted changes expensive. A system expected to support production-like evolution was being constrained by a structure optimized for a single generation path.

- Options considered (2-3):
  1. Keep the monolith and patch around it with incremental fixes.
     This was the fastest short-term move, but it would preserve the core coupling and keep future changes expensive.
  2. Partially refactor only the highest-friction area (for example, output writing) and defer deeper separation.
     This would reduce some pain but still leave architectural ambiguity about ownership between simulation logic, catalogs, and orchestration behavior.
  3. Perform a deliberate split into clear surfaces: legacy entrypoint, CLI orchestration, core generation/writer functions, and explicit catalog direction.
     This took more design effort upfront, but it aligned better with long-term maintainability and later migration to a stronger engine contract.

- Decision (what you chose and why):
  We chose the deliberate split. The reason was simple: the project had already crossed the threshold where patching a monolith would create compounding complexity. A modular boundary was needed so that different concerns could evolve independently: invocation and runtime controls in CLI, generation mechanics in core functions, and catalog direction as a first-class track rather than hidden logic inside a single simulator class. This decision optimized for architectural durability, not just short-term velocity.

- Implementation (what you changed):
  The architecture moved from a monolithic `TransactionSimulator` flow to a split model. The newer structure kept `generate.py` as a legacy-compatible entrypoint, but routed execution through modular surfaces:
  - `generate.py` acting as bridge/entrypoint,
  - `cli.py` owning argument parsing and runtime wiring,
  - `config.py` path with validated config loading,
  - `core` functions for generation and parquet writing.
  In parallel, the backlog explicitly identified decoupling moves (extract entity-catalog module, split transaction logic, abstract sink interface) to remove responsibility overlap and make the system composable. This was not a cosmetic rewrite. It was a structural correction intended to reduce hidden coupling and make future realism and orchestration work feasible.

- Result (observable outcome/evidence):
  The observable outcome was an architectural transition from a single dense execution path to a modular execution topology with explicit boundaries between entrypoint, CLI, config validation, and generation/writer mechanics. That created a cleaner platform for later replacement by the data engine contract/gate model.
  Evidence anchors:
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:84`
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:86`
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:88`
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:6`
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:17`
  Supporting former-state context:
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_former_data_gen.md:10`
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_former_data_gen.md:18`

- Why this proves MLOps/Data Eng strength (explicit hiring signal):
  This demonstrates architecture judgment under real delivery pressure. Instead of defending a brittle implementation, we identified structural coupling early, chose a design path that separated concerns, and created a migration-friendly base for future contract-driven evolution. For a recruiter, this is a strong signal of production-minded engineering: not just coding features, but reshaping system boundaries so scale, reliability, and team velocity do not collapse as scope grows.

## ID 2 - Data realism and schema fidelity gaps

- Context (what was at stake):
  This challenge sat at the center of model credibility. The generator could produce schema-valid rows, but schema validity alone does not make data useful for fraud modeling. If customer behavior, merchant behavior, geography, time patterns, and fraud patterns are unrealistic, the downstream pipeline can look healthy while training on synthetic artifacts that do not resemble production risk. In other words, the stakes were not cosmetic data quality. The stakes were whether the entire fraud pipeline would learn useful signals or learn noise.

- Problem (specific contradiction/failure):
  The contradiction was: "valid table shape" vs "invalid behavioral shape." The old flow generated many critical fields inline with independent random draws, which broke real-world structure. Specific failures included:
  - no dedicated entity catalogs for customers/merchants/cards,
  - no control over realistic frequency distributions (for example Zipf-like heavy users),
  - uncorrelated merchant country and geolocation behavior,
  - flat timestamp behavior that ignored daily/weekly seasonality,
  - uniform amount generation and Bernoulli-only fraud labels with no hotspot behavior.
  So although rows could pass basic schema checks, the data-generation logic underrepresented the causal and distributional structure that fraud systems depend on.

- Options considered (2-3):
  1. Keep the current row-level random generation and only tweak parameter ranges.
     This would be quick but would not fix the structural realism problem because the core generation assumptions remained independent and weakly correlated.
  2. Patch realism heuristics directly inside the existing row generator.
     This could improve specific symptoms, but it would keep realism logic entangled in one path and make long-term governance/testing difficult.
  3. Introduce explicit catalog-prep and realism tracks (configurable), then use that structure as a bridge toward a stronger data-engine contract path.
     This required more design and operational discipline but created a controllable realism surface and a cleaner migration path.

- Decision (what you chose and why):
  We chose option 3. The reason was that realism needed to become a first-class design surface, not a patch list. We explicitly pushed toward catalog-aware generation (customer/merchant/card populations, configurable behavior distributions) and scenario-style realism plugins (seasonality, hotspot behavior) instead of continuing with purely inline random generation. This gave us a better technical base and made the limitations more explicit, which also helped us make the later decision to supersede the deprecated generator with a stronger engine path.

- Implementation (what you changed):
  Two meaningful changes were made in the deprecated track:
  1. We documented and prioritized realism mechanics as concrete implementation tasks, including Zipfian entity frequency, geo-correlated merchant catalogs, temporal seasonality, and fraud hotspot injection.
  2. We redesigned the flow to include an explicit `Catalog Preparation` stage under config control (`cfg.catalog`, realism mode, prebuild/load catalogs), then connected transaction assembly to sample entities from those catalogs instead of treating all entities as ad-hoc row-level random values.
  In practice, that meant realism moved from "implicit randomness inside one function" to "explicit generation surfaces with configuration, prebuild/load behavior, and reusable catalog context."

- Result (observable outcome/evidence):
  The observable result was a structural upgrade in how realism was handled: a dedicated catalog-prep path and a realism track were introduced, and the architecture reflected that shift. This improved controllability and reduced some of the original realism contradictions. At the same time, we were honest about closure: this deprecated track did not become the final production path, and remaining realism debt was one of the reasons the architecture was ultimately superseded by the Data Engine direction.
  Evidence anchors:
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:122`
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:124`
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:126`
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:128`
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:65`
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:82`
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:93`
  Additional challenge context:
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:17`
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:20`
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:22`
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:24`
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:26`

- Why this proves MLOps/Data Eng strength (explicit hiring signal):
  This shows strong data-engineering judgment: you distinguished schema correctness from behavioral correctness and treated distribution realism as an engineering problem with explicit controls, not a vague "improve quality" request. It also shows MLOps maturity because you made realism configurable and architecture-visible, which is required for repeatable experimentation, defensible model behavior, and future governance. Finally, it shows senior problem-solving honesty: you improved the system materially, identified what remained structurally insufficient, and then moved to a stronger architecture instead of overstating completion.

## ID 3 - Filename vs orchestrator identity mismatch

- Context (what was at stake):
  This was a reliability and traceability problem, not just a naming preference. The pipeline depended on being able to answer a very specific operational question: "What exact run produced this artifact?" In orchestration contexts (especially backfills and reruns), identity must come from orchestrator/run metadata, not from wall-clock assumptions inside a worker. If identity is ambiguous, replay becomes risky, audits become noisy, and downstream joins can silently point to the wrong data slice.

- Problem (specific contradiction/failure):
  The deprecated generator named output using `date.today()` while orchestration paths expected execution-date-oriented identity. That created a contradiction between artifact names and orchestration intent. In practical terms, backfills or clock drift could generate files that looked "today-generated" even when the logical run belonged to a different schedule date. The old architecture explicitly showed this wall-clock naming pattern. So the system could generate a valid file but still break identity integrity across scheduling, storage paths, and downstream retrieval logic.

- Options considered (2-3):
  1. Quick patch in legacy generator: replace `date.today()` with an injected execution date and keep current naming model.
     This would reduce the immediate mismatch but still keep identity tied to filename conventions and not to stronger run receipts/provenance.
  2. Keep legacy behavior and rely on downstream orchestration conventions to "interpret" file identity.
     This was operationally fragile because it depends on conventions and human discipline rather than deterministic identity contracts.
  3. Treat this as a deeper run-identity problem and move to receipt-based deterministic identity in the Data Engine path.
     This requires broader architectural change but solves the root issue: stable run identity independent of incidental file mtimes or wall-clock date calls.

- Decision (what you chose and why):
  We chose option 3. The core reason was that this challenge exposed a design boundary: filename formatting is too weak to be the system of record for run identity. Instead of investing further in legacy naming patches, we moved to deterministic run identity and stable latest-receipt selection in the engine rails. That gave us replay-safe behavior and reduced the chance of silent identity drift when files are touched or rerun later.

- Implementation (what you changed):
  The implementation path had two layers:
  1. In the deprecated track, the mismatch was explicitly diagnosed and a fix direction was documented (`execution_date` alignment instead of `date.today()` assumptions).
  2. In the replacement engine path, identity handling was hardened materially:
     - `utc_day` partitioning was derived from `run_receipt.created_utc` (not wall clock where receipt exists),
     - "latest run receipt" selection moved from raw file mtime toward `created_utc` ordering with fallback behavior,
     - the same stable-receipt posture was propagated into downstream segment behavior.
  This moved identity semantics from "naming convention hygiene" to "receipt-backed deterministic run identity."

- Result (observable outcome/evidence):
  The outcome was a stronger, replay-safe identity posture:
  - the original mismatch was concretely identified in the deprecated path,
  - the old architecture showed why the mismatch occurred (`date.today()` naming),
  - the final adopted approach shifted to receipt-driven deterministic run identity in engine segments.
  Truth posture: this challenge is best classified as `Superseded` in the deprecated generator because the durable fix landed through architectural replacement, not by deeply extending the old naming flow.
  Evidence anchors:
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:109`
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_former_data_gen.md:448`
  - `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md:3300`
  - `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:3129`
  Additional context anchors:
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:34`
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:35`
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:265`
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:267`
  - `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md:3304`
  - `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_actual.md:3305`
  - `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:3133`

- Why this proves MLOps/Data Eng strength (explicit hiring signal):
  This proves you can recognize when a "small bug" is actually a systems-level identity flaw. Instead of over-focusing on filename cosmetics, you moved identity to deterministic, receipt-backed semantics that survive reruns, backfills, and file-touch noise. For hiring managers, that is a high-value signal: you build data platforms that are auditable, replayable, and operationally trustworthy, which is core to both MLOps and serious data engineering.

## ID 4 - CWD-relative schema path portability failures

- Context (what was at stake):
  This challenge sat in the reliability path of every run. If schema discovery depends on where a command is launched from, then run success becomes environment-dependent instead of contract-dependent. That is dangerous for any MLOps/data platform because local runs, container runs, CI jobs, and orchestration workers naturally have different working directories. The stake was simple but critical: either schema resolution is deterministic, or the pipeline fails unpredictably across environments.

- Problem (specific contradiction/failure):
  The deprecated generator loaded `schema/transaction_schema.yaml` via a CWD-relative path. The contradiction was that the system was expected to be runnable in multiple execution contexts, but schema loading assumed one specific invocation posture. So the same code could pass in one shell and fail in another with "schema not found." This was not a data-quality issue; it was a portability contract failure at startup.

- Options considered (2-3):
  1. Keep CWD-relative schema loading and enforce a strict "run from project root" operator rule.
     This is fragile because it depends on human discipline and breaks quickly under container/orchestrator variation.
  2. Move to config-driven schema resolution (`--config` + validated model) in the generator path.
     This improves portability by making schema/config location explicit and validated at runtime.
  3. In the replacement engine path, harden schema resolution beyond file location by handling reference-pack resolution deterministically under strict validation.
     This addresses deeper schema portability/reliability issues, including external reference resolution failures.

- Decision (what you chose and why):
  We chose a layered approach: adopt option 2 as the immediate correction in the deprecated track, then carry the durable posture through option 3 in the engine path. The reason was practical engineering sequencing. First remove CWD dependence by making config loading explicit and validated; then harden full schema-pack resolution under strict validators so portability does not collapse on cross-schema references.

- Implementation (what you changed):
  The implementation unfolded in two phases:
  1. Deprecated generator architecture:
     - exposed `--config` in CLI,
     - routed startup through `load_config(args.config)`,
     - validated loaded config using a typed model (`GeneratorConfig.model_validate`).
     This moved startup behavior away from implicit path assumptions.
  2. Engine hardening path:
     - when strict validation hit unresolved external refs (for example `schemas.layer1.yaml#/$defs/...`), resolution was hardened by introducing local reference-pack handling rather than relaxing validation.
     - this preserved strictness while making schema resolution deterministic across runtime contexts.
  So the fix was not just "change a path string." It evolved from explicit config-driven load boundaries to robust schema reference resolution behavior.

- Result (observable outcome/evidence):
  The observable result was portability and validation reliability improvement:
  - the CWD-relative schema-path risk was explicitly diagnosed,
  - the current architecture showed config-driven loading and validation,
  - the replacement engine path demonstrated strict schema resolution hardening when external references failed.
  Truth posture: `Superseded`. The deprecated generator issue was real and addressed directionally, but the durable reliability posture came through the engine migration path.
  Evidence anchors:
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:107`
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:20`
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:34`
  - `docs/references/deprecated_[DATA-GEN]_high_level_arch_CURRENT_data_gen.md:38`
  - `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:317`
  Additional challenge context:
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:36`
  - `docs/references/deprecated_[DATA-GEN]_issues_with_data_generator.md:37`
  - `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:313`
  - `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:321`
  - `docs/model_spec/data-engine/implementation_maps/segment_2A.impl_actual.md:329`

- Why this proves MLOps/Data Eng strength (explicit hiring signal):
  This demonstrates production-grade thinking about portability and contract integrity. You did not treat environment-dependent startup failures as "operator mistakes." You moved toward explicit, validated runtime inputs and then hardened strict schema resolution when real validator failures appeared. That is a direct hiring signal for both MLOps and Data Engineering roles: you build systems that run consistently across local/dev/orchestrated environments without weakening correctness standards.
