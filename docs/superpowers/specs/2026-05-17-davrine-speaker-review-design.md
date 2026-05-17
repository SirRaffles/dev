# Speaker Review — Post-Completion UX + Re-Refinement Design

**Date**: 2026-05-17
**Status**: Approved for planning
**Predecessor**: Plan 4 (Quality Dial + Orchestrator + Combo C diarization polish) — shipped 2026-05-17.

---

## Goal

Replace today's two scattered speaker-correction surfaces (`AutoMatchBadge` inline per segment + post-hoc "Name the speakers" panel) with a **single consolidated "Speaker Review" panel** that appears post-completion. The user can confirm/reject B5 auto-matches and register new speakers in one place, accumulate corrections as draft state, then explicitly trigger a re-refinement run that re-derives the transcript with the corrected speaker profiles in context.

## Motivation

**User pain point (2026-05-17 brainstorming)**: today, speaker corrections are fragmented. B5 voice auto-match runs silently — matched names appear inline with no upfront confirmation; their personality profiles get auto-loaded into refinement context (commit `1bb28fb`) without a user gate. If a B5 match is wrong, the refinement has already run with the wrong profile feeding Sonnet's prompt. Meanwhile, unknown speakers surface only via a separate panel at the bottom of the transcript, with no proactive prompt to register them.

The user wants:
- One **consolidated** UI surface for post-completion speaker review
- Explicit **re-refinement** trigger (single Sonnet call) when corrections are made — so the final transcript and corrections reflect the right speaker profiles
- For rejected matches: a smart **2nd-best suggestion** instead of just "Unknown"
- For unknown speakers: a clear inline prompt to create + auto-save voice embedding

## Decision rationale (from brainstorming)

| Decision | Choice | Why |
|---|---|---|
| Gate timing | **Post-completion (rétroactif)** | Minimal pipeline impact — no pause, no race conditions. Current B5 + auto-load behavior stays for the initial run; correction happens after. |
| UI surface | **Single consolidated panel** | Replaces both AutoMatchBadge inline + "Name the speakers" panel. One cohesive review experience instead of two scattered ones. |
| Re-refinement trigger | **Explicit "Apply & re-refine" button** | User makes all corrections (reject/create/rename) first, then 1 batched Sonnet call. Predictable cost, single coherent pipeline run. |
| Reject semantics | **2nd-best registry match + picker fallback** | "Voulez-vous dire {2nd-best}?" modal. Smart use of B5's existing similarity ranking. Falls back to free-text picker if rejected. |

## Architecture

### Pipeline impact: **none** for the first run

The orchestrator (Plan 4A Task 6), B5 inline auto-match, refinement (Plan 1 + Plan 4B Combo C polish), and B7 learning all run exactly as today. The Speaker Review panel is purely a post-completion UI layer plus a new re-refine endpoint.

### Components

```
┌──────────────────────────────────────────────────────────┐
│ TranscriptView (post-completion)                         │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │ SpeakerReviewPanel                               │    │
│  │                                                  │    │
│  │  ── Section A: Identified ──                     │    │
│  │  • Pascal Weber  conf 87%  [Confirm] [Reject]    │    │
│  │  • David Marchesseau  conf 92%  [Confirm] ✓      │    │
│  │                                                  │    │
│  │  ── Section B: Unknown ──                        │    │
│  │  • SPEAKER_02  [Create: ___________ ]            │    │
│  │                                                  │    │
│  │  Pending corrections: 2                          │    │
│  │  [Apply & re-refine]   [Discard changes]         │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  Transcript (segments with current speaker labels)       │
└──────────────────────────────────────────────────────────┘

[Reject clicked on Pascal Weber]
        ↓
┌─────────────────────────────────────────┐
│ RejectMatchModal                        │
│                                         │
│ B5 thought this was Pascal Weber (87%). │
│ Did you mean instead:                   │
│                                         │
│   ● Arnaud Brolly (62%)  [Use this]     │
│                                         │
│ Or pick another:                        │
│   [Search registry ▾]                   │
│   [+ Create new speaker]                │
│                                         │
│   [Mark as Unknown]                     │
└─────────────────────────────────────────┘
```

### Data flow

