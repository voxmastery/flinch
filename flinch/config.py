"""Paths and runtime settings. Thresholds live here and in .flinch/config.toml, never in prompts."""

import logging
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("flinch")

HOST = "127.0.0.1"
PORT = 7331
HOOK_TIMEOUT_S = 5

DEFAULT_CONFIG_TOML = """\
[thresholds]
flinch = 0.55   # avoid >= flinch  -> deny
wary = 0.25     # avoid >= wary    -> ask the user
danger = 0.9    # built-in danger sense: ask before never-seen actions scoring above this
"""


@dataclass(frozen=True)
class Paths:
    home: Path


@dataclass(frozen=True)
class Config:
    flinch_threshold: float = 0.55
    wary_threshold: float = 0.25
    danger_threshold: float = 0.9


def flinch_home(project: Path | None = None) -> Path:
    """State dir: $FLINCH_HOME, else <project or cwd>/.flinch."""
    env = os.environ.get("FLINCH_HOME")
    if env:
        return Path(env)
    return (project or Path.cwd()) / ".flinch"


def paths(project: Path | None = None) -> Paths:
    return Paths(flinch_home(project))


def load_config(home: Path) -> Config:
    path = home / "config.toml"
    try:
        raw = tomllib.loads(path.read_text()) if path.exists() else {}
    except (OSError, tomllib.TOMLDecodeError):
        log.exception("invalid %s; using defaults", path)
        raw = {}
    t, d = raw.get("thresholds", {}), Config()
    try:
        cfg = Config(
            flinch_threshold=float(t.get("flinch", d.flinch_threshold)),
            wary_threshold=float(t.get("wary", d.wary_threshold)),
            danger_threshold=float(t.get("danger", d.danger_threshold)),
        )
    except (TypeError, ValueError):
        log.error("invalid thresholds in %s; using defaults", path)
        return Config()
    if not (0 < cfg.wary_threshold < cfg.flinch_threshold < cfg.danger_threshold <= 1):
        log.error("thresholds must satisfy wary < flinch < danger; using defaults (%s)", path)
        return Config()
    return cfg
