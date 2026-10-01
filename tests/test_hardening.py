"""Production hardening: auth, fail-closed rules, state files, secrets, and model lifetime."""

import json
import os
import stat
import sys
import threading
import time

from fastapi.testclient import TestClient

from flinch import daemon
from flinch.hooks import SessionStartInput
from flinch.jsonfile import SCHEMA_VERSION, file_lock
from flinch.normalize import fingerprint, normalize
from flinch.rules import strong_rule
from flinch.scars import ScarStore

BYPASSES = (
    "/bin/rm -rf /tmp/flinch-test",
    "rm --recursive --force /tmp/flinch-test",
    "sudo /bin/rm -rf /",
    "git -c user.email=a@b.c push --force origin main",
)


def _mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _client(embedder):
    return TestClient(daemon.create_app(embedder=embedder), base_url="http://127.0.0.1",
                      headers={"Authorization": "Bearer test-token"})


def test_daemon_requires_token_loopback_and_json(fake_embedder):
    client = _client(fake_embedder)
    assert client.get("/health").status_code == 200
    assert client.get("/health", headers={"Authorization": "Bearer no"}).status_code == 401
    assert client.get("http://evil.example/health").status_code == 421
    denied = client.post("/hook/pre", content=b"{}", headers={"content-type": "text/plain"})
    assert denied.status_code == 415
    ok = client.post("/hook/pre", content=b"not json", headers={"content-type": "application/json"})
    assert ok.status_code == 200 and ok.content == b""


def test_starting_lock_held_until_health(fake_embedder):
    from flinch.locate import data_home
    from flinch.relay import starting_lock

    lock = starting_lock()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("")
    seen = []
    original = fake_embedder.embed

    def embed(text):
        seen.append(text)
        assert lock.exists()  # still held while the model is loading
        return original(text)

    fake_embedder.embed = embed
    with _client(fake_embedder) as client:
        assert client.get("/health").status_code == 200
    assert "flinch" in seen
    assert not lock.exists()
    assert data_home() == lock.parent


def test_housekeeping_does_not_unload_the_model(fake_embedder, monkeypatch):
    calls = []
    beats = []
    monkeypatch.setattr(daemon, "HOUSEKEEPING_S", 0.05)
    monkeypatch.setattr(daemon.Registry, "evict_idle", lambda self, _s: beats.append("tick"))
    monkeypatch.setattr(daemon.Registry, "unload_idle_model", lambda self: calls.append("unload"))
    with _client(fake_embedder) as client:
        assert client.get("/health").status_code == 200
        time.sleep(0.25)
    assert beats and calls == []


def test_offline_danger_bypasses_with_no_scar_file(tmp_path):
    from flinch.scarcheck import main, reason_for

    home = tmp_path / ".flinch"
    for cmd in BYPASSES:
        reason = reason_for(str(tmp_path), "Bash", {"command": cmd}, home=str(home), root=str(tmp_path))
        assert reason and "Stop and confirm" in reason, cmd
        assert strong_rule(cmd)
    assert reason_for(str(tmp_path), "Bash", {"command": "ls"}, home=str(home), root=str(tmp_path)) is None
    # fingerprints stay exact: a path prefix is not the same scar
    plain = fingerprint(normalize("Bash", {"command": "rm -rf data/"}, str(tmp_path)))
    prefixed = fingerprint(normalize("Bash", {"command": "/bin/rm -rf data/"}, str(tmp_path)))
    assert plain != prefixed
    assert callable(main)


def test_bad_scars_file_fails_closed(tmp_path, monkeypatch, capsys):
    import io

    from flinch import scarcheck

    home = tmp_path / ".flinch"
    home.mkdir()
    path = home / "scars.json"
    path.mkdir()  # present, unreadable as JSON
    body = {"cwd": str(tmp_path), "tool_name": "Bash", "tool_input": {"command": "echo hi"}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(body)))
    assert scarcheck.main(["--home", str(home)]) == 2
    assert "unreadable" in capsys.readouterr().err

    path.rmdir()
    path.write_text("[]")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(body)))
    assert scarcheck.main(["--home", str(home)]) == 2
    assert "wrong shape" in capsys.readouterr().err

    path.write_text(json.dumps({"schema_version": 99, "scars": {}}))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(body)))
    assert scarcheck.main(["--home", str(home)]) == 2
    assert "newer" in capsys.readouterr().err


def test_malformed_known_fingerprint_blocks_only_that_action(tmp_path):
    from flinch.scarcheck import reason_for

    home = tmp_path / ".flinch"
    home.mkdir()
    text = normalize("Bash", {"command": "ls"}, str(tmp_path))
    (home / "scars.json").write_text(json.dumps(
        {"schema_version": 1, "scars": {fingerprint(text): "not-a-record"}}))
    blocked = reason_for(str(tmp_path), "Bash", {"command": "ls"}, home=str(home), root=str(tmp_path))
    other = reason_for(str(tmp_path), "Bash", {"command": "echo hi"}, home=str(home), root=str(tmp_path))
    assert blocked and "unreadable" in blocked
    assert other is None


