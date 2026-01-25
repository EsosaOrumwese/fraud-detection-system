"""CLI for local Scenario Runner execution."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from .config import load_policy, load_wiring
from .engine import LocalEngineInvoker, LocalSubprocessInvoker
from .ids import run_id_from_equivalence_key
from .logging_utils import configure_logging
from .models import ReemitKind, ReemitRequest, RunRequest, RunWindow, ScenarioBinding
from .storage import build_object_store
from .runner import ScenarioRunner


def parse_args() -> argparse.Namespace:
    base = argparse.ArgumentParser(add_help=False)
    base.add_argument("--wiring", required=True, help="Path to wiring profile YAML")
    base.add_argument("--policy", required=True, help="Path to policy profile YAML")

    parser = argparse.ArgumentParser(description="Scenario Runner CLI")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", parents=[base], help="Submit a run request")
    run_parser.add_argument("--run-equivalence-key", required=True)
    run_parser.add_argument("--manifest-fingerprint", required=True)
    run_parser.add_argument("--parameter-hash", required=True)
    run_parser.add_argument("--seed", required=True, type=int)
    run_parser.add_argument("--scenario-id", default=None)
    run_parser.add_argument("--scenario-set", nargs="*")
    run_parser.add_argument("--window-start", required=True)
    run_parser.add_argument("--window-end", required=True)
    run_parser.add_argument("--engine-run-root", default=None)
    run_parser.add_argument("--output-id", action="append")
    run_parser.add_argument("--invoker", default=None)

    reemit_parser = subparsers.add_parser("reemit", parents=[base], help="Re-emit control facts for a run")
    reemit_parser.add_argument("--run-id", required=True)
    reemit_parser.add_argument("--kind", choices=[k.value for k in ReemitKind], default=ReemitKind.BOTH.value)
    reemit_parser.add_argument("--reason", default=None)
    reemit_parser.add_argument("--requested-by", default=None)
    reemit_parser.add_argument("--dry-run", action="store_true")

    quarantine_parser = subparsers.add_parser("quarantine", parents=[base], help="Inspect quarantined runs")
    q_sub = quarantine_parser.add_subparsers(dest="q_action")
    q_list = q_sub.add_parser("list", help="List quarantined runs")
    q_show = q_sub.add_parser("show", help="Show quarantine record for a run")
    q_show.add_argument("--run-id", required=True)

    args = parser.parse_args()
    if args.command is None:
        args = run_parser.parse_args()
        args.command = "run"
    return args


def _log_path_for_args(args: argparse.Namespace) -> str | None:
    base = "runs/fraud-platform"
    if args.command == "run":
        run_id = run_id_from_equivalence_key(args.run_equivalence_key)
        return f"{base}/sr_run_{run_id}.log"
    if args.command == "reemit":
        return f"{base}/sr_reemit_{args.run_id}.log"
    if args.command == "quarantine":
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{base}/sr_quarantine_{ts}.log"
    return f"{base}/sr_cli.log"


def main() -> None:
    args = parse_args()
    log_path = _log_path_for_args(args)
    configure_logging(log_path=log_path)
    wiring = load_wiring(Path(args.wiring))
    policy = load_policy(Path(args.policy))
    if wiring.engine_command:
        invoker = LocalSubprocessInvoker(
            wiring.engine_command,
            cwd=wiring.engine_command_cwd,
            timeout_seconds=wiring.engine_command_timeout_seconds,
        )
    else:
        invoker = LocalEngineInvoker()
    runner = ScenarioRunner(wiring, policy, invoker)
    if args.command == "quarantine":
        store = build_object_store(
            wiring.object_store_root,
            s3_endpoint_url=wiring.s3_endpoint_url,
            s3_region=wiring.s3_region,
            s3_path_style=wiring.s3_path_style,
        )
        prefix = "fraud-platform/sr/quarantine"
        if args.q_action == "list":
            files = store.list_files(prefix)
            for path in files:
                print(path)
            return
        if args.q_action == "show":
            record_path = f"{prefix}/{args.run_id}.json"
            record = store.read_json(record_path)
            print(record)
            return
        raise SystemExit("Quarantine command requires list or show action.")
    if args.command == "reemit":
        reemit_request = ReemitRequest(
            run_id=args.run_id,
            reemit_kind=ReemitKind(args.kind),
            reason=args.reason,
            requested_by=args.requested_by,
            dry_run=args.dry_run,
        )
        response = runner.reemit(reemit_request)
        print(response.model_dump())
        return

    scenario = ScenarioBinding(scenario_id=args.scenario_id, scenario_set=args.scenario_set)
    window = RunWindow(
        window_start_utc=datetime.fromisoformat(args.window_start),
        window_end_utc=datetime.fromisoformat(args.window_end),
        window_tz="UTC",
    )
    request = RunRequest(
        run_equivalence_key=args.run_equivalence_key,
        manifest_fingerprint=args.manifest_fingerprint,
        parameter_hash=args.parameter_hash,
        seed=args.seed,
        scenario=scenario,
        window=window,
        engine_run_root=args.engine_run_root,
        output_ids=args.output_id,
        invoker=args.invoker,
    )
    response = runner.submit_run(request)
    print(response.model_dump())


if __name__ == "__main__":
    main()
