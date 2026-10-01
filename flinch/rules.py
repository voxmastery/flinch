"""High-precision danger rules. Stdlib only, shared with the offline scar check.

`strong_rule` sees a normalized command: sudo and `git -c` are peeled off, the executable
is its basename, and rm's long options are the short flags the patterns already know.
"""

import re

from flinch.normalize import danger_command

# High-precision rules for well-known destroyers; the learned unit covers what these miss.
_STRONG = [
    (re.compile(r"(?:^|[\s;&|(])(?:sudo\s+)?rm\s+(?:-\w*\s+)*-\w*r", re.I), "recursive delete"),
    (re.compile(r"\bgit\s+push\b.*(?:--force\b|--force-with-lease\b|\s-f\b|--mirror\b|--delete\b|\s\+\S|\s:\S)"),
     "force push or remote delete"),
    (re.compile(r"\bgit\s+(?:reset\s+--hard|clean\s+-\w*f|branch\s+-D|checkout\s+--\s|restore\s+\.)"),
     "discards git history or changes"),
    (re.compile(r"\b(?:drop\s+(?:table|database|schema)|truncate\s+table|delete\s+from)\b", re.I), "destructive SQL"),
    (re.compile(r"\bdd\s.*\bof=|\b(?:mkfs\S*|shred|wipefs)\b"), "overwrites a disk or file"),
    (re.compile(r"\bfind\b.*\s-delete\b"), "bulk delete"),
    (re.compile(r"\b(?:terraform|pulumi|cdk)\s+destroy\b|\bkubectl\s+delete\b|\bhelm\s+(?:uninstall|delete)\b"),
     "destroys infrastructure"),
    (re.compile(r"\b(?:flushall|flushdb|dropdb|dropDatabase)\b", re.I), "wipes a datastore"),
    (re.compile(r"\bprune\b.*(?:-a|--all|--volumes|-f)|\bvolume\s+rm\b|\bdown\b.*(?:\s-v\b|--volumes)"),
     "deletes containers or volumes"),
    (re.compile(r"\b(?:env|secrets?|config)\s*:?\s*(?:rm|unset|delete|remove)\b", re.I), "removes secrets or config"),
]


# Commands whose quoted argument is itself executed (SQL, shell, remote commands).
_RUNS_QUOTED = {"psql", "mysql", "sqlite3", "mongo", "mongosh", "redis-cli", "cqlsh", "clickhouse-client",
                "bash", "sh", "zsh", "eval", "ssh", "sudo", "xargs", "docker", "kubectl", "npx", "node", "python",
                "python3", "duckdb", "sqlcmd"}
_OPERATORS = {"&&", "||", ";", "|", "&", "(", ")"}


def executable_text(command: str) -> str:
    """The parts of a shell command that execute: quoted strings become Q unless the command runs them.

    `grep "delete from users" f` -> `grep Q f`, while `psql -c 'drop table x'` keeps its SQL.
    """
    import shlex

    lexer = shlex.shlex(command, posix=False, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return command
    out, head = [], None
    for tok in tokens:
        if tok in _OPERATORS:
            head = None
            out.append(tok)
            continue
        if head is None:
            head = tok.rsplit("/", 1)[-1]
        if len(tok) >= 2 and tok[0] in "'\"" and tok[-1] == tok[0]:
            out.append(tok[1:-1] if head in _RUNS_QUOTED else "Q")
        else:
            out.append(tok)
    return " ".join(out)


def strong_rule(normalized: str) -> str | None:
    text = danger_command(executable_text(normalized))
    for pattern, label in _STRONG:
        if pattern.search(text):
            return label
    return None
