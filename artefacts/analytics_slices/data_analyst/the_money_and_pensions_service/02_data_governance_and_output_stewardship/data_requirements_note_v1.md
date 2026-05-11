
# Data Requirements Note v1

Required field count:
- `10`

Required dimensions:
- `amount_band`
- `band_label`

Required control fields:
- `stream_coverage_count`
- `attention_confirmation_count`
- `aligned_attention_flag`
- `cross_source_reading`

Why these requirements matter:
- they keep the mixed-source lane structured
- they make the cross-source signal auditable
- they ensure the governed summary and supporting detail outputs rest on the same explicit logic
