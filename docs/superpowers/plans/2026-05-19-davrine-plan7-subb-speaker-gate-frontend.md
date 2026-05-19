# Plan 7 Sub-plan B — Frontend Pre-Refinement Speaker Gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the new pre-refinement speaker resolution gate (Plan 7A backend) in the UI. Add an `awaiting_speakers` phase pill with amber/yellow "needs attention" semantics. Extend the polling hook + `JobStatus` so the frontend learns about `speakers_resolved`. Add a `confirmSpeakers` API helper alongside the existing `reRefineJob`. Rewrite `SpeakerReviewPanel` in-place so it operates in two modes: a **pre-refinement** mode (3 sections — Matched / Known profiles / Unknown — with a "Confirm speakers" submit and per-row "Ignore" action) and a **post-refinement** mode (the existing Plan 5 flow — "Apply & re-refine").

**Architecture:** Pure-frontend change. No new components — the existing `SpeakerReviewPanel.tsx` (~390 lines today) is rewritten to become context-aware off `speakers_resolved`. `RejectMatchModal` is reused unchanged. `PhasePill` gains one entry in its label table. `useJobAutoRefinePolling` extends its terminal condition to wait for `speakers_resolved=true` before declaring the job done — without this, a `awaiting_speakers` job would look "terminal" the moment refinement_status becomes `null` and the UI would stop polling for the user's own future Confirm click. `JobStatus` + `fetchJobAutoRefineState` learn the new field, defaulting to `true` for backward compat with pre-Plan-7 jobs that never had a gate (the backend's `_row_to_job` migration in 7A also defaults reloaded `completed` rows to `true`).

**Tech Stack:** React 18 + TypeScript + TailwindCSS, `lucide-react` icons (`UserCheck`/`UserX`/`UserPlus`/`Loader2`/`Sparkles`/`Ban` for the new Ignore action). Existing patterns: `React.memo` for leaf components, polling via `useJobAutoRefinePolling`, registry fetch via `fetchSpeakers()`.

**⚠️ Test framework prerequisite — read before starting Task 1**

This repo has **no Vitest or React Testing Library installed**. `package.json` devDeps include only `@playwright/test`, `@vitejs/plugin-react`, `tsc`, `tailwindcss`, etc. There is no `test` script, no `vitest.config.*`, no existing `*.test.tsx` files, no `node_modules/@testing-library/`. Following the Plan 4C / 5B convention (Path A), this codebase uses **manual smoke + `npx tsc --noEmit`** for frontend verification, not component unit tests.

**This plan follows Path A unconditionally:** every task verifies via `npx tsc --noEmit` for type-correctness and `npm run dev` + browser smoke for behavior. **Do NOT create any `*.test.tsx` files. Do NOT add any `npx vitest run` commands. Do NOT add Vitest/RTL/jsdom devDeps.** Task 5 (manual smoke) is the real verification gate for this plan.

**Dependency lockstep:** This sub-plan **must ship in the same release as Sub-plan A** (`docs/superpowers/plans/2026-05-19-davrine-plan7-suba-speaker-gate-backend.md`). 7B's `speakers_resolved` consumption needs 7A's backend to surface that field on `GET /job/{id}`. 7B's `confirmSpeakers` helper POSTs to `/job/{id}/confirm-speakers` which 7A adds. If 7B ships without 7A:
- The `speakers_resolved` reads default to `undefined` → the panel falls back to post-refinement mode (existing Plan 5 behavior) → no regression for happy-path jobs, but the gate UX never surfaces.
- The Confirm-speakers button 404s on the missing endpoint → blocks gated jobs entirely.

Recommend Plan 7A lands first OR both ship in the same release. The optional `speakers_resolved?: boolean` field on `JobStatus` is the migration handhold that makes 7B forward-compatible: when 7A lands, the field starts arriving and the panel auto-switches to pre-refinement mode for jobs that need it.

---

## File Structure

