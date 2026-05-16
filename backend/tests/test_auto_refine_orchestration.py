"""B2 unit tests: TranscriptionSettings.auto_refine and orchestration wiring."""

import pytest


def test_auto_refine_defaults_to_none():
    from job_models import TranscriptionSettings
    s = TranscriptionSettings()
    assert s.auto_refine is None


def test_auto_refine_accepts_explicit_bool():
    from job_models import TranscriptionSettings
    assert TranscriptionSettings(auto_refine=True).auto_refine is True
    assert TranscriptionSettings(auto_refine=False).auto_refine is False


def test_transcription_job_has_b2_fields():
    from job_models import TranscriptionJob
    j = TranscriptionJob("test-job")
    assert j.refinement_status is None
    assert j.auto_speaker_matches is None
    assert j.learning_summary is None
    assert j.learning_status is None


@pytest.mark.asyncio
async def test_get_job_status_emits_b2_fields(client, sample_job):
    """GET /job/{id} response includes the 4 new B2 fields, even when None."""
    resp = await client.get(f"/job/{sample_job}")
    assert resp.status_code == 200
    body = resp.json()
    assert "refinement_status" in body
    assert "auto_speaker_matches" in body
    assert "learning_summary" in body
    assert "learning_status" in body
