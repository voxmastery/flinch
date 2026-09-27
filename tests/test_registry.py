import threading
import time

from flinch import registry as reg


class SlowEngine:
    def __init__(self, home, embedder=None, root=None, emit=None):
        if root.name == "slow":
            time.sleep(1.0)
        self.home, self.root = home, str(root)

    def close(self):
        pass


def test_cold_project_does_not_block_others(tmp_path, monkeypatch):
    monkeypatch.delenv("FLINCH_HOME", raising=False)
    monkeypatch.setenv("FLINCH_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(reg, "Engine", SlowEngine)
    for name in ("slow", "fast"):
        (tmp_path / name / ".git").mkdir(parents=True)
    r = reg.Registry(lambda k, d: None, embedder=object())
    t = threading.Thread(target=r.for_cwd, args=(str(tmp_path / "slow"),))
    t.start()
    time.sleep(0.1)
    started = time.perf_counter()
    r.for_cwd(str(tmp_path / "fast"))
    assert time.perf_counter() - started < 0.5
    t.join()


def test_same_project_created_once_under_concurrency(tmp_path, monkeypatch):
    monkeypatch.delenv("FLINCH_HOME", raising=False)
    monkeypatch.setenv("FLINCH_DATA_HOME", str(tmp_path / "data"))
    made = []

    class Counting(SlowEngine):
        def __init__(self, *a, **k):
            made.append(1)
            time.sleep(0.2)
            super().__init__(*a, **k)

    monkeypatch.setattr(reg, "Engine", Counting)
    (tmp_path / "p" / ".git").mkdir(parents=True)
    r = reg.Registry(lambda k, d: None, embedder=object())
    results = []
    threads = [threading.Thread(target=lambda: results.append(r.for_cwd(str(tmp_path / "p")))) for _ in range(5)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(made) == 1 and len({id(e) for e in results}) == 1
