# dev_full streaming stack

This stack materializes the `dev_full` streaming substrate required by M2.C:

1. MSK Serverless cluster with IAM SASL auth posture.
2. Bootstrap-broker materialization into SSM secure parameter.
3. Glue schema registry baseline + anchor schema with pinned compatibility mode.

Input network handles are sourced from `dev_full/core` remote state by default and can be overridden explicitly when required.
