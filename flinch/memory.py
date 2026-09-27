"""Pain memories (SPEC §7). The daemon is the only writer: the store holds an exclusive lock."""

import gc
import logging
from dataclasses import dataclass
from pathlib import Path

from flinch.circuit import TextEmbedder

log = logging.getLogger("flinch")

CONTEXT = "flinch.pain"
URI_PREFIX = "flinch://pain/"


@dataclass(frozen=True)
class Recall:
    pain_id: str
    content: str
    activation: float


class Memory:
    def __init__(self, path: Path, embedder: TextEmbedder) -> None:
        import fluctlightdb

        path.mkdir(parents=True, exist_ok=True)
        self._embedder = embedder
        # retain_days=None: pain must not silently expire; the circuit owns fading.
        self._brain = fluctlightdb.connect_embedded(str(path), retain_days=None)

    def _vector(self, text: str) -> list[float]:
        return [float(x) for x in self._embedder.embed(text)]

    def remember_pain(self, normalized: str, reason: str, severity: float, pain_id: str,
                      provenance: str) -> None:
        try:
            self._brain.experience(
                content=f"PAIN: {normalized} caused {reason}", context=CONTEXT, salience=severity,
                outcome="damage", verified=True, provenance_kind=provenance,
                source_uri=f"{URI_PREFIX}{pain_id}", semantic_vector=self._vector(normalized),
            )
            self._brain.checkpoint()
        except Exception:
            log.exception("memory: could not store pain %s", pain_id)

    def recall(self, cue: str, limit: int) -> list[Recall]:
        try:
            result = self._brain.activate(cue=cue, semantic_vector=self._vector(cue), limit=limit)
        except Exception:
            log.exception("memory: recall failed")
            return []
        out = []
        for r in result.get("recalls", []):
            episode = r.get("episode") or {}
            uri = ((episode.get("provenance") or {}).get("source_uri") or "")
            if episode.get("context") == CONTEXT and uri.startswith(URI_PREFIX):
                out.append(Recall(uri[len(URI_PREFIX):], episode.get("content", ""), float(r.get("activation", 0))))
        return out

    def close(self) -> None:
        # No close() in the SDK: dropping the last reference releases the lock.
        self._brain = None
        gc.collect()
