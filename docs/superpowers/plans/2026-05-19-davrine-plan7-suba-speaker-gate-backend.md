# Pre-Refinement Speaker Resolution Gate — Plan 7 Sub-plan A (Backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the backend half of spec `docs/superpowers/specs/2026-05-19-davrine-pre-refinement-speaker-gate-design.md` — insert a user-confirmation gate between alignment and Sonnet refinement. Add a `speakers_resolved` flag, split the orchestrator's post-alignment branch (auto-resolve when all labels matched, else pause at `phase="awaiting_speakers"`), promote `_is_anonymous_label` to a shared module, and add a new `POST /job/{job_id}/confirm-speakers` endpoint that applies user assignments and dispatches refinement.

**Architecture:** Five surgical changes. (1) Extract `_is_anonymous_label` + its compiled regex into a new `backend/services/labels.py` so both `routes/transcription.py` and `services/orchestrator.py` can import it without an underscore-prefixed cross-module reference. (2) Add `self.speakers_resolved = False` to `TranscriptionJob.__init__`; add a one-line migration default in `_row_to_job` (flip to `True` when `row.status == "completed"`); surface the field in `GET /job/{id}`. (3) Replace the orchestrator's single unconditional `_update_job(phase=None, _clear_phase=True, status="completed")` with a branch: if all labels are matched (B5 or non-anonymous) set `speakers_resolved=True` + clear phase + dispatch refinement; else set `phase="awaiting_speakers"` + `status="completed"` and DON'T dispatch. (4) Add `POST /job/{job_id}/confirm-speakers` — same payload shape as `/re-refine`, validates state (404/409/400), reuses `_apply_speaker_assignments` (which already has the name-based fallback from `19f9450`), sets `speakers_resolved=True` + `phase="refining"`, submits `_run_refinement_for_job` to `state.transcription_executor`. (5) Full-suite verification + manual curl smoke. No SQL migration. No new dependency.

**Tech Stack:** Python 3.11+, FastAPI, pytest, pydantic, sqlite3, ThreadPoolExecutor (existing `state.transcription_executor`).

---

## File Structure

**Create:**
- `backend/services/labels.py` — new module hosting `ANON_SPEAKER_RE` and `is_anonymous_label(name)`. Identical regex semantics to the frontend's `src/components/TranscriptView.tsx:13-15` and the current `_ANONYMOUS_SPEAKER_RE` at `backend/routes/transcription.py:798`.
- `backend/tests/test_confirm_speakers.py` — integration + unit tests for the gate behavior, orchestrator split, `/confirm-speakers` endpoint, and `_row_to_job` migration.

**Modify:**
- `backend/job_models.py:18-40` — add `self.speakers_resolved = False` to `TranscriptionJob.__init__`; in `_row_to_job` (`:168-179`) set `job.speakers_resolved = True` after column reads when `row[1] == "completed"`.
- `backend/services/orchestrator.py:271-298` — split the post-alignment block: delete the single unconditional `_update_job(progress=100, message="Complete!", status="completed", phase=None, _clear_phase=True)` line at `:276-277` and replace with the `_all_labels_matched(job)` branch. The auto-resolve branch keeps the clear + dispatches refinement (preserving the existing dispatch block `:282-305`); the awaiting branch sets `phase="awaiting_speakers"` and returns without dispatching.
- `backend/routes/transcription.py:796-805` — DELETE the local `_ANONYMOUS_SPEAKER_RE` + `_is_anonymous_label`, replace with `from services.labels import is_anonymous_label` (alias the existing `_is_anonymous_label` name to the new symbol so existing call sites at `:875`, `:967`, `:1026`, `:1228`, `:1445` keep working — see Task 1 for the exact alias pattern).
- `backend/routes/transcription.py:515-558` — surface `speakers_resolved` in the `GET /job/{job_id}` response dict (after `phase`).
- `backend/routes/transcription.py:1320` (after `/re-refine`) — add `POST /job/{job_id}/confirm-speakers`.

**Reference (read-only):**
- `backend/routes/transcription.py:981-1133` — `_apply_speaker_assignments(job, assignments, audio_path=...)` — reused as-is. The name-based fallback (lines 1040-1057) from commit `19f9450` handles voice extraction when Sonnet+B7 have already overlaid label renames.
- `backend/routes/transcription.py:1178-1320` — `/re-refine` route — the new `/confirm-speakers` mirrors its dispatch pattern (`_set_refinement_status`, `_update_job(phase="refining")`, `state.transcription_executor.submit(_run_refinement_for_job, ...)`).
- `backend/routes/refinement.py:_run_refinement_for_job` — reused as-is for the dispatch.
- `backend/services/orchestrator.py:70-127` — `_TranscribeProgressTicker` (commit `cef3396`) + elapsed-time message in `_run` (commit `b689cd3`). Preserve verbatim; the orchestrator edit only touches the post-alignment block at `:271-298`.
- `backend/routes/transcription.py:917-930` — `SpeakerAssignment` + `ReRefineRequest` pydantic models (reused/mirrored for the new endpoint).
- `backend/tests/conftest.py` — `icloud_base`, `sample_job`, `clean_speakers`, `client` fixtures.
- `backend/tests/test_re_refine.py` — established async-client integration test pattern.
- `src/components/TranscriptView.tsx:13-15` — frontend regex source-of-truth (`^(?:SPEAKER_\d+|Speaker\s*\d+|Unknown)$`, case-insensitive); the new `labels.py` must mirror it.
- `docs/superpowers/specs/2026-05-19-davrine-pre-refinement-speaker-gate-design.md` — authoritative contract.

---

## Conventions for all tasks

