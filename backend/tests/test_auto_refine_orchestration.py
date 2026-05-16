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


def test_run_refinement_for_job_on_refine_exception_sets_failed_status(icloud_base, monkeypatch):
    """When state.refinement_service.refine raises, the helper must mark
    job.refinement_status = "failed" (and the store too)."""
    from unittest.mock import MagicMock
    from job_models import TranscriptionJob

    job = TranscriptionJob("job-fail-1")
    job.status = "completed"
    job.segments = [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}]

    import state
    monkeypatch.setattr(state, "job_store", MagicMock(get=MagicMock(return_value=job)))
    monkeypatch.setattr(state, "jobs", MagicMock(update=MagicMock()))
    rstore = MagicMock(update_status=MagicMock(), save_result=MagicMock())
    monkeypatch.setattr(state, "refinement_store", rstore)
    monkeypatch.setattr(state, "refinement_service",
                        MagicMock(refine=MagicMock(side_effect=RuntimeError("boom"))))

    from routes.refinement import _run_refinement_for_job
    _run_refinement_for_job("job-fail-1", speaker_ids=None, context_path=None)

    assert job.refinement_status == "failed"
    # update_status was called with "failed" too
    failed_calls = [c for c in rstore.update_status.call_args_list
                    if len(c.args) >= 2 and c.args[1] == "failed"]
    assert len(failed_calls) >= 1


def test_run_refinement_for_job_missing_job_does_not_emit_processing(icloud_base, monkeypatch):
    """Missing job must transition directly to failed (no pending->processing->failed)."""
    from unittest.mock import MagicMock
    import state
    monkeypatch.setattr(state, "job_store", MagicMock(get=MagicMock(return_value=None)))
    monkeypatch.setattr(state, "jobs", MagicMock(update=MagicMock()))
    rstore = MagicMock(update_status=MagicMock(), save_result=MagicMock())
    monkeypatch.setattr(state, "refinement_store", rstore)

    from routes.refinement import _run_refinement_for_job
    _run_refinement_for_job("missing-job", speaker_ids=None, context_path=None)

    # update_status should only have been called once, with "failed"
    statuses = [c.args[1] for c in rstore.update_status.call_args_list if len(c.args) >= 2]
    assert "processing" not in statuses, f"unexpected processing transition: {statuses}"
    assert "failed" in statuses


def test_auto_refine_decision_explicit_true():
    from job_models import TranscriptionSettings
    from services.transcription import _should_auto_refine
    assert _should_auto_refine(TranscriptionSettings(auto_refine=True)) is True


def test_auto_refine_decision_explicit_false():
    from job_models import TranscriptionSettings
    from services.transcription import _should_auto_refine
    s = TranscriptionSettings(auto_refine=False, speaker_ids=["sp-1"])
    assert _should_auto_refine(s) is False


def test_auto_refine_decision_default_with_speakers():
    from job_models import TranscriptionSettings
    from services.transcription import _should_auto_refine
    s = TranscriptionSettings(speaker_ids=["sp-1"])
    assert _should_auto_refine(s) is True


def test_auto_refine_decision_default_with_context_path():
    from job_models import TranscriptionSettings
    from services.transcription import _should_auto_refine
    s = TranscriptionSettings(context_path="deal/notes.md")
    assert _should_auto_refine(s) is True


def test_auto_refine_decision_default_with_neither():
    from job_models import TranscriptionSettings
    from services.transcription import _should_auto_refine
    assert _should_auto_refine(TranscriptionSettings()) is False


