"""Error memory: failures, what fixed them, and agents stuck repeating a failing command.

Damage becomes a scar; errors become lessons. When a failing command later passes, the
state-changing actions in between are stored as its fix, and the next time the same error
shows up the agent is told what fixed it last time.
"""

import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from flinch.jsonfile import SCHEMA_VERSION, file_lock, read_versioned, write_json_atomic
from flinch.spiral import command_family
from flinch.redact import redact

MAX_SIGNATURE = 160
MAX_FIX_STEPS = 5
MAX_LESSONS = 200
_ERROR_LINE = re.compile(r"(?i)\b(error|err!|fatal|failed|failure|exception|traceback|cannot|can't|not found|"
                         r"no such|undefined|denied|refused|missing|invalid|unexpected|panic|assert)")
_NOISE = re.compile(r"^\s*(exit code \d+|at .*\(.*:\d+:\d+\)|at .*:\d+:\d+|\^+|~+)\s*$", re.I)
_VOLATILE = re.compile(r"\b\d+[:.]\d+(?:[:.]\d+)*\b|0x[0-9a-f]+|\b[0-9a-f]{8,}\b", re.I)


# Lines that are source code (e.g. a script printed with `cat`), not the error itself.
_SOURCE_LIKE = re.compile(r"^\s*(echo|printf|print\(|console\.|raise\b|throw\b|#|if\b|fi\b|then\b|else\b|exit\s+\d)")
_SHELLS = {"bash", "sh", "zsh"}
_SEPARATORS = {";", "&&", "||", "&"}
_REDIRECTS = {">", ">>", ">&", "<", "&>", "2>", "2>&1"}


def has_error_line(text: str) -> bool:
    return any(_ERROR_LINE.search(ln) and not _SOURCE_LIKE.match(ln) and not _NOISE.match(ln)
               for ln in text.splitlines())


def signature(error: str) -> str:
    """Stable, redacted fingerprint of an error: its last real error line, volatile bits removed."""
    lines = [ln.strip() for ln in redact(error).splitlines()
             if ln.strip() and not _NOISE.match(ln) and not _SOURCE_LIKE.match(ln)]
    errors = [ln for ln in lines if _ERROR_LINE.search(ln)]
    pick = errors[-1] if errors else (lines[-1] if lines else "")
    return _VOLATILE.sub("#", re.sub(r"\s+", " ", pick))[:MAX_SIGNATURE]


def _tokens(command: str) -> list[str] | None:
    import shlex

    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return None


def _segments(tokens: list[str]) -> list[list[str]]:
    """Split on ; && || &, cut each segment at its first pipe, drop redirections."""
    out, cur, piped = [], [], False
    skip = False
    for tok in tokens:
        if tok in _SEPARATORS:
            out.append(cur)
            cur, piped = [], False
            continue
        if piped or skip:
            skip = False
            continue
        if tok == "|":
            piped = True
            continue
        if tok in _REDIRECTS or (tok.startswith(">") and set(tok) <= set(">&")):
            if cur and cur[-1].isdigit():
                cur.pop()
            skip = True
            continue
        cur.append(tok)
    out.append(cur)
    return [seg for seg in out if seg]


def core_command(command: str) -> tuple[str, tuple[str, ...]]:
    """(the command that matters, state-changing setup steps before it) for a compound shell command.

    `cat x ; bash scripts/build.sh 2>&1 | tail` -> ("scripts/build.sh", ()),
    `cp a.example a && sh scripts/build.sh` -> ("scripts/build.sh", ("cp a.example a",)).
    """
    from flinch.readonly import _segment_is_read_only

    tokens = _tokens(command)
    if not tokens:
        return command, ()
    segments = [" ".join(seg) for seg in _segments(tokens)]
    acting = [seg for seg in segments if not _segment_is_read_only(seg)]
    if not acting:
        return (segments[-1] if segments else command), ()
    core = acting[-1].split(" ")
    if core[0] in _SHELLS and len(core) > 1 and not core[1].startswith("-"):
        core = core[1:]
    if core[0].startswith("./"):
        core = [core[0][2:], *core[1:]]
    return " ".join(core), tuple(acting[:-1])


