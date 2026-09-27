import json

import pytest
from fastapi.testclient import TestClient

from flinch import daemon


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "shop" / ".flinch"
    monkeypatch.setenv("FLINCH_HOME", str(h))
    return h


@pytest.fixture
def client(home, fake_embedder):
    return TestClient(daemon.create_app(embedder=fake_embedder))


def tool_body(cmd="ls", event="PreToolUse", tid="t1", **extra):
    return {"session_id": "s1", "cwd": "/p", "hook_event_name": event,
            "tool_name": "Bash", "tool_input": {"command": cmd}, "tool_use_id": tid, **extra}


def run(client, cmd, tid, failed=False):
    """Simulate Claude Code running a command: pre, then post or post-failure."""
    pre = client.post("/hook/pre", json=tool_body(cmd, tid=tid))
    if failed:
        client.post("/hook/post-failure", json=tool_body(cmd, "PostToolUseFailure", tid,
                                                         error="Exit code 1", is_interrupt=False))
    else:
        client.post("/hook/post", json=tool_body(cmd, "PostToolUse", tid, tool_response={}))
    return pre


def hurt(client, reason="deleted the customer database", severity=1.0):
    return client.post("/api/hurt", json={"reason": reason, "severity": severity})


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_pre_passthrough_is_empty_200(client):
    r = client.post("/hook/pre", json=tool_body())
    assert r.status_code == 200 and r.content == b""


def test_scar_flow_denies_exact_action_with_exact_schema(client):
    run(client, "rm -rf data/", "t1")
    run(client, "ls data", "t2")  # read-only: must not steal attribution
    r = hurt(client)
    assert r.status_code == 200 and r.json()["normalized"] == "rm -rf data/"

    denied = client.post("/hook/pre", json=tool_body("rm   -rf data/", tid="t3")).json()
    assert list(denied) == ["hookSpecificOutput"]
    out = denied["hookSpecificOutput"]
    assert set(out) == {"hookEventName", "permissionDecision", "permissionDecisionReason"}
    assert out["hookEventName"] == "PreToolUse" and out["permissionDecision"] == "deny"
    assert "deleted the customer database" in out["permissionDecisionReason"]

    assert client.post("/hook/pre", json=tool_body("git status", tid="t4")).content == b""


def test_hurt_without_any_action_is_409(client):
    assert hurt(client).status_code == 409


def test_hurt_rejects_bad_severity_and_non_json(client):
    run(client, "rm -rf data/", "t1")
    assert hurt(client, severity=0.3).status_code == 422
    r = client.post("/api/hurt", content='{"reason":"x"}', headers={"content-type": "text/plain"})
    assert r.status_code == 415


def test_forgive_removes_scar(client):
    run(client, "rm -rf data/", "t1")
    scar = hurt(client).json()
    assert client.post("/api/forgive", json={"id": scar["pain_id"]}).status_code == 200
    out = client.post("/hook/pre", json=tool_body("rm -rf data/", tid="t9"))
    assert out.content == b"" or out.json()["hookSpecificOutput"]["permissionDecision"] != "deny"
    assert client.post("/api/forgive", json={"id": scar["pain_id"]}).status_code == 404
    assert client.get("/api/scars").json() == []


def test_failed_actions_are_attributable(client):
    run(client, "rm -rf data/", "t1", failed=True)
    assert hurt(client).json()["normalized"] == "rm -rf data/"


def test_decisions_logged_with_gates_and_redaction(client, home):
    client.post("/hook/pre", json=tool_body("curl -H 'Authorization: Bearer supersecrettoken1' x"))
    rec = json.loads((home / "log.jsonl").read_text().splitlines()[-1])
    assert {"ts", "session", "tool", "action", "gates", "decision", "ms"} <= set(rec)
    assert rec["gates"]["scar"] == "miss" and rec["decision"] == "pass"
    assert 0 <= rec["gates"]["reflex"]["avoid"] <= 1
    assert "supersecrettoken1" not in json.dumps(rec)


def test_scars_survive_daemon_restart(home, fake_embedder):
    c1 = TestClient(daemon.create_app(embedder=fake_embedder))
    run(c1, "rm -rf data/", "t1")
    hurt(c1)
    c1.app.state.engine.close()
    c2 = TestClient(daemon.create_app(embedder=fake_embedder))
    assert c2.post("/hook/pre", json=tool_body("rm -rf data/")).json()[
        "hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("path", ["/hook/pre", "/hook/post", "/hook/post-failure",
                                  "/hook/prompt", "/hook/session-start"])
