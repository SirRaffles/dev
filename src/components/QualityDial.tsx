import React from 'react';
import { Sparkles, Zap } from 'lucide-react';

export type QualityMode = 'auto-best' | 'auto-quick';

interface QualityDialProps {
  value: QualityMode;
  onChange: (next: QualityMode) => void;
  disabled?: boolean;
}

interface DialOption {
  id: QualityMode;
  label: string;
  subLabel: string;
  waitLabel: string;
  Icon: typeof Sparkles;
  activeClass: string;
}

const OPTIONS: DialOption[] = [
  {
    id: 'auto-best',
    label: 'Best',
    subLabel: 'Full pipeline',
    waitLabel: '~10 min',
    Icon: Sparkles,
    activeClass: 'bg-blue-500 text-white border-blue-500',
  },
  {
    id: 'auto-quick',
    label: 'Quick',
    subLabel: 'Fast preview',
    waitLabel: '~30 sec',
    Icon: Zap,
    activeClass: 'bg-teal-500 text-white border-teal-500',
  },
];

function QualityDial({ value, onChange, disabled = false }: QualityDialProps) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
        Quality
      </label>
      <div
        role="radiogroup"
        aria-label="Quality"
        className="grid grid-cols-2 gap-2"
      >
        {OPTIONS.map(({ id, label, subLabel, waitLabel, Icon, activeClass }) => {
          const selected = value === id;
          return (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => { if (!disabled) onChange(id); }}
              disabled={disabled}
              className={`flex flex-col items-center justify-center gap-1 px-4 py-4 rounded-xl font-medium border transition-all disabled:opacity-50 ${
                selected
                  ? activeClass
                  : 'bg-slate-100 text-slate-700 border-slate-300 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-200 dark:border-slate-600 dark:hover:bg-slate-600'
              }`}
            >
              <div className="flex items-center gap-2">
                <Icon className="w-4 h-4" aria-hidden="true" />
                <span>{label}</span>
              </div>
              <span className={`text-xs ${selected ? 'opacity-90' : 'opacity-70'}`}>
                {subLabel}
              </span>
              <span className={`text-xs ${selected ? 'opacity-90' : 'opacity-70'}`}>
                {waitLabel}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default React.memo(QualityDial);
