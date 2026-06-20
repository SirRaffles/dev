# Davrine Continuous Improvement — Plan 3 (UX Surfaces B6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the Plan 1 + Plan 2 backend capabilities (auto-refine state, B5 inline auto-match, B7 learning summary, learning log) through six concrete React/TypeScript touchpoints, plus a small backend follow-up so insights see refined speaker names.

**Architecture:** Audit-first (Task 1 produces a touchpoints document that gates the implementation tasks). Then six focused UI tasks: (B6a) refinement-status badges that poll while running; (B6b) inline auto-match badges in `TranscriptView` reading from `auto_speaker_matches` on the job; (B6c) a dedicated `_global.md` editor component mounted under the Contexts tab with two sections (Active / Pending review) and a "promote → Active" action per pending entry; (B6d) a post-job "What was learned" toast; (B6e) an Activity timeline that paginates `GET /learning/log`; (B6f) progressive disclosure of advanced options in `SettingsPanel`. One backend fix (Task 0): the insight worker reads stale `job.segments` — overlay refined segments first so insights actually fire.

**Tech Stack:** React 18, TypeScript (allowJs, strict=false per `tsconfig.json`), Tailwind v3, Vite 6, lucide-react icons, Playwright for e2e. No new runtime deps — match the codebase's "zero new package" hygiene (see `package.json`).

---

## File Structure

**Backend (Task 0 only):**
- Modify: `backend/routes/refinement.py` — orchestrator overlays refined speaker names onto `job.segments` BEFORE calling learning workers, so `extract_insights_auto` finds named speakers
- Modify: `backend/tests/test_learning_orchestrator.py` — add a regression test pinning the segment overlay

**Frontend create:**
- `docs/superpowers/audits/2026-05-15-ux-touchpoints.md` — Task 1 audit deliverable (gates Tasks 2-7)
- `src/hooks/useJobAutoRefinePolling.ts` — small focused poller for the 4 B2 fields on `/job/{id}` (used by B6a, B6d)
- `src/components/RefinementBadge.tsx` — B6a indicator (used in `TranscriptView` and `JobHistory`)
- `src/components/AutoMatchBadge.tsx` — B6b badge + accept/reject menu for an auto-matched speaker label
- `src/components/GlobalGlossaryEditor.tsx` — B6c editor for `_global.md`
- `src/components/LearningToast.tsx` — B6d post-job toast
- `src/components/ActivityTimeline.tsx` — B6e timeline; uses `useLearningLog` below
- `src/hooks/useLearningLog.ts` — `GET /learning/log` paginated client
- `e2e/learning-ux.spec.ts` — Playwright e2e covering B6a + B6d at minimum

**Frontend modify:**
- `src/utils/api.ts` — add fetchers + TypeScript types for: `refinement_status`, `auto_speaker_matches`, `learning_summary`, `learning_status`, `LearningEvent`, `GlobalGlossaryDoc`. Also add `/contexts/_global` GET + PUT + a learning-log GET wrapper.
- `backend/routes/contexts.py` — add `GET /contexts/_global` and `PUT /contexts/_global` endpoints (single-file convenience over the existing folder API — keeps the editor a one-call read/write)
- `src/components/TranscriptView.tsx` — replace the existing `fetchJobAutoMatchSuggestions` fetch with the inline `job.auto_speaker_matches` reader; render `<AutoMatchBadge>` per auto-matched label; mount `<RefinementBadge>`
- `src/components/JobHistory.tsx` — show `<RefinementBadge>` per completed job in the history list
- `src/components/SettingsPanel.tsx` — wrap advanced options in a collapsible `<details>` accordion ("Advanced", default closed)
- `src/components/ContextBrowser.tsx` — mount the new `<GlobalGlossaryEditor>` at the top of the Contexts tab
- `src/App.tsx` — add new `activity` tab to `Navigation`; lazy-load `<ActivityTimeline>`; mount post-job toast at root so it survives view changes
- `src/components/Navigation.tsx` — declare the new `activity` tab + matching icon

**Reference (read-only):**
- `backend/routes/transcription.py:638-647` — GET `/job/{id}` already emits the 4 B2 fields (Plan 1 Task 6)
- `backend/routes/learning.py` — `GET /learning/log?event_type=&since=&limit=&offset=` (Plan 2 Task 7)
- `backend/services/learning.py:LEARNING_LOG_PATH` — path of the JSONL file
- `backend/services/glossary.py` — `append_auto_learned_term` + the file shape (`## Active`, `## Auto-learned (pending review)`)
- `src/components/TranscriptView.tsx:67-160` — existing auto-match flow (post-hoc fetch); Plan 3 replaces it with inline
- `src/hooks/usePollingJob.js` — existing polling pattern to mirror in `useJobAutoRefinePolling`
- `src/components/ContextBrowser.tsx:1-50` — existing folder/file editor (`GlobalGlossaryEditor` follows the same idioms)
- `playwright.config.ts` — base URL `http://localhost:3000`; tests run against `npm run dev`
- `e2e/call-intelligence.spec.ts` — pattern to mirror for `learning-ux.spec.ts`

---

## Conventions for all tasks

- **Branch:** `dev`. Push only at the end of Task 9 after manual validation passes.
- **Commit hygiene:** WIP files exist (~22). Always `git add <specific files>` — never `git add -A`.
- **Frontend dev loop:** the dev server runs at `http://localhost:3000` via `npm run dev`. Tests run via `npx playwright test`. There is no Jest/RTL — UI verification is Playwright + manual.
- **Type strictness:** `tsconfig.json` has `strict: false, allowJs: true`. Don't introduce strict-mode-only patterns; mirror the existing files' style (loose typing where natural, explicit interfaces at API boundaries).
- **Tailwind:** v3 with the existing palette. Use `dark:` variants for every new piece of UI — the app supports dark mode (`useTheme` hook).
- **Icons:** lucide-react only. Don't add new icon packages.
- **No new runtime deps.** If you think you need one, stop and report `BLOCKED`.

---

## Task 1: UX audit document (gates Tasks 3-8)

