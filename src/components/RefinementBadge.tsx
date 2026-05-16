import { Loader2, Sparkles, AlertCircle } from 'lucide-react';
import { RefinementStatus } from '../utils/api';

interface Props {
  status: RefinementStatus;
}

export default function RefinementBadge({ status }: Props) {
  if (!status) return null;

  if (status === 'pending') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
        <Loader2 className="w-3 h-3 animate-spin" />
        Queued for refinement
      </span>
    );
  }
  if (status === 'processing') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-700 dark:text-amber-400">
        <Loader2 className="w-3 h-3 animate-spin" />
        Refining…
      </span>
    );
  }
  if (status === 'done') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-500/20 text-green-700 dark:text-green-400"
            title="Transcript corrections, speaker names, and learning have been applied">
        <Sparkles className="w-3 h-3" />
        Refined
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-rose-500/20 text-rose-700 dark:text-rose-400"
            title="Refinement failed — verbatim transcript is still available">
        <AlertCircle className="w-3 h-3" />
        Refinement failed
      </span>
    );
  }
  return null;
}
