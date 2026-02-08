"""CLI for platform governance events."""

from __future__ import annotations

import argparse
import json
from typing import Any

from .evidence_corridor import (
    EvidenceRefResolutionError,
    EvidenceRefResolutionRequest,
    build_evidence_ref_resolution_corridor,
)
from .writer import build_platform_governance_writer, emit_platform_governance_event


def main() -> None:
    parser = argparse.ArgumentParser(description="Platform governance event tools")
    parser.add_argument(
        "--object-store-root",
        default=None,
        help="Object store root (defaults to PLATFORM_STORE_ROOT or runs/fraud-platform)",
    )
    parser.add_argument("--object-store-endpoint", default=None)
    parser.add_argument("--object-store-region", default=None)
    parser.add_argument(
        "--object-store-path-style",
        action="store_true",
        help="Force S3 path-style addressing",
    )
    parser.add_argument(
        "--no-object-store-path-style",
        action="store_true",
        help="Force non-path-style addressing",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    query = subparsers.add_parser("query", help="Query governance events for a platform run")
    query.add_argument("--platform-run-id", required=True)
    query.add_argument("--event-family", default=None)
    query.add_argument("--limit", type=int, default=0)

    emit = subparsers.add_parser("emit", help="Emit one governance event")
    emit.add_argument("--event-family", required=True)
    emit.add_argument("--actor-id", required=True)
    emit.add_argument("--source-type", required=True)
    emit.add_argument("--source-component", required=True)
    emit.add_argument("--platform-run-id", required=True)
    emit.add_argument("--scenario-run-id", default=None)
    emit.add_argument("--manifest-fingerprint", default=None)
    emit.add_argument("--parameter-hash", default=None)
    emit.add_argument("--seed", default=None)
    emit.add_argument("--scenario-id", default=None)
    emit.add_argument("--dedupe-key", default=None)
    emit.add_argument("--event-id", default=None)
    emit.add_argument("--ts-utc", default=None)
    emit.add_argument("--details", default="{}", help="JSON object")

    resolve_ref = subparsers.add_parser("resolve-ref", help="Resolve one evidence ref through the corridor")
    resolve_ref.add_argument("--actor-id", required=True)
    resolve_ref.add_argument("--source-type", required=True)
    resolve_ref.add_argument("--source-component", required=True)
    resolve_ref.add_argument("--purpose", required=True)
    resolve_ref.add_argument("--platform-run-id", required=True)
    resolve_ref.add_argument("--scenario-run-id", default=None)
    resolve_ref.add_argument("--ref-type", required=True)
    resolve_ref.add_argument("--ref-id", required=True)
    resolve_ref.add_argument("--observed-time", default=None)
    resolve_ref.add_argument(
        "--allow-actor",
        action="append",
        default=[],
        help="Optional explicit allowlist actor (repeatable).",
    )
    resolve_ref.add_argument("--strict", action="store_true", help="Fail command if resolution is denied.")

    args = parser.parse_args()
    path_style: bool | None
    if args.object_store_path_style and args.no_object_store_path_style:
        raise SystemExit("choose one of --object-store-path-style / --no-object-store-path-style")
    if args.object_store_path_style:
        path_style = True
    elif args.no_object_store_path_style:
        path_style = False
    else:
        path_style = None

    writer = build_platform_governance_writer(
        object_store_root=args.object_store_root,
        object_store_endpoint=args.object_store_endpoint,
        object_store_region=args.object_store_region,
        object_store_path_style=path_style,
    )

    if args.cmd == "query":
        rows = writer.query(
            platform_run_id=args.platform_run_id,
            event_family=args.event_family,
            limit=args.limit if args.limit > 0 else None,
        )
        print(json.dumps(rows, sort_keys=True))
        return

    if args.cmd == "resolve-ref":
        corridor = build_evidence_ref_resolution_corridor(
            store=writer.store,
            actor_allowlist=list(args.allow_actor or []),
        )
        try:
            result = corridor.resolve(
                EvidenceRefResolutionRequest(
                    actor_id=args.actor_id,
                    source_type=args.source_type,
                    source_component=args.source_component,
                    purpose=args.purpose,
                    ref_type=args.ref_type,
                    ref_id=args.ref_id,
                    platform_run_id=args.platform_run_id,
                    scenario_run_id=args.scenario_run_id,
                    observed_time=args.observed_time,
                ),
                raise_on_denied=args.strict,
            )
            print(json.dumps(result.to_dict(), sort_keys=True))
        except EvidenceRefResolutionError as exc:
            raise SystemExit(str(exc)) from exc
        return

    details = _load_details(args.details)
    payload = emit_platform_governance_event(
        store=writer.store,
        event_family=args.event_family,
        actor_id=args.actor_id,
        source_type=args.source_type,
        source_component=args.source_component,
        platform_run_id=args.platform_run_id,
        scenario_run_id=args.scenario_run_id,
        manifest_fingerprint=args.manifest_fingerprint,
        parameter_hash=args.parameter_hash,
        seed=args.seed,
        scenario_id=args.scenario_id,
        dedupe_key=args.dedupe_key,
        event_id=args.event_id,
        ts_utc=args.ts_utc,
        details=details,
    )
    print(json.dumps(payload, sort_keys=True))


def _load_details(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--details must be valid JSON object: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("--details must decode to a JSON object")
    return dict(payload)


if __name__ == "__main__":
    main()
