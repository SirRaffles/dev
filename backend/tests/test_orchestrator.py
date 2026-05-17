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
