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
