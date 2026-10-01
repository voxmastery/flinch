import json

from flinch.scars import ScarStore


def test_add_get_persist(tmp_path):
    p = tmp_path / "scars.json"
    s = ScarStore(p)
    scar = s.add("rm -rf data/", "deleted customer db", 1.0)
    assert s.get(scar.fingerprint) == scar
    raw = json.loads(p.read_text())
    assert set(raw[scar.fingerprint]) == {"normalized", "reason", "severity", "created_at", "pain_id"}
    assert ScarStore(p).get(scar.fingerprint) == scar  # survives restart


def test_re_scarring_keeps_the_original_pain_id(tmp_path):
    s = ScarStore(tmp_path / "scars.json")
    first = s.add("rm -rf data/", "first", 0.5, pain_id="p_keep")
    again = s.add("rm -rf data/", "worse", 1.0, pain_id="p_other")
    assert again.pain_id == first.pain_id == "p_keep"
    assert again.severity == 1.0 and len(s.all()) == 1


def test_re_scarring_keeps_one_entry_and_max_severity(tmp_path):
    s = ScarStore(tmp_path / "scars.json")
    a = s.add("rm -rf data/", "r1", 0.5)
    b = s.add("rm -rf data/", "r2", 1.0)
    assert len(s.all()) == 1 and b.severity == 1.0 and b.pain_id == a.pain_id


def test_forgive_by_pain_id_or_fingerprint_prefix(tmp_path):
    s = ScarStore(tmp_path / "scars.json")
    a = s.add("rm -rf data/", "r", 1.0)
    b = s.add("rm -rf src/", "r", 1.0)
    assert s.remove(a.pain_id) == a
    assert s.remove(b.fingerprint[:10]) == b
    assert s.all() == [] and s.remove("nope") is None


def test_corrupt_file_starts_empty_without_crashing(tmp_path):
    p = tmp_path / "scars.json"
    p.write_text("{not json")
    assert ScarStore(p).all() == []