- **Working tree:** ~22 WIP files are uncommitted (verified via `git status --short`). NEVER use `git add -A` / `git add .`. Always stage by exact path. Files touched by this plan that already have WIP changes:
  - `backend/routes/transcription.py` — **heavy WIP risk**. Per Plan 5A history (commit `48d224c` absorbed earlier WIP into the route file, more has since accumulated). Before each edit task that touches it, check first:
    ```bash
    cd ~/Development/apps/whisper-transcription-app && git diff --stat backend/routes/transcription.py
    ```
    If there are pending changes you don't want to mix into the plan's commit, either (a) stash-dance:
    ```bash
    cd ~/Development/apps/whisper-transcription-app && git stash push -m "plan7A-wip-routes-transcription" -- backend/routes/transcription.py
    # … edit, run tests, commit …
    git stash pop
    ```
    or (b) use `git add -p backend/routes/transcription.py` and hand-pick only the plan's hunks. Pick whichever feels safer for the size of the touch.
  - `backend/job_models.py` — verify with `git diff --stat backend/job_models.py`. If clean, edit normally; if WIP, apply the same stash-or-`add -p` discipline.
  - `backend/services/orchestrator.py` — preserve `_TranscribeProgressTicker` (commit `cef3396`) and elapsed-time message in `_run` (commit `b689cd3`). The plan's only edit is at `:271-298` (the post-alignment block); verify your patch doesn't touch the ticker class at `:70-127`.
- **Branch:** all work lands on the current branch (`dev` per recent plan precedent). No new branch.
- **Venv & test command:** run pytest from the backend dir:
  ```bash
  cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest <args>
  ```
- **TDD discipline:** Use superpowers:test-driven-development. Failing test FIRST, watch it fail with the expected error, implement minimum to pass, then commit. Each task below lists the RED step explicitly.
- **Commit granularity:** one commit per task after its tests pass. Format: `Plan 7A Task N: <task summary>` (greppable).
- **No backend restart needed** between tasks 1-4 — pytest hits the code directly. Task 5 does the manual curl smoke; restart the backend then via `launchctl kickstart -k gui/$(id -u)/com.whisper.backend`.
- **Ship-lockstep with Sub-plan B:** the `/confirm-speakers` endpoint is non-breaking — no current client calls it. `speakers_resolved` in the GET response is also additive. Backend can ship first.

---

## Task 1: Promote `is_anonymous_label` to a shared module

**Files:**
- Create: `backend/services/labels.py`
- Modify: `backend/routes/transcription.py:796-805` (delete the local impl, replace with an import + alias)
- Test: existing tests (no new test file — this is a behavior-preserving refactor; the regression net is the existing suite passing)

- [ ] **Step 1: Baseline pytest run**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -5
```
Record the green pass count. Tasks 1-5 must match or exceed this baseline plus the new tests added in Tasks 2-4. If anything fails on baseline, STOP and investigate before touching code.

- [ ] **Step 2: Create the new `labels.py` module**

Write `backend/services/labels.py`:

```python
"""Shared helpers for speaker-label classification.

`is_anonymous_label` is the single source of truth for deciding whether a
diarization label still needs a real name. Used by both the orchestrator
(pre-refinement gate decision) and the routes layer (insights extraction,
re-refine validation, learning-source filtering).

Mirror of the frontend regex at src/components/TranscriptView.tsx:13-15.
Keep the two in lockstep when changing — anonymous-vs-named is a contract
boundary between FE and BE that must agree.
"""

import re
from typing import Optional

# `SPEAKER_00`, `Speaker 1`, `Unknown` — case-insensitive. Anything else
# is treated as a real human name.
ANON_SPEAKER_RE = re.compile(r"^(?:SPEAKER_\d+|Speaker\s*\d+|Unknown)$", re.IGNORECASE)


def is_anonymous_label(name: Optional[str]) -> bool:
    """True iff `name` is missing or matches an anonymous diarization label."""
    if not name:
        return True
    return bool(ANON_SPEAKER_RE.match(name.strip()))
```

- [ ] **Step 3: Delete the local impl in `routes/transcription.py` and import from the new module**

Edit `backend/routes/transcription.py`. At the top of the existing block at `:796-805` (the `import re as _re` + `_ANONYMOUS_SPEAKER_RE` + `def _is_anonymous_label(...)` lines), DELETE those three definitions in their entirety. Replace them with:

```python
# Plan 7: anonymous-label helper moved to services.labels so the orchestrator
# can import it too. We alias to the underscore-prefixed name to keep the
# existing call sites (insights extraction, re-refine validation, etc.)
# unchanged — they reference `_is_anonymous_label` directly.
from services.labels import is_anonymous_label as _is_anonymous_label  # noqa: F401
```

Important constraints:
- DO NOT change the existing call sites at `:875`, `:967`, `:1026`, `:1228`, `:1445`. They keep referring to `_is_anonymous_label` via the alias.
- Verify with: `grep -n "_is_anonymous_label\b" backend/routes/transcription.py` — should return 5 references (the original 5 call sites) plus the new import line. The `def _is_anonymous_label(...)` line should be GONE.
- Also verify no other file imports the old symbol:
  ```bash
  cd ~/Development/apps/whisper-transcription-app && grep -rn "from routes.transcription import.*_is_anonymous_label\|from backend.routes.transcription import.*_is_anonymous_label" backend/
  ```
  Expected: no hits. If any hit appears, update that file to `from services.labels import is_anonymous_label` instead.

- [ ] **Step 4: Run pytest — verify nothing broke (refactor regression net)**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -10
```
Must match the baseline from Step 1. If anything fails: read the trace, the most likely cause is a stale import or a typo in the alias line.

- [ ] **Step 5: Commit Task 1**

```bash
cd ~/Development/apps/whisper-transcription-app && git add backend/services/labels.py backend/routes/transcription.py && git commit -m "Plan 7A Task 1: promote is_anonymous_label to services/labels.py"
```

If `git status` for `backend/routes/transcription.py` shows hunks you don't want to commit, use the stash-dance or `git add -p` (per Conventions above) to land only the import-alias edit.

---

## Task 2: Add `speakers_resolved` field + `_row_to_job` migration + surface in GET

**Files:**
- Modify: `backend/job_models.py:18-40` (add `speakers_resolved` to `__init__`); `:168-179` (set in `_row_to_job` for `status=="completed"`)
- Modify: `backend/routes/transcription.py:515-558` (add `speakers_resolved` to the GET response dict)
- Test: new `backend/tests/test_confirm_speakers.py` — three unit tests for the field

- [ ] **Step 1: RED — write the failing field/migration/GET tests**

Create `backend/tests/test_confirm_speakers.py`:

