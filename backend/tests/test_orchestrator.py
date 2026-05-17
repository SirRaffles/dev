"""Sub-plan A unit tests: orchestrator + phase field + Best/Quick dispatch."""

from unittest.mock import MagicMock

import pytest


def test_transcription_job_has_phase_field_defaulting_to_none():
    """TranscriptionJob must expose `phase` so the orchestrator can write it."""
    from job_models import TranscriptionJob
    job = TranscriptionJob("phase-1")
    assert hasattr(job, "phase"), "TranscriptionJob must declare a `phase` attribute"
    assert job.phase is None, "phase defaults to None pre-start"


def test_update_job_accepts_phase_kwarg(monkeypatch):
    """_update_job must accept an optional phase= argument and write it onto the job."""
    from job_models import TranscriptionJob
    from services import transcription

    job = TranscriptionJob("phase-2")
    monkeypatch.setattr(transcription.state, "jobs", MagicMock(update=MagicMock()))
    transcription._update_job(job, phase="diarizing")
    assert job.phase == "diarizing"


def test_update_job_phase_can_be_cleared_back_to_none(monkeypatch):
    """Setting phase=None must be respected (otherwise None is indistinguishable from 'not provided')."""
    from job_models import TranscriptionJob
    from services import transcription

    job = TranscriptionJob("phase-3")
    job.phase = "transcribing"
    monkeypatch.setattr(transcription.state, "jobs", MagicMock(update=MagicMock()))
    # Use a sentinel-distinct call to clear: pass phase=None explicitly.
    transcription._update_job(job, phase=None, _clear_phase=True)
    assert job.phase is None


def test_run_refinement_for_job_sets_phase_refining(monkeypatch):
    """_run_refinement_for_job must set job.phase='refining' immediately after picking up the job."""
    from job_models import TranscriptionJob
    from routes import refinement as refmod

    job = TranscriptionJob("phase-ref-1")
    job.status = "completed"
    job.segments = [{"start": 0.0, "end": 1.0, "text": "hi", "speaker": "SPEAKER_00"}]

    fake_store = MagicMock()
    fake_store.get = MagicMock(return_value=job)
    fake_store.update = MagicMock()
    monkeypatch.setattr(refmod.state, "job_store", fake_store)
    monkeypatch.setattr(refmod.state, "jobs", fake_store)

    fake_ref_store = MagicMock()
    monkeypatch.setattr(refmod.state, "refinement_store", fake_ref_store)

    # Force an early return after the phase write — fail at refine() so the
    # finally block runs but we don't need a real RefinementService.
    fake_service = MagicMock()
    fake_service.refine.side_effect = RuntimeError("stop here")
    monkeypatch.setattr(refmod.state, "refinement_service", fake_service)

    # Stub the imports so we don't pull the world in.
    monkeypatch.setattr("services.transcription.load_context_document", lambda *_a, **_k: "")
    monkeypatch.setattr("services.transcription.load_speakers_context", lambda *_a, **_k: "")
    monkeypatch.setattr("services.transcription.merge_context_sources", lambda *_a, **_k: "")
    monkeypatch.setattr("services.glossary.load_global_glossary", lambda: "")
    monkeypatch.setattr("services.glossary.load_global_glossary_terms", lambda: None)

    refmod._run_refinement_for_job("phase-ref-1")

    assert job.phase == "refining", f"expected phase='refining', got {job.phase!r}"


def test_run_post_refinement_learning_sets_then_clears_phase(monkeypatch):
    """_run_post_refinement_learning must set phase='learning' at start and clear (None) at end."""
    from job_models import TranscriptionJob
    from routes import refinement as refmod

    job = TranscriptionJob("phase-learn-1")
    job.segments = [{"start": 0.0, "end": 1.0, "speaker": "Alice"}]
    job.speakers = []

    fake_store = MagicMock()
    fake_store.get = MagicMock(return_value=job)
    fake_store.update = MagicMock()
    monkeypatch.setattr(refmod.state, "jobs", fake_store)

    # Stub all three learning workers to no-op success.
    monkeypatch.setattr("services.learning.update_speaker_embeddings", lambda **_k: 0)
    monkeypatch.setattr("services.learning.extract_insights_auto", lambda **_k: 0)
    monkeypatch.setattr("services.learning.learn_glossary_terms", lambda **_k: 0)

    # Capture phase writes in order.
    phase_writes: list = []
    real_update_job = refmod.state.jobs.update  # MagicMock — track on job

    def track_phase(_job, **kwargs):
        if "phase" in kwargs:
            phase_writes.append(kwargs.get("phase"))
        return real_update_job(_job)

    # Patch _update_job (imported lazily in step 3) to capture phase order.
    from services import transcription as tx
    monkeypatch.setattr(tx, "_update_job", track_phase)

    refmod._run_post_refinement_learning(
        job_id="phase-learn-1", audio_path=None,
        segments=[{"start": 0.0, "end": 1.0, "speaker": "Alice"}],
        analysis={},
    )

    assert phase_writes[0] == "learning", f"first phase write should be 'learning', got {phase_writes!r}"
    assert phase_writes[-1] is None, f"last phase write should clear (None), got {phase_writes!r}"
