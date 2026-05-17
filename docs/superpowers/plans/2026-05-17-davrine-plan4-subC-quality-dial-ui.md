# Plan 4 Sub-plan C — UI Quality Dial + Phased Progress Bar

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the engine selector + model dropdown in `SettingsPanel` with a 2-position Quality dial (Best/Quick) and add a phase pill above `ProgressBar`. After this sub-plan, the frontend submits only `engine: 'auto-best' | 'auto-quick'`, no longer references `modelSize`, and shows the current backend phase ("Diarizing…", "Transcribing…", "Refining…", "Learning…") above the progress bar.

**Architecture:** Pure-frontend change. Replaces the 3-button engine row + 3 model dropdowns + Speed/Two-Pass/Word-Timestamps/Context-Terms knobs in `SettingsPanel` with one Quality dial component (2 buttons). Updates `App.tsx` default settings to `engine: 'auto-best'`. Extends `useJobAutoRefinePolling` to also surface `phase` (Sub-plan A backend writes `phase` to `/job/{id}`). Renders a phase pill in `ProgressBar` above the existing 0-100% bar. Does NOT delete dead constants/hooks (Sub-plan D handles that sweep).

**Tech Stack:** React 18 + TypeScript + TailwindCSS, `lucide-react` icons (`Sparkles` for Best, `Zap` for Quick). Existing patterns: `React.memo` for components, settings flow via prop drilling from `App.tsx` → `SettingsPanel`, polling hooks in `src/hooks/`.

**⚠️ Test framework prerequisite — read before starting Task 1**

This repo has **no Vitest or React Testing Library installed**. `package.json` devDeps include only `@playwright/test`, `@vitejs/plugin-react`, `tsc`, `tailwindcss`, etc. There is no `test` script, no `vitest.config.*`, no existing `*.test.tsx` files, no `node_modules/@testing-library/`. Following Plan 3's convention, this codebase uses **Playwright e2e + manual smoke** for frontend verification, not component unit tests.

**Two paths the implementer chooses between** (pick at Task 1):

- **Path A (recommended, matches Plan 3 convention):** **skip every Vitest test in this plan.** Tasks 1-7 that show `npx vitest run …` → instead verify via `npx tsc --noEmit` for type-correctness and `npm run dev` + browser smoke for behavior. Don't commit any `*.test.tsx` files. Task 8 (manual smoke) is the real verification.

- **Path B (only if user explicitly wants to set up a test harness):** insert a Task 0 that adds `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` to devDeps; creates `vitest.config.ts` with `environment: 'jsdom'`; adds `setupTests.ts` importing `@testing-library/jest-dom`; adds `"test": "vitest run"` to package.json scripts. Then Tasks 1-7's Vitest snippets work as-is.

**Default**: Path A. The `npx vitest run …` commands and the `*.test.tsx` file creation steps in Tasks 1, 2, 3 below are aspirational — skip them, type-check with tsc, manually smoke via `npm run dev`. Do NOT commit test files that have no runner.

**Dependency lockstep:** This sub-plan **must ship in the same release as Sub-plan A**. After Sub-plan A lands, the backend rejects any `engine` value other than `auto-best`/`auto-quick` with HTTP 400. The frontend cut-over here must happen at the same moment, or every transcription submission 400s.

**Out of scope (deferred to Sub-plan D):**
- Deleting `src/hooks/useEngineAvailability.ts` (kept alive temporarily — App.tsx still consumes it)
- Deleting `MODEL_SIZES`, `VOXTRAL_MODELS`, `VOXTRAL_LOCAL_MODELS`, `ENGINES` constants in `src/utils/api.ts`
- Deleting the engine-capability disclosure block added in commit `c5e4a53`
- Deleting the Word-Timestamps engine-gating added in commit `4f57b10`
- Removing `fallbackNotice` rendering and the `setSettings(prev => ({...prev, ...fallback}))` branch in App.tsx
- Deleting `docs/engines.md`

This plan ONLY adds the dial + phase pill and removes the old engine selector JSX from `SettingsPanel`. Everything else lives until D.

---

## File Structure

**Create:**
- `src/components/QualityDial.tsx` — 2-button Best/Quick toggle component (memoised, controlled). Owns the visual treatment of the dial (selected state, sub-labels, icons). Pure presentation: takes `value` + `onChange` props, no side effects.
- `src/components/PhasePill.tsx` — small pill rendered above `ProgressBar`. Maps a `phase` string to a human label + icon. Returns `null` when `phase` is null/undefined.
- `src/components/__tests__/QualityDial.test.tsx` — Vitest + RTL component test for the dial.
- `src/components/__tests__/PhasePill.test.tsx` — Vitest + RTL component test for the pill.

**Modify:**
- `src/components/SettingsPanel.tsx` — remove the engine selector row (lines ~225-273), remove the engine capability disclosure block (lines ~275-293), remove the model-size selector inside the Settings Grid (lines ~330-387), remove the Context Terms / Two-Pass / Word Timestamps / Speed Priority knobs from the Advanced details block. Replace with a Quality dial at the top. Drop the `voxtralAvailable` and `voxtralLocalAvailable` props. Drop `modelSize`, `speedPriority`, `engine`, `contextTerms`, `twoPass` from the `Settings` interface (kept in App.tsx state, but no longer destructured in SettingsPanel since the dial owns engine).
- `src/App.tsx` — change default `settings.engine` from `'voxtral-local'` to `'auto-best'`. Drop the `modelSize: 'voxtral-mini-3b'` default (or replace with `modelSize: undefined`). Stop passing `voxtralAvailable`/`voxtralLocalAvailable` to `<SettingsPanel>`. Stop passing `modelSize`/`speedPriority`/`twoPass`/`contextTerms` in the `options` object that flows into `transcription.transcribeFile`. Read `active.phase` from `useProcessingState` and pass it into `<ProgressBar phase={…} />`. Inside the `useWakeOnLan` `onAwake` handler and the proxy-detection effect, change the explicit fallback `setSettings(prev => ({ ...prev, engine: 'whisper', modelSize: 'large-v3-turbo' }))` to `setSettings(prev => ({ ...prev, engine: 'auto-best' }))` and drop the `engine`/`modelSize` keys from the spread of `fallback` when applied.
- `src/utils/api.ts` — narrow `TranscriptionOptions.engine` from `string` to `'auto-best' | 'auto-quick'`. Inside `submitTranscription` and `submitYouTubeTranscription`, change the default for `engine` from `'voxtral-local'` to `'auto-best'`, drop the `model_size` param from the `URLSearchParams` (the backend ignores it after Sub-plan A), and drop `speed_priority` / `two_pass` / `context_terms` params. **Do NOT delete** `MODEL_SIZES`, `VOXTRAL_MODELS`, `VOXTRAL_LOCAL_MODELS`, `ENGINES` exports — Sub-plan D handles them. **Do NOT change** `TranscriptionOptions.modelSize`/`speedPriority`/etc. field declarations — they become unused but stay; Sub-plan D removes them.
- `src/hooks/useJobAutoRefinePolling.ts` — extend `AutoRefineState` interface with `phase: string | null`, read `j.phase` in `fetchJobAutoRefineState` (in `api.ts`), and surface it through the hook. Add `phase` to `fetchJobAutoRefineState` return type.
- `src/hooks/useProcessingState.js` — surface a `phase` field on `active` so `App.tsx` can pass it to `ProgressBar`. For now, `active.phase` reads from `transcription.phase` (the underlying `usePollingJob` already polls `/job/{id}` while the job is active and stores the raw response — we extend it minimally to expose `phase`).
- `src/hooks/useTranscription.ts` — expose `phase` from the underlying `usePollingJob` by adding `phase: job.phase` to its return object.
- `src/hooks/usePollingJob.js` — add a `phase` state tracked from the polled `/job/{id}` response. Expose via the hook return value. (Note: this file is JavaScript, not TypeScript — no type annotations.)
- `src/components/ProgressBar.tsx` — accept a new optional `phase?: string | null` prop. Render `<PhasePill phase={phase} />` ABOVE the `<Loader2>` + message row when `phase` is non-null.

