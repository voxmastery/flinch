"""Scar tissue: exact-match fingerprints of damaging actions (SPEC §4)."""

import dataclasses
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from flinch.jsonfile import read_json, write_json_atomic
from flinch.normalize import fingerprint

SEVERITIES = (0.25, 0.5, 0.75, 1.0)


@dataclass(frozen=True)
class Scar:
    fingerprint: str
    normalized: str
    reason: str
    severity: float
    created_at: str
    pain_id: str

    def record(self) -> dict:
        d = dataclasses.asdict(self)
        del d["fingerprint"]
        return d


class ScarStore:
    """Persists {fingerprint: {normalized, reason, severity, created_at, pain_id}}."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        raw = read_json(path, {})
        self._scars: dict[str, Scar] = {
            fp: Scar(fingerprint=fp, **rec) for fp, rec in (raw.items() if isinstance(raw, dict) else [])
        }

    def _save(self) -> None:
        write_json_atomic(self._path, {fp: s.record() for fp, s in self._scars.items()})

    def get(self, fp: str) -> Scar | None:
        return self._scars.get(fp)

    def all(self) -> list[Scar]:
        return sorted(self._scars.values(), key=lambda s: s.created_at, reverse=True)

    def add(self, normalized: str, reason: str, severity: float) -> Scar:
        fp = fingerprint(normalized)
        with self._lock:
            prior = self._scars.get(fp)
            scar = Scar(
                fingerprint=fp,
                normalized=normalized,
                reason=reason,
                severity=max(severity, prior.severity) if prior else severity,
                created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                pain_id=prior.pain_id if prior else f"p_{uuid.uuid4().hex[:8]}",
            )
            self._scars = {**self._scars, fp: scar}
            self._save()
        return scar

    def remove(self, ident: str) -> Scar | None:
        """Remove by pain_id or a fingerprint prefix (>= 6 chars, unambiguous)."""
        with self._lock:
            matches = [s for s in self._scars.values()
                       if s.pain_id == ident or (len(ident) >= 6 and s.fingerprint.startswith(ident))]
            if len(matches) != 1:
                return None
            scar = matches[0]
            self._scars = {fp: s for fp, s in self._scars.items() if fp != scar.fingerprint}
            self._save()
        return scar
