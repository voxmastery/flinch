"""Assemble a self-contained Claude Code plugin + local marketplace in dist/flinch-marketplace/.

The plugin holds only: hooks, a stdlib hook launcher, the stdlib modules it needs, and a wheel of
the package that the first run installs into the plugin's data dir (unless `flinch` is on PATH).
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The repo root is the marketplace (.claude-plugin/marketplace.json); the plugin lives in plugin/.
OUT = ROOT
PLUGIN = ROOT / "plugin"
STDLIB_MODULES = ("__init__", "locate", "normalize", "redact", "messages", "scarcheck", "relay")
TOOL_MATCHER = "^(Bash|Write|Edit|mcp__.*)$"
URL = "http://127.0.0.1:7331/hook/"
LAUNCH = 'python3 -S "${CLAUDE_PLUGIN_ROOT}/scripts/flinch_hook.py"'

LAUNCHER = '''"""Hook launcher: stdlib only, runs under the system python3."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
if sys.argv[1:2] == ["scarcheck"]:  # hot path, every tool call: import only what it needs
    from flinch.scarcheck import main  # noqa: E402

    sys.exit(main([]))
from flinch.relay import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
'''


def version() -> str:
    import tomllib

    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]


def hooks() -> dict:
    def http(path: str) -> dict:
        return {"type": "http", "url": URL + path, "timeout": 5}

    def cmd(mode: str, timeout: int) -> dict:
        return {"type": "command", "command": f"{LAUNCH} {mode}", "timeout": timeout}

    return {
        "description": "Flinch: blocks actions that caused damage before",
        "hooks": {
            "SessionStart": [{"hooks": [cmd("session-start", 12)]}],
            "UserPromptSubmit": [{"hooks": [cmd("prompt", 6)]}],
            "PreToolUse": [{"matcher": TOOL_MATCHER, "hooks": [http("pre"), cmd("scarcheck", 5)]}],
            "PostToolUse": [{"matcher": TOOL_MATCHER, "hooks": [http("post")]}],
            "PostToolUseFailure": [{"matcher": TOOL_MATCHER, "hooks": [http("post-failure")]}],
        },
    }


def main() -> int:
    if not (ROOT / "flinch" / "ui" / "dist" / "index.html").exists():
        print("error: build the UI first (cd ui && npm run build)", file=sys.stderr)
        return 1
    shutil.rmtree(PLUGIN, ignore_errors=True)
    (PLUGIN / ".claude-plugin").mkdir(parents=True)
    (OUT / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    v = version()

    wheels = PLUGIN / "wheels"
    subprocess.run(["uv", "build", "--wheel", "-q", "-o", str(wheels), str(ROOT)], check=True)
    for w in wheels.iterdir():
        if w.suffix != ".whl":
            w.unlink()

    lib = PLUGIN / "lib" / "flinch"
    lib.mkdir(parents=True)
    for mod in STDLIB_MODULES:
        shutil.copy(ROOT / "flinch" / f"{mod}.py", lib / f"{mod}.py")
    (PLUGIN / "scripts").mkdir()
    (PLUGIN / "scripts" / "flinch_hook.py").write_text(LAUNCHER)
    (PLUGIN / "hooks").mkdir()
    (PLUGIN / "hooks" / "hooks.json").write_text(json.dumps(hooks(), indent=2) + "\n")
    (PLUGIN / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": "flinch", "displayName": "Flinch", "version": v,
        "description": "Blocks AI coding agent actions that caused damage before, and asks before risky ones.",
        "license": "MIT", "keywords": ["safety", "hooks", "guardrails"],
        "author": {"name": "Ganesh", "url": "https://github.com/voxmastery"},
        "homepage": "https://flinch-site-khaki.vercel.app", "repository": "https://github.com/voxmastery/flinch",
    }, indent=2) + "\n")
    (OUT / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
        "name": "flinch", "owner": {"name": "Ganesh", "url": "https://github.com/voxmastery"},
        "metadata": {"description": "Pain receptors for AI agents."},
        "plugins": [{"name": "flinch", "source": "./plugin", "version": v,
                     "description": "Blocks agent actions that caused damage before."}],
    }, indent=2) + "\n")
    size = sum(f.stat().st_size for f in PLUGIN.rglob("*") if f.is_file())
    print(f"built {PLUGIN} ({size / 1024:.0f} KiB) and {OUT / '.claude-plugin' / 'marketplace.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
