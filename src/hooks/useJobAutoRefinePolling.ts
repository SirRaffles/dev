import { useEffect, useState, useRef } from 'react';
import { fetchJobAutoRefineState, RefinementStatus, LearningStatus, LearningSummary, AutoSpeakerMatch } from '../utils/api';

interface AutoRefineState {
  refinement_status: RefinementStatus;
  learning_status: LearningStatus;
  learning_summary: LearningSummary | null;
  auto_speaker_matches: Record<string, AutoSpeakerMatch> | null;
  phase: string | null;
}

const TERMINAL_STATES = new Set<string>(['done', 'failed']);
const POLL_INTERVAL_MS = 5000;  // Per user decision Q6: 5s constant, no backoff.

/**
 * Polls /job/{id} for the 4 B2 fields. Active only when the transcription
 * job is `completed` (so the parent transcription poller has already stopped).
 * Stops once refinement_status hits a terminal state (done|failed).
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
        if (next.refinement_status && TERMINAL_STATES.has(next.refinement_status)) {
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
