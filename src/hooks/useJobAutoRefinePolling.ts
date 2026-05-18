import { useEffect, useState, useRef } from 'react';
import { fetchJobAutoRefineState, RefinementStatus, LearningStatus, LearningSummary, AutoSpeakerMatch } from '../utils/api';

interface AutoRefineState {
  refinement_status: RefinementStatus;
  learning_status: LearningStatus;
  learning_summary: LearningSummary | null;
  auto_speaker_matches: Record<string, AutoSpeakerMatch> | null;
  phase: string | null;
}

const TERMINAL_REFINEMENT = new Set<string>(['done', 'failed']);
const POLL_INTERVAL_MS = 5000;  // Per user decision Q6: 5s constant, no backoff.

/**
 * Polls /job/{id} for the 4 B2 fields. Active only when the transcription
 * job is `completed` (so the parent transcription poller has already stopped).
 *
 * Stop condition: we need BOTH refinement_status in {done, failed} AND
 * phase === null. The backend's lifecycle is:
 *   refinement_status="processing" + phase="refining"
 *   → refinement_status="done" + phase="learning"   (post-refinement workers)
 *   → refinement_status="done" + phase=null         (everything finished)
 * Stopping at refinement_status="done" alone would park the UI on
 * phase="learning" forever — the user sees "Learning…" stuck because the
 * later phase=null update is never fetched. Wait for phase to clear too.
 *
 * `failed` is a hard terminal: phase may or may not clear, but no more
 * meaningful transitions happen, so stop immediately.
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
