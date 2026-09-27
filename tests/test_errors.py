from flinch.errors import ErrorMemory, signature


def test_signature_picks_error_line_and_is_stable():
    a = signature("Exit code 1\n> build\nError: Cannot find module 'express'\n    at load (/app/node_modules/x.js:12:5)")
    b = signature("Exit code 1\nError: Cannot find module 'express'\n    at load (/app/node_modules/x.js:99:1)")
    assert a == b and "Cannot find module 'express'" in a


def test_signature_redacts_secrets():
    assert "sk-ant" not in signature("Error: invalid key sk-ant-api03-" + "x" * 30)


def test_fix_is_learned_and_recalled(tmp_path):
    m = ErrorMemory(tmp_path / "errors.json")
    f1 = m.record_failure("npm run build", "Error: Cannot find module 'express'", change_count=3)
    assert f1.known_fix is None and f1.unchanged_repeats == 0
    lesson = m.record_success("npm run build", ["npm install express", "Edit:package.json"], change_count=5)
    assert lesson is not None and lesson.fixed_by == ("npm install express", "Edit:package.json")
    m2 = ErrorMemory(tmp_path / "errors.json")  # persisted
    again = m2.record_failure("npm run build", "Error: Cannot find module 'express'", change_count=9)
    assert again.known_fix is not None and "npm install express" in again.known_fix.fixed_by


def test_unchanged_repeats_counted_and_reset_by_changes(tmp_path):
    m = ErrorMemory(tmp_path / "errors.json")
    m.record_failure("pytest -q", "E assert 1 == 2", change_count=1)
    assert m.record_failure("pytest -q", "E assert 1 == 2", change_count=1).unchanged_repeats == 1
    assert m.record_failure("pytest -q", "E assert 1 == 2", change_count=1).unchanged_repeats == 2
    assert m.stuck("pytest -q", change_count=1) == 3  # failed three times in a row
    assert m.stuck("pytest -q", change_count=2) == 0  # something changed since the last failure
    assert m.record_failure("pytest -q", "E assert 1 == 2", change_count=2).unchanged_repeats == 0


def test_success_without_changes_is_not_a_lesson(tmp_path):
    m = ErrorMemory(tmp_path / "errors.json")
    m.record_failure("curl localhost:3000", "Connection refused", change_count=1)
    assert m.record_success("curl localhost:3000", [], change_count=1) is None  # flaky, not a fix
    assert m.lessons() == []


def test_lessons_listed_newest_first(tmp_path):
    m = ErrorMemory(tmp_path / "errors.json")
    for i, cmd in enumerate(["npm run build", "cargo test"]):
        m.record_failure(cmd, f"error: thing {cmd}", change_count=i * 2)
        m.record_success(cmd, [f"Edit:f{i}.rs"], change_count=i * 2 + 1)
    assert [l.command for l in m.lessons()] == ["cargo test", "npm run build"]


import pytest  # noqa: E402

from flinch.errors import core_command, masks_exit  # noqa: E402


@pytest.mark.parametrize("cmd,core,prefix", [
    ("cat scripts/build.sh ; bash scripts/build.sh", "scripts/build.sh", ()),
    ("cat scripts/build.sh ; ls -la ; bash scripts/build.sh 2 >& 1 | tail -40", "scripts/build.sh", ()),
    ("cp config/app.example.json config/app.json && sh scripts/build.sh", "scripts/build.sh",
     ("cp config/app.example.json config/app.json",)),
    ("./scripts/build.sh", "scripts/build.sh", ()),
    ("cd web && npm run build", "npm run build", ()),
    ("npm install express && npm run build", "npm run build", ("npm install express",)),
    ("ls", "ls", ()),
])
def test_core_command(cmd, core, prefix):
    assert core_command(cmd) == (core, prefix)


@pytest.mark.parametrize("cmd,masked", [
    ("bash scripts/build.sh 2 >& 1 | tail -40", True), ("npm test || true", True),
    ("pytest ; echo exit=$?", True), ("npm run build", False), ("cp a b && make", False),
])
def test_masks_exit(cmd, masked):
    assert masks_exit(cmd) == masked


def test_signature_prefers_real_error_over_source_lines():
    out = ('#!/bin/sh\nif [ ! -f config/app.json ]; then\n  echo "Error: config/app.json not found" >&2\n'
           '  exit 1\nfi\nError: config/app.json not found\nExit code 1')
    assert signature(out) == "Error: config/app.json not found"
