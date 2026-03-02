from __future__ import annotations

import json
import os
from datetime import datetime, timezone


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    payload = {
        "component": "ofs_build_v0",
        "captured_at_utc": now_utc(),
        "platform_run_id": os.getenv("platform_run_id", ""),
        "scenario_run_id": os.getenv("scenario_run_id", ""),
        "m10_execution_id": os.getenv("m10_execution_id", ""),
        "status": "BOOTSTRAP_OK",
        "note": "Repo-managed Databricks source surface is active.",
    }
    print(json.dumps(payload, ensure_ascii=True))


if __name__ == "__main__":
    main()
