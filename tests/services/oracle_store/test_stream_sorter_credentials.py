from __future__ import annotations

import sys
from types import SimpleNamespace

from fraud_detection.oracle_store import stream_sorter


def test_resolve_aws_runtime_credentials_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "env-ak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "env-sk")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "env-token")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    creds = stream_sorter._resolve_aws_runtime_credentials("eu-west-2")

    assert creds.source == "env"
    assert creds.access_key_id == "env-ak"
    assert creds.secret_access_key == "env-sk"
    assert creds.session_token == "env-token"
    assert creds.region == "eu-west-2"


def test_resolve_aws_runtime_credentials_uses_boto3_session(monkeypatch) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "dev-min")

    class Frozen:
        access_key = "session-ak"
        secret_key = "session-sk"
        token = "session-token"

    class Credentials:
        def get_frozen_credentials(self):
            return Frozen()

    class Session:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.region_name = "ap-south-1"

        def get_credentials(self):
            return Credentials()

    fake_boto3 = SimpleNamespace(session=SimpleNamespace(Session=Session))
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    creds = stream_sorter._resolve_aws_runtime_credentials(None)

    assert creds.source == "boto3_session"
    assert creds.access_key_id == "session-ak"
    assert creds.secret_access_key == "session-sk"
    assert creds.session_token == "session-token"
    assert creds.region == "ap-south-1"


def test_resolve_aws_runtime_credentials_none_when_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-1")

    class Session:
        def __init__(self, **kwargs) -> None:
            self.region_name = None

        def get_credentials(self):
            return None

    fake_boto3 = SimpleNamespace(session=SimpleNamespace(Session=Session))
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    creds = stream_sorter._resolve_aws_runtime_credentials(None)

    assert creds.source == "none"
    assert creds.access_key_id is None
    assert creds.secret_access_key is None
    assert creds.session_token is None
    assert creds.region == "us-west-1"
