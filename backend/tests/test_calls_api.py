"""Tests for call management API endpoints (routes/calls.py)."""

import pytest


@pytest.mark.asyncio
async def test_list_calls_empty(client):
    """GET /calls returns empty list initially."""
    resp = await client.get("/calls")
    assert resp.status_code == 200
    data = resp.json()
    assert "calls" in data
    assert "total" in data
    assert isinstance(data["calls"], list)


@pytest.mark.asyncio
async def test_register_call(client, sample_job, clean_calls):
    """POST /calls/{job_id}/register creates a call entry."""
    job_id = sample_job
    resp = await client.post(
        f"/calls/{job_id}/register",
        json={"source_type": "upload", "title": "Test Call"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    clean_calls.append(job_id)


@pytest.mark.asyncio
async def test_register_call_nonexistent_job(client):
    """POST /calls/{job_id}/register returns 404 for nonexistent job."""
    resp = await client.post(
        "/calls/nonexistent-job-id/register",
        json={"source_type": "upload"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_register_call_idempotent(client, sample_job, clean_calls):
    """POST /calls/{job_id}/register is idempotent — second call returns same data."""
    job_id = sample_job
    r1 = await client.post(f"/calls/{job_id}/register", json={"source_type": "test"})
    assert r1.status_code == 200
    clean_calls.append(job_id)

    r2 = await client.post(f"/calls/{job_id}/register", json={"source_type": "test"})
    assert r2.status_code == 200
    assert r2.json()["job_id"] == r1.json()["job_id"]


@pytest.mark.asyncio
async def test_get_call_detail(client, sample_job, clean_calls):
    """GET /calls/{job_id} returns call detail with readiness info."""
    job_id = sample_job
    await client.post(f"/calls/{job_id}/register", json={"source_type": "upload"})
    clean_calls.append(job_id)

    resp = await client.get(f"/calls/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "readiness" in data
    assert data["readiness"]["ready"] is False
    assert "speakers" in data["readiness"]["missing"]
    assert "context" in data["readiness"]["missing"]


@pytest.mark.asyncio
async def test_get_call_not_found(client):
    """GET /calls/{job_id} returns 404 for nonexistent call."""
    resp = await client.get("/calls/nonexistent-call-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_set_call_title(client, sample_job, clean_calls):
    """PUT /calls/{job_id}/title sets the title."""
    job_id = sample_job
    await client.post(f"/calls/{job_id}/register", json={"source_type": "upload"})
    clean_calls.append(job_id)

    resp = await client.put(f"/calls/{job_id}/title", json={"title": "Q1 Planning"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Q1 Planning"

    # Verify
    detail = await client.get(f"/calls/{job_id}")
    assert detail.json()["title"] == "Q1 Planning"


@pytest.mark.asyncio
async def test_set_title_not_found(client):
    """PUT /calls/{job_id}/title returns 404 for nonexistent call."""
    resp = await client.put("/calls/nonexistent-id/title", json={"title": "X"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_assign_context(client, sample_job, clean_calls):
    """PUT /calls/{job_id}/context assigns a context path."""
    job_id = sample_job
    await client.post(f"/calls/{job_id}/register", json={"source_type": "upload"})
    clean_calls.append(job_id)

    resp = await client.put(
        f"/calls/{job_id}/context",
        json={"context_path": "clients/acme"},
    )
    assert resp.status_code == 200
    assert resp.json()["context_path"] == "clients/acme"


@pytest.mark.asyncio
async def test_assign_context_not_found(client):
    """PUT /calls/{job_id}/context returns 404 for nonexistent call."""
    resp = await client.put(
        "/calls/nonexistent-id/context",
        json={"context_path": "test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_identify_speakers_not_found(client):
    """POST /calls/{job_id}/identify-speakers returns 404 for nonexistent call."""
    resp = await client.post("/calls/nonexistent-id/identify-speakers")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_confirm_speaker_not_found(client):
    """POST /calls/{job_id}/confirm-speaker returns 404 for nonexistent call."""
    resp = await client.post(
        "/calls/nonexistent-id/confirm-speaker",
        json={"speaker_label": "SPEAKER_00", "speaker_name": "Alice"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_deliverables_not_found(client):
    """POST /calls/{job_id}/generate-deliverables returns 404 for nonexistent call."""
    resp = await client.post("/calls/nonexistent-id/generate-deliverables")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_generate_deliverables_speakers_not_identified(client, sample_job, clean_calls):
    """POST /calls/{job_id}/generate-deliverables returns 400 when speakers not identified."""
    job_id = sample_job
    await client.post(f"/calls/{job_id}/register", json={"source_type": "upload"})
    clean_calls.append(job_id)

    resp = await client.post(f"/calls/{job_id}/generate-deliverables")
    # Should be 400 (speakers not identified) or 503 (claude not available)
    assert resp.status_code in (400, 503)


@pytest.mark.asyncio
async def test_get_deliverables_empty(client, sample_job, clean_calls):
    """GET /calls/{job_id}/deliverables returns not-generated when no deliverables exist."""
    job_id = sample_job
    await client.post(f"/calls/{job_id}/register", json={"source_type": "upload"})
    clean_calls.append(job_id)

    resp = await client.get(f"/calls/{job_id}/deliverables")
    assert resp.status_code == 200
    data = resp.json()
    assert data["generated"] is False


@pytest.mark.asyncio
async def test_list_calls_with_filter(client, sample_job, clean_calls):
    """GET /calls?status=... filters correctly."""
    job_id = sample_job
    await client.post(f"/calls/{job_id}/register", json={"source_type": "upload"})
    clean_calls.append(job_id)

    # With no filter, should include the new call
    all_resp = await client.get("/calls")
    assert all_resp.status_code == 200

    # Delivered filter should not include our new call
    delivered = await client.get("/calls?status=delivered")
    assert delivered.status_code == 200
    ids = [c["job_id"] for c in delivered.json()["calls"]]
    assert job_id not in ids


@pytest.mark.asyncio
async def test_call_lifecycle(client, sample_job, clean_calls):
    """Full lifecycle: register → title → context → detail → check readiness."""
    job_id = sample_job

    # Register
    r1 = await client.post(f"/calls/{job_id}/register", json={"source_type": "test"})
    assert r1.status_code == 200
    clean_calls.append(job_id)

    # Set title
    r2 = await client.put(f"/calls/{job_id}/title", json={"title": "Lifecycle Test"})
    assert r2.status_code == 200

    # Assign context
    r3 = await client.put(f"/calls/{job_id}/context", json={"context_path": "test/lifecycle"})
    assert r3.status_code == 200

    # Check detail
    r4 = await client.get(f"/calls/{job_id}")
    assert r4.status_code == 200
    data = r4.json()
    assert data["title"] == "Lifecycle Test"
    assert data["context_path"] == "test/lifecycle"
    assert data["context_assigned"] == 1
    # speakers still not identified
    assert data["speakers_identified"] == 0
    assert data["readiness"]["ready"] is False
    assert "speakers" in data["readiness"]["missing"]
    assert "context" not in data["readiness"]["missing"]
