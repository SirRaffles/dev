"""B5 unit test: inline auto-match wiring in _run_transcription_sync (Whisper path)."""

from unittest.mock import MagicMock, patch


def test_inline_auto_match_overlays_names_when_diarization_present(tmp_path, monkeypatch):
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("job-M")
    job._retry_of = None
    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)
    monkeypatch.setattr(transcription.state, "refinement_available", True)
    monkeypatch.setattr(transcription.state, "refinement_store", MagicMock(create=MagicMock()))
    monkeypatch.setattr(transcription.state, "transcription_executor",
                        MagicMock(submit=MagicMock()))

    # Stub diarization to return two speakers.
    monkeypatch.setattr(transcription, "run_diarization", lambda *a, **k: [
        {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
        {"start": 5.0, "end": 10.0, "speaker": "SPEAKER_01"},
    ])
    monkeypatch.setattr(transcription, "assign_speakers_to_segments",
                        lambda segs, speakers: [
                            {"start": 0, "end": 5, "text": "hi", "speaker": "SPEAKER_00"},
                            {"start": 5, "end": 10, "text": "bonjour", "speaker": "SPEAKER_01"},
                        ])
    monkeypatch.setattr(transcription, "stitch_speaker_turns", lambda segs: segs)

    # Stub the embedding service to "match" SPEAKER_00 → Pascal, leave SPEAKER_01 unmatched.
    fake_embedding = MagicMock()
    fake_embedding.auto_identify_speakers = MagicMock(return_value={
        "SPEAKER_00": {"name": "Pascal", "confidence": 0.91, "speaker_id": "sp-1",
                       "matched": True, "source": "pick"},
        "SPEAKER_01": {"name": None, "confidence": 0.3, "speaker_id": None,
                       "matched": False, "source": None},
    })
    monkeypatch.setattr(transcription.state, "get_speaker_embedding_service",
                        lambda: fake_embedding, raising=False)

    monkeypatch.setenv("HF_TOKEN", "fake-token")

    settings = TranscriptionSettings(
        engine="whisper", language="en",
        enable_diarization=True, enable_noise_reduction=False,
        speaker_ids=["sp-1"],
    )

    with patch("mlx_whisper.transcribe", return_value={
        "segments": [
            {"start": 0, "end": 5, "text": "hi", "words": [{"word": "hi", "start": 0, "end": 1, "probability": 1.0}]},
            {"start": 5, "end": 10, "text": "bonjour", "words": [{"word": "bonjour", "start": 5, "end": 6, "probability": 1.0}]},
        ],
        "text": "hi bonjour", "language": "en",
    }):
        transcription._run_transcription_sync("job-M", str(audio_path), settings)

    # auto_speaker_matches stored on the job
    assert job.auto_speaker_matches is not None
    assert job.auto_speaker_matches["SPEAKER_00"]["name"] == "Pascal"
    assert job.auto_speaker_matches["SPEAKER_00"]["matched"] is True

    # Segments overlay: SPEAKER_00 → Pascal, SPEAKER_01 left as is
    speakers_in_segments = [s.get("speaker") for s in job.segments]
    assert "Pascal" in speakers_in_segments
    assert "SPEAKER_01" in speakers_in_segments


def test_inline_auto_match_failure_does_not_break_job(tmp_path, monkeypatch):
    """Auto-match exceptions must be swallowed; segments keep SPEAKER_XX."""
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("job-F")
    job._retry_of = None
    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)
    # Must be True so the B5 branch executes; the test then asserts that
    # the exception inside auto_identify_speakers is swallowed and the job
    # still completes with original SPEAKER_XX labels intact.
    monkeypatch.setattr(transcription.state, "refinement_available", True)
    monkeypatch.setattr(transcription.state, "refinement_store", MagicMock(create=MagicMock()))
    monkeypatch.setattr(transcription.state, "transcription_executor",
                        MagicMock(submit=MagicMock()))
    monkeypatch.setattr(transcription, "run_diarization", lambda *a, **k: [
        {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
    ])
    monkeypatch.setattr(transcription, "assign_speakers_to_segments",
                        lambda segs, speakers: [{"start": 0, "end": 5, "text": "hi", "speaker": "SPEAKER_00"}])
    monkeypatch.setattr(transcription, "stitch_speaker_turns", lambda segs: segs)

    fake_embedding = MagicMock()
    fake_embedding.auto_identify_speakers = MagicMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(transcription.state, "get_speaker_embedding_service",
                        lambda: fake_embedding, raising=False)
    monkeypatch.setenv("HF_TOKEN", "fake-token")

    settings = TranscriptionSettings(engine="whisper", language="en",
                                     enable_diarization=True, enable_noise_reduction=False)
    with patch("mlx_whisper.transcribe", return_value={
        "segments": [{"start": 0, "end": 5, "text": "hi",
                      "words": [{"word": "hi", "start": 0, "end": 1, "probability": 1.0}]}],
        "text": "hi", "language": "en",
    }):
        transcription._run_transcription_sync("job-F", str(audio_path), settings)

    # Job completed; auto_speaker_matches stays None; speakers untouched
    assert job.status == "completed"
    assert job.auto_speaker_matches is None
    assert job.segments[0]["speaker"] == "SPEAKER_00"
