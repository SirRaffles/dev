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


# --- Plan 4A Task 5: TranscriptionSettings.engine narrowing + model_size drop ---


def test_engine_accepts_auto_best():
    from job_models import TranscriptionSettings
    s = TranscriptionSettings(engine="auto-best")
    assert s.engine == "auto-best"


def test_engine_accepts_auto_quick():
    from job_models import TranscriptionSettings
    s = TranscriptionSettings(engine="auto-quick")
    assert s.engine == "auto-quick"


def test_engine_default_is_auto_best():
    from job_models import TranscriptionSettings
    s = TranscriptionSettings()
    assert s.engine == "auto-best", "default engine must be auto-best"


def test_engine_rejects_legacy_whisper():
    from job_models import TranscriptionSettings
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        TranscriptionSettings(engine="whisper")


def test_engine_rejects_legacy_voxtral_local():
    from job_models import TranscriptionSettings
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        TranscriptionSettings(engine="voxtral-local")


def test_engine_rejects_legacy_voxtral_api():
    from job_models import TranscriptionSettings
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        TranscriptionSettings(engine="voxtral-api")


def test_engine_rejects_legacy_parakeet():
    from job_models import TranscriptionSettings
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        TranscriptionSettings(engine="parakeet")


def test_model_size_field_is_gone():
    """TranscriptionSettings no longer has a model_size field.

    Pydantic v2 by default IGNORES extra kwargs, so we assert on the dump
    rather than expecting a ValidationError. (If the field were still
    declared, it'd appear in model_dump().)
    """
    from job_models import TranscriptionSettings
    s = TranscriptionSettings()
    assert "model_size" not in s.model_dump()


# --- Plan 4A Task 6: orchestrator dispatch + phase transitions ---


def test_orchestrate_best_dispatches_whisper(tmp_path, monkeypatch):
    """Best mode calls transcribe_with_whisper, not transcribe_with_parakeet."""
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import orchestrator, transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("orch-best")
    job._retry_of = None
    calls = {"whisper": 0, "parakeet": 0}

    def fake_whisper(*a, **k):
        calls["whisper"] += 1
        return {"segments": [{"start": 0, "end": 1, "text": "hi"}], "text": "hi", "language": "en"}

    def fake_parakeet(*a, **k):
        calls["parakeet"] += 1
        return {"segments": [], "text": "", "language": "en"}

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "refinement_available", False)
    monkeypatch.setattr(orchestrator, "transcribe_with_whisper", fake_whisper)
    monkeypatch.setattr(orchestrator, "transcribe_with_parakeet", fake_parakeet)
    monkeypatch.setattr(orchestrator, "run_diarization", lambda *a, **k: [])
    monkeypatch.delenv("HF_TOKEN", raising=False)

    settings = TranscriptionSettings(engine="auto-best", language="en",
                                     enable_diarization=False, enable_noise_reduction=False)
    orchestrator.orchestrate_transcription("orch-best", str(audio_path), settings, mode="best")

    assert calls["whisper"] == 1
    assert calls["parakeet"] == 0


def test_orchestrate_quick_dispatches_parakeet(tmp_path, monkeypatch):
    """Quick mode calls transcribe_with_parakeet (multilingual v3), not Whisper."""
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import orchestrator, transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("orch-quick")
    job._retry_of = None
    calls = {"whisper": 0, "parakeet": 0, "parakeet_key": None}

    def fake_whisper(*a, **k):
        calls["whisper"] += 1
        return {"segments": [], "text": "", "language": "en"}

    def fake_parakeet(audio_path, model_key=None):
        calls["parakeet"] += 1
        calls["parakeet_key"] = model_key
        return {"segments": [{"start": 0, "end": 1, "text": "hi"}], "text": "hi", "language": "multi"}

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "_parakeet_available", True)
    monkeypatch.setattr(transcription.state, "refinement_available", False)
    monkeypatch.setattr(orchestrator, "transcribe_with_whisper", fake_whisper)
    monkeypatch.setattr(orchestrator, "transcribe_with_parakeet", fake_parakeet)
    monkeypatch.setattr(orchestrator, "run_diarization", lambda *a, **k: [])
    monkeypatch.delenv("HF_TOKEN", raising=False)

    settings = TranscriptionSettings(engine="auto-quick", language="en",
                                     enable_diarization=False, enable_noise_reduction=False)
    orchestrator.orchestrate_transcription("orch-quick", str(audio_path), settings, mode="quick")

    assert calls["parakeet"] == 1
    assert calls["whisper"] == 0
    # Multilingual v3 covers EN+FR per the spec.
    assert calls["parakeet_key"] == "parakeet-multi-v3"


