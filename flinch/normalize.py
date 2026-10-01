"""Action normalization and fingerprinting (SPEC §4). Stdlib only: shared with scarcheck."""

import hashlib
import json
import os
import re
import shlex
from typing import Any

from flinch.redact import redact

_ENV_PREFIX = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*=(?:'[^']*'|\"[^\"]*\"|\S*)\s+)+")
_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_TS = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b"
)
_TMP = re.compile(r"(?<![\w/.$])(?:/private/tmp|/var/tmp|/tmp|\$\{TMPDIR\}|\$TMPDIR)(?=/|\s|$|['\"])[^\s'\"]*")
# A hash-like run needs both a digit and a hex letter: "1234567" is a number, "defaced" a word.
_HEX = re.compile(r"(?<!\w)(?=[0-9a-fA-F]*[a-fA-F])(?=[0-9a-fA-F]*\d)[0-9a-fA-F]{7,}(?!\w)")
_WS = re.compile(r"\s+")


_OPERATOR = re.compile(r"^[();<>|&]+$")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _canonical_shell(command: str) -> str | None:
    """Re-render through a shell tokenizer so quoting and operator spacing don't matter.

    `rm -rf 'data/'` and `rm -rf data/` become the same text. Argument order and path
    spelling are kept: telling near-misses apart is the reflex circuit's job, not the scar's.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    while tokens and _ASSIGNMENT.match(tokens[0]):
        tokens = tokens[1:]
    return " ".join(t if _OPERATOR.match(t) else shlex.quote(t) for t in tokens)


def _bash(command: str) -> str:
    canonical = _canonical_shell(command)
    if canonical is None:
        s = _ENV_PREFIX.sub("", _WS.sub(" ", command).strip())
    else:
        s = canonical
    s = redact(s)
    s = _UUID.sub("<UUID>", s)
    s = _TS.sub("<TS>", s)
    s = _TMP.sub("<TMP>", s)
    return _HEX.sub("<HEX>", s)


def _rel_path(file_path: str, root: str) -> str:
    try:
        rel = os.path.relpath(file_path, root)
    except ValueError:
        return file_path
    return file_path if rel.startswith("..") else rel


def normalize(tool_name: str, tool_input: dict[str, Any], root: str) -> str:
    """Stable text form of an action. `root` is the project root (parent of .flinch/)."""
    if tool_name == "Bash":
        return _bash(str(tool_input.get("command", "")))
    if tool_name in ("Write", "Edit", "Delete") and "file_path" in tool_input:
        return f"{tool_name}:{_rel_path(str(tool_input['file_path']), root)}"
    canonical = json.dumps(tool_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return f"{tool_name}:{redact(canonical)}"


def fingerprint(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


_SUDO_WITH_ARG = {"-u", "-g", "-h", "-p", "-C", "-T", "-r", "-t", "--user", "--group", "--host", "--prompt"}
_GIT_WITH_ARG = {"-C", "--git-dir", "--work-tree", "--namespace"}
_RM_LONG = {"--recursive": "-r", "--force": "-f"}


def _basename(token: str) -> str:
    return token.rsplit("/", 1)[-1]


def _strip_sudo(tokens: list[str]) -> list[str]:
    i = 0
    while i < len(tokens) and _basename(tokens[i]) == "sudo":
        i += 1
        while i < len(tokens) and tokens[i].startswith("-"):
            flag = tokens[i]
            i += 1
            if flag in _SUDO_WITH_ARG and i < len(tokens) and not tokens[i].startswith("-"):
                i += 1
    return tokens[i:]


def _strip_git_globals(tokens: list[str]) -> list[str]:
    if not tokens or _basename(tokens[0]) != "git":
        return tokens
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-c", "--config"):
            i += 1
            if i >= len(tokens):
                break
            i += 2 if "=" not in tokens[i] else 1
            continue
        if tok in _GIT_WITH_ARG:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        break
    return ["git", *tokens[i:]]


def _expand_rm(tokens: list[str]) -> list[str]:
    if not tokens or _basename(tokens[0]) != "rm":
        return tokens
    out = ["rm"]
    for tok in tokens[1:]:
        out.append(_RM_LONG.get(tok, tok))
    return out


def danger_command(command: str) -> str:
    """Form used by danger rules: basename, no sudo, no `git -c`, rm long options expanded.

    Scar fingerprints keep the original normalized text. This form is only for the rules.
    """
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return command
    while tokens and _ASSIGNMENT.match(tokens[0]):
        tokens = tokens[1:]
    tokens = _strip_sudo(tokens)
    tokens = _strip_git_globals(tokens)
    if tokens:
        tokens[0] = _basename(tokens[0])
        tokens = _expand_rm(tokens)
    return " ".join(tokens)
