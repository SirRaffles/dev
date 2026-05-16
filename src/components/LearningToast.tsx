import { useEffect, useRef, useState } from 'react';
import { Sparkles, X } from 'lucide-react';
import { useJobAutoRefinePolling } from '../hooks/useJobAutoRefinePolling';

interface Props {
  jobId: string | null;
  jobCompleted: boolean;
  onClickReview: () => void;
}

const AUTO_DISMISS_MS = 12_000;

export default function LearningToast({ jobId, jobCompleted, onClickReview }: Props) {
  const refineState = useJobAutoRefinePolling(jobId, jobCompleted);
  const [visible, setVisible] = useState(false);
  const [paused, setPaused] = useState(false);
  const [lastShownJob, setLastShownJob] = useState<string | null>(null);
  const dismissTimerRef = useRef<number | null>(null);

  const summary = refineState?.refinement_status === 'done' ? refineState.learning_summary : null;
  const status = refineState?.learning_status ?? null;

  // Decide whether to show the toast for THIS job.
  useEffect(() => {
    if (!summary || !jobId) {
      setVisible(false);
      return;
    }
    if (jobId === lastShownJob) return;  // already shown for this job

    const total = (summary.terms_learned || 0)
      + (summary.insights_added || 0)
      + (summary.embeddings_updated || 0);

    // Per user decision Q2: suppress on failure or nothing-happened.
    if (status === 'failed' || total === 0) {
      setLastShownJob(jobId);  // don't re-fire for this job
      setVisible(false);
      return;
    }

    setVisible(true);
    setLastShownJob(jobId);
  }, [summary, status, jobId, lastShownJob]);

  // Auto-dismiss timer with hover-to-pause.
  useEffect(() => {
    if (!visible || paused) {
      if (dismissTimerRef.current !== null) {
        clearTimeout(dismissTimerRef.current);
        dismissTimerRef.current = null;
      }
      return;
    }
    dismissTimerRef.current = window.setTimeout(() => {
      setVisible(false);
    }, AUTO_DISMISS_MS);
    return () => {
      if (dismissTimerRef.current !== null) {
        clearTimeout(dismissTimerRef.current);
        dismissTimerRef.current = null;
      }
    };
  }, [visible, paused]);

  if (!visible || !summary) return null;

  const items: string[] = [];
  if (summary.terms_learned > 0) {
    items.push(`+${summary.terms_learned} glossary ${summary.terms_learned === 1 ? 'term' : 'terms'} (review)`);
  }
  if (summary.insights_added > 0) {
    items.push(`+${summary.insights_added} speaker ${summary.insights_added === 1 ? 'insight' : 'insights'}`);
  }
  if (summary.embeddings_updated > 0) {
    items.push(`~${summary.embeddings_updated} voice ${summary.embeddings_updated === 1 ? 'embedding' : 'embeddings'} updated`);
  }

  return (
    <div
      className="fixed bottom-6 right-6 z-50 max-w-sm bg-white dark:bg-slate-900 border border-emerald-200 dark:border-emerald-900/50 rounded-lg shadow-lg p-4"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="flex items-start gap-2">
        <Sparkles className="w-4 h-4 text-emerald-600 dark:text-emerald-400 mt-0.5 shrink-0" />
        <div className="flex-1 text-sm text-slate-800 dark:text-slate-200">
          <div className="font-medium mb-1">Refined &amp; learned</div>
          <ul className="text-xs space-y-0.5 text-slate-600 dark:text-slate-400">
            {items.map((it) => <li key={it}>{it}</li>)}
          </ul>
          <button
            onClick={() => { setVisible(false); onClickReview(); }}
            className="mt-2 text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
          >
            Review activity →
          </button>
        </div>
        <button
          onClick={() => setVisible(false)}
          className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 shrink-0"
          aria-label="Dismiss"
        >
          <X className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}