def test_dispatch_submits_to_executor_when_conditions_met(tmp_path, monkeypatch):
    """When auto_refine triggers, _run_transcription_sync must submit
    _run_refinement_for_job to state.transcription_executor."""
    from unittest.mock import MagicMock, patch
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("job-A")
    job._retry_of = None

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)
    monkeypatch.setattr(transcription.state, "refinement_available", True)
    monkeypatch.setattr(transcription.state, "refinement_store", MagicMock(create=MagicMock()))

    submitted = []
    fake_exec = MagicMock(submit=MagicMock(side_effect=lambda *a, **k: submitted.append((a, k))))
    monkeypatch.setattr(transcription.state, "transcription_executor", fake_exec)

    settings = TranscriptionSettings(
        engine="whisper",
        language="en",
        enable_diarization=False,
        enable_noise_reduction=False,
        speaker_ids=["sp-1"],  # forces auto_refine in None mode
    )

    with patch("mlx_whisper.transcribe", return_value={
        "segments": [{"start": 0, "end": 1, "text": "hi", "words": []}],
        "text": "hi", "language": "en",
    }):
        transcription._run_transcription_sync("job-A", str(audio_path), settings)

    assert fake_exec.submit.called, "auto-refine must dispatch on the transcription executor"
    args, _ = submitted[0]
    # First arg is the function, then positional args (job_id, speaker_ids, context_path)
    assert args[1] == "job-A"
    assert args[2] == ["sp-1"]


def test_dispatch_skipped_when_refinement_unavailable(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, patch
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("job-B")
    job._retry_of = None
    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)
    monkeypatch.setattr(transcription.state, "refinement_available", False)
    fake_exec = MagicMock(submit=MagicMock())
    monkeypatch.setattr(transcription.state, "transcription_executor", fake_exec)

    settings = TranscriptionSettings(
        engine="whisper", language="en", enable_diarization=False,
        enable_noise_reduction=False, speaker_ids=["sp-1"],
    )
    with patch("mlx_whisper.transcribe", return_value={
        "segments": [{"start": 0, "end": 1, "text": "hi", "words": []}],
        "text": "hi", "language": "en",
    }):
        transcription._run_transcription_sync("job-B", str(audio_path), settings)

    assert not fake_exec.submit.called


def test_dispatch_failure_rolls_status_back_to_failed(tmp_path, monkeypatch):
    """If executor.submit raises (e.g. pool shutdown), refinement_status must
    not get stuck at 'pending' — it should roll back to 'failed' so the UI
    doesn't poll forever."""
    from unittest.mock import MagicMock, patch
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("job-C")
    job._retry_of = None
    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)
    monkeypatch.setattr(transcription.state, "refinement_available", True)
    rstore = MagicMock(create=MagicMock(), update_status=MagicMock())
    monkeypatch.setattr(transcription.state, "refinement_store", rstore)
    # Executor raises on submit (simulates pool shutdown / saturation).
    fake_exec = MagicMock(submit=MagicMock(side_effect=RuntimeError("pool closed")))
    monkeypatch.setattr(transcription.state, "transcription_executor", fake_exec)

    settings = TranscriptionSettings(
        engine="whisper", language="en", enable_diarization=False,
        enable_noise_reduction=False, speaker_ids=["sp-1"],
    )
    with patch("mlx_whisper.transcribe", return_value={
        "segments": [{"start": 0, "end": 1, "text": "hi", "words": []}],
        "text": "hi", "language": "en",
    }):
        transcription._run_transcription_sync("job-C", str(audio_path), settings)

    assert job.refinement_status == "failed", \
        f"expected status rollback to 'failed', got {job.refinement_status!r}"
    # store row was updated to failed too
    failed_calls = [c for c in rstore.update_status.call_args_list
                    if len(c.args) >= 2 and c.args[1] == "failed"]
    assert len(failed_calls) >= 1

@pytest.mark.asyncio
async def test_learning_summary_round_trips_through_api(client, sample_job):
    """After populating job.learning_summary, GET /job/{id} returns it."""
    import state
    job = state.jobs.get(sample_job)
    assert job is not None
    job.learning_summary = {"embeddings_updated": 1, "insights_added": 2, "terms_learned": 3}
    job.learning_status = "ok"
    state.jobs.update(job)

    resp = await client.get(f"/job/{sample_job}")
    body = resp.json()
    assert body["learning_status"] == "ok"
    assert body["learning_summary"] == {
        "embeddings_updated": 1, "insights_added": 2, "terms_learned": 3,
    }
