# Backend Seam Tidy-Up — Design (Vague B)

**Date:** 2026-06-20
**Source:** architecture audit (Graphify × Fallow × deletion-test), cards S4 + S5 (`Worth exploring`).
**Status:** approved (design decisions confirmed by user).

## Goal

Two small, behaviour-preserving backend deepenings:
1. **S5 — invert the orchestrator→route dependency** so a service no longer reaches into a route module.
2. **S6 — give the `state.py` shared seam a typed façade** so routes stop reaching into bare module globals.

Both are guarded by the existing backend suite (403 passed, 3 skipped on `dev`).

## Context (current state on `dev`)

- `backend/services/orchestrator.py` already extracts finalization into module functions: `_finalize_after_alignment` (L187), `_all_labels_matched` (L136), `_dispatch_refinement` (L156). The only friction is the lazy `from routes.refinement import dispatch_refinement_for_job` inside `_dispatch_refinement` (L160) — a service importing a route.
- `backend/routes/refinement.py:37` `dispatch_refinement_for_job(...)` references only `state.refinement_store`, `state.transcription_executor`, and a lazy `from services.transcription import _update_job`. It does NOT touch the router or `app` — it is service logic misplaced in a route file.
- `backend/state.py` (168 lines) holds module-level globals: stores (`job_store`/`jobs` alias, `batch_jobs`, `multimodal_jobs`, `speaker_store`, `call_speaker_store`, `call_metadata_store`), model flags (`whisper_model_path`, `whisper_model_ready`, `diarization_pipeline`, parakeet), refinement (`refinement_available`, `refinement_service`, `refinement_store`), deliverable (`deliverable_service`, `deliverable_available`), `transcription_executor`, `startup_time`, and `get_speaker_embedding_service()`.
- Routes reach into `state.*` directly: ~190 call sites across 8 route files (transcription 58, calls 36, refinement 33, models_api 14, speakers 13, multimodal 11, jpr 10, recordings 2).

## S5 — Invert the orchestrator→route dependency

**Architecture.** Create `backend/services/refinement_dispatch.py`. Move the body of `dispatch_refinement_for_job` there (it depends only on `state` and the lazy `services.transcription._update_job` — no new cycle). Both `routes/refinement.py` and `services/orchestrator.py` import `dispatch_refinement_for_job` from the new service. Remove the lazy `from routes.refinement import …` in `orchestrator._dispatch_refinement`.

**Finalization.** Keep `_finalize_after_alignment` and `_all_labels_matched` as functions (already extracted). Add unit tests covering: all-labels-matched path, unresolved path → `speaker_review_status`, and the refinement-policy decision (`should_refine` honored / `refinement_available` gate).

**Interface produced:**
```python
# backend/services/refinement_dispatch.py
def dispatch_refinement_for_job(job, settings, audio_path: Optional[str], *, mode: str = ...) -> None
```
(Match the real current signature in routes/refinement.py:37 verbatim.)

**Dependency direction (after):**
```
services/refinement_dispatch.py
   ↑ import            ↑ import
routes/refinement.py   services/orchestrator.py
```
No service→route import remains.

**Gate:** full `python -m pytest tests/ --timeout=60` green; new finalization tests green.

## S6 — Typed façade `app_state`

**Architecture.** Create `backend/app_state.py` exposing a typed accessor surface over the existing `state.py` globals. `state.py` remains the implementation (backing globals); the façade reads from it. Migrate all ~190 `state.X` accesses in the 8 route files to `app_state.X()`.

**Interface produced (accessors over current globals):**
```python
# backend/app_state.py  (names match state.py; () accessor form)
def jobs() -> JobStore                      # state.job_store (alias state.jobs)
def batch_jobs() -> BoundedDict             # state.batch_jobs
def multimodal_jobs() -> BoundedDict        # state.multimodal_jobs
def speaker_store() -> SpeakerStore
def call_speaker_store() -> CallSpeakerStore
def call_metadata_store() -> CallMetadataStore
def refinement_store() -> RefinementStore
def refinement_service()                    # state.refinement_service
def deliverable_service()                   # state.deliverable_service
def executor() -> ThreadPoolExecutor        # state.transcription_executor
def speaker_embedding_service()             # state.get_speaker_embedding_service()
def is_ready_to_transcribe() -> bool        # whisper_model_ready and diarization_pipeline
def refinement_available() -> bool          # state.refinement_available
def deliverable_available() -> bool         # state.deliverable_available
def startup_time() -> float | None
```
Scalar/model flags that are read-only checks (`whisper_model_ready`, etc.) are exposed via the predicates above; routes no longer read the raw flags. The migration is mechanical and behaviour-preserving.

**Testability.** The façade is the single typed seam to mock. Existing tests that monkeypatch `state.*` stay valid because `state.py` is unchanged — the façade reads through to the same globals.

**Gate:** full `python -m pytest tests/ --timeout=60` green.

## Sequencing & AFK execution

- **Order:** S5 first, then S6. S6 migrates `routes/refinement.py`, which S5 also edits — sequential avoids a self-conflict.
- **Worktree base fix:** create worktrees manually from `dev` HEAD (`git worktree add` per `using-git-worktrees`) rather than the Agent tool's auto-isolation, which previously forked a stale commit (`1b062a8`). Each agent starts from current `dev`.
- **Autonomy:** agents execute their plan with TDD, verify green, commit on their branch; the coordinator merges into `dev` with re-verification (merge-and-verify), as in Vague A.

## Non-goals (YAGNI)

- No `TranscriptionFinalizer`/`RefinementDispatcher` classes — the functions already work; classes would add ceremony.
- No FastAPI `Depends` injection — rejected for blast radius; the façade is the lighter seam.
- No change to `state.py` global semantics or initialization order.
- No frontend changes.

## Verification

- Backend suite must stay green at every step: `cd backend && ./venv/bin/python -m pytest tests/ --timeout=60 -q`.
- After each slice merges into `dev`, re-run the full suite on the integrated tree.
- Confirm no `from routes.` import remains in `services/` (S5): `grep -rn "from routes" backend/services/` → empty.
- Confirm no `state.` access remains in routes after S6: `grep -rn "state\." backend/routes/` → only imports of the `state` module by the façade, not raw field access (the façade lives in `app_state.py`, not in routes).
