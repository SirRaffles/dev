# UX Touchpoints Audit — Plan 3 (B6 implementations)

Date: 2026-05-15
Spec: `docs/superpowers/specs/2026-05-15-davrine-continuous-improvement-design.md`
Plan: `docs/superpowers/plans/2026-05-15-davrine-continuous-improvement-plan3-ux-surfaces.md`
Branch: `dev`

This audit is the load-bearing deliverable that gates Plan 3 Tasks 3-8. Each row in the
summary table identifies the file, the current code state, the desired new state, and the
**exact line ranges** where the implementer should insert / replace / delete code. Subsequent
implementer subagents should read their relevant Per-task notes section and go directly to
the line ranges below.

## Summary table

| Task | Surface | Current state | Desired state | Files to modify | Insertion-point line ranges |
|------|---------|---------------|---------------|-----------------|----------------------------|
| B6a  | TranscriptView header chip row | Language + Speakers + (optional) YouTube-captions chip; no refinement indicator | Spinner "Refining…" while pending/processing, then "Refined" badge | `TranscriptView.tsx`, new `RefinementBadge.tsx`, new `useJobAutoRefinePolling.ts` | Header wrapper `TranscriptView.tsx:521-557`. Language `<div>` ends at L532. Insert `<RefinementBadge status={refineState?.refinement_status} />` **between L532 and L533** (i.e. as a new child after the language `<div>`, before the speakers `<div>`). Import + hook call goes at the top: import block currently L1-5; add new import lines after L5. Hook call near other useEffects, after L116 (after the `AUTO_MATCH_CONFIDENCE` const). |
| B6b  | TranscriptView speaker labels + the "Name the speakers" block | Component fetches `/job/{id}/speakers/auto-match` post-hoc and pre-fills `draftAssignments` inputs passively (Lines 118-149). The "Name the speakers" block (L564-658) shows the inputs plus inline confidence chips (L602-628). Anonymous speaker label rendering in segment list at L924-928. | Read `auto_speaker_matches` from the new `useJobAutoRefinePolling` hook. Render `<AutoMatchBadge>` (Accept / Reject) next to each anonymous speaker label in the segment list. The passive pre-fill of `draftAssignments` is GONE. | `TranscriptView.tsx`, new `AutoMatchBadge.tsx` | **DELETE:** import of `fetchJobAutoMatchSuggestions` + `AutoMatchSuggestion` from L3 (keep `assignJobSpeakers`, `fetchSpeakers`, `Speaker`, `SpeakerAssignmentInput`). **DELETE:** state declarations `autoMatch`, `autoMatchMode`, `autoMatchLoading` at L80-82. **DELETE:** the auto-match useEffect at L118-149. **DELETE:** the confidence-chip rendering inside the "Name the speakers" block at L572-575 and L602-628. **KEEP:** the "Name the speakers" block as a fallback for manual rename (L564-658, minus the deletions). **ADD:** `<AutoMatchBadge />` mount inside the segment loop at L924-928 — wrap or augment the existing `{showSpeakers && segment.speaker && !isEditing && <span>…</span>}` so that when `autoMatches[segment.speaker]?.matched === true` (and not locally rejected), the badge renders right after the speaker name span. New import for `AutoMatchBadge` after L5; new local state `rejectedMatches: Record<string, boolean>` near L72. |
| B6c  | Contexts tab top | `ContextBrowser` opens directly with a folder list inside a single card (L123-210), then below it a generic file editor card (L212-254) | Dedicated `_global.md` editor card mounted ABOVE the folder list, with two sections (Active / Pending review) and "Promote → Active" per pending entry | `ContextBrowser.tsx`, new `GlobalGlossaryEditor.tsx`, `backend/routes/contexts.py`, `src/utils/api.ts` | **MOUNT POINT:** the root return of `ContextBrowser` at `ContextBrowser.tsx:123-124`. The outer `<div className="space-y-4">` opens at L124. Insert `<GlobalGlossaryEditor />` as the FIRST child immediately after L124 (i.e. before the existing folders card at L125). Import after L7. Backend: `_safe_path` defined at `backend/routes/contexts.py:31-44`, `FileWriteRequest` model at L27-29, `CONTEXTS_DIR` at L19. Pattern to mirror: the existing `@router.get("/contexts/files/{path:path}")` at L197 and `@router.put("/contexts/files/{path:path}")` at L210-227. Add new endpoints `@router.get("/contexts/_global")` and `@router.put("/contexts/_global")` immediately after the existing file routes (e.g. between L227 and L228). Editor textarea pattern to mirror: existing edit `<textarea>` in `ContextBrowser.tsx:242-247`; save button + dirty state pattern at L228-238. |
| B6d  | App root | No post-job toast | "Learned: N glossary terms, M speaker insights, K voice embeddings updated" toast auto-dismisses 12s; click → navigates to Activity tab | `App.tsx`, new `LearningToast.tsx` | **CRITICAL BINDING:** in `App.tsx`, the active-job state is destructured at L112: `const { transcription, multiModal, isDocumentMode, sourceType, active, resetAll, updateResult } = useProcessingState(file);`. The `active` object is **NOT** a job object — it is a derived view (see `src/hooks/useProcessingState.js:17-31`) exposing **only** `result, error, isProcessing, progress, progressMessage, jobId`. **There is NO `active.status` field.** Job-completed is signaled by `!!active.result && !active.isProcessing` (or by checking `active.result.status === 'completed'` if needed — `active.result` IS the job DTO from `fetchJobStatus`). The plan's claim that `active.status` exists at L537/L648 is INCORRECT — those lines use `active.jobId` and `active.result`, not `active.status`. **MOUNT LOCATION:** the outer return wrapper opens at `App.tsx:268-270` (`<div className="min-h-screen…"><div className="… max-w-…">`). Mount `<LearningToast jobId={active.jobId} jobCompleted={!!active.result && !active.isProcessing} onClickReview={() => setActiveTab('activity')} />` as a sibling of the inner content div — ideally as the LAST child inside the outer `<div className="min-h-screen…">` (i.e. just before the closing `</div>` at L693), so the toast renders fixed-position above any tab. Alternatively place it as the first child of the inner `<div className={…max-w…}>` at L270. Either way, the toast must be OUTSIDE the `{activeTab === 'transcribe' && (<> … </>)}` block (L302-691) so it survives tab changes. |
| B6e  | New "Activity" nav tab | Five tabs in `Navigation.tsx`: transcribe, recordings, calls, speakers, contexts | Six tabs including `activity`; paginated `/learning/log` timeline | `Navigation.tsx`, `App.tsx`, new `ActivityTimeline.tsx`, new `useLearningLog.ts` | **`Navigation.tsx`:** the `NavTab` type union is declared at L4 — extend it to `'transcribe' \| 'recordings' \| 'calls' \| 'speakers' \| 'contexts' \| 'activity'`. The `TABS` array is at L11-17 — append `{ id: 'activity', label: 'Activity', icon: Activity }` after L16. Add `Activity` to the `lucide-react` import on L2 (the convention is to import icon components from `lucide-react`). **`App.tsx`:** the lazy-load block for tab views is at L33-36 — add `const ActivityTimeline = lazy(() => import('./components/ActivityTimeline'));` after L36. The tab dispatch lives inside the `<Suspense>` block at L295-298 — add `{activeTab === 'activity' && <ActivityTimeline />}` between L298 and L299. |
| B6f  | SettingsPanel | Flat grid of all knobs (L309-731), no progressive disclosure | "Advanced" `<details>` accordion (default closed) wrapping the advanced knobs; common knobs stay above the fold | `SettingsPanel.tsx` | The settings grid is `<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">` opening at L309 and closing at L731. Above-the-fold knobs stay where they are. Wrap the move-to-advanced knobs in a new `<details className="..."><summary>Advanced</summary>…</details>` block inserted between L730 (close of last advanced knob's wrapper) and L731 (close of grid div) — or more cleanly, restructure so the advanced knobs are extracted from the grid and placed in a sibling `<details>` block AFTER the grid (i.e. between L731 and L732). See "Per-task notes B6f" below for the enumerated knob list with exact line ranges. |

## Per-task notes

### B6a (refinement-status indicator)

- **Polling hook (NEW):** `src/hooks/useJobAutoRefinePolling.ts` per plan Task 3 Step 2. Mirrors `usePollingJob.js` (`src/hooks/usePollingJob.js:7-141`) but polls only the 4 B2 fields (`refinement_status`, `auto_speaker_matches`, `learning_status`, `learning_summary`) and stops once `refinement_status ∈ {done, failed}`. Active only when the job is already `completed` (so the parent transcription poller in `usePollingJob` has already terminated).
- **Existing polling:** `usePollingJob` (`src/hooks/usePollingJob.js`) sets `result` from the `/job/{id}` response on `completed`/`failed`. It does NOT expose `refinement_status` or `learning_status` to consumers — see L42-66. That's why a separate hook is needed.
- **Insertion point in TranscriptView:** the chip row wrapper at `TranscriptView.tsx:521` (`<div className="flex flex-wrap items-center gap-2 sm:gap-4 mb-6 p-3 bg-slate-100 dark:bg-slate-700/50 rounded-lg text-sm sm:text-base">`). Children:
  - L522-532 — Language `<div>` (closes at L532).
  - L533-539 — Speakers `<div>`.
  - L540-556 — YouTube-captions `<span>` (conditional).
  Insert the new `<RefinementBadge>` between L532 and L533 (right after the language `<div>`).
- **Tailwind chip pattern to match:** the YouTube-captions chip at L548-555 is the cleanest existing chip:
  - `inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-700 dark:text-amber-400` (amber for in-progress)
  - `inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/20 text-green-700 dark:text-green-400` (green for completed/done)
  RefinementBadge should match these so the visual rhythm of the chip row is preserved.
- **Spinner:** `Loader2` from `lucide-react` is already imported on L2 of `TranscriptView.tsx` and used at L575, L640, L689, L730, L753 with `className="… animate-spin"`. Use it in `RefinementBadge` for the `pending`/`processing` state.
- **No new state in TranscriptView:** the hook returns `refineState`; the badge consumes it directly. Already-decoupled.

### B6b (auto-match badges)

- **DELETE imports:** at `TranscriptView.tsx:3` remove `fetchJobAutoMatchSuggestions, AutoMatchSuggestion`. Keep `assignJobSpeakers, fetchSpeakers, Speaker, SpeakerAssignmentInput`. The line becomes:
  `import { LANGUAGES, updateSegments, updateSpeakers, Segment, fetchSpeakers, assignJobSpeakers, Speaker, SpeakerAssignmentInput } from '../utils/api';`
- **DELETE state at L80-82:** the three `autoMatch*` state hooks become irrelevant — `auto_speaker_matches` now arrives from `useJobAutoRefinePolling`.
- **DELETE useEffect at L118-149:** the entire post-hoc fetcher block.
- **DELETE the chip-rendering branches inside the "Name the speakers" block:**
  - L572-575: the `autoMatchMode` + `autoMatchLoading` status line.
  - L602-628: the three confidence chips (`autoMatched`, `existing/new` chip stays in some form, but the `autoMatched` and "maybe X · N%" chips are now redundant — the new `<AutoMatchBadge>` near the segment label IS the visible confirmation). Keep the `existing` / `new speaker` chip (L610-620) for inputs the user types manually.
- **DATA SOURCE:** `const autoMatches = refineState?.auto_speaker_matches || {};` after the polling hook call.
- **BADGE MOUNT:** the per-segment speaker label is rendered at `TranscriptView.tsx:924-928`:
  ```
  {showSpeakers && segment.speaker && !isEditing && (
    <span className="text-purple-400 …">
      {speakerNames[segment.speaker] || segment.speaker}:
    </span>
  )}
  ```
  Augment this to also render `<AutoMatchBadge label={segment.speaker} match={autoMatches[segment.speaker]} onAccept={…} onReject={…} />` immediately after the `<span>` when `autoMatches[segment.speaker]?.matched === true && !rejectedMatches[segment.speaker]`. The badge should render only on the FIRST occurrence of each label (track `seenLabels: Set<string>` inside the segment `.map` so the badge isn't repeated per segment) — alternatively render only when `isAnonymousLabel(segment.speaker)` is true (i.e. the label is still "SPEAKER_00"-style — once the user accepts, the next render's segments are renamed so the badge naturally disappears).
- **Accept handler:** `assignJobSpeakers(jobId, [{ label, speaker_name: match.speaker_name, create_new: false }], true)` — same signature as the existing `handleAssignSpeakers` at L151-201, just for one label at a time.
- **Reject handler:** `setRejectedMatches(prev => ({ ...prev, [label]: true }))` — local-only state, no backend call. Suppresses the badge for the rest of the session.
- **BEHAVIOR CHANGE (callout for implementer):** the passive pre-fill of `draftAssignments` at L134-143 is INTENTIONALLY REMOVED. Do NOT preserve it. The Accept / Reject badge IS the new UX — users explicitly confirm every voice match. This is a deliberate shift toward "user signs off" rather than "we silently rename and hope you notice".

### B6c (`_global.md` editor)

- **MOUNT POINT:** at the top of the `<div className="space-y-4">` wrapper opening at `ContextBrowser.tsx:123-124`. Render `<GlobalGlossaryEditor />` as the FIRST child immediately after `<div className="space-y-4">` on L124 (before the existing card `<div className="bg-white/80 …">` at L125). The `space-y-4` parent provides natural vertical spacing.
- **Add import** after L7 (the existing `useContexts`, `fetchContextFile` imports): `import GlobalGlossaryEditor from './GlobalGlossaryEditor';`
- **Backend file:** `backend/routes/contexts.py`. Relevant existing infrastructure:
  - L19: `CONTEXTS_DIR = ICLOUD_BASE_PATH / "contexts"`
  - L27-29: `class FileWriteRequest(BaseModel)` with single `content: str` field (reuse this).
  - L31-44: `def _safe_path(user_path: str) -> Path` — path-traversal-safe resolver inside `CONTEXTS_DIR`. For `_global.md` use this directly: `target = _safe_path("_global.md")` (or skip _safe_path and inline `target = CONTEXTS_DIR / "_global.md"` since the path is fixed).
  - L197-208: `@router.get("/contexts/files/{path:path}")` — read pattern (returns `content` field).
  - L210-227: `@router.put("/contexts/files/{path:path}")` — write pattern (accepts `FileWriteRequest`, writes file with `utf-8` encoding, creates parent dirs).
  Add `@router.get("/contexts/_global")` and `@router.put("/contexts/_global")` immediately after the file routes (between L227 and L228). The GET endpoint should return `{"content": "", "exists": false}` when the file is missing (don't 404 — the editor's empty state is "no glossary yet").
- **Editor UI pattern to mirror:** `ContextBrowser.tsx:212-254` — the existing in-file editor:
  - L213-218: card wrapper with `bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border …`
  - L220-238: header row with title + edit/preview toggle + Save button (`dirty` gate).
  - L242-247: edit-mode `<textarea>` with `w-full h-80 bg-slate-50 dark:bg-slate-700/50 border …`
  - L248-251: preview-mode `<pre>` wrapper.
  Match these patterns so the new GlobalGlossaryEditor visually integrates with the rest of the Contexts tab.
- **Active / Pending review semantics (from plan):** parse the markdown into two sections by heading (`## Active`, `## Pending review`). Each line in the Pending section gets a "Promote → Active" inline button. See plan Task 5 Step 2 for the rendering code. **Open question:** should "Promote" MOVE the line (remove from Pending) or COPY (audit trail)? See open questions section.

### B6d (post-job toast)

- **CRITICAL — exact App.tsx active-job binding:** the active-job state lives in:
  - L112: destructuring `const { transcription, multiModal, isDocumentMode, sourceType, active, resetAll, updateResult } = useProcessingState(file);`
  - Source: `src/hooks/useProcessingState.js:17-31` defines `active` as `{ result, error, isProcessing, progress, progressMessage, jobId }` via `useMemo`.
  - **There is NO `active.status` field.** The plan's note on L905-909 of plan3.md claiming `active.status === 'completed'` is wrong — `active` does not expose `status`. The correct boolean for "job is completed" is `!!active.result && !active.isProcessing`. Optionally, `active.result?.status === 'completed'` (since `active.result` IS the full job DTO from `fetchJobStatus`, which does include a `status` field — see `usePollingJob.js:55-59`).
  - Correct bindings to pass into the toast:
    ```ts
    const currentJobId = active?.jobId || null;
    const isCompleted = !!active?.result && !active?.isProcessing;
    ```
- **MOUNT LOCATION:** mount the toast OUTSIDE the per-tab guard block at L302-691 so it survives tab switches. Two clean options:
  - **Preferred:** as the LAST child of the outer wrapper at L268-694. The outer `<div className="min-h-screen…">` opens at L269 and closes at L693. Mount the toast just before the closing `</div>` on L693.
  - **Alternative:** as the first child of the inner `<div className={`${viewMode === ViewMode.VISUAL ? 'max-w-6xl' : 'max-w-4xl'} mx-auto …`}>` at L270.
  Either way the toast component itself should use `position: fixed` (e.g. `fixed bottom-6 right-6 z-50`) so it doesn't disturb layout.
- **Toast trigger:** the toast inside renders only when `props.summary != null` (i.e. `refineState?.refinement_status === 'done' && refineState.learning_summary`).
- **Navigation hook:** the toast's "Review activity →" / click handler calls `onClickReview` → `() => setActiveTab('activity')` (depends on B6e being implemented first; if not, fall back to no-op or hide the link).

### B6e (Activity timeline)

- **`Navigation.tsx`:**
  - L2: lucide-react import — append `Activity` to the destructured icon list (e.g. `import { FileAudio, Mic, Phone, Users, FolderOpen, Activity } from 'lucide-react';`).
  - L4: extend the `NavTab` union: `export type NavTab = 'transcribe' | 'recordings' | 'calls' | 'speakers' | 'contexts' | 'activity';`
  - L11-17: `TABS` array — append `{ id: 'activity', label: 'Activity', icon: Activity }` between L16 (the `contexts` entry) and L17 (closing `]`).
- **`App.tsx`:**
  - L26-36: lazy-load block. After L36 (`const ContextBrowser = lazy(...)`) add: `const ActivityTimeline = lazy(() => import('./components/ActivityTimeline'));`
  - L295-298: the per-tab dispatch inside the `<Suspense>` wrapper. Between L298 (`{activeTab === 'contexts' && <ContextBrowser />}`) and L299 (closing `</Suspense>`), add `{activeTab === 'activity' && <ActivityTimeline />}`.
- **Default filter:** **OPEN QUESTION** — should the timeline show all event types or filter to `glossary_add + embedding_update` by default? See open questions section. Recommendation: default to all, with a filter pill row at the top.

### B6f (Settings progressive disclosure) — REQUIRED enumeration

Below is the complete enumeration of `SettingsPanel.tsx` knobs with their exact line ranges and the keep/move decision.

**Above-the-fold (KEEP in main view; do not wrap in `<details>`):**

- **Engine selector** — `L225-273` (Voxtral Local / Whisper / Cloud toggle row).
- **Output Mode toggle (Verbatim/Readable)** — `L276-306`.
- **Model Size selector** — `L311-367`. (Engine-aware: switches between MODEL_SIZES, VOXTRAL_MODELS, VOXTRAL_LOCAL_MODELS.) KEEP because every transcription requires a model choice. The Parakeet variants ARE listed inside the same `<select>` (L349-361) — they share one widget so they can't be separately hidden without rewriting the select. Decision: keep the model-size widget itself above-the-fold; the "headline 3" interpretation in the task description does not cleanly map to the current single-select; document this and let user revise.
- **Language selector** — `L370-407`.
- **Translate to English toggle** — `L410-429` (conditional: shown only when `language !== 'en' && !isVoxtralApi`).
- **Speaker Diarization toggle** — `L432-462` (engine-aware: Voxtral API shows a read-only "built-in" badge; otherwise a toggle).
- **Number of Speakers** — `L465-486` (shown only when `!isVoxtralApi && enableDiarization`).
- **Context Document selector** — `L489-512` (the `contextPath` dropdown).
- **Expected Speakers combobox** — `L519-623` (shown only when `enableDiarization` and conditional on `parsedNumSpeakers`).

**Behind-Advanced (MOVE into `<details>` accordion, default closed):**

- **Context Terms (free-form bias terms)** — `L626-642`. Voxtral Cloud only. Niche knob, ok to hide.
- **Two-Pass Mode** — `L645-665`. Voxtral Cloud only, and only when language is set. Niche + cost-doubling — definitely behind disclosure.
- **Word Timestamps toggle** — `L668-685`. Default off; perf trade-off most users won't tune.
- **Noise Reduction toggle** — `L688-705`. Niche knob.
- **Speed Priority (Parakeet) toggle** — `L708-730`. Whisper-only. The 60x-speed claim is impressive but the knob itself is rarely flipped after the first time.

**Knobs called out in the baseline that don't currently exist in the codebase (so no action needed):**

- `temperature` ladder, `beam_size`, `patience`, `best_of`, `vad_filter` — these are backend-only settings; `SettingsPanel.tsx` does not currently render UI for them.
- `two_pass` — exists; mapped above.
- `word_timestamps`, `enable_noise_reduction` — exist; mapped above.
- `model_size` variants beyond the headline 3 — all live inside the same single `<select>` widget (L349-361). Splitting them out would require rewriting the select; deferred. Implementer should KEEP the existing widget above the fold and use the `<option disabled>` pattern (already in place at L355) to denote which variants are advanced.

**Implementation suggestion for the implementer:** rather than wrapping the existing grid children with `<details>`, extract the advanced knobs out of the grid entirely and place them in a sibling `<details>` block below the grid:

- Close the grid at the current L731 boundary.
- Insert a new `<details className="mt-6 rounded-xl border border-slate-200 dark:border-slate-600 p-4"><summary className="cursor-pointer text-sm font-medium text-slate-700 dark:text-slate-300">Advanced options</summary><div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">{…advanced knobs…}</div></details>` between L731 and L732.

## Open questions for user

These need user confirmation before Tasks 3-8 can finalize:

1. **B6e default filter:** should the Activity timeline show **all** event types, or filter to `glossary_add + embedding_update` only by default? (Recommendation: show all with a pill-row filter; users can narrow.)
2. **B6d toast dismiss policy:** auto-dismiss 12s + click-X, or sticky until the user clicks "Review activity →"? (Plan currently says auto-dismiss 12s — confirm?)
3. **B6c "Promote → Active":** should it MOVE the line out of Pending (no audit trail in the `_global.md` file) or COPY (line appears in both sections; cleaner audit but visual duplication)? Either way the line eventually has to be removable.
4. **B6b AutoMatchBadge placement:** the audit recommends rendering the badge on the FIRST occurrence of each anonymous label in the segment list (not per-segment). Confirm. Alternative: pin a sticky badge row at the top of the transcript card, grouped by label.
5. **B6f progressive disclosure scope:** the audit splits the existing grid into above-the-fold + a `<details>` block (sibling). Confirm this structural change is acceptable vs. wrapping in-place.
6. **B6a polling cadence:** plan says start at 2s, back off after 30s. Confirm acceptable for the dev environment (NAS-Mac wake-from-sleep adds latency).
7. **`active.status` vs `active.result.status`:** plan Task 6 (`LearningToast` mount) refers to `active?.status` (plan line 909). This field does NOT exist on `active` (see `useProcessingState.js:17-31`). Confirm the implementer should use `!!active.result && !active.isProcessing` for completion, and `active.result?.status` if the raw job status is needed.

## Gating

- **This audit MUST be reviewed and accepted by the user before Tasks 3-8 (B6a/b/c/d/e/f UI work + the supporting hook/component files) begin.**
- **Task 2** (the backend orchestrator fix for the insight worker reading stale `job.segments`) **CAN proceed in parallel** with this audit review — it touches only backend code (`backend/services/auto_refine_orchestrator.py` and friends) and has no dependency on the UI insertion points documented here.
- Once the user accepts this audit, implementer subagents for Tasks 3-8 should each read the relevant Per-task notes section + their task-specific section in `docs/superpowers/plans/2026-05-15-davrine-continuous-improvement-plan3-ux-surfaces.md` before touching code. The line ranges above are anchored to the current `dev` branch HEAD; if a prior task's commit lands first and shifts lines, the next task should re-grep for the anchor strings (e.g. `"Language & Speakers Info"`, `class="space-y-4"`, `bg-white/80 dark:bg-slate-800/50`) rather than blindly trust the line numbers.
