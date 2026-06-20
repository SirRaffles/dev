"""Characterization tests for RefinementStore.

These pin the current behaviour of RefinementStore before it is migrated onto
the deep Database module, so the migration can be proven behaviour-preserving.
"""

from job_models import RefinementStore
from migrations.runner import run_migrations


def _store(tmp_path):
    db_path = str(tmp_path / "refine.db")
    run_migrations(db_path)
    return RefinementStore(db_path)


def test_refinement_create_and_get(tmp_path):
    s = _store(tmp_path)
    s.create("job1")
    got = s.get("job1")
    assert got is not None
    assert got["job_id"] == "job1"
    assert got["status"] == "pending"


def test_refinement_get_missing_returns_none(tmp_path):
    s = _store(tmp_path)
    assert s.get("nope") is None


def test_refinement_update_status(tmp_path):
    s = _store(tmp_path)
    s.create("job1")
    s.update_status("job1", "processing")
    assert s.get("job1")["status"] == "processing"


def test_refinement_update_status_with_error(tmp_path):
    s = _store(tmp_path)
    s.create("job1")
    s.update_status("job1", "failed", "boom")
    got = s.get("job1")
    assert got["status"] == "failed"
    assert got["error"] == "boom"


def test_refinement_create_is_idempotent_replace(tmp_path):
    s = _store(tmp_path)
    s.create("job1")
    s.update_status("job1", "completed")
    # INSERT OR REPLACE resets the row back to pending.
    s.create("job1")
    assert s.get("job1")["status"] == "pending"


def test_refinement_save_result(tmp_path):
    s = _store(tmp_path)
    s.create("job1")
    s.save_result(
        "job1",
        {
            "analysis": {"summary": "ok"},
            "refined_segments": [{"text": "hi"}],
            "speaker_mapping": {"SPEAKER_00": "Alice"},
            "corrections_applied": 3,
            "speakers_identified": 2,
            "web_searches_performed": 1,
        },
    )
    got = s.get("job1")
    assert got["status"] == "completed"
    # JSON fields are decoded back into Python objects by _row_to_dict.
    assert got["analysis"] == {"summary": "ok"}
    assert got["refined_segments"] == [{"text": "hi"}]
    assert got["speaker_mapping"] == {"SPEAKER_00": "Alice"}
    assert got["corrections_applied"] == 3
    assert got["speakers_identified"] == 2
    assert got["web_searches_performed"] == 1
    assert got["completed_at"] is not None
