# Pre-Refinement Speaker Resolution Gate — Design

**Date**: 2026-05-19
**Status**: Approved for planning
**Predecessor**: Plan 5 (post-completion Speaker Review + re-refine) — shipped 2026-05-17.

---

## Goal

Insert a **user gate** between transcription/alignment and Sonnet refinement. The user resolves speaker identity once, against full B5 voice match information, before refinement consumes the speaker profiles as context. This replaces the "rétroactif" model where refinement runs first with B5-only matches and the user corrects after — a model that proved fragile in practice (post-refinement overlays renamed labels in segments + pyannote turns, voice embeddings stayed null for known profiles, re-refinement burned 10+ minutes of Sonnet for a second pass).

## Why this is necessary

Plan 5's post-completion model has shipped 6+ blocker bugs in 2 days, all rooted in the same architectural issue: **Sonnet refinement runs before the user has confirmed who's who, then B7 learning overlays rename labels in place, leaving the post-completion panel showing labels that no longer exist in any backend data structure**.

Concrete failures observed:
- David Marchesseau + Pascal Weber profiles `embedding_path=null` despite multiple "Apply & re-refine" attempts — the helper's label-based audio lookup couldn't find them after the overlay renamed everything.
- Panel showed `SPEAKER_00`/`SPEAKER_01` from a pre-overlay snapshot; backend's `job.segments` AND `job.speakers` (pyannote turns) had been renamed → strict validation 400'd the submit.
- Re-refinement ran Sonnet a 2nd time (10+ min) just to re-do work it should have done correctly the first time.

The user proposed (and validated through pain): **resolve speakers FIRST, then refine ONCE with correct context**.

## Decisions from brainstorming (2026-05-19)

| Decision | Choice | Rationale |
|---|---|---|
| Auto-confirm threshold | **Hybride** — pause IF any anonymous label exists, else auto-proceed | All-matched runs are common (regular interlocutors); pausing for those would slow the happy path |
| AFK behavior | **Pause indefinitely** | Single-user dev app; the user can always come back |
| Pre-picked speakers from Settings | Continue to feed Sonnet's refinement context; B5 voice match is still the assignment mechanism | Pre-pick is a hint, not an assignment |
| Audio playback in panel | Out of scope (defer) | UX nice-to-have, not needed for v1 |
| Bulk fix for existing jobs | Out of scope; manual script if needed | Existing jobs already past the gate — separate concern |

## Architecture

### Pipeline lifecycle change

```
diarizing → transcribing → aligning → [GATE]
                                         │
                                         ├── all labels matched by B5 ──→ resolved=true, refining → learning → None
                                         │
                                         └── ≥1 anonymous label ──→ phase=awaiting_speakers (job stays here)
                                                                       ↓ user clicks Confirm
                                                                    resolved=true, refining → learning → None
```

The orchestrator (`backend/services/orchestrator.py`) splits its post-alignment behavior:
- After `assign_speakers_to_segments` (Best) or `assign_speakers_time_proportional` (Quick) finishes
- After B5 inline auto-match populates `auto_speaker_matches`
- Check: are all segment labels either non-anonymous OR matched by B5?
  - **Yes**: set `job.speakers_resolved=True`, dispatch refinement as today
  - **No**: set `job.phase="awaiting_speakers"`, set `job.status="completed"`, leave `speakers_resolved=False`, DO NOT dispatch refinement. Return.

The job is now "completed" from the transcription perspective — the transcript is fully usable (with anonymous labels). Refinement waits for user action.

### New job fields

`backend/job_models.py` — extend `TranscriptionJob`:

```python
class TranscriptionJob:
    def __init__(self, job_id: str):
        ...
        # Plan 7: speaker resolution gate. False until the orchestrator
        # auto-resolves (all B5-matched) or the user submits assignments
        # via POST /job/{id}/confirm-speakers. Refinement is gated on this.
        self.speakers_resolved = False
```

Phase lifecycle table gains `awaiting_speakers`:
- Allowed values: `None | "diarizing" | "transcribing" | "aligning" | "awaiting_speakers" | "refining" | "learning"`
- Transition: `aligning` → `awaiting_speakers` (when user-action needed) → `refining` (post-confirm)

### Decision logic

In `orchestrator.py`, after alignment + B5 inline auto-match:

```python
def _all_labels_matched(job) -> bool:
    """True iff every distinct speaker label in segments is either a
    non-anonymous name OR has an `auto_speaker_matches` entry with
    matched=True. Both conditions mean we know who they are."""
    matches = job.auto_speaker_matches or {}
    for seg in (job.segments or []):
        label = seg.get("speaker")
        if not label:
            continue
        # Already a real name (Sonnet didn't run yet, so these come from B5
        # inline rename only).
        if not is_anonymous_label(label):
            continue
        # Anonymous label — must have a high-conf B5 voice match.
        if not matches.get(label, {}).get("matched"):
            return False
    return True

# In orchestrator main flow, after alignment:
if _all_labels_matched(job):
    job.speakers_resolved = True
    _update_job(job, phase=None, status="completed")
    _dispatch_refinement_if_eligible(job)  # existing auto-refine path
else:
    _update_job(
        job,
        status="completed",
        phase="awaiting_speakers",
        message="Waiting for speaker resolution",
    )
    # Don't dispatch refinement. Frontend will surface the panel,
    # POST /job/{id}/confirm-speakers will dispatch it.
```

