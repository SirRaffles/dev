import React, { useState, useRef, useEffect } from 'react';
import { Clock, Users, Edit2, Save, Edit3, Search, Replace, X, Loader2, Sparkles, Scissors } from 'lucide-react';
import { LANGUAGES, updateSegments, Segment, fetchJobStatus } from '../utils/api';
import { formatTime } from './AudioPlayer';
import ConfirmModal from './ConfirmModal';
import RefinementBadge from './RefinementBadge';
import SpeakerReviewPanel from './SpeakerReviewPanel';
import RenameFileModal from './RenameFileModal';
import { useJobAutoRefinePolling } from '../hooks/useJobAutoRefinePolling';
import { escapeRegExp } from '../utils/transcriptEditOps';
import { useTranscriptEditing } from '../hooks/useTranscriptEditing';
import { useTranscriptSearch } from '../hooks/useTranscriptSearch';

// Diarization emits generic labels like SPEAKER_00 / "Speaker 1". Anything
// that matches this shape is still waiting for a real name.
export const ANON_SPEAKER_RE = /^(?:SPEAKER_\d+|Speaker\s*\d+|Unknown)$/i;
export const isAnonymousLabel = (name: string | null | undefined) =>
  !name ? true : ANON_SPEAKER_RE.test(name.trim());

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
  // Rename-source surface. Fetched once per jobId via fetchJobStatus — the
  // backend exposes original_filename + created_at on the /job/{id} response.
  // We fall back to `filename` so UI-upload + non-JPR jobs that surface a
  // basename through that field still show the inline rename affordance on
  // the main transcription screen (the actual rename endpoint is JPR-only
  // today and will 400 cleanly for other sources, which the modal surfaces).
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [displayFilename, setDisplayFilename] = useState<string | undefined>(undefined);
  const [jobCreatedAt, setJobCreatedAt] = useState<string | undefined>(undefined);
  useEffect(() => {
    let cancelled = false;
    fetchJobStatus(jobId)
      .then((js) => {
        if (cancelled) return;
        setDisplayFilename(js.original_filename || js.filename || undefined);
        setJobCreatedAt(js.created_at || undefined);
      })
      .catch(() => { /* silent — non-JPR jobs just won't surface the button */ });
    return () => { cancelled = true; };
  }, [jobId]);
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [showSpeakers, setShowSpeakers] = useState(true);

  // Speaker labels — read from segments. SpeakerReviewPanel owns all
  // renaming + re-attribution flows (Plan 5). The transcript display below
  // shows `segment.speaker` directly with no client-side override.

  // Edit-mode (draft, split, save) state + handlers live in a dedicated hook.
  // The hook persists the cleaned draft via the callback below: it strips
  // client-only flags, derives the next distinct-speakers set, and surfaces
  // the new segments to the parent.
  const editing = useTranscriptEditing({
    segments: result?.segments,
    persist: async (cleaned) => {
      await updateSegments(jobId, cleaned);
      const nextSpeakers = Array.from(new Set(
        cleaned.map((s) => s.speaker).filter(Boolean)
      )) as string[];
      onResultUpdate?.({
        ...result,
        segments: cleaned,
        speakers: nextSpeakers,
      });
      setReExtractResult(null);
      setReExtractError(null);
    },
  });
  const {
    isEditing,
    isSaving,
    saveError,
    splitError,
    setSplitError,
    draftSegments,
    segmentTextareaRefs,
    enterEditMode,
    exitEditMode,
    editSegment: handleEditSegment,
    changeSegmentSpeaker: handleChangeSegmentSpeaker,
    splitAt: handleSplitSegment,
    save,
  } = editing;

  // Search & replace state + handlers live in a dedicated hook. Replace
  // operations persist directly against the committed segments (one-shot
  // auto-save), matching the existing UX.
  const search = useTranscriptSearch({
    segments: result?.segments,
    persist: async (next) => {
      await updateSegments(jobId, next);
      onResultUpdate?.({ ...result, segments: next });
    },
  });
  const {
    searchQuery,
    setSearchQuery,
    replaceText,
    setReplaceText,
    searchResults,
    isReplacing,
    replaceError,
    performSearch,
    replaceInSegment,
    replaceAll: replaceAllOp,
    resetSearch,
  } = search;

  // Confirmation modals
  const [confirmSave, setConfirmSave] = useState(false);
  const [confirmReplace, setConfirmReplace] = useState<number>(0);

  // Search & replace panel visibility (UI-only — the search state itself is
  // owned by the hook above).
  const [showSearchPanel, setShowSearchPanel] = useState(false);

  const segmentRefs = useRef<Record<number, HTMLDivElement | null>>({});

  // Get unique speakers from result
  const speakers = result?.speakers || [];

  // B6a: poll for refinement + learning state once the job is completed.
  // The parent transcription poller stops at completion; this hook takes over
  // for the post-completion refinement lifecycle. Feeds the SpeakerReviewPanel
  // with auto-match data + phase context.
  const refineState = useJobAutoRefinePolling(jobId, true);
  const autoMatches = refineState?.auto_speaker_matches || {};

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

  // Drive the save-confirm modal: the hook decides whether a confirmation is
  // warranted (multi-segment change) and only persists once confirmed.
  const saveEdits = async () => {
    if (!jobId) {
      exitEditMode();
      return;
    }
    const { needsConfirm } = await save(confirmSave);
    if (needsConfirm) {
      setConfirmSave(true);
      return;
    }
    setConfirmSave(false);
  };

  // Drive the replace-all confirm modal: the hook returns the occurrence count
  // so we can confirm before applying, then re-invokes with `confirmed: true`.
  const replaceAll = async () => {
    if (confirmReplace) {
      setConfirmReplace(0);
      await replaceAllOp(true);
      return;
    }
    const count = await replaceAllOp(false);
    if (count > 0) {
      setConfirmReplace(count);
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
        {refineState?.refinement_reason && refineState.refinement_status == null && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200">
            {refineState.refinement_reason === 'no_context_or_speakers'
              ? 'Skipped refinement: no context or recognized speakers'
              : refineState.refinement_reason === 'off'
                ? 'Refinement off'
                : `Refinement: ${refineState.refinement_reason.replace(/_/g, ' ')}`}
          </span>
        )}
        {displayFilename && (
          <button
            type="button"
            onClick={() => setShowRenameModal(true)}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-600"
            title={`Rename source file: ${displayFilename}`}
          >
            <Edit3 className="w-3 h-3" />
            <span className="truncate max-w-[16rem]">{displayFilename}</span>
          </button>
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

      {/* Plan 5: consolidated post-completion review panel — the single
          surface for accepting/rejecting voice-match suggestions, naming
          anonymous labels, and triggering re-refinement. Replaced the
          legacy inline badge + "Name the speakers" block. */}
      {result?.segments && result.segments.length > 0 && (
        <SpeakerReviewPanel
          jobId={jobId}
          segments={result.segments}
          autoMatches={autoMatches}
          currentPhase={refineState?.phase ?? null}
          speakersResolved={refineState?.speakers_resolved ?? true}
          speakerReviewStatus={refineState?.speaker_review_status}
          onReRefineStart={() => {
            // No-op for now — the polling hook re-derives segments + matches
            // once the backend completes. A future hook could clear manual
            // edits here (per spec § "Collision with manual segment edits"
            // — out of scope for this plan).
          }}
        />
      )}

      {/* Speaker renaming is now exclusively handled by SpeakerReviewPanel
          (Plan 5): pick existing speaker OR create new + auto-trigger
          re-refinement + save voice embedding. The legacy inline "Rename
          Speakers" block was strictly inferior (no re-refinement, no
          embedding save, no registry picker) and produced a confusing
          duplicate surface for the same action. */}

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
              resetSearch();
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
                onClick={resetSearch}
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
                  {showSpeakers && segment.speaker && !isEditing && (
                    <span className="flex items-center gap-1 pt-1 whitespace-nowrap">
                      <span className="text-purple-400 font-medium text-xs sm:text-sm">
                        {segment.speaker}:
                      </span>
                    </span>
                  )}
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
                        <option value={segment.speaker}>{segment.speaker}</option>
                      )}
                      {speakers.map((sp) => (
                        <option key={sp} value={sp}>{sp}</option>
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

      {showRenameModal && displayFilename && (
        <RenameFileModal
          jobId={jobId}
          currentFilename={displayFilename}
          jobCreatedAt={jobCreatedAt}
          analysis={null}
          onClose={() => setShowRenameModal(false)}
          onRenamed={(newName) => setDisplayFilename(newName)}
        />
      )}
    </div>
  );
}

export default React.memo(TranscriptView);
