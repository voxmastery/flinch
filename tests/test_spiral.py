"""Fix-spiral ladder: signature identity, edit hashes, destructive recovery, sensitization."""

import numpy as np
import pytest

from flinch.episode import estimate_tokens
from flinch.errors import ErrorMemory
from flinch.hooks import PostToolUseInput, PreToolUseInput, UserPromptSubmitInput
from flinch.messages import spiral_ask, spiral_escape, spiral_hint, spiral_warning
from flinch.sensitize import Sensitization
from flinch.spiral import command_family, is_revert, proposed_hash

from test_engine import fail, make_engine, pre, run_edit


@pytest.fixture
def engine(tmp_path, fake_embedder):
    built = make_engine(tmp_path / ".flinch", fake_embedder)
    yield built
    built.close()


def _write(engine, path, tid, content):
    payload = {"file_path": str(engine.home.parent / path), "content": content}
    out = engine.pre(PreToolUseInput(session_id="s", cwd="/p", hook_event_name="PreToolUse", tool_name="Write",
                                     tool_input=payload, tool_use_id=tid))
    engine.post(PostToolUseInput(session_id="s", cwd="/p", hook_event_name="PostToolUse", tool_name="Write",
                                 tool_input=payload, tool_use_id=tid, tool_response={}))
    return out


def test_command_family_collapses_variants():
    assert command_family("pytest -q") == command_family("pytest tests/x.py") == "pytest"
    assert command_family("python -m pytest tests/x.py") == "pytest"
    assert command_family("npm run build") == "npm build"
    assert command_family("npm test") != command_family("npm run build")


def test_revert_detects_return_to_an_earlier_hash():
    a, b = proposed_hash("Write", {"content": "A"}), proposed_hash("Write", {"content": "B"})
    assert not is_revert(b, [a])
    assert is_revert(a, [a, b])


def test_open_failure_persists_across_edits_and_variants(tmp_path):
    m = ErrorMemory(tmp_path / "errors.json")
    m.record_check_failure("pytest", "pytest -q", "E assert 1 == 2", "fix tests")
    m.bump()  # an edit moved change_count; the spiral must not care
    again = m.record_check_failure("pytest", "pytest tests/x.py", "E   assert 1 == 2", "fix tests")
    assert again["failures"] == 2 and "pytest tests/x.py" in again["commands"]
    reloaded = ErrorMemory(tmp_path / "errors.json")
    assert reloaded.open_family("pytest")["failures"] == 2
    reloaded.record_check_failure("pytest", "pytest -q", "E assert 9 == 9", "fix tests")
    assert reloaded.open_family("pytest")["failures"] == 1
    assert reloaded.open_family("pytest")["signature"] != again["signature"]


def test_spiral_messages_stay_short():
    for text in (
        spiral_hint("pytest -q", "assert 1 == 2", 1),
        spiral_warning("pytest -q", "assert 1 == 2", 2, 0.65, "cp config/app.example.json config/app.json"),
        spiral_ask("pytest -q", "assert 1 == 2", 2, "cp config/app.example.json config/app.json"),
        spiral_escape("assert 1 == 2", 4, None),
    ):
        assert text.count("\n") <= 2
        assert estimate_tokens(text) <= 80


