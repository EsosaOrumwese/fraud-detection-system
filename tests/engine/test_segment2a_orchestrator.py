import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from engine.scenario_runner.l1_seg_2A import (
    Segment2AConfig,
    Segment2AOrchestrator,
)

from .test_seg_2a_s0_gate import (
    _build_dictionary,
    _build_validation_bundle,
    _write_reference_files,
)


def test_segment2a_orchestrator_run_and_resume():
    upstream_fp = "a" * 64
    tz_release = "test-release"
    git_commit = "b" * 64
    seed = 42

    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        dictionary_path = _build_dictionary(root)
        validation_dir = root / f"data/layer1/1B/validation/fingerprint={upstream_fp}"
        validation_dir.mkdir(parents=True, exist_ok=True)
        bundle_dir, _ = _build_validation_bundle(validation_dir)
        _write_reference_files(root, str(seed), upstream_fp, tz_release)

        orchestrator = Segment2AOrchestrator()
        initial = orchestrator.run(
            Segment2AConfig(
                data_root=root,
                upstream_manifest_fingerprint=upstream_fp,
                parameter_hash="c" * 64,
                seed=seed,
                tzdb_release_tag=tz_release,
                git_commit_hex=git_commit,
                dictionary_path=dictionary_path,
                validation_bundle_path=bundle_dir,
                notes="integration",
            )
        )

        assert initial.resumed is False
        assert initial.receipt_path.exists()
        assert initial.inventory_path.exists()

        resumed = orchestrator.run(
            Segment2AConfig(
                data_root=root,
                upstream_manifest_fingerprint=upstream_fp,
                parameter_hash="c" * 64,
                seed=seed,
                tzdb_release_tag=tz_release,
                git_commit_hex=git_commit,
                dictionary_path=dictionary_path,
                validation_bundle_path=None,
                resume=True,
                resume_manifest_fingerprint=initial.manifest_fingerprint,
            )
        )

        assert resumed.resumed is True
        assert resumed.manifest_fingerprint == initial.manifest_fingerprint
        assert resumed.receipt_path == initial.receipt_path
        assert resumed.inventory_path == initial.inventory_path


@pytest.mark.integration
def test_segment2a_cli_run_and_resume():
    upstream_fp = "a" * 64
    tz_release = "test-release"
    parameter_hash = "c" * 64
    git_commit = "b" * 64
    seed = 7

    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        dictionary_path = _build_dictionary(root)
        validation_dir = root / f"data/layer1/1B/validation/fingerprint={upstream_fp}"
        validation_dir.mkdir(parents=True, exist_ok=True)
        bundle_dir, _ = _build_validation_bundle(validation_dir)
        _write_reference_files(root, str(seed), upstream_fp, tz_release)

        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            [str(Path.cwd() / "packages" / "engine" / "src"), env.get("PYTHONPATH", "")]
        )

        cmd = [
            sys.executable,
            "-m",
            "engine.cli.segment2a",
            "--data-root",
            str(root),
            "--upstream-manifest-fingerprint",
            upstream_fp,
            "--parameter-hash",
            parameter_hash,
            "--seed",
            str(seed),
            "--tzdb-release-tag",
            tz_release,
            "--git-commit-hex",
            git_commit,
            "--dictionary",
            str(dictionary_path),
            "--validation-bundle",
            str(bundle_dir),
        ]

        initial_run = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        payload = json.loads(initial_run.stdout)
        manifest = payload["manifest_fingerprint"]
        assert payload["resumed"] is False
        receipt_path = Path(payload["receipt_path"])
        assert receipt_path.exists()

        resume_run = subprocess.run(
            cmd
            + [
                "--resume",
                "--resume-manifest",
                manifest,
            ],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        resume_payload = json.loads(resume_run.stdout)
        assert resume_payload["resumed"] is True
        assert resume_payload["manifest_fingerprint"] == manifest
