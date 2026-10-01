"""Temporary lowering of ask/deny thresholds in the area that just hurt.

Inspired by sensitization after injury: the drop is local to the scar's sparse
code, scoped to the task when one was recorded, and it decays. It is not a
project-wide flinch.
"""

import math
import threading
import time
from pathlib import Path

import numpy as np

from flinch.jsonfile import read_json, write_json_atomic

# Two hours. Full strength at the moment of pain, about 5% six hours later.
TAU_S = 2 * 60 * 60
# Share of the scar's active cells a new action must reuse before thresholds drop.
AREA_OVERLAP = 0.35
# How far wary/flinch fall at full strength (0.25 → 0.15, 0.55 → 0.33).
DROP = 0.4


class Sensitization:
    def __init__(self, path: Path, now=time.time) -> None:
        self._path = path
        self._now = now
        self._lock = threading.Lock()
        raw = read_json(path, [])
        self._rows: list[dict] = list(raw) if isinstance(raw, list) else []

    def add(self, pain_id: str, cells: list[int], task: str) -> None:
        row = {"pain_id": pain_id, "cells": [int(c) for c in cells], "task": task, "at": self._now()}
        with self._lock:
            self._rows = [r for r in self._rows if r.get("pain_id") != pain_id] + [row]
            write_json_atomic(self._path, self._rows)

    def strength(self, active: np.ndarray, task: str) -> float:
        """1 right after a matching injury, fading toward 0. Unrelated actions stay at 0."""
        now = self._now()
        best = 0.0
        active_set = set(int(x) for x in active.tolist()) if len(active) else set()
        width = max(1, len(active_set))
        for row in self._rows:
            age = max(0.0, now - float(row.get("at") or now))
            faded = math.exp(-age / TAU_S)
            if faded < 0.05:
                continue
            recorded = row.get("task") or ""
            if recorded and task and recorded != task:
                continue
            cells = set(row.get("cells") or [])
            if not cells or len(active_set & cells) / width < AREA_OVERLAP:
                continue
            best = max(best, faded)
        return best

    def thresholds(self, wary: float, flinch: float, active: np.ndarray, task: str) -> tuple[float, float]:
        strength = self.strength(active, task)
        if strength <= 0:
            return wary, flinch
        factor = 1 - DROP * strength
        return wary * factor, flinch * factor