**Files:**
- Create: `docs/superpowers/audits/2026-05-15-ux-touchpoints.md`

**This task gates Tasks 3-8.** The user reviews the audit and signs off before any UI implementation starts. The audit is also what each subsequent implementer reads to understand the surface they're touching — without it, parallel implementations could double-cover or miss a surface.

Task 2 (the backend insight overlay fix) can run in parallel with the audit since it's purely backend.

- [ ] **Step 1: Survey the impacted React components**

For each B6 sub-feature, read the current file end-to-end and record:
- The component's current responsibilities and props.
- Where the new UI element would be inserted (line range).
- Whether existing state/hooks can be reused or new ones are needed.
- Edge cases the current code already handles (so the new UI doesn't break them).

Read in full:
- `src/components/TranscriptView.tsx` (1030 lines)
- `src/components/SettingsPanel.tsx` (736 lines)
- `src/components/ContextBrowser.tsx` (432 lines)
- `src/components/JobHistory.tsx`
- `src/components/SpeakersView.tsx` (304 lines)
- `src/App.tsx` (especially the lazy-load + tab routing)
- `src/hooks/useTranscription.ts`, `src/hooks/usePollingJob.js`, `src/hooks/useContexts.ts`

- [ ] **Step 2: Write the audit document**

Create `docs/superpowers/audits/2026-05-15-ux-touchpoints.md` with this structure:

```markdown
# UX Touchpoints Audit — Plan 3 (B6 implementations)

Date: 2026-05-15
Spec: docs/superpowers/specs/2026-05-15-davrine-continuous-improvement-design.md
Plan: docs/superpowers/plans/2026-05-15-davrine-continuous-improvement-plan3-ux-surfaces.md

## Table — one row per B6 task

| Task | Surface | Current state | Desired state | Files to modify | Insertion-point line ranges |
|------|---------|---------------|---------------|-----------------|----------------------------|
| B6a | TranscriptView header + JobHistory rows | No refinement indicator | Spinner "Refining…" + "Refined" badge | `TranscriptView.tsx`, `JobHistory.tsx` | _fill in_ |
| B6b | TranscriptView speaker labels | Existing post-hoc `/speakers/auto-match` fetch | Inline reads from `job.auto_speaker_matches`; per-label badge + Accept/Reject menu | `TranscriptView.tsx`, new `AutoMatchBadge.tsx` | _fill in_ |
| B6c | Contexts tab | Generic folder/file editor only | Dedicated `_global.md` editor with Active / Pending sections + promote action | `ContextBrowser.tsx`, new `GlobalGlossaryEditor.tsx`, `backend/routes/contexts.py` | _fill in_ |
| B6d | App root | No post-job toast | "Learned: N terms, M insights, K embeddings" toast after refinement done | `App.tsx`, new `LearningToast.tsx` | _fill in_ |
| B6e | New "Activity" nav tab | None | Paginated timeline of /learning/log | `App.tsx`, `Navigation.tsx`, new `ActivityTimeline.tsx`, new `useLearningLog.ts` | _fill in_ |
| B6f | SettingsPanel | Flat list of all knobs (~30 fields) | "Advanced" `<details>` accordion (default closed) wraps temperature ladder, model_size, two_pass | `SettingsPanel.tsx` | _fill in_ |

## Per-task notes

### B6a (refinement-status indicator)

- Existing polling: `usePollingJob` polls `GET /job/{id}` already; it surfaces `status` / `progress` / `progress_message` but does NOT expose `refinement_status` / `learning_status` to consumers. New hook `useJobAutoRefinePolling` should poll only when a job is `completed` AND `refinement_status` is in `(null, "pending", "processing")` — stop polling once `done` or `failed`.
- Visual: small chip next to the language badge in `TranscriptView` header (~line _X_). Replace status text in `JobHistory` rows.
- Reuse: existing `Loader2` spinner icon. Same `bg-blue-100` / `dark:bg-blue-900` chip pattern as the existing "Generated" badge.

### B6b (auto-match badges)
... [continue this pattern for each B6 sub-task]

### B6f (Settings progressive disclosure) — REQUIRED enumeration

The audit MUST enumerate the specific advanced knobs that will move into the `<details>` accordion, with their current line ranges in `SettingsPanel.tsx`. Without this, Task 8 cannot proceed without re-auditing the 736-line file. Expected baseline list (audit may revise after reading): `temperature` ladder, `beam_size`, `patience`, `best_of`, `vad_filter`, `model_size` variants beyond the headline 3, `two_pass`, `word_timestamps`, `enable_noise_reduction`. Keep above-the-fold: `engine`, `language`, `enable_diarization`, `num_speakers`, `speaker_ids`, `context_path`, `output_mode`.

## Open questions for user

Seed at least 3 concrete questions during Step 2 so the gate review is substantive. Examples to spark thought (replace with real questions after reading the code):
- B6e default filter — show all event types, or just `glossary_add + embedding_update` (most actionable)?
- B6d toast dismiss policy — auto-dismiss 12s + click-to-close, or sticky until "Review"?
- B6c — should the "promote → Active" action MOVE the line (remove from pending) or COPY (keep an audit trail)?

## Gating

This audit MUST be reviewed and accepted by the user before Tasks 3-8 begin.
Subsequent implementers reference this document so they know exactly which
files/line-ranges to touch.

(Open questions section is documented in "Per-task notes" above. Remove this placeholder when filling out the audit.)
```

Fill every cell. The "Insertion-point line ranges" column is the load-bearing one — it's what subsequent implementers reference to avoid hunting.

- [ ] **Step 3: Commit and stop for user review**

```bash
cd ~/Development/apps/whisper-transcription-app
git add docs/superpowers/audits/2026-05-15-ux-touchpoints.md
git commit -m "B6: UX touchpoints audit for Plan 3"
```

**Report back with status `DONE` and an explicit note that the next task should not start until the user has reviewed the audit.** The orchestrator will surface to the human.

---

## Task 2: Backend fix — insight worker sees refined speaker names

**Files:**
- Modify: `backend/routes/refinement.py` — orchestrator overlays refined speaker names back onto `job.segments` BEFORE the learning workers run
- Modify: `backend/tests/test_learning_orchestrator.py` — add regression test

**Why:** Plan 2 manual validation showed `insights_added: 0` because `_extract_speaker_insights_sync` (`backend/routes/transcription.py:957`) reads `job.segments` (raw, still SPEAKER_XX) instead of refinement's `refined_segments`. The fix: have the orchestrator overlay refined speaker names back into `job.segments` (in-memory) before calling the insight worker. Refinement's `apply_corrections` already builds the speaker mapping; we just need to make sure the orchestrator-side view of `job.segments` reflects it.

This can run in parallel with Task 1.

**`state.jobs` vs `state.job_store` convention:** `state.jobs` is bound as an alias of `state.job_store` at `backend/state.py:132`. The existing `_run_post_refinement_learning` (`backend/routes/refinement.py:78,126`) uses `state.jobs.get(...)` / `state.jobs.update(...)` — match that convention in the new overlay code. (Other code in the file uses `state.job_store.get` at `_run_refinement_for_job` line 165 — both work, but keep this task consistent with its surrounding orchestrator body.)

- [ ] **Step 1: Write the failing regression test**

Append to `backend/tests/test_learning_orchestrator.py`:

```python
def test_orchestrator_overlays_refined_speaker_names_onto_job_segments(tmp_path, monkeypatch):
    """When refinement renames SPEAKER_XX → real names, those names must land
    on job.segments BEFORE the insight worker reads them. Otherwise
    _extract_speaker_insights_sync sees only anonymous labels and bails."""
    from unittest.mock import MagicMock
    from job_models import TranscriptionJob
    from routes import refinement as rmodule

    # Job starts with SPEAKER_00/01 segments (raw diarization)
    job = TranscriptionJob("job-overlay")
    job.segments = [
        {"start": 0, "end": 60, "text": "...", "speaker": "SPEAKER_00"},
        {"start": 60, "end": 120, "text": "...", "speaker": "SPEAKER_01"},
    ]

    import state
    monkeypatch.setattr(state, "jobs", MagicMock(get=MagicMock(return_value=job),
                                                  update=MagicMock()))

    # Refined segments have real names — the orchestrator must propagate.
    refined = [
        {"start": 0, "end": 60, "text": "...", "speaker": "Pascal"},
        {"start": 60, "end": 120, "text": "...", "speaker": "David"},
    ]

    # Capture what the insight worker would see (it reads from job.segments).
    seen_segments = {}
    def fake_insights(**kwargs):
        # Reflect the same read the real worker would do.
        j = state.jobs.get(kwargs["job_id"])
        seen_segments["speakers"] = [s.get("speaker") for s in (j.segments or [])]
        return 2
    monkeypatch.setattr("services.learning.update_speaker_embeddings",
                        lambda **kwargs: 0)
    monkeypatch.setattr("services.learning.extract_insights_auto", fake_insights)
    monkeypatch.setattr("services.learning.learn_glossary_terms",
                        lambda **kwargs: 0)

    rmodule._run_post_refinement_learning(
        job_id="job-overlay", audio_path=None,
        segments=refined, analysis={},
    )

    assert seen_segments["speakers"] == ["Pascal", "David"], (
        f"insight worker saw {seen_segments['speakers']} — overlay didn't fire"
    )
    assert job.learning_summary["insights_added"] == 2
```

- [ ] **Step 2: Run; confirm failure**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning_orchestrator.py::test_orchestrator_overlays_refined_speaker_names_onto_job_segments -v 2>&1 | tail -10
```
Expected: assertion fail — seen speakers are still `["SPEAKER_00", "SPEAKER_01"]`.

- [ ] **Step 3: Update `_run_post_refinement_learning` in `routes/refinement.py`**

Add the overlay step at the top of the orchestrator (after the `assignments` map build, before the worker calls):

```python
def _run_post_refinement_learning(job_id: str, audio_path: Optional[str],
                                  segments: list, analysis: dict) -> None:
    """..."""
    from services import learning

    assignments: dict = {}
    for seg in (segments or []):
        spk = (seg.get("speaker") or "").strip()
        if not spk or spk.startswith("SPEAKER_"):
            continue
        assignments[spk] = spk

    # NEW: overlay refined speaker names back into job.segments so
    # extract_insights_auto (which reads job.segments via the existing
    # _extract_speaker_insights_sync helper) sees real names instead of
    # SPEAKER_XX. Build a {raw_segment_key: refined_speaker} map from
    # segment timings, then mutate job.segments in place.
    job_for_overlay = state.jobs.get(job_id)
    if job_for_overlay is not None and job_for_overlay.segments and segments:
        # Index refined segments by (start, end) for O(1) lookup. Refinement
        # preserves segment timings; only text/speaker change.
        refined_by_span = {
            (round(float(s.get("start", 0)), 2),
             round(float(s.get("end", 0)), 2)): s.get("speaker")
            for s in segments if s.get("speaker")
        }
        overlaid = False
        for raw in job_for_overlay.segments:
            key = (round(float(raw.get("start", 0)), 2),
                   round(float(raw.get("end", 0)), 2))
            new_spk = refined_by_span.get(key)
            if new_spk and new_spk != raw.get("speaker"):
                raw["speaker"] = new_spk
                overlaid = True
        if overlaid:
            try:
                state.jobs.update(job_for_overlay)
            except Exception:
                logger.debug("jobs.update after overlay failed for %s",
                             job_id, exc_info=True)

    # ... rest of orchestrator unchanged (speaker_turns, 3 workers, etc.)
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_learning_orchestrator.py -v 2>&1 | tail -15
```
Expected: 5 passed (4 prior + 1 new).

- [ ] **Step 5: Run full suite**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -q 2>&1 | tail -3
```
Expected: +1 over the current baseline (`pytest --collect-only` shows 311 tests collected today; the exact post-fix number will be 1 higher than whichever pre-fix baseline you see).

- [ ] **Step 6: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/routes/refinement.py backend/tests/test_learning_orchestrator.py
git commit -m "B7 followup: orchestrator overlays refined speaker names so insights fire"
```

---

## Task 3: B6a — refinement-status indicator

**Files:**
- Create: `src/hooks/useJobAutoRefinePolling.ts`
- Create: `src/components/RefinementBadge.tsx`
- Modify: `src/utils/api.ts` — add types + a `fetchJobAutoRefineState(jobId)` helper
- Modify: `src/components/TranscriptView.tsx` — mount `<RefinementBadge>` at the top
- Modify: `e2e/learning-ux.spec.ts` (create) — Playwright e2e covering "completed → refining → refined" badge transition

**Stretch / deferred:** per-row badge in `src/components/JobHistory.tsx`. Verified that `state.jobs.list_recent()` (`backend/job_models.py:285-317`) does NOT expose `refinement_status`/`learning_status` in the `/jobs` list response — adding it would require a SQL-schema migration (these are in-memory-only by spec). Deferring to a future ticket: either persist the fields or add a per-row fetch on hover. Don't ship in Plan 3.

**Gating:** Task 1 audit must be accepted by the user.

- [ ] **Step 1: Add API types and fetcher**

In `src/utils/api.ts`, extend `JobStatus`:

```typescript
export type RefinementStatus = "pending" | "processing" | "done" | "failed" | null;
export type LearningStatus = "ok" | "partial" | "failed" | null;

export interface LearningSummary {
  embeddings_updated: number;
  insights_added: number;
  terms_learned: number;
}

export interface AutoSpeakerMatch {
  name: string | null;
  confidence: number;
  speaker_id: string | null;
  matched: boolean;
  source?: "pick" | "registry" | null;
  note?: string;
}

export interface JobStatus {
  // ... existing fields ...
  refinement_status?: RefinementStatus;
  auto_speaker_matches?: Record<string, AutoSpeakerMatch> | null;
  learning_summary?: LearningSummary | null;
  learning_status?: LearningStatus;
}

export async function fetchJobAutoRefineState(jobId: string): Promise<{
  refinement_status: RefinementStatus;
  learning_status: LearningStatus;
  learning_summary: LearningSummary | null;
  auto_speaker_matches: Record<string, AutoSpeakerMatch> | null;
}> {
  const res = await fetchWithTimeout(`${API_URL}/job/${jobId}`);
  if (!res.ok) throw new Error(`fetchJobAutoRefineState failed: ${res.status}`);
  const j = await res.json();
  return {
    refinement_status: j.refinement_status ?? null,
    learning_status: j.learning_status ?? null,
    learning_summary: j.learning_summary ?? null,
    auto_speaker_matches: j.auto_speaker_matches ?? null,
  };
}
```

- [ ] **Step 2: Create `src/hooks/useJobAutoRefinePolling.ts`**

```typescript
import { useEffect, useState, useRef } from 'react';
import { fetchJobAutoRefineState, RefinementStatus, LearningStatus, LearningSummary, AutoSpeakerMatch } from '../utils/api';

interface AutoRefineState {
  refinement_status: RefinementStatus;
  learning_status: LearningStatus;
  learning_summary: LearningSummary | null;
  auto_speaker_matches: Record<string, AutoSpeakerMatch> | null;
}

const TERMINAL_STATES = new Set<string>(['done', 'failed']);
const POLL_INTERVAL_MS = 5000;

/**
 * Polls /job/{id} for the 4 B2 fields. Active only while refinement_status
 * is null/pending/processing. Stops once it hits a terminal state (done|failed).
 *
 * Returns null until the first successful fetch, then the current state.
 */
export function useJobAutoRefinePolling(jobId: string | null, jobCompleted: boolean): AutoRefineState | null {
  const [state, setState] = useState<AutoRefineState | null>(null);
  const stopRef = useRef(false);

  useEffect(() => {
    stopRef.current = false;
    if (!jobId || !jobCompleted) {
      setState(null);
      return;
    }

    let cancelled = false;
    const tick = async () => {
      try {
        const next = await fetchJobAutoRefineState(jobId);
        if (cancelled) return;
        setState(next);
        if (next.refinement_status && TERMINAL_STATES.has(next.refinement_status)) {
          stopRef.current = true;
          return;
        }
      } catch {
        // Network blip — keep polling.
      }
      if (!cancelled && !stopRef.current) {
        setTimeout(tick, POLL_INTERVAL_MS);
      }
    };
    tick();

    return () => { cancelled = true; stopRef.current = true; };
  }, [jobId, jobCompleted]);

  return state;
}
```

- [ ] **Step 3: Create `src/components/RefinementBadge.tsx`**

```typescript
import { Loader2, Sparkles, AlertCircle } from 'lucide-react';
import { RefinementStatus } from '../utils/api';

interface Props {
  status: RefinementStatus;
  compact?: boolean;
}

export default function RefinementBadge({ status, compact = false }: Props) {
  if (!status || status === 'pending') {
    if (status === 'pending') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
          <Loader2 className="w-3 h-3 animate-spin" /> Queued for refinement
        </span>
      );
    }
    return null;
  }
  if (status === 'processing') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">
        <Loader2 className="w-3 h-3 animate-spin" /> Refining…
      </span>
    );
  }
  if (status === 'done') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300" title="Transcript corrections, speaker names, and learning have been applied">
        <Sparkles className="w-3 h-3" /> {compact ? 'Refined' : 'Refined transcript ready'}
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded bg-rose-100 dark:bg-rose-900/40 text-rose-700 dark:text-rose-300" title="Refinement failed — verbatim transcript is still available">
        <AlertCircle className="w-3 h-3" /> Refinement failed
      </span>
    );
  }
  return null;
}
```

- [ ] **Step 4: Mount in `TranscriptView.tsx`**

In `TranscriptView.tsx`, at the top of the component body (right after the existing state hooks), add:

```typescript
import RefinementBadge from './RefinementBadge';
import { useJobAutoRefinePolling } from '../hooks/useJobAutoRefinePolling';
// ...
const refineState = useJobAutoRefinePolling(jobId, true /* job is shown only when completed */);
```

In the header rendering (find the existing language badge — see audit document for the line number), render `{refineState?.refinement_status && <RefinementBadge status={refineState.refinement_status} />}` next to it.

- [ ] **Step 5: (Deferred — see Stretch note in file list.)** Skip the JobHistory edit; the fields aren't in the `/jobs` list response.

- [ ] **Step 6: Playwright e2e**

Create `e2e/learning-ux.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test('refinement badge appears post-completion when auto_refine is set', async ({ page }) => {
  await page.goto('/');
  // Submit a small file via the API, then navigate to its job view.
  // Easier: mock the backend response via route intercept so the test is fast.
  await page.route('**/job/**', async (route) => {
    if (route.request().method() !== 'GET') return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: 'test-job',
        status: 'completed',
        progress: 100,
        progress_message: 'Complete!',
        refinement_status: 'processing',
        auto_speaker_matches: null,
        learning_summary: null,
        learning_status: null,
        segments: [{ start: 0, end: 1, text: 'hi', speaker: 'SPEAKER_00' }],
        language: 'en',
      }),
    });
  });
  // Navigate / trigger the TranscriptView render for the mocked job.
  // (Exact navigation depends on the App's job-loading flow — confirm from audit.)
  await page.evaluate(() => {
    // Helper: app exposes a debug navigator?  If not, skip this test for now
    // and rely on manual validation in Task 9.
  });
  await expect(page.getByText(/Refining…|Refined/)).toBeVisible({ timeout: 10_000 });
});
```

If the App doesn't expose a stable way to jump to a job from a Playwright test, **mark this e2e as `test.skip(true, "needs App-level job-loading hook")`** and rely on manual validation in Task 9. Don't over-engineer — Plan 3 ships the UI; e2e coverage can come later.

- [ ] **Step 7: Verify locally**

```bash
cd ~/Development/apps/whisper-transcription-app && npx playwright test e2e/learning-ux.spec.ts 2>&1 | tail -10
```

Also run `npm run dev` and submit a real transcription with auto-refine enabled — verify the badge appears in the TranscriptView header during refinement, transitions to "Refined", and is dismissable.

- [ ] **Step 8: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add src/hooks/useJobAutoRefinePolling.ts src/components/RefinementBadge.tsx src/utils/api.ts src/components/TranscriptView.tsx e2e/learning-ux.spec.ts
git commit -m "B6a: refinement-status badge in TranscriptView"
```