def test_legacy_scars_migrate_and_incompatible_files_are_quarantined(tmp_path):
    from flinch.errors import ErrorMemory
    from flinch.recent import RecentActions

    scars_path = tmp_path / "scars.json"
    legacy = {"abc123": {"normalized": "ls", "reason": "old", "severity": 1.0,
                         "created_at": "2026-01-01T00:00:00+00:00", "pain_id": "p_old"}}
    scars_path.write_text(json.dumps(legacy))
    store = ScarStore(scars_path)
    assert store.get("abc123").pain_id == "p_old"
    store.add("pwd", "noted", 0.25)  # migration is written on the next save
    wrapped = json.loads(scars_path.read_text())
    assert wrapped["schema_version"] == SCHEMA_VERSION and "p_old" in json.dumps(wrapped["scars"])

    bad = tmp_path / "errors.json"
    original = '{"schema_version": 99, "open": {"keep": true}}'
    bad.write_text(original)
    memory = ErrorMemory(bad)
    assert memory.lessons() == []
    archived = list(tmp_path.glob("errors.json.incompatible-*"))
    assert len(archived) == 1 and archived[0].read_text() == original
    memory.bump()
    assert json.loads(bad.read_text())["schema_version"] == SCHEMA_VERSION

    recent_path = tmp_path / "recent.json"
    recent_path.write_text("[]")
    recent = RecentActions(recent_path)
    assert recent.for_session("s") == []
    recent.add(session_id="s", tool_use_id=None, tool="Bash", normalized="ls", fingerprint="f", failed=False)
    assert json.loads(recent_path.read_text())["schema_version"] == SCHEMA_VERSION


def test_state_writes_lock_and_fsync(tmp_path, monkeypatch):
    synced = []
    real = os.fsync

    def spy(fd):
        synced.append(fd)
        return real(fd)

    monkeypatch.setattr(os, "fsync", spy)
    path = tmp_path / "scars.json"
    ScarStore(path).add("ls", "noted", 0.5)
    assert synced
    assert (tmp_path / "scars.json.lock").exists()
    assert _mode(path) == 0o600
    assert _mode(tmp_path) == 0o700

    held = threading.Event()
    release = threading.Event()

    def hold():
        with file_lock(path):
            held.set()
            release.wait(2)

    thread = threading.Thread(target=hold)
    thread.start()
    assert held.wait(1)
    blocked = []

    def wait_for_lock():
        with file_lock(path):
            blocked.append(True)

    waiter = threading.Thread(target=wait_for_lock)
    waiter.start()
    waiter.join(0.15)
    assert blocked == []
    release.set()
    waiter.join(2)
    thread.join(2)
    assert blocked == [True]


def test_private_logs_and_token(tmp_path, fake_embedder, monkeypatch):
    from flinch.auth import ensure_token, token_path
    from flinch.relay import _spawn

    monkeypatch.delenv("FLINCH_TOKEN", raising=False)
    token = ensure_token()
    path = token_path()
    assert path.read_text().strip() == token and _mode(path) == 0o600
    assert _mode(path.parent) == 0o700

    home = tmp_path / "proj" / ".flinch"
    monkeypatch.setenv("FLINCH_HOME", str(home))
    client = TestClient(daemon.create_app(embedder=fake_embedder), base_url="http://127.0.0.1",
                        headers={"Authorization": f"Bearer {token}"})
    client.post("/hook/pre", json={"session_id": "s", "cwd": str(tmp_path), "hook_event_name": "PreToolUse",
                                   "tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_use_id": "t"})
    assert _mode(home / "log.jsonl") == 0o600
    assert _mode(home) == 0o700

    def boom(*_a, **_k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(client.app.state.engine, "pre", boom)
    client.post("/hook/pre", json={"session_id": "s", "cwd": str(tmp_path), "hook_event_name": "PreToolUse",
                                   "tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_use_id": "t2"})
    from flinch.locate import data_home
    assert _mode(data_home() / "errors.log") == 0o600

    log_path = tmp_path / "daemon.log"
    _spawn([sys.executable, "-c", "pass"], log_path)
    assert _mode(log_path) == 0o600 and _mode(log_path.parent) == 0o700


def test_invalid_thresholds_fall_back(tmp_path, caplog):
    from flinch.config import load_config

    (tmp_path / "config.toml").write_text("[thresholds]\nwary = 0.8\nflinch = 0.2\ndanger = 0.9\n")
    cfg = load_config(tmp_path)
    assert (cfg.wary_threshold, cfg.flinch_threshold, cfg.danger_threshold) == (0.25, 0.55, 0.9)


def test_named_task_does_not_inject_unrelated_scar(tmp_path, fake_embedder):
    from flinch.decide import Engine
    from flinch.innate import Innate

    engine = Engine(tmp_path / ".flinch", embedder=fake_embedder, innate=Innate(None, None))
    engine.hurt("deleted the customer database", 1.0, action="rm -rf data/")
    quiet = engine.session_start(SessionStartInput(
        session_id="s", cwd=str(tmp_path), hook_event_name="SessionStart", source="startup",
        prompt="rename this function"))
    assert quiet is None
    cold = engine.session_start(SessionStartInput(
        session_id="s", cwd=str(tmp_path), hook_event_name="SessionStart", source="startup"))
    assert "customer database" in cold["hookSpecificOutput"]["additionalContext"]
    engine.close()


def test_daemon_asks_on_normalized_bypasses(tmp_path, fake_embedder, monkeypatch):
    monkeypatch.setenv("FLINCH_HOME", str(tmp_path / ".flinch"))
    client = _client(fake_embedder)
    for cmd in BYPASSES:
        body = {"session_id": "s", "cwd": str(tmp_path), "hook_event_name": "PreToolUse",
                "tool_name": "Bash", "tool_input": {"command": cmd}, "tool_use_id": cmd[:12]}
        out = client.post("/hook/pre", json=body).json()["hookSpecificOutput"]
        assert out["permissionDecision"] in ("ask", "deny"), cmd
