"""Deep persistence module: one thread-safe SQLite Database behind a small interface.

Collapses the per-store connection/locking/row-mapping boilerplate that used to be
copied across the five hand-rolled stores in ``job_models.py``. Each store keeps
only its table/SQL knowledge and delegates raw access to a shared ``Database``.

Interface:
    - ``connection()``  -> context-managed ``sqlite3.Connection`` (row_factory = Row),
      serialized by an internal lock, committed on clean exit, closed on exit.
    - ``query(sql, params)``      -> ``list[dict]``
    - ``query_one(sql, params)``  -> ``dict | None``
    - ``mutate(sql, params, *, commit=True)`` -> ``rowcount``
    - ``init_pragmas()``          -> apply WAL + perf pragmas once
"""

import sqlite3
import threading
from contextlib import contextmanager

# Pragmas copied verbatim from the original JobStore._init_db so behaviour is
# identical: WAL journaling, relaxed sync, in-memory temp, and 256 MiB mmap.
_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA mmap_size=268435456",
)


class Database:
    """Thread-safe, context-managed SQLite access for the store layer."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()

    @contextmanager
    def connection(self):
        """Yield a serialized connection; commit on clean exit, always close.

        ``check_same_thread=False`` because the app shares stores across a
        ThreadPoolExecutor. The internal lock serializes access so the shared
        path stays safe. On an exception inside the ``with`` block the commit is
        skipped (callers that relied on implicit rollback keep that semantics).
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    def query(self, sql, params=()):
        with self.connection() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def query_one(self, sql, params=()):
        with self.connection() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def mutate(self, sql, params=(), *, commit=True):
        with self.connection() as conn:
            cur = conn.execute(sql, params)
            return cur.rowcount

    def init_pragmas(self):
        with self.connection() as conn:
            for pragma in _PRAGMAS:
                conn.execute(pragma)
