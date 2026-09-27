"""Install/uninstall Flinch hooks in Cursor's hooks.json (user-level by default)."""

import copy
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from flinch.locate import data_home

FLINCH_MARK = "flinch-hooklib"
STDLIB_MODULES = ("__init__", "locate", "normalize", "redact", "messages", "scarcheck", "relay", "cursor_hook")
EVENTS: dict[str, str | None] = {
    "sessionStart": None,
    "beforeSubmitPrompt": None,
    "beforeShellExecution": None,
    "preToolUse": "Write|Delete|MCP:.*",
    "postToolUse": "Shell|Write|Delete|MCP:.*",
    "postToolUseFailure": "Shell|Write|Delete|MCP:.*",
}
# No per-hook "timeout": with Cursor 3.5.33 / cursor-agent 2026.09.10 a postToolUse entry that
# has one silently never runs (verified live). The adapter bounds its own waits instead.


def _ours(hook: dict[str, Any]) -> bool:
    return FLINCH_MARK in str(hook.get("command", ""))


def merge_cursor_hooks(config: dict[str, Any], command: str | None) -> dict[str, Any]:
    """New config with exactly one Flinch entry per event (or none when command is None)."""
    result = copy.deepcopy(config) if config else {}
    result.setdefault("version", 1)
    hooks = result.setdefault("hooks", {})
    for event, matcher in EVENTS.items():
        kept = [h for h in hooks.get(event, []) if not _ours(h)]
        if command:
            entry: dict[str, Any] = {"command": command}
            if matcher:
                entry["matcher"] = matcher
            kept = [*kept, entry]
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    return result


def install_hooklib() -> Path:
    """Copy the stdlib hook modules to a stable location and record how to start the daemon."""
    pkg = Path(__file__).parent
    lib = data_home() / FLINCH_MARK
    target = lib / "flinch"
    shutil.rmtree(lib, ignore_errors=True)
    target.mkdir(parents=True)
    for mod in STDLIB_MODULES:
        shutil.copy(pkg / f"{mod}.py", target / f"{mod}.py")
    launcher = lib / "cursor_hook.py"
    launcher.write_text(
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parent))\n"
        "from flinch.cursor_hook import main\n\nsys.exit(main(sys.argv[1:]))\n")
    (data_home() / "daemon.cmd").write_text(json.dumps([sys.executable, "-m", "flinch.cli"]))
    return launcher


def hooks_path(project: Path | None) -> Path:
    return (project / ".cursor" / "hooks.json") if project else Path.home() / ".cursor" / "hooks.json"


def write_config(path: Path, command: str | None) -> dict[str, Any]:
    current = json.loads(path.read_text()) if path.exists() and path.read_text().strip() else {}
    if path.exists():  # timestamped backup outside the project, so it never gets committed
        import time

        backups = data_home() / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, backups / f"hooks-{time.strftime('%Y%m%d-%H%M%S')}-{abs(hash(str(path))) % 10**6}.json")
    merged = merge_cursor_hooks(current, command)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2) + "\n")
    return merged