**Modify:**
- `src/components/PhasePill.tsx` — add one entry to `PHASE_LABELS`: `awaiting_speakers: 'Awaiting speakers'`. Add a per-phase color override so this phase renders amber/yellow (`bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300`) instead of the default blue. The existing dot inside the pill keeps its `animate-pulse` look but switches to amber too. Net ~+10 lines.
- `src/utils/api.ts` — extend `JobStatus` (line ~46) with optional `speakers_resolved?: boolean`. Extend the return type of `fetchJobAutoRefineState` (line ~73) with the same field, reading `j.speakers_resolved` in the body. Add a `ConfirmSpeakersResponse` interface + `confirmSpeakers(jobId, assignments)` helper near the existing `reRefineJob` (line ~1067). Net ~+35 lines.
- `src/hooks/useJobAutoRefinePolling.ts` — extend `AutoRefineState` with `speakers_resolved: boolean`. Update the terminal condition: stop polling when `(speakers_resolved && refinement_status === 'done' && phase === null) || refinement_status === 'failed'`. Without `speakers_resolved` in the gate, an `awaiting_speakers` job whose `refinement_status` is `null` and `phase` is `awaiting_speakers` would technically not match the current terminal check (phase is non-null), but the moment the user confirms and the orchestrator finishes, we'd want polling to continue through `refining` → `learning` → `null` — which it does today only because `phase !== null` keeps the loop alive. The bug we're guarding against: a future change that loosens the phase check would prematurely terminate awaiting jobs. Explicitly gating on `speakers_resolved` makes the intent locally checkable. Net ~+8 lines.
- `src/components/SpeakerReviewPanel.tsx` — REWRITE in place (existing file, ~390 lines today). New props extension: `speakersResolved?: boolean` from the polling hook. Two modes (detected off this prop):
  - **Pre-refinement** (`speakersResolved === false`): 3 sections (Matched / Known profiles / Unknown). New per-row "Ignore" action in the Unknown section (alongside existing "Assign to existing" + "Create new"). Submit button reads **"Confirm speakers"** and calls `confirmSpeakers(jobId, assignments)`. Pending `{kind: 'ignore'}` corrections serialize as the literal string `"ignore"` in the assignments payload (matches 7A's backend contract).
  - **Post-refinement** (`speakersResolved === true` or undefined): existing 2-section Plan 5 flow. Submit button reads **"Apply & re-refine"** and calls `reRefineJob`. **Backward-compat default**: when `speakersResolved` is undefined (older backend that doesn't surface the field), assume `true` so the existing flow is preserved.
  - Net change inside the file: section split + Ignore action + helper for the submit handler dispatch. Roughly +110 lines / -10 lines.

**Reference (read, don't touch):**
- `docs/superpowers/specs/2026-05-19-davrine-pre-refinement-speaker-gate-design.md` — authoritative spec. Sections to re-read before each task: "Architecture / Pipeline lifecycle change", "New endpoint: `POST /job/{job_id}/confirm-speakers`" (assignment shape — UUID / `new:Name` / `"ignore"`), "Frontend changes" (section layouts, submit button labels), "Edge cases addressed" (empty registry, concurrent confirm), "Acceptance criteria" (the 8 user-facing checks).
- `docs/superpowers/plans/2026-05-19-davrine-plan7-suba-speaker-gate-backend.md` — sibling plan. Provides the `speakers_resolved` field surfaced via `GET /job/{id}` + the `POST /job/{id}/confirm-speakers` endpoint that this plan consumes.
- `src/components/RejectMatchModal.tsx` — reused unchanged. The pre-refinement mode does not invoke this modal (matched speakers from B5 are auto-confirmed in the orchestrator; the panel just displays them in the "Matched" section with a Reject button that opens the modal — which is the existing post-refinement code path).
- `src/components/TranscriptView.tsx:457-468` — existing `<SpeakerReviewPanel … />` mount site. The panel's call site changes by ONE prop (`speakersResolved={refineState?.speakers_resolved ?? true}`); no other restructuring at the mount point.

---

## Conventions

**Commit hygiene — CRITICAL.** The working tree has ~10 WIP files at start of this plan, mostly backend (rate_limit.py, contexts.py, jpr.py, speakers.py, deliverable_service.py, test_jpr_api.py, test_speakers_api.py) + 6 unrelated frontend (ContextBrowser, ErrorBoundary, SpeakerProfile, SpeakersView, useContexts, useSpeakers) + launchd plist + start-backend.sh. Plan 7A is being implemented in parallel and touches `backend/job_models.py`, `backend/services/orchestrator.py`, `backend/routes/transcription.py`, `backend/services/labels.py` (new) — none of which this plan touches.

**Verify before Task 1:**
```bash
git diff src/components/PhasePill.tsx src/components/SpeakerReviewPanel.tsx \
         src/utils/api.ts src/hooks/useJobAutoRefinePolling.ts
```
Expected: **empty** (no WIP on any of this plan's targets). If the diff shows any change, inspect it and either preserve it (re-merge after applying this plan) or coordinate with the user before discarding.

The `renameJobSource` WIP block previously called out in Plan 5B is now committed (commit `9478c2b` or later — verify via `git log --oneline -- src/utils/api.ts | head`). The current `src/utils/api.ts` is fully committed; **no `git add -p` dance is needed** for the api.ts edits this plan makes, unless `git diff src/utils/api.ts` shows new WIP at task start.

**Stash dance for every commit in this plan:**

```bash
# Before staging anything:
git status --short

# Stash unrelated WIP (and untracked junk) so your commit is clean:
git stash push -u -m "sub7B-wip-stash" -- \
  backend/ \
  deploy/ \
  scripts/ \
  src/components/ContextBrowser.tsx \
  src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx \
  src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts \
  src/hooks/useSpeakers.ts \
  Tests/ \
  *.m4a

# Then stage ONLY the files this task touches, by explicit path:
git add src/components/PhasePill.tsx

# Commit, then restore WIP:
git commit -m "..."
git stash pop
```

**Never use `git add -A` or `git add .`** — both pull in WIP from parallel backend work and unrelated frontend WIP.

**If `src/utils/api.ts` has new uncommitted hunks at the start of Task 2** (re-check via `git diff src/utils/api.ts`), fall back to `git add -p src/utils/api.ts` to stage only the hunks this plan adds (the `JobStatus.speakers_resolved` line, the `fetchJobAutoRefineState` extension, the `ConfirmSpeakersResponse` interface, and the `confirmSpeakers` function). Press `n` on any unrelated hunk prompt.

**Commit per task, not at the end.** Each task ends with a commit step.

**Commit message style** (follow `git log --oneline -10`):
- `feat(ui): PhasePill — add awaiting_speakers (amber)`
- `feat(api): JobStatus + polling hook — surface speakers_resolved`
- `feat(api): add confirmSpeakers helper for /job/{id}/confirm-speakers`
- `feat(ui): SpeakerReviewPanel — pre-refinement mode (3 sections + Ignore + Confirm speakers)`

**TypeScript strictness:** Project uses TypeScript. `npx tsc --noEmit` must end at **0 errors** (baseline) after each task. Pre-existing errors in unrelated WIP files (e.g. `src/components/SpeakersView.tsx`, `src/components/ContextBrowser.tsx`) should be stashed before tsc runs — the stash dance above takes care of that. If `tsc` still surfaces unrelated errors, document them in the verification step and confirm they're not caused by your edits.

**Testing:** All UI verification is manual via `npm run dev` + browser. The final Task 5 is an explicit smoke checklist (the verification gate). Do NOT add Vitest/RTL. The smoke checklist requires Plan 7A backend to be live; if 7A isn't deployed yet, run only the regression checks (Steps 4-6 of the smoke — they exercise the post-refinement / backward-compat paths and don't depend on 7A).

---

## Task 1: Extend `PhasePill` with `awaiting_speakers`

**Files:**
- Modify: `src/components/PhasePill.tsx` (add `awaiting_speakers` entry + amber color override)

- [ ] **Step 1: Read the current `PhasePill.tsx`**

Run: `sed -n '1,33p' src/components/PhasePill.tsx`

Expected: a memoised React component exporting `PhasePill`, with a `PHASE_LABELS: Record<string, string>` mapping (lines ~7-13) covering `diarizing` / `transcribing` / `aligning` / `refining` / `learning`, and a single Tailwind class block on the `<span>` (line ~24) that hard-codes `bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300`. Returns `null` when `phase` is null/undefined.

- [ ] **Step 2: Add the `awaiting_speakers` entry + per-phase color override**

Edit `src/components/PhasePill.tsx`. Replace the entire file with:

```tsx
import React from 'react';

interface PhasePillProps {
  phase?: string | null;
}

const PHASE_LABELS: Record<string, string> = {
  diarizing: 'Diarizing…',
  transcribing: 'Transcribing…',
  aligning: 'Aligning…',
  awaiting_speakers: 'Awaiting speakers',
  refining: 'Refining…',
  learning: 'Learning…',
};

// Per-phase color overrides. Default = blue (active processing). The
// `awaiting_speakers` phase is a user-action signal — amber/yellow matches
// the "needs attention" semantics used elsewhere in the app.
const PHASE_COLORS: Record<string, { pill: string; dot: string }> = {
  awaiting_speakers: {
    pill: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
    dot: 'bg-amber-500',
  },
};

const DEFAULT_COLORS = {
  pill: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  dot: 'bg-blue-500',
};

function PhasePill({ phase }: PhasePillProps) {
  if (!phase) return null;

  const label = PHASE_LABELS[phase] ?? `${phase.charAt(0).toUpperCase()}${phase.slice(1)}…`;
  const colors = PHASE_COLORS[phase] ?? DEFAULT_COLORS;

  return (
    <span
      role="status"
      aria-live="polite"
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${colors.pill}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${colors.dot}`} aria-hidden="true" />
      {label}
    </span>
  );
}

