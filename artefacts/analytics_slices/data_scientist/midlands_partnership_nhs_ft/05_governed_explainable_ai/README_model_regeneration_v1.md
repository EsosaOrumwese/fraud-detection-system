# README - Model Regeneration v1

Regeneration order:
1. reuse the bounded file selection in `logs/bounded_file_selection.json`
2. run the SQL governance gate
3. build `flow_model_ready_slice_v1.parquet`
4. build `flow_model_ready_slice_v2_encoded.parquet`
5. run `build_governed_explainable_ai.py`

Required review before recirculation:
- confirm source rules still hold
- confirm leakage boundaries still hold
- confirm model-choice and threshold notes still match outputs
