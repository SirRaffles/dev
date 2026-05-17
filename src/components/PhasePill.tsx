import React from 'react';

interface PhasePillProps {
  phase?: string | null;
}

const PHASE_LABELS: Record<string, string> = {
  diarizing: 'Diarizing…',
  transcribing: 'Transcribing…',
  aligning: 'Aligning…',
  refining: 'Refining…',
  learning: 'Learning…',
};

function PhasePill({ phase }: PhasePillProps) {
  if (!phase) return null;

  const label = PHASE_LABELS[phase] ?? `${phase.charAt(0).toUpperCase()}${phase.slice(1)}…`;

  return (
    <span
      role="status"
      aria-live="polite"
      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" aria-hidden="true" />
      {label}
    </span>
  );
}

export default React.memo(PhasePill);