```python
"""Plan 7A — backend tests for the pre-refinement speaker-resolution gate."""

import uuid
import pytest


# ---------- Task 2: speakers_resolved field + migration + GET surface ----------

def test_transcription_job_speakers_resolved_defaults_false():
    """New jobs start with speakers_resolved=False — they must pass the gate."""
    from job_models import TranscriptionJob
    job = TranscriptionJob("sr-1")
    assert hasattr(job, "speakers_resolved"), \
        "TranscriptionJob must declare a `speakers_resolved` attribute"
    assert job.speakers_resolved is False, "defaults to False pre-gate"


def test_row_to_job_migration_marks_completed_jobs_resolved():
    """Pre-Plan-7 completed jobs reloaded from SQL must be treated as
    already past the gate — they completed before the gate existed."""
    import state
    from job_models import TranscriptionJob

    # Insert a completed job directly into the store (mirrors the
    # restart-reload code path).
    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    job.status = "completed"
    job.progress = 100
    state.job_store.create(job)
    try:
        # Force a cache-miss reload via the SQL path.
        state.job_store._cache.pop(job_id, None)
        reloaded = state.job_store.get(job_id)
        assert reloaded is not None
        assert reloaded.status == "completed"
        assert reloaded.speakers_resolved is True, \
            "_row_to_job must flip completed jobs to resolved=True"
    finally:
        state.job_store.delete(job_id)


def test_row_to_job_migration_leaves_non_completed_unresolved():
    """A row with status != 'completed' must keep speakers_resolved=False
    (the orphan-cleanup will fail it on next restart anyway; this just
    ensures the migration is targeted)."""
    import state
    from job_models import TranscriptionJob

    job_id = str(uuid.uuid4())
    job = TranscriptionJob(job_id)
    job.status = "processing"
    state.job_store.create(job)
    try:
        state.job_store._cache.pop(job_id, None)
        reloaded = state.job_store.get(job_id)
        assert reloaded is not None
        assert reloaded.status == "processing"
        assert reloaded.speakers_resolved is False, \
            "non-completed rows must not be auto-flipped"
    finally:
        state.job_store.delete(job_id)


async def test_get_job_surfaces_speakers_resolved(icloud_base, sample_job, client):
    """GET /job/{id} response must include a `speakers_resolved` field."""
    resp = await client.get(f"/job/{sample_job}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "speakers_resolved" in data, \
        "GET response must surface speakers_resolved"
    # `sample_job` is inserted via state.job_store.create() which writes the
    # default False; the migration only flips on the SQL→Python reload path.
    # The fixture stays in-cache → field is False here, which is fine.
    assert isinstance(data["speakers_resolved"], bool)
```

Run and confirm RED:

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_confirm_speakers.py -x -q 2>&1 | tail -15
```
Expected: 4 failures — `AttributeError` or `AssertionError` on `speakers_resolved` field + `KeyError` on the GET response.

- [ ] **Step 2: GREEN — add the field to `__init__`**

Edit `backend/job_models.py` — find the `TranscriptionJob.__init__` block at `:19-40`. After the existing `self.phase = None` line at `:40`, add:

```python
        # Plan 7: speaker resolution gate. False until the orchestrator
        # auto-resolves (all labels B5-matched or non-anonymous) or the
        # user submits assignments via POST /job/{id}/confirm-speakers.
        # Refinement is gated on this flag.
        self.speakers_resolved = False
```

- [ ] **Step 3: GREEN — add the `_row_to_job` migration**

Edit `backend/job_models.py` — find `_row_to_job` at `:168-179`. After the existing `job.speakers = json.loads(row[9]) if row[9] else []` line at `:178`, but BEFORE the `return job` at `:179`, add:

```python
        # Plan 7 migration: pre-gate completed jobs are by definition past
        # the gate (no gate existed when they completed). Flip the default
        # so they don't get blocked by a UI panel that would never have
        # rendered for them. Non-completed rows are caught by the orphan
        # cleanup in _load_active_jobs (hotfix aaf1727) — they'll be
        # marked failed on startup and never reach the gate flow.
        if job.status == "completed":
            job.speakers_resolved = True
```

- [ ] **Step 4: GREEN — surface `speakers_resolved` in GET `/job/{id}`**

Edit `backend/routes/transcription.py` — find `get_job_status` at `:515-558`. In the response dict at `:523-539`, add a line after the `"phase": getattr(job, "phase", None),` line (currently `:529`):

```python
        # Plan 7: pre-refinement speaker gate — frontend uses this to decide
        # whether to render the SpeakerReviewPanel in pre-refinement mode
        # ("Confirm speakers") vs post-refinement mode ("Apply & re-refine").
        "speakers_resolved": getattr(job, "speakers_resolved", False),
```

- [ ] **Step 5: Run and confirm GREEN**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_confirm_speakers.py -x -q 2>&1 | tail -10
```
All 4 tests must pass. If migration test still fails: confirm the new line is INSIDE `_row_to_job` (before `return job`) and reads `job.status`, not `row[1]` directly — both work but `job.status` is clearer.

- [ ] **Step 6: Full-suite no-regressions check**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -5
```
Must match Task 1's baseline + 4 new passes.

- [ ] **Step 7: Commit Task 2**

```bash
cd ~/Development/apps/whisper-transcription-app && git add backend/job_models.py backend/routes/transcription.py backend/tests/test_confirm_speakers.py && git commit -m "Plan 7A Task 2: add speakers_resolved field + migration + GET surface"
```

If WIP exists on `backend/routes/transcription.py` outside the GET-response region, use `git add -p` to land only the GET-response hunk.

---

## Task 3: Orchestrator split — auto-resolve vs awaiting_speakers

**Files:**
- Modify: `backend/services/orchestrator.py:271-298` (replace the unconditional `_update_job(...status="completed", phase=None, _clear_phase=True)` with the `_all_labels_matched(job)` branch)
- Test: extend `backend/tests/test_confirm_speakers.py` with 3 orchestrator-branch tests

- [ ] **Step 1: RED — write the failing orchestrator-split tests**

Append to `backend/tests/test_confirm_speakers.py`:

```python
# ---------- Task 3: orchestrator split (auto-resolve vs awaiting) ----------

def test_all_labels_matched_true_when_all_segments_named():
    """All segments use real names → matched (auto-resolve path)."""
    from job_models import TranscriptionJob
    from services.orchestrator import _all_labels_matched

    job = TranscriptionJob("mlm-1")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "Pascal Weber"},
        {"start": 5, "end": 10, "text": "bonjour", "speaker": "David Marchesseau"},
    ]
    job.auto_speaker_matches = {}
    assert _all_labels_matched(job) is True


