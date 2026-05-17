"""Tests for the unified /recordings endpoint.

These verify the merge semantics:
 - direct-upload jobs (no JPR backing) show up tagged source="upload"
 - JPR-backed jobs are deduped (the JPR row wins; no double entry)
 - YouTube jobs are tagged source="youtube"
"""

import pytest

from job_models import TranscriptionJob


@pytest.mark.asyncio
async def test_list_recordings_merges_jpr_and_uploads(client, jpr_dir):
    """A direct-upload job with no JPR backing appears alongside JPR files."""
    import state

    job_id = "test-recordings-upload-1"
    job = TranscriptionJob(job_id)
    job.status = "completed"
    state.jobs.create(
        job,
        file_path="/tmp/uploaded.m4a",
        settings={"original_filename": "my_call.m4a"},
    )

    try:
        resp = await client.get("/recordings")
        assert resp.status_code == 200, resp.text
        body = resp.json()

        filenames = [r["filename"] for r in body["recordings"]]
        # The direct-upload entry must be present.
        assert "my_call.m4a" in filenames, f"upload not in merged list: {filenames}"

        upload_entry = next(r for r in body["recordings"] if r["filename"] == "my_call.m4a")
        assert upload_entry["source"] == "upload"
        assert upload_entry["job_id"] == job_id
        assert upload_entry["effective_status"] == "completed"

        # The JPR-side fixture file should also be present and tagged source="jpr".
        jpr_entry = next(
            (r for r in body["recordings"] if r["filename"] == "10-00-00.m4a"),
            None,
        )
        assert jpr_entry is not None, "JPR fixture file missing from merged list"
        assert jpr_entry["source"] == "jpr"
    finally:
        state.jobs.delete(job_id)


@pytest.mark.asyncio
async def test_list_recordings_dedupes_jpr_jobs(client, jpr_dir):
    """A job whose original_filename resolves under JPR_WATCH_PATH is dropped
    from the upload side — the JPR row is the single source of truth."""
    import state

    # The jpr_dir fixture creates JPR/2026-02-18/10-00-00.m4a. Seed a job
    # whose original_filename matches that JPR file.
    job_id = "test-recordings-jpr-backed-1"
    job = TranscriptionJob(job_id)
    job.status = "completed"
    state.jobs.create(
        job,
        file_path="/tmp/10-00-00.m4a",
        settings={"original_filename": "10-00-00.m4a"},
    )

    try:
        resp = await client.get("/recordings")
        assert resp.status_code == 200, resp.text
        body = resp.json()

        matches = [r for r in body["recordings"] if r["filename"] == "10-00-00.m4a"]
        assert len(matches) == 1, (
            f"expected 1 row for 10-00-00.m4a, got {len(matches)}: {matches}"
        )
        # The surviving row should be the JPR-tagged one.
        assert matches[0]["source"] == "jpr"
    finally:
        state.jobs.delete(job_id)


@pytest.mark.asyncio
async def test_list_recordings_tags_youtube(client, jpr_dir):
    """YouTube ingest jobs are tagged source='youtube'."""
    import state

    job_id = "test-recordings-youtube-1"
    job = TranscriptionJob(job_id)
    job.status = "completed"
    state.jobs.create(
        job,
        file_path=None,
        settings={"original_filename": "Some YouTube Title"},
        youtube_url="https://youtu.be/abc123",
    )

    try:
        resp = await client.get("/recordings")
        assert resp.status_code == 200, resp.text
        body = resp.json()

        yt_entry = next(
            (r for r in body["recordings"] if r["job_id"] == job_id),
            None,
        )
        assert yt_entry is not None, "YouTube job missing from merged list"
        assert yt_entry["source"] == "youtube"
    finally:
        state.jobs.delete(job_id)
