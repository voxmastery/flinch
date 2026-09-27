from flinch.memory import Memory


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


def test_memory_failure_never_raises(tmp_path, fake_embedder, monkeypatch):
    m = Memory(tmp_path / "brain", fake_embedder)
    monkeypatch.setattr(m, "_brain", None)
    assert m.recall("x", 3) == []
    m.remember_pain("x", "y", 1.0, "p", "user_explicit")
