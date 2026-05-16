import { useState, useMemo } from 'react';
import { Activity, BookOpen, UserCheck, Sparkles, AlertCircle, ChevronLeft, ChevronRight, RefreshCw, Loader2 } from 'lucide-react';
import { useLearningLog } from '../hooks/useLearningLog';
import { LearningEvent } from '../utils/api';

// Pill filter maps a user-facing label to a backend `type=` value.
// `null` = no filter (show everything).
const PILLS: Array<{ label: string; type: string | null }> = [
  { label: 'All', type: null },
  { label: 'Glossary', type: 'glossary_add' },
  { label: 'Voices', type: 'embedding_update' },
  { label: 'Insights', type: 'insight_added' },
  { label: 'Failures', type: 'embedding_failed' },  // also covers insight_failed via second pass
];

function iconFor(type: string) {
  if (type === 'glossary_add') return <Sparkles className="w-3 h-3 text-amber-600 dark:text-amber-400" />;
  if (type === 'embedding_update') return <UserCheck className="w-3 h-3 text-indigo-600 dark:text-indigo-400" />;
  if (type === 'insight_added') return <BookOpen className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />;
  if (type.endsWith('_failed') || type.endsWith('_skipped')) {
    return <AlertCircle className="w-3 h-3 text-rose-600 dark:text-rose-400" />;
  }
  return <Activity className="w-3 h-3 text-slate-500" />;
}

function summarize(e: LearningEvent): string {
  switch (e.type) {
    case 'glossary_add':
      return `Learned term "${e.term ?? ''}"${e.source_phrase ? ` (from "${e.source_phrase}")` : ''}`;
    case 'embedding_update':
      return `Updated voice signature for ${e.speaker_name ?? 'speaker'} (${e.duration_sec?.toFixed(0) ?? '?'}s of speech)`;
    case 'embedding_skipped':
      return `Skipped voice update: ${e.reason ?? 'unknown reason'}`;
    case 'embedding_failed':
      return `Voice update failed for ${e.speaker_name ?? 'speaker'}: ${e.reason ?? 'unknown'}`;
    case 'insight_added':
      return `Added ${e.category ?? 'insight'} for ${e.speaker_name ?? 'speaker'}`;
    case 'insight_failed':
      return `Insight extraction failed: ${e.reason ?? (e.speaker_name ?? 'unknown')}`;
    default:
      return e.type;
  }
}

function groupByDay(events: LearningEvent[]): Array<{ day: string; events: LearningEvent[] }> {
  const groups: Array<{ day: string; events: LearningEvent[] }> = [];
  for (const e of events) {
    const day = e.ts.slice(0, 10);  // YYYY-MM-DD
    const last = groups[groups.length - 1];
    if (last && last.day === day) last.events.push(e);
    else groups.push({ day, events: [e] });
  }
  return groups;
}

export default function ActivityTimeline() {
  const [activePill, setActivePill] = useState(0);  // index into PILLS
  const filter = useMemo(() => ({ type: PILLS[activePill].type ?? undefined }), [activePill]);
  const { events, total, page, setPage, loading, error, reload, pageSize, hasNext, hasPrev } = useLearningLog(filter);

  const grouped = useMemo(() => groupByDay(events), [events]);

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
          <Activity className="w-5 h-5" />
          <h2 className="text-lg font-semibold">Activity</h2>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {total} {total === 1 ? 'event' : 'events'} total
          </span>
        </div>
        <button onClick={reload} disabled={loading}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-50"
                title="Reload">
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
        </button>
      </div>

      <div className="flex flex-wrap gap-1">
        {PILLS.map((p, i) => (
          <button
            key={p.label}
            onClick={() => { setActivePill(i); setPage(0); }}
            className={`px-3 py-1 text-xs rounded-full border transition ${
              i === activePill
                ? 'bg-indigo-600 border-indigo-600 text-white'
                : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="p-3 rounded bg-rose-50 dark:bg-rose-900/20 text-sm text-rose-700 dark:text-rose-400">
          {error}
        </div>
      )}

      {!loading && events.length === 0 && !error && (
        <div className="text-sm text-slate-500 dark:text-slate-400 p-4 text-center">
          No events yet. Transcribe a recording to start filling this in.
        </div>
      )}

      {grouped.map(({ day, events: dayEvents }) => (
        <div key={day} className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
          <div className="bg-slate-50 dark:bg-slate-800/40 px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-400">
            {day}
          </div>
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {dayEvents.map((e, idx) => (
              <li key={`${e.ts}-${idx}`} className="flex items-start gap-2 px-3 py-2 text-sm text-slate-700 dark:text-slate-300">
                <span className="mt-0.5 shrink-0">{iconFor(e.type)}</span>
                <div className="flex-1">
                  <div>{summarize(e)}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    {e.ts.slice(11, 19)} UTC{e.job_id ? ` · job ${e.job_id.slice(0, 8)}` : ''}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {(hasPrev || hasNext) && (
        <div className="flex items-center justify-between pt-2">
          <button onClick={() => setPage(page - 1)} disabled={!hasPrev}
                  className="inline-flex items-center gap-1 px-3 py-1 text-xs rounded border border-slate-200 dark:border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed">
            <ChevronLeft className="w-3 h-3" /> Prev
          </button>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Page {page + 1} of {Math.max(1, Math.ceil(total / pageSize))}
          </span>
          <button onClick={() => setPage(page + 1)} disabled={!hasNext}
                  className="inline-flex items-center gap-1 px-3 py-1 text-xs rounded border border-slate-200 dark:border-slate-700 disabled:opacity-40 disabled:cursor-not-allowed">
            Next <ChevronRight className="w-3 h-3" />
          </button>
        </div>
      )}
    </div>
  );
}
