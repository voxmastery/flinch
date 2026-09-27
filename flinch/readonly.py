"""Cheap, conservative guess at whether an action can mutate state.

Used to pick attribution candidates and (later) to skip judgment for read-only tools.
When unsure, say mutating.
"""

import re
import shlex
from typing import Any

_READ_ONLY_TOOLS = {"Read", "Glob", "Grep", "LS", "WebFetch", "WebSearch", "TodoWrite"}
_READ_ONLY_CMDS = {
    "ls", "cat", "head", "tail", "grep", "rg", "egrep", "fgrep", "wc", "echo", "printf", "pwd",
    "which", "type", "whoami", "date", "stat", "file", "du", "df", "tree", "less", "more", "diff",
    "env", "printenv", "true", "false", "test", "[", "sort", "uniq", "cut", "tr", "basename",
    "dirname", "realpath", "readlink", "id", "uname", "hostname", "jq", "column", "nl", "cd",
    "fd", "fdfind", "ag", "ack", "xxd", "od", "hexdump", "md5sum", "sha1sum", "sha256sum", "cksum",
    "strings", "whereis", "locate", "ps", "top", "free", "uptime", "lsof", "ss", "netstat", "env",
}
_READ_ONLY_GIT = {"status", "log", "diff", "show", "rev-parse", "ls-files", "blame", "describe", "shortlog",
                  "ls-tree", "ls-remote", "cat-file", "grep", "rev-list", "reflog", "whatchanged", "count-objects"}
# git subcommands that are read-only only with these flags/args
_GIT_CONDITIONAL = {"remote": ({"-v", "show", "get-url"}, None), "config": ({"--get", "--list", "-l", "--get-all"}, None),
                    "stash": ({"list", "show"}, None), "tag": ({"-l", "--list"}, None), "worktree": ({"list"}, None)}
_SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n]")
_HARMLESS_REDIRECT = re.compile(r"\d?>&\d|\d?>\s*/dev/null")


def _segment_is_read_only(segment: str) -> bool:
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return False
    if not tokens:
        return True
    cmd, args = tokens[0], tokens[1:]
    if cmd == "git":
        sub = next((a for a in args if not a.startswith("-")), "")
        if sub in _GIT_CONDITIONAL:
            allowed, _ = _GIT_CONDITIONAL[sub]
            rest = args[args.index(sub) + 1:]
            return bool(set(rest) & allowed) or (sub in ("tag", "remote") and not rest)
        return sub in _READ_ONLY_GIT or (sub == "branch" and not {"-d", "-D", "-m", "-M"} & set(args))
    if cmd == "find":
        return not {"-delete", "-exec", "-execdir", "-ok"} & set(args)
    if cmd == "sed":
        return not any(a.startswith("-i") or a == "--in-place" for a in args)
    return cmd in _READ_ONLY_CMDS


def is_mutating(tool_name: str, tool_input: dict[str, Any]) -> bool:
    if tool_name in _READ_ONLY_TOOLS:
        return False
    if tool_name != "Bash":
        return True
    command = _HARMLESS_REDIRECT.sub(" ", str(tool_input.get("command", "")))
    if ">" in command:
        return True
    return not all(_segment_is_read_only(seg) for seg in _SEGMENT_SPLIT.split(command))