1. **Job completes** → `useJobAutoRefinePolling` returns `refinement_status="done"` + `auto_speaker_matches` with extended shape (top + runner-up).
2. **SpeakerReviewPanel mounts** → reads matches + segments → derives anonymous labels.
3. **User makes corrections** → local `pendingCorrections: Map<label, Action>` state. No backend calls during accumulation.
4. **User clicks "Apply & re-refine"** → frontend POST `/job/{id}/re-refine` with `{speaker_assignments: {label: speaker_id | "unknown" | "new:name"}}`.
5. **Backend handler**:
   - For each "new:name" entry → extract a voice embedding from the audio segments matching that label, then call `state.get_speaker_embedding_service().register_speaker(name, embedding)` (`backend/services/speaker_embedding.py:235`). This single call creates the folder, DB row, and saves the `.npy` — no separate save step needed.
   - **Reuse the existing assign helper**: `POST /job/{job_id}/speakers/assign` (`backend/routes/transcription.py:1006`) already handles "map labels → speaker names, creating speakers when needed". The new `/re-refine` endpoint **calls into the same internal helper** that powers `/speakers/assign` (refactor the helper out of the route body into a callable, then both routes call it). The differences: `/re-refine` adds the re-refinement dispatch on top, and accepts `"unknown"` as an explicit value (to strip names back to anonymous).
   - Build final `speaker_ids` list (union of confirmed + newly-created).
   - Update `job.segments[*].speaker` per the assignments map (delegated to the shared helper above).
   - Update `job.settings.speaker_ids` so future logic sees the canonical set.
   - Reset `job.refinement_status = "pending"`, `job.phase = "refining"`.
   - Dispatch `_run_refinement_for_job(job_id, speaker_ids, context_path, audio_path)` via `state.transcription_executor.submit(_run_refinement_for_job, job_id, speaker_ids, context_path, audio_path)` — the same call site pattern used by the orchestrator at `backend/services/orchestrator.py:193`. This is also what Plan 1's manual `/refine/job/{id}` route uses (`backend/routes/refinement.py:314`); the contract is established and consistent across all 3 dispatch points.
6. **Refinement re-runs**:
   - `_run_refinement_for_job` (existing Plan 4B wiring) loads the union of `speaker_ids` + auto-matched IDs (`1bb28fb` augmentation) → merges personality.md into context.
   - Sonnet runs with new context → produces corrections + diarization polish.
   - `_run_post_refinement_learning` runs again (re-trains embeddings with confirmed names).
   - `phase` transitions `refining` → `learning` → `None`.
7. **Frontend polls** `useJobAutoRefinePolling` → sees new `refinement_status` → re-renders transcript with re-derived segments.

### Backend shape: `auto_speaker_matches` extension

**Today** (produced by `services/speaker_embedding.py:auto_identify_speakers`, ~lines 357-440):
```python
auto_speaker_matches = {
    "SPEAKER_00": {
        "matched": True,
        "speaker_id": "uuid-pascal",
        "name": "Pascal Weber",
        "confidence": 0.87,
        "source": "registry",   # existing: "pick" | "registry" | None
        "note": "...",          # existing: optional human note
    },
    ...
}
```

**Extended** (this design — additive, all existing fields preserved):
```python
auto_speaker_matches = {
    "SPEAKER_00": {
        "matched": True,
        "speaker_id": "uuid-pascal",
        "name": "Pascal Weber",
        "confidence": 0.87,
        "source": "registry",
        "note": "...",
        # NEW: 2nd-best candidate (null when no qualifying runner-up exists)
        "runner_up": {
            "speaker_id": "uuid-arnaud",
            "name": "Arnaud Brolly",
            "confidence": 0.62,
        },
    },
    ...
}
```

The runner-up is null when:
- Registry has only 1 speaker (no 2nd candidate exists)
- Runner-up confidence below a min threshold (e.g. 0.4) — not worth suggesting

**Implementation location**: the runner-up is computed inside `SpeakerEmbeddingService.match_speaker` (`backend/services/speaker_embedding.py:172`) — which currently returns `(name, score)` for the top candidate. Extend it to return `(name, score, runner_up_dict_or_None)` by retaining the second-highest cosine similarity from the per-speaker scoring loop. `auto_identify_speakers` (same file, ~line 357) then propagates `runner_up` into each entry of the returned dict. Update both callers (B5 inline path + any direct callers).

