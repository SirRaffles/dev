"""
Audio processing utilities: extraction and noise reduction.
"""

import subprocess

import numpy as np
import noisereduce as nr
from scipy.io import wavfile


def extract_audio(input_path: str, output_path: str) -> str:
    """Extract audio from video file using ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    return output_path


def apply_noise_reduction(audio_path: str, output_path: str) -> str:
    """Apply noise reduction to audio file using noisereduce library."""
    try:
        sample_rate, audio_data = wavfile.read(audio_path)

        if audio_data.dtype == np.int16:
            audio_data = audio_data.astype(np.float32) / 32768.0
        elif audio_data.dtype == np.int32:
            audio_data = audio_data.astype(np.float32) / 2147483648.0

        reduced_noise = nr.reduce_noise(y=audio_data, sr=sample_rate, prop_decrease=0.8)

        reduced_noise_int16 = (reduced_noise * 32768.0).astype(np.int16)

        wavfile.write(output_path, sample_rate, reduced_noise_int16)

        return output_path
    except Exception as e:
        raise RuntimeError(f"Noise reduction failed: {e}")


import logging
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger(__name__)

# Sentinel: load attempted and failed. None means "not yet attempted".
_SILERO_FAILED = object()
_SILERO_CACHE: Optional[Tuple[Any, Callable[..., list]]] = None


def _get_silero_model():
    """Lazily load silero-vad via torch.hub. Returns (model, get_speech_timestamps),
    None if not yet attempted, or _SILERO_FAILED if a prior attempt failed."""
    global _SILERO_CACHE
    if _SILERO_CACHE is _SILERO_FAILED:
        return None
    if _SILERO_CACHE is not None:
        return _SILERO_CACHE
    try:
        import torch
        model, utils = torch.hub.load(
            "snakers4/silero-vad",
            "silero_vad",
            trust_repo=True,
        )
        get_speech_timestamps = utils[0]
        _SILERO_CACHE = (model, get_speech_timestamps)
        return _SILERO_CACHE
    except Exception as exc:
        logger.warning("silero-vad unavailable, skipping leading-silence trim: %s", exc)
        _SILERO_CACHE = _SILERO_FAILED
        return None


def find_first_speech_offset(audio_path: str, min_silence_s: float = 0.5) -> float:
    """Return seconds of leading silence to trim before transcription.

    Returns 0.0 if:
      - silero-vad cannot be loaded,
      - the audio cannot be read,
      - no speech is detected at all,
      - or the detected leading silence is below `min_silence_s`.

    Never raises; all failures degrade to 0.0 with a logged warning.
    """
    try:
        loaded = _get_silero_model()
        if loaded is None:
            return 0.0
        model, get_speech_timestamps = loaded

        import soundfile as sf
        import numpy as np
        import torch

        audio_np, sample_rate = sf.read(audio_path, dtype="float32", always_2d=False)
        if audio_np.ndim > 1:
            audio_np = audio_np.mean(axis=1)
        if sample_rate != 16000:
            # silero expects 16 kHz; resample crudely via linear interpolation.
            ratio = 16000 / sample_rate
            new_len = int(len(audio_np) * ratio)
            audio_np = np.interp(
                np.linspace(0, len(audio_np) - 1, new_len),
                np.arange(len(audio_np)),
                audio_np,
            ).astype("float32")
            sample_rate = 16000

        tensor = torch.from_numpy(audio_np)
        timestamps = get_speech_timestamps(
            tensor,
            model,
            threshold=0.5,
            sampling_rate=sample_rate,
            min_silence_duration_ms=400,
        )
        if not timestamps:
            return 0.0
        first_start_s = timestamps[0]["start"] / sample_rate
        return first_start_s if first_start_s >= min_silence_s else 0.0
    except Exception as exc:
        logger.warning("VAD lead-silence detection failed: %s", exc)
        return 0.0
