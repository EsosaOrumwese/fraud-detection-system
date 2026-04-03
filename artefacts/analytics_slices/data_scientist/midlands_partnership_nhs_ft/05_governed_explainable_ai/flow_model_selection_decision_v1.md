# Flow Model Selection Decision v1

Selected model:
- `challenger_logistic_encoded_history`

Decision reason:
- selected because the validation uplift materially exceeded the simpler baseline despite the added governance and explanation burden

Validation comparison:
- baseline validation ROC AUC: 0.5194
- challenger validation ROC AUC: 0.6228
- baseline validation High-band truth rate: 2.13%
- challenger validation High-band truth rate: 6.31%

Governance interpretation:
- the baseline remains the more directly explainable option
- the challenger adds encoded historical-risk features derived from the training window and therefore needs stronger explanation and maintenance discipline
