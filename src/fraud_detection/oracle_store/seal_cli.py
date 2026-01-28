"""CLI to seal an oracle pack (write-once manifest + seal)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from fraud_detection.platform_runtime import platform_log_paths
from fraud_detection.scenario_runner.logging_utils import configure_logging
from fraud_detection.scenario_runner.storage import LocalObjectStore, S3ObjectStore

from .config import OracleProfile
from .packer import OraclePackPacker, OraclePackError


def main() -> None:
    parser = argparse.ArgumentParser(description="Oracle Store pack sealer")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--run-facts-ref", required=True, help="run_facts_view reference path")
    parser.add_argument("--pack-root", help="Override pack root (optional)")
    parser.add_argument("--engine-release", default="unknown", help="Engine release identifier")
    parser.add_argument(
        "--seal-status",
        default="SEALED_OK",
        choices=["SEALED_OK", "SEALED_FAILED"],
        help="Seal status to write",
    )
    args = parser.parse_args()

    configure_logging(log_paths=platform_log_paths(create_if_missing=False))
    profile = OracleProfile.load(Path(args.profile))
    packer = OraclePackPacker(profile)
    run_facts = _read_run_facts(args.run_facts_ref, profile)
    try:
        result = packer.seal_from_run_facts(
            run_facts,
            pack_root=args.pack_root,
            engine_release=args.engine_release,
            seal_status=args.seal_status,
        )
    except OraclePackError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, sort_keys=True))


def _read_run_facts(run_facts_ref: str, profile: OracleProfile) -> dict:
    if run_facts_ref.startswith("s3://"):
        parsed = urlparse(run_facts_ref)
        store = S3ObjectStore(
            parsed.netloc,
            prefix="",
            endpoint_url=profile.wiring.object_store_endpoint,
            region_name=profile.wiring.object_store_region,
            path_style=profile.wiring.object_store_path_style,
        )
        return store.read_json(parsed.path.lstrip("/"))
    if Path(run_facts_ref).is_absolute():
        return json.loads(Path(run_facts_ref).read_text(encoding="utf-8"))
    store = LocalObjectStore(Path(profile.wiring.object_store_root))
    return store.read_json(run_facts_ref)


if __name__ == "__main__":
    main()
