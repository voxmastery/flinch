"""Synthesize the original Flinch promo soundtrack (numpy only, no samples).

Reads ../src/timeline.json so every sound lands on the same frame as the picture.
Writes ../public/soundtrack.wav (stereo, 48 kHz, 16-bit).
"""
from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

SR = 48_000
HERE = Path(__file__).resolve().parent
TIMELINE = json.loads((HERE.parent / "src" / "timeline.json").read_text())
FPS = TIMELINE["fps"]
TOTAL_S = TIMELINE["total"] / FPS
N = int(TOTAL_S * SR)
T = np.arange(N) / SR
RNG = np.random.default_rng(7331)


def cue_s(scene: str, name: str) -> float:
    sc = TIMELINE["scenes"][scene]
    return (sc["from"] + sc["cues"][name]) / FPS


def scene_s(scene: str) -> tuple[float, float]:
    sc = TIMELINE["scenes"][scene]
    return sc["from"] / FPS, (sc["from"] + sc["dur"]) / FPS


def midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def env_curve(points: list[tuple[float, float]]) -> np.ndarray:
    """Piecewise-linear envelope over the whole track, smoothed."""
    xs, ys = zip(*points)
    return np.interp(T, xs, ys)


def place(buf: np.ndarray, sig: np.ndarray, at_s: float, pan: float = 0.0, gain: float = 1.0) -> None:
    """Mix a mono signal into the stereo buffer at a time, constant-power pan."""
    i = int(at_s * SR)
    if i >= N:
        return
    sig = sig[: N - i] * gain
    ang = (pan + 1) * np.pi / 4
    buf[0, i:i + len(sig)] += sig * np.cos(ang)
    buf[1, i:i + len(sig)] += sig * np.sin(ang)


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    """Zero-phase FFT low-pass with a soft roll-off (fine for short one-shots)."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(spec, len(x))


# ---------------------------------------------------------------- pad bed
def pad() -> np.ndarray:
    """Detuned additive saw-like voices; brightness and chord follow the story."""
    out = np.zeros((2, N))
    heal = cue_s("charge", "heal")
    minor = [38, 45, 50, 53, 57]           # D minor colour (D2 A2 D3 F3 A3)
    major = [38, 45, 50, 54, 57, 62]       # D major resolve (F# instead of F)
    ask = cue_s("danger", "ask")
    e0, e1 = scene_s("errors")
    c0, _ = scene_s("charge")
    close0, _ = scene_s("close")
    word = cue_s("close", "wordmark")
    bright = env_curve([(0, 0.15), (5, 0.25), (14, 0.45), (21, 0.35), (30, 0.5), (40, 0.4),
                        (ask, 0.75), (e0 + 0.5, 0.35), (e1 - 0.2, 0.45), (c0, 0.3), (heal, 0.4),
                        (close0 + 2, 0.55), (word, 0.7), (TOTAL_S, 0.4)])
    level = env_curve([(0, 0.0), (3, 0.5), (5, 0.6), (21, 0.7), (40, 0.75), (ask, 0.9), (e0 + 0.5, 0.6),
                       (e1, 0.62), (c0 + 0.3, 0.55), (heal, 0.7), (close0, 0.8), (word, 1.0), (word + 4, 0.7),
                       (TOTAL_S, 0.0)])
    swell = 0.85 + 0.15 * np.sin(2 * np.pi * T / 9.0)
    xfade = smoothstep((T - heal) / 2.5)
    for chord, weight in ((minor, 1 - xfade), (major, xfade)):
        for k, note in enumerate(chord):
            f0 = midi(note)
            for ch, det in ((0, -0.07), (1, 0.07)):
                f = f0 * 2 ** (det / 12)
                phase = RNG.uniform(0, 2 * np.pi)
                voice = np.zeros(N)
                for h in range(1, 9):
                    amp = (1 / h) * np.exp(-(h - 1) * (1.2 - bright))
                    voice += amp * np.sin(2 * np.pi * f * h * T + phase * h)
                out[ch] += voice * weight * (0.9 if k == 0 else 0.55)
    return out * level * swell * 0.05


# ---------------------------------------------------------------- one-shots
def sub_impact(dur: float = 2.2) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    freq = 38 + 50 * np.exp(-t * 9)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 2.2)
    thump = lowpass(RNG.standard_normal(len(t)) * np.exp(-t * 30), 180)
    return body * 0.9 + thump * 0.5


def click() -> np.ndarray:
    n = int(0.018 * SR)
    t = np.arange(n) / SR
    noise = RNG.standard_normal(n) * np.exp(-t * 420)
    tone = np.sin(2 * np.pi * RNG.uniform(1800, 2600) * t) * np.exp(-t * 600)
    return lowpass(noise, 5000) * 0.6 + tone * 0.25


def glitch_stab(dur: float = 0.32) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    square = np.sign(np.sin(2 * np.pi * 220 * t * (1 + 0.5 * np.sin(2 * np.pi * 31 * t))))
    crushed = np.round(square * 0.6 + RNG.standard_normal(len(t)) * 0.4, 1)
    gate = (np.floor(t * 40) % 3 != 1).astype(float)
    return lowpass(crushed * gate, 6000) * np.exp(-t * 11)


def low_boom(dur: float = 1.6) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    freq = 50 + 30 * np.exp(-t * 12)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 3.0)


def riser(dur: float) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    x = t / dur
    freq = 90 * 2 ** (x * 3)
    tone = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    noise = lowpass(RNG.standard_normal(len(t)), 2500)
    env = x ** 2.2
    return (tone * 0.5 + noise * 0.35) * env


def chime(note: float, dur: float = 3.0) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    f = midi(note)
    s = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * d)
            for r, a, d in ((1, 1.0, 1.4), (2.76, 0.4, 2.6), (5.4, 0.18, 4.0)))
    return s * np.minimum(1, t / 0.004)


def warm_chord(notes: list[int], dur: float = 5.0) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    env = smoothstep(t / 0.9) * np.exp(-np.maximum(0, t - 1.2) * 0.7)
    s = sum(np.sin(2 * np.pi * midi(n) * t) + 0.3 * np.sin(2 * np.pi * midi(n) * 2 * t) for n in notes)
    return s * env / len(notes)


def error_blip() -> np.ndarray:
    t = np.arange(int(0.35 * SR)) / SR
    freq = np.where(t < 0.09, 330.0, 247.0)
    tone = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    return lowpass(tone, 2200) * np.exp(-t * 7) * np.minimum(1, t / 0.005)


def soft_tick() -> np.ndarray:
    t = np.arange(int(0.25 * SR)) / SR
    return np.sin(2 * np.pi * 880 * t) * np.exp(-t * 18)


# ---------------------------------------------------------------- arrange
def arrange() -> np.ndarray:
    mix = pad()
    cpf = TIMELINE["charsPerFrame"]
    for item in TIMELINE["typing"]:
        start = cue_s(item["scene"], item["cue"])
        for c in range(item["chars"]):
            at = start + (c + 1) / cpf / FPS
            place(mix, click(), at, pan=RNG.uniform(-0.3, 0.3), gain=RNG.uniform(0.07, 0.11))

    delete = cue_s("incident", "delete")
    place(mix, sub_impact(), delete, gain=0.55)
    place(mix, glitch_stab(0.18), delete, gain=0.12)
    place(mix, low_boom(), cue_s("report", "hurt"), gain=0.25)

    for scene, name in (("flinch", "flinch"), ("general", "flinchA")):
        at = cue_s(scene, name)
        place(mix, glitch_stab(), at, pan=-0.2, gain=0.2)
        place(mix, glitch_stab(), at + 0.02, pan=0.2, gain=0.2)
        place(mix, low_boom(), at, gain=0.45)

    for scene, name in (("general", "askB"), ("danger", "ask"), ("charge", "yes")):
        place(mix, soft_tick(), cue_s(scene, name), gain=0.06)

    d0, _ = scene_s("danger")
    ask = cue_s("danger", "ask")
    rise_from = d0 - 1.5
    place(mix, riser(ask - rise_from), rise_from, gain=0.16)

    place(mix, error_blip(), cue_s("errors", "error"), gain=0.16)
    place(mix, soft_tick(), cue_s("errors", "ok"), gain=0.05)
    place(mix, chime(79, 2.5), cue_s("errors", "stored"), pan=0.2, gain=0.09)
    ok2 = cue_s("errors", "ok2")
    place(mix, chime(86, 3.0), ok2, pan=-0.15, gain=0.12)
    place(mix, chime(90, 3.0), ok2 + 0.12, pan=0.15, gain=0.08)
    place(mix, chime(93, 3.0), ok2 + 0.24, gain=0.06)

    heal = cue_s("charge", "heal")
    place(mix, warm_chord([62, 66, 69, 74]), heal, gain=0.22)
    place(mix, chime(86), heal + 0.05, pan=0.25, gain=0.12)
    place(mix, chime(93), heal + 0.35, pan=-0.25, gain=0.07)

    word = cue_s("close", "wordmark")
    place(mix, riser(1.6) * 0.6, word - 1.6, gain=0.1)
    place(mix, warm_chord([50, 57, 62, 66, 69], 6.0), word, gain=0.28)
    place(mix, chime(81, 4.0), word + 0.02, gain=0.1)
    return mix


def master(mix: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    fade = np.minimum(1, T / 1.5) * np.minimum(1, (TOTAL_S - T) / 2.5)
    mix = mix * fade
    rms = np.sqrt(np.mean(mix ** 2))
    target_rms = 10 ** (-14 / 20)          # RMS proxy; measures about -14 LUFS on this material
    mix = mix * (target_rms / rms)
    knee = 10 ** (-3 / 20)
    over = np.abs(mix) > knee
    mix[over] = np.sign(mix[over]) * (knee + (1 - knee) * np.tanh((np.abs(mix[over]) - knee) / (1 - knee)))
    ceiling = 10 ** (-2.5 / 20)  # headroom for AAC encoding overshoot
    peak = np.max(np.abs(mix))
    if peak > ceiling:
        mix *= ceiling / peak
    stats = {
        "rms_dbfs": 20 * np.log10(np.sqrt(np.mean(mix ** 2))),
        "peak_dbfs": 20 * np.log10(np.max(np.abs(mix))),
    }
    return mix, stats


def write_wav(path: Path, mix: np.ndarray) -> None:
    pcm = (np.clip(mix.T, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    out = HERE.parent / "public" / "soundtrack.wav"
    final, stats = master(arrange())
    write_wav(out, final)
    print(f"wrote {out} ({TOTAL_S:.1f}s) rms {stats['rms_dbfs']:.1f} dBFS peak {stats['peak_dbfs']:.1f} dBFS")
