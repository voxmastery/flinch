"""Ring buffer of recently executed mutating actions, for pain attribution (SPEC §6)."""

import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from flinch.jsonfile import SCHEMA_VERSION, file_lock, read_versioned, write_json_atomic

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
        with file_lock(path):
            self._items = self._read()

    def _read(self) -> tuple[Action, ...]:
        raw = read_versioned(self._path, "recent")
        if isinstance(raw, list):
            rows = raw
        elif isinstance(raw, dict) and isinstance(raw.get("actions"), list):
            rows = raw["actions"]
        else:
            rows = []
        items = []
        for row in rows:
            if isinstance(row, dict) and "normalized" in row:
                items.append(Action(**row))
        return tuple(items)

    def _write(self) -> None:
        write_json_atomic(self._path, {"schema_version": SCHEMA_VERSION,
                                       "actions": [asdict(a) for a in self._items]})

    def add(self, **fields) -> Action:
        action = Action(ts=time.time(), **fields)
        with self._lock:
            with file_lock(self._path):
                self._items = (*self._read(), action)[-TOTAL:]
                self._write()
        return action

    def for_session(self, session_id: str) -> list[Action]:
        return [a for a in self._items if a.session_id == session_id][-PER_SESSION:]

    def for_session_any(self) -> list[Action]:
        return list(self._items[-PER_SESSION:])

    def latest(self, session_id: str | None = None) -> Action | None:
        items = self.for_session(session_id) if session_id else self._items
        return items[-1] if items else None
