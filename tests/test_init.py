import json

from typer.testing import CliRunner

from flinch.cli import app
from flinch.settings_merge import FLINCH_URL_PREFIX, merge_hooks

runner = CliRunner()


def test_merge_into_empty():
    merged = merge_hooks({})
    pre = merged["hooks"]["PreToolUse"][0]
    assert pre["matcher"] == "^(Bash|Write|Edit|mcp__.*)$"
    assert pre["hooks"] == [{"type": "http", "url": "http://127.0.0.1:7331/hook/pre", "timeout": 5}]
    assert set(merged["hooks"]) == {"PreToolUse", "PostToolUse", "PostToolUseFailure",
                                    "UserPromptSubmit", "SessionStart"}
    assert "matcher" not in merged["hooks"]["SessionStart"][0]


def test_session_start_is_command_relay():
    # Claude Code 2.1.283 skips HTTP hooks on SessionStart despite the docs.
    (hook,) = merge_hooks({})["hooks"]["SessionStart"][0]["hooks"]
    assert hook["type"] == "command"
    assert "http://127.0.0.1:7331/hook/session-start" in hook["command"]
    assert hook["command"].rstrip().endswith("|| true")


def test_merge_preserves_existing_and_is_idempotent():
    existing = {"model": "x", "hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]}]}}
    once = merge_hooks(existing)
    twice = merge_hooks(once)
    assert once == twice
    assert once["model"] == "x"
    pre = once["hooks"]["PreToolUse"]
    assert pre[0]["hooks"][0]["command"] == "mine.sh"
    assert sum(1 for g in pre for h in g["hooks"] if h.get("url", "").startswith(FLINCH_URL_PREFIX)) == 1
    assert len(twice["hooks"]["SessionStart"]) == 1
    assert existing["hooks"]["PreToolUse"] == [  # input not mutated
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "mine.sh"}]}]


def test_init_writes_files(tmp_path):
    (tmp_path / ".gitignore").write_text("node_modules/\n")
    r = runner.invoke(app, ["init", "--project", str(tmp_path)])
    assert r.exit_code == 0, r.output
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert "PreToolUse" in settings["hooks"]
    assert (tmp_path / ".flinch").is_dir()
    gi = (tmp_path / ".gitignore").read_text().splitlines()
    assert "node_modules/" in gi and ".flinch/" in gi
    runner.invoke(app, ["init", "--project", str(tmp_path)])
    assert (tmp_path / ".gitignore").read_text().splitlines().count(".flinch/") == 1


def test_init_rejects_invalid_settings_json(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{broken")
    r = runner.invoke(app, ["init", "--project", str(tmp_path)])
    assert r.exit_code != 0
    assert (tmp_path / ".claude" / "settings.json").read_text() == "{broken"


def test_strict_adds_scarcheck_and_non_strict_removes_it():
    cmd = "/venv/bin/python -m flinch.scarcheck --home /p/.flinch"
    strict = merge_hooks({}, scarcheck_command=cmd)
    pre_cmds = [h for g in strict["hooks"]["PreToolUse"] for h in g["hooks"] if h["type"] == "command"]
    assert pre_cmds == [{"type": "command", "command": cmd, "timeout": 5}]
    assert merge_hooks(strict, scarcheck_command=cmd) == strict
    relaxed = merge_hooks(strict)
    assert all(h["type"] == "http" for g in relaxed["hooks"]["PreToolUse"] for h in g["hooks"])


def test_init_strict_writes_command(tmp_path):
    r = runner.invoke(app, ["init", "--project", str(tmp_path), "--strict"])
    assert r.exit_code == 0, r.output
    s = (tmp_path / ".claude" / "settings.json").read_text()
    assert "flinch.scarcheck" in s and str(tmp_path / ".flinch") in s


def test_serve_refuses_busy_port():
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        r = runner.invoke(app, ["serve", "--port", str(port)])
    assert r.exit_code == 1 and "already in use" in r.output


def test_init_no_hooks_creates_state_only(tmp_path):
    r = runner.invoke(app, ["init", "--project", str(tmp_path), "--no-hooks"])
    assert r.exit_code == 0 and (tmp_path / ".flinch" / "config.toml").exists()
    assert not (tmp_path / ".claude").exists()


def test_reset_needs_yes(tmp_path):
    r = runner.invoke(app, ["reset", "--project", str(tmp_path)])
    assert r.exit_code != 0 and "--yes" in r.output


def test_reset_offline_deletes_state(tmp_path, monkeypatch):
    import flinch.cli as cli

    home = tmp_path / ".flinch"
    home.mkdir()
    (home / "scars.json").write_text("{}")
    (home / "config.toml").write_text("x = 1")
    monkeypatch.setattr(cli, "_port_in_use", lambda h, p: False)  # daemon down
    r = runner.invoke(app, ["reset", "--yes", "--project", str(tmp_path)])
    assert r.exit_code == 0, r.output
    assert not (home / "scars.json").exists() and (home / "config.toml").exists()
