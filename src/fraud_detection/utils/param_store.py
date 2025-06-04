"""
Lazy getter for SSM parameters.  On first call:
  • Fetches the parameter from AWS SSM
  • Writes/updates a `.env` file in the project root for offline caching

Subsequent calls read from os.environ directly.
"""

from __future__ import annotations
import os
import pathlib
import boto3  # type: ignore

# Path to the local .env file to cache values
_DOTENV = pathlib.Path(".env")


def _write_dotenv(key: str, value: str):
    """
    Append or update a key=value pair in the top-level .env file.
    If the key already exists, overwrite it. Otherwise, append as a new line.
    """
    lines = []
    if _DOTENV.exists():
        lines = _DOTENV.read_text().splitlines()
        # Remove any existing line that starts with KEY=
        lines = [line for line in lines if not line.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    _DOTENV.write_text("\n".join(lines) + "\n")


def get_param(param_name: str) -> str:
    """
    Return the value of the SSM parameter at `param_name`.
    On the first call, fetch from SSM (AWS SDK), cache to .env, and set os.environ.
    On subsequent calls, read from os.environ[key].

    The environment variable key is the uppercase param path with slashes → underscores.
    E.g. "/fraud/raw_bucket_name" → "FRAUD_RAW_BUCKET_NAME".
    """
    # Construct a safe env var name
    env_key = param_name.strip("/").upper().replace("/", "_")
    existing = os.getenv(env_key)
    if existing:
        return existing

    # Fetch from SSM
    ssm = boto3.client("ssm")
    resp = ssm.get_parameter(Name=param_name)
    value = resp["Parameter"]["Value"]

    # Cache locally
    _write_dotenv(env_key, value)
    os.environ[env_key] = value
    return value