def test_all_labels_matched_true_when_all_anonymous_b5_matched():
    """Anonymous labels with B5 matched=True → matched (auto-resolve path)."""
    from job_models import TranscriptionJob
    from services.orchestrator import _all_labels_matched

    job = TranscriptionJob("mlm-2")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "SPEAKER_00"},
        {"start": 5, "end": 10, "text": "bonjour", "speaker": "SPEAKER_01"},
    ]
    job.auto_speaker_matches = {
        "SPEAKER_00": {"matched": True, "name": "Pascal Weber"},
        "SPEAKER_01": {"matched": True, "name": "David Marchesseau"},
    }
    assert _all_labels_matched(job) is True


def test_all_labels_matched_false_when_any_unmatched_anonymous():
    """Any anonymous label without a B5 match → unmatched (awaiting path)."""
    from job_models import TranscriptionJob
    from services.orchestrator import _all_labels_matched

    job = TranscriptionJob("mlm-3")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "Pascal Weber"},
        {"start": 5, "end": 10, "text": "??", "speaker": "SPEAKER_02"},
    ]
    job.auto_speaker_matches = {
        "SPEAKER_02": {"matched": False},
    }
    assert _all_labels_matched(job) is False


def test_all_labels_matched_empty_segments_returns_true():
    """Vacuous case: no segments to resolve → treat as matched (no-op refinement)."""
    from job_models import TranscriptionJob
    from services.orchestrator import _all_labels_matched
    job = TranscriptionJob("mlm-4")
    job.segments = []
    assert _all_labels_matched(job) is True
```

Run and confirm RED:

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_confirm_speakers.py::test_all_labels_matched_true_when_all_segments_named tests/test_confirm_speakers.py::test_all_labels_matched_true_when_all_anonymous_b5_matched tests/test_confirm_speakers.py::test_all_labels_matched_false_when_any_unmatched_anonymous tests/test_confirm_speakers.py::test_all_labels_matched_empty_segments_returns_true -x -q 2>&1 | tail -10
```
Expected: `ImportError: cannot import name '_all_labels_matched'` (helper doesn't exist yet).

- [ ] **Step 2: GREEN — add `_all_labels_matched` helper to the orchestrator**

Edit `backend/services/orchestrator.py`. After the imports block (after `from services.audio import apply_noise_reduction` at `:33`), and after the `logger = logging.getLogger(__name__)` line at `:36`, add the import:

```python
from services.labels import is_anonymous_label
```

Then ABOVE the `def orchestrate_transcription(...)` function (around `:130`, before line 130), add the helper:

```python
def _all_labels_matched(job) -> bool:
    """True iff every distinct speaker label in segments is either a
    non-anonymous name OR has an `auto_speaker_matches` entry with
    matched=True. Both conditions mean we know who they are.

    Empty segments list is treated as 'matched' (vacuously true) — nothing
    to resolve, refinement runs as today.
    """
    matches = job.auto_speaker_matches or {}
    for seg in (job.segments or []):
        label = seg.get("speaker")
        if not label:
            continue
        if not is_anonymous_label(label):
            continue  # Real name — counts as known
        if not matches.get(label, {}).get("matched"):
            return False
    return True
```

- [ ] **Step 3: Run the helper-only tests — confirm GREEN**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_confirm_speakers.py -k _all_labels_matched -x -q 2>&1 | tail -10
```
All 4 helper tests must pass.

- [ ] **Step 4: RED — write the failing orchestrator-branching tests**

Append to `backend/tests/test_confirm_speakers.py`:

```python
def test_orchestrator_auto_resolve_path_sets_resolved_and_dispatches(monkeypatch):
    """When _all_labels_matched returns True, orchestrator must:
      - set job.speakers_resolved = True
      - clear job.phase
      - leave job.status = "completed"
      - dispatch _run_refinement_for_job via state.transcription_executor
    """
    from unittest.mock import MagicMock
    import state
    from job_models import TranscriptionJob
    from services import orchestrator as orch

    job = TranscriptionJob("auto-1")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "Pascal Weber"},
    ]
    job.speakers = []
    job.auto_speaker_matches = {}
    state.job_store.create(job)
    try:
        # Drive the post-alignment finalize block directly. We extract its
        # contents into a private helper so the test can call it without
        # standing up the entire transcribe pipeline (see implementation
        # note in Step 5: the helper is `_finalize_after_alignment`).
        submit_mock = MagicMock()
        monkeypatch.setattr(state, "transcription_executor",
                            MagicMock(submit=submit_mock))
        monkeypatch.setattr(state, "refinement_available", True)
        monkeypatch.setattr(state.refinement_store, "create", MagicMock())
        # Settings stub: auto_refine on so the dispatch fires
        from job_models import TranscriptionSettings
        settings = TranscriptionSettings(speaker_ids=["sid-1"])

        orch._finalize_after_alignment(job, settings, audio_path="/fake.wav")

        assert job.speakers_resolved is True
        assert job.status == "completed"
        assert job.phase is None
        submit_mock.assert_called_once()
    finally:
        state.job_store.delete("auto-1")


def test_orchestrator_awaiting_path_sets_phase_and_does_not_dispatch(monkeypatch):
    """When _all_labels_matched returns False, orchestrator must:
      - leave job.speakers_resolved = False
      - set job.phase = "awaiting_speakers"
      - set job.status = "completed"
      - NOT dispatch refinement
    """
    from unittest.mock import MagicMock
    import state
    from job_models import TranscriptionJob, TranscriptionSettings
    from services import orchestrator as orch

    job = TranscriptionJob("await-1")
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "SPEAKER_00"},
    ]
    job.auto_speaker_matches = {"SPEAKER_00": {"matched": False}}
    state.job_store.create(job)
    try:
        submit_mock = MagicMock()
        monkeypatch.setattr(state, "transcription_executor",
                            MagicMock(submit=submit_mock))
        monkeypatch.setattr(state, "refinement_available", True)
        monkeypatch.setattr(state.refinement_store, "create", MagicMock())
        settings = TranscriptionSettings(speaker_ids=["sid-1"])

        orch._finalize_after_alignment(job, settings, audio_path="/fake.wav")

        assert job.speakers_resolved is False
        assert job.status == "completed"
        assert job.phase == "awaiting_speakers"
        submit_mock.assert_not_called()
    finally:
        state.job_store.delete("await-1")
