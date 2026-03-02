"""Event Bus interfaces + adapters."""

from .publisher import EbRef, EventBusPublisher, FileEventBusPublisher
from .reader import EbRecord, EventBusReader

__all__ = [
    "EbRef",
    "EventBusPublisher",
    "FileEventBusPublisher",
    "KafkaEventBusPublisher",
    "EbRecord",
    "EventBusReader",
]


def __getattr__(name: str):
    if name == "KafkaEventBusPublisher":
        from .kafka import KafkaEventBusPublisher

        return KafkaEventBusPublisher
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
