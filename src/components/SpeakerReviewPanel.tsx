import { useEffect, useMemo, useState } from 'react';
import { UserCheck, UserX, UserPlus, Loader2, Sparkles } from 'lucide-react';
import {
  AutoSpeakerMatch,
  Segment,
  Speaker,
  fetchSpeakers,
  reRefineJob,
} from '../utils/api';
import RejectMatchModal, { RejectTarget } from './RejectMatchModal';
import { isAnonymousLabel } from './TranscriptView';  // exported in Task 5's Step 2

/**
 * Single source of truth for post-completion speaker review (Plan 5).
 * Replaces both:
 *   - the inline AutoMatchBadge per first-occurrence segment
 *   - the "Name the speakers" panel
 *
 * Owns a local `pendingCorrections` map; the user accumulates corrections
 * (confirm / reject / re-attribute / create) before clicking "Apply &
 * re-refine", which sends ONE POST /job/{id}/re-refine and shows a loading
 * state until the polling-driven `currentPhase` returns to null (signalling
 * the backend has finished both refinement + B7 learning).
 */
interface Props {
  jobId: string;
  segments: Segment[];                                  // result.segments
  autoMatches: Record<string, AutoSpeakerMatch>;        // from useJobAutoRefinePolling
  currentPhase?: string | null;                         // from useJobAutoRefinePolling
  onReRefineStart?: () => void;                         // notify parent (clear local edits, etc.)
}

/**
 * Local per-label decision the user has made but not yet submitted.
 *   - confirm: keep the B5 match as-is (no backend op needed, but it
 *     becomes part of the assignments map so the re-refinement run sees
 *     the speaker's profile in context).
 *   - existing: re-attribute to a different registry speaker.
 *   - new: create a new speaker (backend extracts voice embedding).
 *   - unknown: strip the auto-matched name back to the anonymous label.
 */
type CorrectionAction =
  | { kind: 'confirm'; speakerId: string; name: string }
  | { kind: 'existing'; speakerId: string; name: string }
  | { kind: 'new'; name: string }
  | { kind: 'unknown' };

// Use `isAnonymousLabel` imported from TranscriptView — it matches all 3
// shapes (SPEAKER_\d+, "Speaker N", literal "Unknown"). A narrower regex
// here would misclassify "Speaker 1"-style and "Unknown" labels and break
// today's behavior.

export default function SpeakerReviewPanel({
  jobId,
  segments,
  autoMatches,
  currentPhase,
  onReRefineStart,
}: Props) {
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

  const identifiedLabels = allLabels.filter((l) => !isAnonymousLabel(l) || autoMatches[l]?.matched);
  const unknownLabels = allLabels.filter((l) => isAnonymousLabel(l) && !autoMatches[l]?.matched);

  // Load registry once (used for the modal picker + identified-name display).
  useEffect(() => {
    let cancelled = false;
    fetchSpeakers()
      .then((list) => { if (!cancelled) setRegistry(list); })
      .catch(() => { /* silent — modal will show an empty picker */ });
    return () => { cancelled = true; };
  }, []);

  // The panel is in "re-refining" mode when we've fired the POST and the
  // backend phase is non-null. Once it drops back to null, the user can edit
  // again and submit another correction cycle.
  const reRefining = submitting || currentPhase === 'refining' || currentPhase === 'learning';

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
      setAction(label, { kind: 'unknown' });
    }
    setRejectModalLabel(null);
  };

  const handleCreateForAnonymous = (label: string) => {
    const name = (newSpeakerDrafts[label] || '').trim();
    if (name) setAction(label, { kind: 'new', name });
  };

  const handleApply = async () => {
    if (pendingCorrections.size === 0) return;
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
          assignments[label] = 'unknown';
          break;
      }
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      await reRefineJob(jobId, assignments);
      onReRefineStart?.();
      // Clear local corrections — the parent's polling will reflect the new
      // segments once the re-refinement completes.
      setPendingCorrections(new Map());
      setNewSpeakerDrafts({});
    } catch (e: any) {
      setSubmitError(e?.message || 'Re-refinement failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDiscard = () => {
    setPendingCorrections(new Map());
    setNewSpeakerDrafts({});
    setSubmitError(null);
  };

  // Render nothing when there are no labels at all (defensive — TranscriptView
  // shouldn't mount the panel in that case anyway).
  if (allLabels.length === 0) return null;

  const renderAction = (label: string) => {
    const action = pendingCorrections.get(label);
    if (!action) return null;
    const verb = action.kind === 'confirm' ? 'Confirmed'
      : action.kind === 'existing' ? `→ ${action.name}`
      : action.kind === 'new' ? `+ New: ${action.name}`
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

  return (
    <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 rounded-xl">
      <h3 className="text-sm font-medium text-blue-700 dark:text-blue-300 mb-3 flex items-center gap-2">
        <Sparkles className="w-4 h-4" aria-hidden="true" />
        Speaker Review
      </h3>

      {/* Section A: Identified speakers (auto-matched or already named) */}
      {identifiedLabels.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2 uppercase tracking-wide">
            Identified
          </div>
          <ul className="space-y-2">
            {identifiedLabels.map((label) => {
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
                      <button
                        type="button"
                        onClick={() => handleConfirm(label)}
                        disabled={reRefining || !match?.matched}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
                      >
                        <UserCheck className="w-3 h-3" aria-hidden="true" />
                        Confirm
                      </button>
                      <button
                        type="button"
                        onClick={() => setRejectModalLabel(label)}
                        disabled={reRefining || !match?.matched}
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

      {/* Section B: Unknown speakers (anonymous + no match) */}
      {unknownLabels.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-slate-600 dark:text-slate-400 mb-2 uppercase tracking-wide">
            Unknown
          </div>
          <ul className="space-y-2">
            {unknownLabels.map((label) => (
              <li key={label} className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-slate-400 font-mono">{label}</span>
                {renderAction(label) ?? (
                  <>
                    <input
                      type="text"
                      value={newSpeakerDrafts[label] || ''}
                      onChange={(e) =>
                        setNewSpeakerDrafts((prev) => ({ ...prev, [label]: e.target.value }))
                      }
                      placeholder="New speaker name"
                      disabled={reRefining}
                      className="flex-1 min-w-[160px] px-3 py-1 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-400 disabled:opacity-50"
                      onKeyDown={(e) => e.key === 'Enter' && handleCreateForAnonymous(label)}
                    />
                    <button
                      type="button"
                      onClick={() => handleCreateForAnonymous(label)}
                      disabled={reRefining || !(newSpeakerDrafts[label] || '').trim()}
                      className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
                    >
                      <UserPlus className="w-3 h-3" aria-hidden="true" />
                      Create
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Apply / Discard footer */}
      <div className="flex items-center gap-3 mt-4 flex-wrap">
        <button
          type="button"
          onClick={handleApply}
          disabled={reRefining || pendingCorrections.size === 0}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
        >
          {reRefining ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              Re-refining…
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" aria-hidden="true" />
              Apply & re-refine ({pendingCorrections.size})
            </>
          )}
        </button>
        <button
          type="button"
          onClick={handleDiscard}
          disabled={reRefining || pendingCorrections.size === 0}
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
