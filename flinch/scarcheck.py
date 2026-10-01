"""Fail-closed scar check (SPEC §8). Runs as a command hook on every tool call.

Scars hold even when the daemon is down, and so do the high-precision danger rules.
Stdlib only. Exit 2 blocks the tool call. A present but unreadable scars.json blocks too,
with a loud line, instead of failing open. A missing file means there is nothing to enforce.
"""

import json
import os
import sys
from pathlib import Path


def _home_and_root(argv: list[str], body: dict) -> tuple[str, str]:
    if argv[:1] == ["--home"] and len(argv) > 1:
        home = argv[1]
        return home, os.path.dirname(os.path.abspath(home))
    from flinch.locate import project_root, state_dir

    root = project_root(body["cwd"])
    return str(state_dir(root)), str(root)


def load_scars(path: Path) -> tuple[dict | None, str | None]:
    """(records, None) when the file is usable. Missing is ({}, None).

    A present file that cannot be read, or is the wrong shape, returns (None, problem).
    """
    if not path.exists():
        return {}, None
    from flinch.jsonfile import SCHEMA_VERSION, file_lock

    try:
        with file_lock(path, exclusive=False):
            raw = json.loads(path.read_text())
    except OSError:
        return None, "present but unreadable"
    except ValueError:
        return None, "not valid JSON"
    if not isinstance(raw, dict):
        return None, "the wrong shape"
    try:
        version = int(raw.get("schema_version", 1))
    except (TypeError, ValueError):
        return None, "the wrong shape"
    if version > SCHEMA_VERSION:
        return None, "from a newer Flinch"
    if "scars" in raw:
        body = raw.get("scars")
        if not isinstance(body, dict):
            return None, "the wrong shape"
    else:
        body = {k: v for k, v in raw.items() if k != "schema_version"}
    return body, None


def _scar_reason(record: dict) -> str | None:
    from flinch.messages import scar_reason, state_block_reason

    if not isinstance(record, dict) or not record.get("normalized") or not record.get("reason"):
        return state_block_reason("unreadable for a known scar")
    return scar_reason(record["normalized"], record["reason"], str(record.get("pain_id") or ""),
                       str(record.get("created_at") or ""))


def reason_for(cwd: str, tool_name: str, tool_input: dict, home: str | None = None,
               root: str | None = None) -> str | None:
    """Deny text for this action, or None when it may run."""
    from flinch.locate import project_root, state_dir
    from flinch.messages import offline_block_reason, state_block_reason
    from flinch.normalize import fingerprint, normalize
    from flinch.rules import strong_rule

    if home is None:
        root_path = project_root(cwd)
        home_path, root_s = state_dir(root_path), str(root_path)
    else:
        home_path = Path(home)
        root_s = root or os.path.dirname(os.path.abspath(home))
    scars, problem = load_scars(Path(home_path) / "scars.json")
    if problem:
        return state_block_reason(problem)
    text = normalize(tool_name, tool_input or {}, root_s)
    record = (scars or {}).get(fingerprint(text))
    if record is not None:
        return _scar_reason(record)
    if tool_name == "Bash":
        why = strong_rule(str((tool_input or {}).get("command") or text))
        if why:
            return offline_block_reason(why)
    return None


def _run(argv: list[str]) -> int:
    body = json.load(sys.stdin)
    home, root = _home_and_root(argv, body)
    reason = reason_for(body.get("cwd") or root, body.get("tool_name") or "", body.get("tool_input") or {},
                        home=home, root=root)
    if not reason:
        return 0
    print(reason, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    try:
        return _run(sys.argv[1:] if argv is None else argv)
    except BaseException:  # noqa: BLE001 - an unexpected bug must not wedge the agent
        return 0


if __name__ == "__main__":
    sys.exit(main())