**Reference (read, don't touch):**
- `docs/superpowers/specs/2026-05-17-davrine-quality-dial-orchestration-design.md` — authoritative spec. The "Quality Dial UX" section (~lines 39-56) defines the dial layout; the "Phased Progress Bar" section (~lines 200-230) defines the phase lifecycle table.
- `docs/superpowers/audits/2026-05-15-ux-touchpoints.md` — line-range pointers into `SettingsPanel.tsx` for Plan 3's audit. Useful sanity check for edit anchors.
- `src/utils/api.ts` `fetchJobStatus` (~line 272) — returns the full `JobStatus` JSON; backend Sub-plan A adds `phase` to that JSON.

---

## Conventions

**Commit hygiene — CRITICAL.** The working tree has ~22 WIP files at start of this plan, including `src/components/SettingsPanel.tsx`, `src/App.tsx`, `src/utils/api.ts`, and several backend/test files. Sub-plan A is being implemented in parallel and will touch some of the same backend files.

**Stash dance for every commit in this plan:**

```bash
# Before staging anything:
git status --short

# Stash unrelated WIP (and untracked junk) so your commit is clean:
git stash push -u -m "subC-wip-stash" -- \
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

# Then stage ONLY the files this task touches:
git add src/components/QualityDial.tsx src/components/__tests__/QualityDial.test.tsx

# Commit, then restore WIP:
git commit -m "..."
git stash pop
```

**Never use `git add -A` or `git add .`** — both pull in WIP from parallel work.

**If `SettingsPanel.tsx` has WIP from Plan 3 followups** (you'll see it in `git status`), inspect that diff with `git diff src/components/SettingsPanel.tsx` BEFORE this plan starts. Most of those WIP changes are removed in Task 4 of this plan anyway (the engine selector, capability disclosure, model-size dropdown, Word-Timestamps gating, Context-Terms knob all go away). If the WIP is to lines you're deleting, just discard it (`git checkout -- src/components/SettingsPanel.tsx` after stashing) and re-apply the Task 4 changes on the clean file. If the WIP is to lines you're keeping (language picker, diarization toggle, expected speakers, etc.), preserve it.

**Commit per task, not at the end.** Each task ends with a commit step.

**Commit message style** (follow existing `git log --oneline -10`):
- `feat(ui): add Quality dial to SettingsPanel`
- `feat(ui): phase pill above progress bar`
- `feat(ui): App.tsx — default to auto-best engine`
- `chore(api): narrow TranscriptionOptions.engine to auto-best | auto-quick`

**Testing:** UI changes are partially TDD-able with React Testing Library. Tasks 1 and 2 use TDD (write failing component test → implement → test passes). Tasks 4-6 are UI-integration changes harder to TDD — for those, end with a manual Playwright check (run dev server, click through Best/Quick, submit a small audio, verify phase pill appears).

**TypeScript strictness:** Project uses TypeScript. `npx tsc --noEmit` should pass after each task. Run it as part of the verification step.

---

## Task 1: Create `QualityDial` component (TDD)

**Files:**
- Create: `src/components/QualityDial.tsx`
- Create: `src/components/__tests__/QualityDial.test.tsx`

- [ ] **Step 1: Write the failing component test**

Create `src/components/__tests__/QualityDial.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import QualityDial from '../QualityDial';

describe('QualityDial', () => {
  it('renders Best and Quick buttons with sub-labels', () => {
    render(<QualityDial value="auto-best" onChange={() => {}} />);
    expect(screen.getByRole('radio', { name: /best/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /quick/i })).toBeInTheDocument();
    expect(screen.getByText(/~10 min/i)).toBeInTheDocument();
    expect(screen.getByText(/~30 sec/i)).toBeInTheDocument();
  });

  it('marks Best as checked when value is auto-best', () => {
    render(<QualityDial value="auto-best" onChange={() => {}} />);
    expect(screen.getByRole('radio', { name: /best/i })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('radio', { name: /quick/i })).toHaveAttribute('aria-checked', 'false');
  });

  it('marks Quick as checked when value is auto-quick', () => {
    render(<QualityDial value="auto-quick" onChange={() => {}} />);
    expect(screen.getByRole('radio', { name: /best/i })).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByRole('radio', { name: /quick/i })).toHaveAttribute('aria-checked', 'true');
  });

  it('calls onChange with auto-quick when Quick button is clicked', () => {
    const onChange = vi.fn();
    render(<QualityDial value="auto-best" onChange={onChange} />);
    fireEvent.click(screen.getByRole('radio', { name: /quick/i }));
    expect(onChange).toHaveBeenCalledWith('auto-quick');
  });

  it('calls onChange with auto-best when Best button is clicked', () => {
    const onChange = vi.fn();
    render(<QualityDial value="auto-quick" onChange={onChange} />);
    fireEvent.click(screen.getByRole('radio', { name: /best/i }));
    expect(onChange).toHaveBeenCalledWith('auto-best');
  });

  it('does not fire onChange when disabled', () => {
    const onChange = vi.fn();
    render(<QualityDial value="auto-best" onChange={onChange} disabled />);
    fireEvent.click(screen.getByRole('radio', { name: /quick/i }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it('uses radiogroup role on the wrapper', () => {
    render(<QualityDial value="auto-best" onChange={() => {}} />);
    expect(screen.getByRole('radiogroup', { name: /quality/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app && npx vitest run src/components/__tests__/QualityDial.test.tsx --reporter=verbose`

Expected: FAIL with `Cannot find module '../QualityDial'`.

- [ ] **Step 3: Implement `QualityDial`**

Create `src/components/QualityDial.tsx`:

```tsx
import React from 'react';
import { Sparkles, Zap } from 'lucide-react';

export type QualityMode = 'auto-best' | 'auto-quick';

interface QualityDialProps {
  value: QualityMode;
  onChange: (next: QualityMode) => void;
  disabled?: boolean;
}

interface DialOption {
  id: QualityMode;
  label: string;
  subLabel: string;
  waitLabel: string;
  Icon: typeof Sparkles;
  activeClass: string;
}

const OPTIONS: DialOption[] = [
  {
    id: 'auto-best',
    label: 'Best',
    subLabel: 'Full pipeline',
    waitLabel: '~10 min',
    Icon: Sparkles,
    activeClass: 'bg-blue-500 text-white border-blue-500',
  },
  {
    id: 'auto-quick',
    label: 'Quick',
    subLabel: 'Fast preview',
    waitLabel: '~30 sec',
    Icon: Zap,
    activeClass: 'bg-teal-500 text-white border-teal-500',
  },
];

function QualityDial({ value, onChange, disabled = false }: QualityDialProps) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
        Quality
      </label>
      <div
        role="radiogroup"
        aria-label="Quality"
        className="grid grid-cols-2 gap-2"
      >
        {OPTIONS.map(({ id, label, subLabel, waitLabel, Icon, activeClass }) => {
          const selected = value === id;
          return (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => { if (!disabled) onChange(id); }}
              disabled={disabled}
              className={`flex flex-col items-center justify-center gap-1 px-4 py-4 rounded-xl font-medium border transition-all disabled:opacity-50 ${
                selected
                  ? activeClass
                  : 'bg-slate-100 text-slate-700 border-slate-300 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-200 dark:border-slate-600 dark:hover:bg-slate-600'
              }`}
            >
              <div className="flex items-center gap-2">
                <Icon className="w-4 h-4" aria-hidden="true" />
                <span>{label}</span>
              </div>
              <span className={`text-xs ${selected ? 'opacity-90' : 'opacity-70'}`}>
                {subLabel}
              </span>
              <span className={`text-xs ${selected ? 'opacity-90' : 'opacity-70'}`}>
                {waitLabel}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default React.memo(QualityDial);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/__tests__/QualityDial.test.tsx --reporter=verbose`

Expected: All 7 tests PASS.

- [ ] **Step 5: TypeScript check**

Run: `npx tsc --noEmit`

Expected: No errors related to QualityDial. (Existing errors in unrelated WIP files may remain — they're not yours.)

- [ ] **Step 6: Commit**

```bash
git status --short  # confirm only the 2 new files are different
git stash push -u -m "subC-task1-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SettingsPanel.tsx src/components/SpeakerProfile.tsx \
  src/components/SpeakersView.tsx src/hooks/useContexts.ts \
  src/hooks/useSpeakers.ts src/utils/api.ts
git add src/components/QualityDial.tsx src/components/__tests__/QualityDial.test.tsx
git commit -m "feat(ui): add QualityDial component (2-position Best/Quick)"
git stash pop
```

---

## Task 2: Create `PhasePill` component (TDD)

**Files:**
- Create: `src/components/PhasePill.tsx`
- Create: `src/components/__tests__/PhasePill.test.tsx`

- [ ] **Step 1: Write the failing component test**

Create `src/components/__tests__/PhasePill.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import PhasePill from '../PhasePill';

describe('PhasePill', () => {
  it('returns null when phase is null', () => {
    const { container } = render(<PhasePill phase={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('returns null when phase is undefined', () => {
    const { container } = render(<PhasePill phase={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders "Diarizing…" for phase=diarizing', () => {
    render(<PhasePill phase="diarizing" />);
    expect(screen.getByText('Diarizing…')).toBeInTheDocument();
  });

  it('renders "Transcribing…" for phase=transcribing', () => {
    render(<PhasePill phase="transcribing" />);
    expect(screen.getByText('Transcribing…')).toBeInTheDocument();
  });

  it('renders "Aligning…" for phase=aligning', () => {
    render(<PhasePill phase="aligning" />);
    expect(screen.getByText('Aligning…')).toBeInTheDocument();
  });

  it('renders "Refining…" for phase=refining', () => {
    render(<PhasePill phase="refining" />);
    expect(screen.getByText('Refining…')).toBeInTheDocument();
  });

  it('renders "Learning…" for phase=learning', () => {
    render(<PhasePill phase="learning" />);
    expect(screen.getByText('Learning…')).toBeInTheDocument();
  });

  it('renders the raw phase capitalized for an unknown value', () => {
    render(<PhasePill phase="exporting" />);
    expect(screen.getByText('Exporting…')).toBeInTheDocument();
  });

  it('exposes status role for accessibility', () => {
    render(<PhasePill phase="transcribing" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/__tests__/PhasePill.test.tsx --reporter=verbose`

Expected: FAIL with `Cannot find module '../PhasePill'`.

- [ ] **Step 3: Implement `PhasePill`**

Create `src/components/PhasePill.tsx`:

```tsx
import React from 'react';

interface PhasePillProps {
  phase?: string | null;
}

const PHASE_LABELS: Record<string, string> = {
  diarizing: 'Diarizing…',
  transcribing: 'Transcribing…',
  aligning: 'Aligning…',
  refining: 'Refining…',
  learning: 'Learning…',
};

function PhasePill({ phase }: PhasePillProps) {
  if (!phase) return null;

  const label = PHASE_LABELS[phase] ?? `${phase.charAt(0).toUpperCase()}${phase.slice(1)}…`;

  return (
    <span
      role="status"
      aria-live="polite"
      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" aria-hidden="true" />
      {label}
    </span>
  );
}

export default React.memo(PhasePill);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/__tests__/PhasePill.test.tsx --reporter=verbose`

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git status --short
git stash push -u -m "subC-task2-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SettingsPanel.tsx src/components/SpeakerProfile.tsx \
  src/components/SpeakersView.tsx src/hooks/useContexts.ts \
  src/hooks/useSpeakers.ts src/utils/api.ts
git add src/components/PhasePill.tsx src/components/__tests__/PhasePill.test.tsx
git commit -m "feat(ui): add PhasePill component for progress phase labels"
git stash pop
```

---

## Task 3: Plumb `phase` through polling + processing-state hooks

**Files:**
- Modify: `src/utils/api.ts` (`fetchJobAutoRefineState` return + `JobStatus` interface)
- Modify: `src/hooks/usePollingJob.js` (add `phase` state — file is JavaScript, no TS annotations)
- Modify: `src/hooks/useTranscription.ts` (expose `phase`)
- Modify: `src/hooks/useProcessingState.js` (surface `phase` on `active`)
- Modify: `src/hooks/useJobAutoRefinePolling.ts` (read `phase` too, since spec says learning-status overlap)

Background: Sub-plan A's backend adds a `phase: Optional[str]` field to the `/job/{id}` JSON response. The frontend needs to surface that everywhere it polls the job. The transcription poller (`usePollingJob`) runs while the job is `pending`/`processing` and tracks `phase=diarizing|transcribing|aligning`. After the job hits `completed`, the auto-refine poller (`useJobAutoRefinePolling`) takes over and tracks `phase=refining|learning`. Both feed `active.phase` via `useProcessingState`.

- [ ] **Step 1: Inspect `usePollingJob` to plan the edit**

Run: `cat src/hooks/usePollingJob.js`

Note: This is a JS file (~143 lines). The polled response is unpacked inside `pollJobStatus` (around lines 40-66). You'll add a `setPhase` call there alongside `setProgress`/`setProgressMessage`.

- [ ] **Step 2: Extend `JobStatus` and `fetchJobAutoRefineState` in `src/utils/api.ts`**

In `src/utils/api.ts`, modify the `JobStatus` interface (around line 43) to add `phase?: string | null;`:

```ts
export interface JobStatus {
  job_id: string;
  status: string;
  progress?: number;
  // ... existing fields ...
  // Sub-plan A: orchestrator's current pipeline phase
  // ("diarizing" | "transcribing" | "aligning" | "refining" | "learning" | null)
  phase?: string | null;
}
```

Modify `fetchJobAutoRefineState` (around line 66) to return `phase` too:

```ts
export async function fetchJobAutoRefineState(jobId: string): Promise<{
  refinement_status: RefinementStatus;
  learning_status: LearningStatus;
  learning_summary: LearningSummary | null;
  auto_speaker_matches: Record<string, AutoSpeakerMatch> | null;
  phase: string | null;
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
  };
}
```

- [ ] **Step 3: Add `phase` to `usePollingJob.js`**

Read `src/hooks/usePollingJob.js` end-to-end first (it's ~143 lines). The hook takes a generic `fetchStatusFn` and stores `progress`, `progressMessage`, `result`, `error`. We add a parallel `phase` slot.

Make these three edits to `src/hooks/usePollingJob.js`:

**Edit 1** — add `phase` state alongside the other `useState` calls (currently around lines 8-13). Insert after the `setError` line:

```js
const [phase, setPhase] = useState(null);
```

So the block becomes:

```js
const [isActive, setIsActive] = useState(false);
const [jobId, setJobId] = useState(null);
const [progress, setProgress] = useState(0);
const [progressMessage, setProgressMessage] = useState('');
const [result, setResult] = useState(null);
const [error, setError] = useState(null);
const [phase, setPhase] = useState(null);
```

**Edit 2** — inside `pollJobStatus` (currently around line 53), right after `setProgressMessage(data.progress_message || '');`, add:

```js
setPhase(data.phase ?? null);
```

So the block becomes:

```js
setProgress(nextProgress);
setProgressMessage(data.progress_message || '');
setPhase(data.phase ?? null);
```

**Edit 3** — inside `reset` (currently around lines 111-119), add `setPhase(null);` after the existing `setError(null);`:

```js
const reset = useCallback(() => {
  stopPolling();
  setIsActive(false);
  setJobId(null);
  setProgress(0);
  setProgressMessage('');
  setResult(null);
  setError(null);
  setPhase(null);
}, [stopPolling]);
```

**Edit 4** — in the returned object (currently around lines 125-140), add `phase` between `error` and `startJob`:

```js
return {
  isActive,
  jobId,
  progress,
  progressMessage,
  result,
  error,
  phase,
  startJob,
  failJob,
  reset,
  updateResult,
  setProgress,
  setProgressMessage,
  stopPolling,
  pollJobStatus,
};
```

- [ ] **Step 4: Expose `phase` from `useTranscription`**

In `src/hooks/useTranscription.ts`, find the returned object (around line 184). Add `phase: job.phase` to the return:

```ts
return {
  // ... existing fields ...
  phase: job.phase,
};
```

- [ ] **Step 5: Surface `phase` on `active` via `useProcessingState`**

In `src/hooks/useProcessingState.js`, extend the `active` memo (currently around line 17). Document modules can't be in a phase, so multiModal contributes `null`:

```js
const active = useMemo(() => ({
  result: isDocumentMode ? multiModal.result : transcription.result,
  error: isDocumentMode ? multiModal.error : transcription.error,
  isProcessing: isDocumentMode ? multiModal.isProcessing : transcription.isTranscribing,
  progress: isDocumentMode ? multiModal.progress : transcription.progress,
  progressMessage: isDocumentMode ? multiModal.progressMessage : transcription.progressMessage,
  jobId: isDocumentMode ? multiModal.jobId : transcription.jobId,
  // Sub-plan A surfaces orchestrator pipeline phase via /job/{id}.phase
  phase: isDocumentMode ? null : (transcription.phase ?? null),
}), [
  isDocumentMode,
  multiModal.result, multiModal.error, multiModal.isProcessing,
  multiModal.progress, multiModal.progressMessage, multiModal.jobId,
  transcription.result, transcription.error, transcription.isTranscribing,
  transcription.progress, transcription.progressMessage, transcription.jobId,
  transcription.phase,
]);
```

- [ ] **Step 6: Extend `useJobAutoRefinePolling` to expose `phase`**

In `src/hooks/useJobAutoRefinePolling.ts`, extend `AutoRefineState` (around line 4):

```ts
interface AutoRefineState {
  refinement_status: RefinementStatus;
  learning_status: LearningStatus;
  learning_summary: LearningSummary | null;
  auto_speaker_matches: Record<string, AutoSpeakerMatch> | null;
  phase: string | null;
}
```

Since `fetchJobAutoRefineState` now returns `phase` (Step 2), `setState(next)` already wires it through — no further changes needed.

- [ ] **Step 7: TypeScript check**

Run: `npx tsc --noEmit`

Expected: no errors introduced by these changes (existing unrelated errors may remain).

- [ ] **Step 8: Re-run existing tests to ensure nothing broke**

Run: `npx vitest run --reporter=verbose`

Expected: all pre-existing tests pass; the 2 new ones from Tasks 1-2 also pass.

- [ ] **Step 9: Commit**

```bash
git status --short
git stash push -u -m "subC-task3-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SettingsPanel.tsx src/components/SpeakerProfile.tsx \
  src/components/SpeakersView.tsx src/hooks/useContexts.ts \
  src/hooks/useSpeakers.ts
git add src/utils/api.ts src/hooks/usePollingJob.js src/hooks/useTranscription.ts \
        src/hooks/useProcessingState.js src/hooks/useJobAutoRefinePolling.ts
git commit -m "feat(ui): plumb job.phase from /job/{id} through hooks"
git stash pop
```

---

## Task 4: Rewrite `SettingsPanel` — Quality dial + drop engine surface

**Files:**
- Modify: `src/components/SettingsPanel.tsx` (heavy edit)

This is the biggest task. Read the current file end-to-end first (`src/components/SettingsPanel.tsx` is ~736 lines).

**What stays in `SettingsPanel`:**
- Output Mode toggle (Verbatim/Readable) — lines ~296-326
- Language selector — lines ~390-427
- Translate-to-English toggle — lines ~430-449
- Speaker Diarization toggle — lines ~452-482 (drop the `isVoxtralApi` "Built-in" branch; just keep the toggle button branch)
- Number of Speakers — lines ~485-506 (drop the `!isVoxtralApi` guard; just `enableDiarization` gates it)
- Context Document selector — lines ~509-532
- Expected Speakers combobox — lines ~534-643
- Noise Reduction toggle (move out of Advanced into the main Settings Grid since Speed/Two-Pass/Word-Timestamps are gone) — currently in Advanced ~lines 727-743

**What is REMOVED in this task:**
- Engine selector row (3 buttons: Voxtral Local / Whisper / Cloud) — lines ~225-273
- Engine capability disclosure block — lines ~275-293
- Model Size selector inside Settings Grid — lines ~330-387
- Advanced `<details>` block in its entirety — lines ~647-770 (Context Terms, Two-Pass, Word Timestamps, Speed Priority all go; Noise Reduction migrates to the main grid). The whole `<details>` element is removed.
- `voxtralAvailable` and `voxtralLocalAvailable` props
- `isVoxtralApi`, `isVoxtralLocal`, `isWhisper`, `isParakeet`, `parakeetLanguageInvalid`, `currentModelInfo`, `isLanguageSupported`, `supportedLabel`, `PARAKEET_KEYS` constants/derived values
- The `useEffect` that resets `twoPass` when engine flips (lines ~172-176)
- Imports: `Cloud`, `Cpu`, `Clock`, `Layers`, `Volume2`, `VolumeX` from lucide-react (Noise Reduction keeps `Volume2`/`VolumeX`, so re-add those), and `MODEL_SIZES`, `VOXTRAL_MODELS`, `VOXTRAL_LOCAL_MODELS` from `../utils/api`

- [ ] **Step 1: Inspect current SettingsPanel WIP**

Run: `git diff src/components/SettingsPanel.tsx`

If the WIP diff touches lines you're keeping (Language, diarization, expected speakers), preserve those edits. If it touches lines you're deleting (engine selector, model dropdown, capability disclosure, Word Timestamps gating), discard the WIP for those lines.

Decision rule: if every WIP hunk is in soon-to-be-deleted code, stash and discard:

```bash
git stash push -m "subC-settings-wip-pre-rewrite" -- src/components/SettingsPanel.tsx
```

Reapply only what you want to keep at the end (you can `git stash show -p stash@{0}` to peek, then cherry-pick lines back).

- [ ] **Step 2: Rewrite `src/components/SettingsPanel.tsx`**

Replace the whole file content. The new file is ~370 lines (down from ~736).

```tsx
import React, { useEffect, useMemo, useState } from 'react';
import { FileAudio, Languages, Globe, Users, Volume2, VolumeX, FolderOpen, BookOpen } from 'lucide-react';
import { LANGUAGES, fetchContextTree, ContextTree, fetchSpeakers, createSpeaker, Speaker } from '../utils/api';
import QualityDial, { QualityMode } from './QualityDial';

interface Settings {
  language?: string;
  translateToEnglish?: boolean;
  enableDiarization?: boolean;
  numSpeakers?: string;
  enableNoiseReduction?: boolean;
  engine?: QualityMode;          // 'auto-best' | 'auto-quick'
  contextPath?: string;          // path under CONTEXTS_DIR to a .md file or folder
  speakerIds?: string[];         // expected speakers — their personality.md feeds the prompt
  outputMode?: string;
  [key: string]: any;
}

interface SettingsPanelProps {
  settings: Settings;
  onSettingsChange?: (settings: Settings) => void;
  showForDocuments?: boolean;
  disabled?: boolean;
}

function SettingsPanel({
  settings,
  onSettingsChange,
  showForDocuments = false,
  disabled = false,
}: SettingsPanelProps) {
  const {
    language = 'auto',
    translateToEnglish = false,
    enableDiarization = true,
    numSpeakers = '',
    enableNoiseReduction = false,
    engine = 'auto-best',
    contextPath = '',
    speakerIds = [] as string[],
    outputMode = 'verbatim',
  } = settings;

  const handleChange = (key: string, value: any) => {
    onSettingsChange?.({ ...settings, [key]: value });
  };

  // Lazily fetch the context tree so the dropdown can offer available
  // context folders / files. Errors are silent — the dropdown just stays
  // empty and the user can still submit without a context.
  const [contextOptions, setContextOptions] = useState<{ path: string; label: string }[]>([]);
  useEffect(() => {
    let cancelled = false;
    fetchContextTree()
      .then((tree) => {
        if (cancelled) return;
        const flat: { path: string; label: string }[] = [];
        const walk = (node: ContextTree, depth = 0) => {
          if (node.path) {
            flat.push({ path: node.path, label: `${'· '.repeat(depth - 1)}${node.name}`.trim() });
          }
          (node.children || []).forEach((child) => walk(child, depth + 1));
        };
        tree.forEach((n) => walk(n, 1));
        setContextOptions(flat);
      })
      .catch(() => { /* ignore; dropdown stays empty */ });
    return () => { cancelled = true; };
  }, []);

  // Pull the list of registered speakers once so the "Expected speakers" picker
  // can show who's available to attach pre-transcription context from.
  const [speakersAvailable, setSpeakersAvailable] = useState<Speaker[]>([]);
  useEffect(() => {
    let cancelled = false;
    fetchSpeakers()
      .then((list) => { if (!cancelled) setSpeakersAvailable(list); })
      .catch(() => { /* silent — picker just stays empty */ });
    return () => { cancelled = true; };
  }, []);

  // Expected-speakers combobox state.
  const [speakerSearch, setSpeakerSearch] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [speakerCreating, setSpeakerCreating] = useState(false);
  const [speakerCreateError, setSpeakerCreateError] = useState<string | null>(null);

  // Integer num_speakers gates the picker.
  const parsedNumSpeakers = useMemo(() => {
    if (numSpeakers === '' || numSpeakers === 'auto') return null;
    const n = parseInt(String(numSpeakers), 10);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [numSpeakers]);

  const pickedSpeakers = useMemo(
    () => speakersAvailable.filter((s) => speakerIds.includes(s.speaker_id)),
    [speakersAvailable, speakerIds]
  );

  const filteredCandidates = useMemo(() => {
    const q = speakerSearch.trim().toLowerCase();
    return speakersAvailable
      .filter((s) => !speakerIds.includes(s.speaker_id))
      .filter((s) => !q || s.name.toLowerCase().includes(q));
  }, [speakersAvailable, speakerIds, speakerSearch]);

  const capReached = parsedNumSpeakers !== null && speakerIds.length >= parsedNumSpeakers;

  const exactMatch = speakersAvailable.find(
    (s) => s.name.toLowerCase() === speakerSearch.trim().toLowerCase()
  );
  const canInlineCreate = speakerSearch.trim().length > 0 && !exactMatch && !capReached;

  const pickExisting = (s: Speaker) => {
    if (capReached) return;
    handleChange('speakerIds', [...speakerIds, s.speaker_id]);
    setSpeakerSearch('');
    setMenuOpen(false);
  };

  const removePick = (id: string) => {
    handleChange('speakerIds', speakerIds.filter((sid) => sid !== id));
  };

  const createAndPick = async () => {
    const name = speakerSearch.trim();
    if (!name || capReached || speakerCreating) return;
    setSpeakerCreating(true);
    setSpeakerCreateError(null);
    try {
      const created = await createSpeaker(name);
      const list = await fetchSpeakers();
      setSpeakersAvailable(list);
      handleChange('speakerIds', [...speakerIds, created.speaker_id]);
      setSpeakerSearch('');
      setMenuOpen(false);
    } catch (e: any) {
      setSpeakerCreateError(e?.message || 'Could not create speaker');
    } finally {
      setSpeakerCreating(false);
    }
  };

  // For document processing, only show relevant settings
  if (showForDocuments) {
    return (
      <div className="mt-6 p-4 bg-slate-100 dark:bg-slate-700/30 rounded-xl">
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
          Document processing will extract text, images, and visual content.
        </p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Charts and diagrams will be analyzed using GLM-4.6V vision model.
        </p>
      </div>
    );
  }

  const safeEngine: QualityMode = engine === 'auto-quick' ? 'auto-quick' : 'auto-best';

  return (
    <div className="mt-6 space-y-4">
      {/* Quality Dial — replaces engine selector + model dropdown */}
      <QualityDial
        value={safeEngine}
        onChange={(next) => handleChange('engine', next)}
        disabled={disabled}
      />

      {/* Output Mode Toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => handleChange('outputMode', 'verbatim')}
          disabled={disabled}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all disabled:opacity-50 ${
            outputMode === 'verbatim'
              ? 'bg-blue-500 text-white'
              : 'bg-slate-200 text-slate-600 border border-slate-300 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:border-slate-600 dark:hover:bg-slate-600'
          }`}
        >
          <FileAudio className="w-4 h-4" />
          Verbatim
        </button>
        <button
          onClick={() => handleChange('outputMode', 'readable')}
          disabled={disabled}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all disabled:opacity-50 ${
            outputMode === 'readable'
              ? 'bg-teal-500 text-white'
              : 'bg-slate-200 text-slate-600 border border-slate-300 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:border-slate-600 dark:hover:bg-slate-600'
          }`}
        >
          <BookOpen className="w-4 h-4" />
          Readable
        </button>
      </div>
      {outputMode === 'readable' && (
        <p className="text-xs text-slate-500 dark:text-slate-400 -mt-2">
          Removes filler words, adds sentence breaks and paragraphs, formats numbers and currency.
        </p>
      )}

      {/* Settings Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Language Selection */}
        <div>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
            <Languages className="w-4 h-4" />
            Language
          </label>
          <select
            value={language}
            onChange={(e) => {
              const newLang = e.target.value;
              const updates: Settings = { language: newLang };
              if (newLang === 'en') {
                updates.translateToEnglish = false;
              }
              onSettingsChange?.({ ...settings, ...updates });
            }}
            disabled={disabled}
            className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg text-slate-900 dark:bg-slate-700 dark:border-slate-600 dark:text-white focus:outline-none focus:border-blue-400 disabled:opacity-50"
          >
            {Object.entries(LANGUAGES).map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        </div>

        {/* Translate to English Toggle */}
        {language !== 'en' && (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
              <Globe className="w-4 h-4" />
              Translate to English
            </label>
            <button
              onClick={() => handleChange('translateToEnglish', !translateToEnglish)}
              disabled={disabled}
              className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 ${
                translateToEnglish
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-200 text-slate-600 border border-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:border-slate-600'
              }`}
            >
              <Globe className="w-4 h-4" />
              {translateToEnglish ? 'Yes - Output in English' : 'No - Keep Original'}
            </button>
          </div>
        )}

        {/* Speaker Diarization */}
        <div>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
            <Users className="w-4 h-4" />
            Speaker Recognition
          </label>
          <button
            onClick={() => handleChange('enableDiarization', !enableDiarization)}
            disabled={disabled}
            className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 ${
              enableDiarization
                ? 'bg-blue-500 text-white'
                : 'bg-slate-200 text-slate-600 border border-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:border-slate-600'
            }`}
          >
            <Users className="w-4 h-4" />
            {enableDiarization ? 'Enabled' : 'Disabled'}
          </button>
        </div>

        {/* Number of Speakers — gated on diarization being on */}
        {enableDiarization && (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
              <Users className="w-4 h-4" />
              Number of Speakers
            </label>
            <select
              value={numSpeakers}
              onChange={(e) => handleChange('numSpeakers', e.target.value)}
              disabled={disabled}
              className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg text-slate-900 dark:bg-slate-700 dark:border-slate-600 dark:text-white focus:outline-none focus:border-blue-400 disabled:opacity-50"
            >
              <option value="">Auto-detect</option>
              <option value="1">1 speaker</option>
              <option value="2">2 speakers</option>
              <option value="3">3 speakers</option>
              <option value="4">4 speakers</option>
              <option value="5">5 speakers</option>
              <option value="6">6+ speakers</option>
            </select>
          </div>
        )}

        {/* Context Document */}
        <div>
          <label
            htmlFor="context-path-select"
            className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2"
          >
            <FolderOpen className="w-4 h-4" aria-hidden="true" />
            Context
          </label>
          <select
            id="context-path-select"
            value={contextPath}
            onChange={(e) => handleChange('contextPath', e.target.value)}
            disabled={disabled}
            className="w-full px-4 py-3 bg-white border border-slate-300 rounded-lg text-slate-900 dark:bg-slate-700 dark:border-slate-600 dark:text-white focus:outline-none focus:border-violet-400 disabled:opacity-50"
          >
            <option value="">None — no context document</option>
            {contextOptions.map((c) => (
              <option key={c.path} value={c.path}>{c.label || c.path}</option>
            ))}
          </select>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Attach a context document (glossary, acronyms, background) from your Contexts library to bias transcription. Optional.
          </p>
        </div>

        {/* Noise Reduction (migrated out of removed Advanced block) */}
        <div>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
            {enableNoiseReduction ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            Noise Reduction
          </label>
          <button
            onClick={() => handleChange('enableNoiseReduction', !enableNoiseReduction)}
            disabled={disabled}
            className={`w-full px-4 py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 disabled:opacity-50 ${
              enableNoiseReduction
                ? 'bg-blue-500 text-white'
                : 'bg-slate-200 text-slate-600 border border-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:border-slate-600'
            }`}
          >
            {enableNoiseReduction ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            {enableNoiseReduction ? 'Enabled' : 'Disabled'}
          </button>
        </div>

        {/* Expected Speakers — searchable combobox with inline-create.
            Only surfaces when diarization is on AND the user set an explicit
            speaker count (so we can cap picks). Each pick seeds the decoder's
            initial_prompt with the speaker's personality.md, AND narrows the
            post-transcription voice auto-match scope. */}
        {enableDiarization && (
          <div>
            <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
              <Users className="w-4 h-4" aria-hidden="true" />
              Expected Speakers
              {parsedNumSpeakers !== null && (
                <span className="text-xs text-slate-400 font-normal">
                  ({speakerIds.length}/{parsedNumSpeakers})
                </span>
              )}
            </label>

            {parsedNumSpeakers === null ? (
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Pick a specific speaker count above to enable pre-selection.
                Voice auto-match will run against your full speaker registry.
              </p>
            ) : (
              <>
                {/* Picked chips */}
                {pickedSpeakers.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2">
                    {pickedSpeakers.map((s) => (
                      <span
                        key={s.speaker_id}
                        className="inline-flex items-center gap-1 pl-3 pr-1 py-1 rounded-full text-xs font-medium bg-violet-500 text-white"
                      >
                        {s.name}
                        <button
                          type="button"
                          onClick={() => removePick(s.speaker_id)}
                          aria-label={`Remove ${s.name} from expected speakers`}
                          className="w-5 h-5 flex items-center justify-center rounded-full hover:bg-violet-600"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}

                {/* Search + menu */}
                <div className="relative">
                  <input
                    type="text"
                    value={speakerSearch}
                    onChange={(e) => { setSpeakerSearch(e.target.value); setMenuOpen(true); }}
                    onFocus={() => setMenuOpen(true)}
                    onBlur={() => setTimeout(() => setMenuOpen(false), 150)}
                    disabled={disabled || capReached}
                    placeholder={capReached ? 'Cap reached — remove one to pick another' : 'Search or type a new speaker name…'}
                    aria-label="Search expected speakers"
                    className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm text-slate-900 dark:bg-slate-700 dark:border-slate-600 dark:text-white placeholder-slate-400 focus:outline-none focus:border-violet-400 disabled:opacity-50"
                  />
                  {menuOpen && !capReached && (filteredCandidates.length > 0 || canInlineCreate) && (
                    <div className="absolute z-20 left-0 right-0 mt-1 max-h-60 overflow-auto rounded-lg bg-white border border-slate-200 dark:bg-slate-700 dark:border-slate-600 shadow-lg">
                      {filteredCandidates.map((s) => (
                        <button
                          key={s.speaker_id}
                          type="button"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => pickExisting(s)}
                          className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-600"
                        >
                          <span className="truncate">{s.name}</span>
                          <span
                            className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                              s.embedding_path
                                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                                : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                            }`}
                            title={s.embedding_path ? 'Has a voice sample — will auto-match' : 'No voice sample yet — will be learned from this recording'}
                          >
                            {s.embedding_path ? '✓ voice' : '⚠ no voice'}
                          </span>
                        </button>
                      ))}
                      {canInlineCreate && (
                        <button
                          type="button"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={createAndPick}
                          disabled={speakerCreating}
                          className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm border-t border-slate-200 dark:border-slate-600 text-blue-600 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 disabled:opacity-60"
                        >
                          ＋ Create new speaker:&nbsp;<span className="font-medium">{speakerSearch.trim()}</span>
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {speakerCreateError && (
                  <p role="alert" className="text-xs text-red-500 mt-1">{speakerCreateError}</p>
                )}
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                  Picks bias the transcription prompt AND narrow post-transcription voice auto-match.
                  {speakerIds.length === parsedNumSpeakers
                    ? ' Auto-match will be scoped to just these picks.'
                    : ' Partial picks: auto-match runs against the full registry with these as tiebreaker.'}
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default React.memo(SettingsPanel);
```

- [ ] **Step 3: TypeScript check**

Run: `npx tsc --noEmit`

Expected: no errors from `SettingsPanel.tsx`. You may see errors in `App.tsx` about extra props being passed (`voxtralAvailable`, `voxtralLocalAvailable`) — those are fixed in Task 5.

- [ ] **Step 4: Run existing component tests**

Run: `npx vitest run --reporter=verbose`

Expected: all pass. (No component test exists for SettingsPanel itself; Tasks 1-2 cover the new components.)

- [ ] **Step 5: Manual smoke (skip if pure CI run)**

Start dev server: `npm run dev` → open `http://localhost:3000` → confirm Quality dial renders with Best selected, click Quick → it highlights. (Do NOT submit — the backend doesn't accept `auto-best` yet unless Sub-plan A also landed. This is a render-only smoke.)

- [ ] **Step 6: Commit**

```bash
git status --short
git stash push -u -m "subC-task4-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts src/utils/api.ts \
  src/App.tsx
git add src/components/SettingsPanel.tsx
git commit -m "feat(ui): replace SettingsPanel engine selector with Quality dial"
git stash pop
```

---

## Task 5: Update `App.tsx` — default `auto-best`, drop engine props, pass `phase` to ProgressBar

**Files:**
- Modify: `src/App.tsx`

- [ ] **Step 1: Change the default `settings` state**

In `src/App.tsx` around line 75-90, change:

```tsx
const [settings, setSettings] = useState<Record<string, any>>({
  modelSize: 'voxtral-mini-3b',
  language: 'auto',
  translateToEnglish: false,
  enableDiarization: true,
  numSpeakers: '',
  wordTimestamps: false,
  enableNoiseReduction: false,
  speedPriority: false,
  engine: 'voxtral-local',
  contextTerms: '',
  contextPath: '',
  speakerIds: [] as string[],
  twoPass: false,
  outputMode: 'verbatim',
});
```

to:

```tsx
const [settings, setSettings] = useState<Record<string, any>>({
  language: 'auto',
  translateToEnglish: false,
  enableDiarization: true,
  numSpeakers: '',
  enableNoiseReduction: false,
  engine: 'auto-best',
  contextPath: '',
  speakerIds: [] as string[],
  outputMode: 'verbatim',
});
```

(Removed keys: `modelSize`, `wordTimestamps`, `speedPriority`, `contextTerms`, `twoPass`. Plan 4 D will drop the corresponding `TranscriptionOptions` fields entirely.)

- [ ] **Step 2: Drop the engine/model fallback overwrite branches**

Find this block (around lines 145-160):

```tsx
useEffect(() => {
  detectProxy().then(async (proxyData) => {
    if (proxyData) {
      if (proxyData.mac_state === 'awake' && proxyData.model_loaded) {
        const fallback = await refreshEngines();
        if (fallback) setSettings(prev => ({ ...prev, ...fallback }));
      } else {
        setSettings(prev => ({ ...prev, engine: 'whisper', modelSize: 'large-v3-turbo' }));
      }
    } else {
      const fallback = await refreshEngines();
      if (fallback) setSettings(prev => ({ ...prev, ...fallback }));
    }
  });
}, [detectProxy, refreshEngines]);
```

Replace with a no-op for engine fallback (the dial owns `engine`; the wake-proxy detection no longer mutates it). Keep the `detectProxy` call because it's also used to drive `macState` inside `useWakeOnLan`, but don't apply any `engine`/`modelSize` overwrites:

```tsx
useEffect(() => {
  detectProxy().then(async (proxyData) => {
    // Wake-proxy detection still drives macState inside useWakeOnLan.
    // We no longer overwrite settings.engine — the Quality dial owns it.
    // refreshEngines() still pings the backend to populate
    // voxtralAvailable/voxtralLocalAvailable for the (soon-to-be-deleted)
    // useEngineAvailability hook. Sub-plan D removes the hook entirely.
    if (!proxyData || (proxyData.mac_state === 'awake' && proxyData.model_loaded)) {
      await refreshEngines();
    }
  });
}, [detectProxy, refreshEngines]);
```

And the `onAwake` handler in `useWakeOnLan` (around line 108):

```tsx
const { macState, setMacState, wakeStartTime, detectProxy, triggerWake, queueSubmit, hasPendingSubmit } =
  useWakeOnLan({
    onAwake: async () => {
      await refreshEngines();
    },
  });
```

(Dropped the `setSettings(prev => ({ ...prev, ...fallback }))` line — fallback no longer applies to engine.)

- [ ] **Step 3: Drop engine props from `<SettingsPanel>`**

Find (around line 421):

```tsx
<SettingsPanel
  settings={settings}
  onSettingsChange={setSettings}
  showForDocuments={isDocumentMode}
  disabled={active.isProcessing}
  voxtralAvailable={voxtralAvailable}
  voxtralLocalAvailable={voxtralLocalAvailable}
/>
```

Change to:

```tsx
<SettingsPanel
  settings={settings}
  onSettingsChange={setSettings}
  showForDocuments={isDocumentMode}
  disabled={active.isProcessing}
/>
```

- [ ] **Step 4: Drop removed-options keys from the submission `options` object**

In `startProcessing` (around line 221-236), change:

```tsx
const options = {
  language: settings.language,
  enableDiarization: settings.enableDiarization,
  enableNoiseReduction: settings.enableNoiseReduction,
  modelSize: settings.modelSize,
  wordTimestamps: settings.wordTimestamps,
  numSpeakers: settings.numSpeakers,
  translateToEnglish: settings.translateToEnglish,
  speedPriority: settings.speedPriority,
  engine: settings.engine,
  contextTerms: settings.contextTerms,
  contextPath: settings.contextPath,
  speakerIds: settings.speakerIds,
  twoPass: settings.twoPass,
  outputMode: settings.outputMode,
};
```

to:

```tsx
const options = {
  language: settings.language,
  enableDiarization: settings.enableDiarization,
  enableNoiseReduction: settings.enableNoiseReduction,
  numSpeakers: settings.numSpeakers,
  translateToEnglish: settings.translateToEnglish,
  engine: settings.engine,
  contextPath: settings.contextPath,
  speakerIds: settings.speakerIds,
  outputMode: settings.outputMode,
};
```

- [ ] **Step 5: Pass `phase` to `<ProgressBar>`**

Find the existing usage (around line 487):

```tsx
<ProgressBar
  progress={active.progress}
  progressMessage={active.progressMessage}
  sourceType={sourceType}
  batchProgress={transcription.batchProgress}
/>
```

Change to:

```tsx
<ProgressBar
  progress={active.progress}
  progressMessage={active.progressMessage}
  sourceType={sourceType}
  batchProgress={transcription.batchProgress}
  phase={active.phase}
/>
```

- [ ] **Step 6: TypeScript check**

Run: `npx tsc --noEmit`

Expected: no new errors. The `phase` prop on `<ProgressBar>` will be flagged until Task 6 adds it to the prop interface — that's fine; commit Tasks 5 and 6 separately, and verify TS passes after Task 6.

If TS complains about an unused import of `useEngineAvailability` or unused `voxtralAvailable`/`voxtralLocalAvailable`/`fallbackNotice`/`dismissFallbackNotice`/`refreshEngines` destructures, **keep them** — Sub-plan D removes them. They're not errors, just lints (and the project's lint config may not fail on unused vars).

- [ ] **Step 7: Commit**

```bash
git status --short
git stash push -u -m "subC-task5-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts src/utils/api.ts
git add src/App.tsx
git commit -m "feat(ui): App.tsx defaults to engine=auto-best + passes phase to ProgressBar"
git stash pop
```

---

## Task 6: Render `PhasePill` inside `ProgressBar`

**Files:**
- Modify: `src/components/ProgressBar.tsx`

- [ ] **Step 1: Edit `src/components/ProgressBar.tsx`**

Add `phase` to the props interface, import `PhasePill`, render the pill above the existing `<Loader2>` + message row.

Replace the whole component body (file is ~93 lines — full rewrite below for clarity):

```tsx
import React from 'react';
import { Loader2 } from 'lucide-react';
import PhasePill from './PhasePill';

interface BatchJob {
  job_id: string;
  progress: number;
  status: string;
}

interface ProgressBarProps {
  progress: number;
  progressMessage?: string;
  batchProgress?: BatchJob[];
  sourceType?: string;
  phase?: string | null;
}

function ProgressBar({
  progress,
  progressMessage,
  batchProgress = [],
  sourceType = 'audio',
  phase = null,
}: ProgressBarProps) {
  const getMessage = () => {
    if (progressMessage) return progressMessage;

    if (sourceType === 'pdf' || sourceType === 'pptx' || sourceType === 'docx') {
      if (progress < 20) return 'Extracting text...';
      if (progress < 40) return 'Processing images...';
      if (progress < 70) return 'Analyzing visual content...';
      if (progress < 90) return 'Generating output...';
      return 'Finalizing...';
    }

    return 'Processing your audio...';
  };

  return (
    <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-6 mb-8 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none">
      {phase && (
        <div className="mb-3">
          <PhasePill phase={phase} />
        </div>
      )}
      <div className="flex items-center gap-3 mb-4">
        <Loader2 className="w-5 h-5 animate-spin text-blue-400" aria-hidden="true" />
        <span className="font-medium">{getMessage()}</span>
      </div>
      <div
        className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-3"
        role="progressbar"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Processing progress"
      >
        <div
          className="bg-gradient-to-r from-blue-500 to-purple-500 h-3 rounded-full transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>
      <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
        {sourceType === 'pdf' || sourceType === 'pptx' || sourceType === 'docx'
          ? 'Document processing may take a few moments'
          : 'Quality-focused transcription may take a few minutes'}
      </p>

      {batchProgress.length > 1 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">Individual files:</p>
          {batchProgress.map((job, idx) => (
            <div key={job.job_id} className="flex items-center gap-2">
              <span className="text-xs text-slate-500 dark:text-slate-400 w-6">{idx + 1}.</span>
              <div
                className="flex-1 bg-slate-200 dark:bg-slate-600 rounded-full h-2"
                role="progressbar"
                aria-valuenow={job.progress}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className={`h-2 rounded-full transition-all duration-300 ${
                    job.status === 'completed' ? 'bg-green-500' :
                    job.status === 'failed' ? 'bg-red-500' :
                    'bg-blue-500'
                  }`}
                  style={{ width: `${job.progress}%` }}
                />
              </div>
              <span className="text-xs text-slate-500 dark:text-slate-400 w-12">{job.progress}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default React.memo(ProgressBar);
```

- [ ] **Step 2: TypeScript check**

Run: `npx tsc --noEmit`

Expected: no errors related to `ProgressBar` or `App.tsx`'s use of it.

- [ ] **Step 3: Re-run tests**

Run: `npx vitest run --reporter=verbose`

Expected: all pre-existing tests still pass; PhasePill + QualityDial tests still pass.

- [ ] **Step 4: Commit**

```bash
git status --short
git stash push -u -m "subC-task6-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts src/utils/api.ts
git add src/components/ProgressBar.tsx
git commit -m "feat(ui): ProgressBar renders PhasePill above progress fill"
git stash pop
```

---

## Task 7: Narrow `TranscriptionOptions.engine` and drop dead params from API helpers

**Files:**
- Modify: `src/utils/api.ts`

- [ ] **Step 1: Narrow the `engine` type**

In `src/utils/api.ts`, find `TranscriptionOptions` (around line 103) and change:

```ts
export interface TranscriptionOptions {
  language?: string;
  enableDiarization?: boolean;
  enableNoiseReduction?: boolean;
  modelSize?: string;
  wordTimestamps?: boolean;
  translateToEnglish?: boolean;
  speedPriority?: boolean;
  engine?: string;
  twoPass?: boolean;
  outputMode?: string;
  numSpeakers?: number;
  contextTerms?: string;
  contextPath?: string;
  speakerIds?: string[];
}
```

to:

```ts
export interface TranscriptionOptions {
  language?: string;
  enableDiarization?: boolean;
  enableNoiseReduction?: boolean;
  // Deprecated fields kept until Sub-plan D removes them; no longer sent.
  modelSize?: string;
  wordTimestamps?: boolean;
  speedPriority?: boolean;
  twoPass?: boolean;
  contextTerms?: string;
  // Quality dial mode — backend orchestrator picks the actual engine + model.
  engine?: 'auto-best' | 'auto-quick';
  translateToEnglish?: boolean;
  outputMode?: string;
  numSpeakers?: number;
  contextPath?: string;
  speakerIds?: string[];
}
```

- [ ] **Step 2: Drop dead params from `submitTranscription`**

Find `submitTranscription` (around line 284). Change the `URLSearchParams` block:

```ts
const params = new URLSearchParams({
  language: options.language || 'auto',
  enable_diarization: String(options.enableDiarization ?? true),
  enable_noise_reduction: String(options.enableNoiseReduction ?? false),
  model_size: options.modelSize || 'voxtral-realtime-4b',
  word_timestamps: String(options.wordTimestamps ?? false),
  translate_to_english: String(options.translateToEnglish ?? false),
  speed_priority: String(options.speedPriority ?? false),
  engine: options.engine || 'voxtral-local',
  two_pass: String(options.twoPass ?? false),
  output_mode: options.outputMode || 'verbatim',
});
```

to:

```ts
const params = new URLSearchParams({
  language: options.language || 'auto',
  enable_diarization: String(options.enableDiarization ?? true),
  enable_noise_reduction: String(options.enableNoiseReduction ?? false),
  translate_to_english: String(options.translateToEnglish ?? false),
  engine: options.engine || 'auto-best',
  output_mode: options.outputMode || 'verbatim',
});
```

Then remove the `if (options.contextTerms) { params.append('context_terms', options.contextTerms); }` block immediately below (the loop adding contextTerms / numSpeakers / contextPath / speakerIds). Keep `numSpeakers`, `contextPath`, `speakerIds` blocks — they're still valid:

```ts
if (options.numSpeakers) {
  params.append('num_speakers', String(options.numSpeakers));
}

if (options.contextPath) {
  params.append('context_path', options.contextPath);
}

if (options.speakerIds && options.speakerIds.length > 0) {
  params.append('speaker_ids', options.speakerIds.join(','));
}
```

(Delete only the `if (options.contextTerms)` block.)

- [ ] **Step 3: Drop dead params from `submitYouTubeTranscription`**

Find `submitYouTubeTranscription` (around line 347). Change:

```ts
const params = new URLSearchParams({
  model_size: options.modelSize || 'voxtral-realtime-4b',
  word_timestamps: String(options.wordTimestamps ?? false),
  speed_priority: String(options.speedPriority ?? false),
  engine: options.engine || 'voxtral-local',
  two_pass: String(options.twoPass ?? false),
  output_mode: options.outputMode || 'verbatim',
});
```

to:

```ts
const params = new URLSearchParams({
  engine: options.engine || 'auto-best',
  output_mode: options.outputMode || 'verbatim',
});
```

Delete the `if (options.contextTerms)` block in this function too. Keep `numSpeakers`, `contextPath`, `speakerIds`.

- [ ] **Step 4: Apply the same transformation to `submitBatchTranscription`**

`submitBatchTranscription` confirmed to build its own `URLSearchParams` with the same dead keys. Repeat Step 2's transformation on it: drop `model_size`, `speed_priority`, `two_pass`, `context_terms` (and any `engine`-derived value other than `auto-best`/`auto-quick`); keep `numSpeakers`, `contextPath`, `speakerIds`, `outputMode`.

Sanity-check grep before and after to confirm nothing was missed:

Run: `grep -n "submitBatchTranscription\|model_size\|speed_priority\|two_pass\|context_terms" src/utils/api.ts`

After the edit the only remaining matches should be the function declaration and Sub-plan D-deferred constants (`MODEL_SIZES`, `VOXTRAL_MODELS`).

- [ ] **Step 5: TypeScript check**

Run: `npx tsc --noEmit`

Expected: no errors. The narrowed `engine: 'auto-best' | 'auto-quick'` is now compatible with the Settings/QualityDial flow.

- [ ] **Step 6: Run tests**

Run: `npx vitest run --reporter=verbose`

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git status --short
git stash push -u -m "subC-task7-stash" -- \
  backend/ deploy/ scripts/ Tests/ *.m4a \
  src/components/ContextBrowser.tsx src/components/ErrorBoundary.tsx \
  src/components/SpeakerProfile.tsx src/components/SpeakersView.tsx \
  src/hooks/useContexts.ts src/hooks/useSpeakers.ts
git add src/utils/api.ts
git commit -m "chore(api): narrow TranscriptionOptions.engine to auto-best|auto-quick + drop dead params"
git stash pop
```

---

## Task 8 (verification): End-to-end manual check

This task is verification-only. It assumes Sub-plan A has shipped (backend accepts `auto-best`/`auto-quick`). If A has NOT shipped yet, run only Steps 1-3 (UI render only) and defer Steps 4-7 to the joint deploy window.

- [ ] **Step 1: Start dev server**

Run from repo root: `npm run dev`

Open `http://localhost:3000` in the browser.

- [ ] **Step 2: Verify Quality dial renders correctly**

- Quality dial appears at the top of the SettingsPanel with two buttons (Best, Quick)
- Best is selected by default (highlighted blue)
- Sub-labels "Full pipeline" / "~10 min" under Best
- Sub-labels "Fast preview" / "~30 sec" under Quick
- Click Quick → highlight moves; click Best → highlight moves back
- No engine selector (Voxtral Local / Whisper / Cloud) anywhere
- No model size dropdown anywhere
- No "Advanced options" `<details>` block
- Noise Reduction toggle is visible in the main settings grid (not hidden in Advanced)

- [ ] **Step 3: Verify no console errors**

Open browser devtools console. Confirm no React warnings about missing props, unknown DOM attributes, etc.

- [ ] **Step 4 (gated on Sub-plan A live): Submit a small audio with Best**

- Pick a small test audio (e.g. `Tests/15-29-21.m4a` if present)
- Click Start
- Watch the progress bar — a blue pill should appear above the bar showing "Diarizing…" / "Transcribing…" as the backend reports phases (Sub-plan A drives this)
- Transcript should appear when done

- [ ] **Step 5 (gated on Sub-plan A live): Submit the same audio with Quick**

- Click Quick on the dial
- Submit same audio
- Phases should run much faster; should complete in ~30s
- Phase pill should transition: Diarizing… → Transcribing… → (after the job completes) Refining… → Learning… (this last pair comes from `useJobAutoRefinePolling`'s `phase` field)

- [ ] **Step 6 (gated on Sub-plan A live): Verify the network request**

Open devtools Network tab. Find the `/transcribe/file` POST request. Confirm:
- `engine=auto-best` (or `auto-quick`) in query string
- No `model_size`, `speed_priority`, `two_pass`, `word_timestamps`, `context_terms` params
- `language`, `enable_diarization`, `enable_noise_reduction`, `translate_to_english`, `output_mode` still present
- `num_speakers` / `context_path` / `speaker_ids` present when their inputs are non-empty

- [ ] **Step 7: Done — no commit (verification only)**

If all checks pass, Sub-plan C is complete. No additional commit; the work is already in tree.

---

## Self-Review Checklist (run after writing this plan, before saving final)

- [x] **Spec coverage**:
  - Quality Dial UX section → Task 1 (component) + Task 4 (integration)
  - Phased Progress Bar section → Task 2 (PhasePill) + Task 3 (plumbing) + Task 5/6 (rendering)
  - "What this sub-plan does NOT touch" — explicitly called out in header; Task 7 deliberately leaves `MODEL_SIZES`/`VOXTRAL_*`/`ENGINES` and `useEngineAvailability` alive
  - Phase pill at null → Task 2 test covers it
  - Default Best → Task 5 sets `engine: 'auto-best'`
  - Lockstep with Sub-plan A → header section "Dependency lockstep"
  - 5-7 tasks (we have 7 + 1 verification) — within budget

- [x] **Placeholder scan**: no TBDs, no "add appropriate error handling", every code step has actual code, every command has an expected outcome.

- [x] **Type consistency**:
  - `QualityMode = 'auto-best' | 'auto-quick'` defined in QualityDial, used in SettingsPanel + TranscriptionOptions
  - `PhasePill` accepts `phase?: string | null` matching `ProgressBar`'s prop
  - `useJobAutoRefinePolling` `AutoRefineState.phase: string | null` matches `fetchJobAutoRefineState` return
  - `usePollingJob` exposes `phase: string | null` consumed by `useTranscription` and surfaced via `useProcessingState`'s `active.phase`

- [x] **Stash dance**: every commit step includes the stash dance to protect parallel WIP from Plan 3 + Sub-plan A.
