"""Generic agent interface: flinch check / ran / report / run."""

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import flinch.cli as cli
from flinch import daemon

runner = CliRunner()


@pytest.fixture
def wired(tmp_path, monkeypatch, fake_embedder):
    monkeypatch.setenv("FLINCH_HOME", str(tmp_path / "proj" / ".flinch"))
    (tmp_path / "proj").mkdir()
    monkeypatch.chdir(tmp_path / "proj")
    client = TestClient(daemon.create_app(embedder=fake_embedder), base_url="http://127.0.0.1",
                        headers={"Authorization": "Bearer test-token"})

    def post(route, body):
        r = client.post(route, json=body)
        return r.json() if r.content else {}

    monkeypatch.setattr(cli, "_post_hook", post)
    monkeypatch.setattr(cli, "_start_daemon", lambda: True)
    yield client
    client.app.state.registry.close_all()


def test_check_allows_and_blocks_after_pain(wired):
    assert runner.invoke(cli.app, ["check", "--", "ls", "src"]).exit_code == 0
    assert runner.invoke(cli.app, ["ran", "--", "sh", "-c", "rm -rf data/"]).exit_code == 0
    r = runner.invoke(cli.app, ["report", "you deleted the customer database!"])
    assert r.exit_code == 0 and "rm -rf data/" in r.output
    blocked = runner.invoke(cli.app, ["check", "--", "sh", "-c", "rm -rf data/"])
    assert blocked.exit_code == 2 and "Flinch blocked" in blocked.output


def test_check_asks_for_never_seen_destroyer(wired):
    r = runner.invoke(cli.app, ["check", "--", "git", "push", "--force", "origin", "main"])
    assert r.exit_code == 3 and "force push" in r.output


def test_ran_failed_is_recorded(wired):
    assert runner.invoke(cli.app, ["ran", "--failed", "--", "rm", "-rf", "build/"]).exit_code == 0
    assert wired.app.state.engine.recent.latest().normalized == "rm -rf build/"


def test_run_executes_allowed_and_refuses_blocked(wired, tmp_path):
    out = runner.invoke(cli.app, ["run", "--", "sh", "-c", "echo hi > made.txt"])
    assert out.exit_code == 0 and (tmp_path / "proj" / "made.txt").exists()
    runner.invoke(cli.app, ["report", "you deleted my notes, that overwrote made.txt!"])
    again = runner.invoke(cli.app, ["run", "--", "sh", "-c", "echo hi > made.txt"])
    assert again.exit_code == 2


def test_run_ask_without_tty_refuses(wired):
    r = runner.invoke(cli.app, ["run", "--", "git", "push", "--force", "origin", "main"])
    assert r.exit_code == 3 and "confirm" in r.output.lower()


def test_check_fails_closed_on_scar_when_daemon_down(tmp_path, monkeypatch):
    from flinch.scars import ScarStore

    home = tmp_path / "p" / ".flinch"
    ScarStore(home / "scars.json").add("rm -rf data/", "deleted db", 1.0)
    monkeypatch.setenv("FLINCH_HOME", str(home))
    monkeypatch.chdir(tmp_path / "p")
    monkeypatch.setattr(cli, "_post_hook", lambda route, body: None)
    monkeypatch.setattr(cli, "_start_daemon", lambda: False)
    assert runner.invoke(cli.app, ["check", "--", "rm", "-rf", "data/"]).exit_code == 2
    assert runner.invoke(cli.app, ["check", "--", "ls"]).exit_code == 0


def test_run_yes_answers_ask_but_never_a_block(wired, tmp_path):
    (tmp_path / "proj" / "junk").mkdir()
    assert runner.invoke(cli.app, ["run", "--yes", "--", "rm", "-rf", "junk"]).exit_code == 0
    assert not (tmp_path / "proj" / "junk").exists()
    runner.invoke(cli.app, ["report", "you deleted my junk folder!"])
    (tmp_path / "proj" / "junk").mkdir()
    assert runner.invoke(cli.app, ["run", "--yes", "--", "rm", "-rf", "junk"]).exit_code == 2
    assert (tmp_path / "proj" / "junk").exists()


def test_run_teaches_and_recalls_an_error_fix(wired, tmp_path):
    proj = tmp_path / "proj"
    build = 'test -f config.json || { echo "Error: config.json not found" >&2; exit 1; }'
    first = runner.invoke(cli.app, ["run", "--", "bash", "-c", build])
    assert first.exit_code == 1
    assert runner.invoke(cli.app, ["run", "--", "touch", "config.json"]).exit_code == 0
    assert runner.invoke(cli.app, ["run", "--", "bash", "-c", build]).exit_code == 0  # fixed: lesson learned
    (proj / "config.json").unlink()
    again = runner.invoke(cli.app, ["run", "--", "bash", "-c", build])
    assert again.exit_code == 1 and "touch config.json" in again.output and "happened before" in again.output
