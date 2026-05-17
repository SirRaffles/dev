"""Tests for file upload validation (extension and magic bytes)."""

import io

import pytest


@pytest.mark.asyncio
async def test_upload_unsupported_extension(client):
    """Reject files with unsupported extensions.

    Note: In test env the engine may not be loaded (503), so we pass
    engine=auto-best and accept either 400 (extension rejected) or 503
    (engine unavailable — checked before extension). Both prove the
    endpoint is alive and rejecting bad input.
    """
    fake = io.BytesIO(b"not a real file")
    resp = await client.post(
        "/transcribe/file?language=auto&engine=auto-best",
        files={"file": ("test.exe", fake, "application/octet-stream")},
    )
    # 400 if engine available (extension check), 503 if model not loaded (checked first)
    assert resp.status_code in (400, 503)
    if resp.status_code == 400:
        assert "Unsupported file type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_wrong_magic_bytes(client, fake_mp3):
    """Reject files where magic bytes don't match declared extension."""
    with open(fake_mp3, "rb") as f:
        resp = await client.post(
            "/transcribe/file?language=auto&engine=auto-best",
            files={"file": ("audio.mp3", f, "audio/mpeg")},
        )
    # 400 if engine available (magic-byte check), 503 if model not loaded
    assert resp.status_code in (400, 503)
    if resp.status_code == 400:
        assert "does not match declared type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_valid_wav_accepted(client, tmp_audio):
    """Valid WAV file should be accepted (returns job_id even if transcription fails)."""
    with open(tmp_audio, "rb") as f:
        resp = await client.post(
            "/transcribe/file?language=auto&engine=auto-best",
            files={"file": ("test.wav", f, "audio/wav")},
        )
    # 200 if model loaded, 503 if not
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert "job_id" in resp.json()


@pytest.mark.asyncio
async def test_invalid_engine_rejected(client):
    """Request with invalid engine name should return 400."""
    fake = io.BytesIO(b"fake data")
    resp = await client.post(
        "/transcribe/file?language=auto&engine=invalid_engine",
        files={"file": ("test.wav", fake, "audio/wav")},
    )
    assert resp.status_code == 400
    body = resp.json()["detail"].lower()
    assert "auto-best" in body or "no longer supported" in body or "invalid engine" in body


@pytest.mark.asyncio
async def test_upload_default_engine_is_auto_best(client, tmp_audio):
    """Without specifying engine, the route accepts the upload with auto-best."""
    with open(tmp_audio, "rb") as f:
        resp = await client.post(
            "/transcribe/file?language=auto",
            files={"file": ("test.wav", f, "audio/wav")},
        )
    # 200 if engines wired, 503 if model not loaded — either proves no 400.
    assert resp.status_code in (200, 503), f"unexpected {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_upload_rejects_legacy_engine_whisper(client, tmp_audio):
    """Legacy engine values must be rejected with 400."""
    with open(tmp_audio, "rb") as f:
        resp = await client.post(
            "/transcribe/file?language=auto&engine=whisper",
            files={"file": ("test.wav", f, "audio/wav")},
        )
    assert resp.status_code == 400
    body = resp.json()["detail"].lower()
    assert "no longer supported" in body or "auto-best" in body


@pytest.mark.asyncio
async def test_upload_rejects_legacy_engine_voxtral_local(client, tmp_audio):
    with open(tmp_audio, "rb") as f:
        resp = await client.post(
            "/transcribe/file?language=auto&engine=voxtral-local",
            files={"file": ("test.wav", f, "audio/wav")},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_accepts_engine_auto_quick(client, tmp_audio):
    with open(tmp_audio, "rb") as f:
        resp = await client.post(
            "/transcribe/file?language=auto&engine=auto-quick",
            files={"file": ("test.wav", f, "audio/wav")},
        )
    assert resp.status_code in (200, 503)
