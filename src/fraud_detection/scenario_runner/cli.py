"""CLI for local Scenario Runner execution."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .config import load_policy, load_wiring
from .engine import LocalEngineInvoker, LocalSubprocessInvoker
from .logging_utils import configure_logging
from .models import ReemitKind, ReemitRequest, RunRequest, RunWindow, ScenarioBinding
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

    reemit_parser = subparsers.add_parser("reemit", parents=[base], help="Re-emit control facts for a run")
    reemit_parser.add_argument("--run-id", required=True)
    reemit_parser.add_argument("--kind", choices=[k.value for k in ReemitKind], default=ReemitKind.BOTH.value)
    reemit_parser.add_argument("--reason", default=None)
    reemit_parser.add_argument("--requested-by", default=None)

    args = parser.parse_args()
    if args.command is None:
        args = run_parser.parse_args()
        args.command = "run"
    return args


def main() -> None:
    configure_logging()
    args = parse_args()
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
    if args.command == "reemit":
        reemit_request = ReemitRequest(
            run_id=args.run_id,
            reemit_kind=ReemitKind(args.kind),
            reason=args.reason,
            requested_by=args.requested_by,
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
    )
    response = runner.submit_run(request)
    print(response.model_dump())


if __name__ == "__main__":
    main()
