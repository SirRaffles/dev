# Davrine Speaker Review — Plan 5 Sub-plan A (Backend: Runner-up + Re-Refine Endpoint) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the backend half of spec `docs/superpowers/specs/2026-05-17-davrine-speaker-review-design.md` — extend B5 voice auto-match to expose a 2nd-best (`runner_up`) candidate on each `auto_speaker_matches` entry, refactor the existing `/speakers/assign` route body into a shared `_apply_speaker_assignments(job, assignments)` helper, and add a new `POST /job/{id}/re-refine` endpoint that applies assignments + dispatches a second refinement run on `state.transcription_executor`.

**Architecture:** Two surgical, additive changes plus one refactor. (1) `SpeakerEmbeddingService.match_speaker` is extended to return a third value — the second-highest cosine match dict — gated by a `RUNNER_UP_THRESHOLD = 0.4` constant; `auto_identify_speakers` propagates `runner_up` into each result entry (null when none qualifies). (2) The body of `POST /job/{id}/speakers/assign` (currently inline at `routes/transcription.py:1006`) is extracted verbatim into a callable `_apply_speaker_assignments(job, assignments) -> {mapping, results}` so both the existing route AND the new `/re-refine` route share it. (3) The new `POST /job/{id}/re-refine` validates the job is `completed`, calls the shared helper, handles `"unknown"` strip + `"new:name"` voice-embedding registration, resets `job.refinement_status="pending"` + `job.phase="refining"`, then submits `_run_refinement_for_job(job_id, speaker_ids, context_path, audio_path)` to `state.transcription_executor` — the same dispatch pattern as `services/orchestrator.py:193` and `routes/refinement.py:_run_refinement`. Frontend (Sub-plan B) consumes the new `runner_up` field and calls the new endpoint; backend changes are non-breaking — `runner_up` is additive, `/speakers/assign` semantics are preserved, no DB migration.

**Tech Stack:** Python 3.11+, FastAPI, pytest, pydantic, numpy, ThreadPoolExecutor (existing `state.transcription_executor`).

---

## File Structure

**Create:**
- `backend/tests/test_re_refine.py` — integration tests for the new `/re-refine` endpoint + runner_up coverage (~80-120 lines)

**Modify:**
- `backend/services/speaker_embedding.py:172-233` — extend `match_speaker` return signature to `(name, score, runner_up_dict_or_None)`, computing the second-best cosine candidate inside the per-speaker loop, gated by `RUNNER_UP_THRESHOLD = 0.4`
- `backend/services/speaker_embedding.py:357-440` — propagate `runner_up` field through `auto_identify_speakers` into each entry of the returned dict (preserve all existing fields: `matched`, `speaker_id`, `name`, `confidence`, `source`, `note` — additive only)
- `backend/routes/transcription.py:1006-1140` — extract the assignment-application body of `POST /job/{id}/speakers/assign` into a module-level `_apply_speaker_assignments(job, assignments) -> dict` callable; refactor the existing route to delegate to it (behavior-preserving); add the new `POST /job/{id}/re-refine` endpoint that calls the helper + handles `"unknown"`/`"new:name"` semantics + dispatches refinement

**Reference (read-only):**
- `backend/routes/refinement.py:183-303` — `_run_refinement_for_job(job_id, speaker_ids, context_path, audio_path)` — re-used as-is for the re-refinement dispatch; same signature as orchestrator + manual `/refine/job/{id}` route
- `backend/services/orchestrator.py:188-200` — canonical `state.transcription_executor.submit(_run_refinement_for_job, ...)` call site pattern to mirror in the new endpoint
- `backend/services/speaker_embedding.py:235-277` — `register_speaker(name, embedding) -> speaker_id` — re-used for the "new:name" path (creates folder + DB row + saves `.npy` in one call)
- `backend/services/speaker_embedding.py:83` — `extract_embedding(audio_path, start, end) -> np.ndarray` — used by the `"new:name"` branch to derive a voice embedding from the longest matching turn
- `backend/routes/transcription.py:831-870` — existing helpers `_is_anonymous_label`, `_longest_turn_for_label`, `_resolve_job_audio_path` — re-used by the new endpoint
- `backend/state.py:72` — `transcription_executor = ThreadPoolExecutor(max_workers=1)` — refinement dispatch pool
- `backend/job_models.py:33-40` — `refinement_status` and `phase` fields on `TranscriptionJob`
- `backend/tests/test_speaker_auto_match_scope.py` — established pattern for synthetic-embedding tests (no GPU needed)
- `backend/tests/conftest.py` — `icloud_base`, `sample_job`, `clean_speakers` fixtures
- `docs/superpowers/specs/2026-05-17-davrine-speaker-review-design.md` — authoritative spec; "Backend shape" (lines 100-144) and "New endpoint" (lines 146-173) are the contract source of truth

---

## Conventions for all tasks

- **Working tree:** ~22 WIP files are uncommitted (verified via `git status --short`). NEVER use `git add -A` / `git add .`. Always stage by exact path. Files touched by this plan that already have WIP changes:
  - `backend/routes/transcription.py` — **heavy WIP**. Before each edit task that touches it, run:
    ```bash
    cd ~/Development/apps/whisper-transcription-app && git stash push -m "plan5A-wip-routes-transcription" -- backend/routes/transcription.py
    ```
    Then edit, commit, then:
    ```bash
    cd ~/Development/apps/whisper-transcription-app && git stash pop
    ```
    Resolve any conflicts (the WIP changes are in different regions — `_apply_speaker_assignments` extraction and the new `/re-refine` route are in the `:1006-1180` window; existing WIP touches other regions).
  - `backend/services/speaker_embedding.py` — WIP present. Same stash-and-pop pattern. The runner-up changes are in `:172-440`; check `git diff backend/services/speaker_embedding.py` first to identify the WIP regions and avoid stomping.
