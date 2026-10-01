import pytest

import numpy as np

from flinch.config import load_config
from flinch.decide import Engine
from flinch.hooks import (
    PostToolUseFailureInput,
    PostToolUseInput,
    PreToolUseInput,
    SessionStartInput,
    UserPromptSubmitInput,
)
from flinch.innate import Innate, Readout


def pre(cmd, tid="t"):
    return PreToolUseInput(session_id="s", cwd="/p", hook_event_name="PreToolUse",
                           tool_name="Bash", tool_input={"command": cmd}, tool_use_id=tid)


def post(cmd, tid="t"):
    return PostToolUseInput(session_id="s", cwd="/p", hook_event_name="PostToolUse",
                            tool_name="Bash", tool_input={"command": cmd}, tool_use_id=tid, tool_response={})


def make_engine(home, embedder, innate=None):
    events = []
    e = Engine(home, embedder=embedder, emit=lambda t, d: events.append((t, d)), innate=innate or Innate(None, None))
    e.events = events
    return e


@pytest.fixture
def engine(tmp_path, fake_embedder):
    e = make_engine(tmp_path / ".flinch", fake_embedder)
    yield e
    e.close()


def prompt(text, session="s"):
    return UserPromptSubmitInput(session_id=session, cwd="/p", hook_event_name="UserPromptSubmit", prompt=text)


def start():
    return SessionStartInput(session_id="s2", cwd="/p", hook_event_name="SessionStart", source="startup")


def fail(cmd, error="Exit code 1\nboom", tid="f"):
    return PostToolUseFailureInput(session_id="s", cwd="/p", hook_event_name="PostToolUseFailure", tool_name="Bash",
                                   tool_input={"command": cmd}, tool_use_id=tid, error=error, is_interrupt=False)


def damage(engine, cmd="rm -rf data/"):
    engine.pre(pre(cmd, "d1"))
    engine.post(post(cmd, "d1"))
    return engine.hurt("deleted the customer database", 1.0)


@pytest.mark.parametrize("avoid,expected", [(0.9, "deny"), (0.55, "deny"), (0.4, "ask"), (0.25, "ask"), (0.1, None)])
def test_reflex_thresholds(engine, monkeypatch, avoid, expected):
    damage(engine)
    monkeypatch.setattr(engine.circuit, "avoid", lambda active: avoid)
    out = engine.pre(pre("mv backups archive"))  # not destructive by rule: isolates the reflex
    got = out["hookSpecificOutput"]["permissionDecision"] if out else None
    assert got == expected


def test_reflex_deny_cites_nearest_scar(engine, monkeypatch):
    damage(engine)
    monkeypatch.setattr(engine.circuit, "avoid", lambda active: 0.8)
    reason = engine.pre(pre("rm -rf ./data"))["hookSpecificOutput"]["permissionDecisionReason"]
    assert "rm -rf data/" in reason and "deleted the customer database" in reason


def test_hurt_teaches_circuit(engine):
    code = engine.circuit.encode("rm -rf data/")
    assert engine.circuit.avoid(code) == 0
    damage(engine)
    assert engine.circuit.avoid(code) >= 0.55


def test_safe_completion_extinguishes(engine):
    damage(engine)
    code = engine.circuit.encode("rm -rf data/")
    before = engine.circuit.avoid(code)
    engine.pre(pre("rm -rf data/", "x"))  # scar-denied: never runs, so no post
    engine.pre(pre("ls data", "y"))
    engine.post(post("ls data", "y"))
    assert engine.circuit.avoid(code) <= before


def test_forgive_clears_reflex_and_emits(engine):
    scar = damage(engine)
    engine.forgive(scar.pain_id)
    assert engine.circuit.avoid(engine.circuit.encode("rm -rf data/")) == 0
    assert [t for t, _ in engine.events if t == "forgive"]