```

Run and confirm RED:

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_confirm_speakers.py::test_orchestrator_auto_resolve_path_sets_resolved_and_dispatches tests/test_confirm_speakers.py::test_orchestrator_awaiting_path_sets_phase_and_does_not_dispatch -x -q 2>&1 | tail -15
```
Expected: `AttributeError: module 'services.orchestrator' has no attribute '_finalize_after_alignment'`.

- [ ] **Step 5: GREEN — extract `_finalize_after_alignment` + delete the prior unconditional phase-clear**

Edit `backend/services/orchestrator.py`. The current code at `:271-305` is:

```python
        _update_job(job, progress=90, message="Finalizing...")
        job.segments = transcription_segments
        job.result = full_text

        # Clear phase as we transition to completed (verbatim ready).
        _update_job(job, progress=100, message="Complete!", status="completed",
                    phase=None, _clear_phase=True)

        # Auto-refine dispatch (Best mode benefits most; Quick mode also runs
        # …
        if _should_auto_refine(settings) and state.refinement_available:
            try:
                from routes.refinement import _run_refinement_for_job
                job.refinement_status = "pending"
                state.jobs.update(job)
                state.refinement_store.create(job_id)
                job._defer_audio_cleanup = True
                state.transcription_executor.submit(
                    _run_refinement_for_job,
                    job_id,
                    settings.speaker_ids,
                    settings.context_path,
                    audio_path,
                )
                logger.info("Orchestrator: auto-refine dispatched for %s (mode=%s)", job_id, mode)
            except Exception:
                logger.exception("Orchestrator: auto-refine dispatch failed for %s", job_id)
                try:
                    job.refinement_status = "failed"
                    state.jobs.update(job)
                    state.refinement_store.update_status(job_id, "failed", "dispatch failed")
                except Exception:
                    logger.debug("Rollback after dispatch failure failed for %s",
                                 job_id, exc_info=True)
```

REPLACE the entire block from `_update_job(job, progress=90, message="Finalizing...")` (at `:271`) down to (and including) the closing `except Exception` log block (currently `:305`) with this:

