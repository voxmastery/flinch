"""Text embeddings. Loaded on first use and unloaded when idle, so an idle daemon stays small."""

import gc
import logging
import os
import threading
import time
import warnings

import numpy as np

log = logging.getLogger("flinch")

MODEL = "BAAI/bge-small-en-v1.5"
DIM = 384
THREADS = int(os.environ.get("FLINCH_EMBED_THREADS", "2"))  # stay light next to the IDE
IDLE_UNLOAD_S = float(os.environ.get("FLINCH_EMBED_IDLE_S", "900"))


def _trim_heap() -> None:
    try:
        import ctypes

        ctypes.CDLL("libc.so.6").malloc_trim(0)  # hand freed model memory back to the OS (glibc)
    except (OSError, AttributeError):
        pass


class Embedder:
    def __init__(self, model: str = MODEL) -> None:
        self._name = model
        self._model = None
        self._lock = threading.Lock()  # ONNX session: serialize calls
        self._used = 0.0
        self.dim = DIM

    def _load(self):
        from fastembed import TextEmbedding

        from flinch.locate import data_home

        # fastembed defaults to /tmp, which is wiped on reboot
        cache = os.environ.get("FLINCH_MODEL_CACHE") or str(data_home() / "models")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = TextEmbedding(self._name, cache_dir=cache, threads=THREADS, enable_cpu_mem_arena=False)
        log.info("flinch: embedding model loaded")
        return model

    def embed_many(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            if self._model is None:
                self._model = self._load()
            self._used = time.time()
            return np.asarray(list(self._model.embed(texts)), dtype=np.float32)

    def embed(self, text: str) -> np.ndarray:
        return self.embed_many([text])[0]

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def unload_if_idle(self, idle_s: float = IDLE_UNLOAD_S) -> bool:
        with self._lock:
            if self._model is None or time.time() - self._used < idle_s:
                return False
            self._model = None
        gc.collect()
        _trim_heap()
        log.info("flinch: embedding model unloaded (idle)")
        return True
