import re
import sys
import subprocess
from pathlib import Path

import pytest

from fraud_detection.simulator.catalog import load_catalogs  # type: ignore


@pytest.mark.parametrize("workers,batch", [(2, 500)])
def test_cli_realism_v2(tmp_path, workers, batch):
    # ── 1) Locate project root and original config ───────────────────────────────
    project_root = Path(__file__).parents[2].resolve()
    orig_cfg = project_root / "project_config" / "generator_config.yaml"
    assert orig_cfg.exists(), f"Can't find original config at {orig_cfg}"
    text = orig_cfg.read_text()

    # ── 2) Override out_dir to tmp_path/out and write a temp config ──────────────
    out_dir = tmp_path / "out_dir_test"
    # Quote the path so YAML parses Windows drives correctly
    text = re.sub(
        r"^out_dir:.*",
        f'out_dir: "{out_dir.as_posix()}"',
        text,
        flags=re.MULTILINE,
    )
    test_cfg_dir = tmp_path / "project_config"
    test_cfg_dir.mkdir()
    test_cfg = test_cfg_dir / "generator_config.yaml"
    test_cfg.write_text(text)

    # ── 3) Invoke the CLI under project_root so schema/… is on cwd ───────────────
    cmd = [
        sys.executable,
        "-m",
        "fraud_detection.simulator.cli",
        "--config",
        str(test_cfg),
        "--realism",
        "v2",
        "--num-workers",
        str(workers),
        "--batch-size",
        str(batch),
    ]
    result = subprocess.run(
        cmd,
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    # If it failed, dump stdout/stderr for debugging
    assert result.returncode == 0, (
        f"CLI failed (rc={result.returncode})\n\n"
        f"STDOUT:\n{result.stdout}\n\n"
        f"STDERR:\n{result.stderr}"
    )

    # ── 4) Verify the catalogs/ folder was created under our override out_dir ────
    catalog_dir = out_dir / "catalog"
    assert (
        catalog_dir.exists() and catalog_dir.is_dir()
    ), f"No catalog dir at {catalog_dir}"

    # ── 5) load_catalogs must read back the three DataFrames without error ───────
    cust, merch, card = load_catalogs(catalog_dir)
    # Basic sanity checks
    assert cust.height > 0 and "weight" in cust.columns
    assert merch.height > 0 and "risk" in merch.columns
    assert card.height > 0 and "pan_hash" in card.columns
