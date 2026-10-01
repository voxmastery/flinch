import hashlib
import os

import numpy as np
import pytest


class FakeEmbedder:
    """Deterministic char-trigram hashing embedder: similar strings -> similar vectors. Fast."""

    dim = 384

    def embed(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, np.float32)
        padded = f"  {text}  "
        for i in range(len(padded) - 2):
            h = int.from_bytes(hashlib.md5(padded[i:i + 3].encode()).digest()[:4], "little")
            v[h % self.dim] += 1.0 if (h >> 31) & 1 else -1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_many(self, texts):
        return np.stack([self.embed(t) for t in texts])


@pytest.fixture(autouse=True)
def _isolated_data_home(tmp_path_factory, monkeypatch):
    """Tests never touch the user's real ~/.local/share/flinch (logs, state), but share the model cache."""
    from flinch.locate import data_home

    monkeypatch.setenv("FLINCH_MODEL_CACHE", os.environ.get("FLINCH_MODEL_CACHE") or str(data_home() / "models"))
    monkeypatch.setenv("FLINCH_DATA_HOME", str(tmp_path_factory.mktemp("flinch-data")))
    monkeypatch.setenv("FLINCH_TOKEN", "test-token")



@pytest.fixture
def fake_embedder():
    return FakeEmbedder()


@pytest.fixture(scope="session")
def real_embedder():
    from flinch.embed import Embedder

    return Embedder()
