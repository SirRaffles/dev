import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Clock, Users, Edit2, Save, Edit3, Search, Replace, X, Check, Loader2, UserPlus, Sparkles, Scissors } from 'lucide-react';
import { LANGUAGES, updateSegments, updateSpeakers, Segment, fetchSpeakers, assignJobSpeakers, Speaker, SpeakerAssignmentInput } from '../utils/api';
import { formatTime } from './AudioPlayer';
import ConfirmModal from './ConfirmModal';
import RefinementBadge from './RefinementBadge';
import AutoMatchBadge from './AutoMatchBadge';
import { useJobAutoRefinePolling } from '../hooks/useJobAutoRefinePolling';

// Diarization emits generic labels like SPEAKER_00 / "Speaker 1". Anything
// that matches this shape is still waiting for a real name.
const ANON_SPEAKER_RE = /^(?:SPEAKER_\d+|Speaker\s*\d+|Unknown)$/i;
const isAnonymousLabel = (name: string | null | undefined) =>
  !name ? true : ANON_SPEAKER_RE.test(name.trim());

// Escape special regex characters to prevent ReDoS
const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

interface TranscriptResult {
  language?: string;
  language_probability?: number;
  speakers?: string[];
  segments?: Segment[];
  result?: string;
  source?: string;            // "youtube_captions" | undefined
  is_generated?: boolean;     // true for YouTube auto-generated captions
}

interface TranscriptViewProps {
  result: TranscriptResult;
  jobId: string;
  onResultUpdate?: (result: TranscriptResult) => void;
  currentTime?: number;
  onSeekToTime?: (time: number) => void;
  className?: string;
}

