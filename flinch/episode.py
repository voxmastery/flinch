"""One causal pain episode, stored inside a FluctlightDB experience.

FluctlightDB's Episode has no columns for cost, trace, or a cause link (see
docs/PAIN_DESIGN.md). The whole record is a readable first line plus JSON in
`content`, addressed by `source_uri` `flinch://pain/{pain_id}`.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone

HINT_TOKEN_BUDGET = 80


def estimate_tokens(text: str) -> int:
    """Rough prompt cost: about four characters per token. Used to keep hints small."""
    return max(1, (len(text) + 3) // 4)


def embed_text(action: str, reason: str) -> str:
    """One vector has to carry both the action and why it hurt."""
    return f"{action}\n{reason}"


def measure_cost(severity: float, action: str, attempts: int = 1, failed: bool = False) -> tuple[float, str]:
    """0..1 cost. Starts at the reported severity and rises with what the run actually did."""
    from flinch.innate import strong_rule
    from flinch.pain import looks_destructive

    cost = float(severity)
    notes = [f"severity {severity:.2f}"]
    if looks_destructive(action) or strong_rule(action):
        cost += 0.15
        notes.append("destructive")
    if failed:
        cost += 0.10
        notes.append("failed")
    extra = max(0, int(attempts) - 1)
    if extra:
        cost += min(0.20, 0.05 * extra)
        notes.append(f"{int(attempts)} attempts")
    cost = round(min(1.0, max(0.0, cost)), 2)
    return cost, ", ".join(notes)


@dataclass(frozen=True)
class PainEpisode:
    pain_id: str
    project: str
    session: str
    task: str
    action: str
    reason: str
    error: str
    cost: float
    cost_note: str
    attempts: int
    trace: tuple[str, ...]
    accepted_fix: tuple[str, ...]
    created_at: str
    source: str
    severity: float

    @staticmethod
    def build(pain_id: str, project: str, session: str, task: str, action: str, reason: str,
              error: str, severity: float, attempts: int, trace: list[str], accepted_fix: list[str],
              source: str, failed: bool = False, created_at: str | None = None) -> "PainEpisode":
        cost, note = measure_cost(severity, action, attempts, failed)
        when = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        return PainEpisode(
            pain_id=pain_id, project=project, session=session or "", task=task, action=action,
            reason=reason, error=error, cost=cost, cost_note=note, attempts=max(1, int(attempts)),
            trace=tuple(trace), accepted_fix=tuple(accepted_fix), created_at=when, source=source,
            severity=float(severity),
        )


def episode_content(episode: PainEpisode) -> str:
    """Human first line (lexical recall still sees the reason) then the record as JSON."""
    payload = {
        "v": 1,
        "pain_id": episode.pain_id,
        "project": episode.project,
        "session": episode.session,
        "task": episode.task,
        "action": episode.action,
        "reason": episode.reason,
        "error": episode.error,
        "cost": episode.cost,
        "cost_note": episode.cost_note,
        "attempts": episode.attempts,
        "trace": list(episode.trace),
        "accepted_fix": list(episode.accepted_fix),
        "created_at": episode.created_at,
        "source": episode.source,
        "severity": episode.severity,
    }
    return f"PAIN: {episode.action} caused {episode.reason}\n{json.dumps(payload, separators=(',', ':'), ensure_ascii=False)}"


def parse_episode(content: str) -> PainEpisode | None:
    start = content.find("{")
    if start < 0:
        return None
    try:
        data = json.loads(content[start:])
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("pain_id"):
        return None
    try:
        return PainEpisode(
            pain_id=str(data["pain_id"]),
            project=str(data.get("project") or ""),
            session=str(data.get("session") or ""),
            task=str(data.get("task") or ""),
            action=str(data.get("action") or ""),
            reason=str(data.get("reason") or ""),
            error=str(data.get("error") or ""),
            cost=float(data.get("cost") or 0),
            cost_note=str(data.get("cost_note") or ""),
            attempts=int(data.get("attempts") or 1),
            trace=tuple(str(x) for x in (data.get("trace") or [])),
            accepted_fix=tuple(str(x) for x in (data.get("accepted_fix") or [])),
            created_at=str(data.get("created_at") or ""),
            source=str(data.get("source") or ""),
            severity=float(data.get("severity") or 0),
        )
    except (TypeError, ValueError):
        return None


def rank_episodes(items: list[tuple[float, PainEpisode]], cap: int) -> list[tuple[float, PainEpisode]]:
    """Relevance, then severity, then recency. One row per pain_id. Hard cap."""
    best: dict[str, tuple[float, PainEpisode]] = {}
    for activation, episode in items:
        prev = best.get(episode.pain_id)
        if prev is None or (activation, episode.severity, episode.created_at) > (
                prev[0], prev[1].severity, prev[1].created_at):
            best[episode.pain_id] = (activation, episode)
    ordered = sorted(best.values(), key=lambda row: (row[0], row[1].severity, row[1].created_at), reverse=True)
    return ordered[:cap]
