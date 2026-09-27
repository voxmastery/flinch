from pathlib import Path

from flinch.locate import project_root, state_dir


def test_git_root_found_from_subdir(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    sub = tmp_path / "repo" / "src" / "pkg"
    sub.mkdir(parents=True)
    assert project_root(str(sub)) == tmp_path / "repo"


def test_explicit_flinch_dir_wins_over_git(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    (tmp_path / "repo" / "app" / ".flinch").mkdir(parents=True)
    assert project_root(str(tmp_path / "repo" / "app" / "x")) == tmp_path / "repo" / "app"


def test_no_markers_uses_cwd(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    assert project_root(str(d)) == d


def test_state_dir_local_when_opted_in(tmp_path):
    (tmp_path / ".flinch").mkdir()
    assert state_dir(tmp_path) == tmp_path / ".flinch"


def test_state_dir_central_otherwise(tmp_path, monkeypatch):
    monkeypatch.setenv("FLINCH_DATA_HOME", str(tmp_path / "data"))
    a, b = state_dir(tmp_path / "shop"), state_dir(tmp_path / "other" / "shop")
    assert a.parent == tmp_path / "data" / "projects" and a != b and a.name.startswith("shop-")
    assert state_dir(tmp_path / "shop") == a  # stable


def test_flinch_home_env_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("FLINCH_HOME", str(tmp_path / "h"))
    assert state_dir(Path("/anything")) == tmp_path / "h"
