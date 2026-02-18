"""Shared test fixtures."""

import json
import os
import tempfile
import uuid

import pytest
import pytest_asyncio
import httpx


@pytest.fixture(scope="session", autouse=True)
def _patch_env():
    """Ensure tests don't affect production database or require GPU."""
    os.environ.setdefault("LOG_FILE", os.path.join(tempfile.gettempdir(), "whisper_test.log"))


@pytest.fixture
def icloud_base(tmp_path, monkeypatch):
    """Create a temp iCloud-like directory and patch all paths to use it."""
    base = tmp_path / "icloud"
    base.mkdir()
    (base / "speakers").mkdir()
    (base / "contexts").mkdir()
    (base / "calls").mkdir()

    import config
    monkeypatch.setattr(config, "ICLOUD_BASE_PATH", base)

    # Also patch the module-level SPEAKERS_DIR / CONTEXTS_DIR / ICLOUD_BASE_PATH in routes
    import routes.speakers as rs
    import routes.contexts as rc
    monkeypatch.setattr(rs, "SPEAKERS_DIR", base / "speakers")
    monkeypatch.setattr(rs, "ICLOUD_BASE_PATH", base)
    monkeypatch.setattr(rc, "CONTEXTS_DIR", base / "contexts")

    return base


@pytest.fixture
def jpr_dir(tmp_path, monkeypatch):
    """Create a temp JPR directory with fake recordings."""
    jpr = tmp_path / "jpr"
    jpr.mkdir()

    # Create a fake .m4a file
    date_dir = jpr / "2026-02-18"
    date_dir.mkdir()
    fake_audio = date_dir / "10-00-00.m4a"
    fake_audio.write_bytes(b"\x00" * 1024)  # 1KB fake file

    # Create a state file
    state_file = tmp_path / "watcher_state.json"
    state_file.write_text("{}", encoding="utf-8")

    import config
    monkeypatch.setattr(config, "JPR_WATCH_PATH", jpr)
    monkeypatch.setattr(config, "JPR_STATE_FILE", state_file)

    # Also patch the route-level imports
    import routes.jpr as rj
    monkeypatch.setattr(rj, "JPR_WATCH_PATH", jpr)
    monkeypatch.setattr(rj, "JPR_STATE_FILE", state_file)

    return jpr


@pytest.fixture
def sample_job():
    """Insert a completed job into the job store and return its job_id."""
    import state
    from job_models import TranscriptionJob
    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    job.status = "completed"
    job.progress = 100
    job.progress_message = "Done"
    job.language = "en"
    state.job_store.create(job)
    yield job_id
    # Cleanup
    state.job_store.delete(job_id)


@pytest.fixture
def clean_speakers():
    """Fixture that cleans up any speakers created during a test."""
    import state
    created_ids = []
    yield created_ids
    for sid in created_ids:
        state.speaker_store.delete(sid)


@pytest.fixture
def clean_calls():
    """Fixture that cleans up any call_metadata created during a test."""
    import state
    created_ids = []
    yield created_ids
    for jid in created_ids:
        state.call_metadata_store.delete(jid)
        state.call_speaker_store.delete_for_call(jid)


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
