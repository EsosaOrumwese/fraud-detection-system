import os

import pytest

from fraud_detection.event_bus.kinesis import KinesisConfig, KinesisEventBusPublisher


@pytest.mark.skipif(
    not os.getenv("KINESIS_ENDPOINT_URL"),
    reason="KINESIS_ENDPOINT_URL not set for LocalStack",
)
def test_kinesis_publish_smoke() -> None:
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    stream_name = os.getenv("KINESIS_STREAM_NAME", "sr-control-bus")
    publisher = KinesisEventBusPublisher(
        KinesisConfig(
            stream_name=stream_name,
            region=os.getenv("AWS_DEFAULT_REGION"),
            endpoint_url=os.getenv("KINESIS_ENDPOINT_URL"),
        )
    )
    ref = publisher.publish("fp.bus.traffic.v1", "smoke", {"event_id": "evt-kinesis"})
    assert ref.offset_kind == "kinesis_sequence"
    assert ref.offset
