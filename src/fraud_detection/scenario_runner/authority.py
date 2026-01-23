"""Run authority: equivalence registry and lease management."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .ids import hash_payload, run_id_from_equivalence_key


@dataclass(frozen=True)
class RunHandle:
    run_id: str
    intent_fingerprint: str
    leader: bool
    lease_token: str | None
    status_ref: str | None = None
    facts_view_ref: str | None = None


class EquivalenceRegistry:
    def __init__(self, root: Path) -> None:
        self.path = root / "equivalence.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def resolve(self, run_equivalence_key: str, intent_fingerprint: str) -> tuple[str, bool]:
        data = self._read()
        if run_equivalence_key in data:
            existing = data[run_equivalence_key]
            if existing["intent_fingerprint"] != intent_fingerprint:
                raise RuntimeError("EQUIV_KEY_COLLISION")
            return existing["run_id"], False
        run_id = run_id_from_equivalence_key(run_equivalence_key)
        data[run_equivalence_key] = {
            "run_id": run_id,
            "intent_fingerprint": intent_fingerprint,
            "first_seen_at": datetime.now(tz=timezone.utc).isoformat(),
            "last_seen_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        self._write(data)
        return run_id, True

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


class LeaseManager:
    def __init__(self, root: Path, ttl_seconds: int = 300) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def acquire(self, run_id: str, owner_id: str) -> tuple[bool, str | None]:
        path = self.root / f"{run_id}.json"
        now = datetime.now(tz=timezone.utc)
        token = hash_payload(f"{run_id}|{owner_id}|{now.isoformat()}")
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            expires_at = datetime.fromisoformat(data["expires_at"])
            if expires_at > now:
                return False, None
        payload = {
            "owner_id": owner_id,
            "lease_token": token,
            "expires_at": (now + timedelta(seconds=self.ttl_seconds)).isoformat(),
        }
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        return True, token

    def renew(self, run_id: str, lease_token: str) -> bool:
        path = self.root / f"{run_id}.json"
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("lease_token") != lease_token:
            return False
        now = datetime.now(tz=timezone.utc)
        data["expires_at"] = (now + timedelta(seconds=self.ttl_seconds)).isoformat()
        path.write_text(json.dumps(data, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        return True
