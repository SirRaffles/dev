"""Smoke tests for API health and basic endpoints."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("healthy", "degraded")


@pytest.mark.asyncio
async def test_models_endpoint(client):
    resp = await client.get("/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert "default" in data


@pytest.mark.asyncio
async def test_nonexistent_job_returns_404(client):
    resp = await client.get("/job/nonexistent-job-id-000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_docs_accessible(client):
    resp = await client.get("/docs")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_openapi_json(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["info"]["title"] == "Transcription API"
