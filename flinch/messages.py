"""User/agent-facing text. Factual statements only (SPEC §3). Stdlib only: shared with scarcheck."""

from datetime import datetime


def scar_reason(normalized: str, reason: str, pain_id: str, created_at: str) -> str:
    try:
        when = datetime.fromisoformat(created_at).strftime("%d %b %Y")
    except ValueError:
        when = "an earlier session"
    return (f"Flinch blocked this action. On {when}, this exact action (`{normalized}`) "
            f"caused damage: {reason}. It is scarred ({pain_id}) and will not run. "
            f"A different approach is needed, or the user can lift the scar with `flinch forgive {pain_id}`.")


def _pain_ref(scar) -> str:
    if scar is None:
        return "an action that caused damage before"
    return f"`{scar.normalized}`, which caused damage ({scar.reason}; {scar.pain_id})"


def reflex_deny_reason(scar, avoid: float) -> str:
    return (f"Flinch blocked this action by reflex: it closely resembles {_pain_ref(scar)}. "
            f"Resemblance strength {avoid:.2f}. A different approach is needed.")


def reflex_ask_reason(scar, avoid: float) -> str:
    return (f"Flinch: this action resembles {_pain_ref(scar)}. "
            f"Resemblance strength {avoid:.2f}. Confirm only if this is safe.")


def _when(created_at: str) -> str:
    try:
        return datetime.fromisoformat(created_at).strftime("%d %b %Y")
    except ValueError:
        return "an earlier session"


def _lesson(scar) -> str:
    return f"- On {_when(scar.created_at)}, `{scar.normalized}` caused damage: {scar.reason}."


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def cost_line(cost: float, fix: str | None = None) -> str:
    if fix:
        return f"Cost {cost:.2f}. Safe fix: `{_clip(fix, 60)}`."
    return f"Cost {cost:.2f}."


def pain_hint(action: str, reason: str, cost: float, fix: str | None = None) -> str:
    """Two short lines the agent sees before it acts: cause, then cost and any safe fix."""
    lines = [f"`{_clip(action, 64)}` caused damage: {_clip(reason, 100)}.", cost_line(cost, fix)]
    return "\n".join(lines)


def pain_lesson_line(action: str, reason: str, created_at: str, cost: float | None = None,
                     fix: str | None = None) -> str:
    act, why = _clip(action, 80), _clip(reason, 100)
    if cost is None:
        return f"- On {_when(created_at)}, `{act}` caused damage: {why}."
    return f"- On {_when(created_at)}, `{act}` caused damage: {why}. {cost_line(cost, fix)}"


def session_lessons_context(scars, error_lessons=(), detail_lines=None) -> str:
    parts = []
    lines = list(detail_lines) if detail_lines is not None else [_lesson(s) for s in scars]
    if lines:
        body = "\n".join(lines)
        parts.append("Flinch pain memory for this project. These past actions caused damage:\n"
                     f"{body}\n"
                     "Flinch blocks these exact actions, and blocks or asks for confirmation on similar ones.")
    if error_lessons:
        parts.append("Flinch error memory for this project. Known errors and what fixed them:\n"
                     + error_lessons_lines(error_lessons))
    return "\n\n".join(parts)


def relevant_lessons_context(scars, detail_lines=None) -> str:
    lines = "\n".join(detail_lines if detail_lines is not None else [_lesson(s) for s in scars])
    return f"Flinch pain memory relevant to this request:\n{lines}"


def pain_recorded_context(scar) -> str:
    return (f"Flinch recorded pain: `{scar.normalized}` caused damage ({scar.reason}). "
            f"That exact action is now blocked (scar {scar.pain_id}), and similar actions will be blocked or "
            f"need user confirmation.")


def offline_block_reason(why: str) -> str:
    return f"Flinch: {why}. Stop and confirm before running this."


def state_block_reason(problem: str) -> str:
    return f"Flinch: scars.json is {problem}. Blocking this action."


def danger_ask_reason(why: str) -> str:
    return f"Flinch: this action looks destructive and hard to undo ({why}). Confirm only if it is intended."


def _steps(steps) -> str:
    return ", ".join(f"`{x}`" for x in steps)


def known_fix_context(command: str, sig: str, fixed_by, when: float) -> str:
    day = datetime.fromtimestamp(when).strftime("%d %b %Y")
    return (f"Flinch error memory: this error happened before in this project ({day}). `{command}` failed with "
            f"\"{sig}\" and passed after: {_steps(fixed_by)}.")


def repeat_failure_context(command: str, times: int) -> str:
    return (f"Flinch: `{command}` has now failed {times} times in a row with the same error, and nothing "
            f"changed in between.")


def _fixes(n: int) -> str:
    return f"{n} failed {'fix' if n == 1 else 'fixes'} so far"


def spiral_hint(command: str, sig: str, n: int) -> str:
    return "\n".join([
        f"Flinch: `{_clip(command, 60)}` failed. {_fixes(n)}.",
        f"Same error: \"{_clip(sig, 80)}\".",
    ])


def spiral_warning(command: str, sig: str, n: int, cost: float, fix: str | None = None) -> str:
    lines = [
        f"Flinch: warning. {_fixes(n)}. `{_clip(command, 40)}` failed {n} times in a row. Cost {cost:.2f}.",
        f"Still: \"{_clip(sig, 80)}\".",
    ]
    if fix:
        lines.append(f"Safe fix: `{_clip(fix, 60)}`.")
    return "\n".join(lines[:3])


def spiral_ask(command: str, sig: str, n: int, fix: str | None = None) -> str:
    lines = [
        f"Flinch: confirm another try. {_fixes(n)}. `{_clip(command, 40)}` failed {n} times in a row.",
        f"\"{_clip(sig, 90)}\".",
    ]
    lines.append(f"Known fix: `{_clip(fix, 70)}`." if fix else "Stop if this repeats the same approach.")
    return "\n".join(lines[:3])


def spiral_escape(sig: str, n: int, fix: str | None = None) -> str:
    repair = f"Diagnose: one hypothesis, then `{_clip(fix, 50)}`." if fix else \
        "Diagnose: one hypothesis, then one change."
    return "\n".join([
        f"Flinch: stop. {_fixes(n)}. \"{_clip(sig, 70)}\".",
        "Checkpoint: `git stash` or a new branch. Do not clean up.",
        repair,
    ])


def destructive_spiral_ask(sig: str, n: int, fix: str | None = None) -> str:
    lines = [
        f"Flinch: this cleanup follows a failure. {_fixes(n)}.",
        f"Open error: \"{_clip(sig, 80)}\".",
    ]
    lines.append(f"Safe fix: `{_clip(fix, 60)}`." if fix else "Do not reset, delete, or force-push to get green.")
    return "\n".join(lines[:3])


def thrash_ask(path: str, sig: str, n: int) -> str:
    return "\n".join([
        f"Flinch: `{_clip(path, 50)}` is being edited again. {_fixes(n)}.",
        f"Open error: \"{_clip(sig, 70)}\".",
        "One change, then rerun the check.",
    ])


def stuck_ask_reason(command: str, times: int, sig: str) -> str:
    return (f"Flinch: `{command}` failed {times} times in a row with the same error (\"{sig}\") and nothing has "
            f"changed since. Running it again will likely fail the same way. Confirm only if something outside "
            f"the project changed.")


def error_lessons_lines(lessons) -> str:
    return "\n".join(f"- `{x.command}` failed with \"{x.signature}\"; it passed after {_steps(x.fixed_by)}."
                     for x in lessons)
