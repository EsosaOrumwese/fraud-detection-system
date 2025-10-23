from __future__ import annotations

from pathlib import Path

import pytest

from engine.layers.l1.seg_1B import (
    S5Error,
    S5RunnerConfig,
    S5SiteTileAssignmentRunner,
    S5SiteTileAssignmentValidator,
    S5ValidatorConfig,
)


def test_runner_not_implemented(tmp_path: Path) -> None:
    runner = S5SiteTileAssignmentRunner()
    config = S5RunnerConfig(
        data_root=tmp_path,
        manifest_fingerprint="f" * 64,
        seed="123",
        parameter_hash="abc",
    )
    with pytest.raises(S5Error) as excinfo:
        runner.run(config)
    assert excinfo.value.context.code == "E500_NOT_IMPLEMENTED"


def test_validator_not_implemented(tmp_path: Path) -> None:
    validator = S5SiteTileAssignmentValidator()
    config = S5ValidatorConfig(
        data_root=tmp_path,
        seed="123",
        manifest_fingerprint="f" * 64,
        parameter_hash="abc",
    )
    with pytest.raises(S5Error) as excinfo:
        validator.validate(config)
    assert excinfo.value.context.code == "E500_NOT_IMPLEMENTED"