```python
        _update_job(job, progress=90, message="Finalizing...")
        job.segments = transcription_segments
        job.result = full_text

        # Plan 7: pre-refinement speaker gate. Delegated to a helper so it
        # can be unit-tested without standing up the full transcribe path.
        # CRITICAL: the prior unconditional `_update_job(phase=None,
        # _clear_phase=True, status="completed", ...)` is GONE — the
        # auto-resolve branch keeps the clear, the awaiting branch sets
        # phase="awaiting_speakers" instead.
        _finalize_after_alignment(job, settings, audio_path=audio_path, mode=mode)
```

Then add the new helper above `def orchestrate_transcription(...)` (around `:130`, next to the `_all_labels_matched` helper added in Step 2):

```python
def _finalize_after_alignment(job, settings, audio_path: str,
                              mode: Literal["best", "quick"] = "best") -> None:
    """Plan 7: gate finalization on speaker resolution.

    Called once segments+turns are aligned and B5 auto-match has populated
    `job.auto_speaker_matches`. Branches:
      - All labels matched → set speakers_resolved=True, clear phase,
        dispatch refinement (existing auto-refine path).
      - Any anonymous-unmatched → set phase="awaiting_speakers", status=
        "completed", return WITHOUT dispatching. Refinement waits for
        POST /job/{id}/confirm-speakers.

    The transcript is fully usable in both branches (verbatim is ready);
    only Sonnet refinement is gated.
    """
    job_id = job.job_id
    if _all_labels_matched(job):
        job.speakers_resolved = True
        _update_job(job, progress=100, message="Complete!", status="completed",
                    phase=None, _clear_phase=True)
        if _should_auto_refine(settings) and state.refinement_available:
            try:
                from routes.refinement import _run_refinement_for_job
                job.refinement_status = "pending"
                state.jobs.update(job)
                state.refinement_store.create(job_id)
                job._defer_audio_cleanup = True
                state.transcription_executor.submit(
                    _run_refinement_for_job,
                    job_id,
                    settings.speaker_ids,
                    settings.context_path,
                    audio_path,
                )
                logger.info("Orchestrator: auto-refine dispatched for %s (mode=%s)",
                            job_id, mode)
            except Exception:
                logger.exception("Orchestrator: auto-refine dispatch failed for %s",
                                 job_id)
                try:
                    job.refinement_status = "failed"
                    state.jobs.update(job)
                    state.refinement_store.update_status(job_id, "failed",
                                                         "dispatch failed")
                except Exception:
                    logger.debug("Rollback after dispatch failure failed for %s",
                                 job_id, exc_info=True)
    else:
        # Awaiting branch: don't clear phase, don't dispatch refinement.
        # Transcript is still complete (the user can read it); only the
        # post-refinement enrichment is held back until they click Confirm.
        _update_job(job, progress=100,
                    message="Waiting for speaker resolution",
                    status="completed", phase="awaiting_speakers")
        logger.info("Orchestrator: %s awaiting speaker resolution (gate)", job_id)
```

Verify after the edit:
- The string `phase=None, _clear_phase=True` appears EXACTLY ONCE in `services/orchestrator.py` (inside `_finalize_after_alignment`'s auto-resolve branch). Run:
  ```bash
  cd ~/Development/apps/whisper-transcription-app && grep -n "_clear_phase=True" backend/services/orchestrator.py
  ```
  Expected: exactly one match. If two, the prior unconditional clear wasn't deleted — go back and fix.
- `_TranscribeProgressTicker` class is unchanged (verify `grep -n "elapsed_str" backend/services/orchestrator.py` still returns the elapsed-time line from commit `b689cd3`).

- [ ] **Step 6: Run and confirm GREEN**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_confirm_speakers.py -x -q 2>&1 | tail -10
```
All Task 2 + Task 3 tests must pass (4 + 4 + 2 = 10).

- [ ] **Step 7: Full-suite no-regressions check (orchestrator is on the critical path)**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -10
```
Watch for `test_orchestrator.py` + `test_auto_refine_orchestration.py` regressions in particular — those exercise the same code path. If anything fails, investigate before committing.

- [ ] **Step 8: Commit Task 3**

```bash
cd ~/Development/apps/whisper-transcription-app && git add backend/services/orchestrator.py backend/tests/test_confirm_speakers.py && git commit -m "Plan 7A Task 3: orchestrator gate split — auto-resolve vs awaiting_speakers"
```

---

## Task 4: `POST /job/{job_id}/confirm-speakers` endpoint

**Files:**
- Modify: `backend/routes/transcription.py` — add a new pydantic request model + route handler, immediately AFTER the `/re-refine` block (currently ends at `:1320`)
- Test: extend `backend/tests/test_confirm_speakers.py` with 5 integration tests

- [ ] **Step 1: RED — write the failing endpoint tests**

Append to `backend/tests/test_confirm_speakers.py`:

```python
# ---------- Task 4: POST /job/{job_id}/confirm-speakers ----------

async def test_confirm_speakers_happy_path(
    icloud_base, sample_job, clean_speakers, client, monkeypatch
):
    """Happy path: assign an existing UUID + create a new speaker + ignore one.

    Verifies:
      - 200 + correct response shape
      - speakers_resolved flips to True
      - phase becomes "refining"
      - refinement is dispatched (executor.submit called once)
      - ignored labels do NOT appear in helper_assignments (segments stay anonymous)
    """
    import state
    from unittest.mock import MagicMock
    from job_models import TranscriptionJob

    suffix = uuid.uuid4().hex[:8]
    pascal_name = f"Pascal_T4cs_{suffix}"
    fabrice_name = f"Fabrice_T4cs_{suffix}"

    # Seed job state: completed, speakers_resolved=False (gate not yet passed)
    job = state.job_store.get(sample_job)
    job.segments = [
        {"start": 0,  "end": 5,  "text": "hi",     "speaker": "SPEAKER_00"},
        {"start": 5,  "end": 10, "text": "salut",  "speaker": "SPEAKER_01"},
        {"start": 10, "end": 15, "text": "???",    "speaker": "SPEAKER_02"},
    ]
    job.speakers = [
        {"start": 0, "end": 5,   "speaker": "SPEAKER_00"},
        {"start": 5, "end": 10,  "speaker": "SPEAKER_01"},
        {"start": 10, "end": 15, "speaker": "SPEAKER_02"},
    ]
    job.status = "completed"
    job.speakers_resolved = False
    state.job_store.update(job)

    # Pre-seed Pascal so the UUID-assign path has something to find
    pascal_id = str(uuid.uuid4())
    state.speaker_store.create(pascal_id, pascal_name, f"speakers/{pascal_name}")
    clean_speakers.append(pascal_id)

    # Stub executor + embedding service so the test doesn't fire the worker
    submit_mock = MagicMock()
    monkeypatch.setattr(state, "transcription_executor",
                        MagicMock(submit=submit_mock))
    fake_emb = MagicMock()
    monkeypatch.setattr(
        state, "get_speaker_embedding_service",
        lambda: MagicMock(
            extract_embedding=MagicMock(return_value=fake_emb),
            register_speaker=MagicMock(return_value="fabrice-uuid-stub"),
            update_embedding=MagicMock(),
        ),
        raising=False,
    )

    body = {
        "speaker_assignments": {
            "SPEAKER_00": pascal_id,                # existing UUID
            "SPEAKER_01": f"new:{fabrice_name}",    # create new
            "SPEAKER_02": "ignore",                 # leave anonymous
        }
    }
    resp = await client.post(f"/job/{sample_job}/confirm-speakers", json=body)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["job_id"] == sample_job
    assert data["phase"] == "refining"
    assert data["speakers_assigned"] == 2  # ignore doesn't count
    assert data["speakers_ignored"] == 1
    assert any(c["name"] == fabrice_name for c in data["speakers_created"])

    # Cleanup the created Fabrice if it landed in the store
    fab = state.speaker_store.get_by_name(fabrice_name)
    if fab and fab.get("speaker_id"):
        clean_speakers.append(fab["speaker_id"])

    # Gate state flipped
    job_after = state.job_store.get(sample_job)
    assert job_after.speakers_resolved is True
    assert job_after.phase == "refining"

    # Refinement was dispatched
    submit_mock.assert_called_once()


async def test_confirm_speakers_409_when_already_resolved(
    icloud_base, sample_job, client
):
    """If speakers_resolved is already True, return 409 (idempotent error)."""
    import state
    job = state.job_store.get(sample_job)
    job.status = "completed"
    job.speakers_resolved = True
    state.job_store.update(job)

    resp = await client.post(
        f"/job/{sample_job}/confirm-speakers",
        json={"speaker_assignments": {"SPEAKER_00": "ignore"}},
    )
    assert resp.status_code == 409
    assert "resolved" in resp.text.lower() or "already" in resp.text.lower()


async def test_confirm_speakers_409_when_job_not_completed(
    icloud_base, sample_job, client
):
    """If status != 'completed', return 409."""
    import state
    job = state.job_store.get(sample_job)
    job.status = "processing"
    job.speakers_resolved = False
    state.job_store.update(job)

    resp = await client.post(
        f"/job/{sample_job}/confirm-speakers",
        json={"speaker_assignments": {"SPEAKER_00": "ignore"}},
    )
    assert resp.status_code == 409
    assert "completed" in resp.text.lower()


async def test_confirm_speakers_400_on_empty_assignments(
    icloud_base, sample_job, client
):
    """Empty speaker_assignments map → 400."""
    import state
    job = state.job_store.get(sample_job)
    job.status = "completed"
    job.speakers_resolved = False
    state.job_store.update(job)

    resp = await client.post(
        f"/job/{sample_job}/confirm-speakers",
        json={"speaker_assignments": {}},
    )
    assert resp.status_code == 400


async def test_confirm_speakers_404_when_job_not_found(client):
    """Unknown job_id → 404."""
    resp = await client.post(
        "/job/does-not-exist/confirm-speakers",
        json={"speaker_assignments": {"SPEAKER_00": "ignore"}},
    )
    assert resp.status_code == 404


async def test_confirm_speakers_tolerates_stale_labels(
    icloud_base, sample_job, clean_speakers, client, monkeypatch
):
    """Per re-refine pattern (commits 0a45794 + 19f9450): if a submitted
    label is no longer in job.segments, the endpoint must NOT 400 — it
    relies on _apply_speaker_assignments' name-based fallback. The helper
    will record the assignment even if the original label is gone."""
    import state
    from unittest.mock import MagicMock

    suffix = uuid.uuid4().hex[:8]
    pascal_name = f"Pascal_T4stale_{suffix}"

    job = state.job_store.get(sample_job)
    # The submitted label "SPEAKER_99" doesn't appear in segments —
    # mimics the post-overlay drift the spec describes.
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": pascal_name},
    ]
    job.speakers = []
    job.status = "completed"
    job.speakers_resolved = False
    state.job_store.update(job)

    pascal_id = str(uuid.uuid4())
    state.speaker_store.create(pascal_id, pascal_name, f"speakers/{pascal_name}")
    clean_speakers.append(pascal_id)

    monkeypatch.setattr(state, "transcription_executor",
                        MagicMock(submit=MagicMock()))
    monkeypatch.setattr(
        state, "get_speaker_embedding_service",
        lambda: MagicMock(
            extract_embedding=MagicMock(return_value=MagicMock()),
            update_embedding=MagicMock(),
        ),
        raising=False,
    )

    resp = await client.post(
        f"/job/{sample_job}/confirm-speakers",
        json={"speaker_assignments": {"SPEAKER_99": pascal_id}},
    )
    # Must not 400 on the stale label — same contract as /re-refine.
    assert resp.status_code == 200, resp.text
