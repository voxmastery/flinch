"""Innate readouts: output units trained offline on labeled examples, shipped with Flinch.

Alongside the pain-learned unit, two readouts are pre-trained on the same sparse cell codes
(plus the whitened embedding): "danger" for actions and "report" for user messages. They are
plain logistic units; training lives in scripts/train_innate.py. No network, no keys.
"""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger("flinch")

WEIGHTS = Path(__file__).parent / "innate.npz"
DANGER_THRESHOLD = 0.9  # chosen on held-out tool families (see training report)
REPORT_THRESHOLD = 0.9  # zero false reports on held-out data at this level

from flinch.rules import executable_text, strong_rule

__all__ = ["executable_text", "strong_rule"]


@dataclass(frozen=True)
class Readout:
    w: np.ndarray
    b: float

    def __call__(self, code: np.ndarray, z: np.ndarray) -> float:
        x = float(self.w[: len(self.w) - len(z)][code].sum() + self.w[len(self.w) - len(z):] @ (4.0 * z) + self.b)
        return 1.0 / (1.0 + np.exp(-x))


def fingerprint_of(mu: np.ndarray, inputs: np.ndarray) -> str:
    """Identifies the encoding the weights were trained against (reference whitening + projection)."""
    return hashlib.sha256(np.round(mu, 5).tobytes() + inputs.tobytes()).hexdigest()[:16]


class Innate:
    def __init__(self, danger: Readout | None, report: Readout | None) -> None:
        self.danger = danger
        self.report = report

    @property
    def available(self) -> bool:
        return self.danger is not None

    @classmethod
    def load(cls, encoding_fingerprint: str, path: Path = WEIGHTS) -> "Innate":
        try:
            with np.load(path) as z:
                if str(z["fingerprint"]) != encoding_fingerprint:
                    log.warning("innate weights were trained for a different encoding; using rules only")
                    return cls(None, None)
                return cls(Readout(z["danger_w"], float(z["danger_b"])), Readout(z["report_w"], float(z["report_b"])))
        except (OSError, KeyError, ValueError):
            log.warning("innate weights missing or unreadable; using rules only")
            return cls(None, None)