### New endpoint: `POST /job/{job_id}/confirm-speakers`

Request body — same shape as the existing `/re-refine` endpoint for consistency:

```json
{
  "speaker_assignments": {
    "SPEAKER_00": "uuid-david",         // assign to existing profile
    "SPEAKER_01": "uuid-pascal",        // assign to existing profile
    "SPEAKER_02": "new:Fabrice Dubois", // create new profile + save voice
    "SPEAKER_03": "ignore"              // leave anonymous, no profile
  }
}
```

Action types:
- **UUID string** → assign to existing profile, extract voice from this session's segments matching the label, save embedding (EMA-update if profile already has one)
- **`"new:name"`** → create new profile with this name, extract voice, save embedding
- **`"ignore"`** → leave the label as-is in segments (anonymous). No profile change. No embedding extraction. The refinement still runs but treats this label as unknown.

Response:
```json
{
  "job_id": "...",
  "status": "processing",
  "phase": "refining",
  "speakers_created": [{"speaker_id": "...", "name": "..."}],
  "speakers_assigned": 3,
  "speakers_ignored": 1
}
```

Failures:
- `404` — job not found
- `409` — `speakers_resolved=true` already (user submitted twice; idempotent error message tells them refinement is already in progress)
- `409` — `status != "completed"` (transcription still in flight; can't resolve speakers yet)
- `400` — label not in segments AND not in pyannote turns AND not retrievable by name (truly bogus)
- `400` — `"new:name"` with malformed name

### Endpoint behavior

1. Validate job state (404/409).
2. For each assignment, build internal `SpeakerAssignment` records:
   - `"ignore"` → skip embedding extraction, don't add to assignment list (segments stay anonymous).
   - UUID → look up speaker name from registry, build `SpeakerAssignment(label, speaker_name=name, create_new=False)`.
   - `"new:name"` → `SpeakerAssignment(label, speaker_name=name, create_new=True)`.
3. Call `_apply_speaker_assignments(job, helper_assignments, audio_path=audio_path)`. The helper handles voice extraction (with the name-based fallback from commit `19f9450`), embedding save, segment rename.
4. Set `job.speakers_resolved = True`.
5. Set `job.phase = "refining"`.
6. Dispatch `_run_refinement_for_job` via `state.transcription_executor` (same pattern as `/re-refine` and orchestrator).
7. Return.

### Re-using the existing `/re-refine` endpoint

The existing `POST /job/{job_id}/re-refine` stays. Use case: user notices Sonnet mis-identified someone after refinement completes. The panel transforms post-refinement to show a "Apply & re-refine" button instead of "Confirm speakers".

The two endpoints share the helper but have different state preconditions:
- `/confirm-speakers`: job has `speakers_resolved=False`. Sets it true. Dispatches refinement.
- `/re-refine`: job has `speakers_resolved=True` AND `refinement_status=done`. Re-dispatches refinement.

### Frontend changes

**Phase pill** (`src/components/PhasePill.tsx`):
- Add `awaiting_speakers` → "Awaiting speakers" label, yellow/amber color (matches "needs attention" semantics).

**`SpeakerReviewPanel.tsx`** — three sections instead of two:

```
┌─────────────────────────────────────────────────────────────┐
│ Speaker Review                                              │
│                                                             │
│ ── Matched (auto-confirmed) ──                              │
│   • David Marchesseau  (conf 92%)   [Reject]               │
│   • Pascal Weber       (conf 87%)   [Reject]               │
│                                                             │
│ ── Known profiles, no voice yet ──                          │
│   • SPEAKER_02         [Pick from registry ▼]              │
│                                                             │
│ ── Unknown ──                                               │
│   • SPEAKER_03         [Create new: ___] [Ignore]          │
│                                                             │
│ Pending corrections: 2                                      │
│ [Confirm speakers]   [Discard changes]                      │
└─────────────────────────────────────────────────────────────┘
```

Section classification per label:
- **Matched**: `autoMatches[label]?.matched === true` (B5 voice match)
- **Known profiles, no voice**: `isAnonymousLabel(label) && !autoMatches[label]?.matched && registry.length > 0` — user picks via dropdown
- **Unknown**: same as known-profiles section visually, but actions emphasize "Create new" or "Ignore"

In practice Section B and C are similar — both show anonymous labels with a registry picker + create input + ignore button. The split is a visual nice-to-have; v1 can render them as a single "Unresolved" section with all three actions inline.

**Submit button label** — context-aware:
- Pre-refinement (`speakers_resolved=false`, `refinement_status=null`): "Confirm speakers" → POST `/confirm-speakers`
- Post-refinement (`speakers_resolved=true`, `refinement_status=done`): "Apply & re-refine" → POST `/re-refine` (existing flow)

**Polling hook** (`src/hooks/useJobAutoRefinePolling.ts`):
- Terminal condition updated: poll while `(speakers_resolved && refinement_status !== "done") || phase != null`. Stop when `speakers_resolved && refinement_status === "done" && phase === null` OR `refinement_status === "failed"`.

**API helpers** (`src/utils/api.ts`):
- New `confirmSpeakers(jobId, assignments)` POSTing to `/job/{id}/confirm-speakers`. Same payload shape as `reRefineJob`. Same response shape (extended with `speakers_ignored`).
- Extend `JobStatus` interface with `speakers_resolved?: boolean`.

### Migration

Existing jobs in the DB don't have `speakers_resolved`. On load (`_row_to_job`), default to `True` — they've already passed the gate (or never had one). This means:
- Pre-Plan-7 completed jobs: refinement either ran or didn't; no blocking.
- Pre-Plan-7 awaiting jobs (none expected since the gate didn't exist): wouldn't exist.

In-memory new instances default to `False` via `__init__`.

## Files structure

**Modify**:
- `backend/job_models.py` — add `self.speakers_resolved = False` in `TranscriptionJob.__init__`
- `backend/services/orchestrator.py` — split post-alignment logic: auto-resolve if all matched, else set phase=awaiting_speakers
- `backend/routes/transcription.py` — add `POST /job/{job_id}/confirm-speakers` route; surface `speakers_resolved` in GET `/job/{id}` response
- `src/components/SpeakerReviewPanel.tsx` — three sections; context-aware submit button; "Ignore" action for unknown speakers
- `src/components/PhasePill.tsx` — add `awaiting_speakers` mapping
- `src/utils/api.ts` — add `confirmSpeakers` helper; extend `JobStatus` with `speakers_resolved`
- `src/hooks/useJobAutoRefinePolling.ts` — extend terminal condition + state shape

**Create**:
- `backend/tests/test_confirm_speakers.py` — integration tests: auto-resolve path, awaiting-speakers path, confirm dispatch, ignore handling, idempotency on duplicate confirm

**Reference (read-only)**:
- `backend/routes/transcription.py:_apply_speaker_assignments` — reused as-is from Plan 5A Task 3; the name-based fallback (commit `19f9450`) already handles the voice extraction edge cases
- `backend/routes/refinement.py:_run_refinement_for_job` — reused as-is for the dispatch
- `backend/services/learning.py:update_speaker_embeddings` — still runs post-refinement as B7

## Out of scope

- **Audio playback in the panel** to let the user hear which voice is which before assigning. Useful UX but not blocking the gate's value.
- **Confidence threshold for auto-confirm**. The user picked Hybride which means "all matched → auto, any anonymous → pause" without a per-speaker confidence threshold. If a B5 match is wrong but high-confidence, the user will see it in the Matched section with a Reject button.
- **AFK timeout**. Pause indefinitely.
- **Bulk fix for existing jobs with `embedding_path=null`**. Separate concern; a CLI script `python -m scripts.backfill_embeddings <job_id>` can be written ad-hoc later.
- **Concurrent confirmation**. Multiple users hitting Confirm at the same time isn't a real scenario for a single-user app.

## Acceptance criteria

When Plan 7 ships:

1. A new transcription with 2 voice-matched + 1 anonymous speaker auto-resolves the 2 matched and pauses for the 1 anonymous. Phase pill shows "Awaiting speakers". Refinement does NOT auto-fire.
2. The panel shows 3 sections (Matched / Known profiles / Unknown) with appropriate actions per section. Submit button reads "Confirm speakers".
3. After clicking Confirm, voice embeddings for the assigned speakers land on their profiles (`embedding_path` non-null in `speakers` table). Refinement dispatches and the phase pill cycles refining → learning → None.
4. A new transcription where ALL labels are B5-matched skips the pause entirely — `speakers_resolved=true` is set in the orchestrator, refinement dispatches immediately. Phase pill goes: aligning → refining → learning → None (no awaiting_speakers).
5. After refinement completes, the panel transforms: "Confirm speakers" button becomes "Apply & re-refine" (existing Plan 5 flow). User can still post-edit.
6. Pre-Plan-7 completed jobs in history are not affected — they show no panel (treated as resolved by migration default).
7. Frontend `npx tsc --noEmit`: 0 errors. Backend suite: 374+ passed.
8. New `test_confirm_speakers.py` adds ≥6 integration tests covering: auto-resolve path, awaiting path, confirm dispatch, ignore action, 409 when already resolved, 409 when not completed, name-based embedding extraction works.

## Sub-plan decomposition

Two halves that lockstep-release:

- **Plan 7A — Backend**: speakers_resolved field + orchestrator split + `/confirm-speakers` endpoint + tests + GET `/job/{id}` response surface. ~5 tasks.
- **Plan 7B — Frontend**: PhasePill mapping + 3-section panel + context-aware submit + polling extension + `confirmSpeakers` helper. ~5 tasks.

They ship together. Backend can land first if it's backward-compatible (it is — existing frontend still uses `/re-refine`).
