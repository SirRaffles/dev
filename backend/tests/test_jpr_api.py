"""Tests for JPR file management API endpoints (routes/jpr.py)."""

import pytest


@pytest.mark.asyncio
async def test_list_recordings(client, jpr_dir):
    """GET /jpr/recordings returns recording list with watcher_status."""
    resp = await client.get("/jpr/recordings")
    assert resp.status_code == 200
    data = resp.json()
    assert "recordings" in data
    assert "total" in data
    assert "watcher_status" in data
    assert data["watcher_status"]["available"] is True


@pytest.mark.asyncio
async def test_list_recordings_finds_m4a(client, jpr_dir):
    """GET /jpr/recordings includes the fake .m4a file from the fixture."""
    resp = await client.get("/jpr/recordings")
    assert resp.status_code == 200
    data = resp.json()
    filenames = [r["filename"] for r in data["recordings"]]
    assert "10-00-00.m4a" in filenames


@pytest.mark.asyncio
async def test_get_recording(client, jpr_dir):
    """GET /jpr/recordings/{path} returns detail for an existing recording."""
    resp = await client.get("/jpr/recordings/2026-02-18/10-00-00.m4a")
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "10-00-00.m4a"
    assert data["size_bytes"] == 1024
    assert "status" in data


@pytest.mark.asyncio
async def test_get_recording_not_found(client, jpr_dir):
    """GET /jpr/recordings/{path} returns 404 for nonexistent file."""
    resp = await client.get("/jpr/recordings/2026-01-01/missing.m4a")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reprocess_recording(client, jpr_dir):
    """POST /jpr/recordings/{path}/reprocess returns status for existing file."""
    resp = await client.post("/jpr/recordings/2026-02-18/10-00-00.m4a/reprocess")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("queued", "not_tracked")


@pytest.mark.asyncio
async def test_reprocess_not_found(client, jpr_dir):
    """POST /jpr/recordings/{path}/reprocess returns 404 for missing file."""
    resp = await client.post("/jpr/recordings/missing/file.m4a/reprocess")
    assert resp.status_code == 404
