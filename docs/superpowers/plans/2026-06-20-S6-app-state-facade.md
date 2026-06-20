# S6 — Typed `app_state` façade over the state.py seam

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `backend/app_state.py` — a typed accessor façade over the existing `state.py` globals — and migrate the ~190 `state.X` accesses in the 8 route files to `app_state.X()`. `state.py` stays the implementation.

**Architecture:** The façade exposes accessor functions that read through to `state.py`'s module globals. No global semantics or initialization order changes. The migration is mechanical and behaviour-preserving, guarded by the full backend suite. **Blocked by S5** (S5 edits `routes/refinement.py`; do S5 first to avoid conflicts).

**Tech Stack:** Python 3, FastAPI, pytest.

## Global Constraints

- Run backend tests from `backend/` with the venv: `./venv/bin/python -m pytest tests/ --timeout=60 -q`.
- `state.py` MUST remain unchanged in semantics and init order — the façade only reads from it. Existing tests monkeypatch `state.*`; they must keep passing because the façade reads through to those same globals.
- Behaviour-preserving: each `app_state.X()` returns exactly the current `state.X` value at call time (accessors read live, do not cache).
- Scope: `backend/app_state.py` (new), the 8 route files under `backend/routes/`, and `backend/tests/` (façade tests). Do NOT touch `state.py`, services, or frontend.

---

### Task 1: Build the façade with tests

**Files:**
- Create: `backend/app_state.py`
- Create: `backend/tests/test_app_state.py`

**Interfaces produced** (accessor names map to `state.py` globals; read live):
```python
# backend/app_state.py
import state
def jobs(): return state.job_store
def batch_jobs(): return state.batch_jobs
def multimodal_jobs(): return state.multimodal_jobs
def speaker_store(): return state.speaker_store
def call_speaker_store(): return state.call_speaker_store
def call_metadata_store(): return state.call_metadata_store
def refinement_store(): return state.refinement_store
def refinement_service(): return state.refinement_service
def deliverable_service(): return state.deliverable_service
def executor(): return state.transcription_executor
def speaker_embedding_service(): return state.get_speaker_embedding_service()
def is_ready_to_transcribe(): return bool(state.whisper_model_ready and state.diarization_pipeline)
def refinement_available(): return bool(state.refinement_available)
def deliverable_available(): return bool(state.deliverable_available)
def startup_time(): return state.startup_time
```

- [ ] **Step 1: Write failing tests** that prove the façade reads through to `state`:

```python
# backend/tests/test_app_state.py
import state
import app_state

def test_jobs_reads_through(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(state, "job_store", sentinel)
    assert app_state.jobs() is sentinel

def test_is_ready_combines_flags(monkeypatch):
    monkeypatch.setattr(state, "whisper_model_ready", True)
    monkeypatch.setattr(state, "diarization_pipeline", object())
    assert app_state.is_ready_to_transcribe() is True
    monkeypatch.setattr(state, "whisper_model_ready", False)
    assert app_state.is_ready_to_transcribe() is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_app_state.py -v`
Expected: FAIL (no module `app_state`).

- [ ] **Step 3: Implement `backend/app_state.py`** exactly as the interface block above (verify each `state.X` name exists by reading `state.py` first).

- [ ] **Step 4: Run to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_app_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app_state.py backend/tests/test_app_state.py
git commit -m "feat(app_state): typed façade over state.py globals"
```

---

### Task 2: Migrate routes — one file per step, test after each

**Files (one per step):** `backend/routes/transcription.py`, `calls.py`, `refinement.py`, `models_api.py`, `speakers.py`, `multimodal.py`, `jpr.py`, `recordings.py`

For EACH route file, do this loop (start with the smallest — `recordings.py` (2 sites) — to validate the pattern, then ascend to `transcription.py` (58 sites) last):

- [ ] **Step A:** In the file, `import app_state` and replace each raw field access:
  - `state.job_store` / `state.jobs` → `app_state.jobs()`
  - `state.batch_jobs` → `app_state.batch_jobs()`
  - `state.multimodal_jobs` → `app_state.multimodal_jobs()`
  - `state.speaker_store` → `app_state.speaker_store()`
  - `state.call_speaker_store` → `app_state.call_speaker_store()`
  - `state.call_metadata_store` → `app_state.call_metadata_store()`
  - `state.refinement_store` → `app_state.refinement_store()`
  - `state.refinement_service` → `app_state.refinement_service()`
  - `state.deliverable_service` → `app_state.deliverable_service()`
  - `state.transcription_executor` → `app_state.executor()`
  - `state.get_speaker_embedding_service()` → `app_state.speaker_embedding_service()`
  - `state.whisper_model_ready and state.diarization_pipeline` → `app_state.is_ready_to_transcribe()`
  - `state.refinement_available` → `app_state.refinement_available()`
  - `state.deliverable_available` → `app_state.deliverable_available()`
  - `state.startup_time` → `app_state.startup_time()`
  - Leave any access that has no façade accessor as `state.X` and NOTE it (do not invent an accessor mid-migration — report it for a façade extension).

- [ ] **Step B:** Run that file's API test (and the full suite for the last/biggest files):

Run (example for speakers): `./venv/bin/python -m pytest tests/test_speakers_api.py -v`
Expected: PASS.

- [ ] **Step C:** Commit per file:

```bash
git add backend/routes/<file>.py
git commit -m "refactor(routes): <file> reads state via app_state façade"
```

Repeat A–C for all 8 files.

---

### Task 3: Verification & finish

- [ ] **Step 1:** Confirm raw `state.<field>` field access is gone from routes (imports of the `state` module may remain only if some non-accessor field was intentionally left and reported):

Run: `grep -rn "state\.\(job_store\|jobs\|batch_jobs\|multimodal_jobs\|speaker_store\|call_speaker_store\|call_metadata_store\|refinement_store\|refinement_service\|deliverable_service\|transcription_executor\|refinement_available\|deliverable_available\|startup_time\)" backend/routes/`
Expected: no matches (all migrated). Report any deliberate leftovers.

- [ ] **Step 2:** Full suite:

Run: `./venv/bin/python -m pytest tests/ --timeout=60 -q`
Expected: all PASS. Capture the summary.

- [ ] **Step 3:** REQUIRED SUB-SKILL: Use superpowers:verification-before-completion, then report your branch + evidence for the coordinator to merge.

## Self-Review notes
- Accessors read live (`return state.X`) — never snapshot at import time, or monkeypatch-based tests break.
- If a route accesses a `state` field with no accessor (e.g. `state._parakeet_available`), leave it and report it rather than guessing an accessor — the façade can be extended deliberately.
- `state.jobs` is a legacy alias for `state.job_store`; both map to `app_state.jobs()`.
