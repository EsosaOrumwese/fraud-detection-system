# Preliminary Responses - Job Ad 23 - Met Office

Purpose:
- work through each essential criterion before drafting the final form responses
- keep the evidence grounded in actual platform and work history
- make the `CARL` structure explicit so the final answers are easier to score and easier to compress

Important note:
- the live Met Office ad has `5` essential criteria
- criterion `1` is the **lead criterion**
- the application form may allow `7` boxes, but only `5` need substantive answers

---

## Criterion 1 - Lead Criterion

**Essential criterion**

Experience and knowledge in a physical or environmental science, mathematics, statistics and/or data science, gained through a relevant degree or subsequent professional experience and/or postgraduate qualification.

**Context**
- My strongest route into this criterion is through physical science, mathematics, statistics, and data science rather than through a direct environmental-science specialism.
- I bring that mix from three places that fit together cleanly:
  - a first-class undergraduate grounding in mechanical engineering and later field exposure in a technical oilfield environment where equipment behaviour, pressure, temperature, and signal interpretation mattered;
  - a postgraduate qualification in `MSc Data Science with Artificial Intelligence (Distinction)`;
  - subsequent professional experience on the governed fraud platform, where I have been applying statistical, predictive, and time-aware analytical methods to large operational datasets in a production-shaped analytical setting.
- I also have supporting masters-level project work that widened that base beyond one narrow modelling type:
  - a multitask deep-learning thesis on smartphone sensor data;
  - a game-theoretic network-analysis study for counterterrorism surveillance prioritisation;
  - a pandemic business-activity and government-policy time-series analysis;
  - multi-objective optimisation work using evolutionary methods.

**Action**
- In the strongest academic example, my masters thesis, I worked with raw physical-signal data from smartphone accelerometers, gyroscopes, and rotation-vector sensors using the `SHL` dataset preview subset: `227` hours of labelled `100Hz` data and `81,938,560` raw records. I reduced that to `4,096,928` records through controlled downsampling, built journey segmentation and sub-segmentation logic, transformed device-coordinate signals into Earth-coordinate representations using quaternions, Euler angles, and rotation matrices, and then implemented `BiLSTM`, `ResNet50-GRU`, and multitask deep-learning models in `Python`/`PyTorch`, with hyperparameter tuning through `Ray Tune`.
- In parallel masters work, I applied mathematical and statistical reasoning to materially different problem classes rather than only one modelling pattern:
  - used game-theoretic centrality, graph methods, and `NetworkX` to rank key actors in a pre-attack terrorist network and turn that into a bounded surveillance recommendation;
  - combined `1,004` daily Facebook business-activity files into a `2,396,549`-row time-series base, then integrated policy data to interpret how external interventions related to business recovery patterns across countries;
  - implemented `NSGA2`-style non-dominated sorting, crowding distance, and local-search logic for a bi-objective travelling thief optimisation problem.
- In subsequent professional work on the platform, I moved from academic analysis into applied statistical and data-science delivery. I used `Python`, `SQL`, `R`, and structured analytical workflows to build prioritisation, forecasting, and impact-modelling outputs over governed fraud data, comparing alternative decision postures, quantifying uncertainty and trade-offs, and turning model behaviour into reviewable decision-support material.

**Result**
- The academic route gives me formal depth:
  - `MSc Data Science with Artificial Intelligence (Distinction)`;
  - first-class undergraduate training in a physical-science/engineering discipline.
- The thesis and project work gave me evidence across physical-signal modelling, mathematical transformation, statistical evaluation, time-series interpretation, optimisation, and network science rather than only classroom exposure.
- The professional route shows that I can apply that grounding to consequential analytical problems. On the platform, the work delivered:
  - `2.29x` baseline yield in the highest-risk band;
  - capture of `41.3%` of positives in the top `20.1%` of scored flows;
  - `7.31%` test `MAPE` on bounded daily demand forecasting;
  - a tighter preferred decision posture that reduced selected-flow burden by `511,500` and downstream case-handling activity by `1,185,849` while improving fraud-truth yield from `12.06%` to `12.37%`.
- Taken together, that gives me a defensible evidence base for this criterion through degree-level study, postgraduate data science, and subsequent applied analytical delivery.

**Learning**
- The main learning from this path is that I work best where observed systems, mathematical structure, and decision use meet.
- My background has made me comfortable moving between physical behaviour, statistical reasoning, computational modelling, and user-facing interpretation:
  - from field signals and equipment context,
  - to sensor and time-series data,
  - to optimisation and network analysis,
  - to production-shaped data-science work over governed operational data.
- That is the strongest honest case for this lead criterion: I am not claiming a specialist climate-science background I do not have, but I can show a strong and sustained base in physical-science thinking, mathematics/statistics, and applied data science, gained through formal qualifications and then extended through substantial hands-on analytical work.

---

## Criterion 2

