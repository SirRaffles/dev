"""Tests for JobStore SQLite storage."""

import os
import tempfile
import sqlite3

from job_models import TranscriptionJob, JobStore


def test_job_store_crud():
    """Test create, get, update, delete lifecycle."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        store = JobStore(db_path)
        job = TranscriptionJob("test-123")
        store.create(job)

        retrieved = store.get("test-123")
        assert retrieved is not None
        assert retrieved.status == "pending"

        retrieved.status = "completed"
        retrieved.result = {"text": "hello world"}
        store.update(retrieved)

        updated = store.get("test-123")
        assert updated.status == "completed"
        assert updated.result == {"text": "hello world"}

        store.delete("test-123")
        assert store.get("test-123") is None
    finally:
        os.unlink(db_path)


def test_wal_mode_enabled():
    """Verify WAL journal mode is set on initialization."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        JobStore(db_path)
        conn = sqlite3.connect(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"
    finally:
        os.unlink(db_path)


def test_job_store_contains():
    """Test __contains__ operator."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        store = JobStore(db_path)
        assert "nonexistent" not in store

        job = TranscriptionJob("exists-456")
        store.create(job)
        assert "exists-456" in store
    finally:
        os.unlink(db_path)