function TranscriptView({
  result,
  jobId,
  onResultUpdate,
  currentTime = 0,
  onSeekToTime,
  className = '',
}: TranscriptViewProps) {
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [showSpeakers, setShowSpeakers] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Edit-mode draft: a mutable copy of result.segments that the editor
  // writes into for every operation — text edits, per-segment speaker
  // changes, and splits. Becomes the authoritative payload sent to
  // PUT /job/{id}/segments on Save. Null outside edit mode.
  const [draftSegments, setDraftSegments] = useState<Segment[] | null>(null);
  // Per-segment refs so Split can read the textarea's caret position to
  // decide where to break the text.
  const segmentTextareaRefs = useRef<Record<number, HTMLTextAreaElement | null>>({});
  // Local error (e.g. split refused because cursor is at edge).
  const [splitError, setSplitError] = useState<string | null>(null);

  // Speaker renaming
  const [speakerNames, setSpeakerNames] = useState<Record<string, string>>({});
  const [editingSpeaker, setEditingSpeaker] = useState<string | null>(null);
  const [tempSpeakerName, setTempSpeakerName] = useState('');
  const [isSavingSpeaker, setIsSavingSpeaker] = useState(false);
  const [speakerError, setSpeakerError] = useState<string | null>(null);

  // Post-transcription speaker assignment.
  //   draftAssignments: per-label text input state (empty = skip for now)
  //   registry: known speakers (for autocomplete)
  //   insightStatus: whether the async insight-extraction task is running
  const [registry, setRegistry] = useState<Speaker[]>([]);
  const [draftAssignments, setDraftAssignments] = useState<Record<string, string>>({});
  const [assignSaving, setAssignSaving] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);
  const [insightStatus, setInsightStatus] = useState<'idle' | 'running' | 'done'>('idle');
  // B6b: inline auto-match data source — replaces the deleted post-hoc fetch.
  // `auto_speaker_matches` is fed by the refinement polling hook below.
  const [rejectedMatches, setRejectedMatches] = useState<Record<string, boolean>>({});
  // Render the badge only on the FIRST occurrence of each label in the segment
  // list (per user decision Q4). Use a ref to track seen labels across the
  // .map() iteration; resets when segments change.
  const seenLabelsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    fetchSpeakers()
      .then((list) => { if (!cancelled) setRegistry(list); })
      .catch(() => { /* silent */ });
    return () => { cancelled = true; };
  }, []);

  // Confirmation modals
  const [confirmSave, setConfirmSave] = useState(false);
  const [confirmReplace, setConfirmReplace] = useState<number>(0);

  // Search & replace
  const [showSearchPanel, setShowSearchPanel] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [searchResults, setSearchResults] = useState<number[]>([]);
  const [isReplacing, setIsReplacing] = useState(false);
  const [replaceError, setReplaceError] = useState<string | null>(null);

  const segmentRefs = useRef<Record<number, HTMLDivElement | null>>({});

  // Get unique speakers from result
  const speakers = result?.speakers || [];
  const anonymousLabels = useMemo(
    () => speakers.filter(isAnonymousLabel),
    [speakers],
  );

  // Confidence threshold mirroring backend SPEAKER_MATCH_THRESHOLD. Above → we
  // consider the suggestion strong enough to pre-fill the input; below → the
  // input stays blank but the chip still surfaces the best guess.
  const AUTO_MATCH_CONFIDENCE = 0.65;

  // B6a: poll for refinement + learning state once the job is completed.
  // The parent transcription poller stops at completion; this hook takes over
  // for the post-completion refinement lifecycle.
  const refineState = useJobAutoRefinePolling(jobId, true);

  // B6b: inline auto-match data source — keyed by pyannote label
  // (SPEAKER_00…). Sourced from the refinement poller above; replaces the
  // old post-hoc auto-match fetch.
  const autoMatches = refineState?.auto_speaker_matches || {};

  // Reset the "seen labels" tracker whenever the segments change so a
  // re-render emits the badge on the first occurrence again.
  useEffect(() => { seenLabelsRef.current = new Set(); }, [result?.segments]);

  // B6b: accept/reject handlers for the inline AutoMatchBadge. Accept reuses
  // the existing assign endpoint with create_new=false (we already know the
  // speaker exists in the registry — that's how voice-match found them).
  const handleAcceptAutoMatch = async (label: string, name: string, _speakerId: string) => {
    try {
      await assignJobSpeakers(jobId, [{ label, speaker_name: name, create_new: false }], false);
      // Locally rename the label so the badge disappears + the transcript
      // text updates without waiting for a full refresh.
      setSpeakerNames((prev) => ({ ...prev, [label]: name }));
    } catch (e) {
      // Surface in console only — the badge stays visible for retry.
      // eslint-disable-next-line no-console
      console.error('Accept auto-match failed', e);
    }
  };

  const handleRejectAutoMatch = (label: string) => {
    setRejectedMatches((prev) => ({ ...prev, [label]: true }));
  };

  const handleAssignSpeakers = async () => {
    const assignments: SpeakerAssignmentInput[] = [];
    for (const label of anonymousLabels) {
      const name = (draftAssignments[label] || '').trim();
      if (!name) continue;
      const existing = registry.find((r) => r.name.toLowerCase() === name.toLowerCase());
      assignments.push({
        label,
        speaker_name: existing ? existing.name : name,
        create_new: !existing,
      });
    }
    if (assignments.length === 0) {
      setAssignError('Fill in at least one name');
      return;
    }
    setAssignSaving(true);
    setAssignError(null);
    setInsightStatus('idle');
    try {
      const res = await assignJobSpeakers(jobId, assignments, true);
      // Refresh the transcript view with the newly-named segments.
      onResultUpdate?.({
        ...result,
        segments: res.segments,
        speakers: res.speakers,
      });
      // Clear the drafts that were just saved.
      setDraftAssignments((prev) => {
        const next = { ...prev };
        for (const a of assignments) delete next[a.label];
        return next;
      });
      // Refresh the registry so new speakers appear in the autocomplete.
      try {
        const list = await fetchSpeakers();
        setRegistry(list);
      } catch { /* non-fatal */ }
      if (res.insight_extraction_scheduled) {
        setInsightStatus('running');
        // Simple heuristic timer: surface a "done" banner ~20s later. The
        // backend runs the update asynchronously via BackgroundTasks; there's
        // no streaming progress hook, so we show a best-effort indicator.
        setTimeout(() => setInsightStatus('done'), 20000);
      }
    } catch (err: any) {
      setAssignError(err?.message || 'Assignment failed');
    } finally {
      setAssignSaving(false);
    }
  };

  // Get current playing segment index
  const getCurrentSegmentIndex = () => {
    if (!result?.segments) return -1;
    return result.segments.findIndex(
      segment => currentTime >= segment.start && currentTime <= segment.end
    );
  };

  const currentSegmentIndex = getCurrentSegmentIndex();

  // Auto-scroll to current segment
  useEffect(() => {
    if (!result?.segments || !currentTime) return;

    const currentSegment = result.segments.findIndex(
      segment => currentTime >= segment.start && currentTime <= segment.end
    );

    if (currentSegment >= 0 && segmentRefs.current[currentSegment]) {
      segmentRefs.current[currentSegment]!.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });
    }
  }, [currentTime, result]);

  // All edit-mode mutations go through the draft. Outside edit mode the
  // draft is null and we read directly from result.segments.
  const handleEditSegment = (index: number, newText: string) => {
    setDraftSegments((prev) =>
      prev ? prev.map((s, j) => (j === index ? { ...s, text: newText } : s)) : prev
    );
  };

  const handleChangeSegmentSpeaker = (index: number, newSpeaker: string) => {
    setDraftSegments((prev) =>
      prev ? prev.map((s, j) => (j === index ? { ...s, speaker: newSpeaker } : s)) : prev
    );
  };

  // Split the segment at the current cursor position in its textarea.
  // Reject edge positions (0 or ≥ text length) so we never produce an empty
  // half. Timestamps are char-proportional — exact enough for insight
  // extraction and the user can still eyeball-adjust after the fact.
  const handleSplitSegment = (index: number) => {
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
      } as Segment;
      const next = [...prev];
      next.splice(index, 1, partA, partB);
      return next;
    });
  };

  const enterEditMode = () => {
    setDraftSegments(
      (result?.segments || []).map((s) => ({ ...s }))
    );
    setSplitError(null);
    setSaveError(null);
    setIsEditing(true);
  };

  const exitEditMode = () => {
    setDraftSegments(null);
    setSplitError(null);
    setIsEditing(false);
  };

  // After saveEdits we may want to re-run insight extraction. This is async
  // + long-running; we surface a status line next to the "Re-extract" button.
  const [reExtracting, setReExtracting] = useState(false);
  const [reExtractResult, setReExtractResult] = useState<{ updated: number; errors: number } | null>(null);
  const [reExtractError, setReExtractError] = useState<string | null>(null);

  const handleReExtractInsights = async () => {
    if (!jobId) return;
    setReExtracting(true);
    setReExtractResult(null);
    setReExtractError(null);
    try {
      const { extractJobSpeakerInsights } = await import('../utils/api');
      const res = await extractJobSpeakerInsights(jobId);
      setReExtractResult({ updated: res.updated.length, errors: res.errors.length });
    } catch (e: any) {
      setReExtractError(e?.message || 'Re-extract failed');
    } finally {
      setReExtracting(false);
    }
  };

  const saveEdits = async () => {
    if (!jobId || !draftSegments) {
      exitEditMode();
      return;
    }

    // Diff draft vs original to decide whether the save is worth issuing and
    // how many changes we're about to commit (drives the confirm modal).
    const original = result?.segments || [];
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
      return;
    }

    // Rough change count for the confirm modal — enough to nudge the user
    // but doesn't need to be perfectly precise.
    const changeCount = lengthChanged
      ? Math.abs(draftSegments.length - original.length) + draftSegments.filter((s, i) => {
          const o = original[i];
          return o && ((s.text ?? '') !== (o.text ?? '') || (s.speaker ?? '') !== (o.speaker ?? ''));
        }).length
      : draftSegments.reduce((n, s, i) => {
          const o = original[i];
          return n + (!o || (s.text ?? '') !== (o.text ?? '') || (s.speaker ?? '') !== (o.speaker ?? '') ? 1 : 0);
        }, 0);
    if (changeCount > 1 && !confirmSave) {
      setConfirmSave(true);
      return;
    }

    setConfirmSave(false);
    setIsSaving(true);
    setSaveError(null);
    try {
      // Strip client-only flags before hitting the backend.
      const cleaned = draftSegments.map(({ _justSplit: _js, ...s }: any) => s);
      await updateSegments(jobId, cleaned);

      const nextSpeakers = Array.from(new Set(
        cleaned.map((s: any) => s.speaker).filter(Boolean)
      )) as string[];

      onResultUpdate?.({
        ...result,
        segments: cleaned,
        speakers: nextSpeakers,
      });

      exitEditMode();
      setReExtractResult(null);
      setReExtractError(null);
    } catch (err: any) {
      setSaveError(err.message || 'Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  };

  // Speaker renaming functions
  const startEditingSpeaker = (speaker: string) => {
    setEditingSpeaker(speaker);
    setTempSpeakerName(speakerNames[speaker] || speaker);
  };

  const cancelEditingSpeaker = () => {
    setEditingSpeaker(null);
    setTempSpeakerName('');
  };

  const saveSpeakerName = async () => {
    if (!editingSpeaker || !tempSpeakerName.trim() || !jobId) return;

    setIsSavingSpeaker(true);
    setSpeakerError(null);
    try {
      const mapping = { [editingSpeaker]: tempSpeakerName.trim() };
      const data = await updateSpeakers(jobId, mapping);

      setSpeakerNames(prev => ({ ...prev, [editingSpeaker]: tempSpeakerName.trim() }));
      onResultUpdate?.({ ...result, segments: data.segments, speakers: data.speakers });
      cancelEditingSpeaker();
    } catch (err: any) {
      setSpeakerError(err.message || 'Failed to rename speaker');
    } finally {
      setIsSavingSpeaker(false);
    }
  };

  // Search functions
  const performSearch = () => {
    if (!result?.segments || !searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    const matches: number[] = [];
    const query = searchQuery.toLowerCase();
    result.segments.forEach((segment, index) => {
      if (segment.text.toLowerCase().includes(query)) {
        matches.push(index);
      }
    });
    setSearchResults(matches);
  };

  const replaceInSegment = async (index: number) => {
    if (!searchQuery || !result?.segments) return;

    setIsReplacing(true);
    setReplaceError(null);

    const segment = result.segments[index];
    const newText = segment.text.replace(new RegExp(escapeRegExp(searchQuery), 'gi'), replaceText);

    // Used to be edit-mode-aware; now search & replace just operates on
    // the committed segments directly and auto-saves — matching the
    // existing UX where each Replace is a one-shot persist.
    const updatedSegments = result.segments.map((seg, i) => (
      i === index ? { ...seg, text: newText } : seg
    ));

    try {
      await updateSegments(jobId, updatedSegments);
      onResultUpdate?.({ ...result, segments: updatedSegments });
      performSearch();
    } catch (err: any) {
      setReplaceError(err.message || 'Failed to replace text');
    } finally {
      setIsReplacing(false);
    }
  };

  const replaceAll = async () => {
    if (!searchQuery || !result?.segments) return;

    // Count total occurrences across all segments
    const regex = new RegExp(escapeRegExp(searchQuery), 'gi');
    let totalOccurrences = 0;
    result.segments.forEach((segment) => {
      const matches = segment.text.match(regex);
      if (matches) totalOccurrences += matches.length;
    });

    if (totalOccurrences === 0) return;

    if (!confirmReplace) {
      setConfirmReplace(totalOccurrences);
      return;
    }

    setConfirmReplace(0);
    setIsReplacing(true);
    setReplaceError(null);

    const updatedSegments = result.segments.map((segment) => ({
      ...segment,
      text: segment.text.replace(new RegExp(escapeRegExp(searchQuery), 'gi'), replaceText)
    }));

    try {
      await updateSegments(jobId, updatedSegments);
      onResultUpdate?.({ ...result, segments: updatedSegments });
      setSearchResults([]);
      setSearchQuery('');
      setReplaceText('');
    } catch (err: any) {
      setReplaceError(err.message || 'Failed to replace all');
    } finally {
      setIsReplacing(false);
    }
  };

  // Highlight matching text
  const highlightText = (text: string, index: number): React.ReactNode => {
    if (!searchQuery || !searchResults.includes(index)) return text;

    const regex = new RegExp(`(${escapeRegExp(searchQuery)})`, 'gi');
    const parts = text.split(regex);

    return parts.map((part, i) =>
      regex.test(part) ? <mark key={i} className="bg-yellow-400 text-black px-0.5 rounded">{part}</mark> : part
    );
  };

  const handleSeek = (time: number) => {
    onSeekToTime?.(time);
  };

  return (
    <div className={className}>
      {/* Language & Speakers Info */}
      <div className="flex flex-wrap items-center gap-2 sm:gap-4 mb-6 p-3 bg-slate-100 dark:bg-slate-700/50 rounded-lg text-sm sm:text-base">
        {result.language && (
          <div className="flex items-center gap-2">
            <span className="text-slate-500 dark:text-slate-300">Language:</span>
            <span className="font-medium">{LANGUAGES[result.language] || result.language.toUpperCase()}</span>
            {result.language_probability && (
              <span className="text-slate-500 dark:text-slate-400 text-sm">
                ({(result.language_probability * 100).toFixed(1)}%)
              </span>
            )}
          </div>
        )}
        {refineState?.refinement_status && (
          <RefinementBadge status={refineState.refinement_status} />
        )}
        {speakers.length > 0 && (
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-purple-400" />
            <span className="text-slate-500 dark:text-slate-300">Speakers:</span>
            <span className="font-medium">{speakers.length}</span>
          </div>
        )}
        {result.source === 'youtube_captions' && (
          <span
            role="status"
            aria-label={
              result.is_generated
                ? 'Source: YouTube auto-generated captions (lower quality)'
                : 'Source: YouTube human-authored captions'
            }
            className={
              result.is_generated
                ? 'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-700 dark:text-amber-400'
                : 'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/20 text-green-700 dark:text-green-400'
            }
          >
            {result.is_generated ? 'Auto-generated captions' : 'YouTube captions'}
          </span>
        )}
      </div>

      {/* Name the speakers — only surfaces while there are still anonymous
          diarization labels waiting to be mapped to real speakers in the
          registry. Unlike the inline "Rename Speakers" block below, this one
          writes back to the Speakers DB, saves a voice embedding for future
          auto-match, and kicks off personality-insight extraction. */}
      {anonymousLabels.length > 0 && (
        <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-xl">
          <h3 className="text-sm font-medium text-blue-700 dark:text-blue-300 mb-1 flex items-center gap-2">
            <UserPlus className="w-4 h-4" aria-hidden="true" />
            Name the speakers
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
            Type any name — if it matches an existing speaker you'll see <span className="font-medium text-slate-600 dark:text-slate-300">↪ existing</span>; otherwise a new speaker is created in your registry on save, marked <span className="font-medium text-emerald-700 dark:text-emerald-400">＋ new</span>. Their voice is saved so future recordings auto-match, and insights from this call are appended to their profile.
          </p>
          <datalist id="speakers-registry">
            {registry.map((s) => <option key={s.speaker_id} value={s.name} />)}
          </datalist>
          <div className="space-y-2">
            {anonymousLabels.map((label) => {
              const value = draftAssignments[label] ?? '';
              const match = registry.find((r) => r.name.toLowerCase() === value.trim().toLowerCase());
              return (
                <div key={label} className="flex items-center gap-2 flex-wrap">
                  <span className="inline-flex items-center gap-1 text-xs font-mono px-2 py-1 rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                    {label}
                  </span>
                  <input
                    type="text"
                    list="speakers-registry"
                    value={value}
                    onChange={(e) => setDraftAssignments((prev) => ({ ...prev, [label]: e.target.value }))}
                    placeholder="Speaker name (existing or new)"
                    disabled={assignSaving}
                    className="flex-1 min-w-[180px] px-3 py-1.5 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:opacity-50"
                  />
                  {value.trim() && (
                    <span
                      className={`text-xs font-medium px-2 py-1 rounded ${
                        match
                          ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
                          : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                      }`}
                    >
                      {match ? '↪ existing' : '＋ new speaker'}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
          <div className="flex items-center gap-3 mt-3 flex-wrap">
            <button
              type="button"
              onClick={handleAssignSpeakers}
              disabled={assignSaving || anonymousLabels.every((l) => !(draftAssignments[l] || '').trim())}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
            >
              {assignSaving ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> : <Save className="w-4 h-4" aria-hidden="true" />}
              Save speakers
            </button>
            {insightStatus === 'running' && (
              <span className="inline-flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                <Sparkles className="w-4 h-4 text-amber-500 animate-pulse" aria-hidden="true" />
                Extracting personality insights in the background…
              </span>
            )}
            {insightStatus === 'done' && (
              <span className="inline-flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                <Sparkles className="w-4 h-4" aria-hidden="true" />
                Speakers updated with new insights.
              </span>
            )}
            {assignError && <span role="alert" className="text-red-500 text-xs">{assignError}</span>}
          </div>
        </div>
      )}

      {/* Speaker Renaming */}
      {speakers.length > 0 && (
        <div className="mb-6 p-4 bg-slate-100 dark:bg-slate-700/30 rounded-xl">
          <h3 className="text-sm font-medium text-slate-600 dark:text-slate-300 mb-3 flex items-center gap-2">
            <Edit3 className="w-4 h-4" />
            Rename Speakers
          </h3>
          <div className="flex flex-wrap gap-2">
            {speakers.map((speaker) => (
              <div key={speaker} className="flex items-center gap-1">
                {editingSpeaker === speaker ? (
                  <div className="flex items-center gap-1 bg-slate-200 dark:bg-slate-600 rounded-lg px-2 py-1">
                    <input
                      type="text"
                      value={tempSpeakerName}
                      onChange={(e) => setTempSpeakerName(e.target.value)}
                      className="w-24 bg-white dark:bg-slate-700 text-slate-900 dark:text-white px-2 py-1 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                      autoFocus
                      disabled={isSavingSpeaker}
                      onKeyDown={(e) => e.key === 'Enter' && saveSpeakerName()}
                    />
                    <button
                      type="button"
                      onClick={saveSpeakerName}
                      disabled={isSavingSpeaker}
                      aria-label="Save speaker name"
                      className="p-2.5 min-w-[44px] min-h-[44px] text-green-500 hover:text-green-400 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                    >
                      {isSavingSpeaker
                        ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                        : <Check className="w-4 h-4" aria-hidden="true" />}
                    </button>
                    <button
                      type="button"
                      onClick={cancelEditingSpeaker}
                      disabled={isSavingSpeaker}
                      aria-label="Cancel rename"
                      className="p-2.5 min-w-[44px] min-h-[44px] text-red-500 hover:text-red-400 disabled:opacity-50 flex items-center justify-center"
                    >
                      <X className="w-4 h-4" aria-hidden="true" />
                    </button>
                    {speakerError && <span role="alert" className="text-red-400 text-xs ml-1">{speakerError}</span>}
                  </div>
                ) : (
                  <div className="flex items-center gap-1 bg-purple-500/20 text-purple-300 rounded-lg px-3 py-1">
                    <span className="text-sm">{speakerNames[speaker] || speaker}</span>
                    <button
                      type="button"
                      onClick={() => startEditingSpeaker(speaker)}
                      aria-label={`Rename speaker ${speakerNames[speaker] || speaker}`}
                      className="p-2.5 min-w-[44px] min-h-[44px] hover:text-purple-200 transition-colors flex items-center justify-center"
                    >
                      <Edit3 className="w-3 h-3" aria-hidden="true" />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Edit / Search Controls */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {isEditing ? (
          <button
            onClick={saveEdits}
            disabled={isSaving}
            className="flex items-center gap-2 px-3 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        ) : (
          <>
            <button
              onClick={enterEditMode}
              className="flex items-center gap-2 px-3 py-2 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 rounded-lg transition-colors"
            >
              <Edit2 className="w-4 h-4" aria-hidden="true" />
              Edit
            </button>
            {/* Re-extract is only useful when the transcript has named
                speakers (insights are produced per speaker). Guard on
                whether at least one segment is labeled. */}
            {result?.segments?.some((s) => s.speaker && !isAnonymousLabel(s.speaker)) && (
              <button
                type="button"
                onClick={handleReExtractInsights}
                disabled={reExtracting}
                title="Regenerate Explicit + Implicit insights for every named speaker, using the current segment attributions."
                className="flex items-center gap-2 px-3 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg transition-colors disabled:opacity-50"
              >
                {reExtracting ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> : <Sparkles className="w-4 h-4" aria-hidden="true" />}
                {reExtracting ? 'Re-extracting…' : 'Re-extract insights'}
              </button>
            )}
            {reExtractResult && (
              <span className="text-xs text-slate-500 dark:text-slate-400 inline-flex items-center gap-1">
                <Sparkles className="w-3 h-3" aria-hidden="true" />
                Refreshed {reExtractResult.updated} section{reExtractResult.updated === 1 ? '' : 's'}
                {reExtractResult.errors > 0 && ` · ${reExtractResult.errors} error${reExtractResult.errors === 1 ? '' : 's'}`}
              </span>
            )}
            {reExtractError && (
              <span role="alert" className="text-xs text-red-500">{reExtractError}</span>
            )}
          </>
        )}
        <button
          onClick={() => {
            const next = !showSearchPanel;
            setShowSearchPanel(next);
            if (!next) {
              setSearchQuery('');
              setReplaceText('');
              setSearchResults([]);
              setReplaceError(null);
            }
          }}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
            showSearchPanel ? 'bg-orange-500 text-white' : 'bg-slate-200 text-slate-600 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600'
          }`}
        >
          <Search className="w-4 h-4" />
          Search & Replace
        </button>
        {saveError && (
          <span className="text-red-400 text-sm">{saveError}</span>
        )}
      </div>

      {/* Search & Replace Panel */}
      {showSearchPanel && (
        <div className="mb-4 p-4 bg-slate-100 dark:bg-slate-700/30 rounded-xl">
          <div className="flex flex-col sm:flex-row gap-3 mb-3">
            <div className="flex-1 min-w-0">
              <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Search</label>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && performSearch()}
                placeholder="Search text..."
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 dark:bg-slate-700 dark:border-slate-600 dark:text-white focus:outline-none focus:border-blue-400"
              />
            </div>
            <div className="flex-1 min-w-0">
              <label className="text-xs text-slate-500 dark:text-slate-400 mb-1 block">Replace with</label>
              <input
                type="text"
                value={replaceText}
                onChange={(e) => setReplaceText(e.target.value)}
                placeholder="Replacement text..."
                className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 dark:bg-slate-700 dark:border-slate-600 dark:text-white focus:outline-none focus:border-blue-400"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={performSearch}
              disabled={isReplacing}
              className="flex items-center gap-2 px-3 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Search className="w-4 h-4" />
              Find
            </button>
            {searchResults.length > 0 && (
              <>
                <span className="text-sm text-slate-500 dark:text-slate-400">
                  {searchResults.length} match{searchResults.length !== 1 ? 'es' : ''} found
                </span>
                <button
                  onClick={replaceAll}
                  disabled={isReplacing}
                  className="flex items-center gap-2 px-3 py-2 bg-orange-500 hover:bg-orange-600 rounded-lg text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isReplacing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Replace className="w-4 h-4" />}
                  {isReplacing ? 'Replacing...' : 'Replace All'}
                </button>
              </>
            )}
            {searchQuery && (
              <button
                onClick={() => { setSearchQuery(''); setReplaceText(''); setSearchResults([]); setReplaceError(null); }}
                className="flex items-center gap-1 px-2 py-2 text-slate-500 dark:text-slate-400 hover:text-slate-300 transition-colors"
              >
                <X className="w-4 h-4" />
                Clear
              </button>
            )}
            {replaceError && (
              <span className="text-red-400 text-sm">{replaceError}</span>
            )}
          </div>
        </div>
      )}

      {/* View Toggles */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <button
          onClick={() => setShowTimestamps(!showTimestamps)}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
            showTimestamps ? 'bg-blue-500 text-white' : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
          }`}
        >
          <Clock className="w-4 h-4" />
          Timestamps
        </button>
        {speakers.length > 0 && (
          <button
            onClick={() => setShowSpeakers(!showSpeakers)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
              showSpeakers ? 'bg-purple-500 text-white' : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
            }`}
          >
            <Users className="w-4 h-4" />
            Speakers
          </button>
        )}
      </div>

      {/* Transcription Text */}
      <div className="bg-slate-50 dark:bg-slate-900/50 rounded-xl p-4 max-h-[60vh] min-h-[16rem] overflow-y-auto">
        {splitError && (
          <div role="alert" className="mb-3 text-xs text-amber-700 dark:text-amber-300 bg-amber-500/10 border border-amber-400/40 rounded px-3 py-2">
            {splitError}
          </div>
        )}
        {/* B6b: mini-banner with bulk "Accept all" when 2+ speakers are
            auto-matched and not yet accepted/rejected. */}
        {(() => {
          const pending = Object.entries(autoMatches).filter(
            ([lbl, m]) => m?.matched && !rejectedMatches[lbl] && !speakerNames[lbl]
          );
          if (pending.length < 2) return null;
          return (
            <div className="mb-3 px-3 py-2 rounded-lg bg-indigo-50 dark:bg-indigo-900/20 text-sm text-indigo-700 dark:text-indigo-300 flex items-center justify-between">
              <span>{pending.length} speakers auto-matched from your registry.</span>
              <button
                onClick={async () => {
                  for (const [lbl, m] of pending) {
                    if (m.speaker_id && m.name) {
                      await handleAcceptAutoMatch(lbl, m.name, m.speaker_id);
                    }
                  }
                }}
                className="ml-3 px-3 py-1 text-xs rounded bg-indigo-600 hover:bg-indigo-700 text-white"
              >
                Accept all
              </button>
            </div>
          );
        })()}
        {(showTimestamps || showSpeakers) && (draftSegments ?? result.segments) ? (
          <div className="space-y-3">
            {(draftSegments ?? result.segments ?? []).map((segment: any, index: number) => {
              const isCurrentSegment = index === currentSegmentIndex;
              const original = result?.segments?.[index];
              // Dirty comparisons only make sense when the array still aligns
              // to the source. Once a split has inserted a row, indices after
              // the split don't correspond to the original; we rely on the
              // `_justSplit` marker to highlight both halves instead.
              const aligned = !draftSegments || draftSegments.length === (result?.segments?.length ?? 0);
              const textChanged = isEditing && aligned && original != null
                && (segment.text ?? '') !== (original.text ?? '');
              const speakerChanged = isEditing && aligned && original != null
                && (segment.speaker ?? '') !== (original.speaker ?? '');
              const justSplit = isEditing && !!segment._justSplit;

              return (
                <React.Fragment key={`seg-${segment.start}-${segment.end}-${index}`}>
                  {segment.paragraph_break && index > 0 && (
                    <div className="border-t border-slate-200 dark:border-slate-700 my-2" />
                  )}
                  <div
                    ref={el => { segmentRefs.current[index] = el; }}
                    className={`flex gap-2 sm:gap-3 p-2 rounded transition-all ${
                      isCurrentSegment ? 'bg-blue-500/20 border-l-2 border-blue-400' : ''
                    } ${textChanged ? 'bg-yellow-500/10' : ''} ${speakerChanged ? 'bg-amber-500/10' : ''} ${justSplit ? 'ring-1 ring-amber-400' : ''}`}
                  >
                  {showTimestamps && (
                    <button
                      onClick={() => handleSeek(segment.start)}
                      className="text-blue-400 hover:text-blue-300 font-mono text-xs sm:text-sm whitespace-nowrap pt-1 cursor-pointer transition-colors min-w-[44px] text-left"
                    >
                      [{formatTime(segment.start)}]
                    </button>
                  )}
                  {showSpeakers && segment.speaker && !isEditing && (() => {
                    const lbl = segment.speaker;
                    const showBadge = (
                      isAnonymousLabel(lbl) &&
                      !!autoMatches[lbl]?.matched &&
                      !rejectedMatches[lbl] &&
                      !seenLabelsRef.current.has(lbl)
                    );
                    if (showBadge) seenLabelsRef.current.add(lbl);
                    return (
                      <span className="flex items-center gap-1 pt-1 whitespace-nowrap">
                        <span className="text-purple-400 font-medium text-xs sm:text-sm">
                          {speakerNames[lbl] || lbl}:
                        </span>
                        {showBadge && (
                          <AutoMatchBadge
                            label={lbl}
                            match={autoMatches[lbl]}
                            onAccept={handleAcceptAutoMatch}
                            onReject={handleRejectAutoMatch}
                          />
                        )}
                      </span>
                    );
                  })()}
                  {isEditing && segment.speaker && speakers.length > 0 && (
                    <select
                      value={segment.speaker}
                      onChange={(e) => handleChangeSegmentSpeaker(index, e.target.value)}
                      aria-label={`Speaker for segment at ${formatTime(segment.start)}`}
                      className={`text-xs font-medium rounded px-1.5 py-1 border focus:outline-none focus:ring-1 focus:ring-blue-400 whitespace-nowrap ${
                        speakerChanged
                          ? 'bg-amber-500 text-white border-amber-500'
                          : 'bg-purple-500/20 text-purple-700 dark:text-purple-300 border-purple-500/40'
                      }`}
                    >
                      {/* Include the current value even if it's not in the
                          top-level speakers list (rare: editing introduces
                          a name not in the distinct-set). */}
                      {!speakers.includes(segment.speaker) && (
                        <option value={segment.speaker}>{speakerNames[segment.speaker] || segment.speaker}</option>
                      )}
                      {speakers.map((sp) => (
                        <option key={sp} value={sp}>{speakerNames[sp] || sp}</option>
                      ))}
                    </select>
                  )}
                  {isEditing ? (
                    <div className="flex-1 flex flex-col gap-1">
                      <textarea
                        ref={(el) => { segmentTextareaRefs.current[index] = el; }}
                        rows={2}
                        value={segment.text}
                        onChange={(e) => handleEditSegment(index, e.target.value)}
                        onFocus={() => setSplitError(null)}
                        className="bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-200 px-2 py-1 rounded border border-slate-300 dark:border-slate-600 focus:outline-none focus:border-blue-400 resize-y"
                      />
                      <button
                        type="button"
                        onClick={() => handleSplitSegment(index)}
                        title="Place the cursor between two words inside the text, then click to break this segment in two."
                        className="self-start text-[11px] text-slate-500 hover:text-amber-600 dark:text-slate-400 dark:hover:text-amber-400 inline-flex items-center gap-1"
                      >
                        <Scissors className="w-3 h-3" aria-hidden="true" />
                        Split at cursor
                      </button>
                    </div>
                  ) : (
                    <p className={`text-slate-800 dark:text-slate-200 leading-relaxed flex-1 ${searchResults.includes(index) ? 'bg-yellow-500/10 rounded px-1' : ''}`}>
                      {highlightText(segment.text, index)}
                      {searchResults.includes(index) && replaceText && (
                        <button
                          onClick={() => replaceInSegment(index)}
                          disabled={isReplacing}
                          className="ml-2 text-xs px-2 py-0.5 bg-orange-500 hover:bg-orange-600 rounded text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Replace
                        </button>
                      )}
                    </p>
                  )}
                  </div>
                </React.Fragment>
              );
            })}
          </div>
        ) : (
          <p className="text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap">
            {result.result}
          </p>
        )}
      </div>

      <ConfirmModal
        open={confirmSave}
        title="Save Changes"
        message={
          draftSegments
            ? `Save changes to ${draftSegments.length !== (result?.segments?.length ?? 0) ? 'the transcript structure + ' : ''}${
                draftSegments.reduce((n, s, i) => {
                  const o = result?.segments?.[i];
                  return n + (o && ((s.text ?? '') !== (o.text ?? '') || (s.speaker ?? '') !== (o.speaker ?? '')) ? 1 : 0);
                }, 0)
              } segment(s)? This cannot be undone.`
            : 'Save changes? This cannot be undone.'
        }
        confirmLabel="Save"
        cancelLabel="Cancel"
        onConfirm={saveEdits}
        onCancel={() => setConfirmSave(false)}
      />

      <ConfirmModal
        open={confirmReplace > 0}
        title="Replace All"
        message={`Replace ${confirmReplace} occurrence${confirmReplace !== 1 ? 's' : ''} of "${searchQuery}" with "${replaceText}"?`}
        confirmLabel="Replace All"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={replaceAll}
        onCancel={() => setConfirmReplace(0)}
      />
    </div>
  );
}

export default React.memo(TranscriptView);
