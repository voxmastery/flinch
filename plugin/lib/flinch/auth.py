"""Per-user daemon token. Stdlib only. The file is mode 0600 under the data dir."""

import os
import secrets
from pathlib import Path

from flinch.jsonfile import FILE_MODE, secure_dir
from flinch.locate import data_home

TOKEN_NAME = "token"


def token_path() -> Path:
    return data_home() / TOKEN_NAME


def ensure_token() -> str:
    """The bearer token for this user. `FLINCH_TOKEN` wins; otherwise the 0600 file."""
    env = os.environ.get("FLINCH_TOKEN")
    if env:
        return env.strip()
    path = token_path()
    try:
        existing = path.read_text().strip()
    except OSError:
        existing = ""
    if existing:
        return existing
    token = secrets.token_hex(32)
    secure_dir(path.parent)
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, FILE_MODE)
    try:
        os.write(fd, (token + "\n").encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(path, FILE_MODE)
    return token


def bearer_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ensure_token()}", "Content-Type": "application/json"}