def masks_exit(command: str) -> bool:
    """True when the shell's exit status won't reflect the command that matters."""
    tokens = _tokens(command) or []
    if "|" in tokens or "||" in tokens:
        return True
    if ";" in tokens:
        last = tokens[len(tokens) - 1 - tokens[::-1].index(";") + 1:]
        return bool(last) and last[0] in ("echo", "printf", "true", ":")
    return False


@dataclass(frozen=True)
class Lesson:
    command: str
    signature: str
    fixed_by: tuple[str, ...]
    failed_at: float
    fixed_at: float


@dataclass(frozen=True)
class Failure:
    signature: str
    unchanged_repeats: int  # previous failures of this command with nothing changed in between
    known_fix: Lesson | None


class ErrorMemory:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        with file_lock(path):
            raw = read_versioned(path, "errors")
        raw = raw if isinstance(raw, dict) else {}
        self._open: dict[str, dict] = dict(raw.get("open", {}))
        self.change_count: int = int(raw.get("change_count", 0))
        self._lessons: tuple[Lesson, ...] = tuple(
            Lesson(**{**lesson, "fixed_by": tuple(lesson["fixed_by"])}) for lesson in raw.get("lessons", []))
        self._spirals: list[dict] = [s for s in raw.get("spirals", []) if isinstance(s, dict)]
        self._recall_ids: list[str] = [str(x) for x in raw.get("recall_ids", [])]

    def _save(self) -> None:
        with file_lock(self._path):
            write_json_atomic(self._path, {
                "schema_version": SCHEMA_VERSION, "open": self._open, "change_count": self.change_count,
                "lessons": [asdict(x) for x in self._lessons], "spirals": self._spirals,
                "recall_ids": self._recall_ids})

    def bump(self) -> int:
        """Something in the project changed (a state-changing action succeeded)."""
        with self._lock:
            self.change_count += 1
            self._save()
            return self.change_count

    def record_failure(self, command: str, error: str, change_count: int) -> Failure:
        sig = signature(error)
        with self._lock:
            prev = self._open.get(command)
            same = prev is not None and prev["signature"] == sig and prev["change_count"] == change_count
            repeats = prev["unchanged_repeats"] + 1 if same else 0
            self._open = {**self._open, command: {
                "signature": sig, "change_count": change_count, "unchanged_repeats": repeats,
                "failed_at": prev["failed_at"] if prev else time.time()}}
            self._save()
            fix = next((x for x in reversed(self._lessons) if x.signature == sig), None)
        return Failure(sig, repeats, fix)

    def record_success(self, command: str, changes: list[str], change_count: int) -> Lesson | None:
        with self._lock:
            prev = self._open.get(command)
            if prev is None:
                return None
            self._open = {k: v for k, v in self._open.items() if k != command}
            lesson = None
            if changes:  # it passed after something changed: that's the fix
                lesson = Lesson(command, prev["signature"], tuple(changes[-MAX_FIX_STEPS:]), prev["failed_at"],
                                time.time())
                self._lessons = (*[x for x in self._lessons if (x.command, x.signature) != (command, lesson.signature)],
                                 lesson)[-MAX_LESSONS:]
            self._save()
        return lesson

    def stuck(self, command: str, change_count: int) -> int:
        """How many times in a row this command failed with nothing changed since (0 if not stuck)."""
        prev = self._open.get(command)
        if prev is None or prev["change_count"] != change_count:
            return 0
        return prev["unchanged_repeats"] + 1

    def open_failure(self, command: str) -> dict | None:
        return self._open.get(command)

    def lessons(self) -> list[Lesson]:
        return sorted(self._lessons, key=lambda x: x.fixed_at, reverse=True)

    def known_fix_step(self, sig: str) -> str | None:
        for lesson in self.lessons():
            if lesson.signature == sig and lesson.fixed_by:
                safe = [step for step in lesson.fixed_by]
                if safe:
                    return safe[0]
        return None

    def record_check_failure(self, family: str, command: str, error: str, task: str) -> dict:
        """Same signature and family increments. A new signature closes the old spiral.

        `change_count` is ignored: an edit between failures is not progress.
        """
        sig = signature(error)
        with self._lock:
            current = self._open_family(family)
            if current is not None and current["signature"] != sig:
                current["open"] = False
                current = None
            if current is None:
                current = {
                    "id": f"sp_{uuid.uuid4().hex[:8]}", "family": family, "signature": sig,
                    "failures": 1, "fixes": 1, "commands": [command], "edits": {}, "destructive": 0,
                    "pain_id": "", "grade": "", "task": task, "opened_at": time.time(), "open": True,
                }
                self._spirals = [*self._spirals, current]
            else:
                commands = list(current["commands"])
                if command not in commands:
                    commands.append(command)
                current = {**current, "failures": current["failures"] + 1, "fixes": current["fixes"] + 1,
                           "commands": commands, "task": task or current.get("task") or ""}
                self._replace(current)
            self._save()
            return dict(current)

    def close_family(self, family: str) -> None:
        with self._lock:
            changed = False
            updated = []
            for row in self._spirals:
                if row.get("open") and row.get("family") == family:
                    updated.append({**row, "open": False})
                    changed = True
                else:
                    updated.append(row)
            open_left = {k: v for k, v in self._open.items() if command_family(k) != family}
            if open_left != self._open:
                self._open = open_left
                changed = True
            if changed:
                self._spirals = updated
                self._save()

    def open_spirals(self) -> list[dict]:
        return [dict(s) for s in self._spirals if s.get("open")]

    def open_family(self, family: str) -> dict | None:
        row = self._open_family(family)
        return dict(row) if row else None

    def active_spiral(self) -> dict | None:
        opens = self.open_spirals()
        return opens[-1] if opens else None

    def note_edit(self, path: str, hashes: list[str]) -> dict | None:
        with self._lock:
            row = self._active_locked()
            if row is None:
                return None
            edits = dict(row.get("edits") or {})
            prior = dict(edits.get(path) or {"n": 0, "hashes": []})
            seen = list(prior.get("hashes") or [])
            for h in hashes:
                if h not in seen:
                    seen.append(h)
            edits[path] = {"n": int(prior.get("n") or 0) + 1, "hashes": seen[-12:]}
            row = {**row, "edits": edits, "fixes": int(row.get("fixes") or 0) + 1}
            self._replace(row)
            self._save()
            return dict(row)

    def note_destructive(self) -> dict | None:
        with self._lock:
            row = self._active_locked()
            if row is None:
                return None
            row = {**row, "destructive": int(row.get("destructive") or 0) + 1,
                   "fixes": int(row.get("fixes") or 0) + 1}
            self._replace(row)
            self._save()
            return dict(row)

    def mark_spiral(self, spiral_id: str, pain_id: str, grade: str) -> None:
        with self._lock:
            for row in self._spirals:
                if row.get("id") == spiral_id:
                    self._replace({**row, "pain_id": pain_id, "grade": grade})
                    if pain_id and pain_id not in self._recall_ids:
                        self._recall_ids = [*self._recall_ids, pain_id]
                    self._save()
                    return

    def recall_ids(self) -> set[str]:
        return set(self._recall_ids)

    def _open_family(self, family: str) -> dict | None:
        for row in reversed(self._spirals):
            if row.get("open") and row.get("family") == family:
                return row
        return None

    def _active_locked(self) -> dict | None:
        for row in reversed(self._spirals):
            if row.get("open"):
                return row
        return None

    def _replace(self, row: dict) -> None:
        self._spirals = [row if s.get("id") == row.get("id") else s for s in self._spirals]