---

## Task 4: B6b — inline auto-match badges with Accept/Reject

**Files:**
- Create: `src/components/AutoMatchBadge.tsx`
- Modify: `src/components/TranscriptView.tsx` — replace existing `fetchJobAutoMatchSuggestions` block with inline reader of `job.auto_speaker_matches` (delivered by the new polling hook from Task 3)
- Modify: `src/utils/api.ts` — re-export `AutoSpeakerMatch` type (already added Task 3)

**Gating:** Task 1 audit + Task 3 hook + Task 0/2 backend overlay.

**Replacement scope:** TranscriptView already has a post-hoc `/speakers/auto-match` fetch loop (lines ~118-160). Plan 1 B5 makes that redundant — the data is now on the job itself. Delete the old post-hoc fetch; render badges from the new field. The Accept action still calls the existing `/job/{id}/speakers/assign` route.

**Behavior change to call out in commit message and audit:** the old flow auto-populated the `draftAssignments` rename inputs when a high-confidence match was found (TranscriptView lines ~134-143) — passive pre-fill. The new B6b flow surfaces an explicit `<AutoMatchBadge>` with Accept / Reject buttons — active confirmation. This is a deliberate UX shift toward "user signs off on every voice match" rather than "we silently rename and hope you notice". Don't preserve the passive pre-fill; the badge IS the new UX.

