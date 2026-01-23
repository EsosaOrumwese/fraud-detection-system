# Evidence - Layer 2 Data Intake

Created: 2025-12-31
Purpose: record new paths and realism checks per artefact.

Use one section per artefact:
- artefact_id:
- new_path:
- realism_checks:

- artefact_id: merchant_class_policy_5A
  new_path: config/layer2/5A/policy/merchant_class_policy_5A.v1.yaml
  realism_checks: MCC sector map covers all 290 merchant MCCs; 10-class catalog present; channel_group map covers card_present/card_not_present. Distribution checks against zone_alloc pending (zone_alloc not yet materialized).

- artefact_id: demand_scale_policy_5A
  new_path: config/layer2/5A/policy/demand_scale_policy_5A.v1.yaml
  realism_checks: Class table and tail parameters set to v1 defaults; global_multiplier calibrated to target mean using merchant universe with deterministic UTC tzid fallback and zone_site_count=1 proxy. Recalibrate once zone_alloc exists.

- artefact_id: baseline_intensity_policy_5A
  new_path: config/layer2/5A/policy/baseline_intensity_policy_5A.v1.yaml
  realism_checks: Tolerances within floors; hard_fail clip mode; caps set above toy limits.

- artefact_id: shape_library_5A
  new_path: config/layer2/5A/policy/shape_library_5A.v1.yaml
  realism_checks: 90 templates (>=40) with >=3 per class/channel; constraints validated for night mass, weekend mass, office-hours mass, and nonflatness.

- artefact_id: scenario_horizon_config_5A
  new_path: config/layer2/5A/scenario/scenario_horizon_config_5A.v1.yaml
  realism_checks: Two scenarios (baseline + stress), 60-minute buckets, horizons 59-90 days, bucket-aligned UTC timestamps.

- artefact_id: scenario_overlay_policy_5A
  new_path: config/layer2/5A/scenario/scenario_overlay_policy_5A.v1.yaml
  realism_checks: Event vocab and bounds set per v1; multiplicative clamp [0,5]; max_events_per_scenario=50000 and overlap cap=20.

- artefact_id: scenario_calendar_5A
  new_path: config/layer2/5A/scenario/calendar/fingerprint=e22b195ba9fa8ed582f4669a26009c67637760bfe3b51c9ac77af92b6aa572e9/scenario={baseline_v1,stress_peak_online_v1}/scenario_calendar_5A.parquet
  realism_checks: baseline_v1=4356 events, stress_peak_online_v1=2947 events; country coverage=183 for both; max overlap sample {baseline:2, stress:3}; event types include PAYDAY/HOLIDAY/CAMPAIGN/OUTAGE/(STRESS for stress).