export default React.memo(PhasePill);
```

The structure preserves the existing default (blue) for all current phases. Only `awaiting_speakers` resolves to a different color row in `PHASE_COLORS`. Future additions can extend the lookup without re-templating.

- [ ] **Step 3: TypeScript check**

Run: `npx tsc --noEmit`

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git status --short  # confirm only PhasePill.tsx is modified

git stash push -u -m "sub7B-task1-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts

git add src/components/PhasePill.tsx
git commit -m "feat(ui): PhasePill — add awaiting_speakers (amber)"
git stash pop
```

---

## Task 2: Extend `JobStatus` + polling hook with `speakers_resolved`

**Files:**
- Modify: `src/utils/api.ts` (extend `JobStatus`, extend `fetchJobAutoRefineState`)
- Modify: `src/hooks/useJobAutoRefinePolling.ts` (extend `AutoRefineState`, update terminal condition)

- [ ] **Step 1: Read the current `JobStatus` + `fetchJobAutoRefineState` definitions**

Run: `sed -n '46,90p' src/utils/api.ts`

Expected: `JobStatus` interface (lines 46-71) with the B2 auto-refine fields, plus `fetchJobAutoRefineState` function (lines 73-90) returning `{refinement_status, learning_status, learning_summary, auto_speaker_matches, phase}`. Neither mentions `speakers_resolved` today.

- [ ] **Step 2: Extend `JobStatus` with `speakers_resolved`**

Edit `src/utils/api.ts`. Locate the `JobStatus` interface (~line 46). Inside the interface body, after the `phase?: string | null;` line (~line 70) and before the closing `}`, insert:

```ts
  // Plan 7: pre-refinement speaker resolution gate. False when the
  // orchestrator paused for user input (phase === 'awaiting_speakers'),
  // true after the user submits via POST /job/{id}/confirm-speakers or
  // when all labels were B5-matched (auto-resolve path). Pre-Plan-7
  // backends omit this field; readers should default to `true` for
  // backward compatibility (the legacy flow has no gate).
  speakers_resolved?: boolean;
```

- [ ] **Step 3: Extend `fetchJobAutoRefineState` return shape + body**

Edit `src/utils/api.ts`. Locate `fetchJobAutoRefineState` (~lines 73-90). Replace its return type + body with:

```ts
export async function fetchJobAutoRefineState(jobId: string): Promise<{
  refinement_status: RefinementStatus;
  learning_status: LearningStatus;
  learning_summary: LearningSummary | null;
  auto_speaker_matches: Record<string, AutoSpeakerMatch> | null;
  phase: string | null;
  speakers_resolved: boolean;
}> {
  const res = await fetchWithTimeout(`${API_URL}/job/${jobId}`);
  if (!res.ok) throw new Error(`fetchJobAutoRefineState failed: ${res.status}`);
  const j = await res.json();
  return {
    refinement_status: j.refinement_status ?? null,
    learning_status: j.learning_status ?? null,
    learning_summary: j.learning_summary ?? null,
    auto_speaker_matches: j.auto_speaker_matches ?? null,
    phase: j.phase ?? null,
    // Default to true for backward compat with pre-Plan-7 backends that
    // don't surface this field — those jobs never had a gate to pass.
    speakers_resolved: j.speakers_resolved ?? true,
  };
}
```

- [ ] **Step 4: Extend `AutoRefineState` + terminal condition in the polling hook**

Edit `src/hooks/useJobAutoRefinePolling.ts`. Replace the entire file with:

```ts
import { useEffect, useState, useRef } from 'react';
import { fetchJobAutoRefineState, RefinementStatus, LearningStatus, LearningSummary, AutoSpeakerMatch } from '../utils/api';

interface AutoRefineState {
  refinement_status: RefinementStatus;
  learning_status: LearningStatus;
  learning_summary: LearningSummary | null;
  auto_speaker_matches: Record<string, AutoSpeakerMatch> | null;
  phase: string | null;
  speakers_resolved: boolean;
}

const TERMINAL_REFINEMENT = new Set<string>(['done', 'failed']);
const POLL_INTERVAL_MS = 5000;  // Per user decision Q6: 5s constant, no backoff.

/**
 * Polls /job/{id} for the post-completion B2 + Plan 7 gate fields.
 * Active only when the transcription job is `completed` (so the parent
 * transcription poller has already stopped).
 *
 * Stop condition: we need ALL THREE of:
 *   - speakers_resolved === true   (user passed the Plan 7 gate, or it auto-resolved)
 *   - refinement_status === 'done' (Sonnet refinement finished)
 *   - phase === null               (B7 learning phase also finished)
 *
 * The backend's lifecycle is:
 *   awaiting_speakers (speakers_resolved=false, phase='awaiting_speakers')
 *     → user confirms →
 *   refining (speakers_resolved=true, refinement_status='processing', phase='refining')
 *     → refinement_status='done', phase='learning'   (post-refinement workers)
 *     → refinement_status='done', phase=null         (everything finished)
 *
 * Stopping at refinement_status='done' alone would park the UI on
 * phase='learning' forever (the user sees "Learning…" stuck because the
 * later phase=null update is never fetched). Stopping when
 * speakers_resolved is still false would freeze the panel before the
 * user has clicked Confirm.
 *
 * `failed` is a hard terminal: phase / speakers_resolved may or may not
 * change, but no more meaningful transitions happen, so stop immediately.
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
        const ref = next.refinement_status;
        if (ref === 'failed') {
          stopRef.current = true;
          return;
        }
        if (next.speakers_resolved && ref === 'done' && next.phase === null) {
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

// Re-exported for tests; not part of the public hook API.
export const __TEST_TERMINAL_REFINEMENT = TERMINAL_REFINEMENT;
```

The behavioral change is one extra condition (`next.speakers_resolved &&`) in the success-terminal branch. The `failed` branch is unchanged — a failed refinement is terminal regardless of `speakers_resolved`.

- [ ] **Step 5: TypeScript check**

Run: `npx tsc --noEmit`