`backend/services/learning.py` (`update_speaker_embeddings`, line 68) is **not** modified — it's the B7 post-refinement embedding worker and is unrelated to B5 inline matching.

### New endpoint: `POST /job/{job_id}/re-refine`

Request body:
```json
{
  "speaker_assignments": {
    "SPEAKER_00": "uuid-arnaud",        // re-attribute to existing
    "SPEAKER_01": "unknown",            // strip name, mark anonymous
    "SPEAKER_02": "new:Fabrice Dubois"  // create new speaker (auto-embedding)
  }
}
```

Response:
```json
{
  "job_id": "...",
  "status": "refining",
  "phase": "refining",
  "speakers_created": [{"speaker_id": "uuid-fabrice", "name": "Fabrice Dubois"}],
  "speakers_assigned": 3
}
```

Failures:
- `404` — job not found
- `409` — job not in `completed` state (can't re-refine an in-flight or never-run job)
- `400` — invalid speaker_id (not in registry), malformed name for create, label not in job's segments

### Frontend: `SpeakerReviewPanel.tsx`

Single-source-of-truth component for the post-completion review experience. Owns:
- Derivation of identified-vs-unknown from `auto_speaker_matches` + segments
- Local `pendingCorrections` state
- Modal triggering for reject flow
- "Apply & re-refine" button + loading state during re-run
- Polling integration to detect when re-refinement completes

Replaces both:
- `AutoMatchBadge` inline rendering in `TranscriptView` (and its reject button per segment)
- The "Name the speakers" panel currently at the bottom of `TranscriptView`

### Frontend: `RejectMatchModal.tsx`

Modal shown when user clicks Reject on an identified speaker. Renders:
- Top match (the rejected one) — greyed out, with rejection rationale
- Runner-up speaker from `auto_speaker_matches[label].runner_up` (if not null) with "Use this" CTA
- Picker dropdown (existing `fetchSpeakers` registry) for free-form re-attribution
- "Create new speaker" inline input
- "Mark as Unknown" escape hatch

## Files structure

**Created**:
- `src/components/SpeakerReviewPanel.tsx` (~250 lines)
- `src/components/RejectMatchModal.tsx` (~120 lines)
- `backend/tests/test_re_refine.py` (~80 lines)

**Modified**:
- `backend/routes/transcription.py` — refactor the speaker-assignment body out of `POST /job/{id}/speakers/assign` (line 1006) into a callable helper; add new `POST /job/{id}/re-refine` endpoint that calls the helper + dispatches refinement (~80 lines net, including refactor)
- `backend/services/speaker_embedding.py` — extend `match_speaker` to return `(name, score, runner_up_dict)`; propagate `runner_up` through `auto_identify_speakers` (~25 lines)
- `src/components/TranscriptView.tsx` — remove old `AutoMatchBadge` inline + "Name the speakers" panel, plumb `SpeakerReviewPanel` (~ -80 / +30 lines). Confirmed by grep: `AutoMatchBadge` is imported only at `TranscriptView.tsx:7` and used only at `:987` — deletion is safe.
- `src/utils/api.ts` — `reRefineJob(jobId, assignments)` helper + extended `AutoSpeakerMatch` type with `runner_up` (~25 lines)

**Reference** (read-only):
- `backend/routes/refinement.py:_run_refinement_for_job` — re-used as-is for the re-refinement dispatch
- `backend/services/speaker_embedding.py:235` — `SpeakerEmbeddingService.register_speaker(name, embedding)` re-used for the "new:name" path (creates folder + DB row + saves .npy in one call)
- `backend/services/orchestrator.py` — unchanged (orchestrator owns the first refinement; re-refinement bypasses orchestrator and calls `_run_refinement_for_job` directly, same pattern as Plan 1's manual `/refine/job/{id}` route)

**Deleted**:
- `src/components/AutoMatchBadge.tsx` — replaced by SpeakerReviewPanel's confirmation UI. Safe to delete: grep confirms the only importer is `TranscriptView.tsx:7` (its single render site).

## Out of scope

- **Pipeline-blocking gate before initial refinement** — explicitly rejected during brainstorming. Initial run uses current behavior.
- **Auto-trigger re-refinement on each correction** — explicitly rejected. Single explicit batch button.
- **Debouncing multi-click corrections** — moot under explicit-button trigger.
- **Voice rejection as B7 negative-training signal** — rejected matches don't currently inform future B5 thresholds. Worth a follow-up Plan once we have rejection telemetry.
- **Edit history / undo** — corrections are submitted once via the button; user can re-correct after re-refinement completes (cycle starts over).
- **Concurrent re-refinements** — user submits Apply, gets a loading state until completion. UI disables further corrections during in-flight re-refine.
- **Speaker profile editing from this panel** — the panel triggers create-with-voice but for editing existing profiles (bio, expertise), user goes to the Speakers tab as today.
- **Pending jobs auto-resume** (from the hotfix `ac02292` followup — different concern).
- **Re-refinement when audio file is gone**: the "new:name" path needs `job.audio_path` to extract a voice embedding. If audio has been cleaned up (Plan 1 B5 cleanup deferral or manual rm), the create-speaker path fails. The endpoint returns `409 audio_unavailable` and skips that label; user can still register the speaker manually later via the Speakers tab. Confirm/reject/re-attribute paths don't need the audio and work unconditionally.
- **Collision with manual segment edits**: if the user manually edited segment text or speaker labels between completion and Apply-and-re-refine, the re-refinement run via `_run_refinement_for_job` will overwrite those edits (it re-derives `refined_segments` from `job.segments` via Sonnet). User-facing warning copy: "Re-refining will replace your manual edits — continue?" confirmation modal before submission.

## Migration

This is a UI-level replacement with no breaking API change:
- Existing job records keep working — `auto_speaker_matches` shape extension is additive (runner_up is optional).
- The legacy `AutoMatchBadge` component is deleted, but its data source (`auto_speaker_matches`) is preserved.
- No DB migration needed.
- No JPR watcher impact.
- Frontend bundle includes 2 new components; 1 removed.

## Sub-plan decomposition

This ships as **one Plan 5** in two halves that lockstep-release:

- **Plan 5A — Backend**: runner-up exposure + `/re-refine` endpoint + tests. ~5 tasks. Owns: `services/speaker_embedding.py`, `routes/transcription.py` (refactor `/speakers/assign` helper + add `/re-refine`), `tests/test_re_refine.py`.
- **Plan 5B — Frontend**: `SpeakerReviewPanel` + `RejectMatchModal` + `api.ts` extension + `TranscriptView` cleanup. ~6 tasks. Owns: `src/components/SpeakerReviewPanel.tsx`, `src/components/RejectMatchModal.tsx`, `src/components/TranscriptView.tsx`, `src/utils/api.ts`, deletion of `src/components/AutoMatchBadge.tsx`.

They ship together; 5A's `runner_up` field is consumed only by 5B, so split-ship would leave the field unused.

## Acceptance criteria

When Plan 5 ships:

1. A completed transcription with 2+ identified speakers shows a single `SpeakerReviewPanel` above the transcript (no inline AutoMatchBadges).
2. Clicking Reject on a B5 match opens `RejectMatchModal` showing the runner-up speaker (when available) with one-click re-attribution.
3. For an anonymous SPEAKER_XX label, the panel shows an inline "Create speaker" input that saves both the speaker profile AND a voice embedding extracted from that label's segments.
4. After confirming/rejecting/creating, the "Apply & re-refine" button enables; clicking it sends one POST to `/re-refine` and the UI shows "Re-refining…" with the phase pill at `refining` then `learning` then None.
5. Re-refinement completes within the same wall-clock window as the initial refinement on the same transcript (no extra overhead beyond the second Sonnet call); transcript re-renders with the corrected speaker labels + updated corrections.
6. Existing transcripts (pre-Plan-5) continue to work — `auto_speaker_matches` without `runner_up` falls back to the picker-only flow.
7. Pyright + ts strict — 0 new errors in frontend.
8. Backend test suite green (~370 tests including new re-refine integration test).
