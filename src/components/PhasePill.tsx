import React from 'react';

interface PhasePillProps {
  phase?: string | null;
}

const PHASE_LABELS: Record<string, string> = {
  diarizing: 'Diarizing…',
  transcribing: 'Transcribing…',
  aligning: 'Aligning…',
  awaiting_speakers: 'Speakers to verify',
  refining: 'Refining…',
  learning: 'Learning…',
};

// Per-phase color overrides. Default = blue (active processing). The
// Legacy `awaiting_speakers` phase is a user-action signal.
const PHASE_COLORS: Record<string, { pill: string; dot: string }> = {
  awaiting_speakers: {
    pill: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
    dot: 'bg-amber-500',
  },
};

const DEFAULT_COLORS = {
  pill: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  dot: 'bg-blue-500',
};

function PhasePill({ phase }: PhasePillProps) {
  if (!phase) return null;

  const label = PHASE_LABELS[phase] ?? `${phase.charAt(0).toUpperCase()}${phase.slice(1)}…`;
  const colors = PHASE_COLORS[phase] ?? DEFAULT_COLORS;

  return (
    <span
      role="status"
      aria-live="polite"
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${colors.pill}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${colors.dot}`} aria-hidden="true" />
      {label}
    </span>
  );
}

export default React.memo(PhasePill);
