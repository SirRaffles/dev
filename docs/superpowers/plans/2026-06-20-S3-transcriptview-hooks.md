# S3 — Deepen TranscriptView (hooks + pure edit-ops module) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the 770-line `TranscriptView.tsx` god-component into a thin render surface over deep modules: a pure `transcriptEditOps` module (split / diff / change-count), and two hooks (`useTranscriptEditing`, `useTranscriptSearch`). The pure logic gains real unit tests — none exist today.

**Architecture:** Extract the side-effect-free algorithms (segment split, draft-vs-original diff, replace-all counting, highlight) into `src/utils/transcriptEditOps.ts` and unit-test them with vitest (added in Task 1). Then lift the stateful edit and search/replace logic into hooks. `TranscriptView.tsx` keeps rendering and wiring only.

**Tech Stack:** React 18 + TypeScript, **vitest** (added by this plan), Playwright e2e, `tsc --noEmit`, eslint.

## Global Constraints

- No unit-test runner exists yet — Task 1 adds vitest (`vitest` + `@vitest/ui` not required; just `vitest` + `jsdom` if a hook test needs DOM). Pure-module tests need no DOM.
- Behaviour-preserving refactor: the transcript edit/search/replace UX must be identical.
- Do not touch `SettingsPanel.tsx` / `SpeakerReviewPanel.tsx` (owned by S2) or any backend file. Stay inside `TranscriptView.tsx`, the new `src/utils/transcriptEditOps.ts`, new hooks under `src/hooks/`, and test/config files.
- Add a `test` script to `package.json` (`"test": "vitest run"`); do not remove existing scripts.
- `import type` for type-only imports.

---

### Task 1: Add vitest and a smoke test

**Files:**
- Modify: `package.json` (add `vitest` devDep + `"test": "vitest run"` script)
- Modify: `vite.config.js` (add `test` config block) OR create `vitest.config.ts`
- Create: `src/utils/__tests__/smoke.test.ts`

- [ ] **Step 1:** Add vitest:

```bash
npm install -D vitest
```

- [ ] **Step 2:** Add to `package.json` scripts: `"test": "vitest run"`. Add a `test` block to `vite.config.js` (`test: { environment: 'node', include: ['src/**/*.test.ts'] }`).

- [ ] **Step 3: Write a failing smoke test**

```ts
// src/utils/__tests__/smoke.test.ts
import { describe, it, expect } from "vitest";
describe("vitest", () => {
  it("runs", () => { expect(1 + 1).toBe(2); });
});
```

- [ ] **Step 4: Run it**

Run: `npm test`
Expected: PASS (1 test). This proves the runner is wired.

- [ ] **Step 5: Commit**

```bash
git add package.json package-lock.json vite.config.js src/utils/__tests__/smoke.test.ts
git commit -m "chore(test): add vitest runner for pure modules"
```

---

### Task 2: Extract & test the pure `transcriptEditOps` module

**Files:**
- Create: `src/utils/transcriptEditOps.ts`
- Create: `src/utils/__tests__/transcriptEditOps.test.ts`
- Read: `src/components/TranscriptView.tsx` (lift logic from `handleSplitSegment` ~L151–186, the diff in `saveEdits` ~L230–258, `performSearch` ~L293, `replaceInSegment` ~L309, `replaceAll` ~L336, `highlightText` ~L377)

**Interfaces:**
- Produces (match the real `Segment` shape found in TranscriptView):
```ts
export interface Segment { start: number; end: number; speaker: string; text: string; }
export function splitSegment(seg: Segment, cursorIndex: number): [Segment, Segment];
export function countChanges(original: Segment[], draft: Segment[]): number;
export function searchSegments(segments: Segment[], query: string): number[]; // matching indices
export function replaceAllInSegments(segments: Segment[], query: string, replacement: string): { segments: Segment[]; count: number };
```

- [ ] **Step 1: Write failing tests for the pure ops** (real algorithm semantics — read the source to copy the exact split/diff rules):

