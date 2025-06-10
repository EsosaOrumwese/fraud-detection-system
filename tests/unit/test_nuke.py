import subprocess
import re


def test_nuke_dry_runs_successfully(tmp_path, monkeypatch):
    # simulate AWS and Terraform commands
    monkeypatch.setenv("FRAUD_RAW_BUCKET_NAME", "dummy-bucket")
    monkeypatch.setenv("FRAUD_ARTIFACTS_BUCKET_NAME", "dummy-bucket")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "file:///nonexistent")
    # stub out aws, terraform, python parts:
    monkeypatch.setenv("PATH", str(tmp_path))  # place no-op binaries here if needed

    result = subprocess.run(
        ["bash", "infra/scripts/nuke.sh", "--dry-run", "--force"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # must see our structured dry-run marker
    assert re.search(r"\[dry-run\].*terraform destroy", result.stdout)
    assert re.search(r"\[dry-run\] would delete artifacts for run", result.stdout)
