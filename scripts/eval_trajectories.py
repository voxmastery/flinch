#!/usr/bin/env python3
"""Score the seven pain trajectories with the fake embedder. Deterministic. No network."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flinch.trajectories import run_all  # noqa: E402
from tests.conftest import FakeEmbedder  # noqa: E402


def main() -> int:
    rows = run_all(FakeEmbedder(), Path(tempfile.mkdtemp()))
    print(f"{'#':>2}  {'trajectory':<24} {'retry':>5} {'destroy':>7} {'warned':>6} "
          f"{'false':>5} {'tokens':>6}  result")
    for row in rows:
        print(f"{row.number:>2}  {row.name:<24} {row.retries_after_first_failure:>5} "
              f"{row.destructive_after_failure:>7} {str(row.warned_before_repeat):>6} "
              f"{row.legit_edit_false_blocks:>5} {row.tokens:>6}  "
              f"{'pass' if row.passed else 'fail'}  {row.detail}")
    failed = [row.number for row in rows if not row.passed]
    print(f"{len(rows) - len(failed)}/{len(rows)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