```

Run and confirm RED:

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_confirm_speakers.py -k confirm_speakers -x -q 2>&1 | tail -15
```
Expected: 6 failures — `404 Not Found` because the route doesn't exist yet.

- [ ] **Step 2: GREEN — add the request model + route handler**

Edit `backend/routes/transcription.py`. Immediately AFTER the existing `class ReRefineRequest(BaseModel):` block (at `:928-930`), add:

```python
class ConfirmSpeakersRequest(BaseModel):
    speaker_assignments: dict[str, str]
    # value is one of: existing speaker_id (UUID), "ignore", or "new:<name>".
    # Plan 7 — pre-refinement speaker resolution gate.
```

Then add the new route. Insert it AFTER the `/re-refine` route (which ends at `:1320`) and BEFORE the `_resolve_match_scope` helper at `:1323`:

```python
@router.post("/job/{job_id}/confirm-speakers")
async def confirm_speakers(job_id: str, req: ConfirmSpeakersRequest):
    """Plan 7 — pre-refinement speaker resolution gate.

    Called when the orchestrator paused at phase=awaiting_speakers because
    one or more diarization labels weren't auto-matched by B5. The user
    has reviewed the labels in the SpeakerReviewPanel and submits
    assignments. Each value is one of:
      - UUID string → assign to existing profile (extract voice + EMA-update)
      - "new:<name>" → create new profile with this name + extract voice
      - "ignore"     → leave the label anonymous in segments (no profile change)

    Sets speakers_resolved=True, transitions phase to "refining", and
    dispatches _run_refinement_for_job. Mirrors /re-refine's dispatch
    pattern (routes/transcription.py:1290-1320).

    Failures:
      - 404 if job not found
      - 409 if job.status != "completed" (gate is only reachable post-alignment)
      - 409 if speakers_resolved already True (idempotent — refinement is
        either in flight or has already run; user should use /re-refine)
      - 400 if speaker_assignments is empty
      - 400 if "new:name" name is malformed (anonymous-looking)

    Label-existence tolerance: matches /re-refine's pattern from commits
    0a45794 + 19f9450 — labels not in current job.segments are NOT 400'd;
    _apply_speaker_assignments' name-based audio-window fallback handles
    stale labels gracefully.
    """
    job = state.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Job must be completed (currently {job.status!r})",
        )
    if getattr(job, "speakers_resolved", False):
        raise HTTPException(
            status_code=409,
            detail="Speakers already resolved for this job; "
                   "use /re-refine to apply further corrections",
        )
    if not req.speaker_assignments:
        raise HTTPException(
            status_code=400,
            detail="At least one speaker_assignments entry required",
        )

    audio_path = _resolve_job_audio_path(job_id)

    # Build SpeakerAssignment records, excluding "ignore" (those skip
    # embedding extraction; their segments stay anonymous in job.segments).
    ignored_labels: list[str] = []
    new_names: set[str] = set()
    helper_assignments: list[SpeakerAssignment] = []

    for label, target in req.speaker_assignments.items():
        if target == "ignore":
            ignored_labels.append(label)
            continue
        if target.startswith("new:"):
            new_name = target[4:].strip()
            if not new_name or _is_anonymous_label(new_name):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid new speaker name: {new_name!r}",
                )
            new_names.add(new_name)
            helper_assignments.append(SpeakerAssignment(
                label=label, speaker_name=new_name, create_new=True,
            ))
            continue
        # Otherwise it's an existing speaker_id (UUID).
        try:
            sp = state.speaker_store.get(target)
        except Exception:
            sp = None
        if not sp or not sp.get("name"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid speaker_id: {target!r}",
            )
        helper_assignments.append(SpeakerAssignment(
            label=label, speaker_name=sp["name"], create_new=False,
        ))

    # Apply assignments via the shared helper (handles segment/turn rename
    # + speaker creation + embedding registration + DB updates). The helper
    # has a name-based fallback (commit 19f9450) for stale labels.
    out = {"results": []}
    if helper_assignments:
        try:
            out = _apply_speaker_assignments(
                job, helper_assignments, audio_path=audio_path,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Speaker assignment failed during confirm-speakers")
            raise HTTPException(
                status_code=409,
                detail=f"Failed to apply speaker assignments: {e}",
            )

    # Build response.speakers_created from helper output.
    speakers_created: list[dict] = [
        {"speaker_id": r["speaker_id"], "name": r["speaker_name"]}
        for r in out["results"]
        if r.get("created") and r.get("speaker_name") in new_names
    ]

    # Flip the gate + transition phase. Refinement store row is created
    # idempotently (INSERT OR REPLACE — see job_models.py).
    state.refinement_store.create(job_id)

    from routes.refinement import _set_refinement_status, _run_refinement_for_job
    from services.transcription import _update_job

    job.speakers_resolved = True
    _set_refinement_status(job, "pending")
    _update_job(job, phase="refining")
    job._defer_audio_cleanup = True

    speaker_ids = list(dict.fromkeys(
        r["speaker_id"] for r in out["results"] if r.get("speaker_id")
    ))
    context_path = (
        job.settings.context_path if getattr(job, "settings", None) else None
    )
    state.transcription_executor.submit(
        _run_refinement_for_job, job_id, speaker_ids, context_path, audio_path,
    )

    return {
        "job_id": job_id,
        "status": "refining",
        "phase": "refining",
        "speakers_created": speakers_created,
        "speakers_assigned": len(helper_assignments),
        "speakers_ignored": len(ignored_labels),
    }
```

