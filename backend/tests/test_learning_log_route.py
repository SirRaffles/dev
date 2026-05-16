"""B7 endpoint tests: GET /learning/log."""

import importlib
import json
import pytest


def _seed_log(icloud_base, entries):
    """Seed the log file AND reload services.learning so the endpoint
    reads the patched ICLOUD_BASE_PATH (constant is captured at import time
    via the per-request `learning.LEARNING_LOG_PATH` lookup in routes/learning.py)."""
    log = icloud_base / "learning_log.jsonl"
    with log.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")
    import services.learning
    importlib.reload(services.learning)


@pytest.fixture(autouse=True)
def _reload_learning_module(icloud_base):
    """Ensure services.learning reflects whichever ICLOUD_BASE_PATH the test
    fixtures patched. Depends on icloud_base so the monkeypatch is applied
    BEFORE we reload (otherwise LEARNING_LOG_PATH stays pointed at the
    production iCloud path captured at module import time)."""
    import services.learning
    importlib.reload(services.learning)
    yield
    importlib.reload(services.learning)


@pytest.mark.asyncio
async def test_learning_log_returns_recent_entries(client, icloud_base):
    _seed_log(icloud_base, [
        {"ts": "2026-05-15T10:00:00Z", "type": "embedding_update", "job_id": "j-1", "speaker_name": "Pascal"},
        {"ts": "2026-05-15T11:00:00Z", "type": "glossary_add", "job_id": "j-1", "term": "Manukai"},
        {"ts": "2026-05-15T12:00:00Z", "type": "insight_added", "job_id": "j-1", "speaker_name": "David", "category": "explicit", "count": 1},
    ])

    resp = await client.get("/learning/log")
    assert resp.status_code == 200
    body = resp.json()
    assert "events" in body
    assert "total" in body
    assert body["total"] == 3
    # Default order: most recent first
    assert body["events"][0]["type"] == "insight_added"
    assert body["events"][-1]["type"] == "embedding_update"


@pytest.mark.asyncio
async def test_learning_log_filter_by_type(client, icloud_base):
    _seed_log(icloud_base, [
        {"ts": "2026-05-15T10:00:00Z", "type": "embedding_update", "job_id": "j-1"},
        {"ts": "2026-05-15T11:00:00Z", "type": "glossary_add", "job_id": "j-1", "term": "X"},
        {"ts": "2026-05-15T12:00:00Z", "type": "embedding_update", "job_id": "j-2"},
    ])
    resp = await client.get("/learning/log?type=embedding_update")
    body = resp.json()
    assert body["total"] == 2
    assert all(e["type"] == "embedding_update" for e in body["events"])


@pytest.mark.asyncio
async def test_learning_log_filter_by_since(client, icloud_base):
    _seed_log(icloud_base, [
        {"ts": "2026-05-14T10:00:00Z", "type": "embedding_update", "job_id": "old"},
        {"ts": "2026-05-15T10:00:00Z", "type": "glossary_add", "job_id": "new", "term": "X"},
    ])
    resp = await client.get("/learning/log?since=2026-05-15T00:00:00Z")
    body = resp.json()
    assert body["total"] == 1
    assert body["events"][0]["job_id"] == "new"


@pytest.mark.asyncio
async def test_learning_log_pagination(client, icloud_base):
    _seed_log(icloud_base, [
        {"ts": f"2026-05-15T10:00:{i:02d}Z", "type": "glossary_add", "job_id": f"j-{i}", "term": f"T{i}"}
        for i in range(10)
    ])
    resp = await client.get("/learning/log?limit=3&offset=2")
    body = resp.json()
    assert len(body["events"]) == 3
    # offset=2 starts at the 3rd most-recent event
    assert body["events"][0]["job_id"] == "j-7"  # 0-indexed from end: j-9 (offset 0), j-8 (1), j-7 (2)


@pytest.mark.asyncio
async def test_learning_log_missing_file_returns_empty(client, icloud_base):
    # Don't seed any log file
    resp = await client.get("/learning/log")
    assert resp.status_code == 200
    body = resp.json()
    assert body["events"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_learning_log_rejects_oversize_limit(client, icloud_base):
    """limit > 500 must be clamped or rejected."""
    resp = await client.get("/learning/log?limit=10000")
    # Either 400 or auto-clamped to 500 — both acceptable; check it doesn't OOM
    assert resp.status_code in (200, 400, 422)