- **Branch:** all work lands on the current branch (`dev` per recent plan precedent). No new branch.
- **Venv:** run pytest from the backend venv:
  ```bash
  cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest <args>
  ```
- **TDD discipline:** Use superpowers:test-driven-development. Failing test FIRST, watch it fail with the expected error, implement minimum to pass, then commit.
- **Commit granularity:** one commit per task after its tests pass. Format: `Plan 5A Task N: <task summary>` (greppable).
- **No backend restart needed** between tasks — pytest hits the code directly. Task 5 (final) is the only manual smoke; restart the backend if doing manual verification: `launchctl kickstart -k gui/$(id -u)/com.whisper.backend`.
- **Ship-lockstep with Sub-plan B:** the new `runner_up` field is only consumed by the frontend (Sub-plan B). Backend can ship first — the field is additive and ignored by current clients. The `/re-refine` endpoint can also ship first — no client calls it yet.

---

## Task 1: Baseline & spec re-read

**Files:**
- None (verification only)

- [ ] **Step 1: Confirm working tree state**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app && git status --short | wc -l
```
Expected: a small number of WIP files (~22 at plan-write time). DO NOT clean them up.

- [ ] **Step 2: Run existing backend tests as baseline**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -5
```
Expected: a clean pass count. **Record the number** — Task 5 must match or exceed this baseline + the new tests added in Tasks 2-4. If anything fails on baseline, stop and investigate before touching code.

- [ ] **Step 3: Re-read the spec**

Re-read `docs/superpowers/specs/2026-05-17-davrine-speaker-review-design.md` sections "Backend shape: `auto_speaker_matches` extension" (lines 100-144) and "New endpoint: `POST /job/{job_id}/re-refine`" (lines 146-173). Confirm the contracts: `runner_up` is null when registry has < 2 speakers OR runner-up confidence < `0.4`; `/re-refine` returns 404 (not found), 409 (not completed OR audio unavailable for new:name), 400 (invalid speaker_id / malformed name / label not in segments).

- [ ] **Step 4: Confirm Plan 4A shipped (orchestrator dispatch pattern in place)**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app && grep -n "transcription_executor.submit" backend/services/orchestrator.py backend/routes/refinement.py
```
Expected: at least one hit in `backend/services/orchestrator.py` calling `_run_refinement_for_job`. This is the exact pattern the new `/re-refine` endpoint mirrors. If empty, STOP — Plan 4A's orchestrator refactor is a prerequisite.

---

## Task 2: Extend `match_speaker` to return runner-up

**Files:**
- Modify: `backend/services/speaker_embedding.py:172-233`
- Test: `backend/tests/test_re_refine.py` (new file — runner_up unit tests added here, integration tests follow in Tasks 4)

- [ ] **Step 1: Write the failing unit tests**

Create `backend/tests/test_re_refine.py` with the first three tests:

```python
"""Plan 5A — backend tests for runner-up exposure + /re-refine endpoint."""

import numpy as np
import pytest

from services.speaker_embedding import SpeakerEmbeddingService


