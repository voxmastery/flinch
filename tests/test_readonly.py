import pytest

from flinch.readonly import is_mutating


@pytest.mark.parametrize("cmd", [
    "ls data", "cat README.md | grep shop", "git status", "git log --oneline -5",
    "find . -name '*.py'", "sed -n 1,5p x", "ls missing 2>&1", "grep x y > /dev/null",
])
def test_read_only_bash(cmd):
    assert not is_mutating("Bash", {"command": cmd})


@pytest.mark.parametrize("cmd", [
    "rm -rf data/", "ls && rm x", "echo hi > out.txt", "sed -i s/a/b/ f", "find . -delete",
    "git push --force origin main", "git branch -D main", "sqlite3 db 'drop table t'", "python x.py",
    "ls; mv a b",
])
def test_mutating_bash(cmd):
    assert is_mutating("Bash", {"command": cmd})


def test_other_tools():
    assert is_mutating("Write", {"file_path": "/x"})
    assert is_mutating("Edit", {"file_path": "/x"})
    assert is_mutating("mcp__db__exec", {})
    assert not is_mutating("Read", {"file_path": "/x"})


@pytest.mark.parametrize("cmd", [
    "git ls-tree -r --name-only HEAD | rg '^data/'", "git cat-file -p HEAD", "git grep TODO",
    "git remote -v", "git config --get user.name", "git stash list", "sha256sum x", "fd data",
])
def test_more_read_only(cmd):
    assert not is_mutating("Bash", {"command": cmd})


@pytest.mark.parametrize("cmd", ["git remote add o x", "git config user.name x", "git stash drop", "git clean -fd"])
def test_more_mutating(cmd):
    assert is_mutating("Bash", {"command": cmd})
