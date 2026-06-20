# S2 — Shared Speaker-Picker Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two independent expected-speaker combobox implementations (in `SettingsPanel.tsx` and `SpeakerReviewPanel.tsx`) with one deep module — a `useSpeakerCombobox` hook plus a `<SpeakerPicker>` adapter — consumed at both seams.

**Architecture:** Extract the combobox state machine (search, filtered candidates, max-speaker cap, inline create, selection chips) into `src/hooks/useSpeakerCombobox.ts`, and the markup into `src/components/SpeakerPicker.tsx`. Both call sites switch to the shared module. No behaviour or visual change; the existing Playwright e2e for the speaker-review flow is the regression net.

**Tech Stack:** React 18 + TypeScript (strict:false), Playwright e2e, eslint, `tsc --noEmit`.

## Global Constraints

- No frontend unit-test runner exists. Verification = `npx tsc --noEmit` + `npm run lint` + `npx playwright test` (the `speaker-review-panel.spec.ts` covers SpeakerReviewPanel).
- This is a behaviour-preserving refactor. The picker must look and behave identically in both panels.
- Keep the existing API calls (speaker fetch, inline-create) exactly as they are today — only their wiring moves.
- Do not touch `TranscriptView.tsx` (owned by S3) or any backend file. Stay inside `src/components/SettingsPanel.tsx`, `src/components/SpeakerReviewPanel.tsx`, and the two new files.
- `import type` for type-only imports (project uses isolatedModules).

---

### Task 1: Establish the regression baseline

**Files:** none (read-only)

- [ ] **Step 1:** Read both implementations and write down their differences:
  - `SettingsPanel.tsx` expected-speakers picker: state at ~L85–144, markup at ~L365–468.
  - `SpeakerReviewPanel.tsx` `renderUnresolvedRow`: ~L238–300.
  Note every divergence (cap behaviour, chip rendering, inline-create copy, callback shape). The shared module must support BOTH via props — list the prop surface this implies.

- [ ] **Step 2: Run the e2e baseline GREEN before any change**

Run: `npx playwright test e2e/speaker-review-panel.spec.ts`
Expected: PASS. If it fails on a pre-existing issue, STOP and report — do not refactor on a red baseline.

- [ ] **Step 3: Run typecheck + lint baseline**

Run: `npx tsc --noEmit && npm run lint`
Expected: clean (or record pre-existing warnings to diff against later).

---

### Task 2: Extract the `useSpeakerCombobox` hook

**Files:**
- Create: `src/hooks/useSpeakerCombobox.ts`

**Interfaces:**
- Produces:
```ts
export interface SpeakerCandidate { id: string; name: string; /* match real shape */ }
export interface UseSpeakerComboboxArgs {
  candidates: SpeakerCandidate[];
  picked: SpeakerCandidate[];
  cap?: number;                 // max speakers; undefined = no cap
  onPick: (c: SpeakerCandidate) => void;
  onRemove: (id: string) => void;
  onCreate: (name: string) => Promise<SpeakerCandidate>;
}
export interface UseSpeakerCombobox {
  search: string; setSearch: (s: string) => void;
  menuOpen: boolean; setMenuOpen: (b: boolean) => void;
  filtered: SpeakerCandidate[];
  capReached: boolean;
  exactMatch: boolean;
  canInlineCreate: boolean;
  creating: boolean; createError: string | null;
  pickExisting: (c: SpeakerCandidate) => void;
  removePick: (id: string) => void;
  createAndPick: () => Promise<void>;
}
export function useSpeakerCombobox(args: UseSpeakerComboboxArgs): UseSpeakerCombobox;
```

- [ ] **Step 1:** Move the `useState`/`useMemo`/handlers from `SettingsPanel.tsx` (L85–144) into `useSpeakerCombobox.ts`, parameterising the divergences found in Task 1 via the args above. The hook owns NO data fetching — candidates and the create callback are injected.

- [ ] **Step 2: Typecheck the new hook in isolation**

Run: `npx tsc --noEmit`
Expected: clean (hook compiles; not yet consumed).

