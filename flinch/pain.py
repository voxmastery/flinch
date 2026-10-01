"""Damage detection and attribution (SPEC §6)."""

import re
import threading
from collections.abc import Callable
from dataclasses import dataclass

from flinch.recent import Action, RecentActions
from flinch.redact import redact

MAX_REASON = 200
DANGER_FOR_BLAME = 0.5  # a candidate counts as destructive if the danger readout says so at this level
Score = Callable[[str], float | None]

_DAMAGE_VERB = (r"(deleted|removed|wiped|destroyed|dropped|erased|nuked|broke|broken|corrupted|"
                r"overwrote|overwritten|lost|trashed|killed|reset)")
_REPORT = re.compile(
    rf"(?i)\b(you|claude|it|that|this|your (?:command|change|edit))\b[^.?!]{{0,40}}\b{_DAMAGE_VERB}\b"
    rf"|\b(we|i)\s+(just\s+)?lost\b|\bdata loss\b"
    rf"|\b(is|are)\s+(all\s+)?(gone|missing|empty(\s+now)?)\b|\bdisappeared\b"
)
_DESTRUCTIVE_WORDS = re.compile(r"(?i)\b(deleted|wiped|destroyed|dropped|erased|nuked|lost|overwr\w+)\b")
_TEST_CMD = re.compile(
    r"(?m)(?:^|&&|;|\|)\s*(?:python3? -m pytest|pytest|npm (?:run )?test|yarn test|pnpm test|go test|cargo test|"
    r"make test|npx (?:jest|vitest)|jest|vitest|mvn test|gradle test|\./gradlew test|rspec|phpunit|tox|"
    r"npm run (?:build|lint|typecheck|check)|yarn (?:build|lint|typecheck)|pnpm (?:build|lint|typecheck)|"
    r"(?:npx )?tsc\b|cargo (?:build|check|clippy)|go (?:build|vet)|make\b|mypy|ruff check|eslint|"
    r"mvn (?:compile|package|verify)|gradle build|dotnet build|python3? -m (?:mypy|ruff|compileall))\b"
)


# Without judgment, blame the most recent action that *looks* destructive: after damage, agents
# usually run several investigation commands, and "latest action" would blame those instead.
_DESTRUCTIVE_ACTION = re.compile(
    r"(?:^|[\s;&|(])(?:rm|rmdir|shred|unlink|truncate|mkfs\S*|dd)\s"
    r"|\b(?:drop|delete|truncate)\b"
    r"|--force\b|\bpush\s+-f\b|reset\s+--hard|\bclean\s+-\w*f"
    r"|(?:^|\s)mv\s|(?:^|\s)\d?>(?![>&])\s*(?!/dev/null)\S"
    r"|^Delete:", re.I)


_PLACEHOLDER = re.compile(r"<[A-Z]+>")  # <TS>, <TMP>, ... from normalization: not redirects


def looks_destructive(normalized: str) -> bool:
    from flinch.innate import executable_text

    return bool(_DESTRUCTIVE_ACTION.search(executable_text(_PLACEHOLDER.sub("X", normalized))))


def is_unsafe_recovery(step: str) -> bool:
    """A cleanup that can itself be the damage. Never store it as the accepted fix."""
    from flinch.innate import strong_rule

    return looks_destructive(step) or strong_rule(step) is not None


_WORD = re.compile(r"[a-z][a-z0-9_-]{2,}")
_STOP = {"you", "the", "and", "all", "that", "this", "just", "deleted", "removed", "wiped", "lost", "broke",
         "database", "files", "folder", "everything", "my", "our", "your", "are", "was", "were", "now", "gone"}


def _mentions(message: str, normalized: str) -> bool:
    words = {w for w in _WORD.findall(message.lower()) if w not in _STOP}
    action = normalized.lower()
    return any(w in action or (len(w) > 4 and w[:4] in action) for w in words)


def pick_culprit(actions: list["Action"], message: str = "", danger: Score | None = None) -> "Action":
    """Most recent destructive action the message points at, else most recent destructive, else latest."""
    def destructive(a: "Action") -> bool:
        if looks_destructive(a.normalized):
            return True
        score = danger(a.normalized) if danger else None
        return score is not None and score >= DANGER_FOR_BLAME

    hits = [a for a in actions if destructive(a)]
    named = [a for a in hits if message and _mentions(message, a.normalized)]
    return (named or hits or actions)[-1]


@dataclass(frozen=True)
class PainFinding:
    normalized: str
    reason: str
    severity: float
    source: str  # user_report
    attribution: str  # fallback


def looks_like_damage_report(text: str) -> bool:
    return bool(_REPORT.search(text))


def is_test_command(normalized: str) -> bool:
    return bool(_TEST_CMD.search(normalized))


class PainDetector:
    """Offline damage detection. `report` scores a user message, `danger` an action (None = no model)."""

    def __init__(self, recent: RecentActions, report: Score | None = None, danger: Score | None = None,
                 report_threshold: float = 0.9) -> None:
        self._recent = recent
        self._report = report
        self._danger = danger
        self._threshold = report_threshold
        self._tests: dict[tuple[str, str], bool] = {}
        self._lock = threading.Lock()

    def _candidates(self, session_id: str) -> list[Action]:
        return self._recent.for_session(session_id) or self._recent.for_session_any()

    def is_report(self, message: str) -> bool:
        if looks_like_damage_report(message):
            return True
        score = self._report(message) if self._report else None
        return score is not None and score >= self._threshold

    def from_prompt(self, session_id: str, prompt: str) -> PainFinding | None:
        actions = self._candidates(session_id)
        message = redact(prompt)[:2000]
        if not actions or not self.is_report(message):
            return None
        culprit = pick_culprit(actions, message, self._danger)
        severity = 1.0 if _DESTRUCTIVE_WORDS.search(message) else 0.75
        return PainFinding(culprit.normalized, f"user reported: {message.strip()[:MAX_REASON]}", severity,
                           "user_report", "fallback")

    def test_result(self, session_id: str, normalized: str, passed: bool) -> str | None:
        """A check (test/build/lint/typecheck) that passed before and fails now: which edits came in between.

        Returned as a lesson for the agent, never as a scar: blocking writes to the file that needs
        fixing would stop the fix.
        """
        key = (session_id, normalized)
        with self._lock:
            previously = self._tests.get(key)
            self._tests = {**self._tests, key: passed}
        if passed or previously is not True:
            return None
        edits = [a for a in self._recent.for_session(session_id) if a.tool in ("Write", "Edit")
                 or a.normalized.startswith(("Write:", "Edit:"))]
        if not edits:
            return None
        changed = ", ".join(a.normalized.split(":", 1)[-1] for a in edits[-3:])
        return f"`{normalized}` passed before in this session and fails now, after edits to {changed}."
