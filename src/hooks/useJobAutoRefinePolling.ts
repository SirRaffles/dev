import { useEffect, useState, useRef } from 'react';
import { fetchJobAutoRefineState, RefinementStatus, LearningStatus, LearningSummary, AutoSpeakerMatch, RefinementMode, SpeakerReviewStatus } from '../utils/api';

interface AutoRefineState {
  refinement_status: RefinementStatus;
  refinement_mode: RefinementMode | null;
  refinement_reason: string | null;
  learning_status: LearningStatus;
  learning_summary: LearningSummary | null;
  auto_speaker_matches: Record<string, AutoSpeakerMatch> | null;
  phase: string | null;
  speakers_resolved: boolean;
  speaker_review_status: SpeakerReviewStatus;
}

const TERMINAL_REFINEMENT = new Set<string>(['done', 'failed']);
const POLL_INTERVAL_MS = 5000;  // Per user decision Q6: 5s constant, no backoff.

/**
 * Polls /job/{id} for the post-completion B2 + Plan 7 gate fields.
 * Active only when the transcription job is `completed` (so the parent
 * transcription poller has already stopped).
 *
 * Stop condition: if no refinement is planned, stop once phase is clear. If
 * refinement runs, stop after refinement+learning are done.
 *
 * The backend's refinement lifecycle is:
 *   raw transcript completed (speakers_resolved may still be false)
 *     → refining (refinement_status='processing', phase='refining')
 *     → refinement_status='done', phase='learning'   (post-refinement workers)
 *     → refinement_status='done', phase=null         (everything finished)
 *
 * Stopping at refinement_status='done' alone would park the UI on
 * phase='learning' forever (the user sees "Learning…" stuck because the
 * later phase=null update is never fetched). speakers_resolved=false is now
 * a review signal, not a polling blocker.
 *
 * `failed` is a hard terminal: phase / speakers_resolved may or may not
 * change, but no more meaningful transitions happen, so stop immediately.
 */
export function useJobAutoRefinePolling(jobId: string | null, jobCompleted: boolean): AutoRefineState | null {
  const [state, setState] = useState<AutoRefineState | null>(null);
  const stopRef = useRef(false);

  useEffect(() => {
    stopRef.current = false;
    if (!jobId || !jobCompleted) {
      setState(null);
      return;
    }

    let cancelled = false;
    const tick = async () => {
      try {
        const next = await fetchJobAutoRefineState(jobId);
        if (cancelled) return;
        setState(next);
        const ref = next.refinement_status;
        if (ref === 'failed') {
          stopRef.current = true;
          return;
        }
        if (ref === null && next.phase === null) {
          stopRef.current = true;
          return;
        }
        if (ref === 'done' && next.phase === null) {
          stopRef.current = true;
          return;
        }
      } catch {
        // Network blip — keep polling.
      }
      if (!cancelled && !stopRef.current) {
        setTimeout(tick, POLL_INTERVAL_MS);
      }
    };
    tick();

    return () => { cancelled = true; stopRef.current = true; };
  }, [jobId, jobCompleted]);

  return state;
}

// Re-exported for tests; not part of the public hook API.
export const __TEST_TERMINAL_REFINEMENT = TERMINAL_REFINEMENT;