- [ ] **Step 1: Create `src/components/AutoMatchBadge.tsx`**

```typescript
import { useState } from 'react';
import { Check, X, UserCheck } from 'lucide-react';
import { AutoSpeakerMatch } from '../utils/api';

interface Props {
  label: string;            // pyannote label, e.g. "SPEAKER_00"
  match: AutoSpeakerMatch;
  onAccept: (label: string, name: string, speakerId: string) => Promise<void> | void;
  onReject: (label: string) => void;
}

export default function AutoMatchBadge({ label, match, onAccept, onReject }: Props) {
  const [busy, setBusy] = useState(false);
  if (!match.matched || !match.name) return null;
  const conf = Math.round((match.confidence ?? 0) * 100);

  const handleAccept = async () => {
    if (!match.speaker_id) return;
    setBusy(true);
    try { await onAccept(label, match.name!, match.speaker_id); } finally { setBusy(false); }
  };

  return (
    <span className="inline-flex items-center gap-1 ml-2 px-1.5 py-0.5 text-xs rounded bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/50"
          title={`Voice-matched from registry (${conf}% confident, ${match.source ?? 'registry'})`}>
      <UserCheck className="w-3 h-3" />
      auto · {conf}%
      <button onClick={handleAccept} disabled={busy} className="ml-1 hover:text-emerald-700 dark:hover:text-emerald-400" title="Accept this auto-match">
        <Check className="w-3 h-3" />
      </button>
      <button onClick={() => onReject(label)} className="hover:text-rose-700 dark:hover:text-rose-400" title="Reject (revert to SPEAKER_XX)">
        <X className="w-3 h-3" />
      </button>
    </span>
  );
}
```

