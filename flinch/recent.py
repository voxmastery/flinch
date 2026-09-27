"""Ring buffer of recently executed mutating actions, for pain attribution (SPEC §6)."""

import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from flinch.jsonfile import read_json, write_json_atomic

PER_SESSION = 20
TOTAL = 200


@dataclass(frozen=True)
class Action:
    session_id: str
    tool_use_id: str | None
    tool: str
    normalized: str
    fingerprint: str
    failed: bool
    ts: float


class RecentActions:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        raw = read_json(path, [])
        self._items: tuple[Action, ...] = tuple(Action(**r) for r in raw) if isinstance(raw, list) else ()

    def add(self, **fields) -> Action:
        action = Action(ts=time.time(), **fields)
        with self._lock:
            self._items = (*self._items, action)[-TOTAL:]
            write_json_atomic(self._path, [asdict(a) for a in self._items])
        return action

    def for_session(self, session_id: str) -> list[Action]:
        return [a for a in self._items if a.session_id == session_id][-PER_SESSION:]

    def for_session_any(self) -> list[Action]:
        return list(self._items[-PER_SESSION:])

    def latest(self, session_id: str | None = None) -> Action | None:
        items = self.for_session(session_id) if session_id else self._items
        return items[-1] if items else None
