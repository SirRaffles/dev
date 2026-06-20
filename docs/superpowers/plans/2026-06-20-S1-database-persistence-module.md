# S1 — Deep Database Persistence Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the five hand-rolled SQLite stores in `backend/job_models.py` behind one deep `Database` module with a small interface (`connection()` / `query` / `query_one` / `mutate`), so connection, locking, WAL pragma and row-mapping live in one place.

**Architecture:** Introduce `backend/persistence/database.py` exposing a thread-safe, context-managed connection plus query helpers. Each of the five stores (`JobStore`, `RefinementStore`, `SpeakerStore`, `CallSpeakerStore`, `CallMetadataStore`) is migrated to receive a `Database` instance and keep only its table/SQL knowledge. No behaviour change: same tables, same rows, same public store methods.

**Tech Stack:** Python 3, stdlib `sqlite3`, `threading`, `contextlib`; pytest + pytest-asyncio + pytest-timeout.

## Global Constraints

- Run all backend tests from the `backend/` directory: `python -m pytest tests/ -v --timeout=60`.
- WAL + pragma settings must remain identical to today (`journal_mode=WAL`, `synchronous=NORMAL`, etc. — copy verbatim from current `JobStore._init_db`).
- Connections must stay `check_same_thread=False` (the app uses a ThreadPoolExecutor).
- Public store method signatures (`get`, `create`, `update`, `list_*`, `delete*`, `__contains__`, etc.) MUST NOT change — only their internals.
- Schema ownership stays with `backend/migrations/runner.py`. Do not move migrations into the Database module. Defensive in-code `CREATE TABLE IF NOT EXISTS` that currently lives in `JobStore`/`RefinementStore` may stay or move to the store, but must not duplicate into the Database module.
- No new third-party dependency.

---

### Task 1: The Database module (interface + connection)

**Files:**
- Create: `backend/persistence/__init__.py`
- Create: `backend/persistence/database.py`
- Test: `backend/tests/test_database.py`

**Interfaces:**
- Produces:
  - `class Database(db_path: str)`
  - `Database.connection() -> contextmanager[sqlite3.Connection]` — yields a connection with `row_factory = sqlite3.Row`, serialized by an internal lock, closed on exit.
  - `Database.query(sql: str, params: tuple = ()) -> list[dict]`
  - `Database.query_one(sql: str, params: tuple = ()) -> dict | None`
  - `Database.mutate(sql: str, params: tuple = (), *, commit: bool = True) -> int` (returns `rowcount`)
  - `Database.init_pragmas() -> None` (applies WAL + pragmas once)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_database.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python -m pytest tests/test_database.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'persistence'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/persistence/database.py
import sqlite3
import threading
from contextlib import contextmanager

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()

    @contextmanager
    def connection(self):
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
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")
```

> NOTE for implementer: copy the EXACT pragma list from the current `JobStore._init_db` in `backend/job_models.py`. The three above are a placeholder — match production verbatim.

`backend/persistence/__init__.py`:
```python
from .database import Database