def test_events_emitted_for_decisions_and_hurt(engine):
    damage(engine)
    engine.pre(pre("rm -rf data/"))
    kinds = [t for t, _ in engine.events]
    assert "hurt" in kinds and kinds.count("decision") == 2
    last = [d for t, d in engine.events if t == "decision"][-1]
    assert last["decision"] == "deny" and last["gate"] == "scar" and len(last["active"]) == 200
    assert set(last) >= {"id", "ts", "session", "tool", "action", "state", "avoid", "latency_ms", "reason"}


def test_heal_event_when_weights_fade(engine):
    scar = damage(engine)
    code = engine.circuit.encode(scar.normalized)
    for _ in range(40):
        engine.circuit.extinguish(code)
    engine.pre(pre("ls", "z"))
    engine.post(post("ls", "z"))
    heals = [d for t, d in engine.events if t == "heal"]
    assert len(heals) == 1 and heals[0]["pain_id"] == scar.pain_id


def test_config_defaults_and_override(tmp_path):
    cfg = load_config(tmp_path)
    assert (cfg.flinch_threshold, cfg.wary_threshold) == (0.55, 0.25)
    (tmp_path / "config.toml").write_text("[thresholds]\nflinch = 0.7\n")
    assert load_config(tmp_path).flinch_threshold == 0.7
    (tmp_path / "config.toml").write_text("not = [valid")
    assert load_config(tmp_path).flinch_threshold == 0.55


# --- step 4: pain detection -------------------------------------------------

def test_user_report_creates_pain_and_tells_claude(engine):
    engine.pre(pre("rm -rf data/", "d1")); engine.post(post("rm -rf data/", "d1"))
    engine.pre(pre("ls", "d2")); engine.post(post("ls", "d2"))
    out = engine.prompt(prompt("you deleted the customer database!"))
    ctx = out["hookSpecificOutput"]
    assert ctx["hookEventName"] == "UserPromptSubmit" and "rm -rf data/" in ctx["additionalContext"]
    assert engine.pre(pre("rm -rf data/", "d3"))["hookSpecificOutput"]["permissionDecision"] == "deny"
    hurt = [d for t, d in engine.events if t == "hurt"][0]
    assert hurt["source"] == "user_report" and hurt["severity"] == 1.0


def test_ordinary_prompt_no_pain(engine):
    engine.pre(pre("rm -rf data/", "d1")); engine.post(post("rm -rf data/", "d1"))
    assert engine.prompt(prompt("please add a README")) is None
    assert engine.scars.all() == []


def test_failures_are_not_pain_without_regression(engine):
    engine.pre(pre("git push --force origin main", "f")); engine.post_failure(fail("git push --force origin main"))
    assert engine.scars.all() == []


# --- step 5: memory and lessons ---------------------------------------------

def test_session_start_lessons(engine):
    assert engine.session_start(start()) is None
    damage(engine)
    ctx = engine.session_start(start())["hookSpecificOutput"]
    assert ctx["hookEventName"] == "SessionStart"
    assert "rm -rf data/" in ctx["additionalContext"] and "deleted the customer database" in ctx["additionalContext"]


def test_forgiven_pain_is_not_a_lesson(engine):
    scar = damage(engine)
    engine.forgive(scar.pain_id)
    assert engine.session_start(start()) is None


def test_memory_written_on_pain(engine):
    damage(engine)
    hits = engine.memory.recall("rm -rf data/", 3)
    assert hits and hits[0].pain_id == engine.scars.all()[0].pain_id


# --- step 6: built-in danger sense (replaces remote judgment) ---------------------

class ConstReadout:
    def __init__(self, p):
        self.p = p

    def __call__(self, code, z):
        return self.p


