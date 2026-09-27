"""One daemon, many projects: routes each hook to its project's engine by `cwd`."""

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from flinch.circuit import TextEmbedder
from flinch.decide import Engine
from flinch.locate import project_root, state_dir

log = logging.getLogger("flinch")

RESOLVE_TTL_S = 60.0
Publish = Callable[[str, dict[str, Any]], None]


class Registry:
    def __init__(self, publish: Publish, embedder: TextEmbedder | None = None,
                 fixed_home: Path | None = None) -> None:
        self._publish = publish
        self._embedder = embedder
        self._fixed_home = fixed_home
        self._engines: dict[str, Engine] = {}
        self._used: dict[str, float] = {}
        self._resolved: dict[str, tuple[float, Path, Path]] = {}
        self._lock = threading.RLock()  # guards dicts only; never held while building an engine
        self._creating: dict[str, threading.Lock] = {}
        self.last_active: str | None = None
        self.last_hook_at = time.time()

    def _shared_embedder(self) -> TextEmbedder:
        with self._lock:
            if self._embedder is None:
                from flinch.embed import Embedder

                self._embedder = Embedder()
            return self._embedder

    def _resolve(self, cwd: str) -> tuple[Path, Path]:
        now = time.time()
        hit = self._resolved.get(cwd)
        if hit and now - hit[0] < RESOLVE_TTL_S:
            return hit[1], hit[2]
        if self._fixed_home:
            root, home = self._fixed_home.parent, self._fixed_home
        else:
            root = project_root(cwd)
            home = state_dir(root)
        self._resolved = {**self._resolved, cwd: (now, root, home)}
        return root, home

    def for_cwd(self, cwd: str) -> Engine:
        root, home = self._resolve(cwd)
        key = str(home)
        engine = self._engines.get(key)
        if engine is None:
            engine = self._create(key, root, home)
        with self._lock:
            self._used[key] = self.last_hook_at = time.time()
            self.last_active = key
        return engine

    def _create(self, key: str, root: Path, home: Path) -> Engine:
        # Per-project lock: a cold start (model load, store open) must not stall other projects,
        # and one project's store must never be opened twice (its lock would block for minutes).
        with self._lock:
            creating = self._creating.setdefault(key, threading.Lock())
        with creating:
            engine = self._engines.get(key)
            if engine is not None:
                return engine
            name = root.name
            engine = Engine(home, embedder=self._shared_embedder(), root=root,
                            emit=lambda kind, data: self._publish(kind, {**data, "project": name}))
            with self._lock:
                self._engines = {**self._engines, key: engine}
            log.info("flinch: loaded project %s (state %s)", root, home)
            return engine

    def active(self) -> Engine | None:
        with self._lock:
            return self._engines.get(self.last_active) if self.last_active else None

    def evict_idle(self, max_idle_s: float) -> None:
        now = time.time()
        with self._lock:
            stale = [k for k, t in self._used.items() if now - t > max_idle_s and k != self.last_active]
            for key in stale:
                self._engines[key].close()
                self._engines = {k: v for k, v in self._engines.items() if k != key}
                self._used.pop(key, None)
                log.info("flinch: unloaded idle project state %s", key)

    def unload_idle_model(self) -> None:
        unload = getattr(self._embedder, "unload_if_idle", None)
        if unload:
            unload()

    def reset(self, cwd: str) -> Path:
        """Forget everything learned for the project at cwd (keeps config.toml)."""
        from flinch.locate import wipe_state

        _, home = self._resolve(cwd)
        key = str(home)
        with self._lock:
            creating = self._creating.setdefault(key, threading.Lock())
        with creating:
            with self._lock:
                engine = self._engines.get(key)
                self._engines = {k: v for k, v in self._engines.items() if k != key}
                self._used.pop(key, None)
                if self.last_active == key:
                    self.last_active = None
            if engine is not None:
                engine.close()  # release the memory store before deleting it
            wipe_state(home)
        log.info("flinch: reset project state %s", home)
        return home

    def close_all(self) -> None:
        with self._lock:
            for engine in self._engines.values():
                engine.close()
            self._engines = {}
