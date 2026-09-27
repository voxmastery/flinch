import io
import json

from flinch import scarcheck
from flinch.scars import ScarStore


def run(home, body, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(body) if not isinstance(body, str) else body))
    return scarcheck.main(["--home", str(home)])


def body(cmd):
    return {"session_id": "s", "cwd": "/x", "hook_event_name": "PreToolUse",
            "tool_name": "Bash", "tool_input": {"command": cmd}}


def test_exits_2_on_scar_match(tmp_path, monkeypatch, capsys):
    home = tmp_path / ".flinch"
    ScarStore(home / "scars.json").add("rm -rf data/", "deleted db", 1.0)
    assert run(home, body("rm  -rf data/"), monkeypatch) == 2
    err = capsys.readouterr().err
    assert "deleted db" in err and "flinch forgive" in err


def test_exits_0_otherwise(tmp_path, monkeypatch):
    home = tmp_path / ".flinch"
    ScarStore(home / "scars.json").add("rm -rf data/", "deleted db", 1.0)
    assert run(home, body("ls"), monkeypatch) == 0


def test_exits_0_on_garbage_or_missing_state(tmp_path, monkeypatch):
    assert run(tmp_path / "none", body("rm -rf data/"), monkeypatch) == 0
    assert run(tmp_path / "none", "garbage", monkeypatch) == 0


def test_is_stdlib_only():
    import ast
    import sys
    from pathlib import Path

    import flinch

    pkg = Path(flinch.__file__).parent
    for mod in ("scarcheck", "normalize", "redact", "messages", "locate", "relay", "cursor_hook", "__init__"):
        tree = ast.parse((pkg / f"{mod}.py").read_text())
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            for n in names:
                top = n.split(".")[0]
                assert top == "flinch" or top in sys.stdlib_module_names, f"{mod} imports {n}"


def test_resolves_central_state_from_cwd(tmp_path, monkeypatch, capsys):
    from flinch.locate import state_dir

    monkeypatch.delenv("FLINCH_HOME", raising=False)
    monkeypatch.setenv("FLINCH_DATA_HOME", str(tmp_path / "data"))
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    ScarStore(state_dir(repo) / "scars.json").add("rm -rf data/", "deleted db", 1.0)
    b = {**body("rm -rf data/"), "cwd": str(repo / "src")}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(b)))
    assert scarcheck.main([]) == 2