def test_strong_rule_asks_for_never_seen_destroyer(engine):
    out = engine.pre(pre("git push --force origin main"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "force push" in out["hookSpecificOutput"]["permissionDecisionReason"]
    last = [d for t, d in engine.events if t == "decision"][-1]
    assert last["gate"] == "judgment" and last["state"] == "wary"


def test_learned_danger_asks_above_threshold(tmp_path, fake_embedder):
    e = make_engine(tmp_path / ".flinch", fake_embedder, Innate(ConstReadout(0.95), ConstReadout(0.0)))
    out = e.pre(pre("fly apps destroy shop -y"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask" and "learned danger 0.95" in \
        out["hookSpecificOutput"]["permissionDecisionReason"]
    e.close()


def test_learned_danger_below_threshold_passes(tmp_path, fake_embedder):
    e = make_engine(tmp_path / ".flinch", fake_embedder, Innate(ConstReadout(0.5), ConstReadout(0.0)))
    assert e.pre(pre("fly deploy")) is None  # pass, never "allow": user permission flow stays intact
    e.close()


def test_read_only_and_file_writes_not_gated(tmp_path, fake_embedder):
    e = make_engine(tmp_path / ".flinch", fake_embedder, Innate(ConstReadout(0.99), ConstReadout(0.0)))
    assert e.pre(pre("ls src")) is None
    w = PreToolUseInput(session_id="s", cwd="/p", hook_event_name="PreToolUse", tool_name="Write",
                        tool_input={"file_path": str(e.home.parent / "a.py"), "content": "x"}, tool_use_id="w")
    assert e.pre(w) is None
    e.close()


def test_status_reflects_trained_weights(engine, tmp_path, fake_embedder):
    assert engine.judgment_status() == "unavailable"  # rules only
    e = make_engine(tmp_path / "x" / ".flinch", fake_embedder, Innate(ConstReadout(0.1), ConstReadout(0.1)))
    assert e.judgment_status() == "ok"
    e.close()


def test_shipped_weights_load_for_real_encoding(tmp_path, real_embedder):
    e = Engine(tmp_path / ".flinch", embedder=real_embedder)
    assert e.innate.available and e.judgment_status() == "ok"
    danger = lambda t: e._danger_score(t)  # noqa: E731
    assert danger("heroku apps:destroy --app shop --confirm shop") >= 0.9
    assert danger("git status") < 0.5 and danger("npm test") < 0.5
    e.close()


def test_plus_refspec_is_force_push():
    from flinch.innate import strong_rule

    assert strong_rule("git push origin +main") == "force push or remote delete"
    assert strong_rule("git push origin main") is None


def test_danger_threshold_configurable(tmp_path, fake_embedder):
    home = tmp_path / ".flinch"
    home.mkdir()
    (home / "config.toml").write_text("[thresholds]\ndanger = 0.97\n")
    e = make_engine(home, fake_embedder, Innate(ConstReadout(0.95), ConstReadout(0.0)))
    assert e.pre(pre("fly apps destroy shop -y")) is None
    e.close()


@pytest.mark.parametrize("cmd,label", [
    ("git push origin :main", "force push or remote delete"), ("dd if=/dev/urandom of=/dev/nvme0n1", "overwrites a disk or file"),
    ("docker compose down -v", "deletes containers or volumes"), ("vercel env rm API_KEY production", "removes secrets or config"),
    ("heroku config:unset DATABASE_URL", "removes secrets or config"), ("gh secret delete TOKEN", "removes secrets or config"),
])
def test_rule_coverage(cmd, label):
    from flinch.innate import strong_rule

    assert strong_rule(cmd) == label


@pytest.mark.parametrize("cmd", ["docker compose down", "vercel env ls", "git push origin main", "echo 'dd is a tool'",
                                 "gh secret list", "grep -n config src/"])
def test_rules_do_not_fire_on_safe(cmd):
    from flinch.innate import strong_rule

    assert strong_rule(cmd) is None


@pytest.mark.parametrize("cmd", [
    'grep "delete from users" app.sql', "grep -r 'DROP TABLE' migrations/", "rg -n 'truncate table' src",
    'echo "rm -rf /" >> README.md', "git log --grep='force push'", 'echo "git push --force is bad"',
])
def test_quoted_or_searched_text_does_not_trigger_rules(cmd):
    from flinch.innate import strong_rule

    assert strong_rule(cmd) is None


@pytest.mark.parametrize("cmd", [
    "psql -c 'drop table users'", "sqlite3 app.db 'delete from orders'", "mysql -e 'TRUNCATE TABLE payments'",
    "rm -rf data/ && echo done",
])
def test_real_destroyers_inside_quotes_still_caught(cmd):
    from flinch.innate import strong_rule

    assert strong_rule(cmd) is not None


# --- errors while building -----------------------------------------------------

def edit(path, tid):
    return PreToolUseInput(session_id="s", cwd="/p", hook_event_name="PreToolUse", tool_name="Edit",
                           tool_input={"file_path": path, "old_string": "a", "new_string": "b"}, tool_use_id=tid)


def run_edit(engine, path, tid):
    e = edit(str(engine.home.parent / path), tid)
    engine.pre(e)
    engine.post(PostToolUseInput(**{**e.model_dump(), "hook_event_name": "PostToolUse", "tool_response": {}}))


def test_known_fix_is_told_on_repeat_error(engine):
    err = "Exit code 1\nError: Cannot find module 'express'"
    engine.pre(pre("npm run build", "b1")); engine.post_failure(fail("npm run build", err, "b1"))
    engine.pre(pre("npm install express", "i1")); engine.post(post("npm install express", "i1"))
    engine.pre(pre("npm run build", "b2")); engine.post(post("npm run build", "b2"))
    engine.pre(pre("rm -rf node_modules", "r1")); engine.post(post("rm -rf node_modules", "r1"))
    engine.pre(pre("npm run build", "b3"))
    out = engine.post_failure(fail("npm run build", err, "b3"))
    ctx = out["hookSpecificOutput"]
    assert ctx["hookEventName"] == "PostToolUseFailure"
    assert "npm install express" in ctx["additionalContext"] and "Cannot find module" in ctx["additionalContext"]


def test_loop_breaker_asks_on_third_unchanged_attempt(engine):
    err = "Exit code 1\nE   assert 1 == 2"
    for i in range(2):
        engine.pre(pre("pytest -q", f"t{i}"))
        out = engine.post_failure(fail("pytest -q", err, f"t{i}"))
    assert "failed 2 times in a row" in out["hookSpecificOutput"]["additionalContext"]
    third = engine.pre(pre("pytest -q", "t3"))
    assert third["hookSpecificOutput"]["permissionDecision"] == "ask"
    run_edit(engine, "src/app.py", "e1")  # a change resets it
    assert engine.pre(pre("pytest -q", "t4")) is None


def test_regression_is_a_lesson_not_a_scar(engine):
    engine.pre(pre("npm run build", "b1")); engine.post(post("npm run build", "b1"))
    run_edit(engine, "src/app.ts", "e1")
    engine.pre(pre("npm run build", "b2"))
    out = engine.post_failure(fail("npm run build", "Exit code 2\nsrc/app.ts(3,1): error TS2304", "b2"))
    assert engine.scars.all() == []  # never block writes to the file that needs fixing
    assert "passed before" in out["hookSpecificOutput"]["additionalContext"] and "src/app.ts" in \
        out["hookSpecificOutput"]["additionalContext"]


def test_error_lessons_reach_new_sessions(engine):
    err = "Exit code 1\nError: Cannot find module 'express'"
    engine.pre(pre("npm run build", "b1")); engine.post_failure(fail("npm run build", err, "b1"))
    engine.pre(pre("npm install express", "i1")); engine.post(post("npm install express", "i1"))
    engine.pre(pre("npm run build", "b2")); engine.post(post("npm run build", "b2"))
    ctx = engine.session_start(start())["hookSpecificOutput"]["additionalContext"]
    assert "npm run build" in ctx and "npm install express" in ctx


def post_out(cmd, tid, stdout="", stderr=""):
    return PostToolUseInput(session_id="s", cwd="/p", hook_event_name="PostToolUse", tool_name="Bash",
                            tool_input={"command": cmd}, tool_use_id=tid,
                            tool_response={"stdout": stdout, "stderr": stderr, "interrupted": False})


def test_fix_learned_across_command_variants_and_masked_failures(engine):
    err = "Error: config/app.json not found"
    engine.pre(pre("cat scripts/build.sh ; bash scripts/build.sh", "a"))
    engine.post_failure(fail("cat scripts/build.sh ; bash scripts/build.sh", f"echo \"{err}\" >&2\n{err}\nExit code 1", "a"))
    fixcmd = "cp config/app.example.json config/app.json && sh scripts/build.sh"
    engine.pre(pre(fixcmd, "b")); engine.post(post_out(fixcmd, "b", stdout="build ok"))
    assert engine.errors.lessons()[0].fixed_by == ("cp config/app.example.json config/app.json",)
    masked = "bash scripts/build.sh 2>&1 | tail -40"  # exit 0, but the output shows the error
    engine.pre(pre(masked, "c"))
    out = engine.post(post_out(masked, "c", stdout=err))
    ctx = out["hookSpecificOutput"]
    assert ctx["hookEventName"] == "PostToolUse" and "cp config/app.example.json config/app.json" in ctx["additionalContext"]


def test_destructive_recovery_is_not_stored_as_the_fix(engine):
    err = "Error: config/app.json not found"
    engine.pre(pre("bash scripts/build.sh", "a"))
    engine.post_failure(fail("bash scripts/build.sh", err, "a"))
    engine.pre(pre("rm -rf node_modules", "r"))
    engine.post(post("rm -rf node_modules", "r"))
    fix = "cp config/app.example.json config/app.json && bash scripts/build.sh"
    engine.pre(pre(fix, "c"))
    engine.post(post_out(fix, "c", stdout="build ok"))
    assert engine.errors.lessons()[0].fixed_by == ("cp config/app.example.json config/app.json",)


def test_only_a_destructive_recovery_stores_no_fix(engine):
    err = "Error: config/app.json not found"
    engine.pre(pre("bash scripts/build.sh", "a"))
    engine.post_failure(fail("bash scripts/build.sh", err, "a"))
    engine.pre(pre("rm -rf node_modules && bash scripts/build.sh", "c"))
    engine.post(post_out("rm -rf node_modules && bash scripts/build.sh", "c", stdout="build ok"))
    assert engine.errors.lessons() == []


def test_episode_records_cause_cost_and_context(engine):
    engine.prompt(prompt("ship the migration"))
    engine.pre(pre("npm run build", "b1"))
    engine.post_failure(fail("npm run build", "Exit code 1\nError: Cannot find module 'express'", "b1"))
    engine.pre(pre("npm install express", "i1"))
    engine.post(post("npm install express", "i1"))
    engine.pre(pre("npm run build", "b2"))
    engine.post(post("npm run build", "b2"))
    engine.pre(pre("rm -rf node_modules", "r1"))
    engine.post(post("rm -rf node_modules", "r1"))
    scar = engine.hurt("broke the production build", 0.75, session_id="s", action="npm run build")
    episode = engine.memory.cached(scar.pain_id)
    assert episode.pain_id == scar.pain_id
    assert episode.action == "npm run build"
    assert episode.reason == "broke the production build"
    assert "Cannot find module" in episode.error
    assert episode.task == "ship the migration"
    assert episode.session == "s" and episode.project == engine.root
    assert episode.attempts >= 1 and "npm run build" in episode.trace
    assert episode.accepted_fix == ("npm install express",)
    assert "rm -rf" not in " ".join(episode.accepted_fix)
    assert episode.cost >= 0.75


def test_exact_deny_names_the_cost_and_keeps_the_schema(engine):
    engine.prompt(prompt("ship the migration"))
    engine.pre(pre("npm run build", "b1"))
    engine.post_failure(fail("npm run build", "Exit code 1\nError: Cannot find module 'express'", "b1"))
    engine.pre(pre("npm install express", "i1"))
    engine.post(post("npm install express", "i1"))
    engine.pre(pre("npm run build", "b2"))
    engine.post(post("npm run build", "b2"))
    engine.hurt("broke the production build", 0.75, action="npm run build")
    out = engine.pre(pre("npm run build", "b3"))["hookSpecificOutput"]
    assert set(out) == {"hookEventName", "permissionDecision", "permissionDecisionReason"}
    reason = out["permissionDecisionReason"]
    assert out["permissionDecision"] == "deny"
    assert "broke the production build" in reason and "Cost " in reason and "npm install express" in reason
    assert reason.count("\n") <= 2
    assert engine.pre(pre("git status", "g")) is None
    assert engine.pre(pre("ls", "l")) is None


def test_pre_tool_hint_is_short_and_capped(engine, monkeypatch):
    from flinch.episode import HINT_TOKEN_BUDGET, episode_content, estimate_tokens
    from flinch.memory import Recall

    scar = damage(engine)
    episode = engine.memory.cached(scar.pain_id)
    other = engine.hurt("overwrote main", 0.5, action="git push --force origin main")
    other_ep = engine.memory.cached(other.pain_id)

    def recall(cue, limit):
        if cue.startswith("mkdir"):
            return [
                Recall(other_ep.pain_id, episode_content(other_ep), 1.2),
                Recall(episode.pain_id, episode_content(episode), 4.0),
                Recall(episode.pain_id, episode_content(episode), 3.0),
            ]
        return []

    monkeypatch.setattr(engine.memory, "recall", recall)
    monkeypatch.setattr(engine.circuit, "avoid", lambda active: 0.0)
    out = engine.pre(pre("mkdir build", "m"))
    text = out["hookSpecificOutput"]["additionalContext"]
    assert "deleted the customer database" in text and "Cost " in text
    assert "overwrote main" not in text  # lower activation, cap is one
    assert text.count("\n") <= 2 and estimate_tokens(text) <= HINT_TOKEN_BUDGET
    assert engine.pre(pre("git status", "g")) is None
    assert engine.pre(pre("echo quiet", "q")) is None  # recall returns nothing: stay quiet


def test_session_ranks_by_relevance_then_severity_and_caps(engine, monkeypatch):
    from flinch.episode import episode_content
    from flinch.memory import Recall

    made = []
    for cmd, sev, why in (
        ("echo alpha", 0.25, "alpha slip"),
        ("echo beta", 1.0, "beta outage"),
        ("echo gamma", 0.5, "gamma break"),
        ("echo delta", 0.75, "delta loss"),
    ):
        scar = engine.hurt(why, sev, action=cmd)
        made.append(engine.memory.cached(scar.pain_id))

    def recall(cue, limit):
        return [Recall(ep.pain_id, episode_content(ep), 1.5) for ep in made]

    monkeypatch.setattr(engine.memory, "recall", recall)
    ctx = engine.session_start(start())["hookSpecificOutput"]["additionalContext"]
    assert "alpha slip" not in ctx  # four episodes, cap three, lowest severity drops
    assert ctx.index("beta outage") < ctx.index("delta loss") < ctx.index("gamma break")
    assert "Cost " in ctx


def test_session_fallback_still_names_cause_and_cost(engine, monkeypatch):
    damage(engine)
    monkeypatch.setattr(engine.memory, "recall", lambda cue, limit: [])
    ctx = engine.session_start(start())["hookSpecificOutput"]["additionalContext"]
    assert "rm -rf data/" in ctx and "deleted the customer database" in ctx and "Cost " in ctx


def test_failed_episode_write_leaves_no_scar(engine, monkeypatch):
    from flinch.memory import MemoryWriteError

    def boom(episode, provenance):
        raise MemoryWriteError("disk full")

    monkeypatch.setattr(engine.memory, "remember_episode", boom)
    with pytest.raises(MemoryWriteError):
        engine.hurt("deleted the customer database", 1.0, action="rm -rf data/")
    assert engine.scars.all() == []


def test_fix_steps_exclude_read_only_investigation(engine):
    err = "Error: config/app.json not found"
    engine.pre(pre("bash scripts/build.sh", "a")); engine.post_failure(fail("bash scripts/build.sh", err, "a"))
    look = "ls config ; cat config/app.example.json ; git check-ignore -v config/app.json"
    engine.pre(pre(look, "b")); engine.post(post_out(look, "b"))
    fix = "cp config/app.example.json config/app.json && bash scripts/build.sh ; echo exit=$?"
    engine.pre(pre(fix, "c")); engine.post(post_out(fix, "c", stdout="build ok"))
    assert engine.errors.lessons()[0].fixed_by == ("cp config/app.example.json config/app.json",)
