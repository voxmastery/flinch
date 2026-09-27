"""Merge Flinch's HTTP hooks into a Claude Code settings dict without clobbering others."""

import copy
from typing import Any

from flinch.config import HOOK_TIMEOUT_S, HOST, PORT

FLINCH_URL_PREFIX = f"http://{HOST}:{PORT}/hook/"
TOOL_MATCHER = "^(Bash|Write|Edit|mcp__.*)$"

_EVENTS: dict[str, tuple[str, str | None]] = {
    "PreToolUse": ("pre", TOOL_MATCHER),
    "PostToolUse": ("post", TOOL_MATCHER),
    "PostToolUseFailure": ("post-failure", TOOL_MATCHER),
    "UserPromptSubmit": ("prompt", None),
    "SessionStart": ("session-start", None),
}
_COMMAND_EVENTS = {"SessionStart"}


# Claude Code 2.1.283 skips HTTP hooks on SessionStart ("HTTP hooks are not supported for
# SessionStart"), so that event uses a command hook relaying stdin to the daemon. `|| true`
# keeps it fail-open and silent when the daemon is down.
def _relay_command(path: str) -> str:
    return (f"curl -s --max-time {HOOK_TIMEOUT_S - 1} -X POST -H 'Content-Type: application/json' "
            f"--data-binary @- {FLINCH_URL_PREFIX}{path} || true")


SCARCHECK_MODULE = "flinch.scarcheck"


def _is_ours(hook: dict[str, Any]) -> bool:
    if hook.get("type") == "http":
        return str(hook.get("url", "")).startswith(FLINCH_URL_PREFIX)
    command = str(hook.get("command", ""))
    return hook.get("type") == "command" and (FLINCH_URL_PREFIX in command or SCARCHECK_MODULE in command)


def _hook_for(event: str, path: str) -> dict[str, Any]:
    if event in _COMMAND_EVENTS:
        return {"type": "command", "command": _relay_command(path), "timeout": HOOK_TIMEOUT_S}
    return {"type": "http", "url": FLINCH_URL_PREFIX + path, "timeout": HOOK_TIMEOUT_S}


def _without_ours(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept = []
    for group in groups:
        hooks = [h for h in group.get("hooks", []) if not _is_ours(h)]
        if hooks:
            kept.append({**group, "hooks": hooks})
    return kept


def merge_hooks(settings: dict[str, Any], scarcheck_command: str | None = None) -> dict[str, Any]:
    """Return a new settings dict with exactly one Flinch hook group per event.

    With `scarcheck_command` (strict mode), PreToolUse also gets a fail-closed command hook.
    """
    result = copy.deepcopy(settings)
    hooks = result.setdefault("hooks", {})
    for event, (path, matcher) in _EVENTS.items():
        group: dict[str, Any] = {"hooks": [_hook_for(event, path)]}
        if matcher:
            group = {"matcher": matcher, **group}
        extra = []
        if event == "PreToolUse" and scarcheck_command:
            extra = [{"matcher": TOOL_MATCHER, "hooks": [
                {"type": "command", "command": scarcheck_command, "timeout": HOOK_TIMEOUT_S}]}]
        hooks[event] = [*_without_ours(hooks.get(event, [])), group, *extra]
    return result
