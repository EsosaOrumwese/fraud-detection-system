"""Runtime dataclasses shared between S5 and S6."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class RouterVirtualArrival:
    """Virtual arrival emitted by S5 for S6 consumption."""

    merchant_id: int
    utc_timestamp: datetime
    utc_day: str
    tz_group_id: str
    site_id: int
    selection_seq: int
    is_virtual: bool

    def normalised_timestamp(self) -> datetime:
        """Return the timestamp normalised to UTC."""

        ts = self.utc_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)


__all__ = ["RouterVirtualArrival"]