@pytest.mark.parametrize("payload", [b"not json", b"[]", b'{"tool_input": 5}'])
def test_garbage_input_is_empty_200(client, path, payload):
    r = client.post(path, content=payload, headers={"content-type": "application/json"})
    assert r.status_code == 200 and r.content == b""


def test_internal_error_is_empty_200(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(client.app.state.engine, "pre", boom)
    r = client.post("/hook/pre", json=tool_body())
    assert r.status_code == 200 and r.content == b""


def test_all_hook_events_accept_valid_bodies(client):
    base = {"session_id": "s1", "cwd": "/p"}
    cases = {
        "/hook/post": tool_body(event="PostToolUse", tool_response={"stdout": ""}),
        "/hook/post-failure": tool_body(event="PostToolUseFailure", error="Exit code 1\nboom",
                                        is_interrupt=False),
        "/hook/prompt": {**base, "hook_event_name": "UserPromptSubmit", "prompt": "hi"},
        "/hook/session-start": {**base, "hook_event_name": "SessionStart", "source": "startup"},
    }
    for path, body in cases.items():
        r = client.post(path, json=body)
        assert r.status_code == 200 and r.content == b"", path


def test_state_endpoint_and_sse(client):
    st = client.get("/api/state").json()
    assert st["cells"] == 4000 and len(st["weights"]) == 4000
    assert st["thresholds"] == {"flinch": 0.55, "wary": 0.25} and st["grid"] == {"cols": 80, "rows": 50}
    assert isinstance(st["decisions"], list) and isinstance(st["scars"], list)


def test_registry_routes_projects_by_cwd(tmp_path, monkeypatch, fake_embedder):
    monkeypatch.delenv("FLINCH_HOME", raising=False)
    monkeypatch.setenv("FLINCH_DATA_HOME", str(tmp_path / "data"))
    a, b = tmp_path / "a", tmp_path / "b"
    for p in (a, b):
        (p / ".git").mkdir(parents=True)
    c = TestClient(daemon.create_app(embedder=fake_embedder))

    def body(cwd, cmd, tid, event="PreToolUse", **extra):
        return {"session_id": "s", "cwd": str(cwd), "hook_event_name": event, "tool_name": "Bash",
                "tool_input": {"command": cmd}, "tool_use_id": tid, **extra}

    c.post("/hook/pre", json=body(a / "src", "rm -rf data/", "1"))
    c.post("/hook/post", json=body(a / "src", "rm -rf data/", "1", "PostToolUse", tool_response={}))
    assert c.post("/api/hurt", json={"reason": "r", "project": str(a)}).status_code == 200
    denied = c.post("/hook/pre", json=body(a, "rm -rf data/", "2")).json()
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    other = c.post("/hook/pre", json=body(b, "rm -rf data/", "3")).json()  # other project: no scar, only
    assert other["hookSpecificOutput"]["permissionDecision"] == "ask"      # the built-in danger sense
    assert c.get("/api/state", params={"project": str(b)}).json()["scars"] == []
    assert not (a / ".flinch").exists()  # central state: repo untouched
    c.app.state.registry.close_all()


def test_reset_wipes_project_state_but_keeps_config(client, home):
    run(client, "rm -rf data/", "t1")
    assert hurt(client).status_code == 200
    (home / "config.toml").write_text("[thresholds]\nflinch = 0.6\n")
    r = client.post("/api/reset", json={"project": str(home.parent)})
    assert r.status_code == 200 and r.json()["reset"] == str(home)
    assert (home / "config.toml").read_text().startswith("[thresholds]")
    assert not (home / "scars.json").exists() and not (home / "circuit.npz").exists()
    assert client.post("/hook/pre", json=tool_body("git status", tid="t2")).content == b""
    assert client.get("/api/scars").json() == []
    engine = client.app.state.registry.for_cwd(str(home.parent))
    assert engine.circuit.avoid(engine.circuit.encode("rm -rf data/")) == 0.0


def test_reset_requires_json(client):
    assert client.post("/api/reset", content="{}", headers={"content-type": "text/plain"}).status_code == 415
