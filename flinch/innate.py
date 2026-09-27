"""Innate readouts: output units trained offline on labeled examples, shipped with Flinch.

Alongside the pain-learned unit, two readouts are pre-trained on the same sparse cell codes
(plus the whitened embedding): "danger" for actions and "report" for user messages. They are
plain logistic units; training lives in scripts/train_innate.py. No network, no keys.
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger("flinch")

WEIGHTS = Path(__file__).parent / "innate.npz"
DANGER_THRESHOLD = 0.9  # chosen on held-out tool families (see training report)
REPORT_THRESHOLD = 0.9  # zero false reports on held-out data at this level

# High-precision rules for well-known destroyers; the learned unit covers what these miss.
_STRONG = [
    (re.compile(r"(?:^|[\s;&|(])(?:sudo\s+)?rm\s+(?:-\w*\s+)*-\w*r", re.I), "recursive delete"),
    (re.compile(r"\bgit\s+push\b.*(?:--force\b|--force-with-lease\b|\s-f\b|--mirror\b|--delete\b|\s\+\S|\s:\S)"), "force push or remote delete"),
    (re.compile(r"\bgit\s+(?:reset\s+--hard|clean\s+-\w*f|branch\s+-D|checkout\s+--\s|restore\s+\.)"), "discards git history or changes"),
    (re.compile(r"\b(?:drop\s+(?:table|database|schema)|truncate\s+table|delete\s+from)\b", re.I), "destructive SQL"),
    (re.compile(r"\bdd\s.*\bof=|\b(?:mkfs\S*|shred|wipefs)\b"), "overwrites a disk or file"),
    (re.compile(r"\bfind\b.*\s-delete\b"), "bulk delete"),
    (re.compile(r"\b(?:terraform|pulumi|cdk)\s+destroy\b|\bkubectl\s+delete\b|\bhelm\s+(?:uninstall|delete)\b"), "destroys infrastructure"),
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
    text = executable_text(normalized)
    for pattern, label in _STRONG:
        if pattern.search(text):
            return label
    return None


@dataclass(frozen=True)
class Readout:
    w: np.ndarray
    b: float

    def __call__(self, code: np.ndarray, z: np.ndarray) -> float:
        x = float(self.w[: len(self.w) - len(z)][code].sum() + self.w[len(self.w) - len(z):] @ (4.0 * z) + self.b)
        return 1.0 / (1.0 + np.exp(-x))


def fingerprint_of(mu: np.ndarray, inputs: np.ndarray) -> str:
    """Identifies the encoding the weights were trained against (reference whitening + projection)."""
    return hashlib.sha256(np.round(mu, 5).tobytes() + inputs.tobytes()).hexdigest()[:16]


class Innate:
    def __init__(self, danger: Readout | None, report: Readout | None) -> None:
        self.danger = danger
        self.report = report

    @property
    def available(self) -> bool:
        return self.danger is not None

    @classmethod
    def load(cls, encoding_fingerprint: str, path: Path = WEIGHTS) -> "Innate":
        try:
            with np.load(path) as z:
                if str(z["fingerprint"]) != encoding_fingerprint:
                    log.warning("innate weights were trained for a different encoding; using rules only")
                    return cls(None, None)
                return cls(Readout(z["danger_w"], float(z["danger_b"])), Readout(z["report_w"], float(z["report_b"])))
        except (OSError, KeyError, ValueError):
            log.warning("innate weights missing or unreadable; using rules only")
            return cls(None, None)