```ts
// src/utils/__tests__/transcriptEditOps.test.ts
import { describe, it, expect } from "vitest";
import { splitSegment, countChanges, replaceAllInSegments } from "../transcriptEditOps";

const seg = { start: 0, end: 10, speaker: "A", text: "hello world" };

describe("splitSegment", () => {
  it("splits text at the cursor and proportions the timestamp", () => {
    const [a, b] = splitSegment(seg, 5);
    expect(a.text).toBe("hello");
    expect(b.text).toBe(" world");
    expect(a.end).toBe(b.start);
    expect(a.start).toBe(0);
    expect(b.end).toBe(10);
  });
});

describe("countChanges", () => {
  it("counts segments whose text changed", () => {
    const orig = [seg];
    const draft = [{ ...seg, text: "changed" }];
    expect(countChanges(orig, draft)).toBe(1);
  });
});

describe("replaceAllInSegments", () => {
  it("replaces every occurrence and returns the count", () => {
    const { segments, count } = replaceAllInSegments([{ ...seg, text: "a a a" }], "a", "b");
    expect(count).toBe(3);
    expect(segments[0].text).toBe("b b b");
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `transcriptEditOps.ts`** by moving the algorithms out of `TranscriptView.tsx` verbatim (preserve the exact proportioning + diff rules — do not "improve" them).

- [ ] **Step 4: Run to verify it passes**

Run: `npm test`
Expected: PASS. If the real split rule differs from the test's assumption, fix the TEST to match production behaviour (this is characterization).

- [ ] **Step 5: Commit**

```bash
git add src/utils/transcriptEditOps.ts src/utils/__tests__/transcriptEditOps.test.ts
git commit -m "feat(transcript): extract pure transcriptEditOps with unit tests"
```

---

### Task 3: Route TranscriptView through transcriptEditOps

**Files:**
- Modify: `src/components/TranscriptView.tsx`

- [ ] **Step 1:** Replace the inline split/diff/replace/search bodies with calls into `transcriptEditOps`. Keep the surrounding state/handlers for now — only the pure cores move.

- [ ] **Step 2: Typecheck + lint + unit**

Run: `npx tsc --noEmit && npm run lint && npm test`
Expected: clean / PASS.

- [ ] **Step 3: e2e smoke (transcript flow)**

Run: `npx playwright test`
Expected: PASS (no transcript-edit regression).

- [ ] **Step 4: Commit**

```bash
git add src/components/TranscriptView.tsx
git commit -m "refactor(transcript): TranscriptView delegates to transcriptEditOps"
```

---

### Task 4: Extract `useTranscriptSearch` hook

**Files:**
- Create: `src/hooks/useTranscriptSearch.ts`
- Modify: `src/components/TranscriptView.tsx`

**Interfaces:**
- Consumes: `searchSegments`, `replaceAllInSegments` from `transcriptEditOps`.
- Produces:
```ts
export function useTranscriptSearch(segments: Segment[], onApply: (next: Segment[]) => void): {
  query: string; setQuery: (s: string) => void;
  replaceText: string; setReplaceText: (s: string) => void;
  matches: number[];
  replaceInSegment: (index: number) => void;
  replaceAll: () => number;
};
```

- [ ] **Step 1:** Move the search/replace state (TranscriptView ~L88–93) and handlers (~L293–386) into the hook. TranscriptView consumes the hook.

- [ ] **Step 2: Verify**

Run: `npx tsc --noEmit && npm run lint && npm test && npx playwright test`
Expected: clean / PASS.

- [ ] **Step 3: Commit**

```bash
git add src/hooks/useTranscriptSearch.ts src/components/TranscriptView.tsx
git commit -m "refactor(transcript): extract useTranscriptSearch hook"
```

---

### Task 5: Extract `useTranscriptEditing` hook

**Files:**
- Create: `src/hooks/useTranscriptEditing.ts`
- Modify: `src/components/TranscriptView.tsx`

**Interfaces:**
- Consumes: `splitSegment`, `countChanges` from `transcriptEditOps`.
- Produces:
```ts
export function useTranscriptEditing(segments: Segment[], onSave: (next: Segment[]) => Promise<void>): {
  isEditing: boolean; enter: () => void; cancel: () => void;
  draft: Segment[];
  editSegment: (index: number, patch: Partial<Segment>) => void;
  changeSpeaker: (index: number, speaker: string) => void;
  splitAt: (index: number, cursor: number) => void;
  pendingChangeCount: number;
  save: () => Promise<void>;
};
```

- [ ] **Step 1:** Move the ~14 edit-mode `useState` and the edit/split/save handlers (TranscriptView ~L48–93 edit slice, `saveEdits` ~L225–290, `handleSplitSegment`) into the hook. Keep the save-confirmation modal trigger in the component, driven by `pendingChangeCount`.

- [ ] **Step 2: Verify**

Run: `npx tsc --noEmit && npm run lint && npm test && npx playwright test`
Expected: clean / PASS.

- [ ] **Step 3: Commit**

```bash
git add src/hooks/useTranscriptEditing.ts src/components/TranscriptView.tsx
git commit -m "refactor(transcript): extract useTranscriptEditing hook"
```

---

### Task 6: Verification & finish

- [ ] **Step 1:** Confirm the component shrank materially:

Run: `wc -l src/components/TranscriptView.tsx`
Expected: well below 770 (target ~300–400).

- [ ] **Step 2:** Full gate:

Run: `npx tsc --noEmit && npm run lint && npm test && npm run build && npx playwright test`
Expected: all clean / PASS. Capture summaries as completion evidence.

- [ ] **Step 3:** REQUIRED SUB-SKILL: Use superpowers:verification-before-completion, then superpowers:finishing-a-development-branch to open/merge the PR.

## Self-Review notes for the implementer
- Extract pure ops FIRST (Task 2) so the hooks consume a tested core — do not invert the order.
- If the real split/diff semantics surprise you, the production behaviour wins; pin it in a test, don't change it.
- The `useJobFilename` extraction the audit also flagged is optional and out of scope here — keep this plan to edit + search + pure ops.
