"""Flask service wrapper for SR."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request

from .config import load_policy, load_wiring
from .engine import LocalEngineInvoker, LocalSubprocessInvoker
from .logging_utils import configure_logging
from .models import RunRequest
from .runner import ScenarioRunner


def create_app(wiring_path: str, policy_path: str) -> Flask:
    configure_logging()
    wiring = load_wiring(Path(wiring_path))
    policy = load_policy(Path(policy_path))
    if wiring.engine_command:
        invoker = LocalSubprocessInvoker(
            wiring.engine_command,
            cwd=wiring.engine_command_cwd,
            timeout_seconds=wiring.engine_command_timeout_seconds,
        )
    else:
        invoker = LocalEngineInvoker()
    runner = ScenarioRunner(wiring, policy, invoker)

    app = Flask(__name__)

    @app.post("/runs")
    def submit_run() -> Any:
        payload = request.get_json(force=True)
        run_request = RunRequest(**payload)
        response = runner.submit_run(run_request)
        return jsonify(response.model_dump())

    return app
