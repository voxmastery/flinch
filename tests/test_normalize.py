import pytest

from flinch.normalize import fingerprint, normalize

ROOT = "/home/u/shop"


def bash(cmd: str) -> str:
    return normalize("Bash", {"command": cmd}, ROOT)


def test_whitespace_collapsed():
    assert bash("  rm   -rf \t data/  ") == "rm -rf data/"


def test_leading_env_assignments_stripped():
    assert bash("FOO=1 BAR='a b' rm -rf data/") == "rm -rf data/"


@pytest.mark.parametrize("a,b", [
    ("rm -rf /tmp/build-123/out", "rm -rf /tmp/xyz"),
    ("cp x $TMPDIR/a", "cp x ${TMPDIR}/b"),
    ("rm run-550e8400-e29b-41d4-a716-446655440000.log", "rm run-6ba7b810-9dad-11d1-80b4-00c04fd430c8.log"),
    ("git reset --hard 3f9a2c1d", "git reset --hard a1b2c3d4e5f6"),
    ("rm backups/c-2026-09-20.db", "rm backups/c-2026-09-21.db"),
    ("echo 2026-09-27T11:13:43Z", "echo 2025-01-01T00:00:00+02:00"),
])
def test_volatile_tokens_share_fingerprint(a, b):
    assert fingerprint(bash(a)) == fingerprint(bash(b))


@pytest.mark.parametrize("a,b", [
    ("rm -rf data/", "rm -rf src/"),
    ("rm -rf data/", "rm -rf ./data"),  # generalization is the circuit's job, not the scar's
    ("sleep 1234567", "sleep 7654321"),  # plain numbers carry meaning
    ("echo defaced", "echo effaced"),  # hex-letter words are not hashes
])
def test_meaningful_differences_kept(a, b):
    assert fingerprint(bash(a)) != fingerprint(bash(b))


def test_tmp_only_at_path_start():
    assert bash("rm -rf data/tmp/x") == "rm -rf data/tmp/x"


def test_write_edit_use_relative_path_and_ignore_content():
    a = normalize("Write", {"file_path": f"{ROOT}/src/app.py", "content": "one"}, ROOT)
    b = normalize("Write", {"file_path": f"{ROOT}/src/app.py", "content": "two"}, ROOT)
    assert a == b == "Write:src/app.py"
    assert normalize("Edit", {"file_path": "/etc/hosts", "old_string": "x"}, ROOT) == "Edit:/etc/hosts"


def test_mcp_canonical_json():
    a = normalize("mcp__db__query", {"b": 1, "a": "x"}, ROOT)
    b = normalize("mcp__db__query", {"a": "x", "b": 1}, ROOT)
    assert a == b == 'mcp__db__query:{"a":"x","b":1}'


def test_secrets_redacted_in_normalized_form():
    n = bash("curl -H 'Authorization: Bearer abcdef0123456789xyz' https://api.x.com")
    assert "abcdef0123456789xyz" not in n


def test_fingerprint_is_sha256_hex():
    fp = fingerprint("x")
    assert len(fp) == 64 and int(fp, 16) >= 0


@pytest.mark.parametrize("a,b", [
    ("rm -rf data/", "rm -rf 'data/'"),
    ("rm -rf data/", 'rm -rf "data/"'),
    ("ls&&rm -rf data/", "ls && rm -rf data/"),
    ("cat x|grep y", "cat x | grep y"),
    ("echo a>out", "echo a > out"),
    ("FOO='a b' rm -rf data/", "rm -rf data/"),
])
def test_shell_equivalent_forms_share_fingerprint(a, b):
    assert bash(a) == bash(b)


def test_unbalanced_quotes_fall_back():
    assert bash("echo 'oops") == "echo 'oops"


def test_hash_char_is_not_a_comment_mid_word():
    assert bash("echo a#b") != bash("echo a")
