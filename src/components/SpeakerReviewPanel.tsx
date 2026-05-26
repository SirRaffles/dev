import { useEffect, useMemo, useState } from 'react';
import { UserCheck, UserX, UserPlus, Loader2, Sparkles, Ban } from 'lucide-react';
import {
  AutoSpeakerMatch,
  Segment,
  Speaker,
  fetchSpeakers,
  reRefineJob,
  confirmSpeakers,
} from '../utils/api';
import RejectMatchModal, { RejectTarget } from './RejectMatchModal';
import { isAnonymousLabel } from './TranscriptView';

/**
 * Speaker review surface — context-aware off `speakerReviewStatus`:
 *
 *   - Needs review: some labels are still anonymous. Refinement may already
 *     have run; this panel lets the user apply speaker updates afterward.
 *     Unknown-section rows expose an "Ignore" action so the user can
 *     leave the label anonymous without creating a duplicate profile.
 *
 *   - Reviewed/not needed: the existing correction flow. 2 sections
 *     (Identified / Unknown). Submit button is "Apply & re-refine" →
 *     POST /job/{id}/re-refine. Reject opens RejectMatchModal.
 *
 * `pendingCorrections` is shared by both modes. The submit handler picks
 * the endpoint based on the current mode. New `{kind: 'ignore'}` action
 * (needs-review only) serializes as the literal "ignore" string in
 * the assignments payload.
 */
interface Props {
  jobId: string;
  segments: Segment[];                            // result.segments
  autoMatches: Record<string, AutoSpeakerMatch>;  // from useJobAutoRefinePolling
  currentPhase?: string | null;                   // from useJobAutoRefinePolling
  speakersResolved?: boolean;                     // Backward-compatible alias
  speakerReviewStatus?: 'not_needed' | 'needs_review' | 'reviewed';
  onReRefineStart?: () => void;                   // notify parent (clear local edits, etc.)
}

/**
 * Local per-label decision the user has made but not yet submitted.
 *   - confirm: keep the B5 match as-is (no backend re-attribution, but
 *     it becomes part of the assignments map so the refinement run sees
 *     the speaker's profile in context).
 *   - existing: re-attribute to a different registry speaker.
 *   - new: create a new speaker (backend extracts voice embedding).
 *   - unknown: strip the auto-matched name back to the anonymous label.
 *     Post-refinement only — for needs-review mode use 'ignore'.
 *   - ignore: leave the label anonymous, no embedding extraction, no
 *     profile change. Needs-review mode only.
 */
type CorrectionAction =
  | { kind: 'confirm'; speakerId: string; name: string }
  | { kind: 'existing'; speakerId: string; name: string }
  | { kind: 'new'; name: string }
  | { kind: 'unknown' }
  | { kind: 'ignore' };

