"""Map a working directory to its project and state directory. Stdlib only (shared with hook scripts).

Project root: nearest ancestor with a `.flinch/` dir (explicit opt-in), else the git root, else cwd.
State: `<root>/.flinch/` when it exists, otherwise a central per-project dir so repos stay untouched.
"""

import hashlib
import os
from pathlib import Path


def data_home() -> Path:
    env = os.environ.get("FLINCH_DATA_HOME")
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "flinch"


def project_root(cwd: str) -> Path:
    start = Path(cwd).resolve()
    git_root = None
    for d in (start, *start.parents):
        if (d / ".flinch").is_dir():
            return d
        if git_root is None and (d / ".git").exists():
            git_root = d
    return git_root or start


def state_dir(root: Path) -> Path:
    env = os.environ.get("FLINCH_HOME")
    if env:
        return Path(env)
    local = root / ".flinch"
    if local.is_dir():
        return local
    digest = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:10]
    return data_home() / "projects" / f"{root.name or 'root'}-{digest}"


KEEP_ON_RESET = ("config.toml",)


def wipe_state(home: Path) -> None:
    """Delete everything Flinch learned for a project, keeping its configuration."""
    import shutil

    if not home.is_dir():
        return
    for entry in home.iterdir():
        if entry.name in KEEP_ON_RESET:
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()
