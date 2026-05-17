"""A1 unit tests: Whisper call kwargs and word-emission gating."""

from unittest.mock import patch, MagicMock


def test_whisper_called_with_a1_kwargs(tmp_path, monkeypatch):
    """The Whisper transcribe call must enforce A1 params regardless of settings."""
    from job_models import TranscriptionSettings
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    captured = {}

    def fake_transcribe(*_args, **kwargs):
        captured.update(kwargs)
        return {"segments": [], "text": "", "language": "en"}

    settings = TranscriptionSettings(
        language="en",
        word_timestamps=False,
        enable_diarization=False,
        enable_noise_reduction=False,
        engine="auto-best",
    )

    job_obj = MagicMock()
    job_obj.status = "pending"
    job_obj._retry_of = None
    job_obj.segments = None

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job_obj), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)

    with patch("mlx_whisper.transcribe", side_effect=fake_transcribe):
        transcription._run_transcription_sync("job-1", str(audio_path), settings)

    assert captured.get("word_timestamps") is True, "A1 must force word_timestamps=True regardless of user setting"
    assert captured.get("condition_on_previous_text") is False, "A1 must disable condition_on_previous_text"
    assert captured.get("logprob_threshold") == -1.0, "A1 must set logprob_threshold=-1.0"
    temperature = captured.get("temperature")
    assert isinstance(temperature, tuple), f"temperature must be a tuple, got {type(temperature)}"
    assert temperature[0] == 0.0 and len(temperature) >= 5, f"temperature ladder malformed: {temperature}"
    assert captured.get("no_speech_threshold") == 0.6, "no_speech_threshold must remain 0.6"


def test_emitted_segments_strip_words_when_user_opted_out(tmp_path, monkeypatch):
    """When settings.word_timestamps=False, emitted segments must NOT contain `words`."""
    from job_models import TranscriptionSettings
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    fake_result = {
        "segments": [
            {
                "start": 0.0, "end": 1.0, "text": "hi",
                "words": [{"word": " hi", "start": 0.0, "end": 1.0, "probability": 0.99}],
            }
        ],
        "text": "hi",
        "language": "en",
    }

    settings = TranscriptionSettings(
        language="en",
        word_timestamps=False,
        enable_diarization=False,
        enable_noise_reduction=False,
        engine="auto-best",
    )

    job_obj = MagicMock()
    job_obj.status = "pending"
    job_obj._retry_of = None
    job_obj.segments = None

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job_obj), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)

    with patch("mlx_whisper.transcribe", return_value=fake_result):
        transcription._run_transcription_sync("job-2", str(audio_path), settings)

    final_segments = job_obj.segments or []
    assert final_segments, "expected at least one emitted segment"
    for seg in final_segments:
        assert "words" not in seg, f"emitted segment must not contain 'words' when user opted out: {seg}"


def test_emitted_segments_keep_words_when_user_opted_in(tmp_path, monkeypatch):
    """When settings.word_timestamps=True, emitted segments MUST contain `words`."""
    from job_models import TranscriptionSettings
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    fake_result = {
        "segments": [
            {
                "start": 0.0, "end": 1.0, "text": "hi",
                "words": [{"word": " hi", "start": 0.0, "end": 1.0, "probability": 0.99}],
            }
        ],
        "text": "hi",
        "language": "en",
    }

    settings = TranscriptionSettings(
        language="en",
        word_timestamps=True,
        enable_diarization=False,
        enable_noise_reduction=False,
        engine="auto-best",
    )

    job_obj = MagicMock()
    job_obj.status = "pending"
    job_obj._retry_of = None
    job_obj.segments = None

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job_obj), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)

    with patch("mlx_whisper.transcribe", return_value=fake_result):
        transcription._run_transcription_sync("job-3", str(audio_path), settings)

    final_segments = job_obj.segments or []
    assert final_segments
    for seg in final_segments:
        assert "words" in seg, f"emitted segment must contain 'words' when user opted in: {seg}"


def test_vad_trim_restores_segment_timestamps(tmp_path, monkeypatch):
    """When VAD finds a 3s lead, Whisper sees the trimmed file and segment
    timestamps are restored to the original time base."""
    from job_models import TranscriptionSettings
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    fake_whisper_result = {
        "segments": [{"start": 0.0, "end": 2.0, "text": "hi", "words": []}],
        "text": "hi",
        "language": "en",
    }

    settings = TranscriptionSettings(
        language="en",
        word_timestamps=True,
        enable_diarization=False,
        enable_noise_reduction=False,
        engine="auto-best",
    )

    job_obj = MagicMock()
    job_obj.status = "pending"
    job_obj._retry_of = None
    job_obj.segments = None

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job_obj), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)

    trimmed_path = str(tmp_path / "trimmed.wav")
    # Force a 3s trim offset and intercept the trim call.
    monkeypatch.setattr("services.audio.find_first_speech_offset", lambda p, **kw: 3.0)
    monkeypatch.setattr("services.audio.make_trimmed_audio", lambda p, trim_offset: trimmed_path)

    received_paths = []

    def capture_path(audio_arg, **_kw):
        received_paths.append(audio_arg)
        return fake_whisper_result

    with patch("mlx_whisper.transcribe", side_effect=capture_path):
        transcription._run_transcription_sync("job-vad", str(audio_path), settings)

    assert received_paths == [trimmed_path], \
        f"Whisper must receive the trimmed file, got {received_paths}"
    segs = job_obj.segments or []
    assert segs and segs[0]["start"] == 3.0 and segs[0]["end"] == 5.0, \
        f"Timestamps must be restored to original time base, got {segs}"


def test_transcribe_with_whisper_is_callable_and_returns_result_dict(tmp_path, monkeypatch):
    """Extraction proof: transcribe_with_whisper exists and returns
    {text, segments, language} preserving A1 kwargs."""
    from job_models import TranscriptionSettings
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    fake_result = {
        "segments": [{"start": 0.0, "end": 1.0, "text": "hi", "words": [
            {"word": " hi", "start": 0.0, "end": 1.0, "probability": 0.99}
        ]}],
        "text": "hi",
        "language": "en",
    }

    captured = {}

    def fake_whisper(*_args, **kwargs):
        captured.update(kwargs)
        return fake_result

    settings = TranscriptionSettings(
        language="en",
        word_timestamps=True,
        enable_diarization=False,
        enable_noise_reduction=False,
        engine="auto-best",
    )

    with patch("mlx_whisper.transcribe", side_effect=fake_whisper):
        out = transcription.transcribe_with_whisper(str(audio_path), settings, job=None)

    assert isinstance(out, dict), f"expected dict, got {type(out)}"
    assert "segments" in out and "text" in out and "language" in out
    assert captured.get("word_timestamps") is True
    assert captured.get("condition_on_previous_text") is False
    assert captured.get("logprob_threshold") == -1.0
