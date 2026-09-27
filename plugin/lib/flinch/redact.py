"""Secret redaction. Applied before anything is logged, embedded, stored, or sent out. Stdlib only."""

import re

MASK = "<REDACTED>"

_TOKENS = re.compile(
    r"ghp_[A-Za-z0-9]{20,}"
    r"|gh[ousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-[A-Za-z0-9_\-]{16,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|xox[abprs]-[A-Za-z0-9\-]{8,}"
)
_BEARER = re.compile(r"(?i)\b(bearer|token|basic)\s+[A-Za-z0-9._~+/=\-]{8,}")
_KEY_VALUE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:api[_-]?key|secret|token|passw(?:or)?d|pwd)[A-Z0-9_]*)(\s*[=:]\s*)"
    r"(\"[^\"]*\"|'[^']*'|[^\s'\"]+)"
)
_SECRET_WORD = r"(?:api[_-]?key|secret|token|passw(?:or)?d|pwd)"
# `--password value`: flags only, so prose like "my password is" is left alone.
_FLAG_VALUE = re.compile(
    rf"(?i)(\s--?[A-Za-z0-9_-]*{_SECRET_WORD}[A-Za-z0-9_-]*)(\s+)(\"[^\"]*\"|'[^']*'|[^\s'\"-][^\s'\"]*)"
)
_PEM = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.S)


def redact(text: str) -> str:
    text = _PEM.sub(MASK, text)
    text = _TOKENS.sub(MASK, text)
    text = _FLAG_VALUE.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", text)
    text = _BEARER.sub(lambda m: f"{m.group(1)} {MASK}", text)
    return _KEY_VALUE.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", text)
