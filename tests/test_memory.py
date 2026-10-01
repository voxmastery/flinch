import pytest

from flinch.episode import embed_text, parse_episode
from flinch.memory import Memory, MemoryWriteError


def test_remember_recall_filter_and_reopen(tmp_path, real_embedder):
    m = Memory(tmp_path / "brain", real_embedder)
    m.remember_pain("rm -rf data/", "deleted the customer database", 1.0, "p_1", "user_explicit")
    m.remember_pain("git push --force origin main", "overwrote main", 0.75, "p_2", "tool_grounded")
    hits = m.recall("clean up the project, it's cluttered", 3)
    assert hits[0].pain_id == "p_1" and "deleted the customer database" in hits[0].content
    assert [h.pain_id for h in m.recall("git push -f", 1)] == ["p_2"]
    m.close()
    m2 = Memory(tmp_path / "brain", real_embedder)
    assert m2.recall("rm -rf data/", 1)[0].pain_id == "p_1"
    m2.close()


def test_recall_is_fail_soft_and_write_failure_raises(tmp_path, fake_embedder, monkeypatch):
    m = Memory(tmp_path / "brain", fake_embedder)
    monkeypatch.setattr(m, "_brain", None)
    assert m.recall("x", 3) == []
    with pytest.raises(MemoryWriteError):
        m.remember_pain("x", "y", 1.0, "p", "user_explicit")


def test_gate_rejection_is_a_write_failure(tmp_path, fake_embedder, monkeypatch):
    m = Memory(tmp_path / "brain", fake_embedder)

    class Brain:
        def experience(self, **kwargs):
            return {"gate_rejected": True, "gate_reason": "confusion"}

        def checkpoint(self):
            raise AssertionError("a rejected episode must not be checkpointed")

    monkeypatch.setattr(m, "_brain", Brain())
    with pytest.raises(MemoryWriteError, match="confusion"):
        m.remember_pain("rm -rf data/", "deleted the customer database", 1.0, "p", "user_explicit")
    m.close()


def test_remember_embeds_action_and_reason(tmp_path, fake_embedder):
    seen = []
    real = fake_embedder.embed

    def wrap(text):
        seen.append(text)
        return real(text)

    fake_embedder.embed = wrap
    m = Memory(tmp_path / "brain", fake_embedder)
    m.remember_pain("rm -rf data/", "deleted the customer database", 1.0, "p_1", "user_explicit")
    assert embed_text("rm -rf data/", "deleted the customer database") in seen
    hit = m.recall("rm -rf data/", 1)[0]
    episode = parse_episode(hit.content)
    assert episode is not None and episode.pain_id == "p_1"
    assert episode.reason == "deleted the customer database" and episode.cost == 1.0
    m.close()
