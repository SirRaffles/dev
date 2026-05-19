"""Plan 7A — backend tests for the pre-refinement speaker-resolution gate."""

import uuid
import pytest


# ---------- Task 2: speakers_resolved field + migration + GET surface ----------

def test_transcription_job_speakers_resolved_defaults_false():
    """New jobs start with speakers_resolved=False — they must pass the gate."""
    from job_models import TranscriptionJob
    job = TranscriptionJob("sr-1")
    assert hasattr(job, "speakers_resolved"), \
        "TranscriptionJob must declare a `speakers_resolved` attribute"
    assert job.speakers_resolved is False, "defaults to False pre-gate"


def test_row_to_job_migration_marks_completed_jobs_resolved():
    """Pre-Plan-7 completed jobs reloaded from SQL must be treated as
    already past the gate — they completed before the gate existed."""
    import state
    from job_models import TranscriptionJob

    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    job.status = "completed"
    job.progress = 100
    state.job_store.create(job)
    try:
        state.job_store._cache.pop(job_id, None)
        reloaded = state.job_store.get(job_id)
        assert reloaded is not None
        assert reloaded.status == "completed"
        assert reloaded.speakers_resolved is True, \
            "_row_to_job must flip completed jobs to resolved=True"
    finally:
        state.job_store.delete(job_id)


def test_row_to_job_migration_leaves_non_completed_unresolved():
    """A row with status != 'completed' must keep speakers_resolved=False."""
    import state
    from job_models import TranscriptionJob

    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    job.status = "processing"
    state.job_store.create(job)
    try:
        state.job_store._cache.pop(job_id, None)
        reloaded = state.job_store.get(job_id)
        assert reloaded is not None
        assert reloaded.status == "processing"
        assert reloaded.speakers_resolved is False, \
            "non-completed rows must not be auto-flipped"
    finally:
        state.job_store.delete(job_id)


async def test_get_job_surfaces_speakers_resolved(icloud_base, sample_job, client):
    """GET /job/{id} response must include a `speakers_resolved` field."""
    resp = await client.get(f"/job/{sample_job}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "speakers_resolved" in data, \
        "GET response must surface speakers_resolved"
    assert isinstance(data["speakers_resolved"], bool)
