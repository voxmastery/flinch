import io
import json

import pytest

from flinch import cursor_hook as ch
from flinch.cursor_install import FLINCH_MARK, merge_cursor_hooks

ROOT = "/work/shop"


def base(event, **extra):
    return {"hook_event_name": event, "conversation_id": "c1", "generation_id": "g1", "cwd": "",
            "workspace_roots": [ROOT], **extra}


def test_shell_maps_to_bash_pre():
    route, body = ch.translate(base("beforeShellExecution", command="rm -rf data/"))
    assert route == "/hook/pre"
    assert body["tool_name"] == "Bash" and body["tool_input"] == {"command": "rm -rf data/"}
    assert body["cwd"] == ROOT and body["session_id"] == "c1" and body["hook_event_name"] == "PreToolUse"


def test_shell_pre_and_post_share_tool_use_id():
    _, pre = ch.translate(base("beforeShellExecution", command="ls"))
    _, post = ch.translate(base("postToolUse", tool_name="Shell", tool_input={"command": "ls", "cwd": ""},
                                tool_use_id="x", tool_output="{}"))
    assert pre["tool_use_id"] == post["tool_use_id"]


def test_write_delete_mcp_map():
    _, w = ch.translate(base("preToolUse", tool_name="Write", tool_input={"file_path": f"{ROOT}/a.py", "content": "x"}))
    assert w["tool_name"] == "Write" and w["tool_input"]["file_path"] == f"{ROOT}/a.py"
    _, d = ch.translate(base("preToolUse", tool_name="Delete", tool_input={"file_path": f"{ROOT}/v.txt"}))
    assert d["tool_name"] == "Delete"
    _, m = ch.translate(base("preToolUse", tool_name="MCP:query", tool_input={"sql": "drop"}))
    assert m["tool_name"] == "mcp__cursor__query"


def test_shell_pretooluse_is_ignored_to_avoid_double_counting():
    assert ch.translate(base("preToolUse", tool_name="Shell", tool_input={"command": "ls"})) is None


def test_denied_failure_is_not_forwarded():
    ev = base("postToolUseFailure", tool_name="Shell", tool_input={"command": "x"}, error_message="denied",
              failure_type="permission_denied", is_interrupt=False)
    assert ch.translate(ev) is None


def test_real_failure_forwarded():
    route, body = ch.translate(base("postToolUseFailure", tool_name="Shell", tool_input={"command": "rm x"},
                                    error_message="rm: busy", failure_type="error", is_interrupt=False))
    assert route == "/hook/post-failure" and body["error"] == "rm: busy"


@pytest.mark.parametrize("decision,event,expected", [
    ("deny", "beforeShellExecution", "deny"), ("ask", "beforeShellExecution", "ask"),
    ("deny", "preToolUse", "deny"), ("ask", "preToolUse", "deny"),  # ask isn't enforced on preToolUse
])
def test_decision_mapping(decision, event, expected):
    reply = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                    "permissionDecisionReason": "because"}}
    out = ch.to_cursor(event, reply)
    assert out["permission"] == expected and "because" in out["agent_message"] and "because" in out["user_message"]


def test_pass_is_empty_output():
    assert ch.to_cursor("beforeShellExecution", None) is None


def test_session_start_context():
    reply = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "lesson"}}
    assert ch.to_cursor("sessionStart", reply) == {"additional_context": "lesson"}


def test_daemon_down_falls_back_to_local_scarcheck(monkeypatch, tmp_path, capsys):
    from flinch.scars import ScarStore

    monkeypatch.setenv("FLINCH_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("FLINCH_HOME", raising=False)
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    from flinch.locate import state_dir
    ScarStore(state_dir(repo) / "scars.json").add("rm -rf data/", "deleted db", 1.0)
    monkeypatch.setattr(ch, "_post", lambda route, body, timeout: None)  # daemon unreachable
    monkeypatch.setattr(ch, "_wake_daemon", lambda wait=0: False)
    ev = {**base("beforeShellExecution", command="rm -rf data/"), "workspace_roots": [str(repo)]}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(ev)))
    assert ch.main([]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["permission"] == "deny" and "deleted db" in out["agent_message"]


def test_unknown_event_or_garbage_is_silent(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert ch.main([]) == 0 and capsys.readouterr().out == ""


def test_merge_preserves_user_hooks_and_is_idempotent():
    mine = {"version": 1, "hooks": {"afterFileEdit": [{"command": "./format.sh"}],
                                    "beforeShellExecution": [{"command": "./mine.sh"}]}}
    once = merge_cursor_hooks(mine, "python3 -S /x/flinch-hooklib/cursor_hook.py")
    assert merge_cursor_hooks(once, "python3 -S /x/flinch-hooklib/cursor_hook.py") == once
    assert once["hooks"]["afterFileEdit"] == [{"command": "./format.sh"}]
    shell = once["hooks"]["beforeShellExecution"]
    assert shell[0] == {"command": "./mine.sh"} and sum(FLINCH_MARK in h["command"] for h in shell) == 1
    assert mine["hooks"]["beforeShellExecution"] == [{"command": "./mine.sh"}]  # not mutated
    removed = merge_cursor_hooks(once, None)
    assert removed["hooks"]["beforeShellExecution"] == [{"command": "./mine.sh"}]
    assert "sessionStart" not in removed["hooks"]


def test_cold_start_waits_and_retries(monkeypatch, capsys):
    calls = []

    def post(route, body, timeout):
        calls.append(route)
        return None if len(calls) == 1 else {"hookSpecificOutput": {"permissionDecision": "deny",
                                                                    "permissionDecisionReason": "scarred"}}
    monkeypatch.setattr(ch, "_post", post)
    woke = []
    monkeypatch.setattr(ch, "_wake_daemon", lambda wait=0: woke.append(wait) or True)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(base("beforeShellExecution", command="rm -rf data/"))))
    assert ch.main([]) == 0
    assert json.loads(capsys.readouterr().out)["permission"] == "deny"
    assert calls == ["/hook/pre", "/hook/pre"] and woke == [ch.COLD_START_WAIT_S]


def test_no_timeout_fields_written():
    cfg = merge_cursor_hooks({}, "python3 -S /x/flinch-hooklib/cursor_hook.py")
    assert all("timeout" not in h for hs in cfg["hooks"].values() for h in hs)


def test_mcp_string_input_is_wrapped():
    _, m = ch.translate(base("preToolUse", tool_name="MCP:exec", tool_input='{"sql": "drop table x"}'))
    assert isinstance(m["tool_input"], dict) and "drop table" in json.dumps(m["tool_input"])


def test_backup_goes_to_data_dir_not_project(tmp_path, monkeypatch):
    from flinch.cursor_install import write_config

    monkeypatch.setenv("FLINCH_DATA_HOME", str(tmp_path / "data"))
    proj = tmp_path / "proj" / ".cursor"
    proj.mkdir(parents=True)
    (proj / "hooks.json").write_text('{"version": 1, "hooks": {}}')
    write_config(proj / "hooks.json", "python3 -S /x/flinch-hooklib/cursor_hook.py")
    assert not list(proj.glob("*backup*"))
    assert list((tmp_path / "data" / "backups").glob("hooks-*.json"))


def test_failure_context_forwarded_to_cursor():
    reply = {"hookSpecificOutput": {"hookEventName": "PostToolUseFailure", "additionalContext": "fixed by x"}}
    assert ch.to_cursor("postToolUseFailure", reply) == {"additional_context": "fixed by x"}
