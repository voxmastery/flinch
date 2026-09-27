"""Sparse-coding reflex circuit (SPEC §5).

Actions are embedded, whitened against a reference corpus of everyday commands, and
projected through a fixed sparse binary matrix; the top 5% of cells form the action's code.
One output unit holds a weight per cell. Pain raises the weights of the painful code's cells,
safe use and time lower them. avoid = mean weight over a new action's active cells.
"""

import logging
import math
import os
import tempfile
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

log = logging.getLogger("flinch")

# Everyday actions used to center/whiten embeddings, so codes reflect what is
# distinctive about an action rather than "it's a shell command".
REFERENCE_CORPUS = (
    "ls", "ls -la", "cat README.md", "git status", "git log --oneline", "git diff", "npm install",
    "npm test", "pytest -q", "python main.py", "mkdir build", "cp a.txt b.txt", "mv old new",
    "touch notes.md", "echo hello", "grep -r TODO src", "find . -name '*.py'", "docker ps",
    "make build", "cargo test", "go build ./...", "curl https://example.com", "pip install requests",
    "git add .", "git checkout -b feature", "cd src", "head -20 log.txt", "tail -f app.log",
    "wc -l *.py", "Write:src/app.py", "Edit:README.md", "Write:tests/test_x.py", "Edit:package.json",
    "sqlite3 db.sqlite '.tables'", "chmod +x run.sh", "ps aux", "kill 1234", "tar czf out.tgz dist",
    "unzip file.zip", "node index.js", "yarn build", "rm build.log", "git pull", "git fetch origin",
    "code .", "open index.html", "du -sh .", "df -h", "whoami",
)


CODE_CACHE_SIZE = 4096


class TextEmbedder(Protocol):
    dim: int

    def embed(self, text: str) -> np.ndarray: ...

    def embed_many(self, texts: list[str]) -> np.ndarray: ...


@dataclass(frozen=True)
class CircuitParams:
    cells: int = 4000
    fan_in: int = 12
    active_fraction: float = 0.05
    eta_pain: float = 0.9
    eta_safe: float = 0.05
    tau_days: float = 14.0
    seed: int = 1337

    @property
    def k(self) -> int:
        return int(round(self.cells * self.active_fraction))


class Circuit:
    def __init__(self, path: Path, embedder: TextEmbedder, params: CircuitParams = CircuitParams(),
                 now: Callable[[], float] = time.time) -> None:
        self._path = path
        self._embedder = embedder
        self.params = params
        self._now = now
        self._lock = threading.Lock()
        self._codes: OrderedDict[str, tuple[np.ndarray, np.ndarray]] = OrderedDict()  # fixed per text: cache
        if not self._load():
            self._init_fresh()

    # --- state ---------------------------------------------------------------

    def _init_fresh(self) -> None:
        p = self.params
        rng = np.random.default_rng(p.seed)
        dim = self._embedder.dim
        self._inputs = np.stack([rng.choice(dim, p.fan_in, replace=False) for _ in range(p.cells)]).astype(np.int16)
        ref = self._embedder.embed_many(list(REFERENCE_CORPUS))
        self._mu = ref.mean(0).astype(np.float32)
        self._sd = (ref.std(0) + 1e-3).astype(np.float32)
        self._w = np.zeros(p.cells, np.float32)
        self._last_decay_at = self._now()

    def _load(self) -> bool:
        if not self._path.exists():
            return False
        try:
            with np.load(self._path) as z:
                inputs, mu, sd, w = z["inputs"], z["mu"], z["sd"], z["w"]
                last = float(z["last_decay_at"])
                seed = int(z["seed"])
        except Exception:
            bad = self._path.with_suffix(".corrupt")
            log.exception("circuit state unreadable; moving to %s and starting fresh", bad)
            os.replace(self._path, bad)
            return False
        if inputs.shape != (self.params.cells, self.params.fan_in) or seed != self.params.seed:
            log.warning("circuit state has different parameters; starting fresh")
            return False
        self._inputs, self._mu, self._sd, self._w, self._last_decay_at = inputs, mu, sd, w, last
        return True

    def save(self) -> None:
        with self._lock:
            arrays = dict(inputs=self._inputs, mu=self._mu, sd=self._sd, w=self._w.copy(),
                          last_decay_at=np.float64(self._last_decay_at), seed=np.int64(self.params.seed))
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=".circuit.", suffix=".npz")
        try:
            with os.fdopen(fd, "wb") as f:
                np.savez(f, **arrays)
            os.replace(tmp, self._path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # --- encoding ------------------------------------------------------------

    def whiten(self, vec: np.ndarray) -> np.ndarray:
        x = (vec - self._mu) / self._sd
        norm = float(np.linalg.norm(x))
        return x / norm if norm else x

    def encode_vector(self, vec: np.ndarray) -> np.ndarray:
        h = self.whiten(vec)[self._inputs].sum(axis=1)  # sparse binary projection: each cell sums its inputs
        k = self.params.k
        top = np.argpartition(-h, k)[:k]
        return np.sort(top).astype(np.int32)

    def features(self, text: str) -> tuple[np.ndarray, np.ndarray]:
        """(active cell code, whitened embedding) for a text; both read-only and cached."""
        with self._lock:
            cached = self._codes.get(text)
            if cached is not None:
                self._codes.move_to_end(text)
                return cached
        vec = self._embedder.embed(text)
        code, z = self.encode_vector(vec), self.whiten(vec).astype(np.float32)
        code.setflags(write=False)
        z.setflags(write=False)
        with self._lock:
            self._codes[text] = (code, z)
            while len(self._codes) > CODE_CACHE_SIZE:
                self._codes.popitem(last=False)
        return code, z

    def encode(self, text: str) -> np.ndarray:
        return self.features(text)[0]

    @property
    def encoding_fingerprint(self) -> str:
        from flinch.innate import fingerprint_of

        return fingerprint_of(self._mu, self._inputs)

    # --- plasticity ----------------------------------------------------------

    def _decay_locked(self) -> None:
        now = self._now()
        dt = max(0.0, now - self._last_decay_at)
        if dt > 0:
            self._w *= math.exp(-dt / (self.params.tau_days * 86400))
            self._last_decay_at = now

    def avoid(self, active: np.ndarray) -> float:
        with self._lock:
            self._decay_locked()
            return float(self._w[active].mean()) if len(active) else 0.0

    def punish(self, active: np.ndarray, severity: float) -> None:
        with self._lock:
            self._decay_locked()
            self._w[active] = np.minimum(1.0, self._w[active] + self.params.eta_pain * severity)

    def extinguish(self, active: np.ndarray) -> None:
        with self._lock:
            self._decay_locked()
            self._w[active] *= 1.0 - self.params.eta_safe

    def forgive(self, active: np.ndarray) -> None:
        with self._lock:
            self._w[active] = 0.0

    def weights(self) -> np.ndarray:
        with self._lock:
            self._decay_locked()
            return self._w.copy()
