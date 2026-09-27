import pytest

from flinch.pain import PainDetector, is_test_command, looks_like_damage_report
from flinch.recent import RecentActions


@pytest.fixture
def recent(tmp_path):
    r = RecentActions(tmp_path / "recent.json")
    for i, a in enumerate(["Write:src/app.py", "rm -rf data/", "git add ."]):
        r.add(session_id="s", tool_use_id=f"t{i}", tool="Bash", normalized=a, fingerprint=str(i), failed=False)
    return r


def detector(recent, report=None, danger=None):
    return PainDetector(recent, report=report, danger=danger)


@pytest.mark.parametrize("text", ["you deleted the customer database!", "It wiped all my data",
                                  "that broke the build", "we lost all the backups"])
def test_heuristic_detects_reports(text):
    assert looks_like_damage_report(text)


@pytest.mark.parametrize("text", ["delete the old logs please", "clean up the project", "what did you change?"])
def test_heuristic_ignores_requests(text):
    assert not looks_like_damage_report(text)


def test_report_via_keywords_blames_destructive(recent):
    f = detector(recent).from_prompt("s", "you deleted the customer database!")
    assert f.normalized == "rm -rf data/" and f.source == "user_report" and f.severity == 1.0
    assert "customer database" in f.reason


def test_report_via_trained_readout(recent):
    msg = "the customer list looks empty to me"  # no keyword hit
    assert detector(recent).from_prompt("s", msg) is None
    f = detector(recent, report=lambda t: 0.95).from_prompt("s", msg)
    assert f is not None and f.normalized == "rm -rf data/"


def test_low_report_score_is_not_pain(recent):
    assert detector(recent, report=lambda t: 0.5).from_prompt("s", "what did you change?") is None


def test_blame_follows_what_the_user_names(tmp_path):
    r = RecentActions(tmp_path / "r.json")
    for i, a in enumerate(["rm -rf uploads/", "rm -rf data/", "git status"]):
        r.add(session_id="s", tool_use_id=str(i), tool="Bash", normalized=a, fingerprint=str(i), failed=False)
    assert detector(r).from_prompt("s", "you deleted all the uploads!").normalized == "rm -rf uploads/"
    assert detector(r).from_prompt("s", "you deleted my files!").normalized == "rm -rf data/"


def test_danger_readout_marks_unknown_destroyer_for_blame(tmp_path):
    r = RecentActions(tmp_path / "r.json")
    for i, a in enumerate(["fly apps destroy shop -y", "git log"]):
        r.add(session_id="s", tool_use_id=str(i), tool="Bash", normalized=a, fingerprint=str(i), failed=False)
    danger = lambda t: 0.95 if "destroy" in t else 0.05  # noqa: E731
    assert detector(r, danger=danger).from_prompt("s", "you broke production").normalized == "fly apps destroy shop -y"


def test_no_recent_actions_no_finding(tmp_path):
    assert detector(RecentActions(tmp_path / "r.json")).from_prompt("s", "you deleted everything") is None


@pytest.mark.parametrize("cmd,yes", [("pytest -q", True), ("npm test", True), ("npm run test", True),
                                      ("go test ./...", True), ("cargo test", True), ("ls tests", False)])
def test_is_test_command(cmd, yes):
    assert is_test_command(cmd) == yes


def test_regression_attributed_to_last_write(recent):
    d = detector(recent)
    assert d.test_result("s", "pytest -q", passed=True) is None
    f = d.test_result("s", "pytest -q", passed=False)
    assert f.normalized == "Write:src/app.py" and f.source == "regression" and f.severity == 0.5
    assert d.test_result("s", "pytest -q", passed=False) is None  # already failing: not a new regression


def test_fallback_prefers_recent_destructive_action(tmp_path):
    from flinch.pain import pick_culprit

    r = RecentActions(tmp_path / "r.json")
    for i, a in enumerate(["Write:src/a.py", "rm -rf data/", "git ls-tree -r HEAD | rg data", "touch x"]):
        r.add(session_id="s", tool_use_id=str(i), tool="Bash", normalized=a, fingerprint=str(i), failed=False)
    assert pick_culprit(r.for_session("s")).normalized == "rm -rf data/"


def test_fallback_without_destructive_uses_latest(tmp_path):
    from flinch.pain import pick_culprit

    r = RecentActions(tmp_path / "r.json")
    for i, a in enumerate(["Write:src/a.py", "touch x"]):
        r.add(session_id="s", tool_use_id=str(i), tool="Bash", normalized=a, fingerprint=str(i), failed=False)
    assert pick_culprit(r.for_session("s")).normalized == "touch x"


@pytest.mark.parametrize("cmd,yes", [
    ("rm -rf data/", True), ("git push --force origin main", True), ("echo x > out.txt", True),
    ("sqlite3 db 'drop table t'", True), ("git reset --hard HEAD~3", True), ("Delete:notes.txt", True),
    ("sqlite3 -readonly backups/c-<TS>.db 'select 1' 2 >& 1 || file x", False),
    ("ls <TMP>", False), ("grep x y > /dev/null", False), ("cat a | wc -l", False), ("pytest -q", False),
])
def test_looks_destructive(cmd, yes):
    from flinch.pain import looks_destructive

    assert looks_destructive(cmd) == yes


def test_multiline_test_command():
    assert is_test_command("cd project\npytest -q")
    assert is_test_command("set -e\nnpm test")


def test_quoted_text_is_not_destructive_for_blame():
    from flinch.pain import looks_destructive

    assert not looks_destructive('echo "rm -rf /" >> README.md')
    assert not looks_destructive('grep "delete from users" app.sql')
    assert looks_destructive("echo x > data/customers.db")
