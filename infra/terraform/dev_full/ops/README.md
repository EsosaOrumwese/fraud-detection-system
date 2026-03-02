# dev_full ops stack

This stack materializes M2.H operations/control surfaces required by dev_full substrate readiness:

- IAM role:
  - `ROLE_MWAA_EXECUTION`
- SSM paths:
  - `/fraud-platform/dev_full/mwaa/webserver_url`
  - `/fraud-platform/dev_full/aurora/endpoint`
  - `/fraud-platform/dev_full/aurora/reader_endpoint`
  - `/fraud-platform/dev_full/aurora/username`
  - `/fraud-platform/dev_full/aurora/password`
  - `/fraud-platform/dev_full/redis/endpoint`

Notes:
- This stack is intentionally bounded to M2 control-surface materialization and secret-path contracts.
- Full production workload services remain in later phase lanes.
