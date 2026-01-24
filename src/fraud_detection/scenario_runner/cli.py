"""CLI for local Scenario Runner execution."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .config import load_policy, load_wiring
from .engine import LocalEngineInvoker
from .logging_utils import configure_logging
from .models import RunRequest, RunWindow, ScenarioBinding
from .runner import ScenarioRunner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scenario Runner CLI")
    parser.add_argument("--wiring", required=True, help="Path to wiring profile YAML")
    parser.add_argument("--policy", required=True, help="Path to policy profile YAML")
    parser.add_argument("--run-equivalence-key", required=True)
    parser.add_argument("--manifest-fingerprint", required=True)
    parser.add_argument("--parameter-hash", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--scenario-id", default=None)
    parser.add_argument("--scenario-set", nargs="*")
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--window-end", required=True)
    parser.add_argument("--engine-run-root", default=None)
    parser.add_argument("--output-id", action="append")
    return parser.parse_args()


def main() -> None:
    configure_logging()
    args = parse_args()
    wiring = load_wiring(Path(args.wiring))
    policy = load_policy(Path(args.policy))
    invoker = LocalEngineInvoker()
    runner = ScenarioRunner(wiring, policy, invoker)
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
