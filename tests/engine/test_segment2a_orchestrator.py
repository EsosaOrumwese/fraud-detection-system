import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from engine.layers.l1.seg_2A import ProvisionalLookupResult
from engine.scenario_runner.l1_seg_2A import Segment2AConfig, Segment2AOrchestrator

from .test_seg_2a_s0_gate import (
    _build_dictionary,
    _build_validation_bundle,
    _write_reference_files,
)


def test_segment2a_orchestrator_run_and_resume(monkeypatch):
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

        captured: dict[str, ProvisionalLookupResult] = {}

        class DummyLookupRunner:
            def run(self, inputs):
                out_dir = (
                    root
                    / f"data/layer1/2A/s1_tz_lookup/seed={inputs.seed}/fingerprint={inputs.manifest_fingerprint}"
                )
                out_dir.mkdir(parents=True, exist_ok=True)
                captured["inputs"] = inputs
                result = ProvisionalLookupResult(
                    seed=inputs.seed,
                    manifest_fingerprint=inputs.manifest_fingerprint,
                    output_path=out_dir,
                    resumed=inputs.resume,
                )
                captured["result"] = result
                return result

        monkeypatch.setattr(
            "engine.scenario_runner.l1_seg_2A.ProvisionalLookupRunner",
            lambda: DummyLookupRunner(),
        )

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
                run_s1=True,
                s1_chunk_size=10,
            )
        )

        assert initial.resumed is False
        assert initial.receipt_path.exists()
        assert initial.inventory_path.exists()
        assert initial.s1_output_path is not None
        assert initial.s1_resumed is False
        assert captured["inputs"].chunk_size == 10

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
                run_s1=True,
                s1_resume=True,
            )
        )

        assert resumed.resumed is True
        assert resumed.manifest_fingerprint == initial.manifest_fingerprint
        assert resumed.receipt_path == initial.receipt_path
        assert resumed.inventory_path == initial.inventory_path
        assert resumed.s1_output_path is not None
        assert resumed.s1_resumed is True


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

        base_cmd = [
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
            base_cmd,
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
        assert "s1_output_path" not in payload

        site_root = root / f"data/layer1/1B/site_locations/seed={seed}"
        src = site_root / f"fingerprint={upstream_fp}"
        dst = site_root / f"fingerprint={manifest}"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)

        run_s1_cmd = base_cmd + [
            "--run-s1",
            "--s1-chunk-size",
            "10",
            "--resume",
            "--resume-manifest",
            manifest,
        ]

        run_s1 = subprocess.run(
            run_s1_cmd,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        s1_payload = json.loads(run_s1.stdout)
        assert s1_payload["resumed"] is True
        assert s1_payload["manifest_fingerprint"] == manifest
        assert s1_payload["s1_resumed"] is False
        s1_path = Path(s1_payload["s1_output_path"])
        assert s1_path.exists()

        resume_run = subprocess.run(
            run_s1_cmd + ["--s1-resume"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        resume_payload = json.loads(resume_run.stdout)
        assert resume_payload["resumed"] is True
        assert resume_payload["manifest_fingerprint"] == manifest
        assert resume_payload["s1_resumed"] is True
