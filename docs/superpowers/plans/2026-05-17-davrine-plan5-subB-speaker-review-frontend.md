# Plan 5 Sub-plan B — Frontend Speaker Review Panel + Reject Modal

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two scattered speaker-correction surfaces (`AutoMatchBadge` rendered inline per first-occurrence segment + the "Name the speakers" panel above the transcript) with a single consolidated `SpeakerReviewPanel` mounted post-completion in `TranscriptView`. The panel accumulates corrections locally, then dispatches one `POST /job/{id}/re-refine` call that triggers a single Sonnet re-refinement run with the corrected speaker profiles in context. A `RejectMatchModal` shows the runner-up speaker (when 5A's backend provides one) for one-click re-attribution.

**Architecture:** Pure-frontend change. Extends `AutoSpeakerMatch` in `src/utils/api.ts` with an optional `runner_up?: {speaker_id, name, confidence}` field (additive — all existing fields preserved). Adds a `reRefineJob(jobId, assignments)` API helper. Adds two new components: `SpeakerReviewPanel.tsx` (~250 lines, owns the post-completion review state machine: derives identified-vs-unknown from `auto_speaker_matches` + segments, owns local `pendingCorrections` map, fires `reRefineJob` on Apply) and `RejectMatchModal.tsx` (~120 lines, surfaces 5A's runner-up + picker fallback). Removes the inline `AutoMatchBadge` render site at `TranscriptView.tsx:987` and the "Name the speakers" block at `TranscriptView.tsx:607-682`, then plumbs `<SpeakerReviewPanel />` in the same general slot. Deletes `src/components/AutoMatchBadge.tsx` (its only importer is `TranscriptView.tsx:7`, confirmed by grep).

**Tech Stack:** React 18 + TypeScript + TailwindCSS, `lucide-react` icons (`UserCheck`/`UserX`/`UserPlus`/`Loader2`/`Sparkles` already in use across the codebase). Existing patterns: `React.memo` for leaf components, polling via `useJobAutoRefinePolling` (already returns `auto_speaker_matches`), registry fetch via `fetchSpeakers()` (already used in `TranscriptView`).

**⚠️ Test framework prerequisite — read before starting Task 1**

This repo has **no Vitest or React Testing Library installed**. `package.json` devDeps include only `@playwright/test`, `@vitejs/plugin-react`, `tsc`, `tailwindcss`, etc. There is no `test` script, no `vitest.config.*`, no existing `*.test.tsx` files, no `node_modules/@testing-library/`. Following the Plan 4C convention (Path A), this codebase uses **manual smoke + `npx tsc --noEmit`** for frontend verification, not component unit tests.

**This plan follows Path A unconditionally:** every task verifies via `npx tsc --noEmit` for type-correctness and `npm run dev` + browser smoke for behavior. **Do NOT create any `*.test.tsx` files. Do NOT add any `npx vitest run` commands. Do NOT add Vitest/RTL/jsdom devDeps.** Task 7 (manual smoke) is the real verification gate for this plan.

**Dependency lockstep:** This sub-plan **must ship in the same release as Sub-plan A** (`docs/superpowers/plans/2026-05-17-davrine-plan5-subA-backend-rerefine.md` once written). 5B's `RejectMatchModal` consumes the `runner_up` field that 5A's backend adds to `auto_speaker_matches`, and the "Apply & re-refine" button calls `POST /job/{id}/re-refine` which 5A adds. If 5B ships without 5A: the runner-up section silently degrades to "no suggestion available, pick from registry" (acceptable graceful fallback because the field is optional), but the Apply button 404s on the endpoint (NOT acceptable — blocks the whole correction flow). Recommend Plan 5A lands first OR both ship in the same release.

---

## File Structure

**Create:**
- `src/components/RejectMatchModal.tsx` (~120 lines) — overlay shown when the user clicks Reject on an identified speaker. Renders the rejected match greyed out, surfaces the runner-up speaker (from `auto_speaker_matches[label].runner_up`) with a "Use this" CTA when present, exposes a picker dropdown sourced from the speaker registry, an inline "Create new speaker" input, and a "Mark as Unknown" escape hatch. Pure presentational + local input state — does not call the backend; resolves a target via the `onAccept(target)` callback.
- `src/components/SpeakerReviewPanel.tsx` (~250 lines) — single source of truth for the post-completion review experience. Two sections (Identified + Unknown), local `pendingCorrections: Map<string, CorrectionAction>` state, opens the `RejectMatchModal` for the reject flow, exposes an inline "Create speaker" input for anonymous labels, and an "Apply & re-refine" button that calls `reRefineJob(jobId, assignments)` then invokes the `onReRefineStart` callback. Shows a loading state ("Re-refining…") while the in-flight re-refinement runs.

**Modify:**
- `src/utils/api.ts` — extend the `AutoSpeakerMatch` interface (around line 28) with an optional `runner_up?: {speaker_id: string; name: string; confidence: number} | null` field. Add a new `reRefineJob(jobId, assignments)` helper near the end of the file (before the `renameJobSource` WIP at line 1048) that POSTs to `/job/{id}/re-refine` with body `{speaker_assignments: Record<string, string>}` and returns `{job_id, status, phase, speakers_created, speakers_assigned}`. Net ~25 lines added. **WIP caveat:** `renameJobSource` at lines 1042-1059 is uncommitted WIP — skip those hunks via `git add -p` (see Conventions).
- `src/components/TranscriptView.tsx` — delete the import of `AutoMatchBadge` (line 7), delete the inline `<AutoMatchBadge ... />` render block (lines ~987-993) and the surrounding `showBadge` IIFE, delete the "Name the speakers" block (lines ~607-682), delete the bulk "Accept all" mini-banner inside the transcript scroll area (lines ~913-937), and import + render `<SpeakerReviewPanel jobId={...} segments={result.segments} autoMatches={autoMatches} onReRefineStart={...} />` placed between the language/refinement-status row (ends around line 605) and the "Rename Speakers" block (starts around line 684, after the deleted "Name the speakers"). Also delete the now-unused `handleAcceptAutoMatch`, `handleRejectAutoMatch`, `rejectedMatches` state, `firstOccurrenceIndex` useMemo, `draftAssignments`/`assignSaving`/`assignError`/`insightStatus` state, and the `handleAssignSpeakers` function (all are subsumed by `SpeakerReviewPanel`). Net ~-180 / +20 lines.

**Delete:**
- `src/components/AutoMatchBadge.tsx` — replaced by `SpeakerReviewPanel`. Confirmed safe by grep: the only importer is `TranscriptView.tsx:7`, the only render site is `TranscriptView.tsx:987`. Both are removed in Task 5.

**Reference (read, don't touch):**
- `docs/superpowers/specs/2026-05-17-davrine-speaker-review-design.md` — authoritative spec. Sections to re-read before each task: "Components" (the ASCII layout), "Data flow" (the 7-step lifecycle), "Frontend: SpeakerReviewPanel.tsx" (responsibilities), "Frontend: RejectMatchModal.tsx" (modal shape), "Out of scope" (especially the "audio file is gone" 409 path and the "collision with manual segment edits" confirmation modal copy).
- `src/hooks/useJobAutoRefinePolling.ts` — already returns `auto_speaker_matches`; no change needed. After Sub-plan A ships, each entry will optionally include `runner_up` (additive — the field flows through unchanged).
- `src/utils/api.ts` `fetchSpeakers()` — used by `SpeakerReviewPanel` to populate the registry picker.
- `src/components/AutoMatchBadge.tsx` (pre-deletion reference for Task 3) — shows the existing accept/reject visual treatment that `SpeakerReviewPanel`'s confirm/reject buttons should echo for visual consistency.

---

## Conventions

**Commit hygiene — CRITICAL.** The working tree has ~22 WIP files at start of this plan, including `backend/**`, `deploy/launchd/com.whisper.backend.plist`, `scripts/start-backend.sh`, `src/components/ContextBrowser.tsx`, `src/components/ErrorBoundary.tsx`, `src/components/SpeakerProfile.tsx`, `src/components/SpeakersView.tsx`, `src/hooks/useContexts.ts`, `src/hooks/useSpeakers.ts`, plus several `.m4a` and untracked test artifacts. Sub-plan A is being implemented in parallel and will touch `backend/services/speaker_embedding.py` + `backend/routes/transcription.py` — none of which this plan touches.

**Additionally:** `src/utils/api.ts` has an uncommitted WIP block at lines 1042-1059 (`RenameSourceResponse` interface + `renameJobSource` function). This plan touches `src/utils/api.ts` for the `AutoSpeakerMatch` extension (line ~28) and the `reRefineJob` helper (to be added before line 1042). The `renameJobSource` hunks must NOT be included in this plan's commits — use `git add -p` to interactively stage only this plan's hunks.

**Verify before Task 1**: `git diff src/components/TranscriptView.tsx` should show no WIP. If it does, inspect it: most lines this plan touches (lines 7, 98-100, 131-142, 152-183, 607-682, 913-937, 973-996) are being deleted in Task 5 anyway. If the WIP overlaps with deletion regions, you can discard it after coordinating with the user. If the WIP overlaps with regions this plan keeps (the transcript rendering, edit mode, save flow), preserve it via the stash-dance below.

**Stash dance for every commit in this plan:**

```bash
# Before staging anything:
git status --short

# Stash unrelated WIP so this commit is clean:
git stash push -u -m "sub5B-wip-stash" -- \
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

# For src/utils/api.ts edits (Task 1): use git add -p to stage ONLY the
# hunks this plan adds. The renameJobSource hunk at the bottom must be
# left unstaged ("n" at its prompt).
git add -p src/utils/api.ts

# For all other files: stage by explicit path only.
git add src/components/RejectMatchModal.tsx

# Commit, then restore WIP:
git commit -m "..."
git stash pop
```

**Never use `git add -A` or `git add .`** — both pull in WIP from parallel work and from the `renameJobSource` WIP block.

**Commit per task, not at the end.** Each task ends with a commit step.

**Commit message style** (follow `git log --oneline -10`):
- `chore(api): extend AutoSpeakerMatch with runner_up field`
- `feat(api): add reRefineJob helper for POST /job/{id}/re-refine`
- `feat(ui): add RejectMatchModal component`
- `feat(ui): add SpeakerReviewPanel component`
- `refactor(ui): TranscriptView — replace AutoMatchBadge + Name-the-speakers with SpeakerReviewPanel`
- `chore(ui): delete obsolete AutoMatchBadge component`

**TypeScript strictness:** Project uses TypeScript. `npx tsc --noEmit` must end at **0 errors** (baseline) after each task. If a pre-existing error in unrelated WIP shows up (e.g., something in `SpeakersView.tsx` from parallel work), document it in the task verification step and confirm it's not caused by your edits.

**Testing:** All UI verification is manual via `npm run dev` + browser. The final Task 7 is an explicit smoke checklist (the verification gate). Do NOT add Vitest/RTL.

---

## Task 1: Extend `AutoSpeakerMatch` with `runner_up` + add `reRefineJob` helper

**Files:**
- Modify: `src/utils/api.ts` (interface `AutoSpeakerMatch` ~line 28; new helper near end of file before line 1042 WIP)

- [ ] **Step 1: Read the current `AutoSpeakerMatch` definition + surrounding context**

Run: `sed -n '28,40p' src/utils/api.ts`

Expected output:
```ts
export interface AutoSpeakerMatch {
  name: string | null;
  confidence: number;
  speaker_id: string | null;
  matched: boolean;
  source?: "pick" | "registry" | null;
  note?: string;
}
```

- [ ] **Step 2: Extend `AutoSpeakerMatch` with the additive `runner_up` field**

Edit `src/utils/api.ts`. Replace the `AutoSpeakerMatch` interface (lines ~28-35) with:

```ts
export interface AutoSpeakerMatch {
  name: string | null;
  confidence: number;
  speaker_id: string | null;
  matched: boolean;
  source?: "pick" | "registry" | null;
  note?: string;
  // Plan 5A backend extension: 2nd-best registry candidate from the cosine
  // similarity ranking. Null when registry has <2 candidates or when the
  // runner-up confidence is below the min threshold (~0.4). Optional so
  // pre-Plan-5 jobs and the legacy code path continue to deserialise.
  runner_up?: {
    speaker_id: string;
    name: string;
    confidence: number;
  } | null;
}
```

- [ ] **Step 3: Add the `ReRefineResponse` interface + `reRefineJob` helper**

Edit `src/utils/api.ts`. Locate the `renameJobSource` function (around line 1048). Insert this block **immediately before** the `renameJobSource` block (i.e. before the `export interface RenameSourceResponse` block at line 1042). This placement matters for the `git add -p` skip in Step 5.

```ts
export interface ReRefineResponse {
  job_id: string;
  status: string;
  phase: string | null;
  speakers_created: Array<{ speaker_id: string; name: string }>;
  speakers_assigned: number;
}

/**
 * Plan 5: trigger a single re-refinement run with corrected speaker
 * assignments. `assignments` maps a diarization label (e.g. "SPEAKER_00")
 * to one of:
 *   - a speaker UUID (re-attribute to existing speaker)
 *   - the literal string "unknown" (strip name, mark anonymous)
 *   - "new:<Display Name>" (create a new speaker; backend extracts a voice
 *     embedding from that label's segments via register_speaker)
 *
 * Backend dispatches a single Sonnet refinement call on success, transitioning
 * job.phase from null → "refining" → "learning" → null.
 */
export async function reRefineJob(
  jobId: string,
  assignments: Record<string, string>,
): Promise<ReRefineResponse> {
  const r = await fetchWithTimeout(`${API_URL}/job/${jobId}/re-refine`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ speaker_assignments: assignments }),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`reRefineJob failed: ${r.status} ${detail.slice(0, 200)}`);
  }
  return r.json();
}
```

- [ ] **Step 4: TypeScript check**

Run: `npx tsc --noEmit`

Expected: 0 errors. (If pre-existing errors appear in unrelated files, capture them — they must not be in `src/utils/api.ts`.)

- [ ] **Step 5: Commit (with `git add -p` to skip the WIP)**

```bash
git status --short  # confirm only src/utils/api.ts is modified for this task

# Stash unrelated WIP first:
git stash push -u -m "sub5B-task1-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts

# Interactively stage ONLY the AutoSpeakerMatch and reRefineJob hunks.
# At each hunk prompt:
#   - AutoSpeakerMatch extension (top of file): press "y"
#   - reRefineJob block (mid-file, just above RenameSourceResponse): press "y"
#   - renameJobSource / RenameSourceResponse hunks (bottom of file): press "n"
git add -p src/utils/api.ts

# Verify the staged diff is just this plan's changes:
git diff --cached src/utils/api.ts

git commit -m "chore(api): extend AutoSpeakerMatch with runner_up + add reRefineJob helper"
git stash pop
```

---

## Task 2: Create `RejectMatchModal` component

**Files:**
- Create: `src/components/RejectMatchModal.tsx`

- [ ] **Step 1: Inspect the existing speaker registry shape**

Run: `grep -n "export interface Speaker\b\|export async function fetchSpeakers" src/utils/api.ts`

Expected: a `Speaker` interface with at least `speaker_id: string` and `name: string`, plus `fetchSpeakers()` returning `Promise<Speaker[]>`. (Used by props typing in this task.)

- [ ] **Step 2: Create `RejectMatchModal.tsx`**

Create `src/components/RejectMatchModal.tsx`:

```tsx
import { useState } from 'react';
import { UserX, UserCheck, UserPlus, X } from 'lucide-react';
import { AutoSpeakerMatch, Speaker } from '../utils/api';

/**
 * Resolved target of a reject flow — passed to onAccept by the modal.
 *   - { kind: 'existing', speakerId } — re-attribute to an existing speaker
 *   - { kind: 'new', name } — create a new speaker (backend extracts embedding)
 *   - { kind: 'unknown' } — strip the name, mark the label anonymous
 */
export type RejectTarget =
  | { kind: 'existing'; speakerId: string; name: string }
  | { kind: 'new'; name: string }
  | { kind: 'unknown' };

interface Props {
  label: string;                          // diarization label, e.g. "SPEAKER_00"
  currentMatch: AutoSpeakerMatch;         // the rejected B5 match
  runnerUp?: AutoSpeakerMatch['runner_up']; // null/undefined when no 2nd-best
  registry: Speaker[];                    // for the picker dropdown
  onAccept: (target: RejectTarget) => void;
  onClose: () => void;
}

export default function RejectMatchModal({
  label,
  currentMatch,
  runnerUp,
  registry,
  onAccept,
  onClose,
}: Props) {
  const [pickerValue, setPickerValue] = useState('');
  const [newName, setNewName] = useState('');

  const currentConf = Math.round((currentMatch.confidence ?? 0) * 100);
  const runnerConf = runnerUp ? Math.round((runnerUp.confidence ?? 0) * 100) : null;

  const handlePicker = () => {
    const target = registry.find((s) => s.speaker_id === pickerValue);
    if (target) onAccept({ kind: 'existing', speakerId: target.speaker_id, name: target.name });
  };

  const handleCreate = () => {
    const trimmed = newName.trim();
    if (trimmed) onAccept({ kind: 'new', name: trimmed });
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={`reject-match-title-${label}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-white dark:bg-slate-800 rounded-xl shadow-2xl p-5 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <h3
            id={`reject-match-title-${label}`}
            className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2"
          >
            <UserX className="w-5 h-5 text-rose-500" aria-hidden="true" />
            Reject voice match for {label}
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        {/* Rejected match — greyed out */}
        <div className="px-3 py-2 rounded-lg bg-slate-100 dark:bg-slate-700/40 opacity-60">
          <div className="text-xs text-slate-500 dark:text-slate-400 mb-1">
            B5 thought this was:
          </div>
          <div className="text-sm font-medium text-slate-700 dark:text-slate-300 line-through">
            {currentMatch.name ?? 'Unknown'} ({currentConf}%)
          </div>
        </div>

        {/* Runner-up suggestion (when 5A backend supplies it) */}
        {runnerUp && (
          <div className="px-3 py-3 rounded-lg bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800/40">
            <div className="text-xs text-slate-500 dark:text-slate-400 mb-1">
              Did you mean instead?
            </div>
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-medium text-indigo-700 dark:text-indigo-300">
                {runnerUp.name} ({runnerConf}%)
              </div>
              <button
                type="button"
                onClick={() => onAccept({
                  kind: 'existing',
                  speakerId: runnerUp.speaker_id,
                  name: runnerUp.name,
                })}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-500 text-white hover:bg-indigo-600"
              >
                <UserCheck className="w-3.5 h-3.5" aria-hidden="true" />
                Use this
              </button>
            </div>
          </div>
        )}

        {/* Picker dropdown — free-form re-attribution from the full registry */}
        <div>
          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
            Or pick another speaker:
          </label>
          <div className="flex items-center gap-2">
            <select
              value={pickerValue}
              onChange={(e) => setPickerValue(e.target.value)}
              className="flex-1 px-3 py-1.5 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              <option value="">— Select —</option>
              {registry.map((s) => (
                <option key={s.speaker_id} value={s.speaker_id}>{s.name}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={handlePicker}
              disabled={!pickerValue}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
            >
              Use
            </button>
          </div>
        </div>

        {/* Inline create new speaker */}
        <div>
          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
            Or create a new speaker:
          </label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="New speaker name"
              className="flex-1 px-3 py-1.5 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-400"
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            />
            <button
              type="button"
              onClick={handleCreate}
              disabled={!newName.trim()}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
            >
              <UserPlus className="w-3.5 h-3.5" aria-hidden="true" />
              Create
            </button>
          </div>
        </div>

        {/* Escape hatch */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-200 dark:border-slate-700">
          <button
            type="button"
            onClick={() => onAccept({ kind: 'unknown' })}
            className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 underline"
          >
            Mark as Unknown
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-600"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: TypeScript check**

Run: `npx tsc --noEmit`

Expected: 0 errors. The component imports `AutoSpeakerMatch` and `Speaker` from `../utils/api`, both of which exist (Speaker is pre-existing; AutoSpeakerMatch was extended in Task 1).

- [ ] **Step 4: Commit**

```bash
git status --short  # confirm only RejectMatchModal.tsx is new

git stash push -u -m "sub5B-task2-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts \
  src/utils/api.ts

git add src/components/RejectMatchModal.tsx
git commit -m "feat(ui): add RejectMatchModal component for Plan 5 reject flow"
git stash pop
```

---

## Task 3: Create `SpeakerReviewPanel` component

**Files:**
- Create: `src/components/SpeakerReviewPanel.tsx`

- [ ] **Step 1: Read `useJobAutoRefinePolling` shape so the panel's polling integration is correct**

Run: `sed -n '1,80p' src/hooks/useJobAutoRefinePolling.ts`

Expected: a hook that polls `/job/{id}` and returns `{refinement_status, learning_status, learning_summary, auto_speaker_matches, phase}`. The `SpeakerReviewPanel` does NOT poll directly — it consumes `autoMatches` passed in by `TranscriptView` (which already calls this hook) and reads `phase` from the same polling state via a `currentPhase` prop.

Note for this task: we expose `currentPhase` as an optional prop so the panel can show "Re-refining…" copy that mirrors the backend phase. `TranscriptView` will wire this in Task 4.

- [ ] **Step 2: Read the existing `isAnonymousLabel` helper used in TranscriptView**

Run: `grep -rn "export function isAnonymousLabel\|export const isAnonymousLabel" src/`

Expected: a utility (likely in `src/utils/`) that detects `SPEAKER_XX` style labels. If it lives somewhere importable, this task imports it. If it's inline-defined in `TranscriptView.tsx`, this task uses an equivalent inline regex `/^SPEAKER_\d+$/i` (document both possibilities — Step 3's code uses the regex form; convert to the import if the helper exists).

- [ ] **Step 3: Create `SpeakerReviewPanel.tsx`**

Create `src/components/SpeakerReviewPanel.tsx`:

```tsx
import { useEffect, useMemo, useState } from 'react';
import { UserCheck, UserX, UserPlus, Loader2, Sparkles } from 'lucide-react';
import {
  AutoSpeakerMatch,
  Segment,
  Speaker,
  fetchSpeakers,
  reRefineJob,
} from '../utils/api';
import RejectMatchModal, { RejectTarget } from './RejectMatchModal';

/**
 * Single source of truth for post-completion speaker review (Plan 5).
 * Replaces both:
 *   - the inline AutoMatchBadge per first-occurrence segment
 *   - the "Name the speakers" panel
 *
 * Owns a local `pendingCorrections` map; the user accumulates corrections
 * (confirm / reject / re-attribute / create) before clicking "Apply &
 * re-refine", which sends ONE POST /job/{id}/re-refine and shows a loading
 * state until the polling-driven `currentPhase` returns to null (signalling
 * the backend has finished both refinement + B7 learning).
 */
interface Props {
  jobId: string;
  segments: Segment[];                                  // result.segments
  autoMatches: Record<string, AutoSpeakerMatch>;        // from useJobAutoRefinePolling
  currentPhase?: string | null;                         // from useJobAutoRefinePolling
  onReRefineStart?: () => void;                         // notify parent (clear local edits, etc.)
}

/**
 * Local per-label decision the user has made but not yet submitted.
 *   - confirm: keep the B5 match as-is (no backend op needed, but it
 *     becomes part of the assignments map so the re-refinement run sees
 *     the speaker's profile in context).
 *   - existing: re-attribute to a different registry speaker.
 *   - new: create a new speaker (backend extracts voice embedding).
 *   - unknown: strip the auto-matched name back to the anonymous label.
 */
type CorrectionAction =
  | { kind: 'confirm'; speakerId: string; name: string }
  | { kind: 'existing'; speakerId: string; name: string }
  | { kind: 'new'; name: string }
  | { kind: 'unknown' };

const ANONYMOUS_RE = /^SPEAKER_\d+$/i;

function isAnonymous(label: string): boolean {
  return ANONYMOUS_RE.test(label);
}

export default function SpeakerReviewPanel({
  jobId,
  segments,
  autoMatches,
  currentPhase,
  onReRefineStart,
}: Props) {
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

  const identifiedLabels = allLabels.filter((l) => !isAnonymous(l) || autoMatches[l]?.matched);
  const unknownLabels = allLabels.filter((l) => isAnonymous(l) && !autoMatches[l]?.matched);

  // Load registry once (used for the modal picker + identified-name display).
  useEffect(() => {
    let cancelled = false;
    fetchSpeakers()
      .then((list) => { if (!cancelled) setRegistry(list); })
      .catch(() => { /* silent — modal will show an empty picker */ });
    return () => { cancelled = true; };
  }, []);

  // The panel is in "re-refining" mode when we've fired the POST and the
  // backend phase is non-null. Once it drops back to null, the user can edit
  // again and submit another correction cycle.
  const reRefining = submitting || currentPhase === 'refining' || currentPhase === 'learning';

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

  const handleCreateForAnonymous = (label: string) => {
    const name = (newSpeakerDrafts[label] || '').trim();
    if (name) setAction(label, { kind: 'new', name });
  };

  const handleApply = async () => {
    if (pendingCorrections.size === 0) return;
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
          assignments[label] = 'unknown';
          break;
      }
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await reRefineJob(jobId, assignments);
      onReRefineStart?.();
      // Clear local corrections — the parent's polling will reflect the new
      // segments once the re-refinement completes.
      setPendingCorrections(new Map());
      setNewSpeakerDrafts({});
    } catch (e: any) {
      setSubmitError(e?.message || 'Re-refinement failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDiscard = () => {
    setPendingCorrections(new Map());
    setNewSpeakerDrafts({});
    setSubmitError(null);
  };

  // Render nothing when there are no labels at all (defensive — TranscriptView
  // shouldn't mount the panel in that case anyway).
  if (allLabels.length === 0) return null;

  const renderAction = (label: string) => {
    const action = pendingCorrections.get(label);
    if (!action) return null;
    const verb = action.kind === 'confirm' ? 'Confirmed'
      : action.kind === 'existing' ? `→ ${action.name}`
      : action.kind === 'new' ? `+ New: ${action.name}`
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

  return (
    <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-xl">
      <h3 className="text-sm font-medium text-blue-700 dark:text-blue-300 mb-3 flex items-center gap-2">
        <Sparkles className="w-4 h-4" aria-hidden="true" />
        Speaker Review
      </h3>

      {/* Section A: Identified speakers (auto-matched or already named) */}
      {identifiedLabels.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2 uppercase tracking-wide">
            Identified
          </div>
          <ul className="space-y-2">
            {identifiedLabels.map((label) => {
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
                      <button
                        type="button"
                        onClick={() => handleConfirm(label)}
                        disabled={reRefining || !match?.matched}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
                      >
                        <UserCheck className="w-3 h-3" aria-hidden="true" />
                        Confirm
                      </button>
                      <button
                        type="button"
                        onClick={() => setRejectModalLabel(label)}
                        disabled={reRefining || !match?.matched}
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

      {/* Section B: Unknown speakers (anonymous + no match) */}
      {unknownLabels.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2 uppercase tracking-wide">
            Unknown
          </div>
          <ul className="space-y-2">
            {unknownLabels.map((label) => (
              <li key={label} className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-slate-400 font-mono">{label}</span>
                {renderAction(label) ?? (
                  <>
                    <input
                      type="text"
                      value={newSpeakerDrafts[label] || ''}
                      onChange={(e) =>
                        setNewSpeakerDrafts((prev) => ({ ...prev, [label]: e.target.value }))
                      }
                      placeholder="New speaker name"
                      disabled={reRefining}
                      className="flex-1 min-w-[160px] px-3 py-1 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:opacity-50"
                      onKeyDown={(e) => e.key === 'Enter' && handleCreateForAnonymous(label)}
                    />
                    <button
                      type="button"
                      onClick={() => handleCreateForAnonymous(label)}
                      disabled={reRefining || !(newSpeakerDrafts[label] || '').trim()}
                      className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
                    >
                      <UserPlus className="w-3 h-3" aria-hidden="true" />
                      Create
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Apply / Discard footer */}
      <div className="flex items-center gap-3 mt-4 flex-wrap">
        <button
          type="button"
          onClick={handleApply}
          disabled={reRefining || pendingCorrections.size === 0}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
        >
          {reRefining ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              Re-refining…
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" aria-hidden="true" />
              Apply & re-refine ({pendingCorrections.size})
            </>
          )}
        </button>
        <button
          type="button"
          onClick={handleDiscard}
          disabled={reRefining || pendingCorrections.size === 0}
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

- [ ] **Step 4: TypeScript check**

Run: `npx tsc --noEmit`

Expected: 0 errors. (`Segment` and `Speaker` are pre-existing exports from `src/utils/api.ts`. `reRefineJob` was added in Task 1. `AutoSpeakerMatch.runner_up` was added in Task 1.)

- [ ] **Step 5: Commit**

```bash
git status --short  # confirm only SpeakerReviewPanel.tsx is new

git stash push -u -m "sub5B-task3-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts \
  src/utils/api.ts

git add src/components/SpeakerReviewPanel.tsx
git commit -m "feat(ui): add SpeakerReviewPanel — consolidated post-completion review (Plan 5)"
git stash pop
```

---

## Task 4: Wire `SpeakerReviewPanel` into `TranscriptView` (additive — old surfaces still present)

**Files:**
- Modify: `src/components/TranscriptView.tsx` (add import + render; do NOT yet delete old surfaces — that's Task 5, kept as separate commit for clean review)

This task is intentionally additive so a reviewer can see the panel rendering alongside the old surfaces during dev (visible double-up). Task 5 removes the old surfaces. The two-step split keeps each commit small and the diff easy to review.

- [ ] **Step 1: Add the import**

Edit `src/components/TranscriptView.tsx`. At line 7 (just below the existing `import AutoMatchBadge from './AutoMatchBadge';`), add:

```tsx
import SpeakerReviewPanel from './SpeakerReviewPanel';
```

Do NOT delete the `AutoMatchBadge` import yet.

- [ ] **Step 2: Read the area where the panel will render**

Run: `sed -n '600,610p' src/components/TranscriptView.tsx`

Expected: the closing `</div>` of the language/refinement-status row at ~line 605-606, then the `{/* Name the speakers */}` comment at ~line 607.

- [ ] **Step 3: Insert the `<SpeakerReviewPanel />` render**

Edit `src/components/TranscriptView.tsx`. Locate the closing `</div>` at the end of the language/source row (the one right before the `{/* Name the speakers */}` comment at line ~607). Insert this block **immediately after that closing `</div>`** and **before** the `{/* Name the speakers */}` comment:

```tsx
      {/* Plan 5: consolidated post-completion review panel.
          Replaces the legacy AutoMatchBadge inline render + "Name the
          speakers" block (both removed in the same change as this insert in
          a real cut, kept here as additive Task 4 → Task 5 removes them). */}
      {result?.segments && result.segments.length > 0 && (
        <SpeakerReviewPanel
          jobId={jobId}
          segments={result.segments}
          autoMatches={autoMatches}
          currentPhase={refineState?.phase ?? null}
          onReRefineStart={() => {
            // Best-effort hook for the parent to clear any local UI state
            // that would otherwise stale while the re-refinement runs. The
            // polling hook will pull re-derived segments + matches once the
            // backend completes. Task 4 leaves the legacy `rejectedMatches`
            // state in place (Task 5 deletes it) — for now this callback is
            // intentionally a no-op so the cleanup commits stay isolated.
            // After Task 5, this stays a no-op (or can become a future hook
            // for clearing manual edits, per spec § "Collision with manual
            // segment edits" — out of scope for this plan).
          }}
        />
      )}
```

- [ ] **Step 4: TypeScript check**

Run: `npx tsc --noEmit`

Expected: 0 errors. The `refineState?.phase` access requires `phase` to exist on the `useJobAutoRefinePolling` return type — it was added in Plan 4C (verify by `grep -n "phase" src/hooks/useJobAutoRefinePolling.ts`). If `phase` is somehow missing, pass `null` directly: `currentPhase={null}` (the panel degrades gracefully — Apply still works, just no "Re-refining…" auto-clear) and surface the discrepancy in the commit message.

- [ ] **Step 5: Browser smoke (dev server)**

```bash
npm run dev
```

Open the app, transcribe a short audio with 2+ speakers (or load an existing completed job). Visually verify:
- The new "Speaker Review" panel renders ABOVE the existing "Name the speakers" panel.
- Both surfaces show the speakers (visible duplication is EXPECTED in Task 4 — it's resolved in Task 5).
- No console errors related to `SpeakerReviewPanel` or `reRefineJob`.

Kill `npm run dev` after smoke (Ctrl+C).

- [ ] **Step 6: Commit**

```bash
git status --short  # confirm only TranscriptView.tsx is modified

git stash push -u -m "sub5B-task4-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts \
  src/utils/api.ts

git add src/components/TranscriptView.tsx
git commit -m "feat(ui): TranscriptView — mount SpeakerReviewPanel (additive, old surfaces still present)"
git stash pop
```

---

## Task 5: Remove the legacy surfaces from `TranscriptView` (inline badge + Name-the-speakers + bulk banner)

**Files:**
- Modify: `src/components/TranscriptView.tsx` — delete the `AutoMatchBadge` import (line 7), the `rejectedMatches` state (~line 100), the `firstOccurrenceIndex` useMemo (~lines 131-142), `handleAcceptAutoMatch` (~lines 157-179) and `handleRejectAutoMatch` (~lines 181-183), the `draftAssignments`/`assignSaving`/`assignError`/`insightStatus` state (~lines 94-97), `handleAssignSpeakers` (~lines 185-235), the "Name the speakers" JSX block (~lines 607-682), the bulk "Accept all" mini-banner (~lines 913-937), and the inline `<AutoMatchBadge ... />` render block + the surrounding `showBadge`/`firstOccurrenceIndex` IIFE (~lines 973-996).

This task is intentionally aggressive — the panel from Task 4 replaces ALL of these surfaces. Anything that still consumes one of the deleted symbols (e.g., a stray reference to `rejectedMatches` outside the bulk banner) must also be cleaned up.

- [ ] **Step 1: Delete the `AutoMatchBadge` import**

Edit `src/components/TranscriptView.tsx`. Delete line 7:

```tsx
import AutoMatchBadge from './AutoMatchBadge';
```

Keep the `SpeakerReviewPanel` import added in Task 4.

- [ ] **Step 2: Delete unused state declarations**

In `src/components/TranscriptView.tsx`, locate and delete these state declarations (the line numbers below are approximate — match the variable names):

```tsx
// Around line 94-97 — delete all 4 lines:
const [draftAssignments, setDraftAssignments] = useState<Record<string, string>>({});
const [assignSaving, setAssignSaving] = useState(false);
const [assignError, setAssignError] = useState<string | null>(null);
const [insightStatus, setInsightStatus] = useState<'idle' | 'running' | 'done'>('idle');

// Around line 100 — delete:
const [rejectedMatches, setRejectedMatches] = useState<Record<string, boolean>>({});
```

The `registry` state (line 93) STAYS — `SpeakerReviewPanel` fetches its own copy, but the legacy "Rename Speakers" block (which this plan does NOT touch) still reads it.

- [ ] **Step 3: Delete the `firstOccurrenceIndex` useMemo**

In `src/components/TranscriptView.tsx`, delete the `firstOccurrenceIndex` useMemo (lines ~131-142):

```tsx
const firstOccurrenceIndex = useMemo(() => {
  const map = new Map<string, number>();
  (result?.segments ?? []).forEach((seg, i) => {
    const spk = seg.speaker;
    if (spk && !map.has(spk)) map.set(spk, i);
  });
  return map;
}, [result?.segments]);
```

Plus the explanatory comment immediately above it.

- [ ] **Step 4: Delete the `handleAcceptAutoMatch` and `handleRejectAutoMatch` handlers**

In `src/components/TranscriptView.tsx`, delete the entire `handleAcceptAutoMatch` function (lines ~157-179) and `handleRejectAutoMatch` (lines ~181-183), plus their preceding explanatory comment block (lines ~154-156).

- [ ] **Step 5: Delete `handleAssignSpeakers`**

In `src/components/TranscriptView.tsx`, delete the entire `handleAssignSpeakers` function (lines ~185-235). The block ends at the closing `};` followed by a blank line before `// Get current playing segment index`.

- [ ] **Step 6: Delete the "Name the speakers" JSX block**

In `src/components/TranscriptView.tsx`, delete the entire `{anonymousLabels.length > 0 && ( ... )}` block at lines ~607-682 (starting with the `{/* Name the speakers */}` comment at line ~607, ending with the closing `)}` after the `</div>` at line ~682). Also delete the `anonymousLabels` useMemo (around line 126-129) if `SpeakerReviewPanel` is now its only consumer — verify with `grep -n "anonymousLabels" src/components/TranscriptView.tsx` after the delete; if the count is 0 the variable + useMemo can be removed.

- [ ] **Step 7: Delete the bulk "Accept all" mini-banner**

In `src/components/TranscriptView.tsx`, delete the IIFE block at lines ~913-937 — the entire `{(() => { const pending = ... })()}` expression starting with `{/* B6b: mini-banner with bulk "Accept all" ... */}` and ending at the closing `})()}`.

- [ ] **Step 8: Delete the inline `<AutoMatchBadge />` render**

In `src/components/TranscriptView.tsx`, locate the `showSpeakers && segment.speaker && !isEditing && (() => { ... })()` block at lines ~973-996. Replace this entire IIFE with the simplified non-badge version:

```tsx
                  {showSpeakers && segment.speaker && !isEditing && (
                    <span className="flex items-center gap-1 pt-1 whitespace-nowrap">
                      <span className="text-purple-400 font-medium text-xs sm:text-sm">
                        {speakerNames[segment.speaker] || segment.speaker}:
                      </span>
                    </span>
                  )}
```

(`speakerNames` is a pre-existing prop/state already used elsewhere in the file — verify by `grep -n "speakerNames" src/components/TranscriptView.tsx`. It stays.)

- [ ] **Step 9: Scan for orphan references**

Run: `grep -n "rejectedMatches\|firstOccurrenceIndex\|handleAcceptAutoMatch\|handleRejectAutoMatch\|draftAssignments\|assignSaving\|assignError\|insightStatus\|handleAssignSpeakers\|AutoMatchBadge" src/components/TranscriptView.tsx`

Expected: **no output** (all references deleted). If any remain, delete them too — they are dangling references to the removed handlers/state.

Also check for now-unused imports from `lucide-react`:

Run: `grep -n "from 'lucide-react'" src/components/TranscriptView.tsx`

Then verify each icon imported on that line still has a usage via `grep`. Common ones that may now be orphans: `UserPlus`, `Save` (both were used by "Name the speakers" only). Remove unused entries from the import statement.

- [ ] **Step 10: TypeScript check**

Run: `npx tsc --noEmit`

Expected: 0 errors. (If errors appear about unused vars, that's a strict-mode hint that you missed an orphan in Step 9 — re-run the grep.)

- [ ] **Step 11: Browser smoke**

```bash
npm run dev
```

Open the app, load a completed transcription with 2+ speakers. Visually verify:
- The "Name the speakers" panel is GONE.
- The bulk "Accept all" indigo banner above the transcript is GONE.
- No inline `auto · NN%` badges next to speaker labels in the transcript.
- The new "Speaker Review" panel is the ONLY speaker-correction surface above the transcript.
- The "Rename Speakers" block (legacy free-form renamer) is still present and works — this plan does NOT touch it.
- No console errors.

Kill `npm run dev`.

- [ ] **Step 12: Commit**

```bash
git status --short  # confirm only TranscriptView.tsx is modified

git stash push -u -m "sub5B-task5-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts \
  src/utils/api.ts

git add src/components/TranscriptView.tsx
git commit -m "refactor(ui): TranscriptView — remove AutoMatchBadge inline + Name-the-speakers panel (Plan 5)"
git stash pop
```

---

## Task 6: Delete the obsolete `AutoMatchBadge` component

**Files:**
- Delete: `src/components/AutoMatchBadge.tsx`

- [ ] **Step 1: Final import scan**

Run: `grep -rn "AutoMatchBadge" src/`

Expected: **no output**. Task 5 deleted the only importer (`TranscriptView.tsx:7`) and the only render site (`TranscriptView.tsx:987`). If output appears, do NOT delete — investigate the stray reference first.

- [ ] **Step 2: Delete the file**

```bash
rm src/components/AutoMatchBadge.tsx
```

- [ ] **Step 3: TypeScript check**

Run: `npx tsc --noEmit`

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git status --short  # confirm only AutoMatchBadge.tsx deletion

git stash push -u -m "sub5B-task6-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts \
  src/utils/api.ts

git add src/components/AutoMatchBadge.tsx
git commit -m "chore(ui): delete obsolete AutoMatchBadge (replaced by SpeakerReviewPanel)"
git stash pop
```

---

## Task 7: Manual smoke verification (the verification gate for this plan)

**Files:** None (verification-only).

**Prerequisite:** Sub-plan A must be deployed to the backend you're smoking against. If 5A is not yet merged, this task verifies degraded-mode behavior (runner-up missing, Apply button 404s) — note both in the task output and mark BLOCKED on Apply.

This task is the verification gate per the Path A convention (no Vitest). Walk through the checklist end-to-end; do not mark the plan complete until every box is checked.

- [ ] **Step 1: Start the app**

```bash
npm run dev
```

In a separate terminal, ensure the backend is running (matches your local launchd setup — `tail -f ~/.whisper-backend.log` to confirm it's healthy).

- [ ] **Step 2: Verify the panel mounts for a fresh transcription**

Upload a short audio file (10-60s, 2+ speakers — re-use a Just Press Record `.m4a` from `Tests/` if available). Wait for the job to complete. Then verify:

- [ ] The "Speaker Review" panel appears above the transcript, with a `Sparkles` icon and a section "Identified" listing any auto-matched speakers (registry hits) and a section "Unknown" listing any anonymous `SPEAKER_XX` labels with no match.
- [ ] The legacy "Name the speakers" panel does NOT appear.
- [ ] The inline `auto · NN%` badges (the old `AutoMatchBadge`) do NOT appear next to speaker names in the transcript.
- [ ] The legacy bulk "Accept all" indigo banner above the transcript does NOT appear.
- [ ] The "Rename Speakers" block (legacy free-form renamer, separate component) still appears — this plan does NOT touch it.

- [ ] **Step 3: Confirm flow**

Click "Confirm" on an identified speaker. Verify:

- [ ] The Confirm/Reject buttons disappear and a green `Confirmed` chip appears.
- [ ] The chip has a `×` button that clears the correction.
- [ ] The "Apply & re-refine (N)" button is now enabled with count = 1.

- [ ] **Step 4: Reject flow with runner-up (requires 5A)**

Click "Reject" on an identified speaker. The `RejectMatchModal` opens. Verify:

- [ ] The rejected match is shown greyed-out + struck-through with its confidence %.
- [ ] If Sub-plan A is deployed AND the registry has 2+ speakers with similarity above the runner-up threshold, the "Did you mean instead?" section appears with a "Use this" button. (If 5A is not deployed yet, this section is silently absent — that's the graceful fallback. Note the absence in your task report.)
- [ ] The picker dropdown lists all registry speakers.
- [ ] The "Create new speaker" input accepts text and the Create button enables.
- [ ] The "Mark as Unknown" link is visible at the bottom-left.
- [ ] Clicking the runner-up's "Use this" closes the modal and shows `→ <Name>` in the panel.
- [ ] Clicking Cancel or clicking outside the modal closes it without setting a correction.

- [ ] **Step 5: Unknown speaker create flow**

Find an anonymous `SPEAKER_XX` label in the Unknown section. Type a name in the input and click Create. Verify:

- [ ] The input + Create button disappear and a green `+ New: <Name>` chip appears.
- [ ] Pressing Enter in the input is equivalent to clicking Create.

- [ ] **Step 6: Apply & re-refine (requires 5A)**

Click "Apply & re-refine (N)". Verify:

- [ ] The button label changes to "Re-refining…" with a spinner.
- [ ] All Confirm/Reject/Create buttons in the panel are disabled.
- [ ] Network tab shows ONE `POST /job/{id}/re-refine` request with a body matching the assignments map shape (`{"speaker_assignments": {"SPEAKER_00": "uuid-...", "SPEAKER_02": "new:My New Speaker", ...}}`).
- [ ] After the backend completes (poll cycle), the transcript re-renders with the corrected speaker labels.
- [ ] The pending corrections map is cleared.
- [ ] The panel returns to interactive state (buttons re-enabled).

If 5A is not deployed: the POST returns 404 and the `submitError` chip shows `reRefineJob failed: 404 ...`. The button re-enables and corrections remain. Mark this step as BLOCKED-ON-5A in your task report.

- [ ] **Step 7: Discard flow**

Make 2-3 corrections without applying. Click "Discard changes". Verify:

- [ ] All Confirmed / `→ Name` / `+ New: Name` chips disappear.
- [ ] All Confirm/Reject buttons + create inputs return.
- [ ] The Apply button is disabled (count = 0).

- [ ] **Step 8: TypeScript baseline**

Run: `npx tsc --noEmit`

Expected: **0 errors**. If non-zero, the plan is not complete — go back and fix.

- [ ] **Step 9: Final git status**

Run: `git status --short`

Expected: only the WIP files unrelated to this plan should appear modified. None of: `src/components/SpeakerReviewPanel.tsx`, `src/components/RejectMatchModal.tsx`, `src/components/TranscriptView.tsx`, `src/utils/api.ts` should be in the modified-but-uncommitted set. (`src/utils/api.ts` may still show as modified because of the `renameJobSource` WIP at the bottom — that is expected and is NOT this plan's concern.)

Run: `git log --oneline -8`

Expected: 6 new commits at the top with the messages from Tasks 1-6, in order.

- [ ] **Step 10: Report**

Mark this task DONE only if every checkbox in Steps 2-9 is checked. If any are BLOCKED (e.g., 5A not deployed), report DONE_WITH_CONCERNS with the specific blocker.

---

## Self-Review Summary

**Spec coverage** (cross-checked against `docs/superpowers/specs/2026-05-17-davrine-speaker-review-design.md`):

| Spec section | Implemented by |
|---|---|
| Single consolidated UI surface | Task 3 (SpeakerReviewPanel) + Task 4 (mount) + Task 5 (delete old surfaces) |
| Two sections (Identified + Unknown) | Task 3 — `identifiedLabels`/`unknownLabels` derivation |
| Local `pendingCorrections` state, no backend during accumulation | Task 3 — `useState<Map>` + handlers don't call API |
| Reject → 2nd-best modal with picker fallback | Task 2 (RejectMatchModal) + Task 3 (modal triggering) |
| Inline "Create new speaker" for anonymous labels | Task 3 — `unknownLabels` section |
| Single explicit "Apply & re-refine" button | Task 3 — `handleApply` posts once |
| POST `/job/{id}/re-refine` with `speaker_assignments` map | Task 1 (`reRefineJob`) + Task 3 (call site) |
| "new:name" / speaker UUID / "unknown" assignment values | Task 3 — `handleApply` builds these |
| Loading state during in-flight re-refinement | Task 3 — `reRefining` flag + button label |
| Polling integration for re-refinement completion | Task 3 — `currentPhase` prop driven by parent's polling |
| `AutoSpeakerMatch.runner_up` consumption | Task 1 (interface) + Task 2 (modal) + Task 3 (passthrough) |
| Delete `AutoMatchBadge.tsx` | Task 6 |
| Replace inline badge render in TranscriptView | Task 5 Step 8 |
| Replace "Name the speakers" panel in TranscriptView | Task 5 Step 6 |
| Lockstep with Plan 5A | Header "Dependency lockstep" + Task 7 BLOCKED-ON-5A markers |
| Graceful pre-Plan-5 fallback (no runner_up) | Task 1 — `runner_up` is optional in interface; Task 2 — modal hides the section when null |

**Out of scope confirmations:**
- No pipeline-blocking gate before initial refinement (spec § Out of scope). Confirmed — this plan only touches post-completion UI.
- No auto-trigger re-refinement on each correction (spec § Out of scope). Confirmed — single explicit Apply button.
- No "Re-refining will replace your manual edits" confirmation modal in this plan. Spec § Out of scope mentions this copy as a needed warning; deferring to a follow-up because the existing TranscriptView edit-mode flow is orthogonal and the spec lists it under "Collision with manual segment edits" as warning copy, not a hard requirement for Plan 5. If the user has unsaved edits when clicking Apply, the re-refinement will overwrite per the spec — document in release notes.
