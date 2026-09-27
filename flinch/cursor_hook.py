"""Cursor hook adapter. Stdlib only. Translates Cursor hook events onto the Flinch daemon.

Cursor rules (verified live with cursor-agent 2026.09.10): empty stdout + exit 0 means "no
opinion"; permission hooks treat invalid JSON as a block, so this never prints anything but a
valid response or nothing. `cwd` arrives empty; the project comes from `workspace_roots`.
"""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:7331"
TOOL_TIMEOUT_S = 3.0
SESSION_WAIT_S = 8.0
PERMISSION_EVENTS = ("beforeShellExecution", "preToolUse")
COLD_START_WAIT_S = 3.0  # hook timeout is 5 s; leave room for the retry


def _root(ev: dict) -> str:
    roots = ev.get("workspace_roots") or []
    return ev.get("cwd") or (roots[0] if roots else "") or os.environ.get("CURSOR_PROJECT_DIR") or os.getcwd()


def _tool(name: str, tool_input) -> tuple[str, dict] | None:
    fields = tool_input if isinstance(tool_input, dict) else {}
    if name == "Shell":
        return "Bash", {"command": str(fields.get("command", ""))}
    if name in ("Write", "Delete"):
        return name, {"file_path": str(fields.get("file_path", ""))}
    if name.startswith("MCP:"):
        return f"mcp__cursor__{name[4:]}", tool_input if isinstance(tool_input, dict) else {"input": tool_input}
    return None


def _shell_id(ev: dict, command: str) -> str:
    # beforeShellExecution carries no tool_use_id; derive one its postToolUse can reproduce.
    digest = hashlib.sha256(command.encode()).hexdigest()[:12]
    return f"sh:{ev.get('generation_id', '')}:{digest}"


def translate(ev: dict) -> tuple[str, dict] | None:
    """Cursor event -> (daemon route, Claude-Code-shaped body), or None to ignore."""
    event = ev.get("hook_event_name")
    common = {"session_id": ev.get("conversation_id") or ev.get("session_id") or "cursor", "cwd": _root(ev)}
    if event == "sessionStart":
        return "/hook/session-start", {**common, "hook_event_name": "SessionStart", "source": "startup"}
    if event == "beforeSubmitPrompt":
        return "/hook/prompt", {**common, "hook_event_name": "UserPromptSubmit", "prompt": ev.get("prompt", "")}
    if event == "beforeShellExecution":
        cmd = ev.get("command", "")
        return "/hook/pre", {**common, "hook_event_name": "PreToolUse", "tool_name": "Bash",
                             "tool_input": {"command": cmd}, "tool_use_id": _shell_id(ev, cmd)}
    name = ev.get("tool_name", "")
    if event == "preToolUse" and name == "Shell":
        return None  # handled by beforeShellExecution, which (unlike preToolUse) enforces "ask"
    raw_input = ev.get("tool_input")
    mapped = _tool(name, raw_input if isinstance(raw_input, dict) else ({} if raw_input is None else raw_input))
    if mapped is None:
        return None
    tool, tool_input = mapped
    tid = _shell_id(ev, tool_input["command"]) if tool == "Bash" else ev.get("tool_use_id")
    body = {**common, "tool_name": tool, "tool_input": tool_input, "tool_use_id": tid}
    if event == "preToolUse":
        return "/hook/pre", {**body, "hook_event_name": "PreToolUse"}
    if event == "postToolUse":
        return "/hook/post", {**body, "hook_event_name": "PostToolUse", "tool_response": {}}
    if event == "postToolUseFailure":
        if ev.get("failure_type") == "permission_denied" or ev.get("is_interrupt"):
            return None  # a block or a cancel is not damage
        return "/hook/post-failure", {**body, "hook_event_name": "PostToolUseFailure",
                                      "error": ev.get("error_message", ""), "is_interrupt": False}
    return None


def to_cursor(event: str, reply: dict | None) -> dict | None:
    out = (reply or {}).get("hookSpecificOutput") or {}
    if event in PERMISSION_EVENTS:
        decision = out.get("permissionDecision")
        if decision not in ("deny", "ask"):
            return None
        reason = out.get("permissionDecisionReason", "Blocked by Flinch.")
        if decision == "ask" and event == "preToolUse":  # Cursor doesn't enforce ask here
            decision, reason = "deny", f"{reason} (Flinch needs the user to confirm; ask them before retrying.)"
        return {"permission": decision, "user_message": reason, "agent_message": reason}
    if event in ("sessionStart", "postToolUse", "postToolUseFailure") and out.get("additionalContext"):
        return {"additional_context": out["additionalContext"]}
    return None


def _post(route: str, body: dict, timeout: float) -> dict | None:
    """Reply dict ({} for an empty reply), or None when the daemon is unreachable."""
    req = urllib.request.Request(BASE + route, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except (urllib.error.URLError, OSError, ValueError):
        return None
    try:
        return json.loads(raw) if raw.strip() else {}
    except ValueError:
        return {}


def _wake_daemon(wait_s: float = 0.0) -> bool:
    from flinch.relay import ensure_daemon

    return ensure_daemon(wait_s)


def _local_scarcheck(body: dict) -> dict | None:
    from flinch.locate import project_root, state_dir
    from flinch.messages import scar_reason
    from flinch.normalize import fingerprint, normalize

    root = project_root(body["cwd"])
    try:
        with open(state_dir(root) / "scars.json") as f:
            scars = json.load(f)
    except (OSError, ValueError):
        return None
    scar = scars.get(fingerprint(normalize(body["tool_name"], body["tool_input"], str(root)))) if scars else None
    if not scar:
        return None
    reason = scar_reason(scar["normalized"], scar["reason"], scar["pain_id"], scar["created_at"])
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def main(argv: list[str]) -> int:
    try:
        ev = json.load(sys.stdin)
        event = ev.get("hook_event_name", "")
        routed = translate(ev)
        if routed is None:
            return 0
        route, body = routed
        if event in ("sessionStart", "beforeSubmitPrompt"):
            _wake_daemon(SESSION_WAIT_S if event == "sessionStart" else 2.0)
        timeout = TOOL_TIMEOUT_S if event in PERMISSION_EVENTS else 6.0
        reply = _post(route, body, timeout)
        if reply is None:  # daemon down or still starting (Cursor's sessionStart doesn't wait for us)
            _wake_daemon(COLD_START_WAIT_S)
            reply = _post(route, body, timeout)
        if reply is None and event in PERMISSION_EVENTS:
            reply = _local_scarcheck(body)  # fail-closed for scars even with the daemon down
        out = to_cursor(event, reply)
        if out:
            print(json.dumps(out))
    except Exception:  # noqa: BLE001 - never break the agent; empty output = no opinion
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
