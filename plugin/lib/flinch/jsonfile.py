"""Small atomic JSON persistence helpers. Stdlib only."""

import json
import logging
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

log = logging.getLogger("flinch")

SCHEMA_VERSION = 1
DIR_MODE = 0o700
FILE_MODE = 0o600


def secure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, DIR_MODE)
    except OSError:
        log.warning("could not set %s to mode 0700", path)


def open_private(path: Path, mode: str = "a"):
    """Append/write a file that is mode 0600, creating parent dirs at 0700."""
    secure_dir(path.parent)
    flags = os.O_CREAT | os.O_WRONLY
    flags |= os.O_APPEND if "a" in mode else os.O_TRUNC
    fd = os.open(path, flags, FILE_MODE)
    try:
        os.chmod(path, FILE_MODE)
        return os.fdopen(fd, mode)
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def file_lock(path: Path, exclusive: bool = True) -> Iterator[None]:
    """Cross-process lock beside `path`. Held across load or save."""
    import fcntl

    secure_dir(path.parent)
    lock_path = path.with_name(f"{path.name}.lock")
    fh = open(lock_path, "a+")
    try:
        os.chmod(lock_path, FILE_MODE)
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield
    finally:
        try:
            import fcntl as _fcntl

            _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)
        finally:
            fh.close()


def quarantine(path: Path) -> Path | None:
    """Move an incompatible state file aside. The bytes stay on disk."""
    if not path.exists():
        return None
    dest = path.with_name(f"{path.name}.incompatible-{time.time_ns()}")
    os.replace(path, dest)
    log.error("quarantined incompatible state %s as %s", path.name, dest.name)
    return dest


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def read_versioned(path: Path, kind: str) -> Any | None:
    """Load a state file. Missing returns None. Corrupt or a newer schema is quarantined."""
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        quarantine(path)
        return None
    version = _schema_version(raw, kind)
    if version is None or version > SCHEMA_VERSION:
        quarantine(path)
        return None
    return raw


def _schema_version(raw: Any, kind: str) -> int | None:
    if kind == "recent" and isinstance(raw, list):
        return 1
    if not isinstance(raw, dict):
        return None
    if "schema_version" not in raw:
        return 1
    try:
        version = int(raw["schema_version"])
    except (TypeError, ValueError):
        return None
    return version if version >= 1 else None


def write_json_atomic(path: Path, data: Any) -> None:
    secure_dir(path.parent)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, FILE_MODE)
        os.replace(tmp, path)
        os.chmod(path, FILE_MODE)
        dirfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
