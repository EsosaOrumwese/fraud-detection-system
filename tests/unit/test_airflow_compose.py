import subprocess
import pathlib


def test_compose_config_generates_valid_yaml():
    comp = pathlib.Path("orchestration/airflow/docker-compose.yml")
    assert comp.exists(), "Compose file is missing"
    # validate synthax
    res = subprocess.run(
        ["docker", "compose", "-f", str(comp), "config"],
        capture_output=True,
        check=False,
    )
    assert res.returncode == 0, f"Compose config failed:\n{res.stderr.decode()}"
    # Optional extra check: ensure webserver healthcheck is defined
    stdout = res.stdout.decode()
    assert (
        "healthcheck" in stdout and "airflow-apiserver" in stdout
    ), "Missing healthcheck in airflow-apiserver service"
