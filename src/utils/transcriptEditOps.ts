// Pure, side-effect-free transcript edit operations.
//
// These algorithms were lifted verbatim out of TranscriptView.tsx so they can
// be unit-tested in isolation and reused by the editing/search hooks. The
// semantics (char-proportional split timestamps, the "rough" change count used
// by the save-confirm modal, case-insensitive search/replace) are preserved
// exactly — production behaviour wins over any tidier alternative.

// Local mirror of the transcript Segment shape. The canonical type lives in
// utils/api (`Segment`), where `speaker`/`paragraph_break` are optional; this
// module only depends on the editable fields and keeps `speaker` optional to
// stay compatible.
export interface Segment {
  start: number;
  end: number;
  text: string;
  speaker?: string;
  paragraph_break?: boolean;
  // Transient marker for the amber ring on a freshly-split second half;
  // stripped before the PUT.
  _justSplit?: boolean;
}

// Escape special regex characters to prevent ReDoS.
export const escapeRegExp = (s: string): string =>
  s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Split a segment at the given cursor index. Timestamps are char-proportional —
// exact enough for insight extraction and the user can still eyeball-adjust
// after the fact. The caller is responsible for rejecting edge positions
// (0 or >= text length) before calling; this is the pure proportioning core.
export function splitSegment(seg: Segment, cursorIndex: number): [Segment, Segment] {
  const text = seg.text || '';
  const pos = cursorIndex;
  const duration = Math.max(0, (seg.end ?? 0) - (seg.start ?? 0));
  const midpoint = (seg.start ?? 0) + duration * (pos / text.length);
  const partA: Segment = {
    ...seg,
    text: text.slice(0, pos).trimEnd(),
    end: midpoint,
  };
  const partB: Segment = {
    ...seg,
    text: text.slice(pos).trimStart(),
    start: midpoint,
    // Transient marker for the amber ring; stripped before the PUT.
    _justSplit: true,
  };
  return [partA, partB];
}

// Rough change count between original and draft segments — enough to nudge the
// user in the confirm modal but doesn't need to be perfectly precise. Mirrors
// the `changeCount` logic in the former saveEdits().
export function countChanges(original: Segment[], draft: Segment[]): number {
  const lengthChanged = draft.length !== original.length;
  return lengthChanged
    ? Math.abs(draft.length - original.length) + draft.filter((s, i) => {
        const o = original[i];
        return o && ((s.text ?? '') !== (o.text ?? '') || (s.speaker ?? '') !== (o.speaker ?? ''));
      }).length
    : draft.reduce((n, s, i) => {
        const o = original[i];
        return n + (!o || (s.text ?? '') !== (o.text ?? '') || (s.speaker ?? '') !== (o.speaker ?? '') ? 1 : 0);
      }, 0);
}

// Return the indices of segments whose text contains the query
// (case-insensitive). A blank/whitespace-only query matches nothing.
export function searchSegments(segments: Segment[], query: string): number[] {
  if (!query.trim()) return [];
  const matches: number[] = [];
  const q = query.toLowerCase();
  segments.forEach((segment, index) => {
    if (segment.text.toLowerCase().includes(q)) {
      matches.push(index);
    }
  });
  return matches;
}

// Replace every occurrence of `query` (case-insensitive) with `replacement`
// across all segments, returning the new segments and the total occurrence
// count. Returns the original segments untouched when there are no matches.
export function replaceAllInSegments(
  segments: Segment[],
  query: string,
  replacement: string,
): { segments: Segment[]; count: number } {
  const regex = new RegExp(escapeRegExp(query), 'gi');
  let count = 0;
  segments.forEach((segment) => {
    const matches = segment.text.match(regex);
    if (matches) count += matches.length;
  });

  if (count === 0) {
    return { segments, count: 0 };
  }

  const next = segments.map((segment) => ({
    ...segment,
    text: segment.text.replace(new RegExp(escapeRegExp(query), 'gi'), replacement),
  }));
  return { segments: next, count };
}

// Replace every occurrence of `query` (case-insensitive) with `replacement`
// inside a single segment's text. Pure helper for the per-segment Replace
// action.
export function replaceInSegmentText(text: string, query: string, replacement: string): string {
  return text.replace(new RegExp(escapeRegExp(query), 'gi'), replacement);
}
