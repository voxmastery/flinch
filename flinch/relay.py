"""Command-hook side of the plugin. Stdlib only: runs under any python3, before Flinch is installed.

  relay.py session-start|prompt   ensure the daemon is running, forward stdin, print its reply
  relay.py scarcheck              fail-closed scar check (exit 2 on a scar)

Never blocks Claude Code: every failure path prints nothing (or a factual systemMessage) and exits 0.
"""

import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:7331"
ROUTES = {"session-start": "/hook/session-start", "prompt": "/hook/prompt"}
WAIT_S = {"session-start": 8.0, "prompt": 3.0}
IDLE_EXIT_S = 3 * 3600


def _data_dir() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_DATA")
    if env:
        return Path(env)
    from flinch.locate import data_home

    return data_home()


def _headers() -> dict[str, str]:
    from flinch.auth import bearer_headers

    return bearer_headers()


def starting_lock() -> Path:
    return _data_dir() / "daemon.starting"


def touch_starting_lock() -> None:
    """Refresh the start lock so a long model load is not treated as abandoned."""
    path = starting_lock()
    try:
        now = time.time()
        os.utime(path, (now, now))
    except OSError:
        pass


def release_starting_lock() -> None:
    try:
        starting_lock().unlink()
    except OSError:
        pass


def _healthy(timeout: float = 0.3) -> bool:
    req = urllib.request.Request(BASE + "/health", headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def find_flinch() -> list[str] | None:
    """argv prefix that runs the flinch CLI: plugin venv, recorded install, or PATH."""
    venv = _data_dir() / "venv" / "bin" / "flinch"
    if venv.exists():
        return [str(venv)]
    from flinch.locate import data_home

    try:
        recorded = json.loads((data_home() / "daemon.cmd").read_text())
        if recorded and os.path.exists(recorded[0]):
            return [str(x) for x in recorded]
    except (OSError, ValueError):
        pass
    exe = shutil.which("flinch")
    return [exe] if exe else None


def _spawn(argv: list[str], log: Path) -> None:
    from flinch.jsonfile import FILE_MODE, secure_dir

    secure_dir(log.parent)
    fd = os.open(log, os.O_CREAT | os.O_WRONLY | os.O_APPEND, FILE_MODE)
    try:
        os.chmod(log, FILE_MODE)
        out = os.fdopen(fd, "ab")
    except BaseException:
        os.close(fd)
        raise
    try:
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True,
                         preexec_fn=lambda: os.nice(10))  # background priority: never compete with the IDE
    finally:
        out.close()


def _claim(lock: Path, stale_s: float = 30.0) -> bool:
    """Atomically take a start/install lock. A lock older than stale_s is considered abandoned."""
    from flinch.jsonfile import secure_dir

    secure_dir(lock.parent)
    for _ in range(2):
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
            return True
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime <= stale_s:
                    return False
                lock.unlink()
            except FileNotFoundError:
                pass
    return False


def ensure_daemon(wait_s: float) -> bool:
    if _healthy():
        return True
    exe = find_flinch()
    if exe is None:
        return False
    if _claim(_data_dir() / "daemon.starting"):  # only one hook starts the daemon; others wait
        _spawn([*exe, "serve", "--idle-exit", str(IDLE_EXIT_S)], _data_dir() / "daemon.log")
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if _healthy():
            return True
        time.sleep(0.2)
    return False


def bootstrap() -> str | None:
    """First run without an install: build a private venv from the bundled wheel, in the background."""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    wheels = sorted(Path(root, "wheels").glob("flinch*.whl")) if root else []
    if not wheels:
        return "Flinch is not installed. Install it with `uv tool install flinch` or `pipx install flinch`."
    data = _data_dir()
    marker = data / "install.running"
    if not _claim(marker, stale_s=900):
        return "Flinch is still installing in the background (first run). Protection starts when it finishes."
    q = shlex.quote
    venv, wheel = q(str(data / "venv")), q(str(wheels[-1]))
    uv = shutil.which("uv")
    if uv:
        script = f"{q(uv)} venv -q --python 3.12 {venv} && {q(uv)} pip install -q -p {venv} {wheel}"
    else:
        script = f"{q(sys.executable)} -m venv {venv} && {venv}/bin/pip install -q {wheel}"
    _spawn(["sh", "-c", f"{script}; rm -f {q(str(marker))}"], data / "install.log")
    return "Flinch is installing in the background (first run, about a minute). Protection starts next prompt."


def forward(route: str, body: bytes, timeout: float = 4.0) -> str:
    req = urllib.request.Request(BASE + route, data=body, headers=_headers())
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def main(argv: list[str]) -> int:
    mode = argv[0] if argv else ""
    if mode == "scarcheck":
        from flinch.scarcheck import main as scarcheck

        return scarcheck([])
    if mode not in ROUTES:
        return 0
    try:
        body = sys.stdin.buffer.read()
        if not ensure_daemon(WAIT_S[mode]):
            note = bootstrap() if find_flinch() is None else None
            if note and mode == "session-start":
                print(json.dumps({"systemMessage": note}))
            return 0
        out = forward(ROUTES[mode], body)
        if out.strip():
            print(out)
    except Exception:  # noqa: BLE001 - a hook must never break the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
