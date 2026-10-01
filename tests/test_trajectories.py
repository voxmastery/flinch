"""The seven scripted trajectories. Trajectory 6 stays a known session-fallback miss."""

from flinch.trajectories import run_all


def test_scripted_trajectories(fake_embedder, tmp_path):
    rows = run_all(fake_embedder, tmp_path)
    assert [row.number for row in rows] == [1, 2, 3, 4, 5, 6, 7]
    by = {row.number: row for row in rows}
    assert by[1].passed and by[1].retries_after_first_failure == 2 and by[1].warned_before_repeat
    assert by[2].passed and by[2].legit_edit_false_blocks == 0 and by[2].retries_after_first_failure == 2
    assert by[3].passed and by[3].destructive_after_failure == 3
    assert by[4].passed
    assert by[5].passed and by[5].warned_before_repeat
    assert by[6].passed is False and by[6].legit_edit_false_blocks == 0
    assert by[7].passed
    for row in rows:
        assert row.tokens >= 0
