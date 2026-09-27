"""The gate pipeline. Owns all mutable state; the daemon is a thin HTTP shell around it."""

import json
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from flinch.circuit import Circuit, TextEmbedder
from flinch.config import Config, load_config
from flinch.hooks import (
    PostToolUseFailureInput,
    PostToolUseInput,
    PreToolUseInput,
    SessionStartInput,
    ToolInput,
    UserPromptSubmitInput,
    context,
    decision,
)
from flinch.errors import ErrorMemory, core_command, has_error_line, masks_exit
from flinch.innate import Innate, strong_rule
from flinch.memory import Memory
from flinch.messages import (
    danger_ask_reason,
    known_fix_context,
    repeat_failure_context,
    stuck_ask_reason,
    pain_recorded_context,
    reflex_ask_reason,
    reflex_deny_reason,
    relevant_lessons_context,
    scar_reason,
    session_lessons_context,
)
from flinch.normalize import fingerprint, normalize
from flinch.pain import PainDetector, PainFinding, is_test_command, pick_culprit
from flinch.readonly import is_mutating
from flinch.recent import RecentActions
from flinch.scars import SEVERITIES, Scar, ScarStore

Emit = Callable[[str, dict[str, Any]], None]
HEAL_BELOW = 0.25
PENDING_CAP = 512
LESSON_LIMIT = 5
STUCK_ASK_AFTER = 2  # ask before a third unchanged run of a command that keeps failing the same way
LESSON_CUE = "destructive actions in this project"
# Recall activation is unbounded; unrelated pain memories sit near 0.26 and on-topic ones
# above 1.0 (measured with the pinned memory store version). Only on-topic memories are injected per prompt.
RELEVANT_ACTIVATION = 1.0
PROVENANCE = {"manual": "user_explicit", "user_report": "user_explicit"}


def _output_text(response: Any) -> str:
    """Tool output as text (Claude Code: {stdout, stderr}; Cursor: JSON string; else anything)."""
    if isinstance(response, dict):
        return "\n".join(str(response.get(k) or "") for k in ("stdout", "stderr", "output"))
    return str(response or "")


class NoActionToBlame(Exception):
    pass


@dataclass(frozen=True)
class Normalized:
    text: str
    fingerprint: str


@dataclass(frozen=True)
class Verdict:
    decision: str  # allow | deny | ask | pass
    gate: str  # scar | reflex | judgment | none
    state: str  # calm | wary | flinch
    reason: str | None
    cite: str | None = None  # pain_id


class DecisionLog:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def write(self, record: dict[str, Any]) -> None:
        line = json.dumps({"ts": round(time.time(), 3), **record}, default=str)
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a") as f:
                f.write(line + "\n")


