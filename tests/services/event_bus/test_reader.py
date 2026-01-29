from pathlib import Path

from fraud_detection.event_bus import EventBusReader, FileEventBusPublisher


def _publish(bus: FileEventBusPublisher, count: int) -> None:
    for idx in range(count):
        bus.publish("fp.bus.traffic.v1", f"k{idx}", {"event_id": f"evt-{idx}"})


def test_reader_returns_offsets(tmp_path: Path) -> None:
    bus = FileEventBusPublisher(tmp_path)
    _publish(bus, 3)
    reader = EventBusReader(tmp_path)
    records = reader.read("fp.bus.traffic.v1", from_offset=0, max_records=10)
    assert [record.offset for record in records] == [0, 1, 2]
    assert records[0].record["payload"]["event_id"] == "evt-0"


def test_reader_from_offset(tmp_path: Path) -> None:
    bus = FileEventBusPublisher(tmp_path)
    _publish(bus, 5)
    reader = EventBusReader(tmp_path)
    records = reader.read("fp.bus.traffic.v1", from_offset=3, max_records=10)
    assert [record.offset for record in records] == [3, 4]
