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


@pytest.mark.asyncio
async def test_rename_job_source_renames_jpr_file(client, jpr_dir):
    """Happy path: rename the JPR file + persist new name in settings."""
    import state
    from job_models import TranscriptionJob

    # Seed a fake job with original_filename matching a JPR file.
    job = TranscriptionJob("job-rn-1")
    job.status = "completed"
    state.jobs.create(job, file_path="/tmp/x.m4a",
                      settings={"original_filename": "10-00-00.m4a"})

    resp = await client.post("/jpr/job/job-rn-1/rename",
                             json={"new_name": "Pascal Weber call"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["old_name"] == "10-00-00.m4a"
    assert body["new_name"] == "Pascal Weber call.m4a"

    # Verify the file actually got renamed on disk
    new_path = jpr_dir / "2026-02-18" / "Pascal Weber call.m4a"
    assert new_path.exists()
    old_path = jpr_dir / "2026-02-18" / "10-00-00.m4a"
    assert not old_path.exists()

    # Verify settings updated
    meta = state.jobs.get_job_meta("job-rn-1")
    assert meta["settings"]["original_filename"] == "Pascal Weber call.m4a"

    # Cleanup
    state.jobs.delete("job-rn-1")


@pytest.mark.asyncio
async def test_rename_job_source_rejects_path_traversal(client, jpr_dir):
    import state
    from job_models import TranscriptionJob

    job = TranscriptionJob("job-rn-trav")
    job.status = "completed"
    state.jobs.create(job, file_path="/tmp/x.m4a",
                      settings={"original_filename": "10-00-00.m4a"})

    for bad in ["../escape.m4a", "/etc/passwd", ".hidden.m4a", ""]:
        resp = await client.post("/jpr/job/job-rn-trav/rename",
                                 json={"new_name": bad})
        assert resp.status_code == 400, f"expected 400 for {bad!r}"

    state.jobs.delete("job-rn-trav")


@pytest.mark.asyncio
async def test_rename_job_source_handles_conflict_with_suffix(client, jpr_dir):
    import state
    from job_models import TranscriptionJob

    # Pre-create a file that will collide.
    (jpr_dir / "2026-02-18" / "Pascal call.m4a").write_bytes(b"\x00")
    (jpr_dir / "2026-02-18" / "10-01-00.m4a").write_bytes(b"\x00")

    job = TranscriptionJob("job-rn-conf")
    job.status = "completed"
    state.jobs.create(job, file_path="/tmp/x.m4a",
                      settings={"original_filename": "10-01-00.m4a"})

    resp = await client.post("/jpr/job/job-rn-conf/rename",
                             json={"new_name": "Pascal call"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["new_name"] == "Pascal call (2).m4a"
    assert (jpr_dir / "2026-02-18" / "Pascal call (2).m4a").exists()

    state.jobs.delete("job-rn-conf")
