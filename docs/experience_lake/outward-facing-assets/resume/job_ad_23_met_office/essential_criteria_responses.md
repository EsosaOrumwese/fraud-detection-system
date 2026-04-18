## Criterion 1 — Lead criterion

**Experience and knowledge in a physical or environmental science, mathematics, statistics and/or data science, gained through a relevant degree or subsequent professional experience and/or postgraduate qualification.**

I meet this criterion through a combination of formal scientific training and applied analytical work. My academic route combines a first-class degree in Mechanical Engineering with an MSc in Data Science with Artificial Intelligence (Distinction). That gave me a strong grounding in mathematics, modelling, statistics, signal interpretation, and scientific reasoning, which I then extended through substantial hands-on data-science work.

A strong academic example is my masters thesis on multitask learning for driver identification and transport-mode classification using smartphone sensor data. I worked with 227 hours of labelled 100Hz accelerometer, gyroscope, and rotation-vector data, covering 81,938,560 raw records, and reduced this to a controlled modelling surface of 4,096,928 records through preprocessing and downsampling. I transformed device-coordinate signals into Earth-coordinate representations using quaternions, Euler angles, and rotation matrices, and implemented BiLSTM, ResNet50-GRU, and multitask deep-learning models in Python/PyTorch, with hyperparameter tuning through Ray Tune.

I then carried the same foundation into applied analytical delivery on a governed fraud platform, where I used Python, SQL, R, and structured workflows to build prioritisation, forecasting, and impact-modelling outputs over large operational datasets. One predictive-modelling slice delivered 2.29x baseline yield in the highest-risk band, captured 41.3% of positives in the top 20.1% of scored flows, and achieved 7.31% test MAPE on bounded daily demand forecasting. In a separate strategy comparison, I quantified a tighter preferred decision posture that reduced selected-flow burden by 511,500 and downstream case-handling activity by 1,185,849 while improving fraud-truth yield from 12.06% to 12.37%.

The strongest honest case I have for this criterion is through physical-science training, mathematics/statistics, and applied data science rather than through direct climate specialism. What I would bring to this role is a solid quantitative base, experience working from observed systems into computational models, and the ability to turn that work into something decision-useful.

## Criterion 2

**Effective oral and written communication skills, with demonstrated ability to convey complex scientific and technical information clearly and with impact to a range of audiences.**

A strong example came in Mar 2026, when I had to explain the difference between a broader and a tighter fraud-selection posture. The challenge was not just presenting the numbers. It was explaining what they meant for the full operating chain: how many events would be selected for review, how much downstream case-handling work that would create, and how concentrated the confirmed outcomes would be within that reviewed population.

I wrote the result as a review pack rather than leaving it as a comparison table. The tighter posture improved confirmed fraud yield from 12.06% to 12.37%, reduced selected-flow burden by 511,500, reduced downstream case-event burden by 1,185,849, and still retained 89.53% of the positives found by the broader posture. The important part was the interpretation. I made it clear that the tighter posture was not simply “better” in the abstract. It meant a smaller review population, less downstream handling work, and a higher concentration of confirmed outcomes, but at the cost of giving up part of the broader posture’s capture.

When I explained the same result orally, I changed the emphasis depending on the audience. Technical readers needed the validity of the comparison and the yield-versus-capture trade-off. Operations-facing readers needed the workload implication. Decision-focused readers needed the choice stated plainly: use the tighter posture if the priority is a more selective and efficient review population, but not if the priority is to push the widest possible set of positives through the workflow.

The result was that the analysis could be used as a real decision object rather than as a technical output. The main thing I have learned is that good technical communication is not about simplifying everything down. It is about keeping the technical truth intact while making the decision meaning clear to the people who need to act on it.

## Criterion 3

**Good organisational skills, with an ability to plan your own work and collaborate with others to deliver significant contributions to high quality scientific outputs while meeting tight deadlines.**

The clearest example for this criterion came during my masters in a group project on the Bi-objective Travelling Thief Problem linked to the GECCO2019 competition. It was a research-led optimisation problem with a fixed deadline, limited compute, and a team where only 4 of the 6 members remained consistently active through the work. The standard still had to stay high: we needed a coherent scientific method, a working implementation, and a report that explained both the algorithm and the constraints honestly.