- [ ] **Step 3: Commit**

```bash
git add src/hooks/useSpeakerCombobox.ts
git commit -m "feat(speakers): extract useSpeakerCombobox state machine"
```

---

### Task 3: Build the `<SpeakerPicker>` presentation adapter

**Files:**
- Create: `src/components/SpeakerPicker.tsx`

**Interfaces:**
- Consumes: `useSpeakerCombobox`.
- Produces:
```ts
export interface SpeakerPickerProps extends UseSpeakerComboboxArgs {
  placeholder?: string;
  label?: string;
}
export function SpeakerPicker(props: SpeakerPickerProps): JSX.Element;
```

- [ ] **Step 1:** Build `SpeakerPicker.tsx` from the richer of the two markups (SettingsPanel's L365–468). It calls `useSpeakerCombobox(props)` and renders input + dropdown + chips. Keep class names / Tailwind identical to current markup so the visual is unchanged.

- [ ] **Step 2: Typecheck + lint**

Run: `npx tsc --noEmit && npm run lint`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add src/components/SpeakerPicker.tsx
git commit -m "feat(speakers): add SpeakerPicker adapter over useSpeakerCombobox"
```

---

### Task 4: Adopt `<SpeakerPicker>` in SettingsPanel

**Files:**
- Modify: `src/components/SettingsPanel.tsx`

- [ ] **Step 1:** Replace the inline picker block (state L85–144 + markup L365–468) with a single `<SpeakerPicker .../>`, wiring its props to SettingsPanel's existing candidate list, picked list, cap (`parsedNumSpeakers`), and the existing inline-create call. Delete the now-dead local state/handlers.

- [ ] **Step 2: Typecheck + lint**

Run: `npx tsc --noEmit && npm run lint`
Expected: clean. Confirm the file shrank (the ~80 picker lines are gone).

- [ ] **Step 3: Commit**

```bash
git add src/components/SettingsPanel.tsx
git commit -m "refactor(settings): use shared SpeakerPicker for expected speakers"
```

---

### Task 5: Adopt `<SpeakerPicker>` in SpeakerReviewPanel

**Files:**
- Modify: `src/components/SpeakerReviewPanel.tsx`

- [ ] **Step 1:** Replace `renderUnresolvedRow` (L238–300) combobox internals with `<SpeakerPicker .../>`, wiring to the panel's per-label candidate list and its inline-create path. Preserve the row layout around the picker (the surrounding row is not part of the shared module).

- [ ] **Step 2: Typecheck + lint**

Run: `npx tsc --noEmit && npm run lint`
Expected: clean.

- [ ] **Step 3: Run the e2e regression (the key gate)**

Run: `npx playwright test e2e/speaker-review-panel.spec.ts`
Expected: PASS — identical behaviour to the Task 1 baseline.

- [ ] **Step 4: Commit**

```bash
git add src/components/SpeakerReviewPanel.tsx
git commit -m "refactor(speaker-review): use shared SpeakerPicker for unresolved rows"
```

---

### Task 6: Verification & finish

- [ ] **Step 1:** Full frontend gate:

Run: `npx tsc --noEmit && npm run lint && npm run build && npx playwright test`
Expected: all clean / PASS. Capture the Playwright summary as completion evidence.

- [ ] **Step 2:** Confirm the duplication is gone:

Run: `grep -rn "filteredCandidates\|capReached\|createAndPick" src/components/SettingsPanel.tsx src/components/SpeakerReviewPanel.tsx`
Expected: no matches in the panels — that logic now lives only in `useSpeakerCombobox.ts`.

- [ ] **Step 3:** REQUIRED SUB-SKILL: Use superpowers:verification-before-completion, then superpowers:finishing-a-development-branch to open/merge the PR.

## Self-Review notes for the implementer
- If the two panels diverge in a way a single prop surface can't express cleanly, prefer two thin wrapper components over branching inside the hook — but keep ONE state machine.
- The e2e in Task 5 is the real acceptance gate; do not declare done without it green.
