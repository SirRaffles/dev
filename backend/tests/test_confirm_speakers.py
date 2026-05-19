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


# ---------- Task 3: orchestrator split (auto-resolve vs awaiting) ----------

def test_all_labels_matched_true_when_all_segments_named():
    """All segments use real names → matched (auto-resolve path)."""
    from job_models import TranscriptionJob
    from services.orchestrator import _all_labels_matched

    job = TranscriptionJob("mlm-1")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "Pascal Weber"},
        {"start": 5, "end": 10, "text": "bonjour", "speaker": "David Marchesseau"},
    ]
    job.auto_speaker_matches = {}
    assert _all_labels_matched(job) is True


def test_all_labels_matched_true_when_all_anonymous_b5_matched():
    """Anonymous labels with B5 matched=True → matched (auto-resolve path)."""
    from job_models import TranscriptionJob
    from services.orchestrator import _all_labels_matched

    job = TranscriptionJob("mlm-2")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "SPEAKER_00"},
        {"start": 5, "end": 10, "text": "bonjour", "speaker": "SPEAKER_01"},
    ]
    job.auto_speaker_matches = {
        "SPEAKER_00": {"matched": True, "name": "Pascal Weber"},
        "SPEAKER_01": {"matched": True, "name": "David Marchesseau"},
    }
    assert _all_labels_matched(job) is True


def test_all_labels_matched_false_when_any_unmatched_anonymous():
    """Any anonymous label without a B5 match → unmatched (awaiting path)."""
    from job_models import TranscriptionJob
    from services.orchestrator import _all_labels_matched

    job = TranscriptionJob("mlm-3")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "Pascal Weber"},
        {"start": 5, "end": 10, "text": "??", "speaker": "SPEAKER_02"},
    ]
    job.auto_speaker_matches = {
        "SPEAKER_02": {"matched": False},
    }
    assert _all_labels_matched(job) is False


def test_all_labels_matched_empty_segments_returns_true():
    """Vacuous case: no segments to resolve → treat as matched (no-op refinement)."""
    from job_models import TranscriptionJob
    from services.orchestrator import _all_labels_matched
    job = TranscriptionJob("mlm-4")
    job.segments = []
    assert _all_labels_matched(job) is True


def test_orchestrator_auto_resolve_path_sets_resolved_and_dispatches(monkeypatch):
    """When _all_labels_matched returns True, orchestrator must:
      - set job.speakers_resolved = True
      - clear job.phase
      - leave job.status = "completed"
      - dispatch _run_refinement_for_job via state.transcription_executor
    """
    from unittest.mock import MagicMock
    import state
    from job_models import TranscriptionJob
    from services import orchestrator as orch

    job = TranscriptionJob("auto-1")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "Pascal Weber"},
    ]
    job.speakers = []
    job.auto_speaker_matches = {}
    state.job_store.create(job)
    try:
        # Drive the post-alignment finalize block directly. We extract its
        # contents into a private helper so the test can call it without
        # standing up the entire transcribe pipeline (see implementation
        # note in Step 5: the helper is `_finalize_after_alignment`).
        submit_mock = MagicMock()
        monkeypatch.setattr(state, "transcription_executor",
                            MagicMock(submit=submit_mock))
        monkeypatch.setattr(state, "refinement_available", True)
        monkeypatch.setattr(state.refinement_store, "create", MagicMock())
        # Settings stub: auto_refine on so the dispatch fires
        from job_models import TranscriptionSettings
        settings = TranscriptionSettings(speaker_ids=["sid-1"])

        orch._finalize_after_alignment(job, settings, audio_path="/fake.wav")

        assert job.speakers_resolved is True
        assert job.status == "completed"
        assert job.phase is None
        submit_mock.assert_called_once()
    finally:
        state.job_store.delete("auto-1")


def test_orchestrator_awaiting_path_sets_phase_and_does_not_dispatch(monkeypatch):
    """When _all_labels_matched returns False, orchestrator must:
      - leave job.speakers_resolved = False
      - set job.phase = "awaiting_speakers"
      - set job.status = "completed"
      - NOT dispatch refinement
    """
    from unittest.mock import MagicMock
    import state
    from job_models import TranscriptionJob, TranscriptionSettings
    from services import orchestrator as orch

    job = TranscriptionJob("await-1")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "SPEAKER_00"},
    ]
    job.auto_speaker_matches = {"SPEAKER_00": {"matched": False}}
    state.job_store.create(job)
    try:
        submit_mock = MagicMock()
        monkeypatch.setattr(state, "transcription_executor",
                            MagicMock(submit=submit_mock))
        monkeypatch.setattr(state, "refinement_available", True)
        monkeypatch.setattr(state.refinement_store, "create", MagicMock())
        settings = TranscriptionSettings(speaker_ids=["sid-1"])

        orch._finalize_after_alignment(job, settings, audio_path="/fake.wav")

        assert job.speakers_resolved is False
        assert job.status == "completed"
        assert job.phase == "awaiting_speakers"
        submit_mock.assert_not_called()
    finally:
        state.job_store.delete("await-1")