- [ ] **Step 2: Replace the post-hoc fetch in `TranscriptView.tsx`**

Find the block that calls `fetchJobAutoMatchSuggestions(jobId)` (~lines 118-160). Replace its data source with the polling hook from Task 3:

```typescript
const refineState = useJobAutoRefinePolling(jobId, true);
const autoMatches = refineState?.auto_speaker_matches || {};
```

Render `<AutoMatchBadge>` next to any speaker label that appears in `autoMatches[label]?.matched === true`. Accept handler calls `assignJobSpeakers(jobId, [{ label, speaker_name: name }])` (existing API). Reject handler updates local state to suppress the badge for that label (no backend call — segments stay as-is).

**Delete the old `fetchJobAutoMatchSuggestions` import + state + effect** — they're now dead code. Verify by `grep fetchJobAutoMatchSuggestions src/` returning only the api.ts definition.

- [ ] **Step 3: Manual smoke**

`npm run dev`, submit a transcription with a registered speaker who has an embedding on file, confirm the badge shows up with confidence, Accept persists, Reject hides.

- [ ] **Step 4: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add src/components/AutoMatchBadge.tsx src/components/TranscriptView.tsx src/utils/api.ts
git commit -m "B6b: inline auto-match badges in TranscriptView (replaces post-hoc fetch)"
```

---

## Task 5: B6c — `_global.md` editor

**Files:**
- Modify: `backend/routes/contexts.py` — add `GET /contexts/_global` + `PUT /contexts/_global` endpoints (single-file convenience over the existing folder API)
- Modify: `backend/tests/test_contexts_api.py` — add tests for the new endpoints
- Create: `src/components/GlobalGlossaryEditor.tsx`
- Modify: `src/utils/api.ts` — `fetchGlobalGlossary`, `saveGlobalGlossary`, `promoteAutoLearnedTerm`
- Modify: `src/components/ContextBrowser.tsx` — mount `<GlobalGlossaryEditor>` at the top of the tab content

**Gating:** Task 1 audit.

- [ ] **Step 1: Add backend endpoints**

Append to `backend/routes/contexts.py`:

```python
@router.get("/contexts/_global")
async def read_global_glossary():
    """Read the global glossary file. Returns empty body if missing."""
    target = CONTEXTS_DIR / "_global.md"
    if not target.is_file():
        return {"content": "", "exists": False}
    return {
        "content": target.read_text(encoding="utf-8"),
        "exists": True,
        "modified_at": target.stat().st_mtime,
    }