def test_ladder_hint_warning_ask_deny_and_edit_does_not_reset(engine):
    err = "Exit code 1\nE   assert 1 == 2"
    engine.pre(pre("pytest -q", "t0"))
    engine.post_failure(fail("pytest -q", err, "t0"))
    hint = engine.pre(pre("pytest tests/x.py", "t1"))
    assert "permissionDecision" not in hint["hookSpecificOutput"]
    assert "1 failed fix so far" in hint["hookSpecificOutput"]["additionalContext"]
    warned = engine.post_failure(fail("pytest tests/x.py", err, "t1"))
    warning = warned["hookSpecificOutput"]["additionalContext"]
    assert "warning" in warning and "Cost " in warning and "assert 1 == 2" in warning
    asked = engine.pre(pre("pytest -q", "t2"))
    assert asked["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "assert 1 == 2" in asked["hookSpecificOutput"]["permissionDecisionReason"]
    run_edit(engine, "src/app.py", "e1")
    still = engine.pre(pre("pytest -q", "t3"))
    assert still["hookSpecificOutput"]["permissionDecision"] == "ask"
    engine.post_failure(fail("pytest -q", err, "t3"))
    denied = engine.pre(pre("pytest -q", "t4"))
    reason = denied["hookSpecificOutput"]["permissionDecisionReason"]
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "stop" in reason and "Checkpoint" in reason and "Diagnose" in reason
    assert "failed fix" in reason
    assert engine.scars.all() == []


def test_known_fix_is_named_in_the_ask(engine):
    err = "Error: config/app.json not found"
    engine.pre(pre("bash scripts/build.sh", "a"))
    engine.post_failure(fail("bash scripts/build.sh", err, "a"))
    fix = "cp config/app.example.json config/app.json && bash scripts/build.sh"
    engine.pre(pre(fix, "b"))
    engine.post(PostToolUseInput(session_id="s", cwd="/p", hook_event_name="PostToolUse", tool_name="Bash",
                                 tool_input={"command": fix}, tool_use_id="b",
                                 tool_response={"stdout": "build ok", "stderr": "", "interrupted": False}))
    engine.pre(pre("bash scripts/build.sh", "c"))
    engine.post_failure(fail("bash scripts/build.sh", err, "c"))
    engine.post_failure(fail("bash scripts/build.sh", err, "d"))
    asked = engine.pre(pre("bash scripts/build.sh", "e"))
    assert asked["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "config/app.example.json" in asked["hookSpecificOutput"]["permissionDecisionReason"]


def test_second_edit_stops_and_a_revert_denies_without_scarring_the_file(engine):
    err = "Exit code 1\nE   assert 1 == 2"
    engine.pre(pre("pytest -q", "c"))
    engine.post_failure(fail("pytest -q", err, "c"))
    assert _write(engine, "src/app.py", "e1", "A\n") is None
    second = _write(engine, "src/app.py", "e2", "B\n")
    assert second["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "src/app.py" in second["hookSpecificOutput"]["permissionDecisionReason"]
    other = _write(engine, "src/other.py", "e3", "ok\n")
    assert other is None
    third = _write(engine, "src/app.py", "e4", "A\n")
    assert third["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Checkpoint" in third["hookSpecificOutput"]["permissionDecisionReason"]
    assert engine.scars.all() == []
    engine.pre(pre("pytest -q", "ok"))
    engine.post(PostToolUseInput(session_id="s", cwd="/p", hook_event_name="PostToolUse", tool_name="Bash",
                                 tool_input={"command": "pytest -q"}, tool_use_id="ok", tool_response={}))
    later = _write(engine, "src/app.py", "e5", "C\n")
    assert later is None or "permissionDecision" not in later["hookSpecificOutput"]


def test_read_only_command_does_not_clear_an_open_failure(engine):
    engine.pre(pre("git push origin main", "p"))
    engine.post_failure(fail("git push origin main", "error: failed to push some refs", "p"))
    engine.pre(pre("git status", "g"))
    engine.post(PostToolUseInput(session_id="s", cwd="/p", hook_event_name="PostToolUse", tool_name="Bash",
                                 tool_input={"command": "git status"}, tool_use_id="g", tool_response={}))
    assert engine.errors.open_family("git")["failures"] == 1


def test_destructive_cleanup_cites_the_open_failure(engine):
    err = "Exit code 2\nerror TS2304: Cannot find name 'x'"
    engine.pre(pre("npm run build", "b"))
    engine.post_failure(fail("npm run build", err, "b"))
    first = engine.pre(pre("git reset --hard", "d1"))
    assert first["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "TS2304" in first["hookSpecificOutput"]["permissionDecisionReason"]
    second = engine.pre(pre("rm -rf node_modules", "d2"))
    assert second["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "TS2304" in second["hookSpecificOutput"]["permissionDecisionReason"]
    assert "Checkpoint" in second["hookSpecificOutput"]["permissionDecisionReason"]
    third = engine.pre(pre("git push --force", "d3"))
    assert third["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert any(name == "escape" for name, _ in engine.events)


def test_spiral_episode_is_recalled_without_a_scar(engine):
    err = "Exit code 1\nE   assert 1 == 2"
    engine.prompt(UserPromptSubmitInput(session_id="s", cwd="/p", hook_event_name="UserPromptSubmit",
                                        prompt="make the tests pass"))
    engine.pre(pre("pytest -q", "t0"))
    engine.post_failure(fail("pytest -q", err, "t0"))
    engine.pre(pre("pytest -q", "t1"))
    hits = engine.memory.recall("pytest -q", 3)
    assert hits and hits[0].pain_id.startswith("s_")
    assert "assert 1 == 2" in hits[0].content
    assert engine.scars.all() == []
    ranked = engine._ranked("pytest -q", 1)
    assert ranked and ranked[0][3] is not None and ranked[0][3].source == "spiral"


def test_sensitization_lowers_thresholds_then_decays(tmp_path):
    now = {"t": 1_000_000.0}
    sense = Sensitization(tmp_path / "sensitize.json", now=lambda: now["t"])
    cells = list(range(200))
    sense.add("p1", cells, "fix the migration")
    active = np.array(cells[:80], dtype=np.int64)
    wary, flinch_at = sense.thresholds(0.25, 0.55, active, "fix the migration")
    assert wary < 0.2 and flinch_at < 0.4
    other = np.array(list(range(500, 700)), dtype=np.int64)
    assert sense.thresholds(0.25, 0.55, other, "fix the migration") == (0.25, 0.55)
    assert sense.thresholds(0.25, 0.55, active, "rename this function") == (0.25, 0.55)
    now["t"] += 8 * 60 * 60
    assert sense.strength(active, "fix the migration") < 0.05


def test_sensitized_area_asks_sooner(engine, monkeypatch):
    monkeypatch.setattr(engine.circuit, "avoid", lambda active: 0.2)
    monkeypatch.setattr(engine.sense, "strength", lambda active, task: 0.0)
    assert engine.pre(pre("mv backups archive", "m1")) is None
    monkeypatch.setattr(engine.sense, "strength", lambda active, task: 1.0)
    asked = engine.pre(pre("mv backups archive", "m2"))
    assert asked["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_backup_copy_is_not_blamed_for_the_write(tmp_path, fake_embedder):
    from flinch.pain import pick_culprit
    from flinch.recent import RecentActions

    recent = RecentActions(tmp_path / "recent.json")
    for i, action in enumerate(["Write:src/a.py", "cp src/a.py.bak src/a.py"]):
        recent.add(session_id="s", tool_use_id=str(i), tool="Bash", normalized=action,
                   fingerprint=str(i), failed=False)
    assert pick_culprit(recent.for_session("s"), "that broke the build").normalized == "Write:src/a.py"
