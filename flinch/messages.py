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


def session_lessons_context(scars) -> str:
    lines = "\n".join(_lesson(s) for s in scars)
    return ("Flinch pain memory for this project. These past actions caused damage:\n"
            f"{lines}\n"
            "Flinch blocks these exact actions, and blocks or asks for confirmation on similar ones.")


def relevant_lessons_context(scars) -> str:
    lines = "\n".join(_lesson(s) for s in scars)
    return f"Flinch pain memory relevant to this request:\n{lines}"


def pain_recorded_context(scar) -> str:
    return (f"Flinch recorded pain: `{scar.normalized}` caused damage ({scar.reason}). "
            f"That exact action is now blocked (scar {scar.pain_id}), and similar actions will be blocked or "
            f"need user confirmation.")


def danger_ask_reason(why: str) -> str:
    return f"Flinch: this action looks destructive and hard to undo ({why}). Confirm only if it is intended."
