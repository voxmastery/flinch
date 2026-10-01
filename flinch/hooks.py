"""Claude Code hook request models and response builders (SPEC §3)."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Decision = Literal["allow", "deny", "ask"]
_DECISIONS = ("allow", "deny", "ask")


class HookInput(BaseModel):
    """Common fields. Unknown fields are tolerated: Claude Code adds new ones over time."""

    model_config = ConfigDict(extra="allow")

    session_id: str
    cwd: str
    hook_event_name: str


class ToolInput(HookInput):
    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str | None = None


class PreToolUseInput(ToolInput):
    pass


class PostToolUseInput(ToolInput):
    tool_response: Any = None


class PostToolUseFailureInput(ToolInput):
    error: str = ""
    is_interrupt: bool = False


class UserPromptSubmitInput(HookInput):
    prompt: str = ""


class SessionStartInput(HookInput):
    source: str = "startup"
    prompt: str = ""


def decision(kind: str, reason: str) -> dict[str, Any]:
    """PreToolUse permission decision, exactly as documented."""
    if kind not in _DECISIONS:
        raise ValueError(f"invalid permission decision: {kind!r}")
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": kind,
            "permissionDecisionReason": reason,
        }
    }


def context(event: str, text: str) -> dict[str, Any]:
    """Inject factual context (SessionStart, UserPromptSubmit, PostToolUse*)."""
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}
