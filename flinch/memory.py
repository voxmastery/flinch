"""Pain memories (SPEC §7). The daemon is the only writer: the store holds an exclusive lock."""

import gc
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from flinch.circuit import TextEmbedder
from flinch.episode import PainEpisode, embed_text, episode_content, measure_cost, parse_episode, rank_episodes

log = logging.getLogger("flinch")

CONTEXT = "flinch.pain"
URI_PREFIX = "flinch://pain/"


class MemoryWriteError(RuntimeError):
    """The pain episode was not stored. Callers must not record a scar without it."""


@dataclass(frozen=True)
class Recall:
    pain_id: str
    content: str
    activation: float


def _gate_rejection(report) -> str | None:
    data = report
    if isinstance(report, str):
        text = report.strip()
        if not text.startswith("{"):
            return None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
    if isinstance(data, dict):
        if data.get("gate_rejected"):
            return str(data.get("gate_reason") or "gate rejected the pain episode")
        return None
    if getattr(data, "gate_rejected", False):
        return str(getattr(data, "gate_reason", None) or "gate rejected the pain episode")
    return None


class Memory:
    def __init__(self, path: Path, embedder: TextEmbedder) -> None:
        import fluctlightdb

        path.mkdir(parents=True, exist_ok=True)
        self._embedder = embedder
        self._by_id: dict[str, PainEpisode] = {}
        # retain_days=None: pain must not silently expire; the circuit owns fading.
        self._brain = fluctlightdb.connect_embedded(str(path), retain_days=None)

    def _vector(self, text: str) -> list[float]:
        return [float(x) for x in self._embedder.embed(text)]

    def cache(self, episode: PainEpisode) -> None:
        self._by_id[episode.pain_id] = episode

    def cached(self, pain_id: str) -> PainEpisode | None:
        return self._by_id.get(pain_id)

    def remember_episode(self, episode: PainEpisode, provenance: str) -> None:
        """Store the episode. Raises MemoryWriteError if the write does not land."""
        if self._brain is None:
            raise MemoryWriteError(f"pain episode {episode.pain_id} was not stored: memory is closed")
        try:
            report = self._brain.experience(
                content=episode_content(episode), context=CONTEXT, salience=float(episode.cost),
                outcome="damage", verified=True, provenance_kind=provenance,
                source_uri=f"{URI_PREFIX}{episode.pain_id}",
                semantic_vector=self._vector(embed_text(episode.action, episode.reason)),
            )
            rejected = _gate_rejection(report)
            if rejected:
                raise MemoryWriteError(f"pain episode {episode.pain_id} was not stored: {rejected}")
            self._brain.checkpoint()
        except MemoryWriteError:
            log.exception("memory: rejected pain %s", episode.pain_id)
            raise
        except Exception as exc:
            log.exception("memory: could not store pain %s", episode.pain_id)
            raise MemoryWriteError(f"pain episode {episode.pain_id} was not stored: {exc}") from exc
        self._by_id[episode.pain_id] = episode

    def remember_pain(self, normalized: str, reason: str, severity: float, pain_id: str,
                      provenance: str) -> None:
        cost, note = measure_cost(severity, normalized)
        episode = PainEpisode(
            pain_id=pain_id, project="", session="", task="", action=normalized, reason=reason,
            error="", cost=cost, cost_note=note, attempts=1, trace=(normalized,), accepted_fix=(),
            created_at="", source="", severity=float(severity),
        )
        self.remember_episode(episode, provenance)

    def recall(self, cue: str, limit: int) -> list[Recall]:
        """Fail-soft: a down store returns nothing so a recall miss cannot wedge the agent."""
        if self._brain is None:
            return []
        try:
            result = self._brain.activate(cue=cue, semantic_vector=self._vector(cue), limit=limit)
        except Exception:
            log.exception("memory: recall failed")
            return []
        if not isinstance(result, dict):
            return []
        out = []
        for r in result.get("recalls", []):
            episode = r.get("episode") or {}
            uri = ((episode.get("provenance") or {}).get("source_uri") or "")
            if episode.get("context") == CONTEXT and uri.startswith(URI_PREFIX):
                content = episode.get("content", "")
                pain_id = uri[len(URI_PREFIX):]
                parsed = parse_episode(content)
                if parsed is not None:
                    self._by_id[parsed.pain_id] = parsed
                out.append(Recall(pain_id, content, float(r.get("activation", 0))))
        return out

    def recall_ranked(self, cue: str, cap: int) -> list[tuple[float, PainEpisode]]:
        recalls = self.recall(cue, max(cap * 4, cap))
        items = []
        for hit in recalls:
            episode = self._by_id.get(hit.pain_id) or parse_episode(hit.content)
            if episode is not None:
                items.append((hit.activation, episode))
        return rank_episodes(items, cap)

    def close(self) -> None:
        # No close() in the SDK: dropping the last reference releases the lock.
        self._brain = None
        gc.collect()
