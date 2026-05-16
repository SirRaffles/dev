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


def test_run_refinement_for_job_loads_context_and_calls_refine(icloud_base, monkeypatch):
    """The shared helper must load global glossary + context_path + speakers
    and forward them to RefinementService.refine."""
    import importlib
    from unittest.mock import MagicMock

    # Seed a global glossary so load_global_glossary returns content.
    (icloud_base / "contexts" / "_global.md").write_text(
        "# Global Glossary\n\n## Active\n\nManukai, Starrag\n",
        encoding="utf-8",
    )

    # Reload glossary so it picks up the patched ICLOUD_BASE_PATH
    import services.glossary
    importlib.reload(services.glossary)

    # Build a fake completed job
    from job_models import TranscriptionJob
    job = TranscriptionJob("job-1")
    job.status = "completed"
    job.segments = [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}]

    import state
    monkeypatch.setattr(state, "job_store", MagicMock(get=MagicMock(return_value=job)))
    monkeypatch.setattr(state, "jobs", MagicMock(update=MagicMock()))
    monkeypatch.setattr(state, "refinement_store", MagicMock(
        update_status=MagicMock(), save_result=MagicMock(),
    ))

    captured = {}
    def fake_refine(segments, context_text=None, glossary_terms=None):
        captured["context_text"] = context_text
        captured["glossary_terms"] = glossary_terms
        return {"analysis": {}, "refined_segments": segments,
                "speaker_mapping": {}, "corrections_applied": 0,
                "speakers_identified": 0, "web_searches_performed": 0}
    fake_service = MagicMock(refine=MagicMock(side_effect=fake_refine))
    monkeypatch.setattr(state, "refinement_service", fake_service)

    from routes.refinement import _run_refinement_for_job
    _run_refinement_for_job("job-1", speaker_ids=None, context_path=None)

    assert captured["context_text"] is not None
    assert "Manukai" in captured["context_text"]
    assert "Manukai" in (captured["glossary_terms"] or [])
    assert job.refinement_status == "done"