def test_orchestrate_emits_phase_transitions(tmp_path, monkeypatch):
    """Best mode writes phases in order: diarizing+transcribing → aligning → None (completed)."""
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import orchestrator, transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("orch-phases")
    job._retry_of = None
    phase_history = []

    real_update = transcription._update_job
    def tracking_update(j, **kw):
        if "phase" in kw or kw.get("_clear_phase"):
            phase_history.append(kw.get("phase"))
        real_update(j, **kw)

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "refinement_available", False)
    monkeypatch.setattr(transcription, "_update_job", tracking_update)
    monkeypatch.setattr(orchestrator, "_update_job", tracking_update)
    monkeypatch.setattr(orchestrator, "transcribe_with_whisper",
                        lambda *a, **k: {"segments": [{"start": 0, "end": 1, "text": "hi"}],
                                         "text": "hi", "language": "en"})
    # Return non-empty diarization so the `aligning` branch fires.
    # Plan 7: orchestrator gates phase-clear on `_all_labels_matched`. Use a
    # non-anonymous label so the auto-resolve branch fires (final phase=None).
    # The awaiting_speakers branch is covered by tests/test_confirm_speakers.py.
    monkeypatch.setattr(orchestrator, "run_diarization",
                        lambda *a, **k: [{"start": 0.0, "end": 1.0, "speaker": "Pascal Weber"}])
    monkeypatch.setattr(orchestrator, "assign_speakers_to_segments",
                        lambda segs, sp: [{"start": 0, "end": 1, "text": "hi", "speaker": "Pascal Weber"}])
    monkeypatch.setattr(orchestrator, "stitch_speaker_turns", lambda segs: segs)
    # B5 auto-match runs only if refinement_available — keep False to skip it here.
    monkeypatch.setenv("HF_TOKEN", "fake")

    settings = TranscriptionSettings(engine="auto-best", language="en",
                                     enable_diarization=True, enable_noise_reduction=False)
    orchestrator.orchestrate_transcription("orch-phases", str(audio_path), settings, mode="best")

    # Expected order per spec Phase Lifecycle table:
    # diarizing (parallel start) → transcribing (dominant) → aligning → None (completed).
    assert "diarizing" in phase_history
    assert "transcribing" in phase_history
    assert "aligning" in phase_history
    assert phase_history[-1] is None, f"final phase write must clear, got {phase_history}"


def test_orchestrate_best_dispatches_refinement_when_auto_refine_fires(tmp_path, monkeypatch):
    """When _should_auto_refine() returns True and refinement is available,
    Best mode submits _run_refinement_for_job onto the transcription executor."""
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import orchestrator, transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("orch-refine")
    job._retry_of = None
    submitted = []
    fake_exec = MagicMock(submit=MagicMock(side_effect=lambda *a, **k: submitted.append((a, k))))

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "refinement_available", True)
    monkeypatch.setattr(transcription.state, "refinement_store", MagicMock(create=MagicMock()))
    monkeypatch.setattr(transcription.state, "transcription_executor", fake_exec)
    monkeypatch.setattr(orchestrator.state, "transcription_executor", fake_exec, raising=False)
    monkeypatch.setattr(orchestrator, "transcribe_with_whisper",
                        lambda *a, **k: {"segments": [{"start": 0, "end": 1, "text": "hi"}],
                                         "text": "hi", "language": "en"})
    monkeypatch.setattr(orchestrator, "run_diarization", lambda *a, **k: [])
    monkeypatch.delenv("HF_TOKEN", raising=False)

    settings = TranscriptionSettings(engine="auto-best", language="en",
                                     enable_diarization=False, enable_noise_reduction=False,
                                     speaker_ids=["sp-1"])  # forces auto_refine via None mode
    orchestrator.orchestrate_transcription("orch-refine", str(audio_path), settings, mode="best")

    assert fake_exec.submit.called, "auto-refine must dispatch on the transcription executor"
    args, _kw = submitted[0]
    # args = (_run_refinement_for_job, job_id, speaker_ids, context_path, audio_path)
    assert args[1] == "orch-refine"
    assert args[2] == ["sp-1"]


def test_run_transcription_sync_routes_auto_best_to_orchestrator(tmp_path, monkeypatch):
    """_run_transcription_sync with engine=auto-best calls orchestrate_transcription(mode='best')."""
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription, orchestrator

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    calls = []
    monkeypatch.setattr(orchestrator, "orchestrate_transcription",
                        lambda jid, ap, s, mode: calls.append((jid, mode)))
    # Also patch the symbol that transcription.py imports.
    monkeypatch.setattr(transcription, "orchestrate_transcription",
                        lambda jid, ap, s, mode: calls.append((jid, mode)), raising=False)

    job = TranscriptionJob("router-1")
    job._retry_of = None
    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))

    settings = TranscriptionSettings(engine="auto-best", language="en",
                                     enable_diarization=False, enable_noise_reduction=False)
    transcription._run_transcription_sync("router-1", str(audio_path), settings)
    assert ("router-1", "best") in calls


def test_run_transcription_sync_routes_auto_quick_to_orchestrator(tmp_path, monkeypatch):
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription, orchestrator

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    calls = []
    monkeypatch.setattr(transcription, "orchestrate_transcription",
                        lambda jid, ap, s, mode: calls.append((jid, mode)), raising=False)

    job = TranscriptionJob("router-2")
    job._retry_of = None
    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))

    settings = TranscriptionSettings(engine="auto-quick", language="en",
                                     enable_diarization=False, enable_noise_reduction=False)
    transcription._run_transcription_sync("router-2", str(audio_path), settings)
    assert ("router-2", "quick") in calls