export default function SpeakerReviewPanel({
  jobId,
  segments,
  autoMatches,
  currentPhase,
  speakersResolved,
  speakerReviewStatus,
  onReRefineStart,
}: Props) {
  const needsReviewMode = speakerReviewStatus === 'needs_review' || (
    speakerReviewStatus === undefined && speakersResolved === false
  );

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

  // Section classification:
  //   Matched      = name resolved (non-anonymous label OR B5-matched)
  //   KnownProfiles = anonymous + unmatched + registry has candidates
  //   Unknown      = anonymous + unmatched + (registry empty OR user wants new/ignore)
  //
  // In post-refinement mode we keep the original 2-section split
  // (matched → "Identified", everything else → "Unknown") for visual
  // continuity with Plan 5. Needs-review renders all 3 sections.
  const matchedLabels = allLabels.filter((l) => !isAnonymousLabel(l) || autoMatches[l]?.matched);
  const unresolvedLabels = allLabels.filter((l) => isAnonymousLabel(l) && !autoMatches[l]?.matched);

  // In needs-review mode, split unresolved into "Known profiles (no
  // voice)" and "Unknown" based on registry availability. Per the spec,
  // Section B and C are visually similar — both render the registry
  // picker + create input. The split is a labeling nice-to-have. v1
  // renders them as separate sections for clarity; the render path is
  // identical except for the heading.
  const knownProfileLabels = needsReviewMode && registry.length > 0 ? unresolvedLabels : [];
  const unknownLabels = needsReviewMode && registry.length > 0 ? [] : unresolvedLabels;

  // Load registry once (used for the picker + identified-name display).
  useEffect(() => {
    let cancelled = false;
    fetchSpeakers()
      .then((list) => { if (!cancelled) setRegistry(list); })
      .catch(() => { /* silent — picker will show as empty */ });
    return () => { cancelled = true; };
  }, []);

  // Reset per-job state when navigating between jobs. Without this, the
  // panel keeps pendingCorrections from a previous job because TranscriptView
  // re-uses the same SpeakerReviewPanel instance across jobId changes
  // (React reconciliation).
  useEffect(() => {
    setPendingCorrections(new Map());
    setNewSpeakerDrafts({});
    setRejectModalLabel(null);
    setSubmitting(false);
    setSubmitError(null);
  }, [jobId]);

  // The panel is "submitting" while a confirm/re-refine POST is in flight
  // OR the orchestrator is actively in the refining phase. We deliberately
  // do NOT block on `currentPhase === 'learning'`: the B7 learning phase
  // runs *after* refinement completes and shouldn't lock the panel.
  const inFlight = submitting || currentPhase === 'refining';

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
      // "Mark as Unknown" semantics differ by mode. Storing the mode-correct
      // kind here (instead of remapping at submit) keeps renderAction's badge
      // consistent with what the user picked.
      setAction(label, { kind: needsReviewMode ? 'ignore' : 'unknown' });
    }
    setRejectModalLabel(null);
  };

  const handleCreateForUnresolved = (label: string) => {
    const name = (newSpeakerDrafts[label] || '').trim();
    if (name) setAction(label, { kind: 'new', name });
  };

  const handleIgnoreForUnresolved = (label: string) => {
    setAction(label, { kind: 'ignore' });
  };

  // Build the assignments map for the submit. The serialization differs
  // by mode: post-refinement maps 'unknown' → 'unknown'; needs-review
  // doesn't expose 'unknown' (uses 'ignore' instead — slightly different
  // semantics: 'unknown' strips an existing name, 'ignore' is a no-op
  // because there was no name to strip yet).
  const buildAssignments = (): Record<string, string> => {
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
          // In post-refinement mode (`/re-refine`), 'unknown' is a legacy
          // value that backend accepts. In needs-review mode
          // (`/confirm-speakers`, Plan 7A), the endpoint only enumerates
          // UUID / 'new:name' / 'ignore'. Map 'unknown' → 'ignore' when
          // pre-refining so a RejectMatchModal "Mark as Unknown" choice
          // doesn't 400. The semantics are equivalent in this mode (both
          // = "don't attach this label to any profile").
          assignments[label] = needsReviewMode ? 'ignore' : 'unknown';
          break;
        case 'ignore':
          assignments[label] = 'ignore';
          break;
      }
    }
    return assignments;
  };

  const handleApply = async () => {
    if (pendingCorrections.size === 0) return;
    const assignments = buildAssignments();
    setSubmitting(true);
    setSubmitError(null);
    try {
      if (needsReviewMode) {
        await confirmSpeakers(jobId, assignments);
      } else {
        await reRefineJob(jobId, assignments);
      }
      onReRefineStart?.();
      setPendingCorrections(new Map());
      setNewSpeakerDrafts({});
    } catch (e: any) {
      setSubmitError(e?.message || 'Submit failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDiscard = () => {
    setPendingCorrections(new Map());
    setNewSpeakerDrafts({});
    setSubmitError(null);
  };

  // Render nothing when there are no labels at all.
  if (allLabels.length === 0) return null;

  const renderAction = (label: string) => {
    const action = pendingCorrections.get(label);
    if (!action) return null;
    const verb =
      action.kind === 'confirm' ? 'Confirmed'
      : action.kind === 'existing' ? `→ ${action.name}`
      : action.kind === 'new' ? `+ New: ${action.name}`
      : action.kind === 'ignore' ? '⊘ Ignored'
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

  // Render an unresolved-label row (used by both Known-profiles and
  // Unknown sections — they share the same action row, only the section
  // heading differs).
  const renderUnresolvedRow = (label: string) => (
    <li key={label} className="flex items-center gap-2 flex-wrap">
      <span className="text-xs text-slate-400 font-mono">{label}</span>
      {renderAction(label) ?? (
        <>
          <select
            value=""
            disabled={inFlight || registry.length === 0}
            onChange={(e) => {
              const sp = registry.find((r) => r.speaker_id === e.target.value);
              if (sp) {
                setAction(label, {
                  kind: 'existing',
                  speakerId: sp.speaker_id,
                  name: sp.name,
                });
              }
            }}
            title={registry.length === 0 ? 'No existing speakers' : 'Assign to existing speaker'}
            className="px-2 py-1 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white disabled:opacity-50"
          >
            <option value="">Assign to existing…</option>
            {registry.map((sp) => (
              <option key={sp.speaker_id} value={sp.speaker_id}>{sp.name}</option>
            ))}
          </select>
          <span className="text-xs text-slate-500 dark:text-slate-400">or</span>
          <input
            type="text"
            value={newSpeakerDrafts[label] || ''}
            onChange={(e) =>
              setNewSpeakerDrafts((prev) => ({ ...prev, [label]: e.target.value }))
            }
            placeholder="New speaker name"
            disabled={inFlight}
            className="flex-1 min-w-[160px] px-3 py-1 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:opacity-50"
            onKeyDown={(e) => e.key === 'Enter' && handleCreateForUnresolved(label)}
          />
          <button
            type="button"
            onClick={() => handleCreateForUnresolved(label)}
            disabled={inFlight || !(newSpeakerDrafts[label] || '').trim()}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
          >
            <UserPlus className="w-3 h-3" aria-hidden="true" />
            Create
          </button>
          {needsReviewMode && (
            <button
              type="button"
              onClick={() => handleIgnoreForUnresolved(label)}
              disabled={inFlight}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-slate-300 text-slate-700 hover:bg-slate-400 dark:bg-slate-600 dark:text-slate-200 dark:hover:bg-slate-500 disabled:opacity-50"
              title="Leave this label anonymous; refinement will treat them as unknown"
            >
              <Ban className="w-3 h-3" aria-hidden="true" />
              Ignore
            </button>
          )}
        </>
      )}
    </li>
  );

  const submitLabel = needsReviewMode ? 'Apply speaker updates' : 'Apply & re-refine';
  const submitInFlightLabel = needsReviewMode ? 'Applying…' : 'Re-refining…';

  return (
    <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-xl">
      <h3 className="text-sm font-medium text-blue-700 dark:text-blue-300 mb-3 flex items-center gap-2">
        <Sparkles className="w-4 h-4" aria-hidden="true" />
        Speaker Review
        {needsReviewMode && (
          <span className="text-xs font-normal text-amber-700 dark:text-amber-300 ml-1">
            — speakers to verify
          </span>
        )}
      </h3>

      {/* Section A: Matched (auto-confirmed by B5 or already named) */}
      {matchedLabels.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2 uppercase tracking-wide">
            {needsReviewMode ? 'Matched (auto-confirmed)' : 'Identified'}
          </div>
          <ul className="space-y-2">
            {matchedLabels.map((label) => {
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
                      {!needsReviewMode && (
                        <button
                          type="button"
                          onClick={() => handleConfirm(label)}
                          disabled={inFlight || !match?.matched}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
                        >
                          <UserCheck className="w-3 h-3" aria-hidden="true" />
                          Confirm
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setRejectModalLabel(label)}
                        disabled={inFlight || !match?.matched}
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

      {/* Section B: Known profiles, no voice yet (needs-review only) */}
      {knownProfileLabels.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2 uppercase tracking-wide">
            Known profiles (no voice yet)
          </div>
          <ul className="space-y-2">
            {knownProfileLabels.map(renderUnresolvedRow)}
          </ul>
        </div>
      )}

      {/* Section C: Unknown */}
      {unknownLabels.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2 uppercase tracking-wide">
            Unknown
          </div>
          <ul className="space-y-2">
            {unknownLabels.map(renderUnresolvedRow)}
          </ul>
        </div>
      )}

      {/* Submit / Discard footer */}
      <div className="flex items-center gap-3 mt-4 flex-wrap">
        <button
          type="button"
          onClick={handleApply}
          disabled={inFlight || pendingCorrections.size === 0}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
        >
          {inFlight ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              {submitInFlightLabel}
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" aria-hidden="true" />
              {submitLabel} ({pendingCorrections.size})
            </>
          )}
        </button>
        <button
          type="button"
          onClick={handleDiscard}
          disabled={inFlight || pendingCorrections.size === 0}
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
