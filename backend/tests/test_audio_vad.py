"""Unit tests for VAD leading-silence trim."""

from unittest.mock import patch, MagicMock

import numpy as np
import pytest


def _fake_silero_load(*_args, **_kwargs):
    """Return (model, utils) tuple shaped like silero-vad's torch.hub return."""
    model = MagicMock()
    get_speech_timestamps = MagicMock()
    # Default behavior: no speech found; tests override per-case.
    get_speech_timestamps.return_value = []
    # silero utils tuple: (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks)
    utils = (get_speech_timestamps, MagicMock(), MagicMock(), MagicMock(), MagicMock())
    return model, utils


def _write_wav(path, duration_s: float, sample_rate: int = 16000):
    import soundfile as sf
    samples = np.zeros(int(duration_s * sample_rate), dtype="float32")
    sf.write(str(path), samples, sample_rate, subtype="PCM_16")


def test_returns_zero_when_no_speech_detected(tmp_path):
    """If silero finds no speech, return 0.0 (caller falls back to raw audio)."""
    from services import audio

    wav = tmp_path / "silence.wav"
    _write_wav(wav, 5.0)

    audio._SILERO_CACHE = None
    with patch("torch.hub.load", side_effect=_fake_silero_load):
        offset = audio.find_first_speech_offset(str(wav))

    assert offset == 0.0


def test_returns_offset_when_leading_silence_exceeds_threshold(tmp_path):
    """If first speech begins at 5s, return ~5.0."""
    from services import audio

    wav = tmp_path / "lead.wav"
    _write_wav(wav, 10.0)

    def _load_with_speech(*_a, **_k):
        model, utils = _fake_silero_load()
        utils[0].return_value = [{"start": 5 * 16000, "end": 8 * 16000}]
        return model, utils

    audio._SILERO_CACHE = None
    with patch("torch.hub.load", side_effect=_load_with_speech):
        offset = audio.find_first_speech_offset(str(wav), min_silence_s=0.5)

    assert offset == pytest.approx(5.0, abs=0.05)


def test_returns_zero_when_lead_below_min_threshold(tmp_path):
    """Speech starts at 0.1s — below 0.5s threshold — return 0.0."""
    from services import audio

    wav = tmp_path / "short_lead.wav"
    _write_wav(wav, 10.0)

    def _load_with_short_lead(*_a, **_k):
        model, utils = _fake_silero_load()
        utils[0].return_value = [{"start": int(0.1 * 16000), "end": 8 * 16000}]
        return model, utils

    audio._SILERO_CACHE = None
    with patch("torch.hub.load", side_effect=_load_with_short_lead):
        offset = audio.find_first_speech_offset(str(wav), min_silence_s=0.5)

    assert offset == 0.0


def test_returns_zero_and_logs_when_silero_unavailable(tmp_path, caplog):
    """torch.hub.load failure must degrade gracefully to 0.0 (no exception)."""
    from services import audio

    wav = tmp_path / "any.wav"
    _write_wav(wav, 5.0)

    audio._SILERO_CACHE = None
    with patch("torch.hub.load", side_effect=RuntimeError("no network")):
        with caplog.at_level("WARNING"):
            offset = audio.find_first_speech_offset(str(wav))

    assert offset == 0.0
    assert any("silero" in r.message.lower() or "vad" in r.message.lower()
               for r in caplog.records)


def test_resample_branch_runs_for_non_16khz_input(tmp_path):
    """Audio at 8kHz must be resampled to 16kHz before silero is called; the
    detected offset is expressed in original-file seconds and within tolerance."""
    import soundfile as sf
    from services import audio

    wav = tmp_path / "8k.wav"
    samples = np.zeros(10 * 8000, dtype="float32")  # 10s of silence at 8 kHz
    sf.write(str(wav), samples, 8000, subtype="PCM_16")

    captured_kwargs = {}

    def _load_with_capture(*_a, **_k):
        model, utils = _fake_silero_load()
        def _capturing_gst(tensor, model, **kw):
            captured_kwargs.update(kw)
            captured_kwargs["tensor_len"] = len(tensor)
            return [{"start": 5 * 16000, "end": 8 * 16000}]
        utils = (_capturing_gst, MagicMock(), MagicMock(), MagicMock(), MagicMock())
        return model, utils

    audio._SILERO_CACHE = None
    with patch("torch.hub.load", side_effect=_load_with_capture):
        offset = audio.find_first_speech_offset(str(wav), min_silence_s=0.5)

    # After resample to 16 kHz, get_speech_timestamps was called with sampling_rate=16000.
    assert captured_kwargs.get("sampling_rate") == 16000
    # Tensor length must be ~160000 samples (10s × 16000) not 80000.
    assert abs(captured_kwargs.get("tensor_len", 0) - 160000) <= 1
    # Offset is computed against the (resampled) sample rate.
    assert offset == pytest.approx(5.0, abs=0.05)


def test_failed_load_is_not_retried(tmp_path):
    """After a failed load, subsequent calls must not retry torch.hub.load."""
    from services import audio

    wav = tmp_path / "any.wav"
    _write_wav(wav, 5.0)

    audio._SILERO_CACHE = None
    mock_loader = MagicMock(side_effect=RuntimeError("no network"))
    with patch("torch.hub.load", mock_loader):
        audio.find_first_speech_offset(str(wav))
        audio.find_first_speech_offset(str(wav))

    # Only the FIRST call should have invoked torch.hub.load.
    assert mock_loader.call_count == 1


def test_make_trimmed_audio_writes_offset_slice(tmp_path):
    """Trimmed file starts at `offset` seconds and is shorter by that amount."""
    import soundfile as sf
    from services import audio

    sr = 16000
    full = np.linspace(0, 1, 10 * sr, dtype="float32")  # 10s ramp 0→1
    src = tmp_path / "src.wav"
    sf.write(str(src), full, sr, subtype="PCM_16")

    out = audio.make_trimmed_audio(str(src), trim_offset=2.5)
    assert out != str(src)

    audio_out, sr_out = sf.read(out, dtype="float32")
    assert sr_out == sr
    expected_len = 10 * sr - int(2.5 * sr)
    assert abs(len(audio_out) - expected_len) <= 1
    # First sample of the trimmed file equals the original at t=2.5s (within fp noise).
    assert audio_out[0] == pytest.approx(full[int(2.5 * sr)], abs=1e-3)