I helped structure the work into smaller functional responsibilities across the active team and made sure my own contribution stayed aligned with the wider method. My direct contribution included implementing the NSGA2 survival logic through non-dominated sorting and crowding distance, and building local-search logic using 2-opt improvement for the TSP component and random bit-flip search for the Knapsack component. Just as importantly, I had to plan my work so it would integrate properly with the rest of the algorithm rather than sit as an isolated piece of code.

As constraints became clearer, we adapted the plan. The full parameter settings from the reference paper were too expensive for the dataset sizes and the available compute, so we shifted to smaller tests and focused on producing a solid, explainable implementation and report within the deadline. That meant keeping the delivery standard fixed while adjusting the way we got there.

The project was delivered as a working optimisation implementation and a strong scientific report that explained the problem, algorithm, implementation logic, and limits on performance. What I took from that experience is that good organisation in scientific work is not rigid task-tracking. It is knowing how to structure work, integrate with others, and adapt the method when time, compute, or team capacity changes.

## Criterion 4

**An ability to discuss diverse user needs and propose appropriate solutions, and to apply your scientific and analytical skills to generate user-relevant insights.**

A strong example came from a predictive-modelling slice I built in Apr 2026. Different users needed different things from the same controlled dataset. Operations users needed to know which suspicious flows were most worth prioritising because review capacity was limited. Planning users needed a short-range view of likely case demand. Review and control users needed the work to stay reproducible and inspectable rather than becoming an open-ended modelling exercise.

I framed the work around one focused question: which suspicious flows were more likely to lead to confirmed fraud outcomes, and what did that imply for near-term case demand? From that, I proposed a bounded solution rather than a broad modelling programme: build a flow_id-level risk-stratification surface, convert the scores into interpretable High, Medium, and Low cohorts, and add a lightweight daily case-demand forecast so the same slice could support planning as well as prioritisation.

The delivered model base contained 2,073,369 training rows, 691,122 validation rows, 691,122 test rows, and 17 model features. Using a bounded statsmodels binomial logistic model, the High band covered only 4.9% of scored test flows but achieved 6.26% fraud-truth yield, or 2.29x the overall test baseline. The combined High and Medium queue covered 20.1% of scored flows while capturing 41.3% of all test positives at 2.06x baseline yield. A bounded daily case-demand forecast achieved 7.31% test MAPE.

The value of that work was that it answered multiple user needs through one coherent analytical slice. It gave operations users a practical prioritisation surface, gave planning users a short-range demand view, and kept the work bounded enough to remain reviewable. The main lesson for me was that user-relevant insight starts with the decision problem, not with the model family. The right solution is the one people can actually use.

## Criterion 5

**Strong scientific computing skills, with experience of coding, especially in Python, and/or using advanced tools for data analysis and visualisation. Experience of applying recognised approaches to software quality assurance.**

The same predictive-modelling slice is also the strongest example of my scientific computing capability, because it required coding, advanced analysis, visualisation, and quality assurance to work together. The task was not only to analyse data. It was to build a bounded and technically trustworthy analytical product over a large governed run without relying on uncontrolled notebook exploration.

I kept the execution SQL-first so the large source surfaces were shaped safely before any in-memory modelling work began. I inspected schema and bounded aggregates in SQL, materialised a model-ready flow table and downstream cohort and forecast-support tables in SQL, and only moved the already-shaped slice into Python for modelling and evaluation. In Python, I built the scoring layer with a statsmodels binomial logistic model, used time-based train, validation, and test windows, and created interpretable cohorts from the validation score distribution.

I also produced figures showing risk-band performance, validation and test stability, cohort separation against both fraud-truth and bank-view outcomes, and forecast-versus-actual case-demand behaviour. For quality assurance, I used time-based splits rather than random mixing, train-only smoothed entity fraud-rate encodings to avoid leakage, saved both the SQL shaping logic and the Python modelling logic, preserved source traceability through bounded_file_selection.json, and kept machine-readable metrics and figure artefacts so the work could be checked and rerun.

The result was a usable prioritisation and planning surface rather than just a coded experiment. On the test window, the High band achieved 2.29x baseline yield, the top 20.1% of scored flows captured 41.3% of positives, and the daily forecast achieved 7.31% test MAPE. Just as importantly, the slice was technically reviewable and reproducible. The main lesson I have taken from this is that strong scientific computing is not only about being able to code in Python. It is about structuring the full workflow so the analysis is bounded, the logic is defensible, the outputs are inspectable, and the results can be rerun without ambiguity.

## Criterion 6

N/A

## Criterion 7

N/A

