"""Causal pain episodes: cost, ranking, and the token budget. No database."""

from flinch.episode import (
    HINT_TOKEN_BUDGET,
    PainEpisode,
    embed_text,
    episode_content,
    estimate_tokens,
    measure_cost,
    parse_episode,
    rank_episodes,
)
from flinch.messages import cost_line, pain_hint
from flinch.pain import is_unsafe_recovery


def _episode(pain_id, action, reason, severity, created_at, cost=None):
    ep = PainEpisode.build(
        pain_id=pain_id, project="/proj", session="s", task="ship the migration", action=action,
        reason=reason, error="Error: permission denied", severity=severity, attempts=2,
        trace=[action], accepted_fix=["cp a b"], source="user_report", failed=True, created_at=created_at,
    )
    if cost is None:
        return ep
    return PainEpisode(**{**ep.__dict__, "cost": cost})


def test_measure_cost_scales_with_what_happened():
    calm, note = measure_cost(0.5, "mkdir build", attempts=1, failed=False)
    assert calm == 0.5 and "severity 0.50" in note
    hot, hot_note = measure_cost(0.5, "rm -rf data/", attempts=3, failed=True)
    assert hot > calm
    assert "destructive" in hot_note and "failed" in hot_note and "3 attempts" in hot_note
    assert 0 <= hot <= 1


def test_attempt_bonus_is_capped():
    modest, _ = measure_cost(0.5, "mkdir build", attempts=3, failed=False)
    many, _ = measure_cost(0.5, "mkdir build", attempts=50, failed=False)
    assert modest == 0.6  # two extra attempts, 0.05 each
    assert many == 0.7  # bonus stops at 0.20


def test_episode_roundtrip_keeps_the_cause():
    ep = _episode("p_1", "rm -rf data/", "deleted the customer database", 1.0, "2026-10-01T00:00:00+00:00")
    text = episode_content(ep)
    assert text.startswith("PAIN: rm -rf data/ caused deleted the customer database\n")
    back = parse_episode(text)
    assert back == ep
    assert parse_episode("no json here") is None


def test_embed_text_carries_action_and_reason():
    text = embed_text("rm -rf data/", "deleted the customer database")
    assert text == "rm -rf data/\ndeleted the customer database"


def test_rank_is_relevance_then_severity_then_recency():
    low = _episode("p_low", "echo a", "mild", 0.25, "2026-10-01T00:00:03+00:00")
    old = _episode("p_old", "echo b", "old", 1.0, "2026-10-01T00:00:01+00:00")
    new = _episode("p_new", "echo c", "new", 1.0, "2026-10-01T00:00:02+00:00")
    ranked = rank_episodes([(0.2, new), (0.2, old), (5.0, low), (0.2, new)], 2)
    assert [ep.pain_id for _act, ep in ranked] == ["p_low", "p_new"]


def test_hint_stays_inside_the_token_budget():
    hint = pain_hint("a" * 400, "b" * 500, 0.85, "c" * 400)
    assert hint.count("\n") == 1
    assert "Cost 0.85." in hint and "Safe fix:" in hint
    assert estimate_tokens(hint) <= HINT_TOKEN_BUDGET
    bare = cost_line(0.85)
    assert bare == "Cost 0.85." and estimate_tokens(bare) < 20


def test_hint_is_cheaper_than_the_stored_episode():
    ep = _episode("p_1", "rm -rf data/", "deleted the customer database", 1.0, "2026-10-01T00:00:00+00:00")
    hint = pain_hint(ep.action, ep.reason, ep.cost, ep.accepted_fix[0])
    assert estimate_tokens(hint) <= HINT_TOKEN_BUDGET
    assert estimate_tokens(hint) * 2 < estimate_tokens(episode_content(ep))


def test_unsafe_recovery_is_a_destructive_step():
    assert is_unsafe_recovery("rm -rf node_modules")
    assert is_unsafe_recovery("git push --force origin main")
    assert is_unsafe_recovery("git reset --hard")
    assert not is_unsafe_recovery("cp config/app.example.json config/app.json")
    assert not is_unsafe_recovery("npm install express")