@router.put("/contexts/_global")
async def write_global_glossary(req: FileWriteRequest):
    """Atomically write the global glossary file."""
    target = CONTEXTS_DIR / "_global.md"
    CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".md.tmp")
    try:
        tmp.write_text(req.content, encoding="utf-8")
        tmp.replace(target)
    finally:
        if tmp.exists():
            try: tmp.unlink()
            except OSError: pass
    return {"status": "saved", "path": "_global.md"}
```

- [ ] **Step 2: Tests for the endpoints**

Append to `backend/tests/test_contexts_api.py`:

```python
@pytest.mark.asyncio
async def test_read_global_glossary_missing(client, icloud_base):
    resp = await client.get("/contexts/_global")
    body = resp.json()
    assert body["content"] == ""
    assert body["exists"] is False


@pytest.mark.asyncio
async def test_write_then_read_global_glossary(client, icloud_base):
    body_md = "# Global Glossary\n\n## Active\n\nManukai\n"
    resp = await client.put("/contexts/_global", json={"content": body_md})
    assert resp.status_code == 200
    resp = await client.get("/contexts/_global")
    body = resp.json()
    assert body["exists"] is True
    assert "Manukai" in body["content"]
```

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_contexts_api.py -v 2>&1 | tail -10
```

- [ ] **Step 3: Frontend types + fetchers**

In `src/utils/api.ts`:

```typescript
export interface GlobalGlossaryDoc {
  content: string;
  exists: boolean;
  modified_at?: number;
}

export async function fetchGlobalGlossary(): Promise<GlobalGlossaryDoc> {
  const r = await fetchWithTimeout(`${API_URL}/contexts/_global`);
  if (!r.ok) throw new Error(`fetchGlobalGlossary failed: ${r.status}`);
  return r.json();
}

export async function saveGlobalGlossary(content: string): Promise<void> {
  const r = await fetchWithTimeout(`${API_URL}/contexts/_global`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  if (!r.ok) throw new Error(`saveGlobalGlossary failed: ${r.status}`);
}
```

- [ ] **Step 4: Editor component**

Create `src/components/GlobalGlossaryEditor.tsx`:

```typescript
import { useEffect, useState } from 'react';
import { Loader2, Save, BookOpen, AlertCircle, CheckCircle } from 'lucide-react';
import { fetchGlobalGlossary, saveGlobalGlossary } from '../utils/api';

export default function GlobalGlossaryEditor() {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchGlobalGlossary()
      .then((d) => setContent(d.content || ''))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await saveGlobalGlossary(content);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 p-4">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading global glossary…
      </div>
    );
  }

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden mb-4">
      <div className="bg-slate-50 dark:bg-slate-800/40 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
          <BookOpen className="w-4 h-4" />
          <span className="font-medium">Global glossary</span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Auto-injected into every transcription's initial prompt + refinement context
          </span>
        </div>
        <div className="flex items-center gap-2">
          {saved && (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700 dark:text-emerald-400">
              <CheckCircle className="w-3 h-3" /> Saved
            </span>
          )}
          {error && (
            <span className="inline-flex items-center gap-1 text-xs text-rose-700 dark:text-rose-400">
              <AlertCircle className="w-3 h-3" /> {error}
            </span>
          )}
          <button onClick={handleSave} disabled={saving}
                  className="inline-flex items-center gap-1 px-3 py-1 text-xs rounded bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white">
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
            Save
          </button>
        </div>
      </div>
      <textarea
        className="w-full p-4 font-mono text-sm bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 border-0 focus:ring-0 resize-y"
        rows={16}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="# Global Glossary&#10;&#10;## Active&#10;&#10;Pascal Weber, Manukai, DMG Mori&#10;&#10;## Auto-learned (pending review)&#10;&#10;(High-confidence corrections land here. Review each item, then move to Active or delete.)"
      />
    </div>
  );
}
```

- [ ] **Step 5: Mount in `ContextBrowser.tsx`**

Add the import and render `<GlobalGlossaryEditor />` at the top of the component's return JSX (before the existing folder/file tree).

