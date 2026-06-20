import { useRef, useState } from 'react';
import type { Segment } from '../utils/transcriptEditOps';
import { splitSegment, countChanges } from '../utils/transcriptEditOps';

interface UseTranscriptEditingOptions {
  // The committed source segments the editor drafts from.
  segments: Segment[] | undefined;
  // Persists the cleaned draft to the backend + surfaces it to the parent.
  // Resolves on success; throws on failure (the hook surfaces the message).
  persist: (cleaned: Segment[]) => Promise<void>;
}

export interface UseTranscriptEditing {
  isEditing: boolean;
  isSaving: boolean;
  saveError: string | null;
  splitError: string | null;
  setSplitError: (s: string | null) => void;
  // Edit-mode draft (null outside edit mode).
  draftSegments: Segment[] | null;
  // Per-segment textarea refs so Split can read the caret position.
  segmentTextareaRefs: React.MutableRefObject<Record<number, HTMLTextAreaElement | null>>;
  enterEditMode: () => void;
  exitEditMode: () => void;
  editSegment: (index: number, newText: string) => void;
  changeSegmentSpeaker: (index: number, newSpeaker: string) => void;
  splitAt: (index: number) => void;
  // Rough change count of the current draft vs source (drives confirm modal).
  pendingChangeCount: number;
  // Saves the draft. When `confirmed` is false and the change count warrants a
  // confirmation, returns `{ needsConfirm: true }` without persisting so the
  // caller can open the modal. Otherwise persists and exits edit mode.
  save: (confirmed: boolean) => Promise<{ needsConfirm: boolean }>;
}

export function useTranscriptEditing({
  segments,
  persist,
}: UseTranscriptEditingOptions): UseTranscriptEditing {
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [draftSegments, setDraftSegments] = useState<Segment[] | null>(null);
  const [splitError, setSplitError] = useState<string | null>(null);
  const segmentTextareaRefs = useRef<Record<number, HTMLTextAreaElement | null>>({});

  const original = segments || [];

  const pendingChangeCount = draftSegments
    ? countChanges(original, draftSegments)
    : 0;

  // All edit-mode mutations go through the draft. Outside edit mode the draft
  // is null and the component reads directly from result.segments.
  const editSegment = (index: number, newText: string) => {
    setDraftSegments((prev) =>
      prev ? prev.map((s, j) => (j === index ? { ...s, text: newText } : s)) : prev,
    );
  };

  const changeSegmentSpeaker = (index: number, newSpeaker: string) => {
    setDraftSegments((prev) =>
      prev ? prev.map((s, j) => (j === index ? { ...s, speaker: newSpeaker } : s)) : prev,
    );
  };

  // Split the segment at the current cursor position in its textarea. Reject
  // edge positions (0 or >= text length) so we never produce an empty half.
  const splitAt = (index: number) => {
    setSplitError(null);
    setDraftSegments((prev) => {
      if (!prev) return prev;
      const seg = prev[index];
      if (!seg) return prev;
      const ta = segmentTextareaRefs.current[index];
      if (!ta) {
        setSplitError('Click inside the segment text first, then Split.');
        return prev;
      }
      const pos = ta.selectionStart ?? 0;
      const text = seg.text || '';
      if (pos <= 0 || pos >= text.length) {
        setSplitError('Place the cursor between two words inside this segment before splitting.');
        return prev;
      }
      const [partA, partB] = splitSegment(seg, pos);
      const next = [...prev];
      next.splice(index, 1, partA, partB);
      return next;
    });
  };

  const enterEditMode = () => {
    setDraftSegments((segments || []).map((s) => ({ ...s })));
    setSplitError(null);
    setSaveError(null);
    setIsEditing(true);
  };

  const exitEditMode = () => {
    setDraftSegments(null);
    setSplitError(null);
    setIsEditing(false);
  };

  const save = async (confirmed: boolean): Promise<{ needsConfirm: boolean }> => {
    if (!draftSegments) {
      exitEditMode();
      return { needsConfirm: false };
    }

    // Diff draft vs original to decide whether the save is worth issuing and
    // how many changes we're about to commit (drives the confirm modal).
    const lengthChanged = draftSegments.length !== original.length;
    const alignedChanged = !lengthChanged && draftSegments.some((s, i) => {
      const o = original[i];
      return !o
        || (s.text ?? '') !== (o.text ?? '')
        || (s.speaker ?? '') !== (o.speaker ?? '')
        || Number(s.start) !== Number(o.start)
        || Number(s.end) !== Number(o.end);
    });
    if (!lengthChanged && !alignedChanged) {
      exitEditMode();
      return { needsConfirm: false };
    }

    const changeCount = countChanges(original, draftSegments);
    if (changeCount > 1 && !confirmed) {
      return { needsConfirm: true };
    }

    setIsSaving(true);
    setSaveError(null);
    try {
      // Strip client-only flags before hitting the backend.
      const cleaned = draftSegments.map(({ _justSplit: _js, ...s }) => s as Segment);
      await persist(cleaned);
      exitEditMode();
    } catch (err: any) {
      setSaveError(err.message || 'Failed to save changes');
    } finally {
      setIsSaving(false);
    }
    return { needsConfirm: false };
  };

  return {
    isEditing,
    isSaving,
    saveError,
    splitError,
    setSplitError,
    draftSegments,
    segmentTextareaRefs,
    enterEditMode,
    exitEditMode,
    editSegment,
    changeSegmentSpeaker,
    splitAt,
    pendingChangeCount,
    save,
  };
}
