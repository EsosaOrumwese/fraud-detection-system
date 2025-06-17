#!/usr/bin/env bash
set -eu
if [[ -n "${BASH_VERSION:-}" ]]; then
  set -o pipefail
fi

ENV_FILE="$(dirname "$0")/../.env"

# Changed: idempotent, only creates keys + UID once
if [ -f "$ENV_FILE" ]; then
  echo ".env already exists, skipping generation"
  exit 0
fi

python - << 'PYCODE'
import base64, os, secrets, pathlib, platform

env_path = pathlib.Path("orchestration/airflow/.env")
lines = [
    # Fernet key for encrypted connections
    f"FERNET_KEY={base64.urlsafe_b64encode(os.urandom(32)).decode()}",
    # Flask secret key
    f"SECRET_KEY={secrets.token_urlsafe(32)}",
    # Non-root UID for file ownership
    f"AIRFLOW_UID={os.getuid() if hasattr(os, 'getuid') else 50000}",
    # Optional suffix for Apple Silicon
    ("IMAGE_ARCH_SUFFIX=-arm64" if platform.machine().startswith("arm") else "")
]
env_path.write_text("\n".join([l for l in lines if l]) + "\n")
print(f"✓ Created .env at {env_path}")
PYCODE
