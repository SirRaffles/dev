"""Tests for context folder management API endpoints (routes/contexts.py)."""

import pytest


@pytest.mark.asyncio
async def test_list_contexts_empty(client, icloud_base):
    """GET /contexts returns empty folders for a fresh contexts dir."""
    resp = await client.get("/contexts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_path"] == ""
    assert isinstance(data["folders"], list)
    assert isinstance(data["files"], list)


@pytest.mark.asyncio
async def test_get_context_tree(client, icloud_base):
    """GET /contexts/tree returns tree structure."""
    resp = await client.get("/contexts/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert "tree" in data
    assert data["tree"]["name"] == "contexts"


@pytest.mark.asyncio
async def test_create_folder(client, icloud_base):
    """POST /contexts/folders creates folder with _meta.json."""
    resp = await client.post(
        "/contexts/folders",
        json={"path": "test-client", "description": "A test context folder"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "test-client"
    assert data["created"] is True

    # Verify folder structure on disk
    folder = icloud_base / "contexts" / "test-client"
    assert folder.exists()
    assert (folder / "_meta.json").exists()
    assert (folder / "context.md").exists()


@pytest.mark.asyncio
async def test_create_folder_empty_path(client, icloud_base):
    """POST /contexts/folders with empty path returns 400."""
    resp = await client.post("/contexts/folders", json={"path": "  "})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_folder_duplicate(client, icloud_base):
    """POST /contexts/folders with existing path returns 409."""
    await client.post("/contexts/folders", json={"path": "dup-folder"})
    resp = await client.post("/contexts/folders", json={"path": "dup-folder"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_nested_folder(client, icloud_base):
    """POST /contexts/folders creates nested paths."""
    resp = await client.post(
        "/contexts/folders",
        json={"path": "clients/acme/q1", "description": "Acme Q1"},
    )
    assert resp.status_code == 200

    # Verify nested structure exists
    assert (icloud_base / "contexts" / "clients" / "acme" / "q1").exists()


@pytest.mark.asyncio
async def test_delete_folder(client, icloud_base):
    """DELETE /contexts/folders/{path} removes the folder."""
    await client.post("/contexts/folders", json={"path": "to-delete"})
    assert (icloud_base / "contexts" / "to-delete").exists()

    resp = await client.delete("/contexts/folders/to-delete")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
    assert not (icloud_base / "contexts" / "to-delete").exists()


@pytest.mark.asyncio
async def test_delete_folder_not_found(client, icloud_base):
    """DELETE /contexts/folders/{path} returns 404 for nonexistent folder."""
    resp = await client.delete("/contexts/folders/nonexistent-folder")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_read_context_file(client, icloud_base):
    """GET /contexts/files/{path} reads a markdown file."""
    # Create folder first (creates context.md)
    await client.post("/contexts/folders", json={"path": "read-test"})

    resp = await client.get("/contexts/files/read-test/context.md")
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert "read-test" in data["content"]  # Template includes folder name


@pytest.mark.asyncio
async def test_write_and_read_context_file(client, icloud_base):
    """PUT then GET /contexts/files/{path} roundtrip."""
    await client.post("/contexts/folders", json={"path": "write-test"})

    # Write
    content = "# Write Test\n\nImportant notes about this context."
    resp = await client.put(
        "/contexts/files/write-test/context.md",
        json={"content": content},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"

    # Read
    resp2 = await client.get("/contexts/files/write-test/context.md")
    assert resp2.status_code == 200
    assert resp2.json()["content"] == content


@pytest.mark.asyncio
async def test_read_file_not_found(client, icloud_base):
    """GET /contexts/files/{path} returns 404 for nonexistent file."""
    resp = await client.get("/contexts/files/nonexistent/file.md")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search_contexts(client, icloud_base):
    """GET /contexts/search?q=... finds matching content."""
    # Create folder and write searchable content
    await client.post("/contexts/folders", json={"path": "search-test"})
    await client.put(
        "/contexts/files/search-test/context.md",
        json={"content": "This context discusses machine learning algorithms."},
    )

    resp = await client.get("/contexts/search?q=machine learning")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) >= 1
    assert any("machine learning" in r["snippet"].lower() for r in data["results"])


@pytest.mark.asyncio
async def test_search_contexts_short_query(client, icloud_base):
    """GET /contexts/search with short query returns 400."""
    resp = await client.get("/contexts/search?q=x")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_subfolders(client, icloud_base):
    """GET /contexts?path=... lists subfolders at a specific path."""
    await client.post("/contexts/folders", json={"path": "parent/child1"})
    await client.post("/contexts/folders", json={"path": "parent/child2"})

    resp = await client.get("/contexts?path=parent")
    assert resp.status_code == 200
    data = resp.json()
    names = [f["name"] for f in data["folders"]]
    assert "child1" in names
    assert "child2" in names


@pytest.mark.asyncio
async def test_read_global_glossary_missing(client, icloud_base):
    resp = await client.get("/contexts/_global")
    assert resp.status_code == 200
    body = resp.json()
    assert body["content"] == ""
    assert body["exists"] is False


@pytest.mark.asyncio
async def test_write_then_read_global_glossary(client, icloud_base):
    body_md = "# Global Glossary\n\n## Active\n\nManukai\n"
    resp = await client.put("/contexts/_global", json={"content": body_md})
    assert resp.status_code == 200
    resp = await client.get("/contexts/_global")
    body = resp.json()
    assert body["exists"] is True
    assert "Manukai" in body["content"]
    assert "modified_at" in body


@pytest.mark.asyncio
async def test_write_global_glossary_atomic(client, icloud_base, tmp_path):
    """The .tmp file should not linger after a successful write."""
    await client.put("/contexts/_global", json={"content": "# Test\n"})
    contexts_dir = icloud_base / "contexts"
    tmp_files = list(contexts_dir.glob("*.tmp"))
    assert tmp_files == [], f"orphan tmp file(s): {tmp_files}"
