# Confluent module (dev_min)

Purpose:
- provision Confluent Cloud environment + Kafka cluster,
- create pinned topic map,
- create runtime Kafka API key owned by a runtime service account.

Notes:
- Confluent Cloud management credentials are provided by the root stack provider config.
- Runtime Kafka credentials are output by this module and should be written to pinned SSM paths by the root stack.