- [ ] **Step 6: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/routes/contexts.py backend/tests/test_contexts_api.py src/components/GlobalGlossaryEditor.tsx src/components/ContextBrowser.tsx src/utils/api.ts
git commit -m "B6c: _global.md editor in Contexts tab + GET/PUT endpoints"
```

---

## Task 6: B6d — post-job "What was learned" toast

**Files:**
- Create: `src/components/LearningToast.tsx`
- Modify: `src/App.tsx` — mount toast at root, wire to polling hook

**Gating:** Tasks 1 + 3 (uses `useJobAutoRefinePolling`).

The toast appears once `refinement_status === 'done'` and `learning_summary` is populated. It auto-dismisses after 12s and shows: `"Learned: N glossary terms, M speaker insights, K voice embeddings updated"`. On click, navigates to the Activity timeline (Task 7).

- [ ] **Step 1: Create `src/components/LearningToast.tsx`**

```typescript
import { useEffect, useState } from 'react';
import { Sparkles, X } from 'lucide-react';
import { LearningSummary, LearningStatus } from '../utils/api';

interface Props {
  summary: LearningSummary | null;
  status: LearningStatus;
  onClickReview: () => void;
}

export default function LearningToast({ summary, status, onClickReview }: Props) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!summary || status === null) {
      setVisible(false);
      return;
    }
    setVisible(true);
    const t = setTimeout(() => setVisible(false), 12_000);
    return () => clearTimeout(t);
  }, [summary, status]);

  if (!visible || !summary) return null;

  const total = (summary.terms_learned || 0) + (summary.insights_added || 0) + (summary.embeddings_updated || 0);
  if (total === 0 && status !== 'failed') return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 max-w-sm bg-white dark:bg-slate-900 border border-emerald-200 dark:border-emerald-900/50 rounded-lg shadow-lg p-4 animate-in slide-in-from-bottom-2">
      <div className="flex items-start gap-2">
        <Sparkles className="w-4 h-4 text-emerald-600 dark:text-emerald-400 mt-0.5" />
        <div className="flex-1 text-sm text-slate-800 dark:text-slate-200">
          <div className="font-medium mb-1">Refined &amp; learned</div>
          <ul className="text-xs space-y-0.5 text-slate-600 dark:text-slate-400">
            {summary.terms_learned > 0 && <li>+{summary.terms_learned} glossary {summary.terms_learned === 1 ? 'term' : 'terms'} (review)</li>}
            {summary.insights_added > 0 && <li>+{summary.insights_added} speaker {summary.insights_added === 1 ? 'insight' : 'insights'}</li>}
            {summary.embeddings_updated > 0 && <li>~{summary.embeddings_updated} voice {summary.embeddings_updated === 1 ? 'embedding' : 'embeddings'} updated</li>}
            {total === 0 && <li>Nothing new this run.</li>}
          </ul>
          <button onClick={onClickReview}
                  className="mt-2 text-xs text-indigo-600 dark:text-indigo-400 hover:underline">
            Review activity →
          </button>
        </div>
        <button onClick={() => setVisible(false)} className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">
          <X className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Mount in `App.tsx`**

After the JSX containing the main view tabs, before the closing wrapper, add:

```typescript
import { useJobAutoRefinePolling } from './hooks/useJobAutoRefinePolling';
import LearningToast from './components/LearningToast';

// inside App component, near other state.
// IMPORTANT: App.tsx uses `active.jobId` and `active.status` (see lines 537,648),
// NOT `job?.jobId`. The audit must confirm the exact binding; the snippet below
// assumes the documented `active` shape.
const currentJobId = active?.jobId || null;
const isCompleted = active?.status === 'completed';
const refineState = useJobAutoRefinePolling(currentJobId, isCompleted);

// in JSX, at root level:
<LearningToast
  summary={refineState?.refinement_status === 'done' ? refineState.learning_summary : null}
  status={refineState?.learning_status ?? null}
  onClickReview={() => setActiveTab('activity')}
/>
```

The audit (Task 1) is responsible for pinning down the exact `active` binding shape so the implementer doesn't have to re-derive it.

- [ ] **Step 3: Manual smoke**

Submit a transcription with auto-refine on, wait for the toast post-completion. Dismiss + "Review activity" both work.

- [ ] **Step 4: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add src/components/LearningToast.tsx src/App.tsx
git commit -m "B6d: post-job 'What was learned' toast"
```

---

## Task 7: B6e — Activity timeline tab

**Files:**
- Create: `src/hooks/useLearningLog.ts`
- Create: `src/components/ActivityTimeline.tsx`
- Modify: `src/components/Navigation.tsx` — add `activity` tab
- Modify: `src/App.tsx` — register lazy-loaded `<ActivityTimeline>` for the new tab
- Modify: `src/utils/api.ts` — `fetchLearningLog`

**Gating:** Task 1 audit.

- [ ] **Step 1: Add fetcher + types in `src/utils/api.ts`**

```typescript
export type LearningEventType =
  | 'embedding_update' | 'embedding_skipped' | 'embedding_failed'
  | 'glossary_add'
  | 'insight_added' | 'insight_failed';

export interface LearningEvent {
  ts: string;
  type: LearningEventType | string;
  job_id?: string;
  speaker_id?: string | null;
  speaker_name?: string;
  term?: string;
  source_phrase?: string;
  reason?: string;
  category?: string;
  duration_sec?: number;
}

export interface LearningLogResponse {
  events: LearningEvent[];
  total: number;
  offset: number;
  limit: number;
}

