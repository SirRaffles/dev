"""Shared test fixtures."""

import os
import tempfile

import pytest
import pytest_asyncio
import httpx


@pytest.fixture(scope="session", autouse=True)
def _patch_env():
    """Ensure tests don't affect production database or require GPU."""
    os.environ.setdefault("LOG_FILE", os.path.join(tempfile.gettempdir(), "whisper_test.log"))


@pytest_asyncio.fixture
async def client():
    """Create an async test client against the real app."""
    from main import app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def tmp_audio(tmp_path):
    """Create a minimal valid WAV file for upload testing."""
    import struct
    wav_path = tmp_path / "test.wav"
    # Minimal WAV: RIFF header + fmt chunk + data chunk (1 second of silence)
    sample_rate = 8000
    num_samples = 8000
    data_size = num_samples * 2  # 16-bit mono
    fmt_chunk = struct.pack('<4sIHHIIHH',
        b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    data_chunk = struct.pack('<4sI', b'data', data_size) + b'\x00' * data_size
    riff_size = 4 + len(fmt_chunk) + len(data_chunk)
    header = struct.pack('<4sI4s', b'RIFF', riff_size, b'WAVE')
    wav_path.write_bytes(header + fmt_chunk + data_chunk)
    return wav_path


@pytest.fixture
def fake_mp3(tmp_path):
    """Create a file with .mp3 extension but wrong magic bytes."""
    bad = tmp_path / "fake.mp3"
    bad.write_bytes(b"this is not an mp3 file at all")
    return bad
