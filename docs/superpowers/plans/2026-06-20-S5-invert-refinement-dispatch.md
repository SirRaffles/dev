# S5 — Invert the orchestrator→route refinement dependency

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `dispatch_refinement_for_job` out of `backend/routes/refinement.py` into a new service `backend/services/refinement_dispatch.py`, so `services/orchestrator.py` no longer imports a route. Add unit tests for the finalization functions.

**Architecture:** The function is service logic misplaced in a route (it touches only `state` + a lazy `services.transcription._update_job`, never the router/`app`). Relocate it (plus its private helpers like `_set_refinement_status` if they are not used elsewhere in the route) into a service module. Both the route and the orchestrator import from the service. Keep finalization functions as-is; cover them with tests.

**Tech Stack:** Python 3, FastAPI app (not touched here), pytest + pytest-asyncio + pytest-timeout.

## Global Constraints

- Run backend tests from `backend/` with the project venv: `./venv/bin/python -m pytest tests/ --timeout=60 -q`.
- Behaviour-preserving: `dispatch_refinement_for_job` keeps its exact signature: `dispatch_refinement_for_job(job, speaker_ids: Optional[List[str]] = None, context_path: Optional[str] = None, audio_path: Optional[str] = None) -> None`.
- No new import cycle: `services/refinement_dispatch.py` may import `state` and (lazily, as today) `services.transcription`; it must NOT import anything from `routes`.
- Do NOT touch `state.py`, `app_state` (that is S6), or any frontend file. Scope: `backend/services/refinement_dispatch.py` (new), `backend/services/orchestrator.py`, `backend/routes/refinement.py`, and `backend/tests/`.

---

### Task 1: Characterize the finalization functions (safety net)

**Files:**
- Create: `backend/tests/test_finalization.py`
- Read: `backend/services/orchestrator.py` (`_all_labels_matched` L136, `_finalize_after_alignment` L187, `_dispatch_refinement` L156)

- [ ] **Step 1:** Read the three functions and the `job`/`settings` shapes they use (`speakers_resolved`, `speaker_review_status`, refinement-policy call). Note the exact attribute names and the review-status constants.

- [ ] **Step 2: Write characterization tests** (these PASS against current code — they pin behaviour before S5 moves anything):

```python
# backend/tests/test_finalization.py
from services.orchestrator import _all_labels_matched

def test_all_labels_matched_true_when_no_anonymous(monkeypatch):
    # Build the minimal job object the function inspects (match real attrs found in Step 1).
    class J: ...
    job = J()
    # ... set the attributes _all_labels_matched reads, for the "all matched" case
    assert _all_labels_matched(job) is True

def test_all_labels_matched_false_when_unresolved(monkeypatch):
    class J: ...
    job = J()
    # ... set attributes for an unresolved-label case
    assert _all_labels_matched(job) is False
```

> Fill the job attributes from the REAL code read in Step 1. Do not invent fields.

- [ ] **Step 3: Run**

Run: `./venv/bin/python -m pytest tests/test_finalization.py -v`
Expected: PASS (pins current behaviour).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_finalization.py
git commit -m "test(orchestrator): characterize finalization label-matching before S5"
```

---

### Task 2: Create the refinement_dispatch service

**Files:**
- Create: `backend/services/refinement_dispatch.py`
- Modify: `backend/routes/refinement.py` (remove the moved function; import it back for any in-route callers)

**Interfaces:**
- Produces: `dispatch_refinement_for_job(job, speaker_ids=None, context_path=None, audio_path=None) -> None` in `services/refinement_dispatch.py`.

- [ ] **Step 1:** Move the full body of `dispatch_refinement_for_job` from `routes/refinement.py` into `services/refinement_dispatch.py`. Bring along any private helpers it calls that are not used elsewhere in the route (e.g. `_set_refinement_status`) — check usages first with `grep -n "_set_refinement_status" backend/routes/refinement.py`; if the helper is used by other route handlers too, leave a copy/shared import rather than breaking them.

- [ ] **Step 2:** In `routes/refinement.py`, replace the definition with `from services.refinement_dispatch import dispatch_refinement_for_job` so existing in-route callers keep working.

- [ ] **Step 3: Run the refinement + transcription suites**

Run: `./venv/bin/python -m pytest tests/test_re_refine.py tests/test_refinement_context.py tests/test_auto_refine_orchestration.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/services/refinement_dispatch.py backend/routes/refinement.py
git commit -m "refactor(refinement): move dispatch_refinement_for_job into a service"
```

---

### Task 3: Point the orchestrator at the service

**Files:**
- Modify: `backend/services/orchestrator.py` (`_dispatch_refinement` L156)

- [ ] **Step 1:** Replace the lazy `from routes.refinement import dispatch_refinement_for_job` (orchestrator L160) with `from services.refinement_dispatch import dispatch_refinement_for_job` (top-level import is now safe — no cycle). Adjust the call if the orchestrator passed args positionally that changed.

- [ ] **Step 2: Confirm no service→route import remains**

Run: `grep -rn "from routes" backend/services/`
Expected: no matches.

- [ ] **Step 3: Run orchestrator + full suite**

Run: `./venv/bin/python -m pytest tests/test_orchestrator.py tests/test_auto_refine_orchestration.py -v && ./venv/bin/python -m pytest tests/ --timeout=60 -q`
Expected: PASS (full suite green).

- [ ] **Step 4: Commit**

```bash
git add backend/services/orchestrator.py
git commit -m "refactor(orchestrator): import refinement dispatch from service, drop route import"
```

---

### Task 4: Verification & finish

- [ ] **Step 1:** Full suite final run:

Run: `./venv/bin/python -m pytest tests/ --timeout=60 -q`
Expected: all PASS. Capture the summary line.

- [ ] **Step 2:** REQUIRED SUB-SKILL: Use superpowers:verification-before-completion, then report your branch + evidence for the coordinator to merge.

## Self-Review notes
- If `_set_refinement_status` or other helpers are shared by multiple route handlers, do NOT break them — keep a shared definition (import from the service, or leave in the route and import into the service).
- The function signature must not change; callers in routes and orchestrator depend on it.
