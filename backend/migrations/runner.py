"""
SQLite migration runner.

Reads numbered SQL files from the migrations/ directory and applies any
that haven't been recorded in schema_version. Migrations run in order
and are applied inside individual transactions.
"""

import os
import re
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent
_VERSION_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def _get_migration_files() -> list[tuple[int, Path]]:
    """Return sorted list of (version, path) tuples for all *.sql files."""
    pattern = re.compile(r"^(\d+)_.+\.sql$")
    files = []
    for path in _MIGRATIONS_DIR.glob("*.sql"):
        m = pattern.match(path.name)
        if m:
            files.append((int(m.group(1)), path))
    return sorted(files, key=lambda x: x[0])


def _get_applied_versions(conn: sqlite3.Connection) -> set[int]:
    cursor = conn.execute("SELECT version FROM schema_version")
    return {row[0] for row in cursor.fetchall()}


def run_migrations(db_path: str) -> None:
    """Apply all unapplied migrations to the database at db_path."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL")

        # Bootstrap: ensure schema_version exists before anything else
        conn.execute(_VERSION_TABLE_DDL)
        conn.commit()

        applied = _get_applied_versions(conn)
        migration_files = _get_migration_files()

        pending = [(v, p) for v, p in migration_files if v not in applied]
        if not pending:
            logger.info("Database schema is up to date (%d migrations applied)", len(applied))
            return

        for version, path in pending:
            sql = path.read_text(encoding="utf-8")
            logger.info("Applying migration %03d: %s", version, path.name)
            try:
                # Run the migration SQL; SQLite executescript auto-commits
                conn.executescript(sql)
                # Record the migration (executescript ends any open transaction)
                conn.execute(
                    "INSERT INTO schema_version (version, filename) VALUES (?, ?)",
                    (version, path.name),
                )
                conn.commit()
                logger.info("Migration %03d applied successfully", version)
            except Exception:
                logger.exception("Migration %03d failed: %s", version, path.name)
                raise

        logger.info("Applied %d migration(s); schema is now up to date", len(pending))
    finally:
        conn.close()
