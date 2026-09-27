import io
import json

from flinch import relay


def test_unknown_mode_is_noop():
    assert relay.main(["bogus"]) == 0


def test_daemon_down_and_not_installed_reports_once(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.setattr(relay, "_healthy", lambda timeout=0.3: False)
    monkeypatch.setattr(relay, "find_flinch", lambda: None)
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"{}")))
    assert relay.main(["session-start"]) == 0
    assert "not installed" in json.loads(capsys.readouterr().out)["systemMessage"]


def test_forwards_reply(monkeypatch, capsys):
    monkeypatch.setattr(relay, "ensure_daemon", lambda wait: True)
    monkeypatch.setattr(relay, "forward", lambda route, body: '{"hookSpecificOutput": {}}')
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"{}")))
    assert relay.main(["prompt"]) == 0
    assert json.loads(capsys.readouterr().out) == {"hookSpecificOutput": {}}


def test_forward_error_is_silent(monkeypatch, capsys):
    monkeypatch.setattr(relay, "ensure_daemon", lambda wait: True)

    def boom(route, body):
        raise OSError("refused")
    monkeypatch.setattr(relay, "forward", boom)
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"{}")))
    assert relay.main(["prompt"]) == 0 and capsys.readouterr().out == ""


def test_only_one_hook_spawns_the_daemon(monkeypatch, tmp_path):
    import threading

    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    monkeypatch.setattr(relay, "_healthy", lambda timeout=0.3: False)
    monkeypatch.setattr(relay, "find_flinch", lambda: ["/bin/true"])
    spawned = []
    monkeypatch.setattr(relay, "_spawn", lambda argv, log: spawned.append(argv))
    threads = [threading.Thread(target=relay.ensure_daemon, args=(0.2,)) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(spawned) == 1


def test_bootstrap_quotes_paths(monkeypatch, tmp_path):
    weird = tmp_path / 'da"ta $(touch pwned)'
    root = tmp_path / "root"
    (root / "wheels").mkdir(parents=True)
    (root / "wheels" / "flinch_agent-0.4.0-py3-none-any.whl").write_text("")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(weird))
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(root))
    calls = []
    monkeypatch.setattr(relay, "_spawn", lambda argv, log: calls.append(argv))
    relay.bootstrap()
    import shlex
    script = calls[0][2]
    assert shlex.quote(str(weird / "venv")) in script
