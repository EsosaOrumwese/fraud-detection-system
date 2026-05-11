# Flow Model Explanation Pack v1

Selected model:
- `challenger_logistic_encoded_history`

Main score drivers by absolute coefficient:
- `device_train_fraud_rate`: coefficient 192.3505
- `instrument_train_fraud_rate`: coefficient 192.3505
- `party_train_fraud_rate`: coefficient 192.3505
- `account_train_fraud_rate`: coefficient 192.3505
- `log_party_flow_count`: coefficient -43.7425
- `merchant_train_fraud_rate`: coefficient 33.5483
- `log_device_flow_count`: coefficient 21.2467
- `log_instrument_flow_count`: coefficient 10.0683

Explanation reading:
- the selected model remains reviewable because it is coefficient-based logistic scoring
- if the challenger is selected, the added drivers are encoded historical-risk features rather than opaque tree logic
- this keeps the slice explainable enough for challenge while still allowing a governed performance comparison
