import { useState } from 'react';
import { UserX, UserCheck, UserPlus, X } from 'lucide-react';
import { AutoSpeakerMatch, Speaker } from '../utils/api';

/**
 * Resolved target of a reject flow — passed to onAccept by the modal.
 *   - { kind: 'existing', speakerId } — re-attribute to an existing speaker
 *   - { kind: 'new', name } — create a new speaker (backend extracts embedding)
 *   - { kind: 'unknown' } — strip the name, mark the label anonymous
 */
export type RejectTarget =
  | { kind: 'existing'; speakerId: string; name: string }
  | { kind: 'new'; name: string }
  | { kind: 'unknown' };

interface Props {
  label: string;                          // diarization label, e.g. "SPEAKER_00"
  currentMatch: AutoSpeakerMatch;         // the rejected B5 match
  runnerUp?: AutoSpeakerMatch['runner_up']; // null/undefined when no 2nd-best
  registry: Speaker[];                    // for the picker dropdown
  onAccept: (target: RejectTarget) => void;
  onClose: () => void;
}

export default function RejectMatchModal({
  label,
  currentMatch,
  runnerUp,
  registry,
  onAccept,
  onClose,
}: Props) {
  const [pickerValue, setPickerValue] = useState('');
  const [newName, setNewName] = useState('');

  const currentConf = Math.round((currentMatch.confidence ?? 0) * 100);
  const runnerConf = runnerUp ? Math.round((runnerUp.confidence ?? 0) * 100) : null;

  const handlePicker = () => {
    const target = registry.find((s) => s.speaker_id === pickerValue);
    if (target) onAccept({ kind: 'existing', speakerId: target.speaker_id, name: target.name });
  };

  const handleCreate = () => {
    const trimmed = newName.trim();
    if (trimmed) onAccept({ kind: 'new', name: trimmed });
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={`reject-match-title-${label}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-white dark:bg-slate-800 rounded-xl shadow-2xl p-5 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <h3
            id={`reject-match-title-${label}`}
            className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2"
          >
            <UserX className="w-5 h-5 text-rose-500" aria-hidden="true" />
            Reject voice match for {label}
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        {/* Rejected match — greyed out */}
        <div className="px-3 py-2 rounded-lg bg-slate-100 dark:bg-slate-700/40 opacity-60">
          <div className="text-xs text-slate-500 dark:text-slate-400 mb-1">
            B5 thought this was:
          </div>
          <div className="text-sm font-medium text-slate-700 dark:text-slate-300 line-through">
            {currentMatch.name ?? 'Unknown'} ({currentConf}%)
          </div>
        </div>

        {/* Runner-up suggestion (when 5A backend supplies it) */}
        {runnerUp && (
          <div className="px-3 py-3 rounded-lg bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800/40">
            <div className="text-xs text-slate-500 dark:text-slate-400 mb-1">
              Did you mean instead?
            </div>
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm font-medium text-indigo-700 dark:text-indigo-300">
                {runnerUp.name} ({runnerConf}%)
              </div>
              <button
                type="button"
                onClick={() => onAccept({
                  kind: 'existing',
                  speakerId: runnerUp.speaker_id,
                  name: runnerUp.name,
                })}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-500 text-white hover:bg-indigo-600"
              >
                <UserCheck className="w-3.5 h-3.5" aria-hidden="true" />
                Use this
              </button>
            </div>
          </div>
        )}

        {/* Picker dropdown — free-form re-attribution from the full registry */}
        <div>
          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
            Or pick another speaker:
          </label>
          <div className="flex items-center gap-2">
            <select
              value={pickerValue}
              onChange={(e) => setPickerValue(e.target.value)}
              className="flex-1 px-3 py-1.5 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              <option value="">— Select —</option>
              {registry.map((s) => (
                <option key={s.speaker_id} value={s.speaker_id}>{s.name}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={handlePicker}
              disabled={!pickerValue}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
            >
              Use
            </button>
          </div>
        </div>

        {/* Inline create new speaker */}
        <div>
          <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
            Or create a new speaker:
          </label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="New speaker name"
              className="flex-1 px-3 py-1.5 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-blue-400"
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            />
            <button
              type="button"
              onClick={handleCreate}
              disabled={!newName.trim()}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
            >
              <UserPlus className="w-3.5 h-3.5" aria-hidden="true" />
              Create
            </button>
          </div>
        </div>

        {/* Escape hatch */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-200 dark:border-slate-700">
          <button
            type="button"
            onClick={() => onAccept({ kind: 'unknown' })}
            className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 underline"
          >
            Mark as Unknown
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-600"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
