from flinch.hooks import PreToolUseInput, context, decision


def test_deny_matches_pretooluse_schema_exactly():
    assert decision("deny", "scarred") == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "scarred",
        }
    }


def test_ask_and_allow_use_same_shape():
    for kind in ("ask", "allow"):
        out = decision(kind, "r")["hookSpecificOutput"]
        assert out["permissionDecision"] == kind
        assert set(out) == {"hookEventName", "permissionDecision", "permissionDecisionReason"}


def test_invalid_decision_rejected():
    import pytest

    with pytest.raises(ValueError):
        decision("block", "nope")


def test_context_output_shape():
    assert context("SessionStart", "fact") == {
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "fact"}
    }


def test_input_model_tolerates_unknown_fields():
    body = {
        "session_id": "s", "cwd": "/x", "hook_event_name": "PreToolUse",
        "tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_use_id": "t",
        "permission_mode": "default", "effort": {"level": "low"}, "brand_new_field": 1,
    }
    m = PreToolUseInput.model_validate(body)
    assert m.tool_input["command"] == "ls"
