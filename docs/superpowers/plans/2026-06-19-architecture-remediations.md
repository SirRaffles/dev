# Architecture Remediations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement incremental remediations from the enriched architecture report without broad rewrites.

**Architecture:** Prefer small deep modules around existing seams. Each task must keep changes scoped, preserve current behavior, and improve locality or leverage at one interface.

**Tech Stack:** React 18, TypeScript, Vite, FastAPI/Python backend, Playwright e2e.

---

### Task 1: Extract Speaker Label Policy

**Files:**
- Create: `src/utils/speakerLabels.ts`
- Modify: `src/components/TranscriptView.tsx`
- Modify: `src/components/SpeakerReviewPanel.tsx`

- [ ] **Step 1: Add shared speaker label module**

Create `src/utils/speakerLabels.ts` with the anonymous-label regex local to the module and `isAnonymousLabel` exported.

- [ ] **Step 2: Move imports**

`TranscriptView.tsx` and `SpeakerReviewPanel.tsx` must import `isAnonymousLabel` from `../utils/speakerLabels`. `SpeakerReviewPanel.tsx` must no longer import from `./TranscriptView`.

- [ ] **Step 3: Verify cycle is gone**

Run: `fallow dead-code --quiet`
Expected: no circular dependency involving `TranscriptView.tsx` and `SpeakerReviewPanel.tsx`.

- [ ] **Step 4: Verify build**

Run: `npm run build`
Expected: exit 0.

### Task 2: Extract Speaker Review Decisions

**Files:**
- Create: `src/utils/speakerReviewDecisions.ts`
- Modify: `src/components/SpeakerReviewPanel.tsx`

- [ ] **Step 1: Extract decision serialization**

Create `buildSpeakerAssignments(pendingCorrections, needsReviewMode)` in `src/utils/speakerReviewDecisions.ts`. It must preserve existing mappings:
- `confirm` and `existing` map to `speakerId`
- `new` maps to `new:<name>`
- `unknown` maps to `ignore` only when `needsReviewMode` is true
- `ignore` maps to `ignore`

- [ ] **Step 2: Use extracted module**

`SpeakerReviewPanel.tsx` must delegate assignment serialization to the new module and keep rendering behavior unchanged.

- [ ] **Step 3: Verify build**

Run: `npm run build`
Expected: exit 0.

### Task 3: Extract Transcription Session Start Logic

**Files:**
- Create: `src/hooks/useTranscriptionSession.ts`
- Modify: `src/App.tsx`

- [ ] **Step 1: Extract start orchestration**

Create a hook that owns the start decision for sleeping/waking Mac state, batch file transcription, document processing, single file transcription, and YouTube transcription. Preserve existing behavior and settings shape.

- [ ] **Step 2: Shrink App**

`App.tsx` must call the hook instead of holding all `startProcessing` branching inline. It may still own UI state.

- [ ] **Step 3: Verify build**

Run: `npm run build`
Expected: exit 0.

### Task 4: Extract Backend Match Scope

**Files:**
- Create: `backend/services/speaker_match_scope.py`
- Modify: `backend/routes/transcription.py`
- Modify: `backend/services/orchestrator.py`
- Modify: `backend/tests/test_speaker_auto_match_scope.py`

- [ ] **Step 1: Move match-scope policy**

Move `_resolve_match_scope` from `backend/routes/transcription.py` to `backend/services/speaker_match_scope.py` as `resolve_match_scope`.

- [ ] **Step 2: Update route and orchestrator**

Both `backend/routes/transcription.py` and `backend/services/orchestrator.py` must import `resolve_match_scope` from the service module. `orchestrator.py` must no longer import route helpers for match scope.

- [ ] **Step 3: Update tests**

`backend/tests/test_speaker_auto_match_scope.py` must import from the new service module.

- [ ] **Step 4: Verify focused backend tests**

Run: `cd backend && python -m pytest tests/test_speaker_auto_match_scope.py`
Expected: exit 0.

### Task 5: Extract E2E Helpers For Duplicated Setup

**Files:**
- Create or modify: `e2e/helpers.ts`
- Modify: `e2e/call-intelligence.spec.ts`
- Modify: `e2e/speaker-review-panel.spec.ts`

- [ ] **Step 1: Extract helpers**

Extract duplicated navigation/setup helpers for opening tabs and finding history jobs. Preserve test behavior.

- [ ] **Step 2: Use helpers**

Both e2e specs should import helpers instead of repeating setup fragments.

- [ ] **Step 3: Verify TypeScript build**

Run: `npm run build`
Expected: exit 0.

### Task 6: Split Frontend Client By Workflow

**Files:**
- Create: `src/api/http.ts`
- Create: `src/api/transcription.ts`
- Create: `src/api/speakers.ts`
- Create: `src/api/calls.ts`
- Create: `src/api/contexts.ts`
- Create: `src/api/recordings.ts`
- Modify: `src/utils/api.ts`

- [ ] **Step 1: Introduce workflow modules**

Move fetch helper and workflow functions into `src/api/*` modules while preserving public exports from `src/utils/api.ts`.

- [ ] **Step 2: Keep compatibility interface**

`src/utils/api.ts` must re-export the same public names so existing callers continue to build.

- [ ] **Step 3: Remove unused exports only if safe**

Do not remove exports used by tests or future routes unless `fallow dead-code --quiet` still reports them after the split.

- [ ] **Step 4: Verify build and Fallow**

Run: `npm run build`
Expected: exit 0.

Run: `fallow dead-code --quiet`
Expected: no new circular dependencies.
