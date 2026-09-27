"""Fail-closed scar check (SPEC §8). Runs as a command hook on every tool call.

Scars hold even when the daemon is down. Stdlib only. Exit 2 blocks the tool call; any internal
problem exits 0 (never wedge the agent). Kept cheap: projects without scars never pay for
normalization (regex compilation dominates the cost).
"""

import json
import sys


def _load(argv: list[str]) -> tuple[dict, str, dict] | None:
    body = json.load(sys.stdin)
    if argv[:1] == ["--home"] and len(argv) > 1:
        import os

        home = argv[1]
        root = os.path.dirname(os.path.abspath(home))
    else:
        from flinch.locate import project_root, state_dir

        root_path = project_root(body["cwd"])
        home, root = str(state_dir(root_path)), str(root_path)
    try:
        with open(f"{home}/scars.json") as f:
            scars = json.load(f)
    except (OSError, ValueError):
        return None
    return (scars, root, body) if scars else None


def main(argv: list[str] | None = None) -> int:
    try:
        loaded = _load(sys.argv[1:] if argv is None else argv)
        if loaded is None:
            return 0
        scars, root, body = loaded
        from flinch.messages import scar_reason
        from flinch.normalize import fingerprint, normalize

        scar = scars.get(fingerprint(normalize(body["tool_name"], body.get("tool_input") or {}, root)))
        if not scar:
            return 0
        print(scar_reason(scar["normalized"], scar["reason"], scar["pain_id"], scar["created_at"]),
              file=sys.stderr)
        return 2
    except BaseException:  # noqa: BLE001 - must never break the agent
        return 0


if __name__ == "__main__":
    sys.exit(main())
