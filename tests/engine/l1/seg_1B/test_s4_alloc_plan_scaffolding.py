from pathlib import Path

import pytest

from engine.layers.l1.seg_1B import S4AllocPlanRunner, S4RunnerConfig
from engine.layers.l1.seg_1B.s4_alloc_plan.exceptions import S4Error


def test_runner_config_normalises_inputs(tmp_path: Path) -> None:
    config = S4RunnerConfig(
        data_root=tmp_path,
        manifest_fingerprint="a" * 64,
        seed="12345",
        parameter_hash="b" * 64,
    )
    assert config.data_root == tmp_path.resolve()
    assert config.manifest_fingerprint == "a" * 64
    assert config.seed == "12345"
    assert config.parameter_hash == "b" * 64


def test_placeholder_runner_raises_not_implemented(tmp_path: Path) -> None:
    runner = S4AllocPlanRunner()
    config = S4RunnerConfig(
        data_root=tmp_path,
        manifest_fingerprint="a" * 64,
        seed="12345",
        parameter_hash="b" * 64,
    )
    with pytest.raises(S4Error) as excinfo:
        runner.run(config)
    assert excinfo.value.context.code == "S4_NOT_IMPLEMENTED"