Expected: 0 errors. The new `speakers_resolved: boolean` field on `AutoRefineState` is consumed by Task 4's `SpeakerReviewPanel` rewrite. Until that task lands, the field is set by the hook and ignored by callers — type-wise it's fine.

- [ ] **Step 6: Commit**

```bash
git status --short  # confirm only api.ts + useJobAutoRefinePolling.ts modified

git stash push -u -m "sub7B-task2-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts

# Verify api.ts has no unrelated WIP. If `git diff src/utils/api.ts` shows
# only this plan's hunks, plain `git add` is safe:
git diff src/utils/api.ts | head -40

git add src/utils/api.ts src/hooks/useJobAutoRefinePolling.ts
git commit -m "feat(api): JobStatus + polling hook — surface speakers_resolved"
git stash pop
```

If `git diff src/utils/api.ts` shows hunks unrelated to this plan (someone else's WIP merged in), fall back to `git add -p src/utils/api.ts` instead, pressing `y` only on this plan's hunks (the `speakers_resolved?: boolean` line in `JobStatus`, the return-type extension on `fetchJobAutoRefineState`, the `j.speakers_resolved ?? true` line).

---

## Task 3: Add `confirmSpeakers` API helper

**Files:**
- Modify: `src/utils/api.ts` (add `ConfirmSpeakersResponse` interface + `confirmSpeakers` function near `reRefineJob`)

- [ ] **Step 1: Read the existing `reRefineJob` for the template**

Run: `sed -n '1046,1082p' src/utils/api.ts`

Expected: the `ReRefineResponse` interface + `reRefineJob` function. The new `confirmSpeakers` helper mirrors this structure with two differences: the endpoint path (`/confirm-speakers` instead of `/re-refine`) and the response shape (adds `speakers_ignored: number`).

- [ ] **Step 2: Insert `ConfirmSpeakersResponse` + `confirmSpeakers` immediately after `reRefineJob`**

Edit `src/utils/api.ts`. Locate the end of `reRefineJob` (the closing `}` of the function around line 1081). Insert this block **immediately after** (before the `RenameSourceResponse` interface at line ~1083):

```ts

export interface ConfirmSpeakersResponse {
  job_id: string;
  status: string;
  phase: string | null;
  speakers_created: Array<{ speaker_id: string; name: string }>;
  speakers_assigned: number;
  speakers_ignored: number;
}

/**
 * Plan 7: pre-refinement gate — submit the user's speaker resolution
 * decisions. Same assignment shape as reRefineJob, with one new action
 * value: the literal string "ignore" (leave the label anonymous, no
 * embedding extraction, no profile change; refinement still runs but
 * treats this label as unknown).
 *
 * `assignments` maps a diarization label (e.g. "SPEAKER_00") to one of:
 *   - a speaker UUID (assign to existing profile, extract voice from this
 *     job's segments, save embedding with EMA-update if profile already
 *     has one)
 *   - "new:<Display Name>" (create a new speaker; extract voice, save
 *     embedding)
 *   - "ignore" (no profile change, segments stay anonymous)
 *
 * Backend dispatches a single Sonnet refinement call on success after
 * flipping job.speakers_resolved=true, transitioning job.phase from
 * 'awaiting_speakers' → 'refining' → 'learning' → null.
 *
 * Failures:
 *   - 404 — job not found
 *   - 409 — speakers_resolved already true (idempotent error: refinement is
 *     either already in progress or done)
 *   - 409 — job status !== 'completed' (transcription still in flight)
 *   - 400 — empty assignments map, or malformed "new:" name
 */
export async function confirmSpeakers(
  jobId: string,
  assignments: Record<string, string>,
): Promise<ConfirmSpeakersResponse> {
  const r = await fetchWithTimeout(`${API_URL}/job/${jobId}/confirm-speakers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ speaker_assignments: assignments }),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`confirmSpeakers failed: ${r.status} ${detail.slice(0, 200)}`);
  }
  return r.json();
}
```

- [ ] **Step 3: TypeScript check**

Run: `npx tsc --noEmit`

Expected: 0 errors. `confirmSpeakers` is exported but not yet consumed; Task 4's `SpeakerReviewPanel` rewrite will import it.

- [ ] **Step 4: Commit**

```bash
git status --short  # confirm only api.ts modified for this task

git stash push -u -m "sub7B-task3-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts

# Verify api.ts has no unrelated WIP. If `git diff src/utils/api.ts` shows
# only the confirmSpeakers block, plain `git add` is safe:
git diff src/utils/api.ts | head -60

git add src/utils/api.ts
git commit -m "feat(api): add confirmSpeakers helper for /job/{id}/confirm-speakers"
git stash pop
```

If unrelated WIP appears in `src/utils/api.ts`, fall back to `git add -p` and press `y` only on the `ConfirmSpeakersResponse` + `confirmSpeakers` hunks.

---

## Task 4: Rewrite `SpeakerReviewPanel` with context-aware modes (3 sections + Ignore + Confirm speakers)

**Files:**
- Modify: `src/components/SpeakerReviewPanel.tsx` (rewrite in place)
- Modify: `src/components/TranscriptView.tsx` (pass `speakersResolved` prop into `<SpeakerReviewPanel />` — one prop addition)

- [ ] **Step 1: Re-read the current `SpeakerReviewPanel.tsx` to understand the existing post-refinement flow**

Run: `wc -l src/components/SpeakerReviewPanel.tsx && sed -n '1,50p' src/components/SpeakerReviewPanel.tsx`

Expected: ~390-line file. Imports `AutoSpeakerMatch, Segment, Speaker, fetchSpeakers, reRefineJob` from `../utils/api`, `RejectMatchModal, RejectTarget` from `./RejectMatchModal`, `isAnonymousLabel` from `./TranscriptView`. Owns `pendingCorrections` map, derives `identifiedLabels` + `unknownLabels` from segments + autoMatches, fires `reRefineJob` on Apply. Two sections (Identified + Unknown). Confirm/Reject buttons for identified. Picker + "Create new" for unknown. Submit button reads "Apply & re-refine (N)".

- [ ] **Step 2: Verify the `<SpeakerReviewPanel />` mount site in `TranscriptView.tsx`**

Run: `grep -n "SpeakerReviewPanel\|refineState" src/components/TranscriptView.tsx | head -20`

Expected: an import line (~line 7), a `refineState` declaration from `useJobAutoRefinePolling` (~line 107), and a `<SpeakerReviewPanel ... />` JSX block (~lines 457-468) that passes `jobId`, `segments`, `autoMatches`, `currentPhase={refineState?.phase ?? null}`, and `onReRefineStart`. This task adds one more prop (`speakersResolved`) to that call site after rewriting the panel.

- [ ] **Step 3: Rewrite `SpeakerReviewPanel.tsx`**

Edit `src/components/SpeakerReviewPanel.tsx`. Replace the entire file with:

```tsx
import { useEffect, useMemo, useState } from 'react';
import { UserCheck, UserX, UserPlus, Loader2, Sparkles, Ban } from 'lucide-react';
import {
  AutoSpeakerMatch,
  Segment,
  Speaker,
  fetchSpeakers,
  reRefineJob,
  confirmSpeakers,
} from '../utils/api';
import RejectMatchModal, { RejectTarget } from './RejectMatchModal';
import { isAnonymousLabel } from './TranscriptView';

