import { useEffect, useState } from 'react';
import { Edit3, Save, X, Loader2, AlertCircle } from 'lucide-react';
import { renameJobSource } from '../utils/api';

interface RefinementAnalysis {
  domain?: string;
  summary?: string;
  speakers?: Array<{ name?: string; label?: string }>;
}

interface Props {
  jobId: string;
  currentFilename: string;
  jobCreatedAt?: string;  // ISO timestamp; used for the date prefix
  analysis?: RefinementAnalysis | null;
  onClose: () => void;
  onRenamed: (newName: string) => void;
}

// Strip filesystem-unsafe characters and collapse whitespace.
function sanitize(s: string): string {
  return s
    .replace(/[/\\:*?"<>|]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function suggestName(
  currentFilename: string,
  jobCreatedAt: string | undefined,
  analysis: RefinementAnalysis | null | undefined
): string {
  const ext = currentFilename.includes('.') ? currentFilename.slice(currentFilename.lastIndexOf('.')) : '';

  // Date prefix: prefer job timestamp, fall back to extracting from current
  // filename (JPR pattern HH-MM-SS.m4a doesn't carry a date in the name itself).
  let datePrefix = '';
  if (jobCreatedAt) {
    const d = new Date(jobCreatedAt);
    if (!isNaN(d.getTime())) {
      const pad = (n: number) => String(n).padStart(2, '0');
      datePrefix = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}-${pad(d.getMinutes())} — `;
    }
  }

  if (!analysis) return currentFilename;

  const domain = sanitize(analysis.domain ?? '').slice(0, 60);
  const namedSpeakers = (analysis.speakers ?? [])
    .map((s) => sanitize(s.name ?? ''))
    .filter((n) => n && !/^SPEAKER_\d+$/i.test(n))
    .slice(0, 3);
  const withWho = namedSpeakers.length > 0 ? ` with ${namedSpeakers.join(' & ')}` : '';

  const body = domain || sanitize(analysis.summary ?? '').slice(0, 60) || currentFilename.replace(ext, '');
  return `${datePrefix}${body}${withWho}${ext}`;
}

export default function RenameFileModal({
  jobId, currentFilename, jobCreatedAt, analysis, onClose, onRenamed,
}: Props) {
  const [newName, setNewName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setNewName(suggestName(currentFilename, jobCreatedAt, analysis));
  }, [currentFilename, jobCreatedAt, analysis]);

  const handleSave = async () => {
    if (!newName.trim() || newName === currentFilename) return;
    setSaving(true);
    setError(null);
    try {
      const res = await renameJobSource(jobId, newName);
      onRenamed(res.new_name);
      onClose();
    } catch (e: any) {
      setError(e.message || 'Rename failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white dark:bg-slate-900 rounded-lg shadow-xl max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <Edit3 className="w-5 h-5" />
            Rename recording file
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="text-sm text-slate-600 dark:text-slate-400 mb-3">
          Renames the JPR audio file on disk. Suggestion derived from refinement
          analysis (call topic + identified speakers).
        </div>

        <div className="mb-3">
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Current</label>
          <div className="px-3 py-2 rounded bg-slate-100 dark:bg-slate-800 text-sm font-mono text-slate-700 dark:text-slate-300 truncate">
            {currentFilename}
          </div>
        </div>

        <div className="mb-3">
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">New name</label>
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="w-full px-3 py-2 rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm font-mono text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            placeholder="e.g. 2026-05-15 15-29 — SAFc partnership with Pascal Weber.m4a"
            spellCheck={false}
            autoFocus
          />
          {!analysis && (
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Refinement not yet complete — suggestion will improve once it finishes.
            </p>
          )}
        </div>

        {error && (
          <div className="mb-3 p-2 rounded bg-rose-50 dark:bg-rose-900/20 text-xs text-rose-700 dark:text-rose-400 flex items-start gap-1">
            <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" /> {error}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button onClick={onClose} disabled={saving}
                  className="px-3 py-1.5 text-sm rounded border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800">
            Cancel
          </button>
          <button onClick={handleSave}
                  disabled={saving || !newName.trim() || newName === currentFilename}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-sm rounded bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white">
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
            Rename
          </button>
        </div>
      </div>
    </div>
  );
}
