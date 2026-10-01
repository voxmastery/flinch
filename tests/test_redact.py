import pytest

from flinch.redact import redact


@pytest.mark.parametrize("secret", [
    "ghp_" + "a" * 36,
    "github_pat_" + "A1" * 20,
    "sk-ant-api03-" + "x" * 30,
    "sk-" + "Z" * 40,
    "AKIA" + "ABCDEFGHIJKLMNOP",
    "xoxb-1234-5678-abcdefgh",
])
def test_known_token_patterns(secret):
    out = redact(f"export TOKEN_USE {secret} done")
    assert secret not in out and "<REDACTED>" in out


def test_bearer_and_key_value():
    assert "s3cr3t" not in redact("curl -H 'Authorization: Bearer s3cr3tvalue'")
    assert "hunter2" not in redact("mysql --password=hunter2 db")
    assert "abc123" not in redact("API_KEY=abc123 ./run")


def test_plain_text_untouched():
    assert redact("rm -rf data/") == "rm -rf data/"


def test_url_userinfo_database_url_and_live_keys():
    assert "s3cret" not in redact("postgres://app:s3cret@db.internal/shop")
    assert "s3cret" not in redact("DATABASE_URL=postgres://app:s3cret@db.internal/shop")
    assert "sk_live_abcDEF123456" not in redact("paid with sk_live_abcDEF123456")
    assert "topsecret" not in redact('REDIS_URL: "redis://:topsecret@localhost:6379"')


@pytest.mark.parametrize("cmd,secret", [
    ("mycli --password hunter2ExtraLong login", "hunter2ExtraLong"),
    ("curl --api-key sk_liveXXXXYYYY https://x", "sk_liveXXXXYYYY"),
    ("tool --token=abcdef123456", "abcdef123456"),
    ("psql --secret 's3cr3t value'", "s3cr3t value"),
])
def test_flag_style_secrets(cmd, secret):
    assert secret not in redact(cmd)


def test_pem_block():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----"
    assert "MIIEow" not in redact(f"echo '{pem}' > k")
