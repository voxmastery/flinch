"""Hook bodies for agents without a hook system: `flinch check / ran / report / run`."""

import os
import shlex
import uuid
from typing import Any

SHELLS = {"sh", "bash", "zsh"}
ALLOW, DENY, ASK = 0, 2, 3


def command_text(args: list[str]) -> str:
    """The shell command an argv represents: `sh -c "x"` and a single quoted string both mean x."""
    if len(args) == 1:
        return args[0]
    if len(args) >= 3 and os.path.basename(args[0]) in SHELLS and args[1] == "-c":
        return args[2]
    return shlex.join(args)


def session_id() -> str:
    """One agent process = one session, unless the caller names it."""
    return os.environ.get("FLINCH_SESSION") or f"cli-{os.getppid()}"


def new_id() -> str:
    return f"cli-{uuid.uuid4().hex[:12]}"


def tool_body(event: str, command: str, cwd: str, tool_use_id: str, **extra: Any) -> dict[str, Any]:
    return {"session_id": session_id(), "cwd": cwd, "hook_event_name": event, "tool_name": "Bash",
            "tool_input": {"command": command}, "tool_use_id": tool_use_id, **extra}


def prompt_body(message: str, cwd: str) -> dict[str, Any]:
    return {"session_id": session_id(), "cwd": cwd, "hook_event_name": "UserPromptSubmit", "prompt": message}


def verdict(reply: dict[str, Any] | None) -> tuple[int, str]:
    out = (reply or {}).get("hookSpecificOutput") or {}
    decision = out.get("permissionDecision")
    reason = out.get("permissionDecisionReason", "")
    if decision == "deny":
        return DENY, reason
    if decision == "ask":
        return ASK, reason
    return ALLOW, ""


def offline_scar(command: str, cwd: str) -> str | None:
    """Fail-closed scar check without the daemon (same logic as the strict hook)."""
    import json

    from flinch.locate import project_root, state_dir
    from flinch.messages import scar_reason
    from flinch.normalize import fingerprint, normalize

    root = project_root(cwd)
    try:
        scars = json.loads((state_dir(root) / "scars.json").read_text())
    except (OSError, ValueError):
        return None
    scar = scars.get(fingerprint(normalize("Bash", {"command": command}, str(root))))
    return scar_reason(scar["normalized"], scar["reason"], scar["pain_id"], scar["created_at"]) if scar else None
