# `hurdle_coefficients.yaml` Visualization Targets

These plots support the coefficient-bundle investigation. The goal is not to decorate the report; it is to expose the statistical surfaces that make the bundle interpretable.

- Show the training corpus surfaces the bundle came from: `y_hurdle` in `logistic.parquet`, `y_nb` in `nb_mean.parquet`, and how their distributions differ by channel and GDP bucket.
- Show the active bundle's structural shape: the `beta` hurdle lane, the `beta_mu` NB-mean lane, their intercept/channel/bucket terms, and their MCC spread.
- Show which MCC coefficients are doing the strongest work in each lane, because the MCC blocks are broad and contain extreme pushes and suppressions.
- Show the active runtime scoring surface: emitted/diagnostic `pi`, realized `is_multi`, and how observed branch outcomes relate to probability bands.
- Show how the bundle family moved over time, separating the hurdle-lane remediation from the NB-mean-lane remediation.
- Show original January export versus active February bundle deltas, so the active bundle is read as a remediated descendant rather than a direct pristine export.
