"""Generate an EB-only replay manifest from current IEG basis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fraud_detection.platform_runtime import RUNS_ROOT, resolve_platform_run_id

from .query import IdentityGraphQuery


def build_manifest_from_basis(basis: dict[str, Any]) -> dict[str, Any]:
    basis_payload = basis.get("basis") if isinstance(basis, dict) else None
    if not isinstance(basis_payload, dict):
        raise ValueError("BASIS_MISSING")
    topics_payload = basis_payload.get("topics")
    if not isinstance(topics_payload, dict):
        raise ValueError("BASIS_TOPICS_MISSING")
    topics: list[dict[str, Any]] = []
    for topic, topic_payload in topics_payload.items():
        partitions_payload = None
        if isinstance(topic_payload, dict):
            partitions_payload = topic_payload.get("partitions")
        if not isinstance(partitions_payload, dict):
            continue
        partitions: list[dict[str, Any]] = []
        for partition, partition_payload in partitions_payload.items():
            if not isinstance(partition_payload, dict):
                continue
            next_offset = partition_payload.get("next_offset")
            offset_kind = partition_payload.get("offset_kind")
            from_offset, to_offset = _offset_range(next_offset, offset_kind)
            entry: dict[str, Any] = {"partition": int(partition)}
            if from_offset is not None:
                entry["from_offset"] = from_offset
            if to_offset is not None:
                entry["to_offset"] = to_offset
            if offset_kind:
                entry["offset_kind"] = str(offset_kind)
            partitions.append(entry)
        if partitions:
            topics.append({"topic": str(topic), "partitions": partitions})
    graph_scope = basis.get("graph_scope") if isinstance(basis, dict) else None
    pins: dict[str, Any] = {}
    if isinstance(graph_scope, dict):
        platform_run_id = graph_scope.get("platform_run_id")
        if platform_run_id:
            pins["platform_run_id"] = platform_run_id
    payload: dict[str, Any] = {"stream_id": basis_payload.get("stream_id"), "topics": topics}
    if pins:
        payload["pins"] = pins
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="IEG replay manifest generator (EB-only)")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--output", help="Optional output path for replay manifest JSON")
    args = parser.parse_args()

    query = IdentityGraphQuery.from_profile(args.profile)
    basis = query.reconciliation()
    if not basis:
        raise SystemExit("NO_GRAPH_BASIS")
    payload = build_manifest_from_basis(basis)

    output_path = args.output
    if output_path:
        path = Path(output_path)
    else:
        graph_scope = basis.get("graph_scope") if isinstance(basis, dict) else None
        platform_run_id = None
        if isinstance(graph_scope, dict):
            platform_run_id = graph_scope.get("platform_run_id")
        if not platform_run_id:
            platform_run_id = resolve_platform_run_id(create_if_missing=False)
        if not platform_run_id:
            raise SystemExit("PLATFORM_RUN_ID_REQUIRED")
        path = RUNS_ROOT / platform_run_id / "identity_entity_graph" / "replay" / "replay_manifest.json"

    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2)
    path.write_text(data + "\n", encoding="utf-8")
    print(str(path))


def _offset_range(next_offset: Any, offset_kind: Any) -> tuple[str | None, str | None]:
    if next_offset is None:
        return None, None
    if offset_kind == "file_line":
        try:
            next_val = int(next_offset)
        except (TypeError, ValueError):
            return "0", None
        if next_val <= 0:
            return "0", None
        return "0", str(next_val - 1)
    return None, str(next_offset)


if __name__ == "__main__":
    main()