**Essential criterion**

Effective oral and written communication skills, with demonstrated ability to convey complex scientific and technical information clearly and with impact to a range of audiences.

**Context**
- The strongest example from my recent work came in a `Mar 2026` platform review where I had to explain the difference between a broader and a tighter fraud-selection posture to readers who cared about different parts of the same operating journey.
- The underlying analytical question was whether the platform should continue sending a broader review population into downstream case handling, or move to a tighter posture that concentrated more strongly on likely fraud.
- The real stakeholder issue was not the metric on its own. It was what the metric meant for the operating chain from suspicious events to case workload to confirmed fraud outcomes. If I did not explain that chain clearly, the work could easily be misread as “the tighter option is simply better,” when the actual result was more conditional than that.

**Action**
- I wrote the result up as a review pack rather than leaving it as a model comparison. The written output kept the comparison tied to the operating questions people would actually care about:
  - how many flows would be sent forward for review;
  - how much downstream case activity that would create;
  - how concentrated the confirmed fraud outcomes would be within that reviewed population;
  - what would be lost if the gate became tighter.
- In the write-up, I kept three figures explicit:
  - the tighter posture improved confirmed fraud yield from `12.06%` to `12.37%`;
  - it reduced selected-flow burden by `511,500` and downstream case-event burden by `1,185,849`;
  - it retained `89.53%` of the broader posture’s positives, which meant some capture was still being given up.
- The important communication step was not stating those numbers, but interpreting them against the operating journey. I made the written message clear: the tighter posture did not mean “better fraud performance” in the abstract. It meant a smaller review population, less downstream handling work, and a higher concentration of confirmed fraud inside the work that remained, but at the cost of giving up part of the broader posture’s fraud capture.
- When explaining the same result orally, I adjusted the emphasis by audience:
  - for technical readers, I focused on why the comparison was valid and why the yield-versus-capture trade-off was genuine;
  - for operations-facing readers, I focused on what `511,500` fewer selected flows and `1,185,849` fewer downstream case events meant in practice: a lighter review burden and a smaller workload moving into case handling;
  - for decision-focused readers, I stated the decision plainly: choose the tighter posture if the priority is a more selective and efficient review population, but not if the priority is to push the widest possible set of positives through the workflow.

**Result**
- The result was that the analysis could be used as a real decision object rather than as a technical comparison table.
- Instead of readers taking away only that the tighter posture had a slightly better yield, they could see the full operating meaning: it created a more selective review population, reduced downstream handling burden, and concentrated confirmed fraud more effectively, but it was not the right choice if the business wanted maximum capture from the broader gate.
- That is what made the communication effective. It linked the technical result to the actual choice in front of the stakeholders: what kind of review posture they wanted to run, and what burden-versus-capture balance they were willing to accept.

**Learning**
- The main learning for me has been that effective communication in technical work is not about restating the metrics in simpler words. It is about tying the metrics back to the operating question the stakeholder is actually trying to answer.
- In this platform context, that means explaining where an analytical result sits in the event-to-case-to-outcome chain, what part of the workflow it changes, and what choice it creates for the people running that workflow.
- That is the strongest evidence I have for this criterion from recent experience: I can take a trade-off-heavy analytical result, keep the technical truth intact, and still explain it in a way that helps different audiences understand the operational choice in front of them.

---

## Criterion 3

**Essential criterion**

Good organisational skills, with an ability to plan your own work and collaborate with others to deliver significant contributions to high quality scientific outputs while meeting tight deadlines.

**Context**
- To be completed

**Action**
- To be completed

**Result**
- To be completed

**Learning**
- To be completed

---

## Criterion 4

**Essential criterion**

An ability to discuss diverse user needs and propose appropriate solutions, and to apply your scientific and analytical skills to generate user-relevant insights.

**Context**
- To be completed

**Action**
- To be completed

**Result**
- To be completed

**Learning**
- To be completed

---

## Criterion 5

**Essential criterion**

Strong scientific computing skills, with experience of coding, especially in Python, and/or using advanced tools for data analysis and visualisation. Experience of applying recognised approaches to software quality assurance.

**Context**
- To be completed

**Action**
- To be completed

**Result**
- To be completed

**Learning**
- To be completed

---

## Notes

- Potential evidence families:
  - `Midlands 01_predictive_modelling`
  - `Imperial 02_large_scale_time_series_longitudinal_analysis_and_quantitative_research_support`
  - `JPMorganChase 01_fraud_strategy_and_rule_optimisation`
  - `JPMorganChase 02_fraud_operations_and_product_impact_analytics`
  - `Field Engineer (Trainee)` for safety-conscious technical context and technical communication
- Keep the domain boundary honest:
  - no fake environmental-science ownership
  - no fake defence-domain ownership
  - strong transfer on applied analysis, scientific computing, problem framing, reporting, and technical communication