- [ ] **Step 3: Run the new tests — confirm GREEN**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_confirm_speakers.py -k confirm_speakers -x -q 2>&1 | tail -15
```
All 6 confirm-speakers tests must pass. Common failures + fixes:
- `422 Unprocessable Entity` on the happy path: check the `ConfirmSpeakersRequest` model is reachable from the route handler signature (added in the right scope).
- `AttributeError: '_set_refinement_status'`: the import line `from routes.refinement import _set_refinement_status, _run_refinement_for_job` must succeed; confirm the symbol exists with `grep -n "def _set_refinement_status" backend/routes/refinement.py`.

- [ ] **Step 4: Run the full `test_confirm_speakers.py` file — all Task 2 + 3 + 4 tests green**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_confirm_speakers.py -x -q 2>&1 | tail -10
```
Expected: 16 passes (4 field/migration + 4 helper + 2 orchestrator-branch + 6 endpoint).

- [ ] **Step 5: Full-suite no-regressions check**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -10
```
Pay particular attention to `test_re_refine.py` — the new route lives in the same file and shares helpers; a regression there is the most likely failure mode.

- [ ] **Step 6: Commit Task 4**

```bash
cd ~/Development/apps/whisper-transcription-app && git add backend/routes/transcription.py backend/tests/test_confirm_speakers.py && git commit -m "Plan 7A Task 4: POST /confirm-speakers endpoint"
```

If `backend/routes/transcription.py` has unrelated WIP, use `git add -p backend/routes/transcription.py` to land only the `ConfirmSpeakersRequest` model + new route hunk.

---

## Task 5: Full-suite verification + manual smoke

**Files:**
- None (verification only)

- [ ] **Step 1: Final full-suite pytest run from a clean state**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -q 2>&1 | tail -10
```
Must show:
- All Task 1 baseline tests still green
- 16 new tests added by this plan all green
- Zero new failures or errors

If anything is red: do NOT proceed. Investigate root cause per superpowers:systematic-debugging.

- [ ] **Step 2: Restart the backend so the smoke test exercises the new route**

```bash
launchctl kickstart -k gui/$(id -u)/com.whisper.backend
```

Then wait for the health endpoint to come up:

```bash
until curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; do sleep 1; done && echo "backend up"
```

- [ ] **Step 3: Smoke — GET `/job/{any_recent_id}` surfaces `speakers_resolved`**

```bash
JOB=$(curl -s http://127.0.0.1:8000/jobs | python3 -c "import json, sys; data=json.load(sys.stdin); print(data['jobs'][0]['job_id'] if data.get('jobs') else '')")
[ -n "$JOB" ] && curl -s "http://127.0.0.1:8000/job/$JOB" | python3 -c "import json,sys; d=json.load(sys.stdin); print('speakers_resolved=', d.get('speakers_resolved'))"
```
Expected: prints `speakers_resolved= True` (for a pre-existing completed job, which the migration in Task 2 flipped on reload).

If `JOB` is empty (no jobs exist): skip this step, it's purely confirmatory.

- [ ] **Step 4: Smoke — POST `/confirm-speakers` on a non-existent job returns 404**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  -H "Content-Type: application/json" \
  -d '{"speaker_assignments": {"SPEAKER_00": "ignore"}}' \
  http://127.0.0.1:8000/job/does-not-exist/confirm-speakers
```
Expected: `404`.

- [ ] **Step 5: Smoke — POST `/confirm-speakers` with empty body returns 400**

```bash
JOB_EXISTING="<any-completed-job-id>"  # use a real one from /jobs if available
[ -n "$JOB_EXISTING" ] && curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  -H "Content-Type: application/json" \
  -d '{"speaker_assignments": {}}' \
  "http://127.0.0.1:8000/job/$JOB_EXISTING/confirm-speakers"
```
Expected: `400` (or `409` if the existing job is already resolved — also acceptable for the smoke, since the validation order is status → already-resolved → empty-body, all return non-2xx).

If you can't find a completed-but-unresolved job, this step is best-effort — the equivalent path is fully covered by `test_confirm_speakers_400_on_empty_assignments`.

- [ ] **Step 6: Final commit (verification only — no code changes)**

This task has no code changes to commit. Confirm working tree state:

```bash
cd ~/Development/apps/whisper-transcription-app && git status --short
```
Should show only the pre-existing WIP files (the ~22 from baseline). No plan-introduced files should be uncommitted.

If you find uncommitted plan-introduced changes (e.g. you forgot to commit Task 3 or 4), stage them now per the task's commit instructions.

---

## Done criteria

- All 5 tasks committed (`git log --oneline | grep "Plan 7A"` shows 4 task commits — Task 5 is verification-only).
- `backend/services/labels.py` exists and contains `is_anonymous_label` + `ANON_SPEAKER_RE`.
- `backend/routes/transcription.py` no longer defines `_is_anonymous_label` (only imports it via alias).
- `backend/job_models.py` has `speakers_resolved=False` in `__init__` and `speakers_resolved=True` for completed rows in `_row_to_job`.
- `backend/services/orchestrator.py` has exactly one `_clear_phase=True` occurrence (in `_finalize_after_alignment`'s auto-resolve branch); `_TranscribeProgressTicker` + elapsed-time message preserved.
- `POST /job/{id}/confirm-speakers` route handler exists; 6 integration tests pass.
- `GET /job/{id}` response includes `speakers_resolved`.
- Full backend pytest suite green, no regressions vs baseline.
- Manual smoke confirms 404 / 400 / GET-field on the running backend.

Sub-plan B (frontend) can now begin — backend changes are non-breaking and additive.
