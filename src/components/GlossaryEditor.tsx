import { useEffect, useState } from 'react';
import { Loader2, Save, BookOpen, AlertCircle, CheckCircle, ArrowUpCircle } from 'lucide-react';
import { fetchGlobalGlossary, saveGlobalGlossary } from '../utils/api';

interface Props {
  /**
   * Glossary file path. Defaults to '_global.md' (the cross-context glossary).
   * Plan 4 will add per-context glossaries by passing this prop with a
   * different path, reusing this component as-is.
   */
  path?: string;
}

const ACTIVE_HEADER = '## Active';
const PENDING_HEADER = '## Auto-learned (pending review)';

/**
 * Promote a pending bullet to the Active section.
 *
 * "Promote" semantics: MOVE the line (remove from Pending, add a clean
 * "- TERM" line to Active). Source metadata stays in learning_log.jsonl,
 * not in the file. This matches user decision Q3.
 */
function promoteLine(body: string, line: string): string {
  const lines = body.split('\n');
  const out: string[] = [];
  let inPending = false;
  let inActive = false;
  let activeEndIdx = -1;

  // Extract just the term from the bullet (strip "- " prefix and " (from ...)" suffix).
  const match = line.match(/^-\s+([^(]+?)\s*(?:\(from\b.*)?$/);
  const promotedTerm = (match?.[1] ?? line.replace(/^-\s+/, '')).trim();

  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i];
    if (ln.startsWith('## ')) {
      inPending = ln === PENDING_HEADER;
      inActive = ln === ACTIVE_HEADER;
    }
    if (inPending && ln.trim() === line.trim()) {
      // Skip this line (remove from Pending).
      continue;
    }
    out.push(ln);
    // Record the FIRST `## Active` header position only — stay consistent with
    // parseSections() which also uses first-match semantics. Duplicate Active
    // headers are user-error; we don't try to be clever about them.
    if (inActive && ln === ACTIVE_HEADER && activeEndIdx === -1) {
      activeEndIdx = out.length;
    }
  }

  if (!promotedTerm) return out.join('\n');

  // Insert "- TERM" right after the Active header (with a blank line if needed).
  if (activeEndIdx >= 0) {
    // Skip past the blank line that typically follows a header.
    let insertAt = activeEndIdx;
    if (out[insertAt] === '') insertAt += 1;
    out.splice(insertAt, 0, `- ${promotedTerm}`);
  } else {
    // No Active section — append one at the end.
    out.push('', ACTIVE_HEADER, '', `- ${promotedTerm}`);
  }

  return out.join('\n');
}

function parseSections(body: string): { activeBody: string; pendingLines: string[] } {
  const lines = body.split('\n');
  const activeStart = lines.findIndex(l => l === ACTIVE_HEADER);
  const pendingStart = lines.findIndex(l => l === PENDING_HEADER);
  const activeEnd = pendingStart > activeStart ? pendingStart : lines.length;
  const activeBody = activeStart >= 0
    ? lines.slice(activeStart, activeEnd).join('\n')
    : '';
  const pendingLines: string[] = [];
  if (pendingStart >= 0) {
    for (let i = pendingStart + 1; i < lines.length; i++) {
      const ln = lines[i];
      if (ln.startsWith('## ')) break;
      if (ln.startsWith('- ')) pendingLines.push(ln);
    }
  }
  return { activeBody, pendingLines };
}

export default function GlossaryEditor({ path = '_global.md' }: Props) {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchGlobalGlossary()
      .then((d) => setContent(d.content || ''))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [path]);  // re-fetch when path changes (Plan 4 future-proof)

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await saveGlobalGlossary(content);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handlePromote = async (line: string) => {
    const next = promoteLine(content, line);
    setContent(next);
    setSaving(true);
    setError(null);
    try {
      await saveGlobalGlossary(next);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: any) {
      setError(e.message);
      // Revert on failure
      setContent(content);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 p-4">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading glossary…
      </div>
    );
  }

  const { pendingLines } = parseSections(content);
  const label = path === '_global.md' ? 'Global glossary' : `Glossary · ${path}`;

  return (
    <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-4 sm:p-6 border border-slate-200 dark:border-slate-700">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
          <BookOpen className="w-4 h-4" />
          <span className="font-medium">{label}</span>
          <span className="text-xs text-slate-500 dark:text-slate-400 hidden sm:inline">
            Auto-injected into transcription prompts + refinement context
          </span>
        </div>
        <div className="flex items-center gap-2">
          {saved && (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700 dark:text-emerald-400">
              <CheckCircle className="w-3 h-3" /> Saved
            </span>
          )}
          {error && (
            <span className="inline-flex items-center gap-1 text-xs text-rose-700 dark:text-rose-400" title={error}>
              <AlertCircle className="w-3 h-3" /> {error.slice(0, 40)}
            </span>
          )}
          <button onClick={handleSave} disabled={saving}
                  className="inline-flex items-center gap-1 px-3 py-1 text-xs rounded bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white">
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
            Save
          </button>
        </div>
      </div>

      {pendingLines.length > 0 && (
        <div className="mb-3 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/50">
          <div className="text-xs font-medium text-amber-800 dark:text-amber-300 mb-2">
            {pendingLines.length} auto-learned term{pendingLines.length === 1 ? '' : 's'} pending review
          </div>
          <ul className="space-y-2">
            {pendingLines.map((line) => {
              // Parse "- TERM (from job-id: source_phrase)" into 2 visual parts:
              // a primary "term" chunk and a secondary "context" caption underneath.
              // Keeps long context phrases from breaking the row layout.
              const m = line.match(/^-\s+([^(]+?)\s*(?:\((.*)\))?$/);
              const term = (m?.[1] ?? line.replace(/^-\s+/, '')).trim();
              const context = m?.[2]?.trim();
              return (
                <li key={line} className="flex items-start justify-between gap-3 text-sm">
                  <div className="flex-1 min-w-0">
                    <div className="font-mono font-medium text-slate-800 dark:text-slate-200 break-words">{term}</div>
                    {context && (
                      <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 break-words">
                        {context}
                      </div>
                    )}
                  </div>
                  <button onClick={() => handlePromote(line)} disabled={saving}
                          className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white shrink-0 mt-0.5"
                          title="Promote to Active section">
                    <ArrowUpCircle className="w-3 h-3" />
                    Promote
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <textarea
        className="w-full h-80 p-3 font-mono text-sm bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 rounded text-slate-800 dark:text-slate-200 focus:ring-1 focus:ring-indigo-500 focus:outline-none resize-y"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder={"# Global Glossary\n\n## Active\n\nPascal Weber, Manukai, DMG Mori\n\n## Auto-learned (pending review)\n\n(High-confidence corrections land here. Review each item, then move to Active or delete.)"}
        spellCheck={false}
      />
    </div>
  );
}
