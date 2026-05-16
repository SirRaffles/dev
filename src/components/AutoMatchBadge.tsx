import { useState } from 'react';
import { Check, X, UserCheck } from 'lucide-react';
import { AutoSpeakerMatch } from '../utils/api';

interface Props {
  label: string;            // pyannote label, e.g. "SPEAKER_00"
  match: AutoSpeakerMatch;
  onAccept: (label: string, name: string, speakerId: string) => Promise<void> | void;
  onReject: (label: string) => void;
}

export default function AutoMatchBadge({ label, match, onAccept, onReject }: Props) {
  const [busy, setBusy] = useState(false);
  if (!match || !match.matched || !match.name) return null;
  const conf = Math.round((match.confidence ?? 0) * 100);

  const handleAccept = async () => {
    if (!match.speaker_id || !match.name) return;
    setBusy(true);
    try {
      await onAccept(label, match.name, match.speaker_id);
    } finally {
      setBusy(false);
    }
  };

  return (
    <span className="inline-flex items-center gap-1 ml-2 px-1.5 py-0.5 text-xs rounded bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/50"
          title={`Voice-matched from registry (${conf}% confident, ${match.source ?? 'registry'})`}>
      <UserCheck className="w-3 h-3" />
      auto · {conf}%
      <button onClick={handleAccept} disabled={busy}
              className="ml-1 hover:text-emerald-700 dark:hover:text-emerald-400 disabled:opacity-50"
              title="Accept this auto-match">
        <Check className="w-3 h-3" />
      </button>
      <button onClick={() => onReject(label)}
              className="hover:text-rose-700 dark:hover:text-rose-400"
              title="Reject (revert to SPEAKER_XX)">
        <X className="w-3 h-3" />
      </button>
    </span>
  );
}