def _unit(vec):
    v = np.asarray(vec, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


# ---------- Task 2: runner-up exposure in match_speaker ----------

def _make_service_with_speakers(monkeypatch, embeddings):
    """Build a SpeakerEmbeddingService with a pre-seeded embedding cache.

    Critical: `_load_known_embeddings` clears `_known_embeddings` on every
    call (services/speaker_embedding.py:59), so we monkeypatch it to a
    no-op after seeding the dict.
    """
    svc = SpeakerEmbeddingService()
    svc._known_embeddings = dict(embeddings)
    monkeypatch.setattr(svc, "_load_known_embeddings", lambda: None)
    return svc


def test_match_speaker_returns_runner_up_when_two_qualifying(monkeypatch):
    """With 2+ speakers above the runner-up threshold, returns 2nd-best."""
    svc = _make_service_with_speakers(monkeypatch, {
        "Pascal":  _unit([1.0, 0.0, 0.0, 0.0]),
        "Arnaud":  _unit([0.8, 0.6, 0.0, 0.0]),  # ~0.8 cosine to query
        "Fabrice": _unit([0.0, 0.0, 1.0, 0.0]),  # ~0.0 cosine → below 0.4 threshold
    })

    name, score, runner_up = svc.match_speaker(_unit([1.0, 0.0, 0.0, 0.0]))

    assert name == "Pascal"
    assert score > 0.99
    assert runner_up is not None
    assert runner_up["name"] == "Arnaud"
    assert 0.7 < runner_up["confidence"] < 0.85
    # Fabrice should NOT appear (below 0.4 threshold)
    assert runner_up["name"] != "Fabrice"


def test_match_speaker_returns_none_runner_up_when_only_one_speaker(monkeypatch):
    """Single-speaker registry has no possible runner-up."""
    svc = _make_service_with_speakers(monkeypatch, {
        "Pascal": _unit([1.0, 0.0, 0.0, 0.0]),
    })

    name, score, runner_up = svc.match_speaker(_unit([1.0, 0.0, 0.0, 0.0]))

    assert name == "Pascal"
    assert runner_up is None


def test_match_speaker_runner_up_below_threshold_returns_none(monkeypatch):
    """Runner-up below RUNNER_UP_THRESHOLD (0.4) is suppressed."""
    svc = _make_service_with_speakers(monkeypatch, {
        "Pascal":  _unit([1.0, 0.0, 0.0, 0.0]),
        "Fabrice": _unit([0.0, 0.0, 0.0, 1.0]),  # orthogonal, cosine = 0
    })

    name, score, runner_up = svc.match_speaker(_unit([1.0, 0.0, 0.0, 0.0]))

    assert name == "Pascal"
    assert runner_up is None  # Fabrice's 0.0 < 0.4 threshold


def test_match_speaker_returns_three_tuple_when_no_match(monkeypatch):
    """Even when no match qualifies, return shape is still 3-tuple (None, score, None)."""
    svc = _make_service_with_speakers(monkeypatch, {
        "Pascal": _unit([0.0, 0.0, 0.0, 1.0]),
    })

    result = svc.match_speaker(_unit([1.0, 0.0, 0.0, 0.0]))

    assert len(result) == 3
    name, score, runner_up = result
    assert name is None
    assert runner_up is None
```

Note: `_load_known_embeddings` clears `_known_embeddings` on every call (confirmed at `services/speaker_embedding.py:59`), hence the helper monkeypatches it to a no-op after seeding the cache. Do NOT skip that step — without it the test cache will be wiped by `match_speaker`'s first call.

- [ ] **Step 2: Run tests, watch them fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_re_refine.py -v
```
Expected: FAIL with `ValueError: too many values to unpack` (current `match_speaker` returns 2-tuple) or `TypeError`. Confirm the failure is the expected unpacking error, not an import error.

- [ ] **Step 3: Implement runner-up in `match_speaker`**

Edit `backend/services/speaker_embedding.py`:

1. Just before the `match_speaker` definition (~line 170-172), add the constant:
   ```python
   # Plan 5A: minimum cosine score for a 2nd-best candidate to be worth
   # suggesting in the Speaker Review reject-flow modal.
   RUNNER_UP_THRESHOLD = 0.4
   ```
   (Place it at module level if there's a constants section, or as a class attribute on `SpeakerEmbeddingService` next to `PREFER_GAP`. Class-attribute is fine and matches `PREFER_GAP` precedent.)

2. Change the return type hint of `match_speaker` from `Tuple[Optional[str], float]` to `Tuple[Optional[str], float, Optional[Dict[str, object]]]` (add `Dict` to the `typing` imports at the top of the file if not already imported).

3. Modify the per-speaker scoring loop to track the second-best as well:
   ```python
   best_name = None
   best_score = 0.0
   second_name = None
   second_score = 0.0
   for name, known_emb in pool.items():
       score = self.cosine_similarity(embedding, known_emb)
       if score > best_score:
           second_name, second_score = best_name, best_score
           best_name, best_score = name, score
       elif score > second_score:
           second_name, second_score = name, score
   ```

4. After the existing tiebreaker block (`if not restrict_to_names and prefer_names ...`), but before the final `if best_score >= SPEAKER_MATCH_THRESHOLD:` return:

   Build the runner-up dict (resolves `speaker_id` from `state.speaker_store`):
   ```python
   runner_up: Optional[Dict[str, object]] = None
   if second_name is not None and second_score >= self.RUNNER_UP_THRESHOLD and second_name != best_name:
       try:
           sp = state.speaker_store.get_by_name(second_name)
       except Exception:
           sp = None
       runner_up = {
           "speaker_id": sp["speaker_id"] if sp else None,
           "name": second_name,
           "confidence": round(second_score, 3),
       }
   ```

5. Update **both** return statements to return the 3-tuple:
   ```python
   if best_score >= SPEAKER_MATCH_THRESHOLD:
       return best_name, best_score, runner_up
   return None, best_score, runner_up
   ```

   Also update the two early-return `return None, 0.0` paths at the top of the function to `return None, 0.0, None`.

- [ ] **Step 4: Run tests, watch them pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_re_refine.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Update `auto_identify_speakers` and existing callers**

Two unpacking sites need updating (the test suite caught the first one; the rest are runtime):

1. `auto_identify_speakers` at `backend/services/speaker_embedding.py:398`:
   ```python
   matched_name, confidence, runner_up = self.match_speaker(
       emb,
       restrict_to_names=restrict_names,
       prefer_names=prefer_names,
   )
   ```
   Then add `"runner_up": runner_up` to both `results[label]` dict literals (the `if matched_name:` branch and the `else:` branch). For the "no embedding" fallback block (the `if label not in results:` loop), set `"runner_up": None`.

2. Grep for any other direct callers:
   ```bash
   cd ~/Development/apps/whisper-transcription-app/backend && grep -rn "match_speaker(" services/ routes/ tests/ 2>/dev/null | grep -v __pycache__
   ```
   For each runtime call site, expand the unpacking to 3-tuple (drop runner_up with `_` if unused). Test call sites that already use `match_speaker` are fine to update with `_` for runner_up.

- [ ] **Step 6: Run the full backend test suite to catch unpacking regressions**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -10
```
Expected: same baseline pass count from Task 1 Step 2 PLUS the 4 new tests. If any test fails with `too many values to unpack`, find the missed call site and fix it.

- [ ] **Step 7: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app && git stash push -m "plan5A-wip-speaker-embedding" -- backend/services/speaker_embedding.py 2>/dev/null || true
# (If the stash captured anything, re-apply task changes from memory — typically nothing was stashed since this task's edits are clean.)
git add backend/services/speaker_embedding.py backend/tests/test_re_refine.py
git commit -m "Plan 5A Task 2: match_speaker returns runner-up (2nd-best) candidate"
git stash list | grep -q "plan5A-wip-speaker-embedding" && git stash pop || true
```

If the stash pop produces conflicts, resolve them by keeping the WIP changes outside the `match_speaker` / `auto_identify_speakers` regions and the Task 2 changes inside those regions.

---

## Task 3: Extract `_apply_speaker_assignments` helper (refactor)

**Files:**
- Modify: `backend/routes/transcription.py:1006-1140` — extract the body of `POST /job/{id}/speakers/assign` into `_apply_speaker_assignments(job, assignments, audio_path=None) -> dict`
- Test: `backend/tests/test_speakers_api.py` (existing — re-run to confirm the refactor is behavior-preserving; if no tests exist for `/speakers/assign`, add a smoke test here in Task 3)

- [ ] **Step 1: Audit existing test coverage for `/speakers/assign`**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && grep -rn "speakers/assign\|assign_job_speakers" tests/ 2>/dev/null | grep -v __pycache__
```
Record what's covered. If `/speakers/assign` already has tests, the refactor's safety net is "old tests still pass". If NOT, before refactoring, add a minimal smoke test to `tests/test_re_refine.py` that hits `POST /job/{id}/speakers/assign` end-to-end via the test client with a stubbed embedding service (skip the actual audio extraction). The test only needs to verify: 200 response, `mapping` applied to `job.segments[*].speaker`, `results` array shape preserved.

- [ ] **Step 2: Write the helper signature test FIRST (TDD)**

Add to `backend/tests/test_re_refine.py`:

```python
# ---------- Task 3: _apply_speaker_assignments shared helper ----------

def test_apply_speaker_assignments_helper_exists_and_returns_results(
    icloud_base, sample_job, clean_speakers, monkeypatch
):
    """The helper extracted from /speakers/assign is callable and returns the
    same shape as the route used to return."""
    import state
    from routes.transcription import _apply_speaker_assignments
    from job_models import SpeakerAssignment

    job = state.job_store.get(sample_job)
    job.segments = [
        {"start": 0, "end": 5, "text": "hi",   "speaker": "SPEAKER_00"},
        {"start": 5, "end": 10, "text": "bonjour", "speaker": "SPEAKER_01"},
    ]
    job.speakers = [
        {"start": 0, "end": 5, "speaker": "SPEAKER_00"},
        {"start": 5, "end": 10, "speaker": "SPEAKER_01"},
    ]
    state.job_store.update(job)

    # Pre-create a speaker so the assignment doesn't need create_new.
    # `speaker_store.create(speaker_id, name, folder_path)` — see
    # backend/tests/test_stores.py:15 for the established pattern.
    import uuid as _uuid
    sid = str(_uuid.uuid4())
    state.speaker_store.create(sid, "Pascal Weber", "speakers/Pascal Weber")
    clean_speakers.append(sid)

    assignments = [SpeakerAssignment(label="SPEAKER_00", speaker_name="Pascal Weber", create_new=False)]

    out = _apply_speaker_assignments(job, assignments, audio_path=None)

    assert "mapping" in out and out["mapping"] == {"SPEAKER_00": "Pascal Weber"}
    assert "results" in out and len(out["results"]) == 1
    assert out["results"][0]["label"] == "SPEAKER_00"
    assert out["results"][0]["speaker_name"] == "Pascal Weber"
    # Side effect: segment label was rewritten in-place
    assert job.segments[0]["speaker"] == "Pascal Weber"
```

The `state.speaker_store.create(speaker_id, name, folder_path)` signature is confirmed in `backend/tests/test_stores.py:15` — no `create_minimal` helper exists. The folder doesn't need to physically exist for this test; the store only writes the DB row. (If a downstream call ends up doing `get_by_name` and reading the folder, the `icloud_base` fixture has already created `<base>/speakers/`.)

- [ ] **Step 3: Run test, watch it fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_re_refine.py::test_apply_speaker_assignments_helper_exists_and_returns_results -v
```
Expected: FAIL with `ImportError: cannot import name '_apply_speaker_assignments'`.

- [ ] **Step 4: Extract the helper (behavior-preserving refactor)**

Stash WIP first:
```bash
cd ~/Development/apps/whisper-transcription-app && git stash push -m "plan5A-wip-routes-transcription" -- backend/routes/transcription.py
```

Edit `backend/routes/transcription.py`. Define a new module-level function ABOVE `assign_job_speakers` (so the route can reference it):

```python
def _apply_speaker_assignments(
    job,
    assignments,
    audio_path: Optional[str] = None,
) -> dict:
    """Apply a list of SpeakerAssignment entries to a completed job.

    Shared between POST /job/{id}/speakers/assign (the legacy review flow)
    and POST /job/{id}/re-refine (Plan 5A new endpoint). For each assignment:
      - locate or create the speaker in the registry
      - extract a voice embedding from the longest matching turn if audio is
        on disk (register for new / EMA-update for existing)
      - rename the label in job.segments and job.speakers in-place
      - bump the speaker's call_count + total_speaking_time

    Returns:
        {
            "mapping": {old_label: new_name, ...},
            "results": [{label, speaker_id, speaker_name, created, ...}, ...],
        }

    Raises HTTPException on invalid input (400 for anonymous-name reuse, 404
    for missing speaker without create_new=true) — same status codes the
    legacy route raised.
    """
    from services.speaker_embedding import SPEAKERS_DIR as _SPEAKERS_DIR
    embedding_service = state.get_speaker_embedding_service()

    mapping: dict[str, str] = {}
    results = []

    for a in assignments:
        # ... PASTE the body of the for-loop from the legacy route here,
        # lines 1040-1112 (the per-assignment processing). Keep semantics
        # IDENTICAL — same HTTPException codes, same fields in `results`.

    # Apply rename in segments + turns + persist (lines 1115-1125 of legacy).
    if mapping:
        for seg in (job.segments or []):
            if seg.get("speaker") in mapping:
                seg["speaker"] = mapping[seg["speaker"]]
        for turn in (job.speakers or []):
            if turn.get("speaker") in mapping:
                turn["speaker"] = mapping[turn["speaker"]]
        try:
            state.jobs.update(job)
        except Exception:
            logger.warning("Failed to persist job after speaker rename", exc_info=True)

    return {"mapping": mapping, "results": results}
```

Then collapse the existing `assign_job_speakers` route to delegate:

```python
@router.post("/job/{job_id}/speakers/assign")
async def assign_job_speakers(
    job_id: str,
    req: AssignSpeakersRequest,
    background_tasks: BackgroundTasks,
):
    """Map anonymous diarization labels to named speakers in the registry.

    Thin wrapper around _apply_speaker_assignments — preserved for
    backwards compatibility. The new /re-refine route uses the same helper
    and adds a refinement re-run on top.
    """
    job = state.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed first")
    if not req.assignments:
        raise HTTPException(status_code=400, detail="No assignments provided")

    audio_path = _resolve_job_audio_path(job_id)
    out = _apply_speaker_assignments(job, req.assignments, audio_path=audio_path)

    # Kick off insight extraction in the background (legacy behavior).
    insight_scheduled = False
    if req.extract_insights and state.deliverable_available:
        background_tasks.add_task(_extract_speaker_insights_sync, job_id)
        insight_scheduled = True

    return {
        "job_id": job_id,
        "assignments": out["results"],
        "insight_extraction_scheduled": insight_scheduled,
        "segments": job.segments,
        "speakers": sorted({s.get("speaker") for s in (job.segments or []) if s.get("speaker")}),
    }
```

- [ ] **Step 5: Run tests, watch them pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_re_refine.py tests/test_speakers_api.py -v
```
Expected: the new helper test passes AND all existing `test_speakers_api.py` tests still pass (proving the refactor is behavior-preserving).

- [ ] **Step 6: Run the full backend test suite**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -10
```
Expected: baseline from Task 1 Step 2 + Task 2's 4 tests + this task's 1 new test.

- [ ] **Step 7: Commit + restore WIP stash**

```bash
cd ~/Development/apps/whisper-transcription-app && git add backend/routes/transcription.py backend/tests/test_re_refine.py
git commit -m "Plan 5A Task 3: extract _apply_speaker_assignments helper from /speakers/assign route"
git stash list | grep -q "plan5A-wip-routes-transcription" && git stash pop || true
```

If `git stash pop` produces conflicts, resolve manually — the WIP changes are in different regions than the refactored `_apply_speaker_assignments` + `assign_job_speakers` blocks. Use `git diff` to inspect each conflict marker and keep both.

---

## Task 4: Add `POST /job/{id}/re-refine` endpoint

**Files:**
- Modify: `backend/routes/transcription.py` — add new route after `assign_job_speakers`
- Test: `backend/tests/test_re_refine.py` — add the four integration tests required by the plan spec

- [ ] **Step 1: Write the four failing integration tests**

Add to `backend/tests/test_re_refine.py`:

```python
# ---------- Task 4: POST /job/{id}/re-refine endpoint ----------
# Note: `client` fixture (conftest.py:115) is an httpx.AsyncClient over the
# real FastAPI app via ASGITransport. asyncio_mode = "auto" in pytest.ini
# (line 62) so @pytest.mark.asyncio is implicit — but doesn't hurt to keep.

import uuid


async def test_re_refine_happy_path_mixed_assignments(
    icloud_base, sample_job, clean_speakers, client, monkeypatch
):
    """Happy path: confirm an existing match + create a new speaker + strip another to unknown."""
    import state
    from unittest.mock import MagicMock

    job = state.job_store.get(sample_job)
    job.segments = [
        {"start": 0, "end": 5, "text": "hi", "speaker": "Pascal"},
        {"start": 5, "end": 10, "text": "bonjour", "speaker": "SPEAKER_01"},
        {"start": 10, "end": 15, "text": "ciao", "speaker": "Arnaud"},
    ]
    job.speakers = [
        {"start": 0, "end": 5, "speaker": "Pascal"},
        {"start": 5, "end": 10, "speaker": "SPEAKER_01"},
        {"start": 10, "end": 15, "speaker": "Arnaud"},
    ]
    job.status = "completed"
    state.job_store.update(job)

    # Pre-seed a speaker for the "confirm existing" path
    pascal_id = state.speaker_store.create(str(uuid.uuid4()), "Pascal", "speakers/Pascal")
    clean_speakers.append(pascal_id)

    # Stub the executor so we don't actually fire the refinement worker
    submit_mock = MagicMock()
    monkeypatch.setattr(state, "transcription_executor", MagicMock(submit=submit_mock))

    # Stub embedding extraction so the "new:Fabrice" path doesn't need real audio
    fake_emb = MagicMock()
    monkeypatch.setattr(
        state, "get_speaker_embedding_service",
        lambda: MagicMock(
            extract_embedding=MagicMock(return_value=fake_emb),
            register_speaker=MagicMock(return_value="fabrice-uuid"),
        ),
        raising=False,
    )

    body = {
        "speaker_assignments": {
            "Pascal":      pascal_id,          # confirm existing
            "SPEAKER_01":  "new:Fabrice Dubois",  # create new + embed
            "Arnaud":      "unknown",          # strip back to anonymous
        }
    }
    resp = await client.post(f"/job/{sample_job}/re-refine", json=body)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["job_id"] == sample_job
    assert data["status"] == "refining"
    assert data["phase"] == "refining"
    assert data["speakers_assigned"] == 3
    assert any(c["name"] == "Fabrice Dubois" for c in data["speakers_created"])

    # Refinement was dispatched on the executor
    submit_mock.assert_called_once()
    args = submit_mock.call_args[0]
    # _run_refinement_for_job(job_id, speaker_ids, context_path, audio_path)
    assert args[1] == sample_job

    # Job state was reset
    job_after = state.job_store.get(sample_job)
    assert job_after.refinement_status == "pending"
    assert job_after.phase == "refining"


async def test_re_refine_409_when_job_not_completed(
    icloud_base, sample_job, async_client
):
    """409 if the job hasn't reached `completed`."""
    import state
    job = state.job_store.get(sample_job)
    job.status = "processing"
    state.job_store.update(job)

    resp = await client.post(
        f"/job/{sample_job}/re-refine",
        json={"speaker_assignments": {"SPEAKER_00": "unknown"}},
    )
    assert resp.status_code == 409
    assert "completed" in resp.text.lower()


async def test_re_refine_400_when_speaker_id_invalid(
    icloud_base, sample_job, client, monkeypatch
):
    """400 if a target speaker_id doesn't exist in the registry."""
    import state
    from unittest.mock import MagicMock

    job = state.job_store.get(sample_job)
    job.segments = [{"start": 0, "end": 5, "text": "hi", "speaker": "SPEAKER_00"}]
    job.status = "completed"
    state.job_store.update(job)

    monkeypatch.setattr(state, "transcription_executor", MagicMock(submit=MagicMock()))

    resp = await client.post(
        f"/job/{sample_job}/re-refine",
        json={"speaker_assignments": {"SPEAKER_00": "nonexistent-uuid"}},
    )
    assert resp.status_code == 400
    assert "speaker" in resp.text.lower()


def test_runner_up_propagated_through_auto_identify(monkeypatch):
    """auto_speaker_matches entries include runner_up when registry has ≥2."""
    svc = _make_service_with_speakers(monkeypatch, {
        "Pascal":  _unit([1.0, 0.0, 0.0, 0.0]),
        "Arnaud":  _unit([0.8, 0.6, 0.0, 0.0]),
    })

    # Stub extract_speaker_embeddings to return one query embedding
    monkeypatch.setattr(
        svc, "extract_speaker_embeddings",
        lambda audio_path, turns: {"SPEAKER_00": _unit([1.0, 0.0, 0.0, 0.0])},
    )
    # Stub speaker_store.get_by_name to avoid DB requirement
    import state
    monkeypatch.setattr(state.speaker_store, "get_by_name",
                        lambda n: {"speaker_id": f"id-{n}"} if n in ("Pascal", "Arnaud") else None)
    monkeypatch.setattr(svc, "save_unknown_embedding", lambda *a, **k: None)

    result = svc.auto_identify_speakers(
        audio_path="/fake.wav",
        speaker_turns=[{"start": 0, "end": 5, "speaker": "SPEAKER_00"}],
        job_id="job-T",
    )

    assert "SPEAKER_00" in result
    entry = result["SPEAKER_00"]
    assert entry["matched"] is True
    assert entry["name"] == "Pascal"
    assert "runner_up" in entry  # field is always present (may be None)
    assert entry["runner_up"] is not None
    assert entry["runner_up"]["name"] == "Arnaud"
```

Add `import uuid` to the top of the file if not present. Adjust `from main import app` to whatever the actual FastAPI app entrypoint is (check `backend/main.py` or grep for `FastAPI(`).

- [ ] **Step 2: Run tests, watch them fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_re_refine.py -v 2>&1 | tail -20
```
Expected: the 4 new tests fail with 404 (route doesn't exist yet) — except `test_runner_up_propagated_through_auto_identify` which exercises Task 2's code path and should fail with `KeyError: 'runner_up'` if the auto_identify update was incomplete. If the runner-up test passes already, great — the wiring from Task 2 carried through.

- [ ] **Step 3: Implement `POST /job/{id}/re-refine`**

Stash WIP first:
```bash
cd ~/Development/apps/whisper-transcription-app && git stash push -m "plan5A-wip-routes-transcription" -- backend/routes/transcription.py
```

Edit `backend/routes/transcription.py`. Add a new pydantic request model near `AssignSpeakersRequest` (~line 953):

```python
class ReRefineRequest(BaseModel):
    speaker_assignments: dict[str, str]
    # value is one of: existing speaker_id, "unknown", or "new:<name>"
```

Add the new route after `assign_job_speakers`:

```python
@router.post("/job/{job_id}/re-refine")
async def re_refine_job(job_id: str, req: ReRefineRequest):
    """Apply post-completion speaker corrections and re-run refinement.

    Plan 5A. Accepts a speaker_assignments map where each value is one of:
      - an existing speaker_id (re-attribute the label to that speaker)
      - "unknown" (strip the label back to its original anonymous form)
      - "new:<name>" (create the speaker with a voice embedding from
        the longest matching turn, then attribute the label)

    Returns 404 if job not found, 409 if job not completed (or audio
    unavailable for a "new:" entry), 400 if a target speaker_id is
    invalid / a "new:" name is malformed / a label is not in segments.
    """
    job = state.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail=f"Job must be completed (currently {job.status!r})")
    if not req.speaker_assignments:
        raise HTTPException(status_code=400, detail="No speaker_assignments provided")

    # Validate every label appears in job.segments
    known_labels = {s.get("speaker") for s in (job.segments or []) if s.get("speaker")}
    for label in req.speaker_assignments:
        if label not in known_labels:
            raise HTTPException(status_code=400, detail=f"Label {label!r} not in job segments")

    audio_path = _resolve_job_audio_path(job_id)
    embedding_service = state.get_speaker_embedding_service()
    speakers_created: list[dict] = []

    # Build the SpeakerAssignment list the shared helper expects.
    # Translate "unknown" → keep label as-is (no rename). Translate "new:name"
    # → register speaker first, then pass speaker_name to the helper.
    # Track which labels are being stripped to "Unknown" so we can rename
    # them in segments + omit them from the refinement speaker_ids union.
    unknown_labels: list[str] = []
    # Per-label counter to keep multiple unknowns distinguishable
    # (Unknown_1, Unknown_2 ...) — re-refinement needs distinct labels so
    # Sonnet doesn't collapse different real speakers into one.
    unknown_counter = 0

    helper_assignments = []
    for label, target in req.speaker_assignments.items():
        if target == "unknown":
            unknown_counter += 1
            unknown_labels.append(label)
            continue
        if target.startswith("new:"):
            new_name = target[4:].strip()
            if not new_name or _is_anonymous_label(new_name):
                raise HTTPException(status_code=400, detail=f"Invalid new speaker name: {new_name!r}")
            # We need audio to extract an embedding for the "new" path.
            longest = _longest_turn_for_label(job.speakers or job.segments or [], label)
            if not audio_path or not longest or (longest["end"] - longest["start"]) < 2.0:
                raise HTTPException(
                    status_code=409,
                    detail=f"Audio unavailable for new speaker {new_name!r} (label {label})",
                )
            try:
                emb = embedding_service.extract_embedding(audio_path, longest["start"], longest["end"])
                new_sid = embedding_service.register_speaker(new_name, emb)
            except Exception as e:
                logger.exception("Failed to register new speaker %s", new_name)
                raise HTTPException(status_code=409, detail=f"Failed to register speaker: {e}")
            speakers_created.append({"speaker_id": new_sid, "name": new_name})
            helper_assignments.append(SpeakerAssignment(label=label, speaker_name=new_name, create_new=False))
            continue
        # Otherwise it's an existing speaker_id — validate + look up the name.
        try:
            sp = state.speaker_store.get(target)
        except Exception:
            sp = None
        if not sp or not sp.get("name"):
            raise HTTPException(status_code=400, detail=f"Invalid speaker_id: {target!r}")
        helper_assignments.append(SpeakerAssignment(label=label, speaker_name=sp["name"], create_new=False))

    # Apply via the shared helper (handles segment/turn rename + DB updates).
    if helper_assignments:
        _apply_speaker_assignments(job, helper_assignments, audio_path=audio_path)

    # Strip unknown labels to anonymous form. Use stable indices so distinct
    # rejected speakers stay distinct in the re-refined transcript.
    if unknown_labels:
        anon_map = {lbl: f"Unknown_{i+1}" for i, lbl in enumerate(unknown_labels)}
        for seg in (job.segments or []):
            if seg.get("speaker") in anon_map:
                seg["speaker"] = anon_map[seg["speaker"]]
        for turn in (job.speakers or []):
            if turn.get("speaker") in anon_map:
                turn["speaker"] = anon_map[turn["speaker"]]
        try:
            state.jobs.update(job)
        except Exception:
            logger.warning("Failed to persist job after unknown-label strip", exc_info=True)

    # Build the speaker_ids list for refinement (union of all assigned targets).
    speaker_ids: list[str] = []
    for target in req.speaker_assignments.values():
        if target == "unknown":
            continue
        if target.startswith("new:"):
            # Find the corresponding created id
            name = target[4:].strip()
            sp = state.speaker_store.get_by_name(name)
            if sp:
                speaker_ids.append(sp["speaker_id"])
        else:
            speaker_ids.append(target)
    speaker_ids = list(dict.fromkeys(speaker_ids))  # dedupe, preserve order

    # Reset refinement state so the UI polling re-renders correctly.
    from routes.refinement import _set_refinement_status, _run_refinement_for_job
    from services.transcription import _update_job
    _set_refinement_status(job, "pending")
    _update_job(job, phase="refining")

    # Dispatch refinement on the same executor pool the orchestrator uses.
    context_path = (job.settings.context_path if getattr(job, "settings", None) else None)
    state.transcription_executor.submit(
        _run_refinement_for_job, job_id, speaker_ids, context_path, audio_path,
    )

    return {
        "job_id": job_id,
        "status": "refining",
        "phase": "refining",
        "speakers_created": speakers_created,
        "speakers_assigned": len(req.speaker_assignments),
    }
```

Make sure `SpeakerAssignment` is imported at the top of the file (it's already used as part of `AssignSpeakersRequest` — check the imports near `job_models`).

- [ ] **Step 4: Run tests, watch them pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_re_refine.py -v 2>&1 | tail -30
```
Expected: all 4 Task 4 tests pass, plus the 4 Task 2 tests and 1 Task 3 test from earlier still pass (9 total in `test_re_refine.py`).

If a test fails:
- **Happy path 404** — the route isn't registered. Confirm the `@router.post` decorator is inside `backend/routes/transcription.py` and the file's router is included in `backend/main.py`.
- **Happy path validation error on body shape** — pydantic schema mismatch. Use `print(resp.text)` to see the 422 detail.
- **400 invalid speaker_id test PASSES on 200 instead** — the lookup branch isn't validating; double-check `state.speaker_store.get(target)` actually returns `None` for unknown ids (some implementations raise instead — wrap in try/except as shown).
- **runner_up test KeyError** — Task 2 Step 5 didn't propagate the field through the no-embedding fallback path. Re-check the `if label not in results:` block in `auto_identify_speakers`.

- [ ] **Step 5: Run the full backend test suite**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -10
```
Expected: baseline + 9 new tests, all passing.

- [ ] **Step 6: Commit + restore WIP stash**

```bash
cd ~/Development/apps/whisper-transcription-app && git add backend/routes/transcription.py backend/tests/test_re_refine.py
git commit -m "Plan 5A Task 4: POST /job/{id}/re-refine endpoint with assignment + dispatch"
git stash list | grep -q "plan5A-wip-routes-transcription" && git stash pop || true
```

Resolve any stash-pop conflicts the same way as Task 3 — WIP changes live outside the `_apply_speaker_assignments` / `assign_job_speakers` / `re_refine_job` regions.

---

## Task 5: Full backend suite + manual smoke + sign-off

**Files:**
- None (verification only)

- [ ] **Step 1: Run the full backend test suite, cold**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -q 2>&1 | tail -15
```
Expected: baseline pass count from Task 1 Step 2, PLUS 9 new tests in `test_re_refine.py`, ALL green. Aim for ~370+ passing.

If any pre-existing test now fails, investigate — most likely cause is a `match_speaker` call site missed in Task 2 Step 5. Grep again:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && grep -rn "match_speaker(" services/ routes/ tests/ 2>/dev/null | grep -v __pycache__
```

- [ ] **Step 2: Restart backend + smoke the new endpoint manually**

Run:
```bash
launchctl kickstart -k gui/$(id -u)/com.whisper.backend && sleep 3 && tail -20 ~/.whisper-backend.log
```
Expected: clean startup, no import errors, no traceback referencing `match_speaker` arity.

Then hit the new endpoint against a completed job (replace `<JOB_ID>` with a real completed job id from `~/.whisper_transcription_jobs.db` or the frontend):
```bash
curl -s -X POST "http://localhost:8000/job/<JOB_ID>/re-refine" \
  -H "Content-Type: application/json" \
  -d '{"speaker_assignments":{"SPEAKER_00":"unknown"}}' | python3 -m json.tool
```
Expected: JSON response with `status: "refining"`, `phase: "refining"`, `speakers_created: []`, `speakers_assigned: 1`. Then tail the backend log to see the refinement actually dispatched.

- [ ] **Step 3: Verify `auto_speaker_matches` runner_up appears on a fresh job (optional)**

If you have a completed job with multiple speakers, GET it and confirm:
```bash
curl -s "http://localhost:8000/job/<JOB_ID>" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('auto_speaker_matches', {}), indent=2))"
```
Expected: each match dict includes a `runner_up` key (value may be null for single-speaker registries or sub-threshold runners-up).

- [ ] **Step 4: Sign-off checklist**

Confirm before declaring Plan 5A done:
- [ ] Full backend test suite green (Task 5 Step 1)
- [ ] `match_speaker` returns a 3-tuple at all return paths (early + match + no-match)
- [ ] `auto_speaker_matches` entries include `runner_up` key (None or dict)
- [ ] `_apply_speaker_assignments(job, assignments, audio_path)` is a module-level callable
- [ ] `POST /job/{id}/speakers/assign` still works (existing tests + manual smoke)
- [ ] `POST /job/{id}/re-refine` returns 200 happy / 404 missing / 409 not-completed / 400 invalid
- [ ] Backend restarts cleanly via launchctl (Task 5 Step 2)
- [ ] No new pyright errors: `cd backend && ./venv/bin/python -m pyright services/speaker_embedding.py routes/transcription.py 2>&1 | tail -5` (if pyright is wired up; skip if not configured)

- [ ] **Step 5: Final commit (if anything changed during smoke)**

Most likely nothing new to commit at this step. If you tweaked anything based on smoke output:
```bash
cd ~/Development/apps/whisper-transcription-app && git add <exact files>
git commit -m "Plan 5A Task 5: smoke fixes + final polish"
```

If nothing changed, skip the commit. Report Plan 5A complete and ready for Sub-plan B (frontend) to begin.

---

## Acceptance criteria

Plan 5A ships when:

1. `SpeakerEmbeddingService.match_speaker` returns `(name, score, runner_up_dict | None)` at every return path, with `runner_up` populated only when there's a 2nd-best speaker scoring ≥ `RUNNER_UP_THRESHOLD = 0.4`.
2. `auto_identify_speakers` propagates `runner_up` into each entry of `auto_speaker_matches` (None when no runner-up qualifies). All existing fields (`matched`, `speaker_id`, `name`, `confidence`, `source`, `note`) are preserved unchanged.
3. `_apply_speaker_assignments(job, assignments, audio_path)` is a module-level callable in `backend/routes/transcription.py` shared by both `POST /job/{id}/speakers/assign` (unchanged external behavior) and the new `POST /job/{id}/re-refine`.
4. `POST /job/{id}/re-refine` accepts `{speaker_assignments: {label: speaker_id | "unknown" | "new:name"}}`, handles all three target shapes correctly, dispatches `_run_refinement_for_job` via `state.transcription_executor.submit`, and returns the documented response with correct error codes (404 / 409 / 400).
5. Backend test suite green (~370+ tests including 9 new tests in `test_re_refine.py`).
6. No regression in `/speakers/assign` external behavior — existing test files (`test_speakers_api.py`, `test_inline_auto_match.py`, `test_speaker_auto_match_scope.py`) still pass.
