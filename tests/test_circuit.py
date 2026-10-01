import numpy as np
import pytest

from flinch.circuit import Circuit, CircuitParams

PAIN = "rm -rf data/"


@pytest.fixture
def real_circuit(tmp_path, real_embedder):
    return Circuit(tmp_path / "circuit.npz", real_embedder)


def test_sparsity_is_exactly_five_percent(real_circuit):
    for text in (PAIN, "ls src", "git push --force origin main", "Write:src/app.py"):
        active = real_circuit.encode(text)
        assert len(active) == 200 == len(set(active.tolist()))
        assert active.min() >= 0 and active.max() < 4000


def test_codes_deterministic_across_restarts(tmp_path, real_embedder):
    a = Circuit(tmp_path / "c.npz", real_embedder)
    code = a.encode(PAIN)
    a.save()
    b = Circuit(tmp_path / "c.npz", real_embedder)
    assert np.array_equal(code, b.encode(PAIN))


def test_spec_thresholds_with_real_embeddings(real_circuit):
    real_circuit.punish(real_circuit.encode(PAIN), 1.0)
    assert real_circuit.avoid(real_circuit.encode(PAIN)) >= 0.55
    assert real_circuit.avoid(real_circuit.encode("rm -rf ./data")) >= 0.25
    assert real_circuit.avoid(real_circuit.encode("ls src")) < 0.1
    assert real_circuit.avoid(real_circuit.encode("git status")) < 0.1


def test_related_action_is_at_least_wary(real_circuit):
    real_circuit.punish(real_circuit.encode(PAIN), 1.0)
    assert real_circuit.avoid(real_circuit.encode("rm -rf backups/")) >= 0.25


def test_weights_persist(tmp_path, fake_embedder):
    a = Circuit(tmp_path / "c.npz", fake_embedder)
    a.punish(a.encode(PAIN), 1.0)
    a.save()
    b = Circuit(tmp_path / "c.npz", fake_embedder)
    assert b.avoid(b.encode(PAIN)) == pytest.approx(a.avoid(a.encode(PAIN)), abs=1e-4)


def test_pain_accumulates_and_saturates(tmp_path, fake_embedder):
    c = Circuit(tmp_path / "c.npz", fake_embedder)
    code = c.encode(PAIN)
    c.punish(code, 0.25)
    first = c.avoid(code)
    assert first == pytest.approx(0.9 * 0.25, abs=1e-6)
    for _ in range(5):
        c.punish(code, 1.0)
    assert c.avoid(code) == pytest.approx(1.0)


def test_extinction_lowers_avoid(tmp_path, fake_embedder):
    c = Circuit(tmp_path / "c.npz", fake_embedder)
    code = c.encode(PAIN)
    c.punish(code, 1.0)
    before = c.avoid(code)
    for _ in range(10):
        c.extinguish(code)
    after = c.avoid(code)
    assert after == pytest.approx(before * 0.95 ** 10, rel=1e-4)


def test_time_decay_lowers_avoid(tmp_path, fake_embedder):
    clock = [1_000_000.0]
    c = Circuit(tmp_path / "c.npz", fake_embedder, CircuitParams(), now=lambda: clock[0])
    code = c.encode(PAIN)
    c.punish(code, 1.0)
    before = c.avoid(code)
    clock[0] += 14 * 86400  # one tau
    assert c.avoid(code) == pytest.approx(before * np.exp(-1), rel=1e-4)


def test_forgive_zeroes_code(tmp_path, fake_embedder):
    c = Circuit(tmp_path / "c.npz", fake_embedder)
    code = c.encode(PAIN)
    c.punish(code, 1.0)
    c.forgive(code)
    assert c.avoid(code) == 0.0


def test_corrupt_state_file_rebuilds(tmp_path, fake_embedder):
    p = tmp_path / "c.npz"
    original = b"garbage"
    p.write_bytes(original)
    c = Circuit(p, fake_embedder)
    assert len(c.encode(PAIN)) == 200
    archived = list(tmp_path.glob("c.npz.incompatible-*"))
    assert len(archived) == 1 and archived[0].read_bytes() == original


def test_code_cache_returns_same_readonly_code(tmp_path, fake_embedder):
    c = Circuit(tmp_path / "c.npz", fake_embedder)
    a, b = c.encode(PAIN), c.encode(PAIN)
    assert a is b and not a.flags.writeable


def test_embedder_unload_and_reload_gives_same_code(tmp_path, real_embedder):
    c = Circuit(tmp_path / "c.npz", real_embedder)
    before = c.encode_vector(real_embedder.embed(PAIN))
    assert real_embedder.unload_if_idle(0) and not real_embedder.loaded
    assert (c.encode_vector(real_embedder.embed(PAIN)) == before).all() and real_embedder.loaded