__all__ = ["Database"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_database.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/persistence backend/tests/test_database.py
git commit -m "feat(persistence): add deep Database module with connection/query/mutate"
```

---

### Task 2: Characterization tests for the five stores (safety net before migration)

**Files:**
- Modify: `backend/tests/test_stores.py`, `backend/tests/test_job_store.py`
- Create: `backend/tests/test_refinement_store.py` (RefinementStore is currently untested — close the gap FIRST)

**Interfaces:**
- Consumes: existing store classes from `backend/job_models.py` (unchanged at this point).

- [ ] **Step 1: Read `backend/job_models.py`** and enumerate every public method of `RefinementStore` (create/update_status/get/list, exact names + signatures). Read `migrations/*.sql` for the `refinements` table shape.

- [ ] **Step 2: Write failing characterization tests for RefinementStore**

```python
# backend/tests/test_refinement_store.py
from job_models import RefinementStore
from migrations.runner import run_migrations

def _store(tmp_path):
    db_path = str(tmp_path / "refine.db")
    run_migrations(db_path)
    return RefinementStore(db_path)

def test_refinement_create_and_get(tmp_path):
    s = _store(tmp_path)
    # Use the REAL method names discovered in Step 1; adjust below to match.
    s.create("job1")
    s.update_status("job1", "completed", None)
    got = s.get("job1")
    assert got["status"] == "completed"
```

> Adjust method names/params to the REAL RefinementStore API found in Step 1. Do not invent fields.

- [ ] **Step 3: Run to verify behaviour (these should PASS against current code — they pin existing behaviour)**

Run: `python -m pytest tests/test_refinement_store.py -v`
Expected: PASS. If a method name is wrong, fix the test to match the real API (these are characterization tests, not red TDD).

- [ ] **Step 4: Confirm existing store suites still pass**

Run: `python -m pytest tests/test_stores.py tests/test_job_store.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_refinement_store.py
git commit -m "test(stores): characterize RefinementStore before persistence migration"
```

---

### Task 3: Migrate the four simple stores onto Database

**Files:**
- Modify: `backend/job_models.py` (`SpeakerStore`, `CallSpeakerStore`, `CallMetadataStore`, `RefinementStore`)
- Modify: `backend/state.py` (wherever these stores are constructed — pass a shared `Database`)

**Interfaces:**
- Consumes: `Database` from Task 1.
- Produces: each store keeps `db_path` for backward compat but holds `self.db = Database(db_path)`; `_get_connection()` removed; `_row_to_dict` replaced by `Database`'s `sqlite3.Row` dicts.

- [ ] **Step 1:** In `job_models.py`, change `SpeakerStore.__init__` to build `self.db = Database(self.db_path)`. Replace each `with self._get_connection() as conn: ... fetchall()` read with `self.db.query(...)`, each single-row read with `self.db.query_one(...)`, each write with `self.db.mutate(...)`. Delete `_get_connection` and `_row_to_dict`.

- [ ] **Step 2: Run SpeakerStore tests**

Run: `python -m pytest tests/test_stores.py -v -k Speaker`
Expected: PASS.

- [ ] **Step 3:** Repeat Step 1 for `CallSpeakerStore`, then `CallMetadataStore`, then `RefinementStore`. After each store, run its tests:

Run: `python -m pytest tests/test_stores.py tests/test_refinement_store.py -v`
Expected: PASS after each store migrated.

- [ ] **Step 4:** Confirm no remaining `_get_connection` in the four migrated stores:

Run: `grep -n "_get_connection" backend/job_models.py`
Expected: only `JobStore` still has it (migrated in Task 4).

- [ ] **Step 5: Commit**

```bash
git add backend/job_models.py backend/state.py
git commit -m "refactor(stores): migrate Speaker/CallSpeaker/CallMetadata/Refinement stores onto Database"
```

---

### Task 4: Migrate JobStore (the cached store) onto Database

**Files:**
- Modify: `backend/job_models.py` (`JobStore`)

**Interfaces:**
- Consumes: `Database`. JobStore keeps its in-memory cache and `threading.Lock` for cache coherence; only raw SQLite access moves to `self.db`.

- [ ] **Step 1:** Replace `JobStore._get_connection()` usages with `self.db.query/query_one/mutate`. KEEP the in-memory cache logic and the cache lock untouched. Move the pragma setup to `self.db.init_pragmas()` called once in `__init__`. Keep the defensive `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE` in `_init_db` but route them through `self.db.connection()`.

- [ ] **Step 2: Run JobStore tests**

Run: `python -m pytest tests/test_job_store.py -v`
Expected: PASS (CRUD, WAL mode, `__contains__`).

- [ ] **Step 3:** Confirm `_get_connection` is fully gone:

Run: `grep -n "_get_connection" backend/job_models.py`
Expected: no matches.

- [ ] **Step 4: Full backend suite**

Run: `python -m pytest tests/ -v --timeout=60`
Expected: PASS (no regressions across orchestrator, routes, stores).

- [ ] **Step 5: Commit**

```bash
git add backend/job_models.py
git commit -m "refactor(stores): migrate JobStore onto Database; remove last _get_connection"
```

---

### Task 5: Verification & finish

- [ ] **Step 1:** Run the full suite one final time from `backend/`:

Run: `python -m pytest tests/ -v --timeout=60`
Expected: all PASS. Capture the summary line as completion evidence.

- [ ] **Step 2:** Confirm net deletion (consolidation actually happened):

Run: `git diff --shortstat main` (or the base branch)
Expected: net negative or near-flat on `job_models.py` despite added module — the five `_get_connection` copies and row converters are gone.

- [ ] **Step 3:** REQUIRED SUB-SKILL: Use superpowers:verification-before-completion, then superpowers:finishing-a-development-branch to open/merge the PR.

## Self-Review notes for the implementer
- Do not change any public store method name or signature — callers in `routes/` and `state.py` rely on them.
- `Database.connection()` commits on clean exit; if any store relied on explicit rollback semantics, preserve them.
- RefinementStore gaining tests (Task 2) is a required deliverable, not optional.