/**
 * Speaker review surface — context-aware off `speakersResolved`:
 *
 *   - Pre-refinement (speakersResolved === false): the orchestrator
 *     paused at the Plan 7 gate (phase === 'awaiting_speakers').
 *     Renders 3 sections (Matched / Known profiles / Unknown). Submit
 *     button is "Confirm speakers" → POST /job/{id}/confirm-speakers.
 *     Unknown-section rows expose an "Ignore" action so the user can
 *     leave the label anonymous without creating a duplicate profile.
 *
 *   - Post-refinement (speakersResolved === true OR undefined for
 *     pre-Plan-7 backends): the existing Plan 5 flow. 2 sections
 *     (Identified / Unknown). Submit button is "Apply & re-refine" →
 *     POST /job/{id}/re-refine. Reject opens RejectMatchModal.
 *
 * `pendingCorrections` is shared by both modes. The submit handler picks
 * the endpoint based on the current mode. New `{kind: 'ignore'}` action
 * (pre-refinement only) serializes as the literal "ignore" string in
 * the assignments payload.
 */
interface Props {
  jobId: string;
  segments: Segment[];                            // result.segments
  autoMatches: Record<string, AutoSpeakerMatch>;  // from useJobAutoRefinePolling
  currentPhase?: string | null;                   // from useJobAutoRefinePolling
  speakersResolved?: boolean;                     // Plan 7 — from useJobAutoRefinePolling
  onReRefineStart?: () => void;                   // notify parent (clear local edits, etc.)
}

/**
 * Local per-label decision the user has made but not yet submitted.
 *   - confirm: keep the B5 match as-is (no backend re-attribution, but
 *     it becomes part of the assignments map so the refinement run sees
 *     the speaker's profile in context).
 *   - existing: re-attribute to a different registry speaker.
 *   - new: create a new speaker (backend extracts voice embedding).
 *   - unknown: strip the auto-matched name back to the anonymous label.
 *     Post-refinement only — for pre-refinement mode use 'ignore'.
 *   - ignore: leave the label anonymous, no embedding extraction, no
 *     profile change. Pre-refinement mode only.
 */
type CorrectionAction =
  | { kind: 'confirm'; speakerId: string; name: string }
  | { kind: 'existing'; speakerId: string; name: string }
  | { kind: 'new'; name: string }
  | { kind: 'unknown' }
  | { kind: 'ignore' };

