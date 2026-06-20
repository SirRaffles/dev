"""Tests for the deep Database persistence module."""

import sqlite3

from persistence.database import Database


def test_query_and_mutate_roundtrip(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    with db.connection() as conn:
        conn.execute("CREATE TABLE t (id TEXT PRIMARY KEY, n INTEGER)")
    n = db.mutate("INSERT INTO t (id, n) VALUES (?, ?)", ("a", 1))
    assert n == 1
    row = db.query_one("SELECT * FROM t WHERE id = ?", ("a",))
    assert row == {"id": "a", "n": 1}
    rows = db.query("SELECT * FROM t")
    assert rows == [{"id": "a", "n": 1}]


def test_connection_uses_row_factory(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    with db.connection() as conn:
        assert conn.row_factory is sqlite3.Row
