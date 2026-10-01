"""Fix-spiral identity: same error across command variants, and edit hashes.

An open failure is the error signature plus the command family (`pytest -q` and
`pytest tests/x.py` share `pytest`). Edits do not clear it. A different signature
on the next run of that family does.
"""

import hashlib

_PY = {"python", "python3", "python3.11", "python3.12", "python3.13"}
_JS = {"npm", "pnpm", "yarn"}


def command_family(core: str) -> str:
    """Stable family so flag and path variants of one check share a spiral."""
    parts = core.split()
    if not parts:
        return core
    head, rest = parts[0], parts[1:]
    if head in _PY and len(rest) >= 2 and rest[0] == "-m":
        head, rest = rest[1], rest[2:]
    if head in _JS and rest:
        sub = rest[1] if rest[0] == "run" and len(rest) >= 2 else rest[0]
        return f"{head} {sub}"
    return head


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def proposed_hash(tool_name: str, tool_input: dict) -> str | None:
    if tool_name == "Write":
        return _sha(str(tool_input.get("content", "")))
    if tool_name == "Edit":
        return _sha(str(tool_input.get("new_string", "")))
    return None


def stored_hashes(tool_name: str, tool_input: dict) -> list[str]:
    """Hashes to remember after the edit runs. The old bytes count, so A→B→A is visible."""
    if tool_name == "Write":
        return [_sha(str(tool_input.get("content", "")))]
    if tool_name == "Edit":
        return [_sha(str(tool_input.get("old_string", ""))), _sha(str(tool_input.get("new_string", "")))]
    return []


def edit_path(normalized: str) -> str | None:
    for prefix in ("Write:", "Edit:"):
        if normalized.startswith(prefix):
            return normalized[len(prefix):]
    return None


def is_revert(proposed: str | None, hashes: list[str]) -> bool:
    """True when the new bytes match an earlier state, not the file's latest hash."""
    if not proposed or len(hashes) < 2:
        return False
    return proposed in hashes[:-1] and proposed != hashes[-1]