export default function SpeakerReviewPanel({
  jobId,
  segments,
  autoMatches,
  currentPhase,
  speakersResolved,
  onReRefineStart,
}: Props) {
  // Mode detection. Default `true` for backward compat with pre-Plan-7
  // backends that don't surface speakers_resolved (legacy flow had no gate
  // → all completed jobs are effectively "post-refinement" for this UI).
  const preRefinementMode = speakersResolved === false;

  const [registry, setRegistry] = useState<Speaker[]>([]);
  const [pendingCorrections, setPendingCorrections] = useState<Map<string, CorrectionAction>>(
    new Map(),
  );
  const [rejectModalLabel, setRejectModalLabel] = useState<string | null>(null);
  const [newSpeakerDrafts, setNewSpeakerDrafts] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Derive all labels present in the transcript segments.
  const allLabels = useMemo(() => {
    const set = new Set<string>();
    for (const s of segments) {
      if (s.speaker) set.add(s.speaker);
    }
    return Array.from(set).sort();
  }, [segments]);

  // Section classification:
  //   Matched      = name resolved (non-anonymous label OR B5-matched)
  //   KnownProfiles = anonymous + unmatched + registry has candidates
  //   Unknown      = anonymous + unmatched + (registry empty OR user wants new/ignore)
  //
  // In post-refinement mode we keep the original 2-section split
  // (matched → "Identified", everything else → "Unknown") for visual
  // continuity with Plan 5. Pre-refinement renders all 3 sections.
  const matchedLabels = allLabels.filter((l) => !isAnonymousLabel(l) || autoMatches[l]?.matched);
  const unresolvedLabels = allLabels.filter((l) => isAnonymousLabel(l) && !autoMatches[l]?.matched);

  // In pre-refinement mode, split unresolved into "Known profiles (no
  // voice)" and "Unknown" based on registry availability. Per the spec,
  // Section B and C are visually similar — both render the registry
  // picker + create input. The split is a labeling nice-to-have. v1
  // renders them as separate sections for clarity; the render path is
  // identical except for the heading.
  const knownProfileLabels = preRefinementMode && registry.length > 0 ? unresolvedLabels : [];
  const unknownLabels = preRefinementMode && registry.length > 0 ? [] : unresolvedLabels;

  // Load registry once (used for the picker + identified-name display).
  useEffect(() => {
    let cancelled = false;
    fetchSpeakers()
      .then((list) => { if (!cancelled) setRegistry(list); })
      .catch(() => { /* silent — picker will show as empty */ });
    return () => { cancelled = true; };
  }, []);

  // Reset per-job state when navigating between jobs. Without this, the
  // panel keeps pendingCorrections from a previous job because TranscriptView
  // re-uses the same SpeakerReviewPanel instance across jobId changes
  // (React reconciliation).
  useEffect(() => {
    setPendingCorrections(new Map());
    setNewSpeakerDrafts({});
    setRejectModalLabel(null);
    setSubmitting(false);
    setSubmitError(null);
  }, [jobId]);

  // The panel is "submitting" while a confirm/re-refine POST is in flight
  // OR the orchestrator is actively in the refining phase. We deliberately
  // do NOT block on `currentPhase === 'learning'`: the B7 learning phase
  // runs *after* refinement completes and shouldn't lock the panel.
  const inFlight = submitting || currentPhase === 'refining';

  const setAction = (label: string, action: CorrectionAction) => {
    setPendingCorrections((prev) => {
      const next = new Map(prev);
      next.set(label, action);
      return next;
    });
  };

  const clearAction = (label: string) => {
    setPendingCorrections((prev) => {
      const next = new Map(prev);
      next.delete(label);
      return next;
    });
  };

  const handleConfirm = (label: string) => {
    const match = autoMatches[label];
    if (match?.speaker_id && match.name) {
      setAction(label, { kind: 'confirm', speakerId: match.speaker_id, name: match.name });
    }
  };

  const handleRejectModalResult = (label: string, target: RejectTarget) => {
    if (target.kind === 'existing') {
      setAction(label, { kind: 'existing', speakerId: target.speakerId, name: target.name });
    } else if (target.kind === 'new') {
      setAction(label, { kind: 'new', name: target.name });
    } else {
      setAction(label, { kind: 'unknown' });
    }
    setRejectModalLabel(null);
  };

  const handleCreateForUnresolved = (label: string) => {
    const name = (newSpeakerDrafts[label] || '').trim();
    if (name) setAction(label, { kind: 'new', name });
  };

  const handleIgnoreForUnresolved = (label: string) => {
    setAction(label, { kind: 'ignore' });
  };

  // Build the assignments map for the submit. The serialization differs
  // by mode: post-refinement maps 'unknown' → 'unknown'; pre-refinement
  // doesn't expose 'unknown' (uses 'ignore' instead — slightly different
  // semantics: 'unknown' strips an existing name, 'ignore' is a no-op
  // because there was no name to strip yet).
  const buildAssignments = (): Record<string, string> => {
    const assignments: Record<string, string> = {};
    for (const [label, action] of pendingCorrections.entries()) {
      switch (action.kind) {
        case 'confirm':
        case 'existing':
          assignments[label] = action.speakerId;
          break;
        case 'new':
          assignments[label] = `new:${action.name}`;
          break;
        case 'unknown':
          // In post-refinement mode (`/re-refine`), 'unknown' is a legacy
          // value that backend accepts. In pre-refinement mode
          // (`/confirm-speakers`, Plan 7A), the endpoint only enumerates
          // UUID / 'new:name' / 'ignore'. Map 'unknown' → 'ignore' when
          // pre-refining so a RejectMatchModal "Mark as Unknown" choice
          // doesn't 400. The semantics are equivalent in this mode (both
          // = "don't attach this label to any profile").
          assignments[label] = preRefinementMode ? 'ignore' : 'unknown';
          break;
        case 'ignore':
          assignments[label] = 'ignore';
          break;
      }
    }
    return assignments;
  };

  const handleApply = async () => {
    if (pendingCorrections.size === 0) return;
    const assignments = buildAssignments();
    setSubmitting(true);
    setSubmitError(null);
    try {
      if (preRefinementMode) {
        await confirmSpeakers(jobId, assignments);
      } else {
        await reRefineJob(jobId, assignments);
      }
      onReRefineStart?.();
      setPendingCorrections(new Map());
      setNewSpeakerDrafts({});
    } catch (e: any) {
      setSubmitError(e?.message || 'Submit failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDiscard = () => {
    setPendingCorrections(new Map());
    setNewSpeakerDrafts({});
    setSubmitError(null);
  };

  // Render nothing when there are no labels at all.
  if (allLabels.length === 0) return null;

  const renderAction = (label: string) => {
    const action = pendingCorrections.get(label);
    if (!action) return null;
    const verb =
      action.kind === 'confirm' ? 'Confirmed'
      : action.kind === 'existing' ? `→ ${action.name}`
      : action.kind === 'new' ? `+ New: ${action.name}`
      : action.kind === 'ignore' ? '⊘ Ignored'
      : '→ Unknown';
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
        {verb}
        <button
          type="button"
          onClick={() => clearAction(label)}
          className="ml-1 opacity-70 hover:opacity-100"
          aria-label={`Clear correction for ${label}`}
        >
          ×
        </button>
      </span>
    );
  };

  // Render an unresolved-label row (used by both Known-profiles and
  // Unknown sections — they share the same action row, only the section
  // heading differs).
  const renderUnresolvedRow = (label: string) => (
    <li key={label} className="flex items-center gap-2 flex-wrap">
      <span className="text-xs text-slate-400 font-mono">{label}</span>
      {renderAction(label) ?? (
        <>
          <select
            value=""
            disabled={inFlight || registry.length === 0}
            onChange={(e) => {
              const sp = registry.find((r) => r.speaker_id === e.target.value);
              if (sp) {
                setAction(label, {
                  kind: 'existing',
                  speakerId: sp.speaker_id,
                  name: sp.name,
                });
              }
            }}
            title={registry.length === 0 ? 'No existing speakers' : 'Assign to existing speaker'}
            className="px-2 py-1 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white disabled:opacity-50"
          >
            <option value="">Assign to existing…</option>
            {registry.map((sp) => (
              <option key={sp.speaker_id} value={sp.speaker_id}>{sp.name}</option>
            ))}
          </select>
          <span className="text-xs text-slate-500 dark:text-slate-400">or</span>
          <input
            type="text"
            value={newSpeakerDrafts[label] || ''}
            onChange={(e) =>
              setNewSpeakerDrafts((prev) => ({ ...prev, [label]: e.target.value }))
            }
            placeholder="New speaker name"
            disabled={inFlight}
            className="flex-1 min-w-[160px] px-3 py-1 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:opacity-50"
            onKeyDown={(e) => e.key === 'Enter' && handleCreateForUnresolved(label)}
          />
          <button
            type="button"
            onClick={() => handleCreateForUnresolved(label)}
            disabled={inFlight || !(newSpeakerDrafts[label] || '').trim()}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
          >
            <UserPlus className="w-3 h-3" aria-hidden="true" />
            Create
          </button>
          {preRefinementMode && (
            <button
              type="button"
              onClick={() => handleIgnoreForUnresolved(label)}
              disabled={inFlight}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-slate-300 text-slate-700 hover:bg-slate-400 dark:bg-slate-600 dark:text-slate-200 dark:hover:bg-slate-500 disabled:opacity-50"
              title="Leave this label anonymous; refinement will treat them as unknown"
            >
              <Ban className="w-3 h-3" aria-hidden="true" />
              Ignore
            </button>
          )}
        </>
      )}
    </li>
  );

  const submitLabel = preRefinementMode ? 'Confirm speakers' : 'Apply & re-refine';
  const submitInFlightLabel = preRefinementMode ? 'Confirming…' : 'Re-refining…';

  return (
    <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-xl">
      <h3 className="text-sm font-medium text-blue-700 dark:text-blue-300 mb-3 flex items-center gap-2">
        <Sparkles className="w-4 h-4" aria-hidden="true" />
        Speaker Review
        {preRefinementMode && (
          <span className="text-xs font-normal text-amber-700 dark:text-amber-300 ml-1">
            — awaiting your input before refinement
          </span>
        )}
      </h3>

      {/* Section A: Matched (auto-confirmed by B5 or already named) */}
      {matchedLabels.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2 uppercase tracking-wide">
            {preRefinementMode ? 'Matched (auto-confirmed)' : 'Identified'}
          </div>
          <ul className="space-y-2">
            {matchedLabels.map((label) => {
              const match = autoMatches[label];
              const conf = match?.confidence != null ? Math.round(match.confidence * 100) : null;
              const displayName = match?.name ?? label;
              return (
                <li key={label} className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-slate-800 dark:text-slate-200">
                    {displayName}
                  </span>
                  {conf != null && (
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      ({conf}%)
                    </span>
                  )}
                  <span className="text-xs text-slate-400 font-mono">{label}</span>
                  {renderAction(label) ?? (
                    <span className="ml-auto flex items-center gap-1">
                      {!preRefinementMode && (
                        <button
                          type="button"
                          onClick={() => handleConfirm(label)}
                          disabled={inFlight || !match?.matched}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
                        >
                          <UserCheck className="w-3 h-3" aria-hidden="true" />
                          Confirm
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setRejectModalLabel(label)}
                        disabled={inFlight || !match?.matched}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-rose-500 text-white hover:bg-rose-600 disabled:opacity-50"
                      >
                        <UserX className="w-3 h-3" aria-hidden="true" />
                        Reject
                      </button>
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Section B: Known profiles, no voice yet (pre-refinement only) */}
      {knownProfileLabels.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2 uppercase tracking-wide">
            Known profiles (no voice yet)
          </div>
          <ul className="space-y-2">
            {knownProfileLabels.map(renderUnresolvedRow)}
          </ul>
        </div>
      )}

      {/* Section C: Unknown */}
      {unknownLabels.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2 uppercase tracking-wide">
            Unknown
          </div>
          <ul className="space-y-2">
            {unknownLabels.map(renderUnresolvedRow)}
          </ul>
        </div>
      )}

      {/* Submit / Discard footer */}
      <div className="flex items-center gap-3 mt-4 flex-wrap">
        <button
          type="button"
          onClick={handleApply}
          disabled={inFlight || pendingCorrections.size === 0}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
        >
          {inFlight ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              {submitInFlightLabel}
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" aria-hidden="true" />
              {submitLabel} ({pendingCorrections.size})
            </>
          )}
        </button>
        <button
          type="button"
          onClick={handleDiscard}
          disabled={inFlight || pendingCorrections.size === 0}
          className="px-4 py-2 text-sm font-medium rounded-lg bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-600 disabled:opacity-50"
        >
          Discard changes
        </button>
        {submitError && (
          <span role="alert" className="text-xs text-rose-600 dark:text-rose-400">
            {submitError}
          </span>
        )}
      </div>

      {rejectModalLabel && autoMatches[rejectModalLabel] && (
        <RejectMatchModal
          label={rejectModalLabel}
          currentMatch={autoMatches[rejectModalLabel]}
          runnerUp={autoMatches[rejectModalLabel].runner_up}
          registry={registry}
          onAccept={(target) => handleRejectModalResult(rejectModalLabel, target)}
          onClose={() => setRejectModalLabel(null)}
        />
      )}
    </div>
  );
}
```

Key differences vs. the existing file:
- New `Ban` icon import for the Ignore action.
- New `confirmSpeakers` import.
- New `speakersResolved?: boolean` prop + `preRefinementMode` derivation.
- New `'ignore'` case in `CorrectionAction` type + `buildAssignments` + `renderAction`.
- Three sections (Matched / Known profiles / Unknown) when in pre-refinement mode; the existing 2-section layout when not.
- Submit button is `Confirm speakers` (calls `confirmSpeakers`) in pre-refinement mode, `Apply & re-refine` (calls `reRefineJob`) otherwise.
- Pre-refinement mode hides the "Confirm" button on matched rows (the orchestrator already auto-confirmed them; the user only needs the Reject option as an override).
- `renderUnresolvedRow` helper factored out so Sections B + C share the action row.

- [ ] **Step 4: Wire `speakersResolved` into the `<SpeakerReviewPanel />` mount in `TranscriptView.tsx`**

Edit `src/components/TranscriptView.tsx`. Locate the `<SpeakerReviewPanel ... />` JSX block (~lines 457-468). Replace the props block with one extra line:

```tsx
        <SpeakerReviewPanel
          jobId={jobId}
          segments={result.segments}
          autoMatches={autoMatches}
          currentPhase={refineState?.phase ?? null}
          speakersResolved={refineState?.speakers_resolved ?? true}
          onReRefineStart={() => {
            // No-op for now — the polling hook re-derives segments + matches
            // once the backend completes. A future hook could clear manual
            // edits here (per spec § "Collision with manual segment edits"
            // — out of scope for this plan).
          }}
        />
```

The default `?? true` is the backward-compat handhold: if `refineState` is null (polling hasn't returned yet) or the field is undefined (older backend), the panel renders in post-refinement mode and behaves exactly like before this plan landed.

- [ ] **Step 5: TypeScript check**

Run: `npx tsc --noEmit`

Expected: 0 errors. The new `Ban` import is a valid `lucide-react` export (used elsewhere in the codebase — quick verify with `grep -l "from 'lucide-react'" src/ | xargs grep -l Ban || true`; if absent, it's still in the lucide-react surface). `confirmSpeakers` was added in Task 3.

- [ ] **Step 6: Commit**

```bash
git status --short  # confirm only SpeakerReviewPanel.tsx + TranscriptView.tsx modified

git stash push -u -m "sub7B-task4-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts

git add src/components/SpeakerReviewPanel.tsx src/components/TranscriptView.tsx
git commit -m "feat(ui): SpeakerReviewPanel — pre-refinement mode (3 sections + Ignore + Confirm speakers)"
git stash pop
```

---

## Task 5: Manual smoke verification (no Playwright, Path A)

**Files:** None modified — verification only.

**Prerequisites:** Plan 7A backend deployed (the `speakers_resolved` field surfaced via `GET /job/{id}`, plus `POST /job/{id}/confirm-speakers` endpoint live). If 7A isn't deployed yet, run only Steps 4-6 (backward-compat regression checks).

- [ ] **Step 1: Start dev environment**

```bash
# Backend (in one shell):
launchctl kickstart -k gui/$UID/com.whisper.backend
# OR if running directly: cd backend && uvicorn main:app --reload --port 8000

# Frontend (in another shell):
cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app
npm run dev  # Vite dev server on :3000 (or :5173)
```

Expected: backend `http://localhost:8000/health` returns 200; frontend opens in browser without console errors.

- [ ] **Step 2: Pre-refinement gate — partially anonymous job**

Setup: ensure the speaker registry has ≥1 named speaker (e.g. "David"). Upload a short audio (~30s) with 2 voices: one matching the registry speaker, one new/unknown.

Trigger transcription with Best engine.

Expected sequence:
1. Phase pill shows: "Diarizing…" → "Transcribing…" → "Aligning…" → **"Awaiting speakers"** (amber/yellow). Refinement does NOT auto-fire.
2. `SpeakerReviewPanel` shows up with header "Speaker Review — awaiting your input before refinement".
3. Section A "Matched (auto-confirmed)" shows the registry-matched speaker with a Reject button only (no Confirm — already auto-confirmed).
4. Section B "Known profiles (no voice yet)" or Section C "Unknown" shows the unmatched label with: registry dropdown, "or" separator, "New speaker name" input + Create button, and an **Ignore** button.
5. Submit button reads **"Confirm speakers (0)"** and is disabled until ≥1 pending correction.

Action: pick "Ignore" on the unknown label. Pending corrections counter increments to 1. Submit button enables.

Click "Confirm speakers (1)".

Expected:
6. POST to `/job/{job_id}/confirm-speakers` (verify via DevTools Network tab).
7. Phase pill transitions: "Awaiting speakers" → "Refining…" (blue) → "Learning…" → no pill (cleared).
8. After refinement completes, the panel transforms: Section A header becomes "Identified", the Ignore buttons disappear (mode flipped to post-refinement after `speakers_resolved=true`), and the Submit button reads "Apply & re-refine".

- [ ] **Step 3: Auto-resolve happy path**

Upload audio where both voices match registry speakers.

Expected sequence:
1. Phase pill: "Diarizing…" → "Transcribing…" → "Aligning…" → "Refining…" → "Learning…" → no pill. **No "Awaiting speakers" pause.**
2. `SpeakerReviewPanel` mounts only after refinement starts (segments are non-empty).
3. Panel renders in post-refinement mode (Identified + Unknown sections, no Ignore buttons, "Apply & re-refine" submit).

- [ ] **Step 4: Backward-compat — pre-Plan-7 backend simulation**

Test that the frontend doesn't break if the backend omits `speakers_resolved`.

Either: (a) check out a pre-7A commit of the backend and re-run, or (b) temporarily patch `fetchJobAutoRefineState` in DevTools to return `speakers_resolved: undefined`.

Expected:
1. Panel defaults to post-refinement mode (the existing Plan 5 flow).
2. Submit button reads "Apply & re-refine" — no "Confirm speakers".
3. No Ignore buttons render.
4. No regression in the existing reject-modal flow.

- [ ] **Step 5: TypeScript baseline check (no regressions)**

Run: `npx tsc --noEmit`

Expected: 0 errors. If pre-existing errors surface in unrelated WIP files (`SpeakersView.tsx`, `ContextBrowser.tsx`, etc.), confirm they're not caused by this plan's edits by stashing the WIP and re-running.

- [ ] **Step 6: Discard-changes regression**

In pre-refinement mode (Step 2 setup), make several pending corrections. Click "Discard changes". All pendings clear; submit button disables; pill remains "Awaiting speakers" (no backend POST fired).

In post-refinement mode (Step 3 setup), make a correction in the Identified section (Confirm or Reject). Click "Discard changes". All pendings clear; no backend POST fired.

- [ ] **Step 7: Acceptance criteria mapping (spec § Acceptance criteria)**

Cross-reference the smoke results to the spec's 8 acceptance criteria (`docs/superpowers/specs/2026-05-19-davrine-pre-refinement-speaker-gate-design.md`, section "Acceptance criteria"):

| # | Criterion | Verified by |
|---|---|---|
| 1 | New transcription with 2 matched + 1 anonymous: matched auto-resolve, paused on anonymous. Pill = "Awaiting speakers". Refinement not auto-fired | Step 2 (1-2) |
| 2 | Panel shows 3 sections with appropriate actions. Submit reads "Confirm speakers" | Step 2 (3-5) |
| 3 | After Confirm: embeddings saved, refinement dispatches, pill cycles refining → learning → None | Step 2 (6-7) — backend side; check `embedding_path` non-null via `select embedding_path from speakers` |
| 4 | All-matched skips the pause; pill goes aligning → refining → learning → None | Step 3 |
| 5 | Post-refinement: panel transforms, "Confirm speakers" becomes "Apply & re-refine" | Step 2 (8) |
| 6 | Pre-Plan-7 completed jobs unaffected (no panel shown — treated as resolved by migration default) | Step 4 |
| 7 | Frontend `npx tsc --noEmit`: 0 errors | Step 5 |
| 8 | Backend test suite — N/A for 7B (covered in 7A) | — |

- [ ] **Step 8: (No commit — verification only)**

This task makes no code changes. If any of Steps 2-7 fail, capture the failure and either (a) fix in a follow-up commit on the same branch, or (b) document a known-issue note in the plan if the failure is acceptable / out-of-scope.

---

## Done

Six commits total across Tasks 1-4:

1. `feat(ui): PhasePill — add awaiting_speakers (amber)` — Task 1
2. `feat(api): JobStatus + polling hook — surface speakers_resolved` — Task 2
3. `feat(api): add confirmSpeakers helper for /job/{id}/confirm-speakers` — Task 3
4. `feat(ui): SpeakerReviewPanel — pre-refinement mode (3 sections + Ignore + Confirm speakers)` — Task 4

(Task 5 is verification-only.)

**Combined diff stats** (approximate):
- `src/components/PhasePill.tsx`: ~+25 lines
- `src/utils/api.ts`: ~+60 lines (`JobStatus.speakers_resolved`, `fetchJobAutoRefineState` extension, `ConfirmSpeakersResponse`, `confirmSpeakers`)
- `src/hooks/useJobAutoRefinePolling.ts`: ~+8 lines
- `src/components/SpeakerReviewPanel.tsx`: ~+110 net lines (rewrite)
- `src/components/TranscriptView.tsx`: ~+1 line (`speakersResolved` prop)

**Final verification:**

```bash
npx tsc --noEmit  # 0 errors
git log --oneline -6  # confirm 4 plan commits on top
git status --short  # confirm WIP from start is restored, no leftover staged files
```

**Lockstep release:** ship this with Plan 7A (`docs/superpowers/plans/2026-05-19-davrine-plan7-suba-speaker-gate-backend.md`). 7B is forward-compatible against pre-7A backends (defaults to post-refinement mode) but the user-visible new gate UX requires 7A to be deployed for the `speakers_resolved=false` path to ever fire.
