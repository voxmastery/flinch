"""Train the innate readouts on flinch/innate_data.py and write flinch/innate.npz.

Also prints held-out results (whole tool families left out) so the shipped thresholds are honest.
Run after changing the data, the embedding model, or the circuit parameters:
    .venv/bin/python scripts/train_innate.py
"""

import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flinch.circuit import Circuit  # noqa: E402
from flinch.embed import Embedder  # noqa: E402
from flinch.innate import DANGER_THRESHOLD, REPORT_THRESHOLD, WEIGHTS, fingerprint_of, strong_rule  # noqa: E402
from flinch.innate_data import DANGEROUS, REPORTS, REQUESTS, SAFE  # noqa: E402
from flinch.pain import looks_like_damage_report  # noqa: E402

L2 = 1.0
ITERS = 600
LR = 0.5


def features(circuit: Circuit, embedder: Embedder, texts: list[str]) -> np.ndarray:
    emb = embedder.embed_many(texts)
    cells = circuit.params.cells
    out = np.zeros((len(texts), cells + emb.shape[1]), np.float32)
    for i, v in enumerate(emb):
        out[i, circuit.encode_vector(v)] = 1.0
        z = (v - circuit._mu) / circuit._sd
        out[i, cells:] = 4.0 * z / np.linalg.norm(z)
    return out


def fit(F: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    w, b = np.zeros(F.shape[1]), 0.0
    weight = np.where(y == 1, (y == 0).sum() / max(1, (y == 1).sum()), 1.0)
    for _ in range(ITERS):
        p = 1 / (1 + np.exp(-(F @ w + b)))
        g = (p - y) * weight
        w -= LR * (F.T @ g / len(y) + L2 * w / len(y))
        b -= LR * g.mean()
    return w, b


def dataset(pos: dict, neg: dict) -> tuple[list[str], np.ndarray, np.ndarray]:
    texts, labels, fams = [], [], []
    for fam in sorted(set(pos) | set(neg)):
        for t in pos.get(fam, []):
            texts.append(t); labels.append(1); fams.append(fam)
        for t in neg.get(fam, []):
            texts.append(t); labels.append(0); fams.append(fam)
    return texts, np.array(labels), np.array(fams)


def held_out_report(name, F, y, fams, rule_hits, threshold) -> None:
    p = np.zeros(len(y))
    for fam in sorted(set(fams)):
        te = fams == fam
        if len(set(y[~te])) < 2:
            continue
        w, b = fit(F[~te], y[~te])
        p[te] = 1 / (1 + np.exp(-(F[te] @ w + b)))
    pred = rule_hits | (p >= threshold)
    recall = (pred & (y == 1)).sum() / (y == 1).sum()
    false_pos = (pred & (y == 0)).sum() / (y == 0).sum()
    print(f"{name}: held-out families, threshold {threshold}: recall {recall:.2f}, false positives {false_pos:.2f}")


def main() -> int:
    embedder = Embedder()
    circuit = Circuit(Path(tempfile.mkdtemp()) / "circuit.npz", embedder)
    out = {"fingerprint": np.array(fingerprint_of(circuit._mu, circuit._inputs))}
    for name, pos, neg, rule, threshold in (
        ("danger", DANGEROUS, SAFE, lambda t: strong_rule(t) is not None, DANGER_THRESHOLD),
        ("report", REPORTS, REQUESTS, looks_like_damage_report, REPORT_THRESHOLD),
    ):
        texts, y, fams = dataset(pos, neg)
        F = features(circuit, embedder, texts)
        held_out_report(name, F, y, fams, np.array([rule(t) for t in texts]), threshold)
        w, b = fit(F, y)
        out[f"{name}_w"], out[f"{name}_b"] = w.astype(np.float32), np.float64(b)
    np.savez(WEIGHTS, **out)
    print(f"wrote {WEIGHTS} ({WEIGHTS.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
