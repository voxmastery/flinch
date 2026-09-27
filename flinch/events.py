"""Fan-out of engine events to SSE subscribers. Publish is thread-safe."""

import asyncio
import json
import threading
from typing import Any

MAX_QUEUE = 256


class EventBus:
    def __init__(self) -> None:
        self._subs: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(MAX_QUEUE)
        with self._lock:
            self._subs.add((asyncio.get_running_loop(), q))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs = {s for s in self._subs if s[1] is not q}

    def publish(self, kind: str, data: dict[str, Any]) -> None:
        message = f"event: {kind}\ndata: {json.dumps(data, default=str)}\n\n"
        with self._lock:
            subs = list(self._subs)
        for loop, q in subs:
            try:
                loop.call_soon_threadsafe(_offer, q, message)
            except RuntimeError:  # loop closed
                self.unsubscribe(q)


def _offer(q: asyncio.Queue, message: str) -> None:
    if q.full():  # slow client: drop oldest rather than block the engine
        q.get_nowait()
    q.put_nowait(message)
