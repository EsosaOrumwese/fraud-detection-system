from pathlib import Path

from fraud_detection.event_bus import FileEventBusPublisher


def test_offsets_are_monotonic(tmp_path: Path) -> None:
    bus = FileEventBusPublisher(tmp_path)
    ref1 = bus.publish("fp.bus.traffic.v1", "k1", {"event_id": "evt-1"})
    ref2 = bus.publish("fp.bus.traffic.v1", "k2", {"event_id": "evt-2"})
    assert ref1.offset_kind == "file_line"
    assert ref1.offset == "0"
    assert ref2.offset == "1"


def test_head_recovers_from_missing(tmp_path: Path) -> None:
    bus = FileEventBusPublisher(tmp_path)
    bus.publish("fp.bus.traffic.v1", "k1", {"event_id": "evt-1"})
    head = tmp_path / "fp.bus.traffic.v1" / "head.json"
    head.unlink()
    ref2 = bus.publish("fp.bus.traffic.v1", "k2", {"event_id": "evt-2"})
    assert ref2.offset == "1"


def test_head_recovers_when_log_missing(tmp_path: Path) -> None:
    topic_dir = tmp_path / "fp.bus.traffic.v1"
    topic_dir.mkdir(parents=True)
    (topic_dir / "head.json").write_text('{"next_offset": 7}', encoding="utf-8")
    bus = FileEventBusPublisher(tmp_path)
    ref = bus.publish("fp.bus.traffic.v1", "k1", {"event_id": "evt-1"})
    assert ref.offset == "0"