export async function fetchLearningLog(params: {
  since?: string;
  type?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<LearningLogResponse> {
  const qs = new URLSearchParams();
  if (params.since) qs.set('since', params.since);
  if (params.type) qs.set('type', params.type);
  if (params.limit !== undefined) qs.set('limit', String(params.limit));
  if (params.offset !== undefined) qs.set('offset', String(params.offset));
  const r = await fetchWithTimeout(`${API_URL}/learning/log?${qs.toString()}`);
  if (!r.ok) throw new Error(`fetchLearningLog failed: ${r.status}`);
  return r.json();
}
```

Also update the NAS nginx config so the `/learning/*` route reaches the wake-proxy instead of falling through to the SPA catch-all. **The file is `deploy/nas/nginx.conf` — NOT the repo-root `nginx.conf` (which only serves static SPA assets).** The wake-proxy regex appears twice (HTTP server block ~line 42, HTTPS server block ~line 133). Add `learning` to the alternation in both:

```nginx
# Before:
^/(jobs?|batch|models|api|speakers?|calls?|contexts?|jpr)(/|$)
# After:
^/(jobs?|batch|models|api|speakers?|calls?|contexts?|jpr|learning)(/|$)
```

**Skip the `vite.config.js` proxy update** — `src/utils/api.ts:3` uses an absolute `API_URL` in dev (`http://localhost:8000`), so the Vite dev-server proxy is not on the request path for `/learning/log`.

- [ ] **Step 2: Create `src/hooks/useLearningLog.ts`**

```typescript
import { useEffect, useState } from 'react';
import { fetchLearningLog, LearningEvent } from '../utils/api';

export function useLearningLog(filter: { type?: string } = {}) {
  const [events, setEvents] = useState<LearningEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 50;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchLearningLog({ ...filter, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then((r) => {
        if (cancelled) return;
        setEvents(r.events);
        setTotal(r.total);
      })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [filter.type, page]);

  return {
    events, total, page, setPage, loading, error,
    hasNext: (page + 1) * PAGE_SIZE < total,
    hasPrev: page > 0,
  };
}
```

- [ ] **Step 3: Create `src/components/ActivityTimeline.tsx`**

Render a chronological list, group by day, color-code by event type, show one filter dropdown (All / Glossary / Insights / Embeddings), pagination buttons (Prev / Next).

Keep it focused — ~150 lines. Tailwind list with icons (Sparkles for glossary_add, UserCheck for embedding_update, BookOpen for insight_added).

- [ ] **Step 4: Wire into App + Navigation**

Add `'activity'` to the `NavTab` union in `Navigation.tsx`; register the tab with an Activity icon.

In `App.tsx`:
```typescript
const ActivityTimeline = lazy(() => import('./components/ActivityTimeline'));
// ...
{activeTab === 'activity' && <Suspense fallback={null}><ActivityTimeline /></Suspense>}
```

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add src/hooks/useLearningLog.ts src/components/ActivityTimeline.tsx src/components/Navigation.tsx src/App.tsx src/utils/api.ts deploy/nas/nginx.conf
git commit -m "B6e: Activity tab — paginated /learning/log timeline"
```

---

## Task 8: B6f — SettingsPanel progressive disclosure

**Files:**
- Modify: `src/components/SettingsPanel.tsx`

**Gating:** Task 1 audit (which identified the specific knobs to bury).

Wrap the advanced knobs (per the audit — typically temperature ladder, model_size variants beyond the main 3, two_pass, beam_size, word_timestamps internal, etc.) in a `<details>` element with `open={false}` default. The basic knobs (engine, language, enable_diarization, num_speakers, speaker_ids, context_path) stay above the fold.

- [ ] **Step 1: Identify the knobs from the audit**

The audit's B6f row lists exact knobs and line ranges. Don't guess — match the audit.

- [ ] **Step 2: Wrap in `<details>`**

```jsx
<details className="mt-4 group">
  <summary className="cursor-pointer text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 select-none">
    <span className="inline-flex items-center gap-1">
      <ChevronRight className="w-3 h-3 transition-transform group-open:rotate-90" />
      Advanced settings
    </span>
  </summary>
  <div className="mt-2 pl-4 border-l-2 border-slate-200 dark:border-slate-700 space-y-3">
    {/* moved advanced knobs */}
  </div>
</details>
```

(Use `<details>` over a state-driven accordion — keyboard accessible, no JS, matches the codebase's "minimal new components" hygiene.)

- [ ] **Step 3: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add src/components/SettingsPanel.tsx
git commit -m "B6f: collapse advanced knobs under Settings → Advanced details"
```

---

## Task 9: Manual validation gate

**Files:**
- None (manual)

End-to-end check that the user can see and act on every B6 surface.

- [ ] **Step 1: Restart backend + start frontend**

```bash
launchctl kickstart -k "gui/$(id -u)/com.whisper.backend"
cd ~/Development/apps/whisper-transcription-app && npm run dev &
```

- [ ] **Step 2: Run a fresh Pascal Weber transcription with auto-refine**

Same flow as Plan 1 Task 12 + Plan 2 Task 9 (curl-submit `Tests/15-29-21.m4a` with both speaker_ids).

- [ ] **Step 3: Verify each B6 surface in the browser**

- **B6a:** TranscriptView header shows "Refining…" while it runs, transitions to "Refined transcript ready".
- **B6b:** If embeddings exist for either speaker, the auto-match badge renders with confidence; Accept persists, Reject hides.
- **B6c:** Contexts tab shows the `_global.md` editor at the top, both Active and Pending sections visible, Save round-trips.
- **B6d:** Toast appears bottom-right post-refinement with non-zero counts (insights_added > 0 after Task 2's fix).
- **B6e:** Activity tab shows the new events from this run + filter dropdown works + pagination works on >50 events.
- **B6f:** Settings panel has the advanced accordion collapsed by default.

- [ ] **Step 4: Final regression**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -q 2>&1 | tail -3
```
Expected: no regressions.

- [ ] **Step 5: Push branch**

```bash
cd ~/Development/apps/whisper-transcription-app && git push origin dev
```

---

## Done criteria

Plan 3 is complete when:
- Task 1 audit landed and was approved.
- All 9 task commits land on `dev`.
- Full backend pytest suite still passes (+1 over the pre-Plan-3 baseline after Task 2).
- Manual smoke covers all 6 B6 surfaces end-to-end.
- Branch pushed to `origin/dev`.

## Out of scope

- Per-row refinement badge in JobHistory (only if the `/jobs` list endpoint exposes the fields — defer otherwise per Task 3 Step 5).
- Activity timeline streaming (polling on tab open is sufficient).
- Mobile responsiveness audit (existing app already targets desktop; new components inherit the conventions).
- New strict-mode TypeScript — codebase is `strict: false`.
- React Testing Library setup — no existing harness; Playwright + manual covers Plan 3.
- ActivityTimeline persistent filters across sessions (in-memory state only).
