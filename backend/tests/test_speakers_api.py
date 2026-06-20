"""Tests for speaker management API endpoints (routes/speakers.py)."""

import pytest


@pytest.mark.asyncio
async def test_list_speakers_empty(client):
    """GET /speakers returns empty list when no speakers exist."""
    resp = await client.get("/speakers")
    assert resp.status_code == 200
    data = resp.json()
    assert "speakers" in data
    assert isinstance(data["speakers"], list)


@pytest.mark.asyncio
async def test_create_speaker(client, icloud_base, clean_speakers):
    """POST /speakers creates a new speaker and returns its data."""
    resp = await client.post("/speakers", json={"name": "Alice Test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Alice Test"
    assert "speaker_id" in data
    clean_speakers.append(data["speaker_id"])

    # Verify folder was scaffolded on iCloud with the 4-part profile.
    speaker_dir = icloud_base / "speakers" / "Alice Test"
    assert speaker_dir.exists()
    assert (speaker_dir / "profile.json").exists()         # metadata
    assert (speaker_dir / "profile.md").exists()           # bio (human-edited)
    assert (speaker_dir / "explicit_insights.md").exists() # LLM-generated
    assert (speaker_dir / "implicit_insights.md").exists() # LLM-generated


@pytest.mark.asyncio
async def test_create_speaker_empty_name(client, icloud_base):
    """POST /speakers with empty name returns 400."""
    resp = await client.post("/speakers", json={"name": "  "})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_speaker_duplicate(client, icloud_base, clean_speakers):
    """POST /speakers with duplicate name returns 409."""
    resp1 = await client.post("/speakers", json={"name": "DupTest"})
    assert resp1.status_code == 200
    clean_speakers.append(resp1.json()["speaker_id"])

    resp2 = await client.post("/speakers", json={"name": "DupTest"})
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_get_speaker(client, icloud_base, clean_speakers):
    """GET /speakers/{id} returns speaker detail with personality."""
    create = await client.post("/speakers", json={"name": "DetailTest"})
    sid = create.json()["speaker_id"]
    clean_speakers.append(sid)

    resp = await client.get(f"/speakers/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "DetailTest"
    assert "personality_md" in data
    assert "calls" in data
    assert "has_embedding" in data


@pytest.mark.asyncio
async def test_get_speaker_not_found(client):
    """GET /speakers/{id} returns 404 for nonexistent speaker."""
    resp = await client.get("/speakers/nonexistent-id-000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_speaker_rename(client, icloud_base, clean_speakers):
    """PUT /speakers/{id} renames speaker and folder."""
    create = await client.post("/speakers", json={"name": "OldName"})
    sid = create.json()["speaker_id"]
    clean_speakers.append(sid)

    resp = await client.put(f"/speakers/{sid}", json={"name": "NewName"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "updated"

    # Verify get returns new name
    detail = await client.get(f"/speakers/{sid}")
    assert detail.json()["name"] == "NewName"


@pytest.mark.asyncio
async def test_update_speaker_not_found(client):
    """PUT /speakers/{id} returns 404 for nonexistent speaker."""
    resp = await client.put("/speakers/nonexistent-id", json={"name": "X"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_speaker(client, icloud_base, clean_speakers):
    """DELETE /speakers/{id} removes speaker from DB and filesystem."""
    create = await client.post("/speakers", json={"name": "DeleteMe"})
    sid = create.json()["speaker_id"]

    resp = await client.delete(f"/speakers/{sid}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Verify gone
    detail = await client.get(f"/speakers/{sid}")
    assert detail.status_code == 404


@pytest.mark.asyncio
async def test_delete_speaker_not_found(client):
    """DELETE /speakers/{id} returns 404 for nonexistent speaker."""
    resp = await client.delete("/speakers/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_personality(client, icloud_base, clean_speakers):
    """GET /speakers/{id}/personality is a legacy alias returning the
    implicit-insights section content."""
    create = await client.post("/speakers", json={"name": "PersonalityGet"})
    sid = create.json()["speaker_id"]
    clean_speakers.append(sid)

    resp = await client.get(f"/speakers/{sid}/personality")
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    # Default scaffold for a fresh speaker surfaces the "Implicit insights" header.
    assert "Implicit insights" in data["content"]


@pytest.mark.asyncio
async def test_update_personality(client, icloud_base, clean_speakers):
    """PUT /speakers/{id}/personality writes new content."""
    create = await client.post("/speakers", json={"name": "PersonalityPut"})
    sid = create.json()["speaker_id"]
    clean_speakers.append(sid)

    new_content = "# PersonalityPut\n\nVery friendly and detail-oriented."
    resp = await client.put(
        f"/speakers/{sid}/personality",
        json={"content": new_content},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"

    # Verify roundtrip
    get_resp = await client.get(f"/speakers/{sid}/personality")
    assert get_resp.json()["content"] == new_content


@pytest.mark.asyncio
async def test_update_personality_not_found(client):
    """PUT /speakers/{id}/personality returns 404 for nonexistent speaker."""
    resp = await client.put(
        "/speakers/nonexistent-id/personality",
        json={"content": "test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_speaker_full_lifecycle(client, icloud_base, clean_speakers):
    """Full lifecycle: create → get → update personality → read personality → list → delete → verify gone."""
    # Create
    r1 = await client.post("/speakers", json={"name": "LifecycleTest"})
    assert r1.status_code == 200
    sid = r1.json()["speaker_id"]

    # Get detail
    r2 = await client.get(f"/speakers/{sid}")
    assert r2.status_code == 200
    assert r2.json()["name"] == "LifecycleTest"

    # Update personality
    r3 = await client.put(f"/speakers/{sid}/personality", json={"content": "# LifecycleTest\n\nUpdated."})
    assert r3.status_code == 200

    # Read personality
    r4 = await client.get(f"/speakers/{sid}/personality")
    assert "Updated." in r4.json()["content"]

    # List speakers
    r5 = await client.get("/speakers")
    names = [s["name"] for s in r5.json()["speakers"]]
    assert "LifecycleTest" in names

    # Delete
    r6 = await client.delete(f"/speakers/{sid}")
    assert r6.status_code == 200

    # Verify gone
    r7 = await client.get(f"/speakers/{sid}")
    assert r7.status_code == 404


@pytest.mark.asyncio
async def test_speaker_embedding_upload_returns_501(client, icloud_base, clean_speakers):
    """POST /speakers/{id}/embedding returns 501 (not yet implemented)."""
    create = await client.post("/speakers", json={"name": "EmbedTest"})
    sid = create.json()["speaker_id"]
    clean_speakers.append(sid)

    resp = await client.post(f"/speakers/{sid}/embedding")
    assert resp.status_code == 501