class Engine:
    def __init__(self, home: Path, embedder: TextEmbedder | None = None, emit: Emit | None = None,
                 config: Config | None = None, innate: Innate | None = None, root: Path | None = None) -> None:
        if embedder is None:
            from flinch.embed import Embedder

            embedder = Embedder()
        self.home = home
        self.root = str(root or home.parent)
        self.name = Path(self.root).name
        self.config = config or load_config(home)
        self.scars = ScarStore(home / "scars.json")
        self.recent = RecentActions(home / "recent.json")
        self.errors = ErrorMemory(home / "errors.json")
        self.log = DecisionLog(home / "log.jsonl")
        self.circuit = Circuit(home / "circuit.npz", embedder)
        self.memory = Memory(home / "brain", embedder)
        self.innate = innate or Innate.load(self.circuit.encoding_fingerprint)
        self.detector = PainDetector(self.recent, report=self._report_score, danger=self._danger_score)
        self.decisions: deque[dict[str, Any]] = deque(maxlen=50)
        self._emit = emit or (lambda kind, data: None)
        self._pending: dict[str, np.ndarray] = {}  # tool_use_id -> active code of allowed actions
        self._scar_codes: dict[str, np.ndarray] = {}
        self._healed: set[str] = set()
        self._lock = threading.Lock()
        self.circuit.encode("warm up")  # first ONNX call is ~10x slower; pay it at startup

    # --- helpers -------------------------------------------------------------

    def _norm(self, inp: ToolInput) -> Normalized:
        text = normalize(inp.tool_name, inp.tool_input, self.root)
        return Normalized(text, fingerprint(text))

    def _scar_code(self, scar: Scar) -> np.ndarray:
        code = self._scar_codes.get(scar.fingerprint)
        if code is None:
            code = self.circuit.encode(scar.normalized)
            self._scar_codes = {**self._scar_codes, scar.fingerprint: code}
        return code

    def _nearest_scar(self, active: np.ndarray) -> Scar | None:
        best, best_overlap = None, 0
        for scar in self.scars.all():
            overlap = len(np.intersect1d(active, self._scar_code(scar), assume_unique=True))
            if overlap > best_overlap:
                best, best_overlap = scar, overlap
        return best

    def judgment_status(self) -> str:
        """Built-in danger sense: "ok" with trained readouts, "unavailable" when running on rules only."""
        return "ok" if self.innate.available else "unavailable"

    def _danger_score(self, text: str) -> float | None:
        if self.innate.danger is None:
            return None
        return self.innate.danger(*self.circuit.features(text))

    def _report_score(self, text: str) -> float | None:
        if self.innate.report is None:
            return None
        return self.innate.report(*self.circuit.features(text))

    def close(self) -> None:
        self.memory.close()

    def _pain_recalls(self, cue: str, limit: int) -> list:
        live = {s.pain_id for s in self.scars.all()}
        return [r for r in self.memory.recall(cue, limit + len(live)) if r.pain_id in live][:limit]

    def weights(self) -> list[float]:
        return [round(float(x), 4) for x in self.circuit.weights()]

    # --- gates ---------------------------------------------------------------

    def _gate(self, inp: ToolInput, n: Normalized, active: np.ndarray, avoid: float) -> Verdict:
        scar = self.scars.get(n.fingerprint)
        if scar:
            return Verdict("deny", "scar", "flinch",
                           scar_reason(scar.normalized, scar.reason, scar.pain_id, scar.created_at), scar.pain_id)
        cfg = self.config
        if avoid >= cfg.wary_threshold:
            near = self._nearest_scar(active)
            if avoid >= cfg.flinch_threshold:
                return Verdict("deny", "reflex", "flinch", reflex_deny_reason(near, avoid),
                               near.pain_id if near else None)
            return Verdict("ask", "reflex", "wary", reflex_ask_reason(near, avoid), near.pain_id if near else None)
        core = core_command(n.text)[0] if inp.tool_name == "Bash" else ""
        stuck = self.errors.stuck(core, self.errors.change_count) if core else 0
        if stuck >= STUCK_ASK_AFTER:
            sig = (self.errors.open_failure(core) or {}).get("signature", "")
            return Verdict("ask", "judgment", "wary", stuck_ask_reason(core, stuck, sig), None)
        return self._judgment(inp, n)

    def _judgment(self, inp: ToolInput, n: Normalized) -> Verdict:
        """Never-seen actions: ask before anything that looks destructive (rules + trained danger unit)."""
        calm = Verdict("pass", "none", "calm", None)
        if inp.tool_name in ("Write", "Edit", "Delete") or not is_mutating(inp.tool_name, inp.tool_input):
            return calm
        why = strong_rule(n.text)
        if why is None:
            score = self._danger_score(n.text)
            if score is None or score < self.config.danger_threshold:
                return calm
            why = f"learned danger {score:.2f}"
        return Verdict("ask", "judgment", "wary", danger_ask_reason(why), None)

    # --- hooks ---------------------------------------------------------------

    def pre(self, inp: PreToolUseInput) -> dict[str, Any] | None:
        started = time.perf_counter()
        n = self._norm(inp)
        active = self.circuit.encode(n.text)
        avoid = self.circuit.avoid(active)
        verdict = self._gate(inp, n, active, avoid)
        ms = round((time.perf_counter() - started) * 1000, 3)
        if verdict.decision != "deny" and inp.tool_use_id:
            with self._lock:
                self._pending[inp.tool_use_id] = active
                while len(self._pending) > PENDING_CAP:
                    self._pending.pop(next(iter(self._pending)))
        self._record(inp, n, active, avoid, verdict, ms)
        if verdict.decision in ("deny", "ask"):
            return decision(verdict.decision, verdict.reason or "")
        return None

    def _record(self, inp: ToolInput, n: Normalized, active: np.ndarray, avoid: float,
                v: Verdict, ms: float) -> None:
        self.log.write({
            "event": "pre", "session": inp.session_id, "tool": inp.tool_name, "action": n.text,
            "gates": {"scar": "hit" if v.gate == "scar" else "miss",
                      "reflex": {"avoid": round(avoid, 4), "state": v.state}},
            "decision": v.decision, "gate": v.gate, "cite": v.cite, "ms": ms,
        })
        event = {"id": uuid.uuid4().hex[:12], "ts": time.time(), "session": inp.session_id,
                 "tool": inp.tool_name, "action": n.text, "decision": v.decision, "gate": v.gate,
                 "state": v.state, "avoid": round(avoid, 4), "active": active.tolist(),
                 "latency_ms": ms, "reason": v.reason}
        self.decisions.append(event)
        self._emit("decision", event)

    def _executed(self, inp: ToolInput, failed: bool) -> str | None:
        """Bookkeeping after a tool ran. Returns a regression note for the agent, if any."""
        with self._lock:
            active = self._pending.pop(inp.tool_use_id, None) if inp.tool_use_id else None
        if not failed and active is not None:
            self.circuit.extinguish(active)
            self._check_healing()
            self.circuit.save()
        n = self._norm(inp)
        note = None
        if inp.tool_name == "Bash" and is_test_command(n.text):
            note = self.detector.test_result(inp.session_id, n.text, passed=not failed)
        if not is_mutating(inp.tool_name, inp.tool_input):
            return note
        self.recent.add(session_id=inp.session_id, tool_use_id=inp.tool_use_id, tool=inp.tool_name,
                        normalized=n.text, fingerprint=n.fingerprint, failed=failed)
        self.log.write({"event": "post-failure" if failed else "post", "session": inp.session_id,
                        "tool": inp.tool_name, "action": n.text})
        return note

    def _check_healing(self) -> None:
        w = self.circuit.weights()
        for scar in self.scars.all():
            if scar.pain_id in self._healed or float(w[self._scar_code(scar)].max()) >= HEAL_BELOW:
                continue
            with self._lock:  # check-then-add must be atomic: concurrent posts would double-heal
                if scar.pain_id in self._healed:
                    continue
                self._healed.add(scar.pain_id)
            self.log.write({"event": "heal", "pain_id": scar.pain_id, "action": scar.normalized})
            self._emit("heal", {"ts": time.time(), "pain_id": scar.pain_id, "action": scar.normalized,
                                "weights": self.weights()})

    def post(self, inp: PostToolUseInput) -> dict[str, Any] | None:
        self._executed(inp, failed=False)
        n = self._norm(inp)
        result = None
        if inp.tool_name == "Bash":
            output = _output_text(inp.tool_response)
            core, prefix = core_command(n.text)
            if masks_exit(n.text) and has_error_line(output):  # e.g. `build 2>&1 | tail`: exit 0, but it failed
                result = self._on_failure(inp, n, output, "PostToolUse")
            elif self.errors.open_failure(core):
                self._learn_fix(inp, n, core, prefix)
        if is_mutating(inp.tool_name, inp.tool_input):
            self.errors.bump()
        return result

    def _learn_fix(self, inp: ToolInput, n: Normalized, core: str, prefix: tuple[str, ...]) -> None:
        failed_at = self.errors.open_failure(core)["failed_at"]
        steps = [core_command(a.normalized) for a in self.recent.for_session_any()
                 if a.ts > failed_at and not a.failed and a.normalized != n.text]
        # keep only the state-changing parts of each earlier action, never the failing command itself
        changes = [part for c, pre_steps in steps for part in (*pre_steps, c)
                   if part != core and is_mutating("Bash", {"command": part})] + list(prefix)
        lesson = self.errors.record_success(core, changes, self.errors.change_count)
        if lesson:
            self.log.write({"event": "lesson", "session": inp.session_id, "action": n.text,
                            "error": lesson.signature, "fixed_by": list(lesson.fixed_by)})
            self._emit("lesson", {"ts": time.time(), "action": n.text, "error": lesson.signature,
                                  "fixed_by": list(lesson.fixed_by)})

    def post_failure(self, inp: PostToolUseFailureInput) -> dict[str, Any] | None:
        if inp.is_interrupt:
            return None
        note = self._executed(inp, failed=True)  # errors become lessons, never scars
        if inp.tool_name != "Bash":
            return None
        return self._on_failure(inp, self._norm(inp), inp.error, "PostToolUseFailure", note)

    def _on_failure(self, inp: ToolInput, n: Normalized, error: str, event: str,
                    note: str | None = None) -> dict[str, Any] | None:
        core = core_command(n.text)[0]
        failure = self.errors.record_failure(core, error, self.errors.change_count)
        parts = [note] if note else []
        if failure.known_fix:
            fix = failure.known_fix
            parts.append(known_fix_context(fix.command, fix.signature, fix.fixed_by, fix.fixed_at))
        if failure.unchanged_repeats >= 1:
            parts.append(repeat_failure_context(core, failure.unchanged_repeats + 1))
        self.log.write({"event": "error", "session": inp.session_id, "action": core, "error": failure.signature,
                        "known_fix": bool(failure.known_fix), "repeats": failure.unchanged_repeats})
        return context(event, " ".join(parts)) if parts else None

    def prompt(self, inp: UserPromptSubmitInput) -> dict[str, Any] | None:
        finding = self.detector.from_prompt(inp.session_id, inp.prompt)
        if finding:
            scar = self._apply(finding, inp.session_id)
            return context("UserPromptSubmit", pain_recorded_context(scar))
        if not self.scars.all():
            return None
        relevant = [r for r in self._pain_recalls(inp.prompt, 3) if r.activation >= RELEVANT_ACTIVATION]
        return context("UserPromptSubmit", relevant_lessons_context(self._scars_for(relevant))) if relevant else None

    def session_start(self, inp: SessionStartInput) -> dict[str, Any] | None:
        scars = self._scars_for(self._pain_recalls(LESSON_CUE, LESSON_LIMIT))
        if not scars:  # recall found nothing: fall back to the most severe, most recent scars
            scars = sorted(self.scars.all(), key=lambda s: (s.severity, s.created_at), reverse=True)[:LESSON_LIMIT]
        fixes = self.errors.lessons()[:LESSON_LIMIT]
        if not scars and not fixes:
            return None
        self.log.write({"event": "lessons", "session": inp.session_id, "pain_ids": [s.pain_id for s in scars],
                        "error_lessons": len(fixes)})
        return context("SessionStart", session_lessons_context(scars, fixes))

    def _scars_for(self, recalls: list) -> list[Scar]:
        by_id = {s.pain_id: s for s in self.scars.all()}
        seen, out = set(), []
        for r in recalls:
            if r.pain_id in by_id and r.pain_id not in seen:
                seen.add(r.pain_id)
                out.append(by_id[r.pain_id])
        return out

    def _apply(self, finding: PainFinding | None, session_id: str) -> Scar | None:
        if finding is None:
            return None
        return self.learn_pain(finding.normalized, finding.reason, finding.severity, finding.source,
                               finding.attribution, session_id)

    # --- pain ----------------------------------------------------------------

    def hurt(self, reason: str, severity: float, session_id: str | None = None, source: str = "manual",
             action: str | None = None) -> Scar:
        """Record pain for an explicit action (a Bash command) or the likeliest recent culprit."""
        if severity not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}")
        if action:
            return self.learn_pain(normalize("Bash", {"command": action}, self.root), reason, severity, source,
                                   "explicit", session_id)
        recent = self.recent.for_session(session_id) if session_id else self.recent.for_session_any()
        if not recent:
            raise NoActionToBlame("no recent mutating action to attribute pain to")
        culprit = pick_culprit(recent, reason, self._danger_score)
        return self.learn_pain(culprit.normalized, reason, severity, source, "fallback", culprit.session_id)

    def learn_pain(self, normalized: str, reason: str, severity: float, source: str,
                   attribution: str, session_id: str | None = None) -> Scar:
        scar = self.scars.add(normalized, reason, severity)
        self.memory.remember_pain(normalized, reason, severity, scar.pain_id, PROVENANCE.get(source, "user_explicit"))
        active = self._scar_code(scar)
        self.circuit.punish(active, severity)
        self.circuit.save()
        self._healed.discard(scar.pain_id)
        self.log.write({"event": "hurt", "session": session_id, "action": normalized, "reason": reason,
                        "severity": severity, "pain_id": scar.pain_id, "source": source,
                        "attribution": attribution})
        self._emit("hurt", {"ts": time.time(), "pain_id": scar.pain_id, "action": normalized, "reason": reason,
                            "severity": severity, "source": source, "attribution": attribution,
                            "active": active.tolist(), "weights": self.weights()})
        return scar

    def forgive(self, ident: str) -> Scar | None:
        scar = self.scars.remove(ident)
        if scar:
            self.circuit.forgive(self._scar_code(scar))
            self.circuit.save()
            self.log.write({"event": "forgive", "action": scar.normalized, "pain_id": scar.pain_id})
            self._emit("forgive", {"ts": time.time(), "pain_id": scar.pain_id, "action": scar.normalized,
                                   "weights": self.weights()})
        return scar
